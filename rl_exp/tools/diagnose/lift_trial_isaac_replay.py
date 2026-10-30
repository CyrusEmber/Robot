# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Render recorded articulation states; this is not an original simulator recording."""

import argparse
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from isaaclab.app import AppLauncher
from rl_exp.tools.runrecord.binding import sha256_file

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--report", type=Path, required=True)
parser.add_argument("--usd", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.out.exists():
    parser.error("output exists")
app = AppLauncher(args).app
try:
    import gymnasium as gym
    import imageio.v2 as imageio
    import numpy as np
    import torch
    from PIL import Image, ImageDraw
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    import rl_exp.tasks  # noqa: F401
    from ablation_harness.components.dr_controller import apply_eval_mode

    report = json.loads(args.report.read_text(encoding="utf-8"))
    if sha256_file(args.usd) != report["metadata"]["usd_sha256"]:
        raise ValueError("USD identity mismatch")
    spec = gym.spec("Lizard2-Flat-Play-v6")
    cfg = resolve_presets(string_to_callable(spec.kwargs["env_cfg_entry_point"])())
    cfg.scene.num_envs, cfg.seed = 1, 123
    apply_eval_mode(cfg, "nominal")
    cfg.scene.robot.spawn.usd_path = str(args.usd.resolve())
    first = report["samples"][0]
    guide_index = report["metadata"]["joints"].index("lift_vertical_joint")
    spawn_z = first["base_pose"][2] - first["q"][guide_index]
    cfg.scene.robot.init_state.pos = (0., 0., spawn_z)
    cfg.viewer.eye = (2.0, -4.5, 2.0)
    cfg.viewer.lookat = (-0.35, 0., 0.45)
    env = gym.make("Lizard2-Flat-Play-v6", cfg=cfg, render_mode="rgb_array")
    env.reset()
    live, robot = env.unwrapped, env.unwrapped.scene["robot"]
    names = report["metadata"]["joints"]
    if list(robot.joint_names) != names:
        raise ValueError("runtime joint order does not match recorded samples")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(str(args.out), fps=20, codec="libx264", macro_block_size=16)
    try:
        for i, sample in enumerate(report["samples"]):
            q = torch.tensor([sample["q"]], dtype=torch.float32, device=live.device)
            zeros = torch.zeros_like(q)
            robot.write_joint_state_to_sim(q, zeros)
            live.sim.forward()
            live.sim.render()
            frame = env.render()
            if frame is None:
                raise ValueError("render backend returned no frame")
            frame = Image.fromarray(np.asarray(frame, dtype=np.uint8))
            draw = ImageDraw.Draw(frame)
            draw.rectangle((0, 0, frame.width, 54), fill=(0, 0, 0))
            draw.text((10, 5), f"RECORDED STATE REPLAY - t={sample['t_s']:.3f}s - 80x SLOW", fill=(255, 255, 255))
            forces = sample["ground_forces"]
            draw.text((10, 27), "Ground normal force: " + "  ".join(
                f"{short} {forces.get(name,[0,0,0])[2]:.0f}N" for name, short in
                (("lf_wrist", "LF"), ("rf_wrist", "RF"), ("rl_ankle", "LH"), ("rr_ankle", "RH"))), fill=(255, 255, 255))
            image = np.asarray(frame)
            for _ in range(8 + (20 if i in (0, len(report["samples"]) - 1) else 0)):
                writer.append_data(image)
    finally:
        writer.close()
    print("ISAAC_STATE_REPLAY", str(args.out), flush=True)
    env.close()
    app.close(exit_code=0)
except BaseException:
    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    app.close(exit_code=1)
    raise
