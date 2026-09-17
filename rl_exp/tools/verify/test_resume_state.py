# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).

# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline test for the true-resume curriculum state (ARCH_PLAN 1.3a, S01-S10).

Round-trips the registered SIR terms + the c_k clock through the checkpoint payload and
pins the policy gates that keep a resume honest:

* S01/S03 bitwise round-trip of every runtime tensor, the counter and the derived c_k for
  the joint SIR, the row SIR and a c_k-only task; ``collect`` hands out copies, and no
  joint-only field is fabricated into a row-SIR term
* S02 the row SIR fingerprint: a grid edit, a reordered equal-proportion type (the same
  column split!), a retuned terrain parameter and each of its 9 cfg entries abort
* S04 the c_k schedule is evidence: the counter alone is not, and changing c0/decay/
  steps_per_iteration or the existence of c_k is refused
* S05 identity/corruption: task, env count, unknown version, NaN/Inf, negative counts,
  out-of-range particles/history/env_type, bad shapes and a broken eval clock are
  rejected instead of restored
* S06 nothing is written until every slot has passed; two terms of one class are refused
* S07 hard-fail boundaries: a declared task without a payload or slot aborts, an
  uncovered stateful term is reported, a registered class wired un-instantiated aborts
* S08 v1 payloads migrate with their missing evidence listed (never backfilled); the
  deprecated ``weights_only`` entry works, and contradicting it is an error
* S09 the declaration is a class attribute (V5..V14 inherit it, PLAY overrides it) that
  does not enter the config data; a non-zero rank neither restores nor saves
* S10 the manifest records the outcome ``apply_resume_state`` returned (test_run_manifest)
* B-layer (1.4a): both SIR terms, given the same statistics and a reset RNG, produce the
  same curriculum update -- driven through the production entry point and per update
  branch (measured update, below ``n_traj_min``, band-empty fallback, walk, replay), each
  fixture asserting the branch it claims to hit; and the c_k-only clock is compared
  against an independently recomputed c_k from the SAVED schedule around the boundaries

NOTE: this proves the payload round-trip and the update mapping, NOT the wiring timing.
That the restore lands before the wrapper's first full reset is train.py behavior and
only a smoke run proves it (1.4b C layer).
"""

import math
import os
import pathlib
import sys
import tempfile
from types import SimpleNamespace

import torch

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from isaaclab.managers import ManagerTermBase  # noqa: E402

import cfg_snapshot as cs  # noqa: E402

from rl_exp.tasks.curriculum_state import (  # noqa: E402
    REQUIRES_CURRICULUM_STATE,
    STATE_KEY,
    _tensor_eq,
    adapter_for,
    apply_resume_state,
    apply_state,
    collect,
    declares,
    expected_terms,
    hook_runner_save,
    static_state,
    uncovered_terms,
    verify_declaration,
    wired_terms,
)
from rl_exp.tasks.param_grid_terrain import build_param_grid_terrain_cfg  # noqa: E402
from rl_exp.tasks.teacher_env_cfg import (  # noqa: E402
    LizardRoughTeacherEnvCfg_V4,
    LizardRoughTeacherEnvCfg_V5,
    LizardRoughTeacherEnvCfg_V13_PLAY,
    LizardRoughTeacherEnvCfg_V14,
)
from rl_exp.tasks.teacher_mdp import JOINT_SIR_TERM, ck_value, init_ck  # noqa: E402
from rl_exp.tools.verify import terrain_split_probe as probe  # noqa: E402
from test_joint_sir import (  # noqa: E402
    GRID,
    NUM_ENVS,
    _cmd as _sir_cmd,
    _env as _sir_env,
    _terrain,
    _term,
)
from test_v5_terrain_sir import NUM_ENVS as ROW_ENVS  # noqa: E402
from test_v5_terrain_sir import _env as _row_env  # noqa: E402
from test_v5_terrain_sir import _term as _row_term  # noqa: E402

CK = dict(c0=0.2, decay=0.98, steps_per_iteration=24)
"""The v3 c_k schedule used by the tests (matches the v11 yaml section)."""

ROW_SEED = 31
"""Fixed test RNG seed for the B-layer row-SIR comparisons (both sides reseeded per call)."""

JOINT_SEED = 32
"""Fixed test RNG seed for the B-layer joint-SIR comparisons."""

ROW_TERM = "terrain_levels"
"""The term name V5..V14 wire the row SIR under."""

ROW_CFG_KEYS = (
    "command_name",
    "band",
    "eval_every",
    "n_traj_min",
    "p_transition",
    "p_replay",
    "success_ratio",
    "soft_edge",
    "steps_per_iteration",
)
ROW_CFG_OTHER = {
    "command_name": "other_velocity",
    "band": (0.4, 0.8),
    "eval_every": 5,
    "n_traj_min": 4,
    "p_transition": 0.5,
    "p_replay": 0.2,
    "success_ratio": 0.7,
    "soft_edge": 0.1,
    "steps_per_iteration": 12,
}


class _TaskCfgV12:
    """Stand-in env cfg class (the identity check reads the class name)."""


class _TaskCfgV11:
    """A different recipe name, to exercise the task-identity gate."""


def _env(terrain, term, *, counter=0, cmd=None, lengths=None, cfg_cls=_TaskCfgV12):
    """Env mock with the curriculum manager wired the way ManagerBase wires it."""
    env = _sir_env(terrain, cmd, counter=counter, lengths=lengths)
    env.cfg = cfg_cls()
    env.curriculum_manager = SimpleNamespace(
        cfg=SimpleNamespace(**{JOINT_SIR_TERM: None if term is None else SimpleNamespace(func=term)})
    )
    return env


def _pair(terrain, cfg_cls=_TaskCfgV12):
    """(env, term) with the c_k schedule armed, as the startup event leaves it."""
    term = _term(_env(terrain, None))
    env = _env(terrain, term, cfg_cls=cfg_cls)
    init_ck(env, None, **CK)
    return env, term


def _drive(env, term, *, blocks=3, counter=0):
    """Spawn, accumulate real Eq. 2/3 evidence, then run one SIR resample."""
    ids = torch.arange(NUM_ENVS)
    term(env, ids)
    nu = torch.tensor([80.0, 80.0, 20.0, 20.0, 95.0, 95.0])  # Tr 0.8 / 0.2 / 0.95
    steps = torch.full((NUM_ENVS,), 100.0)
    for _ in range(blocks):
        term._env_pair[:] = 0  # index_add_ rejects the -1 spawn sentinel
        e = _env(env.scene.terrain, term, counter=counter, cmd=_sir_cmd(nu.clone(), steps.clone()),
                 lengths=torch.ones(NUM_ENVS, dtype=torch.long))
        term(e, ids)
    term._resample_all()  # non-uniform weights, zeroed settled counters
    term._next_eval_step = 240  # first block edge (10 x 24), above counter 123
    term._tr_block_sum, term._tr_block_count = 1.7, 6
    env.common_step_counter = 123
    return env, term


def _write_ckpt(path, *, state=None, it=9, lr=5.0e-4):
    """A checkpoint shaped like rsl_rl's: optimizer dict + iter + infos."""
    ckpt = {"iter": it, "optimizer_state_dict": {"param_groups": [{"lr": lr}]}, "infos": None}
    if state is not None:
        ckpt["infos"] = {STATE_KEY: state}
    torch.save(ckpt, path)
    return path


def _only_slot(state: dict) -> str:
    """Name of the single covered term slot in a v2 payload (these tests wire one term)."""
    names = list(state["terms"])
    assert len(names) == 1, f"expected exactly one covered term, got {names}"
    return names[0]


