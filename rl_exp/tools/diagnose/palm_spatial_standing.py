# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Short free-base standing and single-leg lift diagnostics [m, s, rad, N, N*m]."""
import argparse
import ast
import copy
import difflib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

import numpy as np
import palm_spatial_runtime as wiring
from palm_spatial_inertia import csc, _rotation
from palm_spatial_tracking import _entity_snapshot

SETTINGS = dict(dt_s=.005, duration_s=5., start_clearance_m=.001, stop_drop_m=.15,
                stop_tilt_rad=.35, stop_joint_rad=.35, stop_forbidden_ground_n=5.,
                standing_drop_m=.02, standing_tilt_rad=.1, standing_joint_rad=.1,
                standing_vertical_speed_m_s=.05, foot_load_n=5., weight_relative_error=.2,
                max_calibration_variants=3)

LIFT_SETTINGS = dict(settle_s=5., rise_s=3., hold_s=2., fall_s=3., recover_s=3.,
                     minimum_clearance_m=.01, unloaded_force_n=1., landing_height_m=.005,
                     minimum_mesh_height_m=-.005, max_tracking_error_rad=.1,
                     geometry_samples=33, max_physical_attempts=3)


def _lift_fraction(t):
    start = LIFT_SETTINGS['settle_s']
    top = start + LIFT_SETTINGS['rise_s']
    down = top + LIFT_SETTINGS['hold_s']
    end = down + LIFT_SETTINGS['fall_s']
    if t <= start or t >= end:
        return 0.
    if t >= top and t <= down:
        return 1.
    u = (t-start)/LIFT_SETTINGS['rise_s'] if t < top else (end-t)/LIFT_SETTINGS['fall_s']
    return u**3*(10-15*u+6*u*u)


def _make_lift_plan(standing_path, pose_path, leg, out):
    import local_path_check as check
    from scipy.spatial import ConvexHull
    import xml.etree.ElementTree as ET
    standing = json.loads(standing_path.read_text(encoding='utf-8'))
    source = json.loads(pose_path.read_text(encoding='utf-8'))
    assert standing['completed'] and standing['status'] == 'standing_verified'
    assert source['legs']['combined']['completed_combined_loop']
    assert source['identity']['candidate_files_sha256']['palm_spatial.urdf'] == wiring.URDF_HASH
    foot = standing['target']['end_links'][leg]
    selected = max(source['legs']['combined']['rows'], key=lambda row: row['geometry']['ground_by_link'][foot]['height_m'])
    assert not selected['failures'] and selected['geometry']['ground_by_link'][foot]['height_m'] > LIFT_SETTINGS['minimum_clearance_m']
    build, models, model, zero, collision, excluded, root, *_ = check.probe._static_prepare(Path(source['identity']['build_report']))
    target = {n: (float(selected['q_rad'][n]) if n.startswith(leg+'_') else 0.) for n in zero}
    geometry = []
    for fraction in np.linspace(0, 1, LIFT_SETTINGS['geometry_samples']):
        q = {n: value*float(fraction) for n, value in target.items()}
        state = check._body_state(q, root, model, collision)
        assert not state['limit_failures'] and not state['solid_pairs'], 'single-leg bridge geometry failed'
        assert state['all_ground_min_m'] >= -source['source_config']['position_tolerance_m'], 'single-leg bridge penetrates'
        chain = np.array([q[n] for n in models[leg].names])
        _, normal = models[leg].sole(chain)
        assert (root[:3,:3] @ normal)[2] > 0, 'flipped palm'
        bend = models[leg].names.index(build['definitions'][leg]['bend']+'_joint')
        straight = check.probe.reach.straight_hfe(models[leg].chain)
        assert chain[bend]*np.sign(straight) < abs(straight), 'reverse bend'
        geometry.append(dict(fraction=float(fraction), **state))
    # Existing actual loaded posture, excluding the leg about to lift.
    entities = standing['final_entities']
    links = {p.get('name'): p for p in ET.parse(standing['target']['urdf']).getroot().findall('link')}
    points, mass, com = [], 0., np.zeros(3)
    for name, pose in zip(entities['body_names'], entities['actor_poses_xyzw']):
        rotation, position = _rotation(pose[3:]), np.array(pose[:3])
        link = links[name]
        weight = float(link.find('inertial/mass').get('value'))
        center = np.fromstring(link.find('inertial/origin').get('xyz'), sep=' ')
        mass += weight
        com += weight*(rotation@center+position)
        force = standing['samples'][-1]['ground_forces_n'].get(name, [0,0,0])
        if name != foot and force[2] >= SETTINGS['foot_load_n']:
            cloud = csc.read_obj(model['links'][name]['collision']) @ rotation.T + position
            points.extend(cloud[cloud[:,2] <= cloud[:,2].min()+.005, :2].tolist())
    com /= mass
    hull = ConvexHull(np.array(points))
    margin = -float(np.max(hull.equations[:,:2]@com[:2]+hull.equations[:,2]))
    assert margin > 0, 'remaining contact hull does not contain COM projection'
    out = out.resolve()
    assert wiring.REPO / 'rl_exp/out' in out.parents and not out.exists()
    out.mkdir(parents=True)
    plan = dict(leg=leg, foot=foot, standing_report=str(standing_path.resolve()),
                standing_report_sha256=wiring.binding.sha256_file(standing_path),
                pose_report=str(pose_path.resolve()), pose_report_sha256=wiring.binding.sha256_file(pose_path),
                code_sha256=wiring.binding.sha256_file(Path(__file__)), source_c=selected['s'],
                target_q_rad=target, lift_settings=LIFT_SETTINGS, geometry=geometry,
                remaining_contact_hull_margin_m=margin, loaded_com_m=com.tolist(),
                support_scope='geometry of near-bottom vertices on actually loaded bodies; no force distribution or stability proof')
    wiring.write_json(out/'plan.json', plan)
    print('LIFT_PLAN_READY', leg, 'target_clearance', geometry[-1]['ground_by_link'][foot]['height_m'], 'support_margin', margin)


