# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The startup lifecycle check's own cases (ARCH_PLAN 2.2, stage C1).

A gate cannot be shown by its happy path: one that only ever allows is indistinguishable from no
gate at all, and this one decides whether a *trainer process* starts. So every case below is a
rule of 2.2 with a synthetic directory behind it, and the two properties a reader cannot see from
the code get their own cases:

* **a refusal is evidence, not silence** -- the trainer's T0 is on disk with the verdict before
  the refusal is raised, so a refused launch is distinguishable from one that never happened;
* **nothing is defaulted** -- an unreadable index, an unregistered task, a line with no lifecycle
  entry and an unresolved source checkpoint all refuse. "Not known" is never "active".

The synthetic index is built on the fly: a case needs a retired line (the real directory has none,
and 2.1a forbids retiring one to make a test pass) and a case needs to move the clock without
waiting for a date.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.runrecord import lifecycle  # noqa: E402
from rl_exp.tools.runrecord import manifest as M  # noqa: E402

MAIN = "lizard/main"
SIDE = "lizard/parkour"
TASK = "Lizard-Rough-v14"
SIDE_TASK = "Lizard-Parkour-Climb-v1"
MAIN_RECIPE = "teacher-v14@1"
SIDE_RECIPE = "climb-v1@1"
_TASKS = {MAIN_RECIPE: TASK, SIDE_RECIPE: SIDE_TASK}

NOTICE_DAY = _dt.date(2026, 9, 16)
DUE_DAY = _dt.date(2026, 10, 15)

_real_source_checkpoint = lifecycle.source_checkpoint


class _AgentCfg:
    """The agent-config fields the gate reads, without an rsl_rl config object."""

    def __init__(self, *, resume: bool = False, load_run: str | None = None, load_checkpoint: str | None = None):
        self.resume = resume
        self.load_run = load_run
        self.load_checkpoint = load_checkpoint


def _entry(**over) -> dict:
    entry = {"status": "active", "successor": None, "retired_at": None, "reason": None, "deprecation": None}
    entry.update(over)
    return entry


def _retired(successor: str | None = "lizard/baseline") -> dict:
    return _entry(status="retired", successor=successor, retired_at="2026-09-16", reason="superseded")


def _tree(tmp: pathlib.Path, *, lines: dict, recipes: dict) -> pathlib.Path:
    """A synthetic repo root whose ``rl_exp/versions`` holds both index halves."""
    root = tmp / "repo"
    versions = root / "rl_exp" / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    (versions / "lines.json").write_text(
        json.dumps({"format": 1, "revision": 1, "lines": lines}), encoding="utf-8"
    )
    (versions / "recipes.json").write_text(
        json.dumps(
            {
                "format": 1,
                "recipes": {
                    key: {
                        "line": line,
                        "env_cfg_entry": "pkg.mod:Cfg",
                        "agent_entry": "pkg.mod:Agent",
                        "legacy_task_version": None,
                    }
                    for key, line in recipes.items()
                },
                "tasks": {task: key for key, task in _TASKS.items() if key in recipes},
            }
        ),
        encoding="utf-8",
    )
    return root


def _active_tree(tmp: pathlib.Path) -> pathlib.Path:
    return _tree(tmp, lines={MAIN: _entry(), SIDE: _entry()}, recipes={MAIN_RECIPE: MAIN, SIDE_RECIPE: SIDE})


def _retired_tree(tmp: pathlib.Path, key: str) -> pathlib.Path:
    return _tree(tmp / key, lines={MAIN: _retired(), SIDE: _entry()}, recipes={MAIN_RECIPE: MAIN, SIDE_RECIPE: SIDE})


def _gate(tmp: pathlib.Path, **over):
    """Run the gate against a synthetic directory; the source resolution is pinned per case."""
    directory = over.pop("directory", None) or _active_tree(tmp)
    kwargs = {
        "task": TASK,
        "argv": ["train.py", "--task", TASK],
        "agent_cfg": _AgentCfg(),
        "log_dir": tmp / "logs" / "2026-09-16_00-00-00",
        "root": directory,
        "today": NOTICE_DAY,
    }
    declared_line = over.pop("declared_line", None)
    if declared_line is not None:
        kwargs["declared_line"] = declared_line
    kwargs.update(over)
    return lifecycle.startup_check(**kwargs)


