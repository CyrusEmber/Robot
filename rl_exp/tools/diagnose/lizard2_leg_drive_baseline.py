# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline v7 fixed-root nominal self-weight and per-axis drive estimates; JSON to stdout."""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import yaml

from palm_spatial_inertia import _project, csc
from palm_spatial_tracking import _gravity_design
from rl_exp.tools.runrecord.binding import sha256_file as sha

ROOT = Path(__file__).resolve().parents[3]
RL = ROOT / 'rl_exp'
VERSION = RL / 'versions/lizard2/main/v7'
PARAMS = VERSION / 'main_params.yaml'
LOCK = VERSION / 'asset_lock.json'
ORDER = RL / 'versions/joint_order_runtime.json'
USD_KEY = 'lizard2_round_feet/lizard2_round_feet.usda'
URDF_KEY = 'lizard2_round_feet/lizard2_round_feet.urdf'
FEET = ('lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle')


def load_model(path, names):
    """Validate supported URDF tree and return its body tensors."""
    tree = ET.parse(path).getroot()
    links, joints = tree.findall('link'), tree.findall('joint')
    model = csc.load_urdf(path)
    assert len(links) == len(model['links']) and len(joints) == len(model['joints'])
    assert len(names) == len(set(names)) and set(names) == {j.get('name') for j in joints if j.get('type') == 'revolute'}
    assert all(j.get('type') in ('fixed', 'revolute') for j in joints)
    assert all(np.array_equal(np.fromstring(o.get('rpy', '0 0 0'), sep=' '), np.zeros(3))
               for o in tree.findall('.//origin')), 'unsupported origin rpy'
    edges = model['joints']
    children = [s['child'] for s in edges.values()]
    assert len(set(children)) == len(children) and set(children) == set(model['links']) - {'base_link'}
    assert all(s['parent'] in model['links'] and s['child'] in model['links'] and s['parent'] != s['child']
               and s['origin'].shape == (3,) and np.isfinite(s['origin']).all() for s in edges.values())
    # Detect disconnected cycles before calling chain_up, which assumes a tree.
    parent = {s['child']: s['parent'] for s in edges.values()}
    for link in model['links']:
        seen, current = set(), link
        while current != 'base_link':
            assert current not in seen and current in parent, 'disconnected/cyclic tree'
            seen.add(current)
            current = parent[current]
    for j in joints:
        axis = edges[j.get('name')]['axis']
        if j.get('type') == 'fixed':
            assert axis is None
        else:
            assert axis is not None and axis.shape == (3,) and np.isfinite(axis).all()
            assert abs(np.linalg.norm(axis) - 1) < 1e-7, 'axis not normalized'
            edges[j.get('name')]['axis'] = axis / np.linalg.norm(axis)
    bodies = {}
    for link in links:
        inertial = link.find('inertial')
        mass = float(inertial.find('mass').get('value'))
        com = np.fromstring(inertial.find('origin').get('xyz'), sep=' ')
        i = inertial.find('inertia')
        tensor = np.array([[float(i.get(k)) for k in row] for row in
                           (('ixx', 'ixy', 'ixz'), ('ixy', 'iyy', 'iyz'), ('ixz', 'iyz', 'izz'))])
        assert math.isfinite(mass) and mass > 0 and com.shape == (3,) and np.isfinite(com).all()
        assert np.isfinite(tensor).all() and np.linalg.eigvalsh(tensor).min() > 0
        bodies[link.get('name')] = dict(mass=mass, com=com, inertia=tensor)
    return model, bodies


def project(model, bodies, names, q):
    assert set(q) == set(names) and np.isfinite(list(q.values())).all()
    poses = {n: csc.fk(model['joints'], n, q) for n in bodies}
    matrix = _project(model['joints'], poses, names, bodies)
    assert np.isfinite(matrix).all() and np.allclose(matrix, matrix.T, rtol=1e-12, atol=1e-12)
    assert np.linalg.eigvalsh(matrix).min() > 0
    return matrix


