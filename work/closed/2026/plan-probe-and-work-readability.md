---
id: plan-probe-and-work-readability
title: 复杂计划探测链与事项可读性、骨架生成
scope: .codemaker/rules, rl_exp/tools/pipeline, rl_exp/tools/verify, work/active
status: done
landing: .codemaker/rules/versioning.mdc, rl_exp/tools/pipeline/declare_family.py, rl_exp/tools/verify/check_work_docs.py
outcome: 规则、现有生成入口与三条事项写法落地；新上下文复审通过，详情归 evidence。
close_when: 新上下文按正文“关闭条件”核验实现、回归与文档边界；有缺口不关闭。
evidence: acceptance/records/2026-10-12-plan-probe-and-work-readability
---

## 当前范围

用户拍板：2026-10-12，保留当前文档结构；复杂 PLAN 使用“关键假设 → 最小探测 → 停止条件”。当前仅整理 lizard2 机体驱动、接触协议、配方采用三条事项的 next/close_when，不改它们的技术要求、状态和完成结论。已训 v3 与退休版本 PLAN 不回写。

未来计划骨架复用 `declare_family.py`，事项骨架扩展 `check_work_docs.py`。只生成待填写结构，不代写设计决策、不生成验证通过或自动关闭。

## 下一步

1. 新上下文对照关闭条件核对 landing、当前三条事项及 evidence；重点检查生成器的写入边界与原动作/验收是否完整保留。
2. 可修缺口退 in_progress 修复，证据变化后重审；通过后移入 closed 并补 outcome。核验前不关闭，不执行三条事项的技术工作。

## 关闭条件

- **审核者与输入**：新上下文读取 landing、本项证据及三条事项，不用执行者总结替代核验。
- **规则与生成器**：复杂 PLAN 骨架包含可证伪假设、可执行最小探测和失败/缺证时的停止动作；不得把声明检查当行为证据。事项骨架保留当前字段契约，默认预览不落盘，显式写入且拒绝覆盖。
- **当前事项**：next/close_when 是短路由，正文条目保留原动作、依赖与分阶段出口；没有缩减验收、提前采用机体或启动训练。
- **结果处理**：通过审核后移入 closed 并补 outcome；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。骨架生成成功不算设计完成。
