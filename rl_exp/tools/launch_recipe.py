# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""New launcher (ARCH_PLAN 2.4 C2): the directory decides, then the config is built from it.

The old trainer reaches the same decision through ``manifest.begin``, and it must not be able to
answer differently from this entry, so both call ``lifecycle.startup_check`` (the frozen contract
plus one reader, not two implementations). What this file adds is the order the plan asks for --
directory, then config, then the gate, then the run -- and its own record of what it read, so
phase C's cross-check can compare the two entries for the same directory instead of trusting one.

Until the new builder (2.4 B1/B2) can compose a config from a recipe spec, the training half is
still the fork trainer, started here with the directory pinned (``RL_RECIPE_DIR``) so the run's
T0 binds the *same* directory this launcher judged. ``--launch`` is that hand-off; everything
before it is real and runs without the sim app (``--check``, the default).

    python rl_exp\\tools\\launch_recipe.py --task Lizard-Rough-v14 --num_envs 64
    python rl_exp\\tools\\launch_recipe.py --task Lizard-Rough-v14 --resume --load_run <dir> --launch
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.runrecord import lifecycle, manifest  # noqa: E402
from rl_exp.tools.runrecord import provenance as prov  # noqa: E402
from rl_exp.tools.verify import check_recipe_map  # noqa: E402

PASSTHROUGH = (
    "--num_envs",
    "--seed",
    "--max_iterations",
    "--resume",
    "--load_run",
    "--checkpoint",
    "--drop_curriculum_state",
    "--allow_retired_resume",
)


def _build(entry: str):
    """Construct what an entry point names.

    The class attribute is not readable once the configclass decorator has run (1.0), so an
    identity check has to build an instance; the same idiom the map gate's config half uses.
    """
    module_name, _, class_name = entry.partition(":")
    return getattr(importlib.import_module(module_name), class_name)()


def plan(
    task: str,
    *,
    argv: list[str] | None = None,
    num_envs: int | None = None,
    seed: int | None = None,
    max_iterations: int | None = None,
    resume: bool = False,
    load_run: str | None = None,
    checkpoint: str | None = None,
    root: pathlib.Path | None = None,
) -> dict:
    """Read the directory, build what it declares, and judge the launch before anything runs.

    Args:
        task: the gym task id to launch.
        argv: the command line; the two lifecycle flags are read from it (one reader, as in the
            trainer).
        num_envs: override for the declared env count.
        seed: override for the declared seed.
        max_iterations: override for the declared iteration count.
        resume: whether this is a resume (which the lifecycle table treats differently).
        load_run: the run selector, as the trainer's agent config carries it.
        checkpoint: the checkpoint selector.
        root: repository root whose ``rl_exp/versions`` is read, defaulting to the configured
            directory (``RL_RECIPE_DIR`` or this checkout).

    Returns:
        The launch record: the directory identity, what was built, the config-side binding, the
        golden comparison, the lifecycle verdict and the reason. Refusals are returned, not
        raised, so a caller records them (``allowed: False``).
    """
    index = lifecycle.read_index(root)
    identity = lifecycle.identity(task, index)
    record: dict = {
        "task": task,
        "argv": list(argv or []),
        "directory_revision": index.get("revision"),
        "directory_sha256": index.get("digests"),
        "identity": identity,
    }
    if identity["problems"]:
        return {**record, "allowed": False, "reason": "; ".join(identity["problems"])}

    entry = (index["recipes"].get("recipes") or {})[identity["recipe"]]
    record["recipe"] = identity["recipe"]
    record["recipe_entry"] = {
        "env_cfg_entry": entry.get("env_cfg_entry"),
        "agent_entry": entry.get("agent_entry"),
        "legacy_task_version": entry.get("legacy_task_version"),
    }
    # the config-side half of identity (A3), reused rather than re-derived: what the map declares
    # must be what the built classes carry, or this launch is not the launch the directory names.
    # The instance the binding builds is the one the plan carries -- one construction, not two.
    built: dict = {}
    binding = check_recipe_map.bind(
        {identity["recipe"]: entry}, build=lambda spec: built.setdefault(spec, _build(spec))
    )
    if binding:
        return {**record, "allowed": False, "reason": "; ".join(binding)}

    env_cfg = built[entry["env_cfg_entry"]]
    agent_cfg = _build(entry["agent_entry"])
    if num_envs is not None:
        env_cfg.scene.num_envs = num_envs
    if seed is not None:
        env_cfg.seed = seed
        agent_cfg.seed = seed
    if max_iterations is not None:
        agent_cfg.max_iterations = max_iterations
    agent_cfg.resume = bool(resume)
    if load_run is not None:
        agent_cfg.load_run = load_run
    if checkpoint is not None:
        agent_cfg.load_checkpoint = checkpoint

    record["golden"] = manifest.recipe_ref(env_cfg)
    log_root = pathlib.Path(os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name)))
    verdict, evidence = lifecycle.startup_check(
        task=task,
        argv=record["argv"],
        agent_cfg=agent_cfg,
        log_dir=None,
        log_root=log_root,
        declared_line=record["golden"].get("params_line"),
        root=root,
    )
    return {**record, "allowed": verdict.allowed, "reason": verdict.reason, "lifecycle": evidence}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", required=True, help="gym task id to launch")
    parser.add_argument("--num_envs", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max_iterations", type=int, default=None)
    parser.add_argument("--resume", action="store_true", default=False)
    parser.add_argument("--load_run", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--drop_curriculum_state", action="store_true", default=False)
    parser.add_argument("--allow_retired_resume", action="store_true", default=False)
    parser.add_argument("--record", type=pathlib.Path, default=None, help="write the launch record here")
    parser.add_argument("--launch", action="store_true", default=False,
                        help="hand off to the trainer (the sim app runs; the check above runs first)")
    parser.add_argument("--python", default=sys.executable, help="interpreter for --launch")
    args = parser.parse_args(argv)

    record = plan(
        args.task,
        argv=sys.argv,
        num_envs=args.num_envs,
        seed=args.seed,
        max_iterations=args.max_iterations,
        resume=args.resume,
        load_run=args.load_run,
        checkpoint=args.checkpoint,
    )
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=1, ensure_ascii=False))
    if not record["allowed"]:
        print(f"[launcher] refused: {record['reason']}", file=sys.stderr)
        return 2
    print(f"[launcher] {args.task} -> {record['recipe']} on {record['lifecycle']['line']} allowed")
    if not args.launch:
        return 0

    isaac_root = prov.isaac_root()
    if isaac_root is None:
        print("[launcher] no IsaacLab tree configured (paths.yaml / RL_ISAAC_ROOT); cannot launch", file=sys.stderr)
        return 1
    command = [str(args.python), "scripts/reinforcement_learning/rsl_rl/train.py", "--task", args.task]
    command += [token for flag in PASSTHROUGH for token in _passthrough(args, flag)]
    environment = {**os.environ, lifecycle.INDEX_DIR_ENV: str(lifecycle.index_root())}
    print(f"[launcher] training half is still the fork trainer: {' '.join(command)}")
    return subprocess.call(command, cwd=str(isaac_root), env=environment)


def _passthrough(args, flag: str) -> list[str]:
    """One flag, as the trainer spells it: only what the caller actually asked for.

    Args:
        args: the parsed launcher arguments.
        flag: the flag name (``--num_envs``).

    Returns:
        ``["--num_envs", "64"]``, or ``[]`` when the caller did not set it.
    """
    value = getattr(args, flag.lstrip("-"))
    if value is None or value is False:
        return []
    return [flag] if value is True else [flag, str(value)]


if __name__ == "__main__":
    sys.exit(main())
