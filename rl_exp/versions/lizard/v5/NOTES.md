# v5 —— 反划脚奖励包（r_fc 符号 + r_slip + 肚皮受力罚 + EP 线性跟踪）

> **状态：解冻修改中（当前修订级 v5.2）**——v5 未训练，待改后重新冻结重打 tag。
> 修订历史：v5.0（2026-09-03 初版冻结，tag 当日撤，复现走 git `e08636b`：
> r_slip 一次范数 + 论文绝对米数脚环）→ v5.1（同日：r_slip 改论文平方 |v_f|²；
> 脚环半径 ×5 掌宽换算 [0.4, 0.8, 1.3, 1.8, 2.4]；v3 回放观察修正症状画像
> ——不趴窝、只有脚动，"肚皮免费"从主因降为防御项）→ v5.2（同日：**符号
> 修复**——r_slip/belly 权重 +0.003/+0.5 实为奖励，改 −0.003/−0.5；
> 罚项负号闸门进 check_obs_layout.py）。

- 目的/假设: v3 首跑收敛到原地划脚局部最优（**不趴窝**——肚皮离地，
  腿脚在动但身体不前进，用户 GUI 回放观察 2026-09-03；success_rate 0.47
  白嫖基线、terrain_levels 冻结 1.27、foot_clearance ≤ 5e-5）。三个主因：
  r_fc 符号反（+0.003 奖励低悬脚）、无 r_slip（接触脚滑划零成本）、exp
  跟踪核低速白嫖；肚皮罚为防御项（v3 症状不含肚皮贴地）。假设三管齐下
  后抬脚-推进成为唯一正收益路径。方案细节见本目录 PLAN.md。
- 相对 v4 的变更（obs 381 不变，任务 id `Lizard-Rough-v5`）:
  - **r_fc**: `weight 0.003 → -0.003`（符号修正，v5 yaml 副本）
  - **r_slip**: `feet_slide_ck`（接触脚切向滑速**平方** |v_f|² × c_k，
    weight 0.003，论文原式；stock 6 行本地复制避 P001 import 链）
  - **脚环半径重定标**: `ring_radii [0.08..0.48] → [0.4, 0.8, 1.3, 1.8, 2.4]`
    （×5 掌宽比例换算——论文绝对米数隐含 0.1 m ANYmal 掌，我们的 0.46×0.51 m
    掌让 3/5 圈扫在脚底下；点数不变 obs 208 不动）
  - **r_co**: body 列表缩至 `.*_hfe`+`.*_kfe`（thigh/shank）+ `undesired_contacts_ck`
    （× c_k）；base/haa/脊柱移出（base 归肚皮专项，用户拍板 2026-09-03）
  - **belly_contact_force**: `-0.5·‖F_net‖/706` 连续受力罚，恒权不乘 c_k
    （趴地永不免费）
  - **track_lin_vel_xy_lin**: `1.5·min(⟨v̂_cmd,v_yaw⟩,|v_cmd|)/max(|v_cmd|,0.1)`
    （Cheng et al. 2023 Eq.2 形式；站立 0 分/倒退负分/超速封顶）；删
    `track_lin_vel_xy_exp`；`track_ang_vel_z_exp` 保留
  - **命令**: `lin_vel_x (0,3)` 纯前进；y/wz 不变；**速度课程移除**
  - yaml: v4 全量 + names 段改 + v3.r_fc 负号 + `v5:` 段；地形/DR/网络零变化
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v5 --max_iterations 15000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v5/
- 启动前警示: 地形与 v4 逐字相同——v4 若已过预检则免；未过先看地形
  （v4\NOTES.md 启动前警示全文适用，skill `isaaclab-pretrain-check`）。
- 装配验证（2026-09-03）: 单测 `test_v5_rewards.py` 4/4（线性核 8 case /
  滑移 ×c_k / 肚皮不退火 / 接触罚 ×c_k）；`check_obs_layout.py` v5 段
  （三组契约 + 奖励集合 + r_fc 负号 + (0,3) 范围 + c_k steps 一致）；离线闸门 9/9。
  冒烟 `teacher_smoke_v5.py`（三组 90/208/83 + 前进命令 + term 活性 + 有限性）。
- 验收: 起步 sanity 后直训；反划脚 KPI（feet_slide 非零负 / success_rate
  脱离 0.47 / terrain_levels >2 上行 / foot_clearance 负值激活 / GUI 肉眼
  身体前进）见 PLAN.md。
- 结果回填: （训练后补：reward 曲线读数 / 反划脚 KPI 读数 / eval 跑分表 / 结论）
- 结论: （一句话，训练后补）