def _load_lift_plan(path):
    plan = json.loads(path.read_text(encoding='utf-8'))
    standing_path = Path(plan['standing_report'])
    assert wiring.binding.sha256_file(standing_path) == plan['standing_report_sha256']
    assert plan['lift_settings'] == LIFT_SETTINGS
    prior, manifest, model = _load_standing(standing_path)
    if 'keyframes' in plan:
        assert all(set(frame['q_rad']) == set(prior['joint_names']) for frame in plan['keyframes'])
        assert all(q == 0. for frame in (plan['keyframes'][0], plan['keyframes'][-1]) for q in frame['q_rad'].values())
    return plan, prior, manifest, model


def _load_standing(path):
    prior = json.loads(path.read_text(encoding='utf-8'))
    assert prior['completed'] and prior['status'] == 'standing_verified'
    manifest = Path(prior['manifest'])
    assert wiring.binding.sha256_file(manifest) == prior['manifest_sha256']
    assert wiring.binding.sha256_file(Path(prior['target']['urdf'])) == wiring.URDF_HASH
    return prior, manifest, csc.load_urdf(Path(prior['target']['urdf']))


def _posture_verdict(samples, windows):
    maxima = {}
    for name, (start, end) in windows.items():
        rows = [s for s in samples if start <= s['t_s'] <= end]
        maxima[name] = max((s['chest_tilt_rad'] for s in rows), default=None)
    return dict(max_chest_tilt_rad=maxima)


def _lift_target(t, plan):
    if 'keyframes' not in plan:
        return {n: _lift_fraction(t)*q for n, q in plan['target_q_rad'].items()}
    frames = plan['keyframes']
    assert frames[0]['t_s'] == 0 and frames[-1]['t_s'] == plan['duration_s']
    for before, after in zip(frames, frames[1:]):
        assert before['t_s'] < after['t_s']
        if t <= after['t_s']:
            u = np.clip((t-before['t_s'])/(after['t_s']-before['t_s']), 0., 1.)
            f = u**3*(10-15*u+6*u*u)
            return {n: float(q+f*(after['q_rad'][n]-q)) for n, q in before['q_rad'].items()}
    return frames[-1]['q_rad'].copy()


def _lift_verdict(samples, plan, feet, weight):
    hold_start = LIFT_SETTINGS['settle_s'] + LIFT_SETTINGS['rise_s']
    hold_end = hold_start + LIFT_SETTINGS['hold_s']
    duration = sum(LIFT_SETTINGS[k] for k in ('settle_s', 'rise_s', 'hold_s', 'fall_s', 'recover_s'))
    windows = plan.get('windows', dict(hold=[hold_end-1, hold_end], recovery=[duration-1, duration],
                                     baseline=[LIFT_SETTINGS['settle_s']-1, LIFT_SETTINGS['settle_s']]))
    select = lambda key: [s for s in samples if windows[key][0] <= s['t_s'] <= windows[key][1]]
    hold, recovery, baseline = select('hold'), select('recovery'), select('baseline')
    foot = plan['foot']
    def stable(rows, loaded):
        return bool(rows) and all(
            s['root_drop_m'] <= SETTINGS['standing_drop_m'] and s['tilt_rad'] <= SETTINGS['standing_tilt_rad']
            and max(abs(np.array(s['q_rad'])-s['target_q_rad'])) <= LIFT_SETTINGS['max_tracking_error_rad']
            and abs(s['root_velocity'][2]) <= SETTINGS['standing_vertical_speed_m_s']
            and all(s['ground_forces_n'][n][2] >= SETTINGS['foot_load_n'] for n in loaded) for s in rows)
    checks = dict(baseline_stable=stable(baseline, feet),
                  actual_clearance=bool(hold) and min(s['lifted_mesh_min_m'] for s in hold) >= LIFT_SETTINGS['minimum_clearance_m'],
                  actual_unloaded=bool(hold) and max(np.linalg.norm(s['ground_forces_n'][foot]) for s in hold) <= LIFT_SETTINGS['unloaded_force_n'],
                  supported_hold=stable(hold, [n for n in feet if n != foot]),
                  recovered_stance=stable(recovery, feet),
                  returned_to_ground=bool(recovery) and max(s['lifted_mesh_min_m'] for s in recovery) <= LIFT_SETTINGS['landing_height_m'],
                  no_deep_mesh_penetration=min(s['lifted_mesh_min_m'] for s in samples) >= LIFT_SETTINGS['minimum_mesh_height_m'])
    mean_support = float(np.mean([sum(f[2] for f in s['ground_forces_n'].values()) for s in recovery])) if recovery else None
    checks['recovered_weight_balance'] = mean_support is not None and abs(mean_support-weight) <= SETTINGS['weight_relative_error']*weight
    transfer_force = None
    if 'transfer' in windows:
        transfer = select('transfer')
        baseline_force = float(np.mean([s['ground_forces_n'][foot][2] for s in baseline])) if baseline else 0.
        transfer_force = float(np.mean([s['ground_forces_n'][foot][2] for s in transfer])) if transfer else None
        checks['transferred_load'] = bool(transfer) and baseline_force > SETTINGS['foot_load_n'] and transfer_force < .75*baseline_force
    checks = {name: bool(value) for name, value in checks.items()}
    return dict(checks=checks, passed=all(checks.values()),
                hold_min_clearance_m=min((s['lifted_mesh_min_m'] for s in hold), default=None),
                hold_max_ground_force_n=max((float(np.linalg.norm(s['ground_forces_n'][foot])) for s in hold), default=None),
                recovery_mean_support_n=mean_support, transfer_mean_lifted_foot_force_n=transfer_force)


