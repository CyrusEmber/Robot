# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Bounded live action/contact/reset inspection of the isolated training draft.

Two free-base environments, unchanged PD/gravity/TGS/false. Large actions are
processed without applying or stepping; dynamic targets stay within 0.015 rad.
At most 110 control steps (440 physics steps) after initialization. No termination
is replaced or suppressed. Natural contact termination is observed if it occurs
within 100 zero-action steps; absence is reported as uncovered, not passed.
--termination_fixture instead places env 0 upside down with every collision
vertex initially at least 5 mm above ground, then runs at most 30 zero steps.
It exercises the original contact termination, not a learned fall/recovery task.

Run with --headless --device cuda:0 --out <new directory under rl_exp/out>.
Replay without Kit using --audit <report.json>; --self_check tests the reader.
Reset-time processed/backend targets are recorded separately from the targets
actually applied before the next physics step. Units: rad, rad/s, m, s, N.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402

TASK = 'Lizard2-Flat-Play-v3'
DRAFT = REPO / 'rl_exp/out/lizard2_bc_handoff_20261023/training_interface_draft.json'
DRAFT_SHA = 'a120b8907601852e5ca7bf1190f675d75ea7a8ae0fa79e970d887628ed7e8b19'


def equal(actual, expected, label, atol=1.e-6):
    """Reject wrong shapes, nonfinite values and changed values [SI units]."""
    a, b = np.asarray(actual), np.asarray(expected)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError(label + ': shape/nonfinite')
    if not np.allclose(a, b, atol=atol, rtol=0):
        raise ValueError(label + ': value mismatch')


