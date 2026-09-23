# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline regressions for baseline fixed-window collection, judgement, and startup checks."""

import ast
import importlib
import json
import math
import pathlib
import re
import sys
import tempfile
from types import SimpleNamespace as NS

import yaml

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
import torch
from ablation_harness import baseline_frames, baseline_metrics, loco_judge, metrics, record
from ablation_harness.components import command_player
from rl_exp.tools.diagnose.diag_metrics import mesh_min_z, pad_point_clouds
from rl_exp.tools.verify.baseline_runtime import joint_reset_errors, material_errors, termination_errors

PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/baseline_flat_v1.json").read_text())
V2_PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/baseline_flat_v2.json").read_text())
V3_PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/baseline_flat_v3.json").read_text())
BODY_WEIGHT_N = 706.32  # 72 kg x 9.81, the figure every baseline report carries

# The axis labels a test record carries: a per-body reading has to name its bodies, and the newest
# format's per-foot vectors name their feet.
FEET = ["rr_foot", "rl_foot"]
AXES = {
    "non_foot_fraction": ["chest_pitch", "neck_pitch"],
    "mesh_min_z": ["chest_pitch", "neck_pitch"],
    "foot_contact": FEET,
    "foot_fraction": FEET,
    "foot_lowest_point": FEET,
    "foot_com_pos": FEET,
    "foot_lin_vel": FEET,
    "foot_ang_vel": FEET,
}

# What the newest format demands on top of the first one's meta: where the ground came from, and
# which asset's geometry the foot reading was taken off. Fixture values, not evidence.
GROUND_SOURCE = {"kind": "plane", "z_m": 0.0, "normal": [0.0, 0.0, 1.0]}
FOOT_GEOMETRY = {name: {"obj": f"{name}_collision.obj", "sha256": "sha256:" + "0" * 64, "vertices": 8}
                 for name in FEET}


