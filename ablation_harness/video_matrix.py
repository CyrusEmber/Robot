# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Record one short clip per (speed gear x terrain gear) cell chosen on the command line.

This is a camera, not a judge. It writes mp4 plus the conditions each clip was shot under, and
**no verdict**: the frozen protocols under ``protocols/`` keep their meaning because nothing here
scores anything, and writing a number into ``results/<protocol>/`` from a cell whose command the
recipe never samples would be a measurement claim the protocol cannot back. A cell whose speed
sits outside the recipe's command box is recorded as ``in_recipe_box: false`` so a watched clip is
never mistaken for in-distribution evidence.

Gears are free: ``--speeds 1.5,3`` x ``--terrains plane,slope_10deg,rough_b`` is six cells. The
terrain gears are the names of the frozen suite (``suites.LIZARD_SUITE_V2_NAMES``) plus ``plane``
for the recipe's own ground; a suite gear is built as a single-column board with that one
sub-terrain, so every clip faces the same geometry as every other clip of the same gear.

The command is injected every step (the same mechanism ``eval.py`` uses) and the term is frozen
first, otherwise the framework resamples it and the clip is not the speed that was asked for.

The camera follows the robot (``--follow``, on by default): ``eye``/``lookat`` are offsets from the
robot root, rotated into its spawn frame. This is not free -- the Kit capture parks its camera on
its first frame and never moves it again, so the follow is one camera-prim update per step, and it
is what makes longer clips worth shooting at all.

Clip length is the caller's call, and on suite gears it is the thing to think about: a suite board
is 16 m across with flat borders, so at 3 m/s the graded patch is crossed in a couple of seconds and
the rest of the clip is the robot on flat ground (or off the board entirely). ``--seconds`` defaults
to 6 for the recipe's own plane, which is infinite.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import pathlib
import sys
import traceback

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

PLANE = "plane"
DEFAULT_OUT_DIR = pathlib.Path(__file__).resolve().parent / "videos"
#: Chase-camera offsets from the robot root [m], in the robot's spawn frame (+x = ahead). The
#: recorded camera does not follow on its own -- the Kit capture parks ``/OmniverseKit_Persp`` at
#: ``eye``/``lookat`` on its first frame and never moves it again -- so the follow is done here,
#: one prim update per step, and these offsets are what stays fixed while the robot moves.
DEFAULT_EYE = (-4.0, -3.0, 2.2)
DEFAULT_LOOKAT = (1.5, 0.0, 0.3)
#: The recorder's camera (``video_recorder_cfg``: "the ``/OmniverseKit_Persp`` camera via
#: ``omni.replicator.core``"); read off the live capture when it exposes one, so a recorder that
#: ever captures elsewhere is followed correctly rather than silently not followed.
DEFAULT_CAMERA_PRIM = "/OmniverseKit_Persp"


def parse_speeds(text: str) -> list[float]:
    """``"1.5,3"`` -> ``[1.5, 3.0]``; empty or NaN is a typo, not a gear."""
    gears = []
    for token in text.split(","):
        token = token.strip()
        if token:
            try:
                value = float(token)
            except ValueError:
                raise SystemExit(f"--speeds takes comma-separated numbers, got {token!r}") from None
            if value != value:
                raise SystemExit("--speeds does not take NaN")
            gears.append(value)
    if not gears:
        raise SystemExit("--speeds is empty")
    return gears


def parse_terrains(text: str) -> list[str]:
    """``"plane,rough_b"`` -> validated names, unknown gear refused with the whole menu."""
    from ablation_harness import suites

    allowed = [PLANE, *suites.LIZARD_SUITE_V2_NAMES]
    gears = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        if token not in allowed:
            raise SystemExit(f"unknown terrain gear {token!r}; suite gears are {allowed}")
        gears.append(token)
    if not gears:
        raise SystemExit("--terrains is empty")
    return gears


def gear_terrain(gear: str, recipe_terrain):
    """The ``TerrainImporterCfg`` for one gear: the recipe's own ground, or one suite column."""
    if gear == PLANE:
        return recipe_terrain
    from ablation_harness import suites

    board = suites.lizard_suite_v2()
    generator = board.terrain_generator
    generator.sub_terrains = {gear: generator.sub_terrains[gear]}
    generator.num_rows = 1
    generator.num_cols = 1
    return board


def in_recipe_box(speed: float, box: list[float]) -> bool:
    """Whether the recipe's own command term would ever issue ``speed``."""
    return box[0] - 1e-6 <= speed <= box[1] + 1e-6


def cells(speeds: list[float], terrains: list[str]) -> list[dict]:
    """The matrix, as data: one dict per clip to shoot."""
    return [{"speed": s, "terrain": t} for s in speeds for t in terrains]


