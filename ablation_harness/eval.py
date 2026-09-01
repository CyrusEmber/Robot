# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Unified eval runner for the locomotion ablation harness.

Loads a registered task's env cfg, swaps the terrain for a frozen suite grid,
runs the frozen protocol command timeline with a fixed seed, and writes
per-segment / per-terrain metrics to results/<protocol>/<run_id>/eval.json
plus one row into the protocol's summary.csv.

Usage (from E:\\IsaacLab):
    python ablation_harness\\eval.py --task Lizard-Rough-v2 --checkpoint <model.pt> ^
        --protocol locomotion_eval_v1 --mode nominal --seed 123
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import pathlib
import re
import subprocess

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Locomotion eval harness runner.")
parser.add_argument("--task", type=str, required=True, help="Registered TRAIN task id (not -Play).")
parser.add_argument("--checkpoint", type=str, default=None, help="Policy checkpoint; omit for a zero-action smoke run.")
parser.add_argument("--protocol", type=str, default="locomotion_eval_v1", help="Protocol name under protocols/.")
parser.add_argument("--mode", type=str, default="nominal", choices=["nominal", "robust"])
parser.add_argument("--seed", type=int, default=123, help="Eval seed (pins DR realizations and resets).")
parser.add_argument("--envs_per_terrain", type=int, default=None,
                    help="Env columns per suite terrain; default from protocol suite_layout.")
