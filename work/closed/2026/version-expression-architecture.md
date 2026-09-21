---
id: version-expression-architecture
title: 版本表达架构（退役条款撤回；候选 b 由 ARCH_PLAN.md 承接）
scope: rl_exp/versions/lizard, ARCH_PLAN.md
status: done
landing: ARCH_PLAN.md, rl_exp/versions/lizard/FAMILY.md, .codemaker/rules/versioning.mdc
outcome: 挂账转成有承接方的架构议题：候选 b（组件库 —— 参数级 diff 写 spec 行而非新子类）的具体化由仓根 `ARCH_PLAN.md` 承接，落地进度与验收归 `ACCEPTANCE.md`；曾写进 versioning 的退役条款保持**撤回**状态、不重录。**重议触发保留**：连续两个纯参数级新版本，或第二家族立项
evidence: ARCH_PLAN.md, rl_exp/versions/lizard/ACCEPTANCE.md
---

## 重议触发（保留）

两条任一出现即需重开架构裁决：连续两个纯参数级新版本；或第二家族立项（组件化的收益在此之前不成立）。

## 未覆盖边界

约束仍在：teacher 零家族 import 是冻结纪律，组件化不得破坏"改组件 ≠ 改历史版本语义"。本项不做实现，也不改 `.codemaker/rules/versioning.mdc` 的现行条款。
