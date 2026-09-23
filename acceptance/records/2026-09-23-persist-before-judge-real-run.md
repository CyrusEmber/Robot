# eval 先存后判：判分异常下窗口仍在、可离线复判（2026-09-23）

## 适用范围

`ablation_harness/baseline_eval.py`（保存与判分的顺序、`judged_or_recoverable` 的失败消息）、
`ablation_harness/baseline_frames.py`（`save` 的落地与拒覆盖）、`rl_exp/tools/verify/test_baseline_contract.py`
（六条回归）。只回答"判分异常或同路径重采时，已完成采集是否还在、能否离线复判"，不回答判据内容是否
恰当、不回答产品阈值，也不替代 256-env 正式判决（那份见 `2026-09-23-lizard2-v1-first-eval.md`）。

## 验收条件

1. 注入判分异常后，帧记录可加载并离线复判，且复判输出带判分器与协议身份。
2. 写盘失败不留伪完整产物：目标不存在、临时文件不残留。
3. 同路径重采不覆盖原记录，错误指名原因。
4. 工具错误对调用方可见。

## 结果

真跑四次（`Lizard2-Flat-Play-v1` + `lizard2_flat_v2.json` + `model_13999.pt`，16 envs、seed 123、
headless、20 s = 1000 帧），判分侧用必抛 `RuntimeError` 的桩替换 `baseline_metrics.judge`。

- **① 窗口存活**：注入异常后 `inject2/` 只有 `eval.frames.pt`，**没有 `eval.json`**。栈是链式的：
  内层为注入的 `RuntimeError`，外层为 `judging failed (RuntimeError: ...)`，消息带记录路径与
  `python -m ablation_harness.baseline_metrics <record> --protocol <protocol file>`。
- **① 离线复判成立**：对同一记录离线复判得 `verdict=fail`、`invalid_reasons=[]`，
  判分器 `baseline-criteria-banded-settled-1`（`Lizard2-Flat-v2` v2），1000 帧 × 16 env 全部
  `valid_steps=1000`、`survived=true`，位移 32.453 m。
  **该 `fail` 是覆盖率判决，不是策略回归**：16 env 没有 env 落进 0–0.1 m/s 带 ⇒ 该带 "measured nothing"，
  按带判据不算通过。探针因此不产生关于策略的读数。
- **③ 拒覆盖**：第二次以同一 `--output` 真跑，`save` 以 `FileExistsError` 拒绝；链上可见 Windows 的
  `WinError 183` 被翻译成 "already exists: a collection is evidence, and a second one gets its own path"。
  重跑后 `inject2/` 仍只有那一个记录，复判读数与重跑前逐项相同，文件未被覆盖。
- **② 由离线回归覆盖**：`torch.save` 注入失败 ⇒ 目标不存在、无 `.tmp` 残留。
- **④ 先取读数、后修**：栈文本可见，退出码不可见 —— `app.close()` **自己结束进程且状态为 0**，异常状态
  到不了调用方。**测量方法先纠正**：cmd 里 `prog & echo %errorlevel%` 于**整行解析时**展开，打印的是
  运行前的值；改成批处理逐行 `echo %errorlevel%` 后，方法本身先自证（`sys.exit(3)` ⇒
  `METHODCHECK_EXITCODE=3`）。探针读数：`MARK-app-up` 之后 **`MARK-after-close` 从未打印**、
  `CLOSEPROBE_EXITCODE=0` ⇒ close() 不返回，且以 0 结束。
  **已修**：`main()` 的失败分支打印并 flush 后 `os._exit(1)`，跳过 Kit 关停（代价只由已经失败的这次跑付）。
  修复后同形态真跑：`INJECT_EXITCODE=1`，栈与记录路径照旧，`inject3/` 仍只有 `eval.frames.pt`、无 `eval.json`。

## 证据引用

- 注入方式：把 `baseline_metrics.judge` 换成必抛的桩（本次消息
  `injected judge failure: the verdict has to be re-derivable offline`），其余走真入口
  `baseline_eval.main()`。脚本临时、退出即弃。
- 日志：同目录 `run3.log`（注入异常的链式栈）、`run4.log`（拒覆盖）、`run5.log` + `run5_status.log`
  （修复后的退出码）、`exit_probe.log`（测量方法自证 + `app.close()` 探针）。
- 退出码只能按行读：`exit_probe.bat` / `inject_run.bat` 每条命令各占一行，再 `echo %errorlevel%`。
- 记录：同目录 `inject\eval.frames.pt`、`inject2\eval.frames.pt`（`sha256:610fd5ab` 开头；`*.pt` 不入库，
  本地可复判）。
- 复判命令：
  `E:\IsaacLab\env_isaaclab\Scripts\python.exe -m ablation_harness.baseline_metrics <record> --protocol ablation_harness\protocols\lizard2_flat_v2.json`

## 未覆盖边界

1. 同一条退出码缺陷在**其它入口未修**：`ablation_harness/video_matrix.py` 与
   `rl_exp/tools/diagnose/gait_probe.py` 已打印栈但仍以 0 结束；`ablation_harness/eval.py`、
   `rl_exp/tools/diagnose/*`、`rl_exp/tools/verify/obs_protocol_live.py` 等直接
   `simulation_app.close()` 的入口连栈一起吞。本记录只覆盖 `baseline_eval`。
2. 不承诺任意进程中断（SIGKILL / 断电）后的续采或记录完整性；`save` 无 fsync，该上限写在函数注释里。
3. 不覆盖判据内容与产品阈值（归 `lizard2-family-landing`）；也不把 16-env 的带覆盖率差异断言为缺陷
   （归该事项"零命令带依赖 10 s 重采样"那条）。
4. 本记录不含 256-env 正式读数，也不改那份判决。
