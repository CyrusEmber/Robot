# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Standalone body precheck regression; no pytest or simulator.

Configured Python -B rl_exp/tools/verify/test_body_precheck.py
Add --break_zero_aabb to inject the historical zero-clearance early return
INTO run()'s pair consumer. The SAME overlap assertion must then fail (exit 1).
Add --break_fix {binding,error_rows,roles,params,coverage,config_digest,mesh,
touching,contact_policy,role_semantics} to restore
one historical blocker in memory; identical regression assertions must fail.
--plan_gap {rotation,contact,roles} runs one focused counterexample group.
Assets, configs, CLI reports and compile outputs live only in system temp.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'rl_exp/tools/diagnose'))
import body_precheck as pre  # noqa: E402

IDENTITY = [[1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]]
COUNT = 0


def check(condition, message):
    global COUNT
    COUNT += 1
    assert condition, message


def fixture(folder, chain_count=4, fork=False, direct=False):
    """Arbitrary names, variable axis counts; independent analytic z-axis FK."""
    folder.mkdir()
    mesh = folder / 'solid.obj'
    # Closed consistently wound cube, side 0.2 m; no exporter/runtime dependency.
    mesh.write_text('\n'.join([
        'v -0.1 -0.1 -0.1', 'v 0.1 -0.1 -0.1', 'v 0.1 0.1 -0.1', 'v -0.1 0.1 -0.1',
        'v -0.1 -0.1 0.1', 'v 0.1 -0.1 0.1', 'v 0.1 0.1 0.1', 'v -0.1 0.1 0.1',
        'f 1 3 2', 'f 1 4 3', 'f 5 6 7', 'f 5 7 8', 'f 1 2 6', 'f 1 6 5',
        'f 4 8 7', 'f 4 7 3', 'f 1 5 8', 'f 1 8 4', 'f 2 3 7', 'f 2 7 6',
    ]) + '\n', encoding='utf-8')
    import math
    root = ET.Element('robot', name='arbitrary_machine')
    ET.SubElement(root, 'link', name='anchor')
    q, chains, endpoints, snapshots = {}, {}, {}, {'anchor': copy.deepcopy(IDENTITY)}

    def joint(name, parent, child, xyz, kind='revolute'):
        ET.SubElement(root, 'link', name=child)
        node = ET.SubElement(root, 'joint', name=name, type=kind)
        ET.SubElement(node, 'parent', link=parent)
        ET.SubElement(node, 'child', link=child)
        ET.SubElement(node, 'origin', xyz=' '.join(str(x) for x in xyz), rpy='0 0 0')
        if kind == 'revolute':
            ET.SubElement(node, 'axis', xyz='0 0 1')
            ET.SubElement(node, 'limit', lower='-1', upper='1')
        return node

    trunk, upstream, trunk_angle = 'anchor', {}, 0.
    if fork:
        joint('common_yaw', 'anchor', 'hub', [0, 0, 0])
        q['common_yaw'] = trunk_angle = 0.2
        upstream = {'common_yaw': 'shared_heading'}
        trunk = 'hub'
        matrix = copy.deepcopy(IDENTITY)
        matrix[0][:2] = [math.cos(trunk_angle), -math.sin(trunk_angle)]
        matrix[1][:2] = [math.sin(trunk_angle), math.cos(trunk_angle)]
        snapshots['hub'] = matrix
    entities = []
    for i in range(chain_count):
        parent, roles, point, angle = trunk, dict(upstream), [0., 0., 0.], trunk_angle
        axis_count = 1 + i % 3
        for j in range(axis_count):
            name, link = f'axis_{i}_{j}', f'branch_{i}_{j}'
            xyz = [i * 1.2 + 0.4, 0.2, 1.] if j == 0 else [0.25, 0., 0.]
            joint(name, parent, link, xyz)
            q[name] = (i + j + 1) * 0.03
            roles[name] = f'hinge_{j}'
            # Analytic planar position; no shared FK/rotation helper in oracle.
            point[0] += math.cos(angle) * xyz[0] - math.sin(angle) * xyz[1]
            point[1] += math.sin(angle) * xyz[0] + math.cos(angle) * xyz[1]
            point[2] += xyz[2]
            angle += q[name]
            matrix = copy.deepcopy(IDENTITY)
            matrix[0][:2] = [math.cos(angle), -math.sin(angle)]
            matrix[1][:2] = [math.sin(angle), math.cos(angle)]
            for k in range(3):
                matrix[k][3] = point[k]
            snapshots[link] = matrix
            parent = link
        chains[f'arm#{i}'] = {'root_link': 'anchor', 'end_link': parent, 'joint_roles': roles,
                             'contact_links': [parent]}
        endpoints[f'arm#{i}'] = list(point)
        entities.append(parent)
    if direct:
        first = entities[0]
        joint('weld', first, 'connected_solid', [0, 0, 0], 'fixed')
        entities.append('connected_solid')
        snapshots['connected_solid'] = copy.deepcopy(snapshots[first])
    for link in root.findall('link'):
        if link.get('name') in entities:
            collision = ET.SubElement(link, 'collision')
            geometry = ET.SubElement(collision, 'geometry')
            ET.SubElement(geometry, 'mesh', filename=mesh.name)
    urdf = folder / 'machine.urdf'
    ET.ElementTree(root).write(urdf, encoding='unicode')
    ids = list(chains)
    case = {'id': 'neutral', 'phase': 'stance', 'q_rad': q, 'root_transform': copy.deepcopy(IDENTITY)}
    reqs = []
    for name, params in [
        ('joint_limits', {}),
        ('end_position', {'expected_m': {'neutral': endpoints}, 'tolerance_m': 1e-10}),
        ('self_collision', {'clearance_m': 0.}),
        ('ground', {'normal': [0, 0, 1], 'height_m': 0., 'min_gap_m': 0., 'allowed_contacts': {}}),
    ]:
        reqs.append({'id': name, 'check': name, 'required': True, 'cases': ['neutral'], 'chains': ids, 'params': params})
    cfg = {'inputs': {'identity': 'test-approved-body', 'units': 'SI',
                      'urdf': {'path': urdf.name, 'sha256': pre.binding.sha256_file(urdf)},
                      'meshes': [{'path': mesh.name, 'sha256': pre.binding.sha256_file(mesh)}],
                      'threshold_basis': {'approved_by': 'regression-fixture', 'reference': 'analytic cubes'}},
           'body': {'chains': chains, 'other_joints': {}, 'collision_entities': entities,
                    'excluded_entities': [], 'allowed_pairs': []},
           'tasks': {'cases': [case], 'requirements': reqs}}
    return cfg, folder, snapshots


