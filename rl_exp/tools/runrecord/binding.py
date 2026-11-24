# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The binding primitives: how a record names the bytes and the commit it depended on.

Training provenance and evaluation share the revision abbreviation and the bare SHA-256
digest. Formats that store a ``sha256:`` prefix add it when writing their record. Keep these
primitives usable without starting the simulator.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess

REV_LENGTH = 12
"""Characters a recorded revision carries.

Training and evaluation use the same fixed length. Git's automatically selected
abbreviation can grow with the object database.
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


def git_run(root: pathlib.Path | None, *args: str, strip_output: bool = True, check: bool = False) -> str:
    """Run git in ``root``; return stdout, or "" when git cannot answer.

    The decode is pinned rather than left to the host locale. Left to it, a non-ASCII byte in git's
    output (a commit subject, a path) kills the reader thread, ``stdout`` arrives as ``None``, and
    the failure surfaces as an ``AttributeError`` about ``strip`` -- naming neither git nor the
    encoding. Pinning UTF-8 with replacement is how every other tool-output reader in this tree
    decodes, and it keeps this function's contract ("a string, or empty") true on any host.
    ``strip_output=False`` preserves path whitespace and NUL-delimited output; ``check=True``
    propagates errors rather than interpreting them as empty output.
    """
    if root is None:
        return ""
    try:
        output = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, cwd=root,
            encoding="utf-8", errors="replace",
        ).stdout
        return output.strip() if strip_output else output
    except (OSError, subprocess.CalledProcessError):
        if check:
            raise
        return ""


def git_rev(root: pathlib.Path | None, *, short: bool | int = False) -> str:
    """Revision of the work tree at ``root``, or "" when it is not one.

    Args:
        root: the work tree root, or None when it could not be resolved.
        short: ``False`` (the default) is the recorded spelling -- :data:`REV_LENGTH`
            characters. ``True`` asks git for its own abbreviation and an ``int`` for exactly
            that many characters; both are escape hatches, and a *record* must not reach for
            either, because a run should record the same string for a given commit.
    """
    if short is True:
        return git_run(root, "rev-parse", "--short", "HEAD")
    if short is False:
        short = REV_LENGTH
    return git_run(root, "rev-parse", "HEAD")[:short]
