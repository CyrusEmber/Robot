# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Head-only floor dwell behavior, negative controls, reset and v5 routing [N, s]."""

import sys
from pathlib import Path
from types import SimpleNamespace as NS

import torch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from isaaclab.envs.mdp.terminations import illegal_contact  # noqa: E402
from isaaclab.managers import SceneEntityCfg, TerminationTermCfg  # noqa: E402

FLOOR = '/World/ground/terrain/GroundPlane/CollisionPlane'


class Scene(dict):
    @property
    def sensors(self):
        return self


def fixture(legacy=False):
    sensor = NS(cfg=NS(update_period=.005, history_length=4), body_names=['neck_pitch'],
                contact_view=NS(filter_paths=[[FLOOR], [FLOOR]], filter_count=1), data=NS(
                    force_matrix_w_history=NS(torch=torch.zeros(2, 4, 1, 1, 3)),
                    net_forces_w_history=NS(torch=torch.zeros(2, 4, 1, 3))))
    env = NS(num_envs=2, device='cpu', cfg=NS(decimation=4, sim=NS(dt=.005),
             scene=NS(lazy_sensor_update=False)), scene=Scene(head_ground_contact=sensor,
                                                            contact_forces=sensor))
    params = dict(sensor_name='head_ground_contact', head_body_name='neck_pitch',
                  floor_prim_path=FLOOR, threshold=1., dwell_s=.5)
    if legacy:
        term = lambda env, **kw: illegal_contact(env, threshold=1.,
            sensor_cfg=SceneEntityCfg('contact_forces', body_ids=[0]))
    else:
        from rl_exp.tasks.lizard2_mdp import HeadGroundContactDwell
        term = HeadGroundContactDwell(TerminationTermCfg(func=HeadGroundContactDwell, params=params), env)
    return env, sensor, params, term


def feed(env, sensor, params, term, force=10., net=10.):
    sensor.data.force_matrix_w_history.torch.fill_(0.)
    sensor.data.force_matrix_w_history.torch[..., 2] = force
    sensor.data.net_forces_w_history.torch.fill_(0.)
    sensor.data.net_forces_w_history.torch[..., 2] = net
    return term(env, **params)


def test_brief_head_ground_contact_is_allowed(legacy=False):
    env, sensor, params, term = fixture(legacy)
    assert not feed(env, sensor, params, term).any(), 'brief contact terminated before 0.5 s'


def test_self_contact_is_not_ground(legacy=False):
    env, sensor, params, term = fixture(legacy)
    for _ in range(30):
        assert not feed(env, sensor, params, term, force=0., net=100.).any(), 'self-contact counted as floor'


def test_exact_duration_and_substep_gap():
    env, sensor, params, term = fixture()
    for _ in range(24):
        assert not feed(env, sensor, params, term).any()  # 96 physics steps, 0.48 s
    assert feed(env, sensor, params, term).all()  # exactly 100 steps, 0.5 s
    term.reset()
    for _ in range(24):
        feed(env, sensor, params, term)
    sensor.data.force_matrix_w_history.torch[:, :, 0, 0, 2] = torch.tensor([10., 10., 0., 10.])
    assert not term(env, **params).any()  # one gap inside the control window breaks continuity
    assert term._steps.tolist() == [2, 2], 'history must be consumed oldest first'
    for _ in range(24):
        assert not feed(env, sensor, params, term).any()
    assert feed(env, sensor, params, term).all()


def test_independent_envs_reset_and_threshold():
    env, sensor, params, term = fixture()
    for _ in range(24):
        feed(env, sensor, params, term)
    term.reset(torch.tensor([0]))
    assert feed(env, sensor, params, term).tolist() == [False, True]
    assert term._steps.tolist() == [4, 100]
    term.reset()
    for _ in range(30):
        assert not feed(env, sensor, params, term, force=1.).any()
    assert term._steps.tolist() == [0, 0]


