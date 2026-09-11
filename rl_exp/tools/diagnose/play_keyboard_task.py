# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Keyboard teleop for any registered ``Lizard-*-Play-vN`` task (play.py side).

Registers ``<task>-keyboard`` through play.py's ``--external_callback`` hook, so
the IsaacLab tree stays stock -- nothing to re-apply after a reinstall:

    env_isaaclab\\Scripts\\python.exe scripts\\reinforcement_learning\\rsl_rl\\play.py ^
        --task Lizard-Rough-Play-v8-keyboard ^
        --external_callback rl_exp.tools.diagnose.play_keyboard_task.register ^
        --viz kit --real-time --num_envs 1

Hold a key to move, release to stop -- the device integrates press/release events
rather than coasting, and a release lost to a focus change leaves the command
stuck (``L`` zeroes it, see ``se2_keyboard.Se2Keyboard``). Bindings are the stock
:class:`~isaaclab.devices.keyboard.Se2Keyboard` ones (numpad or arrows):

    ====================== ========================= ========================
    Command                Key (+ve axis)            Key (-ve axis)
    ====================== ========================= ========================
    Move along x-axis      Numpad 8 / Arrow Up       Numpad 2 / Arrow Down
    Move along y-axis      Numpad 4 / Arrow Right    Numpad 6 / Arrow Left
    Rotate along z-axis    Numpad 7 / Z              Numpad 9 / X
    ====================== ========================= ========================

``--viz kit`` is load-bearing (the keyboard is a Kit app-window device; without
a visualizer Kit is never launched), ``--real-time`` keeps the loop at wall-clock
speed so key presses land, and ``--num_envs 1`` is one robot under one keyboard
(every env receives the same command).

