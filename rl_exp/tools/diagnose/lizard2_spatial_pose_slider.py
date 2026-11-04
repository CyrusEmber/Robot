# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Interactive kinematic viewer for Lizard2 URDF joint limits; no physics."""

from __future__ import annotations

import argparse
import pathlib
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial import ConvexHull

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'rl_exp' / 'tools' / 'verify'))
import check_self_collision as csc  # noqa: E402

URDF = REPO / 'rl_exp' / 'lizard2_palm_spatial' / 'lizard2_palm_spatial.urdf'
GROUPS = {
    'LF front': ['lf_shoulder_swing', 'lf_shoulder_abduct', 'lf_shoulder_twist', 'lf_elbow', 'lf_wrist'],
    'RF front': ['rf_shoulder_swing', 'rf_shoulder_abduct', 'rf_shoulder_twist', 'rf_elbow', 'rf_wrist'],
    'RL rear': ['rl_hip_swing', 'rl_hip_abduct', 'rl_hip_twist', 'rl_knee', 'rl_ankle'],
    'RR rear': ['rr_hip_swing', 'rr_hip_abduct', 'rr_hip_twist', 'rr_knee', 'rr_ankle'],
    'Body': ['chest_yaw', 'chest_pitch', 'neck_yaw', 'neck_pitch'],
    'Tail': ['tail1_yaw', 'tail1_pitch', 'tail2_yaw', 'tail2_pitch', 'tail3_yaw', 'tail3_pitch'],
}


def joint_groups(model):
    """Group active axes only; fixed mounts remain in the FK tree."""
    active = {name for name, spec in model['joints'].items() if spec['axis'] is not None}
    groups = {key: [name for name in group if name + '_joint' in active]
              for key, group in GROUPS.items()}
    for group, leg, tip in [('LF front', 'lf', 'wrist'), ('RF front', 'rf', 'wrist'),
                             ('RL rear', 'rl', 'ankle'), ('RR rear', 'rr', 'ankle')]:
        name = f'{leg}_{tip}_lateral'
        if name + '_joint' in active:
            groups[group].insert(-1, name)
    names = [name + '_joint' for group in groups.values() for name in group]
    if len(names) != len(set(names)) or set(names) != active:
        raise ValueError('slider groups do not cover the URDF active joint set exactly')
    return groups


def load_model(path: pathlib.Path):
    """Load the asset and reject unsupported nonzero frame rotations or mesh transforms."""
    root = ET.parse(path).getroot()
    for node in root.findall('./joint/origin') + root.findall('./link/visual/origin'):
        if any(abs(float(x)) > 1e-12 for x in node.get('rpy', '0 0 0').split()):
            raise ValueError('nonzero URDF frame rotation requires another FK reader')
    model = csc.load_urdf(path)
    joint_groups(model)
    meshes = {}
    for link in root.findall('link'):
        visual = link.find('visual')
        if visual is None:
            continue
        origin = visual.find('origin')
        xyz = [float(v) for v in (origin.get('xyz', '0 0 0') if origin is not None else '0 0 0').split()]
        mesh = visual.find('geometry/mesh')
        sphere = visual.find('geometry/sphere')
        if sphere is not None:
            radius = float(sphere.get('radius'))
            if not np.isfinite(radius) or radius <= 0:
                raise ValueError('sphere radius must be positive and finite')
            theta, phi = np.meshgrid(np.linspace(0, np.pi, 13),
                                     np.linspace(0, 2 * np.pi, 24, endpoint=False))
            vertices = radius * np.column_stack((
                (np.sin(theta) * np.cos(phi)).ravel(),
                (np.sin(theta) * np.sin(phi)).ravel(), np.cos(theta).ravel()))
        else:
            if mesh is None or mesh.get('scale', '1 1 1') != '1 1 1':
                raise ValueError('unsupported visual geometry or scale')
            vertices, _ = csc.read_obj_faces((path.parent / mesh.get('filename')).resolve())
        # Draw a closed approximate shell, not disconnected sampled triangles. These hulls
        # are for display only and must never be used for contact or collision measurements.
        sample = vertices[np.linspace(0, len(vertices) - 1, min(len(vertices), 400), dtype=int)]
        meshes[link.get('name')] = (sample + xyz, ConvexHull(sample).simplices)
    return model, meshes


