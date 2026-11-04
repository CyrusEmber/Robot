# -*- coding: utf-8 -*-
"""Offline gate for the eval record format (`ARCH_PLAN` Step 3.2a/3.2e, no sim).

Four things this file is here to prove:

1. The read side keeps Step 0c's four rules apart -- no ``record_format`` is *legacy*
   (fields stay unknown), a format missing its required fields is *incomplete* (not legacy,
   not a pass), and only a complete record can be compared at all.
2. P04's four substitutions (checkpoint / suite / assets / protocol) each move **their own**
   binding, so a swapped input cannot be published under the old record's identity.
3. The record module writes records without consuming the random stream: it must not import
   torch, numpy or random at all (3.2d's offline half).
4. The write-time substitution evidence (``record.substitution_evidence``, work/active/record-variant-and-snapshot-specs.md A3) keeps
   "compared, nothing confirmed" apart from "could not be compared", counts only *proven* moves,
   and stores the values it compared instead of re-reading a baseline that may have moved since.
5. The lookup that feeds it (``record.baseline_evidence``) is offline-reachable: the layout rule
   and all three refusal reasons are asserted here, including the one success path that a broken
   path composition would otherwise hide behind "always unknown".
6. The sweep scheduler's completion evidence and launch path
   (``work/active/ablation-sweep-final-checkpoint-name.md``): a run of budget N ends on
   ``model_{N-1}.pt``, a spec naming no checkpoints is scored at that last one, a finished run is
   not re-trained, and eval enters through the harness's own absolute path.

The negative direction is built in: every substitution asserts both that the digest moved and
that the two records read as ``not_comparable``, and the untouched pair as ``comparable``.
"""

import ast
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import types

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "ablation_harness"))

import record  # noqa: E402
import run_ablation  # noqa: E402  (sibling: the sweep's completion evidence and launch paths)


def _record(complete: bool = True) -> dict:
    """A minimal complete record; ``complete=False`` drops one required field."""
    rec = {
        "record_format": record.RECORD_FORMAT,
        "run": {
            "run_id": "Lizard-Rough-v14_ckpt_nominal_seed123",
            "task": "Lizard-Rough-v14",
            "tag": "ckpt",
            "mode": "nominal",
            "seed": 123,
            "protocol_file": "locomotion_eval_v2",
        },
        "env_cfg": {"digest": "sha256:env"},
        "agent_cfg": {"digest": "sha256:agent", "clip_actions": 1.0},
        "suite": {"name": "lizard_suite_v1", "digest": "sha256:suite", "geometry_digest": "sha256:geometry"},
        "judge": {"id": "judge-v1"},
        "commands": {
            "timeline": [{"t": 0.0, "vx": 0.5, "vy": 0.0, "wz": 0.0}],
            "segments": [{"name": "0-5s", "start_s": 0.0, "end_s": 5.0}],
        },
        "metrics": {"fall": {"tilt_deg": 40.0, "base_height_ratio": 0.6, "sustain_s": 0.5}},
        "eval_protocol": {"name": "Locomotion-Eval-v2", "version": 2, "digest": "sha256:proto"},
        "obs_protocol": {"identity": "proto-main-a", "digest": "sha256:obs"},
        "policy": {"kind": "zero_action"},
        "assets": {"declared_digest": "sha256:assets", "actual": {"verdict": "pass"}},
        "runtime": {
            "device": "cuda:0",
            "num_envs": 72,
            "num_envs_declared": 72,
            "rsl_rl_version": "5.4.2",
            "sim_version": "5.1.0",
            "git_rev_lizard": "abc1234",
            "git_rev_isaaclab": "def5678",
        },
    }
    if not complete:
        rec["suite"].pop("digest")
    return rec


def test_legacy_record_stays_unknown() -> None:
    """No record_format = legacy: absent fields read as unknown and nothing is filled in."""
    legacy = {"task": "Lizard-Rough-v14", "seed": 123}
    state = record.read_state(legacy)
    assert state["state"] == "legacy", f"a record without a format must read as legacy: {state}"
    assert state["missing"] == [], "legacy has no required set to miss -- it is not a pass either"
    assert record.compare(legacy, _record())["verdict"] == "unknown", \
        "a legacy record cannot be comparable to a complete one"


def test_incomplete_format_is_neither_legacy_nor_a_pass() -> None:
    """A format missing its required fields, and an unknown format, both read as incomplete."""
    short = _record(complete=False)
    state = record.read_state(short)
    assert state["state"] == "incomplete", f"a required field is missing: {state}"
    assert state["missing"] == ["suite.digest"], f"the missing field must be named: {state}"

    unknown_format = _record()
    unknown_format["record_format"] = "eval-record-9999"
    assert record.read_state(unknown_format)["state"] == "incomplete", \
        "a format whose required set we do not know cannot be read as complete"


def test_unknown_valued_binding_is_complete_but_not_comparable() -> None:
    """A recorded 'unknown' is present (complete) yet never upgrades into comparability."""
    one = _record()
    other = _record()
    other["assets"]["declared_digest"] = record.UNKNOWN
    assert record.read_state(other)["state"] == "complete", "the field is recorded, only its value is unknown"
    verdict = record.compare(one, other)
    assert verdict["verdict"] == "unknown", f"unknown evidence must not compare as equal: {verdict}"
    assert verdict["unproven"] == ["assets.declared_digest"], \
        f"the unproven binding must be named: {verdict}"
    assert list(verdict["differences"]) == ["assets.declared_digest"], \
        "one side has a digest and the other does not: that is a difference too"


def test_equal_unknowns_are_indistinguishable_but_unproven() -> None:
    """Two records whose binding is unknown on *both* sides are the same measurement re-run.

    They are not comparable in the strong sense (nothing was proven) -- the verdict stays
    ``unknown`` -- but nothing differs, so a re-run of that measurement must be allowed to
    overwrite itself. This is the dev line, where no frozen asset lock exists at all.
    """
    dev = _record()
    dev["assets"]["declared_digest"] = record.UNKNOWN
    twin = _record()
    twin["assets"]["declared_digest"] = record.UNKNOWN
    verdict = record.compare(dev, twin)
    assert verdict["verdict"] == "unknown" and verdict["differences"] == {}, \
        f"equal unknowns are not a difference: {verdict}"
    assert verdict["unproven"] == ["assets.declared_digest"], "and they must be visible as unproven"
    assert record.overwrite_refusal(dev, twin) is None, \
        "an identical measurement re-run must be able to overwrite itself"
    # but the dev record and a locked one do differ, and that stays refused
    refusal = record.overwrite_refusal(dev, _record())
    assert refusal is not None and "assets.declared_digest" in refusal, \
        f"unknown vs a real digest is a difference: {refusal}"


def test_conditions_carry_their_own_required_fields() -> None:
    """robust mode and a checkpoint policy each add fields; dropping one is incomplete."""
    robust = _record()
    robust["run"]["mode"] = "robust"
    state = record.read_state(robust)
    assert state["state"] == "incomplete", "a robust run without its perturbation is incomplete"
    assert "perturbation.t" in state["missing"] and "perturbation.num_steps" in state["missing"]
    robust["perturbation"] = {"t": 12.0, "kick_mps": 4.0, "direction_seed": 123, "num_steps": 600}
    assert record.read_state(robust)["state"] == "complete", \
        "filling the perturbation must close the record"

    ckpt = _record()
    ckpt["policy"]["kind"] = "checkpoint"
    state = record.read_state(ckpt)
    assert state["state"] == "incomplete" and "checkpoint.sha256" in state["missing"], \
        "a checkpoint policy without a hashed checkpoint is incomplete"


def _ckpt_record(digest: str, recheck: str | None = None) -> dict:
    """A checkpoint record; ``recheck`` overrides the post-load re-read."""
    rec = _record()
    rec["policy"] = {"kind": "checkpoint"}
    rec["checkpoint"] = {
        "path": "logs/model_100.pt",
        "sha256": digest,
        "size": 4096,
        "mtime": 1.0,
        "sha256_after_load": recheck if recheck is not None else digest,
    }
    return rec


def test_checkpoint_swapped_under_the_run_voids_the_record() -> None:
    """A checkpoint that changed between load and recheck describes no file that actually ran."""
    rec = _ckpt_record("sha256:first", recheck="sha256:second")
    state = record.read_state(rec)
    assert state["state"] == "incomplete", f"a re-read mismatch must not read as complete: {state}"
    assert "does not describe" in state["note"], f"the reason must be the mismatch: {state}"
    assert record.read_state(_ckpt_record("sha256:first"))["state"] == "complete", \
        "an unchanged checkpoint stays complete"


def test_p04_each_substitution_moves_its_own_binding() -> None:
    """ckpt / suite / assets / protocol: each swapped input moves that binding and only it."""
    assert record.compare(_record(), _record())["verdict"] == "comparable", \
        "two identical records must compare"

    subst = {
        "checkpoint.sha256": _ckpt_record("sha256:a"),
        "suite.digest": _record(),
        "assets.declared_digest": _record(),
        "eval_protocol.digest": _record(),
    }
    subst["suite.digest"]["suite"]["digest"] = "sha256:other-suite"
    subst["assets.declared_digest"]["assets"]["declared_digest"] = "sha256:other-assets"
    subst["eval_protocol.digest"]["eval_protocol"]["digest"] = "sha256:other-protocol"

    for path, other in subst.items():
        base = _ckpt_record("sha256:b") if path == "checkpoint.sha256" else _record()
        verdict = record.compare(base, other)
        assert verdict["verdict"] == "not_comparable", f"{path}: a swapped input must not stay comparable"
        assert list(verdict["differences"]) == [path], \
            f"{path}: exactly that binding must be named: {verdict['differences']}"


#: The baseline reference a variant run writes into its evidence: the base run id kept *before*
#: the ``--variant`` suffix is appended (``eval.py``), in its own protocol dir and group.
_BASELINE_REF = {
    "run_id": "Lizard-Rough-v14_ckpt_nominal_seed123",
    "path": "results/locomotion_eval_v2/v1/Lizard-Rough-v14_ckpt_nominal_seed123/record.json",
}


def _evidence(candidate: dict, baseline: dict | None, reason: str = "") -> dict:
    """The write-time evidence for one candidate/baseline pair, the way `eval.py` asks for it."""
    return record.substitution_evidence(candidate, baseline, baseline_ref=dict(_BASELINE_REF), reason=reason)


def test_confirmed_substitutions_are_named_and_valued() -> None:
    """A moved binding with a value on both sides is proven; the values that proved it are stored."""
    base = _record()
    variant = _record()
    variant["suite"]["digest"] = "sha256:other-suite"
    variant["assets"]["declared_digest"] = "sha256:other-assets"
    evidence = _evidence(variant, base)
    assert evidence["comparison"] == "compared", f"a complete pair is compared: {evidence}"
    assert evidence["substitutions"] == ["suite", "assets"], \
        f"both moved bindings must be named, in BINDINGS order: {evidence['substitutions']}"
    assert evidence["unproven"] == [], f"both sides carry a value: nothing is unproven: {evidence['unproven']}"
    assert evidence["reason"] == "", "a comparison that ran has no excuse to give"
    assert evidence["baseline"] == _BASELINE_REF, "the reference that was looked up is recorded"
    assert evidence["bindings"]["suite.digest"] == {"candidate": "sha256:other-suite", "baseline": "sha256:suite"}, \
        f"the compared values are stored, not just the verdict: {evidence['bindings']['suite.digest']}"
    assert set(record.compare(base, variant)["differences"]) == {"suite.digest", "assets.declared_digest"}, \
        "the pair really does differ on exactly those two bindings"


