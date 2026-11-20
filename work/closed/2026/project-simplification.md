---
id: project-simplification
title: 项目分批精简总纲
scope: rl_exp, ablation_harness, work
status: cancelled
landing: rl_exp/tools, rl_exp/tasks, rl_exp/versions, ablation_harness, work
outcome: 用户裁决取消保留旧静态互锁链的分批修补方案，改为通过 work/active/robot-experiment-architecture-refactor.md 围绕“机体→实验→运行→评测”单向主链重构；原总纲中仍在办的退出码、旧帧裁决与诊断产物事项继续按各自活跃项推进。
---

## 取消说明

原方案试图在不拆除动态配置构建、多层身份映射与逆向验证依赖的前提下分批精简各目录，长期维护税过高。已由 `work/active/robot-experiment-architecture-refactor.md` 接手新方向（保留此处仅作历史决策记录）。

## 原提案边界（已取消）

- 先收敛代码，再处置大文件。范围含本机 `rl_exp/out/`、资产、Blender 源件及关闭事项指针；原先规划为批次 1（诊断入口与探针）、批次 2（验证与工具）、批次 3（训练与评测）、批次 4（本机产物与大资产）及小项（文档导航）。
