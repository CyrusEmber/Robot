---
id: body-swap-and-version-retire
title: 换代不换家族：新机体走新路径、旧机体版本退休、资产锁只冻结一次
scope: rl_exp/versions, rl_exp/tools/verify, rl_exp/tools/runrecord, .codemaker/rules
status: open
landing: .codemaker/rules/versioning.mdc, rl_exp/tools/verify/check_dr_parity.py, rl_exp/versions/lines.json, rl_exp/tools/runrecord/lifecycle.py, rl_exp/tools/verify/check_contact_ownership.py
next: ① **已拍板**：退休只有一种，条目只记 `retired` + `retired_at` + `reason`（原因写文字）；先因算法退休、后来机体也淘汰 ⇒ 不升级分类、不重新退休（换代检查只看它是否已 retired）。**换代检查（不是退休类型）的输入 = 当前机体**：该家族**活跃线** dev yaml 声明的规范化 `usd_path`，不取自任何退休条目字段；多活跃线不一致或活跃线 dev 不声明 ⇒ 拒绝；**无活跃线的家族不参与本检查**（与 `_active_lines` 口径一致，否则全退休的 lizard 家族会红）。**判据（CI 无参数）**：该家族已登记冻结版本中，规范化 `usd_path` ≠ 当前机体且有效状态非 retired ⇒ 红并列出；不读任何退休声明，故"漏写条目"结构性不可能。② 规则：`versioning.mdc` 的"构型变更必换家族"改为"采用新机体 ⇒ 依赖旧机体的冻结版本必须退休"；两条边界：只试验未提交采用不触发、改回路径不撤销退休（= 一次新的采用动作）。③ 身份：`lines.json` 线条目内加 nested `versions` 子映射（只记 status / retired_at / reason；`active` 出现即拒；缺省继承线状态；线 retired 优先）；状态合成落 `lifecycle.identity()` 一处，`judge` 及用例表不变。④ 锁构造：`_lock_files` 按该版本 yaml 的 `usd_path` + 其 URDF + URDF 引用解析出的文件 + 该 yaml；URDF **有限兼容解析**（先 usd 同目录 `<stem>.urdf`，缺失回退 `versions/<family>/<family>.urdf`），已冻结 yaml 与锁不动；`--update-locks` 只创建缺失的锁、要求 `--version`、退休版本一律拒绝。⑤ 检查：退休版不要求锁、不读锁；未退休冻结版必须有锁（缺失或摘要不符即红）；两个集合——全部已登记版本供身份归属与孤儿锁（真无主锁仍红），活跃版本供资产验收；`_urdf_refs` 参数化到 urdf 路径并逐份检查活跃版本；`check_asset_isolation` 与 ① 共用同一"当前机体"解析器（读它的 usd + urdf + 其引用；跨家族"同一批文件"比当前机体的文件集；无活跃消费者的退休资产不要求覆盖、缺失不红）；`check_version_docs` 四件套对退休版豁免 `asset_lock.json`（PLAN/NOTES/yaml 仍要求）；`check_contact_ownership.py:151` 家族改走路由。⑥ 退役动作：同变更删除退休版的 `asset_lock.json`（历史由 Git 保留；删锁 ≠ 删资产），范围清单（被要求退役的版本 + 命中路径）写入 `acceptance/records/`；docstring、锁内 `note`、报错句里"intentional retire + --update-locks 刷新"改为"锁只冻结一次"，夹具同步。⑦ v1 具名缺口记录（机体缺陷已被替代、公共 USD 被覆盖、原 run 无资产字段、不承诺恢复）入 `acceptance/records/`。⑧ 依赖与并行（按文件冲突切，不按步骤数）：**主链＝单文件串行** `check_dr_parity.py` = ④ 锁构造 → ⑤ 检查 → ① 换代检查（三者共用 `_lock_files` 与"当前机体"解析器）；② 规则正文与 ⑥/⑦ 记录收尾写。**旁链 B/C/D 已落**：`effective_status` 落 `check_recipe_registry`（线状态优先，启动侧经 `lifecycle.identity()` 消费）、`check_version_docs` 齐件按版本状态取值、`check_contact_ownership` 家族走 `obs_protocol.family_of`；反证与读数见 `acceptance/records/2026-09-30-version-exception-identity-and-family-route.md`。**接口先行**只剩 `current_body(family)` 待主链定义 —— 它是 ① 与 ⑤ 的共用件，`effective_status(line, version)` 已定。
close_when: (a) 四侧落地且 `run_offline_checks.bat` 全绿；(b) 破坏测试逐条咬住——命令覆盖已有锁(拒) / 换路径却不写退役条目(红) / dev 指向淘汰机体(红) / 活跃线 `usd_path` 不一致(拒) / 活跃版资产缺失或缺锁(红) / 草稿 URDF 引用越界 / 草案写入面与冻结锁路径重叠；反向——退休版资产缺失或清理(不红) / 退休版已删锁(不红) / `check_version_docs` 对退休版不红 / 真无主锁(仍红) / 退休版新训续训(拒) / 清理退休机体目录后其余闸门仍绿；(c) v1 缺口记录见 ⑦；读数入 `acceptance/records/`。
depends_on: asset-tree-per-family
evidence: acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation, acceptance/records/2026-09-30-version-exception-identity-and-family-route
---

## 问题与本次范围

骨骼未定型 ⇒ 换代频繁；"构型变更必换家族"过重，而"用新机体刷新旧版本的锁"会把已训配方重绑到它没训过的机体（已发生一次，事实归
`2026-09-28-lizard2-foot-hull-and-asset-isolation`）。本项把换代收敛在现有 vN 链上，并补两处新路径引入的缺口：草稿 URDF 的引用合法性、家族推导不再从路径反推。

不做：bN 目录身份层、身体注册表、退休分类字段、退休条目里写资产路径、`lock_sha256`、通用重锁开关、恢复演练义务、manifest 扩字段。

## 切法依据

- 退役 = 放弃该版本的复现承诺，不是豁免；算法、机体、方案淘汰都可触发，但不得用于把检查红了糊过去。
- 退休即删锁：历史由 Git 承载（不保证内容正确），删锁 ≠ 删资产；活跃锁仍由摘要比对兜底，离线闸门不宣称能检测手工伪造。
- 诊断按家族声明取当前树：当前机体唯一 ⇒ 对活跃版正确，`meshes_dir` 不改；代价是退休版诊断读数不代表当时机体。
- 换代若被拆成多次提交，中间态必然红灯——设计如此，合进一次变更即转绿。
- 两具身体并行训练的出口 = 新开家族或届时另立隔离方案，不在本项放宽判据。
- 退休不自动删文件；清理是另一次决策，后果当时记一行。

## 与邻近事项的边界

- `asset-tree-per-family`：家族网格树声明是本项前提，本项只改其消费者与锁集合构造。
- `lizard2-family-landing`：v2 配方决策归它。
- `teacher-snapshot-asset-sync` / `teacher-literal-parity-gate`：教师侧手抄同步不在范围内。
