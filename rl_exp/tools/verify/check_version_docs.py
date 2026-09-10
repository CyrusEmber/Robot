# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Version-record completeness gate (no sim, stdlib only -- pre-commit safe).

Mechanizes versioning.mdc section A steps 2 and 5: every recipe version
directory ships the four-piece set (PLAN.md, NOTES.md, lizard_params.yaml,
asset_lock.json locking its own yaml), the family FAMILY.md version-history
table carries its row, and FILEMAP.md lists the directory. Ungated
conventions were the root cause of the v10/v11 record debt (v11 NOTES.md
missing at kickoff, FAMILY/FILEMAP lagging two versions), so the same drift
now turns red like any other freeze-contract violation.

Known ceiling (warn, not fail): git tags. Legacy versions predate the tag
discipline and prefix styles differ (v1/v2/v5 vs lizard-vN), so a missing
tag only warns; per versioning.mdc A, a training run started without a tag
means "treat as frozen" and the tag must be added immediately.
"""

import json
import pathlib
import re
import subprocess

_REPO = pathlib.Path(__file__).resolve().parents[3]
_VERSIONS = _REPO / "rl_exp" / "versions"


def _git_tags() -> set[str]:
    try:
        out = subprocess.run(
            ["git", "tag", "--list"], capture_output=True, text=True, check=True, cwd=_REPO
        ).stdout
        return {line.strip() for line in out.splitlines() if line.strip()}
    except (OSError, subprocess.CalledProcessError):
        return set()


def main() -> int:
    problems: list[str] = []
    warnings: list[str] = []
    tags = _git_tags()
    filemap_text = (_REPO / "FILEMAP.md").read_text(encoding="utf-8")
    families = sorted(p for p in _VERSIONS.iterdir() if p.is_dir())

    for family_dir in families:
        family = family_dir.name
        family_md = family_dir / "FAMILY.md"
        if not family_md.is_file():
            problems.append(f"{family}: versions/{family}/FAMILY.md missing")
            family_text = ""
        else:
            family_text = family_md.read_text(encoding="utf-8")

        for vdir in sorted(p for p in family_dir.glob("v[0-9]*") if p.is_dir()):
            name = vdir.name
            for piece in ("PLAN.md", "NOTES.md", "lizard_params.yaml", "asset_lock.json"):
                if not (vdir / piece).is_file():
                    problems.append(
                        f"{family}/{name}: {piece} missing (versioning.mdc A-2 four-piece set)"
                    )
            lock_path = vdir / "asset_lock.json"
            if lock_path.is_file():
                try:
                    lock = json.loads(lock_path.read_text(encoding="utf-8"))
                    key = f"versions/{family}/{name}/lizard_params.yaml"
                    if key not in lock.get("files", {}):
                        problems.append(
                            f"{family}/{name}: asset_lock.json does not lock its own yaml ({key})"
                        )
                except (json.JSONDecodeError, OSError) as err:
                    problems.append(f"{family}/{name}: asset_lock.json unreadable ({err})")
            if not re.search(rf"^\|\s*{name}\s*\|", family_text, re.MULTILINE):
                problems.append(
                    f"{family}/{name}: no '| {name} |' row in FAMILY.md version history (versioning.mdc A-5)"
                )
            if f"{family}\\{name}\\" not in filemap_text:
                problems.append(
                    f"{family}/{name}: no '{family}\\{name}\\' row in FILEMAP.md (versioning.mdc A-5)"
                )
            if not any(
                t == name or t == f"{family}-{name}" or t.startswith(f"{family}-{name}.")
                for t in tags
            ):
                warnings.append(
                    f"{family}/{name}: no git tag ({name} or {family}-{name}[.minor]) --"
                    " fine for proposals; must exist once training starts"
                )

    print(f"  families checked: {len(families)} ({', '.join(p.name for p in families)})")
    for warn in warnings:
        print(f"  WARN: {warn}")
    for problem in problems:
        print(f"  DRIFT: {problem}")
    if problems:
        print(f"VERSION_DOCS_DRIFT ({len(problems)})")
        return 1
    print("VERSION_DOCS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
