# 验收记录（运行时）— 迁移期指针

按 `ARCH_PLAN.md` v0.12「验收记录通则」保存：每次验收记检查编号、任务 id、命令、代码/框架与资产摘要、
设备与 env 数、seed、输入 checkpoint/样本摘要、预设容差、实际结果、证据路径与通过/失败/未知。

**该通则明确：验收标准是实施要求，不等于已通过。** 只记**实际跑过**的东西；未跑、前提不满足、证据缺失一律
记「未知」，不算通过。离线闸门（`run_offline_checks.bat`）的通过不能替代真跑或隔离重建。

**本文已按主题分流到 `acceptance/records/`，本文只做路由与提示风险，不复述任何结论。**

## 本文用法（迁移期；本节不是验收记录）

- **取结论**：先在下表按主题取**现行记录**，再进那一份读。记录内的「结论」只在它自己的
  「结果」与「未覆盖边界」两节里，别跨记录拼。
- **路由表取代了旧版的「同一主题以最后一个提到它的节为准」**：那条规则判的是**本文的追加序**，
  分流后主题各自成记录 ⇒ 主题级以**现行记录**为准；记录**内部**仍按追加序读，后节可作废前节，
  被作废的旧句保留作留痕。**某主题的前后作废关系写在该记录自己的「适用范围」里**（含它作废了哪条旧读数）。
- **记录的形状由 `rl_exp/tools/verify/check_work_docs.py` 的模块 docstring 看守**：五节按序 ——
  适用范围 / 验收条件 / 结果 / 证据引用 / 未覆盖边界。记录的「未覆盖边界」＝ 该主题"不得据此宣称"的边界。
- **未闭合项的读法**：意图侧 = `work/active/*.md` 与 `work/closed/<年>/`（挂账已整体迁进 `work/`，
  `versions/lizard/PLAN.md` §5 只剩「原行 → 事项」映射表）；评测台侧 = `ablation_harness/HARNESS.md` 的
  挂账节（正文已迁 `work/`，本表只留 id 与指针）；**验收侧开着的项写在各记录的「未覆盖边界」里**
  （如 `社会控制`、`静默跳过`、`不可复跑`、`首回合失败` 等无对应挂账行）。**注意 `work/` 尚未覆盖全部
  未闭合项**（已知例：obs 三张手抄表合口曾只活在记录里，2026-09-21 才另立
  `work/active/obs-three-tables-merge.md`）⇒ 在逐项承接完成前，**不得**说"未闭合项都在 `work/` 里"。

### 读本文必知的通读口径（实测，截至 2026-09-20）

1. **历史记录里的 `[N]` 是当次运行编号，不是闸门身份**（`OFFLINE_CHECKS.md` §1：新条目追加、旧条目退役、
   历史记录按当时的 commit 解读，新记录同时引用脚本名）⇒ **别跨节按编号追**。套件总条目数另受
   `MAX_CHECKS` 棘轮管（45 → 46 于 2026-09-20；**当前值以 `rl_exp/tools/verify/offline_suite.py` 的
   常量为准，本文不复制**）⇒ 各节的成功行读数**只在当日 commit 上成立**。
2. **「已修」与「仍是缺口」并存**：`ClassVar 真缺口未修`（读取侧，
   `2026-09-16-lizard-builder-hard-a.md`）与 `不再有任何 ClassVar 缺口行`（台账打印，
   `2026-09-17-lizard-entry-switch-and-declaration-gap.md`）两处都未在同一句区分 —— 两句都对，指的不是同一件事。
   另有旧边界被后节声明失效而原文保留，**两条已知作废**（都在记录的「适用范围」里带前向指针）：
   - `硬 A 前置未满足`（旧 §B0）被「B1 · 组件库切片 2」判`自此失效` ⇒ 现记在
     `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`；
   - `硬 B 只覆盖 env cfg`（旧 §B2/B4）被「B4 · 硬 B 加齿」判`自此失效` ⇒ 现记在
     `acceptance/records/2026-09-17-lizard-hard-b-difference-declarations.md`。
   **⇒ 一条被作废的句子，一律从作废它的那节读。**

## 主题 → 现行记录

