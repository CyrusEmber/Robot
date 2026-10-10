---
id: isaac-root-parameterisation
title: G3 收尾：ISAAC_ROOT 三处参数化核认 + 删 junction（PLAN #12）
scope: ablation_harness, rl_exp/tools/verify
status: pending_review
landing: ablation_harness/eval.py, ablation_harness/run_ablation.py, ablation_harness/HARNESS.md
next: 由新上下文审（不带本次执笔会话的历史）：先在本机确认无 junction 布局（`if exist "E:\IsaacLab\ablation_harness"` 应为 MISSING），再跑 `rl_exp\tools\verify\run_offline_checks.bat` 看是否全绿；然后对着 `close_when` 读 `acceptance/records/2026-10-10-isaac-root-parameterisation.md` 的现场读数（两条探针 + 那条 `can't open file` 最小复现），判"三处参数化在无 junction 下成立"与"一条 train/eval 命令能起来"是否**各自被证明**，别读执笔会话的总结。成立 ⇒ 关闭：移进 `work/closed/2026/`、去掉 `next`、补 `outcome`，读数与判词留在那份记录里；只证明了一半、或探针产物删到无法复原结论 ⇒ 退回 `in_progress`
close_when: 执行者摘掉 junction 后观察：`rl_exp\tools\verify\run_offline_checks.bat` 全绿，且一条 train/eval 命令能起来——日志目录的 glob 落到真实的 IsaacLab 树而不是本仓 ⇒ 两半都成立即关；任一步失败（例如某处仍在拿"harness 的父目录"当 IsaacLab）⇒ 记下失败点并保持 open
evidence: acceptance/records/2026-10-10-isaac-root-parameterisation.md
---

## 当前状态

两半都已执行完毕，读数与复现命令在 `acceptance/records/2026-10-10-isaac-root-parameterisation.md`。
执行中查出的两处缺陷分别处置：eval 子进程那处相对路径假设（只有 junction 在时才成立）**已修**，属本项
landing；"训练已完成"凭据与训练器收尾命名差一那处**不在本项**，另立
`work/active/ablation-sweep-final-checkpoint-name.md`。等新上下文评审。

## 未覆盖边界

本项不动 harness 的路径解析口径（归 `host_paths.py` 与其闸门），也不改 `paths.yaml` 的机器本地事实；
闸门侧 `RL_ISAAC_ROOT` 的解析属早期已落部分，不在本项重做。eval 子进程的启动路径属本项（已改），
而"训练完成凭据"的命名差一归另立事项。
