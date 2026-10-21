# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Check quarter points of recorded local paths, without solving or smoothing [m, rad].

--source_report <budgeted_local_path report.json> --output_dir <fresh rl_exp/out directory>
Each accepted source segment adds u=1/4 and 3/4 of the original joint-linear interpolation.
At most 64 new poses per leg; first geometry failure stops that leg. Original endpoint and
midpoint verdicts remain source evidence. Reports new full-body ground/collision readings,
contact residual, directed palm, bend and joint-limit/step checks. No continuous proof,
time mapping, no-slip, dynamics, new collision exclusions or tolerance changes.
--mirror checks the actual opposite legs with URDF-derived axis signs and mirrored limits.
Each target adds neutral plus u=1/4, 1/2, 3/4, 1 for every accepted source segment, at most
129 poses per leg. All target poses are rechecked; no source verdict is copied to the target.
--combined checks at most 129 full-body poses: lf/rr in phase, rf/rl offset by half a
path cycle. Body stays fixed; each pose checks all four palms and all collision pairs once.
No solving, smoothing, time mapping, world no-slip or support-force verdict.
--support_schedule with --combined preserves each original joint-line segment, assigns
5/8 of dimensionless cycle c to contact and 1/8 to each remaining phase, and traverses
segments with 10u^3-15u^4+6u^5. Every original node has zero dq/dc and d2q/dc2;
this stop-at-each-node C2 retiming is not geometric smoothing or physical speed approval.
At most 129 combined poses; at least two palms must meet the original contact tolerance.
--self_check --break_test <case> must fail when the actual checking function is broken.
"""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import local_path_view as view
import palm_spatial_probe as probe

REPO = view.REPO


def _quarter_check(rows, evaluate, config, budget=64):
    names = sorted(rows[0]['state']['q_rad'])
    readings, failure, count, completed = [], None, 0, 0
    for segment, (before, after) in enumerate(zip(rows, rows[1:]), 1):
        if after.get('failures') or after.get('midpoint_failures'):
            break
        start = np.array([before['state']['q_rad'][n] for n in names])
        end = np.array([after['state']['q_rad'][n] for n in names])
        for u in (.25, .75):
            if count >= budget:
                failure = {'segment': segment, 'phase': after['phase'], 'failures': ['sampling budget']}
                break
            state = evaluate(dict(zip(names, start + u * (end - start))))
            count += 1
            contact = after['phase'] == 'backward_contact'
            landing = after['phase'] == 'return_neutral'
            previous = before['state'] if u == .25 else after['midpoint']
            following = after['midpoint'] if u == .25 else after['state']
            failures = probe._local_failures(state, previous, None, config, contact, landing)
            failures.extend(state.get('limit_failures', []))
            if landing and following['task_m'][2] > state['task_m'][2] + config['position_tolerance_m']:
                failures.append('landing height increased toward next source sample')
            row = {'segment': segment, 'source_point': after.get('point'), 'phase': after['phase'],
                   'u': u, 's': float(before['s'] + u * (after['s'] - before['s'])),
                   'state': state, 'failures': failures}
            readings.append(row)
            if failures:
                failure = {k: row[k] for k in ('segment', 'phase', 'u', 's', 'failures')}
                break
        if failure is not None:
            break
        completed += 1
    return {'new_pose_count': count, 'checked_segments': completed, 'failure': failure, 'rows': readings,
            'all_requested_quarters_pass': failure is None and completed == len(rows) - 1}


def _mirror_mapping(left, right):
    assert len(left.names) == len(right.names) and len(left.names), 'mirror chain mismatch'
    assert [n.split('_', 1)[1] for n in left.names] == [n.split('_', 1)[1] for n in right.names]
    axes = lambda model: SimpleNamespace(axes=[np.array(s['axis']) for s in model.chain])
    signs = probe.motion.gait.mirror_signs(axes(left), axes(right))
    assert np.isfinite(signs).all(), 'axes are not mirror-related'
    intervals = np.sort(np.array([left.lo * signs, left.hi * signs]), axis=0)
    assert np.allclose(intervals, [right.lo, right.hi], atol=1e-12, rtol=0), 'mirrored limits differ'
    return signs


def _mirror_check(rows, map_angles, evaluate, config, budget=129):
    readings, failure, completed = [], None, 0
    previous = initial = None
    for segment, row in enumerate(rows):
        if row.get('failures') or row.get('midpoint_failures'):
            failure = {'segment': segment, 'failures': ['failed source segment']}
            break
        before = rows[max(segment - 1, 0)]
        names = sorted(row['state']['q_rad'])
        start = np.array([before['state']['q_rad'][n] for n in names])
        end = np.array([row['state']['q_rad'][n] for n in names])
        for u in ((0.,) if segment == 0 else (.25, .5, .75, 1.)):
            if len(readings) >= budget:
                failure = {'segment': segment, 'failures': ['sampling budget']}
                break
            source_q = dict(zip(names, start + u * (end - start)))
            state = evaluate(map_angles(source_q))
            phase = row['phase']
            failures = probe._local_failures(state, previous, None, config,
                                             contact=phase in ('neutral', 'backward_contact'),
                                             landing=phase == 'return_neutral')
            failures.extend(state.get('limit_failures', []))
            if phase in ('lift', 'forward_air') and state['task_m'][2] <= config['position_tolerance_m']:
                failures.append('no resolved lift')
            if previous is not None and phase in ('backward_contact', 'forward_air'):
                dx = state['task_m'][0] - previous['task_m'][0]
                if (phase == 'backward_contact' and dx >= -config['position_tolerance_m']) or (
                        phase == 'forward_air' and dx <= config['position_tolerance_m']):
                    failures.append('no resolved directed displacement')
            if segment and u == 1.:
                delta = max(abs(end[n] - start[n]) for n in range(len(names)))
                if delta > config['joint_step_rad'] + 1e-12:
                    failures.append('source endpoint joint step')
            reading = {'segment': segment, 'phase': phase, 'u': u,
                       's': float(before['s'] + u * (row['s'] - before['s'])),
                       'state': state, 'failures': failures}
            readings.append(reading)
            if failures:
                failure = {k: reading[k] for k in ('segment', 'phase', 'u', 's', 'failures')}
                break
            if initial is None:
                initial = state
            previous = state
        if failure is not None:
            break
        completed += bool(segment)
    closed = bool(initial is not None and previous is not None
                  and probe._local_closed(previous, initial, config))
    return {'pose_count': len(readings), 'checked_segments': completed, 'failure': failure,
            'completed_local_loop': bool(failure is None and completed == len(rows) - 1 and closed),
            'rows': readings}


def _body_state(q, root, urdf, collision):
    ground = {link: probe._static_ground(v, probe.csc.fk(urdf['joints'], link, q), root)
              for link, (v, _) in collision.local.items()}
    pairs = collision.check(q)
    solid, positive = probe._static_pair_readings(pairs)
    limits = [f'joint limit: {n}' for n, value in q.items()
              if not urdf['joints'][n]['limits'][0] <= value <= urdf['joints'][n]['limits'][1]]
    return {'all_ground_min_m': min(g['height_m'] for g in ground.values()), 'ground_by_link': ground,
            'solid_pairs': solid, 'positive_gap_pairs': positive,
            'zero_gap_non_solid_pairs': [r for r in pairs if r['gap_lower_m'] == 0 and r not in solid],
            'limit_failures': limits}


def _state(model, q, root, urdf, collision, straight, bend, geometry=None):
    angles = np.array([q[n] for n in model.names])
    pose = model.pose(angles)
    independent = model.root @ np.array(probe.reach.chain_frames(model.chain, angles)[-1])
    assert np.max(np.abs(pose - independent)) < 1e-10, 'quarter FK mismatch'
    point, normal = model.sole(angles)
    point = root[:3, :3] @ point + root[:3, 3]
    lowest = probe._static_ground(model.vertices, pose, root)
    geometry = _body_state(q, root, urdf, collision) if geometry is None else geometry
    return {'q_rad': {n: float(v) for n, v in q.items()}, 'chain_q_rad': angles.tolist(),
            'task_m': [float(point[0]), float(point[1]), lowest['height_m']],
            'reference_point_m': point.tolist(), 'palm_lowest_vertex': lowest,
            'normal_z': float((root[:3, :3] @ normal)[2]), 'palm_normal': (root[:3, :3] @ normal).tolist(),
            'thigh_shank_angle_deg': probe.reach.thigh_shank_angle(model.chain, angles),
            'reverse_bend': bool(angles[bend] * np.sign(straight) >= abs(straight)), **geometry}


def _phase_angles(rows, joint_names, s):
    assert 0 <= s < 1 and rows[0]['s'] == 0 and rows[-1]['s'] == 1, 'invalid periodic path'
    parameters = np.array([row['s'] for row in rows])
    if s == 0:
        return np.array([rows[0]['state']['q_rad'][n] for n in joint_names]), 'neutral'
    index = int(np.searchsorted(parameters, s, side='left'))
    before, after = rows[index - 1], rows[index]
    u = (s - before['s']) / (after['s'] - before['s'])
    start = np.array([before['state']['q_rad'][n] for n in joint_names])
    end = np.array([after['state']['q_rad'][n] for n in joint_names])
    return start + u * (end - start), after['phase']


def _support_map(c):
    boundaries = np.array([0., 5 / 8, 3 / 4, 7 / 8, 1.])
    assert 0 <= c < 1, 'invalid cycle parameter'
    phase = min(int(np.searchsorted(boundaries, c, side='right')) - 1, 3)
    duration = boundaries[phase + 1] - boundaries[phase]
    coordinate = (c - boundaries[phase]) / duration * 8
    segment = min(int(coordinate), 7)
    u = coordinate - segment
    h = u ** 3 * (10 + u * (-15 + 6 * u))
    dh = 30 * u ** 2 * (1 - u) ** 2
    d2h = 60 * u * (1 - u) * (1 - 2 * u)
    rate = 8 / duration
    return {'source_s': (phase * 8 + segment + h) / 32,
            'ds_dc': dh * rate / 32, 'd2s_dc2': d2h * rate ** 2 / 32,
            'phase_index': phase, 'segment': phase * 8 + segment + 1, 'u': u}


def _support_samples():
    boundaries = np.array([0., 5 / 8, 3 / 4, 7 / 8, 1.])
    nodes = np.r_[np.concatenate([np.linspace(a, b, 9)[:-1]
                                  for a, b in zip(boundaries, boundaries[1:])]), 1.]
    shifted = (nodes[:-1] - .5) % 1.
    knots = np.unique(np.r_[nodes, shifted])
    mids = (knots[:-1] + knots[1:]) / 2
    samples = np.unique(np.r_[knots, mids])
    assert len(samples) <= 129, 'support sampling exceeds approved budget'
    return samples


def _combined_angles(s, tracks, plans, zero, support_schedule=False):
    q, phases = zero.copy(), {}
    for leg, (source, joint_names, offset, signs) in plans.items():
        local_s = (s + offset) % 1.
        mapping = _support_map(local_s) if support_schedule else None
        source_s = mapping['source_s'] if mapping is not None else local_s
        angles, phase = _phase_angles(tracks[source], joint_names, source_s)
        target_names = plans[leg][1] if leg == source else [n.replace(source + '_', leg + '_', 1)
                                                          for n in joint_names]
        q.update(dict(zip(target_names, map(float, angles * signs))))
        phases[leg] = {'phase': phase, 'local_s': source_s}
        if mapping is not None:
            before, after = tracks[source][mapping['segment'] - 1: mapping['segment'] + 1]
            slope = np.array([after['state']['q_rad'][n] - before['state']['q_rad'][n]
                              for n in joint_names]) * 32 * signs
            phases[leg].update({'local_c': local_s, 'mapping': mapping,
                               'dq_dc_rad': (slope * mapping['ds_dc']).tolist(),
                               'd2q_dc2_rad': (slope * mapping['d2s_dc2']).tolist()})
    return q, phases


def _combined_check(parameters, evaluate, config, budget=129, require_support=False):
    rows, failure, previous = [], None, None
    for s in parameters:
        if len(rows) >= budget:
            failure = {'s': float(s), 'failures': ['sampling budget']}
            break
        reading = evaluate(float(s))
        failures = []
        for leg, item in reading['legs'].items():
            state, phase = item['state'], item['phase']
            before = None if previous is None else previous['legs'][leg]['state']
            reasons = probe._local_failures(state, before, None, config,
                                            contact=phase in ('neutral', 'backward_contact'),
                                            landing=phase == 'return_neutral')
            reasons.extend(state.get('limit_failures', []))
            if phase in ('lift', 'forward_air') and state['task_m'][2] <= config['position_tolerance_m']:
                reasons.append('no resolved lift')
            if before is not None and phase in ('backward_contact', 'forward_air'):
                dx = state['task_m'][0] - before['task_m'][0]
                if (phase == 'backward_contact' and dx >= -config['position_tolerance_m']) or (
                        phase == 'forward_air' and dx <= config['position_tolerance_m']):
                    reasons.append('no resolved directed displacement')
            failures.extend(f'{leg}: {reason}' for reason in reasons)
        if require_support:
            contact_legs = [leg for leg, item in reading['legs'].items()
                            if abs(item['state']['task_m'][2]) <= config['position_tolerance_m']]
            if len(contact_legs) < 2:
                failures.append('fewer than two geometric palm contacts')
        row = {'s': float(s), **reading, 'failures': failures}
        rows.append(row)
        if failures:
            failure = {'s': float(s), 'failures': failures}
            break
        previous = reading
    closed = bool(rows and previous is not None and rows[0]['q_rad'] == previous['q_rad']
                  and all(probe._local_closed(previous['legs'][leg]['state'], item['state'], config)
                          for leg, item in rows[0]['legs'].items()))
    return {'pose_count': len(rows), 'failure': failure,
            'completed_combined_loop': bool(failure is None and len(rows) == len(parameters) and closed),
            'rows': rows}


def _combined_run(source, models, zero, root, urdf, collision, build, config, support_schedule=False):
    assert set(source['legs']) == {'lf', 'rr'}, 'combined mode requires the two source legs'
    tracks = {leg: data['rows'] for leg, data in source['legs'].items()}
    for leg, rows in tracks.items():
        assert source['legs'][leg]['completed_local_loop'] and len(rows) == 33, 'complete source loop required'
        assert np.array_equal([r['s'] for r in rows], np.linspace(0, 1, 33)), 'unsupported source grid'
        for row in rows:
            assert not row.get('failures') and not row.get('midpoint_failures'), 'failed source segment'
            assert all(row['state']['q_rad'][n] == 0 for n in zero.keys() - set(models[leg].names))
    plans = {'lf': ('lf', models['lf'].names, 0., np.ones(5)),
             'rr': ('rr', models['rr'].names, 0., np.ones(5)),
             'rf': ('lf', models['lf'].names, .5, _mirror_mapping(models['lf'], models['rf'])),
             'rl': ('rr', models['rr'].names, .5, _mirror_mapping(models['rr'], models['rl']))}
    geometry_fields = ('all_ground_min_m', 'ground_by_link', 'solid_pairs', 'positive_gap_pairs',
                       'zero_gap_non_solid_pairs', 'limit_failures')
    def evaluate(s):
        q, phases = _combined_angles(s, tracks, plans, zero, support_schedule)
        geometry = _body_state(q, root, urdf, collision)
        legs = {}
        for leg, model in models.items():
            bend = model.names.index(build['definitions'][leg]['bend'] + '_joint')
            straight = probe.reach.straight_hfe(model.chain)
            state = _state(model, q, root, urdf, collision, straight, bend, geometry)
            legs[leg] = {**phases[leg], 'state': state}
        return {'q_rad': q, 'geometry': geometry, 'legs': legs}
    parameters = _support_samples() if support_schedule else np.linspace(0, 1, 129)
    result = _combined_check(parameters, evaluate, config, require_support=support_schedule)
    if support_schedule:
        result['schedule'] = {'cycle_parameter': 'dimensionless c, not seconds',
                              'phase_fractions': [5 / 8, 1 / 8, 1 / 8, 1 / 8],
                              'segment_interpolation': '10u^3-15u^4+6u^5',
                              'node_dq_dc_rad': 0., 'node_d2q_dc2_rad': 0.,
                              'physical_speed_or_acceleration_approved': False,
                              'minimum_geometric_contact_palms': 2,
                              'planned_pose_count': len(parameters)}
    for row in result['rows']:
        for item in row['legs'].values():
            for key in ('q_rad', *geometry_fields):
                item['state'].pop(key)
    result['phase_offsets'] = {leg: plan[2] for leg, plan in plans.items()}
    result['joint_mapping'] = {leg: [{'source': n, 'target': n.replace(plan[0] + '_', leg + '_', 1),
                                    'sign': float(sign)} for n, sign in zip(plan[1], plan[3])]
                               for leg, plan in plans.items()}
    result['geometric_contact_legs'] = [
        {'s': r['s'], 'legs': [leg for leg, item in r['legs'].items()
                              if abs(item['state']['task_m'][2]) <= config['position_tolerance_m']]}
        for r in result['rows']]
    return result


def _run(source_path, output, mirror=False, combined=False, support_schedule=False):
    assert REPO / 'rl_exp/out' in output.parents and not output.exists(), 'fresh isolated output required'
    source_path = view.artifact_path(source_path)
    source, _, _, _, tracks = view._load(source_path)
    build_path = view.artifact_path(Path(source['identity']['build_report']))
    build, models, urdf, zero, collision, excluded, root, neutral, blender, identity = probe._static_prepare(build_path)
    assert source['identity'] == identity, 'geometry/collection code identity changed'
    assert source['root_transform'] == root.tolist(), 'root changed'
    assert source['checked_pairs'] == [list(p) for p in collision.pairs], 'pair set changed'
    assert source['excluded_pairs'] == excluded, 'exclusions changed'
    config = source['config']
    assert config['position_tolerance_m'] == 1e-5 and config['joint_step_rad'] == .05, 'unapproved tolerances'
    assert config['points_per_phase'] == 8 and config['midpoint_check'], 'unsupported source sampling'
    results = {}
    if combined:
        results['combined'] = _combined_run(source, models, zero, root, urdf, collision, build, config,
                                            support_schedule)
    if mirror:
        assert set(tracks) == {'lf', 'rr'}, 'mirror mode requires the two source legs'
    for leg, (stats, _) in ({} if combined else tracks).items():
        model = models[leg]
        count = stats['accepted_points']
        rows = source['legs'][leg]['rows'][:count + 1]
        assert count <= 32, 'source exceeds approved sampling budget'
        for row in rows:
            for state in [row['state']] + ([row['midpoint']] if 'midpoint' in row else []):
                assert all(state['q_rad'][n] == 0 for n in zero.keys() - set(model.names)), 'other joints moved'
                assert np.array_equal(np.array([state['q_rad'][n] for n in model.names]), state['chain_q_rad'])
        if mirror:
            assert count == 32 and stats['completed_local_loop'], 'mirror requires a complete source loop'
            target = {'lf': 'rf', 'rr': 'rl'}[leg]
            other = models[target]
            signs = _mirror_mapping(model, other)
            bend = other.names.index(build['definitions'][target]['bend'] + '_joint')
            straight = probe.reach.straight_hfe(other.chain)
            def map_angles(q):
                return {**zero, **{n: float(sign * q[m])
                                  for m, n, sign in zip(model.names, other.names, signs)}}
            result = _mirror_check(rows, map_angles,
                                   lambda q: _state(other, q, root, urdf, collision, straight, bend), config)
            result.update({'source_leg': leg, 'joint_mapping': [
                {'source': m, 'target': n, 'sign': float(sign)}
                for m, n, sign in zip(model.names, other.names, signs)]})
            result.update({'source_accepted_points': count, 'source_completed_local_loop': True})
            results[target] = result
        else:
            bend = model.names.index(build['definitions'][leg]['bend'] + '_joint')
            straight = probe.reach.straight_hfe(model.chain)
            result = _quarter_check(rows, lambda q: _state(model, q, root, urdf, collision, straight, bend), config)
            result.update({'source_accepted_points': count, 'source_completed_local_loop': stats['completed_local_loop'],
                           'source_failure_phase': stats['failure_phase'],
                           'full_source_loop_quarters_pass': bool(count and stats['completed_local_loop']
                                                                   and result['all_requested_quarters_pass'])})
            results[leg] = result
    identity['code_sha256'].update({str(Path(p).resolve()): view.digest(p) for p in (__file__, view.__file__)})
    sampling = ({'fractions': [0., .25, .5, .75, 1.], 'max_poses_per_leg': 129,
                 'source_to_target': {'lf': 'rf', 'rr': 'rl'}} if mirror else
                {'fractions': [.25, .75], 'max_new_poses_per_leg': 64})
    if combined:
        sampling = {'fractions': [0., .25, .5, .75, 1.], 'max_combined_poses': 129,
                    'phase_offsets': results['combined']['phase_offsets']}
    if support_schedule:
        sampling = {'max_combined_poses': 129, 'actual_planned_poses': len(_support_samples()),
                    'phase_offsets': results['combined']['phase_offsets'],
                    'cycle_parameters': _support_samples().tolist(),
                    'joint_linear': True, 'segment_parameter_quintic': True}
    sampling.update({'stop_on_first_failure': True, 'joint_linear': True})
    report = {'mode': 'sampled_local_path_support_schedule' if support_schedule else
                     'sampled_local_path_combined' if combined else
                     'sampled_local_path_mirror' if mirror else 'sampled_local_path_quarters',
              'source_report': str(source_path),
              'source_report_sha256': view.digest(source_path), 'identity': identity,
              'source_config': config, 'sampling': sampling,
              'root_transform': root.tolist(), 'checked_pairs': source['checked_pairs'], 'excluded_pairs': excluded,
              'numerical_geometry_trigger_m': collision.clearance, 'safety_clearance_m': None,
              'legs': results,
              'limits': ('Fixed-body support schedule with C2 node-stopping dimensionless retiming, not geometric '
                         'smoothing or physical speed/dynamics approval. ' if support_schedule else
                         'Four-leg combined sampled geometry with fixed body; no support-force verdict. ' if combined else
                         'Actual opposite legs sampled independently; all target verdicts rechecked. '
                         'No four-leg combination. ' if mirror else
                         'Only new quarter samples checked. Source endpoints/midpoints remain historical verdicts. ')
                        + 'Not continuous contact/collision proof, safe domain, maximal capability, time/speed, '
                          'material no-slip, smooth seams, PD or dynamics. No solving, asset change or relaxed threshold. '
                          'Ground tolerance is numerical, not physical permission. Positive gaps may be AABB lower bounds.'}
    payload = json.dumps(report, indent=1, allow_nan=False)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'report.json').write_text(payload, encoding='utf-8')
    summary = ('pose_count', 'failure', 'completed_combined_loop') if combined else (
        'pose_count', 'checked_segments', 'failure', 'completed_local_loop') if mirror else (
        'new_pose_count', 'checked_segments', 'failure', 'full_source_loop_quarters_pass')
    print(json.dumps({leg: {k: result[k] for k in summary} for leg, result in results.items()}, indent=1), flush=True)


def _self_check(break_test=None):
    if break_test:
        import inspect
        from unittest.mock import patch
        mutations = {'fractions': (_quarter_check, '(.25, .75)', '(.5,)'),
                     'stop': (_quarter_check, 'if failures:', 'if False:'),
                     'budget': (_quarter_check, 'count >= budget', 'False'),
                     'landing': (_quarter_check, "following['task_m'][2] > state['task_m'][2]", '0 > 1'),
                     'contact': (probe._local_failures, "contact and abs(state['task_m'][2]) > tolerance", 'False'),
                     'mirror_sign': (_mirror_mapping, 'return signs', 'return np.ones_like(signs)'),
                     'mirror_limits': (_mirror_mapping, "assert np.allclose(intervals, [right.lo, right.hi], atol=1e-12, rtol=0)", 'assert True'),
                     'mirror_stop': (_mirror_check, 'if failures:', 'if False:'),
                     'mirror_budget': (_mirror_check, 'len(readings) >= budget', 'False'),
                     'mirror_samples': (_mirror_check, '(.25, .5, .75, 1.)', '(.5, 1.)'),
                     'mirror_closure': (_mirror_check, 'and closed)', ')'),
                     'combined_offset': (_combined_angles, '(s + offset) % 1.', 's % 1.'),
                     'combined_interpolation': (_phase_angles, 'start + u * (end - start)', 'end'),
                     'combined_pairs': (_body_state, 'pairs = collision.check(q)', 'pairs = []'),
                     'combined_stop': (_combined_check, 'if failures:', 'if False:'),
                     'combined_budget': (_combined_check, 'len(rows) >= budget', 'False'),
                     'combined_closure': (_combined_check, 'and closed)', ')'),
                     'support_fraction': (_support_map, '5 / 8, 3 / 4, 7 / 8', '1 / 4, 1 / 2, 3 / 4'),
                     'support_curve': (_support_map, 'u ** 3 * (10 + u * (-15 + 6 * u))', 'u'),
                     'support_derivative': (_support_map, '30 * u ** 2 * (1 - u) ** 2', '1.'),
                     'support_gate': (_combined_check, 'len(contact_legs) < 2', 'False'),
                     'support_samples': (_support_samples, 'nodes, shifted', 'nodes')}
        function, old, new = mutations[break_test]
        code = inspect.getsource(function)
        assert old in code
        scope = dict(function.__globals__)
        exec(code.replace(old, new), scope)
        with patch.dict(function.__globals__, {function.__name__: scope[function.__name__]}):
            _self_check()
        return
    config = {'position_tolerance_m': 1e-5, 'joint_step_rad': .05}
    def state(q, height=0., **changes):
        return {'q_rad': {'joint': q}, 'chain_q_rad': [q], 'task_m': [0., 0., height],
                'all_ground_min_m': 0., 'normal_z': 1., 'reverse_bend': False, 'solid_pairs': [], **changes}
    rows = [{'s': 0., 'phase': 'neutral', 'state': state(0.)},
            {'s': .1, 'phase': 'backward_contact', 'state': state(.04), 'midpoint': state(.02)}]
    calls = []
    def hidden_gap(q):
        u = q['joint'] / .04
        calls.append(u)
        return state(q['joint'], .001 * u * (u - .5) * (u - 1))
    result = _quarter_check(rows, hidden_gap, config)
    assert result['failure'] is not None, 'hidden contact gap or fail-stop lost'
    assert result['failure']['failures'] == ['contact residual'] and result['new_pose_count'] == 1
    assert calls == [.25] and result['failure']['s'] == .025, 'missed quarter or did not stop'
    result = _quarter_check(rows, lambda q: state(q['joint']), config)
    assert result['all_requested_quarters_pass'] and [r['u'] for r in result['rows']] == [.25, .75]
    assert np.allclose([r['state']['chain_q_rad'][0] for r in result['rows']], [.01, .03])
    limited = _quarter_check(rows, lambda q: state(q['joint']), config, budget=1)
    assert limited['new_pose_count'] == 1 and limited['failure']['failures'] == ['sampling budget']
    for changes, expected in (({'all_ground_min_m': -2e-5}, 'ground penetration'),
                              ({'normal_z': -1.}, 'back-side palm'), ({'reverse_bend': True}, 'reverse bend'),
                              ({'solid_pairs': [{'pair': ['a', 'b']}]}, 'solid intersection'),
                              ({'limit_failures': ['joint limit: joint']}, 'joint limit: joint')):
        result = _quarter_check(rows, lambda q: state(q['joint'], **changes), config)
        assert expected in result['failure']['failures'] and result['new_pose_count'] == 1
    rows[1]['phase'] = 'return_neutral'
    rows[0]['state']['task_m'][2] = .02
    rows[1]['midpoint']['task_m'][2] = .01
    result = _quarter_check(rows, lambda q: state(q['joint'], .005), config)
    assert result['failure'] is not None, 'landing increase missed'
    assert 'landing height increased toward next source sample' in result['failure']['failures']
    left = SimpleNamespace(names=['lf_swing_joint', 'lf_twist_joint'],
                           chain=[{'axis': [0., 0., 1.]}, {'axis': [0., 1., 0.]}],
                           lo=np.array([-.2, -.3]), hi=np.array([.4, .1]))
    right = SimpleNamespace(names=['rf_swing_joint', 'rf_twist_joint'],
                            chain=[{'axis': [0., 0., -1.]}, {'axis': [0., -1., 0.]}],
                            lo=np.array([-.2, -.1]), hi=np.array([.4, .3]))
    assert np.array_equal(_mirror_mapping(left, right), [1., -1.]), 'mirror sign lost'
    right.hi[1] = .4
    try:
        _mirror_mapping(left, right)
    except AssertionError as error:
        assert str(error) == 'mirrored limits differ'
    else:
        raise AssertionError('wrong mirror limit accepted')
    def mirror_state(q):
        return {**state(q['joint']), 'reference_point_m': [q['joint'], 0., 0.]}
    loop = [{'s': 0., 'phase': 'neutral', 'state': state(0.)},
            {'s': .5, 'phase': 'backward_contact', 'state': state(.04)},
            {'s': 1., 'phase': 'return_neutral', 'state': state(0.)}]
    def contact_state(q):
        reading = mirror_state(q)
        reading['task_m'][0] = -q['joint']
        return reading
    result = _mirror_check(loop, lambda q: q, contact_state, config)
    assert result['completed_local_loop'] and result['pose_count'] == 9
    assert [r['u'] for r in result['rows']] == [0., .25, .5, .75, 1., .25, .5, .75, 1.]
    limited = _mirror_check(loop, lambda q: q, contact_state, config, budget=1)
    assert limited['pose_count'] == 1 and limited['failure']['failures'] == ['sampling budget']
    def failed_state(q):
        reading = contact_state(q)
        if q['joint']:
            reading['normal_z'] = -1.
        return reading
    failed = _mirror_check(loop, lambda q: q, failed_state, config)
    assert failed['pose_count'] == 2 and failed['failure']['failures'] == ['back-side palm']
    for change, expected in (({'all_ground_min_m': -2e-5}, 'ground penetration'),
                             ({'solid_pairs': [{'pair': ['a', 'b']}]}, 'solid intersection'),
                             ({'task_m': [0., 0., 2e-5]}, 'contact residual')):
        failed = _mirror_check(loop, lambda q: q, lambda q: {**contact_state(q), **change}, config)
        assert failed['pose_count'] == 1 and expected in failed['failure']['failures']
    result = _mirror_check(loop[:2], lambda q: q, contact_state, config)
    assert result['failure'] is None and not result['completed_local_loop'], 'false mirror closure'
    sample = [{'s': 0., 'phase': 'neutral', 'state': {'q_rad': {'lf_a': 0.}}},
              {'s': .5, 'phase': 'lift', 'state': {'q_rad': {'lf_a': .04}}},
              {'s': 1., 'phase': 'return_neutral', 'state': {'q_rad': {'lf_a': 0.}}}]
    q, phase = _phase_angles(sample, ['lf_a'], .25)
    assert q[0] == .02 and phase == 'lift', 'combined interpolation changed'
    plans = {'lf': ('lf', ['lf_a'], 0., np.ones(1)), 'rf': ('lf', ['lf_a'], .5, -np.ones(1))}
    q, phases = _combined_angles(0., {'lf': sample}, plans, {'lf_a': 0., 'rf_a': 0., 'tail': 0.})
    assert q == {'lf_a': 0., 'rf_a': -.04, 'tail': 0.} and phases['rf']['local_s'] == .5, 'phase offset lost'
    end, _ = _combined_angles(1., {'lf': sample}, plans, q)
    assert end == q, 'periodic offset closure lost'
    def combined_state(s, failed=False, close=True):
        value = 0. if s == 1. and close else s * .04
        q = {'joint': value}
        reading = {**state(value), 'reference_point_m': [value, 0., 0.]}
        if failed and s > 0:
            reading['solid_pairs'] = [{'pair': ['lf_body', 'rr_body']}]
        return {'q_rad': q, 'legs': {'lf': {'phase': 'neutral', 'state': reading}}}
    complete = _combined_check([0., .5, 1.], combined_state, config)
    assert complete['completed_combined_loop'] and complete['pose_count'] == 3
    failed = _combined_check([0., .5, 1.], lambda s: combined_state(s, failed=True), config)
    assert failed['pose_count'] == 2 and failed['failure'] is not None, 'combined fail-stop lost'
    assert failed['failure']['failures'] == ['lf: solid intersection']
    limited = _combined_check([0., .5, 1.], combined_state, config, budget=1)
    assert limited['pose_count'] == 1 and limited['failure']['failures'] == ['sampling budget']
    open_cycle = _combined_check([0., .5, 1.], lambda s: combined_state(s, close=False), config)
    assert not open_cycle['completed_combined_loop'] and open_cycle['failure'] is None, 'false combined closure'
    from unittest.mock import patch
    collision = SimpleNamespace(local={'body': (np.zeros((1, 3)), None)},
                                check=lambda q: [{'pair': ['a', 'b'], 'gap_lower_m': 0.,
                                                  'intersects': True, 'contained': False}])
    with patch.object(probe.csc, 'fk', return_value=np.eye(4)):
        geometry = _body_state({'joint': 0.}, np.eye(4),
                               {'joints': {'joint': {'limits': [-1., 1.]}}}, collision)
    assert geometry['solid_pairs'] and geometry['all_ground_min_m'] == 0., 'combined collision scan lost'
    assert _support_map(5 / 8)['source_s'] == .25 and np.isclose(_support_map(.5)['source_s'], 6.31744 / 32)
    assert np.isclose(_support_map(5 / 8 + 1 / 256)['source_s'], (8 + .103515625) / 32), 'quintic map lost'
    knots = np.unique(np.r_[np.linspace(0, 5 / 8, 9), np.linspace(5 / 8, 3 / 4, 9),
                            np.linspace(3 / 4, 7 / 8, 9), np.linspace(7 / 8, 1, 9)])
    for c in knots[:-1]:
        item = _support_map(float(c))
        assert item['ds_dc'] == item['d2s_dc2'] == 0., 'node derivatives not zero'
    for c in np.linspace(0, 1, 1025)[:-1]:
        a, b = _support_map(float(c)), _support_map(float((c + .5) % 1.))
        assert a['source_s'] <= .25 or b['source_s'] <= .25, 'scheduled support gap'
    samples = _support_samples()
    assert samples[0] == 0 and samples[-1] == 1 and len(samples) <= 129
    assert all(c in samples for c in knots) and all(float((c - .5) % 1.) in samples for c in knots[:-1])
    unsupported = _combined_check([0., .5, 1.], combined_state, config, require_support=True)
    assert unsupported['pose_count'] == 1 and unsupported['failure'] is not None, 'support gate lost'
    assert 'fewer than two geometric palm contacts' in unsupported['failure']['failures']
    def supported(s):
        reading = combined_state(s)
        reading['legs']['rf'] = reading['legs']['lf']
        return reading
    assert _combined_check([0., .5, 1.], supported, config, require_support=True)['completed_combined_loop']
    print('LOCAL_PATH_QUARTERS_SELF_CHECK_OK: quarters, mirror, combination and support schedule, C2 retiming, fail-stop')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source_report', type=Path)
    parser.add_argument('--output_dir', type=Path)
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--mirror', action='store_true')
    parser.add_argument('--combined', action='store_true')
    parser.add_argument('--support_schedule', action='store_true')
    parser.add_argument('--break_test', choices=('fractions', 'stop', 'budget', 'landing', 'contact',
                                               'mirror_sign', 'mirror_limits', 'mirror_stop', 'mirror_budget',
                                               'mirror_samples', 'mirror_closure', 'combined_offset',
                                               'combined_interpolation', 'combined_pairs', 'combined_stop',
                                               'combined_budget', 'combined_closure', 'support_fraction',
                                               'support_curve', 'support_derivative', 'support_gate', 'support_samples'))
    args = parser.parse_args()
    if args.support_schedule and not args.combined:
        parser.error('--support_schedule requires --combined')
    if args.mirror and args.combined:
        parser.error('--mirror and --combined are separate modes')
    if args.self_check:
        if args.source_report is not None or args.output_dir is not None or args.mirror or args.combined:
            parser.error('--self_check cannot use input/output')
        _self_check(args.break_test)
    else:
        if args.break_test or args.source_report is None or args.output_dir is None:
            parser.error('--source_report and --output_dir required; --break_test requires --self_check')
        _run(args.source_report.resolve(), args.output_dir.resolve(), mirror=args.mirror, combined=args.combined,
             support_schedule=args.support_schedule)


if __name__ == '__main__':
    main()
