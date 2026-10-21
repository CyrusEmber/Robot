# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Real historical inputs, isolated archive recovery and explicit failure controls.

Run: python rl_exp/tools/verify/test_archived_support_read.py
No production archive/index is written. Git commits below belong ONLY to temporary
repositories. Tests copy evidence bytes, never alter the original invalidated runs.
"""

from __future__ import annotations

import builtins
import contextlib
import copy
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "rl_exp" / "tools" / "diagnose"))
import archived_support_read as reader  # noqa: E402


@contextlib.contextmanager
def deny_old_roots(storage_root):
    """Deny both host-absolute and restore-relative old roots, including Path reads."""
    forbidden = [(base / logical).resolve() for base in (REPO, storage_root)
                 for logical in reader.LOGICAL_ROOTS]

    def guarded(original):
        def opened(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                path = pathlib.Path(os.fsdecode(file)).resolve()
                if any(path == root or path.is_relative_to(root) for root in forbidden):
                    raise FileNotFoundError(f"old root inaccessible: {path}")
            return original(file, *args, **kwargs)
        return opened

    with mock.patch("builtins.open", guarded(builtins.open)), mock.patch("io.open", guarded(io.open)):
        yield


class ArchivedSupportReadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {
            schema: subprocess.check_output(["git", "show", f"{pin[0]}:{reader.PRODUCER_PATH}"], cwd=REPO)
            for schema, pin in reader.PINS.items()
        }
        archive_index = REPO / "rl_exp/tools/diagnose/support_archive_index.json"
        mappings = (json.loads(archive_index.read_text(encoding="utf-8"))["packages"]
                    if archive_index.is_file() else [])
        locations = {entry["old_root"]: REPO / entry["new_relative_root"] for entry in mappings}
        cls.originals = {
            logical: {name: ((REPO / logical if (REPO / logical).is_dir() else locations[logical]) / name).read_bytes()
                      for name in reader.FILES}
            for logical in reader.LOGICAL_ROOTS
        }

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="archived_support_")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name) / "bundle"
        self.root.mkdir()
        self.index = self.root / "rl_exp/out/archived_support/index.json"
        entries = []
        for logical, schema in reader.LOGICAL_ROOTS.items():
            relative = f"rl_exp/out/archived_support/packages/{schema}"
            target = self.root / relative
            target.mkdir(parents=True)
            for name, payload in self.originals[logical].items():
                (target / name).write_bytes(payload)
            source_relative = f"rl_exp/out/archived_support/metadata/{schema}_producer.py"
            source = self.root / source_relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(self.sources[schema])
            entries.append({
                "old_root": logical, "new_relative_root": relative, "schema": schema,
                "files": {name: reader.sha256_file(target / name) for name in sorted(reader.FILES)},
                "producer_source": {
                    "relative_path": source_relative, "commit": reader.PINS[schema][0],
                    "sha256": reader.PINS[schema][1],
                },
            })
        self.data = {"format": 1, "packages": entries}
        self.save()

    def save(self):
        self.index.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def read(self, logical=None):
        self.save()
        with deny_old_roots(self.root):
            return reader.read_archive(self.index, logical or next(iter(reader.LOGICAL_ROOTS)), self.root)

    def test_real_baseline_failure_then_both_schemas_restore(self):
        # Actual pre-feature consumer fails when old root is inaccessible, even on host.
        with deny_old_roots(self.root):
            for logical in reader.LOGICAL_ROOTS:
                for base in (REPO, self.root):
                    with self.assertRaises(FileNotFoundError):
                        (base / logical / "summary.md").read_text(encoding="utf-8")
            missing = copy.deepcopy(self.data)
            self.data["packages"] = []
            with self.assertRaisesRegex(ValueError, "missing mapping"):
                self.read()
            self.data = missing
        for logical in reader.LOGICAL_ROOTS:
            self.assertEqual(self.read(logical), self.originals[logical]["summary.md"].decode("utf-8"))
        self.assertNotIn("isaaclab.app", sys.modules)
        self.assertNotIn("torch", sys.modules)

    def test_unknown_duplicate_schema_and_mapping_refused(self):
        with self.assertRaisesRegex(ValueError, "unknown logical root"):
            self.read("unknown/pack")
        entry = self.data["packages"][0]
        self.data["packages"].append(copy.deepcopy(entry))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.read()
        self.data["packages"].pop()
        entry["schema"] = "smoke_p1d"
        with self.assertRaisesRegex(ValueError, "schema mismatch"):
            self.read()

    def test_bad_digests_and_producer_pin_refused(self):
        entry = self.data["packages"][0]
        old = entry["files"]["summary.md"]
        for bad in ("0" * 64, "invalid"):
            entry["files"]["summary.md"] = bad
            with self.assertRaisesRegex(ValueError, "digest"):
                self.read()
        entry["files"]["summary.md"] = old
        entry["producer_source"]["commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "producer pin"):
            self.read()
        entry["producer_source"]["commit"] = reader.PINS[entry["schema"]][0]
        source = self.root / entry["producer_source"]["relative_path"]
        source.write_bytes(source.read_bytes() + b"\n# changed\n")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.read()

    def test_paths_and_exact_file_set_refused(self):
        entry = self.data["packages"][0]
        good = entry["new_relative_root"]
        for bad in ("../outside", "/absolute", "C:/outside", "a\\..\\outside", entry["old_root"]):
            entry["new_relative_root"] = bad
            with self.assertRaises(ValueError):
                self.read()
        entry["new_relative_root"] = good
        original_source = entry["producer_source"]["relative_path"]
        entry["producer_source"]["relative_path"] = "../source.py"
        with self.assertRaisesRegex(ValueError, "path escape"):
            self.read()
        entry["producer_source"]["relative_path"] = original_source
        root = self.root / good
        extra = root / "unlisted.json"
        extra.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "file set"):
            self.read()
        extra.unlink()
        missing = root / "p1a_zero_action_5s.json"
        payload = missing.read_bytes()
        missing.unlink()
        with self.assertRaisesRegex(ValueError, "file set"):
            self.read()
        missing.write_bytes(payload)
        entry["files"].pop(missing.name)
        with self.assertRaisesRegex(ValueError, "file set"):
            self.read()

    def test_stats_consumed_series_ignored_and_row_order_retained(self):
        entry = self.data["packages"][0]
        root = self.root / entry["new_relative_root"]
        case_file = root / "p1a_zero_action_5s.json"
        record = json.loads(case_file.read_text(encoding="utf-8"))
        record["series_json"] = {"not_executable": "__import__('os').abort()", "nonsense": []}
        case_file.write_text(json.dumps(record), encoding="utf-8")
        entry["files"][case_file.name] = reader.sha256_file(case_file)
        self.assertEqual(self.read(), self.originals[entry["old_root"]]["summary.md"].decode("utf-8"))
        # Real renderer consumes stats: changing a bound stat with a fresh hash must fail.
        record["stats"]["flat"]["drift_m"] += 1
        case_file.write_text(json.dumps(record), encoding="utf-8")
        entry["files"][case_file.name] = reader.sha256_file(case_file)
        with self.assertRaisesRegex(ValueError, "do not reproduce"):
            self.read()
        record["stats"]["flat"]["drift_m"] -= 1
        # Restore original stat without float round-trip error.
        record["stats"] = json.loads(self.originals[entry["old_root"]][case_file.name])["stats"]
        case_file.write_text(json.dumps(record), encoding="utf-8")
        entry["files"][case_file.name] = reader.sha256_file(case_file)
        summary = root / "summary.md"
        lines = summary.read_text(encoding="utf-8").splitlines(keepends=True)
        rows = [i for i, line in enumerate(lines) if line.startswith("| p1")]
        lines[rows[0]], lines[rows[1]] = lines[rows[1]], lines[rows[0]]
        summary.write_bytes("".join(lines).encode("utf-8"))
        entry["files"][summary.name] = reader.sha256_file(summary)
        self.assertEqual(self.read(), summary.read_bytes().decode("utf-8"))

    def test_real_git_commit_checkout_autocrlf_true_false_and_cli(self):
        # Use real repo attribute policy: evidence/source/index share byte-preserving out/**.
        shutil.copyfile(REPO / ".gitattributes", self.root / ".gitattributes")
        env = os.environ.copy()
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            env.pop(key, None)

        def git(root, *args):
            return subprocess.run(["git", "-C", str(root), *args], env=env,
                                  check=True, capture_output=True)

        git(self.root, "init")
        git(self.root, "config", "user.name", "Archive recovery test")
        git(self.root, "config", "user.email", "archive-test@example.invalid")
        paths = [".gitattributes", self.index.relative_to(self.root).as_posix()]
        for entry in self.data["packages"]:
            paths += [f"{entry['new_relative_root']}/{name}" for name in sorted(reader.FILES)]
            paths.append(entry["producer_source"]["relative_path"])
        git(self.root, "add", "--", *paths)
        git(self.root, "commit", "-m", "Isolated archive recovery fixture")
        self.assertEqual(len(git(self.root, "ls-files").stdout.splitlines()), 10)
        index_relative = self.index.relative_to(self.root)
        checkouts = {}
        for setting in ("true", "false"):
            checkout = pathlib.Path(self.temp.name) / f"restore_{setting}"
            subprocess.run(["git", "clone", "--no-local", "--no-checkout", str(self.root), str(checkout)],
                           env=env, check=True, capture_output=True)
            checkouts[setting] = checkout
        # Destroy original temporary bundle, including its git object database.
        def writable_then_remove(function, path, exc):
            os.chmod(path, 0o700)
            function(path)
        shutil.rmtree(self.root, onerror=writable_then_remove)
        self.assertFalse(self.root.exists())
        for setting, checkout in checkouts.items():
            with self.subTest(core_autocrlf=setting):
                git(checkout, "config", "core.autocrlf", setting)
                git(checkout, "checkout", "HEAD")
                restored_index = checkout / index_relative
                for entry in self.data["packages"]:
                    logical = entry["old_root"]
                    self.assertFalse((checkout / logical).exists())
                    with deny_old_roots(checkout):
                        rendered = reader.read_archive(restored_index, logical, checkout)
                    self.assertEqual(rendered.encode("utf-8"), self.originals[logical]["summary.md"])
                    cli = subprocess.run([
                        sys.executable, str(pathlib.Path(reader.__file__)), "--index", str(restored_index),
                        "--package", logical, "--storage_root", str(checkout),
                    ], check=True, capture_output=True)
                    self.assertEqual(cli.stdout.decode("utf-8").replace("\r\n", "\n"), rendered)
                print(f"GIT_RECOVERY_OK core.autocrlf={setting}: 6 evidence + 2 sources + index")


if __name__ == "__main__":
    unittest.main(verbosity=2)
