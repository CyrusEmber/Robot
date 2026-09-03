# v5 —— 反划脚奖励包（r_fc 符号 + r_slip + 肚皮受力罚 + EP 线性跟踪）

> **状态：解冻修改中（当前修订级 v5.1）**——2026-09-03 冻结（tag v5 当日撤）→
> 解冻修订 v5.1（r_slip 平方化 + 脚环 ×5 重定标）；症状画像随 v3 回放观察
> 同步修正，见下。

## 修订历史

| 修订 | 日期 | 内容 |
|---|---|---|
| v5.0 | 2026-09-03 | 初版冻结（tag v5 当日撤）：反划脚奖励包——r_fc 负号 / r_slip 一次范数 / 肚皮受力罚 / EP 线性跟踪 / 命令 (0,3) 无速度课程 / 脚环用论文绝对米数。复现走 git `e08636b` |
| v5.1 | 2026-09-03 | ① r_slip 改论文平方 \|v_f\|² 原式；② 脚环半径 ×5 掌宽换算 [0.4, 0.8, 1.3, 1.8, 2.4]；③ 症状画像修正（v3 回放：不趴窝、只有脚动——"肚皮免费"从主因降为防御项）（用户拍板） |
| v5.2 | 2026-09-03 | **符号修复**（写 REWARDS.md 总表时逐项核对抓出）：r_slip 与 belly_contact_force 的 yaml 权重原为 **+0.003 / +0.5**（正权重 × 正函数值 = **奖励**打滑和肚皮贴地），改 **−0.003 / −0.5**。与 v3 r_fc 符号反同 bug 类；`check_obs_layout.py` 补罚项负号闸门（三罚项权重必须 <0）机器拦截 |

## 目的/假设

v3 首跑（15555 iters，2026-09-02_11-33-11）收敛到 **原地划脚局部最优**
（用户 GUI 回放观察 2026-09-03）：**不趴窝**（肚皮离地，区别于家族旧
趴窝 run 2026-08-28），腿/脚在动，但身体不前进——foot-pad creeping。
证据链（tfevents，n=10606）：

- `Episode_Reward/foot_clearance` max 4.9e-5——防拖脚奖励从未触发；
- `Metrics/success_rate` 0.47 ≈ 站立白嫖基线（命令 x~U(-1,2) 的 |v_cmd|<0.5 区
  占 50%，exp 跟踪核站立也有残值）；
- tilt≈0 / time_out 99.9%——稳稳苟满 20s，训练"健康"地收敛到不前进。

根因（论文对照见 `papers/miki-perceptive-locomotion/detail.md` S7 与
`papers/extreme-parkour/detail.md` 奖励表）——症状是"脚动身不动"：

| # | 洞 | v3/v4 状态 | paper 对照 | 对本症状 |
|---|---|---|---|---|
| 1 | r_fc 符号反 | weight +0.003 × 正 hinge = **奖励**低悬脚 | v3 有意反向（防拖脚）但权重忘了取负 | 主因：划脚可低悬免费 |
| 2 | 无 r_slip | F3 定为"计划笔误，不新增" | paper S7: −c_k·Σ_{接触脚} v_f² | **主因：接触脚滑划零成本** |
| 3 | exp 跟踪白嫖 | +1.0·exp(−\|Δv\|²/0.25)，低速命令站立有残值 | EP 线性核 min(⟨d̂,v⟩,v_cmd)/v_cmd，站立 = 0 分 | **主因：划脚不亏钱** |
| 4 | 肚皮接触免费 | base_contact 终止删除（v3.6）、base 在 r_co 里只罚二值 | paper 有躯干触地终止 | **防御项**（v3 症状不含肚皮贴地；留作未来局部最优保险，F3-2） |

另：速度课程 stage 0 (-1,2) 保持 50% 白嫖区且被白嫖 success_rate 钉死在 0 档。

假设：符号修正 + 滑移罚 + 线性跟踪三管齐下后，抬脚-摆动-推进成为唯一
正收益路径，策略逃出原地划脚局部最优。

## 相对 v4 的变更（obs 381 不变，任务 id `Lizard-Rough-v5`）

- **r_fc 符号修正**：`weight: 0.003 → -0.003`（v5 yaml 副本；v3/v4 冻结配方保持原值）
- **r_slip 新增**（`feet_slide_ck`，抄 stock feet_slide 6 行避开 P001 import 链）：
  接触脚切向滑速**平方**罚（论文 |v_f|² 原式）× c_k，weight 0.003（paper 同值；
  注意量级——0.5 m/s 划速 ×4 脚 ≈ 0.003/步 vs 跟踪 1.5/步，首跑探针盯
  `Episode_Reward/feet_slide`，若始终在噪声底则上调 10-30×）