def _self_check(break_failure_handler=False):
    assert _posture_verdict([], {'standing': [4., 5.]}) == dict(max_chest_tilt_rad={'standing': None})
    assert [_lift_fraction(t) for t in (0, 5, 8, 10, 13, 16)] == [0, 0, 1, 1, 0, 0]
    feet, rows = ['lf', 'rf', 'rl', 'rr'], []
    for t in (4.5, 9.5, 15.5):
        hold = t == 9.5
        rows.append(dict(t_s=t, q_rad=[0.], target_q_rad=[0.], root_drop_m=0., tilt_rad=0.,
                         root_velocity=[0.]*6, lifted_mesh_min_m=.02 if hold else 0.,
                         ground_forces_n={n: [0., 0., 0. if hold and n == 'lf' else 50.] for n in feet}))
    verdict = _lift_verdict(rows, {'foot': 'lf'}, feet, 200.)
    assert verdict['passed']
    json.dumps(verdict)  # NumPy booleans must not break persistence.
    missing_clearance = copy.deepcopy(rows)
    missing_clearance[1]['lifted_mesh_min_m'] = 0.
    assert not _lift_verdict(missing_clearance, {'foot': 'lf'}, feet, 200.)['passed']
    still_loaded = copy.deepcopy(rows)
    still_loaded[1]['ground_forces_n']['lf'] = [0., 0., 5.]
    assert not _lift_verdict(still_loaded, {'foot': 'lf'}, feet, 200.)['passed']
    assert not _lift_verdict(rows[:2], {'foot': 'lf'}, feet, 200.)['passed']
    timed = dict(keyframes=[dict(t_s=0., q_rad={'j': 0.}), dict(t_s=3., q_rad={'j': 1.}),
                           dict(t_s=6., q_rad={'j': 0.})], duration_s=6.)
    assert [_lift_target(t, timed)['j'] for t in (0., 1.5, 3., 4.5, 6.)] == [0., .5, 1., .5, 0.]
    transfer_rows = copy.deepcopy(rows)
    transfer_rows[1]['t_s'], transfer_rows[2]['t_s'] = 12.5, 21.5
    transfer = copy.deepcopy(transfer_rows[0])
    transfer['t_s'] = 7.5
    transfer['ground_forces_n']['lf'][2] = 25.
    transfer_rows.insert(1, transfer)
    transfer_plan = dict(foot='lf', windows=dict(baseline=[4., 5.], transfer=[7., 8.], hold=[12., 13.], recovery=[21., 22.]))
    assert _lift_verdict(transfer_rows, transfer_plan, feet, 200.)['passed']
    transfer_rows[1]['ground_forces_n']['lf'][2] = 50.
    assert not _lift_verdict(transfer_rows, transfer_plan, feet, 200.)['passed']
    syntax = ast.parse(Path(__file__).read_text(encoding='utf-8'))
    run = next(n for n in syntax.body if isinstance(n, ast.FunctionDef) and n.name == '_run')
    body = next(n for n in run.body if isinstance(n, ast.Try)).body
    loop = next(n for n in body if isinstance(n, ast.For) and ast.unparse(n.target) == 'step')
    chest = next(n for n in loop.body if isinstance(n, ast.Assign)
                 and ast.unparse(n.targets[0]) == "row['chest_tilt_rad']")
    # Execute production pre-lift/safety branches and final decisions without simulation.
    replay = ast.parse("for row in result['samples']:\n t = row['t_s']\n q = np.array(row['q_rad'])\n desired = np.array(row['target_q_rad'])\n root_pose = np.zeros(7)\n tilt = row['tilt_rad']\n forbidden = row['forbidden_ground_n']").body[0]
    replay.body.extend(loop.body[loop.body.index(chest)+1:])
    start = next(n for n in body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'late')
    end = next(n for n in body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
               and ast.unparse(n.value.func) == 'wiring.write_json')
    decisions = compile(ast.fix_missing_locations(ast.Module(
        body=[replay]+body[body.index(start):body.index(end)], type_ignores=[])), __file__, 'exec')
    from types import SimpleNamespace
    for lifting in (False, True):
        samples = copy.deepcopy(rows if lifting else [rows[0]])
        samples.insert(1, dict(copy.deepcopy(samples[0]), t_s=5.))
        for row in samples:
            row.update(chest_tilt_rad=float(np.radians(2.)), forbidden_ground_n=0.)
        def decide(state, stop=None):
            scope = dict(globals(), args=SimpleNamespace(lift_plan=lifting), require_posture=True,
                         result=dict(samples=state), stop=stop, duration=16. if lifting else 5.,
                         feet=feet, weight=200., robot=None, model=None, plan={'foot': 'lf'},
                         _entity_snapshot=lambda *_: {})
            exec(decisions, scope)
            return scope['passed'], scope['result']
        passed, result = decide(samples)
        assert passed, ('benign chest tilt rejected', lifting, result)
        assert result['status'] == ('single_leg_lift_verified' if lifting else 'standing_verified')
        assert max(result['posture_verdict']['max_chest_tilt_rad'].values()) == float(np.radians(2.))
        for field, value in (('root_drop_m', .03), ('tilt_rad', .11), ('q_rad', [.11]),
                             ('root_velocity', [0., 0., .06, 0., 0., 0.]),
                             ('forbidden_ground_n', 6.)):
            unstable = copy.deepcopy(samples)
            unstable[-1][field] = value
            assert not decide(unstable)[0], (lifting, field)
        unsupported = copy.deepcopy(samples)
        unsupported[-1]['ground_forces_n']['rf'][2] = 0.
        assert not decide(unsupported)[0], ('missing support', lifting)
        assert not decide(samples, ['root_drop'])[0]
    # Exercise the real exception suite in a child process, even if persistence itself fails.
    handler = next(n for n in run.body if isinstance(n, ast.Try)).handlers[0]
    if break_failure_handler:
        guarded = next(n for n in handler.body if isinstance(n, ast.Try))
        handler.body = handler.body[:handler.body.index(guarded)] + guarded.body + guarded.finalbody
    fixture = ast.parse('try:\n raise ValueError("primary diagnostic error")\nexcept BaseException as error:\n pass\nfinally:\n app.close()').body[0]
    fixture.handlers = [handler]
    suite = ast.unparse(ast.fix_missing_locations(ast.Module(body=[fixture], type_ignores=[])))
    setup = ('import os,sys,traceback\nfrom pathlib import Path\nfrom types import SimpleNamespace\n'
             'result={}\nout=Path(".")\n'
             'def fail_write(*args): raise OSError("injected persistence error")\n'
             'def close():\n print("APP_CLOSE_REACHED",flush=True)\n sys.exit(0)\n'
             'wiring=SimpleNamespace(write_json=fail_write)\napp=SimpleNamespace(close=close)\n')
    child = subprocess.run([sys.executable, '-B', '-'], input=setup+suite, text=True, capture_output=True)
    assert child.returncode == 1 and 'APP_CLOSE_REACHED' not in child.stdout, 'failure exit swallowed'
    assert 'primary diagnostic error' in child.stderr and 'injected persistence error' in child.stderr
    print('STANDING_LIFT_SELF_CHECK_OK')