def test_roundtrip_bitwise_and_ck_continuity() -> None:
    torch.manual_seed(11)
    env1, term1 = _pair(_terrain())
    env1, term1 = _drive(env1, term1)
    state = collect(env1, it=5)
    assert state is not None and state["clock"]["common_step_counter"] == 123
    assert state["written_at_iter"] == 5 and state["task"] == "_TaskCfgV12"
    assert state["num_envs"] == NUM_ENVS
    # regression cover for the joint SIR's historical field set: a slot that silently
    # loses one of these would still round-trip, just with that state gone
    assert set(state["terms"][JOINT_SIR_TERM]["runtime"]) == {
        "particles", "estimate", "episodes", "in_band", "history",
        "env_pair", "desired_vel", "env_type", "next_eval_step",
        "tr_block_sum", "tr_block_count", "last_tr_mean",
        "invalid_block", "traj_block", "last_invalid_frac",
        "tr_type_sum", "tr_type_count", "last_tr_by_type",
    }

    env2, term2 = _pair(_terrain())  # cold: cold-start particles, clock at 0
    assert env2.common_step_counter == 0
    reports: list[str] = []
    apply_state(env2, state, report=reports.append)

    for key in ("particles", "estimate", "episodes", "in_band", "history"):
        a, b = getattr(term1, "_" + key), getattr(term2, "_" + key)
        assert len(a) == len(b)
        assert all(torch.equal(x, y) for x, y in zip(a, b)), key
    assert torch.equal(term1._env_pair, term2._env_pair)
    assert torch.equal(term1.desired_vel, term2.desired_vel)
    assert torch.equal(term1._env_type, term2._env_type)
    assert term2._next_eval_step == term1._next_eval_step == 240
    assert term2._tr_block_count == 6 and abs(term2._tr_block_sum - 1.7) < 1e-12
    assert term2._last_tr_mean == term1._last_tr_mean
    assert env2.common_step_counter == 123
    assert ck_value(env2) == ck_value(env1)  # the c_k clock continues, not re-heats
    assert abs(float(term2._estimate[0].max()) - float(term1._estimate[0].max())) < 1e-12
    assert float(term2._estimate[0].min()) >= 0.0 and float(term2._estimate[0].max()) <= 1.0
    assert not [r for r in reports if "WARN" in r]


def test_static_fingerprint_catches_grid_edit() -> None:
    """A terrain-grid edit shifts the column split while n_pairs stays put."""
    torch.manual_seed(3)
    env1, term1 = _pair(_terrain())
    state = collect(env1)

    cfg13 = build_param_grid_terrain_cfg({**GRID, "num_cols": 13})
    probe.generate_record(cfg13)  # the term reads the record of a real generation
    origins = torch.zeros(2, 13, 3)
    terrain13 = SimpleNamespace(
        cfg=SimpleNamespace(terrain_generator=cfg13),
        terrain_origins=origins,
        terrain_levels=torch.zeros(NUM_ENVS, dtype=torch.long),
        terrain_types=torch.tensor([0, 2, 7, 9, 11, 12], dtype=torch.long),
        env_origins=torch.zeros(NUM_ENVS, 3),
    )
    env2, term2 = _pair(terrain13)

    saved = state["terms"][_only_slot(state)]["static"]
    now = static_state(term2, env2)
    assert saved["n_pairs"] == now["n_pairs"]  # counts alone would NOT catch this
    assert saved["n_v"] == now["n_v"]
    assert not _tensor_eq(saved["combo_cols"], now["combo_cols"])

    try:
        apply_state(env2, state, report=lambda *_: None)
    except ValueError as exc:
        assert "static.combo_cols" in str(exc) or "static.velocity" in str(exc), str(exc)
    else:
        raise AssertionError("a re-split terrain grid must abort the restore")


def test_velocity_bucket_mismatch_rejected() -> None:
    torch.manual_seed(4)
    env1, term1 = _pair(_terrain())
    state = collect(env1)
    env2, term2 = _pair(_terrain())
    term2.cfg.velocity_buckets = (0.5, 1.0)  # yaml edit: fewer velocity levels
    try:
        apply_state(env2, state, report=lambda *_: None)
    except ValueError as exc:
        assert "static" in str(exc)
    else:
        raise AssertionError("velocity-bucket drift must abort the restore")


def test_eval_clock_accepts_a_pending_edge_and_rejects_a_stale_one() -> None:
    """A checkpoint saved at (or just past) an edge before the term was called is resumable.

    The term re-arms only when it is called, and it is called on the first step at/after the
    edge where an env resets (real runs: the 240 edge fired at clock 247). A payload saved in
    that window legitimately carries ``next_eval_step <= counter`` -- the update is pending.
    A schedule a whole block behind the counter is still refused (changed block size /
    hand-edited payload).
    """
    block = 240

    def restore_with(counter: int, next_eval: int):
        torch.manual_seed(9)
        env1, term1 = _pair(_terrain())
        state = collect(env1)
        env2, term2 = _pair(_terrain())
        slot = state["terms"][_only_slot(state)]["runtime"]
        slot["next_eval_step"] = next_eval
        state["clock"]["common_step_counter"] = counter
        term2._next_eval_step = next_eval
        apply_state(env2, state, report=lambda *_: None)
        return term2

    for counter, next_eval, why in (
        (960, 960, "saved exactly on the edge, before the term re-armed"),
        (962, 960, "saved a few steps past the edge, before any env reset"),
        (960, 1200, "the usual case: the edge is ahead of the counter"),
    ):
        term = restore_with(counter, next_eval)
        assert term._next_eval_step == next_eval, (counter, next_eval, why)

    for counter, next_eval in ((500, 240), (960, 720), (960, 240)):
        try:
            restore_with(counter, next_eval)
        except ValueError as exc:
            assert "next_eval_step" in str(exc), (counter, next_eval, exc)
        else:
            raise AssertionError(f"a schedule a block or more behind the clock must abort ({counter}, {next_eval})")


def test_corrupt_clock_and_weights_rejected() -> None:
    torch.manual_seed(5)
    env1, term1 = _pair(_terrain())
    state = collect(env1)
    env2, term2 = _pair(_terrain())

    slot = state["terms"][_only_slot(state)]["runtime"]
    slot["next_eval_step"] = 240
    state["clock"]["common_step_counter"] = 500  # block edge is now in the past
    try:
        apply_state(env2, state, report=lambda *_: None)
    except ValueError as exc:
        assert "next_eval_step" in str(exc)
    else:
        raise AssertionError("an eval edge below the restored clock must abort")

    state["clock"]["common_step_counter"] = 0
    # the joint term's sampling source is a raw band probability in [0, 1] (review
    # 2026-09-16 #4), so the corruption that must abort is an out-of-range estimate
    slot["estimate"][0] = slot["estimate"][0].clone()
    slot["estimate"][0].fill_(-0.5)
    try:
        apply_state(env2, state, report=lambda *_: None)
    except ValueError as exc:
        assert "estimate" in str(exc)
    else:
        raise AssertionError("an out-of-range estimate must abort")


def test_task_identity_mismatch_rejected() -> None:
    torch.manual_seed(6)
    env1, term1 = _pair(_terrain(), cfg_cls=_TaskCfgV11)
    state = collect(env1)
    env2, term2 = _pair(_terrain())  # _TaskCfgV12
    try:
        apply_state(env2, state, report=lambda *_: None)
    except ValueError as exc:
        assert "task" in str(exc)
    else:
        raise AssertionError("resuming a v11 checkpoint into a v12 task must abort")


