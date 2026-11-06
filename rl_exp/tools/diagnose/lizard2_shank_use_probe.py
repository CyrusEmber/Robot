# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Roll a v7 checkpoint and report per-role leg-joint use and stance-phase shank tilt.

Shank tilt = angle between the elbow/knee->foot world axis and -Z, taken while the foot centre
is below ``STANCE_Z`` (stance proxy, not a contact measurement). Optional pose samples retain
full joint/link state and both sides of loaded USD joint frames, using xyzw link quaternions.
"""

import argparse
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument('--checkpoint', required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--speed', type=float, default=0.5)
parser.add_argument('--seed', type=int, default=123)
parser.add_argument('--steps', type=int, default=500)
parser.add_argument('--landing_samples', action='store_true', help='filtered floor forces and link/joint state at each physics substep')
parser.add_argument('--propulsion_samples', action='store_true',
                    help='capture floor normal, friction, contact points and state at each physics substep')
parser.add_argument('--policy_drive_case', choices=('swing_kp2', 'twist_kp2', 'swing_kd_half'),
                    help='probe-only gains before policy rollout; no frozen recipe changes')
parser.add_argument('--contact_samples', action='store_true', help='save first-episode control-frame force and shank samples')
parser.add_argument('--drive_probe', choices=('suspended', 'ground'), help='replace policy with bounded actuator calibration')
parser.add_argument('--leg_drive_preflight', action='store_true',
                    help='prepare swing-only baseline/candidate readbacks without stepping physics')
parser.add_argument('--leg_drive_calibration', action='store_true',
                    help='run approved fixed-root paired leg PD comparison')
parser.add_argument('--pose_samples', action='store_true', help='save env 0 poses and USD world axes every 0.5 s')
parser.add_argument('--swing-clip', type=float, default=None,
                    help='probe-only: replace every *_swing_joint action clip with (-v, v); URDF limit still applies')
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.propulsion_samples and not args.landing_samples:
    parser.error('--propulsion_samples requires --landing_samples')
if args.propulsion_samples and (not args.out.parent.is_dir()
                               or args.out.with_name(args.out.stem + '_landing_samples.npz').exists()):
    parser.error('propulsion output directory must exist and sample path must be fresh')
if args.out.exists() or ((args.drive_probe or args.leg_drive_preflight) and args.out.parent.exists()):
    parser.error('output already exists')
if args.leg_drive_preflight and not args.out.parent.parent.is_dir():
    parser.error('leg drive output parent must have an existing parent')
if args.leg_drive_calibration and not args.out.parent.is_dir():
    parser.error('calibration output directory must already exist')
if ((args.leg_drive_preflight and args.leg_drive_calibration)
        or (args.leg_drive_preflight or args.leg_drive_calibration)
        and (args.drive_probe or args.policy_drive_case or args.landing_samples
             or args.contact_samples or args.pose_samples or args.swing_clip is not None)):
    parser.error('leg drive diagnostics cannot be combined with probe interventions')
app = AppLauncher(args).app

STANCE_Z = 0.10
LEGS = {'lf': 'elbow', 'rf': 'elbow', 'rl': 'knee', 'rr': 'knee'}
FOOT = {'lf': 'wrist', 'rf': 'wrist', 'rl': 'ankle', 'rr': 'ankle'}

def landing_events(force_z, valid, dt, flight_s=0.02, contact_s=0.01):
    """Filtered vertical-force onsets after flight and confirmed contact [N, s]; diagnostic windows."""
    import numpy as np

    loaded = force_z > 1.
    events = []
    for env in range(loaded.shape[1]):
        for leg in range(loaded.shape[2]):
            flight = max(1, math.ceil(flight_s / dt - 1e-9))
            contact = max(1, math.ceil(contact_s / dt - 1e-9))
            edges = np.flatnonzero(loaded[1:, env, leg] & ~loaded[:-1, env, leg]) + 1
            for index in edges:
                if index < flight or index + contact > len(loaded):
                    continue
                if (valid[index-flight:index+contact, env].all()
                        and not loaded[index-flight:index, env, leg].any()
                        and loaded[index:index+contact, env, leg].all()):
                    events.append({'sample': int(index), 'env': env, 'leg_index': leg})
    return events


def contact_edges(loaded, valid):
    """Control-frame force edges in contiguous valid first-episode samples; not touchdown authority."""
    import numpy as np

    edges = np.zeros_like(loaded, dtype=bool)
    edges[1:] = loaded[1:] & ~loaded[:-1] & valid[1:, :, None] & valid[:-1, :, None]
    return edges


def sine_response(time, position, target, frequency):
    """Fit sine amplitude ratio and signed lag [deg], discarding the first cycle."""
    import numpy as np

    valid = time >= 1. / frequency
    basis = np.column_stack((np.ones(valid.sum()), np.sin(2*math.pi*frequency*time[valid]),
                             np.cos(2*math.pi*frequency*time[valid])))
    a = np.linalg.lstsq(basis, position[valid], rcond=None)[0]
    b = np.linalg.lstsq(basis, target[valid], rcond=None)[0]
    target_amp = float(np.hypot(b[1], b[2]))
    assert target_amp > 1e-6, 'no sine excitation'
    error = position[valid] - target[valid]
    return {'actual_amplitude_rad': float(np.hypot(a[1], a[2])), 'target_amplitude_rad': target_amp,
            'amplitude_ratio': float(np.hypot(a[1], a[2]) / target_amp),
            'phase_lag_deg': float(np.degrees(np.angle(np.exp(1j*(np.arctan2(b[2], b[1])-np.arctan2(a[2], a[1])))))),
            'mean_abs_track_error_rad': float(np.abs(error).mean()),
            'fit_rms_residual_rad': float(np.sqrt(np.mean((position[valid] - basis @ a)**2))),
            'mean_position_rad': float(position[valid].mean())}


def leg_drive_candidate(names, stiffness, damping, inertia):
    """Make paired v7 and twice-stiffness swing gains [N*m/rad, N*m*s/rad]."""
    import numpy as np
    from rl_exp.tools.diagnose.lizard2_leg_drive_protocol import candidate_gains

    kp, kd = np.asarray(stiffness, dtype=float).copy(), np.asarray(damping, dtype=float).copy()
    if (kp.shape != (2, 26) or kd.shape != (2, 26)
            or not np.array_equal(kp[0], kp[1]) or not np.array_equal(kd[0], kd[1])):
        raise ValueError('invalid paired baseline gains')
    candidate_gains(names, kp[1], kd[1], inertia)
    swing = [i for i, name in enumerate(names) if name.endswith('_swing_joint')]
    kp[1, swing] *= 2
    kd[1, swing] *= math.sqrt(2)
    return kp, kd


def leg_drive_preflight(live, out, checkpoint):
    """Read paired swing-only candidate and backend settings; do not step physics."""
    import numpy as np
    import torch
    import warp as wp
    from rl_exp.tools.diagnose import lizard2_leg_drive_baseline as baseline
    from rl_exp.tools.runrecord.binding import sha256_file

    cfg, _, expected_names, _, bodies = baseline.inputs()
    robot = live.scene['robot']
    names = list(robot.joint_names)
    if names != expected_names or list(robot.root_view.shared_metatype.dof_names) != names:
        raise ValueError('runtime joint order differs from measured v7 order')
    if len(robot.body_names) != 31 or set(robot.body_names) != set(bodies) or not robot.is_fixed_base:
        raise ValueError('v7 body coverage or fixed base mismatch')
    if live.num_envs != 2 or not math.isclose(live.physics_dt, .005, rel_tol=0, abs_tol=1e-9) or live.cfg.decimation != 4:
        raise ValueError('unexpected environment count or timing')

    def values(getter):
        value = getter()
        return (value if torch.is_tensor(value) else wp.to_torch(value)).detach().cpu().numpy().copy()

    before = live.sim.get_physics_step_count()
    initial_kp = values(robot.root_view.get_dof_stiffnesses)
    initial_kd = values(robot.root_view.get_dof_dampings)
    baseline_report = baseline.report()
    nominal_inertia = dict(zip(baseline_report['all_joint_names'], baseline_report['all_inertia_diagonal_kg_m2']))
    kp, kd = leg_drive_candidate(names, initial_kp, initial_kd, [nominal_inertia[name] for name in names])
    limits = values(robot.root_view.get_dof_limits)
    caps = {'effort_nm': values(robot.root_view.get_dof_max_forces),
            'velocity_rad_s': values(robot.root_view.get_dof_max_velocities)}
    if limits.shape != (2, 26, 2) or any(v.shape != (2, 26) for v in caps.values()):
        raise ValueError('backend limit shape mismatch')
    if not np.isfinite(limits).all() or any(not np.isfinite(v).all() or (v <= 0).any() for v in caps.values()):
        raise ValueError('backend limit readback unavailable or invalid')
    if np.any(limits[..., 0] >= limits[..., 1]):
        raise ValueError('invalid backend position limits')
    for field, readback in (('stiffness', initial_kp), ('damping', initial_kd),
                            ('effort_limit', caps['effort_nm']), ('velocity_limit', caps['velocity_rad_s'])):
        groups = cfg['actuators'].values()
        expected = np.array([next(g[field][name] for g in groups if name in g[field]) for name in names])
        if not np.allclose(readback, expected[None, :], rtol=1e-5, atol=1e-6):
            raise ValueError('backend differs from v7 configuration: ' + field)
    source_hash = sha256_file(baseline.RL / baseline.USD_KEY)
    if not source_hash or sha256_file(Path(live.cfg.scene.robot.spawn.usd_path)) != source_hash:
        raise ValueError('formal USD mismatch')
    metadata = dict(scope='candidate-preparation preflight; no physics step, no support or torque verdict',
                    candidate_status='prepared; physical run not approved',
                    candidate_formula='swing only: Kp=2*v7, Kd=sqrt(2)*v7; other joints remain v7',
                    candidate_scope='suspended hypothesis only; two-foot support load not included',
                    task='Lizard2-Flat-Play-v7', checkpoint_identity_only=checkpoint, joint_names=names,
                    body_names=list(robot.body_names), fixed_base=True, physics_dt_s=live.physics_dt,
                    control_dt_s=live.physics_dt * live.cfg.decimation,
                    checkpoint_loaded=False, contact_readback='not collected',
                    initial_stiffness=initial_kp.tolist(), initial_damping=initial_kd.tolist(),
                    nominal_inertia_kg_m2=[nominal_inertia[name] for name in names],
                    inertia_inputs=baseline_report['inputs'],
                    proposed_stiffness=kp.tolist(), proposed_damping=kd.tolist(),
                    effort_limit_nm=caps['effort_nm'].tolist(), velocity_limit_rad_s=caps['velocity_rad_s'].tolist(),
                    position_limits_rad=limits.tolist(), config_default_joint_pos=cfg['default_joint_pos'],
                    code_sha256=sha256_file(Path(__file__)), physics_steps_at_start=before,
                    step_count_scope='sim.step calls after environment construction; startup and callbacks not bounded',
                    physics_steps_at_end=live.sim.get_physics_step_count())
    if metadata['physics_steps_at_end'] != before:
        raise RuntimeError('preflight unexpectedly stepped physics')
    if out is not None:
        out.parent.mkdir(exist_ok=False)
        with out.open('x', encoding='utf-8') as stream:
            json.dump(metadata, stream, indent=2, allow_nan=False)
        print('LEG_DRIVE_PREFLIGHT_OK', out, flush=True)
    return metadata


def leg_drive_contact_views(live, robot, collision_names):
    """Bind each active body to its exact ground contact view in both environments."""
    from pxr import Usd, UsdPhysics
    from isaaclab_physx.physics import PhysxManager
    from rl_exp.tools.diagnose.palm_spatial_runtime import pair_binding

    if live.num_envs != 2:
        raise ValueError('two environments required')
    stage = live.sim.stage
    ground = stage.GetPrimAtPath(live.cfg.scene.terrain.prim_path)
    if not ground.IsValid():
        raise ValueError('invalid terrain prim')
    floors = [prim for prim in Usd.PrimRange(ground) if prim.HasAPI(UsdPhysics.CollisionAPI)]
    if len(floors) != 1 or not UsdPhysics.CollisionAPI(floors[0]).GetCollisionEnabledAttr().Get():
        raise ValueError('single enabled ground collision required')
    floor = str(floors[0].GetPath())
    views, metadata = [], []
    expected_path = '{ENV_REGEX_NS}/Robot'.format(ENV_REGEX_NS=live.scene.env_regex_ns)
    if robot.cfg.prim_path != expected_path:
        raise ValueError(f'unexpected robot environment path: {robot.cfg.prim_path!r}')
    for env in range(2):
        root = stage.GetPrimAtPath(f'/World/envs/env_{env}/Robot')
        if not root.IsValid():
            raise ValueError('missing robot prim')
        bodies = [prim for prim in Usd.PrimRange(root) if prim.HasAPI(UsdPhysics.RigidBodyAPI)]
        if len(bodies) != 31 or {prim.GetName() for prim in bodies} != set(robot.body_names):
            raise ValueError('runtime body set mismatch')
        actual = set()
        for body in bodies:
            nested = [prim for prim in Usd.PrimRange(body) if prim != body and prim.HasAPI(UsdPhysics.RigidBodyAPI)]
            if nested:
                raise ValueError('nested rigid body collision ownership unsupported')
            shapes = [prim for prim in Usd.PrimRange(body) if prim.HasAPI(UsdPhysics.CollisionAPI)]
            if any(not UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() for prim in shapes):
                raise ValueError('disabled body collision')
            if shapes:
                actual.add(body.GetName())
        if actual != set(collision_names):
            raise ValueError('loaded collision ownership differs from locked assets')
        env_views, env_metadata = {}, {}
        for body in bodies:
            if body.GetName() not in actual:
                continue
            path = str(body.GetPath())
            view = PhysxManager.get_physics_sim_view().create_rigid_contact_view(
                path, filter_patterns=[floor], max_contact_data_count=256)
            pair_binding(view.sensor_paths, view.filter_paths, path, [floor],
                         (view.sensor_count, view.filter_count, 3))
            env_views[body.GetName()] = view
            env_metadata[body.GetName()] = dict(body=path, sensor_paths=list(view.sensor_paths),
                                                filter_paths=list(view.filter_paths),
                                                sensor_count=view.sensor_count, filter_count=view.filter_count)
        views.append(env_views)
        metadata.append(env_metadata)
    return floor, views, metadata


def leg_drive_contact_sample(views, body_names, dt):
    """Read each bound ground force matrix after a physics step [N]."""
    import numpy as np
    import torch
    import warp as wp

    if len(views) != 2 or len(body_names) != 31 or not math.isfinite(dt) or dt <= 0:
        raise ValueError('invalid contact sampling scope')
    if set(views[0]) != set(views[1]):
        raise ValueError('ground contact coverage differs between environments')
    contacts = np.zeros((2, len(body_names), 3))
    for env, rows in enumerate(views):
        if not rows or not set(rows) <= set(body_names):
            raise ValueError('ground contact coverage missing')
        for name, view in rows.items():
            value = view.get_contact_force_matrix(dt=dt)
            value = (value if torch.is_tensor(value) else wp.to_torch(value)).detach().cpu().numpy()
            if value.shape != (1, 1, 3) or not np.isfinite(value).all():
                raise ValueError('invalid ground contact matrix')
            contacts[env, body_names.index(name)] = value[0, 0]
    return contacts


def leg_drive_step(live, robot, plan, limits, velocity_caps, binding, constant_window=None):
    """Evaluate a physics substep after advancing."""
    if not isinstance(binding, dict) or not binding.get('views') or not binding.get('collision_names'):
        raise ValueError('contact views must be bound before stepping')
    if binding.get('stopped'):
        raise ValueError('prior substep failed; stop the process')
    import numpy as np
    import torch
    import warp as wp
    from rl_exp.tools.diagnose import lizard2_leg_drive_protocol as protocol

    names = list(robot.joint_names)
    body_names = list(robot.body_names)
    views = binding['views']
    collision = binding['collision_names']
    if (len(views) != 2 or not collision or len(collision) != len(set(collision))
            or not set(collision) <= set(body_names) or any(set(row) != set(collision) for row in views)):
        raise ValueError('contact views incomplete')
    if (len(names) != 26 or len(set(names)) != 26 or names != binding['joint_names']
            or len(body_names) != 31 or len(set(body_names)) != 31 or body_names != binding['body_names']):
        raise ValueError('runtime joint or body order changed')
    if (np.shape(limits) != (2, 26, 2) or np.shape(velocity_caps) != (2, 26)
            or not np.isfinite(limits).all() or not np.isfinite(velocity_caps).all()
            or (np.asarray(velocity_caps) <= 0).any()
            or np.any(np.asarray(limits)[..., 0] >= np.asarray(limits)[..., 1])):
        raise ValueError('missing or invalid backend limits')
    reference = np.asarray(binding['root_pose'])
    if reference.shape != (2, 7) or not np.isfinite(reference).all() or np.any(abs(np.linalg.norm(reference[:, 3:], axis=1)-1) > 1e-4):
        raise ValueError('invalid root reference')
    planned = np.asarray(plan)
    if planned.shape != (26,) or not np.isfinite(planned).all():
        raise ValueError('invalid planned target')
    if constant_window is not None and (np.shape(constant_window)[1:] != (2, 26)
                                        or not np.isfinite(constant_window).all() or len(constant_window) >= 100):
        raise ValueError('invalid preceding constant-window history')
    def values(value):
        return (value if torch.is_tensor(value) else wp.to_torch(value)).detach().cpu().numpy().copy()

    binding.pop('last_frame', None)
    binding['stopped'] = True
    binding['last_frame'] = dict(planned_target=planned.copy(), stage='before_apply')
    live.action_manager.apply_action()
    live.scene.write_data_to_sim()
    target = values(robot.data.joint_pos_target.torch)
    readback = values(robot.root_view.get_dof_position_targets())
    binding['last_frame'].update(stage='before_step', target=target, readback=readback)
    if (target.shape != (2, 26) or readback.shape != (2, 26)
            or not np.isfinite(target).all() or not np.isfinite(readback).all()
            or not np.allclose(target, planned[None, :], rtol=0, atol=1e-7)
            or not np.allclose(readback, target, rtol=0, atol=1e-7)):
        raise ValueError('backend target mismatch before stepping')
    live.sim.step(render=False)
    live.scene.update(live.physics_dt)
    q = values(robot.data.joint_pos.torch)
    velocity = values(robot.data.joint_vel.torch)
    root = values(robot.data.root_link_pose_w.torch)
    binding['last_frame'].update(stage='after_step', q=q, velocity=velocity, root=root,
                                 contact=None, contact_status='not_read')
    if q.shape != (2, 26) or velocity.shape != (2, 26) or root.shape != (2, 7):
        raise ValueError('invalid substep state shape')
    try:
        contact_vectors = leg_drive_contact_sample(views, body_names, live.physics_dt)
        contacts = np.linalg.norm(contact_vectors, axis=-1)
    except Exception as exc:
        binding['last_frame']['contact_status'] = repr(exc)
        raise
    binding['last_frame'].update(contact=contacts, contact_vectors=contact_vectors, contact_status='sampled')
    for env in range(2):
        ref = reference[env]
        quat = root[env, 3:]
        if not np.isfinite(quat).all() or abs(np.linalg.norm(quat)-1) > 1e-4:
            raise ValueError('invalid root quaternion')
        rotation = 2 * np.arccos(np.clip(abs(np.dot(quat, ref[3:])), 0, 1))
        try:
            protocol.check_frame(names=names, expected_names=binding['joint_names'], planned_target=plan,
                                 target=target[env], readback=readback[env], q=q[env], velocity=velocity[env],
                                 limits=limits[env], velocity_cap=velocity_caps[env],
                                 root_displacement=root[env, :3] - ref[:3], root_rotation=rotation,
                                 contact=contacts[env], body_names=body_names, expected_body_names=binding['body_names'],
                                 collision_body_names=collision, contact_body_names=list(views[env]),
                                 constant_window=None if constant_window is None else
                                 np.concatenate((np.asarray(constant_window)[:, env, :], q[env][None, :]), axis=0))
        except protocol.Stop as exc:
            binding['last_frame']['stop'] = dict(env=env, reason=str(exc))
            raise
    binding['stopped'] = False
    return binding['last_frame']


def leg_drive_output_paths(out):
    """Return exclusive per-attempt output paths in the supplied directory."""
    prefix = out.stem + '_'
    paths = {name: out.with_name(prefix + name + suffix) for name, suffix in
             (('startup', '.json'), ('plan', '.json'), ('failure', '.json'),
              ('interrupted_case', '.npz'), ('failure_frame', '.npz'))}
    paths.update({f'case_{i:02d}': out.with_name(f'{prefix}case_{i:02d}.npz') for i in range(8)})
    paths['result'] = out
    return paths


def leg_drive_reserve_outputs(out):
    """Reserve a unique attempt before creating a simulation environment."""
    paths = leg_drive_output_paths(out)
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('calibration attempt output already exists')
    with paths['startup'].open('x', encoding='utf-8') as stream:
        json.dump({'status': 'constructing_environment', 'task': 'Lizard2-Flat-Play-v7',
                   'scope': 'startup physics count and initialization are not yet bounded'}, stream, indent=2)
    return paths


def leg_drive_swing_compare(plans, results):
    """Compare A/B RMS tracking errors from completed swing cases [rad]."""
    from rl_exp.tools.diagnose import lizard2_leg_drive_protocol as protocol

    comparison = {}
    for case in plans:
        other = protocol.Case('B', case.gravity, case.kind, case.axes, case.frequency)
        a, b = results[case.id]['rms'], results[other.id]['rms']
        comparison[other.id] = dict(rms_a_rad=a, rms_b_rad=b,
                                    rms_improvement_fraction=(a - b) / a if a else None)
    return comparison


def leg_drive_calibration(live, out, checkpoint):
    """Capture paired fixed-root v7 A/B tracking with per-substep stops."""
    import numpy as np
    import torch
    import warp as wp
    from rl_exp.tools.diagnose import lizard2_leg_drive_baseline as baseline
    from rl_exp.tools.diagnose import lizard2_leg_drive_protocol as protocol
    from rl_exp.tools.diagnose.lizard2_round_feet_probe import check_interface
    from rl_exp.tools.runrecord.binding import sha256_file

    paths = leg_drive_output_paths(out)
    if not paths['startup'].is_file():
        raise ValueError('missing exclusive startup record')
    binding, trace, results = {}, [], {}
    active, frame_index, started = None, None, time.monotonic()
    metadata = dict(status='starting', scope='fixed-root self-weight only; no support or actual torque verdict',
                    checkpoint_identity_only=checkpoint, code_sha256=sha256_file(Path(__file__)),
                    protocol_sha256=sha256_file(Path(protocol.__file__)), wall_limit_s=1800.)

    def values(value):
        return (value if torch.is_tensor(value) else wp.to_torch(value)).detach().cpu().numpy().copy()

    def save_json(path, data):
        with path.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2, allow_nan=False)

    try:
        initial_count = live.sim.get_physics_step_count()
        metadata['preflight'] = leg_drive_preflight(live, None, checkpoint)
        preflight = metadata['preflight']
        if initial_count != 0:
            raise RuntimeError('unbudgeted physics steps during environment startup')
        robot, manager = live.scene['robot'], live.action_manager
        names, bodies = list(robot.joint_names), list(robot.body_names)
        cfg, _, _, _, _ = baseline.inputs()
        legs = cfg['actuators']['legs']['joint_patterns']
        default = np.array([cfg['default_joint_pos'][name] for name in names])
        if not np.allclose(values(robot.data.default_joint_pos.torch), default[None, :], rtol=0, atol=1e-7):
            raise ValueError('runtime default joint position mismatch')
        expected_kp = np.asarray(preflight['proposed_stiffness'])
        expected_kd = np.asarray(preflight['proposed_damping'])
        limits = np.asarray(preflight['position_limits_rad'])
        caps = np.asarray(preflight['velocity_limit_rad_s'])
        floor, views, contacts = leg_drive_contact_views(live, robot, baseline.report()['authored_collision_bodies'])
        mapping = []
        for key in manager.active_terms:
            term = manager.get_term(key)
            if type(term).__name__ != 'JointPositionAction':
                raise ValueError('unsupported action term: ' + key)
            ids = list(range(len(names)))[term._joint_ids] if isinstance(term._joint_ids, slice) else list(term._joint_ids)
            for local, (name, joint_id) in enumerate(zip(term._joint_names, ids)):
                def scalar(value):
                    if torch.is_tensor(value):
                        if not torch.allclose(value[:, local], value[0, local].expand_as(value[:, local])):
                            raise ValueError('paired action mapping differs: ' + name)
                        return float(value[0, local])
                    return float(value)
                clip = term._clip[:, local] if term.cfg.clip is not None else None
                if clip is None or not torch.allclose(clip, clip[0].expand_as(clip)):
                    raise ValueError('paired action clip missing or differs: ' + name)
                mapping.append(dict(joint=name, joint_index=int(joint_id), global_index=len(mapping),
                                    scale=scalar(term._scale), offset=scalar(term._offset),
                                    clip=clip[0].cpu().tolist()))
        check_interface(names, names, mapping)
        for m in mapping:
            group = 'legs' if m['joint'] in legs else 'spine'
            if (not math.isclose(m['scale'], cfg['action'][group + '_scale'][m['joint']], rel_tol=1e-6)
                    or not math.isclose(m['offset'], cfg['default_joint_pos'][m['joint']], abs_tol=1e-6)
                    or not np.allclose(m['clip'], cfg['action']['clip'][group][m['joint']], rtol=0, atol=1e-6)):
                raise ValueError('action mapping differs from v7: ' + m['joint'])
        robot.write_joint_stiffness_to_sim_index(stiffness=torch.as_tensor(expected_kp, device=live.device, dtype=torch.float32))
        robot.write_joint_damping_to_sim_index(damping=torch.as_tensor(expected_kd, device=live.device, dtype=torch.float32))

        def read_settings():
            for getter, expected in ((robot.root_view.get_dof_stiffnesses, expected_kp),
                                     (robot.root_view.get_dof_dampings, expected_kd),
                                     (robot.root_view.get_dof_limits, limits),
                                     (robot.root_view.get_dof_max_velocities, caps),
                                     (robot.root_view.get_dof_max_forces, preflight['effort_limit_nm'])):
                if not np.allclose(values(getter()), expected, rtol=1e-5, atol=1e-6):
                    raise ValueError('backend gain or limit mismatch')

        read_settings()
        plans = protocol.swing_cases(legs)
        binding.update(views=views, collision_names=list(views[0]), joint_names=names, body_names=bodies)
        root = robot.data.default_root_state.torch.clone()
        root[:, :3] += live.scene.env_origins
        metadata.update(status='ready', floor=floor, contact_bindings=contacts, mapping=mapping,
                        cases=[{'file': paths[f'case_{i:02d}'].name, 'A': case.id,
                                'B': protocol.Case('B', case.gravity, case.kind, case.axes, case.frequency).id}
                               for i, case in enumerate(plans)],
                        scheduled_environment_steps=2 * sum(c.steps for c in plans),
                        scheduled_simulation_steps=sum(c.steps for c in plans),
                        startup_physics_steps=live.sim.get_physics_step_count(),
                        startup_scope='SimulationContext.step calls after context construction; backend callbacks not bounded',
                        limitations=['ground matrices are pair net forces and may hide cancellation',
                                     'terminations, commands and interval events are not stepped',
                                     'actual drive torque, saturation and support remain unjudged'])
        save_json(paths['plan'], metadata)
        start_count = live.sim.get_physics_step_count()
        if start_count != initial_count:
            raise RuntimeError('physics stepped during calibration setup')
        for case_index, case in enumerate(plans):
            active, frame_index, trace = case, None, []
            binding.pop('last_frame', None)
            manager.reset()
            live.scene.reset()
            before_reset = live.sim.get_physics_step_count()
            if before_reset != start_count:
                raise RuntimeError('unbudgeted physics step during reset')
            robot.write_root_pose_to_sim_index(root_pose=root[:, :7])
            robot.write_root_velocity_to_sim_index(root_velocity=root[:, 7:])
            robot.write_joint_state_to_sim_index(position=robot.data.default_joint_pos.torch.clone(),
                                                velocity=torch.zeros_like(robot.data.default_joint_vel.torch))
            live.sim.forward()
            if live.sim.get_physics_step_count() != start_count:
                raise RuntimeError('unbudgeted physics step during reset')
            if not np.allclose(values(robot.data.joint_pos.torch), default[None, :], rtol=0, atol=1e-6):
                raise ValueError('reset joint position mismatch')
            read_settings()
            binding['root_pose'] = values(robot.data.root_link_pose_w.torch)
            desired_root = values(root[:, :7])
            if (not np.allclose(binding['root_pose'][:, :3], desired_root[:, :3], rtol=0, atol=1e-5)
                    or np.any(np.abs(np.linalg.norm(binding['root_pose'][:, 3:], axis=1) - 1.) > 1e-5)
                    or np.any(np.abs(np.sum(binding['root_pose'][:, 3:] * desired_root[:, 3:], axis=1)) < 1. - 1e-6)
                    or not np.allclose(values(robot.data.joint_vel.torch), 0, rtol=0, atol=1e-6)
                    or not np.allclose(values(robot.data.root_link_vel_w.torch), 0, rtol=0, atol=1e-6)):
                raise ValueError('reset root or velocity mismatch')
            binding['stopped'] = False
            plan = protocol.trajectory(case, names, default)
            constant = []
            for frame_index, target in enumerate(plan['target']):
                if time.monotonic() - started > metadata['wall_limit_s']:
                    raise TimeoutError('wall time budget exceeded')
                if live.sim.get_physics_step_count() != start_count:
                    raise RuntimeError('unexpected physics step before sample')
                if frame_index % protocol.DECIMATION == 0:
                    raw = np.array([(target[m['joint_index']] - m['offset']) / m['scale'] for m in mapping])
                    actions = torch.as_tensor(np.tile(raw, (2, 1)), dtype=torch.float32, device=live.device)
                    manager.process_action(actions)
                    processed = np.concatenate([values(manager.get_term(key).processed_actions) for key in manager.active_terms], axis=1)
                    for env in range(2):
                        check_interface(names, names, mapping, raw, processed[env], target)
                in_constant = any(plan['windows'][key][frame_index] for key in
                                  ('positive_hold', 'positive_return', 'negative_hold', 'negative_return')
                                  if key in plan['windows'])
                previous = np.asarray(constant) if in_constant and constant else None
                sample = leg_drive_step(live, robot, target, limits, caps, binding, constant_window=previous)
                start_count += 1
                if live.sim.get_physics_step_count() != start_count:
                    raise RuntimeError('unexpected physics step count')
                trace.append({key: np.asarray(sample[key]).copy() for key in
                              ('target', 'readback', 'q', 'velocity', 'root', 'contact_vectors')})
                if in_constant:
                    constant.append(sample['q'].copy())
                    constant = constant[-99:]
                else:
                    constant.clear()
            arrays = {key: np.stack([row[key] for row in trace]) for key in trace[0]}
            arrays['time_s'] = plan['time']
            with paths[f'case_{case_index:02d}'].open('xb') as stream:
                np.savez_compressed(stream, **arrays)
            for env, gain in enumerate(('A', 'B')):
                actual_case = protocol.Case(gain, case.gravity, case.kind, case.axes, case.frequency)
                metrics = protocol.measure(actual_case, names, default, sample_names=names, time=plan['time'],
                                           target_readback=arrays['readback'][:, env], q=arrays['q'][:, env])
                results[actual_case.id] = dict(metrics, safety='pass')
            print('LEG_DRIVE_CASE', case.id, flush=True)
        comparison = leg_drive_swing_compare(plans, results)
        report = dict(status='completed', metadata=metadata, results=results, comparison=comparison,
                      sampled_physics_steps=start_count-initial_count,
                      overall='unjudged: illustrative screening thresholds not approved; no support or actual torque')
        save_json(out, report)
        print('LEG_DRIVE_CALIBRATION_OK', out, flush=True)
    except BaseException as exc:
        if trace:
            with paths['interrupted_case'].open('xb') as stream:
                np.savez_compressed(stream, **{key: np.stack([row[key] for row in trace]) for key in trace[0]})
        frame = binding.get('last_frame')
        if frame:
            with paths['failure_frame'].open('xb') as stream:
                np.savez_compressed(stream, **{key: value for key, value in frame.items() if isinstance(value, np.ndarray)})
        save_json(paths['failure'], dict(status='failed', error=repr(exc), traceback=traceback.format_exc(),
                  active_case=None if active is None else active.id, frame_index=frame_index,
                  last_frame_stage=None if not frame else frame.get('stage'),
                  last_frame_contact_status=None if not frame else frame.get('contact_status'),
                  last_frame_stop=None if not frame else frame.get('stop'), completed_results=results,
                  physics_step_count=live.sim.get_physics_step_count(), metadata=metadata))
        raise


def drive_probe(live, out, mode, checkpoint):
    """Observe bounded sine response through action manager; time [s], angle [rad], estimated torque [N*m]."""
    import numpy as np
    import torch
    import warp as wp
    from rl_exp.tools.runrecord.binding import sha256_file

    check_time = np.arange(0., 8., 0.02)
    check_target = 0.1 * np.sin(2*math.pi*check_time)
    check_actual = 0.06 * np.sin(2*math.pi*check_time - math.pi/6)
    check_result = sine_response(check_time, check_actual, check_target, 1.)
    assert abs(check_result['amplitude_ratio'] - 0.6) < 1e-6
    assert abs(check_result['phase_lag_deg'] - 30.) < 1e-6
    negative = sine_response(check_time, 0.06 * np.sin(2*math.pi*check_time + math.pi/6), check_target, 1.)
    assert abs(negative['phase_lag_deg'] - 30.) > 1.
    assert sine_response(check_time, np.zeros_like(check_time), check_target, 1.)['amplitude_ratio'] < 1e-6
    robot = live.scene['robot']
    term = live.action_manager.get_term('joint_pos_legs')
    names, ids = list(term._joint_names), list(term._joint_ids)
    assert len(names) == 16 and robot.is_fixed_base == (mode == 'suspended')
    settings = {'amplitude_rad': 0.10, 'frequency_hz': [0.5, 1.0], 'settle_s': 2., 'cycles': 4,
                'cases': ['baseline', 'proximal_kp2_kd_sqrt2', 'proximal_kd_half', 'bend_kp_half_kd_sqrt_half',
                          'proximal_scale2'], 'torque_channel': 'K*(target-q)-D*dq from live gains, estimate only',
                'velocity_target': 'zero', 'control_dt_s': live.step_dt, 'physics_dt_s': live.physics_dt,
                'raw_amplitude': 0.5, 'phase_time_alignment': 'position sampled one control_dt after held target issuance',
                'scope': 'isolated calibration, no policy/reward/termination/DR events; gravity retained'}
    kp, kd = robot.data.joint_stiffness.torch.clone(), robot.data.joint_damping.torch.clone()
    proximal = [ids[i] for i, n in enumerate(names) if n.endswith(('_swing_joint', '_twist_joint'))]
    bend = [ids[i] for i, n in enumerate(names) if n.endswith(('_elbow_joint', '_knee_joint'))]
    kp[1, proximal] *= 2.
    kd[1, proximal] *= math.sqrt(2.)
    kd[2, proximal] *= 0.5
    kp[3, bend] *= 0.5
    kd[3, bend] *= math.sqrt(0.5)
    robot.write_joint_stiffness_to_sim_index(stiffness=kp)
    robot.write_joint_damping_to_sim_index(damping=kd)
    term._scale[4, [i for i, n in enumerate(names) if n.endswith(('_swing_joint', '_twist_joint'))]] *= 2.
    assert torch.allclose(wp.to_torch(robot.root_view.get_dof_stiffnesses()).to(kp.device), kp)
    assert torch.allclose(wp.to_torch(robot.root_view.get_dof_dampings()).to(kd.device), kd)
    baseline_root = robot.data.default_root_state.torch.clone()
    baseline_root[:, :3] += live.scene.env_origins
    zeros = torch.zeros((5, live.action_manager.total_action_dim), device=live.device)
    sensor = live.scene['contact_forces']
    belly_ids = [sensor.body_names.index(n) for n in ('base_link', 'chest_pitch')]
    force_peak, z_min = np.zeros(5), np.full(5, np.inf)
    results = []
    out.parent.mkdir(parents=True, exist_ok=True)
    metadata = {'settings': settings, 'mode': mode, 'source_checkpoint_identity_only': checkpoint,
                'joint_names': names, 'stiffness': kp.cpu().tolist(), 'damping': kd.cpu().tolist(),
                'action_scale': term._scale.cpu().tolist(), 'action_clip': term._clip.cpu().tolist(),
                'code_sha256': sha256_file(Path(__file__)), 'source_usd_sha256': sha256_file(Path(live.cfg.scene.robot.spawn.usd_path))}
    (out.parent / 'plan.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')

    def reset_fixture():
        live.action_manager.reset()
        live.scene.reset()
        robot.write_root_pose_to_sim_index(root_pose=baseline_root[:, :7])
        robot.write_root_velocity_to_sim_index(root_velocity=baseline_root[:, 7:])
        robot.write_joint_state_to_sim_index(position=robot.data.default_joint_pos.torch.clone(),
                                            velocity=torch.zeros_like(robot.data.default_joint_vel.torch))
        live.sim.forward()
        assert torch.allclose(robot.data.joint_pos.torch, robot.data.default_joint_pos.torch, atol=1e-6)
        assert torch.allclose(wp.to_torch(robot.root_view.get_dof_stiffnesses()).to(kp.device), kp)
        assert torch.allclose(wp.to_torch(robot.root_view.get_dof_dampings()).to(kd.device), kd)

    def step(raw):
        live.action_manager.process_action(raw)
        target = raw[:, :16] * term._scale + term._offset
        target = torch.maximum(torch.minimum(target, term._clip[:, :, 1]), term._clip[:, :, 0])
        assert torch.allclose(term.processed_actions, target, atol=1e-6)
        for _ in range(live.cfg.decimation):
            live.action_manager.apply_action()
            live.scene.write_data_to_sim()
            live.sim.step(render=False)
            live.scene.update(live.physics_dt)
        q, dq = robot.data.joint_pos.torch[:, ids], robot.data.joint_vel.torch[:, ids]
        assert torch.isfinite(q).all() and torch.isfinite(dq).all()
        return q.cpu().numpy().copy(), target.cpu().numpy().copy()

    reset_fixture()
    for _ in range(round(settings['settle_s'] / live.step_dt)):
        step(zeros)
        force = sensor.data.net_forces_w.torch[:, belly_ids].norm(dim=-1).max(dim=1).values.cpu().numpy()
        force_peak = np.maximum(force_peak, force)
        z_min = np.minimum(z_min, robot.data.body_link_pos_w.torch[:, robot.body_names.index('base_link'), 2].cpu().numpy())
    for frequency in settings['frequency_hz']:
        for local, name in enumerate(names):
            reset_fixture()
            for _ in range(round(settings['settle_s'] / live.step_dt)):
                step(zeros)
            positions, targets, estimates, base_poses, belly_forces = [], [], [], [], []
            steps = round(settings['cycles'] / frequency / live.step_dt)
            for index in range(steps):
                raw = zeros.clone()
                raw[:, local] = settings['raw_amplitude'] * math.sin(2 * math.pi * frequency * index * live.step_dt)
                q, target = step(raw)
                positions.append(q)
                targets.append(target)
                effort = kp[:, ids] * (torch.tensor(target, device=live.device) - robot.data.joint_pos.torch[:, ids])
                effort -= kd[:, ids] * robot.data.joint_vel.torch[:, ids]
                estimates.append(effort.cpu().numpy().copy())
                base_poses.append(robot.data.body_link_pose_w.torch[:, robot.body_names.index('base_link')].cpu().numpy().copy())
                belly_forces.append(sensor.data.net_forces_w.torch[:, belly_ids].norm(dim=-1).max(dim=1).values.cpu().numpy())
            positions, targets, estimates = np.stack(positions), np.stack(targets), np.stack(estimates)
            base_poses, belly_forces = np.stack(base_poses), np.stack(belly_forces)
            time = np.arange(steps) * live.step_dt
            for case in range(5):
                response = sine_response(time, positions[:, case, local], targets[:, case, local], frequency)
                response['phase_lag_deg'] = float(np.degrees(np.angle(np.exp(1j*np.radians(
                    response['phase_lag_deg'] + 360*frequency*live.step_dt)))))
                results.append({'case': settings['cases'][case], 'joint': name, 'frequency_hz': frequency, **response,
                                'mean_base_z_m': float(base_poses[:, case, 2].mean()),
                                'belly_force_peak_n': float(belly_forces[:, case].max()),
                                'estimated_effort_peak_nm': float(np.abs(estimates[:, case, local]).max()),
                                'estimated_saturation_fraction': float(np.mean(np.abs(estimates[:, case, local]) >=
                                    float(robot.data.joint_effort_limits.torch[case, ids[local]])))})
            np.savez_compressed(out.parent / f'{frequency:g}hz_{name}.npz', positions=positions, targets=targets,
                                estimated_effort=estimates, time_s=time, base_pose_xyzw=base_poses, belly_force_n=belly_forces)
            (out.parent / 'progress.json').write_text(json.dumps({'completed_rows': results}, indent=2), encoding='utf-8')
            print('DRIVE_CASE', mode, frequency, name, flush=True)
    report = {'metadata': metadata, 'results': results, 'zero_action_belly_peak_n': force_peak.tolist(),
              'zero_action_base_min_z_m': z_min.tolist(), 'completed': True}
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DRIVE_PROBE_OK', out, flush=True)


calibration_started = False
propulsion_started = False
try:
    import gymnasium as gym
    import numpy as np
    import torch
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg
    from rsl_rl.runners import OnPolicyRunner
    import rl_exp.tasks  # noqa: F401
    from ablation_harness.components.dr_controller import apply_eval_mode
    from ablation_harness.record import checkpoint_digest

    task = 'Lizard2-Flat-Play-v7'
    if args.propulsion_samples:
        from rl_exp.tools.runrecord.binding import sha256_file

        propulsion_paths = {name: args.out.with_name(args.out.stem + suffix) for name, suffix in
                            (('startup', '_startup.json'), ('failure', '_failure.json'),
                             ('samples', '_landing_samples.npz'), ('partial', '_partial.npz'))}
        if any(path.exists() for path in (args.out, *propulsion_paths.values())):
            raise FileExistsError('propulsion attempt output already exists')
        with propulsion_paths['startup'].open('x', encoding='utf-8') as stream:
            json.dump({'status': 'starting', 'task': task, 'checkpoint': checkpoint_digest(args.checkpoint),
                       'code_sha256': sha256_file(Path(__file__)), 'speed_mps': args.speed,
                       'seed': args.seed, 'steps': args.steps}, stream, indent=2, allow_nan=False)
        propulsion_started = True
    spec = gym.spec(task)
    cfg = resolve_presets(string_to_callable(spec.kwargs['env_cfg_entry_point'])())
    cfg.scene.num_envs, cfg.seed = 4, args.seed
    cfg.episode_length_s = 20.0
    apply_eval_mode(cfg, 'nominal')
    if args.landing_samples:
        assert not args.drive_probe and not args.policy_drive_case and args.swing_clip is None
        cfg.scene.lazy_sensor_update = False
        floor = cfg.terminations.head_ground_contact.params['floor_prim_path']
        for leg, tip in FOOT.items():
            sensor_cfg = cfg.scene.head_ground_contact.copy()
            sensor_cfg.prim_path = f'{{ENV_REGEX_NS}}/Robot/Geometry/{leg}_{tip}'
            sensor_cfg.filter_prim_paths_expr = [floor]
            sensor_cfg.update_period = cfg.sim.dt
            sensor_cfg.history_length = cfg.decimation
            sensor_cfg.track_air_time = False
            if args.propulsion_samples:
                sensor_cfg.track_contact_points = True
                sensor_cfg.track_friction_forces = True
                sensor_cfg.max_contact_data_count_per_prim = 128
            setattr(cfg.scene, f'landing_{leg}', sensor_cfg)
    if args.policy_drive_case:
        assert not args.drive_probe and args.swing_clip is None, 'one diagnostic intervention per run'
        role = 'twist' if args.policy_drive_case == 'twist_kp2' else 'swing'
        group = cfg.scene.robot.actuators['legs']
        for name in group.stiffness:
            if name.endswith(f'_{role}_joint'):
                if args.policy_drive_case.endswith('kp2'):
                    group.stiffness[name] *= 2.
                    group.damping[name] *= math.sqrt(2.)
                else:
                    group.damping[name] *= 0.5
    if args.drive_probe or args.leg_drive_preflight or args.leg_drive_calibration:
        cfg.scene.num_envs = 2 if args.leg_drive_preflight or args.leg_drive_calibration else 5
        cfg.scene.robot.spawn.articulation_props.fix_root_link = bool(
            args.leg_drive_preflight or args.leg_drive_calibration or args.drive_probe == 'suspended')
        if args.leg_drive_preflight or args.leg_drive_calibration or args.drive_probe == 'suspended':
            cfg.scene.robot.init_state.pos = (0., 0., 2.)
            original_spawn = cfg.scene.robot.spawn.func

            def suspended_spawn(prim_path, spawn_cfg, *positional, **keywords):
                from pxr import Sdf, Usd, UsdPhysics

                prim = original_spawn(prim_path, spawn_cfg, *positional, **keywords)
                roots = [p for p in Usd.PrimRange(prim) if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
                assert len(roots) == 2 and sum(p.GetName() == 'base_link' for p in roots) == 1
                base = next(p for p in roots if p.GetName() == 'base_link')
                excluded = {'PhysicsArticulationRootAPI', 'NewtonArticulationRootAPI', 'PhysxArticulationAPI'}
                base.SetMetadata('apiSchemas', Sdf.TokenListOp.CreateExplicit(
                    [name for name in base.GetAppliedSchemas() if name not in excluded]))
                assert not base.HasAPI(UsdPhysics.ArticulationRootAPI) and base.HasAPI(UsdPhysics.RigidBodyAPI)
                assert len([p for p in Usd.PrimRange(prim) if p.HasAPI(UsdPhysics.ArticulationRootAPI)]) == 1
                return prim

            cfg.scene.robot.spawn.func = suspended_spawn
        for name, event in vars(cfg.events).items():
            if event is not None:
                setattr(cfg.events, name, None)
    agent = handle_deprecated_rsl_rl_cfg(string_to_callable(spec.kwargs['rsl_rl_cfg_entry_point'])(),
                                         importlib.metadata.version('rsl-rl-lib'))
    if args.leg_drive_calibration:
        paths = leg_drive_reserve_outputs(args.out)
        calibration_started = True
    env = gym.make(task, cfg=cfg)
    live = env.unwrapped
    if args.leg_drive_preflight:
        leg_drive_preflight(live, args.out, checkpoint_digest(args.checkpoint))
        env.close()
        app.close(exit_code=0)
        sys.exit(0)
    if args.leg_drive_calibration:
        leg_drive_calibration(live, args.out, checkpoint_digest(args.checkpoint))
        env.close()
        app.close(exit_code=0)
        sys.exit(0)
    wrapper = RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions)
    if args.drive_probe:
        drive_probe(live, args.out, args.drive_probe, checkpoint_digest(args.checkpoint))
        wrapper.close()
        app.close(exit_code=0)
        sys.exit(0)
    runner = OnPolicyRunner(wrapper, agent.to_dict(), log_dir=None, device=live.device)
    runner.load(args.checkpoint)
    policy = runner.get_inference_policy(device=live.device)
    robot = live.scene['robot']
    if args.policy_drive_case:
        import warp as wp
        assert torch.allclose(wp.to_torch(robot.root_view.get_dof_stiffnesses()).to(live.device),
                              robot.data.joint_stiffness.torch)
        assert torch.allclose(wp.to_torch(robot.root_view.get_dof_dampings()).to(live.device),
                              robot.data.joint_damping.torch)
    command = live.command_manager.get_term('base_velocity')
    leg_term = live.action_manager.get_term('joint_pos_legs')
    leg_names = list(leg_term._joint_names)
    if args.swing_clip is not None:
        for i, n in enumerate(leg_names):
            if n.endswith('_swing_joint'):
                leg_term._clip[:, i] = torch.tensor([-args.swing_clip, args.swing_clip], device=live.device)
    jidx = [robot.joint_names.index(n) for n in leg_names]
    bidx = {leg: (robot.body_names.index(f'{leg}_{LEGS[leg]}'), robot.body_names.index(f'{leg}_{FOOT[leg]}'))
            for leg in LEGS}
    samples, sample_frames = [], {}
    if args.pose_samples:
        from pxr import UsdPhysics
        from rl_exp.tools.diagnose.lizard2_round_feet_usd import rotation
        from isaaclab.utils.math import matrix_from_quat

        for prim in live.sim.stage.Traverse():
            if '/env_0/' not in str(prim.GetPath()) or prim.GetName() not in leg_names:
                continue
            if not prim.IsA(UsdPhysics.RevoluteJoint):
                continue
            joint = UsdPhysics.RevoluteJoint(prim)
            basis = np.eye(3)['XYZ'.index(joint.GetAxisAttr().Get())]
            sample_frames[prim.GetName()] = [
                (str(rel.GetTargets()[0]).rsplit('/', 1)[-1], np.array(position.Get()), rotation(quat.Get()) @ basis)
                for rel, position, quat in (
                    (joint.GetBody0Rel(), joint.GetLocalPos0Attr(), joint.GetLocalRot0Attr()),
                    (joint.GetBody1Rel(), joint.GetLocalPos1Attr(), joint.GetLocalRot1Attr()))]
        assert set(sample_frames) == set(leg_names), 'loaded USD leg-joint set mismatch'
    if args.policy_drive_case:
        from rl_exp.tools.runrecord.binding import sha256_file

        args.out.parent.mkdir(parents=True, exist_ok=True)
        (args.out.parent / 'plan.json').write_text(json.dumps({
            'task': task, 'checkpoint': checkpoint_digest(args.checkpoint), 'policy_drive_case': args.policy_drive_case,
            'seed': args.seed, 'speed_mps': args.speed, 'steps': args.steps,
            'leg_action_names': leg_names, 'stiffness': robot.data.joint_stiffness.torch[0, jidx].cpu().tolist(),
            'damping': robot.data.joint_damping.torch[0, jidx].cpu().tolist(),
            'code_sha256': sha256_file(Path(__file__)), 'scope': 'frozen policy gain intervention, not retraining'},
            indent=2), encoding='utf-8')
    landing_trace = []
    landing_active = np.ones(live.num_envs, dtype=bool)
    if args.landing_samples:
        import xml.etree.ElementTree as ET
        from pxr import UsdPhysics

        test_force = np.array([0, 0, 0, 0, 10, 10, 10, 0, 10, 0, 0, 0, 0, 10, 10], dtype=float).reshape(-1, 1, 1)
        test_valid = np.ones((len(test_force), 1), dtype=bool)
        assert [e['sample'] for e in landing_events(test_force, test_valid, 0.005)] == [4, 13]
        test_valid[13:] = False
        assert [e['sample'] for e in landing_events(test_force, test_valid, 0.005)] == [4]
        floor_prim = live.sim.stage.GetPrimAtPath(floor)
        assert floor_prim.IsValid() and floor_prim.HasAPI(UsdPhysics.CollisionAPI)
        landing_sensors = [live.scene[f'landing_{leg}'] for leg in LEGS]
        for (leg, tip), sensor in zip(FOOT.items(), landing_sensors):
            assert sensor.body_names == [f'{leg}_{tip}'] and sensor.contact_view.filter_count == 1
            assert all(row == floor or row == [floor] for row in sensor.contact_view.filter_paths)
            if args.propulsion_samples:
                sources = list(sensor.contact_view.sensor_paths)
                sources = [row[0] if isinstance(row, (list, tuple)) and len(row) == 1 else row for row in sources]
                assert sources == [f'/World/envs/env_{i}/Robot/Geometry/{leg}_{tip}' for i in range(live.num_envs)]
                assert sensor.cfg.track_contact_points and sensor.cfg.track_friction_forces
        tree = ET.parse(Path(cfg.scene.robot.spawn.usd_path).with_suffix('.urdf')).getroot()
        for leg, tip in FOOT.items():
            collision = tree.find(f"link[@name='{leg}_{tip}']/collision")
            assert float(collision.find('geometry/sphere').get('radius')) == 0.08
            assert collision.find('origin').get('xyz', '0 0 0') == '0 0 0'
        original_scene_update = live.scene.update
        capture_landing = False

        def landing_scene_update(dt):
            original_scene_update(dt)
            if not capture_landing:
                return
            assert math.isclose(dt, live.physics_dt), 'landing capture requires each physics substep'
            positions = robot.data.body_link_pos_w.torch
            directions = torch.stack([positions[:, foot] - positions[:, top] for top, foot in bidx.values()], dim=1)
            directions /= directions.norm(dim=-1, keepdim=True)
            forces = torch.stack([sensor.data.force_matrix_w.torch[:, 0, 0] for sensor in landing_sensors], dim=1)
            row = {'force_w_n': forces.cpu().numpy().copy(),
                   'shank_direction_w': directions.cpu().numpy().copy(),
                   'foot_pos_w_m': positions[:, [foot for _, foot in bidx.values()]].cpu().numpy().copy(),
                   'joint_pos_rad': robot.data.joint_pos.torch.cpu().numpy().copy(),
                   'root_pose_xyzw': robot.data.root_link_pose_w.torch.cpu().numpy().copy(),
                   'valid': landing_active.copy()}
            if args.propulsion_samples:
                import warp as wp

                row['friction_w_n'] = torch.stack([s.data.friction_forces_w.torch[:, 0, 0] for s in landing_sensors], dim=1).cpu().numpy().copy()
                row['contact_pos_w_m'] = torch.stack([s.data.contact_pos_w.torch[:, 0, 0] for s in landing_sensors], dim=1).cpu().numpy().copy()
                row['contact_count'] = np.stack([wp.to_torch(s.contact_view.get_contact_data(dt=dt)[4]).cpu().numpy()[:, 0]
                                                 for s in landing_sensors], axis=1)
                row['friction_count'] = np.stack([wp.to_torch(s.contact_view.get_friction_data(dt=dt)[2]).cpu().numpy()[:, 0]
                                                  for s in landing_sensors], axis=1)
                row['joint_velocity_rad_s'] = robot.data.joint_vel.torch.cpu().numpy().copy()
                row['joint_target_rad'] = robot.data.joint_pos_target.torch.cpu().numpy().copy()
                row['step_count'] = live.sim.get_physics_step_count()
            landing_trace.append(row)

        live.scene.update = landing_scene_update
    contact_trace = []
    contact_active = np.ones(live.num_envs, dtype=bool)
    if args.contact_samples:
        test_loaded = np.array([0, 1, 0, 1, 0, 1], dtype=bool).reshape(-1, 1, 1)
        test_valid = np.array([0, 1, 1, 1, 0, 0], dtype=bool).reshape(-1, 1)
        assert np.flatnonzero(contact_edges(test_loaded, test_valid)).tolist() == [3]
        assert np.count_nonzero(test_loaded[1:] & ~test_loaded[:-1]) == 3
        contact_sensor = live.scene['contact_forces']
        contact_ids = [contact_sensor.body_names.index(f'{leg}_{FOOT[leg]}') for leg in LEGS]
        contact_belly_ids = [contact_sensor.body_names.index(name) for name in ('base_link', 'chest_pitch')]
        contact_start = robot.data.body_link_pos_w.torch[:, robot.body_names.index('base_link')].cpu().numpy().copy()
    resets = 0
    pos, tgt, tilt, raw = [], [], {leg: [] for leg in LEGS}, []
    obs = wrapper.get_observations()
    for step in range(args.steps):
        command.vel_command_b[:] = torch.tensor([args.speed, 0., 0.], device=live.device)
        landing_start = len(landing_trace)
        capture_landing = args.landing_samples
        with torch.no_grad():
            act = policy(obs)
            raw.append(act[:, :len(leg_names)].cpu().numpy())
            obs, _, done, _ = wrapper.step(act)
        capture_landing = False
        if args.landing_samples:
            assert len(landing_trace)-landing_start == live.cfg.decimation
            ended = done.cpu().numpy().astype(bool)
            landing_active &= ~ended
            for row in landing_trace[landing_start:]:
                row['valid'][ended] = False
        resets += int(done.sum())
        if not bool(done.any()):
            assert torch.equal(leg_term.raw_actions, act[:, :len(leg_names)]), 'leg slice != action term raw input'
        d = robot.data
        pos.append(d.joint_pos.torch[:, jidx].cpu().numpy())
        tgt.append(d.joint_pos_target.torch[:, jidx].cpu().numpy())
        bp = d.body_link_pos_w.torch
        if args.contact_samples:
            from isaaclab.utils.math import quat_apply_inverse, yaw_quat

            contact_active &= ~done.cpu().numpy().astype(bool)
            directions = torch.stack([bp[:, foot] - bp[:, top] for top, foot in bidx.values()], dim=1)
            directions /= directions.norm(dim=-1, keepdim=True)
            yaw_velocity = quat_apply_inverse(yaw_quat(d.root_link_quat_w.torch), d.root_link_lin_vel_w.torch)
            contact_trace.append({'valid': contact_active.copy() & (step > 0),
                                  'foot_force_z_n': contact_sensor.data.net_forces_w.torch[:, contact_ids, 2].cpu().numpy().copy(),
                                  'shank_tilt_deg': torch.rad2deg(torch.acos((-directions[..., 2]).clamp(-1, 1))).cpu().numpy(),
                                  'shank_xy_deg': torch.rad2deg(torch.asin(directions[..., :2].clamp(-1, 1))).cpu().numpy(),
                                  'foot_pos_w_m': bp[:, [foot for _, foot in bidx.values()]].cpu().numpy().copy(),
                                  'base_pos_w_m': bp[:, robot.body_names.index('base_link')].cpu().numpy().copy(),
                                  'yaw_velocity_mps': yaw_velocity.cpu().numpy(),
                                  'belly_force_n': contact_sensor.data.net_forces_w.torch[:, contact_belly_ids].norm(dim=-1).max(dim=1).values.cpu().numpy()})
        if args.pose_samples and step % max(1, round(0.5 / live.step_dt)) == 0 and not bool(done[0]):
            positions = bp[0].cpu().numpy()
            rotations = matrix_from_quat(d.body_link_quat_w.torch[0]).cpu().numpy()
            axes, axis_errors, pivot_errors = {}, [], []
            for name, frames in sample_frames.items():
                world = [(positions[robot.body_names.index(body)] + rotations[robot.body_names.index(body)] @ pivot,
                          rotations[robot.body_names.index(body)] @ axis) for body, pivot, axis in frames]
                axes[name] = world[1][1].tolist()
                axis_errors.append(float(np.linalg.norm(world[0][1] - world[1][1])))
                pivot_errors.append(float(np.linalg.norm(world[0][0] - world[1][0])))
            samples.append({'time_s': (step + 1) * live.step_dt,
                            'joint_pos_rad': dict(zip(robot.joint_names, d.joint_pos.torch[0].cpu().tolist())),
                            'body_pos_w_m': dict(zip(robot.body_names, positions.tolist())),
                            'body_quat_w_xyzw': dict(zip(robot.body_names, d.body_link_quat_w.torch[0].cpu().tolist())),
                            'joint_axes_w': axes, 'max_joint_axis_pair_error': max(axis_errors),
                            'max_joint_pivot_pair_error_m': max(pivot_errors)})
        for leg, (b_top, b_foot) in bidx.items():
            v = bp[:, b_foot] - bp[:, b_top]
            ang = torch.rad2deg(torch.acos((-v[:, 2] / v.norm(dim=-1)).clamp(-1, 1)))
            tilt[leg].append(torch.where(bp[:, b_foot, 2] < STANCE_Z, ang, torch.full_like(ang, float('nan'))).cpu().numpy())
    pos, tgt = np.stack(pos), np.stack(tgt)
    raw = np.stack(raw)
    joints = {}
    for i, name in enumerate(leg_names):
        p, t, r = pos[:, :, i].ravel(), tgt[:, :, i].ravel(), raw[:, :, i].ravel()
        joints[name] = {'raw_mean': float(r.mean()), 'raw_p5': float(np.percentile(r, 5)), 'raw_p95': float(np.percentile(r, 95)),
                        'pos_std': float(p.std()), 'pos_span_5_95': float(np.percentile(p, 95) - np.percentile(p, 5)),
                        'tgt_span_5_95': float(np.percentile(t, 95) - np.percentile(t, 5)),
                        'tgt_mean': float(t.mean()), 'tgt_min': float(t.min()), 'tgt_max': float(t.max()),
                        'pos_mean': float(p.mean()),
                        'mean_abs_track_err': float(np.abs(t - p).mean())}
    stance = {}
    for leg, rows in tilt.items():
        a = np.stack(rows).ravel()
        a = a[~np.isnan(a)]
        stance[leg] = {'samples': int(a.size), 'mean_deg': float(a.mean()) if a.size else None,
                       'p10_p90_deg': [float(np.percentile(a, 10)), float(np.percentile(a, 90))] if a.size else None}
    report = dict(checkpoint=checkpoint_digest(args.checkpoint), task=task, speed=args.speed, seed=args.seed,
                  action_scale=leg_term._scale[0].cpu().tolist(), action_offset=leg_term._offset[0].cpu().tolist(),
                  action_clip=leg_term._clip[0].cpu().tolist(), clip_actions=agent.clip_actions,
                  steps=args.steps, dt=live.step_dt, stance_proxy_foot_z_m=STANCE_Z, swing_clip=args.swing_clip,
                  joints=joints, stance_shank_tilt=stance, leg_action_names=leg_names,
                  runtime_joint_names=robot.joint_names,
                  reset_count=resets, pose_samples_env0=samples, policy_drive_case=args.policy_drive_case,
                  leg_stiffness=robot.data.joint_stiffness.torch[0, jidx].cpu().tolist(),
                  leg_damping=robot.data.joint_damping.torch[0, jidx].cpu().tolist())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.contact_samples:
        arrays = {name: np.stack([row[name] for row in contact_trace]) for name in contact_trace[0]}
        np.savez_compressed(args.out.parent / 'contact_samples.npz', **arrays)
        valid = arrays['valid']
        force = arrays['foot_force_z_n']
        loaded = force > 1.
        rising = contact_edges(loaded, valid)
        feet = {}
        for i, leg in enumerate(LEGS):
            stance_mask = loaded[..., i] & valid
            event_mask = rising[..., i]
            event_tilt = arrays['shank_tilt_deg'][..., i][event_mask]
            stance_tilt = arrays['shank_tilt_deg'][..., i][stance_mask]
            feet[leg] = {'contact_indicator_fraction': float(stance_mask.sum() / valid.sum()) if valid.any() else None,
                         'candidate_contact_edges': int(event_mask.sum()),
                         'candidate_edge_tilt_deg': event_tilt.tolist(),
                         'force_contact_tilt_mean_deg': float(stance_tilt.mean()) if stance_tilt.size else None,
                         'force_contact_xy_mean_deg': arrays['shank_xy_deg'][..., i, :][stance_mask].mean(axis=0).tolist()
                                                      if stance_tilt.size else None}
        first_episode_joints = {}
        for i, name in enumerate(leg_names):
            actual, target = pos[..., i][valid], tgt[..., i][valid]
            first_episode_joints[name] = {
                'samples': int(actual.size),
                'pos_span_5_95_rad': float(np.percentile(actual, 95)-np.percentile(actual, 5)) if actual.size else None,
                'target_span_5_95_rad': float(np.percentile(target, 95)-np.percentile(target, 5)) if actual.size else None,
                'mean_abs_track_error_rad': float(np.abs(actual-target).mean()) if actual.size else None}
        report['contact_diagnostic'] = {'feet': feet, 'valid_control_frames': int(valid.sum()),
                                        'per_env_valid_frames': valid.sum(axis=0).tolist(),
                                        'per_env_first_invalid_s': [float((np.flatnonzero(~valid[1:, i])[0]+2)*live.step_dt)
                                                                    if (~valid[1:, i]).any() else None for i in range(live.num_envs)],
                                        'first_episode_joint_use': first_episode_joints,
                                        'threshold_n': 1., 'validity': 'first episode only; done and frame zero excluded',
                                        'sampling': 'last physics substep of control frame, unfiltered net vertical force',
                                        'scope': 'diagnostic force-edge candidates, not calibrated touchdown or slip verdict',
                                        'mean_velocity_error_mps': float(np.abs(arrays['yaw_velocity_mps'][..., 0][valid]-args.speed).mean())
                                                                   if valid.any() else None,
                                        'belly_contact_indicator_fraction': float(np.mean(arrays['belly_force_n'][valid] > 1.))
                                                                            if valid.any() else None,
                                        'per_env_forward_displacement_m': [float(arrays['base_pos_w_m'][valid[:, i], i, 0][-1]-contact_start[i, 0])
                                                                           if valid[:, i].any() else None for i in range(live.num_envs)]}
    if args.landing_samples:
        arrays = {name: np.stack([row[name] for row in landing_trace]) for name in landing_trace[0]}
        arrays['valid'][:live.cfg.decimation] = False
        if args.propulsion_samples:
            with args.out.with_name(args.out.stem + '_landing_samples.npz').open('xb') as stream:
                np.savez_compressed(stream, **arrays)
        else:
            np.savez_compressed(args.out.parent / 'landing_samples.npz', **arrays)
        events = landing_events(arrays['force_w_n'][..., 2], arrays['valid'], live.physics_dt)
        for event in events:
            i, env, leg = event['sample'], event['env'], event['leg_index']
            direction = arrays['shank_direction_w'][i, env, leg]
            event.update(time_s=(i+1)*live.physics_dt, leg=list(LEGS)[leg],
                         tilt_deg=float(np.degrees(np.arccos(np.clip(-direction[2], -1, 1)))),
                         xy_deg=np.degrees(np.arcsin(np.clip(direction[:2], -1, 1))).tolist(),
                         sphere_bottom_z_m=float(arrays['foot_pos_w_m'][i, env, leg, 2]-0.08))
        report['landing_diagnostic'] = {'events': events, 'physics_samples': len(landing_trace),
                                        'valid_env_samples': int(arrays['valid'].sum()),
                                        'dt_s': live.physics_dt, 'filter_floor': floor, 'threshold_n': 1.,
                                        'flight_s': 0.02, 'confirm_contact_s': 0.01,
                                        'joint_names': robot.joint_names,
                                        'sensor_bodies': [sensor.body_names for sensor in landing_sensors],
                                        'scope': 'filtered-force onset after brief flight, not calibrated material contact or slip'}
        if args.propulsion_samples:
            from rl_exp.tools.runrecord.binding import sha256_file

            report['propulsion_diagnostic'] = {
                'samples': args.out.stem + '_landing_samples.npz', 'code_sha256': sha256_file(Path(__file__)),
                'usd_sha256': sha256_file(Path(cfg.scene.robot.spawn.usd_path)),
                'physics_dt_s': live.physics_dt, 'step_count_first_last': [int(arrays['step_count'][0]), int(arrays['step_count'][-1])],
                'count_range': [int(arrays['contact_count'].min()), int(arrays['contact_count'].max())],
                'friction_count_range': [int(arrays['friction_count'].min()), int(arrays['friction_count'].max())],
                'scope': 'ground-filtered normal and friction forces with mean contact point; not actual actuator torque'}
        live.scene.update = original_scene_update
    if args.propulsion_samples:
        with args.out.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
    else:
        args.out.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print('SHANK_USE_PROBE_OK', args.out, flush=True)
    wrapper.close()
    app.close(exit_code=0)
except SystemExit:
    raise
except BaseException as exc:
    traceback.print_exc()
    if propulsion_started:
        rows = locals().get('landing_trace', [])
        if rows and all(set(row) == set(rows[0]) for row in rows):
            with propulsion_paths['partial'].open('xb') as stream:
                np.savez_compressed(stream, **{name: np.stack([row[name] for row in rows]) for name in rows[0]})
        with propulsion_paths['failure'].open('x', encoding='utf-8') as stream:
            json.dump({'status': 'failed', 'error': repr(exc), 'traceback': traceback.format_exc(),
                       'captured_samples': len(rows),
                       'physics_step_count': live.sim.get_physics_step_count() if 'live' in locals() else None},
                      stream, indent=2)
    if calibration_started and not paths['failure'].exists():
        with paths['failure'].open('x', encoding='utf-8') as stream:
            json.dump({'status': 'startup_or_shutdown_failure', 'error': repr(exc),
                       'traceback': traceback.format_exc()}, stream, indent=2)
    app.close(exit_code=1)
    raise
