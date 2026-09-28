---
id: training-curve-readout-missing
title: 训练曲线读数无家：入库步骤可被跳过，收敛读数没人收
scope: rl_exp/tools/trainlog, rl_exp/tools/pipeline, rl_exp/versions/lizard2, .codemaker/rules/versioning.mdc, acceptance/records
status: open
landing: rl_exp/tools/pipeline/declare_family.py, .codemaker/rules/versioning.mdc, rl_exp/tools/trainlog/dump_tb.py
next: ① **v1 已补**（2026-09-28：csv 入库 + 收敛读数落 `acceptance/records/2026-09-28-lizard2-v1-training-curve.md` + §A 第 4 步写明落点与归属）② **骨架行已补**（`declare_family.py` 的 NOTES 骨架加"训练曲线"行，2026-09-28）③ **实测缺口（2026-09-28）**：20 个版本 NOTES 提到 run，只有 4 个目录有入库 csv（lizard main v1/v5/v10、lizard2 main v1）⇒ 约 16 处未入库，需逐版核 run 是否还在机器上、能补则补、不能补则在该版 NOTES 写明为什么没有 ④ **无闸门（已知上限）**：run 目录机器本地、不进仓，仓内无法判"某版跑过没入库"，只能靠版本收尾人核
close_when: (a) 每个有 run 的版本目录要么有 `tb_scalars.csv`，要么在 NOTES 写明为什么没有；(b) `declare_family.py` 骨架自带训练曲线行；(c) §A 第 4 步的落点与读数归属在磁盘上可验证（读法命令能跑通）——三件齐了才关
evidence: acceptance/records/2026-09-28-lizard2-v1-training-curve
---

## 问题与本次范围

曲线数据本身一直存在（run 目录的 tfevents），缺的是**仓里的家与收尾动作**：`versioning.mdc` §A 第 4 步
把"曲线导出"列为管线一步，但入库落点、谁读、收敛读数归谁都没有机制可查；`check_version_docs.py` 只查
版本目录四件套，所以"导出没做"在闸门上是静默的。本项收这条链的债：入库落点、读数归属、骨架槽位。
不含评测侧（用曲线画图/出报告的那一头，见 `plot-eval-report-stale`）。

## 当前状态

- v1（lizard2 主线）此前**漏了入库**：NOTES 的"训练读数"行只指向 tfevents 与巡检入口，收敛类数字于是只活在
  引用它的散文里。2026-09-28 补齐（入库 + 记录 + 规则落点），实测读法跑通。
- 规则侧已落点：§A 第 4 步写明入库落点 `vN/tb_scalars.csv` 与"收敛类读数归 `acceptance/records/`"。
- 机制侧仍缺：NOTES 骨架无"训练曲线"行；无闸门能发现"某版跑过但没入库"。

## 未覆盖边界

- **入库是抽样**：仓内的 csv 是抽样记录，逐迭代细节留机器本地，抽样器行为由
  `test_dump_tb_sampling.py` 看守；这里不重复它的参数。
- **读数口径归记录**：分块宽度与平台带 band 是记录里声明的一次读数口径，不是判据；换口径要重新陈述。
- **run 记录本体不在仓内**：本项只能保证"落点与槽位存在"，不能保证某次 run 的 tfevents 还在。
