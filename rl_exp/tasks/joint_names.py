# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""What a leg is made of: the leg groups and the joint roots, in one table (``ARCH_PLAN`` "E. 名表单点化").

The same five roots were written out by hand at least seven times -- ``check_joint_layout``,
``check_self_collision``, ``gait_probe``, ``check_leg_reachability``, ``plot_joints``,
``baseline_metrics``, ``baseline_eval`` -- and in three different dialects of the same fact:

* the bare root, ``hip`` -- the token a name is split on (``lf_hip`` -> ``lf`` + ``hip``);
* the joint suffix, ``_hip_joint`` -- what ``str.endswith`` is handed;
* the regex, ``.*_hip_joint`` -- what a name list or an actuator group is matched with.

Seven copies is seven edits for one rename, and six chances to miss one -- the failure mode no test
catches, because the tool that was missed still runs, on the wrong joints. One table, three dialects
derived from it, so a rename is this file and one act.

**Stdlib only, and importing this file never needs this package's ``__init__``.** A caller that reaches
it as ``from rl_exp.tasks import joint_names`` pays ``rl_exp/tasks/__init__.py`` (gym registration, so
gymnasium); a caller that must not pay it (the offline gates, any interpreter with no gymnasium) reads
the file directly -- the idiom ``check_obs_protocol.py`` already uses
(``importlib.util.spec_from_file_location``), or puts ``rl_exp/tasks`` on ``sys.path`` and does a plain
``import joint_names``.

**The rename is data here, not active.** ``PLANNED_*`` is the 2026-10-10 user-approved front/rear split
(``hip`` -> ``shoulder_swing``/``hip_swing``, ...). Nothing in this module returns it unless asked, the
active names above are the OLD ones the assets and the checkpoints carry, and every existing gate must
stay green on them. Flipping to the new names is the body-swap act
(``work/active/lizard2-body-drive-candidate.md``, "骨骼改名"), not an edit here.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

#: The four legs, in the repo's canonical order: the front pair, then the rear pair. The order is a
#: fact two callers already depend on -- the leg split below derives the front/rear groups from it,
#: and a report that lists the legs lists them in it.
LEGS = ("lf", "rf", "rl", "rr")

#: The leg chain, proximal -> distal, one entry per joint: the sprawl/vertical root, the abduction
#: hinge, the fore-aft hinge, the second fore-aft hinge, and the blade. The chain's length is not a
#: constant anyone may assume elsewhere -- a family that inserts a joint (lizard2's ``hip`` at the
#: root) adds a token here, which is the one line such a body costs.
CHAIN_ROOTS = ("hip", "haa", "hfe", "kfe", "foot")

#: The one suffix every joint in this repo carries: link ``<leg>_<root>``, joint ``<leg>_<root>_joint``.
JOINT_SUFFIX = "_joint"

#: The legs by limb group, derived from :data:`LEGS` rather than written twice: the actuator groups, the
#: per-limb naming and the contact bodies are per group, so the split has to agree with the order.
FRONT_LEGS, REAR_LEGS = LEGS[:2], LEGS[2:]


def suffixes_for(roots: tuple[str, ...] = CHAIN_ROOTS) -> tuple[str, ...]:
    """Dialect 2 (``_hip_joint``, ...) for a chain, in the order the roots are given.

    A function rather than a constant alone because the check below has to run the same builder over
    the *planned* roots: "the rename does not change the dialect" is then an assertion, not a promise.
    """
    return tuple(f"_{root}{JOINT_SUFFIX}" for root in roots)


def patterns_for(roots: tuple[str, ...] = CHAIN_ROOTS) -> tuple[str, ...]:
    """Dialect 3 (``.*_hip_joint``, ...) for a chain, in the order the roots are given.

    Fullmatch patterns (``re.fullmatch``), which is how the callers use them: a partial match would
    make ``lf_hip_joint_extra`` a hip joint.
    """
    return tuple(f".*_{root}{JOINT_SUFFIX}" for root in roots)