def test_reset_outside_rollout_inference_mode():
    env, sensor, params, term = fixture()
    with torch.inference_mode():
        feed(env, sensor, params, term)
    term.reset(torch.tensor([0]))
    term.reset()
    assert term._steps.tolist() == [0, 0]


def test_invalid_partner_and_sampling_are_rejected():
    from rl_exp.tasks.lizard2_mdp import HeadGroundContactDwell
    for damage in ('partner', 'missing_partner', 'body', 'history', 'lazy'):
        env, sensor, params, _ = fixture()
        if damage == 'partner':
            sensor.contact_view.filter_paths = ['/WrongFloor']
        elif damage == 'missing_partner':
            sensor.contact_view.filter_paths = [[FLOOR], []]
        elif damage == 'body':
            sensor.body_names = ['chest_pitch', 'neck_pitch']
        elif damage == 'history':
            sensor.cfg.history_length = 1
        else:
            env.cfg.scene.lazy_sensor_update = True
        try:
            HeadGroundContactDwell(TerminationTermCfg(func=HeadGroundContactDwell, params=params), env)
        except ValueError:
            continue
        raise AssertionError('accepted invalid '+damage)


def test_v5_routing_preserves_v4():
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg
    from rl_exp.tasks.lizard2_mdp import HeadGroundContactDwell
    cfg = resolve_task_cfg('Lizard2-Flat-v5')
    old = resolve_task_cfg('Lizard2-Flat-v4')
    assert cfg.terminations.head_contact is None
    assert cfg.terminations.head_ground_contact.func is HeadGroundContactDwell
    assert cfg.terminations.head_ground_contact.params['dwell_s'] == .5
    for backend in ('default', 'physx'):
        sensor = getattr(cfg.scene.head_ground_contact, backend)
        assert sensor.prim_path.endswith('/Geometry/neck_pitch')
        assert sensor.filter_prim_paths_expr == [FLOOR]
        assert sensor.history_length == cfg.decimation == 4 and sensor.update_period == .005
    assert old.terminations.head_contact.func is illegal_contact
    assert old.terminations.head_contact.params['sensor_cfg'].body_names == ['chest_pitch', 'neck_pitch']
    assert cfg.terminations.base_contact.to_dict() == old.terminations.base_contact.to_dict()
    expected_rewards = old.rewards.to_dict()
    expected_rewards['undesired_contacts'] = None
    assert cfg.rewards.to_dict() == expected_rewards, 'unrelated reward changed'
    for name in ('actions', 'observations', 'events', 'commands'):
        assert getattr(cfg, name).to_dict() == getattr(old, name).to_dict(), name+' drifted'


def test_v5_leg_contacts_no_longer_deduct_reward():
    import rl_exp.tasks  # registers the task ids when this test is run by itself
    from isaaclab.managers import RewardManager
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg

    old = resolve_task_cfg('Lizard2-Flat-v4').rewards.undesired_contacts
    assert old.weight == -1.0
    # Inject one contacted leg body. Exercise the real manager and reward function,
    # not just a zero in YAML; a later re-enabled term must make this test fail.
    sensor_cfg = old.params['sensor_cfg']
    body_names = sensor_cfg.body_names
    sensor_cfg.body_names = None
    sensor_cfg.body_ids = list(range(len(body_names)))
    forces = torch.zeros(2, 4, len(body_names), 3)
    forces[0, :, 0, 2] = 50.
    env = NS(num_envs=2, device='cpu', sim=NS(is_playing=lambda: True),
             scene=Scene(contact_forces=NS(body_names=body_names, num_bodies=len(body_names),
                         find_bodies=lambda *args, **kwargs: (list(range(len(body_names))), body_names),
                         data=NS(net_forces_w_history=NS(torch=forces)))))
    baseline = RewardManager({'undesired_contacts': old}, env)
    assert torch.allclose(baseline.compute(.02), torch.tensor([-.02, 0.]))
    for task in ('Lizard2-Flat-v5', 'Lizard2-Flat-Play-v5'):
        cfg = resolve_task_cfg(task)
        assert cfg.rewards.undesired_contacts is None, task+' still enables the leg-contact penalty'
        manager = RewardManager({'undesired_contacts': cfg.rewards.undesired_contacts}, env)
        assert manager.active_terms == []
        assert manager.compute(.02).tolist() == [0., 0.]


