---
id: isaac-root-parameterisation
title: G3 收尾：ISAAC_ROOT 三处参数化核认 + 删 junction（PLAN #12）
scope: ablation_harness, rl_exp/tools/verify
status: in_progress
landing: ablation_harness/eval.py, ablation_harness/run_ablation.py, ablation_harness/HARNESS.md
next: 执行者按 evidence 的“独立审核 / 关闭裁定与补证要求”补齐可复读输入与 train/eval 产物；新训完成判定先在关联事项处置。补证后置 pending_review，由不带执行历史的新上下文对照原 close_when、真实布局、离线套件和保留产物重审，不以启动参数捕获或文字总结代替真跑。
close_when: 执行者摘掉 junction 后观察：`rl_exp\tools\verify\run_offline_checks.bat` 全绿，且一条 train/eval 命令能起来——日志目录的 glob 落到真实的 IsaacLab 树而不是本仓 ⇒ 两半都成立即关；任一步失败（例如某处仍在拿"harness 的父目录"当 IsaacLab）⇒ 记下失败点并保持 open
evidence: acceptance/records/2026-10-10-isaac-root-parameterisation.md
---

## 当前状态

本次审核与补证要求见 evidence 的“独立审核”节；下一步按该节执行，补证后重新提交审核。
关联缺陷：`work/active/ablation-sweep-final-checkpoint-name.md`。

## 未覆盖边界

本项不动 harness 的路径解析口径（归 `host_paths.py` 与其闸门），也不改 `paths.yaml` 的机器本地事实；
闸门侧 `RL_ISAAC_ROOT` 的解析属早期已落部分，不在本项重做。eval 子进程的启动路径属本项，
而“训练完成凭据”的命名差一归关联事项。
