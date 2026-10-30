# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Compare zero-target, loaded standing for the v6 and isolated double-axis candidate."""
import argparse
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate_usd', type=Path)
parser.add_argument('--lateral_kp', type=float, default=None)
parser.add_argument('--lateral_kd', type=float, default=None)
parser.add_argument('--test_joint', default=None)
parser.add_argument('--test_target', type=float, default=0.15)
parser.add_argument('--sweep', action='store_true', help='paired +/- test of every joint, plus zero control')
parser.add_argument('--no_gravity', action='store_true', help='unloaded comparison above the floor')
parser.add_argument('--duration', type=float, default=None, help='duration [s]; default 2 or 4 seconds')
parser.add_argument('--out', type=Path, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.out.exists():
    parser.error('output exists')
app = AppLauncher(args).app
try:
    import gymnasium as gym
    import torch
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    import rl_exp.tasks  # noqa: F401
    from ablation_harness.components.dr_controller import apply_eval_mode
    from rl_exp.tools.runrecord.binding import sha256_file

    spec = gym.spec('Lizard2-Flat-Play-v6')
    cfg = resolve_presets(string_to_callable(spec.kwargs['env_cfg_entry_point'])())
    cfg.scene.num_envs, cfg.seed = (69 if args.sweep else 1), 123
    apply_eval_mode(cfg, 'nominal')
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
    env = gym.make('Lizard2-Flat-Play-v6', cfg=cfg)
    live = env.unwrapped
    env.reset()
    robot, sensor = live.scene['robot'], live.scene['contact_forces']
    names = robot.joint_names
    expected = 34 if args.candidate_usd else 30
    assert len(names) == expected
    rows = []
    original = live.termination_manager.compute
    step = 0
    def capture():
        dones = original()
        forces = sensor.data.net_forces_w_history.torch.norm(dim=-1).amax(dim=1)
        if args.sweep:
            rows.append({'step': step, 'done': dones.cpu().tolist(),
                         'base_contact': live.termination_manager.get_term('base_contact').cpu().tolist(),
                         'root_position': robot.data.root_pos_w.torch.cpu().tolist(),
                         'gravity_b': robot.data.projected_gravity_b.torch.cpu().tolist(),
                         'joint_positions': robot.data.joint_pos.torch.cpu().tolist(),
                         'joint_targets': robot.data.joint_pos_target.torch.cpu().tolist(),
                         'forces_N': forces.cpu().tolist()})
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
    if args.sweep:
        assert args.candidate_usd and not args.test_joint and args.test_target > 0
        offset = 0
        for term_name in live.action_manager.active_terms:
            term = live.action_manager.get_term(term_name)
            group_cfg = getattr(cfg.actions, term_name)
            for i, joint in enumerate(term._joint_names):
                for sign in (-1, 1):
                    sweep_cases.append({'joint': joint, 'sign': sign,
                                        'action_index': offset + i, 'scale': group_cfg.scale[joint]})
            offset += len(term._joint_names)
        assert len(sweep_cases) == 68 and offset == 34
    if args.test_joint:
        term = live.action_manager.get_term('joint_pos_legs')
        if args.test_joint not in term._joint_names or live.action_manager.active_terms[0] != 'joint_pos_legs':
            raise ValueError('test joint not in first leg action term')
        command_index = term._joint_names.index(args.test_joint)
        scale = cfg.actions.joint_pos_legs.scale[args.test_joint]
    duration = args.duration if args.duration is not None else (4. if args.test_joint or args.sweep else 2.)
    if not 2. <= duration < cfg.episode_length_s:
        raise ValueError('duration must be >= 2 seconds and below the episode length')
    for step in range(1, round(duration / live.step_dt) + 1):
        live.command_manager.get_term('base_velocity').vel_command_b[:] = 0.
        if args.sweep and step > 100:
            fraction = min((step - 100) / 25., 1.)
            for i, case in enumerate(sweep_cases, start=1):
                action[i, case['action_index']] = case['sign'] * args.test_target * fraction / case['scale']
        if args.test_joint and step > 100:
            action[0, command_index] = args.test_target * min((step - 100) / 25., 1.) / scale
        env.step(action)
        if not args.sweep and rows[-1]['done']:
            break
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
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print('STANDING_RECORD_OK', args.out, 'steps', len(rows), flush=True)
    env.close(); app.close(exit_code=0)
except BaseException:
    traceback.print_exc()
    app.close(exit_code=1)
    raise
