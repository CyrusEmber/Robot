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

ROOT_BODY_PRIM = "Geometry/base_link"
BELLY_BODY = "base_link"
CHEST_BODY = "chest_pitch"
HEAD_BODY = "neck_pitch"
HEAD_BODY_PRIM = f"{{ENV_REGEX_NS}}/Robot/Geometry/{HEAD_BODY}"
NOMINAL_WEIGHT_N = 706.0

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

#: Measured 2026-11-03 on Lizard2-Flat-Play-v7: the articulation order the observation and the
#: action actually read, keyed by the asset it was measured on. This is NOT the action order above
#: -- a permutation here silently misaligns every trained checkpoint, so it is written down as a
#: fact and bound to the asset's bytes instead of being derived from the URDF tree.
MEASURED_JOINT_ORDER = (
    "chest_yaw_joint",
    "tail1_yaw_joint",
    "rl_hip_swing_joint",
    "rr_hip_swing_joint",
    "chest_pitch_joint",
    "tail1_pitch_joint",
    "rl_hip_abduct_joint",
    "rr_hip_abduct_joint",
    "neck_yaw_joint",
    "lf_shoulder_swing_joint",
    "rf_shoulder_swing_joint",
    "tail2_yaw_joint",
    "rl_hip_twist_joint",
    "rr_hip_twist_joint",
    "neck_pitch_joint",
    "lf_shoulder_abduct_joint",
    "rf_shoulder_abduct_joint",
    "tail2_pitch_joint",
    "rl_knee_joint",
    "rr_knee_joint",
    "lf_shoulder_twist_joint",
    "rf_shoulder_twist_joint",
    "tail3_yaw_joint",
    "lf_elbow_joint",
    "rf_elbow_joint",
    "tail3_pitch_joint",
)

#: The formal asset the order above was measured on; a re-export must update these deliberately.
MEASURED_USD_SHA256 = "134bf043d42c3600dcb4369ef2c5642c49f1f68b650991702f833c6bca8eb6e4"
MEASURED_URDF_SHA256 = "dbc00660b5c8feac84099fee65b44fe7a867f12a67f7ab437347ca7d82460a13"

#: sha256 of ``"|".join(MEASURED_JOINT_ORDER)``: a permutation keeps the joint set, so binding the
#: bytes of the asset does not notice it -- this does, until it is re-pasted deliberately.
MEASURED_ORDER_SHA256 = "3841d3bc2c0e21de977c4a5702622ca43f6b64b80effc311152cb7b26478241c"

# Default action scale and symmetric clip bound per joint [rad].
ACTION_SCALE = {
    "lf_shoulder_swing_joint": 0.19999999999999998,
    "lf_shoulder_abduct_joint": 0.19999999999999998,
    "lf_shoulder_twist_joint": 0.17453292519943295,
    "lf_elbow_joint": 0.39999999999999997,
    "rf_shoulder_swing_joint": 0.19999999999999998,
    "rf_shoulder_abduct_joint": 0.19999999999999998,
    "rf_shoulder_twist_joint": 0.17453292519943295,
    "rf_elbow_joint": 0.39999999999999997,
    "rl_hip_swing_joint": 0.19999999999999998,
    "rl_hip_abduct_joint": 0.19999999999999998,
    "rl_hip_twist_joint": 0.17453292519943295,
    "rl_knee_joint": 0.39999999999999997,
    "rr_hip_swing_joint": 0.19999999999999998,
    "rr_hip_abduct_joint": 0.19999999999999998,
    "rr_hip_twist_joint": 0.17453292519943295,
    "rr_knee_joint": 0.39999999999999997,
    "chest_yaw_joint": 0.19999999999999998,
    "chest_pitch_joint": 0.16666666666666666,
    "neck_yaw_joint": 0.19999999999999998,
    "neck_pitch_joint": 0.16666666666666666,
    "tail1_yaw_joint": 0.19999999999999998,
    "tail1_pitch_joint": 0.16666666666666666,
    "tail2_yaw_joint": 0.19999999999999998,
    "tail2_pitch_joint": 0.16666666666666666,
    "tail3_yaw_joint": 0.19999999999999998,
    "tail3_pitch_joint": 0.16666666666666666,
}
ACTION_CLIP = {
    "lf_shoulder_swing_joint": 0.6,
    "lf_shoulder_abduct_joint": 0.6,
    "lf_shoulder_twist_joint": 0.5235987755982988,
    "lf_elbow_joint": 1.0,
    "rf_shoulder_swing_joint": 0.6,
    "rf_shoulder_abduct_joint": 0.6,
    "rf_shoulder_twist_joint": 0.5235987755982988,
    "rf_elbow_joint": 1.0,
    "rl_hip_swing_joint": 0.6,
    "rl_hip_abduct_joint": 0.6,
    "rl_hip_twist_joint": 0.5235987755982988,
    "rl_knee_joint": 1.2,
    "rr_hip_swing_joint": 0.6,
    "rr_hip_abduct_joint": 0.6,
    "rr_hip_twist_joint": 0.5235987755982988,
    "rr_knee_joint": 1.2,
    "chest_yaw_joint": 0.6,
    "chest_pitch_joint": 0.5,
    "neck_yaw_joint": 0.6,
    "neck_pitch_joint": 0.5,
    "tail1_yaw_joint": 0.6,
    "tail1_pitch_joint": 0.5,
    "tail2_yaw_joint": 0.6,
    "tail2_pitch_joint": 0.5,
    "tail3_yaw_joint": 0.6,
    "tail3_pitch_joint": 0.5,
}


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
                disable_gravity=False,
                retain_accelerations=False,
                linear_damping=0.0,
                angular_damping=0.0,
                max_linear_velocity=1000.0,
                max_angular_velocity=1000.0,
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
                friction=0.0,
                dynamic_friction=0.0,
                viscous_friction=0.0,
            ),
            "spine": ImplicitActuatorCfg(
                joint_names_expr=list(SPINE_ACTION_JOINTS),
                stiffness={joint: kp for joint, kp, _ in _SPINE_DRIVES},
                damping={joint: kd for joint, _, kd in _SPINE_DRIVES},
                effort_limit_sim=dict.fromkeys(SPINE_ACTION_JOINTS, 80.0) | {"chest_pitch_joint": 280.0},
                velocity_limit_sim=4.0,
                armature=0.0,
                friction=0.0,
                dynamic_friction=0.0,
                viscous_friction=0.0,
            ),
        },
    )
