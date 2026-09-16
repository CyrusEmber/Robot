# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Access to the declared observation protocols (``ARCH_PLAN`` Step 3.1a).

One reader for the declaration in ``versions/obs_protocols.json``, so the network's reshape
contract, the smoke specs and the static gates stop carrying their own copy of the group and
foot order. Four hand-kept copies of "the feet are lf, rf, rl, rr" is four chances to fix
three of them.

Stdlib only and no isaaclab import: a caller that must not pay a 2.5 s framework import (or
must keep working while the task tree is mid-edit) can still ask what the layout is.

The declaration is the *identity* of a protocol, not its construction: this module never
builds a config and never derives a layout from one. ``check_obs_protocol`` compares the
declared layout against the constructed cfg, which is what keeps the two from drifting apart.
"""

from __future__ import annotations

import functools
import json
import pathlib

DECLARATION = pathlib.Path(__file__).resolve().parents[2] / "rl_exp" / "versions" / "obs_protocols.json"
_FOOT_SUFFIX = "_foot_ring"


class ProtocolError(ValueError):
    """The declaration cannot answer the question -- never a silent default."""


@functools.lru_cache(maxsize=1)
def declaration() -> dict:
    """The parsed declaration.

    Raises:
        ProtocolError: the file is missing or unreadable. An absent declaration is not an
            empty one: every caller here answers a question about identity, and answering it
            with nothing would let a wrong layout pass.
    """
    try:
        return json.loads(DECLARATION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ProtocolError(f"cannot read {DECLARATION}: {err}") from err


def protocol_for(task_id: str) -> str:
    """The protocol identity a task declares.

    Raises:
        ProtocolError: the task is not declared. Identity is read, never guessed from the task
            id or the entry point path.
    """
    route = (declaration().get("tasks") or {}).get(task_id)
    if not isinstance(route, dict) or "protocol" not in route:
        raise ProtocolError(f"{task_id}: no protocol declared for this task")
    return route["protocol"]


def groups_for(task_id: str) -> dict:
    """The declared layout of a task's protocol: group name -> terms, order included.

    Raises:
        ProtocolError: the task is undeclared, or names a protocol the declaration omits.
    """
    key = protocol_for(task_id)
    entry = (declaration().get("protocols") or {}).get(key)
    if not isinstance(entry, dict) or not isinstance(entry.get("groups"), dict):
        raise ProtocolError(f"{task_id}: protocol {key} has no groups in the declaration")
    return entry["groups"]


def terms_for(task_id: str, group: str) -> list[str]:
    """The declared term order of one group.

    Raises:
        ProtocolError: the task declares no such group, or the group is dropped there (a
            dropped group has no terms to hand out).
    """
    groups = groups_for(task_id)
    if group not in groups:
        raise ProtocolError(f"{task_id}: protocol declares no group {group!r}; has {sorted(groups)}")
    entry = groups[group]
    if entry.get("dropped"):
        raise ProtocolError(f"{task_id}: group {group!r} is dropped for this task")
    return list(entry.get("terms") or [])


def feet_for(task_id: str, group: str = "extero") -> tuple[str, ...]:
    """The foot order a task's ring group encodes, derived from its term names.

    Derived rather than declared twice: the extero group's terms *are* the feet in order, so a
    second list would be a second place to keep in step. Every term must carry the ring suffix,
    and the group must hold one term per foot.

    Raises:
        ProtocolError: a term does not match the ring naming, so the order cannot be read.
    """
    terms = terms_for(task_id, group)
    feet: list[str] = []
    for term in terms:
        if not term.endswith(_FOOT_SUFFIX):
            raise ProtocolError(f"{task_id}: group {group!r} term {term!r} is not a ring term; foot order cannot be read")
        feet.append(term[: -len(_FOOT_SUFFIX)])
    if len(set(feet)) != len(feet):
        raise ProtocolError(f"{task_id}: group {group!r} repeats a foot: {feet}")
    return tuple(feet)