def test_v6_belly_contact_reset(task='Lizard2-Flat-v6'):
    """The old base-only selector misses chest contact; feet and tail remain allowed."""
    import rl_exp.tasks
    from isaaclab.managers import TerminationManager
    from isaaclab.utils.string import resolve_matching_names
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg

    names = ['base_link', 'chest_pitch', 'lf_wrist', 'tail1_pitch']
    forces = torch.zeros(2, 4, len(names), 3)
    cfg = resolve_task_cfg(task).terminations.base_contact.copy()
    env = NS(num_envs=2, device='cpu', sim=NS(is_playing=lambda: True),
             scene=Scene(contact_forces=NS(body_names=names, num_bodies=len(names),
                 find_bodies=lambda patterns, **kwargs: resolve_matching_names(patterns, names, **kwargs),
                 data=NS(net_forces_w_history=NS(torch=forces)))))
    manager = TerminationManager({'base_contact': cfg}, env)
    forces[:, :, 2:, 2] = 1000.
    assert not manager.compute().any(), 'foot or tail contact caused a belly reset'
    forces[0, 0, 1, 2] = 1.
    assert not manager.compute().any(), 'the inherited strict threshold changed'
    forces[0, 0, 1, 2] = 1.01
    assert manager.compute().tolist() == [True, False], 'chest belly contact did not reset immediately'
    forces.zero_()
    forces[1, -1, 1, 2] = 50.
    assert manager.compute().tolist() == [False, True], 'oldest physics substep was missed or envs leaked'
    forces.zero_()
    forces[0, 0, 0, 2] = 2.
    assert manager.compute().tolist() == [True, False], 'root-body contact protection was lost'


def test_v6_changes_only_belly_selection_and_yaw_range():
    import gymnasium as gym
    import rl_exp.tasks
    from isaaclab.utils.string import string_to_callable
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg

    for suffix in ('', '-Play'):
        old_task = 'Lizard2-Flat'+suffix+'-v5'
        new_task = old_task.replace('v5', 'v6')
        old, cfg = resolve_task_cfg(old_task), resolve_task_cfg(new_task)
        assert old.terminations.base_contact.params['sensor_cfg'].body_names == ['base_link']
        assert cfg.terminations.base_contact.params['sensor_cfg'].body_names == ['base_link', 'chest_pitch']
        expected = old.terminations.to_dict()
        expected['base_contact']['params']['sensor_cfg']['body_names'] = ['base_link', 'chest_pitch']
        assert cfg.terminations.to_dict() == expected, 'unrelated termination changed'
        for name in ('scene', 'rewards', 'actions', 'observations', 'events', 'commands', 'sim', 'curriculum'):
            expected_group = getattr(old, name).to_dict()
            if name == 'commands':
                expected_group['base_velocity']['ranges']['ang_vel_z'] = (-.5, .5)
            assert getattr(cfg, name).to_dict() == expected_group, name+' drifted'
        old_agent = string_to_callable(gym.spec(old_task).kwargs['rsl_rl_cfg_entry_point'])().to_dict()
        new_agent = string_to_callable(gym.spec(new_task).kwargs['rsl_rl_cfg_entry_point'])().to_dict()
        old_agent['experiment_name'] = 'lizard2_v6'
        assert old_agent == new_agent, 'PPO changed beyond its log identity'
        test_v6_belly_contact_reset(new_task)


