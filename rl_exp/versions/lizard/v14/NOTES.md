# v14 NOTES —— 加回摔倒闸（只剩侧翻），头承重降级为惩罚

- 修订历史：v14.0（2026-09-14，单变量：新增终止项；base = v13，用户拍板）；
  v14.1（2026-09-14，**判据改形**：取消"单凭鼻朝下角度"收局，改为"持续前栽 **且**
  头部贴地"；roll 仍走重力方向）；v14.2（2026-09-14，**验收量测换帧 + 侧滑改 abs**，
  与 v13.2 同口径：前向 `vel_yaw_x`、侧滑 `mean(|vel_yaw_y|)`、逐帧 MAE；闸
  `test_acceptance_metrics.py`）；v14.3（2026-09-15，**前栽不再收局，改惩罚**，用户拍板：
  "头承重只惩罚、不中止" → 终止项只剩侧翻；头承重 = 无阈值、按竖向力成比例的奖励惩罚；
  roll 判据同时修成 pitch 无关形（代码审查 #2）；eval 采样帧升 v2）。

- 目的/假设: v10 删掉 v3 的 `tilt_terminate`（`projected_gravity_b.z > -0.6`，**总倾角**、
  **瞬时**）是因为它把合法 pitch 当摔——假阳占 episode 0.60（v8.1 @7700）/ 0.76（v6
  @8950），`success_rate` 被钉在 0.019（见 `v10\NOTES.md`）。本版装回的**不是**那种总倾角
  闸。用户诉求：roll 太歪（侧翻）要停；头杵地**只惩罚、不收局**。
  v14 假设：侧翻闸（分轴 + dwell + pitch 无关口径）不会复现 v3 病历，同时砍掉明显报废的
  rollout；前栽留在 rollout 里（v10「摔倒数据供起身梯度」的设计不动），代价由每步惩罚承担。
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

- **判据设计（v14.3）**
  1. **侧翻 = 终止**：`|sin(roll)| > sin(70°)`，roll 走**重力方向**（直立 = `(0,0,-1)`，
     与 v3 同源）。实现是 pitch 无关形：`|pg_b.y| > sin(lim) · hypot(pg_b.y, pg_b.z)`
     —— 直接用 `|pg_b.y|` 会把"既俯仰又侧滚"的姿态读小（`pg_y = -sin(roll)·cos(pitch)`：
     30° 鼻朝下 + 80° 侧滚读成 60°，落进阈值内 → 漏收局；评审 #2）。
     该式等价于"roll ∈ (70°, 110°)"：>110° 后横向重力分量重新变小、与仰翻不可分，
     **故意**不加闸（仰翻/趴地留在 rollout，见下条）。
  2. **头承重 = 惩罚，不是终止**：`head_load_penalty = -1.0 · relu(ΣFz_head)/(m·g ≈ 706 N)`；
     头链由 `contact_forces` 传感器的 `find_sensors` 口径解析（不是 `robot.find_bodies`——
     两者排列不保证一致，评审 #1）。**无阈值、无姿态门控、无足部卸载条件**：无阈值 = 轻碰擦
     按比例少罚、不存在免费区；不加姿态门控 = 斜面重力系角度整段退出判据（评审 #4 的假阳面
     随之消失）；不加"足部卸载"= 尾巴/肚子同样承重（v10 实测尾尖 72.8 N = 10.3% 体重），
     卸载条件会把"尾巴拖地"误判成"头在承重"。只取世界系 **+z** 分量：侧向擦碰不承重。
  3. **dwell 0.5 s**（侧翻）：v3 无 dwell，跃起/打滑的瞬时尖峰就收局；本版要求持续。
- **故意不掐**：仰翻、趴地（roll ≈ 0）仍留在 rollout 里 → v10「摔倒数据供起身梯度」的
  设计不被破坏；前栽同样留在 rollout（v14.3），代价改由每步惩罚承担。
- 默认值（yaml knob，非论文钉死）：`roll_limit_deg=70.0`、`dwell_s=0.5`；
  `head_load.weight=-1.0`、`head_load.force_scale=706.0`、`head_body_names=[".*neck.*"]`。
- **预注册假阳闸**：`Episode_Termination/roll_over` 必须接近 0（v3 闸吃掉了 0.60-0.76 的
  episode）。若它爬升且低速档 `success_rate` 停滞（v3 的指纹组合）→ 阈值太紧，先放宽/改成
  "足部射线地面法线"口径，**不直接判废**；判废回滚线 = v13。
- **预注册惩罚闸**：`Episode_Reward/head_load_penalty` 应停在"接近 0 但非零"（正常步态头不
  承重，落地/蹭地形偶发小值）。若它常驻大值而 tracking 仍在涨，说明策略学会了"用头当第五条
  支撑腿"（v10 的尾巴先例：尾尖承重 10.3% 体重）→ 抬 `head_load.weight`。
- **评测口径核实（评审 #3）**：harness `metrics.fall` 是几何判据（tilt > 40° 或
  clearance < 0.6× 站高，持续 0.5 s）；侧翻闸在 roll > 70° 收局，而 roll > 70° 必然
  tilt > 70° > 40° ⇒ **闸响那一帧满足 fall 判据**。但"那一帧可见"取决于采样帧：
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
