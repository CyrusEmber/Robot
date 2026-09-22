# v14 NOTES —— 只剩一条翻覆闸（侧翻/翻过去即收局），头承重降级为惩罚

> **课程读数边界（2026-09-22 补记）**：行 SIR 成功标签使用终态命令乘全长与无方向净位移，超时且终态平移命令为零时距离条件自动通过；该标签参与课程采样。`terrain_levels` 只能描述采样等级，不能单独证明地形通过能力、跟踪能力或掌握程度；独立评测不因此自动失效。历史 run 影响核认见 `work/active/row-sir-commanded-measurement-defect.md`。

- 修订历史：v14.0（2026-09-14，单变量：新增终止项；base = v13，用户拍板）；
  v14.1（2026-09-14，**判据改形**：取消"单凭鼻朝下角度"收局，改为"持续前栽 **且**
  头部贴地"；roll 仍走重力方向）；v14.2（2026-09-14，**验收量测换帧 + 侧滑改 abs**，
  与 v13.2 同口径：前向 `vel_yaw_x`、侧滑 `mean(|vel_yaw_y|)`、逐帧 MAE；闸
  `test_acceptance_metrics.py`）；v14.3（2026-09-15，**前栽不再收局，改惩罚**，用户拍板：
  "头承重只惩罚、不中止" → 终止项只剩侧翻；头承重 = 无阈值、按竖向力成比例的奖励惩罚；
  roll 判据同时修成 pitch 无关形（评审 #2）；eval 采样帧升 v2）；v14.4（2026-09-15，
  **roll 改读基座四元数、单调覆盖整圈**，用户拍板：`|sin|` 形在 110° 之后回落把"肚朝上"
  整族放过了，而"留着供起身梯度"的理由不成立 —— Miki 配方没有任何起身目标，倒了就是
  翻车，不该留）。

- 目的/假设: v10 删掉 v3 的 `tilt_terminate`（`projected_gravity_b.z > -0.6`，**总倾角**、
  **瞬时**）是因为它把合法 pitch 当摔——假阳占 episode 0.60（v8.1 @7700）/ 0.76（v6
  @8950），`success_rate` 被钉在 0.019（见 `v10\NOTES.md`）。本版装回的**不是**那种总倾角
  闸。用户诉求：roll 太歪（侧翻）要停；头杵地**只惩罚、不收局**。
  v14 假设：翻覆闸（roll 单调 + dwell）不会复现 v3 病历，同时砍掉报废 rollout；前栽留在
  rollout 里（代价由每步惩罚承担）。**v14.4 修正**：v14.0-v14.3 把"肚朝上/仰翻"留作起身数据，
  该前提不成立 —— Miki 配方没有任何起身目标，倒了就是翻车，不该留。
  **两次判据改形**：v14.1 曾把前栽收窄成"持续前栽 ∧ 头链接地"；v14.3 判定该合取式的假阳面
  （坡上持续前倾 + 头颈碰擦；10 N 阈值只有体重的 1.4%，证不了承重）不可能靠调阈值消干净，
  且"收局"本身会把前栽数据从 rollout 里拿走 —— 于是整段移到奖励侧。
- 相对 v13 的变更（v14.3 现状；obs/DR/地形/课程零变更）:
  - 终止项：`teacher_mdp.roll_over_trigger()` 纯函数（离线可测）+ `RollOverTerm`
    （`ManagerTermBase`，per-env dwell 计数器 + `reset(env_ids)` 钩子），挂
    `terminations.roll_over`；v10 的 `terminations.tilt = None` 保持不变
  - 奖励项：`teacher_mdp.head_load_penalty()`（`RewTerm`；`SceneEntityCfg` 把
    contact_forces 过滤到头链 → 竖向力 relu 求和 / 706 N；权重 -1.0，不做 c_k 缩放）
  - `LizardRoughTeacherEnvCfg_V14(V13)`: `params_version="v14"`
  - `versions/lizard/v14/lizard_params.yaml` = v13 全量 + `v14.roll_over` / `v14.head_load`
    （v14.0/v14.1 的 `fall_gate` 段作废）
  - 注册 `Lizard-Rough-v14` / `Lizard-Rough-Play-v14`（runner
    `lizard_rough_teacher_v14`）
  - 静态闸 `rl_exp/tools/verify/check_terminations_v14.py`（侧翻判据单测 + 惩罚算术 +
    接线 + v13 冻结不动 + yaml 记录），挂进 `run_offline_checks.bat`

