# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Flat-ground walking recipe for the lizard2 main line: wiring and the action split only.

Built directly on :class:`LocomotionVelocityRoughEnvCfg` and on framework MDP terms
only. It imports no other recipe module -- not the family base, not the teacher snapshot,
not ``teacher_mdp`` -- so this line's recipe is a file you can read end to end instead
of the residue of six generations of inheritance. The two kernels this line needs from the
shared, actively-mutated ``teacher_mdp.py`` live in :mod:`rl_exp.tasks.lizard2_recipe`,
copied beside the elements that reference them.

What is missing is missing on purpose, and every absence is written here rather than
inherited:

* no terrain generator, no height scanner, no foot-ring sensors, no privileged
  observation group -- flat ground is the whole point, and the policy group already
  carries exactly the 7 proprio terms (3+3+3+3+30+30+30 = 102 dims): four fixed
  3-vectors (``base_lin_vel``, ``base_ang_vel``, ``projected_gravity``,
  ``velocity_commands``) plus three joints-wide terms (``joint_pos``, ``joint_vel``,
  ``actions``), each as wide as this skeleton's 30 joints -- 20 leg joints including the
  meshless hip pivots, 10 spine;
* no curriculum of any kind (``terrain_levels`` removed; the staged speed curriculum
  belongs to other lines and simply does not exist here);
* no domain randomization, and no pushes: "no curriculum" and "no DR" are independent
  decisions, so every randomization event the framework base registers is set to None
  explicitly. Deleting the c_k clock alone would leave them running at full strength,
  and two of them (the interval wrench and the interval velocity push) are not c_k-gated
  at all -- they would never have annealed in the first place.

The command is a *range* -- ``lin_vel_x`` ``[0.0, 2.0]`` m/s, resampled on the framework's own 10 s
window, so a 20 s episode holds two commands -- and the two switches that can rewrite an issued
command are turned off explicitly (``heading_command``, ``rel_standing_envs``). The startup probe
reads the issued command tensor rather than trusting the config, because a yaml range and the
tensor the command manager actually issues are two things the config alone cannot tell apart.
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

from rl_exp.tasks import recipe_params
from rl_exp.tasks.play_utils import apply_play_wiring

# this file lives at rl_exp/tasks/lizard2_env_cfg.py -> exp root is parents[1]
_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]

# family-relative handle of this recipe line: the one place that answers "whose line is
# this", used both here for the parameter path and by the gates for the lock routing
_LINE_KEY = "lizard2/main"
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
class Lizard2ActionsCfg(ActionsCfg):
    """The deployed two-group action split, frozen.

    Legs are ordered before spine so the concatenated 30-dim action layout equals the
    articulation tree order (legs 20 including the meshless hip pivot, spine 10) -- the same
    layout the observations (``last_action``) assume. The hip pattern is written before
    ``*_haa_joint`` because the new skeleton puts each leg's hip pivot immediately before its
    haa (``versions/lizard2/main/main_params.yaml`` ``joint_order``), so the tree order a
    reader has in mind is the one written here.
    The split exists because the platform's interface is split; it is frozen here rather
    than simplified to one group, since a reference run that trains against a different action
    interface cannot answer a question about this robot as deployed.

    ``joint_pos`` (the single-group base term) is removed: leaving it in place would add
    30 more action dims driven by the same joints.
    """

    joint_pos = None
    joint_pos_legs = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=[".*_hip_joint", ".*_haa_joint", ".*_hfe_joint", ".*_kfe_joint", ".*_foot_joint"],
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
class Lizard2WiringCfg(LocomotionVelocityRoughEnvCfg):
    """The shared wiring this line's recipes start from: the framework stock cfg, plus identity.

    The teacher line splits the same way -- a base that resolves every structural choice from the
    version it is handed, and per-recipe deltas on top. This is that base for the lizard2 main
    line, and it is deliberately *empty*: the framework stock ``LocomotionVelocityRoughEnvCfg`` plus the
    two members every gate routes by. One inlined env cfg was once the only thing here -- the
    whole recipe, in one ``__post_init__``. It is a declaration now
    (``rl_exp.tasks.lizard2_recipe``), so "what v1 is" is readable as an ordered element list instead of
    as the residue of one ``__post_init__``.

    The identity members are the point, not decoration: a base class that did not declare
    ``params_line`` would make the builder stamp an *instance* attribute the snapshot cannot
    filter the same way the class path filters it, and the two paths would differ by a field that
    says nothing about the recipe.
    """

    params_line: ClassVar[str] = _LINE_KEY
    params_version = _DEFAULT_VERSION
