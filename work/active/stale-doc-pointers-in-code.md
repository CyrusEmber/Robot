---
id: stale-doc-pointers-in-code
title: 代码与配置里的旧目标指针：1 处硬错 + 7 处旧编号引用（文档侧不改写）
scope: .codemaker/skills, rl_exp/tasks, rl_exp/tools, ablation_harness, hooks
status: open
landing: .codemaker/skills/tool/isaaclab-task-creator/references/runtime_facts.md, rl_exp/tasks/recipe.py, rl_exp/tasks/teacher_mdp.py, rl_exp/tools/runrecord/binding.py, rl_exp/tools/runrecord/rebuild.py, rl_exp/tools/verify/check_record_bindings.py, rl_exp/tools/verify/test_terrain_geometry.py, ablation_harness/protocols/locomotion_eval_v3.yaml
next: 分两批，只改注释与文档串，不动行为。**批 A（1 处硬错，先做）** = `.codemaker/skills/tool/isaaclab-task-creator/references/runtime_facts.md` 的 `LAYOUT` 行写着"与 `FAMILY.md` 布局表对账"，改指 `rl_exp/versions/lizard/OBS.md`（FAMILY 已声明 obs 契约 SSOT = OBS.md，照旧指针找会落空）。**批 B（7 处旧编号）** = 按下面「批 B 白名单」逐处改指事项或机制（原引用片段才是身份，行号仅供定位）。**冻结与证据类**的 8 处见另一张表、本项不改，理由逐条在表里。**不改写** `acceptance/records/`、`rl_exp/versions/lizard/main/v*/` 与 `work/` 里的历史引用
close_when: 批 A = 该 skill 文件不再把 `FAMILY.md` 当 obs 布局出处。批 B = 白名单 7 处逐处有处置（改指事项/机制，或写明为何只改指向说法），复跑片段匹配后**未处置 0 处**；冻结与证据类不计入该判据。两批各自完成即关；批 B 未完而 A 完，保持 open 并写明剩余数
---

## 现状（2026-09-21 实测）

真正待改 **8 处**（1 处硬错 + 7 处旧编号），全在代码/配置与 skill reference 里；文档侧的历史引用
不在本项。上一版的范围与计数经不起复跑，见「上一版错在哪」。

## 批 B 白名单（7 处；原引用片段 = 身份，行号仅定位）

| 文件 | 原引用片段 | 行 | 目标 |
|---|---|---|---|
| `rl_exp/tasks/recipe.py` | `family PLAN ledger #15 option a` | 275 | `work/closed/2026/sir-criterion-and-obs-layout.md` |
| `rl_exp/tasks/teacher_mdp.py` | `replacing the v5.5 binary terminal proxy (family PLAN ledger #15` | 878 | 同上 |
| `rl_exp/tools/runrecord/binding.py` | `the point of #27 ② is that one commit has one string per run` | 87 | `work/active/record-variant-and-snapshot-specs.md` |
| `rl_exp/tools/verify/check_record_bindings.py` | `before #27 each of them spelled the shared half itself` | 10 | 同上 |
| `rl_exp/tools/runrecord/rebuild.py` | ``PLAN.md`` #18 turned into a gate` | 14 | `work/active/verified-rebuild-rating.md` |
| `rl_exp/tools/verify/test_terrain_geometry.py` | `the claim #18 ① is about` | 130 | 同上（`check_terrain_geometry.py` 的 `foot_relief` docstring） |
| `ablation_harness/protocols/locomotion_eval_v3.yaml` | `(PLAN.md #18 ①)` | 8 | 同上（地形两列退化的机制） |

编号 → 事项取自 `rl_exp/versions/lizard/PLAN.md` §5 的「原行 → 新事项」表（#15 在「已收走」行）。

## 冻结与证据类（8 处命中；本项不改）

| 文件 | 命中 | 不改的理由 |
|---|---|---|
| `rl_exp/fork_patches/local_tree_extras.patch` | 2 | 历史补丁存档：`framework_pin_check.py`（套件 `[1]`）按序应用到 pristine 副本后**逐字节比**，改一字节 `PIN_CHECK` 即红 |
| `rl_exp/fork_patches/train_seed_rng.patch` | 2 | 同上 |
| `rl_exp/versions/lizard/verify_logs/step1-offline-00d0b07-2026-09-15.log` | 4 | `00d0b07` 那次离线跑的真日志，被记录按**当时 commit**引用；改它等于伪造历史证据 |
| `acceptance/records/2026-09-15-lizard-resume-payload-chain.md` | 1 | 已入库验收记录，编号指当时 PLAN；历史记录不改写 |
| `rl_exp/versions/lizard/main/v3/PLAN.md` | 2 | 版本目录历史记录，靠 PLAN §5 的映射解析 |

排除理由按"它是什么"给（存档/pin、真跑日志、已入库证据、版本目录历史），不是按扩展名。

## 上一版错在哪（留痕）

- 批 A 的 5 处**全部落空**（三个代码文件无 `FAMILY` 引用；两处 `docs/pitfalls.md` 已是全路径，文件名
  还写错）—— 真指针在 skill reference，而上一版 `scope` 没覆盖 `.codemaker/skills/`。
- 批 B 的"约 90 处"**不可复现**（`PLAN.md #` 全仓 13 处、`.py` 为 **0**；代码用裸 `#27`/`#18 ①`）
  ⇒ 判据由计数改为白名单。

## 未覆盖边界

- 文档侧的 `PLAN.md #N` / `挂账 #N`（版本目录、记录、`work/` 自身）不在本项，要一并处理须另立。
- 只改注释与文档串，不动行为、不动 golden、不重排导入。
- 指向内容**确实已不存在**（而非搬家）时保留原文并记下，不自行判断删留；白名单是 2026-09-21 的快照，
  不保证 7 处之外再无旧指针（新写的旧式引用要重跑本项的方法）。