def test_env_type_mismatch_warns_and_restores_saved() -> None:
    torch.manual_seed(7)
    env1, term1 = _pair(_terrain())
    state = collect(env1)
    terrain2 = _terrain()
    terrain2.terrain_types = torch.tensor([1, 3, 5, 7, 9, 11], dtype=torch.long)  # other draw
    env2, term2 = _pair(terrain2)
    reports: list[str] = []
    apply_state(env2, state, report=reports.append)
    assert any("per-env terrain-type draw differs" in r for r in reports)
    assert torch.equal(term2._env_type, term1._env_type)


def test_termless_task_passthrough() -> None:
    torch.manual_seed(8)
    env1, term1 = _pair(_terrain())
    state = collect(env1)
    env_play = _env(_terrain(), None)  # PLAY: curriculum.joint_sir = None
    assert collect(env_play) is None
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_ckpt(pathlib.Path(tmp) / "model_9.pt", state=state)
        reports: list[str] = []
        assert apply_resume_state(env_play, path, report=reports.append)["status"] == "no_state"
        assert any("wires no" in r for r in reports)
    assert env_play.common_step_counter == 0


def test_missing_state_hard_aborts_and_weights_only_opts_out() -> None:
    torch.manual_seed(9)
    env1, term1 = _pair(_terrain())
    env1, term1 = _drive(env1, term1)
    state = collect(env1)
    env2, term2 = _pair(_terrain())
    cold = term2._particles[0].clone()

    with tempfile.TemporaryDirectory() as tmp:
        stateless = _write_ckpt(pathlib.Path(tmp) / "model_9.pt")
        try:
            apply_resume_state(env2, stateless, report=lambda *_: None)
        except RuntimeError as exc:
            assert "--drop_curriculum_state" in str(exc)
        else:
            raise AssertionError("a stateless checkpoint on a joint-SIR task must abort")
        assert env2.common_step_counter == 0 and torch.equal(term2._particles[0], cold)

        stated = _write_ckpt(pathlib.Path(tmp) / "model_10.pt", state=state, it=10)
        reports: list[str] = []
        # ``weights_only`` is the deprecated alias of ``drop_curriculum_state``; both must opt out
        assert apply_resume_state(env2, stated, weights_only=True, report=reports.append)["status"] == "dropped"
        assert any("--drop_curriculum_state" in r and "dropped" in r for r in reports)
        assert env2.common_step_counter == 0 and torch.equal(term2._particles[0], cold)

        reports = []
        assert apply_resume_state(env2, stated, report=reports.append)["status"] == "restored"
        assert env2.common_step_counter == 123
        assert torch.equal(term2._particles[0], state["terms"][_only_slot(state)]["runtime"]["particles"][0])
        assert any("iter=10" in r and "lr=0.0005" in r for r in reports)
        assert any("particle_entropy" in r for r in reports)


def test_hook_runner_save_rides_and_passes_through() -> None:
    class _Runner:
        is_distributed = False
        gpu_global_rank = 0
        current_learning_iteration = 7

        def __init__(self):
            self.calls = []

        def save(self, path, infos=None, *args, **kwargs):
            self.calls.append((path, infos, args, kwargs))
            return "saved"

    torch.manual_seed(10)
    env, term = _pair(_terrain())
    env, term = _drive(env, term, blocks=1)
    runner = _Runner()
    reports: list[str] = []
    hook_runner_save(runner, env, report=reports.append)
    assert runner.save.__name__ == "save"  # functools.wraps kept the signature name

    assert runner.save("model_7.pt") == "saved"
    path, infos, _, _ = runner.calls[-1]
    assert path == "model_7.pt" and STATE_KEY in infos
    assert infos[STATE_KEY]["written_at_iter"] == 7
    assert any("model_7.pt" in r and "counter=" in r for r in reports)

    runner.save("model_8.pt", {"custom": 1}, "extra")
    _, infos, args, _ = runner.calls[-1]
    assert infos["custom"] == 1 and STATE_KEY in infos and args == ("extra",)

    termless = _Runner()
    hook_runner_save(termless, _env(_terrain(), None), report=reports.append)
    termless.save("model_9.pt")
    assert termless.calls[-1][1] is None  # untouched for tasks without the term


def test_uncovered_stateful_term_tripwire() -> None:
    torch.manual_seed(12)
    env, term = _pair(_terrain())
    fake = object.__new__(type("_FakeStatefulTerm", (ManagerTermBase,), {}))
    setattr(env.curriculum_manager.cfg, "speed_curriculum", SimpleNamespace(func=fake))
    assert uncovered_terms(env) == ["speed_curriculum"]

    with tempfile.TemporaryDirectory() as tmp:
        path = _write_ckpt(pathlib.Path(tmp) / "model_9.pt", state=collect(env))
        reports: list[str] = []
        apply_resume_state(env, path, report=reports.append)
    assert any("not covered by any registered adapter" in r for r in reports)


# --- row SIR (v5..v14 line) + c_k-only + the boundary cases ------------------------


class _TaskCfgV14:
    """Stand-in env cfg: the v14 recipe declares the curriculum contract, as the real class does."""

    REQUIRES_CURRICULUM_STATE = True


class _TaskCfgV14Plain:
    """The same recipe WITHOUT the declaration (a task that tolerates a cold curriculum)."""


_ROW_CFGS: dict[tuple, object] = {}


def _row_generator_cfg(names, props, rows, cols):
    """A real generator cfg (flat planes: cheap) with one real generation behind it.

    The row-SIR term consumes the record of the generation that ran (ARCH_PLAN Step 3.3d);
    the column split is the generator's, not something this test writes down.
    """
    key = (tuple(names), tuple(props), rows, cols)
    if key not in _ROW_CFGS:
        from isaaclab.terrains import MeshPlaneTerrainCfg, TerrainGeneratorCfg

        cfg = TerrainGeneratorCfg(
            size=(2.0, 2.0), border_width=0.5, num_rows=rows, num_cols=cols,
            curriculum=True, seed=0, use_cache=False,
            sub_terrains={name: MeshPlaneTerrainCfg(proportion=p) for name, p in zip(names, props)},
        )
        probe.generate_record(cfg)
        _ROW_CFGS[key] = cfg
    return _ROW_CFGS[key]


def _row_grid(names, props, *, rows=10, cols=20):
    """A row-SIR terrain grid: ordered sub-terrain names, proportions, column split."""
    origins = torch.zeros(rows, cols, 3)
    origins[:, :, 0] = torch.arange(rows).unsqueeze(1) * 100.0
    origins[:, :, 1] = torch.arange(cols).unsqueeze(0) * 1.0
    types = (torch.arange(ROW_ENVS).float() / (ROW_ENVS / cols)).long()
    return SimpleNamespace(
        cfg=SimpleNamespace(terrain_generator=_row_generator_cfg(names, props, rows, cols)),
        terrain_origins=origins,
        terrain_levels=torch.zeros(ROW_ENVS, dtype=torch.long),
        terrain_types=types,
        env_origins=torch.zeros(ROW_ENVS, 3),
    )


def _row_pair(terrain=None, *, counter=0, cfg_cls=_TaskCfgV14):
    """(env, term) for the row SIR line, wired and c_k-armed the way V5..V14 wire it."""
    terrain = _row_grid(("t0", "t1", "t2"), (0.2, 0.3, 0.5)) if terrain is None else terrain
    env = _row_env(terrain, counter=counter)
    env.cfg = cfg_cls()
    env.num_envs = ROW_ENVS
    term = _row_term(env)
    env.curriculum_manager = SimpleNamespace(cfg=SimpleNamespace(**{ROW_TERM: SimpleNamespace(func=term)}))
    init_ck(env, None, **CK)
    return env, term


