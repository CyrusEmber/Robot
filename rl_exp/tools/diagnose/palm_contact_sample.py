# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Read native body-to-ground contact patches on the isolated training draft.

One environment, zero actions, at most 100 control/400 physics steps (2 s),
unchanged gravity/PD/caps/TGS/false and original terminations. No external force,
velocity reference, policy, lift or walking controller. Contact views observe
exact body/floor paths without changing collision filters. Units: m, s, N,
rad, rad/s, m/s. --audit replays raw arrays without Kit and rejects corruptions.
"""
from __future__ import annotations

import argparse
import copy
import inspect
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402
from palm_training_interface import DRAFT, DRAFT_SHA, TASK, equal  # noqa: E402
from palm_spatial_inertia import _rotation, csc  # noqa: E402
from palm_spatial_runtime import pair_binding  # noqa: E402

CAPACITY = 256


def contact_patch(arrays):
    """Slice one exact body/floor pair's native buffers [N, m, unit normal]."""
    forces, points, normals, separations, counts, starts = arrays
    assert counts.shape == starts.shape == (1, 1)
    assert forces.shape == separations.shape == (CAPACITY, 1)
    assert points.shape == normals.shape == (CAPACITY, 3)
    count, start = int(counts[0, 0]), int(starts[0, 0])
    assert 0 <= count < CAPACITY and (count == 0 or 0 <= start <= CAPACITY-count)
    selected = slice(start, start+count) if count else slice(0, 0)
    return dict(count=count, start=start, forces=forces[selected].reshape(-1).tolist(),
                points=points[selected].tolist(), normals=normals[selected].tolist(),
                separations=separations[selected].reshape(-1).tolist())


def material_velocity(points, com_pose, com_velocity):
    """Velocity of rigid material at world points [m/s], COM velocity [m/s, rad/s]."""
    return np.asarray(com_velocity)[:3] + np.cross(
        np.asarray(com_velocity)[3:], np.asarray(points).reshape(-1, 3)-np.asarray(com_pose)[:3])


def pose_velocity(points, previous, current, dt):
    """Backward displacement of the SAME current material points [m/s].

    Contact patch indices are not material identifiers. Map current world points
    into the actor frame, then through the previous actor transform. This is an
    interval estimate, not an exact instantaneous velocity or contact tracking.
    """
    local = (np.asarray(points).reshape(-1, 3)-current[:3]) @ _rotation(current[3:])
    before = local @ _rotation(previous[3:]).T + previous[:3]
    return (np.asarray(points).reshape(-1, 3)-before)/dt


