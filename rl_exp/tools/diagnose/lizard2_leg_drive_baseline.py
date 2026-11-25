# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline v7 fixed-root nominal self-weight and per-axis drive estimates; JSON to stdout."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from rl_exp.robots import lizard2_round_feet as robot
from rl_exp.tools.runrecord.binding import sha256_file as sha
from rl_exp.tools.verify import check_self_collision
from rl_exp.tools.verify.check_self_collision import chain_up, fk, load_urdf

ROOT = Path(__file__).resolve().parents[3]
RL = ROOT / 'rl_exp'
USD_KEY = 'lizard2_round_feet/lizard2_round_feet.usda'
URDF_KEY = 'lizard2_round_feet/lizard2_round_feet.urdf'
FEET = ('lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle')
SWING = ('lf_shoulder_swing_joint', 'rf_shoulder_swing_joint', 'rl_hip_swing_joint', 'rr_hip_swing_joint')


def _rotation(quat):
    x, y, z, w = np.asarray(quat, dtype=float)
    assert np.isfinite(quat).all() and abs(x*x + y*y + z*z + w*w - 1) < 1e-5
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def _project(joints, poses, names, bodies):
    """Project body tensors about their COM into fixed-base joint coordinates [kg*m^2]."""
    result = np.zeros((len(names), len(names)))
    for link, body in bodies.items():
        pose = poses[link]
        center = pose[:3, :3] @ body['com'] + pose[:3, 3]
        linear, angular = np.zeros((3, len(names))), np.zeros((3, len(names)))
        ancestry = chain_up(joints, link)
        for k, name in enumerate(names):
            if name not in ancestry:
                continue
            spec = joints[name]
            frame = poses[spec['child']]
            axis = frame[:3, :3] @ spec['axis']
            angular[:, k] = axis
            linear[:, k] = np.cross(axis, center - frame[:3, 3])
        world_tensor = pose[:3, :3] @ body['inertia'] @ pose[:3, :3].T
        result += angular.T @ world_tensor @ angular + body['mass'] * linear.T @ linear
    return result


def _gravity_design(reference, urdf):
    """Per-joint gravity moment at neutral and single-axis +/-0.02 rad, and the kp/kd it implies."""
    model = load_urdf(urdf)
    names = reference['snapshots'][0]['joint_names']
    links = ET.parse(urdf).getroot().findall('link')
    masses = {l.get('name'): float(l.find('inertial/mass').get('value')) for l in links}
    centers = {l.get('name'): np.fromstring(l.find('inertial/origin').get('xyz'), sep=' ') for l in links}
    chains = {n: chain_up(model['joints'], n) for n in masses}
    poses = [{}] + [{n: a} for n in names for a in (-.02, .02)]
    moments = []
    for q in poses:
        frames = {n: fk(model['joints'], n, q) for n in masses}
        com = {n: frames[n][:3, :3] @ centers[n] + frames[n][:3, 3] for n in masses}
        row = []
        for n in names:
            spec = model['joints'][n]
            frame = frames[spec['child']]
            axis = frame[:3, :3] @ spec['axis']
            axis /= np.linalg.norm(axis)
            row.append(sum(float(axis @ np.cross(com[l]-frame[:3, 3], [0., 0., -9.81*masses[l]]))
                           for l in masses if n in chains[l]))
        moments.append(row)
    moments = np.asarray(moments)
    inertia = np.diag(next(s['mass_matrix'] for s in reference['snapshots'] if s['label'] == 'neutral'))
    load = np.abs(moments).max(axis=0)
    kp = np.maximum(inertia*(2*math.pi)**2, load/.03)
    kd = 2*np.sqrt(inertia*kp)
    chest = names.index('chest_pitch_joint')
    assert load[chest] < 280. and moments[0, chest] != 0
    return dict(joint_names=names, sampled_gravity_torque_nm=moments.tolist(),
                max_gravity_torque_nm=load.tolist(), neutral_inertia_diagonal=inertia.tolist(),
                kp=kp.tolist(), kd=kd.tolist(), gravity_m_s2=[0., 0., -9.81], static_error_scale_rad=.03,
                subtree_mass_kg={n: sum(masses[l] for l in masses if n in chains[l]) for n in names},
                chest_amplitude_rad=float(-np.sign(moments[0, chest])*.02),
                scope='fixed-root downstream self-weight at neutral and single-axis +/-0.02 rad; not contact support')


