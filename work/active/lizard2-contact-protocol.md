---
id: lizard2-contact-protocol
title: lizard2 新接触评测协议：滑移/滚动/偏转样本对拍与承重分组
scope: ablation_harness, rl_exp/tools/verify, acceptance/records
status: open
landing: ablation_harness/protocols, ablation_harness/baseline_metrics.py
next: 不等机体候选，可立即开始：先确认引擎能给出的接触点通道，再用合成/固定样本（固定偏转、滚动、真实滑动）对拍并发布具名新协议草案。阈值数值不在本项定；最终阈值由 lizard2-family-landing S5 在比较前经用户确认。
close_when: 新上下文审核协议文件与标定样本：三类样本（偏转、滚动、真实滑动）在同一口径下被区分，行走/零速站立分场景，允许尾触地与异常主承重分别判，report_only 清单收窄且旧协议未被改写；读数归 acceptance/records，协议号与配方号不互推。通过交 lizard2-family-landing；样本不可区分或通道缺失则退回 in_progress，口径取舍需用户的置 blocked。
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-10-lizard2-v3-first-eval, acceptance/records/2026-10-10-lizard2-v3-band-buckets, acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration, acceptance/records/2026-10-09-lizard2-v3-eval-entry-and-inert-velocity-field
---

产品协议与报告清单归本项；采集、指标与执行机制归已关闭的 `work/closed/2026/baseline-eval-pipeline-restructure.md`，机制可用即发布协议，不形成互等关闭。冻结的旧协议与报告摘要保持不变，新增或收窄只走新协议文件。

## 动作

1. 先核对引擎实际能给的接触点/材料点数据通道，再定口径；通道不存在时写具名缺口，不用最低顶点跳变冒称材料点速度。
2. 新协议覆盖足底净空、足端相对机身摆幅、承重接触材料点相对地面的切向运动，并逐项绑定实现。柔顺偏转/滚动/真实滑动按整体记录“联动设计修订”第 2 条区分：关节偏转与原点移动不自动扣分，真实承重接触点滑动仍计滑移，回位不抹去已发生的滑动；近似点切换、滚动与有效阶段须声明。
3. 发布前用固定接触偏转、滚动与真实滑动的样本校准口径，样本与复读命令入 `acceptance/records/<日期>-lizard2-contact-protocol.md`。
4. 整理 `report_only` 实现清单，移除 `dof_torque_frac_of_limit`（关节力矩留专项采集），未实现的 `foot_yaw_deg` 不进新清单。
5. `no_non_foot_carrier` 的持续部分承重档补齐幅值标定：允许尾触地与异常载荷分别标定，不沿用旧分组；既有样本、复读方法和缺口见 `acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration.md`。拖尾与新增掌跖段承重进入具名接触分组，接触体名称取 `lizard2-body-drive-candidate` 名表（新名确定前以占位声明，采用时一并落定）。
6. 声明固定命令序列、速度带、等待窗与覆盖要求，按新场景采集，不把历史随机场景读数当新证据。历史分桶只作参考。

## 边界

阈值不在本项冻结；S6 按冻结协议复验，失败不事后放宽，换尺须新协议与同尺重评。v3 入口与协议身份交付只按 `acceptance/records/2026-10-10-lizard2-v3-first-eval.md` 取用，不以旧入口可用或旧判决替代新协议。静态趴姿场景不发布，归 `lizard2-prone-posture`。
