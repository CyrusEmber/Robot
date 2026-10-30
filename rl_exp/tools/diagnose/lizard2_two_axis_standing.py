# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Compare zero-target, loaded standing for the v6 and isolated double-axis candidate."""
import argparse
import json
from pathlib import Path
import sys
import math
import traceback


def tiprise_target(samples, elapsed):
    """Return phase, alpha and linearly interpolated full joint targets [rad, s]."""
    phase = ('settle' if elapsed < 4. else 'rise' if elapsed < 6. else
             'hold' if elapsed < 7. else 'fall' if elapsed < 9. else 'recovery')
    alpha = max(0., min((elapsed - 4.) / 2., 1., (9. - elapsed) / 2.))
    index = min(int(alpha * 10), 9)
    weight = alpha * 10 - index
    low, high = samples[index]['q_rad'], samples[index + 1]['q_rad']
    return phase, alpha, {name: value + weight * (high[name] - value)
                          for name, value in low.items()}

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate_usd', type=Path)
parser.add_argument('--tiprise_geometry', type=Path, help='opt-in 10 s free-root geometry-target trial')
parser.add_argument('--candidate_urdf', type=Path, help='optional explicit geometry URDF identity check')
parser.add_argument('--lateral_kp', type=float, default=None)
parser.add_argument('--lateral_kd', type=float, default=None)
parser.add_argument('--test_joint', default=None)
parser.add_argument('--test_target', type=float, default=0.15)
parser.add_argument('--sweep', action='store_true', help='paired +/- test of every joint, plus zero control')
parser.add_argument('--feet_sweep', action='store_true', help='control plus +/- added axes only (9 envs)')
parser.add_argument('--ramp_s', type=float, default=1., help='feet sweep ramp [s]')
parser.add_argument('--settle_s', type=float, default=4., help='feet sweep settling [s]')
parser.add_argument('--safety_checks', action='store_true', help='stop all envs on pre-reset safety violation')
parser.add_argument('--no_gravity', action='store_true', help='unloaded comparison above the floor')
parser.add_argument('--duration', type=float, default=None, help='duration [s]; default 2 or 4 seconds')
parser.add_argument('--out', type=Path, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.out.exists():
    parser.error('output exists')
if args.feet_sweep and (args.sweep or args.test_joint or not args.candidate_usd):
    parser.error('--feet_sweep requires candidate and excludes sweep/test_joint')
if not 0 < args.ramp_s < float('inf') or not 0 <= args.settle_s < float('inf'):
    parser.error('ramp_s must be positive finite; settle_s nonnegative finite')
if args.feet_sweep and not 0 < args.test_target <= .05:
    parser.error('--feet_sweep requires 0 < test_target <= .05 rad')
if args.candidate_urdf and not args.tiprise_geometry:
    parser.error('--candidate_urdf requires --tiprise_geometry')
if args.tiprise_geometry and (not args.candidate_usd or args.sweep or args.feet_sweep
                              or args.test_joint or args.no_gravity
                              or args.duration not in (None, 10.)):
    parser.error('--tiprise_geometry requires candidate, gravity, one env and duration 10; excludes sweeps/test_joint')
app = AppLauncher(args).app
try:
    import gymnasium as gym
    import torch
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    import rl_exp.tasks  # noqa: F401
    from ablation_harness.components.dr_controller import apply_eval_mode
    from rl_exp.tools.runrecord.binding import git_rev, sha256_file
    from ablation_harness.host_paths import isaac_root
    from rl_exp.tools.diagnose.lizard2_support_sweep_report import safety_failures, json_finite

    diagnostic = args.safety_checks or args.feet_sweep or bool(args.tiprise_geometry)
    geometry_report = None
    if args.tiprise_geometry:
        geometry_path = args.tiprise_geometry.resolve()
        geometry_report = json.loads(geometry_path.read_text(encoding='utf-8'))
        geometry_hash = sha256_file(geometry_path)
        urdf = Path(geometry_report['urdf']).resolve()
        bindings = geometry_report['bindings_sha256']
        if (not geometry_report['passed'] or len(geometry_report['samples']) != 11
                or bindings[str(urdf)] != sha256_file(urdf)
                or (args.candidate_urdf and sha256_file(args.candidate_urdf) != sha256_file(urdf))):
            raise ValueError('tiprise geometry/URDF identity mismatch or incomplete geometry')
        q0 = geometry_report['initial_q_rad']
        for index, sample in enumerate(geometry_report['samples']):
            if (not sample['passed'] or set(sample['q_rad']) != set(q0)
                    or not all(math.isfinite(v) for v in sample['q_rad'].values())
                    or not math.isclose(sample['root_rise_m'], .002 * index, abs_tol=1e-9)):
                raise ValueError('invalid tiprise node')
        if not all(math.isfinite(v) for v in q0.values()):
            raise ValueError('nonfinite initial q')
    spec = gym.spec('Lizard2-Flat-Play-v6')
    cfg = resolve_presets(string_to_callable(spec.kwargs['env_cfg_entry_point'])())
    cfg.scene.num_envs, cfg.seed = (69 if args.sweep else 9 if args.feet_sweep else 1), 123
    apply_eval_mode(cfg, 'nominal')
    if diagnostic:
        cfg.scene.robot.spawn.articulation_props.enabled_self_collisions = False
    if args.no_gravity:
        cfg.scene.robot.spawn.rigid_props.disable_gravity = True
        cfg.scene.robot.init_state.pos = (0., 0., 2.)
    added = [f'{leg}_{tip}_lateral_joint' for leg, tip in
             [('lf', 'wrist'), ('rf', 'wrist'), ('rl', 'ankle'), ('rr', 'ankle')]]
    if args.candidate_usd:
        source = args.candidate_usd.resolve()
        if not source.is_relative_to((ROOT / 'rl_exp/out').resolve()):
            raise ValueError('candidate must be isolated under rl_exp/out')
        cfg.scene.robot.spawn.usd_path = str(source)
        feet = cfg.scene.robot.actuators['feet']
        for joint, source_joint in zip(added, ['lf_wrist_joint','rf_wrist_joint','rl_ankle_joint','rr_ankle_joint']):
            feet.joint_names_expr.append(joint)
            for attr in ('stiffness', 'damping', 'effort_limit', 'effort_limit_sim',
                         'velocity_limit', 'velocity_limit_sim'):
                getattr(feet, attr)[joint] = getattr(feet, attr)[source_joint]
            if args.lateral_kp is not None:
                feet.stiffness[joint] = args.lateral_kp
            if args.lateral_kd is not None:
                feet.damping[joint] = args.lateral_kd
            term = cfg.actions.joint_pos_legs
            term.joint_names.append(joint)
            term.scale[joint] = term.scale[source_joint]
            term.clip[joint] = term.clip[source_joint]
    if geometry_report is not None:
        cfg.scene.robot.init_state.joint_pos = dict(q0)
        cfg.scene.robot.init_state.joint_vel = dict.fromkeys(q0, 0.)
        cfg.scene.robot.init_state.pos = tuple(geometry_report['samples'][0]['root_position_world_m'])
        cfg.scene.robot.init_state.rot = (0., 0., 0., 1.)  # This fork uses xyzw.
        cfg.scene.robot.init_state.lin_vel = (0., 0., 0.)
        cfg.scene.robot.init_state.ang_vel = (0., 0., 0.)
        cfg.scene.robot.spawn.articulation_props.fix_root_link = False
    env = gym.make('Lizard2-Flat-Play-v6', cfg=cfg)
    live = env.unwrapped
    env.reset()
    robot, sensor = live.scene['robot'], live.scene['contact_forces']
    names = robot.joint_names
    expected = 34 if args.candidate_usd else 30
    assert len(names) == expected
    failures = []
    if diagnostic:
        import omni.usd
        from pxr import PhysxSchema
        stage = omni.usd.get_context().get_stage()
        articulation_prims = [prim for prim in stage.Traverse()
                              if str(prim.GetPath()).startswith('/World/envs/env_')
                              and '/Robot' in str(prim.GetPath())
                              and prim.HasAPI(PhysxSchema.PhysxArticulationAPI)]
        enabled = [PhysxSchema.PhysxArticulationAPI(prim).GetEnabledSelfCollisionsAttr().Get()
                   for prim in articulation_prims]
        if len(enabled) != cfg.scene.num_envs or any(value is not False for value in enabled):
            raise RuntimeError(f'loaded-stage self collision must be false for every env: {enabled}')
        hard_limits = robot.data.joint_pos_limits.torch.cpu().tolist()
        foot_names = [f'{leg}_{tip}{suffix}_joint' for leg, tip in
                      [('lf', 'wrist'), ('rf', 'wrist'), ('rl', 'ankle'), ('rr', 'ankle')]
                      for suffix in ('', '_lateral') if f'{leg}_{tip}{suffix}_joint' in names]
        foot_ids = [names.index(name) for name in foot_names]
        assert len(foot_ids) == (8 if args.candidate_usd else 4)
    class SafetyStop(Exception):
        pass
    rows = []
    original = live.termination_manager.compute
    step = 0
    def capture():
        dones = original()
        forces = sensor.data.net_forces_w_history.torch.norm(dim=-1).amax(dim=1)
        if args.sweep or diagnostic:
            rows.append({'step': step, 'done': dones.cpu().tolist(),
                         'base_contact': live.termination_manager.get_term('base_contact').cpu().tolist(),
                         'root_position': robot.data.root_pos_w.torch.cpu().tolist(),
                         'gravity_b': robot.data.projected_gravity_b.torch.cpu().tolist(),
                         'joint_positions': robot.data.joint_pos.torch.cpu().tolist(),
                         'joint_targets': robot.data.joint_pos_target.torch.cpu().tolist(),
                         'forces_N': forces.cpu().tolist()})
            if diagnostic:
                rows[-1].update(
                    joint_velocities=robot.data.joint_vel.torch.cpu().tolist(),
                    root_velocity=robot.data.root_vel_w.torch.cpu().tolist(),
                    raw_action=live.action_manager.action.cpu().tolist(),
                    processed_targets={key: live.action_manager.get_term(key).processed_actions.cpu().tolist()
                                       for key in live.action_manager.active_terms})
                if geometry_report is not None:
                    rows[-1].update(
                        requested_phase=requested_phase, requested_alpha=requested_alpha,
                        requested_q_rad=requested_q,
                        root_quaternion_xyzw=robot.data.root_quat_w.torch.cpu().tolist())
                    for key, term, offset in tiprise_terms:
                        target = torch.tensor([[requested_q[n] for n in term._joint_names]], device=live.device)
                        if not torch.allclose(term.processed_actions, target, atol=1e-6, rtol=0.):
                            failures.append({'env': 0, 'reason': 'processed_target_mismatch', 'term': key})
                failures.extend(safety_failures(rows[-1], hard_limits, foot_ids))
                if failures:
                    raise SafetyStop()  # Before env.step reaches auto-reset; raw row already retained.
            return dones
        forces = forces[0]
        rows.append({'step': step, 'done': bool(dones[0]),
                     'base_contact': bool(live.termination_manager.get_term('base_contact')[0]),
                     'root_position': robot.data.root_pos_w.torch[0].cpu().tolist(),
                     'gravity_b': robot.data.projected_gravity_b.torch[0].cpu().tolist(),
                     'joint_positions': robot.data.joint_pos.torch[0].cpu().tolist(),
                     'joint_targets': robot.data.joint_pos_target.torch[0].cpu().tolist(),
                     'forces_N': forces.cpu().tolist()})
        return dones
    live.termination_manager.compute = capture
    action = torch.zeros((cfg.scene.num_envs, live.action_manager.total_action_dim), device=live.device)
    sweep_cases = []
    tiprise_terms = []
    if geometry_report is not None:
        if set(names) != set(q0):
            raise ValueError('geometry does not cover every loaded joint')
        offset = 0
        mapped = []
        from isaaclab.envs.mdp.actions.joint_actions import JointPositionAction
        for key in live.action_manager.active_terms:
            term = live.action_manager.get_term(key)
            if type(term) is not JointPositionAction:
                raise ValueError('tiprise requires absolute joint-position action terms')
            tiprise_terms.append((key, term, offset))
            mapped.extend(term._joint_names)
            offset += term.action_dim
            # Preflight all endpoints: affine interpolation cannot exceed endpoint bounds.
            for node in [q0] + [sample['q_rad'] for sample in geometry_report['samples']]:
                target = torch.tensor([[node[n] for n in term._joint_names]], device=live.device)
                raw = (target - term._offset) / term._scale
                if not torch.isfinite(raw).all():
                    raise ValueError(f'invalid scale/offset for {key}')
                if term.cfg.clip is not None and (
                        (target < term._clip[..., 0]).any() or (target > term._clip[..., 1]).any()):
                    raise ValueError(f'tiprise target would be clipped: {key}')
        if sorted(mapped) != sorted(names) or offset != live.action_manager.total_action_dim:
            raise ValueError('tiprise requires every joint mapped exactly once')
    if args.sweep or args.feet_sweep:
        assert args.candidate_usd and not args.test_joint and args.test_target > 0
        offset = 0
        for term_name in live.action_manager.active_terms:
            term = live.action_manager.get_term(term_name)
            group_cfg = getattr(cfg.actions, term_name)
            for i, joint in enumerate(term._joint_names):
                if args.feet_sweep and joint not in added:
                    continue
                for sign in (-1, 1):
                    sweep_cases.append({'joint': joint, 'sign': sign,
                                        'action_index': offset + i, 'scale': group_cfg.scale[joint]})
            offset += len(term._joint_names)
        assert len(sweep_cases) == (8 if args.feet_sweep else 68) and offset == 34
    if args.test_joint:
        term = live.action_manager.get_term('joint_pos_legs')
        if args.test_joint not in term._joint_names or live.action_manager.active_terms[0] != 'joint_pos_legs':
            raise ValueError('test joint not in first leg action term')
        command_index = term._joint_names.index(args.test_joint)
        scale = cfg.actions.joint_pos_legs.scale[args.test_joint]
    duration = 10. if geometry_report is not None else args.duration
    duration = duration if duration is not None else (9. if args.feet_sweep else
                4. if args.test_joint or args.sweep else 2.)
    if not 2. <= duration < cfg.episode_length_s:
        raise ValueError('duration must be >= 2 seconds and below the episode length')
    if args.feet_sweep and duration <= args.settle_s + args.ramp_s:
        raise ValueError('feet sweep duration must leave a post-ramp observation window')
    try:
        for step in range(1, round(duration / live.step_dt) + 1):
            live.command_manager.get_term('base_velocity').vel_command_b[:] = 0.
            if geometry_report is not None:
                requested_phase, requested_alpha, requested_q = tiprise_target(
                    geometry_report['samples'], (step - 1) * live.step_dt)
                for key, term, offset in tiprise_terms:
                    target = torch.tensor([[requested_q[n] for n in term._joint_names]], device=live.device)
                    action[:, offset:offset + term.action_dim] = (target - term._offset) / term._scale
            if args.feet_sweep:
                elapsed = (step - 1) * live.step_dt - args.settle_s
                fraction = max(0., min(elapsed / args.ramp_s, 1.,
                                       (2 * args.ramp_s + 1. - elapsed) / args.ramp_s))
                for i, case in enumerate(sweep_cases, start=1):
                    action[i, case['action_index']] = case['sign'] * args.test_target * fraction / case['scale']
            if args.sweep and step > 100:
                fraction = min((step - 100) / 25., 1.)
                for i, case in enumerate(sweep_cases, start=1):
                    action[i, case['action_index']] = case['sign'] * args.test_target * fraction / case['scale']
            if args.test_joint and step > 100:
                action[0, command_index] = args.test_target * min((step - 100) / 25., 1.) / scale
            env.step(action)
            if not args.sweep and not diagnostic and rows[-1]['done']:
                break
    except SafetyStop:
        pass
    result = {'usd': cfg.scene.robot.spawn.usd_path,
              'usd_sha256': sha256_file(Path(cfg.scene.robot.spawn.usd_path)),
              'joint_names': names, 'sensor_body_names': sensor.body_names,
              'dt_s': live.step_dt, 'case': 'candidate' if args.candidate_usd else 'v6',
              'joint_stiffness': robot.data.joint_stiffness.torch[0].cpu().tolist(),
              'joint_damping': robot.data.joint_damping.torch[0].cpu().tolist(),
              'joint_effort_limits': robot.data.joint_effort_limits.torch[0].cpu().tolist(),
              'test_joint': args.test_joint, 'test_target': args.test_target if args.test_joint else None,
              'sweep_cases': sweep_cases, 'sweep_target': args.test_target if args.sweep else None,
              'no_gravity': args.no_gravity,
              'gains': 'v6 gains; added axes diagnostic overrides when supplied', 'rows': rows}
    if diagnostic:
        result.update(
            safety_failures=failures, trial_status='failed' if failures else 'completed',
            runtime_self_collisions=enabled,
            self_collision_readback='loaded USD stage PhysxArticulationAPI; backend getter unavailable',
            joint_position_limits=hard_limits,
            joint_velocity_limits=robot.data.joint_vel_limits.torch.cpu().tolist(),
            actual_torque='unavailable; not reconstructed from Kp*error',
            physics_dt_s=cfg.sim.dt, decimation=cfg.decimation,
            feet_sweep=args.feet_sweep, ramp_s=args.ramp_s, settle_s=args.settle_s,
            duration_s=duration, foot_joint_names=foot_names,
            sweep_target=args.test_target if args.sweep or args.feet_sweep else None,
            repo_rev=git_rev(ROOT), isaaclab_rev=git_rev(isaac_root()),
            source_sha256={str(path.relative_to(ROOT)): sha256_file(path) for path in
                           (Path(__file__), ROOT / 'rl_exp/tools/diagnose/lizard2_support_sweep_report.py')},
            force_observation='Per-body maximum net-force norm over sensor history at each control step; '
                              'not ground-only, not contact-pair classification; may miss peaks outside history.')
    if geometry_report is not None:
        result['tiprise'] = {
            'geometry_path': str(geometry_path), 'geometry_sha256': geometry_hash,
            'geometry_report': geometry_report,
            'urdf': str(urdf), 'urdf_sha256': sha256_file(urdf),
            'candidate_urdf': str(args.candidate_urdf.resolve()) if args.candidate_urdf else None,
            'initial_q_rad': q0, 'initial_root_position_m': list(cfg.scene.robot.init_state.pos),
            'initial_root_quaternion_xyzw': list(cfg.scene.robot.init_state.rot),
            'phase_durations_s': dict(settle=4., rise=2., hold=1., fall=2., recovery=1.),
            'action_joint_names': {key: term._joint_names for key, term, _ in tiprise_terms},
            'root_control': 'free root; initialization/reset only; no trajectory root writes or fixtures',
            'asset_identity_scope': 'USD file hash and geometry URDF hash recorded separately; '
                                    'not a USD-versus-URDF equivalence certificate',
            'contact_region_validated': False,
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(json_finite(result) if diagnostic else result,
                                indent=2, allow_nan=False))
    print('STANDING_RECORD_FAILED' if failures else 'STANDING_RECORD_OK',
          args.out, 'steps', len(rows), flush=True)
    env.close(); app.close(exit_code=1 if failures else 0)
    if failures:
        raise SystemExit(1)
except SystemExit:
    raise
except BaseException:
    traceback.print_exc()
    app.close(exit_code=1)
    raise
