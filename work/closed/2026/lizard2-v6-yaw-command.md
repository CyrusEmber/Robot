---
id: lizard2-v6-yaw-command
title: lizard2 v6.1 开放转向速度指令
scope: rl_exp/versions/lizard2, rl_exp/tools/verify, rl_exp/tools/diagnose
status: done
landing: rl_exp/versions/lizard2/main/v6/main_params.yaml
close_when: 新上下文按正文“关闭条件”核验落点与证据；有缺口不关闭。
outcome: 独立审核通过，修订与证据同次提交；策略能力不在本轮验收范围。
evidence: acceptance/records/2026-10-28-lizard2-v6-yaw-command.md
---

## 当前范围

用户明确解冻未训练 v6 并选择转向范围；保留已推标签，修订落在原任务，不启动训练。

## 下一步

1. 新上下文对照关闭条件、实际文件及原始证据审核；结论进入验收记录。
2. 审核通过后执行者关闭事项并提交修订锚，保留旧标签。

## 关闭条件

- **审核者与输入**：新上下文读取 landing、版本 PLAN、差异声明及验收记录原始入口。
- **可观察验收**：左右转指令到达观测，定时换档且跟随优于静止/反向；原标签不改指，既有腹部重开保持。
- **交付与边界**：交付可复读的配方修订；不宣称学会转弯，不启动训练。
- **结果处理**：通过审核后关闭；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。
