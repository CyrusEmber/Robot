# lizard2 main/v3 运行记录入口

## 设计引用

目的与假设见 [PLAN.md](PLAN.md)。

## 本版重点变化

采用用户批准的候选机体，踝部只取消策略动作通道，保留可动关节与 PD。
完整差异及逐项理由唯一归 [diff.json](diff.json)。

## 实际执行与偏离

自检轮（2026-10-08~09）只实施与验证，无训练 run；那部分命令、运行验证与限制归
`acceptance/records/2026-10-08-lizard2-v3-landing.md`。

训练轮（2026-10-10，v3.4 用户拍板）：本版已冻结（tag `lizard2-main-v3`），随后启动训练。

- run 目录：`logs/rsl_rl/lizard2_v3/<时间戳>`（启动后回填，见下一次提交）。
- 命令形态：`scripts\reinforcement_learning\rsl_rl\train.py --task Lizard2-Flat-v3 --headless`，cwd `E:\IsaacLab`；
  `num_envs`/`seed`/`max_iterations` 用配方声明值（4096 / 42 / 6000），未加会话覆盖。
- 命令行、覆盖参数、seed、checkpoint 的正文在该 run 目录的 `run_manifest.json` / `checkpoints.json`
  （记录本体机器本地、不进仓）：复读 `python rl_exp\tools\runrecord\manifest.py --verify <run 目录>`。

## 结果回填

报告：`acceptance/records/2026-10-08-lizard2-v3-landing.md`。仿真/离线检查按该记录复读。

后续需求与文档状态核对：`acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync.md`；本次仅更新文档，无新仿真或训练 run。

## 结论

本轮工程交付判定见报告；不把接口自检当作 mesh 碰撞、完整动作周期或策略效果验收。
