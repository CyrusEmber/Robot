# -*- coding: utf-8 -*-
"""Startup probe for a baseline task: read what the env actually does, before training.

A recipe that says 0.5 m/s and a command manager that issues something else look
identical in the config file. This probe therefore reads the values the env produces --
the issued command tensor, the resolved observation groups, the per-term reward
magnitudes, the randomization that is actually in force -- and refuses to pass if any of
them disagrees with the recipe.

Run before the first training run of a baseline version:

    python rl_exp\\tools\\verify\\baseline_probe.py --task Lizard-Baseline-Flat-v1

Exit code is 0 only when every check passed; the reward magnitudes and the action
diagnostics are printed for judgement, not asserted (an action mean is not a pass/fail
criterion: it depends on joint scale, default pose and gait).
"""

import argparse
import pathlib
import re

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--task", default="Lizard-Baseline-Flat-v1")
parser.add_argument("--num_envs", type=int, default=16)
parser.add_argument("--steps", type=int, default=60, help="control steps to observe")
parser.add_argument(
    "--random-actions",
    action="store_true",
    help="excite the interface with uniform actions instead of holding zero: the action and "
    "joint diagnostics are meaningless without excitation, but the robot then falls, so the "
    "reward magnitudes are no longer nominal. Run both ways.",
)
parser.add_argument(
    "--head-press",
    action="store_true",
    help="after the standing rollout, lower the base until the head chain is --press-depth m below "
    "the ground and watch whether the recipe's head-contact termination fires (and at what force)",
)
parser.add_argument("--press-depth", type=float, default=0.05,
                    help="how far below the ground to push the lowest head-chain mesh point [m]")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import isaaclab_tasks  # noqa: F401, E402
from isaaclab.utils.math import quat_apply  # noqa: E402

from rl_exp.tools.diagnose.diag_metrics import (  # noqa: E402
    MESH_CHECK_BODIES, body_load_n, collision_mesh_dir, foot_ids, mesh_min_z, mesh_vertices,
    pad_point_clouds, tilt_cos,
)
from rl_exp.tools.verify.baseline_runtime import (  # noqa: E402
    joint_reset_errors, material_errors, resolve_task_cfg, termination_errors,
)
from rl_exp.tasks import obs_protocol, recipe_params  # noqa: E402

PROBLEMS: list[str] = []
EXPECTED_COMMAND = (0.5, 0.0, 0.0)
# every randomization event the framework base registers: the recipe turns all of them
# off by name, because deleting the c_k clock alone leaves two interval events running
DR_EVENTS = (
    "physics_material",
    "add_base_mass",
    "base_com",
    "base_external_force_torque",
    "push_robot",
)
# `reset_robot_joints` is deliberately NOT above: it is not randomization to be removed but the
# joint reset itself -- in this IsaacLab it is the only writer of joint state at reset, since
# `Articulation.reset` clears actuator state and wrenches only. The recipe keeps it and pins its
# ranges instead, so it is asserted as "kept and pinned" below. That the write actually lands is
# a rollout question, not a config question: `reset_check.py` proves it.


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def term_values(manager, name: str):
    """Per-term values of a manager, robust to how the fork stores them.

    Reward and termination managers have moved their per-term tensors around across
    versions; a probe that dies on the internal name would report nothing at all.
    """
    for attr in ("_step_reward", "_step_values"):
        table = getattr(manager, attr, None)
        names = getattr(manager, "_term_names", None)
        if table is not None and names is not None and name in names:
            return table[:, names.index(name)]
    sums = getattr(manager, "_episode_sums", None)
    if sums is not None and name in sums:
        return sums[name]
    return None


