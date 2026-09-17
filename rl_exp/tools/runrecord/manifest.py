# -*- coding: utf-8 -*-
"""Run manifest: what a training run actually was, recorded where it can be checked.

ARCH_PLAN 1.2. The recipe golden (``check_cfg_lock.py``) says what the *code* would
produce; this module records what a *run* did, at three time points, and freezes it
once the final training conditions are known:

======================  ===========================================================
``pre_make``            before ``gym.make``: declared recipe / asset / terrain /
                        obs-layout references, seed, env count, sim and control dt,
                        the requested resume, and the code provenance actually loaded
``env_constructed``     after construction: resolved env cfg digest, what the env
                        really did (num_envs, params_version, dts, seed) versus the
                        declaration, and the live obs group dimensions
``ready_to_learn``      after the runner is built and the checkpoint restored, and
                        BEFORE ``learn``: the resolved algorithm / policy classes,
                        effective learning rate, obs groups, resume source hash, and
                        the curriculum-state evidence -- then the manifest is frozen
                        and its digest is what checkpoints point back at
======================  ===========================================================

Checkpoints carry ``infos[CKPT_INFOS_KEY]`` = the run id + the frozen manifest digest
+ the iteration + a payload digest -- never the manifest *file* hash of the file it
lives in, and never a hash of the checkpoint itself (that goes to the external
``checkpoints.json`` index, which is written after the file exists).

Failure semantics (ARCH_PLAN hard constraints 1 and 5): recording never crashes
training, but a failure before T1 makes the run **incomplete** -- the manifest gets a
``failure`` entry, ``ready_to_learn`` is never written, and later checkpoints say
``status: incomplete`` instead of pointing at a T1 digest. Silent green is the one
outcome this module must not produce, so every check either passes, fails visibly, or
is reported as unknown with a reason.

One thing this module **refuses** instead of recording: a training launch from a dirty
project tree (``dirty_tree_refusal``). The T0 record is still written first, so a refused
launch leaves evidence rather than nothing; the refusal is then a ``failure`` entry plus a
non-zero exit. A dirty tree is not a run whose provenance is merely awkward -- no revision
restores it, so its rebuildable claim could never be proven, and finding that out months
later is strictly worse than finding it out at launch.

Verify offline: ``python -m rl_exp.tools.runrecord.manifest --verify <log_dir>``.
The report is two-dimensional, as the plan requires: evidence level (record complete /
rebuildable / rebuild verified) crossed with result (pass / fail / unknown).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.runrecord import lifecycle as lifecycle_gate  # noqa: E402
from rl_exp.tools.runrecord import provenance as prov  # noqa: E402
from rl_exp.tools.verify import cfg_snapshot as cs  # noqa: E402
from rl_exp.tools.verify import recipe_lifecycle  # noqa: E402

FORMAT_VERSION = 1
MANIFEST_NAME = "run_manifest.json"
INDEX_NAME = "checkpoints.json"
CKPT_INFOS_KEY = "run_manifest"
STAGES = ("pre_make", "env_constructed", "ready_to_learn")

EVIDENCE_LEVELS = ("记录完整", "可重建", "已验证重建")
RESULTS = ("通过", "失败", "未知")


def _now() -> str:
    return prov.now()


def _atomic_write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)



def asset_digest(params_version: str | None, line_key: str | None = None) -> dict:
    """Digest of the frozen asset lock (an allow-list, not a dependency closure).

    The paths listed by the lock are resolved relative to ``rl_exp`` (that is how the
    lock is written) and hashed now; a listed file that is missing is reported, since
    a lock whose files are gone proves nothing.

    Args:
        params_version: the recipe version whose lock applies, or None for the live
            development recipe (which has no lock).
        line_key: the recipe line that owns the version. Version names repeat across
            lines -- ``v1`` exists on main, parkour and baseline -- so a search by version
            alone has several answers and used to return whichever sorted first. Give the
            line and the answer is unambiguous; leave it out and several matches are
            reported rather than guessed.

    Returns:
        The asset reference: lock path, lock hash, per-file hash map digest, and the
        list of files that could not be read.
    """
    if not params_version:
        return {"lock": None, "detail": "live development recipe: no frozen asset lock"}
    lock_path = None
    if line_key:
        from rl_exp.tools.verify.recipe_lines import RecipeLineError, discover

        try:
            lines = discover()
        except RecipeLineError as err:
            return {"lock": None, "detail": f"recipe line discovery failed: {err}"}
        line = lines.get(line_key)
        if line is None:
            return {"lock": None, "detail": f"params_line={line_key!r} is not a discovered recipe line"}
        candidate = line.root / params_version / "asset_lock.json"
        if not candidate.is_file():
            return {"lock": None, "detail": f"line {line_key!r} has no {params_version} asset lock"}
        lock_path = candidate
    if lock_path is None:
        candidates = sorted(_REPO.glob(f"rl_exp/versions/lizard/**/{params_version}/asset_lock.json"))
        if len(candidates) > 1:
            return {
                "lock": None,
                "detail": f"{len(candidates)} lines carry a {params_version} lock"
                f" {[c.relative_to(_REPO).as_posix() for c in candidates]}; the caller must name the line",
            }
        if not candidates:
            return {"lock": None, "detail": f"no asset_lock.json for {params_version!r}"}
        lock_path = candidates[0]
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return {"lock": cs.relativize(str(lock_path)), "detail": f"unreadable: {err}"}
    files = lock.get("files", {})
    hashes: dict[str, str] = {}
    missing: list[str] = []
    for rel, recorded in sorted(files.items()):
        digest = prov.sha256_file(_REPO / "rl_exp" / rel)
        if digest is None:
            missing.append(rel)
            continue
        if digest != recorded:
            missing.append(f"{rel} (content changed: {digest[:12]} != {recorded[:12]})")
        hashes[rel] = digest
    return {
        "lock": cs.relativize(str(lock_path)),
        "lock_sha256": prov.sha256_file(lock_path),
        "file_count": len(files),
        "manifest_sha256": prov.sha256_bytes(
            json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "missing_or_changed": missing,
        "closure": "allow-list only (USD dependency closure not implemented)",
    }


def protocol_ref(task_id: str | None) -> dict:
    """The observation protocol a task's recipe declares (``ARCH_PLAN`` Step 3.1d).

    Two different facts, named apart on purpose: ``obs_protocol_digest`` is the *declared*
    protocol -- the layout a reviewer approved and the gate holds the tree to -- while
    ``obs_layout_digest`` is the observation subtree this session actually instantiated. They
    agree until someone edits a layout without re-declaring it, and that drift is worth being
    able to read off a run record rather than re-deriving later.
    """
    if not isinstance(task_id, str) or not task_id:
        return {"obs_protocol": None, "obs_protocol_note": "no golden task id, so no protocol to name"}
    try:
        from rl_exp.tasks import obs_protocol
    except ImportError as err:  # the declaration is in-repo, so this is a broken install
        return {"obs_protocol": None, "obs_protocol_note": f"obs_protocol unimportable: {err!r}"}
    try:
        key = obs_protocol.protocol_for(task_id)
        entry = (obs_protocol.anchors().get("protocols") or {}).get(key)
    except obs_protocol.ProtocolError as err:
        return {"obs_protocol": None, "obs_protocol_note": f"{task_id}: {err}"}
    entry = entry if isinstance(entry, dict) else {}
    return {
        "obs_protocol": key,
        "obs_protocol_digest": entry.get("digest"),
        "obs_protocol_dims": entry.get("dims") or {},
        # which articulation order the obs and the action indexed during this run: a pinned,
        # measured fact, so a checkpoint can be traced to the order it was trained under
        "runtime_joint_order_digest": obs_protocol.joint_order_digest(task_id),
    }


def recipe_ref(env_cfg) -> dict:
    """The recipe this run declares, plus whether it still matches the committed golden.

    The run's own digest contains the session's overrides (``--num_envs``, seed, device,
    log dir), so it is recorded but never required to equal the recipe golden. What the
    overrides actually changed is recorded separately, because "the recipe says X and the
    run used Y" is the fact a later reader needs.
    """
    snapshot = cs.snapshot(env_cfg)
    version = getattr(env_cfg, "params_version", None)
    ref = {
        "params_version": version if isinstance(version, str) else None,
        "recipe_digest": cs.digest(snapshot),
        "obs_layout_digest": cs.digest(snapshot.get("observations", {})),
        "note": "obs_layout_digest is the layout this session instantiated; obs_protocol* is the declared protocol (ARCH_PLAN Step 3.1d)",
    }
    # the golden lives in the file of the line this recipe declares (one file per line,
    # so "whose golden is this" is readable); the combination block is shared by all lines
    from rl_exp.tools.verify.recipe_lines import RecipeLineError, discover

    line_key = getattr(type(env_cfg), "params_line", None)
    try:
        lines = discover()
    except RecipeLineError as err:
        ref["golden"] = f"recipe line discovery failed: {err}"
        return ref
    line = lines.get(line_key)
    if line is None:
        ref["golden"] = (
            f"env cfg {type(env_cfg).__name__} declares params_line={line_key!r}, "
            f"which is not a discovered recipe line {sorted(lines)}"
        )
        return ref
    ref["params_line"] = line.key
    if not line.lock_path.is_file():
        ref["golden"] = f"no golden lock for line {line.key!r} in this tree"
        return ref
    try:
        lock = json.loads(line.lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        ref["golden"] = f"golden lock unreadable: {err}"
        return ref
    entries = lock.get("entries", {})
    entry = next((e for e in entries.values() if e.get("env_cfg_class", "").endswith(type(env_cfg).__name__)), None)
    if entry is None:
        ref["golden"] = f"no golden entry for {type(env_cfg).__name__}"
        return ref
    golden_key = next((k for k, e in entries.items() if e is entry), None)
    ref["golden_task"] = golden_key.split("|")[-1] if golden_key else None
    ref["golden_combination"] = golden_key.rsplit("|", 1)[0] if golden_key else None
    ref["golden_digest"] = entry.get("digest")
    ref.update(protocol_ref(ref.get("golden_task")))
    baselines_path = _REPO / "rl_exp" / "versions" / "cfg_baselines.json"
    baseline: dict = {}
    if baselines_path.is_file():
        try:
            baseline = (json.loads(baselines_path.read_text(encoding="utf-8")).get("baselines") or {}).get(
                ref["golden_combination"], {}
            )
        except (OSError, json.JSONDecodeError) as err:
            baseline = {}
            ref["golden_baselines_note"] = f"baselines unreadable: {err}"
    ref["golden_snapshot_format"] = baseline.get("cfg_snapshot_format")
    golden_env = (entry.get("snapshot") or {}).get("env")
    if golden_env is not None:
        from rl_exp.tools.verify.check_cfg_lock import walk_diff

        rows: list = []
        walk_diff(golden_env, snapshot, "", rows, limit=200)
        ref["session_overrides"] = [f"{path}: {before} -> {after}" for path, before, after in rows[:40]]
        ref["session_override_count"] = len(rows)
    ref["golden_digest_note"] = (
        "golden digest is over env+agent recipe defaults; this run's digest also "
        "contains session overrides, so the two are recorded, not required equal"
    )
    return ref


def _term_classes(env) -> dict:
    """Term callables of the live env cfg, as stable ``module:qualname`` strings."""
    out: dict[str, list[str]] = {}
    cfg = getattr(env.unwrapped, "cfg", None)
    for section in ("observations", "actions", "rewards", "terminations", "curriculum", "events", "commands"):
        terms = getattr(cfg, section, None)
        if terms is None or not hasattr(terms, "__dict__"):
            continue
        names = []
        for name, term in vars(terms).items():
            if name.startswith("_") or term is None:
                continue
            func = getattr(term, "func", None)
            if func is not None:
                names.append(f"{name}={func}")
        if names:
            out[section] = sorted(names)
    return out


class RunContext:
    """In-process state shared by the four recording call sites in the trainer.

    Attributes:
        log_dir: absolute run directory (``logs/rsl_rl/<experiment>/<timestamp>``).
        run_id: the run directory name; the key checkpoints point back at.
        manifest: the record being built up; written on every stage.
        frozen: True once ``ready_to_learn`` has been written.
        t1_sha256: digest of the frozen manifest, referenced by later checkpoints.
        failures: reasons recorded so far, newest last.
    """

    def __init__(self, log_dir: pathlib.Path, task: str | None):
        self.log_dir = pathlib.Path(log_dir)
        self.run_id = self.log_dir.name
        self.task = task
        self.manifest: dict = {}
        self.frozen = False
        self.t1_sha256: str | None = None
        self.failures: list[str] = []

    @property
    def manifest_path(self) -> pathlib.Path:
        return self.log_dir / MANIFEST_NAME

    @property
    def index_path(self) -> pathlib.Path:
        return self.log_dir / INDEX_NAME

    def fail(self, reason: str) -> None:
        """Record a failed check: visible in the manifest, never a crash."""
        self.failures.append(reason)
        self.manifest.setdefault("checks_failed", []).append({"at": _now(), "reason": reason})
        print(f"[run-manifest] FAIL: {reason}")
        self.flush()

    def flush(self) -> None:
        if not self.manifest:
            return
        self.manifest["failures"] = list(self.failures)
        self.manifest["updated_at"] = _now()
        try:
            # the manifest is written THROUGH the snapshot serializer: unset agent
            # fields (MISSING), non-finite floats, paths and any unforeseen object type
            # are all handled by one rule set instead of a json.dumps default
            _atomic_write(self.manifest_path, json.dumps(cs.snapshot(self.manifest), indent=1, ensure_ascii=False))
        except OSError as err:
            print(f"[run-manifest] could not write {self.manifest_path}: {err}")


def begin(*, log_dir, task: str | None, argv: list[str], env_cfg, agent_cfg) -> RunContext:
    """Stage ``pre_make``: what this run declares, before anything is built.

    Args:
        log_dir: the run directory (created by the trainer already).
        task: the gym task id launched.
        argv: the full command line, for the record.
        env_cfg: the env config as passed to ``gym.make`` (CLI overrides applied).
        agent_cfg: the agent config as resolved from the CLI.

    Returns:
        The run context to hand to the later stages.
    """
    ctx = RunContext(pathlib.Path(log_dir), task)
    declined: str | None = None
    try:
        ctx.manifest = {
            "run_manifest_format": FORMAT_VERSION,
            "run_id": ctx.run_id,
            "task": task,
            "argv": argv,
            "log_dir": cs.relativize(str(ctx.log_dir)),
            "started_at": _now(),
            "code": prov.code_sources(),
        }
        version = getattr(env_cfg, "params_version", None)
        assets = asset_digest(
            version if isinstance(version, str) else None, getattr(type(env_cfg), "params_line", None)
        )
        ctx.manifest["declaration"] = {
            "recipe": recipe_ref(env_cfg),
            "agent_digest": cs.digest(cs.snapshot(agent_cfg)),
            "assets": assets,
            "seed": getattr(env_cfg, "seed", None),
            "num_envs": getattr(getattr(env_cfg, "scene", None), "num_envs", None),
            "sim_dt": getattr(getattr(env_cfg, "sim", None), "dt", None),
            "decimation": getattr(env_cfg, "decimation", None),
            "control_dt": _control_dt(env_cfg),
            "resume_request": {
                "load_run": getattr(agent_cfg, "load_run", None),
                "load_checkpoint": getattr(agent_cfg, "load_checkpoint", None),
                "resume": getattr(agent_cfg, "resume", None),
                "max_iterations": getattr(agent_cfg, "max_iterations", None),
            },
            "distributed": _distributed(),
        }
        # Lifecycle (ARCH_PLAN 2.2, stage C1): the directory is read once, here, and the verdict
        # is recorded in T0 before anything is built. This is where the old trainer and the
        # tuning entry (which shells out to it) get their answer -- the gate lives in the module
        # they already call, so no new call site can be forgotten.
        #
        # A raising gate is a refusal, not a warning: an unknown permission is not a permission.
        try:
            verdict, lifecycle_evidence = lifecycle_gate.startup_check(
                task=task,
                argv=argv,
                agent_cfg=agent_cfg,
                log_dir=ctx.log_dir,
                declared_line=(ctx.manifest["declaration"]["recipe"] or {}).get("params_line"),
            )
        except Exception as err:  # noqa: BLE001
            verdict = None
            lifecycle_evidence = {
                "allowed": False,
                "reason": f"lifecycle check failed: {type(err).__name__}: {err}",
            }
        ctx.manifest["declaration"]["lifecycle"] = lifecycle_evidence
        if verdict is None or not verdict.allowed:
            declined = lifecycle_evidence["reason"]
        elif verdict.warn:
            print(f"[run-manifest] WARNING: {verdict.warn}")
        ctx.manifest["stages"] = {"pre_make": {"at": _now()}}
        # T0 hits disk immediately: if the process dies during gym.make, the launch
        # declaration must already be on disk
        ctx.flush()
        print(f"[run-manifest] {ctx.run_id}: T0 recorded ({ctx.manifest_path})")
    except Exception as err:  # noqa: BLE001
        ctx.fail(f"pre_make recording failed: {type(err).__name__}: {err}")
    drifted = ctx.manifest.get("declaration", {}).get("assets", {}).get("missing_or_changed")
    if drifted:
        # the run is about to use assets that no longer match the frozen lock
        ctx.fail(f"assets differ from the frozen lock: {drifted[:3]} (total {len(drifted)})")
    # with T0 already on disk: a refused launch leaves evidence, not nothing. The directory's
    # answer comes first: a line that is retired refuses whatever state the tree is in, and the
    # message it carries (which successor to move to) is the one the caller needs.
    if declined is not None:
        ctx.fail(f"refused to start: {declined}")
        raise RuntimeError(f"[run-manifest] refused to start: {declined}")
    refusal = dirty_tree_refusal(ctx)
    if refusal is not None:
        ctx.fail(f"refused to start: {refusal}")
        raise RuntimeError(f"[run-manifest] refused to start: {refusal}")
    override_reason = os.environ.get(DIRTY_OVERRIDE_ENV, "").strip()
    if override_reason:
        ctx.manifest.setdefault("declaration", {})["dirty_tree_override_reason"] = override_reason
        ctx.flush()
        print(f"[run-manifest] WARNING: dirty tree accepted via {DIRTY_OVERRIDE_ENV}: {override_reason}")
    return ctx


DIRTY_OVERRIDE_ENV = "RL_ALLOW_DIRTY_TREE"
"""Environment variable naming the reason a launch from a dirty tree is accepted.

