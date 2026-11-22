# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Reusable articulation and action joint order for the fixed round-foot Lizard2."""

from pathlib import Path

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg

_ASSET_DIR = Path(__file__).resolve().parents[1] / "lizard2_round_feet"
USD_PATH = _ASSET_DIR / "lizard2_round_feet.usda"
URDF_PATH = _ASSET_DIR / "lizard2_round_feet.urdf"

# Each row specifies the joint name, default stiffness and default damping.
# The order within each group is the default action column order.
_LEG_DRIVES = (
    ("lf_shoulder_swing_joint", 39.51528592905594, 12.578106166597744),
    ("lf_shoulder_abduct_joint", 683.3387264744138, 60.46906596698318),
    ("lf_shoulder_twist_joint", 63.0, 9.259147567093025),
    ("lf_elbow_joint", 220.0, 14.95006801883189),
    ("rf_shoulder_swing_joint", 39.51530946002652, 12.57811365673831),
    ("rf_shoulder_abduct_joint", 683.3389536890733, 60.46907063160223),
    ("rf_shoulder_twist_joint", 63.0, 9.2591467559832),
    ("rf_elbow_joint", 220.0, 14.950070650195313),
    ("rl_hip_swing_joint", 42.430006073784355, 13.505890404123846),
    ("rl_hip_abduct_joint", 707.7715645844042, 63.21388695024736),
    ("rl_hip_twist_joint", 62.0, 9.054972304307615),
    ("rl_knee_joint", 220.0, 14.950076790041491),
    ("rr_hip_swing_joint", 42.42998254281378, 13.50588291398328),
    ("rr_hip_abduct_joint", 707.7713694627079, 63.213923617214846),
    ("rr_hip_twist_joint", 62.0, 9.054978426060286),
    ("rr_knee_joint", 220.0, 14.950093455325538),
)
_SPINE_DRIVES = (
    ("chest_yaw_joint", 1183.4806397841637, 376.71358775041693),
    ("chest_pitch_joint", 7835.783011254786, 895.5293576650034),
    ("neck_yaw_joint", 52.913237006972885, 16.842806449305478),
    ("neck_pitch_joint", 304.46663057539075, 40.917534161789845),
    ("tail1_yaw_joint", 94.9596647293975, 30.22660007206544),
    ("tail1_pitch_joint", 1052.7517254177665, 122.08309725184303),
    ("tail2_yaw_joint", 37.673672166476464, 11.991902299436566),
    ("tail2_pitch_joint", 479.2714787818486, 42.577695464661495),
    ("tail3_yaw_joint", 6.440327228306681, 2.0500198270286676),
    ("tail3_pitch_joint", 128.6921180297125, 9.159101712150125),
)

LEG_ACTION_JOINTS = tuple(joint for joint, _, _ in _LEG_DRIVES)
SPINE_ACTION_JOINTS = tuple(joint for joint, _, _ in _SPINE_DRIVES)
ACTION_JOINTS = LEG_ACTION_JOINTS + SPINE_ACTION_JOINTS


def make_robot_cfg(prim_path: str = "{ENV_REGEX_NS}/Robot") -> ArticulationCfg:
    """Create a fresh round-foot articulation configuration.

    Args:
        prim_path: USD prim path for the robot.

    Returns:
        The articulation with independent actuator settings for the caller.
    """
    return ArticulationCfg(
        prim_path=prim_path,
        spawn=sim_utils.UsdFileCfg(
            usd_path=str(USD_PATH),
            activate_contact_sensors=True,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                max_depenetration_velocity=1.0,
            ),
            articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                enabled_self_collisions=False,
                solver_position_iteration_count=8,
                solver_velocity_iteration_count=0,
            ),
        ),
        init_state=ArticulationCfg.InitialStateCfg(
            pos=(0.0, 0.0, 0.6038),
            joint_pos=dict.fromkeys(ACTION_JOINTS, 0.0),
            joint_vel=dict.fromkeys(ACTION_JOINTS, 0.0),
        ),
        soft_joint_pos_limit_factor=0.95,
        actuators={
            "legs": ImplicitActuatorCfg(
                joint_names_expr=list(LEG_ACTION_JOINTS),
                stiffness={joint: kp for joint, kp, _ in _LEG_DRIVES},
                damping={joint: kd for joint, _, kd in _LEG_DRIVES},
                effort_limit_sim=180.0,
                velocity_limit_sim=10.0,
                armature=0.0,
            ),
            "spine": ImplicitActuatorCfg(
                joint_names_expr=list(SPINE_ACTION_JOINTS),
                stiffness={joint: kp for joint, kp, _ in _SPINE_DRIVES},
                damping={joint: kd for joint, _, kd in _SPINE_DRIVES},
                effort_limit_sim=dict.fromkeys(SPINE_ACTION_JOINTS, 80.0) | {"chest_pitch_joint": 280.0},
                velocity_limit_sim=4.0,
                armature=0.0,
            ),
        },
    )