def inputs():
    lock = json.loads(LOCK.read_text(encoding='utf-8'))['files']
    for key in (USD_KEY, URDF_KEY, 'versions/lizard2/main/v7/main_params.yaml'):
        assert sha(RL / key) == lock[key], 'asset lock mismatch: ' + key
    cfg = yaml.safe_load(PARAMS.read_text(encoding='utf-8'))
    assert cfg['robot']['usd_path'] == USD_KEY and cfg['robot']['base_body_name'] == 'base_link'
    assert cfg['robot']['base_init_rotation_xyzw'] == [0., 0., 0., 1.]
    names = [n + '_joint' for n in cfg['joint_order']]
    q = cfg['default_joint_pos']
    assert len(names) == 26 and set(names) == set(q) and all(v == 0. for v in q.values())
    runtime_doc = json.loads(ORDER.read_text(encoding='utf-8'))['assets'][USD_KEY]
    runtime = [n + '_joint' for n in runtime_doc['joint_order']]
    assert len(runtime) == len(set(runtime)) == 26 and set(runtime) == set(names)
    groups = cfg['actuators']
    assert set(groups) == {'legs', 'spine'}
    assert set(groups['legs']['joint_patterns']).isdisjoint(groups['spine']['joint_patterns'])
    assert set(groups['legs']['joint_patterns']) | set(groups['spine']['joint_patterns']) == set(names)
    for group, spec in groups.items():
        selected = set(spec['joint_patterns'])
        assert spec['armature'] == 0 and set(cfg['action']['joints'][group]) == selected
        assert set(cfg['action'][group + '_scale']) == set(cfg['action']['clip'][group]) == selected
        for field in ('stiffness', 'damping', 'effort_limit', 'velocity_limit'):
            assert set(spec[field]) == selected and all(math.isfinite(v) and v > 0 for v in spec[field].values())
    assert cfg['action']['use_default_offset'] is True
    model, bodies = load_model(RL / URDF_KEY, names)
    legs = groups['legs']['joint_patterns']
    assert len(legs) == 16
    for foot, prefix in zip(FEET, ('lf_', 'rf_', 'rl_', 'rr_')):
        ancestry = csc.chain_up(model['joints'], foot)
        assert ancestry[-1].endswith('_fixed') and len([n for n in ancestry if n in legs and n.startswith(prefix)]) == 4
    return cfg, names, runtime, model, bodies


def collision_bodies(stage, tree):
    """Match authored URDF and USD collision-bearing body names, without simulating."""
    from pxr import Usd, UsdPhysics

    assert stage is not None, 'missing USD stage'
    links = tree.findall('link')
    link_names = [link.get('name') for link in links]
    assert len(link_names) == len(set(link_names))
    bodies = [prim for prim in stage.Traverse() if prim.HasAPI(UsdPhysics.RigidBodyAPI)]
    names = [prim.GetName() for prim in bodies]
    assert len(names) == len(set(names)) == len(link_names) and set(names) == set(link_names)
    collision = set()
    for body in bodies:
        shapes = []
        for prim in Usd.PrimRange(body):
            if prim != body and prim.HasAPI(UsdPhysics.RigidBodyAPI):
                raise AssertionError('nested rigid body collision ownership requires runtime audit')
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                shapes.append(prim)
        assert all(UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() for prim in shapes)
        if shapes:
            collision.add(body.GetName())
    assert collision == {link.get('name') for link in links if link.find('collision') is not None}, \
        'URDF and USD collision bodies differ'
    return collision


