# -*- coding: utf-8 -*-
"""Framework pin check: does this IsaacLab tree still provide what we rely on?

The lizard stack leans on several IsaacLab INTERNALS (not public API). Each one
is a silent breakage waiting for an upstream refactor. This script greps the
IsaacLab SOURCE TREE (plain python, no kit/app needed) for the exact symbols
we depend on, and compares the tree's git commit against the pinned SHA that
the whole stack was last verified against.

Pinned IsaacLab: 28a37cecdd433c22d9eabd6a5954add9f13a8951 (tag perf-2026-06-24)

Usage: python rl_exp\\tools\\verify\\framework_pin_check.py [--isaac-root PATH] [--strict]
  --strict also fails on SHA mismatch (default: symbol checks fail, SHA warns)
  Root resolution order: --isaac-root > paths.yaml / env RL_ISAAC_ROOT (read by
  ablation_harness/host_paths.py) > venv python location.
"""
import argparse
import ast
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

# the one reader of machine-local host paths, shared with the eval harness
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "ablation_harness"))
import host_paths  # noqa: E402

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PATCH_DIR = _REPO_ROOT / "rl_exp" / "fork_patches"

PINNED_SHA = "28a37cecdd433c22d9eabd6a5954add9f13a8951"
PINNED_DESC = "perf-2026-06-24 (tested 2026-08-31)"

# (file under <root>, regex, who depends on it)
NEEDLES = [
    ("source/isaaclab/isaaclab/managers/manager_base.py",
     r"term_cfg\.func = term_cfg\.func\(cfg=term_cfg",
     "staged_curriculum._dependency_met (curriculum term cross-reference)"),
    ("source/isaaclab/isaaclab/sensors/ray_caster/base_ray_caster.py",
     r"meshes: ClassVar",
     "teacher_mdp.FootContactNormalsTerm (global wp mesh registry)"),
    ("source/isaaclab/isaaclab/utils/warp/kernels.py",
     r"def raycast_mesh_masked_kernel",
     "teacher_mdp.FootContactNormalsTerm (terrain normal raycast)"),
    ("source/isaaclab/isaaclab/assets/articulation/base_articulation_data.py",
     r"def joint_stiffness",
     "metrics.step_energy (live PD gains readback)"),
    ("source/isaaclab/isaaclab/assets/articulation/base_articulation_data.py",
     r"def joint_damping",
     "metrics.step_energy (live PD gains readback)"),
    ("source/isaaclab/isaaclab/assets/articulation/base_articulation.py",
     r"def write_root_velocity_to_sim",
     "recovery.apply_kick (velocity kick)"),
    ("source/isaaclab/isaaclab/envs/manager_based_env_cfg.py",
     r"seed: int \| None",
     "eval.py env_cfg.seed pinning"),
    ("source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py",
     r"height_scanner\.update_period = self\.decimation \* self\.sim\.dt",
     "family/teacher scanner cadence contract (50 Hz policy rate)"),
    # v3: obs groups reach the model through the wrapper untouched
    ("source/isaaclab_rl/isaaclab_rl/rsl_rl/vecenv_wrapper.py",
     r"return TensorDict\(obs_dict, batch_size=\[self\.num_envs\]\)",
     "SplitEncoderModel (obs dict -> TensorDict group passthrough)"),
    # resume timing: the c_k clock lives here, and curriculum compute must stay
    # ahead of the command reset that reads the joint SIR's desired_vel
    ("source/isaaclab/isaaclab/envs/manager_based_rl_env.py",
     r"self\.common_step_counter = 0",
     "curriculum_state.collect (the c_k clock is captured/restored here)"),
    ("source/isaaclab/isaaclab/envs/manager_based_rl_env.py",
     r"self\.curriculum_manager\.compute\(env_ids=env_ids\)",
     "curriculum_state.apply_resume_state (restore-before-first-reset timing)"),
]

