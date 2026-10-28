---
id: terrain-contact-suite-coverage
title: 补测多地形接触与视频运行
scope: ablation_harness/video_matrix.py, rl_exp/tools/diagnose/head_ground_dwell_probe.py
status: cancelled
landing: rl_exp/tools/diagnose/head_ground_dwell_probe.py
evidence: acceptance/records/2026-10-10-isaac-root-parameterisation.md
outcome: 用户决定取消过度扩展的补测；未验证边界保留在验收记录，不作为已验证能力。
close_when: 新上下文按正文“关闭条件”核验落点与证据；有缺口不关闭。
---

## 当前范围

头地过滤器修复的套件平地列物理夹具与 nominal eval 已有证据；其他地形列真实头地接触、真实自接触、自然跌倒、robust 和真实视频尚未覆盖。已有证据见 `acceptance/records/2026-10-10-isaac-root-parameterisation.md` 的「头地过滤器独立审核」节。自碰撞默认关闭时须说明可测条件，不以合成缓冲替代实测。

## 下一步

1. 执行者核对各地形形状、任务自碰撞约束和可复现的自然跌倒条件，设计并运行真实接触、视频与 robust 检查；保留失败现场。
2. 结果与边界进入验收记录；完成后置 `pending_review`，由无执笔历史的新上下文审核。

## 关闭条件

- **审核者与输入**：新上下文读真实运行产物、复读命令、实现及验收记录。
- **可观察验收**：覆盖套件其他列的头地接触和非地触发隔离，核对视频与 robust 真实运行；核实自接触和自然跌倒证据或将确实不可测的约束明确交付审核。
- **交付与边界**：未完成的动作不得消失；物理夹具不作为策略性能结论。
- **结果处理**：通过审核后关闭；可修缺口退 `in_progress`，仅用户能解决的缺口置 `blocked`。