parser.add_argument("--tag", type=str, default=None, help="Run label; defaults to checkpoint/random.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
# a -Play cfg arrives with every DR event already nulled, which silently turns
# robust mode into nominal (dr_controller can only keep or remove events that
# still exist) -- refuse loudly instead of publishing wrong numbers
if args_cli.task.endswith("-Play"):
    raise SystemExit(
        f"Task '{args_cli.task}' is a PLAY variant. Pass the TRAIN task id instead: "
        "the harness controls domain randomization itself (nominal disables it, "
        "robust keeps it at a pinned seed), so it needs a cfg with DR intact."
    )
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402
import yaml  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402

from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab.utils.string import string_to_callable  # noqa: E402

import isaaclab_tasks  # noqa: F401, E402  (registers the gym tasks)

import metrics  # noqa: E402
import suites  # noqa: E402
from components.command_player import CommandPlayer  # noqa: E402
from components.dr_controller import apply_eval_mode  # noqa: E402
from components import recovery as recovery_mod  # noqa: E402

_HARNESS_DIR = pathlib.Path(__file__).resolve().parent
# provenance roots: the lizard git repo (junction-resolved) vs the IsaacLab
# root (invocation path, junction NOT resolved). They differ only on the
# original-machine layout; on a fresh tree the harness is copied into the
# IsaacLab root and there is no separate lizard repo to point at.
_REPO_ROOT = _HARNESS_DIR.parent
_ISAAC_ROOT = pathlib.Path(__file__).absolute().parents[1]
if _REPO_ROOT == _ISAAC_ROOT or not (_REPO_ROOT / "rl_exp").is_dir():
    _REPO_ROOT = None
_SUITE_REGISTRY = {
    "lizard_suite_v1": (suites.LIZARD_SUITE_V1_NAMES, suites.lizard_suite_v1),
}
# summary.csv columns (protocol-wide, machine-readable single line per run)
_SUMMARY_COLUMNS = [
    "run_id", "protocol", "task", "tag", "mode", "seed",
    "git_rev_lizard", "git_rev_isaaclab", "timestamp",
    "success_rate", "fall_rate", "lin_mae_mps", "ang_mae_radps",
    "energy_per_m_j", "stop_overshoot_mps", "recovery_mean_s", "never_recovered",
]


def _git_rev(repo: pathlib.Path) -> str:
    """Short commit id of the git repo at ``repo`` ('unknown' if not a repo)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _load_protocol(name: str) -> dict:
    path = _HARNESS_DIR / "protocols" / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _round(value, digits=4):
    if isinstance(value, float) and value == value:
        return round(value, digits)
    return value


def _prepare_env(protocol: dict) -> tuple[object, object]:
    """Env cfg from the gym registry (no hydra), suite swap, protocol timing, eval mode."""
    spec = gym.spec(args_cli.task)
    env_cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    agent_cfg = string_to_callable(spec.kwargs["rsl_rl_cfg_entry_point"])()

    suite_factory = _SUITE_REGISTRY[protocol["suite"]][1]
    num_cols = int(protocol["suite_layout"]["num_cols"])
    if args_cli.envs_per_terrain is None:
        args_cli.envs_per_terrain = int(protocol["suite_layout"]["envs_per_terrain"])

    env_cfg.scene.terrain = suite_factory()
    env_cfg.scene.num_envs = args_cli.envs_per_terrain * num_cols
    env_cfg.episode_length_s = float(protocol["episode_length_s"])
    env_cfg.seed = args_cli.seed
    env_cfg.curriculum.terrain_levels = None  # fixed suite: no terrain roaming
    if args_cli.device is not None:
        env_cfg.sim.device = args_cli.device
    apply_eval_mode(env_cfg, args_cli.mode)
    return env_cfg, agent_cfg


def _make_policy(wrapper, mbenv, agent_cfg, device) -> tuple[object, str]:
    """Trained checkpoint policy or zero-action smoke policy."""
    if args_cli.checkpoint is not None:
        agent_cfg.seed = args_cli.seed
        runner = OnPolicyRunner(wrapper, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
        runner.load(args_cli.checkpoint)
        return runner.get_inference_policy(device=device), args_cli.checkpoint
    action_dim = mbenv.action_manager.total_action_dim

    def policy(obs, _action_dim=action_dim):
        return torch.zeros(obs.shape[0], _action_dim, device=obs.device)

    return policy, "zero_action"


def _rollout(wrapper, mbenv, robot, policy, player, cmd_term, scanner, center_ray,
             push, num_steps: int, step_dt: float, device: str) -> dict:
    """One protocol episode per env; data frozen after each env's first done."""
    series = {
        "lin_vel_b": [], "ang_vel_b": [], "cmd": [], "tilt_cos": [],
        "clearance": [], "energy": [],
    }
    first_done = torch.full((mbenv.num_envs,), num_steps, dtype=torch.long, device=device)
    start_pos = robot.data.root_pos_w.torch.clone()
    end_pos = robot.data.root_pos_w.torch.clone()
    obs = wrapper.get_observations()

    for step in range(num_steps):
        cmd = player.command_at(step * step_dt)
        cmd_term.vel_command_b[:] = cmd
        if push is not None and step == push[0]:
            recovery_mod.apply_kick(robot, push[1], push[2])

        # Snapshot BEFORE wrapper.step(): IsaacLab resets terminated envs inside
        # step(), so any post-step read of scene tensors returns respawn values,
        # not terminal ones (H1: end_pos and the done-step series entries were
        # spawn garbage). ponytail: pre-step snapshot is off by one step_dt from
        # the true terminal state; the post-physics pre-reset state is not
        # observable through the public step() API.
        data = robot.data
        snap = {
            "lin_vel_b": data.root_lin_vel_b.torch.clone(),
            "ang_vel_b": data.root_ang_vel_b.torch.clone(),
            "tilt_cos": -data.projected_gravity_b.torch[:, 2].clone(),
            "root_pos_w": data.root_pos_w.torch.clone(),
        }
        if scanner is not None:
            terrain_z = scanner.data.ray_hits_w.torch[:, center_ray, 2]
            snap["clearance"] = data.root_pos_w.torch[:, 2] - terrain_z
        snap["energy"] = metrics.step_energy(
            data.joint_stiffness.torch, data.joint_damping.torch,
            data.joint_pos_target.torch, data.joint_pos.torch, data.joint_vel.torch,
        )

        with torch.inference_mode():
            actions = policy(obs)
        obs, _, _, _ = wrapper.step(actions)

        for key in ("lin_vel_b", "ang_vel_b", "tilt_cos", "clearance", "energy"):
            if key in snap:
                series[key].append(snap[key])
        series["cmd"].append(cmd.clone())

        done_now = mbenv.termination_manager.dones
        newly_done = done_now & (first_done == num_steps)
        if bool(newly_done.any()):
            env_ids = newly_done.nonzero(as_tuple=False).squeeze(-1)
            first_done[env_ids] = step
            end_pos[env_ids] = snap["root_pos_w"][env_ids]

    # capture before close(): scene tensors are freed on close
    return {
        "series": series,
        "first_done": first_done,
        "start_pos": start_pos,
        "end_pos": end_pos,
        "terrain_types": mbenv.scene.terrain.terrain_types.clone(),
    }


def _segment_stats(seg: dict, lin_err, ang_err, succ, lin_vel_b, valid, step_axis) -> dict | None:
    t0, t1 = float(seg["start_s"]), float(seg["end_s"])
    sel = ((step_axis >= t0) & (step_axis < t1)).squeeze(1)
    if bool(sel.sum()) == 0:
        return None
    m = valid[sel]
    stats = {
        "name": seg["name"],
        "lin_mae_mps": metrics.summarize_segment(lin_err[sel], m),
        "ang_mae_radps": metrics.summarize_segment(ang_err[sel], m),
        "success_rate": metrics.summarize_segment(succ[sel].float(), m),
    }
    if all(v == 0.0 for v in seg["cmd"][:2]):
        stats["stop_overshoot_mps"] = metrics.stop_overshoot(lin_vel_b[sel], m).mean().item()
    return stats


def _analyze(rollout: dict, protocol: dict, tilt_cos_min: float, clearance_min: float,
             player, terrain_names, policy_label: str, num_steps: int, step_dt: float,
             device: str, push) -> tuple[dict, list, dict | None]:
    """Frozen protocol metrics from the rollout -> (result, segments, recovery)."""
    m_cfg = protocol["metrics"]
    fall_cfg = m_cfg["fall"]
    series = rollout["series"]
    first_done = rollout["first_done"]
    start_pos, end_pos = rollout["start_pos"], rollout["end_pos"]

    lin_vel_b = torch.stack(series["lin_vel_b"])
    ang_vel_b = torch.stack(series["ang_vel_b"])
    cmd = torch.stack(series["cmd"])
    tilt_cos = torch.stack(series["tilt_cos"])
    energy = torch.stack(series["energy"])
    clearance = torch.stack(series["clearance"]) if series["clearance"] else None
    valid = torch.arange(num_steps, device=device).unsqueeze(1) <= first_done.unsqueeze(0)
    valid_f = valid.float()

    lin_err, ang_err = metrics.tracking_errors(lin_vel_b, ang_vel_b, cmd)
    succ = metrics.success_mask(
        lin_err, ang_err,
        float(m_cfg["tracking_lin_threshold_mps"]), float(m_cfg["tracking_ang_threshold_radps"]),
    )
    sustain_steps = max(1, int(round(float(fall_cfg["sustain_s"]) / step_dt)))
    falls = metrics.fall_flags(tilt_cos, clearance, tilt_cos_min, clearance_min, sustain_steps, valid)

    travelled = torch.linalg.norm(end_pos[:, :2] - start_pos[:, :2], dim=-1)
    # energy series is per-step POWER [W] (metrics.step_energy); integrating
    # over valid steps requires the step duration -- pre-fix runs omitted it
    # and reported numbers inflated by 1/step_dt (see summary.csv 2026-08-28)
    energy_total = (energy * valid_f).sum(dim=0) * step_dt
    energy_per_m = (energy_total / travelled.clamp(min=0.1)).mean().item()

    step_axis = torch.arange(num_steps, device=device).unsqueeze(1) * step_dt
    segments = [
        s for s in (
            _segment_stats(seg, lin_err, ang_err, succ, lin_vel_b, valid, step_axis)
            for seg in player.segments(num_steps * step_dt, step_dt)
        ) if s
    ]

    terrains = {}
    for col, tname in enumerate(terrain_names):
        env_ids = (rollout["terrain_types"] == col).nonzero(as_tuple=False).squeeze(-1)
        if env_ids.numel() == 0:
            continue
        terrains[tname] = {
            "completion": metrics.completion_ratio(
                start_pos[env_ids], end_pos[env_ids], cmd[:, env_ids], valid[:, env_ids], step_dt
            ).mean().item(),
            "fall_rate": falls[env_ids].float().mean().item(),
            "success_rate": metrics.summarize_segment(succ[:, env_ids].float(), valid[:, env_ids]),
        }

    result = {
        "protocol": protocol["name"],
        "mode": args_cli.mode,
        "task": args_cli.task,
        "checkpoint": policy_label,
        "seed": args_cli.seed,
        "num_envs": len(first_done),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        # code provenance: which lizard git state and which IsaacLab fork
        # state produced these numbers (results without it are unattributable)
        "git_rev_lizard": _git_rev(_REPO_ROOT) if _REPO_ROOT else "unknown",
        "git_rev_isaaclab": _git_rev(_ISAAC_ROOT),
        "global": {
            "success_rate": metrics.summarize_segment(succ.float(), valid),
            "fall_rate": falls.float().mean().item(),
            "lin_mae_mps": metrics.summarize_segment(lin_err, valid),
            "ang_mae_radps": metrics.summarize_segment(ang_err, valid),
            "energy_per_m_j": energy_per_m,
            "terrain_completion_mean": sum(t["completion"] for t in terrains.values()) / max(len(terrains), 1),
        },
        "segments": segments,
        "terrains": terrains,
    }

    recovery = None
    if push is not None:
        push_step = push[0]
        r_cfg = m_cfg["recovery"]
        # recovery is measured on envs still inside their FIRST episode at the
        # kick: envs that already terminated were auto-respawned (new episode,
        # excluded by valid mask) and would pollute spike/never-recovered stats
        surviving = (first_done > push_step).nonzero(as_tuple=False).squeeze(-1)
        recovery = recovery_mod.recovery_times(
            lin_err[:, surviving], push_step,
            float(r_cfg["threshold_mps"]), max(1, int(round(float(r_cfg["sustain_s"]) / step_dt))),
            step_dt, valid[:, surviving],
        )
        recovery["fall_after_push_rate"] = (
            falls & (first_done > push_step)
        ).float().sum().item() / max(int(surviving.numel()), 1)
        recovery["measured_envs"] = int(surviving.numel())
        result["recovery"] = recovery

    return result, segments, recovery


def _persist(result: dict, segments: list, recovery: dict | None, run_id: str, tag: str):
    """eval.json + one summary.csv row (same run_id overwritten)."""
    # directory keyed by the protocol FILE stem (stable); the display name stays in the JSON
    out_dir = _HARNESS_DIR / "results" / args_cli.protocol / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "eval.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    row = {c: "" for c in _SUMMARY_COLUMNS}
    row.update({
        "run_id": run_id, "protocol": result["protocol"], "task": args_cli.task, "tag": tag,
        "mode": args_cli.mode, "seed": args_cli.seed, "timestamp": result["timestamp"],
        "git_rev_lizard": result["git_rev_lizard"], "git_rev_isaaclab": result["git_rev_isaaclab"],
        "success_rate": _round(result["global"]["success_rate"]),
        "fall_rate": _round(result["global"]["fall_rate"]),
        "lin_mae_mps": _round(result["global"]["lin_mae_mps"]),
        "ang_mae_radps": _round(result["global"]["ang_mae_radps"]),
        "energy_per_m_j": _round(result["global"]["energy_per_m_j"]),
    })
    if segments and "stop_overshoot_mps" in segments[-1]:
        row["stop_overshoot_mps"] = _round(segments[-1]["stop_overshoot_mps"])
    if recovery is not None:
        row["recovery_mean_s"] = _round(recovery["recovery_time_mean_s"])
        row["never_recovered"] = _round(recovery["never_recovered_frac"])

    summary_path = _HARNESS_DIR / "results" / args_cli.protocol / "summary.csv"
    existing = []
    if summary_path.exists():
        with open(summary_path, encoding="utf-8") as f:
            existing = [r for r in csv.DictReader(f) if r.get("run_id") != run_id]
    with open(summary_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(existing)
        writer.writerow(row)


def main():
    protocol = _load_protocol(args_cli.protocol)
    terrain_names = _SUITE_REGISTRY[protocol["suite"]][0]

    env_cfg, agent_cfg = _prepare_env(protocol)
    gym_env = gym.make(args_cli.task, cfg=env_cfg)
    mbenv = gym_env.unwrapped
    wrapper = RslRlVecEnvWrapper(gym_env, clip_actions=agent_cfg.clip_actions)
    robot = mbenv.scene["robot"]
    device = mbenv.device
    step_dt = mbenv.step_dt
    num_steps = int(round(float(protocol["episode_length_s"]) / step_dt))

    policy, policy_label = _make_policy(wrapper, mbenv, agent_cfg, device)

    player = CommandPlayer(protocol["command_timeline"], mbenv.num_envs, device)
    cmd_term = mbenv.command_manager.get_term("base_velocity")
    fall_cfg = protocol["metrics"]["fall"]
    tilt_cos_min = math.cos(math.radians(float(fall_cfg["tilt_deg"])))
    clearance_min = float(fall_cfg["base_height_ratio"]) * float(env_cfg.scene.robot.init_state.pos[2])

    scanner = mbenv.scene.sensors.get("height_scanner", None)
    center_ray = None
    if scanner is not None:
        # center ray of the grid pattern (odd x odd grid -> exact middle)
        num_rays = int(scanner.data.ray_hits_w.torch.shape[1])
        if num_rays % 2 == 0:
            raise ValueError(f"Suite fall metric needs an odd-ray grid pattern, got {num_rays} rays.")
        center_ray = num_rays // 2

    push = None
    if args_cli.mode == "robust" and "recovery_push" in protocol.get("robust", {}):
        push_cfg = protocol["robust"]["recovery_push"]
        push = (
            int(round(float(push_cfg["t"]) / step_dt)),
            float(push_cfg["kick_mps"]),
            recovery_mod.make_kick_directions(mbenv.num_envs, args_cli.seed, device),
        )

    rollout = _rollout(wrapper, mbenv, robot, policy, player, cmd_term, scanner,
                       center_ray, push, num_steps, step_dt, device)
    gym_env.close()

    result, segments, recovery = _analyze(
        rollout, protocol, tilt_cos_min, clearance_min, player, terrain_names,
        policy_label, num_steps, step_dt, device, push,
    )

    tag = args_cli.tag or ("ckpt" if args_cli.checkpoint else "random")
    # strip only the gym API suffix of family ids ("-v0" at the very end);
    # teacher recipe versions ("-v1"/"-v2") are part of the run identity
    run_id = f"{re.sub(r'-v0$', '', args_cli.task)}_{tag}_{args_cli.mode}_seed{args_cli.seed}"
    _persist(result, segments, recovery, run_id, tag)

    print(f"[EVAL] protocol={result['protocol']} mode={result['mode']} run_id={run_id}")
    print(f"[EVAL] success={result['global']['success_rate']:.3f} fall={result['global']['fall_rate']:.3f} "
          f"lin_mae={result['global']['lin_mae_mps']:.3f} energy_per_m={result['global']['energy_per_m_j']:.1f}")
    if recovery is not None:
        print(f"[EVAL] recovery_mean={recovery['recovery_time_mean_s']:.2f}s "
              f"never_recovered={recovery['never_recovered_frac']:.2f}")
    print(f"[EVAL] wrote results/{args_cli.protocol}/{run_id}/eval.json")


if __name__ == "__main__":
    main()
    simulation_app.close()
