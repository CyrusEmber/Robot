# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Record three named policy diagnostics, not a frozen evaluation protocol.

Run once with --out pointing at a new directory. This historical diagnostic requires the
2026-11-04_16-12-57 v7 checkpoint at CHECKPOINT. The parent records the child command,
checkpoint digests and exit status; one Isaac child records all three scenarios.
Video frame i is the state rendered after control step i, at video time i/fps.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
CHECKPOINT = Path('E:/IsaacLab/logs/rsl_rl/lizard2_v7/2026-11-04_16-12-57/model_0.pt')
EXPECTED_SHA = '94cd4fb180cfd1918e9f08e51920bfaa6aefffdba6a2a3312ff517febc16edde'
TASK = 'Lizard2-Flat-Play-v7'
SCENARIOS = ('turn', 'stop', 'push')


def now():
    return datetime.datetime.now().astimezone().isoformat()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def check_command(obs, expected):
    if len(obs) != 3 or any(not math.isfinite(a) or abs(a-b) > 1e-6 for a, b in zip(obs, expected)):
        raise ValueError(f'policy command differs from intended command: {obs} != {expected}')


def self_check():
    # A stale policy observation must fail, including immediately at the stop transition.
    check_command([1, 0, .5], [1, 0, .5])
    check_command([0, 0, 0], [0, 0, 0])
    try:
        check_command([1, 0, 0], [0, 0, 0])
    except ValueError:
        pass
    else:
        raise AssertionError('stale command was accepted')
    # A terminal sample belongs to the first episode, subsequent samples do not.
    valid = True
    rows = []
    for done in (False, True, False):
        rows.append(valid)
        valid = valid and not done
    assert rows == [True, True, False]
    print('SELF_CHECK_OK', flush=True)


