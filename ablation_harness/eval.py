# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Evaluate a standalone policy on the locomotion protocol and write eval.json."""

from __future__ import annotations

import argparse
import datetime
import importlib.metadata
from importlib.util import find_spec
from io import BytesIO
import json
import math
import os
import pathlib
import runpy
import subprocess
import sys
import traceback
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Run the entire module under the guard: imports after AppLauncher can fail before main(),
# and Kit may exit 0 during Python shutdown even without an explicit app.close().
if __name__ == "__main__":
    try:
        runner = runpy.run_path(__file__, run_name="__eval_runner__")
        runner["main"]()
        runner["simulation_app"].close()
    except BaseException as exc:
        if isinstance(exc, SystemExit) and (exc.code is None or exc.code == 0):
            raise
        try:
            traceback.print_exc()
            sys.stderr.flush()
            sys.stdout.flush()
        finally:
            os._exit(1)
    sys.exit(0)

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--checkpoint", "--ckpt", required=True, type=pathlib.Path)
parser.add_argument("--checkpoint-sha256", help=argparse.SUPPRESS)
parser.add_argument("--exp", type=pathlib.Path, help="Experiment definition for a historical checkpoint.")
parser.add_argument("--output-dir", type=pathlib.Path)
parser.add_argument("--protocol", default="locomotion_eval_v3")
parser.add_argument("--mode", choices=("nominal", "robust"), default="robust")
parser.add_argument("--seed", type=int, default=123)
parser.add_argument("--envs_per_terrain", type=int, help="Environments per terrain. Defaults to the protocol value.")
parser.add_argument("--allow-drift", action="store_true",
                    help="Allow evaluation when training-time inference config differs from the Run.")
parser.add_argument("--print-suite-fingerprint", action="store_true")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
from ablation_harness.experiment_eval import experiment_files, experiment_source

args_cli.checkpoint = args_cli.checkpoint.resolve()
try:
    args_cli.experiment_files = experiment_files(args_cli.checkpoint, args_cli.exp)
except (OSError, ValueError, KeyError) as exc:
    parser.error(str(exc))
args_cli.task = args_cli.experiment_files[0].stem
args_cli.output_dir = args_cli.output_dir or args_cli.checkpoint.parent / "evaluation" / uuid.uuid4().hex[:8] / "metrics"

if find_spec("isaacsim") is None:
    raise SystemExit("Isaac Sim/Kit is unavailable. PhysX evaluation requires it.")
launcher = AppLauncher(args_cli)
simulation_app = launcher.app
args_cli.device = launcher.device

import torch  # noqa: E402
import yaml  # noqa: E402

from rl_exp.locomotion.env import load_policy, make_env, wrap_env  # noqa: E402

import host_paths  # noqa: E402  (machine-local IsaacLab root, see paths.example.yaml)
import loco_judge  # noqa: E402  (sibling module: the criterion's identity and derivation half)
import metrics  # noqa: E402
import record  # noqa: E402  (sibling module: the eval record format, ARCH_PLAN Step 3.2a)
import suites  # noqa: E402
import suite_lock  # noqa: E402  (sibling module: the suite fingerprint lock, ARCH_PLAN Step 3.3)
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
    "lizard_suite_v2": (suites.LIZARD_SUITE_V2_NAMES, suites.lizard_suite_v2),
}


