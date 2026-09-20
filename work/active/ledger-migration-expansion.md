---
id: ledger-migration-expansion
title: 扩大迁移：HARNESS → PLAN → ACCEPTANCE 的逐段分流
scope: ablation_harness, rl_exp/versions/lizard, rl_exp/tools/verify
status: open
landing: ablation_harness/HARNESS.md, rl_exp/versions/lizard/PLAN.md, rl_exp/versions/lizard/ACCEPTANCE.md
next: 按批推进，一批一验收。**批 0（先做）**：把 `WORK_PLAN.md` 里已成机制的规则收敛进 `AGENTS.md` 与闸门、把未成机制的规则落进本项，然后删除该提案——在它删除前它只是规则的暂存处，不是常驻文档。**批 1 = HARNESS**：逐项确认状态、机制落点、可执行关闭条件，迁成事项文件，**同一变更删除旧正文、原行只留 id 与指针**，然后按验收条件验收。**批 2 = PLAN**：拆开"部分完成、部分待做"的混合事项再迁，**不借迁移顺带实现功能**。**批 3 = ACCEPTANCE**：按"证据 → 记录 / 仍有效的约束 → 机制 / 待决 → 事项 / 决策解释 → 随记录"分流，**保留历史证据及适用边界**。
close_when: 三批各自验收通过并留下记录即关。每批的验收（主判据，人工走查）= **可定位 / 可执行 / 可关闭 / 无约束遗漏** 四项；走查必须真的沿"下一步 → 观测 → 分支结论"走一遍，"确认后可关"式措辞即使过格式检查也判该批不通过。某批不通过则该批重做，不扩大到下一批
---

## 问题与本次范围

试点（三个事项）已通过：见 `acceptance/records/2026-09-20-ledger-pilot.md`。本项管**剩下的大文档**，
按"分流压力从小到大"分批，一批不停就不动下一批。

## 每批的硬约束

- **迁移权威性**：一个事项的迁移必须在**同一变更**内完成"建立新记录 + 删除旧正文 + 留下定位指针"；
  不允许两份正文并存后"稍后清理"。接受阶段性覆盖不全，**不接受阶段性双真源**。
- **状态不许顺手改**：迁移只做搬运与成形，**不借迁移顺带实现功能**（功能修复另立事项、另行验收）。
- **不许为了迁完而补写结论**：遇到需要重新决策的语义（原文自相矛盾、历史局部通过被当成当前整体结论、
  适用范围不明），**留下待决项**并写明"待谁在哪一步裁决"，不自己补一个结论。
- **历史证据的适用边界要跟着走**：ACCEPTANCE 里的读数属于当时的协议/套件/资产状态；
  分流时把边界一起搬，**不把历史局部通过升级成当前整体结论**。

## 已知的待决项（迁到哪一批就在哪一批裁决）

- `HARNESS.md` 内部矛盾：一处说当前评测协议是 v2、一处说 v3 ⇒ 批 1 裁决。
- `tasks/components.py`、`tasks/lizard_env_cfg.py`、`tools/verify/teacher_smoke.py` 三处注释仍指向
  FAMILY 的 obs 布局表（该表归 `OBS.md`）⇒ 属于代码文件，另行安排。
- `check_pxr_leak.py` / `check_split_probe_wait.py` 的 docstring 里 `docs/pitfalls.md` 路径陈旧 ⇒ 同上。
- FAMILY 版本史行与 FILEMAP 版本目录行都带版本身份（重叠约 70%）⇒ 是否收敛到一处，批 2 顺带裁决。

## 未覆盖边界

本项不实现任何 `HARNESS/PLAN/ACCEPTANCE` 里挂账的功能；不改闸门口径（现有 47 条检查保持）；
不动各家族 `vN/` 目录里的四件套（那由 `check_version_docs.py` 看守）。
