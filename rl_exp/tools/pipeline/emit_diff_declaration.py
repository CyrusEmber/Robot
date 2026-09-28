# -*- coding: utf-8 -*-
"""Emit a recipe's difference declaration (`diff.json`) from ITS OWN resolved cfg.

Hard B asks a recipe to list the paths where it differs from the framework stock cfg, and to name,
per path, the element that wrote it. Both halves are computable from the recipe itself:

* the changed leaves come from ``walk_diff(snapshot(stock), snapshot(subject))``, the same walker the
  gate uses, so "the declaration agrees with the build" holds by construction rather than by review;
* the author of each leaf comes from ``recipe.build(version, trace=trace)`` replayed element by
  element -- the same replay the gate's attribution check runs, so the two cannot disagree.

Nothing is read from another family: a new family's declaration is derived from that family module and its own params. This is the replacemement for cloning a sibling line's
``diff.json`` and renaming its element keys (which produced names that do not exist on the target
line the first time it was tried).

Usage (from {rl_exp}/tools/pipeline):
    <venv python> emit_diff_declaration.py --line lizard2/main --version v1
    <venv python> emit_diff_declaration.py --line lizard2/main --version v1 --out <path>
Prints the JSON by default; --out writes it. The ``why`` fields are emitted as TODO on purpose: a
reason is a human claim about intent, and inventing one here would be the tool answering a question
only the author can answer. ``--out`` onto an existing declaration PRESERVES the reasons already
written for the same env path set and the same agent leaves, so re-emitting cannot delete prose.
"""

import argparse
import hashlib
import importlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
_EXP = _REPO / "rl_exp"
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_EXP / "tools" / "verify"))

import cfg_snapshot as cs  # noqa: E402
import check_cfg_lock as lock  # noqa: E402 - the sibling that owns snapshot/diff/lock reading
import check_recipe_build as crb  # noqa: E402 - the gate that owns the hard-B mechanism
from rl_exp.tasks import recipe  # noqa: E402

AGENT_STOCK = "isaaclab_rl.rsl_rl:RslRlOnPolicyRunnerCfg"

ROOT_NOTE = (
    "Hard B, root reading: base.json is null (a lineage root has no mother), so the declared"
    " difference is against the framework stock cfg -- the only base a root can have. This file"
    " was COMPUTED from this recipe's own resolved cfg (rl_exp/tools/pipeline/emit_diff_declaration.py):"
    " the paths are the leaves that differ from stock and the element named under each group is the one"
    " that moved them in the replay, so the paths here cannot disagree with the build. The why strings"
    " are TODO until an author writes them: hard B compares paths, not prose, so an unwritten reason is"
    " a review item rather than a wrong claim."
)

LINEAGE_NOTE = (
    "Hard B, lineage reading: base.json names {mother} as this recipe's mother, so the declared"
    " difference is against that recipe -- not against the framework stock cfg, which would bury this"
    " version's own delta inside everything its ancestors already wrote. Env paths are grouped by the"
    " element that last moved them in the replay, so the paths here cannot disagree with the build;"
    " params_version is filtered as identity, because it says which recipe this is and it is what makes"
    " the two recipes different at all. The why strings are TODO until an author writes them: hard B"
    " compares paths, not prose, so an unwritten reason is a review item rather than a wrong claim."
)


def why_todo_env(mother: str | None) -> str:
    """The unwritten-reason placeholder, naming the base this declaration is read against."""
    return ("TODO: this element writes this path -- say why (compared against "
            f"{f'its mother {mother}' if mother else 'the framework stock cfg'})")


def why_todo_agent(mother: str | None) -> str:
    """Same, for an agent leaf. The root wording is kept byte-for-byte: it is what existing root
    declarations carry, and a re-emit must not look like an edit."""
    return ("TODO: this leaf is set where "
            f"{f'mother {mother}' if mother else 'the stock'} leaves it unset -- say why")


AGENT_WHY = ("The agent is a class, not a declaration: these entries carry a reason and no element"
             " name.")


