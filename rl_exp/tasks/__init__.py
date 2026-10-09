# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Gym registration for the lizard2 task family, plus the env cfgs and agents it names.

Importing this package registers the lizard2 gym tasks -- the only family still on the training
path (the lizard/main, lizard/parkour and lizard/baseline lines are retired). Registration also
works without importing this module directly: the shim at
``isaaclab_tasks/.../config/lizard/__init__.py`` imports it on
``import isaaclab_tasks``.
"""

import gymnasium as gym

##
# Register Gym environments.
##

# lizard2 (2026-09-22): a separate family, not a lizard version -- it has its own USD asset and a
# 30-joint skeleton (a co-located hip pivot per leg), so its task ids are its own and no lizard
# checkpoint can be replayed on it. Lineage and the measurement that justified it:
# work/closed/2026/baseline-v3-new-skeleton.md and the record it points at.
gym.register(
    id="Lizard2-Flat-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:Lizard2FlatEnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:Lizard2PPORunnerCfg",
    },
)

gym.register(
    id="Lizard2-Flat-Play-v1",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:Lizard2FlatEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:Lizard2PPORunnerCfg",
    },
)

# lizard2 v2 (2026-09-28): the same recipe as v1 with the blade joints' action authority removed,
# so its action width (26) differs from v1's (30) and a v1 checkpoint cannot be replayed on it --
# hence its own ids and its own runner (one version, one log directory).
gym.register(
    id="Lizard2-Flat-v2",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:Lizard2FlatV2EnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:Lizard2V2PPORunnerCfg",
    },
)

gym.register(
    id="Lizard2-Flat-Play-v2",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:Lizard2FlatV2EnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:Lizard2V2PPORunnerCfg",
    },
)

# V3 adopts the approved stance body; kfe/foot retain PD but leave the policy interface.
gym.register(
    id="Lizard2-Flat-v3",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:Lizard2FlatV3EnvCfg",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:Lizard2V3PPORunnerCfg",
    },
)

gym.register(
    id="Lizard2-Flat-Play-v3",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:Lizard2FlatV3EnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:Lizard2V3PPORunnerCfg",
    },
)
