"""Declare a new family/line's first version: five hand edits become one re-runnable command.

``versioning.mdc`` section A names five steps for a new recipe version. For a **new line**
(``versions/<family>/<line>/v1/``, no upstream to copy from) steps 1-3 are pure file
placement, and that is where the record debt came from: hand edits cannot be re-run, cannot
be reviewed as a plan, and drift from the conventions silently.

It reads only generic interfaces -- the recipe/line/config registries (``versions/lines.json``,
``versions/recipes.json``), the line's own params yaml, and the family's asset pair
(``versions/<family>/<family>.urdf`` + ``assets/<family>/<family>.usda``). **No other family
takes part in any step**: there is no template to clone, no reference line to name, and no
historical family this tool protects or consults. Cloning a sibling declaration used to be step
2's mechanism and is gone: the declaration is computed from the recipe this family itself
resolves (``emit_diff_declaration.py``), which is the only source that cannot name a path the
target line does not write.

What this script does, in order:

1. **Refuse unless the line really exists**: the dev yaml, the family URDF, the compiled
   USD, a ``lines.json`` lifecycle record, and the line's recipe keys in ``recipes.json``.
2. **Write the version directory**: the frozen yaml copy, ``base.json`` (a lineage root
   declares ``null``), ``PLAN.md`` and ``NOTES.md`` skeletons whose section names are the ones
   versioning.mdc A-2 requires, each marked TODO.
3. **Write ``versions/<family>/FAMILY.md``** when the family has no family document yet.
4. **Print** (never write) the FAMILY.md version row and the FILEMAP.md line row a human has to
   paste -- the FAMILY row is exactly what ``check_version_docs.py`` looks for.
5. **With ``--apply`` only**: call the lock/declaration generators --
   ``emit_diff_declaration.py`` (the version's own ``diff.json``, after the frozen yaml lands),
   ``check_cfg_lock.py --update --line <family>/<line> --reason <why>`` (a new line needs its
   own golden, which lands in the line root, never in ``vN/``) and ``check_dr_parity.py
   --update-locks --family <family>`` (the version's own ``asset_lock.json``: the frozen yaml
   pins the usd PATH, the lock pins its CONTENT). Every gate's exit code is checked, and the
   run ends with a byte comparison of every OTHER family's ``asset_lock.json``: this tool
   cannot reach another family, and now it cannot pretend it did not either.

Dry run is the default and prints every artifact in full, so what lands can be reviewed
first. Idempotent: an existing file is reported and skipped, ``--force`` overwrites. Every
write is asserted to be inside ``versions/<family>/`` before it happens.

Ceilings, stated so a green run is not read as more than it is:

* the emitted ``diff.json`` carries TODO ``why`` strings: hard B compares paths, not prose, so
  an unwritten reason is a review item, and this tool deliberately does not invent one.
* the declaration is DERIVED from the recipe's own resolved cfg, so it cannot disagree with the
  build -- and equally cannot notice a missing pin: the independent counts belong in
  ``check_recipe_build.py``'s EXPECTED_DIFFS, which no generator writes.
* the **gates are not run in dry-run mode**, and a new task id also needs its config class
  (``params_line`` + ``params_version``) registered before ``check_cfg_lock`` can find it.
  File placement without a registered recipe is a half-landed line and nothing here says so.
* ``asset_lock.json`` is not written here: it is a generator's product (step 5), so until an
  ``--apply`` runs, ``check_version_docs`` will report it missing. That is expected, not a bug.
* ``--root`` relocates the tree for idempotence demos on a copy; the generators read the
  real repo's registry, so they are skipped loudly when the root is not this repo.

Usage (from the repo root, or from ``{rl_exp}/tools/pipeline``):

    E:\\IsaacLab\\env_isaaclab\\Scripts\\python.exe rl_exp\\tools\\pipeline\\declare_family.py --help
    python declare_family.py --family lizard2 --line main --version v1 \\
        --experiment-name lizard2_v1 --max-iterations 10000 --reason "<why>"
    python declare_family.py ... --apply --reason "<why>"   # writes, then runs the gates
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import datetime
import json
import pathlib
import re
import subprocess
import sys

# this file lives at rl_exp/tools/pipeline/declare_family.py -> repo root is parents[3]
_REPO = pathlib.Path(__file__).resolve().parents[3]

NAME_RE = re.compile(r"[A-Za-z0-9_]+")
"""Family and line names become directory names and gate handles: keep them plain."""

VERSION_RE = re.compile(r"v\d+")
"""The pattern ``recipe_lines`` discovers version directories by, so anything else is invisible."""

WIRING_SUFFIX = "WiringCfg"
"""A line's shared wiring class is named this way (``BaselineWiringCfg``, ``Lizard2WiringCfg``)."""


