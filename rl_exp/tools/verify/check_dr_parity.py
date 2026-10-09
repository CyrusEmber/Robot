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
   Same check, same pass: a yaml that declares an ``actuators:`` block must cover EVERY joint the
   body's urdf limits, exactly once -- a joint no group matches keeps its urdf ``effort``/``velocity``
   silently, and two groups claiming one joint leave the winner ambiguous. What that does NOT prove
   is that the claimed value reached the solver (the cfg is what the implicit actuator hands over, so
   the urdf column is not the winning value wherever a group claims the joint -- but "covered" is a
   statement about the yaml, not about the built env). The divergence between the urdf column and the
   cfg value is therefore PRINTED, not gated: whether the two numbers ought to agree needs a torque
   requirement no line has declared yet (``work/closed/2026/actuator-params-audit.md``).
6. asset lock: each ``versions/<line>/vN/asset_lock.json`` pins sha256 of its family's urdf,
   the compiled usda, every mesh under ``meshes/**``, and the version's OWN
   frozen yaml. Frozen yamls pin the usd PATH, not its CONTENT, so an in-place
   asset regeneration silently breaks working-tree reproduction of every
   resident teacher task id; this check makes that a reviewed commit.
   The comparison runs BOTH ways and over the lock set itself: a locked path that is no longer on
   disk is a deletion the hashes cannot see (the path simply stops being hashed while the lock keeps
   claiming it), and a lock sitting in a version directory no discovered version owns is read by
   nobody. Both of those used to be silence.
   A lock is written ONCE, for one named version, and never refreshed: rewriting a record of what a
   version loaded erases the evidence that it changed, and a version that loads different assets is
   a new version. Locks frozen before this rule keep their older ``note`` text -- they are frozen
   records, not documents to correct.

Usage: python rl_exp\\tools\\verify\\check_dr_parity.py [--strict] [--self-test]
       python rl_exp\\tools\\verify\\check_dr_parity.py --update-locks --version <family/line/vN>

``--self-test`` runs the falsifiers in-process before the real checks (``test_declare_family``):
they demonstrate that a tree with exactly ONE family can be landed, that the tool writes only that
family's subtree and fails on any failed step, that the subject declaration refuses an empty or
unreadable one, and that the asset contract no longer demands the old family's keys. A gate whose
failure modes were never demonstrated is not a gate.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from recipe_lines import RecipeLine, RecipeLineError, discover  # noqa: E402
import check_recipe_registry  # noqa: E402 - owns the lifecycle index's shape

_REPO = pathlib.Path(__file__).resolve().parents[3]
# The file-digest primitive has one home (work/active/record-variant-and-snapshot-specs.md ①): the asset locks are hashed with it
# rather than with a local ``sha256(read_bytes())``, so the scan that keeps that home single
# (``check_record_bindings.py``) does not have to carry an exception for this gate.
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tasks import obs_protocol  # noqa: E402 - the one body/urdf resolver (see its tail)
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
        return list(discover(_VERSIONS).values())
    except RecipeLineError as err:
        problems.append(f"recipe line discovery: {err}")
        return []


def _active_lines(problems: list[str], report_empty: bool = True) -> set[str]:
    """Line keys ``versions/lines.json`` declares ``active`` -- a status, not a name rule.

    The asset contract is a claim about a LIVE asset; a retired line's frozen yaml describes the
    asset of its own date, so checking it against today's usda yields findings nobody can act on.
    Retirement is a declaration in the lifecycle index (``check_recipe_registry`` owns its shape),
    which is why it is read from there: the previous filter inferred "carries the robot contract"
    from the line being named ``main`` (review 2026-09-22).

    ``report_empty`` is for the second and later readers in one run: the index-shaped problem
    ("declares no active line") belongs to whoever reads it first, and reporting it twice would make
    one broken index look like several.
    """
    document = check_recipe_registry.load(_LINES)
    # ``load`` puts ``_missing``/``_unreadable`` at the TOP level. Looking for them inside ``lines``
    # (as this did) read an unusable index as "no active line" -- a silent empty set, which is the
    # one answer a lifecycle index must never be able to produce.
    for key in ("_missing", "_unreadable"):
        if document.get(key):
            problems.append(f"{_LINES.name} is not usable: {document[key]}")
            return set()
    lines = document.get("lines") or {}
    active = {k for k, v in lines.items() if isinstance(v, dict) and v.get("status") == "active"}
    if not active and report_empty:
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
    registry = check_recipe_registry.load(_LINES)
    yamls: dict[str, pathlib.Path] = {}
    skipped = []
    retired = []
    for line in _recipe_lines(problems):
        if line.key not in active:
            skipped.append(line.key)
            continue
        yamls[f"{line.key}/dev"] = line.dev_yaml
        for version, path in line.versions.items():
            # Version-level retirement, not just the whole line: a retired version keeps its yaml,
            # PLAN and NOTES but its assets are deliberately gone, so the asset contract -- which
            # reads the yaml's usd_path off disk -- must not hold it to them.
            if check_recipe_registry.effective_status(registry, line.key, version) == "retired":
                retired.append(f"{line.key}/{version}")
                continue
            yamls[f"{line.key}/{version}"] = path
    if skipped:
        print(f"  not active (status in {_LINES.name}): {sorted(skipped)}")
    if retired:
        print(f"  retired versions (asset contract not checked): {retired}")
    return yamls


def _recipe_yamls(problems: list[str]) -> list[pathlib.Path]:
    """Every frozen yaml in the tree; a yaml's parent directory is its version dir."""
    return [path for line in _recipe_lines(problems) for path in line.versions.values()]


def _actuator_groups(text: str) -> dict[str, dict]:
    """The yaml's ``actuators:`` block as ``{group: {"patterns": [...], <scalar key>: str}}``.

    Hand-read by line, like the scalar keys above: the block is a mapping whose value is a list plus a
    few floats, and this file carries no yaml dependency on purpose. A line that declares no
    ``actuators:`` block returns ``{}`` -- not declaring one is not a contract, the same rule the
    body-name lists follow.
    """
    start = re.search(r"^actuators:[ \t]*$", text, re.M)
    if start is None:
        return {}
    rest = text[start.end():]
    stop = re.search(r"^\S", rest, re.M)
    block = rest[: stop.start()] if stop else rest
    groups: dict[str, dict] = {}
    for match in re.finditer(r"^  (\w+):[ \t]*\n((?:[ \t]{4,}.*\n|\n)*)", block, re.M):
        body = match.group(2)
        groups[match.group(1)] = {
            "patterns": [item.strip().strip("\"'") for item in re.findall(r"^[ \t]+- (.+)$", body, re.M)],
            **dict(re.findall(r"^[ \t]+(\w+): ([-\d.]+)[ \t]*$", body, re.M)),
        }
    return groups


def _urdf_limits(urdf: pathlib.Path) -> dict[str, dict[str, float | None]]:
    """Every ``<joint>`` limit the urdf carries: ``{joint: {"effort": 150.0, ...}}``.

    This is the URDF's OWN column -- metadata the converter copies into the usda and the solver can be
    handed at spawn. It is read to decide which yaml group owns each joint, and to print how far that
    column has drifted from the value the cfg hands the solver.
    """
    text = urdf.read_text(encoding="utf-8", errors="ignore")
    out: dict[str, dict[str, float | None]] = {}
    for joint in re.finditer(r'<joint name="([^"]+)"[^>]*>(.*?)</joint>', text, re.S):
        limit = re.search(r"<limit ([^/>]*)/>", joint.group(2))
        if limit is None:
            continue
        values: dict[str, float | None] = {}
        for key, raw in re.findall(r'(\w+)="([^"]*)"', limit.group(1)):
            try:
                values[key] = float(raw)
            except ValueError:
                values[key] = None
        out[joint.group(1)] = values
    return out


def _joint_owners(groups: dict[str, dict], limits: dict[str, dict]) -> dict[str, list[str]]:
    """Which actuator group claims each urdf joint: ``{joint: [group, ...]}``; an empty list = nobody."""
    return {
        joint: sorted(name for name, spec in groups.items()
                      if any(re.search(pattern, joint) for pattern in spec["patterns"]))
        for joint in limits
    }


def check_asset_contract() -> list[str]:
    problems = []
    yamls = _version_yamls(problems)
    counts = {"asset": 0, "joint_order": 0, "body_lists": 0, "no_asset": 0,
              "actuators": 0, "joints": 0, "urdf_differs": 0, "velocity_declared": 0}
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
        groups = _actuator_groups(text)
        if not groups:
            continue  # no actuators: this yaml's contract is about prims, not about a value the solver is given
        counts["actuators"] += 1
        try:
            urdf = obs_protocol.resolve_body(usd_rel, path.relative_to(_VERSIONS).parts[0], _EXP)["urdf"]
            limits = _urdf_limits(urdf)
        except ValueError as err:
            problems.append(f"{tag}: declares actuators but its body's urdf is unresolvable ({err})")
            continue
        owners = _joint_owners(groups, limits)
        counts["joints"] += len(owners)
        for joint, claims in sorted(owners.items()):
            if not claims:
                problems.append(
                    f"{tag}: urdf joint {joint} is claimed by no actuator group -- nothing covers it, so "
                    "the urdf's own effort/velocity is the only value it has")
            elif len(claims) > 1:
                problems.append(f"{tag}: urdf joint {joint} is claimed by {claims} -- the winning group "
                                "is ambiguous")
        for joint, claims in owners.items():
            if len(claims) != 1:
                continue
            spec = groups[claims[0]]
            counts["velocity_declared"] += 1 if "velocity_limit" in spec else 0
            for column, key in (("effort", "effort_limit"), ("velocity", "velocity_limit")):
                declared, actual = spec.get(key), limits[joint].get(column)
                if declared is not None and actual is not None and abs(float(declared) - actual) > 1e-9:
                    counts["urdf_differs"] += 1
    print(f"  yamls checked: {len(yamls)} ({counts['asset']} declare an asset, {counts['no_asset']} do not;"
          f" {counts['joint_order']} declare joint_order, {counts['body_lists']} declare body-name lists)")
    if counts["actuators"]:
        print(f"  actuator blocks: {counts['actuators']} yaml(s) declare one over {counts['joints']} urdf "
              f"joint(s); the urdf's own limit differs from the value the cfg hands the solver on "
              f"{counts['urdf_differs']} joint-column(s), and {counts['velocity_declared']} declared "
              f"velocity_limit(s) never reach it -- the urdf column is READOUT, not the winner, and why "
              f"the two should agree is still open (work/closed/2026/actuator-params-audit.md)")
    return problems


# asset artifacts pinned by a version's asset_lock.json (paths relative to rl_exp); each version's
# lock additionally pins its OWN frozen yaml
def _key(path: pathlib.Path) -> str:
    """A path as a lock spells it: resolved, relative to ``rl_exp``, forward slashes."""
    return str(path.resolve().relative_to(_EXP)).replace("\\", "/")


# The urdf lookup, the mesh-reference reader and the repo-boundary check live in ``obs_protocol``
# (``resolve_urdf`` / ``urdf_refs``): the lock builder, the joint-layout probe and the
# contact-ownership probe need ONE answer to "which body does this recipe load", and two of them
# used to re-derive it from the spawn path's parent directory.


def _lock_files(yaml_path: pathlib.Path) -> list[str]:
    """What this version actually loads: its own yaml plus the body the recipe declares.

    The set comes from what the recipe DECLARES, not from the family's directory position --
    :func:`obs_protocol.resolve_body` owns the two on-disk shapes and refuses a body whose urdf
    cannot be resolved. The previous rule here pinned ``versions/<family>/<family>.urdf`` and
    ``assets/<family>/<family>.usda`` whatever the yaml said, plus every file under the family's
    declared tree, so a draft body in its own path would have been locked against the old one.

    Raises:
        ValueError: the recipe declares no asset, or its body cannot be resolved (the resolver's
            ``ProtocolError`` is a ``ValueError``). Refused rather than defaulted: a lock pinning
            the wrong asset is worse than no lock, and this is what builds one.
    """
    family = yaml_path.relative_to(_VERSIONS).parts[0]
    usd_rel = _yaml_scalar(yaml_path.read_text(encoding="utf-8"), "usd_path")
    if not usd_rel:
        raise ValueError(f"{yaml_path}: declares no usd_path -- nothing for a lock to pin")
    return sorted(set(obs_protocol.resolve_body(usd_rel, family, _EXP)["keys"]) | {_key(yaml_path)})


def _asset_hashes(yaml_path: pathlib.Path) -> dict[str, str]:
    """What this version loads (see :func:`_lock_files`, its own frozen yaml included).

    Post-freeze yaml edits are contract breaks, not tweaks. The digest comes from the one
    file-hash primitive (work/active/record-variant-and-snapshot-specs.md ①); a listed file that
    vanished while it was being hashed is a hard stop, because this dict is written straight
    into an asset lock and a null digest there is worse than no lock at all.
    """
    files = _lock_files(yaml_path)
    hashes: dict[str, str] = {}
    for rel in files:
        digest = binding.sha256_file(_EXP / rel)
        if digest is None:
            raise FileNotFoundError(f"asset lock: {rel} unreadable while hashing")
        hashes[rel] = digest
    return hashes


def update_asset_locks(version: str | None = None, family: str | None = None) -> list[str]:
    """Write the asset lock of ONE version that does not have one yet; return discovery problems.

    A lock is written once. This entry never rewrites an existing one: the lock is the frozen
    record of what a version loaded, so "the assets changed, refresh the lock" is not a repair --
    it erases the evidence that they changed (measured 2026-09-28: one geometry repair refreshed a
    trained version's lock, leaving it describing a body that version never ran on). A version that
    loads different assets is a new version.

    ``version`` names the single version to lock (``family/line/vN``) and is required: a
    scope-less run is how one repair swept every version in the tree. ``family`` narrows discovery
    further. Retired versions are refused outright -- their lock was deleted on purpose and
    re-creating it would restore a claim nobody maintains.

    Discovery problems are returned rather than raised so ``--update-locks`` can refuse
    loudly instead of printing ``LOCKS_UPDATED`` over a tree it only half understood.
    """
    problems: list[str] = []
    if version is None:
        return ["--update-locks needs --version <family/line/vN>: without it the run would write "
                "locks for every version in the tree, which is how one repair swept them all"]
    wanted = version.replace("\\", "/").strip("/")
    registry = check_recipe_registry.load(_LINES)
    written, skipped = 0, 0
    for yaml_path in _recipe_yamls(problems):
        vdir = yaml_path.parent
        vtag = str(vdir.relative_to(_VERSIONS)).replace("\\", "/")
        if vtag != wanted:
            skipped += 1
            continue
        if family is not None and vdir.relative_to(_VERSIONS).parts[0] != family:
            problems.append(f"{vtag}: outside --family {family!r}; not written")
            continue
        status = _effective_status(registry, vtag, problems)
        # Only an EXPLICITLY active version may be locked. Retired has a message of its own (its lock
        # was deleted on purpose); anything else -- an unreadable index, an invalid exception -- must
        # not be able to write one, because a lock is what later checks compare a version against.
        if status != "active":
            if status is None:
                problems.append(f"{vtag}: its lifecycle status cannot be read -- refusing to write a lock")
            else:
                problems.append(f"{vtag}: status {status!r} -- refusing to write a lock")
            continue
        try:
            current = _asset_hashes(yaml_path)
        except (ValueError, FileNotFoundError) as err:
            problems.append(f"{vtag}: cannot build its asset set ({err}); nothing was written")
            continue
        payload = {
            "note": "asset sha256 pinned at freeze; this lock is written once and never refreshed "
                    "-- a version that loads different assets is a new version (see check_dr_parity.py)",
            "files": current,
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        lock = vdir / "asset_lock.json"
        # Exclusive create, not "check then write": the check-then-write window is exactly where a
        # second writer would land, and an existing lock is never overwritten (it is the record of
        # what this version loaded). A failure here leaves no file behind.
        try:
            handle = os.fdopen(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644),
                               "w", encoding="utf-8", newline="\n")
        except FileExistsError:
            problems.append(f"{vtag}: already locked -- a lock is written once and never refreshed "
                            "(a version that loads different assets is a new version)")
            continue
        except OSError as err:
            problems.append(f"{vtag}: cannot create its lock ({err}); nothing was written")
            continue
        try:
            with handle:
                handle.write(text)
        except OSError as err:
            lock.unlink(missing_ok=True)
            problems.append(f"{vtag}: writing its lock failed ({err}); the partial file was removed")
            continue
        written += 1
        print(f"  locked {vtag}")
    if written == 0 and not problems:
        problems.append(f"{wanted}: names no discovered version (nothing written)")
    print(f"  {written} lock(s) written, {skipped} version(s) not this one")
    return problems


# A lock answers two questions and they are asked apart in ``check_asset_locks``: what it RECORDS
# (every entry still exists and still hashes to what it says) and what the version NEEDS (the set the
# recipe and urdf produce is inside it). Extra recorded entries are legitimate -- locks frozen under
# the earlier whole-tree rule hold them -- which is why "recorded == expected" is not the test.


def _unread_locks(root: pathlib.Path, checked: set[str]) -> list[str]:
    """Locks under ``root`` whose version directory is not among the versions this check read.

    Versions are enumerated by discovery, so a lock no discovered version owns is read by nobody --
    and nothing reading it looks exactly like nothing wrong with it.
    """
    return sorted(
        str(p.parent.relative_to(root)) for p in root.glob("*/*/*/asset_lock.json")
        if str(p.parent.relative_to(root)) not in checked
    )


def _effective_status(registry, vtag: str, problems: list[str]) -> str | None:
    """The lifecycle status of a version directory tag (``family/line/vN``).

    Read through the one lifecycle reader (line status + version exception). An index that cannot
    answer is reported rather than defaulted: a version whose status is unknown is neither active
    nor retired, and silently picking one of them is how "missing must not read as active" fails.
    """
    parts = pathlib.PurePath(vtag).parts
    if len(parts) != 3:
        problems.append(f"{vtag}: not a family/line/version path")
        return None
    status = check_recipe_registry.effective_status(registry, "/".join(parts[:2]), parts[2])
    if status is None:
        problems.append(f"{vtag}: the lifecycle index cannot answer its status (run "
                        "check_recipe_registry.py -- a status nobody can read is not permission)")
    return status


def check_asset_locks() -> list[str]:
    """Frozen versions vs the assets they load: active versions must match, retired ones are skipped.

    Two sets, deliberately. Every discovered version is what identity and the orphan check need (a
    lock no version owns is read by nobody), while only ACTIVE versions are held to their assets:
    a retired version's lock is deleted by the retirement change and ``--update-locks`` refuses to
    re-create it, so demanding one back would make retiring a version impossible without keeping
    its assets alive forever.
    """
    problems = []
    yamls = _recipe_yamls(problems)
    checked = {str(y.parent.relative_to(_VERSIONS)) for y in yamls}
    for vtag in _unread_locks(_VERSIONS, checked):
        problems.append(f"{vtag}: has an asset_lock.json but no discovered version reads it -- "
                        "nothing checks its contents; declare the version or drop the lock")
    registry = check_recipe_registry.load(_LINES)
    locked, retired = 0, 0
    for yaml_path in yamls:
        vdir = yaml_path.parent
        vtag = str(vdir.relative_to(_VERSIONS)).replace("\\", "/")
        if _effective_status(registry, vtag, problems) == "retired":
            retired += 1
            continue
        lock = vdir / "asset_lock.json"
        if not lock.exists():
            problems.append(f"{vtag}: no asset_lock.json (run --update-locks --version {vtag})")
            continue
        try:
            recorded = json.loads(lock.read_text(encoding="utf-8"))["files"]
        except (json.JSONDecodeError, KeyError) as err:
            problems.append(f"{vtag}: asset_lock.json does not hold a file map ({err})")
            continue
        locked += 1
        # (1) What the lock RECORDS: every entry must still exist and still hash to what it says --
        # including files today's builder would not add any more (an older mesh format, a whole-tree
        # entry). A lock checked for existence only passes here while the run side (asset_digest)
        # rejects the same drift, and the lock is exactly what that comparison reads.
        for rel in sorted(recorded):
            digest = binding.sha256_file(_EXP / rel)
            if digest is None:
                problems.append(f"{vtag}: locked file is gone or unreadable: {rel} (the lock still "
                                "lists it; restore the file or retire this version -- locks are "
                                "never rewritten)")
            elif digest != recorded[rel]:
                problems.append(f"{vtag}: locked file changed since freeze: {rel} "
                                f"{recorded[rel][:8]} -> {digest[:8]}")
        # (2) What the version NEEDS: the set the recipe and its urdf produce has to be inside the
        # lock. Extra entries are legitimate (older rules were broader); missing ones are not.
        try:
            current = _asset_hashes(yaml_path)
        except (ValueError, FileNotFoundError) as err:
            problems.append(f"{vtag}: cannot build its asset set ({err})")
            continue
        for rel, sha in sorted(current.items()):
            if rel not in recorded:
                problems.append(f"{vtag}: asset not in the lock: {rel} {sha[:8]} -- a lock is never "
                                "refreshed; a version that loads different assets is a new version")
    print(f"  versions locked: {locked} active, {retired} retired (skipped)")
    return problems


def check_body_swap() -> list[str]:
    """No version may keep loading a body its family has replaced, unless it is retired.

    A body swap is "the family's active line now declares a different usd". Every version frozen on
    the old body has to be retired in the same change: it was not trained on the new one, and its
    lock (deleted with its retirement) is what stops anything silently rebinding it to the new body.

    The input is the ACTIVE LINE's declaration, never a retirement entry: a check that took its
    input from the thing it verifies would pass whenever the record was simply forgotten. A family
    with no active line is not checked -- nothing runs it, so there is no current body to compare
    against, and the retired families' own asset bookkeeping is left untouched.
    """
    problems: list[str] = []
    active = _active_lines(problems, report_empty=False)
    if not active:
        return problems
    registry = check_recipe_registry.load(_LINES)
    yamls = _recipe_yamls(problems)
    families = sorted({key.split("/")[0] for key in active})
    checked, flagged = 0, 0
    for family in families:
        current = _current_body(family, problems, active)
        if current is None:
            continue  # nothing to compare against; _current_body reported why
        current_key = _key(current["usd"])
        for yaml_path in yamls:
            vdir = yaml_path.parent
            if vdir.relative_to(_VERSIONS).parts[0] != family:
                continue
            vtag = str(vdir.relative_to(_VERSIONS)).replace("\\", "/")
            usd_rel = _yaml_scalar(yaml_path.read_text(encoding="utf-8"), "usd_path")
            if not usd_rel:
                continue  # declares no asset, so there is nothing to compare (the contract owns it)
            checked += 1
            if _key(_EXP / usd_rel) == current_key:
                continue
            if _effective_status(registry, vtag, problems) != "retired":
                flagged += 1
                problems.append(
                    f"{vtag}: loads {usd_rel} while {family}'s current body is {current_key} -- a "
                    "version frozen on the replaced body must be retired in the same change"
                )
    print(f"  body swap: {checked} version(s) over {len(families)} active family(ies), "
          f"{flagged} still on a replaced body")
    return problems


def _self_test_body_swap() -> list[str]:
    """Falsify the swap check: one version left on the replaced body, one properly retired."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        versions = root / "rl_exp" / "versions"
        (versions / "gamma" / "gamma.urdf").parent.mkdir(parents=True)
        (versions / "gamma" / "gamma.urdf").write_text(
            '<mesh filename="meshes/collision/body_collision.obj"/>', encoding="utf-8")
        (versions / "gamma" / "main" / "main_params.yaml").parent.mkdir(parents=True)
        (versions / "gamma" / "main" / "main_params.yaml").write_text(
            "robot:\n  usd_path: assets/gamma/b2/b2.usda\n", encoding="utf-8")
        for version, usd in (("v1", "assets/gamma/b1/b1.usda"), ("v2", "assets/gamma/b2/b2.usda")):
            vdir = versions / "gamma" / "main" / version
            vdir.mkdir(parents=True)
            (vdir / "main_params.yaml").write_text(f"robot:\n  usd_path: {usd}\n", encoding="utf-8")
        body = root / "rl_exp" / "assets" / "gamma" / "b2"
        body.mkdir(parents=True)
        (body / "b2.usda").write_text("", encoding="utf-8")
        (body / "b2.urdf").write_text("", encoding="utf-8")  # a body in its own dir ships its URDF

        def write_index(v1_retired: bool) -> None:
            entry = {"status": "active", "successor": None, "retired_at": None, "reason": None,
                     "versions": None}
            if v1_retired:
                entry["versions"] = {"v1": {"status": "retired", "retired_at": "2026-09-30",
                                            "reason": "body replaced"}}
            (versions / "lines.json").write_text(
                json.dumps({"format": 1, "lines": {"gamma/main": entry}}), encoding="utf-8")

        global _EXP, _VERSIONS, _LINES
        saved = (_EXP, _VERSIONS, _LINES)
        try:
            _EXP, _VERSIONS, _LINES = root / "rl_exp", versions, versions / "lines.json"
            write_index(v1_retired=False)
            if not any("frozen on the replaced body" in p for p in check_body_swap()):
                problems.append("a version still loading the replaced body was not reported")
            write_index(v1_retired=True)
            if check_body_swap():
                problems.append("a retired version on the replaced body was reported anyway")

            # Two active lines naming different bodies: refused, not guessed. "Which body is current"
            # has to be one answer, or the check's own input would depend on which line is read.
            (versions / "gamma" / "side").mkdir()
            (versions / "gamma" / "side" / "side_params.yaml").write_text(
                "robot:\n  usd_path: assets/gamma/b1/b1.usda\n", encoding="utf-8")
            old_body = root / "rl_exp" / "assets" / "gamma" / "b1"
            old_body.mkdir(parents=True)
            (old_body / "b1.usda").write_text("", encoding="utf-8")
            (versions / "lines.json").write_text(json.dumps({"format": 1, "lines": {
                "gamma/main": {"status": "active", "successor": None, "retired_at": None,
                               "reason": None, "versions": None},
                "gamma/side": {"status": "active", "successor": None, "retired_at": None,
                               "reason": None, "versions": None}}}), encoding="utf-8")
            if not any("disagree about the current body" in p for p in check_body_swap()):
                problems.append("two active lines naming different bodies were not reported")
        finally:
            _EXP, _VERSIONS, _LINES = saved
    return problems


def _self_test_retired_versions() -> list[str]:
    """Falsify "retired means out of the asset checks" -- two cases no earlier fixture reached.

    (a) ONE version retired inside an active line, its body's files deleted with it: no check may
        still demand that body exist (it is deliberately gone). (b) A line whose every version is
        retired, declared tree deleted too: the family has no active consumer, so nothing here
        applies and the old fixed paths must not be read.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        versions = root / "rl_exp" / "versions"
        triangle = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        usda = ('def Scope "Geometry" {}\n'
                'def Mesh "body_collision" {\n  point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]\n}\n')

        def write_yaml(rel: str, usd: str) -> pathlib.Path:
            path = versions / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"robot:\n  usd_path: {usd}\n", encoding="utf-8")
            return path

        # gamma: v1 retired on a body whose files are gone; v2 active on the body that is here.
        (versions / "gamma" / "meshes" / "collision").mkdir(parents=True)
        (versions / "gamma" / "meshes" / "collision" / "body_collision.obj").write_text(
            triangle, encoding="utf-8")
        (versions / "gamma" / "assets.json").write_text(
            json.dumps({"format": 1, "meshes_dir": "versions/gamma/meshes"}), encoding="utf-8")
        body = root / "rl_exp" / "assets" / "gamma" / "b2"
        body.mkdir(parents=True)
        (body / "b2.usda").write_text(usda, encoding="utf-8")
        (body / "b2.urdf").write_text(
            '<mesh filename="../../../versions/gamma/meshes/collision/body_collision.obj"/>',
            encoding="utf-8")
        write_yaml("gamma/main/main_params.yaml", "assets/gamma/b2/b2.usda")
        write_yaml("gamma/main/v1/main_params.yaml", "assets/gamma/b1/b1.usda")  # gone on purpose
        v2_yaml = write_yaml("gamma/main/v2/main_params.yaml", "assets/gamma/b2/b2.usda")

        # delta: every version retired, and the declared tree is gone with the assets.
        (versions / "delta" / "delta.urdf").parent.mkdir(parents=True, exist_ok=True)
        (versions / "delta" / "delta.urdf").write_text('<mesh filename="meshes/x.obj"/>', encoding="utf-8")
        (versions / "delta" / "assets.json").write_text(
            json.dumps({"format": 1, "meshes_dir": "versions/delta/meshes"}), encoding="utf-8")
        write_yaml("delta/main/main_params.yaml", "assets/delta/delta.usda")
        write_yaml("delta/main/v1/main_params.yaml", "assets/delta/delta.usda")

        (versions / "lines.json").write_text(json.dumps({"format": 1, "lines": {
            "gamma/main": {"status": "active", "successor": None, "retired_at": None, "reason": None,
                           "versions": {"v1": {"status": "retired", "retired_at": "2026-09-30",
                                               "reason": "body replaced"}}},
            "delta/main": {"status": "retired", "successor": None, "retired_at": "2026-09-30",
                           "reason": "replaced"}}}), encoding="utf-8")
        global _EXP, _VERSIONS, _LINES
        saved = (_EXP, _VERSIONS, _LINES)
        try:
            _EXP, _VERSIONS, _LINES = root / "rl_exp", versions, versions / "lines.json"
            # v2's lock comes from the real builder: a fixture must not invent a digest.
            (versions / "gamma" / "main" / "v2" / "asset_lock.json").write_text(
                json.dumps({"files": _asset_hashes(v2_yaml)}), encoding="utf-8")

            demanded = check_asset_contract()
            if any("recipe line discovery" in p for p in demanded):
                # A fixture whose tree cannot be discovered checks nothing and would pass vacuously.
                problems.append(f"the fixture's own tree is undiscoverable: {demanded}")
            else:
                still_demanded = [p for p in demanded if p.startswith("gamma/main/v1")]
                if still_demanded:
                    problems.append(
                        f"a retired version's missing asset was still demanded: {still_demanded}"
                    )
            isolation = check_asset_isolation()
            if isolation:
                problems.append(f"a family with no active consumer was still checked: {isolation}")
            held = [p for p in check_asset_locks() if "gamma/main/v1" in p or "delta" in p]
            if held:
                problems.append(f"a retired version was still held to its assets: {held}")
        finally:
            _EXP, _VERSIONS, _LINES = saved
    return problems


def _self_test_actuator_contract() -> list[str]:
    """Falsify the actuator-group coverage rule, one case per way it can be wrong.

    The rule exists because a yaml group is what makes the cfg value the one the solver is given: a
    joint no group claims keeps its urdf ``effort``/``velocity`` instead, and a joint two groups claim
    has no defined winner. Both are silent without an assertion, so both cases are fixtured here --
    a happy-path fixture alone would only prove the regex matches when it matches.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        versions = root / "rl_exp" / "versions"
        body = root / "rl_exp" / "assets" / "gamma" / "b2"
        body.mkdir(parents=True)
        (body / "b2.usda").write_text('def Scope "Geometry" {}\n', encoding="utf-8")
        (versions / "gamma" / "assets.json").parent.mkdir(parents=True, exist_ok=True)
        (versions / "gamma" / "assets.json").write_text(
            json.dumps({"format": 1, "meshes_dir": "versions/gamma/meshes"}), encoding="utf-8")
        (versions / "lines.json").write_text(json.dumps({"format": 1, "lines": {
            "gamma/main": {"status": "active", "successor": None, "retired_at": None, "reason": None}}}),
            encoding="utf-8")

        def write_urdf(joints: list[str]) -> None:
            # A urdf is a single <robot> document: resolve_body parses it, so bare <joint> elements
            # are refused as junk after the document element.
            (body / "b2.urdf").write_text(
                '<robot name="gamma">\n' + "".join(
                    f'  <joint name="{joint}" type="revolute">\n'
                    f'    <limit lower="-1.0" upper="1.0" effort="30" velocity="6"/>\n  </joint>\n'
                    for joint in joints) + "</robot>\n", encoding="utf-8")

        def write_yaml(groups: str) -> None:
            path = versions / "gamma" / "main" / "main_params.yaml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("robot:\n  usd_path: assets/gamma/b2/b2.usda\n"
                            f"actuators:\n{groups}", encoding="utf-8")

        def contract() -> list[str] | None:
            """The check's own actuator findings, or None when the fixture's tree is undiscoverable."""
            found = check_asset_contract()
            if any("recipe line discovery" in p or "no active line" in p for p in found):
                return None  # an undiscoverable fixture checks nothing and would pass vacuously
            # An unresolvable body counts as a finding: filtering it out would let a fixture that
            # never read a urdf pass the clean case by producing no actuator findings at all.
            return [p for p in found
                    if "actuator group" in p or "winning group" in p or "declares actuators" in p]

        covered = ("  legs:\n    joint_patterns:\n      - \".*_hip_joint\"\n"
                   "    stiffness: 800.0\n    effort_limit: 180.0\n"
                   "  feet:\n    joint_patterns:\n      - \".*_foot_joint\"\n"
                   "    stiffness: 200.0\n    effort_limit: 70.0\n")
        global _EXP, _VERSIONS, _LINES
        saved = (_EXP, _VERSIONS, _LINES)
        try:
            _EXP, _VERSIONS, _LINES = root / "rl_exp", versions, versions / "lines.json"
            write_urdf(["lf_hip_joint", "lf_foot_joint"])
            write_yaml(covered)
            found = contract()
            if found is None:
                problems.append("the actuator fixture's own tree is undiscoverable")
            elif found:
                problems.append(f"a fully covered urdf was reported as uncovered: {found}")

            write_urdf(["lf_hip_joint", "lf_foot_joint", "lf_spare_joint"])
            found = contract()
            if found is None or not any("claimed by no actuator group" in p for p in found):
                problems.append("a urdf joint no group claims was NOT reported: its body's own "
                                "effort/velocity would win silently")

            write_urdf(["lf_hip_joint", "lf_foot_joint"])
            write_yaml(covered + "  extra:\n    joint_patterns:\n      - \".*_hip_joint\"\n"
                                 "    stiffness: 1.0\n")
            found = contract()
            if found is None or not any("winning group is ambiguous" in p for p in found):
                problems.append("a urdf joint claimed by two groups was NOT reported")
        finally:
            _EXP, _VERSIONS, _LINES = saved
    return problems


def _self_test_urdf_resolution() -> list[str]:
    """Falsify the compatibility rule: the family's own urdf is a fallback for the DECLARED legacy
    layout only.

    A usd in its own directory with no urdf beside it must be refused, never paired with the
    family's urdf: that pairing is "new body, old URDF", which the lock would then pin as if it were
    the body the version loads.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        base = root / "rl_exp"
        legacy_urdf = base / "versions" / "gamma" / "gamma.urdf"
        legacy_urdf.parent.mkdir(parents=True)
        legacy_urdf.write_text('<mesh filename="meshes/x.obj"/>', encoding="utf-8")
        body = base / "assets" / "gamma" / "b2"
        body.mkdir(parents=True)
        (body / "b2.usda").write_text("", encoding="utf-8")

        try:
            obs_protocol.resolve_urdf(body / "b2.usda", "gamma", base)
            problems.append("a new-layout usd without its own urdf fell back to the family's")
        except obs_protocol.ProtocolError:
            pass
        beside = body / "b2.urdf"
        beside.write_text("", encoding="utf-8")
        if obs_protocol.resolve_urdf(body / "b2.usda", "gamma", base) != beside:
            problems.append("a urdf beside its usda was not resolved")
        legacy_usda = base / "assets" / "gamma" / "gamma.usda"
        legacy_usda.write_text("", encoding="utf-8")
        if obs_protocol.resolve_urdf(legacy_usda, "gamma", base) != legacy_urdf:
            problems.append("the declared legacy layout did not resolve to the family's urdf")
        (base / "assets" / "gamma" / "gamma.urdf").unlink(missing_ok=True)
        legacy_urdf.unlink()
        try:
            obs_protocol.resolve_urdf(legacy_usda, "gamma", base)
            problems.append("the legacy usd resolved even with no urdf to fall back to")
        except obs_protocol.ProtocolError:
            pass
        outside = root / "elsewhere" / "outside.usda"
        outside.parent.mkdir(parents=True)
        outside.write_text("", encoding="utf-8")
        try:
            obs_protocol.resolve_body("../elsewhere/outside.usda", "gamma", base)
            problems.append("a usd resolving outside rl_exp was accepted")
        except obs_protocol.ProtocolError:
            pass

        # A URDF's writing style must not decide what its body is made of, and an unreadable one is
        # not a body without meshes.
        odd = base / "versions" / "gamma" / "gamma.urdf"
        odd.write_text("<?xml version='1.0'?>\n<robot name='gamma'>\n  <link name='body'>\n"
                       "    <collision><geometry><mesh name='m' "
                       "filename='meshes/collision/body_collision.obj'/></geometry></collision>\n"
                       "  </link>\n</robot>\n", encoding="utf-8")
        parsed = obs_protocol.urdf_refs(odd)
        if len(parsed) != 1 or parsed[0].name != "body_collision.obj":
            problems.append(f"a single-quoted mesh reference was not parsed: {parsed}")
        broken = base / "versions" / "gamma" / "broken.urdf"
        broken.write_text("<robot><link>", encoding="utf-8")
        try:
            obs_protocol.urdf_refs(broken)
            problems.append("an unparseable URDF was answered with an empty reference list")
        except obs_protocol.ProtocolError:
            pass
    return problems


def _self_test_lock_content() -> list[str]:
    """Falsify the two questions an ACTIVE lock answers -- kept apart on purpose.

    (1) Content: every path the lock records still exists AND matches its digest, including paths
        today's builder would no longer add (an older mesh format, an entry from the whole-tree
        rule). A lock that is only checked for existence passes the offline gate while the run side
        (``asset_digest``) rejects the same drift. (2) Coverage: the required set the recipe and its
        urdf produce has to be inside the lock.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        versions = root / "rl_exp" / "versions"
        triangle = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        (versions / "gamma" / "meshes" / "collision").mkdir(parents=True)
        (versions / "gamma" / "assets.json").write_text(
            json.dumps({"format": 1, "meshes_dir": "versions/gamma/meshes"}), encoding="utf-8")
        (versions / "gamma" / "meshes" / "collision" / "body_collision.obj").write_text(
            triangle, encoding="utf-8")
        # A file the lock records but the builder no longer produces: the shape of a lock frozen
        # under the older rule.
        extra = versions / "gamma" / "meshes" / "collision" / "older_rule_extra.obj"
        extra.write_text(triangle, encoding="utf-8")
        body = root / "rl_exp" / "assets" / "gamma" / "b2"
        body.mkdir(parents=True)
        (body / "b2.usda").write_text(
            'def Scope "Geometry" {}\n'
            'def Mesh "body_collision" {\n  point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]\n}\n',
            encoding="utf-8")
        # Single quotes and the attributes in another order: a pattern expecting `<mesh filename="…"`
        # reads this as a body with NO meshes, which every caller treats as clean.
        (body / "b2.urdf").write_text(
            "<robot name='gamma'><link name='body'><collision><geometry>"
            "<mesh name='m' filename='../../../versions/gamma/meshes/collision/body_collision.obj'/>"
            "</geometry></collision></link></robot>", encoding="utf-8")
        for rel in ("gamma/main/main_params.yaml", "gamma/main/v1/main_params.yaml"):
            path = versions / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("robot:\n  usd_path: assets/gamma/b2/b2.usda\n", encoding="utf-8")
        (versions / "lines.json").write_text(json.dumps({"format": 1, "lines": {
            "gamma/main": {"status": "active", "successor": None, "retired_at": None,
                           "reason": None, "versions": None}}}), encoding="utf-8")
        global _EXP, _VERSIONS, _LINES
        saved = (_EXP, _VERSIONS, _LINES)
        try:
            _EXP, _VERSIONS, _LINES = root / "rl_exp", versions, versions / "lines.json"
            v1_yaml = versions / "gamma" / "main" / "v1" / "main_params.yaml"
            extra_key = str(extra.relative_to(_EXP)).replace("\\", "/")
            recorded = _asset_hashes(v1_yaml)
            recorded[extra_key] = binding.sha256_file(extra)
            (v1_yaml.parent / "asset_lock.json").write_text(
                json.dumps({"files": recorded}), encoding="utf-8")

            intact = check_asset_locks()
            if intact:
                problems.append(f"a lock whose files all match was reported: {intact}")
            mesh_key = "versions/gamma/meshes/collision/body_collision.obj"
            if mesh_key not in recorded:
                problems.append(f"the lock does not cover the mesh the urdf names: {sorted(recorded)}")
            (versions / "gamma" / "meshes" / "collision" / "body_collision.obj").write_text(
                triangle + "v 0 2 0\nf 2 3 4\n", encoding="utf-8")
            if not any("body_collision.obj" in p for p in check_asset_locks()):
                problems.append("changing a mesh the urdf names was not reported")
            extra.write_text(triangle + "v 0 2 0\nf 2 3 4\n", encoding="utf-8")
            if not any(extra_key in p for p in check_asset_locks()):
                problems.append("a recorded file whose CONTENT changed was not reported (existence "
                                "only, so the offline gate and asset_digest disagree)")
            extra.unlink()
            if not any(extra_key in p for p in check_asset_locks()):
                problems.append("a recorded file that is gone was not reported")
        finally:
            _EXP, _VERSIONS, _LINES = saved
    return problems


def _self_test_swap_rehearsal() -> list[str]:
    """A whole body swap on a throwaway family, stage by stage.

    The failure this mechanism exists to prevent is a SEQUENCE, not a single check: adopt a new body,
    leave a version frozen on the old one, refresh its lock instead of retiring it, or lock the new
    body against the old URDF. So the rehearsal walks the sequence and asserts at every stage -- both
    the problem that must appear and the silence that must follow once it is handled:

    1. v1 frozen on b1, locked                     -> clean
    2. the dev yaml adopts b2                      -> v1 flagged, still loading the replaced body
    3. v1 retired, its lock deleted                -> clean again
    4. b1's assets removed                         -> still clean (nothing asks for them)
    5. v2 on b2 with no lock, then locked          -> red first, then clean, and only v2's lock exists
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        versions = root / "rl_exp" / "versions"
        triangle = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        usda = ('def Scope "Geometry" {}\n'
                'def Mesh "body_collision" {\n  point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]\n}\n')
        (versions / "gamma" / "meshes" / "collision").mkdir(parents=True)
        (versions / "gamma" / "meshes" / "collision" / "body_collision.obj").write_text(
            triangle, encoding="utf-8")
        (versions / "gamma" / "assets.json").write_text(
            json.dumps({"format": 1, "meshes_dir": "versions/gamma/meshes"}), encoding="utf-8")

        def write_yaml(rel: str, usd: str) -> pathlib.Path:
            path = versions / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"robot:\n  usd_path: {usd}\n", encoding="utf-8")
            return path

        def make_body(name: str) -> pathlib.Path:
            body = root / "rl_exp" / "assets" / "gamma" / name
            body.mkdir(parents=True)
            (body / f"{name}.usda").write_text(usda, encoding="utf-8")
            (body / f"{name}.urdf").write_text(
                '<mesh filename="../../../versions/gamma/meshes/collision/body_collision.obj"/>',
                encoding="utf-8")
            return body

        old_body = make_body("b1")
        make_body("b2")

        def write_index(retired: dict | None = None) -> None:
            entry = {"status": "active", "successor": None, "retired_at": None, "reason": None,
                     "versions": retired}
            (versions / "lines.json").write_text(
                json.dumps({"format": 1, "lines": {"gamma/main": entry}}), encoding="utf-8")

        global _EXP, _VERSIONS, _LINES
        saved = (_EXP, _VERSIONS, _LINES)
        try:
            _EXP, _VERSIONS, _LINES = root / "rl_exp", versions, versions / "lines.json"

            # 1. Frozen on b1, locked.
            write_yaml("gamma/main/main_params.yaml", "assets/gamma/b1/b1.usda")
            v1_yaml = write_yaml("gamma/main/v1/main_params.yaml", "assets/gamma/b1/b1.usda")
            write_index()
            if update_asset_locks("gamma/main/v1"):
                problems.append("stage 1: the first version could not be locked")
            if check_asset_locks() or check_body_swap() or check_asset_contract():
                problems.append(f"stage 1 was not clean: {check_asset_locks() + check_body_swap()}")

            # 2. Adopt b2. v1 is now frozen on a replaced body.
            write_yaml("gamma/main/main_params.yaml", "assets/gamma/b2/b2.usda")
            missed = check_body_swap()
            if not any("gamma/main/v1" in p and "retired" in p for p in missed):
                problems.append(f"stage 2 did not flag the version left on the old body: {missed}")

            # 3. Retire it: the exception lands, and the lock goes with it.
            write_index({"v1": {"status": "retired", "retired_at": "2026-09-30",
                                "reason": "body replaced"}})
            (v1_yaml.parent / "asset_lock.json").unlink()
            if check_asset_locks() or check_body_swap() or check_asset_contract():
                problems.append(f"stage 3 still held the retired version: "
                                f"{check_asset_locks() + check_body_swap() + check_asset_contract()}")

            # 4. Remove the old body's assets. Nothing may ask for them again.
            shutil.rmtree(old_body)
            if check_asset_locks() or check_body_swap() or check_asset_contract() or check_asset_isolation():
                problems.append("stage 4 still demanded a retired body's assets")

            # 5. The new version: red without a lock, clean with one -- and only its own lock is new.
            write_yaml("gamma/main/v2/main_params.yaml", "assets/gamma/b2/b2.usda")
            if not any("gamma/main/v2" in p for p in check_asset_locks()):
                problems.append("stage 5 did not report the active version with no lock")
            if update_asset_locks("gamma/main/v2"):
                problems.append("stage 5 could not lock the new version")
            finished = (check_asset_locks() + check_body_swap() + check_asset_contract()
                        + check_asset_isolation())
            if finished:
                problems.append(f"the swap did not finish clean: {finished}")
            new_lock = versions / "gamma" / "main" / "v2" / "asset_lock.json"
            if not new_lock.is_file():
                problems.append("stage 5 did not create the new version's lock")
            if (versions / "gamma" / "main" / "v1" / "asset_lock.json").exists():
                problems.append("stage 5 recreated the retired version's lock")
        finally:
            _EXP, _VERSIONS, _LINES = saved
    return problems


def _self_test_locks() -> list[str]:
    """Falsify what the lock gate is made of: a deleted asset, a lock nobody reads, the two urdf shapes.

    The legacy shape (``versions/<family>/<family>.urdf``) needs no fixture of its own: every
    version in the real tree is frozen under it, so a broken fallback reds the suite itself.
    """
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        vdir = root / "family" / "line" / "v1"
        vdir.mkdir(parents=True)
        (vdir / "asset_lock.json").write_text("{}", encoding="utf-8")
        vtag = str(pathlib.Path("family") / "line" / "v1")
        if _unread_locks(root, set()) != [vtag]:
            problems.append(f"a lock no version reads was not reported: {_unread_locks(root, set())}")
        if _unread_locks(root, {vtag}):
            problems.append("a lock a version did read was reported as unread")

    # An ACTIVE version with no lock is red: the lock is the record of what it loads, and asking for
    # one back is exactly what a retired version must not be asked.
    global _EXP, _VERSIONS, _LINES
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        versions = root / "rl_exp" / "versions"
        (versions / "gamma" / "main" / "v1").mkdir(parents=True)
        (versions / "gamma" / "gamma.urdf").write_text(
            '<mesh filename="meshes/collision/body_collision.obj"/>', encoding="utf-8")
        for yaml_path in (versions / "gamma" / "main" / "main_params.yaml",
                          versions / "gamma" / "main" / "v1" / "main_params.yaml"):
            yaml_path.write_text("robot:\n  usd_path: assets/gamma/b2/b2.usda\n", encoding="utf-8")
        body = root / "rl_exp" / "assets" / "gamma" / "b2"
        body.mkdir(parents=True)
        (body / "b2.usda").write_text("", encoding="utf-8")
        (versions / "lines.json").write_text(json.dumps({"format": 1, "lines": {
            "gamma/main": {"status": "active", "successor": None, "retired_at": None,
                           "reason": None, "versions": None}}}), encoding="utf-8")
        saved_all = (_EXP, _VERSIONS, _LINES)
        try:
            _EXP, _VERSIONS, _LINES = root / "rl_exp", versions, versions / "lines.json"
            if not any("no asset_lock.json" in p for p in check_asset_locks()):
                problems.append("an active version without a lock was not reported")
        finally:
            _EXP, _VERSIONS, _LINES = saved_all
    return problems


def _family_trees() -> dict[str, pathlib.Path]:
    """Every family declaration: family -> the mesh tree it consumes (absolute)."""
    trees: dict[str, pathlib.Path] = {}
    for declaration in sorted(_VERSIONS.glob("*/assets.json")):
        family = declaration.parent.name
        try:
            declared = json.loads(declaration.read_text(encoding="utf-8")).get("meshes_dir")
        except (OSError, json.JSONDecodeError) as err:
            raise ValueError(f"{declaration}: unreadable ({err})") from err
        if not isinstance(declared, str) or not declared:
            raise ValueError(f"{declaration}: no 'meshes_dir'")
        trees[family] = (_EXP / declared).resolve()
    return trees


