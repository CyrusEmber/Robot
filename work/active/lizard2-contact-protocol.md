---
id: lizard2-contact-protocol
title: lizard2 新接触评测协议：滑移/滚动/偏转样本对拍与承重分组
scope: ablation_harness, rl_exp/tools/verify, rl_exp/tools/diagnose, acceptance/records
status: open
landing: ablation_harness/protocols, ablation_harness/baseline_metrics.py, ablation_harness/baseline_eval.py, rl_exp/tools/diagnose/gait_probe.py
next: 执行者补测量口径和三类样本，承接 E 的 writer 契约并回交真实报告链；S5 阈值前置动作消费标定后确认判据，不等正式采用。
close_when: 新上下文按正文“关闭条件”审核协议与标定样本，通过交 lizard2-family-landing；缺口按责任退回。
evidence: acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-10-lizard2-v3-first-eval, acceptance/records/2026-10-10-lizard2-v3-band-buckets, acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration, acceptance/records/2026-10-09-lizard2-v3-eval-entry-and-inert-velocity-field
---

产品协议与报告清单归本项；采集、指标与执行机制归已关闭的 `work/closed/2026/baseline-eval-pipeline-restructure.md`，机制可用即发布协议，不形成互等关闭。冻结的旧协议与报告摘要保持不变，新增或收窄只走新协议文件。

## 动作

1. 通道存在性已核（可用的通道、具名缺口、滚动/有效阶段为何分不开、报告项被静默不检查的那两项，全归 `acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory.md` C 节，本项不复述）：动作从那份缺口表开始定口径；缺口仍在时写具名缺口，不用最低顶点跳变冒称材料点速度。
2. 新协议覆盖足底净空、足端相对机身摆幅、承重接触材料点相对地面的切向运动，并逐项绑定实现。柔顺偏转/滚动/真实滑动按整体记录“联动设计修订”第 2 条区分：关节偏转与原点移动不自动扣分，真实承重接触点滑动仍计滑移，回位不抹去已发生的滑动；近似点切换、滚动与有效阶段须声明。
3. 发布前用固定接触偏转、滚动与真实滑动的样本校准口径，样本与复读命令入 `acceptance/records/<日期>-lizard2-contact-protocol.md`。
4. 整理 `report_only` 实现清单，移除 `dof_torque_frac_of_limit`（关节力矩留专项采集），未实现的 `foot_yaw_deg` 不进新清单。
5. `no_non_foot_carrier` 的持续部分承重档补齐幅值标定：允许尾触地与异常载荷分别标定，不沿用旧分组；既有样本、复读方法和缺口见 `acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration.md`。拖尾与新增掌跖段承重进入具名接触分组，样本和新报告消费 E 的实际目标绑定；当前 palm 接触端为腕/踝子 link，不能使用指/趾根占位，也不等正式采用才绑定。
6. 声明固定命令序列、速度带、等待窗与覆盖要求，按新场景采集，不把历史随机场景读数当新证据。历史分桶只作参考。
7. 承接 E3 的报告 writer 交接：当前实现、字段/列契约、双目标实际报告链与未验边界取 `acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md`“追加：E 双目标实际消费者执行”；后续新测量语义仍走本项具名新协议，不重解释旧协议。继续补样本标定和新口径；受资产前提阻碍的验收不得用已有同几何报告豁免，不等机体项关闭或 S6 采用。
8. 可复读的测量口径和样本先供 B/C 安全标定，再交 `lizard2-family-landing` S5 阈值前置动作；该交接无需本项先关闭。最终设计比较由 D 使用已确认判据，新协议完整发布仍按本项关闭条件审核。

## 关闭条件

- **审核者与输入**：新上下文读取协议文件、标定样本与 evidence 中的真实记录；执行者完成后先置 pending_review。
- **可观察验收**：偏转、滚动、真实滑动三类样本在同一口径下被区分；行走与零速站立分场景；允许尾触地与异常主承重分别判定。
- **协议与证据边界**：`report_only` 清单收窄，新 writer/reader 契约及 E 的真实报告交接齐备，旧协议不改写；读数归 `acceptance/records/`，协议号与配方号不互推。最终阈值由 `lizard2-family-landing` S5 阈值前置动作在 D 比较前经用户确认，不在本项定。
- **结果处理**：通过交 `lizard2-family-landing`；样本不可区分或通道缺失退 in_progress，口径取舍需用户时置 blocked。

## 边界

阈值不在本项冻结；S6 按冻结协议复验，失败不事后放宽，换尺须新协议与同尺重评。v3 入口与协议身份交付只按 `acceptance/records/2026-10-10-lizard2-v3-first-eval.md` 取用，不以旧入口可用或旧判决替代新协议。静态趴姿场景不发布，归 `lizard2-prone-posture`。