def inspect_report(r):
    """Check raw force conservation and summarize sampled ground contact [SI]."""
    assert r['completed'] and r['closed']
    assert r['settings'] == dict(dt_s=.005, decimation=4, controls=100, capacity=CAPACITY)
    assert r['readbacks']['force_timing'] is False and r['readbacks']['solver'] == 'TGS'
    assert r['readbacks']['fixed_base'] is False and r['readbacks']['self_collisions'] is True
    assert not any(r['readbacks']['disable_gravity'].values())
    bodies, feet, tails = r['body_names'], set(r['feet']), set(r['tails'])
    assert len(feet) == 4 and feet.isdisjoint(tails)
    assert set(r['views']) == set(r['vertices']) and feet <= set(r['views'])
    for name, mapping in r['views'].items():
        pair_binding(mapping['sensor_paths'], mapping['filter_paths'], mapping['body'],
                     [r['floor']], (1, 1, 3))
        assert mapping['body'].rsplit('/', 1)[-1] == name
    assert 0 < len(r['samples']) <= 400 and len(r['samples']) == 4*len(r['steps'])
    group_loads, contacts, gaps = [], {}, []
    previous = np.asarray(r['initial_actor_pose'])
    for index, row in enumerate(r['samples']):
        assert row['step'] == index+1
        assert set(row['contacts']) == set(r['views'])
        equal(row['raw_actions'], np.zeros((1, 30)), 'zero raw actions', atol=0.)
        equal(row['position_targets'], np.zeros((1, 30)), 'zero position targets', atol=0.)
        equal(row['velocity_targets'], np.zeros((1, 30)), 'zero velocity targets', atol=0.)
        actors = np.asarray(row['actor_pose'])
        coms, velocities = np.asarray(row['com_pose']), np.asarray(row['com_velocity'])
        assert actors.shape == coms.shape == (len(bodies), 7)
        assert velocities.shape == (len(bodies), 6)
        assert all(np.isfinite(a).all() for a in (actors, coms, velocities))
        load = dict(feet=0., tail=0., other=0.)
        for name, patch in row['contacts'].items():
            count, start = patch['count'], patch['start']
            assert isinstance(count, int) and 0 <= count < CAPACITY
            assert isinstance(start, int) and (count == 0 or 0 <= start < CAPACITY-count+1)
            points = np.asarray(patch['points']).reshape(-1, 3)
            normals = np.asarray(patch['normals']).reshape(-1, 3)
            magnitudes = np.asarray(patch['forces']).reshape(-1)
            separations = np.asarray(patch['separations']).reshape(-1)
            assert points.shape == normals.shape == (count, 3)
            assert magnitudes.shape == separations.shape == (count,)
            assert all(np.isfinite(a).all() for a in (points, normals, magnitudes, separations))
            aggregate = (magnitudes[:, None]*normals).sum(axis=0)
            equal(aggregate, patch['ground_force'], name+' patch force sum', atol=.002)
            body_id = bodies.index(name)
            equal(patch['net_force'], np.asarray(row['net_forces'])[body_id], name+' net force', atol=.002)
            group = 'feet' if name in feet else 'tail' if name in tails else 'other'
            load[group] += float(aggregate[2])
            if count:
                equal(np.linalg.norm(normals, axis=1), np.ones(count), name+' normals', atol=1.e-4)
                assert magnitudes.min() >= -1.e-6
                native = material_velocity(points, coms[body_id], velocities[body_id])
                displacement = pose_velocity(points, previous[body_id], actors[body_id], .005)
                tangent = lambda v: v-(v*normals).sum(axis=-1, keepdims=True)*normals
                # The candidate is a geometric probe, not a ground contact point.
                vertices = np.asarray(r['vertices'][name]) @ _rotation(actors[body_id, 3:]).T + actors[body_id, :3]
                candidate = vertices[vertices[:, 2].argmin()]
                candidate_native = material_velocity(candidate, coms[body_id], velocities[body_id])
                candidate_displacement = pose_velocity(candidate, previous[body_id], actors[body_id], .005)
                positive = magnitudes > 0
                contacts.setdefault(name, []).append(dict(step=index+1, count=count,
                    positive_force=bool(positive.any()),
                    loaded_native_speed_m_s=float(np.linalg.norm(tangent(native)[positive], axis=1).max())
                        if positive.any() else None,
                    loaded_displacement_speed_m_s=float(np.linalg.norm(tangent(displacement)[positive], axis=1).max())
                        if positive.any() else None,
                    force_z_n=float(aggregate[2]),
                    native_speed_m_s=float(np.linalg.norm(tangent(native), axis=1).max()),
                    displacement_speed_m_s=float(np.linalg.norm(tangent(displacement), axis=1).max()),
                    candidate_distance_m=float(np.linalg.norm(points-candidate, axis=1).min()),
                    candidate_native_speed_m_s=float(np.linalg.norm(tangent(candidate_native), axis=1).max()),
                    candidate_displacement_speed_m_s=float(np.linalg.norm(tangent(candidate_displacement), axis=1).max()),
                    tangent_disagreement_m_s=float(np.linalg.norm(tangent(native-displacement), axis=1).max()),
                    ground_minus_net_n=float(np.linalg.norm(aggregate-np.asarray(patch['net_force']))),
                    native_minus_displacement_m_s=float(np.linalg.norm(native-displacement, axis=1).max())))
                gaps.extend(points[:, 2].tolist())
        group_loads.append(load)
        previous = actors
    assert contacts, 'no actual contact observed'
    total = np.asarray([sum(row.values()) for row in group_loads])
    summary = {}
    for name, rows in contacts.items():
        late = [x for x in rows if x['step'] > max(0, len(r['samples'])-100)]
        summary[name] = dict(contact_frames=len(rows), max_points=max(x['count'] for x in rows),
            positive_force_frames=sum(x['positive_force'] for x in rows),
            max_normal_force_z_n=max(x['force_z_n'] for x in rows),
            late_mean_normal_force_z_n=float(np.mean([forces_row['contacts'][name]['ground_force'][2]
                for forces_row in r['samples'][-min(100, len(r['samples'])):]])),
            max_native_tangent_m_s=max(x['native_speed_m_s'] for x in rows),
            max_displacement_tangent_m_s=max(x['displacement_speed_m_s'] for x in rows),
            late_max_native_tangent_m_s=max((x['native_speed_m_s'] for x in late), default=None),
            late_max_displacement_tangent_m_s=max((x['displacement_speed_m_s'] for x in late), default=None),
            late_positive_force_max_native_tangent_m_s=max((x['loaded_native_speed_m_s']
                for x in late if x['positive_force']), default=None),
            late_positive_force_max_displacement_tangent_m_s=max((x['loaded_displacement_speed_m_s']
                for x in late if x['positive_force']), default=None),
            late_max_candidate_native_tangent_m_s=max((x['candidate_native_speed_m_s'] for x in late), default=None),
            late_max_candidate_displacement_tangent_m_s=max((x['candidate_displacement_speed_m_s'] for x in late), default=None),
            late_max_tangent_disagreement_m_s=max((x['tangent_disagreement_m_s'] for x in late), default=None),
            max_ground_minus_net_n=max(x['ground_minus_net_n'] for x in rows),
            max_velocity_disagreement_m_s=max(x['native_minus_displacement_m_s'] for x in rows),
            max_candidate_to_nearest_contact_m=max(x['candidate_distance_m'] for x in rows))
    return dict(status='native_contact_arrays_verified', physics_steps=len(r['samples']),
        controls=len(r['steps']), stop_reason=r.get('stop_reason'), contacts=summary,
        late_mean_load_n={k: float(np.mean([x[k] for x in group_loads[-100:]])) for k in ('feet', 'tail', 'other')},
        late_mean_support_over_weight=float(total[-100:].mean()/r['weight_n']),
        contact_height_range_m=[min(gaps), max(gaps)],
        scope='zero-action finite sample; patch maxima include zero-force solver points unless labelled '
              'positive_force; normal forces only; no rolling/sliding classification or policy verdict')


