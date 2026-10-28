# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Opt-in native v5/v6 head/floor binding and dwell checks, called by palm_preflight [N, s]."""

from pathlib import Path

import torch
from isaaclab.utils.math import quat_apply, quat_apply_inverse


@torch.inference_mode()
def check(live, result: dict, *, terrain_suite: bool = False) -> dict:
    """Check real sensor buffers, then produce a short forced head-floor contact sample.

    The final root reposition is an isolated measurement fixture, not a policy
    rollout, balance test or reset change. Never call this on a training process.
    """
    sensor = live.scene['head_ground_contact']
    cfg = live.termination_manager.get_term_cfg('head_ground_contact')
    term = cfg.func
    from pxr import UsdPhysics

    floor = live.sim.stage.GetPrimAtPath(cfg.params['floor_prim_path'])
    result.update(body_names=sensor.body_names, sensor_paths=list(sensor.contact_view.sensor_paths),
                  floor_paths=list(sensor.contact_view.filter_paths), filter_count=sensor.contact_view.filter_count,
                  floor_prim_valid=floor.IsValid(), floor_collision_api=floor.HasAPI(UsdPhysics.CollisionAPI),
                  floor_prim_type=floor.GetTypeName() if floor.IsValid() else None,
                  dt_s=live.physics_dt, dwell_s=cfg.params['dwell_s'], controlled_physics_steps=0)
    assert sensor.body_names == ['neck_pitch']
    assert all(row == cfg.params['floor_prim_path'] or row == [cfg.params['floor_prim_path']]
               for row in sensor.contact_view.filter_paths)
    assert sensor.contact_view.filter_count == 1
    assert floor.IsValid() and floor.HasAPI(UsdPhysics.CollisionAPI)
    history = sensor.data.force_matrix_w_history.torch
    net = sensor.data.net_forces_w_history.torch
    saved_history, saved_net = history.clone(), net.clone()
    try:
        term.reset()
        history.zero_()
        net.fill_(100.)
        assert not term(live, **cfg.params).any(), 'unfiltered net force leaked into ground dwell'
        history[..., 2] = 10.
        trace = []
        for step in range(1, 26):
            done = term(live, **cfg.params)
            trace.append(int(done.sum()))
            assert bool(done.all()) == (step == 25)
        result['injected_continuous_10n_done_counts'] = trace
        term.reset(torch.tensor([0], device=live.device))
        done = term(live, **cfg.params)
        assert not done[0] and done[1:].all()
        result['partial_reset_steps'] = term._steps.cpu().tolist()
        term.reset()
        for _ in range(24):
            term(live, **cfg.params)
        history[:, 1, 0, 0, 2] = 0.
        assert not term(live, **cfg.params).any()
        assert torch.equal(term._steps, torch.ones_like(term._steps))
        result['one_substep_gap_steps'] = term._steps.cpu().tolist()
    finally:
        history.copy_(saved_history)
        net.copy_(saved_net)
        term.reset()
    result['native_clear_head_floor_max_n'] = float(torch.linalg.vector_norm(saved_history, dim=-1).max())

    robot = live.scene['robot']
    index = list(robot.body_names).index('neck_pitch')
    mesh = Path(__file__).resolve().parents[2]/'lizard2_palm_spatial/meshes/collision/neck_pitch_collision.obj'
    vertices = torch.tensor([list(map(float, row.split()[1:4])) for row in mesh.read_text().splitlines()
                             if row.startswith('v ')], device=live.device)
    position = robot.data.body_link_pos_w.torch[:, index]
    rotation = robot.data.body_link_quat_w.torch[:, index]
    points = quat_apply(rotation[:, None, :].expand(-1, len(vertices), -1).reshape(-1, 4),
                        vertices[None].expand(live.num_envs, -1, -1).reshape(-1, 3))
    pose = robot.data.root_link_pose_w.torch.clone()
    head_world = points.reshape(live.num_envs, -1, 3) + position[:, None, :]
    # Pitch forward so the head reaches the floor while the trunk stays above it.
    local = quat_apply_inverse(pose[:, None, 3:].expand(-1, len(vertices), -1).reshape(-1, 4),
                               (head_world-pose[:, None, :3]).reshape(-1, 3))
    rotation = torch.tensor([0., .4794255386, 0., .8775825619], device=live.device)
    rotated = quat_apply(rotation.expand(len(local), 4), local).reshape(live.num_envs, -1, 3)
    pose[:, 3:] = rotation
    if terrain_suite:
        origin = live.scene.terrain.terrain_origins[0, 0]
        result['terrain_origins'] = live.scene.terrain.terrain_origins.cpu().tolist()
        result['initial_terrain_types'] = live.scene.terrain.terrain_types.cpu().tolist()
        result['fixture_flat_origin'] = origin.cpu().tolist()
        # Both robots occupy separated locations on the same flat tile.
        pose[:, 0] = origin[0] + torch.tensor([-1., 1.], device=live.device)
        pose[:, 1] = origin[1]
        pose[:, 2] = origin[2] - rotated[:, :, 2].min(dim=1).values - .01
    else:
        pose[:, 2] = -rotated[:, :, 2].min(dim=1).values - .01
    joints = robot.data.joint_pos.torch.clone()
    zero_velocity = torch.zeros(live.num_envs, 6, device=live.device)
    samples = result['native_forced_head_floor_force_w_n'] = []
    native_done = result['native_continuous_done_counts'] = []
    result['fixture_root_pose'] = pose.cpu().tolist()
    term.reset()
    for step in range(1, 101):
        robot.write_joint_state_to_sim(joints, torch.zeros_like(joints))
        robot.write_root_link_pose_to_sim_index(root_pose=pose)
        robot.write_root_com_velocity_to_sim_index(root_velocity=zero_velocity)
        live.scene.write_data_to_sim()
        live.sim.forward()
        live.sim.step(render=False)
        live.scene.update(live.physics_dt)
        force = sensor.data.force_matrix_w.torch[:, 0, 0].clone()
        samples.append(force.cpu().tolist())
        result['controlled_physics_steps'] += 1
        if step % live.cfg.decimation == 0:
            done = term(live, **cfg.params)
            native_done.append(int(done.sum()))
            assert bool(done.all()) == (step == 100), 'native dwell fired at the wrong physics step'
    assert torch.isfinite(torch.tensor(samples)).all()
    assert (torch.linalg.vector_norm(torch.tensor(samples), dim=-1) > cfg.params['threshold']).all(), \
        'forced head-floor contact did not continuously reach the filtered channel'
    if terrain_suite:
        box_sensor = live.scene['head_probe_contact']
        box_path = '/World/HeadProbeBox/geometry/mesh'
        box = live.sim.stage.GetPrimAtPath(box_path)
        non_ground = result['native_non_ground'] = dict(
            box_path=box_path, box_prim_valid=box.IsValid(),
            box_collision_api=box.HasAPI(UsdPhysics.CollisionAPI),
            box_prim_type=box.GetTypeName() if box.IsValid() else None,
            sensor_paths=list(box_sensor.contact_view.sensor_paths),
            filter_paths=list(box_sensor.contact_view.filter_paths),
            filter_count=box_sensor.contact_view.filter_count,
            box_force_w_n=[], ground_force_w_n=[], done_counts=[])
        assert box.IsValid() and box.HasAPI(UsdPhysics.CollisionAPI)
        assert box_sensor.body_names == ['neck_pitch']
        assert box_sensor.contact_view.filter_count == 1
        assert all(row == box_path or row == [box_path] for row in box_sensor.contact_view.filter_paths)
        # Box top is 2 m above the flat tile; the head never touches terrain.
        pose[:, 2] += 2.
        non_ground['fixture_root_pose'] = pose.cpu().tolist()
        term.reset()
        for step in range(1, 101):
            robot.write_joint_state_to_sim(joints, torch.zeros_like(joints))
            robot.write_root_link_pose_to_sim_index(root_pose=pose)
            robot.write_root_com_velocity_to_sim_index(root_velocity=zero_velocity)
            live.scene.write_data_to_sim()
            live.sim.forward()
            live.sim.step(render=False)
            live.scene.update(live.physics_dt)
            non_ground['box_force_w_n'].append(box_sensor.data.force_matrix_w.torch[:, 0, 0].cpu().tolist())
            non_ground['ground_force_w_n'].append(sensor.data.force_matrix_w.torch[:, 0, 0].cpu().tolist())
            if step % live.cfg.decimation == 0:
                non_ground['done_counts'].append(int(term(live, **cfg.params).sum()))
        box_force = torch.tensor(non_ground['box_force_w_n'])
        ground_force = torch.tensor(non_ground['ground_force_w_n'])
        assert torch.isfinite(box_force).all() and torch.isfinite(ground_force).all()
        assert (torch.linalg.vector_norm(box_force, dim=-1) > cfg.params['threshold']).all(), \
            'non-ground contact did not continuously reach its own filtered channel'
        assert (torch.linalg.vector_norm(ground_force, dim=-1) <= cfg.params['threshold']).all(), \
            'non-ground contact leaked into ground filtered channel'
        assert not any(non_ground['done_counts']), 'non-ground contact triggered dwell'
        non_ground['passed'] = True
    result['passed'] = True
    return result
