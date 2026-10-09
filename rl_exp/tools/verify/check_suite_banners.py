# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Repo-root and batch-banner hygiene: what the shell leaves behind, and what scratch leaves behind.

Two banners in this suite carried that bug for real: ``echo ... task -> recipe ...`` wrote a
stray file named ``config`` into the repo root and swallowed its own banner, and
``echo ... versions\\<line>\\cfg_lock.json`` was an input redirect that errored on every run.
Both were invisible: the shell executes the redirect, prints nothing, and the failure does not
reach the ``|| goto :fail`` on the next line, so the suite stayed green while its output rotted.

**The root scan is the same class of failure, one actor over.** A scratch script dropped at the
repo root is equally invisible -- ``_tmp_*`` is git-ignored, so no gate and no ``git status``
ever reads it -- and 64 of them had accumulated by 2026-10-09 (2026-09-03, 2026-09-22,
2026-09-23, 2026-09-28, 2026-09-29: scripts, probe logs and raw JSON, cited by nine acceptance
records as their reread path, none of them committed and none deleted). The rule existed
(``FILEMAP.md``, tools-by-category) and enforced nothing, which is the debt a convention always
runs up. So the root holds declared entries only, and the deadline is the commit -- the hook
calls this too. Scratch that outlives its task belongs in ``rl_exp/tools/diagnose/`` (a readout
worth rereading) or ``rl_exp/tools/archive/`` (history); the rest gets deleted, not renamed
(the scan is by name-against-declaration, so ``helper.py`` is caught as well).

