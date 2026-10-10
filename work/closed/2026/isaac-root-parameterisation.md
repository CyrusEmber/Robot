---
id: isaac-root-parameterisation
title: G3 收尾：ISAAC_ROOT 三处参数化核认 + 删 junction（PLAN #12）
scope: ablation_harness, rl_exp/tools/verify
status: done
landing: ablation_harness/eval.py, ablation_harness/run_ablation.py, ablation_harness/HARNESS.md
outcome: 独立审核通过原 close_when 的路径与启动验收；分组汇总和整树可重建不在关闭承诺内。裁定见 evidence 的「补证独立审核」节；关联完成凭据事项仍待独立审核。
close_when: 执行者摘掉 junction 后观察：`rl_exp\tools\verify\run_offline_checks.bat` 全绿，且一条 train/eval 命令能起来——日志目录的 glob 落到真实的 IsaacLab 树而不是本仓 ⇒ 两半都成立即关；任一步失败（例如某处仍在拿"harness 的父目录"当 IsaacLab）⇒ 记下失败点并保持 open
evidence: acceptance/records/2026-10-10-isaac-root-parameterisation.md
---

## 当前状态

独立审核裁定见 evidence 的「补证独立审核」节。
关联缺陷事项仍见 `work/active/ablation-sweep-final-checkpoint-name.md`，不由本项代关。

## 未覆盖边界

本项不动 harness 的路径解析口径（归 `host_paths.py` 与其闸门），也不改 `paths.yaml` 的机器本地事实；
闸门侧 `RL_ISAAC_ROOT` 的解析属早期已落部分，不在本项重做。eval 子进程的启动路径属本项，
而“训练完成凭据”的命名差一归关联事项。
