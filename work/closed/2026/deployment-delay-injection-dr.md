---
id: deployment-delay-injection-dr
title: 延迟注入 DR（UE 部署前，PLAN #6）
scope: rl_exp/tasks, rl_exp/versions/lizard
status: cancelled
landing: rl_exp/versions/lizard/OBS.md
outcome: 用户 2026-10-09 裁决记 `cancelled`：落点原写 `components.py` 与退休线的 `OBS.md`，前者随本迭代清理删除，且仓内本就零实现、无 lizard2 落点 ⇒ 本项不是被接管而是被判掉；日后若作 lizard2 的 DR 需求须另立事项。
---

## 当前状态

挂账只有一行意图（EP 的延迟注入技巧），仓内既无实现也无落点：`rl_exp/tasks` 全量检索没有延迟/时延相关代码，方案文档里它只出现在路线参考行与 parkour 的相机延迟那一条旁边。

## 为什么它是 blocked 而不是 open

它不是"知道要做、只差动手"：训练侧与部署侧的验收条件不同（前者要进冻结快照语义，后者要不动训练配方），**先拍板落点才有可执行的下一步**。在落点定案前写实施步骤只会写出一份将来被推翻的方案。
