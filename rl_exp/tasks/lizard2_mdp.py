# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Historical Lizard2 termination import path."""

from rl_exp.locomotion import terminations


class HeadGroundContactDwell(terminations.HeadGroundContactDwell):
    """Preserve the class identity used by historical recipes."""