def report():
    cfg, names, runtime, model, bodies = inputs()
    from pxr import Usd

    collisions = collision_bodies(Usd.Stage.Open(str(RL / USD_KEY)), ET.parse(RL / URDF_KEY).getroot())
    q = cfg['default_joint_pos']
    matrix = project(model, bodies, names, q)
    reference = {'snapshots': [{'label': 'neutral', 'joint_names': names, 'mass_matrix': matrix.tolist()}]}
    gravity = _gravity_design(reference, RL / URDF_KEY)
    assert gravity['joint_names'] == names
    torques = gravity['sampled_gravity_torque_nm'][0]
    spec = cfg['actuators']['legs']
    feet = {}
    for foot, prefix in zip(FEET, ('lf_', 'rf_', 'rl_', 'rr_')):
        axes = [n for n in spec['joint_patterns'] if n.startswith(prefix)]
        pose = {n: csc.fk(model['joints'], n, q) for n in bodies}
        contribution = np.diag(_project(model['joints'], pose, axes, {foot: bodies[foot]}))
        assert np.all(contribution > 0) and all(gravity['subtree_mass_kg'][n] >= bodies[foot]['mass'] for n in axes)
        feet[foot] = dict(mass_kg=bodies[foot]['mass'], upstream_joint_names=axes,
                          inertia_diagonal_contribution_kg_m2=contribution.tolist())
    rows = []
    for name in spec['joint_patterns']:
        i = names.index(name)
        inertia, kp, kd = float(matrix[i, i]), spec['stiffness'][name], spec['damping'][name]
        effort, velocity = spec['effort_limit'][name], spec['velocity_limit'][name]
        scale, clip = cfg['action']['legs_scale'][name], cfg['action']['clip']['legs'][name]
        assert math.isfinite(scale) and scale > 0 and len(clip) == 2 and clip[0] < 0 < clip[1]
        tau = torques[i]
        wn = math.sqrt(kp / inertia)
        rows.append(dict(joint=name, action_index=cfg['action']['joints']['legs'].index(name),
                         runtime_joint_index=runtime.index(name), kp=kp, kd=kd,
                         scale_rad_per_action=scale, target_clip_rad=clip, inertia_kg_m2=inertia,
                         wn_rad_s=wn, wn_hz=wn/(2*math.pi), zeta=kd/(2*math.sqrt(kp*inertia)),
                         gravity_torque_nm=tau, abs_gravity_torque_nm=abs(tau),
                         static_error_abs_rad=abs(tau)/kp, gravity_percent_effort=100*abs(tau)/effort,
                         kp_scale_percent_effort=100*kp*scale/effort,
                         endpoint_p_nm=[kp*x for x in clip], endpoint_p_percent_effort=[100*kp*x/effort for x in clip],
                         kd_velocity_limit_percent_effort=100*kd*velocity/effort,
                         velocity_limit_rad_s=velocity, effort_limit_nm=effort,
                         subtree_mass_kg=gravity['subtree_mass_kg'][name]))
    paths = [PARAMS, LOCK, RL / URDF_KEY, RL / USD_KEY, ORDER, Path(__file__),
             Path(__file__).with_name('palm_spatial_inertia.py'),
             Path(__file__).with_name('palm_spatial_tracking.py'), Path(csc.__file__)]
    return dict(inputs={str(p.resolve()): sha(p) for p in paths},
                runtime_order_source=[n.removesuffix('_joint') for n in runtime], pose_joint_rad=q,
                root_position_m=[0., 0., cfg['robot']['base_init_height']], root_quaternion_xyzw=[0., 0., 0., 1.],
                gravity_m_s2=[0., 0., -9.81], physics_dt_s=cfg['sim']['dt'],
                control_dt_s=cfg['sim']['dt'] * cfg['sim']['decimation'], all_joint_names=names,
                authored_collision_bodies=sorted(collisions),
                authored_no_collision_bodies=sorted(set(bodies) - collisions),
                all_joint_actuators=cfg['actuators'], all_joint_actions=cfg['action'],
                fixed_foot_contributions=feet, all_inertia_diagonal_kg_m2=np.diag(matrix).tolist(), rows=rows,
                limitations=['Fixed-root URDF nominal all-zero pose, not stable contact or support static load.',
                             'Gravity torque sign is applied gravity; holding compensation is opposite.',
                             'Local single-axis frequency is not closed-loop bandwidth; coupling ignored.',
                             'Clip is processed target range; endpoint P is instantaneous relative to zero, not saturation or margin.',
                             'Kp*scale and Kd*velocity-limit percentages are separate hypothetical terms, not simultaneous.',
                             'Configured limits are not measurements; actual torque, two-foot support, runtime settings and pass thresholds unjudged.',
                             'Authored URDF/USD collision-body lists require loaded-stage and backend binding before use.',
                             'Effective runtime target offsets require readback; they are not inferred from use_default_offset.',
                             'Runtime joint index is articulation order, not action-vector index; source names lack _joint suffix.',
                             'Projection uses the same fixed-root inertia convention as reflected_inertia, including fixed feet.'])


def contact_moments(model, names, frames, points, normal, friction, counts):
    """Project single-point ground forces [N] onto supplied joint frames [N·m]."""
    frames, points, normal, friction, counts = (np.asarray(x) for x in (frames, points, normal, friction, counts))
    n = len(names)
    if (frames.shape != (n, 4, 4) or points.shape != (n, 3) or normal.shape != (n, 3)
            or friction.shape != (n, 3) or counts.shape != (n,)
            or not np.isfinite(frames).all() or not np.isfinite(normal).all() or not np.isfinite(friction).all()
            or not np.isin(counts, (0, 1)).all() or not np.isfinite(points[counts == 1]).all()
            or np.any(np.linalg.norm(normal[counts == 0], axis=-1) > 1e-6)
            or np.any(np.linalg.norm(friction[counts == 0], axis=-1) > 1e-6)):
        raise ValueError('invalid or ambiguous contact data')
    axes = np.stack([frame[:3, :3] @ model['joints'][name]['axis'] for name, frame in zip(names, frames)])
    arm = np.where((counts == 1)[:, None], points - frames[:, :3, 3], 0.)
    n_moment = np.einsum('ij,ij->i', axes, np.cross(arm, normal))
    f_moment = np.einsum('ij,ij->i', axes, np.cross(arm, friction))
    return dict(normal_nm=n_moment, friction_nm=f_moment, total_nm=n_moment + f_moment)


