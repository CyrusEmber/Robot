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
``--update --line <line> --reason "<why>"``
                   refresh ONE recipe line's golden for the current framework
                   combination; prints the field-level diff first, refuses without a
                   reason, and cannot reach another line's file
``--line <line>``  restrict to one recipe line (family-relative, e.g. ``lizard/parkour``)
``--diff``         print changed field paths against the baseline
``--vs-upstream``  value diff against ``LocomotionVelocityRoughEnvCfg`` defaults,
                   attributed to the version that last set each value
``--tasks``        restrict to task ids containing any of these substrings

Storage is split so that "whose golden is this" is readable and writable:

* ``rl_exp/versions/cfg_baselines.json`` -- one block per framework combination. A
  combination is a fact about IsaacLab / rsl_rl / Python, not about a recipe, so it is
  stored once for the whole tree instead of once per line.
* ``rl_exp/versions/<family>[/<line>]/cfg_lock.json`` -- that line's golden entries only.

Four properties this file is built to keep:

**Ownership is declared, never guessed.** Every registered recipe names its line as a
``ClassVar`` on the env cfg (``params_line``) and the gate routes by that. A task id and
an entry-point path are both names that a rename can move while the recipe stays put, so
deriving the owner from either cannot distinguish "unowned" from "owned by someone I did
not think of" -- and an unowned task would be checked against nothing while looking green.

**An update cannot rewrite another line's golden.** ``--update`` requires ``--line`` and
writes only that line's file (plus, at most, *adding* a combination block). Before the
split, one ``--update`` replaced every entry under the combination, so seeding a new
task's golden silently absorbed any drift in the other 33 -- attributed to the new task's
reason string. That is the accident this shape exists to prevent.

**Growth is bounded by framework combinations, not by runs.** Entry keys are
``<combination>|<task id>`` and the combination blocks describe each combination once. A
task therefore never appears twice, training run number 200 adds nothing, and a new key
appears only when the IsaacLab / rsl_rl / Python combination changes (old combinations are
kept, since an old recipe must stay checkable under the framework it was built on).

**The text is chosen for git diffs.** JSON with ``indent=1`` puts one key per line, key
order is the semantic order (so it comes from the config, not from a sort), and floats are
``repr`` -- a changed leaf changes exactly one line, and an unchanged run changes nothing.

