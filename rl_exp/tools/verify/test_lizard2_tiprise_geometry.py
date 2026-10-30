# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Focused offline front-edge selection and tiprise rejection checks."""

import unittest
from pathlib import Path

import numpy as np

from rl_exp.tools.diagnose.lizard2_tiprise_geometry import front_heel, run


class TipriseGeometryTest(unittest.TestCase):
    def test_root_forward_not_outward_and_deduplicate(self):
        # Long direction is y (outward), but root forward remains +x.
        points = np.array([[0., -2., 0.], [0., 2., 0.], [1., -2., 0.],
                           [1., 2., 0.], [1., 2., 0.], [2., 0., 0.2]])
        front, heel = front_heel(points)
        np.testing.assert_allclose(front.mean(axis=0), [1., 0., 0.])
        np.testing.assert_allclose(heel, [0., 0., 0.])
        self.assertEqual(len(front), 2)
        # Wrong-sign forward and whole-mesh extrema must not pass this check.
        self.assertFalse(np.allclose(front.mean(axis=0), heel))
        self.assertLess(front[:, 0].max(), points[:, 0].max())

    def test_actual_candidate_path_not_flat_lift(self):
        urdf = Path(__file__).resolve().parents[2] / 'out/lizard2_two_axis_20261029/candidate01/lizard2_two_axis.urdf'
        if not urdf.exists():
            self.skipTest('isolated candidate not installed')
        report = run(urdf)
        self.assertTrue(report['passed'])
        self.assertEqual(len(report['samples']), 11)
        keys = set(report['initial_q_rad'])
        for sample in report['samples']:
            self.assertEqual(set(sample['q_rad']), keys)
            self.assertGreaterEqual(sample['min_ground_gap_m'], -report['ground_tolerance_m'])
            for gap in sample['all_mesh_ground_gaps']:
                if gap['link'] not in report['axes']:
                    self.assertGreater(gap['min_ground_gap_m'], report['ground_tolerance_m'])
        for foot in report['samples'][-1]['feet'].values():
            self.assertAlmostEqual(foot['tilt_rad'], 0.15, places=4)
            self.assertGreater(foot['heel_world_m'][2] - foot['front_world_m'][2], 0.03)
            self.assertGreater(foot['foot_relative_shank_angle_rad'], 0.1)
            self.assertGreater(min(foot['foot_joint_margin_rad'].values()), 0.02)
        self.assertAlmostEqual(report['samples'][-1]['root_rise_m'], 0.02)

    def test_point_front_is_ambiguous(self):
        with self.assertRaisesRegex(ValueError, 'user geometry choice required'):
            front_heel(np.array([[0., -1., 0.], [0., 1., 0.], [1., 0., 0.]]))


if __name__ == '__main__':
    unittest.main()
