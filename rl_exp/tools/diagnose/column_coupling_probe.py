# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Repeatable zero-action column-coupling diagnostic, not an eval protocol.

Run from the repository root with the IsaacLab Python:
    python rl_exp/tools/diagnose/column_coupling_probe.py run --output <new-directory> --steps 100
    python rl_exp/tools/diagnose/column_coupling_probe.py compare <run-directory>
    python rl_exp/tools/diagnose/column_coupling_probe.py selftest

Every subprocess gets its own log and raw .npz. Auto-reset remains enabled, but
its actual call is intercepted and pre-reset state and per-env IDs are stored.
Compare paired pre-reset captures before post-step samples at each step. A
pre-reset divergence is reset-clean if neither arm reset that env on prior steps;
a post-step divergence also counts resets in the current step. When only one arm
resets, the other arm's corresponding pre-reset state was not captured. The
first_* fields identify the first observable difference, not necessarily the
first difference; first_is_provable is false after an unpaired pre-reset sample.
Other environments' resets and unobserved PhysX state remain possible channels.
Hashes bind recorded files for consistency, not authenticity: coordinated archive
changes are undetectable. Joint names are metadata only, not independently verified.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

import numpy as np

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from ablation_harness.host_paths import isaac_root  # noqa: E402
from rl_exp.tools.runrecord.binding import sha256_bytes, sha256_file  # noqa: E402

FIELDS = ('pos', 'quat', 'lin', 'ang', 'qpos', 'qvel')
RUNS = ('ctrl1', 'ctrl2', 'rougha1', 'rougha2')
NAMES = ('flat', 'slope_5deg', 'slope_10deg', 'stairs_10cm', 'stairs_20cm',
         'rough_a', 'rough_b', 'gap_20cm', 'gap_40cm')


def sha(path):
    digest = sha256_file(path)
    if digest is None:
        raise OSError(f'cannot hash file: {path}')
    return digest


def bits_differ(a, b):
    if a.shape != b.shape or a.dtype != b.dtype:
        raise ValueError('state shape or dtype mismatch')
    return np.any(np.ascontiguousarray(a).view(np.uint8).reshape(*a.shape[:2], -1)
                  != np.ascontiguousarray(b).view(np.uint8).reshape(*b.shape[:2], -1), axis=-1)


def validate(data):
    required = set(FIELDS) | {'types', 'terminated', 'truncated', 'reset', 'reset_pre_valid'} | {
        'reset_pre_' + field for field in FIELDS}
    if not required.issubset(data.files):
        raise ValueError(f'missing raw arrays: {sorted(required - set(data.files))}')
    types = data['types']
    if types.shape != (72,) or not np.array_equal(np.bincount(types, minlength=9), np.full(9, 8)):
        raise ValueError('expected exactly 8 environments per terrain')
    shape = data['pos'].shape[:2]
    if len(shape) != 2 or shape[0] < 2 or shape[1] != 72:
        raise ValueError('incomplete state trajectory')
    for field in ('terminated', 'truncated', 'reset', 'reset_pre_valid'):
        if data[field].shape != shape or data[field].dtype != np.bool_:
            raise ValueError(f'incomplete flags {field}')
    widths = {'pos': 3, 'quat': 4, 'lin': 3, 'ang': 3}
    for field in FIELDS:
        a, pre = data[field], data['reset_pre_' + field]
        if (a.ndim != 3 or a.shape[:2] != shape or a.shape[2] == 0
                or (field in widths and a.shape[2] != widths[field])
                or pre.shape != a.shape or pre.dtype != a.dtype or a.dtype.kind != 'f'):
            raise ValueError(f'incomplete field {field}')
        if not np.isfinite(a).all():
            raise ValueError(f'non-finite {field}')
        if not np.isfinite(pre[data['reset_pre_valid']]).all():
            raise ValueError(f'non-finite reset_pre_{field}')
    if data['qpos'].shape[2] != data['qvel'].shape[2]:
        raise ValueError('joint width mismatch')
    if not np.array_equal(data['reset'], data['reset_pre_valid']):
        raise ValueError('reset/pre-reset capture mismatch')
    if any(data[f][0].any() for f in ('terminated', 'truncated', 'reset')):
        raise ValueError('unexpected initial event')
    if not np.array_equal(data['reset'], data['terminated'] | data['truncated']):
        raise ValueError('reset/done mismatch')


