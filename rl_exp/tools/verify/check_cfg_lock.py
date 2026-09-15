# -*- coding: utf-8 -*-
"""Recipe golden gate: every registered task's resolved env/agent config is locked.

ARCH_PLAN 1.1b. This is the "整改前 golden" the Step 2 acceptance (hard A) compares
against, so it has to exist before any config-organization change starts.

Why the lock lives at the family root and not in ``versions/lizard/vN/``: those
directories are frozen by ``versioning.mdc`` (红线: 冻结目录只读) and
``check_version_docs.py`` gates their five-piece set. A golden is a gate artifact
that is regenerated whenever the tree changes, so it gets one family-level file
whose per-task entries name the recipe version they belong to.

Offline by construction: tasks are read from ``gym`` registry specs and their cfg
classes are *constructed*; ``gym.make`` (and therefore the sim) is never called.
The path is the same one ``train.py`` uses -- ``env_cfg_entry_point`` -- so the
golden is the recipe as launched, not a re-derivation.

Modes
-----
default            verify every registered task against the baseline for the current
                   framework combination (drift -> exit 1)
``--update --reason "<why>"``
                   create/refresh that baseline; prints the field-level diff first and
                   refuses without a reason
``--diff``         print changed field paths against the baseline
``--vs-upstream``  value diff against ``LocomotionVelocityRoughEnvCfg`` defaults,
                   attributed to the version that last set each value
``--tasks``        restrict to task ids containing any of these substrings

Three properties this file is built to keep:

**Growth is bounded by framework combinations, not by runs.** Entry keys are
``<combination>|<task id>`` and ``baselines`` describes each combination once. A task
therefore never appears twice, training run number 200 adds nothing, and a new key
appears only when the IsaacLab / rsl_rl / Python combination changes (old combinations
are kept, since an old recipe must stay checkable under the framework it was built on).

**The text is chosen for git diffs.** JSON with ``indent=1`` puts one key per line,
key order is the semantic order (so it comes from the config, not from a sort), and
floats are ``repr`` -- a changed leaf changes exactly one line, and an unchanged run
changes nothing at all.

**A baseline is never overwritten as a reflex.** ``--update`` demands a reason, prints
the concrete differences it is about to absorb, and a framework upgrade with no
baseline for that combination fails loudly with instructions instead of quietly
re-baselining ("更新 golden 当消警" is the failure mode this prevents).
"""

import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cfg_snapshot as cs  # noqa: E402
from rl_exp.tools.runrecord import provenance as prov  # noqa: E402

LOCK_PATH = _REPO / "rl_exp" / "versions" / "lizard" / "cfg_lock.json"
LOCK_FORMAT = 2
UPSTREAM_CFG = "isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg:LocomotionVelocityRoughEnvCfg"
_TASK_VERSION = re.compile(r"Lizard-Rough(?:-Play)?-v(\d+)")
_DIFF_LIMIT = 60
_ENTRY_KEYS = {"version", "env_cfg_class", "agent_cfg_class", "digest", "snapshot"}
"""An entry is a recipe fact about a task id. Anything run-scoped here would mean the
lock grows with training runs, which is exactly what it must not do."""


def resolve_entry(entry: str):
    """Import "module:Attr" the way gym resolves an entry point."""
    module_name, _, attr = entry.partition(":")
    module = __import__(module_name, fromlist=[attr])
    obj = module
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


def registered_tasks() -> dict[str, dict]:
    """Every registered task whose entry points live in this repo."""
    import gymnasium  # noqa: F401 - importing rl_exp.tasks performs the registration
    from gymnasium.envs.registration import registry

    import rl_exp.tasks  # noqa: F401

    out = {}
    for task_id, spec in registry.items():
        kwargs = getattr(spec, "kwargs", {}) or {}
        env_entry = kwargs.get("env_cfg_entry_point")
        agent_entry = kwargs.get("rsl_rl_cfg_entry_point")
        if isinstance(env_entry, str) and env_entry.startswith("rl_exp."):
            out[task_id] = {"env": env_entry, "agent": agent_entry}
    return dict(sorted(out.items()))


