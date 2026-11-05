---
id: v7-short-run-post-train-evidence
title: v7短训训后证据与未完成项
scope: ablation_harness, rl_exp/versions/lizard2/main/v7
status: open
landing: ablation_harness/HARNESS.md, rl_exp/versions/lizard2/main/v7
next: 执行者核查短训训后缺口和画面同步，保留零有效样本事实并明确后续处置。
close_when: 新上下文核验短训训后证据、未完成项及其承接后决定关闭。
evidence: acceptance/records/2026-11-04-training-provenance-dependency-scope.md
---

## 当前范围

承接来源短训的训后未完成证据，原始结果与局限见[验收记录](../../acceptance/records/2026-11-04-training-provenance-dependency-scope.md)。不假定短训模型已达到运动能力，也不借本项授权新训练。

## 下一步

1. 执行者核查画面与物理状态同步，保留首帧黑屏、抽帧和遮挡等局限；不能据图片推断不可见接触。
2. 保留 robust 首局停车及恢复窗口零有效样本，按实际证据决定是否有可行补测；不得把提前扰动补片当正式协议结果。
3. 明确逐足承载、摆动及非足支撑的数值口径和实际测量；接触口径由 `work/active/lizard2-contact-protocol.md` 承接，落地阶段应用由 `work/active/lizard2-thigh-drive-shank-landing.md` 承接，不把候选指标当正式判据。
4. 完成后置 pending_review，交新上下文审核原始证据和仍无法判断的项目。

## 关闭条件

- **审核者与输入**：新上下文读取原始评测、录像、证据记录和相关承接事项。
- **可观察验收**：按 `ablation_harness/HARNESS.md` 如实报告有效样本与视频核验；零样本不写成成功，逐足或非足支撑须有经核定的测量口径。
- **交付与边界**：不能补出的历史数据保持未知；需要新的模型或其他未完成动作须有明确承接，不自动新增训练。
- **结果处理**：通过审核后关闭；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。
