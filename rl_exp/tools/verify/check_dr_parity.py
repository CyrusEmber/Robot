# -*- coding: utf-8 -*-
"""Static parity gate for the freeze/determinism contracts (no sim, plain python).

Six checks, all machine-readable, all fail under --strict:

1. teacher-vs-family DR wiring, PER DECLARED SUBJECT: extracts every ``self.<manager>.<term>``
   wiring line from each pair named in ``versions/freeze_parity.json`` and reports the symmetric
   difference. The teacher snapshot deliberately duplicates the DR wiring (freeze discipline: no
   family imports) -- intentional divergence is fine, but it must be REVIEWED, never accidental.
   Which files form a pair, and which divergences were reviewed, are both declared there: this
   module holds no family name of its own.
2. DR event list sync: ``play_utils.DR_EVENT_NAMES`` (PLAY variants) must equal
   ``dr_controller._DR_EVENT_NAMES`` (eval modes). Two physical copies exist by
   design (the harness stays robot-agnostic); this check makes drift loud.
3. PLAY wiring coverage: every ``*_PLAY`` cfg class must call
   ``apply_play_wiring`` -- the block that hand-copies drifted twice historically.
4. robot block parity, per declared subject: the ``ArticulationCfg(...)`` literal in the two files
   (spawn props, init_state, limits) is a hand-copied freeze that check 1 does not see; symmetric
   line diff, reviewed diffs go to that subject's ``robot_block_allowlist``.
5. asset contract: every ACTIVE line's yaml (``versions/lines.json`` status, not a name rule) is
   checked against the asset IT names -- the usda must still provide the Geometry scope, every
   ``base_body_name`` and ``joint_order`` entry, and every body-name list the yaml DECLARES must
   match a link. Only declared keys are asserted: a line is not required to carry the old family's
   recipe shape, and a line that declares no ``usd_path`` has no asset contract to check.
   Catches asset regeneration that renames/drops prims.
6. asset lock: each ``versions/<line>/vN/asset_lock.json`` pins sha256 of its family's urdf,
   the compiled usda, every mesh under ``meshes/**``, and the version's OWN
   frozen yaml. Frozen yamls pin the usd PATH, not its CONTENT, so an in-place
   asset regeneration silently breaks working-tree reproduction of every
   resident teacher task id; this check makes that a reviewed commit
   (refresh locks with --update-locks in the same change that retires assets;
   --update-locks only rewrites versions whose lock actually changed, and --family
   keeps a caller that is landing one family from rewriting the rest).

Usage: python rl_exp\\tools\\verify\\check_dr_parity.py [--strict] [--self-test]
       python rl_exp\\tools\\verify\\check_dr_parity.py --update-locks [--family <name>]

``--self-test`` runs the falsifiers in-process before the real checks (``test_declare_family``):
they demonstrate that a tree with exactly ONE family can be landed, that the tool writes only that
family's subtree and fails on any failed step, that the subject declaration refuses an empty or
unreadable one, and that the asset contract no longer demands the old family's keys. A gate whose
failure modes were never demonstrated is not a gate.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from recipe_lines import RecipeLine, RecipeLineError, discover  # noqa: E402
import check_recipe_registry  # noqa: E402 - owns the lifecycle index's shape

_REPO = pathlib.Path(__file__).resolve().parents[3]
# The file-digest primitive has one home (work/active/record-variant-and-snapshot-specs.md ①): the asset locks are hashed with it
# rather than with a local ``sha256(read_bytes())``, so the scan that keeps that home single
# (``check_record_bindings.py``) does not have to carry an exception for this gate.
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.runrecord import binding  # noqa: E402
_EXP = _REPO / "rl_exp"
_TASKS = _EXP / "tasks"
_PLAY_UTILS = _TASKS / "play_utils.py"
_DR_CONTROLLER = _REPO / "ablation_harness" / "components" / "dr_controller.py"
_VERSIONS = _EXP / "versions"
_LINES = _VERSIONS / "lines.json"
# Which files are compared against each other is a DECLARATION, not a constant here: the freeze
# discipline makes the teacher snapshot a hand copy of a family cfg, and only the pair's owner knows
# which pair that is. Hard-coding lizard's two filenames made this gate unable to serve any other
# family and unable to notice a pair that moved (review 2026-09-22).
SUBJECTS_PATH = _VERSIONS / "freeze_parity.json"

# PLAY classes that legitimately skip apply_play_wiring (reviewed exceptions), keyed by class name
PLAY_WIRING_ALLOWLIST: set[str] = set()


def load_subjects() -> tuple[list[dict], list[str]]:
    """The declared parity subjects, as ``(subjects, problems)``.

    A subject names a line and the two cfg files whose hand-copied content must stay in sync, plus
    the divergences already reviewed (exact line -> why). Everything is checked here: a subject whose
    files are missing, or a tree with no subject at all, is a problem rather than a silent pass --
    "nothing was compared" must never print the same as "everything agreed".
    """
    problems: list[str] = []
    try:
        document = json.loads(SUBJECTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return [], [f"{SUBJECTS_PATH}: unreadable or not JSON ({err}) -- the parity subjects are a"
                    " declaration, so a missing one is a refusal, not a default"]
    subjects = document.get("subjects")
    if not isinstance(subjects, list) or not subjects:
        return [], [f"{SUBJECTS_PATH}: no subjects declared -- nothing would be compared"]
    for subject in subjects:
        if not isinstance(subject, dict) or not subject.get("line"):
            problems.append(f"{SUBJECTS_PATH}: a subject without a 'line' handle")
            continue
        for key in ("family_cfg", "teacher_cfg"):
            rel = subject.get(key)
            if not isinstance(rel, str) or not (_REPO / rel).is_file():
                problems.append(f"{SUBJECTS_PATH}: subject {subject['line']!r} {key} missing: {rel}")
        for key in ("wiring_allowlist", "robot_block_allowlist"):
            if not isinstance(subject.get(key), dict):
                problems.append(f"{SUBJECTS_PATH}: subject {subject['line']!r} {key} must be an"
                                " object mapping the exact line to its reason")
    return subjects, problems


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
    """Each declared subject: the symmetric wiring difference of its two files, allowlist applied."""
    subjects, problems = load_subjects()
    for subject in subjects:
        if not subject.get("family_cfg") or not subject.get("teacher_cfg"):
            continue
        allow = set(subject.get("wiring_allowlist") or {})
        sides = {}
        for key in ("family_cfg", "teacher_cfg"):
            lines = [l for l in wiring_lines(_REPO / subject[key]) if l not in allow]
            sides[key] = set(lines)
        for key, label in (("family_cfg", "family-only"), ("teacher_cfg", "teacher-only")):
            counterpart = sides["teacher_cfg" if key == "family_cfg" else "family_cfg"]
            for line in sorted(sides[key] - counterpart):
                problems.append(f"[{subject['line']}] {label} wiring line: {line}")
        print(f"  {subject['line']}: family {len(sides['family_cfg'])} lines | teacher"
              f" {len(sides['teacher_cfg'])} lines | allowlisted {len(allow)}")
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
    """Each declared subject: the symmetric ArticulationCfg difference of its two files."""
    subjects, problems = load_subjects()
    for subject in subjects:
        if not subject.get("family_cfg") or not subject.get("teacher_cfg"):
            continue
        allow = set(subject.get("robot_block_allowlist") or {})
        sides = {}
        for key in ("family_cfg", "teacher_cfg"):
            sides[key] = set(l for l in _articulation_block(_REPO / subject[key]) if l not in allow)
        for key, label in (("family_cfg", "family-only"), ("teacher_cfg", "teacher-only")):
            counterpart = sides["teacher_cfg" if key == "family_cfg" else "family_cfg"]
            for line in sorted(sides[key] - counterpart):
                problems.append(f"[{subject['line']}] {label} robot line: {line}")
        print(f"  {subject['line']}: family block {len(sides['family_cfg'])} lines | teacher"
              f" {len(sides['teacher_cfg'])} lines")
    return problems


def _yaml_scalar(text: str, key: str) -> str:
    match = re.search(rf"^[ \t]*{key}: (.+)$", text, re.M)
    return match.group(1).strip() if match else ""


def _declared_block_lists(text: str) -> dict[str, list[str]]:
    """Every block-style list the yaml DECLARES, as ``{key: items}``.

    Discovered rather than fixed: the previous version asserted a hard-coded trio
    (``foot_body_names`` / ``limb_body_names`` / ``undesired_contact_body_names``), so a line that
    randomizes nothing was forced to carry a block it never reads -- a requirement inferred from
    "this is a main line", i.e. from the shape of the OLD family's recipe rather than from anything
    the line says about itself (review 2026-09-22). What a line declares is what gets checked;
    what it does not declare is not its contract.
    """
    out: dict[str, list[str]] = {}
    for match in re.finditer(r"^[ \t]*([A-Za-z_]\w*):\n((?:[ \t]+- .+\n?)+)", text, re.M):
        out[match.group(1)] = [item.strip().strip("\"'") for item in re.findall(r"[ \t]+- (.+)", match.group(2))]
    return out


def _recipe_lines(problems: list[str]) -> list[RecipeLine]:
    """Every recipe line the tree declares, through the one shared discovery entry.

    A tree that breaks the yaml/lock convention is reported here and yields no lines --
    never a partial list. A gate that checks "the files it happened to recognise" cannot
    tell a clean tree from an unrecognised one, which is how this file's two older
    discovery copies (a fixed filename, and a recursive glob) came to disagree.
    """
    try:
        return list(discover().values())
    except RecipeLineError as err:
        problems.append(f"recipe line discovery: {err}")
        return []


def _active_lines(problems: list[str]) -> set[str]:
    """Line keys ``versions/lines.json`` declares ``active`` -- a status, not a name rule.

    The asset contract is a claim about a LIVE asset; a retired line's frozen yaml describes the
    asset of its own date, so checking it against today's usda yields findings nobody can act on.
    Retirement is a declaration in the lifecycle index (``check_recipe_registry`` owns its shape),
    which is why it is read from there: the previous filter inferred "carries the robot contract"
    from the line being named ``main`` (review 2026-09-22).
    """
    document = check_recipe_registry.load(_LINES)
    lines = document.get("lines") or {}
    for key in ("_missing", "_unreadable"):
        if lines.get(key):
            problems.append(f"{_LINES.name} is not usable: {lines[key]}")
            return set()
    active = {k for k, v in lines.items() if isinstance(v, dict) and v.get("status") == "active"}
    if not active:
        problems.append(f"{_LINES.name} declares no active line -- the asset contract would check nothing")
    return active


def _version_yamls(problems: list[str]) -> dict[str, pathlib.Path]:
    """Active lines' yamls, keyed the way records are (``lizard/main/dev``, ``lizard/main/v14``).

    Every ACTIVE line, not just ``main``: the contract below asserts only what each yaml declares
    (``usd_path`` present, ``joint_order`` matching the usda, every declared body-name list matching
    a link), so a side line with a different schema is checked on its own terms instead of being
    skipped by a rule about its name -- or forced to adopt the main line's keys.
    """
    active = _active_lines(problems)
    yamls: dict[str, pathlib.Path] = {}
    skipped = []
    for line in _recipe_lines(problems):
        if line.key not in active:
            skipped.append(line.key)
            continue
        yamls[f"{line.key}/dev"] = line.dev_yaml
        for version, path in line.versions.items():
            yamls[f"{line.key}/{version}"] = path
    if skipped:
        print(f"  not active (status in {_LINES.name}): {sorted(skipped)}")
    return yamls


def _recipe_yamls(problems: list[str]) -> list[pathlib.Path]:
    """Every frozen yaml in the tree; a yaml's parent directory is its version dir."""
    return [path for line in _recipe_lines(problems) for path in line.versions.values()]


