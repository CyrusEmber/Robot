# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Explain restored palm recovery and map coupled elbow/wrist interference [m, rad, s].

Analyzes the HISTORICAL flat-palm sample only. Its 2-degree criterion is not a full-cycle motion
requirement; the user clarified that the palm must tilt and paddle during motion on 2026-10-14.
An impossible historical target is not evidence that the robot needs different axes or more DOFs.
Uses the same engineering targets as the historical 5b sample, without changing the asset or PD. For this
vertical-yaw plus three-parallel-hinge chain, position fixes the leg plane within a narrow yaw
interval. The palm normal is perpendicular to that plane axis. Therefore asin(abs(axis_world.z))
is a tilt lower bound even if the remaining hinges have unlimited rotation. Bounds optimize over
ALL yaw intervals allowed by the sole-position tolerance, not over numerical IK starts.

Elbow/wrist maps hold the other joints at zero. They distinguish 5 mm clearance, actual solid
overlap and a historical level-palm sample subset. That subset is not the permitted paddle phase.
Slices are not a full-domain safe box or hardware ROM.
Unsupported axes/frames fail before any claimed bound. Output directory must be fresh under rl_exp/out.
"""

import argparse
import json
from pathlib import Path

import numpy as np

import palm_motion_boundaries as motion

HERE = Path(__file__).resolve()


def trig_intervals(a: float, b: float, h: float, epsilon: float,
                   low: float, high: float) -> list[tuple[float, float]]:
    """Intervals [rad] with abs(a*cos(yaw)+b*sin(yaw)-h) <= epsilon; lengths [m]."""
    radius = np.hypot(a, b)
    if radius < 1e-15:
        return [(low, high)] if abs(h) <= epsilon else []
    phase = np.arctan2(b, a)
    cuts = [low, high]
    for value in (h - epsilon, h + epsilon):
        if abs(value) > radius:
            continue
        delta = np.arccos(np.clip(value / radius, -1., 1.))
        for root in (phase - delta, phase + delta):
            for k in range(-3, 4):
                q = root + k * 2 * np.pi
                if low < q < high:
                    cuts.append(float(q))
    cuts = sorted(set(cuts))
    intervals = [(x, y) for x, y in zip(cuts, cuts[1:])
                 if abs(a * np.cos((x + y) / 2) + b * np.sin((x + y) / 2) - h) <= epsilon]
    # Preserve a feasible isolated endpoint (zero-width position budget also has isolated roots).
    for q in cuts:
        if abs(a * np.cos(q) + b * np.sin(q) - h) <= epsilon + 1e-14:
            if not any(x <= q <= y for x, y in intervals):
                intervals.append((q, q))
    return intervals


def trig_min_abs(a: float, b: float, intervals: list[tuple[float, float]]) -> float:
    """Minimum abs(a*cos(yaw)+b*sin(yaw)) over intervals [rad]."""
    candidates = []
    phase = np.arctan2(b, a)
    for low, high in intervals:
        angles = [low, high]
        for k in range(-6, 7):
            q = phase + k * np.pi / 2
            if low <= q <= high:
                angles.append(float(q))
        candidates.extend(abs(a * np.cos(q) + b * np.sin(q)) for q in angles)
    return float(min(candidates)) if candidates else float('inf')


def plane_parameters(leg: motion.gait.Leg) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Validate the planar chain; return pivot [m], local axis, yaw sign and invariant offset [m]."""
    axes = [axis / np.linalg.norm(axis) for axis in leg.axes]
    assert abs(abs(axes[0][2]) - 1) < 1e-12, 'first axis must be vertical'
    assert np.linalg.norm(axes[0][:2]) < 1e-12, 'first axis must be vertical'
    assert all(np.linalg.norm(axis - axes[1]) < 1e-12 for axis in axes[1:]), 'hinge axes must be parallel'
    assert abs(axes[1][2]) < 1e-12, 'hinge axis must be horizontal'
    assert abs(np.dot(axes[1], np.array([0., 0., 1.]))) < 1e-12
    sign = float(axes[0][2])
    pivot = leg.root[:3, 3] + leg.root[:3, :3] @ leg.spec[0]['origin']
    h = float(np.dot(axes[1], sum((spec['origin'] for spec in leg.spec[1:]), leg.sole_local.copy())))
    return pivot, axes[1], sign, h