def build_entry(task_id: str, spec: dict) -> dict:
    """Resolved snapshot + digest for one task's env and agent cfg."""
    env_cls = resolve_entry(spec["env"])
    env_cfg = env_cls()
    agent_snap = None
    resolved_agent = None
    if isinstance(spec.get("agent"), str):
        resolved_agent = spec["agent"]
        agent_snap = cs.snapshot(resolve_entry(resolved_agent)())
    payload = {"env": cs.snapshot(env_cfg), "agent": agent_snap}
    version = getattr(env_cfg, "params_version", None)
    return {
        "version": version if isinstance(version, str) else None,
        "env_cfg_class": spec["env"],
        "agent_cfg_class": resolved_agent,
        "digest": cs.digest(payload),
        "snapshot": payload,
    }


def _brief(value, limit: int = 70) -> str:
    text = json.dumps(value, sort_keys=False, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "~"


def walk_diff(old, new, prefix: str, out: list, limit: int = _DIFF_LIMIT) -> None:
    """Collect differing leaf paths (order-sensitive: mappings and lists compare in order)."""
    if len(out) > limit:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for key in dict.fromkeys([*old, *new]):
            child = f"{prefix}.{key}" if prefix else key
            if key not in old:
                out.append((child, "<absent>", _brief(new[key])))
            elif key not in new:
                out.append((child, _brief(old[key]), "<absent>"))
            else:
                walk_diff(old[key], new[key], child, out, limit)
    elif isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            out.append((f"{prefix}[]", f"{len(old)} items", f"{len(new)} items"))
        else:
            for index, (before, after) in enumerate(zip(old, new, strict=True)):
                walk_diff(before, after, f"{prefix}[{index}]", out, limit)
    elif old != new:
        out.append((prefix, _brief(old), _brief(new)))


def _print_diff(task_id: str, old, new, header: str) -> None:
    """Print the changed field paths between two snapshots."""
    rows: list = []
    walk_diff(old, new, header, rows)
    if not rows:
        return
    print(f"  {task_id}: {len(rows)} path(s) differ")
    for path, before, after in rows[:_DIFF_LIMIT]:
        print(f"    {path}: {before} -> {after}")
    if len(rows) > _DIFF_LIMIT:
        print(f"    ... {len(rows) - _DIFF_LIMIT} more (raise _DIFF_LIMIT to see them)")


def verify(lock: dict, current: dict, problems: list[str], show_diff: bool, only: list[str]) -> None:
    """Every registered task must be locked, and its resolved config unchanged.

    The baseline is selected by framework combination: the same recipe under a
    different IsaacLab / rsl_rl / Python combination is a DIFFERENT baseline, not a
    drift. ``only`` narrows the scope to task ids containing one of the given
    substrings; everything outside it is neither checked nor reported (a filtered run
    must not look like mass retirement).
    """
    combo = combination()
    key = combination_key(combo)
    baselines = lock.get("baselines", {})
    if key not in baselines:
        problems.append(
            f"no baseline for this framework combination ({key}); the lock holds {sorted(baselines)}. "
            f"A framework upgrade gets its OWN baseline pair -- never an in-place overwrite. "
            f'Create one deliberately: --update --reason "<why this combination needs a baseline>"'
        )
        return
    baseline = baselines[key]
    if baseline.get("cfg_snapshot_format") != cs.FORMAT_VERSION:
        problems.append(
            f"baseline snapshot format {baseline.get('cfg_snapshot_format')} != serializer "
            f"{cs.FORMAT_VERSION}: the stored snapshots cannot be compared with freshly taken ones"
        )
        return
    entries = lock.get("entries", {})
    in_scope = lambda task_id: not only or any(token in task_id for token in only)  # noqa: E731
    for task_id, entry in current.items():
        if not in_scope(task_id):
            continue
        stored = entries.get(entry_key(key, task_id))
        if stored is None:
            problems.append(f"{task_id}: no golden entry in this baseline (drifted out, or a new task)")
            continue
        if cs.digest(stored["snapshot"]) != stored["digest"]:
            problems.append(
                f"{task_id}: golden entry is internally inconsistent (digest does not match "
                f"its own snapshot) -- the lock was hand-edited; a drift diff would be unusable"
            )
        extra = set(stored) - _ENTRY_KEYS
        if extra:
            problems.append(
                f"{task_id}: golden entry carries fields that are not recipe facts {sorted(extra)}; "
                f"run-scoped data here would make the lock grow with every run"
            )
        if stored["digest"] != entry["digest"]:
            problems.append(f"{task_id}: config drift vs golden")
            if show_diff:
                _print_diff(task_id, stored["snapshot"], entry["snapshot"], "")
        claimed = stored.get("version")
        if claimed != entry["version"]:
            problems.append(
                f"{task_id}: params_version {entry['version']!r} != golden {claimed!r} "
                f"(the task id and the recipe it loads disagree)"
            )
        match = _TASK_VERSION.fullmatch(task_id)
        if match and entry["version"] != f"v{match.group(1)}":
            problems.append(
                f"{task_id}: task id claims v{match.group(1)} but the cfg loads "
                f"params_version={entry['version']!r}"
            )
    for stored_key in entries:
        combo_part, _, task_id = stored_key.rpartition("|")
        if combo_part not in baselines:
            problems.append(
                f"{stored_key}: entry claims a baseline {combo_part!r} that the lock does not describe"
            )
        elif task_id not in current and in_scope(task_id):
            problems.append(f"{task_id}: golden entry has no registered task (retired task or renamed id)")


def combination() -> dict:
    """The framework combination a baseline belongs to.

    The resolved config depends on the framework code as much as on this repo's
    recipes, so a baseline is keyed by what produced it -- not by when it was taken
    and never by which run needed it.
    """
    return {
        "isaaclab_rev": prov.rev(prov.isaac_root()) or "unresolved",
        "rsl_rl": prov.rsl_rl_id(),
        "python": sys.version.split()[0],
    }


def combination_key(combo: dict) -> str:
    """Short, stable key of a framework combination."""
    return f"isaaclab={combo['isaaclab_rev']}|rsl_rl={combo['rsl_rl']}|python={combo['python']}"


def entry_key(combo_key: str, task_id: str) -> str:
    """Entry key: the combination first, so a task never appears twice by accident.

    The combination lives in the KEY rather than in a nested mapping on purpose: the
    stored snapshots keep the same indentation as before, so introducing baselines cost
    a key rewrite instead of re-indenting every line of every snapshot -- a format
    change that rewrites the whole file is unreadable in review, which defeats the
    point of a diffable golden.
    """
    return f"{combo_key}|{task_id}"


def load_lock() -> tuple[dict, str | None]:
    """Read the lock file; the second value is an error, not an exception.

    A lock written by an older format is reported, never migrated in place: the
    numbers in it would silently change meaning.
    """
    if not LOCK_PATH.is_file():
        return {}, (
            f"{cs.relativize(str(LOCK_PATH))} missing; create the baseline deliberately with "
            f'--update --reason "<why>" (no golden means no drift detection at all)'
        )
    try:
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return {}, f"lock unreadable: {err}"
    if lock.get("lock_format") != LOCK_FORMAT:
        return lock, (
            f"lock format {lock.get('lock_format')} != {LOCK_FORMAT}; regenerate deliberately with "
            f'--update --reason "<why>" -- an in-place rewrite would hide what moved'
        )
    return lock, None


def _previous_entries(lock: dict, key: str, entries: dict) -> dict | None:
    """Entries of an existing baseline for this combination, keyed by task id.

    Handles the pre-v2 flat lock too: during a format migration the reviewer needs to see
    what actually moved, not "34 tasks appeared".
    """
    keys = [stored for stored in entries if stored.startswith(f"{key}|")]
    if keys:
        return {stored.split("|")[-1]: entries[stored] for stored in keys}
    if "lock_format" not in lock or lock.get("lock_format") == 1:
        # pre-v2 flat lock: compare against it so a migration reports what moved
        return lock.get("entries") or None
    return None


def _baseline_changes(previous: dict | None, current: dict) -> list[str]:
    """Print a per-task field-level diff of a baseline update; return the summary lines.

    This is the review the user reads before the lock is rewritten. It prints the
    concrete changed field paths, not just "the digest moved".
    """
    if previous is None:
        return [f"new baseline ({len(current)} tasks)"]
    changed = [t for t in current if t in previous and previous[t]["digest"] != current[t]["digest"]]
    added = [t for t in current if t not in previous]
    removed = [t for t in previous if t not in current]
    for task_id in changed:
        _print_diff(task_id, previous[task_id]["snapshot"], current[task_id]["snapshot"], "")
    summary = []
    if changed:
        summary.append(f"{len(changed)} task(s) changed: {changed[:5]}")
    if added:
        summary.append(f"{len(added)} task(s) added: {added[:5]}")
    if removed:
        summary.append(f"{len(removed)} task(s) removed: {removed[:5]}")
    if not summary:
        summary.append("no content change (provenance or format only)")
    return summary


def update(current: dict, reason: str | None) -> int:
    """Write/refresh the baseline for the current framework combination.

    Refuses without ``--reason``: a baseline must never be rewritten as a reflex to
    make a red gate green ("更新 golden 当消警"), so the update carries a stated
    reason and prints the concrete differences first.
    """
    combo = combination()
    key = combination_key(combo)
    lock, error = load_lock()  # a missing/older lock is fine here: this is the deliberate act
    baselines = dict(lock.get("baselines", {}))
    # only same-format entries are keyed by combination; a pre-v2 flat lock is re-keyed
    # from scratch below (its bare task ids are the ones being replaced)
    entries = dict(lock.get("entries", {})) if lock.get("lock_format") == LOCK_FORMAT else {}
    previous = _previous_entries(lock, key, entries)
    if error:
        print(f"  note: {error}")
    if previous is not None and "lock_format" not in lock:
        print(f"  note: pre-v2 lock; entries compared below and re-keyed into format {LOCK_FORMAT}")

    print(f"  combination: {key}")
    for line in _baseline_changes(previous, current):
        print(f"  change: {line}")
    if not reason:
        print("  REFUSED: --update needs --reason. Review the diff above (field paths, not just digests),")
        print('           then re-run: --update --reason "lizard-v15 golden: <what moved and why>"')
        return 1

    # this combination is replaced wholesale; every other combination is kept as it was
    entries = {stored: value for stored, value in entries.items() if not stored.startswith(f"{key}|")}
    entries.update({entry_key(key, task_id): entry for task_id, entry in current.items()})
    baselines[key] = {
        "created_at": prov.now(),
        "reason": reason,
        "created_rev": prov.rev(_REPO),
        "created_dirty": bool(prov.git(_REPO, "status", "--porcelain")),
        "combination": combo,
        "cfg_snapshot_format": cs.FORMAT_VERSION,
        "task_count": len(current),
    }
    lock = {
        "lock_format": LOCK_FORMAT,
        "note": (
            "recipe golden, keyed by framework combination: entry keys are '<combination>|<task id>' "
            "and a training run never adds one"
        ),
        "baselines": dict(sorted(baselines.items())),
        "entries": dict(sorted(entries.items())),
    }
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(lock, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    size = LOCK_PATH.stat().st_size
    print(f"  lock written: {cs.relativize(str(LOCK_PATH))} ({size / 1024:.0f} KiB)")
    print(f"  baselines in file: {len(lock['baselines'])}, entries: {len(lock['entries'])}")
    if baselines[key]["created_dirty"]:
        print("  WARN: repo tree is dirty -- this baseline is NOT a clean one; regenerate after committing")
    return 0


def attribution(cfg_cls) -> dict[str, str]:
    """Map a changed field path to the ancestor version that first introduced it.

    "值相同不证明来自继承": the declaring class of a field says nothing about which
    version set the value. Walking the MRO and diffing each subclass against its
    parent attributes every difference to the version that introduced it.
    """
    chain = [c for c in cfg_cls.__mro__ if isinstance(c, type) and hasattr(c, "__dataclass_fields__")]
    snaps: dict[str, dict | None] = {}
    for cls in chain:
        try:
            snaps[cls.__name__] = cs.snapshot(cls())
        except Exception as err:  # noqa: BLE001 - a non-constructible mixin proves nothing, skip it
            print(f"    (attribution: {cls.__name__} not constructible: {type(err).__name__})")
            snaps[cls.__name__] = None
    origin: dict[str, str] = {}
    for child, parent in zip(chain, chain[1:], strict=False):
        child_snap, parent_snap = snaps[child.__name__], snaps[parent.__name__]
        if child_snap is None or parent_snap is None:
            continue
        rows: list = []
        walk_diff(parent_snap, child_snap, "", rows, limit=10**6)
        for path, _, _ in rows:
            origin.setdefault(path, child.__name__.replace("LizardRoughTeacherEnvCfg_", ""))
    return origin


def _origin_of(path: str, origin: dict[str, str]) -> str:
    if path in origin:
        return origin[path]
    root = path.split(".", 1)[0].split("[", 1)[0]
    for key, value in origin.items():
        if key.split(".", 1)[0].split("[", 1)[0] == root:
            return value
    return "<framework base>"


def vs_upstream(current: dict, only: list[str]) -> int:
    """Value diff against the framework base, attributed to the version that set it."""
    upstream = cs.snapshot(resolve_entry(UPSTREAM_CFG)())
    for task_id, entry in current.items():
        if only and not any(token in task_id for token in only):
            continue
        rows: list = []
        walk_diff(upstream, entry["snapshot"]["env"], "", rows, limit=10**6)
        print(f"  {task_id}: {len(rows)} path(s) differ from the framework base")
        if not only:
            continue
        origin = attribution(resolve_entry(entry["env_cfg_class"]))
        tally: dict[str, int] = {}
        for path, _, _ in rows:
            tally[_origin_of(path, origin)] = tally.get(_origin_of(path, origin), 0) + 1
        print(f"    attributed to: {dict(sorted(tally.items(), key=lambda kv: -kv[1]))}")
        for path, before, after in rows[:_DIFF_LIMIT]:
            print(f"    [{_origin_of(path, origin)}] {path}: {before} -> {after}")
        if len(rows) > _DIFF_LIMIT:
            print(f"    ... {len(rows) - _DIFF_LIMIT} more")
    return 0


def main() -> int:
    args = sys.argv[1:]
    only: list[str] = []
    if "--tasks" in args:
        only = [t for t in args[args.index("--tasks") + 1].split(",") if t]

    current = {task_id: build_entry(task_id, spec) for task_id, spec in registered_tasks().items()}
    print(f"  registered rl_exp tasks: {len(current)}")

    if "--update" in args:
        return update(current, _value_of(args, "--reason"))

    if "--vs-upstream" in args:
        return vs_upstream(current, only)

    problems: list[str] = []
    lock, error = load_lock()
    if error:
        problems.append(error)
    else:
        verify(lock, current, problems, show_diff="--diff" in args, only=only)

    for problem in problems:
        print(f"  DRIFT: {problem}")
    if problems:
        print(f"CFG_LOCK_DRIFT ({len(problems)})")
        return 1
    print(f"CFG_LOCK_OK ({len(current)} tasks, {combination_key(combination())})")
    return 0


def _value_of(args: list[str], flag: str) -> str | None:
    """Value following a flag, or None (a bare flag carries no reason)."""
    if flag not in args:
        return None
    index = args.index(flag) + 1
    return args[index] if index < len(args) and not args[index].startswith("--") else None


if __name__ == "__main__":
    raise SystemExit(main())
