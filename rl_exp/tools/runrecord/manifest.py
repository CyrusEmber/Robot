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
import subprocess
import sys
from datetime import datetime

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.verify import cfg_snapshot as cs  # noqa: E402

FORMAT_VERSION = 1
MANIFEST_NAME = "run_manifest.json"
INDEX_NAME = "checkpoints.json"
CKPT_INFOS_KEY = "run_manifest"
STAGES = ("pre_make", "env_constructed", "ready_to_learn")

EVIDENCE_LEVELS = ("记录完整", "可重建", "已验证重建")
RESULTS = ("通过", "失败", "未知")

_UNTRACKED_CAP = 40


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: pathlib.Path, chunk: int = 1 << 20) -> str | None:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(chunk), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def _atomic_write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _git(root: pathlib.Path | None, *args: str) -> str:
    if root is None:
        return ""
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, cwd=root
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def git_state(root: pathlib.Path | None, label: str) -> dict:
    """Provenance of one git work tree: revision, dirty state, diffs, untracked files.

    Untracked files are the honest weak spot: a hash of the tree cannot bring them
    back, so they are listed by name and flagged as needing archiving.

    Args:
        root: the work tree root, or None when it could not be resolved.
        label: human label used in the ``resolved`` flag ("repository" / "isaaclab").

    Returns:
        The record for this tree; ``available: False`` when git could not answer.
    """
    if root is None:
        return {"available": False, "detail": f"{label} root unresolved"}
    rev = _git(root, "rev-parse", "HEAD")
    if not rev:
        return {"available": False, "detail": f"{root} is not a git work tree"}
    porcelain = _git(root, "status", "--porcelain=v2")
    status_lines = porcelain.splitlines()
    untracked = sorted(line.split(" ", 1)[1] for line in status_lines if line.startswith("? "))
    diff = _git(root, "diff", "HEAD")
    return {
        "available": True,
        "root": cs.relativize(str(root)),
        "rev": rev[:12],
        "dirty": bool(status_lines),
        "status_porcelain_sha256": _sha256_bytes(porcelain.encode("utf-8")),
        "diff_sha256": _sha256_bytes(diff.encode("utf-8")),
        "diff_lines": len(diff.splitlines()),
        "untracked_count": len(untracked),
        "untracked": untracked[:_UNTRACKED_CAP],
        "untracked_requires_archive": bool(untracked),
    }


def rsl_rl_state() -> dict:
    """Provenance of rsl_rl: source tree when editable, distribution version when installed."""
    try:
        spec = importlib.util.find_spec("rsl_rl")
    except (ImportError, ValueError):
        spec = None
    origin = getattr(spec, "origin", None) if spec is not None else None
    if origin:
        package_dir = pathlib.Path(origin).resolve().parent
        tree = _git(package_dir, "rev-parse", "--show-toplevel")
        if tree:
            state = git_state(pathlib.Path(tree), "rsl_rl")
            state["mode"] = "editable/source"
            return state
    try:
        from importlib.metadata import version

        return {"available": True, "mode": "installed", "distribution_version": version("rsl_rl")}
    except Exception as err:  # noqa: BLE001 - record the gap, never crash a run
        return {"available": False, "detail": f"{type(err).__name__}: {err}"}


def code_sources() -> dict:
    """All code the run depends on, recorded from what is actually importable."""
    isaac = os.environ.get("RL_ISAAC_ROOT")
    if not isaac:
        try:
            from ablation_harness.host_paths import isaac_root

            resolved = isaac_root()
            isaac = str(resolved) if resolved else None
        except Exception:  # noqa: BLE001
            isaac = None
    return {
        "repository": git_state(_REPO, "repository"),
        "isaaclab": git_state(pathlib.Path(isaac) if isaac else None, "isaaclab"),
        "rsl_rl": rsl_rl_state(),
    }