def test_obs_protocol_bindings_report_as_one_category() -> None:
    """A layout swap moves two bindings but is one substitution -- naming it twice overstates it."""
    base = _record()
    variant = _record()
    variant["obs_protocol"]["identity"] = "proto-main-b"
    variant["obs_protocol"]["digest"] = "sha256:other-obs"
    evidence = _evidence(variant, base)
    assert evidence["substitutions"] == ["obs_protocol"], \
        f"the two obs bindings are one category: {evidence['substitutions']}"
    assert list(record.compare(base, variant)["differences"]) == ["obs_protocol.identity", "obs_protocol.digest"], \
        "both bindings do move -- the merge is this derivation's job, not compare()'s"


def test_an_unproven_side_is_not_a_substitution() -> None:
    """compare() counts unknown-vs-known as a difference; a difference is not proof."""
    base = _record()
    base["assets"]["declared_digest"] = record.UNKNOWN
    evidence = _evidence(_record(), base)
    assert evidence["comparison"] == "compared", "the pair is still compared, one side is just short of evidence"
    assert evidence["substitutions"] == [], f"nothing proven moved, so nothing is claimed: {evidence}"
    assert [entry["path"] for entry in evidence["unproven"]] == ["assets.declared_digest"], \
        f"the undecidable binding must be named: {evidence['unproven']}"
    assert record.UNKNOWN in evidence["unproven"][0]["reason"], \
        f"and it must say why: {evidence['unproven'][0]['reason']}"
    assert "assets.declared_digest" in record.compare(base, _record())["differences"], \
        "compare() does call it a difference -- which is exactly why its keys are not the substitutions"

    # the mirror image, and an absent field: a zero-action baseline carries no checkpoint digest,
    # so a checkpoint candidate differs from it without that proving a *swap* of one
    known = _record()
    known["assets"]["declared_digest"] = record.UNKNOWN
    unknown = _record()
    unknown["assets"]["declared_digest"] = record.UNKNOWN
    assert _evidence(unknown, known)["substitutions"] == [], "unknown on both sides is equal, not a swap"
    assert [entry["path"] for entry in _evidence(_ckpt_record("sha256:cpp"), _record())["unproven"]] == \
        ["checkpoint.sha256"], "a binding the baseline never carried is undecidable, not substituted"


def test_an_unreadable_baseline_reads_unknown_with_its_reason() -> None:
    """A legacy or incomplete baseline decides nothing, and the evidence says which it was."""
    legacy = _evidence(_record(), {"task": "Lizard-Rough-v14", "seed": 123})
    assert legacy["comparison"] == record.UNKNOWN, "a legacy baseline cannot decide a substitution"
    assert "legacy" in legacy["reason"], f"the reason must name what the baseline is: {legacy['reason']}"
    assert legacy["substitutions"] == [] and legacy["unproven"] == [], "nothing was compared, nothing is claimed"
    assert legacy["bindings"]["suite.digest"]["candidate"] == "sha256:suite", \
        "the values this run used are still recorded when the comparison falls through"

    short = _evidence(_record(), _record(complete=False))
    assert short["comparison"] == record.UNKNOWN and "incomplete" in short["reason"], short
    assert "suite.digest" in short["reason"], f"the missing baseline field must be named: {short['reason']}"


def test_a_missing_baseline_reads_unknown_with_a_reason() -> None:
    """No readable baseline there is `unknown` + why -- never a search, and not "the first run"."""
    reason = "a pre-format run sits at results/.../Lizard-Rough-v14_ckpt_nominal_seed123 (results, no record)"
    evidence = _evidence(_record(), None, reason=reason)
    assert evidence["comparison"] == record.UNKNOWN and evidence["reason"] == reason, \
        f"the caller's reason must travel with the verdict: {evidence}"
    assert evidence["baseline"] == _BASELINE_REF, "and so must the reference that was looked at"
    assert evidence["substitutions"] == [] and evidence["unproven"] == [], "no comparison happened"
    assert evidence["bindings"]["suite.digest"] == {"candidate": "sha256:suite", "baseline": None}, \
        "the baseline side is empty, never a fabricated value"


#: The three values ``eval.py`` hands the lookup: protocol directory, campaign group, base run id.
#: A path composed wrongly reads as a *missing* baseline here, which is why the success case below
#: exists -- the three refusal reasons alone cannot tell a right lookup from a broken one.
_LOOKUP = {"protocol": "locomotion_eval_v2", "group": "v1", "base_run_id": "Lizard-Rough-v14_ckpt"}


def _baseline_dir(scratch: str) -> pathlib.Path:
    """The run directory the lookup must resolve, laid out like the harness' results tree."""
    return (pathlib.Path(scratch) / "results" / _LOOKUP["protocol"] / _LOOKUP["group"]
            / _LOOKUP["base_run_id"])


def _lookup(scratch: str, candidate: dict) -> dict:
    """The write side's lookup, asked exactly as ``eval.py`` asks it."""
    return record.baseline_evidence(candidate, pathlib.Path(scratch) / "results", **_LOOKUP)


def test_baseline_lookup_reads_the_neighbouring_run() -> None:
    """The success path: protocol + group + base run id land on a record that compares.

    The campaign group is part of the path, so a lookup that ignored it (or dropped the protocol
    directory) reads as an absent baseline here rather than passing as a comparison.
    """
    with tempfile.TemporaryDirectory() as scratch:
        base = _record()
        base["suite"]["digest"] = "sha256:base-suite"
        path = _baseline_dir(scratch)
        path.mkdir(parents=True)
        (path / "record.json").write_text(json.dumps(base), encoding="utf-8")
        candidate = _record()
        candidate["suite"]["digest"] = "sha256:candidate-suite"
        evidence = _lookup(scratch, candidate)
        assert evidence["comparison"] == "compared", \
            f"a readable neighbour must be compared, not reported missing: {evidence}"
        assert evidence["substitutions"] == ["suite"], evidence["substitutions"]
        assert evidence["baseline"] == {"run_id": _LOOKUP["base_run_id"], "path": str(path / "record.json")}, \
            "the reference that was read is recorded, so a moved results root shows up in the record"


def test_baseline_lookup_names_a_preformat_neighbour() -> None:
    """A directory with results but no record (25 of 31 run dirs) is unknown with *that* reason."""
    with tempfile.TemporaryDirectory() as scratch:
        path = _baseline_dir(scratch)
        path.mkdir(parents=True)
        (path / "eval.json").write_text("{}", encoding="utf-8")
        evidence = _lookup(scratch, _record())
        assert evidence["comparison"] == record.UNKNOWN, evidence
        assert evidence["reason"] == \
            f"a pre-format run sits at {path} (results, no record): its bindings cannot be read", \
            evidence["reason"]
        assert evidence["substitutions"] == [] and evidence["unproven"] == [], "nothing was compared"


def test_baseline_lookup_names_an_absent_run() -> None:
    """Nothing there at all is a named absence -- never "this was the first run"."""
    with tempfile.TemporaryDirectory() as scratch:
        evidence = _lookup(scratch, _record())
        assert evidence["reason"] == f"nothing at {_baseline_dir(scratch)}", evidence["reason"]
        assert evidence["comparison"] == record.UNKNOWN, evidence


def test_baseline_lookup_names_an_unreadable_record() -> None:
    """A truncated record is a refusal with a reason; the parser's own wording is not pinned."""
    with tempfile.TemporaryDirectory() as scratch:
        path = _baseline_dir(scratch)
        path.mkdir(parents=True)
        (path / "record.json").write_text('{"record_format": ', encoding="utf-8")
        evidence = _lookup(scratch, _record())
        assert evidence["comparison"] == record.UNKNOWN, evidence
        assert evidence["reason"].startswith(f"{path / 'record.json'} is unreadable ("), evidence["reason"]


def test_baseline_lookup_names_invalid_utf8_record() -> None:
    """Invalid UTF-8 is unreadable evidence, not a failed evaluation."""
    with tempfile.TemporaryDirectory() as scratch:
        path = _baseline_dir(scratch)
        path.mkdir(parents=True)
        (path / "record.json").write_bytes(b'{"record_format": "\xff"}')
        evidence = _lookup(scratch, _record())
        assert evidence["comparison"] == record.UNKNOWN, evidence
        assert evidence["reason"].startswith(f"{path / 'record.json'} is unreadable ("), evidence["reason"]
        assert "utf-8" in evidence["reason"], evidence["reason"]
        assert evidence["baseline"] == {"run_id": _LOOKUP["base_run_id"], "path": str(path / "record.json")}
        assert evidence["substitutions"] == [] and evidence["unproven"] == [], evidence
        assert evidence["bindings"]["suite.digest"] == {"candidate": "sha256:suite", "baseline": None}, evidence


def test_an_empty_substitution_list_is_not_an_unknown_comparison() -> None:
    """`substitutions: []` means "compared, nothing confirmed" -- the unknown case must not read alike."""
    compared = _evidence(_record(), _record())
    assert compared["comparison"] == "compared" and compared["reason"] == "", compared
    assert compared["substitutions"] == [], "nothing moved, so the list is empty"
    unreachable = _evidence(_record(), None, reason="nothing at results/locomotion_eval_v2/...")
    assert unreachable["substitutions"] == [], "the list is empty in both cases, so it cannot carry the verdict"
    assert unreachable["comparison"] == record.UNKNOWN and unreachable["reason"], \
        "the discriminator has to be `comparison` plus the reason"


def test_stored_evidence_is_not_re_derived_from_a_later_baseline() -> None:
    """The evidence is a snapshot: a baseline rewritten afterwards cannot rewrite this run's story.

    The failure this pins is the one that takes a year to show up (work/active/record-variant-and-snapshot-specs.md): a baseline
    replaced by ``--overwrite`` while an old record still points at that path. The stored bindings
    are what was compared, so a reader never has to trust -- or re-interpret -- the live one.
    """
    candidate = _record()
    candidate["suite"]["digest"] = "sha256:other-suite"
    stored = _evidence(candidate, _record())
    assert stored["substitutions"] == ["suite"], stored["substitutions"]
    assert stored["bindings"]["suite.digest"]["baseline"] == "sha256:suite", "the baseline as it was"

    moved = _record()
    moved["suite"]["digest"] = "sha256:third-suite"
    assert _evidence(candidate, moved)["bindings"]["suite.digest"]["baseline"] == "sha256:third-suite", \
        "the live baseline would say something else now -- re-deriving would change the verdict"
    assert json.loads(json.dumps(stored)) == stored, "and the evidence survives the record's own JSON round trip"
    assert stored["bindings"]["suite.digest"]["baseline"] == "sha256:suite", \
        "the stored evidence keeps the values it was written with"


def test_the_evidence_is_not_a_field_the_format_requires() -> None:
    """A new key may not join ALWAYS: that would read the already-recorded eval records as incomplete."""
    assert "substitutions" not in record.ALWAYS, \
        "requiring it retroactively reads recorded batches as incomplete (the metrics.derived call)"
    plain = _record()
    assert "substitutions" not in plain, "a run that attempted no comparison carries no key at all"
    plain["substitutions"] = _evidence(plain, _record())
    assert record.read_state(plain)["state"] == "complete" and record.missing(plain) == [], \
        "carrying the evidence must not change how the record reads"
    assert record.compare(plain, _record())["differences"] == {}, \
        "the evidence is about the comparison; it is not one of the bindings compared"


