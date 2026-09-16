# v5 —— 反划脚奖励包 + SIR 地形课程

> **状态：已训首跑判废（2026-09-07）**——奖励包按 spec 生效但资产长轴 Y
> 与任务 +X 前向错配，GUI 回放横行（crab-walk）；判废归因与 v6 转正见
> `../v6/NOTES.md`。修订历史：v5.0（2026-09-03 初版冻结，tag 当日撤，复现走
> git `e08636b`：
> r_slip 一次范数 + 论文绝对米数脚环）→ v5.1（同日：r_slip 改论文平方 |v_f|²；
> 脚环半径 ×5 掌宽换算 [0.4, 0.8, 1.3, 1.8, 2.4]；v3 回放观察修正症状画像
> ——不趴窝、只有脚动，"肚皮免费"从主因降为防御项）→ v5.2（同日：**符号
> 修复**——r_slip/belly 权重 +0.003/+0.5 实为奖励，改 −0.003/−0.5；
> 罚项负号闸门进 check_obs_layout.py）→ v5.3（同日：**SIR 地形课程**
> ——Lee et al. 2020 Alg. S1 离散化 + flat 启动列，机制/偏差声明见本目录
> PLAN.md §v5.3）→ v5.4（同日：冷启动进度分制，**当日用户裁决撤回**——
> 论文冷启动也是全失败，自制判据破坏归因隔离；代码保全 `3ef2aa0`，
> 挂账 #15）→ v5.5（同日：**回论文语义**——判定回二值 + 双侧软边带；
> 坡顶 0.4→0.45 rad；flat 列留）。

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
  - **SIR 地形课程（v5.3，v5.5 定案）**: stock `terrain_levels_vel` →
    `SpawnWeightSIRTerrainCurriculum`（粒子=(类型,行)×80，带 [0.5,0.9]
    双侧软边权重重采样 + 游走 0.8 + replay 0.05，每 10 迭代一块；成功 =
    time_out 存活 + 位移 ≥ 0.5×命令全程距离，冷启动全失败→均匀兜底=
    论文行为）；地形 +flat 第 8 类型（比例 0.125
    ≈ 2 列启动补偿）+ 坡顶 slope 0.4→0.45 rad（v5.5）；v3.5"出生
    level 0"废除（`max_init_terrain_level=None` 均匀初始）；V5_PLAY 掐
    课程项。参数表 `v5.terrain_curriculum`（Table S3 直译），偏差声明
    PLAN.md F3-6..10
  - yaml: v4 全量 + names 段改 + v3.r_fc 负号 + `v5:` 段（含
    terrain_curriculum）；DR/网络零变化
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v5 --max_iterations 15000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v5/
- 启动前警示: v5.3 起 terrain ≠ v4 逐字（+flat 列；v5.5 坡顶 0.45）。
  执行记录（2026-09-03，三次）：
  ① preflight 数字过——v5.5 复跑 `--version v5`：8 类型齐、flat 全零
  （预期）、坡类 p2p 1.785（0.45 rad 满档）、random_rough relief p95
  0.320 m ≈ v4 口径 0.325（seed 噪声级）；首次（v5.2，--version v5 仍指
  V4 cfg）另见 v4 批准设计：0.325 m < 掌宽 0.46，脚板必须贴合碎石；
  ② GUI 目视完成（view_terrain --task Lizard-Rough-Play-v5，用户判读）：
  **碎石堆无可见粗糙度**——与 ① 数字矛盾，**挂账 #13**（家族 PLAN §5）。
  归因假设：PLAY 非课程模式难度 U(0,1) 随机采样，所视 tile 大概率低难度
  （难度 d 振幅 ≈ 0.10+0.25d m）。**v5.3 起 #13 观察项由 SIR 课程直接
  回应**：训练流量按真实成败再分配，`Curriculum/terrain_levels` 判读
  语义反转（带内集中/爬升 = 课程在起作用，详见 PLAN.md 验收 3）；
  二次目视看 `_tmp_terrain_previews\v5_*.png`（满档渲染）。