**A baseline is never overwritten as a reflex.** ``--update`` demands a reason, prints the
concrete differences it is about to absorb, and a framework upgrade with no baseline for
that combination fails loudly with instructions instead of quietly re-baselining
("更新 golden 当消警" is the failure mode this prevents).
"""

import functools
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cfg_snapshot as cs  # noqa: E402
from recipe_lines import RecipeLine, RecipeLineError, discover  # noqa: E402
from rl_exp.tools.runrecord import provenance as prov  # noqa: E402

# One baseline block per framework combination, shared by every recipe line: a
# combination describes IsaacLab / rsl_rl / Python, which is not a property of any
# one line, so storing it per line would mean N copies that can disagree.
BASELINES_PATH = _REPO / "rl_exp" / "versions" / "cfg_baselines.json"
# the explicit task -> recipe -> version/line map (one identity rule set, shared with the
# map gate; this file compares golden content, it does not re-derive identity from names)
RECIPES_PATH = _REPO / "rl_exp" / "versions" / "recipes.json"
LOCK_FORMAT = 3
UPSTREAM_CFG = "isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg:LocomotionVelocityRoughEnvCfg"
_DIFF_LIMIT = 60
# a trailing version suffix in a task id ("...-v14"): a claim about a version of the
# id's own line, checked against that line's discovered versions
@functools.lru_cache(maxsize=1)
def recipe_map() -> dict:
    """The task -> recipe mapping, read from the explicit map file.

    Returns:
        The parsed map, or an empty one when the file is missing -- every task then reports
        "no recipe mapping", which is the honest reading of a missing map.
    """
    try:
        return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
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


def declared_line(spec: dict) -> str | None:
    """The recipe line a task declares it belongs to, or None when it declares none.

    Read off the class as a ``ClassVar`` (so this costs no instantiation), never inferred
    from the task id or the entry-point path: both are names that a rename moves while the
    recipe stays put, and a gate that guesses its owner cannot tell "unowned" apart from
    "owned by someone I did not think of".
    """
    line = getattr(resolve_entry(spec["env"]), "params_line", None)
    return line if isinstance(line, str) and line else None


def route_tasks(specs: dict[str, dict]) -> tuple[dict[str, list[str]], list[str]]:
    """Group registered task ids by declared line; report the ones that declare none.

    Args:
        specs: task id -> registration spec, as returned by :func:`registered_tasks`.

    Returns:
        Line handle -> task ids, and the ownership problems (a task missing from the map
        is a problem, never a skip -- an unowned task would be checked against no golden
        at all while still looking green).
    """
    problems: list[str] = []
    by_line: dict[str, list[str]] = {}
    for task_id, spec in specs.items():
        line = declared_line(spec)
        if line is None:
            problems.append(
                f"{task_id}: env cfg {spec['env']} declares no params_line -- a registered "
                f"recipe must name its line, or no gate can say whose golden it needs"
            )
            continue
        by_line.setdefault(line, []).append(task_id)
    return by_line, problems


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


def verify_baseline(baselines: dict, problems: list[str]) -> str | None:
    """The current combination's key when it is declared, else report why it is not.

    The baseline is selected by framework combination: the same recipe under a different
    IsaacLab / rsl_rl / Python combination is a DIFFERENT baseline, not a drift.
    """
    key = combination_key(combination())
    if key not in baselines:
        problems.append(
            f"no baseline for this framework combination ({key}); "
            f"{cs.relativize(str(BASELINES_PATH))} holds {sorted(baselines)}. A framework "
            f"upgrade gets its OWN baseline -- never an in-place overwrite. Create one "
            f'deliberately: --update --line <line> --reason "<why this combination needs one>"'
        )
        return None
    baseline = baselines[key]
    if baseline.get("cfg_snapshot_format") != cs.FORMAT_VERSION:
        problems.append(
            f"baseline snapshot format {baseline.get('cfg_snapshot_format')} != serializer "
            f"{cs.FORMAT_VERSION}: the stored snapshots cannot be compared with freshly taken ones"
        )
        return None
    return key


def verify_entries(
    line: RecipeLine,
    baselines: dict,
    key: str,
    entries: dict,
    current: dict,
    problems: list[str],
    show_diff: bool,
    only: list[str],
    recipes: dict | None = None,
) -> None:
    """Every task of this line must be locked, and its resolved config unchanged.

    ``only`` narrows the scope to task ids containing one of the given substrings;
    everything outside it is neither checked nor reported (a filtered run must not look
    like mass retirement).
    """
    in_scope = lambda task_id: not only or any(token in task_id for token in only)  # noqa: E731
    catalog = recipe_map() if recipes is None else recipes
    for task_id, entry in current.items():
        if not in_scope(task_id):
            continue
        stored = entries.get(entry_key(key, task_id))
        if stored is None:
            problems.append(
                f"{task_id}: no golden entry for line {line.key!r} in this baseline "
                f"(drifted out, or a new task)"
            )
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
                f"(the recipe this task loads is not the one the golden was taken from)"
            )
        # Identity comes from the explicit map, not from a version suffix parsed out of the
        # task id: two rules for one question is how a map that allows something and a regex
        # that rejects it end up coexisting. The declared version must equal what the cfg
        # loads and must have a frozen directory on the line that owns it; a recipe declaring
        # no version is a dev recipe (the v0 family and parkour read the live yaml), so no
        # version comparison applies to it.
        recipe_key = (catalog.get("tasks") or {}).get(task_id)
        if not recipe_key:
            problems.append(f"{task_id}: no recipe mapping in {cs.relativize(str(RECIPES_PATH))}")
            continue
        recipe = (catalog.get("recipes") or {}).get(recipe_key) or {}
        declared_version = recipe.get("legacy_task_version")
        if declared_version != entry["version"]:
            problems.append(
                f"{task_id}: recipe {recipe_key} declares version {declared_version!r} but the "
                f"cfg loads params_version={entry['version']!r}"
            )
        if declared_version is not None and declared_version not in line.versions:
            problems.append(
                f"{task_id}: recipe {recipe_key} declares {declared_version}, which line "
                f"{line.key!r} does not have {sorted(line.versions)} (a golden that cannot exist)"
            )
        if recipe.get("line") != line.key:
            problems.append(
                f"{task_id}: recipe {recipe_key} declares line {recipe.get('line')!r} but the "
                f"cfg's params_line routes it to {line.key!r}"
            )
    for stored_key in entries:
        combo_part, _, task_id = stored_key.rpartition("|")
        if combo_part not in baselines:
            problems.append(
                f"{stored_key}: entry claims a baseline {combo_part!r} that is not declared "
                f"in {cs.relativize(str(BASELINES_PATH))}"
            )
        elif task_id not in current and in_scope(task_id):
            problems.append(f"{task_id}: golden entry has no registered task (retired task or renamed id)")


@functools.lru_cache(maxsize=1)
def combination() -> dict:
    """The framework combination a baseline belongs to.

    The resolved config depends on the framework code as much as on this repo's
    recipes, so a baseline is keyed by what produced it -- not by when it was taken
    and never by which run needed it.

    Cached per process: this costs four git subprocesses on the host IsaacLab tree,
    and a golden check or a ``verify`` re-asks for it once per task / per run.

    ponytail: ceiling -- a change to the IsaacLab tree or to the installed rsl_rl
    inside one process is not observed. Both are host facts fixed before the process
    starts; a test that fakes git must call ``combination.cache_clear()``.
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


