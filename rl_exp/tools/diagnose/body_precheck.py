# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Sampled generic body precheck [m, rad]; plain JSON, no simulation or solver.

CLI: body_precheck.py --config INPUT.json --output FRESH.json [--max_cases N].
Paths in inputs resolve relative to INPUT.json. Output parent must exist; output
must be fresh, under repository rl_exp/out or system temp. Exit 0 only for pass,
1 for a written non-pass report, 2 for unsafe/unwritable output or CLI misuse.

Contract (three blocks, no inferred q, roles, approvals or exclusions):
inputs: identity (nonempty label), units='SI', urdf={path, sha256},
        meshes=[{path, sha256}], threshold_basis={approved_by, reference},
        optional role_evidence={path, sha256}, source_evidence={path, sha256}.
        Source evidence is the existing saved/reopened pose-sample JSON payload:
        candidate_urdf (resolved actual path), candidate_sha256,
        candidate_blend_sha256, candidate_files_sha256, builder_sha256,
        snapshots=[{case,q_rad,pivots:{ALL links:[x,y,z]},meshes:{object_name:
        {link,vertex_count,indices,points}}}]. Hash binds exact bytes read once;
        consumed visual OBJ and saved candidate blend hashes come from that file.
        Source object indices refer to source vertices, NOT exported vertex indices;
        counts need not equal welded/merged exported counts. Every visual link and
        every supplied object is checked; object inventory is stable across snapshots.
body: chains={id: {root_link, end_link, joint_roles={exact_joint: role},
                  contact_links=[link]}}, other_joints={exact_joint: role},
      collision_entities=[link], excluded_entities=[{link, reason}],
      allowed_pairs=[{pair:[link,link], reason}] (legacy WHOLE-PAIR EXCLUSIONS,
      deprecated for contact permissions; retained for existing configurations).
tasks: cases=[{id, phase, q_rad={ALL movable joints: radians},
               root_transform:4x4 SE3}],
       requirements=[{id, check, required:bool, cases:[case_id], chains:[id],
                      params:{...}}]. No wildcard selection.
Checks/params:
 joint_limits: {} (actual URDF bounds, whole machine).
 end_position: {expected_m:{case_id:{chain_id:[x,y,z]}}, tolerance_m}.
   Position is end-link origin in world, NOT an inferred sole/contact point.
 self_collision: {clearance_m, optional contact_pairs:[{pair:[link,link],reason}]}.
   Contact pairs remain checked with zero clearance; they waive ONLY the positive
   engineering margin, never the intersection test. Pair exclusions and contact
   permissions must not overlap. No inherited joint-neighbour exclusions.
   A separating face plane certifies nonpenetration to floating-point resolution.
   Predicate tolerance is 64 * float64 epsilon * pair extent [m], NOT an approved
   penetration allowance. Concave contacts without a separating face plane retain
   the conservative shared intersection result; no general contact classifier.
 role_consistency: {}. Requires inputs.role_evidence, an externally approved JSON:
   {schema:'body_precheck_roles_v1', urdf_sha256, joint_roles:{ALL joints:role},
    approved_by, reference}. ALL means movable joints including other_joints.
   Evidence is read once, hash-bound and compared against the actual URDF identity.
   This checks adapter role semantics against the external mapping, NOT physical
   axis/pivot or entity motion. Use independent source_consistency poses for those.
 ground: {normal:[x,y,z], height_m, min_gap_m,
          allowed_contacts:{link:{max_penetration_m,max_gap_m}}}.
   Unit normal; signed distance normal.dot(world_vertex)-height_m [m]. Contact
   minima must be in [-max_penetration_m,max_gap_m]; all other minima >=min_gap_m.
 source_geometry: {tolerance_m, source_cases:{case_id:source_snapshot_name},
   optional sparse_zero_reset:bool, reset_reference:nonempty provenance}.
   Reuses palm_spatial_probe.check_blender's independent pivot and nearest visual
   vertex readings, without importing its solver. World-neutral exporter frame:
   subtract source root pivot, then apply case root_transform to observations.
   Missing source q means zero ONLY with explicit sparse_zero_reset=true and
   reset_reference; effective complete q must equal selected case. No full source
   orientation, role/axis correctness, connection region, mass/dynamics or continuous
   proof. Absent optional evidence is not_evaluated; unknown payload not_supported.
 source_consistency: {approved_by, reference, tolerance_m, tolerance_rad,
   snapshots:{case_id:{q_rad,root_transform,link_poses:{ALL links:4x4 SE3}}}}.
   Explicit externally approved snapshots, never an independent FK claim.
All thresholds need input approval basis. Unknown checks -> not_supported;
missing check parameters -> not_evaluated. No caller-supplied NA overrides.
Five row states: pass/fail/not_evaluated/not_supported/not_applicable. NA only
for self_collision with one entity (explicit mathematical reason). Every case
needs required joint_limits + self_collision over ALL chains. Ground and
end_position apply only to explicitly selected cases/chains; neither is inferred.
coverage.role_semantics and coverage.source_pose_consistency separately report
full-selection checks across every case; absent evidence stays not_evaluated.
The role evidence's independence and approval remain caller/auditor prerequisites;
copying the adapter mapping into another file is not independent validation.
Whole-machine coverage means sampled limits + collision geometry only, not task
completion. Optional rows cannot replace mandatory ones. Case budget leaves
rows not_evaluated; validation still covers ALL cases before sampling.
Bindings are rehashed before/after path-only consumers and before verdict. This
 detects ordinary concurrent changes, NOT strict immutable consumed bytes (an
 edit restored between checks can escape detection). Config digest binds the
 bytes read once, not a later path read.

Support: connected rooted rigid tree, revolute/fixed, arbitrary serial chains
and forks. No mimic/loops. Joint origin xyz REQUIRED, rpy exactly zero; axis
and finite lower/upper REQUIRED for revolute. Zero collision origin xyz/rpy,
unit mesh scale, exactly one geometry with one triangle positive-index OBJ
per collision-bearing link. Mesh must be finite, closed, consistently wound;
repeated export vertices are welded exactly and repeated-index faces removed.
Distinct exactly collinear faces retain closed topology under shared guarded
triangle algorithms; nonzero double-area must exceed 1e-14 m^2 and at least one
finite-area face is required. Topology checks do NOT certify self-intersection
absence or a meaningful physical solid; sampled results assume exported solid
surfaces. No polygon truncation.
Self collision is evaluated in the robot root frame, so a common world transform
does not change its predicate; ground/endpoints/source poses use the world frame.
Excluded meshes are not consumed or checked. No asset rewrite, Blender,
continuous proof, dynamics, stability or reachability solving. Shared FK and
triangle algorithms retain floating-point tolerances; boundary touching may
be conservatively flagged by shared intersection tests.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'rl_exp/tools/runrecord'))
import binding  # noqa: E402