def inspect_report(r):
    """Recompute interface assertions from recorded raw arrays; no simulator."""
    assert r['completed'] and r['closed']
    names, actions = r['joint_names'], r['action_names']
    assert len(names) == len(actions) == len(set(actions)) == 30 and set(names) == set(actions)
    assert r['readbacks']['force_timing'] is False and r['readbacks']['solver_type'] == 'TGS'
    assert r['readbacks']['fixed_base'] is False and r['readbacks']['self_collisions'] is True
    assert r['readbacks']['body_disable_gravity'] and not any(r['readbacks']['body_disable_gravity'].values())
    assert [p.rsplit('/', 1)[-1] for p in r['native_sensor_paths']] == r['sensor_body_names'] * 2
    assert r['sampling'] == dict(dt_s=.005, decimation=4, period_s=.005, history_length=4, lazy=False)
    index = [names.index(n) for n in actions]
    for row in r['action_probes']:
        raw = np.asarray(row['raw'])
        expected = np.clip(raw * r['scale'] + r['offset'], r['clip_lower'], r['clip_upper'])
        equal(row['processed'], expected, 'affine/clip')
        assert row['physics_steps_added'] == 0
    assert len(r['action_probes']) == 4
    for row in r['physics']:
        expected = np.zeros((2, 30), dtype=np.float32)
        raw = np.asarray(row['raw'], dtype=np.float32)
        expected[:, index] = np.clip(raw * np.asarray(r['scale'], dtype=np.float32)
                                    + np.asarray(r['offset'], dtype=np.float32),
                                    r['clip_lower'], r['clip_upper'])
        assert np.max(np.abs(expected)) <= .015001, 'large target reached physics'
        equal(row['backend_position_target'], expected, 'applied position target')
        equal(row['backend_velocity_target'], np.zeros((2, 30)), 'zero velocity target')
        equal(row['cached_force'], row['native_force'], 'substep force', atol=1.e-4)
        equal(np.asarray(row['history'])[:, 0], row['native_force'], 'latest history', atol=1.e-4)
        equal(np.asarray(row['history'])[:, 1:], np.asarray(row['history_before'])[:, :-1],
              'history shift', atol=1.e-4)
        equal(row['timestamp'], row['timestamp_last_update'], 'fresh sensor timestamp')
        assert not any(row['outdated'])
    assert 4 <= len(r['physics']) <= 440 and len(r['physics']) == 4 * len(r['steps'])
    assert any(np.max(np.abs(p['native_force'])) > 1. for p in r['physics']), 'vacuous contact'
    # These are the unchanged registered draft's two illegal_contact predicates.
    bodies = r['sensor_body_names']
    for i, step in enumerate(r['steps']):
        history = np.asarray(r['physics'][4*i+3]['history'])
        base = np.linalg.norm(history[:, :, bodies.index('base_link')], axis=-1).max(axis=1) > 1.
        head = np.linalg.norm(history[:, :, [bodies.index('chest_pitch'), bodies.index('neck_pitch')]],
                              axis=-1).max(axis=(1, 2)) > 1.
        equal(step['terminated'], base | head, 'original contact termination')
        equal(step['truncated'], [False, False], 'no timeout in bounded window')
        assert all(p['phase'] == step['phase'] for p in r['physics'][4*i:4*i+4])
    for row in r['observations']:
        q, dq, raw = (np.asarray(row[k]) for k in ('q', 'dq', 'raw'))
        expected_raw = dict(base_lin_vel=np.asarray(row['base_lin_vel']),
                            base_ang_vel=np.asarray(row['base_ang_vel']),
                            projected_gravity=np.asarray(row['projected_gravity']),
                            velocity_commands=np.asarray(row['command']),
                            joint_pos=q-np.asarray(r['default_q']), joint_vel=dq-np.asarray(r['default_dq']),
                            actions=raw)
        parts = []
        for term in r['obs_terms']:
            value = expected_raw[term['name']]
            if term['clip'] is not None:
                value = np.clip(value, *term['clip'])
            if term['scale'] is not None:
                value = value * term['scale']
            parts.append(value)
        equal(row['policy'], np.concatenate(parts, axis=1), 'policy values')
        assert np.asarray(row['policy']).shape == (2, 102)
    assert any(np.max(np.abs(o['q'])) > 1.e-4 and np.max(np.abs(o['raw'])) > .001
               for o in r['observations']), 'vacuous nonzero observation'
    for row in r['resets']:
        ids = row['ids']
        for key, expected in (('q', r['default_q']), ('dq', r['default_dq']),
                              ('root', r['default_root'])):
            equal(np.asarray(row['after'][key])[ids], np.asarray(expected)[ids], 'reset '+key, atol=1.e-5)
        for key in ('raw', 'prev', 'history', 'episode'):
            a = np.asarray(row['after'][key])[ids]
            equal(a, np.zeros_like(a), 'reset '+key)
        if 'term_raw' in row['after']:
            equal(np.asarray(row['after']['term_raw'])[ids], np.zeros((len(ids), 30)), 'reset term raw')
        equal(row['after']['backend_q'], row['after']['q'], 'reset backend q')
        equal(row['after']['backend_dq'], row['after']['dq'], 'reset backend dq')
        rest = [i for i in range(2) if i not in ids]
        for key in ('q', 'dq', 'root', 'raw', 'prev', 'processed', 'backend_position_target',
                    'backend_velocity_target', 'history', 'episode'):
            equal(np.asarray(row['after'][key])[rest], np.asarray(row['before'][key])[rest],
                  'subset isolation '+key, atol=0.)
    assert any(row['phase'] == 'subset_dirty' and row['ids'] == [0] for row in r['resets'])
    dirty = [row for row in r['resets'] if row['phase'] in ('full_dirty', 'subset_dirty')]
    assert len(dirty) == 2 and all(np.max(np.abs(row['before']['q'])) > .001 for row in dirty)
    assert all(np.max(np.abs(row['before']['raw'])) > .001 for row in dirty)
    auto = [row for row in r['resets'] if row['phase'] in ('natural', 'contact_terminal_fixture')]
    natural = any(row['phase'] == 'natural' for row in auto)
    if r.get('termination_fixture'):
        assert auto and r['fixture']['min_collision_gap_m'] >= .0049
        done = [i for i, step in enumerate(r['steps']) if any(step['terminated'])]
        assert len(done) == 1 and r['steps'][done[0]]['terminated'] == [True, False]
        assert r['steps'][done[0]]['phase'] == 'contact_terminal_fixture'
        assert done[0]+1 < len(r['steps']) and r['steps'][done[0]+1]['phase'] == 'first_zero_auto', \
            'missing immediate first zero step after automatic reset'
        assert len(auto) == 1 and auto[0]['ids'] == [0]
        assert any(np.max(np.abs(row['before']['prev'])) > .001 for row in r['resets'])
    return dict(status='interface_arrays_verified', control_steps=len(r['steps']),
                physics_steps=len(r['physics']), reset_events=len(r['resets']),
                natural_reset_observed=natural, automatic_reset_observed=bool(auto),
                first_zero_after_automatic_reset=any(p['phase'] == 'first_zero_auto' for p in r['physics']),
                natural_reset_coverage='observed' if natural else 'not_observed',
                stale_targets_at_reset=any(np.max(np.abs(row['after']['processed'])) > 1.e-6
                                           for row in r['resets']),
                scope='isolated draft interface; no formal adoption, balance, tracking precision or training verdict')


