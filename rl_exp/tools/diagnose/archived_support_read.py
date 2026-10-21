# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Read four invalidated Phase 1/3 archives without Kit or original output paths.

Index format 1: ``packages`` is a list of entries containing ``old_root`` (the
logical repo-relative name), ``new_relative_root``, ``schema`` (smoke_p1c/d or v10_run2/3),
``files`` (relative filename -> bare SHA256), and ``producer_source`` with
``relative_path`` (relative to storage_root, outside package), ``commit`` and
``sha256``. Sources must be verbatim ``git show <commit>:<producer path>`` bytes.
The index is caller-approved routing, NOT an externally signed approval.

Only stored 50 Hz stats are rendered using pinned historical main AST statements;
10 Hz series_json is never analyzed. Original timestamp is retained, not recreated.
Successful comparison proves archive readability, not validity of old measurements.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "rl_exp" / "tools" / "runrecord"))
from binding import sha256_file  # noqa: E402

PRODUCER_PATH = "rl_exp/tools/diagnose/diagnose_support.py"
PINS = {
    "smoke_p1c": (
        "d5ff5ce791262f7825fcb6836e2f6fe353b3a551",
        "a2c8e807b1c0741fae0ea3aefddca879937ec3edfd6bbd65b6d4a9a7b83c7009",
    ),
    "smoke_p1d": (
        "29deefe0acf735b8af4359d221fb21a888734668",
        "c4a02e0f5ed8acbc7b25237bb7fbf4c5a58c6f3367a69d1f5452890431b9bd32",
    ),
}
PINS.update({name: PINS["smoke_p1c"] for name in ("v10_run2", "v10_run3")})
LOGICAL_ROOTS = {f"rl_exp/tools/diagnose/out/{name}": name for name in PINS}
FILES = {"p1a_zero_action_5s.json", "p1b_policy_still_10s.json", "summary.md"}
FILE_SETS = {
    name: ({f"p3_steps_r{rep}.json" for rep in range(3)} | {"summary.md"}
           if name.startswith("v10_run") else FILES)
    for name in PINS
}


def _inside(root: pathlib.Path, relative: str) -> pathlib.Path:
    """Resolve portable relative paths; refuse traversal, drive names and symlinks."""
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError(f"invalid relative path: {relative!r}")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"path escape: {relative!r}")
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escape: {relative!r}")
    if any(root.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts) + 1)):
        raise ValueError(f"symlink not allowed: {relative!r}")
    return path


def _checked_file(path: pathlib.Path, digest: str) -> None:
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"invalid digest: {path}")
    if not path.is_file() or sha256_file(path) != digest:
        raise ValueError(f"digest mismatch or missing file: {path}")


def _assigned(node: ast.AST, name: str) -> bool:
    return (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name)


def _phase1_ast(source: str, phase: int = 1) -> ast.Module:
    """Select pinned Phase 1 or 3 summary statements, never imports/main rollout."""
    tree = ast.parse(source)
    mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    if len(mains) != 1:
        raise ValueError("producer must contain exactly one main")
    body = mains[0].body
    starts = [i for i, node in enumerate(body) if _assigned(node, "lines")]
    ends = [i for i, node in enumerate(body) if _assigned(node, "summary")]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("unrecognized summary boundaries")
    start, end = starts[0], ends[0]
    segment = body[start:end + 1]
    if (len(segment) != 8 or not _assigned(segment[1], "p1")
            or not isinstance(segment[2], ast.If)
            or ast.dump(segment[2].test) != ast.dump(ast.Name(id="p1", ctx=ast.Load()))
            or len(segment[2].body) != 2
            or not isinstance(segment[2].body[0], ast.AugAssign)
            or not isinstance(segment[2].body[1], ast.For)
            or not _assigned(segment[3], "p2") or not _assigned(segment[5], "p3")
            or not _assigned(segment[-1], "summary")):
        raise ValueError("unrecognized Phase 1 AST")
    # Source hash is pinned before parsing: no caller/JSON-supplied code reaches exec.
    # Builtins below are renderer dependencies, not a sandbox; the whole-source pin
    # is the code trust boundary. Skip timestamp and every simulator statement.
    if phase == 3:
        if (not isinstance(segment[6], ast.If)
                or ast.dump(segment[6].test) != ast.dump(ast.Name(id="p3", ctx=ast.Load()))):
            raise ValueError("unrecognized Phase 3 AST")
        selected = [segment[5], segment[6], segment[-1]]
    elif phase == 1:
        selected = [segment[1], segment[2], segment[-1]]
    else:
        raise ValueError("unsupported summary phase")
    return ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))


