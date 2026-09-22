# Lizard 家族退役与 v15 提案取消

## 适用范围

2026-09-22 用户明确决定：“lizard整个家族都要退役，因为机体设计缺陷。”覆盖 lizard/main、lizard/baseline、lizard/parkour；这是 owner 的退役决定，不是新增机体能力测量。lizard2 不在退役范围内，也不据此建立各旧路线到新线的配方继承关系。

## 验收条件

- lines.json 中全部 lizard 路线为 retired；历史资产、锁、代码与结果保留。
- v15 提案取消、移入关闭树；共享 term 语义变化与历史课程缺陷各有可定位入口。
- 路线生命周期、文档与仓内离线闸执行，实际结果补在本记录。

## 结果

### 退役决定

main、baseline 于本日退役；parkour 已退役，保留 2026-09-17 的原始理由。successor 保持 null，不把 lizard2 当作旧配方或 checkpoint 的兼容替代。现有生命周期判据拒绝退役线的新训与续训；它在启动时读取状态，不会终止已在运行的进程。

v15 未冻结、未实施、未训练，随家族退役取消；原并行迁移前置门及四项开训选择不再执行。

### 共享 term 与证据边界

v15/PLAN 的 2026-09-16 处置记录说明：评审后的修复落到共享 JointSIRTerrainCurriculum，v11/v12 golden 随之重生成，改变了冻结时语义。v11/v12 NOTES 现各有显式偏差入口。现有记录为 v11 仅 6-iter 冒烟、v12 无 run；未发现正式训练结果需要重判，不代表冻结语义未变，也不扩大冒烟证据的适用版本。

JointSIRTerrainCurriculum、ParticleVelocityCommand 与 param_grid_terrain 仍在仓；recipe 中的正式版本使用者为 v11/v12。机制有实现与冒烟记录，没有正式训练验证。v15/PLAN 评审 1–5 是历史发现，部分已有共享修复，不可整体当作当前未修缺陷；v15.3 的评分与固定窗口提案也不能当作已实现行为。

### 行 SIR 历史边界

静态实现：walked 为 root_pos 与 env_origins 的平面净位移范数；commanded 为终态平移命令范数乘 max_episode_length_s；成功还要求 reset_time_outs。超时且终态命令为零时距离条件自动通过，非超时终止不因此成功；方向与整段命令积分未被核验。成功标签进入课程采样，所以影响不只是一条日志。

recipe 当前接入行 SIR 的正式版本为 v5/v6/v8/v10/v13/v14，v11/v12 接 joint SIR，不能把 v5–v14 一概混写。历史 run 的实际实现身份仍须核对。v14 terrain_levels 可描述采样等级，不能单独证明通过、跟踪或掌握能力；独立评测不因此自动失效。

反例与历史 run 影响核认由 work/active/row-sir-commanded-measurement-defect.md 承接，本记录不声称已经完成动态验证。

## 证据引用

- 本任务用户 2026-09-22 的家族级退役指令。
- rl_exp/versions/lines.json；rl_exp/tools/verify/recipe_lifecycle.py；rl_exp/tools/runrecord/lifecycle.py。
- rl_exp/versions/lizard/main/v15/PLAN.md：2026-09-16 评审、共享修复处置与原实施选项。
- rl_exp/versions/lizard/main/v11/NOTES.md；rl_exp/versions/lizard/main/v12/NOTES.md；rl_exp/versions/lizard/main/v14/NOTES.md。
- rl_exp/tasks/teacher_mdp.py：SpawnWeightSIRTerrainCurriculum、JointSIRTerrainCurriculum、ParticleVelocityCommand；rl_exp/tasks/recipe.py：RECIPES。
- work/closed/2026/v15-joint-sir-draft.md；work/active/row-sir-commanded-measurement-defect.md。

## 未覆盖边界

- 未修改共享 term、旧冻结参数、golden、资产或任务注册，未重跑训练或评测。
- 家族退役不等于历史结果全部无效，不补造已丢失的运行身份或测量。
- 其它事项需按“新训安排 / 历史证据 / 跨家族机制”逐条审查，不因路径包含 lizard 自动取消。