Why the command term is replaced instead of writing ``vel_command_b`` from the
play loop (the ``fork_patches/play_keyboard.patch`` approach): the stock
:class:`~isaaclab.envs.mdp.commands.UniformVelocityCommand` mutates the command
AFTER the play loop's write -- ``CommandManager.compute`` runs from
``ManagerBasedRLEnv.step`` -- so keyboard input only survives until the next
compute. With the recipe's ``heading_command=True``/``rel_heading_envs=1.0`` the
yaw is recomputed from a random heading target every step (turn keys dead),
``rel_standing_envs`` zeroes a fraction of the envs, and
``resampling_time_range`` re-randomizes ``lin_vel_x/y`` mid-run. Owning the term
removes all three at the source, which is the same recipe the eval harness
documents in ``.codemaker/skills/tool/isaaclab-eval-harness/SKILL.md`` and
applies in ``ablation_harness/components/dr_controller.py``.
"""

from __future__ import annotations

import importlib
import sys

import gymnasium as gym
import torch

from isaaclab.utils.configclass import configclass

TASK_SUFFIX = "-keyboard"

# Key-press magnitudes as (v_x [m/s], v_y [m/s], omega_z [rad/s]). The stock
# Se2KeyboardCfg defaults (0.8, 0.4, 1.0) are slow next to the trained command
# range -- v8's yaml is x (-1, 3), y (-0.5, 0.5), yaw (-1, 1) -- so x is pinned
# at the ambition end here, y and yaw left alone. Edit these two numbers (no CLI
# plumbing), same convention as play_fast_task.FAST_VX.
KEY_SENSITIVITY = (3.0, 0.4, 1.0)


def _requested_task() -> str | None:
    """``--task`` from the user's ORIGINAL argv.

    play.py calls the callback before folding ``sys.argv`` down to the
    unconsumed remainder, so the token is still the plain ``--task`` /
    ``--task=`` form here (see ``isaaclab_tasks/utils/preset_cli``).
    """
    for index, token in enumerate(sys.argv):
        if token == "--task" and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
        if token.startswith("--task="):
            return token.split("=", 1)[1]
    return None


def _cfg_class(task_id: str):
    """The ``env_cfg_entry_point`` class registered for *task_id*."""
    entry = gym.spec(task_id).kwargs["env_cfg_entry_point"]
    if not isinstance(entry, str):
        return entry
    module_name, _, attr = entry.partition(":")
    return getattr(importlib.import_module(module_name), attr)


def _keyboard_variant(base_cls):
    """Subclass *base_cls* with the velocity command handed to the keyboard.

    Only ``class_type`` is swapped. The keyboard term owns the entire command,
    so the recipe's ``_range`` fields become inert rather than hostile, and
    staged curricula that poke ``command.cfg.ranges`` keep working.
    """

    @configclass
    class KeyboardVariant(base_cls):
        """Keyboard-teleop variant (see this module's docstring)."""

        def __post_init__(self):
            super().__post_init__()
            # string path, not the class: this runs at cfg construction (pre-Kit)
            self.commands.base_velocity.class_type = f"{__name__}:KeyboardVelocityCommand"

    return KeyboardVariant


def _build_keyboard_command():
    """Build :class:`KeyboardVelocityCommand` on first access (post-kit).

    Everything IsaacLab-side is imported here rather than at module scope: this
    module is imported by play.py's ``--external_callback`` BEFORE Kit boots, and
    ``isaaclab.devices``/``isaaclab.managers`` must not be pulled in at compose
    time (same lazy discipline as ``rl_exp.tasks.teacher_mdp``).
    """
    from isaaclab.managers import CommandTerm

    class KeyboardVelocityCommand(CommandTerm):
        """Velocity command read straight from the keyboard every step.

        Base-frame ``(v_x, v_y, omega_z)`` [m/s, m/s, rad/s]. Referenced from the
        cfg by string (``class_type``) because a command term is constructed at
        env build time, after Kit has started.
        """

        def __init__(self, cfg, env):
            super().__init__(cfg, env)
            from isaaclab.devices.keyboard import Se2Keyboard, Se2KeyboardCfg

            self.vel_command_b = torch.zeros(self.num_envs, 3, device=self.device)
            kbd_cfg = Se2KeyboardCfg(sim_device=str(self.device))
            kbd_cfg.v_x_sensitivity, kbd_cfg.v_y_sensitivity, kbd_cfg.omega_z_sensitivity = (
                KEY_SENSITIVITY
            )
            self._keyboard = Se2Keyboard(kbd_cfg)

        @property
        def command(self) -> torch.Tensor:
            """Desired base velocity in the base frame. Shape is (num_envs, 3)."""
            return self.vel_command_b

        def _update_metrics(self):
            """No metrics: the operator is the command source, not a tracker."""

        def _resample_command(self, env_ids):
            """Never resample -- the command holds until the operator changes it."""

        def _update_command(self):
            """Overwrite the command with the live key state.

            Called once per env step from ``ManagerBasedRLEnv.step`` (after env
            resets), before the observation manager reads the command, so the
            policy sees this step's key state.
            """
            self.vel_command_b[:] = self._keyboard.advance().to(self.device)

    return KeyboardVelocityCommand


def __getattr__(name):
    if name == "KeyboardVelocityCommand":
        cls = _build_keyboard_command()
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def register():
    """play.py ``--external_callback`` entry point: register ``<task>-keyboard``.

    Consumes no CLI args, so it returns the empty remainder play.py intersects
    with (the callback contract).
    """
    task_id = _requested_task()
    if task_id is None:
        raise ValueError(
            f"{__name__} needs --task <base>-keyboard where <base> is a registered "
            "Lizard-*-Play-vN task; see the module docstring for the full command line."
        )
    task_id = task_id.split(":")[-1]
    # the operator passes the SUFFIXED id (that is the task play.py will load), so
    # the base task -- the only one the registry knows at this point -- is the
    # name we must look up
    if task_id.endswith(TASK_SUFFIX):
        task_id = task_id[: -len(TASK_SUFFIX)]
    if "-Play" not in task_id:
        raise ValueError(
            f"{__name__} only wraps PLAY task variants (got {task_id!r}); a train task's "
            "velocity command must stay policy-driven."
        )

    base_cls = _cfg_class(task_id)
    variant = _keyboard_variant(base_cls)
    # gym resolves the entry point by name against this module, so the class must
    # be module-level (a class local to register() would be unreachable)
    name = f"{base_cls.__name__}_Keyboard"
    variant.__name__ = variant.__qualname__ = name
    variant.__module__ = __name__
    globals()[name] = variant

    spec = gym.spec(task_id)
    kwargs = dict(spec.kwargs)
    kwargs["env_cfg_entry_point"] = f"{__name__}:{name}"
    gym.register(
        id=task_id + TASK_SUFFIX,
        entry_point=spec.entry_point,
        disable_env_checker=spec.disable_env_checker,
        kwargs=kwargs,
    )
    print(f"[INFO] Registered keyboard teleop task: {task_id}{TASK_SUFFIX}")
    return []


def _self_check(task_id: str = "Lizard-Rough-Play-v8") -> None:
    """Assert ``register`` wires a real PLAY cfg to the keyboard term (offline).

    Drives the real entry point with a synthetic argv carrying the SUFFIXED task
    id -- the form an operator actually types -- so the suffix stripping and the
    registry lookup are covered, not just the class swap.
    """
    import rl_exp.tasks  # noqa: F401  -- registers the lizard tasks

    from isaaclab.managers import CommandTerm

    sys.argv = [sys.argv[0], "--task", task_id + TASK_SUFFIX, "--viz", "kit"]
    register()

    spec = gym.spec(task_id + TASK_SUFFIX)
    module_name, _, attr = spec.kwargs["env_cfg_entry_point"].partition(":")
    variant = getattr(importlib.import_module(module_name), attr)
    entry = variant().commands.base_velocity.class_type
    assert entry == f"{__name__}:KeyboardVelocityCommand", entry

    cmd_module, _, cmd_attr = entry.partition(":")
    term_cls = getattr(importlib.import_module(cmd_module), cmd_attr)
    assert issubclass(term_cls, CommandTerm), term_cls

    # the term __init__ needs a Kit app window so it cannot be built here; the
    # sensitivity wiring is what would otherwise only fail at GUI launch
    from isaaclab.devices.keyboard.se2_keyboard_cfg import Se2KeyboardCfg

    kbd = Se2KeyboardCfg()
    kbd.v_x_sensitivity, kbd.v_y_sensitivity, kbd.omega_z_sensitivity = KEY_SENSITIVITY
    print(f"KEYBOARD_PLAY_OK ({task_id}{TASK_SUFFIX} -> {entry})")


if __name__ == "__main__":
    _self_check(sys.argv[1] if len(sys.argv) > 1 else "Lizard-Rough-Play-v8")
