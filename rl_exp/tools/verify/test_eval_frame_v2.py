# -*- coding: utf-8 -*-
"""Regression gate for the Locomotion-Eval-v2 frame contract (no sim).

v1 sampled the pre-step state, so an episode whose bad attitude run ended on the
frame it terminated on only ever showed ``sustain_steps - 1`` bad frames -- the
auto-reset inside ``step()`` had already overwritten the last one -- and read as
no-fall. v2 samples the post-physics pre-reset state with the terminal frame
captured, so the same episode's window closes.

This gate encodes both readings on the pure metric layer (``metrics.fall_flags``
+ the valid mask), which is where the frame contract lands. The capture itself
(hooking the env reset) is runtime-only and is reported by the
``terminal frames captured=`` line every eval run prints: it must equal the
number of early-ended episodes, else the private hook went stale.

Usage: python rl_exp\\tools\\verify\\test_eval_frame_v2.py
"""
import json
import pathlib
import sys

import torch
import yaml

_REPO = pathlib.Path(__file__).absolute().parents[3]
sys.path.insert(0, str(_REPO / "ablation_harness"))
sys.path.insert(0, str(_REPO))
from metrics import fall_flags  # noqa: E402
import baseline_metrics  # noqa: E402
import suite_lock  # noqa: E402
from rl_exp.tools.runrecord import binding  # noqa: E402

STEPS, SUSTAIN = 120, 25
TILT_COS_MIN = 0.766044443118978  # cos(40 deg) = the protocol's tilt threshold


def _case(bad_start: int, bad_len: int, first_done: int):
    """(tilt_cos, valid) for one env: bad run of ``bad_len`` frames from ``bad_start``.

    ``tilt_cos = -projected_gravity_b.z``: upright = +1, a 60 deg tilt = cos(60) = 0.5.
    """
    tilt = torch.full((STEPS, 1), 1.0)  # upright
    tilt[bad_start:bad_start + bad_len] = 0.5  # 60 deg, past the 40 deg threshold
    valid = torch.arange(STEPS).unsqueeze(1) <= first_done
    return tilt, valid


def _fall(tilt: torch.Tensor, valid: torch.Tensor) -> bool:
    return bool(fall_flags(tilt, None, TILT_COS_MIN, None, SUSTAIN, valid)[0])


def main():
    # 1) bad run 36..60, episode ends on 60: 25 bad frames, terminal one included
    tilt, valid = _case(36, SUSTAIN, first_done=60)
    assert _fall(tilt, valid), "v2 (terminal frame present): 25-frame window must register"
    # the v1 reading of the same episode: the terminal frame was lost, so the
    # mask stops one row earlier and only 24 bad frames remain
    v1_valid = valid & (torch.arange(STEPS).unsqueeze(1) <= 59)
    assert not _fall(tilt, v1_valid), "v1 truncation (24 frames) must read as no-fall"
    print("  ok terminal frame closes the window (its v1 truncation does not)")

    # 2) one frame short stays short: the fix must not turn any near-miss into a fall
    tilt, valid = _case(36, SUSTAIN - 1, first_done=60)
    assert not _fall(tilt, valid), "24 bad frames must not register as fall"
    print("  ok one frame short is still no fall")

    # 3) same window at the very tail of the series (no termination involved)
    tilt, valid = _case(STEPS - SUSTAIN, SUSTAIN, first_done=STEPS - 1)
    assert _fall(tilt, valid), "window ending on the final row must register"
    print("  ok window ending on the final row")

    # 4) an upright episode still reads clean (mask not inverted by any of the above)
    tilt, valid = _case(0, 0, first_done=STEPS - 1)
    assert not _fall(tilt, valid), "upright episode must not register as fall"
    print("  ok upright episode stays clean")

    test_suite_lock_three_states_and_the_stage_that_refuses()
    test_a_protocol_that_freezes_no_suite_is_refused_from_v4_on()
    test_fingerprint_block_round_trips()
    test_the_shipped_v4_protocol_is_fingerprinted_and_matches()
    test_a_digest_is_compared_without_its_algorithm_prefix()
    test_protocol_anchors_match_the_files_they_pin()
    test_every_protocol_is_anchored_or_declared_legacy()

    print("ALL_EVAL_FRAME_V2_TESTS_PASSED")


