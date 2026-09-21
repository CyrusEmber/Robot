---
id: baseline-eval-measurement-trust
title: 固定窗口验收器可信性：测量契约 + 数值正确 + 采集路径
scope: ablation_harness, rl_exp/tools/verify
status: in_progress
landing: ablation_harness/baseline_frames.py, ablation_harness/baseline_metrics.py, ablation_harness/baseline_eval.py, rl_exp/tools/diagnose/diag_metrics.py, rl_exp/tools/verify/test_baseline_contract.py
next: 只剩一条未取到证：**真实"早终止"记录**——需要一条策略真倒下的 rollout（Play 任务的提前终止项是基座接触，现有六个样本 16/64 env 全活满 1000 帧），据以在真跑上读一次"重生帧不进门槛"；取不到就把该路径的不可达写进验收记录并另立窄项
close_when: 执行者跑完整 20 s 窗口——进程正常退出且落盘 `eval.json`，`verdict` 属于 `pass`/`fail`（既非 `invalid` 也非 `smoke_only`），且四项数值取证在真跑记录上各有一条读数。只有"JSON 齐全"不结项
depends_on: baseline-eval-protocol-gap
evidence: acceptance/records/2026-09-21-baseline-eval-measurement-contract.md
---

## 问题与本次范围

"跑完并把 JSON 落盘"不等于验收器可信。旧窗口的六处度量缺陷都在一次枚举式的读数下成立，其中三处直接
造出**错误结论或空报告**（载荷被 env 维平均、bool 相加当计数、补 `+inf` 转出 NaN、tilt 取最正帧、
门槛缺 `alive` 掩码、未测 tilt 时静默通过；外加 `feet_down_mean` 把逐帧脚数又除以帧数）。
"诊断器跑得通"不能给验收器背书——两条路径共用 `pad_point_clouds`，同一个 NaN 缺陷。

## 当前状态

采集与判定已分家：`baseline_frames`（列契约 + 轴标 + 记录 + 存档）→ `baseline_metrics.judge`
（纯函数，三态 `invalid`/`fail`/`pass`，`python -m ablation_harness.baseline_metrics <record>
--protocol <协议>` 即离线复判）→ `baseline_eval` 只做仿真侧采集。真跑已通过：20 s 跑完、正常退出、
`eval.json` + `eval.frames.pt` 落盘、`verdict = pass`（非 `invalid`、非 `smoke_only`），且各量与诊断器
独立读数一致（MAE 0.01976、位移 +9.459 m、姿态 26.18°、颈链合力 87.2 N、网格 −4.63 mm、
逐脚 duty 0/0.231/0.694/0.714）。六处缺陷 + `feet_down_mean` 均已修并有回归。

**"原生崩溃无异常栈"已推翻**：异常一直到达 Python，吞掉它的是 `app.close()`——Kit 关闭时结束进程，
解释器来不及打印栈（`-X faulthandler` 全程无原生栈）。已修：`main()` 先打印栈并 flush 再关 app，
失败不再表现为静默退出。前两次的异常分别是载荷被平均成 1-D 后的 `IndexError` 与判定侧 cuda/cpu 混用。

**评审补的四项记录校验**（此前只查列齐不查语义）：窗口长度 `steps × step_dt` 必须等于协议窗口、
`start_pos`/`start_yaw` 的形状与有限值、`body_weight_n` 为正、逐帧命令必须落在协议声明的 box 内
（越界即 `invalid`——那份 v1 记录在 1–3 m/s 协议下会被拒绝而不是被判分）。四条各有回归，离线套件 47/47。

未取到的证只有一条：真实早终止样本（见 `next`）。

## 未覆盖边界

不回答 v2 能否被验收（归 `baseline-eval-protocol-gap`）；不覆盖阈值依据（归
`baseline-eval-pipeline-restructure`）；不覆盖详细物理归因（归 `floor-contact-attribution`）。
