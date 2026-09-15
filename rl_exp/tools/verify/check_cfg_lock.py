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
default        verify every registered task against the lock (drift -> exit 1)
``--update``   write/refresh the lock from the current tree
``--diff``     print changed field paths against the lock
``--vs-upstream``  value diff against ``LocomotionVelocityRoughEnvCfg`` defaults,
                   with a provenance column ("值相同" does not prove "来自继承")
``--tasks``    restrict to task ids containing any of these substrings

Scope note: the lock records resolved *values*, so it is tied to the framework
revision that produced them (``locked_isaaclab_rev``). A framework upgrade makes
the whole lock a new baseline pair, exactly as ARCH_PLAN Step 2 requires -- it is
never a routine "update the golden" chore.
"""

import json
import pathlib
import re
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cfg_snapshot as cs  # noqa: E402

LOCK_PATH = _REPO / "rl_exp" / "versions" / "lizard" / "cfg_lock.json"
UPSTREAM_CFG = "isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg:LocomotionVelocityRoughEnvCfg"
_TASK_VERSION = re.compile(r"Lizard-Rough(?:-Play)?-v(\d+)")
_DIFF_LIMIT = 60


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, cwd=_REPO
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


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

    ``only`` narrows the scope to task ids containing one of the given substrings;
    everything outside it is neither checked nor reported (a filtered run must not
    look like mass retirement).
    """
    entries = lock.get("entries", {})
    in_scope = lambda task_id: not only or any(token in task_id for token in only)  # noqa: E731
    for task_id, entry in current.items():
        if not in_scope(task_id):
            continue
        if task_id not in entries:
            problems.append(f"{task_id}: no golden entry (run --update once the tree is the baseline)")
            continue
        if cs.digest(entries[task_id]["snapshot"]) != entries[task_id]["digest"]:
            problems.append(
                f"{task_id}: golden entry is internally inconsistent (digest does not match "
                f"its own snapshot) -- the lock was hand-edited; a drift diff would be unusable"
            )
        if entries[task_id]["digest"] != entry["digest"]:
            problems.append(f"{task_id}: config drift vs golden")
            if show_diff:
                _print_diff(task_id, entries[task_id]["snapshot"], entry["snapshot"], "")
        claimed = entries[task_id].get("version")
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
    for task_id in entries:
        if task_id not in current and in_scope(task_id):
            problems.append(f"{task_id}: golden entry has no registered task (retired task or renamed id)")
    if lock.get("cfg_snapshot_format") != cs.FORMAT_VERSION:
        problems.append(
            f"lock format {lock.get('cfg_snapshot_format')} != serializer {cs.FORMAT_VERSION}"
        )


def update(current: dict) -> int:
    lock = {
        "cfg_snapshot_format": cs.FORMAT_VERSION,
        "note": "recipe golden for every registered rl_exp task; regenerate only on an intended change",
        "locked_at_rev": _git("rev-parse", "HEAD")[:12],
        "locked_dirty": bool(_git("status", "--porcelain")),
        "locked_isaaclab_rev": cs.ISAAC_ROOT and _git_rev(cs.ISAAC_ROOT),
        "locked_python": sys.version.split()[0],
        "entries": current,
    }
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(lock, f, indent=1, ensure_ascii=False)
        f.write("\n")
    size = LOCK_PATH.stat().st_size
    print(f"  lock written: {LOCK_PATH.relative_to(_REPO)} ({size / 1024:.0f} KiB, {len(current)} tasks)")
    if lock["locked_dirty"]:
        print("  WARN: repo tree was dirty -- this golden is NOT a clean baseline")
    return 0


def _git_rev(root) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=root
        ).stdout.strip()[:12]
    except (OSError, subprocess.CalledProcessError):
        return ""


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
        return update(current)

    if "--vs-upstream" in args:
        return vs_upstream(current, only)

    problems: list[str] = []
    if not LOCK_PATH.is_file():
        problems.append(f"{LOCK_PATH.relative_to(_REPO)} missing (run with --update to create the baseline)")
        lock = {}
    else:
        with open(LOCK_PATH, encoding="utf-8") as f:
            lock = json.load(f)
        verify(lock, current, problems, show_diff="--diff" in args, only=only)

    for problem in problems:
        print(f"  DRIFT: {problem}")
    if problems:
        print(f"CFG_LOCK_DRIFT ({len(problems)})")
        return 1
    print(f"CFG_LOCK_OK ({len(current)} tasks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
