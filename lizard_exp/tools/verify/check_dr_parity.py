# -*- coding: utf-8 -*-
"""Static parity gate for the freeze/determinism contracts (no sim, plain python).

Three checks, all machine-readable, all fail under --strict:

1. teacher-vs-family DR wiring: extracts every ``self.<manager>.<term>`` wiring
   line from the family and teacher cfg files and reports the symmetric
   difference. The teacher snapshot deliberately duplicates the DR wiring
   (freeze discipline: no family imports) -- intentional divergence is fine,
   but it must be REVIEWED, never accidental.
2. DR event list sync: ``play_utils.DR_EVENT_NAMES`` (PLAY variants) must equal
   ``dr_controller._DR_EVENT_NAMES`` (eval modes). Two physical copies exist by
   design (the harness stays robot-agnostic); this check makes drift loud.
3. PLAY wiring coverage: every ``*_PLAY`` cfg class must call
   ``apply_play_wiring`` -- the block that hand-copies drifted twice historically.

Usage: python lizard_exp\\tools\\verify\\check_dr_parity.py [--strict]
"""
import argparse
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
_TASKS = _REPO / "lizard_exp" / "tasks"
_FAMILY = _TASKS / "lizard_env_cfg.py"
_TEACHER = _TASKS / "teacher_env_cfg.py"
_PLAY_UTILS = _TASKS / "play_utils.py"
_DR_CONTROLLER = _REPO / "ablation_harness" / "components" / "dr_controller.py"

# wiring lines that only exist on one side BY DESIGN (reviewed divergences)
ALLOWLIST: set[str] = set()

# PLAY classes that legitimately skip apply_play_wiring (reviewed exceptions)
PLAY_WIRING_ALLOWLIST: set[str] = set()


def wiring_lines(path: pathlib.Path) -> list[str]:
    pat = re.compile(r"^\s*self\.(events|rewards|terminations)\.\w+")
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if pat.match(line):
            out.append(re.sub(r"\s+", " ", line.strip()))
    return out


def _extract_name_list(path: pathlib.Path, var_name: str) -> list[str]:
    """Pull the string items out of a module-level ``VAR = [...]`` list."""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^{var_name} = \[(.*?)\]", text, re.M | re.S)
    if match is None:
        raise RuntimeError(f"list '{var_name}' not found in {path}")
    return re.findall(r'"([^"]+)"', match.group(1))


def check_wiring_parity() -> list[str]:
    problems = []
    fam = [l for l in wiring_lines(_FAMILY) if l not in ALLOWLIST]
    tea = [l for l in wiring_lines(_TEACHER) if l not in ALLOWLIST]
    fam_set, tea_set = set(fam), set(tea)
    for line in sorted(fam_set - tea_set):
        problems.append(f"family-only wiring line: {line}")
    for line in sorted(tea_set - fam_set):
        problems.append(f"teacher-only wiring line: {line}")
    print(f"  family wiring lines: {len(fam_set)} | teacher wiring lines: {len(tea_set)}")
    return problems


def check_dr_list_sync() -> list[str]:
    play = _extract_name_list(_PLAY_UTILS, "DR_EVENT_NAMES")
    harness = _extract_name_list(_DR_CONTROLLER, "_DR_EVENT_NAMES")
    print(f"  play_utils: {len(play)} events | dr_controller: {len(harness)} events")
    problems = []
    for name in sorted(set(play) - set(harness)):
        problems.append(f"in play_utils.DR_EVENT_NAMES but not dr_controller._DR_EVENT_NAMES: {name}")
    for name in sorted(set(harness) - set(play)):
        problems.append(f"in dr_controller._DR_EVENT_NAMES but not play_utils.DR_EVENT_NAMES: {name}")
    return problems


def check_play_wiring_coverage() -> list[str]:
    """Every *_PLAY configclass in tasks/*.py must call apply_play_wiring."""
    problems = []
    class_pat = re.compile(r"^class (\w*PLAY\w*)\(", re.M)
    for path in sorted(_TASKS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in class_pat.finditer(text):
            name = match.group(1)
            body = text[match.end():]
            nxt = re.search(r"^class ", body, re.M)
            if nxt is not None:
                body = body[:nxt.start()]
            if "apply_play_wiring(" not in body:
                if name not in PLAY_WIRING_ALLOWLIST:
                    problems.append(f"{path.name}: class {name} does not call apply_play_wiring")
    print(f"  PLAY classes checked")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    checks = {
        "wiring parity (family vs teacher)": check_wiring_parity,
        "DR event list sync (play_utils vs dr_controller)": check_dr_list_sync,
        "PLAY wiring coverage (apply_play_wiring)": check_play_wiring_coverage,
    }
    all_problems = []
    for title, fn in checks.items():
        print(f"[check] {title}")
        problems = fn()
        if problems:
            for p in problems:
                print(f"  DRIFT: {p}")
            all_problems.extend(problems)

    if not all_problems:
        print("PARITY_OK")
        return 0
    print(f"PARITY_DRIFT ({len(all_problems)} problem(s); review whether each diff is "
          f"intentional; allowlists in this script)")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