An environment variable rather than a trainer CLI flag on purpose: the guard lives in the
module the trainer already calls, so turning it on needs no fork patch and no edit to the
fork tree -- and the fork tree is exactly where a CLI flag would have to live.
"""


def dirty_tree_refusal(ctx: RunContext) -> str | None:
    """Why this launch must abort, or None when the project tree may be trained from.

    Scoped to the project repository, not to every recorded code source: the IsaacLab tree
    is *expected* to carry the fork patches uncommitted, so refusing on it would refuse
    every launch and train people to set the override as a habit. Both stay recorded.

    Args:
        ctx: the run context whose T0 has just been written.

    Returns:
        The refusal message, or None when the tree is clean or the override carries a reason.
    """
    source = (ctx.manifest.get("code") or {}).get("repository") or {}
    if not source.get("dirty"):
        return None
    if os.environ.get(DIRTY_OVERRIDE_ENV, "").strip():
        return None
    return (
        f"the project tree is dirty (rev {source.get('rev', '?')}, "
        f"{source.get('diff_lines', '?')} diff line(s), {source.get('untracked_count', '?')} untracked): "
        f"no revision restores it, so this run's rebuildable claim could never be proven. Commit first, "
        f'or state the reason explicitly: {DIRTY_OVERRIDE_ENV}="<why this dirty tree must run>"'
    )


def _control_dt(env_cfg) -> float | None:
    sim = getattr(env_cfg, "sim", None)
    decimation = getattr(env_cfg, "decimation", None)
    dt = getattr(sim, "dt", None)
    return dt * decimation if dt and decimation else None


def _distributed() -> dict:
    return {"rank": int(os.getenv("RANK", "0")), "world_size": int(os.getenv("WORLD_SIZE", "1"))}


def after_env(ctx: RunContext, env) -> None:
    """Stage ``env_constructed``: what the env actually resolved, versus the declaration.

    A mismatch here is a real failure (the run is not what it declared), but it is
    recorded rather than raised: the plan forbids a silent green, not a lost run.
    """
    try:
        unwrapped = env.unwrapped
        declared = ctx.manifest.get("declaration", {})
        checks = {
            "num_envs": (declared.get("num_envs"), getattr(unwrapped, "num_envs", None)),
            "sim_dt": (declared.get("sim_dt"), getattr(getattr(unwrapped.cfg, "sim", None), "dt", None)),
            "control_dt": (declared.get("control_dt"), getattr(unwrapped, "step_dt", None)),
            "seed": (declared.get("seed"), getattr(unwrapped.cfg, "seed", None)),
            "params_version": (
                declared.get("recipe", {}).get("params_version"),
                getattr(unwrapped.cfg, "params_version", None),
            ),
        }
        mismatches = [
            f"{name}: declared {before!r} != actual {after!r}" for name, (before, after) in checks.items() if before != after
        ]
        stage = {
            "at": _now(),
            "env_cfg_digest": cs.digest(cs.snapshot(unwrapped.cfg)),
            "obs_group_dims": {
                name: list(dims) for name, dims in getattr(unwrapped.observation_manager, "group_obs_dim", {}).items()
            },
            "checked": {name: list(pair) for name, pair in checks.items()},
        }
        ctx.manifest.setdefault("stages", {})["env_constructed"] = stage
        ctx.flush()
        for mismatch in mismatches:
            ctx.fail(f"env construction disagreed with the declaration -- {mismatch}")
        if not mismatches:
            print(f"[run-manifest] {ctx.run_id}: env built as declared (obs groups {list(stage['obs_group_dims'])})")
    except Exception as err:  # noqa: BLE001
        ctx.fail(f"env_constructed recording failed: {type(err).__name__}: {err}")


def _state_digest(runner) -> str | None:
    """Digest of the policy payload about to be saved (not the file it lands in)."""
    try:
        state = runner.alg.policy.state_dict()
    except Exception:  # noqa: BLE001
        return None
    digest = hashlib.sha256()
    for key in sorted(state):
        digest.update(key.encode("utf-8"))
        tensor = state[key]
        try:
            digest.update(tensor.detach().cpu().numpy().tobytes())
        except AttributeError:
            digest.update(str(tensor).encode("utf-8"))
    return digest.hexdigest()


def _effective_lr(runner) -> float | None:
    """Learning rate the optimizer will actually use (post-restore, post-CLI)."""
    try:
        return runner.alg.optimizer.param_groups[0]["lr"]
    except Exception:  # noqa: BLE001
        return None


def _declared_lr(agent_cfg) -> float | None:
    """Learning rate the recipe asks for; the gap to the effective one is a fact, not a bug."""
    try:
        return agent_cfg.algorithm.learning_rate
    except Exception:  # noqa: BLE001
        return None


def _curriculum_state_evidence(env) -> dict:
    """Evidence that the curriculum state was actually restored, not just intended.

    A module that cannot be imported is recorded as unavailable rather than taking the
    whole T1 record down with it: the run's conditions are still worth freezing, and an
    unimportable state module is itself a finding the record has to carry.
    """
    if importlib.util.find_spec("rl_exp.tasks.curriculum_state") is None:
        return {"module_present": False, "detail": "rl_exp.tasks.curriculum_state is not importable"}
    try:
        from rl_exp.tasks import curriculum_state as cstate
    except Exception as err:  # noqa: BLE001 - record the gap, do not lose the record
        return {"module_present": True, "import_error": f"{type(err).__name__}: {err}"}

    unwrapped = getattr(env, "unwrapped", env)
    evidence = {
        "module_present": True,
        "state_version": getattr(cstate, "STATE_VERSION", None),
        "state_key": getattr(cstate, "STATE_KEY", None),
        "common_step_counter": int(getattr(unwrapped, "common_step_counter", -1)),
    }
    try:
        covered = cstate.covered_terms(unwrapped)
        evidence["covered_terms"] = sorted(covered) if covered else []
        evidence["uncovered_terms"] = sorted(cstate.uncovered_terms(unwrapped))
        evidence["requires_resume_state"] = bool(cstate.requires_resume_state(unwrapped))
        # the promise, the wiring and whether they reconcile: the three together are what a later
        # reader needs to tell "this run never promised continuity" from "it promised and lost it"
        evidence["expected_terms"] = cstate.expected_terms(unwrapped)
        evidence["wired_terms"] = sorted(cstate.wired_terms(unwrapped))
        evidence["declaration_problems"] = cstate.verify_declaration(unwrapped)
        # the raw declaration: the only thing readable when the module itself is missing
        evidence["declares_curriculum_state"] = bool(
            getattr(type(getattr(unwrapped, "cfg", None)), cstate.REQUIRES_CURRICULUM_STATE, False)
        )
    except Exception as err:  # noqa: BLE001 - the module is identifiable even when the env is not scannable
        evidence["terms_scan_error"] = f"{type(err).__name__}: {err}"
    return evidence


def _t1_payload(manifest: dict) -> dict:
    """The exact content the T1 digest covers: everything except the digest and the write stamp."""
    payload = {key: value for key, value in manifest.items() if key not in ("updated_at", "t1_sha256")}
    payload["failures"] = list(manifest.get("failures", []))
    return payload


def t1_digest(manifest: dict) -> str:
    """Digest of the frozen record; recomputable from the manifest alone.

    Used both when freezing and when verifying, so a hand-edited manifest cannot keep
    a digest that no longer describes it.

    Args:
        manifest: the manifest mapping (as written, or as loaded back).

    Returns:
        The SHA-256 hex digest of the serialized record.
    """
    return cs.digest(cs.snapshot(_t1_payload(manifest)))


def freeze(
    ctx: RunContext,
    *,
    runner,
    env,
    agent_cfg,
    resume_path: str | None,
    drop_curriculum_state: bool | None = None,
    curriculum_resume: dict | None = None,
    weights_only: bool | None = None,
) -> None:
    """Stage ``ready_to_learn``: the final manifest, frozen, before ``learn``.

    Called after the runner exists and the checkpoint is restored. Once this returns,
    later checkpoints reference ``ctx.t1_sha256`` -- so this is the last moment at
    which the run's conditions can still be described as unknowns.

    Args:
        ctx: the run context from :func:`begin`.
        runner: the rsl_rl runner (already loaded, never yet learning).
        env: the wrapped vec env.
        agent_cfg: the resolved agent config.
        resume_path: the checkpoint this run resumed from, if any.
        drop_curriculum_state: whether the caller asked to drop the curriculum state.
        curriculum_resume: the outcome :func:`~rl_exp.tasks.curriculum_state.apply_resume_state`
            returned -- what the restore *actually did*. Recorded verbatim: the record
            must not re-derive it from a counter or from the registry's support list.
        weights_only: deprecated alias of ``drop_curriculum_state``.
    """
    if drop_curriculum_state is not None and weights_only is not None and bool(weights_only) != bool(drop_curriculum_state):
        raise ValueError(
            f"weights_only={weights_only!r} conflicts with drop_curriculum_state="
            f"{drop_curriculum_state!r}; they are the same switch, so pass one of them"
        )
    if weights_only is not None:
        print(
            "[run-manifest] DEPRECATED: freeze(weights_only=) is now freeze(drop_curriculum_state=)"
            " (same behavior)"
        )
    drop_curriculum_state = bool(drop_curriculum_state) or bool(weights_only)
    try:
        source = pathlib.Path(resume_path) if resume_path else None
        declared_lr, effective_lr = _declared_lr(agent_cfg), _effective_lr(runner)
        stage = {
            "at": _now(),
            "env_cfg_digest": cs.digest(cs.snapshot(env.unwrapped.cfg)),
            "agent_digest": cs.digest(cs.snapshot(agent_cfg)),
            "resolved_algorithm": _class_id(getattr(runner, "alg", None)),
            "resolved_models": _resolved_models(runner),
            "learning_rate": {
                "declared_by_recipe": declared_lr,
                "effective": effective_lr,
                "agrees": declared_lr == effective_lr,
                "source": (
                    "recipe"
                    if declared_lr == effective_lr
                    else "checkpoint optimizer state overrode the recipe (resume)"
                    if source is not None
                    else "not the recipe value, and no checkpoint was loaded"
                ),
            },
            "iteration": getattr(runner, "current_learning_iteration", None),
            "obs_group_dims": {
                name: list(dims) for name, dims in getattr(env.unwrapped.observation_manager, "group_obs_dim", {}).items()
            },
            "obs_groups": getattr(agent_cfg, "obs_groups", None),
            "empirical_normalization": getattr(agent_cfg, "empirical_normalization", None),
            "term_classes": _term_classes(env),
            # S09 (ARCH_PLAN 1.3): the *actual* distributed flags, next to the launch-time
            # declaration in T0. Non-zero ranks neither restore nor save curriculum state
            # (it belongs to rank 0's envs), so multi-GPU resume is recorded as unverified.
            "distributed": {
                "launch": _distributed(),
                "runner_is_distributed": bool(getattr(runner, "is_distributed", False)),
                "runner_gpu_global_rank": getattr(runner, "gpu_global_rank", None),
                "multi_gpu_resume_verified": False,
            },
            "resume": {
                "resumed": source is not None,
                "drop_curriculum_state": drop_curriculum_state,
                "source": cs.relativize(str(source)) if source else None,
                "source_sha256": prov.sha256_file(source) if source else None,
                "loaded_iteration": getattr(runner, "current_learning_iteration", None),
                # what the restore did (from apply_resume_state), not what it could have done
                "curriculum_state": (
                    dict(curriculum_resume) if curriculum_resume is not None else {"status": "fresh_run"}
                ),
                "curriculum_module": _curriculum_state_evidence(env),
            },
            "code": prov.code_sources(),
        }
        ctx.manifest.setdefault("stages", {})["ready_to_learn"] = stage
        ctx.manifest["failures"] = list(ctx.failures)
        # frozen digest of the record itself; the manifest is never asked to contain it
        ctx.manifest["t1_sha256"] = t1_digest(ctx.manifest)
        ctx.t1_sha256 = ctx.manifest["t1_sha256"]
        ctx.frozen = True
        ctx.flush()
        print(f"[run-manifest] {ctx.run_id}: T1 frozen sha256={ctx.t1_sha256[:16]} iter={stage['iteration']}")
    except Exception as err:  # noqa: BLE001
        ctx.fail(f"ready_to_learn recording failed: {type(err).__name__}: {err}")


def _class_id(obj) -> str | None:
    if obj is None:
        return None
    cls = type(obj)
    return f"{cls.__module__}:{cls.__qualname__}"


def _resolved_models(runner) -> dict:
    """The model objects the runner actually built, keyed by where they live.

    Which attribute holds the network differs between rsl_rl versions and recipes (a
    combined ``policy`` in some, split ``actor``/``critic`` in others), so every holder
    is scanned and the attribute name is part of the key -- the record says where the
    class came from, not just that something was there.
    """
    out: dict[str, str | None] = {}
    for holder_name, holder in (("alg", getattr(runner, "alg", None)), ("runner", runner)):
        if holder is None:
            continue
        for attr in ("policy", "actor", "critic", "actor_critic", "model"):
            obj = getattr(holder, attr, None)
            if obj is not None and hasattr(obj, "state_dict"):
                out[f"{holder_name}.{attr}"] = _class_id(obj)
    return out


def hook_runner_save(runner, ctx: RunContext) -> None:
    """Make every checkpoint name the frozen manifest, and index its file hash outside.

    Must be installed *after* any other save wrapper (it hashes the written file, so
    it has to run outermost). Rank 0 only: a checkpoint written by another rank would
    claim a manifest the rank never verified.

    Args:
        runner: the rsl_rl runner whose ``save`` gets wrapped.
        ctx: the run context.
    """
    if getattr(runner, "is_distributed", False) and getattr(runner, "gpu_global_rank", 0) != 0:
        return

    original = runner.save

    def save_with_manifest(path, infos=None, *args, **kwargs):
        status = "ready_to_learn" if ctx.frozen else "incomplete"
        payload = {
            "run_id": ctx.run_id,
            "status": status,
            "iteration": getattr(runner, "current_learning_iteration", None),
            "t1_sha256": ctx.t1_sha256,
            "model_payload_sha256": _state_digest(runner),
        }
        if status != "ready_to_learn":
            payload["reason"] = ctx.failures[-1] if ctx.failures else "T1 never froze"
        out = original(path, {**(infos or {}), CKPT_INFOS_KEY: payload}, *args, **kwargs)
        _index_checkpoint(ctx, pathlib.Path(str(path)), payload)
        return out

    runner.save = save_with_manifest


def _index_checkpoint(ctx: RunContext, path: pathlib.Path, payload: dict) -> None:
    """Append the checkpoint's own file hash to the external index (never into T1)."""
    try:
        index = json.loads(ctx.index_path.read_text(encoding="utf-8")) if ctx.index_path.is_file() else {}
        file_digest = prov.sha256_file(path)
        index[path.name] = {
            "sha256": file_digest,
            "size": path.stat().st_size if path.exists() else None,
            "iteration": payload.get("iteration"),
            "t1_sha256": payload.get("t1_sha256"),
            "status": payload.get("status"),
            "written_at": _now(),
        }
        index["run_id"] = ctx.run_id
        _atomic_write(ctx.index_path, json.dumps(index, indent=1, ensure_ascii=False))
    except Exception as err:  # noqa: BLE001
        print(f"[run-manifest] checkpoint index update failed: {type(err).__name__}: {err}")