def feet_walk(artifact: dict, *, lift_m: float = 0.06, slip_mps: float = 0.0, spin_rad_s: float = 0.0,
              descend_mps: float = 0.0, period: int = 4) -> dict:
    """Give a format-2 window a gait: every foot alternates stance with a swing clearing ``lift_m``.

    The knobs are the three things the foot criteria have to tell apart -- a swing that lifts or does
    not, a loaded foot moving tangentially (``slip_mps``) versus one only rotating about its contact
    (``spin_rad_s``: the contact point moves while the body's velocity stays zero), and a foot coming
    straight down (``descend_mps``), which is not sliding along the ground.
    """
    frames = artifact["frames"]
    steps, envs, feet = frames["foot_contact"].shape
    phase = (torch.arange(steps).view(-1, 1) + torch.arange(feet).view(1, -1)) % period
    swing = (phase >= period // 2).view(steps, 1, feet).expand(steps, envs, feet)

    contact = (~swing).to(torch.float32)
    frames["foot_contact"] = contact
    frames["foot_fraction"] = contact * 0.25
    frames["foot_com_pos"] = torch.zeros(steps, envs, feet, 3)
    frames["foot_lowest_point"] = torch.zeros(steps, envs, feet, 3)
    frames["foot_lowest_point"][..., 0] = 0.02  # a 2 cm lever arm from the body's COM
    frames["foot_lowest_point"][..., 2] = torch.where(swing, torch.full_like(contact, lift_m), 0.0)
    frames["foot_lin_vel"] = torch.zeros(steps, envs, feet, 3)
    frames["foot_lin_vel"][..., 0] = torch.where(swing, torch.zeros_like(contact), slip_mps)
    frames["foot_lin_vel"][..., 2] = -descend_mps
    frames["foot_ang_vel"] = torch.zeros(steps, envs, feet, 3)
    frames["foot_ang_vel"][..., 2] = spin_rad_s  # yawing over the contact sweeps it sideways
    return artifact


def expect(exception, fn, *args, **kwargs):
    """Call ``fn`` and return the exception it must raise."""
    try:
        fn(*args, **kwargs)
    except exception as err:
        return err
    raise AssertionError(f"{getattr(fn, '__name__', fn)} must raise {exception.__name__}")


def default_frame(num_envs: int, columns: dict | None = None) -> dict:
    """One all-zero frame, shaped as the declared columns prescribe."""
    frame = {}
    for name, (kind, _, _) in (baseline_frames.COLUMNS if columns is None else columns).items():
        if kind == baseline_frames.VEC3_FEET:
            frame[name] = torch.zeros(num_envs, len(AXES[name]), 3)
        elif name in AXES:
            frame[name] = torch.zeros(num_envs, len(AXES[name]))
        else:
            frame[name] = torch.zeros(num_envs, 3) if kind == "vec3" else torch.zeros(num_envs)
    return frame


def build(protocol: dict, steps: int, *, num_envs: int = 1, series: dict | None = None,
          start_pos: torch.Tensor | None = None, start_yaw: torch.Tensor | None = None,
          fmt: str = baseline_frames.FORMAT) -> dict:
    """Collect a synthetic window through the real contract.

    ``series`` overrides a column per frame (``f(step) -> tensor``). The defaults are a clean run:
    walking exactly on the command the protocol declares (the middle of its box, so a fixed and a
    ranged protocol both get a run that is on command), feet down, nothing loaded that should not
    be, a timeout on the last frame. ``start_pos``/``start_yaw`` are the episode's initial state.
    ``fmt`` writes the window under that format's declaration, which is how a record from an older
    format gets built after a newer one exists.
    """
    box = baseline_metrics.command_box(protocol)
    forward = (box[0][0] + box[0][1]) / 2.0
    step_dt = protocol["episode_length_s"] / steps
    # Only the labels this format actually declares: the newest format's foot columns do not exist in
    # the older one, and a collector names the axes of the format it writes.
    declared = baseline_frames.format_spec(fmt)["columns"]
    recorder = baseline_frames.BaselineFrames(
        num_envs=num_envs, step_dt=step_dt,
        axes={name: labels for name, labels in AXES.items() if name in declared}, fmt=fmt)
    for step in range(steps):
        frame = default_frame(num_envs, recorder.columns)
        # Metres, not frame counts: one step of a 100-frame window is 0.2 s, so a robot on command
        # at 2 m/s really has moved 0.4 m by frame 1.
        frame["pos"][:] = torch.tensor([(step + 1) * forward * step_dt, 0.0, 0.0])
        frame["velocity_yaw"][:] = torch.tensor([forward, 0.0, 0.0])
        frame["command_world"][:] = torch.tensor([forward, 0.0, 0.0])
        frame["tilt_cos"][:] = 1.0
        frame["mesh_min_z"][:] = 0.5
        frame["foot_contact"][:] = 1.0
        frame["foot_fraction"][:] = 0.25
        frame["timeout"][:] = 1.0 if step == steps - 1 else 0.0
        if "foot_lowest_point" in frame:
            # A foot resting on the plane: its deepest mesh vertex sits at ground z, and the foot is
            # neither lifting nor sliding -- the reading the newest format adds, at its zero point.
            frame["foot_lowest_point"][..., 2] = 0.0
        for name, override in (series or {}).items():
            frame[name] = override(step)
        recorder.add(**frame)
    return recorder.artifact(
        protocol=protocol, body_weight_n=BODY_WEIGHT_N,
        start_pos=torch.zeros(num_envs, 3) if start_pos is None else start_pos,
        start_yaw=torch.zeros(num_envs) if start_yaw is None else start_yaw,
        # Handed to every format; only the newest one requires them.
        ground_source=GROUND_SOURCE, foot_geometry=FOOT_GEOMETRY)


def truncated(artifact: dict, frames_kept: int) -> dict:
    """The same window with its frames cut short, as a crash mid-collection would leave it."""
    cut = dict(artifact)
    cut["frames"] = {name: values[:frames_kept] for name, values in artifact["frames"].items()}
    return cut


def score(fail_at=None, *, simultaneous=False, yaw=0.0):
    def position(step):
        # After failure deliberately supply huge respawn displacements: none may count.
        distance = (step + 1) * 0.5 if fail_at is None or step <= fail_at else 1000.0
        return torch.tensor([[distance * math.cos(yaw), distance * math.sin(yaw), 0.0]])

    return baseline_metrics.judge(build(PROTOCOL, 20, series={
        "pos": position,
        "yaw": lambda step: torch.tensor([yaw]),
        "terminated": lambda step: torch.tensor([1.0 if step == fail_at else 0.0]),
        "timeout": lambda step: torch.tensor([1.0 if step == 19 or (simultaneous and step == fail_at) else 0.0]),
    }, start_yaw=torch.tensor([yaw])))


# --- the collector's contract ------------------------------------------------------------------

def test_collector_refuses_frames_that_do_not_fit_the_contract():
    recorder = baseline_frames.BaselineFrames(num_envs=2, step_dt=0.02, axes=AXES)
    frame = default_frame(2)
    recorder.add(**frame)
    assert recorder.count == 1
    del frame["tilt_cos"]
    err = expect(baseline_frames.FramesContractError, recorder.add, **frame)
    assert "tilt_cos" in str(err), err
    frame["tilt_cos"] = torch.zeros(2)
    frame["foot_contact"] = torch.zeros(2, 3)
    err = expect(baseline_frames.FramesContractError, recorder.add, **frame)
    assert "foot_contact" in str(err) and "shape" in str(err), err
    frame["foot_contact"] = torch.zeros(2, 2)
    frame["undeclared"] = torch.zeros(2)
    err = expect(baseline_frames.FramesContractError, recorder.add, **frame)
    assert "undeclared" in str(err), err


def test_axis_labels_must_agree_with_the_values():
    """A per-body reading whose labels do not fit its values cannot say which body it measured."""
    artifact = build(V2_PROTOCOL, 20)
    artifact["axes"]["non_foot_fraction"] = ["chest_pitch"]
    result = baseline_metrics.judge(artifact)
    assert result["verdict"] == "invalid", result["gates"]
    assert any("axis labels" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]


def test_a_cut_short_window_is_invalid_not_an_exception():
    result = baseline_metrics.judge(truncated(build(PROTOCOL, 20), 5))
    assert result["verdict"] == "invalid"
    assert any("5 of 20 frames" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]
    assert all(value is None for value in result["gates"].values()), "no gate may be judged from half a window"


def test_non_finite_measurement_is_invalid():
    artifact = build(V2_PROTOCOL, 20)
    artifact["frames"]["mesh_min_z"][7, 0, 0] = float("nan")
    result = baseline_metrics.judge(artifact)
    assert result["verdict"] == "invalid"
    assert any("mesh_min_z" in reason and "non-finite" in reason
               for reason in result["invalid_reasons"]), result["invalid_reasons"]


# --- the frame contract, by format -------------------------------------------------------------
#
# A record is read under the declaration its format names, so two things have to hold: the current
# format's table may not move in place, and a record written under an older format stays readable as
# what it was. The declaration is frozen by digest in ``frame_semantics.json``, and the fixture below
# is what keeps that digest from being a digest of a table that had already drifted.

_FRAMES_SEMANTICS_PATH = _REPO / "ablation_harness" / "frame_semantics.json"

#: The first published format's columns, spelled out here instead of generated from
#: ``baseline_frames.COLUMNS``: a fixture built from the live table follows an edit to it, so it
#: could never notice that the records already on disk no longer line up with what they were read as.
_OLD_FORMAT = "baseline-frames-1"
_OLD_COLUMNS = {
    "pos": "vec3", "yaw": "env", "velocity_yaw": "vec3", "command_world": "vec3",
    "head_tail_force": "env", "tilt_cos": "env", "non_foot_fraction": "bodies",
    "mesh_min_z": "bodies", "foot_contact": "feet", "foot_fraction": "feet",
    "terminated": "env", "timeout": "env",
}


def frame_frozen_digests(spec: dict) -> dict:
    """The digests that pin each format: the live declaration, and the stored block itself."""
    out = {}
    for fmt, block in spec["formats"].items():
        stored = {key: value for key, value in block.items()
                  if key not in ("columns_sha256", "frozen_sha256")}
        out[fmt] = {"columns_sha256": record.digest(baseline_frames.format_spec(fmt)),
                    "frozen_sha256": record.digest(stored)}
    return out


def test_frame_semantics_are_frozen():
    """Every format's declaration is still the one its published name stands for."""
    spec = json.loads(_FRAMES_SEMANTICS_PATH.read_text(encoding="utf-8"))
    digests = frame_frozen_digests(spec)
    assert spec["formats"], "an empty table pins nothing"
    for fmt, block in spec["formats"].items():
        module = importlib.import_module(block["module"])
        assert getattr(module, block["constant"]) == fmt, \
            f"{fmt}: {block['module']}.{block['constant']} says {getattr(module, block['constant'])!r}"
        live = module.format_spec(fmt)
        assert sorted(live["columns"]) == sorted(block["columns"]), (
            f"{fmt}: its columns changed ({sorted(live['columns'])} against {sorted(block['columns'])}). "
            "A published format keeps its columns: a new or renamed column is a new format name, and "
            "this one stays readable as what it was")
        for name, (kind, unit, meaning) in live["columns"].items():
            assert list(block["columns"][name]) == [kind, unit, meaning], (
                f"{fmt}/{name}: its declaration moved to {[kind, unit, meaning]}: a changed meaning, "
                "unit or shape is a new format, not an edit")
        assert list(live["axis_kinds"]) == block["axis_kinds"], f"{fmt}: its axis kinds changed"
        assert list(live["required_meta"]) == block["required_meta"], f"{fmt}: its required meta changed"
        assert digests[fmt]["columns_sha256"] == block["columns_sha256"], (
            f"{fmt}: the live declaration no longer matches the digest it was published under. Paste "
            f"{digests[fmt]['columns_sha256']} only if the move was approved, or restore the "
            "declaration (`--print-frames-frozen` prints both)")
        assert digests[fmt]["frozen_sha256"] == block["frozen_sha256"], (
            f"{fmt}: this block changed in place. Paste {digests[fmt]['frozen_sha256']} only as a "
            "deliberate re-pin: the records already naming this format point at the semantics it had")
        for case in block["cases"]:
            assert callable(globals().get(case)), \
                f"{fmt}: {case} is the case that pins this format's refusals, and it is gone"


def test_an_older_format_record_is_read_under_its_own_declaration():
    """A record is judged by the format it names, not by the newest table this reader holds."""
    assert {name: kind for name, (kind, _, _) in
            baseline_frames.format_spec(_OLD_FORMAT)["columns"].items()} == _OLD_COLUMNS, (
        "the oldest format's declaration moved: the records already written under it would be read "
        "as columns they never had")
    artifact = build(PROTOCOL, 20, fmt=_OLD_FORMAT)
    assert artifact["format"] == _OLD_FORMAT, artifact["format"]
    result = baseline_metrics.judge(artifact)
    assert result["verdict"] == "pass", (result["invalid_reasons"], result["gates"])
    assert not any("does not declare" in reason for reason in result["invalid_reasons"])


def test_an_unknown_format_is_refused_not_read_as_the_newest():
    """A format this reader does not know is unreadable, not silently judged as the newest one."""
    artifact = build(PROTOCOL, 20)
    artifact["format"] = "baseline-frames-99"
    result = baseline_metrics.judge(artifact)
    assert result["verdict"] == "invalid", result["gates"]
    assert any("baseline-frames-99" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]
    assert all(value is None for value in result["gates"].values()), "an unreadable record judges nothing"
    assert result["metrics"] == {} and result["per_env"] == {}, "nor does it report numbers"

    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "eval.frames.pt"
        torch.save(artifact, path)
        err = expect(baseline_frames.FramesContractError, baseline_frames.load, path)
        assert "baseline-frames-99" in str(err), err


def test_a_per_foot_vector_needs_one_point_per_foot():
    """A foot reading is per foot: the newest format's axis-carrying vec3 has to fit its labels."""
    recorder = baseline_frames.BaselineFrames(num_envs=2, step_dt=0.02, axes=AXES)
    frame = default_frame(2, recorder.columns)
    frame["foot_lin_vel"] = torch.zeros(2, 2)  # (N, F): the trailing vector is missing
    err = expect(baseline_frames.FramesContractError, recorder.add, **frame)
    assert "foot_lin_vel" in str(err) and "(2, 2, 3)" in str(err), err


def test_the_newest_format_demands_where_its_foot_geometry_came_from():
    """The provenance of the foot reading travels with the record, or the record is not judgeable."""
    artifact = build(PROTOCOL, 20)
    assert artifact["format"] == baseline_frames.FORMAT, artifact["format"]
    assert sorted(artifact["meta"]["foot_geometry"]) == sorted(FEET), artifact["meta"]["foot_geometry"]
    assert artifact["meta"]["ground_source"]["kind"] == "plane"

    del artifact["meta"]["foot_geometry"]
    result = baseline_metrics.judge(artifact)
    assert result["verdict"] == "invalid", result["gates"]
    assert any("foot_geometry" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]
    assert all(value is None for value in result["gates"].values()), result["gates"]


def test_a_new_format_does_not_move_an_old_records_verdict():
    """Two formats, one policy: extra columns may not change what the same run is judged to be."""
    old = baseline_metrics.judge(build(PROTOCOL, 20, fmt=_OLD_FORMAT))
    new = baseline_metrics.judge(build(PROTOCOL, 20))
    assert old["verdict"] == new["verdict"] == "pass", (old["invalid_reasons"], new["invalid_reasons"])
    assert old["gates"] == new["gates"], (old["gates"], new["gates"])
    assert old["metrics"] == new["metrics"], (old["metrics"], new["metrics"])
    added = set(new["axes"]) - set(old["axes"])
    assert added == {"foot_lowest_point", "foot_com_pos", "foot_lin_vel", "foot_ang_vel"}, added


def test_a_saved_record_is_written_whole_and_never_over_one_that_exists():
    """The record is the evidence: it lands in one piece, and a second collection takes a new path."""
    artifact = build(PROTOCOL, 20)
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "eval.frames.pt"
        baseline_frames.save(path, artifact)
        assert baseline_frames.load(path)["format"] == artifact["format"]
        assert baseline_frames.load(path)["meta"]["steps"] == 20
        err = expect(FileExistsError, baseline_frames.save, path, artifact)
        assert "already exists" in str(err), err
        assert baseline_frames.load(path)["frames"].keys() == artifact["frames"].keys()

        # A write that dies half way leaves nothing that could pass for a complete window.
        half = pathlib.Path(tmp) / "half.frames.pt"

        def dies(*args, **kwargs):
            raise RuntimeError("no space left on device")

        original, torch.save = torch.save, dies
        try:
            expect(RuntimeError, baseline_frames.save, half, artifact)
        finally:
            torch.save = original
        assert not half.exists(), "a failed write must not leave a record behind"
        assert not list(pathlib.Path(tmp).glob("half.frames.pt.*.tmp")), "the temp file has to go"


def test_the_window_is_saved_before_it_is_judged():
    """The one ordering a judge defect must not be able to undo, read off the real ``run``.

    The offline half is :func:`test_a_judge_failure_names_the_record_to_retry_from`; this is the
    half that cannot be exercised without a simulator, so it is read as the order of two calls
    inside ``run`` rather than left to the next 20 s rollout to notice.
    """
    source = ast.parse((_REPO / "ablation_harness" / "baseline_eval.py").read_text(encoding="utf-8"))
    run = next(node for node in source.body
               if isinstance(node, ast.FunctionDef) and node.name == "run")
    at = {"save": None, "judge": None}
    for node in ast.walk(run):
        if isinstance(node, ast.Call):
            called = ast.unparse(node.func)
            if called.endswith("baseline_frames.save"):
                at["save"] = node.lineno
            elif called.endswith("judged_or_recoverable"):
                at["judge"] = node.lineno
    assert at["save"] and at["judge"], f"run does not both save and judge: {at}"
    assert at["save"] < at["judge"], (
        f"the window is judged on line {at['judge']} before it is saved on line {at['save']}: a judge "
        "defect would then cost a completed collection")


def test_a_judge_failure_names_the_record_to_retry_from():
    """A judge defect must not cost the window: the error names the file that re-judges it offline."""
    from ablation_harness import baseline_eval

    artifact = build(PROTOCOL, 20)
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "eval.frames.pt"
        assert baseline_eval.judged_or_recoverable(artifact, path) == baseline_metrics.judge(artifact)

        def dies(subject):
            raise RuntimeError("Expected all tensors to be on the same device, but found cuda:0 and cpu")

        original, baseline_metrics.judge = baseline_metrics.judge, dies
        try:
            err = expect(RuntimeError, baseline_eval.judged_or_recoverable, artifact, path)
        finally:
            baseline_metrics.judge = original
        assert str(path) in str(err), err
        assert "python -m ablation_harness.baseline_metrics" in str(err), err
        assert isinstance(err.__cause__, RuntimeError), "the judge's own error has to stay reachable"


# --- the foot criteria: what the gait kind cannot see -------------------------------------------

def test_the_walk_reference_passes_both_foot_criteria():
    result = baseline_metrics.judge(feet_walk(build(FOOTED_PROTOCOL, 20)))
    assert result["verdict"] == "pass", (result["invalid_reasons"], result["gates"])
    assert result["gates"]["foot_lift"] and result["gates"]["foot_slip"], result["gates"]
    assert [round(v, 3) for v in result["diagnostics"]["foot_clearance_swing_m"]] == [0.06] * len(FEET), \
        result["diagnostics"]
    assert result["diagnostics"]["foot_swing_frames"] == [10] * len(FEET), result["diagnostics"]
    assert result["report_groups"]["behaviour"].count("foot_slip_mps") == 1


def test_a_swing_that_never_lifts_fails_the_lift_criterion():
    result = baseline_metrics.judge(feet_walk(build(FOOTED_PROTOCOL, 20), lift_m=0.0))
    assert result["verdict"] == "fail" and result["gates"]["foot_lift"] is False, result["gates"]
    assert result["gates"]["foot_slip"] is True, "the slip reading is a different question"
    assert result["metrics"]["foot_lift_feet_least"] == 0, result["metrics"]


def test_a_loaded_foot_sliding_at_its_contact_point_fails_the_slip_criterion():
    result = baseline_metrics.judge(feet_walk(build(FOOTED_PROTOCOL, 20), slip_mps=0.4))
    assert result["verdict"] == "fail" and result["gates"]["foot_slip"] is False, result["gates"]
    assert result["gates"]["foot_lift"] is True, "a sliding foot may still lift clear"
    assert result["metrics"]["foot_slip_fraction_worst"] == 1.0, result["metrics"]
    assert [round(v, 3) for v in result["diagnostics"]["foot_slip_mps"]] == [0.4] * len(FEET), result["diagnostics"]


def test_a_foot_that_only_pivots_slips_at_the_point_while_its_body_does_not_move():
    """The case a body-origin reading calls zero: omega x r moves the contact, not the body."""
    artifact = feet_walk(build(FOOTED_PROTOCOL, 20), spin_rad_s=5.0)
    assert float(artifact["frames"]["foot_lin_vel"].norm(dim=-1).max()) == 0.0, "the body is not moving"
    result = baseline_metrics.judge(artifact)
    assert result["gates"]["foot_slip"] is False, result["diagnostics"]["foot_slip_mps"]
    assert result["diagnostics"]["foot_slip_mps"][0] > 0.09, result["diagnostics"]  # 5 rad/s x 0.02 m


def test_a_foot_descending_onto_the_ground_is_not_sliding():
    """Only the tangential part is slip: a foot landing at 2 m/s is not being dragged."""
    result = baseline_metrics.judge(feet_walk(build(FOOTED_PROTOCOL, 20), descend_mps=2.0))
    assert result["gates"]["foot_slip"] is True, result["diagnostics"]["foot_slip_mps"]


def test_a_record_without_the_foot_columns_cannot_be_judged_by_the_foot_criteria():
    """A criterion over a quantity the run never measured is invalid, never a fail."""
    result = baseline_metrics.judge(build(FOOTED_PROTOCOL, 20, fmt=_OLD_FORMAT))
    assert result["verdict"] == "invalid", result["gates"]
    assert any("foot_lowest_point" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]
    assert all(value is None for value in result["gates"].values()), result["gates"]


def test_only_the_reader_that_declares_its_reports_can_be_asked_for_one_nobody_computes():
    """The completeness check lands on the new id and leaves the published verdicts alone."""
    undeclared = dict(FOOTED_PROTOCOL, report_only=["foot_yaw_deg", "foot_slip_mps"])
    result = baseline_metrics.judge(feet_walk(build(undeclared, 20)))
    assert result["verdict"] == "invalid", result["gates"]
    assert any("foot_yaw_deg" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]

    # The frozen family protocol declares items this judge does not compute, and its own reader keeps
    # reading it: a published verdict is not invalidated by a later tightening of a *newer* reader.
    frozen = json.loads((_REPO / "ablation_harness/protocols/lizard2_flat_v2.json").read_text())
    assert set(frozen["report_only"]) - set(baseline_metrics.REPORT_ITEMS), "the list is fully implemented"
    old = baseline_metrics.judge(feet_walk(build(frozen, 20)))
    assert old["judge"]["id"] == baseline_metrics.BANDED_SETTLED_JUDGE_ID, old["judge"]
    assert old["invalid_reasons"] == [], old["invalid_reasons"]
    assert old["verdict"] in ("pass", "fail"), old["verdict"]


def test_every_reader_this_module_implements_has_a_frozen_block():
    """A reader without a block is a semantics change nobody pinned; the table is the gate."""
    spec = json.loads(_SEMANTICS_PATH.read_text(encoding="utf-8"))
    for judge_id, kinds in baseline_metrics.JUDGE_KINDS.items():
        block = spec["ids"].get(judge_id)
        assert block is not None, f"{judge_id} can be named by a protocol but nothing pins its kinds"
        assert set(block["kinds"]) == set(kinds), (judge_id, block["kinds"], kinds)


# --- fixed scenes: one command per env, held for the whole window -------------------------------
#
# ``SCENE_PROTOCOL`` lives with the other protocols, after ``V4_PROTOCOL``; the fixtures here only
# read it when a test runs.


def scene_window(*, num_envs: int = 6, assign: bool = True, collide: int | None = None,
                 kill: int | None = None, shift_env: int | None = None) -> dict:
    """A window under :data:`SCENE_PROTOCOL`, each env's frames carrying its assigned scene's command.

    ``assign=False`` leaves the record with no assignment at all, ``collide`` folds one scene onto
    another (so an env was never assigned it), ``kill`` ends one scene's envs on frame 0, and
    ``shift_env`` gives one env a command its scene does not declare.
    """
    artifact = build(SCENE_PROTOCOL, 20, num_envs=num_envs)
    scenes = SCENE_PROTOCOL["scenes"]
    if not assign:
        return artifact
    assignment = command_player.scene_assignment(scenes, num_envs, 11)
    if collide is not None:
        assignment = torch.where(assignment == collide, torch.zeros_like(assignment), assignment)
    block = command_player.scene_commands(scenes, assignment, num_envs, "cpu")
    artifact["frames"]["command_world"] = block.unsqueeze(0).expand(20, num_envs, 3).clone()
    if shift_env is not None:
        artifact["frames"]["command_world"][:, shift_env, 0] += 1.0
    if kill is not None:
        artifact["frames"]["terminated"][:, assignment == kill] = 1.0
    artifact["meta"] = dict(artifact["meta"], scenes={
        "declared": [dict(scene) for scene in scenes], "assignment": assignment.tolist(),
        "resampling_frozen": True, "seed": 11})
    return artifact


def test_a_scene_assignment_covers_every_scene_and_does_not_fix_scene_to_env():
    """Round-robin sets the counts so no band can be empty; the seed decides which envs, not how many."""
    scenes = SCENE_PROTOCOL["scenes"]
    assignment = command_player.scene_assignment(scenes, 6, 11)
    assert [int((assignment == index).sum()) for index in range(len(scenes))] == [2, 2, 2]
    assert command_player.scene_assignment(scenes, 6, 11).tolist() == assignment.tolist(), "not reproducible"
    other = command_player.scene_assignment(scenes, 6, 12)
    assert sorted(other.tolist()) == sorted(assignment.tolist()), "the counts are the point, not the order"
    assert other.tolist() != assignment.tolist(), "a fixed pairing would confound a band with its env"
    uneven = command_player.scene_assignment(scenes, 4, 3)
    assert sorted(int((uneven == index).sum()) for index in range(len(scenes))) == [1, 1, 2]


def test_scene_commands_put_each_env_under_its_own_scene():
    scenes = SCENE_PROTOCOL["scenes"]
    assignment = command_player.scene_assignment(scenes, 6, 11)
    block = command_player.scene_commands(scenes, assignment, 6, "cpu")
    for env in range(6):
        assert block[env, 0].item() == scenes[int(assignment[env])]["vx"], env


def test_a_scene_window_without_its_assignment_is_invalid():
    result = baseline_metrics.judge(scene_window(assign=False))
    assert result["verdict"] == "invalid", result["gates"]
    assert any("which scene each env walked" in reason for reason in result["invalid_reasons"]), \
        result["invalid_reasons"]


def test_a_declared_scene_that_measured_nothing_is_named():
    """Coverage is why the block exists: a band nobody measured is refused, not left silently empty."""
    collision = baseline_metrics.judge(scene_window(collide=2))
    assert collision["verdict"] == "invalid", collision["gates"]
    assert any("assigned to no env" in reason for reason in collision["invalid_reasons"]), \
        collision["invalid_reasons"]

    # The weaker case stays a reading rather than a refusal: an env that ended on frame 0 still has
    # that frame inside its episode, and the report has to distinguish "two frames" from "coverage".
    killed = baseline_metrics.judge(scene_window(kill=1))
    assert killed["invalid_reasons"] == [], killed["invalid_reasons"]
    assert killed["diagnostics"]["scene_valid_frames"]["mid_2mps"] == 2, killed["diagnostics"]
    assert killed["diagnostics"]["scene_valid_frames"]["slow_1mps"] == 40, killed["diagnostics"]


def test_the_recorded_commands_must_match_the_assigned_scene():
    """The check a broadcast-only injection cannot pass: env 0's frames carry another scene's command."""
    result = baseline_metrics.judge(scene_window(shift_env=0))
    assert result["verdict"] == "invalid", result["gates"]
    assert any("disagree" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]


def test_a_scene_window_reports_how_many_valid_frames_each_scene_got():
    result = baseline_metrics.judge(scene_window())
    assert result["invalid_reasons"] == [], result["invalid_reasons"]
    assert set(result["diagnostics"]["scene_valid_frames"]) == {"slow_1mps", "mid_2mps", "fast_3mps"}
    assert all(count == 2 * 20 for count in result["diagnostics"]["scene_valid_frames"].values()), \
        result["diagnostics"]["scene_valid_frames"]
    assert result["report_groups"]["measurement"].count("scene_valid_frames") == 1


def test_v2_refuses_a_gate_it_could_not_measure():
    """Unmeasured is unknown, and unknown is not a pass."""
    artifact = build(V2_PROTOCOL, 20)
    del artifact["frames"]["tilt_cos"]
    result = baseline_metrics.judge(artifact)
    assert result["verdict"] == "invalid"
    assert any("never measured" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]
    assert all(value is None for value in result["gates"].values()), result["gates"]


# --- the record's own length and initial state: asked for by review, neither was checked -------

def test_window_length_must_equal_the_protocol_window():
    """1000 frames of a 20 s protocol is a 20 s window; of a 40 s protocol it is half of one."""
    artifact = build(PROTOCOL, 20)
    artifact["meta"]["step_dt"] = 0.04  # 20 x 0.04 = 0.8 s, not the protocol's 20 s
    result = baseline_metrics.judge(artifact)
    assert result["verdict"] == "invalid", result["gates"]
    assert any("the protocol declares 20 s" in reason for reason in result["invalid_reasons"]), \
        result["invalid_reasons"]
    assert all(value is None for value in result["gates"].values())


def test_the_initial_state_is_checked_for_shape_and_finiteness():
    wrong = build(PROTOCOL, 20)
    wrong["meta"]["start_pos"] = torch.zeros(3)
    result = baseline_metrics.judge(wrong)
    assert result["verdict"] == "invalid"
    assert any("start_pos has shape" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]

    broken = build(PROTOCOL, 20)
    broken["meta"]["start_yaw"] = torch.tensor([float("nan")])
    result = baseline_metrics.judge(broken)
    assert result["verdict"] == "invalid"
    assert any("start_yaw is not finite" in reason for reason in result["invalid_reasons"]), \
        result["invalid_reasons"]

    weightless = build(PROTOCOL, 20)
    del weightless["meta"]["body_weight_n"]
    assert baseline_metrics.judge(weightless)["verdict"] == "invalid", "no weight, no newtons"


def test_a_record_is_refused_under_a_protocol_it_was_not_collected_for():
    """The v1 drag record was collected at a constant 0.5 m/s; v3 asks for 1-3 m/s."""
    artifact = build(PROTOCOL, 20)  # command 0.5, inside v1's degenerate box
    artifact["protocol"] = V3_PROTOCOL
    result = baseline_metrics.judge(artifact)
    assert result["verdict"] == "invalid", result["gates"]
    assert any("different command protocol" in reason for reason in result["invalid_reasons"]), \
        result["invalid_reasons"]


# --- v3's two relative axes and its contact axis -----------------------------------------------

def test_v3_normalized_tracking_scores_the_band_not_one_number():
    """Holding the band it was given is the question a 1-3 m/s task asks."""
    dt = V3_PROTOCOL["episode_length_s"] / 100
    on_band = baseline_metrics.judge(build(V3_PROTOCOL, 100))          # commands 2.0, walks 2.0
    assert on_band["gates"]["tracking"], on_band["metrics"]
    assert on_band["metrics"]["forward_mae_norm"] < 1e-6, on_band["metrics"]
    assert abs(on_band["metrics"]["forward_mae_mps"]) < 1e-6, on_band["metrics"]
    assert on_band["verdict"] == "pass", (on_band["gates"], on_band["metrics"])

    # A robot nailing the absolute 2.0 m/s while the command alternates 1.0 and 3.0: half the
    # frames are 1.0 m/s off, half are 1 m/s over on a 3 m/s ask (1/3) -- the normalized error
    # says it is off the band, which the mean absolute error cannot.
    def command(step):
        return torch.tensor([[1.0 if step % 2 else 3.0, 0.0, 0.0]])

    def velocity(step):
        return torch.tensor([[2.0, 0.0, 0.0]])

    wandering = baseline_metrics.judge(build(V3_PROTOCOL, 100, series={
        "pos": lambda step: torch.tensor([[(step + 1) * 2.0 * dt, 0.0, 0.0]]),
        "command_world": command, "velocity_yaw": velocity,
    }))
    assert not wandering["gates"]["tracking"], wandering["metrics"]
    assert abs(wandering["metrics"]["forward_mae_norm"] - (1.0 + 1.0 / 3.0) / 2.0) < 1e-6, \
        wandering["metrics"]


def test_v3_displacement_is_measured_against_the_distance_asked_for():
    """A policy that covers half the distance its commands asked for fails; the full 20 s is the ask."""
    dt = V3_PROTOCOL["episode_length_s"] / 100
    short = baseline_metrics.judge(build(V3_PROTOCOL, 100, series={
        "pos": lambda step: torch.tensor([[(step + 1) * 1.0 * dt, 0.0, 0.0]]),  # 1.0 of the 2.0 asked
        "velocity_yaw": lambda step: torch.tensor([[1.0, 0.0, 0.0]]),
    }))
    assert not short["gates"]["displacement"], short["metrics"]
    assert abs(short["metrics"]["displacement_frac"] - 0.5) < 1e-5, short["metrics"]
    assert not short["gates"]["tracking"], "walking at half the issued speed is off band too"
    on_band = baseline_metrics.judge(build(V3_PROTOCOL, 100))
    assert abs(on_band["metrics"]["displacement_frac"] - 1.0) < 1e-5, on_band["metrics"]


def test_v3_head_chain_contact_is_the_training_termination_criterion():
    """Same predicate as the training termination: a chest/neck reaction above 1 N on any frame."""
    clean = baseline_metrics.judge(build(V3_PROTOCOL, 100))
    assert clean["gates"]["no_non_foot_contact"], clean["metrics"]
    assert clean["metrics"]["non_foot_contact_load_n_max"] == 0.0, clean["metrics"]

    # 1 N / 706.32 N of body weight is the limit; the v1 drag record's neck is 87.2 N.
    touching = baseline_metrics.judge(build(V3_PROTOCOL, 100, series={
        "non_foot_fraction": lambda step: torch.tensor([[0.0, 1.5 / BODY_WEIGHT_N]]),
    }))
    assert not touching["gates"]["no_non_foot_contact"], touching["metrics"]
    assert abs(touching["metrics"]["non_foot_contact_load_n_max"] - 1.5) < 1e-3, touching["metrics"]
    assert touching["diagnostics"]["non_foot_contact_frames"][1] == 100, touching["diagnostics"]

    legitimate = baseline_metrics.judge(build(V3_PROTOCOL, 100, series={
        "non_foot_fraction": lambda step: torch.tensor([[0.0, 0.9 / BODY_WEIGHT_N]]),
    }))
    assert legitimate["gates"]["no_non_foot_contact"], "below the contact limit is not contact"


def test_v3_keeps_the_two_samples_apart():
    """A kept anomaly sample must stay red and a clean run green: neither sets the other's numbers."""
    dragging = baseline_metrics.judge(build(V3_PROTOCOL, 1000, series={
        "non_foot_fraction": lambda step: torch.tensor([[0.0, 87.2 / BODY_WEIGHT_N]]),
        "mesh_min_z": lambda step: torch.tensor([[0.18, -0.0046]]),
        "tilt_cos": lambda step: torch.tensor([0.9]),
        "foot_contact": lambda step: torch.tensor([[1.0, 0.0]]),
        "foot_fraction": lambda step: torch.tensor([[0.3, 0.0]]),
    }))
    assert dragging["verdict"] == "fail", dragging["gates"]
    assert dragging["gates"]["no_non_foot_contact"] is False, "87.2 N on the neck is a support"
    assert dragging["metrics"]["non_foot_contact_load_n_max"] > 87.0
    assert abs(dragging["metrics"]["non_foot_mesh_min_z_m"] + 0.0046) < 1e-6, \
        "the mesh reading is reported even where the protocol does not gate it"
    clean = baseline_metrics.judge(build(V3_PROTOCOL, 1000))
    assert clean["verdict"] == "pass", (clean["gates"], clean["metrics"])
    assert clean["metrics"]["non_foot_mesh_min_z_m"] == 0.5


def test_v3_the_two_axes_no_sample_ever_exercised_can_still_fail():
    """Survival and attitude were only ever seen GREEN: assert the other side here.

    Both of the line's real samples (a zero-action rollout and a random checkpoint) live out the
    window and stay inside 40 deg, so those two gates only ever had a passing side -- and nothing in
    this file ever asserted either of them as ``False``. A gate that can only pass is not a gate, so
    the failing side is built the way the other three axes already are: synthetic windows at the
    judge. An episode that never times out is a policy that fell, and 0.6 s held past cos(40 deg) is
    the dwell the protocol names.
    """
    fell = baseline_metrics.judge(build(V3_PROTOCOL, 1000, series={
        "timeout": lambda step: torch.tensor([0.0]),
    }))
    assert fell["gates"]["survival"] is False, fell["metrics"]
    assert fell["verdict"] == "fail", fell["gates"]

    held_past_the_dwell = baseline_metrics.judge(build(V3_PROTOCOL, 1000, series={
        "tilt_cos": lambda step: torch.tensor([0.6 if step < 30 else 0.999]),
    }))
    assert held_past_the_dwell["gates"]["attitude"] is False, held_past_the_dwell["diagnostics"]
    assert held_past_the_dwell["verdict"] == "fail", held_past_the_dwell["gates"]


# --- what the window measures ------------------------------------------------------------------

def test_fixed_window():
    assert score()["verdict"] == "pass"
    assert abs(score(yaw=1.57079632679)["metrics"]["forward_displacement_m"] - 10) < 1e-5
    failed = score(3)
    assert failed["metrics"]["forward_displacement_m"] == 2
    assert abs(failed["metrics"]["forward_mae_mps"] - 0.4) < 1e-6
    assert failed["metrics"]["first_episode_timeout_fraction"] == 0
    assert score(19, simultaneous=True)["metrics"]["first_episode_timeout_fraction"] == 0


def test_actual_reset_and_material():
    data = NS(joint_pos=NS(torch=torch.ones(2, 3)), default_joint_pos=NS(torch=torch.zeros(2, 3)),
              joint_vel=NS(torch=torch.ones(2, 3)), default_joint_vel=NS(torch=torch.zeros(2, 3)))
    robot = NS(data=data, num_instances=2, root_view=NS(get_material_properties=lambda: torch.ones(2, 4, 3)))
    assert len(joint_reset_errors(robot)) == 2
    data.joint_pos.torch.zero_()
    data.joint_vel.torch.zero_()
    assert joint_reset_errors(robot) == []
    assert material_errors(robot) == []
    materials = torch.ones(2, 4, 3)
    materials[1, 0, 0] = 0.5
    robot.root_view.get_material_properties = lambda: materials
    assert material_errors(robot)


def test_probe_registered_entry():
    # Execute the real main's setup through gym.make without importing/starting Kit.
    source = ast.parse((_REPO / "rl_exp/tools/verify/baseline_probe.py").read_text(encoding="utf-8"))
    fn = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    prefix = []
    for statement in fn.body:
        prefix.append(statement)
        if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "env" for t in statement.targets):
            break
    prefix.append(ast.Return(value=ast.Name(id="cfg", ctx=ast.Load())))
    fn.body = prefix
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    selected = NS(scene=NS(num_envs=1))
    wrong = NS(scene=NS(num_envs=1))
    # The stub carries every argument the probe's *early* CLI guards read, because the AST prefix
    # above stops at the `env = ...` line and those guards run before it: `shot` alone for now
    # (its `and` short-circuits, so the renderer flag is never reached).
    namespace = {
        "args_cli": NS(task="requested-play-task", num_envs=3, shot=False),
        "resolve_task_cfg": lambda task: selected if task == "requested-play-task" else None,
        "BaselineFlatEnvCfg": lambda: wrong,
        "gym": NS(make=lambda task, cfg, **kw: NS()),
    }
    exec(compile(module, "<probe setup>", "exec"), namespace)
    assert namespace["main"]() is selected, "probe ignored the requested registered entry"