def _current_body(family: str, problems: list[str], active: set[str] | None = None) -> dict | None:
    """The body a family currently runs, read from its ACTIVE lines' declared ``usd_path``.

    One rule for the whole family: every active line must name the same usd, and that path is the
    family's current body. The body-swap check and the isolation check both call this, so they
    cannot disagree about which body a family is on, and neither infers it from a directory name.

    Returns:
        ``{"usd": .., "urdf": .., "lines": [..]}``, or ``None`` when the family has no active line
        (nothing runs it, so nothing here applies). A disagreement between active lines, a
        declaration that cannot be read, or a usd that is not on disk is reported as a problem and
        also yields ``None`` -- refused rather than guessed.
    """
    active = _active_lines(problems)
    declarations: dict[str, list[str]] = {}
    for line in _recipe_lines(problems):
        if line.key not in active or line.key.split("/")[0] != family:
            continue
        declaration = line.dev_yaml
        if not declaration.is_file():
            problems.append(f"{line.key}: dev yaml {declaration} is missing -- no current body to read")
            return None
        usd_rel = _yaml_scalar(declaration.read_text(encoding="utf-8"), "usd_path")
        if not usd_rel:
            problems.append(f"{line.key}: dev yaml declares no usd_path -- no current body to read")
            return None
        usd = (_EXP / usd_rel).resolve()
        if not usd.is_file():
            problems.append(f"{line.key}: declared usd_path {usd_rel} is not on disk")
            return None
        declarations.setdefault(str(usd), []).append(line.key)
    if not declarations:
        return None
    if len(declarations) > 1:
        problems.append(f"{family}: active lines disagree about the current body -- "
                        + " / ".join(f"{usd} <- {sorted(keys)}"
                                     for usd, keys in sorted(declarations.items())))
        return None
    usd = pathlib.Path(next(iter(declarations)))
    try:
        urdf = obs_protocol.resolve_urdf(usd, family, _EXP)
    except obs_protocol.ProtocolError as err:
        problems.append(f"{family}: no urdf for its current body ({err})")
        return None
    return {"usd": usd, "urdf": urdf, "lines": sorted(declarations[str(usd)])}


