# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Focused viewer regression; run directly with the host Python (no simulation)."""

import pathlib
import sys
import xml.etree.ElementTree as ET

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'rl_exp/tools/diagnose'))
import lizard2_spatial_pose_slider as viewer


def check(path, count, round_feet=False):
    import matplotlib.pyplot as plt

    model, meshes = viewer.load_model(path)
    fig = viewer.build(path, backend='Agg', show=False)
    radio, reset_button, state, values, draw = fig._pose_controls
    assert len(values) == count
    assert all(model['joints'][name]['axis'] is not None for name in values)
    seen = set()
    for index in range(len(viewer.GROUPS)):
        radio.set_active(index)
        seen.update(slider.label.get_text() + '_joint' for slider in state['sliders'])
    assert seen == set(values)
    if round_feet:
        assert not any('wrist' in name or 'ankle' in name for name in values)
        root = ET.parse(path).getroot()
        feet = [link.get('name') for link in root.findall('link')
                if link.find('visual/geometry/sphere') is not None]
        assert len(feet) == 4 and all(name in meshes for name in feet)
        radio.set_active(2)
        twist = next(slider for slider in state['sliders'] if slider.label.get_text() == 'rl_hip_twist')
        np.testing.assert_allclose([twist.valmin, twist.valmax], [-0.5236, 0.5236], atol=1e-4)
        foot = next(name for name in feet if name.startswith('rl_'))
        collection = fig.axes[0].collections[list(meshes).index(foot)]
        before = collection._vec.copy()
        twist.set_val(0.1)
        assert values['rl_hip_twist_joint'] == 0.1
        assert not np.allclose(collection._vec, before)
        vertices, faces = meshes[foot]
        transform = viewer.csc.fk(model['joints'], foot, values)
        expected = (vertices @ transform[:3, :3].T + transform[:3, 3])[faces].reshape(-1, 3).T
        np.testing.assert_allclose(collection._vec[:3], expected)
        # Exercise the actual Button callback, not an imitation of reset.
        reset_button._observers.process('clicked', None)
        assert all(value == 0.0 for value in values.values())
        np.testing.assert_allclose(collection._vec, before)
    plt.close(fig)
    print(f'PASS {count} active joints: {path}', flush=True)


if __name__ == '__main__':
    check(REPO / 'rl_exp/out/lizard2_round_feet/export03/lizard2_round_feet.urdf', 26, True)
    check(viewer.URDF, 30)
    candidate = REPO / 'rl_exp/out/lizard2_two_axis_20261029/candidate01/lizard2_two_axis.urdf'
    if candidate.exists():
        check(candidate, 34)
