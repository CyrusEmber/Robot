# Lizard 26 关节四足机器人训练计划

> SSOT: rl_exp git 仓（例 `E:\lizard_migration\rl_exp\`；参数 `lizard_params.yaml`，
> 几何 `lizard.urdf`，管线脚本 `blender\`；版本冻结 `versions\lizard\vN\`，
> 版本级计划归各自目录）。代码不复制进 IsaacLab 根，部署见仓根 README。
> 更新: 2026-09-01（v3 提案 `versions\lizard\v3\PLAN.md`；包名 lizard_exp→rl_exp；
> versions 家族分层；上一版 2026-08-28 v2.1 teacher 快照落地 + 冒烟通过）

## 1. 目标

26 关节蜥蜴四足（16 腿关节 HAA/HFE/KFE/FOOT + 10 脊柱关节）在粗糙地形上做速度跟踪运动，
最终以盲部署形态（零特权信息）跑进 UE。

参考论文/代码：

| 来源 | 用途 |
|---|---|
| Miki et al. 2022, *Learning robust perceptive locomotion for quadrupedal robots in the wild* (arXiv:2201.08117) | 总路线：teacher(特权 RL) → student(蒸馏)，两阶段 |
| awesomericky/quadruped-robot-belief-encoder | student 网络参考：GRU belief encoder + 门控融合 + belief decoder |
| chengxuxin/extreme-parkour (ICRA 2024) | 全流程代码参考（Isaac Gym 版），延迟注入等工程技巧 |

## 2. 现状快照

### 2.1 资产（已稳定）

- URDF/USD: 26 revolute 关节，72 kg，零位=自然站姿（Blender WYSIWYG 烘焙）
- 站姿验证: 四脚受力合计 ≈ 全重 706N，z 稳定 0.94（平地）
- 脚掌 blade 平板落地；kfe 轴 Y（±1.6），foot 轴 X（±0.5），haa 轴 Y，hfe 轴 Z

### 2.2 环境（已建，lizard 家族 = 活的实验场）

- `Lizard-Velocity-Rough-v0`：蜥蜴尺度地形（16m 瓦片、台阶 0.1~0.5m）、高度扫描 135 点
  （2.8×1.6m @0.2m，覆盖全部脚位）、DR 全套、带噪声扫描
- `Lizard-Velocity-Curriculum-Rough-v0`：staged 三课程变体（备用）

### 2.3 第一次训练（15000 iters）失败复盘

症状: 趴地不动，feet_air_time≈0，success_rate 0.31，课程全卡 stage 0，地形等级 0.1/9。

根因（激励逃生舱）:

1. 趴下时躯干圆柱/大腿着地，`base_contact` 终止只查 base_link → 悬空不终止
2. `flat_orientation_l2` 权重 0 → 趴下不罚
3. 接触惩罚 -1.0 太轻、抬脚奖励 0.125 太低

**决策（做法 2）**: 奖励修复方案（躯干终止/姿态惩罚/接触×5/抬脚×4/降难度）整体**回滚挂账**，
所有环境保持 变量隔离——先验证"特权 obs 能否单独救趴窝"（对照实验），
再决定是否动激励。修复方案细节保留在下表，随时可重新应用：

| 项 | 候选修改（已回滚） |
|---|---|
| 躯干终止 | 新增 `torso_contact`（rear/tail/neck 接触即终局） |
| 姿态惩罚 | `flat_orientation_l2` 0 → -2.0（rough 爬坡冲突，若启用应挪 flat-only） |
| 接触惩罚 | -1.0 → -5.0 |
| 抬脚奖励 | 0.125 → 0.5 |
| 开局难度 | `max_init_terrain_level` 5→0，腿质量 DR ±30%→±15% |

## 3. 总路线（Miki 两阶段 + EP 工程）

```
Phase 1  Teacher: 特权 actor PPO（当前，Lizard-Rough-v0）
Phase 2  Student: 蒸馏（belief encoder + 加噪扫描 + 重建损失）
Phase 3  部署: student → ONNX → UE
```

决策记录:

- **参数版本化**（2026-08-28，用户拍板）: `rl_exp/versions/lizard/vN/` 冻结参数副本 +
  NOTES.md + tb_scalars.csv；跑 vN 只读 vN 的副本（teacher v0 已钉死 `TEACHER_PARAMS_VERSION="v0"`）。
  家族总文档 `FAMILY.md`（任务注册表/版本历史/开新版本流程）。配方变更才升版，换 seed 不升。
- **teacher actor 吃特权**（Miki 式 A 方案，用户拍板），蒸馏成本（belief encoder 全套）接受。
  曾讨论 EP 式非对称 critic（特权只进 critic），因 student 保留高度扫描、A 增益被稀释而推荐 B，
  最终用户选 A 换上限。
- **teacher 独立快照环境**（用户拍板）：不经过任何 lizard 中间层，直接继承框架基类
  `LocomotionVelocityRoughEnvCfg`。理由: teacher 语义 = 论文配方冻结快照，Phase 2 蒸馏依赖其
  稳定不变；与 lizard 家族（活实验场）共享基类会互相干扰（当日两起事故实证）。
  参数仍读 `lizard_params.yaml`（数值 SSOT 保留，代码快照冻结）。
- **奖励基线**（做法 2，用户拍板）: teacher 与论文一致，无激励补丁，做"特权救不救趴窝"对照。

## 4. Phase 1 · Teacher Env（Lizard-Rough-v0）

新文件: `config/lizard/teacher_env_cfg.py` + `config/lizard/teacher_mdp.py`（特权 obs term）
注册: `Lizard-Rough-v0` / `Lizard-Rough-Play-v0`，runner `LizardTeacherPPORunnerCfg`、
`experiment_name=lizard_rough_teacher`（与家族 `lizard_rough` 旧 run 目录隔离，防 checkpoint 污染）。

### 4.1 结构

```
LizardRoughTeacherEnvCfg
  └─ 继承 LocomotionVelocityRoughEnvCfg（框架基类，零 lizard 中间层）
      ├─ 机器人/地形缩放/DR: 快照（从 lizard 家族抄入，冻结）
      └─ 数值参数: 读 lizard_params.yaml（SSOT）
