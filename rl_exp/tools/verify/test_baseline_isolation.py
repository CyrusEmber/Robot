# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""A registered baseline task resolves while the main recipe line is unavailable.

``versions/lizard/baseline/PLAN.md`` §与其它线的边界 states the contract: that line's recipe code
does not import another line's cfg or mdp. A contract about imports is checked by imports, in a
process where the main line has not been imported yet -- which is why this is its own check rather
than an assertion inside a gate that already imported everything (the suite gives every check its
own interpreter).

Three phases, because they answer different questions:

* **blocked** -- the baseline tasks resolve while every main-line module raises; the blocker's own
  exception (not any ``ImportError``) is what fails a deliberate import, so "isolation held" cannot
  be a missing dependency in disguise;
* **baseline then main** -- resolving the main line afterwards must not swap the baseline classes
  under the caller: one recipe has one expression, and the runtime answer to "which class is this
  task" must not depend on the order things were imported in;
* **main then baseline, fresh module** -- the reverse order, in a module whose cache is empty, with
  the main constructor watched: the baseline line must never be built through it.

The allowlist below is fixed and states why each module is allowed. It is asserted as an *equality*
with what the process actually loaded, in both directions: a module the baseline needs but the list
forbids fails loudly, and a permission nobody uses is a permission to drop rather than a licence to
keep.
"""

from __future__ import annotations

import importlib
import importlib.abc
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

MARKER = "BASELINE_ISOLATION_BLOCKED"
TASKS_MODULE = "rl_exp.tasks.recipe_tasks"
BASELINE_NAMES = ("BaselineFlatEnvCfg", "BaselineFlatEnvCfg_PLAY")
MAIN_LINE = "lizard/main"
MAIN_NAME = "LizardRoughTeacherEnvCfg_V14"

# name -> why a registered baseline task is allowed to drag it in
ALLOWED = {
    "rl_exp.tasks": "the package itself: gym registrations only, it imports no cfg",
    "rl_exp.tasks.agents": "the package holding the runner cfgs",
    "rl_exp.tasks.agents.rsl_rl_ppo_cfg": "the runner cfg the baseline task registers",
    "rl_exp.tasks.baseline_env_cfg": "this line's own wiring and action split",
    "rl_exp.tasks.baseline_mdp": "this line's own kernels (the two it copies from teacher_mdp)",
    "rl_exp.tasks.baseline_recipe": "this line's declaration: its elements, table and constructor",
    "rl_exp.tasks.play_utils": "shared PLAY wiring, deliberately dependency-free (its own docstring)",
    "rl_exp.tasks.recipe_factory": "the shared class-construction mechanism, isaaclab-only",
    "rl_exp.tasks.recipe_params": "the shared parameter loader: one document per caller, per line",
    "rl_exp.tasks.recipe_tasks": "the entry seam itself: resolves one line's classes on demand",
}


class Blocked(ImportError):
    """The blocker's own error, so the self-proof matches a type no missing dependency raises."""


def _blocker(hits: list[str]) -> importlib.abc.MetaPathFinder:
    """A finder that refuses every ``rl_exp.tasks`` module the baseline's closure does not name.

    Default-deny, and by name: a hand-written list of forbidden modules only catches the imports
    someone thought of, which is the failure mode this check exists for.
    """

    class BlockMain(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):  # noqa: ANN001, ARG002 - abc signature
            if fullname == "rl_exp.tasks" or fullname.startswith("rl_exp.tasks."):
                if fullname not in ALLOWED:
                    hits.append(fullname)
                    raise Blocked(f"{MARKER}: {fullname} is not part of the baseline's closure")
            return None

    return BlockMain()


def _loaded() -> set[str]:
    """The ``rl_exp.tasks`` modules this interpreter has imported."""
    return {name for name in sys.modules if name == "rl_exp.tasks" or name.startswith("rl_exp.tasks.")}


def _entry_point(task_id: str) -> type:
    """The env cfg class a task's registration resolves to."""
    import gymnasium as gym
    from isaaclab.utils.string import string_to_callable

    return string_to_callable(gym.spec(task_id).kwargs["env_cfg_entry_point"])


