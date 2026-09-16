# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""One params-document loader for every recipe line (``ARCH_PLAN.md`` 2.4, B1's last slice).

Four env-cfg modules each carried their own near-identical loader, and the copies had already
drifted: three cached the parsed document, the fourth re-parsed the file on every call, and only
two refused the dev yaml for a frozen recipe.

The cache is the subtle half. One cfg construction runs a chain of ``__post_init__`` that each
re-read the same yaml, so the parse -- not the cfg wiring -- is what makes building a config cost
something. What is frozen is the *file*, never the Python object built from it: handing out the
cached document makes every cfg in the process share one mutable tree, and one
``params[...] = ...`` would then leak across versions and tasks (``test_params_isolation.py``
fails if a load stops being isolated).

What stays per line is only what is genuinely per line: which key it is, and whether its dev yaml
is readable at all.
"""

from __future__ import annotations

import copy
import functools
import pathlib

import yaml

_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]


@functools.lru_cache(maxsize=64)
def document(path: str, stamp: tuple[int, int]) -> dict:
    """Parse a params yaml, cached on ``stamp`` = (mtime_ns, size).

    Args:
        path: the params file to read.
        stamp: the file's (mtime_ns, size) at call time. The stamp, not a line or version name,
            is the cache key: a dev yaml is a live tuning file, so a name-keyed cache would keep
            serving the content from before the edit.

    Returns:
        The parsed document. Shared with the cache -- call :func:`load` unless you want that.

    ponytail: ceiling -- a rewrite that keeps both mtime_ns and size is served from the cache;
    64 entries covers every version one build touches.
    """
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def path(line_key: str, version: str | None) -> pathlib.Path:
    """The params file of one recipe line: this version's frozen copy, or the line's dev yaml.

    Args:
        line_key: family-relative handle of the recipe line (``"lizard/main"``).
        version: a frozen version handle (``"v14"``), or None for the dev yaml.

    Returns:
        The file to read. The basename mirrors the directory name
        (``versions/lizard/main/main_params.yaml``) -- the convention ``recipe_lines`` discovers by.
    """
    line_dir = _RL_EXP_DIR / "versions" / line_key
    dev = line_dir / f"{line_dir.name}_params.yaml"
    return dev if version is None else line_dir / version / dev.name


def load(line_key: str, version: str | None, *, frozen_only: bool = False) -> dict:
    """This line's parameters, as a document the caller owns.

    Args:
        line_key: family-relative handle of the recipe line (``"lizard/main"``).
        version: a frozen version handle (``"v14"``), or None for the line's dev yaml.
        frozen_only: refuse the dev yaml. Some lines are frozen snapshots: a version-stamped
            task reading a mutable file is pinned to content its golden says nothing about.

    Returns:
        The parsed document, deep-copied so the caller can edit its own tree.

    Raises:
        ValueError: ``frozen_only`` was asked for and no version was given.
    """
    if frozen_only and version is None:
        raise ValueError(
            f"line {line_key!r} is frozen: a params load needs its version, never the dev yaml"
        )
    file = path(line_key, version)
    stat = file.stat()
    # deepcopy on every call, the first one included: the cache holds the parsed document, the
    # caller gets its own tree. What is frozen is the file, not the object built from it, and a
    # shared tree would let one cfg's edit reach another's (~1 ms here vs ~50 ms to re-parse).
    return copy.deepcopy(document(str(file), (stat.st_mtime_ns, stat.st_size)))
