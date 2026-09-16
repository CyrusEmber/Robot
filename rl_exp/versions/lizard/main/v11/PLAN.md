# v11 PLAN —— 多维联合粒子滤波地形课程（Lee 2020 复刻 + 联合粒子扩展）

> 生成：2026-09-10。状态：**提案态**——v10 在训，本版开发可并行，**开训锚等 v10
> 判决**（归因隔离，见 §10）。决策来源：2026-09-10 用户系列拍板——band=[0.5,0.9]
> 论文值；全部课程/地形旋钮暴露 yaml；旧版代码必须可复现；结构解耦（add-only）；
> 地形升级参数与难度等级表进 yaml。
> 论文依据：Lee et al. 2020（arXiv:2010.11251，Science Robotics）公式 2–10 +
> Algorithm S1，HTML 全文逐式核对（2026-09-10）。归因声明见 §9。
> 本文件为 v11 设计 SSOT；实施 kickoff 时冻结 yaml 副本 + 建 NOTES.md。
> 修订：v11.2（2026-09-10 记录性勘误：§2.2 预算按归一化比例重算、§5 草图删
> 未实现键、§11 两行对齐实现——见修订记录）。

## 1. 目的与假设

三个要解的问题：

1. **对角线问题**：stock `TerrainGenerator` 用单一难度标量 t∈[0,1] 把该类型所有
   参数同步插值（`TEACHER_TERRAINS_CFG_V3` 实锤：stairs 的 step_width 恒 0.7、
   stones 的 width/distance 绑定增减）。离对角组合（高台阶+宽踏面、窄石+密排）
   永远采不到。Lee 2020 自证：可行分布在 (frequency, amplitude) 边缘呈**弓形**
   （其 Fig. S1B）——1-D 难度标量表示不了。
2. **速度盲维**：v5 起 `lin_vel_x (0,3)` 命令均匀随机，与课程无关。"同一地形
   不同速度"（0.4 m 台阶慢速能过、快速不行）不可表达、不可测量。
3. **测量口径**：v5.5 定案的"二值终局代理"（timeout & 走完 50% 指令距离）回
   论文逐步 Tr——家族 PLAN 挂账 #15 候选 a 落地。

**假设**：联合粒子 (类型, 参数格, 速度桶) 的 SIR 把训练流量集中到 Tr∈[0.5,0.9]
的曲面（薄壳）上；壳的多模态（难地形+慢速 / 易地形+快速 / 离对角组合）得到
充分训练，且 cell 的 episode 占比显著高于 v10。

## 2. 粒子与网格设计

- **粒子** p = (类型 τ, 参数格 cell, v 桶)，联合不分家（Tr 是 (地形,速度) 联合
  函数，拆两个 PF 互相污染测量）。默认 **16 粒子/类型**（Lee 用 10；多维补偿
  上调），yaml 可调。
- **网格（菜单）**：startup 冻结生成。cell = 该类型参数表的**独立采样组合**
  （非行插值对角线）。速度维不占地形内存，只在粒子状态里。
- **粒子（火力）**：流量只落在粒子引用的 (cell, v) 对上，网格大小 ≠ 粒子数。

### 2.1 默认参数档位表（全部 yaml 可调，值即难度等级）

| 类型（比例） | 参数轴 × 档位（默认值） | cell 数 |
|---|---|---|
| pyramid_stairs (.2) | step_height ×5 [0.08, 0.17, 0.27, 0.36, 0.45]（v11.1 顶档 0.55→0.45 等距重切）；step_width ×3 [0.5, 0.7, 0.95] | 15 |
| pyramid_stairs_inv (.2) | 同上 | 15 |
| stepping_stones (.1) | stone_width ×3 [0.5, 0.7, 0.9]；stone_distance ×3 [0.3, 0.5, 0.7] | 9 |
| boxes (.1) | grid_height ×3 [0.08, 0.19, 0.30]；grid_width ×2 [0.6, 0.9] | 6 |
| random_rough (.2) | noise_amp ×4 [0.10, 0.18, 0.27, 0.35]（downsampled_scale 0.5 恒定，v4 定案 ≥掌宽 0.46；v11.1 勘误：原表停留 v3.6 的 0.3） | 4 |
| hf_pyramid_slope (.1) + inv (.1) | slope ×4 [0.0, 0.15, 0.30, 0.45]（v5 满档 0.45 rad；v11.1 勘误对齐 yaml 实值） | 4+4 |
| flat 启动列（v5.3 先例保留） | — | 若干 |
| **速度桶（公共维）** | lin_vel_x ×6 [0.5, 1.0, 1.5, 2.0, 2.5, 3.0] | 0（粒子态） |