- **r_co 重定标**：body 列表缩到 `.*_hfe` + `.*_kfe`（thigh/shank，paper r_co 原文），
  func 换 `undesired_contacts_ck`（×c_k）；base 移到肚皮专项、haa/脊柱豁免（用户拍板）
- **肚皮受力罚新增**（`belly_contact_force`）：`-0.5·‖F_net‖/706`——连续受力比例罚，
  平贴 ≈ 满体重 → -0.5/步；**恒权不乘 c_k**（趴地在课程任何阶段都不能免费）
- **EP 线性跟踪**（`track_lin_vel_xy_lin`）：`1.5·min(⟨v̂_cmd, v_yaw⟩, |v_cmd|)/
  max(|v_cmd|, 0.1)`——站立 0 分、倒退负分、超速封顶；删 `track_lin_vel_xy_exp`，
  `track_ang_vel_z_exp` 保留（yaw 命令照旧）
- **命令与课程**：`lin_vel_x (0, 3)` 纯前进（无后退白嫖区）；`lin_vel_y (-0.5,0.5)` /
  `ang_vel_z (-1,1)` 不变；**速度课程整体移除**（stage 0 本身就是白嫖区）
- **脚环半径重定标**：`ring_radii [0.08..0.48] → [0.4, 0.8, 1.3, 1.8, 2.4]`（×5，
  2026-09-03 用户拍板）——论文半径是给 ~0.1 m ANYmal 掌定的绝对米数，我们的
  0.46×0.51 m 掌让 5 圈里 3 圈扫在脚掌底下；×5 恢复论文的掌宽相对比例
  （0.8×–5×），外圈前视约一个身位（v4 碎石 0.5 m 间距的落点规划）。
  点数不变：obs 契约 52/脚 × 4 = 208 不动
- 地形/collision stack/DR/c_k（其余项）/obs/网络：与 v4 逐字相同

## F3 偏差声明（有意偏离 paper）

1. **线性核替换 exp 核**（Miki 用 0.75·exp 对称核；EP 归一化线性核）——取 EP 形式
   断白嫖，用户拍板 2026-09-03；
2. **肚皮受力罚**：paper 无此项（他们靠躯干触地终止 + CPG 动作空间强制摆腿）；
   我们无 CPG，用连续受力罚替代终止（v3.6 已删 base_contact，用户拍板不恢复）；
3. **脚环半径 ×5 重定标**：paper 用绝对米数（0.08–0.48 m，隐含 ANYmal ~0.1 m
   掌）；v5 按掌宽相对比例换算（0.8×–5× 掌宽）。这是"对齐论文意图"而非
   "对齐论文数字"——绝对米数在我们的掌尺下是错的；
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

## 验收（沿 v3.2 口径 + 反划脚专属判据）

- 起步 sanity（~100 iters）：无 NaN、非零 reward、终止计数正常（tilt 可能升——
  学走路初期摔倒是预期）
- **反划脚判据（新增，v5 核心 KPI）**：
  1. `Episode_Reward/feet_slide` 非零且为负（滑划被罚）；
  2. `Metrics/success_rate` 脱离 0.47 白嫖基线并持续上行（>0.7 才算真推进）；
  3. `Curriculum/terrain_levels` 不再冻结（>2 并上行）；
  4. `Episode_Reward/foot_clearance` 非零（负值——r_fc 修号后真在罚低悬脚，
     说明脚开始真抬）；
  5. `Episode_Reward/belly_contact_force` 保持 ~0（防御项，正常应恒 0）；
  6. GUI 回放（`--viz kit`）肉眼确认身体前进。
- 训完以 harness eval 为准：v5 vs v4 仅 nominal 可比（奖励变更不改 DR 语义，
  但策略分布不同，robust 模式跨版本参考价值有限）。

## 启动前警示（继承 v4 三步 + v5 无地形变更）

地形与 v4 逐字相同（`TEACHER_TERRAINS_CFG_V4`）：若 v4 预检（terrain_preflight /
view_terrain GUI 目视）已做过且通过，v5 无需重做；若未做，先看地形再开训
（v4 NOTES 启动前警示 1-3 步全文适用）。