def _ck_only_env(*, counter=0, ck=True):
    """An env that wires no curriculum term and only runs the c_k clock (v3/v4 line)."""
    env = _row_env(_row_grid(("t0", "t1", "t2"), (0.2, 0.3, 0.5)), counter=counter)
    env.cfg = _TaskCfgV14()
    env.num_envs = ROW_ENVS
    env.curriculum_manager = SimpleNamespace(cfg=SimpleNamespace(terrain_levels=None))
    if ck:
        init_ck(env, None, **CK)
    return env


def _perturb_row(term):
    """Give every row-SIR runtime field a value the cold term does not have."""
    for t in range(term._num_types):
        term._weights[t] = torch.full((term._num_rows,), 1.0 + 0.5 * t)
        term._weights[t] = term._weights[t] / term._weights[t].sum()
        term._particles[t] = torch.arange(term._num_rows - 1, -1, -1)
        term._episodes[t] = torch.full((term._num_rows,), 3.0)
        term._successes[t] = torch.full((term._num_rows,), 1.0)
        term._history[t] = torch.arange(term._num_rows, dtype=torch.long) % term._num_rows
    term._next_eval_step = 240


def _row_payload(*, counter=120):
    """A row-SIR payload carrying a non-initial state (S01's fixture)."""
    torch.manual_seed(20)
    env, term = _row_pair(counter=counter)
    _perturb_row(term)
    return collect(env, it=3), env, term


def test_row_sir_roundtrip_and_field_set() -> None:
    state, env1, term1 = _row_payload()
    slot = state["terms"][ROW_TERM]
    assert slot["adapter"] == "row_sir" and slot["adapter_version"] == 1
    assert slot["term_type"].endswith(".SpawnWeightSIRTerrainCurriculum")
    assert set(slot["runtime"]) == {
        "particles", "weights", "episodes", "successes", "history", "env_type", "next_eval_step"
    }
    assert set(slot["static"]) == {
        "types", "num_types", "num_rows", "type_cols", "terrain_config_sha256", "cfg"
    }
    assert sorted(slot["static"]["cfg"]) == sorted(ROW_CFG_KEYS)
    assert state["clock"]["ck"]["static"] == {"c0": 0.2, "decay": 0.98, "steps_per_iteration": 24}
    assert state["task"] == "_TaskCfgV14" and state["num_envs"] == ROW_ENVS

    # S01: collect hands out copies -- a later update of the live term must not rewrite it
    snapshot = slot["runtime"]["weights"][0].clone()
    term1._weights[0] *= 2.0
    assert torch.equal(slot["runtime"]["weights"][0], snapshot)
    term1._weights[0] /= 2.0

    env2, term2 = _row_pair(counter=0)
    out = apply_state(env2, state, report=lambda *_: None)
    assert out["evidence"] == "complete" and out["c_k"] == {"restored": True, "schedule": "matched"}
    assert [term["name"] for term in out["terms"]] == [ROW_TERM]
    assert env2.common_step_counter == 120 and ck_value(env2) == ck_value(env1)
    for key in ("particles", "weights", "episodes", "successes", "history"):
        assert _tensor_eq(getattr(term2, "_" + key), getattr(term1, "_" + key)), key
    assert torch.equal(term2._env_type, term1._env_type)
    assert term2._next_eval_step == term1._next_eval_step == 240
    assert not hasattr(term2, "_env_pair")  # joint-only field: never fabricated into a row slot


def test_row_sir_type_order_and_terrain_changes_rejected() -> None:
    torch.manual_seed(21)
    props = (0.3, 0.3, 0.4)
    env1, term1 = _row_pair(_row_grid(("t0", "t1", "t2"), props), counter=120)
    _perturb_row(term1)
    state = collect(env1)

    # the same proportions and the same column split: only the two type NAMES moved
    swapped = _row_grid(("t1", "t0", "t2"), props)
    env2, term2 = _row_pair(swapped, counter=0)
    assert all(torch.equal(a, b) for a, b in zip(term1._type_cols, term2._type_cols))
    try:
        apply_state(env2, state, report=lambda *_: None)
    except ValueError as exc:
        assert "terrain_config_sha256" in str(exc) or "types" in str(exc), str(exc)
    else:
        raise AssertionError("reordering two equal-proportion types must abort")

    # the same names and proportions, one difficulty parameter moved
    retuned = _row_grid(("t0", "t1", "t2"), (0.2, 0.3, 0.5))
    retuned.cfg.terrain_generator.sub_terrains["t1"].noise_amp = (0.2, 0.3)
    env3, term3 = _row_pair(retuned, counter=0)
    try:
        apply_state(env3, state, report=lambda *_: None)
    except ValueError as exc:
        assert "terrain_config_sha256" in str(exc), str(exc)
    else:
        raise AssertionError("a retuned terrain parameter must abort")

    # a different grid: rows are the particles, so num_rows has to bind too
    env4, term4 = _row_pair(_row_grid(("t0", "t1", "t2"), (0.2, 0.3, 0.5), rows=8), counter=0)
    try:
        apply_state(env4, state, report=lambda *_: None)
    except ValueError as exc:
        assert "num_rows" in str(exc) or "static" in str(exc), str(exc)
    else:
        raise AssertionError("a changed row count must abort")


def test_row_sir_cfg_entries_each_rejected() -> None:
    for key in ROW_CFG_KEYS:
        state, env1, term1 = _row_payload()
        env2, term2 = _row_pair(counter=0)
        setattr(term2.cfg, key, ROW_CFG_OTHER[key])
        try:
            apply_state(env2, state, report=lambda *_: None)
        except ValueError as exc:
            assert f"static.cfg.{key}" in str(exc) or "next_eval_step" in str(exc), f"{key}: {exc}"
        else:
            raise AssertionError(f"a changed cfg.{key} must abort")
        assert env2.common_step_counter == 0


def test_c_k_only_roundtrip() -> None:
    env1 = _ck_only_env(counter=288)
    state = collect(env1, it=2)
    assert state is not None and state["terms"] == {}  # empty terms = no covered term, legal
    assert state["clock"]["ck"]["static"] == {"c0": 0.2, "decay": 0.98, "steps_per_iteration": 24}

    env2 = _ck_only_env(counter=0)
    out = apply_state(env2, state, report=lambda *_: None)
    assert out["terms"] == [] and out["evidence"] == "complete"
    assert out["c_k"] == {"restored": True, "schedule": "matched"}
    assert env2.common_step_counter == 288
    assert ck_value(env2) == ck_value(env1)  # the c_k clock continues, not re-heats


