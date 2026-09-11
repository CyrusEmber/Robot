# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).

# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline test for the true-resume curriculum state (no sim, plain torch).

Round-trips the joint SIR + c_k clock through the checkpoint payload and pins
the policy gates that keep a resume honest:

* bitwise round-trip of every runtime tensor, ``common_step_counter`` and the
  derived ``c_k``; the cold term turns into the saved one
* the static fingerprint catches a yaml/terrain edit that renumbers particles
  while leaving counts like ``n_pairs`` intact (the silent-corruption case)
* task/env-count/schema mismatch, corrupt eval clock and inconsistent weights
  are rejected instead of restored
* policy: no joint SIR term -> passthrough; term + stateless checkpoint ->
  hard abort naming ``--weights_only``; ``--weights_only`` -> explicit drop
* ``hook_runner_save`` rides the checkpoint's ``infos`` slot, passes extra
  args through and leaves termless tasks untouched
* the per-env type draw mismatch warns and restores the saved assignment; an
  uncovered stateful curriculum term is called out

NOTE: this proves the payload round-trip, NOT the wiring timing. That the
restore lands before the wrapper's first full reset (so the respawn consumes
the restored particles) is train.py behavior and only a smoke run proves it.
"""

import pathlib
import sys
import tempfile
from types import SimpleNamespace

import torch

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from isaaclab.managers import ManagerTermBase  # noqa: E402

from rl_exp.tasks.curriculum_state import (  # noqa: E402
    STATE_KEY,
    _other_stateful_terms,
    _static_state,
    _tensor_eq,
    apply_resume_state,
    apply_state,
    collect,
    hook_runner_save,
)
from rl_exp.tasks.param_grid_terrain import build_param_grid_terrain_cfg  # noqa: E402
from rl_exp.tasks.teacher_mdp import JOINT_SIR_TERM, ck_value, init_ck  # noqa: E402
from test_joint_sir import (  # noqa: E402
    GRID,
    NUM_ENVS,
    _cmd as _sir_cmd,
    _env as _sir_env,
    _terrain,
    _term,
)

CK = dict(c0=0.2, decay=0.98, steps_per_iteration=24)
"""The v3 c_k schedule used by the tests (matches the v11 yaml section)."""


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


def test_roundtrip_bitwise_and_ck_continuity() -> None:
    torch.manual_seed(11)
    env1, term1 = _pair(_terrain())
    env1, term1 = _drive(env1, term1)
    state = collect(env1, it=5)
    assert state is not None and state["common_step_counter"] == 123
    assert state["written_at_iter"] == 5 and state["task"] == "_TaskCfgV12"
    assert state["num_envs"] == NUM_ENVS

    env2, term2 = _pair(_terrain())  # cold: cold-start particles, clock at 0
    assert env2.common_step_counter == 0
    reports: list[str] = []
    apply_state(env2, state, report=reports.append)

    for key in ("particles", "weights", "episodes", "in_band", "tr_sum", "history"):
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
    assert abs(float(term2._weights[0].sum()) - 1.0) < 1e-6
    assert not [r for r in reports if "WARN" in r]


def test_static_fingerprint_catches_grid_edit() -> None:
    """A terrain-grid edit shifts the column split while n_pairs stays put."""
    torch.manual_seed(3)
    env1, term1 = _pair(_terrain())
    state = collect(env1)

    cfg13 = build_param_grid_terrain_cfg({**GRID, "num_cols": 13})
    origins = torch.zeros(2, 13, 3)
    terrain13 = SimpleNamespace(
        cfg=SimpleNamespace(terrain_generator=SimpleNamespace(sub_terrains=cfg13.sub_terrains)),
        terrain_origins=origins,
        terrain_levels=torch.zeros(NUM_ENVS, dtype=torch.long),
        terrain_types=torch.tensor([0, 2, 7, 9, 11, 12], dtype=torch.long),
        env_origins=torch.zeros(NUM_ENVS, 3),
    )
    env2, term2 = _pair(terrain13)

    saved, now = state["static"], _static_state(term2)
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


def test_corrupt_clock_and_weights_rejected() -> None:
    torch.manual_seed(5)
    env1, term1 = _pair(_terrain())
    state = collect(env1)
    env2, term2 = _pair(_terrain())

    state["runtime"]["next_eval_step"] = 240
    state["common_step_counter"] = 500  # block edge is now in the past
    try:
        apply_state(env2, state, report=lambda *_: None)
    except ValueError as exc:
        assert "next_eval_step" in str(exc)
    else:
        raise AssertionError("an eval edge below the restored clock must abort")

    state["common_step_counter"] = 0
    state["runtime"]["weights"][0] = state["runtime"]["weights"][0] * 0.5
    try:
        apply_state(env2, state, report=lambda *_: None)
    except ValueError as exc:
        assert "weights" in str(exc)
    else:
        raise AssertionError("unnormalized weights must abort")


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
        assert apply_resume_state(env_play, path, report=reports.append) is False
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
            assert "--weights_only" in str(exc)
        else:
            raise AssertionError("a stateless checkpoint on a joint-SIR task must abort")
        assert env2.common_step_counter == 0 and torch.equal(term2._particles[0], cold)

        stated = _write_ckpt(pathlib.Path(tmp) / "model_10.pt", state=state, it=10)
        reports: list[str] = []
        assert apply_resume_state(env2, stated, weights_only=True, report=reports.append) is False
        assert any("--weights_only" in r and "dropped" in r for r in reports)
        assert env2.common_step_counter == 0 and torch.equal(term2._particles[0], cold)

        reports = []
        assert apply_resume_state(env2, stated, report=reports.append) is True
        assert env2.common_step_counter == 123
        assert torch.equal(term2._particles[0], state["runtime"]["particles"][0])
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
    assert _other_stateful_terms(env) == ["speed_curriculum"]

    with tempfile.TemporaryDirectory() as tmp:
        path = _write_ckpt(pathlib.Path(tmp) / "model_9.pt", state=collect(env))
        reports: list[str] = []
        apply_resume_state(env, path, report=reports.append)
    assert any("NOT covered by this module" in r for r in reports)


def _main() -> None:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"[OK] {fn.__name__}")
    print(f"test_resume_state: {len(tests)} passed")


if __name__ == "__main__":
    _main()
