# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Check the live v7 round-foot joints, action targets, contacts and resets.

The v6 candidate probe is available at archive/pre-refactor.
"""

import argparse
import json
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tools.diagnose.lizard2_round_feet import FEET
from rl_exp.tools.runrecord.binding import sha256_file


def check_interface(expected, names, mapping, raw=None, processed=None, targets=None, backend=None):
    """Validate the complete 26-axis mapping and affine position commands [rad]."""
    if (len(expected) != 26 or len(set(expected)) != 26 or len(names) != 26
            or len(set(names)) != 26 or set(names) != set(expected)
            or len(mapping) != 26
            or {m['joint'] for m in mapping} != set(expected)
            or {m['global_index'] for m in mapping} != set(range(26))
            or {m['joint_index'] for m in mapping} != set(range(26))):
        raise ValueError('incomplete or duplicate 26-axis mapping')
    for m in mapping:
        if names[m['joint_index']] != m['joint'] or not math.isfinite(m['scale']) or m['scale'] == 0:
            raise ValueError('invalid joint route or scale')
    if raw is None:
        return
    if not all(len(v) == 26 for v in (raw, processed, targets)):
        raise ValueError('command vectors must contain every column')
    if backend is not None:
        if len(backend) != 26 or any(not math.isfinite(v) or abs(v - t) > 2e-6
                                     for v, t in zip(backend, targets)):
            raise ValueError('backend target mismatch')
    for m in mapping:
        i, j = m['global_index'], m['joint_index']
        value = raw[i] * m['scale'] + m['offset']
        if m['clip'] is not None:
            value = max(m['clip'][0], min(m['clip'][1], value))
        if not all(math.isfinite(v) and abs(v - value) <= 2e-6 for v in (processed[i], targets[j])):
            raise ValueError(f'command misrouting or affine mismatch: {m["joint"]}')


def interface_probe(env, candidate, result):
    """Send targets without stepping physics, then reset genuinely altered state."""
    import torch
    live = env.unwrapped
    robot, manager = live.scene['robot'], live.action_manager
    expected = [j.get('name') for j in ET.parse(candidate['urdf']).getroot().findall('joint')
                if j.get('type') == 'revolute']
    names = list(robot.joint_names)
    mapping = []
    for key in manager.active_terms:
        term = manager.get_term(key)
        if type(term).__name__ != 'JointPositionAction':
            raise ValueError(f'unsupported position term: {type(term).__name__}')
        ids = list(range(len(names)))[term._joint_ids] if isinstance(term._joint_ids, slice) else list(term._joint_ids)
        for local, (name, joint_id) in enumerate(zip(term._joint_names, ids)):
            def scalar(value):
                return float(value[0, local]) if torch.is_tensor(value) else float(value)
            mapping.append(dict(term=key, local_index=local, global_index=len(mapping),
                                joint=name, joint_index=int(joint_id), scale=scalar(term._scale),
                                offset=scalar(term._offset),
                                clip=term._clip[0, local].cpu().tolist() if term.cfg.clip is not None else None))
    result.update(expected_joint_names=expected, joint_names=names, mapping=mapping,
                  scope='commands and reset only; no motion, contacts, support or trained policy',
                  env_step_calls=0, reset_calls=0, forward_calls=0,
                  physics_steps_at_load=live.sim.get_physics_step_count(),
                  physics_count_channel='SimulationContext.get_physics_step_count; startup before load not bounded',
                  target_channel='robot.data.joint_pos_target (command buffer), scene.write_data_to_sim called',
                  cases=[])
    check_interface(expected, names, mapping)
    start = live.sim.get_physics_step_count()
    def vector(value):
        return value[0].detach().cpu().tolist()
    def snapshot():
        return dict(root_state_xyzw=vector(robot.data.root_state_w.torch),
                    joint_pos=vector(robot.data.joint_pos.torch), joint_vel=vector(robot.data.joint_vel.torch),
                    action=vector(manager.action), prev_action=vector(manager.prev_action),
                    targets=vector(robot.data.joint_pos_target.torch),
                    processed=[v for k in manager.active_terms for v in vector(manager.get_term(k).processed_actions)],
                    episode_length=live.episode_length_buf.cpu().tolist(),
                    command=vector(live.command_manager.get_command('base_velocity')))
    result['loaded'] = snapshot()
    action = torch.zeros((1, 26), device=live.device)
    view = getattr(robot, 'root_physx_view', None)
    getter = getattr(view, 'get_dof_position_targets', None)
    readback = result['physx_target_readback'] = {'available': callable(getter), 'checked_cases': 0}
    if callable(getter):
        backend_names = list(view.shared_metatype.dof_names)
        readback['joint_names'] = backend_names
        if backend_names != names:
            raise ValueError('backend DOF order differs from robot.joint_names')
    def backend_vector():
        try:
            value = getter()
            if not torch.is_tensor(value):
                import warp as wp
                value = wp.to_torch(value)
            return vector(value)
        except Exception as error:
            readback['error'] = repr(error)
            raise
    def send(label):
        manager.process_action(action)
        manager.apply_action()
        live.scene.write_data_to_sim()
        row = dict(label=label, raw=vector(action),
                   processed=[v for k in manager.active_terms for v in vector(manager.get_term(k).processed_actions)],
                   targets=vector(robot.data.joint_pos_target.torch))
        result['cases'].append(row)
        if callable(getter):
            row['backend_targets'] = backend_vector()
        check_interface(expected, names, mapping, row['raw'], row['processed'], row['targets'],
                        backend=row.get('backend_targets'))
        if callable(getter):
            row['backend_max_abs_error'] = max(abs(a - b) for a, b in zip(row['backend_targets'], row['targets']))
            readback['checked_cases'] += 1
        return row
    baseline = send('zero')
    result['zero_action_targets'] = baseline['targets']
    for m in mapping:
        for sign in (-1, 1):
            action.zero_()
            action[0, m['global_index']] = sign * .01 / m['scale']
            row = send(f'{m["joint"]}:{sign:+d}')
            desired = baseline['targets'].copy()
            desired[m['joint_index']] += sign * .01
            if any(abs(a - b) > 2e-6 for a, b in zip(row['targets'], desired)):
                raise ValueError('onehot changed another column or clipped requested excursion')
    result['before_perturbation'] = snapshot()
    root = robot.data.default_root_state.torch.clone()
    root[:, :3] += live.scene.env_origins
    root[:, :3] += torch.tensor([.02, .01, .05], device=live.device)
    root[:, 7:] = .03
    q = robot.data.default_joint_pos.torch.clone()
    delta = torch.tensor([.01 if i % 2 else -.01 for i in range(26)], device=live.device)
    limits = robot.data.joint_pos_limits.torch
    q = torch.clamp(q + delta, min=limits[:, :, 0] + 1e-5, max=limits[:, :, 1] - 1e-5)
    dq = torch.full_like(q, .02)
    result['perturbation_requested'] = dict(root_state_xyzw=vector(root), joint_pos=vector(q), joint_vel=vector(dq))
    robot.write_root_pose_to_sim_index(root_pose=root[:, :7])
    robot.write_root_velocity_to_sim_index(root_velocity=root[:, 7:])
    robot.write_joint_position_to_sim_index(position=q)
    robot.write_joint_velocity_to_sim_index(velocity=dq)
    # Two processing calls populate both manager history buffers without env.step.
    action.fill_(.1)
    manager.process_action(action)
    action.fill_(.2)
    manager.process_action(action)
    live.episode_length_buf[:] = 7
    live.sim.forward()
    result['forward_calls'] += 1
    result['altered'] = snapshot()
    def close(actual, wanted, label):
        if not torch.allclose(actual, wanted, atol=2e-5, rtol=0):
            raise ValueError(f'state readback mismatch: {label}')
    close(robot.data.root_state_w.torch, root, 'written root')
    close(robot.data.joint_pos.torch, q, 'written joints')
    close(robot.data.joint_vel.torch, dq, 'written joint velocity')
    if not bool(((q - robot.data.default_joint_pos.torch).abs() > 1e-4).all()):
        raise ValueError('joint perturbation not genuine in every column')
    if not bool((manager.action != 0).all() and (manager.prev_action != 0).all()):
        raise ValueError('action history not genuinely altered')
    result['reset_calls'] += 1
    env.reset()
    result['forward_calls'] += 1  # ManagerBasedEnv.reset invokes sim.forward (no physics step).
    result['after_reset'] = snapshot()
    default_root = robot.data.default_root_state.torch.clone()
    default_root[:, :3] += live.scene.env_origins
    result['reset_expected'] = dict(root_state_xyzw=vector(default_root),
                                   joint_pos=vector(robot.data.default_joint_pos.torch),
                                   joint_vel=vector(robot.data.default_joint_vel.torch))
    close(robot.data.root_state_w.torch, default_root, 'reset root incl xyzw and velocity')
    close(robot.data.joint_pos.torch, robot.data.default_joint_pos.torch, 'reset joints')
    close(robot.data.joint_vel.torch, robot.data.default_joint_vel.torch, 'reset joint velocity')
    close(manager.action, torch.zeros_like(manager.action), 'reset action')
    close(manager.prev_action, torch.zeros_like(manager.prev_action), 'reset previous action')
    if bool(live.episode_length_buf.any()):
        raise ValueError('episode length not reset')
    result['targets_after_reset'] = vector(robot.data.joint_pos_target.torch)
    result['reset_target_note'] = 'record only; reset need not clear processed actions or command targets; no rewrite'
    if callable(getter):
        result['backend_targets_after_reset'] = backend_vector()
    action.zero_()
    result['post_reset_zero'] = send('post_reset_zero')
    if any(abs(a - b) > 2e-6 for a, b in zip(result['post_reset_zero']['targets'], baseline['targets'])):
        raise ValueError('post-reset zero targets differ from full zero-action defaults')
    result['physics_steps_after_load'] = live.sim.get_physics_step_count() - start
    if result['physics_steps_after_load'] != 0:
        raise ValueError('physics advanced during commands/reset-only probe')
    result.update(status='completed', explicit_reset_checked=True)


def check_columns(actual, expected, label, *, require_nonzero=False):
    """Reject missing, nonfinite, swapped or falsely zero measurement columns."""
    if len(actual) != len(expected) or not actual:
        raise ValueError(f'column width mismatch: {label}')
    if any(not math.isfinite(a) or not math.isfinite(b) or abs(a-b) > 2e-5
           for a, b in zip(actual, expected)):
        raise ValueError(f'column value mismatch: {label}')
    if require_nonzero and not all(abs(v) > 1e-6 for v in expected):
        raise ValueError(f'nonzero stimulus missing: {label}')


def check_reset_rows(before, after, defaults, ids):
    """Check reset state/history and exact preservation of nonselected environments."""
    for key, rows in before.items():
        for i, previous in enumerate(rows):
            actual = after[key][i]
            if i not in ids:
                # IEEE bytes distinguish signed zero too; snapshots contain exact tensor values.
                unchanged = (struct.pack(f'{len(actual)}d', *actual) == struct.pack(f'{len(previous)}d', *previous)
                             if isinstance(actual, list) else actual == previous)
                if not unchanged:
                    raise ValueError(f'other environment changed: {key}:{i}')
                continue
            if key in defaults:
                check_columns(actual, defaults[key][i], f'reset {key}:{i}')
            elif key in ('action', 'prev_action'):
                check_columns(actual, [0.] * len(actual), f'reset {key}:{i}')
            elif key == 'episode_length' and actual != 0:
                raise ValueError('episode residue after reset')


def formal_probe(env, candidate, result):
    """Measure the v7 interface, nonzero observations and three control steps."""
    import torch
    import warp as wp
    from isaaclab.utils.math import quat_apply_inverse, quat_from_euler_xyz
    live = env.unwrapped
    robot, manager = live.scene['robot'], live.action_manager
    result['body_names'] = list(robot.body_names)
    if len(robot.body_names) != 31 or not all(n in robot.body_names for n in FEET):
        raise ValueError('formal body identity mismatch')
    # Existing no-physics probe also checks explicit reset of both environments.
    interface_probe(env, candidate, result)
    result.update(status='incomplete', scope='formal v7 interface and bounded first steps; not support or training')
    if not result['physx_target_readback']['available']:
        raise ValueError('PhysX target getter required')
    names, mapping = result['joint_names'], result['mapping']
    def tensor(value):
        return value if torch.is_tensor(value) else value.torch
    def rows(value):
        return tensor(value).detach().cpu().tolist()
    def backend():
        value = robot.root_physx_view.get_dof_position_targets()
        return rows(value if torch.is_tensor(value) else wp.to_torch(value))
    def snapshot():
        return dict(root=rows(robot.data.root_state_w), joint_pos=rows(robot.data.joint_pos),
                    joint_vel=rows(robot.data.joint_vel), action=rows(manager.action),
                    prev_action=rows(manager.prev_action), episode_length=rows(live.episode_length_buf),
                    command=rows(live.command_manager.get_command('base_velocity')),
                    processed=[sum((rows(manager.get_term(k).processed_actions)[i]
                                    for k in manager.active_terms), []) for i in range(2)],
                    targets=rows(robot.data.joint_pos_target), backend_targets=backend())
    root_default = robot.data.default_root_state.torch.clone()
    root_default[:, :3] += live.scene.env_origins
    defaults = dict(root=rows(root_default), joint_pos=rows(robot.data.default_joint_pos),
                    joint_vel=rows(robot.data.default_joint_vel))
    obs_manager = live.observation_manager
    result['observations'] = dict(group_order=list(obs_manager.active_terms), groups={})
    axis = torch.arange(1, 27, device=live.device).float()
    sign = torch.where(axis.remainder(2) == 0, -1., 1.)
    action = torch.stack((axis * sign, -axis.roll(7) * sign)) * .003
    root = root_default.clone()
    root[:, :3] += torch.tensor([[.02, -.03, .04], [-.01, .04, .06]], device=live.device)
    root[:, 3:7] = quat_from_euler_xyz(torch.tensor([.11, -.17], device=live.device),
                                     torch.tensor([-.13, .09], device=live.device),
                                     torch.tensor([.07, -.05], device=live.device))  # Installed fork: xyzw.
    root[:, 7:] = torch.tensor([[.13, -.24, .35, -.46, .57, -.68],
                               [-.31, .42, -.16, .27, -.63, .54]], device=live.device)
    q = robot.data.default_joint_pos.torch.clone()
    limits = robot.data.joint_pos_limits.torch
    delta = torch.stack((axis * sign, -axis.roll(11) * sign)) * .0005
    q = torch.clamp(q + delta, min=limits[:, :, 0]+1e-5, max=limits[:, :, 1]-1e-5)
    dq = torch.stack((-axis * sign, axis.roll(5) * sign)) * .007
    robot.write_root_pose_to_sim_index(root_pose=root[:, :7])
    robot.write_root_velocity_to_sim_index(root_velocity=root[:, 7:])
    robot.write_joint_position_to_sim_index(position=q)
    robot.write_joint_velocity_to_sim_index(velocity=dq)
    manager.process_action(action * -.5)
    manager.process_action(action)
    live.episode_length_buf[:] = torch.tensor([7, 8], device=live.device)
    command = live.command_manager.get_term('base_velocity').vel_command_b
    command[:] = torch.tensor([[.79, -.81, .92], [-.71, .62, -.53]], device=live.device)
    manager.apply_action()
    live.scene.write_data_to_sim()
    live.sim.forward()
    result['forward_calls'] += 1
    # Public data refresh advances cache timestamp, not physics. Writes do not
    # invalidate body-frame velocity caches in this fork; do not patch framework.
    robot.update(1e-6)
    result['nonphysics_cache_refresh_s'] = 1e-6
    result['nonzero_state'] = snapshot()
    result['nonzero_state'].update(commands=rows(command), joint_name_index=dict(zip(names, range(26))))
    for label, value, wanted in (('written root', robot.data.root_state_w, root),
                                 ('written q', robot.data.joint_pos, q),
                                 ('written dq', robot.data.joint_vel, dq)):
        for i in range(2):
            check_columns(rows(value)[i], rows(wanted)[i], label)
    # Independent frame references use actual world-state readback, not body-frame caches.
    actual_root = robot.data.root_state_w.torch.clone()
    expected_sources = dict(base_lin_vel=quat_apply_inverse(actual_root[:, 3:7], actual_root[:, 7:10]),
                            base_ang_vel=quat_apply_inverse(actual_root[:, 3:7], actual_root[:, 10:13]),
                            projected_gravity=quat_apply_inverse(actual_root[:, 3:7], robot.data.GRAVITY_VEC_W.torch),
                            velocity_commands=command, actions=manager.action)
    observation = obs_manager.compute()
    for group, terms in obs_manager.active_terms.items():
        group_cfg = getattr(live.cfg.observations, group)
        group_record = dict(term_order=list(terms), enable_corruption=group_cfg.enable_corruption,
                            shape=list(observation[group].shape), terms=[])
        result['observations']['groups'][group] = group_record
        if group_cfg.enable_corruption or not obs_manager.group_obs_concatenate[group]:
            raise ValueError('formal observation group must be uncorrupted and concatenated')
        column = 0
        # Fork-private term configs: read selection/scaling only; never modify published terms.
        for name, term_cfg, dims in zip(terms, obs_manager._group_obs_term_cfgs[group],
                                       obs_manager.group_obs_term_dim[group]):
            if term_cfg.history_length or term_cfg.modifiers:
                raise ValueError('unsupported observation history/modifier')
            ids = None
            if name in ('joint_pos', 'joint_vel'):
                entity = term_cfg.params.get('asset_cfg')
                ids = entity.joint_ids if entity is not None else slice(None)
                values = getattr(robot.data, name).torch
                default = getattr(robot.data, 'default_' + name).torch
                source = (values - default)[:, ids]
                selected = list(range(26))[ids] if isinstance(ids, slice) else list(ids)
                columns = [names[int(i)] for i in selected]
            else:
                if name not in expected_sources:
                    raise ValueError(f'unknown observation semantic: {name}')
                source = expected_sources[name]
                columns = ([m['joint'] for m in mapping] if name == 'actions' else
                           {'base_lin_vel': ['x', 'y', 'z'], 'base_ang_vel': ['x', 'y', 'z'],
                            'projected_gravity': ['x', 'y', 'z'],
                            'velocity_commands': ['lin_vel_x', 'lin_vel_y', 'ang_vel_z']}[name])
            actual_raw = term_cfg.func(live, **term_cfg.params)
            reference = source.clone()
            if term_cfg.clip:
                reference = reference.clamp(*term_cfg.clip)
            if term_cfg.scale is not None:
                reference = reference * term_cfg.scale
            width = reference.shape[1]
            term_record = dict(name=name, start=column, width=width, manager_dim=list(dims),
                               columns=columns, source=rows(source), raw=rows(actual_raw),
                               expected=rows(reference), actual=rows(observation[group][:, column:column+width]))
            group_record['terms'].append(term_record)
            rejected = []
            counterexamples = [('cross_env_broadcast', [term_record['expected'][0]] * 2),
                               ('column_broadcast', [[row[0]] * width for row in term_record['expected']])]
            if name == 'projected_gravity':
                wrong = robot.data.GRAVITY_VEC_W.torch.clone()
                if term_cfg.clip:
                    wrong = wrong.clamp(*term_cfg.clip)
                if term_cfg.scale is not None:
                    wrong = wrong * term_cfg.scale
                counterexamples.append(('unrotated_gravity', rows(wrong)))
            for label, wrong in counterexamples:
                try:
                    for i in range(2):
                        check_columns(wrong[i], term_record['expected'][i], label)
                except ValueError:
                    rejected.append(label)
                else:
                    raise ValueError(f'stimulus blind spot: {group}:{name}:{label}')
            term_record['counterexamples_rejected'] = rejected
            for i in range(2):
                nonzero = True
                check_columns(rows(actual_raw)[i], rows(source)[i], name, require_nonzero=nonzero)
                check_columns(term_record['actual'][i], term_record['expected'][i], group+':'+name,
                              require_nonzero=nonzero)
            if list(dims) != [width] or len(columns) != width:
                raise ValueError('observation term dimensions differ from measured columns')
            column += width
        if observation[group].shape != (2, column):
            raise ValueError('observation trailing columns or batch mismatch')
    before = snapshot()
    result['reset_calls'] += 1
    live.reset(env_ids=torch.tensor([0], dtype=torch.int32, device=live.device))
    result['forward_calls'] += 1
    after = snapshot()
    result['subset_reset'] = dict(before=before, after=after, expected=defaults,
                                  note='selected command/processed/targets may persist; nonselected byte-exact')
    check_reset_rows(before, after, defaults, [0])
    result['subset_reset']['passed'] = True
    physics_before_zero = live.sim.get_physics_step_count()
    manager.process_action(torch.zeros_like(action))
    manager.apply_action()
    live.scene.write_data_to_sim()
    zero = snapshot()
    for i in range(2):
        check_interface(result['expected_joint_names'], names, mapping, zero['action'][i], zero['processed'][i],
                        zero['targets'][i], backend=zero['backend_targets'][i])
    if live.sim.get_physics_step_count() != physics_before_zero:
        raise ValueError('subset zero-send advanced physics')
    result['subset_post_reset_zero'] = dict(after=zero, passed=True, physics_steps=0,
                                           note='all-column zero send/write only; NOT subset first physics step')
    manager.process_action(action * -.5)
    manager.process_action(action)
    manager.apply_action()
    live.scene.write_data_to_sim()
    before = snapshot()
    result['reset_calls'] += 1
    env.reset()
    result['forward_calls'] += 1
    after = snapshot()
    check_reset_rows(before, after, defaults, [0, 1])
    result['explicit_reset_nonzero'] = dict(before=before, after=after, expected=defaults, passed=True,
                                           processed=[rows(manager.get_term(k).processed_actions) for k in manager.active_terms],
                                           targets=rows(robot.data.joint_pos_target), backend_targets=backend(),
                                           note='processed and target persistence recorded; framework unchanged')
    if live.sim.get_physics_step_count() - result['physics_steps_at_load'] != 0:
        raise ValueError('physics advanced before bounded control steps')
    start = live.sim.get_physics_step_count()
    result['physics_control_start'] = start
    result['control_steps'] = []
    active_step = None
    original_write = live.scene.write_data_to_sim
    original_reset = live._reset_idx
    def capture_write(*args, **kwargs):
        value = original_write(*args, **kwargs)
        if active_step is not None:
            raw = rows(manager.action)
            processed = [sum((rows(manager.get_term(k).processed_actions)[i]
                              for k in manager.active_terms), []) for i in range(2)]
            targets, physical = rows(robot.data.joint_pos_target), backend()
            row = dict(raw=raw, processed=processed, targets=targets, backend_targets=physical,
                       physics_count=live.sim.get_physics_step_count())
            active_step['writes'].append(row)
            for i in range(2):
                check_interface(result['expected_joint_names'], names, mapping, raw[i], processed[i],
                                targets[i], backend=physical[i])
        return value
    def capture_reset(ids):
        before = snapshot()
        result['auto_reset_calls'] = result.get('auto_reset_calls', 0) + 1
        value = original_reset(ids)
        after = snapshot()
        reset_ids = ids.cpu().tolist()
        record = dict(ids=reset_ids, before=before, after=after)
        active_step.setdefault('auto_resets', []).append(record)
        check_reset_rows(before, after, defaults, reset_ids)
        record['passed'] = True
        return value
    live.scene.write_data_to_sim = capture_write
    live._reset_idx = capture_reset
    try:
        for label in ('first_after_explicit_reset', 'forced_timeout', 'first_after_auto_reset'):
            if label == 'forced_timeout':
                live.episode_length_buf[0] = live.max_episode_length - 1
                # Nonzero stale targets/history before timeout; next zero must overwrite all axes.
                manager.process_action(action * -.5)
                manager.process_action(action)
                manager.apply_action()
                original_write()
            active_step = dict(label=label, writes=[], before=snapshot())
            result['control_steps'].append(active_step)
            result['env_step_calls'] += 1
            obs, reward, terminated, truncated, _ = env.step(torch.zeros((2, 26), device=live.device))
            active_step['after'] = snapshot()
            active_step.update(terminated=rows(terminated), truncated=rows(truncated),
                               observation_shapes={k: list(v.shape) for k, v in obs.items()},
                               finite=all(bool(torch.isfinite(v).all()) for v in obs.values()) and
                               all(bool(torch.isfinite(torch.tensor(active_step['after'][k])).all())
                                   for k in ('root', 'joint_pos', 'joint_vel')))
            if not active_step['writes'] or not active_step['finite']:
                raise ValueError('missing first-step target evidence or nonfinite state')
            if label == 'forced_timeout':
                if rows(truncated) != [True, False] or rows(terminated) != [False, False]:
                    raise ValueError('forced timeout did not isolate environment zero')
                if [r['ids'] for r in active_step.get('auto_resets', [])] != [[0]]:
                    raise ValueError('unexpected auto reset selection')
            elif bool(terminated.any() or truncated.any()):
                raise ValueError('unexpected first-step termination')
            result['physics_steps_after_load'] = live.sim.get_physics_step_count() - start
    finally:
        live.scene.write_data_to_sim = original_write
        live._reset_idx = original_reset
    if result['env_step_calls'] != 3 or result['physics_steps_after_load'] != 3 * live.cfg.decimation:
        raise ValueError('physics/control budget mismatch')
    result.update(status='completed', auto_reset_checked=True, first_control_steps_checked=True)


def formal_main():
    """Run the bounded probe against the explicit v7 experiment."""
    import shutil
    import time
    from isaaclab.app import AppLauncher
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True, choices=('Lizard2-Flat-v7', 'Lizard2-Flat-Play-v7'),
                        help='select the explicit v7 Train or Play configuration')
    parser.add_argument('--out', type=Path, required=True, help='exclusive new run directory')
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if not args.out.parent.is_dir() or args.out.exists():
        parser.error('output parent must exist; run directory must not exist')
    args.out.mkdir(exist_ok=False)
    shutil.copy2(__file__, args.out / 'source.py')
    result = dict(status='incomplete', task=args.task, exit_code=1, env_step_calls=0)
    report = args.out / 'report.json'
    app = env = None
    started = time.monotonic()
    exit_code = 1
    try:
        launcher = AppLauncher(args)
        app = launcher.app
        from isaaclab.envs import ManagerBasedRLEnv
        from rl_exp.experiments.lizard2 import flat_v7

        cfg = flat_v7.make_env_cfg(play=args.task == 'Lizard2-Flat-Play-v7')
        cfg.sim.device = launcher.device
        body = flat_v7.ROBOT
        usd = Path(cfg.scene.robot.spawn.usd_path).resolve()
        urdf = body.URDF_PATH.resolve()
        bindings = result['bindings'] = {}
        for path in (usd, urdf, Path(__file__), Path(flat_v7.__file__), Path(body.__file__)):
            digest = sha256_file(path)
            if digest is None:
                raise ValueError(f'missing bound input: {path}')
            bindings[str(path)] = digest
        cfg.scene.num_envs = 2
        cfg.seed = 123
        result.update(num_envs=2, seed=123, cfg_changes=['scene.num_envs', 'seed'],
                      usd=str(usd), urdf=str(urdf), corruption=cfg.observations.policy.enable_corruption,
                      decimation=cfg.decimation, dt_s=cfg.sim.dt)
        env = ManagerBasedRLEnv(cfg=cfg)
        formal_probe(env, {'urdf': str(urdf)}, result)
        for path, digest in bindings.items():
            if sha256_file(Path(path)) != digest:
                raise ValueError(f'input changed during run: {path}')
        if time.monotonic() - started > 180:
            raise TimeoutError('run exceeded 180 seconds')
        exit_code = 0
    except BaseException as error:
        result.update(status='error', error=repr(error), traceback=traceback.format_exc())
        if env is not None:
            result['physics_steps_at_failure'] = env.unwrapped.sim.get_physics_step_count()
            if 'physics_control_start' in result:
                result['physics_steps_after_load'] = result['physics_steps_at_failure'] - result['physics_control_start']
        traceback.print_exc()
    finally:
        result.update(exit_code=exit_code, wall_seconds=time.monotonic()-started)
        report.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
        print('FORMAL_V7_RESULT', json.dumps(dict(status=result['status'], exit_code=exit_code,
                                               report=str(report), wall_seconds=result['wall_seconds'])), flush=True)
        try:
            if env is not None:
                env.close()
        finally:
            if app is not None:
                app.close(exit_code=exit_code)
            raise SystemExit(exit_code)


if __name__ == '__main__':
    if any(arg.split('=', 1)[0] == '--candidate' for arg in sys.argv[1:]):
        raise SystemExit('Run the v6 candidate probe from archive/pre-refactor.')
    formal_main()
