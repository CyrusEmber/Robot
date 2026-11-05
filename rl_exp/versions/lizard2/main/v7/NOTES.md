# lizard2 main/v7 运行记录

## 设计与差异

目的、假设、验收与计划命令见 [PLAN.md](PLAN.md)。本版采用固定圆足并移除足端活动动作，使用收窄后的双肘边界；完整差异及理由唯一取 [diff.json](diff.json)。

## 实际执行与偏离

本版接入阶段做资产晋升、配置及离线检查；后续接口实测取 [接口记录](../../../../../acceptance/records/2026-11-03-lizard2-v7-interface.md)。接入和冻结阶段没有启动策略训练；实际提交/标签/远端身份取 [冻结记录](../../../../../acceptance/records/2026-11-03-lizard2-v7-freeze.md)。接入执行与原缺证归 [接入记录](../../../../../acceptance/records/2026-11-03-lizard2-v7-round-feet.md)，不将其历史状态当当前接口状态。

## 结果回填

- 已训 run `E:/IsaacLab/logs/rsl_rl/lizard2_v7/2026-11-03_17-07-29/`；策略现场诊断取 [小腿倾角记录](../../../../../acceptance/records/2026-11-04-lizard2-shank-tilt-reach.md)。
- 来源短训 run `E:/IsaacLab/logs/rsl_rl/lizard2_v7/2026-11-04_16-12-57/`；复读 `python -m rl_exp.tools.runrecord.manifest --verify E:/IsaacLab/logs/rsl_rl/lizard2_v7/2026-11-04_16-12-57`，来源与训后状态取 [验收记录](../../../../../acceptance/records/2026-11-04-training-provenance-dependency-scope.md)。

## 结论

已产生策略训练及来源短训记录；来源短训不代表策略性能通过，固定评估状态和边界取上述记录。
