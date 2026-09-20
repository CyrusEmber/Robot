# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Config-class construction shared by independent recipe lines."""

from collections.abc import Callable
from typing import ClassVar

from isaaclab.utils.configclass import configclass


def make_class(base: type, *, name: str, version: str | None, statements: dict[str, bool],
               apply: Callable, description: str) -> type:
    """Build a registered config class without importing any other recipe line."""
    def __post_init__(self):
        base.__post_init__(self)
        apply(self)

    namespace = {
        "params_version": version,
        "__post_init__": __post_init__,
        "__doc__": description,
        "__annotations__": {key: ClassVar[bool] for key in statements},
        **statements,
    }
    return configclass(type(name, (base,), namespace))
