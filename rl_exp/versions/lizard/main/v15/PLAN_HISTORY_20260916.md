# v15 PLAN —— 地形课程换 joint SIR（参数格 combo × 速度桶），base = v14

> 生成：2026-09-16。状态：**起草（提案态，未冻结、未实施）**。
> 血统：`base.json` = v14（唯一母本快照）。obs / action / 奖励 / 终止 / DR / 资产**零差异**。
> 用户拍板（2026-09-16）："v15 用 SIR 课程，不要 v14 的地形课程"——即用 v11 的
> **联合粒子 SIR**（particle = 参数格 combo × 速度桶）替掉 v5 血统的**行 SIR**
> （`SpawnWeightSIRTerrainCurriculum`, `Curriculum/terrain_levels`）。
> 前置：**本版在"老框架"（现 V 子类 + `vN/lizard_params.yaml`）下训练，项目并行迁
> 新框架（`ARCH_PLAN.md` Step 2）** —— 该并行的硬约束见下文"前置门"。

## 目的/假设（≤3 行）

v5 血统的行 SIR 只有**难度行**一个轴，且 8 类型里 `random_rough` / `flat` 根本不吃难度
（`hf_terrains.py:30` / `mesh_terrains.py:34` 忽略 difficulty）；而**类型维度在两条线上都不可调**
——joint SIR 的 env→type 在初始化由列分配锁定（`teacher_mdp.py:1150`），重生只在同类型粒子池内
抽样，游走只动参数档或速度桶（`:1307-1329`），行 SIR 同理（`:773` / `:831`）。
v15 假设：让**每个类型自己的参数 ladder**（台阶高×踏面 / 石宽×间距 / 格高×格宽 / 噪声幅 / 坡角）
+ **速度桶**成为课程轴，课程即可**在类型内部**把流量从过不去的参数档挪开
（**不跨类型**：类型份额 = 生成器 proportions，与论文 per-type trajectory share 一致）。
判读量用 `tr_mean` / `particle_entropy`；`frontier_max_v` **不作能力进度**（见"评审发现"5）。

## 相对 v14 的 diff（4 条，其余逐字段零差异）

1. **terrain_generator**：v5 的 10 行 × 20 列难度盘（`TEACHER_TERRAINS_CFG_V5`）
   → `build_param_grid_terrain_cfg(v15["terrain_grid"])`（参数格：每类型一张 levels 表，
   每 combo = 一个单值 sub-terrain，`<type>|<lvl>_<lvl>` 命名；默认比例下 58 combos，
   `num_rows=4` × `num_cols=120` 实例列）；`max_init_terrain_level = None`
2. **commands**：`UniformVelocityCommand (0,3)` → `ParticleVelocityCommand`
   （bucket `[0.5…3.0]` + `command_jitter` 0.1；`resampling_time_range=(1e9,1e9)`，
   速度由课程按 (combo, bucket) 写入 `desired_vel`）—— 字段逐项从 v14 现接线复制
3. **curriculum**：`terrain_levels: SpawnWeightSIRTerrainCurriculum` → **`None`**；
   新挂 `teacher_mdp.JOINT_SIR_TERM = "joint_sir"`：
   `JointSIRTerrainCurriculumCfg(func=JointSIRTerrainCurriculum, band, velocity_buckets,
   particles_per_type, eval_every, n_traj_min, p_transition, p_replay, maintain_mass,
   steps_per_iteration)`
4. **yaml**：`versions/lizard/v15/lizard_params.yaml` = v14 全量 + `v15` 段
   （`terrain_grid` / `velocity_buckets` / `terrain_curriculum` / `velocity_command`）

零差异声明：obs 三组（proprio 90 / extero 208 / priv 83）、26 维动作、奖励包
（含 v13 `track_lin_vel_xy_miki`、v14 `head_load_penalty`）、终止（`time_out` +
v14 `roll_over`；`tilt = None`）、DR、资产与关节接口 —— **逐字段同 v14**。

## 前置门（本版特有，不满足不许冻结/开训）

1. **并行迁移的资产保全**（用户拍板 2026-09-15 / 2026-09-16）：
   - 开训前**必须打 tag**（`versioning.mdc:41`：启动训练时无 tag → 视同冻结，立即补打）；
   - 训练进程**不得重启/续训**（重启 = 从磁盘 import 新框架代码，本次 run 的来源被劈成两段）；
   - 训练结束前**不得对 `cfg_lock` 做 `--update`**（`--update` 整体替换组合块，
     旧 golden 永久丢失，且本 run 的"可重建"行会翻红）；
   - 评测 v15 ckpt 需要本版代码 → 迁移后必须保留旧任务 id 映射、不许静默重定向
     （`ARCH_PLAN.md` Step 2.1 不变量）。
