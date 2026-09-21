---
id: obs-three-tables-merge
title: obs 三张手抄表与声明合口（用户已定"要合"，未落地）
scope: rl_exp/tasks, rl_exp/versions
status: open
landing: rl_exp/tasks/components.py, rl_exp/versions/obs_protocols.json
next: **核认（先做）**：① 确认 `components.observations` 的三张手抄表（`PROPRIO_TERMS`/`BASELINE_PRIV_TERMS`/`SPEC_TERMS`）仍在、且仍由 `[8]`+`[42]` 互钉；② 确认合口目标形状 —— 组件只留构造，改为按 `(line, version)` 读 `versions/obs_protocols.json` 的声明，删掉三张表；③ 确认合口代价已落在文档里（`--live` 退化为"声明 → 配置"的转换一致性检查，届时唯一独立来源是冻结 golden、3.1e 真 env 变承重）。**动工前置** = builder 改动静下来后一次落（2026-09-17 的排期约束，是否满足由核认 ① 判定）。**不做**：新增身份参数（已核过不需要）。实施前先跑一次全量离线套件留基线
close_when: 观测 = 三张手抄表从 `rl_exp/tasks/components.py` 消失、改由 `(line, version)` 读声明；`check_obs_protocol` 与 `check_obs_layout` 与 `check_cfg_lock`（golden 未动）同时绿；且 `--live` 退化这一事实已写进 obs 契约文档（`OBS.md` 或 `obs_protocol.py` 的说明）。缺任一条保持 open；若核认发现合口会牵动 golden 或框架 pin，就地停下并把牵连面写进本项，由人决定
evidence: acceptance/records/2026-09-16-lizard-builder-hard-a.md
---

## 问题与本次范围

「声明不参与 cfg 构造」是当时的写点隔离取舍，代价 = 三张手抄表与 `versions/obs_protocols.json` 声明
双写；用户已定"要合"，但落地一直没排上。**本项只做核认与落地**，理由、身份讨论与代价的论证留在
`acceptance/records/2026-09-16-lizard-builder-hard-a.md`（§3.1 第 11 条、L158 追记、L266 未覆盖边界），
不在本项复述。

## 未覆盖边界

不新增身份参数、不动 golden、不改框架 pin；合口前后 `--live` 的证据强度变化属**已知降级**，本项需把它
写进文档而不是当成无代价重构。