def record_scenario(name, out):
    import gymnasium as gym
    import imageio
    import torch
    from isaaclab.utils.math import euler_xyz_from_quat
    from isaaclab.utils.string import string_to_callable
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg
    from isaaclab_tasks.utils.hydra import resolve_presets
    from isaaclab_physx.renderers.kit_viewport_utils import set_kit_renderer_camera_view
    from rsl_rl.runners import OnPolicyRunner
    import rl_exp.tasks  # noqa: F401
    from ablation_harness.components.dr_controller import apply_eval_mode
    from ablation_harness.components.recovery import apply_kick, make_kick_directions
    from ablation_harness.video_matrix import DEFAULT_CAMERA_PRIM, DEFAULT_EYE, follow_view

    spec = gym.spec(TASK)
    cfg = resolve_presets(string_to_callable(spec.kwargs['env_cfg_entry_point'])())
    cfg.scene.num_envs, cfg.seed = 1, 0
    cfg.episode_length_s = 20.0
    cfg.curriculum.terrain_levels = None
    apply_eval_mode(cfg, 'nominal')
    agent = handle_deprecated_rsl_rl_cfg(
        string_to_callable(spec.kwargs['rsl_rl_cfg_entry_point'])(),
        importlib.metadata.version('rsl-rl-lib'))
    env = gym.make(TASK, cfg=cfg, render_mode='rgb_array')
    wrapper = None
    try:
        wrapper = RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions)
        live = env.unwrapped
        robot = live.scene['robot']
        term = live.command_manager.get_term('base_velocity')
        manager = live.observation_manager
        names = manager.active_terms['policy']
        dims = manager.group_obs_term_dim['policy']
        idx = names.index('velocity_commands')
        if dims[idx] != (3,) or any(len(d) != 1 for d in dims[:idx]):
            raise RuntimeError(f'unsupported observation term dimensions: {dims}')
        offset = sum(d[0] for d in dims[:idx])
        runner = OnPolicyRunner(wrapper, agent.to_dict(), log_dir=None, device=live.device)
        runner.load(str(CHECKPOINT))
        policy = runner.get_inference_policy(device=live.device)
        yaw = float(euler_xyz_from_quat(robot.data.root_quat_w.torch)[2][0])
        dt = float(live.step_dt)
        fps = round(1 / dt)
        if abs(fps * dt - 1) > 1e-6:
            raise RuntimeError('video fps cannot exactly represent control step')
        count = round(3.0 / dt)
        switch = round(.3 / dt)
        direction = make_kick_directions(1, 0, live.device)
        vec = lambda x: x.detach().cpu().tolist()
        def snapshot():
            return dict(root_pos_w=vec(robot.data.root_pos_w.torch[0]),
                        root_quat_w=vec(robot.data.root_quat_w.torch[0]),
                        lin_vel_b=vec(robot.data.root_lin_vel_b.torch[0]),
                        ang_vel_b=vec(robot.data.root_ang_vel_b.torch[0]),
                        lin_vel_w=vec(robot.data.root_lin_vel_w.torch[0]))
        terminal = {}
        original_reset = live._reset_idx
        def capture_reset(ids):
            terminal['motion_pre_reset'] = snapshot()
            terminal['termination_terms'] = {
                n: bool(live.termination_manager.get_term(n)[0])
                for n in live.termination_manager.active_terms}
            original_reset(ids)
        live._reset_idx = capture_reset
        capture = getattr(live.video_recorder, '_capture', None)
        camera = getattr(getattr(capture, 'cfg', None), 'camera_prim_path', DEFAULT_CAMERA_PRIM)
        meta = dict(scenario=name, task=TASK, seed=0, mode='nominal', num_envs=1,
                    step_dt_s=dt, fps=fps, frames_expected=count, command_offset=offset,
                    observation_terms=names, observation_term_dims=dims,
                    command_schedule=('vx=1 vy=0 wz=+0.5' if name == 'turn' else
                                      'vx=1 vy=0 wz=0; stop at 0.3 s' if name == 'stop' else
                                      'vx=1 vy=0 wz=0; kick at 0.3 s'),
                    kick_mps=4.0 if name == 'push' else None,
                    kick_direction_world=vec(direction[0]) if name == 'push' else None,
                    camera_prim=camera, reset_events=str(cfg.events),
                    video_time_definition='frame index / fps; frame after step, reset frames show respawn',
                    notes='Illustrative only; early stop/push differs from frozen protocol; '
                          'post-reset frames and steps are not first-episode samples.')
        save(out / f'{name}_conditions.json', meta)
        first_done = None
        resets = 0
        writer = imageio.get_writer(out / f'{name}.mp4', fps=fps)
        try:
            with (out / f'{name}_steps.jsonl').open('w', encoding='utf-8', buffering=1) as data:
                for step in range(count):
                    target = [1., 0., .5 if name == 'turn' else 0.]
                    if name == 'stop' and step >= switch:
                        target = [0., 0., 0.]
                    manager_before_set = vec(live.command_manager.get_command('base_velocity')[0])
                    term.vel_command_b[:] = torch.tensor(target, device=live.device)
                    manager_before = vec(live.command_manager.get_command('base_velocity')[0])
                    # Recompute observation after injection; previous step's obs is stale at transitions.
                    obs = wrapper.get_observations()
                    policy_cmd = vec(obs['policy'][0, offset:offset + 3])
                    check_command(policy_cmd, target)
                    pre = snapshot()
                    kicked = name == 'push' and step == switch
                    if kicked:
                        apply_kick(robot, 4.0, direction)
                    terminal.clear()
                    with torch.inference_mode():
                        action = policy(obs)
                        _, _, dones, _ = wrapper.step(action)
                    done = bool(dones[0])
                    after = vec(live.command_manager.get_command('base_velocity')[0])
                    post = snapshot()
                    if done and not terminal:
                        raise RuntimeError('done without pre-reset capture')
                    if done:
                        resets += 1
                        if first_done is None:
                            first_done = step
                    eye, lookat = follow_view(robot.data.root_pos_w.torch[0], yaw, DEFAULT_EYE, (0., 0., .2))
                    live.video_recorder.cfg.eye, live.video_recorder.cfg.lookat = eye, lookat
                    set_kit_renderer_camera_view(eye=list(eye), target=list(lookat), camera_prim_path=camera)
                    frame = env.render()
                    if frame is None:
                        raise RuntimeError('no camera frame')
                    writer.append_data(frame)
                    row = dict(step=step, control_time_before_s=step*dt,
                               control_time_after_s=(step+1)*dt, video_time_s=step/fps,
                               target_command=target, manager_before_set=manager_before_set,
                               manager_before_policy=manager_before, policy_obs_command=policy_cmd,
                               manager_after_step=after, motion_before=pre, motion_after_step=post,
                               kick_applied=kicked, done=done, reset_index=resets,
                               first_episode_sample=first_done is None or first_done == step,
                               terminal_pre_reset=dict(terminal) if done else None)
                    data.write(json.dumps(row, allow_nan=False) + '\n')
        finally:
            writer.close()
            live._reset_idx = original_reset
        meta.update(frames_written=count, first_done_step=first_done,
                    first_done_control_time_s=None if first_done is None else (first_done + 1)*dt,
                    first_done_video_time_s=None if first_done is None else first_done/fps,
                    resets=resets)
        save(out / f'{name}_conditions.json', meta)
        print('SCENARIO_COMPLETE', name, json.dumps(meta), flush=True)
    finally:
        (wrapper if wrapper is not None else env).close()