def _prepare(report, out, leg_frequency_hz, neck_frequency_hz):
    from pxr import Usd, UsdPhysics
    prior = json.loads(report.read_text(encoding='utf-8'))
    assert prior['completed'] and prior['status'] == 'combined_tracking_verified'
    manifest = Path(prior['tracking_manifest'])
    assert wiring.binding.sha256_file(manifest) == prior['tracking_manifest_sha256']
    doc = json.loads(manifest.read_text(encoding='utf-8'))
    old_usd, old_urdf = Path(doc['target']), Path(doc['urdf'])
    assert wiring.binding.sha256_file(old_usd) == doc['sha256']['target']
    assert wiring.binding.sha256_file(old_urdf) == wiring.URDF_HASH
    model = csc.load_urdf(old_urdf)
    minima = {}
    for name, link in model['links'].items():
        if link['collision']:
            pose = csc.fk(model['joints'], name, {})
            vertices = csc.read_obj(link['collision']) @ pose[:3, :3].T + pose[:3, 3]
            minima[name] = float(vertices[:, 2].min())
    height = -min(minima.values()) + SETTINGS['start_clearance_m']
    stage = Usd.Stage.Open(str(old_usd))
    original = stage.GetRootLayer().ExportToString()
    fixed = [UsdPhysics.FixedJoint(p) for p in stage.Traverse() if p.IsA(UsdPhysics.FixedJoint)
             and (not UsdPhysics.FixedJoint(p).GetBody0Rel().GetTargets()
                  or not UsdPhysics.FixedJoint(p).GetBody1Rel().GetTargets())]
    assert len(fixed) == 1 and not fixed[0].GetJointEnabledAttr().HasAuthoredValueOpinion()
    fixed[0].GetJointEnabledAttr().Set(False)
    text = stage.GetRootLayer().ExportToString()
    stripped, count = re.subn(r'(?m)^[ \t]*(?:uniform )?bool physics:jointEnabled = (?:false|0)\n', '', text)
    assert count == 1 and stripped == original, '\n'.join(difflib.unified_diff(original.splitlines(), text.splitlines()))
    (out / 'palm_spatial.usda').write_text(text, encoding='utf-8')
    shutil.copyfile(old_urdf, out / 'palm_spatial.urdf')
    shutil.copytree(old_usd.parent / 'meshes', out / 'meshes')
    new_manifest = out / 'standing_manifest.json'
    doc['target_binding'].update(target=str(out/'palm_spatial.usda'), urdf=str(out/'palm_spatial.urdf'), source=str(new_manifest))
    for key in ('target', 'urdf'):
        doc[key] = doc['target_binding'][key]
        doc['sha256'][key] = wiring.binding.sha256_file(Path(doc[key]))
    doc['config']['scene.robot.init_state.pos'] = [0., 0., height]
    doc['config']['scene.robot.spawn.rigid_props.disable_gravity'] = False
    for field, power in (('stiffness', 2), ('damping', 1)):
        key = f'scene.robot.actuators.legs.{field}'
        doc['config'][key] = {n: v*leg_frequency_hz**power for n, v in doc['config'][key].items()}
        neck_key = f'scene.robot.actuators.spine.{field}'
        doc['config'][neck_key]['neck_pitch_joint'] *= neck_frequency_hz**power
    doc['standing_adapter'] = dict(prior_manifest=str(manifest), prior_manifest_sha256=wiring.binding.sha256_file(manifest),
                                  world_fixed_joint=str(fixed[0].GetPath()), only_joint_enabled_delta_verified=True,
                                  root_height_m=height, neutral_mesh_minima_m=minima,
                                  leg_frequency_hz=leg_frequency_hz, neck_frequency_hz=neck_frequency_hz, damping_ratio=1.)
    wiring.write_json(new_manifest, doc)
    return prior, new_manifest, model, doc['standing_adapter']


