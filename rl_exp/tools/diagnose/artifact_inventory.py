# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Read-only diagnostic inventory; stdlib, no simulation, migration or deletion.

CLI: artifact_inventory.py --output FRESH.json [--repo REPO]
Default roots: rl_exp/out and rl_exp/tools/diagnose/out. Output parent must exist.
All entries/packages remain pending, writer/runtime unknown, approved_delete false.
Hashes bind observed bytes, NOT an atomic snapshot or proof that writers stopped.
Directories/symlinks have no content hash; links/junctions are never traversed.

Reference discovery is lexical, not execution tracing: bounded UTF-8 text files
in the repository, plus existing JSON input paths recursively (including external
local paths). JSON string values and path-shaped keys resolve against source parent
then repository; repo-prefixed paths prefer repository. Missing explicit JSON paths
have bounded audit evidence, not graph edges. Cycles terminate by visited path. Directory
references conservatively associate all descendant packages. No date-name rules.
Text over 8 MiB, caches, binaries, unreadable files and missing/dynamic paths cannot
prove absence of consumers. Skips/errors and limits are recorded in the snapshot.
Git uses two batch commands, not per-entry subprocesses. Tracked paths are not
reported as ignored by Git. Transitive consumers are lexical mentions only.
Exit 0 means snapshot written, not lifecycle acceptance. Exit 2 means CLI/read/write failure.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file

ROOTS = ("rl_exp/out", "rl_exp/tools/diagnose/out")
TEXT_SUFFIXES = {".py", ".json", ".yaml", ".yml", ".md", ".mdc", ".txt", ".log",
                 ".csv", ".toml", ".ini", ".cfg", ".bat", ".ps1", ".sh", ".xml", ".urdf"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
             ".cache", "cache", "node_modules", ".venv", "venv", "env_isaaclab"}
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_REFERENCE_FILES = 20000
MAX_UNRESOLVED_REFERENCES = 1000
PATH_TOKEN = re.compile(r"(?:[A-Za-z]:/|/|\.{1,2}/)?(?:[\w.@+-]+/)+[\w.@+-]*")
QUOTED = re.compile(r"[`\"']([^`\"'\r\n]+)[`\"']")


def path_label(path: Path, repo: Path) -> str:
    """Return repository-relative or absolute POSIX spelling."""
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()


def is_link(path: Path) -> bool:
    """Reject symlinks and Windows junction/reparse points."""
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def signature(info: os.stat_result) -> tuple:
    return info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino


def enumerate_root(root: Path, repo: Path) -> tuple[dict, list]:
    """Enumerate every directory and file without following links."""
    entries, errors = {}, []
    stack = [root]
    while stack:
        path = stack.pop()
        label = path_label(path, repo)
        try:
            info = path.lstat()
            kind = "link" if is_link(path) else "directory" if stat.S_ISDIR(info.st_mode) else "file"
            entries[label] = {"path": label, "kind": kind, "signature": signature(info),
                              "size_bytes": info.st_size if kind == "file" else None}
            if kind == "directory":
                stack.extend(sorted(path.iterdir(), reverse=True))
        except OSError as exc:
            entries[label] = {"path": label, "kind": "unknown", "signature": None, "size_bytes": None}
            errors.append({"path": label, "error": str(exc)})
    return entries, errors


