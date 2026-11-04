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
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument('--checkpoint', required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--speed', type=float, default=0.5)
parser.add_argument('--seed', type=int, default=123)
parser.add_argument('--steps', type=int, default=500)
parser.add_argument('--pose_samples', action='store_true', help='save env 0 poses and USD world axes every 0.5 s')
parser.add_argument('--swing-clip', type=float, default=None,
                    help='probe-only: replace every *_swing_joint action clip with (-v, v); URDF limit still applies')
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.out.exists():
    parser.error('output already exists')
app = AppLauncher(args).app

STANCE_Z = 0.10
LEGS = {'lf': 'elbow', 'rf': 'elbow', 'rl': 'knee', 'rr': 'knee'}
FOOT = {'lf': 'wrist', 'rf': 'wrist', 'rl': 'ankle', 'rr': 'ankle'}

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
    spec = gym.spec(task)
    cfg = resolve_presets(string_to_callable(spec.kwargs['env_cfg_entry_point'])())
    cfg.scene.num_envs, cfg.seed = 4, args.seed
    cfg.episode_length_s = 20.0
    apply_eval_mode(cfg, 'nominal')
    agent = handle_deprecated_rsl_rl_cfg(string_to_callable(spec.kwargs['rsl_rl_cfg_entry_point'])(),
                                         importlib.metadata.version('rsl-rl-lib'))
    env = gym.make(task, cfg=cfg)
    wrapper = RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions)
    live = env.unwrapped
    runner = OnPolicyRunner(wrapper, agent.to_dict(), log_dir=None, device=live.device)
    runner.load(args.checkpoint)
    policy = runner.get_inference_policy(device=live.device)
    robot = live.scene['robot']
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
    resets = 0
    pos, tgt, tilt, raw = [], [], {leg: [] for leg in LEGS}, []
    obs = wrapper.get_observations()
    for step in range(args.steps):
        command.vel_command_b[:] = torch.tensor([args.speed, 0., 0.], device=live.device)
        with torch.no_grad():
            act = policy(obs)
            raw.append(act[:, :len(leg_names)].cpu().numpy())
            obs, _, done, _ = wrapper.step(act)
        resets += int(done.sum())
        assert torch.equal(leg_term.raw_actions, act[:, :len(leg_names)]), 'leg slice != action term raw input'
        d = robot.data
        pos.append(d.joint_pos.torch[:, jidx].cpu().numpy())
        tgt.append(d.joint_pos_target.torch[:, jidx].cpu().numpy())
        bp = d.body_link_pos_w.torch
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
                  reset_count=resets, pose_samples_env0=samples)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print('SHANK_USE_PROBE_OK', args.out, flush=True)
    wrapper.close()
    app.close(exit_code=0)
except BaseException:
    traceback.print_exc()
    app.close(exit_code=1)
    raise