def wiring_class(family: str, line_key: str):
    """The family's wiring class for `line_key`, found by the statement it makes about itself.

    Each line's wiring declares ``params_line = "<family>/<line>"`` -- the full handle, not the bare
    line name; scanning for that statement keeps this tool from owning a name table that would
    silently go stale.
    """
    module = importlib.import_module(f"rl_exp.tasks.{family}_env_cfg")
    hits = [obj for obj in vars(module).values()
            if isinstance(obj, type) and getattr(obj, "params_line", None) == line_key]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one wiring class declaring params_line={line_key!r} in "
                         f"rl_exp.tasks.{family}_env_cfg, found {[h.__name__ for h in hits]}")
    return hits[0]


def stock_parent(wiring) -> tuple[type, str]:
    """The framework stock cfg the wiring derives from, and its resolvable handle."""
    for base in wiring.__mro__[1:]:
        module = getattr(base, "__module__", "")
        if module.startswith("isaaclab_tasks."):
            return base, f"{module}:{base.__name__}"
    raise SystemExit(f"{wiring.__name__} has no isaaclab_tasks parent: it is not a stock-derived wiring")


def base_mother(line_key: str, version: str) -> str | None:
    """The mother this version's ``base.json`` names, or ``None`` for a lineage root.

    The base is neither this tool's choice nor the declaration's: ``base.json`` decides it, and the
    gate reads the same file to decide what to compare against (``check_recipe_build.base_of`` says
    so from its side, and refuses a declaration whose stock block contradicts it). Reading it here is
    what stops a version that has a mother from being emitted as if it were a root -- which is what
    this tool did while it had one reading, and why every later version on a line had to be written
    by hand until now.
    """
    path = _EXP / "versions" / line_key / version / "base.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("base")
    except (OSError, json.JSONDecodeError) as err:
        raise SystemExit(f"{line_key}/{version}: base.json unreadable: {type(err).__name__}: {err}")


def leaf_rows(base_obj, subject_obj) -> list[tuple[str, str, str]]:
    """Changed leaves as ``(path, base value, subject value)``, identity fields dropped."""
    rows: list = []
    lock.walk_diff(cs.snapshot(base_obj), cs.snapshot(subject_obj), "", rows, limit=1 << 30)
    return [row for row in rows if row[0].split(".")[0] not in crb.IDENTITY_FIELDS]


def leaves(base_obj, subject_obj) -> list[str]:
    return [row[0] for row in leaf_rows(base_obj, subject_obj)]


