# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline regressions for baseline fixed-window scoring and startup checks."""

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
from ablation_harness.baseline_metrics import BaselineWindow
from rl_exp.tools.verify.baseline_runtime import joint_reset_errors, material_errors, termination_errors

PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/baseline_flat_v1.json").read_text())


def score(fail_at=None, *, simultaneous=False, yaw=0.0):
    window = BaselineWindow(torch.zeros(1, 3), torch.tensor([yaw]), steps=20, protocol=PROTOCOL)
    for step in range(20):
        # After failure deliberately supply huge respawn displacements: none may count.
        distance = (step + 1) * 0.5 if fail_at is None or step <= fail_at else 1000.0
        y = torch.tensor([yaw])
        pos = torch.stack((distance * y.cos(), distance * y.sin(), torch.zeros(1)), dim=-1)
        window.add(pos=pos, yaw=y, velocity_yaw=torch.tensor([[0.5, 0.0, 0.0]]),
                   head_tail_force=torch.zeros(1), terminated=torch.tensor([step == fail_at]),
                   timeout=torch.tensor([step == 19 or (simultaneous and step == fail_at)]))
    return window.result()


def test_fixed_window():
    assert score()["verdict"] == "pass"
    assert abs(score(yaw=1.57079632679)["metrics"]["forward_displacement_m"] - 10) < 1e-5
    failed = score(3)
    assert failed["metrics"]["forward_displacement_m"] == 2
    assert abs(failed["metrics"]["forward_mae_mps"] - 0.4) < 1e-6
    assert failed["metrics"]["first_episode_timeout_fraction"] == 0
    assert score(19, simultaneous=True)["metrics"]["first_episode_timeout_fraction"] == 0
    window = BaselineWindow(torch.zeros(1, 3), torch.zeros(1), steps=20, protocol=PROTOCOL)
    try:
        window.result()
    except ValueError:
        pass
    else:
        raise AssertionError("partial windows must not pass")


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
    window = BaselineWindow(torch.zeros(1, 3), start_yaw, steps=steps, protocol=PROTOCOL)
    for step in range(steps):
        travel = (step + 1) * speed
        pos = torch.tensor([[travel * math.cos(yaw), travel * math.sin(yaw), 0.0]])
        window.add(pos=pos, yaw=start_yaw, velocity_yaw=torch.tensor([[speed, 0.0, 0.0]]),
                   head_tail_force=torch.zeros(1), terminated=torch.tensor([False]),
                   timeout=torch.tensor([step == steps - 1]))
    return window.result()


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
    # known bad, another line, needs its own decision: its docstring claims (x, y, z, w) and its
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


V2_PROTOCOL = json.loads((_REPO / "ablation_harness/protocols/baseline_flat_v2.json").read_text())


def drag_window(protocol: dict, *, neck_fraction: float, mesh_z: float = -0.052, tilt_cos_value: float = 0.9,
                steps: int = 20, speed: float = 0.5) -> dict:
    """A rollout that tracks the command perfectly while the neck carries the robot.

    Everything the v1 gates look at is nominal: 0.5 m/s forward, 10 m of travel, no failure.
    The v2 gates read the rest -- non-foot carrier, tilt, collision mesh through the floor.
    """
    window = BaselineWindow(torch.zeros(1, 3), torch.zeros(1), steps=steps, protocol=protocol)
    feet = torch.tensor([[True, False, True, True]])
    for step in range(steps):
        travel = (step + 1) * speed
        window.add(pos=torch.tensor([[travel, 0.0, 0.0]]), yaw=torch.zeros(1),
                   velocity_yaw=torch.tensor([[speed, 0.0, 0.0]]), head_tail_force=torch.zeros(1),
                   terminated=torch.tensor([False]), timeout=torch.tensor([step == steps - 1]),
                   tilt_cos=torch.tensor([tilt_cos_value]),
                   non_foot_fraction=torch.tensor([[0.01, neck_fraction, 0.0]]),
                   mesh_min_z=torch.tensor([[0.5, mesh_z, 0.5]]), foot_contact=feet,
                   foot_fraction=torch.tensor([[0.3, 0.0, 0.3, 0.3]]))
    return window.result()


def test_v2_catches_what_v1_passed():
    """The neck-dragging rollout must fail v2 on the axes v1 never read, and pass nothing extra."""
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


def test_v2_sustain_filter_and_unmeasured_refusal():
    """A one-frame spike is contact noise; a gate with no measurement is refused, not passed."""
    window = BaselineWindow(torch.zeros(1, 3), torch.zeros(1), steps=1000, protocol=V2_PROTOCOL)
    for step in range(1000):
        window.add(pos=torch.tensor([[0.5 * (step + 1) * 0.02, 0.0, 0.0]]), yaw=torch.zeros(1),
                   velocity_yaw=torch.tensor([[0.5, 0.0, 0.0]]), head_tail_force=torch.zeros(1),
                   terminated=torch.tensor([False]), timeout=torch.tensor([step == 999]),
                   tilt_cos=torch.tensor([0.1 if step == 5 else 0.999]),
                   non_foot_fraction=torch.tensor([[0.9 if step == 5 else 0.01, 0.0, 0.0]]),
                   mesh_min_z=torch.tensor([[0.5, 0.5, 0.5]]),
                   foot_contact=torch.ones(1, 4, dtype=torch.bool),
                   foot_fraction=torch.full((1, 4), 0.25))
    assert window.result()["gates"]["attitude"], "one tilted frame is a bump, not a fall"
    assert window.result()["gates"]["no_non_foot_carrier"], "one loaded frame is a bump, not a carrier"
    silent = BaselineWindow(torch.zeros(1, 3), torch.zeros(1), steps=20, protocol=V2_PROTOCOL)
    try:
        silent.result()
    except ValueError:
        pass
    else:
        raise AssertionError("a partial window must not score")


def test_v2_refuses_a_gate_it_could_not_measure():
    """Unmeasured is unknown, and unknown is not a pass."""
    window = BaselineWindow(torch.zeros(1, 3), torch.zeros(1), steps=2, protocol=V2_PROTOCOL)
    for step in range(2):
        window.add(pos=torch.tensor([[0.5 * (step + 1), 0.0, 0.0]]), yaw=torch.zeros(1),
                   velocity_yaw=torch.tensor([[0.5, 0.0, 0.0]]), head_tail_force=torch.zeros(1),
                   terminated=torch.tensor([False]), timeout=torch.tensor([step == 1]))
    try:
        window.result()
    except ValueError as err:
        assert "never measured" in str(err), err
    else:
        raise AssertionError("scoring a v2 window with no tilt/carrier/mesh readings must be refused")


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
