---
id: lizard2-gait-followups
title: 步态补测遗留：lf 追因、目标越界、奖励载体
scope: rl_exp/tools/diagnose, rl_exp/versions/lizard2
status: open
landing: rl_exp/tools/diagnose/gait_probe.py, rl_exp/tools/diagnose/diag_metrics.py, rl_exp/versions/lizard2/main/v1/PLAN.md
next: ① **lf 腿追因（已收窄到策略侧）**：限位与资产几何两条候选已被削弱（读数见步态记录 ⑦ 与新记录 `2026-09-23-lizard2-leg-chains-not-mirrored.md`）⇒ 先让探针把**逐帧关节序列**写进报告（现在只存汇总），再按相位左右对比 lf 与 rf 的目标；旧线 v10 记过同一条腿独扛体重（`rl_exp/versions/lizard/main/v10/NOTES.md:66`）可作旁证，但那是载荷不是链条几何。② **高速档目标普遍越界**：1.5–2.8 m/s 四腿 hip/hfe 的目标系统性超出限位（步态记录 ⑦；2.8 档 rl hip 18.3% 帧越界）⇒ 查动作尺度 / PD 增益 / 奖励形状哪一层把它推出去（读数可先做，不依赖 ③）。③ **奖励侧载体**：加回 `feet_slide`/`foot_clearance` 是记录 ⑥ 点明的"仍未答"，但 `rl_exp/versions/lizard2/main/` 下只有 `v1`，没有承接版本 ⇒ 先定载体（新 v2 配方还是 v1 的修订），再谈参数。
close_when: ① 给出 lf 的成因判定并附读数（逐帧左右对比，或明示该对比仍不能定性并说明缺什么）；② 越界的成因落到一层实现并附改前改后的读数，或明示"本版不追"并给出理由；③ 载体定下且改动落在该版本参数上。三件齐即具备关闭条件；任一件被明示不做须写下理由并移出本项——留着不说等于没关。
depends_on: floor-contact-attribution
evidence: acceptance/records/2026-09-23-lizard2-v1-gait-skate.md, acceptance/records/2026-09-23-lizard2-leg-chains-not-mirrored.md, acceptance/records/2026-09-23-gait-probe-exit-status.md
---

## 来源与范围

六件都出自 2026-09-23 的步态补测（记录见 evidence）：读数已闭环，但这六件动作当时没做，且此前只存在于会话里。

不重开 ⑤⑥ 的读数裁定（已入记录）；不改冻结协议，协议侧缺项（`min_lift_m`、`foot_slip_mps`）归
`lizard2-family-landing` 与 `baseline-eval-pipeline-restructure`；不管探针以外的入口退出码，归
`exit-status-swallowed-by-app-close`。

## 未覆盖边界

不覆盖奖励的重新设计（本项只问"载体在哪"）；不覆盖诊断器集成（归 `floor-contact-attribution`）；
不覆盖 0–0.1 m/s 档与足端姿态（`foot_yaw_deg` 仍未算，属新观测，需要时另立）。
