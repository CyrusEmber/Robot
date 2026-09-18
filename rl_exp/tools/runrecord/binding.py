# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The binding primitives: how a record names the bytes and the commit it depended on.

PLAN.md #27 ①. The run manifest (``rl_exp/tools/runrecord/manifest.py``) and the eval
record (``ablation_harness/record.py``) describe one run in two files, and they used to spell
the shared half twice:

* **a content digest** -- ``provenance.sha256_file`` streamed the file to bare hex, while
  ``record.file_sha256`` streamed it again to ``sha256:`` + hex. The digest is the primitive
  and lives here; the ``sha256:`` prefix belongs to the eval record's own format and stays at
  the point where that record is written, so no emitted value moved.
* **a commit id** -- ``provenance.rev`` truncated ``rev-parse HEAD`` to 12 characters while
  ``eval._git_rev`` asked git for ``--short`` (about 7), so one commit read as two different
  strings in the two records of one run and nothing could reconcile them. There is one
  spelling now (:data:`REV_LENGTH`), and ``check_record_bindings.py`` keeps a second one from
  being written.

Stdlib only, deliberately: ``record.py``'s offline test asserts the eval record cannot import
torch/numpy/random, and a record must be writable on a machine that cannot start the
simulator. It imports nothing from this repo either -- it is the bottom of the stack, so
``provenance`` may import it and so may the harness.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess

REV_LENGTH = 12
"""Characters a recorded revision carries.

One number, one spelling: the manifest has always recorded this many, and the eval record now
records the same string for the same commit (PLAN.md #27 ①). It is *not* ``git --short`` -- that
length belongs to git and moves as the object database grows.
"""


def sha256_bytes(payload: bytes) -> str:
    """Hex digest of ``payload`` -- bare hex, the convention both records bind by."""
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: pathlib.Path | None, chunk: int = 1 << 20) -> str | None:
    """Content hash of a file, or None when it cannot be read.

    Chunked rather than ``read_bytes()`` because checkpoints are hashed by this function and
    they are not small.
    """
    if path is None:
        return None
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(chunk), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def git_run(root: pathlib.Path | None, *args: str) -> str:
    """Run git in ``root``; return stdout, or "" when git cannot answer."""
    if root is None:
        return ""
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, cwd=root
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def git_rev(root: pathlib.Path | None, *, short: bool | int = False) -> str:
    """Revision of the work tree at ``root``, or "" when it is not one.

    Args:
        root: the work tree root, or None when it could not be resolved.
        short: ``False`` (the default) is the recorded spelling -- :data:`REV_LENGTH`
            characters. ``True`` asks git for its own abbreviation and an ``int`` for exactly
            that many characters; both are escape hatches, and a *record* must not reach for
            either, because the point of #27 ② is that one commit has one string per run.
    """
    if short is True:
        return git_run(root, "rev-parse", "--short", "HEAD")
    if short is False:
        short = REV_LENGTH
    return git_run(root, "rev-parse", "HEAD")[:short]