def test_c_k_schedule_evidence_per_parameter() -> None:
    state, env1, term1 = _row_payload()
    for key, other in (("c0", 0.3), ("decay", 0.97), ("steps_per_iteration", 12)):
        env2, term2 = _row_pair(counter=0)
        env2._lizard_ck_params = {**CK, key: other}
        try:
            apply_state(env2, state, report=lambda *_: None)
        except ValueError as exc:
            assert f"clock.ck.static.{key}" in str(exc), str(exc)
        else:
            raise AssertionError(f"the same counter under another {key} is a different c_k")
        assert env2.common_step_counter == 0

    # c_k existence, both directions: a schedule that vanished, and one that appeared
    env3, term3 = _row_pair(counter=0)
    del env3._lizard_ck_params
    try:
        apply_state(env3, state, report=lambda *_: None)
    except ValueError as exc:
        assert "wires no init_ck" in str(exc), str(exc)
    else:
        raise AssertionError("a checkpoint schedule on a task without one must abort")

    del env1._lizard_ck_params
    stateless_c_k = collect(env1)  # the same task, now running no schedule
    assert stateless_c_k["clock"]["ck"] is None
    env5, term5 = _row_pair(counter=0)  # a task WITH the schedule, resumed from the above
    try:
        apply_state(env5, stateless_c_k, report=lambda *_: None)
    except ValueError as exc:
        assert "records none" in str(exc), str(exc)
    else:
        raise AssertionError("the counter alone is not evidence; an absent fingerprint must abort")

    # both sides explicitly schedule-less: legal, and the counter still continues
    env4 = _ck_only_env(counter=0, ck=False)
    out = apply_state(env4, stateless_c_k, report=lambda *_: None)
    assert out["c_k"] == {"restored": True, "schedule": "none"}
    assert env4.common_step_counter == 120


def test_corrupt_row_sir_payload_rejected() -> None:
    cases = {
        "nan weight": lambda s: s["terms"][ROW_TERM]["runtime"]["weights"][0].__setitem__(0, float("nan")),
        "inf episode": lambda s: s["terms"][ROW_TERM]["runtime"]["episodes"][0].__setitem__(0, float("inf")),
        "negative weight": lambda s: s["terms"][ROW_TERM]["runtime"]["weights"][0].__setitem__(0, -0.5),
        "weights not normalized": lambda s: s["terms"][ROW_TERM]["runtime"]["weights"][0].mul_(0.5),
        "negative successes": lambda s: s["terms"][ROW_TERM]["runtime"]["successes"][0].__setitem__(0, -1.0),
        "successes above episodes": lambda s: s["terms"][ROW_TERM]["runtime"]["successes"][0].__setitem__(0, 5.0),
        "particle out of range": lambda s: s["terms"][ROW_TERM]["runtime"]["particles"][0].__setitem__(0, 99),
        "float particles": lambda s: s["terms"][ROW_TERM]["runtime"].__setitem__(
            "particles", [s["terms"][ROW_TERM]["runtime"]["particles"][0].float()]
        ),
        "history index out of range": lambda s: s["terms"][ROW_TERM]["runtime"]["history"][0].__setitem__(0, 99),
        "history too short": lambda s: s["terms"][ROW_TERM]["runtime"].__setitem__(
            "history", [torch.zeros(2, dtype=torch.long)]
        ),
        "env_type out of range": lambda s: s["terms"][ROW_TERM]["runtime"]["env_type"].__setitem__(0, 99),
        "env_type wrong length": lambda s: s["terms"][ROW_TERM]["runtime"].__setitem__(
            "env_type", torch.zeros(2, dtype=torch.long)
        ),
        "unknown container version": lambda s: s.__setitem__("version", 99),
        "missing clock": lambda s: s.pop("clock"),
        "missing slot": lambda s: s.__setitem__("terms", {}),
        "extra slot": lambda s: s["terms"].__setitem__("ghost", dict(s["terms"][ROW_TERM])),
    }
    for label, mutate in cases.items():
        state, _env1, _term1 = _row_payload()
        mutate(state)
        env2, term2 = _row_pair(counter=0)
        before = [t.clone() for t in term2._weights]
        counter_before = env2.common_step_counter
        try:
            apply_state(env2, state, report=lambda *_: None)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{label}: must be rejected")
        # S06: nothing is written before every slot has passed
        assert all(torch.equal(a, b) for a, b in zip(term2._weights, before)), label
        assert env2.common_step_counter == counter_before, label


def test_hard_fail_boundaries() -> None:
    state, env1, term1 = _row_payload()

    # a renamed term is a mismatch, not a correspondence to guess
    renamed = {"version": state["version"], **{k: v for k, v in state.items() if k != "terms"}}
    renamed["terms"] = {"terrain_levels_new": state["terms"][ROW_TERM]}
    env2, term2 = _row_pair(counter=0)
    try:
        apply_state(env2, renamed, report=lambda *_: None)
    except ValueError as exc:
        assert "renamed term" in str(exc), str(exc)
    else:
        raise AssertionError("a renamed term must need an explicit migration")

    # two terms of one registered class: no silent key overwrite, no arbitrary pick
    env3, term3 = _row_pair(counter=0)
    env3.curriculum_manager.cfg.__dict__["second_row_sir"] = SimpleNamespace(func=term3)
    try:
        collect(env3)
    except RuntimeError as exc:
        assert "one instance per term class" in str(exc), str(exc)
    else:
        raise AssertionError("two instances of one registered class must be refused")

    # a registered class wired as the CLASS (not an instance) is not "no term"
    from rl_exp.tasks.teacher_mdp import SpawnWeightSIRTerrainCurriculum

    env4 = _ck_only_env()
    env4.curriculum_manager = SimpleNamespace(
        cfg=SimpleNamespace(terrain_levels=SimpleNamespace(func=SpawnWeightSIRTerrainCurriculum))
    )
    try:
        collect(env4)
    except RuntimeError as exc:
        assert "not an instance" in str(exc), str(exc)
    else:
        raise AssertionError("a class wired instead of an instance must abort")

    # a declared task that wires no term at all still requires continuity
    plain = _row_pair(counter=0, cfg_cls=_TaskCfgV14Plain)[0]
    assert not hasattr(type(plain.cfg), REQUIRES_CURRICULUM_STATE)


def test_v1_payload_migrates_with_its_missing_evidence() -> None:
    torch.manual_seed(23)
    env1, term1 = _pair(_terrain())
    env1, term1 = _drive(env1, term1)
    v2 = collect(env1, it=7)
    slot = v2["terms"][JOINT_SIR_TERM]
    v1 = {
        "version": 1,
        "written_at_iter": 4,
        "task": "_TaskCfgV12",
        "num_envs": NUM_ENVS,
        "common_step_counter": v2["clock"]["common_step_counter"],
        "static": {k: v for k, v in slot["static"].items() if k != "terrain_config_sha256"},
        "runtime": slot["runtime"],
    }
    env2, term2 = _pair(_terrain())
    reports: list[str] = []
    out = apply_state(env2, v1, report=reports.append)
    assert out["source_version"] == 1 and out["payload_version"] == 2
    assert out["evidence"] == "partial"  # readable, deliberately not declared complete
    assert out["missing_evidence"] == ["clock.ck", "terms.joint_sir.static.terrain_config_sha256"]
    assert out["c_k"] == {"restored": True, "schedule": "unverified"}
    assert env2.common_step_counter == v2["clock"]["common_step_counter"]
    # the live parameters are NOT written into the migrated payload: no manufactured evidence
    assert any("missing evidence: clock.ck" in r for r in reports)
    assert any("v1 payload" in r for r in reports)


def test_drop_alias_and_conflict() -> None:
    torch.manual_seed(24)
    env1, term1 = _pair(_terrain())
    env1, term1 = _drive(env1, term1)
    state = collect(env1)
    env2, term2 = _pair(_terrain())
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_ckpt(pathlib.Path(tmp) / "model_9.pt", state=state, it=9)
        try:
            apply_resume_state(env2, path, drop_curriculum_state=True, weights_only=False)
        except ValueError as exc:
            assert "conflicts" in str(exc), str(exc)
        else:
            raise AssertionError("contradicting the deprecated alias must be an error")
        assert env2.common_step_counter == 0
        reports: list[str] = []
        out = apply_resume_state(env2, path, weights_only=True, report=reports.append)
        assert out["status"] == "dropped" and out["evidence"] == "none"
        assert any("DEPRECATED" in r for r in reports)
        assert env2.common_step_counter == 0  # explicit drop = cold curriculum


