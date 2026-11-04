# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline FK: which leg joint can change the shank tilt, and by how much; no simulation.

Shank axis = elbow/knee link -> foot link, tilt measured from world -Z with the base upright
(identity root, chest/neck/tail at zero). ``fore_aft``/``lateral`` are arcsin of the unit
shank-axis X/Y components, ``total`` the angle from -Z; all radians. Joint limits come from the
URDF, the same range the v7 action clip uses. Geometry only: no contact, dynamics, or claim about
what the policy does.
"""

import argparse
import itertools
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "verify"))
import check_self_collision as geometry  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
DEFAULT_URDF = REPO / "rl_exp/lizard2_round_feet/lizard2_round_feet.urdf"
DEFAULT_OUT = REPO / "rl_exp/out/lizard2_shank_tilt/reach01/result.json"
LEGS = {"lf": ("shoulder", "elbow", "wrist"), "rf": ("shoulder", "elbow", "wrist"),
        "rl": ("hip", "knee", "ankle"), "rr": ("hip", "knee", "ankle")}
ROLES = ("swing", "abduct", "twist", "bend")


def leg_spec(leg):
    root, bend, foot = LEGS[leg]
    names = [f"{leg}_{root}_swing_joint", f"{leg}_{root}_abduct_joint", f"{leg}_{root}_twist_joint",
             f"{leg}_{bend}_joint"]
    return names, f"{leg}_{bend}", f"{leg}_{foot}"


def tilt(joints, leg, q):
    """(fore_aft, lateral) tilt of the shank from vertical, radians."""
    _, shank, foot = leg_spec(leg)
    top = geometry.fk(joints, shank, q)[:3, 3]
    d = geometry.fk(joints, foot, q)[:3, 3] - top
    d = d / np.linalg.norm(d)
    return float(np.arcsin(d[0])), float(np.arcsin(d[1])), float(np.arccos(-d[2]))


def analyse(joints, leg, steps=11):
    names, _, _ = leg_spec(leg)
    lims = [joints[n]["limits"] for n in names]
    grid = [np.linspace(lo, hi, steps) for lo, hi in lims]
    fa, la, tt = [], [], []
    for combo in itertools.product(*grid):
        f, l, t = tilt(joints, leg, dict(zip(names, combo)))
        fa.append(f)
        la.append(l)
        tt.append(t)
    h = 1e-3
    sens = {}
    for role, n in zip(ROLES, names):
        up, dn = tilt(joints, leg, {n: h}), tilt(joints, leg, {n: -h})
        sens[role] = [(up[0] - dn[0]) / (2 * h), (up[1] - dn[1]) / (2 * h)]
    swing, abduct, twist, bend = names

    def best_swing_only(q0):
        """Smallest total tilt reachable by sweeping swing alone from pose q0."""
        lo, hi = joints[swing]["limits"]
        return min(tilt(joints, leg, {**q0, swing: s})[2] for s in np.linspace(lo, hi, 61))

    start = {}
    for label, q0 in (("lateral_tilted(abduct=0.4)", {abduct: 0.4}), ("fore_aft_tilted(twist=0.3)", {twist: 0.3})):
        start[label] = {"tilt_before": tilt(joints, leg, q0)[2],
                        "tilt_after_swing_only": best_swing_only(q0)}
    return {"joints": dict(zip(ROLES, names)),
            "sens_rad_per_rad[fore_aft,lateral]": sens,
            "reach_fore_aft_rad": [min(fa), max(fa)], "reach_lateral_rad": [min(la), max(la)],
            "reach_total_tilt_rad": [min(tt), max(tt)],
            "swing_only_recovery": start}


def selfcheck(joints):
    """Break the model on purpose: a swing axis not vertical must change swing's fore-aft sensitivity."""
    names, _, _ = leg_spec("lf")
    base = analyse(joints, "lf", steps=3)["sens_rad_per_rad[fore_aft,lateral]"]["swing"]
    bent = {k: dict(v) for k, v in joints.items()}
    bent[names[0]]["axis"] = np.array([0.0, 1.0, 0.0])
    changed = analyse(bent, "lf", steps=3)["sens_rad_per_rad[fore_aft,lateral]"]["swing"]
    assert max(abs(np.array(base) - np.array(changed))) > 0.1, (base, changed)


