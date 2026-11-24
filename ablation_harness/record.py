# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Stdlib-only digest and metadata helpers shared by evaluation and diagnostic probes.

No torch/numpy/sim/RNG imports: callers can hash files or objects offline without touching
any random stream. The retired ``record.json`` state machine lives in ``archive/pre-refactor``.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.runrecord import binding  # noqa: E402

#: Sentinel written for provenance fields that could not be established.
UNKNOWN = "unknown"


def canonical(obj) -> str:
    """One deterministic JSON rendering, so equal content hashes equal."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(obj) -> str:
    """``sha256:`` digest of one object's canonical rendering."""
    return "sha256:" + hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def file_sha256(path: pathlib.Path | str, chunk: int = 1 << 20) -> str | None:
    """``sha256:`` digest of a file, or ``None`` when it cannot be read."""
    value = binding.sha256_file(path, chunk)
    return None if value is None else "sha256:" + value


def checkpoint_digest(path: pathlib.Path | str) -> dict:
    """Identify a checkpoint file: digest, byte size and mtime."""
    resolved = os.path.realpath(path)
    try:
        stat = os.stat(resolved)
        size, mtime = stat.st_size, round(float(stat.st_mtime), 6)
    except OSError:
        size, mtime = None, None
    return {
        "path": str(path),
        "resolved": resolved,
        "sha256": file_sha256(resolved),
        "size": size,
        "mtime": mtime,
    }
