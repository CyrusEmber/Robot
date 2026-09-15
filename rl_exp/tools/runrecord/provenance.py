# -*- coding: utf-8 -*-
"""Code provenance: which code a run (or a baseline) actually depended on.

Shared by the run manifest (what a run was) and the recipe golden lock (which
framework combination a baseline belongs to), so the *rule* for identifying a
dependency exists once:

* a git work tree is identified by revision + the digest of ``git diff HEAD`` +
  the porcelain status digest, plus the names of untracked files;
* an editable-installed package is identified by its source tree, an installed one
  by its distribution version -- the two are not interchangeable, because only the
  first can be brought back by name;
* untracked files are the honest weak spot: a revision hash cannot restore them, so
  they are listed and flagged as needing an archive.

Paths are relativized through :mod:`cfg_snapshot` so a record stays comparable
across machines.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import pathlib
import subprocess
import sys
from datetime import datetime

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.verify.cfg_snapshot import relativize  # noqa: E402

UNTRACKED_CAP = 40


def git(root: pathlib.Path | None, *args: str) -> str:
    """Run git in ``root``; return stdout, or "" when git cannot answer."""
    if root is None:
        return ""
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, cwd=root
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def rev(root: pathlib.Path | None, short: int = 12) -> str:
    """Revision of a work tree, or "" when it is not one."""
    return git(root, "rev-parse", "HEAD")[:short]


def now() -> str:
    """Local timestamp with offset, one format for every record this repo writes."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: pathlib.Path | None, chunk: int = 1 << 20) -> str | None:
    """Content hash of a file, or None when it cannot be read."""
    if path is None:
        return None
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(chunk), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def git_state(root: pathlib.Path | None, label: str) -> dict:
    """Provenance of one git work tree.

    Args:
        root: the work tree root, or None when it could not be resolved.
        label: name used in the ``available: False`` explanation.

    Returns:
        Revision, dirty flag, diff and status digests, and the untracked file list.
    """
    if root is None:
        return {"available": False, "detail": f"{label} root unresolved"}
    head = rev(root)
    if not head:
        return {"available": False, "detail": f"{root} is not a git work tree"}
    porcelain = git(root, "status", "--porcelain=v2")
    status_lines = porcelain.splitlines()
    untracked = sorted(line.split(" ", 1)[1] for line in status_lines if line.startswith("? "))
    diff = git(root, "diff", "HEAD")
    return {
        "available": True,
        "root": relativize(str(root)),
        "rev": head,
        "dirty": bool(status_lines),
        "status_porcelain_sha256": sha256_bytes(porcelain.encode("utf-8")),
        "diff_sha256": sha256_bytes(diff.encode("utf-8")),
        "diff_lines": len(diff.splitlines()),
        "untracked_count": len(untracked),
        "untracked": untracked[:UNTRACKED_CAP],
        "untracked_requires_archive": bool(untracked),
    }


def isaac_root() -> pathlib.Path | None:
    """The host IsaacLab tree: env override first, then the repo's own resolver."""
    stated = os.environ.get("RL_ISAAC_ROOT")
    if stated:
        return pathlib.Path(stated)
    try:
        from ablation_harness.host_paths import isaac_root as resolve

        return resolve()
    except Exception:  # noqa: BLE001 - an unresolved host path is recorded, not fatal
        return None


def rsl_rl_state() -> dict:
    """rsl_rl provenance: source tree when editable, distribution version when installed."""
    try:
        spec = importlib.util.find_spec("rsl_rl")
    except (ImportError, ValueError):
        spec = None
    origin = getattr(spec, "origin", None) if spec is not None else None
    if origin:
        package_dir = pathlib.Path(origin).resolve().parent
        tree = git(package_dir, "rev-parse", "--show-toplevel")
        if tree:
            state = git_state(pathlib.Path(tree), "rsl_rl")
            state["mode"] = "editable/source"
            return state
    try:
        from importlib.metadata import version

        return {"available": True, "mode": "installed", "distribution_version": version("rsl_rl")}
    except Exception as err:  # noqa: BLE001 - record the gap, never crash a run
        return {"available": False, "detail": f"{type(err).__name__}: {err}"}


def rsl_rl_id() -> str:
    """One short string identifying the rsl_rl that is importable right now."""
    state = rsl_rl_state()
    if not state.get("available"):
        return "unknown"
    if state.get("mode") == "installed":
        return f"installed:{state.get('distribution_version')}"
    return f"source:{state.get('rev')}"


def code_sources() -> dict:
    """All code the run depends on, recorded from what is actually importable."""
    return {
        "repository": git_state(_REPO, "repository"),
        "isaaclab": git_state(isaac_root(), "isaaclab"),
        "rsl_rl": rsl_rl_state(),
    }