def asset_digest(params_version: str | None) -> dict:
    """Digest of the frozen asset lock (an allow-list, not a dependency closure).

    The paths listed by the lock are resolved relative to ``rl_exp`` (that is how the
    lock is written) and hashed now; a listed file that is missing is reported, since
    a lock whose files are gone proves nothing.

    Args:
        params_version: the recipe version whose lock applies, or None for the live
            development recipe (which has no lock).

    Returns:
        The asset reference: lock path, lock hash, per-file hash map digest, and the
        list of files that could not be read.
    """
    if not params_version:
        return {"lock": None, "detail": "live development recipe: no frozen asset lock"}
    candidates = sorted(_REPO.glob(f"rl_exp/versions/lizard/**/{params_version}/asset_lock.json"))
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
        digest = _sha256_file(_REPO / "rl_exp" / rel)
        if digest is None:
            missing.append(rel)
            continue
        if digest != recorded:
            missing.append(f"{rel} (content changed: {digest[:12]} != {recorded[:12]})")
        hashes[rel] = digest
    return {
        "lock": cs.relativize(str(lock_path)),
        "lock_sha256": _sha256_file(lock_path),
        "file_count": len(files),
        "manifest_sha256": _sha256_bytes(
            json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "missing_or_changed": missing,
        "closure": "allow-list only (USD dependency closure not implemented)",
    }


def recipe_ref(env_cfg) -> dict:
    """The recipe this run declares, plus whether it still matches the committed golden."""
    snapshot = cs.snapshot(env_cfg)
    version = getattr(env_cfg, "params_version", None)
    ref = {
        "params_version": version if isinstance(version, str) else None,
        "recipe_digest": cs.digest(snapshot),
        "obs_layout_digest": cs.digest(snapshot.get("observations", {})),
        "note": "obs_layout_digest stands in for the protocol object (ARCH_PLAN Step 3)",
    }
    lock_path = _REPO / "rl_exp" / "versions" / "lizard" / "cfg_lock.json"
    if not lock_path.is_file():
        ref["golden"] = "no golden lock in this tree"
        return ref
    try:
        entries = json.loads(lock_path.read_text(encoding="utf-8")).get("entries", {})
    except (OSError, json.JSONDecodeError) as err:
        ref["golden"] = f"golden lock unreadable: {err}"
        return ref
    entry = next((e for e in entries.values() if e.get("env_cfg_class", "").endswith(type(env_cfg).__name__)), None)
    ref["golden_digest"] = entry.get("digest") if entry else None
    ref["golden_task"] = next((k for k, e in entries.items() if e is entry), None) if entry else None
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
    try:
        ctx.manifest = {
            "run_manifest_format": FORMAT_VERSION,
            "run_id": ctx.run_id,
            "task": task,
            "argv": argv,
            "log_dir": cs.relativize(str(ctx.log_dir)),
            "started_at": _now(),
            "code": code_sources(),
        }
        version = getattr(env_cfg, "params_version", None)
        assets = asset_digest(version if isinstance(version, str) else None)
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
    return ctx


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


def _curriculum_state_evidence(env) -> dict:
    """Evidence that the curriculum state was actually restored, not just intended."""
    evidence: dict = {"module_present": importlib.util.find_spec("rl_exp.tasks.curriculum_state") is not None}
    if not evidence["module_present"]:
        return evidence
    from rl_exp.tasks import curriculum_state as cstate

    evidence["state_version"] = getattr(cstate, "STATE_VERSION", None)
    evidence["state_key"] = getattr(cstate, "STATE_KEY", None)
    evidence["common_step_counter"] = int(getattr(env.unwrapped, "common_step_counter", -1))
    evidence["covered_terms"] = sorted(getattr(cstate, "_CFG_KEYS", {}) or [])
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
    weights_only: bool = False,
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
        weights_only: whether the caller asked to drop the curriculum state.
    """
    try:
        source = pathlib.Path(resume_path) if resume_path else None
        stage = {
            "at": _now(),
            "env_cfg_digest": cs.digest(cs.snapshot(env.unwrapped.cfg)),
            "agent_digest": cs.digest(cs.snapshot(agent_cfg)),
            "resolved_algorithm": _class_id(getattr(runner, "alg", None)),
            "resolved_policy": _class_id(getattr(getattr(runner, "alg", None), "policy", None)),
            "effective_lr": _effective_lr(runner),
            "iteration": getattr(runner, "current_learning_iteration", None),
            "obs_group_dims": {
                name: list(dims) for name, dims in getattr(env.unwrapped.observation_manager, "group_obs_dim", {}).items()
            },
            "obs_groups": getattr(agent_cfg, "obs_groups", None),
            "empirical_normalization": getattr(agent_cfg, "empirical_normalization", None),
            "term_classes": _term_classes(env),
            "resume": {
                "requested": weights_only,
                "source": cs.relativize(str(source)) if source else None,
                "source_sha256": _sha256_file(source) if source else None,
                "loaded_iteration": getattr(runner, "current_learning_iteration", None),
                "curriculum_state": _curriculum_state_evidence(env),
            },
            "code": code_sources(),
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
        file_digest = _sha256_file(path)
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


def _row(level: str, result: str, detail: str) -> dict:
    assert level in EVIDENCE_LEVELS, level
    assert result in RESULTS, result
    return {"level": level, "result": result, "detail": detail}


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
    rows.extend(_verify_code(manifest, problems))
    rows.extend(_verify_assets(manifest, problems))
    rows.extend(_verify_recipe(manifest, problems))
    rows.extend(_verify_payload(run_dir, manifest, problems))
    rows.append(
        _row(
            "已验证重建",
            "未知",
            "isolation rebuild is ARCH_PLAN 1.5: no rebuild record, so nothing is claimed here",
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


def _verify_code(manifest: dict, problems: list[str]) -> list[dict]:
    recorded = manifest.get("code", {})
    fresh = code_sources()
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
        if before.get("rev") != after.get("rev") or before.get("diff_sha256") != after.get("diff_sha256"):
            rows.append(
                _row("可重建", "失败", f"{name}: rev/diff moved ({before.get('rev')} -> {after.get('rev')})")
            )
            problems.append(f"{name}: code changed since the run")
        elif before.get("untracked_requires_archive"):
            rows.append(
                _row(
                    "可重建",
                    "未知",
                    f"{name}: rev matched; {before.get('untracked_count')} untracked file(s) present then "
                    f"(archived? {before.get('untracked', [])[:3]})",
                )
            )
        else:
            rows.append(_row("可重建", "通过", f"{name}: rev {before.get('rev')} and diff digest match"))
    return rows


def _verify_assets(manifest: dict, problems: list[str]) -> list[dict]:
    recorded = manifest.get("declaration", {}).get("assets", {})
    lock = recorded.get("lock")
    if not lock:
        return [_row("可重建", "未知", f"assets: {recorded.get('detail', 'no lock recorded')}")]
    fresh = asset_digest(manifest.get("declaration", {}).get("recipe", {}).get("params_version"))
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
    declaration = manifest.get("declaration", {})
    task = manifest.get("task")
    recorded = declaration.get("recipe", {}).get("recipe_digest")
    if not recorded:
        return [_row("可重建", "未知", "recipe: no digest recorded")]
    try:
        from gymnasium.envs.registration import registry

        import rl_exp.tasks  # noqa: F401

        spec = registry.get(task)
        env_cfg = spec.kwargs["env_cfg_entry_point"] if spec else None
        if env_cfg is None:
            return [_row("可重建", "未知", f"recipe: task {task} no longer registered")]
        from rl_exp.tools.verify.check_cfg_lock import resolve_entry

        fresh = cs.digest(cs.snapshot(resolve_entry(env_cfg)()))
    except Exception as err:  # noqa: BLE001
        return [_row("可重建", "未知", f"recipe: could not re-derive ({type(err).__name__}: {err})")]
    if fresh != recorded:
        problems.append("recipe: re-derived digest differs from the run's record")
        return [_row("可重建", "失败", "recipe: the code no longer builds the recorded config")]
    return [_row("可重建", "通过", f"recipe: re-derived digest matches ({str(recorded)[:16]})")]


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
        digest = _sha256_file(run_dir / name)
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
        print(f"  [{row['level']}] {row['result']}: {row['detail']}")
    print(f"  evidence levels: pass={sum(r['result'] == '通过' for r in rows)} "
          f"fail={sum(r['result'] == '失败' for r in rows)} unknown={sum(r['result'] == '未知' for r in rows)}")
    if problems:
        for problem in problems:
            print(f"  BLOCKING: {problem}")
        print(f"RUN_MANIFEST_DRIFT ({len(problems)})")
        return 1
    print("RUN_MANIFEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