SUPPORT = __doc__
CHECKS = {'joint_limits', 'end_position', 'self_collision', 'ground', 'source_consistency', 'role_consistency',
          'source_geometry'}


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def text(value, label):
    need(isinstance(value, str) and bool(value.strip()), f'{label}: nonempty string required')
    return value


def finite_data(value):
    if isinstance(value, float):
        need(math.isfinite(value), 'nonfinite input number')
    elif isinstance(value, dict):
        for item in value.values():
            finite_data(item)
    elif isinstance(value, list):
        for item in value:
            finite_data(item)


def number(value, label, minimum=None):
    need(type(value) in (float, int) and math.isfinite(value), f'{label}: finite number required')
    need(minimum is None or value >= minimum, f'{label}: below minimum {minimum}')
    return float(value)


def vector(value, label, length=3):
    need(isinstance(value, list) and len(value) == length, f'{label}: length {length} required')
    return [number(x, label) for x in value]


def se3(value, label, np):
    need(isinstance(value, list) and len(value) == 4, f'{label}: 4x4 SE3 required')
    matrix = np.array([vector(row, label, 4) for row in value])
    need(np.array_equal(matrix[3], [0, 0, 0, 1]), f'{label}: homogeneous bottom row')
    rotate = matrix[:3, :3]
    need(np.allclose(rotate.T @ rotate, np.eye(3), atol=1e-10, rtol=0)
         and abs(float(np.linalg.det(rotate)) - 1) <= 1e-10, f'{label}: proper rotation required')
    return matrix


def distinct_names(value, label, nonempty=True):
    need(isinstance(value, list), f'{label}: list required')
    for name in value:
        text(name, label)
    need(len(set(value)) == len(value) and (bool(value) or not nonempty), f'{label}: duplicate/empty selection')
    return value


def role_map(value, names, label):
    need(isinstance(value, dict) and set(value) == set(names), f'{label}: exact joint coverage required')
    for role in value.values():
        text(role, label)


def bound_input(spec, base):
    need(isinstance(spec, dict), 'input binding must be an object')
    path = (base / text(spec.get('path'), 'input path')).resolve()
    approved = text(spec.get('sha256'), 'approved sha256')
    need(len(approved) == 64 and all(c in '0123456789abcdef' for c in approved), 'bare lowercase sha256 required')
    actual = binding.sha256_file(path)
    need(actual is not None and actual == approved, f'input hash mismatch or unreadable: {path}')
    return path, {'path': str(path), 'approved_sha256': approved, 'actual_sha256': actual}


def revalidate_inputs(report):
    records = ([report['inputs']['urdf']] if 'urdf' in report['inputs'] else [])
    records += report['inputs'].get('meshes', [])
    if 'role_evidence' in report['inputs']:
        records.append(report['inputs']['role_evidence'])
    if 'source_evidence' in report['inputs']:
        records.append(report['inputs']['source_evidence'])
    records += report['inputs'].get('source_visuals', [])
    records += report['inputs'].get('source_blends', [])
    for record in records:
        record['actual_sha256'] = binding.sha256_file(Path(record['path']))
        record['binding_state'] = ('pass' if record['actual_sha256'] == record['approved_sha256'] else 'fail')
    need(all(record['binding_state'] == 'pass' for record in records), 'bound input changed or unreadable')


def xml_vector(element, attribute, default=None):
    raw = element.get(attribute, default) if element is not None else default
    need(raw is not None, f'URDF missing {attribute}')
    return vector([float(x) for x in raw.split()], f'URDF {attribute}')


def validate_urdf(path):
    root = ET.parse(path).getroot()
    need(root.tag == 'robot', 'URDF robot element required')
    links, joints, parents, mesh_paths = {}, {}, {}, {}
    for link in root.findall('link'):
        name = text(link.get('name'), 'link name')
        need(name not in links, f'duplicate link name: {name}')
        links[name] = link
    need(bool(links), 'empty URDF links')
    for joint in root.findall('joint'):
        name = text(joint.get('name'), 'joint name')
        need(name not in joints, f'duplicate joint name: {name}')
        kind = joint.get('type')
        if kind not in ('revolute', 'fixed') or joint.find('mimic') is not None:
            raise NotImplementedError(f'unsupported joint type/mimic: {name}')
        origin = joint.find('origin')
        if origin is None or origin.get('xyz') is None:
            raise NotImplementedError(f'joint origin xyz required by shared reader: {name}')
        xml_vector(origin, 'xyz')
        if xml_vector(origin, 'rpy', '0 0 0') != [0., 0., 0.]:
            raise NotImplementedError(f'nonzero joint rpy: {name}')
        axis = joint.find('axis')
        if axis is not None:
            values = xml_vector(axis, 'xyz')
            squared = sum(x * x for x in values)
            need(math.isfinite(squared) and squared > 0, f'zero/unstable joint axis: {name}')
        if kind == 'revolute':
            need(axis is not None, f'missing revolute axis: {name}')
            limit = joint.find('limit')
            need(limit is not None, f'missing revolute limits: {name}')
            lo, hi = float(limit.get('lower')), float(limit.get('upper'))
            number(lo, 'joint lower'); number(hi, 'joint upper')
            need(lo <= hi, f'reversed joint limits: {name}')
        elif joint.find('limit') is not None:
            limit = joint.find('limit')
            number(float(limit.get('lower')), 'fixed lower')
            number(float(limit.get('upper')), 'fixed upper')
        parent, child = joint.find('parent'), joint.find('child')
        need(parent is not None and child is not None, f'missing parent/child: {name}')
        p, c = parent.get('link'), child.get('link')
        need(p in links and c in links, f'missing referenced link: {name}')
        need(c not in parents, f'duplicate child: {c}')
        parents[c] = (p, name)
        joints[name] = kind
    roots = set(links) - set(parents)
    need(len(roots) == 1, 'tree requires exactly one root (cycle/disconnected)')
    tree_root = next(iter(roots))
    for link in links:
        current, seen = link, set()
        while current in parents:
            need(current not in seen, f'tree cycle: {link}')
            seen.add(current)
            current = parents[current][0]
        need(current == tree_root, f'disconnected tree: {link}')
    for name, link in links.items():
        shapes = link.findall('collision')
        if len(shapes) > 1:
            raise NotImplementedError(f'multiple collision shapes: {name}')
        if not shapes:
            continue
        shape = shapes[0]
        origin = shape.find('origin')
        if (xml_vector(origin, 'xyz', '0 0 0') != [0., 0., 0.]
                or xml_vector(origin, 'rpy', '0 0 0') != [0., 0., 0.]):
            raise NotImplementedError(f'nonzero collision transform: {name}')
        geometry = shape.find('geometry')
        if geometry is None or len(geometry) != 1 or geometry[0].tag != 'mesh':
            raise NotImplementedError(f'single mesh geometry required: {name}')
        mesh = geometry[0]
        if xml_vector(mesh, 'scale', '1 1 1') != [1., 1., 1.]:
            raise NotImplementedError(f'nonunit mesh scale: {name}')
        filename = text(mesh.get('filename'), 'mesh filename')
        if '://' in filename or Path(filename).suffix.lower() != '.obj':
            raise NotImplementedError(f'local OBJ path required: {name}')
        mesh_paths[name] = (path.parent / filename).resolve()
    return set(links), joints, parents, tree_root, mesh_paths


