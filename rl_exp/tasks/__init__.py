# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Lizard task family: env cfgs, agents, curriculum component, gym registration.

Importing this package registers all lizard gym tasks. Registration also works
without importing this module directly: the shim at
``isaaclab_tasks/.../config/lizard/__init__.py`` imports it on
``import isaaclab_tasks``.
"""

import gymnasium as gym

##
# Register Gym environments.
##

gym.register(
    id="Lizard-Velocity-Flat-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardFlatEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardFlatPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Flat-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardFlatEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardFlatPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Curriculum-Flat-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardCurriculumFlatEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardCurriculumFlatPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Curriculum-Flat-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardCurriculumFlatEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardCurriculumFlatPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Rough-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardRoughPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Rough-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardRoughPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Curriculum-Rough-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardCurriculumRoughEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardCurriculumRoughPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Curriculum-Rough-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardCurriculumRoughEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardCurriculumRoughPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v2",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V2",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV2PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v2",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V2_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV2PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v3",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V3",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV3PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v3",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V3_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV3PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v4",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V4",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV4PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v4",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V4_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV4PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v5",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V5",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV5PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v5",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V5_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV5PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v6",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V6",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV6PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v6",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V6_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV6PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v8",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V8",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV8PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v8",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V8_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV8PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v10",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V10",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV10PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v10",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V10_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV10PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v11",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V11",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV11PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v11",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V11_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV11PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v12",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V12",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV12PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v12",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V12_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV12PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v13",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V13",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV13PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v13",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V13_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV13PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v14",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V14",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV14PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v14",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V14_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV14PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V1",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V1_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherPPORunnerCfg",
    },
)

##
# Parkour line (versions/lizard/parkour/, Parkour in the Wild position-task
# experts).
##


gym.register(
    id="Lizard-Parkour-Climb-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.parkour_env_cfg:ParkourClimbEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardParkourClimbPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Parkour-Climb-Play-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.parkour_env_cfg:ParkourClimbEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardParkourClimbPPORunnerCfg",
    },
)

##
# Baseline line (versions/lizard/baseline/): flat ground, a fixed low-speed forward
# command, no curriculum and no domain randomization. The line answers one question, so
# its recipe is one file (baseline_env_cfg.py) plus its own parameter SSOT, with no
# imports from any other recipe module.
##


gym.register(
    id="Lizard-Baseline-Flat-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:BaselineFlatEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardBaselinePPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Baseline-Flat-Play-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:BaselineFlatEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardBaselinePPORunnerCfg",
    },
)

# v2 (versions/lizard/baseline/v2/PLAN.md): the speed window opens to 1-3 m/s and the blade
# joints lose command authority. Same runner cfg: the PPO hyperparameters are not a variable
# this round adds.
gym.register(
    id="Lizard-Baseline-Flat-v2",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:BaselineFlatV2EnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardBaselineV2PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Baseline-Flat-Play-v2",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:BaselineFlatV2EnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardBaselineV2PPORunnerCfg",
    },
)
