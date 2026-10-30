# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Focused checks for the foot-plate-only rise sweep on the actual lizard2 URDF."""

import unittest
from pathlib import Path

from rl_exp.tools.diagnose import lift_foot_plate_sweep as sweep
from rl_exp.tools.runrecord.binding import sha256_file

URDF = Path(__file__).resolve().parents[2] / "lizard2_palm_spatial/lizard2_palm_spatial.urdf"


def _ik(**over):
    joints = [f"{p}_{j}_joint" for p, j in (("lf", "wrist"), ("rr", "ankle"))]
    ik = {"urdf": str(URDF), "urdf_sha256": sha256_file(URDF),
          "support": ["lf_wrist", "rr_ankle"], "samples": [{"q_rad": {j: 0. for j in joints}}]}
    ik.update(over)
    return ik


class FootPlateSweepTest(unittest.TestCase):
    def test_held_angle_has_zero_rise_and_rise_is_nonnegative_at_flat_sole(self):
        for foot in sweep.run(_ik())["feet"].values():
            held = min(foot["rows"], key=lambda r: abs(r["angle_rad"]))
            self.assertAlmostEqual(held["rise_vs_held_m"], 0., places=9)
            self.assertGreaterEqual(foot["min_rise_m"], -1e-9)

    def test_mirrored_feet_reach_the_same_rise_at_opposite_limits(self):
        feet = sweep.run(_ik())["feet"]
        self.assertAlmostEqual(feet["lf_wrist"]["max_rise_m"], feet["rr_ankle"]["max_rise_m"], places=4)
        self.assertAlmostEqual(feet["lf_wrist"]["argmax_angle_rad"], -feet["rr_ankle"]["argmax_angle_rad"], places=4)

    def test_changed_urdf_identity_and_bad_steps_are_rejected(self):
        with self.assertRaises(ValueError):
            sweep.run(_ik(urdf_sha256="0" * 64))
        for steps in (2, 4):
            with self.assertRaises(ValueError):
                sweep.run(_ik(), steps=steps)


if __name__ == "__main__":
    unittest.main()