def check_asset_contract() -> list[str]:
    problems = []
    yamls = _version_yamls(problems)
    counts = {"asset": 0, "joint_order": 0, "body_lists": 0, "no_asset": 0}
    for tag, path in yamls.items():
        text = path.read_text(encoding="utf-8")
        usd_rel = _yaml_scalar(text, "usd_path")
        if not usd_rel:
            counts["no_asset"] += 1  # declares no asset: nothing here is its contract
            continue
        counts["asset"] += 1
        usda_path = _EXP / usd_rel
        if not usda_path.exists():
            problems.append(f"{tag}: usd_path missing on disk: {usda_path}")
            continue
        usda = usda_path.read_text(encoding="utf-8", errors="ignore")
        joints = set(re.findall(r'def \w+Joint "([^"]+)"', usda))
        links = set(re.findall(r'def Xform "([^"]+)"', usda))
        if 'def Scope "Geometry"' not in usda:
            problems.append(f"{tag}: no Geometry scope in {usda_path.name} "
                            f"(cfgs hardcode prim path Robot/Geometry/base_link)")
        base_body = _yaml_scalar(text, "base_body_name")
        if base_body and base_body not in links:
            problems.append(f"{tag}: base_body_name not a link in usda: {base_body}")
        lists = _declared_block_lists(text)
        order = lists.get("joint_order")
        if order is not None:
            counts["joint_order"] += 1
            for name in order:
                if f"{name}_joint" not in joints:
                    problems.append(f"{tag}: joint_order entry missing in usda: {name}_joint")
            if len(joints) != len(order):
                problems.append(f"{tag}: usda has {len(joints)} joints, yaml joint_order has {len(order)}")
        for key, patterns in lists.items():
            if not key.endswith("body_names"):
                continue
            counts["body_lists"] += 1
            for pattern in patterns:
                if not any(re.search(pattern, link) for link in links):
                    problems.append(f"{tag}: body pattern matches no link: {key}={pattern}")
    print(f"  yamls checked: {len(yamls)} ({counts['asset']} declare an asset, {counts['no_asset']} do not;"
          f" {counts['joint_order']} declare joint_order, {counts['body_lists']} declare body-name lists)")
    return problems


