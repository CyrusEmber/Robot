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


def summarize(path: Path, window: int = 25) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    cases, rows, names = data['sweep_cases'], data['rows'], data['joint_names']
    if len(cases) != 2 * len(names) or len(rows) < window or window < 1:
        raise ValueError('missing sweep cases or measurement window')
    keyed = {(case['joint'], case['sign']): index + 1 for index, case in enumerate(cases)}
    if len(keyed) != len(cases) or set(keyed) != {(name, sign) for name in names for sign in (-1, 1)}:
        raise ValueError('sweep must cover every joint and sign once')
    # Auto-reset can replace a terminal pose, invalidating paired late-window comparisons.
    if any(any(row['done']) for row in rows):
        raise ValueError('episode terminated: inspect the pre-reset raw data, do not summarize')
    last = rows[-window:]
    result = {}
    for joint_index, name in enumerate(names):
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
            'response_half_range_rad': (mean(plus, 'joint_positions') - mean(minus, 'joint_positions')) / 2.,
        }
    return {'source': str(path), 'no_gravity': data['no_gravity'],
            'window_steps': window, 'dt_s': data['dt_s'], 'joints': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--window', type=int, default=25)
    args = parser.parse_args()
    print(json.dumps(summarize(args.report, args.window), indent=2, allow_nan=False))