- **判据设计（v14.4）**
  1. **翻覆 = 终止（唯一一条）**：roll 取**基座四元数**的 ZYX roll（`euler_xyz_from_quat`，
     `atan2` 形），`|roll| > roll_limit_deg`；配一条鼻子朝天的护栏 `pitch_guard_deg=80°`
     （ZYX 在 `|pitch| = 90°` 退化，那里报出的数不再是"身体的 roll"；起立/跃起的合法姿态落在
     这窗内，真摔由 harness 几何判据记）。
     为什么不用重力：重力只是一个方向矢量，只能把姿态确定到"绕世界竖直的转动"为止，而这条闸
     恰好需要那部分信息 ——
     - **与 yaw 无关**：纯朝向变化不动 roll；
     - **与 pitch 不混**：`|pg_b.y| = |sin(roll)|·cos(pitch)` 会把"既俯仰又侧滚"读小
       （30° 鼻朝下 + 80° 侧滚读成 58° → 漏收局；评审 #2）。后来的 pitch 不变形修掉了这个，
       但 `|sin|` 在 90° 见顶后回落，**不单调**；
     - **单调**：因此 110° 之后整段被放过——滚过竖直线反而"安全"。`|roll| > 90°` ⟺ 基座上轴
       掉到地平线以下（翻到底/肚朝上），"翻过去"那一半必须在闸内：v14.0-v14.3 留它是为
       "起身梯度"，v14.4 判定该前提不成立（Miki 配方无起身目标，倒了就是翻车），一并收局。
  2. **头承重 = 惩罚，不是终止**：`head_load_penalty = -1.0 · relu(ΣFz_head)/(m·g ≈ 706 N)`；
     头链由 `contact_forces` 传感器的 `find_sensors` 口径解析（不是 `robot.find_bodies`——
     两者排列不保证一致，评审 #1）。**无阈值、无姿态门控、无足部卸载条件**：无阈值 = 轻碰擦
     按比例少罚、不存在免费区；不加姿态门控 = 斜面重力系角度整段退出判据（评审 #4 的假阳面
     随之消失）；不加"足部卸载"= 尾巴/肚子同样承重（v10 实测尾尖 72.8 N = 10.3% 体重），
     卸载条件会把"尾巴拖地"误判成"头在承重"。只取世界系 **+z** 分量：侧向擦碰不承重。
  3. **dwell 0.5 s**（侧翻）：v3 无 dwell，跃起/打滑的瞬时尖峰就收局；本版要求持续。
- **仍然不进闸的**：趴地（肚朝下，roll ≈ 0）—— 这条轴看不见它，用户明确"base 接触地没关系"，
  且 base 接触自 v3.6 起就是惩罚不是终止；前栽同样不收局（v14.3），代价由每步惩罚承担。
- 默认值（yaml knob，非论文钉死）：`roll_limit_deg=70.0`、`pitch_guard_deg=80.0`、
  `dwell_s=0.5`；`head_load.weight=-1.0`、`head_load.force_scale=706.0`、
  `head_body_names=[".*neck.*"]`。