def test_run_id_reuse_is_refused_unless_comparable() -> None:
    """3.2c: an occupied run_id may only be rewritten by the same measurement."""
    base = _record()
    assert record.overwrite_refusal(None, base) is None, "an empty run_id is never a refusal"
    assert record.overwrite_refusal(base, _record()) is None, "a re-run of the same measurement overwrites itself"
    swapped = _record()
    swapped["suite"]["digest"] = "sha256:other-suite"
    refusal = record.overwrite_refusal(base, swapped)
    assert refusal is not None and "suite.digest" in refusal, \
        f"a swapped suite under the same run_id must be refused, and say why: {refusal}"
    assert record.overwrite_refusal({"task": "Lizard-Rough-v14"}, base) is not None, \
        "a legacy record at that run_id cannot certify anything, so it is refused too"
    # a *run directory* holding results but no record is the same case: 25 of the 31 run dirs
    # in the harness predate the format, and nothing may be written over them by accident
    assert record.overwrite_refusal(record.legacy_run(), base) is not None, \
        "an eval.json without a record.json is a legacy run, not an empty run_id"


def test_checkpoint_digest_follows_the_file() -> None:
    """The digest helper reads the real bytes: a rewritten file changes it, a missing one is None."""
    with tempfile.TemporaryDirectory() as scratch:
        path = pathlib.Path(scratch) / "model.pt"
        path.write_bytes(b"first")
        first = record.checkpoint_digest(path)
        assert first["sha256"] and first["size"] == 5, f"a readable file must hash: {first}"
        path.write_bytes(b"second")
        assert record.checkpoint_digest(path)["sha256"] != first["sha256"], \
            "different bytes must hash differently"
        assert record.checkpoint_digest(pathlib.Path(scratch) / "absent.pt")["sha256"] is None, \
            "an unreadable checkpoint is None, never a fabricated digest"


def test_record_module_cannot_consume_the_random_stream() -> None:
    """3.2d's offline half: the record module imports no framework and no RNG."""
    source = (_REPO / "ablation_harness" / "record.py").read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    banned = {"torch", "numpy", "random"}
    assert not (imported & banned), f"record.py must not import {sorted(imported & banned)}"
    # `random` can arrive via a stdlib import of the *test* (tempfile), so the module-level
    # claim is checked on the record module's own namespace, and the framework claim on the
    # process: importing record.py must not have pulled torch/numpy in for anyone.
    for name in sorted(banned):
        assert not hasattr(record, name), f"the record module exposes {name}"
    for framework in ("torch", "numpy"):
        assert framework not in sys.modules, f"importing the record module pulled in {framework}"
    for token in ("np.random", "torch.rand", "random."):
        assert token not in source, f"record.py must not reach for {token}"


# --- the table's conditions (Step 3.2d): what may share one scoreboard ---------------------------
#
# The summary is what people read instead of the records, so it is where a row whose ground,
# protocol, judge or assets moved would otherwise sit next to its neighbours as if comparable.


def _twin(**overrides) -> dict:
    """A second record of the same batch, with the named fields replaced."""
    rec = _record()
    rec["run"]["run_id"] = "Lizard-Rough-v14_zero_nominal_seed123"
    for path, value in overrides.items():
        section, _, field = path.partition(".")
        rec[section][field] = value
    return rec


def test_a_scoreboard_may_compare_different_models():
    """The checkpoint is the variable a table compares, so it is not a condition.

    Conditions are deliberately not the binding set: requiring the checkpoint equal would refuse
    every legitimate cross-model table, which is the one thing a scoreboard exists to show.
    """
    a, b = _record(), _twin()
    a["checkpoint"] = {"sha256": "sha256:model-a"}
    b["checkpoint"] = {"sha256": "sha256:model-b"}
    assert record.conditions_conflict(a, b)["conflicts"] == {}, record.conditions_conflict(a, b)
    assert record.compare(a, b)["verdict"] == "not_comparable", "the binding set still separates them"


def test_a_moved_condition_keeps_two_rows_out_of_one_table():
    a, b = _record(), _twin()
    b["eval_protocol"]["digest"] = "sha256:other-protocol"
    assert "eval_protocol.digest" in record.conditions_conflict(a, b)["conflicts"]
    report = record.table_conflicts([a, b])
    assert report["conflicts"][a["run"]["run_id"]]["against"][b["run"]["run_id"]]["eval_protocol.digest"] == {
        "a": "sha256:proto", "b": "sha256:other-protocol"}
    duplicate = _record()
    duplicate["eval_protocol"]["digest"] = "sha256:another-protocol"
    report = record.table_conflicts([b, a, duplicate])
    pairs = report["conflicts"][b["run"]["run_id"]]["against"]
    assert len(pairs) == 2, pairs
    assert {pair["eval_protocol.digest"]["b"] for pair in pairs.values()} == {
        "sha256:proto", "sha256:another-protocol"}, pairs
    incomplete = _record(complete=False)
    legacy = {"run": {"run_id": a["run"]["run_id"]}}
    assert len(record.table_conflicts([incomplete, legacy])["unreadable"]) == 2
    missing = _record(complete=False)
    del missing["run"]["run_id"]
    named = _record(complete=False)
    named["run"]["run_id"] = "row0"
    assert len(record.table_conflicts([missing, named])["unreadable"]) == 2


def test_the_same_protocol_name_is_not_the_same_protocol():
    """An identity can be re-approved under the same name while the layout moves: check both."""
    a, b = _record(), _twin()
    b["obs_protocol"]["identity"] = a["obs_protocol"]["identity"]
    b["obs_protocol"]["digest"] = "sha256:obs-later"
    assert "obs_protocol.digest" in record.conditions_conflict(a, b)["conflicts"]


def test_a_cross_asset_row_is_allowed_only_when_it_says_so():
    a, b = _record(), _twin()
    b["assets"]["declared_digest"] = "sha256:other-assets"
    refused = record.conditions_conflict(a, b)
    assert "assets.declared_digest" in refused["conflicts"], refused
    assert "declared_as" not in refused["conflicts"]["assets.declared_digest"], \
        "an undeclared assets difference is a conflict like any other"
    b["run"]["variant"] = "assets"
    allowed = record.conditions_conflict(a, b)
    assert allowed["conflicts"]["assets.declared_digest"]["declared_as"] == "assets", allowed


