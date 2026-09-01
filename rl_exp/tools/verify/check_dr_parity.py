# -*- coding: utf-8 -*-
"""Static parity gate for the freeze/determinism contracts (no sim, plain python).

Six checks, all machine-readable, all fail under --strict:

1. teacher-vs-family DR wiring: extracts every ``self.<manager>.<term>`` wiring
   line from the family and teacher cfg files and reports the symmetric
   difference. The teacher snapshot deliberately duplicates the DR wiring
   (freeze discipline: no family imports) -- intentional divergence is fine,
   but it must be REVIEWED, never accidental.
2. DR event list sync: ``play_utils.DR_EVENT_NAMES`` (PLAY variants) must equal
   ``dr_controller._DR_EVENT_NAMES`` (eval modes). Two physical copies exist by
   design (the harness stays robot-agnostic); this check makes drift loud.
3. PLAY wiring coverage: every ``*_PLAY`` cfg class must call
   ``apply_play_wiring`` -- the block that hand-copies drifted twice historically.
4. robot block parity: the ``ArticulationCfg(...)`` literal in the family and
   teacher cfg files (spawn props, init_state, limits) is a hand-copied freeze
   that check 1 does not see; symmetric line diff, reviewed diffs go to
   ROBOT_BLOCK_ALLOWLIST.
5. asset contract: the text USD (lizard.usda) must still provide every prim
   path and name the cfgs hardcode -- Geometry scope + base_link (scanner
   ``Robot/Geometry/base_link``), every ``joint_order`` entry as ``<name>_joint``,
   and every body-name pattern in the dev AND frozen version yamls matching at
   least one link. Catches asset regeneration that renames/drops prims.
6. asset lock: ``versions/lizard/vN/asset_lock.json`` pins sha256 of lizard.urdf,
   the compiled usda, every mesh under ``meshes/**``, and the version's OWN
   frozen yaml. Frozen yamls pin the usd PATH, not its CONTENT, so an in-place
   asset regeneration silently breaks working-tree reproduction of every
   resident teacher task id; this check makes that a reviewed commit
   (refresh locks with --update-locks in the same change that retires assets;
   --update-locks only rewrites versions whose lock actually changed).

Usage: python rl_exp\\tools\\verify\\check_dr_parity.py [--strict]
       python rl_exp\\tools\\verify\\check_dr_parity.py --update-locks
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
_EXP = _REPO / "rl_exp"
_TASKS = _EXP / "tasks"
_FAMILY = _TASKS / "lizard_env_cfg.py"
_TEACHER = _TASKS / "teacher_env_cfg.py"
_PLAY_UTILS = _TASKS / "play_utils.py"
_DR_CONTROLLER = _REPO / "ablation_harness" / "components" / "dr_controller.py"
_VERSIONS = _EXP / "versions"

# wiring lines that only exist on one side BY DESIGN (reviewed divergences)
ALLOWLIST: set[str] = set()

# ArticulationCfg block lines that only exist on one side BY DESIGN
ROBOT_BLOCK_ALLOWLIST: set[str] = set()

# PLAY classes that legitimately skip apply_play_wiring (reviewed exceptions)
PLAY_WIRING_ALLOWLIST: set[str] = set()


def wiring_lines(path: pathlib.Path) -> list[str]:
    pat = re.compile(r"^\s*self\.(events|rewards|terminations)\.\w+")
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if pat.match(line):
            out.append(re.sub(r"\s+", " ", line.strip()))
    return out


def _extract_name_list(path: pathlib.Path, var_name: str) -> list[str]:
    """Pull the string items out of a module-level ``VAR = [...]`` list."""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^{var_name} = \[(.*?)\]", text, re.M | re.S)
    if match is None:
        raise RuntimeError(f"list '{var_name}' not found in {path}")
    return re.findall(r'"([^"]+)"', match.group(1))


def check_wiring_parity() -> list[str]:
    problems = []
    fam = [l for l in wiring_lines(_FAMILY) if l not in ALLOWLIST]
    tea = [l for l in wiring_lines(_TEACHER) if l not in ALLOWLIST]
    fam_set, tea_set = set(fam), set(tea)
    for line in sorted(fam_set - tea_set):
        problems.append(f"family-only wiring line: {line}")
    for line in sorted(tea_set - fam_set):
        problems.append(f"teacher-only wiring line: {line}")
    print(f"  family wiring lines: {len(fam_set)} | teacher wiring lines: {len(tea_set)}")
    return problems


def check_dr_list_sync() -> list[str]:
    play = _extract_name_list(_PLAY_UTILS, "DR_EVENT_NAMES")
    harness = _extract_name_list(_DR_CONTROLLER, "_DR_EVENT_NAMES")
    print(f"  play_utils: {len(play)} events | dr_controller: {len(harness)} events")
    problems = []
    # count assert: a silent-empty extraction (regex broke, list emptied) or a
    # duplicated entry passes the symmetric-difference check vacuously
    if not play:
        problems.append("play_utils.DR_EVENT_NAMES extracted EMPTY (regex broke or list emptied)")
    if not harness:
        problems.append("dr_controller._DR_EVENT_NAMES extracted EMPTY (regex broke or list emptied)")
    if len(play) != len(harness):
        problems.append(f"DR event list length drift: play_utils {len(play)} vs "
                        f"dr_controller {len(harness)} (duplicate entry?)")
    for name in sorted(set(play) - set(harness)):
        problems.append(f"in play_utils.DR_EVENT_NAMES but not dr_controller._DR_EVENT_NAMES: {name}")
    for name in sorted(set(harness) - set(play)):
        problems.append(f"in dr_controller._DR_EVENT_NAMES but not play_utils.DR_EVENT_NAMES: {name}")
    return problems


def check_play_wiring_coverage() -> list[str]:
    """Every *_PLAY configclass in tasks/*.py must call apply_play_wiring."""
    problems = []
    class_pat = re.compile(r"^class (\w*PLAY\w*)\(", re.M)
    for path in sorted(_TASKS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in class_pat.finditer(text):
            name = match.group(1)
            body = text[match.end():]
            nxt = re.search(r"^class ", body, re.M)
            if nxt is not None:
                body = body[:nxt.start()]
            if "apply_play_wiring(" not in body:
                if name not in PLAY_WIRING_ALLOWLIST:
                    problems.append(f"{path.name}: class {name} does not call apply_play_wiring")
    print(f"  PLAY classes checked")
    return problems


def _articulation_block(path: pathlib.Path) -> list[str]:
    """Extract the ArticulationCfg(...) literal as normalized code lines."""
    text = path.read_text(encoding="utf-8")
    start = text.find("ArticulationCfg(")
    if start < 0:
        raise RuntimeError(f"no ArticulationCfg(...) literal in {path}")
    depth = 0
    end = len(text)
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    lines = []
    for line in text[start:end].splitlines():
        code = line.split("#", 1)[0].strip()
        if code:
            lines.append(re.sub(r"\s+", " ", code))
    return lines


def check_robot_block_parity() -> list[str]:
    fam = [l for l in _articulation_block(_FAMILY) if l not in ROBOT_BLOCK_ALLOWLIST]
    tea = [l for l in _articulation_block(_TEACHER) if l not in ROBOT_BLOCK_ALLOWLIST]
    fam_set, tea_set = set(fam), set(tea)
    problems = []
    for line in sorted(fam_set - tea_set):
        problems.append(f"family-only robot line: {line}")
    for line in sorted(tea_set - fam_set):
        problems.append(f"teacher-only robot line: {line}")
    print(f"  family robot block: {len(fam_set)} lines | teacher: {len(tea_set)} lines")
    return problems


def _yaml_scalar(text: str, key: str) -> str:
    match = re.search(rf"^[ \t]*{key}: (.+)$", text, re.M)
    return match.group(1).strip() if match else ""


def _yaml_block_list(text: str, key: str) -> list[str]:
    """Items of a block-style list under ``key:`` at ANY indent (lists like
    foot_body_names nest under ``names:`` -- a col-0 anchor made the body
    pattern check silently run zero times). A missing key is a hard error:
    silent empty == the bug this helper used to have."""
    match = re.search(rf"^[ \t]*{key}:\n((?:[ \t]+- .+\n?)+)", text, re.M)
    if match is None:
        raise RuntimeError(f"yaml block list '{key}:' not found (yaml restructured?)")
    return [item.strip().strip("\"'") for item in re.findall(r"[ \t]+- (.+)", match.group(1))]


def _version_yamls() -> dict[str, pathlib.Path]:
    yamls = {"dev": _EXP / "lizard_params.yaml"}
    for vdir in sorted(_VERSIONS.glob("*/v*")):
        cfg = vdir / "lizard_params.yaml"
        if cfg.exists():
            yamls[str(vdir.relative_to(_VERSIONS))] = cfg
    return yamls