v11.1 勘误后本表逐值镜像冻结 yaml（此前 rough/slope/downsampled_scale 三处
停留在 v3.6/v3 时代值，与 V4/V5 实际配置不符）。

各轴档数**不对齐**——按该轴 Tr 陡度定（单轴一格跨度不得让 Tr 跳过整条带，
否则该轴重演 v10 前诊断的 C 场景）。默认值取自 V3 cfg 各 range 线性切档，
实施时按 preflight 渲染复核后可改。

### 2.2 流量预算（v11.1 实测回填）

```
每类型每块 episode 数 ≈ num_envs × prop × (eval_every × steps_per_iter / episode_len)
粒子数 ≤ 上式 / n_traj_min
```

实测口径：**4096 env**（stock 基类默认——v10 run `params/env.yaml` 实证，注册
命令不带 `--num_envs`；原估算误按 2048）、块 = 10×24 = 240 步、episode =
20 s × 50 Hz = **1000 步**（v10 删 tilt 后仅 time_out → 满长）→ 每块每 env
0.24 次 reset。

| 比例（归一化后，∑=1.125） | 类型 | eps/块 | ÷16 粒子/块 |
|---|---|---|---|
| .2→.178 | stairs / stairs_inv / rough | ≈175 | **10.9** ✓ |
| .1→.089 | stones / boxes / slope / slope_inv | ≈87 | **5.5 低于线** |

.1 类**低于** n_traj_min=6（Poisson λ≈5.5 → 每块 ~60% 单粒子 pair 被审查；
v11.2 勘误：v11.1 行误按未归一化比例算，高估 12.5%）——
**v11.1 修复**：`_resample_all` 只清零已结算 pair（episodes ≥ n_traj_min），
未结算 pair **跨块累积**证据直到过线再结算（原实现每块无条件清零 + 保旧权
只冻结旧权不攒证据，低流量 pair 永远走 previous 分支 = 权重永久均匀，SIR
对低比例类型退化为随机游走；v5 同构代码靠 tilt 短 episode 养活，v10 删截断
后前提失效）。per-type 粒子数旋钮仍不存在（particles_per_type 全局单值），
跨块累积机制覆盖之。

## 3. 测量口径（Tr，Lee 2020 Eq.2/3/7 逐式复刻）

1. **逐步标签** ν(s_t,a_t,s_{t+1})：`v_pr > 0.2` 记 1，否则记 0。
   v_pr = 基座速度·指令方向内积（带符号：倒退/横漂 ≤0 → 0；超速不罚）。
   0.2 m/s 的 1/3 最大速度经验值，yaml 暴露；对 (0,3) 命令域保持绝对值
   ——低速桶因此天然偏易、被推向难地形/高速，自适应压力即设计意图。
   **v11.1 勘误**：终止步无 done 特判，按实际速度记——论文"终止记 0"未
   逐式复刻；v10 后仅 time_out（机器人常仍在运动），影响≈0，作为已知
   偏差记录而非复刻声明。
2. **轨迹 Tr** = 该轨迹逐步标签平均 ∈ [0,1]（"以达标速度推进的时间占比"）。
   终止后步不存在（**非**补零到满 episode 长；终止转移本身按实际速度记，
   见第 1 条偏差）。
