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
WHY_TODO_ENV = "TODO: this element writes this path -- say why (compared against the framework stock cfg)"
WHY_TODO_AGENT = "TODO: this leaf is set where the stock leaves it unset -- say why"


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


def agent_entry(line: str) -> str:
    """The runner cfg this line's recipes name, read from the recipe map rather than guessed."""
    data = json.loads((_EXP / "versions" / "recipes.json").read_text(encoding="utf-8"))
    for key, entry in data["recipes"].items():
        if entry.get("line") == line and "play" not in key:
            return entry["agent_entry"]
    raise SystemExit(f"no recipe entry names line {line!r}")


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

    wiring_rows: list = []
    lock.walk_diff(cs.snapshot(stock_cls()), cs.snapshot(wiring(params_version=version)), "", wiring_rows,
                   limit=1 << 30)
    wiring_except = sorted(row[0] for row in wiring_rows)

    subject = recipe.build(version, line=line_key)
    env_rows = leaf_rows(stock_cls(), subject)
    changed = [row[0] for row in env_rows]
    env_briefs = {row[0]: str(row[2]) for row in env_rows}

    trace: list = []
    recipe.build(version, trace=trace, line=line_key)
    produced = crb.authored_paths(trace, line_key, version)
    # last writer wins: a path several elements touch in sequence still has one element that set its
    # final value, and the gate accepts any element that really moved it.
    author_of = {leaf: name for name in produced for leaf in produced[name] if leaf in changed}

    env_allowed: dict[str, dict] = {}
    unowned = []
    for leaf in changed:
        author = author_of.get(leaf)
        if author is None:
            unowned.append(leaf)
            continue
        env_allowed.setdefault(author, {"paths": [], "why": WHY_TODO_ENV})["paths"].append(leaf)
    for group in env_allowed.values():
        group["paths"].sort()

    agent_handle = agent_entry(line_key)
    agent_cls = lock.resolve_entry(agent_handle)
    agent_rows = leaf_rows(lock.resolve_entry(AGENT_STOCK)(), agent_cls())
    agent_changed = [row[0] for row in agent_rows]
    agent_briefs = {row[0]: str(row[2]) for row in agent_rows}
    declaration = {
        "format": 4,
        "recipe": None,  # filled by the caller's recipe key lookup below
        "line": line_key,
        "note": (
            "Hard B, root reading: base.json is null (a lineage root has no mother), so the declared"
            " difference is against the framework stock cfg -- the only base a root can have. This file"
            " was COMPUTED from this recipe's own resolved cfg (rl_exp/tools/pipeline/emit_diff_declaration.py):"
            " the paths are the leaves that differ from stock and the element named under each group is the one"
            " that moved them in the replay, so the paths here cannot disagree with the build. The why strings"
            " are TODO until an author writes them: hard B compares paths, not prose, so an unwritten reason is"
            " a review item rather than a wrong claim."
        ),
        "base": {"stock": stock_handle, "wiring": f"{wiring.__module__}:{wiring.__name__}",
                 "wiring_is_stock_except": wiring_except},
        "env": {"allowed": env_allowed},
        "agent": {"stock": AGENT_STOCK,
                  "why": "The agent is a class, not a declaration: these entries carry a reason and no element name.",
                  "allowed": {path: WHY_TODO_AGENT for path in sorted(agent_changed)}},
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
    print(f"[emit] {args.line}/{args.version}: {len(declaration['env']['allowed'])} element groups, "
          f"{env_paths} env paths, {len(declaration['agent']['allowed'])} agent leaves, "
          f"base {declaration['base']['stock']} + {declaration['base']['wiring_is_stock_except']}",
          file=sys.stderr)
    if unowned:
        print(f"[emit] {len(unowned)} changed path(s) no element claims: {unowned[:5]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
