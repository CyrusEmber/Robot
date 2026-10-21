# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Audit a bounded left-knee PhysX force probe without starting physics.

Reads two 3400-step fixed-root self-weight cases at symmetric knee/elbow Kp=220.
Reprojects raw incoming child-frame wrenches, checks force-source attribution,
and compares settled torque with an independent COM potential derivative.
Reported torques are step averages [N*m], time [s], joint angles [rad].
This does not test peak actuator capability or validate other postures/contacts.
"""
from pathlib import Path
import argparse
import copy
import json
import math
import sys
import xml.etree.ElementTree as ET
import numpy as np

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root/'rl_exp/tools/diagnose'))
import palm_spatial_runtime as wiring
from palm_spatial_inertia import csc

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True, help='New JSON analysis path; existing evidence is never overwritten')
args = parser.parse_args()
report_path = args.report.resolve()
out = report_path.parent
assert args.out.parent.is_dir() and not args.out.exists()
report = json.loads(report_path.read_text(encoding='utf-8'))
assert report['completed'] and report['selected_cases_completed']
assert report['steps_completed'] == report['planned_max_steps'] == 6800
assert [c['case'] for c in report['cases']] == ['rl_combined', 'rl_knee_joint']
assert report['retry_allowed'] is False and report['full_runs_started'] == 1
assert report['code_sha256'] == wiring.binding.sha256_file(out/'source.py')
assert report['tracking_manifest_sha256'] == wiring.binding.sha256_file(out/'tracking_manifest.json')
for p, h in report['input'].items():
    assert wiring.binding.sha256_file(Path(p)) == h
prior_path = Path(report['resume']['report'])
assert wiring.binding.sha256_file(prior_path) == report['resume']['report_sha256']
prior = json.loads(prior_path.read_text(encoding='utf-8'))
expected_design = copy.deepcopy(prior['design'])
for name in ('rl_knee_joint', 'rr_knee_joint', 'lf_elbow_joint', 'rf_elbow_joint'):
    i = expected_design['joint_names'].index(name)
    expected_design['kp'][i] = 220.
    expected_design['kd'][i] *= math.sqrt(220./prior['design']['kp'][i])
assert report['design'] == expected_design
for key in ('kp', 'kd'):
    assert np.array_equal(np.asarray(report['readbacks'][key]), np.asarray(expected_design[key], dtype=np.float32))
assert {k: v for k, v in report['readbacks'].items() if k not in ('kp', 'kd')} == {k: v for k, v in prior['readbacks'].items() if k not in ('kp', 'kd')}
manifest = json.loads((out/'tracking_manifest.json').read_text(encoding='utf-8'))
tree = ET.parse(manifest['target_binding']['urdf']).getroot()
model = csc.load_urdf(Path(manifest['target_binding']['urdf']))
names = report['joint_names']
index = names.index('rl_knee_joint')
binding = report['joint_force_probe']
assert binding['joint_names'] == names
assert binding['joints']['rl_knee_joint']['child_body'] == 'rl_knee'
assert binding['joints']['rl_knee_joint']['axis'] == 'X'
assert all(spec['drive_type'] == 'force' for spec in binding['joints'].values())
mass, center = {}, {}
for link in tree.findall('link'):
    name = link.get('name')
    mass[name] = float(link.find('inertial/mass').get('value'))
    center[name] = np.fromstring(link.find('inertial/origin').get('xyz'), sep=' ')

def potential(q):
    angles = dict(zip(names, q))
    frames = {n: csc.fk(model['joints'], n, angles) for n in mass}
    return sum(9.81*mass[n]*(frames[n][:3, :3]@center[n]+frames[n][:3, 3])[2] for n in mass)

def gravity_compensation(q):
    step = np.zeros(len(q)); step[index] = 1e-5
    return (potential(q+step)-potential(q-step))/(2e-5)

def quintic(t):
    if t <= 2:
        u = t/2
    elif t <= 3:
        return .02
    elif t <= 5:
        u = (5-t)/2
    else:
        return 0.
    return .02*(6*u**5-15*u**4+10*u**3)

def max_run(mask):
    best = current = 0
    for x in mask:
        current = current+1 if x else 0
        best = max(best, current)
    return best

caps = np.asarray(report['readbacks']['effort_caps'])
assert caps[index] == 180.
limits = np.asarray(binding['position_limits_rad'])
friction = np.asarray(binding['friction_properties'])
armature = np.asarray(binding['armatures'])
results = []
assert friction.shape == (30, 3) and armature.shape == (30,) and limits.shape == (30, 2)
assert all(np.isfinite(a).all() for a in (friction, armature, limits, caps))
assert np.all(caps > 0)
projection_max = 0.
explicit_max = 0.
fk_max = 0.
for summary in report['cases']:
    data = json.loads((out/(summary['case']+'.json')).read_text(encoding='utf-8'))
    assert data['summary'] == summary and len(data['samples']) == 3400 and len(data['entities']) == 5
    rows = data['samples']
    t = np.asarray([r['t_s'] for r in rows])
    q = np.asarray([r['q_rad'] for r in rows])
    u = np.asarray([r['target_rad'] for r in rows])
    v = np.asarray([r['velocity_rad_s'] for r in rows])
    contact = np.asarray([r['max_contact_n'] for r in rows])
    projected = np.asarray([r['joint_force_probe']['projected_joint_effort_nm'] for r in rows])
    incoming = np.asarray([r['joint_force_probe']['incoming_child_joint_wrench'] for r in rows])
    explicit = np.asarray([r['joint_force_probe']['explicit_actuation_input_nm'] for r in rows])
    manual = np.asarray([[incoming[k, binding['joints'][n]['child_index'], binding['joints'][n]['torque_component']]
                          for n in names] for k in range(len(rows))])
    assert all(np.isfinite(a).all() for a in (q, u, v, contact, incoming, projected, explicit, t))
    assert np.array_equal(t, np.arange(1, 3401)*.005)
    axes = [names.index(n) for n in summary['commanded_joints']]
    expected = np.zeros_like(u)
    expected[:, axes] = np.asarray([quintic(max(float(s)-5, 0)) if s <= 11 else -quintic(float(s)-11) for s in t])[:, None]
    assert np.allclose(expected, u, atol=1e-16, rtol=0)
    assert np.array_equal(np.asarray([r['backend_drive_targets']['position_rad'] for r in rows]), u.astype(np.float32).astype(float))
    assert np.count_nonzero([r['backend_drive_targets']['velocity_rad_s'] for r in rows]) == 0
    assert abs(q).max() <= .35 and abs(q-u).max() <= .35
    assert np.all(abs(v) < np.asarray(report['readbacks']['velocity_caps'])*.5) and contact.max() <= 1.
    baseline = q[999]
    directions = []
    absolute_directions = []
    for start in (5., 11.):
        active = (t > start)&(t <= start+6.)
        local = t[active]-start
        error = abs(q[active][:, axes]-baseline[axes]-u[active][:, axes])
        other = np.delete(q[active]-baseline, axes, axis=1)
        item = dict(max_error_rad=float(error.max()),
                    plateau_error_rad=float(error[(local >= 2.8)&(local <= 3.)].max()),
                    final_error_rad=float(error[local >= 5.8].max()),
                    max_other_joint_rad=float(abs(other).max()))
        item['passed'] = bool(item['max_error_rad'] <= .012 and item['plateau_error_rad'] <= .002
            and item['final_error_rad'] <= .002 and item['max_other_joint_rad'] <= .01)
        directions.append(item)
        absolute_error = abs(q[active, index]-u[active, index])
        absolute_directions.append(dict(max_error_rad=float(absolute_error.max()),
            plateau_error_rad=float(absolute_error[(local >= 2.8)&(local <= 3.)].max()),
            final_error_rad=float(absolute_error[local >= 5.8].max())))
    settling = (t >= 4.8)&(t <= 5.)
    absolute = dict(settle_error_rad=float(abs(q[settling, index]-u[settling, index]).max()),
                    directions=absolute_directions)
    absolute['passed'] = bool(absolute['settle_error_rad'] <= .002 and all(
        d['plateau_error_rad'] <= .002 and d['final_error_rad'] <= .002 for d in absolute_directions))
    assert directions == summary['directions'] and absolute == summary['left_knee_absolute']
    incremental_passed = bool(all(d['passed'] for d in directions) and np.ptp(q[settling], axis=0).max() <= .002
        and abs(q[settling]).max() <= .1 and abs(q-u).max() <= .1)
    assert incremental_passed == summary['incremental_passed']
    assert summary['passed'] == (incremental_passed and absolute['passed'])
    projection_max = max(projection_max, float(abs(projected-manual).max()))
    explicit_max = max(explicit_max, float(abs(explicit).max()))
    raw_manual = np.asarray([r['joint_force_probe']['manual_axis_projection_nm'] for r in rows])
    assert np.array_equal(raw_manual, manual)
    tau = projected[:, index]
    shadow = np.asarray([r['reconstructed_pd_request_nm'][index] for r in rows])
    kp, kd = report['readbacks']['kp'][index], report['readbacks']['kd'][index]
    assert np.allclose(shadow, kp*(u[:, index]-q[:, index])-kd*v[:, index], atol=1e-7, rtol=1e-6)
    masks = {'settle': (t >= 4.8)&(t <= 5.)}
    for label, start in (('positive', 5.), ('negative', 11.)):
        local = t-start
        masks[label+'_hold'] = (local >= 2.8)&(local <= 3.)
        masks[label+'_return'] = (local >= 5.8)&(local <= 6.)
        masks[label+'_motion'] = ((local > 0)&(local < 2.))|((local > 3.)&(local < 5.))
    windows = {}
    for label, mask in masks.items():
        item = dict(peak_abs_nm=float(abs(tau[mask]).max()), mean_nm=float(tau[mask].mean()),
                    max_absolute_error_rad=float(abs(q[mask, index]-u[mask, index]).max()),
                    max_read_velocity_rad_s=float(abs(v[mask, index]).max()),
                    max_position_derivative_rad_s=float(abs(np.gradient(q[:, index], .005)[mask]).max()),
                    mean_shadow_nm=float(shadow[mask].mean()), peak_to_peak_nm=float(np.ptp(tau[mask])))
        if label == 'settle' or label.endswith('_hold') or label.endswith('_return'):
            comp = gravity_compensation(q[mask].mean(axis=0))
            item.update(gravity_compensation_nm=float(comp), gravity_residual_nm=float(item['mean_nm']-comp),
                        mean_proportional_term_nm=float((kp*(u[mask, index]-q[mask, index])).mean()))
        windows[label] = item
    ratio = abs(tau)/caps[index]
    peak = int(abs(tau).argmax())
    margin = np.minimum(q-limits[:, 0], limits[:, 1]-q)
    result = dict(case=summary['case'], peak_abs_nm=float(abs(tau).max()), peak_time_s=float(t[peak]),
                  peak_fraction_of_cap=float(ratio.max()),
                  active_peak_abs_nm=float(abs(tau[t > 5.]).max()),
                  active_peak_fraction_of_cap=float(ratio[t > 5.].max()), peak_signed_nm=float(tau[peak]),
                  samples_at_or_above_99pct_cap=int(np.count_nonzero(ratio >= .99)),
                  longest_99pct_cap_run_s=max_run(ratio >= .99)*.005,
                  minimum_position_limit_margin_rad=float(margin[:, index].min()),
                  max_shadow_difference_nm=float(abs(tau-shadow).max()),
                  windows=windows, tracking_passed=summary['passed'])
    for e in data['entities']:
        qmap = dict(zip(e['joint_names'], e['q_rad']))
        actual = np.asarray(e['actor_poses_xyzw'])
        # Root is fixed at the original identity orientation; compare FK positions only here.
        root_pose = actual[e['body_names'].index('base_link')]
        assert np.allclose(root_pose[3:], [0., 0., 0., 1.], atol=1e-6, rtol=0)
        base_pos = root_pose[:3]
        for name, pose in zip(e['body_names'], actual):
            frame = csc.fk(model['joints'], name, qmap)
            fk_max = max(fk_max, float(abs(frame[:3, 3]+base_pos-pose[:3]).max()))
    results.append(result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
assert fk_max < 1e-5
attributable = bool(projection_max <= 1e-4 and explicit_max == 0. and np.count_nonzero(friction) == 0
    and np.count_nonzero(armature) == 0 and not binding['tendon_prims']
    and all(c['minimum_position_limit_margin_rad'] > .1 for c in results))
analysis = dict(completed=True, steps=6800, report_sha256=wiring.binding.sha256_file(out/'report.json'),
    source_sha256=report['code_sha256'], independent_actor_position_max_error=fk_max,
    projection_max_difference_nm=projection_max, explicit_actuation_max_abs_nm=explicit_max,
    friction_properties_max_abs=float(abs(friction).max()), armature_max_abs=float(abs(armature).max()),
    knee_step_average_drive_attribution_supported=attributable, cases=results,
    scope='current fixed-root self-weight +/-0.02 rad only; step averages do not bound substep peaks; not a max-torque stress test')
wiring.write_json(args.out, analysis)
print('JOINT_FORCE_ANALYSIS', json.dumps({k: v for k, v in analysis.items() if k != 'cases'}, ensure_ascii=False), flush=True)
