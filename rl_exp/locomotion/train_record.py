# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Record the source and runtime interface of a training run."""

from importlib.metadata import version
import json
from math import prod
import os
from pathlib import Path
from shutil import copyfile
from subprocess import CalledProcessError
import sys
from xml.etree import ElementTree

from rl_exp.tools.runrecord.binding import git_run, sha256_file

_REPO = Path(__file__).resolve().parents[2]
_DIFF_EXCLUDES = tuple(f":(exclude,icase,glob)**/*.{ext}" for ext in ("pt", "usda", "blend", "obj", "stl"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def asset_fingerprints(usd: str, urdf: Path | None) -> dict:
    """Record the USD dependency graph and any URDF meshes beside it."""
    from pxr import UsdUtils

    usd_path = Path(usd).resolve()
    layers, assets, missing = UsdUtils.ComputeAllDependencies(str(usd_path))
    if missing:
        raise FileNotFoundError(f"Unresolved dependencies of {usd_path}: {missing}")

    def fingerprint(path: Path, dependencies) -> dict:
        def digest(file: Path) -> str:
            value = sha256_file(file)
            if value is None:
                raise FileNotFoundError(f"Asset is unreadable: {file}")
            return value

        files = {file.resolve() for file in dependencies}
        files.discard(path)
        return {
            "path": str(path),
            "sha256": digest(path),
            "dependencies": {
                Path(os.path.relpath(file, path.parent)).as_posix() if file.anchor == path.anchor else file.as_posix():
                digest(file) for file in sorted(files)
            },
        }

    result = {"usd": fingerprint(usd_path, [*(Path(layer.realPath) for layer in layers), *(Path(str(p)) for p in assets)])}
    if urdf is not None:
        urdf = urdf.resolve()
        meshes = (urdf.parent / mesh.attrib["filename"] for mesh in ElementTree.parse(urdf).iter("mesh"))
        result["urdf"] = fingerprint(urdf, meshes)
    return result


def write_provenance(run: Path, experiment: Path, usd: str, urdf: Path | None) -> None:
    """Save tracked changes, the experiment file, and imported untracked Python sources."""
    import isaaclab

    framework_source = Path(isaaclab.__file__).resolve().parent
    framework_root = git_run(framework_source, "rev-parse", "--show-toplevel")
    framework = {"source": str(framework_source), "head": git_run(framework_source, "rev-parse", "HEAD") or None,
                 "version": version("isaaclab")}
    if framework_root:
        framework_diff = git_run(Path(framework_root), "diff", "HEAD", "--no-ext-diff", strip_output=False, check=True)
        if framework_diff:
            (run / "isaaclab.diff").write_text(framework_diff, encoding="utf-8", newline="\n")
            framework["git_diff"] = "isaaclab.diff"
    git_head = git_run(_REPO, "rev-parse", "HEAD") or None
    git_error = None
    untracked = None
    try:
        diff = git_run(_REPO, "diff", "HEAD", "--no-ext-diff", "--", ".", *_DIFF_EXCLUDES,
                       strip_output=False, check=True)
        output = git_run(_REPO, "ls-files", "--others", "--exclude-standard", "-z",
                         strip_output=False, check=True)
        untracked = set(output.split("\0"))
        (run / "git.diff").write_text(diff, encoding="utf-8", newline="\n")
    except CalledProcessError as error:
        git_error = error.stderr.strip()
    except OSError as error:
        git_error = str(error)

    copied_experiment = Path("experiment") / experiment.name
    (run / copied_experiment.parent).mkdir()
    copyfile(experiment, run / copied_experiment)

    copied_sources = []
    for module in tuple(sys.modules.values()):
        origin = getattr(module, "__file__", None)
        if not origin or not origin.endswith(".py"):
            continue
        source = Path(origin).resolve()
        if source == experiment or not source.is_relative_to(_REPO) or not source.is_file():
            continue
        relative = source.relative_to(_REPO)
        if untracked is not None and relative.as_posix() not in untracked:
            continue
        target = run / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source, target)
        copied_sources.append(relative.as_posix())

    entry = {"path": str(experiment), "copy": copied_experiment.as_posix()}
    if experiment.is_relative_to(_REPO):
        entry["repo_path"] = experiment.relative_to(_REPO).as_posix()
    write_json(run / "provenance.json", {
        "experiment": entry,
        "repository_head": git_head,
        "git_diff": "git.diff" if git_error is None else None,
        "git_error": git_error,
        "copied_sources": sorted(set(copied_sources)),
        "isaaclab": framework,
        "rsl_rl_version": version("rsl-rl-lib"),
        "assets": asset_fingerprints(usd, urdf),
    })


def interface_signature(env) -> dict:
    """Read ordered observation and action dimensions from the initialized managers."""
    observations = env.observation_manager
    actions = env.action_manager
    action_terms = []
    for name in actions.active_terms:
        term = actions.get_term(name)
        descriptor = getattr(term, "IO_descriptor", None)
        joints = getattr(descriptor, "joint_names", None)
        action = {"name": name, "width": term.action_dim}
        if joints is not None:
            action["joints"] = list(joints)
        action_terms.append(action)
    observation_groups = []
    for group, names in observations.active_terms.items():
        group_cfg = getattr(observations.cfg, group)
        terms = []
        for name, shape in zip(names, observations.group_obs_term_dim[group], strict=True):
            term = {"name": name, "width": prod(shape)}
            if name in {"joint_pos", "joint_vel"}:
                entity = getattr(group_cfg, name).params.get("asset_cfg")
                robot = env.scene[entity.name if entity is not None else "robot"]
                indices = entity.joint_ids if entity is not None else slice(None)
                term["joints"] = (list(robot.joint_names[indices]) if isinstance(indices, slice)
                                  else [robot.joint_names[i] for i in indices])
            terms.append(term)
        observation_groups.append({"name": group, "terms": terms})
    return {
        "observations": observation_groups,
        "action_dim": actions.total_action_dim,
        "actions": action_terms,
    }
