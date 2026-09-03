# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline unit test for the v5.3 SIR terrain curriculum (no sim, plain torch).

Checks, against a fully mocked env/terrain: the TerrainGenerator column ->
type split replication, the initial full reset (no stats pollution, origins
re-pointed consistently), the terminal-episode success predicate (survival +
displacement >= ratio x commanded distance), the soft band edges, band-driven
resampling, insufficient-traffic weight retention, random-walk clamping,
replay-memory redraws and the block-evaluation throttle.
"""

import pathlib
import sys
from types import SimpleNamespace

import torch

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from rl_exp.tasks.teacher_mdp import (  # noqa: E402
    SpawnWeightSIRTerrainCurriculum,
    SIRTerrainCurriculumCfg,
)

NUM_ENVS = 8
NUM_ROWS = 10
NUM_COLS = 20


class _Scene(dict):
    """Scene mock: dict access for assets + attribute for the terrain."""

    def __init__(self, robot, terrain):
        super().__init__(robot=robot)
        self.terrain = terrain


def _terrain(sub_props=(0.2, 0.3, 0.5)):
    origins = torch.zeros(NUM_ROWS, NUM_COLS, 3)
    origins[:, :, 0] = torch.arange(NUM_ROWS).unsqueeze(1) * 100.0
    origins[:, :, 1] = torch.arange(NUM_COLS).unsqueeze(0) * 1.0
    sub_terrains = {f"t{i}": SimpleNamespace(proportion=p) for i, p in enumerate(sub_props)}
    gen_cfg = SimpleNamespace(sub_terrains=sub_terrains)
    # importer formula (terrain_importer.py:348-350)
    types = (torch.arange(NUM_ENVS).float() / (NUM_ENVS / NUM_COLS)).long()
    return SimpleNamespace(
        cfg=SimpleNamespace(terrain_generator=gen_cfg),
        terrain_origins=origins,
        terrain_levels=torch.randint(0, NUM_ROWS, (NUM_ENVS,)),
        terrain_types=types,
        env_origins=torch.zeros(NUM_ENVS, 3),
    )


def _env(terrain, *, counter=0, pos=None, cmd=None, timeouts=None, lengths=None):
    pos = torch.zeros(NUM_ENVS, 3) if pos is None else pos
    cmd = torch.zeros(NUM_ENVS, 3) if cmd is None else cmd
    timeouts = torch.zeros(NUM_ENVS, dtype=torch.bool) if timeouts is None else timeouts
    lengths = torch.zeros(NUM_ENVS, dtype=torch.long) if lengths is None else lengths
    robot = SimpleNamespace(data=SimpleNamespace(root_pos_w=SimpleNamespace(torch=pos)))
    return SimpleNamespace(
        scene=_Scene(robot, terrain),
        command_manager=SimpleNamespace(get_command=lambda name: cmd),
        reset_time_outs=timeouts,
        episode_length_buf=lengths,
        common_step_counter=counter,
        max_episode_length_s=20.0,
    )


def _term(env, **overrides):
    defaults = dict(
        band=(0.5, 0.9), eval_every=10, n_traj_min=6, p_transition=0.8,
        p_replay=0.05, success_ratio=0.5, soft_edge=0.05, steps_per_iteration=24,
    )
    defaults.update(overrides)
    return SpawnWeightSIRTerrainCurriculum(
        SIRTerrainCurriculumCfg(func=SpawnWeightSIRTerrainCurriculum, **defaults), env
    )


def test_column_type_mapping() -> None:
    # cum(normalized 0.2/0.3/0.5) = [0.2, 0.5, 1.0] -> cols 0-3 / 4-9 / 10-19
    term = _term(_env(_terrain()))
    assert term._type_cols[0].tolist() == [0, 1, 2, 3]
    assert term._type_cols[1].tolist() == list(range(4, 10))
    assert term._type_cols[2].tolist() == list(range(10, 20))
    # env -> type follows the initial columns [0, 2, 5, 7, 10, 12, 15, 17]
    assert term._env_type.tolist() == [0, 0, 1, 1, 2, 2, 2, 2]


def test_initial_spawn_reassigns_all_envs() -> None:
    torch.manual_seed(0)
    terrain = _terrain()
    env = _env(terrain)  # counter 0, episode_length_buf all zero
    term = _term(env)
    ret = term(env, torch.arange(NUM_ENVS))
    assert ret.dim() == 0 and torch.isfinite(ret)
    # initial full reset must not pollute the episode stats
    for t in range(3):
        assert float(term._episodes[t].sum()) == 0.0
        assert float(term._successes[t].sum()) == 0.0
    # origins consistently re-pointed into the env's type columns
    for i in range(NUM_ENVS):
        lvl = terrain.terrain_levels[i].item()
        col = terrain.terrain_types[i].item()
        assert 0 <= lvl <= NUM_ROWS - 1
        assert col in term._type_cols[term._env_type[i].item()].tolist()
        assert torch.equal(terrain.env_origins[i], terrain.terrain_origins[lvl, col])


def test_success_predicate() -> None:
    terrain = _terrain()
    terrain.terrain_levels[:] = 3
    pos = torch.zeros(NUM_ENVS, 3)
    pos[0, 0] = 10.0  # env 0: survived + walked 10 m >= 0.5 * (1 m/s * 20 s)
    pos[1, 0] = 1.0   # env 1: survived but only 1 m
    pos[2, 0] = 10.0  # env 2: walked far but terminated early
    cmd = torch.zeros(NUM_ENVS, 3)
    cmd[:, 0] = 1.0
    timeouts = torch.zeros(NUM_ENVS, dtype=torch.bool)
    timeouts[0] = True
    timeouts[1] = True
    lengths = torch.full((NUM_ENVS,), 400, dtype=torch.long)
    env = _env(terrain, pos=pos, cmd=cmd, timeouts=timeouts, lengths=lengths, counter=1)
    term = _term(env)
    term(env, torch.tensor([0, 1, 2]))
    # envs 0,1 are type 0 (columns 0, 2); env 2 is type 1 (column 5)
    assert float(term._episodes[0][3]) == 2.0
    assert float(term._successes[0][3]) == 1.0
    assert float(term._episodes[1][3]) == 1.0
    assert float(term._successes[1][3]) == 0.0


def test_band_soft_edges() -> None:
    term = _term(_env(_terrain()))
    p = torch.tensor([0.0, 0.45, 0.47, 0.5, 0.7, 0.9, 0.92, 0.95, 1.0])
    expected = torch.tensor([0.0, 0.0, 0.4, 1.0, 1.0, 1.0, 0.6, 0.0, 0.0])
    out = term._measurement_prob(p)
    assert torch.allclose(out, expected, atol=1e-6), f"got {out}"


def _stats_one_hot(term, t, row: int) -> None:
    """Give every row of type ``t`` full traffic; only ``row`` lands in-band.

    Rows below n_traj_min keep their previous weight (uniform), so a one-hot
    weight vector needs episodes on ALL rows.
    """
    term._episodes[t][:] = 10.0
    term._successes[t][:] = 1.0  # p = 0.1, below the band
    term._episodes[t][row] = 10.0
    term._successes[t][row] = 7.0  # p = 0.7, inside the band


def test_resample_selects_in_band_rows() -> None:
    term = _term(_env(_terrain()), p_transition=0.0, p_replay=0.0)
    _stats_one_hot(term, 0, 3)
    term._resample()
    assert term._particles[0].tolist() == [3] * NUM_ROWS
    assert float(term._episodes[0].sum()) == 0.0  # accumulators reset
    assert float(term._successes[0].sum()) == 0.0


def test_insufficient_traffic_keeps_weights() -> None:
    term = _term(_env(_terrain()))
    term._resample()  # zero episodes everywhere
    for t in range(3):
        assert torch.allclose(term._weights[t], torch.full((NUM_ROWS,), 1.0 / NUM_ROWS))


def test_random_walk_clamps() -> None:
    term = _term(_env(_terrain()), p_transition=1.0, p_replay=0.0)
    # one-hot weight at row 0 -> resample draws 0s, walk moves to {0, 1} only
    _stats_one_hot(term, 0, 0)
    term._resample()
    assert set(term._particles[0].tolist()) <= {0, 1}
    # same at the top edge
    _stats_one_hot(term, 1, 9)
    term._resample()
    assert set(term._particles[1].tolist()) <= {8, 9}


def test_replay_draws_from_history() -> None:
    term = _term(_env(_terrain()), p_transition=0.0, p_replay=1.0)
    term._history[0] = torch.full((NUM_ROWS,), 7, dtype=torch.long)
    term._episodes[0][2] = 10.0  # one-hot weight at row 2 -> resample all 2s
    term._successes[0][2] = 7.0
    term._resample()
    assert (term._particles[0] == 7).all()  # replay overwrote every particle


def test_block_eval_throttle() -> None:
    terrain = _terrain()
    env = _env(terrain, counter=100)
    term = _term(env, p_transition=0.0, p_replay=0.0)
    before = term._particles[0].clone()
    _stats_one_hot(term, 0, 3)  # would resample to [3]*10 if it fired
    term(env, torch.tensor([0]))  # counter 100 < 240: no resample
    assert term._particles[0].tolist() == before.tolist()
    env.common_step_counter = 240
    term(env, torch.tensor([0]))  # boundary: resample fires
    assert term._particles[0].tolist() == [3] * NUM_ROWS
    assert term._next_eval_step == 480  # quantized advance, no drift


def main() -> int:
    tests = [
        test_column_type_mapping,
        test_initial_spawn_reassigns_all_envs,
        test_success_predicate,
        test_band_soft_edges,
        test_resample_selects_in_band_rows,
        test_insufficient_traffic_keeps_weights,
        test_random_walk_clamps,
        test_replay_draws_from_history,
        test_block_eval_throttle,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {test.__name__}: {exc}")
    if failed:
        print(f"V5_TERRAIN_SIR_TEST_FAILED ({failed})")
        return 1
    print("V5_TERRAIN_SIR_TEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
