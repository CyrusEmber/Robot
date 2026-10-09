# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from isaaclab.utils.configclass import configclass

from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg


@configclass
class Lizard2PPORunnerCfg(RslRlOnPolicyRunnerCfg):
    """Runner cfg for `Lizard2-Flat-v1` (new family: 30-joint skeleton, 0-3 m/s command window).

    The value block below is declared here rather than inherited from another line's runner: it is
    the plain-MLP recipe this family's runs were launched with, and an edit to it moves this family
    alone. ``obs_normalization`` is off by this first recipe's choice -- starting from scratch does
    not require disabling it, fresh statistics would also be new state.

    Two record-level choices it carries:

    * its own ``experiment_name``: one version, one log directory (versioning.mdc A), so a lizard2
      run cannot land among another line's.
    * ``max_iterations`` stated as what is actually intended, so the recorded run is reproducible
      from its own NOTES: a command *range* (two commands per 20 s episode) plus a skeleton whose
      learning curve is unknown.
    """

    num_steps_per_env = 24
    max_iterations = 10000
    save_interval = 50
    experiment_name = "lizard2_v1"
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
class Lizard2V2PPORunnerCfg(Lizard2PPORunnerCfg):
    """Runner cfg for `Lizard2-Flat-v2` (same recipe as v1, blade loses action authority).

    The same PPO recipe and the same recorded budget as v1's *run*, not as v1's declaration:
    ``max_iterations`` is stated at the value v1 was actually trained with, so this version's run
    is reproducible from its own NOTES instead of repeating the deviation v1's NOTES had to record
    (declared 10000, run 14000). The comparison arm needs the same number, so it is declared here
    rather than passed as an override twice.

    Its own ``experiment_name`` for the usual reason (one version, one log directory): a v2 run must
    not land among v1's, and the two arms' runs must not land among each other's.
    """

    max_iterations = 14000
    experiment_name = "lizard2_v2"


@configclass
class Lizard2V3PPORunnerCfg(Lizard2V2PPORunnerCfg):
    """V3 body/action adoption; PPO identical to v2, budget declared at 6000.

    The adopted body is untrained and its joint limits, ankle sense and collision surface are still
    open (`work/active/joint-limit-shape-and-range-pass.md`), so a run here is a short read of the
    new body, not a training candidate: 6000 is what it will have been trained for, and every
    reading off it says "up to step 6000" rather than "converged" (user's call, 2026-10-09). Declared
    here rather than passed as a CLI override for the reason v2's docstring gives.
    """

    max_iterations = 6000
    experiment_name = "lizard2_v3"
