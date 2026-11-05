# -*- coding: utf-8 -*-
"""Offline test for the isolation-rebuild gate (ARCH_PLAN 1.5).

The gate has one job -- never let a rebuild look possible when the material is not
retrievable -- so the negative cases carry this test: a dirty diff that has drifted, a
dirty diff with nowhere to live, untracked code that is gone, a payload that was edited,
and an original path that is still readable. All of it without a simulator.

The recorder's own stubs (``test_run_manifest._record``) build the run records, so what a
manifest contains stays decided in one place.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import types
from contextlib import ExitStack
from unittest.mock import patch

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")

import torch  # noqa: E402

from rl_exp.tools.runrecord import manifest as M  # noqa: E402
from rl_exp.tools.runrecord import provenance as prov  # noqa: E402
from rl_exp.tools.runrecord import rebuild as R  # noqa: E402
from test_run_manifest import _record, isolated_assets, Lizard2FlatV4EnvCfg, Lizard2V4PPORunnerCfg  # noqa: E402
from test_lifecycle_gate import active_index  # noqa: E402

# This gate exists to record dirty/untracked runs, so its synthetic runs have to be allowed
# to start from one -- the launch guard in run_manifest.begin is opted out here deliberately,
# stating a reason exactly as a human would have to.
os.environ.setdefault(M.DIRTY_OVERRIDE_ENV, "offline test: exercises dirty/untracked run records")

PROBLEMS: list[str] = []
TASK = "Lizard-Rough-v14"


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def _sources(diff: str, *, dirty: bool = True, untracked: tuple[str, ...] = ()) -> dict:
    """Synthetic provenance: the gate must not depend on the state of the dev tree."""
    common = {"available": True, "rev": "rev0001", "diff_sha256": prov.sha256_bytes(diff.encode("utf-8")), "diff_lines": len(diff.splitlines())}
    return {
        "repository": {**common, "dirty": dirty, "untracked_in_code_root": list(untracked)},
        "isaaclab": {**common, "dirty": False, "untracked_in_code_root": []},
        "rsl_rl": {**common, "mode": "editable/source", "dirty": False, "untracked_in_code_root": []},
    }


def _fake_trees(root: pathlib.Path) -> dict[str, pathlib.Path]:
    trees = {name: root / name for name in ("repository", "isaaclab", "rsl_rl")}
    for tree in trees.values():
        (tree / ".git").mkdir(parents=True, exist_ok=True)
    return trees


def _fake_git(live_diff: str):
    """Enough git for the gate: revisions exist, and the live diff is whatever we say.

    Everything else (including the revisions the framework combination is keyed by) goes
    to real git, so faking the diff does not silently move the golden's combination.
    """
    real = prov.git

    def git(tree, *args, **kwargs):
        if args[:1] == ("cat-file",) or args[:2] == ("rev-parse", "--verify"):
            return "present"
        if args[:2] == ("diff", "HEAD"):
            return live_diff
        return real(tree, *args, **kwargs)

    return git


def _real_ckpt(run_dir: pathlib.Path) -> str:
    """Turn the stub checkpoint into a loadable torch payload and re-index its hash."""
    index_path = run_dir / M.INDEX_NAME
    index = json.loads(index_path.read_text(encoding="utf-8"))
    name = sorted(entry for entry, value in index.items() if isinstance(value, dict))[-1]
    payload = {**index[name], "run_id": index.get("run_id")}
    torch.save({"infos": {M.CKPT_INFOS_KEY: payload}, "model_state_dict": {}}, run_dir / name)
    index[name]["sha256"] = prov.sha256_file(run_dir / name)
    index[name]["size"] = (run_dir / name).stat().st_size
    index_path.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return name


def _real_git_scope(root: pathlib.Path, cfg, agent) -> None:
    """Exercise T0 and rebuild against a real, isolated dirty work tree."""
    with isolated_assets(root) as repo, active_index(root), patch.object(prov, "_REPO", repo), patch.object(
        R, "_REPO", repo
    ), patch.object(R, "CODE_SOURCES", ("repository",)), ExitStack() as fixture_patches:
        def git(*args: str) -> None:
            subprocess.run(
                ["git", *args], cwd=repo, check=True, capture_output=True,
                env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
            )

        def put(path: str, content: str) -> None:
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        def clean() -> None:
            for path in tracked:
                put(path, "original\n")
            for path in ("new_notes.md", "ablation_harness/record.py", "notes/中文 配置.yaml", "configs/run.log.yaml"):
                (repo / path).unlink(missing_ok=True)

        def item(source: dict) -> tuple[dict, list[str]]:
            refusals: list[str] = []
            result = R._code_item("repository", source, None, "scope", root / "stage", {}, refusals)
            return result, refusals

        def record(name: str, reason: str = "", *, freeze_it: bool = True) -> tuple[pathlib.Path, dict, bool]:
            run = root / name
            with (patch.dict(os.environ, {M.DIRTY_OVERRIDE_ENV: reason}),
                  patch.object(prov, "code_sources", code_sources),
                  patch.object(lifecycle, "read_index", return_value=index),
                  patch.object(M, "recipe_ref", return_value=recipe),
                  patch.object(M, "asset_digest", return_value=assets),
                  patch.object(M.cs, "snapshot", new=cached_snapshot)):
                try:
                    _record(run, freeze_it=freeze_it, index_ready=True, cfg=cfg, agent=agent)
                    started = True
                except RuntimeError as err:
                    if "refused to start" not in str(err):
                        raise
                    started = False
            data = json.loads((run / M.MANIFEST_NAME).read_text(encoding="utf-8"))
            return run, data, started

        git("init", "-q")
        tracked = ("notes.md", "ablation_harness/eval.py", "ablation_harness/run_ablation.py",
                   "ablation_harness/host_paths.py")
        for path in tracked:
            put(path, "original\n")
        (repo / "asset.bin").write_bytes(b"original\x00binary\n")
        git("add", "--", ".")
        git("-c", "user.name=Offline Test", "-c", "user.email=offline@example.invalid", "commit", "-q", "-m", "fixture")

        # ponytail: this fixture never changes HEAD after setup; remove the cache if it
        # starts committing. Status, paths and diff are still sampled from Git each time.
        real_rev = prov.rev
        fixture_rev = real_rev(repo)
        fixture_patches.enter_context(patch.object(prov, "rev", lambda tree: fixture_rev if tree == repo else real_rev(tree)))
        check("scope/revision-cache-fixture", bool(fixture_rev))

        # Host dependencies are outside this isolated repository; every repository
        # T0 and T1 still runs the real git_state against the fixture.
        dependencies = {
            "isaaclab": {"available": False, "detail": "outside fixture"},
            "rsl_rl": {"available": False, "detail": "outside fixture"},
        }

        def code_sources():
            return {**dependencies, "repository": prov.git_state(repo, "repository", code_root=repo)}

        from rl_exp.tools.runrecord import lifecycle
        index = lifecycle.read_index()
        recipe = M.recipe_ref(cfg)
        assets = M.asset_digest(cfg.params_version, type(cfg).params_line)
        snapshots = {id(cfg): M.cs.snapshot(cfg), id(agent): M.cs.snapshot(agent)}
        real_snapshot = M.cs.snapshot

        def cached_snapshot(obj, **kwargs):
            return snapshots[id(obj)] if id(obj) in snapshots and not kwargs else real_snapshot(obj, **kwargs)

        # Real Git binary stubs are not patches; exercise capture and historical material.
        binary = repo / "asset.bin"
        for operation in ("modify", "delete", "add"):
            binary.write_bytes(b"original\x00binary\n")
            added = repo / "added.bin"
            added.unlink(missing_ok=True)
            if operation == "modify":
                binary.write_bytes(b"changed\x00binary\n")
            elif operation == "delete":
                binary.unlink()
            else:
                added.write_bytes(b"new\x00binary\n")
                git("add", "--", "added.bin")
            run, source_data, _ = record(f"binary_{operation}", "binary regression")
            raw_diff = prov.git(repo, "diff", "HEAD")
            apply_result = subprocess.run(["git", "apply", "--check", "-"], cwd=repo,
                                          input=raw_diff.encode("utf-8"), capture_output=True)
            check(f"binary/{operation}/real-stub", "Binary files " in raw_diff and apply_result.returncode != 0,
                  apply_result.stderr.decode("utf-8", errors="replace"))
            dest, archive = root / f"binary_dest_{operation}", root / f"binary_archive_{operation}"
            result, _ = R.capture(run, dest, archive)
            check(f"binary/{operation}/capture-refuses", result["verdict"] == "refused"
                  and any("binary" in x.lower() for x in result["refusals"]), str(result))
            if operation == "modify":
                archived = archive / run.name / "repository.diff"
                archived.parent.mkdir(parents=True, exist_ok=True)
                archived.write_text(raw_diff, encoding="utf-8", newline="")
                old_archive, _ = R.capture(run, root / "binary_old_archive", archive)
                check("binary/old-archive-refuses", old_archive["verdict"] == "refused"
                      and any("binary" in x.lower() for x in old_archive["refusals"]), str(old_archive["refusals"]))
                # Recreate an old captured material from the genuine T0 diff, independent of capture.
                diff = dest / "material" / "code" / "repository.diff"
                diff.parent.mkdir(parents=True, exist_ok=True)
                diff.write_text(raw_diff, encoding="utf-8", newline="")
                manifest_dest = dest / "material" / "run" / M.MANIFEST_NAME
                manifest_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(run / M.MANIFEST_NAME, manifest_dest)
                old = {"verdict": "captured", "items": {"repository": {"retrieval": "stored-diff",
                       "payload": "code/repository.diff", "recorded": source_data["code"]["repository"]}},
                       "payload_digests": {"code/repository.diff": prov.sha256_file(diff),
                                           "run/" + M.MANIFEST_NAME: prov.sha256_file(manifest_dest)}}
                (dest / R.MATERIAL_NAME).write_text(json.dumps(old), encoding="utf-8")
                rows, problems = R.check(dest, root / "rebuild_root", originals=[root / "absent"])
                check("binary/historical-check-blocks", R._exit_code(rows, problems) != 0
                      and any("binary" in row["detail"].lower() and row["required"] for row in rows), str(rows))
            if operation == "add":
                git("reset", "-q", "HEAD", "--", "added.bin")
            added.unlink(missing_ok=True)
        binary.write_bytes(b"original\x00binary\n")
        binary.write_bytes(b"first\x00binary\n")
        first = prov.git_state(repo, "repository", code_root=repo)
        first_diff = prov.git(repo, "diff", "HEAD")
        binary.write_bytes(b"second\x00binary\n")
        second = prov.git_state(repo, "repository", code_root=repo)
        second_diff = prov.git(repo, "diff", "HEAD")
        check("binary/index-records-live-change", first["diff_sha256"] != second["diff_sha256"]
              and first_diff != second_diff and "index " in first_diff and "index " in second_diff,
              f"first={first_diff!r}, second={second_diff!r}")
        drift_run, drift_data, _ = record("binary_post_t1_drift", "binary drift regression")
        binary.write_bytes(b"third\x00binary\n")
        drift_capture, _ = R.capture(drift_run, root / "binary_drift_dest", root / "binary_drift_archive")
        check("binary/post-t1-drift-refused", drift_data["code"]["repository"]["diff_sha256"] !=
              prov.git_state(repo, "repository", code_root=repo)["diff_sha256"]
              and drift_capture["verdict"] == "refused"
              and any("no longer matches" in text for text in drift_capture["refusals"]), str(drift_capture["refusals"]))
        binary.write_bytes(b"original\x00binary\n")

        untracked_binary = repo / "untracked.bin"
        untracked_binary.write_bytes(b"untracked\x00binary\n")
        untracked_run, _, _ = record("binary_untracked", "untracked regression")
        untracked_result, _ = R.capture(untracked_run, root / "binary_untracked_dest", root / "binary_untracked_archive")
        check("binary/untracked-archived", untracked_result["verdict"] == "captured"
              and (root / "binary_untracked_dest/material/code/repository/untracked.bin").read_bytes()
              == b"untracked\x00binary\n", str(untracked_result["refusals"]))
        untracked_binary.unlink()

        # Real text hunk contains the same sentence, but never a Git summary line.
        put("ablation_harness/host_paths.py", "Binary files a/foo and b/foo differ\n")
        text_run, _, _ = record("binary_text_sentence", "text regression")
        text_result, _ = R.capture(text_run, root / "binary_text_dest", root / "binary_text_archive")
        check("binary/text-sentence-not-stub", text_result["verdict"] == "captured", str(text_result["refusals"]))
        clean()

        # Binary on an excluded path alone is restored by revision; mixed diffs are conservatively refused.
        (repo / "ablation_harness/eval.py").write_bytes(b"excluded\x00binary\n")
        excluded_run, _, _ = record("binary_excluded")
        excluded_result, _ = R.capture(excluded_run, root / "binary_excluded_dest")
        check("binary/excluded-only", excluded_result["verdict"] == "captured"
              and excluded_result["items"]["repository"]["retrieval"] == "git-rev", str(excluded_result))
        put("ablation_harness/host_paths.py", "protected text\n")
        mixed_run, _, _ = record("binary_mixed", "mixed regression")
        mixed_result, _ = R.capture(mixed_run, root / "binary_mixed_dest", root / "binary_mixed_archive")
        check("binary/excluded-mixed-conservative", mixed_result["verdict"] == "refused"
              and any("binary" in x.lower() for x in mixed_result["refusals"]), str(mixed_result["refusals"]))
        clean()

        # Each path is changed alone; no override on the first real launch.
        cases = (
            ("tracked-prose", "notes.md", False),
            ("untracked-prose", "new_notes.md", True),
            ("tracked-eval", "ablation_harness/eval.py", False),
            ("untracked-eval", "ablation_harness/record.py", True),
            ("tracked-dispatch", "ablation_harness/run_ablation.py", False),
        )
        for name, path, untracked in cases:
            clean()
            if untracked and (repo / path).exists():
                raise AssertionError(f"fixture path must be untracked: {path}")
            put(path, "changed\n")
            run, data, started = record(f"scope_{name}")
            source = data["code"]["repository"]
            check(f"scope/{name}/launch", started, str(data.get("failures")))
            check(
                f"scope/{name}/t0-classification",
                source.get("dirty") is True and source.get("changed_blocking") == []
                and isinstance(source.get("eval_exclusive_paths"), list)
                and (path.endswith(".md") or path in source.get("eval_exclusive_paths", [])),
                str({key: source.get(key) for key in ("dirty", "changed_blocking", "eval_exclusive_paths")}),
            )
            # Even an old startup refusal must not hide the actual rebuild defect.
            if not started:
                run, data, _ = record(f"scope_{name}_override", "offline scope regression")
                source = data["code"]["repository"]
            captured, _ = R.capture(run, root / f"capture_{name}")
            check(f"scope/{name}/item-no-archive", captured["items"]["repository"]["retrieval"] == "git-rev",
                  str(captured["refusals"]))
            check(f"scope/{name}/capture-no-archive", captured["verdict"] == "captured", str(captured["refusals"]))
            saved = captured["items"]["repository"]["recorded"]
            check(
                f"scope/{name}/snapshot-roundtrip",
                "eval_exclusive_paths" in source and "changed_blocking" in source
                and saved.get("eval_exclusive_paths") == source["eval_exclusive_paths"]
                and saved.get("changed_blocking") == source["changed_blocking"]
                and saved.get("changed_paths_full") == source.get("changed_paths_full")
                and "eval_exclusive_paths" in saved and "changed_blocking" in saved and "changed_paths_full" in saved,
                f"T0={source.get('eval_exclusive_paths')}, {source.get('changed_blocking')}; material={saved}",
            )

            if name == "tracked-eval":
                snapshot = source.get("eval_exclusive_paths")
                replacement = tuple(entry for entry in prov.EVAL_EXCLUSIVE_PATHS if entry != path)
                with patch.object(prov, "EVAL_EXCLUSIVE_PATHS", replacement):
                    current = code_sources()["repository"]
                    changed_capture, _ = R.capture(run, root / "capture_declaration_changed")
                    check(
                        "scope/declaration-changed/t0-wins",
                        path not in current.get("eval_exclusive_paths", [path])
                        and path in current.get("changed_blocking", [])
                        and changed_capture["items"]["repository"]["retrieval"] == "git-rev"
                        and changed_capture["verdict"] == "captured"
                        and changed_capture["items"]["repository"]["recorded"].get("eval_exclusive_paths") == snapshot,
                        f"current={current.get('eval_exclusive_paths')}, {current.get('changed_blocking')}; "
                        f"capture={changed_capture['refusals']}",
                    )

            if name == "tracked-prose":
                # Model historical on-disk records from this real run, preserving a valid T1.
                for missing in (("eval_exclusive_paths",), ("changed_blocking",),
                                ("eval_exclusive_paths", "changed_blocking")):
                    legacy = json.loads(json.dumps(data))
                    for key in missing:
                        legacy["code"]["repository"].pop(key, None)
                    legacy["t1_sha256"] = M.t1_digest(legacy)
                    (run / M.MANIFEST_NAME).write_text(json.dumps(legacy), encoding="utf-8")
                    old_capture, _ = R.capture(run, root / ("legacy_" + "_".join(missing)))
                    check(
                        f"scope/legacy-missing-{'-'.join(missing)}",
                        old_capture["items"]["repository"]["retrieval"] == "none"
                        and old_capture["verdict"] == "refused"
                        and any("repository:" in x and "archive" in x for x in old_capture["refusals"]),
                        f"capture={old_capture['verdict']} {old_capture['refusals']}",
                    )

        clean()
        protected = "ablation_harness/host_paths.py"
        put(protected, "changed\n")
        run, data, started = record("scope_protected_override", "offline protected change")
        source = data["code"]["repository"]
        with patch.dict(os.environ, {M.DIRTY_OVERRIDE_ENV: ""}):
            refusal = M.dirty_tree_refusal(types.SimpleNamespace(manifest=data))
        check("scope/protected/dirty-refused", refusal is not None and "dirty" in refusal, str(refusal))
        check(
            "scope/protected/override-preserves-classification",
            started and data.get("declaration", {}).get("dirty_tree_override_reason") == "offline protected change"
            and protected in source.get("changed_blocking", []), str(source.get("changed_blocking")),
        )
        captured, _ = R.capture(run, root / "capture_protected")
        check(
            "scope/protected/override-no-archive-refused",
            captured["items"]["repository"]["retrieval"] == "none"
            and captured["verdict"] == "refused"
            and any("repository:" in x and "archive" in x for x in captured["refusals"]),
            f"capture={captured['verdict']} {captured['refusals']}",
        )

        clean()
        protected = "ablation_harness/host_paths.py"
        prose = "new_notes.md"
        exclusive = "ablation_harness/record.py"
        put(protected, "protected change\n")
        put(prose, "untracked prose\n")
        put(exclusive, "untracked eval\n")
        run, data, started = record("scope_mixed", "offline mixed regression")
        source = data["code"]["repository"]
        check("scope/mixed/t0", started and source.get("changed_blocking") == [protected]
              and {prose, exclusive} <= set(source.get("untracked_in_code_root", [])), str(source))
        with patch.object(prov, "code_sources", code_sources), patch.object(prov, "EVAL_EXCLUSIVE_PATHS", ()):
            row = M._verify_code(data, [])[0]
        check("scope/mixed/verify", row["result"] == "通过" and "untracked code" not in row["detail"], str(row))
        (repo / prose).unlink()
        (repo / exclusive).unlink()
        with patch.object(prov, "EVAL_EXCLUSIVE_PATHS", ()):
            captured, _ = R.capture(run, root / "capture_mixed", root / "mixed_archive")
        check("scope/mixed/archive", captured["verdict"] == "captured"
              and f"code/repository/{prose}" not in captured["payload_digests"]
              and f"code/repository/{exclusive}" not in captured["payload_digests"], str(captured["refusals"]))
        legacy = json.loads(json.dumps(data))
        for key in ("eval_exclusive_paths", "changed_blocking"):
            legacy["code"]["repository"].pop(key)
        with patch.object(prov, "code_sources", code_sources), patch.object(prov, "EVAL_EXCLUSIVE_PATHS", ()):
            row = M._verify_code(legacy, [])[0]
            old_refusals = []
            old_item = R._code_item("repository", legacy["code"]["repository"], root / "legacy_mixed_archive",
                                    "scope", root / "legacy_mixed_stage", {}, old_refusals)
        check("scope/mixed/legacy-verify", row["result"] == "未知"
              and "2 untracked code" in row["detail"], str(row))
        check("scope/mixed/legacy-archive", old_item["retrieval"] == "none"
              and any("gone and was never stored" in text for text in old_refusals), str(old_refusals))

        clean()
        unicode_path = "notes/中文 配置.yaml"
        filtered_path = "configs/run.log.yaml"
        put(protected, "protected tracked change alongside untracked\n")
        put("new_notes.md", "untracked prose alongside protected\n")
        put("ablation_harness/record.py", "untracked eval alongside protected\n")
        put(unicode_path, "untracked\n")
        put(filtered_path, "untracked protected configuration\n")
        run, data, started = record("scope_untracked", "offline untracked regression")
        source = data["code"]["repository"]
        check("scope/untracked-unicode/full-path", started and unicode_path in source.get("changed_blocking", [])
              and unicode_path in source.get("untracked_in_code_root", []), str(source))
        with patch.object(prov, "code_sources", code_sources):
            row = M._verify_code(data, [])[0]
        check("scope/untracked-protected/verify", row["result"] == "未知" and "2 untracked code" in row["detail"]
              and "ablation_harness/record.py" not in row["detail"] and "new_notes.md" not in row["detail"], str(row))
        (repo / "new_notes.md").unlink()
        (repo / "ablation_harness/record.py").unlink()
        captured, _ = R.capture(run, root / "capture_untracked", root / "untracked_archive")
        check("scope/untracked-unicode/archived", captured["verdict"] == "captured"
              and f"code/repository/{unicode_path}" in captured["payload_digests"], str(captured["refusals"]))
        check("scope/untracked-filtered/not-lost", started and filtered_path in source.get("changed_blocking", [])
              and filtered_path in source.get("untracked_in_code_root", [])
              and captured["verdict"] == "captured" and f"code/repository/{filtered_path}" in captured["payload_digests"],
              str(captured["refusals"]))

        clean()
        protected_path = "ablation_harness/host_paths.py"
        run = root / "scope_t0_t1_change"
        from test_run_manifest import _StubEnv, _StubRunner, _begin
        with (patch.dict(os.environ, {M.DIRTY_OVERRIDE_ENV: ""}), patch.object(prov, "code_sources", code_sources),
              patch.object(M, "recipe_ref", return_value=recipe),
              patch.object(M, "asset_digest", return_value=assets), patch.object(M.cs, "snapshot", cached_snapshot)):
            ctx = _begin(index_ready=True, log_dir=run, task="Lizard2-Flat-v4", argv=["train.py"],
                         env_cfg=cfg, agent_cfg=agent)
            env = _StubEnv(cfg)
            M.after_env(ctx, env)
            put(protected_path, "changed after T0\n")
            runner = _StubRunner(lr=agent.algorithm.learning_rate)
            M.hook_runner_save(runner, ctx)
            M.freeze(ctx, runner=runner, env=env, agent_cfg=agent, resume_path=None, drop_curriculum_state=False)
            runner.save(run / "model_42.pt")
        captured, _ = R.capture(run, root / "capture_t0_t1_change")
        check("scope/t0-t1-protected-change", captured["verdict"] != "captured"
              and any("code" in problem.lower() or "scope" in problem.lower()
                      for problem in [*captured["refusals"], *captured["problems"]]),
              f"T1 protected change must prevent a T0-only capture: {captured['verdict']}, "
              f"{captured['refusals']}, {captured['problems']}")

        clean()
        put(protected_path, "tracked dirty at T0\n")
        run = root / "scope_tracked_same_path"
        with (patch.dict(os.environ, {M.DIRTY_OVERRIDE_ENV: "test tracked drift"}),
              patch.object(prov, "code_sources", code_sources), patch.object(M, "recipe_ref", return_value=recipe),
              patch.object(M, "asset_digest", return_value=assets), patch.object(M.cs, "snapshot", cached_snapshot)):
            ctx = _begin(index_ready=True, log_dir=run, task="Lizard2-Flat-v4", argv=["train.py"],
                         env_cfg=cfg, agent_cfg=agent)
            env = _StubEnv(cfg)
            M.after_env(ctx, env)
            put(protected_path, "tracked dirty at T1\n")
            runner = _StubRunner(lr=agent.algorithm.learning_rate)
            M.hook_runner_save(runner, ctx)
            M.freeze(ctx, runner=runner, env=env, agent_cfg=agent, resume_path=None, drop_curriculum_state=False)
            runner.save(run / "model_42.pt")
        captured, _ = R.capture(run, root / "capture_tracked_same_path", root / "tracked_archive")
        check("scope/t0-t1-same-tracked", any("protected code scope changed" in p for p in captured["problems"]),
              f"tracked content drift must be recorded: {captured['verdict']}, {captured['problems']}")
        clean()
        put(protected_path, "tracked changed at T0\n")
        run, _, _ = record("scope_after_t1_tracked", "test post-T1 tracked drift")
        put(protected_path, "tracked changed after T1\n")
        captured, _ = R.capture(run, root / "capture_after_t1_tracked", root / "post_t1_tracked_archive")
        check("scope/after-t1-tracked", captured["verdict"] == "refused"
              and any("no longer matches" in text for text in captured["refusals"]), str(captured["refusals"]))

        # Untracked content identity belongs to verified-rebuild-rating; a pathname alone
        # cannot decide T0/T1 or post-T1 content equality.
        clean()
        put("ablation_harness/eval.py", "only eval changed before T0\n")
        run = root / "scope_declaration_changed_during_run"
        with (patch.dict(os.environ, {M.DIRTY_OVERRIDE_ENV: ""}), patch.object(prov, "code_sources", code_sources),
              patch.object(M, "recipe_ref", return_value=recipe),
              patch.object(M, "asset_digest", return_value=assets), patch.object(M.cs, "snapshot", cached_snapshot)):
            ctx = _begin(index_ready=True, log_dir=run, task="Lizard2-Flat-v4", argv=["train.py"],
                         env_cfg=cfg, agent_cfg=agent)
            env = _StubEnv(cfg)
            M.after_env(ctx, env)
            runner = _StubRunner(lr=agent.algorithm.learning_rate)
            M.hook_runner_save(runner, ctx)
            with patch.object(prov, "EVAL_EXCLUSIVE_PATHS", tuple(path for path in prov.EVAL_EXCLUSIVE_PATHS
                                                                  if path != "ablation_harness/eval.py")):
                M.freeze(ctx, runner=runner, env=env, agent_cfg=agent, resume_path=None, drop_curriculum_state=False)
            runner.save(run / "model_42.pt")
        captured, _ = R.capture(run, root / "capture_declaration_during_run")
        recorded = json.loads((run / M.MANIFEST_NAME).read_text(encoding="utf-8"))
        t0 = recorded["code"]["repository"]
        t1 = recorded["stages"]["ready_to_learn"]["code"]["repository"]
        check("scope/t0-declaration-during-run", captured["verdict"] == "captured"
              and "ablation_harness/eval.py" in t0["eval_exclusive_paths"]
              and "ablation_harness/eval.py" in t1["changed_blocking"]
              and "ablation_harness/eval.py" in t1["changed_paths_full"],
              f"T1 must classify with the T0 declaration: {captured['verdict']}, {captured['problems']}")

        clean()
        run = root / "scope_t0_t1_untracked"
        with (patch.dict(os.environ, {M.DIRTY_OVERRIDE_ENV: "test untracked drift"}),
              patch.object(prov, "code_sources", code_sources), patch.object(M, "recipe_ref", return_value=recipe),
              patch.object(M, "asset_digest", return_value=assets), patch.object(M.cs, "snapshot", cached_snapshot)):
            ctx = _begin(index_ready=True, log_dir=run, task="Lizard2-Flat-v4", argv=["train.py"],
                         env_cfg=cfg, agent_cfg=agent)
            env = _StubEnv(cfg)
            M.after_env(ctx, env)
            put("configs/run.log.yaml", "new protected file after T0\n")
            runner = _StubRunner(lr=agent.algorithm.learning_rate)
            M.hook_runner_save(runner, ctx)
            M.freeze(ctx, runner=runner, env=env, agent_cfg=agent, resume_path=None, drop_curriculum_state=False)
            runner.save(run / "model_42.pt")
        captured, _ = R.capture(run, root / "capture_t0_t1_untracked", root / "untracked_drift_archive")
        check("scope/t0-t1-untracked", captured["verdict"] != "captured"
              and any("protected code scope changed" in text for text in captured["problems"]), str(captured))
        clean()

        clean()
        for i in range(45):
            put(f"bulk/{i:02}.py", "changed\n")
        put("z_protected.py", "untracked\n")
        _, data, started = record("scope_over_cap", "offline over-cap regression", freeze_it=False)
        source = data["code"]["repository"]
        blocking = source.get("changed_blocking") or []
        check(
            "scope/over-40/full-blocking",
            started and len(blocking) == 46 and "z_protected.py" in blocking
            and all(f"bulk/{i:02}.py" in blocking for i in range(45)),
            f"blocking count={len(blocking)}, last={blocking[-3:]}",
        )
        result, refusals = item(source)
        check("scope/over-40/no-archive-refused", result["retrieval"] == "none" and bool(refusals), str(refusals))
        check("scope/revision-stayed-fixed", real_rev(repo) == fixture_rev, "fixture HEAD changed during cached sampling")


def main() -> int:
    root = pathlib.Path(tempfile.mkdtemp(prefix="rebuild_gate_"))
    real_sources, real_git, real_tree_root = prov.code_sources, prov.git, R._tree_root
    trees = _fake_trees(root)
    R._tree_root = lambda name: trees[name]
    assets = ExitStack()
    try:
        asset_repo = assets.enter_context(isolated_assets(root))
        assets.enter_context(patch.object(R, "_REPO", asset_repo))
        assets.enter_context(active_index(root))
        cfg, agent = Lizard2FlatV4EnvCfg(), Lizard2V4PPORunnerCfg()
        recipe = M.recipe_ref(cfg)
        asset_digest = M.asset_digest(cfg.params_version, type(cfg).params_line)
        snapshots = {id(cfg): M.cs.snapshot(cfg), id(agent): M.cs.snapshot(agent)}
        real_snapshot = M.cs.snapshot

        def cached_snapshot(obj, **kwargs):
            return snapshots[id(obj)] if id(obj) in snapshots and not kwargs else real_snapshot(obj, **kwargs)

        # ponytail: synthetic cases do not change recipe inputs; remove this cache if they do.
        from rl_exp.tools.verify import check_cfg_lock
        build_entry = check_cfg_lock.build_entry
        recipe_entries = {}

        def cached_entry(task, spec):
            key = (task, json.dumps(spec, sort_keys=True))
            if key not in recipe_entries:
                recipe_entries[key] = build_entry(task, spec)
            return recipe_entries[key]

        assets.enter_context(patch.object(check_cfg_lock, "build_entry", cached_entry))

        def record_fixture(run):
            with patch.object(M, "recipe_ref", return_value=recipe), patch.object(
                M, "asset_digest", return_value=asset_digest
            ), patch.object(M.cs, "snapshot", new=cached_snapshot):
                return _record(run, index_ready=True, cfg=cfg, agent=agent)

        # 1. a dirty diff that has drifted: the recorded content is gone for good
        prov.code_sources = lambda: _sources("OLD DIFF")
        prov.git = _fake_git("DIFFERENT DIFF")
        run = root / "run_drifted"
        record_fixture(run)
        record, _ = R.capture(run, root / "dest_drifted")
        check(
            "capture/refuse-drifted-diff",
            record["verdict"] == "refused" and any("no longer matches" in line for line in record["refusals"]),
            f"{record['verdict']} {record['refusals'][:2]}",
        )
        check("capture/refusal-writes-no-material", not (root / "dest_drifted" / "material").exists())
        check(
            "capture/refusal-is-written-down",
            json.loads((root / "dest_drifted" / R.MATERIAL_NAME).read_text(encoding="utf-8"))["verdict"] == "refused",
        )

        # 2. a dirty diff with no archive location: hashed, but retrievable from nowhere
        prov.code_sources = lambda: _sources("SAME DIFF")
        prov.git = _fake_git("SAME DIFF")
        run = root / "run_noarch"
        record_fixture(run)
        record, _ = R.capture(run, root / "dest_noarch")
        check(
            "capture/refuse-without-archive",
            record["verdict"] == "refused" and any("work/active/verified-rebuild-rating.md" in line for line in record["refusals"]),
            f"{record['verdict']} {record['refusals'][:2]}",
        )

        # 3. the same diff, with an archive: content stored and hashed back
        archive = root / "archive"
        record, _ = R.capture(run, root / "dest_archived", archive)
        stored = archive / record["run_id"] / "repository.diff"
        check("capture/accept-with-archive", record["verdict"] == "captured", f"{record['verdict']} {record['refusals']}")
        check(
            "capture/stored-diff-hashes-as-recorded",
            stored.is_file() and prov.sha256_file(stored) == record["items"]["repository"]["recorded"]["diff_sha256"],
            f"{stored}",
        )
        check("capture/payload-keeps-the-content", "code/repository.diff" in record["payload_digests"])
        check(
            "capture/payload-hash-matches",
            prov.sha256_file(root / "dest_archived" / "material" / "code" / "repository.diff")
            == record["payload_digests"]["code/repository.diff"],
        )
        check(
            "capture/clean-source-needs-no-archive",
            record["items"]["isaaclab"]["retrieval"] == "git-rev"
            and "git checkout" in record["items"]["isaaclab"]["payload"],
            "a clean source comes back by revision without an archive",
        )

        # 4. untracked code: content, not a hash, or nothing
        prov.code_sources = lambda: _sources("SAME DIFF", untracked=("source/spider",))
        run = root / "run_untracked"
        record_fixture(run)
        record, _ = R.capture(run, root / "dest_untracked", archive)
        check(
            "capture/refuse-vanished-untracked",
            record["verdict"] == "refused" and any("never stored" in line for line in record["refusals"]),
            f"{record['verdict']} {record['refusals'][:2]}",
        )
        (trees["repository"] / "source" / "spider").mkdir(parents=True)
        (trees["repository"] / "source" / "spider" / "spider_env_cfg.py").write_text("SPIDER = 1\n", encoding="utf-8")
        record, _ = R.capture(run, root / "dest_untracked", archive)
        check("capture/keep-untracked-code", record["verdict"] == "captured", f"{record['refusals'][:2]}")
        check(
            "capture/untracked-payload-stored",
            "code/repository/source/spider/spider_env_cfg.py" in record["payload_digests"],
            f"{sorted(record['payload_digests'])}",
        )

        # 5. the check: material integrity, sources, isolation, payload binding
        dest = root / "dest_untracked"
        ckpt = _real_ckpt(run)
        record, _ = R.capture(run, dest, archive)
        deps = [pathlib.Path(R.__file__).resolve().parents[3], prov.isaac_root(), asset_repo]
        gone = root / "not_a_source_path"
        check("check/empty-rebuilt-is-unknown", R._exit_code(R.check_sources(root, [], [gone], rebuilt=()), []) == 2)
        source_rows = R.check_sources(root / "rebuild_root", deps, [gone])
        check("check/rebuilt-module-not-excused-by-dependency",
              any(row["result"] == "失败" for row in source_rows), str(source_rows))
        asset_rows = R.check_asset_origins(root / "rebuild_root", deps, [gone],
                                           json.loads((run / M.MANIFEST_NAME).read_text(encoding="utf-8")))
        check("check/asset-lock-not-excused-by-dependency",
              any(row["result"] == "失败" for row in asset_rows), str(asset_rows))
        check("check/sibling-path-not-under-root",
              not R._under(root / "rebuild_root_other" / "rl_exp.py", [root / "rebuild_root"]))
        old_root = root / "rebuild_root"
        rows, problems = R.check(dest, old_root, deps, [gone])
        check("check/missing-root-fails", R._exit_code(rows, problems) != 0
              and any("rebuild root is not a directory" in row["detail"] for row in rows), str(rows))

        rebuild_root = asset_repo
        source = pathlib.Path(R.__file__).resolve().parents[3]
        for directory in ("rl_exp/tools/runrecord", "rl_exp/tools/verify"):
            shutil.copytree(source / directory, rebuild_root / directory, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "out"))
        for filename in ("rl_exp/__init__.py", "rl_exp/tools/__init__.py"):
            src = source / filename
            if src.is_file():
                shutil.copy2(src, rebuild_root / filename)
        # This in-process fixture checks material and checkpoint branches only; import origin
        # is validated by the fresh-interpreter cases below.
        assets.enter_context(patch.object(R, "_module_origin", return_value=rebuild_root / "rl_exp" / "__init__.py"))
        rows, problems = R.check(dest, rebuild_root, deps[1:], [gone])
        check("check/exit-code", R._exit_code(rows, problems) == 0, f"{[(r['result'], r['detail'][:60]) for r in rows if r['required']]}")
        check(
            "check/scope-declares-reuse",
            any(r["detail"].startswith("scope: rebuilt") and r["result"] == "通过" for r in rows),
            f"{[r['detail'][:70] for r in rows]}",
        )
        check(
            "check/material-row",
            any(r["detail"].startswith("material:") and r["result"] == "通过" for r in rows),
            f"{[r['detail'][:40] for r in rows]}",
        )
        check(
            "check/binding-row",
            any(r["detail"].startswith(f"checkpoints: {ckpt}") and r["result"] == "通过" for r in rows),
            f"{[r['detail'][:50] for r in rows]}",
        )
        check(
            "check/informational-rows-do-not-decide",
            any(r["result"] == "未知" and not r["required"] for r in rows),
            "a bare run record cannot know about an archive, so its code rows stay unknown",
        )

        # 6. the fallback assertion: resolving back into the original tree must fail, while
        #    the original merely being readable is scope, not a failure
        readable = root / "still_there"
        readable.mkdir()
        deps = deps[1:]
        rows, _ = R.check(dest, rebuild_root, deps, originals=[])
        check(
            "check/no-original-is-unknown",
            R._exit_code(rows, []) == 2
            and any(r["result"] == "未知" and r["required"] and "no fallback was asserted" in r["detail"] for r in rows),
            f"{[(r['result'], r['detail'][:60]) for r in rows]}",
        )
        rows, _ = R.check(dest, rebuild_root, originals=[rebuild_root])
        check(
            "check/fallback-to-original-fails",
            any(r["result"] == "失败" and "resolved back into the original tree" in r["detail"] for r in rows),
            f"{[(r['result'], r['detail'][:60]) for r in rows if r['result'] == '失败']}",
        )
        rows, _ = R.check(dest, rebuild_root, deps, originals=[readable])
        check(
            "check/readable-original-is-informational",
            R._exit_code(rows, []) == 0
            and any("still readable" in r["detail"] and not r["required"] for r in rows),
            f"{[(r['result'], r['detail'][:60]) for r in rows]}",
        )
        rows, _ = R.check(dest, root / "rebuild_root", [], [gone])
        check(
            "check/undeclared-import-location-fails",
            any(r["result"] == "失败" and "did not resolve under the rebuild root" in r["detail"] for r in rows),
            f"{[(r['result'], r['detail'][:60]) for r in rows if r['result'] == '失败']}",
        )
        rows = R.check_sources(rebuild_root, deps, [gone])
        check(
            "check/reused-deps-are-not-asserted",
            R._exit_code(rows, []) == 0 and "resolves under" in rows[0]["detail"],
            "the framework is a declared dependency, so where it resolves is recorded, not asserted",
        )
        with patch.object(R, "_module_origin", side_effect=lambda name: (
            rebuild_root / "rl_exp" / "__init__.py" if name == "rl_exp" else deps[0] / "isaaclab" / "__init__.py"
        )):
            rows = R.check_sources(rebuild_root, deps[:1], [gone], rebuilt=("rl_exp", "isaaclab"))
        check(
            "check/rebuilt-module-is-asserted",
            any("isaaclab" in r["detail"] and r["result"] == "失败" for r in rows),
            "declaring the framework rebuilt as well must assert where it came from",
        )
        rows, _ = R.check(dest, rebuild_root, deps, originals=[asset_repo])
        check(
            "check/asset-lock-fallback-fails",
            any(r["result"] == "失败" and "the lock resolves back into the original tree" in r["detail"] for r in rows),
            f"{[(r['result'], r['detail'][:60]) for r in rows if r['result'] == '失败']}",
        )
        rows, _ = R.check(dest, deps[0], deps, originals=[deps[0]])
        check(
            "check/path-config-only-is-not-a-drill",
            R._exit_code(rows, []) != 0
            and any("not a material recovery drill" in r["detail"] and r["required"] for r in rows),
            f"{[(r['result'], r['detail'][:70]) for r in rows]}",
        )

        # 7. the missing-file negative test
        code = (
            "import json, pathlib, sys; "
            "from rl_exp.tools.runrecord import rebuild as r; "
            "root, source, lock = map(pathlib.Path, sys.argv[1:]); "
            "rows = r.check_sources(root, [source], [source]); "
            "assets = r.check_asset_origins(root, [source], [source], "
            "{'declaration': {'assets': {'lock': str(lock)}}}); "
            "print(json.dumps({'origin': str(r._module_origin('rl_exp')), 'rows': rows + assets, "
            "'exit': r._exit_code(rows + assets, [])}))"
        )
        for label, cwd, expected in (("restored", rebuild_root, 0), ("original", source, 1)):
            child_env = {**os.environ, "PYTHONPATH": str(cwd), "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run([sys.executable, "-B", "-c", code, str(rebuild_root), str(source),
                                     "<REPO_ROOT>/rl_exp/versions/lizard2/main/v4/asset_lock.json"],
                                    cwd=cwd, env=child_env, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace")
            data = json.loads(result.stdout.splitlines()[-1]) if result.returncode == 0 and result.stdout else {}
            expected_origin = cwd / "rl_exp" / "__init__.py"
            source_row = next((row for row in data.get("rows", []) if row["detail"].startswith("sources:")), {})
            asset_row = next((row for row in data.get("rows", []) if row["detail"].startswith("assets:")), {})
            expected_result = "通过" if expected == 0 else "失败"
            check(f"check/real-process-{label}", result.returncode == 0 and data.get("exit") == expected
                  and pathlib.Path(data.get("origin", "")).resolve() == expected_origin.resolve()
                  and source_row.get("result") == expected_result and asset_row.get("result") == expected_result,
                  f"exit={result.returncode}, data={data}, stderr={result.stderr[-400:]}")

        with patch.object(R, "check", wraps=R.check) as checks:
            rows, problems = R.maintest(dest, rebuild_root, deps, [gone], rebuilt=("rl_exp",))
        check("maintest/rebuilt-scope-preserved", len(checks.call_args_list) == 2
              and all(len(call.args) >= 5 and call.args[4] == ("rl_exp",) for call in checks.call_args_list))
        check(
            "maintest/removed-payload-fails",
            any("must fail" in r["detail"] and r["result"] == "通过" for r in rows),
            f"{[r['detail'][:70] for r in rows]}",
        )
        check(
            "maintest/restored-payload-passes",
            any("restored" in r["detail"] and r["result"] == "通过" for r in rows),
            f"{[r['detail'][:70] for r in rows]}",
        )
        check(
            "maintest/payload-is-back",
            prov.sha256_file(dest / "material" / "run" / f"{ckpt}") == record["payload_digests"][f"run/{ckpt}"],
        )

        # 8. a refused material is never claimed (exit 2, not 0)
        rows, _ = R.check(root / "dest_noarch", rebuild_root, deps, [gone])
        check(
            "check/refused-material-not-claimed",
            R._exit_code(rows, []) == 2 and any("was not captured" in r["detail"] for r in rows),
            f"{[(r['result'], r['detail'][:50]) for r in rows]}",
        )

        # 9. an edited payload must not pass the material row
        victim = dest / "material" / "run" / f"{ckpt}"
        original = victim.read_bytes()
        victim.write_bytes(original + b"x")
        rows, _ = R.check(dest, rebuild_root, deps, [gone])
        check(
            "check/edited-payload-fails",
            any(r["detail"].startswith("material:") and r["result"] == "失败" for r in rows),
            f"{[r['detail'][:60] for r in rows]}",
        )
        victim.write_bytes(original)

        # 10. a record edited after freezing is not a rebuild subject
        forged = root / "run_forged"
        record_fixture(forged)
        path = forged / M.MANIFEST_NAME
        data = json.loads(path.read_text(encoding="utf-8"))
        data["declaration"]["seed"] = 7
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        record, problems = R.capture(forged, root / "dest_forged")
        check(
            "capture/refuse-edited-record",
            record["verdict"] == "failed" and any("T1 digest" in line for line in record["problems"]),
            f"{record['verdict']} {record['problems']}",
        )
        rows, _ = R.check(root / "dest_forged", rebuild_root, deps, [gone])
        check(
            "check/failed-material-blocks",
            R._exit_code(rows, []) == 1 and rows[0]["result"] == "失败",
            f"{[(r['result'], r['detail'][:50]) for r in rows]}",
        )
    finally:
        assets.close()
        prov.code_sources, prov.git, R._tree_root = real_sources, real_git, real_tree_root
        shutil.rmtree(root, ignore_errors=True)

    try:
        _real_git_scope(root / "real_git_scope", cfg, agent)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    for problem in PROBLEMS:
        print(f"  {problem}")
    print("REBUILD_GATE_TEST_OK" if not PROBLEMS else "REBUILD_GATE_TEST_DRIFT")
    return 0 if not PROBLEMS else 1


if __name__ == "__main__":
    # Git for Windows' cmd/git.exe launches another process on each invocation. Use
    # the native executable from the same installation; all Git samples stay live.
    git_exe = shutil.which("git")
    git_path = os.environ.get("PATH", "")
    if os.name == "nt" and git_exe:
        result = subprocess.run([git_exe, "--exec-path"], capture_output=True, text=True)
        if result.returncode == 0:
            native_bin = pathlib.Path(result.stdout.strip()).parent.parent / "bin"
            launcher = native_bin.parent.parent / "cmd" / "git.exe"
            if launcher.is_file() and pathlib.Path(git_exe).resolve() == launcher.resolve() and (native_bin / "git.exe").is_file():
                git_path = str(native_bin) + os.pathsep + git_path
    with patch.dict(os.environ, {"PATH": git_path}):
        raise SystemExit(main())