def _isolation_lock_files(usda: pathlib.Path, urdf: pathlib.Path, tree: pathlib.Path) -> list[str]:
    """The current body's paths: its usda, its urdf, and every file under its declared tree."""
    files = [_key(usda), _key(urdf)]
    files += sorted(str(p.relative_to(_EXP)).replace("\\", "/")
                    for p in tree.rglob("*") if p.is_file())
    return files


def _usda_points(usda: pathlib.Path, body: str) -> list[list[float]] | None:
    """The inline collision points of one body in a family's usda, or ``None`` when absent."""
    block = re.search(rf'def Mesh "{body}_collision".*?point3f\[\] points = \[(.*?)\]',
                      usda.read_text(encoding="utf-8"), re.DOTALL)
    if block is None:
        return None
    return [[float(v) for v in item.split(",")]
            for item in re.findall(r"\(([^)]*)\)", block.group(1))]


def _vertex_gap(torch, first: list[list[float]], second: list[list[float]]) -> float:
    """Max nearest-neighbour distance between two vertex sets (both directions), [m]."""
    a = torch.unique(torch.tensor(first, dtype=torch.float32).round(decimals=5), dim=0)
    b = torch.unique(torch.tensor(second, dtype=torch.float32).round(decimals=5), dim=0)
    return max(float(torch.cdist(x, y).min(dim=1).values.max()) for x, y in ((a, b), (b, a)))