def chain_path(parents, root, end):
    current, names, links = end, [], [end]
    while current != root:
        need(current in parents, f'{root} is not ancestor of {end}')
        current, name = parents[current]
        names.append(name)
        links.append(current)
    return list(reversed(names)), list(reversed(links))


def validate_obj(path):
    vertices, faces = 0, []
    for line in path.read_text(encoding='utf-8').splitlines():
        tokens = line.split()
        if not tokens or tokens[0].startswith('#'):
            continue
        if tokens[0] == 'v':
            if len(tokens) != 4 or not line.startswith('v '):
                raise NotImplementedError('OBJ vertices require three coordinates and v-space prefix')
            vector([float(x) for x in tokens[1:]], 'mesh vertex')
            vertices += 1
        elif tokens[0] == 'f':
            if len(tokens) != 4 or not line.startswith('f '):
                raise NotImplementedError('OBJ triangle positive-index faces required')
            indices = [int(x.split('/')[0]) for x in tokens[1:]]
            if min(indices) <= 0:
                raise NotImplementedError('OBJ negative/zero indices unsupported')
            faces.append(indices)
    need(vertices >= 4 and bool(faces), 'empty/insufficient solid OBJ')
    need(max(max(face) for face in faces) <= vertices, 'OBJ index out of range')


def mesh_prepare(path, np, csc, triangles, normalization=None):
    validate_obj(path)
    vertices, faces = csc.read_obj_faces(path)
    vertices, inverse = np.unique(vertices, axis=0, return_inverse=True)
    faces = inverse[faces]
    original_count = len(faces)
    # Same pole normalization as palm_motion_boundaries.Collision: weld exactly,
    # drop repeated indices, retain distinct collinear faces for closed topology.
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
    need(bool(len(faces)), 'empty solid mesh after pole normalization')
    need(len(np.unique(np.sort(faces, axis=1), axis=0)) == len(faces), 'duplicate mesh faces')
    tri = vertices[faces]
    double_area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    need(np.all((double_area == 0) | (double_area > 1e-14)) and np.any(double_area > 1e-14),
         'degenerate mesh triangles (nonzero double-area must exceed 1e-14 m^2)')
    need(set(faces.ravel()) == set(range(len(vertices))), 'unused mesh vertices')
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    keys, ids, counts = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
    need(np.all(counts == 2), 'non-watertight mesh')
    balance = np.bincount(ids, weights=np.where(edges[:, 0] < edges[:, 1], 1, -1), minlength=len(keys))
    need(np.all(balance == 0), 'inconsistent mesh winding')
    representatives = triangles.component_representatives(vertices, faces)
    if normalization is not None:
        normalization.update(original_faces=original_count, normalized_faces=len(faces),
                             dropped_repeated_index_faces=original_count - len(faces),
                             retained_collinear_faces=int(np.count_nonzero(double_area == 0)))
    return vertices, faces, representatives


def separating_face(va, fa, vb, fb, np):
    """Return a supporting-plane witness [m], never infer overlap from hulls.

    All vertices must be on opposite sides of a candidate face normal. This
    sufficient separation test also works for concave solids; failure to find
    a plane says nothing about penetration. Recenter before projection. The
    numerical envelope covers normalization/projection roundoff, not mechanical
    tolerance; features below this envelope are not resolved.
    """
    a, b = va - va[0], vb - va[0]
    extent = max(float(np.linalg.norm(a, axis=1).max()), float(np.linalg.norm(b, axis=1).max()))
    tolerance = 64 * np.finfo(float).eps * extent
    for vertices, faces in ((a, fa), (b, fb)):
        tri = vertices[faces]
        normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        lengths = np.linalg.norm(normals, axis=1)
        normals = normals[lengths > 0] / lengths[lengths > 0, None]
        normals = np.unique(normals, axis=0)
        for start in range(0, len(normals), 32):
            axes = normals[start:start + 32]
            pa, pb = a @ axes.T, b @ axes.T
            gaps = np.maximum(pb.min(0) - pa.max(0), pa.min(0) - pb.max(0))
            index = int(np.argmax(gaps))
            if gaps[index] >= -tolerance:
                return {'projected_gap_m': float(gaps[index]), 'numeric_tolerance_m': tolerance,
                        'axis_root': axes[index].tolist()}
    return None


def pair_evaluate(a, b, world, meshes, clearance, np, triangles):
    va, vb = world[a], world[b]
    lower = float(np.linalg.norm(np.maximum(0., np.maximum(va.min(0) - vb.max(0), vb.min(0) - va.max(0)))))
    # Positive separation OR an exact nonpenetrating AABB separating plane.
    # Overlapping boxes at clearance=0 must reach triangles/containment;
    # direct-joint pairs receive no inherited exemption.
    boxes_separate = bool(np.any(va.max(0) <= vb.min(0)) or np.any(vb.max(0) <= va.min(0)))
    if lower >= clearance and (lower > 0 or boxes_separate):
        return {'pair': [a, b], 'gap_lower_m': lower, 'method': 'aabb_lower_bound', 'state': 'pass'}
    _, fa, ra = meshes[a]
    _, fb, rb = meshes[b]
    if clearance == 0:
        witness = separating_face(va, fa, vb, fb, np)
        if witness is not None:
            return {'pair': [a, b], 'method': 'separating_face_plane', 'state': 'pass',
                    'separation_witness': witness}
    crosses = triangles.surface_crosses(va, fa, vb, fb) or triangles.surface_crosses(vb, fb, va, fa)
    contained = (any(triangles.inside(va[i], vb, fb) for i in ra)
                 or any(triangles.inside(vb[i], va, fa) for i in rb))
    gap = 0. if crosses or contained else triangles.surface_distance(va, fa, vb, fb)
    failed = crosses or contained or gap < clearance
    return {'pair': [a, b], 'gap_m': gap, 'intersects': bool(crosses), 'contained': bool(contained),
            'method': 'triangle_surface_solid_angle', 'state': 'fail' if failed else 'pass'}