# --- the suite lock (Locomotion-Eval-v4): the frozen ground, checked before it is measured ---------
#
# v3 locked nothing: the protocol named a suite, while the suite's content and seed lived in
# suites.py and the mesh came out of the engine. Two runs both saying `lizard_suite_v2` could stand
# on different ground, discoverable only afterwards from the record's digests. v4 freezes both
# fingerprints in the protocol, in two steps, and the third outcome is what keeps a machine swap
# from reading as a protocol change.

_FROZEN_ENV = {"sim_version": "5.0.0", "physx_version": "107.3.31", "gpu": "RTX 4090",
               "gpu_compute_capability": "8.9", "numpy_version": "1.26.1", "warp_version": "1.7.0",
               "torch_version": "2.10.0", "git_rev_isaaclab": "abc123"}
_OTHER_ENV = {**_FROZEN_ENV, "physx_version": "107.4.0"}


def _protocol(version: int, expected: dict | None) -> dict:
    protocol = {"name": f"Locomotion-Eval-v{version}", "version": version, "suite": "lizard_suite_v2"}
    if expected is not None:
        protocol["suite_expected"] = expected
    return protocol


def _declared(cfg="sha256:cfg", geometry="sha256:geo", env=None) -> dict:
    return {"name": "lizard_suite_v2", "cfg_digest": cfg, "geometry_digest": geometry,
            "geometry_env": _FROZEN_ENV if env is None else env}


def test_suite_lock_three_states_and_the_stage_that_refuses():
    frozen = _declared()
    matching = suite_lock.compare(_protocol(4, frozen), "sha256:cfg", "sha256:geo", _FROZEN_ENV)
    assert matching["verdict"] == suite_lock.MATCH, matching
    assert suite_lock.start_refusal(_protocol(4, frozen), matching, stage="cfg") is None
    assert suite_lock.start_refusal(_protocol(4, frozen), matching, stage="geometry") is None

    # The cfg is the harness' own factory output, so it is comparable before the env exists and a
    # wrong suite never costs a simulator start.
    wrong_cfg = suite_lock.compare(_protocol(4, frozen), "sha256:other", "sha256:geo", _FROZEN_ENV)
    assert wrong_cfg["verdict"] == suite_lock.MISMATCH, wrong_cfg
    assert "cfg_digest" in (suite_lock.start_refusal(_protocol(4, frozen), wrong_cfg, stage="cfg") or "")

    # The geometry is generated by the engine, so it is only comparable after construction.
    wrong_geometry = suite_lock.compare(_protocol(4, frozen), "sha256:cfg", "sha256:other", _FROZEN_ENV)
    assert suite_lock.start_refusal(_protocol(4, frozen), wrong_geometry, stage="cfg") is None, \
        "the geometry is not known yet at the cfg stage, so it cannot refuse there"
    assert "geometry_digest" in (suite_lock.start_refusal(_protocol(4, frozen), wrong_geometry,
                                                          stage="geometry") or "")

    # Same mismatch, different engine: unknown, not a protocol change. This is the whole reason the
    # verdict is not a boolean -- a machine migration must not be reported as a terrain edit.
    moved = suite_lock.compare(_protocol(4, frozen), "sha256:cfg", "sha256:other", _OTHER_ENV)
    assert moved["verdict"] == suite_lock.UNKNOWN, moved
    assert "physx_version" in moved["geometry"]["reason"], moved["geometry"]
    assert suite_lock.start_refusal(_protocol(4, frozen), moved, stage="geometry") is None

    # A declared environment field that is not judged must not soften a real mismatch into unknown.
    extra = _declared(env={**_FROZEN_ENV, "driver_version": "555.0"})
    extra = suite_lock.compare(_protocol(4, extra), "sha256:cfg", "sha256:other", _FROZEN_ENV)
    assert extra["verdict"] == suite_lock.MISMATCH, extra
    print("  ok suite lock: match / mismatch / unknown, and only the reachable stage refuses")