# same but inside the rsl_rl package the venv installs under <root>: the
# class_name point-path registration is the whole v3 architecture's foundation
RSL_RL_NEEDLES = [
    ("env_isaaclab/Lib/site-packages/rsl_rl/utils/utils.py",
     r'if ":" in callable_or_name:',
     "teacher_networks class_name point path (module:Class resolution)"),
    ("env_isaaclab/Lib/site-packages/rsl_rl/utils/utils.py",
     r"def resolve_obs_groups",
     "obs_groups cfg validation (actor/critic sets -> env group names)"),
    ("env_isaaclab/Lib/site-packages/rsl_rl/algorithms/ppo.py",
     r'resolve_callable\(cfg\["actor"\]\.pop\("class_name"\)\)',
     "v3 runner actor class_name injection (SplitEncoderModel)"),
    ("env_isaaclab/Lib/site-packages/rsl_rl/algorithms/ppo.py",
     r'resolve_callable\(cfg\["critic"\]\.pop\("class_name"\)\)',
     "v3 runner critic class_name injection"),
    ("env_isaaclab/Lib/site-packages/rsl_rl/algorithms/distillation.py",
     r'resolve_callable\(cfg\["student"\]\.pop\("class_name"\)\)',
     "Phase 2 student class_name injection (student_networks)"),
    ("env_isaaclab/Lib/site-packages/rsl_rl/algorithms/distillation.py",
     r'resolve_callable\(cfg\["teacher"\]\.pop\("class_name"\)\)',
     "Phase 2 teacher class_name injection"),
    ("env_isaaclab/Lib/site-packages/rsl_rl/models/mlp_model.py",
     r"def get_latent",
     "SplitEncoderModel base-class forward protocol"),
    # resume: the curriculum state rides the checkpoint's infos slot
    ("env_isaaclab/Lib/site-packages/rsl_rl/runners/on_policy_runner.py",
     r"def save\(self, path: str, infos: dict \| None = None\)",
     "curriculum_state.hook_runner_save (infos parameter still exists)"),
    ("env_isaaclab/Lib/site-packages/rsl_rl/runners/on_policy_runner.py",
     r'saved_dict\["infos"\] = infos',
     "curriculum_state.hook_runner_save (infos still lands in the checkpoint)"),
]


#: The one fork file whose DR semantics we inherit without a recipe covering them
#: (work/closed/2026/fork-tree-dr-semantics-and-hygiene.md). ``force_range``/``torque_range`` are deliberately NOT pinned: our
#: recipes assign them explicitly, so their fork values never reach an experiment.
DR_EVENT_FILE = (
    "source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py"
)

#: Event term -> the fields frozen here. ``check_fork_patches`` compares the tree against
#: the archives, so an edit applied to BOTH sides keeps that comparison green: only a
#: constant held outside the tree can catch a silently re-pinned experiment.
FORK_DR_SEMANTICS: dict[str, dict[str, object]] = {
    "base_external_force_torque": {"mode": "interval", "interval_range_s": (4.0, 8.0)},
    "push_robot": {"mode": "interval", "interval_range_s": (3.0, 6.0)},
}


def _event_term_keywords(path: pathlib.Path) -> dict[str, dict[str, object]]:
    """``{assignment name: {keyword: value}}`` for every ``X = Something(...)`` in a module.

    Values come from :func:`ast.literal_eval`, so a bound name or an f-string reads as
    ``None`` -- a field this check cannot see must not read as a field that matches.
    """
    terms: dict[str, dict[str, object]] = {}
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8", errors="replace"))):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            fields: dict[str, object] = {}
            for kw in node.value.keywords:
                if kw.arg is None:
                    continue
                try:
                    fields[kw.arg] = ast.literal_eval(kw.value)
                except (ValueError, SyntaxError):
                    fields[kw.arg] = None
            terms[target.id] = fields
    return terms


def check_fork_dr_semantics(root: pathlib.Path, failures: list[str]) -> None:
    """The DR the fork tree injects behind our back must not move silently.

    Two push events in :data:`DR_EVENT_FILE` carry their ``mode``/``interval_range_s`` from
    the fork tree, not from our recipes (work/closed/2026/fork-tree-dr-semantics-and-hygiene.md): they decide every run's random kicks
    and are otherwise visible only as a golden diff. Read by assignment target, so a comment
    or a different event cannot satisfy the pin.
    """
    path = root / DR_EVENT_FILE
    if not path.is_file():
        failures.append(f"{DR_EVENT_FILE}: file gone (fork DR semantics, work/closed/2026/fork-tree-dr-semantics-and-hygiene.md)")
        return
    terms = _event_term_keywords(path)
    for name, expected in FORK_DR_SEMANTICS.items():
        fields = terms.get(name)
        if fields is None:
            failures.append(f"{DR_EVENT_FILE}: event term '{name}' is gone (work/closed/2026/fork-tree-dr-semantics-and-hygiene.md)")
            continue
        for field, want in expected.items():
            got = fields.get(field)
            if got != want:
                failures.append(
                    f"{DR_EVENT_FILE}: {name}.{field} is {got!r}, frozen at {want!r} "
                    "(fork DR semantics, work/closed/2026/fork-tree-dr-semantics-and-hygiene.md)"
                )