def _git_rev(repo: pathlib.Path | None) -> str:
    """Commit id of the git repo at ``repo`` ('unknown' if not a repo).

    Evaluation and training provenance use the same fixed-length revision from ``binding``.
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
    from ablation_harness import cfg_snapshot

    layout = protocol.get("suite_layout") or {}
    return {
        "name": protocol["suite"],
        "num_rows": layout.get("num_rows"),
        "num_cols": layout.get("num_cols"),
        "envs_per_terrain": layout.get("envs_per_terrain"),
        "terrains": list(_SUITE_REGISTRY[protocol["suite"]][0]),
        "digest": cfg_snapshot.digest(cfg_snapshot.snapshot(env_cfg.scene.terrain)),
    }


def _physx_version() -> str:
    """The PhysX build the simulator runs, or 'unknown'.

    Named in the geometry fingerprint because terrain meshes are generated *by the engine*: the same
    suite config on a different solver build is not the same ground, so the engine has to be a
    recorded fact rather than an assumption. Three spellings across Isaac Sim releases (the ext
    cache's distribution, the extension's package, the runtime's own report); none answering is
    'unknown' and never a guess, which is what keeps an unnamed engine from reading as a known one.
    """
    for name in ("isaacsim-extscache-physics", "omni.physx"):
        version = _package_version(name)
        if version != record.UNKNOWN:
            return version
    try:
        import omni.physx

        return str(omni.physx.get_physx_interface().get_physx_version())
    except Exception:  # no extension, no app, or no such accessor -- all 'unknown'
        return record.UNKNOWN


def _geometry_env() -> dict:
    """The environment a geometry digest is comparable in.

    Recorded so a mismatch can be attributed: the same fingerprint differing on a different engine
    or GPU stack is *unknown*, not a protocol change. Without this the two would be one red, and a
    machine swap would read as a terrain edit.
    """
    gpu, capability = record.UNKNOWN, record.UNKNOWN
    try:
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
            capability = ".".join(str(part) for part in torch.cuda.get_device_capability(0))
    except Exception:
        pass
    return {
        "sim_version": _package_version("isaacsim"),
        "physx_version": _physx_version(),
        "numpy_version": _package_version("numpy"),
        "warp_version": _package_version("warp-lang"),
        "torch_version": _package_version("torch"),
        "gpu": gpu,
        "gpu_compute_capability": capability,
        "git_rev_isaaclab": _git_rev(_ISAAC_ROOT),
    }


def _print_suite_fingerprint(protocol: dict, cfg_digest: str, geometry_digest: str) -> None:
    """The block to paste into ``suite_expected``: approving a fingerprint is a deliberate act.

    This is the one path that writes nothing. A gate that filled in its own expectation would
    approve whatever the machine happened to produce, which is the opposite of freezing it.
    """
    print(f"[EVAL] paste into protocols/{args_cli.protocol}.yaml under suite_expected:")
    print(suite_lock.fingerprint_block(protocol, cfg_digest, geometry_digest, _geometry_env()))




def _runtime_reference(mbenv) -> dict:
    """Identify the simulator and environment that produced the measurements."""
    return {
        "device": str(getattr(mbenv, "device", record.UNKNOWN)),
        "num_envs": int(getattr(mbenv, "num_envs", -1)),
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


def _prepare_env(protocol: dict) -> tuple[object, object, str, tuple[BytesIO, dict, dict], dict, dict]:
    """Load the experiment and apply the evaluation protocol."""
    from ablation_harness.experiment_eval import (
        checkpoint_signature,
        checkpoint_snapshot,
        configurations,
        height_scanner_prim_path,
    )

    env_cfg, agent_cfg, assets, config_check, experiment = configurations(
        args_cli.experiment_files,
        checkpoint=args_cli.checkpoint,
        allow_drift=args_cli.allow_drift,
    )
    stream, binding = checkpoint_snapshot(args_cli.checkpoint, args_cli.checkpoint_sha256)
    pinned_checkpoint = stream, binding, checkpoint_signature(stream, binding)

    suite_factory = _SUITE_REGISTRY[protocol["suite"]][1]
    num_cols = int(protocol["suite_layout"]["num_cols"])
    if args_cli.envs_per_terrain is None:
        args_cli.envs_per_terrain = int(protocol["suite_layout"]["envs_per_terrain"])

    env_cfg.scene.terrain = suite_factory()
    suites.bind_head_ground_to_terrain(env_cfg)
    env_cfg.scene.num_envs = args_cli.envs_per_terrain * num_cols
    env_cfg.episode_length_s = float(protocol["episode_length_s"])
    env_cfg.seed = args_cli.seed
    if env_cfg.curriculum is not None:
        env_cfg.curriculum.terrain_levels = None  # fixed suite: no terrain roaming
    if args_cli.device is not None:
        env_cfg.sim.device = args_cli.device
    apply_eval_mode(env_cfg, args_cli.mode)
    from isaaclab.sensors import RayCasterCfg, patterns

    # Evaluation-only ground clearance at the root XY. It stays outside the policy inputs.
    env_cfg.scene.height_scanner = RayCasterCfg(
        prim_path=height_scanner_prim_path(env_cfg, experiment),
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
        ray_alignment="world", mesh_prim_paths=["/World/ground"],
        pattern_cfg=patterns.GridPatternCfg(resolution=0.1, size=(0.0, 0.0)),
    )
    # The suite as the harness built it, digestible before the simulator starts: the check that can
    # refuse a wrong ground without paying for an app launch.
    from ablation_harness import cfg_snapshot

    suite_cfg_digest = cfg_snapshot.digest(cfg_snapshot.snapshot(env_cfg.scene.terrain))
    return env_cfg, agent_cfg, suite_cfg_digest, pinned_checkpoint, assets, config_check


def _make_policy(wrapper, env, agent_cfg, rec: dict, pinned_checkpoint):
    """Check the runtime interface before loading the same verified checkpoint bytes."""
    from ablation_harness.experiment_eval import check_signature
    from rl_exp.locomotion.run import interface_signature

    stream, binding, expected = pinned_checkpoint
    actual = interface_signature(env)
    check_signature(expected, actual)
    rec["interface_signature"] = actual
    rec["checkpoint"] = binding
    agent_cfg.seed = args_cli.seed
    return load_policy(wrapper, agent_cfg, stream, env.device)

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
        snap["clearance"] = torch.where(torch.isfinite(terrain_z), data.root_pos_w.torch[:, 2] - terrain_z, torch.nan)
    return snap


def _rollout(wrapper, mbenv, robot, policy, player, cmd_term, scanner, center_ray,
             push, num_steps: int, step_dt: float, device: str) -> dict:
    """One protocol episode per env; data frozen after each env's first done.

    Frames are the **post-physics, pre-reset** states (Locomotion-Eval-v2): the
    frame the reward and the terminations actually saw. v1 sampled the pre-step
    state instead -- one ``step_dt`` early, and blind to each episode's terminal
    frame, which the auto-reset inside ``step()`` overwrites before it can be
    read (see ``protocols/locomotion_eval_v3.yaml`` for why that last frame
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
    windows = player.segments(num_steps * step_dt, step_dt)
    segments = [
        s for s in (
            _segment_stats(seg, lin_err, ang_err, succ, lin_vel_b, valid, step_axis)
            for seg in windows
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
    samples = {}
    for col, name in enumerate(terrain_names):
        subset = rollout["terrain_types"] == col
        terrain_valid = valid[:, subset]
        rows = []
        for segment in windows:
            window = ((step_axis >= segment["start_s"]) & (step_axis < segment["end_s"])).squeeze(1)
            mask = terrain_valid[window]
            row = {"name": segment["name"], "window_s": [segment["start_s"], segment["end_s"]],
                   "valid_steps": int(mask.sum()), "valid_envs": int(mask.any(dim=0).sum())}
            if row["valid_steps"]:
                row["lin_mae_mps"] = float(lin_err[window][:, subset][mask].mean())
                row["ang_mae_radps"] = float(ang_err[window][:, subset][mask].mean())
                if all(v == 0.0 for v in segment["cmd"]):
                    speed = torch.linalg.vector_norm(lin_vel_b[window][:, subset, :2], dim=-1)
                    row["stop_mean_residual_mps"] = float(speed[mask].mean())
            else:
                row.update(lin_mae_mps=None, ang_mae_radps=None, missing_reason="no valid samples")
            rows.append(row)
        samples[name] = {"envs": int(subset.sum()), "segments": rows}
    result["report_only"] = {
        "samples_by_terrain": samples,
        "early_terminations": int((first_done < num_steps - 1).sum()),
    }
    hits = torch.isfinite(clearance) & valid if clearance is not None else torch.zeros_like(valid)
    result["report_only"]["fall_clearance"] = {
        "valid_steps": int(hits.sum()), "missing_steps": int((valid & ~hits).sum())
    }
    if not bool(hits.any()):
        result["report_only"]["fall_clearance"]["missing_reason"] = "No clearance samples; fall rate uses tilt only."
    if not any(all(v == 0.0 for v in segment["cmd"]) for segment in windows):
        result["report_only"]["stop_residual"] = {"value": None, "missing_reason": "no stop segment in protocol"}
    result["protocol_judgment"] = {
        "tracking_success_rate": result["global"]["success_rate"],
        "tracking_step_thresholds": [m_cfg["tracking_lin_threshold_mps"], m_cfg["tracking_ang_threshold_radps"]],
        "overall_pass": None,
        "reason": "the protocol defines per-step criteria, not an overall pass threshold",
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
        if not math.isfinite(recovery["recovery_time_mean_s"]):
            recovery["missing_reason"] = "no recovery samples" if surviving.numel() == 0 else "no environment recovered"
        result["recovery"] = recovery
    elif args_cli.mode == "robust":
        result["recovery"] = {"measured_envs": 0, "missing_reason": "protocol does not declare a recovery push"}

    return result, segments, recovery




def _atomic_write_json(path: pathlib.Path, payload) -> None:
    """Write JSON through a temporary file: a crash leaves the old file or the new one.

    The record is read back by later runs (the refusal compares against it), so a half-written
    one would make the *next* run fail on garbage instead of on a decision.
    """
    path.parent.mkdir(parents=True, exist_ok=True)  # terrain/ sits one level below the run dir
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _null_nonfinite(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _null_nonfinite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_null_nonfinite(item) for item in value]
    return value




def main():
    from ablation_harness.terrain_geometry import evidence, seed_rngs
    from ablation_harness import cfg_snapshot, terrain_split_probe

    protocol = _load_protocol(args_cli.protocol)
    terrain_names = _SUITE_REGISTRY[protocol["suite"]][0]

    source = experiment_source(args_cli.checkpoint, args_cli.experiment_files)
    env_cfg, agent_cfg, suite_cfg_digest, pinned_checkpoint, assets, config_check = _prepare_env(protocol)
    source["config_check"] = config_check
    # Step one of the suite lock: the cfg is the harness' own declaration, so a mismatch is
    # definitive and is answered before the simulator starts.
    cfg_lock = suite_lock.compare(protocol, suite_cfg_digest, record.UNKNOWN, _geometry_env())
    refusal = suite_lock.start_refusal(protocol, cfg_lock, stage="cfg")
    if refusal is not None:
        raise SystemExit(f"[EVAL] refused: {refusal}")
    # The suite's ground is pinned by the suite's own seed, not by --seed: every eval of every
    # run has to stand on the same terrain, which needs the global streams the terrain functions
    # draw from (the generator seeds only its own local rng). Without this the rough columns are
    # a different terrain in every eval.
    seed_rngs(suites.SUITE_SEED)
    terrain_split_probe.install()
    gym_env = make_env(env_cfg)
    mbenv = gym_env.unwrapped
    wrapper = wrap_env(gym_env, agent_cfg)
    robot = mbenv.scene["robot"]
    device = mbenv.device
    step_dt = mbenv.step_dt
    num_steps = int(round(float(protocol["episode_length_s"]) / step_dt))

    env_snap = cfg_snapshot.snapshot(env_cfg)
    agent_snap = cfg_snapshot.snapshot(agent_cfg)
    rec: dict = {
        "env_cfg": {"digest": cfg_snapshot.digest(env_snap), "snapshot": env_snap},
        "agent_cfg": {
            "digest": cfg_snapshot.digest(agent_snap),
            "snapshot": agent_snap,
            # None is a value here (the wrapper applies no clipping), so it is written as such
            # rather than left empty -- an empty slot in this format means "not recorded"
            "clip_actions": agent_cfg.clip_actions if agent_cfg.clip_actions is not None else "none",
        },
        "suite": _suite_reference(protocol, env_cfg),
        "judge": loco_judge.judge_reference(),
        "eval_protocol": _protocol_reference(protocol),
        "runtime": _runtime_reference(mbenv),
    }
    rec["assets"] = assets
    rec["experiment"] = source

    # what this run actually stood on: the per-cell geometry digests, captured where the
    # generator handed the mesh over. A reader can compare the ground from two runs without
    # regenerating either suite.
    # The cells also carry their relief, which is the number that says whether a column the
    # protocol calls "rough" is rough for this robot's foot.
    terrain_record = terrain_split_probe.record_for(mbenv.scene.terrain)
    rec["suite"]["geometry_digest"] = terrain_record["geometry_digest"]
    # Step two of the suite lock: the ground itself, which only exists once the generator handed the
    # meshes over. Refused here rather than after the rollout, so a run on the wrong ground costs a
    # construction and not a measurement.
    suite_lock_state = suite_lock.compare(protocol, suite_cfg_digest,
                                         terrain_record["geometry_digest"], _geometry_env())
    if args_cli.print_suite_fingerprint:
        _print_suite_fingerprint(protocol, suite_cfg_digest, terrain_record["geometry_digest"])
        # Return rather than exit: the module's own shutdown path closes the app, and a SystemExit
        # here would skip it -- the failure mode this harness already paid for once, where Kit's
        # shutdown swallowed the exit and the process hung with nothing to read.
        return
    refusal = suite_lock.start_refusal(protocol, suite_lock_state, stage="geometry")
    if refusal is not None:
        raise SystemExit(f"[EVAL] refused: {refusal}")
    rec["suite"]["lock"] = {"verdict": suite_lock_state["verdict"], "cfg": suite_lock_state["cfg"],
                            "geometry": suite_lock_state["geometry"]}
    rec["suite"]["geometry_env"] = suite_lock_state["geometry_env"]
    rec["suite"]["expected"] = suite_lock_state["declared"]
    rec["run"] = {"task": args_cli.task, "mode": args_cli.mode, "seed": args_cli.seed, "protocol_file": args_cli.protocol}
    policy = _make_policy(wrapper, mbenv, agent_cfg, rec, pinned_checkpoint)

    player = CommandPlayer(protocol["command_timeline"], mbenv.num_envs, device)
    cmd_term = mbenv.command_manager.get_term("base_velocity")
    fall_cfg = protocol["metrics"]["fall"]
    # The declaration as the numbers `fall_flags` is handed. The arithmetic lives in loco_judge,
    # where it is reachable without a simulator: it is half of this run's judge.id, and a dwell off
    # by one step or a clearance measured from the wrong height is invisible in a passing rollout.
    derived = loco_judge.derived_thresholds(
        protocol,
        stand_height_m=float(env_cfg.scene.robot.init_state.pos[2]),
        step_dt=step_dt,
    )
    tilt_cos_min = derived["tilt_cos_min"]
    clearance_min = derived["clearance_min"]
    sustain_steps = derived["sustain_steps"]

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
    # cannot stand in for any of them: they are built from the running scene.
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

    output = args_cli.output_dir / "eval.json"
    if output.exists():
        raise FileExistsError(f"Evaluation output already exists: {output}")

    rollout = _rollout(wrapper, mbenv, robot, policy, player, cmd_term, scanner,
                       center_ray, push, num_steps, step_dt, device)
    gym_env.close()

    result, _, recovery = _analyze(
        rollout, protocol, tilt_cos_min, clearance_min, sustain_steps, player, terrain_names,
        str(args_cli.checkpoint), num_steps, step_dt, device, push,
    )

    ground = evidence(terrain_record, identity={
        "suite": protocol["suite"], "seed": suites.SUITE_SEED,
        "task": args_cli.task, "protocol": args_cli.protocol, "mode": args_cli.mode,
    })
    result["conditions"] = rec
    result["terrain_evidence"] = ground
    _atomic_write_json(output, _null_nonfinite(result))
    print(f"[EVAL] protocol={result['protocol']} mode={result['mode']}")

    # v2 hook liveness: it captures one frame per reset the rollout caused, so 0 means the
    # private _reset_idx hook went stale on an IsaacLab bump. ``dones`` is
    # ``truncated | terminated`` (termination_manager.py:104), and time_out fires on the last
    # step -- so *every* surviving env resets there and the two numbers are whole-run counts,
    # not early-only ones: printing the total as "early done" reads as "72/72 envs fell over
    # mid-episode" when the truth was none (measured 2026-09-20).
    resets_in_rollout = (rollout["first_done"] < num_steps).sum().item()
    early_terminations = (rollout["first_done"] < num_steps - 1).sum().item()
    print(f"[EVAL] terminal frames captured={rollout['terminal_frames']} "
          f"resets_in_rollout={resets_in_rollout} early_terminations={early_terminations}")
    print(f"[EVAL] success={result['global']['success_rate']:.3f} fall={result['global']['fall_rate']:.3f} "
          f"lin_mae={result['global']['lin_mae_mps']:.3f} energy_per_m={result['global']['energy_per_m_j']:.1f}")
    if recovery is not None:
        print(f"[EVAL] recovery_mean={recovery['recovery_time_mean_s']:.2f}s "
              f"never_recovered={recovery['never_recovered_frac']:.2f}")
    print(f"[EVAL] wrote {output}")