# asset artifacts pinned by a version's asset_lock.json (paths relative to rl_exp); each version's
# lock additionally pins its OWN frozen yaml
def _lock_files(family: str) -> list[str]:
    """That family's urdf + compiled usda + every source mesh under meshes/** (meshes are the
    regeneration upstream of both; usda embeds copies but a mesh-only rebuild must still go loud).

    The mesh tree is shared on purpose: a family whose geometry is unchanged (lizard2 adds joints,
    not meshes) reads the same source files, and a family that changes geometry has to put its own
    tree there, which this list then picks up for both.
    """
    files = [f"versions/{family}/{family}.urdf", f"assets/{family}/{family}.usda"]
    files += sorted(
        str(p.relative_to(_EXP)).replace("\\", "/")
        for p in (_EXP / "meshes").rglob("*") if p.is_file()
    )
    return files


def _asset_hashes(yaml_path: pathlib.Path) -> dict[str, str]:
    """Global assets + that version's own frozen params yaml (post-freeze yaml
    edits are contract breaks, not tweaks).

    The digest comes from the one file-hash primitive (work/active/record-variant-and-snapshot-specs.md ①); a listed file that
    vanished while it was being hashed is a hard stop, because this dict is written straight
    into an asset lock and a null digest there is worse than no lock at all.
    """
    files = _lock_files(yaml_path.relative_to(_VERSIONS).parts[0])
    files.append(str(yaml_path.relative_to(_EXP)).replace("\\", "/"))
    hashes: dict[str, str] = {}
    for rel in files:
        digest = binding.sha256_file(_EXP / rel)
        if digest is None:
            raise FileNotFoundError(f"asset lock: {rel} unreadable while hashing")
        hashes[rel] = digest
    return hashes


