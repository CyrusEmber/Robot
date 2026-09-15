# v14 NOTES —— 加回摔倒闸，但只掐"头杵地"和"侧翻"（per-axis + dwell）

- 修订历史：v14.0（2026-09-14，单变量：新增终止项；base = v13，用户拍板）；
  v14.1（2026-09-14，**判据改形**：取消"单凭鼻朝下角度"收局，改为"持续前栽 **且**
  头部贴地"；roll 仍走重力方向）；v14.2（2026-09-14，**验收量测换帧 + 侧滑改 abs**，
  与 v13.2 同口径：前向 `vel_yaw_x`、侧滑 `mean(|vel_yaw_y|)`、逐帧 MAE；闸
  `test_acceptance_metrics.py`）。

- 目的/假设: v10 删掉 v3 的 `tilt_terminate`（`projected_gravity_b.z > -0.6`，**总倾角**、
  **瞬时**）是因为它把合法 pitch 当摔——假阳占 episode 0.60（v8.1 @7700）/ 0.76（v6
  @8950），`success_rate` 被钉在 0.019（见 `v10\NOTES.md`）。本版装回的是**另一种闸**，
  用户诉求：平地两后脚翘起、头杵地要停；roll 太歪（侧翻）要停。
  v14 假设：只掐这两个"变形/翻覆"姿态不会复现 v3 病历，同时砍掉明显报废的 rollout。
  **v14.1 收窄**：鼻朝下角度**单独不足以**收局（v14.0 的写法会对任何前倾姿态开火），
  前栽必须与**头链接地**同时成立才收局。
- 相对 v13 的变更（**单变量**，obs/DR/地形/课程/奖励零变更）:
  - `teacher_mdp.pg_over_tilt_limit()` 纯函数（离线可测）+ `TiltPitchRollTerm`
    （`ManagerTermBase`，per-env dwell 计数器 + `reset(env_ids)` 钩子）
  - `LizardRoughTeacherEnvCfg_V14(V13)`: `params_version="v14"`，挂
    `terminations.tilt_pitch_roll`（v10 的 `terminations.tilt = None` 保持不变，
    新术语名不复用 `tilt` 以免与 v3 记录混淆）
  - `versions/lizard/v14/lizard_params.yaml` = v13 全量 + `v14.fall_gate` 段
  - 注册 `Lizard-Rough-v14` / `Lizard-Rough-Play-v14`（runner
    `lizard_rough_teacher_v14`）
  - 静态闸 `rl_exp/tools/verify/check_terminations_v14.py`（判据单测 + 接线 +
    v13 冻结不动 + yaml 记录），挂进 `run_offline_checks.bat`

- **判据设计（与 v3 的三点差异，逐条对应 v3 的失败原因）**
  1. **分轴**而非总倾角，且全部走**重力方向**（直立 = `(0,0,-1)`，与 v3 同源）：
     前栽 = `pg_b[:,0] > sin(45°)` **∧** 头链接触力 `> 10 N`；侧翻 =
     `|pg_b[:,1]| > sin(70°)`。
  2. **前栽是合取式**：鼻朝下**单独不收局**；鼻朝上（爬坡/上台阶/跃起）永不触发——
     两者正是 v3 假阳的病根。
  3. **dwell 0.5 s**：v3 无 dwell，跃起/打滑的瞬时尖峰就收局；本版要求持续。
     （采样：`contact_forces` 传感器的 `net_forces_w`，头链 body 名由 yaml
     `head_body_names = [".*neck.*"]` 定，与 diagnose 的 头颈承重 口径同源。）
- **故意不掐**：仰翻、趴地（前栽与 roll 都不成立）仍留在 rollout 里 → v10「摔倒数据
  供起身梯度」的设计不被破坏；本版只砍「后脚翘起、头杵地」与「侧翻」两类。
- 默认值（yaml knob，非论文钉死）：`pitch_down_limit_deg=45.0`、`head_contact_n=10.0`、
  `head_body_names=[".*neck.*"]`、`roll_limit_deg=70.0`、`dwell_s=0.5`。
- **预注册假阳闸**：`Episode_Termination/head_plant_roll` 必须接近 0。若它爬升且低速档
  `success_rate` 停滞（v3 的指纹组合）→ 阈值太紧，先放宽/改成"足部射线地面法线"口径，
  **不直接判废**；判废回滚线 = v13。
- 评测口径不受污染：harness `metrics.fall` 走几何判据（tilt > 40° 或 clearance < 0.6×
  站高，持续 0.5 s），比本闸（70°）**更严** → 本闸不可能把摔倒从 Locomotion-Eval-v1
  的 fall 口径里藏起来（被闸收局的 episode 仍读作 fall）。
- 验收（预注册）:
  1. 不劣化 = 固定场景：`Locomotion-Eval-v1` nominal seed 123（`lizard_suite_v1`）
     v14 对比 v13/v10 ckpt 同期——`lin_mae_mps`（全局+逐地形）、
     `terrain_completion_mean`、`success_rate`/`fall_rate`、`stop_overshoot_mps`。
     **不用** `Curriculum/terrain_levels`（课程状态 ≠ 能力）。
  2. 闸不空转也不乱响：`Episode_Termination/head_plant_roll` 占比落在"非零但低"（TB 只有
     全局值）；地形维度的信号来自 eval.json 的逐地形 `success_rate`/`fall_rate` 与
     diagnose Phase 3 台阶通过率——若闸主要在不该响的地方响（stairs/gap 通过率比 v13 掉），
     就是阈值太紧的信号。
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
      --protocol locomotion_eval_v1 --mode nominal --seed 123
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v14/
- 结果回填: （训练后补：终止占比逐地形 / 固定套件指标对 v13 / 三洞量测含 MAE / 结论）
- 结论: （一句话，训练后补）
