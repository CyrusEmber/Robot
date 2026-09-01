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


@configclass
class LizardV3PpoAlgorithmCfg(RslRlPpoAlgorithmCfg):
    """PPO algorithm cfg with the paper S1 hyperparams + per-iter lr decay.

    ``lr_decay`` is consumed by ``DecayingLrPPO`` (teacher_networks.py,
    registered via the ``class_name`` point path -- zero rsl_rl changes).
    """

    class_name: str = "rl_exp.tasks.teacher_networks:DecayingLrPPO"
    lr_decay: float = 0.9999


@configclass
class LizardTeacherV3PPORunnerCfg(RslRlOnPolicyRunnerCfg):
    """Runner cfg for `Lizard-Rough-v3` (paper-aligned teacher, obs 381).

    Paper S1 hyperparams: lr 5e-4 with 0.9999/iter decay (schedule fixed),
    gamma 0.996, 2 epochs, clip 0.2, entropy 0.005, GAE 0.95, minibatch size
    8300 -> num_mini_batches = max(1, floor(num_envs * num_steps_per_env /
    8300)) = 11 at the stock 4096 envs x 24 steps. Actor/critic are the
    three-encoder ``SplitEncoderModel`` (per-stream normalization ON), fed by
    the env's proprio/extero/priv obs groups.
    """

    num_steps_per_env = 24
    max_iterations = 4000
    save_interval = 50
    experiment_name = "lizard_rough_teacher_v3"
    obs_groups = {
        "actor": ["proprio", "extero", "priv"],
        "critic": ["proprio", "extero", "priv"],
    }
    actor = RslRlMLPModelCfg(
        class_name="rl_exp.tasks.teacher_networks:SplitEncoderModel",
        hidden_dims=[256, 160, 128],
        activation="lrelu",
        obs_normalization=True,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    critic = RslRlMLPModelCfg(
        class_name="rl_exp.tasks.teacher_networks:SplitEncoderModel",
        hidden_dims=[256, 160, 128],
        activation="lrelu",
        obs_normalization=True,
    )
    algorithm = LizardV3PpoAlgorithmCfg(
        num_learning_epochs=2,
        # 4096 envs x 24 steps / 8300 (paper minibatch size) ~= 11 batches
        num_mini_batches=11,
        learning_rate=5.0e-4,
        schedule="fixed",
        gamma=0.996,
        lam=0.95,
        entropy_coef=0.005,
        desired_kl=0.01,
        max_grad_norm=1.0,
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
    )
