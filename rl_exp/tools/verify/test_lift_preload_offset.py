# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Focused checks for the preload offset iteration used by the guided lift trial."""

import unittest

from rl_exp.tools.diagnose.lift_preload_offset import next_offset


def _case(q_a, q_b, offset=None):
    ik = {"samples": [{"q_rad": {"lf_elbow_joint": 0.2, "rf_elbow_joint": 0.3}}]}
    meta = {"joints": ["lf_elbow_joint", "rf_elbow_joint"], "offset": offset}
    return {"metadata": meta, "samples": [{"q": q_a}, {"q": q_b}]}, ik


class PreloadOffsetTest(unittest.TestCase):
    def test_offset_cancels_mean_deviation_for_selected_prefix_only(self):
        report, ik = _case([0.3, 0.9], [0.5, 0.9])
        out = next_offset(report, ik, 0, 2, ["lf_"])
        self.assertEqual(list(out), ["lf_elbow_joint"])
        self.assertAlmostEqual(out["lf_elbow_joint"], 0.2 - 0.4)

    def test_previous_offset_accumulates(self):
        report, ik = _case([0.3, 0.9], [0.3, 0.9], offset={"lf_elbow_joint": -0.1})
        self.assertAlmostEqual(next_offset(report, ik, 0, 2, ["lf_"])["lf_elbow_joint"], -0.1 + 0.2 - 0.3)

    def test_bad_inputs_are_rejected(self):
        report, ik = _case([0.3, 0.9], [0.3, 0.9])
        with self.assertRaises(ValueError):
            next_offset(report, ik, 2, 2, ["lf_"])
        report["metadata"]["offset"] = {"tail1_yaw_joint": 0.1}
        with self.assertRaises(ValueError):
            next_offset(report, ik, 0, 2, ["lf_"])


if __name__ == "__main__":
    unittest.main()
