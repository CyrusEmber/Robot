# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline pre-reset standing safety regression; no AppLauncher or simulation."""
import ast
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.diagnose.lizard2_support_sweep_report import safety_failures, summarize_hold


class HoldSummaryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'hold.json'
        # One constant batched row template, repeated over an eight-second hold.
        row = dict(step=1, done=[False], root_position=[[0., 0., .6]],
                   gravity_b=[[0., 0., -1.]], joint_positions=[[.1] * 8],
                   joint_targets=[[.12] * 8], joint_velocities=[[0.] * 8])
        self.data = dict(trial_status='completed', safety_failures=[], duration_s=8., dt_s=.5,
                         joint_names=[f'foot_{i}' for i in range(8)],
                         foot_joint_names=[f'foot_{i}' for i in range(8)], rows=[])
        for step in range(1, 17):
            sample = copy.deepcopy(row)
            sample['step'] = step
            self.data['rows'].append(sample)

    def summary(self):
        self.path.write_text(json.dumps(self.data), encoding='utf-8')
        return summarize_hold(self.path)

    def test_constant_hold(self):
        result = self.summary()
        self.assertEqual(result['ended_time_s'], 8.)
        self.assertEqual(result['window_steps'], 4)
        self.assertEqual(len(result['envs']), 1)
        env = result['envs'][0]
        self.assertEqual(len(env['joints']), 8)
        for joint in env['joints'].values():
            for key in ('target_error_mean_rad', 'target_error_min_rad', 'target_error_max_rad'):
                self.assertAlmostEqual(joint[key], -.02)
            self.assertEqual(joint['position_drift_rad'], 0.)
            self.assertEqual(joint['max_abs_velocity_rad_s'], 0.)
        self.assertEqual(env['root_height_drift_m'], 0.)
        self.assertEqual(env['tilt_max_rad'], 0.)

    def test_drift_and_batched_envs(self):
        for row in self.data['rows']:
            for key in ('done', 'root_position', 'gravity_b', 'joint_positions',
                        'joint_targets', 'joint_velocities'):
                row[key].append(copy.deepcopy(row[key][0]))
        for row in self.data['rows'][-2:]:
            row['joint_positions'][1][0] = .13
            row['joint_velocities'][1][0] = -.07
            row['root_position'][1][2] = .61
            row['gravity_b'][1] = [math.sin(.2), 0., -math.cos(.2)]
        result = self.summary()
        self.assertEqual(result['envs'][0]['joints']['foot_0']['position_drift_rad'], 0.)
        env = result['envs'][1]
        joint = env['joints']['foot_0']
        self.assertAlmostEqual(joint['position_drift_rad'], .03)
        self.assertAlmostEqual(joint['target_error_mean_rad'], -.005)
        self.assertAlmostEqual(joint['target_error_min_rad'], -.02)
        self.assertAlmostEqual(joint['target_error_max_rad'], .01)
        self.assertAlmostEqual(joint['max_abs_velocity_rad_s'], .07)
        self.assertAlmostEqual(env['root_height_drift_m'], .01)
        self.assertAlmostEqual(env['tilt_max_rad'], .2)

    def test_reject_invalid_hold(self):
        original = copy.deepcopy(self.data)
        for case in ('safety', 'status', 'incomplete', 'duration', 'window', 'nonfinite', 'done'):
            with self.subTest(case=case):
                self.data = copy.deepcopy(original)
                if case == 'safety':
                    self.data['safety_failures'] = [{'env': 0, 'reason': 'tilt'}]
                elif case == 'status':
                    self.data['trial_status'] = 'failed'
                elif case == 'incomplete':
                    self.data['rows'].pop()
                elif case == 'duration':
                    del self.data['duration_s']
                elif case == 'window':
                    self.data['rows'] = self.data['rows'][-2:]
                elif case == 'nonfinite':
                    self.data['rows'][0]['joint_positions'][0][0] = 'nan'
                else:
                    self.data['rows'][0]['done'][0] = True
                with self.assertRaises(ValueError):
                    self.summary()


class TipriseTargetTest(unittest.TestCase):
    def test_phase_boundaries_and_all_node_intervals(self):
        # Load only the pure helper: importing the executable launches Isaac Sim.
        source = Path(__file__).resolve().parents[1] / 'diagnose/lizard2_two_axis_standing.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        helper = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'tiprise_target')
        namespace = {}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), 'exec'), namespace)
        target = namespace['tiprise_target']
        samples = [{'q_rad': {'leg': i * i / 100., 'tail': .3}} for i in range(11)]
        for time, phase, alpha in [(0., 'settle', 0.), (4., 'rise', 0.),
                                   (5., 'rise', .5), (6., 'hold', 1.),
                                   (7., 'fall', 1.), (8., 'fall', .5),
                                   (9., 'recovery', 0.), (10., 'recovery', 0.)]:
            actual_phase, actual_alpha, q = target(samples, time)
            self.assertEqual(actual_phase, phase)
            self.assertAlmostEqual(actual_alpha, alpha)
            self.assertEqual(q['tail'], .3)
        for i in range(10):
            for time in (4. + (i + .5) / 5., 9. - (i + .5) / 5.):
                _, _, q = target(samples, time)
                self.assertAlmostEqual(q['leg'], (i * i + (i + 1) ** 2) / 200.)


class FootControlSafetyTest(unittest.TestCase):
    def test_tiprise_initial_rotation_matches_fork_xyzw(self):
        source = (Path(__file__).resolve().parents[1] / 'diagnose/lizard2_two_axis_standing.py').read_text(encoding='utf-8')
        import ast
        assignments = [node for node in ast.walk(ast.parse(source))
                       if isinstance(node, ast.Assign) and any(
                           ast.unparse(target) == 'cfg.scene.robot.init_state.rot' for target in node.targets)]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(ast.literal_eval(assignments[0].value), (0., 0., 0., 1.))

    def test_pre_reset_rejects_each_failure_in_any_env(self):
        good = dict(done=[False, False], root_position=[[0., 0., .6]] * 2,
                    gravity_b=[[0., 0., -1.]] * 2,
                    joint_positions=[[0.] * 8 for _ in range(2)],
                    joint_velocities=[[0.] * 8 for _ in range(2)])
        limits = [[[-1., 1.]] * 8 for _ in range(2)]
        self.assertEqual(safety_failures(good, limits, list(range(8))), [])
        cases = [('done', None, True, 'done'),
                 ('joint_positions', 0, float('nan'), 'nonfinite'),
                 ('joint_velocities', 0, float('inf'), 'nonfinite'),
                 ('joint_positions', 0, 2., 'foot_limit_margin'),
                 ('root_position', 2, .449, 'root_height'),
                 ('gravity_b', 2, -math.cos(math.radians(31)), 'tilt')]
        cases += [('joint_positions', i, .981, 'foot_limit_margin') for i in range(8)]
        for field, index, value, reason in cases:
            with self.subTest(field=field, index=index, reason=reason):
                row = copy.deepcopy(good)
                if index is None:
                    row[field][1] = value
                else:
                    row[field][1][index] = value
                failures = safety_failures(row, limits, list(range(8)))
                self.assertIn({'env': 1, 'reason': reason}, failures)
                captured = row[field][1] if index is None else row[field][1][index]
                if isinstance(value, float) and math.isnan(value):
                    self.assertTrue(math.isnan(captured))
                else:
                    self.assertEqual(captured, value)
                # A clean reset must not erase the captured terminal frame's verdict.
                self.assertEqual(safety_failures(good, limits, list(range(8))), [])
                self.assertTrue(failures)


if __name__ == '__main__':
    unittest.main()
