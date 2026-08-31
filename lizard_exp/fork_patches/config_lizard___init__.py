# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Shim: lizard task registration lives in lizard_exp (self-contained project).

This file must stay inside isaaclab_tasks so that ``import isaaclab_tasks``
triggers registration; everything else (env cfgs, agents, curriculum
component, registrations) lives in ``E:\\IsaacLab\\lizard_exp\\tasks``.
"""

import pathlib
import sys

# config/<robot>/__init__.py -> IsaacLab root is parents[8]
_ISAAC_ROOT = str(pathlib.Path(__file__).resolve().parents[8])
if _ISAAC_ROOT not in sys.path:
    sys.path.insert(0, _ISAAC_ROOT)

import lizard_exp.tasks  # noqa: E402,F401  (registers all lizard gym tasks)
