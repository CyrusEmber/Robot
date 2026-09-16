# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The launcher's cases, and phase C's cross-check (ARCH_PLAN 2.4 C2/C3).

C3 asks the two entries to *each* bind what they read and then be compared, because an entry
that only inherits the other's answer has no evidence chain of its own. So the cases here are:
what the launcher refuses, what it records, and whether the record it produces for a task
matches, field for field, the lifecycle verdict the trainer's T0 carries for the same task --
which is what "the two entries cannot answer differently" has to mean in practice.

The comparison is only meaningful if both sides are produced for the same directory. The
launcher reads the configured one; the trainer's ``begin`` reads it too, through the same
module, so a case that relocates the directory (``RL_RECIPE_DIR``) moves both or neither.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools import launch_recipe  # noqa: E402
from rl_exp.tools.runrecord import lifecycle  # noqa: E402
from rl_exp.tools.runrecord import manifest as M  # noqa: E402
from rl_exp.tools.verify import lifecycle_entry_fixture as fixture_entry  # noqa: E402

TASK = "Lizard-Rough-v14"


def main() -> int:
    """Run every case; each one asserts something a reader cannot see from the happy path."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = pathlib.Path(tmp_dir)
        problems.extend(_happy_path())
        problems.extend(_refusals(tmp))
        problems.extend(_cross_check(tmp))
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        print(f"launcher: {len(problems)} case(s) wrong")
        return 1
    print("  the launcher refuses what the directory refuses, and matches the trainer's T0")
    print("LAUNCHER_OK")
    return 0


def _happy_path() -> list[str]:
    """An active task: allowed, with the identity, the built entries and the golden recorded."""
    problems: list[str] = []
    record = launch_recipe.plan(TASK, argv=["launch_recipe.py", "--task", TASK], num_envs=64, seed=7)
    if not record["allowed"]:
        return [f"{TASK} must be launchable from an active line: {record['reason']}"]
    if record["recipe"] != "teacher-v14@1" or record["lifecycle"]["line"] != "lizard/main":
        problems.append(f"the directory's own identity must be recorded: {record['identity']!r}")
    declared = lifecycle.read_index()["recipes"]["recipes"][record["recipe"]]["env_cfg_entry"]
    if record["recipe_entry"]["env_cfg_entry"] != declared:
        problems.append(f"the declared entry must be recorded verbatim: {record['recipe_entry']!r}")
    if not record["golden"].get("golden_digest"):
        problems.append(f"the golden comparison must be recorded, got {record['golden']!r}")
    if record["lifecycle"]["directory_sha256"] != lifecycle.read_index()["digests"]:
        problems.append("the record must name the directory it was read from, by digest")
    if record["lifecycle"]["operation"] != "new_train":
        problems.append(f"a launch without --resume is new work, got {record['lifecycle']['operation']!r}")
    resumed = launch_recipe.plan(TASK, argv=["launch_recipe.py", "--resume"], resume=True, load_run=".*")
    if resumed["lifecycle"]["operation"] != "resume":
        problems.append("--resume must read as a resume (the table treats the two differently)")
    return problems


def _refusals(tmp: pathlib.Path) -> list[str]:
    """What the launcher must not let through, including a fixture directory that is retired."""
    problems: list[str] = []
    invented = launch_recipe.plan("Lizard-Invented-v99", argv=["launch_recipe.py"])
    if invented["allowed"] or "not in the recipe map" not in invented["reason"]:
        problems.append(f"an unregistered task must be refused: {invented.get('reason')!r}")

    fixture = tmp / "retired"
    fixture_entry.build(
        fixture, retire="lizard/main", announce=None, notice_until=None, today=None, successor=None
    )
    os.environ[lifecycle.INDEX_DIR_ENV] = str(fixture)
    try:
        record = launch_recipe.plan(TASK, argv=["launch_recipe.py", "--task", TASK])
        if record["allowed"] or "successor" not in record["reason"]:
            problems.append(f"a retired line must refuse the launch: {record.get('reason')!r}")
        if record["lifecycle"]["status"] != "retired":
            problems.append(f"the refusal must carry the status it read: {record.get('lifecycle')!r}")
        # and the fixture is what was judged, not this checkout
        if record["lifecycle"]["directory_sha256"] == lifecycle.read_index(_REPO)["digests"]:
            problems.append("the fixture directory must be the one judged")
    finally:
        os.environ.pop(lifecycle.INDEX_DIR_ENV, None)
    return problems


FIELDS = ("operation", "task", "recipe", "line", "status", "directory_revision", "directory_sha256")


def _compare(launcher: dict, trainer: dict) -> list[str]:
    """What the two entries disagree on: phase C's cross-check, kept callable so it can be falsified.

    Args:
        launcher: the ``lifecycle`` evidence :func:`rl_exp.tools.launch_recipe.plan` recorded.
        trainer: the ``declaration.lifecycle`` the trainer's T0 carries.

    Returns:
        One line per disagreement.
    """
    return [
        f"{field}: launcher {launcher.get(field)!r} != trainer {trainer.get(field)!r}"
        for field in ("declared_params_line", *FIELDS)
        if launcher.get(field) != trainer.get(field)
    ]


def _cross_check(tmp: pathlib.Path) -> list[str]:
    """C3: the launcher's record and the trainer's T0 verdict, for the same directory.

    The trainer's side is produced by the real call site (``manifest.begin``, which the fork
    patch calls before ``gym.make``), not by a copy of its logic.
    """
    problems: list[str] = []
    argv = ["train.py", "--task", TASK, "--num_envs", "64"]
    record = launch_recipe.plan(TASK, argv=argv, num_envs=64)
    if not record["allowed"]:
        return [f"the cross-check needs an allowed launch first: {record['reason']}"]

    os.environ["RL_ALLOW_DIRTY_TREE"] = "offline test: the cross-check needs a launch record"
    try:
        log_dir = tmp / "logs" / "cross_check"
        ctx = M.begin(log_dir=log_dir, task=TASK, argv=argv, env_cfg=_env_cfg(), agent_cfg=_agent_cfg())
        written = json.loads(ctx.manifest_path.read_text(encoding="utf-8"))["declaration"]["lifecycle"]
    finally:
        os.environ.pop("RL_ALLOW_DIRTY_TREE", None)

    problems.extend(f"the two entries disagree: {line}" for line in _compare(record["lifecycle"], written))

    # the comparison has to be able to fail: a single field moved on either side is a difference
    doctored = {**written, "line": "lizard/parkour"}
    if not _compare(record["lifecycle"], doctored):
        problems.append("a differing field slipped through the cross-check")
    return problems


def _env_cfg():
    """The env cfg the trainer's T0 reads: declared line and version, nothing else used here."""

    class _Cfg:
        params_version = "v14"
        params_line = "lizard/main"
        seed = 42
        decimation = 4

        class sim:  # noqa: N801
            dt = 0.005

        class scene:  # noqa: N801
            num_envs = 64

    return _Cfg()


def _agent_cfg():
    """An agent config with the fields the trainer's T0 and the gate read."""

    class _Agent:
        resume = False
        load_run = None
        load_checkpoint = None
        max_iterations = 3000
        experiment_name = "lizard_rough_teacher_v14"
        seed = 42
        device = "cuda:0"

        def to_dict(self):
            return {"experiment_name": self.experiment_name, "seed": self.seed}

    return _Agent()


if __name__ == "__main__":
    sys.exit(main())
