# 仓库结构评审：变化向量、退休线残留与治理占比（2026-10-09）

## 适用范围

对 2026-10-09 HEAD（`8435482`）的仓库结构做一次读数型评审，用于给两项在办事项定依据：
`work/active/retired-family-code-prune.md`、`work/active/gate-admission-rule.md`。
只读 git 历史、文件清单、离线套件清单与 import 关系；不跑训练、不跑仿真、不改任何代码与配置。
不判定任何单个闸门"有没有用"，也不替所有者决定删除或规则采纳。

## 验收条件

- 变化向量以 git 历史为据，不以目录观感为据（`.codemaker/rules/architecture.mdc` 第 1 条）。
- 每条发现先分诊为本地问题或结构问题（同规则第 2 条）。
- 读数附读法，别人能在同一 rev 上复读。

## 结果

### 变化向量（`git log --since=2026-09-01 --name-only`，每个 commit 按其触到的路径类别去重计数）

| 类别（路径前缀） | 触到它的 commit |
|---|---|
| 全部 commit | 591 |
| `*.md` 文档 | 423 |
| `rl_exp/tools/verify/` | 234 |
| `rl_exp/tasks/` | 87 |
| `ablation_harness/`（不含 `results/`） | 64 |
| 资产（`meshes` / `blender` / `assets` / `*candidate*`） | 11 |
| **只触 verify / 文档 / `rl_exp/versions/**.json` / 其它杂项** | **365** |

最近两周（10-01 起）的 commit 主题集中在 lizard2 机体：站姿、关节限位、执行器、惯量、自碰撞。
两次退休都源于机体：lizard 整家族 2026-09-22（机体设计缺陷），lizard2 v1/v2 2026-10-08（换机体）。
⇒ 实际变化向量 = **机体 / 资产**；治理体系的重心 = **已训配方的可复现**（冻结、golden、血统、资产锁）。

### 规模（`git ls-files` 逐文件行数，按顶层两级目录汇总）

| 面 | py 行数 |
|---|---|
| `rl_exp/tools/`（其中 `verify/` 96 个文件） | 39092 |
| `rl_exp/tasks/` | 10862 |

### 退休线在主路径上的残留

- 离线套件（`offline_suite.py --list`）48 项里，看守 lizard 退休线专属代码的约 14 项：
  `test_staged_curriculum` / `test_teacher_networks` / `test_student_networks` / `test_v3_curriculum` /
  `test_v5_terrain_sir` / `test_joint_sir` / `test_resume_state` / `check_reward_v13` /
  `check_terminations_v14` / `test_baseline_contract` / `test_baseline_isolation` 等（逐项归属未审，见未覆盖边界）。
- lizard2 任务模块（`lizard2_recipe.py` / `lizard2_env_cfg.py`）只 import `recipe_params` / `play_utils` /
  `recipe_factory`，不 import `teacher_mdp` / `curriculum_state` / `teacher_env_cfg` / parkour / baseline。
- **反向耦合存在**：共用件 `rl_exp/tasks/recipe.py` 直接 import `baseline_*` / `teacher_*` / `lizard_env_cfg` /
  `curriculum_state`；`test_run_manifest.py` import `curriculum_state`；`terrain_preflight.py` import `teacher_env_cfg`。
  ⇒ 删旧线不是"删一组文件"，先要把共用件里对旧线的引用拆出来。
- `work/active/` 27 项里，scope 或标题落在退休线上的候选：`baseline-pre-make-record-check`、`baseline-v2-recipe`
  （状态 `in_progress`，而其线已退休）、`deployment-delay-injection-dr`、`phase2-obs-fidelity`、
  `row-sir-commanded-measurement-defect`、`staged-curriculum-metric-wiring`、`teacher-literal-parity-gate`、
  `teacher-snapshot-asset-sync`、`v7-ghost-leg-implementation`（逐项是否仍对 lizard2 有意义未审）。