def test_a_protocol_that_freezes_no_suite_is_refused_from_v4_on():
    """The rule may not apply backwards: v1-v3 were published without a lock and must still run."""
    unlocked_v4 = _protocol(4, {"name": "lizard_suite_v2", "cfg_digest": "sha256:cfg",
                                "geometry_digest": None, "geometry_env": None})
    lock = suite_lock.compare(unlocked_v4, "sha256:cfg", "sha256:geo", _FROZEN_ENV)
    assert lock["verdict"] == suite_lock.NOT_DECLARED, lock
    assert suite_lock.start_refusal(unlocked_v4, lock, stage="cfg") is None, \
        "the fingerprint-printing path has to be reachable, or nothing could ever be approved"
    refusal = suite_lock.start_refusal(unlocked_v4, lock, stage="geometry")
    assert refusal and "--print-suite-fingerprint" in refusal, refusal

    legacy = suite_lock.compare(_protocol(3, None), "sha256:cfg", "sha256:geo", _FROZEN_ENV)
    assert legacy["verdict"] == suite_lock.NOT_DECLARED
    assert suite_lock.start_refusal(_protocol(3, None), legacy, stage="geometry") is None
    print("  ok suite lock: v4 must freeze its ground, v3 is grandfathered")


def test_fingerprint_block_round_trips():
    """What --print-suite-fingerprint prints is what the next run will be checked against."""
    block = json.loads(suite_lock.fingerprint_block(_protocol(4, None), "sha256:cfg", "sha256:geo",
                                                    _FROZEN_ENV))
    assert block["name"] == "lizard_suite_v2" and block["cfg_digest"] == "sha256:cfg"
    lock = suite_lock.compare(_protocol(4, block), "sha256:cfg", "sha256:geo", _FROZEN_ENV)
    assert lock["verdict"] == suite_lock.MATCH, lock
    print("  ok the printed fingerprint block is exactly what a later run matches")


def test_the_shipped_v4_protocol_is_fingerprinted_and_matches():
    """The declaration on disk, not a fixture: v4 must carry a complete fingerprint and be unlocked.

    This pin flips with the protocol's own state, which is the point: while the fingerprint was
    unfilled the assertion was "refused"; once a real run pasted it, the assertion is "declared,
    complete, and no longer refused". A v4 left half-declared cannot pass either way.
    """
    protocol = yaml.safe_load((_REPO / "ablation_harness" / "protocols" /
                               "locomotion_eval_v4.yaml").read_text(encoding="utf-8"))
    expected = protocol["suite_expected"]
    assert expected["name"] == protocol["suite"], expected
    for key in ("cfg_digest", "geometry_digest"):
        assert expected[key], f"v4 is unlocked without a {key}"
        assert len("".join(ch for ch in expected[key] if ch != ":")) >= 64, expected[key]
    # The declared environment must cover every field the lock judges, or a later field would read
    # as an unknown environment rather than as the same one -- and 'unknown' never refuses.
    declared_env = expected["geometry_env"] or {}
    missing = [name for name in suite_lock.ENV_FIELDS if name not in declared_env]
    assert not missing, f"geometry_env does not declare {missing}"
    # The declaration against itself: this is a completeness/shape pin, not a probe of the machine
    # (the three states are exercised with synthetic digests in the test above).
    lock = suite_lock.compare(protocol, expected["cfg_digest"], expected["geometry_digest"], _FROZEN_ENV)
    assert lock["cfg"]["verdict"] == suite_lock.MATCH, lock["cfg"]
    assert lock["geometry"]["verdict"] == suite_lock.MATCH, lock["geometry"]
    assert suite_lock.start_refusal(protocol, lock, stage="cfg") is None
    assert suite_lock.start_refusal(protocol, lock, stage="geometry") is None
    v3 = yaml.safe_load((_REPO / "ablation_harness" / "protocols" /
                         "locomotion_eval_v3.yaml").read_text(encoding="utf-8"))
    assert "suite_expected" not in v3, "the frozen v3 protocol is not edited in place"
    print("  ok v4 is fingerprinted, complete, and no longer refused; v3 is untouched")


def test_a_digest_is_compared_without_its_algorithm_prefix():
    """The two spellings in circulation must not read as a mismatch.

    ``cfg_snapshot.digest`` returns bare hex while ``record.digest`` and the terrain probe return
    ``sha256:<hex>``. The lock's first real run refused a *correct* declaration for exactly that
    reason, so the comparison is on the digest and the reported values keep their spelling.
    """
    bare = "c0d71" + "0" * 59
    prefixed = f"sha256:{bare}"
    declared = _declared(cfg=prefixed, geometry=prefixed)
    same = (
        suite_lock.compare(_protocol(4, declared), prefixed, prefixed, _FROZEN_ENV),
        suite_lock.compare(_protocol(4, declared), bare, prefixed, _FROZEN_ENV),
        suite_lock.compare(_protocol(4, declared), prefixed, bare, _FROZEN_ENV),
    )
    for lock in same:
        assert lock["verdict"] == suite_lock.MATCH, lock
    moved = suite_lock.compare(_protocol(4, declared), bare, f"sha256:{'a' * 64}", _FROZEN_ENV)
    assert moved["verdict"] == suite_lock.MISMATCH, moved
    assert moved["geometry"]["actual"] == f"sha256:{'a' * 64}", moved["geometry"]
    print("  ok digests compare across spellings; the report keeps the spelling it read")


