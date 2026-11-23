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

from rl_exp.locomotion.train_record import asset_fingerprints
from rl_exp.tools.runrecord.binding import sha256_bytes

_REPO = Path(__file__).resolve().parents[1]


def experiment_files(checkpoint: Path, explicit: Path | None) -> tuple[Path, Path | None]:
    """Find the experiment in the current checkout and its Run, if available."""
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
    experiment = (_REPO / entry["repo_path"] if "repo_path" in entry else Path(entry["path"])).resolve()
    if not experiment.is_file():
        raise ValueError(f"Restore the Run's experiment to {experiment}, or supply it with --exp.")
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


def configurations(files: tuple[Path, Path | None], *, play: bool = False):
    """Construct fresh environment and runner configs for a checkpoint."""
    from isaaclab_rl.rsl_rl import handle_deprecated_rsl_rl_cfg

    path, resolved = files
    spec = spec_from_file_location("_robot_training_experiment", path)
    experiment = module_from_spec(spec)
    sys.modules[spec.name] = experiment
    spec.loader.exec_module(experiment)
    env_cfg = experiment.make_env_cfg(play=True) if play else experiment.make_env_cfg()
    runner_cfg = handle_deprecated_rsl_rl_cfg(experiment.make_runner_cfg(), version("rsl-rl-lib"))
    urdf = getattr(experiment, "URDF_PATH", None)
    assets = asset_fingerprints(env_cfg.scene.robot.spawn.usd_path, urdf)
    if resolved is not None:
        provenance = json.loads(resolved.with_name("provenance.json").read_text(encoding="utf-8"))
        for kind, asset in provenance["assets"].items():
            current = assets.get(kind, {})
            for key in ("sha256", "dependencies"):
                if key in asset and (asset[key] is None or asset[key] != current.get(key)):
                    raise ValueError(f"{kind.upper()} {key} differs from the training Run: {current.get('path')}")
    return env_cfg, runner_cfg, assets


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


def checkpoint_signature(checkpoint: BytesIO, binding: dict) -> dict:
    """Read the embedded signature or the signature measured once for a legacy checkpoint."""
    import torch

    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    signature = (payload.get("infos") or {}).get("interface_signature")
    if signature is not None:
        return signature
    path = Path(binding["path"])
    sidecar = path.with_suffix(path.suffix + ".interface.json")
    if not sidecar.is_file():
        raise ValueError(f"Checkpoint has no interface signature. Expected legacy signature: {sidecar}")
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    if record["sha256"] != binding["sha256"]:
        raise ValueError(f"Legacy interface signature belongs to a different checkpoint: {sidecar}")
    return record["interface_signature"]


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
    elif isinstance(expected, list) and isinstance(actual, list):
        for index, (left, right) in enumerate(zip(expected, actual)):
            _require_match(left, right, f"{path}[{index}]")
        if len(expected) != len(actual):
            index = min(len(expected), len(actual))
            raise ValueError(f"{path}[{index}] mismatch: expected length {len(expected)}, got {len(actual)}")
    elif expected != actual:
        raise ValueError(f"{path} mismatch: expected {expected!r}, got {actual!r}")
