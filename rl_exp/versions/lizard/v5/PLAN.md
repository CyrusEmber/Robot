# v5 —— 反趴窝奖励包（r_fc 符号 + r_slip + 肚皮受力罚 + EP 线性跟踪）

## 目的/假设

v3 首跑（15555 iters，2026-09-02_11-33-11）收敛到 **foot-pad creeping 局部最优**：
success_rate 钉在站桩白嫖基线 0.47、terrain_levels 冻结 1.27、foot_clearance 奖励
全程 ≤ 5e-5（脚从未摆动）。证据链（tfevents，n=10606）：

- `Episode_Reward/foot_clearance` max 4.9e-5——防拖脚奖励从未触发；
- `Metrics/success_rate` 0.47 ≈ 站立白嫖基线（命令 x~U(-1,2) 的 |v_cmd|<0.5 区
  占 50%，exp 跟踪核站立也有残值）；
- tilt≈0 / time_out 99.9%——趴着 20s 苟满，训练"健康"地收敛到不动。

根因 = 四洞齐开（论文对照见 `papers/miki-perceptive-locomotion/detail.md` S7 与
`papers/extreme-parkour/detail.md` 奖励表）：

| # | 洞 | v3/v4 状态 | paper 对照 |
|---|---|---|---|
| 1 | r_fc 符号反 | weight +0.003 × 正 hinge = **奖励**低悬脚 | v3 有意反向（防拖脚）但权重忘了取负 |
| 2 | 无 r_slip | F3 定为"计划笔误，不新增" | paper S7: −c_k·Σ_{接触脚} v_f²，唯一直接罚爬行 |
| 3 | 肚皮免费 | base_contact 终止删除（v3.6）、base 在 r_co 里只罚二值 | paper 有躯干触地终止；EP 碰撞罚 −10 |
| 4 | exp 跟踪白嫖 | +1.0·exp(−\|Δv\|²/0.25)，低速命令站立有残值 | EP 线性核 min(⟨d̂,v⟩,v_cmd)/v_cmd，站立 = 0 分 |

另：速度课程 stage 0 (-1,2) 保持 50% 白嫖区且被白嫖 success_rate 钉死在 0 档。

假设：堵住四个洞后，摆腿/抬脚成为唯一正收益路径，策略逃出趴窝局部最优。

## 相对 v4 的变更（obs 381 不变，任务 id `Lizard-Rough-v5`）

- **r_fc 符号修正**：`weight: 0.003 → -0.003`（v5 yaml 副本；v3/v4 冻结配方保持原值）
- **r_slip 新增**（`feet_slide_ck`，抄 stock feet_slide 6 行避开 P001 import 链）：
  接触脚切向滑速罚 × c_k，weight 0.003（paper 同值）
- **r_co 重定标**：body 列表缩到 `.*_hfe` + `.*_kfe`（thigh/shank，paper r_co 原文），
  func 换 `undesired_contacts_ck`（×c_k）；base 移到肚皮专项、haa/脊柱豁免（用户拍板）
- **肚皮受力罚新增**（`belly_contact_force`）：`-0.5·‖F_net‖/706`——连续受力比例罚，
  平贴 ≈ 满体重 → -0.5/步；**恒权不乘 c_k**（趴地在课程任何阶段都不能免费）
- **EP 线性跟踪**（`track_lin_vel_xy_lin`）：`1.5·min(⟨v̂_cmd, v_yaw⟩, |v_cmd|)/
  max(|v_cmd|, 0.1)`——站立 0 分、倒退负分、超速封顶；删 `track_lin_vel_xy_exp`，
  `track_ang_vel_z_exp` 保留（yaw 命令照旧）
- **命令与课程**：`lin_vel_x (0, 3)` 纯前进（无后退白嫖区）；`lin_vel_y (-0.5,0.5)` /
  `ang_vel_z (-1,1)` 不变；**速度课程整体移除**（stage 0 本身就是白嫖区）
- 地形/collision stack/DR/c_k（其余项）/obs/网络：与 v4 逐字相同

## F3 偏差声明（有意偏离 paper）

1. **线性核替换 exp 核**（Miki 用 0.75·exp 对称核；EP 归一化线性核）——取 EP 形式
   断白嫖，用户拍板 2026-09-03；
2. **肚皮受力罚**：paper 无此项（他们靠躯干触地终止 + CPG 动作空间强制摆腿）；
   我们无 CPG，用连续受力罚替代终止（v3.6 已删 base_contact，用户拍板不恢复）；
3. **feet_slide 用一次范数**（stock）而非 paper 的 v_f²——小滑速更狠、大滑速更宽，
   防爬行方向上更保守；
4. **命令范围 (0,3) vs paper 速度范围**：Miki 未给训练范围；EP [0,1.5]。3 m/s 上段
   对 72kg 蜥蜴可能不可达——线性核不会炸（超速封顶），代价是高段样本稀释；
5. HAA/脊柱接触豁免（r_co 只罚 hfe/kfe）——paper 只罚 thigh/shank 的直译，
   脖子尾巴拖地暂不罚（观察首跑再定）。

## 训练命令

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v5 --max_iterations 15000 --seed 42
```

- log 目录: logs/rsl_rl/lizard_rough_teacher_v5/
- v3 实测 461 iters/h @ 4096 env → 15000 iters ≈ 33h

## 验收（沿 v3.2 口径 + 反趴窝专属判据）

- 起步 sanity（~100 iters）：无 NaN、非零 reward、终止计数正常（tilt 可能升——
  学走路初期摔倒是预期）
- **反趴窝判据（新增，v5 核心 KPI）**：
  1. `Episode_Reward/feet_slide` 非零且为负（爬行被罚）；
  2. `Episode_Reward/belly_contact_force` 趋 0（肚皮离地）；
  3. `Metrics/success_rate` 脱离 0.47 白嫖基线并持续上行（>0.7 才算真动起来）；
  4. `Curriculum/terrain_levels` 不再冻结（>2 并上行）；
  5. GUI 回放（`--viz kit`）肉眼确认迈腿。
- 训完以 harness eval 为准：v5 vs v4 仅 nominal 可比（奖励变更不改 DR 语义，
  但策略分布不同，robust 模式跨版本参考价值有限）。

## 启动前警示（继承 v4 三步 + v5 无地形变更）

地形与 v4 逐字相同（`TEACHER_TERRAINS_CFG_V4`）：若 v4 预检（terrain_preflight /
view_terrain GUI 目视）已做过且通过，v5 无需重做；若未做，先看地形再开训
（v4 NOTES 启动前警示 1-3 步全文适用）。
