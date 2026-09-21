---
id: baseline-eval-pipeline-restructure
title: baseline eval 重整：采集—判定—归因分家，结论三态
scope: ablation_harness, rl_exp/tools/diagnose
status: in_progress
landing: ablation_harness/baseline_frames.py, ablation_harness/baseline_metrics.py, ablation_harness/baseline_eval.py, ablation_harness/HARNESS.md
next: ① 报告固定分列有效性 / 任务表现 / 行为有效性三块（采集自检 + 门槛 + 诊断），异常归因按需触发而不是每次评估都做完整物理调查；② 归因腿（接触点切向速度、地面与自碰分离、切向力方向）见 `floor-contact-attribution`；③ 门槛阈值需独立依据与正常／异常样本验证——**不得把观测到的读数直接写成允许阈值**
close_when: 在 baseline 上跑通一次完整流程：仿真侧产出带单位、形状、轴标的记录 → 离线判定（含改协议复判不重跑物理）→ 报告分列有效性／表现／行为三项，且两份场景项（`baseline-eval-measurement-trust`、`floor-contact-attribution`）均已关闭
depends_on: baseline-eval-measurement-trust, floor-contact-attribution
evidence: acceptance/records/2026-09-21-baseline-eval-measurement-contract.md
---

## 问题与本次范围

缺的不是某个读数，是主流程：常规 eval 既不自检"测得对不对"，也不问"这算不算行走"，
出问题时只能临时诊断。本轮把流程定成采集 → 判定 → 归因三段，并只做在 baseline 上跑通所需的部分，
不搭覆盖所有任务的通用评估框架。

| 段 | 必须回答的问题 |
|---|---|
| 测量自检 | 维度、body 对应、有限值、接触计数对不对？不满足 ⇒ 评估**无效**，不判策略好坏 |
| 固定窗口采集 | 同一 rollout 逐 env 逐帧落盘，明确终止帧与有效区间 |
| 任务表现 | 速度、位移、存活是否达标 |
| 行为有效性 | 是否依赖非足支撑、持续拖地、异常穿透；逐脚接触与滑动如何 |
| 异常归因 | 只在异常时做：地面接触对、接触点速度、切向力方向、摩擦利用率 |
| 报告 | 有效性 / 表现 / 行为三块分别给出，未解决的问题留白 |

## 当前状态

前三段已落地（`baseline_frames` → `baseline_metrics.judge` → `baseline_eval`），判定与仿真解耦：
阈值要动不必重跑物理，且"采集错了"与"判据错了"可分别定位。归因段按需触发，落在诊断器侧。

## 未覆盖边界

不覆盖阈值是否恰当（阈值要有独立依据与正常／异常样本），不覆盖通用多任务评估框架，
不覆盖接触物理本身的参数决策（归 `floor-contact-attribution`）。
