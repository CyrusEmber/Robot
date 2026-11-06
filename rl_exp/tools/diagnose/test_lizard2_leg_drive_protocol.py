# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline synthetic checks; no simulator or physical execution."""
import ast
import copy
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import yaml

import lizard2_leg_drive_baseline as base
import lizard2_leg_drive_protocol as p
from lizard2_round_feet_probe import check_interface


def rejects(fn, label):
    try:
        fn()
    except p.Stop:
        print('EXPECTED_STOP', label)
    else:
        raise AssertionError('not rejected: ' + label)


def probe_adapter():
    path = Path(__file__).with_name('lizard2_shank_use_probe.py')
    nodes = [node for node in ast.parse(path.read_text(encoding='utf-8')).body
             if isinstance(node, ast.FunctionDef) and node.name == 'leg_drive_candidate']
    assert len(nodes) == 1, 'native probe must expose candidate adapter'
    namespace = {'np': np, 'math': math}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['leg_drive_candidate']


def native_step_adapter():
    path = Path(__file__).with_name('lizard2_shank_use_probe.py')
    node = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body
                if isinstance(n, ast.FunctionDef) and n.name == 'leg_drive_step')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['leg_drive_step']


def run():
    path = Path(__file__).with_name('lizard2_shank_use_probe.py')
    tree = ast.parse(path.read_text(encoding='utf-8'))
    with TemporaryDirectory() as temporary:
        parent = Path(temporary)
        out = parent / 'retry02.json'
        for name in ('failure.json', 'startup.json', 'plan.json', 'case_00.npz', 'result.json'):
            (parent / name).write_bytes(b'original evidence')
        original = {path.name: path.read_bytes() for path in parent.iterdir()}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'leg_drive_output_paths']
        assert len(nodes) == 1, 'same-directory calibration output mapping missing'
        namespace = {'json': json}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        paths = namespace['leg_drive_output_paths'](out)
        assert paths['result'] == out
        assert all(p.parent == parent and p.name.startswith('retry02_') for k, p in paths.items() if k != 'result')
        assert len(set(paths.values())) == len(paths)
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'leg_drive_reserve_outputs']
        assert len(nodes) == 1, 'exclusive reservation must reject collisions before execution'
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        reserve = namespace['leg_drive_reserve_outputs']
        paths['plan'].write_bytes(b'prior plan')
        try:
            reserve(out)
        except FileExistsError:
            pass
        else:
            raise AssertionError('orphaned plan accepted as fresh run')
        assert not paths['startup'].exists() and paths['plan'].read_bytes() == b'prior plan'
        paths['plan'].unlink()
        assert reserve(out) == paths and json.loads(paths['startup'].read_text())['status'] == 'constructing_environment'
        paths['startup'].unlink()
        for name, artifact in paths.items():
            with artifact.open('xb') as stream:
                stream.write(name.encode())
        assert original == {name: (parent / name).read_bytes() for name in original}
        before = {path.name: path.read_bytes() for path in parent.iterdir()}
        try:
            with paths['startup'].open('xb') as stream:
                stream.write(b'overwritten')
        except FileExistsError:
            pass
        else:
            raise AssertionError('duplicate attempt overwrote startup')
        assert before == {path.name: path.read_bytes() for path in parent.iterdir()}
    assert any(isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'app'
                                                     for target in node.targets) for node in tree.body), \
        'AppLauncher must start on the normal path'
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'leg_drive_candidate']
    assert calls, 'native candidate adapter is not used'
    preflight = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'leg_drive_preflight')
    preflight_calls = [node for node in ast.walk(preflight) if isinstance(node, ast.Call)]
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr in
                   ('step', 'forward', 'write_joint_stiffness_to_sim_index', 'write_joint_damping_to_sim_index')
                   for node in preflight_calls)
    wrapper_assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                           and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                           and node.value.func.id == 'RslRlVecEnvWrapper']
    calibration_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Name) and node.func.id == 'leg_drive_calibration']
    assert wrapper_assignments and calibration_calls
    assert min(node.lineno for node in calibration_calls) < min(node.lineno for node in wrapper_assignments), \
        'fixed-root calibration must not let the RL wrapper reset the environment'
    arguments = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_argument'
                 and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == '--leg_drive_preflight']
    assert len(arguments) == 1
    calibration = next((node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'leg_drive_calibration'), None)
    assert calibration is not None, 'native A/B calibration loop is missing'
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == 'leg_drive_calibration' for node in ast.walk(tree)), 'calibration loop is not routed'
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == 'leg_drive_step' for node in ast.walk(calibration)), 'missing per-frame stop integration'
    candidate = probe_adapter()
    bind = next((node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'leg_drive_contact_views'), None)
    assert any(isinstance(node, ast.Attribute) and node.attr == 'env_regex_ns'
               for node in ast.walk(bind)), 'contact binding must use the resolved runtime environment namespace'
    propulsion = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute)
                  and isinstance(node.value, ast.Attribute) and node.value.attr == 'contact_view']
    assert not any(node.attr == 'prim_paths' for node in propulsion), 'contact view has no prim_paths'
    assert any(node.attr == 'sensor_paths' for node in propulsion), 'contact source identity not bound'
    sample = next((node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == 'leg_drive_contact_sample'), None)
    assert bind is not None and sample is not None, 'missing native contact setup or substep sampling'
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == 'get_contact_force_matrix' for node in ast.walk(sample))
    step = next((node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'leg_drive_step'), None)
    assert step is not None, 'missing native per-physics-step stop integration'
    called = [node for node in ast.walk(step) if isinstance(node, ast.Call)]
    assert any(isinstance(node.func, ast.Attribute) and node.func.attr == 'check_frame' for node in called)
    assert any(isinstance(node.func, ast.Name) and node.func.id == 'leg_drive_contact_sample' for node in called)
    adapter = native_step_adapter()
    call_order = []
    class FakeManager:
        def apply_action(self): call_order.append('apply')
    class FakeScene:
        def write_data_to_sim(self): call_order.append('write')
        def update(self, dt): call_order.append('update')
    class FakeSim:
        def step(self, render=False): call_order.append('step')
    class FakeLive:
        action_manager = FakeManager()
        scene = FakeScene()
        sim = FakeSim()
        physics_dt = .005
    try:
        adapter(FakeLive(), None, None, None, None, None)
    except ValueError:
        pass
    else:
        raise AssertionError('unbound native contact accepted')
    assert call_order == [], 'stepped without bound contact'
    import types
    import torch
    class Array:
        def __init__(self, value): self.torch = torch.as_tensor(value, dtype=torch.float32)
    class View:
        def __init__(self): self.targets = torch.zeros((2, 26))
        def get_dof_position_targets(self): return self.targets
    class Robot:
        joint_names = [f'joint{i}' for i in range(26)]
        body_names = [f'body{i}' for i in range(31)]
        root_view = View()
        data = types.SimpleNamespace(joint_pos_target=Array(np.zeros((2, 26))),
                                     joint_pos=Array(np.zeros((2, 26))), joint_vel=Array(np.zeros((2, 26))),
                                     root_link_pose_w=Array(np.tile([0, 0, 2, 0, 0, 0, 1], (2, 1))))
    robot = Robot()
    binding = dict(views=[{'body0': 1}, {'body0': 1}], collision_names=['body0'],
                   root_pose=np.tile([0, 0, 2, 0, 0, 0, 1], (2, 1)),
                   joint_names=robot.joint_names, body_names=robot.body_names)
    adapter.__globals__['leg_drive_contact_sample'] = lambda views, body_names, dt: np.zeros((2, 31, 3))
    limits = np.tile([[-1., 1.]], (2, 26, 1))
    caps = np.full((2, 26), 10.)
    robot.root_view.targets[:] = .1
    try:
        adapter(FakeLive(), robot, np.zeros(26), limits, caps, binding)
    except ValueError:
        pass
    else:
        raise AssertionError('wrong pre-step backend target accepted')
    assert 'step' not in call_order
    assert binding['last_frame']['stage'] == 'before_step' and binding['stopped']
    assert np.all(binding['last_frame']['readback'] == .1)
    binding['stopped'] = False
    robot.root_view.targets[:] = 0
    call_order.clear()
    adapter(FakeLive(), robot, np.zeros(26), limits, caps, binding)
    assert call_order == ['apply', 'write', 'step', 'update']
    robot.data.joint_vel.torch[1, 0] = 5.
    call_order.clear()
    try:
        adapter(FakeLive(), robot, np.zeros(26), limits, caps, binding)
    except RuntimeError as exc:
        assert str(exc) == 'velocity'
    else:
        raise AssertionError('over-speed physical substep was accepted')
    assert call_order == ['apply', 'write', 'step', 'update'] and binding['last_frame']['velocity'][1, 0] == 5.
    assert binding['last_frame']['stop'] == {'env': 1, 'reason': 'velocity'}
    binding['stopped'] = False
    robot.data.joint_vel.torch[1, 0] = 0
    vectors = np.zeros((2, 31, 3)); vectors[0, 0, 2] = 2.
    adapter.__globals__['leg_drive_contact_sample'] = lambda views, body_names, dt: vectors
    try:
        adapter(FakeLive(), robot, np.zeros(26), limits, caps, binding)
    except RuntimeError as exc:
        assert str(exc) == 'contact'
    else:
        raise AssertionError('unsafe ground force accepted')
    assert binding['last_frame']['contact_vectors'][0, 0, 2] == 2.
    failed = binding['last_frame']
    call_order.clear()
    try:
        adapter(FakeLive(), robot, np.zeros(26), limits, caps, binding)
    except ValueError:
        pass
    else:
        raise AssertionError('continued after failed substep')
    assert call_order == [] and binding['last_frame'] is failed
    binding['stopped'] = False
    adapter.__globals__['leg_drive_contact_sample'] = lambda views, body_names, dt: np.zeros((2, 31, 3))
    robot.data.joint_pos.torch[0, 0] = float('nan')
    try:
        adapter(FakeLive(), robot, np.zeros(26), limits, caps, binding)
    except RuntimeError as exc:
        assert 'finite' in str(exc)
    else:
        raise AssertionError('non-finite position accepted')
    assert np.isnan(binding['last_frame']['q'][0, 0])
    binding['stopped'] = False
    robot.data.joint_pos.torch[0, 0] = 0
    for data_field in ('joint_vel', 'root_link_pose_w'):
        value = getattr(robot.data, data_field).torch
        saved = value[0, 0].item(); value[0, 0] = float('nan')
        try:
            adapter(FakeLive(), robot, np.zeros(26), limits, caps, binding)
        except (RuntimeError, ValueError):
            pass
        else:
            raise AssertionError('non-finite ' + data_field + ' accepted')
        binding['stopped'] = False
        value[0, 0] = saved
    call_order.clear()
    try:
        adapter(FakeLive(), robot, np.zeros(25), limits, caps, binding)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid target accepted')
    assert call_order == [], 'invalid plan reached action manager'
    adapter.__globals__['leg_drive_contact_sample'] = lambda *args: (_ for _ in ()).throw(ValueError('contact missing'))
    try:
        adapter(FakeLive(), robot, np.zeros(26), limits, caps, binding)
    except ValueError:
        pass
    else:
        raise AssertionError('missing ground data accepted')
    assert binding['last_frame']['contact'] is None and 'contact missing' in binding['last_frame']['contact_status']
    binding['stopped'] = False
    adapter.__globals__['leg_drive_contact_sample'] = lambda views, body_names, dt: np.zeros((2, 31, 3))
    previous = np.zeros((8, 2, 26))
    previous[:, 0, 0] = [0, .01, -.02, .04, -.08, .12, .11, .1]
    robot.data.joint_pos.torch[0, 0] = .09
    try:
        adapter(FakeLive(), robot, np.zeros(26), limits, caps, binding, constant_window=previous)
    except RuntimeError as exc:
        assert str(exc) == 'growing oscillation'
    else:
        raise AssertionError('growing oscillation ignored by native adapter')
    source = np.tile(np.arange(1., 27.), (2, 1))
    groups = [('lf', 'shoulder'), ('rf', 'shoulder'), ('rl', 'hip'), ('rr', 'hip')]
    names = ([f'{leg}_{root}_swing_joint' for leg, root in groups]
             + [f'{leg}_{root}_{axis}_joint' for leg, root in groups for axis in ('abduct', 'twist')]
             + [f'{leg}_{end}_joint' for leg, end in (('lf', 'elbow'), ('rf', 'elbow'), ('rl', 'knee'), ('rr', 'knee'))]
             + [f'j{i}' for i in range(10)])
    inertia = np.linspace(.2, 1.2, 26)
    kp, kd = candidate(names, source, source + 10, inertia)
    assert np.array_equal(kp[0], source[0]) and np.array_equal(kd[0], source[0] + 10)
    np.testing.assert_allclose(kp[1, :4], source[1, :4] * 2)
    np.testing.assert_allclose(kd[1, :4], (source[1, :4] + 10) * math.sqrt(2))
    assert np.array_equal(kp[1, 4:], source[1, 4:]) and np.array_equal(kd[1, 4:], source[1, 4:] + 10)
    assert np.array_equal(source, np.tile(np.arange(1., 27.), (2, 1)))
    try:
        candidate(names, np.stack((source[0], source[0] + 1)), np.stack((source[0], source[0])), inertia)
    except ValueError:
        pass
    else:
        raise AssertionError('unequal paired baseline gains accepted')
    bad_swing = names.copy(); bad_swing[0] = 'other_swing_joint'
    for bad_names, bad_kp, bad_kd in ((names[:-1], source, source), (names, source[:1], source),
                                      (names, np.full((2, 26), np.nan), source), (bad_swing, source, source)):
        try:
            candidate(bad_names, bad_kp, bad_kd, inertia)
        except (ValueError, RuntimeError):
            pass
        else:
            raise AssertionError('invalid native candidate accepted')
    path = Path(__file__).resolve().parents[2] / 'versions/lizard2/main/v7/main_params.yaml'
    cfg = yaml.safe_load(path.read_text(encoding='utf-8'))
    names = [n + '_joint' for n in cfg['joint_order']]
    legs = cfg['actuators']['legs']['joint_patterns']
    default = np.array([cfg['default_joint_pos'][n] for n in names])
    cases = p.cases(legs)
    swing_cases = p.swing_cases(legs)
    assert len(swing_cases) == len({case.id for case in swing_cases}) == 8
    assert all(case.gain == 'A' and case.gravity == 'on' and case.kind == 'sin'
               and len(case.axes) == 1 and case.axes[0].endswith('_swing_joint') for case in swing_cases)
    assert {case.frequency for case in swing_cases} == {.5, 1.}
    assert sum(case.steps for case in swing_cases) == 12800
    rejects(lambda: p.swing_cases(legs[:-1]), 'incomplete swing plan')
    compare_swing = next((node for node in tree.body if isinstance(node, ast.FunctionDef)
                          and node.name == 'leg_drive_swing_compare'), None)
    assert compare_swing is not None, 'swing comparison must consume recorded flat metrics'
    comparison_scope = {}
    exec(compile(ast.Module(body=[compare_swing], type_ignores=[]), str(path), 'exec'), comparison_scope)
    metrics = {}
    for case in swing_cases:
        other = p.Case('B', case.gravity, case.kind, case.axes, case.frequency)
        metrics[case.id], metrics[other.id] = {'rms': 1.0}, {'rms': .75}
    compared = comparison_scope['leg_drive_swing_compare'](swing_cases, metrics)
    assert len(compared) == 8 and all(value['rms_improvement_fraction'] == .25 for value in compared.values())
    assert len(cases) == len({c.id for c in cases}) == 208
    assert sum(c.steps for c in cases) == 476800
    for gain in p.GAINS:
        selected = p.cases(legs, gain=gain)
        assert len(selected) == 104 and sum(c.steps for c in selected) == 238400
        for gravity in p.GRAVITIES:
            selected = p.cases(legs, gain=gain, gravity=gravity)
            assert len(selected) == 52 and sum(c.steps for c in selected) == 119200
    self_weight = p.cases(legs, gravity='on')
    assert len(self_weight) == 104 and sum(c.steps for c in self_weight) == 238400
    groups = cfg['actuators']
    kp = np.array([next(spec['stiffness'][n] for spec in groups.values() if n in spec['stiffness']) for n in names])
    kd = np.array([next(spec['damping'][n] for spec in groups.values() if n in spec['damping']) for n in names])
    inertia = np.array(base.report()['all_inertia_diagonal_kg_m2'])
    new_kp, new_kd = p.candidate_gains(names, kp, kd, inertia)
    for i, name in enumerate(names):
        expected_kp = inertia[i] * (4 * math.pi)**2 if name.endswith('_swing_joint') else kp[i]
        expected_kd = 1.4 * math.sqrt(expected_kp * inertia[i]) if name.endswith('_swing_joint') else kd[i]
        assert np.isclose(new_kp[i], expected_kp) and np.isclose(new_kd[i], expected_kd)
    rejects(lambda: p.candidate_gains(names, kp[:-1], kd, inertia), 'candidate gain shape')
    for bad in (inertia[:-1], np.zeros(26), np.full(26, np.nan)):
        rejects(lambda: p.candidate_gains(names, kp, kd, bad), 'candidate inertia')
    changed = inertia.copy(); swing = next(i for i, name in enumerate(names) if name.endswith('_swing_joint'))
    changed[swing] *= 1.1
    altered_kp, altered_kd = p.candidate_gains(names, kp, kd, changed)
    assert set(np.flatnonzero(new_kp != altered_kp)) == {swing}
    assert set(np.flatnonzero(new_kd != altered_kd)) == {swing}
    rejects(lambda: p.cases(legs[:-1]), 'missing axis')
    rejects(lambda: p.cases(legs, gain='C'), 'unknown candidate')
    hold = next(c for c in cases if c.kind == 'hold' and len(c.axes) == 1)
    combo = next(c for c in cases if len(c.axes) == 4)
    h = p.trajectory(hold, names, default)
    rejects(lambda: p.trajectory(hold, names, np.ones(26)), 'wrong default target')
    idx = names.index(hold.axes[0])
    assert h['target'].shape == (3400, 26) and h['time'][-1] == 17
    for w in h['windows'].values():
        assert w.sum() == 100
    assert np.allclose(h['target'][h['windows']['positive_hold'], idx], .1)
    assert np.allclose(h['target'][h['windows']['negative_hold'], idx], -.1)
    assert np.allclose(h['target'][h['windows']['positive_return'], idx], 0)
    assert np.allclose(h['target'][h['windows']['negative_return'], idx], 0)
    for frame in (1030, 1129, 1200, 2000, 2320, 3399):
        held = (frame // 4) * .02
        if 5 <= held < 7:
            x = (held - 5) / 2
            expected = .1 * (10 * x**3 - 15 * x**4 + 6 * x**5)
        elif 7 <= held < 8:
            expected = .1
        else:
            continue
        assert abs(h['target'][frame, idx] - expected) < 1e-12
    c = p.trajectory(combo, names, default)
    assert np.allclose(c['target'][h['windows']['positive_hold']][:, [names.index(x) for x in combo.axes]], .1)
    assert np.count_nonzero(c['target'][1600]) == 4
    result = p.measure(hold, names, default, sample_names=names, time=h['time'],
                       target_readback=h['target'], q=h['target'])
    assert result['precision_pass'] and result['other_offset'] == 0
    q = h['target'].copy()
    q[h['windows']['positive_hold'], idx] += .06
    assert not p.measure(hold, names, default, sample_names=names, time=h['time'],
                         target_readback=h['target'], q=q)['precision_pass']
    q = h['target'].copy()
    q[h['windows']['settle'], (idx + 1) % 26] = np.linspace(0, .004, 100)
    q[1000:, (idx + 1) % 26] = .021
    assert not p.measure(hold, names, default, sample_names=names, time=h['time'],
                         target_readback=h['target'], q=q)['precision_pass']
    q = h['target'].copy()
    q[2000:, (idx + 1) % 26] = .03
    assert p.measure(hold, names, default, sample_names=names, time=h['time'],
                     target_readback=h['target'], q=q)['other_offset'] == .03
    rejects(lambda: p.measure(hold, names, default, sample_names=names[::-1], time=h['time'],
                              target_readback=h['target'], q=q), 'axis order')
    rejects(lambda: p.measure(hold, names, default, sample_names=names, time=h['time'][:-1],
                              target_readback=h['target'], q=q), 'dropped frame')
    time = h['time'].copy(); time[20] += .005
    rejects(lambda: p.measure(hold, names, default, sample_names=names, time=time,
                              target_readback=h['target'], q=q), 'misaligned time')
    target = h['target'].copy(); target[1000, idx] = .1
    rejects(lambda: p.measure(hold, names, default, sample_names=names, time=h['time'],
                              target_readback=target, q=q), 'target mismatch')
    cfg_runtime, _, runtime, _, _ = base.inputs()
    action_names = cfg_runtime['action']['joints']['legs'] + cfg_runtime['action']['joints']['spine']
    mapping = []
    for i, name in enumerate(action_names):
        group = 'legs' if i < 16 else 'spine'
        mapping.append(dict(joint=name, global_index=i, joint_index=runtime.index(name),
                            scale=cfg_runtime['action'][group + '_scale'][name],
                            offset=cfg_runtime['default_joint_pos'][name], clip=cfg_runtime['action']['clip'][group][name]))
    runtime_default = np.array([cfg_runtime['default_joint_pos'][n] for n in runtime])
    unique = p.cases(legs, gain='A', gravity='off')
    assert {(c.kind, c.axes, c.frequency) for c in unique} == {(c.kind, c.axes, c.frequency) for c in cases}
    for case in unique:
        target_rows = p.trajectory(case, runtime, runtime_default)['target'][::p.DECIMATION]
        for target in target_rows:
            raw = np.empty(26)
            for m in mapping:
                i, j = m['global_index'], m['joint_index']
                assert m['clip'][0] <= target[j] <= m['clip'][1]
                raw[i] = (target[j] - m['offset']) / m['scale']
            processed = [raw[m['global_index']] * m['scale'] + m['offset'] for m in mapping]
            check_interface(runtime, runtime, mapping, raw, processed, target, backend=target)
    case = next(c for c in unique if c.kind == 'hold' and len(c.axes) == 1)
    target = p.trajectory(case, runtime, runtime_default)['target'][1600]
    raw = np.empty(26)
    for m in mapping:
        raw[m['global_index']] = (target[m['joint_index']] - m['offset']) / m['scale']
    processed = [raw[m['global_index']] * m['scale'] + m['offset'] for m in mapping]
    broken = target.copy(); broken[runtime.index(case.axes[0])] = 0.
    try:
        check_interface(runtime, runtime, mapping, raw, processed, target, backend=broken)
    except ValueError:
        pass
    else:
        raise AssertionError('wrong backend target accepted')
    for freq in (.5, 1.):
        sin = next(c for c in cases if c.kind == 'sin' and c.frequency == freq)
        tr = p.trajectory(sin, names, default)
        assert len(tr['time']) == (2000 if freq == .5 else 1200)
        assert tr['windows']['measure'].sum() == round(3 / freq / p.DT)
        # Four physical samples see the same command from the control-frame start.
        assert np.all(tr['target'].reshape(-1, 4, 26) == tr['target'].reshape(-1, 4, 26)[:, :1, :])
        t = tr['time']; q = tr['target'].copy(); idx = names.index(sin.axes[0])
        q[:, idx] = .08 * np.sin(2 * np.pi * freq * (t - 2) - .3)
        m = p.measure(sin, names, default, sample_names=names, time=t, target_readback=tr['target'], q=q)
        assert np.isclose(m['amplitude'], .08) and np.isclose(m['phase_rad'], -.3)
        assert m['fit_residual'] < 1e-12
        mask = tr['windows']['measure']
        assert np.isclose(m['rms'], np.sqrt(np.mean((q[mask, idx] - tr['target'][mask, idx])**2)))
        assert m['rms'] > 0
        q = tr['target'].copy()
        settled = tr['windows']['settle']
        q[settled, (idx + 1) % 26] = np.tile([-.002, .002], settled.sum() // 2)
        q[tr['time'] > 2, (idx + 1) % 26] = .017
        assert p.measure(sin, names, default, sample_names=names, time=t,
                         target_readback=tr['target'], q=q)['precision_pass']
        q[:, idx] *= .1
        assert p.measure(sin, names, default, sample_names=names, time=t,
                         target_readback=tr['target'], q=q)['phase_rad'] is None
    body = [f'body{i}' for i in range(31)]
    args = dict(names=names, expected_names=names[:], planned_target=np.zeros(26), target=np.zeros(26), readback=np.zeros(26),
                q=np.zeros(26), velocity=np.zeros(26), limits=np.tile([-1., 1.], (26, 1)),
                velocity_cap=np.full(26, 10.), root_displacement=np.zeros(3), root_rotation=0.,
                contact=np.zeros(31), body_names=body, expected_body_names=body[:],
                collision_body_names=body[:18], contact_body_names=body[:18])
    p.check_frame(**args)
    measured = np.zeros(31); measured[0] = .5
    p.check_frame(**dict(args, contact=measured))
    rejects(lambda: p.check_frame(**dict(args, contact_body_names=body[:17])), 'missing collision sensor')
    rejects(lambda: p.check_frame(**dict(args, contact_body_names=body[:18] + ['unknown'])), 'unknown collision sensor')
    rejects(lambda: p.check_frame(**dict(args, contact_body_names=body[:18] + [body[0]])), 'duplicate collision sensor')
    measured[20] = .5
    rejects(lambda: p.check_frame(**dict(args, contact=measured)), 'noncollision body contact')
    arbitrary = np.full(26, .2)
    rejects(lambda: p.check_frame(**dict(args, target=arbitrary, readback=arbitrary, q=arbitrary)),
            'unverified arbitrary target')
    for label, field, value in (
        ('joint order', 'names', names[::-1]), ('body coverage', 'body_names', body[:-1]),
        ('readback', 'readback', np.full(26, .01)), ('nonfinite', 'q', np.full(26, np.nan)),
        ('root translation', 'root_displacement', [0, 0, .00101]), ('root rotation', 'root_rotation', .00101),
        ('joint limit', 'q', np.full(26, 1.02)), ('tracking', 'q', np.full(26, .36)),
        ('velocity', 'velocity', np.full(26, 5)), ('contact', 'contact', np.full(31, 1.01)),
        ('missing contact', 'contact', np.zeros(30)), ('missing cap', 'velocity_cap', np.zeros(26)),
    ):
        broken = dict(args); broken[field] = value
        rejects(lambda: p.check_frame(**broken), label)
    history = np.zeros((9, 26)); history[:, 0] = [0, .01, -.02, .04, -.08, .12, .11, .1, .09]
    broken = dict(args, q=history[-1], constant_window=history)
    rejects(lambda: p.check_frame(**broken), 'growing oscillation')
    history[:, 0] = [0, .1, -.1, .1, -.1, .1, .09, .08, .07]
    p.check_frame(**dict(args, q=history[-1], constant_window=history))
    # Populate every matching case, so absent or malformed cases cannot hide.
    results = {}
    for case in cases:
        metrics = {'safety': 'pass', 'settle_drift': .001, 'other_offset': .001}
        if case.kind == 'sin':
            metrics.update(max_error=.08, fit_residual=.005)
            metrics['rms'] = .04 if case.gain == 'A' else (.036 if case.axes[0].endswith('_swing_joint') else .044)
        else:
            metrics['errors'] = {w: [.02] * len(case.axes) for w in
                                 ('positive_hold', 'positive_return', 'negative_hold', 'negative_return')}
        results[case.id] = metrics
    assert p.compare(legs, results)['suspended_subset'] == 'pass'
    assert p.compare(legs, results)['overall'] == 'unjudged'
    candidate = next(c for c in cases if c.gain == 'B' and c.kind == 'sin' and c.axes[0].endswith('_swing_joint'))
    broken = copy.deepcopy(results); broken[candidate.id]['rms'] = .037
    assert p.compare(legs, broken)['cases'][candidate.id] == 'fail'
    broken[candidate.id]['rms'] = float('nan')
    assert p.compare(legs, broken)['cases'][candidate.id] == 'unjudged'
    broken[candidate.id]['safety'] = 'stop'; broken[candidate.id]['precision_pass'] = False
    assert p.compare(legs, broken)['suspended_subset'] == 'stop'
    assert p.compare(legs, broken)['case_status'][candidate.id] == 'stop'
    broken = copy.deepcopy(results); broken[candidate.id]['rms'] = 0.
    broken[candidate.id]['max_error'] = .2
    assert p.compare(legs, broken)['cases'][candidate.id] != 'pass'
    broken = copy.deepcopy(results); broken[candidate.id]['precision_pass'] = True
    del broken[candidate.id]['fit_residual']
    assert p.compare(legs, broken)['cases'][candidate.id] == 'unjudged'
    broken = copy.deepcopy(results); del broken[candidate.id]
    assert p.compare(legs, broken)['suspended_subset'] == 'unjudged'
    baseline = p.Case('A', candidate.gravity, candidate.kind, candidate.axes, candidate.frequency)
    broken[baseline.id]['safety'] = 'stop'
    assert p.compare(legs, broken)['suspended_subset'] == 'stop'
    broken = copy.deepcopy(results); del broken[baseline.id]
    failed = next(c for c in cases if c.gain == 'A' and c.kind == 'sin' and c != baseline)
    failed_pair = p.Case('B', failed.gravity, failed.kind, failed.axes, failed.frequency)
    del broken[failed_pair.id]
    broken[failed.id]['max_error'] = .2
    assert p.compare(legs, broken)['suspended_subset'] == 'fail'
    assert p.compare(legs, broken)['case_status'][failed.id] == 'fail'
    assert p.compare(legs, broken)['case_status'][failed_pair.id] == 'unjudged'
    broken = copy.deepcopy(results); broken[candidate.id] = None
    assert p.compare(legs, broken)['cases'][candidate.id] == 'unjudged'
    combo = next(c for c in cases if c.gain == 'B' and len(c.axes) == 4)
    broken = copy.deepcopy(results); broken[combo.id]['errors']['negative_return'][2] = .025
    assert p.compare(legs, broken)['cases'][combo.id] == 'fail'
    rejects(lambda: p.compare(legs, {'bad id': {}}), 'unknown result')
    print('PASS: 208 unique cases, 476800 physics steps, synthetic tracking and safety checks')


if __name__ == '__main__':
    run()