def test_v6_yaw_command_sampling_and_reward():
    """Both turning directions reach command observations and the actual yaw reward."""
    import rl_exp.tasks  # register tasks for standalone regression execution
    from isaaclab.envs.mdp.commands.velocity_command import UniformVelocityCommand
    from isaaclab.envs.mdp.observations import generated_commands
    from isaaclab.envs.mdp.rewards import track_ang_vel_z_exp
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg

    for task in ('Lizard2-Flat-v6', 'Lizard2-Flat-Play-v6'):
        cfg = resolve_task_cfg(task)
        assert cfg.commands.base_velocity.ranges.ang_vel_z == (-.5, .5), 'v6 yaw range is still zero-only'
        assert not cfg.commands.base_velocity.heading_command
        assert cfg.commands.base_velocity.rel_standing_envs == 0.
        command = object.__new__(UniformVelocityCommand)
        command._env = NS(num_envs=64, device='cpu')
        command.cfg = cfg.commands.base_velocity
        command.vel_command_b = torch.zeros(64, 3)
        command.is_standing_env = torch.zeros(64, dtype=torch.bool)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(42)
            command._resample_command(torch.arange(64))
        sampled = command.command.clone()
        command._update_command()
        assert torch.equal(sampled, command.command), 'postprocessing overwrote sampled turning commands'
        assert (sampled[:, 2] > .05).any() and (sampled[:, 2] < -.05).any()
        assert sampled[:, 2].abs().max() <= .5
        assert sampled[:, 0].min() >= 0. and sampled[:, 0].max() <= 3.
        assert sampled[:, 1].eq(0.).all()
        env = NS(command_manager=NS(get_command=lambda name: command.command),
                 scene={'robot': NS(data=NS(root_ang_vel_b=NS(torch=torch.zeros(64, 3))))})
        assert torch.equal(generated_commands(env, 'base_velocity'), sampled)
        command.vel_command_b[:, 2] = .5
        term = cfg.rewards.track_ang_vel_z_exp
        stopped = track_ang_vel_z_exp(env, **term.params)*term.weight
        env.scene['robot'].data.root_ang_vel_b.torch[:, 2] = .5
        following = track_ang_vel_z_exp(env, **term.params)*term.weight
        env.scene['robot'].data.root_ang_vel_b.torch[:, 2] = -.5
        opposite = track_ang_vel_z_exp(env, **term.params)*term.weight
        assert torch.allclose(following, torch.full((64,), .5))
        assert (following > stopped).all() and (stopped > opposite).all()


def test_v5_disables_self_collisions_without_changing_v4():
    import rl_exp.tasks  # register tasks for standalone execution
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg

    old = resolve_task_cfg('Lizard2-Flat-v4')
    assert old.scene.robot.spawn.articulation_props.enabled_self_collisions is True
    expected = old.scene.robot.to_dict()
    expected['spawn']['articulation_props']['enabled_self_collisions'] = False
    for task in ('Lizard2-Flat-v5', 'Lizard2-Flat-Play-v5'):
        cfg = resolve_task_cfg(task)
        assert cfg.scene.robot.spawn.articulation_props.enabled_self_collisions is False, task
        assert cfg.scene.robot.to_dict() == expected, 'unrelated robot configuration changed'


if __name__ == '__main__':
    if '--legacy-belly' in sys.argv:
        try:
            test_v6_belly_contact_reset('Lizard2-Flat-v5')
        except AssertionError as error:
            print('LEGACY_BELLY_FAILURE:', error)
            raise SystemExit(1)
        raise SystemExit(0)
    if '--legacy' in sys.argv:
        failed = 0
        for check in (test_brief_head_ground_contact_is_allowed, test_self_contact_is_not_ground):
            try:
                check(legacy=True)
            except AssertionError as error:
                print(check.__name__, 'FAIL:', error)
                failed += 1
        sys.exit(1 if failed else 0)
    for name, check in list(globals().items()):
        if name.startswith('test_'):
            check()
            print(name, 'PASS')
    print('LIZARD2_V5_HEAD_GROUND_DWELL_OK')
