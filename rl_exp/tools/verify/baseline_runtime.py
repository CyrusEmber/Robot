# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Runtime checks shared by the baseline probe and its fixed-window evaluation."""


def resolve_task_cfg(task: str, require_line: str | None = None):
    """Resolve the requested registered config; never substitute a hardcoded class.

    The test is "this task is a recipe task" -- it declares its params line -- and NOT "this task
    belongs to the one historical line the probe was first written for": every line has the same
    runtime interface, and a hardcoded line key silently made the probe useless for any other family
    (review 2026-09-22). A caller that really needs one line (the fixed-window evaluation pins the
    baseline line for comparability) passes ``require_line`` and says so at its own call site.
    """
    import gymnasium as gym
    from isaaclab.utils.string import string_to_callable

    cfg = string_to_callable(gym.spec(task).kwargs["env_cfg_entry_point"])()
    line = getattr(cfg, "params_line", None)
    if not line:
        raise ValueError(f"{task} declares no params_line: not a recipe task")
    if require_line is not None and line != require_line:
        raise ValueError(f"{task} is on line {line!r}, not {require_line!r}")
    return cfg


def joint_reset_errors(robot) -> list[str]:
    """Check actual reset joint positions [rad] and velocities [rad/s]."""
    import torch

    errors = []
    for key in ("joint_pos", "joint_vel"):
        actual = getattr(robot.data, key).torch
        expected = getattr(robot.data, "default_" + key).torch
        if not torch.allclose(actual, expected, atol=1e-5, rtol=0):
            errors.append(f"{key}: actual reset differs from default by {(actual - expected).abs().max().item()}")
    return errors


def material_errors(robot) -> list[str]:
    """Read live per-shape friction/restitution; absence is a failed check, not a pass."""
    import torch
    import warp as wp

    try:
        values = robot.root_view.get_material_properties()
        values = values if isinstance(values, torch.Tensor) else wp.to_torch(values)
    except (AttributeError, RuntimeError, TypeError) as err:
        return [f"live material properties unavailable: {err}"]
    if values.shape[0] != robot.num_instances or values.numel() == 0:
        return [f"unexpected material shape: {tuple(values.shape)}"]
    if not torch.isfinite(values).all() or not torch.equal(values, values[0:1].expand_as(values)):
        return ["live friction/restitution differs across envs or is non-finite"]
    return []


def termination_errors(env) -> list[str]:
    """Inject controlled sensor history and clock values through the active manager.

    This checks contact/timeout wiring and thresholds, not physical fall dynamics.
    Buffers and manager outputs are restored before returning.
    """
    import torch

    manager = env.termination_manager
    sensor = env.scene.sensors["contact_forces"]
    forces = sensor.data.net_forces_w_history.torch
    saved_forces = forces.clone()
    saved_clock = env.episode_length_buf.clone()
    errors = []
    term = manager.get_term_cfg("base_contact")
    # Choose the contract's body independently of the configured term. Injecting the
    # term's own IDs would also pass if it were accidentally wired to a foot.
    body_id = sensor.body_names.index("base_link")
    try:
        forces.zero_()
        env.episode_length_buf.zero_()
        manager.compute()
        if manager.get_term("base_contact").any() or manager.get_term("time_out").any():
            errors.append("contact/timeout fires in a clear initial state")
        forces[0, -1, body_id, 2] = float(term.params["threshold"]) + 1.0
        manager.compute()
        expected = torch.zeros(env.num_envs, dtype=torch.bool, device=env.device)
        expected[0] = True
        if not torch.equal(manager.get_term("base_contact"), expected):
            errors.append("base_contact did not fire only for the injected env")
        forces.zero_()
        env.episode_length_buf[0] = env.max_episode_length
        manager.compute()
        if not torch.equal(manager.get_term("time_out"), expected) or manager.get_term("base_contact").any():
            errors.append("timeout/contact separation failed at the episode deadline")
    finally:
        forces.copy_(saved_forces)
        env.episode_length_buf.copy_(saved_clock)
        manager.compute()
    return errors
