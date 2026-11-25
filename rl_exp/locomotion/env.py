# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Assembly steps that training, evaluation and video recording share.

Isaac imports stay inside the functions: callers load the experiment before the app launches.
Evaluation-only changes (suite terrain, ``apply_eval_mode``, the height scanner) are made by the
caller on the cfg before ``make_env``; nothing here knows about them.
"""

from importlib.metadata import version
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


def load_experiment(path: Path):
    """Import a standalone experiment file under the fixed module name runs record."""
    spec = spec_from_file_location("_robot_training_experiment", path)
    experiment = module_from_spec(spec)
    sys.modules[spec.name] = experiment
    spec.loader.exec_module(experiment)
    return experiment


def make_runner_cfg(experiment):
    """Build the experiment's runner cfg, migrated to the installed rsl-rl version."""
    from isaaclab_rl.rsl_rl import handle_deprecated_rsl_rl_cfg

    return handle_deprecated_rsl_rl_cfg(experiment.make_runner_cfg(), version("rsl-rl-lib"))


def make_env(env_cfg, *, render_mode: str | None = None):
    """Construct the manager-based environment; ``render_mode="rgb_array"`` for recording."""
    from isaaclab.envs import ManagerBasedRLEnv

    return ManagerBasedRLEnv(cfg=env_cfg, render_mode=render_mode)


def wrap_env(env, runner_cfg):
    """Wrap ``env`` for rsl-rl with the action clipping the runner cfg declares."""
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper

    return RslRlVecEnvWrapper(env, clip_actions=runner_cfg.clip_actions)


def load_policy(wrapper, runner_cfg, checkpoint, device: str):
    """Load pinned checkpoint bytes (a seekable stream) and return the inference policy."""
    from rsl_rl.runners import OnPolicyRunner

    runner = OnPolicyRunner(wrapper, runner_cfg.to_dict(), log_dir=None, device=device)
    checkpoint.seek(0)
    runner.load(checkpoint, map_location=device)
    return runner.get_inference_policy(device=device)