3. **粒子权重**（Eq.7）= N_traj 条轨迹中 per-traj Tr ∈ **[0.5, 0.9]** 的
   **轨迹占比**（不是"平均 Tr 落带"）。带值 yaml 暴露，默认论文值（用户拍板
   2026-09-10）。
4. 轨迹复用训练 rollout，无独立评估（论文明示）。

**口径反转记录**：v5.5 二值终局代理 → v11 逐步 Tr（挂账 #15 候选 a）。
v10 前的 v1–v10 语义不受影响（旧类冻结，见 §6）。

## 4. 课程动力学

| 机制 | 定案 | 出处 |
|---|---|---|
| eval 块 | 每 10 iter 重采样一次 | Lee N_evaluate |
| 重采样 | 按权重 multinomial，粒子数/类型不变 | Alg S1 |
| 随机游走 | p=0.8，**单轴 ±1**（随机选一条参数轴或 v 桶） | Alg S1 + 多维扩展 |
| replay | p=0.05 从历史池均匀回抽 | Alg S1 |
| 带空兜底 | 见 §4.1 | 本仓扩展 |
| 冷启动 | 全最易 combo（levels 全 0）+ v 桶 0.5–3.0 轮转（v11.1 勘误：原"uniform + 近平地/低速偏置"与实现不符——非 flat 类型的最易 combo ≠ 近平地，且无低速偏置） | Lee 初始化 |

### 4.1 带空兜底（方向分流，泛化到 (cell,v) 对）

total==0 时按 learned = (该对 N_traj 轨迹 Tr 均值 ≥ hi) 分流：

- **混合态**（有 learned 有未 learned）：维护份额 maintain_mass（默认 0.1）均摊
  learned 对；主力集中在"learned 对的单轴一步邻居"（前沿壳的贴边采样）。
  游走自动把主力 40% 落回 learned 侧、40% 探更远。
- **全 learned**（真掌握）：uniform 重探（论文语义，flat once mastered）。
- **全未 learned**（冷启动全失败）：uniform（v5.4 裁决先例——论文冷启动也全
  失败，不引入自制判据）。

### 4.2 命令接线

粒子 v 桶 → env reset 时直写 `command_manager.get_term("base_velocity").vel_command_b[env_ids]`
（play.py/eval.py 同款机制），桶内加小抖动（yaml）。**时序待验证**：CommandTerm
自身 reset resample 与课程 term 写入的先后（smoke 必验项，后写者胜）。

## 5. yaml SSOT 设计（用户拍板：全部暴露）

`versions/lizard/v11/lizard_params.yaml` = v10 全量拷贝 + `v11:` 段：

```yaml
v11:
  terrain_grid:              # 难度等级表（生成器与课程共读，单一真源）
    stairs:   {step_height: [...], step_width: [...]}
    stairs_inv: {...}
    stepping_stones: {stone_width: [...], stone_distance: [...]}
    boxes:    {grid_height: [...], grid_width: [...]}
    random_rough: {noise_amp: [...]}
    slopes:   {slope: [...]}
    proportions: {stairs: 0.2, ...}      # 类型比例
  velocity_buckets: [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
  terrain_curriculum:         # 升级旋钮
    band: [0.5, 0.9]
    v_pr_threshold: 0.2       # [m/s]
    particles_per_type: 16
    eval_every: 10
    n_traj_min: 6
    p_transition: 0.8
    p_replay: 0.05
    maintain_mass: 0.1
    command_jitter: 0.1       # [m/s] 桶内抖动
```

`check_obs_layout.py` 追加 v11 断言：cfg 字段 ↔ yaml 逐项对表（沿用 v5 模式）。

## 6. 解耦与复现纪律（用户拍板）

**冻结清单（一字不改）**：

- `SpawnWeightSIRTerrainCurriculum` / `SIRTerrainCurriculumCfg`（v5–v10 语义，
  含 v5.5 二值代理——挂账 #15 的 a/b 分叉保留可回退）
- `TEACHER_TERRAINS_CFG` / `TEACHER_TERRAINS_CFG_V3` 及 v1–v10 全部 env cfg 类
- v1–v10 yaml 段、任务 id、runner experiment_name、log 目录
- eval 协议 `locomotion_eval_v1.yaml` + 现有 suites（跨版本对账基准）