def _summary_asset_case(base, candidate, *, variants=True):
    """Exercise the real summary reader with two persisted rows."""
    import csv

    with tempfile.TemporaryDirectory(prefix="summary-assets-") as scratch:
        harness = pathlib.Path(scratch)
        root = harness / "results" / "test-protocol"
        root.mkdir(parents=True)
        fields = ["run_id", "persist_id"] + (["variant"] if variants else [])
        with (root / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for rec, displayed in (base, candidate):
                rec = json.loads(json.dumps(rec))
                ref = (rec.get("substitutions") or {}).get("baseline") or {}
                if ref.get("path") == "__same_group__":
                    ref["path"] = str(root / ref["run_id"] / "record.json")
                run = rec["run"]
                folder = root / run["run_id"]
                folder.mkdir()
                (folder / "record.json").write_text(json.dumps(rec), encoding="utf-8")
                row = {"run_id": run["run_id"], "persist_id": run["persist_id"]}
                if variants:
                    row["variant"] = displayed
                writer.writerow(row)
        output = io.StringIO()
        with _patched(run_ablation, _HARNESS_DIR=harness), contextlib.redirect_stdout(output):
            status = run_ablation._summarize(types.SimpleNamespace(protocol="test-protocol", group=None))
        return status, output.getvalue()


def _asset_rows(variant):
    base, candidate = _ckpt_record("sha256:model"), _ckpt_record("sha256:model")
    base["run"].update(run_id="base", persist_id="a", variant=None, group=None)
    candidate["run"].update(run_id=f"base_{variant}", persist_id="b", variant=variant, group=None)
    candidate["assets"]["declared_digest"] = "sha256:other"
    return base, candidate


def test_summary_asset_declaration_boundaries():
    for variant, allowed in (("assets", True), ("assets-unknown", True),
                             ("assets+suite", True), ("suite+assets-unknown", True),
                             ("suite+assets-note", False), ("not-assets", False), ("myassets", False),
                             ("assetsx", False), ("suite+not-assets", False),
                             ("not-assets+assets", False), ("ckpt3000", False)):
        base, candidate = _asset_rows(variant)
        status, output = _summary_asset_case((base, ""), (candidate, variant))
        assert (status == 0) == allowed, (variant, status, output)
        assert ("declared as assets" in output) == allowed, (variant, output)


def test_summary_rejects_ambiguous_asset_labels():
    for variant in ("no-assets", "without-assets", "non-assets", "foo-assets",
                    "assets-not-replaced", "not-assets+assets"):
        base, candidate = _asset_rows(variant)
        status, output = _summary_asset_case((base, ""), (candidate, variant))
        assert status != 0 and "declared as assets" not in output, (variant, status, output)


def test_summary_baseline_direction_uses_actual_source_paths():
    import csv

    with tempfile.TemporaryDirectory(prefix="summary-direction-") as scratch:
        harness = pathlib.Path(scratch)
        root = harness / "results" / "test-protocol"
        base, candidate = _asset_rows("ckpt3000")
        base["run"].update(run_id="base_assets", variant="assets")
        candidate["run"]["run_id"] = "base_assets_ckpt3000"
        for group, rec in (("a", base), ("b", candidate)):
            folder = root / group / rec["run"]["run_id"]
            folder.mkdir(parents=True)
            with (folder.parent / "summary.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["run_id", "persist_id", "variant"])
                writer.writeheader()
                writer.writerow({key: rec["run"].get(key) or "" for key in writer.fieldnames})
        base_path = root / "a" / "base_assets" / "record.json"
        candidate_path = root / "b" / "base_assets_ckpt3000" / "record.json"
        candidate["substitutions"] = record.substitution_evidence(
            candidate, base, baseline_ref={"run_id": "base_assets", "path": str(base_path)})
        base_path.write_text(json.dumps(base), encoding="utf-8")
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        args = types.SimpleNamespace(protocol="test-protocol", group=None)
        def summarize():
            output = io.StringIO()
            with _patched(run_ablation, _HARNESS_DIR=harness), contextlib.redirect_stdout(output):
                status = run_ablation._summarize(args)
            return status, output.getvalue()
        status, output = summarize()
        assert status == 0 and "unproven" in output and "direction" in output, (status, output)
        # Same group, snapshot actually pointing to that baseline: only candidate label counts.
        target = root / "a" / candidate["run"]["run_id"]
        candidate_path.parent.rename(target)
        (root / "b" / "summary.csv").unlink()
        with (root / "a" / "summary.csv").open("a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=["run_id", "persist_id", "variant"]).writerow(
                {key: candidate["run"].get(key) or "" for key in ("run_id", "persist_id", "variant")})
        status, output = summarize()
        assert status != 0 and "assets.declared_digest" in output, (status, output)
        # A snapshot pointing into another group must not borrow this same-named row.
        candidate["substitutions"]["baseline"]["path"] = str(root / "b" / "base_assets" / "record.json")
        (target / "record.json").write_text(json.dumps(candidate), encoding="utf-8")
        status, output = summarize()
        assert status == 0 and "unproven" in output and "direction" in output, (status, output)
        # A valid candidate label cannot be suppressed by an unrelated cross-group snapshot.
        base["run"]["variant"] = "ckpt3000"
        candidate["run"]["variant"] = "assets"
        candidate["substitutions"] = record.substitution_evidence(
            base, candidate, baseline_ref={"run_id": candidate["run"]["run_id"], "path": str(target / "record.json")})
        base["substitutions"] = candidate.pop("substitutions")
        base["substitutions"]["baseline"]["path"] = str(root / "b" / candidate["run"]["run_id"] / "record.json")
        base_path.write_text(json.dumps(base), encoding="utf-8")
        (target / "record.json").write_text(json.dumps(candidate), encoding="utf-8")
        (root / "a" / "summary.csv").write_text(
            "run_id,persist_id,variant\nbase_assets,a,ckpt3000\nbase_assets_ckpt3000,b,assets\n", encoding="utf-8")
        status, output = summarize()
        assert status == 0 and "unproven" in output and "direction" in output, (status, output)


def test_summary_cross_group_snapshot_does_not_hide_candidate_declaration():
    with tempfile.TemporaryDirectory(prefix="summary-reverse-") as scratch:
        harness = pathlib.Path(scratch)
        root = harness / "results" / "test-protocol"
        base, candidate = _asset_rows("assets")
        base["run"].update(run_id="base", variant="ckpt3000")
        candidate["run"]["run_id"] = "candidate"
        for group, rec in (("a", base), ("b", candidate)):
            folder = root / group / rec["run"]["run_id"]
            folder.mkdir(parents=True)
            (folder.parent / "summary.csv").write_text(
                f"run_id,persist_id,variant\n{rec['run']['run_id']},{rec['run']['persist_id']},"
                f"{rec['run']['variant']}\n", encoding="utf-8")
        base["substitutions"] = record.substitution_evidence(
            base, candidate, baseline_ref={"run_id": "candidate", "path": str(root / "b" / "candidate" / "record.json")})
        for group, rec in (("a", base), ("b", candidate)):
            (root / group / rec["run"]["run_id"] / "record.json").write_text(json.dumps(rec), encoding="utf-8")
        output = io.StringIO()
        with _patched(run_ablation, _HARNESS_DIR=harness), contextlib.redirect_stdout(output):
            status = run_ablation._summarize(types.SimpleNamespace(protocol="test-protocol", group=None))
        assert status == 0 and "declared as assets" in output.getvalue() and "direction" in output.getvalue(), output.getvalue()


def test_summary_real_records_reject_false_asset_declaration():
    root = (_REPO / "ablation_harness" / "results" / "locomotion_eval_v3" / "livecheck")
    base = record.load(root / "Lizard2-Flat-v3_live_nominal_seed123" / "record.json")
    candidate = record.load(root / "Lizard2-Flat-v3_live_nominal_seed123_ckpt3000" / "record.json")
    base["run"]["persist_id"], candidate["run"]["persist_id"] = "a", "b"
    candidate["assets"]["declared_digest"] = "sha256:other"
    candidate["run"]["variant"] = "not-assets"
    candidate["substitutions"] = record.substitution_evidence(
        candidate, base, baseline_ref={"run_id": base["run"]["run_id"], "path": "original/record.json"})
    status, output = _summary_asset_case((base, ""), (candidate, "not-assets"))
    assert status != 0 and "assets.declared_digest" in output and "declared as assets" not in output, output
    candidate["run"]["variant"] = "assets"
    status, output = _summary_asset_case((base, ""), (candidate, "assets"))
    assert status == 0 and "declared as assets" in output, output


def test_summary_preserves_historical_asset_label():
    path = (_REPO / "ablation_harness" / "results" / "locomotion_eval_v2" / "dev" /
            "Lizard-Velocity-Rough_devnolock_nominal_seed123_assets-unknown" / "record.json")
    historical = record.load(path)
    assert historical["run"]["variant"] == "assets-unknown"
    assert historical["assets"]["declared_digest"] == record.UNKNOWN
    # Historical unknown assets cannot prove a swap; use the actual label on complete temporary rows.
    base, candidate = _asset_rows(historical["run"]["variant"])
    status, output = _summary_asset_case((base, ""), (candidate, historical["run"]["variant"]))
    assert status == 0 and "declared as assets" in output, (status, output)
    candidate["assets"]["declared_digest"] = record.UNKNOWN
    status, output = _summary_asset_case((base, ""), (candidate, historical["run"]["variant"]))
    assert status != 0 and "unproven" in output, (status, output)


def test_summary_requires_variant_column_to_match_record():
    base, candidate = _asset_rows("assets")
    status, output = _summary_asset_case((base, ""), (candidate, "not-assets"))
    assert status != 0 and "variant" in output, (status, output)
    status, output = _summary_asset_case((base, ""), (candidate, ""), variants=False)
    assert status == 0, (status, output)


def test_summary_requires_identifiable_candidate_to_declare():
    base, candidate = _asset_rows("ckpt3000")
    # A prior variant can itself be the base identity of a different tag. The candidate's
    # write-time baseline reference identifies the direction, not record list order.
    base["run"].update(run_id="base_assets", variant="assets")
    candidate["run"]["run_id"] = "base_assets_ckpt3000"
    candidate["substitutions"] = record.substitution_evidence(
        candidate, base, baseline_ref={"run_id": "base_assets", "path": "__same_group__"})
    for rows in (((base, "assets"), (candidate, "ckpt3000")),
                 ((candidate, "ckpt3000"), (base, "assets"))):
        status, output = _summary_asset_case(*rows)
        assert status != 0 and "assets.declared_digest" in output, (status, output)
    # The physical source path, not optional run.group metadata, identifies the group.
    candidate["run"]["group"] = "different-group"
    status, output = _summary_asset_case((base, "assets"), (candidate, "ckpt3000"))
    assert status != 0, (status, output)
    candidate["run"]["group"] = None
    candidate["substitutions"]["bindings"]["assets.declared_digest"]["baseline"] = "old-digest"
    status, output = _summary_asset_case((base, "assets"), (candidate, "ckpt3000"))
    assert status == 0, (status, output)  # the baseline was replaced after the snapshot
    candidate["run"].update(run_id="base_assets_assets", variant="assets")
    candidate["substitutions"] = record.substitution_evidence(
        candidate, base, baseline_ref={"run_id": "base_assets", "path": "__same_group__"})
    status, output = _summary_asset_case((base, "assets"), (candidate, "assets"))
    assert status == 0, (status, output)


def test_summary_asset_owner_unknown_keeps_existing_symmetric_behavior():
    a, b = _asset_rows("assets")
    b["run"]["run_id"] = "unrelated_assets"
    for rows in (((a, ""), (b, "assets")), ((b, "assets"), (a, ""))):
        status, output = _summary_asset_case(*rows)
        assert status == 0, (status, output)


def test_an_absent_fact_is_unproven_and_an_unreadable_row_is_named():
    a, b = _record(), _twin()
    a["judge"] = {"id": record.UNKNOWN}
    b["judge"] = {"id": record.UNKNOWN}
    found = record.conditions_conflict(a, b)
    assert found["conflicts"] == {} and found["unproven"] == ["judge.id"], found
    incomplete = _record(complete=False)
    incomplete["run"]["run_id"] = "incomplete"
    report = record.table_conflicts([_record(), incomplete])
    assert "incomplete" in report["unreadable"] and not report["conflicts"], report


def _assert_missing_identity_refused(field):
    # Delete only this identity from both rows; the other identity remains present.
    with tempfile.TemporaryDirectory(prefix="missing-identity-") as scratch:
        harness = pathlib.Path(scratch)
        root = harness / "results" / "test-protocol"
        for group in ("a", "b"):
            rec = _ckpt_record("sha256:model")
            rec["run"].update(run_id="run", persist_id=group)
            section, key = field.split(".")
            del rec[section][key]
            folder = root / group / "run"
            folder.mkdir(parents=True)
            (folder / "record.json").write_text(json.dumps(rec), encoding="utf-8")
            (folder.parent / "summary.csv").write_text(f"run_id,persist_id\nrun,{group}\n", encoding="utf-8")
        output = io.StringIO()
        with _patched(run_ablation, _HARNESS_DIR=harness), contextlib.redirect_stdout(output):
            status = run_ablation._summarize(types.SimpleNamespace(protocol="test-protocol", group=None))
        assert status != 0 and field in output.getvalue(), (field, status, output.getvalue())


def test_missing_geometry_identity_alone_refuses_summary():
    _assert_missing_identity_refused("suite.geometry_digest")


def test_missing_judge_identity_alone_refuses_summary():
    _assert_missing_identity_refused("judge.id")


def test_missing_identity_evidence_is_unproven_and_summary_refuses():
    a, b = _ckpt_record("sha256:model"), _ckpt_record("sha256:model")
    for rec in (a, b):
        del rec["suite"]["geometry_digest"]
        del rec["judge"]
        rec["suite"]["num_rows"] = 1
        rec["suite"]["num_cols"] = 9
        rec["suite"]["envs_per_terrain"] = 8
        rec["suite"]["terrains"] = ["flat"]
    assert record.read_state(a)["state"] == record.read_state(b)["state"] == "complete"
    for field in ("suite.geometry_digest", "judge.id"):
        assert field in record.conditions_conflict(a, b)["unproven"]
    b["suite"]["geometry_digest"] = record.UNKNOWN
    assert "suite.geometry_digest" in record.conditions_conflict(a, b)["unproven"]
    del b["suite"]["geometry_digest"]
    b["suite"]["geometry_digest"] = "sha256:geometry"
    assert "suite.geometry_digest" in record.conditions_conflict(a, b)["unproven"]
    del b["suite"]["geometry_digest"]
    for rec in (a, b):
        for field in ("num_rows", "num_cols", "envs_per_terrain", "terrains"):
            del rec["suite"][field]
    assert set(record.conditions_conflict(a, b)["unproven"]) == {"suite.geometry_digest", "judge.id"}
    with tempfile.TemporaryDirectory(prefix="missing-identities-") as scratch:
        harness = pathlib.Path(scratch)
        root = harness / "results" / "test-protocol"
        for group, rec in (("a", a), ("b", b)):
            rec["run"].update(run_id="run", persist_id=group)
            folder = root / group / "run"
            folder.mkdir(parents=True)
            (folder / "record.json").write_text(json.dumps(rec), encoding="utf-8")
            (folder.parent / "summary.csv").write_text(f"run_id,persist_id\nrun,{group}\n", encoding="utf-8")
        output = io.StringIO()
        with _patched(run_ablation, _HARNESS_DIR=harness), contextlib.redirect_stdout(output):
            status = run_ablation._summarize(types.SimpleNamespace(protocol="test-protocol", group=None))
        assert status != 0 and "suite.geometry_digest" in output.getvalue() and "judge.id" in output.getvalue(), output.getvalue()
        b["suite"]["geometry_digest"] = record.UNKNOWN
        b["judge"] = {"id": record.UNKNOWN}
        (root / "b" / "run" / "record.json").write_text(json.dumps(b), encoding="utf-8")
        output = io.StringIO()
        with _patched(run_ablation, _HARNESS_DIR=harness), contextlib.redirect_stdout(output):
            status = run_ablation._summarize(types.SimpleNamespace(protocol="test-protocol", group=None))
        assert status != 0 and "unproven" in output.getvalue(), output.getvalue()
        a["suite"]["geometry_digest"] = record.UNKNOWN
        a["judge"] = {"id": record.UNKNOWN}
        (root / "a" / "run" / "record.json").write_text(json.dumps(a), encoding="utf-8")
        output = io.StringIO()
        with _patched(run_ablation, _HARNESS_DIR=harness), contextlib.redirect_stdout(output):
            status = run_ablation._summarize(types.SimpleNamespace(protocol="test-protocol", group=None))
        assert status == 0 and "unproven" in output.getvalue(), output.getvalue()


def test_terrain_pivot_refuses_duplicate_sources_but_keeps_csv_rows():
    import csv

    with tempfile.TemporaryDirectory(prefix="terrain-collision-") as scratch:
        harness = pathlib.Path(scratch)
        root = harness / "results" / "test-protocol"
        payload = {"protocol": "test-protocol", "task": "task", "mode": "nominal", "seed": 123,
                   "checkpoint": "model_1.pt", "terrains": {"flat": {"completion": 0.2,
                   "fall_rate": 0.3, "success_rate": 0.4}}}
        for group, run, value in (("a", "same", 0.2), ("b", "same", 0.8), ("a", "other", 0.6)):
            folder = root / group / run
            folder.mkdir(parents=True)
            payload["terrains"]["flat"]["completion"] = value
            (folder / "eval.json").write_text(json.dumps(payload), encoding="utf-8")
        with _patched(run_ablation, _HARNESS_DIR=harness):
            for group, expected in ((None, 3), ("a", 2)):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    status = run_ablation._by_terrain(types.SimpleNamespace(protocol="test-protocol", group=group))
                assert status == 1 and "terrain pivot collision" in output.getvalue(), output.getvalue()
                with (root / (group or "") / "terrains.csv").open(encoding="utf-8", newline="") as f:
                    rows = list(csv.DictReader(f))
                assert len(rows) == expected and len({r["completion"] for r in rows}) == expected, rows
                expected_sources = {"a/same/eval.json": "0.2", "a/other/eval.json": "0.6"}
                if group is None:
                    expected_sources["b/same/eval.json"] = "0.8"
                assert {r["source"]: r["completion"] for r in rows} == expected_sources, rows
                assert all(r["run_id"] == r["source"].split("/")[-2] for r in rows), rows
                assert list(rows[0]) == ["run_id", "protocol", "task", "mode", "seed", "iteration",
                                         "terrain", "completion", "fall_rate", "success_rate", "source"]
                assert all(r["protocol"] == "test-protocol" and r["task"] == "task" and
                           r["mode"] == "nominal" and r["seed"] == "123" and r["iteration"] == "1" and
                           r["terrain"] == "flat" and r["fall_rate"] == "0.3" and r["success_rate"] == "0.4"
                           for r in rows), rows
            args = types.SimpleNamespace(protocol="test-protocol", group="b")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                assert run_ablation._by_terrain(args) == 0
            assert "0.80" in output.getvalue(), output.getvalue()
            folder = root / "root-run"
            folder.mkdir()
            (folder / "eval.json").write_text(json.dumps(payload), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                assert run_ablation._by_terrain(types.SimpleNamespace(protocol="test-protocol", group=None)) == 1
            with (root / "terrains.csv").open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            assert any(r["run_id"] == "root-run" and r["source"] == "root-run/eval.json" for r in rows), rows
        rows = run_ablation._collect_terrain_rows(root, "b")
        try:
            run_ablation._terrain_pivot(rows + rows, "completion")
        except ValueError as exc:
            assert "terrain pivot collision" in str(exc)
        else:
            assert False, "duplicate cells from one source must not overwrite"


def test_summary_checks_conditions_across_groups():
    with tempfile.TemporaryDirectory(prefix="summary-groups-") as scratch:
        harness = pathlib.Path(scratch)
        root = harness / "results" / "test-protocol"
        for group, digest in (("a", "sha256:first"), ("b", "sha256:second")):
            run = root / group / "same-run"
            run.mkdir(parents=True)
            rec = _ckpt_record("sha256:model")
            rec["run"].update(run_id="same-run", persist_id=group)
            rec["suite"]["digest"] = digest
            assert record.read_state(rec)["state"] == "complete"
            (run / "record.json").write_text(json.dumps(rec), encoding="utf-8")
            (run.parent / "summary.csv").write_text(f"run_id,persist_id\nsame-run,{group}\n", encoding="utf-8")
        args = types.SimpleNamespace(protocol="test-protocol", group=None)
        with _patched(run_ablation, _HARNESS_DIR=harness):
            assert run_ablation._summarize(args) != 0, "cross-group suite differences must be refused"
            args.group = "a"
            assert run_ablation._summarize(args) == 0, "one group without conflicts must pass"
            args.group = None
            other = root / "b" / "same-run" / "record.json"
            rec = json.loads(other.read_text(encoding="utf-8"))
            rec["suite"]["digest"] = "sha256:first"
            other.write_text(json.dumps(rec), encoding="utf-8")
            assert run_ablation._summarize(args) == 0, "matching groups must pass"
            rec["suite"]["digest"] = "sha256:second"
            rec["assets"]["declared_digest"] = "sha256:other"
            rec["run"]["variant"] = "assets"
            other.write_text(json.dumps(rec), encoding="utf-8")
            assert run_ablation._summarize(args) != 0, "declared assets must not hide a suite conflict"
            rec["suite"]["digest"] = "sha256:first"
            other.write_text(json.dumps(rec), encoding="utf-8")
            assert run_ablation._summarize(args) == 0, "declared assets remain allowed"
            del rec["suite"]["digest"]
            other.write_text(json.dumps(rec), encoding="utf-8")
            assert run_ablation._summarize(args) != 0, "incomplete records must not be certified"


def test_summary_reads_each_record_once_and_consistently_reports_conditions():
    from unittest.mock import patch

    with tempfile.TemporaryDirectory(prefix="summary-conditions-") as scratch:
        harness = pathlib.Path(scratch)
        root = harness / "results" / "test-protocol"
        a, b = _ckpt_record("sha256:model"), _ckpt_record("sha256:model")
        a["run"].update(run_id="first", persist_id="a")
        b["run"].update(run_id="second", persist_id="b")
        files = []
        for group, rec in (("", a), ("group", b)):
            folder = root / group
            folder.mkdir(parents=True, exist_ok=True)
            (folder / rec["run"]["run_id"]).mkdir()
            path = folder / rec["run"]["run_id"] / "record.json"
            path.write_text(json.dumps(rec), encoding="utf-8")
            extra_header = ",success_rate" if group else ""
            extra_value = ",0.73" if group else ""
            (folder / "summary.csv").write_text(
                f"run_id,persist_id{extra_header}\n{rec['run']['run_id']},{rec['run']['persist_id']}{extra_value}\n",
                encoding="utf-8")
            files.append(path)
        args = types.SimpleNamespace(protocol="test-protocol", group=None)
        def run():
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = run_ablation._summarize(args)
            return result, output.getvalue()
        with _patched(run_ablation, _HARNESS_DIR=harness):
            original_load = record.load
            counts = {}
            def load_once(path):
                counts[path] = counts.get(path, 0) + 1
                assert counts[path] == 1, f"record read more than once: {path}"
                return original_load(path)
            with patch.object(record, "load", side_effect=load_once):
                status, output = run()
                assert status == 0 and "success_rate" in output and "0.73" in output, output
            def broken(path):
                if path == files[0]:
                    raise OSError("injected read failure")
                return original_load(path)
            with patch.object(record, "load", side_effect=broken):
                status, output = run()
                assert status != 0 and "first" in output
            b["judge"] = {"id": record.UNKNOWN}
            a["judge"] = {"id": record.UNKNOWN}
            files[0].write_text(json.dumps(a), encoding="utf-8")
            files[1].write_text(json.dumps(b), encoding="utf-8")
            status, output = run()
            assert status == 0 and "unproven" in output and "judge.id" in output
            assert "source" in output and "group" in output
            b["judge"]["id"] = "known"
            files[1].write_text(json.dumps(b), encoding="utf-8")
            status, output = run()
            assert status != 0 and "judge.id" in output
            a["suite"]["num_rows"] = 1
            b["suite"]["num_rows"] = True
            files[0].write_text(json.dumps(a), encoding="utf-8")
            files[1].write_text(json.dumps(b), encoding="utf-8")
            status, output = run()
            assert status != 0 and "suite.num_rows" in output, output
            del a["suite"]["num_rows"]
            del b["suite"]["num_rows"]
            files[0].write_text(json.dumps(a), encoding="utf-8")
            b["judge"]["id"] = record.UNKNOWN
            b["assets"]["declared_digest"] = "sha256:other"
            b["run"]["variant"] = "assets"
            files[1].write_text(json.dumps(b), encoding="utf-8")
            status, output = run()
            assert status == 0 and "unproven" in output and "declared as assets" in output
            (root / "group" / "summary.csv").unlink()
            (root / "summary.csv").write_text("run_id,persist_id\nfirst,a\nsecond,b\n", encoding="utf-8")
            (root / "second").mkdir()
            (root / "second" / "record.json").write_text(json.dumps(b), encoding="utf-8")
            status, output = run()
            assert status == 0 and "unproven" in output and "declared as assets" in output
            a["assets"]["declared_digest"] = record.UNKNOWN
            b["assets"]["declared_digest"] = record.UNKNOWN
            (root / "first" / "record.json").write_text(json.dumps(a), encoding="utf-8")
            (root / "second" / "record.json").write_text(json.dumps(b), encoding="utf-8")
            status, output = run()
            assert status == 0 and "assets.declared_digest" in output and "unproven" in output
            b["assets"]["declared_digest"] = "sha256:other"
            (root / "second" / "record.json").write_text(json.dumps(b), encoding="utf-8")
            status, output = run()
            assert status != 0 and "assets.declared_digest" in output and "unproven" in output


def test_summary_rejects_corrupt_inputs():
    with tempfile.TemporaryDirectory(prefix="summary-corrupt-") as scratch:
        harness = pathlib.Path(scratch)
        folder = harness / "results" / "test-protocol"
        folder.mkdir(parents=True)
        summary = folder / "summary.csv"
        run = folder / "run"
        run.mkdir()
        record_path = run / "record.json"
        rec = _ckpt_record("sha256:model")
        rec["run"].update(run_id="run", persist_id="generation")
        record_path.write_text(json.dumps(rec), encoding="utf-8")
        args = types.SimpleNamespace(protocol="test-protocol", group=None)
        with _patched(run_ablation, _HARNESS_DIR=harness):
            for content in (b"", b"task\nrun\n", b"run_id,mode\nrun\n", b"run_id\nrun,extra\n",
                            b"run_id\n\xff\n", b"run_id,run_id\nrun,run\n", b"run_id\nrun\nrun\n",
                            b"run_id\n../run\n", b"run_id\nC:\\run\n", b"run_id\n.\n"):
                summary.write_bytes(content)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = run_ablation._summarize(args)
                assert result != 0 and "summary.csv" in output.getvalue(), (content, result, output.getvalue())
            summary.write_text("run_id,persist_id\nrun,generation\n", encoding="utf-8")
            record_path.write_bytes(b"\xff")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = run_ablation._summarize(args)
            assert result != 0 and "record.json" in output.getvalue(), output.getvalue()
            record_path.write_text(json.dumps(rec), encoding="utf-8")
            assert run_ablation._summarize(args) == 0
            summary.write_text("run_id\n", encoding="utf-8")
            assert run_ablation._summarize(args) == 0, "valid header without rows is empty, not corrupt"
            summary.write_text("run_id,persist_id\nrun,generation\n", encoding="utf-8")
            rec["suite"]["digest"] = 123
            record_path.write_text(json.dumps(rec), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = run_ablation._summarize(args)
            assert status != 0 and "suite.digest" in output.getvalue(), output.getvalue()
            summary.write_text("run_id\n", encoding="utf-8")
            (folder / ".summary-write.lock").write_text("active or stale", encoding="utf-8")
            assert run_ablation._summarize(args) != 0, "a locked empty table is not certified"
            (folder / ".summary-write.lock").unlink()
            new_group = folder / "new-group"
            new_group.mkdir()
            (new_group / ".summary-write.lock").write_text("active or stale", encoding="utf-8")
            assert run_ablation._summarize(args) != 0, "a new group's lock must be discovered without a summary"


def test_summary_rejects_invalid_terrain_names():
    with tempfile.TemporaryDirectory(prefix="summary-terrains-") as scratch:
        harness = pathlib.Path(scratch)
        folder = harness / "results" / "test-protocol"
        run = folder / "run"
        run.mkdir(parents=True)
        rec = _ckpt_record("sha256:model")
        rec["run"].update(run_id="run", persist_id="generation")
        (folder / "summary.csv").write_text("run_id,persist_id\nrun,generation\n", encoding="utf-8")
        args = types.SimpleNamespace(protocol="test-protocol", group=None)
        with _patched(run_ablation, _HARNESS_DIR=harness):
            for value, expected in ((["flat", "stairs"], 0), (record.UNKNOWN, 0),
                                    ([1], 1), ([True], 1), (["flat", 1], 1), (["flat", True], 1),
                                    (["flat", ""], 1), ("flat", 1), (None, 1)):
                rec["suite"]["terrains"] = value
                (run / "record.json").write_text(json.dumps(rec), encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    status = run_ablation._summarize(args)
                assert (status != 0) == bool(expected), (value, status, output.getvalue())
                if expected:
                    assert "suite.terrains" in output.getvalue(), output.getvalue()
            del rec["suite"]["terrains"]
            (run / "record.json").write_text(json.dumps(rec), encoding="utf-8")
            assert run_ablation._summarize(args) == 0


def test_summary_rejects_mismatched_record_generation():
    with tempfile.TemporaryDirectory(prefix="summary-generation-") as scratch:
        harness = pathlib.Path(scratch)
        folder = harness / "results" / "test-protocol"
        run = folder / "run"
        run.mkdir(parents=True)
        rec = _ckpt_record("sha256:model")
        rec["run"].update(run_id="run", persist_id="second")
        (run / "record.json").write_text(json.dumps(rec), encoding="utf-8")
        summary = folder / "summary.csv"
        args = types.SimpleNamespace(protocol="test-protocol", group=None)
        with _patched(run_ablation, _HARNESS_DIR=harness):
            for expected, actual in (("first", "second"), ("first", ""), ("", "second")):
                summary.write_text(f"run_id,persist_id\nrun,{expected}\n", encoding="utf-8")
                rec["run"]["persist_id"] = actual
                (run / "record.json").write_text(json.dumps(rec), encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = run_ablation._summarize(args)
                assert result != 0 and "persist_id" in output.getvalue(), output.getvalue()
            rec["run"]["persist_id"] = "first"
            (run / "record.json").write_text(json.dumps(rec), encoding="utf-8")
            summary.write_text("run_id,persist_id\nrun,first\n", encoding="utf-8")
            assert run_ablation._summarize(args) == 0
            del rec["run"]["persist_id"]
            (run / "record.json").write_text(json.dumps(rec), encoding="utf-8")
            summary.write_text("run_id\nrun\n", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = run_ablation._summarize(args)
            assert result != 0 and "generation unverified" in output.getvalue()


def test_lock_metadata_failure_closes_descriptor_and_releases_lock():
    import os
    from unittest.mock import patch

    tree = ast.parse((_REPO / "ablation_harness" / "eval.py").read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_persist"]
    namespace = {"pathlib": pathlib, "os": os, "uuid": __import__("uuid")}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "eval.py", "exec"), namespace)
    with tempfile.TemporaryDirectory(prefix="lock-metadata-") as scratch:
        harness = pathlib.Path(scratch)
        protocol = harness / "results" / "test-protocol"
        protocol.mkdir(parents=True)
        namespace.update(_RESULTS_ROOT=harness / "results", _run_dir=lambda run_id: protocol / run_id,
                         args_cli=types.SimpleNamespace(protocol="test-protocol"))
        result = {"timestamp": "test"}
        rec = _record()
        args = types.SimpleNamespace(protocol="test-protocol", group=None)
        original_open = os.open
        opened = []
        def capture_open(*args, **kwargs):
            fd = original_open(*args, **kwargs)
            opened.append(fd)
            return fd
        def failed_metadata(*args, **kwargs):
            raise OSError("injected metadata failure")
        with _patched(run_ablation, _HARNESS_DIR=harness):
            for call in (lambda: namespace["_persist"](result, [], None, "run", "tag", rec),
                         lambda: run_ablation._summarize(args)):
                opened.clear()
                try:
                    with patch.object(os, "open", side_effect=capture_open), patch.object(os, "fdopen", side_effect=failed_metadata):
                        try:
                            call()
                        except OSError as exc:
                            assert str(exc) == "injected metadata failure", str(exc)
                        else:
                            assert False, "metadata failure must abort"
                    assert len(opened) == 1
                    try:
                        os.fstat(opened[0])
                    except OSError:
                        pass
                    else:
                        assert False, "metadata failure leaked its descriptor"
                    assert not (protocol / ".summary-write.lock").exists()
                    assert not (protocol / "run").exists()
                finally:
                    for fd in opened:
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                    (protocol / ".summary-write.lock").unlink(missing_ok=True)


def test_persist_binds_each_summary_row_to_its_write():
    import ast
    import csv

    source = (_REPO / "ablation_harness" / "eval.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    selected = [node for node in tree.body if
                isinstance(node, ast.FunctionDef) and node.name in ("_atomic_write_json", "_persist")]
    assert len(selected) == 2
    namespace = {"pathlib": pathlib, "json": json, "csv": csv, "os": __import__("os"),
                 "uuid": __import__("uuid"), "record": record,
                 "_SUMMARY_COLUMNS": ["run_id", "protocol", "task", "tag", "mode", "seed", "variant",
                                      "git_rev_lizard", "git_rev_isaaclab", "timestamp", "persist_id",
                                      "success_rate", "fall_rate", "lin_mae_mps", "ang_mae_radps",
                                      "energy_per_m_j", "stop_overshoot_mps", "recovery_mean_s", "never_recovered"],
                 "_round": lambda x: round(x, 4), "_guard_writes": lambda *args: None,
                 "args_cli": types.SimpleNamespace(task="task", mode="nominal", seed=123, variant=None, protocol="test-protocol")}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "eval.py", "exec"), namespace)
    with tempfile.TemporaryDirectory(prefix="persist-generation-") as scratch:
        root = pathlib.Path(scratch)
        namespace["_RESULTS_ROOT"] = root.parent
        namespace["args_cli"].protocol = root.name
        namespace["_run_dir"] = lambda run_id: root / run_id
        result = {"timestamp": "same-second", "protocol": "test", "global": {
            "success_rate": 1, "fall_rate": 0, "lin_mae_mps": 0, "ang_mae_radps": 0, "energy_per_m_j": 0}}
        rec = _ckpt_record("sha256:model")
        namespace["_persist"](result, [], None, "run", "tag", rec)
        first = rec["run"]["persist_id"]
        with (root / "summary.csv").open(encoding="utf-8", newline="") as f:
            assert list(csv.DictReader(f))[0]["persist_id"] == first
        namespace["_persist"](result, [], None, "run", "tag", rec)
        with (root / "summary.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1 and rows[0]["persist_id"] == rec["run"]["persist_id"] != first
        assert json.loads((root / "run" / "record.json").read_text(encoding="utf-8"))["run"]["persist_id"] == rows[0]["persist_id"]
        original_write = namespace["_atomic_write_json"]
        def interrupted(path, payload):
            if path.name == "eval.json":
                raise OSError("injected interruption")
            original_write(path, payload)
        namespace["_atomic_write_json"] = interrupted
        try:
            namespace["_persist"](result, [], None, "run", "tag", rec)
            assert False, "interruption must abort persistence"
        except OSError as exc:
            assert str(exc) == "injected interruption"
        harness = root / "harness"
        protocol_dir = harness / "results" / "test-protocol"
        protocol_dir.mkdir(parents=True)
        assert (root / ".summary-write.lock").is_file(), "failed writes retain the lock for inspection"
        (root / "run").rename(protocol_dir / "run")
        (root / "summary.csv").rename(protocol_dir / "summary.csv")
        (root / ".summary-write.lock").rename(protocol_dir / ".summary-write.lock")
        output = io.StringIO()
        with _patched(run_ablation, _HARNESS_DIR=harness), contextlib.redirect_stdout(output):
            status = run_ablation._summarize(types.SimpleNamespace(protocol="test-protocol", group=None))
        assert status != 0 and ".summary-write.lock" in output.getvalue(), output.getvalue()
        (protocol_dir / ".summary-write.lock").unlink()
        output = io.StringIO()
        with _patched(run_ablation, _HARNESS_DIR=harness), contextlib.redirect_stdout(output):
            status = run_ablation._summarize(types.SimpleNamespace(protocol="test-protocol", group=None))
        assert status != 0 and "persist_id" in output.getvalue(), output.getvalue()


def test_persist_refuses_second_writer_without_losing_rows():
    import ast
    import csv
    import threading

    tree = ast.parse((_REPO / "ablation_harness" / "eval.py").read_text(encoding="utf-8"))
    selected = [node for node in tree.body if
                isinstance(node, ast.FunctionDef) and node.name in ("_atomic_write_json", "_persist")]
    namespace = {"pathlib": pathlib, "json": json, "csv": csv, "os": __import__("os"),
                 "uuid": __import__("uuid"), "record": record,
                 "_SUMMARY_COLUMNS": ["run_id", "protocol", "task", "tag", "mode", "seed", "variant",
                                      "git_rev_lizard", "git_rev_isaaclab", "timestamp", "persist_id",
                                      "success_rate", "fall_rate", "lin_mae_mps", "ang_mae_radps",
                                      "energy_per_m_j", "stop_overshoot_mps", "recovery_mean_s", "never_recovered"],
                 "_round": lambda x: round(x, 4), "_guard_writes": lambda *args: None,
                 "args_cli": types.SimpleNamespace(task="task", mode="nominal", seed=123, variant=None, protocol="test-protocol")}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "eval.py", "exec"), namespace)
    with tempfile.TemporaryDirectory(prefix="persist-writers-") as scratch:
        root = pathlib.Path(scratch)
        namespace["_RESULTS_ROOT"] = root.parent
        namespace["args_cli"].protocol = root.name
        namespace["_run_dir"] = lambda run_id: root / run_id
        result = {"timestamp": "same-second", "protocol": "test", "global": {
            "success_rate": 1, "fall_rate": 0, "lin_mae_mps": 0, "ang_mae_radps": 0, "energy_per_m_j": 0}}
        entered, release = threading.Event(), threading.Event()
        original_write = namespace["_atomic_write_json"]
        def paused(path, payload):
            if path.parent.name == "first" and path.name == "record.json":
                entered.set()
                assert release.wait(5), "test timed out waiting for second writer"
            original_write(path, payload)
        namespace["_atomic_write_json"] = paused
        errors = []
        def writer():
            try:
                namespace["_persist"](result.copy(), [], None, "first", "tag", _ckpt_record("sha256:model"))
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=writer)
        thread.start()
        try:
            assert entered.wait(5)
            try:
                namespace["_persist"](result.copy(), [], None, "second", "tag", _ckpt_record("sha256:model"))
            except (OSError, SystemExit):
                refused = True
            else:
                refused = False
            assert refused, "a concurrent writer must be refused before touching any run files"
            assert not (root / "second" / "record.json").exists()
            with _patched(run_ablation, _HARNESS_DIR=root.parent):
                with __import__("unittest.mock", fromlist=["patch"]).patch.object(
                        run_ablation, "_summary_paths", return_value=[root / "summary.csv"]):
                    assert run_ablation._summarize_locked(types.SimpleNamespace(protocol="test-protocol", group=None)) != 0
        finally:
            release.set()
            thread.join(5)
        assert not thread.is_alive() and not errors, errors
        namespace["_atomic_write_json"] = original_write
        namespace["_persist"](result.copy(), [], None, "second", "tag", _ckpt_record("sha256:model"))
        with (root / "summary.csv").open(encoding="utf-8", newline="") as f:
            assert {row["run_id"] for row in csv.DictReader(f)} == {"first", "second"}


def test_summary_blocks_concurrent_writer_and_new_group():
    from unittest.mock import patch
    import os
    import csv

    tree = ast.parse((_REPO / "ablation_harness" / "eval.py").read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ("_atomic_write_json", "_persist")]
    columns = next(node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "_SUMMARY_COLUMNS" for t in node.targets))
    namespace = {"pathlib": pathlib, "json": json, "csv": csv, "os": os,
                 "uuid": __import__("uuid"), "record": record,
                 "_round": lambda x: round(x, 4), "_guard_writes": lambda *args: None,
                 "args_cli": types.SimpleNamespace(task="task", mode="nominal", seed=123, variant=None,
                                                   protocol="test-protocol")}
    exec(compile(ast.Module(body=[columns, *selected], type_ignores=[]), "eval.py", "exec"), namespace)
    with tempfile.TemporaryDirectory(prefix="summary-snapshot-") as scratch:
        harness = pathlib.Path(scratch)
        protocol = harness / "results" / "test-protocol"
        run = protocol / "first"
        run.mkdir(parents=True)
        rec = _ckpt_record("sha256:model")
        rec["run"].update(run_id="first", persist_id="first-id")
        (run / "record.json").write_text(json.dumps(rec), encoding="utf-8")
        (protocol / "summary.csv").write_text("run_id,persist_id\nfirst,first-id\n", encoding="utf-8")
        original_load = record.load
        attempted = []
        namespace["_RESULTS_ROOT"] = harness / "results"
        namespace["_run_dir"] = lambda run_id: protocol / "new-group" / run_id
        result = {"timestamp": "test", "protocol": "test", "global": {
            "success_rate": 1, "fall_rate": 0, "lin_mae_mps": 0, "ang_mae_radps": 0, "energy_per_m_j": 0}}
        def during_read(path):
            try:
                namespace["_persist"](result.copy(), [], None, "second", "tag", _ckpt_record("sha256:model"))
            except SystemExit:
                attempted.append("blocked")
            else:
                attempted.append("wrote")
            return original_load(path)
        args = types.SimpleNamespace(protocol="test-protocol", group=None)
        with _patched(run_ablation, _HARNESS_DIR=harness), patch.object(record, "load", side_effect=during_read):
            status = run_ablation._summarize(args)
        assert attempted == ["blocked"] and status == 0, (attempted, status)
        assert not (protocol / "new-group" / "second" / "record.json").exists()


def test_persist_refuses_corrupt_existing_summary_before_writing():
    import csv

    tree = ast.parse((_REPO / "ablation_harness" / "eval.py").read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ("_atomic_write_json", "_persist")]
    columns = next(node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "_SUMMARY_COLUMNS" for t in node.targets))
    namespace = {"pathlib": pathlib, "json": json, "csv": csv, "os": __import__("os"),
                 "uuid": __import__("uuid"), "record": record,
                 "_round": lambda x: round(x, 4), "_guard_writes": lambda *args: None,
                 "args_cli": types.SimpleNamespace(task="task", mode="nominal", seed=123, variant=None, protocol="test-protocol")}
    exec(compile(ast.Module(body=[columns, *selected], type_ignores=[]), "eval.py", "exec"), namespace)
    with tempfile.TemporaryDirectory(prefix="persist-corrupt-") as scratch:
        root = pathlib.Path(scratch)
        namespace["_RESULTS_ROOT"] = root.parent
        namespace["args_cli"].protocol = root.name
        namespace["_run_dir"] = lambda run_id: root / run_id
        result = {"timestamp": "test", "protocol": "test", "global": {
            "success_rate": 1, "fall_rate": 0, "lin_mae_mps": 0, "ang_mae_radps": 0, "energy_per_m_j": 0}}
        summary = root / "summary.csv"
        legacy_lock = root / "legacy-group" / ".summary-write.lock"
        legacy_lock.parent.mkdir()
        legacy_lock.write_text("legacy writer or recovery", encoding="utf-8")
        summary.write_text("run_id\n", encoding="utf-8")
        try:
            namespace["_persist"](result.copy(), [], None, "new-run", "tag", _ckpt_record("sha256:model"))
        except (ValueError, OSError, SystemExit):
            pass
        else:
            assert False, "legacy group lock must block writes"
        assert not (root / "new-run" / "record.json").exists()
        assert legacy_lock.is_file() and not (root / ".summary-write.lock").exists()
        legacy_lock.unlink()
        for content in (b"run_id,persist_id\nlost\n", b"run_id,run_id\nlost,lost\n",
                        b"run_id\nlost,extra\n", b"run_id\n\xff\n", b"run_id\nold\nold\n"):
            summary.write_bytes(content)
            try:
                namespace["_persist"](result.copy(), [], None, "new-run", "tag", _ckpt_record("sha256:model"))
            except (ValueError, OSError, SystemExit):
                pass
            else:
                assert False, f"corrupt summary was accepted: {content!r}"
            assert summary.read_bytes() == content
            assert not (root / "new-run" / "record.json").exists(), "existing data must be validated first"
            assert not (root / ".summary-write.lock").exists()


