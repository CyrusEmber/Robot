# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Compare four-axis palm and five-axis shoulder/hip-twist candidates [m, rad, s].

Input is build.json from lizard2_palm_spatial_candidate.py. Uses saved Blender motion as an
independent oracle, then the existing URDF tree/FK readers for bounded IK and mesh collision.
Historical fixed-point/level-palm +/-3 degree pitch is a regression diagnostic ONLY, not a gait
requirement. Roll and yaw use the same amplitude as exploratory samples. No dynamics/adoption.
--lock_twist is the fail-before control: the real added axes remain in the asset but are held zero.
--inject_error twist_axis must fail the source/Blender checks, not produce a successful report.
"""

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "rl_exp/tools/verify"))
import check_leg_reachability as reach  # noqa: E402
import palm_motion_boundaries as motion  # noqa: E402
sys.path.insert(0, str(REPO / "rl_exp/tools/runrecord"))
from binding import sha256_file as digest  # noqa: E402

csc = motion.gait.csc
names = reach.joint_names


class Leg:
    """Read the actual ordered tree and express a sole point and upward normal [m]."""

    def __init__(self, path, leg, naming):
        self.leg = leg
        self.urdf = csc.load_urdf(path)
        self.names = reach.chain_joint_names(path, leg, naming)
        self.chain = reach.load_chain(path, leg, naming)
        self.end = names.end_link(leg, naming)
        self.root = csc.fk(self.urdf['joints'], self.urdf['joints'][self.names[0]]['parent'], {})
        self.lo = np.array([s['limits'][0] for s in self.chain])
        self.hi = np.array([s['limits'][1] for s in self.chain])
        pose = self.pose(np.zeros(len(self.names)))
        self.vertices = csc.read_obj(self.urdf['links'][self.end]['collision'])
        world = self.vertices @ pose[:3, :3].T + pose[:3, 3]
        self.sole_local = (world[world[:, 2] < world[:, 2].min() + 1e-3].mean(0) - pose[:3, 3]) @ pose[:3, :3]
        self.neutral, _ = self.sole(np.zeros(len(self.names)))

    def pose(self, q):
        return csc.fk(self.urdf['joints'], self.end, dict(zip(self.names, q)))

    def sole(self, q):
        pose = self.pose(q)
        return pose[:3, :3] @ self.sole_local + pose[:3, 3], pose[:3, 2]

    def solve(self, point, up, guess, lock_twist=False):
        free = [i for i, name in enumerate(self.names) if not (lock_twist and '_twist_joint' in name)]

        def expand(x):
            q = np.zeros(len(self.names))
            q[free] = x
            return q

        def residual(x):
            p, n = self.sole(expand(x))
            # Consistent old/new scaling; full normal rejects an upside-down solution.
            return np.r_[(p - point) / 1e-4, (n - up) / np.radians(2)]

        # At a cycle's neutral crossing, roundoff-sized starts can collapse TRF's initial
        # trust radius. Exact zero gives the solver its normal initial radius.
        start = guess[free].copy()
        if np.linalg.norm(start) < 1e-8:
            start[:] = 0
        result = least_squares(residual, start, bounds=(self.lo[free], self.hi[free]),
                               xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=300)
        return expand(result.x)


def check_blender(build, urdf, inject):
    """Compare saved Blender pivots/mesh samples against the independent URDF FK [m]."""
    if inject:
        urdf['joints']['lf_shoulder_twist_joint']['axis'] = np.array([0., 0., 1.])
    root = ET.parse(build['candidate_urdf']).getroot()
    visual = {}
    for link in root.findall('link'):
        mesh = link.find('visual/geometry/mesh')
        if mesh is not None:
            visual[link.get('name')] = cKDTree(csc.read_obj(Path(build['candidate_urdf']).parent / mesh.get('filename')))
    pivot_error, mesh_error = 0., 0.
    for snapshot in build['snapshots']:
        q = snapshot['q_rad']
        # Exporter uses world-neutral axes and subtracts the base bone head from positions.
        base_origin = np.array(snapshot['pivots']['base_link'])
        for name, point in snapshot['pivots'].items():
            frame = csc.fk(urdf['joints'], name, q)
            pivot_error = max(pivot_error, float(np.linalg.norm(frame[:3, 3] - (point - base_origin))))
        for row in snapshot['meshes'].values():
            frame = csc.fk(urdf['joints'], row['link'], q)
            local = (np.array(row['points']) - base_origin - frame[:3, 3]) @ frame[:3, :3]
            mesh_error = max(mesh_error, float(visual[row['link']].query(local)[0].max()))
    # Source mesh/URDF positions are rounded to six decimals; Blender uses float32.
    assert pivot_error < 1e-5 and mesh_error < 1e-5, (pivot_error, mesh_error)
    return {'max_pivot_error_m': pivot_error, 'max_visual_sample_error_m': mesh_error,
            'cases': len(build['snapshots']), 'budget_m': 1e-5,
            'budget_basis': 'six-decimal exported positions plus float32 multi-link transforms'}


def measure(leg, q, rotate):
    point, normal = leg.sole(q)
    return {'q_rad': q.tolist(), 'position_error_m': float(np.linalg.norm(rotate @ point - leg.neutral)),
            'tilt_deg': float(np.degrees(np.arccos(np.clip((rotate @ normal)[2], -1, 1)))),
            'limit_margin_deg': float(np.degrees(np.minimum(q - leg.lo, leg.hi - q).min()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build_report', type=Path, required=True)
    parser.add_argument('--output_dir', type=Path, required=True)
    parser.add_argument('--lock_twist', action='store_true')
    parser.add_argument('--inject_error', choices=('twist_axis',))
    args = parser.parse_args()
    output = args.output_dir.resolve()
    assert REPO / 'rl_exp/out' in output.parents and not output.exists(), 'Fresh isolated output required'
    build = json.loads(args.build_report.read_text(encoding='utf-8'))
    candidate = Path(build['candidate_urdf'])
    assert digest(candidate) == build['candidate_sha256']
    assert digest(candidate.with_suffix('.blend')) == build['candidate_blend_sha256']
    for relative, sha in build.get('candidate_files_sha256', {}).items():
        assert digest(candidate.parent / relative) == sha, relative
    for path, sha in build['input_sha256'].items():
        assert digest(path) == sha, path
    source = Path(build['source_urdf'])
    for path in (source, candidate):
        motion.validate_geometry(path)
    new = {leg: Leg(candidate, leg, names.PALM_SPATIAL_NAMING) for leg in names.LEGS}
    old = {leg: Leg(source, leg, names.PALM_NAMING) for leg in names.LEGS}
    urdf = csc.load_urdf(candidate)
    blender = check_blender(build, urdf, bool(args.inject_error))
    capability = {}
    for leg, model in new.items():
        q = np.zeros(5)
        assert np.linalg.norm(model.neutral - old[leg].neutral) < 1e-10
        # Two independent implementations of transform composition agree away from zero.
        mixed = np.array([.05, -.04, .08, .06, -.03])
        stdlib = model.root @ np.array(reach.chain_frames(model.chain, mixed)[-1])
        assert np.max(np.abs(stdlib - model.pose(mixed))) < 1e-10
        bend = build['definitions'][leg]['bend']
        original_bend = csc.fk(urdf['joints'], bend, {})[:3, 3]
        q[2] = np.radians(10)
        moved_bend = csc.fk(urdf['joints'], bend, dict(zip(model.names, q)))[:3, 3]
        assert np.linalg.norm(moved_bend - original_bend) < 1e-7, 'Twist is not along upper limb'
        displacement = np.linalg.norm(model.sole(q)[0] - model.neutral)
        assert displacement > 1e-3, 'Added joint has no downstream effect'
        ranks = {}
        for label, item in (('old', old[leg]), ('new', model)):
            def task(q):
                p, n = item.sole(q)
                return np.r_[p, n[:2]]
            zero = np.zeros(len(item.names))
            jac = np.column_stack([(task(zero + np.eye(len(zero))[i] * 1e-6)
                                    - task(zero - np.eye(len(zero))[i] * 1e-6)) / 2e-6
                                   for i in range(len(zero))])
            ranks[label] = {'rank': int(np.linalg.matrix_rank(jac, tol=1e-7)),
                            'singular_values_mixed_units': np.linalg.svd(jac, compute_uv=False).tolist()}
        assert ranks['new']['rank'] == 5
        capability[leg] = {'twist_knee_elbow_position_error_m': float(np.linalg.norm(moved_bend - original_bend)),
                           'twist_10deg_sole_displacement_m': float(displacement), 'task_jacobian': ranks}
    # Mirror has a negative sign on the polar long-axis direction, unlike an axial-vector convention.
    mirror_error = 0.
    for left, right in (('lf', 'rf'), ('rl', 'rr')):
        a, b = new[left], new[right]
        signs = motion.gait.mirror_signs(type('Axes', (), {'axes': [np.array(s['axis']) for s in a.chain]})(),
                                        type('Axes', (), {'axes': [np.array(s['axis']) for s in b.chain]})())
        assert np.isfinite(signs).all() and signs[2] == -1
        q = np.array([.05, -.04, .08, .06, -.03])
        pa, na = a.sole(q)
        pb, nb = b.sole(q * signs)
        mirror_error = max(mirror_error, float(np.linalg.norm(pb - pa * [1, -1, 1])),
                           float(np.linalg.norm(nb - na * [1, -1, 1])))
    assert mirror_error < 2e-4, mirror_error  # existing neutral geometry has micrometre asymmetry
    masses = [sum(row['mass'] for row in reach.link_inertials(path).values()) for path in (source, candidate)]
    assert abs(masses[0] - masses[1]) < 1e-10
    rows = []
    for mode, axis in (('pitch', [0, 1, 0]), ('roll', [1, 0, 0]), ('yaw', [0, 0, 1])):
        guesses = {(version, leg): np.zeros(len(models[leg].names))
                   for version, models in (('old', old), ('new', new)) for leg in names.LEGS}
        # Closed cycle includes both extrema and return to neutral.
        for frame, angle in enumerate(3 * np.sin(np.linspace(0, 2 * np.pi, 17))):
            rotate = motion.gait.rotation(np.array(axis, float), np.radians(angle))
            row = {'mode': mode, 'frame': frame, 'body_angle_deg': float(angle), 'root_rotation': rotate.tolist()}
            for version, models in (('old', old), ('new', new)):
                row[version] = {}
                for leg, model in models.items():
                    q = model.solve(rotate.T @ model.neutral, rotate.T @ np.array([0., 0., 1.]),
                                    guesses[version, leg], args.lock_twist and version == 'new')
                    guesses[version, leg] = q
                    row[version][leg] = measure(model, q, rotate)
            rows.append(row)
    maximum = {version: {key: max(row[version][leg][key] for row in rows for leg in names.LEGS)
                         for key in ('position_error_m', 'tilt_deg')}
               for version in ('old', 'new')}
    regression = maximum['new']['position_error_m'] <= 1e-4 and maximum['new']['tilt_deg'] <= 2
    assert maximum['old']['tilt_deg'] > 2, 'The historical failure was not reproduced'
    # Check actual geometry at neutral and both pitch/roll extrema; sparse samples only.
    collision = motion.Collision(urdf, .005)
    remap = {d['abduct']: d['twist'] for d in build['definitions'].values()}
    approved = {frozenset(remap.get(n, n) for n in pair) for pair in motion.gait.APPROVED}
    collision.pairs = [(a, b) for a, b in collision.pairs if frozenset((a, b)) not in approved]
    collisions = []
    if not args.lock_twist:
        for row in [rows[0]] + [r for r in rows if r['mode'] != 'yaw' and abs(r['body_angle_deg']) > 2.999]:
            q = {n: angle for leg, model in new.items() for n, angle in zip(model.names, row['new'][leg]['q_rad'])}
            pairs = collision.check(q)
            collisions.append({'mode': row['mode'], 'body_angle_deg': row['body_angle_deg'],
                               'minimum_gap_m': min(p['gap_lower_m'] for p in pairs),
                               'failures': [p for p in pairs if p['fail']]})
    summary = {'maxima': maximum, 'regression_pass': regression, 'lock_twist': args.lock_twist,
               'capability': capability, 'blender': blender, 'mirror_residual_m_or_unitless': mirror_error,
               'old_new_mass_kg': masses, 'collision_samples': collisions,
               'source_build_report': str(args.build_report.resolve()), 'build_report_sha256': digest(args.build_report),
               'probe_sha256': digest(__file__), 'rows': rows,
               'limits': 'Kinematics only. 51 samples per leg; collision only five full-body poses. Not a continuous safe domain, gait, dynamics or hardware ROM proof.'}
    output.mkdir(parents=True, exist_ok=False)
    (output / 'report.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    if not args.lock_twist:
        plot(output, old, new, rows)
    print(json.dumps({'maxima': maximum, 'blender': blender, 'regression_pass': regression,
                      'collision_failures': sum(len(r['failures']) for r in collisions)}, indent=1), flush=True)
    if not regression:
        raise SystemExit('REGRESSION_REJECTED: fixed-point/normal diagnostic still fails')


def plot(output, old, new, rows):
    """Write a reviewable geometry comparison and diagnostic curve."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(14, 8))
    selected = next(r for r in rows if r['mode'] == 'pitch' and r['body_angle_deg'] > 2.999)
    for i, (version, models, title) in enumerate((('old', old, 'Current: shoulder/hip has 2 axes'),
                                                 ('new', new, 'Candidate: shoulder/hip has 3 axes'))):
        ax = fig.add_subplot(2, 2, i + 1, projection='3d')
        rotate = np.array(selected['root_rotation'])
        for leg, model in models.items():
            q = selected[version][leg]['q_rad']
            frames = reach.chain_frames(model.chain, q)
            pts = np.array([(model.root @ np.array(frame))[:3, 3] for frame in frames[1:]]) @ rotate.T
            color = {'lf': '#1976d2', 'rf': '#64b5f6', 'rl': '#d86e23', 'rr': '#eab676'}[leg]
            ax.plot(*pts.T, '-o', color=color, markersize=3)
            p, n = model.sole(q)
            ax.scatter(*model.neutral, color='black', s=12)
            ax.quiver(*(rotate @ p), *(rotate @ n * .18), color=color)
            pose = model.pose(q)
            vertices = (model.vertices @ pose[:3, :3].T + pose[:3, 3]) @ rotate.T
            ax.scatter(*vertices[::max(1, len(vertices) // 70)].T, s=1, color=color, alpha=.5)
        ax.set_title(title + '\nBody pitch +3 deg; black dots = fixed sole targets')
        ax.set(xlabel='X [m]', ylabel='Y [m]', zlabel='Z [m]')
        ax.set_box_aspect((2, 2, 1))
        ax.view_init(24, -50)
    ax = fig.add_subplot(2, 1, 2)
    pitch = [r for r in rows if r['mode'] == 'pitch']
    for version, style in (('old', '--'), ('new', '-')):
        for leg in ('lf', 'rl'):
            ax.plot([r['frame'] for r in pitch], [r[version][leg]['tilt_deg'] for r in pitch],
                    style, label=f'{version} {leg}')
    ax.axhline(2, color='gray', linestyle=':', label='Historical diagnostic: 2 deg')
    ax.set(xlabel='Sample in body pitch cycle 0 -> +3 -> 0 -> -3 -> 0 deg', ylabel='Palm tilt [deg]')
    ax.legend(ncol=3)
    ax.grid(alpha=.2)
    fig.suptitle('Spatial palm reconfiguration — geometric diagnostic, not gait/dynamics validation')
    fig.tight_layout()
    fig.savefig(output / 'comparison.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
