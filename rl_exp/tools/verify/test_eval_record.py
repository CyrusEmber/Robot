# -*- coding: utf-8 -*-
"""Offline gate for the eval record format (`ARCH_PLAN` Step 3.2a/3.2e, no sim).

Three things this file is here to prove:

1. The read side keeps Step 0c's four rules apart -- no ``record_format`` is *legacy*
   (fields stay unknown), a format missing its required fields is *incomplete* (not legacy,
   not a pass), and only a complete record can be compared at all.
2. P04's four substitutions (checkpoint / suite / assets / protocol) each move **their own**
   binding, so a swapped input cannot be published under the old record's identity.
3. The record module writes records without consuming the random stream: it must not import
   torch, numpy or random at all (3.2d's offline half).

The negative direction is built in: every substitution asserts both that the digest moved and
that the two records read as ``not_comparable``, and the untouched pair as ``comparable``.
"""

import ast
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
