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
import hashlib
import json
import pathlib

DECLARATION = pathlib.Path(__file__).resolve().parents[2] / "rl_exp" / "versions" / "obs_protocols.json"
ANCHORS = pathlib.Path(__file__).resolve().parents[2] / "rl_exp" / "versions" / "obs_protocol_anchors.json"
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


RUNTIME_ORDERS = (
    pathlib.Path(__file__).resolve().parents[2] / "rl_exp" / "versions" / "lizard" / "joint_order_runtime.json"
)


def _params_document(task_id: str) -> tuple[dict, pathlib.Path] | None:
    """The recipe's parameters document and its path, or ``None`` when it cannot be found.

    Addressed by the declaration's own route (line + version), not by guessing the file's name
    from the task id: a rename must not silently resolve to no document.
    """
    route = task_route(task_id)
    line = route.get("line")
    if not isinstance(line, str) or not line:
        return None
    line_dir = DECLARATION.parent / line
    basename = f"{line_dir.name}_params.yaml"
    version = route.get("version")
    candidates = [line_dir / basename] if version is None else [line_dir / version / basename, line_dir / basename]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return None
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")), path
    except Exception:  # a document that cannot be parsed is a missing document here
        return None


def usd_path(task_id: str) -> str | None:
    """The asset a task's recipe loads, or ``None`` when the document does not say."""
    found = _params_document(task_id)
    if found is None:
        return None
    asset = ((found[0].get("robot") or {}) if isinstance(found[0], dict) else {}).get("usd_path")
    return asset if isinstance(asset, str) and asset else None


def runtime_joint_order_for_asset(asset: str) -> list[str] | None:
    """The measured articulation order of an asset, or ``None`` when unpinned.

    Keyed by the asset because that is what the order belongs to: every recipe loading the same
    USD resolves the same sequence, whatever line or version it belongs to.
    """
    if not asset or not RUNTIME_ORDERS.is_file():
        return None
    try:
        entry = (json.loads(RUNTIME_ORDERS.read_text(encoding="utf-8")).get("assets") or {}).get(asset)
    except (OSError, json.JSONDecodeError):
        return None
    order = (entry or {}).get("joint_order")
    return list(order) if isinstance(order, list) and order else None


def runtime_joint_order(task_id: str) -> list[str] | None:
    """The measured articulation order of this task's asset, or ``None`` when unpinned.

    Kept apart from the recipe's ``joint_order`` on purpose: that one is the URDF tree order the
    deployment side reads, while this one is what the observation and the action actually index.
    A permutation here misaligns every checkpoint trained before it, so it is measured once and
    compared from then on, never inferred from the version or the asset's name.
    """
    asset = usd_path(task_id)
    return runtime_joint_order_for_asset(asset) if asset else None


def joint_order_digest(task_id: str) -> str | None:
    """A digest of the pinned runtime order, for run records: which order a policy trained under."""
    order = runtime_joint_order(task_id)
    if order is None:
        return None
    return hashlib.sha256("\n".join(order).encode("utf-8")).hexdigest()


def task_route(task_id: str) -> dict:
    """The declaration's route for one task: ``protocol``, ``version``, ``line``.

    Empty for an undeclared task: callers that need a hard failure ask
    :func:`protocol_for`, while a reader reporting on many tasks wants the absence as a value.
    """
    route = (declaration().get("tasks") or {}).get(task_id)
    return dict(route) if isinstance(route, dict) else {}


def declared(task_id: str) -> bool:
    """Whether the declaration carries this task at all.

    Asked separately from :func:`protocol_for` because "not declared" and "declared but the
    recipe has no live config any more" are different situations: the first is a typo or a gap
    and should raise, the second is a retirement -- a legal lifecycle move whose golden and
    frozen yaml stay -- and a gate should report it as a line of text, not die importing.
    """
    route = (declaration().get("tasks") or {}).get(task_id)
    return isinstance(route, dict) and "protocol" in route


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


def live_terms_for(task_id: str, group: str) -> list[str]:
    """The terms a group actually carries: the declared order minus the dropped ones.

    A dropped term is still part of the declaration -- it says the cfg had a term there and
    took it away -- while the manager sees only the live ones. Both questions are asked, so
    both answers are available from one place.

    Raises:
        ProtocolError: as :func:`terms_for`.
    """
    groups = groups_for(task_id)
    terms = terms_for(task_id, group)
    dropped = set(groups[group].get("dropped_terms") or [])
    return [term for term in terms if term not in dropped]


def anchors() -> dict:
    """The approved facts about each protocol: digest, widths, label, purpose.

    Read from the same file the gate reads and never writes: approving a digest or a width is
    a separate, deliberate act, and a module that could refresh them would approve anything it
    happened to load.

    Raises:
        ProtocolError: the file is missing or unreadable.
    """
    try:
        return json.loads(ANCHORS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ProtocolError(f"cannot read {ANCHORS}: {err}") from err


def recorded_dims(task_id: str) -> dict[str, int] | None:
    """The approved per-group widths, or ``None`` when no real run has asserted them yet.

    ``None`` and ``{}`` mean different things -- unmeasured versus measured-and-empty -- so the
    caller can tell "nobody has looked" from "there is nothing there".
    """
    key = protocol_for(task_id)
    entry = (anchors().get("protocols") or {}).get(key)
    dims = entry.get("dims") if isinstance(entry, dict) else None
    return dict(dims) if isinstance(dims, dict) and dims else None


def dims_for(task_id: str) -> dict[str, int]:
    """The approved per-group widths a smoke assertion may compare against.

    Raises:
        ProtocolError: this protocol has no measured widths. Asserting against an invented
            width is worse than not asserting: it fails the tree for being right.
    """
    dims = recorded_dims(task_id)
    if dims is None:
        raise ProtocolError(f"{task_id}: no approved dims for this protocol; a real run has to measure them first")
    return dims


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
