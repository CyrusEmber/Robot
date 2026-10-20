# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Real Git regression for diagnostic output ignore and byte boundaries.

Run directly with stdlib unittest. Optional --baseline reads HEAD's root rules
instead of current working-tree rules, solely to reproduce the pre-fix failure.
Only TemporaryDirectory-owned repositories are written; no main-tree Git writes.
Small CRLF fixtures cover both output roots and proposed runs/archive layouts.
This does not validate consumer paths, artifact migration or full recovery.
Git hooks/signing remain enabled; commit failures are errors, never bypassed.
"""

import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
BASELINE = False
PAYLOADS = {
    "build.json": b'{\r\n  "fixture": "diagnostic-boundary"\r\n}\r\n',
    "robot.urdf": b'<robot name="fixture">\r\n  <link name="body"/>\r\n</robot>\r\n',
    "mesh.obj": b'v 0 0 0\r\nv 1 0 0\r\nv 0 1 0\r\nf 1 2 3\r\n',
}
OUTPUT_ROOTS = ("rl_exp/out", "rl_exp/tools/diagnose/out")
SAMPLES = {
    f"{root}/{layout}{name}": data
    for root in OUTPUT_ROOTS
    for layout in ("", "runs/boundary-fixture/", "archive/boundary-fixture/")
    for name, data in PAYLOADS.items()
}


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run real Git, preserving binary stdout and reporting failures verbatim."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=60,
    )
    if check and result.returncode:
        raise RuntimeError(
            f"git {' '.join(args)}: exit {result.returncode}\n"
            f"{result.stdout.decode('utf-8', errors='replace')}"
            f"{result.stderr.decode('utf-8', errors='replace')}"
        )
    return result


def put(repo: Path, name: str, data: bytes) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def rules() -> dict[str, bytes]:
    return {
        name: git(ROOT, "show", f"HEAD:{name}").stdout if BASELINE
        else (ROOT / name).read_bytes()
        for name in (".gitattributes", ".gitignore")
    }


class DiagnosticGitBoundaryTest(unittest.TestCase):
    def new_repo(self, parent: Path, autocrlf: str) -> Path:
        repo = parent / "source"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.name", "Diagnostic boundary regression")
        git(repo, "config", "user.email", "diagnostic-boundary@example.invalid")
        git(repo, "config", "core.autocrlf", autocrlf)
        # Global settings already inherit normally; preserve main's local signing
        # settings too. Never switch off signing or override hooksPath.
        for key in ("commit.gpgsign", "user.signingkey", "gpg.format", "gpg.program",
                    "gpg.ssh.program", "gpg.ssh.defaultKeyCommand"):
            value = git(ROOT, "config", "--get", key, check=False)
            if value.returncode == 0:
                git(repo, "config", key, value.stdout.decode().strip())
            elif value.returncode != 1:
                raise RuntimeError(f"Cannot read signing config {key}: {value.stderr!r}")
        return repo

    def install_rules(self, repo: Path) -> None:
        for name, data in rules().items():
            put(repo, name, data)
        git(repo, "add", "--", ".gitattributes", ".gitignore")
        git(repo, "commit", "-q", "-m", "Install actual root diagnostic rules")

    def assert_bytes(self, label: str, raw: bytes, blob: bytes, checkout: bytes) -> None:
        hashes = [hashlib.sha256(data).hexdigest() for data in (raw, blob, checkout)]
        print(f"{label}: raw={hashes[0]} blob={hashes[1]} checkout={hashes[2]}", flush=True)
        self.assertEqual(blob, raw, f"{label}: Git add changed original CRLF bytes")
        self.assertEqual(checkout, raw, f"{label}: fresh checkout changed original bytes")
        self.assertEqual(hashes, [hashes[0]] * 3, f"{label}: SHA256 differs")

    def test_crlf_add_commit_delete_recheckout_bytes(self):
        for autocrlf in ("true", "false"):
            with tempfile.TemporaryDirectory(prefix="diagnostic-git-bytes-") as temp:
                repo = self.new_repo(Path(temp), autocrlf)
                self.install_rules(repo)
                for name, data in SAMPLES.items():
                    put(repo, name, data)
                # Forced add only seeds explicit tracked fixtures in this temp repo.
                git(repo, "add", "-f", "--", *SAMPLES)
                git(repo, "commit", "-q", "-m", "Seed temporary CRLF evidence baseline")
                blobs = {name: git(repo, "show", f"HEAD:{name}").stdout for name in SAMPLES}
                for name in SAMPLES:
                    (repo / name).unlink()
                    self.assertFalse((repo / name).exists())
                git(repo, "checkout-index", "-f", "--", *SAMPLES)
                for name, raw in SAMPLES.items():
                    with self.subTest(autocrlf=autocrlf, path=name):
                        self.assert_bytes(f"autocrlf={autocrlf} {name}", raw, blobs[name],
                                          (repo / name).read_bytes())
                self.assertEqual(git(repo, "status", "--porcelain").stdout, b"")

    def test_new_output_default_add_is_ignored_and_status_clean(self):
        for autocrlf in ("true", "false"):
            with tempfile.TemporaryDirectory(prefix="diagnostic-git-ignore-") as temp:
                repo = self.new_repo(Path(temp), autocrlf)
                self.install_rules(repo)
                for name, data in SAMPLES.items():
                    put(repo, name, data)
                    with self.subTest(autocrlf=autocrlf, path=name):
                        ignored = git(repo, "check-ignore", "--", name, check=False)
                        added = git(repo, "add", "--", name, check=False)
                        status = git(repo, "status", "--porcelain", "--untracked-files=all",
                                     "--", name).stdout
                        tracked = git(repo, "ls-files", "--", name).stdout
                        print(f"autocrlf={autocrlf} {name}: check-ignore={ignored.returncode} "
                              f"add={added.returncode} status={status!r} tracked={tracked!r}", flush=True)
                        self.assertEqual(ignored.returncode, 0, f"{name}: not ignored")
                        self.assertNotEqual(added.returncode, 0, f"{name}: default add accepted output")
                        self.assertIn(b"ignored", added.stderr.lower(), f"{name}: wrong add failure")
                        self.assertEqual(status, b"", f"{name}: leaked into default status")
                        self.assertEqual(tracked, b"", f"{name}: newly tracked")

    def test_existing_tracked_survives_ignore_commit_and_clone(self):
        for autocrlf in ("true", "false"):
            with tempfile.TemporaryDirectory(prefix="diagnostic-git-tracked-") as temp:
                parent = Path(temp)
                # Before root rules exist, preserve original fixture bytes for the
                # historical commit. Target autocrlf applies after that commit.
                repo = self.new_repo(parent, "false")
                for name, data in SAMPLES.items():
                    put(repo, name, data)
                git(repo, "add", "-f", "--", *SAMPLES)
                git(repo, "commit", "-q", "-m", "Track evidence before installing ignore")
                before = git(repo, "rev-parse", "HEAD").stdout.strip()
                git(repo, "config", "core.autocrlf", autocrlf)
                self.install_rules(repo)
                self.assertNotEqual(git(repo, "rev-parse", "HEAD").stdout.strip(), before)
                self.assertEqual(int(git(repo, "rev-list", "--count", "HEAD").stdout), 2)
                clone = parent / "clone"
                git(parent, "clone", "-q", "--no-checkout", str(repo), str(clone))
                git(clone, "config", "core.autocrlf", autocrlf)
                git(clone, "checkout", "-q", "--detach", "HEAD")
                for name, raw in SAMPLES.items():
                    with self.subTest(autocrlf=autocrlf, path=name):
                        expected = name.encode() + b"\n"
                        self.assertEqual(git(repo, "ls-files", "--", name).stdout, expected)
                        self.assertEqual(git(clone, "ls-files", "--", name).stdout, expected)
                        # Tracked paths are excluded from normal check-ignore.
                        self.assertEqual(git(clone, "check-ignore", "--", name,
                                             check=False).returncode, 1)
                        self.assert_bytes(f"clone autocrlf={autocrlf} {name}", raw,
                                          git(clone, "show", f"HEAD:{name}").stdout,
                                          (clone / name).read_bytes())
                self.assertEqual(git(clone, "status", "--porcelain").stdout, b"")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true",
                        help="Reproduce failure using HEAD root rules; does not revert main files")
    args, remaining = parser.parse_known_args()
    BASELINE = args.baseline
    print(f"rules={'HEAD baseline' if BASELINE else 'current working tree'} "
          f"HEAD={git(ROOT, 'rev-parse', 'HEAD').stdout.decode().strip()}", flush=True)
    for name, data in rules().items():
        print(f"rule={name} sha256={hashlib.sha256(data).hexdigest()}", flush=True)
    unittest.main(argv=[__file__, *remaining], verbosity=2)