def audit(path):
    """Replay exact source/manifest bindings and reject corrupted real samples."""
    r = json.loads(path.read_text(encoding='utf-8'))
    assert sha256_file(path.parent/'source.py') == r['source_sha256']
    assert sha256_file(Path(r['manifest'])) == r['manifest_sha256'] == DRAFT_SHA
    for field, digest in r['asset_sha256'].items():
        assert sha256_file(Path(r['target'][field])) == digest
    for name, source in r['runtime_sources'].items():
        assert sha256_file(path.parent/name) == source['sha256']
    result = inspect_report(r)
    corruptions = (
        lambda d: d['action_probes'][0]['processed'][0].reverse(),
        lambda d: d['physics'][0]['backend_velocity_target'][0].__setitem__(0, .01),
        lambda d: d['physics'][0]['history'][0][0][0].__setitem__(0, 12345.),
        lambda d: d['resets'][0]['after']['raw'][0].__setitem__(0, .01),
        lambda d: d['observations'][0]['policy'][0].__setitem__(12, 12345.),
        lambda d: d['steps'][0]['terminated'].__setitem__(0, not d['steps'][0]['terminated'][0]),
    )
    if r.get('termination_fixture'):
        corruptions += (lambda d: next(s for s in d['steps'] if s['phase'] == 'first_zero_auto')
                        .__setitem__('phase', 'first_zero_full'),)
    for corrupt in corruptions:
        broken = copy.deepcopy(r)
        corrupt(broken)
        try:
            inspect_report(broken)
        except (AssertionError, ValueError):
            continue
        raise AssertionError('reader accepted corrupted sample')
    return dict(result, rejected_corruptions=len(corruptions))


