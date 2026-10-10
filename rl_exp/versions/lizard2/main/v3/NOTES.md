# lizard2 main/v3 运行记录入口

## 设计引用

目的与假设见 [PLAN.md](PLAN.md)。

## 本版重点变化

采用用户批准的候选机体，踝部只取消策略动作通道，保留可动关节与 PD。
完整差异及逐项理由唯一归 [diff.json](diff.json)。

## 实际执行与偏离

自检轮（2026-10-08~09）只实施与验证，无训练 run；那部分命令、运行验证与限制归
`acceptance/records/2026-10-08-lizard2-v3-landing.md`。

训练轮（2026-10-10，v3.4 用户拍板）：本版已冻结（tag `lizard2-main-v3`，落在 `f1ae6f8`），随后启动训练。

- **作废的一次**：助手于 10:09 起过一次（`logs/rsl_rl/lizard2_v3/2026-10-10_10-09-15`），10:12 按用户要求
  手工终止（该 run 只到 `model_0.pt`，不是一次训练结果）。它的 T0/T1 留在机器本地，**本版训练依据不取它**。
- **正式 run**：用户自行启动，`logs/rsl_rl/lizard2_v3/2026-10-10_10-14-50`，6000/6000 跑满
  （末档 `model_5999.pt`，10:14 起、13:31 收尾）。
- 命令形态：`scripts\reinforcement_learning\rsl_rl\train.py --task Lizard2-Flat-v3 --headless`，cwd `E:\IsaacLab`；
  无会话覆盖，`num_envs`/`seed`/`max_iterations` 取配方声明值（4096 / 42 / 6000）。
- 参考：作废那次实测约 2 分钟才进训练循环（场景创建 23.5 s、仿真启动 115 s），T0 在启动早期即落盘，
  命令行、覆盖参数、seed、checkpoint 的正文在该 run 目录的 `run_manifest.json` / `checkpoints.json`：
  复读 `python rl_exp\tools\runrecord\manifest.py --verify logs\rsl_rl\lizard2_v3\<时间戳>`（相对 `<ISAAC_ROOT>`）。

## 结果回填

| 项 | 值 |
|---|---|
| 训练读数 | 曲线落点 = 本目录 `tb_scalars.csv`（全量 `.full.csv` 留机器本地）；读法 `dump_tb.py` / `plot_tb.py`；**收敛类读数**归 `acceptance/records/2026-10-10-lizard2-v3-training-curve.md` |
| 评测判决 | `ablation_harness/results/lizard2_flat_v5/v3/Lizard2-Flat-v3_5999_deterministic_seed123/eval.json`（协议 `lizard2_flat_v5.json` 判 recipe v3，reader `baseline-criteria-banded-settled-1`，256 envs / seed 123 / 20 s，**pass**）⇒ 读数与边界归 `acceptance/records/2026-10-10-lizard2-v3-first-eval.md` |

报告：`acceptance/records/2026-10-08-lizard2-v3-landing.md`。仿真/离线检查按该记录复读。

后续需求与文档状态核对：`acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync.md`；本次仅更新文档，无新仿真或训练 run。

## 结论

首判 **pass**（八条闸门全过、`invalid_reasons` 空），入口可用成立；训练曲线到 6000 仍在动 ⇒
按短窗预算，"收敛/修复"均不成立。工程交付判定见报告与两份 2026-10-10 记录；
不把接口自检当作 mesh 碰撞、完整动作周期或策略效果验收。