def row(report, name, case='neutral'):
    return next(r for r in report['results'] if r['id'] == name and r.get('case_id', case) == case)


def exercise(cfg, folder, expected='pass', budget=None):
    report = pre.run(cfg, folder, budget)
    check(report['status'] == expected, f"expected {expected}, got {report['status']}: {report.get('reason', report['results'])}")
    json.dumps(report, allow_nan=False)
    return report


def edit_xml(cfg, folder, change):
    updated = copy.deepcopy(cfg)
    path = folder / updated['inputs']['urdf']['path']
    original = path.read_text(encoding='utf-8')
    root = ET.fromstring(original)
    change(root)
    ET.ElementTree(root).write(path, encoding='unicode')
    updated['inputs']['urdf']['sha256'] = pre.binding.sha256_file(path)
    return updated, path, original


def rejected_xml(cfg, folder, change, state='not_supported'):
    updated, path, original = edit_xml(cfg, folder, change)
    try:
        report = exercise(updated, folder, 'fail')
        check(report['input_state'] == state, f"wrong rejection: {report.get('reason')}")
    finally:
        path.write_text(original, encoding='utf-8')


def plan_gap_suite(group):
    """Behavioral counterexamples for contact policy and independent role evidence."""
    import math
    with tempfile.TemporaryDirectory(prefix='body_precheck_plan_') as temp:
        cfg, base, _ = fixture(Path(temp) / 'pair', chain_count=1, direct=True)
        cfg['tasks']['requirements'] = [r for r in cfg['tasks']['requirements']
                                       if r['check'] in ('joint_limits', 'self_collision')]
        cfg['tasks']['cases'][0]['q_rad']['axis_0_0'] = 0.
        pair = ['branch_0_0', 'connected_solid']

        def offset(value):
            path = base / 'machine.urdf'
            root = ET.parse(path).getroot()
            root.find("joint[@name='weld']/origin").set('xyz', f'{value} 0 0')
            ET.ElementTree(root).write(path, encoding='unicode')
            cfg['inputs']['urdf']['sha256'] = pre.binding.sha256_file(path)

        if group == 'rotation':
            offset(.2)
            for angle in (0., math.pi / 4, -.27):
                c, s = math.cos(angle), math.sin(angle)
                cfg['tasks']['cases'][0]['root_transform'] = [
                    [c, -s, 0, 12.], [s, c, 0, -7.], [0, 0, 1, 3.], [0, 0, 0, 1.]]
                exercise(cfg, base)  # SAME contact under a common rigid transform.
            # Rotate the pair inside the root frame too; root cancellation alone
            # does not implement touching semantics for joint-driven poses.
            cfg['tasks']['cases'][0]['q_rad']['axis_0_0'] = .31
            exercise(cfg, base)
            offset(.199)
            exercise(cfg, base, 'fail')
        elif group == 'contact':
            collision = cfg['tasks']['requirements'][1]
            collision['params'] = {'clearance_m': .05, 'contact_pairs': [
                {'pair': pair, 'reason': 'fixture permits touching, never overlap'}]}
            offset(.2)
            out = exercise(cfg, base)
            details = row(out, 'self_collision')['detail']['pairs']
            check(len(details) == 1 and details[0]['pair'] == pair, 'contact pair must still be checked')
            check(not out['body']['excluded_pairs'], 'contact is not an exclusion')
            offset(.199)
            exercise(cfg, base, 'fail')
            offset(0.)
            exercise(cfg, base, 'fail')
            offset(.2)
            collision['params']['contact_pairs'] = []
            exercise(cfg, base, 'fail')  # Positive engineering margin still enforced.
            collision['params']['contact_pairs'] = [{'pair': pair, 'reason': ''}]
            exercise(cfg, base, 'fail')
            collision['params']['contact_pairs'] = [{'pair': pair, 'reason': 'touch'}]
            cfg['body']['allowed_pairs'] = [{'pair': pair, 'reason': 'legacy exemption'}]
            exercise(cfg, base, 'fail')  # Conflicting contact and exclusion must reject.
            # Touch permission for one pair must not waive another pair's margin.
            other, location, _ = fixture(Path(temp) / 'three', chain_count=2, direct=True)
            path = location / 'machine.urdf'
            root = ET.parse(path).getroot()
            root.find("joint[@name='weld']/origin").set('xyz', '.2 0 0')
            root.find("joint[@name='axis_1_0']/origin").set('xyz', '.85 .2 1')
            root.find("joint[@name='axis_1_1']/origin").set('xyz', '0 0 0')
            ET.ElementTree(root).write(path, encoding='unicode')
            other['inputs']['urdf']['sha256'] = pre.binding.sha256_file(path)
            other['tasks']['cases'][0]['q_rad'] = {n: 0. for n in other['tasks']['cases'][0]['q_rad']}
            other['tasks']['requirements'] = [r for r in other['tasks']['requirements']
                                              if r['check'] in ('joint_limits', 'self_collision')]
            other['tasks']['requirements'][1]['params'] = {
                'clearance_m': .1, 'contact_pairs': [{'pair': pair, 'reason': 'touch only here'}]}
            out = exercise(other, location, 'fail')
            details = row(out, 'self_collision')['detail']['pairs']
            check(len(details) == 3 and next(r for r in details if r['pair'] == pair)['state'] == 'pass',
                  'only declared contact has zero required margin')
            check(any(r['state'] == 'fail' and r['required_clearance_m'] == .1 for r in details),
                  'other-pair margin remains enforced')
        elif group == 'roles':
            offset(.3)
            role_req = {'id': 'roles', 'check': 'role_consistency', 'required': True,
                        'cases': ['neutral'], 'chains': ['arm#0'], 'params': {}}
            cfg['tasks']['requirements'].append(role_req)
            missing = exercise(cfg, base, 'fail')
            check(row(missing, 'roles')['state'] == 'not_evaluated', 'missing role evidence is unmeasured')
            roles_path = base / 'source_roles.json'
            evidence = {'schema': 'body_precheck_roles_v1',
                        'urdf_sha256': cfg['inputs']['urdf']['sha256'],
                        'approved_by': 'fixture-source-author', 'reference': 'independent fixture specification',
                        'joint_roles': {'axis_0_0': 'hinge_0'}}

            def save_evidence():
                roles_path.write_text(json.dumps(evidence), encoding='utf-8')
                cfg['inputs']['role_evidence'] = {
                    'path': roles_path.name, 'sha256': pre.binding.sha256_file(roles_path)}

            save_evidence()
            out = exercise(cfg, base)
            check(out['coverage']['role_semantics'] == 'pass', 'explicit semantic coverage')
            check(out['coverage']['source_pose_consistency'] == 'not_evaluated',
                  'role mapping is not entity motion evidence')
            cfg['body']['chains']['arm#0']['joint_roles']['axis_0_0'] = 'wrong_semantic_role'
            out = exercise(cfg, base, 'fail')
            check(row(out, 'roles')['state'] == 'fail', 'same names with wrong roles must fail')
            cfg['body']['chains']['arm#0']['joint_roles']['axis_0_0'] = 'hinge_0'
            evidence['urdf_sha256'] = '0' * 64
            save_evidence()
            exercise(cfg, base, 'fail')
            evidence['urdf_sha256'] = cfg['inputs']['urdf']['sha256']
            evidence['joint_roles'] = {}
            save_evidence()
            exercise(cfg, base, 'fail')
            evidence['joint_roles'] = {'axis_0_0': 'hinge_0'}
            save_evidence()
            roles_path.write_text('{}', encoding='utf-8')
            exercise(cfg, base, 'fail')
            save_evidence()
            consumer = pre.revalidate_inputs
            mutated = False

            def mutate_evidence(report):
                nonlocal mutated
                if 'role_evidence' in report['inputs'] and not mutated:
                    roles_path.write_text('{}', encoding='utf-8')
                    mutated = True
                return consumer(report)

            from unittest.mock import patch
            with patch.object(pre, 'revalidate_inputs', mutate_evidence):
                exercise(cfg, base, 'fail')
            save_evidence()
            config_path, report_path = base / 'config.json', base / 'roles_report.json'
            config_path.write_text(json.dumps(cfg), encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', str(pre.HERE), '--config', str(config_path),
                                     '--output', str(report_path)], capture_output=True, text=True)
            check(result.returncode == 0 and json.loads(report_path.read_text())['coverage']['role_semantics'] == 'pass',
                  'role evidence consumed through real CLI')
        print(f'PASS plan gap {group}: {COUNT} assertions')


