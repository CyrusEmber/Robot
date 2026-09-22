# -*- coding: utf-8 -*-
"""Negative control + acceptance check for the family-landing tool: no other family takes part.

Run in-process by ``check_dr_parity.py --self-test`` (the gate whose contracts these are) and
standalone while debugging. The property under test is the one that decides whether "create a new
family" is a generic operation or a copy of a historical one:

* a tree holding EXACTLY ONE family can be declared (nothing is looked up in a sibling);
* the tool writes only that family's subtree;
* its artifacts mention no other family (no template leakage into PLAN/NOTES/FAMILY);
* the zero-drift guard's scope is "every family but the target", not a name;
* a gate that fails fails the run, and a guard with nothing to compare refuses instead of
  passing quietly;
* the parity gate's subject list and the asset contract's key list are DECLARATIONS: a yaml
  without the old family's keys is checked on its own terms instead of being refused.

Everything runs offline (no sim, no IsaacLab import): the tool is driven as a subprocess on a
synthetic tree, and the two gate entry points are imported for their pure functions.
"""

import json
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/pipeline")
sys.path.insert(0, "rl_exp/tools/verify")
import declare_family as df  # noqa: E402
import check_dr_parity as dp  # noqa: E402

PY = sys.executable
TOOL = "rl_exp/tools/pipeline/declare_family.py"

PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def _family_tree(root: pathlib.Path, family: str = "zoo") -> pathlib.Path:
    """A tree with ONE family and no sibling to copy from, plus the shared registries.

    The wiring class is written the way a real line writes it -- the key it declares about
    itself (``params_line``) is the only thing the tool may use to find it -- and it derives from
    an ``isaaclab_tasks`` import so the stock parent is discoverable without another family.
    """
    (root / "rl_exp" / "assets" / family).mkdir(parents=True)
    (root / "rl_exp" / "assets" / family / f"{family}.usda").write_text("x\n", encoding="utf-8")
    (root / "rl_exp" / "versions" / family / "main").mkdir(parents=True)
    (root / "rl_exp" / "versions" / family / f"{family}.urdf").write_text("<robot/>\n", encoding="utf-8")
    (root / "rl_exp" / "versions" / family / "main" / "main_params.yaml").write_text(
        "robot:\n  name: %s\n" % family, encoding="utf-8")
    (root / "rl_exp" / "versions" / "lines.json").write_text(
        json.dumps({"format": 1, "lines": {f"{family}/main": {"status": "active", "successor": None,
                                                             "retired_at": None, "reason": None}}}),
        encoding="utf-8")
    (root / "rl_exp" / "versions" / "recipes.json").write_text(
        json.dumps({"format": 1,
                    "recipes": {f"{family}-flat-v1@1": {"line": f"{family}/main",
                                                        "env_cfg_entry": f"rl_exp.tasks.{family}_env_cfg:ZooEnvCfg",
                                                        "agent_entry": "rl_exp.tasks.agents.ppo:ZooRunnerCfg",
                                                        "legacy_task_version": "v1"}},
                    "tasks": {f"Zoo-Flat-v1": f"{family}-flat-v1@1"}}), encoding="utf-8")
    (root / "rl_exp" / "tasks").mkdir(parents=True)
    (root / "rl_exp" / "tasks" / f"{family}_env_cfg.py").write_text(
        "from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import StockEnvCfg\n\n\n"
        "class ZooWiringCfg(StockEnvCfg):\n"
        "    params_line = \"%s/main\"\n" % family, encoding="utf-8")
    return root


def run(root: pathlib.Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, TOOL, "--root", str(root), "--family", "zoo", "--line", "main",
                           "--version", "v1", "--experiment-name", "zoo_v1", *extra],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=".")


