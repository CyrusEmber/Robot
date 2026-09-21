# 版本记录漂移审计（NOTES 手写差异段 vs diff.json）

## 适用范围

覆盖 `rl_exp/versions/` 下带 `diff.json` 的 16 个版本目录：NOTES 手写差异段与其声明的对照，
外加 `work/` 台账入站引用的两次扫描（路径式 / id 式）。时点 2026-09-21，计数与样本不回填后续变化。

不含：`why` 语义漂移的全体普查（只报样本，无自动判据）、冻结历史是否重写（按 A0 口径不改写）、
人读成本（read-cost 口径的 after 读数归试点事项的验收）。

## 验收条件（读侧口径，写在这里便于复测）

- **漂移判定**：NOTES 手写差异段出现"其余照 X / 零变更"式**全量句**，且 `diff.json` 的 `env.allowed` /
  `agent.allowed` 里存在该段未提的路径 ⇒ 记 `notes-stale`。
- **引用判定**：`**/*.md|py|rst` 里形如 `work/active/<id>.md`、`work/closed/<year>/<id>.md` 的路径须存在；
  front matter 的 `depends_on` / `superseded_by` 里裸 id 须能唯一解析。两者只判"存在 / 能否解析"，
  不判语义正确性。

## 结果

**漂移面**：带 `diff.json` 的版本 **16**；带手写差异段 **13**；判 `notes-stale` **3**。

| 版本 | NOTES 的全量句 | 声明里被漏掉的路径 |
|---|---|---|
| `baseline/v2` | "其余逐项照 v1" | `terminations.head_load_contact` |
| `main/v3` | 无全量句，整组声明搬去 PLAN，NOTES 只剩英文散点 | `curriculum.speed_curriculum`、`sim.physics.default.gpu_collision_stack_size`、`pyramid_stairs` / `stepping_stones` / `boxes.proportion` |
| `main/v8` | "reward…零变更"（同文件修订历史却记着 r_slip ×10） | `rewards.feet_slide.weight` |

**根因（样本一致）**：漂移全部落在**修订追加过的路径**上——初版写下的差异段与声明一致，后续修订
（v3.6 / v5.3 / v8.1 / v14.4）只往「修订历史」「目的」段追加，差异段要点不动。失效点集中在全量句。

**声明侧自身的 `why` 漂移（两例，只报样本）**：

- `main/v12/diff.json` 的 `why` 与 `main/v8/diff.json` 逐字相同（"r_slip x10"），而 v12 干的是**撤销** ×10
  ⇒ **方向相反**。路径闸门过（`check_recipe_build.py` 只钉条数与路径），语义无人看守。
- `main/v6` 的 `scene.robot.actuators.spine.{stiffness,damping}` 只写在 `base.json.note` 里 ⇒ 声明文件
  复述了差异列表。

**冻结面**：13 个带差异段的版本里 **5 个已冻结**（6 个 tag：`lizard-baseline-v1`、`lizard-v6`、`lizard-v8`、
`lizard-v8.1`、`lizard-v10`、`lizard-v11.1`），**8 个未冻结**（`baseline/v2`、`main/{v2,v3,v4,v5,v12,v13,v14}`）。
三分之二的漂移点落在未冻结版上。

**入站引用扫描**：路径式 **0** 断链、id 式 **0** 悬空（全仓 `md`/`py`/`rst`）。设计上"active → closed 换路径"
的成本**今天尚未付出**，不等于不会发生。

**机制现状（决定了动作大小）**：`versioning.mdc:52` 的 `copy vN vN+1` 连 `PLAN.md`/`NOTES.md` 正文一起继承
（无脚手架脚本，全仓无 `--new-version`）；per-version 的 NOTES/PLAN 正文**无任何闸门读取**
（`check_version_docs.py:222` 只判存在）；实际运行信息已在 `rl_exp/tools/runrecord/manifest.py:340-400`
（`argv` / `seed` / `num_envs` / `params_version` + `:261` 的 `session_overrides`）。

## 证据引用

- 复测方式：两遍 `python -c` 扫描（路径式：全仓 `md`/`py`/`rst` 抽 `work/(active|closed/<year>)/<id>.md` 与磁盘比对；
  id 式：`work/**/*.md` 的 `depends_on`/`superseded_by` 裸 id 与现存 id 集合比对）。两遍读数均为 0。
- 逐例行号：`rl_exp/versions/lizard/baseline/v2/NOTES.md:17-20`、`main/v13/NOTES.md:21`（首条改为散文、
  无 `## 相对上版 diff` 标题）、四个带标题的 NOTES = `baseline/v1`、`baseline/v2`、`main/v12`、`parkour/v1`。
- 闸门侧：`rl_exp/tools/verify/check_recipe_build.py:88`（`EXPECTED_DIFFS` 只钉条数）、
  `check_version_docs.py:222`（只判四件套存在）、`check_work_docs.py`（记录五节 / 事项形状 / 台账预算）。
- 相关事项：`work/closed/2026/version-doc-single-owner.md`（治理动作，已关闭；读数见
  `acceptance/records/2026-09-21-version-doc-read-cost.md`）、
  `work/closed/2026/ledger-inbound-reference-scan.md`（入站引用扫描，已收）。

## 未覆盖边界

- `why` 语义漂移**无自动判据**，本记录只报 2 例样本，不构成"其余 why 正确"的结论。
- 未测人读成本：本记录是 AI 扫描读数，**不得**当作"短摘要 vs 仅链接"两读法的对照。
- 未覆盖 `main/{v0,v1,v7,v9,v15}` 与 `parkour/v1` 的差异段（无 `diff.json` 可比或不在本次对照集）。
- 未裁决冻结历史是否重写；未把历史 stale 记为待办（豁免，不清零）。
- 16 / 13 / 3 是 2026-09-21 的快照，后续开版会让它失真。