def _run(args):
    out = args.out.resolve()
    assert wiring.REPO / 'rl_exp/out' in out.parents and not out.exists()
    out.mkdir(parents=True)
    shutil.copyfile(__file__, out/'source.py')
    input_path = args.lift_plan or args.standing_reference or args.tracking_report
    result = dict(completed=False, stage='startup', settings=SETTINGS,
                  input={str(input_path): wiring.binding.sha256_file(input_path)},
                  code_sha256=wiring.binding.sha256_file(Path(__file__)), samples=[])
    app, env = None, None
    try:
        from isaaclab.app import AppLauncher
        app = AppLauncher(args).app
        import gymnasium as gym
        import torch
        import warp as wp
        import rl_exp.tasks
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from isaaclab_physx.physics import PhysxManager
        from pxr import Usd, UsdPhysics
        from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg, joint_reset_errors
        if args.lift_plan:
            assert args.leg_frequency_hz in (None, 6., 12.) and args.neck_frequency_hz == 1 and not args.load_reference and not args.neck_load_reference
            plan, prior, manifest, model = _load_lift_plan(args.lift_plan)
            adapter = copy.deepcopy(prior['standing_adapter'])
            lift_leg_scale = (args.leg_frequency_hz or adapter['leg_frequency_hz'])/adapter['leg_frequency_hz']
            if args.wrist_frequency_hz != 1 or lift_leg_scale != 1:
                document = json.loads(manifest.read_text(encoding='utf-8'))
                for field, power in (('stiffness', 2), ('damping', 1)):
                    key = f'scene.robot.actuators.feet.{field}'
                    document['config'][key] = {n: value*(args.wrist_frequency_hz**power if n.endswith('wrist_joint') else 1)
                                               for n, value in document['config'][key].items()}
                    leg_key = f'scene.robot.actuators.legs.{field}'
                    document['config'][leg_key] = {n: value*lift_leg_scale**power for n, value in document['config'][leg_key].items()}
                adapter['wrist_frequency_hz'] = args.wrist_frequency_hz
                adapter['leg_frequency_hz'] *= lift_leg_scale
                document['standing_adapter'] = adapter
                document['lift_gain_source'] = dict(manifest=str(manifest), sha256=wiring.binding.sha256_file(manifest))
                manifest = out/'lift_manifest.json'
                document['target_binding']['source'] = str(manifest)
                wiring.write_json(manifest, document)
            result.update(lift_plan=plan, lift_settings=LIFT_SETTINGS)
        elif args.standing_reference:
            prior, manifest, model = _load_standing(args.standing_reference)
            adapter = copy.deepcopy(prior['standing_adapter'])
        elif args.leg_frequency_hz != 1:
            assert args.leg_frequency_hz == 6 and args.load_reference
            load = json.loads(args.load_reference.read_text(encoding='utf-8'))
            assert load['completed'] and load['status'] == 'standing_failed' and load['stop_reason'] == ['joint_motion']
            result['input'][str(args.load_reference)] = wiring.binding.sha256_file(args.load_reference)
        if args.tracking_report and args.neck_frequency_hz != 1:
            assert args.neck_frequency_hz == 2 and args.neck_load_reference and args.leg_frequency_hz == 6
            neck_load = json.loads(args.neck_load_reference.read_text(encoding='utf-8'))
            assert neck_load['completed'] and neck_load['status'] == 'standing_failed' and neck_load['stop_reason'] is None
            late_q = np.array([s['q_rad'] for s in neck_load['samples'] if s['t_s'] >= 4])
            bad = [n for n, value in zip(neck_load['joint_names'], abs(late_q).max(axis=0)) if value > SETTINGS['standing_joint_rad']]
            assert bad == ['neck_pitch_joint']
            result['input'][str(args.neck_load_reference)] = wiring.binding.sha256_file(args.neck_load_reference)
        if args.tracking_report:
            prior, manifest, model, adapter = _prepare(args.tracking_report, out, args.leg_frequency_hz, args.neck_frequency_hz)
        chest_scale = (args.chest_frequency_hz or adapter.get('chest_frequency_hz', 1.))/adapter.get('chest_frequency_hz', 1.)
        lf_wrist_scale = args.lf_wrist_frequency_hz/adapter.get('lf_wrist_frequency_hz', 1.)
        if chest_scale != 1 or lf_wrist_scale != 1:
            document = json.loads(manifest.read_text(encoding='utf-8'))
            document['posture_gain_source'] = dict(manifest=str(manifest), sha256=wiring.binding.sha256_file(manifest))
            for field, power in (('stiffness', 2), ('damping', 1)):
                document['config'][f'scene.robot.actuators.spine.{field}']['chest_pitch_joint'] *= chest_scale**power
                document['config'][f'scene.robot.actuators.feet.{field}']['lf_wrist_joint'] *= lf_wrist_scale**power
            adapter['chest_frequency_hz'] = args.chest_frequency_hz or adapter.get('chest_frequency_hz', 1.)
            adapter['lf_wrist_frequency_hz'] = args.lf_wrist_frequency_hz
            document['standing_adapter'] = adapter
            manifest = out/'posture_manifest.json'
            document['target_binding']['source'] = str(manifest)
            wiring.write_json(manifest, document)
        result.update(standing_adapter=adapter, manifest=str(manifest), manifest_sha256=wiring.binding.sha256_file(manifest))
        cfg = copy.deepcopy(resolve_task_cfg(wiring.REGISTERED_TASK))
        target = wiring.obs_protocol.load_diagnostic_target(manifest, cfg, wiring.REGISTERED_TASK)
        cfg.sim.device, cfg.sim.dt, cfg.seed = args.device, SETTINGS['dt_s'], 0
        assert cfg.scene.terrain.terrain_type == 'plane'
        result['runtime_overrides'] = {'sim.dt': cfg.sim.dt, 'sim.device': cfg.sim.device, 'seed': cfg.seed}
        env = gym.make(wiring.REGISTERED_TASK, cfg=cfg)
        wrapper = RslRlVecEnvWrapper(env, clip_actions=None)
        live, robot = env.unwrapped, env.unwrapped.scene['robot']
        assert not robot.is_fixed_base and not joint_reset_errors(robot)
        assert not live._physics_handles_decimation and live.physics_dt == SETTINGS['dt_s']
        names, body_names = list(robot.joint_names), list(robot.body_names)
        assert names == prior['joint_names']
        backend = lambda x: wp.to_torch(x).cpu().numpy()[0]
        kp, kd = backend(robot.root_view.get_dof_stiffnesses()), backend(robot.root_view.get_dof_dampings())
        expected_kp, expected_kd = np.array(prior['readbacks']['kp']), np.array(prior['readbacks']['kd'])
        leg_names = cfg.scene.robot.actuators['legs'].joint_names_expr
        for k, name in enumerate(names):
            if name in leg_names:
                scale = lift_leg_scale if args.lift_plan else (1. if args.standing_reference else args.leg_frequency_hz)
                expected_kp[k] *= scale**2
                expected_kd[k] *= scale
            elif name == 'neck_pitch_joint':
                expected_kp[k] *= args.neck_frequency_hz**2
                expected_kd[k] *= args.neck_frequency_hz
            elif name == 'chest_pitch_joint':
                expected_kp[k] *= chest_scale**2
                expected_kd[k] *= chest_scale
            if args.lift_plan and name.endswith('wrist_joint'):
                expected_kp[k] *= args.wrist_frequency_hz**2
                expected_kd[k] *= args.wrist_frequency_hz
            if name == 'lf_wrist_joint':
                expected_kp[k] *= lf_wrist_scale**2
                expected_kd[k] *= lf_wrist_scale
        assert np.allclose(kp, expected_kp, rtol=1e-6) and np.allclose(kd, expected_kd, rtol=1e-6)
        bodies = {p.GetName(): p for p in live.sim.stage.Traverse()
                  if p.HasAPI(UsdPhysics.RigidBodyAPI) and p.GetName() in body_names}
        assert set(bodies) == set(body_names)
        assert all(p.GetAttribute('physxRigidBody:disableGravity').Get() is False for p in bodies.values())
        ground = live.sim.stage.GetPrimAtPath(cfg.scene.terrain.prim_path)
        floors = [p for p in Usd.PrimRange(ground) if p.HasAPI(UsdPhysics.CollisionAPI)]
        assert len(floors) == 1, 'expected one actual floor collider'
        floor = str(floors[0].GetPath())
        views, mapping = {}, {}
        for name, prim in bodies.items():
            if not any(p.HasAPI(UsdPhysics.CollisionAPI) for p in Usd.PrimRange(prim)):
                continue
            path = str(prim.GetPath())
            view = PhysxManager.get_physics_sim_view().create_rigid_contact_view(path, filter_patterns=[floor], max_contact_data_count=256)
            wiring.pair_binding(view.sensor_paths, view.filter_paths, path, [floor], (view.sensor_count, view.filter_count, 3))
            views[name] = view
            mapping[name] = dict(body=path, floor=floor, sensor_paths=view.sensor_paths, filter_paths=view.filter_paths)
        assert len(views) == 18
        feet = list(target['end_links'].values())
        allowed = set(feet) | {n for n in views if n.startswith('tail')}
        mass = float(robot.data.body_mass.torch.sum())
        weight = mass * abs(cfg.sim.gravity[2])
        result.update(joint_names=names, body_names=body_names, target=target, ground_pair_mapping=mapping,
                      readbacks=dict(fixed_base=False, kp=kp.tolist(), kd=kd.tolist(), mass_kg=mass, gravity=cfg.sim.gravity,
                                     position_limits=robot.data.joint_pos_limits.torch[0].cpu().tolist(),
                                     velocity_caps=backend(robot.root_view.get_dof_max_velocities()).tolist(),
                                     effort_caps=robot.data.joint_effort_limits.torch[0].cpu().tolist()))
        result['initial_entities'] = _entity_snapshot(robot, model)
        zero = torch.zeros((1, live.action_manager.total_action_dim), device=args.device)
        action_names, action_ids = [], []
        for term_name in live.action_manager.active_terms:
            term = live.action_manager.get_term(term_name)
            ids = list(range(len(names)))[term._joint_ids] if isinstance(term._joint_ids, slice) else list(term._joint_ids)
            action_names.extend(term._joint_names)
            action_ids.extend(map(int, ids))
            assert np.all(torch.as_tensor(term._scale).cpu().numpy() == 1) and np.all(torch.as_tensor(term._offset).cpu().numpy() == 0)
        wiring.exact_channels(names, action_names, action_ids, names)
        result['action_names'] = action_names
        if args.lift_plan:
            assert set(plan['target_q_rad']) == set(names)
            lifted_vertices = csc.read_obj(model['links'][plan['foot']]['collision'])
            lifted_id = body_names.index(plan['foot'])
            duration = plan.get('duration_s', sum(LIFT_SETTINGS[k] for k in ('settle_s', 'rise_s', 'hold_s', 'fall_s', 'recover_s')))
        else:
            duration = SETTINGS['duration_s']
        start_z = float(robot.data.root_link_pose_w.torch[0, 2])
        chest_id = body_names.index('chest_pitch')
        stop = None
        for step in range(1, int(duration/SETTINGS['dt_s'])+1):
            t = step*SETTINGS['dt_s']
            desired = np.zeros(len(names))
            action = zero.clone()
            if args.lift_plan:
                target_q = _lift_target(t, plan)
                for k, name in enumerate(names):
                    desired[k] = target_q[name]
                    action[0, action_names.index(name)] = desired[k]
            live.action_manager.process_action(action)
            live.action_manager.apply_action()
            live.scene.write_data_to_sim()
            live.sim.step(render=False)
            live.scene.update(SETTINGS['dt_s'])
            q = robot.data.joint_pos.torch[0].cpu().numpy().copy()
            v = robot.data.joint_vel.torch[0].cpu().numpy().copy()
            root_pose = robot.data.root_link_pose_w.torch[0].cpu().numpy().copy()
            root_vel = robot.data.root_link_vel_w.torch[0].cpu().numpy().copy()
            forces = {n: wp.to_torch(view.get_contact_force_matrix(dt=SETTINGS['dt_s'])).cpu().numpy().reshape(3).tolist()
                      for n, view in views.items()}
            tilt = float(np.arccos(np.clip(_rotation(root_pose[3:])[2, 2], -1, 1)))
            forbidden = max(np.linalg.norm(f) for n, f in forces.items() if n not in allowed)
            row = dict(t_s=t, q_rad=q.tolist(), velocity_rad_s=v.tolist(), target_q_rad=desired.tolist(),
                       root_pose_xyzw=root_pose.tolist(), root_velocity=root_vel.tolist(), tilt_rad=tilt,
                       root_drop_m=start_z-float(root_pose[2]), ground_forces_n=forces,
                       forbidden_ground_n=float(forbidden), reconstructed_pd_request_nm=(kp*(desired-q)-kd*v).tolist())
            if args.lift_plan:
                actual = robot.data.body_link_pose_w.torch[0, lifted_id].cpu().numpy()
                row['lifted_mesh_min_m'] = float((lifted_vertices @ _rotation(actual[3:]).T + actual[:3])[:,2].min())
                if 'keyframes' not in plan:
                    row['lift_fraction'] = _lift_fraction(t)
                if 'sole_local_m' in plan:
                    row['sole_positions_w_m'] = {}
                    for leg, local in plan['sole_local_m'].items():
                        pose = robot.data.body_link_pose_w.torch[0, body_names.index(target['end_links'][leg])].cpu().numpy()
                        row['sole_positions_w_m'][leg] = (_rotation(pose[3:])@local+pose[:3]).tolist()
            result['samples'].append(row)
            chest_pose = robot.data.body_link_pose_w.torch[0, chest_id].cpu().numpy()
            row['chest_tilt_rad'] = float(np.arccos(np.clip(_rotation(chest_pose[3:])[2, 2], -1, 1)))
            assert np.isfinite(q).all() and np.isfinite(root_pose).all(), 'non-finite state'
            checks = {'root_drop': row['root_drop_m'] > SETTINGS['stop_drop_m'], 'root_tilt': tilt > SETTINGS['stop_tilt_rad'],
                      'joint_motion': abs(q-desired).max() > SETTINGS['stop_joint_rad'],
                      'forbidden_ground': forbidden > SETTINGS['stop_forbidden_ground_n']}
            if any(checks.values()):
                stop = [k for k, value in checks.items() if value]
                break
        late = [s for s in result['samples'] if s['t_s'] >= duration-1]
        passed = stop is None and bool(late) and all(
            s['root_drop_m'] <= SETTINGS['standing_drop_m'] and s['tilt_rad'] <= SETTINGS['standing_tilt_rad']
            and max(map(abs, s['q_rad'])) <= SETTINGS['standing_joint_rad']
            and abs(s['root_velocity'][2]) <= SETTINGS['standing_vertical_speed_m_s']
            and all(s['ground_forces_n'][n][2] >= SETTINGS['foot_load_n'] for n in feet)
            for s in late)
        mean_support = float(np.mean([sum(f[2] for f in s['ground_forces_n'].values()) for s in late])) if late else None
        passed = passed and abs(mean_support-weight) <= SETTINGS['weight_relative_error']*weight
        result.update(completed=True, stage='completed', status='standing_verified' if passed else 'standing_failed',
                      stop_reason=stop, weight_n=weight, late_mean_ground_support_n=mean_support,
                      final_entities=_entity_snapshot(robot, model))
        if args.lift_plan:
            result['lift_verdict'] = _lift_verdict(result['samples'], plan, feet, weight)
            passed = stop is None and result['lift_verdict']['passed']
            result['status'] = 'single_leg_lift_verified' if passed else 'single_leg_lift_failed'
        windows = {'standing': [SETTINGS['duration_s']-1, SETTINGS['duration_s']]}
        if args.lift_plan:
            windows = dict(baseline=[4., 5.], hold=[9., 10.], recovery=[15., 16.])
            windows.update({k: v for k, v in plan.get('windows', {}).items() if k != 'transfer'})
        result['posture_verdict'] = _posture_verdict(result['samples'], windows)
        wiring.write_json(out/'report.json', result)
        print('STANDING_COMPLETED', result['status'], 'stop', stop, 'last_t', result['samples'][-1]['t_s'], flush=True)
        if not passed:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)  # Preserve a physical failure before App.close can swallow its exit.
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
        try:
            wiring.write_json(out/'failure.json', result)
        except BaseException as persistence_error:
            print('FAILURE_REPORT_WRITE_ERROR', repr(persistence_error), file=sys.stderr, flush=True)
        finally:
            traceback.print_exception(error)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)
    finally:
        if env is not None:
            env.close()
        if app is not None:
            app.close()
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracking_report', type=Path)
    parser.add_argument('--lift_plan', type=Path)
    parser.add_argument('--standing_reference', type=Path)
    parser.add_argument('--chest_frequency_hz', type=float, choices=(1., 2.))
    parser.add_argument('--lf_wrist_frequency_hz', type=float, choices=(1., 6.), default=1.)
    parser.add_argument('--wrist_frequency_hz', type=float, choices=(1., 6.), default=1.)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--leg_frequency_hz', type=float, choices=(1., 6., 12.))
    parser.add_argument('--load_reference', type=Path)
    parser.add_argument('--neck_frequency_hz', type=float, choices=(1., 2.), default=1.)
    parser.add_argument('--neck_load_reference', type=Path)
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--break_failure_handler', action='store_true')
    if '--self_check' in sys.argv:
        args = parser.parse_args()
        _self_check(args.break_failure_handler)
    else:
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(parser)
        args = parser.parse_args()
        if not args.out or sum(bool(p) for p in (args.tracking_report, args.lift_plan, args.standing_reference)) != 1 or args.break_failure_handler:
            parser.error('select exactly one of tracking_report, lift_plan and standing_reference, and provide out')
        if args.standing_reference and (args.leg_frequency_hz is not None or args.wrist_frequency_hz != 1 or args.neck_frequency_hz != 1 or args.load_reference or args.neck_load_reference or args.lf_wrist_frequency_hz != 1):
            parser.error('standing_reference permits only a chest frequency override')
        if args.tracking_report and (args.chest_frequency_hz is not None or args.lf_wrist_frequency_hz != 1):
            parser.error('chest/LF overrides require standing_reference or lift_plan')
        if args.tracking_report:
            args.leg_frequency_hz = args.leg_frequency_hz or 1.
            if args.leg_frequency_hz == 12 or args.wrist_frequency_hz != 1:
                parser.error('loaded leg/wrist overrides require lift_plan')
        sys.exit(0 if _run(args) else 1)
