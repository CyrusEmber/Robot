# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Compare a fixed policy against zero actions and capture native belly-triggered resets.

Run with the final v5 checkpoint and --task Lizard2-Flat-Play-v6 --viz none.
The same command with the v5 task is the failing control: its base-only selector
allows chest support. This checks reset wiring, not learned locomotion quality.
Outputs JSON under the caller's --out path; starts no training and writes no weights.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


def probe(args) -> dict:
    """Capture contacts before automatic reset overwrites the terminal frame [N, s]."""
    import gymnasium as gym
    import importlib.metadata
    import torch
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg
    from rsl_rl.runners import OnPolicyRunner

    import rl_exp.tasks  # noqa: F401
    from ablation_harness.components.dr_controller import apply_eval_mode
    from ablation_harness.record import checkpoint_digest

    spec = gym.spec(args.task)
    cfg = resolve_presets(string_to_callable(spec.kwargs['env_cfg_entry_point'])())
    cfg.scene.num_envs, cfg.seed = 2, args.seed
    cfg.episode_length_s = max(20., args.seconds + 1.)
    apply_eval_mode(cfg, 'nominal')
    agent = handle_deprecated_rsl_rl_cfg(
        string_to_callable(spec.kwargs['rsl_rl_cfg_entry_point'])(),
        importlib.metadata.version('rsl-rl-lib'))
    env = gym.make(args.task, cfg=cfg)
    wrapper = None
    try:
        wrapper = RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions)
        live = env.unwrapped
        runner = OnPolicyRunner(wrapper, agent.to_dict(), log_dir=None, device=live.device)
        runner.load(args.checkpoint)
        policy = runner.get_inference_policy(device=live.device)
        obs = wrapper.get_observations()
        robot, sensor = live.scene['robot'], live.scene['contact_forces']
        body_names = sensor.body_names
        root_id, chest_id = body_names.index('base_link'), body_names.index('chest_pitch')
        monitored = live.termination_manager.get_term_cfg('base_contact').params['sensor_cfg']
        threshold = live.termination_manager.get_term_cfg('base_contact').params['threshold']
        events, reset_counts, peak_chest = [], [0, 0], [0., 0.]
        step = 0
        original_compute = live.termination_manager.compute

        def capture():
            dones = original_compute()
            forces = torch.linalg.vector_norm(sensor.data.net_forces_w_history.torch, dim=-1).amax(dim=1)
            for index in range(2):
                peak_chest[index] = max(peak_chest[index], float(forces[index, chest_id]))
            for index in dones.nonzero(as_tuple=True)[0].tolist():
                events.append(dict(
                    step=step, time_s=round(step*live.step_dt, 4),
                    case=('policy', 'zero_action')[index],
                    root_force_N=float(forces[index, root_id]),
                    chest_force_N=float(forces[index, chest_id]),
                    base_contact=bool(live.termination_manager.get_term('base_contact')[index]),
                    head_contact=bool(live.termination_manager.get_term('head_ground_contact')[index]),
                    time_out=bool(live.termination_manager.get_term('time_out')[index])))
            return dones

        live.termination_manager.compute = capture
        try:
            command = live.command_manager.get_term('base_velocity')
            target = torch.tensor([1.5, 0., 0.], device=live.device)
            for step in range(1, round(args.seconds/live.step_dt)+1):
                command.vel_command_b[:] = target
                with torch.no_grad():
                    actions = policy(obs)
                    actions[1].zero_()
                    obs, _, dones, _ = wrapper.step(actions)
                for index in range(2):
                    reset_counts[index] += int(dones[index])
        finally:
            live.termination_manager.compute = original_compute
        final_forces = torch.linalg.vector_norm(sensor.data.net_forces_w.torch[1], dim=-1)
        feet = ('lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle')
        zero_feet = {name: float(final_forces[body_names.index(name)]) for name in feet}
        policy_events = [event for event in events if event['case'] == 'policy']
        first = policy_events[0] if policy_events else None
        passed = (reset_counts[0] > 0 and reset_counts[1] == 0 and first['base_contact']
                  and first['chest_force_N'] > threshold and first['root_force_N'] <= threshold
                  and not first['head_contact'] and not first['time_out']
                  and all(force > threshold for force in zero_feet.values()))
        return dict(task=args.task, seed=args.seed, seconds=args.seconds, command_mps=1.5,
                    checkpoint=checkpoint_digest(args.checkpoint),
                    monitored_bodies=monitored.body_names, threshold_N=threshold,
                    reset_counts=dict(policy=reset_counts[0], zero_action=reset_counts[1]),
                    peak_chest_force_N=dict(policy=peak_chest[0], zero_action=peak_chest[1]),
                    first_policy_reset=first, events=events, zero_final_foot_forces_N=zero_feet,
                    zero_final_gravity_b=robot.data.projected_gravity_b.torch[1].cpu().tolist(),
                    passed=bool(passed))
    finally:
        (wrapper if wrapper is not None else env).close()


def main() -> int:
    from isaaclab.app import AppLauncher

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', default='Lizard2-Flat-Play-v6',
                        choices=['Lizard2-Flat-Play-v5', 'Lizard2-Flat-Play-v6'])
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--seconds', type=float, default=3.)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--out', type=Path, required=True)
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if not 1. <= args.seconds <= 10.:
        parser.error('--seconds must be between 1 and 10')
    if args.out.exists():
        parser.error('--out must be a new report path')
    app = AppLauncher(args).app
    report = dict(task=args.task, passed=False)
    try:
        report = probe(args)
    except BaseException as error:
        report['error'] = repr(error)
        traceback.print_exc()
    finally:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print(json.dumps(report), flush=True)
        print('BELLY_RESET_PROBE_OK' if report['passed'] else 'BELLY_RESET_PROBE_FAILED', flush=True)
        app.close(exit_code=0 if report['passed'] else 1)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
