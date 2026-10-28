# lizard2 v6.1 转向指令修订

## 适用范围

用户拍板 2026-10-28：目标转速选择 ±0.5 rad/s，并明确解冻尚未训练的 v6，在 v6 内修订，先核对已推标签限制。本机 `E:/IsaacLab/logs/rsl_rl/lizard2_v6` 不存在。已推 `lizard2-main-v6` 指向 `35d9ca11173f90fc22f6812d83e3d7dee1ca04ae`，不撤销、不改指；本次使用新标签 `lizard2-main-v6.1`。这是用户明确授权的同版修订例外，旧快照仍可从原标签恢复。当前事项：`work/active/lizard2-v6-yaw-command.md`。

只改 v6 的 `commands.ang_vel_z` 从 `[0, 0]` 到 `[-0.5, 0.5] rad/s`。沿用原 TRAIN/PLAY 任务、日志身份、10 s 换档、102 维观测、0.5 权重与 0.5 rad/s 标准差的转速跟踪奖励、腹部接触立即终止。未训练、未加载策略、未产出权重。正转速为左转，负转速为右转；这是转速而非目标朝向角。

## 验收条件

- 旧零转速配置使新回归因预期范围失败；修改后实际 UniformVelocityCommand 在 TRAIN/PLAY 均采样左右转并进入 generated_commands 观测，不被 heading/standing 覆盖。
- 真实 track_ang_vel_z_exp 在目标 +0.5 rad/s 时，跟随奖励高于静止，静止高于反向；既有腹部重开回归仍成立。
- 原生仿真按原始周期换档，策略观测命令段逐步等于实际指令，命令不超范围；零动作不触发重开，排除 reset 重采样冒充定时换档。
- 黄金工具只报告 v6 TRAIN/PLAY 的两个转速边界变化；旧标签不变，相关检查和仓库闸门通过。声明一致不作为策略能力证据。

## 结果

- 修改前 `v6_yaw_regression_before.log` 报 `AssertionError: v6 yaw range is still zero-only`，退出 1；修订后同一新增测试通过，`test_lizard2_v5.py` 全部 12 项通过，包括腹部接触、历史头部持续接触及 v4/v5 保持回归。
- 原生 Play-v6：16 环境，seed 42，10.1 s / 505 控制步。初始与 9.9 s 指令计数均为 1，10.1 s 全部为 2；reset 总数 0。初始转速约 -0.39 至 +0.48 rad/s，末段约 -0.48 至 +0.39 rad/s。逐步检查观测传递、上下界和左右符号均成立；102 维观测中命令从偏移 9 开始，宽度 3，依据运行时管理器维度定位。
- 目标 +0.5 rad/s 时，真实奖励函数的加权奖励率：跟随 0.5，静止约 0.18394，反向约 0.009158；管理器每步仍乘 dt。因此转向目标下静止奖励降低，但没有消除所有静止收益。
- `check_cfg_lock --update` 仅报告 `Lizard2-Flat-v6`、`Lizard2-Flat-Play-v6` 各 2 个 yaw 边界变化，其他任务条目未变。新锁 SHA256 `b1396611378c26e9f723fde301e38404db801692c74093fe6cac1fca2cc9172d`。资产锁使用生成器重建，旧锁备份在 ignored out；资产字节未变，仅 YAML 摘要随授权修订变化。对母本 v5 的完整声明为腹部选择 1 路径、转速 2 路径、runner 日志名 1 路径。
- 全部离线闸门 37/37 通过（155.8 s，jobs=2）；首次因本记录章节名称不符格式失败，修正后完整复跑。成本检查依工具原规则单独复跑确认在预算内，未放宽门槛。启动器仅核计划，报告 v6 可新训，无 `--launch`，无新 run。独立审核见末节。

## 证据引用与复读

原始本机产物均在 ignored `rl_exp/out/`；本记录保存结论，入口保留在仓内。使用 `E:/IsaacLab/env_isaaclab/Scripts/python.exe -B`：

```text
python -B rl_exp/tools/verify/test_lizard2_v5.py
python -B rl_exp/tools/diagnose/yaw_command_probe.py --out rl_exp/out/v6_yaw_native_rerun.json --viz none
python -B rl_exp/tools/verify/check_cfg_lock.py --diff --line lizard2/main
python -B rl_exp/tools/launch_recipe.py --task Lizard2-Flat-v6 --seed 42
python -u -B rl_exp/tools/verify/offline_suite.py --python E:/IsaacLab/env_isaaclab/Scripts/python.exe --jobs 2
```

修改前单项命令：`python -B -c "from rl_exp.tools.verify.test_lizard2_v5 import test_v6_yaw_command_sampling_and_reward; test_v6_yaw_command_sampling_and_reward()"`。复现负对照时，在临时工作树检出旧标签的 YAML 后执行新测试，不能覆盖已经训练的版本。原始日志：`v6_yaw_regression_before.log`、`v6_yaw_regression_after.log`、`v6_yaw_native.log`、`v6_yaw_native.json`、`v6_yaw_cfg_update.log`、`v6_yaw_asset_lock.log`、`v6_yaw_offline_suite_verified.log`、`v6_yaw_launch_plan.log`。腹部物理依据仍见 [原记录](2026-10-28-lizard2-v6-belly-reset.md)，本轮测试继续验证其终止接线。

## 未覆盖边界与审核

没有启动策略训练，不能证明策略会响应转向、转弯稳定或前进性能提升。原生零动作仿真验证指令链及站立负对照，不测步态。旧 v5 策略从未训练非零转向目标；直接迁移不能视为已具备转弯能力。

独立审核通过（2026-10-28，新上下文）：已对照关闭条件审阅实际 YAML、指令接线、回归与原生探针实现、差异声明、锁生成日志和现有原始证据；未发现阻断本次配方修订的实质缺陷。修改前失败与修改后通过对应同一转速回归，TRAIN/PLAY 指令与奖励证据及原生定时换档证据支持所述边界，腹部重开回归保留；原标签实际仍指向 `35d9ca11173f90fc22f6812d83e3d7dee1ca04ae`。按用户要求，本次审核未新增检查、未重跑测试或仿真，未读取 cfg_lock.json 正文；锁范围依据生成工具现有输出，v6.1 标签仍须由执行者在提交后建立。不据此认定策略学会转弯。
