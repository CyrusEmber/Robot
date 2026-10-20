# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Tempfile checks for inventory references, cycles, Git, races and safe output."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

_TOOL = Path(__file__).resolve().parents[1] / "diagnose/artifact_inventory.py"
_SPEC = importlib.util.spec_from_file_location("artifact_inventory", _TOOL)
inv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(inv)


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.put(".gitignore", "rl_exp/out/pkg/ignored.bin\n")
        self.put("rl_exp/out/pkg/a.json", json.dumps({"nested": [{"input": "b.json"}]}))
        self.put("rl_exp/out/pkg/b.json", json.dumps({"back": "a.json", "input": "../other/raw.bin"}))
        self.put("rl_exp/out/other/raw.bin", "raw")
        self.put("rl_exp/out/pkg/ignored.bin", "ignored")
        self.put("rl_exp/out/loose.txt", "loose")
        self.put("rl_exp/tools/diagnose/out/second/report.json", json.dumps({"input": "rl_exp/out/pkg/a.json"}))
        self.put("work/active/example.md", "Consumes `rl_exp/tools/diagnose/out/second/report.json`\n")
        self.put("consumer.py", "INPUT = 'rl_exp/out/pkg/a.json'\n")
        self.put("acceptance/records/sample.md", "Evidence `rl_exp/out/pkg`\n")
        self.git("add", ".gitignore", "rl_exp/out/pkg/a.json")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def put(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_nested_cycle_git_packages_and_exclusive(self):
        report = inv.inventory(self.repo)
        entries = {row["path"]: row for row in report["entries"]}
        self.assertTrue(entries["rl_exp/out/pkg/a.json"]["tracked"])
        self.assertFalse(entries["rl_exp/out/pkg/b.json"]["tracked"])
        self.assertTrue(entries["rl_exp/out/pkg/ignored.bin"]["ignored"])
        self.assertFalse(entries["rl_exp/out/pkg/b.json"]["ignored"])
        self.assertEqual(entries["rl_exp/out/other/raw.bin"]["sha256"], inv.sha256_file(self.repo / "rl_exp/out/other/raw.bin"))
        packages = {row["path"]: row for row in report["packages"]}
        self.assertEqual(packages["rl_exp/out/pkg"]["files"], 3)
        self.assertEqual(packages["rl_exp/out/loose.txt"]["files"], 1)
        self.assertIn("rl_exp/out/other/raw.bin", packages["rl_exp/tools/diagnose/out/second"]["transitive_inputs"])
        self.assertIn("work/active/example.md", packages["rl_exp/out/other"]["transitive_consumers"])
        edges = report["reference_edges"]
        self.assertTrue(any(edge["source"].endswith("a.json") and edge["target"].endswith("b.json")
                            and edge["location"] == "/nested/0/input" for edge in edges))
        self.assertTrue(any(edge["source_category"] == "acceptance" for edge in edges))
        self.assertLess(len(edges), 30)
        for row in [*report["entries"], *report["packages"]]:
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["writer_status"], "unknown")
            self.assertFalse(row["approved_delete"])
        output = self.repo / "snapshot.json"
        inv.write_snapshot(output, report)
        old = output.read_bytes()
        with self.assertRaises(FileExistsError):
            inv.write_snapshot(output, {"replacement": True})
        self.assertEqual(output.read_bytes(), old)

    def test_external_json_dependency_and_cycle(self):
        with tempfile.TemporaryDirectory() as external:
            external = Path(external)
            first, second = external / "first.json", external / "second.json"
            first.write_text(json.dumps({"next": str(second)}), encoding="utf-8")
            second.write_text(json.dumps({"cycle": str(first), "raw": str(self.repo / "rl_exp/out/other/raw.bin")}),
                              encoding="utf-8")
            self.put("rl_exp/out/pkg/external.json", json.dumps({"input": str(first)}))
            report = inv.inventory(self.repo)
            package = next(row for row in report["packages"] if row["path"] == "rl_exp/out/pkg")
            self.assertIn(second.as_posix(), package["transitive_inputs"])
            self.assertIn("rl_exp/out/other/raw.bin", package["transitive_inputs"])

    def test_hash_map_path_keys_are_dependencies(self):
        dependency = self.put("rl_exp/out/other/hash~input.bin", "hash input")
        paths = [str(dependency), "rl_exp/out/other/raw.bin"]
        source = "rl_exp/out/pkg/hashes.json"
        self.put(source, json.dumps({"hashes": {path: "a" * 64 for path in paths}}))
        report = inv.inventory(self.repo)
        package = next(row for row in report["packages"] if row["path"] == "rl_exp/out/pkg")
        for path in paths:
            target = dependency.relative_to(self.repo).as_posix() if path == str(dependency) else path
            self.assertIn(target, package["transitive_inputs"])
            pointer = "/hashes/" + path.replace("~", "~0").replace("/", "~1") + "/@key"
            self.assertTrue(any(edge["source"] == source and edge["target"] == target
                                and edge["location"] == pointer and edge["kind"] == "json_input"
                                for edge in report["reference_edges"]))

    def test_missing_json_paths_are_audited_not_graphed(self):
        missing = str(self.repo / "absent" / "input.bin")
        source = "rl_exp/out/pkg/missing.json"
        self.put(source, json.dumps({"absolute": missing, "relative": "absent/input.bin",
                                     "basename": "absent.bin", "hashes": {"absent/key.bin": "a" * 64},
                                     "uri": "https://example.invalid/input.bin", "digest": "b" * 64,
                                     "word": "notpath", "units": "rad/s",
                                     "note": "Input dependency is unavailable."}))
        self.put("missing.md", "Missing `absent/document.bin` is only a lexical mention.\n")
        report = inv.inventory(self.repo)
        rows = report["reference_audit"]["unresolved"]
        self.assertEqual({(row["source"], row["location"], row["value"]) for row in rows},
                         {(source, "/absolute", missing), (source, "/relative", "absent/input.bin"),
                          (source, "/basename", "absent.bin"),
                          (source, "/hashes/absent~1key.bin/@key", "absent/key.bin")})
        self.assertEqual(report["reference_audit"]["unresolved_truncated"], 0)
        self.assertEqual(report["reference_coverage"], "unknown")
        self.assertFalse(any(edge["source"] == source for edge in report["reference_edges"]))
        package = next(row for row in report["packages"] if row["path"] == "rl_exp/out/pkg")
        self.assertNotIn(Path(missing).as_posix(), package["transitive_inputs"])
        self.assertFalse(any("absent" in path for path in package["transitive_inputs"]))

    def test_unresolved_audit_budget(self):
        self.put("rl_exp/out/pkg/missing.json", json.dumps({"inputs": ["absent/a.bin", "absent/b.bin",
                                                                                    "absent/c.bin"]}))
        with patch.object(inv, "MAX_UNRESOLVED_REFERENCES", 1):
            report = inv.inventory(self.repo)
        audit = report["reference_audit"]
        self.assertEqual(audit["max_unresolved_references"], 1)
        self.assertEqual(len(audit["unresolved"]), 1)
        self.assertEqual(audit["unresolved_truncated"], 2)
        self.assertEqual(report["reference_coverage"], "unknown")

    def test_hash_failure_and_boundary_change_unknown(self):
        original_digest = inv.sha256_file

        def failing_digest(path):
            return None if path.name == "raw.bin" else original_digest(path)

        original_scan = inv.discover_references

        def changed_scan(*args, **kwargs):
            result = original_scan(*args, **kwargs)
            self.put("rl_exp/out/added.txt", "new boundary")
            return result

        with patch.object(inv, "sha256_file", failing_digest), patch.object(inv, "discover_references", changed_scan):
            report = inv.inventory(self.repo)
        raw = next(row for row in report["entries"] if row["path"].endswith("raw.bin"))
        self.assertIsNone(raw["sha256"])
        self.assertEqual(raw["observation_status"], "unknown")
        root = next(row for row in report["roots"] if row["path"] == "rl_exp/out")
        self.assertEqual(root["boundary_status"], "unknown")
        self.assertIn("rl_exp/out/added.txt", root["changed_paths"])

    def test_cli_existing_output_preserves_bytes(self):
        output = self.put("existing.json", "old bytes")
        result = subprocess.run([__import__("sys").executable, str(_TOOL), "--repo", str(self.repo),
                                 "--output", str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_bytes(), b"old bytes")


if __name__ == "__main__":
    unittest.main()