def check_asset_contract() -> list[str]:
    problems = []
    for tag, path in _version_yamls().items():
        text = path.read_text(encoding="utf-8")
        usda_path = _EXP / _yaml_scalar(text, "usd_path")
        if not usda_path.exists():
            problems.append(f"{tag}: usd_path missing on disk: {usda_path}")
            continue
        usda = usda_path.read_text(encoding="utf-8", errors="ignore")
        joints = set(re.findall(r'def \w+Joint "([^"]+)"', usda))
        links = set(re.findall(r'def Xform "([^"]+)"', usda))
        if 'def Scope "Geometry"' not in usda:
            problems.append(f"{tag}: no Geometry scope in {usda_path.name} "
                            f"(cfgs hardcode prim path Robot/Geometry/base_link)")
        if _yaml_scalar(text, "base_body_name") not in links:
            problems.append(f"{tag}: base_body_name not a link in usda")
        order = _yaml_block_list(text, "joint_order")
        for name in order:
            if f"{name}_joint" not in joints:
                problems.append(f"{tag}: joint_order entry missing in usda: {name}_joint")
        if len(joints) != len(order):
            problems.append(f"{tag}: usda has {len(joints)} joints, yaml joint_order has {len(order)}")
        for key in ("foot_body_names", "limb_body_names", "undesired_contact_body_names"):
            for pattern in _yaml_block_list(text, key):
                if not any(re.search(pattern, link) for link in links):
                    problems.append(f"{tag}: body pattern matches no link: {key}={pattern}")
    print(f"  yamls checked: {len(_version_yamls())}")
    return problems


