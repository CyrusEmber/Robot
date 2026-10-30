# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Focused checks for bounded link-target IK on the actual lizard2 URDF."""

import unittest
from pathlib import Path

import numpy as np

from rl_exp.tools.diagnose import pose_target_solver as ik


class PoseTargetSolverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = ik.load_model(Path(__file__).resolve().parents[2] / "lizard2_palm_spatial/lizard2_palm_spatial.urdf")
        cls.initial = {n: 0. for n, j in cls.model["joints"].items() if j["axis"] is not None}

    def test_real_joint_target_and_held_joints(self):
        joint = "lf_elbow_joint"
        link = "lf_wrist"
        sample = dict(self.initial, **{joint: 0.1})
        pose = ik.geometry.fk(self.model["joints"], link, sample)
        target = {"link": link, "point_local": [0., 0., 0.], "point_target": pose[:3, 3],
                  "normal_local": [0., 0., 1.], "normal_target": pose[:3, 2]}
        result = ik.solve(self.model, self.initial, [joint], [target], 1e-5, 1e-4)
        self.assertTrue(result["passed"])
        self.assertAlmostEqual(result["q_rad"][joint], 0.1, places=4)
        self.assertTrue(all(result["q_rad"][n] == 0. for n in self.initial if n != joint))

    def test_impossible_target_and_bad_normals_are_not_passes(self):
        target = {"link": "lf_wrist", "point_local": [0., 0., 0.], "point_target": [100., 0., 0.]}
        result = ik.solve(self.model, self.initial, ["lf_elbow_joint"], [target], 1e-5, 1e-4)
        self.assertFalse(result["passed"])
        self.assertGreater(result["targets"][0]["position_error_m"], 1.)
        target.update(normal_local=[0., 0., 2.], normal_target=[0., 0., 1.])
        with self.assertRaises(ValueError):
            ik.solve(self.model, self.initial, ["lf_elbow_joint"], [target], 1e-5, 1e-4)


if __name__ == "__main__":
    unittest.main()
