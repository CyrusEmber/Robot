# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Unapproved, offline lizard2 suspended-drive protocol; no simulator integration.

Callers supply v7 names and independently verified backend data. Targets are absolute
radians, not actions; scale/clip conversion and backend readback remain caller duties.
All trajectory samples are at physics-frame ends; targets are held from control-frame
starts. Safety must be called on *every* frame, not only after a completed case.
"""
from dataclasses import dataclass
import math

import numpy as np

DT = 0.005
DECIMATION = 4
LEGS = ('lf', 'rf', 'rl', 'rr')
GAINS = ('A', 'B')
GRAVITIES = ('off', 'on')


class Stop(RuntimeError):
    """Immediate safety stop; preserve the offending frame externally."""


def _array(value, shape, label):
    try:
        a = np.asarray(value, dtype=float)
    except (ValueError, TypeError) as exc:
        raise Stop(f'{label}: invalid numeric data') from exc
    if a.shape != shape or not np.isfinite(a).all():
        raise Stop(f'{label}: shape or finite-value failure')
    return a


def _legs(names):
    names = tuple(names)
    expected = {f'{leg}_{root}_{axis}_joint' for leg, root in
                (('lf', 'shoulder'), ('rf', 'shoulder'), ('rl', 'hip'), ('rr', 'hip'))
                for axis in ('swing', 'abduct', 'twist')}
    expected |= {f'{leg}_{end}_joint' for leg, end in
                 (('lf', 'elbow'), ('rf', 'elbow'), ('rl', 'knee'), ('rr', 'knee'))}
    if len(names) != 16 or len(set(names)) != 16 or set(names) != expected:
        raise Stop('16 named v7 leg joints required')
    return names


@dataclass(frozen=True)
class Case:
    gain: str
    gravity: str
    kind: str
    axes: tuple[str, ...]
    frequency: float = 0.0

    @property
    def id(self) -> str:
        return f'{self.gain}|{self.gravity}|{self.kind}|{",".join(self.axes)}|{self.frequency:g}'

    @property
    def steps(self) -> int:
        return 3400 if self.kind == 'hold' else int(round((2 + 4 / self.frequency) / DT))


def cases(leg_names, gain=None, gravity=None) -> list[Case]:
    """Build cases from v7 leg joint names; select one gain and/or gravity if needed."""
    legs = _legs(leg_names)
    if gain is not None and gain not in GAINS or gravity is not None and gravity not in GRAVITIES:
        raise Stop('unknown gain or gravity')
    result = []
    for g in (GAINS if gain is None else (gain,)):
        for grav in (GRAVITIES if gravity is None else (gravity,)):
            for axis in legs:
                result.extend((Case(g, grav, 'hold', (axis,)),
                               Case(g, grav, 'sin', (axis,), .5), Case(g, grav, 'sin', (axis,), 1.)))
            result.extend(Case(g, grav, 'hold', tuple(n for n in legs if n.startswith(leg + '_')))
                          for leg in LEGS)
    if gain is None and gravity is None:
        assert len(result) == len({c.id for c in result}) == 208
        assert sum(c.steps for c in result) == 476800
    return result


def swing_cases(leg_names) -> list[Case]:
    """Select the four swing axes and two frequencies for paired self-weight tests."""
    return [case for case in cases(leg_names, gain='A', gravity='on')
            if case.kind == 'sin' and case.axes[0].endswith('_swing_joint')]


def candidate_gains(names, stiffness, damping, inertia) -> tuple[np.ndarray, np.ndarray]:
    """Return candidate Kp [N m/rad], Kd [N m s/rad] from zero-pose inertia [kg m²].

    Inertia must be fixed-root, zero-pose downstream inertia, not a loaded
    effective inertia. Four swing axes use nominal 2 Hz and damping ratio 0.7;
    other axes keep v7 gains. This is not a loaded-support or bandwidth verdict.
    """
    names = tuple(names)
    if len(names) != 26 or len(set(names)) != 26:
        raise Stop('26 unique ordered joint names required')
    _legs([n for n in names if n.startswith(tuple(leg + '_' for leg in LEGS))])
    kp = _array(stiffness, (26,), 'stiffness').copy()
    kd = _array(damping, (26,), 'damping').copy()
    inertia = _array(inertia, (26,), 'inertia')
    if (kp <= 0).any() or (kd <= 0).any() or (inertia <= 0).any():
        raise Stop('invalid gain or inertia')
    swing = [i for i, name in enumerate(names) if name.endswith('_swing_joint')]
    if len(swing) != 4:
        raise Stop('invalid swing axes')
    kp[swing] = inertia[swing] * (4 * math.pi)**2
    kd[swing] = 1.4 * np.sqrt(kp[swing] * inertia[swing])
    return kp, kd


def _validate_case(case, names):
    names = tuple(names)
    if len(names) != 26 or len(set(names)) != 26:
        raise Stop('26 unique ordered joint names required')
    legs = _legs([n for n in names if n.startswith(tuple(leg + '_' for leg in LEGS))])
    if (case.gain not in GAINS or case.gravity not in GRAVITIES or case.kind not in ('hold', 'sin')
            or not case.axes or len(set(case.axes)) != len(case.axes) or not set(case.axes) <= set(legs)):
        raise Stop('invalid case')
    if len(case.axes) != 1 and (len(case.axes) != 4 or not any(
            set(case.axes) == {n for n in legs if n.startswith(leg + '_')} for leg in LEGS)):
        raise Stop('invalid combination')
    if (case.kind == 'sin' and (len(case.axes) != 1 or case.frequency not in (.5, 1.))
            or case.kind == 'hold' and case.frequency != 0):
        raise Stop('invalid case frequency')


def trajectory(case: Case, names, default) -> dict:
    """Return frame-end seconds, held absolute targets [rad], and boolean windows.

    ``names`` is the exact 26-axis backend order; ``default`` is its absolute target
    [rad]. Windows exclude the left boundary and include the right frame end.
    """
    _validate_case(case, names)
    default = _array(default, (26,), 'default')
    if np.any(default != 0):
        raise Stop('v7 default targets must be zero')
    n = case.steps
    end = (np.arange(n) + 1) * DT
    start = (np.arange(n) // DECIMATION) * (DECIMATION * DT)
    signal = np.zeros(n)
    windows = {'settle': (end > (4.5 if case.kind == 'hold' else 1.5)) &
                         (end <= (5. if case.kind == 'hold' else 2.))}
    if case.kind == 'hold':
        for sign, begin, label in ((1, 5., 'positive'), (-1, 11., 'negative')):
            x = np.clip((start - begin) / 2, 0, 1)
            up = x**3 * (10 + x * (-15 + 6*x))
            x = np.clip((start - begin - 3) / 2, 0, 1)
            down = x**3 * (10 + x * (-15 + 6*x))
            signal += sign * .1 * (up - down)
            for suffix, left, right in (('hold', begin + 2.5, begin + 3),
                                        ('return', begin + 5.5, begin + 6)):
                windows[f'{label}_{suffix}'] = (end > left) & (end <= right)
    else:
        active = start >= 2
        signal[active] = .1 * np.sin(2 * np.pi * case.frequency * (start[active] - 2))
        windows['measure'] = (end > 2 + 1 / case.frequency) & (end <= 2 + 4 / case.frequency)
    target = np.broadcast_to(default, (n, 26)).copy()
    target[:, [names.index(axis) for axis in case.axes]] += signal[:, None]
    return {'time': end, 'target': target, 'windows': windows}


def check_frame(*, names, expected_names, planned_target, target, readback, q, velocity, limits, velocity_cap,
                root_displacement, root_rotation, contact, body_names, expected_body_names,
                collision_body_names, contact_body_names, constant_window=None):
    """Raise Stop for a safety violation in one physics frame.

    Arrays use backend joint order; q/targets/limits are [rad], velocity/cap [rad/s].
    planned_target is this frame's trajectory sample, target is the sent command.
    Root displacement is [m], rotation angle [rad], filtered contact magnitudes [N].
    The 31-body vector contains ground-filtered readings for every collision body;
    other entries must be zero only after runtime geometry is independently verified.
    ``collision_body_names`` is that verified set; ``contact_body_names`` lists actual
    bound sensors. This function does not validate the stage or sensor filter identity.
    ``constant_window`` is consecutive q in the current last 0.5 s constant-target
    window (at most 100 frames), shape [frames, 26]. The caller must preserve raw
    non-finite samples and invoke this check before sending any next step.
    """
    if tuple(names) != tuple(expected_names) or len(names) != 26 or len(set(names)) != 26:
        raise Stop('joint order mismatch')
    if (len(body_names) != 31 or len(set(body_names)) != 31
            or tuple(body_names) != tuple(expected_body_names)):
        raise Stop('body coverage/order mismatch')
    collision_bodies, sensors = tuple(collision_body_names), tuple(contact_body_names)
    if (not collision_bodies or len(collision_bodies) != len(set(collision_bodies))
            or not set(collision_bodies) <= set(body_names) or len(sensors) != len(set(sensors))
            or set(sensors) != set(collision_bodies)):
        raise Stop('collision sensor coverage mismatch')
    planned_target = _array(planned_target, (26,), 'planned target')
    target = _array(target, (26,), 'target')
    readback = _array(readback, (26,), 'readback')
    q = _array(q, (26,), 'q')
    velocity = _array(velocity, (26,), 'velocity')
    limits = _array(limits, (26, 2), 'limits')
    cap = _array(velocity_cap, (26,), 'velocity cap')
    displacement = _array(root_displacement, (3,), 'root displacement')
    rotation = _array(root_rotation, (), 'root rotation')
    contact = _array(contact, (31,), 'contact')
    if (limits[:, 0] >= limits[:, 1]).any() or (cap <= 0).any() or (contact < 0).any() or rotation < 0:
        raise Stop('invalid limits, cap, rotation or contact magnitude')
    if any(contact[i] != 0 for i, name in enumerate(body_names) if name not in collision_bodies):
        raise Stop('noncollision body has contact reading')
    if not np.allclose(planned_target, target, rtol=0, atol=1e-7):
        raise Stop('sent target differs from planned trajectory')
    if not np.allclose(target, readback, rtol=0, atol=1e-7):
        raise Stop('backend target mismatch')
    if np.linalg.norm(displacement) > .001 or rotation > .001:
        raise Stop('root motion')
    if ((q < limits[:, 0] - .01) | (q > limits[:, 1] + .01)).any():
        raise Stop('physical limit exceeded')
    if (np.abs(q - target) > .35).any():
        raise Stop('position error')
    if (np.abs(velocity) >= cap / 2).any():
        raise Stop('velocity')
    if (contact > 1).any():
        raise Stop('contact')
    if constant_window is not None:
        history = np.asarray(constant_window)
        if history.ndim != 2 or not 1 <= len(history) <= 100:
            raise Stop('constant window shape')
        history = _array(history, (len(history), 26), 'constant window')
        if not np.array_equal(history[-1], q):
            raise Stop('constant window does not end at current frame')
        for column in history.T:
            # Ignore plateaus while retaining the last point before a change.
            keep = np.r_[np.diff(column) != 0, True]
            values = column[keep]
            d = np.diff(values)
            peaks = values[1:-1][d[:-1] * d[1:] < 0]
            if len(peaks) >= 4:
                a, b, c = np.abs(np.diff(peaks))[-3:]
                if a < b < c and c > .1:
                    raise Stop('growing oscillation')


def measure(case: Case, names, default, *, sample_names, time, target_readback, q) -> dict:
    """Compute direct tracking and coupling metrics after complete frame-end capture.

    All q and target_readback arrays are [physical steps, 26] in sample_names order,
    radians. Missing frames, reordered axes, non-finite values and wrong target fail.
    This does not replace per-frame safety or verify contact-channel provenance.
    Phase is response relative to continuous sin(2*pi*f*(t-2)) at frame end.
    """
    plan = trajectory(case, names, default)
    if tuple(sample_names) != tuple(names):
        raise Stop('sample joint order mismatch')
    n = case.steps
    times = _array(time, (n,), 'time')
    target = _array(target_readback, (n, 26), 'target readback')
    q = _array(q, (n, 26), 'q')
    if not np.allclose(times, plan['time'], rtol=0, atol=1e-9):
        raise Stop('missing or misaligned physics frames')
    if not np.allclose(target, plan['target'], rtol=0, atol=1e-7):
        raise Stop('backend target mismatch')
    indexes = [names.index(a) for a in case.axes]
    other = [i for i in range(26) if i not in indexes]
    settle = q[plan['windows']['settle']]
    if len(settle) != 100:
        raise Stop('settle window incomplete')
    drift = float(np.max(np.ptp(settle, axis=0)))
    later = q[times > (5 if case.kind == 'hold' else 2)][:, other]
    offset = float(max(np.max(np.abs(later - settle[:, other].min(axis=0))),
                       np.max(np.abs(later - settle[:, other].max(axis=0)))))
    result = {'settle_drift': drift, 'other_offset': offset,
              'precision_pass': drift <= .005 and offset <= .02}
    if case.kind == 'hold':
        errors = {}
        for name in ('positive_hold', 'positive_return', 'negative_hold', 'negative_return'):
            mask = plan['windows'][name]
            if mask.sum() != 100:
                raise Stop('hold window incomplete')
            errors[name] = np.max(np.abs(q[mask][:, indexes] - target[mask][:, indexes]), axis=0).tolist()
        result['errors'] = errors
        result['precision_pass'] &= max(max(v) for v in errors.values()) <= .05
    else:
        mask = plan['windows']['measure']
        if mask.sum() != round(3 / case.frequency / DT):
            raise Stop('sin window incomplete')
        actual = q[mask, indexes[0]]
        error = actual - target[mask, indexes[0]]
        phase_time = 2 * np.pi * case.frequency * (times[mask] - 2)
        design = np.column_stack((np.sin(phase_time), np.cos(phase_time), np.ones(len(actual))))
        coeff = np.linalg.lstsq(design, actual, rcond=None)[0]
        amplitude = float(np.hypot(coeff[0], coeff[1]))
        result.update(rms=float(np.sqrt(np.mean(error**2))), max_error=float(np.max(np.abs(error))),
                      amplitude=amplitude, amplitude_ratio=amplitude / .1,
                      phase_rad=float(np.arctan2(coeff[1], coeff[0])) if amplitude >= .01 else None,
                      fit_residual=float(np.sqrt(np.mean((actual - design @ coeff)**2))))
        result['precision_pass'] &= (result['rms'] <= .075 and result['max_error'] <= .15
                                     and result['fit_residual'] <= .02)
    return result


def compare(leg_names, results, gravity=None) -> dict:
    """Compare every matching A/B case for selected gravity (or both).

    Results map case IDs to measured metric dicts, augmented with safety='pass'
    or 'stop'. Missing/invalid metrics are unjudged. case_status records each
    individual result; cases records paired comparisons. Overall remains unjudged
    even when the suspended subset passes: torque/support are not measured.
    """
    all_cases = cases(leg_names, gravity=gravity)
    ids = [c.id for c in all_cases]
    if len(ids) != len(set(ids)) or any(k not in ids for k in results):
        raise Stop('duplicate case or unknown result id')
    output = {}

    def safety_failure(item):
        return isinstance(item, dict) and item.get('safety') == 'stop'

    def precision(case, item):
        drift = _array(item['settle_drift'], (), 'settle drift').item()
        offset = _array(item['other_offset'], (), 'other offset').item()
        if drift < 0 or offset < 0:
            raise ValueError('negative drift or offset')
        valid = drift <= .005 and offset <= .02
        if case.kind == 'sin':
            metrics = _array([item['rms'], item['max_error'], item['fit_residual']], (3,), 'sin metrics')
            if (metrics < 0).any():
                raise ValueError('negative sin metric')
            return valid and bool(np.all(metrics <= [.075, .15, .02]))
        errors = _array([item['errors'][w] for w in ('positive_hold', 'positive_return',
                         'negative_hold', 'negative_return')], (4, len(case.axes)), 'hold errors')
        if (errors < 0).any():
            raise ValueError('negative hold error')
        return valid and bool((errors <= .05).all())

    absolute = {}
    for case in all_cases:
        item = results.get(case.id)
        if not isinstance(item, dict) or item.get('safety') != 'pass':
            continue
        try:
            absolute[case.id] = precision(case, item)
        except (KeyError, TypeError, ValueError, Stop):
            pass
    case_status = {case.id: ('stop' if safety_failure(results.get(case.id)) else
                             'unjudged' if case.id not in absolute else
                             'pass' if absolute[case.id] else 'fail') for case in all_cases}
    any_stop = any(safety_failure(item) for item in results.values())
    for b in (c for c in all_cases if c.gain == 'B'):
        a = Case('A', b.gravity, b.kind, b.axes, b.frequency)
        key = b.id
        if safety_failure(results.get(a.id)) or safety_failure(results.get(key)):
            output[key] = 'stop'
            continue
        if a.id not in ids or a.id not in results or key not in results:
            output[key] = 'unjudged'
            continue
        left, right = results[a.id], results[key]
        if not isinstance(left, dict) or not isinstance(right, dict):
            output[key] = 'unjudged'
            continue
        if left.get('safety') == 'stop' or right.get('safety') == 'stop':
            output[key] = 'stop'
            continue
        if left.get('safety') != 'pass' or right.get('safety') != 'pass':
            output[key] = 'unjudged'
            continue
        try:
            if a.id not in absolute or key not in absolute:
                raise ValueError('missing metrics')
            absolute_pass = absolute[a.id] and absolute[key]
            if b.kind == 'sin':
                av = _array(left['rms'], (), 'A rms').item()
                bv = _array(right['rms'], (), 'B rms').item()
                swing = b.axes[0].endswith('_swing_joint')
                passed = bv <= (.9 * av if swing else 1.1 * av + .002)
            else:
                av = _array([left['errors'][w] for w in ('positive_hold', 'positive_return',
                              'negative_hold', 'negative_return')], (4, len(b.axes)), 'A errors')
                bv = _array([right['errors'][w] for w in ('positive_hold', 'positive_return',
                              'negative_hold', 'negative_return')], (4, len(b.axes)), 'B errors')
                swing = len(b.axes) == 1 and b.axes[0].endswith('_swing_joint')
                passed = swing or bool(np.all(bv <= 1.1 * av + .002))
            output[key] = 'pass' if passed and absolute_pass else 'fail'
        except (KeyError, TypeError, ValueError, Stop):
            output[key] = 'unjudged'
    subset = ('stop' if any_stop else 'fail' if 'fail' in output.values() or False in absolute.values() else
              'unjudged' if not output or 'unjudged' in output.values() else 'pass')
    return {'case_status': case_status, 'cases': output, 'suspended_subset': subset, 'overall': 'unjudged'}