# global asset artifacts pinned by versions/lizard/vN/asset_lock.json (paths
# relative to rl_exp); each version's lock additionally pins its OWN frozen yaml
def _lock_files() -> list[str]:
    """urdf + compiled usda + every source mesh under meshes/** (meshes are the
    regeneration upstream of both; usda embeds copies but a mesh-only rebuild
    must still go loud)."""
    files = ["lizard.urdf", "assets/lizard/lizard.usda"]
    files += sorted(
        str(p.relative_to(_EXP)).replace("\\", "/")
        for p in (_EXP / "meshes").rglob("*") if p.is_file()
    )
    return files


def _asset_hashes(vdir: pathlib.Path) -> dict[str, str]:
    """Global assets + that version's own lizard_params.yaml (post-freeze yaml
    edits are contract breaks, not tweaks)."""
    files = _lock_files()
    files.append(str((vdir / "lizard_params.yaml").relative_to(_EXP)).replace("\\", "/"))
    return {rel: hashlib.sha256((_EXP / rel).read_bytes()).hexdigest() for rel in files}


def update_asset_locks() -> None:
    for vdir in sorted(_VERSIONS.glob("*/v*")):
        if not (vdir / "lizard_params.yaml").exists():
            continue
        current = _asset_hashes(vdir)
        lock = vdir / "asset_lock.json"
        if lock.exists():
            try:
                recorded = json.loads(lock.read_text(encoding="utf-8"))["files"]
            except (json.JSONDecodeError, KeyError):
                recorded = None
            if recorded == current:
                print(f"  unchanged {vdir.relative_to(_VERSIONS)}")
                continue
        payload = {
            "note": "asset sha256 pinned at freeze; refresh with --update-locks only in a "
                    "commit that intentionally retires assets (see check_dr_parity.py)",
            "files": current,
        }
        (vdir / "asset_lock.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"  locked {vdir.relative_to(_VERSIONS)}")


def check_asset_locks() -> list[str]:
    problems = []
    for vdir in sorted(_VERSIONS.glob("*/v*")):
        if not (vdir / "lizard_params.yaml").exists():
            continue
        vtag = str(vdir.relative_to(_VERSIONS))
        lock = vdir / "asset_lock.json"
        if not lock.exists():
            problems.append(f"{vtag}: no asset_lock.json (run --update-locks once)")
            continue
        current = _asset_hashes(vdir)
        recorded = json.loads(lock.read_text(encoding="utf-8"))["files"]
        for rel, sha in current.items():
            if recorded.get(rel) != sha:
                problems.append(f"{vtag}: asset changed since freeze: {rel} "
                                f"{recorded.get(rel, '?')[:8]} -> {sha[:8]}")
    print(f"  versions locked: {len(list(_VERSIONS.glob('*/v*')))}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--update-locks", action="store_true",
                        help="write versions/lizard/vN/asset_lock.json from current assets and exit")
    args = parser.parse_args()

    if args.update_locks:
        update_asset_locks()
        print("LOCKS_UPDATED")
        return 0

    checks = {
        "wiring parity (family vs teacher)": check_wiring_parity,
        "DR event list sync (play_utils vs dr_controller)": check_dr_list_sync,
        "PLAY wiring coverage (apply_play_wiring)": check_play_wiring_coverage,
        "robot ArticulationCfg parity (family vs teacher)": check_robot_block_parity,
        "asset contract (usda prims/joints vs yamls + hardcoded paths)": check_asset_contract,
        "asset lock (frozen versions vs current assets)": check_asset_locks,
    }
    all_problems = []
    for title, fn in checks.items():
        print(f"[check] {title}")
        problems = fn()
        if problems:
            for p in problems:
                print(f"  DRIFT: {p}")
            all_problems.extend(problems)

    if not all_problems:
        print("PARITY_OK")
        return 0
    print(f"PARITY_DRIFT ({len(all_problems)} problem(s); review whether each diff is "
          f"intentional; allowlists in this script)")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
