# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Read-only round-feet USD audit [kg, m, kg*m^2]; explicit --repair saves a new sibling, no physics."""
import argparse
import ast
import json
from pathlib import Path
import sys
import traceback
import xml.etree.ElementTree as ET

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdUtils

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tools.runrecord.binding import sha256_file as sha256

DEFAULT = ROOT / 'rl_exp/out/lizard2_round_feet/export03'
FEET = ('lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle')
REPAIR_LINKS = {'lf_elbow', 'rf_elbow', 'rl_knee', 'rr_knee', 'tail1_pitch'}


def repair_clone(stage, urdf):
    """Reuse proven conjugation repair offline; never edit source layer."""
    helper = ROOT / 'rl_exp/tools/diagnose/palm_spatial_inertia.py'
    names = {'_rotation', '_comparison', '_principal_repair', 'repair_fresh_stage'}
    nodes = [n for n in ast.parse(helper.read_text(encoding='utf-8')).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names, 'repair helper functions missing'
    namespace = {'np': np, 'ET': ET}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(helper), 'exec'), namespace)
    layer = Sdf.Layer.CreateAnonymous('principal_axes_repair.usda')
    assert layer.ImportFromString(stage.GetRootLayer().ExportToString())
    clone = Usd.Stage.Open(layer)
    result = namespace['repair_fresh_stage'](clone, urdf)
    assert {c['link'] for c in result['changes']} == REPAIR_LINKS, 'unexpected repair scope'
    assert len(result['changes']) == 5, 'unexpected repair count'
    return clone, result


def comparison(actual, expected):
    """Same scale-relative 64-float32-epsilon budget as palm_spatial_inertia._comparison."""
    actual, expected = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    if actual.shape != expected.shape or not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError('nonfinite or incompatible comparison')
    scale = max(float(np.abs(actual).max()), float(np.abs(expected).max()), np.finfo(np.float32).tiny)
    budget = 64 * np.finfo(np.float32).eps * scale
    error = float(np.abs(actual - expected).max())
    return {'actual': actual.tolist(), 'expected': expected.tolist(), 'max_abs_error': error,
            'float32_budget': float(budget), 'pass': bool(error <= budget)}


def rotation(quat):
    """pxr quaternion active rotation; columns are transformed basis vectors."""
    if abs(quat.GetLength() - 1) > 1e-5:
        raise ValueError('nonunit quaternion')
    q = Gf.Rotation(Gf.Quatd(quat))
    return np.column_stack([q.TransformDir(Gf.Vec3d(*v)) for v in np.eye(3)])


def xyz(element, key='xyz'):
    return np.fromstring(element.get(key, '0 0 0') if element is not None else '0 0 0', sep=' ')


def origin(element):
    r, p, y = xyz(element, 'rpy')
    rx = np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])
    ry = np.array([[np.cos(p), 0, np.sin(p)], [0, 1, 0], [-np.sin(p), 0, np.cos(p)]])
    rz = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1]])
    return xyz(element), rz @ ry @ rx


