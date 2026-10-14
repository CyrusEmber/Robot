# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""5b isolated geometric turning, return-to-neutral and hinge interference [m, rad, s].

Run with the configured IsaacLab Python, without starting simulation::

    python rl_exp/tools/diagnose/palm_motion_boundaries.py --urdf <candidate.urdf> --output_dir <rl_exp/out/new>
    python rl_exp/tools/diagnose/palm_motion_boundaries.py --self_check

The config is an engineering target, approved 2026-10-14. Turning has explicit SE(2) root motion
and fixed world footholds during stance. Recovery means a prescribed root displacement returning
to neutral with four fixed footholds, NOT recovery after a push. No forces, PD, gravity or stability.
All joint bounds come from the isolated URDF. Observed joint extrema are a sampled target envelope,
never a Cartesian safe box or finalized policy range. All collision-bearing link pairs are checked
except direct joint neighbours and the existing six approved connection pairs. Proximity uses
triangle surfaces, segment/triangle intersections and solid-angle containment. AABB distance is a
conservative clearance lower bound for remote pairs. Mesh distance includes vertex/face AND edge/edge
features. Boundary scans vary one hinge at a time in neutral and scenario-extreme contexts; they
do not prove the full joint domain safe. The externally shared FK and URDF remain common assumptions.
"""

import argparse
import csv
import itertools
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

sys.path.insert(0, str(Path(__file__).resolve().parent))
import palm_gait_kinematics as gait  # noqa: E402

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
LEGS = tuple(gait.ROLES)


def point_segment(points, a, b):
    delta = b - a
    den = np.sum(delta * delta, axis=-1)
    t = np.clip(np.sum((points - a) * delta, axis=-1) / np.maximum(den, 1e-30), 0., 1.)
    return np.linalg.norm(points - (a + t[..., None] * delta), axis=-1)


def surface_distance(va, fa, vb, fb):
    """Exact minimum triangle-surface distance [m], excluding interior containment."""
    best = np.inf
    for points, tri in ((va, vb[fb]), (vb, va[fa])):
        a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
        u, v = b - a, c - a
        uu, uv, vv = (np.sum(x * y, axis=1) for x, y in ((u, u), (u, v), (v, v)))
        den = uu * vv - uv * uv
        for chunk in np.array_split(points, max(1, len(points) // 32)):
            p = chunk[:, None, :]
            rel = p - a
            pu, pv = np.sum(rel * u, axis=-1), np.sum(rel * v, axis=-1)
            s = (vv * pu - uv * pv) / np.maximum(den, 1e-30)
            t = (uu * pv - uv * pu) / np.maximum(den, 1e-30)
            face = np.linalg.norm(rel - s[..., None] * u - t[..., None] * v, axis=-1)
            face = np.where((s >= 0) & (t >= 0) & (s + t <= 1) & (den > 1e-25), face, np.inf)
            distances = np.minimum.reduce([face, point_segment(p, a, b),
                                           point_segment(p, b, c), point_segment(p, c, a)])
            best = min(best, float(distances.min()))
    ea = np.unique(np.sort(np.concatenate([fa[:, [0, 1]], fa[:, [1, 2]], fa[:, [2, 0]]]), axis=1), axis=0)
    eb = np.unique(np.sort(np.concatenate([fb[:, [0, 1]], fb[:, [1, 2]], fb[:, [2, 0]]]), axis=1), axis=0)
    b0, b1 = vb[eb[:, 0]], vb[eb[:, 1]]
    v = b1 - b0
    vv = np.sum(v * v, axis=-1)
    for chunk in np.array_split(ea, max(1, len(ea) // 32)):
        a0, a1 = va[chunk[:, 0], None], va[chunk[:, 1], None]
        u, w = a1 - a0, a0 - b0
        uu, uv, uw, vw = (np.sum(x * y, axis=-1) for x, y in ((u, u), (u, v), (u, w), (v, w)))
        den = uu * vv - uv * uv
        s = (uv * vw - vv * uw) / np.maximum(den, 1e-30)
        t = (uu * vw - uv * uw) / np.maximum(den, 1e-30)
        interior = np.linalg.norm(w + s[..., None] * u - t[..., None] * v, axis=-1)
        interior = np.where((s >= 0) & (s <= 1) & (t >= 0) & (t <= 1) & (den > 1e-25), interior, np.inf)
        distances = np.minimum.reduce([interior, point_segment(a0, b0, b1), point_segment(a1, b0, b1),
                                       point_segment(b0, a0, a1), point_segment(b1, a0, a1)])
        best = min(best, float(distances.min()))
    return best


def surface_crosses(va, fa, vb, fb):
    tri = vb[fb]
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    edges = np.unique(np.sort(np.concatenate([fa[:, [0, 1]], fa[:, [1, 2]], fa[:, [2, 0]]]), axis=1), axis=0)
    for chunk in np.array_split(edges, max(1, len(edges) // 32)):
        start = va[chunk[:, 0], None]
        direction = va[chunk[:, 1], None] - start
        h = np.cross(direction, e2)
        det = np.sum(e1 * h, axis=-1)
        good = np.abs(det) > 1e-14
        inv = np.divide(1., det, out=np.zeros_like(det), where=good)
        rel = start - tri[:, 0]
        u = inv * np.sum(rel * h, axis=-1)
        q = np.cross(rel, e1)
        v = inv * np.sum(direction * q, axis=-1)
        t = inv * np.sum(e2 * q, axis=-1)
        if np.any(good & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t >= 0) & (t <= 1)):
            return True
    return False


def inside(point, vertices, faces):
    a, b, c = (vertices[faces[:, i]] - point for i in range(3))
    la, lb, lc = (np.linalg.norm(x, axis=1) for x in (a, b, c))
    numerator = np.sum(a * np.cross(b, c), axis=1)
    denominator = la * lb * lc + np.sum(a * b, axis=1) * lc + np.sum(b * c, axis=1) * la + np.sum(c * a, axis=1) * lb
    return abs(float(np.arctan2(numerator, denominator).sum() * 2)) > 2 * np.pi


def component_representatives(vertices, faces):
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    graph = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(vertices), len(vertices)))
    _, labels = connected_components(graph, directed=False)
    _, representatives = np.unique(labels, return_index=True)
    return representatives


class Collision:
    def __init__(self, urdf, clearance):
        self.urdf, self.clearance = urdf, clearance
        self.local = {}
        self.mesh_paths = []
        self.representatives = {}
        for name, spec in urdf['links'].items():
            if spec['collision'] is None:
                continue
            vertices, faces = gait.csc.read_obj_faces(spec['collision'])
            vertices, inverse = np.unique(vertices, axis=0, return_inverse=True)
            faces = inverse[faces]
            # OBJ exports repeat vertices and include zero-width pole triangles. Drop triangles
            # with repeated indices; keep distinct collinear vertices to retain the closed topology.
            faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
            _, unique = np.unique(np.sort(faces, axis=1), axis=0, return_index=True)
            faces = faces[unique]
            # Winding containment is valid only for closed, consistently oriented surfaces.
            edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
            _, counts = np.unique(np.sort(edges, axis=1), axis=0, return_counts=True)
            assert np.all(counts == 2), f'non-watertight collision mesh: {name}'
            directed = edges[:, 0] < edges[:, 1]
            keys, ids = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True)
            balance = np.bincount(ids, weights=np.where(directed, 1, -1), minlength=len(keys))
            assert np.all(balance == 0), f'inconsistent winding: {name}'
            self.local[name] = (vertices, faces)
            self.representatives[name] = component_representatives(vertices, faces)
            self.mesh_paths.append(spec['collision'])
        self.pairs = [(a, b) for a, b in itertools.combinations(sorted(self.local), 2)
                      if frozenset((a, b)) not in gait.APPROVED
                      and not gait.csc.jointed_pair(urdf['joints'], a, b)]

    def check(self, angles):
        world = {}
        for name, (verts, _) in self.local.items():
            pose = gait.csc.fk(self.urdf['joints'], name, angles)
            world[name] = verts @ pose[:3, :3].T + pose[:3, 3]
        rows = []
        for a, b in self.pairs:
            va, vb = world[a], world[b]
            delta = np.maximum(0., np.maximum(va.min(0) - vb.max(0), vb.min(0) - va.max(0)))
            lower = float(np.linalg.norm(delta))
            if lower >= self.clearance:
                rows.append({'pair': [a, b], 'gap_lower_m': lower, 'method': 'aabb_lower_bound', 'fail': False})
                continue
            fa, fb = self.local[a][1], self.local[b][1]
            intersects = surface_crosses(va, fa, vb, fb) or surface_crosses(vb, fb, va, fa)
            contained = (any(inside(va[i], vb, fb) for i in self.representatives[a])
                         or any(inside(vb[i], va, fa) for i in self.representatives[b]))
            gap = 0. if intersects or contained else surface_distance(va, fa, vb, fb)
            rows.append({'pair': [a, b], 'gap_lower_m': gap, 'method': 'triangle_surface',
                         'intersects': intersects, 'contained': contained, 'fail': gap < self.clearance})
        return rows


def validate_geometry(path):
    """Reject transforms the reused FK/OBJ readers do not model."""
    root = ET.parse(path).getroot()
    for joint in root.findall('joint'):
        assert joint.get('type') in ('revolute', 'fixed'), 'unsupported joint type'
        assert np.allclose([float(x) for x in joint.find('origin').get('rpy', '0 0 0').split()], 0), 'joint rpy unsupported'
    for link in root.findall('link'):
        assert len(link.findall('collision')) <= 1, 'multiple collision shapes unsupported'
        shape = link.find('collision')
        if shape is None:
            continue
        origin = shape.find('origin')
        if origin is not None:
            assert np.allclose([float(x) for x in origin.get('xyz', '0 0 0').split()], 0), 'collision offset unsupported'
            assert np.allclose([float(x) for x in origin.get('rpy', '0 0 0').split()], 0), 'collision rotation unsupported'
        mesh = shape.find('geometry/mesh')
        assert mesh is not None and np.allclose([float(x) for x in mesh.get('scale', '1 1 1').split()], 1), 'mesh scale unsupported'


def root_turn(t, speed, rate):
    yaw = rate * t
    rotate = gait.rotation(np.array([0., 0., 1.]), yaw)
    shift = np.array([speed * t, 0., 0.]) if rate == 0 else np.array([speed * np.sin(yaw) / rate, speed * (1 - np.cos(yaw)) / rate, 0.])
    return rotate, shift


def turn_target(leg, t, rate, config):
    period, stance = config['period_s'], config['stance_fraction']
    speed = config['step_m'] / (period * stance)
    offset = gait.PHASE[leg.leg]
    cycle = np.floor(t / period + offset)
    phase = t / period + offset - cycle
    ts = (cycle - offset) * period
    point = leg.neutral_sole + np.array([config['step_m'] / 2, 0., 0.])
    r0, p0 = root_turn(ts, speed, rate)
    anchor = r0 @ point + p0
    if phase >= stance:
        rn, pn = root_turn(ts + period, speed, rate)
        end = rn @ point + pn
        s = (phase - stance) / (1 - stance)
        anchor = anchor + (end - anchor) * (0.5 - 0.5 * np.cos(np.pi * s))
        anchor[2] += config['lift_m'] * np.sin(np.pi * s) ** 2
    rotate, shift = root_turn(t, speed, rate)
    return rotate.T @ (anchor - shift), rotate.T @ np.array([0., 0., 1.]), rotate, shift, anchor, phase < stance


def solve(leg, point, up, guess, position_tolerance, tilt_tolerance_deg):
    orientation_weight = position_tolerance / np.radians(tilt_tolerance_deg)

    def residual(q):
        actual, normal = leg.sole(q)
        # Normalize competing goals by the accepted tolerances; exact normal is not required.
        return np.r_[actual - point, orientation_weight * (normal - up)]
    result = least_squares(residual, np.clip(guess, leg.lo + 1e-8, leg.hi - 1e-8),
                           bounds=(leg.lo, leg.hi), xtol=1e-12, ftol=1e-12, gtol=1e-12)
    actual, normal = leg.sole(result.x)
    tilt = np.degrees(np.arccos(np.clip(np.dot(normal, up), -1., 1.)))
    if np.linalg.norm(actual - point) <= position_tolerance and tilt <= tilt_tolerance_deg:
        return result.x
    candidates = [result]
    for start in (np.zeros(4), (leg.lo + leg.hi) / 2):
        candidates.append(least_squares(residual, start, bounds=(leg.lo, leg.hi),
                                        xtol=1e-12, ftol=1e-12, gtol=1e-12))
    return min(candidates, key=lambda x: np.linalg.norm(x.fun)).x


def scenario(name, urdf, legs, detector, config, out):
    recovery = name.startswith('recover')
    duration = config['recovery_period_s'] if recovery else config['period_s']
    n = round(config['frames_per_period'] * duration / config['period_s'])
    dt = duration / n
    q = {l: np.zeros((n + 1, 4)) for l in LEGS}
    pos, tilt, slip = [], [], []
    frames, roots, support = [], [], []
    for k, t in enumerate(np.linspace(0, duration, n + 1)):
        angles, errors = {}, {}
        for l, leg in legs.items():
            if recovery:
                axis, sign = name.split('_')[1:]
                sign = 1. if sign == 'pos' else -1.
                amplitude = sign * np.sin(np.pi * t / duration) ** 2
                shift, rotate = np.zeros(3), np.eye(3)
                if axis in ('y', 'z'):
                    shift['xyz'.index(axis)] = amplitude * config['recovery_translation_m']
                else:
                    rotate = gait.rotation(np.eye(3)[0 if axis == 'roll' else 1], amplitude * np.radians(config['recovery_angle_deg']))
                anchor = leg.neutral_sole.copy()
                point, up, stance = rotate.T @ (anchor - shift), rotate.T @ np.array([0., 0., 1.]), True
            else:
                rate = 0. if name == 'straight' else config['turn_rad_s'] * (1 if name == 'turn_pos' else -1)
                point, up, rotate, shift, anchor, stance = turn_target(leg, t, rate, config)
            q[l][k] = solve(leg, point, up, q[l][k - 1] if k else np.zeros(4),
                            config['pos_tol_m'], config['tilt_tol_deg'])
            actual, normal = leg.sole(q[l][k])
            position_error = float(np.linalg.norm(actual - point))
            tilt_error = float(np.degrees(np.arccos(np.clip((rotate @ normal)[2], -1, 1))))
            errors[l] = [position_error, tilt_error]
            pos.append(position_error)
            tilt.append(tilt_error)
            if stance:
                slip.append(float(np.linalg.norm(rotate @ actual + shift - anchor)))
            angles.update(zip(leg.names, map(float, q[l][k])))
        frames.append(angles)
        roots.append((rotate, shift))
        support.append(errors)
    failures, stats = [], {}
    limits = {j.get('name'): float(j.find('limit').get('velocity')) for j in ET.parse(config['urdf']).getroot().findall('joint') if j.find('limit') is not None}
    for l, leg in legs.items():
        margin = np.minimum(q[l] - leg.lo, leg.hi - q[l]).min(0)
        velocity = np.abs(np.diff(q[l], axis=0) / dt).max(0)
        seam = float(np.abs(q[l][-1] - q[l][0]).max())
        stats[l] = {'joints': leg.names, 'q_min_rad': q[l].min(0).tolist(), 'q_max_rad': q[l].max(0).tolist(),
                    'margin_rad': margin.tolist(), 'velocity_rad_s': velocity.tolist(), 'seam_rad': seam}
        if margin.min() < config['limit_margin_rad']:
            failures.append(f'{l}: joint margin')
        if np.any(velocity > config['velocity_fraction'] * np.array([limits[nm] for nm in leg.names])):
            failures.append(f'{l}: velocity')
        if np.abs(np.diff(q[l], axis=0)).max() > config['max_frame_step_rad']:
            failures.append(f'{l}: discontinuity')
        if seam > 1e-6:
            failures.append(f'{l}: seam')
    if max(pos) > config['pos_tol_m']:
        failures.append('position residual')
    if max(tilt) > config['tilt_tol_deg']:
        failures.append('palm tilt')
    worst = {}
    # Every solved frame, including seam; no coarse collision subsampling.
    for k, angles in enumerate(frames):
        for row in detector.check(angles):
            key = '~'.join(row['pair'])
            if key not in worst or row['gap_lower_m'] < worst[key]['gap_lower_m']:
                worst[key] = dict(row, frame=k)
    collision_rows = sorted(worst.values(), key=lambda x: x['gap_lower_m'])
    if any(row['fail'] for row in collision_rows):
        failures.append('collision clearance')
    names = [nm for leg in legs.values() for nm in leg.names]
    with (out / f'{name}.csv').open('x', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['t_s'] + names + [f'root_r{i}{j}' for i in range(3) for j in range(3)] + ['root_x_m', 'root_y_m', 'root_z_m'] + [f'{l}_{field}' for l in LEGS for field in ('residual_m', 'tilt_deg')])
        for k, angles in enumerate(frames):
            r, p = roots[k]
            writer.writerow([k * dt] + [angles[nm] for nm in names] + r.ravel().tolist() + p.tolist() + [value for l in LEGS for value in support[k][l]])
    row = {'name': name, 'status': 'FAIL' if failures else 'PASS_SAMPLED_GEOMETRY_ONLY', 'failures': failures,
           'frames': n + 1, 'max_position_residual_m': max(pos), 'max_palm_tilt_deg': max(tilt),
           'max_stance_world_error_m': max(slip), 'legs': stats, 'collision_pairs': len(detector.pairs),
           'collision_closest': collision_rows[:12]}
    print('SCENARIO', name, row['status'], f'position={max(pos):.6g}m tilt={max(tilt):.6g}deg', flush=True)
    return row, frames


def hinge_boundaries(urdf, legs, detector, config, contexts):
    report = []
    for l, leg in legs.items():
        upper, lower = leg.spec[2]['origin'], leg.spec[3]['origin']
        axis = leg.axes[2] / np.linalg.norm(leg.axes[2])
        straight = float(np.arctan2(np.dot(np.cross(lower, upper), axis), np.dot(lower, upper)))
        fold = straight - np.sign(straight) * np.pi
        name = leg.names[2]
        mechanical = {'joint': name, 'limits_rad': [float(leg.lo[2]), float(leg.hi[2])],
                      'straight_rad': straight, 'fold_rad': float(fold),
                      'straight_inside_limits': bool(leg.lo[2] <= straight <= leg.hi[2]),
                      'fold_inside_limits': bool(leg.lo[2] <= fold <= leg.hi[2]),
                      'contexts': []}
        for label, base in contexts:
            samples = np.linspace(leg.lo[2], leg.hi[2], config['boundary_samples'])
            observed = []
            for angle in samples:
                pose = dict(base, **{name: float(angle)})
                # Preserve all pairs: combined contexts can expose interference away from this leg.
                rows = detector.check(pose)
                failed = [row for row in rows if row['fail']]
                observed.append({'q_rad': float(angle), 'fail': bool(failed), 'pairs': failed[:4]})
            brackets = []
            for previous, current in zip(observed, observed[1:]):
                if previous['fail'] == current['fail']:
                    continue
                a, b = previous['q_rad'], current['q_rad']
                fail_a = previous['fail']
                while b - a > config['boundary_resolution_rad']:
                    mid = (a + b) / 2
                    failed = any(row['fail'] for row in detector.check(dict(base, **{name: mid})))
                    if failed == fail_a:
                        a = mid
                    else:
                        b = mid
                brackets.append({'lo_rad': a, 'hi_rad': b, 'fail_at_lo': fail_a})
            mechanical['contexts'].append({'name': label, 'fixed_angles_rad': base, 'samples': observed, 'transition_brackets': brackets})
        report.append(mechanical)
        print('BOUNDARY', name, f'straight={straight:.6g} fold={fold:.6g}', flush=True)
    return report


def pitch_multistart(urdf, config):
    """Retry both prescribed pitch peaks [rad] with 32 starts; report position [m] and tilt [deg]."""
    rows = []
    for sign in (-1, 1):
        rotate = gait.rotation(np.array([0., 1., 0.]), sign * np.radians(config['recovery_angle_deg']))
        for l in LEGS:
            leg = gait.Leg(urdf, l)
            point = rotate.T @ leg.neutral_sole
            up = rotate.T @ np.array([0., 0., 1.])
            candidates = []

            def residual(q):
                actual, normal = leg.sole(q)
                weight = config['pos_tol_m'] / np.radians(config['tilt_tol_deg'])
                return np.r_[actual - point, weight * (normal - up)]

            for seed in range(32):
                result = least_squares(residual, np.random.default_rng(seed).uniform(leg.lo, leg.hi),
                                       bounds=(leg.lo, leg.hi), xtol=1e-12, ftol=1e-12, gtol=1e-12)
                actual, normal = leg.sole(result.x)
                error = float(np.linalg.norm(actual - point))
                tilt = float(np.degrees(np.arccos(np.clip(np.dot(normal, up), -1., 1.))))
                if error <= config['pos_tol_m']:
                    candidates.append((tilt, error))
            best = min(candidates) if candidates else (None, None)
            rows.append({'sign': sign, 'leg': l, 'starts': 32, 'best_position_m': best[1],
                         'best_tilt_deg': best[0], 'failed': best[0] is None or best[0] > config['tilt_tol_deg']})
    return rows


def sampled_envelope(legs, scenarios):
    accepted = [case for case in scenarios if not case['failures']]
    if not accepted:
        return {}
    return {nm: [min(case['legs'][l]['q_min_rad'][i] for case in accepted),
                 max(case['legs'][l]['q_max_rad'][i] for case in accepted)]
            for l, leg in legs.items() for i, nm in enumerate(leg.names)}


def collision_replay(source, out, detector, urdf, legs, config):
    """Recheck collisions on existing trajectories [rad], retaining source kinematic verdicts."""
    report = json.loads((source / 'report.json').read_text())
    assert report['completed'] and report.get('purpose') is None
    assert report['identity']['files'][config['urdf']] == gait.binding.sha256_file(Path(config['urdf']))
    for path in detector.mesh_paths:
        assert report['identity']['files'][str(path.resolve())] == gait.binding.sha256_file(path)
    assert {k: v for k, v in report['config'].items() if k != 'urdf'} == {k: v for k, v in config.items() if k != 'urdf'}
    source_hashes = {str((source / 'report.json').resolve()): gait.binding.sha256_file(source / 'report.json')}
    for case in report['scenarios']:
        trajectory = source / f'{case["name"]}.csv'
        source_hashes[str(trajectory.resolve())] = gait.binding.sha256_file(trajectory)
        with trajectory.open() as handle:
            frames = [{nm: float(row[nm]) for leg in legs.values() for nm in leg.names}
                      for row in csv.DictReader(handle)]
        assert len(frames) == case['frames']
        assert all(np.isfinite(list(angles.values())).all() for angles in frames), 'non-finite trajectory'
        worst = {}
        for k, angles in enumerate(frames):
            for row in detector.check(angles):
                key = '~'.join(row['pair'])
                if key not in worst or row['gap_lower_m'] < worst[key]['gap_lower_m']:
                    worst[key] = dict(row, frame=k)
        case['collision_closest'] = sorted(worst.values(), key=lambda x: x['gap_lower_m'])[:12]
        case['failures'] = [failure for failure in case['failures'] if failure != 'collision clearance']
        if any(row['fail'] for row in worst.values()):
            case['failures'].append('collision clearance')
        case['status'] = 'FAIL' if case['failures'] else 'PASS_SAMPLED_GEOMETRY_ONLY'
        (out / trajectory.name).write_bytes(trajectory.read_bytes())
        (out / f'{case["name"]}.json').write_text(json.dumps(case, indent=1))
        print('COLLISION_REPLAY', case['name'], case['status'], flush=True)
    contexts = [(row['name'], row['fixed_angles_rad']) for row in report['hinge_boundaries'][0]['contexts']]
    report['hinge_boundaries'] = hinge_boundaries(urdf, legs, detector, config, contexts)
    assert all(gait.binding.sha256_file(Path(p)) == h for p, h in source_hashes.items())
    report['trajectory_source'] = {'directory': str(source.resolve()), 'files': source_hashes,
                                 'identity': report['identity']}
    report['sampled_envelope_rad'] = sampled_envelope(legs, report['scenarios'])
    report['status'] = ('TARGET_FAILURES_RECORDED' if any(case['failures'] for case in report['scenarios'])
                        else 'PASS_SAMPLED_GEOMETRY_ONLY')
    return report


def self_check(break_crossing=False):
    from scipy.spatial import ConvexHull
    def box(scale, shift):
        v = np.array(list(itertools.product((-1., 1.), repeat=3))) * scale + shift
        hull = ConvexHull(v)
        f = hull.simplices.copy()
        for k, indices in enumerate(f):
            tri = v[indices]
            if np.dot(np.cross(tri[1] - tri[0], tri[2] - tri[0]), hull.equations[k, :3]) < 0:
                f[k, [1, 2]] = f[k, [2, 1]]
        return v, f
    va, fa = box(np.array([1., .1, .1]), np.zeros(3))
    vb, fb = box(np.array([.1, 1., .1]), np.zeros(3))
    crossing = False if break_crossing else surface_crosses(va, fa, vb, fb)
    assert crossing, 'edge/face crossing must be detected without contained vertices'
    assert not any(inside(p, vb, fb) for p in va), 'fixture must exclude vertex containment'
    small, fs = box(np.array([.02, .02, .02]), np.zeros(3))
    assert inside(small[0], va, fa), 'enclosed solid must be detected'
    outside, fo = box(np.array([.02, .02, .02]), np.array([4., 0., 0.]))
    compound_v, compound_f = np.concatenate([outside, small]), np.concatenate([fo, fs + len(outside)])
    assert not inside(compound_v[0], va, fa), 'first component must be outside'
    assert any(inside(compound_v[i], va, fa) for i in component_representatives(compound_v, compound_f)), 'second component containment'
    distant, fd = box(np.array([1., .1, .1]), np.array([3., 0., 0.]))
    assert not surface_crosses(va, fa, distant, fd)
    assert abs(surface_distance(va, fa, distant, fd) - 1.) < 1e-10, 'parallel surfaces gap'
    # Edge/edge interior minimum: perpendicular skew segments separated by 0.25 m.
    tri_a = np.array([[-1., 0., 0.], [1., 0., 0.], [1., -1., 0.]])
    tri_b = np.array([[0., -1., .25], [0., 1., .25], [-1., 1., .25]])
    assert abs(surface_distance(tri_a, np.array([[0, 1, 2]]), tri_b, np.array([[0, 1, 2]])) - .25) < 1e-10
    print('PALM_5B_SELF_CHECK_OK', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--urdf', type=Path)
    parser.add_argument('--config', type=Path, default=HERE.with_name('palm_5b_targets.json'))
    parser.add_argument('--output_dir', type=Path)
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--break_crossing', action='store_true')
    parser.add_argument('--pitch_multistart', action='store_true', help='only retry both pitch peaks with 32 starts per leg')
    parser.add_argument('--collision_replay', type=Path, help='recheck existing full-run collision evidence, retaining kinematics')
    args = parser.parse_args()
    if args.self_check:
        self_check(args.break_crossing)
        return
    if args.urdf is None or args.output_dir is None:
        parser.error('--urdf and --output_dir required')
    out = args.output_dir.resolve()
    assert REPO / 'rl_exp/out' in out.parents, 'output must stay under rl_exp/out'
    config = json.loads(args.config.read_text())
    assert config['frames_per_period'] >= 20 and config['boundary_samples'] >= 3
    assert 0 < config['stance_fraction'] < 1 and config['period_s'] > 0
    assert config['clearance_m'] > 0 and config['boundary_resolution_rad'] > 0
    assert config['pos_tol_m'] > 0 and config['tilt_tol_deg'] > 0
    validate_geometry(args.urdf)
    urdf = gait.csc.load_urdf(args.urdf.resolve())
    legs = {l: gait.Leg(urdf, l) for l in LEGS}
    detector = Collision(urdf, config['clearance_m'])
    out.mkdir(parents=True, exist_ok=False)
    config['urdf'] = str(args.urdf.resolve())
    sources = [HERE, args.config, Path(gait.__file__), Path(gait.csc.__file__), args.urdf,
               REPO / 'rl_exp/tools/verify/check_leg_reachability.py',
               REPO / 'rl_exp/tasks/joint_names.py', Path(gait.binding.__file__)] + detector.mesh_paths
    hashes = {str(p.resolve()): gait.binding.sha256_file(p) for p in sources}
    identity = {'revision': gait.binding.git_rev(REPO), 'files': hashes,
                'connection_exclusions': [sorted(pair) for pair in sorted(gait.APPROVED, key=lambda p: sorted(p))]}
    for path in sources:
        if path.suffix not in ('.py', '.json'):
            continue
        target = out / 'source_snapshot' / path.resolve().relative_to(REPO)
        if target.suffix == '.py':
            target = target.with_suffix('.py.txt')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    (out / 'launch_identity.json').write_text(json.dumps(identity, indent=1))
    report = {'config': config, 'identity': identity, 'scenarios': [], 'completed': False}
    if args.collision_replay:
        assert not args.pitch_multistart
        report = collision_replay(args.collision_replay.resolve(), out, detector, urdf, legs, config)
        report['identity'] = identity
        assert all(gait.binding.sha256_file(p) == hashes[str(p.resolve())] for p in sources)
        (out / 'report.json').write_text(json.dumps(report, indent=1))
        print('PALM_5B_REPLAY', report['status'], out, flush=True)
        raise SystemExit(1 if any(case['failures'] for case in report['scenarios']) else 0)
    if args.pitch_multistart:
        rows = pitch_multistart(urdf, config)
        report.update(purpose='pitch_peak_multistart_only', pitch_multistart=rows, completed=True)
        assert all(gait.binding.sha256_file(p) == hashes[str(p.resolve())] for p in sources)
        (out / 'report.json').write_text(json.dumps(report, indent=1))
        for row in rows:
            print('PITCH_MULTISTART', row, flush=True)
        raise SystemExit(1 if any(row['failed'] for row in rows) else 0)
    contexts = [('neutral', {})]
    for name in ['straight', 'turn_pos', 'turn_neg'] + [f'recover_{axis}_{sign}' for axis in ('y', 'z', 'roll', 'pitch') for sign in ('pos', 'neg')]:
        row, frames = scenario(name, urdf, legs, detector, config, out)
        report['scenarios'].append(row)
        # One actual combined pose per case: maximum norm of joint excursion; never synthesize extrema.
        k = max(range(len(frames)), key=lambda i: sum(v * v for v in frames[i].values()))
        contexts.append((f'{name}_frame_{k}', frames[k]))
        (out / f'{name}.json').write_text(json.dumps(row, indent=1))
    report['hinge_boundaries'] = hinge_boundaries(urdf, legs, detector, config, contexts)
    report['sampled_envelope_rad'] = sampled_envelope(legs, report['scenarios'])
    assert all(gait.binding.sha256_file(p) == hashes[str(p.resolve())] for p in sources), 'input/code changed during run'
    report['completed'] = True
    report['status'] = 'TARGET_FAILURES_RECORDED' if any(row['failures'] for row in report['scenarios']) else 'PASS_SAMPLED_GEOMETRY_ONLY'
    (out / 'report.json').write_text(json.dumps(report, indent=1))
    print('PALM_5B', report['status'], out, flush=True)
    raise SystemExit(1 if report['status'] == 'TARGET_FAILURES_RECORDED' else 0)


if __name__ == '__main__':
    main()