def test_a_diagnostic_row_cannot_sit_in_a_scores_table():
    """``--group`` decides where a row lands, never what it is (work/active/diagnostic-run-gate.md).

    Four cases, because the refusal has to be narrower than "any row I dislike": a zero-action row
    in a scores table is refused with its kind named; the same row under the smoke group is allowed
    (that table is a diagnostic one on purpose); a scored row passes; and a record written before
    ``policy.kind`` existed is reported uncertified -- refusing it would make every historical table
    unreadable, which is not the same thing as safer.
    """
    sys.path.insert(0, str(_REPO / "ablation_harness"))
    import run_ablation  # noqa: E402

    def table(group: str | None, kind: str | None):
        base = pathlib.Path(tempfile.mkdtemp(prefix="table-")) / "proto"
        folder = base / group if group else base
        run_id = "run-ck" if kind == "checkpoint" else "run-zero"
        (folder / run_id).mkdir(parents=True)
        payload = {"record_format": record.RECORD_FORMAT}
        if kind is not None:
            payload["policy"] = {"kind": kind}
        (folder / run_id / "record.json").write_text(json.dumps(payload), encoding="utf-8")
        path = folder / "summary.csv"
        path.write_text(f"run_id\n{run_id}\n", encoding="utf-8")
        return run_ablation._identity_report(path, [{"run_id": run_id}])

    assert table(None, "zero_action") == ([("run-zero", "zero_action")], []), \
        "a diagnostic row in a scores table has to be refused, with its kind named"
    assert table("smoke", "zero_action") == ([], []), "a smoke table is a diagnostic table on purpose"
    assert table(None, "checkpoint") == ([], []), "a scored policy row is what a scores table is for"
    refused, uncertified = table(None, None)
    assert not refused and uncertified == ["run-zero"], "no kind is uncertified, not refused"


