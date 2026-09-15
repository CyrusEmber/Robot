# -*- coding: utf-8 -*-
"""Isolation rebuild (ARCH_PLAN 1.5): take the material, then check a rebuild against it.

1.5 asks a different question from 1.2. 1.2 asked "is this run recorded"; this asks "can
this run be built again somewhere that cannot reach the original sources". The plan
splits that into three things, all of which this module does **without a simulator**:

``--capture <run_dir> <dest>``
    Take what a rebuild needs: the code at the declared revision, the declared dirty
    diff, the untracked code, the asset lock, the recipe and the checkpoints -- and every
    content digest that goes with it. decision (user, 2026-09-15): material
    that cannot be brought back is a **refusal**, not a footnote. A refusd capture writes
    no material at all, only the refusal record, so nothing downstream can mistake a gap
    for a rebuild. That is ``PLAN.md`` #18 turned into a gate: to capture a run whose code
    was dirty or untracked, you must name where that content lives (``--archive``).
``--check <dest> --root <rebuild_root>``
    Run inside the rebuilt tree. Answers the plan's three questions: the material digests
    still describe the material, every imported module and the asset lock resolve inside
    the rebuild root (or a declared dependency) and **never back into the original source
    or asset trees**, and the configuration plus checkpoint payload agree with the frozen
    T1 record. Whether the originals are still readable is recorded as scope, not required:
    1.5 claims "受检查路径上的配置与加载级重建通过", not OS-level isolation (v0.16).
``--maintest <dest> --root <rebuild_root>``
    The missing-file negative test: drop one required payload, the check must fail; put it
    back, the check must pass.

No ``gym.make`` and no Isaac Sim anywhere here, so what this can verify is configuration
and loading -- which is the level 1.5 claims ("受检查路径上的配置与加载级重建通过"), not
inference or training equivalence.

Offline test: ``python rl_exp/tools/verify/test_rebuild_gate.py``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import shutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.runrecord import manifest as M  # noqa: E402
from rl_exp.tools.runrecord import provenance as prov  # noqa: E402
from rl_exp.tools.verify import cfg_snapshot as cs  # noqa: E402

MATERIAL_NAME = "rebuild_material.json"
MATERIAL_FORMAT = 1
CODE_SOURCES = ("repository", "isaaclab", "rsl_rl")
IMPORTED_MODULES = ("rl_exp", "isaaclab", "isaaclab_tasks", "rsl_rl")
_ROW = M._row


# ---------------------------------------------------------------------------------
# Small filesystem helpers: text is written and read with newline="" so a diff
# stored on Windows still hashes to the digest the recorder took on a normal pipe.
# ---------------------------------------------------------------------------------


def _read_text(path: pathlib.Path) -> str:
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _stored_text(path: pathlib.Path, digest: str | None) -> str | None:
    """Content of a previously stored payload, but only when it hashes as declared."""
    if digest is None or not path.is_file():
        return None
    text = _read_text(path)
    return text if prov.sha256_bytes(text.encode("utf-8")) == digest else None


def _stage_file(src: pathlib.Path, rel: str, stage: pathlib.Path, digests: dict) -> str:
    target = stage / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    digests[rel] = prov.sha256_file(target)
    return rel


def _stage_tree(src: pathlib.Path, rel: str, stage: pathlib.Path, digests: dict) -> None:
    target = stage / rel
    shutil.copytree(
        src, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    for path in sorted(target.rglob("*")):
        if path.is_file():
            digests[str(path.relative_to(stage)).replace(os.sep, "/")] = prov.sha256_file(path)


def _tree_root(name: str) -> pathlib.Path | None:
    """Work tree a code source lives in, resolved the same way provenance resolves it."""
    if name == "repository":
        return _REPO
    if name == "isaaclab":
        return prov.isaac_root()
    try:
        spec = importlib.util.find_spec("rsl_rl")
    except (ImportError, ValueError):
        return None
    origin = getattr(spec, "origin", None)
    if not origin:
        return None
    top = prov.git(pathlib.Path(origin).resolve().parent, "rev-parse", "--show-toplevel")
    return pathlib.Path(top) if top else None


def _unrelativize(stated: str, token: str, root: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(stated.replace(token, str(root)))


def _object_exists(tree: pathlib.Path | None, spec: str) -> bool:
    """Does this revision (or ``rev:path``) exist in the tree's object database?

    ``git cat-file -e`` is silent on success, and :func:`provenance.git` reports stdout --
    so ask for something that has to be printed.
    """
    if tree is None:
        return False
    return bool(prov.git(tree, "rev-parse", "--verify", spec))


# ---------------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------------


def _code_item(name: str, recorded: dict, archive: pathlib.Path | None, run_id: str, stage, digests, refusals) -> dict:
    """Can the code this run used be brought back, and where is it?

    A clean source is brought back by revision. A dirty source is not: only its diff
    digest was recorded, so the content itself has to be *stored* somewhere the rebuild
    can read later -- that is what ``--archive`` names. Without it the capture refuses,
    because hashing a diff does not make it retrievable (PLAN.md #18).
    """
    keep = ("rev", "dirty", "diff_sha256", "diff_lines", "untracked_in_code_root", "mode")
    item = {"retrieval": "none", "recorded": {key: recorded.get(key) for key in keep}}
    root = _tree_root(name)
    item["tree"] = cs.relativize(str(root)) if root else None
    if not recorded.get("available"):
        refusals.append(f"{name}: not recorded at run time ({recorded.get('detail', 'no detail')})")
        return item
    if recorded.get("mode") == "installed":
        refusals.append(f"{name}: installed distribution {recorded.get('distribution_version')}, source not pinned")
        return item
    if root is None or not (root / ".git").exists():
        refusals.append(f"{name}: no work tree at {root}")
        return item
    rev = recorded.get("rev")
    if not _object_exists(root, f"{rev}^{{commit}}"):
        refusals.append(f"{name}: revision {rev} is not in {root}; the run's code cannot be brought back")
        return item
    if not recorded.get("dirty"):
        item["retrieval"] = "git-rev"
        item["payload"] = f"{rev} (git checkout)"
        return item

    stored = (archive / run_id) if archive else None
    diff_path = (stored / f"{name}.diff") if stored else None
    if diff_path is not None:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff = _stored_text(diff_path, recorded.get("diff_sha256")) if diff_path else None
    if diff is None:
        live = prov.git(root, "diff", "HEAD")
        live_sha = prov.sha256_bytes(live.encode("utf-8"))
        if live_sha != recorded.get("diff_sha256"):
            refusals.append(
                f"{name}: the run worked in a dirty tree, the recorded diff "
                f"{str(recorded.get('diff_sha256'))[:8]} no longer matches the live tree {live_sha[:8]}, "
                f"and the diff content was never stored (PLAN.md #18)"
            )
            return item
        if diff_path is None:
            refusals.append(
                f"{name}: dirty tree ({recorded.get('diff_lines')} diff lines) and no archive location "
                f"for its content (PLAN.md #18); pass --archive"
            )
            return item
        _write_text(diff_path, live)
        diff = live
    item["stored_diff"] = cs.relativize(str(diff_path)) if diff_path else None
    item["payload"] = _stage_file(diff_path, f"code/{name}.diff", stage, digests)

    for relative in recorded.get("untracked_in_code_root") or []:
        if stored is None:
            refusals.append(f"{name}: untracked code {relative} has no archive location (PLAN.md #18)")
            return item
        held = stored / "untracked" / name / relative
        if not held.exists():
            live_path = root / relative
            if not live_path.exists():
                refusals.append(f"{name}: untracked code {relative} is gone and was never stored")
                return item
            if live_path.is_dir():
                shutil.copytree(
                    live_path, held, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
                )
            else:
                held.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(live_path, held)
        if held.is_dir():
            _stage_tree(held, f"code/{name}/{relative}", stage, digests)
        else:
            _stage_file(held, f"code/{name}/{relative}", stage, digests)
    item["retrieval"] = "stored-diff"
    return item


def _asset_item(recorded: dict, params_version: str | None, problems: list[str], refusals: list[str]) -> dict:
    """The asset lock's files, hashed now: they are tracked, so a revision brings them back."""
    lock_rel = recorded.get("lock")
    if not lock_rel:
        refusals.append("assets: no lock recorded for this run")
        return {"retrieval": "none"}
    lock_path = _unrelativize(str(lock_rel), "<REPO_ROOT>", _REPO)
    if not lock_path.is_file():
        refusals.append(f"assets: lock {lock_rel} is not in this tree")
        return {"retrieval": "none"}
    live = M.asset_digest(params_version)
    if live.get("missing_or_changed"):
        problems.append(f"assets: {live['missing_or_changed'][:3]} (lock says {recorded.get('file_count')} files)")
        return {"retrieval": "none", "lock": lock_rel, "detail": "files missing or changed"}
    if live.get("manifest_sha256") != recorded.get("manifest_sha256"):
        problems.append(
            f"assets: content digest {str(live.get('manifest_sha256'))[:12]} != recorded "
            f"{str(recorded.get('manifest_sha256'))[:12]}"
        )
        return {"retrieval": "none", "lock": lock_rel, "detail": "digest differs"}
    relative = lock_path.relative_to(_REPO).as_posix()
    if not _object_exists(_REPO, f"{recorded.get('repository_rev', 'HEAD')}:{relative}"):
        # the lock file itself must exist at the recorded revision, otherwise the rebuild
        # tree (a checkout of that revision) would not carry the assets at all
        refusals.append(f"assets: {relative} is not in the repository at the run's revision")
        return {"retrieval": "none", "lock": lock_rel}
    return {
        "retrieval": "in-repo-git",
        "lock": lock_rel,
        "lock_relative_to_repo": relative,
        "file_count": live.get("file_count"),
        "manifest_sha256": live.get("manifest_sha256"),
    }


def _payload_item(run_dir: pathlib.Path, stage: pathlib.Path, digests: dict, problems: list[str], refusals: list[str]) -> dict:
    """Record and checkpoints, copied: the payload is what the rebuild has to load."""
    index_path = run_dir / M.INDEX_NAME
    if not index_path.is_file():
        refusals.append(f"checkpoints: no {M.INDEX_NAME} in the run, nothing to rebuild against")
        return {"retrieval": "none"}
    index = json.loads(index_path.read_text(encoding="utf-8"))
    files: dict[str, str] = {}
    for name, entry in index.items():
        if not isinstance(entry, dict):
            continue
        source = run_dir / name
        digest = prov.sha256_file(source)
        if digest is None:
            refusals.append(f"checkpoints: {name} is not in the run directory any more")
            continue
        if digest != entry.get("sha256"):
            problems.append(f"checkpoints: {name} content changed since the index was written")
            continue
        files[name] = _stage_file(source, f"run/{name}", stage, digests)
    for extra in (M.MANIFEST_NAME, M.INDEX_NAME):
        if (run_dir / extra).is_file():
            _stage_file(run_dir / extra, f"run/{extra}", stage, digests)
    params = run_dir / "params"
    if params.is_dir():
        for path in sorted(params.rglob("*")):
            if path.is_file():
                _stage_file(path, f"run/params/{path.name}", stage, digests)
    if not files:
        refusals.append("checkpoints: no usable checkpoint file was recorded")
    return {"retrieval": "copied", "files": sorted(files), "count": len(files)}


def capture(run_dir: pathlib.Path, dest: pathlib.Path, archive: pathlib.Path | None = None):
    """Take the material a rebuild needs, or refuse in writing.

    Args:
        run_dir: the run directory holding ``run_manifest.json``.
        dest: where the material goes; also where the refusal record goes.
        archive: a location for content a revision cannot restore (dirty diffs, untracked
            code). Without it such a run is refused -- that is PLAN.md #18 as a gate.

    Returns:
        ``(record, problems)``: the material record as written (``verdict`` is one of
        ``captured`` / ``refused`` / ``failed``) and the blocking problems.
    """
    problems: list[str] = []
    refusals: list[str] = []
    manifest_path = run_dir / M.MANIFEST_NAME
    if not manifest_path.is_file():
        return {"material_format": MATERIAL_FORMAT, "verdict": "failed", "problems": [f"no {M.MANIFEST_NAME}"]}, [
            f"{run_dir}: no run manifest"
        ]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = manifest.get("run_id") or run_dir.name
    if manifest.get("t1_sha256") != M.t1_digest(manifest):
        problems.append("record: the T1 digest does not describe the record it sits in")
    missing_stages = [stage for stage in M.STAGES if stage not in manifest.get("stages", {})]
    if missing_stages:
        refusals.append(f"record: no final T1 (missing {missing_stages}); the run was never ready to learn")
    if manifest.get("failures"):
        refusals.append(f"record: the run recorded failures ({manifest['failures'][-1]})")

    stage = dest / ".staging"
    if stage.exists():
        shutil.rmtree(stage)
    digests: dict[str, str] = {}
    declaration = manifest.get("declaration", {})
    code = manifest.get("code", {})
    items = {
        name: _code_item(name, code.get(name, {}), archive, run_id, stage, digests, refusals)
        for name in CODE_SOURCES
    }
    version = declaration.get("recipe", {}).get("params_version")
    asset_recorded = dict(declaration.get("assets", {}))
    asset_recorded["repository_rev"] = code.get("repository", {}).get("rev")
    items["assets"] = _asset_item(asset_recorded, version, problems, refusals)
    items["payload"] = _payload_item(run_dir, stage, digests, problems, refusals)

    verdict = "failed" if problems else ("refused" if refusals else "captured")
    record = {
        "material_format": MATERIAL_FORMAT,
        "run_id": run_id,
        "task": manifest.get("task"),
        "t1_sha256": manifest.get("t1_sha256"),
        "captured_at": prov.now(),
        "archive": cs.relativize(str(archive)) if archive else None,
        "verdict": verdict,
        "refusals": refusals,
        "problems": problems,
        "items": items,
        "payload_digests": {},
    }
    dest.mkdir(parents=True, exist_ok=True)
    material = dest / "material"
    if verdict == "captured":
        if material.exists():
            shutil.rmtree(material)
        os.replace(stage, material)
        record["payload_digests"] = {rel: digests[rel] for rel in sorted(digests)}
    elif stage.exists():
        shutil.rmtree(stage)
    _write_text(dest / MATERIAL_NAME, json.dumps(record, indent=1, ensure_ascii=False))
    return record, problems


# ---------------------------------------------------------------------------------
# Check: the three questions 1.5 asks, asked inside the rebuilt tree
# ---------------------------------------------------------------------------------


def _under(path: pathlib.Path, roots: list[pathlib.Path]) -> bool:
    resolved = str(path.resolve())
    return any(resolved.startswith(str(root.resolve())) for root in roots if root is not None)


def _module_origin(module: str) -> pathlib.Path | None:
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        return None
    origin = getattr(spec, "origin", None) if spec is not None else None
    return pathlib.Path(origin).resolve() if origin else None


def _reachable(path: pathlib.Path) -> bool:
    try:
        return path.is_dir() or path.is_file()
    except OSError:
        return False


def check_material(record: dict, dest: pathlib.Path) -> list[dict]:
    """The payload copies still hash as captured -- no silent local patch."""
    bad = [
        rel
        for rel, digest in (record.get("payload_digests") or {}).items()
        if prov.sha256_file(dest / "material" / rel) != digest
    ]
    return [
        _ROW(
            "已验证重建",
            "失败" if bad else "通过",
            f"material: {len(record.get('payload_digests') or {})} captured file(s)"
            + (f", changed or missing: {bad[:3]}" if bad else " hash as captured"),
        )
    ]


def check_sources(root: pathlib.Path, deps: list[pathlib.Path], originals: list[pathlib.Path]) -> list[dict]:
    """Where do the modules a rebuild imports actually come from?

    The claim is bounded on purpose (ARCH_PLAN 1.5, v0.16): nothing the rebuild resolves may
    fall back into the original source tree, and nothing may come from an undeclared
    location. Whether the original directories are still *readable* is recorded, not
    required -- that would be OS-level isolation, which is explicitly out of scope here.
    """
    rows: list[dict] = []
    if not originals:
        rows.append(
            _ROW(
                "已验证重建",
                "未知",
                "sources: no original source/asset path given (--original), so no fallback was asserted",
            )
        )
        return rows
    allowed = [root, *deps]
    fell_back, undeclared = [], []
    for module in IMPORTED_MODULES:
        origin = _module_origin(module)
        if origin is None:
            undeclared.append(f"{module}: not importable here")
        elif _under(origin, originals):
            fell_back.append(f"{module} -> {origin}")
        elif not _under(origin, allowed):
            undeclared.append(f"{module} -> {origin}")
    rows.append(
        _ROW(
            "已验证重建",
            "失败" if (fell_back or undeclared) else "通过",
            "sources: "
            + (
                f"resolved back into the original tree ({fell_back[:2]})"
                if fell_back
                else f"outside the rebuild root and declared dependencies ({undeclared[:2]})"
                if undeclared
                else f"every import resolves under {root}"
                + (f" (declared dependencies: {[str(dep) for dep in deps]})" if deps else "")
            ),
        )
    )
    still_there = [str(path) for path in originals if _reachable(path)]
    rows.append(
        _ROW(
            "已验证重建",
            "未知",
            "boundary: no OS-level access cut was performed; original paths "
            + (
                f"are still readable ({still_there}) -- recorded as scope, not treated as a failure"
                if still_there
                else f"were not readable from here ({[str(p) for p in originals]})"
            ),
            False,
        )
    )
    return rows


def check_asset_origins(root: pathlib.Path, deps: list[pathlib.Path], originals: list[pathlib.Path], manifest: dict) -> list[dict]:
    """The assets the rebuild reads must resolve inside the rebuild, not back into the original tree."""
    lock = (manifest.get("declaration", {}).get("assets") or {}).get("lock")
    if not lock:
        return [_ROW("已验证重建", "未知", "assets: the run recorded no lock to locate")]
    resolved = _unrelativize(str(lock), "<REPO_ROOT>", _REPO)
    falls_back = _under(resolved, originals)
    inside = _under(resolved, [root, *deps])
    return [
        _ROW(
            "已验证重建",
            "失败" if (falls_back or not inside or not resolved.is_file()) else "通过",
            "assets: "
            + (
                f"the lock resolves back into the original tree ({resolved})"
                if falls_back
                else f"the lock does not resolve inside the rebuild ({resolved})"
                if not inside
                else f"the lock resolves under the rebuild root ({cs.relativize(str(resolved))})"
            ),
        )
    ]


def check_payload_binding(run_dir: pathlib.Path, manifest: dict) -> list[dict]:
    """Load a checkpoint and check it points back at this record's frozen T1."""
    index_path = run_dir / M.INDEX_NAME
    if not index_path.is_file():
        return [_ROW("已验证重建", "未知", "checkpoints: no index to choose a payload from")]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    ready = sorted(name for name, entry in index.items() if isinstance(entry, dict) and entry.get("status") == "ready_to_learn")
    if not ready:
        return [_ROW("已验证重建", "未知", "checkpoints: none written after T1 froze")]
    try:
        import torch
    except ImportError as err:  # noqa: BLE001
        return [_ROW("已验证重建", "未知", f"checkpoints: torch unavailable ({err})")]
    name = ready[-1]
    try:
        payload = torch.load(run_dir / name, map_location="cpu", weights_only=False)
        infos = payload.get("infos", {}) if isinstance(payload, dict) else {}
    except Exception as err:  # noqa: BLE001 - an unreadable payload is an unknown, not a pass
        return [_ROW("已验证重建", "未知", f"checkpoints: {name} could not be loaded ({type(err).__name__}: {err})")]
    binding = infos.get(M.CKPT_INFOS_KEY) or {}
    ok = bool(binding) and binding.get("t1_sha256") == manifest.get("t1_sha256") and binding.get("run_id") == manifest.get("run_id")
    return [
        _ROW(
            "已验证重建",
            "通过" if ok else "失败",
            f"checkpoints: {name} loads and points at run {binding.get('run_id')} / T1 "
            f"{str(binding.get('t1_sha256'))[:16]}",
        )
    ]


def check(dest: pathlib.Path, root: pathlib.Path, deps: list[pathlib.Path] | None = None, originals: list[pathlib.Path] | None = None):
    """Check a rebuild against the material captured for a run.

    Args:
        dest: the directory holding ``rebuild_material.json`` (and ``material/``).
        root: the rebuild root -- where the rebuilt code and assets are expected to be.
        deps: locations of declared, pre-installed dependencies (interpreter, framework).
        originals: the original source/asset roots. Nothing may resolve back into them; their
            readability is recorded as scope only (no OS-level access cut is performed).

    Returns:
        ``(rows, problems)`` in the same shape the run manifest uses: evidence level
        crossed with result, plus the blocking problems.
    """
    problems: list[str] = []
    material_path = dest / MATERIAL_NAME
    if not material_path.is_file():
        return [_ROW("已验证重建", "失败", f"{MATERIAL_NAME} missing in {cs.relativize(str(dest))}")], [
            f"{dest}: no material record"
        ]
    record = json.loads(material_path.read_text(encoding="utf-8"))
    if record.get("verdict") != "captured":
        if record.get("verdict") == "failed":
            problems.extend(record.get("problems") or ["capture failed"])
        reasons = (record.get("problems") or []) + (record.get("refusals") or [])
        return [
            _ROW(
                "已验证重建",
                "失败" if record.get("verdict") == "failed" else "未知",
                f"material was not captured (verdict={record.get('verdict')}): {reasons[:2]}",
            )
        ], problems

    run_dir = dest / "material" / "run"
    manifest_path = run_dir / M.MANIFEST_NAME
    if not manifest_path.is_file():
        problems.append(f"{run_dir}: the manifest was not among the captured payload")
        return [_ROW("已验证重建", "失败", "material: captured without the run manifest")], problems
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    rows = check_material(record, dest)
    rows.extend(check_sources(root, deps or [], originals or []))
    rows.extend(check_asset_origins(root, deps or [], originals or [], manifest))
    rows.extend(_informational(M._verify_self_consistency(manifest, problems)))
    rows.extend(_informational(M._verify_code(manifest, problems)))
    rows.extend(_informational(M._verify_assets(manifest, problems)))
    rows.extend(M._verify_recipe(manifest, problems))
    rows.extend(_informational(M._verify_payload(run_dir, manifest, problems)))
    rows.extend(check_payload_binding(run_dir, manifest))
    return rows, problems


def _informational(rows: list[dict]) -> list[dict]:
    """Supporting rows: the material record, not these, is what 1.5 turns on.

    ``manifest._verify_code`` cannot know about an archive, so it calls every dirty tree
    unknown -- correct for a bare run record, redundant here where the material record has
    already proved the content was captured. They are printed, and they do not decide.
    """
    return [dict(row, required=False) for row in rows]


def _exit_code(rows: list[dict], problems: list[str]) -> int:
    if problems:
        return 1
    if any(row["result"] == "失败" and row["required"] for row in rows):
        return 1
    if any(row["result"] == "未知" and row["required"] for row in rows):
        return 2
    return 0


# ---------------------------------------------------------------------------------
# Missing-file negative test
# ---------------------------------------------------------------------------------


def maintest(dest: pathlib.Path, root: pathlib.Path, deps=None, originals=None):
    """Remove one required payload: the check must fail. Put it back: it must pass."""
    record_path = dest / MATERIAL_NAME
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {}
    payloads = sorted(rel for rel in (record.get("payload_digests") or {}) if rel.startswith("run/") and rel.endswith(".pt"))
    if not payloads:
        return [_ROW("已验证重建", "未知", "maintest: no checkpoint payload to remove")], []
    victim = dest / "material" / payloads[0]
    backup = victim.read_bytes()
    rows: list[dict] = []
    try:
        victim.unlink()
        removed_rows, removed_problems = check(dest, root, deps, originals)
        failed = _exit_code(removed_rows, removed_problems) != 0
        rows.append(
            _ROW(
                "已验证重建",
                "通过" if failed else "失败",
                f"maintest: with {payloads[0]} removed the rebuild must fail, and it "
                + ("did" if failed else "did not (it fell back to something undeclared)"),
            )
        )
    finally:
        victim.write_bytes(backup)
    restored_rows, restored_problems = check(dest, root, deps, originals)
    restored = _exit_code(restored_rows, restored_problems) == 0
    rows.append(
        _ROW(
            "已验证重建",
            "通过" if restored else "未知",
            f"maintest: with {payloads[0]} restored the rebuild "
            + ("passes" if restored else "still does not pass, so the negative test proved nothing"),
        )
    )
    return rows, []


# ---------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------


def _paths(values: list[str]) -> list[pathlib.Path]:
    return [pathlib.Path(value) for value in values]


def _report(rows: list[dict], problems: list[str]) -> int:
    for row in rows:
        mark = "" if row["required"] else " (not required yet)"
        print(f"  [{row['level']}] {row['result']}: {row['detail']}{mark}")
    for problem in problems:
        print(f"  BLOCKING: {problem}")
    code = _exit_code(rows, problems)
    print(
        {
            0: "REBUILD_CHECK_OK",
            1: "REBUILD_CHECK_DRIFT",
            2: "REBUILD_CHECK_PARTIAL",
        }[code]
    )
    return code


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    def flag(name: str, repeat: bool = False):
        if name not in args:
            return None if not repeat else []
        return args[args.index(name) + 1] if not repeat else [
            args[i + 1] for i, value in enumerate(args) if value == name
        ]

    if "--capture" in args:
        run_dir, dest = pathlib.Path(args[args.index("--capture") + 1]), pathlib.Path(args[args.index("--capture") + 2])
        archive = flag("--archive")
        record, problems = capture(run_dir, dest, pathlib.Path(archive) if archive else None)
        print(f"  run: {cs.relativize(str(run_dir))} -> {cs.relativize(str(dest))}")
        for line in record.get("problems", []):
            print(f"  BLOCKING: {line}")
        for line in record.get("refusals", []):
            print(f"  NOT CAPTURED: {line}")
        for name, item in record.get("items", {}).items():
            print(f"  {name}: retrieval={item.get('retrieval')}")
        print(
            {
                "captured": "REBUILD_CAPTURE_OK",
                "refused": "REBUILD_CAPTURE_REFUSED",
                "failed": "REBUILD_CAPTURE_DRIFT",
            }[record.get("verdict", "failed")]
        )
        return {"captured": 0, "refused": 2}.get(record.get("verdict"), 1)
    if "--check" in args or "--maintest" in args:
        name = "--check" if "--check" in args else "--maintest"
        dest = pathlib.Path(args[args.index(name) + 1])
        root = flag("--root")
        if root is None:
            print(f"usage: python -m rl_exp.tools.runrecord.rebuild {name} <dest> --root <rebuild_root>")
            return 2
        deps = _paths(flag("--dep", repeat=True) or [])
        originals = _paths(flag("--original", repeat=True) or [])
        rows, problems = (
            check(dest, pathlib.Path(root), deps, originals)
            if name == "--check"
            else maintest(dest, pathlib.Path(root), deps, originals)
        )
        print(f"  rebuild: {cs.relativize(str(dest))} (root {cs.relativize(root)})")
        return _report(rows, problems)
    print(__doc__.splitlines()[0])
    print("usage: python -m rl_exp.tools.runrecord.rebuild --capture <run_dir> <dest> [--archive DIR]")
    print("       python -m rl_exp.tools.runrecord.rebuild --check <dest> --root <rebuild_root> [--dep P]... --original P...")
    print("       python -m rl_exp.tools.runrecord.rebuild --maintest <dest> --root <rebuild_root> ...")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
