# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""No second copy of the terrain column split (ARCH_PLAN Step 3.3d's scan gate).

Step 3.3's own failure mode, named in the plan: if the migration stops at the probe, the two
copies the curricula used to carry quietly grow back -- a third copy is one paste away, and
nothing about it looks wrong until the generator's rule moves and the copies do not.

The scan looks for the rule's signature in **code**, not in prose: comments and strings are
dropped before matching, so a comment or docstring may quote the old line (this file does) and
a real copy cannot hide behind a `# noqa`. ``rl_exp/tasks/terrain_map.py`` is the one home.

Signature: the boundary epsilon applied to a column fraction (``col / num_cols + 0.001``), or
an epsilon next to a cumulative sum in the same file -- the second catches the line after a
rename of either side. The detector is self-tested here, so a green run cannot mean "matcher
broke".

**Scope, honestly (work/active/record-variant-and-snapshot-specs.md ②):** this is a paste detector, not a semantics check. A rule
rewritten so that no literal survives -- ``1e-3``, a tolerance derived from the grid, a
``searchsorted``/``floor`` boundary -- shares no token with the copy and is out of this scan's
reach by construction. That direction is held where it can be decided: a record whose declared
mapping is not ``terrain_map.column_split``'s output is refused by ``terrain_map.check`` at the
consumption boundary (see ``test_terrain_map.py``), so a second *rule* cannot be consumed even
though this scan cannot see it written.
"""

from __future__ import annotations

import pathlib
import re
import sys
import tokenize

_REPO = pathlib.Path(__file__).resolve().parents[3]
_HOME = _REPO / "rl_exp" / "tasks" / "terrain_map.py"
_ROOTS = ("rl_exp", "ablation_harness")

#: ``<name> / <name> + 0.001`` -- the epsilon welded to a column fraction.
_FRACTION_EPSILON = re.compile(r"/\s*[A-Za-z_][\w.]*\s*\+\s*0\.001")
_EPSILON = re.compile(r"0\.001")
_CUMULATIVE = re.compile(r"\bcum(?:sum|ulative)?\b|\bnp\.cumsum\b")


def code_lines(path: pathlib.Path) -> dict[int, str]:
    """Source lines with comments and string literals removed.

    Prose has to stay out of reach: a docstring explaining the rule, or a comment quoting the
    old line, is documentation, while the same text as code is a copy. Tokenizing rather than
    regexing the raw text is what keeps those two apart.
    """
    skip = {
        tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
        tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER,
    }
    lines: dict[int, list[str]] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            tokens = list(tokenize.generate_tokens(handle.readline))
    except (OSError, SyntaxError, tokenize.TokenError, IndentationError):
        return {}
    for token in tokens:
        if token.type in skip:
            continue
        lines.setdefault(token.start[0], []).append(token.string)
    return {line: " ".join(parts) for line, parts in lines.items()}


def offenders(text_by_line: dict[int, str]) -> list[str]:
    """Findings for one file's code lines, as ``line N: <code>`` strings."""
    found = []
    whole = " ".join(text_by_line.values())
    for line, code in text_by_line.items():
        if _FRACTION_EPSILON.search(code):
            found.append(f"line {line}: {code.strip()}")
    if _EPSILON.search(whole) and _CUMULATIVE.search(whole):
        found.append("epsilon and a cumulative sum in one file (the rule's shape, however renamed)")
    return found


def _self_test() -> list[str]:
    """The matcher must fire on the old code line and stay quiet on the same text as prose."""
    problems: list[str] = []
    copy = {7: "frac = col / num_cols + 0.001"}
    if not offenders(copy):
        problems.append("the detector missed the copied line it exists for")
    prose = {3: "def f():"}  # a docstring/comment mention leaves no tokens behind
    if offenders(prose):
        problems.append(f"the detector fired on prose: {offenders(prose)}")
    renamed = {1: "acc = np.cumsum(w)", 2: "eps = 0.001"}
    if not any("cumulative" in finding for finding in offenders(renamed)):
        problems.append("the epsilon-plus-cumulative-sum fallback never fires")
    return problems


def main() -> int:
    self_test_problems = _self_test()
    scanned = 0
    findings: list[tuple[str, list[str]]] = []
    for root in _ROOTS:
        for path in sorted((_REPO / root).rglob("*.py")):
            if path == _HOME:
                continue
            scanned += 1
            lines = code_lines(path)
            hits = offenders(lines)
            if hits:
                findings.append((path.relative_to(_REPO).as_posix(), hits))
    for problem in self_test_problems:
        print(f"  self-test: {problem}")
    for path, hits in findings:
        for hit in hits:
            print(f"  {path}: {hit}")
    if self_test_problems or findings:
        print(
            f"TERRAIN_SPLIT_SINGLE_SOURCE_VIOLATED ({len(self_test_problems)} self-test, "
            f"{len(findings)} file(s)): the rule belongs in {_HOME.relative_to(_REPO).as_posix()} only"
        )
        return 1
    print(f"terrain split rule: one home ({_HOME.relative_to(_REPO).as_posix()}), {scanned} file(s) clean")
    print("TERRAIN_SPLIT_SINGLE_SOURCE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
