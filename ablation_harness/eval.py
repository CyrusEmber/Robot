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
        --protocol locomotion_eval_v2 --mode nominal --seed 123
"""

from __future__ import annotations

import argparse
import csv
import datetime
import importlib.metadata
import json
import math
import os
import pathlib
import re
import subprocess
import sys

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Locomotion eval harness runner.")
parser.add_argument("--task", type=str, required=True, help="Registered TRAIN task id (not -Play).")
parser.add_argument("--checkpoint", type=str, default=None, help="Policy checkpoint; omit for a zero-action smoke run.")
parser.add_argument("--protocol", type=str, default="locomotion_eval_v2", help="Protocol name under protocols/.")
parser.add_argument("--mode", type=str, default="nominal", choices=["nominal", "robust"])
parser.add_argument("--seed", type=int, default=123, help="Eval seed (pins DR realizations and resets).")
parser.add_argument("--envs_per_terrain", type=int, default=None,
                    help="Env columns per suite terrain; default from protocol suite_layout.")
parser.add_argument("--tag", type=str, default=None, help="Run label; defaults to checkpoint/random.")
parser.add_argument("--group", type=str, default=None,
                    help="Optional campaign folder under results/<protocol>/ (e.g. v1); its "
                         "runs and summary.csv stay inside that folder instead of the protocol root.")
parser.add_argument("--variant", type=str, default=None,
                    help="Suffix naming what was swapped against the base run (P04 substitutions: "
                         "ckpt / suite / assets / protocol). Its own run_id, its own records.")
parser.add_argument("--overwrite", action="store_true",
                    help="Allow writing into an existing run_id that cannot be certified as this "
                         "same measurement: a differing record, a pre-format run (results but no "
                         "record), or an unreadable record file. Without it, all three are refused.")
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

from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg  # noqa: E402
from isaaclab.utils.string import string_to_callable  # noqa: E402

import isaaclab_tasks  # noqa: F401, E402  (registers the gym tasks)

import host_paths  # noqa: E402  (machine-local IsaacLab root, see paths.example.yaml)
import metrics  # noqa: E402
import record  # noqa: E402  (sibling module: the eval record format, ARCH_PLAN Step 3.2a)
import suites  # noqa: E402
from components.command_player import CommandPlayer  # noqa: E402
from components.dr_controller import apply_eval_mode  # noqa: E402
from components import recovery as recovery_mod  # noqa: E402

_HARNESS_DIR = pathlib.Path(__file__).resolve().parent


def _git_root(path: pathlib.Path | None) -> pathlib.Path | None:
    """Top level of the git repo containing ``path`` (None if absent/not a repo)."""
    if path is None:
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return pathlib.Path(out.stdout.strip()) if out.returncode == 0 else None


def _find_isaac_root() -> pathlib.Path | None:
    """IsaacLab root from ``paths.yaml`` / ``RL_ISAAC_ROOT`` / an upward probe."""
    return host_paths.isaac_root()


# Provenance roots. Path arithmetic cannot name them: the harness used to be
# reached through an E:\IsaacLab junction (so "harness parent" meant IsaacLab)
# and now lives in the lizard repo and is invoked by absolute path, where the
# same arithmetic returns the lizard repo and labels its rev as the IsaacLab
# one. So: git owns the lizard side, host_paths (paths.yaml / RL_ISAAC_ROOT)
# owns the IsaacLab side, and an undiscoverable root reports 'unknown' instead
# of a wrong rev.
_LIZARD_ROOT = _git_root(_HARNESS_DIR)
_ISAAC_ROOT = _find_isaac_root()
_ISAAC_GIT_ROOT = _git_root(_ISAAC_ROOT)
# The record asks two in-repo readers (the frozen asset lock and the declared obs protocol).
# Both are stdlib-only, but they live under rl_exp, which is reached by absolute path rather
# than as an installed package -- so the repo root joins sys.path here, next to the
# provenance roots it was just derived from, instead of each reader guessing its own.
if _LIZARD_ROOT is not None and str(_LIZARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_LIZARD_ROOT))
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


def _git_rev(repo: pathlib.Path | None) -> str:
    """Commit id of the git repo at ``repo`` ('unknown' if not a repo).

    One spelling for both records (PLAN.md #27 ①): this used to ask git for ``--short`` (~7
    characters) while the run manifest recorded 12, so one commit read as two different strings
    in the two records of the same run. The primitive and the length live in ``binding`` now,
    so ``runtime.git_rev_lizard`` and ``code.repository.rev`` are the same string.
    """
    if repo is None:
        return record.UNKNOWN
    try:
        from rl_exp.tools.runrecord import binding

        return binding.git_rev(repo) or record.UNKNOWN
    except Exception:  # a broken tree must degrade to 'unknown', never to no record
        return record.UNKNOWN


def _load_protocol(name: str) -> dict:
    path = _HARNESS_DIR / "protocols" / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _package_version(name: str) -> str:
    """Installed version of ``name``, or 'unknown' -- an unreadable version is not a guess."""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return record.UNKNOWN


def _protocol_reference(protocol: dict) -> dict:
    """The protocol *file* this run was measured under: name, version and its content digest.

    Recorded apart from the obs protocol identity (3.1a): one is the measurement contract,
    the other is the layout the policies were trained under.
    """
    path = _HARNESS_DIR / "protocols" / f"{args_cli.protocol}.yaml"
    return {
        "name": protocol.get("name") or args_cli.protocol,
        "version": protocol.get("version"),
        "digest": record.file_sha256(path),
    }


def _suite_reference(protocol: dict, env_cfg) -> dict:
    """The frozen terrain suite as swapped into this env cfg, plus its digest.

    The digest is over the *instantiated* importer cfg, so a suite edit is visible even when
    the run's env cfg digest is compared against another run's.
    """
    from rl_exp.tools.verify import cfg_snapshot

    layout = protocol.get("suite_layout") or {}
    return {
        "name": protocol["suite"],
        "num_rows": layout.get("num_rows"),
        "num_cols": layout.get("num_cols"),
        "envs_per_terrain": layout.get("envs_per_terrain"),
        "terrains": list(_SUITE_REGISTRY[protocol["suite"]][0]),
        "digest": cfg_snapshot.digest(cfg_snapshot.snapshot(env_cfg.scene.terrain)),
    }


def _obs_reference(task: str) -> dict:
    """The declared obs protocol for this task (Step 3.1a) -- declared, not instantiated."""
    identity, approved, note = record.UNKNOWN, record.UNKNOWN, ""
    try:
        from rl_exp.tools.runrecord import manifest as manifest_mod

        ref = manifest_mod.protocol_ref(task)
        identity = ref.get("obs_protocol") or record.UNKNOWN
        approved = ref.get("obs_protocol_digest") or record.UNKNOWN
        note = ref.get("obs_protocol_note") or ""
    except Exception as err:  # a broken tree must degrade to 'unknown', never to no record
        note = f"obs protocol lookup failed: {err!r}"
    return {"identity": identity, "digest": approved, "note": note}


def _assets_reference(env_cfg) -> dict:
    """Declared asset lock digest vs the *actual* files: pass / fail / unknown."""
    from rl_exp.tools.runrecord import manifest as manifest_mod

    version = getattr(env_cfg, "params_version", None)
    ref = manifest_mod.asset_digest(version if isinstance(version, str) else None, getattr(type(env_cfg), "params_line", None))
    changed = ref.get("missing_or_changed") or []
    manifest_sha = ref.get("manifest_sha256")
    if manifest_sha is None:
        verdict = "unknown"
    else:
        verdict = "fail" if changed else "pass"
    return {
        "declared_digest": manifest_sha or ref.get("lock_sha256") or record.UNKNOWN,
        "lock": ref.get("lock"),
        "file_count": ref.get("file_count"),
        "manifest_sha256": manifest_sha or record.UNKNOWN,
        "actual": {
            "verdict": verdict,
            "changed": changed[:10],
            "detail": ref.get("detail") or (ref.get("closure") if manifest_sha else ""),
        },
    }


def _runtime_reference(env_cfg, mbenv) -> dict:
    """What actually ran, with the declared value kept in its own field.

    The env cfg is not a substitute for either the installed versions or the values the
    process ended up using (``--device``, num_envs), so declared and actual stay apart.
    """
    return {
        "device": str(getattr(mbenv, "device", record.UNKNOWN)),
        "device_declared": str(getattr(env_cfg.sim, "device", record.UNKNOWN)),
        "num_envs": int(getattr(mbenv, "num_envs", -1)),
        "num_envs_declared": int(getattr(env_cfg.scene, "num_envs", -1)),
        "rsl_rl_version": _package_version("rsl-rl-lib"),
        "sim_version": _package_version("isaacsim"),
        "git_rev_lizard": _git_rev(_LIZARD_ROOT) if _LIZARD_ROOT != _ISAAC_GIT_ROOT else record.UNKNOWN,
        "git_rev_isaaclab": _git_rev(_ISAAC_ROOT),
    }


def _perturbation_reference(protocol: dict, push) -> dict | None:
    """The robust push as applied: step, kick magnitude, direction seed and horizon.

    A robust protocol that declares no ``recovery_push`` applied no perturbation; that is
    recorded as 'unknown' rather than left empty, so such a run cannot read as comparable to
    a pushed one.
    """
    if args_cli.mode != "robust":
        return None
    push_cfg = (protocol.get("robust") or {}).get("recovery_push") or {}
    return {
        "t": push_cfg.get("t", record.UNKNOWN),
        "kick_mps": push_cfg.get("kick_mps", record.UNKNOWN),
        "direction_seed": args_cli.seed,
        "num_steps": int(push[0]) if push is not None else record.UNKNOWN,
    }


def _round(value, digits=4):
    if isinstance(value, float) and value == value:
        return round(value, digits)
    return value


def _prepare_env(protocol: dict) -> tuple[object, object]:
    """Env cfg from the gym registry (no hydra), suite swap, protocol timing, eval mode."""
    spec = gym.spec(args_cli.task)
    env_cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    agent_cfg = string_to_callable(spec.kwargs["rsl_rl_cfg_entry_point"])()
    # same legacy-cfg migration train.py does: rsl-rl >= 5 rejects the old
    # `stochastic`/`init_noise_std` policy fields that the repo cfgs still carry
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, importlib.metadata.version("rsl-rl-lib"))

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


def _make_policy(wrapper, mbenv, agent_cfg, device, rec: dict) -> tuple[object, str]:
    """Trained checkpoint policy or zero-action smoke policy.

    The checkpoint is hashed **here, at load**, into the record: this is the file the run
    actually loaded, and the digest is re-read immediately after ``load`` so a checkpoint
    overwritten while the run is in flight reads as a mismatch instead of being certified by
    whatever sits at that path at the end (``record.read_state`` voids such a record).
    """
    if args_cli.checkpoint is not None:
        agent_cfg.seed = args_cli.seed
        runner = OnPolicyRunner(wrapper, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
        before = record.checkpoint_digest(args_cli.checkpoint)
        runner.load(args_cli.checkpoint)
        rec["policy"] = {"kind": "checkpoint"}
        rec["checkpoint"] = {**before, "sha256_after_load": record.file_sha256(before["resolved"])}
        return runner.get_inference_policy(device=device), args_cli.checkpoint
    action_dim = mbenv.action_manager.total_action_dim
    rec["policy"] = {"kind": "zero_action", "action_dim": int(action_dim)}

    def policy(obs, _action_dim=action_dim):
        return torch.zeros(obs.shape[0], _action_dim, device=obs.device)

    return policy, "zero_action"


def _snapshot(robot, scanner, center_ray) -> dict:
    """One frame of per-env state read from the live buffers [m/s, m/s, cos, m, W]."""
    data = robot.data
    snap = {
        "lin_vel_b": data.root_lin_vel_b.torch.clone(),
        "ang_vel_b": data.root_ang_vel_b.torch.clone(),
        "tilt_cos": -data.projected_gravity_b.torch[:, 2].clone(),
        "root_pos_w": data.root_pos_w.torch.clone(),
        "energy": metrics.step_energy(
            data.joint_stiffness.torch, data.joint_damping.torch,
            data.joint_pos_target.torch, data.joint_pos.torch, data.joint_vel.torch,
        ),
    }
    if scanner is not None:
        terrain_z = scanner.data.ray_hits_w.torch[:, center_ray, 2]
        snap["clearance"] = data.root_pos_w.torch[:, 2] - terrain_z
    return snap


def _rollout(wrapper, mbenv, robot, policy, player, cmd_term, scanner, center_ray,
             push, num_steps: int, step_dt: float, device: str) -> dict:
    """One protocol episode per env; data frozen after each env's first done.

    Frames are the **post-physics, pre-reset** states (Locomotion-Eval-v2): the
    frame the reward and the terminations actually saw. v1 sampled the pre-step
    state instead -- one ``step_dt`` early, and blind to each episode's terminal
    frame, which the auto-reset inside ``step()`` overwrites before it can be
    read (see ``protocols/locomotion_eval_v2.yaml`` for why that last frame
    matters to the fall window).
    """
    series = {
        "lin_vel_b": [], "ang_vel_b": [], "cmd": [], "tilt_cos": [],
        "clearance": [], "energy": [],
    }
    first_done = torch.full((mbenv.num_envs,), num_steps, dtype=torch.long, device=device)
    start_pos = robot.data.root_pos_w.torch.clone()
    end_pos = robot.data.root_pos_w.torch.clone()
    obs = wrapper.get_observations()

    # terminal-frame capture: scene tensors are refreshed at the end of the
    # physics block (scene.update) and overwritten only after that, by the
    # auto-reset inside step() -- so the terminal state is readable exactly in
    # the window between the two. IsaacLab exposes no callback for that window
    # (record_pre_reset is its nearest neighbour and is HDF5-shaped), so hook
    # the reset itself. Installed here, after the construction-time reset, so
    # every call is a rollout termination.
    terminal: dict = {}
    pending_ids: torch.Tensor | None = None
    captured_frames = 0
    _orig_reset_idx = mbenv._reset_idx

    def _reset_with_capture(env_ids):
        nonlocal pending_ids
        terminal.update(_snapshot(robot, scanner, center_ray))
        pending_ids = env_ids.clone()
        _orig_reset_idx(env_ids)

    mbenv._reset_idx = _reset_with_capture

    for step in range(num_steps):
        cmd = player.command_at(step * step_dt)
        cmd_term.vel_command_b[:] = cmd
        if push is not None and step == push[0]:
            recovery_mod.apply_kick(robot, push[1], push[2])

        with torch.inference_mode():
            actions = policy(obs)
        obs, _, _, _ = wrapper.step(actions)

        snap = _snapshot(robot, scanner, center_ray)
        if pending_ids is not None:
            # rows whose episode ended this step: their scene tensors already
            # hold respawn values, so put the captured terminal frame back
            for key, value in snap.items():
                value[pending_ids] = terminal[key][pending_ids]
            captured_frames += int(pending_ids.numel())
            pending_ids = None

        for key in ("lin_vel_b", "ang_vel_b", "tilt_cos", "clearance", "energy"):
            if key in snap:
                series[key].append(snap[key])
        series["cmd"].append(cmd.clone())

        done_now = mbenv.termination_manager.dones
        newly_done = done_now & (first_done == num_steps)
        if bool(newly_done.any()):
            env_ids = newly_done.nonzero(as_tuple=False).squeeze(-1)
            first_done[env_ids] = step
            # the terminal frame itself, not a pre-step approximation (H1)
            end_pos[env_ids] = snap["root_pos_w"][env_ids]

    mbenv._reset_idx = _orig_reset_idx

    # capture before close(): scene tensors are freed on close
    return {
        "series": series,
        "first_done": first_done,
        "start_pos": start_pos,
        "end_pos": end_pos,
        "terminal_frames": captured_frames,
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
             sustain_steps: int, player, terrain_names, policy_label: str, num_steps: int,
             step_dt: float, device: str, push) -> tuple[dict, list, dict | None]:
    """Frozen protocol metrics from the rollout -> (result, segments, recovery).

    ``tilt_cos_min``, ``clearance_min`` and ``sustain_steps`` arrive as arguments rather than
    being derived here: they are the *derived* thresholds the metrics actually used, and the
    record carries the values that ran, not the yaml they were computed from.
    """
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
        "git_rev_lizard": _git_rev(_LIZARD_ROOT) if _LIZARD_ROOT != _ISAAC_GIT_ROOT else "unknown",
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


def _run_dir(run_id: str) -> pathlib.Path:
    """Where this run's artifacts live: protocol dir, optional campaign group, run_id."""
    return _HARNESS_DIR / "results" / args_cli.protocol / (args_cli.group or "") / run_id


