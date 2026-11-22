# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Lizard2 v7 flat-ground velocity-tracking experiment."""

from isaaclab import sim as sim_utils
from isaaclab.assets import AssetBaseCfg
from isaaclab.envs import ManagerBasedRLEnvCfg, mdp
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewardTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR, ISAACLAB_NUCLEUS_DIR
from isaaclab.utils.configclass import configclass
from isaaclab_physx.physics import PhysxCfg
from isaaclab_physx.sensors import ContactSensorCfg
from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg

from rl_exp.locomotion.rewards import belly_contact_force, track_lin_vel_xy_miki
from rl_exp.locomotion.terminations import HeadGroundContactDwell
from rl_exp.robots import lizard2_round_feet

URDF_PATH = lizard2_round_feet.URDF_PATH
LEGACY_TASK = "Lizard2-Flat-v7"

_DT = 0.005
_DECIMATION = 4
_HEAD_BODY = "neck_pitch"
_FLOOR_COLLIDER = "/World/ground/terrain/GroundPlane/CollisionPlane"
_ZERO_ROOT_RANGES = dict.fromkeys(("x", "y", "z", "roll", "pitch", "yaw"), (0.0, 0.0))

# Scale and symmetric clip bound by joint axis, in radians. The clip is applied
# by Isaac Lab to the processed action after scale and offset.
_LEG_ACTION_LIMITS = {
    "swing": (0.19999999999999998, 0.6),
    "abduct": (0.19999999999999998, 0.6),
    "twist": (0.17453292519943295, 0.5235987755982988),
    "elbow": (0.39999999999999997, 1.0),
    "knee": (0.39999999999999997, 1.2),
}
_SPINE_ACTION_LIMITS = {"yaw": (0.19999999999999998, 0.6), "pitch": (0.16666666666666666, 0.5)}


def _joint_position_action(
    joints: tuple[str, ...], limits: dict[str, tuple[float, float]]
) -> mdp.JointPositionActionCfg:
    by_joint = {joint: limits[joint.rsplit("_", 2)[1]] for joint in joints}
    return mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=list(joints),
        scale={joint: scale for joint, (scale, _) in by_joint.items()},
        offset=0.0,
        clip={joint: (-bound, bound) for joint, (_, bound) in by_joint.items()},
        use_default_offset=True,
        preserve_order=True,
    )


@configclass
class _Observations:
    @configclass
    class Policy(ObsGroup):
        base_lin_vel = ObsTerm(func=mdp.base_lin_vel)
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel)
        projected_gravity = ObsTerm(func=mdp.projected_gravity)
        velocity_commands = ObsTerm(func=mdp.generated_commands, params={"command_name": "base_velocity"})
        joint_pos = ObsTerm(func=mdp.joint_pos_rel)
        joint_vel = ObsTerm(func=mdp.joint_vel_rel)
        actions = ObsTerm(func=mdp.last_action)

    policy: Policy = Policy(enable_corruption=False, concatenate_terms=True)


@configclass
class _Actions:
    joint_pos_legs = _joint_position_action(lizard2_round_feet.LEG_ACTION_JOINTS, _LEG_ACTION_LIMITS)
    joint_pos_spine = _joint_position_action(lizard2_round_feet.SPINE_ACTION_JOINTS, _SPINE_ACTION_LIMITS)


@configclass
class _Commands:
    base_velocity = mdp.UniformVelocityCommandCfg(
        asset_name="robot",
        resampling_time_range=(10.0, 10.0),
        heading_command=False,
        rel_standing_envs=0.0,
        debug_vis=True,
        ranges=mdp.UniformVelocityCommandCfg.Ranges(
            lin_vel_x=(0.0, 3.0), lin_vel_y=(0.0, 0.0), ang_vel_z=(-0.5, 0.5)
        ),
    )


@configclass
class _Rewards:
    track_ang_vel_z_exp = RewardTerm(
        func=mdp.track_ang_vel_z_exp, weight=0.5, params={"command_name": "base_velocity", "std": 0.5}
    )
    lin_vel_z_l2 = RewardTerm(func=mdp.lin_vel_z_l2, weight=-2.0)
    dof_torques_l2 = RewardTerm(func=mdp.joint_torques_l2, weight=-1.0e-5)
    action_rate_l2 = RewardTerm(func=mdp.action_rate_l2, weight=-0.01)
    track_lin_vel_xy_miki = RewardTerm(
        func=track_lin_vel_xy_miki, weight=1.5, params={"command_name": "base_velocity", "sigma_sq": 0.25}
    )
    belly_contact_force = RewardTerm(
        func=belly_contact_force,
        weight=-0.5,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=["base_link"]), "force_scale": 706.0},
    )


@configclass
class _Terminations:
    time_out = DoneTerm(func=mdp.time_out, time_out=True)
    base_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=["base_link", "chest_pitch"]), "threshold": 1.0},
    )
    head_ground_contact = DoneTerm(
        func=HeadGroundContactDwell,
        params={
            "sensor_name": "head_ground_contact",
            "head_body_name": _HEAD_BODY,
            "floor_prim_path": _FLOOR_COLLIDER,
            "threshold": 1.0,
            "dwell_s": 0.5,
        },
    )