@contextlib.contextmanager
def _patched(module, **values):
    """Set module attributes for one test, restore them however it ends."""
    old = {k: getattr(module, k) for k in values}
    for key, value in values.items():
        setattr(module, key, value)
    try:
        yield
    finally:
        for key, value in old.items():
            setattr(module, key, value)


def _probe_run(**overrides) -> dict:
    """One-run spec payload; nominal only, so one checkpoint means one eval."""
    return {"tag": "probe", "task": "Lizard2-Flat-v3", "seed": 42, "max_iterations": 2,
            "eval_modes": ["nominal"], **overrides}


def _sweep_harness(scratch: str, run: dict, seed: list[str] = (), train_ok: bool = True,
                   train_writes_last: bool = True, eval_writes_result: bool = True) -> dict:
    """Run the real ``_sweep`` over a fake two-tree layout; only sim and sharing are faked.

    ``work/active/ablation-sweep-final-checkpoint-name.md``: the scheduler asked for
    ``model_{max_iterations}.pt`` while a run of that budget ends on ``model_{N-1}.pt``, so every
    spec that had to train failed before eval. The fakes are the subprocess (which would start
    Isaac Sim) and the two shared roots; the scheduler's own decisions are the real ones.
    """
    import yaml

    isaac = pathlib.Path(scratch) / "isaac"
    run_dir = isaac / "logs" / "rsl_rl" / "exp" / f"2026-01-01_00-00-00_{run['tag']}"
    run_dir.mkdir(parents=True)
    for name in seed:
        (run_dir / name).write_bytes(b"")
    harness = pathlib.Path(scratch) / "harness"
    harness.mkdir()
    (harness / "eval.py").write_text("", encoding="utf-8")
    spec = pathlib.Path(scratch) / "spec.yaml"
    spec.write_text(yaml.safe_dump({"runs": [run], "group": "probe"}), encoding="utf-8")

    calls = {"train": [], "eval": []}

    def fake_run(argv, cwd=None, check=False):
        kind = "train" if argv[1].endswith("train.py") else "eval"
        calls[kind].append((list(argv), cwd))
        if kind == "train":
            if not train_ok:
                raise subprocess.CalledProcessError(1, argv)
            if train_writes_last:
                (run_dir / f"model_{int(run['max_iterations']) - 1}.pt").write_bytes(b"")
        elif eval_writes_result:
            iteration = _checkpoint_of(argv).stem.split("_")[-1]
            run_id = f"{run['task']}_{run['tag']}_it{iteration}_nominal_seed123"
            out_json = harness / "results" / "locomotion_eval_v3" / "probe" / run_id / "eval.json"
            out_json.parent.mkdir(parents=True, exist_ok=True)
            out_json.write_text("{}", encoding="utf-8")
        return types.SimpleNamespace(returncode=0)

    args = types.SimpleNamespace(spec=str(spec), python="python", device=None,
                                 protocol="locomotion_eval_v3", group=None)
    fake_subprocess = types.SimpleNamespace(run=fake_run,
                                            CalledProcessError=subprocess.CalledProcessError)
    with _patched(run_ablation, _ISAAC_ROOT=isaac, _HARNESS_DIR=harness,
                  subprocess=fake_subprocess):
        failures = run_ablation._sweep(args)
    return {"failures": failures, **calls, "run_dir": run_dir, "harness": harness, "isaac": isaac}


