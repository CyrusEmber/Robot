# -*- coding: utf-8 -*-
"""Order-preserving, lossless config snapshot serializer (ARCH_PLAN 1.1).

Turns a resolved config object into a JSON-safe snapshot that can be diffed and
hashed. The rules it implements (ARCH_PLAN 详案 1.1) are all about not losing
information that a plain ``to_dict()`` + ``json.dump`` silently loses:

* **order is semantic** -- dataclass field order and mapping insertion order carry
  meaning (obs groups and term order, action order, joint/foot order, terrain
  column -> combo order, ``sub_terrains`` key order). They are preserved in the
  JSON text, so the digest covers them too; a reordered mapping is a different
  digest.
* **floats round-trip** -- ``repr`` of a Python float is exact in 3.x, so floats
  are written as-is: no rounding, no fixed digit count, no truncation. Non-finite
  values get an explicit tag instead of the non-standard ``NaN``/``Infinity``.
* **callables are identities, not addresses** -- module + qualname only; the code
  version that gives them meaning is bound separately by the run manifest. A
  ``repr`` containing ``0x...`` in a snapshot means this rule was bypassed.
* **missing is not None** -- a real ``None`` stays ``null``; an unset value becomes a
  distinguishable marker, so "not configured" can never read as "set to None". The
  marker is matched by TYPE, not identity: config members are deep-copied at
  construction (``_process_mutable_types``/``_custom_post_init``), which mints new
  ``_MISSING_TYPE`` instances, so ``value is dataclasses.MISSING`` is False for a
  field that a recipe never set (real case: ``RslRlOnPolicyRunnerCfg`` fields).
* **paths are relative** -- repo and Isaac paths become ``<REPO_ROOT>`` /
  ``<ISAAC_ROOT>``; external URLs pass through untouched.
* **opaque objects get stable tags** -- ``slice``, ``type``, tensors, arrays, sets
  are tagged by value or by name, never by address or iteration order.
* **no address ever reaches the text** -- an object whose only printable form
  embeds ``0x...`` contributes its type identity and no value text; otherwise the
  digest would depend on the allocator instead of the config.

The snapshot is for comparison, not for reconstruction: nothing here rebuilds an
object from the snapshot. 1.2 binds the actual value separately in the manifest,
and 1.5 hashes assets by content rather than embedding them here.

Hashing a snapshot never writes the hash back into the snapshot (see the "no
self-referential hash" constraint); the digest goes next to it.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from dataclasses import MISSING

FORMAT_VERSION = 1
"""Snapshot format version; record it next to any snapshot whose digest is pinned."""

MISSING_TAG = "__missing__"
CALLABLE_TAG = "__callable__"
TYPE_TAG = "__type__"
SLICE_TAG = "__slice__"
TUPLE_TAG = "__tuple__"
SET_TAG = "__set__"
ARRAY_TAG = "__array__"
FLOAT_TAG = "__float__"
VALUE_TAG = "__value__"

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]+")
"""Address pattern: any snapshot text containing one is not reproducible."""

try:  # single source of truth for the host Isaac root (paths.yaml + marker)
    from ablation_harness.host_paths import isaac_root as _isaac_root

    ISAAC_ROOT = _isaac_root()
except Exception:  # noqa: BLE001 - unresolved host path must not crash the offline tools
    ISAAC_ROOT = None


def relativize(text: str) -> str:
    """Replace repo / Isaac root prefixes with placeholders."""
    for root, tag in ((_REPO_ROOT, "<REPO_ROOT>"), (ISAAC_ROOT, "<ISAAC_ROOT>")):
        if root is None:
            continue
        prefix = str(root)
        if text == prefix:
            return tag
        for sep in (os.sep, "/", "\\"):
            if text.startswith(prefix + sep):
                tail = text[len(prefix) + 1 :]
                return f"{tag}/{tail.replace(os.sep, '/')}" if sep == os.sep else f"{tag}/{tail}"
    return text


def _callable_id(obj) -> str:
    """Stable identity of a callable/type: module + qualified name."""
    module = getattr(obj, "__module__", None) or ""
    qualname = getattr(obj, "__qualname__", None) or getattr(obj, "__name__", None) or "<anonymous>"
    return f"{module}.{qualname}" if module else qualname


def _is_finite(value: float) -> bool:
    """True for finite floats: NaN and the infinities are not JSON-representable."""
    return value == value and value not in (float("inf"), float("-inf"))


def _array_tag(obj) -> dict:
    """Content digest of a tensor/array, so equality does not depend on formatting."""
    dtype = str(getattr(obj, "dtype", type(obj).__name__))
    shape = list(getattr(obj, "shape", ()) or ())
    try:
        payload = obj.detach().cpu().numpy().tobytes()
    except AttributeError:
        payload = obj.tobytes()
    return {ARRAY_TAG: {"dtype": dtype, "shape": shape, "sha256": hashlib.sha256(payload).hexdigest()}}


def snapshot(obj, *, _depth: int = 0):
    """Convert a config value into a JSON-safe, order-preserving snapshot.

    Args:
        obj: any value reachable from a config: dataclass instance, mapping,
            sequence, scalar, callable, array or opaque object.

    Returns:
        The snapshot: plain JSON scalars/arrays/objects, plus tagged objects for
        everything JSON cannot represent without losing meaning.

    Raises:
        ValueError: past ``_depth`` levels, which means the value is a cycle or a
            deeper structure than a config tree can legitimately be.
    """
    if _depth > 64:
        raise ValueError("config nesting deeper than 64 levels: cycle or non-config object?")
    depth = _depth + 1

    # order matters: bool is an int, str is a Sequence, ResolvableString is a str
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return obj if _is_finite(obj) else {FLOAT_TAG: repr(obj)}
    if isinstance(obj, str):
        return relativize(obj)
    if isinstance(obj, type(MISSING)):
        return {MISSING_TAG: True}
    if isinstance(obj, slice):
        return {SLICE_TAG: [snapshot(obj.start, _depth=depth), snapshot(obj.stop, _depth=depth), obj.step]}
    if isinstance(obj, (bytes, bytearray)):
        return {ARRAY_TAG: {"dtype": "bytes", "shape": [len(obj)], "sha256": hashlib.sha256(bytes(obj)).hexdigest()}}
    if isinstance(obj, type):
        return {TYPE_TAG: _callable_id(obj)}
    if callable(obj):
        return {CALLABLE_TAG: _callable_id(obj)}
    if isinstance(obj, (set, frozenset)):
        return {SET_TAG: sorted(json.dumps(snapshot(v, _depth=depth)) for v in obj)}
    if hasattr(obj, "__dataclass_fields__"):
        # Iterate the instance namespace, not the declared fields: version
        # constructors assign whole pieces imperatively (e.g. `V3.__post_init__`
        # does `self.observations.extero = ...`), so those groups exist on the
        # instance but are NOT dataclass fields -- walking the declared fields
        # silently drops the observation groups the network contract is built on.
        out = {name: snapshot(value, _depth=depth) for name, value in vars(obj).items() if not name.startswith("__")}
        for name in obj.__dataclass_fields__:
            if name not in out:
                # declared but never set on the instance: absent, NOT an explicit None
                out[name] = {MISSING_TAG: True}
        return out
    if isinstance(obj, dict):
        return {str(key): snapshot(value, _depth=depth) for key, value in obj.items()}
    if isinstance(obj, tuple):
        return {TUPLE_TAG: [snapshot(v, _depth=depth) for v in obj]}
    if isinstance(obj, list):
        return [snapshot(v, _depth=depth) for v in obj]
    if isinstance(obj, pathlib.PurePath):
        return relativize(str(obj))
    if hasattr(obj, "dtype") and hasattr(obj, "shape"):
        return _array_tag(obj)
    # last resort: the type identity, plus the plain text form only when it is free of
    # addresses -- `str()` of a bare object embeds `at 0x...`, which would make the
    # digest follow the allocator (and change on every run)
    text = relativize(str(obj))
    fallback = {TYPE_TAG: _callable_id(type(obj))}
    if not ADDRESS_RE.search(text):
        fallback[VALUE_TAG] = text
    return fallback


def canonical_json(snap) -> str:
    """Canonical JSON text of a snapshot: semantic order kept, separators fixed."""
    return json.dumps(snap, sort_keys=False, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(snap) -> str:
    """SHA-256 of the canonical JSON: covers values, order and tags, not the file."""
    return hashlib.sha256(canonical_json(snap).encode("utf-8")).hexdigest()