def propulsion_report(arrays, joint_names):
    """Summarize single-point foot contact moments for recorded rollout samples [N·m]."""
    from palm_spatial_inertia import _rotation

    _, _, runtime, model, _ = inputs()
    if list(joint_names) != runtime:
        raise ValueError('recorded joint order mismatch')
    valid = np.asarray(arrays['valid'], dtype=bool)
    if valid.ndim != 2:
        raise ValueError('valid mask shape mismatch')
    steps, envs = valid.shape
    vector_shape = (steps, envs, 4, 3)
    for key in ('force_w_n', 'friction_w_n', 'contact_pos_w_m', 'foot_pos_w_m'):
        if np.shape(arrays[key]) != vector_shape:
            raise ValueError('vector shape mismatch: ' + key)
    for key in ('contact_count', 'friction_count'):
        if np.shape(arrays[key]) != (steps, envs, 4):
            raise ValueError('contact count shape mismatch')
    for key in ('joint_pos_rad', 'joint_velocity_rad_s', 'joint_target_rad'):
        if np.shape(arrays[key]) != (steps, envs, 26) or not np.isfinite(arrays[key][valid]).all():
            raise ValueError('joint state mismatch: ' + key)
    if (np.shape(arrays['root_pose_xyzw']) != (steps, envs, 7)
            or not np.isfinite(arrays['root_pose_xyzw'][valid]).all()
            or np.shape(arrays['step_count']) != (steps,)
            or np.any(np.diff(arrays['step_count']) != 1)):
        raise ValueError('root pose or physics-step sequence mismatch')
    normal, friction = arrays['force_w_n'], arrays['friction_w_n']
    points, centers = arrays['contact_pos_w_m'], arrays['foot_pos_w_m']
    counts, friction_counts = arrays['contact_count'], arrays['friction_count']
    if (not np.isfinite(normal[valid]).all() or not np.isfinite(friction[valid]).all()
            or not np.isfinite(centers[valid]).all() or (counts < 0).any() or (friction_counts < 0).any()
            or np.any(counts.sum(axis=1) >= 512) or np.any(friction_counts.sum(axis=1) >= 512)):
        raise ValueError('missing, invalid or possibly saturated contact buffer')
    names = [f'{leg}_{root}_swing_joint' for leg, root in
             (('lf', 'shoulder'), ('rf', 'shoulder'), ('rl', 'hip'), ('rr', 'hip'))]
    valid_times = np.repeat(valid[:, :, None], 4, axis=2)
    if np.any(np.linalg.norm(friction[(friction_counts == 0) & valid_times], axis=-1) > 1e-6):
        raise ValueError('contact buffer disagrees with force or point')
    loads = {leg: [] for leg in ('lf', 'rf', 'rl', 'rr')}
    tracking = {leg: [] for leg in loads}
    velocities = {leg: [] for leg in loads}
    ambiguities = 0
    weak_contacts = 0
    bad_points = 0
    for sample, env in np.argwhere(valid):
        q = dict(zip(runtime, arrays['joint_pos_rad'][sample, env]))
        root = np.eye(4)
        root[:3, :3] = _rotation(arrays['root_pose_xyzw'][sample, env, 3:])
        root[:3, 3] = arrays['root_pose_xyzw'][sample, env, :3]
        for leg, (name, foot) in enumerate(zip(names, FEET)):
            count = counts[sample, env, leg]
            if count > 1:
                ambiguities += 1
                continue
            if count == 1 and np.linalg.norm(normal[sample, env, leg] + friction[sample, env, leg]) <= 1.:
                weak_contacts += 1
                continue
            frame = root @ csc.fk(model['joints'], model['joints'][name]['child'], q)
            point = points[sample, env, leg]
            if count == 1:
                foot_frame = root @ csc.fk(model['joints'], foot, q)
                if np.linalg.norm(foot_frame[:3, 3] - centers[sample, env, leg]) > 1e-4:
                    raise ValueError('live foot center and URDF FK mismatch')
                if (not np.isfinite(point).all() or abs(np.linalg.norm(point - centers[sample, env, leg]) - .08) > .01
                        or abs(point[2]) > .01):
                    bad_points += 1
                    continue
            moment = contact_moments(model, [name], frame[None], point[None], normal[sample, env, leg][None],
                                     friction[sample, env, leg][None], np.array([count]))
            if count == 1:
                label, index = foot[:2], runtime.index(name)
                loads[label].append([float(moment[key][0]) for key in ('normal_nm', 'friction_nm', 'total_nm')])
                tracking[label].append(float(arrays['joint_target_rad'][sample, env, index] - q[name]))
                velocities[label].append(float(arrays['joint_velocity_rad_s'][sample, env, index]))
    result = {}
    for leg, values in loads.items():
        data = np.asarray(values)
        result[leg] = dict(samples=len(data), max_abs_nm=np.max(np.abs(data), axis=0).tolist() if len(data) else None,
                           p95_abs_nm=np.percentile(np.abs(data), 95, axis=0).tolist() if len(data) else None,
                           target_error_p95_rad=float(np.percentile(np.abs(tracking[leg]), 95)) if len(data) else None,
                           target_error_max_rad=float(np.max(np.abs(tracking[leg]))) if len(data) else None,
                           velocity_p95_rad_s=float(np.percentile(np.abs(velocities[leg]), 95)) if len(data) else None)
    return dict(valid_env_samples=int(valid.sum()), usable_contact_samples=sum(len(v) for v in loads.values()),
                multi_point_samples=ambiguities, contact_force_at_most_1n=weak_contacts,
                invalid_contact_point_samples=bad_points,
                multiple_friction_anchors=int(np.sum((friction_counts > 1) & valid_times)), legs=result,
                components=['normal', 'friction', 'total'],
                scope='ground-on-foot contact-moment proxy using normal point for friction; not actuator torque',
                limitations=['friction anchor locations were not captured; friction moment is approximate',
                             '1 N and 1 cm thresholds are measurement filters, not acceptance criteria',
                             'single trajectory, seed and checkpoint; contact spikes are not motor saturation'])


