# lizard2 v1 步态实测：承重脚在滑、摆动脚只抬 2–8 cm（2026-09-23）

## 适用范围

本条记录**一次观测与它引出的判据缺口**，不覆盖修复：`ablation_harness/protocols/lizard2_flat_v1.json` /
`lizard2_flat_v2.json` 的 `gait_swing_v1`（缺少离地高度项）与 `report_only` 里无人计算的
`foot_slip_mps`/`foot_duty`/`foot_load_fraction`/`feet_down_mean`、`rl_exp/versions/lizard2/main/v1/PLAN.md`
验收节要求的 `min_lift_m`。修复形态与奖励侧改动另立（见末节）。

## 验收条件

1. 结论必须来自**量**，不能只来自"看起来像"：逐脚 duty、承重期足端滑移、摆动期离地高度三样各给数。
2. 必须区分"真的抬了"与"力抖动"：`foot_contact == 0` 的帧要同时给几何读数。
3. 必须与**本仓既有的同一病症标准**对照（退役线自己的 `foot_clearance` 与 `r_slip` 升级记录），
   否则"0.2 m 算不算高""0.7 m/s 算不算滑"没有出处。
4. 判在**真·无限平面**上：有限地板上的长距离直行会掉出去，掉下去的行不许当读数。

## 结果

### 条件

`logs/rsl_rl/lizard2_v1/2026-09-22_19-26-50` 的 `model_13999.pt`
（sha256 `48e89b4afa24a3ed171626885e9234f5e0d61445ece03b44cd849c16d8c92f1f`），14000/14000 迭代、
4096 envs 训练。三处读数：① 判决帧记录（256 envs × 20 s，`eval.frames.pt`）；② 退役线 v2 的同类帧记录
（16 envs × 20 s）作对照；③ 一次性平面探针（每档 1 env × 4 s，`dt 0.02`，`root_z_min` 0.98–1.0 ⇒ 未坠落）。

### ① 帧记录：接触时间与"零力段"（力口径，20 s 窗口）

| | 逐脚 duty | 每脚每 20 s 的零力段数 | 零力段时长 中位 | < 0.2 s 占比 | feet-down 混合 |
|---|---|---|---|---|---|
| **lizard2 v1** | 0.33 / 0.62 / 0.46 / 0.44 | 55 / 57 / 96 / 89（2.8–4.8 Hz） | 0.14 s | **88%** | 1 脚 34% · 2 脚 38% · 3 脚 21% · 4 脚 3% |
| 退役线 v2 | 0.50 / 0.57 / 0.30 / 0.33 | 74 / 85 / 81 / 79（3.7–4.2 Hz） | 0.08 s | 69% | 2 脚 72% · 1 脚 20% |

⇒ 两代都在"高频小步"这一档，**不是 v1 独有的回归**；但下面②说明我们滑得更多。

### ② 平面探针：几何 + 承重期滑移（决定性读数）

| 档 | 逐脚 duty | **承重脚滑移** 中位 / p95 [m/s] | 摆动相离地 中位 [m] | 卸载却贴地 帧数 |
|---|---|---|---|---|
| 0.5 m/s | 0.65–0.87 | 0.21–0.63 / 0.65–1.16 | 0.009–0.041 | 0 |
| 1.5 m/s | 0.32–0.63 | **0.65–1.54 / 1.41–3.13** | 0.023–0.086 | 0–3 |
| 2.8 m/s | 0.32– | 1.13– / — | 0.02–0.06（摆幅 0.18） | — |

- **承重脚滑移 ≈ 机身速度**：1.5 m/s 时机身走 1.5 m/s，承重脚中位滑 0.65–1.54 m/s ⇒ 所谓"支撑相"
  基本是跟着地面蹭，不是踩着地面把身体蹬过去。
- **离地只有 2–8 cm**：摆动相中位离地 0.023–0.086 m，全帧中位 0.02–0.055 m。
- **卸载不等于贴地**：`foot_contact == 0` 且离地 ≤ 5 mm 的帧只有 0–3 帧 ⇒ 零力段是真抬脚，
  不是力抖动骗过判据。

### ③ 出处：本仓自己的同一病症标准

- `rl_exp/versions/lizard/REWARDS.md:18,41,45`：`feet_slide`(r_slip) = `−Σ_{接触脚}|v_f|²`，
  "**反划脚**：脚踩地就不许横移——逼'先抬再走'"；`foot_clearance`(r_fc) = "摆动脚离地不足
  **0.2 m** 罚"，两项**成对**即"步态时序的执法者"。
