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
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")

import torch  # noqa: E402

from rl_exp.tools.runrecord import manifest as M  # noqa: E402
from rl_exp.tools.runrecord import provenance as prov  # noqa: E402
from rl_exp.tools.runrecord import rebuild as R  # noqa: E402
from test_run_manifest import _record  # noqa: E402

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

    def git(tree, *args):
        if args[:1] == ("cat-file",) or args[:2] == ("rev-parse", "--verify"):
            return "present"
        if args[:2] == ("diff", "HEAD"):
            return live_diff
        return real(tree, *args)

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


def main() -> int:
    root = pathlib.Path(tempfile.mkdtemp(prefix="rebuild_gate_"))
    real_sources, real_git, real_tree_root = prov.code_sources, prov.git, R._tree_root
    trees = _fake_trees(root)
    R._tree_root = lambda name: trees[name]
    try:
        # 1. a dirty diff that has drifted: the recorded content is gone for good
        prov.code_sources = lambda: _sources("OLD DIFF")
        prov.git = _fake_git("DIFFERENT DIFF")
        run = root / "run_drifted"
        _record(run)
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
        _record(run)
        record, _ = R.capture(run, root / "dest_noarch")
        check(
            "capture/refuse-without-archive",
            record["verdict"] == "refused" and any("PLAN.md #18" in line for line in record["refusals"]),
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
        _record(run)
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
        deps = [pathlib.Path(R.__file__).resolve().parents[3], prov.isaac_root()]
        gone = root / "not_a_source_path"
        rows, problems = R.check(dest, root / "rebuild_root", deps, [gone])
        check("check/exit-code", R._exit_code(rows, problems) == 0, f"{[(r['result'], r['detail'][:60]) for r in rows if r['required']]}")
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
        rows, _ = R.check(dest, root / "rebuild_root", deps, originals=[])
        check(
            "check/no-original-is-unknown",
            R._exit_code(rows, []) == 2
            and any(r["result"] == "未知" and r["required"] and "no fallback was asserted" in r["detail"] for r in rows),
            f"{[(r['result'], r['detail'][:60]) for r in rows]}",
        )
        rows, _ = R.check(dest, root / "rebuild_root", originals=[pathlib.Path(R.__file__).resolve().parents[3]])
        check(
            "check/fallback-to-original-fails",
            any(r["result"] == "失败" and "resolved back into the original tree" in r["detail"] for r in rows),
            f"{[(r['result'], r['detail'][:60]) for r in rows if r['result'] == '失败']}",
        )
        rows, _ = R.check(dest, root / "rebuild_root", deps, originals=[readable])
        check(
            "check/readable-original-is-informational",
            R._exit_code(rows, []) == 0
            and any("still readable" in r["detail"] and not r["required"] for r in rows),
            f"{[(r['result'], r['detail'][:60]) for r in rows]}",
        )
        rows, _ = R.check(dest, root / "rebuild_root", [], [gone])
        check(
            "check/undeclared-import-location-fails",
            any(r["result"] == "失败" and "outside the rebuild" in r["detail"] for r in rows),
            f"{[(r['result'], r['detail'][:60]) for r in rows if r['result'] == '失败']}",
        )
        rows = R.check_sources(root / "rebuild_root", deps, [gone])
        check(
            "check/reused-deps-are-not-asserted",
            R._exit_code(rows, []) == 0 and "resolves under" in rows[0]["detail"],
            "the framework is a declared dependency, so where it resolves is recorded, not asserted",
        )
        rows = R.check_sources(root / "rebuild_root", deps[:1], [gone], rebuilt=("rl_exp", "isaaclab"))
        check(
            "check/rebuilt-module-is-asserted",
            any("isaaclab" in r["detail"] and r["result"] == "失败" for r in rows),
            "declaring the framework rebuilt as well must assert where it came from",
        )
        rows, _ = R.check(dest, root / "rebuild_root", deps, originals=[deps[0]])
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
        rows, _ = R.check(dest, root / "rebuild_root", deps, originals=[gone])
        check(
            "check/scope-declares-reuse",
            any(r["detail"].startswith("scope: rebuilt") and r["result"] == "通过" for r in rows),
            f"{[r['detail'][:70] for r in rows]}",
        )

        # 7. the missing-file negative test
        rows, problems = R.maintest(dest, root / "rebuild_root", deps, [gone])
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
        rows, _ = R.check(root / "dest_noarch", root / "rebuild_root", deps, [gone])
        check(
            "check/refused-material-not-claimed",
            R._exit_code(rows, []) == 2 and any("was not captured" in r["detail"] for r in rows),
            f"{[(r['result'], r['detail'][:50]) for r in rows]}",
        )

        # 9. an edited payload must not pass the material row
        victim = dest / "material" / "run" / f"{ckpt}"
        original = victim.read_bytes()
        victim.write_bytes(original + b"x")
        rows, _ = R.check(dest, root / "rebuild_root", deps, [gone])
        check(
            "check/edited-payload-fails",
            any(r["detail"].startswith("material:") and r["result"] == "失败" for r in rows),
            f"{[r['detail'][:60] for r in rows]}",
        )
        victim.write_bytes(original)

        # 10. a record edited after freezing is not a rebuild subject
        forged = root / "run_forged"
        _record(forged)
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
        rows, _ = R.check(root / "dest_forged", root / "rebuild_root", deps, [gone])
        check(
            "check/failed-material-blocks",
            R._exit_code(rows, []) == 1 and rows[0]["result"] == "失败",
            f"{[(r['result'], r['detail'][:50]) for r in rows]}",
        )
    finally:
        prov.code_sources, prov.git, R._tree_root = real_sources, real_git, real_tree_root
        shutil.rmtree(root, ignore_errors=True)

    for problem in PROBLEMS:
        print(f"  {problem}")
    print("REBUILD_GATE_TEST_OK" if not PROBLEMS else "REBUILD_GATE_TEST_DRIFT")
    return 0 if not PROBLEMS else 1


if __name__ == "__main__":
    raise SystemExit(main())