def score_along_heading(yaw: float, *, steps: int = 20, speed: float = 0.5) -> dict:
    """A robot travelling at ``speed`` along its own heading for the whole window."""
    from ablation_harness.baseline_eval import yaw_of
    from isaaclab.utils.math import quat_from_euler_xyz

    quat = quat_from_euler_xyz(torch.zeros(1), torch.full((1,), 0.35), torch.tensor([yaw]))
    start_yaw = yaw_of(quat)

    def position(step):
        travel = (step + 1) * speed
        return torch.tensor([[travel * math.cos(yaw), travel * math.sin(yaw), 0.0]])

    return baseline_metrics.judge(build(PROTOCOL, steps, series={
        "pos": position, "yaw": lambda step: start_yaw.clone()}, start_yaw=start_yaw))


def test_eval_forward_axis_is_the_training_frame():
    """The evaluator's forward axis must be the operator the reward kernel uses, not a re-derivation."""
    from ablation_harness.baseline_eval import yaw_of
    from isaaclab.utils.math import quat_apply_inverse, quat_from_euler_xyz, wrap_to_pi, yaw_quat

    yaws = torch.tensor([0.0, math.pi / 2, math.pi, -2.0])
    quat = quat_from_euler_xyz(torch.zeros(4), torch.full((4,), 0.35), yaws)
    assert torch.allclose(wrap_to_pi(yaw_of(quat) - yaws), torch.zeros(4), atol=1e-5), \
        "yaw must survive a pitched base, unchanged"
    delta = torch.stack((10.0 * yaws.cos(), 10.0 * yaws.sin(), torch.zeros(4)), dim=-1)
    kernel_axis = quat_apply_inverse(yaw_quat(quat), delta)[:, 0]
    eval_axis = delta[:, 0] * yaw_of(quat).cos() + delta[:, 1] * yaw_of(quat).sin()
    assert torch.allclose(eval_axis, kernel_axis, atol=1e-4), \
        "the evaluator's projection must agree with the reward frame's operator"
    assert torch.allclose(eval_axis, torch.full((4,), 10.0), atol=1e-4), \
        "travelling along its own heading is forward, at every heading"