def audit(path):
    """Replay recorded bindings and real-array negative controls without Kit."""
    r = json.loads(path.read_text(encoding='utf-8'))
    assert r['completed'] and r['closed'], 'incomplete collection'
    assert sha256_file(path.parent/'source.py') == r['source_sha256']
    assert sha256_file(path.parent/'native_contact_api.py') == r['native_api_sha256']
    assert sha256_file(DRAFT) == r['manifest_sha256'] == DRAFT_SHA
    for source, digest in r['asset_sha256'].items():
        assert sha256_file(Path(source)) == digest
    for source, digest in r['mesh_sha256'].items():
        assert sha256_file(Path(source)) == digest
    checked = inspect_report(r)
    first = next((i, n) for i, s in enumerate(r['samples']) for n, p in s['contacts'].items() if p['count'])
    for damage in ('force', 'point_shape', 'mapping', 'velocity_target', 'gravity'):
        bad = copy.deepcopy(r)
        i, name = first
        if damage == 'force':
            bad['samples'][i]['contacts'][name]['forces'][0] += 1.
        elif damage == 'point_shape':
            bad['samples'][i]['contacts'][name]['points'].pop()
        elif damage == 'mapping':
            bad['views'][name]['filter_paths'] = ['/WrongFloor']
        elif damage == 'velocity_target':
            bad['samples'][i]['velocity_targets'][0][0] = .01
        else:
            bad['readbacks']['disable_gravity'][name] = True
        try:
            inspect_report(bad)
        except (AssertionError, ValueError):
            continue
        raise AssertionError('accepted damaged '+damage)
    return dict(checked, rejected_corruptions=5)