That is why this is a gate and not a convention. The detection runs against the suite itself,
and it proves its own detector first -- a scanner that quietly matches nothing would have the
same symptom as the bug it exists to catch. Escaping with ``^`` is the fix (``echo(`` does not
help: redirection is parsed out of the raw line before ``echo`` ever sees its arguments).
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
SUITE = _REPO / "rl_exp" / "tools" / "verify" / "run_offline_checks.bat"
_ECHO = re.compile(r"^\s*echo\b(?!\()(?P<text>.*)$", re.IGNORECASE)
_SPECIAL = "<>|&"

#: Every name the repo root may hold. Adding a new top-level file or directory is a one-line
#: change here, in the same commit that creates it -- visible in the diff, unlike the scratch it
#: replaces. Deleting a declared entry without updating this list is also red (``.git`` aside:
#: plumbing, absent in an exported tree). Kept a declaration rather than a pattern because a
#: pattern scan only catches the name someone already thought of (see the module docstring).
DECLARED_ROOT = (
    ".codemaker", ".git", ".gitattributes", ".gitignore", "AGENTS.md", "ARCH_PLAN.md",
    "FILEMAP.md", "README.md", "ablation_harness", "acceptance", "hooks", "papers",
    "paths.example.yaml", "rl_exp", "setup.bat", "work",
)
#: Entries that come and go without anyone deciding anything: the machine-local path config
#: (``paths.yaml``, git-ignored) and the pytest cache. Absent on a fresh clone, and neither is a
#: decision -- so demanding they be present would be the gate crying wolf.
OPTIONAL_ROOT = ("paths.yaml", ".pytest_cache")

ROOT_SELF_TEST: list[tuple[str, list[str], list[str]]] = [
    ("a declared root", [".codemaker", "README.md", "rl_exp", "work", "paths.yaml"], []),
    ("scratch renamed out of the ignored pattern", ["_tmp_foot_read.py", "helper.py"],
     ["_tmp_foot_read.py", "helper.py"]),
    ("the junk file the banner bug wrote", ["config", "rl_exp"], ["config"]),
    ("a new top-level doc, undeclared", ["CONTRIBUTING.md"], ["CONTRIBUTING.md"]),
]


def stray_root(names: list[str], declared: tuple[str, ...] = DECLARED_ROOT,
               optional: tuple[str, ...] = OPTIONAL_ROOT) -> list[str]:
    """Root entries outside the declared set, sorted.

    Args:
        names: the names found in the repo root.
        declared: the entries the root is allowed to hold.
        optional: entries that may or may not be present.

    Returns:
        The names to delete or declare; empty means the root holds nothing it should not.
    """
    allowed = set(declared) | set(optional)
    return sorted(name for name in names if name not in allowed)

SELF_TEST: list[tuple[str, list[str]]] = [
    ("echo [1] a -> b", [">"]),
    ("echo [24] vs versions\\<line>\\cfg_lock.json", ["<", ">"]),
    ("echo a | b", ["|"]),
    ("echo a & b", ["&"]),
    ("  echo indented > file", [">"]),
    ("echo versions\\^<line^>\\cfg_lock.json", []),
    ("echo [31] task id to recipe, revision to entries", []),
    ("echo %PY% rl_exp\\tools\\verify\\check_recipe_map.py --bind-config", []),
    ("echo ALL_OFFLINE_CHECKS_PASSED", []),
    ("if not defined PY for /f \"delims=\" %%p in ('python a.py 2^>nul') do set PY=%%p", []),
    ("echo(WARN: no python", []),
]


def unescaped_specials(text: str) -> list[str]:
    """Special characters the shell would act on, skipping ``^``-escaped ones.

    Args:
        text: the text of one ``echo`` line, after the command word.

    Returns:
        The offending characters in order (empty when the line is inert).
    """
    found: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == "^" and index + 1 < len(text):
            index += 2  # the escape consumes the next character
            continue
        if text[index] in _SPECIAL:
            found.append(text[index])
        index += 1
    return found


def scan(path: pathlib.Path) -> list[str]:
    """Every ``echo`` line in one batch file whose text the shell would not print as written.

    Args:
        path: the batch file to read.

    Returns:
        One problem per offending line; empty means every banner prints what it says.
    """
    out: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        match = _ECHO.match(line)
        if not match:
            continue
        offenders = unescaped_specials(match.group("text"))
        if offenders:
            out.append(
                f"{path.name}:{number}: bare {sorted(set(offenders))} in an echo -- escape it with ^"
                f" or the shell redirects and writes a stray file instead of printing"
            )
    return out


def self_test() -> list[str]:
    """Prove both detectors fire and stay quiet on the shapes they must not touch."""
    problems: list[str] = []
    for line, expected in SELF_TEST:
        match = _ECHO.match(line)
        actual = [] if match is None else unescaped_specials(match.group("text"))
        if actual != expected:
            problems.append(f"detector: {line!r} expected {expected}, got {actual}")
    for label, names, expected in ROOT_SELF_TEST:
        actual = stray_root(names)
        if actual != expected:
            problems.append(f"root detector ({label}): expected {expected}, got {actual}")
    if len(DECLARED_ROOT) < 10:
        problems.append(f"DECLARED_ROOT is down to {len(DECLARED_ROOT)} entries: a truncated list passes every root")
    return problems


def banner_lines(path: pathlib.Path) -> int:
    """How many ``echo`` lines one batch file has (the matcher's own evidence).

    Args:
        path: the batch file to read.

    Returns:
        The count. A scan that matches nothing must not look like a clean scan, so the
        caller treats zero as a problem rather than a pass.
    """
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    return sum(1 for line in text.splitlines() if _ECHO.match(line))


def main(argv: list[str] | None = None) -> int:
    """Scan the suite (and every other batch file in the repo) for banner redirects, and the repo root for undeclared entries."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", default=str(SUITE), help="the batch file to scan")
    args = parser.parse_args(argv)

    problems = self_test()
    if problems:
        for problem in problems:
            print(f"  FAIL {problem}")
        print("repo hygiene gate: the detector itself is broken, a clean scan would mean nothing")
        return 1

    suite = pathlib.Path(args.suite)
    banners = banner_lines(suite)
    if banners == 0:
        problems.append(f"{suite.name}: no echo banners matched -- an empty scan is not a clean scan")
    targets = [suite]
    targets += sorted(p for p in _REPO.rglob("*.bat") if "archive" not in p.parts and p not in targets)
    for path in targets:
        if path.is_file():
            problems.extend(scan(path))

    root = sorted(p.name for p in _REPO.iterdir())
    strays = stray_root(root)
    for name in strays:
        problems.append(
            f"repo root: {name!r} is undeclared -- the root holds declared entries only. Delete the scratch, "
            f"or move a readout worth rereading to rl_exp/tools/diagnose/; a new top-level entry gets declared in "
            f"DECLARED_ROOT ({pathlib.Path(__file__).name}) in the same commit"
        )
    vanished = [name for name in DECLARED_ROOT if name != ".git" and not (_REPO / name).exists()]
    if vanished:
        problems.append(f"repo root: declared entries are gone ({', '.join(vanished)}) -- update DECLARED_ROOT in the same commit")

    print(f"  detector: {len(SELF_TEST) + len(ROOT_SELF_TEST)} shapes verified | banners in {suite.name}: {banners} | batch files: {len(targets)}")
    print(f"  repo root: {len(root)} entries, {len(strays)} undeclared")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print(f"repo hygiene (banners + root): {len(problems)} problem(s)")
        return 1
    print("  every echo banner prints as written; the repo root holds only declared entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
