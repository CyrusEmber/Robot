# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Evaluation record format: the conditions a run was measured under (ARCH_PLAN Step 3.2a).

An eval run's numbers are only readable next to the conditions that produced them, and
``mbenv.cfg`` after ``gym.make`` does not carry them: the command player, the robust push,
the metric thresholds and the eval step count are all built *after* the env exists
(``eval.py``). So the record names each of them separately -- a changed command or a changed
threshold does not have to show up in the env cfg digest to be recorded.

Stdlib only, and no torch/sim/RNG import: this module defines a format and reads it back, so
a record can be inspected on a machine that cannot start the simulator, and writing a record
can never consume the random stream the numbers are supposed to describe.

The format version is independent of the eval protocol version: a protocol bump (timeline,
thresholds, terrain, DR, metric definitions, sampled frame) is a new ``locomotion_eval_vN``;
adding a provenance field is not, and would otherwise force a protocol version for a change
that does not move any number.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys

# The digest primitive (and the one revision spelling) live on the training side's runrecord
# package, which is what this record binds against: PLAN.md #27 ①, one file hashes a file.
# Reached by absolute path because the harness is invoked from IsaacLab and ``rl_exp`` is not
# an installed package -- the same insert ``eval.py`` does for its other in-repo readers.
_REPO = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.runrecord import binding  # noqa: E402

RECORD_FORMAT = "eval-record-1"

#: Fields every complete record carries, as dotted paths into the record.
ALWAYS = (
    "run.run_id",
    "run.task",
    "run.mode",
    "run.seed",
    "run.protocol_file",
    "env_cfg.digest",
    "agent_cfg.digest",
    "agent_cfg.clip_actions",
    "commands.timeline",
    "commands.segments",
    "metrics.fall.tilt_deg",
    "metrics.fall.base_height_ratio",
    "metrics.fall.sustain_s",
    "eval_protocol.name",
    "eval_protocol.version",
    "eval_protocol.digest",
    "obs_protocol.identity",
    "obs_protocol.digest",
    "suite.name",
    "suite.digest",
    "policy.kind",
    "assets.declared_digest",
    "assets.actual.verdict",
    "runtime.device",
    "runtime.num_envs",
    "runtime.num_envs_declared",
    "runtime.rsl_rl_version",
    "runtime.sim_version",
    "runtime.git_rev_lizard",
    "runtime.git_rev_isaaclab",
)

#: Fields required only under a recorded condition. Each condition field is itself in
#: :data:`ALWAYS`, so "no checkpoint" cannot be claimed by omitting the policy kind.
CONDITIONAL: dict[str, dict[str, tuple[str, ...]]] = {
    "policy.kind": {
        "checkpoint": (
            "checkpoint.path",
            "checkpoint.sha256",
            "checkpoint.size",
            "checkpoint.mtime",
            "checkpoint.sha256_after_load",
        )
    },
    "run.mode": {
        "robust": ("perturbation.t", "perturbation.kick_mps", "perturbation.direction_seed", "perturbation.num_steps")
    },
}

#: Fields that decide whether two records describe the same measurement (P04's four
#: substitutions -- checkpoint / suite / assets / protocol -- plus the declared obs protocol).
BINDINGS = (
    "checkpoint.sha256",
    "suite.digest",
    "assets.declared_digest",
    "eval_protocol.digest",
    "obs_protocol.identity",
    "obs_protocol.digest",
)

#: Value written for a fact that could not be established. Deliberately a string, not
#: ``null``: an empty slot reads like "not recorded", which is the thing Step 0c refuses.
UNKNOWN = "unknown"

_MISSING = object()


def canonical(obj) -> str:
    """One deterministic JSON rendering, so equal content hashes equal."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(obj) -> str:
    """``sha256:`` digest of one object's canonical rendering."""
    return "sha256:" + hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def file_sha256(path: pathlib.Path | str, chunk: int = 1 << 20) -> str | None:
    """``sha256:`` digest of a file, or ``None`` when it cannot be read.

    The digest comes from the shared primitive (bare hex, ``binding.sha256_file``); the
    ``sha256:`` prefix is this record format's own spelling and stays here, so moving the
    primitive did not move any emitted value.
    """
    digest = binding.sha256_file(path, chunk)
    return None if digest is None else "sha256:" + digest


def checkpoint_digest(path: pathlib.Path | str) -> dict:
    """Identify a checkpoint file: digest, byte size and mtime.

    Taken where the policy is *loaded*, not re-read after the run: a checkpoint overwritten
    mid-run would otherwise be certified by a file the run never used.
    """
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


def get(record: dict, path: str):
    """Value at a dotted path, or an internal missing marker when any step is absent."""
    node = record
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


def missing(record: dict) -> list[str]:
    """Required paths this record does not carry (``None`` counts as absent)."""
    if not isinstance(record, dict):
        return ["<record>"]
    absent = [path for path in ALWAYS if get(record, path) in (_MISSING, None)]
    for condition_path, table in CONDITIONAL.items():
        value = get(record, condition_path)
        for condition, paths in table.items():
            if value == condition:
                absent += [path for path in paths if get(record, path) in (_MISSING, None)]
    return absent