def _params():
    """The live v7 configuration in the shape the report reads (the YAML it used to read is retired)."""
    from rl_exp import lizard2_v7

    env = lizard2_v7.make_env_cfg()
    articulation = env.scene.robot
    actions = {'joints': {}, 'clip': {}, 'use_default_offset': env.actions.joint_pos_legs.use_default_offset}
    for group in ('legs', 'spine'):
        action = getattr(env.actions, f'joint_pos_{group}')
        actions['joints'][group] = list(action.joint_names)
        actions[group + '_scale'] = {name: action.scale[name] for name in action.joint_names}
        actions['clip'][group] = {name: list(action.clip[name]) for name in action.joint_names}
    actuators = {}
    for group, spec in articulation.actuators.items():
        joints = list(spec.joint_names_expr)

        def limit(field):
            value = getattr(spec, field)
            return {n: (value[n] if isinstance(value, dict) else value) for n in joints}

        actuators[group] = {'joint_patterns': joints, 'armature': spec.armature,
                            'stiffness': dict(spec.stiffness), 'damping': dict(spec.damping),
                            'effort_limit': limit('effort_limit_sim'),
                            'velocity_limit': limit('velocity_limit_sim')}
    return {'robot': {'usd_path': USD_KEY, 'base_body_name': robot.BELLY_BODY,
                      'base_init_rotation_xyzw': [0., 0., 0., 1.],
                      'base_init_height': float(articulation.init_state.pos[2])},
            'sim': {'dt': env.sim.dt, 'decimation': env.decimation},
            'actuators': actuators, 'action': actions,
            'default_joint_pos': dict(articulation.init_state.joint_pos)}


def load_model(path, names):
    """Validate supported URDF tree and return its body tensors."""
    tree = ET.parse(path).getroot()
    links, joints = tree.findall('link'), tree.findall('joint')
    model = load_urdf(path)
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
    poses = {n: fk(model['joints'], n, q) for n in bodies}
    matrix = _project(model['joints'], poses, names, bodies)
    assert np.isfinite(matrix).all() and np.allclose(matrix, matrix.T, rtol=1e-12, atol=1e-12)
    assert np.linalg.eigvalsh(matrix).min() > 0
    return matrix


def inputs():
    assert sha(RL / USD_KEY) == robot.MEASURED_USD_SHA256, 'formal USD bytes moved since the order was measured'
    assert sha(RL / URDF_KEY) == robot.MEASURED_URDF_SHA256, 'formal URDF bytes moved since the order was measured'
    tree = ET.parse(RL / URDF_KEY).getroot()
    names = [j.get('name') for j in tree.findall('joint') if j.get('type') == 'revolute']
    cfg = _params()
    assert cfg['robot']['usd_path'] == USD_KEY and cfg['robot']['base_body_name'] == 'base_link'
    assert cfg['robot']['base_init_rotation_xyzw'] == [0., 0., 0., 1.]
    q = cfg['default_joint_pos']
    assert len(names) == 26 and set(names) == set(q) == set(robot.ACTION_JOINTS)
    assert all(v == 0. for v in q.values())
    runtime = list(robot.MEASURED_JOINT_ORDER)
    assert len(runtime) == len(set(runtime)) == 26 and set(runtime) == set(names)
    order = hashlib.sha256('|'.join(runtime).encode()).hexdigest()
    assert order == robot.MEASURED_ORDER_SHA256, (
        'the measured articulation order moved since it was recorded\n'
        f'      recorded: {robot.MEASURED_ORDER_SHA256}\n'
        f'      module:   {order}\n'
        '      re-measure with lizard2_shank_use_probe.py --leg_drive_preflight, then approve the new'
        ' order and digest together')
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
        ancestry = chain_up(model['joints'], foot)
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
        pose = {n: fk(model['joints'], n, q) for n in bodies}
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
    paths = [RL / URDF_KEY, RL / USD_KEY, Path(__file__), Path(robot.__file__),
             Path(check_self_collision.__file__)]
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
            frame = root @ fk(model['joints'], model['joints'][name]['child'], q)
            point = points[sample, env, leg]
            if count == 1:
                foot_frame = root @ fk(model['joints'], foot, q)
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