def source_geometry_prepare(spec, base, path, report, root_link, np, csc):
    """Read saved/reopened pose samples once; bind consumed visuals and blend [m]."""
    from scipy.spatial import cKDTree
    evidence_path = (base / text(spec.get('path'), 'source evidence path')).resolve()
    need(evidence_path.is_file(), 'independent source evidence file absent')
    # Unlike path-only geometry readers, source JSON is decoded from these exact bytes.
    raw = evidence_path.read_bytes()
    digest = text(spec.get('sha256'), 'source evidence sha256')
    need(len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'bare lowercase sha256 required')
    record = {'path': str(evidence_path), 'approved_sha256': digest,
              'actual_sha256': binding.sha256_bytes(raw)}
    report['inputs']['source_evidence'] = record
    need(record['actual_sha256'] == digest, 'source evidence hash mismatch')
    source = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object)
    need(isinstance(source, dict), 'source evidence object required')
    fields = {'candidate_urdf', 'candidate_sha256', 'candidate_blend_sha256',
              'candidate_files_sha256', 'snapshots', 'builder_sha256'}
    if not fields <= set(source):
        raise NotImplementedError('source evidence requires saved/reopened pose-sample payload')
    finite_data(source)
    need((evidence_path.parent / text(source['candidate_urdf'], 'source candidate path')).resolve() == path,
         'source candidate path differs from actual URDF')
    need(source['candidate_sha256'] == report['inputs']['urdf']['approved_sha256'],
         'source evidence belongs to a different URDF')
    producer = text(source['builder_sha256'], 'source producer sha256')
    need(len(producer) == 64 and all(c in '0123456789abcdef' for c in producer), 'source producer bare sha256 required')
    files = source['candidate_files_sha256']
    need(isinstance(files, dict), 'source candidate file hashes object required')
    approved = {}
    for name, digest in files.items():
        file = (path.parent / text(name, 'candidate file')).resolve()
        need(file not in approved, 'duplicate resolved source candidate file')
        approved[file] = digest
    need(approved.get(path) == source['candidate_sha256'], 'source candidate file URDF binding absent')
    blends = [file for file in approved if file.suffix.lower() == '.blend'
              and approved[file] == source['candidate_blend_sha256']]
    need(len(blends) == 1, 'exact source candidate blend binding required')
    _, blend_record = bound_input({'path': str(blends[0]), 'sha256': approved[blends[0]]}, path.parent)
    report['inputs']['source_blends'] = [blend_record]
    report['source_provenance'] = {
        'evidence_sha256': record['approved_sha256'], 'producer_sha256': producer,
        'candidate_urdf': str(path), 'candidate_sha256': source['candidate_sha256'],
        'candidate_blend_sha256': source['candidate_blend_sha256'],
        'source_blend': source.get('source_blend'), 'source_urdf': source.get('source_urdf'),
        'input_sha256': source.get('input_sha256'),
        'independence': 'saved source observations; producer/origin independence remains auditor prerequisite'}
    revalidate_inputs(report)
    root = ET.parse(path).getroot()
    revalidate_inputs(report)
    visual_paths = {}
    for link in root.findall('link'):
        visuals = link.findall('visual')
        if not visuals:
            continue
        if len(visuals) != 1:
            raise NotImplementedError('source geometry supports one visual mesh per link')
        visual = visuals[0]
        geometries, origins = visual.findall('geometry'), visual.findall('origin')
        geometry = geometries[0] if geometries else None
        mesh = visual.find('geometry/mesh')
        if (len(geometries) != 1 or len(origins) > 1 or mesh is None or geometry is None or len(list(geometry)) != 1
                or xml_vector(visual.find('origin'), 'xyz', '0 0 0') != [0., 0., 0.]
                or xml_vector(visual.find('origin'), 'rpy', '0 0 0') != [0., 0., 0.]
                or xml_vector(mesh, 'scale', '1 1 1') != [1., 1., 1.]):
            raise NotImplementedError('source geometry requires zero-origin unit-scale visual OBJ')
        filename = text(mesh.get('filename'), 'source visual filename')
        if '://' in filename or Path(filename).suffix.lower() != '.obj':
            raise NotImplementedError('source geometry requires local visual OBJ')
        visual_paths[link.get('name')] = (path.parent / filename).resolve()
    need(bool(visual_paths), 'source geometry requires actual visual assets')
    records = {}
    for file in visual_paths.values():
        need(file in approved, f'unbound source visual mesh: {file}')
        if file not in records:
            _, records[file] = bound_input({'path': str(file), 'sha256': approved[file]}, path.parent)
    report['inputs']['source_visuals'] = list(records.values())
    trees = {}
    for name, file in visual_paths.items():
        revalidate_inputs(report)
        validate_obj(file)
        vertices = csc.read_obj(file)
        need(vertices.ndim == 2 and vertices.shape[1] == 3 and len(vertices) > 0
             and np.isfinite(vertices).all(), 'finite nonempty visual vertices required')
        trees[name] = cKDTree(vertices)
        revalidate_inputs(report)
    need(isinstance(source['snapshots'], list) and bool(source['snapshots']), 'source snapshots list required')
    snapshots = {}
    for snap in source['snapshots']:
        need(isinstance(snap, dict), 'source snapshot object required')
        name = text(snap['case'], 'source snapshot case')
        need(name not in snapshots, 'duplicate source snapshot case')
        snapshots[name] = snap
    inventory = None
    for snap in snapshots.values():
        objects = snap['meshes']
        need(isinstance(objects, dict) and bool(objects), 'source mesh samples object required')
        current = {}
        for name, sample in objects.items():
            text(name, 'source object name')
            need(isinstance(sample, dict), 'source object sample required')
            current[name] = (sample['link'], sample['vertex_count'], sample['indices'])
        need(inventory is None or current == inventory, 'source object inventory/link/count/indices changed across snapshots')
        inventory = current
    return snapshots, trees, root_link


