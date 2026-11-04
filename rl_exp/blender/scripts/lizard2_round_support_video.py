# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Render frozen URDF geometry, then encode labelled still-view video; no physics.

Blender: --background --factory-startup --python-exit-code 1 --python SCRIPT --
Host Python: SCRIPT --encode. Outputs are fresh, under rl_exp/out. Units: m, rad.
"""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tools.runrecord.binding import sha256_file as sha  # noqa: E402

REPORT = ROOT / 'rl_exp/out/lizard2_round_support/prepare02/geometry.json'
BLEND = ROOT / 'rl_exp/out/lizard2_round_feet/skeleton02/lizard2_round_feet.blend'
BLEND_SHA = '4e3073d1389db9875a0dd4db4e7ec4ef7a56b5231d7df6fc12edc4c57660cf07'
OUT = ROOT / 'rl_exp/out/lizard2_round_support/video02'
HELPER = ROOT / 'rl_exp/tools/verify/check_self_collision.py'
VIEWS = [('front', (1, 0, .24)), ('side', (0, -1, .18)), ('oblique', (1.2, -1.6, 1.1))]


def render(out, report=REPORT):
    import bpy
    import numpy as np
    from mathutils import Matrix, Vector, Euler, Quaternion

    data = json.loads(report.read_text(encoding='utf-8'))
    assert data['passed'] and set(data['groups']) == {'lf+rr', 'rf+rl'}
    bindings = dict(data['sha256'])
    for path, digest in bindings.items():
        assert sha(path) == digest, f'Source binding changed: {path}'
    assert sha(BLEND) == BLEND_SHA, 'Source blend changed'
    for path in (report, BLEND, Path(__file__), HELPER):
        bindings[str(path)] = sha(path)
    assert out.is_relative_to((ROOT / 'rl_exp/out').resolve()) and not out.exists()
    out.mkdir(parents=True)

    # Same pure-function extraction used by lizard2_round_feet_export.py.
    names = {'load_urdf', 'chain_up', 'fk'}
    nodes = [n for n in ast.parse(HELPER.read_text(encoding='utf-8')).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    namespace = {'np': np, 'ET': ET, 'pathlib': __import__('pathlib')}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(HELPER), 'exec'), namespace)
    urdf = Path(data['urdf'])
    model = namespace['load_urdf'](urdf)
    tree = ET.parse(urdf).getroot()
    assert all(j.find('origin').get('rpy', '0 0 0') == '0 0 0' for j in tree.findall('joint'))

    def origin(item):
        node = item.find('origin')
        if node is None:
            return Matrix.Identity(4)
        xyz = Vector(tuple(map(float, node.get('xyz', '0 0 0').split())))
        rpy = Euler(tuple(map(float, node.get('rpy', '0 0 0').split())), 'XYZ')
        return Matrix.Translation(xyz) @ rpy.to_matrix().to_4x4()

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    objects = []
    for link in tree.findall('link'):
        for index, visual in enumerate(link.findall('visual')):
            shape, = list(visual.find('geometry'))
            if shape.tag == 'mesh':
                mesh_path = (urdf.parent / shape.get('filename')).resolve()
                assert str(mesh_path) in bindings, 'Unbound visual mesh'
                before = set(bpy.data.objects)
                bpy.ops.wm.obj_import(filepath=str(mesh_path), forward_axis='Y', up_axis='Z')
                obj, = set(bpy.data.objects) - before
                scale = tuple(map(float, shape.get('scale', '1 1 1').split()))
            else:
                assert shape.tag == 'sphere'
                bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=float(shape.get('radius')))
                obj = bpy.context.object
                scale = (1, 1, 1)
            obj.name = link.get('name') + '_visual_' + str(index)
            objects.append((obj, link.get('name'), origin(visual), Matrix.Diagonal((*scale, 1)), shape.tag))
            obj.color = (.48, .56, .61, 1)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.001))
    bpy.context.object.name = 'Floor_z0'
    bpy.context.object.color = (.16, .19, .22, 1)
    # Thin floor grid provides height and scale cues without any simulation.
    for axis in (0, 1):
        for i in range(-12, 13):
            position = [0., 0., -.0005]
            position[axis] = i * .25
            bpy.ops.mesh.primitive_cube_add(size=1, location=position)
            obj = bpy.context.object
            obj.dimensions = (.003, 6, .0005) if axis == 0 else (6, .003, .0005)
            obj.color = (.23, .27, .30, 1)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x, scene.render.resolution_y = 960, 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'OBJECT'
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.045, .055, .065)
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 4.1
    xyzw = data['root_quaternion_xyzw']
    root = Matrix.Translation(Vector(data['root_position_world_m'])) @ Quaternion((xyzw[3], *xyzw[:3])).to_matrix().to_4x4()
    checks, frames = {}, []
    for group_name, group in data['groups'].items():
        q = group['solver']['q_rad']
        assert len(q) == 26 and set(q) == {n for n, j in model['joints'].items() if j['axis'] is not None}
        errors = []
        for obj, link, local, scale, kind in objects:
            pose = root @ Matrix(namespace['fk'](model['joints'], link, q).tolist()) @ local
            obj.matrix_world = pose @ scale
            if kind == 'sphere':
                row, = [r for r in group['validation']['geometry'] if r['kind'] == 'visual' and r['link'] == link]
                error = (pose.translation - Vector(row['center_world_m'])).length
                assert error < data['point_tolerance_m'], (group_name, link, error)
                assert abs(pose.translation.z - row['radius_m'] - row['ground_gap_m']) < data['point_tolerance_m']
                errors.append(error)
                obj.color = (1., .48, .06, 1) if link in group['support'] else (.04, .5, 1., 1)
        bpy.context.view_layer.update()
        twists = [n for n in q if n.endswith('_twist_joint')]
        twist_zero = len(twists) == 4 and all(q[n] == 0. for n in twists)
        checks[group_name] = {'max_sphere_center_error_m': max(errors), 'q_rad': q, 'support': group['support'], 'twist_zero': twist_zero}
        points = [obj.matrix_world @ Vector(c) for obj, *_ in objects for c in obj.bound_box]
        lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        target = (lo + hi) / 2
        target.z = max(target.z, .35)
        for view, direction in VIEWS:
            camera.location = target + Vector(direction).normalized() * 10
            camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
            filename = group_name.replace('+', '_') + '_' + view + '.png'
            scene.render.filepath = str(out / filename)
            bpy.ops.render.render(write_still=True)
            frames.append({'image': filename, 'group': group_name, 'view': view, 'support': group['support']})
    manifest = {'scope': 'GEOMETRY ONLY / NO PHYSICS; frozen poses; hard camera cuts; no pose interpolation; designated support is not measured force or stability',
                'input_sha256': bindings, 'geometry_checks': checks, 'frames': frames}
    (out / 'render.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('RENDER PASS', out)


def encode(out):
    from PIL import Image, ImageDraw, ImageFont
    import imageio_ffmpeg

    manifest = json.loads((out / 'render.json').read_text(encoding='utf-8'))
    assert sha(__file__) == manifest['input_sha256'][str(Path(__file__))]
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 23)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19)
    images = []
    for frame in manifest['frames']:
        image = Image.open(out / frame['image']).convert('RGB')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 960, 92), fill=(12, 18, 24))
        draw.rectangle((0, 562, 960, 640), fill=(12, 18, 24))
        twist_label = ' | TWIST=0' if manifest['geometry_checks'][frame['group']].get('twist_zero', False) else ''
        draw.text((18, 8), 'GEOMETRY ONLY / NO PHYSICS' + twist_label, font=font, fill='#ffce69')
        draw.text((18, 42), f"Group: {frame['group'].upper()}   |   View: {frame['view'].upper()}   |   Frozen existing pose", font=font, fill='white')
        support = ' + '.join(s.upper() for s in frame['support'])
        draw.text((18, 568), f'Orange = designated support: {support}   |   Blue = other feet', font=small, fill='white')
        draw.text((18, 597), 'Floor z=0 | Grid 0.25 m | Static geometry, not stability/contact-force evidence', font=small, fill='#c4d2dd')
        path = out / ('labelled_' + frame['image'])
        image.save(path)
        images.append(image.tobytes())
    video = out / 'two_groups_geometry.mp4'
    assert not video.exists(), 'Refuse to overwrite video'
    writer = imageio_ffmpeg.write_frames(str(video), (960, 640), fps=15, codec='libx264', pix_fmt_out='yuv420p', output_params=['-movflags', '+faststart'])
    writer.send(None)
    try:
        for image in images:
            for _ in range(30):
                writer.send(image)
    finally:
        writer.close()
    # Decode every frame. Check playable H264 output and exact count, not file existence.
    reader = imageio_ffmpeg.read_frames(str(video), pix_fmt='rgb24')
    metadata = next(reader)
    count = sum(1 for _ in reader)
    assert count == 180 and metadata['size'] == (960, 640) and abs(metadata['duration'] - 12) < .1, metadata
    manifest['video'] = {'path': str(video), 'sha256': sha(video), 'frames': count, 'duration_s': metadata['duration'], 'fps': metadata['fps'], 'size': metadata['size'], 'codec': metadata['codec']}
    manifest['output_sha256'] = {p.name: sha(p) for p in out.glob('*.png')}
    (out / 'render.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest['video'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--report', type=Path, default=REPORT)
    parser.add_argument('--encode', action='store_true')
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    if args.encode:
        encode(args.out.resolve())
    else:
        render(args.out.resolve(), args.report.resolve())
