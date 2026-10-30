# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Check candidate articulation joint targets in gravity-free diagnostic simulation."""
import argparse
import json
from pathlib import Path
import traceback

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--usd', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.out.exists():
    parser.error('output already exists')
app = AppLauncher(args).app
try:
    import torch
    import isaaclab.sim as sim_utils
    from isaaclab.assets import ArticulationCfg
    from isaaclab.actuators import ImplicitActuatorCfg
    from isaaclab.scene import InteractiveSceneCfg
    from isaaclab.envs import ManagerBasedEnv, ManagerBasedEnvCfg, mdp
    from isaaclab.managers import ObservationGroupCfg, ObservationTermCfg
    from isaaclab.utils import configclass

    @configclass
    class SceneCfg(InteractiveSceneCfg):
        robot = ArticulationCfg(prim_path='{ENV_REGEX_NS}/Robot',
            spawn=sim_utils.UsdFileCfg(usd_path=str(args.usd.resolve()),
                rigid_props=sim_utils.RigidBodyPropertiesCfg(disable_gravity=True),
                articulation_props=sim_utils.ArticulationRootPropertiesCfg(enabled_self_collisions=False)),
            init_state=ArticulationCfg.InitialStateCfg(pos=(0., 0., 2.)),
            actuators={'all': ImplicitActuatorCfg(joint_names_expr=['.*'], stiffness=40., damping=8.,
                                                 effort_limit_sim=70., velocity_limit_sim=6.)})

    @configclass
    class ActionsCfg:
        joints = mdp.JointPositionActionCfg(asset_name='robot', joint_names=['.*'], scale=1.,
                                             use_default_offset=True, preserve_order=True)

    @configclass
    class PolicyCfg(ObservationGroupCfg):
        joint_pos = ObservationTermCfg(func=mdp.joint_pos_rel)

    @configclass
    class ObservationsCfg:
        policy = PolicyCfg(enable_corruption=False, concatenate_terms=False)

    cfg = ManagerBasedEnvCfg(scene=SceneCfg(num_envs=1, env_spacing=5.), actions=ActionsCfg(),
                             observations=ObservationsCfg(), events={}, decimation=1,
                             sim=sim_utils.SimulationCfg(dt=.005, device=args.device))
    env = ManagerBasedEnv(cfg)
    env.reset()
    robot = env.scene['robot']
    names = env.action_manager.get_term('joints')._joint_names
    assert len(names) == 34 and len(robot.joint_names) == 34
    results = {}
    for leg, tip in [('lf', 'wrist'), ('rf', 'wrist'), ('rl', 'ankle'), ('rr', 'ankle')]:
        for suffix in ('_lateral_joint', '_joint'):
            name = leg + '_' + tip + suffix
            env.reset()
            action = torch.zeros((1, len(names)), device=env.device)
            action[0, names.index(name)] = .2
            for _ in range(200):
                env.step(action)
            actual = float(robot.data.joint_pos.torch[0, robot.joint_names.index(name)])
            results[name] = actual
            assert abs(actual - .2) < .08, (name, actual)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({'usd': str(args.usd.resolve()), 'joints': names,
        'measured_rad': results, 'target_rad': .2, 'gravity': False, 'seconds_per_axis': 1.,
        'scope': 'isolated unladen tracking; gains are diagnostic only'}, indent=2), encoding='utf-8')
    print('TWO_AXIS_NATIVE_OK', results, flush=True)
    env.close()
    app.close(exit_code=0)
except BaseException:
    traceback.print_exc()
    app.close(exit_code=1)
    raise