def snapshot(root: pathlib.Path) -> dict[str, bytes]:
    """Every file under ``rl_exp`` as bytes, so "what did this run change" is answered by content."""
    base = root / "rl_exp"
    return {str(p.relative_to(root)).replace("\\", "/"): p.read_bytes()
            for p in base.rglob("*") if p.is_file()}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = _family_tree(pathlib.Path(tmp))

        # --- 1. a one-family tree is declarable: no reference family, no template -------------
        dry = run(root)
        check("one-family-tree/declares", dry.returncode == 0,
              f"rc={dry.returncode}; output tail: {dry.stdout[-600:]}")
        check("one-family-tree/no-reference-flag", "reference" not in (dry.stdout + dry.stderr).lower(),
              "the run mentions a reference family")
        check("one-family-tree/stock-parent", "stock base" in dry.stdout and "StockEnvCfg" in dry.stdout,
              "the framework stock parent was not derived from the module's own imports")

        # --- 2. apply writes only this family's subtree, and names no other family -----------
        before = snapshot(root)
        applied = run(root, "--apply", "--reason", "self-check")
        check("apply/succeeds-on-a-copy", applied.returncode == 0, f"rc={applied.returncode}: {applied.stdout[-600:]}")
        after = snapshot(root)
        changed = [p for p in sorted(set(before) | set(after)) if before.get(p) != after.get(p)]
        check("apply/changed-something", bool(changed), "the run wrote nothing at all")
        check("apply/wrote-only-target-family",
              all(p.startswith("rl_exp/versions/zoo/") for p in changed),
              f"files changed outside the target family: {[p for p in changed if not p.startswith('rl_exp/versions/zoo/')]}")
        for name in ("main_params.yaml", "base.json", "PLAN.md", "NOTES.md"):
            check(f"apply/{name}", (root / "rl_exp" / "versions" / "zoo" / "main" / "v1" / name).is_file(), "missing")
        texts = "\n".join((root / "rl_exp" / "versions" / "zoo" / p).read_text(encoding="utf-8")
                          for p in ("FAMILY.md", "main/v1/PLAN.md", "main/v1/NOTES.md"))
        check("apply/artifacts-mention-no-other-family", "lizard" not in texts.lower(),
              "an artifact of the new family carries another family's name (template leakage)")

        # --- 3. the zero-drift guard's scope excludes ONLY the target family -----------------
        real = pathlib.Path(".").resolve()
        scope = df.foreign_locks(real, "lizard")
        check("guard/scope-is-every-other-family",
              bool(scope) and all(k.startswith("lizard2/") for k in scope),
              f"target lizard should see only lizard2 files, saw {sorted(scope)[:3]}")

    # --- 4. a gate that fails fails the run (rc participation) ------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        broken = _family_tree(pathlib.Path(tmp))
        (broken / "rl_exp" / "tasks" / "zoo_env_cfg.py").unlink()  # preconditions must refuse
        refused = run(broken)
        check("refusal/broken-tree-fails", refused.returncode == 1 and "REFUSED" in refused.stdout,
              f"rc={refused.returncode}: {refused.stdout[-400:]}")

    # --- 5. the parity subjects are a declaration, and an empty one refuses ------------------
    with tempfile.TemporaryDirectory() as tmp:
        empty = pathlib.Path(tmp) / "freeze_parity.json"
        empty.write_text(json.dumps({"format": 1, "subjects": []}), encoding="utf-8")
        keep = dp.SUBJECTS_PATH
        dp.SUBJECTS_PATH = empty
        subjects, problems = dp.load_subjects()
        check("subjects/empty-declaration-refuses", subjects == [] and bool(problems), f"problems={problems}")
        empty.write_text(json.dumps({"format": 1, "subjects": [{"line": "x", "family_cfg": "nope.py",
                                                                "teacher_cfg": "nope.py"}]}), encoding="utf-8")
        subjects, problems = dp.load_subjects()
        check("subjects/missing-files-refuse", sum("missing" in p for p in problems) == 2,
              f"problems={problems}")
        dp.SUBJECTS_PATH = keep
        real_subjects, real_problems = dp.load_subjects()
        check("subjects/repo-declares-one", len(real_subjects) == 1 and not real_problems,
              f"{real_problems or [s.get('line') for s in real_subjects]}")

        # --- 6. the asset contract follows declared keys, not the old family's shape ---------
        yaml_text = "robot:\n  usd_path: assets/zoo/zoo.usda\n  joint_order:\n    - a\n    - b\n"
        lists = dp._declared_block_lists(yaml_text)
        check("contract/finds-declared-lists", sorted(lists) == ["joint_order"], f"{sorted(lists)}")
        check("contract/no-limb-key-required", "limb_body_names" not in lists,
              "a yaml without the old family's DR block would still be refused by a fixed key list")

    if PROBLEMS:
        print(f"DECLARE_FAMILY_SELF_TEST_FAILED ({len(PROBLEMS)})")
        return 1
    print("DECLARE_FAMILY_SELF_TEST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
