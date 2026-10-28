# lizard2 main/v6 运行记录

## 设计与差异

目的、假设与验收见 [PLAN.md](PLAN.md)。本版使胸腹外壳触地进入即时重开；完整差异及逐项理由见 [diff.json](diff.json)。

## 实际执行与偏离

本轮不启动策略训练。配置、回归及原生自动 reset 验证的复读入口归 [验收记录](../../../../../acceptance/records/2026-10-28-lizard2-v6-belly-reset.md)。

## 结果回填

验证状态取同一验收记录；无新训练 run/checkpoint。

## 结论

本版仅恢复腹部触地重开，不据此宣称策略性能改善。
