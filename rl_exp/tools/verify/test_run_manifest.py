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
import os
import pathlib
import shutil
import sys
import tempfile
import types

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")

import torch  # noqa: E402

from rl_exp.tools.runrecord import manifest as M  # noqa: E402
from rl_exp.tools.runrecord import provenance as prov  # noqa: E402
from rl_exp.tasks import curriculum_state as cstate  # noqa: E402
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


def _record(
    tmp: pathlib.Path,
    *,
    num_envs: int | None = None,
    freeze_it: bool = True,
    save_early: bool = False,
    runner_lr: float | None = None,
    resume_path: pathlib.Path | None = None,
    curriculum_resume: dict | None = None,
):
    """Run the four recording call sites against stubs, saving one checkpoint.

    ``runner_lr`` defaults to the recipe's own value, so the "declared == effective"
    case is the honest default and a mismatch has to be asked for explicitly.
    ``curriculum_resume`` stands in for the outcome ``apply_resume_state`` returns.
    """
    cfg = LizardRoughTeacherEnvCfg_V14()
    agent = LizardTeacherV14PPORunnerCfg()
    env = _StubEnv(cfg, num_envs)
    runner = _StubRunner(lr=agent.algorithm.learning_rate if runner_lr is None else runner_lr)
    ctx = M.begin(log_dir=tmp, task=TASK, argv=["train.py", "--task", TASK], env_cfg=cfg, agent_cfg=agent)
    M.hook_runner_save(runner, ctx)
    if save_early:
        runner.save(tmp / "model_0.pt")
    M.after_env(ctx, env)
    if freeze_it:
        M.freeze(
            ctx,
            runner=runner,
            env=env,
            agent_cfg=agent,
            resume_path=str(resume_path) if resume_path else None,
            drop_curriculum_state=False,
            curriculum_resume=curriculum_resume,
        )
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


def _clean_sources() -> dict:
    """A synthetic clean-tree provenance, so the test does not depend on the dev tree.

    Recording from the live tree would make every assertion here depend on whether the
    developer happens to have uncommitted work, which is exactly the situation the
    record is supposed to describe rather than inherit.
    """
    return {
        "repository": {"available": True, "rev": "aaaa1111", "dirty": False, "diff_sha256": "d", "untracked_in_code_root": []},
        "isaaclab": {"available": True, "rev": "bbbb2222", "dirty": False, "diff_sha256": "d", "untracked_in_code_root": []},
        "rsl_rl": {"available": True, "mode": "editable/source", "rev": "bbbb2222", "dirty": False, "diff_sha256": "d", "untracked_in_code_root": []},
    }


