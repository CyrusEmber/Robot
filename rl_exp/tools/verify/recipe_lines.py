# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Single discovery entry for recipe lines: their parameter files and their lock file.

Three gates used to answer "which yaml belongs to which recipe" three different ways --
``check_dr_parity._version_yamls`` hardcoded the basename ``lizard_params.yaml`` and
globbed a single depth, ``check_dr_parity._recipe_dirs`` rglobbed ``*_params.yaml`` at
any depth, ``check_version_docs`` counted ``*_params.yaml`` itself. Where they disagree
the symptom is not a wrong answer but a *silent skip*: one gate checks a file the others
never look at, and nothing says so. This module is the one answer.

Layout it defines (one place, so a convention change is one edit):

* ``versions/<family>/<line>/<line>_params.yaml``           line dev yaml
* ``versions/<family>/<line>/vN/<line>_params.yaml``        frozen yaml
* ``versions/<family>/<line>/cfg_lock.json``                line golden lock

The main line's ``<line>`` IS the family name (``versions/lizard/``), so the main line
needs no extra directory and the existing ``versions/lizard/cfg_lock.json`` keeps its
path. Side lines (versioning.mdc A 分线条款) sit one level deeper and are keyed
family-relative, e.g. ``versions/lizard/parkour/v1/`` -> ``"lizard/parkour"``.

The basename convention is ``<line>_params.yaml``, NOT a fixed ``lizard_params.yaml``:
the parkour line already froze ``parkour_params.yaml``, and a rule that turns a frozen
directory red is a rule that gets deleted instead of followed.

Discovery is strict on purpose -- zero or multiple ``*_params.yaml``, a basename that
does not match its line, or a non-``v<N>`` version directory is an error, never a skip.
It raises rather than returning a partial map because every number a gate prints
downstream is meaningless on a half-discovered tree, and a half-discovered tree is
exactly what "skip what you do not recognise" produces.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

_REPO = pathlib.Path(__file__).resolve().parents[3]
VERSIONS = _REPO / "rl_exp" / "versions"

_VERSION_DIR = re.compile(r"v\d+")
PARAMS_SUFFIX = "_params.yaml"


class RecipeLineError(RuntimeError):
    """Discovery failed; the message lists every broken line at once."""


@dataclasses.dataclass(frozen=True)
class RecipeLine:
    """One recipe line: where its parameters live and which versions exist.

    Args:
        key: family-relative handle used by records and gates, e.g. ``"lizard"`` or
            ``"lizard/parkour"``.
        name: line leaf name; the parameters file must be ``<name>_params.yaml``.
        root: the line directory, e.g. ``versions/lizard/parkour``.
        dev_yaml: the line's live parameters SSOT (changes are not retroactive).
        versions: frozen version handle -> its frozen yaml, e.g. ``{"v1": ...}``.
    """

    key: str
    name: str
    root: pathlib.Path
    dev_yaml: pathlib.Path
    versions: dict[str, pathlib.Path]

    @property
    def lock_path(self) -> pathlib.Path:
        """Recipe golden lock of this line (one file per line, never shared)."""
        return self.root / "cfg_lock.json"

    @property
    def is_main_line(self) -> bool:
        """True for the family's own line (``"lizard"``), False for side lines.

        Side lines carry a different recipe schema -- ``lizard/parkour`` has no
        ``joint_order``/body-name lists -- so checks that assert the robot contract use
        this to stay main-line-only, while checks about *assets and records* cover every
        line. Stated here instead of being implied by a glob depth.
        """
        return "/" not in self.key


def _is_version_dir(path: pathlib.Path) -> bool:
    return path.is_dir() and _VERSION_DIR.fullmatch(path.name) is not None


def _line_roots(family_dir: pathlib.Path) -> list[pathlib.Path]:
    """The family's main line, plus every side line (a subdir holding ``v<N>`` dirs).

    One level only: a line of a line has no use case yet, and allowing arbitrary
    nesting would make ``"lizard/parkour"`` ambiguous with ``"lizard/parkour/x"``.
    """
    roots = [family_dir]
    for child in sorted(p for p in family_dir.iterdir() if p.is_dir()):
        if _VERSION_DIR.fullmatch(child.name):
            continue
        if any(_is_version_dir(entry) for entry in child.iterdir()):
            roots.append(child)
    return roots


def _params_yaml(root: pathlib.Path, name: str, problems: list[str]) -> pathlib.Path | None:
    """The one ``<name>_params.yaml`` under ``root``, or None after recording why not."""
    found = sorted(p for p in root.glob(f"*{PARAMS_SUFFIX}") if p.is_file())
    if not found:
        problems.append(f"{root}: no *{PARAMS_SUFFIX} (line {name!r} has no parameter SSOT)")
        return None
    if len(found) > 1:
        problems.append(
            f"{root}: {len(found)} *{PARAMS_SUFFIX} files {[p.name for p in found]}"
            f" -- exactly one per line (which one is the SSOT cannot be guessed)"
        )
        return None
    expected = f"{name}{PARAMS_SUFFIX}"
    if found[0].name != expected:
        problems.append(
            f"{root}: parameters file {found[0].name!r} != convention {expected!r}"
            f" (the basename names its line, so a reader of a path knows its owner)"
        )
        return None
    return found[0]


def discover(versions_dir: pathlib.Path | None = None) -> dict[str, RecipeLine]:
    """Every recipe line in the tree, keyed by family-relative handle.

    Args:
        versions_dir: directory holding the families (``versions/``); defaults to this
            repo's. Injectable so the gate's own test can drive a synthetic tree.

    Returns:
        Line handle -> :class:`RecipeLine`, ordered by handle.

    Raises:
        RecipeLineError: the tree is not discoverable. All problems are reported at
            once -- fixing them one red run at a time is how a convention ends up
            half-applied.
    """
    root_dir = VERSIONS if versions_dir is None else versions_dir
    if not root_dir.is_dir():
        raise RecipeLineError(f"versions directory does not exist: {root_dir}")

    problems: list[str] = []
    lines: dict[str, RecipeLine] = {}
    for family_dir in sorted(p for p in root_dir.iterdir() if p.is_dir()):
        for line_root in _line_roots(family_dir):
            key = line_root.relative_to(root_dir).as_posix()
            versions: dict[str, pathlib.Path] = {}
            ordered = sorted(
                (d for d in line_root.iterdir() if _is_version_dir(d)),
                key=lambda d: int(d.name[1:]),
            )
            for version_dir in ordered:
                frozen = _params_yaml(version_dir, line_root.name, problems)
                if frozen is not None:
                    versions[version_dir.name] = frozen
            lines[key] = RecipeLine(
                key=key,
                name=line_root.name,
                root=line_root,
                dev_yaml=_params_yaml(line_root, line_root.name, problems),
                versions=versions,
            )

    if problems:
        raise RecipeLineError("recipe line discovery failed:\n  " + "\n  ".join(problems))
    return lines