# ---------------------------------------------------------------------------------
# Verification: the offline half. Every row is (evidence level, result, detail).
# ---------------------------------------------------------------------------------


def _row(level: str, result: str, detail: str, required: bool = True) -> dict:
    """One check. ``required`` marks a claim the run's integrity depends on.

    An unknown on a required row is not a failure -- but it is also not a pass, so the
    caller cannot report the run as verified (ARCH_PLAN hard constraint 1). Rows that
    are honestly not attempted yet (the isolation rebuild of 1.5) are not required, so
    they do not hold a record back either.
    """
    assert level in EVIDENCE_LEVELS, level
    assert result in RESULTS, result
    return {"level": level, "result": result, "detail": detail, "required": required}


def verify(run_dir: pathlib.Path) -> tuple[list[dict], list[str]]:
    """Check a recorded run: what it proves, what it fails, and what cannot be checked.

    Args:
        run_dir: the run directory holding ``run_manifest.json``.

    Returns:
        ``(rows, problems)`` where each row is one check with its evidence level and
        result, and ``problems`` lists the failures that block acceptance.
    """
    rows: list[dict] = []
    problems: list[str] = []
    manifest_path = run_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        rows.append(_row("记录完整", "失败", f"{MANIFEST_NAME} missing in {cs.relativize(str(run_dir))}"))
        return rows, [f"{run_dir}: no manifest"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stages = manifest.get("stages", {})
    missing = [stage for stage in STAGES if stage not in stages]
    if missing:
        rows.append(_row("记录完整", "失败", f"stages missing: {missing} (run never reached T1?)"))
        problems.append(f"{run_dir}: incomplete record, missing {missing}")
    elif manifest.get("failures"):
        rows.append(_row("记录完整", "失败", f"recorded failures: {manifest['failures'][-1]}"))
        problems.append(f"{run_dir}: {manifest['failures'][-1]}")
    else:
        rows.append(_row("记录完整", "通过", f"T0/T1 present, T1 sha256={str(manifest.get('t1_sha256'))[:16]}"))
    if manifest.get("run_manifest_format") != FORMAT_VERSION:
        problems.append(f"{run_dir}: manifest format {manifest.get('run_manifest_format')} != {FORMAT_VERSION}")

    rows.extend(_verify_self_consistency(manifest, problems))
    rows.extend(_verify_lifecycle(manifest, problems))
    rows.extend(_verify_code(manifest, problems))
    rows.extend(_verify_assets(manifest, problems))
    rows.extend(_verify_recipe(manifest, problems))
    rows.extend(_verify_curriculum_state(manifest, problems))
    rows.extend(_verify_payload(run_dir, manifest, problems))
    rows.append(
        _row(
            "已验证重建",
            "未知",
            "isolation rebuild is ARCH_PLAN 1.5: no rebuild record, so nothing is claimed here",
            required=False,
        )
    )
    return rows, problems


def _verify_self_consistency(manifest: dict, problems: list[str]) -> list[dict]:
    """Do not take the recorder's own conclusions on trust: re-derive them from its record.

    Two things are checked here. The T1 digest must still describe the manifest it sits
    in (so a hand-edited record cannot keep a matching digest), and the declared/actual
    pairs captured at construction must actually agree (so a mismatch cannot be
    neutralised by editing either side afterwards, or by a recorder that forgot to
    report it).
    """
    rows: list[dict] = []
    recorded = manifest.get("t1_sha256")
    if not recorded:
        return [_row("记录完整", "未知", "no T1 digest to recheck (run never froze)")]
    if t1_digest(manifest) != recorded:
        problems.append("record: T1 digest does not describe the manifest it lives in")
        rows.append(_row("记录完整", "失败", "T1 digest mismatch: the record was edited after freezing"))
    else:
        rows.append(_row("记录完整", "通过", f"T1 digest re-derived from the record ({str(recorded)[:16]})"))

    checked = manifest.get("stages", {}).get("env_constructed", {}).get("checked", {})
    disagreements = [
        f"{name}: declared {pair[0]!r} != actual {pair[1]!r}"
        for name, pair in checked.items()
        if isinstance(pair, list) and len(pair) == 2 and pair[0] != pair[1]
    ]
    if disagreements:
        problems.append(f"record: declared/actual disagree -- {disagreements[:2]}")
        rows.append(_row("记录完整", "失败", f"construction disagreement in the record: {disagreements[:2]}"))
    else:
        rows.append(_row("记录完整", "通过", f"declared/actual agree on {len(checked)} field(s)"))
    return rows


def _verify_lifecycle(manifest: dict, problems: list[str]) -> list[dict]:
    """Was this launch permitted by the directory, and does the record still say so?

    The live directory is re-read only to *compare* with what was recorded: a launch that the
    directory has since moved past is reported as such, never re-judged (hard constraint 6 --
    the record is what was true when the run started, not what today's layout would allow) and
    never silently upgraded to a pass. The recorded verdict itself is under the T1 digest, so it
    cannot be edited into a permission after the fact.
    """
    recorded = (manifest.get("declaration") or {}).get("lifecycle")
    if not recorded:
        return [
            _row(
                "记录完整",
                "未知",
                "no lifecycle verdict recorded: this launch predates the gate, so nothing is claimed",
            )
        ]
    if recorded.get("allowed") is not True:
        problems.append(f"lifecycle: the launch was refused ({recorded.get('reason')})")
        return [_row("记录完整", "失败", f"lifecycle refused the launch: {recorded.get('reason')}")]
    if recorded.get("status") not in recipe_lifecycle.STATUSES:
        problems.append(f"lifecycle: recorded status {recorded.get('status')!r} is not a status")
        return [_row("记录完整", "失败", f"lifecycle recorded status {recorded.get('status')!r}")]
    live = lifecycle_gate.read_index()
    if live.get("digests") == recorded.get("directory_sha256"):
        return [
            _row(
                "记录完整",
                "通过",
                f"line {recorded.get('line')} was {recorded.get('status')} at revision"
                f" {recorded.get('directory_revision')}, and the directory has not changed since",
            )
        ]
    return [
        _row(
            "记录完整",
            "未知",
            "the recipe directory has changed since this launch: the recorded verdict stands as"
            " what this run was started under, and today's directory is not re-applied to it",
            required=False,
        )
    ]


def _verify_code(manifest: dict, problems: list[str]) -> list[dict]:
    """Can the code that ran be reached again, and did it move since?

    A moved revision is not a failure: the record names the revision, so the code is
    reachable (``git checkout <rev>``). What *is* a problem is a run whose code included
    uncommitted changes: the record hashes the diff but does not contain it, so nothing
    can bring that code back -- which is exactly the archive gap (PLAN.md #18).
    """
    recorded = manifest.get("code", {})
    fresh = prov.code_sources()
    rows: list[dict] = []
    for name in ("repository", "isaaclab", "rsl_rl"):
        before, after = recorded.get(name, {}), fresh.get(name, {})
        if not before.get("available"):
            rows.append(_row("可重建", "未知", f"{name}: not recorded ({before.get('detail', 'no detail')})"))
            continue
        if before.get("mode") == "installed":
            rows.append(
                _row("可重建", "未知", f"{name}: installed distribution {before.get('distribution_version')}, source not pinned")
            )
            continue
        moved = before.get("rev") != after.get("rev")
        diff_moved = before.get("diff_sha256") != after.get("diff_sha256")
        dirty_then = before.get("dirty")
        code_in_untracked = before.get("untracked_in_code_root") or []
        outside = len(before.get("untracked_outside_code_root") or [])
        ignored = f" ({outside} untracked file(s) outside the code root ignored)" if outside else ""
        if dirty_then and code_in_untracked:
            rows.append(
                _row(
                    "可重建",
                    "未知",
                    f"{name}: the run had {len(code_in_untracked)} untracked code file(s) "
                    f"(e.g. {code_in_untracked[:2]}); this record hashes them and stops there -- whether the "
                    f"content was kept is asserted by the 1.5 drill material (rebuild --capture --archive), "
                    f"not by the run record (PLAN.md #18).{ignored}",
                )
            )
        elif dirty_then and diff_moved:
            rows.append(
                _row(
                    "可重建",
                    "未知",
                    f"{name}: the run worked in a dirty tree and that diff no longer matches "
                    f"(recorded {str(before.get('diff_sha256'))[:8]} -> {str(after.get('diff_sha256'))[:8]}); "
                    f"uncommitted code is hashed, not stored here -- the 1.5 drill material is where that is "
                    f"asserted (PLAN.md #18).{ignored}",
                )
            )
        elif moved:
            rows.append(
                _row(
                    "可重建",
                    "通过",
                    f"{name}: recorded at {before.get('rev')}, tree has since moved to {after.get('rev')}; "
                    f"the run's code is reachable at the recorded revision"
                    + ("" if not dirty_then else " (recorded as a dirty tree; see the diff digest)")
                    + ignored,
                )
            )
        else:
            rows.append(
                _row(
                    "可重建",
                    "通过",
                    f"{name}: rev {before.get('rev')} and its diff digest match"
                    + ("" if not dirty_then else f" (dirty tree at record time: {before.get('diff_lines')} diff lines)")
                    + ignored,
                )
            )
    return rows


def _verify_assets(manifest: dict, problems: list[str]) -> list[dict]:
    recorded = manifest.get("declaration", {}).get("assets", {})
    lock = recorded.get("lock")
    if not lock:
        return [_row("可重建", "未知", f"assets: {recorded.get('detail', 'no lock recorded')}")]
    declared_recipe = manifest.get("declaration", {}).get("recipe", {})
    fresh = asset_digest(declared_recipe.get("params_version"), declared_recipe.get("params_line"))
    if fresh.get("manifest_sha256") != recorded.get("manifest_sha256"):
        problems.append("assets: content differs from the recorded lock")
        return [
            _row(
                "可重建",
                "失败",
                f"assets: {fresh.get('missing_or_changed', [])[:3]} "
                f"(recorded {recorded.get('file_count')} files)",
            )
        ]
    return [
        _row(
            "可重建",
            "通过",
            f"assets: {recorded.get('file_count')} locked file(s) match ({recorded.get('closure')})",
        )
    ]


def _verify_recipe(manifest: dict, problems: list[str]) -> list[dict]:
    """Did the reviewed recipe for this task move since the run?

    The check is against the *recipe*, re-derived the same way the golden lock builds it
    (registry class, no session overrides). Comparing the lock's digest with the run's own
    digest would be wrong by construction: the run's config carries ``--num_envs``, seed,
    device and log dir, and those are session facts, not recipe drift.
    """
    declaration = manifest.get("declaration", {})
    task = manifest.get("task")
    recipe = declaration.get("recipe", {})
    if not recipe.get("recipe_digest"):
        return [_row("可重建", "未知", "recipe: no digest recorded")]
    overrides = recipe.get("session_override_count")
    note = f"; {overrides} field(s) differ from the recipe defaults (session overrides)" if overrides else ""
    try:
        import rl_exp.tasks  # noqa: F401 - registers the tasks
        from rl_exp.tools.verify.check_cfg_lock import build_entry, registered_tasks

        spec = registered_tasks().get(task)
        fresh = build_entry(task, spec)["digest"] if spec else None
    except Exception as err:  # noqa: BLE001
        return [_row("可重建", "未知", f"recipe: could not re-derive ({type(err).__name__}: {err})")]
    if fresh is None:
        return [_row("可重建", "未知", f"recipe: task {task} is no longer registered")]
    recorded = recipe.get("golden_digest")
    if recorded is None:
        return [_row("可重建", "未知", f"recipe: the run recorded no golden digest (no lock in that tree){note}")]
    # A golden can move for two very different reasons, and the record must not confuse
    # them: the recipe itself changed (a real failure -- the run's conditions are gone),
    # or the baseline was taken under another framework combination or another snapshot
    # format (no comparison is possible, so the claim is unknown, not failed).
    from rl_exp.tools.verify.check_cfg_lock import combination, combination_key

    current_combination = combination_key(combination())
    recorded_combination = recipe.get("golden_combination")
    if recorded_combination and recorded_combination != current_combination:
        return [
            _row(
                "可重建",
                "未知",
                f"recipe: the run's baseline belongs to another framework combination "
                f"({recorded_combination}); this tree is {current_combination}{note}",
            )
        ]
    current_format = cs.FORMAT_VERSION
    recorded_format = recipe.get("golden_snapshot_format")
    if fresh == recorded:
        return [_row("可重建", "通过", f"recipe: reviewed golden unchanged ({str(fresh)[:12]}){note}")]
    if recorded_format is None:
        return [
            _row(
                "可重建",
                "未知",
                f"recipe: the record predates the snapshot-format tag, so a difference "
                f"({str(recorded)[:12]} -> {str(fresh)[:12]}) cannot be attributed to the recipe or to the "
                f"snapshot semantics{note}",
            )
        ]
    if recorded_format != current_format:
        return [
            _row(
                "可重建",
                "未知",
                f"recipe: snapshot semantics changed since the run (format {recorded_format} -> "
                f"{current_format}), so the recorded golden digest is not comparable{note}",
            )
        ]
    problems.append("recipe: the reviewed recipe for this task has changed since the run")
    return [
        _row(
            "可重建",
            "失败",
            f"recipe: reviewed golden moved ({str(recorded)[:12]} -> {str(fresh)[:12]}){note}",
        )
    ]


def _verify_payload(run_dir: pathlib.Path, manifest: dict, problems: list[str]) -> list[dict]:
    index_path = run_dir / INDEX_NAME
    if not index_path.is_file():
        return [_row("可重建", "未知", f"checkpoints: no {INDEX_NAME} (no checkpoint saved yet?)")]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    incomplete = [name for name, entry in index.items() if isinstance(entry, dict) and entry.get("status") != "ready_to_learn"]
    if incomplete:
        problems.append(f"checkpoints: {len(incomplete)} written before T1 froze: {incomplete[:3]}")
    bad = []
    for name, entry in index.items():
        if not isinstance(entry, dict):
            continue
        digest = prov.sha256_file(run_dir / name)
        if digest is None:
            bad.append(f"{name}: missing")
        elif digest != entry.get("sha256"):
            bad.append(f"{name}: content changed")
    if bad:
        problems.append(f"checkpoints: {bad[:3]}")
        return [_row("可重建", "失败", f"checkpoints: {bad[:3]}")]
    return [
        _row(
            "可重建",
            "通过" if not incomplete else "未知",
            f"checkpoints: {len([k for k, v in index.items() if isinstance(v, dict)])} file(s) match; "
            f"payload contents not read (tensor digests live inside the checkpoint's infos)",
        )
    ]


def _verify_curriculum_state(manifest: dict, problems: list[str]) -> list[dict]:
    """S10 (ARCH_PLAN 1.3): did the curriculum state carry over, and is that *recorded*?

    The row reads the outcome ``apply_resume_state`` returned, not the registry's
    support list and not the counter: a task that could restore something, or an env
    whose counter happens to be non-zero, is not evidence that a restore happened.
    """
    stage = manifest.get("stages", {}).get("ready_to_learn", {})
    resume = stage.get("resume") or {}
    outcome = resume.get("curriculum_state") or {}
    status = outcome.get("status")
    coverage = resume.get("curriculum_module") or {}
    declared = bool(coverage.get("declares_curriculum_state"))

    if status == "fresh_run":
        return [_row("记录完整", "通过", "curriculum: fresh run, no resume to restore")]

    terms = ", ".join(sorted(t.get("name", "?") for t in outcome.get("terms") or [])) or "none"
    detail = (
        f"curriculum: status={status} source_version={outcome.get('source_version')} terms=[{terms}]"
        f" c_k={outcome.get('c_k')} counter={outcome.get('common_step_counter')} rank={outcome.get('rank')}"
    )
    if status == "restored":
        missing = outcome.get("missing_evidence") or []
        if outcome.get("evidence") == "complete" and not missing:
            return [_row("记录完整", "通过", detail)]
        # loadable, deliberately not declared complete: the missing witnesses are listed
        return [_row("记录完整", "未知", f"{detail} missing_evidence={missing}")]
    if status == "dropped":
        return [_row("记录完整", "未知", f"{detail} (explicitly dropped: the curriculum cold-starts)", False)]
    if outcome.get("notes"):
        detail = f"{detail} notes={outcome['notes']}"
    if status == "module_unavailable" or (declared and status in (None, "no_state", "rank_skipped")):
        problems.append(f"curriculum state required but not restored ({status})")
    return [_row("记录完整", "未知", detail)]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--verify" not in args:
        print(__doc__.splitlines()[0])
        print("usage: python -m rl_exp.tools.runrecord.manifest --verify <run_dir>")
        return 2
    target = pathlib.Path(args[args.index("--verify") + 1])
    rows, problems = verify(target)
    print(f"  run: {cs.relativize(str(target))}")
    for row in rows:
        mark = "" if row["required"] else " (not required yet)"
        print(f"  [{row['level']}] {row['result']}: {row['detail']}{mark}")
    unknown = [row for row in rows if row["result"] == "未知" and row["required"]]
    print(
        f"  evidence levels: pass={sum(r['result'] == '通过' for r in rows)} "
        f"fail={sum(r['result'] == '失败' for r in rows)} unknown={sum(r['result'] == '未知' for r in rows)} "
        f"(of which required-and-unknown: {len(unknown)})"
    )
    if problems:
        for problem in problems:
            print(f"  BLOCKING: {problem}")
        print(f"RUN_MANIFEST_DRIFT ({len(problems)})")
        return 1
    if unknown:
        for row in unknown:
            print(f"  NOT CLAIMED: {row['detail']}")
        print(f"RUN_MANIFEST_PARTIAL ({len(unknown)} required claim(s) unknown)")
        return 2
    print("RUN_MANIFEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
