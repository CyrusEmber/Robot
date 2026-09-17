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
        # joints: the declaration names terms, not joints, so the recipe's own document is the
        # side to compare the resolved articulation against
        route = obs_protocol.task_route(task_id)
        path = params_path(route.get("line", ""), route.get("version"))
        if path is None:
            problems.append(f"{task_id}: no parameters document for line {route.get('line')!r}")
            joints = "no-doc"
        else:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            declared_joints = document.get("joint_order")
            # the document lists base names ("lf_haa"), the articulation resolves prim names
            # ("lf_haa_joint"): normalise before comparing, or every joint reads as both missing
            live_joints = [_base(name) for name in robot.joint_names]
            if declared_joints is None:
                joints = "no joint_order declared"
            elif set(live_joints) != set(declared_joints):
                problems.append(
                    f"{task_id}: live joint names differ from the recipe's joint_order"
                    f" (live-only {sorted(set(live_joints) - set(declared_joints))},"
                    f" declared-only {sorted(set(declared_joints) - set(live_joints))})"
                )
                joints = "NAME MISMATCH"
            elif live_joints != list(declared_joints):
                # Same joints, different sequence. The obs and the action follow the live
                # articulation order; the document's order is the URDF tree order the deployment
                # side reads. Nothing in the repo asserted the two agree -- check_dr_parity
                # compares the document against a *set* of usda joints -- and they do not, so
                # this is reported with both sequences rather than quietly passed.
                warnings.append(
                    f"{task_id}: live joint sequence != declared joint_order (same {len(live_joints)} joints)"
                    f"\n         live     {live_joints}"
                    f"\n         declared {list(declared_joints)}"
                )
                joints = f"{len(live_joints)} joints, SEQUENCE DIFFERS from the document"
            else:
                joints = f"{len(live_joints)} joints in declared order"
        return f"{task_id}: {'/'.join(counts)} | bodies={len(robot.body_names)} | joints={joints}"
    finally:
        env.close()


def main() -> int:
    problems: list[str] = []
    warnings: list[str] = []
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
