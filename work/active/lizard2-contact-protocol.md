---
id: lizard2-contact-protocol
title: lizard2 新接触评测协议：滑移/滚动/偏转样本对拍与承重分组
scope: ablation_harness, rl_exp/tools/verify, rl_exp/tools/diagnose, acceptance/records
status: in_progress
landing: ablation_harness/protocols, ablation_harness/baseline_metrics.py, ablation_harness/baseline_eval.py, rl_exp/tools/diagnose/gait_probe.py
next: 执行者维护评测待办；新增指标使用前补对应标定与协议，不阻塞首轮训练。
close_when: 新上下文按正文“关闭条件”审核协议与标定样本，通过交 lizard2-family-landing；缺口按责任退回。
evidence: acceptance/records/2026-10-19-lizard2-chest-standing-pd.md, acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-10-lizard2-v3-first-eval, acceptance/records/2026-10-10-lizard2-v3-band-buckets, acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration, acceptance/records/2026-10-09-lizard2-v3-eval-entry-and-inert-velocity-field
---

产品协议与报告清单归本项；采集机制取已关闭的 `work/closed/2026/baseline-eval-pipeline-restructure.md`。按[训练优先修订](../../acceptance/records/2026-10-23-lizard2-training-priority-plan.md)，本项完整发布、三类动态标定与异常主承重分类不作为当前首轮开训前置。训练必需的实际动作、观测、接触力采样与 reset 由候选 D/E 及训练接入核验；本项继续维护未完成评测工具，不取消或视为通过。冻结旧协议保持原语义，新增或收窄走新协议文件。

样本只验证测量，不要求手工卸载、移重、平衡、抬腿、躯尾协调或步态成功；学习性能交 `lizard2-family-landing` 的训练后策略评测。若新滑移/滚动或承重分类进入奖励、终止或合格判定，使用前必须完成对应标定与审核。

## 动作

采样与测量见[记录](../../acceptance/records/2026-10-23-lizard2-contact-native.md)；其余按下文交付。

1. 通道存在性已核（可用的通道、具名缺口、滚动/有效阶段为何分不开、报告项被静默不检查的那两项，全归 `acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory.md` C 节，本项不复述）：动作从那份缺口表开始定口径；缺口仍在时写具名缺口，不用最低顶点跳变冒称材料点速度。
2. 新协议覆盖足底净空、足端相对机身摆幅、承重接触材料点相对地面的切向运动，并逐项绑定实现。柔顺偏转/滚动/真实滑动按整体记录“联动设计修订”第 2 条区分：关节偏转与原点移动不自动扣分，真实承重接触点滑动仍计滑移，回位不抹去已发生的滑动；近似点切换、滚动与有效阶段须声明。
3. 在发布并使用新滑移/滚动判分前，用固定接触偏转、滚动与真实滑动样本校准对应口径，样本与复读命令入 `acceptance/records/<日期>-lizard2-contact-protocol.md`。本项保留为评测待办，不是当前首轮位置策略训练的最后一步，不自动追加物理运行。
4. 整理 `report_only` 实现清单，移除 `dof_torque_frac_of_limit`（关节力矩留专项采集），未实现的 `foot_yaw_deg` 不进新清单。
5. `no_non_foot_carrier` 的持续部分承重档补齐幅值标定：允许尾触地与异常载荷分别标定，不沿用旧分组；既有样本、复读方法和缺口见 `acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration.md`。拖尾与新增掌跖段承重进入具名接触分组，样本和新报告消费 E 的实际目标绑定；当前 palm 接触端为腕/踝子 link，不能使用指/趾根占位，也不等正式采用才绑定。
6. 声明固定命令序列、速度带、等待窗与覆盖要求，按新场景采集，不把历史随机场景读数当新证据。历史分桶只作参考。
7. 承接 [接线专项 E3](lizard2-candidate-wiring.md#e3-消费者迁移与交接范围) 的报告 writer 交接：既有字段/列契约、双目标实际报告链与未验边界取 `acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md`“追加：E 双目标实际消费者执行”；新测量仍走具名新协议，不重解释旧结果。受资产变化影响的评测须重验，训练可先使用已有可信的接口与报告项。
8. 按实际消费用途交付测量口径与样本。B/C/D 所需驱动安全、通道与接触力输入不与完整动态分类互等；新增策略判分在使用前交 `lizard2-family-landing` 固定指标、窗口与用户确认阈值。未校准指标写未判，不反推阈值；本项完整发布仍按下文审核。

## 关闭条件

- **审核者与输入**：新上下文读取协议文件、标定样本与 evidence 中的真实记录；执行者完成后先置 pending_review。
- **可观察验收**：偏转、滚动、真实滑动三类样本在同一口径下被区分；行走与零速站立分场景；允许尾触地与异常主承重分别判定。
- **协议与证据边界**：`report_only` 清单收窄，新 writer/reader 契约及 E 的真实报告交接齐备，旧协议不改写；读数归 `acceptance/records/`，协议号与配方号不互推。新增策略性能阈值由 `lizard2-family-landing` 在使用前经用户确认，不在本项代定、不作为开训或 D 手工步态门槛。
- **结果处理**：通过交 `lizard2-family-landing`；样本不可区分或通道缺失退 in_progress，口径取舍需用户时置 blocked。

## 边界

阈值不在本项冻结；使用该判分时按固定协议复验，失败不事后放宽，换尺须新协议与同尺重评。v3 入口与协议身份只按 `acceptance/records/2026-10-10-lizard2-v3-first-eval.md` 取用，不外推当前候选。静态趴姿场景不发布，归 `lizard2-prone-posture`。
