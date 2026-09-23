---
id: lizard2-gait-followups
title: 步态补测：lf 追因、相位切分、奖励载体
scope: rl_exp/tools/diagnose, rl_exp/versions/lizard2
status: open
landing: rl_exp/tools/diagnose/gait_probe.py, rl_exp/tools/diagnose/diag_metrics.py, rl_exp/versions/lizard2/main/v1/PLAN.md
next: ① **lf 腿追因**（最像真缺陷）：三档的目标净空都为负（读数在记录 ⑥）⇒ 先判"资产/构型固有不对称"还是"策略学出来的"：旧线 v10 记过左前脚独扛体重的极不对称（`rl_exp/versions/lizard/main/v10/NOTES.md:66`、`v10/DIAGNOSE.md:205`，同一条腿），再查该腿的动作分布与关节限幅。② **相位切分复核 p95**：承重接触点速度的 p95 含触地/离地过渡帧（记录 ⑤ 自认的边界）⇒ 把过渡帧剔除后重算，给"稳态滑移"一个带读数的数。③ **探针报告防呆**：报告里写 checkpoint sha + argv（现在只有"跑前删旧报告"的纪律，见记录 ⑥ 第 5 条）。④ **`summarise()` 的离线自检**：段切分、摆动峰值与中位数只有真跑验证过 ⇒ 喂已知合成序列断言段数与峰值。⑤ **退役记录 ② 的旧口径**：② 是旧探针的读数（足端原点高度、刚体速度）⇒ 用 ⑤ 的数字替掉其关键行，只留一句历史说明。⑥ **奖励侧载体**：加回 `feet_slide`/`foot_clearance` 是记录 ⑥ 末段点明的"仍未答"，但 `rl_exp/versions/lizard2/main/` 下只有 `v1`，没有承接版本 ⇒ 先定载体（新 v2 配方还是 v1 的修订），再谈参数。
close_when: ① 给出 lf 的成因判定（固有不对称 / 策略 / 限幅）并附读数；② 切分后的数字入记录；③ 注入一次失败真跑，报告里能读到 sha 与 argv，且失败退出码非零；④ `--self-check` 在合成序列上断言段数与峰值；⑤ 记录 ② 只剩历史说明；⑥ 载体定下且改动落在该版本的参数上。六件齐即具备关闭条件；任一件被明示不做（例如决定不追 lf），须写下理由并把它移出本项——留着不说等于没关。
depends_on: floor-contact-attribution
evidence: acceptance/records/2026-09-23-lizard2-v1-gait-skate.md, acceptance/records/2026-09-23-gait-probe-exit-status.md
---

## 来源与范围

六件都出自 2026-09-23 的步态补测（记录见 evidence）：读数已闭环，但这六件动作当时没做，且此前只存在于会话里。

不重开 ⑤⑥ 的读数裁定（已入记录）；不改冻结协议，协议侧缺项（`min_lift_m`、`foot_slip_mps`）归
`lizard2-family-landing` 与 `baseline-eval-pipeline-restructure`；不管探针以外的入口退出码，归
`exit-status-swallowed-by-app-close`。

## 未覆盖边界

不覆盖奖励的重新设计（本项只问"载体在哪"）；不覆盖诊断器集成（归 `floor-contact-attribution`）；
不覆盖 0–0.1 m/s 档与足端姿态（`foot_yaw_deg` 仍未算，属新观测，需要时另立）。
