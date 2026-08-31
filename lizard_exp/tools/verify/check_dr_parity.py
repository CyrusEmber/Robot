# -*- coding: utf-8 -*-
"""Static parity check: teacher cfg must wire DR/events identically to the family.

The teacher snapshot deliberately duplicates ~180 lines of DR wiring from the
family cfg (freeze discipline: no family imports). This script extracts every
``self.<manager>.<term>`` wiring line from both files and reports the symmetric
difference -- intentional divergence is fine, but it must be REVIEWED, never
accidental. Run it whenever either file changes.

Usage: python lizard_exp\\tools\\verify\\check_dr_parity.py [--strict]
  --strict: exit 1 when any difference exists (CI-style guard)
"""
import argparse
import pathlib
import re
import sys

_HERE = __file__
_REPO = pathlib.Path(_HERE).resolve().parents[3]
FAMILY = _REPO / "lizard_exp" / "tasks" / "lizard_env_cfg.py"
TEACHER = _REPO / "lizard_exp" / "tasks" / "teacher_env_cfg.py"

# wiring lines that only exist on one side BY DESIGN (reviewed divergences)
ALLOWLIST = {
    "self.events.reset_robot_joints = None",  # family PLAY only (view_lizard helper)
}


def wiring_lines(path: pathlib.Path) -> list[str]:
    pat = re.compile(r"^\s*self\.(events|rewards|terminations)\.\w+")
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if pat.match(line):
            out.append(re.sub(r"\s+", " ", line.strip()))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    fam = [l for l in wiring_lines(FAMILY) if l not in ALLOWLIST]
    tea = [l for l in wiring_lines(TEACHER) if l not in ALLOWLIST]

    fam_set, tea_set = set(fam), set(tea)
    only_family = sorted(fam_set - tea_set)
    only_teacher = sorted(tea_set - fam_set)

    print(f"family wiring lines: {len(fam_set)} | teacher wiring lines: {len(tea_set)}")
    for line in only_family:
        print(f"  family-only: {line}")
    for line in only_teacher:
        print(f"  teacher-only: {line}")

    if not only_family and not only_teacher:
        print("PARITY_OK")
        return 0
    print("PARITY_DRIFT (review whether each diff is intentional; allowlist in this script)")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