def two_foot_trim(label: str) -> dict:
    """Solve swing offsets that put the projected centre of mass under a diagonal support line.

    Args:
        label: Support pair from the offline geometry (``'lf+rr'``, ``'rf+rl'``), or ``'both'`` to
            solve all four swing axes together so the two diagonals cross under the centre of mass.

    Returns:
        Joint-space offsets [rad] on swing axes only, chosen so the contact points keep their heights
        and the stance keeps its height, plus the residuals. Kinematic only: no contact compliance,
        and a centre of mass on the line leaves no restoring margin.
    """
    import lizard2_round_support_geometry as support

    _, names, _, model, bodies = inputs()
    geometry = support.run(RL / URDF_KEY)
    if label != 'both' and label not in geometry['groups']:
        raise ValueError('unknown support group: ' + label)
    if not (geometry['passed'] if label == 'both' else geometry['groups'][label]['passed']):
        raise ValueError('support geometry solve failed for ' + label)
    group = geometry['groups']['lf+rr' if label == 'both' else label]
    # "both" answers a default-pose question, so it starts from the zero pose rather than a stance
    # with the opposite pair folded and the tail pitched.
    base = {name: 0. for name in names} if label == 'both' else dict(group['solver']['q_rad'])
    feet = list(group['support']) if label != 'both' else list(FEET)
    pairs = [(feet[0], feet[3]), (feet[1], feet[2])] if label == 'both' else [(feet[0], feet[1])]
    shapes = [g for item in geometry['groups'].values() for g in item['validation']['geometry']]
    radius = {foot: next(g['radius_m'] for g in shapes
                         if g['link'] == foot and g['kind'] == 'collision') for foot in feet}
    root = np.asarray(geometry['root_position_world_m'])
    mass = sum(body['mass'] for body in bodies.values())
    trims = [next(name for name in SWING if name.startswith(foot[:2] + '_')) for foot in feet]
    # Swing axes are vertical, so the contact points move in the horizontal plane only: the stance
    # keeps its height and its foot heights, and only the support line moves under the mass.
    mirror = {name: float(np.sign(model['joints'][name]['axis'][2])) for name in trims}

    def state(values):
        q = dict(base)
        for name, value in zip(trims, values):
            q[name] += value * mirror[name]
        poses = {n: fk(model['joints'], n, q) for n in bodies}
        com = sum(body['mass'] * (poses[n][:3, :3] @ body['com'] + poses[n][:3, 3])
                  for n, body in bodies.items()) / mass + root
        points = {foot: np.asarray(poses[foot][:3, 3]) + root - [0., 0., radius[foot]] for foot in feet}
        return com, points

    def crossing(points):
        (a, b), (c, d) = ((points[p[0]], points[p[1]]) for p in pairs)
        first = np.array([b[0] - a[0], b[1] - a[1]])
        second = np.array([d[0] - c[0], d[1] - c[1]])
        t = np.linalg.solve(np.column_stack((first, -second)), np.array([c[0] - a[0], c[1] - a[1]]))
        return a[:2] + t[0] * first

    def residual(values):
        com, points = state(values)
        if label == 'both':
            return crossing(points) - com[:2], com, points
        a, b = points[feet[0]], points[feet[1]]
        line = np.array([b[0] - a[0], b[1] - a[1], 0.])
        line /= np.linalg.norm(line)
        normal = np.array([-line[1], line[0], 0.])
        return np.array([(com - a) @ normal, a[2] - b[2]]), com, points

    values, damping = np.zeros(len(trims)), 1e-4
    for _ in range(300):
        f = residual(values)[0]
        if float(np.linalg.norm(f)) < 1e-9:
            break
        jac = np.zeros((len(f), len(trims)))
        for k in range(len(trims)):
            step = np.zeros(len(trims))
            step[k] = 1e-6
            jac[:, k] = (residual(values + step)[0] - f) / 1e-6
        step = jac.T @ np.linalg.solve(jac @ jac.T + damping * np.eye(len(f)), f)
        scale = min(1., .05 / max(float(np.abs(step).max()), 1e-12))
        candidate = values - step * scale
        if float(np.linalg.norm(residual(candidate)[0])) < float(np.linalg.norm(f)):
            values, damping = candidate, max(damping / 2, 1e-9)
        else:
            damping *= 4
    f, com, points = residual(values)
    if float(np.linalg.norm(f)) > 1e-6 or np.abs(values).max() > .4:
        raise ValueError(f'no bounded trim found for {label}: residual {np.abs(f).max():.2e}, '
                         f'max trim {np.abs(values).max():.3f} rad')
    offsets = {}
    for pair in pairs:
        a, b = points[pair[0]], points[pair[1]]
        line = np.array([b[0] - a[0], b[1] - a[1], 0.])
        line /= np.linalg.norm(line)
        offsets['+'.join(sorted((pair[0][:2], pair[1][:2])))] = \
            float((com - a) @ np.array([-line[1], line[0], 0.]))
    return dict(support_group=label, support_feet=feet,
                foot_radius_m={foot: float(radius[foot]) for foot in feet},
                trims_rad={name: float(value * mirror[name]) for name, value in zip(trims, values)},
                com_offset_m=float(f[0]), foot_height_gap_m=float(f[1]) if len(f) > 1 else 0.,
                diagonal_offsets_m=offsets, com_height_m=float(com[2]), base_q_rad=base,
                limitations=['Kinematic solve: no contact compliance, friction or PD sag is modelled.',
                             'A centre of mass on the support line is neutral, not stable: no restoring margin.'])