def child(out):
    from isaaclab.app import AppLauncher
    parser = argparse.ArgumentParser()
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args(['--headless', '--enable_cameras'])
    app = AppLauncher(args).app
    try:
        for name in SCENARIOS:
            record_scenario(name, out)
    except BaseException:
        traceback.print_exc()
        sys.stderr.flush()
        sys.stdout.flush()
        os._exit(1)
    app.close()


def parent(out):
    out.mkdir(exist_ok=False)
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--child', '--out', str(out)]
    sha_before = digest(CHECKPOINT)
    execution = dict(command=command, cwd=str(REPO), started_at=now(),
                     checkpoint=str(CHECKPOINT), checkpoint_sha256_before=sha_before,
                     checkpoint_sha256_expected=EXPECTED_SHA, ended_at=None, exit_code=None)
    save(out / 'execution.json', execution)
    code = 1
    try:
        if sha_before != EXPECTED_SHA:
            raise RuntimeError('checkpoint SHA mismatch before launch')
        with (out / 'video.log').open('w', encoding='utf-8') as log:
            code = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT).returncode
    finally:
        execution.update(ended_at=now(), exit_code=code, checkpoint_sha256_after=digest(CHECKPOINT))
        save(out / 'execution.json', execution)
    if code != 0 or execution['checkpoint_sha256_after'] != sha_before:
        raise SystemExit('simulation failed or checkpoint changed; inspect execution.json and video.log')
    # Decode every frame with ffmpeg; extract images at named video times.
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with (out / 'ffmpeg.log').open('w', encoding='utf-8') as log:
        for name in SCENARIOS:
            clip = out / f'{name}.mp4'
            subprocess.run([ffmpeg, '-v', 'error', '-xerror', '-i', str(clip), '-f', 'null', '-'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            for t in (0., .2, .3, .4, .6, .8, 1., 1.2, 1.5, 2., 2.5, 2.98):
                image = out / f'{name}_t{t:05.2f}s.png'
                subprocess.run([ffmpeg, '-v', 'error', '-xerror', '-ss', str(t), '-i', str(clip),
                                '-frames:v', '1', '-y', str(image)],
                               stdout=log, stderr=subprocess.STDOUT, check=True)
                if not image.is_file() or image.stat().st_size == 0:
                    raise RuntimeError(f'no extracted frame at {t}s: {clip}')
    print('COMPLETE', out, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--self_check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check()
    elif args.out is None:
        parser.error('--out required')
    elif args.child:
        child(args.out.resolve())
    else:
        parent(args.out.resolve())


if __name__ == '__main__':
    main()
