# lizard2 v3 首判的按命令分桶读数：低命令段无任何非足承载、滑移集中在中高带（2026-10-10）

## 适用范围

`ablation_harness/results/lizard2_flat_v5/v3/Lizard2-Flat-v3_5999_deterministic_seed123/eval.frames.pt`
的**离线分桶读数**：把首判的同一份帧按命令带分开，取误差 / 存活 / 接触 / 净空 / 承重脚滑移。
这是 `work/active/lizard2-family-landing.md` ③（"低命令段站着有分"这条假设）的**第一份输入**，
不是结论；也不改任何判据、不重跑仿真、不训练。

帧记录本身**机器本地**（`.gitignore:53` 的 `*.pt`），所以这份读数的复读命令只在本机有效。

## 验收条件

1. 分桶用**判分器自己的**函数（`baseline_metrics._band_masks` / `_alive` / `_settled` /
   `foot_slip_speed` / `foot_clearance`），不另写一套带宽或滑移口径。
2. 每条读数必须**指名它属于哪条带**并写明帧数（空带不是过，也不是结论）。
3. 分桶不改变判据：这里没有任何一条是新的 gate，判据仍以协议为准。
4. 单 ckpt / 单 seed / 单回合 ⇒ 不得据此声称策略稳定性或收敛。

## 结果

条件：1000 帧、256 envs、`step_dt` 0.02 s、256000 env-帧**全部 alive**（首回合无提前终止，
`first_episode_timeout_fraction = 1.0`）、`unclaimed_frames=0`、地面 = `declared (plane)`；
本表只是首判同一份帧的另一种读法（八闸全过不在此复述）。

| 带 | alive 帧 | settled 帧 | 相对误差（限 0.25） | 访问过的 env | 非足 fraction 均值/最大 | 头尾力最大 [N] | 承重脚滑移 p90 / p99 / max [m/s] | 净空 p05 / p50 / min [m] | 足端相对机身摆幅 中位/最大 [m] |
|---|---|---|---|---|---|---|---|---|---|
| 0–0.1 | 7495 | 6370 | 0.0848 | 15 | 0.00000 / 0.00000 | 0.0000 | 0.030 / 0.521 / 4.805 | 0.0019 / 0.0524 / 0.0000 | 0.467 / 0.555 |
| 0.1–1 | 81501 | 69276 | 0.0551 | 138 | 0.00000 / 0.00000 | 0.0000 | 1.092 / 2.385 / 9.844 | 0.0008 / 0.0357 / −0.0016 | 0.649 / 0.903 |
| 1–2 | 88998 | 75648 | 0.0146 | 144 | 0.00000 / 0.00000 | 0.0000 | 2.351 / 3.888 / 8.726 | 0.0010 / 0.0688 / −0.0055 | 0.688 / 0.860 |
| 2–3 | 78006 | 66306 | 0.0101 | 137 | 0.00000 / 0.00000 | 0.0000 | 3.235 / 5.130 / 9.622 | 0.0014 / 0.0755 / −0.0031 | 0.662 / 0.692 |

滑移列的均值（承重帧、`foot_fraction ≥ 0.05`）：`0.028 / 0.505 / 1.219 / 1.746 m/s`。
承重帧数按**脚-帧**统计：`29614 / 208848 / 172234 / 118146`。

### 三条读数

1. **低命令段没有靠非足承载取分**：零命令带 7495 个 alive 帧里，非足 `fraction` **均值与最大值都是 0.00000**，
   头尾力 0.0000 N——四足之外没有任何身体部位承重。四带皆然。⇒ ③ 的假设在**接触侧**没有被推翻，
   但也没有被证明"站着有分"：`tracking` 这一项在零命令带本来就按 `|v|` 判（0.063 m/s，限 0.15），
   策略站得稳、没趴下，判分器给过。