_SELF_TEST_FIXTURE = """base_external_force_torque = EventTerm(
    func=mdp.apply_external_force_torque,
    mode="interval",
    interval_range_s={ft},
)
push_robot = EventTerm(
    func=mdp.push_by_setting_velocity,
    mode="interval",
    interval_range_s={push},
)
"""


def self_test() -> list[str]:
    """Falsify the DR-semantics reader on fixtures, in-process, without a fork tree.

    The case that earns the gate is the renamed one: an edit applied to the tree AND the
    patch archive together keeps ``check_fork_patches`` green, so the pin has to read its
    own constant and bind it to the assignment name -- a file that merely still contains
    the frozen values in some other event must fail.

    Returns:
        One problem per fixture that behaved unlike the tree would.
    """
    cases = [
        (_SELF_TEST_FIXTURE.format(ft="(4.0, 8.0)", push="(3.0, 6.0)"), []),
        (_SELF_TEST_FIXTURE.format(ft="(5.0, 8.0)", push="(3.0, 6.0)"),
         ["base_external_force_torque.interval_range_s"]),
        (_SELF_TEST_FIXTURE.format(ft="(4.0, 8.0)", push="(2.0, 6.0)"),
         ["push_robot.interval_range_s"]),
        # a value the reader cannot see (a bound name) must read as a mismatch, not as a match
        (_SELF_TEST_FIXTURE.format(ft="SOME_CONST", push="(3.0, 6.0)"),
         ["base_external_force_torque.interval_range_s"]),
        # the frozen values survive in another term: still not the event we inherited
        (_SELF_TEST_FIXTURE.format(ft="(4.0, 8.0)", push="(3.0, 6.0)")
         .replace("base_external_force_torque", "some_other_term"), ["is gone"]),
    ]
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="dr_pin_self_test_") as tmp:
        case = pathlib.Path(tmp) / DR_EVENT_FILE
        case.parent.mkdir(parents=True, exist_ok=True)
        for text, expected in cases:
            case.write_text(text, encoding="utf-8")
            found: list[str] = []
            check_fork_dr_semantics(pathlib.Path(tmp), found)
            if not expected and found:
                problems.append(f"self-test: the frozen fixture must pass, got {found}")
            elif expected and not all(any(want in f for f in found) for want in expected):
                problems.append(f"self-test: expected a failure naming {expected}, got {found}")
    print(f"FORK_DR_SEMANTICS_SELF_TEST_OK ({len(cases)} fixtures)")
    return problems


def _patch_targets(patch: pathlib.Path) -> list[str]:
    """The file paths one patch touches, read from its ``+++ b/<path>`` headers."""
    return re.findall(r"^\+\+\+ b/(.+?)\s*$", patch.read_text(encoding="utf-8"), re.M)


