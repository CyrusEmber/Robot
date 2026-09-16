# -*- coding: utf-8 -*-
"""Negative control for check_cfg_lock.py: every drift it claims to catch must fire.

Runs partly against the real lock files and registry (fast), a synthetic
two-line tree in a temp directory, and requires a problem for each tamper. A gate whose
failure modes were never demonstrated is not a gate.

Beyond entry drift, this pins the properties the per-line split exists to hold:

* ownership is declared -- a task whose cfg names no line must be reported, not skipped;
* an update cannot reach another line's golden (the accident the split prevents), and a
  whole-tree ``--update`` without ``--line`` is refused before it writes anything;
* growth is bounded by framework combinations (runs add nothing), the text diffs one line
  per changed leaf and re-serializes byte-identically, and an update without a stated
  reason is refused rather than silently re-baselining.
"""

import difflib
import json
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")
import cfg_snapshot as cs  # noqa: E402
import check_cfg_lock as g  # noqa: E402

PROBLEMS: list[str] = []
KEY = g.combination_key(g.combination())


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def _snapshot(decimation: int = 4) -> dict:
    """A tiny stand-in for a resolved cfg snapshot (only needs to be diffable)."""
    return {"env": {"decimation": decimation, "episode_length_s": 20.0}, "agent": None}


def _entry(snapshot: dict | None = None, version: str | None = "v1") -> dict:
    snap = _snapshot() if snapshot is None else snapshot
    return {
        "version": version,
        "env_cfg_class": "rl_exp.tasks.x:Cfg",
        "agent_cfg_class": "rl_exp.tasks.agents.y:Runner",
        "digest": cs.digest(snap),
        "snapshot": snap,
    }


def _tree(root: pathlib.Path) -> dict:
    """A two-line ``versions/`` tree: ``lizard/main`` (v1, v2) and ``lizard/parkour`` (v1)."""
    for key, versions in {"lizard/main": ["v1", "v2"], "lizard/parkour": ["v1"]}.items():
        line_dir = root.joinpath(*key.split("/"))
        line_dir.mkdir(parents=True, exist_ok=True)
        (line_dir / f"{line_dir.name}_params.yaml").write_text("x: 1\n", encoding="utf-8")
        for version in versions:
            (line_dir / version).mkdir(exist_ok=True)
            (line_dir / version / f"{line_dir.name}_params.yaml").write_text("x: 1\n", encoding="utf-8")
    return g.discover(root)


def _synthetic_map(line, current: dict) -> dict:
    """The map a hand-built tree needs, agreeing with its live entries by default.

    Identity now comes from ``versions/recipes.json``, so a synthetic tree has to carry a
    map as well. Making the default agree with the live config keeps every other case about
    what it was about, and a case that wants map drift hands in its own.
    """
    recipes: dict = {}
    tasks: dict = {}
    for task_id, entry in current.items():
        key = f"synthetic-{task_id}@1"
        recipes[key] = {
            "line": line.key,
            "env_cfg_entry": "rl_exp.tasks.x:Cfg",
            "agent_entry": "rl_exp.tasks.agents.y:Runner",
            "legacy_task_version": entry.get("version") if isinstance(entry, dict) else None,
        }
        tasks[task_id] = key
    return {"format": 1, "recipes": recipes, "tasks": tasks}


def _verify(line, entries: dict, current: dict, only: list[str] | None = None,
            recipes: dict | None = None) -> list[str]:
    baselines = {KEY: {"cfg_snapshot_format": cs.FORMAT_VERSION}}
    problems: list[str] = []
    catalog = _synthetic_map(line, current) if recipes is None else recipes
    g.verify_entries(line, baselines, KEY, entries, current, problems, show_diff=True, only=only or [],
                     recipes=catalog)
    return problems