def _phase_blocked() -> dict[str, type]:
    """Resolve both baseline tasks with the main line unavailable; return the classes."""
    already = _loaded()
    assert not already - set(ALLOWED), (
        f"this interpreter already imported {sorted(already - set(ALLOWED))} before the check: the"
        " isolation claim needs a process that has not imported the main line (the suite gives"
        " every check its own interpreter)"
    )
    hits: list[str] = []
    blocker = _blocker(hits)
    sys.meta_path.insert(0, blocker)
    try:
        import gymnasium as gym  # noqa: F401 - imported before the registry is read
        import rl_exp.tasks  # noqa: F401 - registers the tasks
        from isaaclab.utils.string import string_to_callable

        from rl_exp.tasks import recipe_tasks

        for task in ("Lizard-Baseline-Flat-v1", "Lizard-Baseline-Flat-Play-v1"):
            cfg = _entry_point(task)()
            agent_cfg = string_to_callable(gym.spec(task).kwargs["rsl_rl_cfg_entry_point"])()
            assert cfg.scene.terrain.terrain_type == "plane"
            assert cfg.events.reset_robot_joints.params["position_range"] == (1.0, 1.0)
            assert agent_cfg.actor.hidden_dims == [256, 128, 128]

        # The blocker has to be *the* reason an import fails. Without this, a broken environment
        # (a missing dependency, a path problem) would make the leaks invisible and the check green.
        try:
            importlib.import_module("rl_exp.tasks.recipe")
        except Blocked as err:
            assert MARKER in str(err), err
        else:
            raise AssertionError(
                "the blocker did not fire on rl_exp.tasks.recipe -- the isolation claim is untested"
            )
        assert hits == ["rl_exp.tasks.recipe"], f"unexpected blocked imports: {hits}"

        resolved = {name: getattr(recipe_tasks, name) for name in BASELINE_NAMES}
        assert all(getattr(recipe_tasks, name) is cls for name, cls in resolved.items()), (
            "a baseline class was rebuilt on a second read: this module must hand back one object"
        )
        assert all(string_to_callable(f"{TASKS_MODULE}:{name}") is cls for name, cls in resolved.items()), (
            "the registry string and the module attribute disagree about the baseline class"
        )
        leaked = _loaded() - set(ALLOWED)
        assert not leaked, f"main-line modules were imported while blocked: {sorted(leaked)}"
        unused = set(ALLOWED) - _loaded()
        assert not unused, (
            f"{sorted(unused)} are allowed but unused -- the allowlist is what the baseline needs,"
            " not what it might: drop the permission or use it"
        )
    finally:
        sys.meta_path.remove(blocker)
    return resolved


def _phase_baseline_then_main(baseline: dict[str, type]) -> None:
    """Resolving the main line afterwards must leave the baseline classes alone."""
    from rl_exp.tasks import recipe_tasks

    main = getattr(recipe_tasks, MAIN_NAME)
    assert main.__name__ == MAIN_NAME and main is getattr(recipe_tasks, MAIN_NAME)
    for name, cls in baseline.items():
        assert getattr(recipe_tasks, name) is cls, (
            f"{name} was swapped for another object while the main line resolved -- a class the"
            " runtime hands out must not depend on import order (one recipe, one expression)"
        )


def _phase_main_then_baseline() -> None:
    """Main first, in a fresh module, with the main constructor watched.

    The first two phases cannot answer this: by then the baseline names are cached, so the main
    line's resolution has nothing to overwrite. Dropping the module from ``sys.modules`` and
    importing it again gives a cache that is empty -- the same state a process that resolved a main
    task first would be in.
    """
    from rl_exp.tasks import recipe

    del sys.modules[TASKS_MODULE]
    fresh = importlib.import_module(TASKS_MODULE)
    built: list[tuple[str | None, str]] = []
    original = recipe.recipe_class

    def watched(version, **kwargs):  # noqa: ANN001 - transparent wrapper
        built.append((kwargs.get("line"), version))
        return original(version, **kwargs)

    recipe.recipe_class = watched
    try:
        main = getattr(fresh, MAIN_NAME)
        baseline = {name: getattr(fresh, name) for name in BASELINE_NAMES}
    finally:
        recipe.recipe_class = original

    assert main.__name__ == MAIN_NAME and main.__module__ == "rl_exp.tasks.recipe_factory"
    assert [line for line, _ in built] == [MAIN_LINE], (
        f"resolving the main line and the baseline line built {built} -- the baseline line must be"
        " built by its own module's constructor, never by the main line's"
    )
    for name, cls in baseline.items():
        assert cls.__name__ == name and getattr(fresh, name) is cls


def main() -> None:
    baseline = _phase_blocked()
    _phase_baseline_then_main(baseline)
    _phase_main_then_baseline()
    print("BASELINE_ISOLATION_OK")


if __name__ == "__main__":
    main()