def compare_pair(left, right):
    validate(left)
    validate(right)
    if not np.array_equal(left['types'], right['types']):
        raise ValueError('environment terrain assignments differ')
    differences = {f: bits_differ(left[f], right[f]) for f in FIELDS}
    both_reset = left['reset_pre_valid'] & right['reset_pre_valid']
    pre_differences = {f: bits_differ(left['reset_pre_' + f], right['reset_pre_' + f]) & both_reset
                       for f in FIELDS}
    any_diff = np.logical_or.reduce(list(differences.values()))
    any_pre_diff = np.logical_or.reduce(list(pre_differences.values()))
    reset = left['reset'] | right['reset']
    rows = []
    for env in range(72):
        steps = np.flatnonzero(any_diff[:, env] | any_pre_diff[:, env])
        step = int(steps[0]) if len(steps) else None
        phase = ('pre_reset' if any_pre_diff[step, env] else 'initial' if step == 0 else 'post_step') if step is not None else None
        first_diff = pre_differences if phase == 'pre_reset' else differences
        end = step if phase == 'pre_reset' else step + 1 if step is not None else 0
        rows.append({'env': env, 'column': int(left['types'][env]),
                     'terrain': NAMES[int(left['types'][env])], 'first_step': step, 'first_phase': phase,
                     'first_fields': [f for f in FIELDS if step is not None and first_diff[f][step, env]],
                     'first_is_provable': (not (left['reset'][:step + 1, env] ^ right['reset'][:step + 1, env]).any()) if step is not None else None,
                     'reset_through_first': bool(reset[:end, env].any()) if step is not None else None,
                     'pre_uncomparable_steps': np.flatnonzero(left['reset'][:, env] ^ right['reset'][:, env]).tolist(),
                     'reset_steps_left': np.flatnonzero(left['reset'][:, env]).tolist(),
                     'reset_steps_right': np.flatnonzero(right['reset'][:, env]).tolist(),
                     'terminated_steps_left': np.flatnonzero(left['terminated'][:, env]).tolist(),
                     'terminated_steps_right': np.flatnonzero(right['terminated'][:, env]).tolist(),
                     'truncated_steps_left': np.flatnonzero(left['truncated'][:, env]).tolist(),
                     'truncated_steps_right': np.flatnonzero(right['truncated'][:, env]).tolist()})
    return rows