def test_eval_scores_equal_relative_motion_equally():
    """Same motion, different heading: the fixed window must not care which way it faces."""
    for yaw in (0.0, 1.2, -1.2, math.pi):
        result = score_along_heading(yaw)
        assert abs(result["metrics"]["forward_displacement_m"] - 10.0) < 1e-3, \
            f"yaw {yaw}: forward displacement must not depend on the heading"
        assert result["metrics"]["forward_mae_mps"] < 1e-6, f"yaw {yaw}: motion is exactly on command"
        assert result["verdict"] == "pass", f"yaw {yaw}: a perfectly tracked walk must pass"


# A hand-rolled yaw that reads the quaternion as (w, x, y, z) silently returns ~pi on (x, y, z, w)
# data, which flips the sign of every forward-displacement gate. Both spellings below are that bug.
_WXYZ_YAW = (
    re.compile(r"\[:\s*,\s*3\]\s*,\s*\w+\[:\s*,\s*0\]"),
    re.compile(r"\[:\s*,\s*0\]\s*\*\s*\w+\[:\s*,\s*3\]"),
)
_YAW_EXTRACTIONS_ALLOWED = {
    # kept on purpose: the wrong branch the diagnostics display next to the library's answer
    "rl_exp/tools/diagnose/diagnose_support.py": "对照 that proves the wrong branch wrong (see its comment)",
    # known bad, another line, decided 2026-09-22: its docstring claims (x, y, z, w) while its
    # math is the (w, x, y, z) branch. The line is retired and never trained -- its only log
    # directory holds the refusal manifest and nothing else -- so no reading needs reinterpretation
    # and the fix is not applied. Kept here so the debt stays visible instead of silent
    # (work/closed/2026/parkour-yaw-reinterpretation.md).
    "rl_exp/tasks/parkour_mdp.py": "parkour line's _yaw_from_quat: same bug class, line retired and never trained",
}