def test_declaration_is_checked_against_wiring_and_each_save() -> None:
    """A promise that cannot be honoured stops the run, and a checkpoint that would lie stops too.

    Three findings the earlier guards could not reach: the promise may hold on the class while the
    wiring is empty (the save guard's conjunction then reads "no promise"), a term may be wired
    with no adapter (its state would cold-start), and a payload may carry only the clock while the
    config asks for terms -- emptiness is not the question, coverage is.
    """
    torch.manual_seed(31)
    env, term = _row_pair(counter=0)
    assert declares(env) and verify_declaration(env) == []
    assert expected_terms(env) == [ROW_TERM] and wired_terms(env).keys() == {ROW_TERM}

    # 1. declared, but the config asks for nothing: the promise and the recipe disagree
    unwired = _row_pair(counter=0)[0]
    unwired.curriculum_manager = SimpleNamespace(cfg=SimpleNamespace(**{ROW_TERM: None}))
    problems = verify_declaration(unwired)
    assert problems and "wires no curriculum at all" in problems[0], problems
    assert not verify_declaration(_row_pair(counter=0, cfg_cls=_TaskCfgV14Plain)[0])

    class _Runner:
        is_distributed = False
        gpu_global_rank = 0
        current_learning_iteration = 3

        def save(self, path, infos=None, *args, **kwargs):
            return "saved"

    try:
        hook_runner_save(_Runner(), unwired, report=lambda _line: None)
        raise AssertionError("a declared task whose wiring cannot honour it must not start")
    except RuntimeError as err:
        assert "cannot honour it" in str(err)

    # 2. declared, but a wired stateful term has no adapter: it could never be snapshotted
    uncovered = _row_pair(counter=0)[0]
    fake = object.__new__(type("_FakeStatefulTerm", (ManagerTermBase,), {}))
    uncovered.curriculum_manager.cfg.speed_curriculum = SimpleNamespace(func=fake)
    assert any("no registered adapter" in problem for problem in verify_declaration(uncovered))

    # 3. a payload that carries only the clock is not a curriculum state for this task
    runner = _Runner()
    hook_runner_save(runner, env, report=lambda _line: None)
    # the declarative side keeps asking for the term (it is the env cfg, as on a real env) while
    # the manager's wiring is cleared after the startup check: exactly the mid-run change the
    # older "collect came back empty" branch cannot see, because the clock makes the payload real
    env.cfg.curriculum = SimpleNamespace(**{ROW_TERM: SimpleNamespace(func=term)})
    env.curriculum_manager.cfg.__dict__[ROW_TERM] = None
    payload = collect(env, it=3)
    assert payload is not None and payload["terms"] == {}  # the clock alone: not None, not enough
    assert expected_terms(env) == [ROW_TERM]
    try:
        runner.save("model_3.pt")
        raise AssertionError("a checkpoint without the state its task promises must not be written")
    except RuntimeError as err:
        assert "un-resumable" in str(err)

    # the falsifier: with the declaration read removed, that same save goes through -- so the
    # finding above is the new rule, not the older empty-payload branch
    import rl_exp.tasks.curriculum_state as cstate

    try:
        cstate.declares = lambda _env: False
        runner2 = _Runner()
        hook_runner_save(runner2, env, report=lambda _line: None)
        assert runner2.save("model_3b.pt") == "saved"
    finally:
        cstate.declares = declares


def test_declaration_is_class_level_and_off_in_play() -> None:
    assert getattr(LizardRoughTeacherEnvCfg_V5, REQUIRES_CURRICULUM_STATE) is True
    assert getattr(LizardRoughTeacherEnvCfg_V14, REQUIRES_CURRICULUM_STATE) is True  # inherited
    assert getattr(LizardRoughTeacherEnvCfg_V13_PLAY, REQUIRES_CURRICULUM_STATE) is False
    assert not hasattr(LizardRoughTeacherEnvCfg_V4, REQUIRES_CURRICULUM_STATE)  # v4 has no SIR term

    # not config data: the cfg snapshot (the recipe golden and every run manifest's
    # cfg digest) excludes ClassVars, so changing the declaration cannot look like
    # changing the configuration. Upstream's to_dict walks the instance namespace and
    # still carries it -- that dump is a per-run artifact, not a comparison surface.
    cfg = LizardRoughTeacherEnvCfg_V5()
    assert REQUIRES_CURRICULUM_STATE not in cs.snapshot(cfg)  # the golden/digest surface
    assert REQUIRES_CURRICULUM_STATE in cfg.to_dict()  # upstream dump: recorded, not compared


def test_non_zero_rank_neither_restores_nor_saves() -> None:
    state, env1, term1 = _row_payload()
    env2, term2 = _row_pair(counter=0)
    os.environ["RANK"] = "1"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_ckpt(pathlib.Path(tmp) / "model_9.pt", state=state, it=9)
            reports: list[str] = []
            out = apply_resume_state(env2, path, report=reports.append)
            assert out["status"] == "rank_skipped" and out["rank"] == 1
            assert env2.common_step_counter == 0
            assert any("multi-GPU resume is not covered" in r for r in reports)

            class _Runner:
                gpu_global_rank = 1
                is_distributed = True

                def save(self, path, infos=None, *args, **kwargs):
                    return None

            assert hook_runner_save(_Runner(), env1, report=reports.append) is False
            assert any("saves no curriculum state" in r for r in reports)
    finally:
        del os.environ["RANK"]


def test_fork_patch_call_site_contract() -> None:
    """S07's call-site half: the archived patches must carry the declaration gate.

    train.py itself needs a running Isaac Sim app, so the constraint is pinned on the
    archive instead: the ImportError branch reads the declaration off ``type(env_cfg)``
    (available without importing rl_exp) and only tolerates a missing module when the
    caller asked for a drop. Every refusal on this path leaves through ``os._exit(2)``
    rather than a raise -- by then the sim app is already up, its teardown runs on the way
    out and rewrites the exit code to 0 (measured 2026-09-17), so a raise would be a
    boundary nobody outside the process can see.
    """
    patch = (_REPO / "rl_exp" / "fork_patches" / "train_curriculum_resume.patch").read_text(encoding="utf-8")
    assert "drop_curriculum_state" in patch and "--weights_only" in patch
    assert "REQUIRES_CURRICULUM_STATE" in patch and "__requires_curriculum_state__" not in patch
    assert "except ImportError as exc:" in patch
    assert "[FATAL]" in patch and "os._exit(2)" in patch
    assert "raise RuntimeError(" not in patch, "no refusal on this path may be a bare raise"
    assert "installed = hook_runner_save(runner, env)" in patch and "if not installed:" in patch
    assert "drop_curriculum_state=drop_curriculum_state" in patch