def compare(root, write_report=False):
    directories = [(root / name / 'capture') if (root / name / 'capture').is_dir() else (root / name) for name in RUNS]
    metas = [json.loads((directory / 'metadata.json').read_text(encoding='utf-8')) for directory in directories]
    for name, directory, meta in zip(RUNS, directories, metas):
        if meta['status'] != 'complete' or meta['name'] != name:
            raise ValueError(f'incomplete or misidentified run: {name}')
        if sha(directory / 'raw.npz') != meta['raw_sha256']:
            raise ValueError(f'raw hash mismatch: {name}')
    if len({m['steps'] for m in metas}) != 1:
        raise ValueError('step count mismatch')
    snapshot = root / 'capture_script.py'
    if not snapshot.is_file():
        raise ValueError(f'capture script snapshot missing: {snapshot}')
    snapshot_hash = sha(snapshot)
    if any(m['script_sha256'] != snapshot_hash for m in metas):
        raise ValueError('capture script snapshot hash mismatch')
    print('identity: snapshot and raw hashes checked; joint names are metadata only; '
          'coordinated archive tampering is not detectable', flush=True)
    def check_equal(a, b, path, allowed=()):
        if path in allowed:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            if a.keys() != b.keys():
                raise ValueError(f'metadata mismatch: {path} keys')
            for key in a:
                check_equal(a[key], b[key], f'{path}.{key}', allowed)
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                raise ValueError(f'metadata mismatch: {path} length')
            for i, (x, y) in enumerate(zip(a, b)):
                check_equal(x, y, f'{path}[{i}]', allowed)
        elif type(a) is not type(b) or a != b:
            raise ValueError(f'metadata mismatch: {path}')

    for a, b in ((0, 1), (2, 3)):
        check_equal(metas[a]['config'], metas[b]['config'], 'config')
        check_equal(metas[a]['terrain'], metas[b]['terrain'], 'terrain', {'terrain.cfg_id'})
    prefix = 'config.scene.terrain.terrain_generator.sub_terrains.rough_b.'
    check_equal(metas[0]['config'], metas[2]['config'], 'config',
                {prefix + k for k in ('noise_range', 'noise_step', 'downsampled_scale')})
    generators = [m['config']['scene']['terrain']['terrain_generator'] for m in metas]
    rough = [g['sub_terrains']['rough_b'] for g in generators]
    if all(rough[0][k] == rough[2][k] for k in ('noise_range', 'noise_step', 'downsampled_scale')):
        raise ValueError('terrain intervention config unchanged')
    terrain_a, terrain_b = metas[0]['terrain'], metas[2]['terrain']
    check_equal({k: v for k, v in terrain_a.items() if k != 'cells'},
                {k: v for k, v in terrain_b.items() if k != 'cells'}, 'terrain',
                {'terrain.cfg_id', 'terrain.geometry_digest'})
    cells_a = {(c['row'], c['col']): c for c in terrain_a['cells']}
    cells_b = {(c['row'], c['col']): c for c in terrain_b['cells']}
    if len(cells_a) != len(terrain_a['cells']) or len(cells_b) != len(terrain_b['cells']) or cells_a.keys() != cells_b.keys():
        raise ValueError('metadata mismatch: terrain.cells coordinates')
    if (0, 6) not in cells_a or cells_a[(0, 6)].get('sub_terrain') != 'rough_b':
        raise ValueError('metadata mismatch: terrain.cells rough_b')
    for key in cells_a:
        path = f'terrain.cells[{key[0]},{key[1]}]'
        allowed = {path + '.' + k for k in ('params', 'geometry', 'relief')} if key == (0, 6) else set()
        check_equal(cells_a[key], cells_b[key], path, allowed)
    # Generator overwrites these common fields before the probe hashes cfg.to_dict().
    def to_dict_value(value):
        if isinstance(value, dict):
            if set(value) == {'__tuple__'}:
                return [to_dict_value(v) for v in value['__tuple__']]
            if any(k.startswith('__') for k in value):
                raise ValueError('cannot bind terrain params: unsupported snapshot tag')
            return {k: to_dict_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [to_dict_value(v) for v in value]
        return value

    for meta, generator, params in zip(metas, generators, rough):
        params = dict(params, **{k: generator[k] for k in ('size', 'horizontal_scale', 'vertical_scale', 'slope_threshold')})
        text = json.dumps(to_dict_value(params), sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
        expected = 'sha256:' + sha256_bytes(text.encode('utf-8'))
        cell = next(c for c in meta['terrain']['cells'] if (c['row'], c['col']) == (0, 6))
        if cell['params'] != expected:
            raise ValueError(f'terrain cell params/config mismatch: {meta["name"]}')
    if cells_a[(0, 6)] == cells_b[(0, 6)]:
        raise ValueError('terrain intervention is not observable in rough_b cell')
    for meta in metas[1:]:
        check_equal(metas[0]['joint_names'], meta['joint_names'], 'joint_names')
    for key in ('source_hashes', 'asset_directory_files', 'asset_path', 'python', 'torch', 'cuda', 'gpu', 'step_dt'):
        if any(m[key] != metas[0][key] for m in metas[1:]):
            raise ValueError(f'capture identity mismatch: {key}')
    arrays = [np.load(directory / 'raw.npz', allow_pickle=False) for directory in directories]
    try:
        pairs = ((0, 1), (2, 3), (0, 2), (1, 3))
        result = {}
        for data, meta in zip(arrays, metas):
            validate(data)
            names = meta['joint_names']
            if (not isinstance(names, list) or not names or any(not isinstance(n, str) or not n for n in names)
                    or len(set(names)) != len(names) or data['qpos'].shape[2] != len(names)):
                raise ValueError(f'joint width or names mismatch: {meta["name"]}')
        for a, b in pairs:
            rows = compare_pair(arrays[a], arrays[b])
            if (a, b) in ((0, 1), (2, 3)) and (any(
                    r['first_step'] is not None or r['pre_uncomparable_steps'] for r in rows) or any(
                    not np.array_equal(arrays[a][f], arrays[b][f]) for f in ('terminated', 'truncated', 'reset'))):
                raise ValueError(f'same-arm repeatability failure: {RUNS[a]} vs {RUNS[b]}')
            if arrays[a]['pos'].shape[0] != metas[a]['steps'] + 1 or arrays[b]['pos'].shape[0] != metas[b]['steps'] + 1:
                raise ValueError('trajectory shorter than requested')
            result[f'{RUNS[a]}_vs_{RUNS[b]}'] = rows
            print(f'{RUNS[a]} vs {RUNS[b]}: initial_diffs={sum(r["first_step"] == 0 for r in rows)} '
                  f'initial_details={[(r["env"], r["column"], r["terrain"], r["first_fields"]) for r in rows if r["first_step"] == 0]} '
                  f'first_clean={[(r["env"], r["terrain"], r["first_step"], r["first_phase"]) for r in rows if r["first_step"] not in (None, 0) and not r["reset_through_first"]]} '
                  f'first_after_reset={[(r["env"], r["first_step"], r["first_phase"]) for r in rows if r["reset_through_first"]]} '
                  f'pre_uncomparable={[(r["env"], r["pre_uncomparable_steps"]) for r in rows if r["pre_uncomparable_steps"]]} '
                  f'first_only_observable={[(r["env"], r["first_step"], r["first_phase"]) for r in rows if r["first_is_provable"] is False]}', flush=True)
        if write_report:
            output = root / 'comparison.json'
            with output.open('x', encoding='utf-8') as stream:
                json.dump(result, stream, indent=2, allow_nan=False)
                stream.write('\n')
            print(f'comparison: {output}')
    finally:
        for data in arrays:
            data.close()


def selftest():
    import tempfile

    def fixture():
        flags = np.zeros((4, 72), dtype=bool)
        widths = {'pos': 3, 'quat': 4, 'lin': 3, 'ang': 3, 'qpos': 2, 'qvel': 2}
        payload = {f: np.zeros((4, 72, widths[f]), dtype=np.float32) for f in FIELDS}
        payload.update({f'reset_pre_{f}': payload[f].copy() for f in FIELDS})
        payload.update(types=np.repeat(np.arange(9), 8), terminated=flags.copy(), truncated=flags.copy(),
                       reset=flags.copy(), reset_pre_valid=flags.copy())
        return payload

    def reset(payload, step=1, env=9):
        for f in ('reset', 'reset_pre_valid', 'terminated'):
            payload[f][step, env] = True

    with tempfile.TemporaryDirectory() as folder:
        def pair(left, right):
            paths = [Path(folder) / f'{i}.npz' for i in range(2)]
            for path, payload in zip(paths, (left, right)):
                np.savez(path, **payload)
            with np.load(paths[0]) as a, np.load(paths[1]) as b:
                return compare_pair(a, b)

        def rejected(payload, message, left=None):
            try:
                pair(fixture() if left is None else left, payload)
            except ValueError as exc:
                assert message in str(exc), str(exc)
            else:
                raise AssertionError(f'accepted: {message}')

        def pre_reset():
            a, b = fixture(), fixture()
            reset(a)
            reset(b)
            b['reset_pre_pos'][1, 9, 0] = np.nextafter(np.float32(0), np.float32(1))
            b['pos'][1, 9, 1] = 1
            row = pair(a, b)[9]
            assert (row['first_step'], row['first_phase'], row['first_fields'], row['reset_through_first']) == (
                1, 'pre_reset', ['pos'], False)
            b['pos'][1, 9, 1] = 0
            assert pair(a, b)[9]['first_phase'] == 'pre_reset'
            reset(a, 2)
            reset(b, 2)
            b['reset_pre_pos'][1, 9, 0] = 0
            b['reset_pre_qvel'][2, 9, 0] = 1
            row = pair(a, b)[9]
            assert (row['first_step'], row['first_phase'], row['reset_through_first']) == (2, 'pre_reset', True)
            for f in FIELDS:
                a, b = fixture(), fixture()
                reset(a)
                reset(b)
                b['reset_pre_' + f][1, 9, 0] = 1
                assert pair(a, b)[9]['first_fields'] == [f]

        def post_reset():
            a, b = fixture(), fixture()
            assert all(r['first_step'] is None for r in pair(a, b))
            reset(a)
            reset(b)
            a['truncated'][1, 9] = True  # termination and timeout can coincide
            b['pos'][1, 9, 0] = np.nextafter(np.float32(0), np.float32(1))
            row = pair(a, b)[9]
            assert (row['first_step'], row['first_phase'], row['first_fields'], row['reset_through_first']) == (
                1, 'post_step', ['pos'], True)
            b['pos'][0, 9, 0] = 1
            assert (pair(a, b)[9]['first_step'], pair(a, b)[9]['first_phase']) == (0, 'initial')

        def asymmetric():
            a, b = fixture(), fixture()
            reset(a)
            row = pair(a, b)[9]
            assert row['first_step'] is None and row['pre_uncomparable_steps'] == [1]
            b['pos'][2, 9, 0] = 1
            row = pair(a, b)[9]
            assert row['first_step'] == 2 and row['pre_uncomparable_steps'] == [1]

        def shapes():
            for f in FIELDS:
                p = fixture()
                p[f] = p[f][:, :, :0]
                p['reset_pre_' + f] = p['reset_pre_' + f][:, :, :0]
                rejected(p, f'incomplete field {f}', p)
            p = fixture()
            del p['qvel']
            rejected(p, 'missing raw arrays')

        def events():
            for f in ('terminated', 'truncated'):
                p = fixture()
                p[f][1, 9] = True
                rejected(p, 'reset/done mismatch')
                p['reset'][1, 9] = p['reset_pre_valid'][1, 9] = True
                assert pair(p, p)[9]['first_step'] is None
            p = fixture()
            p['reset'][1, 9] = p['reset_pre_valid'][1, 9] = True
            rejected(p, 'reset/done mismatch')
            p = fixture()
            p['reset'][1, 9] = True
            rejected(p, 'reset/pre-reset capture mismatch')
            p = fixture()
            p['terminated'][0, 9] = True
            rejected(p, 'initial')

        def finite_and_widths():
            for f in FIELDS:
                for value in (np.nan, np.inf, -np.inf):
                    p = fixture()
                    p[f][1, 9, 0] = value
                    rejected(p, f'non-finite {f}', p)
                    p = fixture()
                    reset(p)
                    p['reset_pre_' + f][1, 9, 0] = value
                    rejected(p, f'non-finite reset_pre_{f}', p)
                p = fixture()
                p['reset_pre_' + f][1, 9, 0] = np.nan
                assert pair(p, p)[9]['first_step'] is None
            for f in ('pos', 'quat', 'lin', 'ang'):
                p = fixture()
                p[f] = p[f][:, :, :1]
                p['reset_pre_' + f] = p['reset_pre_' + f][:, :, :1]
                rejected(p, f'incomplete field {f}', p)
            p = fixture()
            p['qvel'] = p['qvel'][:, :, :1]
            p['reset_pre_qvel'] = p['reset_pre_qvel'][:, :, :1]
            rejected(p, 'joint width', p)

        def observable():
            a, b = fixture(), fixture()
            reset(a)
            b['pos'][2, 9, 0] = 1
            row = pair(a, b)[9]
            assert row['first_step'] == 2 and not row['first_is_provable']
            a, b = fixture(), fixture()
            reset(a)
            b['pos'][1, 9, 0] = 1
            assert not pair(a, b)[9]['first_is_provable']
            a, b = fixture(), fixture()
            b['pos'][0, 9, 0] = 1
            reset(a)
            assert pair(a, b)[9]['first_is_provable']

        def regression_gaps():
            import contextlib
            import copy
            import io
            from unittest.mock import patch

            root = Path(folder) / 'regressions'
            root.mkdir()
            snapshot = root / 'capture_script.py'
            snapshot.write_bytes(b'capture snapshot')
            generator = {'size': [1, 1], 'horizontal_scale': 0.1, 'vertical_scale': 0.01,
                         'slope_threshold': None, 'sub_terrains': {'rough_b': {
                             'noise_range': [0, 0], 'noise_step': 1, 'downsampled_scale': None}}}
            def param_hash(gen):
                params = dict(gen['sub_terrains']['rough_b'], **{k: gen[k] for k in (
                    'size', 'horizontal_scale', 'vertical_scale', 'slope_threshold')})
                return 'sha256:' + sha256_bytes(json.dumps(params, sort_keys=True, separators=(',', ':'),
                                                            ensure_ascii=False, default=str).encode())
            metas = []
            for i, name in enumerate(RUNS):
                directory = root / name
                directory.mkdir()
                payload = fixture()
                if i >= 2:
                    payload['pos'][0, 48, 0] = 1
                np.savez(directory / 'raw.npz', **payload)
                gen = copy.deepcopy(generator)
                if i >= 2:
                    gen['sub_terrains']['rough_b']['noise_step'] = 2
                cell = {'row': 0, 'col': 6, 'sub_terrain': 'rough_b', 'difficulty': 1,
                        'params': param_hash(gen), 'geometry': str(i >= 2), 'relief': int(i >= 2)}
                metas.append({'name': name, 'status': 'complete', 'steps': 3,
                              'script_sha256': sha(snapshot), 'raw_sha256': sha(directory / 'raw.npz'),
                              'config': {'scene': {'terrain': {'terrain_generator': gen}}},
                              'terrain': {'cfg_id': i, 'geometry_digest': str(i >= 2), 'cells': [cell]},
                              'joint_names': ['a', 'b'], 'source_hashes': {}, 'asset_directory_files': {},
                              'asset_path': 'x', 'python': 'x', 'torch': 'x', 'cuda': 'x', 'gpu': 'x', 'step_dt': 1})

            def save():
                for name, meta in zip(RUNS, metas):
                    (root / name / 'metadata.json').write_text(json.dumps(meta), encoding='utf-8')

            def reject(message):
                save()
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        compare(root)
                except (ValueError, OSError) as exc:
                    assert message in str(exc), str(exc)
                else:
                    raise AssertionError(f'accepted: {message}')

            def missing_snapshot():
                snapshot.unlink()
                try:
                    reject('snapshot')
                finally:
                    snapshot.write_bytes(b'capture snapshot')

            def changed_snapshot():
                snapshot.write_bytes(b'changed')
                try:
                    reject('snapshot')
                finally:
                    snapshot.write_bytes(b'capture snapshot')

            def mismatched_arm():
                metas[3]['script_sha256'] = 'wrong'
                try:
                    reject('snapshot')
                finally:
                    metas[3]['script_sha256'] = sha(snapshot)

            def unchanged_config():
                for meta in metas[2:]:
                    meta['config']['scene']['terrain']['terrain_generator']['sub_terrains']['rough_b']['noise_step'] = 1
                try:
                    reject('intervention')
                finally:
                    for meta in metas[2:]:
                        meta['config']['scene']['terrain']['terrain_generator']['sub_terrains']['rough_b']['noise_step'] = 2

            def unbound_params():
                for meta in metas[2:]:
                    meta['terrain']['cells'][0]['params'] = metas[0]['terrain']['cells'][0]['params']
                try:
                    reject('params')
                finally:
                    for meta in metas[2:]:
                        meta['terrain']['cells'][0]['params'] = param_hash(meta['config']['scene']['terrain']['terrain_generator'])

            def initial_output():
                save()
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    compare(root)
                text = out.getvalue()
                assert "(48, 6, 'rough_b', ['pos'])" in text, text

            def run_snapshot():
                output = Path(folder) / 'new_run'
                def launch(command, **kwargs):
                    assert (output / 'capture_script.py').read_bytes() == Path(__file__).read_bytes()
                    return type('Process', (), {'returncode': 0})()
                with patch('subprocess.run', side_effect=launch), patch(__name__ + '.compare'):
                    run(output, 1)

            failures = []
            for test in (missing_snapshot, changed_snapshot, mismatched_arm, unchanged_config, unbound_params,
                         initial_output, run_snapshot):
                try:
                    test()
                except (AssertionError, ValueError, OSError, KeyError) as exc:
                    print(f'selftest regression {test.__name__}: FAIL {exc}', flush=True)
                    failures.append(test.__name__)
                else:
                    print(f'selftest regression {test.__name__}: PASS', flush=True)
            assert not failures, failures

        def metadata_and_repeatability():
            import copy
            root = Path(folder) / 'batch'
            root.mkdir()
            snapshot = root / 'capture_script.py'
            snapshot.write_bytes(b'capture snapshot')
            generator = {'size': 1, 'horizontal_scale': 1, 'vertical_scale': 1, 'slope_threshold': None,
                         'sub_terrains': {'rough_b': {'noise_range': [0, 0], 'noise_step': 1,
                                                      'downsampled_scale': None, 'size': 1}}}
            config = {'scene': {'terrain': {'terrain_generator': generator}}}
            def param_hash(gen):
                params = dict(gen['sub_terrains']['rough_b'], **{k: gen[k] for k in (
                    'size', 'horizontal_scale', 'vertical_scale', 'slope_threshold')})
                return 'sha256:' + sha256_bytes(json.dumps(params, sort_keys=True, separators=(',', ':'),
                                                            ensure_ascii=False, default=str).encode())
            terrain = {'cfg_id': 0, 'geometry_digest': 'a', 'mode': 'grid', 'cells': [
                {'row': 0, 'col': 6, 'sub_terrain': 'rough_b', 'difficulty': 1,
                 'params': param_hash(generator), 'geometry': 'a', 'relief': 0}]}
            base = {'status': 'complete', 'steps': 3, 'script_sha256': sha(snapshot), 'config': config,
                    'terrain': terrain, 'joint_names': ['a', 'b'], 'source_hashes': {},
                    'asset_directory_files': {}, 'asset_path': 'x', 'python': 'x', 'torch': 'x',
                    'cuda': 'x', 'gpu': 'x', 'step_dt': 1}
            metas = []
            for i, name in enumerate(RUNS):
                d = root / name
                d.mkdir()
                np.savez(d / 'raw.npz', **fixture())
                m = copy.deepcopy(base)
                m.update(name=name, raw_sha256=sha(d / 'raw.npz'))
                if i >= 2:
                    m['config']['scene']['terrain']['terrain_generator']['sub_terrains']['rough_b']['noise_step'] = 2
                    m['terrain']['geometry_digest'] = 'b'
                    gen = m['config']['scene']['terrain']['terrain_generator']
                    m['terrain']['cells'][0].update(params=param_hash(gen), geometry='b', relief=1)
                metas.append(m)

            def save():
                for name, meta in zip(RUNS, metas):
                    (root / name / 'metadata.json').write_text(json.dumps(meta), encoding='utf-8')

            def rejected_compare(message):
                save()
                try:
                    compare(root)
                except ValueError as exc:
                    assert message in str(exc), str(exc)
                else:
                    raise AssertionError(f'accepted: {message}')

            save()
            compare(root)
            for i in (2, 3):
                metas[i]['joint_names'].reverse()
            rejected_compare('joint_names')
            for i in (2, 3):
                metas[i]['joint_names'].reverse()
                metas[i]['config']['scene']['terrain']['terrain_generator']['sub_terrains']['rough_b']['size'] = 2
            rejected_compare('config.scene.terrain.terrain_generator.sub_terrains.rough_b.size')
            for i in (2, 3):
                metas[i]['config']['scene']['terrain']['terrain_generator']['sub_terrains']['rough_b']['size'] = 1
                metas[i]['terrain']['mode'] = 'other'
            rejected_compare('terrain.mode')
            for i in (2, 3):
                metas[i]['terrain']['mode'] = 'grid'
                metas[i]['terrain']['cells'][0]['difficulty'] = 2
            rejected_compare('terrain.cells')
            for i in (2, 3):
                metas[i]['terrain']['cells'][0]['difficulty'] = 1
            for meta in metas:
                meta['joint_names'].append('c')
            rejected_compare('joint width')
            for meta in metas:
                meta['joint_names'].pop()
            p = fixture()
            p['pos'][1, 9, 0] = 1
            np.savez(root / 'ctrl2' / 'raw.npz', **p)
            metas[1]['raw_sha256'] = sha(root / 'ctrl2' / 'raw.npz')
            rejected_compare('same-arm')
            p = fixture()
            reset(p)
            np.savez(root / 'ctrl2' / 'raw.npz', **p)
            metas[1]['raw_sha256'] = sha(root / 'ctrl2' / 'raw.npz')
            rejected_compare('same-arm')
            p = fixture()
            reset(p)
            np.savez(root / 'ctrl1' / 'raw.npz', **p)
            p['terminated'][1, 9] = False
            p['truncated'][1, 9] = True
            np.savez(root / 'ctrl2' / 'raw.npz', **p)
            for name, meta in zip(RUNS[:2], metas[:2]):
                meta['raw_sha256'] = sha(root / name / 'raw.npz')
            rejected_compare('same-arm')
            for name, meta in zip(RUNS[:2], metas[:2]):
                np.savez(root / name / 'raw.npz', **fixture())
                meta['raw_sha256'] = sha(root / name / 'raw.npz')
            save()
            for name in RUNS:
                d = root / name / 'capture'
                d.mkdir()
                for file in ('raw.npz', 'metadata.json'):
                    (root / name / file).replace(d / file)
            compare(root)

        def capture_protection():
            import types
            output = Path(folder) / 'existing'
            output.mkdir()
            (output / 'raw.npz').write_bytes(b'ORIGINAL RAW')
            (output / 'metadata.json').write_bytes(b'ORIGINAL METADATA')
            app_module = types.ModuleType('isaaclab.app')
            def forbidden(*args):
                raise AssertionError('AppLauncher reached before output reservation')
            app_module.AppLauncher = forbidden
            previous = sys.modules.get('isaaclab.app')
            sys.modules['isaaclab.app'] = app_module
            try:
                try:
                    capture(types.SimpleNamespace(output=str(output), name='ctrl1', steps=1))
                except FileExistsError:
                    pass
                else:
                    raise AssertionError('existing output accepted')
                assert (output / 'raw.npz').read_bytes() == b'ORIGINAL RAW'
                assert (output / 'metadata.json').read_bytes() == b'ORIGINAL METADATA'
            finally:
                if previous is None:
                    del sys.modules['isaaclab.app']
                else:
                    sys.modules['isaaclab.app'] = previous

        failures = []
        for test in (pre_reset, post_reset, asymmetric, shapes, events, finite_and_widths,
                     observable, metadata_and_repeatability, capture_protection, regression_gaps):
            try:
                test()
            except (AssertionError, ValueError, KeyError) as exc:
                print(f'selftest {test.__name__}: FAIL {exc}', flush=True)
                failures.append(test.__name__)
            else:
                print(f'selftest {test.__name__}: PASS', flush=True)
        if failures:
            raise AssertionError(f'selftest failures: {failures}')


def run(output, steps):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / 'capture_script.py'
    with snapshot.open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    print(f'run directory: {output}', flush=True)
    for name in RUNS:
        directory = output / name
        directory.mkdir()
        command = [sys.executable, '-B', str(Path(__file__).resolve()), 'capture', '--name', name,
                   '--output', str(directory / 'capture'), '--steps', str(steps), '--headless', '--device', 'cuda:0']
        if sha(Path(__file__)) != sha(snapshot):
            raise RuntimeError(f'capture script changed before {name}')
        with (directory / 'command.json').open('x', encoding='utf-8') as stream:
            json.dump({'cwd': str(REPO), 'argv': command}, stream, indent=2)
        print(f'launch {name}', flush=True)
        with (directory / 'console.log').open('xb') as log:
            process = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
        print(f'{name}: exit={process.returncode} log={directory / "console.log"}', flush=True)
        if process.returncode:
            raise RuntimeError(f'{name} failed; remaining arms not launched')
    compare(output, write_report=True)


def capture(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(REPO))
    from isaaclab.app import AppLauncher
    app = AppLauncher(args).app
    env = None
    records = {f: [] for f in FIELDS}
    pre = {f: [] for f in FIELDS}
    flags = {f: [] for f in ('terminated', 'truncated', 'reset', 'reset_pre_valid')}
    meta = {'name': args.name, 'status': 'failed', 'steps': args.steps,
            'script_path': str(Path(__file__).resolve()), 'script_sha256': sha(Path(__file__)),
            'python': sys.executable, 'argv': sys.argv, 'cwd': os.getcwd(),
            'unmeasured': ['PhysX cooked meshes, BVH, contact manifolds, solver caches and ordering',
                           'policy/observation closed loop and quantitative metric amplification']}
    types = None
    try:
        import gymnasium as gym
        import torch
        import isaaclab_tasks  # noqa: F401
        import rl_exp.tasks  # noqa: F401
        from isaaclab.utils.string import string_to_callable
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from ablation_harness import suites
        from ablation_harness.components.dr_controller import apply_eval_mode
        from rl_exp.tasks.terrain_geometry import seed_rngs
        from rl_exp.tools.verify import terrain_split_probe, cfg_snapshot

        spec = gym.spec('Lizard2-Flat-v3')
        cfg = string_to_callable(spec.kwargs['env_cfg_entry_point'])()
        cfg.scene.terrain = suites.lizard_suite_v2()
        sub = cfg.scene.terrain.terrain_generator.sub_terrains
        sub['rough_a'] = suites._LIZARD_SUITE_V1_GENERATOR.sub_terrains['rough_a'].copy()
        if args.name.startswith('ctrl'):
            sub['rough_b'] = suites._LIZARD_SUITE_V1_GENERATOR.sub_terrains['rough_b'].copy()
        cfg.scene.num_envs = 72
        cfg.episode_length_s = 30.0
        cfg.seed = 123
        cfg.sim.device = args.device
        cfg.curriculum.terrain_levels = None
        apply_eval_mode(cfg, 'nominal')
        meta['config'] = cfg_snapshot.snapshot(cfg)
        meta['asset_path'] = str(Path(str(cfg.scene.robot.spawn.usd_path)).resolve())
        asset = Path(meta['asset_path'])
        meta['asset_directory_files'] = {str(p.resolve()): sha(p) for p in sorted(asset.parent.rglob('*')) if p.is_file()}
        meta['torch'] = torch.__version__
        meta['cuda'] = torch.version.cuda
        meta['gpu'] = torch.cuda.get_device_name(0)
        isaac = isaac_root()
        meta['isaac_root'] = str(isaac)
        meta['source_hashes'] = {str(p.resolve()): sha(p) for root in (
            REPO / 'rl_exp/tasks', REPO / 'ablation_harness', REPO / 'rl_exp/tools/verify',
            isaac / 'source/isaaclab/isaaclab', isaac / 'source/isaaclab_rl/isaaclab_rl',
            isaac / 'source/isaaclab_tasks/isaaclab_tasks')
            for p in sorted(root.rglob('*.py')) if p.is_file()}
        for label, command in (('repo_git', ['git', '-C', str(REPO), 'status', '--short', '--branch']),
                               ('repo_head', ['git', '-C', str(REPO), 'rev-parse', 'HEAD']),
                               ('isaac_git', ['git', '-C', str(isaac), 'status', '--short', '--branch']),
                               ('isaac_head', ['git', '-C', str(isaac), 'rev-parse', 'HEAD']),
                               ('gpu_driver', ['nvidia-smi'])):
            proc = subprocess.run(command, capture_output=True, text=True, errors='replace')
            meta[label] = {'exit': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}
        seed_rngs(suites.SUITE_SEED)
        terrain_split_probe.install()
        env = gym.make('Lizard2-Flat-v3', cfg=cfg)
        mbenv = env.unwrapped
        meta['terrain'] = terrain_split_probe.record_for(mbenv.scene.terrain)
        wrapper = RslRlVecEnvWrapper(env, clip_actions=None)
        robot = mbenv.scene['robot']
        types = mbenv.scene.terrain.terrain_types.detach().cpu().numpy().copy()
        meta['step_dt'] = mbenv.step_dt
        meta['action_shape'] = [mbenv.num_envs, mbenv.action_manager.total_action_dim]
        meta['joint_names'] = list(robot.joint_names)
        print(f'terrain={meta["terrain"]["geometry_digest"]} step_dt={mbenv.step_dt}', flush=True)

        def values():
            data = robot.data
            return {key: getattr(data, attr).torch.detach().cpu().numpy().copy() for key, attr in (
                ('pos', 'root_pos_w'), ('quat', 'root_quat_w'), ('lin', 'root_lin_vel_w'),
                ('ang', 'root_ang_vel_w'), ('qpos', 'joint_pos'), ('qvel', 'joint_vel'))}

        initial = values()
        for f in FIELDS:
            records[f].append(initial[f])
            pre[f].append(np.zeros_like(initial[f]))
        for f in flags:
            flags[f].append(np.zeros(72, dtype=bool))
        reset_original = mbenv._reset_idx
        current = {}

        def watch_reset(ids):
            ids_cpu = ids.detach().cpu().numpy().astype(int)
            if current['reset'][ids_cpu].any():
                raise RuntimeError('multiple resets for env in one step')
            sample = values()
            for f in FIELDS:
                current['pre'][f][ids_cpu] = sample[f][ids_cpu]
            current['reset'][ids_cpu] = True
            return reset_original(ids)

        mbenv._reset_idx = watch_reset
        actions = torch.zeros(*meta['action_shape'], device=mbenv.device)
        for step in range(1, args.steps + 1):
            current = {'reset': np.zeros(72, dtype=bool),
                       'pre': {f: np.zeros_like(initial[f]) for f in FIELDS}}
            wrapper.step(actions)
            sample = values()
            for f in FIELDS:
                records[f].append(sample[f])
                pre[f].append(current['pre'][f])
            flags['terminated'].append(mbenv.reset_terminated.detach().cpu().numpy().astype(bool).copy())
            flags['truncated'].append(mbenv.reset_time_outs.detach().cpu().numpy().astype(bool).copy())
            flags['reset'].append(current['reset'].copy())
            flags['reset_pre_valid'].append(current['reset'].copy())
            if step in (1, 10, args.steps):
                print(f'step={step} reset_ids={np.flatnonzero(current["reset"]).tolist()}', flush=True)
        meta['status'] = 'complete'
    except BaseException:
        traceback.print_exc()
        raise
    finally:
        if types is not None and records['pos']:
            raw = {f: np.stack(records[f]) for f in FIELDS}
            raw.update({f'reset_pre_{f}': np.stack(pre[f]) for f in FIELDS})
            raw.update({f: np.stack(flags[f]) for f in flags})
            raw['types'] = types
            with (output / 'raw.npz').open('xb') as stream:
                np.savez_compressed(stream, **raw)
            meta['raw_sha256'] = sha(output / 'raw.npz')
        with (output / 'metadata.json').open('x', encoding='utf-8') as stream:
            json.dump(meta, stream, indent=2, allow_nan=False, default=str)
        if env is not None:
            env.close()
        app.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    child = sub.add_parser('run')
    child.add_argument('--output', required=True)
    child.add_argument('--steps', type=int, default=100)
    child = sub.add_parser('capture')
    if len(sys.argv) > 1 and sys.argv[1] == 'capture':
        sys.path.insert(0, str(REPO))
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(child)
    child.add_argument('--output', required=True)
    child.add_argument('--steps', type=int, default=100)
    child.add_argument('--name', choices=RUNS, required=True)
    comp = sub.add_parser('compare')
    comp.add_argument('directory', type=Path)
    sub.add_parser('selftest')
    args = parser.parse_args()
    if args.command in ('run', 'capture') and args.steps < 1:
        parser.error('--steps must be positive')
    if args.command == 'selftest':
        selftest()
    elif args.command == 'compare':
        compare(args.directory.resolve())
    elif args.command == 'run':
        run(Path(args.output), args.steps)
    else:
        capture(args)


if __name__ == '__main__':
    main()
