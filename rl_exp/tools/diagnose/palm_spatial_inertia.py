# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Read the bound spatial candidate's inertia at neutral and an existing gait pose.

One fixed-base, zero-gain startup; state writes/forward only, no commanded physical steps.
Compare URDF, authored USD, raw tensors and generalized mass matrices [kg, m, kg*m^2].
No PD proposal, loaded tracking, effective speed or support verdict.
"""

import argparse
import copy
import inspect
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET

import numpy as np

import palm_spatial_runtime as wiring

sys.path.insert(0, str(wiring.REPO / 'rl_exp/tools/verify'))
import check_self_collision as csc


def _rotation(quat):
    x, y, z, w = np.asarray(quat, dtype=float)
    assert np.isfinite(quat).all() and abs(x*x + y*y + z*z + w*w - 1) < 1e-5
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def _comparison(actual, expected):
    actual, expected = np.asarray(actual), np.asarray(expected)
    assert actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all()
    scale = max(float(np.abs(actual).max()), float(np.abs(expected).max()), np.finfo(np.float32).tiny)
    budget = 64 * np.finfo(np.float32).eps * scale
    error = float(np.abs(actual - expected).max())
    return {'max_abs_error': error, 'float32_budget': float(budget), 'within_roundoff_budget': bool(error <= budget)}


def _project(joints, poses, names, bodies):
    """Project body tensors about their COM into fixed-base joint coordinates [kg*m^2]."""
    result = np.zeros((len(names), len(names)))
    for link, body in bodies.items():
        pose = poses[link]
        center = pose[:3, :3] @ body['com'] + pose[:3, 3]
        linear, angular = np.zeros((3, len(names))), np.zeros((3, len(names)))
        ancestry = csc.chain_up(joints, link)
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


def _principal_repair(diagonal, quat, expected):
    rotation = _rotation(quat)
    if _comparison(rotation @ diagonal @ rotation.T, expected)['within_roundoff_budget']:
        return None
    inverse = np.r_[-np.asarray(quat[:3]), quat[3]]
    corrected = _rotation(inverse)
    assert _comparison(corrected @ diagonal @ corrected.T, expected)['within_roundoff_budget'], 'unexplained inertia mismatch'
    return inverse


def repair_fresh_stage(stage, urdf):
    """Check fresh converted mass/COM/tensors; repair only explained principal axes."""
    from pxr import Gf, UsdPhysics
    links = {link.get('name'): link for link in ET.parse(urdf).getroot().findall('link')}
    bodies = [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)]
    assert len(bodies) == len(links) == 31 and {p.GetName() for p in bodies} == set(links)
    original = stage.GetRootLayer().ExportToString()
    changes, pending = [], []
    for prim in bodies:
        link = links[prim.GetName()]
        origin = link.find('inertial/origin')
        assert np.all(np.fromstring(origin.get('rpy', '0 0 0'), sep=' ') == 0)
        api = UsdPhysics.MassAPI(prim)
        assert _comparison(float(api.GetMassAttr().Get()), float(link.find('inertial/mass').get('value')))['within_roundoff_budget'], 'mass mismatch'
        assert _comparison(list(api.GetCenterOfMassAttr().Get()), np.fromstring(origin.get('xyz'), sep=' '))['within_roundoff_budget'], 'COM mismatch'
        spec = link.find('inertial/inertia')
        expected = np.array([[float(spec.get(k)) for k in row]
                             for row in (('ixx', 'ixy', 'ixz'), ('ixy', 'iyy', 'iyz'), ('ixz', 'iyz', 'izz'))])
        diagonal = np.diag(list(api.GetDiagonalInertiaAttr().Get()))
        old = api.GetPrincipalAxesAttr().Get()
        quat = [*old.GetImaginary(), old.GetReal()]
        replacement = _principal_repair(diagonal, quat, expected)
        if replacement is not None:
            pending.append((api.GetPrincipalAxesAttr(), old, replacement, prim.GetName()))
    # No stage writes until every tensor has an explanation.
    for attr, old, replacement, name in pending:
        attr.Set(Gf.Quatf(float(replacement[3]), Gf.Vec3f(*map(float, replacement[:3]))))
        changes.append({'link': name, 'before_xyzw': [*old.GetImaginary(), old.GetReal()],
                        'after_xyzw': replacement.tolist()})
    corrected = stage.GetRootLayer().ExportToString()
    for attr, old, _, _ in pending:
        attr.Set(old)
    assert stage.GetRootLayer().ExportToString() == original, 'fields beyond principal axes changed'
    assert stage.GetRootLayer().ImportFromString(corrected)
    return {'links_verified': len(bodies), 'changes': changes, 'only_principal_axes_delta_verified': True,
            'scope': 'fresh authored mass/COM/tensors only; runtime mass matrix remains unverified'}


def _repair_manifest(manifest, out):
    from pxr import Gf, Usd, UsdPhysics
    document = json.loads(manifest.read_text(encoding='utf-8'))
    source = Path(document['target_binding']['target'])
    urdf = Path(document['target_binding']['urdf'])
    stage = Usd.Stage.Open(str(source))  # Keep the stage alive while accessing its layer.
    original = stage.GetRootLayer().ExportToString()
    links = {link.get('name'): link for link in ET.parse(urdf).getroot().findall('link')}
    changes, saved = [], []
    for prim in stage.Traverse():
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        link = links[prim.GetName()]
        origin = link.find('inertial/origin')
        assert np.all(np.fromstring(origin.get('rpy', '0 0 0'), sep=' ') == 0)
        spec = link.find('inertial/inertia')
        expected = np.array([[float(spec.get(k)) for k in row]
                             for row in (('ixx', 'ixy', 'ixz'), ('ixy', 'iyy', 'iyz'), ('ixz', 'iyz', 'izz'))])
        api = UsdPhysics.MassAPI(prim)
        diagonal = np.diag(list(api.GetDiagonalInertiaAttr().Get()))
        old = api.GetPrincipalAxesAttr().Get()
        quat = [*old.GetImaginary(), old.GetReal()]
        replacement = _principal_repair(diagonal, quat, expected)
        if replacement is not None:
            attr = api.GetPrincipalAxesAttr()
            saved.append((attr, old))
            attr.Set(Gf.Quatf(float(replacement[3]), Gf.Vec3f(*map(float, replacement[:3]))))
            changes.append({'link': prim.GetName(), 'attribute': str(attr.GetPath()),
                            'before_xyzw': quat, 'after_xyzw': replacement.tolist()})
    assert len(changes) == 5, 'unexpected repair scope'
    corrected_text = stage.GetRootLayer().ExportToString()
    for attr, old in saved:
        attr.Set(old)
    assert stage.GetRootLayer().ExportToString() == original, 'fields beyond principal axes changed'
    (out / 'palm_spatial.usda').write_text(corrected_text, encoding='utf-8')
    shutil.copyfile(urdf, out / 'palm_spatial.urdf')
    shutil.copytree(source.parent / 'meshes', out / 'meshes')
    updated = copy.deepcopy(document)
    new_manifest = out / 'registered_manifest.json'
    updated['target_binding'].update(target=str(out / 'palm_spatial.usda'), urdf=str(out / 'palm_spatial.urdf'),
                                      source=str(new_manifest))
    for key in ('target', 'urdf'):
        updated[key] = updated['target_binding'][key]
        updated['sha256'][key] = wiring.binding.sha256_file(Path(updated[key]))
    updated['inertia_repair'] = {'source_manifest': str(manifest), 'source_manifest_sha256': wiring.binding.sha256_file(manifest),
                                 'source_usd_sha256': wiring.binding.sha256_file(source), 'changes': changes,
                                 'only_principal_axes_delta_verified': True}
    wiring.write_json(new_manifest, updated)
    return new_manifest, updated['inertia_repair']


def _snapshot(robot, live, target, label, source_q):
    from pxr import UsdPhysics
    model = csc.load_urdf(Path(target['urdf']))
    tree = ET.parse(target['urdf']).getroot()
    for origin in tree.findall('.//origin'):
        assert np.all(np.fromstring(origin.get('rpy', '0 0 0'), sep=' ') == 0), 'unsupported nonzero origin rpy'
    names, body_names = list(robot.joint_names), list(robot.body_names)
    assert set(names) == set(source_q) and set(body_names) == set(model['links'])
    q = robot.data.joint_pos.torch[0].cpu().numpy()
    assert np.max(abs(q - np.array([source_q[n] for n in names]))) < 1e-5, 'state readback mismatch'
    actors = robot.data.body_link_pose_w.torch[0].cpu().numpy()
    masses = robot.data.body_mass.torch[0].cpu().numpy()
    com = robot.data.body_com_pos_b.torch[0].cpu().numpy()
    axes_quat = robot.data.body_com_quat_b.torch[0].cpu().numpy()
    tensors = robot.data.body_inertia.torch[0].cpu().numpy().reshape(-1, 3, 3)
    matrix = robot.data.mass_matrix.torch[0].cpu().numpy()
    assert matrix.shape == (len(names), len(names)) and np.isfinite(matrix).all(), 'fixed-base mass matrix shape'
    assert robot.is_fixed_base
    for field in ('joint_stiffness', 'joint_damping', 'joint_armature'):
        assert np.all(getattr(robot.data, field).torch.cpu().numpy() == 0), 'nonzero ' + field
    poses = {}
    for name, pose in zip(body_names, actors):
        transform = np.eye(4)
        transform[:3, :3], transform[:3, 3] = _rotation(pose[3:]), pose[:3]
        poses[name] = transform
    root = poses['base_link']
    fk_error = max(float(np.abs(poses[name] - root @ csc.fk(model['joints'], name, dict(zip(names, q)))).max())
                   for name in body_names)
    assert fk_error < 1e-5, 'actor/FK frame mismatch'
    authored = {p.GetName(): p for p in live.sim.stage.Traverse()
                if p.HasAPI(UsdPhysics.RigidBodyAPI) and p.GetName() in body_names}
    assert set(authored) == set(body_names)
    urdf, usd, raw, principal, readings = {}, {}, {}, {}, {}
    for i, link in enumerate(tree.findall('link')):
        name = link.get('name')
        k = body_names.index(name)
        inertia = link.find('inertial/inertia')
        tensor = np.array([[float(inertia.get(key)) for key in row]
                           for row in (('ixx', 'ixy', 'ixz'), ('ixy', 'iyy', 'iyz'), ('ixz', 'iyz', 'izz'))])
        urdf[name] = {'mass': float(link.find('inertial/mass').get('value')),
                      'com': np.fromstring(link.find('inertial/origin').get('xyz'), sep=' '), 'inertia': tensor}
        mass_api = UsdPhysics.MassAPI(authored[name])
        quat = mass_api.GetPrincipalAxesAttr().Get()
        rotation = _rotation([*quat.GetImaginary(), quat.GetReal()])
        diagonal = np.diag(list(mass_api.GetDiagonalInertiaAttr().Get()))
        usd[name] = {'mass': float(mass_api.GetMassAttr().Get()),
                     'com': np.array(mass_api.GetCenterOfMassAttr().Get()),
                     'inertia': rotation @ diagonal @ rotation.T}
        raw[name] = {'mass': float(masses[k]), 'com': com[k], 'inertia': tensors[k]}
        rp = _rotation(axes_quat[k])
        principal[name] = {**raw[name], 'inertia': rp @ tensors[k] @ rp.T}
        readings[name] = {'urdf': {n: v.tolist() if isinstance(v, np.ndarray) else v for n, v in urdf[name].items()},
                          'usd_mass_kg': usd[name]['mass'], 'usd_com_m': usd[name]['com'].tolist(),
                          'usd_diagonal_inertia': diagonal.tolist(), 'usd_principal_axes_xyzw': [*quat.GetImaginary(), quat.GetReal()],
                          'raw_inertia': tensors[k].tolist(), 'live_mass_kg': float(masses[k]),
                          'live_com_m': com[k].tolist(), 'live_principal_axes_xyzw': axes_quat[k].tolist(),
                          'mass': _comparison(masses[k], urdf[name]['mass']),
                          'com': _comparison(com[k], urdf[name]['com']),
                          'usd_tensor_vs_urdf': _comparison(usd[name]['inertia'], tensor),
                          'raw_tensor_vs_urdf': _comparison(tensors[k], tensor),
                          'principal_rotated_raw_vs_urdf': _comparison(principal[name]['inertia'], tensor)}
    projections = {kind: _project(model['joints'], poses, names, entries)
                   for kind, entries in (('urdf', urdf), ('usd', usd), ('raw_actor', raw), ('raw_principal', principal))}
    matrix_checks = {kind: _comparison(matrix, value) for kind, value in projections.items()}
    return {'label': label, 'joint_names': names, 'body_names': body_names, 'q_rad': q.tolist(),
            'actor_poses_xyzw': actors.tolist(), 'actor_fk_max_error_m_or_rotation': fk_error,
            'links': readings, 'mass_matrix': matrix.tolist(), 'projected_mass_matrices': {k: v.tolist() for k, v in projections.items()},
            'mass_matrix_checks': matrix_checks, 'runtime_fixed_base': True,
            'limits': 'Locked-base generalized inertia, not contact/free-base effective inertia or loaded tracking. '
                      'Raw tensor frame hypotheses are measurements, not assumed conventions.'}


def _validate_inputs(args):
    """Validate approved fresh inputs before JSON parsing, output writes or Kit startup."""
    reset_hash = getattr(args, 'approved_reset_sha256', None)
    pose_hash = getattr(args, 'approved_pose_sha256', None)
    fresh = reset_hash is not None or pose_hash is not None
    if fresh:
        wiring.require(reset_hash and pose_hash, 'fresh reset and pose approvals both required')
        wiring.require(not args.repair_inertia, 'fresh reset cannot use legacy inertia repair')
        for path, digest, label in ((args.reset_report, reset_hash, 'reset'), (args.pose_report, pose_hash, 'pose')):
            wiring.require(wiring.binding.sha256_file(path) == digest, label + ' approval mismatch')
    source = json.loads(args.reset_report.read_text(encoding='utf-8'))
    assert source['completed'] and source['status'] == 'reset_and_neutral_first_step_verified'
    manifest = Path(source['replay_manifest'])
    assert wiring.binding.sha256_file(manifest) == source['replay_manifest_sha256'], 'replay manifest hash mismatch'
    pose_report = json.loads(args.pose_report.read_text(encoding='utf-8'))
    assert pose_report['legs']['combined']['completed_combined_loop']
    # The approved old pose remains a state sample, not a new asset or gait approval.
    assert pose_report['identity']['candidate_files_sha256']['palm_spatial.urdf'] == wiring.URDF_HASH, 'pose source URDF mismatch'
    pose = next(r for r in pose_report['legs']['combined']['rows'] if r['s'] == .25)
    assert not pose['failures']
    out = args.out.resolve()
    assert wiring.REPO / 'rl_exp/out' in out.parents and not out.exists(), 'fresh isolated output required'
    wiring.check_build(wiring.BUILD)
    if fresh:
        document = json.loads(manifest.read_text(encoding='utf-8'))
        approved_urdf = source['input']['urdf_sha256']
        exported = wiring.check_export(Path(document['input']['export_report']),
                                       document['input']['export_report_sha256'], approved_urdf)
        wiring.require(document['sha256']['urdf'] == document['input']['urdf_sha256'] == approved_urdf,
                       'fresh URDF lineage mismatch')
        wiring.require(document['input']['candidate_files_sha256'] == exported['files_sha256'],
                       'fresh export file binding mismatch')
        wiring.require(document['connection_filter']['source_usd_sha256'] == source['input']['usd_sha256'],
                       'fresh USD reset binding mismatch')
        root = Path(document['target_binding']['urdf']).resolve().parent
        for name, digest in exported['files_sha256'].items():
            if name == 'lizard2_palm_spatial.urdf':
                path = Path(document['target_binding']['urdf'])
            else:
                path = (root / name).resolve()
                wiring.require(path.is_relative_to(root), 'fresh mesh path escape')
            wiring.require(wiring.binding.sha256_file(path) == digest, 'fresh replay file hash mismatch: ' + name)
        # The real approved replay has no measured order. Do not substitute measured_manifest
        # or drop the order check to accommodate it: that is a distinct report-bound input.
        wiring.check_registered_manifest(manifest, measured_order=False)
        q = pose['q_rad']
        wiring.require(set(q) == set(document['target_binding']['joint_names'])
                       and np.isfinite(list(q.values())).all() and any(v != 0. for v in q.values()),
                       'fresh c=0.25 state mismatch')
    return source, manifest, pose, out, fresh


def _self_check(break_projection=False, args=None):
    from unittest.mock import patch
    if break_projection:
        scope = {}
        exec(inspect.getsource(_project).replace("body['mass'] * linear.T @ linear", '0 * linear.T @ linear'), globals(), scope)
        with patch.dict(globals(), {'_project': scope['_project']}):
            _self_check()
        return
    assert np.allclose(_rotation([0, 0, np.sqrt(.5), np.sqrt(.5)]) @ [1, 0, 0], [0, 1, 0])
    joints = {'hinge': {'parent': 'base', 'child': 'tip', 'axis': np.array([0., 0., 1.])}}
    bodies = {'tip': {'mass': 2., 'com': np.array([.5, 0., 0.]), 'inertia': np.diag([.1, .2, .3])}}
    assert np.allclose(_project(joints, {'tip': np.eye(4)}, ['hinge'], bodies), [[.8]])
    assert not _comparison([1.], [2.])['within_roundoff_budget']
    diagonal = np.diag([.13, .17, .24])
    assert _principal_repair(diagonal, [0., 0., 0., 1.], diagonal) is None
    fixed = _principal_repair(diagonal, [.5, .5, .5, .5], np.diag([.17, .24, .13]))
    assert np.array_equal(fixed, [-.5, -.5, -.5, .5])
    for expected in (diagonal + np.eye(3), np.full((3, 3), np.nan)):
        try:
            _principal_repair(diagonal, [.5, .5, .5, .5], expected)
        except AssertionError:
            pass
        else:
            raise AssertionError('unexplained/nonfinite inertia accepted')
    if args is not None and (args.approved_reset_sha256 is not None or args.approved_pose_sha256 is not None):
        _, manifest, _, _, fresh = _validate_inputs(args)
        assert fresh
        def rejected(label, candidate):
            try:
                _validate_inputs(candidate)
            except (AssertionError, ValueError):
                print('INERTIA_INPUT_REJECTED', label)
            else:
                raise AssertionError('invalid input accepted: ' + label)
        for label, changes in (
                ('wrong_reset_approval', {'approved_reset_sha256': '0' * 64}),
                ('wrong_pose_approval', {'approved_pose_sha256': '0' * 64}),
                ('partial_approval', {'approved_pose_sha256': None}),
                ('fresh_legacy_repair', {'repair_inertia': True}),
                ('output_escape', {'out': wiring.REPO / 'not_an_inertia_output'}),
                ('output_exists', {'out': args.reset_report.parent})):
            candidate = copy.copy(args)
            vars(candidate).update(changes)
            rejected(label, candidate)
        read_text = Path.read_text
        # Mutate only in-memory reads; approved artifacts remain untouched. Real validators run.
        for label, path, mutate in (
                ('wrong_pose_source', args.pose_report,
                 lambda d: d['identity']['candidate_files_sha256'].update({'palm_spatial.urdf': '0' * 64})),
                ('wrong_manifest', args.reset_report,
                 lambda d: d.update(replay_manifest=d['measured_manifest'])),
                ('wrong_fresh_urdf', manifest,
                 lambda d: d['sha256'].update(urdf='0' * 64)),
                ('inherited_runtime_order', manifest,
                 lambda d: d.update(runtime_joint_order=d['joint_order']))):
            document = json.loads(read_text(path, encoding='utf-8'))
            mutate(document)
            text = json.dumps(document)
            def altered(p, *a, **kw):
                return text if p.resolve() == path.resolve() else read_text(p, *a, **kw)
            with patch.object(Path, 'read_text', altered):
                rejected(label, args)
        print('SPATIAL_INERTIA_FRESH_INPUT_CHECK_OK')
    print('SPATIAL_INERTIA_SELF_CHECK_OK')


def _run(args):
    source, manifest, pose, out, fresh = _validate_inputs(args)
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, out / 'source.py')
    result = {'completed': False, 'stage': 'app_startup', 'input': {
        str(p): wiring.binding.sha256_file(p) for p in (args.reset_report, args.pose_report, manifest)},
        'code_sha256': wiring.binding.sha256_file(Path(__file__)), 'snapshots': [],
        'scope': 'one startup; fixed-base zero gains; neutral and existing c=0.25 state; no commanded physics steps'}
    if fresh:
        result['approvals'] = {'reset_report_sha256': args.approved_reset_sha256,
                               'pose_report_sha256': args.approved_pose_sha256}
    app, env = None, None
    try:
        from isaaclab.app import AppLauncher
        app = AppLauncher(args).app
        import gymnasium as gym
        import torch
        import rl_exp.tasks
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg, joint_reset_errors
        if args.repair_inertia:
            manifest, result['inertia_repair'] = _repair_manifest(manifest, out)
        result['replay_manifest'] = str(manifest)
        result['replay_manifest_sha256'] = wiring.binding.sha256_file(manifest)
        if fresh:
            wiring.check_registered_manifest(manifest, measured_order=False)
        else:
            wiring.check_registered_manifest(manifest)
        cfg = copy.deepcopy(resolve_task_cfg(wiring.REGISTERED_TASK))
        target = wiring.obs_protocol.load_diagnostic_target(manifest, cfg, wiring.REGISTERED_TASK)
        cfg.sim.device = args.device
        result['target'] = target
        result['stage'] = 'gym_make'
        env = gym.make(wiring.REGISTERED_TASK, cfg=cfg)
        wrapper = RslRlVecEnvWrapper(env, clip_actions=None)
        live, robot = env.unwrapped, env.unwrapped.scene['robot']
        assert not joint_reset_errors(robot), 'normal reset mismatch'
        result['framework_sources'] = {str(Path(inspect.getfile(obj))): wiring.binding.sha256_file(Path(inspect.getfile(obj)))
                                       for obj in (type(robot), type(robot.data), type(live))}
        for label, state in (('neutral', {n: 0. for n in robot.joint_names}), ('existing_c_0.25', pose['q_rad'])):
            result['stage'] = label
            if label != 'neutral':
                q = torch.tensor([[state[n] for n in robot.joint_names]], device=args.device)
                robot.write_joint_state_to_sim_index(position=q, velocity=torch.zeros_like(q))
                live.scene.write_data_to_sim()
                live.sim.forward()
                robot.update(0.)
            snapshot = _snapshot(robot, live, target, label, state)
            result['snapshots'].append(snapshot)
            wiring.write_json(out / (label + '.json'), snapshot)
            print('INERTIA_SNAPSHOT', label, json.dumps(snapshot['mass_matrix_checks']), flush=True)
        verified = all(s['mass_matrix_checks']['urdf']['within_roundoff_budget']
                       and all(v['mass']['within_roundoff_budget'] and v['com']['within_roundoff_budget']
                               and v['usd_tensor_vs_urdf']['within_roundoff_budget'] for v in s['links'].values())
                       for s in result['snapshots'])
        result.update(completed=True, stage='completed', status='authored_inertia_and_mass_matrix_verified' if verified else 'captured_inertia_mismatch')
        wiring.write_json(out / 'report.json', result)
        print('INERTIA_COMPLETED', result['status'], flush=True)
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
        wiring.write_json(out / 'failure.json', result)
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    finally:
        if env is not None:
            env.close()
        if app is not None:
            app.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset_report', type=Path)
    parser.add_argument('--pose_report', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--break_projection', action='store_true')
    parser.add_argument('--repair_inertia', action='store_true')
    parser.add_argument('--approved_reset_sha256', help='explicit fresh reset report approval; requires pose approval')
    parser.add_argument('--approved_pose_sha256', help='explicit existing c=0.25 pose report approval')
    if '--self_check' in sys.argv:
        args = parser.parse_args()
        if (args.approved_reset_sha256 is not None or args.approved_pose_sha256 is not None) and not all((args.reset_report, args.pose_report, args.out)):
            parser.error('fresh input self_check requires reset_report, pose_report and out')
        _self_check(args.break_projection, args)
    else:
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(parser)
        args = parser.parse_args()
        if not all((args.reset_report, args.pose_report, args.out)) or args.break_projection:
            parser.error('reset_report, pose_report and out are required')
        _run(args)