def _checkpoint_of(argv: list[str]) -> pathlib.Path:
    return pathlib.Path(argv[argv.index("--checkpoint") + 1])


def test_a_fresh_run_is_scored_at_its_last_checkpoint():
    """A run of budget N ends on model_{N-1}.pt -- the default checkpoint is that one.

    Pre-fix, ``_run_train`` looked for model_2.pt on a two-iteration run, printed
    ``expected model_2.pt not found`` and returned None: training happened, then the sweep counted a
    failure and never reached eval. The budget's indices are the trainer's 0..N-1, so the assertion
    is on what a real run leaves behind, not on a name the scheduler composed.
    """
    run = _probe_run()
    result = _sweep_harness(tempfile.mkdtemp(prefix="sweep-"), run)
    assert run_ablation._eval_checkpoints(run, result["run_dir"], 2) == [1], \
        "the default is the run's last checkpoint (N-1), not the budget N the trainer never saves"
    assert result["failures"] == 0, f"a run that trains must reach eval, got {result['failures']} failure(s)"
    assert len(result["train"]) == 1, "the budget had not been reached, so training had to run once"
    assert len(result["eval"]) == 1, "one default checkpoint means one eval"
    assert _checkpoint_of(result["eval"][0][0]) == result["run_dir"] / "model_1.pt", \
        "with no eval_checkpoints the run's own last checkpoint (N-1) is the one to score"


