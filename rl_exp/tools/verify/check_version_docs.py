# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Version-record completeness gate (no sim, stdlib only -- pre-commit safe).

Mechanizes versioning.mdc section A steps 2 and 5: every recipe version
directory ships the four-piece set (PLAN.md, NOTES.md, <line>_params.yaml --
named after its line, so a path names its owner, asset_lock.json locking its
own yaml), the family FAMILY.md version-history
table carries its row and names what the version is. Ungated
conventions were the root cause of the v10/v11 record debt (v11 NOTES.md
missing at kickoff, FAMILY lagging two versions), so the same drift
now turns red like any other freeze-contract violation. Which directories are
discoverable at all is delegated to ``recipe_lines`` rather than counted here.
FILEMAP.md used to need a per-version row too; that row is gone (2026-09-23) --
see the note where the check stood.

A **retired version** (``versions/lines.json`` version exception) keeps PLAN/NOTES/yaml and
drops the asset lock: the lock exists to hold a trained recipe to the bytes it was trained on,
and a version nobody trains again is not re-checked against anything. The status is read
through ``check_recipe_registry.effective_status``, the same single reader the launch path uses,
so this gate cannot disagree with the one that refuses a retired version's training.

Known ceiling (warn, not fail): git tags. Legacy versions predate the tag
discipline and prefix styles differ (v1/v2/v5 vs lizard-vN), so a missing
tag only warns; per versioning.mdc A, a training run started without a tag
means "treat as frozen" and the tag must be added immediately.

The **harness code baseline** is the exception to that. `ablation_harness/HARNESS.md`
keeps its own version counter and writes the tag discipline in the same paragraph,
and that counter has one naming form and no proposal state -- the number goes in when
the version lands -- so a number without its tag is red rather than a warning. It reads
that line as prose, so a line it cannot parse is a failure too: a reworded line would
otherwise make the assertion a no-op, which reads exactly like a correct repo. Ceiling:
local refs only -- a tag made and never pushed is invisible here, and that is the half
that lets someone else check the tree out.

Lineage gate: every version dir carries base.json naming its single
ancestry parent (the one frozen snapshot this recipe was modified from;
decision references to other versions stay in PLAN.md prose). The lineage
numbers in FAMILY.md are handles, not an ordering contract -- the DAG in
base.json files is the SSOT, so v7<-v6 vs v9<-v8 rebases never break
neighbors' records.

Side lines (versioning.mdc A, 分线条款: versions/<family>/<line>/vN/) are
found recursively and keyed by family-relative path ("parkour/v1"), so their
records are gated the same as main-line vN.

Coverage-verdict scan (versioning.mdc 仓根层): the family PLAN/FAMILY,
FILEMAP.md and HARNESS.md write coverage, and ACCEPTANCE.md is the sole owner
of pass readouts -- a gate verdict quoted in one of them is a second copy of a
fact whose owner is the ledger, and it goes stale the moment either side moves
(measured 2026-09-20: four such quotes in PLAN.md, three in FILEMAP.md).

Status-marker scan (same 仓根层 clause, other half): ARCH_PLAN.md writes
judgements and implementation form, never current status, so a bold
已完成/已落地/待实现 is the same class of second copy (measured 2026-09-20:
eight of them, in the 判据 lists). The preamble's own sentence quotes the
words unbolded -- that sentence is the rule, not a violation, so that scan is
scoped to the bold form. The clause names 标题 first, and the H1 line is where
a stale status is read before anything else: scanning only the bold form left
"（提案，待审核）" in the title from the day the document was written until
2026-10-09 (twenty days and one architecture review later), so the H1 line now
carries its own word list. Body prose may say 提案 -- only the H1 line is read.