#: Dialect 2 of the active names: index ``i`` is ``CHAIN_ROOTS[i]``'s suffix.
JOINT_SUFFIXES = suffixes_for()
#: Dialect 3 of the active names, same order.
JOINT_PATTERNS = patterns_for()

#: The three joints between the root yaw and the blade: the hinges whose axes share one plane. Their
#: plane is what the root yaw can turn and nothing can tilt -- a structural claim
#: (``check_leg_reachability``) -- and the last two of them are the pair a fold pose moves together.
HINGE_ROOTS = CHAIN_ROOTS[1:4]


def link_name(leg: str, root: str) -> str:
    """The link a root forms on a leg, ``lf_hip``.

    The link of a joint and the joint itself share one root in this repo (``lf_hip`` is the link,
    ``lf_hip_joint`` the joint), which is why the contact body of a leg is its chain's end link and
    why one table can name both.
    """
    return f"{leg}_{root}"


def joint_name(leg: str, root: str) -> str:
    """The joint a root forms on a leg, ``lf_hip_joint`` -- dialect 1's root plus dialect 2's suffix."""
    return link_name(leg, root) + JOINT_SUFFIX


def end_link(leg: str) -> str:
    """The leg's chain-end link, ``lf_foot``: the contact body every foot sensor and ``.*_foot`` reads.

    Derived from the chain's last root, not written as the string ``foot``: the end of the chain is a
    chain fact, and the rename moves it to ``finger``/``toe`` without this function being edited.
    """
    return link_name(leg, CHAIN_ROOTS[-1])


#: The joints the per-frame reports carry and the panels draw: the root, the first fore-aft hinge and
#: the blade. Given by POSITION, not by word -- a report that hard-coded ``hfe`` would draw an empty
#: row after a rename and still look like a figure, which is the failure a name table exists to stop.
REPORT_ROOTS = (CHAIN_ROOTS[0], CHAIN_ROOTS[2], CHAIN_ROOTS[-1])

#: The bodies a foot sensor, a reward or a foot raycast is handed -- the chain-end link per leg. As a
#: PATTERN, not as the four exact names: the engine resolves it in its own body order, so naming them
#: one by one would be this table's order silently becoming the observation's order. The rename turns
#: this line into one pattern per limb group (front ``.*_finger``, rear ``.*_toe``).
CONTACT_BODY_PATTERNS = (f".*_{CHAIN_ROOTS[-1]}",)


def is_contact_body(name: str) -> bool:
    """Is ``name`` a body a foot is -- the chain-end link of some leg?

    The predicate form of :data:`CONTACT_BODY_PATTERNS`, for the callers that hold a body name and a
    list comprehension rather than a name they can hand the engine (``find_bodies`` /
    ``find_sensors``). ``str.endswith("_foot")`` spelled the same fact in each of them.
    """
    return any(re.fullmatch(pattern, name) for pattern in CONTACT_BODY_PATTERNS)


# -------------------------------------------------------------------------------------------------
# PLANNED, NOT ACTIVE -- the 2026-10-10 rename (user-approved; lands with the candidate body)
#
# The front limb becomes an arm and the rear one keeps a leg's words, so the two no longer share a
# root: one asset, two limb groups, five new names each. This is *data*: it answers only when asked by
# name (:func:`planned_root`), no active table above is built from it, and a tool that reads it before
# the body lands would measure a chain no asset carries.
# -------------------------------------------------------------------------------------------------

#: Whether the planned names are the live ones. ``False`` while the assets and every checkpoint carry
#: the old ones; the self-check refuses a ``True`` here without the body that lands it.
PLANNED_ACTIVE = False

#: Old root -> the root that limb group's chain carries after the rename, per chain position.
PLANNED_RENAMES: dict[str, dict[str, str]] = {
    "front": {"hip": "shoulder_swing", "haa": "shoulder_abduct", "hfe": "elbow",
              "kfe": "wrist", "foot": "finger"},
    "rear": {"hip": "hip_swing", "haa": "hip_abduct", "hfe": "knee",
             "kfe": "ankle", "foot": "toe"},
}