#: Two copies of one collision mesh are written by different tools and are independently quantised
#: (the .usda prints fewer decimals), so the floor is not zero: measured 2026-09-28 at 0.086-0.244 mm
#: over both families. The tolerance is three orders below the defect it was written for (the rl foot's
#: 4.4 mm deeper, nine-times-wider resting patch).
ISOLATION_TOLERANCE_M = 5.0e-4
#: The shared tree, i.e. the retirement-era convention. A family declaring it is the declared
#: exception to "urdf references must land in the declared tree" -- its files are frozen under locks
#: that must not be rewritten, so the divergence is printed rather than repaired here.
LEGACY_TREE = "meshes"


def check_asset_isolation() -> list[str]:
    """Each family loads and measures the geometry IT declares, and no two families share it.

    Four refusals, all of them failures this repo has actually had: a family that consumes a tree it
    never declared; physics (the usda's inline points) and diagnostics (the declared tree's .obj)
    drifting apart, so a report describes a mesh no run loaded; two families pinning the same files,
    which turns "repair family A's foot" into "retire family B's assets"; and a URDF whose references
    resolve somewhere other than the tree its family declares.
    """
    import torch

    problems: list[str] = []
    trees = _family_trees()
    if not trees:
        problems.append("no family declares a mesh tree (versions/<family>/assets.json)")
    # A family that carries an asset contract but no declaration is refused rather than defaulted.
    # Discovery is by ACTIVE RECIPE, not by where a urdf happens to sit: the old scan
    # (``_VERSIONS.glob("*/*.urdf")``) only saw the pre-2026-10 layout, so a family whose body lives in
    # its own directory could load assets with no tree declared at all and nothing said so.

    active = _active_lines(problems)
    for family in sorted({line.key.split("/")[0] for line in _recipe_lines(problems)
                          if line.key in active} - set(trees)):
        problems.append(f"{family}: an active recipe loads assets but versions/{family}/assets.json "
                        "declares no mesh tree -- the tree it reads must be declared, not defaulted")
    current_bodies = {family: _current_body(family, problems, active) for family in trees}

    # Only families with an ACTIVE consumer are checked. A fully retired family has no current body
    # to read (its assets may be gone with the retirement), and falling back to the pre-2026-10
    # fixed paths would hold it to files nobody maintains -- retired bookkeeping is its own business.
    family_bodies = {family: body for family, body in current_bodies.items() if body}
    locked = {family: set(_isolation_lock_files(family_bodies[family]["usd"],
                                                family_bodies[family]["urdf"], tree))
              for family, tree in trees.items() if family in family_bodies}
    families = sorted(family_bodies)
    for i, first in enumerate(families):
        for second in families[i + 1:]:
            shared = locked[first] & locked[second]
            if shared:
                problems.append(f"{first} and {second} lock the same files ({len(shared)} paths, "
                                f"e.g. {sorted(shared)[0]}): one family's geometry change would "
                                "rewrite the other's frozen assets")

    for family, tree in trees.items():
        body = family_bodies.get(family)
        if body is None:
            continue
        if not tree.is_dir():
            problems.append(f"{family}: declared mesh tree {tree} is not a directory")
        usda, family_urdf = body["usd"], body["urdf"]
        declared_legacy = json.loads((_VERSIONS / family / "assets.json")
                                     .read_text(encoding="utf-8")).get("meshes_dir") == LEGACY_TREE
        refs = [ref for ref in (ref_path.resolve() for ref_path in obs_protocol.urdf_refs(family_urdf))
                if ref.is_file()]
        missing = len(obs_protocol.urdf_refs(family_urdf)) - len(refs)
        if missing:
            problems.append(f"{family}: urdf has {missing} mesh reference(s) that do not resolve")
        landed = {ref.parent.parent for ref in refs}
        if landed and landed != {tree}:
            if declared_legacy:
                print(f"  {family}: urdf references {sorted(str(p) for p in landed)} while the family "
                      f"declares {tree} -- frozen divergence, recorded rather than repaired")
            else:
                problems.append(f"{family}: urdf mesh references resolve to "
                                f"{sorted(str(p) for p in landed)}, not to the declared tree {tree}")

        bodies = sorted(p.name[: -len("_collision.obj")]
                        for p in (tree / "collision").glob("*_collision.obj"))
        compared, worst_body, worst_gap = 0, "", 0.0
        for body in bodies:
            inline = _usda_points(usda, body)
            if inline is None:
                problems.append(f"{family}: {body} has a collision mesh in {tree} but no inline "
                                "points in the usda -- physics and diagnostics disagree")
                continue
            obj = [line.split()[1:4] for line in
                   (tree / "collision" / f"{body}_collision.obj")
                   .read_text(encoding="utf-8").splitlines() if line.startswith("v ")]
            gap = _vertex_gap(torch, inline, [[float(v) for v in row] for row in obj])
            compared += 1
            if gap > worst_gap:
                worst_body, worst_gap = body, gap
            if gap > ISOLATION_TOLERANCE_M:
                problems.append(f"{family}/{body}: usda inline points differ from {tree} by "
                                f"{gap * 1000:.3f} mm (tolerance {ISOLATION_TOLERANCE_M * 1000:.1f}) "
                                "-- the run does not load the mesh the readings are taken off")
        print(f"  {family}: {compared} collision mesh(es) against its usda, tree={tree}, "
              f"worst gap {worst_gap * 1000:.3f} mm ({worst_body})")
    return problems


