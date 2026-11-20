# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Spider hexapod flat-ground velocity tracking.

Robot geometry comes from spider_exp/spider.urdf (SSOT), control params from
spider_exp/spider_params.yaml (SSOT). See spider_env_cfg.py.
"""

import pathlib

import yaml

import isaaclab.sim as sim_utils
from isaaclab.actuators import IdealPDActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.configclass import configclass

from isaaclab_tasks.manager_based.locomotion.velocity.config.anymal_c.flat_env_cfg import AnymalCFlatEnvCfg

# this file: .../config/spider/spider_env_cfg.py -> IsaacLab root is parents[8]
_SPIDER_EXP_DIR = pathlib.Path(__file__).resolve().parents[8] / "spider_exp"


def _load_params() -> dict:
    with open(_SPIDER_EXP_DIR / "spider_params.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@configclass
class SpiderFlatEnvCfg(AnymalCFlatEnvCfg):
    """Spider hexapod on flat ground. All robot params read from the SSOT files."""

    def __post_init__(self):
        super().__post_init__()

        params = _load_params()
        robot_params = params["robot"]
        actuator_params = params["actuators"]
        action_params = params["action"]
        sim_params = params["sim"]
        names_params = params["names"]

        # swap anymal-C for the spider (USD produced by convert_urdf.py)
        self.scene.robot = ArticulationCfg(
            prim_path="{ENV_REGEX_NS}/Robot",
            spawn=sim_utils.UsdFileCfg(
                usd_path=str(_SPIDER_EXP_DIR / robot_params["usd_path"]),
                activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(
                    disable_gravity=False,
                    retain_accelerations=False,
                    linear_damping=0.0,
                    angular_damping=0.0,
                    max_linear_velocity=1000.0,
                    max_angular_velocity=1000.0,
                    max_depenetration_velocity=1.0,
                ),
                articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                    enabled_self_collisions=True,
                    solver_position_iteration_count=4,
                    solver_velocity_iteration_count=0,
                ),
            ),
            init_state=ArticulationCfg.InitialStateCfg(
                pos=(0.0, 0.0, robot_params["base_init_height"]),
                joint_pos=params["default_joint_pos"],
            ),
            actuators={
                # ideal PD on purpose: UE side uses the same position drive, no actuator net
                "legs": IdealPDActuatorCfg(
                    joint_names_expr=[".*_coxa", ".*_femur", ".*_tibia"],
                    stiffness=actuator_params["stiffness"],
                    damping=actuator_params["damping"],
                    effort_limit=actuator_params["effort_limit"],
                    velocity_limit=actuator_params["velocity_limit"],
                    armature=actuator_params["armature"],
                ),
            },
            soft_joint_pos_limit_factor=0.95,
        )

        # action space from SSOT
        self.actions.joint_pos.scale = action_params["scale"]
        self.actions.joint_pos.use_default_offset = action_params["use_default_offset"]

        # timing from SSOT
        self.decimation = sim_params["decimation"]
        self.episode_length_s = sim_params["episode_length_s"]
        self.sim.dt = sim_params["dt"]
        self.sim.render_interval = self.decimation

        # reward body-name patterns from SSOT
        self.rewards.feet_air_time.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["foot_body_names"]
        )
        self.rewards.undesired_contacts.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["undesired_contact_body_names"]
        )

        # inherited push disturbance is tuned for a 50 kg quadruped; spider is ~10 kg
        self.events.base_external_force_torque.params["force_range"] = (-10.0, 10.0)
        self.events.base_external_force_torque.params["torque_range"] = (-1.5, 1.5)


@configclass
class SpiderFlatEnvCfg_PLAY(SpiderFlatEnvCfg):
    def __post_init__(self):
        super().__post_init__()

        # smaller scene for play
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        # disable randomization for play
        self.observations.policy.enable_corruption = False
        # remove random pushing event
        self.events.base_external_force_torque = None
        self.events.push_robot = None