def test_b_layer_update_equivalence() -> None:
    """1.4a B layer: same statistics + a reset RNG => the same real curriculum update."""
    # n_traj_min is 6, so the first case is a settled measurement update (p_hat 0.7 is in
    # band) and the second keeps the prior weight -- the branch split is the point here;
    # the per-branch fixtures live in the *_branch_equivalence tests below
    for label, episodes, successes in (("measured update", 10.0, 7.0), ("below n_traj_min", 0.5, 0.2)):
        state, env1, term1 = _row_payload()
        env2, term2 = _row_pair(counter=0)
        apply_state(env2, state, report=lambda *_: None)
        for term in (term1, term2):
            for t in range(term._num_types):
                term._weights[t] = torch.full((term._num_rows,), 1.0 / term._num_rows)
                term._episodes[t] = torch.full((term._num_rows,), episodes)
                term._successes[t] = torch.full((term._num_rows,), successes)
                term._history[t] = torch.arange(term._num_rows, dtype=torch.long)
        torch.manual_seed(7)
        term1._resample()
        torch.manual_seed(7)
        term2._resample()
        for key in ("particles", "weights", "episodes", "successes", "history"):
            assert _tensor_eq(getattr(term1, "_" + key), getattr(term2, "_" + key)), f"{label}: {key}"
        assert term1._next_eval_step == term2._next_eval_step, label

    # the same for the joint SIR, driven by the real Eq. 2/3 statistics
    torch.manual_seed(25)
    env3, term3 = _pair(_terrain())
    env3, term3 = _drive(env3, term3)
    state = collect(env3)
    env4, term4 = _pair(_terrain())
    apply_state(env4, state, report=lambda *_: None)
    torch.manual_seed(8)
    term3._resample_all()
    torch.manual_seed(8)
    term4._resample_all()
    for key in ("particles", "estimate", "episodes", "in_band", "history"):
        assert _tensor_eq(getattr(term3, "_" + key), getattr(term4, "_" + key)), key
    assert term3._next_eval_step == term4._next_eval_step