2. **首跑声明**：joint SIR 这条线在仓内**从未真训**（v11 只有 `max_iterations=6` 的冒烟，
   v12 无 run）→ 本版是该课程线的第一次真跑，v11/v12 只能作机制参考，**不能作基线**。

## 验收（预注册，同 `NOTES.md`）

1. **不劣化（固定场景）**：Locomotion-Eval-v2 `nominal` seed 123，对比 v14 同条件
   `lin_mae_mps` / `success_rate` / `fall_rate` / `terrain_completion_mean`。
   **不用 `terrain_levels` 判读**（口径已换）。注意：v15 的命令是离散步点，与
   v5–v14 的连续 `U(0,3)` 数字**不可直接同表**，对比时须标注口径变化。
2. **课程活性（口径已修正）**：`Curriculum/joint_sir/tr_mean` 与 `particle_entropy` 必须有输出，
   且 `particle_entropy` 下降 或 `tr_mean` 进带 [0.5,0.9] 才算"课程在起作用"；
   **`frontier_max_v` 只读作"当前被采样的最高速度"，不作能力进度**（冷启动即满值 3.0，
   `teacher_mdp.py:1346-1352`；评审 5）。
3. **全失败态判据（v15.3 口径）**：`tr_mean < 0.05` 且 `particle_entropy` 不降（> 0.9×初始值）
   = 课程卡在"权重全零 → 当前粒子群内均匀 → 局部游走"，**仍然不会自己下探**（v15.3 后不再是
   全域随机游走，见"无信息 / 全带外"）→ 触发人工介入（降 ladder / 降桶下限 / 修配方），不等它自愈。
4. **短局 / 翻覆交互（新增，评审 2）**：Tr 是"达标帧占比"、不罚短局、不看终止原因
   （`teacher_mdp.py:1168` + `:941-947`）⇒ 判读必须并列 `terrain_completion_mean` 与逐地形
   `fall_rate`，并在结论里写明"是否存在靠短局命中带内而持续吃流量的组合"。
   v15 继承 v14 的 roll_over 闸，这个交互是**必测项**。
5. **崩点诊断口径**（v14 教训）：`fall_rate` 在难 suite 上会饱和（v14 连 flat 都 1.0），
   故判读必须并列 `terrain_completion_mean` 与逐地形 completion，禁止只看 fall。

## 训练 / 冒烟命令

```
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v15 --max_iterations 15000 --seed 42
```

冒烟（`versioning.mdc:53` 纪律：**薄壳 + SMOKE_SPEC 一行，禁复制整份脚本**）：
`rl_exp\tools\verify\teacher_smoke_v15.py` → `main("v15")`；
`SMOKE_SPEC["v15"]` 以 v11 行为母本逐字段人审（`command="particle"`、
`train=JOINT_SIR`、`grid=(4,120)`、`log_key="Curriculum/joint_sir/frontier_max_v"`、
`param_grid=True`），差异只允许：奖励追加 `head_load_penalty`、终止追加 `roll_over`
（v14 的两件），并保留 v11 的 `_bucket_jitter_check`。

## 待实施件（代码，本 PLAN 定稿后按序做）

1. `teacher_env_cfg.py`：`LizardRoughTeacherEnvCfg_V15(LizardRoughTeacherEnvCfg_V14)` +
   `_V15_PLAY`（PLAY 须 `apply_play_wiring` + `setattr(self.curriculum, JOINT_SIR_TERM, None)`）
2. `rl_exp/tasks/__init__.py`：注册 `Lizard-Rough-v15` / `Lizard-Rough-Play-v15`
3. `agents/rsl_rl_ppo_cfg.py`：`LizardTeacherV15PPORunnerCfg`
   （`experiment_name = "lizard_rough_teacher_v15"`）
4. `teacher_smoke_runner.py`：`SMOKE_SPEC["v15"]` 行 + 薄壳 `teacher_smoke_v15.py`
5. `check_dr_parity.py` 白名单：新接线的 term 行（`curriculum.joint_sir` / `commands.base_velocity`）
6. 离线套件：`run_offline_checks.bat` 跑绿（含 v11 联合 SIR 闸、v14 摔倒闸、版本文档闸）
7. 冻结前 `cfg_lock --update --reason "v15 初稿"` + tag `<family>-v15`