def _occupied_refusal(out_dir: pathlib.Path, rec: dict) -> str | None:
    """Why this run_id must not be written, or ``None``. Three cases, answered apart:

    * a readable record -- :func:`record.overwrite_refusal` decides;
    * a run directory with results but **no record** -- a pre-format run, refused exactly like
      a legacy record (0c rule 1): 25 of this harness' 31 run directories are in that state, and
      a tag reused by accident must not overwrite one of them;
    * an **unreadable** record file (truncated, hand-edited) -- refused, because we cannot tell
      what it says, and the caller can replace it explicitly.
    """
    record_path, eval_path = out_dir / "record.json", out_dir / "eval.json"
    if not record_path.is_file():
        return record.overwrite_refusal(record.legacy_run(), rec) if eval_path.is_file() else None
    try:
        previous = record.load(record_path)
    except (OSError, json.JSONDecodeError) as err:
        return f"an existing record is unreadable ({err})"
    return record.overwrite_refusal(previous, rec)


def _guard_writes(out_dir: pathlib.Path, rec: dict, run_id: str) -> None:
    """Refuse an occupied run_id and an incomplete record before anything is written.

    Called as soon as the bindings exist (right after the policy is loaded), so a mistyped
    ``--variant`` is refused in a second rather than after a full rollout, and again in
    ``_persist`` as the last line of defence -- the record is what the table cites.
    """
    if not args_cli.overwrite:
        refusal = _occupied_refusal(out_dir, rec)
        if refusal is not None:
            raise SystemExit(
                f"[EVAL] refusing to write run_id={run_id}: {refusal}. Give this run its own "
                "identity with --variant, or replace the existing record with --overwrite."
            )
    state = record.read_state(rec)
    if state["state"] != "complete":
        raise SystemExit(
            f"[EVAL] refusing to write an {state['state']} record for {run_id}: "
            f"{state['missing'] or state['note']}"
        )


