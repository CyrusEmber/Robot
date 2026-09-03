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
        "env_cfg_entry_point": "rl_exp.tasks.lizard_env_cfg:LizardFlatEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardFlatPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Flat-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.lizard_env_cfg:LizardFlatEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardFlatPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Curriculum-Flat-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.curriculum_env_cfg:LizardCurriculumFlatEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardCurriculumFlatPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Curriculum-Flat-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.curriculum_env_cfg:LizardCurriculumFlatEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardCurriculumFlatPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Rough-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.rough_env_cfg:LizardRoughEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardRoughPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Rough-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.rough_env_cfg:LizardRoughEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardRoughPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Curriculum-Rough-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.curriculum_rough_env_cfg:LizardCurriculumRoughEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardCurriculumRoughPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Velocity-Curriculum-Rough-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.curriculum_rough_env_cfg:LizardCurriculumRoughEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardCurriculumRoughPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v2",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V2",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV2PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v2",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V2_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV2PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v3",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V3",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV3PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v3",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V3_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV3PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v4",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V4",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV4PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v4",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V4_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV4PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v5",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V5",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV5PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v5",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V5_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV5PPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V1",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherPPORunnerCfg",
    },
)

gym.register(
    id="Lizard-Rough-Play-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V1_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherPPORunnerCfg",
    },
)
