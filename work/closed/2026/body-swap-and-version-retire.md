---
id: body-swap-and-version-retire
title: 换代不换家族：新机体走新路径、旧机体版本退休、资产锁只冻结一次
scope: rl_exp/versions, rl_exp/tools/verify, rl_exp/tools/runrecord, rl_exp/tools/pipeline, .codemaker/rules
status: done
landing: .codemaker/rules/versioning.mdc, rl_exp/tools/verify/check_dr_parity.py, rl_exp/tasks/obs_protocol.py, rl_exp/tools/verify/check_recipe_registry.py, rl_exp/versions/lines.json, rl_exp/tools/runrecord/lifecycle.py, rl_exp/tools/verify/check_joint_layout.py, rl_exp/tools/verify/check_contact_ownership.py
close_when: 四步主体、第三轮两处漏检、以及"先补反证再修"的纪律都满足——每条新判据都在修复前的实现上确认过是红的，各闸门与全套离线检查全绿，记录补完三段 ⇒ 关闭。此前两次"全绿"分别只覆盖四侧骨架与被点名的那四条边界，不足以作为关闭依据（第一次漏掉 5 条路径、第二次漏掉本项第三轮的 2 条）。
depends_on: asset-tree-per-family
evidence: acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation, acceptance/records/2026-09-30-body-swap-and-lock-freeze, acceptance/records/2026-09-30-lizard2-v1-body-gap
outcome: 三段走完。**第一段**四侧骨架：规则（`versioning.mdc` 越级段：换家族只留给明确另立的设计，本体/构型迭代 = 同家族机体换代，采用新机体时旧机体上所有冻结版本同变更退休，锁只写一次）；身份（`lines.json` `versions` 子映射 + `effective_status` 唯一读法，`runrecord/lifecycle.py` 消费）；锁（引用驱动构造 + `update_asset_locks --version` 只创建）；检查（`check_asset_locks` 双集合 + 退休跳过、`check_asset_isolation` 用"当前机体"、新增 `check_body_swap`）。**第二段**补齐 5 条此前未覆盖的路径（活跃线内单版本退休+旧资产清理、整族无活跃消费者+清理、新布局缺 URDF 的回退、锁内额外文件被改、显式 active 例外/versions 非法类型），并做成两段可重跑夹具：`_self_test_swap_rehearsal` 在临时家族走完整换代（冻结+落锁 → 采用新机体 → 报出漏退 → 退休删锁 → 清理旧资产 → 新版本先红后落锁），五阶段既断言必须出现的报错也断言处理后的安静。**第三段**修两处实际漏检：①`obs_protocol.urdf_refs` 原用正则 `<mesh filename="…"` ⇒ 单引号或属性换序时网格不进锁、改网格不报红，改为标准库 XML 解析（按 localname 找 `mesh`），且**存在但不可解析 ⇒ `ProtocolError`**（"没解析到"不得写成"没有网格"）；②`check_asset_isolation` 的"活跃家族必须有树声明"原用 `_VERSIONS.glob("*/*.urdf")`（只看旧位置）⇒ 机体在自己目录的家族整族漏检，改为**从活跃配方发现家族**。两处都先复现、再**把修复临时回退确认新断言会失败**、然后恢复。拒绝语义同段收紧：状态必须明确 active 才允许写锁、`O_CREAT|O_EXCL` 独占创建、失败即删半成品并写明 nothing was written；并修掉 `_active_lines` 把顶层 `_missing` 当子键读的 bug。**最终读数**：`ALL_OFFLINE_CHECKS_PASSED (47/47 in 61.1s)`、`PARITY_OK`（七个夹具）、`RECIPE_REGISTRY_GATE_OK`（25 拒绝 + 10 读法）、`VERSION_DOCS_OK`、`WORK_DOCS_OK`；`rl_exp/versions` 无工作树差异。**未覆盖**：真实家族的换代仍未发生（演练是夹具内的）；两个需仿真器的调用方（`check_joint_layout`、`check_contact_ownership`）已改为共用解析器并通过语法编译，但未在仿真中实跑；无活跃消费者的家族整族跳过隔离检查 ⇒ 旧家族 `lizard` 的 URDF/消费树分歧不再被打印，处置归 `asset-tree-per-family`；相关改动尚未提交。三段读数与两轮基线证据见 `2026-09-30-body-swap-and-lock-freeze.md`。
---

## 问题与本次范围

骨骼未定型 ⇒ 换代频繁；"构型变更必换家族"过重，而"用新机体刷新旧版本的锁"会把已训配方重绑到它没训过的机体（已发生一次，事实与缺口分归
`2026-09-28-lizard2-foot-hull-and-asset-isolation` 与 `2026-09-30-lizard2-v1-body-gap`）。本项把换代收敛在现有 vN 链上。

三段：第一段落四侧骨架；第二段补齐四条边界并做完整换代演练；第三段修两处实际漏检（URDF 引用解析漏网格、新布局家族绕过隔离检查）。全程不引入退休分类、不加身体身份层、不加恢复义务，也不迁移现有身体、不改冻结配方、不刷新旧锁、不补做 v1 恢复。

不做：bN 目录身份层、身体注册表、退休分类字段、退休条目里写资产路径、`lock_sha256`、通用重锁开关、恢复演练义务、manifest 扩字段。

## 切法依据

- 退役 = 放弃该版本的复现承诺，不是豁免；算法、机体、方案淘汰都可触发，但不得用于把检查红了糊过去。
- 退休即删锁：历史由 Git 承载（不保证内容正确），删锁 ≠ 删资产；活跃锁仍由摘要比对兜底，离线闸门不宣称能检测手工伪造。
- 诊断按家族声明取当前树：当前机体唯一 ⇒ 对活跃版正确，`meshes_dir` 不改；代价是退休版诊断读数不代表当时机体。
- 换代若被拆成多次提交，中间态必然红灯——设计如此，合进一次变更即转绿。
- 两具身体并行训练的出口 = 新开家族或届时另立隔离方案，不在本项放宽判据。
- 退休不自动删文件；清理是另一次决策，后果当时记一行。
- **兼容只对已声明的旧布局成立**：把"兼容旧布局"写成"任何缺文件都去找旧文件"，会让新 USD 与旧 URDF 错配。
- **解析必须对写法不敏感，失败必须出声**：一个只认某一种写法的解析器会把"没解析到"写成"没有网格"，而空集合在各处都被读成"干净"。
- **判据的发现面必须覆盖它要守的布局**：从目录位置发现家族，只能在旧布局下有效——新布局必须从配方发现。

## 与邻近事项的边界

- `asset-tree-per-family`：家族网格树声明是本项前提，本项只改其消费者与锁集合构造。**已记录的后果**：第一步 (b) 让无活跃消费者的家族整族跳过隔离检查后，旧家族 `lizard` 的 URDF/消费树分歧不再被打印 ⇒ 该分歧的唯一自动提示消失，处置归那个事项。
- `lizard2-family-landing`：v2 配方决策归它。
- `teacher-snapshot-asset-sync` / `teacher-literal-parity-gate`：教师侧手抄同步不在范围内。
