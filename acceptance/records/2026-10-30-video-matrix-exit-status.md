# 录像矩阵入口失败退出码修复

## 适用范围

仅覆盖 `ablation_harness/video_matrix.py` 中模拟器启动后的异常退出；跨入口事项仍在 `work/active/exit-status-swallowed-by-app-close.md`。不改变成功关停，不改变评测协议或策略判分。

## 验收条件

- 真正录像入口失败时调用方能看到异常栈和非零退出码；成功时退出码为零。
- 回归验证在修复前失败、修复后通过，覆盖普通异常、非零 `SystemExit`、输出刷新失败和成功关闭。
- 不以录像输出推断策略性能。

## 结果

| 场景 | 实际入口 | 栈 | 子进程退出码 |
|---|---|---|---|
| 修复前，缺失 checkpoint | `video_matrix.py`，v5 Play 任务、单环境、平地、单视角、1 s | 可见 | 0 |
| 修复后，相同缺失 checkpoint | 同上 | 可见，包含缺失路径 | 1 |
| 修复后，真实 v5 checkpoint | 同上 | 不适用 | 0 |

成功录像保存了原片、对照片和 `matrix.json`；失败跳过 Kit 的 `app.close()`，由操作系统回收进程资源。这是退出状态可靠性的代价，不承诺异常时已打开的第三方资源完成正常关停。无法写入或刷新 stderr 时不能保证栈可见，但退出码仍非零。

回归使用模拟 `app.close()` 直接以 0 退出的独立子进程：原写法普通异常变红（返回 0），引入 `os._exit` 后 stdout 刷新异常仍变红（返回 0）；内层 `finally` 保证非零，先刷新 stderr 再刷新 stdout。修复后四条场景通过，并核验成功时 close 被调用、失败时未调用。初次离线套件报形状闸缺少子进程声明；在 `check_suite_shape.py` 明确一个调用点及其进程边界理由后，完整套件通过。该调用点循环启动四个解释器；本机单独运行本回归约 3.4 s。

独立代码审核发现 stdout 刷新异常会吞退出码、stderr 应优先刷新；修正后新上下文复核未发现阻塞问题。其审核未运行仿真，不代替上述真实读数。

## 证据引用

- 最终真跑日志与录像：`rl_exp/tools/diagnose/out/runs/video_exit_final_eo26ileh/fail.log`、`success.log`、`success/`；本机输出被忽略，不随仓提交。
- 回归入口：`E:\IsaacLab\env_isaaclab\Scripts\python.exe -c "from rl_exp.tools.verify.test_terrain_geometry import test_video_matrix_failure_exit_status; test_video_matrix_failure_exit_status()"`。
- 全套：`rl_exp\tools\verify\run_offline_checks.bat`；本次 37/37 通过。
- 成功 checkpoint：`logs/rsl_rl/lizard2_v5/2026-10-26_16-35-11/model_5999.pt`，位于 IsaacLab 根；命令使用 `--task Lizard2-Flat-Play-v5 --speeds 0.5 --seconds 1 --views side --terrains plane --num_envs 1 --headless`。

## 未覆盖边界

本项其他入口尚未逐个完成失败与成功真跑，不据此关闭跨入口事项。已完成单入口采用原生局部失败出口而非新建共享助手；完整清点后再决定跨入口形态。本记录不验证硬中断、stderr 本身不可写、视频编码器异常后的片段完整性或策略性能。