## 已知风险 / 回滚线

- **冷启动流量稀**：58 combos × 6 buckets，`eval_every=10 × steps_per_iteration=24`=240 步一块
  → 课程信号可能要数小时才出现；带空兜底 = **当前粒子群内均匀重采样再局部游走**
  （`maintain_mass` 已在 2026-09-16 退役，只剩字段兼容 v11/v12 yaml）。
- **地形太小相对 episode 太长**（新记账）：cell 16 m / 出生点在中心 ⇒ 出被分配列的预算只有 8 m，
  而 20 s × 0.5–3.0 m/s = 10–60 m ⇒ 必须靠"待拍板 1"的 `W` 定义框住，否则 `Tr` 记的是别人家的地形。
- **命令分布改变**：bucket 6 档 + jitter ⇒ 与 v5–v14 的跟踪/超调数字不可同表；
  逐帧标签从 base 帧投影换成 yaw 帧 tol，同样不可与 v11/v12 的旧 `Tr` 同表。
- **回滚线**：v14（但 v14 自身尚无干净基线：崩前 850/1150 = 站着不动 `completion 0.007`、
  崩后 3150 `fall=1.0`）→ 判废时须先声明按哪一条口径回滚。

## 评审发现（2026-09-16，代码逐条复核；**待你拍板才动机制**）

五条外部评审全部**成立**（已核代码）。它们直接影响 v15 的"改什么、验收什么"，故在冻结前记账。
**纪律前提**：`JointSIRTerrainCurriculum` 现在同时被 v11/v12 的配方引用，`versioning.mdc:59`
红线 = 已发布 term 的实现永不改语义 → 任何行为修复要么给 v15 一个**新 term 变体**（v11/v12 保持
原语义），要么走显式偏差声明。**不得静默 patch 共享实现。**

| # | 结论 | 证据（file:line） | 对 v15 的影响与处置建议 |
|---|---|---|---|
| 1 | **类型流量不可调**（P1，成立） | env→type 初始化锁定 `teacher_mdp.py:1150`（行 SIR `:773`）；重生只在同类型池内抽 `:1190-1204`；游走只动参数档/速度桶 `:1307-1329`、`_neighbors` `:1288-1305`；`_env_type` 全文只写一次 | **本 PLAN 目的段与 FAMILY 行已改**：收益边界 = 类型**内部**参数 ladder，不跨类型。若确实要跨类型转移份额 → **需新增机制**（另立版本，不与 joint SIR 混谈） |
| 2 | **短局 + 末段翻覆可拿高权重**（P1，成立） | Tr = 比例 `:1168`（`_nu_sum/_step_count`）；标签 = 沿指令方向投影 > `v_pr_threshold`，**不校验桶量级、不看终止原因、无最短存活**（`:941-947`）；v11.1 已记"终止步无特判" | 3 s 里 2 s 达标 = Tr 0.67 ∈ band → 权重升。"移动几秒就摔"会被当成值得反复采样的难度区间。**验收必须并列存活/翻覆口径**（eval 侧 `fall_rate` + `completion`），并在课程判读闸里把"短局失败"单列 |
| 3 | **冷启动保护只对第一批出生有效**（P1，成立） | 粒子初始化 = combo 0 × 桶轮转 `:1137-1138`，但 `_weights` 全域均匀 `:1139`；首个 block 里未结算对保留均匀权重 `:1238` → `multinomial` 直接在全 pair 空间抽 `:1245` | 保护期仅 `eval_every × steps_per_iteration` = **240 步**（`:1153`）。"无证据 ⇒ 局部探索"未实现，实际是**全域探索**。需二选一并写进 PLAN：保持当前粒子+局部探索，还是继续全域（现行为）—— 若改，需行为测试（"无已结算样本"用例） |
| 4 | **新旧尺度混用**（P2，成立，且更广） | `weights = where(settled, measured, self._weights[ti])` `:1238`（行 SIR 同构 `:853`）：`measured` ∈ [0,1] 原始估计 vs `self._weights` 是**已归一化采样概率**（每对 ≈ 1/n_pairs，stairs 1/90≈0.011） | 不止"流量影响"：**任何已结算对都系统性压过未结算对**（0.8 vs 0.011 ≈ 72×；即便 0.05 也 ≈4.5×）→ 采样分布混入"谁更容易凑够 n_traj_min 的样本"。修法：**分开保存原始估计**（`_estimate[ti]`），只在抽样前归一化一份副本 |
| 5 | **`frontier_max_v` 冷启动即满值**（P2，成立） | `_metrics` `:1346-1352`：取当前粒子桶值的 max，无样本量/掌握条件；初始化桶轮转 → 立刻 3.0（v11 冒烟实测 `frontier_max_v 3.0` 佐证） | 只能读作"**当前被采样的最高速度**"，不替代 `terrain_levels` 作能力进度。能力前沿必须附带样本量 + 跟踪 + 存活条件（与 #2 同一处修） |

