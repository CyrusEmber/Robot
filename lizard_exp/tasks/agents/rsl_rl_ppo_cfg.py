# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from isaaclab.utils.configclass import configclass

from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg


@configclass
class LizardFlatPPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 1500
    save_interval = 50
    experiment_name = "lizard_flat"
    actor = RslRlMLPModelCfg(
        hidden_dims=[256, 128, 128],
        activation="elu",
        obs_normalization=False,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[256, 128, 128],
        activation="elu",
        obs_normalization=False,
    )
    algorithm = RslRlPpoAlgorithmCfg(
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
    )


@configclass
class LizardRoughPPORunnerCfg(LizardFlatPPORunnerCfg):
    """Runner cfg for `Lizard-Velocity-Rough-v0` (family rough, separate log dir)."""

    experiment_name = "lizard_rough"


@configclass
class LizardTeacherPPORunnerCfg(LizardFlatPPORunnerCfg):
    """Runner cfg for the `Lizard-Rough-v1` teacher snapshot.

    Separate log dir from the family rough runs: the teacher recipe is frozen
    (plan §4.1) and must not share checkpoints with family experiments.
    """

    experiment_name = "lizard_rough_teacher"


@configclass
class LizardCurriculumFlatPPORunnerCfg(LizardFlatPPORunnerCfg):
    """Runner cfg for `Lizard-Velocity-Curriculum-Flat-v0` (separate log dir)."""

    experiment_name = "lizard_curriculum_flat"


@configclass
class LizardCurriculumRoughPPORunnerCfg(LizardFlatPPORunnerCfg):
    """Runner cfg for `Lizard-Velocity-Curriculum-Rough-v0` (separate log dir)."""

    experiment_name = "lizard_curriculum_rough"