def _atomic_write_json(path: pathlib.Path, payload) -> None:
    """Write JSON through a temporary file: a crash leaves the old file or the new one.

    The record is read back by later runs (the refusal compares against it), so a half-written
    one would make the *next* run fail on garbage instead of on a decision.
    """
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _persist(result: dict, segments: list, recovery: dict | None, run_id: str, tag: str, rec: dict):
    """record.json + eval.json + one summary.csv row (same run_id overwritten).

    Run uniqueness (Step 3.2c) is decided **before anything is written**: a run_id that already
    holds a record which does not compare as comparable is refused, not replaced -- "same name,
    new numbers" is how a table keeps a row nobody can reproduce. A re-run of the same
    measurement is comparable by construction and simply overwrites itself.
    """
    # directory keyed by the protocol FILE stem (stable); the display name stays in the JSON.
    # --group adds a campaign folder that owns both the run dirs and its summary.csv
    out_dir = _run_dir(run_id)
    rec["run"]["timestamp"] = result["timestamp"]
    _guard_writes(out_dir, rec, run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(out_dir / "record.json", rec)
    _atomic_write_json(out_dir / "eval.json", result)

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

    summary_path = out_dir.parent / "summary.csv"
    kept_rows = []
    if summary_path.exists():
        with open(summary_path, encoding="utf-8") as f:
            kept_rows = [r for r in csv.DictReader(f) if r.get("run_id") != run_id]
    summary_tmp = summary_path.with_name(summary_path.name + ".tmp")
    with open(summary_tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(kept_rows)
        writer.writerow(row)
    os.replace(summary_tmp, summary_path)


def main():
    from rl_exp.tools.verify import cfg_snapshot

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

    # The record of conditions (Step 3.2b). Filled where each fact exists -- env-side facts
    # here, the policy in _make_policy, the timeline once the player exists -- and written
    # once in _persist, so a run that dies mid-rollout still leaves nothing half-recorded.
    env_snap = cfg_snapshot.snapshot(env_cfg)
    agent_snap = cfg_snapshot.snapshot(agent_cfg)
    rec: dict = {
        "record_format": record.RECORD_FORMAT,
        "env_cfg": {"digest": cfg_snapshot.digest(env_snap), "snapshot": env_snap},
        "agent_cfg": {
            "digest": cfg_snapshot.digest(agent_snap),
            "snapshot": agent_snap,
            # None is a value here (the wrapper applies no clipping), so it is written as such
            # rather than left empty -- an empty slot in this format means "not recorded"
            "clip_actions": agent_cfg.clip_actions if agent_cfg.clip_actions is not None else "none",
        },
        "suite": _suite_reference(protocol, env_cfg),
        "eval_protocol": _protocol_reference(protocol),
        "obs_protocol": _obs_reference(args_cli.task),
        "assets": _assets_reference(env_cfg),
        "runtime": _runtime_reference(env_cfg, mbenv),
    }
    tag = args_cli.tag or ("ckpt" if args_cli.checkpoint else "random")
    # strip only the gym API suffix of family ids ("-v0" at the very end);
    # teacher recipe versions ("-v1"/"-v2") are part of the run identity
    run_id = f"{re.sub(r'-v0$', '', args_cli.task)}_{tag}_{args_cli.mode}_seed{args_cli.seed}"
    if args_cli.variant:  # a swapped input gets its own identity, not the base run's
        run_id = f"{run_id}_{args_cli.variant}"
    rec["run"] = {
        "run_id": run_id,
        "task": args_cli.task,
        "tag": tag,
        "mode": args_cli.mode,
        "seed": args_cli.seed,
        "protocol_file": args_cli.protocol,
        "variant": args_cli.variant,
        "group": args_cli.group,
    }

    policy, policy_label = _make_policy(wrapper, mbenv, agent_cfg, device, rec)

    player = CommandPlayer(protocol["command_timeline"], mbenv.num_envs, device)
    cmd_term = mbenv.command_manager.get_term("base_velocity")
    fall_cfg = protocol["metrics"]["fall"]
    tilt_cos_min = math.cos(math.radians(float(fall_cfg["tilt_deg"])))
    clearance_min = float(fall_cfg["base_height_ratio"]) * float(env_cfg.scene.robot.init_state.pos[2])
    sustain_steps = max(1, int(round(float(fall_cfg["sustain_s"]) / step_dt)))

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

    # the rest of the conditions: the timeline handed to the player and the windows the
    # metrics cut from it, the thresholds, and (robust) the push as applied. `mbenv.cfg`
    # cannot stand in for any of them -- they are all built after `gym.make`.
    rec["commands"] = {
        "timeline": protocol["command_timeline"],
        "segments": player.segments(num_steps * step_dt, step_dt),
    }
    rec["metrics"] = {
        "episode_length_s": float(protocol["episode_length_s"]),
        "tracking_lin_threshold_mps": float(protocol["metrics"]["tracking_lin_threshold_mps"]),
        "tracking_ang_threshold_radps": float(protocol["metrics"]["tracking_ang_threshold_radps"]),
        "fall": {key: fall_cfg[key] for key in ("tilt_deg", "base_height_ratio", "sustain_s")},
        "recovery": protocol["metrics"].get("recovery"),
        "step_dt": step_dt,
        "num_steps": num_steps,
        # what the metrics *used*, not the yaml they came from: a changed derivation (a dropped
        # radians, a different initial height) must move the record even when the yaml is frozen
        "derived": {
            "tilt_cos_min": tilt_cos_min,
            "clearance_min": clearance_min,
            "sustain_steps": sustain_steps,
        },
    }
    rec["perturbation"] = _perturbation_reference(protocol, push)

    # every binding now exists, so an occupied run_id or an incomplete record is refused here
    # rather than after the rollout (a mistyped --variant must not cost two minutes)
    _guard_writes(_run_dir(run_id), rec, run_id)

    rollout = _rollout(wrapper, mbenv, robot, policy, player, cmd_term, scanner,
                       center_ray, push, num_steps, step_dt, device)
    gym_env.close()

    result, segments, recovery = _analyze(
        rollout, protocol, tilt_cos_min, clearance_min, sustain_steps, player, terrain_names,
        policy_label, num_steps, step_dt, device, push,
    )

    _persist(result, segments, recovery, run_id, tag, rec)

    print(f"[EVAL] protocol={result['protocol']} mode={result['mode']} run_id={run_id}")
    # v2 hook liveness: it must capture one frame per early-ended episode, so 0
    # here means the private _reset_idx hook went stale on an IsaacLab bump
    print(f"[EVAL] terminal frames captured={rollout['terminal_frames']} "
          f"early_done_envs={(rollout['first_done'] < num_steps).sum().item()}")
    print(f"[EVAL] success={result['global']['success_rate']:.3f} fall={result['global']['fall_rate']:.3f} "
          f"lin_mae={result['global']['lin_mae_mps']:.3f} energy_per_m={result['global']['energy_per_m_j']:.1f}")
    if recovery is not None:
        print(f"[EVAL] recovery_mean={recovery['recovery_time_mean_s']:.2f}s "
              f"never_recovered={recovery['never_recovered_frac']:.2f}")
    # the record's own verdict, so a reader does not have to open the file to know whether
    # the conditions were all recorded (an 'unknown' value is complete, an absent one is not)
    print(f"[EVAL] record={record.RECORD_FORMAT} state={record.read_state(rec)['state']} "
          f"checkpoint={(rec.get('checkpoint') or {}).get('sha256') or 'none'} "
          f"suite={rec['suite']['digest'][:19]} assets={rec['assets']['actual']['verdict']}")
    print(f"[EVAL] wrote results/{args_cli.protocol}/{args_cli.group + '/' if args_cli.group else ''}{run_id}/eval.json")
    print(f"[EVAL] wrote results/{args_cli.protocol}/{args_cli.group + '/' if args_cli.group else ''}{run_id}/record.json")


if __name__ == "__main__":
    main()
    simulation_app.close()