- 装配验证（2026-09-03，v5.5 定案态）: 单测 `test_v5_terrain_sir.py`
  **9/9**（列→类型映射 / 初始 reset 跳过+origin 重指 / 成功三态判定 /
  双侧软边带 / 带内重采样 / 流量不足保权 / 游走 clamp / replay / 块评估
  节流）——v5.4 曾 10/10（进度分三态 + 冷启动梯度），撤回时随代码回退；
  `check_obs_layout.py` v5 段 SIR 断言（term 类型 + yaml 参数逐项 +
  flat 列在场 + 10×20 网格钉死 + PLAY 掐课程）；离线闸门 **10/10**；
  `terrain_preflight --version v5` 过（坡 0.45 复核）；冒烟
  `teacher_smoke_v5.py` 双环境——PLAY（三组 90/208/83 + 无 SIR）+
  TRAIN 2env（SIR 真地形实例化、origin 落格内、`Curriculum/
  terrain_levels=3.0` 有限）。
- 验收: 起步 sanity 后直训；反划脚 KPI（feet_slide 非零负 / success_rate
  脱离 0.47 / terrain_levels >2 上行 / foot_clearance 负值激活 / GUI 肉眼
  身体前进）见 PLAN.md。
- **问题所在（2026-09-07 定位，横行根因）**：资产坐标系错配，非奖励/训练问题。
  - 旧 URDF 长轴 = **Y**：neck1_yaw_joint origin `y=+1.0696`（头 +y）、
    tail_yaw_joint `y=-1.2613`（尾 -y）、四腿 hip 左右沿 **x** 分布
    （lf x=-0.32 / rf x=+0.34）。而任务全链按 IsaacLab 惯例给 **base +X** 付钱：
    `track_lin_vel_xy_lin` 是 yaw 对齐系（≈base 系）速度投影
    （`teacher_mdp.py:452-456`），命令 `lin_vel_x (0,3)` 也在 base-x。
    → policy 被付钱沿自身**右侧**横移 0–3 m/s，且按 spec 这就是最优解——
    训练曲线全程"健康"（跟踪核爬升），横行不是症状而是 spec 的忠实执行。
  - **波及面**：v1 的 0.635 同样是横行成绩（base+x = 旧资产的侧面；度量
    从不引用视觉朝向，数字本身真实有效）；v3 划脚诊断不受影响（r_fc/r_slip/
    exp 核的归因全部 frame 无关，且 v5 同轴下位移确被教会 = 反证有效）。
  - **后果**：v1/v3/v5 旧任务 id 原地复现已退役（工作树已是新资产，跑旧 id
    = 静默错配，闸门不报警）；复现走 `git checkout <tag>` 整树。旧 checkpoint
    只在旧资产上有意义。转正重训走 v6。
- 结果回填: 首跑（~2000+ iters，seed 42，2026-09-07）：**GUI 回放横行**
  （crab-walk）→ 判废。根因**不在本奖励包**：资产 URDF 长轴 = Y
  （neck +y/tail -y/腿沿 x）而任务给 base +X 付钱——policy 按最优解沿自身
  右侧横移，`track_lin_vel_xy_lin` 照常爬升（奖励包教会了位移，方向错配）。
  旁证：eval `locomotion_eval_v1/v5/summary.csv` nominal lin_mae 0.41-0.50 /
  success 0.32-0.39。资产转正重训走 v6（reward/obs 逐字不动）。横行根因
  证据链与装配验证见 `../v6/NOTES.md`。旧 run 数据留 logs/rsl_rl/
  lizard_rough_teacher_v5/ 作废案证据。
- 结论: 奖励包生效（位移真被学会），但被资产轴错配劫持方向——v5 作为
  "反划脚包有效性"的反向证明存档，重训见 v6。
