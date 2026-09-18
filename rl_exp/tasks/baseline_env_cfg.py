# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Flat-ground walking baseline: fixed low-speed forward command, nothing else.

Built directly on :class:`LocomotionVelocityRoughEnvCfg` and on framework MDP terms
only. It imports no other recipe module -- not the family base, not the teacher snapshot,
not ``teacher_mdp`` -- so "the baseline recipe" is a file you can read end to end instead
of the residue of six generations of inheritance. The two kernels it needs from the
shared, actively-mutated ``teacher_mdp.py`` are re-implemented in
:mod:`rl_exp.tasks.baseline_mdp` (with a test that catches drift).

What is missing is missing on purpose, and every absence is written here rather than
inherited:

* no terrain generator, no height scanner, no foot-ring sensors, no privileged
  observation group -- flat ground is the whole point, and the policy group already
  carries exactly the 7 proprio terms (3+3+3+3+26+26+26 = 90 dims);
* no curriculum of any kind (``terrain_levels`` removed; the staged speed curriculum
  belongs to other lines and simply does not exist here);
* no domain randomization, and no pushes: "no curriculum" and "no DR" are independent
  decisions, so every randomization event the framework base registers is set to None
  explicitly. Deleting the c_k clock alone would leave them running at full strength,
  and two of them (the interval wrench and the interval velocity push) are not c_k-gated
  at all -- they would never have annealed in the first place.

The command is a fixed point, and the two switches that can rewrite a "fixed" command
are turned off explicitly (``heading_command``, ``rel_standing_envs``). ``baseline_probe``
reads the issued command tensor rather than trusting the config, because a config that
*says* 0.5 m/s and a command manager that issues something else look identical here.
"""

import pathlib
from typing import ClassVar

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.configclass import configclass

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import (
    ActionsCfg,
    LocomotionVelocityRoughEnvCfg,
)

from rl_exp.tasks import baseline_mdp, recipe_params
from rl_exp.tasks.play_utils import apply_play_wiring

# this file lives at rl_exp/tasks/baseline_env_cfg.py -> exp root is parents[1]
_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]

# family-relative handle of this recipe line: the one place that answers "whose line is
# this", used both here for the parameter path and by the gates for the lock routing
_LINE_KEY = "lizard/baseline"
_DEFAULT_VERSION = "v1"


def _load_params(version: str | None = None) -> dict:
    """Load this line's parameter SSOT.

    Args:
        version: a frozen version handle (``"v1"``) to read that version's frozen copy, or
            None for the live dev yaml. Always pass the cfg's own ``params_version``: a
            version-stamped task that read the dev yaml would be pinned to a mutable file.

    Returns:
        The resolved parameters of this line, as this caller's own tree -- the line shares the
        one loader now, so it also gets the parse cache every other line had.
    """
    return recipe_params.load(_LINE_KEY, version)


@configclass
class BaselineActionsCfg(ActionsCfg):
    """The deployed two-group action split, frozen.

    Legs are ordered before spine so the concatenated 26-dim action layout equals the
    articulation tree order -- the same layout the observations (``last_action``) assume.
    The split exists because the platform's interface is split; it is frozen here rather
    than simplified to one group, since a baseline that trains against a different action
    interface cannot answer a question about this robot as deployed.

    ``joint_pos`` (the single-group base term) is removed: leaving it in place would add
    26 more action dims driven by the same joints.
    """

    joint_pos = None
    joint_pos_legs = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=[".*_haa_joint", ".*_hfe_joint", ".*_kfe_joint", ".*_foot_joint"],
        scale=0.5,
        use_default_offset=True,
    )
    joint_pos_spine = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=["chest_.*", "neck_.*", "tail[0-9]_.*"],
        scale=0.25,
        use_default_offset=True,
    )


@configclass
class BaselineWiringCfg(LocomotionVelocityRoughEnvCfg):
    """The shared wiring this line's recipes start from: the framework stock cfg, plus identity.

    The teacher line splits the same way -- a base that resolves every structural choice from the
    version it is handed, and per-recipe deltas on top. This is that base for the baseline line,
    and it is deliberately *empty*: the framework stock ``LocomotionVelocityRoughEnvCfg`` plus the
    two members every gate routes by. ``BaselineFlatEnvCfg`` was once the only thing here -- the
    whole recipe, inlined. It is a declaration now
    (``rl_exp.tasks.recipe``), so "what v1 is" is readable as an ordered element list instead of
    as the residue of one ``__post_init__``.

    The identity members are the point, not decoration: a base class that did not declare
    ``params_line`` would make the builder stamp an *instance* attribute the snapshot cannot
    filter the same way the class path filters it, and the two paths would differ by a field that
    says nothing about the recipe.
    """

    params_line: ClassVar[str] = _LINE_KEY
    params_version = _DEFAULT_VERSION




