# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Render recorded 5b root/joint trajectories; pictures are not physical verification.

Usage: python rl_exp/tools/diagnose/palm_motion_view.py --report_dir <5b output>
Outputs side/top GIFs for the requested cases, and a per-case residual plot. Refuses overwrite.
World origin is the neutral root; the neutral sole plane is at approximately z=-0.603 m.
"""

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.spatial import ConvexHull

import palm_motion_boundaries as motion


def render(out, name, report):
    with (out / f'{name}.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    urdf_path = Path(report['config']['urdf'])
    assert motion.gait.binding.sha256_file(urdf_path) == report['identity']['files'][str(urdf_path)]
    urdf = motion.gait.csc.load_urdf(urdf_path)
    local = {link: motion.gait.csc.read_obj(spec['collision']) for link, spec in urdf['links'].items()
             if spec['collision'] is not None}
    legs = {l: motion.gait.Leg(urdf, l) for l in motion.LEGS}
    names = [nm for leg in legs.values() for nm in leg.names]
    images = {'side': [], 'top': []}
    for view in images:
        assert not (out / f'{name}_{view}.gif').exists(), 'refuse GIF overwrite'
    for k in np.linspace(0, len(rows) - 1, 41).astype(int):
        row = rows[k]
        angles = {nm: float(row[nm]) for nm in names}
        rotate = np.array([[float(row[f'root_r{i}{j}']) for j in range(3)] for i in range(3)])
        shift = np.array([float(row[f'root_{axis}_m']) for axis in 'xyz'])
        world = {}
        for link, verts in local.items():
            frame = motion.gait.csc.fk(urdf['joints'], link, angles)
            world[link] = (verts @ frame[:3, :3].T + frame[:3, 3]) @ rotate.T + shift
        soles = np.array([rotate @ leg.sole(np.array([angles[nm] for nm in leg.names]))[0] + shift
                          for leg in legs.values()])
        for view, (i, j) in (('side', (0, 2)), ('top', (0, 1))):
            fig, ax = plt.subplots(figsize=(8, 5))
            for link, vertices in world.items():
                flat = vertices[:, [i, j]]
                hull = ConvexHull(flat)
                poly = flat[hull.vertices]
                ax.fill(poly[:, 0], poly[:, 1], alpha=.45,
                        color='tab:red' if link.split('_')[0] in motion.LEGS else 'tab:blue')
            ax.scatter(soles[:, i], soles[:, j], s=12, c='black')
            ax.set_xlim(-1.8, 1.4)
            ax.set_ylim((-1., .5) if view == 'side' else (-1.3, 1.3))
            if view == 'side':
                ax.axhline(legs['lf'].neutral_sole[2], color='gray', lw=.7)
            ax.set_aspect('equal')
            ax.set_xlabel('world x [m]')
            ax.set_ylabel('world z [m]' if view == 'side' else 'world y [m]')
            status = next(case['status'] for case in report['scenarios'] if case['name'] == name)
            ax.set_title(f'{name} {status}\nt={float(row["t_s"]):.2f} s | prescribed geometry')
            fig.canvas.draw()
            images[view].append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3]))
            plt.close(fig)
    for view, frames in images.items():
        frames[0].save(out / f'{name}_{view}.gif', save_all=True, append_images=frames[1:], duration=60, loop=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report_dir', type=Path, required=True)
    parser.add_argument('--scenarios', nargs='+', default=['turn_pos', 'turn_neg', 'recover_roll_pos', 'recover_pitch_pos'])
    args = parser.parse_args()
    out = args.report_dir.resolve()
    assert motion.REPO / 'rl_exp/out' in out.parents
    report = json.loads((out / 'report.json').read_text())
    assert report['completed'], 'incomplete run'
    for name in args.scenarios:
        assert name in {case['name'] for case in report['scenarios']}, 'unknown scenario'
        render(out, name, report)
        print('PALM_5B_RENDERED', name, flush=True)
    target = out / 'residuals.png'
    assert not target.exists(), 'refuse plot overwrite'
    names = [case['name'] for case in report['scenarios']]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].bar(names, [case['max_position_residual_m'] * 1000 for case in report['scenarios']])
    axes[0].axhline(report['config']['pos_tol_m'] * 1000, color='red')
    axes[0].set_ylabel('position residual [mm]')
    axes[1].bar(names, [case['max_palm_tilt_deg'] for case in report['scenarios']])
    axes[1].axhline(report['config']['tilt_tol_deg'], color='red')
    axes[1].set_ylabel('palm tilt [deg]')
    axes[1].tick_params(axis='x', rotation=55)
    fig.tight_layout()
    fig.savefig(target, dpi=140)
    plt.close(fig)


if __name__ == '__main__':
    main()
