---
id: exit-status-swallowed-by-app-close
title: 入口失败被 app.close() 吞成退出码 0
scope: ablation_harness, rl_exp/tools/diagnose, rl_exp/tools/verify
status: in_progress
landing: ablation_harness/video_matrix.py, rl_exp/tools/diagnose/gait_probe.py, ablation_harness/eval.py
next: 执行者清点剩余入口的异常与拒绝路径，逐个修复并实测，确定跨入口关停形态。
close_when: 每个入口各有两条真跑读数：失败 ⇒ 栈可见且退出码非零；成功 ⇒ 0。工具不许把失败报成成功；形态（共享助手或逐处）在同一变更里定下并说明为何。
evidence: acceptance/records/2026-10-30-video-matrix-exit-status.md, acceptance/records/2026-10-19-lizard2-single-leg-lift.md, acceptance/records/2026-10-19-lizard2-loaded-standing.md, acceptance/records/2026-09-23-persist-before-judge-real-run.md, acceptance/records/2026-09-23-gait-probe-exit-status.md
---

## 来源与范围

`baseline_eval` 的真跑取证暴露出：`app.close()` 会自行结束进程，异常若尚未交给调用方，可能被报成成功。
`baseline_eval` 的裁定不在本项；单入口已完成的修复和证据见 evidence。

## 未覆盖边界

不重开 `baseline_eval` 的裁定（见 `work/closed/2026/baseline-eval-persist-before-judge.md`）；
不改成功路径的关停行为；不评价各入口自身是否该失败（只问失败能否被调用方看见）。

## 下一步

- 复核当前 `eval.py`、诊断和验证入口的实际控制流；已修入口与新发现入口分别核对，不能沿用旧清单假设。
- 每个受影响入口保留失败与成功真跑证据及对应回归；以子进程读退出码，或在 Windows CMD 中使用延迟展开，不能用同一命令行预展开 `%errorlevel%`。
- 检查跨入口共享关停助手与既有原生关停方式的实际适用性，再定形态；不以局部完成代替全部入口验收。

## 关闭条件

沿用 close_when 的逐入口成功/失败真跑及形态决策要求；局部修复不关闭跨入口事项。
