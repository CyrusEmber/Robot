# -*- coding: utf-8 -*-
"""Negative control for check_pxr_leak.py: a poisoned construction must still be judged a leak.

The gate is two halves that fail independently, so both are pinned here:

* the **judgement** -- "did pxr enter ``sys.modules``" must be able to come out clean for a
  real construction and dirty for a poisoned one. A gate that only ever ran the real chain
  would look green while it judged nothing (that is precisely the shape of the bug it was
  rewritten for: the old one imported modules and never constructed a cfg).
* the **attribution** -- the failing window must name the import that requested the poison
  and carry the stack of the construction that asked for it. The judgement alone tells you a
  leak happened, not which ``__post_init__`` did it, and looking that up by hand is what
  ``docs/pitfalls.md`` P004 cost the last time.

The poisoned half runs last on purpose: importing pxr is one-way in a process, and this whole
check is one process (each check is).
"""

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")
import check_pxr_leak as gate  # noqa: E402

PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def _poisoned_cfg():
    """A cfg-shaped stand-in for P004: construction alone imports a runtime module."""
    from isaaclab.utils.configclass import configclass

    @configclass
    class PoisonedCfg:
        def __post_init__(self):
            import isaaclab.terrains.terrain_generator  # noqa: F401  (pulls pxr at import)

    return PoisonedCfg


def main() -> int:
    specs = gate.registered_tasks()
    check("the registry resolves tasks to construct", bool(specs), "no rl_exp task registered")
    if not specs:
        return 1

    # -- clean half: a real task, watched, must stay clean -------------------------------
    task_id, spec = next(iter(specs.items()))
    watcher = gate.watch()
    try:
        gate.construct(spec)
    finally:
        gate.stop_watch(watcher)
    check(f"a real task constructs clean ({task_id})", not gate.leaked(), str(gate.leaked()[:3]))
    check("its construction requested no poison", watcher.requested is None, str(watcher.requested))

    # -- poisoned half: the same window around a construction that imports the runtime ----
    watcher = gate.watch()
    try:
        _poisoned_cfg()()
    finally:
        gate.stop_watch(watcher)
    check("a poisoned construction is judged a leak", bool(gate.leaked()), "the judgement no longer fires")
    check(
        "the leak is attributed to the requesting import and the frame that asked for it",
        watcher.requested is not None and "test_pxr_leak_gate" in watcher.stack,
        f"requested={watcher.requested!r} stack={'names this file' if 'test_pxr_leak_gate' in watcher.stack else 'does not name this file'}",
    )

    if PROBLEMS:
        print(f"\ntest_pxr_leak_gate: {len(PROBLEMS)} problem(s)")
        for problem in PROBLEMS:
            print(f"  - {problem}")
        return 1
    print("\ntest_pxr_leak_gate: OK (judgement fires on a poisoned construction and names it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
