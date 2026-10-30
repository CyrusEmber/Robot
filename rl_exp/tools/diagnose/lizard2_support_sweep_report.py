# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Summarize paired joint sweeps without treating reset frames as measurements."""
import argparse
import json
import math
from pathlib import Path
import statistics


def safety_failures(row: dict, limits: list, foot_ids: list[int]) -> list[dict]:
    """Check batched pre-reset readings: height [m], tilt/foot margin [rad]."""
    failures = []
    for env, done in enumerate(row['done']):
        reasons = ['done'] if done else []
        fields = ('root_position', 'gravity_b', 'joint_positions', 'joint_velocities')
        fields += tuple(key for key in ('root_velocity',) if key in row)
        if not all(math.isfinite(x) for key in fields for x in row[key][env]):
            reasons.append('nonfinite')
        if row['root_position'][env][2] < .45:
            reasons.append('root_height')
        if -row['gravity_b'][env][2] < math.cos(math.radians(30)):
            reasons.append('tilt')
        if any(not all(math.isfinite(x) for x in limits[env][j]) or
               min(row['joint_positions'][env][j] - limits[env][j][0],
                   limits[env][j][1] - row['joint_positions'][env][j]) < .02 for j in foot_ids):
            reasons.append('foot_limit_margin')
        failures.extend({'env': env, 'reason': reason} for reason in reasons)
    return failures


def json_finite(value):
    """Preserve nonfinite raw evidence as explicit strings in strict JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: json_finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_finite(item) for item in value]
    return value


def summarize(path: Path, window: int = 25) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    cases, rows, names = data['sweep_cases'], data['rows'], data['joint_names']
    selected = [name for name in names if any(case['joint'] == name for case in cases)] if data.get('feet_sweep') else names
    if len(cases) != 2 * len(selected) or len(rows) < window or window < 1:
        raise ValueError('missing sweep cases or measurement window')
    keyed = {(case['joint'], case['sign']): index + 1 for index, case in enumerate(cases)}
    if len(keyed) != len(cases) or set(keyed) != {(name, sign) for name in selected for sign in (-1, 1)}:
        raise ValueError('sweep must cover every selected joint and sign once')
    # Auto-reset can replace a terminal pose, invalidating paired late-window comparisons.
    if data.get('safety_failures') or any(any(row['done']) for row in rows):
        raise ValueError('episode terminated or safety failed: inspect the pre-reset raw data, do not summarize')
    last = rows[-window:]
    result = {}
    for name in selected:
        joint_index = names.index(name)
        def mean(env, field):
            numbers = [row[field][env][joint_index] for row in last]
            if not all(math.isfinite(value) for value in numbers):
                raise ValueError('nonfinite joint reading')
            return statistics.mean(numbers)
        minus, plus = keyed[name, -1], keyed[name, 1]
        neg_target, pos_target = mean(minus, 'joint_targets'), mean(plus, 'joint_targets')
        result[name] = {
            'zero_position_rad': mean(0, 'joint_positions'),
            'zero_target_rad': mean(0, 'joint_targets'),
            'negative_target_rad': neg_target,
            'positive_target_rad': pos_target,
            'negative_position_rad': mean(minus, 'joint_positions'),
            'positive_position_rad': mean(plus, 'joint_positions'),
            'target_half_range_rad': (pos_target - neg_target) / 2.,
            'response_half_range_rad': (mean(plus, 'joint_positions') - mean(minus, 'joint_positions')) / 2.,
        }
    return {'source': str(path), 'no_gravity': data['no_gravity'],
            'window_steps': window, 'dt_s': data['dt_s'], 'joints': result}


def summarize_hold(path: Path, window_s: float = 2) -> dict:
    """Describe final-window hold readings [rad, rad/s, m, s]; no success thresholds.

    Errors are position minus target. Drift is late-half mean minus early-half
    mean, split at the temporal midpoint of the final window, per environment.
    """
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data.get('rows', [])
    if data.get('safety_failures') or data.get('trial_status') != 'completed':
        raise ValueError('hold not completed or safety failed')
    duration, dt = data.get('duration_s'), data.get('dt_s')
    if not all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0
               for x in (duration, dt, window_s)) or not rows:
        raise ValueError('missing or invalid duration, timestep or measurement window')
    names, feet = data['joint_names'], data['foot_joint_names']
    if len(feet) != 8 or len(set(feet)) != 8 or any(names.count(name) != 1 for name in feet):
        raise ValueError('hold requires eight unique foot joints')
    env_count = len(rows[0]['done'])
    if not env_count:
        raise ValueError('missing batched environments')
    previous = None
    fields = ('root_position', 'gravity_b', 'joint_positions', 'joint_targets', 'joint_velocities')
    for row in rows:
        step = row.get('step')
        if (not isinstance(step, int) or step < 0 or
                (previous is not None and step != previous + 1)):
            raise ValueError('missing or invalid contiguous measurement window')
        previous = step
        if len(row['done']) != env_count or any(row['done']):
            raise ValueError('episode terminated or inconsistent batch')
        for field in fields + tuple(key for key in ('root_velocity',) if key in row):
            if len(row[field]) != env_count:
                raise ValueError('inconsistent batch')
            for values in row[field]:
                expected = 3 if field in ('root_position', 'gravity_b') else len(names)
                if field != 'root_velocity' and len(values) != expected:
                    raise ValueError('inconsistent reading dimensions')
                if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in values):
                    raise ValueError('nonfinite hold reading')
    ended = rows[-1]['step'] * dt
    if ended < duration - dt / 2:
        raise ValueError('incomplete hold duration')
    start = ended - window_s
    if start < -dt / 2 or rows[0]['step'] * dt > start + dt + 1e-9:
        raise ValueError('missing measurement window')
    last = [row for row in rows if row['step'] * dt > start + 1e-9]
    early = [row for row in last if row['step'] * dt <= start + window_s / 2 + 1e-9]
    late = [row for row in last if row['step'] * dt > start + window_s / 2 + 1e-9]
    if not early or not late:
        raise ValueError('missing early or late half window')
    envs = []
    for env in range(env_count):
        def drift(field, index):
            return (statistics.mean(row[field][env][index] for row in late) -
                    statistics.mean(row[field][env][index] for row in early))
        joints = {}
        for name in feet:
            index = names.index(name)
            errors = [row['joint_positions'][env][index] - row['joint_targets'][env][index] for row in last]
            joints[name] = {
                'target_error_mean_rad': statistics.mean(errors),
                'target_error_min_rad': min(errors),
                'target_error_max_rad': max(errors),
                'position_drift_rad': drift('joint_positions', index),
                'max_abs_velocity_rad_s': max(abs(row['joint_velocities'][env][index]) for row in last),
            }
        envs.append({'env': env, 'joints': joints,
                     'root_height_drift_m': drift('root_position', 2),
                     'tilt_max_rad': max(math.acos(max(-1., min(1., -row['gravity_b'][env][2])))
                                         for row in last)})
    return {'source': str(path), 'duration_s': duration, 'ended_time_s': ended,
            'dt_s': dt, 'window_s': window_s, 'window_steps': len(last),
            'error_convention': 'position minus target',
            'drift_convention': 'late-half mean minus early-half mean', 'envs': envs}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--window', type=int, default=25)
    parser.add_argument('--hold', action='store_true')
    parser.add_argument('--window_s', type=float, default=2.)
    args = parser.parse_args()
    result = summarize_hold(args.report, args.window_s) if args.hold else summarize(args.report, args.window)
    print(json.dumps(result, indent=2, allow_nan=False))