def read_state(record: dict) -> dict:
    """Three-state read: ``legacy`` / ``incomplete`` / ``complete``, plus why.

    * no ``record_format`` = legacy: absent fields stay unknown, nothing is derived or filled in;
    * a ``record_format`` we do not know, or a known one missing fields = **incomplete**: not
      legacy treatment, and not a pass either;
    * everything required present = complete. A field whose value is :data:`UNKNOWN` is
      present and therefore complete -- absence of *evidence* is recorded, not hidden.
    """
    if not isinstance(record, dict):
        return {"state": "incomplete", "missing": ["<record>"], "note": "not a JSON object"}
    fmt = record.get("record_format")
    if fmt is None:
        return {
            "state": "legacy",
            "missing": [],
            "note": "no record_format: legacy record; absent fields stay unknown, nothing is derived",
        }
    if fmt != RECORD_FORMAT:
        return {
            "state": "incomplete",
            "missing": [],
            "note": f"record_format {fmt!r} is not {RECORD_FORMAT!r}: its required set is unknown, "
            "so it cannot be read as complete",
        }
    absent = missing(record)
    if absent:
        return {
            "state": "incomplete",
            "missing": absent,
            "note": "format present but required fields are missing: not legacy treatment, and not a pass",
        }
    # the checkpoint re-read after load is not decoration: a mismatch means the file that was
    # hashed is not the file that ran, so the record describes neither one of them
    loaded = get(record, "checkpoint.sha256_after_load")
    if loaded is not _MISSING and loaded != get(record, "checkpoint.sha256"):
        return {
            "state": "incomplete",
            "missing": [],
            "note": "checkpoint digest changed between load and recheck: the record does not describe the file that ran",
        }
    return {"state": "complete", "missing": [], "note": ""}


def compare(a: dict, b: dict) -> dict:
    """Comparability of two records: ``comparable`` / ``not_comparable`` / ``unknown``.

    A missing side, or a binding that reads :data:`UNKNOWN`, is **unknown**: absent evidence
    never upgrades itself into comparability. ``differences`` holds only bindings whose values
    actually **differ**; ``unproven`` names bindings that read ``unknown`` on both sides -- equal,
    but equal in the absence of a value. A binding that reads ``unknown`` on one side and is
    known on the other is both. Metadata that does not bind the measurement (run id, timestamp,
    group) is deliberately not compared.
    """
    for label, side in (("a", a), ("b", b)):
        state = read_state(side)
        if state["state"] != "complete":
            return {
                "verdict": "unknown",
                "reason": f"{label} record is {state['state']}: {state['note'] or state['missing']}",
                "differences": {},
                "unproven": [],
            }
    differences: dict[str, dict] = {}
    unproven: list[str] = []
    for path in BINDINGS:
        left, right = get(a, path), get(b, path)
        left = None if left is _MISSING else left
        right = None if right is _MISSING else right
        if left is None and right is None:
            continue
        if left == right:
            if left == UNKNOWN:
                unproven.append(path)
            continue
        differences[path] = {"a": left, "b": right}
        if left == UNKNOWN or right == UNKNOWN:
            unproven.append(path)
    if differences:
        reason = "bindings differ" if not unproven else f"{', '.join(unproven)} cannot be compared"
        return {
            "verdict": "unknown" if unproven else "not_comparable",
            "reason": reason,
            "differences": differences,
            "unproven": unproven,
        }
    if unproven:
        return {
            "verdict": "unknown",
            "reason": f"{', '.join(unproven)} is unknown on both sides: equal, but unproven",
            "differences": {},
            "unproven": unproven,
        }
    return {"verdict": "comparable", "reason": "", "differences": {}, "unproven": []}


def legacy_run() -> dict:
    """A stand-in for a run that predates the format: results, but no record.

    It reads as ``legacy``, so a run directory holding an ``eval.json`` and no ``record.json``
    is refused exactly like a legacy record rather than mistaken for an empty run_id -- 3.2c
    exists because an existing run whose identity cannot be established must not be replaced
    silently.
    """
    return {"note": "run directory holds results without a record (pre-format)"}


def overwrite_refusal(previous: dict | None, current: dict) -> str | None:
    """Why writing ``current`` over ``previous`` must be refused, or ``None`` when it may proceed.

    ``None`` previous means nothing sits at that run_id. A previous record that is not complete
    -- legacy, another format, missing fields -- is refused: its identity cannot be established.
    A complete previous record is refused when a binding **differs**; when the bindings are equal
    the pair is the same measurement re-run and overwrites itself, and bindings that read
    ``unknown`` on both sides count as equal there (equal evidence, absent though it is).
    """
    if previous is None:
        return None
    state = read_state(previous)
    if state["state"] != "complete":
        return (
            f"an existing record is {state['state']} "
            f"({state['note'] or state['missing']}): its identity cannot be established"
        )
    verdict = compare(previous, current)
    if verdict["differences"]:
        return "an existing record differs on " + ", ".join(verdict["differences"])
    return None


def load(path: pathlib.Path | str) -> dict:
    """Read a record file; a missing or unreadable file is a hard error, not an empty record."""
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
