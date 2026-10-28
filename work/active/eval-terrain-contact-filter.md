---
id: eval-terrain-contact-filter
title: 评测套件适配头部地面接触过滤器
scope: ablation_harness/eval.py, rl_exp/tasks/lizard2_recipe.py
status: open
landing: ablation_harness/eval.py
evidence: acceptance/records/2026-10-10-isaac-root-parameterisation.md
next: 执行者核定套件碰撞路径及传感器语义，修复评测配置并以真实仿真和破坏回归验证。
close_when: 新上下文按正文“关闭条件”核验落点与证据；有缺口不关闭。
---

## 当前范围

v5/v6 的头部地面接触传感器过滤训练平地路径；eval 换成固定地形套件后该路径不存在，初始化失败。失败证据见 `acceptance/records/2026-10-10-isaac-root-parameterisation.md` 的「修复后 v6 探针」节。

## 下一步

1. 执行者查明套件中实际碰撞体、接触过滤及头部终止语义，保留地面专用判据，避免对机器人自身接触误判。
2. 加修复前失败、修复后通过的回归；真实仿真验证 v5/v6 套件启动、头地接触与非地接触区分，留下可复读证据。
3. 完成后置 `pending_review`，由无执笔历史的新上下文审核。

## 关闭条件

- **审核者与输入**：新上下文读取落点、测试、真实仿真和验收记录。
- **可观察验收**：固定套件下传感器过滤目标有效；头地接触触发原判据，非地接触不误触发；评测完整落盘。
- **交付与边界**：不改冻结协议或静默关闭终止项；未覆盖情形明确留在活跃事项。
- **结果处理**：通过审核后关闭；可修缺口退 `in_progress`，仅用户能解决的缺口置 `blocked`。