def tilt_bound(leg: motion.gait.Leg, point: np.ndarray, root: np.ndarray,
               position_tolerance: float) -> dict:
    """Minimum necessary palm tilt [deg] at a body sole target [m] and prescribed root rotation."""
    pivot, axis, sign, offset = plane_parameters(leg)
    delta = leg.root[:3, :3].T @ (point - pivot)
    low, high = sorted([sign * leg.lo[0], sign * leg.hi[0]])
    # Unit axis projection cannot amplify a Euclidean position error. Tiny numeric slack makes
    # the yaw set conservative rather than claiming more than floating-point precision supports.
    intervals = trig_intervals(axis[0] * delta[0] + axis[1] * delta[1],
                              axis[0] * delta[1] - axis[1] * delta[0], offset,
                              position_tolerance + 1e-10, low, high)
    row = (root @ leg.root[:3, :3])[2]
    a = row[0] * axis[0] + row[1] * axis[1]
    b = -row[0] * axis[1] + row[1] * axis[0]
    minimum = trig_min_abs(a, b, intervals)
    return {'yaw_intervals_rad': [[float(x / sign), float(y / sign)] for x, y in intervals],
            'position_projection_offset_m': offset,
            'min_necessary_tilt_deg': None if not intervals else float(np.degrees(np.arcsin(np.clip(minimum, 0., 1.)))),
            'position_projection_possible': bool(intervals)}


def verify_projection(leg: motion.gait.Leg, urdf: dict, negate_yaw: bool = False) -> float:
    """Compare the analytic projection and normal invariant against URDF FK at 64 states [rad]."""
    pivot, axis, sign, offset = plane_parameters(leg)
    maximum = 0.
    rng = np.random.default_rng(19014)
    for q in rng.uniform(leg.lo, leg.hi, size=(64, 4)):
        angles = dict(zip(leg.names, map(float, q)))
        pose = motion.gait.csc.fk(urdf['joints'], leg.link, angles)
        point = pose[:3, :3] @ leg.sole_local + pose[:3, 3]
        yaw = (-1 if negate_yaw else 1) * sign * q[0]
        world_axis = leg.root[:3, :3] @ motion.gait.rotation(np.array([0., 0., 1.]), yaw) @ axis
        residual = abs(float(np.dot(world_axis, point - pivot)) - offset)
        normal_residual = abs(float(np.dot(world_axis, pose[:3, 2])))
        maximum = max(maximum, residual, normal_residual)
    assert maximum < 1e-8, f'plane/FK invariant mismatch: {maximum}'
    return maximum


