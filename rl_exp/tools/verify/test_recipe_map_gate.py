# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Negative control for ``check_recipe_map``: every refusal must actually fire.

Two things get their own cases beyond the refusals, because reading the happy path does
not reveal them:

* ``check_recipe_map.registered`` reads ``id=`` as a keyword (that is how every call in
  ``rl_exp/tasks/__init__.py`` is written). The first version read positional args only
  and returned an empty registry, which made the gate pass for the wrong reason -- a
  parser that finds nothing looks exactly like a tree with nothing to check.
* the declared version must be a dash-separated token of the task id, so ``v1`` is not
  satisfied by ``Lizard-Rough-v14``. Substring matching would have blessed a v14 task
  mapped to a v1 recipe.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from check_recipe_map import bind, load, registered, validate  # noqa: E402

ENV_V14 = "rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V14"
AGENT_V14 = "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV14PPORunnerCfg"
LINE = "lizard/main"
TASK = "Lizard-Rough-v14"
LINES = {"lizard/main": None, "lizard/parkour": None}
REGISTERED = {TASK: {"env_cfg_entry_point": ENV_V14, "rsl_rl_cfg_entry_point": AGENT_V14}}


def _entry(**over) -> dict:
    entry = {"line": "lizard/main", "env_cfg_entry": ENV_V14, "agent_entry": AGENT_V14, "legacy_task_version": "v14"}
    entry.update(over)
    return entry


def _doc(recipes: dict, tasks: dict, fmt: int = 1) -> dict:
    return {"format": fmt, "recipes": recipes, "tasks": tasks}


CLEAN = _doc({"teacher-v14@1": _entry()}, {TASK: "teacher-v14@1"})

CASES: list[tuple[str, dict, dict, str | None]] = [
    ("registered task with no mapping", _doc({"teacher-v14@1": _entry()}, {}), REGISTERED,
     "with no recipe mapping"),
    ("mapping names an unregistered task", _doc({"teacher-v14@1": _entry()}, {TASK: "teacher-v14@1", "Lizard-Rough-v99": "teacher-v14@1"}),
     REGISTERED, "names no registered task"),
    ("mapping points at a recipe that does not exist", _doc({"teacher-v14@1": _entry()}, {TASK: "teacher-v13@1"}),
     REGISTERED, "which no recipe defines"),
    ("env entry redirected away from the registration",
     _doc({"teacher-v14@1": _entry(env_cfg_entry="rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V13")},
          {TASK: "teacher-v14@1"}), REGISTERED, "must not be redirected silently"),
    ("agent entry redirected away from the registration",
     _doc({"teacher-v14@1": _entry(agent_entry="rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardTeacherV13PPORunnerCfg")},
          {TASK: "teacher-v14@1"}), REGISTERED, "must not be redirected silently"),
    ("recipe names an undiscovered line", _doc({"teacher-v14@1": _entry(line="lizard/ghost")}, {TASK: "teacher-v14@1"}),
     REGISTERED, "is not a discovered recipe line"),
    ("recipe key without a revision", _doc({"teacher-v14": _entry()}, {TASK: "teacher-v14"}), REGISTERED,
     "must read <id>@<revision>"),
    ("recipe key with revision zero", _doc({"teacher-v14@0": _entry()}, {TASK: "teacher-v14@0"}), REGISTERED,
     "must read <id>@<revision>"),
    ("recipe omits a field", _doc({"teacher-v14@1": {"line": "lizard"}}, {TASK: "teacher-v14@1"}), REGISTERED,
     "recipe is missing"),
    ("recipe carries a run-scoped field",
     _doc({"teacher-v14@1": _entry(run_id="abc")}, {TASK: "teacher-v14@1"}), REGISTERED, "unknown fields"),
    ("legacy version is not v<N>",
     _doc({"teacher-v14@1": _entry(legacy_task_version="14")}, {TASK: "teacher-v14@1"}), REGISTERED,
     "must be null or v<N>"),
    ("v1 must not be satisfied by v14 in the task id",
     _doc({"teacher-v1@1": _entry(legacy_task_version="v1")}, {TASK: "teacher-v1@1"}), REGISTERED, "never states"),
    ("entry point is not module:qualname",
     _doc({"teacher-v14@1": _entry(agent_entry="LizardTeacherV14PPORunnerCfg")}, {TASK: "teacher-v14@1"}),
     REGISTERED, "is not module:qualname"),
    ("format changed without this gate", _doc({"teacher-v14@1": _entry()}, {TASK: "teacher-v14@1"}, fmt=2),
     REGISTERED, "format"),
    # -- shapes that must stay green ------------------------------------------------
    ("matching map", CLEAN, REGISTERED, None),
    ("v0 family: no declared version while the id says v0",
     _doc({"rough-v0@1": _entry(env_cfg_entry="rl_exp.tasks.recipe_tasks:LizardRoughEnvCfg",
                                agent_entry="rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardRoughPPORunnerCfg",
                                legacy_task_version=None)},
          {"Lizard-Velocity-Rough-v0": "rough-v0@1"}),
     {"Lizard-Velocity-Rough-v0": {"env_cfg_entry_point": "rl_exp.tasks.recipe_tasks:LizardRoughEnvCfg",
                                   "rsl_rl_cfg_entry_point": "rl_exp.tasks.agents.rsl_rl_ppo_cfg:LizardRoughPPORunnerCfg"}},
     None),
]


