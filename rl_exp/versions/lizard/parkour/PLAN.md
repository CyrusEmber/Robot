# Parkour in the Wild 支线提案（multi-expert distillation + RL fine-tuning）

> 状态：**提案，未开工**（本文 = 支线路线意图 SSOT，允许"待/未/若"）。开工时按
> `.codemaker/rules/versioning.mdc` §A 分线条款开 `parkour/v1/`（全量式 PLAN），
> 本文降级为路线层，版本细节归 `parkour/vN/PLAN.md`。
> 来源论文：Parkour in the Wild（[arXiv:2505.11164](https://arxiv.org/abs/2505.11164)，
> 2025，RSS 2025 录用待核实）。论文笔记：仓内 `papers/parkour-in-the-wild/`
> （brief.md + detail.md，可复现粒度含 reward 全表/噪声模型/网络结构）。
> 分支规划：`paper/parkour-in-the-wild`（off main，与 v5 主线隔离）。
>
> 修订：v1 初稿 2026-09-04（讨论稿；§6 三项决策未拍板）

## 1. 论文核心（为什么值得做这条线）

9 个地形专家策略 → DAgger 蒸馏成单个 depth 驱动 foundation policy → RL 微调
（含真实 3D 扫描地形）→ 单策略超过各专家（+3.1%）且可"加地形→继续微调"不掉点。
关键结论：分层技能切换 9 技能即失效；蒸馏只是初始化，RL 微调才是完成态；
critic 预训练 + 蒸馏期 action noise 保微调稳定。

## 2. 组件映射（论文 → 仓内现状）

| 论文组件 | 仓内现状 | 动作 |
|---|---|---|
| Stage 1：N 地形专家（特权 elevation map 1×2m@0.1m + 3×6m@0.5m + lidar 1 ray/30°） | teacher v3–v5 单策略多地形 + 课程；height_scanner、脚环 RayCaster、特权 obs 齐备 | 开支线 `versions/lizard/parkour/`；专家 = 单地形 env cfg + 位置任务 + 专家特有 reward/curriculum，复用 `teacher_mdp` 特权段与 `SplitEncoderModel` 注册机制 |
| 位置任务 (r\*, ψ\*, t\*) | 仅 velocity 命令 | 新 command term（目标点+朝向+时间预算）+ 到达判定 S_L = 1(‖r_xy−r\*_xy‖<0.25m)·1(‖ψ−ψ\*‖<0.5rad) |
| Table 2 reward（2 任务项 + 12 正则项，见论文笔记 detail.md） | REWARDS.md 体系 + v5 反划脚包 | 移植论文表为支线专用 term 集；正则项从 v5 包起步（v0 趴窝教训不回滚） |
| Stage 2：DAgger 在线蒸馏（学生动作加零均值高斯噪声执行，专家同状态打标，MSE） | `student_networks.py` 为 Miki 式离线 BC——路线不同，两线并存 | 新 DAgger trainer（学生 rollout + 专家查询 + MSE）+ 混合 obs 组 env（专家组/学生组同环境）——**工程量最大件** |
| 学生感知 4×48×32 深度图（2 前 2 后） | 无相机资产；**RayCasterCamera 已核实存在于 pin 28a37ce** | 4× RayCasterCamera（warp 光线投射深度，免渲染管线、免改 lizard 资产）+ 论文 5 步噪声模型（clip 2m/0.15m、边缘噪声、Perlin 空洞、盲区 1–5 列、高斯模糊）做成 obs corruption term |
| 学生网络：每图 CNN(3conv+pool→2FC→64) → 拼 proprio → 2×LSTM → 拼 proprio+指令 → 3FC ELU MLP | `SplitEncoderModel` 的 `class_name` 点路径注册机制现成 | 新 `ParkourStudentModel`，同机制注册；消融口径：depth 输入必须 LSTM（论文结论） |
| Stage 3：RL 微调 + 特权 critic + critic 预训练（冻结 policy 先训 critic） | runner `obs_groups` actor/critic 分离现成（v3 先例）；critic 预训练无 | 微调 env（actor: proprio+depth；critic: +priv 高程/扫描特权）+ runner 扩展：critic 预热阶段 + 低初始 log_std + 保守超参 |
| 评测：1000 rollouts@90% 难度，到达率表 | Locomotion-Eval-v1 为速度跟踪口径 | harness 加 parkour 口径（到达率 S_L）+ 固定地形 suite；蒸馏 vs 微调 vs 专家对比表（对标论文 Table 4） |
| 15 个真实 3D 扫描地形（SAR 废墟） | 无扫描资产 | 切片期用 random_rough 高难度替代（偏差声明）；扫描地形导入后置 M6 |
| 蒸馏稳定技巧：action noise / 相机延迟随机化（部署免同步） | 延迟注入 DR 挂账 #6（EP 技巧同源） | 蒸馏 action noise 必做；相机延迟随机化随 M4 |

## 3. 已声明偏差（开工时进家族 OBS.md 偏差声明机制）

1. 深度图 = RayCaster 几何深度 + 论文 5 步合成噪声，非渲染深度（无材质/光照效应）。
2. 机器人 = lizard（26 关节：16 腿 + 10 spine，72kg），非 ANYmal D（12 关节）；
   地形按 lizard 几何定标（先对齐待定标）；
   脚环/水平扫描 = lidar 1 ray/30°。
4. 技能集按蜥蜴构型裁剪（Tables/crouch 对低趴构型意义存疑，待 §6-4 拍板）。
5. 主线 Miki Phase 2（belief encoder 蒸馏）与本线并行不互斥：本线学生是
   CNN+LSTM+DAgger，不动 `student_networks.py` 已有接口。

## 4. Milestones（开工后细化进 parkour/v1/PLAN.md）

| M | 内容 | 验收线 | 预算 |
|---|---|---|---|
| M0 | 分支 `paper/parkour-in-the-wild` + 支线骨架（v1 PLAN 全量式 + NOTES）+ papers 笔记入库 | 分支建好，离线闸门绿 | 0.5 天 |
| M1 | 任务基建：位置命令 term、S_L 判定、Table 2 reward 移植、parkour 地形 cfg（lizard 尺度）、obs 契约 + `check_obs_layout` 扩展 + 冒烟脚本 | 冒烟通过（obs 维度/有限性/命令重采样判读），离线闸门绿 | 1–2 天代码 |
| M2 | 专家 1 号（Climb，楼梯）：env cfg + 课程（复用 StagedCurriculumTerm/SIR 经验）+ 训练 + 评测 | 楼梯地形到达率 ≥95%（论文专家档 84.8–99.9），位置任务范式跑通 | 1 重跑 |
| M3 | 其余专家（Walk/Jump/Stepping stones，按 §6-1 拍板数） | 各自地形到达率 ≥95%，checkpoint 冻结 | N−1 重跑 |
| M4 | DAgger 蒸馏：4× RayCasterCamera obs + 噪声 corruption + `ParkourStudentModel` + 混合 obs 组 env + DAgger trainer + 蒸馏 run | 蒸馏 vs 专家掉点表成型（论文对标：平均 −10.4%）；显存/耗时 gate（脚环 +15% 先例，time_foot_rings 式实测） | 1–2 天代码 + 1 重跑 |
| M5 | RL 微调：非对称 critic env + critic 预训练 runner 扩展 + 混合地形微调 | 微调恢复到专家 ±5%（论文 +3.1%）；未见地形（random_rough 高难度）非零到达率 | 1–2 天代码 + 1 重跑 |
| M6（可选） | 反复微调加地形（新地形 3% 样本实验，对标 Down-stones 54.4→92.4）、分层/VAE 技能组合对比、扫描地形导入、扩专家数 | 论文 §3.2/§3.3 复刻 | 视范围 |

## 5. 风险表

| # | 风险 | 缓解 |
|---|---|---|
| 1 | DAgger trainer 是 rsl_rl 外新训练循环，最大工程件 | 渐进路线：先离线 BC（存专家轨迹）验证学生网络，再上在线 DAgger |
| 2 | 位置任务新范式 + lizard 趴窝前科（v0 教训） | reward 从 v5 反划脚包起步；M2 单专家先验证，趴窝信号即停 |
| 3 | 4 路 RayCasterCamera × 2048 env 显存/耗时未实测 | M4 前跑 time_foot_rings 式实测 gate；超预算降 2 路（前向双目） |
| 4 | 蒸馏 ill-posed（专家同状态异动作 + 模态错位）——论文自述精度地形掉点最大 | 预期内（论文 Beams/梅花桩掉点）；验收线按论文口径允许 −10% |
| 5 | 计算预算：切片 ≈ 5 重跑（3 专家 + 蒸馏 + 微调，2048 env × ~5k iters 档） | 垂直切片先行（§6-1）；专家可降 env 数并行训 |
| 6 | v5 主线在飞（SIR 判据裁决挂账 #15） | 分支隔离不动主线文件；teacher 已发布`teacher_mdp` 若需改动先过红线审查 |
| 7 | RayCasterCamera pattern/接口与论文 48×32 pinhole 对齐方式未验证 | M1 冒烟含单图形状/视场验证 |

## 6. 未决问题（下次讨论锚点，拍板后更新本文并开 v1）

1. **范围**：垂直切片（Walk/Climb/Jump[+Stepping stones]，约 5 重跑）先行，还是全量技能集（lizard 裁剪版 9 技能，11+ 重跑）一步到位。倾向：切片先行。
2. **学生感知路线**：RayCaster 深度图（论文忠实，本线灵魂）vs 高度扫描+belief（复用 Miki Phase 2 已有规格，`student_networks.py` 现成）。倾向：RayCaster 深度——但意味着两条学生线并行，Phase 2 挂账 #4/#5 不被本线消化。
3. **命令空间**：位置任务 (r\*,ψ\*,t\*)（论文核心，跳/爬必须点到点）vs 速度命令（复用现有，但跳/爬技能退化）。倾向：位置任务，M1 新基建。
4. **技能集裁剪**：Tables/crouch 是否保留（蜥蜴低趴构型）；Beams 无 stock 地形需自定义 pattern（M6 后置）。
5. **专家数与地形映射**：Jump = gap（box 地形）、Climb = pyramid_stairs、Climb down 是否独立专家（论文独立）。
