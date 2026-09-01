# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Staged curriculum terms for velocity-based locomotion tasks.

A staged curriculum is a sequence of :class:`StageCfg` entries. Each stage owns:

* a gate (metric threshold + sustain time) that decides when training advances to the
  next stage,
* a payload (velocity command ranges and/or action term scales) applied on entering
  the stage,
* an optional dependency on the stage index reached by another staged curriculum.

This makes the term generic: bone unlocking (action scales), speed widening and
turning widening (command ranges) are all just different stage lists.
"""

from __future__ import annotations

import re
from dataclasses import MISSING
from typing import TYPE_CHECKING

from isaaclab.managers import CurriculumTermCfg, ManagerTermBase
from isaaclab.utils.configclass import configclass

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedEnv

    from isaaclab.envs.mdp.commands import UniformVelocityCommand


@configclass
class StageCfg:
    """Parameters of a single curriculum stage (the single source of truth)."""

    metric_threshold: float = 0.8
    """Advance to the next stage once the gate metric stays above this value."""
    sustain_s: float = 60.0
    """Time [s] the metric must stay above :attr:`metric_threshold` before advancing."""
    command_ranges: dict[str, tuple[float, float]] | None = None
    """Ranges assigned to the command term on entering this stage.

    Keys are attribute names of the command ranges object, e.g. ``"lin_vel_x"``.
    """
    action_scales: dict[str, float] | None = None
    """Scales assigned to action terms on entering this stage (term name -> scale)."""
    requires: str | None = None
    """Dependency on another staged curriculum before this stage can be entered.

    Format: ``"<term_name>>=<stage_idx>"``, e.g. ``"speed_curriculum>=2"``.
    """


@configclass
class StagedCurriculumTermCfg(CurriculumTermCfg):
    """Configuration for :class:`StagedCurriculumTerm`."""

    command_name: str = "base_velocity"
    """Name of the velocity command term whose metrics drive the gate."""
    metric_name: str = "success_rate"
    """Command metric used as gate (episode-mean success flags, updated at resets)."""
    stages: list[StageCfg] = MISSING
    """Stage list; index 0 is applied when the curriculum first computes."""


class StagedCurriculumTerm(ManagerTermBase):
    """Curriculum term that advances through a list of stages.

    The gate metric is read from a command term's ``metrics`` buffer (per-environment
    episode statistics finalized at episode resets). The mean over all environments
    must exceed the stage threshold continuously for ``sustain_s`` seconds before the
    term advances. Advancing applies the next stage's payload; the returned dictionary
    is logged by the curriculum manager as ``Curriculum/<term_name>/*``.
    """

    cfg: StagedCurriculumTermCfg

    def __init__(self, cfg: StagedCurriculumTermCfg, env: ManagerBasedEnv):
        """Initialize the term state.

        Args:
            cfg: The staged curriculum configuration.
            env: The environment instance.
        """
        super().__init__(cfg, env)
        if not self.cfg.stages:
            raise ValueError(f"Curriculum term received an empty stage list: {self.cfg}.")
        self.stage_idx = 0
        self._counter_steps = 0
        self._applied = False

    """
    Operations.
    """

    def __call__(self, env, env_ids) -> dict[str, float]:
        """Advance the curriculum if the gate condition is met.

        Args:
            env: The environment instance.
            env_ids: The environment indices (unused; the gate is global).

        Returns:
            Logging dictionary with the current stage and gate metric.
        """
        stage = self.cfg.stages[self.stage_idx]
        if not self._applied:
            self._apply_stage(stage)
            self._applied = True
        # already at the last stage: nothing left to gate or apply
        if self.stage_idx >= len(self.cfg.stages) - 1:
            return {"stage": self.stage_idx}
        next_stage = self.cfg.stages[self.stage_idx + 1]
        if not self._dependency_met(next_stage.requires):
            return {"stage": self.stage_idx}
        metric = self._gate_metric()
        if metric >= stage.metric_threshold:
            self._counter_steps += 1
        else:
            self._counter_steps = 0
        sustain_steps = max(1, round(stage.sustain_s / self._env.step_dt))
        if self._counter_steps >= sustain_steps:
            self.stage_idx += 1
            self._counter_steps = 0
            self._apply_stage(self.cfg.stages[self.stage_idx])
        return {"stage": self.stage_idx, "metric": metric}

    """
    Implementation specific functions.
    """

    def _gate_metric(self) -> float:
        """Mean of the configured command metric over all environments."""
        command: UniformVelocityCommand = self._env.command_manager.get_term(self.cfg.command_name)
        return float(command.metrics[self.cfg.metric_name].mean())

    def _apply_stage(self, stage: StageCfg):
        """Apply the stage payload (command ranges and action scales)."""
        if stage.command_ranges is not None:
            command = self._env.command_manager.get_term(self.cfg.command_name)
            for attr, value in stage.command_ranges.items():
                setattr(command.cfg.ranges, attr, value)
        if stage.action_scales is not None:
            for term_name, scale in stage.action_scales.items():
                action_term = self._env.action_manager.get_term(term_name)
                # keep cfg in sync; the term reads the private `_scale` in process_actions()
                action_term._scale = float(scale)
                action_term.cfg.scale = float(scale)

    def _dependency_met(self, requires: str | None) -> bool:
        """Check a ``"<term_name>>=<idx>"`` dependency against another staged term."""
        if requires is None:
            return True
        match = re.fullmatch(r"(?P<name>\w+)>=(?P<idx>\d+)", requires)
        if match is None:
            raise ValueError(f"Invalid `requires` spec '{requires}'; expected '<term_name>>=<idx>'.")
        curr_cfg = self._env.curriculum_manager.cfg
        if isinstance(curr_cfg, dict):
            dep_cfg = curr_cfg.get(match.group("name"))
        else:
            dep_cfg = getattr(curr_cfg, match.group("name"), None)
        if dep_cfg is None:
            raise ValueError(f"Curriculum dependency '{match.group('name')}' not found in curriculum cfg.")
        dep_term = dep_cfg.func
        if not isinstance(dep_term, StagedCurriculumTerm):
            raise TypeError(f"Curriculum dependency '{match.group('name')}' is not a StagedCurriculumTerm.")
        return dep_term.stage_idx >= int(match.group("idx"))
