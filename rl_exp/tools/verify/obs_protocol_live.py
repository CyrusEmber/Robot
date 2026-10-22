# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Live observation contract (``ARCH_PLAN`` 3.1e): the running env against the declaration.

The offline halves compare the declaration with a recorded golden and with a constructed cfg.
Neither can see what the environment actually hands the policy: the manager's term order, each
term's width, the shape of the tensor, and which joints and bodies the articulation really
resolved to. Those are read here, from a reset env, and compared against the declaration --
plus the recipe's own parameters document for the joint order, since the declaration names terms,
not joints.

Usage:
    python rl_exp/tools/verify/obs_protocol_live.py --headless --tasks Lizard2-Flat-v3 ...

Exit code is 1 when any task's live contract disagrees.
"""

import argparse
import pathlib

from isaaclab.app import AppLauncher

# Before the parser because ``--naming`` offers the table's ids; the same import order the other
# diagnostics use. ``rl_exp.tasks`` pays the gym registration, which these tools already have.
from rl_exp.tasks import joint_names  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--tasks", nargs="*", default=["Lizard2-Flat-v3"])
parser.add_argument("--envs", type=int, default=2, help="envs to build (small on purpose)")
parser.add_argument("--pin", action="store_true", help="record the measured runtime joint order")
parser.add_argument("--target_config", type=pathlib.Path, default=None, help="isolated diagnostic JSON manifest (one task only; never --pin)")
parser.add_argument("--value_report", type=pathlib.Path, default=None,
                    help="probe nonzero policy values without physics steps; isolated fixed-base zero-gain target only")
parser.add_argument("--naming", default=None, choices=sorted(joint_names.NAMINGS),
                    help="which words the spawned body carries: 'shared' = every leg one root set (every "
                         "asset today), 'split' = the front/rear rename. Declared, and checked against the "
                         "spawned bodies (a declared foot has to exist as the naming's chain-end link)")
parser.add_argument("--reason", default=None, help="why the order is being recorded (required with --pin)")
parser.add_argument(
    "--all-tasks",
    action="store_true",
    help="only check that every declared task's asset has a pinned order (reads files, builds nothing)",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
if args_cli.value_report:
    if not args_cli.target_config or args_cli.envs != 1 or len(args_cli.tasks) != 1 or args_cli.pin or args_cli.all_tasks:
        parser.error("--value_report requires one isolated target/environment/task, without --pin/--all-tasks")
    if args_cli.value_report.exists() or args_cli.value_report.with_suffix(args_cli.value_report.suffix + ".source.py").exists():
        parser.error("--value_report output already exists")
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import isaaclab_tasks  # noqa: F401,E402
import yaml  # noqa: E402

from rl_exp.tasks import obs_protocol  # noqa: E402

_REPO = pathlib.Path(__file__).resolve().parents[3]


def _base(joint_name: str) -> str:
    """A joint's base name: the documents list ``lf_haa``, the articulation resolves ``lf_haa_joint``."""
    return joint_name[: -len("_joint")] if joint_name.endswith("_joint") else joint_name


PARSER_EPILOGUE = (
    "  The runtime joint order is not the recipe's joint_order: this script compares the live"
    " articulation against the measured order pinned in versions/joint_order_runtime.json,"
    " and only reports the recipe's own order (URDF tree order) as a warning."
)


