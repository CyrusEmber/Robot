# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""The one column-split rule, and the record of what a generator actually did (Step 3.3b).

``TerrainGenerator._generate_curriculum_terrains`` splits columns over sub-terrain
proportions with a cumulative sum and a boundary epsilon, and the real ``sub_indices`` it
computes are local to that function and dropped when it returns. Two curricula therefore
replicated the rule verbatim (``teacher_mdp.py``), and the only evidence that the copies
still matched the generator was a hardcoded expectation against a mock -- never the real
generator. One rule lives here; the record of a real generation (``tools/verify/
terrain_split_probe.py``, Step 3.3c) is what the curricula consume.

Stdlib only, no torch and no isaaclab: the rule is arithmetic over proportions, and the
curricula that need it must not pay a framework import to learn what a column is.

**Modes are not the same thing** (Step 3.3, "模式区分"): ``curriculum`` assigns a column to a
sub-terrain, ``random`` samples a sub-terrain *per cell* and has no column mapping to
declare. :func:`check` refuses a random-mode record that claims columns, a curriculum record
whose captured cells disagree with the declared split, and a mapping that is not this rule's
output -- the last one so that a reimplementation cannot be consumed even when it is
perfectly self-consistent.
"""

from __future__ import annotations

import hashlib
import json

#: The boundary epsilon ``terrain_generator.py`` adds to the column fraction, so that a
#: column sitting exactly on a cumulative boundary lands in the lower sub-terrain. Not a
#: knob: it reproduces that line, and it is spelled once, here.
SPLIT_EPSILON = 0.001

MODE_CURRICULUM = "curriculum"
MODE_RANDOM = "random"


class SplitRecordError(RuntimeError):
    """The record cannot answer the question -- never a silent default."""


def digest(obj) -> str:
    """``sha256:`` digest of one JSON-able object, for pinning a sub-terrain's parameters."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def column_split(proportions, num_cols: int) -> tuple[int, ...]:
    """Column -> sub-terrain index, as the generator's curriculum split assigns them.

    Args:
        proportions: per sub-terrain proportion, in cfg order (need not sum to one).
        num_cols: number of terrain columns.

    Returns:
        One sub-terrain index per column. Every index is in range: the largest column
        fraction is ``(num_cols - 1) / num_cols + epsilon``, which stays below the last
        cumulative boundary of a normalized distribution.
    """
    if num_cols <= 0:
        raise SplitRecordError(f"num_cols must be positive, got {num_cols}")
    total = float(sum(proportions))
    if total <= 0.0:
        raise SplitRecordError("proportions sum to zero: no sub-terrain owns a column")
    cumulative: list[float] = []
    acc = 0.0
    for value in proportions:
        acc += float(value) / total
        cumulative.append(acc)
    columns: list[int] = []
    for col in range(num_cols):
        fraction = col / num_cols + SPLIT_EPSILON
        index = next((i for i, bound in enumerate(cumulative) if fraction < bound), None)
        if index is None:
            raise SplitRecordError(f"column {col} falls past every cumulative boundary of {cumulative}")
        columns.append(index)
    return tuple(columns)


def new_record(cfg, cfg_id: int) -> dict:
    """An empty record for ``cfg``: the declared side, before any generation is observed."""
    names = list(cfg.sub_terrains.keys())
    proportions = [float(sub.proportion) for sub in cfg.sub_terrains.values()]
    mode = MODE_CURRICULUM if cfg.curriculum else MODE_RANDOM
    return {
        "cfg_id": cfg_id,
        "mode": mode,
        "num_rows": int(cfg.num_rows),
        "num_cols": int(cfg.num_cols),
        "sub_terrains": names,
        "proportions": proportions,
        # only curriculum mode declares a mapping; the random one samples per cell
        "columns": list(column_split(proportions, int(cfg.num_cols))) if mode == MODE_CURRICULUM else None,
        # list, not dict: a duplicated (row, col) has to stay visible as a duplicate
        "cells": [],
        # whatever the probe could not pair up, kept verbatim rather than dropped
        "anomalies": [],
    }


def column_of(record: dict, requested_col: int) -> int:
    """Declared sub-terrain index for one column (curriculum mode only)."""
    columns = record.get("columns")
    if not columns:
        raise SplitRecordError(
            f"record is mode {record.get('mode')!r}: no column mapping is declared for it"
        )
    if not 0 <= requested_col < len(columns):
        raise SplitRecordError(f"column {requested_col} is out of range for {len(columns)} columns")
    return int(columns[requested_col])


