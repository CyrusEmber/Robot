# gait 探针的失败不再伪装成成功（2026-09-23）

## 适用范围

条目 `work/active/exit-status-swallowed-by-app-close.md` 的**一个入口**：`rl_exp/tools/diagnose/gait_probe.py`。
`app.close()` 自己结束进程且状态为 0，所以异常即使打印了栈，调用方读到的仍是成功——而本探针的报告只在
run 末尾写，**"成功"就会让上一份 JSON 留在原地被当成新读数**（本探针 2026-09-23 真崩过一次，见
`2026-09-23-lizard2-v1-gait-skate.md` ⑥ 第 5 条）。其余入口与形态选择（共享助手 vs 逐处）归该条目。

## 验收条件

失败 ⇒ 栈可见**且**退出码非零；成功 ⇒ 0。退出码必须按行读：`cmd` 里 `prog & echo %errorlevel%` 是
解析时展开，必读成 0 ⇒ 用 `cmd /v:on /c "... & echo !errorlevel!"`。

## 结果

| 跑 | 注入 | 栈可见 | 退出码 |
|---|---|---|---|
| 失败 | `--checkpoint missing_checkpoint.pt` | 是（`FileNotFoundError` 落在日志里） | **1** |
| 成功 | 真 checkpoint，`--speeds 0.5 --seconds 1` | — | **0** |

修法照抄 `ablation_harness/baseline_eval.py:321-330` 的失败分支：`traceback.print_exc()` + 两个
`flush()` + **`os._exit(1)`，在 `close()` 之前**离开。代价是失败跑跳过 Kit 关停，只有已经失败的跑付这一价。

## 证据引用

- 代码：`rl_exp/tools/diagnose/gait_probe.py`（`__main__` 的失败分支）。
- 两条读数机器本地：`rl_exp/tools/diagnose/out/gait_probe/exit_fail.log` 与 `exit_ok.log`（`out/` gitignore）。

## 未覆盖边界

只处理这一个入口；不评判各入口自身是否该失败；不改成功路径的关停行为；`--self-check` 不启仿真，不走该分支。
