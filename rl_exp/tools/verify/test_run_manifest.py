# -*- coding: utf-8 -*-
"""Offline test for the run manifest (ARCH_PLAN 1.2).

No sim: the env and runner are stubs carrying only what the recorder reads (cfg,
num_envs, step_dt, obs group dims, state_dict, optimizer lr, iteration). What is
being tested is the *record* and the verification of it, not the trainer.

The negative cases matter more than the happy path here: the plan's whole point is
that a run must never look complete when it is not -- so a declared/actual mismatch,
a missing T1, a moved code revision, changed assets, a vanished checkpoint, and a
checkpoint written before T1 all have to be reported as blocking.
"""

import json
import pathlib
import shutil
import sys
import tempfile
import types

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")

import torch  # noqa: E402

from rl_exp.tools.runrecord import manifest as M  # noqa: E402
from rl_exp.tasks.agents.rsl_rl_ppo_cfg import LizardTeacherV14PPORunnerCfg  # noqa: E402
from rl_exp.tasks.teacher_env_cfg import LizardRoughTeacherEnvCfg_V14  # noqa: E402

PROBLEMS: list[str] = []
TASK = "Lizard-Rough-v14"


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


class _StubPolicy:
    def state_dict(self) -> dict:
        return {"w": torch.zeros(4), "b": torch.ones(2)}


class _StubAlg:
    def __init__(self, lr: float = 3e-4):
        self.policy = _StubPolicy()
        self.optimizer = types.SimpleNamespace(param_groups=[{"lr": lr}])


class _StubRunner:
    """Only the runner surface the recorder touches."""

    def __init__(self, lr: float = 3e-4, iteration: int = 42):
        self.alg = _StubAlg(lr)
        self.current_learning_iteration = iteration
        self.is_distributed = False
        self.saves: list[dict] = []

    def save(self, path, infos=None, *args, **kwargs):
        pathlib.Path(path).write_text(json.dumps({"infos": infos}, default=str), encoding="utf-8")
        self.saves.append(infos or {})
        return infos


class _StubEnv:
    def __init__(self, cfg, num_envs: int | None = None, step_dt: float | None = None):
        self.unwrapped = types.SimpleNamespace(
            cfg=cfg,
            num_envs=num_envs if num_envs is not None else cfg.scene.num_envs,
            step_dt=step_dt if step_dt is not None else cfg.sim.dt * cfg.decimation,
            common_step_counter=1234,
            observation_manager=types.SimpleNamespace(
                group_obs_dim={"proprio": (90,), "extero": (208,), "priv": (83,)}
            ),
        )


def _record(tmp: pathlib.Path, *, num_envs: int | None = None, freeze_it: bool = True, save_early: bool = False):
    """Run the four recording call sites against stubs, saving one checkpoint."""
    cfg = LizardRoughTeacherEnvCfg_V14()
    agent = LizardTeacherV14PPORunnerCfg()
    env = _StubEnv(cfg, num_envs)
    runner = _StubRunner()
    ctx = M.begin(log_dir=tmp, task=TASK, argv=["train.py", "--task", TASK], env_cfg=cfg, agent_cfg=agent)
    M.hook_runner_save(runner, ctx)
    if save_early:
        runner.save(tmp / "model_0.pt")
    M.after_env(ctx, env)
    if freeze_it:
        M.freeze(ctx, runner=runner, env=env, agent_cfg=agent, resume_path=None, weights_only=False)
    if not save_early:
        runner.save(tmp / "model_42.pt")
    return ctx, env, runner


def _tamper(tmp: pathlib.Path, mutate, refresh_t1: bool = False) -> pathlib.Path:
    """Copy the recorded run, mutate its manifest, return the copy.

    ``refresh_t1`` recomputes the T1 digest after the mutation, which is exactly what a
    careful forger would do -- the checks that catch it must not depend on a stale digest.
    """
    copy = tmp.with_name(tmp.name + "_tampered")
    if copy.exists():
        shutil.rmtree(copy)
    shutil.copytree(tmp, copy)
    path = copy / M.MANIFEST_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    if refresh_t1 and "t1_sha256" in data:
        data["t1_sha256"] = M.t1_digest(data)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return copy


def _result(rows: list[dict], level: str) -> str | None:
    return next((row["result"] for row in rows if row["level"] == level), None)


def _detail_result(rows: list[dict], prefix: str) -> str | None:
    return next((row["result"] for row in rows if row["detail"].startswith(prefix)), None)


