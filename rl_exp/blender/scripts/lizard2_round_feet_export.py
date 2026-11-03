# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Export the hash-bound round skeleton after full source correspondence checks.

Blender --background --factory-startup --python-exit-code 1 --python <script> --
--out <fresh rl_exp/out/...>. SI units. No physics or USD conversion.
Axes are inherited from the verified formal URDF, not inferred from bone Y axes.
"""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rl_exp.tools.diagnose.lizard2_round_feet import SOURCE, FEET, build_tree, validate_tree
from rl_exp.tools.runrecord.binding import sha256_file
from types import SimpleNamespace

# Reuse pure FK/OBJ functions without importing simulation task registrations.
GEOMETRY_PATH = ROOT / 'rl_exp/tools/verify/check_self_collision.py'
_geometry_ast = ast.parse(GEOMETRY_PATH.read_text(encoding='utf-8'))
_geometry_functions = [n for n in _geometry_ast.body if isinstance(n, ast.FunctionDef)
                       and n.name in {'load_urdf', 'read_obj', 'chain_up', 'fk'}]
require_names = {n.name for n in _geometry_functions}
if require_names != {'load_urdf', 'read_obj', 'chain_up', 'fk'}:
    raise ValueError('shared FK helper contract changed')
_geometry_namespace = {'np': np, 'ET': ET, 'pathlib': __import__('pathlib')}
exec(compile(ast.Module(body=_geometry_functions, type_ignores=[]),
             str(GEOMETRY_PATH), 'exec'), _geometry_namespace)
geometry = SimpleNamespace(**{n: _geometry_namespace[n] for n in require_names})
from lizard2_round_feet_candidate import vertices

SKELETON = ROOT / 'rl_exp/out/lizard2_round_feet/skeleton02/lizard2_round_feet.blend'
SKELETON_SHA = '4e3073d1389db9875a0dd4db4e7ec4ef7a56b5231d7df6fc12edc4c57660cf07'
FORMAL_SHA = 'e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00'
PARENTS = dict(zip(FEET, ('lf_elbow', 'rf_elbow', 'rl_knee', 'rr_knee')))
TOL = 1e-5
RADIUS = .08


def require(condition, message):
    if not condition:
        raise ValueError(message)


def open_scene(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    arm, = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    bpy.context.view_layer.update()
    require(not arm.constraints and not arm.animation_data, 'animated/constrained armature')
    require(all(not b.constraints and b.matrix_basis == Matrix.Identity(4)
                for b in arm.pose.bones), 'non-neutral/constrained bones')
    return arm


def capture(arm):
    """Capture every frame, head, tail and evaluated world vertex [m]."""
    meshes = {}
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        require(obj.parent == arm and obj.parent_type == 'BONE'
                and obj.parent_bone in arm.data.bones, 'unbound mesh: ' + obj.name)
        require(not obj.constraints and not obj.animation_data, 'animated mesh: ' + obj.name)
        meshes[obj.name] = (obj.parent_bone, np.array(vertices(obj)),
                           tuple(tuple(p.vertices) for p in obj.data.polygons))
    return {
        'bones': {b.name: (b.parent.name if b.parent else None,
                          np.array(arm.matrix_world @ b.matrix_local),
                          np.array(arm.matrix_world @ b.tail_local)) for b in arm.data.bones},
        'meshes': meshes,
    }


def compare_upstream(reference, actual):
    expected = set(reference['bones']) - set(FEET)
    require(set(actual['bones']) == expected, 'bone inventory mismatch')
    error = 0.
    for name in expected:
        parent, frame, tail = reference['bones'][name]
        p, f, t = actual['bones'][name]
        require(parent == p, 'bone parent: ' + name)
        require(np.max(np.abs(frame - f)) < TOL and np.linalg.norm(tail - t) < TOL,
                'bone frame/head/tail: ' + name)
    old = {n: row for n, row in reference['meshes'].items() if row[0] not in FEET}
    new = {n: row for n, row in actual['meshes'].items() if not n.startswith('round_')}
    require(old.keys() == new.keys(), 'upstream mesh inventory')
    for name, (parent, points, faces) in old.items():
        p, actual_points, actual_faces = new[name]
        require(parent == p and points.shape == actual_points.shape and faces == actual_faces,
                'mesh ownership/topology: ' + name)
        gap = float(np.max(np.linalg.norm(points - actual_points, axis=1)))
        error = max(error, gap)
        require(gap < TOL, 'world mesh vertices: ' + name)
    return error


def check_spheres(arm, centers):
    """Reject wrong rigid binding, center or radius [m], including evaluated shape."""
    for foot, parent in PARENTS.items():
        obj = bpy.data.objects['round_' + foot]
        require(obj.parent == arm and obj.parent_type == 'BONE' and obj.parent_bone == parent,
                'sphere binding: ' + foot)
        require(not obj.modifiers and not obj.constraints and not obj.vertex_groups
                and not obj.animation_data and not obj.data.shape_keys,
                'sphere deformation: ' + foot)
        points = np.array(vertices(obj))
        center = centers[foot]
        require(np.linalg.norm(np.array(obj.matrix_world.translation) - center) < TOL,
                'sphere center: ' + foot)
        require(np.max(np.abs(np.linalg.norm(points - center, axis=1) - RADIUS)) < TOL,
                'sphere radius: ' + foot)
        require(np.max(np.abs(points.mean(axis=0) - center)) < TOL,
                'sphere geometric center: ' + foot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--elbow_limit', type=float, help='symmetric elbow limit [rad]; no source expansion')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    out = args.out.resolve()
    require(out.is_relative_to((ROOT / 'rl_exp/out').resolve()) and not out.exists(),
            'output must be fresh under rl_exp/out')
    bindings = {}

    def bind(path, expected=None):
        path = Path(path).resolve()
        value = sha256_file(path)
        require(expected is None or value == expected, 'SHA256 mismatch: ' + str(path))
        bindings[str(path)] = value
        return path

    bind(SKELETON, SKELETON_SHA)
    bind(SOURCE, FORMAL_SHA)
    build_path = bind(SKELETON.parent / 'build.json')
    build = json.loads(build_path.read_text(encoding='utf-8'))
    require(Path(build['candidate']).resolve() == SKELETON.resolve()
            and build['candidate_sha256'] == SKELETON_SHA
            and build['sphere_radius_m'] == RADIUS, 'skeleton build binding')
    two_axis = bind(build['source'], build['source_sha256'])
    provenance = json.loads(bind(two_axis.with_suffix('.json')).read_text(encoding='utf-8'))
    require(Path(provenance['candidate']).resolve() == two_axis
            and provenance['candidate_sha256'] == bindings[str(two_axis)], 'two-axis binding')
    original = bind(provenance['source'], provenance['source_sha256'])
    require(provenance['source_sha256'] ==
            'beeac4c09726260bf392a6ecc81a04ebcf9b54a210416493bbb2689c4909cdea',
            'unexpected original formal blend')
    for path in (__file__, Path(__file__).with_name('lizard2_round_feet_candidate.py'),
                 ROOT / 'rl_exp/tools/diagnose/lizard2_round_feet.py',
                 GEOMETRY_PATH,
                 ROOT / 'rl_exp/tools/runrecord/binding.py'):
        bind(path)
    require(bindings[str(Path(__file__).with_name('lizard2_round_feet_candidate.py'))]
            == build['script_sha256'], 'skeleton builder hash mismatch')
    model = geometry.load_urdf(SOURCE)
    formal = ET.parse(SOURCE)
    for joint in formal.getroot().findall('joint'):
        require(joint.get('type') == 'revolute'
                and all(float(v) == 0 for v in joint.find('origin').get('rpy').split()),
                'unsupported formal joint/FK rotation')
    joints = {j.find('child').get('link'): j for j in formal.getroot().findall('joint')}
    arm = open_scene(original)
    reference = capture(arm)
    require(set(reference['bones']) == set(model['links']), 'formal Blender bone inventory')
    root_offset = reference['bones']['base_link'][1][:3, 3]
    for name, (parent, frame, tail) in reference['bones'].items():
        require(parent == (joints[name].find('parent').get('link') if name in joints else None),
                'formal parent mismatch: ' + name)
        require(np.linalg.norm(frame[:3, 3] - root_offset
                               - geometry.fk(model['joints'], name, {})[:3, 3]) < TOL,
                'formal pivot/FK mismatch: ' + name)
    # Reuse only the existing generator's pure mesh helper and ball classification.
    # Importing that script would execute its export CLI and mutate output trees.
    generator = bind(Path(__file__).with_name('generate_urdf.py'))
    parsed = ast.parse(generator.read_text(encoding='utf-8'))
    selected = [n for n in parsed.body if
                isinstance(n, ast.FunctionDef) and n.name == 'build_bmesh' or
                isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'BALL_MESHES'
                                                 for t in n.targets)]
    require(len(selected) == 2, 'generator mesh helper contract changed')
    namespace = {'bmesh': bmesh, 'depsgraph': bpy.context.evaluated_depsgraph_get()}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(generator), 'exec'), namespace)
    mesh_error = 0.
    mesh_count = 0
    for link in formal.getroot().findall('link'):
        name = link.get('name')
        objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.parent_bone == name]
        for kind in ('visual', 'collision'):
            chosen = [o for o in objects if kind == 'visual' or o.name not in namespace['BALL_MESHES']]
            shapes = link.findall(kind)
            require(len(shapes) == bool(chosen), 'formal mesh coverage: ' + name)
            if not chosen:
                continue
            origin = shapes[0].find('origin')
            require(all(float(v) == 0 for k in ('xyz', 'rpy') for v in origin.get(k).split()),
                    'nonzero mesh origin')
            relative = Path(shapes[0].find('geometry/mesh').get('filename'))
            path = (SOURCE.parent / relative).resolve()
            require(not relative.is_absolute() and path.is_relative_to(SOURCE.parent.resolve()),
                    'nonlocal formal mesh')
            bind(path)
            expected = geometry.read_obj(path)
            bm = namespace['build_bmesh'](chosen, Vector(reference['bones'][name][1][:3, 3]), kind == 'visual')
            try:
                actual = np.array([tuple(v.co) for face in bm.faces
                                   for i in range(1, len(face.verts) - 1)
                                   for v in (face.verts[0], face.verts[i], face.verts[i + 1])])
            finally:
                bm.free()
            require(actual.shape == expected.shape, 'formal mesh vertex coverage: ' + name)
            gap = float(np.max(np.linalg.norm(actual - expected, axis=1)))
            require(gap < TOL, f'formal mesh vertices: {name} {kind} {gap}')
            mesh_error = max(mesh_error, gap)
            mesh_count += 1
    arm = open_scene(SKELETON)
    current = capture(arm)
    upstream_error = compare_upstream(reference, current)
    require(len(current['bones']) == 27, 'expected 27 bones')
    require(set(current['meshes']) ==
            {n for n, row in reference['meshes'].items() if row[0] not in FEET}
            | {'round_' + foot for foot in FEET}, 'round mesh inventory')
    centers = {foot: reference['bones'][foot][1][:3, 3] for foot in FEET}
    check_spheres(arm, centers)
    rejected = []
    for foot in FEET:
        obj = bpy.data.objects['round_' + foot]
        for defect in ('binding', 'center'):
            parent, world = obj.parent_bone, obj.matrix_world.copy()
            if defect == 'binding':
                obj.parent_bone = 'base_link'
            else:
                obj.location.x += .01
            bpy.context.view_layer.update()
            try:
                check_spheres(arm, centers)
            except ValueError:
                rejected.append(foot + ':' + defect)
            finally:
                obj.parent_bone = parent
                obj.matrix_world = world
                bpy.context.view_layer.update()
            require(foot + ':' + defect in rejected, 'negative check failed')
    check_spheres(arm, centers)
    # Complete source/bone correspondence above before applying candidate-only limits.
    tree = build_tree(SOURCE, RADIUS, elbow_limit=args.elbow_limit)
    movable = [j for j in tree.getroot().findall('joint') if j.get('type') != 'fixed']
    require(len(movable) == 26, 'expected 26 axes')
    # Exercise each inherited axis against shared URDF FK, all pivots and mesh vertices.
    neutral_frames = {b.name: arm.matrix_world @ b.matrix for b in arm.pose.bones}
    motion_errors = {}
    for joint in movable:
        child = joint.find('child').get('link')
        bone = arm.pose.bones[child]
        mode = bone.rotation_mode
        bone.rotation_mode = 'QUATERNION'
        axis = Vector(tuple(float(v) for v in joint.find('axis').get('xyz').split()))
        bone.rotation_quaternion = Quaternion(neutral_frames[child].to_3x3().inverted() @ axis, .07)
        bpy.context.view_layer.update()
        q = {joint.get('name'): .07}
        maximum = 0.
        for name in current['bones']:
            fk = geometry.fk(model['joints'], name, q)
            actual = np.array(arm.matrix_world @ arm.pose.bones[name].head)
            maximum = max(maximum, float(np.linalg.norm(actual - root_offset - fk[:3, 3])))
        for name, (owner, points, _) in current['meshes'].items():
            neutral = geometry.fk(model['joints'], owner, {})
            fk = geometry.fk(model['joints'], owner, q)
            local = points - root_offset - neutral[:3, 3]
            expected = local @ fk[:3, :3].T + fk[:3, 3] + root_offset
            actual = np.array(vertices(bpy.data.objects[name]))
            maximum = max(maximum, float(np.max(np.linalg.norm(actual - expected, axis=1))))
        bone.matrix_basis = Matrix.Identity(4)
        bone.rotation_mode = mode
        bpy.context.view_layer.update()
        require(maximum < TOL, 'axis FK/world geometry: ' + child + ' ' + str(maximum))
        motion_errors[joint.get('name')] = maximum
    check_spheres(arm, centers)
    compare_upstream(reference, capture(arm))
    require(all(sha256_file(p) == h for p, h in bindings.items()), 'input changed during checks')
    out.mkdir(parents=True, exist_ok=False)
    for mesh in tree.getroot().iter('mesh'):
        relative = Path(mesh.get('filename'))
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE.parent / relative, destination)
        require(sha256_file(destination) == bindings[str((SOURCE.parent / relative).resolve())],
                'exported mesh hash mismatch')
    target = out / 'lizard2_round_feet.urdf'
    tree.write(target, encoding='utf-8', xml_declaration=True)
    validate_tree(formal, ET.parse(target), RADIUS, elbow_limit=args.elbow_limit)
    files = {p.relative_to(out).as_posix(): sha256_file(p) for p in sorted(out.rglob('*')) if p.is_file()}
    report = dict(source=str(SKELETON), source_bindings_sha256=bindings,
                  urdf=str(target), urdf_sha256=sha256_file(target), radius_m=RADIUS,
                  foot_body_names=list(FEET), fixed_mounts=[f'{n}_fixed' for n in FEET],
                  active_joint_count=26, link_count=31,
                  mass_kg=sum(float(l.find('inertial/mass').get('value')) for l in tree.getroot().findall('link')),
                  mass_policy='diagnostic: retain former foot mass; COM sphere center; I=0.4*m*r^2',
                  foot_mass_kg={n: float(tree.getroot().find(f"link[@name='{n}']/inertial/mass").get('value')) for n in FEET},
                  zero_pose={n: {'center_root_m': (centers[n] - root_offset).tolist(),
                                 'bottom_root_z_m': float(centers[n][2] - root_offset[2] - RADIUS)} for n in FEET},
                  candidate_files_sha256=files, blender_version=bpy.app.version_string,
                  correspondence=dict(bones=27, formal_meshes=mesh_count,
                                      max_formal_mesh_error_m=mesh_error,
                                      max_upstream_vertex_error_m=upstream_error,
                                      axis_motion_errors_m=motion_errors,
                                      negative_rejections=rejected, tolerance_m=TOL),
                  scope='verified Blender-bound isolated candidate; inherited formal axes; no physics/USD/adoption')
    if args.elbow_limit is not None:
        report['design_change'] = dict(
            source=str(SOURCE), source_sha256=bindings[str(SOURCE.resolve())],
            elbow_limit_rad=args.elbow_limit,
            joint_limits_rad={
                name: {label: {k: float(root.find(f"joint[@name='{name}']/limit").get(k))
                               for k in ('lower', 'upper')}
                       for label, root in (('old', formal.getroot()), ('new', tree.getroot()))}
                for name in ('lf_elbow_joint', 'rf_elbow_joint')},
            scope='only lf/rf elbow lower/upper; knees, twist and all other upstream bytes unchanged')
    require(all(sha256_file(p) == h for p, h in bindings.items()), 'source changed during export')
    with (out / 'candidate.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print('ROUND_FEET_EXPORT_OK', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
