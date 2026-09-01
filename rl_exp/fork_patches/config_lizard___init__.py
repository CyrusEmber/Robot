# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Shim: lizard task registration lives in rl_exp (self-contained project).

This file must stay inside isaaclab_tasks so that ``import isaaclab_tasks``
triggers registration; everything else (env cfgs, agents, curriculum
component, registrations) lives in the rl_exp git repo, made importable by the
venv .pth file (repo README, deployment step 1).
"""

import rl_exp.tasks  # noqa: F401  (registers all lizard gym tasks)