@configclass
class _Events:
    # v7 TRAIN uses deterministic resets with no domain randomization or pushes.
    reset_base = EventTerm(
        func=mdp.reset_root_state_uniform,
        mode="reset",
        params={"pose_range": _ZERO_ROOT_RANGES.copy(), "velocity_range": _ZERO_ROOT_RANGES.copy()},
    )
    reset_robot_joints = EventTerm(
        func=mdp.reset_joints_by_scale,
        mode="reset",
        params={"position_range": (1.0, 1.0), "velocity_range": (0.0, 0.0)},
    )


@configclass
class _Scene(InteractiveSceneCfg):
    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="plane",
        max_init_terrain_level=5,
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply", restitution_combine_mode="multiply",
            static_friction=1.0, dynamic_friction=1.0,
        ),
        visual_material=sim_utils.MdlFileCfg(
            mdl_path=f"{ISAACLAB_NUCLEUS_DIR}/Materials/TilesMarbleSpiderWhiteBrickBondHoned/TilesMarbleSpiderWhiteBrickBondHoned.mdl",
            project_uvw=True,
            texture_scale=(0.25, 0.25),
        ),
    )
    robot = lizard2_round_feet.make_robot_cfg()
    contact_forces = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/Robot/.*", update_period=_DT, history_length=_DECIMATION, track_air_time=True
    )
    head_ground_contact = ContactSensorCfg(
        prim_path=f"{{ENV_REGEX_NS}}/Robot/Geometry/{_HEAD_BODY}",
        update_period=_DT,
        history_length=_DECIMATION,
        filter_prim_paths_expr=[_FLOOR_COLLIDER],
        track_air_time=False,
    )
    sky_light = AssetBaseCfg(
        prim_path="/World/skyLight",
        spawn=sim_utils.DomeLightCfg(
            intensity=750.0,
            texture_file=f"{ISAAC_NUCLEUS_DIR}/Materials/Textures/Skies/PolyHaven/kloofendal_43d_clear_puresky_4k.hdr",
        ),
    )


def make_env_cfg(*, play: bool = False) -> ManagerBasedRLEnvCfg:
    """Return the v7 environment configuration for training or playback."""
    scene = _Scene(num_envs=4096, env_spacing=2.5, lazy_sensor_update=False)

    # Preserve the historical v7 rigid-body and actuator friction settings.
    rigid_props = scene.robot.spawn.rigid_props
    rigid_props.disable_gravity = False
    rigid_props.retain_accelerations = False
    rigid_props.linear_damping = 0.0
    rigid_props.angular_damping = 0.0
    rigid_props.max_linear_velocity = 1000.0
    rigid_props.max_angular_velocity = 1000.0
    for actuator in scene.robot.actuators.values():
        actuator.friction = 0.0
        actuator.dynamic_friction = 0.0
        actuator.viscous_friction = 0.0

    if play:
        scene.num_envs = 50
        scene.terrain.max_init_terrain_level = None

    return ManagerBasedRLEnvCfg(
        scene=scene,
        observations=_Observations(),
        actions=_Actions(),
        commands=_Commands(),
        rewards=_Rewards(),
        terminations=_Terminations(),
        events=_Events(),
        curriculum=None,
        decimation=_DECIMATION,
        episode_length_s=20.0,
        sim=sim_utils.SimulationCfg(
            dt=_DT,
            render_interval=_DECIMATION,
            physics_material=scene.terrain.physics_material,
            physics=PhysxCfg(
                gpu_max_rigid_patch_count=10 * 2**15, solver_type=1, enable_external_forces_every_iteration=False
            ),
        ),
    )


def make_runner_cfg() -> RslRlOnPolicyRunnerCfg:
    """Return the v7 PPO runner configuration."""
    return RslRlOnPolicyRunnerCfg(
        num_steps_per_env=24,
        max_iterations=6000,
        save_interval=50,
        experiment_name="lizard2_v7",
        obs_groups={"actor": ["policy"], "critic": ["policy"]},
        actor=RslRlMLPModelCfg(
            hidden_dims=[256, 128, 128],
            activation="elu",
            obs_normalization=False,
            distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
        ),
        critic=RslRlMLPModelCfg(hidden_dims=[256, 128, 128], activation="elu", obs_normalization=False),
        algorithm=RslRlPpoAlgorithmCfg(
            value_loss_coef=1.0,
            use_clipped_value_loss=True,
            clip_param=0.2,
            entropy_coef=0.005,
            num_learning_epochs=5,
            num_mini_batches=4,
            learning_rate=1.0e-3,
            schedule="adaptive",
            gamma=0.99,
            lam=0.95,
            desired_kl=0.01,
            max_grad_norm=1.0,
        ),
    )