def update_asset_locks(family: str | None = None) -> list[str]:
    """Rewrite every version lock that actually changed; return discovery problems.

    ``family`` scopes the write to one family's versions and reports the count it left alone,
    so a caller landing a NEW family can hand the tool a scope it cannot step outside of --
    instead of running the whole-tree rewrite and then trying to detect the collateral from
    the output ("the second run is always clean" is not a guard). ``None`` keeps the historical
    whole-tree behaviour, which is what an intentional asset retirement wants.

    Discovery problems are returned rather than raised so ``--update-locks`` can refuse
    loudly instead of printing ``LOCKS_UPDATED`` over a tree it only half understood.
    """
    problems: list[str] = []
    out_of_scope = 0
    for yaml_path in _recipe_yamls(problems):
        vdir = yaml_path.parent
        if family is not None and vdir.relative_to(_VERSIONS).parts[0] != family:
            out_of_scope += 1
            continue
        current = _asset_hashes(yaml_path)
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
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"  locked {vdir.relative_to(_VERSIONS)}")
    if family is not None:
        print(f"  scope: {family} only -- {out_of_scope} other version(s) not read, not written")
    return problems


def check_asset_locks() -> list[str]:
    problems = []
    yamls = _recipe_yamls(problems)
    for yaml_path in yamls:
        vdir = yaml_path.parent
        vtag = str(vdir.relative_to(_VERSIONS))
        lock = vdir / "asset_lock.json"
        if not lock.exists():
            problems.append(f"{vtag}: no asset_lock.json (run --update-locks once)")
            continue
        current = _asset_hashes(yaml_path)
        recorded = json.loads(lock.read_text(encoding="utf-8"))["files"]
        for rel, sha in current.items():
            if recorded.get(rel) != sha:
                problems.append(f"{vtag}: asset changed since freeze: {rel} "
                                f"{recorded.get(rel, '?')[:8]} -> {sha[:8]}")
    print(f"  versions locked: {len(yamls)}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--update-locks", action="store_true",
                        help="write versions/<line>/vN/asset_lock.json from current assets and exit")
    parser.add_argument("--family", default=None,
                        help="with --update-locks: restrict the rewrite to this family's versions "
                             "(a new family must not be able to touch a landed family's locks)")
    parser.add_argument("--self-test", action="store_true",
                        help="also falsify the detector in-process (declared subjects, declared asset "
                             "contract keys, and the family-landing tool's write scope)")
    args = parser.parse_args()

    if args.self_test:
        import test_declare_family as falsifier

        if falsifier.main() != 0:
            return 1

    if args.update_locks:
        problems = update_asset_locks(args.family)
        if problems:
            for p in problems:
                print(f"  DRIFT: {p}")
            print("LOCKS_NOT_UPDATED")
            return 1
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
