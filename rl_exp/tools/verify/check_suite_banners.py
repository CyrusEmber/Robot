# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Batch-file banner hygiene: an unescaped ``<``/``>``/``|``/``&`` in an ``echo`` is a redirect.

Two banners in this suite carried that bug for real: ``echo ... task -> recipe ...`` wrote a
stray file named ``config`` into the repo root and swallowed its own banner, and
``echo ... versions\\<line>\\cfg_lock.json`` was an input redirect that errored on every run.
Both were invisible: the shell executes the redirect, prints nothing, and the failure does not
reach the ``|| goto :fail`` on the next line, so the suite stayed green while its output rotted.

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
    """Prove the detector fires and stays quiet on the shapes it must not touch."""
    problems: list[str] = []
    for line, expected in SELF_TEST:
        match = _ECHO.match(line)
        actual = [] if match is None else unescaped_specials(match.group("text"))
        if actual != expected:
            problems.append(f"detector: {line!r} expected {expected}, got {actual}")
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
    """Scan the suite (and every other batch file in the repo) for banner redirects."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", default=str(SUITE), help="the batch file to scan")
    args = parser.parse_args(argv)

    problems = self_test()
    if problems:
        for problem in problems:
            print(f"  FAIL {problem}")
        print("suite banner gate: the detector itself is broken, a clean scan would mean nothing")
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
    print(f"  detector: {len(SELF_TEST)} shapes verified | banners in {suite.name}: {banners} | batch files: {len(targets)}")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print(f"suite banners: {len(problems)} problem(s)")
        return 1
    print("  every echo banner prints as written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