**新增清单（add-only）**：

- `rl_exp/tasks/param_grid_terrain.py`：本地复制 stock `TerrainGenerator` 改造
  （行难度插值 → 显式参数表组合采样；仓库"本地复制避 import 链"先例）
- `teacher_mdp.py` 追加 `JointSIRTerrainCurriculum` + `JointSIRTerrainCurriculumCfg`
  （复用 SpawnWeightSIR 骨架 ~80%：记账/重采样/游走/replay/spawn）
- `teacher_env_cfg.py`：`TEACHER_TERRAINS_CFG_V11`（读 yaml 参数表构建）+
  `LizardRoughTeacherEnvCfg_V11(V10)`（override `params_version="v11"` + 换
  terrain cfg + 换课程 term，一行子类模式）+ 注册 `Lizard-Rough-v11` /
  `Lizard-Rough-Play-v11`（PLAY 走 `apply_play_wiring`，禁手抄清单）

**结构原则**：地形参数表 = 生成器与课程共读的单一真源（yaml 一处，两处消费）；
旧版本复现 = 旧任务 id + 旧 yaml 段 + 旧类，三者全冻结，offline 闸门全版本
parity 不回退。

## 7. 实施件与验证链

| # | 件 | 验证 |
|---|---|---|
| 1 | `param_grid_terrain.py` 生成器 | terrain_preflight 渲染 + 逐 cell 参数断言 + **坑#9：替换后显式重设 `curriculum=True`** |
| 2 | `JointSIRTerrainCurriculum` | `tools/verify/test_joint_sir.py`（仿 test_staged_curriculum mock 模式）：粒子记账 / 权重=带内轨迹占比 / 单轴游走 / 兜底三分支 / 命令写入断言 / **回归：v5 SIR 旧测试全绿** |
| 3 | V11 cfg + 注册 | `check_obs_layout.py` v11 断言 + `teacher_smoke_v11.py`（obs 维度不变 381 / 命令=粒子桶 / spawn 落格正确 / resample 后 frontier 键非零） |
| 4 | yaml v11 段 | check 对表 |
| 5 | offline 闸门 | `run_offline_checks.bat` 全绿（含 v1–v10 旧断言不回退） |

## 8. 指标与验收（预注册）

**新 TB 键**（class-based term `__call__` 返回 dict，每键自动进
`Curriculum/joint_sir/<key>`）：

- `frontier_max_v`：每类型带内最大 v 桶均值——**进度主指标**（对标旧
  `terrain_levels`，判读语义沿用挂账 #13：爬升=课程工作，长期贴地才复核）
- `particle_entropy`：粒子分布熵——多模态健康（塌 0 = 前沿坍缩告警）
- `tr_mean`：带内粒子 Tr 均值——带内居中度

probe（`probe_run.py` CURRICULUM 组自动读新键）+ `plot_tb.py:44` 键表加三行。

**验收线**（v10 判决后开训，~2000 iter 节点判读）：

1. `frontier_max_v` 爬升（课程活性）
2. `particle_entropy` 不塌 0
3. `tr_mean` 落 [0.5, 0.9] 附近
4. **离对角验证**：非对角 cell（参数组合偏离旧难度对角线）episode 占比 > 20%
   ——对角线问题的直接量化
5. eval v1 旧套件 completion 不低于 v10 同期（能力不回退）

## 9. 归因声明

- **论文血统**（Lee 2020）：SIR 骨架、超参默认值（N_evaluate 10 / N_traj 6 /
  p_transition 0.8 / p_replay 0.05）、Tr 口径 Eq.2/3/7、带 [0.5,0.9]。
- **本仓扩展**（超出论文，训练口径注明）：速度桶入粒子（论文命令随机、不入
  粒子）；冻结参数网格（论文每粒子重生成地形——RaiSim 无 cook 管线，本平台
  代价见 v11 讨论记录：全网格重生成 ≈ 5–20 s 停摆/次）；参数独立采样 cell；
  带空方向分流兜底。（v11.1 勘误：原列"近平地冷启动偏置"未实现，实际
  冷启动 = 全最易 combo + 全速度桶轮转。）