def swing_terms(kp, kd, inertia, scale, effort, velocity, load=None) -> dict:
    """Return local swing criteria terms from one axis and one gain set [N m/rad, N m s/rad].

    Args:
        kp: Stiffness [N·m/rad].
        kd: Damping [N·m·s/rad].
        inertia: Fixed-root zero-pose downstream inertia [kg·m²].
        scale: Action scale [rad per action].
        effort: Configured effort limit [N·m].
        velocity: Configured velocity limit [rad/s].
        load: Optional external joint moment magnitudes [N·m].

    Returns:
        Local natural frequency [Hz], damping ratio, Kp·scale and Kd·velocity
        percentages of the configured effort limit, and load/static-error terms [rad].
    """
    values = (kp, kd, inertia, scale, effort, velocity)
    if not all(math.isfinite(float(v)) and v > 0 for v in values):
        raise ValueError('invalid gain, inertia or limit')
    if load is not None and (not np.isfinite(load).all() or (np.asarray(load) < 0).any()):
        raise ValueError('invalid load moment')
    return dict(wn_hz=math.sqrt(kp / inertia) / (2 * math.pi), zeta=kd / (2 * math.sqrt(kp * inertia)),
                kp_scale_percent_effort=100 * kp * scale / effort,
                kd_velocity_limit_percent_effort=100 * kd * velocity / effort,
                load_static_error_rad=None if load is None else (np.asarray(load) / kp).tolist())


