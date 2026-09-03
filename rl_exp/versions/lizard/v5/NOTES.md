# v5 —— 反划脚奖励包 + SIR 地形课程

> **状态：解冻修改中（当前修订级 v5.4）**——v5 未训练，tag v5 三次撤
> （2026-09-03，v5.4 冷启动修订），改毕重打。
> 修订历史：v5.0（2026-09-03 初版冻结，tag 当日撤，复现走 git `e08636b`：
> r_slip 一次范数 + 论文绝对米数脚环）→ v5.1（同日：r_slip 改论文平方 |v_f|²；
> 脚环半径 ×5 掌宽换算 [0.4, 0.8, 1.3, 1.8, 2.4]；v3 回放观察修正症状画像
> ——不趴窝、只有脚动，"肚皮免费"从主因降为防御项）→ v5.2（同日：**符号
> 修复**——r_slip/belly 权重 +0.003/+0.5 实为奖励，改 −0.003/−0.5；
> 罚项负号闸门进 check_obs_layout.py）→ v5.3（同日：**SIR 地形课程**
> ——Lee et al. 2020 Alg. S1 离散化 + flat 启动列，机制/偏差声明见本目录
> PLAN.md §v5.3）→ v5.4（同日：**冷启动修复**——用户抓的洞"最开始肯定
> 全都失败"：终局二值改连续进度分（位移线性 × 存活占比，存活因子抵消
> 翻滚滑水），带下权重硬 0 改线性 ∝ p̂ 保冷启动难度梯度）。

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
  - **SIR 地形课程（v5.3+v5.4）**: stock `terrain_levels_vel` →
    `SpawnWeightSIRTerrainCurriculum`（粒子=(类型,行)×80，带 [0.5,0.9]
    权重重采样 + 游走 0.8 + replay 0.05，每 10 迭代一块；进度分 =
    min(位移/(0.5×命令全程距离),1)×存活占比，带下权重线性 ∝ p̂——
    v5.4 冷启动修复）；地形 +flat 第 8 类型（比例 0.125
    ≈ 2 列启动补偿）；v3.5"出生 level 0"废除（`max_init_terrain_level=
    None` 均匀初始）；V5_PLAY 掐课程项。参数表 `v5.terrain_curriculum`
    （Table S3 直译），偏差声明 PLAN.md F3-6..9
  - yaml: v4 全量 + names 段改 + v3.r_fc 负号 + `v5:` 段（含
    terrain_curriculum）；DR/网络零变化
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v5 --max_iterations 15000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v5/
- 启动前警示: v5.3 起 terrain ≠ v4 逐字（+flat 列）。执行记录
  （2026-09-03，两次）：
  ① preflight 数字过——v5.3 复跑 `--version v5`：8 类型齐、flat 全零
  （预期）、random_rough relief p95 0.330 m ≈ v4 口径 0.325（seed 噪声级）；
  首次（v5.2，--version v5 仍指 V4 cfg）另见 v4 批准设计：0.325 m < 掌宽
  0.46，脚板必须贴合碎石；
  ② GUI 目视完成（view_terrain --task Lizard-Rough-Play-v5，用户判读）：
  **碎石堆无可见粗糙度**——与 ① 数字矛盾，**挂账 #13**（家族 PLAN §7）。
  归因假设：PLAY 非课程模式难度 U(0,1) 随机采样，所视 tile 大概率低难度
  （难度 d 振幅 ≈ 0.10+0.25d m）。**v5.3 起 #13 观察项由 SIR 课程直接
  回应**：训练流量按真实成败再分配，`Curriculum/terrain_levels` 判读
  语义反转（带内集中/爬升 = 课程在起作用，详见 PLAN.md 验收 3）；
  二次目视看 `_tmp_terrain_previews\v5_*.png`（满档渲染）。
- 装配验证（2026-09-03，v5.3→v5.4）: 单测 `test_v5_terrain_sir.py` **10/10**
  （列→类型映射 / 初始 reset 跳过+origin 重指 / **进度分三态**（满额×存活
  /翻滚滑水×0.2/站立 0）/ **双段带曲线**（带下线性+带上软边）/ 带内重采样 /
  流量不足保权 / 游走 clamp / replay / **冷启动梯度**（全失败期易行 5:1
  压难行——用户洞的回归测试）/ 块评估节流）；
  `check_obs_layout.py` v5 段新增 SIR 断言（term 类型 + yaml 参数逐项 +
  flat 列在场 + 10×20 网格钉死 + PLAY 掐课程）；离线闸门 **10/10**；
  `terrain_preflight --version v5` 过；冒烟 `teacher_smoke_v5.py` 扩双环境
  ——PLAY（三组 90/208/83 + 无 SIR）+ TRAIN 2env（SIR 真地形实例化、
  origin 落格内、`Curriculum/terrain_levels=3.0` 有限）。
- 验收: 起步 sanity 后直训；反划脚 KPI（feet_slide 非零负 / success_rate
  脱离 0.47 / terrain_levels >2 上行 / foot_clearance 负值激活 / GUI 肉眼
  身体前进）见 PLAN.md。
- 结果回填: （训练后补：reward 曲线读数 / 反划脚 KPI 读数 / eval 跑分表 / 结论）
- 结论: （一句话，训练后补）