- **口径反转记录**：v5.5 二值终局代理 → 逐步 Tr（挂账 #15 候选 a 落地）；
  v5"速度课程移除" → v11 速度入粒子（自适应，非线性 ramp 回退）。
- **与挂账 #14 的关系**：参数表化 yaml 与候选 b（组件 spec 表化）同向，但本版
  只表化地形/课程两件，不做全面组件库改造。

## 10. 版本纪律与时序

- v9 空号保留（断腿线，重基 v8 提案态）；v10 在训锚不可逆 → v11 开新版本。
- **开训门 = v10 判决**，判决标准 = v10 NOTES 验收 1–5（time_out 占比 → 1.0、
  success_rate 离开 0.019、terrain_levels 爬升、belly ≈ 0、track_lin_vel 回升
  vs 0.79 基线）。v10 若判废，v11 重基决策（重开 v12 或改基）另议。
- 开发时序：§7 件 1–5 可与 v10 训练并行；冻结 yaml + NOTES + asset_lock 在
  kickoff 时完成。
- 训练命令（注册后）：
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v11 --max_iterations 15000 --seed 42
  ```
- log 目录：`logs/rsl_rl/lizard_rough_teacher_v11/`（runner experiment_name
  隔离）。

## 11. 风险与已知上限

| 风险 | 对策 |
|---|---|
| (cell,v) 对测量稀疏（低比例类型） | v11.1：未结算 pair 跨块累积到 n_traj_min 再结算（.1 类 ≈5.5 eps/粒子/块，低于线——v11.2 按归一化比例重算）；粒子集中 |
| 起步 policy 弱（v10 翻身若未成） | 冷启动全最易 combo + 全桶轮转；带绝对下限 0.2 m/s 不设相对阈值 |
| 命令写入时序（resample vs 课程） | smoke 必验项；后写者胜，必要时挂 reset 后钩子 |
| 参数档位断崖（相邻档 Tr 落差 > 带宽） | 档位表 yaml 可调——调档 = 参数级变更，升 v11.M 不必 v12 |
| v10 判废 | §10 重基 |
| 旧测试回归 | v5 SIR 旧断言由 `test_v5_terrain_sir.py` 承担（离线闸门 [10/11]，同基线防漂移）；同文件重复断言取消（v11.2 勘误：原计划"同文件跑"未实施，两套断言并存反而漂移） |

## 12. 待办（实施 kickoff 清单）

- [x] 开发（2026-09-10，与 v10 训练并行）：件 1–5 落地——`param_grid_terrain.py`、
  `teacher_mdp.py` v11 段（ParticleVelocityCommand + JointSIRTerrainCurriculum，旧类零改动）、
  冻结 `v11/lizard_params.yaml` + asset_lock（`--update-locks` 重锁）、V11/PLAY 类 + spec
  `v11` 键 + 注册 + runner、`test_joint_sir.py` 9/9、`check_obs_layout.py` v11 断言、
  `run_offline_checks.bat` [11/11] 全绿、`plot_tb.py` progress 图加三键。
  **smoke 延后**（用户拍板 2026-09-10：训练开始再起 sim）：PLAY 段已验
  （obs 381 三组 / 无 tilt / 命令回落 / spine 0.25 / 有限性），TRAIN 段已验
  （480 cell 网格 6.7 s 生成、命令项 = ParticleVelocityCommand），其余 TRAIN 断言
  （joint_sir 活性 / 4×120 落格 / 桶命令 / frontier_max_v 键）留开训前跑
  `teacher_smoke_v11.py --headless` 补验
- [x] v11.1 审查四修（2026-09-10，用户拍板"顶档降 0.45，别的也修"，见修订记录）：
  stairs 顶档 0.45 重切 yaml、`_resample_all` 结算式清零（P0）、`JOINT_SIR_TERM`
  常量化 + `desired >= 0.0` 哨兵、PLAN 四处勘误 + 修订记录节；
  `test_joint_sir.py` 10/10（新增跨块累积回归测试）
- [ ] v10 判决（开训门）：NOTES 验收 1–5
- [ ] 开训前：`teacher_smoke_v11.py --headless` TRAIN 段全绿
- [x] episode 长度/env 数实测 → §2.2 预算表回填（v11.1：4096 env × 1000 步，
  20 s × 50 Hz，v10 run env.yaml 实证）
- [ ] preflight 渲染 v11 网格（逐 cell 参数断言 + 目视；重点 stairs 顶两档
  0.36/0.45——超出历史任何训练/评测实证范围）
- [x] 家族 PLAN 挂账 #15 状态更新（候选 a 由 v11 落地）

## 修订记录

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-09-10 | v11.1 | 审查四修（用户拍板"顶档降 0.45，别的也修"；离线闸门 11/11 绿）：① **stairs 顶档 0.55→0.45**（等距重切 [0.08,0.17,0.27,0.36,0.45]，yaml+PLAN 同步）——动力学演算：腿关节力矩/功率全过（最坏 ~106 N·m vs 180 限），卡在躯干几何（0.55 = 站高 0.94 的 59%，腹面借越无余量）且 0.42/0.55 从未被任何 run 实证（terrain_levels 贴地、eval 套件止于 0.20）；v3.4.1 卡排判据预判在先。注意：0.36/0.45 仍超实证范围，preflight 重点目视。② **P0 课程静默死缺陷**：`_resample_all` 原每块无条件 `episodes.zero_()`，keep-previous 只冻结旧权不攒证据 → 低流量 pair（.1 类 6.15 eps/粒子/块，Poisson 下 ~40%/块被审查）权重永久均匀；改为结算式清零（只清 episodes≥n_traj_min 的 pair，未结算跨块累积）。v5 同构代码不动（冻结纪律；它靠 tilt 短 episode 养活）。回归测试 `test_sparse_pair_accumulates_across_blocks`（旧代码下必红）。③ **`JOINT_SIR_TERM` 常量化**（teacher_mdp 定义 + env cfg setattr + check_obs_layout getattr 三处同源，防部分改名静默回退均匀命令）+ `desired > 0.0` 哨兵改 `>= 0.0`（0.0 速度桶不再被吞；桶值域非负，-1 哨兵仍排除）。④ **PLAN 勘误**：§2.1 档位表对齐 yaml 实值（rough [0.10..0.35]、slope [0..0.45 rad]、downsampled_scale 0.5 v4 定案）；§2.2 预算按 4096 env 实测回填（原误按 2048）；§3 终止步无特判记为已知偏差（原"含终止记 0"未实现，v10 后仅 time_out 影响≈0）；§4/§9/§11 冷启动声明改实际实现（全最易 combo + 全桶轮转，"近平地/低速偏置"未实现且 `cold_start_bias` 键从未进冻结 yaml）。同步：家族 PLAN 挂账 #15 结案 + FAMILY/FILEMAP 补 v10/v11 行。 |
| 2026-09-10 | v11.2 | 记录性勘误（外部 review 发现，用户拍板"修复一下"；不改方案实质）：① §2.2 预算按**归一化比例**重算——v11.1 行误用未归一化值（∑=1.125），高估 12.5%：.2 类 197→175、.1 类 98→87，÷16 = 12.3→10.9、6.15→**5.5 低于 n_traj_min=6**，Poisson 审查率 ~40%→~60%；跨块累积由保险升格为必需（①行原数字保留不改，以本行为准）。② §5 yaml 草图删 `flat_start_cols`（冻结 yaml 无此键、代码不读；与 cold_start_bias 同类漂移）。③ §11"旧测试回归"行措辞对齐实现：v5 断言在 `test_v5_terrain_sir.py`（闸门 [10/11]），非同文件。④ `run_offline_checks.bat` 标签分母 /10→/11（观感）。 |