#: The same mapping read as two chains, derived so the chains and the table cannot drift apart.
PLANNED_ROOTS: dict[str, tuple[str, ...]] = {
    group: tuple(names[root] for root in CHAIN_ROOTS) for group, names in PLANNED_RENAMES.items()
}


def planned_root(leg: str, root: str) -> str:
    """The root ``root`` becomes on ``leg`` under the planned rename. Data, not the live answer.

    Keyed by the OLD root and the leg, because that is the question a caller has ("this ``kfe`` on the
    front limb becomes what?") -- and because the old name is the only one both bodies agree on.

    Raises:
        KeyError: unknown leg or root. A name table that answers a name it does not carry is how a
            wrong link ends up in an asset.
    """
    if leg not in LEGS:
        raise KeyError(f"{leg}: not one of {LEGS}")
    return PLANNED_RENAMES["front" if leg in FRONT_LEGS else "rear"][root]


def _self_check() -> None:
    """Asserts, no framework and no fixtures: ``python rl_exp/tasks/joint_names.py``.

    Four readings, the four this module can be wrong in:

    (a) each dialect resolves for all five roots and all four legs -- and does NOT resolve a name that
        is not in the table (a ``.*_joint`` that matches anything is worse than a missing entry);
    (b) the derived selections (the hinges, the reported three, the contact bodies) stay inside the
        chain and pick the bodies the chain ends at -- and the contact pattern matches those four and
        nothing else, which is the overload a rename is most likely to move SILENTLY;
    (c) the planned mapping keeps the chain order and the leg grouping, so the new name set is the same
        *shape* as the old one, a tool reading it per leg gets a name per chain position, and the two
        limb groups end at two different links (which is what makes the contact pattern split in two);
    (d) this file's import surface is the standard library, so the Blender/offline interpreter that must
        not pay torch or gymnasium can hold the table.
    """
    # (a) three dialects, five roots, four legs
    resolved = 0
    for leg in LEGS:
        for index, root in enumerate(CHAIN_ROOTS):
            joint = joint_name(leg, root)
            assert link_name(leg, root) == f"{leg}_{root}", joint
            assert joint == f"{leg}_{root}_joint", joint
            assert JOINT_SUFFIXES[index] == f"_{root}{JOINT_SUFFIX}", (JOINT_SUFFIXES, index)
            assert JOINT_PATTERNS[index] == f".*_{root}{JOINT_SUFFIX}", (JOINT_PATTERNS, index)
            assert joint.endswith(JOINT_SUFFIXES), joint
            assert any(re.fullmatch(pattern, joint) for pattern in JOINT_PATTERNS), joint
            resolved += 1
    assert resolved == 20, resolved
    assert tuple(end_link(leg) for leg in LEGS) == ("lf_foot", "rf_foot", "rl_foot", "rr_foot"), LEGS
    # Nothing outside the table may resolve: a chain-end link, the trunk, a bare root, a longer name.
    for outsider in ("base_link", "lf_foot", "lf_foot_link", "hip", "lf_hip_joint_extra"):
        assert not outsider.endswith(JOINT_SUFFIXES), outsider
        assert not any(re.fullmatch(pattern, outsider) for pattern in JOINT_PATTERNS), outsider

    # (b) the derived selections: inside the chain, in chain order, and the contact pattern is the
    # OVERLOAD one -- the same string a foot sensor is handed also names the joint that moves it, so a
    # rename that moves an end link has to move this pattern with it.
    for selection, name in ((HINGE_ROOTS, "HINGE_ROOTS"), (REPORT_ROOTS, "REPORT_ROOTS")):
        assert selection, name
        assert len(set(selection)) == len(selection), (name, selection)
        assert set(selection) <= set(CHAIN_ROOTS), (name, selection, CHAIN_ROOTS)
        assert list(CHAIN_ROOTS.index(root) for root in selection) == sorted(
            CHAIN_ROOTS.index(root) for root in selection), (name, selection)
    assert HINGE_ROOTS == CHAIN_ROOTS[1:4], HINGE_ROOTS
    assert HINGE_ROOTS[-2:] == ("hfe", "kfe"), HINGE_ROOTS
    assert REPORT_ROOTS[-1] == CHAIN_ROOTS[-1], REPORT_ROOTS
    ends = {end_link(leg) for leg in LEGS}
    assert {name for name in ends if is_contact_body(name)} == ends, ends
    for outsider in ("base_link", "lf_foot_link", "lf_foot_joint", "lf_kfe", "lf_hip"):
        assert not is_contact_body(outsider), outsider

    # (c) the planned mapping: same chain order, same leg grouping, different words
    assert PLANNED_ACTIVE is False, "the rename is a candidate -- it lands with the body that carries it"
    assert set(PLANNED_RENAMES) == {"front", "rear"}, sorted(PLANNED_RENAMES)
    assert set(PLANNED_ROOTS) == set(PLANNED_RENAMES)
    planned = 0
    for group, legs in (("front", FRONT_LEGS), ("rear", REAR_LEGS)):
        names = PLANNED_RENAMES[group]
        assert tuple(names) == CHAIN_ROOTS, (group, tuple(names))
        assert PLANNED_ROOTS[group] == tuple(names[root] for root in CHAIN_ROOTS), group
        assert len(set(names.values())) == len(CHAIN_ROOTS), (group, sorted(names.values()))
        assert not set(names.values()) & set(CHAIN_ROOTS), (group, "a planned name is already an active root")
        for new in names.values():
            assert re.fullmatch(r"[a-z][a-z0-9_]*", new), new
        for leg in legs:
            for root in CHAIN_ROOTS:
                new = planned_root(leg, root)
                assert new == names[root] and new != root, (leg, root, new)
                # The planned chain goes through the SAME dialect builders: the rename is words, not shape.
                planned_joint = f"{leg}_{new}{JOINT_SUFFIX}"
                assert planned_joint.endswith(suffixes_for(PLANNED_ROOTS[group])), planned_joint
                assert any(re.fullmatch(pattern, planned_joint)
                           for pattern in patterns_for(PLANNED_ROOTS[group])), planned_joint
                planned += 1
    assert planned == 20, planned
    # One asset carries both groups, so no name may be shared between them.
    assert not set(PLANNED_ROOTS["front"]) & set(PLANNED_ROOTS["rear"]), PLANNED_ROOTS
    # A name outside the table is refused, by leg and by root.
    for leg, root in (("xx", "hip"), ("lr", "hip"), ("lf", "toe"), ("lf", "elbow")):
        try:
            planned_root(leg, root)
        except KeyError:
            continue
        raise AssertionError(f"({leg!r}, {root!r}): not in the table, so it must not be answered")

    # (d) the import surface is the standard library
    assert hasattr(sys, "stdlib_module_names"), "python < 3.10 cannot read the stdlib list; this check is not running"
    imported: set[str] = set()
    for node in ast.walk(ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    assert imported, "the AST walk found no import at all -- the check would pass on an empty file"
    third_party = imported - set(sys.stdlib_module_names)
    assert not third_party, f"non-stdlib import(s): {sorted(third_party)}"

    print("[SELF-CHECK] 3 dialects x 5 roots x 4 legs = 20 names resolve, nothing outside the table does; "
          "the hinges, the reported three and the contact pattern pick the chain's own bodies and nothing "
          "else; the planned front/rear chains keep the chain order and the leg grouping, split the "
          "contact pattern in two, and refuse unlisted names; imports are stdlib only: %s"
          % ", ".join(sorted(imported)))


if __name__ == "__main__":
    _self_check()