def support_report(foot_forces: dict[str, list[float]] | None = None) -> dict:
    """Estimate two-foot load sensitivity for a prescribed root-upright pose.

    Args:
        foot_forces: World-frame ground-on-foot forces [N] for all four named feet.
            None selects an illustrative, non-measured force.

    Returns:
        Per-axis fixed-root inertia [kg·m²], Jacobians [m], external and holding
        torques [N·m], and overall force [N] and moment [N·m] balance.
    """
    import lizard2_round_support_geometry as support

    cfg, names, _, model, bodies = inputs()
    weight = sum(body['mass'] for body in bodies.values()) * 9.81
    assumed_default = foot_forces is None
    if assumed_default:
        foot_forces = {foot: [0.1 * weight, 0., 0.5 * weight] for foot in FEET}
    if set(foot_forces) != set(FEET):
        raise ValueError('supply all four foot forces')
    foot_forces = {foot: np.asarray(value, dtype=float) for foot, value in foot_forces.items()}
    if not all(value.shape == (3,) and np.isfinite(value).all() for value in foot_forces.values()):
        raise ValueError('invalid foot force')
    geometry = support.run(RL / URDF_KEY)
    if not geometry['passed']:
        raise ValueError('support geometry failed')
    legs = cfg['actuators']['legs']
    groups = {}
    for label, group in geometry['groups'].items():
        q = group['solver']['q_rad']
        root = np.asarray(geometry['root_position_world_m'])
        poses = {n: csc.fk(model['joints'], n, q) for n in bodies}
        com = np.asarray(group['validation']['com_world_m'])
        feet = {}
        for foot in group['support']:
            sphere = next(g for g in group['validation']['geometry']
                          if g['link'] == foot and g['kind'] == 'collision')
            contact = np.asarray(sphere['center_world_m']) - [0., 0., sphere['radius_m']]
            feet[foot] = dict(contact_world_m=contact.tolist(), example_force_world_n=foot_forces[foot].tolist())
        forces = {foot: np.asarray(data['example_force_world_n']) for foot, data in feet.items()}
        points = {foot: np.asarray(data['contact_world_m']) for foot, data in feet.items()}
        required_force = -(sum(forces.values(), np.zeros(3)) + [0., 0., -weight])
        required_moment = -sum((np.cross(points[f] - com, forces[f]) for f in feet), np.zeros(3))
        inertia = project(model, bodies, names, q)
        rows = []
        for name in legs['joint_patterns']:
            spec = model['joints'][name]
            frame = poses[spec['child']]
            axis, joint = frame[:3, :3] @ spec['axis'], root + frame[:3, 3]
            gravity = sum(float(axis @ np.cross(poses[link][:3, :3] @ body['com']
                                                + poses[link][:3, 3] + root - joint,
                                                [0., 0., -9.81 * body['mass']]))
                          for link, body in bodies.items() if name in csc.chain_up(model['joints'], link))
            jacobian = {foot: np.cross(axis, points[foot] - joint) if name in csc.chain_up(model['joints'], foot)
                        else np.zeros(3) for foot in feet}
            contact = sum(float(jacobian[foot] @ forces[foot]) for foot in feet)
            holding = -(gravity + contact)
            kp, kd, limit = legs['stiffness'][name], legs['damping'][name], legs['effort_limit'][name]
            rows.append(dict(joint=name, axis_world=axis.tolist(), joint_world_m=joint.tolist(),
                             contact_jacobian_m={f: j.tolist() for f, j in jacobian.items()},
                             gravity_torque_nm=gravity, example_contact_torque_nm=contact,
                             example_holding_torque_nm=holding, v7_kp=kp, v7_kd=kd,
                             fixed_root_inertia_kg_m2=float(inertia[names.index(name), names.index(name)]),
                             configured_effort_limit_nm=limit, example_v7_static_error_abs_rad=abs(holding) / kp,
                             example_configured_effort_percent=100 * abs(holding) / limit))
        groups[label] = dict(q_rad=q, root_position_world_m=root.tolist(), com_world_m=com.tolist(), feet=feet,
                             example_required_guide_force_n=required_force.tolist(),
                             example_required_guide_moment_at_com_nm=required_moment.tolist(), rows=rows)
    paths = [PARAMS, LOCK, RL / USD_KEY, ORDER, Path(__file__), Path(csc.__file__),
             Path(__file__).with_name('palm_spatial_inertia.py')]
    hashes = dict(geometry['sha256'])
    hashes.update({str(p.resolve()): sha(p) for p in paths})
    return dict(geometry_passed=geometry['passed'], inputs_sha256=hashes, weight_n=weight,
                force_assumption='0.1mg forward and 0.5mg vertical per support foot' if assumed_default else 'user supplied',
                groups=groups,
                limitations=['Static prescribed pose and hypothetical forces; no actual contact or drive measurement.',
                             'Example assumes guide load on base, with required moment reported at COM; net balance only.',
                             'Gravity and contact torques are external; holding torque is their negative, excluding other loads.',
                             'Static error is local tau/Kp, not a solved equilibrium; configured effort is not verified runtime cap.',
                             'Fixed-root diagonal inertia is not the effective inertia under contact constraints.',
                             'Contact point is sphere bottom; dynamics, friction feasibility, guides and limits are unverified.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--two_foot', action='store_true', help='Report hypothetical guided two-foot load sensitivity')
    parser.add_argument('--foot_forces', type=Path, help='JSON map of four foot names to world-frame force vectors [N]')
    parser.add_argument('--propulsion_report', type=Path, help='Analyze recorded propulsion report and matching NPZ')
    args = parser.parse_args()
    if args.foot_forces and not args.two_foot:
        parser.error('--foot_forces requires --two_foot')
    if args.propulsion_report and (args.two_foot or args.foot_forces):
        parser.error('--propulsion_report cannot be combined with --two_foot')
    forces = json.loads(args.foot_forces.read_text(encoding='utf-8')) if args.foot_forces else None
    if args.propulsion_report:
        recorded = json.loads(args.propulsion_report.read_text(encoding='utf-8'))
        sample_path = args.propulsion_report.parent / recorded['propulsion_diagnostic']['samples']
        with np.load(sample_path, allow_pickle=False) as samples:
            result = propulsion_report(samples, recorded['runtime_joint_names'])
        result['input_sha256'] = {str(p): sha(p) for p in (args.propulsion_report, sample_path, RL / URDF_KEY, Path(__file__))}
    else:
        result = support_report(forces) if args.two_foot else report()
    print(json.dumps(result, indent=2, allow_nan=False))
