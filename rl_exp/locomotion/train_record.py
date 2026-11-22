# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Record the source and runtime interface of a training run."""

from importlib.metadata import version
import json
from math import prod
from pathlib import Path
from shutil import copyfile
from subprocess import CalledProcessError
import sys

from rl_exp.tools.runrecord.binding import git_run, sha256_file

_REPO = Path(__file__).resolve().parents[2]
_DIFF_EXCLUDES = tuple(f":(exclude,icase,glob)**/*.{ext}" for ext in ("pt", "usda", "blend", "obj", "stl"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_provenance(run: Path, experiment: Path, usd: str, urdf: Path | None) -> None:
    """Save tracked changes, the experiment file, and imported untracked Python sources."""
    import isaaclab

    framework_source = Path(isaaclab.__file__).resolve().parent
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

    assets = {"usd": {"path": str(usd), "sha256": sha256_file(Path(usd))}}
    if urdf is not None:
        assets["urdf"] = {"path": str(urdf), "sha256": sha256_file(urdf)}
    write_json(run / "provenance.json", {
        "experiment": {"path": str(experiment), "copy": copied_experiment.as_posix()},
        "repository_head": git_head,
        "git_diff": "git.diff" if git_error is None else None,
        "git_error": git_error,
        "copied_sources": sorted(set(copied_sources)),
        "isaaclab": {"source": str(framework_source), "head": git_run(framework_source, "rev-parse", "HEAD") or None,
                     "version": version("isaaclab")},
        "rsl_rl_version": version("rsl-rl-lib"),
        "assets": assets,
    })


def interface_signature(env) -> dict:
    """Read ordered observation and action dimensions from the initialized managers."""
    observations = env.observation_manager
    actions = env.action_manager
    action_terms = []
    for name in actions.active_terms:
        term = actions.get_term(name)
        action_terms.append({"name": name, "width": term.action_dim, "joints": list(term.IO_descriptor.joint_names)})
    return {
        "observations": [
            {"name": group, "terms": [
                {"name": term, "width": prod(shape)}
                for term, shape in zip(terms, observations.group_obs_term_dim[group], strict=True)
            ]}
            for group, terms in observations.active_terms.items()
        ],
        "action_dim": actions.total_action_dim,
        "actions": action_terms,
    }
