# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Offline-suite shape: one list, one process per check, no hidden interpreter children.

Three rules, each of which the suite already broke for real (OFFLINE_CHECKS.md):

**One list.** The check list lived in the batch file, and adding a gate meant an entry
there plus a banner line, so the two could disagree about what ran. The list is
``offline_suite.py``'s ``CHECKS``; the batch file only calls the runner.

**One interpreter per check.** A check that starts ``sys.executable`` pays the interpreter
+ torch import again (~2.5 s, and two thirds of the checks are import-bound). That is how a
suite gets slower every iteration without anyone writing slow code. Children are allowed,
but only where a *declared* reason says the process boundary is the point, and the declared
count is compared with the code -- so growth shows up in review instead of in the wall
clock.

**A scan that finds nothing is not a clean scan.** Every rule is a pure function
(``shape_problems``) so the self-test can falsify each one against fabricated input: a gate
that quietly passes because it matched nothing has the same symptom as the rule it keeps.

Cost budgets are *not* here: they need timings, so the runner enforces them. This gate is
static and stdlib-only on purpose -- it stays runnable when the venv is broken, which is
exactly when the suite's shape is suspect.

Usage: python rl_exp\\tools\\verify\\check_suite_shape.py
"""

from __future__ import annotations

import pathlib
import re
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
SUITE = _HERE / "run_offline_checks.bat"
RUNNER = "offline_suite.py"

# A check may start its own interpreter only where the process boundary is what is being
# tested. The count is the contract: it is compared with the code below, so a new
# interpreter child cannot land without declaring itself here.
SPAWN_ALLOWED: dict[str, tuple[int, str]] = {
    "test_cfg_snapshot.py": (1, "the digest must be identical from two PYTHONHASHSEED runs"),
    "test_dump_tb_sampling.py": (2, "the CLI resample path only exists in dump_tb.py's __main__"),
}

# an invocation of a check script by name, which is the second list this gate forbids
_CHECK_INVOCATION = re.compile(r"(?:check|test)_\w+\.py")
# the spawn marker: a subprocess call whose argument list starts with the live interpreter
# (newlines allowed between the two, since the real one spans lines)
_SPAWN = re.compile(r"subprocess\.\w+\(\s*\[\s*sys\.executable")
_REM = re.compile(r"^\s*(?:REM\b|::)", re.IGNORECASE)

# Fixtures are assembled from pieces on purpose: written whole, this file would itself look
# like it starts interpreters per run, and the gate would have to exempt itself to pass.
_SPAWN_SELF_TEST: list[tuple[str, bool]] = [
    ('subprocess.run(' + '[sys.executable, "-c", code], capture_output=True, text=True)', True),
    ('proc = subprocess.run(\n            ' + '[sys.executable, "-c", code], env=env)', True),
    ('subprocess.run(["git", *args], cwd=root)', False),
    ("exe = pathlib.Path(" + "sys.executable)", False),  # reads the path, never starts it
]

_BAT_SELF_TEST: list[tuple[str, bool]] = [
    ('"%PY%" rl_exp\\tools\\verify\\check_cfg_lock.py || goto :fail', True),
    ("REM rl_exp\\tools\\verify\\framework_pin_check.py", False),
    ('"%PY%" rl_exp\\tools\\verify\\offline_suite.py --python "%PY%" %*', False),
    # naming a check in prose is still a copy of the list, one rename away from a lie
    ("echo rl_exp\\tools\\verify\\test_recipe_lines.py", True),
]

_CLEAN_CHECK = ("a check", ["rl_exp/tools/verify/a_check.py"])
_CLEAN_BAT = f'"%PY%" rl_exp\\tools\\verify\\{RUNNER} --python "%PY%" %*'


def _spawns(text: str) -> int:
    """How many times one script starts its own interpreter."""
    return len(_SPAWN.findall(text))


def _bat_invocations(text: str) -> list[str]:
    """Check scripts the batch file invokes itself (``REM`` lines are prose, not calls)."""
    return [
        match.group(0)
        for line in text.splitlines()
        if not _REM.match(line)
        for match in _CHECK_INVOCATION.finditer(line)
    ]


def shape_problems(
    checks: list[tuple[str, list[str]]],
    bat_text: str,
    present: set[str],
    spawn_counts: dict[str, int],
) -> list[str]:
    """Every structural rule, as a pure function so each one can be falsified.

    Args:
        checks: the runner's ``CHECKS`` (label, argv after the interpreter).
        bat_text: the entry-point batch file's text.
        present: names of the check scripts that exist next to the runner.
        spawn_counts: script name -> how many interpreter children its text starts.

    Returns:
        One problem per broken rule; empty means the shape is intact.
    """
    problems: list[str] = []
    if not checks:
        return ["the check list is empty -- a scan that finds nothing is not a clean scan"]

    scripts = [pathlib.Path(argv[0]).name for _, argv in checks]
    duplicates = sorted({name for name in scripts if scripts.count(name) > 1})
    if duplicates:
        problems.append(f"the same script is checked twice: {duplicates} (its cost is paid twice)")
    for _, argv in checks:
        if pathlib.Path(argv[0]).name not in present:
            problems.append(f"{argv[0]}: listed in CHECKS but not on disk -- the suite would fail here")

    if RUNNER not in bat_text:
        problems.append(f"{SUITE.name}: does not call {RUNNER}, so nothing would run")
    named = _bat_invocations(bat_text)
    if named:
        problems.append(
            f"{SUITE.name}: names check scripts itself ({sorted(set(named))}) -- the list is "
            f"{RUNNER}'s CHECKS, and a second copy drifts into 'the suite ran something other "
            f"than what is written down'"
        )

    declared = {name: count for name, (count, _) in SPAWN_ALLOWED.items() if name in scripts}
    actual = {name: count for name, count in spawn_counts.items() if count and name in scripts}
    for name in sorted(set(actual) | set(declared)):
        if name not in actual:
            problems.append(f"{name}: declared in SPAWN_ALLOWED but no longer spawns -- drop the entry")
        elif name not in declared:
            problems.append(
                f"{name}: spawns a interpreter {actual[name]}x without declaring it -- each child "
                f"re-pays the import (~2.5s); declare it in SPAWN_ALLOWED with a reason, or keep "
                f"the cases in-process"
            )
        elif actual[name] != declared[name]:
            problems.append(f"{name}: spawns {actual[name]}x, declared {declared[name]}x -- declare the growth")
    return problems


def self_test() -> list[str]:
    """Prove both detectors fire, and that every structural rule fires on its own falsifier."""
    problems: list[str] = []
    for line, expected in _BAT_SELF_TEST:
        if bool(_bat_invocations(line)) != expected:
            problems.append(f"bat detector: {line!r} expected {expected}")
    for snippet, expected in _SPAWN_SELF_TEST:
        if bool(_spawns(snippet)) != expected:
            problems.append(f"spawn detector: {snippet!r} expected {expected}")

    def fired(checks, bat, present, counts, needle: str) -> bool:
        return any(needle in problem for problem in shape_problems(checks, bat, present, counts))

    good = {pathlib.Path(_CLEAN_CHECK[1][0]).name}
    if shape_problems([_CLEAN_CHECK], _CLEAN_BAT, good, {}):
        problems.append("a clean shape was reported as broken")
    if not fired([], _CLEAN_BAT, set(), {}, "empty"):
        problems.append("an empty check list was not reported")
    if not fired([_CLEAN_CHECK], _CLEAN_BAT, set(), {}, "not on disk"):
        problems.append("a CHECKS entry with no file was not reported")
    if not fired([_CLEAN_CHECK, _CLEAN_CHECK], _CLEAN_BAT, good, {}, "twice"):
        problems.append("the same script listed twice was not reported")
    if not fired([_CLEAN_CHECK], "REM nothing here", good, {}, "does not call"):
        problems.append("a batch file that never calls the runner was not reported")
    if not fired([_CLEAN_CHECK], _CLEAN_BAT + "\n\"%PY%\" x\\check_a.py\n", good, {}, "names check scripts"):
        problems.append("a batch file naming its own check was not reported")
    declared_name = next(iter(SPAWN_ALLOWED))
    declared_check = ("declared", [f"rl_exp/tools/verify/{declared_name}"])
    if not fired([_CLEAN_CHECK], _CLEAN_BAT, good, {"a_check.py": 1}, "without declaring"):
        problems.append("an undeclared interpreter child was not reported")
    if not fired(
        [declared_check],
        _CLEAN_BAT,
        {declared_name},
        {declared_name: SPAWN_ALLOWED[declared_name][0] + 1},
        "declare the growth",
    ):
        problems.append("an interpreter child that multiplied was not reported")
    if not fired([declared_check], _CLEAN_BAT, {declared_name}, {}, "drop the entry"):
        problems.append("a stale SPAWN_ALLOWED entry was not reported")
    return problems


def main() -> int:
    """Read the suite from disk and report every structural rule it breaks."""
    import offline_suite  # the one list, imported rather than parsed

    checks = offline_suite.CHECKS
    present = {
        pathlib.Path(argv[0]).name
        for _, argv in checks
        if (_REPO / argv[0]).is_file()
    }
    counts = {
        name: _spawns((_HERE / name).read_text(encoding="utf-8", errors="replace"))
        for name in present
    }
    bat = SUITE.read_text(encoding="utf-8", errors="replace") if SUITE.is_file() else ""

    problems = self_test() + shape_problems(checks, bat, present, counts)
    declared = sum(1 for name in counts if name in SPAWN_ALLOWED)
    print(f"  checks: {len(checks)} | interpreter children declared: {declared} | {SUITE.name}: 1 runner call")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print(f"suite shape: {len(problems)} problem(s)")
        return 1
    print("SUITE_SHAPE_OK (one list, one process per check, no undeclared children)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