def analyse_poses(joints, report):
    """Compare sampled live link poses and axes with URDF FK; angles [rad], positions [m]."""
    from scipy.spatial.transform import Rotation

    rows = []
    for sample in report['pose_samples_env0']:
        q = sample['joint_pos_rad']
        positions = sample['body_pos_w_m']
        root = np.eye(4)
        root[:3, :3] = Rotation.from_quat(sample['body_quat_w_xyzw']['base_link']).as_matrix()
        root[:3, 3] = positions['base_link']
        frames = {name: root @ geometry.fk(joints, name, q) for name in positions}
        position_error = max(float(np.linalg.norm(frame[:3, 3] - positions[name])) for name, frame in frames.items())
        axis_error = max(float(np.linalg.norm(frames[joints[name]['child']][:3, :3] @
                                             (joints[name]['axis'] / np.linalg.norm(joints[name]['axis'])) - axis))
                         for name, axis in sample['joint_axes_w'].items())
        legs = {}
        for leg in LEGS:
            names, shank, foot = leg_spec(leg)
            direction = frames[foot][:3, 3] - frames[shank][:3, 3]
            direction /= np.linalg.norm(direction)
            swing = names[0]
            sweep = []
            for angle in np.linspace(*joints[swing]['limits'], 61):
                altered = {**q, swing: angle}
                vector = root[:3, :3] @ (geometry.fk(joints, foot, altered)[:3, 3] -
                                        geometry.fk(joints, shank, altered)[:3, 3])
                sweep.append(float(np.arccos(np.clip(-vector[2] / np.linalg.norm(vector), -1, 1))))
            role_zero = {}
            for name in names:
                altered = {**q, name: 0.0}
                vector = root[:3, :3] @ (geometry.fk(joints, foot, altered)[:3, 3] -
                                        geometry.fk(joints, shank, altered)[:3, 3])
                role_zero[name] = float(np.arccos(np.clip(-vector[2] / np.linalg.norm(vector), -1, 1)))
            legs[leg] = {'foot_z_m': positions[foot][2], 'stance_proxy': positions[foot][2] < 0.10,
                         'role_to_zero_tilt_rad': role_zero,
                         'tilt_rad': float(np.arccos(np.clip(-direction[2], -1, 1))),
                         'fore_aft_rad': float(np.arcsin(np.clip(direction[0], -1, 1))),
                         'lateral_rad': float(np.arcsin(np.clip(direction[1], -1, 1))),
                         'best_swing_only_rad': min(sweep),
                         'foot_relative_base_m': (root[:3, :3].T @
                                                  (np.array(positions[foot]) - root[:3, 3])).tolist()}
        rows.append({'time_s': sample['time_s'], 'max_fk_position_error_m': position_error,
                     'max_fk_axis_error': axis_error, 'legs': legs})
    assert rows, 'no live pose samples'
    return {'samples': rows, 'max_fk_position_error_m': max(r['max_fk_position_error_m'] for r in rows),
            'max_fk_axis_error': max(r['max_fk_axis_error'] for r in rows),
            'scope': 'sampled env 0, fixed remaining joints/root during swing sweeps; no support/collision verdict'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--urdf", type=Path, default=DEFAULT_URDF)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument('--pose_report', type=Path, help='live pose samples from lizard2_shank_use_probe')
    p.add_argument("--steps", type=int, default=11)
    args = p.parse_args()
    assert not args.out.exists(), 'output already exists'
    tree = ET.parse(args.urdf).getroot()
    assert all(np.allclose(np.fromstring(n.get('rpy', '0 0 0'), sep=' '), 0) for n in tree.findall('joint/origin'))
    joints = geometry.load_urdf(args.urdf.resolve())["joints"]
    selfcheck(joints)
    if args.pose_report:
        report = json.loads(args.pose_report.read_text(encoding='utf-8'))
        result = analyse_poses(joints, report)
        result['source_pose_report'] = str(args.pose_report)
        broken = {name: dict(spec) for name, spec in joints.items()}
        broken['lf_shoulder_swing_joint']['axis'] = np.array([0.0, 1.0, 0.0])
        negative = analyse_poses(broken, report)
        assert negative['max_fk_axis_error'] > result['max_fk_axis_error'] + 0.1
        result['axis_negative_control_max_error'] = negative['max_fk_axis_error']
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('LIVE_FK', result['max_fk_position_error_m'], result['max_fk_axis_error'])
        return
    result = {"urdf": str(args.urdf), "steps": args.steps, "legs": {l: analyse(joints, l, args.steps) for l in LEGS}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    for leg, r in result["legs"].items():
        print(leg, "sens", {k: [round(x, 3) for x in v] for k, v in r["sens_rad_per_rad[fore_aft,lateral]"].items()})
        print(leg, "reach fore_aft", [round(x, 3) for x in r["reach_fore_aft_rad"]], "lateral",
              [round(x, 3) for x in r["reach_lateral_rad"]], "total", [round(x, 3) for x in r["reach_total_tilt_rad"]])
        print(leg, "swing-only", {k: [round(v["tilt_before"], 3), round(v["tilt_after_swing_only"], 3)]
                                  for k, v in r["swing_only_recovery"].items()})


if __name__ == "__main__":
    main()
