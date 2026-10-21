# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Independently reread stored bidirectional single-axis self-weight samples.

--report REPORT.json [--output FRESH.json]. No Kit, simulation or shared writer.
Supports completed selected single-axis runs with the frozen 0.005 s / 17 s /
0.02 rad protocol. Recomputes targets, float32 backend targets, PD requests,
bidirectional verdicts and actor-pose FK from stored samples. Does not rerun
physics, audit gain-selection formulas, approve deployment or infer missing
cases. passed=True means audit consistency, including a real failed verdict.
Historical variant-specific preparation checks remain in their archived sources.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

if sys.flags.optimize:
    raise RuntimeError('self_weight_audit requires assertions; optimization is unsupported')

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'rl_exp/tools/runrecord'))
from binding import sha256_file


def audit(report_path: Path) -> dict:
    """Return independently recomputed sample consistency for a supported report."""
    out = report_path.parent
    report = json.loads(report_path.read_text(encoding='utf-8'))
    assert report['completed'] and report['selected_cases_completed'], 'incomplete selected cases'
    names = report['joint_names']
    assert len(names) == len(set(names)) and names, 'ambiguous joint order'
    assert [c['case'] for c in report['cases']] == list(report['selected_cases']), 'case coverage'
    assert all(c['case'] in names and c['commanded_joints'] == [c['case']]
               for c in report['cases']), 'only single-axis samples are supported'
    assert report['planned_max_steps'] == report['steps_completed'] == 3400 * len(report['cases'])
    required = dict(amplitude_rad=.02, ramp_s=2., hold_s=1., dt_s=.005,
                    max_error_rad=.012, hold_error_rad=.002, max_other_joint_rad=.01,
                    settle_s=5., max_absolute_error_rad=.1, settle_drift_rad=.002,
                    stop_absolute_error_rad=.35, stop_contact_n=1., velocity_target='zero')
    assert all(report['settings'].get(k) == v for k, v in required.items()), 'unsupported protocol'
    assert report['code_sha256'] == sha256_file(out / 'source.py'), 'source snapshot changed'
    for path, digest in report['input'].items():
        assert sha256_file(Path(path)) == digest, 'input binding changed: ' + path
    manifest_path = out / 'tracking_manifest.json'
    assert sha256_file(manifest_path) == report['tracking_manifest_sha256'], 'manifest changed'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    urdf_path = Path(manifest['target_binding']['urdf'])
    assert sha256_file(urdf_path) == manifest['sha256']['urdf'], 'URDF changed'
    assert report['readbacks']['fixed_base'] and len(report['readbacks']['body_disable_gravity']) == 31
    assert all(v is False for v in report['readbacks']['body_disable_gravity'].values())
    for key in ('kp', 'kd'):
        assert np.array_equal(np.asarray(report['readbacks'][key]),
                              np.asarray(report['design'][key], dtype=np.float32)), 'gain readback mismatch'
    speeds = np.asarray(report['readbacks']['velocity_caps'])
    assert speeds.shape == (len(names),) and np.isfinite(speeds).all() and (speeds > 0).all()
    urdf = ET.parse(urdf_path).getroot()
    joints = []

    def rodrigues(axis, angle):
        a = np.asarray(axis, dtype=float)
        a /= np.linalg.norm(a)
        x,y,z = a
        skew = np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
        return np.eye(3)+math.sin(angle)*skew+(1-math.cos(angle))*(skew@skew)

    for j in urdf.findall('joint'):
        origin = j.find('origin')
        xyz = np.fromstring(origin.get('xyz','0 0 0') if origin is not None else '0 0 0', sep=' ')
        rpy = np.fromstring(origin.get('rpy','0 0 0') if origin is not None else '0 0 0', sep=' ')
        transform = np.eye(4)
        transform[:3,3] = xyz
        transform[:3,:3] = rodrigues([0,0,1],rpy[2])@rodrigues([0,1,0],rpy[1])@rodrigues([1,0,0],rpy[0])
        axis = j.find('axis')
        joints.append((j.get('name'), j.find('parent').get('link'), j.find('child').get('link'),
                       transform, np.fromstring(axis.get('xyz') if axis is not None else '1 0 0',sep=' ')))

    def quat_matrix(quat):
        # Independent normalized axis-angle conversion from stored xyzw actor poses.
        q = np.asarray(quat, dtype=float)
        q /= np.linalg.norm(q)
        length = np.linalg.norm(q[:3])
        return np.eye(3) if length < 1e-15 else rodrigues(q[:3]/length, 2*math.atan2(length,q[3]))

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

    results = []
    fk_max = 0.
    contact_max = 0.
    velocity_ratio_max = 0.
    reconstructed_delta_max = 0.
    for summary in report['cases']:
        data = json.loads((out/(summary['case']+'.json')).read_text(encoding='utf-8'))
        assert data['summary'] == summary
        rows = data['samples']
        assert len(rows) == 3400
        t = np.asarray([r['t_s'] for r in rows])
        q = np.asarray([r['q_rad'] for r in rows])
        target = np.asarray([r['target_rad'] for r in rows])
        v = np.asarray([r['velocity_rad_s'] for r in rows])
        contacts = np.asarray([r['max_contact_n'] for r in rows])
        assert all(np.isfinite(a).all() for a in (q,target,v,contacts,t))
        assert np.array_equal(t,np.arange(1,3401)*.005)
        index = names.index(summary['case'])
        expected = np.zeros_like(target)
        expected[:,index] = [quintic(max(float(s)-5,0)) if s <= 11 else -quintic(float(s)-11) for s in t]
        assert np.allclose(expected,target,atol=1e-16,rtol=0), 'stored target differs from prescribed motion'
        backend = np.asarray([r['backend_drive_targets']['position_rad'] for r in rows])
        assert np.array_equal(backend,target.astype(np.float32).astype(float))
        assert all(r['backend_drive_targets']['joint_names'] == names for r in rows)
        assert np.count_nonzero([r['backend_drive_targets']['velocity_rad_s'] for r in rows]) == 0
        assert abs(q).max() <= .35 and abs(q-target).max() <= .35
        assert np.all(abs(v) < speeds*.5) and contacts.max() <= 1.
        contact_max = max(contact_max,float(contacts.max()))
        velocity_ratio_max = max(velocity_ratio_max,float((abs(v)/speeds).max()))
        kp,kd = [np.asarray(report['readbacks'][key],dtype=np.float32) for key in ('kp','kd')]
        reconstructed = kp*(target-q.astype(np.float32))-kd*v.astype(np.float32)
        requested = np.asarray([r['reconstructed_pd_request_nm'] for r in rows])
        reconstructed_delta_max = max(reconstructed_delta_max,float(abs(reconstructed-requested).max()))
        assert np.array_equal(reconstructed,requested)
        baseline = q[999]
        settling = (t>=4.8)&(t<=5.)
        directions = []
        for start in (5.,11.):
            select = (t>start)&(t<=start+6.)
            local = t[select]-start
            error = abs(q[select,index]-baseline[index]-target[select,index])
            other = np.delete(q[select]-baseline,index,axis=1)
            d = dict(max_error_rad=float(error.max()),
                     plateau_error_rad=float(error[(local>=2.8)&(local<=3.)].max()),
                     final_error_rad=float(error[local>=5.8].max()),
                     max_other_joint_rad=float(abs(other).max()))
            d['passed'] = d['max_error_rad']<=.012 and d['plateau_error_rad']<=.002 and d['final_error_rad']<=.002 and d['max_other_joint_rad']<=.01
            directions.append(d)
            # At hold midpoint the actual motion has the commanded sign.
            sample = int(round((start+2.9)/.005))-1
            assert (q[sample,index]-baseline[index])*target[sample,index] > 0
        verdict = dict(passed=bool(all(d['passed'] for d in directions)
                       and np.ptp(q[settling],axis=0).max()<=.002 and abs(q[settling]).max()<=.1 and abs(q-target).max()<=.1),
                       directions=directions, baseline_q_rad=baseline.tolist(),
                       settle_drift_rad=float(np.ptp(q[settling],axis=0).max()),
                       settle_absolute_error_rad=float(abs(q[settling]).max()),
                       max_absolute_error_rad=float(abs(q-target).max()))
        assert verdict == {k:v for k,v in summary.items() if k not in ('case','commanded_joints','samples_completed')}
        assert len(data['entities']) == 5
        for e in data['entities']:
            actual = {}
            for link,pose in zip(e['body_names'],e['actor_poses_xyzw']):
                tr = np.eye(4)
                tr[:3,:3] = quat_matrix(pose[3:])
                tr[:3,3] = pose[:3]
                actual[link] = tr
            poses = {'base_link':actual['base_link']}
            qmap = dict(zip(e['joint_names'],e['q_rad']))
            pending = list(joints)
            while pending:
                progressed = []
                for spec in pending:
                    name,parent,child,origin,axis = spec
                    if parent not in poses:
                        continue
                    move = np.eye(4)
                    move[:3,:3] = rodrigues(axis,qmap.get(name,0))
                    poses[child] = poses[parent]@origin@move
                    progressed.append(spec)
                assert progressed
                pending = [p for p in pending if all(p is not done for done in progressed)]
            fk_max = max(fk_max,max(float(abs(poses[n]-actual[n]).max()) for n in e['body_names']))
        results.append(dict(case=summary['case'],passed=summary['passed'],directions=directions))
    assert fk_max < 1e-5
    assert report['all_selected_cases_passed'] == all(c['passed'] for c in report['cases'])
    expected_statuses = (
        {'self_weight_axes_verified', 'self_weight_gain_trial_verified',
         'left_knee_kp30_verified', 'calibrated_precision_verified'}
        if report['all_selected_cases_passed'] else
        {'self_weight_axes_completed_precision_unmet', 'self_weight_gain_trial_completed_precision_unmet',
         'left_knee_kp30_precision_unmet', 'calibrated_precision_completed_unmet'})
    assert report['status'] in expected_statuses, 'unsupported or inconsistent report status'
    return dict(passed=True, cases=results, steps=report['steps_completed'],
                independent_actor_fk_max_error=fk_max, max_contact_n=contact_max,
                max_velocity_fraction=velocity_ratio_max,
                reconstructed_pd_delta_nm=reconstructed_delta_max,
                report_sha256=sha256_file(report_path), source_sha256=report['code_sha256'])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output is not None and (args.output.exists() or not args.output.parent.is_dir()):
        parser.error('output must be fresh and its parent must exist')
    result = audit(args.report.resolve())
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output is not None:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(payload)
    print(payload, end='')


if __name__ == '__main__':
    main()