def coupled_map(leg: motion.gait.Leg, detector: motion.Collision,
                config: dict, output: Path) -> dict:
    """Sample elbow/wrist positions [rad], solid overlap and level-palm phase constraints [deg]."""
    elbows = np.linspace(leg.lo[2], leg.hi[2], config['boundary_samples'])
    wrists = np.linspace(leg.lo[3], leg.hi[3], config['boundary_samples'] // 4 + 1)
    gaps, solid, tilt = [], [], []
    clearance_brackets, solid_brackets = [], []
    for wrist in wrists:
        gap_row, solid_row, tilt_row = [], [], []
        for elbow in elbows:
            angles = {leg.names[2]: float(elbow), leg.names[3]: float(wrist)}
            rows = detector.check(angles)
            gap_row.append(min(row['gap_lower_m'] for row in rows))
            solid_row.append(any(row.get('intersects', False) or row.get('contained', False) for row in rows))
            _, normal = leg.sole(np.array([0., 0., elbow, wrist]))
            tilt_row.append(float(np.degrees(np.arccos(np.clip(normal[2], -1., 1.)))))
        gaps.append(gap_row)
        solid.append(solid_row)
        tilt.append(tilt_row)
        for mode, flags, target in (
                ('clearance', np.array(gap_row) < config['clearance_m'], clearance_brackets),
                ('solid', solid_row, solid_brackets)):
            for k in range(len(elbows) - 1):
                if flags[k] == flags[k + 1]:
                    continue
                low, high = elbows[k:k + 2]
                start_fail = bool(flags[k])
                while high - low > config['boundary_resolution_rad']:
                    middle = (low + high) / 2
                    rows = detector.check({leg.names[2]: float(middle), leg.names[3]: float(wrist)})
                    failed = (any(row['fail'] for row in rows) if mode == 'clearance' else
                              any(row.get('intersects', False) or row.get('contained', False) for row in rows))
                    if failed == start_fail:
                        low = middle
                    else:
                        high = middle
                target.append({'wrist_rad': float(wrist), 'lo_elbow_rad': float(low),
                               'hi_elbow_rad': float(high), 'fail_at_lo': start_fail})
        print('COUPLED_MAP', leg.leg, f'wrist={wrist:.4f}', flush=True)
    gap_array, tilt_array, solid_array = np.array(gaps), np.array(tilt), np.array(solid)
    rows = {'leg': leg.leg, 'fixed_other_angles_rad': 0., 'elbow_rad': elbows.tolist(),
            'wrist_rad': wrists.tolist(), 'clearance_lower_m': gaps, 'solid_overlap': solid,
            'palm_tilt_deg': tilt, 'clearance_brackets': clearance_brackets,
            'solid_brackets': solid_brackets,
            'level_phase_samples': int((tilt_array <= config['tilt_tol_deg']).sum()),
            'level_phase_collisions': int(((tilt_array <= config['tilt_tol_deg']) &
                                           (gap_array < config['clearance_m'])).sum()),
            'solid_samples': int(solid_array.sum())}
    (output / f'{leg.leg}_coupled.json').write_text(json.dumps(rows, indent=1))
    return rows


def plot_maps(maps: list[dict], config: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(maps), figsize=(11, 4), sharey=True)
    for ax, row in zip(np.atleast_1d(axes), maps):
        gaps = np.array(row['clearance_lower_m'])
        level = np.array(row['palm_tilt_deg']) <= config['tilt_tol_deg']
        solid = np.array(row['solid_overlap'])
        # 0 clear, 1 below clearance, 2 solid overlap; white line marks level-palm phase.
        classes = np.where(solid, 2, np.where(gaps < config['clearance_m'], 1, 0))
        ax.pcolormesh(row['elbow_rad'], row['wrist_rad'], classes, vmin=0, vmax=2,
                      cmap=plt.matplotlib.colors.ListedColormap(['#4c956c', '#f7b32b', '#d1495b']), shading='nearest')
        ax.contour(row['elbow_rad'], row['wrist_rad'], level.astype(float), levels=[.5], colors=['white'])
        ax.set_title(f'{row["leg"]}: green clear / amber <5 mm / red overlap')
        ax.set_xlabel('elbow [rad]')
        ax.set_ylabel('wrist [rad]')
    fig.suptitle('Other joints zero; white boundary: palm tilt <= 2 deg. Sampled slices only.')
    fig.tight_layout()
    fig.savefig(output / 'coupled_boundaries.png', dpi=150)
    plt.close(fig)


def self_check() -> None:
    intervals = trig_intervals(1., 0., 0., .1, -.6, .6)
    assert not intervals, 'cos(yaw) cannot approach zero in this interval'
    intervals = trig_intervals(0., 1., 0., .1, -.6, .6)
    assert abs(intervals[0][0] + np.arcsin(.1)) < 1e-12
    assert abs(intervals[0][1] - np.arcsin(.1)) < 1e-12
    assert abs(trig_min_abs(0., 1., intervals)) < 1e-12
    assert abs(trig_min_abs(1., 0., intervals) - np.sqrt(.99)) < 1e-12
    print('RECOVERY_CONSTRAINTS_SELF_CHECK_OK', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source_report_dir', type=Path)
    parser.add_argument('--output_dir', type=Path)
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--break_yaw', action='store_true')
    args = parser.parse_args()
    self_check()
    if args.self_check and args.source_report_dir is None:
        return
    if args.source_report_dir is None or args.output_dir is None:
        parser.error('--source_report_dir and --output_dir required')
    source = args.source_report_dir.resolve() / 'report.json'
    original = json.loads(source.read_text())
    assert original['completed']
    config = original['config']
    urdf_path = Path(config['urdf'])
    motion.validate_geometry(urdf_path)
    urdf = motion.gait.csc.load_urdf(urdf_path)
    legs = {l: motion.gait.Leg(urdf, l) for l in motion.LEGS}
    detector = motion.Collision(urdf, config['clearance_m'])
    sources = [HERE, Path(motion.__file__), Path(motion.gait.__file__), Path(motion.gait.csc.__file__),
               Path(motion.gait.binding.__file__), source, urdf_path] + detector.mesh_paths
    hashes = {str(p.resolve()): motion.gait.binding.sha256_file(p) for p in sources}
    for p in [urdf_path] + detector.mesh_paths:
        assert hashes[str(p.resolve())] == original['identity']['files'][str(p.resolve())], 'source input changed'
    invariants = {l: verify_projection(leg, urdf, args.break_yaw) for l, leg in legs.items()}
    output = args.output_dir.resolve()
    assert motion.REPO / 'rl_exp/out' in output.parents
    output.mkdir(parents=True, exist_ok=False)
    for p in sources:
        if p.suffix != '.py':
            continue
        target = output / 'source_snapshot' / p.resolve().relative_to(motion.REPO)
        target = target.with_suffix('.py.txt')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
    peaks = []
    for axis in ('roll', 'pitch'):
        for sign in (-1., 1.):
            root = motion.gait.rotation(np.eye(3)[0 if axis == 'roll' else 1],
                                        sign * np.radians(config['recovery_angle_deg']))
            for l, leg in legs.items():
                result = tilt_bound(leg, root.T @ leg.neutral_sole, root, config['pos_tol_m'])
                result.update(leg=l, root_axis=axis, root_angle_deg=sign * config['recovery_angle_deg'])
                result['tilt_target_impossible'] = (not result['position_projection_possible'] or
                                                   result['min_necessary_tilt_deg'] > config['tilt_tol_deg'])
                peaks.append(result)
                print('TILT_BOUND', l, axis, sign, result['min_necessary_tilt_deg'], flush=True)
    maps = [coupled_map(legs[l], detector, config, output) for l in ('lf', 'rf')]
    plot_maps(maps, config, output)
    assert all(motion.gait.binding.sha256_file(p) == hashes[str(p.resolve())] for p in sources)
    report = {'completed': True, 'status': 'DIAGNOSTIC_FINDINGS_ONLY', 'config': config,
              'assumption_scope': 'historical_flat_palm_sample_only_not_full_cycle_acceptance',
              'identity': {'revision': motion.gait.binding.git_rev(motion.REPO), 'files': hashes},
              'plane_invariant_residual': invariants, 'recovery_peak_bounds': peaks, 'coupled_maps': maps}
    (output / 'report.json').write_text(json.dumps(report, indent=1))
    print('PALM_RECOVERY_CONSTRAINTS_COMPLETE', output, flush=True)


if __name__ == '__main__':
    main()
