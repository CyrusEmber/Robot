# Parkour v1 — 切片：跑 / 爬 / 跳 三专家 → DAgger 蒸馏 → RL 微调

> 状态：**初稿（未冻结）**。本文件 = 本版本方案 SSOT；路线层与决策记录见
> [../PLAN.md](../PLAN.md)；论文可复现细节见仓根 `papers/`（parkour-in-the-wild
> detail.md = 蒸馏/微调/噪声模型；anymal-parkour brief.md = 专家配方真源）。
> 开新版本流程继承 `.codemaker/rules/versioning.mdc` §A；红线：已发布 term
> 实现永不改语义。
>
> 修订：v1 初稿 2026-09-04
> 修订：v1.1 2026-09-04（用户拍板：撤回预加 belly 罚；Table 2 定性为微调表）
> 修订：v1.2 2026-09-04（**专家配方按 ANYmal Parkour Table S2 重写**，用户纠偏
> "专家训练不是你这样的"：①专家表含 Move-in-direction（approach 稠密激励）+
> Stumble + 专家版终止罚，v1.1 的"专家期 gate=none"结论撤回——两张表 gate 均为
> 字面 𝟙_{t\*<1}，approach 激励由 direction 项承担；②专家地形配比 80/20 与
> per-skill 定制入方案；③对称增广（Mittal 2024）入方案——lizard 仅左右对称；
> ④高程图训练期加扰（M1 全剥是错的）。专家 = Hoeller 2023 配方 + Rudin 2022a
> 位置任务 + Mittal 2024 对称增广，论文 2.1 原文结构。）

## 1. 目的与范围

复现论文核心范式（多专家蒸馏 + RL 微调 > 分层/单策略 RL）于 lizard：

- **3 专家**：跑（Walk 配方：stairs+slopes+rough 混合）/ 爬（box 上+下折叠）/
  跳（box gap 跑跳，probe gate）
- **1 蒸馏**：DAgger 在线蒸馏 → 单深度感知学生
- **1 微调**：RL 微调（特权 critic + critic 预训练）恢复并超越专家
- 跳跃 probe 不过 → 双专家（跑+爬）继续，管线结论不受影响

不做（本版出界）：9 技能全量、扫描地形导入、分层/VAE 对比、UE 部署。

## 2. 专家配方（ANYmal Parkour Table S2 + per-skill 定制，lizard 版）

### 位置任务（Rudin 2022a 任务描述，已实现于 parkour_mdp.PositionCommand）

- 指令 (r\*, ψ\*, t\*)；t\* = 剩余时间预算 = 重采样计时器；到达 S_L 即换点。
- S_L = 1(‖r_xy−r\*_xy‖ < 0.25 m)·1(‖ψ−ψ\*‖ < 0.5 rad)。

### 专家 Reward（Table S2 全量；与微调表 Table 2 的差异已标出）

| 项 | 表达式 | 权重 | 备注 |
|---|---|---|---|
| Position tracking | 𝟙_{t\*<1}(1−0.5‖r_xy−r\*_xy‖) | 10 | **字面门控**（v1.1 撤回 gate=none） |
| Heading tracking | 𝟙_{t\*<1}(1−0.5‖ψ−ψ\*‖) | 5 | 同上 |
| **Move in direction** | **cos⟨v_b, r\*−r⟩** | **1** | **专家表独有**：approach 稠密激励 |
| Joint velocity / Torque / 两类越限 / Base acc / Feet acc / Action rate / Feet force / Don't wait / Stand at target / Collision | 与微调表相同（见 papers detail.md） | 同 | |
| **Stumble** | **𝟙(‖F_f,xy‖ > 2‖F_f,z‖)** | **−1** | **专家表独有**：横向足力惩罚 |
| **Termination（专家版）** | **𝟙_base collision + 𝟙_{F_f>1500}** | **−200** | 微调表才是 α>135°+q̇ 越限 −2e3 |

### 地形配比与 per-skill 定制（正文 IV-B2）

| 专家 | 地形 | 定制 |
|---|---|---|
| 跑（Walk） | **60% stairs + 20% slopes + 20% random obstacles** 混合 | 无特化（泛化担当） |
| 爬（Climb up/down 折叠） | **80% box 障碍 + 20% random rough** | up：box 高度课程 + **降 base/knee 碰撞罚**（允许用膝，paper 先例）；down：**足部冲击力终止**（防跳下，F_f 阈值 lizard 定标） |
| 跳（Jump） | **80% box gap + 20% random rough** | gap 宽度课程；probe gate 前置（M1.5） |

- **爬 = box 墙不是楼梯**（paper 中楼梯属 Walk 专家）——M1 用 pyramid stairs 需
  重做为 boxes 网格地形（IsaacLab MeshRandomGridTerrainCfg），lizard 尺度 M2 预检。
- 出生/指令结构 per-skill：climb-down 生在箱顶、jump 目标在对岸箱上——
  PositionCommand 的采样策略需 per-skill 参数化（M2）。

### 专家观测

proprio（v_b, ω_b, g_b, q, q̇, prev action）+ (r\*, t\*, ψ\*) + h 高程图
（paper 2×1m，lizard 1.6×1.0m@0.1 = 187 点）。
**高程图训练期加扰**（paper：点噪声 + 全图平移 ≤7.5cm；M1 全剥是错的）——
点噪声用 stock Unoise，平移项 M2 评估（需自定义 noise model）。