def follow_view(root, yaw: float, eye_off, lookat_off) -> tuple[tuple, tuple]:
    """World ``(eye, target)`` for one frame: the offsets rotated into the robot's spawn frame.

    Rotating by the *spawn* yaw rather than the live one keeps the shot steady -- a chase camera
    that re-aims with every yaw wobble is a worse record of the gait than one that holds still.
    """
    ca, sa = math.cos(yaw), math.sin(yaw)

    def place(offset):
        return (float(root[0]) + offset[0] * ca - offset[1] * sa,
                float(root[1]) + offset[0] * sa + offset[1] * ca,
                float(root[2]) + offset[2])

    return place(eye_off), place(lookat_off)


def record_cell(cell: dict, args) -> dict:
    """Shoot one clip and return its conditions. Kit must already be up."""
    import gymnasium as gym
    import imageio
    import torch
    from isaaclab.utils.string import string_to_callable
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg
    from rsl_rl.runners import OnPolicyRunner

    from ablation_harness import record as record_mod
    from ablation_harness.components.command_player import CommandPlayer
    from ablation_harness.components.dr_controller import apply_eval_mode

    import rl_exp.tasks  # noqa: F401  (registers the tasks)

    spec = gym.spec(args.task)
    cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    agent_cfg = string_to_callable(spec.kwargs["rsl_rl_cfg_entry_point"])()
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, importlib.metadata.version("rsl-rl-lib"))
    speed = cell["speed"]
    command_box = [float(v) for v in cfg.commands.base_velocity.ranges.lin_vel_x]

    cfg.scene.terrain = gear_terrain(cell["terrain"], cfg.scene.terrain)
    cfg.curriculum.terrain_levels = None
    cfg.scene.num_envs = args.num_envs
    cfg.seed = args.seed
    cfg.episode_length_s = args.seconds
    apply_eval_mode(cfg, "nominal")
    if not args.follow:
        # Fixed camera: eye/lookat are absolute world points, and the shot is over as soon as the
        # robot leaves the frame -- which at 3 m/s is a few seconds.
        cfg.viewer.eye = tuple(args.eye)
        cfg.viewer.lookat = tuple(args.lookat)

    env = gym.make(args.task, cfg=cfg, render_mode="rgb_array")
    wrapper = None
    clip = pathlib.Path(args.out_dir) / f"{speed:g}mps_{cell['terrain']}.mp4"
    try:
        wrapper = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
        live = env.unwrapped
        steps = round(args.seconds / live.step_dt)
        cmd_term = live.command_manager.get_term("base_velocity")
        player = CommandPlayer([{"t": 0.0, "vx": speed}], live.num_envs, live.device)
        robot = live.scene["robot"]
        start = robot.data.root_pos_w.torch.clone()

        runner = OnPolicyRunner(wrapper, agent_cfg.to_dict(), log_dir=None, device=live.device)
        runner.load(args.checkpoint)
        policy = runner.get_inference_policy(device=live.device)

        obs = wrapper.get_observations()
        written = 0
        # The robot's spawn heading, read once: the policy may turn, and the final pose may already
        # be a respawn (episode length == clip length, so the last step times out and auto-resets).
        # Distance read only after the last step would report that respawn as ~0 m of travel.
        from isaaclab.utils.math import euler_xyz_from_quat
        yaw = float(euler_xyz_from_quat(robot.data.root_quat_w.torch)[2][0])
        peak_forward = 0.0
        resets = 0
        first_reset_s = None
        move_camera = None
        camera_prim = DEFAULT_CAMERA_PRIM
        if args.follow:
            from isaaclab_physx.renderers.kit_viewport_utils import set_kit_renderer_camera_view

            move_camera = set_kit_renderer_camera_view
            capture = getattr(live.video_recorder, "_capture", None)
            camera_prim = getattr(getattr(capture, "cfg", None), "camera_prim_path", DEFAULT_CAMERA_PRIM)
        clip.parent.mkdir(parents=True, exist_ok=True)
        writer = imageio.get_writer(clip, fps=round(1.0 / live.step_dt))
        try:
            for step in range(steps):
                cmd_term.vel_command_b[:] = player.command_at(0.0)
                with torch.no_grad():
                    obs, _, _, _ = wrapper.step(policy(obs))
                if move_camera is not None:
                    eye, target = follow_view(robot.data.root_pos_w.torch[0], yaw, args.eye, args.lookat)
                    # The capture reads eye/lookat once, on its first frame; the prim is what every
                    # later frame comes from. Set both, so frame 0 is the shot too.
                    live.video_recorder.cfg.eye, live.video_recorder.cfg.lookat = eye, target
                    move_camera(eye=list(eye), target=list(target), camera_prim_path=camera_prim)
                frame = env.render()
                if frame is None:
                    raise RuntimeError("env.render() returned no frame: no video backend "
                                       "(launch with cameras enabled)")
                writer.append_data(frame)
                written += 1
                delta = (robot.data.root_pos_w.torch[0] - start[0])[:2]
                peak_forward = max(peak_forward, float(delta[0] * math.cos(yaw) + delta[1] * math.sin(yaw)))
                if bool(live.termination_manager.dones[0]):
                    resets += 1
                    if first_reset_s is None:
                        first_reset_s = round((step + 1) * live.step_dt, 4)
        finally:
            writer.close()
        if written != steps:
            raise RuntimeError(f"clip has {written} frames, expected {steps}: the rollout was cut short")
        if not clip.exists() or clip.stat().st_size == 0:
            raise RuntimeError(f"no clip was written to {clip}")
        # Forward means along the robot's spawn heading, so a turned robot reads as its own path.
        delta = (robot.data.root_pos_w.torch[0] - start[0])[:2]
        net_forward = float(delta[0] * math.cos(yaw) + delta[1] * math.sin(yaw))
        return {
            "speed_mps": speed, "terrain": cell["terrain"], "in_recipe_box": in_recipe_box(speed, command_box),
            "command_box_mps": command_box, "num_envs": live.num_envs, "seconds": args.seconds,
            "frames": written, "fps": round(1.0 / live.step_dt, 4),
            "forward_displacement_m": round(peak_forward, 4),
            "forward_speed_mps": round(peak_forward / args.seconds, 4),
            "net_forward_m": round(net_forward, 4),
            "resets": resets, "first_reset_s": first_reset_s,
            "checkpoint": record_mod.checkpoint_digest(args.checkpoint),
            "clip": str(clip), "clip_bytes": clip.stat().st_size if clip.exists() else 0,
            "camera": {"follow": args.follow, "camera_prim": camera_prim,
                       "eye": [float(v) for v in args.eye], "lookat": [float(v) for v in args.lookat],
                       "frame": "offsets from the robot root (spawn frame)" if args.follow
                                else "absolute world points"},
            "terrain_size_m": (cfg.scene.terrain.terrain_generator.size[0]
                               if cfg.scene.terrain.terrain_generator is not None else None),
        }
    finally:
        (wrapper if wrapper is not None else env).close()