def _git(args: list[str], cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    """Run git (text mode); ``cwd`` defaults to this process's directory."""
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def check_fork_patches(root: pathlib.Path, failures: list[str]) -> None:
    """The archives under ``fork_patches/`` must still describe this fork tree.

    setup.bat only ever looks at the tree -- forward-apply, or ``--check --reverse``
    to skip what is already applied -- so an archive that drifted from its own
    baseline, or a tree hand-edited inside a patched region, keeps exit code 0 while
    a hunk silently disappears: the resume hook, the run manifest, the declaration
    gate. Rebuild each archive from the tree's own HEAD in a scratch repo, chain them
    the way setup.bat does, and compare the result byte for byte.
    """
    patches = sorted(PATCH_DIR.glob("*.patch"))
    if not patches:
        return
    if not (root / ".git").exists():
        print("WARN: fork tree is not a git repo -- cannot verify the patch archives against it")
        return
    targets = sorted({rel for patch in patches for rel in _patch_targets(patch)})
    baseline_ok = True
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="pin_patch_"))
    try:
        subprocess.run(["git", "init", "-q", "."], cwd=scratch, check=True, capture_output=True)
        for rel in targets:
            blob = subprocess.run(
                ["git", "-C", str(root), "show", f"HEAD:{rel}"], capture_output=True, check=False
            )
            if blob.returncode != 0:
                failures.append(f"{rel}: not in the fork tree's HEAD -- cannot rebuild {len(patches)} archive(s)")
                baseline_ok = False
                continue
            dest = scratch / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob.stdout)
        for patch in patches:
            applied = _git(["-C", str(root), "apply", "--check", str(patch)])
            reversed_ = _git(["-C", str(root), "apply", "--check", "--reverse", str(patch)])
            if applied.returncode == 0:
                failures.append(
                    f"{patch.name}: NOT applied to the fork tree (setup.bat step 3 applies the archives; "
                    "without them the run silently loses the hook it declares)"
                )
                baseline_ok = False
            elif reversed_.returncode != 0:
                failures.append(
                    f"{patch.name}: neither applied nor appliable -- the tree and the archive disagree "
                    f"({reversed_.stderr.strip().splitlines()[:1]})"
                )
                baseline_ok = False
            if baseline_ok:
                chained = _git(["apply", "-p1", str(patch)], cwd=scratch)
                if chained.returncode != 0:
                    failures.append(
                        f"{patch.name}: does not apply to its own baseline (re-pin the archive): "
                        f"{chained.stderr.strip().splitlines()[:1]}"
                    )
                    baseline_ok = False
        if baseline_ok:
            for rel in targets:
                # newline-normalized: core.autocrlf is machine-local and both the
                # archives and the hunks are newline-agnostic, so a CRLF difference is
                # a local checkout setting, not a content drift
                rebuilt = (scratch / rel).read_bytes().replace(b"\r\n", b"\n")
                actual = (root / rel).read_bytes().replace(b"\r\n", b"\n")
                if rebuilt != actual:
                    failures.append(f"{rel}: rebuilt-from-archives != fork tree (a hunk was edited in one place only)")
    except (OSError, subprocess.SubprocessError) as err:  # noqa: BLE001
        print(f"WARN: patch-archive rebuild unavailable ({type(err).__name__}: {err})")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def detect_root(cli: str | None) -> pathlib.Path | None:
    """IsaacLab tree: explicit flag, then host_paths, then the venv's own tree."""
    root = host_paths.isaac_root(override=cli)
    if root is not None:
        return root
    # a venv installed under <ROOT> (<ROOT>/env_isaaclab/Scripts/python.exe) still
    # names the tree through its own interpreter, so ask that before giving up
    exe = pathlib.Path(sys.executable)
    cand = exe.parents[2] if len(exe.parents) > 2 else None
    if cand is not None and (cand / "source" / "isaaclab").is_dir():
        return cand
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--isaac-root", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--self-test", action="store_true", help="also falsify the DR-semantics reader")
    args = parser.parse_args()

    root = detect_root(args.isaac_root)
    if root is None:
        print("FAIL: IsaacLab root not found (pass --isaac-root, or record it in "
              "paths.yaml / RL_ISAAC_ROOT -- see paths.example.yaml)")
        return 1
    print(f"IsaacLab root: {root}")

    failures = self_test() if args.self_test else []
    for rel, pattern, user in NEEDLES + RSL_RL_NEEDLES:
        path = root / rel
        if not path.is_file():
            failures.append(f"{rel}: file gone ({user})")
            continue
        if not re.search(pattern, path.read_text(encoding="utf-8", errors="replace"), re.M):
            failures.append(f"{rel}: pattern '{pattern}' no longer present ({user})")

    # dirty-tree WARN: a locally modified pinned tree invalidates every needle
    try:
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=15, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        dirty = ""
    if dirty:
        print(f"WARN: IsaacLab tree has uncommitted changes ({len(dirty.splitlines())} entries) -- "
              "needle checks read the working tree, not the pinned SHA")

    try:
        sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        sha = ""
    if not sha:
        print(f"WARN: cannot read IsaacLab git SHA (pin {PINNED_SHA[:12]} unverifiable)")
    elif sha == PINNED_SHA:
        print(f"ISAAC_SHA_MATCH {sha[:12]} ({PINNED_DESC})")
    else:
        msg = (f"ISAAC_SHA_DIFF {sha[:12]} != pinned {PINNED_SHA[:12]} -- "
               "re-run the smoke chain before trusting results")
        print(("FAIL: " if args.strict else "WARN: ") + msg)
        if args.strict:
            failures.append(msg)

    check_fork_dr_semantics(root, failures)
    check_fork_patches(root, failures)

    for f in failures:
        print(f"FAIL: {f}")
    if failures:
        print(f"PIN_CHECK_FAILED ({len(failures)}) -- framework moved under us; "
              "fix the dependents or re-pin after a full verification pass")
        return 1
    print("PIN_CHECK_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
