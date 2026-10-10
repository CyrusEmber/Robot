---
id: pending-review-before-close
title: 事项关闭前增加 Pending Review 与独立 AI 审核
scope: work, rl_exp/tools/verify/check_work_docs.py, AGENTS.md
status: done
landing: rl_exp/tools/verify/check_work_docs.py, AGENTS.md
close_when: 新上下文的审核者逐条核对该项声称的观测：工具三件（状态集合、closed 树反向闸门、`--list` 状态匹配）在破坏测试下报红、在真实树上不误报，`AGENTS.md` 的流程与工具行为一致，且审核者对"证据缺失的关闭候选"给出拒绝（放行即说明这步是盖章）；观测 = 记录里的逐条判定与工具判词 + 审核者对缺证据样例的拒绝。
evidence: acceptance/records/2026-10-10-pending-review-before-close
outcome: 2026-10-10 落地：`check_work_docs.py` 加 `pending_review` 状态、closed 树反向闸门、`--list` 兼匹配状态，并加自测 fixture 与两条破坏测试（删掉各自逻辑即报红）；`AGENTS.md` 补"关闭前先 `pending_review`"。关闭动作由新上下文的审核者两轮试审作出：首轮 PASS-WITH-GAPS —— 机制与破坏测试成立，负向对照（缺证据的关闭候选）判 REJECT（故不是盖章），但指出"先写指针后补记录 ⇒ 待审项恒为 DRIFT"这一未定价后果；已按它补 `AGENTS.md` 一句、并把本记录与该项同批落地，二轮复审判 PASS。逐条判定与读数、以及未覆盖边界（无"必须有审核记录"的机闸、不追溯历史关闭项、审核者只以角色具名故滞留待审项无责任人）都在证据记录里。本项自身即该流程的第一次用例。
---

## 现状

已落地（工具侧）：`check_work_docs.py` 的 `_STATUS` 增加 `pending_review`，新增"closed 树里出现
`pending_review` 即红"的反向闸门，`--list` 的关键词改为同时匹配状态（`--list pending_review`）；
自测新增两个 fixture（active 侧合法、closed 侧报红）与筛选断言。`AGENTS.md` 的关闭流程补了
"关闭前先 `pending_review`"一节。

边界与已知代价：

- 该状态**不设**"必须有审核记录"的机器闸门：记录存在不等于被读过，格式闸门证明不了审核真发生，
  判真伪靠 review。
- 不追溯要求历史关闭项补审核记录；关闭树里既有的 55 项不动。
- 审核者是**新上下文**（不带执笔会话历史）的 AI，只对着 `close_when`、落点与证据判，不看执笔者的
  总结；新上下文降低的是盲点相关性，不是"模型独立"或正确性保证。
- 发起关闭的会话负责启动审核，不做后台自动扫描；待审项留在默认列表，不会退出发现链。

## 未覆盖边界

判据是否被擅自放宽、审核是否流于形式，本工具不判（见上）；`--list` 的字节预算与 `work/active/`
总量预算不受本次改动影响（筛选不改变打印行）。
