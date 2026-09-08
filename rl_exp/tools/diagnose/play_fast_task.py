# -*- coding: utf-8 -*-
"""Register an on-the-fly PLAY task variant with a forced forward-speed window.

Stock play.py samples commands from the recipe's ambition window (v5/v6/v8
PLAY = 0-3 m/s), so replay envs often stand still. This module registers
``Lizard-Rough-Play-v8-fast`` (window pinned to 1-3 m/s) via play.py's
``--external_callback`` hook — the play loop itself stays stock:

    env_isaaclab\Scripts\python.exe scripts\reinforcement_learning\rsl_rl\play.py ^
        --task Lizard-Rough-Play-v8-fast ^
        --external_callback rl_exp.tools.diagnose.play_fast_task.register ^
        --num_envs 8 --real-time

Adjust the window by editing FAST_VX (two numbers, no CLI plumbing — the
callback contract is "consume nothing, return []" so hydra stays untouched).
The cfg class lives at MODULE level: gym.make resolves the env_cfg entry
point string against this module at env build time — a class defined inside
register() would be a local and unreachable (first-run bug, fixed here).
"""

import gymnasium as gym

from isaaclab.utils.configclass import configclass

FAST_VX = (1.0, 3.0)


def register():
    """Called by play.py --external_callback; registers the task, consumes no args."""
    from rl_exp.tasks.teacher_env_cfg import LizardRoughTeacherEnvCfg_V8_PLAY
    from rl_exp.tasks.agents.rsl_rl_ppo_cfg import LizardTeacherV8PPORunnerCfg

    @configclass
    class LizardRoughTeacherEnvCfg_V8_PLAY_FAST(LizardRoughTeacherEnvCfg_V8_PLAY):
        """v8 PLAY with the forward-speed window pinned for visual inspection."""

        def __post_init__(self):
            super().__post_init__()
            self.commands.base_velocity.ranges.lin_vel_x = FAST_VX

    LizardRoughTeacherEnvCfg_V8_PLAY_FAST.__module__ = __name__  # entry point target
    globals()["LizardRoughTeacherEnvCfg_V8_PLAY_FAST"] = LizardRoughTeacherEnvCfg_V8_PLAY_FAST

    gym.register(
        id="Lizard-Rough-Play-v8-fast",
        entry_point="isaaclab.envs:ManagerBasedRLEnv",
        disable_env_checker=True,
        kwargs={
            "env_cfg_entry_point": (
                "rl_exp.tools.diagnose.play_fast_task:LizardRoughTeacherEnvCfg_V8_PLAY_FAST"
            ),
            "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV8PPORunnerCfg",
        },
    )
    return []
