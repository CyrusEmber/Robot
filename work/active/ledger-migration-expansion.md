---
id: ledger-migration-expansion
title: 扩大迁移：HARNESS → PLAN → ACCEPTANCE 的逐段分流
scope: ablation_harness, rl_exp/versions/lizard, rl_exp/tools/verify
status: open
landing: ablation_harness/HARNESS.md, rl_exp/versions/lizard/PLAN.md, rl_exp/versions/lizard/ACCEPTANCE.md
next: 开**批 1 = HARNESS**：逐项确认状态、机制落点、可执行关闭条件，迁成事项文件，**同一变更内删除旧正文、原行只留 id 与指针**，然后按下面四项走查验收（批 0 已完成：见"批 0 落地"）。批 2 = PLAN、批 3 = ACCEPTANCE 保持不动
close_when: 三批各自验收通过并留下记录即关。每批的验收（主判据，人工走查）= **可定位 / 可执行 / 可关闭 / 无约束遗漏**；走查必须真的沿"下一步 → 观测 → 分支结论"走一遍，"确认后可关"式措辞即使过格式检查也判该批不通过。某批不通过则该批重做，不推进下一批
---

## 问题与本次范围

试点（三个事项）已通过：`acceptance/records/2026-09-20-ledger-pilot.md`。本项管**剩下的大文档**，按
"分流压力从小到大"分批，一批不通过就不动下一批。

## 批 0 落地（2026-09-20，已完成）

规则各自回了机制，提案文件删除：**发现命令与三条不变式** → `AGENTS.md`；**事项字段、状态词表、
引用分型、关闭动作、预算上限与"工具不做决定"** → `check_work_docs.py` 的模块文档 + 闸门断言；
**验收记录五节（适用范围 / 验收条件 / 结果 / 证据引用 / 未覆盖边界）** → 同闸门；
**迁移权威性、四项验收、待决项纪律** → 本项。不再有第二处规则源。

## 每批的硬约束

- **迁移权威性**：一个事项的迁移必须在**同一变更**内完成"建立新记录 + 删除旧正文 + 留下定位指针"；
  不允许两份正文并存。接受阶段性覆盖不全，**不接受阶段性双真源**。
- **状态不许顺手改**：迁移只做搬运与成形，**不借迁移顺带实现功能**（功能修复另立事项、另行验收）。
- **不许为了迁完而补写结论**：遇到需要重新决策的语义，**留下待决项**并写明"待谁在哪一步裁决"。
- **历史证据的适用边界要跟着走**：`ACCEPTANCE.md` 里的读数属于当时的协议/套件/资产状态；分流时
  把边界一起搬，**不把历史局部通过升级成当前整体结论**。

## 单一职责的终态（批 1–3 的目标形状）

| 文档 | 保留 | 移出 |
|---|---|---|
| `HARNESS.md`（`isaaclab-eval-harness` 的 SSOT） | 评测台必要说明 | 待办 → `work/`；版本历史/修订记录 → 记录；具体规则 → 对应机制 |
| `PLAN.md` | 目标、路线、优先级原则 | 挂账 → `work/`；已关闭行 → `closed/` |
| `ACCEPTANCE.md` | 迁移期旧路径说明（短） | 历史正文按批次 → `records/` |
| `AGENTS.md` | 读取规则、发现命令（默认入口） | — |

默认读取成本按 **`AGENTS.md` + 列举输出**计；这四份文档都按需按节读，不再声明"必读整份"。

## 明确不保证（别让后人误会）

规则无遗漏 / 迁移语义等价 / 关闭理由充分（机器只验理由存在） / 取消是否合理 / 单一职责（只机检
判据段存在，语义靠评审） / 文档体积等于 token 节省 / 单次对照可外推全仓 / AI 实际会读归档。
前几项需要评审，闸门只能让"便宜路径 = 正确路径"。

## 已知的待决项（迁到哪一批就在哪一批裁决）

- `HARNESS.md` 内部矛盾：一处说当前评测协议是 v2、一处说 v3 ⇒ 批 1 裁决。
- `tasks/components.py`、`tasks/lizard_env_cfg.py`、`tools/verify/teacher_smoke.py` 三处注释仍指向
  FAMILY 的 obs 布局表（该表归 `OBS.md`）⇒ 属代码文件，另行安排。
- `check_pxr_leak.py` / `check_split_probe_wait.py` 的 docstring 里 `docs/pitfalls.md` 路径陈旧 ⇒ 同上。
- FAMILY 版本史行与 FILEMAP 版本目录行都带版本身份（重叠约 70%）⇒ 批 2 裁决。

## 未覆盖边界

本项不实现任何 `HARNESS/PLAN/ACCEPTANCE` 里挂账的功能；不改闸门口径（现有 47 条检查保持）；
不动各家族 `vN/` 目录里的四件套（那由 `check_version_docs.py` 看守）。
