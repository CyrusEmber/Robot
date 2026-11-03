# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Offline v7 fixed-foot regression; no simulation or training."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tasks import obs_protocol
from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg
from rl_exp.tools.runrecord.binding import sha256_file

FEET = ('lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle')
REMOVED = {f'{name}_joint' for name in FEET}


def test_v7_contract():
    mother = yaml.safe_load((ROOT/'rl_exp/versions/lizard2/main/v6/main_params.yaml').read_text())
    for task in ('Lizard2-Flat-v7', 'Lizard2-Flat-Play-v7'):
        cfg = resolve_task_cfg(task)
        target = obs_protocol.load_diagnostic_target(None, cfg, task)
        assert target['naming'] == 'palm_spatial'
        assert set(target['end_links'].values()) == set(FEET)
        assert sha256_file(Path(target['urdf'])) == 'dbc00660b5c8feac84099fee65b44fe7a867f12a67f7ab437347ca7d82460a13'
        assert sha256_file(Path(target['target'])) == '134bf043d42c3600dcb4369ef2c5642c49f1f68b650991702f833c6bca8eb6e4'
        tree = ET.parse(target['urdf']).getroot()
        active = {j.get('name') for j in tree.findall('joint') if j.get('type') != 'fixed'}
        assert len(tree.findall('link')) == 31 and len(active) == 26
        for foot in FEET:
            assert tree.find(f"joint[@name='{foot}_fixed']").get('type') == 'fixed'
        names = []
        for term in (cfg.actions.joint_pos_legs, cfg.actions.joint_pos_spine):
            names += term.joint_names
            assert set(term.clip) == set(term.scale) == set(term.joint_names)
            assert term.preserve_order and term.use_default_offset
        assert len(names) == len(set(names)) == 26 and set(names) == active
        assert not active & REMOVED
        for elbow in ('lf_elbow_joint', 'rf_elbow_joint'):
            assert cfg.actions.joint_pos_legs.clip[elbow] == (-1., 1.)
            assert cfg.actions.joint_pos_legs.scale[elbow] == mother['action']['legs_scale'][elbow]
            assert abs(cfg.actions.joint_pos_legs.scale[elbow] - .4) < 1e-15
        assert set(cfg.scene.robot.init_state.joint_pos) == active
        assert set(cfg.scene.robot.init_state.joint_vel) == active
        assert set(cfg.scene.robot.actuators) == {'legs', 'spine'}
        for name, group in cfg.scene.robot.actuators.items():
            for field in ('stiffness', 'damping', 'effort_limit', 'velocity_limit', 'armature'):
                assert getattr(group, field) == mother['actuators'][name][field]
        assert cfg.scene.robot.init_state.rot == (0., 0., 0., 1.)
        assert cfg.scene.robot.init_state.pos[2] == mother['robot']['base_init_height'] == .6038
        assert abs((cfg.scene.robot.init_state.pos[2] - .6037631034851074) - .0000368965148926) < 1e-15
        assert not cfg.REQUIRES_CURRICULUM_STATE
    current = yaml.safe_load((ROOT/'rl_exp/versions/lizard2/main/v7/main_params.yaml').read_text())
    expected = json.loads(json.dumps(mother))
    expected['robot']['usd_path'] = 'lizard2_round_feet/lizard2_round_feet.usda'
    expected['joint_order'] = [j for j in expected['joint_order'] if f'{j}_joint' not in REMOVED]
    expected['default_joint_pos'] = {j: v for j, v in expected['default_joint_pos'].items() if j not in REMOVED}
    del expected['actuators']['feet']
    for field in ('legs_scale',):
        expected['action'][field] = {j: v for j, v in expected['action'][field].items() if j not in REMOVED}
    expected['action']['joints']['legs'] = [j for j in expected['action']['joints']['legs'] if j not in REMOVED]
    expected['action']['clip']['legs'] = {j: v for j, v in expected['action']['clip']['legs'].items() if j not in REMOVED}
    for elbow in ('lf_elbow_joint', 'rf_elbow_joint'):
        expected['action']['clip']['legs'][elbow] = [-1., 1.]
    assert current == expected, 'unapproved drift from v6.1'
    assert yaml.safe_load((ROOT/'rl_exp/versions/lizard2/main/main_params.yaml').read_text()) == current
    assert resolve_task_cfg('Lizard2-Flat-v6').params_version == 'v6'
    assert len(resolve_task_cfg('Lizard2-Flat-v6').scene.robot.init_state.joint_pos) == 30
    from rl_exp.tasks.agents.rsl_rl_ppo_cfg import Lizard2V6PPORunnerCfg, Lizard2V7PPORunnerCfg
    old, new = Lizard2V6PPORunnerCfg().to_dict(), Lizard2V7PPORunnerCfg().to_dict()
    assert new.pop('experiment_name') == 'lizard2_v7'
    old.pop('experiment_name')
    assert old == new
    sys.path.insert(0, str(ROOT/'rl_exp/tools/verify'))
    import check_recipe_registry as registry
    lines = registry.load(ROOT/'rl_exp/versions/lines.json')
    for version in ('v4', 'v5', 'v6'):
        assert registry.effective_status(lines, 'lizard2/main', version) == 'retired'
        assert not (ROOT/f'rl_exp/versions/lizard2/main/{version}/asset_lock.json').exists()


def test_fixed_terminal_rejection():
    from unittest.mock import patch

    task = 'Lizard2-Flat-v7'
    cfg = resolve_task_cfg(task)
    target = obs_protocol.load_diagnostic_target(None, cfg, task)
    for mutation in ('wrong_name', 'not_fixed', 'wrong_parent', 'active_terminal'):
        tree = ET.parse(target['urdf'])
        mount = tree.getroot().find("joint[@name='lf_wrist_fixed']")
        if mutation == 'wrong_name':
            mount.set('name', 'lf_wrong_fixed')
        elif mutation == 'not_fixed':
            mount.set('type', 'revolute')
        elif mutation == 'wrong_parent':
            mount.find('parent').set('link', 'base_link')
        else:
            mount.set('name', 'lf_wrist_joint')
            mount.set('type', 'revolute')
            cfg.actions.joint_pos_legs.joint_names.append('lf_wrist_joint')
        with patch.object(obs_protocol.ET, 'parse', return_value=tree):
            try:
                obs_protocol.load_diagnostic_target(None, cfg, task)
            except ValueError:
                pass
            else:
                raise AssertionError(f'accepted mismatched fixed terminal: {mutation}')


if __name__ == '__main__':
    test_v7_contract()
    test_fixed_terminal_rejection()
    print('LIZARD2_V7_CONFIG_OK')