- **预注册假阳闸**：`Episode_Termination/roll_over` 必须**远低于** v3 的指纹区间
  （当年那闸吃掉了 0.60-0.76 的 episode）。**v14.4 起不再预期恒零** —— 肚朝上那一半也在
  闸内，真摔就该计数。若它爬进 0.6+ 且低速档 `success_rate` 停滞（v3 的指纹组合）→ 阈值太紧，
  先放宽/改成"足部射线地面法线"口径，**不直接判废**；判废回滚线 = v13。
- **预注册惩罚闸**：`Episode_Reward/head_load_penalty` 应停在"接近 0 但非零"（正常步态头不
  承重，落地/蹭地形偶发小值）。若它常驻大值而 tracking 仍在涨，说明策略学会了"用头当第五条
  支撑腿"（v10 的尾巴先例：尾尖承重 10.3% 体重）→ 抬 `head_load.weight`。
- **评测口径核实（评审 #3）**：harness `metrics.fall` 是几何判据（tilt > 40° 或
  clearance < 0.6× 站高，持续 0.5 s）；闸在 `|roll| > 70°` 收局，而
  `tilt = acos(cos(pitch)·cos(roll)) ≥ 70° > 40°` 恒成立（离线闸扫网格断言了这条不变式）
  ⇒ **闸响那一帧必然满足 fall 判据**。但"那一帧可见"取决于采样帧：
  Locomotion-Eval-v1 采 step 之前的帧，且终止帧会被 auto-reset 覆盖掉——dwell 恰好满 25 帧
  收局的 episode 只剩 24 帧 → fall 漏记；v2 采 step 之后的 reward 帧并把终止帧抓回来，
  这条保证才真正成立。v14.0-v14.2 里"被闸收局必然计为 fall"的表述未经检验，已作废。
- 验收（预注册）:
  1. 不劣化 = 固定场景：`Locomotion-Eval-v2` nominal seed 123（`lizard_suite_v1`）
     v14 对比 v13/v10 ckpt 同期——`lin_mae_mps`（全局+逐地形）、
     `terrain_completion_mean`、`success_rate`/`fall_rate`、`stop_overshoot_mps`。
     **不用** `Curriculum/terrain_levels`（课程状态 ≠ 能力）。**协议纪律**：基线 ckpt 若只有
     v1 行，必须在 v2 下重跑才能与 v14 同表（跨协议不比；v1→v2 差一帧）。
  2. 闸不空转也不乱响：`Episode_Termination/roll_over` 占比落在"非零但低"（TB 只有
     全局值）；地形维度的信号来自 eval.json 的逐地形 `success_rate`/`fall_rate` 与
     diagnose Phase 3 台阶通过率——若闸主要在不该响的地方响（stairs/gap 通过率比 v13 掉），
     就是阈值太紧的信号。**头承重的信号改看 `Episode_Reward/head_load_penalty`**（见上
     "预注册惩罚闸"），不再看终止占比。
  3. 主问题是否被救：v13 的欠速/不动 + 侧向漂移 + 超速三项量测（口径 = 奖励同帧：
     前向 `vel_yaw_x`、侧滑 `mean(|vel_yaw_y|)`、逐帧 `fwd_mae_mps` 报告，见
     `diag_metrics`）与 v13 对比。**注意口径**：收局会砍掉漂移尾巴，漂移/超速指标会被
     机械性改善——判读必须同时看 `Episode_Termination` 占比和 `fwd_mae_mps`，不能只看
     均值类指标。
  4. 观察项（非闸）：`feet_slide` 账本（真走起来滑动代价可能升，不作判废线）、后脚 duty、
     belly 接触。
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v14 --max_iterations 15000 --seed 42
  ```
- 固定场景评测命令（验收 1）:
  ```bat
  python ablation_harness\eval.py --task Lizard-Rough-v14 --checkpoint <model.pt> ^
      --protocol locomotion_eval_v2 --mode nominal --seed 123
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v14/
- 结果回填: （训练后补：终止占比逐地形 / 固定套件指标对 v13 / 三洞量测含 MAE / 结论）
- 结论: （一句话，训练后补）