**v14（行 SIR）同源问题（评审附带指出，已核）**：`walked = ‖root_pos − env_origins‖`（净位移、无方向）
`teacher_mdp.py:805-811`；`commanded = ‖cmd_xy‖ × max_episode_length_s` = **用结束时命令 × 全长**，
不是整段积分 → 通过判据既不校验方向也不校验路径，且 `cmd=0` 的 standing env 恒判成功
（commanded=0 ⇒ `walked ≥ 0` 永真）。**这条是 v14 已有测量缺陷**，与"换 joint SIR"无关；
v15 的 Tr 没有这个白送漏洞（ν 要求 `v_pr > 0.2`），所以 v15 对"站桩策略"更不宽容（见本 PLAN 风险节）。

**处置（v15.3 起覆盖）**：1–5 的机制修复**已落到共享实现**（工作副本：`teacher_mdp.py`
信任闸 / 单尺度估计 / 局部支撑 / verified frontier / 逐类型 Tr；`curriculum_state.py` 适配器 v2）；
v15.3 重规划再改**逐帧标签 + 固定分母 + 冷启动**（见下节）。表内 `:1139` / `:1238` / `:1245`
等行号是**改动前**的历史证据，保留备查，不再对应当前代码。

副作用记账：v11/v12 的配方引用同一个 term ⇒ 它们**已不是冻结时的语义**
（`cfg_lock.json` golden 随之重生成，reason 记 2026-09-16）。共享 term 继续改需要
**显式偏差声明**或**给 v15 一个专用变体**——这条待拍板（见"待拍板"2）。

## 算法语义（v15.3 固定，不再改）

- particle = (**地形参数 combo, 速度桶**)；类型份额固定 = 生成器 proportions，**各类型独立维护粒子群**。
  **作废承诺**：不再承诺"课程自动把类型流量挪走"——类型维度在初始化即锁定
  （`teacher_mdp.py:1182`），跨类型转移不在本版范围内。
- 两级测量**照旧**，不合并：
  1. `Tr` = **单条轨迹内**的达标帧比例；
  2. `measurement(pair)` = 该 pair 的轨迹中 **`Tr ∈ [0.5, 0.9]` 的比例**（band 计数 / 轨迹数）。
  明确：**不是**"pair 平均成功率落在 50%–90%"，两者不是同一算法。

## 评分修正（本版的核心，用户拍板）

**逐帧达标改用"与奖励同帧"的水平面速度跟踪误差**（`track_lin_vel_xy_miki` 用 yaw 帧 2D 误差，
`teacher_mdp.py:584-613`）：

- `nu = 1 iff ‖vel_yaw_xy − cmd_xy‖ ≤ track_tol_mps`；`cmd` 取**实际下发**值（含桶内 jitter，
  `teacher_mdp.py:962-968`）——不用桶标称值。
- 初始 `track_tol_mps = 0.3`，**明确为待验证参数**（不得在开训前当结论写进 NOTES）。
- 作废旧判据 `v_pr > 0.2`（base 帧投影）：侧滑/反向它已排除，但"3 m/s 桶爬 0.3 m/s 也算达标"
  和"超速好帧照样计分"都来自它；同时 base 帧 → **yaw 帧**才算与奖励同一坐标系。
- `progress_frac` **不叠加**为第二道门槛（与 tol 重复约束）。

**失败必须影响分母（用户拍板）**：

- 每条轨迹的 `Tr` 分母 = **固定观察窗口 `W`**，不是实际存活步数；提前失败后，`W` 内剩余帧记
  **未达标**。现行 `tr = _nu_sum / _step_count`（`teacher_mdp.py:1207`）用实际生命长度归一化 ⇒
  "少活一会儿"反而提分，必须改。

**`W` 怎么定（实施前必须先定，第 1 步已核实）**：

