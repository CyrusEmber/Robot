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
"""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'rl_exp/tools/verify'))
import check_self_collision as csc  # noqa: E402
sys.path.insert(0, str(REPO / 'rl_exp/tools/runrecord'))
from binding import sha256_file as digest  # noqa: E402


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


def _load(source):
    report = json.loads(source.read_text(encoding='utf-8'))
    assert report['mode'] == 'budgeted_local_path', 'unsupported report schema'
    identity = report['identity']
    build_path = Path(identity['build_report'])
    assert digest(build_path) == identity['build_report_sha256'], 'build changed'
    build = json.loads(build_path.read_text(encoding='utf-8'))
    candidate = Path(build['candidate_urdf']).resolve()
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
    tracks = {leg: _track(data) for leg, data in report['legs'].items()}
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
        if len(s) > 1:
            axes[1].stairs(np.array(stats['segment_slope_rad_per_s_parameter'])[:, i], s, label=name)
    if len(moving):
        axes[0].legend(fontsize=8)
    axes[0].set_ylabel('joint angle [rad]')
    axes[1].set_ylabel('dq/ds [rad / path parameter]')
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
    fig.suptitle(f'{leg}: recorded path / piecewise-linear slopes; no speed verdict')
    fig.savefig(output / f'{leg}_trajectory.png', dpi=120)
    plt.close(fig)


def _render(output, leg, stats, frames, urdf, meshes, root, plt):
    from matplotlib.collections import PolyCollection
    from PIL import Image

    worlds = [_world(urdf, meshes, root, f['state']['q_rad']) for f in frames]
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
        ax.set_xlim(lo[x], hi[x])
        ax.set_ylim(lo[y], hi[y])
        ax.set_aspect('equal')
        ax.set_xlabel('root/world x [m]')
        ax.set_ylabel('root/world z [m]' if view == 'side' else 'root/world y [m]')
        if view == 'side':
            ax.axhline(0, color='gray', lw=.7)
        ax.legend(fontsize=7, loc='lower left')
        images = []
        for f, world in zip(frames, worlds):
            faces = np.concatenate([world[link][indices] for link, (_, indices) in meshes.items()])
            colors = np.concatenate([np.tile([1., .35, .15] if link.startswith(leg + '_') else [.2, .4, .7],
                                              (len(indices), 1)) for link, (_, indices) in meshes.items()])
            order = np.argsort(faces[:, :, depth].mean(axis=1))
            triangles.set_verts(faces[order][:, :, [x, y]])
            triangles.set_facecolors(colors[order])
            state = f['state']
            point = np.array(state['reference_point_m'])
            contact = np.array(state['palm_lowest_vertex']['position_m'])
            tip = point + np.array(state['palm_normal']) * .08
            reference.set_data([point[x]], [point[y]])
            lowest.set_data([contact[x]], [contact[y]])
            normal.set_data([point[x], tip[x]], [point[y], tip[y]])
            status = 'local closed samples' if stats['completed_local_loop'] else 'accepted prefix ONLY'
            ax.set_title(f'{leg} {status} | {f["phase"]} | s={f["s"]:.5f} {f["kind"]}\n'
                         f'vertex={state["palm_lowest_vertex"]["vertex_index"]}; collision triangles; playback NOT time')
            fig.canvas.draw()
            images.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()))
        images[0].save(output / f'{leg}_{view}.gif', save_all=True, append_images=images[1:], duration=100, loop=0)
        plt.close(fig)


def _run(source, output):
    assert REPO / 'rl_exp/out' in output.parents and not output.exists(), 'fresh isolated output required'
    report, urdf, meshes, root, tracks = _load(source)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import PIL

    output.mkdir(parents=True, exist_ok=False)
    for leg, (stats, frames) in tracks.items():
        assert leg.isidentifier(), 'unsafe leg output name'
        _plot(output, leg, stats, plt)
        _render(output, leg, stats, frames, urdf, meshes, root, plt)
    result = {'mode': 'recorded_local_path_analysis',
              'source_report': str(source), 'source_report_sha256': digest(source),
              'source_identity': report['identity'],
              'postprocess_code_sha256': {str(Path(p).resolve()): digest(Path(p))
                                           for p in (__file__, csc.__file__, REPO / 'rl_exp/tools/runrecord/binding.py')},
              'render_versions': {'numpy': np.__version__, 'matplotlib': matplotlib.__version__, 'Pillow': PIL.__version__},
              'render': {'geometry': 'actual collision triangles, orthographic projection',
                         'frame_selection': 'all recorded accepted endpoints and midpoints; no added poses',
                         'display_duration_ms': 100, 'display_loop_only': True},
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
                     'world': (_world, '+ root[:3, 3]', '+ 0')}
        function, old, new = mutations[break_test]
        code = inspect.getsource(function)
        assert old in code
        scope = dict(globals())
        exec(code.replace(old, new), scope)
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
    assert 'palm_spatial_probe' not in sys.modules, 'postprocessor imported solver'
    print('LOCAL_PATH_VIEW_SELF_CHECK_OK: nonuniform slopes, seams, partial prefix, midpoint and mesh FK')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source_report', type=Path)
    parser.add_argument('--output_dir', type=Path)
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--break_test', choices=('slope_scale', 'cycle_sign', 'midpoint', 'world'))
    args = parser.parse_args()
    if args.self_check:
        if args.source_report is not None or args.output_dir is not None:
            parser.error('--self_check cannot use input/output')
        _self_check(args.break_test)
    else:
        if args.break_test:
            parser.error('--break_test requires --self_check')
        if args.source_report is None or args.output_dir is None:
            parser.error('--source_report and --output_dir required')
        _run(args.source_report.resolve(), args.output_dir.resolve())


if __name__ == '__main__':
    main()