def collect(args):
    """Collect unchanged candidate manager/backend values within the fixed budget."""
    assert sha256_file(DRAFT) == DRAFT_SHA
    out = args.out.resolve()
    assert REPO/'rl_exp/out' in out.parents and not out.exists()
    out.mkdir(parents=True)
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    r = dict(completed=False, closed=False, manifest=str(DRAFT), manifest_sha256=DRAFT_SHA,
             source_sha256=sha256_file(out/'source.py'), action_probes=[], physics=[], steps=[],
             observations=[], resets=[], phase='startup', termination_fixture=args.termination_fixture)
    app = env = None
    started = time.monotonic()
    try:
        from isaaclab.app import AppLauncher
        app = AppLauncher(args).app
        import gymnasium as gym
        import inspect
        import torch
        import warp as wp
        from pxr import UsdPhysics
        import rl_exp.tasks  # noqa: F401
        from rl_exp.tasks import obs_protocol
        from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg
        cfg = resolve_task_cfg(TASK)
        target = obs_protocol.load_diagnostic_target(DRAFT, cfg, TASK)
        cfg.scene.num_envs, cfg.sim.device, cfg.seed = 2, args.device, 0
        env = gym.make(TASK, cfg=cfg)
        live = env.unwrapped
        robot, sensor, manager = live.scene['robot'], live.scene['contact_forces'], live.action_manager
        obs_protocol.validate_diagnostic_runtime(target, cfg, robot, sensor, manager)
        assert not live._physics_handles_decimation
        tensor = lambda x: x.detach().cpu().tolist()
        backend = lambda method: wp.to_torch(getattr(robot.root_view, method)()).clone()
        names = list(robot.joint_names)
        action_names, scales, offsets, lower, upper = [], [], [], [], []
        for key in manager.active_terms:
            term = manager.get_term(key)
            action_names.extend(term._joint_names)
            scales.extend(tensor(torch.broadcast_to(torch.as_tensor(term._scale, device=live.device),
                                                    term.raw_actions.shape))[0])
            offsets.extend(tensor(torch.broadcast_to(torch.as_tensor(term._offset, device=live.device),
                                                     term.raw_actions.shape))[0])
            lower.extend(tensor(term._clip[0, :, 0]))
            upper.extend(tensor(term._clip[0, :, 1]))
        physics_scene = live.sim.stage.GetPrimAtPath(cfg.sim.physics_prim_path)
        r.update(target=target, asset_sha256={k: sha256_file(Path(target[k])) for k in ('target', 'urdf')},
                 joint_names=names, action_names=action_names, sensor_body_names=list(sensor.body_names),
                 native_sensor_paths=list(sensor.contact_view.sensor_paths), scale=scales, offset=offsets,
                 clip_lower=lower, clip_upper=upper,
                 sampling=dict(dt_s=live.physics_dt, decimation=cfg.decimation, period_s=sensor.cfg.update_period,
                               history_length=sensor.cfg.history_length, lazy=cfg.scene.lazy_sensor_update),
                 readbacks=dict(fixed_base=robot.is_fixed_base,
                     self_collisions=cfg.scene.robot.spawn.articulation_props.enabled_self_collisions,
                     force_timing=physics_scene.GetAttribute('physxScene:enableExternalForcesEveryIteration').Get(),
                     solver_type=physics_scene.GetAttribute('physxScene:solverType').Get(),
                     kp=tensor(backend('get_dof_stiffnesses')), kd=tensor(backend('get_dof_dampings')),
                     effort_caps=tensor(backend('get_dof_max_forces')),
                     speed_caps=tensor(backend('get_dof_max_velocities')),
                     body_disable_gravity={str(p.GetPath()): p.GetAttribute('physxRigidBody:disableGravity').Get()
                         for p in live.sim.stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)}))
        reference = REPO/'rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json'
        assert sha256_file(reference) == '5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6'
        prior = json.loads(reference.read_text(encoding='utf-8'))
        assert names == prior['joint_names'] and manager.total_action_dim == 30
        for key, old in (('kp', 'kp'), ('kd', 'kd'), ('effort_caps', 'effort_caps'), ('speed_caps', 'velocity_caps')):
            equal(r['readbacks'][key], [prior['readbacks'][old]] * 2, 'unchanged '+key, atol=0.)
        assert r['readbacks']['force_timing'] is False and r['readbacks']['solver_type'] == 'TGS'
        assert not robot.is_fixed_base and not any(r['readbacks']['body_disable_gravity'].values())
        r['runtime_sources'] = {}
        for obj in (type(live), type(sensor), type(manager.get_term(manager.active_terms[0])), type(robot)):
            source = Path(inspect.getfile(obj))
            name = obj.__name__ + '.py'
            (out/name).write_bytes(source.read_bytes())
            r['runtime_sources'][name] = dict(original=str(source), sha256=sha256_file(source))
        r['default_q'], r['default_dq'] = tensor(robot.data.default_joint_pos.torch), tensor(robot.data.default_joint_vel.torch)
        default_root = torch.cat((robot.data.default_root_pose.torch, robot.data.default_root_vel.torch), dim=1).clone()
        default_root[:, :3] += live.scene.env_origins
        r['default_root'] = tensor(default_root)
        r['obs_terms'] = []
        om = live.observation_manager
        for name, term in zip(om.active_terms['policy'], om._group_obs_term_cfgs['policy']):
            assert not term.history_length and not term.modifiers and term.noise is None
            scale = tensor(term.scale) if isinstance(term.scale, torch.Tensor) else term.scale
            r['obs_terms'].append(dict(name=name, scale=scale, clip=term.clip))

        def processed():
            return torch.cat([manager.get_term(k).processed_actions for k in manager.active_terms], dim=1)

        def snapshot():
            return dict(q=tensor(robot.data.joint_pos.torch), dq=tensor(robot.data.joint_vel.torch),
                        root=tensor(torch.cat((robot.data.root_link_pose_w.torch, robot.data.root_com_vel_w.torch), dim=1)),
                        backend_q=tensor(backend('get_dof_positions')), backend_dq=tensor(backend('get_dof_velocities')),
                        raw=tensor(manager.action), prev=tensor(manager.prev_action), processed=tensor(processed()),
                        term_raw=tensor(torch.cat([manager.get_term(k).raw_actions for k in manager.active_terms], dim=1)),
                        backend_position_target=tensor(backend('get_dof_position_targets')),
                        backend_velocity_target=tensor(backend('get_dof_velocity_targets')),
                        history=tensor(sensor._data.net_forces_w_history.torch), episode=tensor(live.episode_length_buf))

        original_reset, original_physics, original_update = live._reset_idx, live.sim.step, live.scene.update

        def reset(ids):
            row = dict(phase=r['phase'], ids=torch.as_tensor(ids).cpu().tolist(), before=snapshot())
            if r['phase'] in ('natural', 'contact_terminal_fixture'):
                row['terminal_policy'] = tensor(live.observation_manager.compute_group('policy'))
            original_reset(ids)
            row['after'] = snapshot()
            r['resets'].append(row)

        def physics(*a, **kw):
            assert len(r['physics']) < 440 and time.monotonic()-started < 600, 'budget exhausted'
            row = dict(phase=r['phase'], raw=tensor(manager.action),
                       backend_position_target=tensor(backend('get_dof_position_targets')),
                       backend_velocity_target=tensor(backend('get_dof_velocity_targets')),
                       history_before=tensor(sensor._data.net_forces_w_history.torch))
            result = original_physics(*a, **kw)
            forces = wp.to_torch(sensor.contact_view.get_net_contact_forces(dt=live.physics_dt)).clone()
            row['native_force'] = tensor(forces.reshape(2, len(sensor.body_names), 3))
            r['physics'].append(row)
            return result

        def update(*a, **kw):
            result = original_update(*a, **kw)
            row = r['physics'][-1]
            # Read internal buffers only: this observer must not repair lazy sampling.
            row.update(cached_force=tensor(sensor._data.net_forces_w.torch),
                       history=tensor(sensor._data.net_forces_w_history.torch),
                       timestamp=tensor(wp.to_torch(sensor._timestamp)),
                       timestamp_last_update=tensor(wp.to_torch(sensor._timestamp_last_update)),
                       outdated=tensor(wp.to_torch(sensor._is_outdated)))
            return result

        live._reset_idx, live.sim.step, live.scene.update = reset, physics, update
        zero = torch.zeros((2, 30), device=live.device)

        def step(action):
            assert len(r['steps']) < 110
            obs, _, terminated, truncated, _ = env.step(action)
            r['steps'].append(dict(phase=r['phase'], terminated=tensor(terminated), truncated=tensor(truncated)))
            r['observations'].append(dict(q=tensor(robot.data.joint_pos.torch), dq=tensor(robot.data.joint_vel.torch),
                raw=tensor(manager.action), base_lin_vel=tensor(robot.data.root_com_lin_vel_b.torch),
                base_ang_vel=tensor(robot.data.root_com_ang_vel_b.torch),
                projected_gravity=tensor(robot.data.projected_gravity_b.torch),
                command=tensor(live.command_manager.get_command('base_velocity')), policy=tensor(obs['policy'])))
            assert torch.isfinite(robot.data.joint_pos.torch).all() and torch.isfinite(obs['policy']).all()
            return bool((terminated | truncated).any())

        r['phase'] = 'initial'
        env.reset()
        # Only process these signatures; never apply large or clipped references.
        for factor in (1., -1., 100., -100.):
            raw = torch.arange(1, 31, device=live.device).repeat(2, 1) * (.003*factor)
            raw[1] *= -1
            before = len(r['physics'])
            manager.process_action(raw)
            r['action_probes'].append(dict(raw=tensor(raw), processed=tensor(processed()),
                                           physics_steps_added=len(r['physics'])-before))
        manager.process_action(zero)
        # Small, distinguishable targets in action order, bounded to 0.015 rad.
        small = torch.arange(1, 31, device=live.device).repeat(2, 1) * .0005
        small[1] *= -1
        small /= torch.tensor(scales, device=live.device)
        r['phase'] = 'small_action'
        step(small)
        step(-small)
        if args.termination_fixture:
            from isaaclab.utils.math import quat_apply
            from rl_exp.tools.verify import check_self_collision as collision
            r['phase'] = 'fixture_prepare_reset'
            env.reset()
            model = collision.load_urdf(Path(target['urdf']))
            points = []
            for name, spec in model['links'].items():
                if not spec.get('collision'):
                    continue
                pose = robot.data.body_link_pose_w.torch[0, robot.body_names.index(name)]
                vertices = torch.tensor(collision.read_obj(spec['collision']), device=live.device, dtype=torch.float32)
                world = quat_apply(pose[3:].expand(len(vertices), 4), vertices) + pose[:3]
                points.append(world - default_root[0, :3])
            vertices = torch.cat(points)
            rotation = torch.tensor([1., 0., 0., 0.], device=live.device)
            inverted = quat_apply(rotation.expand(len(vertices), 4), vertices)
            fixture = default_root.clone()
            fixture[0, 2] = -inverted[:, 2].min() + .005
            fixture[0, 3:7] = rotation
            robot.write_root_link_pose_to_sim_index(root_pose=fixture[:, :7])
            robot.write_root_com_velocity_to_sim_index(root_velocity=fixture[:, 7:])
            live.sim.forward()
            r['fixture'] = dict(scope='inverted clearance fixture; original contact termination unchanged',
                                root=tensor(fixture), min_collision_gap_m=float((inverted[:, 2]+fixture[0, 2]).min()))
            r['phase'] = 'contact_terminal_fixture'
        else:
            r['phase'] = 'natural'
        for _ in range(30 if args.termination_fixture else 100):
            if step(zero):
                break
        if args.termination_fixture:
            assert any(row['phase'] == 'contact_terminal_fixture' for row in r['resets']), 'contact fixture did not terminate'
            r['phase'] = 'first_zero_auto'
            step(zero)
        # Dirty all resettable state, keeping contact history from real steps.
        def dirty_state():
            q = torch.arange(1, 31, device=live.device).repeat(2, 1) * .0005
            dq = q * -2
            robot.write_joint_state_to_sim(q, dq)
            root = default_root.clone()
            root[:, :3] += .01
            root[:, 7:] = .01
            robot.write_root_link_pose_to_sim_index(root_pose=root[:, :7])
            robot.write_root_com_velocity_to_sim_index(root_velocity=root[:, 7:])
            manager.process_action(small)
            manager.apply_action()
            live.scene.write_data_to_sim()
            live.sim.forward()

        dirty_state()
        r['phase'] = 'full_dirty'
        env.reset()
        r['phase'] = 'first_zero_full'
        step(zero)
        dirty_state()
        r['phase'] = 'subset_dirty'
        live.reset(env_ids=torch.tensor([0], dtype=torch.int32, device=live.device))
        r['phase'] = 'first_zero_subset'
        step(zero)
        r['completed'] = True
        live._reset_idx, live.sim.step, live.scene.update = original_reset, original_physics, original_update
    except Exception as exc:
        r.update(error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        if env is not None:
            env.close()
            r['closed'] = True
        (out/'report.json').write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
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
    parser.add_argument('--termination_fixture', action='store_true')
    if '--audit' not in sys.argv and '--self_check' not in sys.argv:
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if args.self_check:
        for a, b in (([float('nan')], [0]), ([1, 2], [2, 1]), ([1], [[1]])):
            try:
                equal(a, b, 'negative control')
            except ValueError:
                continue
            raise AssertionError('invalid array accepted')
        print('INTERFACE_READER_SELF_CHECK_OK')
    elif args.audit:
        print(json.dumps(audit(args.audit), indent=2))
    else:
        if not args.out:
            parser.error('--out required')
        collect(args)


if __name__ == '__main__':
    main()
