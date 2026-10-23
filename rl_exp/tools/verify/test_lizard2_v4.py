# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline formal-v4 routing/drive/action checks; no Kit or training [SI units]."""
import copy
import math
from pathlib import Path
import sys
from unittest.mock import patch
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tasks import obs_protocol  # noqa: E402
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402
from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg  # noqa: E402

TASK = 'Lizard2-Flat-Play-v4'


def test_formal_binding_uses_declared_naming():
    cfg = resolve_task_cfg(TASK)
    target = obs_protocol.load_diagnostic_target(None, cfg, TASK)
    assert target['naming'] == 'palm_spatial'
    assert target['end_links'] == dict(lf='lf_wrist', rf='rf_wrist', rl='rl_ankle', rr='rr_ankle')
    assert len(target['joint_names']) == 30
    assert sha256_file(Path(target['target'])) == '721e8a4053c2a6114b5c4607e57ed34f287fe317f8f9abb47a5e857b845e9c0e'
    assert sha256_file(Path(target['urdf'])) == 'e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00'


def test_wrong_formal_naming_is_rejected():
    cfg = resolve_task_cfg(TASK)
    document, source = obs_protocol._params_document(TASK)
    wrong = copy.deepcopy(document)
    wrong['robot']['naming'] = 'shared'
    with patch.object(obs_protocol, '_params_document', return_value=(wrong, source)):
        try:
            obs_protocol.load_diagnostic_target(None, cfg, TASK)
        except ValueError as error:
            assert 'foreign leg joints' in str(error)
        else:
            raise AssertionError('wrong declared naming was accepted')


def test_formal_actions_match_urdf_limits():
    cfg = resolve_task_cfg(TASK)
    target = obs_protocol.load_diagnostic_target(None, cfg, TASK)
    limits = {j.get('name'): j.find('limit') for j in ET.parse(target['urdf']).getroot().findall('joint')
              if j.get('type') != 'fixed'}
    names = []
    assert cfg.actions.joint_pos is None
    for term in (cfg.actions.joint_pos_legs, cfg.actions.joint_pos_spine):
        assert term.preserve_order and term.use_default_offset and term.offset == 0.
        for name in term.joint_names:
            lo, hi = float(limits[name].get('lower')), float(limits[name].get('upper'))
            assert term.clip[name] == (lo, hi)
            assert math.isclose(term.scale[name], min(-lo, hi)/3, rel_tol=0., abs_tol=1.e-12)
        names += term.joint_names
    assert len(names) == len(set(names)) == 30 and set(names) == set(limits)


def test_runtime_caps_and_sampling_are_explicit():
    cfg = resolve_task_cfg(TASK)
    carried = []
    for group in cfg.scene.robot.actuators.values():
        carried += group.joint_names_expr
        assert group.effort_limit_sim == group.effort_limit
        assert group.velocity_limit_sim == group.velocity_limit
    assert len(carried) == len(set(carried)) == 30
    for name in ('lf_elbow_joint', 'rf_elbow_joint', 'rl_knee_joint', 'rr_knee_joint'):
        assert cfg.scene.robot.actuators['legs'].stiffness[name] == 220.
    assert cfg.scene.robot.actuators['spine'].effort_limit_sim['chest_pitch_joint'] == 280.
    assert cfg.scene.robot.spawn.articulation_props.enabled_self_collisions
    assert cfg.scene.robot.init_state.rot == (0., 0., 0., 1.)
    assert not cfg.scene.lazy_sensor_update
    for name in ('default', 'physx'):
        sensor = getattr(cfg.scene.contact_forces, name)
        assert sensor.update_period == cfg.sim.dt == .005 and sensor.history_length == cfg.decimation == 4
    assert cfg.sim.physics.physx.solver_type == 1
    assert cfg.sim.physics.physx.enable_external_forces_every_iteration is False
    for field in ('pose_range', 'velocity_range'):
        assert cfg.events.reset_base.params[field] == dict.fromkeys(
            ('x', 'y', 'z', 'roll', 'pitch', 'yaw'), (0., 0.))


def test_old_body_keeps_shared_binding():
    task = 'Lizard2-Flat-Play-v3'
    cfg = resolve_task_cfg(task)
    assert obs_protocol.load_diagnostic_target(None, cfg, task)['naming'] == 'shared'


def test_declaration_covers_list_changes():
    sys.path.insert(0, str(REPO/'rl_exp/tools/verify'))
    from check_recipe_build import covers

    key = 'rewards.undesired_contacts.params.sensor_cfg.body_names'
    assert covers(key, key+'[]')
    assert covers(key, key+'[0]')
    assert not covers(key, key+'_other[]')
    assert not covers(key+'[0]', key)


def test_default_geometry_reader_binds_current_body_and_per_joint_gains():
    from rl_exp.tools.verify import check_leg_reachability as geometry

    urdf, naming, _ = geometry.diagnostic_urdf(None, None, None)
    assert urdf == (REPO/'rl_exp/lizard2_palm_spatial/lizard2_palm_spatial.urdf').resolve()
    assert geometry._naming_id(naming) == 'palm_spatial'
    joints = geometry.chain_joint_names(urdf, 'lf', naming)
    gains = geometry.gain_table(REPO/'rl_exp', 'lizard2', joints)
    assert gains['lf_elbow_joint']['kp'] == 220.
    assert set(gains) == set(joints)
    assert geometry.CALIBRATION_URDF != urdf


def test_diff_emitter_names_every_writer_of_declared_parent_paths():
    from rl_exp.tools.pipeline import emit_diff_declaration as emitter

    declaration, unowned, _, _ = emitter.build('lizard2/main', 'v4')
    assert not unowned
    problems = []
    assert emitter.crb.hard_b('lizard2/main', 'v4', declaration, problems) == 66
    assert not problems, problems


if __name__ == '__main__':
    for name, check in list(globals().items()):
        if name.startswith('test_'):
            check()
            print(name, 'PASS')
    print('LIZARD2_V4_CONFIG_OK')
