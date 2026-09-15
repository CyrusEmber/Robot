# -*- coding: utf-8 -*-
"""Small-scope validation of the config snapshot serializer (ARCH_PLAN 1.1).

Scope: prove the serialization rules hold on real config trees before the golden
registry (all registered tasks) is built on top of them. Every check is written so
it can fail -- the digest checks are falsified by reordering a mapping in the
snapshot and requiring the digest to change.

Checks
------
1  order: dataclass/mapping order is preserved AND covered by the digest
2  floats: bit-exact JSON round-trip, including subnormals and -0.0; non-finite tagged
3  callables/types: stable module+qualname identity, no addresses anywhere in the text
4  missing vs None: distinguishable (outside configclass trees, see the note below)
5  paths: repo/Isaac roots relativized, external URLs untouched
6  opaque objects: real config trees hit the tag paths (slice), not dead code
7  digests: deterministic per class, discriminating across classes

Note on check 4: an *env* configclass cannot hold ``MISSING`` as a value -- the
decorator raises ``TypeError`` for a ``MISSING`` default (``configclass.py:304``)
and a field without a default cannot be instantiated. The *agent* config does:
``RslRlOnPolicyRunnerCfg`` leaves fields unset (``stochastic``, ``init_noise_std``,
``obs_groups``, ...), which the runner fills later. Those are real ``_MISSING_TYPE``
instances produced by deep-copy, so the marker must be recognised by type -- an
identity check against ``dataclasses.MISSING`` misses every one of them.
"""

import copy
import json
import os
import re
import struct
import subprocess
import sys
from dataclasses import MISSING

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")
import cfg_snapshot as cs  # noqa: E402
from rl_exp.tasks.agents.rsl_rl_ppo_cfg import LizardTeacherV14PPORunnerCfg  # noqa: E402
from rl_exp.tasks.teacher_env_cfg import (  # noqa: E402
    LizardRoughTeacherEnvCfg_V13,
    LizardRoughTeacherEnvCfg_V14,
)

PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def _packs(value: float) -> bytes:
    return struct.pack("<d", value)


_GROUP_FIELDS = {"enable_corruption", "concatenate_terms", "history_length", "flatten_history_dim", "concatenate_dim"}


def check_order(snap: dict, cfg) -> None:
    """Order is preserved from the live instance and is inside the digest.

    The extero term order is asserted against the frozen contract (the network
    reshapes ``[N, 4, 52]`` in that order; mirror of ``check_obs_layout.V3_EXTERO_ORDER``),
    so this is not a restatement of how the snapshot was built. Group-level settings
    live in the same mapping; they are not terms.
    """
    groups = snap["observations"]
    terms = [t for t in groups["extero"] if t not in _GROUP_FIELDS]
    expected = ["lf_foot_ring", "rf_foot_ring", "rl_foot_ring", "rr_foot_ring"]
    check("order/obs-groups-visible", {"proprio", "extero", "priv"} <= set(groups), f"got {sorted(groups)}")
    check("order/extero-terms", terms == expected, f"{terms} != {expected}")

    reversed_snap = json.loads(cs.canonical_json(snap))
    reversed_snap["observations"]["extero"] = dict(reversed(list(reversed_snap["observations"]["extero"].items())))
    check(
        "order/digest-covers-order",
        cs.digest(reversed_snap) != cs.digest(snap),
        "reordering a group did not change the digest: order is not part of the summary",
    )


def check_floats() -> None:
    """Floats survive JSON text exactly; non-finite values cannot ride bare."""
    awkward = [0.1, 1.0 / 3.0, 1e-320, -0.0, 1e308, 5e-324, 3.141592653589793]
    snap = cs.snapshot({"v": awkward})
    back = json.loads(cs.canonical_json(snap))["v"]
    check(
        "floats/bit-exact",
        all(_packs(a) == _packs(b) for a, b in zip(awkward, back, strict=True)),
        f"{awkward} -> {back}",
    )
    check("floats/no-fixed-digits", cs.canonical_json(cs.snapshot({"v": 0.1})) == '{"v":0.1}')
    for bad in (float("nan"), float("inf"), float("-inf")):
        tagged = cs.snapshot({"v": bad})
        ok = cs.FLOAT_TAG in tagged["v"] and cs.canonical_json(tagged).startswith('{"v":{"__float__"')
        check(f"floats/tagged-{bad!r}", ok, f"{cs.canonical_json(tagged)}")
    try:
        json.dumps({"v": float("nan")}, allow_nan=False)
        check("floats/bare-nan-illegal", False, "bare NaN serialized; the tag is not needed?")
    except ValueError:
        check("floats/bare-nan-illegal", True)


def check_identities(snap: dict) -> None:
    """Callables and types are module+qualname identities, never addresses."""
    text = cs.canonical_json(snap)
    calls = sorted(set(re.findall(r'"__callable__":"([^"]+)"', text)))
    types_ = sorted(set(re.findall(r'"__type__":"([^"]+)"', text)))
    check("identity/callables-present", len(calls) > 5, f"only {len(calls)} callables in a v14 snapshot")
    check(
        "identity/name-form",
        all(re.fullmatch(r"[\w.]+", name) for name in calls + types_),
        f"{[n for n in calls + types_ if not re.fullmatch(r'[\w.]+', n)][:3]}",
    )
    check("identity/no-address", re.search(r"at 0x[0-9a-fA-F]+", text) is None, "an object repr leaked")
    # callables that the config already carries as resolvable strings stay strings:
    # they are the stable identity already, so they must NOT be re-wrapped in a tag
    check(
        "identity/terrain-generator-class-type",
        snap["scene"]["terrain"]["terrain_generator"]["class_type"]
        == "isaaclab.terrains.terrain_generator:TerrainGenerator",
        f"{snap['scene']['terrain']['terrain_generator']['class_type']}",
    )


