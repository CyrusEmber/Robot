---
id: eval-command-observation-timing
title: 评测命令与策略观测时序
scope: ablation_harness/eval.py, ablation_harness/protocols
status: open
landing: ablation_harness/eval.py, ablation_harness/protocols
next: 执行者复现命令切换与策略观测错位，按协议冻结纪律修复并验证。
close_when: 新上下文核验时序修复、协议版本和历史结果限制后决定关闭。
evidence: acceptance/records/2026-11-04-training-provenance-dependency-scope.md
---

## 当前范围

独立审核发现评测命令和策略观测可能错位，历史结果限制见[来源事项验收记录](../../acceptance/records/2026-11-04-training-provenance-dependency-scope.md)。本项只处理评测时序，不重新训练或改写历史记录。

## 下一步

1. 执行者用首步、命令切换和自动 reset 的反例核实实际策略观测，保留历史评测解释限制。
2. 按冻结纪律修复测量时序；核对观测噪声、状态更新和终止帧，不修改已发布协议。复测真实环境及离线回归。
3. 完成后置 pending_review，交新上下文审核实现、版本和证据。

## 关闭条件

- **审核者与输入**：新上下文读取实现、协议、回归及真实运行证据。
- **可观察验收**：首步、切换和 reset 后策略实际观察到对应命令；修前反例失败、修后通过，历史协议行为不被静默改写。
- **交付与边界**：新协议按版本纪律审核冻结；旧评估保留原始结果和时序局限，不跨协议混比。
- **结果处理**：通过审核后关闭；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。
