# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Correct sampled stance material positions with a prescribed horizontal root [m, rad].

Use --source_report <support report> --root_report <prior replay analysis> --output_dir
<fresh rl_exp/out directory>. Reuse the source grid, five-axis solver limits/budget,
complete collision set and numerical position tolerance. Each stance keeps one actual
front-edge material vertex on the ground and retains the contact edge's horizontal
heading; its palm may pitch/roll. Swing preserves source
mesh clearance and smoothly joins stance XY offsets. No physical time or new asset.
Stops at the first solver/geometry failure; renders with local_path_view separately.
"""

import argparse
import json
from pathlib import Path

import numpy as np

import local_path_check as check

view, probe = check.view, check.probe


def _contact_target(c, local_c, sample, material_index):
    """Return one stance material target or a smooth swing XY/minimum-height target [m]."""
    touch = c - local_c
    anchor = sample(touch, material_index)[0].copy()
    anchor[2] = 0.
    if local_c <= 5 / 8:
        return {'point_xy_m': anchor[:2], 'minimum_z_m': 0., 'anchor_m': anchor}
    u = (local_c - 5 / 8) / (3 / 8)
    h = u ** 3 * (10 + u * (-15 + 6 * u))
    point, height = sample(c, material_index)
    lift, _ = sample(touch + 5 / 8, material_index)
    touchdown, _ = sample(touch + 1, material_index)
    # Horizontal offsets only: preserve the original swing's resolved mesh clearance.
    offset = (1 - h) * (anchor[:2] - lift[:2])
    return {'point_xy_m': point[:2] + offset, 'minimum_z_m': height, 'anchor_m': None}


def _contact_residual(model, q, previous, root, shift, index, target, config):
    pose = model.pose(q)
    point = root[:3, :3] @ (pose[:3, :3] @ model.vertices[index] + pose[:3, 3]) + root[:3, 3] + shift
    height = probe._static_ground(model.vertices, pose, root)['height_m']
    horizontal = point[:2] - target['point_xy_m']
    errors = np.r_[horizontal, height - target['minimum_z_m']]
    if target['anchor_m'] is not None:
        errors = np.r_[errors, point[2] - target['anchor_m'][2]]
        if 'heading_vertex' in target:
            other = root[:3, :3] @ (pose[:3, :3] @ model.vertices[target['heading_vertex']] + pose[:3, 3])
            other += root[:3, 3] + shift
            edge = other[:2] - point[:2]
            direction = target['heading_xy']
            errors = np.r_[errors, edge[0] * direction[1] - edge[1] * direction[0]]
    return np.r_[errors / config['position_tolerance_m'], (q - previous) * 1e-4]


def _solve_contact(residual, seed, lo, hi, config):
    """Let least-squares converge within the existing call budget [rad]."""
    lower = np.maximum(lo, seed - config['joint_step_rad'])
    upper = np.minimum(hi, seed + config['joint_step_rad'])
    attempts = []
    candidate = seed.copy()
    for start in (seed, np.zeros(len(seed)), seed + np.linspace(-.01, .01, len(seed))):
        count, best_error = 0, float('inf')
        best = seed.copy()
        def counted(q):
            nonlocal count, best_error, best
            if count >= config['evaluations_per_attempt']:
                raise StopIteration
            count += 1
            value = residual(q)
            error = float(np.linalg.norm(value[:-len(seed)]))
            if error < best_error:
                best_error, best = error, q.copy()
            return value
        exhausted = False
        try:
            result = probe.least_squares(counted, np.clip(start, lower + 1e-12, upper - 1e-12),
                                         bounds=(lower, upper), max_nfev=config['evaluations_per_attempt'],
                                         xtol=1e-10, ftol=1e-10, gtol=1e-10)
            candidate = result.x
        except StopIteration:
            exhausted, candidate = True, best
        error = float(np.linalg.norm(residual(candidate)[:-len(seed)]))
        attempts.append({'evaluations': count, 'budget_exhausted': exhausted,
                         'best_scaled_position_error': error, 'q_rad': candidate.tolist()})
        if error <= 1:
            return candidate, attempts, False
    return candidate, attempts, True


def _run(source_path, root_path, output, anchor='front_contact', early_stop=False, orientation='contact_heading'):
    assert view.REPO / 'rl_exp/out' in output.parents and not output.exists(), 'fresh isolated output required'
    source_path, root_path = view.artifact_path(source_path), view.artifact_path(root_path)
    source, _, _, _, _ = view._load(source_path)
    assert source['mode'] == 'sampled_local_path_support_schedule'
    root_report = json.loads(root_path.read_text(encoding='utf-8'))
    assert root_report['source_report_sha256'] == view.digest(source_path), 'root/source mismatch'
    assert root_report['source_identity'] == source['identity'], 'root candidate mismatch'
    original = source['legs']['combined']
    rows = original['rows']
    assert original['completed_combined_loop'] and original['failure'] is None and len(rows) <= 129
    parameters = [r['s'] for r in rows]
    root_data = root_report['root_translation']
    assert root_data['root_applied'] and root_data['c'] == parameters
    shifts = np.array(root_data['offsets_m'], dtype=float)
    assert shifts.shape == (len(rows), 3) and np.isfinite(shifts).all()
    assert np.all(shifts[:, 2] == 0) and np.all(shifts[0] == 0)
    build_path = view.artifact_path(Path(source['identity']['build_report']))
    build, models, urdf, zero, collision, excluded, root, _, _, identity = probe._static_prepare(build_path)
    assert all(value == source['identity'][key] for key, value in identity.items() if key != 'code_sha256')
    assert all(source['identity']['code_sha256'].get(path) == sha for path, sha in identity['code_sha256'].items())
    assert root.tolist() == source['root_transform']
    assert source['checked_pairs'] == [list(p) for p in collision.pairs] and source['excluded_pairs'] == excluded
    config = source['source_config']
    assert config['position_tolerance_m'] == 1e-5 and config['joint_step_rad'] == .05
    assert config['evaluations_per_attempt'] == 200 and config['attempts_per_point'] == 3
    indices, samplers, heading_vertices = {}, {}, {}
    for leg, model in models.items():
        touch = 0. if leg in ('lf', 'rr') else .5
        index = parameters.index(touch)
        indices[leg] = rows[index]['legs'][leg]['state']['palm_lowest_vertex']['vertex_index']
        heading_vertices[leg] = indices[leg]
        pose = root @ model.pose(np.array([rows[index]['q_rad'][n] for n in model.names]))
        world = model.vertices @ pose[:3, :3].T + pose[:3, 3]
        patch = np.flatnonzero(world[:, 2] <= world[:, 2].min() + config['position_tolerance_m'])
        if anchor == 'front_contact':
            indices[leg] = int(max(patch, key=lambda j: (world[j, 0], world[j, 1], int(j))))

        def sample(c, vertex, model=model, leg=leg):
            cycle = int(np.floor(c))
            i = parameters.index(c - cycle)
            q = np.array([rows[i]['q_rad'][n] for n in model.names])
            pose = root @ model.pose(q)
            point = model.vertices[vertex] @ pose[:3, :3].T + pose[:3, 3] + shifts[i] + cycle * shifts[-1]
            return point, rows[i]['legs'][leg]['state']['task_m'][2]

        samplers[leg] = sample
    corrected, failure, first_q = [], None, None
    for i, row in enumerate(rows):
        q, targets, attempts, failures = dict(zero), {}, {}, []
        for leg, model in models.items():
            seed = np.array([row['q_rad'][n] for n in model.names])
            target = _contact_target(row['s'], row['legs'][leg]['local_c'], samplers[leg], indices[leg])
            if target['anchor_m'] is not None and orientation == 'contact_heading':
                other, _ = samplers[leg](row['s'] - row['legs'][leg]['local_c'], heading_vertices[leg])
                edge = other[:2] - target['point_xy_m']
                assert np.linalg.norm(edge) > 0, 'heading feature coincides with anchor'
                target.update({'heading_vertex': heading_vertices[leg], 'heading_xy': edge / np.linalg.norm(edge)})
            targets[leg] = target
            residual = lambda value: _contact_residual(model, value, seed, root, shifts[i],
                                                        indices[leg], target, config)
            if i == len(rows) - 1:
                solved = np.array([first_q[n] for n in model.names])
                attempts[leg] = []
                exhausted = False
            else:
                solve = probe._local_solve if early_stop else _solve_contact
                solved, attempts[leg], exhausted = solve(
                    residual, seed, model.lo, model.hi, config)
            if exhausted or np.linalg.norm(residual(solved)[:-len(solved)]) > 1:
                failures.append(f'{leg}: material target residual or solver budget')
            q.update(zip(model.names, map(float, solved)))
        geometry = check._body_state(q, root, urdf, collision)
        legs = {}
        for leg, model in models.items():
            bend = model.names.index(build['definitions'][leg]['bend'] + '_joint')
            state = check._state(model, q, root, urdf, collision,
                                 probe.reach.straight_hfe(model.chain), bend, geometry)
            before = corrected[-1]['legs'][leg]['state'] if corrected else None
            phase = row['legs'][leg]['phase']
            reasons = probe._local_failures(state, before, None, config,
                                            contact=targets[leg]['anchor_m'] is not None,
                                            landing=phase == 'return_neutral') + state['limit_failures']
            if phase in ('lift', 'forward_air') and state['task_m'][2] <= config['position_tolerance_m']:
                reasons.append('no resolved lift')
            if before is not None and phase in ('backward_contact', 'forward_air'):
                dx = state['task_m'][0] - before['task_m'][0]
                if (phase == 'backward_contact' and dx >= -config['position_tolerance_m']) or (
                        phase == 'forward_air' and dx <= config['position_tolerance_m']):
                    reasons.append('no resolved directed displacement')
            failures.extend(f'{leg}: {reason}' for reason in reasons)
            target = {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in targets[leg].items()}
            legs[leg] = {'phase': phase, 'local_c': row['legs'][leg]['local_c'], 'state': state,
                         'material_vertex_index': indices[leg], 'target': target, 'solver_attempts': attempts[leg]}
        if sum(abs(item['state']['task_m'][2]) <= config['position_tolerance_m'] for item in legs.values()) < 2:
            failures.append('fewer than two geometric palm contacts')
        corrected.append({'s': row['s'], 'q_rad': q, 'geometry': geometry, 'legs': legs, 'failures': failures})
        print(f'CONTACT_POSE {i + 1}/{len(rows)} c={row["s"]:.6f} failures={failures}', flush=True)
        if failures:
            failure = {'s': row['s'], 'failures': failures}
            break
        first_q = first_q or dict(q)
    closed = bool(failure is None and corrected[-1]['q_rad'] == corrected[0]['q_rad'])
    result = {'pose_count': len(corrected), 'failure': failure, 'completed_combined_loop': closed,
              'rows': corrected, 'source_schedule': original['schedule']}
    report = {'mode': 'sampled_contact_corrected_path', 'source_report': str(source_path),
              'source_report_sha256': view.digest(source_path), 'identity': identity,
              'root_report': str(root_path), 'root_report_sha256': view.digest(root_path),
              'root_transform': root.tolist(), 'root_offsets_m': shifts[:len(corrected)].tolist(),
              'anchor_selection': anchor,
              'early_stop_at_position_tolerance': early_stop,
              'stance_orientation': orientation,
              'source_config': config, 'checked_pairs': source['checked_pairs'], 'excluded_pairs': excluded,
              'legs': {'combined': result},
              'correction_code_sha256': {str(Path(p).resolve()): view.digest(Path(p))
                                         for p in (__file__, view.__file__, check.__file__)},
              'limits': 'Finite corrected source grid only. Rechecked all sampled geometry; no midpoint or '
                        'continuous-domain claim. Anchor position tolerance is a numerical solve tolerance, '
                        'not a new approved slip threshold. No physical timing, C2 derivative, PD or dynamics.'}
    output.mkdir(parents=True, exist_ok=False)
    (output / 'report.json').write_text(json.dumps(report, indent=1, allow_nan=False), encoding='utf-8')
    print(json.dumps({'completed': closed, 'failure': failure, 'poses': len(corrected)}), flush=True)


def _self_check(break_target=False):
    if break_target:
        import inspect
        from unittest.mock import patch
        scope = {}
        code = inspect.getsource(_contact_target).replace("'point_xy_m': anchor[:2]",
                                                         "'point_xy_m': sample(c, material_index)[0][:2]")
        exec(code, globals(), scope)
        with patch.dict(globals(), {'_contact_target': scope['_contact_target']}):
            _self_check()
        return
    def sample(c, index):
        assert index == 7
        return np.array([c, 2., 0.]), .1
    target = _contact_target(.25, .25, sample, 7)
    assert np.array_equal(target['point_xy_m'], [0., 2.]), 'stance target drifted with source'
    assert np.array_equal(_contact_target(1.25, .25, sample, 7)['anchor_m'], [1., 2., 0.])
    lift = _contact_target(.625, .625, sample, 7)
    assert np.array_equal(lift['point_xy_m'], [0., 2.])
    swing = _contact_target(.8125, .8125, sample, 7)
    assert np.allclose(swing['point_xy_m'], [.5, 2.]) and swing['minimum_z_m'] == .1
    assert swing['anchor_m'] is None
    print('CONTACT_TARGET_SELF_CHECK_OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source_report', type=Path)
    parser.add_argument('--root_report', type=Path)
    parser.add_argument('--output_dir', type=Path)
    parser.add_argument('--anchor', choices=('front_contact', 'lowest'), default='front_contact')
    parser.add_argument('--early_stop', action='store_true')
    parser.add_argument('--stance_orientation', choices=('free', 'contact_heading'),
                        default='contact_heading')
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--break_target', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        _self_check(args.break_target)
    else:
        if args.break_target or not all((args.source_report, args.root_report, args.output_dir)):
            parser.error('source_report, root_report and output_dir required; break_target needs self_check')
        _run(args.source_report.resolve(), args.root_report.resolve(), args.output_dir.resolve(),
             args.anchor, args.early_stop, args.stance_orientation)
