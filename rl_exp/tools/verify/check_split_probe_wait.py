# -*- coding: utf-8 -*-
"""P005 gate: waiting for the generator module must not depend on being asked by the importer.

`terrain_split_probe.install()` runs inside a cfg's ``__post_init__`` -- during hydra compose,
before Kit has finished starting -- so it must not import ``isaaclab.terrains.terrain_generator``
itself (P004: pip pxr before Kit kills the boot). It waits for the framework to import that module
and patches the generator when it does.

The wait used to be a ``sys.meta_path`` finder, and that is a race the probe loses: the machinery
stops at the first finder that answers, Kit keeps one of its own ahead of anything inserted later,
and the module then arrives without our hook ever being asked. Nothing failed loudly -- ``_RECORDS``
just stayed empty and the consumer refused the terrain with "the probe was not installed", a
truthful message about a cause three steps away (measured 2026-09-18: every param-grid trainer run,
while the env instrument passed because it imports ``isaaclab.terrains`` early and never takes the
waiting branch).

The mechanic is reproduced without a simulator: pay the import the way a foreign importer would
(put the module in ``sys.modules``), then import anything at all -- the wait rides on
``builtins.__import__``, which every python-level import goes through, so who did the importing and
where they sat in ``sys.meta_path`` stops mattering.

Pinned here: (1) ``install()`` does not import the module itself, (2) the patch lands after a
foreign import, (3) the watcher is taken back off ``builtins.__import__`` once it has fired.

Usage: python check_split_probe_wait.py
"""

from __future__ import annotations

import builtins
import sys
import types

from rl_exp.tools.verify import terrain_split_probe as probe

#: The module under watch, and the real importer we expect to be handed back afterwards.
GENERATOR = probe._GENERATOR_MODULE
ORIGIN_IMPORT = builtins.__import__


def _foreign_module() -> tuple[types.ModuleType, type]:
    """A stand-in for the module the framework imports: the four call points ``_patch()`` wraps."""
    class TerrainGenerator:
        def _get_terrain_mesh(self, difficulty, cfg):
            return ("unpatched", difficulty, cfg)

        def _add_sub_terrain(self, mesh, origin, row, col, sub_terrain_cfg):
            return None

        def _generate_curriculum_terrains(self):
            return None

        def _generate_random_terrains(self):
            return None

    module = types.ModuleType(GENERATOR)
    module.TerrainGenerator = TerrainGenerator
    return module, TerrainGenerator


def main() -> int:
    if GENERATOR in sys.modules:
        print(f"check_split_probe_wait: cannot judge -- {GENERATOR} is already imported in this process")
        return 1

    problems: list[str] = []
    probe.install()
    if GENERATOR in sys.modules:
        problems.append("install() imported the generator module itself: that is the pre-Kit pxr leak (P004)")

    module, generator = _foreign_module()
    sys.modules[GENERATOR] = module  # somebody else paid the import, the way the framework does
    builtins.__import__("colorsys")  # any import at all, through the builtin the wait rides on

    if not probe._PATCHED:
        problems.append(
            "the patch did not land after a foreign import: the wait is position-dependent again "
            "(a finder ahead of ours answers first and we are never asked)"
        )
    elif generator._get_terrain_mesh.__qualname__ == "TerrainGenerator._get_terrain_mesh":
        problems.append("_PATCHED is set but the generator is still unwrapped")
    if builtins.__import__ is not ORIGIN_IMPORT:
        problems.append("the watcher stayed on builtins.__import__ after firing: it must be one shot")

    for problem in problems:
        print(f"check_split_probe_wait: FAIL -- {problem}")
    if problems:
        return 1
    print("check_split_probe_wait: OK (a foreign import still lands the patch, and install() imports nothing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