def swing_review(plan_path: Path, propulsion_path: Path | None = None) -> dict:
    """Cross-check recorded swing A/B gains against recorded loads and response.

    Args:
        plan_path: Recorded run plan JSON holding preflight gains, limits, mapping and case files.
        propulsion_path: Recorded propulsion report JSON; its NPZ supplies contact moments [N·m].

    Returns:
        Per swing axis: recorded gains, limits and inertia, local terms for both gain sets,
        and measured suspended RMS, amplitude ratio and phase for both gains.
    """
    import lizard2_leg_drive_protocol as protocol

    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    pre, mapping = plan['preflight'], plan['mapping']
    names = pre['joint_names']
    cfg, cfg_names, _, model, bodies = inputs()
    assert sorted(names) == sorted(cfg_names), 'plan joint names differ from v7'
    default = pre['config_default_joint_pos']
    default = np.asarray([default[n] for n in names] if isinstance(default, dict) else default, dtype=float)
    assert default.shape == (26,) and not default.any(), 'unsupported default targets'
    stiffness = {**cfg['actuators']['legs']['stiffness'], **cfg['actuators']['spine']['stiffness']}
    damping = {**cfg['actuators']['legs']['damping'], **cfg['actuators']['spine']['damping']}
    gains = {}
    for key, field, row, source in (('v7_kp', 'initial_stiffness', 0, stiffness),
                                    ('candidate_kp', 'proposed_stiffness', 1, stiffness),
                                    ('v7_kd', 'initial_damping', 0, damping),
                                    ('candidate_kd', 'proposed_damping', 1, damping)):
        values = np.asarray(pre[field], dtype=float)
        if values.shape != (2, 26):
            raise ValueError('recorded gain row shape mismatch: ' + field)
        gains[key] = values[row]
        if row == 0 and not np.allclose(values[0], [source[n] for n in names]):
            raise ValueError('recorded v7 gain row differs from config: ' + field)
    if (gains['candidate_kp'] <= 0).any() or (gains['candidate_kd'] <= 0).any():
        raise ValueError('invalid recorded candidate gains')
    inertia = np.diag(project(model, bodies, names, cfg['default_joint_pos']))
    if not np.allclose(np.asarray(pre['nominal_inertia_kg_m2'], dtype=float), inertia, atol=1e-12):
        raise ValueError('recorded nominal inertia differs from current asset')
    effort = np.asarray(pre['effort_limit_nm'], dtype=float)[0]
    velocity = np.asarray(pre['velocity_limit_rad_s'], dtype=float)[0]
    scale = {}
    for entry in mapping:
        if entry['joint'] in SWING:
            scale[entry['joint']] = float(entry['scale'])
    assert set(scale) == set(SWING), 'recorded mapping lacks swing axes'
    moments = None
    if propulsion_path is not None:
        recorded = json.loads(propulsion_path.read_text(encoding='utf-8'))
        with np.load(propulsion_path.parent / recorded['propulsion_diagnostic']['samples'],
                     allow_pickle=False) as samples:
            moments = propulsion_report(samples, recorded['runtime_joint_names'])
    cases = {case.id: case for case in protocol.cases(cfg['action']['joints']['legs'], gravity='on')}
    rows, measured = [], {}
    for entry in plan['cases']:
        if not Path(plan_path.parent / entry['file']).is_file():
            raise ValueError('missing case sample: ' + entry['file'])
        with np.load(plan_path.parent / entry['file'], allow_pickle=False) as sample:
            arrays = {key: sample[key] for key in sample}
        for slot, key in ((0, entry['A']), (1, entry['B'])):
            if key not in cases:
                raise ValueError('unknown recorded case: ' + key)
            measured[key] = protocol.measure(cases[key], names, default, sample_names=names, time=arrays['time_s'],
                                             target_readback=arrays['readback'][:, slot], q=arrays['q'][:, slot])
    for name in SWING:
        index = names.index(name)
        p95 = maximum = None
        if moments is not None:
            leg = moments['legs'][name[:2]]
            p95, maximum = float(leg['p95_abs_nm'][2]), float(leg['max_abs_nm'][2])
        load = None if p95 is None else np.array([p95, maximum])
        row = dict(joint=name, runtime_joint_index=index, scale_rad_per_action=scale[name],
                   effort_limit_nm=float(effort[index]), velocity_limit_rad_s=float(velocity[index]),
                   inertia_kg_m2=float(inertia[index]),
                   p95_contact_moment_nm=p95, max_contact_moment_nm=maximum)
        for label in ('v7', 'candidate'):
            kp, kd = gains[label + '_kp'][index], gains[label + '_kd'][index]
            row[label] = swing_terms(kp, kd, inertia[index], scale[name], effort[index], velocity[index], load)
            row[label].update(kp=float(kp), kd=float(kd))
        row['measured'] = {}
        for frequency in (.5, 1.):
            for gain in ('A', 'B'):
                key = f'{gain}|on|sin|{name}|{frequency:g}'
                if key not in measured:
                    raise ValueError('recorded case missing: ' + key)
                row['measured'][f'{gain}|{frequency:g}'] = {
                    key2: measured[key][key2] for key2 in ('rms', 'amplitude_ratio', 'phase_rad', 'max_error',
                                                          'fit_residual', 'precision_pass')}
            a, b = (row['measured'][f'{g}|{frequency:g}']['rms'] for g in 'AB')
            row['measured'][f'rms_reduction_percent|{frequency:g}'] = 100 * (a - b) / a
        rows.append(row)
    paths = [plan_path, Path(__file__), Path(protocol.__file__), RL / URDF_KEY, Path(robot.__file__),
             Path(check_self_collision.__file__)]
    if propulsion_path is not None:
        paths.append(propulsion_path)
    return dict(plan=str(plan_path), mapping_scope='recorded run plan, not a live backend readback this run',
                input_sha256={str(p.resolve()): sha(p) for p in paths}, rows=rows,
                propulsion_legs=None if moments is None else moments['legs'],
                verdicts=['Static-error and authority terms use recorded contact moments and configured limits; '
                          'no approved tolerance, so loaded adequacy stays unjudged.',
                          'Measured suspended response is a fixed-root self-weight comparison; actual actuator '
                          'torque, saturation, two-foot support and retrained behaviour are not covered.'],
                limitations=['Contact moments are single-point friction-approximated ground-on-foot proxies.',
                             'Authority and damping percentages are separate hypothetical terms at configured limits.',
                             'Recorded gains are plan preflight rows, not per-case runtime readback in this review.'])


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
        poses = {n: fk(model['joints'], n, q) for n in bodies}
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
                          for link, body in bodies.items() if name in chain_up(model['joints'], link))
            jacobian = {foot: np.cross(axis, points[foot] - joint) if name in chain_up(model['joints'], foot)
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
    paths = [RL / USD_KEY, Path(__file__), Path(robot.__file__), Path(check_self_collision.__file__)]
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
    parser.add_argument('--swing_review', type=Path, help='Review a recorded swing A/B plan against recorded loads')
    parser.add_argument('--two_foot_trim', choices=('lf+rr', 'rf+rl', 'both'),
                        help='Solve swing offsets putting the centre of mass under a diagonal support line, '
                             'or under the crossing of both diagonals with "both"')
    args = parser.parse_args()
    if args.foot_forces and not args.two_foot:
        parser.error('--foot_forces requires --two_foot')
    if (args.propulsion_report or args.swing_review or args.two_foot_trim) and (args.two_foot or args.foot_forces):
        parser.error('--propulsion_report, --swing_review and --two_foot_trim cannot be combined with --two_foot')
    forces = json.loads(args.foot_forces.read_text(encoding='utf-8')) if args.foot_forces else None
    if args.two_foot_trim:
        result = two_foot_trim(args.two_foot_trim)
        paths = (RL / URDF_KEY, Path(__file__), Path(check_self_collision.__file__),
                 Path(__import__('lizard2_round_support_geometry').__file__))
        result['input_sha256'] = {str(p): sha(p) for p in paths}
    elif args.swing_review:
        result = swing_review(args.swing_review, args.propulsion_report)
    elif args.propulsion_report:
        recorded = json.loads(args.propulsion_report.read_text(encoding='utf-8'))
        sample_path = args.propulsion_report.parent / recorded['propulsion_diagnostic']['samples']
        with np.load(sample_path, allow_pickle=False) as samples:
            result = propulsion_report(samples, recorded['runtime_joint_names'])
        paths = (args.propulsion_report, sample_path, RL / URDF_KEY, Path(__file__),
                 Path(check_self_collision.__file__))
        result['input_sha256'] = {str(p): sha(p) for p in paths}
    else:
        result = support_report(forces) if args.two_foot else report()
    print(json.dumps(result, indent=2, allow_nan=False))