def test_no_hand_rolled_quat_yaw():
    """Only the library may turn a quaternion into an angle; a second opinion is a second truth."""
    offenders = []
    for root in ("rl_exp", "ablation_harness"):
        for path in sorted((_REPO / root).rglob("*.py")):
            key = path.relative_to(_REPO).as_posix()
            if key == "rl_exp/tools/verify/test_baseline_contract.py" or key in _YAW_EXTRACTIONS_ALLOWED:
                continue
            text = path.read_text(encoding="utf-8")
            if any(pattern.search(text) for pattern in _WXYZ_YAW):
                offenders.append(key)
    assert not offenders, (
        "hand-rolled quaternion yaw found; call yaw_quat / euler_xyz_from_quat instead: "
        f"{offenders}"
    )


# --- per-env, per-frame readings: every case below was measured live on 2026-09-21 -------------

def test_loads_are_measured_per_env():
    """The old reader averaged over envs, so 0.2 on one and 0 on the other read as a passing 0.1."""
    artifact = build(V2_PROTOCOL, 20, num_envs=2, series={
        "non_foot_fraction": lambda step: torch.tensor([[0.2, 0.0], [0.0, 0.0]]),
    })
    result = baseline_metrics.judge(artifact)
    assert abs(result["metrics"]["non_foot_load_fraction_max"] - 0.2) < 1e-6, result["metrics"]
    assert result["gates"]["no_non_foot_carrier"] is False, "20% of body weight must not be diluted by env 1"
    assert abs(result["diagnostics"]["non_foot_load_fraction"][0] - 0.2) < 1e-6, result["diagnostics"]


def test_foot_duty_counts_contact_frames():
    """bool + bool stays bool: the old accumulator could only report 0 or 1, never a duty cycle."""
    artifact = build(V2_PROTOCOL, 20, num_envs=2, series={
        "foot_contact": lambda step: torch.tensor([[1.0, 0.0], [1.0, 1.0]] if step < 15
                                                   else [[0.0, 1.0], [0.0, 1.0]]),
    })
    diagnostics = baseline_metrics.judge(artifact)["diagnostics"]
    assert [round(duty, 3) for duty in diagnostics["foot_duty"]] == [0.75, 0.625], diagnostics
    # env 0 has one foot down every frame; env 1 has both for 15 of 20 frames ((15*2 + 5)/20 = 1.75).
    assert abs(diagnostics["feet_down_mean"] - 1.375) < 1e-6, diagnostics


def test_respawn_frames_are_not_scored():
    """After env 0 dies its frames belong to another rollout: not its posture, not its position."""
    artifact = build(V2_PROTOCOL, 20, num_envs=2, series={
        "terminated": lambda step: torch.tensor([1.0 if step == 5 else 0.0, 0.0]),
        "mesh_min_z": lambda step: (torch.tensor([[-9.0, 0.5], [0.5, 0.5]]) if step > 5
                                    else torch.full((2, 2), 0.5)),
        "non_foot_fraction": lambda step: (torch.tensor([[0.9, 0.0], [0.0, 0.0]]) if step > 5
                                           else torch.zeros(2, 2)),
    })
    result = baseline_metrics.judge(artifact)
    assert result["gates"]["no_mesh_through_floor"], "a respawn 9 m under the floor is not env 0's posture"
    assert result["gates"]["no_non_foot_carrier"], "nor is it env 0's load"
    assert result["per_env"]["survived"] == [False, True], result["per_env"]
    assert abs(result["per_env"]["forward_displacement_m"][0] - 3.0) < 1e-5, \
        "env 0's displacement froze at its last frame"


def test_tracking_follows_the_command_issued_each_frame():
    """A range command is judged against what was issued that frame, not against a constant."""
    def command(step):
        return torch.tensor([[1.0 + 0.5 * (step % 3), 0.0, 0.0]])

    dt = V3_PROTOCOL["episode_length_s"] / 30
    artifact = build(V3_PROTOCOL, 30, series={
        "command_world": command, "velocity_yaw": command,
        "pos": lambda step: torch.tensor([[(step + 1) * 1.5 * dt, 0.0, 0.0]]),
    })
    result = baseline_metrics.judge(artifact)
    assert result["metrics"]["forward_mae_norm"] < 1e-6, "matching each frame's own command is on band"
    assert abs(result["metrics"]["command_mps_mean"] - 1.5) < 1e-6, result["metrics"]
    assert result["gates"]["tracking"] and result["gates"]["displacement"], result["gates"]

    lagging = baseline_metrics.judge(build(V3_PROTOCOL, 30, series={
        "command_world": command, "velocity_yaw": lambda step: torch.tensor([[2.5, 0.0, 0.0]]),
    }))
    assert not lagging["gates"]["tracking"], lagging["metrics"]
    assert lagging["metrics"]["forward_mae_norm"] > 0.2, lagging["metrics"]


def test_the_tilt_readout_is_the_worst_posture():
    """The largest cosine is the most upright frame; the reported figure must be the episode's worst."""
    artifact = build(V2_PROTOCOL, 1000, series={
        "tilt_cos": lambda step: torch.tensor([0.999 if step % 3 else 0.9]),
    })
    result = baseline_metrics.judge(artifact)
    assert result["gates"]["attitude"], "no breach lasts the 0.5 s dwell"
    assert abs(result["diagnostics"]["tilt_max_deg"] - math.degrees(math.acos(0.9))) < 0.05, result["diagnostics"]


def test_mesh_reading_survives_uneven_vertex_counts():
    """+inf padding became NaN inside quat_apply, so every mesh narrower than the widest read NaN."""
    clouds = [torch.rand(3, 3) * 0.1, torch.rand(7, 3) * 0.1]
    padded = pad_point_clouds(clouds)
    assert torch.isfinite(padded).all(), "padding must be a real point, not a poison value"
    pos = torch.zeros(2, 2, 3)
    quat = torch.tensor([0.3, 0.2, 0.1, 0.9])
    quat = quat / torch.linalg.norm(quat)
    quat = quat.expand(2, 2, 4)
    together = mesh_min_z(pos, quat, [0, 1], padded)
    assert torch.isfinite(together).all(), together
    for index, cloud in enumerate(clouds):
        alone = mesh_min_z(pos[:, index:index + 1], quat[:, index:index + 1], [0], cloud[None])
        assert torch.allclose(together[:, index], alone[:, 0]), "padding moved the minimum"


def test_v2_catches_what_v1_passed():
    """The neck-dragging rollout must fail v2 on the axes v1 never read, and pass nothing extra."""
    def drag_window(protocol, *, neck_fraction, mesh_z=-0.052, tilt_cos_value=0.9):
        return baseline_metrics.judge(build(protocol, 20, series={
            "tilt_cos": lambda step: torch.tensor([tilt_cos_value]),
            "non_foot_fraction": lambda step: torch.tensor([[0.01, neck_fraction]]),
            "mesh_min_z": lambda step: torch.tensor([[0.5, mesh_z]]),
            "foot_contact": lambda step: torch.tensor([[1.0, 0.0]]),
            "foot_fraction": lambda step: torch.tensor([[0.3, 0.0]]),
        }))

    dragging = drag_window(V2_PROTOCOL, neck_fraction=0.48)
    assert dragging["verdict"] == "fail"
    assert dragging["gates"]["tracking"] and dragging["gates"]["displacement"] \
        and dragging["gates"]["survival"], "the v1 axes really are nominal in this rollout"
    assert not dragging["gates"]["no_non_foot_carrier"], "48% of body weight on the neck must not pass"
    assert not dragging["gates"]["no_mesh_through_floor"], "a mesh 5 cm below ground must not pass"
    assert dragging["gates"]["attitude"], "26 deg of tilt is inside the fall predicate, not a gate hit"
    assert drag_window(PROTOCOL, neck_fraction=0.48)["verdict"] == "pass", \
        "the v1 protocol is the thing that passed this; that is the gap v2 closes"
    clean = drag_window(V2_PROTOCOL, neck_fraction=0.02, mesh_z=0.4, tilt_cos_value=0.999)
    assert clean["verdict"] == "pass", clean["gates"]


def test_v2_sustain_filter_ignores_a_single_frame():
    """A one-frame spike is contact noise; a sustained one is the gate."""
    single = baseline_metrics.judge(build(V2_PROTOCOL, 1000, series={
        "tilt_cos": lambda step: torch.tensor([0.1 if step == 5 else 0.999]),
        "non_foot_fraction": lambda step: torch.tensor([[0.9 if step == 5 else 0.01, 0.0]]),
    }))
    assert single["gates"]["attitude"], "one tilted frame is a bump, not a fall"
    assert single["gates"]["no_non_foot_carrier"], "one loaded frame is a bump, not a carrier"
    held = baseline_metrics.judge(build(V2_PROTOCOL, 1000, series={
        "non_foot_fraction": lambda step: torch.tensor([[0.9 if step >= 5 else 0.01, 0.0]]),
    }))
    assert not held["gates"]["no_non_foot_carrier"], "a body loaded for the rest of the window is a carrier"


def test_termination_injection_is_independent_of_wiring():
    forces = torch.zeros(2, 3, 2, 3)
    clock = torch.zeros(2)
    cfg = NS(params={"threshold": 1.0, "sensor_cfg": NS(body_ids=[0])})
    outputs = {}

    def compute():
        ids = cfg.params["sensor_cfg"].body_ids
        outputs["base_contact"] = (forces[:, :, ids].norm(dim=-1).amax(dim=(1, 2)) > 1)
        outputs["time_out"] = clock >= 1000

    manager = NS(compute=compute, get_term_cfg=lambda name: cfg, get_term=lambda name: outputs[name])
    sensor = NS(body_names=["base_link", "rf_foot"], data=NS(net_forces_w_history=NS(torch=forces)))
    env = NS(termination_manager=manager, scene=NS(sensors={"contact_forces": sensor}),
             episode_length_buf=clock, max_episode_length=1000, num_envs=2, device="cpu")
    assert termination_errors(env) == []
    assert forces.count_nonzero() == 0 and clock.count_nonzero() == 0
    cfg.params["sensor_cfg"].body_ids = [1]
    assert termination_errors(env), "a contact term wired to a foot must fail the base injection"


# --- the judge's criteria: kinds, boundaries, and the frozen case table -------------------------
#
# ablation_harness/judge_semantics.json pins each judge id to the cases that define it, and each
# case to the verdict and gate outcomes it must produce. One frozen sample could not do this job: a
# sample covers only the behaviour it happens to touch, so an edit outside that path would leave the
# id unchanged while the semantics moved. The table is frozen by digest -- editing a block that
# already shipped is red, so a changed criterion needs a NEW kind and a new id.
#
#     python rl_exp/tools/verify/test_baseline_contract.py --print-frozen
#
# prints the digests to paste after deliberately publishing a new id.
V4_PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/baseline_flat_v4.json").read_text())
LIZARD2_PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/lizard2_flat_v1.json").read_text())
#: The same protocol with the settled banded kinds (``settle_s``): a band's first frames are not
#: evidence, so it is a reader of its own rather than a re-pinned parameter on the one above.
LIZARD2_SETTLED_PROTOCOL = json.loads(
    (_REPO / "ablation_harness/protocols/lizard2_flat_v2.json").read_text())
_SEMANTICS_PATH = _REPO / "ablation_harness" / "judge_semantics.json"
_STEP_DT = 0.02  # every fixture below runs the protocol's 20 s window in 1000 steps

