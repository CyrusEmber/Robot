# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline smoke test for StagedCurriculumTerm (no simulation, mock managers)."""

import torch

from rl_exp.tasks.staged_curriculum import (
    StagedCurriculumTerm,
    StagedCurriculumTermCfg,
    StageCfg,
)


class MockRanges:
    def __init__(self):
        self.lin_vel_x = (-1.0, 1.0)
        self.ang_vel_z = (-1.0, 1.0)


class MockCommand:
    def __init__(self):
        self.cfg = type("C", (), {})()
        self.cfg.ranges = MockRanges()
        self.metrics = {"success_rate": torch.zeros(4)}


class MockAction:
    def __init__(self):
        self._scale = 0.5
        self.cfg = type("A", (), {"scale": 0.5})()


class MockCommandManager:
    def __init__(self, term):
        self._term = term

    def get_term(self, name):
        return self._term


class MockActionManager:
    def __init__(self, terms):
        self._terms = terms

    def get_term(self, name):
        return self._terms[name]


class MockSpeedTerm(StagedCurriculumTerm):
    def __init__(self):
        # bypass parent init: dependency stub only needs `stage_idx`
        self.stage_idx = 1


class MockCurriculumManager:
    def __init__(self, cfg):
        self.cfg = cfg


class MockEnv:
    def __init__(self, cmd, actions, curr_cfg):
        self.command_manager = MockCommandManager(cmd)
        self.action_manager = MockActionManager(actions)
        self.curriculum_manager = MockCurriculumManager(curr_cfg)
        self.step_dt = 0.02


def main():
    speed_cfg = type("S", (), {"func": MockSpeedTerm()})()
    env = MockEnv(MockCommand(), {"joint_pos_tail": MockAction()}, {"speed_curriculum": speed_cfg})

    cfg = StagedCurriculumTermCfg(
        func=StagedCurriculumTerm,
        stages=[
            StageCfg(action_scales={"joint_pos_tail": 0.0}, metric_threshold=0.8, sustain_s=1.0),
            StageCfg(action_scales={"joint_pos_tail": 0.5}),
        ],
    )
    term = StagedCurriculumTerm(cfg, env)

    # metric below threshold: no advance, stage 0 applied
    state = term(env, None)
    assert state["stage"] == 0, state
    assert env.action_manager.get_term("joint_pos_tail")._scale == 0.0
    assert env.action_manager.get_term("joint_pos_tail").cfg.scale == 0.0

    # 50 steps at 0.02 s = 1.0 s above threshold -> advance
    env.command_manager._term.metrics["success_rate"] = torch.ones(4)
    for _ in range(49):
        state = term(env, None)
    assert state["stage"] == 0, "advanced too early"
    state = term(env, None)
    assert state["stage"] == 1, state
    assert env.action_manager.get_term("joint_pos_tail")._scale == 0.5

    # dip below threshold resets counter (terminal stage now, but verify no crash)
    env.command_manager._term.metrics["success_rate"] = torch.zeros(4)
    state = term(env, None)
    assert state == {"stage": 1}

    # dependency gating: turn term must not advance while speed_curriculum < 2
    turn_cfg = StagedCurriculumTermCfg(
        func=StagedCurriculumTerm,
        stages=[
            StageCfg(command_ranges={"ang_vel_z": (-0.5, 0.5)}, metric_threshold=0.8, sustain_s=1.0),
            StageCfg(command_ranges={"ang_vel_z": (-2.0, 2.0)}, requires="speed_curriculum>=2"),
        ],
    )
    turn = StagedCurriculumTerm(turn_cfg, env)
    env.command_manager._term.metrics["success_rate"] = torch.ones(4)
    for _ in range(60):
        state = turn(env, None)
    assert state["stage"] == 0, "advanced despite unmet dependency"
    assert env.command_manager._term.cfg.ranges.ang_vel_z == (-0.5, 0.5)

    speed_cfg.func.stage_idx = 2
    for _ in range(49):
        state = turn(env, None)
    assert state["stage"] == 0
    state = turn(env, None)
    assert state["stage"] == 1
    assert env.command_manager._term.cfg.ranges.ang_vel_z == (-2.0, 2.0)

    # invalid requires spec raises
    bad_cfg = StagedCurriculumTermCfg(
        func=StagedCurriculumTerm,
        stages=[
            StageCfg(metric_threshold=0.8, sustain_s=1.0),
            StageCfg(command_ranges={"ang_vel_z": (-2.0, 2.0)}, requires="bogus spec"),
        ],
    )
    bad = StagedCurriculumTerm(bad_cfg, env)
    try:
        bad(env, None)
        for _ in range(60):
            bad(env, None)
        raise AssertionError("expected ValueError for invalid requires spec")
    except ValueError:
        pass

    print("ALL_STAGED_CURRICULUM_TESTS_PASSED")


if __name__ == "__main__":
    main()
