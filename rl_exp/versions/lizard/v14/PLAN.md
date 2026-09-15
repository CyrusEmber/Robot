# v14 PLAN —— 加回摔倒闸（per-axis pitch/roll + dwell），单变量

> 生成：2026-09-14。状态：**实施完成待训**（单变量，base = v13；验收与假阳闸预注册于
> `NOTES.md`）。

## 目的/假设（≤3 行）

v13 的 Miki 对称核闭掉账本三盲区，但**不阻止**"头杵地/侧翻"这类报废姿态继续占 rollout。
v3 的旧闸（总倾角 > 53°、瞬时）因假阳（0.60/0.76 的 episode）被 v10 删除；v14 假设：
只掐"**前栽**（鼻朝下 >45° **且** 头链接触力 >10 N，两者缺一不收局）+ **|roll| > 70°**"、
且各需持续 0.5 s（判据全走重力方向），则既不复发 v3 病历，又能砍掉真报废姿态
（仰翻/趴地仍保留 → v10 起身梯度不破）。

## 相对 v13 的 diff（单变量，obs/DR/地形/课程/奖励零变更）

1. `teacher_mdp.py`：`pg_over_tilt_limit()` 纯函数 + `TiltPitchRollTerm`（stateful dwell
   + `reset(env_ids)`）
2. `teacher_env_cfg.py`：`LizardRoughTeacherEnvCfg_V14(V13)` + `_V14_PLAY`，挂
   `terminations.head_plant_roll`（v10 的 `terminations.tilt = None` 原样保留）
3. `versions/lizard/v14/lizard_params.yaml` = v13 全量 + `v14.fall_gate`
   （`pitch_down_limit_deg=45` / `head_contact_n=10` / `head_body_names=[".*neck.*"]` /
   `roll_limit_deg=70` / `dwell_s=0.5`）、`base.json`（base=v13）
4. 注册 `Lizard-Rough-v14` / `Lizard-Rough-Play-v14`（runner `lizard_rough_teacher_v14`）
5. 静态闸 `rl_exp/tools/verify/check_terminations_v14.py`（判据单测 + 接线 + v13 冻结不动），
   挂进 `run_offline_checks.bat`
6. `check_dr_parity` 白名单加 `self.terminations.head_plant_roll = DoneTerm(`（teacher-only）

## 验收（同 NOTES 预注册）

1. 不劣化（固定场景）：Locomotion-Eval-v1 nominal seed 123 对比 v13/v10 同期
   `lin_mae_mps`（全局+逐地形）/ `terrain_completion_mean` / `success_rate` / `fall_rate` /
   `stop_overshoot_mps`；不用 `terrain_levels`
2. 闸行为：`Episode_Termination/head_plant_roll` 非零但低（TB 全局）；地形信号看 eval.json
   逐地形 `success_rate`/`fall_rate` + diagnose Phase 3 通过率（stairs/gap 掉 = 阈值太紧）
3. 主问题：v13 的三洞量测对比 v13（口径 = 奖励同帧：前向 `vel_yaw_x`、侧滑
   `mean(|vel_yaw_y|)`、逐帧 `fwd_mae_mps` 报告）；**口径**：收局会机械性
   改善漂移/超速均值 → 必须与终止占比、MAE 同看
4. 观察项（非闸）：`feet_slide` / 后脚 duty / belly 接触

## 训练

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v14 --max_iterations 15000 --seed 42
```

log：`logs/rsl_rl/lizard_rough_teacher_v14/`

## 修订记录

| 日期 | 版本 | 变更 + 原因 + 依据 |
|---|---|---|
| 2026-09-14 | v14.0 | 初稿（用户要求：平地两后脚翘起头着地、roll 太歪即终止）。设计对照 v3 病历逐条去风险：分轴（非总倾角）+ pitch 单向（鼻朝上不触发）+ dwell 0.5 s；仰翻/趴地不掐以保 v10 起身梯度。假阳闸预注册（终止占比近零 + 低速档 success_rate 不得停滞），判废回滚线 = v13 |
| 2026-09-14 | v14.1 | 判据改形（用户拍板）：取消"单凭鼻朝下角度"收局，改为**前栽 ∧ 头贴地**（鼻朝下 >45° 且头链接触力 >10 N；头链 = `.*neck.*`，读 stock `contact_forces`）；roll 保持重力方向 `|pg_b.y| > sin(70°)`。理由：角度单独不足以区分"真报废"与"任何前倾姿态"，头着地才是那个姿态的实测证据。闸测试同步重写 + 变异测试（去掉头接触合取项 → 断言即红） |
| 2026-09-14 | v14.2 | 验收量测换帧 + 侧滑 abs（与 v13.2 同口径，用户 review）：前向 `vel_yaw_x`（奖励同帧）、侧滑 `mean(|vel_yaw_y|)`、逐帧 MAE 报告；新增纯函数模块 `diag_metrics.py` + 闸 `test_acceptance_metrics.py`。判读纪律：终止会机械性改善漂移/超速均值，须与终止占比、MAE 同看 |
