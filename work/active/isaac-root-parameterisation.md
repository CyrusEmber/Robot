---
id: isaac-root-parameterisation
title: G3 收尾：ISAAC_ROOT 三处参数化核认 + 删 junction（PLAN #12）
scope: ablation_harness, rl_exp/tools/verify
status: pending_review
landing: ablation_harness/eval.py, ablation_harness/run_ablation.py, ablation_harness/HARNESS.md
next: 由不带执行历史的新上下文审：对照原 close_when 读 evidence 的「补证」节——完整新训链已在修复后真跑走通，spec 在仓内、训练目录与 eval 产物均保留；前次审核退回理由（产物被删）已不复存在。成立 ⇒ 关闭（移 work/closed/2026/、去 next、补 outcome）；仍有缺口 ⇒ 退回 in_progress。
close_when: 执行者摘掉 junction 后观察：`rl_exp\tools\verify\run_offline_checks.bat` 全绿，且一条 train/eval 命令能起来——日志目录的 glob 落到真实的 IsaacLab 树而不是本仓 ⇒ 两半都成立即关；任一步失败（例如某处仍在拿"harness 的父目录"当 IsaacLab）⇒ 记下失败点并保持 open
evidence: acceptance/records/2026-10-10-isaac-root-parameterisation.md
---

## 当前状态

补证完毕：修复后完整新训链真跑走通，spec/训练目录/eval 产物均保留。判定依据见 evidence 的「补证」节。
关联缺陷事项 `ablation-sweep-final-checkpoint-name` 同批待审。

## 未覆盖边界

本项不动 harness 的路径解析口径（归 `host_paths.py` 与其闸门），也不改 `paths.yaml` 的机器本地事实；
闸门侧 `RL_ISAAC_ROOT` 的解析属早期已落部分，不在本项重做。eval 子进程的启动路径属本项，
而“训练完成凭据”的命名差一归关联事项。