```

快照与家族的两处**有意**差异（均向 stock 语义对齐，2026-08-28 确认）:

1. `TEACHER_TERRAINS_CFG.curriculum = True`——家族在基类置位**之后**替换地形生成器，
   标志回落默认 False（行序不再按难度排列）；teacher 恢复 stock rough 的行序课程。
2. 扫描器 `update_period = decimation*dt`（50 Hz，对齐策略步）——家族替换扫描器后
   该值保持默认 0（200 Hz，浪费 4 倍 raycast）。stock anymal 即 50 Hz。

冒烟已过（PLAY 变体, 2 envs）: `OBS_SHAPE (2,266)` / `ACTION_DIM 26` / `OBS_FINITE True` /
`MASS_SUM ≈ 72 kg`（特权质量真值）/ `FOOT_CONTACT` 四脚真值接触标志正常。

### 4.2 观测（actor 全可见，critic 同源）

```
policy obs (266 维) =
    本体感受: lin/ang vel(带噪) + gravity + commands + joint pos/vel(26) + last_action(26)
  + 干净高度扫描 135 点（特权: 去 Unoise，保留 clip）
  + 真值线/角速度（特权: 无噪声对应项）
  + 腿接触状态 ×4（特权, contact 力值过阈 bool）
  + 摆动时长 ×4（特权, sensor current_air_time）
  + 全 body 质量真值 27（特权, body_mass 读回）