@dataclasses.dataclass(frozen=True)
class Target:
    """The version being declared and the two values it declares about its own runner."""

    family: str
    line: str
    version: str
    experiment_name: str
    max_iterations: int | None

    @property
    def key(self) -> str:
        """Family-relative line handle, the name every gate routes by."""
        return f"{self.family}/{self.line}"

    @property
    def rel(self) -> str:
        """Family-relative version path (``main/v1``), the name FAMILY/FILEMAP rows use."""
        return f"{self.line}/{self.version}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Command line, with the dry-run/apply split spelled out in ``--help``."""
    parser = argparse.ArgumentParser(
        description=(
            "Declare a new family/line's first recipe version (versioning.mdc A steps 1-3) as one"
            " re-runnable command: precondition check, version-directory four-piece set, FAMILY.md"
            " skeleton, then the two lock generators."
        ),
        epilog=(
            "Dry run is the default and prints every artifact in full; --apply writes them and then"
            " runs check_cfg_lock.py --update and check_dr_parity.py --update-locks --family <family>,"
            " failing the run on any non-zero gate and on any foreign asset_lock.json byte change."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--family",
        required=True,
        help=(
            "family name, e.g. lizard2; must already have versions/<family>/<family>.urdf,"
            " assets/<family>/<family>.usda, a versions/lines.json record and recipe keys in"
            " versions/recipes.json (checked first, refusal lists what is missing)"
        ),
    )
    parser.add_argument(
        "--line",
        default="main",
        help="line name inside the family (default: main); its root owns <line>_params.yaml and cfg_lock.json",
    )
    parser.add_argument(
        "--version",
        default="v1",
        help="version handle to land (default: v1); must be v<N>, the pattern the gates discover versions by",
    )
    parser.add_argument(
        "--experiment-name",
        help=(
            "runner experiment_name this version declares -- one version, one log directory"
            " (versioning.mdc A); default <family>_<version>. Checked against the emitted"
            " declaration: if the runner cfg does not set it, the declaration has no such leaf and"
            " the run refuses, because a version whose log directory is unnamed cannot be traced"
        ),
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        help=(
            "runner max_iterations to declare; when given, the emitted declaration must carry that"
            " leaf (checking that the runner cfg really sets a budget for this version). Omitted"
            " leaves the reviewer to read the emitted value"
        ),
    )
    parser.add_argument(
        "--reason",
        help=(
            "why this line needs its own recipe golden; passed straight to check_cfg_lock.py, which"
            " refuses without it. Required with --apply"
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the files and run the two lock generators (default: dry run, nothing written)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite files that already exist (default: report and skip -- idempotent re-runs)",
    )
    parser.add_argument(
        "--root",
        help=(
            "repo root to operate on instead of this checkout; testing/idempotence demos on a copy"
            " of the tree only -- the two gates are repo-scoped and are skipped when the root is not"
            " this repo"
        ),
    )
    return parser.parse_args(argv)


# --------------------------------------------------------------------------------------
# step 1: preconditions
# --------------------------------------------------------------------------------------


def _read_json(path: pathlib.Path) -> dict:
    """A JSON object from disk, or an empty one -- a missing file reports through its own check."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _version_dirs(root: pathlib.Path) -> list[pathlib.Path]:
    """Version directories under ``root``, oldest first (``v<N>`` only: discovery's pattern)."""
    if not root.is_dir():
        return []
    return sorted(
        (d for d in root.iterdir() if d.is_dir() and VERSION_RE.fullmatch(d.name)),
        key=lambda d: int(d.name[1:]),
    )


def find_wiring(repo: pathlib.Path, line_key: str) -> tuple[str | None, list[str], list[str], pathlib.Path | None]:
    """This line's wiring class, as ``(dotted entry, its base names, candidates, its module)``.

    Candidates are collected before choosing so "two classes claim this line" is a refusal
    instead of a coin flip.
    """
    tasks = repo / "rl_exp" / "tasks"
    found: list[tuple[str, list[str], pathlib.Path]] = []
    for module_path in sorted(tasks.glob("*_env_cfg.py")):
        for name, key, bases in _class_params_line(module_path):
            if key == line_key:
                found.append((f"rl_exp.tasks.{module_path.stem}:{name}", bases, module_path))
    wiring = [c for c in found if c[0].rsplit(":", 1)[1].endswith(WIRING_SUFFIX)]
    chosen = wiring[0] if len(wiring) == 1 else None
    return (chosen[0] if chosen else None), (chosen[1] if chosen else []), [c[0] for c in found], (
        chosen[2] if chosen else None)


def stock_bases(module_path: pathlib.Path | None, bases: list[str]) -> list[str]:
    """Which of ``bases`` the module binds from ``isaaclab_tasks`` -- i.e. its framework stock cfgs.

    Read from the wiring module's own import statements, not from another family's declaration:
    hard B compares a lineage root against the framework stock cfg, and "which imported class is
    the stock one" is a fact about THIS module. Parsed rather than imported for the same reason
    ``_class_params_line`` is: importing a task module pulls IsaacLab into this tool.
    """
    if module_path is None:
        return []
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("isaaclab_tasks"):
            bound.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            bound.update(alias.asname or alias.name.split(".")[0]
                         for alias in node.names if alias.name.startswith("isaaclab_tasks"))
    return sorted(set(bases) & bound)


def preconditions(repo: pathlib.Path, target: Target) -> tuple[list[tuple[str, bool, str]], list[str], dict]:
    """Every fact the line must already own, as ``(checks, problems, facts)``.

    Nothing is guessed on a missing item: a refusal names the path it looked for, because the
    next action (create the asset, register the line) differs per item.
    """


def _class_params_line(module_path: pathlib.Path) -> list[tuple[str, str | None, list[str]]]:
    """Top-level classes that declare ``params_line``, as ``(class name, declared key, base names)``.

    Read by parsing rather than importing: importing a task module pulls IsaacLab, and "whose
    line is this" is a ``ClassVar`` string a parser can see.
    """
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    consts: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    consts[target.id] = node.value.value
    out: list[tuple[str, str | None, list[str]]] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        bases += [b.attr for b in node.bases if isinstance(b, ast.Attribute)]
        for stmt in node.body:
            target: str | None = None
            value: ast.expr | None = None
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                target, value = stmt.target.id, stmt.value
            elif (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
            ):
                target, value = stmt.targets[0].id, stmt.value
            if target != "params_line" or value is None:
                continue
            if isinstance(value, ast.Constant):
                key = value.value if isinstance(value.value, str) else None
            elif isinstance(value, ast.Name):
                key = consts.get(value.id)
            else:
                key = None
            out.append((node.name, key, bases))
    return out


def preconditions(repo: pathlib.Path, target: Target) -> tuple[list[tuple[str, bool, str]], list[str], dict]:
    """Every fact the line must already own, as ``(checks, problems, facts)``.

    Nothing is guessed on a missing item: a refusal names the path it looked for, because the
    next action (create the asset, register the line) differs per item.
    """
    exp = repo / "rl_exp"
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, path: pathlib.Path) -> None:
        checks.append((label, path.is_file(), str(path)))

    check("dev yaml", exp / "versions" / target.family / target.line / f"{target.line}_params.yaml")
    check("family urdf", exp / "versions" / target.family / f"{target.family}.urdf")
    check("compiled usd", exp / "assets" / target.family / f"{target.family}.usda")
    check("line registry", exp / "versions" / "lines.json")
    check("recipe map", exp / "versions" / "recipes.json")

    problems = [f"{label} missing: {path}" for label, ok, path in checks if not ok]

    for flag, value in (("--family", target.family), ("--line", target.line)):
        if NAME_RE.fullmatch(value) is None:
            problems.append(f"{flag} {value!r} is not [A-Za-z0-9_]+ -- it becomes a directory name and a gate handle")
    if VERSION_RE.fullmatch(target.version) is None:
        problems.append(
            f"--version {target.version!r} is not v<N>, and version directories are discovered by that"
            " pattern (recipe_lines) -- anything else is a directory no gate reads"
        )

    registry = _read_json(exp / "versions" / "lines.json").get("lines") or {}
    entry = registry.get(target.key)
    if entry is None:
        problems.append(
            f"versions/lines.json has no {target.key!r} record -- a discovered line with no lifecycle"
            " record is a refusal, never a default 'active' (check_recipe_registry.py)"
        )
    elif entry.get("status") != "active":
        problems.append(
            f"{target.key} is {entry.get('status')!r} in lines.json -- a retired line cannot take a new version"
        )

    recipes = _read_json(exp / "versions" / "recipes.json")
    recipe_keys = [k for k, v in (recipes.get("recipes") or {}).items() if isinstance(v, dict) and v.get("line") == target.key]
    if not recipe_keys:
        problems.append(
            f"versions/recipes.json has no recipe key for line {target.key!r} -- a version with no registered"
            " task id is unreachable, so there is nothing to lock"
        )
    named = [k for k in recipe_keys if target.version in k]
    train = [k for k in recipe_keys if "play" not in k.lower()]
    recipe_key = (named or train or recipe_keys or [None])[0]

    older = [d.name for d in _version_dirs(exp / "versions" / target.family / target.line) if int(d.name[1:]) < int(target.version[1:])]
    if older:
        problems.append(
            f"line {target.key} already has an older version {older} -- this tool lands a line's FIRST version;"
            " for vN+1 see versioning.mdc A-1 (copy vN to vN+1, then reset the bodies)"
        )

    wiring, wiring_bases, candidates, wiring_module = find_wiring(repo, target.key)
    if wiring is None:
        problems.append(
            f"no unique {WIRING_SUFFIX} class declares params_line={target.key!r} in rl_exp/tasks/*_env_cfg.py"
            f" (candidates found: {candidates or 'none'}) -- base.wiring names the class a recipe is built on,"
            " and a wrong name makes the whole declaration unresolvable"
        )
    stock = stock_bases(wiring_module, wiring_bases)
    if wiring and not stock:
        problems.append(
            f"{wiring} has no base bound from isaaclab_tasks (bases: {wiring_bases or 'none'}) -- hard B compares"
            " a lineage root against the framework stock cfg, so the wiring has to derive from one; a wiring"
            " that only derives from this repo's own classes has no stock parent to declare a difference against"
        )

    task_ids: dict[str, list[str]] = {rid: [] for rid in recipe_keys}
    for task_id, rid in (recipes.get("tasks") or {}).items():
        if rid in task_ids:
            task_ids[rid].append(task_id)
    tasks = [(task_id, rid) for rid in recipe_keys for task_id in task_ids[rid]]

    facts = {
        "recipe_keys": recipe_keys,
        "recipe_key": recipe_key,
        "tasks": tasks,
        "wiring": wiring,
        "stock_class": stock[0] if stock else None,
    }
    return checks, problems, facts


# --------------------------------------------------------------------------------------
# step 2: the version directory
# --------------------------------------------------------------------------------------


def base_json(target: Target) -> str:
    """``base.json`` for a lineage root: ``null`` plus what that means for the comparison."""
    payload = {
        "base": None,
        "note": (
            f"Line root: {target.key} has no upstream recipe, so this version names no parent snapshot."
            " A lineage root can therefore only be compared against the framework stock cfg, and that is"
            " what this recipe IS: what it writes on top of the stock cfg, path by path -- see diff.json."
            " Values borrowed from another line are data, not lineage."
        ),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _plan_md(target: Target, today: str) -> str:
    """PLAN.md skeleton: a new line's v1 is a multi-variable design, so the FULL form."""
    return f"""# {target.line}/{target.version} 方案（全量式，新线）

> 骨架落位 {today}，由 `rl_exp/tools/pipeline/declare_family.py` 生成：**标 `TODO` 的节必须写完才算定稿**，
> 生成器只保证节名齐（versioning.mdc §A-2）与不夹带别线的正文。
> 无上游母本（`base.json` 为 `null`）⇒ 按 §A 分线条款用**全量式 PLAN**：新线的 v1 是多变量设计，
> 不用单变量小改的简短骨架。
> 结果见 [NOTES.md](NOTES.md)；完整差异与逐项理由以 [diff.json](diff.json) 为准，本文不复述。
> 修订：（首稿不写；此后每次修订按 §B 加一行并同步本行）

## 目的与假设

TODO 一句话：本线只回答哪一个问题。**不预留第二臂**——预留 = 变量没写死。
TODO 假设与判据：写成可证伪的形式；判据的可执行口径（固定窗口、失败后如何处理）见「验收」。

## 配方

TODO 逐项：值 + 依据。至少点名地形 / 命令 / 观测宽度 / 网络 / 奖励项数 / 终止 / 课程 / DR / 资产与 sim 时序。
**不要在这里复制 diff.json 的逐路径清单**（那是它唯一的维护位置，第二份清单必然失真）。

## 修订记录

| 日期 | 版本 | 变更 + 原因 + 依据 |
|---|---|---|
| TODO | {target.version} | 初稿。 |

## 明确不做

TODO 逐项点名（缺席是设计，不是遗漏），可对着 diff.json 的 allowed 集合反推。

## 验收

TODO 主轴：几条同时成立才算通过 + 逐条阈值；**每条都要有可执行口径**，不是形容词。
TODO 固定窗口规则：例如"失败后不得重建 env 续算位移""不得只截取失败前的帧"。
TODO 补充报告项：明确标注**不作通过门槛**。

## 启动方案（计划命令）

TODO `python scripts\\reinforcement_learning\\rsl_rl\\train.py --task <task id> --num_envs <N>`。
开训前：打 tag `{target.family}-{target.line}-{target.version}`、
`check_cfg_lock.py --update --line {target.key} --reason "..."`、工作树必须干净（脏树开训被硬拒）。

## 风险与挂账（预注册）

TODO 开训前写死判废线（什么现象判废），而不是事后定。
"""


def _notes_md(target: Target, today: str) -> str:
    """NOTES.md skeleton: exactly the five sections versioning.mdc A-2 names."""
    return f"""# {target.line}/{target.version} 结果

> 骨架落位 {today}，由 `rl_exp/tools/pipeline/declare_family.py` 生成（versioning.mdc §A 必含骨架：
> 设计的引用 / 本版重点变化 / 实际执行与偏离 / 结果回填 / 结论）；生成器只保证节齐与不夹带别线的正文。
> 配方与验收定义见 [PLAN.md](PLAN.md)。

## 设计的引用

目的与假设见 [PLAN.md](PLAN.md)（不复制判据）。

## 本版重点变化（阅读提示，≤2 句）

TODO ≤2 句**阅读提示**，**不作完整性承诺**；完整差异与逐项理由以 [diff.json](diff.json) 为准。

## 实际执行与偏离

TODO 实跑必须写 run 目录路径 `logs/rsl_rl/<experiment_name>/<时间戳>`——同一 experiment_name 下会有
多次 run，缺时间戳指向的是目录、不是那一次。命令行 / 覆盖参数 / seed / checkpoint 的正文留在该目录的
`run_manifest.json` / `checkpoints.json`（记录本体机器本地、不进仓）⇒ 这里只给路径 + 复读命令。
TODO 偏离计划的地方照实写；run 记录不完整就写明缺什么、结果凭什么锚住。

## 结果回填

| 项 | 值 |
|---|---|
| run id | TODO |
| checkpoint | TODO |
| 评测报告 | TODO |
| 分类判定 | TODO |

## 结论

TODO 回答 PLAN 的那个问题；**照实写结论的边界**（几个 seed / 几个 checkpoint / 有无 DR）。
"""


# --------------------------------------------------------------------------------------
# step 3-4: family document and the rows a human pastes
# --------------------------------------------------------------------------------------


def family_md(target: Target, facts: dict, today: str) -> str:
    """FAMILY.md skeleton: identity, the line, the task table, and this version's history row.

    Facts only (present tense), and the rule text is pointed at rather than copied -- the
    versioning rules are inherited by reference, not by duplication.
    """
    rows = "\n".join(
        f"| `{task_id}` | `{recipe_id}`（冻结参数 `versions/{target.family}/{target.line}/{target.version}/{target.line}_params.yaml`） |"
        for task_id, recipe_id in facts["tasks"]
    ) or "| TODO | TODO |"
    return f"""# {target.family} 训练家族总文档

> 一个版本 = 一代训练配方（参数冻结副本 + 版本文档 + 训练记录）。代码共享继承，参数严格按版本隔离：
> 跑某个 `vN` 只读它自己目录里的冻结副本，开发态参数的修改永不影响已冻结版本。
> **本文只收已成立的事实（现在时/过去时）**：任何"待/未/若"字头的内容住 [PLAN.md](PLAN.md)。
> **继承机制按引用不复制**：升版五步、状态机、记录规范、PLAN/NOTES 必含骨架从
> `.codemaker/rules/versioning.mdc` §A 继承，本文不复制规则正文；目录职责、闸门清单、
> 版本目录**不再**逐条登记于仓根 `FILEMAP.md`（2026-09-23 起）；本文这张版本史表就是它的登记，
> 路径与冻结状态由目录本身与 `check_version_docs` 的形态检查保证。

## 家族身份

TODO 一句话：这副机器人/构型是什么，与别的家族差在哪（具体到几何或关节，不是"更好了"）。
TODO 家族为什么存在（要回答的那个问题），以及**不借别的家族的值**：借来的值是数据，不是血统。

## 线

- `versions/{target.family}/{target.line}/` = 本家族第一条线。线根放该线的开发态参数与配方锁
  （`{target.line}_params.yaml` / `cfg_lock.json`），`vN/` 放冻结副本。
- 家族级文档（`FAMILY.md` / `PLAN.md`）落在 `versions/{target.family}/`，**不在 `{target.line}/` 里**。
- 线之间的隔离是硬约束：本线不 import 其它线的 cfg/mdp，要哪个核就复制一份进本线自己的模块。

## 任务注册表

真源是 `rl_exp/tasks/recipe.py` 的配方表 + `versions/recipes.json`（本文只留人类速查）。

| 任务 id | 配方来源 |
|---|---|
{rows}

## 版本历史

血统 SSOT = 各版本目录 `base.json`（唯一母本边；决策引用留在 PLAN 散文）。`vN` 编号只是句柄，不是顺序契约。
**身份（这版是什么）与教训只在这里**；判决读数归各 `vN/NOTES.md`。

| 版本 | 日期 | 摘要 | 教训 |
|---|---|---|---|
| {target.rel} | {today} | TODO 这版是什么（血统根 ⇒ `base.json` 为 `null`，比较对象是框架 stock） | （训练后补） |
"""


def family_row(target: Target, today: str) -> str:
    """The FAMILY.md version-history row, in the shape ``check_version_docs`` matches on."""
    return f"| {target.rel} | {today} | TODO 这版是什么（血统根 ⇒ `base.json` 为 `null`） | （训练后补） |"


def filemap_rows(target: Target) -> list[str]:
    """The FILEMAP.md row to paste: the line directory, which is the level FILEMAP indexes.

    Versions are no longer listed here (2026-09-23). The row that used to stand for a version
    repeated its path and one boilerplate sentence, and the check behind it only looked for the
    path as a substring -- a passing mention satisfied it. What a version *is* belongs in the
    FAMILY row, and that the directory exists at all is what the shape checks read.
    """
    family_doc = f"`versions/{target.family}/FAMILY.md`"
    return [
        f"| `rl_exp\\versions\\{target.family}\\{target.line}\\` | 版本线目录（线根放开发态参数与配方锁；身份见 {family_doc} 版本史） |",
    ]


# --------------------------------------------------------------------------------------
# step 5: the two generators, and the zero-drift self check
# --------------------------------------------------------------------------------------


def run_gate(repo: pathlib.Path, argv: list[str], label: str) -> subprocess.CompletedProcess:
    """Run one gate with this interpreter and print its output verbatim."""
    command = [sys.executable, *argv]
    print(f"\n--- {label}\n    {' '.join(command)}")
    proc = subprocess.run(command, cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr.strip():
        print("--- stderr\n" + proc.stderr, end="" if proc.stderr.endswith("\n") else "\n")
    print(f"--- rc {proc.returncode}")
    return proc


def gate_passed(repo: pathlib.Path, argv: list[str], label: str) -> bool:
    """A gate that writes is a gate that can fail: a non-zero rc must stop the landing."""
    return run_gate(repo, argv, label).returncode == 0


def foreign_locks(repo: pathlib.Path, family: str) -> dict[str, bytes]:
    """``{versions/<line>/<version>/asset_lock.json -> bytes}`` for every family but this one.

    The zero-drift guard compares this before and after the writing gates. It is a BYTE
    comparison, not a parse of the gates' stdout: the previous version counted ``unchanged``
    lines, of which the second ``--update-locks`` run can never produce a foreign one (the
    first run already rewrote them), so it reported "0 checked" and passed over its own
    collateral. Bytes cannot be talked out of a difference.
    """
    root = repo / "rl_exp" / "versions"
    snap: dict[str, bytes] = {}
    for path in sorted(root.glob("*/*/*/asset_lock.json")):
        rel = path.relative_to(root)
        if rel.parts[0] == family:
            continue
        snap[rel.as_posix()] = path.read_bytes()
    return snap


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------


def declare_agent_leaves(diff_path: pathlib.Path, target: Target) -> bool:
    """Put this version's declared agent values into the emitted declaration, or refuse.

    The declaration is computed from the runner cfg, so an entry it does not carry means the cfg
    never sets that field -- which is exactly the state worth failing on (an unnamed log directory,
    or a version that inherits another version's iteration budget by not setting one). The value is
    written ahead of the TODO reason: the value is a declaration, the reason is still the author's.
    """
    declaration = json.loads(diff_path.read_text(encoding="utf-8"))
    allowed = ((declaration.get("agent") or {}).get("allowed")) or {}
    expected = {
        "experiment_name": f"{target.experiment_name} -- one version, one log directory (versioning.mdc A)."
                           " TODO: say why this version needs its own",
    }
    if target.max_iterations is not None:
        expected["max_iterations"] = f"{target.max_iterations} -- declared with this version (--max-iterations)." \
                                     " TODO: say why this budget"
    missing = [path for path in expected if path not in allowed]
    if missing:
        print("*** REFUSED: the runner cfg this line's recipes name does not set " + ", ".join(missing)
              + " (no such leaf in the emitted declaration), so the declared value could not be checked.")
        return False
    allowed.update(expected)
    diff_path.write_text(json.dumps(declaration, indent=2, sort_keys=False) + "\n", encoding="utf-8", newline="\n")
    print("  declared agent leaves: " + ", ".join(f"{k}={v.split(' ')[0]}" for k, v in expected.items()))
    return True


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = pathlib.Path(args.root).resolve() if args.root else _REPO
    target = Target(
        family=args.family,
        line=args.line,
        version=args.version,
        experiment_name=args.experiment_name or f"{args.family}_{args.version}",
        max_iterations=args.max_iterations,
    )
    today = datetime.date.today().isoformat()
    notes: list[str] = []

    print(f"repo root   : {repo}")
    print(f"target      : versions/{target.family}/{target.line}/{target.version}/  (line {target.key!r})")
    print("sources     : this line's own params yaml, its registered recipe keys, the family's urdf/usda"
          " -- no other family is read")
    print(f"experiment  : {target.experiment_name}")
    print(f"mode        : {'APPLY' if args.apply else 'DRY RUN'}  force={args.force}")

    print("\npreconditions:")
    checks, problems, facts = preconditions(repo, target)
    for label, ok, path in checks:
        print(f"  {'ok     ' if ok else 'MISSING'} {label:<14} {path}")
    if facts["recipe_keys"]:
        print(f"  ok      recipes        {len(facts['recipe_keys'])} key(s) for the line: {facts['recipe_keys']}")
        print(f"  ok      recipe chosen  {facts['recipe_key']}  (diff.json 'recipe')")
    if facts["wiring"]:
        print(f"  ok      wiring class   {facts['wiring']}  (diff.json base.wiring)")
        print(f"  ok      stock base     {facts['stock_class']}  (framework cfg it is compared against)")
    if not args.experiment_name:
        notes.append(f"--experiment-name omitted: declared as {target.experiment_name} (one version, one log directory)")
    if problems:
        print("\nREFUSED -- the line is not ready to land a version:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    # --- what would be written -------------------------------------------------------
    dev_yaml = repo / "rl_exp" / "versions" / target.family / target.line / f"{target.line}_params.yaml"
    version_dir = dev_yaml.parent / target.version
    family_path = repo / "rl_exp" / "versions" / target.family / "FAMILY.md"
    artifacts: list[tuple[pathlib.Path, bytes, str]] = [
        (
            version_dir / f"{target.line}_params.yaml",
            dev_yaml.read_bytes(),
            f"frozen copy of the dev yaml {dev_yaml.relative_to(repo)} -- byte-identical, read by every versioned task.",
        ),
        (version_dir / "base.json", base_json(target).encode("utf-8"), ""),
        (version_dir / "PLAN.md", _plan_md(target, today).encode("utf-8"), ""),
        (version_dir / "NOTES.md", _notes_md(target, today).encode("utf-8"), ""),
    ]
    if family_path.exists():
        notes.append(
            f"versions/{target.family}/FAMILY.md already exists: not touched. Paste the version row printed"
            " below (the gate matches '| <line>/<version> |' exactly)."
        )
    else:
        artifacts.append((family_path, family_md(target, facts, today).encode("utf-8"), ""))

    print("\nfiles this run would write:")
    for path, data, preview in artifacts:
        state = "exists -> skip" if path.exists() and not args.force else ("exists -> overwrite (--force)" if path.exists() else "new")
        print(f"  [{state:<24}] {path.relative_to(repo)}   ({len(data)} bytes)")
    print(
        f"  [computed at apply time] versions/{target.family}/{target.line}/{target.version}/diff.json"
        "  <- rl_exp/tools/pipeline/emit_diff_declaration.py, derived from THIS recipe's own resolved cfg"
        " (it reads the frozen params, so it cannot be previewed in a dry run)"
    )
    print(
        f"  [gate product, not written here] versions/{target.family}/{target.line}/{target.version}/asset_lock.json"
        "  <- check_dr_parity.py --update-locks --family <family> (--apply only)"
    )

    print("\n--- artifacts in full (nothing written yet)")
    for path, data, preview in artifacts:
        print(f"\n===== {path.relative_to(repo)} =====")
        print(preview or data.decode("utf-8"), end="" if (preview or data.decode("utf-8")).endswith("\n") else "\n")

    print("\n--- pasted by hand (this tool never edits a shared document)")
    print(f"FAMILY.md  versions/{target.family}/FAMILY.md -> 版本历史 表加一行:")
    print(f"  {family_row(target, today)}")
    print("FILEMAP.md -> 版本线目录 表加一行（版本目录不再逐条登记）:")
    for row in filemap_rows(target):
        print(f"  {row}")
    print(f"runner cfg (rl_exp/tasks/agents/rsl_rl_ppo_cfg.py): the class named by this line's recipe keys"
          f" must declare experiment_name={target.experiment_name!r}"
          + (f" and max_iterations={target.max_iterations}" if target.max_iterations is not None else "")
          + "; the emit step below refuses if it does not.")

    if not args.apply:
        print("\n--- DRY RUN: nothing written.")
        print(f"  would run: emit_diff_declaration.py --line {target.key} --version {target.version} --out <version_dir>/diff.json")
        print(f"  would then check: the emitted agent leaves carry {target.experiment_name!r}"
              + (f" and {target.max_iterations}" if target.max_iterations is not None else ""))
        print(f"  would run: check_cfg_lock.py --update --line {target.key} --reason {args.reason or '<--reason>'!r}")
        print(f"  would run: check_dr_parity.py --update-locks --family {target.family}")
        print("  would check: every OTHER family's asset_lock.json byte-identical before vs after")
        print("  note: without --apply there is no asset_lock.json in the new version directory, so")
        print("        check_version_docs.py reports that piece missing until the generators run.")
        for note in notes:
            print(f"  note: {note}")
        return 0

    if not args.reason:
        print("\nREFUSED: --apply needs --reason (check_cfg_lock.py refuses a golden rewrite without one, and a")
        print("         re-run after the refusal would still know why it was written).")
        return 1

    boundary = repo / "rl_exp" / "versions" / target.family
    print("\n--- writing")
    written = skipped = 0
    for path, data, _ in artifacts:
        target_path = path.resolve()
        if boundary.resolve() not in target_path.parents:
            print(f"  REFUSED: {target_path} is outside {boundary} -- this tool writes only its own family.")
            return 1
        if target_path.exists() and not args.force:
            print(f"  skip  {path.relative_to(repo)} (already exists; --force overwrites)")
            skipped += 1
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        print(f"  write {path.relative_to(repo)}")
        written += 1
    print(f"  {written} written, {skipped} skipped")

    if repo != _REPO:
        print("\n--- gates skipped: --root points at a copy, not this repo (emit_diff_declaration,")
        print("    check_cfg_lock and check_dr_parity all resolve the recipe/line registries through the")
        print("    real repo root, so running them here would read and lock the wrong tree). Missing from")
        print(f"    this copy until they run for real: {version_dir.name}/diff.json and the lock products.")
        for note in notes:
            print(f"note: {note}")
        return 0

    # The difference declaration is computed AFTER the frozen params land, because building the recipe
    # reads the versioned yaml: it is a product of the cfg THIS family actually resolves, not a copy of
    # another family's declaration (see emit_diff_declaration.py for why that distinction matters).
    if not gate_passed(
        repo,
        ["rl_exp/tools/pipeline/emit_diff_declaration.py", "--line", target.key, "--version",
         target.version, "--out", str(version_dir / "diff.json")],
        "emit_diff_declaration --out diff.json",
    ):
        print("*** REFUSED: the difference declaration could not be computed, so this version has no")
        print("***          hard A declaration -- nothing to check the built cfg against.")
        return 1
    if not declare_agent_leaves(version_dir / "diff.json", target):
        return 1

    before = foreign_locks(repo, target.family)

    print(f"\n--- zero-drift guard: {len(before)} asset_lock.json outside {target.family} snapshotted before the writing gates")
    if not gate_passed(
        repo,
        ["rl_exp/tools/verify/check_cfg_lock.py", "--update", "--line", target.key, "--reason", args.reason],
        "check_cfg_lock --update",
    ):
        print("*** REFUSED: check_cfg_lock --update failed -- the golden may or may not have been rewritten;")
        print("*** inspect it before re-running (a landed version with an unwritten golden is a silent pass).")
        return 1
    if not gate_passed(
        repo,
        ["rl_exp/tools/verify/check_dr_parity.py", "--update-locks", "--family", target.family],
        "check_dr_parity --update-locks --family",
    ):
        print("*** REFUSED: check_dr_parity --update-locks failed -- no lock was written for this version.")
        return 1

    after = foreign_locks(repo, target.family)
    if not before:
        print("*** RED: there is no asset_lock.json outside this family to compare against, so the guard")
        print("***      would pass while checking nothing. Land another family first, or check by hand.")
        return 1
    drift = [rel for rel in sorted(set(before) | set(after)) if before.get(rel) != after.get(rel)]
    if drift:
        print("*** RED: this run reached outside its family -- foreign asset_lock.json bytes changed:")
        for rel in drift:
            print(f"***   {rel}")
        print("*** (or the tree already carried asset drift before this run: run check_dr_parity.py alone first)")
        return 1
    print(f"OK: {len(before)} foreign asset_lock.json byte-identical before vs after; "
          f"this run wrote only {target.family}.")
    for note in notes:
        print(f"note: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
