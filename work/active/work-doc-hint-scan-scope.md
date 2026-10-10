---
id: work-doc-hint-scan-scope
title: 指针扫描把冻结证据读成活指针（HINT 信道被恒噪占满）
scope: rl_exp/tools/verify
status: pending_review
landing: rl_exp/tools/verify/check_work_docs.py
next: 审——**新上下文**（不带执行会话历史）对着 `close_when` 与 `acceptance/records/2026-10-10-work-doc-hint-scope.md` 判三件：① 豁免是否只扩到**冻结证据类**（`_FROZEN_REFS` = 版本记录 + `acceptance/records`），有没有连带放过活文档 —— 判据是自测里活文档那条过时引用**仍须**出 HINT；② 破坏测试是否真咬住（撤掉 `acceptance/records` 后自测必须红在那条断言上）；③ 准入的缺陷是**真实一次**而非"以防万一"（`34c4917` 关闭 `runtime-acceptance-v3` 时暴露）。审核读数入 `acceptance/records/`，本项只留指针；审过即移进 `work/closed/2026/`、去掉本 `next`、补 `outcome`
close_when: 扫描不再读冻结证据类，且自测同时钉住两侧（冻结记录里出现过时指针必须**不报**、活文档里出现过时指针必须**仍报**）。按 `AGENTS.md` §Gates 准入：回应一次真实缺陷（写明是哪一次）、在该缺陷上有破坏测试、标明查的是行为成立而非声明一致 —— 本项钉的正是闸门自身行为，故破坏测试即证据
evidence: acceptance/records/2026-10-10-work-doc-hint-scope.md
---

## 当前状态

- **已做**：`_FROZEN_REFS` 按类扩到 `acceptance/records`；自测补冻结记录一侧的 fixture 与反向断言（活文档一侧早已有）。读数、破坏测试与复读命令全在 `evidence`（本项不复述数字）。
- **待审**：见 `next`。执行者认为本项已做完，故置 `pending_review`。

## 为什么按类豁免，而不是逐条修

记录的活句柄方向是**事项 → 记录**：事项带 `evidence` 指过去，记录里那句"被验的动作 = 某事项"是历史。所以
记录里回指事项的过时路径**不是路由**，按路径豁免它不丢信息；反过来在证据里改路径，等于把"当时对着哪件事"抹掉 ——
那条记录就不再是任何事的证据。这条判断不需要人逐句读，正是它归"类"的原因。

## 未覆盖边界

- 不改冻结证据里已写下的路径，也不把 HINT 升级成红闸：文本仍判不出"活指针 vs 痕迹"，这条边界不变。
- 不含 `work/closed/**` 散文的同类豁免（当前无命中）；要豁免是另一次判断。
- 不含"把扫描扩到代码/配置"：那里路径是数据或 fixture，`_REF_SUFFIXES` 已钉住该边界。