```

### 4.3 动作与命令

- 动作: legs 16 维（scale 0.5）+ spine 锁定（scale 0），obs 保留 26 维（Phase 2 解锁不改结构）
- 命令（teacher 本地覆盖，论文标准）: `lin_vel_x [-1,1]`, `lin_vel_y [-0.5,0.5]`, `ang_vel_z [-1,1]`

### 4.4 特权分档

| 项 | 状态 |
|---|---|
| 接触 bool / air time / 质量 / 真值速度 | ✅ v1（现成数据） |
| 摩擦真值 / 外力真值 | ⏳ v2 挂账（需 event 采样缓存改造） |

### 4.5 与论文的已知偏差

1. 动作空间: 关节位置目标（论文 CPG 相位参数）
2. DR 的 log curriculum（论文 c_k）: 固定范围
3. 摩擦/外力特权 v2 才补
4. 脊柱锁定（论文 ANYmal 无脊柱——形态学处理，非方法偏差）

### 4.6 验收标准

500~1000 iters 内出现交替迈步（feet_air_time 持续 >0），success_rate 爬升过 0.5；
若特权下仍趴窝 → 激励逃生舱假设坐实，启用 §2.3 挂账的奖励修复再训。

## 5. Phase 2 · Student 蒸馏规格（后置，Phase 1 验收后细化）

- 网络: 移植 `RecurrentAttentionPolicy`（GRU belief encoder + 门控融合 + belief decoder 重建外感）
- 输入: 本体感受（瞬时）+ 加噪高度扫描（移植参考仓库 3 噪声模型: 逐点噪声/遮挡/漂移）
- 损失: `L_bc(动作) + L_re(扫描重建)`，噪声课程 c_sk 渐进
- 数据: teacher rollout 存干净扫描，离线加噪（同一批数据可随课程重新加噪）
- 部署: student 零特权、零干净扫描依赖

## 6. 命令速查

```bat
:: Phase 1 teacher 训练
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v0 --max_iterations 4000 --seed 42

:: 回放（自动导出 policy.onnx / policy.pt 到 checkpoint 目录）
python scripts\reinforcement_learning\rsl_rl\play.py --task Lizard-Rough-Play-v0 --num_envs 50 --checkpoint <model.pt>

:: 验证工具（E:\IsaacLab 根目录）
python rl_exp\tools\verify\position_check.py --headless --rough   :: 站立/受力
python rl_exp\tools\diagnose\debug_pose.py --headless             :: 腿对称性
python rl_exp\tools\verify\view_lizard.py --viz kit               :: GUI 观察（注意此脚本挂 Flat-Play 任务）
python rl_exp\tools\trainlog\read_curriculum.py                   :: 课程终态（旧训练）
python rl_exp\tools\verify\teacher_smoke.py --headless            :: teacher env 冒烟（obs 维度/有限性）
```

## 7. 挂账清单

| # | 事项 | 优先级 |
|---|---|---|
| 1 | ✅ teacher env 独立快照重写（去掉 lizard 中间层继承） | 完成 2026-08-28 |
| 2 | ✅ teacher_smoke 解包 bug（gym 5 元组）+ 冒烟通过 | 完成 2026-08-28 |
| 3 | teacher 训练 + §4.6 验收（特权 vs 趴窝对照） | 🔴 当前 |
| 4 | 摩擦/外力真值 obs term（event 缓存） | 🟡 Phase 2 前 |
| 5 | 三噪声模型 C++→Python 移植 | 🟡 Phase 2 |
| 6 | 延迟注入 DR（EP 技巧） | 🟡 UE 部署前 |
| 7 | 奖励修复重应用（若 §4.6 对照坐实逃生舱假设） | 🟡 条件触发 |
| 8 | 资产换代时同步 teacher 快照文件（2026-08-31 起机器化报警：check_dr_parity ④robot 块比对/⑤usda 结构契约/⑥versions asset_lock 哈希锁；同步本身仍是人工，但漏同步会在离线闸门炸出 DRIFT） | 🟢 有闸门 |
| 9 | staged 课程 metric 接线 bug（Curriculum/*/metric 恒 0） | 🟢 低 |
| 10 | yaml obs_layout 更新（感知版 +扫描差异） | 🟢 文档债 |
| 11 | DR 放宽策略 / resume 二阶段 | 🟢 走稳后 |
