# lizard2 main/v5：头部持续触地终止

> 修订：v5.1。母本为已训 main/v4；用户要求解冻未训练的 v5，已撤销本地与远端 `lizard2-main-v5` 标签，当前为提案态。本轮修改奖励，不启动训练。

## 目的与假设

用户拍板：2026-10-26，只有头部接触地面连续满 0.5 s 才触发该项，胸部、颈关节及自碰撞不计入。沿用现有 1 N 接触力阈值。实际头部碰撞网格的刚体 owner 名为 `neck_pitch`；没有另一个独立 `head` 刚体，不按字符串把该头部网格排除。

用户拍板：2026-10-26，在解冻的 v5 内去掉指定腿部接触惩罚；YAML 权重置零后不再注册该奖励项。其余奖励及头部持续触地终止保持原语义；移除此惩罚本身不构成步态或稳定性改善的证明。

## 差异

完整差异与原因取 [diff.json](diff.json)，母本取 [base.json](base.json)。独立头部→地面滤波传感器替换旧 `head_contact`，指定腿部接触奖励项关闭，根部触地及其余配置保持母本。v4 冻结文件及共享开发态参数不变。

## 验收

- 实际只绑定头部碰撞 owner 和地面 collider；胸部及自碰撞净力不得进入该项。
- 逐物理子步检查连续接触，达到 YAML 中的持续时间才终止；任何一个离地子步清零，部分/完整 reset 清零对应环境，不跨回合或环境累计。
- 新要求对旧函数的失败对照、新 term 的阈值/边界/间断/reset/错绑定测试和正式原生传感器通道核验可复读。
- 对同一组腿部接触力输入，旧版扣分，v5 TRAIN/PLAY 均无该奖励项且不扣分；其余奖励字段一致。
- v4 配方、资产、位置动作/零速度参考、观测、驱动、命令、PPO 和根部终止保持原状。当前修订验证归 [奖励修订记录](../../../../../acceptance/records/2026-10-26-lizard2-v5-leg-contact-penalty.md)，既有头地通道验证取原记录，不外推为本轮策略性能。

## 启动方案

任务为 `Lizard2-Flat-v5` / `Lizard2-Flat-Play-v5`，runner 为 `Lizard2V5PPORunnerCfg`，日志身份 `lizard2_v5`。本轮不启动新训练、不热改原 v4 进程。既有 v4 checkpoint 始终按原终止规则归因；若后续加载其权重用于 v5，须作为新配方迁移记录源 checkpoint，不冒称同配方续训。

当前保持解冻；下一次开训前须对实际配置重新检查并冻结，不自动重建已撤销标签。

核启动身份但不启动：`python -B rl_exp/tools/launch_recipe.py --task Lizard2-Flat-v5 --seed 42 --record rl_exp/out/lizard2_v5_launch_plan.json`。独立原生核验：`python -B rl_exp/tools/diagnose/palm_preflight.py --task Lizard2-Flat-v5 --out rl_exp/out/<新目录> --num_envs 4 --steps 100 --head_ground_check --viz none`。此开关末尾含隔离强制触地测量夹具，不是步态或性能测试。

## 修订记录

| 日期 | 修订 | 变更与依据 |
|---|---|---|
| 2026-10-26 | v5 | 用户拍板改为头部→地面连续接触终止；已训 v4 保留，新任务承接。 |
| 2026-10-26 | v5.1 | 用户拍板解冻 v5 并去掉指定腿部接触惩罚；理由与验证取奖励修订记录。 |