def read_archive(index: pathlib.Path, package: str, storage_root: pathlib.Path = REPO) -> str:
    """Verify archive bytes and render stored stats; return exact original summary."""
    if package not in LOGICAL_ROOTS:
        raise ValueError(f"unknown logical root: {package}")
    data = json.loads(index.read_text(encoding="utf-8"))
    entries = data.get("packages")
    if (data.get("format") != 1 or not isinstance(entries, list)
            or any(not isinstance(entry, dict) for entry in entries)):
        raise ValueError("expected index format 1 with packages list")
    roots = [entry.get("old_root") for entry in entries]
    if len(roots) != len(set(roots)) or any(root not in LOGICAL_ROOTS for root in roots):
        raise ValueError("duplicate or unknown logical root in index")
    matches = [entry for entry in entries if entry.get("old_root") == package]
    if len(matches) != 1:
        raise ValueError(f"missing mapping: {package}")
    entry = matches[0]
    schema = LOGICAL_ROOTS[package]
    if entry.get("schema") != schema:
        raise ValueError("schema mismatch")
    root = storage_root.resolve()
    new_root = _inside(root, entry["new_relative_root"])
    if new_root == _inside(root, package):
        raise ValueError("archive mapping must not read old root")
    expected_files = FILE_SETS[schema]
    files = entry.get("files")
    if not isinstance(files, dict) or set(files) != expected_files:
        raise ValueError(f"file set mismatch for {schema}")
    if not new_root.is_dir() or {p.name for p in new_root.iterdir()} != expected_files:
        raise ValueError("archive file set mismatch")
    for name, digest in files.items():
        _checked_file(_inside(new_root, name), digest)
    producer = entry["producer_source"]
    if (producer.get("commit"), producer.get("sha256")) != PINS[schema]:
        raise ValueError("producer pin mismatch")
    source_path = _inside(root, producer["relative_path"])
    if source_path.is_relative_to(new_root):
        raise ValueError("producer metadata must be outside package")
    _checked_file(source_path, producer["sha256"])
    phase = 3 if schema.startswith("v10_run") else 1
    renderer = _phase1_ast(source_path.read_text(encoding="utf-8"), phase)
    original = (new_root / "summary.md").read_bytes().decode("utf-8")
    header = original.split("\n", 1)[0]
    if not re.fullmatch(r"# v10 支撑诊断 summary（\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}）", header):
        raise ValueError("unrecognized original timestamp header")
    records = {}
    for name in sorted(expected_files - {"summary.md"}):
        record = json.loads((new_root / name).read_text(encoding="utf-8"))
        case = record.get("case")
        if case != pathlib.Path(name).stem or case in records:
            raise ValueError("case identity mismatch")
        # Only renderer inputs: never feed series_json to execution.
        records[case] = {"case": case, "stats": record["stats"]}
    namespace = {"lines": [header, ""]}
    if phase == 1:
        order = re.findall(r"^\| (p1[^ |]+) \|", original, re.MULTILINE)
        if len(order) != len(records) or set(order) != set(records):
            raise ValueError("summary case rows mismatch")
    else:
        order = sorted(records)  # Fixed r0/r1/r2 file set is producer repetition order.
        rows = re.findall(r"^\| ([1-9]\d*)cm \| (up|down) \|", original, re.MULTILINE)
        tags = [tag for tag, direction in rows if direction == "up"]
        if (not tags or len(tags) != len(set(tags))
                or rows != [(tag, direction) for tag in tags for direction in ("up", "down")]):
            raise ValueError("summary height rows mismatch")
        stat_keys = {"flat"} | {f"{direction}_{tag}" for tag, direction in rows}
        if any(set(record["stats"]) != stat_keys for record in records.values()):
            raise ValueError("stats height keys mismatch")
        # Explicit historical table order, checked against every stored stats key set.
        namespace["heights"] = [int(tag) / 100 for tag in tags]
    namespace["results"] = [records[case] for case in order]
    exec(compile(renderer, str(source_path), "exec"),
         {"__builtins__": {"str": str, "int": int, "round": round, "set": set,
                           "sorted": sorted, "len": len}}, namespace)
    rendered = namespace["summary"]
    if rendered != original:
        raise ValueError("stored stats do not reproduce historical summary")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=pathlib.Path, required=True)
    parser.add_argument("--package", required=True, choices=LOGICAL_ROOTS)
    parser.add_argument("--storage_root", type=pathlib.Path, default=REPO)
    args = parser.parse_args()
    try:
        summary = read_archive(args.index, args.package, args.storage_root)
    except (ValueError, OSError, KeyError, TypeError, SyntaxError) as exc:
        parser.exit(1, f"ARCHIVED_SUPPORT_REFUSED: {exc}\n")
    sys.stdout.write(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