def source_geometry_evaluate(params, case, poses, context, np):
    """Reuse pivot + nearest visual vertex readings, never infer full source poses [m]."""
    need(set(params) <= {'tolerance_m', 'source_cases', 'sparse_zero_reset', 'reset_reference'},
         'unknown source_geometry params')
    tolerance = number(params['tolerance_m'], 'source geometry tolerance_m', 0)
    need(context is not None, 'independent inputs.source_evidence required')
    if isinstance(context, dict):
        if context['state'] == 'not_supported':
            raise NotImplementedError(context['reason'])
        raise ValueError(context['reason'])
    snapshots, trees, root = context
    need(isinstance(params['source_cases'], dict), 'source_cases mapping required')
    snap_name = text(params['source_cases'][case['id']], 'selected source case')
    snap = snapshots[snap_name]
    q = snap['q_rad']
    need(isinstance(q, dict) and set(q) <= set(case['q_rad']), 'source q contains unknown joints')
    q = {n: number(v, 'source q_rad') for n, v in q.items()}
    sparse = params.get('sparse_zero_reset', False)
    need(type(sparse) is bool, 'sparse_zero_reset must be boolean')
    if sparse:
        text(params['reset_reference'], 'explicit source zero-reset provenance required')
        q = {n: q.get(n, 0.) for n in case['q_rad']}
    need(q == case['q_rad'], 'source effective q does not match complete case q')
    pivots = snap['pivots']
    need(isinstance(pivots, dict) and set(pivots) == set(poses), 'source pivots require every actual link')
    pivots = {n: np.array(vector(p, f'source pivot {n}')) for n, p in pivots.items()}
    # Shared exporter convention: world-neutral orientations, base head subtracted.
    base_origin = pivots[root]
    root_pose = se3(case['root_transform'], 'source case root_transform', np)
    link_rows = {}
    for name, point in pivots.items():
        expected = root_pose[:3, :3] @ (point - base_origin) + root_pose[:3, 3]
        actual = poses[name][:3, 3]
        error = float(np.linalg.norm(actual - expected))
        link_rows[name] = {'actual_m': actual.tolist(), 'source_world_m': point.tolist(),
                           'expected_m': expected.tolist(), 'error_m': error}
    objects = snap['meshes']
    need(isinstance(objects, dict) and bool(objects), 'source mesh samples object required')
    need({r['link'] for r in objects.values() if isinstance(r, dict)} == set(trees),
         'source sample links must cover every actual visual asset')
    object_rows = {}
    for name, sample in objects.items():
        text(name, 'source object name')
        need(isinstance(sample, dict) and sample['link'] in trees, 'source object link mismatch')
        count, indices, points = sample['vertex_count'], sample['indices'], sample['points']
        need(type(count) is int and count > 0, 'source vertex_count positive integer required')
        need(isinstance(indices, list) and bool(indices) and all(type(i) is int and 0 <= i < count for i in indices)
             and len(set(indices)) == len(indices), 'source sample indices duplicate/out of range')
        need(isinstance(points, list) and len(points) == len(indices), 'source points/indices coverage mismatch')
        points = np.array([vector(p, f'source sample {name}') for p in points])
        frame = poses[sample['link']]
        expected = (points - base_origin) @ root_pose[:3, :3].T + root_pose[:3, 3]
        local = (expected - frame[:3, 3]) @ frame[:3, :3]
        distances, _ = trees[sample['link']].query(local)
        index = int(np.argmax(distances))
        object_rows[name] = {'link': sample['link'], 'source_vertex_count': count, 'samples_checked': len(points),
                             'max_error_m': float(distances[index]), 'worst_source_index': indices[index],
                             'worst_source_world_m': points[index].tolist(),
                             'state': 'pass' if float(distances[index]) <= tolerance else 'fail'}
    passed = all(r['error_m'] <= tolerance for r in link_rows.values()) and all(r['state'] == 'pass' for r in object_rows.values())
    return ('pass' if passed else 'fail'), {
        'source_snapshot': snap_name, 'effective_source_q_rad': q, 'sparse_zero_reset': sparse,
        'reset_reference': params.get('reset_reference'), 'root_transform': case['root_transform'],
        'source_base_origin_m': base_origin.tolist(), 'tolerance_m': tolerance,
        'links': link_rows, 'objects': object_rows, 'visual_links_checked': len(trees),
        'samples_checked': sum(r['samples_checked'] for r in object_rows.values()),
        'scope': 'independent pivots + sampled visual geometry; nearest vertex, not one-to-one; '
                 'no full orientation, role, axis correctness, mass, dynamics or continuous proof'}