def _builder(versions: dict):
    """A stand-in for building an entry point: the map gives the version, or an error."""

    def build(entry: str):
        value = versions[entry]
        if isinstance(value, Exception):
            raise value
        version, line = value if isinstance(value, tuple) else (value, LINE)
        return type("Cfg", (), {"params_version": version, "params_line": line})()

    return build


BIND_CASES: list[tuple[str, dict, dict, str | None]] = [
    ("binding agrees", {"r@1": _entry()}, {ENV_V14: "v14"}, None),
    ("class carries no version", {"r@1": _entry()}, {ENV_V14: None}, "carries params_version=None"),
    ("class carries a different version", {"r@1": _entry()}, {ENV_V14: "v13"}, "carries params_version='v13'"),
    ("declared null while the class carries one", {"r@1": _entry(legacy_task_version=None)}, {ENV_V14: "v0"},
     "declared legacy_task_version=None"),
    ("entry point cannot be built", {"r@1": _entry()}, {ENV_V14: ImportError("no module named")}, "cannot build"),
    ("entry point is not a string, left to validate", {"r@1": _entry(env_cfg_entry=17)}, {}, None),
    ("right version, wrong line", {"r@1": _entry()}, {ENV_V14: ("v14", "lizard/baseline")},
     "lifecycle permissions would be read from the wrong line"),
    ("config declares no line at all", {"r@1": _entry()}, {ENV_V14: ("v14", None)}, "params_line=None"),
]


def main() -> int:
    """Run every case, then pin the registration parser against the real module."""
    failures: list[str] = []
    for label, doc, registry, expected in CASES:
        problems = validate(doc, LINES, registry)
        if expected is None:
            if problems:
                failures.append(f"{label}: expected clean, got {problems}")
        elif not any(expected in problem for problem in problems):
            failures.append(f"{label}: expected {expected!r}, got {problems}")

    for label, entries, versions, expected in BIND_CASES:
        problems = bind(entries, build=_builder(versions))
        if expected is None:
            if problems:
                failures.append(f"{label}: expected clean, got {problems}")
        elif not any(expected in problem for problem in problems):
            failures.append(f"{label}: expected {expected!r}, got {problems}")

    # the real registration module: a parser that reads nothing must not pass. The
    # expected count is derived from the declared map, not written as a literal -- a
    # literal goes stale the moment a task is added, and then this test fails for a
    # reason unrelated to the parser it exists to guard.
    real = registered()
    declared = len(load()["tasks"])
    if not real:
        failures.append("registration parser read no tasks from rl_exp/tasks/__init__.py")
    elif len(real) != declared:
        failures.append(f"registration parser read {len(real)} tasks, the map declares {declared}")
    elif not real[TASK].get("env_cfg_entry_point", "").endswith(f":{ENV_V14.split(':')[1]}"):
        # the parser's job is to read the *env* entry for this task, not to agree with one module
        # path: after the entry switch the same class is reached through recipe_tasks, and pinning
        # the module here would make this falsifier go red for a change it does not guard
        failures.append(f"registration parser mis-read {TASK}: {real[TASK]}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"recipe map falsifier: {len(failures)}/{len(CASES) + len(BIND_CASES) + 1} cases wrong")
        return 1
    print(f"  map refusals fired: {len(CASES)} map cases + {len(BIND_CASES)} binding cases + {len(real)}-task registration parse")
    print("RECIPE_MAP_GATE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
