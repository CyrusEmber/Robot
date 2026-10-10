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

import importlib.metadata
import importlib.util
import json
import os
import pathlib
import sys
from datetime import datetime
from urllib.parse import urlsplit
from urllib.request import url2pathname

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# The two primitives this module used to implement live in ``binding`` (work/active/record-variant-and-snapshot-specs.md ①): one
# function hashes a file, one abbreviates a revision, and both records call them. They are
# re-exported under the names this package's callers (``manifest``, ``rebuild``, the golden
# lock) and ``test_run_manifest.py`` already import, rather than re-implemented -- a second
# implementation is what ``check_record_bindings.py`` fails on. ``hashlib`` and ``subprocess``
# are no longer imported here for that reason.
from rl_exp.tools.runrecord.binding import (  # noqa: E402
    git_rev as rev,
    git_run as git,
    sha256_bytes,
    sha256_file,
)
from rl_exp.tools.verify.cfg_snapshot import relativize  # noqa: E402

UNTRACKED_CAP = 40


def now() -> str:
    """Local timestamp with offset, one format for every record this repo writes."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


# untracked entries that are not code: logs, caches, scratch dirs. Recorded, but they
# do not make a run unrebuildable -- treating them as blockers would leave every
# verdict "unknown" forever on a working machine, which is as useless as a green light.
_NON_CODE_TOKENS = ("__pycache__", ".pyc", "logs/", "logs\\", ".tmp", ".log")


def split_untracked(untracked: list[str], root: pathlib.Path | None, code_root: pathlib.Path | None) -> tuple[list[str], list[str]]:
    """Split untracked files into those inside the importable code root and the rest.

    Args:
        untracked: paths as git reported them, relative to ``root``.
        root: the work tree root.
        code_root: where importable code lives (``<repo>``, ``<tree>/source``), or None.

    Returns:
        ``(in_code_root, outside)``: only the first group can change what a run did.
    """
    inside: list[str] = []
    outside: list[str] = []
    for relative in untracked:
        cleaned = relative.strip('"')
        if any(token in cleaned for token in _NON_CODE_TOKENS):
            outside.append(cleaned)
            continue
        if root is None or code_root is None:
            outside.append(cleaned)
            continue
        target = (root / cleaned).resolve()
        if str(target).startswith(str(code_root)):
            inside.append(cleaned)
        else:
            outside.append(cleaned)
    return inside, outside


def split_prose(changed: list[str]) -> tuple[list[str], list[str]]:
    """Split changed paths into the prose and the rest.

    Prose is the ledger, the records and the plans -- all ``.md``, and nothing a run reads. A run's
    rebuildable claim is about the code, the configs and the assets its declaration digests, so a
    document edited while a run is in flight changes none of them; refusing over it would turn
    "commit your notes before you train" into a habit and teach people to set the override, which is
    the same failure mode the IsaacLab tree is exempted for. The cut is by extension on purpose:
    it cannot be widened by adding a directory, and no config, lock or asset is a ``.md``.

    Args:
        changed: paths git reports as changed, tracked or untracked.

    Returns:
        ``(prose, blocking)``: only the second group can change what a run read.
    """
    prose = [path for path in changed if path.lower().endswith(".md")]
    blocking = [path for path in changed if not path.lower().endswith(".md")]
    return prose, blocking


def _changed_paths(root: pathlib.Path) -> list[str]:
    """Every path git reports as changed, tracked or untracked, as one flat sorted list.

    Two raw name lists rather than one parsed status listing: these come back NUL-separated and
    unprefixed, so a path with spaces, a rename, or a status column the git helper strips needs no
    care at all. (A first version sliced the status listing at a fixed offset and lost the first
    character of every modified path, because the helper hands back stripped lines.)
    """
    names: list[str] = []
    for args in (("diff", "--name-only", "-z", "HEAD"),
                 ("ls-files", "--others", "--exclude-standard", "-z")):
        names.extend(field for field in git(root, *args).split("\0") if field.strip())
    return sorted(set(name.strip() for name in names))



def git_state(root: pathlib.Path | None, label: str, code_root: pathlib.Path | None = None) -> dict:
    """Provenance of one git work tree.

    Args:
        root: the work tree root, or None when it could not be resolved.
        label: name used in the ``available: False`` explanation.
        code_root: importable-code root used to judge untracked files; None counts every
            untracked file as relevant.

    Returns:
        Revision, dirty flag, diff and status digests, and the untracked file split.
    """
    if root is None:
        return {"available": False, "detail": f"{label} root unresolved"}
    head = rev(root)
    if not head:
        return {"available": False, "detail": f"{root} is not a git work tree"}
    porcelain = git(root, "status", "--porcelain=v2")
    status_lines = porcelain.splitlines()
    untracked = sorted(line.split(" ", 1)[1] for line in status_lines if line.startswith("? "))
    in_code, outside = split_untracked(untracked, root, code_root)
    changed = _changed_paths(root)
    prose, blocking = split_prose(changed)
    diff = git(root, "diff", "HEAD")
    return {
        "available": True,
        "root": relativize(str(root)),
        "rev": head,
        "dirty": bool(status_lines),
        "status_porcelain_sha256": sha256_bytes(porcelain.encode("utf-8")),
        "diff_sha256": sha256_bytes(diff.encode("utf-8")),
        "diff_lines": len(diff.splitlines()),
        "changed_paths": changed[:UNTRACKED_CAP],
        # What the launch gate refuses on: the changed paths that are not prose. ``dirty`` stays the
        # whole truth about the tree, so a record whose only dirt was a document says so and is not
        # refused for it (2026-09-22; the rebuild gate already read it this way).
        "changed_non_prose": blocking[:UNTRACKED_CAP],
        "changed_prose_count": len(prose),
        "untracked_count": len(untracked),
        "untracked": untracked[:UNTRACKED_CAP],
        "untracked_in_code_root": in_code,
        "untracked_outside_code_root": outside,
        "untracked_requires_archive": bool(in_code),
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


_SITE_DIRS = ("site-packages", "dist-packages")


def _module_origin(module: str) -> pathlib.Path | None:
    """The file a top-level module resolves to, or None when it is not importable."""
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        return None
    origin = getattr(spec, "origin", None) if spec is not None else None
    return pathlib.Path(origin).resolve() if origin else None


def _direct_url(distribution) -> dict | None:
    """The install origin a distribution recorded, or None when it recorded none.

    PEP 610: an install from a directory, an archive or a VCS gets this file next to its metadata,
    and an editable one carries ``dir_info.editable``. A wheel taken from an index has none, so
    "absent" means the origin is not recorded -- not that the install has none.
    """
    raw = distribution.read_text("direct_url.json")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _editable_source(direct_url: dict | None) -> pathlib.Path | None:
    """The directory an editable install points at, or None when the install is not editable."""
    if not (direct_url or {}).get("dir_info", {}).get("editable"):
        return None
    url = (direct_url or {}).get("url") or ""
    if not url.startswith("file:"):
        return None
    return pathlib.Path(url2pathname(urlsplit(url).path))


def _in_site_packages(origin: pathlib.Path) -> bool:
    """Is this file inside an install directory rather than a checkout on the import path?"""
    return any(part.lower() in _SITE_DIRS for part in origin.parts)


def _owning_distribution(module: str, origin: pathlib.Path):
    """``(distribution, its recorded origin, its editable source)`` for the imported ``origin``.

    Ownership is read off the distribution's own metadata (``top_level.txt``, or its file list when
    that is absent), and an editable install is matched by *path*: the source its record points at
    has to be the file that got imported, or it is not the install that ran.

    A loop rather than ``importlib.metadata.packages_distributions``: that builds the mapping for
    every distribution on the box and measured 4.3 s here (237 distributions), while two metadata
    reads per distribution cost 0.2 s -- and this runs once per process.
    """
    for distribution in importlib.metadata.distributions():
        direct = _direct_url(distribution)
        source = _editable_source(direct)
        if source is not None:
            if (source / module / "__init__.py").resolve() == origin:
                return distribution, direct, source
            continue
        top = (distribution.read_text("top_level.txt") or "").split()
        if module in top:
            return distribution, direct, None
        if not top and any(
            str(part).replace("\\", "/") == f"{module}/__init__.py" for part in distribution.files or ()
        ):
            return distribution, direct, None
    return None, None, None


def rsl_rl_state() -> dict:
    """rsl_rl provenance: an editable install is the tree it points at, anything else a distribution.

    "Is it editable" is answered by the install's own record (PEP 610 ``direct_url.json``), not by
    where the package directory happens to sit: this venv lives *inside* the IsaacLab checkout, so
    "the package dir is in a git tree" read a wheel as a source install and named an IsaacLab
    revision as the rsl_rl a run had loaded (measured 2026-10-10,
    ``acceptance/records/2026-10-10-record-format-live-checks.md``). An install whose origin was not
    recorded is identified by its version and nothing else, and says so -- borrowing the enclosing
    tree's revision is what made that identity unfalsifiable.

    Ceiling: two wheels of one version read as one identity here; the state carries the distribution
    name and the directory it was unpacked to, so a reader can see that is the case.
    """
    origin = _module_origin("rsl_rl")
    if origin is None:
        return {"available": False, "detail": "rsl_rl is not importable"}
    distribution, direct, source = _owning_distribution("rsl_rl", origin)
    if source is None and not _in_site_packages(origin):
        # Nothing accounts for the file, or a distribution accounts for it without recording an
        # origin: either way what ran is the checkout the file sits in (PYTHONPATH, `setup.py
        # develop`), and a venv inside a repo is excluded by the site-packages test above.
        source = origin.parent
    if source is not None:
        tree = git(source, "rev-parse", "--show-toplevel")
        if tree:
            state = git_state(pathlib.Path(tree), "rsl_rl", code_root=source)
            state["mode"] = "editable/source"
            state["package_dir"] = relativize(str(source))
            return state
    if distribution is not None:
        state = {
            "available": True,
            "mode": "installed",
            "distribution": distribution.metadata["Name"],
            "distribution_version": distribution.version,
            "origin": relativize(str(origin.parent)),
        }
        if direct is not None:
            state["direct_url"] = direct
        else:
            state["detail"] = "no direct_url.json: the wheel recorded no origin, so its version is the identity"
        return state
    return {"available": False, "detail": f"nothing on this box accounts for {origin}"}


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
    tree = isaac_root()
    return {
        "repository": git_state(_REPO, "repository", code_root=_REPO),
        "isaaclab": git_state(tree, "isaaclab", code_root=(tree / "source") if tree else None),
        "rsl_rl": rsl_rl_state(),
    }