def evaluate(check, params, case, selected, chains, model, poses, world, meshes, pairs, np, triangles,
             collision_world=None, role_context=None, source_context=None):
    q = case['q_rad']
    need(isinstance(params, dict), 'check params object required')
    if check == 'joint_limits':
        need(not params, 'joint_limits params must be empty')
        bounds = {n: {'q_rad': q[n], 'lower_rad': s['limits'][0], 'upper_rad': s['limits'][1]}
                  for n, s in model['joints'].items() if n in q}
        return ('pass' if all(s['lower_rad'] <= s['q_rad'] <= s['upper_rad'] for s in bounds.values()) else 'fail'), {'joints': bounds}
    if check == 'source_geometry':
        return source_geometry_evaluate(params, case, poses, source_context, np)
    if check == 'end_position':
        need(set(params) <= {'expected_m', 'tolerance_m'}, 'unknown end_position params')
        tolerance = number(params['tolerance_m'], 'tolerance_m', 0)
        actual = {}
        for name in selected:
            expected = np.array(vector(params['expected_m'][case['id']][name], 'expected_m'))
            point = poses[chains[name]['end_link']][:3, 3]
            error = float(np.linalg.norm(point - expected))
            actual[name] = {'actual_m': point.tolist(), 'expected_m': expected.tolist(), 'error_m': error}
        return ('pass' if all(s['error_m'] <= tolerance for s in actual.values()) else 'fail'), {'chains': actual, 'tolerance_m': tolerance}
    if check == 'self_collision':
        need(set(params) <= {'clearance_m', 'contact_pairs'}, 'unknown self_collision params')
        clearance = number(params['clearance_m'], 'clearance_m', 0)
        permissions = params.get('contact_pairs', [])
        need(isinstance(permissions, list), 'contact_pairs list required')
        contact_pairs = {}
        for item in permissions:
            need(isinstance(item, dict) and set(item) == {'pair', 'reason'}, 'contact pair/reason required')
            pair = distinct_names(item['pair'], 'contact pair')
            need(len(pair) == 2, 'contact pair requires two entities')
            key = tuple(sorted(pair))
            need(key in pairs, 'contact pair must be checked, not excluded or unknown')
            need(key not in contact_pairs, 'duplicate contact pair')
            contact_pairs[key] = text(item['reason'], 'contact reason')
        points = world if collision_world is None else collision_world
        rows = []
        for a, b in pairs:
            margin = 0. if (a, b) in contact_pairs else clearance
            result = pair_evaluate(a, b, points, meshes, margin, np, triangles)
            result['required_clearance_m'] = margin
            if (a, b) in contact_pairs:
                result['contact_permission'] = contact_pairs[(a, b)]
            rows.append(result)
        if len(meshes) == 1:
            return 'not_applicable', {'reason': 'one checked collision entity: no possible pair', 'pairs': rows}
        return ('fail' if any(r['state'] == 'fail' for r in rows) else 'pass'), {'pairs': rows, 'clearance_m': clearance}
    if check == 'role_consistency':
        need(not params, 'role_consistency params must be empty')
        need(role_context is not None, 'independent inputs.role_evidence required')
        declared, evidence = role_context
        mismatches = {name: {'declared': role, 'expected': evidence['joint_roles'][name]}
                      for name, role in declared.items() if role != evidence['joint_roles'][name]}
        return ('fail' if mismatches else 'pass'), {
            'mismatches': mismatches, 'approved_by': evidence['approved_by'], 'reference': evidence['reference'],
            'scope': 'all movable joint role labels only; physical axes/entity motion not certified'}
    if check == 'ground':
        need(set(params) <= {'normal', 'height_m', 'min_gap_m', 'allowed_contacts'}, 'unknown ground params')
        normal = np.array(vector(params['normal'], 'ground normal'))
        need(abs(float(np.linalg.norm(normal)) - 1) <= 1e-10, 'ground normal must be unit')
        height = number(params['height_m'], 'height_m')
        gap = number(params['min_gap_m'], 'min_gap_m', 0)
        contacts = params['allowed_contacts']
        need(isinstance(contacts, dict), 'allowed_contacts object required')
        declared = {link for chain in chains.values() for link in chain['contact_links']}
        need(set(contacts) <= declared and set(contacts) <= set(world), 'undeclared contact link')
        rows = {}
        for name, vertices in world.items():
            minimum = float(np.min(vertices @ normal - height))
            if name in contacts:
                lo = -number(contacts[name]['max_penetration_m'], 'max_penetration_m', 0)
                hi = number(contacts[name]['max_gap_m'], 'max_gap_m', 0)
                passed = lo <= minimum <= hi
            else:
                lo, hi, passed = gap, None, minimum >= gap
            rows[name] = {'minimum_m': minimum, 'lower_m': lo, 'upper_m': hi, 'state': 'pass' if passed else 'fail'}
        return ('pass' if all(r['state'] == 'pass' for r in rows.values()) else 'fail'), {'links': rows, 'normal': normal.tolist(), 'height_m': height}
    if check == 'source_consistency':
        need(set(params) <= {'approved_by', 'reference', 'tolerance_m', 'tolerance_rad', 'snapshots'},
             'unknown source_consistency params')
        text(params['approved_by'], 'snapshot approved_by'); text(params['reference'], 'snapshot reference')
        mt = number(params['tolerance_m'], 'snapshot tolerance_m', 0)
        rt = number(params['tolerance_rad'], 'snapshot tolerance_rad', 0)
        snap = params['snapshots'][case['id']]
        need(snap['q_rad'] == q and snap['root_transform'] == case['root_transform'], 'snapshot q/root do not match case')
        need(set(snap['link_poses']) == set(poses), 'snapshot requires every actual link')
        rows = {}
        for name, actual in poses.items():
            expected = se3(snap['link_poses'][name], 'snapshot pose', np)
            distance = float(np.linalg.norm(actual[:3, 3] - expected[:3, 3]))
            rotation = actual[:3, :3].T @ expected[:3, :3]
            angle = float(np.arccos(np.clip((np.trace(rotation) - 1) / 2, -1, 1)))
            rows[name] = {'position_error_m': distance, 'rotation_error_rad': angle}
        return ('pass' if all(r['position_error_m'] <= mt and r['rotation_error_rad'] <= rt for r in rows.values()) else 'fail'), {'links': rows, 'approved_by': params['approved_by'], 'reference': params['reference']}
    raise NotImplementedError(f'unknown check: {check}')


