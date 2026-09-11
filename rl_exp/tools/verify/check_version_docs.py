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

Lineage gate: every version dir carries base.json naming its single
ancestry parent (the one frozen snapshot this recipe was modified from;
decision references to other versions stay in PLAN.md prose). The lineage
numbers in FAMILY.md are handles, not an ordering contract -- the DAG in
base.json files is the SSOT, so v7<-v6 vs v9<-v8 rebases never break
neighbors' records.

Side lines (versioning.mdc A, 分线条款: versions/<family>/<line>/vN/) are
found recursively and keyed by family-relative path ("parkour/v1"), so their
records are gated the same as main-line vN.
"""

import json
import pathlib
import re
import subprocess
import sys

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


def main(show_tree: bool = "--tree" in sys.argv) -> int:
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

        # recursive: side lines (versions/<family>/<line>/vN/, versioning.mdc A
        # 分线条款) are keyed by family-relative path, e.g. "parkour/v1"
        rels = sorted(
            "/".join(p.relative_to(family_dir).parts)
            for p in family_dir.rglob("v[0-9]*")
            if p.is_dir()
        )
        parent: dict[str, str | None] = {}
        for rel in rels:
            vdir = family_dir.joinpath(*rel.split("/"))
            own_yaml = sorted(f.name for f in vdir.glob("*_params.yaml"))
            if len(own_yaml) != 1:
                problems.append(
                    f"{family}/{rel}: expected exactly one *_params.yaml, found "
                    f"{own_yaml or 'none'} (versioning.mdc A-2 four-piece set)"
                )
            for piece in ("PLAN.md", "NOTES.md", "asset_lock.json"):
                if not (vdir / piece).is_file():
                    problems.append(
                        f"{family}/{rel}: {piece} missing (versioning.mdc A-2 four-piece set)"
                    )
            lock_path = vdir / "asset_lock.json"
            if lock_path.is_file() and own_yaml:
                try:
                    lock = json.loads(lock_path.read_text(encoding="utf-8"))
                    key = f"versions/{family}/{rel}/{own_yaml[0]}"
                    if key not in lock.get("files", {}):
                        problems.append(
                            f"{family}/{rel}: asset_lock.json does not lock its own yaml ({key})"
                        )
                except (json.JSONDecodeError, OSError) as err:
                    problems.append(f"{family}/{rel}: asset_lock.json unreadable ({err})")
            if not re.search(rf"^\|\s*{re.escape(rel)}\s*\|", family_text, re.MULTILINE):
                problems.append(
                    f"{family}/{rel}: no '| {rel} |' row in FAMILY.md version history (versioning.mdc A-5)"
                )
            filemap_key = family + "\\" + rel.replace("/", "\\") + "\\"
            if filemap_key not in filemap_text:
                problems.append(
                    f"{family}/{rel}: no '{filemap_key}' row in FILEMAP.md (versioning.mdc A-5)"
                )
            # line versions need the qualified prefix: bare "v1" would collide
            # with the main line's first generation
            leaf = rel.rsplit("/", 1)[-1]
            tag_stem = f"{family}-{rel.replace('/', '-')}" if "/" in rel else f"{family}-{leaf}"
            if not any(
                t == tag_stem
                or t.startswith(f"{tag_stem}.")
                or ("/" not in rel and t == leaf)  # legacy unprefixed main-line tags
                for t in tags
            ):
                warnings.append(
                    f"{family}/{rel}: no git tag ({leaf} or {tag_stem}[.minor]) --"
                    " fine for proposals; must exist once training starts"
                )
            base_path = vdir / "base.json"
            if not base_path.is_file():
                problems.append(
                    f"{family}/{rel}: base.json missing (lineage edge -- versioning.mdc A-2)"
                )
                continue
            try:
                data = json.loads(base_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as err:
                problems.append(f"{family}/{rel}: base.json unreadable ({err})")
                continue
            if "base" not in data:
                problems.append(f"{family}/{rel}: base.json has no 'base' field (root uses null)")
            else:
                parent[rel] = data["base"]

        # pass 2: resolve + validate edges now that every base.json is
        # collected; a bare base name resolves inside the version's own line
        edges: dict[str, str] = {}
        for rel, base in parent.items():
            if base is None:
                continue  # lineage root
            line_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
            cand = base if base in rels else (f"{line_dir}/{base}" if line_dir else base)
            if cand not in rels:
                problems.append(f"{family}/{rel}: base '{base}' is not a known version")
            elif cand not in parent:
                problems.append(f"{family}/{rel}: base '{base}' has no base.json itself")
            else:
                edges[rel] = cand

        # cycle guard over the resolved lineage edges
        for start in edges:
            seen = {start}
            node: str | None = edges[start]
            while node is not None:
                if node in seen:
                    problems.append(f"{family}/{start}: lineage cycle through {node}")
                    break
                seen.add(node)
                node = edges.get(node)

        if show_tree and rels:
            children: dict[str | None, list[str]] = {}
            for rel in rels:
                children.setdefault(edges.get(rel), []).append(rel)

            def _sort_key(s: str) -> tuple:
                line, leaf = s.rsplit("/", 1) if "/" in s else ("", s)
                return (line, int(re.search(r"\d+", leaf).group()))

            def _walk(node: str, indent: int) -> None:
                print(f"  {'  ' * indent}{node}")
                for child in sorted(children.get(node, []), key=_sort_key):
                    _walk(child, indent + 1)

            print(f"  lineage tree ({family}):")
            for root in sorted(children.get(None, []), key=_sort_key):
                _walk(root, 0)

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
