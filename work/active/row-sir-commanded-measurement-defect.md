---
id: row-sir-commanded-measurement-defect
title: 行 SIR 成功标签缺陷与退役家族历史读数边界
scope: rl_exp/tasks/teacher_mdp.py, rl_exp/versions/lizard
status: open
landing: rl_exp/tasks/teacher_mdp.py, rl_exp/versions/lizard/main/v14/NOTES.md
next: 用隔离反例验证终态命令乘全长、无方向净位移与 timeout 联合判据；按 recipe 接线及历史 run 身份核准受影响版本与读数，将允许引用和禁止推断的范围写入验收记录。旧冻结实现暂不修改；未来复用须另立版本化修复项。
close_when: 反例与接线核验完成，历史影响已划界且各受影响的现行结果入口有证据指针；证据不足的 run 明记 unknown，不补造历史。若仍有未核对结果则保持 open。
evidence: acceptance/records/2026-09-22-lizard-family-retirement.md
---

## 当前缺口

实现落点为 `SpawnWeightSIRTerrainCurriculum.__call__`；具体判据、静态影响范围与尚未执行的验证归 evidence。家族退役不消除历史训练采样与读数解释问题。