# Mesh-reference reading is ``obs_protocol.urdf_refs`` (one implementation, keyed by the urdf rather
# than by a family name -- a body may sit anywhere: a draft beside the frozen one).


def _self_test_isolation() -> list[str]:
    """Falsifiers: a declared pair passes; re-shared trees, a drifted usda and a missing declaration fail."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "rl_exp" / "versions" / "alpha" / "meshes" / "collision").mkdir(parents=True)
        (root / "rl_exp" / "versions" / "beta" / "meshes" / "collision").mkdir(parents=True)
        (root / "rl_exp" / "meshes" / "collision").mkdir(parents=True)
        (root / "rl_exp" / "assets" / "alpha").mkdir(parents=True)
        (root / "rl_exp" / "assets" / "beta").mkdir(parents=True)
        triangle = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        for family, tree in (("alpha", "meshes"), ("beta", "versions/beta/meshes")):
            (root / "rl_exp" / "versions" / family / "assets.json").write_text(
                json.dumps({"format": 1, "meshes_dir": tree}), encoding="utf-8")
            # A line directory per family, because a params yaml directly under the FAMILY directory
            # is refused ("parameters outside any line"): this check only looks at families with an
            # ACTIVE consumer, so the fixture has to register one (the index below says so).
            line_dir = root / "rl_exp" / "versions" / family / "main"
            line_dir.mkdir(parents=True, exist_ok=True)
            (line_dir / "main_params.yaml").write_text(
                f"robot:\n  usd_path: assets/{family}/{family}.usda\n", encoding="utf-8")
            (root / "rl_exp" / tree / "collision" / "body_collision.obj").write_text(
                triangle, encoding="utf-8")
            (root / "rl_exp" / "versions" / family / f"{family}.urdf").write_text(
                '<mesh filename="meshes/collision/body_collision.obj"/>', encoding="utf-8")
            (root / "rl_exp" / "assets" / family / f"{family}.usda").write_text(
                'def Mesh "body_collision" {\n  point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]\n}\n',
                encoding="utf-8")
        # alpha is the legacy shape: its URDF names a per-family tree while the family declares the
        # shared one, and that divergence is reported rather than failed.
        (root / "rl_exp" / "versions" / "alpha" / "meshes" / "collision"
         / "body_collision.obj").write_text(triangle, encoding="utf-8")
        (root / "rl_exp" / "versions" / "lines.json").write_text(json.dumps({"format": 1, "lines": {
            "alpha/main": {"status": "active", "successor": None, "retired_at": None, "reason": None,
                           "versions": None},
            "beta/main": {"status": "active", "successor": None, "retired_at": None, "reason": None,
                          "versions": None}}}), encoding="utf-8")
        global _EXP, _VERSIONS, _LINES
        saved = (_EXP, _VERSIONS, _LINES)
        try:
            _EXP = root / "rl_exp"
            _VERSIONS = _EXP / "versions"
            _LINES = _VERSIONS / "lines.json"
            first = check_asset_isolation()
            if first:
                problems.append(f"a declared, isolated pair was reported as a problem: {first}")
            (root / "rl_exp" / "versions" / "beta" / "assets.json").write_text(
                json.dumps({"format": 1, "meshes_dir": "meshes"}), encoding="utf-8")
            if not any("lock the same files" in p for p in check_asset_isolation()):
                problems.append("two families pinning the same files was not reported")
            (root / "rl_exp" / "versions" / "beta" / "assets.json").write_text(
                json.dumps({"format": 1, "meshes_dir": "versions/beta/meshes"}), encoding="utf-8")
            (root / "rl_exp" / "assets" / "beta" / "beta.usda").write_text(
                'def Mesh "body_collision" {\n  point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0.01)]\n}\n',
                encoding="utf-8")
            if not any("inline points differ" in p for p in check_asset_isolation()):
                problems.append("a usda that drifted from its declared tree was not reported")
            (root / "rl_exp" / "versions" / "beta" / "assets.json").unlink()
            if not any("declares no mesh tree" in p for p in check_asset_isolation()):
                problems.append("a family with an asset contract but no declaration was not reported")
        finally:
            _EXP, _VERSIONS, _LINES = saved

    # A body in its own directory -- the layout a new body lands in. The check has to follow the
    # ACTIVE line's declared usd_path (so the usda and urdf come off that body), and its urdf's
    # references still have to land in the family's declared tree.
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        body = root / "rl_exp" / "assets" / "gamma" / "b2"
        (body / "meshes" / "collision").mkdir(parents=True)
        (root / "rl_exp" / "versions" / "gamma" / "meshes" / "collision").mkdir(parents=True)
        (root / "rl_exp" / "versions" / "gamma" / "main").mkdir(parents=True)
        triangle = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        (root / "rl_exp" / "versions" / "gamma" / "assets.json").write_text(
            json.dumps({"format": 1, "meshes_dir": "versions/gamma/meshes"}), encoding="utf-8")
        (root / "rl_exp" / "versions" / "gamma" / "meshes" / "collision"
         / "body_collision.obj").write_text(triangle, encoding="utf-8")
        (body / "meshes" / "collision" / "body_collision.obj").write_text(triangle, encoding="utf-8")
        (root / "rl_exp" / "versions" / "lines.json").write_text(json.dumps({
            "format": 1,
            "lines": {"gamma/main": {"status": "active", "successor": None, "retired_at": None,
                                    "reason": None, "versions": None}},
        }), encoding="utf-8")
        (body / "b2.usda").write_text(
            'def Mesh "body_collision" {\n  point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]\n}\n',
            encoding="utf-8")
        (body / "b2.urdf").write_text(
            '<mesh filename="../../../versions/gamma/meshes/collision/body_collision.obj"/>',
            encoding="utf-8")
        (root / "rl_exp" / "versions" / "gamma" / "main" / "main_params.yaml").write_text(
            "robot:\n  usd_path: assets/gamma/b2/b2.usda\n", encoding="utf-8")
        saved_all = (_EXP, _VERSIONS, _LINES)
        try:
            _EXP = root / "rl_exp"
            _VERSIONS = _EXP / "versions"
            _LINES = _VERSIONS / "lines.json"
            if check_asset_isolation():
                problems.append("a body in its own directory was reported as a problem")
            (body / "b2.urdf").write_text('<mesh filename="meshes/collision/body_collision.obj"/>',
                                          encoding="utf-8")
            if not any("not to the declared tree" in p for p in check_asset_isolation()):
                problems.append("a body's urdf referencing outside the declared tree was not reported")
            # Discovery is by active recipe, not by where a urdf sits: a family whose body lives in its
            # own directory must still be asked for its tree declaration.
            (root / "rl_exp" / "versions" / "gamma" / "assets.json").unlink()
            if not any("declares no mesh tree" in p for p in check_asset_isolation()):
                problems.append("an active family whose tree declaration is missing was not reported")
        finally:
            _EXP, _VERSIONS, _LINES = saved_all
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--update-locks", action="store_true",
                        help="write ONE version's missing asset_lock.json and exit (never rewrites)")
    parser.add_argument("--version", default=None,
                        help="with --update-locks: the single version to lock, family/line/vN")
    parser.add_argument("--family", default=None,
                        help="with --update-locks: refuse a --version outside this family")
    parser.add_argument("--self-test", action="store_true",
                        help="also falsify the detector in-process (declared subjects, declared asset "
                             "contract keys, the lock set's two comparisons, and the family-landing "
                             "tool's write scope)")
    args = parser.parse_args()

    if args.self_test:
        import test_declare_family as falsifier

        if falsifier.main() != 0:
            return 1
        # Every falsifier runs before any of them decides the exit code: the point of these is to
        # name which boundary is unproven, and stopping at the first would name only that one. A
        # fixture that CRASHES is a failure to report too, not a reason to stop.
        selftest_problems: list[str] = []
        for label, falsifier in (("locks", _self_test_locks),
                                 ("lock content", _self_test_lock_content),
                                 ("body swap", _self_test_body_swap),
                                 ("retired versions", _self_test_retired_versions),
                                 ("actuator contract", _self_test_actuator_contract),
                                 ("urdf resolution", _self_test_urdf_resolution),
                                 ("isolation", _self_test_isolation),
                                 ("swap rehearsal", _self_test_swap_rehearsal)):
            try:
                selftest_problems.extend(falsifier())
            except Exception as err:  # noqa: BLE001 -- deliberate: the crash IS the finding
                selftest_problems.append(f"{label}: the check crashed rather than answering ({err!r})")
        for problem in selftest_problems:
            print(f"  SELFTEST: {problem}")
        if selftest_problems:
            return 1

    if args.update_locks:
        problems = update_asset_locks(args.version, args.family)
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
        "body swap (a version frozen on a replaced body must be retired)": check_body_swap,
        "asset isolation (per-family mesh tree declared / usda matches that tree / no two families "
        "pin the same files / urdf refs land in the declared tree)": check_asset_isolation,
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
