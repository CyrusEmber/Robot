---
id: row-sir-commanded-measurement-defect
title: 行 SIR 成功标签缺陷与退役家族历史读数边界
scope: rl_exp/tasks/teacher_mdp.py, rl_exp/versions/lizard
status: cancelled
landing: rl_exp/tasks/teacher_mdp.py, rl_exp/versions/lizard/main/v14/NOTES.md
outcome: 用户 2026-10-09 裁决按"接管关系"分开记关闭词：本项只给退役线的历史读数划引用边界，不是被清理项接管的实施动作 ⇒ 记 `cancelled`；边界本身已写在 evidence 的退休记录里，未核对的 run 明记 unknown，不补造历史。
evidence: acceptance/records/2026-09-22-lizard-family-retirement.md
---

## 当前缺口

实现落点为 `SpawnWeightSIRTerrainCurriculum.__call__`；具体判据、静态影响范围与尚未执行的验证归 evidence。家族退役不消除历史训练采样与读数解释问题。