| 主题 | 现行记录 |
|---|---|
| 续训状态层：载荷 / 指纹 / 适配器（离线 S01–S10 + B 层）、C 层真跑、恢复演练、运行记录 R1–R10 | `acceptance/records/2026-09-15-lizard-resume-payload-chain.md` |
| 配方线生命周期与身份映射（L01/L05/L06 离线半）、A0 布局迁移与独立审核、版本类体删除 | `acceptance/records/2026-09-16-lizard-layout-migration-lifecycle.md` |
| 组件库 B1 六片、单写者范围、`_load_params` 收敛 | `acceptance/records/2026-09-16-lizard-component-library-b1.md` |
| 冻结基线（B0）：锚 / 比较口径 / `[35]` 看守 / 四次合法重锚 / 硬 A 前置 | `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md` |
| 构建器与硬 A（B3）：机制、按版本元素化、`[41]` 覆盖钉数 / 缺口台账 / 逐步归属 | `acceptance/records/2026-09-16-lizard-builder-hard-a.md` |
| 硬 B 差异声明：baseline → v14 试点 → main 12 条 → 家族三条、三类作者 | `acceptance/records/2026-09-17-lizard-hard-b-difference-declarations.md` |
| 声明载体与接线对账、入口切换（C2 机制 / C4）、生命周期收缩、声明缺口清空 | `acceptance/records/2026-09-17-lizard-entry-switch-and-declaration-gap.md` |
| obs 协议契约与宽度、live 契约、家族宽度批准、`dims_digest` 与 `evidence` | `acceptance/records/2026-09-16-lizard-obs-protocol-gate.md` |
| eval 记录（3.2）、地形映射（3.3）、记录写侧的评审修正 | `acceptance/records/2026-09-17-lizard-eval-record-and-terrain-map.md` |
| 主线真跑收口、L03 真跑臂（arm2/arm3）、`[48]` 等待机制闸 | `acceptance/records/2026-09-18-lizard-mainline-run-closeout-l03.md` |
| 基线线独立化收尾、摘要对 EOL 敏感（已修）、固定窗口评测入口 | `acceptance/records/2026-09-20-lizard-baseline-line-eol-and-fixed-window-eval.md` |
| 冻结基线第三次与第四次重锚：baseline `cfg_lock.json`（v2 落地；v2 头链终止改判据；v1 两条任务两轮均逐字段未变） | `acceptance/records/2026-09-21-baseline-cfg-lock-rebaseline.md` |
| 地形产物一致（几何 digest / 起伏 / 再生核验） | `acceptance/records/2026-09-20-lizard-terrain-artifacts.md` |

**本表的范围**：只列**从本文迁出去的主题证据**（分流时 12 条，之后随新主题增行），**不是**验收记录的总
目录。挂账已迁进 `work/`；**迁移审计记录**（`2026-09-20-doc-read-cost-baseline`、`2026-09-20-ledger-pilot`、
`2026-09-20-harness-migration`、`2026-09-21-plan-migration`、`2026-09-21-acceptance-ledger-split`、
`2026-09-20-baseline-flat-eval-protocol`）不在此表，入口是引用它们的事项 —— 前五份经
`work/closed/2026/ledger-migration-expansion.md`，最后一份经 `work/active/baseline-v2-recipe.md` 等
（另见 `FAMILY.md` 与 `baseline/v2/PLAN.md`）。要找"某份记录为什么存在"，走 `work/` 的 `evidence` 字段。

## 旧路径说明（找旧节 → 去记录）

| 旧节（本文 2026-09-20 之前的标题） | 现所在记录（同上表文件） |
|---|---|
| §1.2b · §1.3a · §1.5a · §1.4a · §1.4b · §Step 1 汇总复核 | `2026-09-15-lizard-resume-payload-chain.md` |
| §2.1 · §2.1b · §2.4（A0 + 独立审核与修复） · §2.4 收尾（含追加 2026-09-18 ①②③） | `2026-09-16-lizard-layout-migration-lifecycle.md` |
| §B1 · 组件库切片 1–6（切片 1 的 `B0 追加`①②③④ 与切片 2 的 `B0 结论文更新`除外） | `2026-09-16-lizard-component-library-b1.md` |
| §B0 · §B1 切片 1 的 `B0 追加`①②③④ · §B1 切片 2 的 `B0 结论文更新` | `2026-09-16-lizard-frozen-baseline-reanchors.md` |
| §B3 · 硬 A：构建器机制 · §B3 · v5 元素化 · §B3 · v6–v14 元素化 · §B3 收尾 · `[41]` 的三条纪律 | `2026-09-16-lizard-builder-hard-a.md` |
| §B2/B4 · baseline 线接入 + 硬 B 清单 · §B4 · 硬 B 加齿 · §B4 · 谱系口径（v14 试点） · §B4 · main 线 12 条 · §硬 B 追加（2026-09-18） | `2026-09-17-lizard-hard-b-difference-declarations.md` |
| §声明载体与接线对账 · §入口切换的机制与第一档真跑（含生命周期收缩、L02 补记、两处边界） · §C2 收尾 · 翻注册表 · §收掉最后一条声明缺口 | `2026-09-17-lizard-entry-switch-and-declaration-gap.md` |
| §3.1（含结构性风险处置 8–11 条） · §3.1e · §3.1e 补账 · §3.1a 追加 | `2026-09-16-lizard-obs-protocol-gate.md` |
| §3.2 · §3.3 · §评审修正 | `2026-09-17-lizard-eval-record-and-terrain-map.md` |
| §主线真跑收口 + L03 真跑臂 | `2026-09-18-lizard-mainline-run-closeout-l03.md` |
| §追加（2026-09-20）基线线独立化收尾 · 摘要对 EOL 敏感 · 固定窗口评测入口 | `2026-09-20-lizard-baseline-line-eol-and-fixed-window-eval.md` |
| §追加（2026-09-20）· 地形产物一致 | `2026-09-20-lizard-terrain-artifacts.md` |

迁移按**同一变更内建新删旧**：旧节正文已搬入对应记录并在本文删除，旧标题与旧路径只保留在此表里
（§1.2b 的「本文用法」与 §开始处的通则留在本文抬头，不回填进记录）。