def pair(pending: list[tuple[int, float, str]], cfg_id: int) -> tuple[int | None, str]:
    """Which pending ``_get_terrain_mesh`` a cell consumes, or why none does.

    The pairing is by **cfg identity**, not by position in the loop: the generator either
    passes one of its own sub-terrain cfgs (the same object it handed to the mesh builder) or
    the call is not a terrain cell at all. Anything else is refused rather than matched to the
    nearest pending entry -- a mismatched pairing would silently attach one cell's difficulty
    to another cell's parameters.

    Args:
        pending: unpaired ``(cfg id, difficulty, parameter digest)`` entries, oldest first.
        cfg_id: identity of the sub-terrain cfg passed to ``_add_sub_terrain``.

    Returns:
        ``(index into pending, "")``, or ``(None, reason)`` when the add cannot be paired.
    """
    if not pending:
        return None, "no preceding _get_terrain_mesh"
    index = next((i for i, item in enumerate(pending) if item[0] == cfg_id), None)
    if index is None:
        return None, "no pending _get_terrain_mesh for this sub-terrain cfg (cfg identity does not match)"
    return index, ""


def check(record: dict) -> list[str]:
    """Every problem this record carries; empty means it can be consumed.

    Sanity refusals (Step 3.3c): an unknown sub-terrain, a pairing failure recorded as an
    anomaly, a missing cell, a duplicate cell, a row/column out of range, a random-mode
    record claiming a column mapping, a declared mapping that :func:`column_split` does not
    reproduce, and a captured cell that disagrees with the declared split. Returning a list
    (not raising) keeps a record with several problems readable.
    """
    problems: list[str] = [f"anomaly: {item}" for item in record.get("anomalies", [])]
    mode = record.get("mode")
    if mode not in (MODE_CURRICULUM, MODE_RANDOM):
        problems.append(f"unknown generation mode {mode!r}")
    names = record.get("sub_terrains") or []
    num_rows, num_cols = int(record.get("num_rows", 0)), int(record.get("num_cols", 0))
    if mode == MODE_RANDOM and record.get("columns"):
        problems.append("random mode samples per cell: it must not declare a column mapping")
    if mode == MODE_CURRICULUM and not record.get("columns"):
        problems.append("curriculum mode must declare its column mapping")
    # The mapping is not merely required to be self-consistent (the cell loop below tests that):
    # it has to be *this rule's* output. A record whose columns came from another rule -- a
    # reimplementation with a different tolerance, or the pre-3.3b copy without the boundary
    # epsilon -- agrees with its own cells and would otherwise be consumed as if it were sound.
    # Reproducing it here is what makes "one rule" a property of the record rather than a promise
    # about the code that wrote it, and a static scan for copies cannot see a new rule at all.
    if mode == MODE_CURRICULUM and record.get("columns") and num_cols > 0:
        try:
            by_rule = [int(index) for index in column_split(record.get("proportions") or [], num_cols)]
        except SplitRecordError as err:
            problems.append(f"the declared split cannot be reproduced by the one rule: {err}")
        else:
            declared = [int(index) for index in record["columns"]]
            if by_rule != declared:
                problems.append(
                    f"the declared split does not come from the one split rule "
                    f"(rule says {by_rule}, record says {declared})"
                )

    seen: set[tuple[int, int]] = set()
    for cell in record.get("cells", []):
        row, col, name = int(cell.get("row", -1)), int(cell.get("col", -1)), cell.get("sub_terrain")
        where = f"cell ({row}, {col})"
        if name not in names:
            problems.append(f"{where}: unknown sub-terrain {name!r}")
        if not (0 <= row < num_rows) or not (0 <= col < num_cols):
            problems.append(f"{where}: out of the {num_rows}x{num_cols} grid")
        if (row, col) in seen:
            problems.append(f"{where}: duplicate")
        seen.add((row, col))
        # the declared split is only comparable when there is one (its absence is already a
        # problem above; raising here would lose the other findings)
        if mode == MODE_CURRICULUM and name in names and 0 <= col < num_cols and record.get("columns"):
            declared = column_of(record, col)
            if names.index(name) != declared:
                problems.append(
                    f"{where}: column {col} generated {name!r} but the declared split says "
                    f"{names[declared]!r}"
                )
    if num_rows > 0 and num_cols > 0 and len(seen) != num_rows * num_cols:
        problems.append(f"grid is not complete: {len(seen)} of {num_rows * num_cols} cells captured")
    return problems
