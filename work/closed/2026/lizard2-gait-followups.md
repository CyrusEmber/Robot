---
id: lizard2-gait-followups
title: 步态补测遗留：动作接口无界、奖励载体
scope: rl_exp/tools/diagnose, rl_exp/versions/lizard2
status: superseded
landing: rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tasks/lizard2_env_cfg.py
superseded_by: lizard2-family-landing
outcome: 六件各有结局（数值与理由在 evidence 的记录里，本文件不复述）：**相位切分**（承重段两端各剔 2 帧后重算：rl 稳态真滑，其余三条的大 p95 是过渡帧）、**报告身份**（写 checkpoint sha256 + argv）、**`summarise` 离线自检**（合成序列断言，含相位剔除与"p50 是下中位"）、**记录 ② 退役** —— 四件已交付（`15b1bcf` / `71ed49e`）；**lf（左前）那条读数已撤回**（步态记录 ⑧：摆动中段实测净空三档均高于 rf，符号翻转来自线性修正项＝瞬时量，不是姿态）；**两项决定**（动作输出约束放哪一层、奖励变更进 v2 的项与权重）已交 `lizard2-family-landing` 的「当前待决定」，本项不再持有动作。
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