#: The frozen criteria protocol with the foot criteria added, read by the reader that can read them.
#: Its other criteria are reused as they are, so a foot case fails on a foot gate rather than on the
#: window being unusual in some other way: the foot criteria exist next to the ones already there.
FOOTED_PROTOCOL = {
    **V4_PROTOCOL,
    "judge": baseline_metrics.FOOTED_JUDGE_ID,
    "criteria": {
        **V4_PROTOCOL["criteria"],
        "foot_lift": {"kind": "foot_lift_v1",
                      "params": {"min_lift_m": 0.03, "band_mps": 0.5, "min_feet": 2}},
        "foot_slip": {"kind": "foot_slip_v1",
                      "params": {"max_slip_mps": 0.05, "min_load": 0.05, "max_slip_fraction": 0.02}},
    },
    "report_only": ["forward_mae_mps", "foot_slip_mps", "foot_clearance_swing_m", "foot_duty",
                    "foot_swing_frames", "foot_ground_source"],
}

#: A protocol that declares fixed scenes -- one constant command per env, held for the whole window --
#: with every scene inside the box the same protocol already declares.
SCENE_PROTOCOL = {
    **V4_PROTOCOL,
    "scenes": [{"name": "slow_1mps", "vx": 1.0}, {"name": "mid_2mps", "vx": 2.0},
               {"name": "fast_3mps", "vx": 3.0}],
}


def _fixture_plain(kw):
    """A clean run on the command: every declared gate passes."""
    return V4_PROTOCOL, build(V4_PROTOCOL, 1000, num_envs=2)


def _fixture_tilt_hold(kw):
    """The base tilted below the threshold for exactly ``seconds``, then upright."""
    frames = max(1, int(round(kw["seconds"] / _STEP_DT)))

    def tilt(step):
        return torch.full((2,), 0.5 if step < frames else 1.0)

    return V4_PROTOCOL, build(V4_PROTOCOL, 1000, num_envs=2, series={"tilt_cos": tilt})


def _fixture_contact(kw):
    """One frame with a non-foot body at (or just above) the declared load limit."""
    # The criterion's own conversion, so "exactly at the limit" is exactly the same float.
    limit = 1.0 / BODY_WEIGHT_N
    fraction = limit if kw["fraction"] == "at_limit" else limit + 1e-3

    def non_foot(step):
        return torch.tensor([[fraction if step == 5 else 0.0, 0.0]] * 2)

    return V4_PROTOCOL, build(V4_PROTOCOL, 1000, num_envs=2, series={"non_foot_fraction": non_foot})


def _fixture_tracking_at_threshold(kw):
    """Speed error and distance exactly at their thresholds (0.25 of the command, 0.75 of it).

    Both numbers have to be exact in binary -- 1024 steps of a 20 s window, so the step is 5/256 s
    and neither the commanded distance nor the measured one picks up a representation error. A
    threshold case that lands on rounding tests the float, not the comparison. The distance is
    summed over the window, which is why a 1000-step window cannot be used here: 1000 x 0.02 already
    lands a few ulps off.
    """
    steps = 1024
    dt = V4_PROTOCOL["episode_length_s"] / steps
    protocol = json.loads(json.dumps(V4_PROTOCOL))
    protocol["criteria"]["tracking"]["params"] = {"threshold": 0.25, "normalized": True}
    protocol["criteria"]["displacement"]["params"] = {"threshold": 0.75, "normalized": True}

    def velocity(step):
        return torch.tensor([[1.5, 0.0, 0.0]] * 2)

    def position(step):
        return torch.tensor([[(step + 1) * 1.5 * dt, 0.0, 0.0]] * 2)

    return protocol, build(protocol, steps, num_envs=2, series={"velocity_yaw": velocity, "pos": position})


def _fixture_carrier_hold(kw):
    """One body carrying at least the declared fraction for exactly ``seconds``."""
    frames = max(1, int(round(kw["seconds"] / _STEP_DT)))

    def non_foot(step):
        return torch.tensor([[kw["fraction"] if step < frames else 0.0, 0.0]] * 2)

    return V2_PROTOCOL, build(V2_PROTOCOL, 1000, num_envs=2, series={"non_foot_fraction": non_foot})


def _fixture_carrier_alternating(kw):
    """Two bodies taking turns for ``span_s``: each is loaded for single frames only.

    This is the case the aggregation order decides. Body by body no run reaches two frames, so a
    "one body held it" criterion would pass; the declared criterion merges the bodies first, so a
    span at the declared dwell (0.5 s) is one sustained reading and the gate fails, while a span
    just under it passes. ``test_carrier_aggregation_merges_bodies_before_time`` asserts the
    per-body reading that makes the difference.
    """
    span = max(1, int(round(kw["span_s"] / _STEP_DT)))

    def non_foot(step):
        if step >= span:
            return torch.zeros(2, 2)
        row = [0.0, 0.0]
        row[step % 2] = 0.9
        return torch.tensor([row] * 2)

    return V2_PROTOCOL, build(V2_PROTOCOL, 1000, num_envs=2, series={"non_foot_fraction": non_foot})


def _fixture_mesh_at_threshold(kw):
    """A body's lowest mesh vertex exactly at the declared floor."""
    def mesh(step):
        return torch.tensor([[-0.01, 0.5]] * 2)

    return V2_PROTOCOL, build(V2_PROTOCOL, 1000, num_envs=2, series={"mesh_min_z": mesh})


_LOCO_CACHE: dict = {}


def _loco_protocol() -> dict:
    """A fresh copy of the runnable locomotion protocol (v3; v4 is not unlocked until fingerprinted)."""
    if "v3" not in _LOCO_CACHE:
        _LOCO_CACHE["v3"] = _load_protocol_dict("locomotion_eval_v3.yaml")
    return json.loads(json.dumps(_LOCO_CACHE["v3"]))


def _fixture_loco_derivation(kw):
    """The declared fall clause as the numbers the kernels are handed, overridden per case.

    The floats are rounded to 9 decimals: ``cos`` comes from the platform's libm, and the last bits
    of ``cos(radians(40))`` are not portable across machines. Rounding keeps the case stable
    anywhere, at the cost of not seeing a change below 1e-9 -- the honest ceiling of a frozen
    expectation that has to survive a machine swap.
    """
    protocol = _loco_protocol()
    for key, value in kw.get("fall", {}).items():
        protocol["metrics"]["fall"][key] = value
    derived = loco_judge.derived_thresholds(protocol, stand_height_m=kw["stand_height_m"],
                                           step_dt=kw["step_dt"])
    return protocol, {"judge_id": loco_judge.JUDGE_ID,
                      "tilt_cos_min": round(derived["tilt_cos_min"], 9),
                      "clearance_min": round(derived["clearance_min"], 9),
                      "sustain_steps": derived["sustain_steps"]}


def _fixture_loco_fall(kw):
    """The geometric fall predicate around the dwell, and the clearance branch beside it."""
    steps, sustain = kw["window_steps"], kw["sustain_steps"]
    tilt = torch.ones(steps, 1)
    tilt[kw["bad_start"]:kw["bad_start"] + kw["bad_len"]] = 0.5  # below cos(40 deg) = 0.766
    clearance = torch.full((steps, 1), kw["clearance"]) if "clearance" in kw else None
    valid = torch.arange(steps).unsqueeze(1) <= kw["first_done"]
    flag = metrics.fall_flags(tilt, clearance, 0.766044443118978, kw.get("clearance_min"),
                              sustain, valid)
    return _loco_protocol(), {"judge_id": loco_judge.JUDGE_ID, "fall": bool(flag[0])}


def _fixture_loco_success(kw):
    """Command success at the declared thresholds, which are strict on both axes."""
    ok = metrics.success_mask(torch.tensor([[kw["lin_err"]]]), torch.tensor([[kw["ang_err"]]]), 0.5, 0.4)
    return _loco_protocol(), {"judge_id": loco_judge.JUDGE_ID, "success": bool(ok[0, 0])}


def _fixture_loco_energy(kw):
    """Joint power from the implicit-PD reconstruction, against a hand-computed value.

    The expectation is a hand calculation, so every input here is exact in binary: a case landing on
    a rounding error would test the float rather than the formula (including the damping sign).
    """
    power = metrics.step_energy(
        torch.tensor([[10.0, 20.0]]), torch.tensor([[1.0, 2.0]]),
        torch.tensor([[0.5, -0.5]]), torch.tensor([[0.25, -0.25]]), torch.tensor([[1.0, -3.0]]),
    )
    return _loco_protocol(), {"judge_id": loco_judge.JUDGE_ID, "power_w": float(power[0])}


def _fixture_loco_completion(kw):
    """Completion over a 1 s window whose steps are exact in binary: the turn rate must not enter."""
    steps, dt = 16, 0.0625
    cmd = torch.tensor([[[kw["vx"], 0.0, kw["wz"]]]]).expand(steps, 1, 3).contiguous()
    ratio = metrics.completion_ratio(torch.zeros(1, 3), torch.tensor([[kw["travelled"], 0.0, 0.0]]),
                                     cmd, torch.ones(steps, 1, dtype=torch.bool), dt)
    return _loco_protocol(), {"judge_id": loco_judge.JUDGE_ID, "completion": float(ratio[0])}


_FIXTURES = {
    "plain": _fixture_plain,
    "tilt_hold": _fixture_tilt_hold,
    "contact": _fixture_contact,
    "tracking_at_threshold": _fixture_tracking_at_threshold,
    "carrier_hold": _fixture_carrier_hold,
    "carrier_alternating": _fixture_carrier_alternating,
    "mesh_at_threshold": _fixture_mesh_at_threshold,
    "loco_derivation": _fixture_loco_derivation,
    "loco_fall": _fixture_loco_fall,
    "loco_success": _fixture_loco_success,
    "loco_energy": _fixture_loco_energy,
    "loco_completion": _fixture_loco_completion,
}