def test_protocol_anchors_match_the_files_they_pin():
    """A protocol's declared numbers have to move as a deliberate edit, not as a silent one.

    The criteria table pins kinds and cases, the suite lock pins the ground, and the migration proof
    compares one record's verdicts under two protocols -- none of them reads a protocol's declared
    numbers, so a threshold could move with the whole offline suite still green
    (acceptance/records/2026-09-23-threshold-pilot.md: v4's tracking threshold 0.2 -> 0.25, 47/47).

    What this pin is: a change detector over the protocols in use. What it is not: an approval.
    Pasting a digest into ``protocol_anchors.json`` is the deliberate act, and a green run afterwards
    says the file and the table agree -- not that anyone reviewed the number that moved.
    """
    table = json.loads((_REPO / "ablation_harness" / "protocol_anchors.json").read_text(encoding="utf-8"))
    harness = _REPO / "ablation_harness"
    problems = []
    for rel, entry in sorted(table["anchors"].items()):
        assert entry.get("reason"), f"{rel}: an anchor without a reason records no review"
        path = harness / rel
        if not path.is_file():
            problems.append(f"{rel}: anchored but not on disk -- retire this entry deliberately")
            continue
        actual = binding.sha256_file(path)
        if actual != entry["sha256"]:
            problems.append(
                f"{rel}: the bytes moved since they were approved\n"
                f"      table: {entry['sha256']}\n"
                f"      disk:  {actual}\n"
                f"      revert the edit, or approve the new bytes with a reason in protocol_anchors.json"
            )
    assert not problems, "\n".join(problems)
    print(f"  ok {len(table['anchors'])} protocol(s) match the bytes their approval records")


def _protocol_identity(path: pathlib.Path) -> tuple[str, int] | None:
    """The ``(name, version)`` a protocol file declares, or ``None`` when it declares neither."""
    text = path.read_text(encoding="utf-8")
    block = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    if not isinstance(block, dict):
        return None
    name, version = block.get("name"), block.get("version")
    return (name, version) if isinstance(name, str) and isinstance(version, int) else None


def test_every_protocol_is_anchored_or_declared_legacy():
    """The subjects come off the tree, because a declaration only lists what somebody remembered.

    On the day this rule was written a protocol had already landed unanchored -- ``6de88a0`` added
    ``lizard2_flat_v2.json`` and nothing noticed, the same shape that let two golden locks go
    unguarded (acceptance/records/2026-09-22-golden-subject-completeness.md). Reading the set off
    ``protocols/`` is what makes a new protocol covered the moment it arrives. An exemption is a
    *rule*, not a second list to maintain: the name+version pairs already declared in
    ``baseline_metrics.LEGACY_PROTOCOLS`` are the protocols published before the anchor existed.
    """
    harness = _REPO / "ablation_harness"
    table = json.loads((harness / "protocol_anchors.json").read_text(encoding="utf-8"))
    anchored = set(table["anchors"])
    problems, exempt = [], []
    for path in sorted((harness / "protocols").iterdir()):
        if path.suffix not in (".json", ".yaml"):
            continue
        rel = f"protocols/{path.name}"
        if rel in anchored:
            continue
        identity = _protocol_identity(path)
        if identity is not None and identity in baseline_metrics.LEGACY_PROTOCOLS:
            exempt.append(rel)
            continue
        problems.append(
            f"{rel}: on disk but neither anchored nor declared legacy -- a protocol nothing checks can"
            " have its numbers moved with the suite green; add its digest and reason to"
            " protocol_anchors.json, or make its case for being exempt"
        )
    assert not problems, "\n".join(problems)
    print(f"  ok {len(anchored)} protocol(s) anchored, {len(exempt)} declared legacy, none uncovered")


if __name__ == "__main__":
    main()
