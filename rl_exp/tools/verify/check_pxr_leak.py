# -*- coding: utf-8 -*-
"""P001/P003 gate: the resolved task cfg chain must stay pxr-clean (no sim).

``train.py`` walks this chain during hydra compose, BEFORE AppLauncher starts Kit:
``load_cfg_from_registry`` reads each task's ``env_cfg_entry_point`` out of the gym
registry and **constructs** the class. If anything on that path drags pip usd-core pxr
(site-packages/pxr) into ``sys.modules``, Kit boots with two mismatched USD builds sharing
the same version tag and dies with "No to_python (by-value) converter found" (P001:
omni.kit.usd.mdl TfNotice wrapper; P003: omni.physx UsdTimeCode/GfVec3f).

So the chain is modelled the way the trainer walks it -- registry entry -> construct --
rather than as a hand-written list of modules to import. Two things that an import-only
check cannot see, and this one can:

* **what the registry points at today.** The entry points were switched from the version
  class modules to the generated classes in ``rl_exp.tasks.recipe_tasks`` (ARCH_PLAN 2.4
  C2). A list of module names written down by hand keeps checking the old modules and stays
  green while the entry moves out from under it.
* **``__post_init__`` side effects.** A cfg is built pre-Kit, but the env it describes is
  built after Kit is up, and work that only belongs to the second half sometimes lands in
  the first. The leak this gate was extended for (2026-09-18) was exactly that:
  ``components.terrain`` -> ``terrain_split_probe.install`` -> ``isaaclab.terrains.utils``
  -> ``from pxr import UsdGeom``, reached from ``__post_init__``, invisible to any check
  that stops at the import surface.

The judgement is deliberately one bit -- *did pxr enter ``sys.modules``* -- because it needs
no list of poison modules to stay true (the poison has moved twice already: P001
``ray_caster``, P003 ``envs.mdp.commands``, P004 ``isaaclab.terrains``). Everything else this
file prints is evidence for whoever has to fix it: the import that requested the poison family
and the stack that asked for it, so the offender is named here instead of being looked up in
``docs/pitfalls.md``. The window is watched rather than asserted over because the first
request is what carries the stack; ``test_pxr_leak_gate.py`` pins that the judgement and the
attribution still fire on a poisoned construction.

Run this after ANY change to env cfg / mdp module imports or to what a cfg does while it is
being constructed; it is part of run_offline_checks.bat.

Usage: python check_pxr_leak.py
"""

import sys
import traceback

from rl_exp.tools.verify.check_cfg_lock import registered_tasks, resolve_entry

#: The family whose arrival pre-Kit is the failure. ``pxr`` is the poison; ``isaacsim`` is
#: watched too because reaching it pre-Kit is the same mistake caught one import earlier.
POISON = ("pxr", "isaacsim")

#: Evidence only, never a judgement: which sim/USD runtime modules the construction newly
#: imported. A package root (``isaaclab.terrains``) is a legitimate cfg import while its
#: runtime submodules are not, and only the stack tells those apart -- hence a print, not a rule.
_RUNTIME_HINT = (
    "pxr",
    "isaacsim",
    "omni",
    "isaaclab.sim",
    "isaaclab.sensors",
    "isaaclab.scene_data",
    "isaaclab.terrains",
)


class LeakWatch:
    """The first request for the poison family inside a watched window, with its stack."""

    def __init__(self, poison: tuple[str, ...] = POISON) -> None:
        self.poison = tuple(poison)
        self.requested: str | None = None
        self.stack: str = ""

    def find_spec(self, fullname, path=None, target=None):
        if self.requested is None and (fullname in self.poison or fullname.startswith("pxr.")):
            self.requested = fullname
            self.stack = "".join(traceback.format_stack()[:-1])
        return None


def watch() -> LeakWatch:
    """Start watching for the poison family; close with :func:`stop_watch`."""
    watcher = LeakWatch()
    sys.meta_path.insert(0, watcher)
    return watcher


def stop_watch(watcher: LeakWatch) -> None:
    """Remove a watcher installed by :func:`watch`."""
    sys.meta_path.remove(watcher)


def leaked() -> list[str]:
    """The poison modules present in ``sys.modules`` right now."""
    return sorted(m for m in sys.modules if m == "pxr" or m.startswith("pxr."))


def construct(spec: dict) -> None:
    """Construct one task's env cfg, and its agent cfg, the way ``load_cfg_from_registry`` does."""
    resolve_entry(spec["env"])()
    if isinstance(spec.get("agent"), str):
        resolve_entry(spec["agent"])()  # composed alongside the env cfg, same pre-kit window


def _report(watcher: LeakWatch, before: set[str]) -> None:
    print(f"check_pxr_leak: FAIL -- pxr imported pre-kit by the resolved task cfg chain: {leaked()[:5]}")
    if watcher.requested:
        print(f"  first request for the poison family: {watcher.requested}, from:")
        print("\n".join("    " + line for line in watcher.stack.splitlines()))
    touched = sorted(m for m in set(sys.modules) - before
                     if any(m == hint or m.startswith(hint + ".") for hint in _RUNTIME_HINT))
    if touched:
        print(f"  runtime modules this construction imported (evidence, not the judgement): {touched[:8]}")
    print("Hint: see pitfalls.md P001/P003/P004. In the cfg chain, an import or a __post_init__")
    print("side effect reached pip usd-core pxr -- isaaclab.terrains.* (its utils.py imports")
    print("pxr at module top), the class modules of isaaclab.sensors.ray_caster /")
    print("isaaclab.envs.mdp.commands, or isaaclab.sim.simulation_context. The cfg is built")
    print("pre-kit and the env post-kit, so work that needs those belongs behind a lazy")
    print("import that runs once Kit is up.")


def main() -> int:
    specs = registered_tasks()
    if not specs:
        print("check_pxr_leak: FAIL -- the registry resolved no rl_exp task, so nothing was checked")
        return 1
    before = set(sys.modules)
    watcher = watch()
    try:
        for spec in specs.values():
            construct(spec)
    finally:
        stop_watch(watcher)
    if leaked():
        _report(watcher, before)
        return 1
    print(f"check_pxr_leak: OK (resolved task cfg chain is pxr-clean: {len(specs)} tasks constructed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