def test_eval_without_result_is_a_failure_even_on_zero_exit():
    result = _sweep_harness(tempfile.mkdtemp(prefix="sweep-"), _probe_run(), eval_writes_result=False)
    assert len(result["eval"]) == 1 and result["failures"] == 1


def test_a_finished_run_is_not_retrained():
    """The completion evidence reads the directory, so a finished run is reused, not re-trained."""
    run = _probe_run()
    result = _sweep_harness(tempfile.mkdtemp(prefix="sweep-"), run, seed=["model_1.pt"])
    assert not result["train"], "a run that already reached its budget must not be trained again"
    assert _checkpoint_of(result["eval"][0][0]) == result["run_dir"] / "model_1.pt"


def test_an_unfinished_or_failed_train_is_not_a_finished_run():
    """Half a budget, or a crash, is not "done" -- both must be counted as failures, with no eval."""
    run = _probe_run()
    partial = _sweep_harness(tempfile.mkdtemp(prefix="sweep-"), run, train_writes_last=False)
    assert partial["failures"] == 1 and not partial["eval"], \
        "a run that stopped before its last iteration is unfinished, not scored"
    crashed = _sweep_harness(tempfile.mkdtemp(prefix="sweep-"), run, train_ok=False)
    assert crashed["failures"] == 1 and not crashed["eval"], "a failed train is a failed run"


def test_the_sweep_launches_from_the_repo_and_runs_isaaclab_as_cwd():
    """Eval enters through the harness's own absolute path; the IsaacLab tree is only the cwd.

    Pre-fix, ``_run_eval`` passed the string ``ablation_harness/eval.py`` with ``cwd=IsaacLab``,
    which resolved only while the retired junction made one a child of the other -- with the link
    gone it was ``can't open file``. The log glob must likewise come from the resolved IsaacLab tree.
    """
    run = _probe_run()
    result = _sweep_harness(tempfile.mkdtemp(prefix="sweep-"), run)
    train_argv, train_cwd = result["train"][0]
    eval_argv, eval_cwd = result["eval"][0]
    assert eval_argv[1] == str(result["harness"] / "eval.py"), \
        f"the eval entry has to be an existing absolute path, not {eval_argv[1]!r}"
    assert pathlib.Path(eval_argv[1]).is_file(), "the entry named has to exist"
    assert train_argv[1] == "scripts/reinforcement_learning/rsl_rl/train.py" and \
        train_cwd == str(result["isaac"]), "the trainer is IsaacLab's own script, relative to its tree"
    assert eval_cwd == str(result["isaac"]), "eval inherits the same cwd as train"
    assert str(result["run_dir"]).startswith(str(result["isaac"])), \
        "the log directory must be found in the IsaacLab tree, not beside the harness"


#: The pairs written before the fix (``eval.py`` read HEAD into the result *after* the rollout, so a
#: commit landing mid-run left the two files of one run disagreeing). Each entry names the
#: disagreement itself, so re-running one of those runs makes the entry stale and this gate says to
#: drop it rather than letting an old exception quietly cover a new mismatch.
_PRE_FIX_REV_PAIRS = {
    "locomotion_eval_v3/livecheck/Lizard2-Flat-v3_live_nominal_seed123_ckpt3000": {
        "git_rev_lizard": ("0f4b2bf5317a", "ee1fc367cba8"),
    },
    "locomotion_eval_v3/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123": {
        "git_rev_lizard": ("0f4b2bf5317a", "e4d1ac7d0a04"),
    },
}
_RESULTS = _REPO / "ablation_harness" / "results"
_REV_FIELDS = ("git_rev_lizard", "git_rev_isaaclab")


def one_run_one_revision(results: pathlib.Path, exceptions: dict[str, dict[str, tuple[str, str]]]) -> list[str]:
    """Mismatched revisions between a run's record and its result, plus the exceptions gone stale.

    One run is one measurement, so its two files have to name one revision of each tree. Reading the
    pairs off disk covers the artifacts the write side produced, which a fixture over the writer
    cannot: the divergence was in the two files, and no single call returns both.

    Args:
        results: the harness' results root.
        exceptions: run key -> field -> the (record, result) pair that was already wrong when the fix
            landed.

    Returns:
        One message per mismatch, and one per exception that is no longer needed.
    """
    problems: list[str] = []
    for record_path in sorted(results.glob("**/record.json")):
        result_path = record_path.with_name("eval.json")
        if not result_path.is_file():
            continue
        record_json = json.loads(record_path.read_text(encoding="utf-8"))
        result_json = json.loads(result_path.read_text(encoding="utf-8"))
        recorded = record_json.get("runtime") or {}
        key = record_path.parent.relative_to(results).as_posix()
        for field in _REV_FIELDS:
            pair = (recorded.get(field), result_json.get(field))
            known = (exceptions.get(key) or {}).get(field)
            if pair[0] == pair[1]:
                if known is not None:
                    problems.append(f"{key}: {field} now agrees ({pair[0]}) -- drop its exception")
                continue
            if known != pair:
                problems.append(f"{key}: {field} record {pair[0]} != result {pair[1]}")
    return problems


def test_one_run_names_one_revision() -> None:
    """A run's record and its result must name the same code; the stored pairs are the control.

    The guard bites on the two pairs written before the fix (asserted below without the exceptions),
    and passes with them declared. A run re-run after the fix leaves its exception unused, and that
    is reported as a problem rather than ignored -- an exception nobody needs is how the next
    mismatch gets covered up.
    """
    unguarded = one_run_one_revision(_RESULTS, {})
    assert len(unguarded) == len(_PRE_FIX_REV_PAIRS), \
        f"the stored pairs must hold exactly the disagreements the table names: {unguarded}"
    for key, fields in _PRE_FIX_REV_PAIRS.items():
        assert any(message.startswith(key) for message in unguarded), \
            f"{key} is the pair this guard is for, and it has to be caught by reading disk: {unguarded}"
    with tempfile.TemporaryDirectory() as scratch:
        run = pathlib.Path(scratch) / "locomotion_eval_v3" / "group" / "a_run"
        run.mkdir(parents=True)
        (run / "record.json").write_text(json.dumps({"runtime": {"git_rev_lizard": "aa"}}), encoding="utf-8")
        (run / "eval.json").write_text(json.dumps({"git_rev_lizard": "aa"}), encoding="utf-8")
        assert one_run_one_revision(pathlib.Path(scratch), {}) == [], "two files that agree are not a finding"
        (run / "eval.json").write_text(json.dumps({"git_rev_lizard": "bb"}), encoding="utf-8")
        assert one_run_one_revision(pathlib.Path(scratch), {}) == [
            "locomotion_eval_v3/group/a_run: git_rev_lizard record aa != result bb"
        ], "a revision re-read after the rollout is exactly this shape"
        (run / "eval.json").write_text(json.dumps({"git_rev_lizard": "aa"}), encoding="utf-8")
        stale = {"locomotion_eval_v3/group/a_run": {"git_rev_lizard": ("zz", "zz")}}
        assert one_run_one_revision(pathlib.Path(scratch), stale) == [
            "locomotion_eval_v3/group/a_run: git_rev_lizard now agrees (aa) -- drop its exception"
        ], "an exception whose disagreement is gone has to be reported"
    assert one_run_one_revision(_RESULTS, _PRE_FIX_REV_PAIRS) == [], \
        "with the pre-fix pairs declared, the stored runs must read clean"


def _eval_exit_probe(entry: pathlib.Path) -> None:
    """Run the real parser and post-launch import; simulate Kit and main in a child."""
    script = r'''
import atexit, builtins, io, os, pathlib, runpy, sys, types
mode, entry, marker = sys.argv[1:]
app_module = types.ModuleType('isaaclab.app')
class AppLauncher:
    @staticmethod
    def add_app_launcher_args(parser): pass
    def __init__(self, args):
        self.app = self
        atexit.register(lambda: os._exit(0))
    def close(self):
        if mode == 'close_error': raise RuntimeError('injected close failure')
        pathlib.Path(marker).touch()
        os._exit(0)
app_module.AppLauncher = AppLauncher
sys.modules['isaaclab'] = types.ModuleType('isaaclab')
sys.modules['isaaclab.app'] = app_module
original_import = builtins.__import__
def injected_import(name, *args, **kwargs):
    if name == 'gymnasium': raise RuntimeError('injected import failure')
    return original_import(name, *args, **kwargs)
builtins.__import__ = injected_import
sys.argv = [entry] + (['--help'] if mode == 'help' else [] if mode == 'parser_error' else ['--task', 'test'])
original_run_path = runpy.run_path
if mode not in ('import', 'help', 'parser_error'):
    def fake_runner(path, run_name):
        def main():
            if mode == 'error': raise RuntimeError('injected main failure')
            if mode == 'system_exit': raise SystemExit('injected main refusal')
            if mode == 'broken_stdout':
                class BrokenStdout(io.StringIO):
                    def flush(self): raise OSError('stdout flush failed')
                sys.stdout = BrokenStdout()
                raise RuntimeError('injected flush failure')
        return {'main': main, 'simulation_app': AppLauncher(None)}
    runpy.run_path = fake_runner
original_run_path(entry, run_name='__main__')
'''
    cases = (('import', 1, 'injected import failure'), ('parser_error', 1, '--task'),
             ('help', 0, 'usage:'), ('error', 1, 'injected main failure'),
             ('system_exit', 1, 'injected main refusal'), ('broken_stdout', 1, 'injected flush failure'),
             ('close_error', 1, 'injected close failure'), ('success', 0, ''))
    with tempfile.TemporaryDirectory() as scratch:
        for mode, expected, message in cases:
            marker = pathlib.Path(scratch) / mode
            result = subprocess.run([sys.executable, '-c', script, mode, str(entry), str(marker)], cwd=scratch,
                                    capture_output=True, text=True, encoding='utf-8', errors='replace')
            assert result.returncode == expected, (mode, result.returncode, result.stderr)
            assert message in (result.stdout if mode == 'help' else result.stderr), (mode, result.stderr)
            assert marker.exists() == (mode == 'success'), mode
            if expected == 1:
                assert 'Traceback' in result.stderr, (mode, result.stderr)


def test_eval_failure_exit_status() -> None:
    _eval_exit_probe(_REPO / 'ablation_harness' / 'eval.py')


def _main() -> None:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"[OK] {fn.__name__}")
    assert "torch" not in sys.modules and "numpy" not in sys.modules, \
        "the checks in this file must stay framework-free"
    print(f"test_eval_record: {len(tests)} passed")


if __name__ == "__main__":
    _main()