def cleanup_self_check():
    """Exercise the actual collector finally with stub close and write failures."""
    import ast
    from contextlib import nullcontext
    from tempfile import TemporaryDirectory
    from unittest.mock import patch

    tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))
    collector = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'collect')
    final = next(n for n in collector.body if isinstance(n, ast.Try)).finalbody
    wrapper = ast.parse('def cleanup(out, r, env, app, failed):\n pass').body[0]
    wrapper.body = final
    called = []

    class App:
        def close(self):
            called.append('close')
            raise SystemExit(0)

    namespace = dict(json=json, traceback=traceback, audit=lambda p: called.append('audit') or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
                 '<actual collector finally>', 'exec'), namespace)
    with TemporaryDirectory(prefix='contact_cleanup_', dir=REPO/'rl_exp/out') as directory:
        out = Path(directory)
        for case in ('normal', 'collection_failure', 'nan', 'write_failure'):
            called.clear()
            r = dict(completed=case == 'normal', closed=True, failure='fixture failure')
            if case == 'nan':
                r['value'] = float('nan')
            disk = patch.object(Path, 'write_text', side_effect=OSError('fixture disk failure')) \
                if case == 'write_failure' else nullcontext()
            try:
                with disk:
                    namespace['cleanup'](out, r, None, App(), case == 'collection_failure')
            except (ValueError, OSError, RuntimeError):
                assert case != 'normal'
            else:
                assert case == 'normal', 'failure escaped cleanup'
            assert called[-1:] == ['close'], 'app cleanup skipped on '+case
            assert ('audit' in called) == (case == 'normal')