def _fixture_banded(kw):
    """A commanded sweep over the declared bands, with the velocity, position and gait it produces.

    One fixture for the four banded criteria, because they read one window. ``segments`` is the
    command schedule (``[[speed, frames], ...]``); ``spoil`` cuts the velocity inside one band while
    the command keeps asking for it; ``creep`` moves the robot while the command is zero;
    ``stop_after`` stops the robot while the command keeps being issued; ``load_fraction`` /
    ``load_frames`` put that fraction of body weight on both non-foot bodies; ``swing_feet`` /
    ``air_frames`` give that many feet a swing of that length; ``zero_env`` holds one env at a zero
    command for the whole window; ``meta_plain`` hands the episode's initial state in as plain
    numbers instead of tensors; ``settled`` reads the window under ``lizard2_flat_v2.json`` (the
    settled banded kinds) instead of v1, with ``settle_s`` overriding its declared 0.5 s; ``coast`` is
    ``(speed, frames)`` -- the robot keeps that speed for that many frames after the command drops to
    zero from a nonzero one, which is what a command step costs in reality; ``protocol_patch`` edits a
    parameter of a copy of the protocol.
    """
    protocol = json.loads(json.dumps(LIZARD2_SETTLED_PROTOCOL if kw.get("settled")
                                     else LIZARD2_PROTOCOL))
    if kw.get("settled") and "settle_s" in kw:
        for gate in ("tracking", "displacement"):
            protocol["criteria"][gate]["params"]["settle_s"] = kw["settle_s"]
    for gate, params in (kw.get("protocol_patch") or {}).items():
        protocol["criteria"][gate]["params"].update(params)
    steps, num_envs = 200, 2
    dt = protocol["episode_length_s"] / steps
    speeds = [speed for speed, frames in kw["segments"] for _ in range(frames)]
    speeds += [0.0] * max(0, steps - len(speeds))
    spoil, factor = kw.get("spoil"), kw.get("spoil_factor", 0.5)
    creep, stop_after = kw.get("creep", 0.0), kw.get("stop_after")
    zero_env, swing = kw.get("zero_env"), kw.get("swing_feet", 0)
    air = kw.get("air_frames", 8)
    load_fraction, load_frames = kw.get("load_fraction", 0.0), kw.get("load_frames", 0)
    coast = kw.get("coast")

    def commanded(env, step):
        return 0.0 if env == zero_env else speeds[step]

    def zero_run_start(env, step):
        """First frame of the zero-command run ``step`` is in, when that run follows a moving command."""
        if commanded(env, step) != 0.0:
            return None
        start = step
        while start > 0 and commanded(env, start - 1) == 0.0:
            start -= 1
        return start if start > 0 and commanded(env, start - 1) != 0.0 else None

    def velocity(env, step):
        speed = commanded(env, step)
        if spoil is not None and spoil[0] <= speed < spoil[1]:
            speed *= factor
        if speed == 0.0:
            if coast is not None:
                start = zero_run_start(env, step)
                if start is not None and step - start < coast[1]:
                    return coast[0]
            return creep
        return speed

    forward = [0.0] * num_envs
    positions = []
    for step in range(steps):
        for env in range(num_envs):
            if stop_after is None or step < stop_after:
                forward[env] += velocity(env, step) * dt
        positions.append(torch.tensor([[value, 0.0, 0.0] for value in forward], dtype=torch.float32))

    def swinging(step, foot):
        return swing > foot and step % (2 * air) < air

    def contact(step):
        return torch.tensor([[0.0 if swinging(step, foot) else 1.0 for foot in range(2)]
                             for _ in range(num_envs)], dtype=torch.float32)

    def fraction(step):
        planted = 0.25
        return torch.tensor([[0.0 if swinging(step, foot) else planted for foot in range(2)]
                             for _ in range(num_envs)], dtype=torch.float32)

    def non_foot(step):
        loaded = load_fraction if 10 <= step < 10 + load_frames else 0.0
        return torch.full((num_envs, 2), loaded)

    # ``meta_plain`` hands the initial state in as plain numbers. The collector passes meta through
    # unchanged, so on the live path these are the device tensors the episode started from while the
    # frames are CPU copies: a gate that assumes either device breaks on both, and only this one can
    # be reproduced without a second device in the test.
    meta = ({"start_pos": [[0.0, 0.0, 0.0]] * num_envs, "start_yaw": [0.0] * num_envs}
            if kw.get("meta_plain") else {})

    return protocol, build(protocol, steps, num_envs=num_envs, series={
        "command_world": lambda step: torch.tensor([[commanded(env, step), 0.0, 0.0]
                                                    for env in range(num_envs)]),
        "velocity_yaw": lambda step: torch.tensor([[velocity(env, step), 0.0, 0.0]
                                                   for env in range(num_envs)]),
        "pos": lambda step: positions[step],
        "foot_contact": contact,
        "foot_fraction": fraction,
        "non_foot_fraction": non_foot,
    }, **meta)


# Registered next to its definition rather than in the table above: the table is built at import
# time, before this function exists. One home per fixture still holds -- there is exactly one line
# that binds the name "banded" to a fixture.
_FIXTURES["banded"] = _fixture_banded


def test_banded_tracking_judges_each_band_and_the_zero_band_in_absolute_units():
    """A range command is judged band by band: the spoilt band fails while the others stay clean."""
    sweep = {"segments": [[0.0, 50], [0.5, 50], [1.5, 50], [2.5, 50]]}
    clean = baseline_metrics.judge(_fixture_banded(sweep)[1])
    assert clean["judge"]["id"] == baseline_metrics.BANDED_JUDGE_ID, clean["judge"]
    assert clean["gates"]["tracking"] and clean["gates"]["displacement"], clean["gates"]
    assert clean["metrics"]["tracking_band_frames"] == {"0-0.1mps": 100, "0.1-1mps": 100,
                                                       "1-2mps": 100, "2-3mps": 100}, \
        clean["metrics"]["tracking_band_frames"]

    spoiled = baseline_metrics.judge(_fixture_banded({**sweep, "spoil": (1.0, 2.0)})[1])
    assert not spoiled["gates"]["tracking"], spoiled["metrics"]["tracking_band_reasons"]
    assert spoiled["metrics"]["tracking_band_error"]["1-2mps"] == 0.5, spoiled["metrics"]
    assert spoiled["metrics"]["tracking_band_error"]["0.1-1mps"] == 0.0, "another band moved too"

    creeping = baseline_metrics.judge(_fixture_banded({**sweep, "creep": 0.4})[1])
    assert not creeping["gates"]["tracking"], creeping["metrics"]["tracking_band_reasons"]
    assert any("0-0.1mps" in reason for reason in creeping["metrics"]["tracking_band_reasons"]), \
        creeping["metrics"]["tracking_band_reasons"]


def test_banded_a_band_nothing_was_commanded_into_is_not_a_pass():
    """Two ways to measure nothing: a declared band with no frames, and frames in no band."""
    uncovered = baseline_metrics.judge(_fixture_banded({"segments": [[0.5, 100], [1.5, 100]]})[1])
    assert not uncovered["gates"]["tracking"], uncovered["gates"]
    assert uncovered["metrics"]["tracking_band_frames"]["2-3mps"] == 0
    assert any("measured nothing" in reason for reason in uncovered["metrics"]["tracking_band_reasons"])

    holed = baseline_metrics.judge(_fixture_banded({
        "segments": [[0.5, 100], [1.5, 100]],
        "protocol_patch": {"tracking": {"bands": [[0.0, 0.1], [0.1, 1.0]]}}})[1])
    assert holed["metrics"]["tracking_unclaimed_frames"] == 200, holed["metrics"]
    assert not holed["gates"]["tracking"], holed["gates"]


def test_banded_displacement_sums_over_the_band_before_dividing():
    """Stopping mid-window keeps the command in the denominator: the ratio falls, the window stays."""
    sweep = {"segments": [[0.0, 50], [0.5, 50], [1.5, 50], [2.5, 50]]}
    clean = baseline_metrics.judge(_fixture_banded(sweep)[1])
    assert abs(clean["metrics"]["displacement_band_ratio"]["1-2mps"] - 1.0) < 1e-6, clean["metrics"]
    stopped = baseline_metrics.judge(_fixture_banded({**sweep, "stop_after": 150})[1])
    assert not stopped["gates"]["displacement"], stopped["metrics"]["displacement_band_reasons"]
    assert abs(stopped["metrics"]["displacement_band_ratio"]["2-3mps"]) < 1e-6, stopped["metrics"]
    assert abs(stopped["metrics"]["displacement_band_ratio"]["0.1-1mps"] - 1.0) < 1e-6, \
        "a band the robot did walk must not be charged for a later one"


def test_banded_displacement_reads_an_initial_state_that_is_not_already_a_tensor():
    """The initial state travels beside the frames, so the gate must not assume a device for it.

    The live path hands meta through as the tensors the episode started from -- device tensors, while
    the frames are CPU copies -- and the first real run of this gate died on exactly that ("Expected
    all tensors to be on the same device, but found at least two devices, cuda:0 and cpu"). A second
    device is not available to a fixture, so this one hands the same state in as plain numbers: the
    same assumption, broken the same way, raising the same way before the conversion.
    """
    sweep = {"segments": [[0.0, 50], [0.5, 50], [1.5, 50], [2.5, 50]], "swing_feet": 2,
             "meta_plain": True}
    plain = baseline_metrics.judge(_fixture_banded(sweep)[1])
    assert plain["gates"]["displacement"], plain["metrics"]["displacement_band_reasons"]
    assert abs(plain["metrics"]["displacement_band_ratio"]["1-2mps"] - 1.0) < 1e-6, plain["metrics"]


def test_settled_banded_criteria_forgive_the_command_step_and_nothing_more():
    """A band boundary is a step: the frames before the command has been in force are not evidence.

    Same window several ways, on the schedule that walks last and then stops, which is where a real
    resample lands (the line's own zero band began at frame 499, the 10 s boundary). ``coast`` is the
    braking the step costs: inside the declared 1.5 s it must not be held against the policy, beyond it
    it must be, and a robot that keeps creeping through the band is a failure either way. The same
    braking run under the un-settled reader fails, which is what the settle window changed, and the
    zero band's displacement reading is metres per env rather than a sum over the band's envs.
    """
    walk_then_stop = {"segments": [[0.5, 50], [1.5, 50], [2.5, 50], [0.0, 50]], "swing_feet": 2}
    # The fixture's step is 0.1 s, so the declared 1.5 s of settling is 15 frames.
    inside = baseline_metrics.judge(_fixture_banded(
        {**walk_then_stop, "settled": True, "coast": (2.6, 10)})[1])
    assert inside["gates"]["tracking"], inside["metrics"]["tracking_band_reasons"]
    assert inside["gates"]["displacement"], inside["metrics"]["displacement_band_reasons"]
    assert abs(inside["metrics"]["tracking_band_unsettled_max"]["0-0.1mps"] - 2.6) < 1e-6, \
        "the report must carry what the trim removed, not only what it left"

    unread = baseline_metrics.judge(_fixture_banded({**walk_then_stop, "coast": (2.6, 10)})[1])
    assert not unread["gates"]["tracking"], \
        "the published reader has no settle window, so it reads the step: that is the defect"

    beyond = baseline_metrics.judge(_fixture_banded(
        {**walk_then_stop, "settled": True, "coast": (2.6, 25)})[1])
    assert not beyond["gates"]["tracking"], beyond["metrics"]["tracking_band_error"]
    assert not beyond["gates"]["displacement"], beyond["metrics"]["displacement_band_ratio"]

    creeping = baseline_metrics.judge(_fixture_banded(
        {**walk_then_stop, "settled": True, "creep": 0.4})[1])
    assert not creeping["gates"]["tracking"], creeping["metrics"]["tracking_band_error"]

    # Five settled frames of a 1.0 m/s crawl is 0.5 m in *each* env: metres, not the 1.0 m two envs
    # add up to. A criterion whose number scales with the batch size is not a criterion.
    per_env = baseline_metrics.judge(_fixture_banded(
        {**walk_then_stop, "settled": True, "coast": (1.0, 20)})[1])
    assert not per_env["gates"]["displacement"], per_env["metrics"]["displacement_band_ratio"]
    assert abs(per_env["metrics"]["displacement_band_ratio"]["0-0.1mps"] - 0.5) < 1e-6, \
        per_env["metrics"]["displacement_band_ratio"]


def test_non_foot_load_sum_catches_two_bodies_under_the_single_body_fraction():
    """Two bodies at 4% carry 8% between them: the single-body criterion sees neither, the sum does."""
    loaded = {"segments": [[0.5, 200]], "load_fraction": 0.04, "load_frames": 6}
    result = baseline_metrics.judge(_fixture_banded(loaded)[1])
    assert result["gates"]["no_non_foot_carrier"], "the fraction is 0.05 and no body reached it"
    assert not result["gates"]["no_non_foot_load_sum"], result["metrics"]
    assert abs(result["metrics"]["non_foot_load_sum_max"] - 0.08) < 1e-6, result["metrics"]

    lighter = baseline_metrics.judge(_fixture_banded({**loaded, "load_fraction": 0.03})[1])
    assert lighter["gates"]["no_non_foot_load_sum"], lighter["metrics"]
    briefer = baseline_metrics.judge(_fixture_banded({**loaded, "load_frames": 4})[1])
    assert briefer["gates"]["no_non_foot_load_sum"], f"0.4 s is under the 0.5 s dwell: {briefer['metrics']}"