- 几何：cell = `_SIZE = (16, 16)` m（`param_grid_terrain.py:34`）；**row → x、col → y**
  （`terrain_generator.py:335`）；env 出生在 cell 中心（`terrain_importer.py:353`）；一个 combo
  拥有**连续列块**（`teacher_mdp.py:1154-1161`），**最窄 1 列 = 16 m**。
- ⇒ 出生点到 col 块边界只有 **8 m**；而 episode 20 s（`v15` yaml `episode_length_s: 20.0`，
  dt 0.005 × decimation 4 = **0.02 s/步**，`max_episode_length = 1000`）配 bucket 0.5–3.0 ⇒
  **10–60 m 行程**。x 方向虽然是 4 行同 combo 重复，但 `ang_vel_z ∈ [-1,1]` 的 yaw 指令会改航向
  ⇒ **全长窗口下，标签跨 combo 污染是全场景问题，不是边角**。
- 候选（**待拍板 1**）：
  - (a) `W = min(episode, floor(8 m / bucket / dt))` → 每桶 133–800 步。代价：3.0 m/s 桶只观察
    2.7 s，加速瞬态吃掉大半，band 可能永远打不进。
  - (b) 【推荐】`W` = 全长 1000 步 **+ 逐帧"仍在被分配 combo 列块内"门**：分母固定，出块帧记
    未达标（= 没守住被分配地形）。实现 ~3 行：`terrain.terrain_types[env]` 已在重生时写好
    （`teacher_mdp.py:1254`），用当前位置反推列号比较即可。
  - (c) 现状（全长 + 不掩蔽）：噪声最大，不推荐。
- 附带杠杆（不解决 8 m 最坏值，只改分布）：缩窄 `lin_vel_y` / `ang_vel_z` 指令范围；
  加大 `num_rows` / `num_cols`。

## 冷启动（只改初始分布，不设达标闸）

- 每类型一个**显式 `anchor_combo`**（yaml 指定"预设简单端"）——**不由全零索引默认推得**；
  轴序本身不动，且"更宽 stone_width / 踏面 = 更易"**不作既成事实**，标"方向待实测"。
- **全部初始粒子放在最低速度桶**（现行是桶轮转 `teacher_mdp.py:1170` ⇒ 冷启动即铺满 0.5–3.0，改）。
- 历史池由这些初始粒子建立。
- 允许直接游走到更高速度或相邻地形，**不要求先达标**：冷启动是合理起点，不是永久限制探索。
- 作废 v15.2 的 `anchor_share` / `anchor_mastered` / `mastery_streak` / 逐级晋升 / 硬解锁。

## 每个 block 只做一次局部扩展

顺序固定（用户拍板）：

1. 用**足够样本**更新 pair 的原始测量估计；不足 → 保留旧估计，继续收集。
2. 为**当前粒子**赋权并重采样。
3. 对重采样结果执行**一次**单轴随机游走。
4. 5% 概率从历史池替换。
5. 更新历史与日志。

作废"邻居先进支撑集、抽完再走一步"的**重复扩展**（现行 `_support:1325` + `_walk:1359` 是两段）。
参数轴与速度轴**暂时保持现有均匀选轴规则**；先记录实际迁移率，不同时引入轴权重。

## 无信息 / 全带外行为（用户拍板）

| 情况 | 处理 |
|---|---|
| 样本不足 | 保留估计，继续收集，**不记失败** |
| 有非零测量权重 | 按权重重采样 |
| 当前粒子权重全零 | 在**当前粒子群内**均匀重采样，再局部游走 |
| 5% 回溯 | 从**历史完整 pair** 抽样，不改全域随机 |

⇒ 全失败仍能探索，但不会跳到全部地形×速度空间。**暂不新增**有向前沿回退、掌握判据、超时升级。

## 第 1 步核实结论（时序，已做）

- 调用序：`_reset_idx` 里 **curriculum（`manager_based_rl_env.py:369`）→ command reset（`:394`）**，
  而 `episode_length_buf` 在 **`:407`** 才清零 ⇒ 课程 hook 读到的 `_nu_sum` / `_step_count` 正是
  刚刚结束那条轨迹，且长度可读（`min_episode_frac` 判据也靠它）。
- 终止帧**已计入**（`_update_metrics` 在 step 内、reset 之前，`velocity_command.py:124-132`）；
  首次全量 reset 被 `episode_length_buf > 0` 跳过（`teacher_mdp.py:1203`）⇒ **不漏终止帧、不混重生帧**。