2. **滑移随命令单调上升**：p90 从 0.030（零带）→ 1.092 → 2.351 → 3.235 m/s，峰值上到 9.8 m/s。
   这是 ③ 里"滑移/净空奖励要不要上"的第一份量级依据——中高带承重脚在快速滑动，
   而协议现在**不判它**（`foot_slip_mps` 是 `report_only`）。
3. **净空贴地**：p05 常在 0.8–1.9 mm，`min` 有 −5.5 mm 的负值（未承重帧上脚底网格低于地面 z）——
   是穿透还是接触求解的读数误差，本记录不判（穿透容忍度归 `work/active/floor-contact-attribution.md`）。

### 这份读数不能回答的那半

③ 的原话是"低命令段**站着有分**这件事只是假设（核是双侧惩罚）"——它问的是**奖励**，不是接触。
帧记录里没有奖励项，逐带奖励分只能从 `Episode_Reward/*` 的 episode 级曲线（tensorboard）或
把奖励核在某条带上离线重跑得到；两者都不在本记录范围。**要把这半补上**需要：
逐带奖励分（跑一次带奖励项逐帧归档的 PLAY/eval），或对既有帧补算可离线复现的奖励项
（`track_lin_vel_xy_miki` 可算，`action_rate_l2` / `dof_torques_l2` 的输入不在帧里）。

## 证据引用

**这份读数的输入与读法**（不写成"复读命令"：分桶脚本是一次性的，未入库；帧记录本身也只在那台机器上）：

- 输入：`ablation_harness/results/lizard2_flat_v5/v3/Lizard2-Flat-v3_5999_deterministic_seed123/eval.frames.pt`；
- 分桶：`baseline_metrics._band_masks(command_world[:,:,0], 协议 tracking.params)`，
  settled 用 `_settled(...)`、alive 用 `_alive(terminated, timeout)`；
- 滑移：`baseline_metrics.foot_slip_speed(frames, meta)`（承重定义 = `foot_contact > 0` 且
  `foot_fraction ≥ 0.05`）；净空：`baseline_metrics.foot_clearance(frames, meta)`；
- 摆幅：足端最低点与机身位置之差在航向轴（`pos` / `yaw`）上的投影，逐帧极差。

要**重取**这份读数，先重跑一次采集（仿真），或从其它机器的同一份记录上按上面的函数复算——
本表就是这次的读数本身。若它变成需要反复取的读数，**那时**才落 `rl_exp/tools/diagnose/` 成工具
（现在一次性，不落）。

判决与条件：`acceptance/records/2026-10-10-lizard2-v3-first-eval.md`（读数不在此复述）。
帧记录的**判决**可离线复读：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -m ablation_harness.baseline_metrics ^
  ablation_harness\results\lizard2_flat_v5\v3\Lizard2-Flat-v3_5999_deterministic_seed123\eval.frames.pt ^
  --protocol ablation_harness\protocols\lizard2_flat_v5.json
```

- 判决与条件：`acceptance/records/2026-10-10-lizard2-v3-first-eval.md`（读数不在此复述）。
- 判分器函数与语义：`ablation_harness/baseline_metrics.py`（`_gate_tracking_banded_v1` / `foot_slip_speed` /
  `foot_clearance`）。
- 事项：`work/active/lizard2-family-landing.md` ③。

## 未覆盖边界

1. **单 ckpt / 单 seed / 单回合**；每带的 env 数（15–144）不同，零命令带只有 15 个 env 落进去（10 s 重采样所致）。
2. **零带的相对误差列不是判据**：judge 在零带读的是 `max |v|` 绝对值（0.063 m/s），相对误差只是同一批帧的
   统一口径读数，别拿它当判据。
3. **摆幅列不是步态定义**：它是"该带内、足端最低点相对机身在航向轴上投影"的逐帧极差，含整段移动过程，
   与"一个步态周期里的摆幅"不是同一件事。
4. **滑移是未设阈值的分布**：本记录不给容限建议值（那是 ③ 的出口决策）。
5. **净空 `min` 为负**只用来说明它是负的；成因未查（另立事项）。
