# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Repeatable zero-action column-coupling diagnostic, not an eval protocol.

Run from the repository root with the IsaacLab Python:
    python rl_exp/tools/diagnose/column_coupling_probe.py run --output <new-directory> --steps 100
    python rl_exp/tools/diagnose/column_coupling_probe.py compare <run-directory>
    python rl_exp/tools/diagnose/column_coupling_probe.py selftest

With --intervention single_noise_min, the only modified config scalar is the
rough_b noise_range lower bound. The default preserves the earlier bundled probe.

Every subprocess gets its own log and raw .npz. Auto-reset remains enabled, but
its actual call is intercepted and pre-reset state and per-env IDs are stored.
Compare paired pre-reset captures before post-step samples at each step. A
pre-reset divergence is reset-clean if neither arm reset that env on prior steps;
a post-step divergence also counts resets in the current step. When only one arm
resets, the other arm's corresponding pre-reset state was not captured. The
first_* fields identify the first observable difference, not necessarily the
first difference; first_is_provable is false after an unpaired pre-reset sample.
Other environments' resets and unobserved PhysX state remain possible channels.
By default compare requires exit_status.json for every arm, written by run() only
on a confirmed successful exit. To inspect older batches without that proof, use
compare --allow_unconfirmed (or allow_unconfirmed=True in Python). Missing exits
are reported as unconfirmed; invalid or nonzero confirmations are always rejected.
Unconfirmed comparisons cannot write a report.
Optional --rng_trace hashes complete global RNG states at seeded step 0 and after
steps. CUDA state reads can synchronize or otherwise perturb timing and physics.
Equal snapshots cannot exclude intermediate changes that were restored, private
RNGs, or differences in PhysX. Hashes bind recorded files for consistency, not
authenticity: coordinated archive changes are undetectable. Joint names are
metadata only, not independently verified.
"""
from __future__ import annotations

import argparse
import io
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


def assert_controlled_initial(reference, actual):
    for field in FIELDS:
        a, b = reference[field], actual[field]
        if a.ndim != 2 or a.shape[0] != 72 or a.shape[1] == 0 or not np.isfinite(a).all():
            raise ValueError(f'invalid reference {field}')
        if a.shape != b.shape or a.dtype != b.dtype or a.tobytes() != b.tobytes():
            raise ValueError(f'controlled initial mismatch: {field}')


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


def rng_digests(state):
    """Hash each complete global RNG state without consuming random numbers."""
    values = [state['python'], state['numpy'], state['torch_cpu'], *state['torch_cuda']]
    return np.array([list(bytes.fromhex(sha256_bytes(json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8'))))
                     for value in values], dtype=np.uint8)


def compare_rng_traces(arrays, metas):
    declarations = [m.get('rng_trace') for m in metas]
    present = ['rng_trace' in a.files for a in arrays]
    if not any(declarations) and not any(present):
        return None
    declaration = declarations[0]
    if (not isinstance(declaration, dict) or set(declaration) != {'version', 'cuda_devices'}
            or type(declaration['version']) is not int or declaration['version'] != 1
            or type(declaration['cuda_devices']) is not int or declaration['cuda_devices'] < 1
            or any(d != declaration for d in declarations) or not all(present)):
        raise ValueError('rng trace declaration or presence mismatch')
    count = declaration['cuda_devices']
    expected = (metas[0]['steps'] + 1, 3 + count, 32)
    traces = [a['rng_trace'] for a in arrays]
    if any(t.shape != expected or t.dtype != np.uint8 for t in traces):
        raise ValueError('rng trace shape or dtype mismatch')
    if any('control' not in m or not np.array_equal(t[0], rng_digests(m['control']['rng_after_seed']))
           for t, m in zip(traces, metas)):
        raise ValueError('rng trace step 0 does not match seeded state')
    result = {}
    for i, name in enumerate(('python', 'numpy', 'torch_cpu', *(f'torch_cuda:{j}' for j in range(count)))):
        column = [t[:, i, :] for t in traces]
        mismatch = np.flatnonzero(np.any(np.stack(column) != column[0][None, :, :], axis=(0, 2))).tolist()
        changes = {}
        for arm, values in zip(RUNS, column):
            steps = np.flatnonzero(np.any(values != values[0], axis=1))
            changes[arm] = int(steps[0]) if len(steps) else None
        result[name] = {'first_four_arm_mismatch': mismatch[0] if mismatch else None,
                        'mismatch_steps': mismatch, 'first_change_by_arm': changes,
                        'step_groups': [{arm: bytes(values[step]).hex() for arm, values in zip(RUNS, column)}
                                        for step in range(expected[0])]}
    return result


def compare(root, write_report=False, *, allow_unconfirmed=False):
    if type(allow_unconfirmed) is not bool:
        raise TypeError('allow_unconfirmed must be a boolean')
    directories = [(root / name / 'capture') if (root / name / 'capture').is_dir() else (root / name) for name in RUNS]
    metadata_bytes = [(directory / 'metadata.json').read_bytes() for directory in directories]
    metas = [json.loads(data) for data in metadata_bytes]
    raw_bytes = []
    unconfirmed = []
    for name, directory, meta, data in zip(RUNS, directories, metas, metadata_bytes):
        if meta['status'] != 'complete' or meta['name'] != name:
            raise ValueError(f'incomplete or misidentified run: {name}')
        confirmation_path = directory / 'exit_status.json'
        try:
            confirmation = json.loads(confirmation_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            if os.path.lexists(confirmation_path):
                raise ValueError(f'invalid exit confirmation: {name}') from None
            if not allow_unconfirmed:
                raise ValueError(f'missing exit confirmation: {name}') from None
            unconfirmed.append(name)
        else:
            if (not isinstance(confirmation, dict) or type(confirmation.get('returncode')) is not int
                    or confirmation['returncode'] != 0
                    or confirmation.get('metadata_sha256') != sha256_bytes(data)):
                raise ValueError(f'invalid exit confirmation: {name}')
        raw = (directory / 'raw.npz').read_bytes()
        if sha256_bytes(raw) != meta['raw_sha256']:
            raise ValueError(f'raw hash mismatch: {name}')
        raw_bytes.append(raw)
    if len({m['steps'] for m in metas}) != 1:
        raise ValueError('step count mismatch')
    snapshot = root / 'capture_script.py'
    if not snapshot.is_file():
        raise ValueError(f'capture script snapshot missing: {snapshot}')
    snapshot_hash = sha(snapshot)
    if any(m['script_sha256'] != snapshot_hash for m in metas):
        raise ValueError('capture script snapshot hash mismatch')
    if unconfirmed:
        if write_report:
            raise ValueError('cannot write a report for unconfirmed capture exits')
        print(f'WARNING: exit status unconfirmed for {", ".join(unconfirmed)}; '
              'comparison does not certify successful capture', flush=True)
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
    interventions = {m.get('intervention', 'legacy') for m in metas}
    if len(interventions) != 1 or next(iter(interventions)) not in ('legacy', 'single_noise_min'):
        raise ValueError('capture intervention mismatch')
    intervention = next(iter(interventions))
    prefix = 'config.scene.terrain.terrain_generator.sub_terrains.rough_b.'
    allowed = ({prefix + 'noise_range.__tuple__[0]'} if intervention == 'single_noise_min' else
               {prefix + k for k in ('noise_range', 'noise_step', 'downsampled_scale')})
    check_equal(metas[0]['config'], metas[2]['config'], 'config', allowed)
    generators = [m['config']['scene']['terrain']['terrain_generator'] for m in metas]
    rough = [g['sub_terrains']['rough_b'] for g in generators]
    if intervention == 'single_noise_min':
        ranges = [r['noise_range']['__tuple__'] for r in rough]
        if len(ranges[0]) != 2 or ranges[0][0] == ranges[2][0]:
            raise ValueError('terrain intervention config unchanged')
    elif all(rough[0][k] == rough[2][k] for k in ('noise_range', 'noise_step', 'downsampled_scale')):
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
    if intervention == 'single_noise_min' and (not cells_a[(0, 6)].get('geometry') or
            not cells_b[(0, 6)].get('geometry') or
            cells_a[(0, 6)]['geometry'] == cells_b[(0, 6)]['geometry']):
        raise ValueError('terrain intervention geometry unchanged or missing')
    for meta in metas[1:]:
        check_equal(metas[0]['joint_names'], meta['joint_names'], 'joint_names')
    for key in ('source_hashes', 'asset_directory_files', 'asset_path', 'python', 'torch', 'cuda', 'gpu', 'step_dt'):
        if any(m[key] != metas[0][key] for m in metas[1:]):
            raise ValueError(f'capture identity mismatch: {key}')
    arrays = [np.load(io.BytesIO(data), allow_pickle=False) for data in raw_bytes]
    try:
        for data in arrays:
            validate(data)
        controls = [m.get('control') for m in metas]
        if any(controls) or any('control_input_pos' in data.files for data in arrays):
            if any(not c or c.get('mode') != 'controlled_initial_v1' for c in controls):
                raise ValueError('controlled capture mode mismatch')
            if intervention != 'single_noise_min':
                raise ValueError('controlled capture intervention mismatch')
            for c in controls[1:]:
                for key in ('mode', 'runtime_seed', 'rng_after_seed', 'state_frame', 'readback', 'limitation'):
                    check_equal(controls[0][key], c[key], f'control.{key}')
            reference = {f: arrays[0][f][0] for f in FIELDS}
            for i, (data, meta) in enumerate(zip(arrays, metas)):
                if i and (meta.get('reference', {}).get('sha256') != metas[0]['raw_sha256']):
                    raise ValueError('controlled reference hash mismatch')
                for phase in ('input', 'readback'):
                    assert_controlled_initial(reference, {f: data['control_' + phase + '_' + f] for f in FIELDS})
                assert_controlled_initial(reference, {f: data[f][0] for f in FIELDS})
                for f in FIELDS:
                    if data['control_before_' + f].shape != reference[f].shape:
                        raise ValueError(f'controlled before shape mismatch: {f}')
            print('controlled: all 72 initial fields match reference and backend readback; '
                  'PhysX internal state remains unmeasured', flush=True)
        rng_report = compare_rng_traces(arrays, metas)
        if rng_report is not None:
            for name, entry in rng_report.items():
                print(f'rng {name}: first_four_arm_mismatch={entry["first_four_arm_mismatch"]} '
                      f'mismatch_steps={entry["mismatch_steps"]} first_change_by_arm={entry["first_change_by_arm"]}', flush=True)
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
            if rng_report is not None:
                output = root / 'rng_comparison.json'
                with output.open('x', encoding='utf-8') as stream:
                    json.dump(rng_report, stream, indent=2, allow_nan=False)
                    stream.write('\n')
                print(f'rng comparison: {output}')
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
                if isinstance(params['noise_range'], dict):
                    params['noise_range'] = params['noise_range']['__tuple__']
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
                    directory = root / name
                    (directory / 'metadata.json').write_text(json.dumps(meta), encoding='utf-8')
                    (directory / 'exit_status.json').write_text(json.dumps({
                        'returncode': 0, 'metadata_sha256': sha(directory / 'metadata.json')}), encoding='utf-8')

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

            def single_noise_min():
                original = copy.deepcopy(metas)
                try:
                    for i, meta in enumerate(metas):
                        meta['intervention'] = 'single_noise_min'
                        gen = meta['config']['scene']['terrain']['terrain_generator']
                        rough = gen['sub_terrains']['rough_b']
                        rough['noise_step'] = 1
                        rough['noise_range'] = {'__tuple__': [int(i >= 2), 2]}
                        meta['terrain']['cells'][0]['params'] = param_hash(gen)
                    save()
                    with contextlib.redirect_stdout(io.StringIO()):
                        compare(root)
                    for meta in metas[2:]:
                        gen = meta['config']['scene']['terrain']['terrain_generator']
                        gen['sub_terrains']['rough_b']['noise_step'] = 2
                        meta['terrain']['cells'][0]['params'] = param_hash(gen)
                    reject('rough_b.noise_step')
                    for meta in metas[2:]:
                        gen = meta['config']['scene']['terrain']['terrain_generator']
                        gen['sub_terrains']['rough_b']['noise_step'] = 1
                        meta['terrain']['cells'][0]['params'] = param_hash(gen)
                        meta['terrain']['cells'][0]['geometry'] = metas[0]['terrain']['cells'][0]['geometry']
                    reject('geometry unchanged')
                finally:
                    metas[:] = original

            def controlled_compare():
                original = copy.deepcopy(metas)
                originals = [(root / name / 'raw.npz').read_bytes() for name in RUNS]
                try:
                    for i, meta in enumerate(metas):
                        meta['intervention'] = 'single_noise_min'
                        gen = meta['config']['scene']['terrain']['terrain_generator']
                        gen['sub_terrains']['rough_b'].update(noise_step=1, noise_range={'__tuple__': [int(i >= 2), 2]})
                        meta['terrain']['cells'][0]['params'] = param_hash(gen)
                        meta['control'] = {'mode': 'controlled_initial_v1', 'runtime_seed': 123,
                                           'rng_after_seed': 'same', 'state_frame': 'world',
                                           'readback': 'backend', 'limitation': 'internal'}
                        payload = fixture()
                        for f in FIELDS:
                            for phase in ('before', 'input', 'readback'):
                                payload['control_' + phase + '_' + f] = payload[f][0].copy()
                        if i == 1:
                            payload['control_readback_pos'][71, 0] = 1
                        np.savez(root / RUNS[i] / 'raw.npz', **payload)
                        meta['raw_sha256'] = sha(root / RUNS[i] / 'raw.npz')
                    for meta in metas[1:]:
                        meta['reference'] = {'sha256': metas[0]['raw_sha256']}
                    reject('controlled initial mismatch: pos')
                finally:
                    metas[:] = original
                    for name, contents in zip(RUNS, originals):
                        (root / name / 'raw.npz').write_bytes(contents)

            def rng_trace_regression():
                original = copy.deepcopy(metas)
                originals = [(root / name / 'raw.npz').read_bytes() for name in RUNS]
                try:
                    seed = {'python': [1], 'numpy': [2], 'torch_cpu': '03', 'torch_cuda': ['04']}
                    for i, meta in enumerate(metas):
                        meta['rng_trace'] = {'version': 1, 'cuda_devices': 1}
                        meta['intervention'] = 'single_noise_min'
                        gen = meta['config']['scene']['terrain']['terrain_generator']
                        gen['sub_terrains']['rough_b'].update(noise_step=1, noise_range={'__tuple__': [int(i >= 2), 2]})
                        meta['terrain']['cells'][0]['params'] = param_hash(gen)
                        meta['control'] = {'mode': 'controlled_initial_v1', 'runtime_seed': 123,
                                           'rng_after_seed': seed, 'state_frame': 'world',
                                           'readback': 'backend', 'limitation': 'internal'}
                        payload = fixture()
                        for f in FIELDS:
                            for phase in ('before', 'input', 'readback'):
                                payload['control_' + phase + '_' + f] = payload[f][0].copy()
                        payload['rng_trace'] = np.repeat(rng_digests(seed)[None, :, :], 4, axis=0)
                        if i == 2:
                            payload['rng_trace'][2, 1, 0] ^= 1
                        np.savez(root / RUNS[i] / 'raw.npz', **payload)
                        meta['raw_sha256'] = sha(root / RUNS[i] / 'raw.npz')
                    for meta in metas[1:]:
                        meta['reference'] = {'sha256': metas[0]['raw_sha256']}
                    save()
                    with contextlib.redirect_stdout(io.StringIO()):
                        compare(root, write_report=True)
                    report = json.loads((root / 'rng_comparison.json').read_text(encoding='utf-8'))
                    assert report['numpy']['first_four_arm_mismatch'] == 2
                    assert report['numpy']['mismatch_steps'] == [2]
                    assert report['numpy']['first_change_by_arm']['rougha1'] == 2
                    (root / 'comparison.json').unlink()
                    (root / 'rng_comparison.json').unlink()
                    payload['rng_trace'] = payload['rng_trace'][:-1]
                    np.savez(root / RUNS[3] / 'raw.npz', **payload)
                    metas[3]['raw_sha256'] = sha(root / RUNS[3] / 'raw.npz')
                    reject('rng trace')
                    del payload['rng_trace']
                    np.savez(root / RUNS[3] / 'raw.npz', **payload)
                    metas[3]['raw_sha256'] = sha(root / RUNS[3] / 'raw.npz')
                    reject('rng trace')
                finally:
                    metas[:] = original
                    for name, contents in zip(RUNS, originals):
                        (root / name / 'raw.npz').write_bytes(contents)

            def run_snapshot():
                output = Path(folder) / 'new_run'
                def launch(command, **kwargs):
                    assert (output / 'capture_script.py').read_bytes() == Path(__file__).read_bytes()
                    capture_dir = Path(command[command.index('--output') + 1])
                    capture_dir.mkdir()
                    (capture_dir / 'raw.npz').write_bytes(b'fixture raw')
                    (capture_dir / 'metadata.json').write_text(json.dumps({
                        'name': command[command.index('--name') + 1], 'status': 'complete',
                        'raw_sha256': sha(capture_dir / 'raw.npz'),
                        'script_sha256': sha(output / 'capture_script.py'),
                        'source_hashes': {}, 'asset_directory_files': {}}), encoding='utf-8')
                    return type('Process', (), {'returncode': 0})()
                with patch('subprocess.run', side_effect=launch), patch(__name__ + '.compare'):
                    run(output, 1)
                for name in RUNS:
                    capture_dir = output / name / 'capture'
                    status = json.loads((capture_dir / 'exit_status.json').read_text(encoding='utf-8'))
                    assert status == {'returncode': 0, 'metadata_sha256': sha(capture_dir / 'metadata.json')}

            def run_failed_capture():
                output = Path(folder) / 'failed_run'
                def launch(command, **kwargs):
                    capture_dir = Path(command[command.index('--output') + 1])
                    capture_dir.mkdir()
                    (capture_dir / 'metadata.json').write_text(json.dumps({'status': 'complete'}), encoding='utf-8')
                    return type('Process', (), {'returncode': 1})()
                with patch('subprocess.run', side_effect=launch), patch(__name__ + '.compare'):
                    try:
                        run(output, 1)
                    except RuntimeError as exc:
                        assert 'ctrl1 failed' in str(exc)
                    else:
                        raise AssertionError('failed capture accepted')
                assert not (output / 'ctrl1' / 'capture' / 'exit_status.json').exists()
                assert not (output / 'ctrl2').exists()

            failures = []
            for test in (missing_snapshot, changed_snapshot, mismatched_arm, unchanged_config, unbound_params,
                         initial_output, single_noise_min, controlled_compare, rng_trace_regression, run_snapshot, run_failed_capture):
                try:
                    test()
                except (AssertionError, ValueError, OSError, KeyError) as exc:
                    print(f'selftest regression {test.__name__}: FAIL {exc}', flush=True)
                    failures.append(test.__name__)
                else:
                    print(f'selftest regression {test.__name__}: PASS', flush=True)
            assert not failures, failures

        def metadata_and_repeatability():
            import contextlib
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
                    directory = root / name
                    (directory / 'metadata.json').write_text(json.dumps(meta), encoding='utf-8')
                    (directory / 'exit_status.json').write_text(json.dumps({
                        'returncode': 0, 'metadata_sha256': sha(directory / 'metadata.json')}), encoding='utf-8')

            def rejected_compare(message):
                save()
                for allow in (False, True):
                    try:
                        compare(root, allow_unconfirmed=allow)
                    except ValueError as exc:
                        assert message in str(exc), str(exc)
                    else:
                        raise AssertionError(f'accepted: {message}')

            save()
            for name in RUNS:
                (root / name / 'exit_status.json').unlink()
            try:
                compare(root)
            except ValueError as exc:
                assert 'exit confirmation' in str(exc), str(exc)
            else:
                raise AssertionError('default compare accepted unconfirmed flat capture')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                compare(root, allow_unconfirmed=True)
            assert all(name in output.getvalue() for name in RUNS), output.getvalue()
            assert 'unconfirmed' in output.getvalue(), output.getvalue()
            try:
                compare(root, allow_unconfirmed='False')
            except (TypeError, ValueError):
                pass
            else:
                raise AssertionError('non-boolean allow_unconfirmed accepted')
            try:
                compare(root, write_report=True, allow_unconfirmed=True)
            except ValueError as exc:
                assert 'unconfirmed' in str(exc), str(exc)
            else:
                raise AssertionError('unconfirmed report accepted')
            save()
            (root / RUNS[1] / 'exit_status.json').unlink()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                compare(root, allow_unconfirmed=True)
            warning = next(line for line in output.getvalue().splitlines() if 'unconfirmed' in line)
            assert RUNS[1] in warning and all(name not in warning for name in (RUNS[0], RUNS[2], RUNS[3])), warning
            save()
            compare(root)
            from unittest.mock import patch
            with patch(__name__ + '.sha', wraps=sha) as hashing:
                compare(root)
                assert all(Path(call.args[0]).name != 'raw.npz' for call in hashing.call_args_list), hashing.call_args_list
            for name in RUNS:
                capture_dir = root / name / 'capture'
                capture_dir.mkdir()
                (capture_dir / 'metadata.json').write_text((root / name / 'metadata.json').read_text(encoding='utf-8'),
                                                           encoding='utf-8')
                (capture_dir / 'raw.npz').write_bytes((root / name / 'raw.npz').read_bytes())
            try:
                compare(root)
            except ValueError as exc:
                assert 'exit confirmation' in str(exc), str(exc)
            else:
                raise AssertionError('default compare accepted unconfirmed nested capture')
            for name in RUNS:
                capture_dir = root / name / 'capture'
                (capture_dir / 'exit_status.json').write_text(json.dumps({
                    'returncode': 0, 'metadata_sha256': sha(capture_dir / 'metadata.json')}), encoding='utf-8')
            compare(root)
            status = root / RUNS[0] / 'capture' / 'exit_status.json'
            status.write_text('{"returncode": 1}', encoding='utf-8')
            rejected_compare('exit confirmation')
            status.write_text(json.dumps({'returncode': False,
                'metadata_sha256': sha(root / RUNS[0] / 'capture' / 'metadata.json')}), encoding='utf-8')
            rejected_compare('exit confirmation')
            status.write_text(json.dumps({'returncode': 0, 'metadata_sha256': 'wrong'}), encoding='utf-8')
            rejected_compare('exit confirmation')
            for name in RUNS:
                capture_dir = root / name / 'capture'
                for file in ('exit_status.json', 'metadata.json', 'raw.npz'):
                    (capture_dir / file).unlink()
                capture_dir.rmdir()
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
                for file in ('raw.npz', 'metadata.json', 'exit_status.json'):
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

        def capture_exit_regression():
            import ast
            import subprocess
            script = r'''
import ast, atexit, json, os, pathlib, sys, traceback
import numpy as np
source, output, mode = sys.argv[1:]
atexit.register(lambda: os._exit(0))
tree = ast.parse(pathlib.Path(source).read_text(encoding='utf-8'))
collector = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'capture')
cleanup = next(n for n in collector.body if isinstance(n, ast.Try) and n.finalbody).finalbody
wrapper = ast.parse('def finish():\n try:\n  meta["status"] = "complete"\n finally:\n  pass').body[0]
wrapper.body[0].finalbody = cleanup
class Env:
    def close(self):
        if mode == 'failure': raise RuntimeError('injected env close failure')
class App:
    def close(self):
        pathlib.Path(output, 'app_closed').touch()
        if mode in ('app_failure', 'app_failure_metadata_failure'):
            raise RuntimeError('injected app close failure')
        if mode == 'app_exit_zero': raise SystemExit(0)
        if mode == 'app_exit_nonzero': raise SystemExit(7)
        os._exit(0)
output = pathlib.Path(output)
if mode == 'raw_failure':
    def fail_raw(*args, **kwargs): raise OSError('injected raw write failure')
    np.savez_compressed = fail_raw
if mode == 'metadata_failure':
    def fail_replace(*args, **kwargs): raise OSError('injected metadata replace failure')
    pathlib.Path.replace = fail_replace
if mode == 'app_failure_metadata_failure':
    original_replace = pathlib.Path.replace
    def fail_close_replace(path, target):
        if path.name == 'metadata.close_failure.json': raise OSError('injected close marker failure')
        return original_replace(path, target)
    pathlib.Path.replace = fail_close_replace
namespace = dict(sys=sys, os=os, traceback=traceback, json=json, np=np, output=output,
                 meta={'status': 'failed'}, types=np.array([0]), records={'pos': [np.array([0])]},
                 pre={'pos': [np.array([0])]}, flags={}, control_raw={}, FIELDS=('pos',),
                 sha=lambda path: 'fixture', env=Env(), app=App())
exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])), source, 'exec'), namespace)
namespace['finish']()
'''
            for mode in ('failure', 'success', 'app_failure', 'app_exit_zero', 'app_exit_nonzero',
                         'app_failure_metadata_failure', 'raw_failure', 'metadata_failure'):
                output = Path(folder) / ('exit_' + mode)
                output.mkdir()
                result = subprocess.run([sys.executable, '-B', '-c', script, str(Path(__file__).resolve()),
                                         str(output), mode], capture_output=True, text=True, timeout=30)
                succeeded = mode in ('success', 'app_exit_zero')
                reached_app = mode in ('success', 'app_failure', 'app_exit_zero', 'app_exit_nonzero',
                                       'app_failure_metadata_failure')
                assert (result.returncode == 0) == succeeded, (mode, result.returncode, result.stderr)
                metadata = output / 'metadata.json'
                if mode == 'raw_failure':
                    assert not metadata.exists()
                else:
                    meta = json.loads(metadata.read_text(encoding='utf-8'))
                    assert meta['status'] == ('complete' if succeeded or mode == 'app_failure_metadata_failure'
                                              else 'failed'), meta
                assert (output / 'raw.npz').exists()
                assert (output / 'app_closed').exists() == reached_app
                if not succeeded:
                    assert 'Traceback' in result.stderr
                    assert 'injected' in result.stderr or 'SystemExit: 7' in result.stderr
                if mode == 'app_failure_metadata_failure':
                    assert 'injected app close failure' in result.stderr
                    assert 'injected close marker failure' in result.stderr

        def capture_launcher_regression():
            import subprocess
            script = r'''
import atexit, importlib.util, os, sys, types
app = types.ModuleType('isaaclab.app')
class AppLauncher:
    def __init__(self, args):
        atexit.register(lambda: os._exit(0))
        raise RuntimeError('injected launcher failure')
app.AppLauncher = AppLauncher
sys.modules['isaaclab.app'] = app
spec = importlib.util.spec_from_file_location('column_probe', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.capture(types.SimpleNamespace(output=sys.argv[2], name='ctrl1', steps=1))
'''
            source = Path(__file__).resolve()
            current = source.read_text(encoding='utf-8')
            guarded = ('    try:\n        app = AppLauncher(args).app\n    except BaseException:\n'
                       '        try:\n            traceback.print_exc()\n            sys.stderr.flush()\n'
                       '            sys.stdout.flush()\n        finally:\n            os._exit(1)\n')
            assert current.count(guarded) == 1
            before = Path(folder) / 'before_launcher.py'
            before.write_text(current.replace(guarded, '    app = AppLauncher(args).app\n'), encoding='utf-8')
            for entry, label, expected in ((before, 'before', 0), (source, 'after', 1)):
                result = subprocess.run([sys.executable, '-B', '-c', script, str(entry),
                                         str(Path(folder) / ('launcher_' + label))],
                                        capture_output=True, text=True, timeout=30)
                assert (result.returncode == expected and 'Traceback' in result.stderr
                        and 'injected launcher failure' in result.stderr), result

        def controlled_initial_regression():
            reference = {f: fixture()[f][0].copy() for f in FIELDS}
            assert_controlled_initial(reference, reference)
            for field in FIELDS:
                actual = {f: a.copy() for f, a in reference.items()}
                actual[field][71, 0] = np.nextafter(np.float32(0), np.float32(1))
                try:
                    assert_controlled_initial(reference, actual)
                except ValueError as exc:
                    assert field in str(exc)
                else:
                    raise AssertionError(f'accepted changed {field}')

        failures = []
        for test in (pre_reset, post_reset, asymmetric, shapes, events, finite_and_widths,
                     observable, metadata_and_repeatability, capture_protection, capture_exit_regression,
                     capture_launcher_regression, regression_gaps,
                     controlled_initial_regression):
            try:
                test()
            except (AssertionError, ValueError, KeyError) as exc:
                print(f'selftest {test.__name__}: FAIL {exc}', flush=True)
                failures.append(test.__name__)
            else:
                print(f'selftest {test.__name__}: PASS', flush=True)
        if failures:
            raise AssertionError(f'selftest failures: {failures}')


def run(output, steps, intervention='legacy', controlled_initial=False, rng_trace=False):
    """Run capture arms; only this supervising path records successful exits."""
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
        if intervention != 'legacy':
            command.extend(['--intervention', intervention])
        if controlled_initial:
            command.append('--controlled_initial')
            if name != 'ctrl1':
                command.extend(['--reference', str(output / 'ctrl1' / 'capture' / 'raw.npz')])
        if rng_trace:
            command.append('--rng_trace')
        if sha(Path(__file__)) != sha(snapshot):
            raise RuntimeError(f'capture script changed before {name}')
        with (directory / 'command.json').open('x', encoding='utf-8') as stream:
            json.dump({'cwd': str(REPO), 'argv': command}, stream, indent=2)
        print(f'launch {name}', flush=True)
        with (directory / 'console.log').open('xb') as log:
            process = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
        print(f'{name}: exit={process.returncode} log={directory / "console.log"}', flush=True)
        if sha(Path(__file__)) != sha(snapshot):
            raise RuntimeError(f'capture script changed during {name}; remaining arms not launched')
        if process.returncode:
            raise RuntimeError(f'{name} failed; remaining arms not launched')
        metadata_path = directory / 'capture' / 'metadata.json'
        metadata_bytes = metadata_path.read_bytes()
        metadata = json.loads(metadata_bytes)
        if metadata['status'] != 'complete' or metadata['name'] != name:
            raise RuntimeError(f'{name} has incomplete or misidentified metadata')
        if metadata['script_sha256'] != sha(snapshot):
            raise RuntimeError(f'capture script identity mismatch: {name}')
        if sha(directory / 'capture' / 'raw.npz') != metadata['raw_sha256']:
            raise RuntimeError(f'capture raw identity mismatch: {name}')
        with (directory / 'capture' / 'exit_status.json').open('x', encoding='utf-8') as stream:
            json.dump({'returncode': process.returncode, 'metadata_sha256': sha256_bytes(metadata_bytes)}, stream, indent=2)
        if name != RUNS[0]:
            first = json.loads((output / RUNS[0] / 'capture' / 'metadata.json').read_text(encoding='utf-8'))
            for key in ('source_hashes', 'asset_directory_files'):
                if metadata[key] != first[key]:
                    raise RuntimeError(f'capture identity mismatch: {name} {key}')
    compare(output, write_report=True)


def capture(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(REPO))
    from isaaclab.app import AppLauncher
    try:
        app = AppLauncher(args).app
    except BaseException:
        try:
            traceback.print_exc()
            sys.stderr.flush()
            sys.stdout.flush()
        finally:
            os._exit(1)
    env = None
    records = {f: [] for f in FIELDS}
    pre = {f: [] for f in FIELDS}
    flags = {f: [] for f in ('terminated', 'truncated', 'reset', 'reset_pre_valid')}
    meta = {'name': args.name, 'status': 'failed', 'steps': args.steps,
            'intervention': args.intervention,
            'script_path': str(Path(__file__).resolve()), 'script_sha256': sha(Path(__file__)),
            'python': sys.executable, 'argv': sys.argv, 'cwd': os.getcwd(),
            'unmeasured': ['PhysX cooked meshes, BVH, contact manifolds, solver caches and ordering',
                           'policy/observation closed loop and quantitative metric amplification']}
    types = None
    control_raw = {}
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
        if args.intervention == 'single_noise_min':
            if not args.name.startswith('ctrl'):
                sub['rough_b'].noise_range = (0.10, 0.16)
        elif args.name.startswith('ctrl'):
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
        def source_hashes():
            return {str(p.resolve()): sha(p) for root in (
                REPO / 'rl_exp/tasks', REPO / 'ablation_harness', REPO / 'rl_exp/tools/verify',
                isaac / 'source/isaaclab/isaaclab', isaac / 'source/isaaclab_rl/isaaclab_rl',
                isaac / 'source/isaaclab_tasks/isaaclab_tasks', isaac / 'source/isaaclab_physx/isaaclab_physx')
                for p in sorted(root.rglob('*.py')) if p.is_file()}

        meta['source_hashes'] = source_hashes()
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
            # Pull-on-demand may replace a Warp buffer while its ProxyArray still points at the old one.
            for field in ('_root_link_pose_w_ta', '_root_link_pos_w_ta', '_root_link_quat_w_ta',
                          '_root_com_vel_w_ta', '_root_com_lin_vel_w_ta', '_root_com_ang_vel_w_ta',
                          '_joint_pos_ta', '_joint_vel_ta'):
                setattr(data, field, None)
            return {key: getattr(data, attr).torch.detach().cpu().numpy().copy() for key, attr in (
                ('pos', 'root_pos_w'), ('quat', 'root_quat_w'), ('lin', 'root_lin_vel_w'),
                ('ang', 'root_ang_vel_w'), ('qpos', 'joint_pos'), ('qvel', 'joint_vel'))}

        if args.controlled_initial:
            import random
            import warp as wp

            def backend_values():
                wp.synchronize_device(mbenv.device)
                view = robot.root_view
                pose = wp.to_torch(view.get_root_transforms()).detach().cpu().numpy().copy()
                velocity = wp.to_torch(view.get_root_velocities()).detach().cpu().numpy().copy()
                return dict(pos=pose[:, :3].copy(), quat=pose[:, 3:].copy(),
                            lin=velocity[:, :3].copy(), ang=velocity[:, 3:].copy(),
                            qpos=wp.to_torch(view.get_dof_positions()).detach().cpu().numpy().copy(),
                            qvel=wp.to_torch(view.get_dof_velocities()).detach().cpu().numpy().copy())

            def rng_state():
                numpy_state = np.random.get_state()
                return {'python': random.getstate(),
                        'numpy': [numpy_state[0], numpy_state[1].tolist(), *numpy_state[2:]],
                        'torch_cpu': torch.get_rng_state().numpy().tobytes().hex(),
                        'torch_cuda': [s.cpu().numpy().tobytes().hex() for s in torch.cuda.get_rng_state_all()]}

            from isaaclab.actuators import ImplicitActuator
            from isaaclab.envs.mdp.actions.joint_actions import JointPositionAction

            if not robot.actuators or any(type(a) is not ImplicitActuator for a in robot.actuators.values()):
                raise ValueError('controlled probe requires stateless implicit actuators')
            if getattr(robot, '_has_newton_actuators', False):
                raise ValueError('controlled probe does not support Newton actuators')
            if any(type(mbenv.action_manager.get_term(n)) is not JointPositionAction
                   for n in mbenv.action_manager.active_terms):
                raise ValueError('controlled probe requires joint position actions')
            if mbenv.action_manager.action.any() or mbenv.action_manager.prev_action.any() or mbenv.episode_length_buf.any():
                raise ValueError('wrapper reset action or episode state is not zero')
            if robot._instantaneous_wrench_composer.active or robot._permanent_wrench_composer.active:
                raise ValueError('wrapper reset left active external wrenches')
            before_rng = rng_state()
            meta['control_attempt'] = {'rng_before_seed': before_rng, 'reference': str(args.reference) if args.reference else None}
            before = backend_values()
            if args.reference:
                reference_path = args.reference.resolve()
                reference_meta = json.loads((reference_path.parent / 'metadata.json').read_text(encoding='utf-8'))
                if (reference_meta['status'] != 'complete' or reference_meta['name'] != 'ctrl1'
                        or reference_meta.get('control', {}).get('mode') != 'controlled_initial_v1'
                        or reference_meta['raw_sha256'] != sha(reference_path)
                        or reference_meta['script_sha256'] != meta['script_sha256']):
                    raise ValueError('invalid reference run identity')
                with np.load(reference_path, allow_pickle=False) as ref:
                    validate(ref)
                    if not np.array_equal(ref['types'], types) or reference_meta['joint_names'] != meta['joint_names']:
                        raise ValueError('reference terrain assignment or joint names mismatch')
                    reference = {f: ref[f][0].copy() for f in FIELDS}
                meta['reference'] = {'path': str(reference_path), 'sha256': sha(reference_path)}
            else:
                reference = before
            control_raw.update({'control_before_' + f: before[f] for f in FIELDS})
            control_raw.update({'control_input_' + f: reference[f] for f in FIELDS})
            tensor = lambda a: torch.as_tensor(np.ascontiguousarray(a), device=mbenv.device)
            # root_*_vel_w is COM velocity in world coordinates; pose is link frame, xyzw.
            robot.write_root_link_pose_to_sim_index(root_pose=tensor(np.concatenate((reference['pos'], reference['quat']), axis=1)))
            robot.write_root_com_velocity_to_sim_index(root_velocity=tensor(np.concatenate((reference['lin'], reference['ang']), axis=1)))
            robot.write_joint_state_to_sim_index(position=tensor(reference['qpos']), velocity=tensor(reference['qvel']))
            actual = backend_values()
            control_raw.update({'control_readback_' + f: actual[f] for f in FIELDS})
            assert_controlled_initial(reference, actual)
            # API write methods leave some derived/cache timestamps valid. Force fresh simulation reads.
            for field in ('_root_link_pose_w', '_root_com_vel_w', '_root_link_vel_w', '_root_com_pose_w',
                          '_root_link_state_w', '_root_com_state_w', '_root_state_w', '_joint_pos', '_joint_vel'):
                getattr(robot.data, field).timestamp = -1.0
            # ProxyArray may already refer to an older allocation after a read refresh.
            for field in vars(robot.data):
                if field.startswith('_root_') and field.endswith('_ta'):
                    setattr(robot.data, field, None)
            robot.data._joint_pos_ta = robot.data._joint_vel_ta = None
            assert_controlled_initial(reference, values())
            random.seed(123)
            np.random.seed(123)
            torch.manual_seed(123)
            torch.cuda.manual_seed_all(123)
            meta['control'] = {'mode': 'controlled_initial_v1', 'runtime_seed': 123,
                               'rng_before_seed': before_rng, 'rng_after_seed': rng_state(),
                               'state_frame': 'root link pose xyzw; root COM linear/angular velocity in world',
                               'readback': 'PhysX root_view and refreshed IsaacLab data, no simulation step',
                               'limitation': 'PhysX internal state and independent RNG generators not controlled'}
        initial = values()
        if args.controlled_initial:
            assert_controlled_initial(reference, initial)
        for f in FIELDS:
            records[f].append(initial[f])
            pre[f].append(np.zeros_like(initial[f]))
        for f in flags:
            flags[f].append(np.zeros(72, dtype=bool))
        if args.rng_trace:
            state = rng_state()
            if len(state['torch_cuda']) != torch.cuda.device_count() or not state['torch_cuda']:
                raise ValueError('rng trace CUDA device count mismatch')
            meta['rng_trace'] = {'version': 1, 'cuda_devices': len(state['torch_cuda'])}
            rng_trace = [rng_digests(state)]
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
            if args.rng_trace:
                state = rng_state()
                if len(state['torch_cuda']) != meta['rng_trace']['cuda_devices']:
                    raise ValueError('rng trace CUDA device count changed')
                rng_trace.append(rng_digests(state))
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
        if args.rng_trace:
            control_raw['rng_trace'] = np.stack(rng_trace)
        if sha(Path(__file__)) != meta['script_sha256'] or source_hashes() != meta['source_hashes']:
            raise RuntimeError('capture source identity changed during run')
        if {str(p.resolve()): sha(p) for p in sorted(asset.parent.rglob('*')) if p.is_file()} != meta['asset_directory_files']:
            raise RuntimeError('asset identity changed during run')
        meta['status'] = 'complete'
    except BaseException:
        traceback.print_exc()
        raise
    finally:
        failed = sys.exc_info()[0] is not None
        try:
            if types is not None and records['pos']:
                raw = {f: np.stack(records[f]) for f in FIELDS}
                raw.update({f'reset_pre_{f}': np.stack(pre[f]) for f in FIELDS})
                raw.update({f: np.stack(flags[f]) for f in flags})
                raw['types'] = types
                raw.update(control_raw)
                with (output / 'raw.npz').open('xb') as stream:
                    np.savez_compressed(stream, **raw)
                meta['raw_sha256'] = sha(output / 'raw.npz')
            elif control_raw:
                with (output / 'control_failure.npz').open('xb') as stream:
                    np.savez_compressed(stream, **control_raw)
                meta['control_failure_sha256'] = sha(output / 'control_failure.npz')
            completed = meta['status'] == 'complete'
            meta['status'] = 'failed'
            with (output / 'metadata.json').open('x', encoding='utf-8') as stream:
                json.dump(meta, stream, indent=2, allow_nan=False, default=str)
            if env is not None:
                env.close()
            if completed:
                meta['status'] = 'complete'
                temporary = output / 'metadata.complete.json'
                with temporary.open('x', encoding='utf-8') as stream:
                    json.dump(meta, stream, indent=2, allow_nan=False, default=str)
                temporary.replace(output / 'metadata.json')
        except BaseException:
            failed = True
            traceback.print_exc()
        finally:
            if failed:
                try:
                    sys.stderr.flush()
                    sys.stdout.flush()
                finally:
                    os._exit(1)
        try:
            app.close()
        except BaseException as exc:
            if isinstance(exc, SystemExit) and exc.code in (None, 0):
                raise
            try:
                traceback.print_exc()
                meta['status'] = 'failed'
                temporary = output / 'metadata.close_failure.json'
                with temporary.open('x', encoding='utf-8') as stream:
                    json.dump(meta, stream, indent=2, allow_nan=False, default=str)
                temporary.replace(output / 'metadata.json')
            except BaseException:
                traceback.print_exc()
            finally:
                try:
                    sys.stderr.flush()
                    sys.stdout.flush()
                finally:
                    os._exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    child = sub.add_parser('run')
    child.add_argument('--output', required=True)
    child.add_argument('--steps', type=int, default=100)
    child.add_argument('--intervention', choices=('legacy', 'single_noise_min'), default='legacy')
    child.add_argument('--controlled_initial', action='store_true')
    child.add_argument('--rng_trace', action='store_true')
    child = sub.add_parser('capture')
    if len(sys.argv) > 1 and sys.argv[1] == 'capture':
        sys.path.insert(0, str(REPO))
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(child)
    child.add_argument('--output', required=True)
    child.add_argument('--steps', type=int, default=100)
    child.add_argument('--name', choices=RUNS, required=True)
    child.add_argument('--intervention', choices=('legacy', 'single_noise_min'), default='legacy')
    child.add_argument('--controlled_initial', action='store_true')
    child.add_argument('--rng_trace', action='store_true')
    child.add_argument('--reference', type=Path)
    comp = sub.add_parser('compare')
    comp.add_argument('directory', type=Path)
    comp.add_argument('--allow_unconfirmed', action='store_true')
    sub.add_parser('selftest')
    args = parser.parse_args()
    if args.command in ('run', 'capture') and args.steps < 1:
        parser.error('--steps must be positive')
    if args.command in ('run', 'capture') and args.controlled_initial and args.intervention != 'single_noise_min':
        parser.error('--controlled_initial requires --intervention single_noise_min')
    if args.command in ('run', 'capture') and args.rng_trace and not args.controlled_initial:
        parser.error('--rng_trace requires --controlled_initial')
    if args.command == 'capture' and args.controlled_initial and (args.name == 'ctrl1') == bool(args.reference):
        parser.error('controlled ctrl1 must not have --reference; other arms require it')
    if args.command == 'capture' and args.reference and not args.controlled_initial:
        parser.error('--reference requires --controlled_initial')
    if args.command == 'selftest':
        selftest()
    elif args.command == 'compare':
        compare(args.directory.resolve(), allow_unconfirmed=args.allow_unconfirmed)
    elif args.command == 'run':
        run(Path(args.output), args.steps, args.intervention, args.controlled_initial, args.rng_trace)
    else:
        capture(args)


if __name__ == '__main__':
    main()