def load_baselines() -> tuple[dict, str | None]:
    """Read the shared framework-combination baselines; the second value is an error.

    A baseline is a statement about the framework combination (IsaacLab rev / rsl_rl /
    Python), which is not a property of any one recipe line -- so it exists once for the
    whole tree and every line points at it. One copy per line would mean N answers to
    "is this combination known", free to disagree.
    """
    if not BASELINES_PATH.is_file():
        return {}, (
            f"{cs.relativize(str(BASELINES_PATH))} missing; a combination gets its own "
            f'baseline deliberately: --update --line <line> --reason "<why>"'
        )
    try:
        data = json.loads(BASELINES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return {}, f"baselines unreadable: {err}"
    if data.get("lock_format") != LOCK_FORMAT:
        return data.get("baselines", {}), (
            f"baselines format {data.get('lock_format')} != {LOCK_FORMAT}; migrate deliberately "
            f"-- an --update rewrite would hide what moved"
        )
    return data.get("baselines", {}), None


def load_entries(line: RecipeLine) -> tuple[dict, str | None]:
    """Read one recipe line's golden entries; the second value is an error.

    One file per line on purpose: ``--update`` must not be able to rewrite a different
    line's golden, and the entry schema is deliberately closed (extra fields are run-scoped
    data), so the file path is the only place a golden's owner can be read off.
    """
    path = line.lock_path
    if not path.is_file():
        return {}, (
            f"{cs.relativize(str(path))} missing (line {line.key!r} has no golden); create it "
            f'deliberately with --update --line {line.key} --reason "<why>"'
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return {}, f"{cs.relativize(str(path))} unreadable: {err}"
    if data.get("lock_format") != LOCK_FORMAT:
        return data.get("entries", {}), (
            f"{cs.relativize(str(path))}: format {data.get('lock_format')} != {LOCK_FORMAT}; "
            f"migrate deliberately -- an --update rewrite would hide what moved"
        )
    return data.get("entries", {}), None


def _previous_entries(entries: dict, key: str) -> dict | None:
    """This line's existing entries for this combination, keyed by task id.

    The reviewer has to see what actually moved (field paths), not "34 tasks appeared",
    so the comparison is per task id.
    """
    keys = [stored for stored in entries if stored.startswith(f"{key}|")]
    if not keys:
        return None
    return {stored.split("|")[-1]: entries[stored] for stored in keys}


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


def update(line: RecipeLine, current: dict, reason: str | None) -> int:
    """Write/refresh ONE recipe line's golden entries for the current combination.

    Refuses without ``--reason``: a baseline must never be rewritten as a reflex to make
    a red gate green ("更新 golden 当消警"), so the update carries a stated reason and
    prints the concrete differences first.

    At most two files are touched: this line's own entries, and -- only by *adding* a
    block -- the shared combination baselines. A different line's golden is not reachable
    from here, which is the whole reason the entries live per line.
    """
    combo = combination()
    key = combination_key(combo)
    baselines, baselines_error = load_baselines()  # missing is fine: this is the deliberate act
    entries, entries_error = load_entries(line)
    entries = dict(entries)
    previous = _previous_entries(entries, key)
    for error in (baselines_error, entries_error):
        if error:
            print(f"  note: {error}")

    print(f"  combination: {key}")
    print(f"  line: {line.key} ({len(current)} task(s)) [{cs.relativize(str(line.lock_path))}]")
    for summary in _baseline_changes(previous, current):
        print(f"  change: {summary}")
    if not reason:
        print("  REFUSED: --update needs --reason. Review the diff above (field paths, not just digests),")
        print(f'           then re-run: --update --line {line.key} --reason "<what moved and why>"')
        return 1

    # this line's entries for this combination are replaced; this line's other
    # combinations are kept, and no other line is written at all
    entries = {stored: value for stored, value in entries.items() if not stored.startswith(f"{key}|")}
    entries.update({entry_key(key, task_id): entry for task_id, entry in current.items()})
    line_lock = {
        "lock_format": LOCK_FORMAT,
        "note": (
            f"recipe golden of line {line.key!r}: entry keys are '<combination>|<task id>' "
            f"and a training run never adds one"
        ),
        # the reason for THIS line's last golden revision lives here, not in the shared
        # combination block: a combination block records why that framework combination
        # was opened at all, and one field there would be overwritten by whichever line
        # updated last (every line's reason would vanish except the newest)
        "reason": reason,
        "reason_at": prov.now(),
        "reason_rev": prov.rev(_REPO),
        "entries": dict(sorted(entries.items())),
    }
    line.lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Written LF, not the platform's line ending: this file is digested by [35], and a digest
    # taken from a CRLF write on Windows would read as drift on the LF checkout every machine
    # gets (.gitattributes). `write_text` translates ``\n`` unless told not to.
    line.lock_path.write_text(
        json.dumps(line_lock, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(
        f"  entries written: {cs.relativize(str(line.lock_path))} "
        f"({line.lock_path.stat().st_size / 1024:.0f} KiB, {len(line_lock['entries'])} entries)"
    )

    if key in baselines:
        print(f"  combination baseline declared: {cs.relativize(str(BASELINES_PATH))} ({len(baselines)} total)")
        return 0
    baselines[key] = {
        "created_at": prov.now(),
        "reason": reason,
        "created_rev": prov.rev(_REPO),
        "created_dirty": bool(prov.git(_REPO, "status", "--porcelain")),
        "combination": combo,
        "cfg_snapshot_format": cs.FORMAT_VERSION,
    }
    shared = {
        "lock_format": LOCK_FORMAT,
        "note": (
            "framework-combination baselines, shared by every recipe line: a combination is a "
            "fact about IsaacLab / rsl_rl / Python, not about any one recipe"
        ),
        "baselines": dict(sorted(baselines.items())),
    }
    BASELINES_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINES_PATH.write_text(  # LF, like the line locks: [35] digests this file
        json.dumps(shared, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"  combination baseline CREATED: {cs.relativize(str(BASELINES_PATH))} ({len(baselines)} total)")
    print("  note: every other line now needs its own entries for this combination (--update --line ...)")
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


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if "--self-test" in args:
        if args != ["--self-test"]:
            raise ValueError("--self-test must be used alone")
        import test_cfg_lock_gate as falsifier

        return falsifier.main()  # includes the real-tree read-only verification
    only: list[str] = []
    if "--tasks" in args:
        only = [t for t in args[args.index("--tasks") + 1].split(",") if t]
    line_arg = _value_of(args, "--line")

    specs = registered_tasks()
    by_line, problems = route_tasks(specs)
    print(f"  registered rl_exp tasks: {len(specs)} in {len(by_line)} declared line(s)")

    try:
        lines = discover()
    except RecipeLineError as err:
        print(f"  DRIFT: recipe line discovery: {err}")
        print("CFG_LOCK_DRIFT (1)")
        return 1
    print(f"  discovered recipe lines: {sorted(lines)}")

    for line_key in sorted(by_line):
        if line_key not in lines:
            problems.append(
                f"{line_key}: {len(by_line[line_key])} task(s) declare this line "
                f"(e.g. {sorted(by_line[line_key])[0]}) but no such line exists {sorted(lines)}"
                f" -- a typo in params_line would send the golden to a file nobody reads"
            )
    if line_arg is not None and line_arg not in lines:
        problems.append(f"--line {line_arg!r} is not a discovered line {sorted(lines)}")

    target = {
        line_key: task_ids
        for line_key, task_ids in by_line.items()
        if line_key in lines and (line_arg is None or line_key == line_arg)
    }
    current = {
        line_key: {task_id: build_entry(task_id, specs[task_id]) for task_id in sorted(task_ids)}
        for line_key, task_ids in sorted(target.items())
    }

    if "--update" in args:
        if line_arg is None:
            print("  REFUSED: --update needs --line <line>. One whole-tree update would rewrite")
            print("           every line's golden under a single reason string, silently absorbing")
            print(f"           any drift in the lines you did not mean to touch. Lines: {sorted(lines)}")
            return 1
        if line_arg not in current:
            print(f"  REFUSED: --line {line_arg!r} has no registered task in a discovered line")
            return 1
        return update(lines[line_arg], current[line_arg], _value_of(args, "--reason"))

    flat_current = {task_id: entry for entries in current.values() for task_id, entry in entries.items()}
    if "--vs-upstream" in args:
        return vs_upstream(flat_current, only)

    baselines, baselines_error = load_baselines()
    if baselines_error:
        problems.append(baselines_error)
        key = None
    else:
        key = verify_baseline(baselines, problems)

    if key is not None:
        for line_key, line_current in current.items():
            entries, entries_error = load_entries(lines[line_key])
            if entries_error:
                problems.append(entries_error)
                continue
            verify_entries(
                lines[line_key], baselines, key, entries, line_current, problems,
                show_diff="--diff" in args, only=only,
            )

    for problem in problems:
        print(f"  DRIFT: {problem}")
    if problems:
        print(f"CFG_LOCK_DRIFT ({len(problems)})")
        return 1
    checked = sum(len(entries) for entries in current.values())
    print(f"CFG_LOCK_OK ({checked} tasks, {len(current)} line(s), {combination_key(combination())})")
    return 0


def _value_of(args: list[str], flag: str) -> str | None:
    """Value following a flag, or None (a bare flag carries no reason)."""
    if flag not in args:
        return None
    index = args.index(flag) + 1
    return args[index] if index < len(args) and not args[index].startswith("--") else None


if __name__ == "__main__":
    # The in-process falsifier must import this instance, not execute a second copy.
    sys.modules.setdefault("check_cfg_lock", sys.modules[__name__])
    raise SystemExit(main())
