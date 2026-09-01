# v3 —— teacher 论文对齐版（三编码器 + 脚环 + 趴窝修复包）

- 目的/假设: v2 只完成了特权 obs 表；teacher 与 Miki et al. 2022 仍有四处结构性
  差异（单体 MLP / obs 归一化关闭 / 网格扫描 / 奖励终止面为 stock ANYmal 校准）。
  v3 按 `PLAN.md`（本目录，v3.3）全量对齐：SplitEncoderModel 三编码器（g_e/g_p/f_π
  + 三流各自 running mean/std）、每脚 52 点环形扫描、tilt 终止 + 防拖 r_fc +
  c_k 惩罚课程 + DR reset 化。
- 相对 v2 的变更（obs 308 → 三组 90/208/83 = 381，任务 id `Lizard-Rough-v3`）:
  - **obs 结构**：单向量 `policy` 组拆为 `proprio/extero/priv` 三个命名组（rsl_rl
    `obs_groups` 按名取流，F1 `check_obs_layout.py` 看守组名/顺序）；
    extero = 4×RayCaster 挂 `{lf,rf,rl,rr}_foot`（`ray_alignment="yaw"`，
    update_period=策略率，counts {6,8,10,12,16} × radii 0.08–0.48 m），
    `height_scan` 相对脚高、scan_offset=0.0、clip ±1
  - **网络**：`teacher_networks.py` `SplitEncoderModel`（MLPModel 子类，
    `class_name` 点路径注册，零 rsl_rl 改动）+ `DecayingLrPPO`（lr 0.9999/iter）；
    runner cfg `LizardTeacherV3PPORunnerCfg`（S1 超参：lr 5e-4 / γ 0.996 / 2 epochs /
    clip 0.2 / entropy 0.005 / GAE 0.95 / minibatch 8300→11 批 @4096×24）
  - **D1** tilt 终止 `pg_z > -0.6`（估计值进 yaml，消融档）
  - **D2** r_fc 防拖脚替换 feet_air_time 奖励（swing 脚 + 净空 < 0.2 m 铰链罚，
    权重 0.003；**有意反向偏差**——论文罚"抬太高"）；feet_air_time 特权 obs 保留
  - **D3** c_k 课程：c_k = 0.2^(0.98^iter)，纯函数读 `common_step_counter`，
    乘子挂 q̈/torque/ω_xy 三项（feet_slide 非本仓奖励项——计划笔误，不新增）；
    接触罚豁免 c_k 恒 -1.0；不挂 CurriculumTerm（规避挂账 #9）
  - **D4** DR reset 化 + 锚点缩放（mass/com/inertia/gains/joint 五项
    range 向恒等锚点收拢 × c_k；friction 保持 startup——`foot_friction_truth`
    读回缓存只在 startup 语义有效，F3 偏差声明）
  - yaml：v2 全量 + `v3:` 段（foot_ring / tilt / r_fc / curriculum_ck）
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v3 --max_iterations 4000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v3/
- 验收（v3.2 用户拍板）：**不设中途达标门**——起步 sanity（~100 iters 内无 NaN /
  非零 reward / 终止计数正常）后直训 4000 iters，验收一律以训完 harness eval 为准
  （v3 vs v2 仅 nominal 可比；robust/fall_rate 跨版本不可比，DR 语义不同）
- 装配验证（2026-09-01，均绿）: 离线闸门 8/8（含新增网络单测 11 项 + v3 课程/环形单测
  5 项 + obs 布局门）；`teacher_smoke_v3.py`（三组 90/208/83、extero 顺序 lf/rf/rl/rr、
  tilt+r_fc 活性、extero std>ε）；`time_foot_rings.py` 4096 env 计时
  v3 121.8 vs v2 105.8 ms/step（+15%，预算内，无需 40 点降配）
- 结果回填: （训练后补：reward 曲线读数 / eval 跑分表 / c_k 收敛观察 / 结论）
- 结论: （一句话，训练后补）