- 已知重叠：`W` 固定后，`min_episode_frac` / `require_survive` 与"提前失败记未达标"功能重复
  （保留 = 额外硬过滤；删除 = 少一个 knob）——**待拍板 4**。

## 验证与实施顺序（用户拍板）

1. **离线闸**（`test_joint_sir.py`）新增 5 条：高速桶低速爬行拿不到高 `Tr`；同一失败前轨迹
   **提前翻覆不能因缩短分母提分**；无样本不产生全域跳跃；非回溯更新最多移动一轴一格；
   全带外回退 / 5% 回溯 / 状态恢复符合定义。
2. **最小改动实现**：初始化（`anchor_combo` + 最低桶）、逐帧标签（yaw 帧 tol）、固定 `W` + 越界记
   未达标、重采样/游走顺序（去掉双扩展）；课程状态**显式升版**（适配器 v2 → v3），
   旧状态**不得静默套用**。
3. **短训**：PPO / 奖励 / 翻覆闸**不变**，看每类型每桶的采样份额与样本量、`Tr` 分布与带内轨迹比例、
   提前失败率、粒子扩散速度、动作极值 / KL / value loss。
4. **固定套件独立评测**：不得用"课程带内比例上涨"替代运动能力提升。
   验收核心：低速简单端能给出有效学习信号；粒子靠测量 + 游走找可学区，**既无证据不乱扩散，也不被硬门槛锁住**。

## 待拍板（实施前，4 条）

1. `W` 取 (a) 每桶几何裁窗 / **(b) 全长 + 出块掩蔽【推荐】** / (c) 现状？
2. 共享 term 改动方式：继续改 `JointSIRTerrainCurriculum`（v11/v12 语义随之变，需偏差声明 + 状态升版），
   还是给 v15 建**专用变体**？
3. 是否缩窄 `lin_vel_y` / `ang_vel_z` 指令范围（换更少越界，代价 = 命令分布再变一次）？
4. `min_episode_frac` / `require_survive` 保留还是删除？

## 修订记录

| 日期 | 版本 | 变更 + 原因 + 依据 |
|---|---|---|
| 2026-09-16 | v15 | 初稿（提案态）：joint SIR 替行 SIR，单变量=课程/地形表示/命令三项一体（用户拍板："v15 用 SIR 课程，不要 v14 的地形课程"）；并行迁移的前置门按 2026-09-15/16 讨论写入 |
| 2026-09-16 | v15.1 | **修正过度声明 + 评审记账**：目的段改为"类型**内部**参数 ladder 可调、类型份额固定"（原写"让类型成为课程轴"与代码冲突，`teacher_mdp.py:1150`/`:1307-1329` 实证）；新增"评审发现"节记录 5 条外部评审（全部成立）+ v14 行 SIR 同源测量缺陷；`frontier_max_v` 明确不作能力进度 |
| 2026-09-16 | v15.2 | **分配策略定案（当时拍板，v15.3 已作废）**：锚集 = {flat + 各类型预设简单端} × 最低桶；掌握判据三合一；`anchor_share = 0.85`；`anchor_mastered` 用近期窗口 + 连续周期 + 逐类型解锁；frontier 随 ckpt 持久化（适配器升 v3） |
| 2026-09-16 | v15.3 | **重规划（用户拍板）：保留联合 SIR，修正评分与冷启动**。作废 v15.2 的锚集/85% 分配/`anchor_mastered` 硬解锁/逐级晋升/掌握判据；固定算法语义（两级测量照旧：`Tr` 帧比例 → pair 的 band 比例，**不是** pair 平均成功率）；逐帧标签改 yaw 帧跟踪误差 `‖vel_yaw_xy − cmd_xy‖ ≤ track_tol_mps`（用实际含 jitter 的指令，初始 0.3 待验证，`progress_frac` 不叠加）；分母改**固定窗口 W**，提前失败记未达标；冷启动 = 显式 `anchor_combo` + 全部最低桶 + 保留历史池，不设达标闸；每块**只做一次**局部扩展（作废双扩展），轴选择暂仍均匀；无信息/全带外行为成表。第 1 步核实已做：时序（curriculum 早于 command reset、`episode_length_buf` 后清零）不漏帧不混重生帧；**几何发现**：cell 16 m、出生点在中心 ⇒ 出被分配列预算 8 m vs 20 s × 0.5–3.0 m/s 行程 10–60 m ⇒ `W` 必须先定（待拍板）。 |