def audit(stage, tree):
    rows, failures = {}, []

    def check(name, operation):
        try:
            result = operation()
            if isinstance(result, (bool, np.bool_)):
                result = {'pass': bool(result)}
            rows[name] = result
            if not result['pass']:
                failures.append(name)
        except Exception as exc:
            rows[name] = {'pass': False, 'error': f'{type(exc).__name__}: {exc}'}
            failures.append(name)

    prims = list(stage.Traverse())
    bodies = [p for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI)]
    joints = [p for p in prims if p.IsA(UsdPhysics.Joint)]
    links = {e.get('name'): e for e in tree.findall('link')}
    specs = {e.get('name'): e for e in tree.findall('joint')}
    body_map = {p.GetName(): p for p in bodies}
    joint_map = {p.GetName(): p for p in joints}
    check('body_names', lambda: len(bodies) == len(links) == 31 and set(body_map) == set(links))
    check('joint_names', lambda: len(joints) == len(specs) == 30 and set(joint_map) == set(specs))
    for kind, schema, count in [('revolute', UsdPhysics.RevoluteJoint, 26), ('fixed', UsdPhysics.FixedJoint, 4)]:
        expected = {n for n, e in specs.items() if e.get('type') == kind}
        actual = {p.GetName() for p in joints if p.IsA(schema)}
        check(kind + '_names', lambda a=actual, e=expected, c=count: len(a) == c and a == e)
    check('units', lambda: UsdGeom.GetStageMetersPerUnit(stage) == 1 and
          UsdPhysics.GetStageKilogramsPerUnit(stage) == 1 and UsdGeom.GetStageUpAxis(stage) == 'Z')
    for name, link in links.items():
        def body_readback(name=name, link=link):
            prim = body_map[name]
            api = UsdPhysics.MassAPI(prim)
            com, inertial_rotation = origin(link.find('inertial/origin'))
            spec = link.find('inertial/inertia')
            tensor = np.array([[float(spec.get(k)) for k in row] for row in
                               [('ixx', 'ixy', 'ixz'), ('ixy', 'iyy', 'iyz'), ('ixz', 'iyz', 'izz')]])
            expected = inertial_rotation @ tensor @ inertial_rotation.T
            quat = api.GetPrincipalAxesAttr().Get()
            rot = rotation(quat)
            diagonal = np.array(api.GetDiagonalInertiaAttr().Get())
            tests = {'mass': comparison(api.GetMassAttr().Get(), float(link.find('inertial/mass').get('value'))),
                     'com': comparison(api.GetCenterOfMassAttr().Get(), com),
                     'full_inertia': comparison(rot @ np.diag(diagonal) @ rot.T, expected)}
            return {'path': str(prim.GetPath()), 'principal_axes_xyzw': [*quat.GetImaginary(), quat.GetReal()],
                    'diagonal_inertia': diagonal.tolist(), 'checks': tests,
                    'pass': all(t['pass'] for t in tests.values()) and bool(np.all(diagonal > 0))}
        check('body/' + name, body_readback)
    for name, spec in specs.items():
        def joint_readback(name=name, spec=spec):
            prim = joint_map[name]
            api = UsdPhysics.Joint(prim)
            targets = [list(api.GetBody0Rel().GetTargets()), list(api.GetBody1Rel().GetTargets())]
            expected_targets = [[body_map[spec.find(k).get('link')].GetPath()] for k in ('parent', 'child')]
            p0, p1 = np.array(api.GetLocalPos0Attr().Get()), np.array(api.GetLocalPos1Attr().Get())
            r0, r1 = rotation(api.GetLocalRot0Attr().Get()), rotation(api.GetLocalRot1Attr().Get())
            # Joint frames coincide at q=0: T_parent_child = T_parent_joint * inverse(T_child_joint).
            relative = r0 @ r1.T
            pos, rot = origin(spec.find('origin'))
            tests = {'body_links': {'actual': [[str(p) for p in t] for t in targets],
                                    'expected': [[str(p) for p in t] for t in expected_targets],
                                    'pass': targets == expected_targets},
                     'local_frame_translation': comparison(p0 - relative @ p1, pos),
                     'local_frame_rotation': comparison(relative, rot),
                     'enabled': {'pass': bool(api.GetJointEnabledAttr().Get())}}
            if spec.get('type') == 'revolute':
                rev = UsdPhysics.RevoluteJoint(prim)
                axis = np.eye(3)['XYZ'.index(rev.GetAxisAttr().Get())]
                tests['axis_child'] = comparison(r1 @ axis, xyz(spec.find('axis')))
                limit = spec.find('limit')
                tests['limits_degrees'] = comparison([rev.GetLowerLimitAttr().Get(), rev.GetUpperLimitAttr().Get()],
                                                     np.degrees([float(limit.get('lower')), float(limit.get('upper'))]))
            return {'path': str(prim.GetPath()), 'local_pos0': p0.tolist(), 'local_pos1': p1.tolist(),
                    'local_rot0': r0.tolist(), 'local_rot1': r1.tolist(), 'checks': tests,
                    'pass': all(t['pass'] for t in tests.values())}
        check('joint/' + name, joint_readback)
    cache = UsdGeom.XformCache()
    for name in FEET:
        def foot_readback(name=name):
            body = body_map[name]
            descendants = list(Usd.PrimRange(body))[1:]
            colliders = [p for p in descendants if p.HasAPI(UsdPhysics.CollisionAPI)]
            visuals = [p for p in descendants if p.IsA(UsdGeom.Gprim) and not p.HasAPI(UsdPhysics.CollisionAPI)]
            readings = []
            for prim in colliders + visuals:
                owner = prim.GetParent()
                while owner and not owner.HasAPI(UsdPhysics.RigidBodyAPI):
                    owner = owner.GetParent()
                matrix, reset = cache.ComputeRelativeTransform(prim, body)
                radius = UsdGeom.Sphere(prim).GetRadiusAttr().Get() if prim.IsA(UsdGeom.Sphere) else None
                readings.append({'path': str(prim.GetPath()), 'owner': str(owner.GetPath()), 'radius_m': radius,
                                 'local_transform': np.array(matrix).tolist(),
                                 'pass': owner == body and radius is not None and abs(radius - .08) < 1e-8
                                 and not reset and comparison(np.array(matrix), np.eye(4))['pass']
                                 and (not prim.HasAPI(UsdPhysics.CollisionAPI) or
                                      bool(UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()))})
            return {'colliders': len(colliders), 'visuals': len(visuals), 'geometry': readings,
                    'pass': len(colliders) == len(visuals) == 1 and all(r['pass'] for r in readings)
                    and not any(p.IsA(UsdGeom.Mesh) for p in descendants)}
        check('foot/' + name, foot_readback)
    return {'pass': not failures, 'failures': failures, 'checks': rows,
            'authored_body_world_positions_m': {p.GetName(): list(cache.GetLocalToWorldTransform(p).ExtractTranslation())
                                                for p in bodies}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export_dir', type=Path, default=DEFAULT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--usd', type=Path, help='USD to audit, within export_dir (default: original)')
    parser.add_argument('--repair', type=Path, help='Opt in: save repaired USD to a new sibling of --usd')
    args = parser.parse_args()
    directory = args.export_dir.resolve()
    usd = (args.usd or directory / 'lizard2_round_feet/lizard2_round_feet.usda').resolve()
    if not usd.is_relative_to(directory) or not usd.is_file():
        parser.error('usd must be an existing file within export directory')
    target = args.repair.resolve() if args.repair else None
    repair_record = directory / ((target or usd).stem + '.repair.json')
    if target and (target.parent != usd.parent or target.exists() or target.suffix != '.usda'
                   or repair_record.exists()):
        parser.error('repair requires a new .usda sibling and a new repair record')
    output = args.output or directory / 'usd_audit.json'
    if (not output.parent.is_dir() or output.exists() or output.resolve().parent != directory
            or output.suffix != '.json' or output.resolve() == repair_record):
        parser.error('output must be a new JSON in existing export directory, distinct from repair record')
    report = {'pass': False, 'scope': 'authored USD stage only; no runtime, contacts, material or loaded pose/FK verdict',
              'inertia_convention': 'R diag(I) R.T; pxr active quaternion, imaginary xyz / real w; no repairs',
              'bindings': {}, 'binding_failures': []}

    def bind(path, expected=None):
        path = Path(path).resolve()
        try:
            digest = sha256(path)
            if digest is None:
                raise OSError(f'cannot hash file: {path}')
            report['bindings'][str(path)] = {'sha256': digest, 'expected': expected,
                                             'pass': expected is None or digest == expected}
            if expected is not None and digest != expected:
                report['binding_failures'].append(str(path))
        except Exception as exc:
            report['bindings'][str(path)] = {'pass': False, 'error': str(exc)}
            report['binding_failures'].append(str(path))

    try:
        manifest = directory / 'candidate.json'
        bind(manifest)
        doc = json.loads(manifest.read_text(encoding='utf-8'))
        for path, expected in doc['source_bindings_sha256'].items():
            bind(path, expected)
        for path, expected in doc['candidate_files_sha256'].items():
            resolved = (directory / path).resolve()
            if not resolved.is_relative_to(directory):
                raise ValueError('candidate path escapes export directory')
            bind(resolved, expected)
        urdf = directory / 'lizard2_round_feet.urdf'
        bind(urdf, doc['urdf_sha256'])
        for path in [Path(__file__), ROOT / 'rl_exp/tools/diagnose/lizard2_two_axis_convert.py',
                     ROOT / 'rl_exp/tools/pipeline/flatten_usd.py', ROOT / 'rl_exp/tools/diagnose/palm_spatial_inertia.py',
                     directory / 'config.yaml', directory / 'conversion.log', directory / '.asset_hash']:
            bind(path)
        history = directory / 'usd_audit.json'
        if history.exists():
            bind(history)  # Historical evidence: bind when present, never rewrite.
        bind(usd)
        if not target and repair_record.exists():
            bind(repair_record)
            repair_doc = json.loads(repair_record.read_text(encoding='utf-8'))
            assert Path(repair_doc['target']).resolve() == usd
            bind(usd, repair_doc['target_sha256'])
            bind(repair_doc['source'], repair_doc['source_sha256'])
            for path, entry in repair_doc['bindings'].items():
                bind(path, entry['sha256'])
            report['repair_record'] = str(repair_record)
        layers, assets, unresolved = UsdUtils.ComputeAllDependencies(str(usd))
        report['dependencies'] = {'layers': [l.identifier for l in layers], 'assets': list(assets),
                                  'unresolved': list(unresolved)}
        for path in [l.realPath for l in layers if not l.anonymous] + list(assets):
            bind(path)
        tree = ET.parse(urdf).getroot()
        stage = Usd.Stage.Open(str(usd))
        report['baseline'] = audit(stage, tree)
        if target:
            assert not report['binding_failures'] and not unresolved, 'unbound or unresolved inputs'
            assert set(report['baseline']['failures']) == {'body/' + n for n in REPAIR_LINKS}, 'unexpected original failures'
            repaired, repair = repair_clone(stage, urdf)
            repaired_audit = audit(repaired, tree)
            assert repaired_audit['pass'], 'repaired clone failed full audit'
            assert all(sha256(p) == r['sha256'] for p, r in report['bindings'].items()), 'inputs changed'
            # Exclusive create: never overwrite source or an existing repair.
            with target.open('x', encoding='utf-8', newline='') as stream:
                stream.write(repaired.GetRootLayer().ExportToString())
            saved = Usd.Stage.Open(str(target))
            assert saved.GetRootLayer().ExportToString() == repaired.GetRootLayer().ExportToString(), 'saved layer fields changed'
            assert audit(saved, tree) == repaired_audit, 'saved repair differs from validated clone'
            repair.update(source=str(usd), source_sha256=sha256(usd), target=str(target),
                          target_sha256=sha256(target), bindings=dict(report['bindings']),
                          original_failures=report['baseline']['failures'])
            with repair_record.open('x', encoding='utf-8') as stream:
                json.dump(repair, stream, indent=2, allow_nan=False)
                stream.write('\n')
            report['original_baseline'] = report['baseline']
            report['baseline'] = repaired_audit
            report['repair_record'] = str(repair_record)
            report['inertia_convention'] = 'R diag(I) R.T; proven principal-axes conjugation only; see repair record'
            bind(target)
            bind(repair_record)
            stage = saved
        report['negative_tests'] = {}
        for label in ('foot_mass', 'fixed_body_link', 'full_tensor'):
            session = Sdf.Layer.CreateAnonymous('audit_negative')
            test_stage = Usd.Stage.Open(stage.GetRootLayer(), session)
            test_stage.SetEditTarget(session)
            if label == 'foot_mass':
                prim = test_stage.GetPrimAtPath('/lizard_robot/Geometry/lf_wrist')
                UsdPhysics.MassAPI(prim).GetMassAttr().Set(2.0)
                expected_failure = 'body/lf_wrist'
            elif label == 'fixed_body_link':
                prim = test_stage.GetPrimAtPath('/lizard_robot/Physics/lf_wrist_fixed')
                UsdPhysics.Joint(prim).GetBody1Rel().SetTargets(['/lizard_robot/Geometry/base_link'])
                expected_failure = 'joint/lf_wrist_fixed'
            else:
                prim = test_stage.GetPrimAtPath('/lizard_robot/Geometry/lf_wrist')
                attr = UsdPhysics.MassAPI(prim).GetDiagonalInertiaAttr()
                diagonal = attr.Get()
                attr.Set(Gf.Vec3f(diagonal[0] * 2, diagonal[1], diagonal[2]))
                expected_failure = 'body/lf_wrist'
            broken = audit(test_stage, tree)
            session.Clear()
            restored = audit(test_stage, tree)
            report['negative_tests'][label] = {'expected_failure': expected_failure,
                'injected_failures': broken['failures'], 'injected_readback': broken['checks'][expected_failure],
                'restored_pass': restored['pass'], 'restored_failures': restored['failures'],
                'pass': expected_failure in broken['failures'] and
                        not broken['checks'][expected_failure]['pass'] and restored == report['baseline']}
        report['disk_bindings_unchanged'] = all(sha256(p) == r['sha256'] for p, r in report['bindings'].items()
                                                if 'sha256' in r)
        report['pass'] = (report['baseline']['pass'] and not report['binding_failures'] and not unresolved
                          and report['disk_bindings_unchanged']
                          and all(t['pass'] for t in report['negative_tests'].values()))
    except Exception:
        report['error'] = traceback.format_exc()
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': str(output), 'sha256': sha256(output), 'pass': report['pass'],
                      'failures': report.get('baseline', {}).get('failures'),
                      'binding_failures': report['binding_failures'], 'error': report.get('error')}))
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
