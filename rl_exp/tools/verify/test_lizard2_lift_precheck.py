# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Check that lift geometry precheck detects actual tail-ground penetration."""

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "rl_exp/tools/diagnose"))
import body_precheck  # noqa: E402
import lizard2_lift_geometry as lift  # noqa: E402
import lizard2_lift_precheck as precheck  # noqa: E402


class LiftPrecheckTest(unittest.TestCase):
    def test_tail_penetration_is_not_treated_as_two_foot_clearance(self):
        urdf = ROOT / "rl_exp/lizard2_palm_spatial/lizard2_palm_spatial.urdf"
        ik = lift.run(urdf, [0.], support=["lf_wrist", "rr_ankle"], tail_pitch=0.1)
        self.assertTrue(ik["samples"][0]["passed"])
        manifest = {"connection_filter": {"pairs": [["base_link", "rl_hip_twist"],
            ["base_link", "rr_hip_twist"], ["base_link", "tail1_pitch"],
            ["chest_pitch", "lf_shoulder_twist"], ["chest_pitch", "rf_shoulder_twist"],
            ["tail1_pitch", "tail2_pitch"]]}}
        good = precheck.prepare(ik, manifest)
        report = body_precheck.run(good, ROOT)
        self.assertEqual(report["status"], "pass")
        bad = copy.deepcopy(good)
        bad["tasks"]["cases"][0]["q_rad"]["tail1_pitch_joint"] = -0.1
        report = body_precheck.run(bad, ROOT)
        self.assertEqual(report["status"], "fail")
        ground = next(r for r in report["results"] if r["check"] == "ground")
        self.assertEqual(ground["detail"]["links"]["tail2_pitch"]["state"], "fail")


if __name__ == "__main__":
    unittest.main()