def git_states(repo: Path, labels: list[str]) -> tuple[set | None, set | None, list]:
    """Batch tracked/ignored lookup; Git failures stay unknown."""
    errors = []
    results = []
    commands = (["ls-files", "-z", "--cached"], ["check-ignore", "-z", "--stdin"])
    for index, args in enumerate(commands):
        try:
            result = subprocess.run(["git", "-C", str(repo), *args],
                                    input=("\0".join(labels) + "\0").encode("utf-8") if index else None,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if result.returncode not in ({0, 1} if index else {0}):
                raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
            results.append(set(result.stdout.decode("utf-8").split("\0")) - {""})
        except (OSError, RuntimeError, UnicodeError) as exc:
            results.append(None)
            errors.append({"operation": "git " + " ".join(args), "error": str(exc)})
    return results[0], results[1], errors


def json_strings(value: object):
    """Yield string values and path-shaped keys; keys use pointer/@key evidence."""
    stack = [("", value)]
    while stack:
        pointer, item = stack.pop()
        if isinstance(item, str):
            yield pointer, item
        elif isinstance(item, dict):
            for key, child in item.items():
                location = pointer + "/" + str(key).replace("~", "~0").replace("/", "~1")
                stack.append((location, child))
                if isinstance(key, str) and ("/" in key or "\\" in key or Path(key).is_absolute()):
                    yield location + "/@key", key
        elif isinstance(item, list):
            stack.extend((pointer + "/" + str(index), child) for index, child in enumerate(item))


def resolve_paths(value: str, source: Path, repo: Path) -> set[Path]:
    """Resolve existing local literal paths; no basename guessing or eval."""
    normalized = value.replace("\\\\", "/").replace("\\", "/")
    candidates = {normalized.strip(), *PATH_TOKEN.findall(normalized), *QUOTED.findall(normalized)}
    found = set()
    for candidate in candidates:
        candidate = candidate.strip().rstrip(".,;:")
        if not candidate or "\x00" in candidate or "://" in candidate:
            continue
        path = Path(candidate)
        # Require path syntax, or an existing file-like basename in a JSON value.
        if "/" not in candidate and not path.suffix:
            continue
        bases = [repo, source.parent] if candidate.startswith(("rl_exp/", "work/", "acceptance/")) else [source.parent, repo]
        for base in bases:
            target = Path(os.path.abspath(path if path.is_absolute() else base / path))
            try:
                if target.exists():
                    found.add(target)
                    break
            except OSError:
                continue
    return found


def discover_references(repo: Path, excluded: set[Path]) -> tuple[list, dict]:
    """Scan bounded repository text and recursively reached external JSON inputs."""
    queue = deque()
    audit = {"max_text_bytes": MAX_TEXT_BYTES, "max_reference_files": MAX_REFERENCE_FILES,
             "max_unresolved_references": MAX_UNRESOLVED_REFERENCES,
             "unresolved": [], "unresolved_truncated": 0,
             "excluded_directories": sorted(SKIP_DIRS), "skipped": [], "errors": [], "scanned_files": 0}
    for directory, names, files in os.walk(repo, followlinks=False,
                                          onerror=lambda exc: audit["errors"].append({"error": str(exc)})):
        parent = Path(directory)
        safe_names = []
        for name in names:
            child = parent / name
            try:
                if name not in SKIP_DIRS and not is_link(child):
                    safe_names.append(name)
            except OSError as exc:
                audit["errors"].append({"path": path_label(child, repo), "error": str(exc)})
        names[:] = sorted(safe_names)
        queue.extend(parent / name for name in sorted(files) if Path(name).suffix.lower() in TEXT_SUFFIXES)
    edges, seen, dedup = [], set(), set()
    while queue and len(seen) < MAX_REFERENCE_FILES:
        source = queue.popleft()
        if source in seen or source in excluded:
            continue
        seen.add(source)
        label = path_label(source, repo)
        try:
            if is_link(source) or source.stat().st_size > MAX_TEXT_BYTES:
                audit["skipped"].append({"path": label, "reason": "link_or_text_size_limit"})
                continue
            text = source.read_text(encoding="utf-8-sig")
            if "\x00" in text:
                audit["skipped"].append({"path": label, "reason": "binary_text"})
                continue
            audit["scanned_files"] += 1
            if source.suffix.lower() == ".json":
                values = [(pointer, value, "json_input") for pointer, value in json_strings(json.loads(text))]
            else:
                values = [(str(line), value, "text_reference") for line, value in enumerate(text.splitlines(), 1)]
            for location, value, kind in values:
                targets = resolve_paths(value, source, repo)
                if kind == "json_input":
                    literal = value.replace("\\", "/").strip()
                    explicit = (literal and "\x00" not in literal and "://" not in literal
                                and not re.fullmatch(r"[0-9a-fA-F]{32,}", literal)
                                and (Path(literal).is_absolute() or literal.startswith(("rl_exp/", "./", "../"))
                                     or Path(literal).suffix.lower() in TEXT_SUFFIXES | {
                                         ".obj", ".stl", ".usd", ".usda", ".blend", ".bin",
                                         ".gif", ".png", ".mp4", ".pt"}))
                    if explicit:
                        path = Path(literal)
                        candidates = {Path(os.path.abspath(path if path.is_absolute() else base / path))
                                      for base in (source.parent, repo)}
                        if not targets & candidates:
                            if len(audit["unresolved"]) < MAX_UNRESOLVED_REFERENCES:
                                audit["unresolved"].append({"source": label, "location": location,
                                                            "value": value})
                            else:
                                audit["unresolved_truncated"] += 1
                for target in sorted(targets):
                    target_label = path_label(target, repo)
                    key = label, target_label, kind, location
                    if key in dedup:
                        continue
                    dedup.add(key)
                    category = ("work" if label.startswith("work/") else
                                "acceptance" if label.startswith("acceptance/") else
                                "code" if source.suffix.lower() == ".py" else
                                "config" if source.suffix.lower() in {".yaml", ".yml", ".toml", ".ini", ".cfg"} else
                                "report")
                    edges.append({"source": label, "target": target_label, "kind": kind,
                                  "source_category": category, "location": location})
                    if kind == "json_input" and target.suffix.lower() == ".json" and target.is_file():
                        queue.append(target)
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            audit["errors"].append({"path": label, "error": str(exc)})
    if queue:
        audit["skipped"].append({"reason": "reference_file_budget", "queued": len(queue)})
    return edges, audit


def reachable(seeds: set[str], graph: dict[str, set[str]]) -> list[str]:
    """Cycle-safe closure; excludes initial seeds."""
    seen, stack = set(seeds), list(seeds)
    while stack:
        for target in graph.get(stack.pop(), ()):
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return sorted(seen - seeds)


def inventory(repo: Path, roots: tuple[str, ...] = ROOTS, excluded: set[Path] | None = None) -> dict:
    """Build a conservative observation, without writing or approving deletion."""
    repo = Path(os.path.abspath(repo))
    started = datetime.now(timezone.utc).isoformat()
    entries, root_rows, errors = {}, [], []
    for root in roots:
        rows, problems = enumerate_root(repo / root, repo)
        entries.update(rows)
        errors.extend(problems)
        root_rows.append({"path": root, "boundary_status": "unknown" if problems else "observed",
                          "initial_entries": len(rows)})
    tracked, ignored, git_errors = git_states(repo, sorted(entries))
    errors.extend(git_errors)
    packages = {}
    for label, row in sorted(entries.items()):
        root = next(root for root in roots if label == root or label.startswith(root + "/"))
        relative = label[len(root):].lstrip("/")
        package = root + "/" + relative.split("/")[0] if relative else None
        row.update({"root": root, "package": package, "tracked": label in tracked if tracked is not None else None,
                    "ignored": label in ignored if ignored is not None else None,
                    "sha256": None, "observation_status": "observed", "runtime_status": "unknown",
                    "writer_status": "unknown", "status": "pending", "approved_delete": False,
                    "owner": "diagnostic-artifact-lifecycle executor",
                    "next": "verify producer/consumer/value/writer"})
        if row["kind"] == "file":
            try:
                row["sha256"] = sha256_file(repo / label)
                if row["sha256"] is None:
                    raise OSError("file unreadable during hashing")
                if signature((repo / label).stat()) != row["signature"]:
                    row["observation_status"] = "unknown"
                    row["hash_error"] = "file_changed_during_hash"
            except OSError as exc:
                row["observation_status"] = "unknown"
                row["hash_error"] = str(exc)
        elif row["kind"] in {"link", "unknown"}:
            row["observation_status"] = "unknown"
        if package:
            if package not in packages:
                packages[package] = {"path": package, "root": root, "files": 0, "directories": 0,
                                     "links": 0, "size_bytes": 0, "tracked_files": 0, "ignored_files": 0,
                                     "unknown_entries": 0, "status": "pending", "approved_delete": False,
                                     "transitive_consumers_kind": "lexical_mention_only",
                                     "owner": row["owner"], "next": row["next"], "writer_status": "unknown",
                                     "runtime_status": "unknown"}
            item = packages[package]
            item["files"] += row["kind"] == "file"
            item["directories"] += row["kind"] == "directory"
            item["links"] += row["kind"] == "link"
            item["size_bytes"] += row["size_bytes"] or 0
            item["tracked_files"] += row["kind"] == "file" and row["tracked"] is True
            item["ignored_files"] += row["kind"] == "file" and row["ignored"] is True
    edges, reference_audit = discover_references(repo, excluded or set())
    forward, reverse = defaultdict(set), defaultdict(set)
    for edge in edges:
        forward[edge["source"]].add(edge["target"])
        reverse[edge["target"]].add(edge["source"])
    for package, item in packages.items():
        root = item["root"]
        seeds = {label for label, row in entries.items() if row["package"] == package}
        # A literal ancestor directory reference may consume any descendant.
        ancestors = {label for label in reverse if package.startswith(label.rstrip("/") + "/")}
        incoming = [i for i, edge in enumerate(edges) if edge["target"] in seeds | ancestors]
        outgoing = [i for i, edge in enumerate(edges) if edge["source"] in seeds]
        item["direct_reference_edges"] = incoming
        item["direct_input_edges"] = outgoing
        item["transitive_consumers"] = reachable(seeds | ancestors, reverse)
        item["transitive_inputs"] = reachable(seeds, forward)
    for root_row in root_rows:
        root = root_row["path"]
        after, problems = enumerate_root(repo / root, repo)
        before = {label: row for label, row in entries.items() if row["root"] == root}
        changes = sorted(set(before) ^ set(after))
        changes.extend(label for label in before.keys() & after.keys()
                       if before[label]["kind"] != after[label]["kind"]
                       or before[label]["signature"] != after[label]["signature"])
        root_row["changed_paths"] = sorted(set(changes))
        if changes or problems:
            root_row["boundary_status"] = "unknown"
            for row in before.values():
                row["observation_status"] = "unknown"
        errors.extend(problems)
        files = [row for row in before.values() if row["kind"] == "file"]
        root_row.update({"files": len(files), "directories": sum(row["kind"] == "directory" for row in before.values()),
                         "size_bytes": sum(row["size_bytes"] or 0 for row in files),
                         "tracked_files": sum(row["tracked"] is True for row in files),
                         "ignored_files": sum(row["ignored"] is True for row in files)})
    for item in packages.values():
        item["unknown_entries"] = sum(row["observation_status"] == "unknown" for row in entries.values()
                                      if row["package"] == item["path"])
    files = [row for row in entries.values() if row["kind"] == "file"]
    return {"schema": "diagnostic_artifact_inventory_v1", "started_utc": started,
            "finished_utc": datetime.now(timezone.utc).isoformat(), "runtime_status": "unknown",
            "writer_status": "unknown", "approved_delete": False, "snapshot_only": True,
            "reference_coverage": "unknown",
            "summary": {"files": len(files), "size_bytes": sum(row["size_bytes"] or 0 for row in files),
                        "tracked_files": sum(row["tracked"] is True for row in files),
                        "ignored_files": sum(row["ignored"] is True for row in files),
                        "packages": len(packages), "reference_edges": len(edges),
                        "unknown_entries": sum(row["observation_status"] == "unknown" for row in entries.values())},
            "roots": root_rows, "entries": list(entries.values()), "packages": list(packages.values()),
            "reference_edges": edges, "reference_audit": reference_audit, "errors": errors,
            "limits": ["Lexical references are not producer/consumer or value verification.",
                       "Missing/dynamic paths and skipped files may hide dependencies.",
                       "Unchanged stat/hash observations do not prove absence of writers.",
                       "Rewrites preserving observed stat signatures can escape change detection.",
                       "Snapshot is non-atomic; no deletion or retention approval inferred."]}


def write_snapshot(output: Path, report: dict) -> None:
    """Exclusive creation; existing bytes are never overwritten."""
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = Path(os.path.abspath(args.output))
    try:
        if output.exists() or not output.parent.is_dir():
            raise ValueError("output must be fresh and its parent must exist")
        report = inventory(args.repo, excluded={output})
        write_snapshot(output, report)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"inventory: {exc}\n")
    print(json.dumps({"output": str(output), **report["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
