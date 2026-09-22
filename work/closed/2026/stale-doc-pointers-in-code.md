---
id: stale-doc-pointers-in-code
title: 代码与配置里的旧目标指针：1 处硬错 + 7 处旧编号（已关；6 处改指，1 处在冻结协议内不改并写明理由）
scope: .codemaker/skills, rl_exp/tasks, rl_exp/tools, ablation_harness, hooks
status: done
landing: .codemaker/skills/tool/isaaclab-task-creator/references/runtime_facts.md, rl_exp/tasks/recipe.py, rl_exp/tasks/teacher_mdp.py, rl_exp/tools/runrecord/binding.py, rl_exp/tools/runrecord/rebuild.py, rl_exp/tools/verify/check_record_bindings.py, rl_exp/tools/verify/test_terrain_geometry.py
outcome: 批 A 1 处硬错改指：`runtime_facts.md` 的 `LAYOUT` 行不再拿 `FAMILY.md` 当 obs 布局出处，改指 `rl_exp/versions/lizard/OBS.md`（`FAMILY.md` 第 10 行自己声明 obs 契约 SSOT = OBS.md）。批 B 7 处里 6 处改指事项/机制：`recipe.py` / `teacher_mdp.py` 的 `family PLAN ledger #15 option a` → `work/closed/2026/sir-criterion-and-obs-layout.md`；`binding.py` / `check_record_bindings.py` 的 `#27` → `work/active/record-variant-and-snapshot-specs.md`；`rebuild.py` / `test_terrain_geometry.py` 的 `#18` → `work/active/verified-rebuild-rating.md`（映射取自 `rl_exp/versions/lizard/PLAN.md` §5）。第 7 处 `ablation_harness/protocols/locomotion_eval_v3.yaml:8` 的 `(PLAN.md #18 ①)` **不改**：该文件头自述"落库即冻结，只读"，`test_eval_frame_v2.py` 也断言 v3 未被就地编辑，改注释同样是改字节；按 `close_when` 允许的"写明为何只改指向说法"处置 —— 该处说的是地形 rough 两列退化的机制，机制本体在 `ablation_harness/suites.py` 与 `rl_exp/tasks/terrain_geometry.py`，且 v3 已被 v4 supersede，照当前协议走不会落到这一行。复核：全仓片段匹配（`family PLAN ledger #15` / `the point of #27` / `before #27` / `PLAN.md` + 双反引号 + ` #18` / `the claim #18 ①` / `与 FAMILY.md 布局表对账`）除该冻结行外 **0 处未处置**；6 个改动文件 `py_compile` 通过；`check_record_bindings.py` 复跑 `RECORD_BINDING_SINGLE_SOURCE_OK`（178 文件）。无新验收记录：只改注释与文档串，无行为、无 golden、无判据变化。
---

## 处置表（原引用片段 = 身份，行号为改前定位）

| 文件 | 原引用 | 处置 |
|---|---|---|
| `.codemaker/skills/tool/isaaclab-task-creator/references/runtime_facts.md` | `与 FAMILY.md 布局表对账` | 改指 `rl_exp/versions/lizard/OBS.md` |
| `rl_exp/tasks/recipe.py` | `family PLAN ledger #15 option a` | → `option a of work/closed/2026/sir-criterion-and-obs-layout.md` |
| `rl_exp/tasks/teacher_mdp.py` | 同上 | 同上 |
| `rl_exp/tools/runrecord/binding.py` | `the point of #27 ② …` | → `② in work/active/record-variant-and-snapshot-specs.md` |
| `rl_exp/tools/verify/check_record_bindings.py` | `before #27 each …` | → `before that item's ① gate` |
| `rl_exp/tools/runrecord/rebuild.py` | ``PLAN.md`` #18 turned into a gate | → `① of work/active/verified-rebuild-rating.md` |
| `rl_exp/tools/verify/test_terrain_geometry.py` | `the claim #18 ① is about` | → `the claim ① of work/active/verified-rebuild-rating.md` |
| `ablation_harness/protocols/locomotion_eval_v3.yaml` | `(PLAN.md #18 ①)` | **不改**：冻结只读契约文件（理由见 `outcome`） |

## 本项不改的引用（冻结与证据类，8 处命中）

| 文件 | 命中 | 理由 |
|---|---|---|
| `rl_exp/fork_patches/local_tree_extras.patch` | 2 | 历史补丁存档：`framework_pin_check.py`（套件 `[1]`）按序应用到 pristine 副本后**逐字节比**，改一字节 `PIN_CHECK` 即红 |
| `rl_exp/fork_patches/train_seed_rng.patch` | 2 | 同上 |
| `rl_exp/versions/lizard/verify_logs/step1-offline-00d0b07-2026-09-15.log` | 4 | `00d0b07` 那次离线跑的真日志，被记录按**当时 commit**引用；改它等于伪造历史证据 |
| `acceptance/records/2026-09-15-lizard-resume-payload-chain.md` | 1 | 已入库验收记录，编号指当时 PLAN；历史记录不改写 |
| `rl_exp/versions/lizard/main/v3/PLAN.md` | 2 | 版本目录历史记录，靠 PLAN §5 的映射解析 |

排除理由按"它是什么"给（存档/pin、真跑日志、已入库证据、版本目录历史），不是按扩展名。

## 方法（可复跑）

`PLAN.md #` / `挂账 #` 这类编号在代码里是**裸写**的（上一版"约 90 处"不可复现：全仓 `PLAN.md #`
13 处、`.py` 为 **0**，代码用裸 `#27`/`#18 ①`），故判据由计数改为白名单：按原引用片段全仓匹配，逐处处置。
上一版的批 A 5 处**全部落空**（真指针在 skill reference，而那一版 `scope` 没覆盖 `.codemaker/skills/`）。

## 未覆盖边界

- 文档侧的 `PLAN.md #N` / `挂账 #N`（版本目录、记录、`work/` 自身）不在本项，要一并处理须另立。
- 白名单是 2026-09-21 的快照，2026-09-22 复核时 7 处命中全在且行位未变；新写的旧式引用要重跑本项的方法。
- 只改注释与文档串：不动行为、不动 golden、不重排导入；指向内容"确实不存在（而非搬家）"时保留原文并记下。
