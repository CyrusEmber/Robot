# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline numerical and negative checks for the v7 fixed-root baseline."""
import copy
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

import numpy as np

import lizard2_leg_drive_baseline as baseline
from palm_spatial_inertia import _rotation


def rejects(fn, label):
    try:
        fn()
    except AssertionError:
        print('EXPECTED_REJECTION', label)
    else:
        raise AssertionError('negative check did not fail: ' + label)


def potential(model, bodies, q):
    total = 0.
    for name, body in bodies.items():
        pose = baseline.csc.fk(model['joints'], name, q)
        center = pose[:3, :3] @ body['com'] + pose[:3, 3]
        total += body['mass'] * 9.81 * center[2]
    return total


def run():
    assert np.allclose(_rotation([0, 0, math.sqrt(.5), math.sqrt(.5)]) @ [1, 0, 0], [0, 1, 0])
    # A 2 kg mass at x=.5 and 1 kg fixed foot at x=1: Iyy=.2+.5+.1+1=1.8.
    body = '<inertial><origin xyz="{xyz}" rpy="0 0 0"/><mass value="{mass}"/><inertia ixx=".1" iyy="{iyy}" izz=".1" ixy="0" ixz="0" iyz="0"/></inertial>'
    robot = ('<robot name="pendulum"><link name="base_link">' + body.format(xyz='0 0 0', mass=1, iyy='.1') +
             '</link><link name="tip">' + body.format(xyz='.5 0 0', mass=2, iyy='.2') +
             '</link><link name="foot">' + body.format(xyz='0 0 0', mass=1, iyy='.1') +
             '</link><joint name="chest_pitch_joint" type="revolute"><parent link="base_link"/>'
             '<child link="tip"/><origin xyz="0 0 0" rpy="0 0 0"/><axis xyz="0 1 0"/>'
             '<limit lower="-1" upper="1"/></joint><joint name="foot_fixed" type="fixed">'
             '<parent link="tip"/><child link="foot"/><origin xyz="1 0 0" rpy="0 0 0"/>'
             '</joint></robot>')
    with TemporaryDirectory() as temp:
        path = Path(temp) / 'pendulum.urdf'
        path.write_text(robot, encoding='utf-8')
        names = ['chest_pitch_joint']
        model, bodies = baseline.load_model(path, names)
        matrix = baseline.project(model, bodies, names, {names[0]: 0.})
        assert np.allclose(matrix, [[1.8]], atol=1e-12)
        ref = {'snapshots': [dict(label='neutral', joint_names=names, mass_matrix=matrix.tolist())]}
        g = baseline._gravity_design(ref, path)['sampled_gravity_torque_nm']
        assert np.isclose(g[0][0], 19.62, atol=1e-12)
        assert np.isclose(g[2][0], 19.62 * math.cos(.02), atol=1e-12)
        broken = copy.deepcopy(bodies)
        broken['foot']['mass'] = 0.
        rejects(lambda: np.testing.assert_allclose(baseline.project(model, broken, names, {names[0]: 0.}), [[1.8]]),
                'fixed_foot_mass_removed_from_projection')
        path.write_text(robot.replace('value="1"/><inertia', 'value="0"/><inertia', 1), encoding='utf-8')
        rejects(lambda: baseline.load_model(path, names), 'zero_mass')
        path.write_text(robot.replace('axis xyz="0 1 0"', 'axis xyz="0 2 0"'), encoding='utf-8')
        rejects(lambda: baseline.load_model(path, names), 'nonnormal_axis')
        path.write_text(robot, encoding='utf-8')
        rejects(lambda: baseline.load_model(path, ['wrong_joint']), 'axis_name_mismatch')
    cfg, names, runtime, model, bodies = baseline.inputs()
    matrix = baseline.project(model, bodies, names, cfg['default_joint_pos'])
    ref = {'snapshots': [dict(label='neutral', joint_names=names, mass_matrix=matrix.tolist())]}
    gravity = baseline._gravity_design(ref, baseline.RL / baseline.URDF_KEY)
    legs = cfg['actuators']['legs']['joint_patterns']
    # Independent potential derivative checks neutral plus +/- .02 single-axis samples for all legs.
    h = 1e-6
    for name in legs:
        index = names.index(name)
        for a, row in ((0., 0), (-.02, 1 + 2*index), (.02, 2 + 2*index)):
            qp, qm = {name: a+h}, {name: a-h}
            numerical = -(potential(model, bodies, qp) - potential(model, bodies, qm))/(2*h)
            assert abs(numerical - gravity['sampled_gravity_torque_nm'][row][index]) < 2e-7, name
    # Four fixed feet affect inertia and the nonzero-angle gravity in their own leg.
    with TemporaryDirectory() as temp:
        root = ET.parse(baseline.RL / baseline.URDF_KEY)
        for foot in baseline.FEET:
            root.find(f"link[@name='{foot}']/inertial/mass").set('value', '0')
        path = Path(temp) / 'no_feet.urdf'
        root.write(path, encoding='utf-8')
        without = baseline._gravity_design(ref, path)
        altered = copy.deepcopy(bodies)
        for foot in baseline.FEET:
            altered[foot]['mass'] = 0.
        no_mass = baseline.project(model, altered, names, cfg['default_joint_pos'])
        for prefix in ('lf_', 'rf_', 'rl_', 'rr_'):
            name = next(n for n in legs if n.startswith(prefix) and ('elbow' in n or 'knee' in n))
            i = names.index(name)
            assert matrix[i, i] > no_mass[i, i]
            row = 2 + 2*i
            assert abs(gravity['sampled_gravity_torque_nm'][row][i] - without['sampled_gravity_torque_nm'][row][i]) > .05
            rejects(lambda i=i: np.testing.assert_allclose(matrix[i, i], no_mass[i, i], rtol=1e-10),
                    prefix + 'foot_mass_mutation')
    from pxr import Usd
    stage = Usd.Stage.Open(str(baseline.RL / baseline.USD_KEY))
    tree = ET.parse(baseline.RL / baseline.URDF_KEY).getroot()
    collisions = baseline.collision_bodies(stage, tree)
    assert len(collisions) == 18 and set(baseline.FEET) <= collisions
    mutated = Usd.Stage.CreateInMemory()
    mutated.GetRootLayer().ImportFromString(stage.GetRootLayer().ExportToString())
    from pxr import UsdPhysics
    shape = next(prim for prim in mutated.Traverse() if prim.HasAPI(UsdPhysics.CollisionAPI))
    UsdPhysics.CollisionAPI(shape).GetCollisionEnabledAttr().Set(False)
    rejects(lambda: baseline.collision_bodies(mutated, tree), 'disabled USD collision')
    mutated = Usd.Stage.CreateInMemory()
    mutated.GetRootLayer().ImportFromString(stage.GetRootLayer().ExportToString())
    body = next(prim for prim in mutated.Traverse() if prim.HasAPI(UsdPhysics.RigidBodyAPI))
    nested = mutated.DefinePrim(str(body.GetPath()) + '/nested', 'Xform')
    UsdPhysics.RigidBodyAPI.Apply(nested)
    rejects(lambda: baseline.collision_bodies(mutated, tree), 'nested USD body')
    link = next(link for link in tree.findall('link') if link.find('collision') is not None)
    link.remove(link.find('collision'))
    rejects(lambda: baseline.collision_bodies(stage, tree), 'missing URDF collision')
    rejects(lambda: baseline.collision_bodies(None, tree), 'unreadable USD')
    result = baseline.report()
    assert len(result['rows']) == 16 and all(runtime[r['runtime_joint_index']] == r['joint']
                                             and cfg['action']['joints']['legs'][r['action_index']] == r['joint']
                                             for r in result['rows'])
    support = baseline.support_report()
    assert support['geometry_passed'] and set(support['groups']) == {'lf+rr', 'rf+rl'}
    weight = support['weight_n']
    assert np.isclose(weight, sum(b['mass'] for b in bodies.values()) * 9.81)
    for group in support['groups'].values():
        q, root = group['q_rad'], np.array(group['root_position_world_m'])
        forces = {foot: np.array(data['example_force_world_n']) for foot, data in group['feet'].items()}
        points = {foot: np.array(data['contact_world_m']) for foot, data in group['feet'].items()}
        local_points = {}
        for foot, point in points.items():
            pose = baseline.csc.fk(model['joints'], foot, q)
            local_points[foot] = pose[:3, :3].T @ (point - root - pose[:3, 3])
        force_sum = sum(forces.values(), np.array([0., 0., -weight]))
        moment_sum = sum((np.cross(points[f] - group['com_world_m'], forces[f]) for f in points), np.zeros(3))
        assert np.allclose(force_sum + group['example_required_guide_force_n'], 0., atol=1e-8)
        assert np.allclose(moment_sum + group['example_required_guide_moment_at_com_nm'], 0., atol=1e-8)
        inertia = baseline.project(model, bodies, names, q)
        for row in group['rows']:
            name = row['joint']
            assert np.isclose(row['fixed_root_inertia_kg_m2'], inertia[names.index(name), names.index(name)])
            joint = root + baseline.csc.fk(model['joints'], model['joints'][name]['child'], q)[:3, 3]
            assert np.allclose(row['joint_world_m'], joint)
            assert np.isclose(np.linalg.norm(row['axis_world']), 1.)
            qp, qm = dict(q), dict(q)
            qp[name] += h
            qm[name] -= h
            gravity_fd = -(potential(model, bodies, qp) - potential(model, bodies, qm)) / (2*h)
            assert abs(row['gravity_torque_nm'] - gravity_fd) < 2e-7, name
            for foot in points:
                pp, pm = (baseline.csc.fk(model['joints'], foot, pose) for pose in (qp, qm))
                jacobian_fd = (pp[:3, :3] @ local_points[foot] + pp[:3, 3]
                               - pm[:3, :3] @ local_points[foot] - pm[:3, 3]) / (2*h)
                actual = row['contact_jacobian_m'][foot]
                assert np.allclose(actual, jacobian_fd, atol=2e-7), (name, foot)
            expected = sum(np.dot(row['contact_jacobian_m'][foot], forces[foot]) for foot in points)
            assert np.isclose(row['example_contact_torque_nm'], expected, atol=1e-10)
            assert np.isclose(row['example_holding_torque_nm'], -(gravity_fd + expected), atol=2e-7)
            assert np.isclose(row['example_v7_static_error_abs_rad'], abs(row['example_holding_torque_nm']) / row['v7_kp'])
    custom_forces = {foot: [float(20 + 10*i), float(3*i), float(300 + 5*i)]
                     for i, foot in enumerate(baseline.FEET)}
    custom = baseline.support_report(custom_forces)
    for label, group in custom['groups'].items():
        for foot, data in group['feet'].items():
            assert data['example_force_world_n'] == custom_forces[foot]
        old_rows = {row['joint']: row for row in support['groups'][label]['rows']}
        for row in group['rows']:
            old = old_rows[row['joint']]
            expected_delta = sum(np.dot(row['contact_jacobian_m'][foot], np.array(custom_forces[foot]) - forces_old)
                                 for foot, forces_old in ((f, np.array(support['groups'][label]['feet'][f]['example_force_world_n']))
                                                          for f in group['feet']))
            assert np.isclose(row['example_contact_torque_nm'] - old['example_contact_torque_nm'], expected_delta)
    broken_forces = dict(custom_forces, lf_wrist=[float('nan'), 0., 1.])
    for bad_forces in ({}, broken_forces):
        try:
            baseline.support_report(bad_forces)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid assumed foot forces accepted')
    names = ('lf_shoulder_swing_joint', 'rf_shoulder_swing_joint', 'rl_hip_swing_joint', 'rr_hip_swing_joint')
    frame = np.tile(np.eye(4), (4, 1, 1))
    point = np.tile([1., 0., 0.], (4, 1))
    normal = np.tile([0., 0., 10.], (4, 1))
    friction = np.tile([0., 2., 0.], (4, 1))
    data = baseline.contact_moments(model, names, frame, point, normal, friction, np.ones(4, dtype=int))
    np.testing.assert_allclose(data['normal_nm'], 0.)
    np.testing.assert_allclose(data['friction_nm'], [2., -2., 2., -2.])
    np.testing.assert_allclose(data['total_nm'], [2., -2., 2., -2.])
    zero = baseline.contact_moments(model, names, frame, np.full((4, 3), np.nan),
                                    np.zeros((4, 3)), np.zeros((4, 3)), np.zeros(4, dtype=int))
    np.testing.assert_allclose(zero['total_nm'], 0.)
    try:
        baseline.contact_moments(model, names, frame, point, np.full((4, 3), np.nan), friction, np.ones(4, dtype=int))
    except ValueError:
        pass
    else:
        raise AssertionError('nonfinite force accepted')
    for bad_point, bad_count in ((point, np.array([2, 1, 1, 1])),
                                 (np.full((4, 3), np.nan), np.ones(4, dtype=int))):
        try:
            baseline.contact_moments(model, names, frame, bad_point, normal, friction, bad_count)
        except ValueError:
            pass
        else:
            raise AssertionError('unreliable contact point accepted')
    f = np.tile([0., 2., 0.], (1, 4, 4, 1))
    pt = np.tile([1., 0., 0.], (1, 4, 4, 1))
    fake = dict(valid=np.ones((1, 4), dtype=bool), step_count=np.array([1]),
                force_w_n=np.tile([0., 0., 10.], (1, 4, 4, 1)), friction_w_n=f, contact_pos_w_m=pt,
                contact_count=np.ones((1, 4, 4), dtype=int), friction_count=np.ones((1, 4, 4), dtype=int),
                joint_pos_rad=np.zeros((1, 4, 26)), joint_velocity_rad_s=np.zeros((1, 4, 26)),
                joint_target_rad=np.zeros((1, 4, 26)), root_pose_xyzw=np.tile([0., 0., 0., 0., 0., 0., 1.], (1, 4, 1)),
                foot_pos_w_m=np.zeros((1, 4, 4, 3)))
    fake['foot_pos_w_m'][:] = [baseline.csc.fk(model['joints'], foot, {})[:3, 3] for foot in baseline.FEET]
    fake['root_pose_xyzw'][..., 2] = -fake['foot_pos_w_m'][0, 0, 0, 2] + .08
    fake['foot_pos_w_m'] += fake['root_pose_xyzw'][..., None, :3]
    physical = dict(fake, contact_pos_w_m=fake['foot_pos_w_m'] + [0., 0., -.08])
    assert baseline.propulsion_report(physical, runtime)['usable_contact_samples'] == 16
    analysis = baseline.propulsion_report(physical, runtime)
    assert analysis['legs']['lf']['target_error_p95_rad'] == 0.
    changed_target = dict(physical, joint_target_rad=physical['joint_target_rad'].copy())
    changed_target['joint_target_rad'][..., runtime.index(names[0])] = .2
    assert np.isclose(baseline.propulsion_report(changed_target, runtime)['legs']['lf']['target_error_p95_rad'], .2)
    missing_friction = dict(physical, friction_count=np.zeros((1, 4, 4), dtype=int))
    try:
        baseline.propulsion_report(missing_friction, runtime)
    except ValueError:
        pass
    else:
        raise AssertionError('friction force without a friction anchor accepted')
    bad_point = dict(physical, contact_pos_w_m=physical['contact_pos_w_m'] + [0., 0., -1.])
    bad_analysis = baseline.propulsion_report(bad_point, runtime)
    assert bad_analysis['usable_contact_samples'] == 0 and bad_analysis['invalid_contact_point_samples'] == 16
    missing_point = dict(physical, contact_pos_w_m=np.full((1, 4, 4, 3), np.nan))
    assert baseline.propulsion_report(missing_point, runtime)['invalid_contact_point_samples'] == 16
    corrupted = dict(fake, step_count=np.array([2, 4]))
    try:
        baseline.propulsion_report(corrupted, runtime)
    except ValueError:
        pass
    else:
        raise AssertionError('misaligned propulsion step count accepted')
    print('OFFLINE_BASELINE_TEST_OK: inertia, gravity, collision and contact virtual-work checks')


if __name__ == '__main__':
    run()