def check_missing_vs_none() -> None:
    """An unset record must not read as an explicit None."""
    snap = cs.snapshot({"unset": MISSING, "explicit": None})
    check(
        "missing/distinguishable",
        snap["unset"] == {cs.MISSING_TAG: True} and snap["explicit"] is None,
        f"{snap}",
    )
    # config members are deep-copied at construction, which mints NEW _MISSING_TYPE
    # instances -- so `is MISSING` is False for a field the recipe never set
    copied = copy.deepcopy(MISSING)
    check("missing/deepcopy-breaks-identity", copied is not MISSING, "deepcopy preserved the singleton?")
    check("missing/detected-by-type", cs.snapshot({"v": copied})["v"] == {cs.MISSING_TAG: True}, "identity check leaked")


def check_agent_cfg() -> None:
    """The agent cfg is where unset (MISSING) fields actually live; it must stay stable."""
    agent = cs.snapshot(LizardTeacherV14PPORunnerCfg())
    text = cs.canonical_json(agent)
    check("agent/no-address", cs.ADDRESS_RE.search(text) is None, "an object repr leaked into the agent snapshot")
    check("agent/missing-tagged", cs.MISSING_TAG in text, "unset agent fields must be tagged, not printed")
    check(
        "agent/deterministic",
        cs.digest(agent) == cs.digest(cs.snapshot(LizardTeacherV14PPORunnerCfg())),
        "two constructions of the agent cfg differ inside one process",
    )


def check_cross_process() -> None:
    """Digest stability across processes (hash seed / allocator), which in-process checks miss."""
    code = (
        "import sys;sys.path.insert(0,'.');sys.path.insert(0,'rl_exp/tools/verify');"
        "import cfg_snapshot as cs;"
        "from rl_exp.tasks.agents.rsl_rl_ppo_cfg import LizardTeacherV14PPORunnerCfg as A;"
        "print(cs.digest(cs.snapshot(A())))"
    )

    def run(seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": seed}
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(cs._REPO_ROOT), env=env
        )
        if proc.returncode != 0:
            return f"<failed: {proc.stderr.strip().splitlines()[-1] if proc.stderr else proc.returncode}>"
        return proc.stdout.strip()

    first, second = run("1"), run("99999")
    check(
        "digest/cross-process-stable",
        len({first, second}) == 1 and not first.startswith("<failed"),
        f"PYTHONHASHSEED 1 -> {first[:20]}, 99999 -> {second[:20]}",
    )


def check_paths(snap: dict) -> None:
    """Repo/Isaac paths are placeholders; external URLs pass through."""
    usd = snap["scene"]["robot"]["spawn"]["usd_path"]
    check("paths/repo-relative", usd.startswith("<REPO_ROOT>/"), f"{usd}")
    text = cs.canonical_json(snap)
    roots = [str(r) for r in (cs._REPO_ROOT, cs.ISAAC_ROOT) if r is not None]
    leaks = sorted({m for r in roots for m in re.findall(re.escape(r) + r"[\\/][^\"']*", text)})
    check("paths/no-absolute-leak", not leaks, f"{leaks[:3]}")
    check("paths/external-untouched", "s3-us-west-2.amazonaws.com" not in text or "://" in text)


def check_tags_exercised(snap: dict) -> None:
    """The tag paths are hit by real config data, not only by unit inputs."""
    text = cs.canonical_json(snap)
    for tag, why in ((cs.SLICE_TAG, "SceneEntityCfg slice fields"), (cs.TUPLE_TAG, "range tuples")):
        check(f"tags/{tag}", tag in text, f"{why} absent from a real snapshot")


def check_digest(snap: dict) -> None:
    check("digest/deterministic", cs.digest(snap) == cs.digest(cs.snapshot(LizardRoughTeacherEnvCfg_V14())))
    check(
        "digest/discriminates",
        cs.digest(snap) != cs.digest(cs.snapshot(LizardRoughTeacherEnvCfg_V13())),
        "v13 and v14 share a digest: the summary cannot tell recipes apart",
    )
    check("digest/versioned-format", isinstance(cs.FORMAT_VERSION, int))


def main() -> int:
    cfg = LizardRoughTeacherEnvCfg_V14()
    snap = cs.snapshot(cfg)
    check("snapshot/json-stable", json.loads(cs.canonical_json(snap)) == json.loads(cs.canonical_json(cs.snapshot(cfg))))
    check_order(snap, cfg)
    check_floats()
    check_identities(snap)
    check_missing_vs_none()
    check_agent_cfg()
    check_cross_process()
    check_paths(snap)
    check_tags_exercised(snap)
    check_digest(snap)
    print(f"  snapshot digest (v14): {cs.digest(snap)[:16]}... size {len(cs.canonical_json(snap))} bytes")
    if PROBLEMS:
        print(f"CFG_SNAPSHOT_DRIFT ({len(PROBLEMS)})")
        return 1
    print("CFG_SNAPSHOT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
