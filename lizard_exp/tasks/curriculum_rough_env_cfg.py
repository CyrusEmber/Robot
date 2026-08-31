# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Lizard (26-joint) rough-terrain task with staged bone/speed/turning curricula.

Same staged curricula as the flat variant (:mod:`.curriculum_env_cfg`) on top of
the stock rough-terrain setup (:mod:`.rough_env_cfg`): the terrain difficulty
curriculum from the rough base stays active alongside bone/speed/turning.
"""

from isaaclab.utils.configclass import configclass

from lizard_exp.tasks.lizard_env_cfg import _load_params
from lizard_exp.tasks.curriculum_env_cfg import (
    LizardCurriculumActionsCfg,
    _make_stages,
)
from lizard_exp.tasks.play_utils import disable_dr_events
from lizard_exp.tasks.rough_env_cfg import LizardRoughEnvCfg


@configclass
class LizardCurriculumRoughEnvCfg(LizardRoughEnvCfg):
    """26-joint lizard on rough terrain with staged bone/speed/turning curricula."""

    def __post_init__(self):
        super().__post_init__()

        params = _load_params(self.params_version)
        action_params = params["action"]

        # split the single joint action term (keeps the tree-order action layout)
        self.actions = LizardCurriculumActionsCfg()
        self.actions.joint_pos_legs.scale = action_params["legs_scale"]
        self.actions.joint_pos_legs.use_default_offset = action_params["use_default_offset"]
        self.actions.joint_pos_spine.use_default_offset = action_params["use_default_offset"]

        # staged curricula replace the fixed command ranges; terrain_levels stays
        for term_name, term_cfg in _make_stages(action_params["spine_scale"]).items():
            setattr(self.curriculum, term_name, term_cfg)

        # initial command ranges mirror stage 0 (avoids one off-spec resample)
        self.commands.base_velocity.ranges.lin_vel_x = (0.0, 1.0)
        self.commands.base_velocity.ranges.ang_vel_z = (-0.5, 0.5)


@configclass
class LizardCurriculumRoughEnvCfg_PLAY(LizardCurriculumRoughEnvCfg):
    """Play variant: curricula off, spine live, final-stage command ranges."""

    def __post_init__(self):
        super().__post_init__()
        params = _load_params(self.params_version)

        # smaller scene + fixed terrain grid (matches the rough PLAY setup)
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.scene.terrain.max_init_terrain_level = None
        if self.scene.terrain.terrain_generator is not None:
            self.scene.terrain.terrain_generator.num_rows = 5
            self.scene.terrain.terrain_generator.num_cols = 5
            self.scene.terrain.terrain_generator.curriculum = False
        self.observations.policy.enable_corruption = False
        # deterministic evaluation: every DR event off (shared list, single
        # source -- this PLAY previously missed randomize_limb_mass)
        disable_dr_events(self.events)

        # curricula off: final stage everywhere (spine live, full ranges)
        self.curriculum.terrain_levels = None
        self.curriculum.bone_curriculum = None
        self.curriculum.speed_curriculum = None
        self.curriculum.turn_curriculum = None
        self.actions.joint_pos_spine.scale = params["action"]["spine_scale"]
        self.commands.base_velocity.ranges.lin_vel_x = (1.0, 3.0)
        self.commands.base_velocity.ranges.ang_vel_z = (-2.0, 2.0)