def run_suite(break_zero=False, break_fix=None):
    broken_source = None
    if break_fix:
        source = pre.HERE.read_text(encoding='utf-8')
        changes = {
            'binding': ("    need(all(record['binding_state'] == 'pass' for record in records), 'bound input changed or unreadable')",
                        '    return'),
            'roles': ("                need(joint not in joint_roles or joint_roles[joint] == role, f'conflicting joint role: {joint}')",
                      '                pass'),
            'params': ("    need(isinstance(params, dict), 'check params object required')\n    if check == 'joint_limits':\n        need(not params, 'joint_limits params must be empty')",
                       "    if check == 'joint_limits':"),
            'coverage': ("missing = sorted({'joint_limits', 'self_collision'} - whole)",
                         "missing = sorted({'joint_limits', 'self_collision', 'ground', 'end_position'} - whole)"),
            'error_rows': ("{'id': req.get('id') if isinstance(req.get('id'), str) else None,\n                                                  'check': req.get('check') if isinstance(req.get('check'), str) else None,\n                                                  'required': req.get('required') if type(req.get('required')) is bool else True,",
                           "{'id': req.get('id'), 'check': req.get('check'), 'required': req.get('required'),"),
            'mesh': ("    need(np.all((double_area == 0) | (double_area > 1e-14)) and np.any(double_area > 1e-14),",
                     "    need(original_count == len(faces) and np.all(double_area > 1e-14),"),
            'config_digest': ("'sha256': digest}", "'sha256': binding.sha256_file(args.config)}"),
            'touching': ("witness = separating_face(va, fa, vb, fb, np)", "witness = None"),
            'contact_policy': ("margin = 0. if (a, b) in contact_pairs else clearance", "margin = clearance"),
            'role_semantics': ("return ('fail' if mismatches else 'pass'), {", "return 'pass', {"),
        }
        old, new = changes[break_fix]
        check(source.count(old) == 1, 'break injection must match exactly once')
        broken_source = source.replace(old, new)
        exec(compile(broken_source, str(pre.HERE), 'exec'), pre.__dict__)
    if break_zero:
        original_pair = pre.pair_evaluate

        def broken_pair(a, b, world, meshes, clearance, np, triangles):
            va, vb = world[a], world[b]
            lower = float(np.linalg.norm(np.maximum(0., np.maximum(va.min(0) - vb.max(0), vb.min(0) - va.max(0)))))
            if lower >= clearance:  # Historical defect injected into REAL run consumer.
                return {'pair': [a, b], 'gap_lower_m': lower, 'method': 'BROKEN_ZERO_AABB', 'state': 'pass'}
            return original_pair(a, b, world, meshes, clearance, np, triangles)

        pre.pair_evaluate = broken_pair
    with tempfile.TemporaryDirectory(prefix='body_precheck_') as temp:
        folder = Path(temp)
        cfg, base, snapshots = fixture(folder / 'four')
        report = exercise(cfg, base)
        # Mutations at approval, validation and shared path readers must lose binding.
        import check_self_collision as csc
        for owner, attribute, artifact in [(pre, 'bound_input', 'urdf'), (pre, 'validate_urdf', 'urdf'),
                                            (csc, 'load_urdf', 'urdf'), (csc, 'read_obj_faces', 'mesh')]:
            target = base / ('machine.urdf' if artifact == 'urdf' else 'solid.obj')
            original_bytes = target.read_bytes()
            consumer = getattr(owner, attribute)
            changed = False

            def mutate_after(*args, **kwargs):
                nonlocal changed
                result = consumer(*args, **kwargs)
                if not changed:
                    target.write_bytes(original_bytes.replace(b'upper="1"', b'upper="2"')
                                       if artifact == 'urdf' else original_bytes + b'# changed\n')
                    changed = True
                return result

            setattr(owner, attribute, mutate_after)
            try:
                out = exercise(cfg, base, 'fail')
                records = [out['inputs']['urdf']] + out['inputs']['meshes']
                check(any(r.get('binding_state') == 'fail' and r['actual_sha256'] != r['approved_sha256']
                          for r in records), f'{attribute}: failure must expose lost binding')
            finally:
                setattr(owner, attribute, consumer)
                target.write_bytes(original_bytes)
        generic = copy.deepcopy(cfg)
        generic['tasks']['requirements'] = [r for r in generic['tasks']['requirements']
                                            if r['check'] in {'joint_limits', 'self_collision'}]
        generic['tasks']['cases'][0]['phase'] = 'free_space'
        for chain in generic['body']['chains'].values():
            chain['contact_links'] = []
        out = exercise(generic, base)
        check({r['check'] for r in out['results']} == {'joint_limits', 'self_collision'}, 'no inferred floor/endpoint')
        check(len(out['coverage']['cases']['neutral']['required_selections']) == 2, 'full selected row coverage recorded')
        for req_index in range(4):
            for bad_params in ['ignored', [], {'typo': 0}]:
                updated = copy.deepcopy(cfg)
                updated['tasks']['requirements'][req_index]['params'] = bad_params
                out = exercise(updated, base, 'fail')
                check(row(out, cfg['tasks']['requirements'][req_index]['id'])['state'] == 'not_evaluated',
                      'known check invalid params must not pass')
                optional = copy.deepcopy(cfg['tasks']['requirements'][req_index])
                optional.update(id='malformed_optional', required=False, params=bad_params)
                updated = copy.deepcopy(cfg); updated['tasks']['requirements'].append(optional)
                check(row(exercise(updated, base), 'malformed_optional')['state'] == 'not_evaluated',
                      'optional invalid params visible without overriding required pass')
        check(report['coverage']['whole_machine'] == 'pass', 'whole-machine coverage')
        check(len(report['body']['checked_pairs']) == 6, 'four-chain full pair set')
        check(report['counters']['pairs_evaluated'] == 6, 'pair counter')
        for count, fork in [(6, False), (4, True), (6, True)]:
            other, location, _ = fixture(folder / f'{count}_{fork}', count, fork)
            out = exercise(other, location)
            check(len(out['body']['checked_pairs']) == count * (count - 1) // 2, 'generic full pairs')
            if fork:
                check(all('common_yaw' in c['actual_joints'] for c in out['body']['chains'].values()), 'fork shared upstream coverage')
                conflict = copy.deepcopy(other)
                conflict['body']['chains']['arm#1']['joint_roles']['common_yaw'] = 'contradictory_role'
                check('conflicting joint role: common_yaw' in exercise(conflict, location, 'fail')['reason'],
                      'shared joint contradictory roles rejected')
                torso = copy.deepcopy(other)
                for chain in torso['body']['chains'].values():
                    chain['root_link'] = 'hub'
                    chain['joint_roles'].pop('common_yaw')
                torso['body']['other_joints'] = {'common_yaw': 'torso_heading'}
                exercise(torso, location)
                torso['body']['other_joints'] = {}
                exercise(torso, location, 'fail')
        # Full q/world root drives analytic expected positions and snapshots.
        moved = copy.deepcopy(cfg)
        moved['tasks']['cases'][0]['root_transform'][0][3] = 2.
        for point in moved['tasks']['requirements'][1]['params']['expected_m']['neutral'].values():
            point[0] += 2.
        exercise(moved, base)
        snapshot_req = {'id': 'snap', 'check': 'source_consistency', 'required': True,
                        'cases': ['neutral'], 'chains': list(cfg['body']['chains']),
                        'params': {'approved_by': 'analytic-test', 'reference': 'independent-z-rotation',
                                   'tolerance_m': 1e-10, 'tolerance_rad': 1e-7,
                                   'snapshots': {'neutral': {'q_rad': copy.deepcopy(cfg['tasks']['cases'][0]['q_rad']),
                                                           'root_transform': copy.deepcopy(IDENTITY), 'link_poses': snapshots}}}}
        snap_cfg = copy.deepcopy(cfg); snap_cfg['tasks']['requirements'].append(snapshot_req)
        exercise(snap_cfg, base)
        for bad_params in ['ignored', [], {**snapshot_req['params'], 'typo': 0}]:
            updated = copy.deepcopy(cfg)
            invalid = copy.deepcopy(snapshot_req); invalid['params'] = bad_params
            updated['tasks']['requirements'].append(invalid)
            check(row(exercise(updated, base, 'fail'), 'snap')['state'] == 'not_evaluated',
                  'source_consistency invalid params rejected')
        updated = copy.deepcopy(cfg); updated['tasks']['requirements'][0].pop('params')
        check(row(exercise(updated, base, 'fail'), 'joint_limits')['state'] == 'not_evaluated',
              'missing joint_limits params not evaluated')
        snap_cfg['tasks']['requirements'][-1]['params']['snapshots']['neutral']['q_rad']['axis_0_0'] += .1
        check(row(exercise(snap_cfg, base, 'fail'), 'snap')['state'] == 'not_evaluated', 'snapshot full q binding')
        # Counterexample: every endpoint succeeds, solids from different chains coincide.
        overlap, path, original = edit_xml(cfg, base, lambda root: root.find("joint[@name='axis_1_0']/origin").set('xyz', '0.4 0.2 1'))
        try:
            overlap['tasks']['cases'][0]['q_rad']['axis_1_0'] = 0.
            overlap['tasks']['cases'][0]['q_rad']['axis_1_1'] = 0.
            overlap['tasks']['cases'][0]['q_rad']['axis_0_0'] = 0.
            root = ET.parse(path).getroot()
            root.find("joint[@name='axis_1_1']/origin").set('xyz', '0 0 0')
            ET.ElementTree(root).write(path, encoding='unicode')
            overlap['inputs']['urdf']['sha256'] = pre.binding.sha256_file(path)
            exp = overlap['tasks']['requirements'][1]['params']['expected_m']['neutral']
            exp['arm#0'] = exp['arm#1'] = [0.4, 0.2, 1.]
            out = exercise(overlap, base, 'fail')  # --break_zero_aabb MUST go red HERE.
            check(row(out, 'end_position')['state'] == 'pass', 'endpoint-only false-pass counterexample')
            check(row(out, 'self_collision')['state'] == 'fail', 'zero clearance coincident solids must fail')
            # Nested solids, no surface crossing: shared solid-angle containment.
            nested = copy.deepcopy(overlap)
            small_mesh = base / 'inner.obj'
            small_lines = []
            for line in (base / 'solid.obj').read_text(encoding='utf-8').splitlines():
                small_lines.append('v ' + ' '.join(str(float(x) / 2) for x in line.split()[1:])
                                   if line.startswith('v ') else line)
            small_mesh.write_text('\n'.join(small_lines) + '\n', encoding='utf-8')
            root.find("link[@name='branch_1_1']/collision/geometry/mesh").set('filename', 'inner.obj')
            ET.ElementTree(root).write(path, encoding='unicode')
            nested['inputs']['urdf']['sha256'] = pre.binding.sha256_file(path)
            nested['inputs']['meshes'].append({'path': 'inner.obj', 'sha256': pre.binding.sha256_file(small_mesh)})
            nested_out = exercise(nested, base, 'fail')
            nested_pair = next(p for p in row(nested_out, 'self_collision')['detail']['pairs']
                               if p['pair'] == ['branch_0_0', 'branch_1_1'])
            check(nested_pair['contained'] and not nested_pair['intersects'], 'contained solids without surface crossing')
            root.find("link[@name='branch_1_1']/collision/geometry/mesh").set('filename', 'solid.obj')
            crossing = copy.deepcopy(overlap)
            root.find("joint[@name='axis_1_1']/origin").set('xyz', '.1 0 0')
            ET.ElementTree(root).write(path, encoding='unicode')
            crossing['inputs']['urdf']['sha256'] = pre.binding.sha256_file(path)
            crossing['tasks']['requirements'][1]['params']['expected_m']['neutral']['arm#1'] = [.5, .2, 1.]
            check(row(exercise(crossing, base, 'fail'), 'self_collision')['state'] == 'fail', 'partial overlapping solids')
            separated = copy.deepcopy(crossing)
            root.find("joint[@name='axis_1_1']/origin").set('xyz', '.2 0 0')
            ET.ElementTree(root).write(path, encoding='unicode')
            separated['inputs']['urdf']['sha256'] = pre.binding.sha256_file(path)
            separated['tasks']['requirements'][1]['params']['expected_m']['neutral']['arm#1'] = [.6, .2, 1.]
            exercise(separated, base)  # Exactly zero surface separation: touching allowed.
            root.find("joint[@name='axis_1_1']/origin").set('xyz', '.3 0 0')
            ET.ElementTree(root).write(path, encoding='unicode')
            separated['inputs']['urdf']['sha256'] = pre.binding.sha256_file(path)
            separated['tasks']['requirements'][1]['params']['expected_m']['neutral']['arm#1'] = [.7, .2, 1.]
            exercise(separated, base)  # Zero required clearance; positive separation passes.
            separated['tasks']['requirements'][2]['params']['clearance_m'] = .05
            exercise(separated, base)
            separated['tasks']['requirements'][2]['params']['clearance_m'] = .15
            check(row(exercise(separated, base, 'fail'), 'self_collision')['state'] == 'fail', 'insufficient positive gap')
        finally:
            path.write_text(original, encoding='utf-8')
        direct, location, _ = fixture(folder / 'direct', direct=True)
        check(row(exercise(direct, location, 'fail'), 'self_collision')['state'] == 'fail', 'directly jointed pair cannot disappear')
        direct['body']['allowed_pairs'] = [{'pair': ['branch_0_0', 'connected_solid'], 'reason': 'fixture welded overlapping geometry'}]
        out = exercise(direct, location)
        check(len(out['body']['excluded_pairs']) == 1, 'explicit exclusion reported')
        for transform, attribute, value in [('joint', 'rpy', '0 0 1e-16'),
                                            ('collision', 'xyz', '1e-16 0 0'),
                                            ('collision', 'rpy', '0 1e-16 0')]:
            def change(root, transform=transform, attribute=attribute, value=value):
                target = root.find('joint/origin') if transform == 'joint' else ET.SubElement(root.find('link/collision'), 'origin')
                target.set(attribute, value)
            rejected_xml(cfg, base, change)
        rejected_xml(cfg, base, lambda r: r.find('link/collision/geometry/mesh').set('scale', '1 1 1.0000000000000002'))
        rejected_xml(cfg, base, lambda r: r.find('link/collision/geometry').append(ET.Element('box', size='1 1 1')))
        rejected_xml(cfg, base, lambda r: r.find('link/collision/geometry').remove(r.find('link/collision/geometry/mesh')))
        rejected_xml(cfg, base, lambda r: r.find("link[@name='branch_0_0']").append(copy.deepcopy(r.find('link/collision'))))
        rejected_xml(cfg, base, lambda r: ET.SubElement(r.find('joint'), 'mimic', joint='axis_1_0'))
        for kind in ('prismatic', 'continuous', 'floating', 'mystery'):
            rejected_xml(cfg, base, lambda r, kind=kind: r.find('joint').set('type', kind))
        rejected_xml(cfg, base, lambda r: r.find('joint').remove(r.find('joint/origin')))
        for change in [
            lambda r: r.find('joint/axis').set('xyz', 'nan 0 1'),
            lambda r: r.find('joint/axis').set('xyz', '0 0 0'),
            lambda r: r.find('joint/limit').set('upper', 'inf'),
            lambda r: r.find('joint/parent').set('link', 'nonexistent'),
            lambda r: r.find('joint/parent').set('link', 'branch_0_0'),
            lambda r: r.append(copy.deepcopy(r.find('joint'))),
            lambda r: r.append(copy.deepcopy(r.find('link'))),
            lambda r: r.findall('joint')[1].find('child').set('link', 'branch_0_0'),
            lambda r: ET.SubElement(r, 'link', name='orphan'),
        ]:
            rejected_xml(cfg, base, change, 'not_evaluated')
        # A disconnected cycle plus one valid root defeats root-count-only validation.
        def add_cycle(root):
            for name in ('cycle_a', 'cycle_b'):
                ET.SubElement(root, 'link', name=name)
            for i, (parent, child) in enumerate([('cycle_a', 'cycle_b'), ('cycle_b', 'cycle_a')]):
                joint = ET.SubElement(root, 'joint', name=f'cycle{i}', type='fixed')
                ET.SubElement(joint, 'origin', xyz='0 0 0')
                ET.SubElement(joint, 'parent', link=parent); ET.SubElement(joint, 'child', link=child)
        rejected_xml(cfg, base, add_cycle, 'not_evaluated')
        mesh = base / 'solid.obj'; original_mesh = mesh.read_text(encoding='utf-8')
        # Exported poles: duplicate coordinates weld to repeated-index zero-width faces.
        pole_mesh = original_mesh + 'v -0.1 -0.1 -0.1\nf 1 9 2\nf 9 1 3\n'
        # Split one cube edge on one side only; the collinear face closes its topology.
        collinear_mesh = original_mesh.replace('f 1 3 2\n', 'f 1 3 9\nf 9 3 2\nf 1 9 2\n')
        collinear_mesh += 'v 0 -0.1 -0.1\n'
        for source, dropped, retained in [(pole_mesh, 2, 0), (collinear_mesh, 0, 1)]:
            updated = copy.deepcopy(cfg)
            mesh.write_text(source, encoding='utf-8')
            digest = pre.binding.sha256_file(mesh)
            updated['inputs']['meshes'][0]['sha256'] = digest
            try:
                out = exercise(updated, base)  # Historical rejection must fail THIS assertion.
                counts = out['mesh_normalization']['branch_0_0']
                check(counts['dropped_repeated_index_faces'] == dropped
                      and counts['retained_collinear_faces'] == retained, 'pole normalization counts')
                check(counts['normalized_faces'] == 12 + retained * 2, 'no finite-area faces dropped')
                check(pre.binding.sha256_file(mesh) == digest
                      and all(r['actual_sha256'] == r['approved_sha256'] and r['binding_state'] == 'pass'
                              for r in [out['inputs']['urdf'], *out['inputs']['meshes']]),
                      'normalization preserves bound asset bytes')
            finally:
                mesh.write_text(original_mesh, encoding='utf-8')
        # Removing genuine faces, reversing winding, duplicates and tiny finite areas stay rejected.
        for source, reason in [
            (pole_mesh.replace('f 1 3 2\n', ''), 'non-watertight mesh'),
            (pole_mesh.replace('f 1 3 2\n', 'f 1 2 3\n'), 'inconsistent mesh winding'),
            (pole_mesh + 'f 1 3 2\n', 'duplicate mesh faces'),
            (collinear_mesh.replace('v 0 -0.1 -0.1', 'v 0 -0.1 -0.099999999999999'),
             'degenerate mesh triangles'),
            ('\n'.join('v ' + ' '.join(str(float(x) * 1e-7) for x in line.split()[1:])
                       if line.startswith('v ') else line for line in original_mesh.splitlines()) + '\n',
             'degenerate mesh triangles'),
        ]:
            updated = copy.deepcopy(cfg)
            mesh.write_text(source, encoding='utf-8')
            updated['inputs']['meshes'][0]['sha256'] = pre.binding.sha256_file(mesh)
            try:
                out = exercise(updated, base, 'fail')
                check(reason in out['reason'], f'damaged/tiny mesh rejection: {out["reason"]}')
            finally:
                mesh.write_text(original_mesh, encoding='utf-8')
        for bad, state in [('v nan -0.1 -0.1', 'not_evaluated'), ('f -1 3 2', 'not_supported'),
                           ('f 1 3 2 4', 'not_supported'), ('f 1 999 2', 'not_evaluated')]:
            updated = copy.deepcopy(cfg)
            source = original_mesh.replace('v -0.1 -0.1 -0.1', bad) if bad.startswith('v') else original_mesh.replace('f 1 3 2', bad)
            mesh.write_text(source, encoding='utf-8')
            updated['inputs']['meshes'][0]['sha256'] = pre.binding.sha256_file(mesh)
            try:
                out = exercise(updated, base, 'fail'); check(out['input_state'] == state, 'malformed OBJ rejection')
            finally:
                mesh.write_text(original_mesh, encoding='utf-8')
        for change in [
            lambda c: c['tasks']['cases'][0]['q_rad'].pop('axis_0_0'),
            lambda c: c['tasks']['cases'][0]['q_rad'].update(axis_0_0=float('nan')),
            lambda c: c['tasks']['cases'][0]['root_transform'][0].__setitem__(3, float('inf')),
            lambda c: c['tasks']['cases'][0]['root_transform'][0].__setitem__(0, -1.),
            lambda c: c['tasks']['cases'][0]['root_transform'][0].__setitem__(0, 2.),
            lambda c: c['body']['chains']['arm#0']['joint_roles'].update(ghost='wrong'),
            lambda c: c['body']['chains']['arm#0']['joint_roles'].pop('axis_0_0'),
            lambda c: c['body']['chains'].pop('arm#0'),
            lambda c: c['body'].__setitem__('chains', {}),
            lambda c: c['body'].__setitem__('collision_entities', []),
            lambda c: c['body']['collision_entities'].pop(),
            lambda c: c['inputs']['urdf'].__setitem__('sha256', '0' * 64),
            lambda c: c['inputs']['meshes'][0].__setitem__('sha256', '0' * 64),
            lambda c: c['tasks'].__setitem__('requirements', []),
            lambda c: c['tasks']['requirements'][0].update(not_applicable=True, reason='arbitrary override'),
            lambda c: c['body']['allowed_pairs'].append({'pair': ['branch_0_0', 'branch_1_1'], 'reason': ''}),
        ]:
            updated = copy.deepcopy(cfg); change(updated); exercise(updated, base, 'fail')
        updated = copy.deepcopy(cfg)
        updated['body']['collision_entities'] = ['branch_0_0']
        updated['body']['excluded_entities'] = [{'link': n, 'reason': 'explicit fixture exclusion'}
                                                for n in cfg['body']['collision_entities'] if n != 'branch_0_0']
        out = exercise(updated, base)
        check(row(out, 'self_collision')['state'] == 'not_applicable'
              and row(out, 'self_collision')['detail']['reason'], 'only mathematical NA with explicit reason')
        updated = copy.deepcopy(cfg); updated['tasks']['cases'][0]['q_rad']['axis_0_0'] = 1.1
        check(row(exercise(updated, base, 'fail'), 'joint_limits')['state'] == 'fail', 'actual named q exceeds limit')
        updated = copy.deepcopy(cfg); updated['tasks']['requirements'][1]['params']['expected_m']['neutral']['arm#0'][0] += .1
        check(row(exercise(updated, base, 'fail'), 'end_position')['state'] == 'fail', 'analytic endpoint failure')
        updated = copy.deepcopy(cfg); updated['tasks']['requirements'][2]['check'] = 'unknown_check'
        check(row(exercise(updated, base, 'fail'), 'self_collision')['state'] == 'not_supported', 'unknown requirement not pass')
        updated = copy.deepcopy(cfg); updated['tasks']['requirements'][2]['params'] = {}
        check(row(exercise(updated, base, 'fail'), 'self_collision')['state'] == 'not_evaluated', 'missing parameter not pass')
        updated = copy.deepcopy(cfg); updated['tasks']['requirements'][2]['required'] = False
        check(exercise(updated, base, 'fail')['coverage']['whole_machine'] == 'fail', 'optional collision cannot fill mandatory coverage')
        updated = copy.deepcopy(cfg); updated['tasks']['requirements'][1]['chains'] = ['arm#0']
        check(exercise(updated, base)['coverage']['whole_machine'] == 'pass', 'endpoint coverage follows explicit selection')
        updated = copy.deepcopy(cfg); updated['tasks']['requirements'][3]['params']['height_m'] = .95
        check(row(exercise(updated, base, 'fail'), 'ground')['state'] == 'fail', 'all mesh vertices checked against plane')
        updated['tasks']['requirements'][3]['params']['allowed_contacts'] = {
            n: {'max_penetration_m': .06, 'max_gap_m': .01} for n in cfg['body']['collision_entities']}
        exercise(updated, base)
        updated['tasks']['requirements'][3]['params']['allowed_contacts']['branch_0_0']['max_penetration_m'] = .01
        check(row(exercise(updated, base, 'fail'), 'ground')['state'] == 'fail', 'contact penetration tolerance')
        updated = copy.deepcopy(cfg); updated['tasks']['requirements'].append({**copy.deepcopy(snapshot_req), 'required': False, 'check': 'unsupported_optional'})
        check(row(exercise(updated, base), 'snap')['state'] == 'not_supported', 'optional unknown visible, cannot mask required')
        out = exercise(cfg, base, 'fail', 0)
        check(all(r['state'] == 'not_evaluated' for r in out['results']), 'zero budget cannot truncate to pass')
        updated = copy.deepcopy(cfg)
        second = copy.deepcopy(updated['tasks']['cases'][0]); second['id'] = 'second'; second['phase'] = 'swing'
        updated['tasks']['cases'].append(second)
        for req in updated['tasks']['requirements']:
            req['cases'].append('second')
            if req['check'] == 'end_position':
                req['params']['expected_m']['second'] = copy.deepcopy(req['params']['expected_m']['neutral'])
        out = exercise(updated, base, 'fail', 1)
        check(row(out, 'self_collision', 'second')['state'] == 'not_evaluated', 'unprocessed mandatory case remains')
        check(out['counters']['cases_evaluated'] == 1, 'budget exact')
        # Real CLI: success, refusal to overwrite, malformed JSON, unknown URDF, bad hash.
        config_path = base / 'config.json'; config_path.write_text(json.dumps(cfg), encoding='utf-8')
        output = base / 'report.json'
        command = [sys.executable, '-B', str(pre.HERE), '--config', str(config_path), '--output', str(output)]
        if break_fix == 'error_rows':
            injected = "import sys; sys.path.insert(0, " + repr(str(pre.HERE.parent)) + "); import body_precheck as p; exec(compile(" + repr(broken_source) + ", str(p.HERE), 'exec'), p.__dict__); sys.exit(p.main())"
            injected_path = base / 'broken_cli.py'
            injected_path.write_text(injected, encoding='utf-8')
            command = [sys.executable, '-B', str(injected_path)] + command[3:]
        result = subprocess.run(command, capture_output=True, text=True)
        check(result.returncode == 0, f'CLI pass: {result.stderr}')
        content = output.read_bytes()
        check(json.loads(content)['status'] == 'pass', 'CLI consumer report')
        check(json.loads(content)['config']['sha256'] == pre.binding.sha256_bytes(config_path.read_bytes()),
              'CLI digest matches consumed config bytes')
        for key in ('id', 'check', 'required'):
            for value in (float('nan'), float('inf'), -float('inf')):
                malformed = copy.deepcopy(cfg)
                malformed['tasks']['requirements'][0][key] = value
                config_path.write_text(json.dumps(malformed), encoding='utf-8')
                target = base / f'nonfinite_{key}_{value}.json'
                result = subprocess.run(command[:-1] + [str(target)], capture_output=True, text=True)
                check(result.returncode == 1, f'nonfinite requirement {key}: CLI1 not partial CLI2: {result.stderr}')
                out = json.loads(target.read_text(encoding='utf-8'),
                                 parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
                check(out['status'] == 'fail' and all(type(r['required']) is bool for r in out['results']),
                      'nonfinite rejection writes strict JSON with safe bool fallback')
        config_path.write_text(json.dumps(cfg), encoding='utf-8')
        # In-process CLI config mutation after parse: digest still names consumed bytes.
        from unittest.mock import patch
        target = base / 'config_mutation_report.json'
        consumed = config_path.read_bytes()
        real_run = pre.run

        def mutate_config(*args, **kwargs):
            config_path.write_bytes(b'{"changed_after_parse":true}')
            return real_run(*args, **kwargs)

        with patch.object(pre, 'run', mutate_config), patch.object(sys, 'argv',
                ['body_precheck', '--config', str(config_path), '--output', str(target)]):
            check(pre.main() == 0, 'config consumed once CLI pass')
        check(json.loads(target.read_text(encoding='utf-8'))['config']['sha256'] == pre.binding.sha256_bytes(consumed),
              'config digest must not claim late mutated path bytes')
        config_path.write_bytes(consumed)
        result = subprocess.run(command, capture_output=True, text=True)
        check(result.returncode == 2 and output.read_bytes() == content, 'fresh-only output no overwrite')
        for i, payload in enumerate(['{broken', '{"inputs":{},"inputs":{}}', json.dumps({**cfg, 'inputs': {**cfg['inputs'], 'urdf': {'path': 'machine.urdf', 'sha256': '0' * 64}}})]):
            config_path.write_text(payload, encoding='utf-8')
            target = base / f'bad_report_{i}.json'
            result = subprocess.run(command[:-1] + [str(target)], capture_output=True, text=True)
            check(result.returncode == 1 and 'Traceback' not in result.stderr, 'invalid input CLI fail without traceback')
            check(json.loads(target.read_text(encoding='utf-8'))['status'] == 'fail', 'invalid input writes report')
        unknown, path, original = edit_xml(cfg, base, lambda r: r.find('joint').set('type', 'prismatic'))
        try:
            config_path.write_text(json.dumps(unknown), encoding='utf-8')
            target = base / 'unsupported_report.json'
            result = subprocess.run(command[:-1] + [str(target)], capture_output=True, text=True)
            check(result.returncode == 1 and json.loads(target.read_text(encoding='utf-8'))['input_state'] == 'not_supported', 'unsupported asset real CLI')
        finally:
            path.write_text(original, encoding='utf-8')
        print(f'PASS: {COUNT} assertions; CLI and run pipeline; isolated temporary assets')
        print(json.dumps({'body_precheck_sha256': pre.binding.sha256_file(pre.HERE),
                          'test_sha256': pre.binding.sha256_file(Path(__file__)),
                          'shared_code_sha256': report['code_sha256']}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--break_zero_aabb', action='store_true')
    parser.add_argument('--break_fix', choices=['binding', 'error_rows', 'roles', 'params', 'coverage', 'config_digest',
                                               'mesh', 'touching', 'contact_policy', 'role_semantics'])
    parser.add_argument('--plan_gap', choices=['rotation', 'contact', 'roles'])
    args = parser.parse_args()
    if args.plan_gap:
        plan_gap_suite(args.plan_gap)
    else:
        run_suite(args.break_zero_aabb, args.break_fix)
        for group in ('rotation', 'contact', 'roles'):
            plan_gap_suite(group)