def pin(asset: str, task_id: str, joints: list[str], bodies: int, reason: str) -> None:
    """Record a measured runtime order (``--pin --reason``): the deliberate act, not a refresh.

    Writing lives here, reading lives in :mod:`rl_exp.tasks.obs_protocol`, so the check and the
    pin cannot disagree about which file holds the measured order.
    """
    import datetime as _dt
    import json

    path = obs_protocol.RUNTIME_ORDERS
    document = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"format": 1, "assets": {}}
    previous = (document.setdefault("assets", {}).get(asset) or {}).get("joint_order")
    document["assets"][asset] = {
        "measured_at": _dt.date.today().isoformat(),
        "measured_on": task_id,
        "body_count": bodies,
        "joint_order": joints,
        "reason": reason,
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state = "unchanged" if previous == joints else "changed"
    print(f"  PINNED {asset}: {len(joints)} joints ({state}); reason: {reason}")


def params_path(line: str, version: str | None) -> pathlib.Path | None:
    """The recipe's parameters document: ``<line>/vN/<basename>_params.yaml``, or the line's own."""
    line_dir = _REPO / "rl_exp" / "versions" / line
    basename = f"{line_dir.name}_params.yaml"
    candidates = [line_dir / basename] if version is None else [line_dir / version / basename, line_dir / basename]
    return next((path for path in candidates if path.is_file()), None)


def value_problems(observations: dict) -> list[str]:
    """Reject non-finite values even when the tensor layout agrees."""
    import torch

    return [f"group {group} contains non-finite observations"
            for group, tensor in observations.items() if not torch.isfinite(tensor).all()]


def compare_values(actual, expected, label: str) -> float:
    """Check a policy slice against independent state/action inputs [SI units]."""
    import torch

    if actual.shape != expected.shape or not torch.isfinite(actual).all() or not torch.isfinite(expected).all():
        raise ValueError(f"{label}: non-finite values or shape mismatch")
    error = float((actual - expected).abs().max())
    if error > 1.e-6:
        raise ValueError(f"{label}: value/order mismatch ({error})")
    return error


def probe_values(live, cfg, target: dict, out: pathlib.Path) -> None:
    """Inject distinguishable joint states [rad, rad/s] and actions; never step physics."""
    import json
    import torch
    import warp as wp
    from rl_exp.tools.runrecord import binding

    robot, manager = live.scene["robot"], live.observation_manager
    if not robot.is_fixed_base or not cfg.scene.robot.spawn.rigid_props.disable_gravity:
        raise ValueError("value probe requires fixed base and disabled gravity")
    for actuator in cfg.scene.robot.actuators.values():
        if actuator.stiffness != 0. or actuator.damping != 0.:
            raise ValueError("value probe requires zero gains")
    terms = list(manager.active_terms["policy"])
    expected_terms = ["base_lin_vel", "base_ang_vel", "projected_gravity", "velocity_commands",
                      "joint_pos", "joint_vel", "actions"]
    if terms != expected_terms or cfg.observations.policy.enable_corruption:
        raise ValueError("value probe requires the deterministic seven-term policy")
    term_cfgs = manager._group_obs_term_cfgs["policy"]
    if len(term_cfgs) != len(terms) or len(manager.group_obs_term_dim["policy"]) != len(terms):
        raise ValueError("value probe term configuration/dimension count mismatch")
    if any(term.history_length or term.modifiers or term.noise for term in term_cfgs):
        raise ValueError("value probe does not support history/modifiers/noise")
    runtime = list(robot.joint_names)
    channels = [name for term in live.action_manager.active_terms
                for name in live.action_manager.get_term(term)._joint_names]
    if len(channels) != len(runtime) or set(channels) != set(runtime):
        raise ValueError("value probe requires exactly one action per joint")
    command = live.command_manager.get_command("base_velocity")
    original = {"q": robot.data.joint_pos.torch.clone(), "dq": robot.data.joint_vel.torch.clone(),
                "action": live.action_manager.action.clone(), "command": command.clone()}
    start_steps = live._sim_step_counter
    source = pathlib.Path(__file__)
    source_bytes = source.read_bytes()
    report = {"completed": False, "scope": "state injection; no tracking, load or rollout verdict",
              "target_binding": target, "manifest_sha256": binding.sha256_file(pathlib.Path(target["source"])),
              "code_sha256": binding.sha256_bytes(source_bytes), "runtime_joint_order": runtime,
              "action_order": channels, "samples": [], "negative_controls": [],
              "transforms": {name: {"clip": term.clip,
                  "scale": term.scale.cpu().tolist() if isinstance(term.scale, torch.Tensor) else term.scale}
                  for name, term in zip(terms, term_cfgs)}}
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Different signatures in runtime and action order expose permutations hidden by zero poses.
        index = torch.arange(1, len(runtime) + 1, device=live.device).unsqueeze(0)
        for sign in (-1., 1.):
            q, dq = sign * index * .001, -sign * index * .002
            limits = robot.data.joint_pos_limits.torch
            if not ((q >= limits[..., 0]) & (q <= limits[..., 1])).all():
                raise ValueError("value probe position outside actual joint limits")
            action = sign * torch.flip(index, dims=[1]) * .003
            robot.write_joint_state_to_sim(q, dq)
            live.action_manager.process_action(action)
            command.copy_(torch.tensor([[.17, -.23, .31]], device=live.device) * sign)
            # Read the backend too: a successful cache assignment alone is insufficient.
            backend_q = wp.to_torch(robot.root_view.get_dof_positions()).clone()
            backend_dq = wp.to_torch(robot.root_view.get_dof_velocities()).clone()
            compare_values(backend_q, q, "backend position")
            compare_values(backend_dq, dq, "backend velocity")
            expected = {"base_lin_vel": torch.zeros((1, 3), device=live.device),
                        "base_ang_vel": torch.zeros((1, 3), device=live.device),
                        "projected_gravity": torch.tensor([[0., 0., -1.]], device=live.device),
                        "velocity_commands": command.clone(),
                        "joint_pos": q - robot.data.default_joint_pos.torch,
                        "joint_vel": dq - robot.data.default_joint_vel.torch, "actions": action}
            observation = manager.compute_group("policy")
            errors, slices, offset = {}, {}, 0
            for name, term_cfg, dim in zip(terms, term_cfgs, manager.group_obs_term_dim["policy"]):
                value = expected[name].clone()
                if term_cfg.clip is not None:
                    value = value.clamp(*term_cfg.clip)
                if term_cfg.scale is not None:
                    value *= term_cfg.scale
                end = offset + int(dim[0])
                errors[name] = compare_values(observation[:, offset:end], value, name)
                slices[name] = [offset, end]
                offset = end
            if offset != observation.shape[1] or value_problems({"policy": observation}):
                raise ValueError("unexpected or non-finite policy values")
            report["samples"].append({"sign": sign, "q_rad": q.cpu().tolist(),
                "dq_rad_s": dq.cpu().tolist(), "raw_action": action.cpu().tolist(),
                "backend_q_rad": backend_q.cpu().tolist(), "backend_dq_rad_s": backend_dq.cpu().tolist(),
                "command": command.cpu().tolist(), "observation": observation.cpu().tolist(),
                "slices": slices, "max_error_by_term": errors})
            # Corrupt real computed slices; same shapes and sets must not hide a wrong value/order.
            for name in ("joint_pos", "joint_vel", "actions"):
                begin, end = slices[name]
                correct = observation[:, begin:end]
                broken = correct.flip([1])
                try:
                    compare_values(broken, correct, name)
                except ValueError:
                    report["negative_controls"].append(f"{sign}:{name}:permuted")
                else:
                    raise ValueError("permuted nonzero slice was accepted")
        if live._sim_step_counter != start_steps:
            raise ValueError("value probe unexpectedly advanced environment physics")
        report.update(completed=True, added_physics_steps=0,
                      default_joint_pos=robot.data.default_joint_pos.torch.cpu().tolist(),
                      default_joint_vel=robot.data.default_joint_vel.torch.cpu().tolist())
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        robot.write_joint_state_to_sim(original["q"], original["dq"])
        live.action_manager.process_action(original["action"])
        command.copy_(original["command"])
        with out.with_suffix(out.suffix + ".source.py").open("xb") as handle:
            handle.write(source_bytes)
        with out.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write("\n")


def check_task(task_id: str, problems: list[str], warnings: list[str],
               naming: dict[str, tuple[str, ...]] = joint_names.LEGACY_NAMING) -> str:
    """Build one task's env, read its contract off the live managers, compare, and report."""
    spec = gym.spec(task_id)
    cfg = spec.kwargs["env_cfg_entry_point"]
    module_name, _, cls_name = cfg.partition(":")
    env_cfg = getattr(__import__(module_name, fromlist=[cls_name]), cls_name)()
    env_cfg.scene.num_envs = args_cli.envs
    binding = obs_protocol.load_diagnostic_target(
        args_cli.target_config, env_cfg, task_id, naming_override=args_cli.naming)
    naming = joint_names.naming_from_binding(binding)
    if args_cli.target_config and args_cli.pin:
        raise ValueError("isolated diagnostic manifests cannot pin frozen runtime orders")
    env = gym.make(task_id, cfg=env_cfg)
    try:
        obs, _ = env.reset()
        problems.extend(f"{task_id}: {problem}" for problem in value_problems(obs))
        unwrapped = env.unwrapped
        manager = unwrapped.observation_manager
        declared = {
            group: entry for group, entry in obs_protocol.groups_for(task_id).items() if not entry.get("dropped")
        }
        widths = {} if args_cli.target_config else obs_protocol.recorded_dims(task_id) or {}
        live_groups = set(manager.active_terms)
        if live_groups != set(declared):
            problems.append(f"{task_id}: live groups {sorted(live_groups)} != declared {sorted(declared)}")
        counts = []
        for group, entry in declared.items():
            expected = obs_protocol.live_terms_for(task_id, group)
            actual = list(manager.active_terms[group])
            if actual != expected:
                problems.append(f"{task_id}: group {group} live term order {actual} != declared {expected}")
                continue
            dims = [int(dim[0]) for dim in manager.group_obs_term_dim[group]]
            total = sum(dims)
            counts.append(f"{group}={total}")
            if group not in widths:
                counts[-1] += "(unapproved)"
            elif widths[group] != total:
                problems.append(f"{task_id}: group {group} live width {total} != approved {widths[group]}")
            shape = tuple(obs[group].shape)
            if shape != (args_cli.envs, total):
                problems.append(f"{task_id}: group {group} tensor {shape} != ({args_cli.envs}, {total})")
            # per-term widths are the part a group total cannot see: two terms can trade width
            problems.extend(
                f"{task_id}: group {group} term {name} is {dim} wide" for name, dim in zip(actual, dims) if dim <= 0
            )
        # the feet the declaration names must exist as bodies on the articulation it really built
        try:
            feet = obs_protocol.feet_for(task_id, "extero")
        except obs_protocol.ProtocolError:
            feet = ()
        robot = unwrapped.scene["robot"]
        obs_protocol.validate_diagnostic_runtime(binding, env_cfg, robot,
            unwrapped.scene["contact_forces"], unwrapped.action_manager)
        if args_cli.target_config:
            feet = tuple(joint_names.LEGS)
            print(f"  BOUND_FEET source={binding['source']} expected={binding['end_links']}")
        for foot in feet:
            # The body a declared foot names comes off the binding: ``_foot`` is one body's word, and the
            # declared ring term is the protocol's (its own vocabulary is frozen per protocol version).
            end = joint_names.end_link(foot, naming)
            if end not in robot.body_names:
                problems.append(f"{task_id}: declared foot {foot!r} has no {end} body in {robot.body_names}")
        # joints: the declaration names terms, not joints. Two different orders are in play --
        # the recipe's joint_order (URDF tree order, what the deployment side reads) and the
        # articulation order the obs and the action use. Only the second one has to be pinned,
        # because a permutation there misaligns every checkpoint and nothing used to record it.
        if args_cli.target_config:
            order = binding.get("runtime_joint_order")
            if order is None:
                problems.append(f"{task_id}: manifest requires runtime_joint_order for live order check")
            elif list(robot.joint_names) != order:
                problems.append(f"{task_id}: live joints differ from manifest runtime_joint_order")
            if args_cli.value_report:
                if problems:
                    raise ValueError("refusing value injection after layout/binding failure")
                probe_values(unwrapped, env_cfg, binding, args_cli.value_report)
            return f"{task_id}: {'/'.join(counts)} | four bound feet checked | source={binding['source']}"
        route = obs_protocol.task_route(task_id)
        path = params_path(route.get("line", ""), route.get("version"))
        live_joints = [_base(name) for name in robot.joint_names]
        if path is None:
            problems.append(f"{task_id}: no parameters document for line {route.get('line')!r}")
            joints = "no-doc"
        else:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            asset = (document.get("robot") or {}).get("usd_path")
            declared_joints = document.get("joint_order")
            if args_cli.pin:
                if not args_cli.reason:
                    problems.append(f"{task_id}: --pin needs --reason (pinning without a stated reason is a refresh)")
                else:
                    pin(asset, task_id, live_joints, len(robot.body_names), args_cli.reason)
            pinned = obs_protocol.runtime_joint_order(task_id)
            if pinned is None:
                problems.append(
                    f"{task_id}: asset {asset!r} has no measured runtime joint order -- run this with"
                    f" --pin --reason '<why>' once, then the order is checked from then on"
                )
                joints = f"nothing pinned for {asset}"
            elif pinned != live_joints:
                problems.append(
                    f"{task_id}: live joint order differs from the measured one for {asset!r}"
                    f"\n         live   {live_joints}"
                    f"\n         pinned {pinned}"
                )
                joints = f"{len(live_joints)} joints, MISMATCH against the measured order"
            else:
                joints = f"{len(live_joints)} joints match the measured runtime order"
            if declared_joints is not None and list(declared_joints) != live_joints:
                # informational: the recipe's order is the URDF contract, not this one
                warnings.append(
                    f"{task_id}: recipe joint_order is the URDF tree order and differs from the"
                    f" runtime order (not a fault; both are recorded)"
                )
        return f"{task_id}: {'/'.join(counts)} | bodies={len(robot.body_names)} | joints={joints}"
    finally:
        env.close()


def coverage(problems: list[str]) -> int:
    """Every declared task's asset must carry a measured runtime joint order.

    File-level only, no sim: this answers "is the order written down for everything we would
    train", which is the part of the contract that can be checked without a run.
    """
    tasks = obs_protocol.declaration().get("tasks") or {}
    assets: dict[str, list[str]] = {}
    for task_id in sorted(tasks):
        asset = obs_protocol.usd_path(task_id)
        if asset is None:
            problems.append(f"{task_id}: no usd_path in the recipe's parameters document")
            continue
        assets.setdefault(asset, []).append(task_id)
        if obs_protocol.runtime_joint_order(task_id) is None:
            problems.append(
                f"{task_id}: asset {asset!r} has no measured runtime joint order"
                f" -- measure it once with --pin --reason '<why>'"
            )
    for asset, task_ids in sorted(assets.items()):
        order = obs_protocol.runtime_joint_order(task_ids[0]) or []
        print(f"  OK   {asset}: {len(order)} joints pinned, {len(task_ids)} declared task(s)")
    return len(tasks)


def main() -> int:
    problems: list[str] = []
    warnings: list[str] = []
    if args_cli.all_tasks:
        covered = coverage(problems)
        for problem in problems:
            print(f"  FAIL {problem}")
        if problems:
            print(f"OBS_PROTOCOL_LIVE_FAILED ({len(problems)} problem(s))")
            return 1
        print(f"OBS_PROTOCOL_LIVE_OK ({covered} declared task(s), all pinned; no env built)")
        return 0
    lines = []
    if args_cli.target_config and (args_cli.all_tasks or len(args_cli.tasks) != 1):
        raise ValueError("--target_config requires exactly one --tasks task and no --all-tasks")
    naming = joint_names.LEGACY_NAMING
    for task_id in args_cli.tasks:
        try:
            lines.append(check_task(task_id, problems, warnings, naming))
        except Exception as err:  # a task that cannot be built is a problem, never a skip
            problems.append(f"{task_id}: cannot build or reset: {err!r}")
    for line in lines:
        print(f"  OK   {line}")
    for warning in warnings:
        print(f"  WARN {warning}")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print(f"OBS_PROTOCOL_LIVE_FAILED ({len(problems)} problem(s), {len(warnings)} warning(s))")
        return 1
    print(f"OBS_PROTOCOL_LIVE_OK ({len(lines)} task(s), {len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    code = main()
    if code:
        # Kit close may terminate with status 0; preserve real CLI rejection first.
        import os
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    simulation_app.close()
    raise SystemExit(code)
