# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline structural checks for the isolated fixed-sphere foot candidate."""

import ast
import copy
import struct
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.diagnose.lizard2_round_feet import SOURCE, build_tree, validate_tree
from rl_exp.tools.diagnose.lizard2_round_feet_probe import check_interface, check_columns, check_reset_rows


class RoundFeetTest(unittest.TestCase):
    def test_live_task_resolves_native_presets(self):
        import gymnasium as gym
        import rl_exp.tasks
        from isaaclab_tasks.utils.hydra import PresetCfg
        from isaaclab_physx.sensors.contact_sensor.contact_sensor_cfg import ContactSensorCfg

        tree = ast.parse(Path(__file__).with_name('obs_protocol_live.py').read_text(encoding='utf-8'))
        check = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'check_task')
        end = next(i for i, n in enumerate(check.body) if isinstance(n, ast.Assign)
                   and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'env_cfg')
        construction = check.body[:end + 1]
        legacy = copy.deepcopy(construction)
        legacy[-1].value = ast.parse(
            'getattr(__import__(module_name, fromlist=[cls_name]), cls_name)()').body[0].value
        for task in ('Lizard2-Flat-v7', 'Lizard2-Flat-Play-v7'):
            for unresolved, statements in ((False, construction), (True, legacy)):
                with self.subTest(task=task, unresolved=unresolved):
                    scope = dict(gym=gym, task_id=task)
                    exec(compile(ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[])),
                                 '<check_task config construction>', 'exec'), scope)
                    sensor = scope['env_cfg'].scene.head_ground_contact
                    if unresolved:
                        self.assertIsInstance(sensor, PresetCfg)
                        with self.assertRaises(AssertionError):
                            self.assertIsInstance(sensor, ContactSensorCfg)
                    else:
                        self.assertIsInstance(sensor, ContactSensorCfg)
                        self.assertNotIsInstance(sensor, PresetCfg)
                        self.assertEqual(sensor.prim_path, '{ENV_REGEX_NS}/Robot/Geometry/neck_pitch')
                        self.assertEqual(sensor.history_length, 4)
                        self.assertEqual(sensor.filter_prim_paths_expr,
                                         ['/World/ground/terrain/GroundPlane/CollisionPlane'])

    def _formal_stimulus(self):
        import types
        import torch
        from isaaclab.utils.math import quat_from_euler_xyz
        from rl_exp.tools.diagnose import lizard2_round_feet_probe as probe
        tree = ast.parse(Path(probe.__file__).read_text(encoding='utf-8'))
        formal = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'formal_probe')
        start = next(i for i, n in enumerate(formal.body) if isinstance(n, ast.Assign)
                     and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('axis', 'action'))
        end = next(i for i, n in enumerate(formal.body[start:], start)
                   if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                   and isinstance(n.value.func, ast.Attribute)
                   and n.value.func.attr == 'write_root_pose_to_sim_index')
        data = types.SimpleNamespace(default_joint_pos=types.SimpleNamespace(torch=torch.zeros(2, 26)),
                                     joint_pos_limits=types.SimpleNamespace(torch=torch.tensor([-1., 1.]).repeat(2, 26, 1)))
        default = torch.zeros(2, 13)
        default[:, 6] = 1.
        scope = dict(torch=torch, quat_from_euler_xyz=quat_from_euler_xyz,
                     live=types.SimpleNamespace(device='cpu'), root_default=default,
                     robot=types.SimpleNamespace(data=data))
        exec(compile(ast.Module(body=formal.body[start:end], type_ignores=[]), '<formal stimulus>', 'exec'), scope)
        return scope

    def test_formal_stimulus_cross_env(self):
        scope = self._formal_stimulus()
        for key in ('q', 'dq', 'action'):
            values = scope[key].tolist()
            self.assertTrue(all(a != b for a, b in zip(*values)), key)
            for row in values:
                self.assertTrue(all(v != 0 for v in row), key)
                self.assertEqual(len(set(row)), 26, key)
                with self.assertRaises(ValueError):
                    check_columns([row[0]] * 26, row, key)
            with self.assertRaises(ValueError):
                check_columns(values[0], values[1], key)
    def test_formal_stimulus_transform(self):
        import torch
        from isaaclab.utils.math import quat_apply_inverse
        root = self._formal_stimulus()['root']
        for segment in (slice(7, 10), slice(10, 13)):
            source = quat_apply_inverse(root[:, 3:7], root[:, segment]).tolist()
            for i in range(2):
                with self.assertRaises(ValueError):
                    check_columns(root[i, segment].tolist(), source[i], 'unrotated velocity')
            self.assertTrue(all(a != b for a, b in zip(*source)))
        gravity = quat_apply_inverse(root[:, 3:7], torch.tensor([[0., 0., -1.]]).repeat(2, 1)).tolist()
        for row in gravity:
            check_columns(row, row, 'gravity', require_nonzero=True)
            with self.assertRaises(ValueError):
                check_columns([0., 0., -1.], row, 'unrotated gravity')
        with self.assertRaises(ValueError):
            check_columns(gravity[0], gravity[1], 'broadcast gravity')

    def test_reset_extra_fields_and_byte_preservation(self):
        fields = ('command', 'processed', 'targets', 'backend_targets')
        before = {key: [[.1, -.2], [.3, -0.]] for key in fields}
        after = copy.deepcopy(before)
        for key in fields:
            after[key][0] = [.7, .8]  # Selected persistence/change allowed, not forced zero.
        check_reset_rows(before, after, {}, [0])
        for key in fields:
            bad = copy.deepcopy(after)
            bad[key][1][0] = .4
            with self.assertRaises(ValueError):
                check_reset_rows(before, bad, {}, [0])
        bad = copy.deepcopy(after)
        bad['command'][1][1] = 0.
        self.assertNotEqual(struct.pack('d', before['command'][1][1]), struct.pack('d', 0.))
        with self.assertRaises(ValueError):
            check_reset_rows(before, bad, {}, [0])

    def test_nonzero_columns_and_reset_residue(self):
        expected = [.13, -.24, .35]
        check_columns(expected, expected, 'velocity', require_nonzero=True)
        for bad in ([0., 0., 0.], expected[::-1], expected[:-1], [float('nan'), -.24, .35]):
            with self.assertRaises(ValueError):
                check_columns(bad, expected, 'velocity', require_nonzero=True)
        with self.assertRaises(ValueError):
            check_columns([0., 0.], [0., 0.], 'false nonzero', require_nonzero=True)
        before = dict(root=[[1., 2.], [3., 4.]], action=[[.1], [.2]],
                      prev_action=[[.3], [.4]], episode_length=[7, 8])
        after = dict(root=[[0., 0.], [3., 4.]], action=[[0.], [.2]],
                     prev_action=[[0.], [.4]], episode_length=[0, 8])
        defaults = dict(root=[[0., 0.], [0., 0.]])
        check_reset_rows(before, after, defaults, [0])
        for field in ('root', 'action', 'prev_action', 'episode_length'):
            bad = copy.deepcopy(after)
            bad[field][0] = copy.deepcopy(before[field][0])
            with self.assertRaises(ValueError):
                check_reset_rows(before, bad, defaults, [0])
        bad = copy.deepcopy(after)
        bad['action'][1] = [0.]
        with self.assertRaises(ValueError):
            check_reset_rows(before, bad, defaults, [0])

    def test_complete_interface_and_negative_routes(self):
        names = [f'joint_{i}' for i in range(26)]
        mapping = [dict(joint=name, global_index=i, joint_index=25-i,
                        scale=.5, offset=.2, clip=[-.5, .5]) for i, name in enumerate(names)]
        loaded = names[::-1]
        raw = [0.] * 26
        raw[3] = .02
        processed = [.2] * 26
        processed[3] = .21
        targets = processed[::-1]
        check_interface(names, loaded, mapping, raw, processed, targets)
        for bad in (mapping[:-1], mapping[:-1] + [mapping[0]]):
            with self.assertRaises(ValueError):
                check_interface(names, loaded, bad)
        misrouted = targets.copy()
        misrouted[22], misrouted[21] = misrouted[21], misrouted[22]
        with self.assertRaises(ValueError):
            check_interface(names, loaded, mapping, raw, processed, misrouted)
        bad = targets.copy()
        bad[0] = float('nan')
        with self.assertRaises(ValueError):
            check_interface(names, loaded, mapping, raw, processed, bad)
        check_interface(names, loaded, mapping, raw, processed, targets, backend=targets)
        for backend in (misrouted, bad, targets[:-1], [float('inf')] + targets[1:]):
            with self.assertRaises(ValueError):
                check_interface(names, loaded, mapping, raw, processed, targets, backend=backend)
        raw[3] = 2.
        processed[3] = .5
        targets = processed[::-1]
        check_interface(names, loaded, mapping, raw, processed, targets)

    def test_candidate_preserves_upstream_and_replaces_all_four_feet(self):
        validate_tree(ET.parse(SOURCE), build_tree(SOURCE, .08), .08)

    def test_elbow_override_and_default_limits(self):
        source = ET.parse(SOURCE)
        for desired in (None, 1.0):
            candidate = (build_tree(SOURCE, .08) if desired is None else
                         build_tree(SOURCE, .08, elbow_limit=desired))
            validate_tree(source, candidate, .08, elbow_limit=desired)
            for name in ('lf_elbow_joint', 'rf_elbow_joint', 'rl_knee_joint', 'rr_knee_joint'):
                limit = candidate.getroot().find(f"joint[@name='{name}']/limit")
                expected = desired if desired is not None and 'elbow' in name else 1.2
                self.assertEqual([float(limit.get(k)) for k in ('lower', 'upper')], [-expected, expected])
            for joint in source.getroot().findall('joint'):
                if 'twist' in joint.get('name'):
                    self.assertEqual(ET.tostring(joint), ET.tostring(candidate.getroot().find(
                        f"joint[@name='{joint.get('name')}']")))

    def test_elbow_override_rejects_unrequested_changes(self):
        candidate = build_tree(SOURCE, .08, elbow_limit=1.0)
        for name, key, value in (
                ('lf_elbow_joint', 'upper', '1.2'),
                ('rf_elbow_joint', 'lower', '-1.2'),
                ('rl_knee_joint', 'upper', '1.0'),
                ('rr_knee_joint', 'lower', '-1.0'),
                ('lf_elbow_joint', 'effort', '1')):
            with self.subTest(name=name, key=key):
                bad = copy.deepcopy(candidate)
                bad.getroot().find(f"joint[@name='{name}']/limit").set(key, value)
                with self.assertRaises(AssertionError):
                    validate_tree(ET.parse(SOURCE), bad, .08, elbow_limit=1.0)
        with self.assertRaises(AssertionError):
            validate_tree(ET.parse(SOURCE), candidate, .08)
        with self.assertRaises(AssertionError):
            validate_tree(ET.parse(SOURCE), build_tree(SOURCE, .08), .08, elbow_limit=1.0)

    def test_invalid_elbow_limits_rejected(self):
        candidate = build_tree(SOURCE, .08)
        for desired in (float('nan'), float('inf'), -float('inf'), 0., -1., 1.200001):
            with self.subTest(desired=desired):
                with self.assertRaises(ValueError):
                    build_tree(SOURCE, .08, elbow_limit=desired)
                with self.assertRaises(ValueError):
                    validate_tree(ET.parse(SOURCE), candidate, .08, elbow_limit=desired)

    def test_original_feet_do_not_satisfy_replacement_contract(self):
        with self.assertRaises(AssertionError):
            validate_tree(ET.parse(SOURCE), ET.parse(SOURCE), .08)

    def test_active_mount_or_upstream_change_is_rejected(self):
        candidate = build_tree(SOURCE, .08)
        bad = copy.deepcopy(candidate)
        bad.getroot().find("joint[@name='lf_wrist_fixed']").set('type', 'revolute')
        with self.assertRaises(AssertionError):
            validate_tree(ET.parse(SOURCE), bad, .08)
        bad = copy.deepcopy(candidate)
        bad.getroot().find("joint[@name='lf_elbow_joint']/limit").set('upper', '0.01')
        with self.assertRaises(AssertionError):
            validate_tree(ET.parse(SOURCE), bad, .08)


if __name__ == '__main__':
    unittest.main()
