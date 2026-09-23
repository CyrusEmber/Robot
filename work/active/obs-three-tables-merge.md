---
id: obs-three-tables-merge
title: obs 三张手抄表与声明合口（用户已定"要合"，未落地）
scope: rl_exp/tasks, rl_exp/versions
status: open
landing: rl_exp/tasks/components.py, rl_exp/versions/obs_protocols.json
next: **核认已完成**（依据与行号见 `acceptance/records/2026-09-23-blocked-chain-and-obs-merge-precheck.md`）：三张表仍在（`components.py:391,402,412`，构造用 `:550-557`）；互钉的准确形态是 —— `check_obs_layout`（`[8]`）读**构出的**分组序列比它自己的期望顺序，而期望顺序来自**声明**（`_declared_orders`→`obs_protocol.live_terms_for`，`:96,104,107-114`），这才是"实现 vs 声明"的对账；`test_component_ownership.py:275-307` 另直接点名三张表；`check_obs_protocol`（`[42]`）**不点名**表（它钉"声明 vs golden"，`--live` 才钉构出的 cfg）。合口后 `[8]` 退化为"声明 vs 声明"这一代价已由代码确认。**动工前置：满足**（`components.py` 最后一次实质改动 `bbedd96` 2026-09-18，其后仅 `4a80e47` 改引用）。下一步＝实施：先跑一次全量离线套件留基线，再按"组件只留构造、按 `(line, version)` 读声明"一次落。**不做**：新增身份参数
close_when: 观测 = 三张手抄表从 `rl_exp/tasks/components.py` 消失、改由 `(line, version)` 读声明；`check_obs_protocol` 与 `check_obs_layout` 与 `check_cfg_lock`（golden 未动）同时绿；且 `--live` 退化这一事实已写进 obs 契约文档（`OBS.md` 或 `obs_protocol.py` 的说明）。缺任一条保持 open；若核认发现合口会牵动 golden 或框架 pin，就地停下并把牵连面写进本项，由人决定
evidence: acceptance/records/2026-09-16-lizard-builder-hard-a.md, acceptance/records/2026-09-23-blocked-chain-and-obs-merge-precheck
---

## 问题与本次范围

「声明不参与 cfg 构造」是当时的写点隔离取舍，代价 = 三张手抄表与 `versions/obs_protocols.json` 声明
双写；用户已定"要合"，但落地一直没排上。**本项只做核认与落地**，理由、身份讨论与代价的论证留在
`acceptance/records/2026-09-16-lizard-builder-hard-a.md`（§3.1 第 11 条、L158 追记、L266 未覆盖边界），
不在本项复述。

## 未覆盖边界

不新增身份参数、不动 golden、不改框架 pin；合口前后 `--live` 的证据强度变化属**已知降级**，本项需把它
写进文档而不是当成无代价重构。
