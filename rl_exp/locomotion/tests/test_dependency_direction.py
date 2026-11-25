# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""The training core must not import evaluation or tools, at any nesting level."""

import ast
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1]
_FORBIDDEN = ("ablation_harness", "rl_exp.tools")
# Pure-stdlib hashing/git primitives shared with evaluation; it imports nothing from either side.
_ALLOWED = ("rl_exp.tools.runrecord.binding",)


def _imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from ((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.lineno, "." * node.level + (node.module or "")


def _hits(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def test_core_does_not_import_evaluation_or_tools():
    found = [
        f"{path.relative_to(_CORE)}:{line} imports {name}"
        for path in sorted(_CORE.glob("*.py"))
        for line, name in _imports(path)
        if _hits(name, _FORBIDDEN) and not _hits(name, _ALLOWED)
    ]
    assert not found, "core imports evaluation/tools:\n" + "\n".join(found)
