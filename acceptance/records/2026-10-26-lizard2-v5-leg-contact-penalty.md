# lizard2 v5.1：解冻并关闭指定腿部接触惩罚

## 适用范围

用户于 2026-10-26 明确要求去掉指定腿部接触惩罚，并要求在 v5 内解冻修订。核对本机 `logs/rsl_rl/` 未发现 v5 run；旧冻结标签 `lizard2-main-v5` 本地与远端均指向 `8f9ce3a4a3d399220aa60dfabde4ff4e22177821`。按用户授权撤销该标签，保留所有提交历史，不重写已训 v4。

本轮保持解冻提案态，无新训练、无自动重打标签。原终止规则验证保留在 `2026-10-26-lizard2-v5-head-ground-dwell.md`，只按其当时配置解释。

## 验收条件

- v5 TRAIN/PLAY 均不注册指定腿部接触奖励项，同一组接触输入不再扣分；旧版仍能检出并扣分。
- 其余奖励、终止、动作、观测、驱动与命令不变，旧版快照不漂移。
- 撤销 v5 冻结标签并保持提案态；不自动启动训练或重新冻结。

## 结果

v5 YAML 的 `rewards.undesired_contacts` 从 -1.0 置为 0.0；构建器对该零权重不注册奖励项，实际 TRAIN/PLAY 的 `rewards.undesired_contacts` 均为 null。根部触地终止、头部连续触地终止、其余奖励、动作、观测、驱动、命令和 PPO 不变。共享开发态 YAML 与 v4 冻结文件均未改。

`check_cfg_lock.py --update --line lizard2/main` 的逐字段报告只列出两个 v5 任务，每任务仅 `env.rewards.undesired_contacts` 一个路径变化；其余任务快照没有变化。`diff.json` 重新生成并补写用户决策理由，相对 v4 的差异新增该奖励路径。

现有资产锁同时包含版本 YAML。按本次明确解冻授权，只将该 YAML 摘要重新绑定到当前修订，所有 USD/URDF/网格摘要保持原值；没有替换资产或全量刷新其摘要。

### 行为验证

`test_v5_leg_contacts_no_longer_deduct_reward` 使用实际框架 `RewardManager` 和原 `undesired_contacts` 函数，向两个环境的接触历史注入一个腿部刚体 50 N、另一个无接触的输入。旧规则在 0.02 s 控制步返回 `[-0.02, 0]`；修改前 v5 测试实际失败，报仍启用接触惩罚。修改后 v5 TRAIN/PLAY 均不注册该项，同输入返回 `[0, 0]`。其余奖励字段逐项与 v4 比较，仅允许被移除项变化。

本次 v5 测试八项通过，覆盖原头地持续接触边界、reset、隔离及新奖励移除行为。

完整离线套件 37/37 通过；配方构建核对十个任务快照一致。额外逐条比较更新前后的锁条目，只有当前组合下两个 v5 任务变化；资产锁中只有版本 YAML 绑定变化，所有物理资产摘要保持原值。

## 证据引用

复读：

```powershell
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp/tools/verify/test_lizard2_v5.py
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp/tools/verify/check_recipe_build.py
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp/tools/verify/offline_suite.py
git tag --list lizard2-main-v5
git ls-remote --tags origin refs/tags/lizard2-main-v5
```

## 未覆盖边界

接触输入为软件行为测试，不是新仿真策略评测；不据此声明步态、支撑或稳定性改善。训练与策略评测继续由 `work/active/lizard2-family-landing.md` 承接，本项不关闭，也不将本记录视为独立审核。
