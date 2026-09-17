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
    python rl_exp/tools/verify/obs_protocol_live.py --headless --tasks Lizard-Rough-v14 ...

Exit code is 1 when any task's live contract disagrees.
"""

import argparse
import pathlib

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--tasks", nargs="*", default=["Lizard-Rough-v14"])
parser.add_argument("--envs", type=int, default=2, help="envs to build (small on purpose)")
parser.add_argument("--pin", action="store_true", help="record the measured runtime joint order")
parser.add_argument("--reason", default=None, help="why the order is being recorded (required with --pin)")
parser.add_argument(
    "--all-tasks",
    action="store_true",
    help="only check that every declared task's asset has a pinned order (reads files, builds nothing)",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
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
    " articulation against the measured order pinned in versions/lizard/joint_order_runtime.json,"
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


def check_task(task_id: str, problems: list[str], warnings: list[str]) -> str:
    """Build one task's env, read its contract off the live managers, compare, and report."""
    spec = gym.spec(task_id)
    cfg = spec.kwargs["env_cfg_entry_point"]
    module_name, _, cls_name = cfg.partition(":")
    env_cfg = getattr(__import__(module_name, fromlist=[cls_name]), cls_name)()
    env_cfg.scene.num_envs = args_cli.envs
    env = gym.make(task_id, cfg=env_cfg)
    try:
        obs, _ = env.reset()
        unwrapped = env.unwrapped
        manager = unwrapped.observation_manager
        declared = {
            group: entry for group, entry in obs_protocol.groups_for(task_id).items() if not entry.get("dropped")
        }
        widths = obs_protocol.recorded_dims(task_id) or {}
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
        for foot in feet:
            if f"{foot}_foot" not in robot.body_names:
                problems.append(f"{task_id}: declared foot {foot!r} has no {foot}_foot body in {robot.body_names}")
        # joints: the declaration names terms, not joints. Two different orders are in play --
        # the recipe's joint_order (URDF tree order, what the deployment side reads) and the
        # articulation order the obs and the action use. Only the second one has to be pinned,
        # because a permutation there misaligns every checkpoint and nothing used to record it.
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
    for task_id in args_cli.tasks:
        try:
            lines.append(check_task(task_id, problems, warnings))
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
    simulation_app.close()
    raise SystemExit(code)