def main() -> int:
    root = pathlib.Path(tempfile.mkdtemp(prefix="runrecord_"))
    real_sources = prov.code_sources
    prov.code_sources = _clean_sources
    try:
        run_dir = root / "2026-09-15_14-00-00_v14"
        ctx, env, runner = _record(run_dir)

        manifest = json.loads((run_dir / M.MANIFEST_NAME).read_text(encoding="utf-8"))
        check("record/stages", all(s in manifest["stages"] for s in M.STAGES), f"{list(manifest['stages'])}")
        check("record/t1-frozen", ctx.frozen and bool(ctx.t1_sha256), "T1 not frozen")
        self_hash = prov.sha256_file(run_dir / M.MANIFEST_NAME)
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
            "record/resolved-models",
            manifest["stages"]["ready_to_learn"]["resolved_algorithm"].endswith("_StubAlg")
            and manifest["stages"]["ready_to_learn"]["resolved_models"].get("alg.policy", "").endswith("_StubPolicy"),
            f"{manifest['stages']['ready_to_learn']['resolved_models']}",
        )
        check(
            "record/effective-lr",
            manifest["stages"]["ready_to_learn"]["learning_rate"]["effective"]
            == LizardTeacherV14PPORunnerCfg().algorithm.learning_rate
            and manifest["stages"]["ready_to_learn"]["learning_rate"]["agrees"] is True,
            f"{manifest['stages']['ready_to_learn']['learning_rate']}",
        )
        check(
            "record/obs-dims",
            manifest["stages"]["ready_to_learn"]["obs_group_dims"] == {"proprio": [90], "extero": [208], "priv": [83]},
            f"{manifest['stages']['ready_to_learn']['obs_group_dims']}",
        )
        check(
            "record/curriculum-evidence",
            manifest["stages"]["ready_to_learn"]["resume"]["curriculum_module"].get("state_version")
            == cstate.STATE_VERSION
            and manifest["stages"]["ready_to_learn"]["resume"]["curriculum_state"]["status"] == "fresh_run",
            f"{manifest['stages']['ready_to_learn']['resume']}",
        )
        check(
            "record/distributed-flags",
            manifest["stages"]["ready_to_learn"]["distributed"]["multi_gpu_resume_verified"] is False,
            f"{manifest['stages']['ready_to_learn']['distributed']}",
        )
        saved = runner.saves[-1].get(M.CKPT_INFOS_KEY, {})
        check(
            "checkpoint/infos",
            saved.get("t1_sha256") == ctx.t1_sha256 and saved.get("status") == "ready_to_learn",
            f"{saved}",
        )
        index = json.loads((run_dir / M.INDEX_NAME).read_text(encoding="utf-8"))
        entry = next(v for k, v in index.items() if isinstance(v, dict))
        check("checkpoint/index-sha", entry["sha256"] == prov.sha256_file(next(run_dir.glob("*.pt"))), f"{entry}")

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

        # --- S10: what the restore actually did, per outcome ----------------------
        # The record carries apply_resume_state's own report; each shape has to land on
        # the right verdict -- and a *declared* task must not pass with a cold curriculum.
        ckpt = root / "model_9.pt"
        ckpt.write_bytes(b"not really a checkpoint")
        for label, outcome, want, blocking in (
            (
                "restored-complete",
                {"status": "restored", "source_version": 2, "evidence": "complete", "terms": [{"name": "terrain_levels"}],
                 "c_k": {"restored": True, "schedule": "matched"}, "common_step_counter": 28800, "rank": 0},
                "通过",
                False,
            ),
            (
                "restored-partial-v1",
                {"status": "restored", "source_version": 1, "evidence": "partial", "terms": [{"name": "joint_sir"}],
                 "missing_evidence": ["clock.ck", "terms.joint_sir.static.terrain_config_sha256"]},
                "未知",
                False,
            ),
            ("dropped", {"status": "dropped", "evidence": "none"}, "未知", False),
            ("module-unavailable", {"status": "module_unavailable", "error": "ImportError: boom"}, "未知", True),
        ):
            sub = pathlib.Path(tempfile.mkdtemp(dir=root))
            _record(sub / "run", resume_path=ckpt, curriculum_resume=outcome)
            sub_rows, sub_problems = M.verify(sub / "run")
            check(
                f"s10/{label}",
                _detail_result(sub_rows, "curriculum:") == want
                and (any("curriculum state required" in p for p in sub_problems) == blocking),
                f"{_detail_result(sub_rows, 'curriculum:')} problems={sub_problems}",
            )
            shutil.rmtree(sub)

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

        # A moved revision on a clean record is NOT a failure: the code is reachable at the
        # recorded revision, which is the point of recording it (verified by exit 0).
        moved = _tamper(
            run_dir, lambda d: d["code"]["repository"].__setitem__("rev", "deadbeef1234"), refresh_t1=True
        )
        moved_rows, moved_problems = M.verify(moved)
        check(
            "verify/rev-moved-is-reachable",
            M.main(["--verify", str(moved)]) == 0
            and not moved_problems
            and any("reachable at the recorded revision" in row["detail"] for row in moved_rows),
            f"{[r for r in moved_rows if r['level'] == '可重建']}",
        )
        shutil.rmtree(moved)

        # A baseline taken under another framework combination is NOT recipe drift: the
        # digest was never comparable, so the claim is unknown. Reporting it as drift would
        # send someone hunting a recipe change that never happened.
        other_combo = _tamper(
            run_dir,
            lambda d: d["declaration"]["recipe"].__setitem__(
                "golden_combination", "isaaclab=0000|rsl_rl=x|python=9.9"
            ),
            refresh_t1=True,
        )
        combo_rows, combo_problems = M.verify(other_combo)
        check(
            "verify/another-combination",
            any("another framework combination" in row["detail"] for row in combo_rows)
            and not combo_problems,
            f"{[r for r in combo_rows if r['level'] == '可重建']}",
        )
        shutil.rmtree(other_combo)

        # A run whose code included UNTRACKED source cannot be rebuilt from the record:
        # unknown on a required claim -> neither green nor a failure (hard constraint 1),
        # and it must name the archive gap it is a symptom of.
        dirty = _tamper(
            run_dir,
            lambda d: d["code"]["repository"].update(
                dirty=True,
                rev="deadbeef1234",
                diff_sha256="different",
                untracked_in_code_root=["rl_exp/tasks/new_thing.py"],
            ),
            refresh_t1=True,
        )
        dirty_rows, _ = M.verify(dirty)
        check(
            "verify/untracked-code-unrecoverable",
            M.main(["--verify", str(dirty)]) == 2
            and any("PLAN.md #18" in row["detail"] for row in dirty_rows)
            and not any(row["result"] == "失败" for row in dirty_rows),
            f"{[r for r in dirty_rows if r['level'] == '可重建']}",
        )
        shutil.rmtree(dirty)

        # a dirty tree whose diff no longer matches cannot be recreated either: the hash
        # proves it was different, it cannot bring the code back
        stale = _tamper(
            run_dir,
            lambda d: d["code"]["repository"].update(dirty=True, diff_sha256="different"),
            refresh_t1=True,
        )
        stale_rows, _ = M.verify(stale)
        check(
            "verify/dirty-diff-unrecoverable",
            M.main(["--verify", str(stale)]) == 2
            and any("that diff no longer matches" in row["detail"] for row in stale_rows),
            f"{[r for r in stale_rows if r['level'] == '可重建']}",
        )
        shutil.rmtree(stale)
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
        # --- a dirty project tree is refused at launch, not merely recorded -------
        # No revision restores a dirty tree, so the run's rebuildable claim could never be
        # proved -- learning that at launch beats learning it months later. The provenance
        # is injected so the case does not depend on whether the developer happens to have
        # uncommitted work.
        dirty_sources = json.loads(json.dumps(_clean_sources()))
        dirty_sources["repository"].update(dirty=True, diff_lines=17, untracked_count=2)
        prov.code_sources = lambda: dirty_sources
        dirty_dir = root / "2026-09-15_11-00-00_v14"
        dirty_dir.mkdir()
        cfg_dirty = LizardRoughTeacherEnvCfg_V14()
        agent_dirty = LizardTeacherV14PPORunnerCfg()
        saved_override = os.environ.pop(M.DIRTY_OVERRIDE_ENV, None)
        try:
            M.begin(log_dir=dirty_dir, task=TASK, argv=["train.py"], env_cfg=cfg_dirty, agent_cfg=agent_dirty)
            check("dirty/refused", False, "a dirty project tree was accepted without a stated reason")
        except RuntimeError as err:
            check("dirty/refused", M.DIRTY_OVERRIDE_ENV in str(err) and "dirty" in str(err), f"{err}")
        refused = json.loads((dirty_dir / M.MANIFEST_NAME).read_text(encoding="utf-8"))
        check(
            "dirty/refusal-is-recorded",
            any("refused" in failure for failure in refused.get("failures", [])),
            f"{refused.get('failures')}",
        )
        check(
            "dirty/refusal-wrote-t0",
            "pre_make" in refused.get("stages", {}),
            "the refusal left no evidence on disk",
        )
        check("dirty/refusal-verify-blocks", M.main(["--verify", str(dirty_dir)]) != 0, "a refused launch verified clean")

        os.environ[M.DIRTY_OVERRIDE_ENV] = "offline test: must run in whatever tree it finds"
        try:
            ctx_dirty = M.begin(
                log_dir=dirty_dir, task=TASK, argv=["train.py"], env_cfg=cfg_dirty, agent_cfg=agent_dirty
            )
            check(
                "dirty/override-records-its-reason",
                ctx_dirty.manifest["declaration"].get("dirty_tree_override_reason", "").startswith("offline test"),
                f"{ctx_dirty.manifest['declaration'].get('dirty_tree_override_reason')}",
            )
        finally:
            if saved_override is None:
                os.environ.pop(M.DIRTY_OVERRIDE_ENV, None)
            else:
                os.environ[M.DIRTY_OVERRIDE_ENV] = saved_override
        check(
            "dirty/clean-tree-needs-no-override",
            M.dirty_tree_refusal(types.SimpleNamespace(manifest={"code": _clean_sources()})) is None,
            "a clean tree was refused",
        )
        check(
            "dirty/only-the-project-tree-blocks",
            M.dirty_tree_refusal(
                types.SimpleNamespace(
                    manifest={
                        "code": {
                            **_clean_sources(),
                            "isaaclab": {**_clean_sources()["isaaclab"], "dirty": True},
                        }
                    }
                )
            )
            is None,
            "the IsaacLab tree (expected to carry uncommitted fork patches) blocked a launch",
        )
    finally:
        prov.code_sources = real_sources
        shutil.rmtree(root, ignore_errors=True)

    for problem in PROBLEMS:
        print(f"  {problem}")
    print("RUN_MANIFEST_TEST_OK" if not PROBLEMS else "RUN_MANIFEST_TEST_DRIFT")
    return 0 if not PROBLEMS else 1


if __name__ == "__main__":
    raise SystemExit(main())