def main() -> int:
    cfg = resolve_task_cfg(args_cli.task)
    cfg.scene.num_envs = args_cli.num_envs
    env = gym.make(args_cli.task, cfg=cfg)
    unwrapped = env.unwrapped
    num_envs = args_cli.num_envs
    dt = getattr(unwrapped, "step_dt", None)

    # --- the expectations come from the task's OWN document, not from this file -------------
    # A probe that hardcodes one line's fixed command and one line's obs width cannot check any
    # other line, and the version-driven values are the point: this line's window is a RANGE and
    # its obs is width-derived (review 2026-09-22).
    params = recipe_params.load(cfg.params_line, cfg.params_version)
    command_ranges = params["commands"]
    body_patterns = params.get("names", {})
    approved_dims = obs_protocol.recorded_dims(args_cli.task)
    print(f"[probe] task {args_cli.task} -> line {cfg.params_line} {cfg.params_version}")
    print(f"  command ranges lin_vel_x {command_ranges['lin_vel_x']} lin_vel_y {command_ranges['lin_vel_y']} "
          f"ang_vel_z {command_ranges['ang_vel_z']}")
    print(f"  approved obs widths for this asset: {approved_dims}")

    # --- events: the randomization must be off, by name and in effect --------------
    print("[probe] events")
    for event_name in DR_EVENTS:
        event = getattr(unwrapped.cfg.events, event_name, "absent")
        check(f"events/{event_name}-off", event is None, f"{event!r} is still wired")
    reset_base = getattr(unwrapped.cfg.events, "reset_base", None)
    check("events/reset_base-kept", reset_base is not None, "no reset event: nothing places the robot")
    # the joint reset must be kept AND pinned: kept, because a respawned env otherwise keeps the
    # joint state it fell with; pinned, because the stock ranges scale the default pose by 0.5-1.5
    reset_joints = getattr(unwrapped.cfg.events, "reset_robot_joints", None)
    check("events/reset-joints-kept", reset_joints is not None,
          "no joint reset event: every episode after the first starts from the previous one's pose")
    if reset_joints is not None:
        func_name = getattr(reset_joints.func, "__name__", None)
        check("events/reset-joints-is-the-reset", func_name == "reset_joints_by_scale",
              f"func is {func_name!r}, not the default-pose writer this probe asserts on")
        pinned = (tuple(reset_joints.params.get("position_range", ())) == (1.0, 1.0)
                  and tuple(reset_joints.params.get("velocity_range", ())) == (0.0, 0.0))
        check("events/reset-joints-pinned", pinned,
              f"position_range {reset_joints.params.get('position_range')} / "
              f"velocity_range {reset_joints.params.get('velocity_range')}: anything but (1,1)/(0,0) "
              "randomizes the spawn (equal bounds are exact under rand*(b-a)+a)")
    # reset_base places the robot: its own ranges must be zero on every axis it declares, not
    # merely present -- the probe used to check the term exists and never read its numbers
    base_nonzero = {
        f"{key}.{axis}": rng
        for key in ("pose_range", "velocity_range")
        for axis, rng in (reset_base.params.get(key, {}) if reset_base is not None else {}).items()
        if tuple(rng) != (0.0, 0.0)
    }
    check("events/reset-base-ranges-zero", not base_nonzero,
          f"the spawn is still randomized: {base_nonzero}")

    obs, _ = env.reset()
    robot = unwrapped.scene["robot"]
    masses = robot.data.body_mass.torch
    check(
        "events/no-mass-randomization",
        bool((masses == masses[0]).all()),
        f"base body mass differs across envs (tolerance 0 expected): {masses[:, 0][:4]}",
    )
    errors = joint_reset_errors(robot)
    check("events/actual-joint-reset", not errors, "; ".join(errors))
    errors = material_errors(robot)
    check("events/live-materials-uniform", not errors, "; ".join(errors))
    errors = termination_errors(unwrapped)
    check("terminations/contact-and-timeout-behavior", not errors, "; ".join(errors))
    # Clear the diagnostic injection before any rollout observations are collected.
    obs, _ = env.reset()

    # --- command: read the tensor the env issues, not the config -------------------
    print("[probe] command")
    cmd_term = unwrapped.command_manager.get_term("base_velocity")
    observed = cmd_term.command[:, :3]
    tol = 1e-6
    for axis, column in (("lin_vel_x", 0), ("lin_vel_y", 1), ("ang_vel_z", 2)):
        lo, hi = command_ranges[axis]
        values = observed[:, column]
        if abs(hi - lo) < tol:
            check(f"command/{axis}-fixed-at-{lo:g}", bool((values - lo).abs().max() < tol),
                  f"issued {values[:4].tolist()} != {lo}")
        else:
            inside = bool(((values >= lo - tol) & (values <= hi + tol)).all())
            check(f"command/{axis}-inside-{lo:g}-to-{hi:g}", inside,
                  f"issued {values[:4].tolist()} leaves the declared range")
            if inside and axis == "lin_vel_x":
                spread = float(values.max() - values.min())
                check("command/sampled-per-env", spread > 1e-9,
                      f"every env got the same command ({float(values[0]):+.3f}); a range that is not "
                      "sampled per env is a fixed command wearing a range's clothes")
                print(f"  issued x range: min {float(values.min()):+.3f} max {float(values.max()):+.3f} "
                      f"spread {spread:.3f} m/s over {num_envs} envs")
    standing_envs = getattr(cmd_term, "is_standing_env", None)
    check("command/no-standing-envs", standing_envs is None or not bool(standing_envs.any()), f"{standing_envs}")
    heading = getattr(cmd_term, "is_heading_env", None)
    check("command/no-heading-envs", heading is None or not bool(heading.any()), f"{heading}")

    command_stable = True
    action_rows = []
    action_deltas = []
    term_counts = {"time_out": 0, "fall": 0}
    reward_sums: dict[str, torch.Tensor] = {}
    reward_halves: dict[str, list[torch.Tensor]] = {}
    joint_means = {"|q|": [], "|qd|": [], "|tau|": [], "at_limit_low": [], "at_limit_high": []}
    torque_rows: list[torch.Tensor] = []  # per-joint |tau| over the whole rollout, not one frame
    # --- standing: the zero-action rollout is the only one here that measures the asset and the
    # PD rather than a policy. Height says whether it holds itself up, the per-body load says what
    # carries it, per-joint |qd|/|tau| say with which joints -- and whether any of them is dead.
    # Skipped under --random-actions: a falling robot's numbers describe the fall, not the stance.
    standing = not args_cli.random_actions
    joint_names = list(robot.joint_names)
    body_names = list(robot.body_names)
    contact_sensor = unwrapped.scene.sensors.get("contact_forces")
    load_readable = (contact_sensor is not None
                     and contact_sensor.data.net_forces_w.torch.shape[1] == len(body_names))
    spawn_z = robot.data.root_pos_w.torch[:, 2].mean().item()
    mesh_present = [name for name in MESH_CHECK_BODIES if name in body_names]
    mesh_ids = [body_names.index(name) for name in mesh_present]
    mesh_corners = pad_point_clouds([mesh_vertices(collision_mesh_dir() / f"{name}_collision.obj")
                                     for name in mesh_present]).to(unwrapped.device) if mesh_present else None
    z_rows: list[torch.Tensor] = []
    tilt_rows: list[torch.Tensor] = []
    load_rows: list[torch.Tensor] = []
    mesh_rows: list[torch.Tensor] = []
    qd_rows: list[torch.Tensor] = []
    reward_names = list(getattr(unwrapped.reward_manager, "_term_names", []))
    act_dim = unwrapped.action_manager.total_action_dim
    soft_limits = robot.data.soft_joint_pos_limits.torch
    span = (soft_limits[..., 1] - soft_limits[..., 0]).clamp_min(1e-6)
    last_action = None
    for step in range(args_cli.steps):
        if args_cli.random_actions:
            actions = torch.empty(num_envs, act_dim, device=unwrapped.device).uniform_(-1.0, 1.0)
        else:
            actions = torch.zeros(num_envs, act_dim, device=unwrapped.device)
        with torch.inference_mode():
            obs, rew, term, trunc, _ = env.step(actions)
        # the issued command must stay inside the declared box for the whole rollout: the box is the
        # document's, not a fixed point (a range that drifts outside its own declaration is worse
        # than a fixed command, because the evaluator grades against the declaration)
        for axis, column in (("lin_vel_x", 0), ("lin_vel_y", 1), ("ang_vel_z", 2)):
            low, high = command_ranges[axis]
            value = cmd_term.command[:, column]
            if not bool(((value >= low - 1e-6) & (value <= high + 1e-6)).all()):
                command_stable = False
        action = unwrapped.action_manager.action
        action_rows.append(action.abs().clone())
        if last_action is not None:
            action_deltas.append((action - last_action).abs().clone())
        last_action = action.clone()
        term_counts["time_out"] += int((trunc & ~term).sum())
        term_counts["fall"] += int((term & ~trunc).sum())
        # both ends, not just the lower one: the old expression took .abs() of a gap that is
        # already non-negative and compared it to the lower limit alone, so a joint pinned at
        # its upper limit read as free
        at_limit_low = (robot.data.joint_pos.torch - soft_limits[..., 0]) / span < 0.05
        at_limit_high = (soft_limits[..., 1] - robot.data.joint_pos.torch) / span < 0.05
        joint_means["|q|"].append(robot.data.joint_pos.torch.abs().mean().reshape(1))
        joint_means["|qd|"].append(robot.data.joint_vel.torch.abs().mean().reshape(1))
        joint_means["|tau|"].append(robot.data.applied_torque.torch.abs().mean().reshape(1))
        joint_means["at_limit_low"].append(at_limit_low.float().mean().reshape(1))
        joint_means["at_limit_high"].append(at_limit_high.float().mean().reshape(1))
        torque_rows.append(robot.data.applied_torque.torch.abs().mean(dim=0).clone())
        if standing:
            z_rows.append(robot.data.root_pos_w.torch[:, 2].mean().reshape(1))
            # the angle to straight down is acos of the same quantity the fall criteria read
            # (shared with the fixed-window evaluator, so both judge the same scale)
            tilt_rows.append(
                tilt_cos(robot.data.projected_gravity_b.torch).acos().mean().rad2deg().reshape(1)
            )
            qd_rows.append(robot.data.joint_vel.torch.abs().amax(dim=0).clone())
            if load_readable:
                load_rows.append(contact_sensor.data.net_forces_w.torch.clone())
                mesh_rows.append(
                    mesh_min_z(robot.data.body_pos_w.torch, robot.data.body_quat_w.torch,
                               mesh_ids, mesh_corners)
                )
        for name in reward_names:
            value = term_values(unwrapped.reward_manager, name)
            if value is None:
                continue
            reward_sums[name] = reward_sums.get(name, torch.zeros_like(value)) + value
            half = 0 if step < args_cli.steps // 2 else 1
            halves = reward_halves.setdefault(name, [torch.zeros_like(value), torch.zeros_like(value)])
            halves[half] = halves[half] + value

    check("command/issued-stable-over-rollout", command_stable, "the issued command changed during the rollout")

    # --- observations -------------------------------------------------------------
    print("[probe] observations")
    groups = obs if isinstance(obs, dict) else {"policy": obs}
    check("obs/single-policy-group", sorted(groups) == ["policy"], f"{sorted(groups)}")
    policy = groups.get("policy")
    live_width = None if policy is None else int(policy.shape[-1])
    if approved_dims and "policy" in approved_dims:
        check(f"obs/policy-{approved_dims['policy']}-dims-as-approved", live_width == approved_dims["policy"],
              f"live {live_width} vs approved {approved_dims['policy']} "
              f"({obs_protocol.protocol_for(args_cli.task)})")
    else:
        check("obs/policy-width-approved", False,
              f"{args_cli.task}: this asset has no approved obs widths "
              "(obs_protocol_live.py --tasks <id> --pin measures them)")
    check("obs/finite", bool(torch.isfinite(policy).all()), "non-finite observation")

    # --- action interface: every joint needs exactly one channel ---------------------
    print("[probe] actions")
    am = unwrapped.action_manager
    channelled: dict[str, int] = {}
    joint_to_action: dict[str, tuple[int, float]] = {}
    offset = 0
    for term_name in am.active_terms:
        term = am.get_term(term_name)
        scale = term._scale
        scale = float(scale) if not hasattr(scale, "reshape") else float(scale.reshape(-1)[0])
        print(f"  term {term_name}: {len(term._joint_names)} joints, scale {scale}")
        for position, joint in enumerate(term._joint_names):
            channelled[joint] = channelled.get(joint, 0) + 1
            joint_to_action[joint] = (offset + position, scale)
        offset += len(term._joint_names)
    missing = sorted(set(joint_names) - set(channelled))
    doubled = sorted(joint for joint, count in channelled.items() if count > 1)
    check("actions/every-joint-channelled", not missing, f"no action term carries {missing}")
    check("actions/no-joint-in-two-terms", not doubled, f"carried twice: {doubled}")
    check("actions/dim-matches-mapping", am.total_action_dim == len(channelled),
          f"dim {am.total_action_dim} vs {len(channelled)} channelled joints")

    # --- terminations -------------------------------------------------------------
    print("[probe] terminations")
    termination_names = set(getattr(unwrapped.termination_manager, "_term_names", []))
    # the document is the expectation: every contact-gate threshold it declares has to be a live
    # term, and time_out is the framework's own
    expected_terms = {"time_out"} | {key[: -len("_threshold")] for key in params["terminations"]
                                     if key.endswith("_threshold")}
    for needed in sorted(expected_terms):
        check(f"terminations/{needed}-present", needed in termination_names, f"{sorted(termination_names)}")
    unexpected = sorted(termination_names - expected_terms)
    print(f"  declared by the yaml: {sorted(expected_terms)} | live: {sorted(termination_names)}"
          + (f" | extra live terms: {unexpected}" if unexpected else ""))
    print(f"  info episodes over {args_cli.steps} steps: {term_counts}")

    # --- diagnostics (printed, not asserted) --------------------------------------
    print(f"[probe] rewards over {args_cli.steps} steps x {num_envs} envs (per-step mean per env)")
    for name, total in sorted(reward_sums.items()):
        per_step = (total / args_cli.steps).mean().item()
        print(f"  {name:28s} {per_step:+.6f}")
    if action_rows:
        stacked = torch.stack(action_rows)
        action_abs = stacked
        print("[probe] action diagnostics (reference for 'is it moving at all')")
        print(f"  mean|a| {action_abs.mean().item():.4f}  p95 {torch.quantile(action_abs.flatten(), 0.95).item():.4f}  max {action_abs.max().item():.4f}")
        if action_deltas:
            print(f"  mean|da| {torch.stack(action_deltas).mean().item():.4f}  (adjacent-step diff)")
        print(f"  per-dim mean|a| commanded dims: {(action_abs.mean(dim=(0, 1)) > 1e-4).sum().item()}/{act_dim}")
    if standing and z_rows:
        print("[probe] standing under zero action (asset and PD, not policy)")
        z = torch.cat(z_rows)
        tilt = torch.cat(tilt_rows)
        print(f"  base z mean {z.mean().item():.4f} min {z.min().item():.4f} (spawn {spawn_z:.4f}) m   "
              f"tilt mean {tilt.mean().item():.2f} max {tilt.max().item():.2f} deg")
        # per env, not over the whole batch: body_mass is (num_envs, num_bodies), so a bare sum
        # divides the load by num_envs and reads the closure as ~1/num_envs
        weight = robot.data.body_mass.torch[0].sum().item() * 9.81
        if load_readable:
            load = body_load_n(torch.cat(load_rows))
            carriers = ", ".join(f"{body_names[i]} {load[i].item():.1f}"
                                 for i in torch.argsort(load, descending=True).tolist()
                                 if load[i].item() > 1.0)
            feet = foot_ids(body_names)
            print(f"  load per body [N] (>1 N): {carriers or 'none'}")
            print(f"  total/(m*g) {load.sum().item() / weight:.4f}  (feet only "
                  f"{load[feet].sum().item() / weight:.4f})")
            heaviest_non_foot = max((load[i].item() for i in range(len(body_names)) if i not in feet),
                                    default=0.0)
            check("load/no-non-foot-carrier", heaviest_non_foot <= 1.0,
                  f"a non-foot body carries {heaviest_non_foot:.1f} N "
                  "(head/neck/tail/belly must not take the robot's weight)")
        else:
            shape = None if contact_sensor is None else tuple(contact_sensor.data.net_forces_w.torch.shape)
            print(f"  load per body: no contact_forces sensor covering every body (shape {shape}, "
                  f"{len(body_names)} bodies) -- contact attribution is unavailable")
        if mesh_corners is not None:
            mesh_z = torch.cat(mesh_rows).min(dim=0).values
            lowest = ", ".join(f"{name} {mesh_z[i].item():+.3f}" for i, name in enumerate(mesh_present))
            print(f"  non-foot mesh lowest world z [m] (min over rollout): {lowest}")
            check("load/no-non-foot-mesh-through-floor", bool((mesh_z > 0.0).all()),
                  "a non-foot collision mesh reached z <= 0: the body is on, or through, the floor")
        else:
            check("load/mesh-bodies-present", False,
                  f"none of {MESH_CHECK_BODIES} is a body of this asset"
                  f" (bodies: {body_names})")
        qd = torch.stack(qd_rows).mean(dim=0)
        top = torch.argsort(qd, descending=True)[:5].tolist()
        print(f"  per-joint mean |qd| [rad/s], top 5: "
              + ", ".join(f"{joint_names[i]} {qd[i].item():.3f}" for i in top))
        idle = [joint_names[i] for i in torch.nonzero(qd < 1e-3).flatten().tolist()]
        print(f"  joints that never moved (mean |qd| < 1e-3 rad/s): {idle or 'none'}")
    if joint_means["|tau|"]:
        stacked_means = {key: torch.cat(values) for key, values in joint_means.items()}
        print("[probe] joint diagnostics (mean over the rollout)")
        print(
            f"  |q| {stacked_means['|q|'].mean().item():.4f} rad   "
            f"|qd| {stacked_means['|qd|'].mean().item():.4f} rad/s   "
            f"|tau| {stacked_means['|tau|'].mean().item():.4f} N.m   "
            f"near-limit low {stacked_means['at_limit_low'].mean().item() * 100:.2f}%  "
            f"high {stacked_means['at_limit_high'].mean().item() * 100:.2f}%"
        )
        # a joint that is never loaded is a wiring or limit symptom, not a policy property;
        # worth naming here so a silent dead joint cannot hide behind an average.
        # Over the whole rollout: a single frame catches a moment of unload -- or the frame right
        # after a reset, when nothing has been commanded yet -- and reads it as "this joint is dead"
        torque_per_joint = torch.stack(torque_rows).mean(dim=0)
        quiet = [robot.joint_names[i] for i in torch.nonzero(torque_per_joint < 1e-3).flatten().tolist()]
        print(f"  joints with ~zero mean |tau| over the rollout ({len(quiet)}): {quiet if quiet else 'none'}")
    if dt is not None:
        print(f"[probe] control dt {dt:.4f} s")

    # --- the head-contact gate: observe it firing, do not assume it -----------------
    # A termination that was never seen to fire is a claim about a threshold, not a measurement of
    # one (review 2026-09-22). This lowers the base until the lowest head-chain collision mesh point
    # is --press-depth m below the ground, then watches the termination and the contact force.
    if args_cli.head_press:
        print("[probe] head-contact gate (pressed)")
        patterns = body_patterns.get("head_contact_body_names") or []
        matched = [name for name in body_names
                   if any(re.fullmatch(pattern, name) for pattern in patterns)]
        collider = collision_mesh_dir()
        head_bodies = [name for name in matched if (collider / f"{name}_collision.obj").is_file()]
        # A contact gate can only act through a collider. A pattern that matches a link without one is
        # a dead entry that reads like coverage -- the same defect this repo already carries in the
        # reward's `.*_kfe` (review 2026-09-22). Naming it here is what keeps it from being inherited.
        dead = sorted(set(matched) - set(head_bodies))
        check("head/press-bodies-resolved", bool(head_bodies),
              f"the yaml's head patterns {patterns} match no body with a collision mesh")
        check("head/no-collider-less-pattern", not dead,
              f"the head patterns match {dead}, which has no collision mesh: their contact force is "
              "structurally zero, so that part of the guard can never fire")
        threshold = params["terminations"].get("head_contact_threshold")
        if head_bodies and threshold is not None:
            env.reset()
            for _ in range(max(5, args_cli.steps // 4)):
                env.step(torch.zeros((num_envs, unwrapped.action_manager.total_action_dim), device=unwrapped.device))
            corners = pad_point_clouds([mesh_vertices(collision_mesh_dir() / f"{name}_collision.obj")
                                        for name in head_bodies]).to(unwrapped.device)
            ids = [body_names.index(name) for name in head_bodies]
            def head_floor() -> float:
                """Lowest world z of the head chain's collision meshes, over all envs."""
                pose = robot.data.body_pos_w.torch[:, ids].unsqueeze(2)
                orientation = robot.data.body_quat_w.torch[:, ids].unsqueeze(2).expand(-1, -1, corners.shape[1], -1)
                world = pose + quat_apply(orientation, corners.unsqueeze(0).expand(num_envs, -1, -1, -1))
                return float(world[..., 2].min())
            drop = head_floor() + args_cli.press_depth  # positive while the head hangs above the floor
            if drop > 0.0:
                posed = robot.data.root_state_w.torch.clone()
                posed[:, 2] -= drop
                robot.write_root_pose_to_sim(posed[:, :7])
                robot.write_root_velocity_to_sim(torch.zeros((num_envs, 6), device=unwrapped.device))
                print(f"  lowered the base by {drop:.3f} m so the lowest head-chain point sits "
                      f"{args_cli.press_depth:.3f} m below the ground")
            fired_at, peak_force, steps_to_fire = None, 0.0, 0
            zero_action = torch.zeros((num_envs, unwrapped.action_manager.total_action_dim),
                                      device=unwrapped.device)
            # Lowering the base alone lands the robot on its FEET -- the legs are longer than the neck
            # is forward, so the head never reaches the floor (measured: 0.00 N with the head nominally
            # 5 cm under it). The press therefore also drives the head chain toward its limits, which
            # is what actually puts the head on the ground.
            press_action = zero_action.clone()
            chain = [name for name in joint_names if name.startswith(("chest_", "neck_"))]
            for joint in chain:
                index_scale = joint_to_action.get(joint)
                if index_scale is None:
                    continue
                index, scale = index_scale
                if scale > 0:
                    low = float(robot.data.joint_pos_limits.torch[0, joint_names.index(joint), 0])
                    press_action[0, index] = low / scale
            manager = unwrapped.termination_manager
            head_index = (manager._term_names.index("head_contact")
                          if "head_contact" in manager._term_names else None)
            for step in range(args_cli.steps):
                env.step(zero_action)
                if contact_sensor is not None:
                    peak_force = max(peak_force, contact_sensor.data.net_forces_w.torch[:, ids, :]
                                     .norm(dim=-1).max().item())
                dones = getattr(manager, "_term_dones", None)
                fired = bool(dones[:, head_index].any()) if (dones is not None and head_index is not None) else False
                if fired:
                    fired_at, steps_to_fire = step, step
                    break
            print(f"  head bodies: {head_bodies} | yaml threshold {threshold} N | "
                  f"peak head contact force seen: {peak_force:.2f} N")
            if fired_at is None:
                check("head/fires-when-pressed", False,
                      f"the head sat {-args_cli.press_depth:.2f} m below the ground for {args_cli.steps} "
                      f"steps and head_contact never fired (peak force {peak_force:.2f} N)")
            else:
                check("head/fires-when-pressed", True)
                print(f"  head_contact fired after {steps_to_fire} pressed steps; peak head force "
                      f"{peak_force:.2f} N vs threshold {threshold} N")

    env.close()
    if PROBLEMS:
        print(f"BASELINE_PROBE_FAILED ({len(PROBLEMS)})")
        return 1
    print("BASELINE_PROBE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