def run(config: dict, config_dir: Path, max_cases: int | None = None) -> dict:
    """Evaluate approved sampled poses [m, rad]; return JSON-safe, fail-closed report."""
    report = {'schema': 'body_precheck_v1', 'status': 'fail', 'support': SUPPORT,
              'inputs': {}, 'coverage': {'whole_machine': 'not_evaluated', 'role_semantics': 'not_evaluated',
                                        'source_pose_consistency': 'not_evaluated', 'source_geometry': 'not_evaluated'},
              'results': [], 'counters': {'cases_evaluated': 0, 'pairs_evaluated': 0},
              'code_sha256': {'body_precheck': binding.sha256_file(HERE)}}
    try:
        need(isinstance(config, dict), 'config object required')
        finite_data(config)
        inputs, body, tasks = config['inputs'], config['body'], config['tasks']
        text(inputs['identity'], 'identity'); need(inputs['units'] == 'SI', 'units must be SI')
        text(inputs['threshold_basis']['approved_by'], 'threshold approved_by')
        text(inputs['threshold_basis']['reference'], 'threshold reference')
        report['inputs']['identity'] = inputs['identity']
        report['inputs']['threshold_basis'] = inputs['threshold_basis']
        path, record = bound_input(inputs['urdf'], config_dir)
        report['inputs']['urdf'] = record
        approved_meshes = {}
        need(isinstance(inputs['meshes'], list), 'meshes binding list required')
        for spec in inputs['meshes']:
            mesh, record = bound_input(spec, config_dir)
            need(mesh not in approved_meshes, 'duplicate mesh binding')
            approved_meshes[mesh] = record
        report['inputs']['meshes'] = list(approved_meshes.values())
        revalidate_inputs(report)
        links, kinds, parents, root, mesh_paths = validate_urdf(path)
        revalidate_inputs(report)
        movable = {name for name, kind in kinds.items() if kind == 'revolute'}
        chains = body['chains']
        need(isinstance(chains, dict) and bool(chains), 'nonempty chains required')
        covered, chain_records, joint_roles = set(), {}, {}
        for name, chain in chains.items():
            text(name, 'chain id')
            start, end = chain['root_link'], chain['end_link']
            need(start in links and end in links and start != end, f'invalid chain endpoints: {name}')
            names, members = chain_path(parents, start, end)
            moving = set(names) & movable
            need(bool(moving), f'chain without movable joints: {name}')
            role_map(chain['joint_roles'], moving, f'{name} joint_roles')
            for joint, role in chain['joint_roles'].items():
                need(joint not in joint_roles or joint_roles[joint] == role, f'conflicting joint role: {joint}')
                joint_roles[joint] = role
            contacts = distinct_names(chain['contact_links'], 'contact_links', False)
            need(set(contacts) <= set(members) & set(mesh_paths), f'contact links outside chain/geometry: {name}')
            covered.update(moving)
            chain_records[name] = {**chain, 'actual_joints': names, 'actual_links': members}
        role_map(body['other_joints'], movable - covered, 'other_joints')
        role_context = None
        if 'role_evidence' in inputs:
            evidence_path, record = bound_input(inputs['role_evidence'], config_dir)
            report['inputs']['role_evidence'] = record
            raw = evidence_path.read_bytes()
            need(binding.sha256_bytes(raw) == record['approved_sha256'], 'role evidence changed while reading')
            evidence = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object)
            need(isinstance(evidence, dict), 'role evidence object required')
            finite_data(evidence)
            need(evidence['schema'] == 'body_precheck_roles_v1', 'unsupported role evidence schema')
            need(evidence['urdf_sha256'] == report['inputs']['urdf']['approved_sha256'],
                 'role evidence belongs to a different URDF')
            text(evidence['approved_by'], 'role evidence approved_by')
            text(evidence['reference'], 'role evidence reference')
            role_map(evidence['joint_roles'], movable, 'source joint_roles')
            role_context = ({**joint_roles, **body['other_joints']}, evidence)
            revalidate_inputs(report)
        entities = distinct_names(body['collision_entities'], 'collision_entities')
        exclusions = body['excluded_entities']
        need(isinstance(exclusions, list), 'excluded_entities list required')
        excluded = {}
        for item in exclusions:
            link = text(item['link'], 'excluded link'); text(item['reason'], 'excluded reason')
            need(link not in excluded, 'duplicate entity exclusion')
            excluded[link] = item['reason']
        need(set(entities).isdisjoint(excluded) and set(entities) | set(excluded) == set(mesh_paths),
             'exact collision entity coverage required')
        need(set(approved_meshes) == {mesh_paths[n] for n in entities}, 'approved meshes must exactly match consumed meshes')
        allowed = {}
        need(isinstance(body['allowed_pairs'], list), 'allowed_pairs list required')
        for item in body['allowed_pairs']:
            pair = distinct_names(item['pair'], 'allowed pair')
            need(len(pair) == 2 and set(pair) <= set(entities), 'allowed pair requires two checked entities')
            text(item['reason'], 'allowed pair reason')
            key = tuple(sorted(pair)); need(key not in allowed, 'duplicate allowed pair')
            allowed[key] = item['reason']
        pairs = [p for p in itertools.combinations(sorted(entities), 2) if p not in allowed]
        cases = tasks['cases']; requirements = tasks['requirements']
        need(isinstance(cases, list) and bool(cases), 'nonempty cases required')
        need(isinstance(requirements, list) and bool(requirements), 'nonempty requirements required')
        case_ids, req_ids = set(), set()
        for case in cases:
            cid = text(case['id'], 'case id'); text(case['phase'], 'case phase')
            need(cid not in case_ids, 'duplicate case id'); case_ids.add(cid)
            need(isinstance(case['q_rad'], dict) and set(case['q_rad']) == movable, 'complete movable q_rad required')
            for angle in case['q_rad'].values():
                number(angle, 'q_rad')
        for req in requirements:
            rid = text(req['id'], 'requirement id'); text(req['check'], 'requirement check')
            need(rid not in req_ids, 'duplicate requirement id'); req_ids.add(rid)
            need(type(req['required']) is bool, 'required must be boolean')
            need(set(distinct_names(req['cases'], 'requirement cases')) <= case_ids, 'unknown selected case')
            need(set(distinct_names(req['chains'], 'requirement chains')) <= set(chains), 'unknown selected chain')
            need(not ({'not_applicable', 'state', 'reason'} & set(req)), 'caller NA/state override prohibited')
        need(any(r['required'] for r in requirements), 'at least one mandatory requirement required')
        need(max_cases is None or type(max_cases) is int and max_cases >= 0, 'max_cases must be nonnegative integer')
        # Import heavy shared consumers only after identity/tree/coverage validation.
        import numpy as np
        sys.path.insert(0, str(REPO / 'rl_exp/tools/verify'))
        import check_self_collision as csc
        import palm_motion_boundaries as triangles
        for module in (csc, triangles, triangles.gait, binding):
            report['code_sha256'][module.__name__] = binding.sha256_file(Path(module.__file__))
        for case in cases:
            se3(case['root_transform'], 'root_transform', np)
        revalidate_inputs(report)
        model = csc.load_urdf(path)
        revalidate_inputs(report)
        meshes = {}
        report['mesh_normalization'] = {}
        for name in entities:
            revalidate_inputs(report)
            normalization = report['mesh_normalization'][name] = {}
            meshes[name] = mesh_prepare(mesh_paths[name], np, csc, triangles, normalization)
            revalidate_inputs(report)
        source_context = None
        if any(r['check'] == 'source_geometry' for r in requirements) and 'source_evidence' in inputs:
            try:
                need(isinstance(inputs['source_evidence'], dict), 'source evidence binding object required')
                source_context = source_geometry_prepare(inputs['source_evidence'], config_dir, path, report, root, np, csc)
            except (NotImplementedError, ValueError, KeyError, TypeError, OSError) as exc:
                source_context = {'state': 'not_supported' if isinstance(exc, NotImplementedError) else 'not_evaluated',
                                  'reason': f'{type(exc).__name__}: {exc}'}
        report['body'] = {'root_link': root, 'chains': chain_records, 'other_joints': body['other_joints'],
                          'movable_joints': sorted(movable), 'collision_entities': entities,
                          'excluded_entities': exclusions, 'checked_pairs': [list(p) for p in pairs],
                          'excluded_pairs': [{'pair': list(p), 'reason': reason} for p, reason in allowed.items()]}
        if allowed:
            report['warnings'] = ['body.allowed_pairs is a legacy whole-pair exclusion, not contact validation; '
                                  'use self_collision.params.contact_pairs for touch-only permission']
        report['cases'] = cases
        report['requirements'] = requirements
        report['max_cases'] = max_cases
        coverage = {}
        for index, case in enumerate(cases):
            cid = case['id']
            required = [r for r in requirements if r['required'] and cid in r['cases']]
            whole = {r['check'] for r in required if set(r['chains']) == set(chains)}
            missing = sorted({'joint_limits', 'self_collision'} - whole)
            coverage[cid] = {'missing_required_checks': missing,
                             'required_selections': [{'id': r['id'], 'check': r['check'], 'chains': r['chains']}
                                                     for r in required],
                             'state': 'pass' if not missing else 'fail'}
            budget = max_cases is not None and index >= max_cases
            if not budget:
                root_pose = se3(case['root_transform'], 'root_transform', np)
                local_poses = {n: csc.fk(model['joints'], n, case['q_rad']) for n in links}
                poses = {n: root_pose @ pose for n, pose in local_poses.items()}
                need(all(np.isfinite(p).all() for p in poses.values()), 'nonfinite FK result')
                world = {n: vertices @ poses[n][:3, :3].T + poses[n][:3, 3] for n, (vertices, _, _) in meshes.items()}
                collision_world = {n: vertices @ local_poses[n][:3, :3].T + local_poses[n][:3, 3]
                                   for n, (vertices, _, _) in meshes.items()}
                report['counters']['cases_evaluated'] += 1
            for req in requirements:
                if cid not in req['cases']:
                    continue
                row = {'id': req['id'], 'check': req['check'], 'required': req['required'],
                       'case_id': cid, 'phase': case['phase'], 'chains': req['chains']}
                try:
                    if budget:
                        row.update(state='not_evaluated', reason='max_cases budget exhausted')
                    elif req['check'] not in CHECKS:
                        row.update(state='not_supported', reason=f"unknown check: {req['check']}")
                    else:
                        state, detail = evaluate(req['check'], req['params'], case, req['chains'], chains,
                                                 model, poses, world, meshes, pairs, np, triangles,
                                                 collision_world=collision_world, role_context=role_context,
                                                 source_context=source_context)
                        finite_data(detail)
                        row.update(state=state, detail=detail)
                        if req['check'] == 'self_collision':
                            report['counters']['pairs_evaluated'] += len(detail['pairs'])
                except NotImplementedError as exc:
                    row.update(state='not_supported', reason=str(exc))
                except (KeyError, TypeError, ValueError, OverflowError) as exc:
                    row.update(state='not_evaluated', reason=f'invalid/missing check data: {exc}')
                report['results'].append(row)
        report['coverage'] = {'whole_machine': 'pass' if all(c['state'] == 'pass' for c in coverage.values()) else 'fail',
                              'cases': coverage, 'movable_role_coverage': 'pass', 'collision_entity_coverage': 'pass'}
        for label, method in (('role_semantics', 'role_consistency'), ('source_pose_consistency', 'source_consistency'),
                              ('source_geometry', 'source_geometry')):
            states = []
            for cid in case_ids:
                rows = [r for r in report['results'] if r['case_id'] == cid and r['check'] == method
                        and set(r['chains']) == set(chains)]
                states.append('fail' if any(r['state'] == 'fail' for r in rows) else
                              'pass' if rows and all(r['state'] == 'pass' for r in rows) else 'not_evaluated')
            report['coverage'][label] = ('fail' if 'fail' in states else
                                         'pass' if all(s == 'pass' for s in states) else 'not_evaluated')
        revalidate_inputs(report)
        mandatory = [r for r in report['results'] if r['required']]
        report['status'] = ('pass' if mandatory and all(r['state'] in ('pass', 'not_applicable') for r in mandatory)
                            and report['coverage']['whole_machine'] == 'pass' else 'fail')
    except (NotImplementedError, ValueError, KeyError, TypeError, OSError, ET.ParseError, ImportError,
            OverflowError, RecursionError, AssertionError) as exc:
        state = 'not_supported' if isinstance(exc, NotImplementedError) else 'not_evaluated'
        report['reason'] = f'{type(exc).__name__}: {exc}'
        report['input_state'] = state
        try:
            revalidate_inputs(report)
        except ValueError as changed:
            report['reason'] += f'; {changed}'
        report['status'] = 'fail'
        report['coverage']['whole_machine'] = state
        if isinstance(config, dict):
            pending = config.get('tasks', {})
            pending = pending.get('requirements', []) if isinstance(pending, dict) else []
            if isinstance(pending, list):
                for req in pending:
                    if isinstance(req, dict):
                        report['results'].append({'id': req.get('id') if isinstance(req.get('id'), str) else None,
                                                  'check': req.get('check') if isinstance(req.get('check'), str) else None,
                                                  'required': req.get('required') if type(req.get('required')) is bool else True,
                                                  'state': state, 'reason': report['reason']})
    return report


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, f'duplicate JSON key: {key}')
        result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max_cases', type=int)
    args = parser.parse_args()
    output = args.output.resolve()
    roots = [(REPO / 'rl_exp/out').resolve(), Path(tempfile.gettempdir()).resolve()]
    if not output.parent.is_dir() or output.exists() or not any(output.is_relative_to(r) for r in roots):
        print('output must be fresh with existing parent under rl_exp/out or system temp', file=sys.stderr)
        return 2
    try:
        # Reserve exclusively before reading input; never overwrite a competing writer.
        with output.open('x', encoding='utf-8') as handle:
            digest = None
            try:
                raw = args.config.read_bytes()
                digest = binding.sha256_bytes(raw)
                config = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object)
                report = run(config, args.config.resolve().parent, args.max_cases)
            except (OSError, ValueError, RecursionError) as exc:
                report = {'schema': 'body_precheck_v1', 'status': 'fail', 'input_state': 'not_evaluated',
                          'reason': f'input read/JSON error: {exc}', 'results': [],
                          'coverage': {'whole_machine': 'not_evaluated'},
                          'code_sha256': {'body_precheck': binding.sha256_file(HERE)}}
            report['config'] = {'path': str(args.config.resolve()), 'sha256': digest}
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write('\n')
    except (OSError, ValueError) as exc:
        print(f'report write failed: {exc}', file=sys.stderr)
        return 2
    print(f"{report['status']}: {output}")
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
