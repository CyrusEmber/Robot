---
id: exit-status-swallowed-by-app-close
title: 入口失败被 app.close() 吞成退出码 0
scope: ablation_harness, rl_exp/tools/diagnose, rl_exp/tools/verify
status: open
landing: ablation_harness/video_matrix.py, rl_exp/tools/diagnose/gait_probe.py, ablation_harness/eval.py
next: 先按行读退出码确认现状（cmd 里 `prog & echo %errorlevel%` 是解析时展开，必读成 0——用 `cmd /v:on /c "... & echo !errorlevel!"`，本项 2026-09-23 已用此法取到 1 与 0 两条读数）：`video_matrix.py` 已打印栈但仍以 0 结束；**`gait_probe.py` 已修**（照抄 `baseline_eval` 的失败分支：打印 + flush 后 `os._exit(1)`；失败 ⇒ 栈可见且退出码 1、成功 ⇒ 0，读数见 `acceptance/records/2026-09-23-gait-probe-exit-status.md`）；`eval.py`、`diagnose_*`、`obs_protocol_live.py` 直接 `simulation_app.close()`，连栈一起吞。再定形态：逐处照抄还是收进一个共享关停助手——共 6 处以上，复制即第二处正文。
close_when: 每个入口各有两条真跑读数：失败 ⇒ 栈可见且退出码非零；成功 ⇒ 0。工具不许把失败报成成功；形态（共享助手或逐处）在同一变更里定下并说明为何。
evidence: acceptance/records/2026-10-19-lizard2-single-leg-lift.md, acceptance/records/2026-10-19-lizard2-loaded-standing.md, acceptance/records/2026-09-23-persist-before-judge-real-run.md, acceptance/records/2026-09-23-gait-probe-exit-status.md
---

## 来源与范围

`baseline_eval` 的 P0 真跑取证暴露出：`app.close()` **自己结束进程且状态为 0**（探针读数：`app.close()`
之后那句从未打印、进程状态 0），所以异常即使打印了栈，调用方读到的仍是成功。`baseline_eval` 已修
（失败分支 flush 后 `os._exit(1)`，真跑 `INJECT_EXITCODE=1`）；本项只收其余入口。

## 未覆盖边界

不重开 `baseline_eval` 的裁定（已关闭，见 `work/closed/2026/baseline-eval-persist-before-judge.md`）；
不改成功路径的关停行为；不评价各入口自身是否该失败（只问失败能否被调用方看见）。

## 下一步

执行者继续按 next 清点其它入口及确定共享关停形态；三轴候选新入口的物理判词出口取 `acceptance/records/2026-10-19-lizard2-loaded-standing.md`，报告保存自身失败时的局部修复与回归取 `acceptance/records/2026-10-19-lizard2-single-leg-lift.md`。其余入口及异常分支仍须按各自实际路径取证，不以局部回交代替。

## 关闭条件

沿用 close_when 的逐入口成功/失败真跑及形态决策要求；本轮局部回交不关闭跨入口事项。
