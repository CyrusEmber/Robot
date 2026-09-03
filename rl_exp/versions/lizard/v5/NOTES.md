# v5 —— 反趴窝奖励包（r_fc 符号 + r_slip + 肚皮受力罚 + EP 线性跟踪）

- 目的/假设: v3 首跑收敛到 foot-pad creeping 局部最优（success_rate 0.47 白嫖基线、
  terrain_levels 冻结 1.27、foot_clearance ≤ 5e-5）。四个奖励洞：r_fc 符号反
  （+0.003 奖励低悬脚）、无 r_slip、肚皮免费、exp 跟踪核低速白嫖。假设堵洞后
  摆腿成为唯一正收益路径。方案细节见本目录 PLAN.md。
- 相对 v4 的变更（obs 381 不变，任务 id `Lizard-Rough-v5`）:
  - **r_fc**: `weight 0.003 → -0.003`（符号修正，v5 yaml 副本）
  - **r_slip**: `feet_slide_ck`（接触脚切向滑速 × c_k，weight 0.003，stock 6 行
    本地复制避 P001 import 链）
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
- 验收: 起步 sanity 后直训；反趴窝 KPI（feet_slide 非零 / belly→0 /
  success_rate 脱离 0.47 / terrain_levels >2 上行 / GUI 肉眼迈腿）见 PLAN.md。
- 结果回填: （训练后补：reward 曲线读数 / 反趴窝 KPI 读数 / eval 跑分表 / 结论）
- 结论: （一句话，训练后补）
