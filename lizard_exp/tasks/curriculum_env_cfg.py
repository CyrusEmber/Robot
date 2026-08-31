# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Lizard (26-joint) flat-ground task with staged bone/speed/turning curricula.

Extends the flat task (:mod:`.lizard_env_cfg`) with three independent staged
curricula built from the generic :class:`StagedCurriculumTerm`:

* ``bone_curriculum``: stage 0 locks the 10 spine joints at their rest pose
  (action scale 0), stage 1 hands spine control to the policy (legs first).
* ``speed_curriculum``: widens ``lin_vel_x`` through (0, 1) -> (1, 2) -> (1, 3) [m/s].
* ``turn_curriculum``: widens ``ang_vel_z`` from (-0.5, 0.5) to (-2.0, 2.0) [rad/s],
  entering the final stage only once ``speed_curriculum`` reached stage 2.

All tunables live in the stage lists. Action/observation dimensions are
unchanged w.r.t. the flat task: the joint action term is split into legs +
spine so the spine scale can be gated, with legs ordered before spine so the
concatenated action layout matches the articulation tree order.
"""

from isaaclab.utils.configclass import configclass

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from lizard_exp.tasks.lizard_env_cfg import (
    LizardFlatEnvCfg,
    _load_params,
)
from lizard_exp.tasks.staged_curriculum import (
    StagedCurriculumTerm,
    StagedCurriculumTermCfg,
    StageCfg,
)
from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import ActionsCfg


@configclass
class LizardCurriculumActionsCfg(ActionsCfg):
    """Joint actions split into legs and spine so the spine scale can be gated per stage."""

    joint_pos = None
    # legs before spine keeps the concatenated action layout identical to the tree order
    joint_pos_legs = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=[".*_haa_joint", ".*_hfe_joint", ".*_kfe_joint", ".*_foot_joint"],
        scale=0.5,
        use_default_offset=True,
    )
    joint_pos_spine = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=["rear_.*", "tail_.*", "neck.*_yaw_joint", "neck.*_pitch_joint"],
        scale=0.0,
        use_default_offset=True,
    )


def _make_stages(spine_scale: float) -> dict[str, StagedCurriculumTermCfg]:
    """Build the three curriculum term cfgs; all tunables live in the stage lists."""
    bone_stages = [
        # stage 0: spine locked at rest pose (scale 0 -> target stays at default joint pos)
        StageCfg(action_scales={"joint_pos_spine": 0.0}, metric_threshold=0.8, sustain_s=240.0),
        # stage 1: hand spine control to the policy
        StageCfg(action_scales={"joint_pos_spine": spine_scale}),
    ]
    speed_stages = [
        StageCfg(command_ranges={"lin_vel_x": (0.0, 1.0)}, metric_threshold=0.8, sustain_s=120.0),
        StageCfg(command_ranges={"lin_vel_x": (1.0, 2.0)}, metric_threshold=0.8, sustain_s=120.0),
        StageCfg(command_ranges={"lin_vel_x": (1.0, 3.0)}),
    ]
    turn_stages = [
        StageCfg(command_ranges={"ang_vel_z": (-0.5, 0.5)}, metric_threshold=0.8, sustain_s=120.0),
        StageCfg(command_ranges={"ang_vel_z": (-2.0, 2.0)}, requires="speed_curriculum>=2"),
    ]
    return {
        "bone_curriculum": StagedCurriculumTermCfg(func=StagedCurriculumTerm, stages=bone_stages),
        "speed_curriculum": StagedCurriculumTermCfg(func=StagedCurriculumTerm, stages=speed_stages),
        "turn_curriculum": StagedCurriculumTermCfg(func=StagedCurriculumTerm, stages=turn_stages),
    }


@configclass
class LizardCurriculumFlatEnvCfg(LizardFlatEnvCfg):
    """26-joint lizard on flat ground with staged bone/speed/turning curricula."""

    def __post_init__(self):
        super().__post_init__()

        params = _load_params()
        action_params = params["action"]

        # split the single joint action term (keeps the tree-order action layout)
        self.actions = LizardCurriculumActionsCfg()
        self.actions.joint_pos_legs.scale = action_params["legs_scale"]
        self.actions.joint_pos_legs.use_default_offset = action_params["use_default_offset"]
        self.actions.joint_pos_spine.use_default_offset = action_params["use_default_offset"]

        # staged curricula replace the flat task's fixed command ranges
        for term_name, term_cfg in _make_stages(action_params["spine_scale"]).items():
            setattr(self.curriculum, term_name, term_cfg)

        # initial command ranges mirror stage 0 (avoids one off-spec resample)
        self.commands.base_velocity.ranges.lin_vel_x = (0.0, 1.0)
        self.commands.base_velocity.ranges.ang_vel_z = (-0.5, 0.5)


@configclass
class LizardCurriculumFlatEnvCfg_PLAY(LizardCurriculumFlatEnvCfg):
    """Play variant: curricula off, spine live, final-stage command ranges."""

    def __post_init__(self):
        super().__post_init__()
        params = _load_params()

        self.curriculum.bone_curriculum = None
        self.curriculum.speed_curriculum = None
        self.curriculum.turn_curriculum = None
        self.actions.joint_pos_spine.scale = params["action"]["spine_scale"]
        self.commands.base_velocity.ranges.lin_vel_x = (1.0, 3.0)
        self.commands.base_velocity.ranges.ang_vel_z = (-2.0, 2.0)