def _spy(obj, name: str) -> list:
    """Count the calls of a method (evidence that a fixture hit the branch it claims)."""
    real = getattr(obj, name)
    calls: list = []

    def wrapper(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    setattr(obj, name, wrapper)
    return calls


def _b_update(env, term, block: int, seed: int):
    """Drive the REAL production update at the block edge under a fixed test RNG."""
    env.common_step_counter = block
    torch.manual_seed(seed)
    return term(env, torch.arange(int(env.num_envs)))


def test_b_layer_row_sir_branch_equivalence() -> None:
    """1.4a B layer, row SIR: every update branch, original vs restored, bitwise.

    Each fixture sets the pre-state that SELECTS a branch and then asserts that branch's
    signature, so a fixture that stops reaching its branch fails instead of passing
    vacuously. The pre-state is collected, restored into a cold term, and both terms are
    driven through the production entry point (``term(env, ids)`` at the block edge) --
    which also covers the throttle (``next_eval_step``) and the respawn of the resetting
    envs, not just the resample.
    """
    def flags(term, **spec):
        term.cfg.p_transition = spec["p_transition"]
        term.cfg.p_replay = spec["p_replay"]

    def prior(term, row: int):
        for t in range(term._num_types):
            term._weights[t] = torch.zeros(term._num_rows).scatter_(0, torch.tensor([row]), 1.0)

    def measured(term):
        """Settled rows, only row 0 in band: the measurement replaces the prior."""
        for t in range(term._num_types):
            term._episodes[t] = torch.full((term._num_rows,), 10.0)
            term._successes[t] = torch.zeros(term._num_rows)
            term._successes[t][0] = 7.0
            term._weights[t] = torch.full((term._num_rows,), 1.0 / term._num_rows)

    def sparse(term):
        """Every row below n_traj_min: the prior weight must survive."""
        for t in range(term._num_types):
            term._episodes[t] = torch.full((term._num_rows,), 3.0)
            term._successes[t] = torch.full((term._num_rows,), 1.0)
        prior(term, 5)

    def all_out_of_band(term):
        """Every row settled and nothing in band: the whole type re-explores uniformly."""
        for t in range(term._num_types):
            term._episodes[t] = torch.full((term._num_rows,), 10.0)
            term._successes[t] = torch.zeros(term._num_rows)
        prior(term, 3)

    def walkable(term):
        sparse(term)
        prior(term, 3)

    def replayable(term):
        sparse(term)
        for t in range(term._num_types):
            term._history[t] = torch.tensor([7, 8]).repeat(5)

    def expect_measured(term, _calls):
        for t in range(term._num_types):
            assert float(term._weights[t][0]) == 1.0, "the measurement must replace the prior"
            assert bool((term._particles[t] == 0).all())
            assert float(term._episodes[t].abs().max()) == 0.0  # consumed: stats zeroed
            assert float(term._successes[t].abs().max()) == 0.0

    def expect_sparse(term, _calls):
        for t in range(term._num_types):
            assert float(term._weights[t][5]) == 1.0, "below n_traj_min the prior weight survives"
            assert bool((term._particles[t] == 5).all())
            assert float(term._episodes[t].abs().max()) == 0.0  # row SIR zeroes every block

    def expect_flat(term, _calls):
        for t in range(term._num_types):
            want = torch.full((term._num_rows,), 1.0 / term._num_rows)
            assert torch.allclose(term._weights[t], want), "an all-out-of-band type re-explores uniformly"

    def expect_walk(term, _calls):
        for t in range(term._num_types):
            assert set(term._particles[t].tolist()) <= {2, 4}, "p_transition=1 must walk off row 3"

    def expect_replay(term, _calls):
        for t in range(term._num_types):
            assert set(term._particles[t].tolist()) <= {7, 8}, "p_replay=1 must redraw from the pool"

    cases = (
        ("measured update", dict(p_transition=0.0, p_replay=0.0), measured, expect_measured),
        ("below n_traj_min", dict(p_transition=0.0, p_replay=0.0), sparse, expect_sparse),
        ("band-empty fallback", dict(p_transition=0.0, p_replay=0.0), all_out_of_band, expect_flat),
        ("random walk", dict(p_transition=1.0, p_replay=0.0), walkable, expect_walk),
        ("replay", dict(p_transition=0.0, p_replay=1.0), replayable, expect_replay),
    )
    for label, spec, setup, expect in cases:
        env1, term1 = _row_pair(counter=120)
        flags(term1, **spec)  # set before collect: the cfg is part of the fingerprint
        setup(term1)
        state = collect(env1, it=1)
        env2, term2 = _row_pair(counter=0)
        flags(term2, **spec)  # same flags, so the restored state still fits
        saved = state["terms"][ROW_TERM]["runtime"]
        cold = adapter_for(type(term2)).runtime(term2, env2)
        # negative control: cold != payload, so a no-op restore fails this test
        assert any(not _tensor_eq(saved[k], cold[k]) for k in cold), label
        apply_state(env2, state, report=lambda *_: None)

        assert _tensor_eq(_b_update(env1, term1, 240, ROW_SEED), _b_update(env2, term2, 240, ROW_SEED)), label
        for key in ("particles", "weights", "episodes", "successes", "history"):
            assert _tensor_eq(getattr(term1, "_" + key), getattr(term2, "_" + key)), f"{label}: {key}"
        assert term1._next_eval_step == term2._next_eval_step == 480, label
        assert _tensor_eq(term1._env_type, term2._env_type), label
        for attr in ("terrain_levels", "terrain_types", "env_origins"):
            assert _tensor_eq(getattr(env1.scene.terrain, attr), getattr(env2.scene.terrain, attr)), f"{label}: {attr}"
        expect(term1, [])
        expect(term2, [])


def test_b_layer_joint_sir_branch_equivalence() -> None:
    """1.4a B layer, joint SIR: every update branch, original vs restored, bitwise.

    Same shape as the row-SIR test. ``_fallback_weights`` and ``_walk`` are counted on the
    source term: the branch fixtures are one-hot priors (or all-settled counters), so the
    way the particles can leave that prior IS the branch under test. Branch *semantics*
    (which neighbor, which clamp) are pinned by ``test_joint_sir.py``; here the claim is
    that the restored term reaches the same branch with the same result.
    """
    def flags(term, **spec):
        term.cfg.p_transition = spec["p_transition"]
        term.cfg.p_replay = spec["p_replay"]

    def fill(term, *, episodes, in_band=0.0):
        for ti in range(len(term._types)):
            n = term._n_pairs[ti]
            term._episodes[ti] = torch.full((n,), float(episodes))
            term._in_band[ti] = torch.full((n,), float(in_band))

    def mid(term, ti: int) -> int:
        """A pair with room to move on at least one axis (velocity or a param axis)."""
        return term._n_pairs[ti] // 2

    def prior(term):
        """Point the sampling source at the mid pair (the joint term samples from its
        raw ``_estimate`` since the 2026-09-16 fixes, not from a weight vector)."""
        for ti in range(len(term._types)):
            term._estimate[ti] = torch.zeros(term._n_pairs[ti]).scatter_(0, torch.tensor([mid(term, ti)]), 1.0)

    def measured(term):
        """Every pair settled, pair 0 carrying all the in-band trajectories."""
        fill(term, episodes=10.0)
        for ti in range(len(term._types)):
            term._in_band[ti][0] = 10.0

    def sparse(term):
        fill(term, episodes=3.0, in_band=1.0)
        prior(term)

    def frontier(term):
        """Every pair settled; combo 0 in band (estimate 1.0), the rest drained (0.0)."""
        fill(term, episodes=10.0)
        for ti in range(len(term._types)):
            term._in_band[ti][: term._n_v] = 10.0

    def walkable(term):
        sparse(term)

    def replayable(term):
        sparse(term)
        for ti in range(len(term._types)):
            term._history[ti] = torch.tensor([1, 2]).repeat(2)

    def expect_measured(term, _calls):
        for ti in range(len(term._types)):
            assert float(term._estimate[ti][0]) == 1.0
            assert bool((term._particles[ti] == 0).all())
            assert float(term._episodes[ti].abs().max()) == 0.0  # settled pairs are consumed
            assert float(term._in_band[ti].abs().max()) == 0.0

    def expect_sparse(term, _calls):
        for ti in range(len(term._types)):
            assert float(term._estimate[ti][mid(term, ti)]) == 1.0
            assert bool((term._particles[ti] == mid(term, ti)).all())
            assert float(term._episodes[ti].min()) == 3.0, "unsettled pairs keep their counters across blocks"

    def expect_frontier(term, calls):
        """Band-empty but evidence-driven: only pairs that reached the band keep traffic."""
        assert calls, "the resample must be the branch that ran"
        for ti in range(len(term._types)):
            learned = term._estimate[ti] >= term.cfg.band[0]
            assert bool(learned.any())
            assert bool(learned[term._particles[ti]].all())

    def expect_walk(term, calls):
        assert calls, "the walk must be the branch that ran"
        moved = False
        for ti in range(len(term._types)):
            pair = mid(term, ti)
            assert set(term._particles[ti].tolist()) <= set(term._neighbors(ti, pair)) | {pair}
            moved = moved or set(term._particles[ti].tolist()) != {pair}
        assert moved, "p_transition=1 must move particles off the one-hot prior (clamping aside)"

    def expect_replay(term, _calls):
        for ti in range(len(term._types)):
            assert set(term._particles[ti].tolist()) <= {1, 2}, "p_replay=1 must redraw from the pool"

    cases = (
        ("measured update", dict(p_transition=0.0, p_replay=0.0), measured, expect_measured, ()),
        ("below n_traj_min", dict(p_transition=0.0, p_replay=0.0), sparse, expect_sparse, ()),
        ("band-empty evidence resample", dict(p_transition=0.0, p_replay=0.0), frontier, expect_frontier,
         ("_support",)),
        ("random walk", dict(p_transition=1.0, p_replay=0.0), walkable, expect_walk, ("_walk",)),
        ("replay", dict(p_transition=0.0, p_replay=1.0), replayable, expect_replay, ()),
    )
    for label, spec, setup, expect, spied in cases:
        env1, term1 = _pair(_terrain())
        flags(term1, **spec)
        setup(term1)
        src_calls = {name: _spy(term1, name) for name in spied}
        state = collect(env1, it=1)
        env2, term2 = _pair(_terrain())
        flags(term2, **spec)
        saved = state["terms"][JOINT_SIR_TERM]["runtime"]
        cold = adapter_for(type(term2)).runtime(term2, env2)
        assert any(not _tensor_eq(saved[k], cold[k]) for k in cold), label
        apply_state(env2, state, report=lambda *_: None)
        dst_calls = {name: _spy(term2, name) for name in spied}

        assert _tensor_eq(_b_update(env1, term1, 240, JOINT_SEED), _b_update(env2, term2, 240, JOINT_SEED)), label
        for key in ("particles", "estimate", "episodes", "in_band", "history", "env_pair"):
            assert _tensor_eq(getattr(term1, "_" + key), getattr(term2, "_" + key)), f"{label}: {key}"
        assert _tensor_eq(term1.desired_vel, term2.desired_vel), label
        assert term1._next_eval_step == term2._next_eval_step == 480, label
        assert term1._tr_block_count == term2._tr_block_count == 0, label
        assert term1._tr_block_sum == term2._tr_block_sum == 0.0, label
        for attr in ("terrain_levels", "terrain_types", "env_origins"):
            assert _tensor_eq(getattr(env1.scene.terrain, attr), getattr(env2.scene.terrain, attr)), f"{label}: {attr}"
        expect(term1, next(iter(src_calls.values())) if src_calls else [])
        expect(term2, next(iter(dst_calls.values())) if dst_calls else [])


def test_b_layer_c_k_boundary_equivalence() -> None:
    """1.4a B layer, c_k-only: the counter and the SAVED-parameter c_k at the block edges.

    A c_k-only task's whole state is the counter (c_k is a pure function of it), so the
    check is: the restored counter equals the source, and the c_k recomputed independently
    in float64 from the *payload's* schedule parameters agrees with the live value just
    before, at and just after an iteration boundary, |err| <= 1e-12.
    """
    steps = int(CK["steps_per_iteration"])
    source = _ck_only_env(counter=10 * steps + 3)
    state = collect(source, it=0)
    saved = state["clock"]["ck"]["static"]
    assert state["terms"] == {} and saved == {"c0": 0.2, "decay": 0.98, "steps_per_iteration": 24}

    restored = _ck_only_env(counter=0)
    apply_state(restored, state, report=lambda *_: None)
    assert restored.common_step_counter == 10 * steps + 3
    assert ck_value(restored) == ck_value(source)

    def reference(counter: int) -> float:
        """The same formula through an independent float64 path (no `**` on the same operands)."""
        return math.exp(math.log(saved["c0"]) * saved["decay"] ** (counter // saved["steps_per_iteration"]))

    seen = {}
    for counter in (steps - 1, steps, steps + 1, 10 * steps - 1, 10 * steps, 10 * steps + 1, 977):
        for env in (source, restored):
            env.common_step_counter = counter
        assert ck_value(source) == ck_value(restored), counter
        assert abs(ck_value(restored) - reference(counter)) <= 1e-12, counter
        seen[counter] = ck_value(restored)
    assert seen[steps - 1] != seen[steps], "the iteration boundary is where c_k steps"


def _main() -> None:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"[OK] {fn.__name__}")
    print(f"test_resume_state: {len(tests)} passed")


if __name__ == "__main__":
    _main()