def build(line_key: str, version: str) -> dict:
    family, line = line_key.split("/")
    wiring = wiring_class(family, line_key)
    stock_cls, stock_handle = stock_parent(wiring)
    mother = base_mother(line_key, version)

    # The stock/wiring walk has a reader only in the root reading's ``base`` block. A version with a
    # mother is read against that recipe, so the walk is not paid for -- and, more to the point, it
    # cannot end up in a block the gate refuses as a second answer to the base question.
    wiring_except: list = []
    if mother is None:
        wiring_rows: list = []
        lock.walk_diff(cs.snapshot(stock_cls()), cs.snapshot(wiring(params_version=version)), "",
                       wiring_rows, limit=1 << 30)
        wiring_except = sorted(row[0] for row in wiring_rows)

    subject = recipe.build(version, line=line_key)
    base_cfg = stock_cls() if mother is None else recipe.build(mother, line=line_key)
    env_rows = leaf_rows(base_cfg, subject)
    changed = [row[0] for row in env_rows]
    env_briefs = {row[0]: str(row[2]) for row in env_rows}

    trace: list = []
    recipe.build(version, trace=trace, line=line_key)
    produced = crb.authored_paths(trace, line_key, version)
    # Declare what the REPLAY says each element moved, not the leaf the mother comparison landed on.
    # The two granularities differ whenever an element rewrites a whole sub-cfg while only one leaf
    # under it actually moved: the replay says ``actions.joint_pos_legs``, the comparison against a
    # mother says ``actions.joint_pos_legs.joint_names[]``. The gate asks whether the entry COVERS a
    # path the element moved (``check_recipe_build.hard_b``), so the entry has to sit at or above the
    # replay's path; last writer wins, because a path several elements touch still has one element
    # that set its final value and the gate accepts any element that really moved it.
    author_of: dict[str, tuple[str, str]] = {}
    for name in reversed([name for name, _ in trace]):
        for moved in sorted(produced.get(name, ())):
            for leaf in changed:
                if leaf not in author_of and crb.covers(moved, leaf):
                    author_of[leaf] = (name, moved)

    env_allowed: dict[str, dict] = {}
    unowned = []
    declared: set[str] = set()
    for leaf in changed:
        found = author_of.get(leaf)
        if found is None:
            unowned.append(leaf)
            continue
        author, entry = found
        group = env_allowed.setdefault(author, {"paths": [], "why": why_todo_env(mother)})
        if entry not in declared:
            declared.add(entry)
            group["paths"].append(entry)
    for group in env_allowed.values():
        group["paths"].sort()

    # The agent side is read against the same base as the env side: the mother's runner cfg when there
    # is one, the stock runner otherwise. The gate resolves the base the same way, and a ``stock`` key
    # here is the second answer that would contradict ``base.json``.
    agent_cls = lock.resolve_entry(crb.agent_entry(line_key, version))
    agent_base_handle = crb.agent_entry(line_key, mother) if mother else AGENT_STOCK
    agent_rows = leaf_rows(lock.resolve_entry(agent_base_handle)(), agent_cls())
    agent_changed = [row[0] for row in agent_rows]
    agent_briefs = {row[0]: str(row[2]) for row in agent_rows}
    if mother is None:
        declaration = {
            "format": 4,
            "recipe": None,  # filled by the caller's recipe key lookup below
            "line": line_key,
            "note": ROOT_NOTE,
            "base": {"stock": stock_handle, "wiring": f"{wiring.__module__}:{wiring.__name__}",
                     "wiring_is_stock_except": wiring_except},
            "env": {"allowed": env_allowed},
            "agent": {"stock": AGENT_STOCK, "why": AGENT_WHY,
                      "allowed": {path: why_todo_agent(None) for path in sorted(agent_changed)}},
        }
    else:
        declaration = {
            "format": 4,
            "recipe": None,  # filled by the caller's recipe key lookup below
            "line": line_key,
            "note": LINEAGE_NOTE.format(mother=mother),
            "env": {"allowed": env_allowed},
            "agent": {"why": AGENT_WHY,
                      "allowed": {path: why_todo_agent(mother) for path in sorted(agent_changed)}},
        }
    data = json.loads((_EXP / "versions" / "recipes.json").read_text(encoding="utf-8"))
    for key, entry in data["recipes"].items():
        if entry.get("line") == line_key and entry.get("legacy_task_version") == version:
            declaration["recipe"] = key
            break
    if declaration["recipe"] is None:
        raise SystemExit(f"no recipe key for line {line_key} version {version}")
    # what each reason will be compared against on the next emit: paths alone are not enough, because
    # a reason also asserts numbers ("10000 -- ...", "the exp kernel replaced by the miki kernel")
    env_digests = {author: _values_digest({path: env_briefs.get(path, "") for path in group["paths"]})
                   for author, group in env_allowed.items()}
    return declaration, unowned, env_digests, _values_digest(agent_briefs)


REVIEW_FLAG = (" [REVIEW: the values this reason was written against have changed since -- re-read it"
               " against the current numbers]")
"""Appended to a reason whose numbers moved. The TEXT IS KEPT: rewriting it is the author's job, and
dropping it would delete the only prose this file has (review 2026-09-22)."""


