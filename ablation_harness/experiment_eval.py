# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Load a standalone experiment and check policy input and output order."""

from importlib.metadata import version
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
import json
import os
from pathlib import Path
import sys

from rl_exp.locomotion.train_record import interface_signature
from rl_exp.tools.runrecord.binding import sha256_bytes, sha256_file


def experiment_files(checkpoint: Path, explicit: Path | None) -> tuple[Path, Path | None]:
    """Use the Run's experiment copy and resolved configuration unless an experiment is supplied."""
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")
    if explicit is not None:
        if not explicit.is_file() or explicit.suffix != ".py":
            raise ValueError(f"--exp must identify an existing Python file: {explicit}")
        return explicit.resolve(), None
    run = checkpoint.parent
    provenance = run / "provenance.json"
    resolved = run / "resolved_cfg.yaml"
    if not provenance.is_file() or not resolved.is_file():
        raise ValueError("Checkpoint has no training Run configuration. Supply its experiment with --exp.")
    entry = json.loads(provenance.read_text(encoding="utf-8"))["experiment"]
    experiment = (run / entry["copy"]).resolve()
    if not experiment.is_relative_to(run.resolve()) or not experiment.is_file():
        raise ValueError(f"Training Run's experiment copy is missing or invalid: {experiment}")
    return experiment, resolved


def resolved_config(path: Path) -> dict:
    """Read a saved Isaac Lab config including its unresolved scene indices."""
    import yaml

    class ConfigLoader(yaml.FullLoader):
        pass

    ConfigLoader.add_constructor(
        "tag:yaml.org,2002:python/object/apply:builtins.slice",
        lambda loader, node: slice(*loader.construct_sequence(node)),
    )
    return yaml.load(path.read_text(encoding="utf-8"), Loader=ConfigLoader)


def configurations(files: tuple[Path, Path | None]):
    """Construct fresh environment and runner configs for a checkpoint."""
    from isaaclab_rl.rsl_rl import handle_deprecated_rsl_rl_cfg

    path, resolved = files
    spec = spec_from_file_location("_robot_training_experiment", path)
    experiment = module_from_spec(spec)
    sys.modules[spec.name] = experiment
    spec.loader.exec_module(experiment)
    env_cfg = experiment.make_env_cfg()
    runner_cfg = handle_deprecated_rsl_rl_cfg(experiment.make_runner_cfg(), version("rsl-rl-lib"))
    if resolved is not None:
        saved = resolved_config(resolved)
        # The saved experiment supplies all experiment settings. Restore the
        # fields the training CLI can override, before applying eval settings.
        env_cfg.seed = saved["env"]["seed"]
        env_cfg.scene.num_envs = saved["env"]["scene"]["num_envs"]
        env_cfg.sim.device = saved["env"]["sim"]["device"]
        runner_cfg.seed = saved["runner"]["seed"]
        runner_cfg.device = saved["runner"]["device"]
        runner_cfg.max_iterations = saved["runner"]["max_iterations"]
        provenance = json.loads(resolved.with_name("provenance.json").read_text(encoding="utf-8"))
        current_assets = {"usd": env_cfg.scene.robot.spawn.usd_path, "urdf": getattr(experiment, "URDF_PATH", None)}
        for kind, asset in provenance["assets"].items():
            current = current_assets[kind]
            if current is None or sha256_file(Path(current)) != asset["sha256"]:
                raise ValueError(f"{kind.upper()} differs from the training Run: {current}")

        actual_env = env_cfg.to_dict()
        saved_env = saved["env"]
        # Output location may move. The USD path is already checked by content.
        actual_env.pop("log_dir", None)
        saved_env.pop("log_dir", None)
        actual_env["scene"]["robot"]["spawn"].pop("usd_path", None)
        saved_env["scene"]["robot"]["spawn"].pop("usd_path", None)
        _require_match(saved_env, actual_env, "Run environment config")
        _require_match(saved["runner"], runner_cfg.to_dict(), "Run runner config")
    return env_cfg, runner_cfg, getattr(experiment, "LEGACY_TASK", None)


def checkpoint_snapshot(checkpoint: Path, expected_sha256: str | None = None) -> tuple[BytesIO, dict]:
    """Pin the exact bytes used for signature checks and inference in this process."""
    with checkpoint.open("rb") as handle:
        content = handle.read()
        stat = os.fstat(handle.fileno())
    digest = sha256_bytes(content)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"Checkpoint changed before loading: {checkpoint}")
    return BytesIO(content), {
        "path": str(checkpoint), "resolved": str(checkpoint.resolve()), "sha256": digest,
        "size": len(content), "mtime": round(stat.st_mtime, 6),
    }


def checkpoint_signature(checkpoint: BytesIO, legacy_task: str | None, device: str) -> dict:
    """Read the embedded signature, or measure the declared legacy environment once."""
    import torch

    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    signature = (payload.get("infos") or {}).get("interface_signature")
    if signature is not None:
        return signature
    if legacy_task is None:
        raise ValueError("Checkpoint has no interface signature and the experiment declares no legacy task.")

    import gymnasium as gym
    from isaaclab.envs import ManagerBasedRLEnv
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    import rl_exp.tasks  # Registers the explicitly requested historical reference.

    entry = gym.spec(legacy_task).kwargs["env_cfg_entry_point"]
    cfg = resolve_presets(string_to_callable(entry)())
    cfg.scene.num_envs = 1
    cfg.seed = 123
    cfg.sim.device = device
    env = ManagerBasedRLEnv(cfg=cfg)
    try:
        return interface_signature(env)
    finally:
        env.close()


def check_signature(expected: dict, actual: dict) -> None:
    """Reject the first ordered observation or action mismatch before loading policy weights."""
    _require_match(expected, actual, "Checkpoint interface")


def _require_match(expected, actual, path: str) -> None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in expected:
            if key not in actual:
                raise ValueError(f"{path}.{key} is missing")
            _require_match(expected[key], actual[key], f"{path}.{key}")
        unexpected = next((key for key in actual if key not in expected), None)
        if unexpected is not None:
            raise ValueError(f"{path}.{unexpected} was not in the saved definition")
    elif isinstance(expected, (list, tuple)) and type(expected) is type(actual) and len(expected) == len(actual):
        for index, (left, right) in enumerate(zip(expected, actual)):
            _require_match(left, right, f"{path}[{index}]")
    elif expected != actual:
        raise ValueError(f"{path} mismatch: expected {expected!r}, got {actual!r}")
