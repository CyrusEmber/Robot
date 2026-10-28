---
id: lizard2-v6-belly-reset
title: lizard2 v6 腹部触地立即重开
scope: rl_exp/tasks, rl_exp/versions/lizard2, rl_exp/tools/verify, rl_exp/tools/diagnose
status: done
landing: rl_exp/tasks/lizard2_recipe.py
evidence: acceptance/records/2026-10-28-lizard2-v6-belly-reset.md
outcome: 独立审核通过，配置交付与未覆盖边界见验收记录。
close_when: 新上下文按正文“关闭条件”核验落点与证据；有缺口不关闭。
---

## 当前范围

按用户要求恢复腹部触地立即重开，交付独立 v6 配方。实际碰撞体归属与接触判据写入实现；已训 v5 保持原身份，本轮不启动训练。

## 交付

实现、回归、原生自动 reset 对照与仓库检查经独立新上下文审核，正式结论取验收记录。本项只交付配置与验证，不承接训练启动或策略性能验收。

## 关闭条件

- **审核者与输入**：不带执笔历史的新上下文读取 v6 PLAN、实际实现及验收记录中的回归和原生证据。
- **可观察验收**：腹部接触即时触发自动 reset，正常四足站立不误触发；v5 及其它配方行为不漂移。
- **交付与边界**：向用户交付配置与复读入口，不将本轮验证等同训练启动或策略学会步态；仓库检查的真实未过项不得隐藏。
- **结果处理**：通过审核后关闭；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。