def _values_digest(pairs: dict[str, str]) -> str:
    """A short digest over ``{path: rendered value}`` -- what a reason was written against.

    Recorded at the top level (``authored_against``) rather than inside each reason: the file stays
    readable when nothing moved, and the REVIEW flag appears only where it is true.
    """
    return hashlib.sha256(json.dumps(dict(sorted(pairs.items())), sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _flag(reason: str) -> str:
    """``reason`` + the REVIEW flag, unless it is unwritten or already flagged."""
    if not isinstance(reason, str) or not reason.strip() or "REVIEW:" in reason or reason.lstrip().startswith("TODO"):
        return reason
    return reason.rstrip() + REVIEW_FLAG


def carry_reasons(declaration: dict, previous: dict | None, env_digests: dict | None = None,
                  agent_digest: str | None = None) -> list[str]:
    """Keep the authored ``why`` strings a previous declaration carries; MARK the ones whose values moved.

    The reasons are the one part of this file a generator cannot write, so a re-emit must not be a way
    to delete them -- nor a way to silently approve numbers they no longer describe. Both directions:

    * an env group's reason describes a path set AND the values on it. Both live in the group's digest,
      so a changed digest (a path that appeared or vanished, or a number that moved) keeps the original
      text and flags it for review instead of quietly approving the new state;
    * an agent leaf's reason describes its value: the whole agent section carries one digest, and a
      mismatch flags every authored reason in it.

    The digests written this time are the baseline the NEXT emit compares against, so the flag fires
    exactly once per change rather than on every run.
    """
    notes: list[str] = []
    declaration["authored_against"] = {"env": dict(sorted((env_digests or {}).items())),
                                       "agent": agent_digest}
    if not isinstance(previous, dict):
        return notes
    old = previous.get("authored_against") or {}
    old_env_digests = old.get("env") if isinstance(old.get("env"), dict) else {}
    old_env_why = ((previous.get("env") or {}).get("allowed")) or {}
    old_agent_why = ((previous.get("agent") or {}).get("allowed")) or {}
    flagged = []
    for author, group in declaration["env"]["allowed"].items():
        written = old_env_why.get(author)
        written = written.get("why") if isinstance(written, dict) else None
        if isinstance(written, str) and written.strip():
            group["why"] = written  # the author's text is the only prose this file has: carry it
        if old_env_digests.get(author) and old_env_digests[author] != (env_digests or {}).get(author):
            group["why"] = _flag(group["why"])
            flagged.append(author)
    for leaf in declaration["agent"]["allowed"]:
        written = old_agent_why.get(leaf)
        if isinstance(written, str) and written.strip():
            declaration["agent"]["allowed"][leaf] = written
    if old.get("agent") and old["agent"] != agent_digest:
        for leaf, why in declaration["agent"]["allowed"].items():
            declaration["agent"]["allowed"][leaf] = _flag(why)
        flagged.append("agent")
    if flagged:
        notes.append("values moved since these reasons were written, so they are kept WITH a REVIEW flag"
                     f" (re-read them): {flagged}")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--line", required=True, help="family-relative line handle, e.g. lizard2/main")
    parser.add_argument("--version", required=True, help="version handle, e.g. v1")
    parser.add_argument("--out", help="write here instead of printing")
    args = parser.parse_args()

    declaration, unowned, env_values, agent_values = build(args.line, args.version)
    previous = None
    if args.out and pathlib.Path(args.out).is_file():
        try:
            previous = json.loads(pathlib.Path(args.out).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None
    notes = carry_reasons(declaration, previous, env_values, agent_values)
    text = json.dumps(declaration, indent=2, sort_keys=False) + "\n"
    for note in notes:
        print(f"note: {note}")
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    else:
        print(text)
    env_paths = sum(len(g["paths"]) for g in declaration["env"]["allowed"].values())
    # The base line is read from the declaration the same way the gate reads it: a stock block for a
    # lineage root, and for a version with a mother the mother -- which ``build`` already resolved, so
    # the summary cannot describe a different reading than the file it just wrote.
    base_desc = (f"base {declaration['base']['stock']} + {declaration['base']['wiring_is_stock_except']}"
                 if "base" in declaration else f"base mother {base_mother(args.line, args.version)}")
    print(f"[emit] {args.line}/{args.version}: {len(declaration['env']['allowed'])} element groups, "
          f"{env_paths} env paths, {len(declaration['agent']['allowed'])} agent leaves, {base_desc}",
          file=sys.stderr)
    if unowned:
        print(f"[emit] {len(unowned)} changed path(s) no element claims: {unowned[:5]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