def test_gait_needs_the_declared_feet_a_long_enough_swing_and_a_landing():
    """A gait is a sequence: two feet swinging 0.8 s and loading on landing pass, one foot does not."""
    sweep = {"segments": [[0.0, 50], [0.5, 50], [1.5, 50], [2.5, 50]], "swing_feet": 2, "air_frames": 8}
    two = baseline_metrics.judge(_fixture_banded(sweep)[1])
    assert two["gates"]["gait"], two["metrics"]
    assert two["metrics"]["gait_swing_feet_least"] == 2, two["metrics"]

    one = baseline_metrics.judge(_fixture_banded({**sweep, "swing_feet": 1})[1])
    assert not one["gates"]["gait"], one["metrics"]

    brief = baseline_metrics.judge(_fixture_banded({
        **sweep, "air_frames": 1, "protocol_patch": {"gait": {"min_air_time_s": 0.2}}})[1])
    assert not brief["gates"]["gait"], f"a 0.1 s swing is not a 0.2 s step: {brief['metrics']}"

    standing = baseline_metrics.judge(_fixture_banded({**sweep, "zero_env": 1})[1])
    assert standing["gates"]["gait"], "an env commanded to stand is not asked for a gait"


def frozen_digests(spec: dict) -> dict:
    """The digests that pin each id: its case block, and the semantics surface it can reach."""
    out = {}
    for judge_id, block in spec["ids"].items():
        surface = importlib.import_module(block["module"]).semantics_surface()
        pinned = {name: surface[name] for name in block["kinds"]}
        block_without_digest = {key: value for key, value in block.items() if key != "frozen_sha256"}
        out[judge_id] = {"kinds_sha256": record.digest(pinned),
                         "frozen_sha256": record.digest(block_without_digest)}
    return out


def _matches(observed: dict, expected: dict, where: str = "") -> str | None:
    """The first place an observation fails a (possibly nested) expectation, or ``None``."""
    for key, want in expected.items():
        got = observed.get(key)
        spot = f"{where}{key}"
        if isinstance(want, dict):
            if not isinstance(got, dict):
                return f"{spot}: expected a block, got {got!r}"
            problem = _matches(got, want, where=f"{spot}.")
            if problem is not None:
                return problem
        elif got != want:
            return f"{spot}: {got!r}, not {want!r}"
    return None


def _drive_baseline(subject) -> dict:
    """A baseline case's subject is a frames artifact; its observation is the verdict it earns."""
    result = baseline_metrics.judge(subject)
    return {"judge_id": result["judge"]["id"], "verdict": result["verdict"], "gates": result["gates"],
            "invalid_reasons": result["invalid_reasons"]}


def _drive_loco(subject) -> dict:
    """A locomotion case builds its own observation: its kernels have no single verdict object."""
    return subject


_DRIVERS = {"baseline": _drive_baseline, "loco": _drive_loco}


def test_judge_semantics_are_frozen_and_hold():
    """Every id's cases, run against the id they are pinned to, must produce the frozen outcome."""
    spec = json.loads(_SEMANTICS_PATH.read_text(encoding="utf-8"))
    digests = frozen_digests(spec)
    assert spec["ids"], "an empty table pins nothing"
    for judge_id, block in spec["ids"].items():
        module = importlib.import_module(block["module"])
        assert getattr(module, block["constant"]) == judge_id, \
            f"{judge_id}: {block['module']}.{block['constant']} says {getattr(module, block['constant'])!r}"
        assert digests[judge_id]["kinds_sha256"] == block["kinds_sha256"], (
            f"{judge_id}: the kind table it can reach changed. A published id keeps its kinds: a new "
            "or reshaped criterion needs a new id, not a re-pin (spell the old kind out in the new one)")
        assert digests[judge_id]["frozen_sha256"] == block["frozen_sha256"], (
            f"{judge_id}: its case block changed in place. Publish a new id instead; the records that "
            "already name this one point at the semantics it had")
        protocol_name = _load_protocol_name(block["protocol_file"])
        driver = _DRIVERS[block["driver"]]
        for case_name, case in block["cases"].items():
            protocol, subject = _FIXTURES[case["fixture"]](case["kw"])
            assert protocol["name"] == protocol_name, \
                f"{judge_id}/{case_name}: {protocol['name']} is not {protocol_name}"
            observed = driver(subject)
            assert observed["judge_id"] == judge_id, \
                f"{case_name}: judged by {observed['judge_id']}, not {judge_id}"
            problem = _matches(observed, case["expect"])
            assert problem is None, f"{judge_id}/{case_name}: {problem} (observed {observed})"


def _load_protocol_dict(file_name: str) -> dict:
    """A protocol by file name; the two families spell theirs in JSON and YAML respectively."""
    text = (_REPO / "ablation_harness" / "protocols" / file_name).read_text(encoding="utf-8")
    return yaml.safe_load(text) if file_name.endswith((".yaml", ".yml")) else json.loads(text)


def _load_protocol_name(file_name: str) -> str:
    return _load_protocol_dict(file_name)["name"]


def test_carrier_aggregation_merges_bodies_before_time():
    """The declared order is "any body over the fraction, then the dwell", so taking turns counts.

    Body by body the longest loaded run here is a single frame; merged across bodies it is the whole
    span. A reader who wanted "one body held it alone" reads the same record to the opposite
    verdict, which is why the order lives in the kind rather than in a protocol's spelling.
    """
    protocol, artifact = _fixture_carrier_alternating({"span_s": 0.5})
    loaded = artifact["frames"]["non_foot_fraction"] >= protocol["gates"]["non_foot_load_fraction_lt"]
    dwell = protocol["gates"]["non_foot_load_sustain_s"]
    assert loaded.shape[-1] == 2 and bool(loaded.any()), loaded.shape
    for body in range(loaded.shape[-1]):
        alone = baseline_metrics._run_lengths(loaded[:, :, body]).max().item() * _STEP_DT
        assert alone < dwell, f"body {body} alone holds it for {alone}s, at or above the {dwell}s dwell"
    merged = baseline_metrics._run_lengths(loaded.any(dim=-1)).max().item() * _STEP_DT
    assert merged >= dwell, merged
    assert not baseline_metrics.judge(artifact)["gates"]["no_non_foot_carrier"]


def test_v4_reproduces_v3_on_one_record():
    """The migration proof: v4 renames the criteria and changes no number."""
    artifact = build(V3_PROTOCOL, 1000, num_envs=2)
    under_v3 = baseline_metrics.judge(artifact)
    under_v4 = baseline_metrics.judge({**artifact, "protocol": V4_PROTOCOL})
    assert under_v3["verdict"] == "pass", under_v3["gates"]
    assert under_v4["verdict"] == under_v3["verdict"], (under_v4["invalid_reasons"], under_v3["invalid_reasons"])
    assert under_v4["gates"] == under_v3["gates"], (under_v4["gates"], under_v3["gates"])
    assert under_v4["metrics"] == under_v3["metrics"], "a rename must not move a measured number"


def test_judge_identity_travels_with_the_verdict():
    """A verdict names the reader that produced it, and legacy is a specific reader, not a shrug."""
    assert baseline_metrics.judge(build(V4_PROTOCOL, 1000))["judge"] == {
        "id": baseline_metrics.JUDGE_ID, "origin": "declared",
        "protocol_name": "Baseline-Flat-v4", "protocol_version": 4}
    for protocol in (PROTOCOL, V2_PROTOCOL, V3_PROTOCOL):
        identity = baseline_metrics.judge(build(protocol, 1000))["judge"]
        assert identity["id"] == baseline_metrics.LEGACY_JUDGE_ID, identity
        assert identity["origin"] == "legacy" and identity["protocol_name"] == protocol["name"], identity


def test_a_protocol_that_declares_nothing_readable_is_refused_not_defaulted():
    """An unreadable criterion is invalid, never a silent fallback to older semantics."""
    artifact = build(V4_PROTOCOL, 1000)

    def judged(criteria):
        protocol = json.loads(json.dumps(V4_PROTOCOL))
        protocol["criteria"] = criteria
        return baseline_metrics.judge({**artifact, "protocol": protocol})

    base = V4_PROTOCOL["criteria"]
    cases = {        "does not implement": {"tracking": {"kind": "tracking_v9", "params": {"threshold": 0.2, "normalized": True}}},
        "does not accept": {"attitude": {"kind": "sustained_tilt_v1",
                                        "params": {"threshold_cos": 0.766, "sustain_s": 0.5, "op": "lt"}}},
        "is missing": {"attitude": {"kind": "sustained_tilt_v1", "params": {"threshold_cos": 0.766}}},
        "not a known gate": {"no_such_axis": {"kind": "survival_v1", "params": {"threshold": 0.9}}},
        "unset": {"attitude": {"kind": "sustained_tilt_v1",
                              "params": {"threshold_cos": 0.766, "sustain_s": None}}},
        "declares no gate": {},
    }
    for expected_reason, override in cases.items():
        result = judged(override)
        assert result["verdict"] == "invalid", (expected_reason, result["gates"])
        assert any(expected_reason in reason for reason in result["invalid_reasons"]), \
            (expected_reason, result["invalid_reasons"])
    # The unmodified block still judges: the refusals above are about the block, not the record.
    assert baseline_metrics.judge({**artifact, "protocol": V4_PROTOCOL})["verdict"] == "pass"
    assert base["tracking"]["kind"] == "tracking_v1", "the base block is the one being perturbed above"


def test_a_strays_protocol_without_criteria_is_refused_but_a_known_one_judges():
    """The legacy reader is a whitelist by declared identity, not a fallback for anything old-looking."""
    artifact = build(PROTOCOL, 1000)
    stranger = {**artifact["protocol"], "name": "Baseline-Flat-v9", "version": 9}
    result = baseline_metrics.judge({**artifact, "protocol": stranger})
    assert result["verdict"] == "invalid", result["gates"]
    assert any("declares no criteria" in reason for reason in result["invalid_reasons"]), result["invalid_reasons"]
    assert result["judge"]["id"] == "unresolved", result["judge"]
    assert baseline_metrics.judge(artifact)["verdict"] == "pass", "the known v1 protocol still judges"


def test_the_legacy_reader_refuses_thresholds_it_cannot_read():
    """An unknown key is not a gate: it is a protocol this reader cannot decide."""
    unknown = json.loads(json.dumps(V2_PROTOCOL))
    unknown["gates"]["some_new_axis_gt"] = 1.0
    result = baseline_metrics.judge({**build(V2_PROTOCOL, 1000), "protocol": unknown})
    assert result["verdict"] == "invalid" and any("no criterion for" in r for r in result["invalid_reasons"])

    both = json.loads(json.dumps(V2_PROTOCOL))
    both["gates"]["forward_mae_norm_lt"] = 0.2  # now it names an absolute and a normalized tracking error
    result = baseline_metrics.judge({**build(V2_PROTOCOL, 1000), "protocol": both})
    assert result["verdict"] == "invalid" and any("only one of them" in r for r in result["invalid_reasons"])

    gap = json.loads(json.dumps(V2_PROTOCOL))
    del gap["gates"]["tilt_sustain_s"]
    result = baseline_metrics.judge({**build(V2_PROTOCOL, 1000), "protocol": gap})
    assert result["verdict"] == "invalid" and any("names no tilt_sustain_s" in r for r in result["invalid_reasons"]), \
        result["invalid_reasons"]


def main():
    if "--print-frozen" in sys.argv:
        print(json.dumps(frozen_digests(json.loads(_SEMANTICS_PATH.read_text(encoding="utf-8"))), indent=2))
        return
    if "--print-frames-frozen" in sys.argv:
        print(json.dumps(frame_frozen_digests(
            json.loads(_FRAMES_SEMANTICS_PATH.read_text(encoding="utf-8"))), indent=2))
        return
    # Import isolation has its own fresh-process suite entry.
    from rl_exp.tools.verify import test_baseline_mdp

    test_baseline_mdp.main()
    for name, test in sorted(globals().copy().items()):
        if name.startswith("test_"):
            test()
    print("BASELINE_CONTRACT_OK")
    from rl_exp.tools.verify import test_acceptance_metrics

    test_acceptance_metrics._main()


if __name__ == "__main__":
    main()
