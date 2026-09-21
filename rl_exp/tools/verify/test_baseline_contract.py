# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline regressions for baseline fixed-window collection, judgement, and startup checks."""

import ast
import json
import math
import pathlib
import re
import sys
from types import SimpleNamespace as NS

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
import torch
from ablation_harness import baseline_frames, baseline_metrics
from rl_exp.tools.diagnose.diag_metrics import mesh_min_z, pad_point_clouds
from rl_exp.tools.verify.baseline_runtime import joint_reset_errors, material_errors, termination_errors

PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/baseline_flat_v1.json").read_text())
V2_PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/baseline_flat_v2.json").read_text())
V3_PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/baseline_flat_v3.json").read_text())
BODY_WEIGHT_N = 706.32  # 72 kg x 9.81, the figure every baseline report carries

# The axis labels a test record carries: a per-body reading has to name its bodies.
AXES = {
    "non_foot_fraction": ["chest_pitch", "neck_pitch"],
    "mesh_min_z": ["chest_pitch", "neck_pitch"],
    "foot_contact": ["rr_foot", "rl_foot"],
    "foot_fraction": ["rr_foot", "rl_foot"],
}


def expect(exception, fn, *args, **kwargs):
    """Call ``fn`` and return the exception it must raise."""
    try:
        fn(*args, **kwargs)
    except exception as err:
        return err
    raise AssertionError(f"{getattr(fn, '__name__', fn)} must raise {exception.__name__}")


def default_frame(num_envs: int) -> dict:
    """One all-zero frame, shaped as the contract prescribes."""
    frame = {}
    for name, (kind, _, _) in baseline_frames.COLUMNS.items():
        width = len(AXES[name]) if name in AXES else (3 if kind == "vec3" else 0)
        frame[name] = torch.zeros(num_envs, width) if width else torch.zeros(num_envs)
    return frame


def build(protocol: dict, steps: int, *, num_envs: int = 1, series: dict | None = None,
          start_pos: torch.Tensor | None = None, start_yaw: torch.Tensor | None = None) -> dict:
    """Collect a synthetic window through the real contract.

    ``series`` overrides a column per frame (``f(step) -> tensor``). The defaults are a clean run:
    walking exactly on the command the protocol declares (the middle of its box, so a fixed and a
    ranged protocol both get a run that is on command), feet down, nothing loaded that should not
    be, a timeout on the last frame. ``start_pos``/``start_yaw`` are the episode's initial state.
    """
    box = baseline_metrics.command_box(protocol)
    forward = (box[0][0] + box[0][1]) / 2.0
    step_dt = protocol["episode_length_s"] / steps
    recorder = baseline_frames.BaselineFrames(num_envs=num_envs, step_dt=step_dt, axes=AXES)
    for step in range(steps):
        frame = default_frame(num_envs)
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
        for name, override in (series or {}).items():
            frame[name] = override(step)
        recorder.add(**frame)
    return recorder.artifact(
        protocol=protocol, body_weight_n=BODY_WEIGHT_N,
        start_pos=torch.zeros(num_envs, 3) if start_pos is None else start_pos,
        start_yaw=torch.zeros(num_envs) if start_yaw is None else start_yaw)


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
    namespace = {
        "args_cli": NS(task="requested-play-task", num_envs=3),
        "resolve_task_cfg": lambda task: selected if task == "requested-play-task" else None,
        "BaselineFlatEnvCfg": lambda: wrong,
        "gym": NS(make=lambda task, cfg: NS()),
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
    # known bad, another line, needs its own decision: its docstring claims (x, y, z, w) while its
    # math is the (w, x, y, z) branch. Recorded here so the debt stays visible instead of silent.
    "rl_exp/tasks/parkour_mdp.py": "parkour line's _yaw_from_quat: same bug class, pending decision",
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


def main():
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