def build(path: pathlib.Path = URDF, backend: str = 'TkAgg', show: bool = True):
    import matplotlib
    matplotlib.use(backend)
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button, RadioButtons, Slider
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    path = path.resolve()
    model, meshes = load_model(path)
    groups = joint_groups(model)
    values = {name: 0.0 for name, spec in model['joints'].items() if spec['axis'] is not None}
    fig = plt.figure(figsize=(14, 9))
    is_candidate = any(name.endswith('_lateral_joint') for name in model['joints'])
    has_spheres = ET.parse(path).find('./link/visual/geometry/sphere') is not None
    label = ('Lizard2 fixed round feet' if has_spheres else
             'Lizard2 two-axis candidate' if is_candidate else 'Lizard2 palm spatial')
    title = f'{label} | {len(values)} active joints'
    fig.canvas.manager.set_window_title(title)
    fig.text(0.03, 0.96, f'Source: {path}', fontsize=8)
    ax = fig.add_axes([0.03, 0.10, 0.65, 0.82], projection='3d')
    ax.set_xlim(-1.9, 1.9); ax.set_ylim(-1.3, 1.3); ax.set_zlim(-0.8, 1.0)
    ax.set_box_aspect((3.8, 2.6, 1.8))
    ax.view_init(elev=18, azim=-62)
    ax.set_xlabel('X forward [m]'); ax.set_ylabel('Y left [m]'); ax.set_zlabel('Z [m]')
    ax.set_title(title + '\nApproximate display shells; no gravity/contact')
    ax.mouse_init(rotate_btn=[1, 2], pan_btn=[], zoom_btn=3)
    collections = {}
    for name, (vertices, faces) in meshes.items():
        color = ('#579ad1' if name.startswith(('lf_', 'rl_')) else
                 '#d4965c' if name.startswith(('rf_', 'rr_')) else '#a4afb6')
        collection = Poly3DCollection(vertices[faces], facecolor=color, edgecolor='none', alpha=0.92)
        ax.add_collection3d(collection)
        collections[name] = collection
    fig.text(0.03, 0.04, 'Drag model to rotate; right drag to zoom. Angles are radians.', fontsize=10)
    radio = RadioButtons(fig.add_axes([0.72, 0.57, 0.24, 0.31]), list(groups))
    slider_axes = [fig.add_axes([0.75, 0.49 - i * 0.061, 0.20, 0.025]) for i in range(6)]
    reset_button = Button(fig.add_axes([0.74, 0.06, 0.20, 0.05]), 'Reset all')
    state = {'sliders': [], 'group': 'LF front', 'changing': False}

    def draw():
        for name, (vertices, faces) in meshes.items():
            transform = csc.fk(model['joints'], name, values)
            points = vertices @ transform[:3, :3].T + transform[:3, 3]
            collections[name].set_verts(points[faces])
        fig.canvas.draw_idle()

    def select(group):
        state['changing'] = True
        for slider in state['sliders']:
            slider.disconnect_events()
        state['sliders'] = []
        state['group'] = group
        for index, area in enumerate(slider_axes):
            area.clear()
            area.set_visible(index < len(groups[group]))
            if index >= len(groups[group]):
                continue
            name = groups[group][index] + '_joint'
            low, high = model['joints'][name]['limits']
            slider = Slider(area, name.removesuffix('_joint'), low, high, valinit=values[name], valfmt='%+.2f')
            def changed(value, key=name):
                if not state['changing']:
                    values[key] = float(value)
                    draw()
            slider.on_changed(changed)
            state['sliders'].append(slider)
        state['changing'] = False
        fig.canvas.draw_idle()

    def reset(_event):
        values.update(dict.fromkeys(values, 0.0))
        select(state['group'])
        draw()

    radio.on_clicked(select)
    reset_button.on_clicked(reset)
    select('LF front')
    draw()
    # Keep widgets alive for Matplotlib callbacks, and expose state for focused verification.
    fig._pose_controls = (radio, reset_button, state, values, draw)
    if show:
        fig.canvas.draw()
        print(f'VIEWER_READY | {title} | source={path} | backend={backend}', flush=True)
        plt.show()
    return fig


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', default='TkAgg')
    parser.add_argument('--urdf', type=pathlib.Path, default=URDF)
    args = parser.parse_args()
    build(path=args.urdf, backend=args.backend)