def run(args) -> dict:
    """Shoot every cell and return the manifest."""
    speeds = parse_speeds(args.speeds)
    terrains = parse_terrains(args.terrains)
    matrix = cells(speeds, terrains)
    if args.dry_run:
        return {"dry_run": True, "cells": matrix}
    shots = []
    for cell in matrix:
        print(f"[VIDEO-MATRIX] shooting {cell['speed']:g} m/s on {cell['terrain']}", flush=True)
        shots.append(record_cell(cell, args))
    return {"cells": shots}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", default="Lizard-Baseline-Flat-Play-v2")
    parser.add_argument("--checkpoint", help="policy checkpoint; required unless --dry-run")
    parser.add_argument("--speeds", default="3.0", help="comma-separated speed gears [m/s]")
    parser.add_argument("--terrains", default=PLANE,
                        help="comma-separated terrain gears: plane, or any suite column name")
    parser.add_argument("--seconds", type=float, default=6.0, help="clip length [s]")
    parser.add_argument("--num_envs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--follow", action=argparse.BooleanOptionalAction, default=True,
                        help="chase camera: eye/lookat are offsets from the robot root (default). "
                             "--no-follow makes them absolute world points, and the robot leaves "
                             "the frame within seconds at speed")
    parser.add_argument("--eye", type=float, nargs=3, default=list(DEFAULT_EYE),
                        help="camera position [m]: offset from the robot when --follow, world point otherwise")
    parser.add_argument("--lookat", type=float, nargs=3, default=list(DEFAULT_LOOKAT),
                        help="camera target [m]: offset from the robot when --follow, world point otherwise")
    parser.add_argument("--out_dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--dry_run", action="store_true",
                        help="print the matrix and exit; launches no simulator")
    from isaaclab.app import AppLauncher

    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if args.num_envs < 1:
        parser.error("--num_envs must be positive")
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    if not args.dry_run and not args.checkpoint:
        parser.error("--checkpoint is required to shoot a clip")
    if args.dry_run:
        print(json.dumps(run(args), indent=2))
        return
    # rgb_array frames come from the recorder, which needs cameras regardless of --headless.
    args.enable_cameras = True
    app = AppLauncher(args).app
    try:
        # Gears are validated only now: naming a suite column imports the suite, and that import
        # chain must not run before the app, or Kit's own USD stack comes up poisoned (pitfalls P003).
        manifest = run(args)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"task": args.task, "seed": args.seed, **manifest},
                             indent=2, ensure_ascii=False, allow_nan=False)
        (args.out_dir / "matrix.json").write_text(payload, encoding="utf-8")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    except BaseException:
        # app.close() ends the process, so a traceback raised past it never reaches the terminal.
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        raise
    finally:
        app.close()


if __name__ == "__main__":
    main()