- `rl_exp/versions/lizard/main/v15/main_params.yaml:262-270`：v8.1 预注册升级，`r_slip` −0.003 → **−0.03
  （×10）**，触发条件写的是"`feet_slide` 停在噪声底、反解 `sum(|v_f|²) ~ 0.93/step`、低俗**划脚**
  （v3 paddle-creep，**GUI 已确认**）以 **~0.7–1 m/s** 滑接触脚而跟踪只花 1/180 的价"。
  ⇒ 我们 1.5 m/s 档的中位滑移 **0.65–1.54 m/s 就落在那条升级线的区间内或之上**，p95 达 3.1 m/s。
- `rl_exp/versions/lizard/baseline/v1/PLAN.md:125` 预注册风险第 3 条：
  "**删掉 `feet_slide`/`foot_clearance`** 可能重现拖脚/划脚；**这是首轮主动接受的取舍**。"
  lizard2 v1 逐项照旧线冻结（`lizard2/main/v1/diff.json`、7 项奖励）⇒ **该取舍已到期**。

### ④ 判据缺口（本次的根因）

- `rl_exp/versions/lizard2/main/v1/PLAN.md:164` 的验收表格明写步态判据为
  `gait_swing_v1 {min_swing_feet, min_air_time_s, **min_lift_m**, band_mps}`，且"每条摆动脚同时满足
  **离地高度**、持续离地、**落地后恢复承重**，并报告支撑期足端滑移"。
- 实际交付的两种 K 只有 `min_swing_feet` / `min_air_time_s` / `min_landing_load` / `band_mps`：
  **`min_lift_m` 没有实现**，`min_air_time_s` 定在 **0.1 s**，而实测摆动相中位 0.023–0.086 m、
  零力段 88% 短于 0.2 s ⇒ 现判据贴着观测值的下沿，等于只问"有没有动一下"。
- 冻结理由记在协议 `why_v1`："No lift term in the gait criterion. The record carries per-foot contact
  and load, not height, and a threshold on a quantity the run never measured..."——**这句话本身成立
  （记录里确实没有高度列），但结论应是"给记录加一列"，不是"删掉判据"**。同理 `report_only` 声明了
  `foot_slip_mps`/`foot_yaw_deg`/`foot_duty` 却无人计算；本记录②里手算的滑移正是 `foot_slip_mps`。
- 与判决的关系：`pass` 八条**没有一条能看见**"垫着滑"（八条读的是接触与承重，不是高度与滑速）
  ⇒ 那份 `pass` 只证明"没倒、方向对、位移对"，不证明会走路。

## 证据引用

- 帧记录：`ablation_harness/results/lizard2_flat_v2/v1/Lizard2-Flat-v1_13999_deterministic_seed123/eval.frames.pt`
  （①）；对照 `ablation_harness/results/baseline_flat_v3/v2-trained-9999/eval.frames.pt`。
- 探针（②）：`_tmp_foot_clearance.py` + `_tmp_foot_clearance.json`（一次性脚本，未入仓；
  `_tmp_*` 在 `.gitignore` 内）。它读 `robot.data.body_pos_w` / `body_lin_vel_w` 与接触传感器，
  命令经 `vel_command_b` 每步注入 —— 与 `video_matrix.py` 同一注入机制，只是不录画面。
- 视频（人眼入口）：`ablation_harness/videos/2026-09-23-lizard2-v1-13999/{0.5,1.5,3}mps_plane.mp4`
  （该目录 gitignore）。
- 支撑诊断（③的旁证，但**只能读 0.5 那一行**）：`rl_exp/tools/diagnose/out/_tmp_lizard2_gait`；
  1.5 / 2.8 两行 `foot z_min = −3.5…−4.5 m`、`tilt_max 90°`、垂直载荷只剩 0.36 体重
  ⇒ **跑出有限地板掉下去了**，其读数不是能力。
- 判决记录：`acceptance/records/2026-09-23-lizard2-v1-first-eval.md`。

## 未覆盖边界

1. `slide_loaded` 是**足部 body 原点**的世界速度，不是接触点速度；foot 为平板/球头时两者在滚动时不同。
2. 每档 4 s、每档 1 env、1 个 seed、1 颗检查点；②的表格是**量级**不是统计量。
3. ①的 duty/零力段来自**力**口径（`foot_contact > 0`），②说明它没被抖动污染，但两处口径不同源。
4. 未测：足端姿态（`foot_yaw_deg`）、支撑相足端实际接触面积、关节级归因（哪几个关节在做这件事）、
   以及 0–0.1 m/s 档的步态（本次三档最低 0.5）。
5. 未修：`min_lift_m` 未实现、`foot_slip_mps` 未计算、奖励侧 `feet_slide`/`foot_clearance` 未加回。