### 对称增广（Mittal 2024 = arXiv:2403.04359，实现参考 leggedrobotics/rsl_rl）

- 机制：每条 transition 生成镜像变体（obs/动作按对称轴变换），**原动作的
  log-prob 复制到镜像变体**（解决镜像态 off-policy 收敛问题，ANYmal S3）。
- ANYmal 用前后+左右 4 变体；**lizard 只有左右对称**（neck 6 关节 vs rear+tail
  4 关节，前后不对称）→ 2× 增广。
- 实现：PPO minibatch 级（关节置换表 + obs 列置换：Δr_y/Δψ 取反、高程图镜像列）。

## 3. 跳跃 probe gate（M1.5，先证后用）

- **双口径**：站跳（reward=腾空高度）+ 跑跳（reward=腾空前向净空），各 ~2000
  iters 短跑，平地+沟条地形，无位置任务结构。
- **gate 判据（初值，可调）**：跑跳 eval 净空 ≥0.4m 或腾空 ≥0.2s。
- 过 → 跳专家进 M3；不过 → 双专家管线继续（用户拍板）。

## 4. 专家训练（M2–M3）

- 每专家 = 单地形配比 env cfg（快照纪律不变）+ 上节 S2 配方。
- 网络 = 单 obs 组 MLP（M1 已建）。
- 任务 id：`Lizard-Parkour-Run-v1` / `-Climb-v1` / `-Jump-v1`（+Play 对）。
- 训练顺序：Climb（M2，范式验证）→ Run → Jump（probe 过才开）。
- 验收线：各专家自有地形 90% 训练难度到达率 ≥90%（paper Fig. 4F 口径）。

## 5. 蒸馏（M4）

- 学生感知：**Q2 终裁在 M3 末**（倾向 4× RayCasterCamera 48×32 深度，2 前 2 后，
  俯角 M1 冒烟实测——趴行构型必须看得见脚下近场）。
- 学生网络 `ParkourStudentModel`：每图 CNN(3conv+pool→2FC→64) → 拼 proprio →
  2×LSTM → 拼 proprio+指令 → 3FC ELU → 26 维动作。
- DAgger trainer（新，rsl_rl 外自研训练循环）：混合 obs 组 env → 学生动作加
  零均值高斯噪声执行 → 专家同状态打标 → MSE。渐进降级：在线跑不通 → 离线 BC。
- 噪声模型：论文 5 步（clip/边缘/Perlin 空洞/盲区列/模糊）做成 obs corruption。
- 验收线：蒸馏 vs 专家掉点表成型（论文对标 −10.4%）。

## 6. RL 微调（M5）

- reward 切换到论文 **Table 2（微调表）**：去 direction/stumble、终止罚换
  α>135°+q̇ 越限 −2e3 形式——两张表的分界至此落地（专家 S2 / 微调 T2）。
- env：actor obs = proprio+depth；critic obs = +特权（obs_groups 非对称现成）。
- 稳定三件套：蒸馏 action noise 遗产 + 低初始 log_std + critic 预训练。
- 微调地形 = 全专家地形混合 + 未见保留地形。
- 验收线：微调恢复到专家 ±5%（论文 +3.1%）；未见地形非零到达率。

## 7. 风险（本版增量；路线级风险见 ../PLAN.md §5）

| # | 风险 | 缓解 |
|---|---|---|
| P1 | 跳跃物理未知（扭矩/体重 ANYmal 档但 sprawled 构型反跳跃） | M1.5 probe gate |
| P2 | 位置任务作弊面（慢蠕/肚皮代步） | paper 自带防线（Don't wait + direction + t\* 截断 + Stumble）；belly 罚补丁挂账 H5 待命 |
| P3 | DAgger 自研循环工程量 | 渐进降级（在线→离线 BC） |
| P4 | RayCasterCamera 俯角/近场覆盖设计错 | M1 冒烟含近场覆盖验证 |
| P5 | box 爬地形 lizard 定标未知（ANYmal 膝钩行为 lizard 无对应——blade 脚掌） | M2 地形预检 gate；stairs 版本作为 fallback（v3.4 已验证） |
| P6 | 对称增广的 obs 列置换表错位（26 关节 + 187 点高程镜像） | 置换表单测进 offline checks（仿 test_staged_curriculum） |
| P7 | 专家版终止罚含 base collision——lizard sprawled 爬箱必触肚皮 | paper 先例：climb up 降碰撞罚权重；M2 按技能调（挂 H8） |

## 8. 挂账

- H1：Q2 学生感知终裁（M3 末，RayCaster 深度 vs belief 复用）
- H2：UE 深度部署方案（SceneCapture vs LineTrace，部署阶段）
- H3：下楼梯独立专家分支决策（M3，下行学崩才开）
- H4：gap 难度轴真实起点（probe 标定"桥跨"上限）
- H5：belly_contact_force 补丁待命（−1.0，v5 形态）——仅凭 M2 证据启用
- H6：~~Track gate 两段式~~ **已作废**（v1.2）：两张表均为字面 𝟙_{t\*<1} 门控，
  approach 激励 = direction 项，专家/微调两表差异在 direction/stumble/终止罚
- H7：高程图全图平移扰动实现（M2 评估，自定义 noise model vs 偏差声明）
- H8：per-skill 碰撞罚权重表（paper climb up 先例，lizard sprawled 需重定）
