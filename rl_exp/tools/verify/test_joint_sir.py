# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).

# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline unit test for the v11 joint SIR terrain curriculum (no sim, plain torch).

Checks, against a fully mocked env/terrain: the param-grid builder's combo
expansion and single-value ranges, the column -> combo split replication,
the initial full reset (no stats pollution, particle commands + origins
consistent), the Eq. 2/3/7 measurement chain (nu sums -> per-trajectory Tr ->
in-band-fraction weights, keep-previous on sparse pairs + cross-block counter
accumulation for pairs below n_traj_min, v11.1), the band-empty
directional fallback branches, single-axis random-walk clamping, replay
redraws, the block-evaluation throttle, and the ParticleVelocityCommand
lin_vel_x sourcing/fallback (0.0 bucket included).
"""

import pathlib
import sys
from types import SimpleNamespace

import torch

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from rl_exp.tasks.param_grid_terrain import build_param_grid_terrain_cfg  # noqa: E402
from rl_exp.tasks.teacher_mdp import (  # noqa: E402
    JOINT_SIR_TERM,
    JointSIRTerrainCurriculum,
    JointSIRTerrainCurriculumCfg,
    ParticleVelocityCommand,
)

NUM_ENVS = 6
GRID = {
    "num_rows": 2,
    "num_cols": 12,
    "stairs": {"proportion": 0.5, "step_height": [0.1, 0.2], "step_width": [0.5, 0.7, 0.9]},
    "random_rough": {"proportion": 0.3, "noise_amp": [0.1, 0.2]},
    "flat": {"proportion": 0.2},
}
VEL_BUCKETS = (0.5, 1.0, 1.5)


class _Scene(dict):
    """Scene mock: attribute access for the terrain."""

    def __init__(self, terrain):
        super().__init__()
        self.terrain = terrain


def _terrain():
    cfg = build_param_grid_terrain_cfg(GRID)
    origins = torch.zeros(2, 12, 3)
    origins[:, :, 0] = torch.arange(2).unsqueeze(1) * 100.0
    origins[:, :, 1] = torch.arange(12).unsqueeze(0)
    gen_cfg = SimpleNamespace(sub_terrains=cfg.sub_terrains)
    # importer formula (terrain_importer.py:348-350): env i -> initial column
    types = torch.tensor([0, 2, 6, 8, 10, 11], dtype=torch.long)
    return SimpleNamespace(
        cfg=SimpleNamespace(terrain_generator=gen_cfg),
        terrain_origins=origins,
        terrain_levels=torch.zeros(NUM_ENVS, dtype=torch.long),
        terrain_types=types,
        env_origins=torch.zeros(NUM_ENVS, 3),
    )


def _cmd(nu, steps):
    return SimpleNamespace(_nu_sum=nu, _step_count=steps)


def _env(terrain, cmd=None, *, counter=0, lengths=None):
    lengths = torch.zeros(NUM_ENVS, dtype=torch.long) if lengths is None else lengths
    return SimpleNamespace(
        scene=_Scene(terrain),
        command_manager=SimpleNamespace(get_term=lambda name: cmd),
        episode_length_buf=lengths,
        common_step_counter=counter,
        num_envs=NUM_ENVS,
    )


def _term(env, **overrides):
    defaults = dict(
        band=(0.5, 0.9), velocity_buckets=VEL_BUCKETS, particles_per_type=4,
        eval_every=10, n_traj_min=6, p_transition=0.8, p_replay=0.05,
        maintain_mass=0.1, steps_per_iteration=24, command_name="base_velocity",
    )
    defaults.update(overrides)
    return JointSIRTerrainCurriculum(
        JointSIRTerrainCurriculumCfg(func=JointSIRTerrainCurriculum, **defaults), env
    )


def test_builder_combos_and_ranges() -> None:
    cfg = build_param_grid_terrain_cfg(GRID)
    assert set(cfg.sub_terrains) == {
        "stairs|0_0", "stairs|0_1", "stairs|0_2", "stairs|1_0", "stairs|1_1", "stairs|1_2",
        "random_rough|0", "random_rough|1", "flat",
    }
    stairs = cfg.sub_terrains["stairs|1_2"]
    assert stairs.step_height_range == (0.2, 0.2)
    assert stairs.step_width == 0.9
    assert abs(stairs.proportion - 0.5 / 6) < 1e-12
    assert cfg.curriculum is True and cfg.num_cols == 12 and cfg.num_rows == 2
    # column starvation guard
    bad = dict(GRID)
    bad["num_cols"] = 6
    try:
        build_param_grid_terrain_cfg(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("num_cols=6 must raise (stairs combos lose their column)")


def test_parse_split_and_radix() -> None:
    term = _term(_env(_terrain()))
    assert term._types == ["stairs", "random_rough", "flat"]
    assert term._n_levels[0] == [2, 3] and term._n_pairs[0] == 18
    assert [c.numel() for c in term._combo_cols[0]] == [1] * 6
    assert [c.numel() for c in term._combo_cols[1]] == [2, 2]
    assert [c.numel() for c in term._combo_cols[2]] == [2]
    # env -> type follows the initial columns [0, 2, 6, 8, 10, 11]
    assert term._env_type.tolist() == [0, 0, 1, 1, 2, 2]
    # mixed-radix roundtrip (last axis fastest, product order)
    assert term._decode_levels(0, 5) == [1, 2]
    assert term._encode_combo(0, [1, 2]) == 5
    assert term._decode_levels(0, 4) == [1, 1]


def test_initial_spawn_reassigns_all_envs() -> None:
    torch.manual_seed(0)
    t = _terrain()
    env = _env(t)  # initial full reset: episode_length_buf all zero
    term = _term(env)
    out = term(env, torch.arange(NUM_ENVS))
    # no stats pollution from the initial reset
    assert all(float(e.sum()) == 0.0 for e in term._episodes)
    assert all(float(b.sum()) == 0.0 for b in term._in_band)
    # every env got a pair + a bucket velocity
    assert (term._env_pair >= 0).all()
    assert torch.isin(term.desired_vel, torch.tensor(VEL_BUCKETS)).all()
    # spawn origins consistent with (row, col); columns stay within the env's type
    bounds = {0: (0, 5), 1: (6, 9), 2: (10, 11)}
    for i in range(NUM_ENVS):
        r, c = int(t.terrain_levels[i]), int(t.terrain_types[i])
        assert torch.equal(t.env_origins[i], t.terrain_origins[r, c])
        assert 0 <= r < 2
        lo, hi = bounds[int(term._env_type[i])]
        assert lo <= c <= hi
    # metrics dict contract
    assert set(out) == {"frontier_max_v", "particle_entropy", "tr_mean"}
    assert 0.5 <= out["frontier_max_v"] <= 1.5


def test_measurement_eq7_and_throttle() -> None:
    torch.manual_seed(0)
    t = _terrain()
    env = _env(t)
    term = _term(env)
    term(env, torch.arange(NUM_ENVS))  # initial spawn
    # pin every type to pair 0 (easiest combo, v bucket 0)
    for ti in range(3):
        term._particles[ti] = torch.zeros(4, dtype=torch.long)
    nu = torch.tensor([80.0, 80.0, 20.0, 20.0, 95.0, 95.0])  # Tr = 0.8 / 0.2 / 0.95
    steps = torch.full((NUM_ENVS,), 100.0)
    for _ in range(6):
        e = _env(t, _cmd(nu.clone(), steps.clone()), counter=0, lengths=torch.ones(NUM_ENVS, dtype=torch.long))
        term(e, torch.arange(NUM_ENVS))
    # below the eval block boundary: counters accumulate, no resample
    assert float(term._episodes[0].sum()) == 12.0
    assert float(term._in_band[0].sum()) == 12.0
    # block boundary triggers the resample
    e = _env(t, _cmd(nu.clone(), steps.clone()), counter=240, lengths=torch.ones(NUM_ENVS, dtype=torch.long))
    term(e, torch.arange(NUM_ENVS))
    assert float(term._episodes[0].sum()) == 0.0
    # stairs pair 0: 12/12 in-band episodes -> Eq. 7 weight 1.0, mixed with the
    # 17 sparse pairs keeping their uniform prior 1/18, then normalized
    w = term._weights[0]
    assert abs(float(w[0]) - 18.0 / 35.0) < 1e-6
    assert abs(float(w.sum()) - 1.0) < 1e-6
    # rough pair 0 measured out-of-band (Tr 0.2): weight zeroed
    assert float(term._weights[1][0]) == 0.0
    # flat pair 0 measured Tr 0.95 (learned, out of band above) -> weight 0;
    # the unmeasured v-neighbors keep their uniform prior -> normalized 0.5
    # (the mixed fallback itself is unit-tested in test_fallback_branches_unit)
    wf = term._weights[2]
    assert float(wf[0]) == 0.0
    assert abs(float(wf[1]) - 0.5) < 1e-6
    assert abs(float(wf[2]) - 0.5) < 1e-6


def test_sparse_pair_accumulates_across_blocks() -> None:
    """v11.1: a pair below n_traj_min keeps its counters across blocks.

    The pre-fix ``_resample_all`` zeroed every pair each block, so
    low-traffic pairs never accumulated evidence and kept their initial
    uniform weight forever (the SIR degraded to a random walk for them).
    """
    torch.manual_seed(4)
    t = _terrain()
    term = _term(_env(t))
    ones = torch.ones(NUM_ENVS, dtype=torch.long)
    nu = torch.full((NUM_ENVS,), 80.0)  # Tr 0.8 -> in band
    steps = torch.full((NUM_ENVS,), 100.0)
    e = _env(t, _cmd(nu.clone(), steps.clone()), counter=0, lengths=ones)
    # the respawn at the end of each call reassigns pairs, and the init value
    # is -1 (unset -- index_add_ rejects it), so point every env at pair 0
    # of its own type before each call (envs 0-1 = stairs, 2-3 = rough, 4-5 = flat)
    term._env_pair[:] = 0
    term(e, torch.arange(NUM_ENVS))
    term._env_pair[:] = 0
    term(e, torch.arange(NUM_ENVS))
    term._resample_all()  # block boundary with only 4 episodes on pair 0
    assert float(term._episodes[0][0]) == 4.0  # unsettled -> counter KEPT
    assert abs(float(term._weights[0][0]) - 1.0 / 18.0) < 1e-6  # prior kept
    term._env_pair[:] = 0
    term(e, torch.arange(NUM_ENVS))  # 2 more -> 6 >= n_traj_min
    term._resample_all()
    assert float(term._episodes[0][0]) == 0.0  # settled -> counter reset
    assert abs(float(term._weights[0][0]) - 18.0 / 35.0) < 1e-6  # Eq. 7 measured


def test_fallback_branches_unit() -> None:
    term = _term(_env(_terrain()))
    episodes = torch.zeros(18)
    tr_sum = torch.zeros(18)
    episodes[0] = 6.0
    tr_sum[0] = 5.7  # Tr 0.95 -> learned
    episodes[[3, 15]] = 6.0
    tr_sum[[3, 15]] = 0.6  # Tr 0.1 -> unlearned
    w = term._fallback_weights(0, episodes, tr_sum)
    assert abs(float(w[0]) - 0.1) < 1e-6  # learned: maintenance share
    assert abs(float(w[1]) - 0.3) < 1e-6  # v+1 frontier
    assert abs(float(w[3]) - 0.3) < 1e-6  # combo(0,1) frontier
    assert abs(float(w[9]) - 0.3) < 1e-6  # combo(1,0) frontier
    assert float(w[15]) == 0.0  # unlearned, not adjacent: no mass
    # all-failed (cold start) -> uniform
    episodes = torch.zeros(18)
    episodes[0] = 6.0
    tr_sum = torch.zeros(18)
    w = term._fallback_weights(0, episodes, tr_sum)
    assert torch.allclose(w, torch.full((18,), 1.0 / 18))
    # all-learned -> uniform
    episodes = torch.full((18,), 6.0)
    tr_sum = torch.full((18,), 6.0)  # Tr 1.0
    w = term._fallback_weights(0, episodes, tr_sum)
    assert torch.allclose(w, torch.full((18,), 1.0 / 18))
    # nothing measured -> uniform
    w = term._fallback_weights(0, torch.zeros(18), torch.zeros(18))
    assert torch.allclose(w, torch.full((18,), 1.0 / 18))


def test_walk_single_axis_and_clamp() -> None:
    term = _term(_env(_terrain()))
    torch.manual_seed(1)
    start = torch.tensor([5 * 3 + 2, 0, 4 * 3 + 1, 2])
    for _ in range(8):  # cover several axis/direction draws
        out = term._walk(0, start)
        for a, b in zip(start.tolist(), out.tolist()):
            ca, va = divmod(a, 3)
            cb, vb = divmod(b, 3)
            la = term._decode_levels(0, ca)
            lb = term._decode_levels(0, cb)
            assert 0 <= vb < 3
            assert all(0 <= l < n for l, n in zip(lb, term._n_levels[0]))
            diffs = [abs(x - y) for x, y in zip(la, lb)]
            assert sum(diffs) + abs(va - vb) <= 1  # single axis, one level


def test_replay_redraw() -> None:
    torch.manual_seed(2)
    t = _terrain()
    term = _term(_env(t), p_replay=1.0)
    pool_before = term._history[0].clone()
    term._resample_all()
    assert set(term._particles[0].tolist()) <= set(pool_before.tolist())


def test_command_term_sources_particle_velocity() -> None:
    sir = SimpleNamespace(desired_vel=torch.tensor([1.0, -1.0]))
    env = SimpleNamespace(
        device="cpu",
        curriculum_manager=SimpleNamespace(
            cfg=SimpleNamespace(**{JOINT_SIR_TERM: SimpleNamespace(func=sir)})
        ),
    )
    cmd = ParticleVelocityCommand.__new__(ParticleVelocityCommand)
    cmd._env = env
    cmd.cfg = SimpleNamespace(
        command_jitter=0.0,
        v_pr_threshold=0.2,
        ranges=SimpleNamespace(lin_vel_x=(0.0, 3.0), lin_vel_y=(-0.5, 0.5), ang_vel_z=(-1.0, 1.0), heading=None),
        heading_command=False,
        rel_heading_envs=0.0,
        rel_standing_envs=0.0,
    )
    cmd.vel_command_b = torch.zeros(2, 3)
    cmd.is_heading_env = torch.zeros(2, dtype=torch.bool)
    cmd.is_standing_env = torch.zeros(2, dtype=torch.bool)
    cmd.heading_target = torch.zeros(2)
    torch.manual_seed(3)
    cmd._resample_command([0, 1])
    assert cmd.vel_command_b[0, 0] == 1.0  # particle bucket value
    assert 0.0 <= cmd.vel_command_b[1, 0] < 3.0  # unset (-1) -> range fallback
    # 0.0 is a legal bucket value (sentinel is -1); the pre-v11.1 ``> 0.0``
    # test swallowed it into the range fallback
    sir.desired_vel = torch.tensor([0.0, -1.0])
    cmd.vel_command_b[:] = 0.0
    cmd._resample_command([0, 1])
    assert cmd.vel_command_b[0, 0] == 0.0
    assert 0.0 <= cmd.vel_command_b[1, 0] < 3.0
    # no curriculum term (PLAY): full fallback
    setattr(env.curriculum_manager.cfg, JOINT_SIR_TERM, None)
    cmd.vel_command_b[:] = 0.0
    cmd._resample_command([0, 1])
    assert 0.0 <= cmd.vel_command_b[0, 0] < 3.0
    # jitter stays within the band around the bucket value
    setattr(env.curriculum_manager.cfg, JOINT_SIR_TERM, SimpleNamespace(func=sir))
    cmd.cfg.command_jitter = 0.1
    sir.desired_vel = torch.tensor([1.0, -1.0])
    cmd.vel_command_b[:] = 0.0
    cmd._resample_command([0, 1])
    assert abs(float(cmd.vel_command_b[0, 0]) - 1.0) <= 0.1


def test_command_term_eq2_labels() -> None:
    cmd = ParticleVelocityCommand.__new__(ParticleVelocityCommand)
    cmd._env = SimpleNamespace(device="cpu")
    cmd.cfg = SimpleNamespace(v_pr_threshold=0.2)
    cmd.vel_command_b = torch.tensor([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    v = torch.tensor([[0.5, 0.0, 0.0], [0.1, 0.0, 0.0]])
    cmd.robot = SimpleNamespace(
        data=SimpleNamespace(
            root_lin_vel_b=SimpleNamespace(torch=v),
            root_ang_vel_b=SimpleNamespace(torch=torch.zeros_like(v)),
        )
    )
    cmd._error_xy_sum = torch.zeros(2)
    cmd._error_yaw_sum = torch.zeros(2)
    cmd._step_count = torch.zeros(2)
    cmd._nu_sum = torch.zeros(2)
    cmd._update_metrics()
    assert cmd._nu_sum.tolist() == [1.0, 0.0]  # v_pr 0.5 > 0.2 / 0.1 < 0.2
    # zero command -> no direction -> label 0
    cmd.vel_command_b[0] = 0.0
    v[0, 0] = 2.0
    cmd._update_metrics()
    assert cmd._nu_sum.tolist() == [1.0, 0.0]


def _main() -> None:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"[OK] {fn.__name__}")
    print(f"test_joint_sir: {len(tests)} passed")


if __name__ == "__main__":
    _main()