def main() -> int:
    """Run every case; each one asserts a rule that would otherwise rot unenforced."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = pathlib.Path(tmp_dir)
        failures.extend(_identity_cases(tmp))
        failures.extend(_retired_cases(tmp))
        failures.extend(_flag_and_announcement_cases(tmp))
        failures.extend(_trainer_cases(tmp))

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"lifecycle startup gate: {len(failures)} case(s) wrong")
        return 1
    print("  refusals fired, refusals left evidence, and the record keeps its own verdict")
    print("LIFECYCLE_STARTUP_OK")
    return 0


def _identity_cases(tmp: pathlib.Path) -> list[str]:
    """Identity comes from the directory, and every missing piece refuses."""
    problems: list[str] = []
    verdict, evidence = _gate(tmp)
    if not (
        verdict.allowed
        and evidence["line"] == MAIN
        and evidence["recipe"] == MAIN_RECIPE
        and evidence["status"] == "active"
    ):
        problems.append(f"an active line must proceed with its identity recorded: {verdict!r} {evidence!r}")

    invented = _active_tree(tmp / "invented")
    verdict, _ = _gate(tmp, directory=invented, task="Lizard-Invented-v99")
    if verdict.allowed or "not in the recipe map" not in verdict.reason:
        problems.append(f"a task with no recipe must be refused, got {verdict!r}")

    dangling = _tree(tmp / "dangling", lines={MAIN: _entry()}, recipes={MAIN_RECIPE: "lizard/ghost"})
    verdict, _ = _gate(tmp, directory=dangling)
    if verdict.allowed or "no lifecycle entry" not in verdict.reason:
        problems.append(f"a line with no lifecycle entry must not read as active, got {verdict!r}")

    mangled = tmp / "mangled" / "repo"
    (mangled / "rl_exp" / "versions").mkdir(parents=True)
    (mangled / "rl_exp" / "versions" / "recipes.json").write_text("{}", encoding="utf-8")
    verdict, _ = _gate(tmp, directory=mangled)
    if verdict.allowed or "not usable" not in verdict.reason:
        problems.append(f"an unreadable index must refuse, got {verdict!r}")

    # two answers to "which line is this" cannot both be describing this launch
    verdict, _ = _gate(tmp, declared_line=SIDE)
    if verdict.allowed or "identity disagreement" not in verdict.reason:
        problems.append(f"a declared line that contradicts the map must be refused, got {verdict!r}")
    verdict, _ = _gate(tmp, declared_line=MAIN)
    if not verdict.allowed:
        problems.append(f"a declared line that agrees with the map must proceed, got {verdict!r}")
    return problems


def _retired_cases(tmp: pathlib.Path) -> list[str]:
    """The 2.2 table, on a line that is actually retired."""
    problems: list[str] = []
    retired = _retired_tree(tmp, "retired")

    verdict, _ = _gate(tmp, directory=retired)
    if verdict.allowed or "successor" not in verdict.reason:
        problems.append(f"new work on a retired line must be refused with its successor, got {verdict!r}")

    verdict, _ = _gate(tmp, directory=retired, agent_cfg=_AgentCfg(resume=True))
    if verdict.allowed or "--allow_retired_resume" not in verdict.reason:
        problems.append(f"a resume on a retired line must be refused without the flag, got {verdict!r}")

    continuation = ["train.py", "--task", TASK, "--resume", "--allow_retired_resume"]
    lifecycle.source_checkpoint = lambda *a, **k: "/logs/run/model_9.pt"
    try:
        verdict, evidence = _gate(
            tmp,
            directory=retired,
            agent_cfg=_AgentCfg(resume=True, load_run="run", load_checkpoint="model_9.pt"),
            argv=continuation,
        )
        if not verdict.allowed or evidence["source_checkpoint"] is None:
            problems.append(f"an explicit continuation with a resolved source must proceed: {verdict!r}")
        if evidence["drop_curriculum_state"]:
            problems.append("--allow_retired_resume must never drop the curriculum state")

        lifecycle.source_checkpoint = lambda *a, **k: None
        verdict, _ = _gate(tmp, directory=retired, agent_cfg=_AgentCfg(resume=True), argv=continuation)
        if verdict.allowed:
            problems.append("--allow_retired_resume without a resolved source must be refused")

        # a resolver that blows up is "unknown", and unknown is not permission
        lifecycle.source_checkpoint = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        verdict, _ = _gate(tmp, directory=retired, agent_cfg=_AgentCfg(resume=True), argv=continuation)
        if verdict.allowed:
            problems.append("a failing source resolution must refuse, not allow")
    finally:
        lifecycle.source_checkpoint = _real_source_checkpoint
    return problems


def _flag_and_announcement_cases(tmp: pathlib.Path) -> list[str]:
    """Flag misuse refuses; an announcement warns and never blocks."""
    problems: list[str] = []
    verdict, _ = _gate(tmp, argv=["train.py", "--allow_retired_resume"])
    if verdict.allowed or "needs a resume" not in verdict.reason:
        problems.append(f"the continuation flag without a resume must be refused, got {verdict!r}")

    verdict, _ = _gate(tmp, argv=["train.py", "--drop_curriculum_state"])
    if verdict.allowed or "cold start" not in verdict.reason:
        problems.append(f"--drop_curriculum_state without a resume must be refused, got {verdict!r}")

    if not lifecycle.flag_in(["train.py", "--allow_retired_resume=true"], "--allow_retired_resume"):
        problems.append("an =true spelling of a flag must count as the flag")
    if lifecycle.flag_in(["train.py", "--allow_retired_resume_typo"], "--allow_retired_resume"):
        problems.append("a flag whose name only starts the same must not count")

    announced = _tree(
        tmp / "announced",
        lines={
            MAIN: _entry(
                deprecation={
                    "notice": "new work goes to lizard/baseline",
                    "declared_at": "2026-09-16",
                    "retire_not_before": {"kind": "date", "not_before": "2026-10-15"},
                }
            ),
            SIDE: _entry(),
        },
        recipes={MAIN_RECIPE: MAIN, SIDE_RECIPE: SIDE},
    )
    verdict, evidence = _gate(tmp, directory=announced, today=DUE_DAY)
    if not verdict.allowed or not verdict.warn or not evidence["retirement_due"]:
        problems.append(f"a due announcement must warn and still proceed: {verdict!r} {evidence!r}")
    verdict, evidence = _gate(tmp, directory=announced, today=NOTICE_DAY)
    if verdict.warn or evidence["retirement_due"]:
        problems.append(f"an announcement before its condition must not warn: {verdict!r}")

    revision_condition = _tree(
        tmp / "revision_condition",
        lines={
            MAIN: _entry(
                deprecation={
                    "notice": "x",
                    "declared_at": "2026-09-16",
                    "retire_not_before": {"kind": "registry_revision", "at_least": 2},
                }
            ),
            SIDE: _entry(),
        },
        recipes={MAIN_RECIPE: MAIN, SIDE_RECIPE: SIDE},
    )
    due = {_gate(tmp, directory=revision_condition, today=day)[1]["retirement_due"] for day in (NOTICE_DAY, DUE_DAY)}
    if due != {False}:
        problems.append(f"a revision condition must not depend on the clock: {due}")
    return problems


def _trainer_cases(tmp: pathlib.Path) -> list[str]:
    """The trainer-side half: ``begin`` records the verdict, and a refusal is raised *and* recorded.

    ``begin`` is the trainer's own call site (the fork patch calls it before ``gym.make``), so
    these cases run it for real, with a synthetic directory patched in -- the real one has no
    retired line to refuse. The dirty-tree override is set because this checkout is dirty while
    the change is being written; it is the documented way to say so and it has its own tests.
    """
    problems: list[str] = []
    os.environ["RL_ALLOW_DIRTY_TREE"] = "offline test: the gate's own cases"
    try:
        log_dir = tmp / "logs" / "active_run"
        ctx = M.begin(
            log_dir=log_dir,
            task=TASK,
            argv=["train.py", "--task", TASK],
            env_cfg=_env_cfg(),
            agent_cfg=_AgentCfg(),
        )
        manifest = json.loads(ctx.manifest_path.read_text(encoding="utf-8"))
        recorded = manifest["declaration"].get("lifecycle")
        if not recorded or recorded.get("allowed") is not True or recorded.get("line") != MAIN:
            problems.append(f"T0 must carry the lifecycle verdict verbatim, got {recorded!r}")
        if recorded and recorded.get("directory_sha256") != lifecycle.read_index()["digests"]:
            problems.append("T0 must bind the directory by digest, not only by revision number")

        # the verdict sits inside the T1 payload: editing it afterwards is detectable
        before = M.t1_digest(manifest)
        manifest["declaration"]["lifecycle"]["line"] = SIDE
        if M.t1_digest(manifest) == before:
            problems.append("editing the recorded lifecycle must change the T1 digest")

        # a refused launch: the verdict reaches T0, then the launch stops
        refused = _retired_tree(tmp, "refused")
        live_read_index = lifecycle.read_index
        lifecycle.read_index = lambda *a, **k: live_read_index(refused)
        try:
            refused_log = tmp / "logs" / "refused_run"
            try:
                M.begin(
                    log_dir=refused_log,
                    task=TASK,
                    argv=["train.py", "--task", TASK],
                    env_cfg=_env_cfg(),
                    agent_cfg=_AgentCfg(),
                )
            except RuntimeError as err:
                if "refused to start" not in str(err):
                    problems.append(f"a refusal must say it refused, got {err}")
            else:
                problems.append("a retired line must refuse the launch before anything is built")
            written = json.loads((refused_log / M.MANIFEST_NAME).read_text(encoding="utf-8"))
            verdict = written["declaration"].get("lifecycle") or {}
            if verdict.get("allowed") is not False or "successor" not in (verdict.get("reason") or ""):
                problems.append(f"a refused launch must leave its verdict in T0, got {verdict!r}")
            if not written.get("failures"):
                problems.append("a refused launch must record the refusal, not only raise it")
        finally:
            lifecycle.read_index = live_read_index

        problems.extend(_verify_row_cases())
    finally:
        os.environ.pop("RL_ALLOW_DIRTY_TREE", None)
    return problems


def _verify_row_cases() -> list[str]:
    """The ``verify`` row: a refusal blocks, an invented status fails, an absent verdict is
    unknown, and a directory that has moved on is reported rather than re-judged."""
    problems: list[str] = []
    cases = [
        ("refusal blocks", {"allowed": False, "reason": "retired line", "status": "retired"}, "失败", True),
        ("no verdict recorded", None, "未知", False),
        ("invented status", {"allowed": True, "status": "deprecated"}, "失败", True),
    ]
    for label, evidence, expected, blocking in cases:
        raised: list[str] = []
        manifest = {"declaration": {"lifecycle": evidence}} if evidence is not None else {"declaration": {}}
        rows = M._verify_lifecycle(manifest, raised)
        if rows[0]["result"] != expected:
            problems.append(f"verify row ({label}): expected {expected}, got {rows[0]!r}")
        if bool(raised) != blocking:
            problems.append(f"verify row ({label}): blocking={bool(raised)}, expected {blocking}")

    live = lifecycle.read_index()
    recorded = {
        "allowed": True,
        "status": "active",
        "line": MAIN,
        "directory_revision": live["revision"],
        "directory_sha256": {"lines": "moved-on", "recipes": "moved-on"},
    }
    raised = []
    rows = M._verify_lifecycle({"declaration": {"lifecycle": recorded}}, raised)
    if rows[0]["result"] != "未知" or raised or rows[0]["required"]:
        problems.append(f"a moved directory is a note, not a block and not a pass: {rows[0]!r}")

    recorded["directory_sha256"] = live["digests"]
    raised = []
    rows = M._verify_lifecycle({"declaration": {"lifecycle": recorded}}, raised)
    if rows[0]["result"] != "通过" or raised:
        problems.append(f"an unchanged directory must confirm the recorded verdict: {rows[0]!r}")
    return problems


def _env_cfg():
    """A minimal env cfg: the fields the T0 declaration reads, and a declared recipe line."""

    class _Cfg:
        params_version = "v14"
        params_line = MAIN
        seed = 42
        decimation = 4

        class sim:  # noqa: N801 - the shape the record reads
            dt = 0.005

        class scene:  # noqa: N801
            num_envs = 64

    return _Cfg()


if __name__ == "__main__":
    sys.exit(main())