def main() -> int:
    root = pathlib.Path(tempfile.mkdtemp(prefix="runrecord_"))
    try:
        run_dir = root / "2026-09-15_14-00-00_v14"
        ctx, env, runner = _record(run_dir)

        manifest = json.loads((run_dir / M.MANIFEST_NAME).read_text(encoding="utf-8"))
        check("record/stages", all(s in manifest["stages"] for s in M.STAGES), f"{list(manifest['stages'])}")
        check("record/t1-frozen", ctx.frozen and bool(ctx.t1_sha256), "T1 not frozen")
        self_hash = M._sha256_file(run_dir / M.MANIFEST_NAME)
        check(
            "record/no-self-hash",
            self_hash not in json.dumps(manifest),
            "the manifest hashes itself -- a digest of a file cannot live inside it",
        )
        check(
            "record/code-sources",
            all(k in manifest["code"] for k in ("repository", "isaaclab", "rsl_rl"))
            and manifest["code"]["repository"]["available"],
            f"{list(manifest['code'])}",
        )
        check("record/declaration", {"seed", "num_envs", "sim_dt", "control_dt", "assets"} <= set(manifest["declaration"]))
        check(
            "record/effective-lr",
            manifest["stages"]["ready_to_learn"]["effective_lr"] == 3e-4,
            f"{manifest['stages']['ready_to_learn']['effective_lr']}",
        )
        check(
            "record/obs-dims",
            manifest["stages"]["ready_to_learn"]["obs_group_dims"] == {"proprio": [90], "extero": [208], "priv": [83]},
            f"{manifest['stages']['ready_to_learn']['obs_group_dims']}",
        )
        check(
            "record/curriculum-evidence",
            manifest["stages"]["ready_to_learn"]["resume"]["curriculum_state"].get("state_version"),
            "state version not recorded",
        )
        saved = runner.saves[-1].get(M.CKPT_INFOS_KEY, {})
        check(
            "checkpoint/infos",
            saved.get("t1_sha256") == ctx.t1_sha256 and saved.get("status") == "ready_to_learn",
            f"{saved}",
        )
        index = json.loads((run_dir / M.INDEX_NAME).read_text(encoding="utf-8"))
        entry = next(v for k, v in index.items() if isinstance(v, dict))
        check("checkpoint/index-sha", entry["sha256"] == M._sha256_file(next(run_dir.glob("*.pt"))), f"{entry}")

        rows, problems = M.verify(run_dir)
        check("verify/clean", not problems, f"{problems[:2]}")
        check("verify/record-complete", _result(rows, "记录完整") == "通过", f"{rows[0]}")
        for prefix in ("assets:", "recipe:", "checkpoints:"):
            check(f"verify/{prefix[:-1]}", _detail_result(rows, prefix) == "通过", f"{_detail_result(rows, prefix)}")
        check(
            "verify/no-unexplained-failure",
            all(row["result"] != "失败" for row in rows),
            f"{[r for r in rows if r['result'] == '失败']}",
        )
        check("verify/rebuild-unknown", _result(rows, "已验证重建") == "未知", "1.5 not built yet, must not claim")
        check("verify/exit-code", M.main(["--verify", str(run_dir)]) == 0, "clean run must exit 0")

        # --- negatives -----------------------------------------------------------
        bad = _tamper(run_dir, lambda d: d["declaration"].__setitem__("num_envs", 1))
        check("negative/declaration-edited", M.main(["--verify", str(bad)]) == 1, "edited declaration not reported")
        shutil.rmtree(bad)

        # a forger who also refreshes the digest: only the recorded pairs can catch it
        bad = _tamper(
            run_dir,
            lambda d: d["stages"]["env_constructed"]["checked"].__setitem__("num_envs", [8, 64]),
            refresh_t1=True,
        )
        forged_rows, forged_problems = M.verify(bad)
        check(
            "negative/forged-pair",
            any("disagreement in the record" in row["detail"] for row in forged_rows) and bool(forged_problems),
            f"{[r for r in forged_rows if r['result'] == '失败']}",
        )
        shutil.rmtree(bad)

        bad = _tamper(run_dir, lambda d: d["stages"].pop("ready_to_learn"))
        check("negative/missing-t1", M.main(["--verify", str(bad)]) == 1, "missing T1 not reported")
        shutil.rmtree(bad)

        bad = _tamper(run_dir, lambda d: d["code"]["repository"].__setitem__("rev", "0" * 12))
        check("negative/code-moved", M.main(["--verify", str(bad)]) == 1, "moved revision not reported")
        shutil.rmtree(bad)

        bad = _tamper(run_dir, lambda d: d["declaration"]["assets"].__setitem__("manifest_sha256", "0" * 64))
        check("negative/assets-changed", M.main(["--verify", str(bad)]) == 1, "asset drift not reported")
        shutil.rmtree(bad)

        bad = _tamper(
            run_dir,
            lambda d: d["declaration"]["recipe"].__setitem__("recipe_digest", "0" * 64),
        )
        check("negative/recipe-changed", M.main(["--verify", str(bad)]) == 1, "recipe drift not reported")
        shutil.rmtree(bad)

        # a checkpoint written before T1 froze must not claim readiness
        early = root / "2026-09-15_13-00-00_v14"
        ctx_early, _, runner_early = _record(early, save_early=True)
        early_infos = runner_early.saves[-1].get(M.CKPT_INFOS_KEY, {})
        check(
            "negative/pre-t1-checkpoint",
            early_infos.get("status") == "incomplete" and early_infos.get("t1_sha256") is None,
            f"{early_infos}",
        )
        check("negative/pre-t1-verify", M.main(["--verify", str(early)]) == 1, "incomplete run passed verification")

        # a vanished checkpoint file must fail the payload check
        victim = next(run_dir.glob("*.pt"))
        backup = victim.read_bytes()
        victim.unlink()
        check("negative/checkpoint-gone", M.main(["--verify", str(run_dir)]) == 1, "missing checkpoint not reported")
        victim.write_bytes(backup)
        check("negative/checkpoint-restored", M.main(["--verify", str(run_dir)]) == 0, "restored checkpoint did not pass")

        # a stub env that disagrees with the declaration must be recorded as a failure
        mismatch_dir = root / "2026-09-15_12-00-00_v14"
        ctx_bad, _, _ = _record(mismatch_dir, num_envs=64)
        check("negative/env-mismatch-fails", ctx_bad.failures and "num_envs" in ctx_bad.failures[-1], f"{ctx_bad.failures}")
        check("negative/env-mismatch-verify", M.main(["--verify", str(mismatch_dir)]) == 1, "mismatch passed verification")

        check(
            "determinism/state-digest",
            M._state_digest(runner) == M._state_digest(runner),
            "state digest unstable",
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    for problem in PROBLEMS:
        print(f"  {problem}")
    print("RUN_MANIFEST_TEST_OK" if not PROBLEMS else "RUN_MANIFEST_TEST_DRIFT")
    return 0 if not PROBLEMS else 1


if __name__ == "__main__":
    raise SystemExit(main())
