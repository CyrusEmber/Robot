# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Read local-path reports; render recorded poses and measure piecewise-linear seams.

--source_report <report.json> --output_dir <fresh rl_exp/out directory>
Outputs analysis.json, per-leg joint/slopes/trajectory PNGs, and side/top GIFs of actual
collision triangles. Uses only recorded endpoints/midpoints, never solves, smooths, adds
contact samples, or converts s to seconds. GIF duration is display pacing only. Failed
paths render their accepted prefix; neither a failed endpoint nor a fictitious closing
segment is inserted. Source collision verdicts remain historical, not revalidated here.
--self_check exercises nonuniform s, slope jumps, partial paths and record validation.
Python optimization (-O/-OO or PYTHONOPTIMIZE) is refused before input reads.
Also reads sampled_local_path_combined and sampled_local_path_support_schedule: one
full-body side/top replay of accepted recorded poses, all four palm markers and phases.
Recorded analytic dq/dc is distinct from sample secants. Root-translation prerequisites
use the SAME material vertices at adjacent recorded poses, not changing lowest centroids;
no root is applied and no no-slip, force, speed or physical period is approved.
--drive_report optionally binds an existing same-candidate reset report's named solver
velocity caps; outputs only a velocity-cap period lower bound, never a selected period.
--root_translation applies cumulative least-squares horizontal contact translations at
the recorded combined poses, preserving root height/orientation and all joint angles.
Residuals track the same material vertex; contact-feature changes are reported separately.
This measured candidate is not a no-slip solution or a physical-period approval.
"""

import argparse
import json
from pathlib import Path
import sys

# Identity checks below rely on assertions, including when _load is imported directly.
if sys.flags.optimize != 0:
    raise RuntimeError('local_path_view does not support Python optimization (-O/-OO or PYTHONOPTIMIZE); '
                       'identity validation requires assertions')

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'rl_exp/tools/verify'))
import check_self_collision as csc  # noqa: E402
sys.path.insert(0, str(REPO / 'rl_exp/tools/runrecord'))
from binding import sha256_file as digest  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from artifact_paths import ArtifactPaths, artifact_path  # noqa: E402


def _path_stats(s, q, phases, closed):
    assert s.ndim == 1 and q.ndim == 2 and len(s) == len(q) == len(phases)
    assert len(s) and q.shape[1] and np.isfinite(s).all() and np.isfinite(q).all()
    ds = np.diff(s)
    assert np.all(ds > 0), 'path parameters must increase'
    delta = np.diff(q, axis=0)
    slopes = delta / ds[:, None]
    assert not closed or (len(s) > 1 and np.max(np.abs(q[-1] - q[0])) <= 1e-12), 'false closure'
    seams = [{'s': float(s[i]), 'incoming_phase': phases[i], 'outgoing_phase': phases[i + 1],
              'slope_jump_rad_per_s_parameter': (slopes[i] - slopes[i - 1]).tolist()}
             for i in range(1, len(s) - 1)]
    cycle = (slopes[0] - slopes[-1]).tolist() if closed else None
    return {'s': s.tolist(), 'q_rad': q.tolist(), 'segment_phases': phases[1:],
            'segment_slope_rad_per_s_parameter': slopes.tolist(), 'internal_seams': seams,
            'cycle_slope_jump_rad_per_s_parameter': cycle,
            'closure_delta_rad': (q[-1] - q[0]).tolist(),
            'max_abs_joint_step_rad': float(np.max(np.abs(delta))) if len(delta) else 0.,
            'max_abs_internal_slope_jump_rad_per_s_parameter':
                float(np.max(np.abs(np.diff(slopes, axis=0)))) if len(slopes) > 1 else 0.}


def _track(data):
    rows = data['rows']
    assert rows and rows[0]['phase'] == 'neutral' and rows[0]['s'] == 0
    initial = rows[0]['state']
    names = sorted(initial['q_rad'])
    assert names, 'empty joint record'
    endpoints, frames = [rows[0]], []

    def frame(state, s, phase, kind):
        assert sorted(state['q_rad']) == names, 'joint names changed'
        q = np.array([state['q_rad'][name] for name in names], dtype=float)
        assert np.isfinite(q).all(), 'nonfinite joints'
        for key, width in (('reference_point_m', 3), ('palm_normal', 3), ('task_m', 3)):
            value = np.array(state[key], dtype=float)
            assert value.shape == (width,) and np.isfinite(value).all(), key
        lowest = state['palm_lowest_vertex']
        assert np.isfinite(lowest['position_m']).all() and len(lowest['position_m']) == 3
        return {'s': float(s), 'phase': phase, 'kind': kind, 'state': state, 'q': q}

    frames.append(frame(initial, rows[0]['s'], 'neutral', 'endpoint'))
    if not rows[0].get('failures'):
        for row in rows[1:]:
            assert np.isfinite(row['s']) and row['s'] > endpoints[-1]['s'], 'invalid s'
            if row.get('failures') or row.get('midpoint_failures'):
                break
            endpoint = frame(row['state'], row['s'], row['phase'], 'endpoint')
            middle = frame(row['midpoint'], (row['s'] + endpoints[-1]['s']) / 2,
                           row['phase'], 'midpoint')
            assert np.max(np.abs(middle['q'] - (frames[-1]['q'] + endpoint['q']) / 2)) <= 1e-12, 'wrong midpoint'
            frames.extend((middle, endpoint))
            endpoints.append(row)
    assert data['accepted_points'] == len(endpoints) - 1, 'accepted prefix mismatch'
    closed = bool(data['completed_local_loop'])
    assert not closed or (len(endpoints) == len(rows) and not rows[0].get('failures')), 'failed loop'
    stats = _path_stats(np.array([row['s'] for row in endpoints]),
                        np.array([[row['state']['q_rad'][name] for name in names] for row in endpoints]),
                        [row['phase'] for row in endpoints], closed)
    stats.update({'joint_names': names, 'completed_local_loop': closed,
                  'accepted_points': len(endpoints) - 1, 'failure_phase': data['failure_phase'],
                  'frames': [{'s': f['s'], 'phase': f['phase'], 'kind': f['kind'],
                              'reference_point_m': f['state']['reference_point_m'],
                              'palm_normal': f['state']['palm_normal'],
                              'lowest_vertex': f['state']['palm_lowest_vertex']}
                             for f in frames]})
    return stats, frames


def _combined_tracks(data):
    rows = data['rows']
    assert rows and rows[0]['s'] == 0 and data['pose_count'] == len(rows)
    names = sorted(rows[0]['q_rad'])
    assert names and set(rows[0]['legs']) == {'lf', 'rf', 'rl', 'rr'}
    accepted = []
    for row in rows:
        assert sorted(row['q_rad']) == names and np.isfinite(list(row['q_rad'].values())).all()
        assert set(row['legs']) == {'lf', 'rf', 'rl', 'rr'}
        assert not accepted or row['s'] > accepted[-1]['s'], 'invalid combined parameter'
        if row['failures']:
            break
        accepted.append(row)
    closed = bool(data['completed_combined_loop'])
    assert not closed or len(accepted) == len(rows), 'failed combined loop'
    tracks = {}
    for leg in rows[0]['legs']:
        frames = [{'s': row['s'], 'phase': row['legs'][leg]['phase'], 'kind': 'recorded combined pose',
                   'state': {**row['legs'][leg]['state'], 'q_rad': row['q_rad']},
                   'q': np.array([row['q_rad'][n] for n in names])} for row in accepted]
        assert frames, 'no accepted combined poses'
        stats = _path_stats(np.array([f['s'] for f in frames]), np.array([f['q'] for f in frames]),
                            [f['phase'] for f in frames], closed)
        stats.update({'joint_names': names, 'completed_local_loop': closed,
                      'accepted_points': len(frames) - 1,
                      'failure_phase': None if data['failure'] is None else 'combined failure',
                      'frames': [{'s': f['s'], 'phase': f['phase'], 'kind': f['kind'],
                                  'reference_point_m': f['state']['reference_point_m'],
                                  'palm_normal': f['state']['palm_normal'],
                                  'lowest_vertex': f['state']['palm_lowest_vertex']} for f in frames],
                      'sample_secants_not_analytic_derivatives': True})
        if 'schedule' in data:
            stats['analytic_joint_names'] = [m['target'] for m in data['joint_mapping'][leg]]
            stats['recorded_dq_dc_rad'] = [row['legs'][leg]['dq_dc_rad'] for row in accepted]
            stats['recorded_d2q_dc2_rad'] = [row['legs'][leg]['d2q_dc2_rad'] for row in accepted]
            for key in ('recorded_dq_dc_rad', 'recorded_d2q_dc2_rad'):
                values = np.asarray(stats[key])
                assert values.shape == (len(accepted), len(stats['analytic_joint_names'])) and np.isfinite(values).all(), key
        tracks[leg] = stats, frames
    return tracks


def _translation_fit(displacements):
    delta = np.asarray(displacements, dtype=float)
    assert delta.ndim == 2 and delta.shape[1] == 3 and len(delta) and np.isfinite(delta).all()
    translation = -delta.mean(axis=0)
    residual = delta + translation
    return {'root_translation_candidate_m': translation.tolist(),
            'max_material_residual_m': float(np.linalg.norm(residual, axis=1).max()),
            'rms_material_residual_m': float(np.sqrt(np.mean(np.sum(residual ** 2, axis=1))))}


def _material_delta(before, after, index):
    assert before.shape == after.shape and before.ndim == 2 and before.shape[1] == 3
    assert isinstance(index, int) and 0 <= index < len(before)
    return after[index] - before[index]


def _rate_prerequisites(report):
    if report['mode'] != 'sampled_local_path_support_schedule':
        return None
    source = json.loads(artifact_path(Path(report['source_report']), report['source_report_sha256']).read_text(encoding='utf-8'))
    data = report['legs']['combined']
    fractions = data['schedule']['phase_fractions']
    assert len(fractions) == 4 and np.isfinite(fractions).all() and min(fractions) > 0 and sum(fractions) == 1
    rows = []
    for leg, mapping in data['joint_mapping'].items():
        original = source['legs'][mapping[0]['source'].split('_', 1)[0]]['rows']
        assert len(original) == 33
        for item in mapping:
            values = np.array([r['state']['q_rad'][item['source']] for r in original])
            delta = abs(np.diff(values))
            rate = np.repeat(8 / np.array(fractions), 8)
            rows.append({'joint': item['target'],
                         'analytic_max_abs_dq_dc_rad': float(np.max(delta * rate * 15 / 8)),
                         'analytic_max_abs_d2q_dc2_rad': float(np.max(delta * rate ** 2 * 10 / np.sqrt(3)))})
    return {'joints': rows, 'physical_period_s': None, 'effective_velocity_limits_rad_s': None,
            'formula': 'For constant c=t/T: max|qd|=max|dq/dc|/T; max|qdd|=max|d2q/dc2|/T^2. '
                       'T must satisfy each bound against measured/approved effective limits; none assumed here.',
            'limits': 'Analytic quintic maxima over recorded original joint segments, not sampled peak estimates. '
                      'No solver limit readback, motor tracking, support or physical period approval.'}


def _drive_prerequisites(report, path, rates):
    assert rates is not None, 'drive readback requires support schedule'
    drive = json.loads(artifact_path(path).read_text(encoding='utf-8'))
    build = json.loads(artifact_path(Path(report['identity']['build_report'])).read_text(encoding='utf-8'))
    assert drive['completed'] and drive['input']['urdf_sha256'] == build['candidate_sha256'], 'drive candidate mismatch'
    manifest = artifact_path(Path(drive['input']['manifest']))
    assert digest(manifest) == drive['input']['manifest_sha256'], 'drive manifest changed'
    binding = json.loads(manifest.read_text(encoding='utf-8'))
    target = artifact_path(Path(binding['target_binding']['target']))
    assert digest(target) == drive['input']['usd_sha256'], 'drive USD changed'
    names = drive['joint_names']
    limits = drive['live_readbacks']['fields']['joint_vel_limits']
    assert len(names) == len(set(names)) and len(limits) == 1 and len(limits[0]) == len(names)
    assert np.isfinite(limits).all() and np.min(limits) > 0, 'invalid readback limits'
    by_name = dict(zip(names, limits[0]))
    assert rates['joints'] and {r['joint'] for r in rates['joints']} <= set(names), 'missing drive joint'
    rows = [{**row, 'readback_velocity_cap_rad_s': by_name[row['joint']],
             'velocity_only_period_lower_bound_s': row['analytic_max_abs_dq_dc_rad'] / by_name[row['joint']]}
            for row in rates['joints']]
    return {'drive_report': str(path), 'drive_report_sha256': digest(path), 'input': drive['input'],
            'joints': rows,
            'velocity_only_period_lower_bound_s': max(row['velocity_only_period_lower_bound_s'] for row in rows),
            'physical_period_approved': False,
            'limits': 'Existing fixed-base zero-gain solver cap readback, not effective loaded tracking or a selected period. '
                      'No cap activation test, acceleration/torque approval, new simulation or root motion.'}


def _root_prerequisites(report, urdf, meshes, root, tracks):
    legs = sorted(tracks)
    frames = {leg: tracks[leg][1] for leg in legs}
    end_links = json.loads(artifact_path(Path(report['identity']['build_report'])).read_text(encoding='utf-8'))['definitions']
    readings = []
    tolerance = report['source_config']['position_tolerance_m']
    for i in range(1, len(frames[legs[0]])):
        displacements, contacts, references = [], [], []
        for leg in legs:
            before, after = frames[leg][i - 1], frames[leg][i]
            a, b = before['state'], after['state']
            if abs(a['palm_lowest_vertex']['height_m']) > tolerance or abs(b['palm_lowest_vertex']['height_m']) > tolerance:
                continue
            link = end_links[leg]['end']
            vertices = meshes[link][0]
            poses = [root @ csc.fk(urdf['joints'], link, state['q_rad']) for state in (a, b)]
            worlds = [vertices @ pose[:3, :3].T + pose[:3, 3] for pose in poses]
            index = b['palm_lowest_vertex']['vertex_index']
            delta = _material_delta(worlds[0], worlds[1], index)
            displacements.append(delta)
            references.append(np.array(b['reference_point_m']) - a['reference_point_m'])
            contacts.append({'leg': leg, 'vertex_index_at_after': index,
                             'same_vertex_displacement_m': delta.tolist(),
                             'same_vertex_before_height_m': float(worlds[0][index, 2]),
                             'same_vertex_after_height_m': float(worlds[1][index, 2]),
                             'same_vertex_contact_at_both': bool(abs(worlds[0][index, 2]) <= tolerance
                                                                 and abs(worlds[1][index, 2]) <= tolerance),
                             'lowest_vertex_changed': index != a['palm_lowest_vertex']['vertex_index']})
        if displacements:
            readings.append({'before_c': frames[legs[0]][i - 1]['s'], 'after_c': frames[legs[0]][i]['s'],
                             'contacts': contacts, 'material_translation_fit': _translation_fit(displacements),
                             'reference_translation_fit': _translation_fit(references)})
    return {'mode': 'recorded_adjacent_material_vertex_translation_compatibility',
            'rows': readings,
            'root_applied': False, 'physical_period_s': None,
            'limits': 'Selected after-pose lowest vertex is the SAME material vertex at both poses. '
                      'Contact feature may switch; this is a translation-only prerequisite, not no-slip proof. '
                      'No root rotation/trajectory, support forces, new poses or collision checks.'}


def _root_translation(prerequisites, frames, prescribed_offsets=None):
    """Apply sampled horizontal root offsets and measure material residuals [m]."""
    intervals = prerequisites['rows']
    assert len(frames) > 1 and len(intervals) == len(frames) - 1 and frames[0]['s'] == 0, 'incomplete root intervals'
    if prescribed_offsets is not None:
        prescribed_offsets = np.asarray(prescribed_offsets, dtype=float)
        assert prescribed_offsets.shape == (len(frames), 3) and np.isfinite(prescribed_offsets).all()
        assert np.all(prescribed_offsets[:, 2] == 0) and np.all(prescribed_offsets[0] == 0)
    offset = np.zeros(3)
    offsets = [offset.tolist()]
    rows = []
    for i, item in enumerate(intervals, 1):
        assert (item['before_c'], item['after_c']) == (frames[i - 1]['s'], frames[i]['s']), 'root interval gap'
        contacts = item['contacts']
        delta = np.asarray([c['same_vertex_displacement_m'] for c in contacts], dtype=float)
        assert delta.ndim == 2 and delta.shape[1] == 3 and len(delta) and np.isfinite(delta).all()
        step = (np.r_[-delta[:, :2].mean(axis=0), 0.] if prescribed_offsets is None else
                prescribed_offsets[i] - prescribed_offsets[i - 1])
        offset = offset + step
        offsets.append(offset.tolist())
        residual = delta + step
        rows.append({'before_c': item['before_c'], 'after_c': item['after_c'],
                     'root_step_m': step.tolist(), 'root_offset_m': offset.tolist(),
                     'contacts': [{**c, 'world_material_displacement_m': r.tolist(),
                                   'horizontal_material_displacement_m': float(np.linalg.norm(r[:2]))}
                                  for c, r in zip(contacts, residual)]})
    contacts = [c for row in rows for c in row['contacts']]
    persistent = [c for c in contacts if c['same_vertex_contact_at_both']]
    return {'mode': 'sampled_horizontal_material_translation_candidate', 'root_applied': True,
            'c': [f['s'] for f in frames], 'offsets_m': offsets, 'rows': rows,
            'net_translation_m': offset.tolist(), 'prescribed_offsets': prescribed_offsets is not None,
            'max_horizontal_material_displacement_m': max(c['horizontal_material_displacement_m'] for c in contacts),
            'max_persistent_contact_displacement_m': (max(c['horizontal_material_displacement_m'] for c in persistent)
                                                      if persistent else None),
            'persistent_contact_readings': len(persistent), 'all_contact_readings': len(contacts),
            'limits': ('Equal weight per contacting leg; ' if prescribed_offsets is None else
                       'Prescribed source root offsets, not refitted to corrected contacts; ')
                      + 'after-pose lowest vertex kept at both endpoints. '
                      'A vertex outside the before-pose contact band is not a persistent contact reading. '
                      'Horizontal-only root translation preserves all sampled heights and internal collisions; '
                      'those source verdicts are reused, not rerun. Residuals are interval displacements, not '
                      'physical slip speeds or an approved no-slip threshold. No new poses, rotation or IK. '
                      'The world path advances; GIF restart is a reset, not a closing world segment.'}


def _load(source):
    paths = ArtifactPaths()
    source = paths.resolve(source)
    report = json.loads(source.read_text(encoding='utf-8'))
    combined = report['mode'] in ('sampled_local_path_combined', 'sampled_local_path_support_schedule',
                                 'sampled_contact_corrected_path')
    assert combined or report['mode'] == 'budgeted_local_path', 'unsupported report schema'
    if combined:
        original = paths.resolve(Path(report['source_report']))
        assert digest(original) == report['source_report_sha256'], 'source path changed'
    identity = report['identity']
    build_path = paths.resolve(Path(identity['build_report']))
    assert digest(build_path) == identity['build_report_sha256'], 'build changed'
    build = json.loads(build_path.read_text(encoding='utf-8'))
    candidate = paths.resolve(Path(build['candidate_urdf'])).resolve()
    assert identity['candidate_files_sha256'] == build['candidate_files_sha256']
    files = identity['candidate_files_sha256']
    bound = {}
    for relative, sha in files.items():
        path = (candidate.parent / relative).resolve()
        assert candidate.parent in path.parents and sha and digest(path) == sha, 'candidate changed'
        bound[path] = sha
    assert bound.get(candidate) == build['candidate_sha256'], 'unbound URDF'
    original_fk = identity['code_sha256'].get(str(Path(csc.__file__).resolve()))
    assert original_fk and digest(Path(csc.__file__)) == original_fk, 'FK changed since collection'
    root = np.array(report['root_transform'], dtype=float)
    assert root.shape == (4, 4) and np.isfinite(root).all()
    assert np.allclose(root[3], [0, 0, 0, 1], atol=1e-12, rtol=0)
    assert np.allclose(root[:3, :3].T @ root[:3, :3], np.eye(3), atol=1e-12, rtol=0)
    assert abs(np.linalg.det(root[:3, :3]) - 1) < 1e-12, 'invalid root rotation'
    urdf = csc.load_urdf(candidate)
    meshes = {}
    for link, spec in urdf['links'].items():
        if spec['collision'] is None:
            continue
        path = spec['collision'].resolve()
        assert path in bound, 'unbound rendered mesh'
        vertices, faces = csc.read_obj_faces(path)
        assert vertices.ndim == 2 and vertices.shape[1] == 3 and np.isfinite(vertices).all()
        assert faces.ndim == 2 and faces.shape[1] == 3 and len(faces)
        assert faces.min() >= 0 and faces.max() < len(vertices), 'invalid mesh faces'
        meshes[link] = (vertices, faces)
    assert meshes and report['legs'], 'empty rendering input'
    movable = sorted(n for n, joint in urdf['joints'].items() if joint['axis'] is not None)
    tracks = _combined_tracks(report['legs']['combined']) if combined else {
        leg: _track(data) for leg, data in report['legs'].items()}
    for leg, (stats, frames) in tracks.items():
        assert leg.isidentifier() and leg in build['definitions'], 'unknown leg'
        assert stats['joint_names'] == movable, 'report/URDF joint mismatch'
        end = build['definitions'][leg]['end']
        assert end in meshes, 'missing palm mesh'
        first = frames[0]['state']
        first_pose = root @ csc.fk(urdf['joints'], end, first['q_rad'])
        reference_local = (np.array(first['reference_point_m']) - first_pose[:3, 3]) @ first_pose[:3, :3]
        for frame in frames:
            state = frame['state']
            for key in ('reference_point_m', 'palm_normal', 'task_m'):
                assert np.asarray(state[key]).shape == (3,) and np.isfinite(state[key]).all(), key
            pose = root @ csc.fk(urdf['joints'], end, state['q_rad'])
            world = meshes[end][0] @ pose[:3, :3].T + pose[:3, 3]
            lowest = state['palm_lowest_vertex']
            index = lowest['vertex_index']
            assert 0 <= index < len(world), 'invalid recorded vertex'
            assert np.max(np.abs(world[index] - lowest['position_m'])) < 1e-9, 'marker/FK mismatch'
            assert abs(world[:, 2].min() - lowest['height_m']) < 1e-9, 'height/FK mismatch'
            assert np.max(np.abs(pose[:3, 2] - state['palm_normal'])) < 1e-9, 'normal/FK mismatch'
            assert np.max(np.abs(pose[:3, :3] @ reference_local + pose[:3, 3]
                                 - state['reference_point_m'])) < 1e-9, 'reference/FK mismatch'
    return report, urdf, meshes, root, tracks


def _world(urdf, meshes, root, q):
    return {link: (v @ pose[:3, :3].T + pose[:3, 3]) @ root[:3, :3].T + root[:3, 3]
            for link, (v, _) in meshes.items() for pose in [csc.fk(urdf['joints'], link, q)]}


def _plot(output, leg, stats, plt):
    s = np.array(stats['s'])
    q = np.array(stats['q_rad'])
    moving = np.flatnonzero(np.any(q != q[0], axis=0))
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), constrained_layout=True)
    for i in moving:
        name = stats['joint_names'][i]
        axes[0].plot(s, q[:, i], label=name)
        if len(s) > 1 and 'recorded_dq_dc_rad' not in stats:
            axes[1].stairs(np.array(stats['segment_slope_rad_per_s_parameter'])[:, i], s, label=name)
    if 'recorded_dq_dc_rad' in stats:
        for i, name in enumerate(stats['analytic_joint_names']):
            axes[1].plot(s, np.array(stats['recorded_dq_dc_rad'])[:, i], label=name)
    if len(moving):
        axes[0].legend(fontsize=8)
    axes[0].set_ylabel('joint angle [rad]')
    axes[1].set_ylabel('recorded analytic dq/dc [rad/c]' if 'recorded_dq_dc_rad' in stats else
                       'sample secant dq/ds [rad / path parameter]')
    frames = stats['frames']
    sample_s = [f['s'] for f in frames]
    reference = np.array([f['reference_point_m'] for f in frames])
    lowest = np.array([f['lowest_vertex']['height_m'] for f in frames])
    axes[2].plot(sample_s, reference[:, 0] - reference[0, 0], label='reference dx [m]')
    axes[2].plot(sample_s, reference[:, 1] - reference[0, 1], label='reference dy [m]')
    axes[2].plot(sample_s, lowest, label='recorded minimum z [m]')
    axes[2].legend(fontsize=8)
    axes[2].set_ylabel('recorded displacement / height [m]')
    for ax in axes:
        ax.set_xlabel('s [dimensionless; NOT time]')
        for seam in stats['internal_seams']:
            if seam['incoming_phase'] != seam['outgoing_phase']:
                ax.axvline(seam['s'], color='gray', alpha=.4)
    fig.suptitle(f'{leg}: recorded path / ' + ('analytic dq/dc samples' if 'recorded_dq_dc_rad' in stats else
                                             'piecewise-linear secants') + '; no speed verdict')
    fig.savefig(output / f'{leg}_trajectory.png', dpi=120)
    plt.close(fig)


def _render(output, leg, stats, frames, urdf, meshes, root, plt, combined_tracks=None, root_offsets=None):
    from matplotlib.collections import PolyCollection
    from PIL import Image

    offsets = np.zeros((len(frames), 3)) if root_offsets is None else np.asarray(root_offsets, dtype=float)
    assert offsets.shape == (len(frames), 3) and np.isfinite(offsets).all()
    worlds = [{link: vertices + shift for link, vertices in _world(urdf, meshes, root, f['state']['q_rad']).items()}
              for f, shift in zip(frames, offsets)]
    points = np.concatenate([v for world in worlds for v in world.values()])
    lo, hi = points.min(axis=0) - .08, points.max(axis=0) + .08
    lo[2], hi[2] = min(lo[2], -.08), max(hi[2], .08)
    for view, (x, y, depth) in {'side': (0, 2, 1), 'top': (0, 1, 2)}.items():
        fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
        triangles = PolyCollection([], edgecolors='none', alpha=.55)
        ax.add_collection(triangles)
        reference, = ax.plot([], [], 'ko', ms=4, label='reference (not material contact)')
        lowest, = ax.plot([], [], 'mo', ms=4, label='recorded lowest vertex')
        normal, = ax.plot([], [], 'm-', lw=1)
        if combined_tracks is not None:
            markers = {}
            for name, color in zip(sorted(combined_tracks), ('orange', 'green', 'purple', 'red')):
                point, = ax.plot([], [], 'o', color=color, ms=4, label=name + ' reference')
                contact, = ax.plot([], [], 'x', color=color, ms=5)
                arrow, = ax.plot([], [], '-', color=color, lw=1)
                markers[name] = point, contact, arrow
        ax.set_xlim(lo[x], hi[x])
        ax.set_ylim(lo[y], hi[y])
        ax.set_aspect('equal')
        ax.set_xlabel('root/world x [m]')
        ax.set_ylabel('root/world z [m]' if view == 'side' else 'root/world y [m]')
        if view == 'side':
            ax.axhline(0, color='gray', lw=.7)
        ax.legend(fontsize=7, loc='lower left')
        images = []
        for frame_index, (f, world) in enumerate(zip(frames, worlds)):
            faces = np.concatenate([world[link][indices] for link, (_, indices) in meshes.items()])
            colors = np.concatenate([np.tile([1., .35, .15] if link.startswith(leg + '_') else [.2, .4, .7],
                                              (len(indices), 1)) for link, (_, indices) in meshes.items()])
            order = np.argsort(faces[:, :, depth].mean(axis=1))
            triangles.set_verts(faces[order][:, :, [x, y]])
            triangles.set_facecolors(colors[order])
            state = f['state']
            shift = offsets[frame_index]
            point = np.array(state['reference_point_m']) + shift
            contact = np.array(state['palm_lowest_vertex']['position_m']) + shift
            tip = point + np.array(state['palm_normal']) * .08
            reference.set_data([point[x]], [point[y]])
            lowest.set_data([contact[x]], [contact[y]])
            normal.set_data([point[x], tip[x]], [point[y], tip[y]])
            status = 'local closed samples' if stats['completed_local_loop'] else 'accepted prefix ONLY'
            ax.set_title(f'{leg} {status} | {f["phase"]} | s={f["s"]:.5f} {f["kind"]}\n'
                         f'vertex={state["palm_lowest_vertex"]["vertex_index"]}; collision triangles; playback NOT time')
            if combined_tracks is not None:
                reference.set_data([], [])
                lowest.set_data([], [])
                normal.set_data([], [])
                phases = []
                for name, (_, leg_frames) in combined_tracks.items():
                    item = leg_frames[frame_index]
                    value = item['state']
                    p = np.array(value['reference_point_m']) + shift
                    v = np.array(value['palm_lowest_vertex']['position_m']) + shift
                    tip = p + np.array(value['palm_normal']) * .08
                    a, b, arrow = markers[name]
                    a.set_data([p[x]], [p[y]])
                    b.set_data([v[x]], [v[y]])
                    arrow.set_data([p[x], tip[x]], [p[y], tip[y]])
                    phases.append(name + ':' + item['phase'])
                root_label = ('fixed root' if root_offsets is None else
                              f'root x={shift[0]:.5f} m; restart is reset')
                ax.set_title(f'four-leg recorded {status} | c={f["s"]:.5f}\n'
                             + ' '.join(phases) + '\n' + root_label + '; playback NOT physical time')
            fig.canvas.draw()
            images.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()))
        images[0].save(output / f'{leg}_{view}.gif', save_all=True, append_images=images[1:], duration=100, loop=0)
        plt.close(fig)


def _run(source, output, drive_report=None, apply_root_translation=False):
    assert REPO / 'rl_exp/out' in output.parents and not output.exists(), 'fresh isolated output required'
    source = artifact_path(source)
    report, urdf, meshes, root, tracks = _load(source)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import PIL

    combined = report['mode'] != 'budgeted_local_path'
    assert combined or not apply_root_translation, 'root translation requires combined poses'
    prerequisites = _root_prerequisites(report, urdf, meshes, root, tracks) if combined else None
    frames = next(iter(tracks.values()))[1]
    saved_offsets = report.get('root_offsets_m')
    if saved_offsets is not None:
        assert len(saved_offsets) == report['legs']['combined']['pose_count'], 'root/pose count mismatch'
        saved_offsets = saved_offsets[:len(frames)]
    translation = (_root_translation(prerequisites, frames, saved_offsets)
                   if apply_root_translation or 'root_offsets_m' in report else None)
    rates = _rate_prerequisites(report) if combined else None
    drive = _drive_prerequisites(report, drive_report, rates) if drive_report is not None else None
    output.mkdir(parents=True, exist_ok=False)
    for leg, (stats, frames) in tracks.items():
        assert leg.isidentifier(), 'unsafe leg output name'
        _plot(output, leg, stats, plt)
        if not combined:
            _render(output, leg, stats, frames, urdf, meshes, root, plt)
    if combined:
        stats, frames = next(iter(tracks.values()))
        _render(output, 'combined', stats, frames, urdf, meshes, root, plt, tracks,
                None if translation is None else translation['offsets_m'])
        if translation is not None:
            fig, (ax, residual_ax) = plt.subplots(2, 1, figsize=(8, 5), constrained_layout=True)
            for i, axis in enumerate('xyz'):
                ax.plot(translation['c'], np.array(translation['offsets_m'])[:, i], label=axis)
            ax.set_ylabel('root offset [m]')
            ax.legend()
            for leg in sorted(tracks):
                values = [(row['after_c'], c['horizontal_material_displacement_m'])
                          for row in translation['rows'] for c in row['contacts'] if c['leg'] == leg]
                if values:
                    residual_ax.scatter(*zip(*values), s=7, label=leg)
            residual_ax.set(xlabel='cycle parameter c (not seconds)', ylabel='material delta per interval [m]')
            residual_ax.legend()
            fig.savefig(output / 'root_translation.png', dpi=120)
            plt.close(fig)
    result = {'mode': 'recorded_combined_path_analysis' if combined else 'recorded_local_path_analysis',
              'source_report': str(source), 'source_report_sha256': digest(source),
              'source_identity': report['identity'],
              'postprocess_code_sha256': {str(Path(p).resolve()): digest(Path(p))
                                           for p in (__file__, csc.__file__, REPO / 'rl_exp/tools/runrecord/binding.py')},
              'render_versions': {'numpy': np.__version__, 'matplotlib': matplotlib.__version__, 'Pillow': PIL.__version__},
              'render': {'geometry': 'actual collision triangles, orthographic projection',
                         'frame_selection': ('all accepted recorded combined poses; no added poses' if combined else
                                             'all recorded accepted endpoints and midpoints; no added poses'),
                         'display_duration_ms': 100, 'display_loop_only': True},
              'root_motion_prerequisites': prerequisites,
              'root_translation': translation,
              'time_mapping_prerequisites': rates,
              'drive_limit_prerequisites': drive,
              'legs': {leg: stats for leg, (stats, _) in tracks.items()},
              'artifacts_sha256': {p.name: digest(p) for p in sorted(output.iterdir())},
              'limits': 'No new collision/contact validation, continuous-domain proof, smoothing, time mapping, '
                        'physical speed, acceleration, no-slip, PD or dynamics verdict. Slopes use endpoints and '
                        'dimensionless s, not display pacing. Partial-path GIF repeats are not closing segments.'}
    (output / 'analysis.json').write_text(json.dumps(result, indent=1, allow_nan=False), encoding='utf-8')
    print(json.dumps({leg: {'accepted_points': stats['accepted_points'], 'recorded_frames': len(frames),
                           'max_internal_slope_jump': stats['max_abs_internal_slope_jump_rad_per_s_parameter'],
                           'cycle_slope_jump': stats['cycle_slope_jump_rad_per_s_parameter']}
                      for leg, (stats, frames) in tracks.items()}, indent=1), flush=True)


def _self_check(break_test=None):
    if break_test:
        import inspect
        from unittest.mock import patch
        mutations = {'slope_scale': (_path_stats, 'delta / ds[:, None]', 'delta'),
                     'cycle_sign': (_path_stats, 'slopes[0] - slopes[-1]', 'slopes[-1] - slopes[0]'),
                     'midpoint': (_track, "<= 1e-12, 'wrong midpoint'", "<= 1., 'wrong midpoint'"),
                     'world': (_world, '+ root[:3, 3]', '+ 0'),
                     'combined_stop': (_combined_tracks, "if row['failures']:", 'if False:'),
                     'translation_sign': (_translation_fit, '-delta.mean(axis=0)', 'delta.mean(axis=0)'),
                     'translation_residual': (_translation_fit, 'residual = delta + translation', 'residual = delta * 0'),
                     'material_index': (_material_delta, 'after[index] - before[index]', 'after[index] - before[0]'),
                     'rate_peak': (_rate_prerequisites, 'rate * 15 / 8', 'rate'),
                     'acceleration_peak': (_rate_prerequisites, '10 / np.sqrt(3)', '1.'),
                     'drive_period': (_drive_prerequisites, "/ by_name[row['joint']]", "* by_name[row['joint']]"),
                     'drive_identity': (_drive_prerequisites, "drive['input']['urdf_sha256'] == build['candidate_sha256']", 'True')}
        mutations.update({
            'root_accumulate': (_root_translation, 'offset = offset + step', 'offset = step'),
            'root_horizontal': (_root_translation, "np.r_[-delta[:, :2].mean(axis=0), 0.]", '-delta.mean(axis=0)'),
            'root_residual': (_root_translation, 'residual = delta + step', 'residual = delta * 0'),
        })
        function, old, new = mutations[break_test]
        code = inspect.getsource(function)
        assert old in code
        scope = {}
        exec(code.replace(old, new), globals(), scope)
        with patch.dict(globals(), {function.__name__: scope[function.__name__]}):
            _self_check()
        return
    from copy import deepcopy
    stats = _path_stats(np.array([0., .2, .5]), np.array([[0., 0.], [.4, 0.], [0., 0.]]),
                        ['neutral', 'out', 'back'], True)
    assert np.allclose(stats['segment_slope_rad_per_s_parameter'], [[2., 0.], [-4 / 3, 0.]])
    assert np.allclose(stats['cycle_slope_jump_rad_per_s_parameter'], [10 / 3, 0.])
    assert np.allclose(stats['internal_seams'][0]['slope_jump_rad_per_s_parameter'], [-10 / 3, 0.])
    partial = _path_stats(np.array([0., .2]), np.array([[0.], [.4]]), ['neutral', 'out'], False)
    assert partial['cycle_slope_jump_rad_per_s_parameter'] is None
    state = lambda q: {'q_rad': {'joint': q}, 'reference_point_m': [0., 0., 0.], 'task_m': [0., 0., 0.],
                       'palm_normal': [0., 0., 1.],
                       'palm_lowest_vertex': {'position_m': [0., 0., 0.], 'height_m': 0., 'vertex_index': 0}}
    data = {'completed_local_loop': False, 'accepted_points': 1, 'failure_phase': 'back',
            'rows': [{'phase': 'neutral', 's': 0., 'state': state(0.)},
                     {'phase': 'out', 's': .2, 'state': state(.4), 'midpoint': state(.2), 'failures': []},
                     {'phase': 'back', 's': .5, 'state': state(0.), 'failures': ['contact']}]}
    summary, frames = _track(data)
    assert len(frames) == 3 and summary['s'] == [0., .2] and frames[-1]['q'][0] == .4
    assert summary['cycle_slope_jump_rad_per_s_parameter'] is None
    broken = deepcopy(data)
    broken['rows'][1]['midpoint']['q_rad']['joint'] = .1
    for call in (lambda: _track(broken),
                 lambda: _path_stats(np.array([0., 0.]), np.array([[0.], [1.]]), ['a', 'b'], False),
                 lambda: _path_stats(np.array([0., 1.]), np.array([[0.], [1.]]), ['a', 'b'], True)):
        try:
            call()
        except AssertionError:
            pass
        else:
            raise AssertionError('invalid path accepted')
    urdf = {'joints': {'move': {'parent': 'base', 'child': 'tip', 'origin': np.array([1., 0., 0.]),
                              'axis': None}}}
    meshes = {'tip': (np.array([[0., 0., 0.]]), np.zeros((1, 3), dtype=int))}
    root = np.eye(4)
    root[2, 3] = 2.
    assert np.array_equal(_world(urdf, meshes, root, {})['tip'], [[1., 0., 2.]])
    combined = {'completed_combined_loop': False, 'failure': {'s': .5}, 'pose_count': 3,
                'rows': [{'s': s, 'q_rad': {'joint': q}, 'failures': failure,
                          'legs': {leg: {'phase': 'backward_contact', 'state': state(q)}
                                   for leg in ('lf', 'rf', 'rl', 'rr')}}
                         for s, q, failure in ((0., 0., []), (.25, .1, []), (.5, .2, ['failed']))]}
    tracks = _combined_tracks(combined)
    assert all(len(frames) == 2 and not stats['completed_local_loop']
               for stats, frames in tracks.values()), 'combined failed frame rendered'
    assert np.allclose(_translation_fit([[1., 0., 0.], [1., 0., 0.]])['root_translation_candidate_m'], [-1., 0., 0.])
    assert _translation_fit([[1., 0., 0.], [-1., 0., 0.]])['max_material_residual_m'] == 1.
    assert np.array_equal(_material_delta(np.array([[9., 0., 0.], [1., 0., 0.]]),
                                         np.array([[1., 0., 0.], [3., 0., 0.]]), 1), [2., 0., 0.])
    intervals = {'rows': [{'before_c': a, 'after_c': b,
                          'contacts': [{'same_vertex_displacement_m': delta, 'same_vertex_contact_at_both': True}
                                       for delta in ([-2., 1., .1], [-4., -1., -.2])]}
                         for a, b in ((0., .4), (.4, 1.))]}
    translated = _root_translation(intervals, [{'s': c} for c in (0., .4, 1.)])
    assert np.allclose(translated['offsets_m'], [[0., 0., 0.], [3., 0., 0.], [6., 0., 0.]])
    assert np.isclose(translated['max_persistent_contact_displacement_m'], np.sqrt(2))
    assert translated['rows'][0]['contacts'][0]['world_material_displacement_m'] == [1., 1., .1]
    prescribed = _root_translation(intervals, [{'s': c} for c in (0., .4, 1.)],
                                    [[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]])
    assert prescribed['net_translation_m'] == [2., 0., 0.]
    assert prescribed['rows'][0]['contacts'][0]['world_material_displacement_m'] == [-1., 1., .1]
    try:
        _root_translation(intervals, [{'s': c} for c in (0., .3, 1.)])
    except AssertionError:
        pass
    else:
        raise AssertionError('root interval gap accepted')
    from unittest.mock import patch
    original = {'legs': {'lf': {'rows': [{'state': {'q_rad': {'lf_joint': i / 32}}}
                                       for i in range(33)]}}}
    with patch.object(Path, 'read_text', return_value=json.dumps(original)), \
            patch.dict(globals(), {'artifact_path': lambda p, *args: p}):
        rates = _rate_prerequisites({'mode': 'sampled_local_path_support_schedule', 'source_report': 'unused',
                                     'source_report_sha256': 'fixture',
                                     'legs': {'combined': {'schedule': {'phase_fractions': [.625, .125, .125, .125]},
                                                           'joint_mapping': {'lf': [{'source': 'lf_joint', 'target': 'lf_joint'}]}}}})
    assert rates['joints'][0]['analytic_max_abs_dq_dc_rad'] == 3.75
    assert np.isclose(rates['joints'][0]['analytic_max_abs_d2q_dc2_rad'], 1280 / np.sqrt(3))
    fixture = {'completed': True, 'input': {'urdf_sha256': 'candidate', 'manifest': 'manifest',
                                          'manifest_sha256': 'hash', 'usd_sha256': 'hash'},
               'joint_names': ['lf_joint'], 'live_readbacks': {'fields': {'joint_vel_limits': [[5.]]}}}
    def text(path, **kwargs):
        if str(path) == 'manifest':
            return json.dumps({'target_binding': {'target': 'usd'}})
        if str(path) in ('candidate', 'foreign'):
            return json.dumps({'candidate_sha256': str(path)})
        return json.dumps(fixture)
    with patch.object(Path, 'read_text', text), patch.dict(globals(), {
            'digest': lambda p: 'hash', 'artifact_path': lambda p, *args: p}):
        result = _drive_prerequisites({'identity': {'build_report': 'candidate'}}, Path('drive'), rates)
        assert result['velocity_only_period_lower_bound_s'] == .75
        try:
            _drive_prerequisites({'identity': {'build_report': 'foreign'}}, Path('drive'), rates)
        except AssertionError:
            pass
        else:
            raise AssertionError('foreign drive identity accepted')
    assert 'palm_spatial_probe' not in sys.modules, 'postprocessor imported solver'
    print('LOCAL_PATH_VIEW_SELF_CHECK_OK: nonuniform slopes, seams, partial prefix, midpoint and mesh FK')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source_report', type=Path)
    parser.add_argument('--output_dir', type=Path)
    parser.add_argument('--drive_report', type=Path)
    parser.add_argument('--root_translation', action='store_true')
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--break_test', choices=('slope_scale', 'cycle_sign', 'midpoint', 'world',
                                               'combined_stop', 'translation_sign', 'translation_residual',
                                               'material_index', 'rate_peak', 'acceleration_peak',
                                               'drive_period', 'drive_identity', 'root_accumulate',
                                               'root_horizontal', 'root_residual'))
    args = parser.parse_args()
    if args.self_check:
        if (args.source_report is not None or args.output_dir is not None or args.drive_report is not None
                or args.root_translation):
            parser.error('--self_check cannot use input/output')
        _self_check(args.break_test)
    else:
        if args.break_test:
            parser.error('--break_test requires --self_check')
        if args.source_report is None or args.output_dir is None:
            parser.error('--source_report and --output_dir required')
        _run(args.source_report.resolve(), args.output_dir.resolve(),
             None if args.drive_report is None else args.drive_report.resolve(), args.root_translation)


if __name__ == '__main__':
    main()
