---
id: isaac-root-parameterisation
title: G3 收尾：ISAAC_ROOT 三处参数化核认 + 删 junction（PLAN #12）
scope: ablation_harness, rl_exp/tools/verify
status: open
landing: ablation_harness/eval.py, ablation_harness/run_ablation.py, ablation_harness/HARNESS.md
next: 两半分开做，**核认要在无 junction 的布局下跑，不能只看代码**：① 逐处核认三处参数化已落 —— `eval.py` 的 Isaac root 已委托 `host_paths`、`run_ablation.py` 的 `_ISAAC_ROOT` 同源、`_log_dir_for_tag` 已改成在解析出的树下 glob；② 在原机删 `E:\IsaacLab\ablation_harness` junction（`HARNESS.md` 已记"已废，可 rmdir"），删后复跑离线闸与一次 train/eval 启动
close_when: 执行者摘掉 junction 后观察：`rl_exp\tools\verify\run_offline_checks.bat` 全绿，且一条 train/eval 命令能起来——日志目录的 glob 落到真实的 IsaacLab 树而不是本仓 ⇒ 两半都成立即关；任一步失败（例如某处仍在拿"harness 的父目录"当 IsaacLab）⇒ 记下失败点并保持 open
---

## 当前状态

harness 自定位已从"靠 junction 布局推算"改成一份声明加一次向上探测（`paths.yaml` / `RL_ISAAC_ROOT`，唯一读者 `host_paths.py`），三处调用点读的是同一个来源；`HARNESS.md` 的记录里 junction 已标"已废"。挂账行剩下的就是"**核认到行为**（不是读到声明）+ 在原机摘掉链接"这一收尾。

## 未覆盖边界

本项不动 harness 的路径解析口径（归 `host_paths.py` 与其闸门），也不改 `paths.yaml` 的机器本地事实；闸门侧 `RL_ISAAC_ROOT` 的解析属早期已落部分，不在本项重做。