Known ceiling: only verdict tokens are scanned, never ratios. ``90/208/83``
(obs widths), ``400/20`` (PD gains) and ``60/30/10`` (noise conditions) are
domain values -- a ratio pattern fires on legitimate prose 15 times out of 18,
and a gate that cries wolf gets its threshold raised instead of obeyed. Which
means a pass *rate* quoted without a verdict token ("27/27 绿") still slips
through; catching that needs review, not a regex.
"""

import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_recipe_registry  # noqa: E402 - owns the lifecycle index's shape and its one status reader
from recipe_lines import RecipeLineError, discover  # noqa: E402

_REPO = pathlib.Path(__file__).resolve().parents[3]
_VERSIONS = _REPO / "rl_exp" / "versions"
_LINES = _VERSIONS / "lines.json"
_ARCH_PLAN = _REPO / "ARCH_PLAN.md"
_HARNESS_DOC = _REPO / "ablation_harness" / "HARNESS.md"

#: The harness's code baseline, and the tag form the discipline beside it demands. The number is
#: written when the version lands (no proposal state, one naming form), so the tag is due in the
#: same breath -- which is why this pair is red while the family versions below stay a warning.
_BASELINE_LINE = re.compile(r"\*\*代码基线\*\*：v(\d+\.\d+\.\d+)")


def required_pieces(retired: bool) -> tuple[str, ...]:
    """The pieces a version directory must ship: a retired version drops its asset lock.

    The lock pins the version to the asset bytes it was trained on, which is a claim only a
    version that may still be run has to make. PLAN/NOTES stay either way -- the record of what
    the version was is exactly what retirement keeps.
    """
    pieces = ("PLAN.md", "NOTES.md")
    return pieces if retired else (*pieces, "asset_lock.json")

#: Gate verdict tokens. Ratios are deliberately NOT scanned (see the module docstring).
_COVERAGE_VERDICT = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_OK\b|ALL_OFFLINE_CHECKS_PASSED")

#: Bold status markers ARCH_PLAN.md must not carry: it writes judgements and implementation
#: form, never current status (its own preamble; versioning.mdc 仓根层). Scoped to the bold
#: form because the preamble quotes the forbidden words unbolded -- that sentence *is* the rule.
_ARCH_STATUS = re.compile(r"\*\*(已完成|已落地|待实现)\*\*")

#: Status words the ARCH_PLAN H1 (title) line must not carry -- the clause names 标题 first. The
#: prefix is lazy so the matched word is the one reported, not the whole title.
_ARCH_TITLE = re.compile(r"^#\s+.*?(提案|待审核|进行中|已完成|已落地|待实现)")


def coverage_docs() -> list[pathlib.Path]:
    """The documents that write coverage instead of pass counts (versioning.mdc 仓根层)."""
    return [
        _REPO / "FILEMAP.md",
        _REPO / "ablation_harness" / "HARNESS.md",
        *sorted(_VERSIONS.glob("*/FAMILY.md")),
        *sorted(_VERSIONS.glob("*/PLAN.md")),
    ]


def verdict_leaks(text: str) -> list[tuple[int, str]]:
    """Gate readouts in ``text``, as ``(line_number, token)``."""
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = _COVERAGE_VERDICT.search(line)
        if match is not None:
            found.append((lineno, match.group(0)))
    return found


def status_claims(text: str) -> list[tuple[int, str]]:
    """Bold status markers in ``text``, as ``(line_number, word)``."""
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = _ARCH_STATUS.search(line)
        if match is not None:
            found.append((lineno, match.group(1)))
    return found


def title_claims(text: str) -> list[tuple[int, str]]:
    """Status words on an H1 line of ``text``, as ``(line_number, word)``."""
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = _ARCH_TITLE.match(line)
        if match is not None:
            found.append((lineno, match.group(1)))
    return found


def baseline_tag_problem(text: str, tags: set[str]) -> str | None:
    """What is wrong with the harness baseline line in ``text``, or ``None`` when nothing is.

    Returns a message rather than a flag so the self-test asserts the whole chain -- parse,
    cardinality, tag lookup -- instead of only the regex. Two things are failures here and only
    one of them is a missing tag: a line that matched zero or two times also fails, because this
    reads prose and a reworded line would otherwise turn the assertion into a no-op that reads
    exactly like a correct repo.
    """
    declared = _BASELINE_LINE.findall(text)
    if len(declared) != 1:
        return (
            f"'**代码基线**：vN.M.K' matched {len(declared)} time(s), expected exactly 1"
            " -- reworded, duplicated or missing, so no version can be read off it"
        )
    tag = f"harness-v{declared[0]}"
    if tag not in tags:
        return (
            f"declares v{declared[0]} but has no tag {tag} -- a number in this line is not a"
            f" declaration until the tree it names can be checked out: git tag {tag} <declaring"
            f" commit> && git push origin {tag}"
        )
    return None


def self_test() -> int:
    """Falsifier for the verdict scan and the piece set: the real cases, and the near-misses that must pass."""
    cases = [
        # the two quotes this scan was written for, verbatim from before they were split
        (
            "work/closed/2026/recipe-registry-and-diff-declaration.md as it read before",
            "**本次独立复核**：`[41]` 单跑 `RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; "
            "322 declared difference(s) against their own base)`；反证重打一次",
            1,
        ),
        (
            "FILEMAP check_c_layer row as it read before",
            "出口 `C_LAYER_OK` / `C_LAYER_FAILED`；未判项记 `UNKNOWN` 不冒充通过。",
            1,
        ),
        # near-misses: a failed-verdict token, the domain ratios, prose about a verdict with no token
        (
            "near-miss tokens",
            "出口 `C_LAYER_FAILED`；工况比率 60/30/10；obs 三组 90/208/83；PD 400/20；未判项记 `UNKNOWN`",
            0,
        ),
        (
            "the same rows after the split",
            "**本次独立复核**：`[41]` 单跑通过（读数归 `ACCEPTANCE.md` §B4）；出口为成功/失败两态判词",
            0,
        ),
    ]
    status_cases = [
        # ARCH_PLAN.md 1.3 as it read before the status marker came out
        ("ARCH_PLAN 1.3 as it read before", "读 `type(env_cfg)` 不依赖 rl_exp 导入；**已落地**），其它任务透传。", 1),
        ("ARCH_PLAN 1.3 after", "读 `type(env_cfg)` 不依赖 rl_exp 导入），其它任务透传。", 0),
        # the preamble quotes the forbidden words unbolded -- that sentence is the rule itself
        ("the ARCH_PLAN preamble quoting the rule", '不写"已完成/已落地/待实现"；正文只写**当时证据与实现形态**（带日期）', 0),
    ]
    title_cases = [
        # the title as it read from the day the document was written until 2026-10-09
        ("the ARCH_PLAN title as it read before",
         "# ARCH_PLAN —— 实验可复现性与配置组织重整（提案，待审核）", 1),
        ("the same title after", "# ARCH_PLAN —— 实验可复现性与配置组织重整", 0),
        # body prose may name 提案 as a decision source; only the H1 line is read
        ("a body line naming 提案 as a decision source",
         "- **判据怎么来的**（决策来源：用户明示 / 审核建议 / 提案选择）→ `git log -p ARCH_PLAN.md`", 0),
        # a level-2 heading is not the title line
        ("a level-2 heading", "## 待定已结 2 项（用户拍板 2026-09-15）", 0),
    ]
    # the piece set is conditional on the version's status, so both directions are asserted: a
    # dropped lock that is still demanded, or a lock nobody drops, is the drift this covers.
    piece_cases = [
        ("an active version ships its asset lock", False, ("PLAN.md", "NOTES.md", "asset_lock.json")),
        ("a retired version keeps the record and drops the lock", True, ("PLAN.md", "NOTES.md")),
    ]
    # The harness baseline pairs a number with a tag. The near-misses are the two ways a prose
    # check goes quietly green: the line reworded, and two lines written where one is read.
    baseline_cases = [
        ("the baseline line as it reads", "**代码基线**：v1.10.0 —— 几何测量的唯一家", {"harness-v1.10.0"}, True),
        # the defect this assertion was written for: 0c3ec25 wrote v1.9.0 into the line and pushed
        # the commit alone, so the number named a version nobody could check out
        ("the same line before the tag existed", "**代码基线**：v1.9.0 —— 几何测量", set(), False),
        # the discipline sentence beside it names the tag form without declaring a version
        ("the discipline sentence naming the tag form", "并打 `harness-vN.M.K` 锚点", set(), False),
        ("a reworded baseline line", "**基线**：v1.10.0", {"harness-v1.10.0"}, False),
        ("two baseline lines", "**代码基线**：v1.10.0\n**代码基线**：v1.9.0", {"harness-v1.10.0"}, False),
    ]
    problems = [
        f"self-test '{name}': expected {expected} leak(s), found {len(verdict_leaks(text))}"
        for name, text, expected in cases
        if len(verdict_leaks(text)) != expected
    ] + [
        f"self-test '{name}': expected {expected} status marker(s), found {len(status_claims(text))}"
        for name, text, expected in status_cases
        if len(status_claims(text)) != expected
    ] + [
        f"self-test '{name}': expected {expected} title status word(s), found {len(title_claims(text))}"
        for name, text, expected in title_cases
        if len(title_claims(text)) != expected
    ] + [
        f"self-test '{name}': expected {expected}, got {tuple(required_pieces(retired))}"
        for name, retired, expected in piece_cases
        if tuple(required_pieces(retired)) != expected
    ] + [
        f"self-test '{name}': baseline line should read {('clean' if clean else 'wrong')},"
        " it reads the opposite"
        for name, text, tags, clean in baseline_cases
        if (baseline_tag_problem(text, tags) is None) != clean
    ]
    if problems:
        for problem in problems:
            print(f"check_version_docs: FAIL -- {problem}")
        return 1
    print(
        f"check_version_docs: self-test OK "
        f"({len(cases) + len(status_cases) + len(title_cases) + len(piece_cases)} fixtures)"
    )
    return 0


def _git_tags() -> set[str] | None:
    """Every tag in the repo, or ``None`` when git cannot be asked at all.

    ``None`` rather than an empty set: an empty set is indistinguishable from a repo whose tags
    are all missing, and the harness baseline below reads that as a red -- a misleading one, on a
    machine where the cause is git rather than a declaration.
    """
    try:
        out = subprocess.run(
            ["git", "tag", "--list"], capture_output=True, text=True, check=True, cwd=_REPO
        ).stdout
        return {line.strip() for line in out.splitlines() if line.strip()}
    except (OSError, subprocess.CalledProcessError):
        return None


def main(show_tree: bool = "--tree" in sys.argv) -> int:
    if "--self-test" in sys.argv and self_test():
        return 1
    problems: list[str] = []
    warnings: list[str] = []
    retired_versions: list[str] = []
    probed = _git_tags()
    tags = probed or set()
    if probed is None:
        problems.append(
            "git tag --list could not be read (no git, or it refused): tag presence is unknown,"
            " so neither the harness baseline nor the version directories were checked against it"
        )
    families = sorted(p for p in _VERSIONS.iterdir() if p.is_dir())

    # Which directories are discoverable versions, and under which params filename, is
    # answered by recipe_lines -- the single owner of that convention. Counting
    # *_params.yaml here as well is how this file and check_dr_parity came to disagree
    # about a misnamed or missing file (each thought the other checked it).
    try:
        lines = discover()
        discovery_error: str | None = None
    except RecipeLineError as err:
        lines = {}
        discovery_error = str(err)
    # keys are in this file's own record space: a version directory's path relative to
    # its family ("main/v0", "parkour/v1" -- the line directory since the main line
    # moved into main/)
    discovered = {
        f"{line.key}/{version}".split("/", 1)[1]: path.name
        for line in lines.values()
        for version, path in line.versions.items()
    }
    if discovery_error is not None:
        problems.append(f"recipe line discovery: {discovery_error}")

    # Whether a version was retired is a lifecycle fact (``lines.json`` version exception) and is
    # read through the registry gate's one reader, so this gate cannot answer "may this version
    # run" differently from the launch path. An unusable index is reported here rather than
    # silently waiving nothing: no status means no version is exempt.
    registry = check_recipe_registry.load(_LINES)
    for key in ("_missing", "_unreadable"):
        if registry.get(key):
            problems.append(
                f"{_LINES.name} is not usable ({registry[key]}): no version's status can be read,"
                f" so nothing here is exempt"
            )

    for family_dir in families:
        family = family_dir.name
        family_md = family_dir / "FAMILY.md"
        if not family_md.is_file():
            problems.append(f"{family}: versions/{family}/FAMILY.md missing")
            family_text = ""
        else:
            family_text = family_md.read_text(encoding="utf-8")

        # recursive: side lines (versions/<family>/<line>/vN/, versioning.mdc A
        # 分线条款) are keyed by family-relative path, e.g. "parkour/v1"
        rels = sorted(
            "/".join(p.relative_to(family_dir).parts)
            for p in family_dir.rglob("v[0-9]*")
            if p.is_dir()
        )
        parent: dict[str, str | None] = {}
        for rel in rels:
            vdir = family_dir.joinpath(*rel.split("/"))
            own_yaml = discovered.get(rel)
            if discovery_error is None and own_yaml is None:
                problems.append(
                    f"{family}/{rel}: recipe_lines cannot discover this version directory "
                    f"(versioning.mdc A-2: exactly one params file, named after its line)"
                )
            # rel is "<line>/vN"; a directory that is not under a line names no registered line,
            # so its status reads as unknown and it keeps every requirement (discovery already
            # reports it as a problem).
            line_name, _, version = rel.rpartition("/")
            retired = (
                check_recipe_registry.effective_status(registry, f"{family}/{line_name}", version)
                == "retired"
            )
            if retired:
                retired_versions.append(f"{family}/{rel}")
            for piece in required_pieces(retired):
                if not (vdir / piece).is_file():
                    problems.append(
                        f"{family}/{rel}: {piece} missing (versioning.mdc A-2 four-piece set)"
                        + (
                            " -- a retired version keeps PLAN/NOTES/yaml and drops its asset lock"
                            if retired
                            else ""
                        )
                    )
            lock_path = vdir / "asset_lock.json"
            if not retired and lock_path.is_file() and own_yaml is not None:
                try:
                    lock = json.loads(lock_path.read_text(encoding="utf-8"))
                    key = f"versions/{family}/{rel}/{own_yaml}"
                    if key not in lock.get("files", {}):
                        problems.append(
                            f"{family}/{rel}: asset_lock.json does not lock its own yaml ({key})"
                        )
                except (json.JSONDecodeError, OSError) as err:
                    problems.append(f"{family}/{rel}: asset_lock.json unreadable ({err})")
            if not re.search(rf"^\|\s*{re.escape(rel)}\s*\|", family_text, re.MULTILINE):
                problems.append(
                    f"{family}/{rel}: no '| {rel} |' row in FAMILY.md version history (versioning.mdc A-5)"
                )
            # The FILEMAP per-version row is gone with its check (2026-09-23): it repeated the path
            # and one boilerplate sentence, and the check only looked for the path as a substring --
            # so a passing mention satisfied it, and the row carried no identity to pick a version by.
            # The version's identity lives in the FAMILY row above; its existence is what the
            # directory checks below already read.
            # line versions need the qualified prefix: bare "v1" would collide
            # with the main line's first generation
            leaf = rel.rsplit("/", 1)[-1]
            tag_stem = f"{family}-{rel.replace('/', '-')}" if "/" in rel else f"{family}-{leaf}"
            if probed is not None and not any(
                t == tag_stem
                or t.startswith(f"{tag_stem}.")
                or ("/" not in rel and t == leaf)  # legacy unprefixed main-line tags
                for t in tags
            ):
                # the message names only spellings this check accepts: for a line version the bare
                # leaf is NOT one of them (it would collide with the main line's first generation),
                # and a message that offers it sends the reader after a tag that would still warn
                expected = f"{tag_stem}[.minor]" if "/" in rel else f"{leaf} or {tag_stem}[.minor]"
                warnings.append(
                    f"{family}/{rel}: no git tag ({expected}) --"
                    " fine for proposals; must exist once training starts"
                )
            base_path = vdir / "base.json"
            if not base_path.is_file():
                problems.append(
                    f"{family}/{rel}: base.json missing (lineage edge -- versioning.mdc A-2)"
                )
                continue
            try:
                data = json.loads(base_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as err:
                problems.append(f"{family}/{rel}: base.json unreadable ({err})")
                continue
            if "base" not in data:
                problems.append(f"{family}/{rel}: base.json has no 'base' field (root uses null)")
            else:
                parent[rel] = data["base"]

        # pass 2: resolve + validate edges now that every base.json is
        # collected; bare base names resolve INSIDE the version's own line
        # first (bare "v1" from parkour/v2 means parkour/v1, never main-line
        # v1); cross-line references write the qualified family-relative path
        edges: dict[str, str] = {}
        for rel, base in parent.items():
            if base is None:
                continue  # lineage root
            line_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
            own = f"{line_dir}/{base}" if line_dir else base
            cand = own if own in rels else (base if base in rels else own)
            if cand not in rels:
                problems.append(f"{family}/{rel}: base '{base}' is not a known version")
            elif cand not in parent:
                problems.append(f"{family}/{rel}: base '{base}' has no base.json itself")
            else:
                edges[rel] = cand

        # cycle guard over the resolved lineage edges
        for start in edges:
            seen = {start}
            node: str | None = edges[start]
            while node is not None:
                if node in seen:
                    problems.append(f"{family}/{start}: lineage cycle through {node}")
                    break
                seen.add(node)
                node = edges.get(node)

        if show_tree and rels:
            children: dict[str | None, list[str]] = {}
            for rel in rels:
                children.setdefault(edges.get(rel), []).append(rel)

            def _sort_key(s: str) -> tuple:
                line, leaf = s.rsplit("/", 1) if "/" in s else ("", s)
                return (line, int(re.search(r"\d+", leaf).group()))

            def _walk(node: str, indent: int) -> None:
                print(f"  {'  ' * indent}{node}")
                for child in sorted(children.get(node, []), key=_sort_key):
                    _walk(child, indent + 1)

            print(f"  lineage tree ({family}):")
            for root in sorted(children.get(None, []), key=_sort_key):
                _walk(root, 0)

    # versioning.mdc 仓根层: a quoted gate verdict in a coverage document is a second copy of a
    # fact whose owner is ACCEPTANCE.md -- and it keeps claiming "passes" after the code moved.
    # The scanned count goes in the success line: a scan that silently matches nothing (wrong
    # path, guard changed) reads exactly like a clean repo, so make the coverage visible.
    pinned = {_REPO / "FILEMAP.md", _REPO / "ablation_harness" / "HARNESS.md"}
    scanned = 0
    for doc in coverage_docs():
        if not doc.is_file():
            if doc in pinned:
                problems.append(f"{doc.relative_to(_REPO)}: coverage document missing")
            continue
        scanned += 1
        for lineno, token in verdict_leaks(doc.read_text(encoding="utf-8")):
            problems.append(
                f"{doc.relative_to(_REPO)}:{lineno}: gate readout '{token}' in a coverage document"
                " (versioning.mdc 仓根层: pass rates and counts live in ACCEPTANCE.md only)"
            )

    # ARCH_PLAN.md writes judgements and implementation form, never current status (its preamble):
    # no bold marker anywhere in it, and no status word on its title line.
    if not _ARCH_PLAN.is_file():
        problems.append("ARCH_PLAN.md: missing")
    else:
        plan_text = _ARCH_PLAN.read_text(encoding="utf-8")
        for lineno, word in status_claims(plan_text):
            problems.append(
                f"ARCH_PLAN.md:{lineno}: status marker '**{word}**' (preamble: 标题/表头/出口写判据,"
                " 正文只写当时证据与实现形态)"
            )
        for lineno, word in title_claims(plan_text):
            problems.append(
                f"ARCH_PLAN.md:{lineno}: status word '{word}' in the title line (preamble:"
                " 标题/表头/出口一律写判据；当前状态归 ACCEPTANCE.md)"
            )

    # The harness code baseline (ablation_harness/HARNESS.md 代码基线) is red, unlike the family
    # tags above: the harness has one naming form and no proposal state, so the number is written
    # when the version lands and the tag is due in the same breath (the discipline sits in the same
    # paragraph). Ceiling: local refs only -- "tagged but never pushed" is invisible here, and that
    # half is what makes the tree check-outable for anyone else, so it stays a review question.
    if not _HARNESS_DOC.is_file():
        problems.append("ablation_harness/HARNESS.md: missing (it writes the harness baseline)")
    else:
        harness_problem = baseline_tag_problem(_HARNESS_DOC.read_text(encoding="utf-8"), tags)
        if harness_problem is not None:
            problems.append(f"ablation_harness/HARNESS.md: {harness_problem}")

    print(f"  families checked: {len(families)} ({', '.join(p.name for p in families)})")
    if retired_versions:
        print(
            f"  retired versions ({len(retired_versions)}, asset_lock.json not required):"
            f" {sorted(retired_versions)}"
        )
    for warn in warnings:
        print(f"  WARN: {warn}")
    for problem in problems:
        print(f"  DRIFT: {problem}")
    if problems:
        print(f"VERSION_DOCS_DRIFT ({len(problems)})")
        return 1
    print(f"VERSION_DOCS_OK (coverage docs scanned: {scanned})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