### 闸门判"文档一致"而非"行为成立"的已知实例

`rl_exp/versions/lines.json` 中 `lizard/parkour` 的退休理由原文：env 已无法构造，"the offline gates were green over it"，
只有真跑发现。

### 分诊

| 发现 | 分类 | 去向 |
|---|---|---|
| 退休线代码、闸门与事项仍在主路径 | 本地（结构能表达"退休"，只是没执行到代码层） | `work/active/retired-family-code-prune.md` |
| 治理面增长快于产品面、闸门偏声明一致性 | 结构（缺"闸门准入"判据，现有结构无法拒绝一条新闸门） | `work/active/gate-admission-rule.md` |
| `FILEMAP.md` 部分条目写行为细节（违反 `.codemaker/rules/docs.mdc`） | 本地 | 就地压缩，不立项 |
| `ARCH_PLAN.md` 标题仍写"提案，待审核" | 本地 | 就地修，不立项 |
| 仓根约 60 个 `_tmp_*`（已 gitignore） | 本地 | 就地清，不立项 |
| run 记录只在本机、fork 补丁钉死 IsaacLab commit | 结构风险，当前未触发 | 暂不立项；换机或升框架时再评 |

## 善后（2026-10-09 同日：分诊表里"就地修 / 清，不立项"的三条）

- **仓根 64 个 `_tmp_*` 全删**（59 个在根、5 个在 `rl_exp/tools/`，含九份验收记录引用的脚本与原始件 ⇒ 那些
  "复读"路径作废，记录本身已声明它们不入仓）；两个工具的仓根默认输出改落
  `rl_exp/tools/diagnose/out/`（`terrain_preflight.py` 的预览、`baseline_probe.py` 的目视帧）。
- **机制**：`check_suite_banners.py`（本因横幅写出仓根 `config` 而生）加"仓根只许声明项"扫描 —— 按声明判
  （改名成 `helper.py` 一样红），`hooks/pre-commit` 也调它 ⇒ **提交即截止线**；`_tmp_*` 的 gitignore 与命名
  约定保留（工作树的脏判据不受影响）。规则本就写在 `FILEMAP.md`，欠的是闸门。
- **FILEMAP 压缩**：只砍行为细节与溯源（归 docstring / git log），路由判别点与关键开关不动。
- **ARCH_PLAN 标题**去状态；`check_version_docs.py` 的状态扫描从"仅加粗"扩到 **H1 标题行** —— 那行躲了 20 天，
  正因为只扫加粗；带自检用例（旧标题必须变红）。

## 证据引用

- 退休事实：`rl_exp/versions/lines.json`、`acceptance/records/2026-09-22-lizard-family-retirement.md`、
  `acceptance/records/2026-10-08-lizard2-v3-landing.md`。
- 套件清单：`python rl_exp/tools/verify/offline_suite.py --list`。
- import 关系：在仓根对 `*.py` 搜 `^(from|import) .*(teacher_mdp|curriculum_state|teacher_env_cfg|baseline_|parkour_|lizard_env_cfg)`。
- 事项清单：`python rl_exp/tools/verify/check_work_docs.py --list`。

## 未覆盖边界

- 统计脚本是一次性的、未入库；表中类别边界（例如 `decl_json` 只算 `rl_exp/versions/**.json`）照上文复读即可，换边界会换数。
- "约 14 项看守退休线"是按套件条目名与 import 判的，**未逐项确认**是否同时覆盖 lizard2 用到的共用件
  （如 `test_resume_state` 看守的续训状态层被 `dr-widening-policy` 列为 lizard2 未来依赖）。逐项判定归删除清单那一步。
- 治理占比只是规模与 commit 计数，不衡量任何一条闸门拦下过多少真实缺陷；没有这份"命中史"，"闸门过多"只是假设。
- 未评估 `ablation_harness/` 内部结构与 `results/` 入库体量。
