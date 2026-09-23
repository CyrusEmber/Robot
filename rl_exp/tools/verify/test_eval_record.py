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

The negative direction is built in: every substitution asserts both that the digest moved and
that the two records read as ``not_comparable``, and the untouched pair as ``comparable``.
"""

import ast
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "ablation_harness"))

import record  # noqa: E402


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
        "suite": {"name": "lizard_suite_v1", "digest": "sha256:suite"},
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
    assert record.table_conflicts([a, b])["conflicts"], "the table report names the pair"


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


def test_an_absent_fact_is_unproven_and_an_unreadable_row_is_named():
    a, b = _record(), _twin()
    a["judge"] = {"id": record.UNKNOWN}
    b["judge"] = {"id": record.UNKNOWN}
    found = record.conditions_conflict(a, b)
    assert found["conflicts"] == {} and found["unproven"] == ["judge.id"], found
    report = record.table_conflicts([_record(), _record(complete=False)])
    assert report["unreadable"] and not report["conflicts"], report


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