def collect(args):
    """Observe native ground patches without changing the isolated draft physics."""
    assert sha256_file(DRAFT) == DRAFT_SHA
    out = args.out.resolve()
    assert out.is_relative_to(REPO/'rl_exp/out') and not out.exists()
    out.mkdir(parents=True)
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    r = dict(completed=False, closed=False, source_sha256=sha256_file(out/'source.py'),
        manifest_sha256=DRAFT_SHA, settings=dict(dt_s=.005, decimation=4, controls=100, capacity=CAPACITY),
        samples=[], steps=[], stop_reason=None)
    app = env = None
    started = time.monotonic()
    failed = False
    try:
        from isaaclab.app import AppLauncher
        app = AppLauncher(args).app
        import gymnasium as gym
        import torch
        import warp as wp
        from pxr import Usd, UsdPhysics
        from isaaclab_physx.physics import PhysxManager
        import rl_exp.tasks  # noqa: F401
        from rl_exp.tasks import obs_protocol
        from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg
        cfg = resolve_task_cfg(TASK)
        target = obs_protocol.load_diagnostic_target(DRAFT, cfg, TASK)
        cfg.scene.num_envs, cfg.sim.device, cfg.seed = 1, args.device, 0
        env = gym.make(TASK, cfg=cfg)
        live = env.unwrapped
        robot, sensor = live.scene['robot'], live.scene['contact_forces']
        obs_protocol.validate_diagnostic_runtime(target, cfg, robot, sensor, live.action_manager)
        assert not live._physics_handles_decimation and live.physics_dt == .005 and cfg.decimation == 4
        tensor = lambda a: a.detach().cpu().tolist()
        backend = lambda method: wp.to_torch(getattr(robot.root_view, method)()).clone()
        ps = live.sim.stage.GetPrimAtPath(cfg.sim.physics_prim_path)
        body_names = list(robot.body_names)
        bodies = {p.GetName(): p for p in live.sim.stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)
                  and p.GetName() in body_names}
        r.update(body_names=body_names, joint_names=list(robot.joint_names), feet=list(target['end_links'].values()),
            tails=[n for n in body_names if n.startswith('tail')], target=target,
            asset_sha256={target[k]: sha256_file(Path(target[k])) for k in ('target', 'urdf')},
            weight_n=float(robot.data.body_mass.torch.sum())*abs(cfg.sim.gravity[2]),
            readbacks=dict(fixed_base=robot.is_fixed_base,
                self_collisions=cfg.scene.robot.spawn.articulation_props.enabled_self_collisions,
                force_timing=ps.GetAttribute('physxScene:enableExternalForcesEveryIteration').Get(),
                solver=ps.GetAttribute('physxScene:solverType').Get(),
                disable_gravity={n: p.GetAttribute('physxRigidBody:disableGravity').Get() for n, p in bodies.items()},
                kp=tensor(backend('get_dof_stiffnesses'))[0], kd=tensor(backend('get_dof_dampings'))[0],
                effort_caps=tensor(backend('get_dof_max_forces'))[0], speed_caps=tensor(backend('get_dof_max_velocities'))[0]))
        prior_path = REPO/'rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json'
        assert sha256_file(prior_path) == '5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6'
        prior = json.loads(prior_path.read_text(encoding='utf-8'))
        assert r['joint_names'] == prior['joint_names']
        for key, old in (('kp', 'kp'), ('kd', 'kd'), ('effort_caps', 'effort_caps'), ('speed_caps', 'velocity_caps')):
            equal(r['readbacks'][key], prior['readbacks'][old], 'unchanged '+key, atol=0.)
        assert r['readbacks']['force_timing'] is False and r['readbacks']['solver'] == 'TGS'
        assert not robot.is_fixed_base and not any(r['readbacks']['disable_gravity'].values())
        floors = [p for p in Usd.PrimRange(live.sim.stage.GetPrimAtPath(cfg.scene.terrain.prim_path))
                  if p.HasAPI(UsdPhysics.CollisionAPI)]
        assert len(floors) == 1
        floor = r['floor'] = str(floors[0].GetPath())
        views, r['views'] = {}, {}
        for name, prim in bodies.items():
            if not any(p.HasAPI(UsdPhysics.CollisionAPI) for p in Usd.PrimRange(prim)):
                continue
            path = str(prim.GetPath())
            view = PhysxManager.get_physics_sim_view().create_rigid_contact_view(
                path, filter_patterns=[floor], max_contact_data_count=CAPACITY)
            pair_binding(view.sensor_paths, view.filter_paths, path, [floor], (view.sensor_count, view.filter_count, 3))
            views[name] = view
            r['views'][name] = dict(body=path, sensor_paths=list(view.sensor_paths), filter_paths=list(view.filter_paths))
        model = csc.load_urdf(Path(target['urdf']))
        r['vertices'] = {n: csc.read_obj(model['links'][n]['collision']).tolist() for n in views}
        r['mesh_sha256'] = {str(model['links'][n]['collision']): sha256_file(Path(model['links'][n]['collision']))
                           for n in views}
        r['initial_actor_pose'] = tensor(robot.data.body_link_pose_w.torch[0])
        api_source = Path(inspect.getfile(type(next(iter(views.values())))))
        (out/'native_contact_api.py').write_bytes(api_source.read_bytes())
        r['native_api_sha256'] = sha256_file(api_source)
        original_update = live.scene.update

        def update(*a, **kw):
            result = original_update(*a, **kw)
            assert len(r['samples']) < 400 and time.monotonic()-started < 600, 'budget exhausted'
            row = dict(step=len(r['samples'])+1, actor_pose=tensor(robot.data.body_link_pose_w.torch[0]),
                com_pose=tensor(robot.data.body_com_pose_w.torch[0]), com_velocity=tensor(robot.data.body_com_vel_w.torch[0]),
                raw_actions=tensor(live.action_manager.action),
                position_targets=tensor(backend('get_dof_position_targets')),
                velocity_targets=tensor(backend('get_dof_velocity_targets')), contacts={})
            net = wp.to_torch(sensor.contact_view.get_net_contact_forces(dt=.005)).clone().reshape(len(sensor.body_names), 3)
            row['net_forces'] = tensor(net[[sensor.body_names.index(n) for n in body_names]])
            for name, view in views.items():
                arrays = [wp.to_torch(v).clone().cpu().numpy() for v in view.get_contact_data(dt=.005)]
                row['contacts'][name] = dict(contact_patch(arrays),
                    ground_force=wp.to_torch(view.get_contact_force_matrix(dt=.005)).cpu().numpy().reshape(3).tolist(),
                    net_force=wp.to_torch(view.get_net_contact_forces(dt=.005)).cpu().numpy().reshape(3).tolist())
            r['samples'].append(row)
            return result

        live.scene.update = update
        zero = torch.zeros((1, 30), device=live.device)
        start_z = float(robot.data.root_link_pose_w.torch[0, 2])
        for control in range(100):
            _, _, terminated, truncated, _ = live.step(zero)
            r['steps'].append(dict(control=control+1, terminated=tensor(terminated), truncated=tensor(truncated)))
            actors = np.asarray(r['samples'][-1]['actor_pose'])
            root = actors[body_names.index('base_link')]
            q = robot.data.joint_pos.torch[0].cpu().numpy()
            safety = dict(root_drop=start_z-root[2] > .15,
                root_tilt=np.arccos(np.clip(_rotation(root[3:])[2, 2], -1, 1)) > .35,
                joint_motion=np.abs(q).max() > .35,
                forbidden_ground=max(np.linalg.norm(v['ground_force']) for n, v in r['samples'][-1]['contacts'].items()
                    if n not in set(r['feet']) | set(r['tails'])) > 5.,
                terminal=bool(terminated.any() or truncated.any()))
            if any(safety.values()):
                r['stop_reason'] = [k for k, v in safety.items() if v]
                break
        r['completed'] = True
    except BaseException:
        failed = True
        r['failure'] = traceback.format_exc()
        raise
    finally:
        try:
            if env is not None:
                try:
                    env.close()
                    r['closed'] = True
                except BaseException:
                    failed = True
                    r['close_failure'] = traceback.format_exc()
            (out/'report.json').write_text(json.dumps(r, indent=2, allow_nan=False), encoding='utf-8')
            if failed:
                raise RuntimeError(r.get('failure', r.get('close_failure')))
            checked = audit(out/'report.json')
            (out/'audit.json').write_text(json.dumps(checked, indent=2), encoding='utf-8')
            print(json.dumps(checked, indent=2), flush=True)
        finally:
            if app is not None:
                try:
                    app.close()
                except SystemExit:
                    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--self_check', action='store_true')
    if '--audit' not in sys.argv and '--self_check' not in sys.argv:
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if args.self_check:
        point = np.array([[0., 0., 0.]])
        com = np.array([0., 0., .1, 0., 0., 0., 1.])
        equal(material_velocity(point, com, [.1, 0., 0., 0., 1., 0.]), [[0., 0., 0.]], 'rolling')
        equal(material_velocity(point, com, [-.1, 0., 0., 0., 1., 0.]), [[-.2, 0., 0.]], 'sliding')
        before = np.array([0., 0., 0., 0., 0., 0., 1.])
        now = before.copy(); now[0] = .001
        equal(pose_velocity(point, before, now, .005), [[.2, 0., 0.]], 'translation')
        before = np.array([.3, -.2, .5, 0., 0., 0., 1.])
        now = np.array([.3, -.2, .5, 0., np.sin(np.pi/4), 0., np.cos(np.pi/4)])
        # Current endpoint [0.3,-0.2,0.4] belonged to [0.4,-0.2,0.5] before rotation.
        equal(pose_velocity([[.3, -.2, .4]], before, now, .5), [[-.2, 0., -.2]], 'same material')
        forces = np.arange(CAPACITY, dtype=float).reshape(-1, 1)
        points = np.repeat(forces, 3, axis=1)
        arrays = [forces, points, points, forces, np.array([[2]]), np.array([[7]])]
        patch = contact_patch(arrays)
        equal(patch['forces'], [7., 8.], 'nonzero buffer offset')
        equal(patch['points'], [[7.]*3, [8.]*3], 'point offset')
        for count, start in ((2, 255), (256, 0), (1, -1)):
            bad = arrays[:4] + [np.array([[count]]), np.array([[start]])]
            try:
                contact_patch(bad)
            except AssertionError:
                continue
            raise AssertionError('invalid contact buffer range accepted')
        empty = contact_patch(arrays[:4] + [np.array([[0]]), np.array([[-1]])])
        assert empty['forces'] == empty['points'] == []
        cleanup_self_check()
        print('CONTACT_SAMPLE_SELF_CHECK_OK')
    elif args.audit:
        print(json.dumps(audit(args.audit), indent=2))
    else:
        if not args.out:
            parser.error('--out required')
        collect(args)


if __name__ == '__main__':
    main()