def _fires(name: str, keyword: str, line, entries: dict, current: dict, only: list[str] | None = None,
           recipes: dict | None = None) -> None:
    problems = _verify(line, entries, current, only, recipes)
    check(name, any(keyword in p for p in problems), f"no problem containing {keyword!r}: {problems}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        lines = _tree(tmp_path / "versions")
        lizard, parkour = lines["lizard/main"], lines["lizard/parkour"]

        # --- entry-level rules (synthetic: no gym, no framework import) -----------
        good = {g.entry_key(KEY, "Lizard-Test-v1"): _entry(version="v1")}
        current = {"Lizard-Test-v1": _entry(version="v1")}
        check("entries/clean", _verify(lizard, good, current) == [], f"{_verify(lizard, good, current)}")

        _fires("entries/missing", "no golden entry", lizard, {}, current)

        stale = dict(good)
        stale[g.entry_key(KEY, "Lizard-Test-v1")] = _entry(_snapshot(decimation=999), version="v1")
        _fires("entries/digest-mismatch", "config drift", lizard, stale, current)

        hand_edited = copy_stored(good, snapshot=_snapshot(decimation=999))
        _fires("entries/hand-edited", "internally inconsistent", lizard, hand_edited, current)

        run_scoped = copy_stored(good)
        run_scoped[g.entry_key(KEY, "Lizard-Test-v1")]["run_id"] = 7
        _fires("entries/run-scoped-field", "not recipe facts", lizard, run_scoped, current)

        _fires("entries/version-changed", "params_version", lizard, copy_stored(good, version="v2"), current)

        _fires("entries/retired", "no registered task", lizard, {g.entry_key(KEY, "Lizard-Gone-v1"): _entry()}, {})

        orphan = {g.entry_key("isaaclab=x|rsl_rl=y|python=9", "Lizard-Test-v1"): _entry()}
        problems: list[str] = []
        g.verify_entries(lizard, {KEY: {"cfg_snapshot_format": cs.FORMAT_VERSION}}, KEY, orphan, current, problems, False, [])
        check("entries/undeclared-combination", any("is not declared" in p for p in problems), f"{problems}")

        # the map's declared version must be the version the cfg loads, and it must have a
        # frozen directory on the line that owns it; a recipe declaring no version is a dev
        # recipe, so no version comparison applies to it
        id_missing = {g.entry_key(KEY, "Lizard-Test-v9"): _entry(version="v9")}
        _fires("entries/declared-version-not-in-line", "does not have", lizard, id_missing,
               {"Lizard-Test-v9": _entry(version="v9")})

        mismatch = {g.entry_key(KEY, "Lizard-Test-v2"): _entry(version="v2")}
        _fires(
            "entries/recipe-declares-other-version",
            "declares version",
            lizard,
            mismatch,
            {"Lizard-Test-v2": _entry(version="v1")},
            recipes={
                "format": 1,
                "recipes": {"synthetic-Lizard-Test-v2@1": {
                    "line": "lizard/main",
                    "env_cfg_entry": "rl_exp.tasks.x:Cfg",
                    "agent_entry": "rl_exp.tasks.agents.y:Runner",
                    "legacy_task_version": "v2",
                }},
                "tasks": {"Lizard-Test-v2": "synthetic-Lizard-Test-v2@1"},
            },
        )
        unversioned = {g.entry_key(KEY, "Lizard-Test-v1"): _entry(version=None)}
        check(
            "entries/id-version-quiet-when-unversioned",
            _verify(lizard, unversioned, {"Lizard-Test-v1": _entry(version=None)}) == [],
            "the documented ceiling (id carries a registration version) turned noisy",
        )

        check(
            "entries/only-filter-scopes",
            _verify(lizard, {}, {"Lizard-Test-v1": _entry()}, only=["Other"]) == [],
            "a filtered run reported an out-of-scope task as retired/missing",
        )

        # --- the split: an update cannot reach another line's file ----------------
        real_baselines = g.BASELINES_PATH
        g.BASELINES_PATH = tmp_path / "versions" / "cfg_baselines.json"
        try:
            parkour.lock_path.write_text('{"lock_format": 3, "entries": {"sentinel": {}}}\n', encoding="utf-8")
            before = parkour.lock_path.read_bytes()
            before_shared = g.BASELINES_PATH.read_bytes() if g.BASELINES_PATH.exists() else None

            check("update/refuses-without-reason", g.update(lizard, current, None) == 1, "update ran without a reason")
            check("update/refused-wrote-nothing", not lizard.lock_path.exists(), "a refused update still wrote")
            check(
                "update/refused-kept-other-line",
                parkour.lock_path.read_bytes() == before,
                "a refused update touched another line",
            )

            check("update/writes-with-reason", g.update(lizard, current, "test baseline") == 0 and lizard.lock_path.is_file())
            written = json.loads(lizard.lock_path.read_text(encoding="utf-8"))
            check(
                "update/one-block-per-combination",
                written["lock_format"] == g.LOCK_FORMAT
                and len(written["entries"]) == len(current)
                and all(stored.startswith(f"{KEY}|") for stored in written["entries"]),
                f"{list(written['entries'])[:2]}",
            )
            check(
                "update/did-not-touch-other-line",
                parkour.lock_path.read_bytes() == before,
                "updating one line rewrote another line's golden -- the accident this split prevents",
            )
            shared = json.loads(g.BASELINES_PATH.read_text(encoding="utf-8"))
            check(
                "update/added-combination-once",
                list(shared["baselines"]) == [KEY] and shared["baselines"][KEY]["reason"] == "test baseline",
                f"{list(shared['baselines'])}",
            )
            shared_bytes = g.BASELINES_PATH.read_bytes()
            g.update(lizard, current, "second reason")
            check(
                "update/kept-existing-combination",
                g.BASELINES_PATH.read_bytes() == shared_bytes,
                "a second update rewrote the shared combination block",
            )
            check(
                "update/only-touched-own-baselines",
                before_shared is None and g.BASELINES_PATH.is_file(),
                "the shared baselines were expected to be created here",
            )
        finally:
            g.BASELINES_PATH = real_baselines

        # --- text format: stable and one line per changed leaf --------------------
        text = json.dumps(written, indent=1, ensure_ascii=False) + "\n"
        again = json.dumps(json.loads(text), indent=1, ensure_ascii=False) + "\n"
        check("text/roundtrip-byte-identical", again == text, "re-serializing the lock changed its bytes")

        edited = json.loads(text)
        stored_key = g.entry_key(KEY, "Lizard-Test-v1")
        edited["entries"][stored_key]["snapshot"]["env"]["decimation"] += 1
        edited_text = json.dumps(edited, indent=1, ensure_ascii=False) + "\n"
        diff = [
            line for line in difflib.unified_diff(text.splitlines(), edited_text.splitlines(), lineterm="")
            if line[:1] in "+-" and line[:3] not in ("+++", "---")
        ]
        check("text/one-line-per-changed-leaf", len(diff) == 2, f"{len(diff)} changed lines: {diff[:4]}")

    # --- the real tree: today's goldens must verify through the new routing ------
    real_paths = {key: line.lock_path for key, line in g.discover().items() if line.lock_path.is_file()}
    real_bytes = {key: path.read_bytes() for key, path in real_paths.items()}
    check("main/whole-tree-update-refused", g.main(["--update", "--reason", "x"]) == 1)
    check("main/unknown-line-refused", g.main(["--update", "--line", "nope/v1", "--reason", "x"]) == 1)
    check("main/real-tree-clean", g.main([]) == 0, "the real lock files no longer verify")
    check(
        "main/refusals-wrote-nothing",
        all(path.read_bytes() == real_bytes[key] for key, path in real_paths.items()),
        "a refused or read-only run rewrote a real lock file",
    )

    if PROBLEMS:
        print(f"CFG_LOCK_GATE_FAILED ({len(PROBLEMS)})")
        return 1
    print("CFG_LOCK_GATE_OK")
    return 0


def copy_stored(entries: dict, snapshot: dict | None = None, version: str | None = None) -> dict:
    """Deep-ish copy of a stored-entries map, optionally replacing one entry's fields."""
    out = json.loads(json.dumps(entries))
    if snapshot is not None or version is not None:
        stored = out[g.entry_key(KEY, "Lizard-Test-v1")]
        if snapshot is not None:
            stored["snapshot"] = snapshot
        # keep the digest as recorded: a snapshot edited without its digest is the
        # hand-edited case this file pins separately
        if version is not None:
            stored["version"] = version
    return out


if __name__ == "__main__":
    raise SystemExit(main())
