# lizard2 main/v5：头部持续触地终止

> 修订：v5。母本为已训 main/v4；冻结锚点 `lizard2-main-v5`。本轮交付终止规则，不启动训练。

## 目的与假设

用户拍板：2026-10-26，只有头部接触地面连续满 0.5 s 才触发该项，胸部、颈关节及自碰撞不计入。沿用现有 1 N 接触力阈值。实际头部碰撞网格的刚体 owner 名为 `neck_pitch`；没有另一个独立 `head` 刚体，不按字符串把该头部网格排除。

## 差异

完整差异与原因取 [diff.json](diff.json)，母本取 [base.json](base.json)。新 term 和独立头部→地面滤波传感器替换旧 `head_contact`，根部触地与其余配方保持母本。原 term 和 v4 冻结文件不改语义；共享开发态参数不切换。

## 验收

- 实际只绑定头部碰撞 owner 和地面 collider；胸部及自碰撞净力不得进入该项。
- 逐物理子步检查连续接触，达到 YAML 中的持续时间才终止；任何一个离地子步清零，部分/完整 reset 清零对应环境，不跨回合或环境累计。
- 新要求对旧函数的失败对照、新 term 的阈值/边界/间断/reset/错绑定测试和正式原生传感器通道核验可复读。
- v4 配方、资产、位置动作/零速度参考、观测、驱动、奖励、命令、PPO 和根部终止保持原状。验证结果及边界唯一归 [验收记录](../../../../../acceptance/records/2026-10-26-lizard2-v5-head-ground-dwell.md)。

## 启动方案

任务为 `Lizard2-Flat-v5` / `Lizard2-Flat-Play-v5`，runner 为 `Lizard2V5PPORunnerCfg`，日志身份 `lizard2_v5`。本轮不启动新训练、不热改原 v4 进程。既有 v4 checkpoint 始终按原终止规则归因；若后续加载其权重用于 v5，须作为新配方迁移记录源 checkpoint，不冒称同配方续训。

核启动身份但不启动：`python -B rl_exp/tools/launch_recipe.py --task Lizard2-Flat-v5 --seed 42 --record rl_exp/out/lizard2_v5_launch_plan.json`。独立原生核验：`python -B rl_exp/tools/diagnose/palm_preflight.py --task Lizard2-Flat-v5 --out rl_exp/out/<新目录> --num_envs 4 --steps 100 --head_ground_check --viz none`。此开关末尾含隔离强制触地测量夹具，不是步态或性能测试。

## 修订记录

| 日期 | 修订 | 变更与依据 |
|---|---|---|
| 2026-10-26 | v5 | 用户拍板改为头部→地面连续接触终止；已训 v4 保留，新任务承接。 |
