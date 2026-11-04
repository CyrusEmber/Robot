# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline original-report replay and geometry mutation checks; no test framework."""

import argparse
import copy
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "diagnose"))
import lizard2_round_support_geometry as tool  # noqa: E402


def test_twist_zero():
    """Exercise actual solve and held-joint validation before report hash replay."""
    context = tool.prepare(tool.DEFAULT_URDF)
    twists = sorted(n for n in context["initial"] if n.endswith("_twist_joint"))
    assert len(twists) == 4
    errors = []
    if set(twists) & set(context["free"]):
        errors.append(f"twists remain free: {twists}")
    data = tool.run(tool.DEFAULT_URDF)
    for name, group in data["groups"].items():
        q = group["solver"]["q_rad"]
        if any(q[n] != 0. for n in twists):
            errors.append(f"{name}: nonzero twist { {n: q[n] for n in twists} }")
        for joint in twists:
            changed = dict(q)
            changed[joint] = 0.1
            verdict = tool.validate(context, changed, group["support"], data["clearance_m"])
            if f"held_joint:{joint}" not in verdict["failures"]:
                errors.append(f"{name}: mutation 0.1 rad not rejected as held_joint:{joint}")
    assert not errors, "\n".join(errors)
    assert len(context["free"]) == 12 and data["passed"]
    print("PASS: four twists held at exact zero; all eight 0.1 rad mutations rejected")


def main():
    test_twist_zero()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=tool.DEFAULT_OUT)
    args = parser.parse_args()
    data = json.loads(args.report.read_text(encoding="utf-8"))
    assert data["passed"] and set(data["groups"]) == set(tool.GROUPS)
    for path, digest in data["sha256"].items():
        assert tool.binding.sha256_file(Path(path)) == digest, path
    context = tool.prepare(Path(data["urdf"]))
    assert len(context["initial"]) == 26 and len(context["free"]) == 12
    assert data["root_quaternion_xyzw"] == [0., 0., 0., 1.]
    assert data["root_rise_m"] == 0
    assert abs(data["root_position_world_m"][2] - context["root_height_m"]) < 1e-12
    assert context["initial"]["tail1_pitch_joint"] == 0.3
    checks = []
    for name, group in data["groups"].items():
        q, support = group["solver"]["q_rad"], group["support"]
        validate = lambda c, values=q: tool.validate(c, values, support, data["clearance_m"])
        result = validate(context)
        assert group["passed"] and group["solver"]["passed"] and result["passed"], result["failures"]
        assert len(result["geometry"]) == len(context["items"])
        assert len([r for r in result["geometry"] if r["shape"] == "sphere"]) == 8
        assert all("normal_local" not in t and "normal_target" not in t for t in group["targets_root_m"])
        assert result == group["validation"]
        checks.append(f"{name}: original full FK/ground/limits/COM replay PASS")

        def rejected(changed, prefix, values=q):
            verdict = validate(changed, values)
            assert not verdict["passed"] and any(f.startswith(prefix) for f in verdict["failures"]), verdict

        # Change actual local geometry, not cached/report measurements. Check both channels.
        for kind in ("visual", "collision"):
            changed = copy.deepcopy(context)
            sphere = next(i for i in changed["items"] if i["link"] == support[0] and i["kind"] == kind)
            sphere["origin"][0, 3] += 0.01
            rejected(changed, "foot_xy:")
            changed = copy.deepcopy(context)
            sphere = next(i for i in changed["items"] if i["link"] == support[0] and i["kind"] == kind)
            sphere["origin"][2, 3] -= 0.01
            rejected(changed, "support_gap:")
            changed = copy.deepcopy(context)
            body = next(i for i in changed["items"] if i["link"] == "base_link" and i["kind"] == kind)
            body["vertices"][:, 2] -= 2.
            rejected(changed, "nonfoot_ground:")
        changed = copy.deepcopy(context)
        swing = next(i for i in changed["items"] if i["link"] not in support and i["link"] in tool.FEET)
        swing["radius_m"] += 0.02
        rejected(changed, "swing_clearance:")
        joint = context["free"][0]
        changed_q = dict(q)
        changed_q[joint] = context["model"]["joints"][joint]["limits"][1] - tool.MARGIN / 2
        rejected(context, "joint_margin:", changed_q)
        changed_q[joint] = context["model"]["joints"][joint]["limits"][1] + 0.01
        rejected(context, "joint_margin:", changed_q)
        checks.append(f"{name}: wrong XY/support height, visual+collision ground, swing clearance, margin/limit mutations REJECTED")
    # Known URDF RPY convention: roll then pitch then yaw; translation stays explicit.
    pose = tool.origin(ET.fromstring('<visual><origin xyz="1 2 3" rpy="0 0 1.5707963267948966"/></visual>'))
    assert np.allclose(pose @ [1., 0., 0., 1.], [1., 3., 3., 1.])
    # Force first solve failure; second group must still execute from its own q0.
    original_solve, calls = tool.solver.solve, []

    def first_fails(model, initial, free, targets, **kwargs):
        assert initial == context["initial"]
        calls.append(targets)
        if len(calls) == 1:
            raise RuntimeError("injected first-group failure")
        return original_solve(model, initial, free, targets, **kwargs)

    tool.solver.solve = first_fails
    try:
        failed = tool.run(Path(data["urdf"]), data["clearance_m"])
    finally:
        tool.solver.solve = original_solve
    assert len(calls) == 2
    assert not failed["passed"] and not failed["groups"]["lf+rr"]["passed"]
    assert len(failed["groups"]["lf+rr"]["solver"]["q_rad"]) == 26
    assert failed["groups"]["rf+rl"]["passed"]
    checks.append("first-group failure retained; second group independently PASS; origin transform PASS")
    print("\n".join(checks))
    print("PASS: offline geometry only; no internal self-collision, continuous path or physical approval")


if __name__ == "__main__":
    main()
