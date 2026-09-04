# Lizard 26 关节四足机器人训练计划

> SSOT: rl_exp git 仓（例 `E:\Robot\rl_exp\`）。本目录 = lizard 家族之家：
> 家族事实 `FAMILY.md`、滚动计划（本文件）、obs 契约 `OBS.md`、奖励语义
> `REWARDS.md`、开发态参数 `lizard_params.yaml`（改动不追溯，与冻结副本同目录
> 共存——改前认准目录层级）、几何 `lizard.urdf`、管线脚本 `blender\`；冻结配方
> 在 `vN\`，版本级方案归各自目录。代码不复制进 IsaacLab 根，部署见仓根 README。
>
> **本文件只收意图（路线 / 备选路径 / 挂账）**：已成立事实 → FAMILY.md，
> 版本方案 → vN\PLAN.md，obs 契约 → OBS.md，奖励语义 → REWARDS.md，
> 命令与摆位 → 仓根 README。时态判据见 `.codemaker/rules/versioning.mdc`
> 分层原则（FAMILY=已成立事实，PLAN=靠行动兑现的意图）。
>
> 更新: 2026-09-03（重构为纯意图文档：现状快照/Phase 1 详情/命令速查移除
> ——事实归 FAMILY，obs 契约归 OBS.md（v1 266 布局迁入），方案细节归 vN\PLAN，
> 命令归 README；备选奖励修复表保留为 §3。上一版 2026-09-02（v4 提案：碎石地
> 重定标，详见 v4\PLAN）；再上一版 2026-09-01（v3 提案；包名 lizard_exp→rl_exp；
> versions 家族分层）。方案细节以各 vN\PLAN.md 为 SSOT，本文件只管路线/挂账）

## 1. 目标

26 关节蜥蜴四足（16 腿关节 HAA/HFE/KFE/FOOT + 10 脊柱关节）在粗糙地形上做速度跟踪运动，
最终以盲部署形态（零特权信息）跑进 UE。

参考论文/代码：

| 来源 | 用途 |
|---|---|
| Miki et al. 2022, *Learning robust perceptive locomotion for quadrupedal robots in the wild* (arXiv:2201.08117) | 总路线：teacher(特权 RL) → student(蒸馏)，两阶段 |
| awesomericky/quadruped-robot-belief-encoder | student 网络参考：GRU belief encoder + 门控融合 + belief decoder |
| chengxuxin/extreme-parkour (ICRA 2024) | 全流程代码参考（Isaac Gym 版），延迟注入等工程技巧 |

## 2. 总路线（Miki 两阶段 + EP 工程）

```
Phase 1  Teacher: 特权 actor PPO（当前 = v5 解冻修改中；版本态速览见 FAMILY 当前状态）
Phase 2  Student: 蒸馏（belief encoder + 加噪扫描 + 重建损失）
Phase 3  部署: student → ONNX → UE
```

当前训练入口：`--task Lizard-Rough-v5`（回放 `Lizard-Rough-Play-v5`）；
验证链与摆位见仓根 README。

**并行支线**：parkour 支线（Parkour in the Wild 范式：跑/爬/跳多专家 → DAgger
蒸馏 → RL 微调）已开 v1（2026-09-04，分支 `paper/parkour-in-the-wild`），路线与
决策见 [parkour/PLAN.md](parkour/PLAN.md) + [parkour/v1/PLAN.md](parkour/v1/PLAN.md)；
与主线 Phase 2（belief 蒸馏）互不阻塞，感知路线终裁挂 H1。

决策记录:

- **参数版本化**（2026-08-28，用户拍板）: `rl_exp/versions/lizard/vN/` 冻结参数副本 +
  NOTES.md + tb_scalars.csv；跑 vN 只读 vN 的副本（teacher v0 已钉死 `TEACHER_PARAMS_VERSION="v0"`）。
  家族总文档 `FAMILY.md`（任务注册表/版本历史/开新版本流程）。配方变更才升版，换 seed 不升。
- **teacher actor 吃特权**（Miki 式 A 方案，用户拍板），蒸馏成本（belief encoder 全套）接受。
  曾讨论 EP 式非对称 critic（特权只进 critic），因 student 保留高度扫描、A 增益被稀释而推荐 B，
  最终用户选 A 换上限。
- **teacher 独立快照环境**（用户拍板）：不经过任何 lizard 中
  `LocomotionVelocityRoughEnvCfg`。理由: teacher 语义 = 论文配方冻结快照，Phase 2 蒸馏依赖其
  稳定不变；与 lizard 家族（活实验场）共享基类会互相干扰（当日两起事故实证）。
  参数仍读 `lizard_params.yaml`（数值 SSOT 保留，代码快照冻结）。
- **奖励基线**（做法 2，用户拍板）: teacher 与论文一致，无激励补丁，做"特权救不救趴窝"对照。

## 3. 备选升级路径（反趴窝奖励修复，已回滚，v3 失效时启用）

第一次训练（15000 iters，v0 时代）失败复盘——症状: 趴地不动，feet_air_time≈0，
success_rate 0.31，课程全卡 stage 0，地形等级 0.1/9。

根因（激励逃生舱）:

1. 趴下时躯干圆柱/大腿着地，`base_contact` 终止只查 base_link → 悬空不终止
2. `flat_orientation_l2` 权重 0 → 趴下不罚
3. 接触惩罚 -1.0 太轻、抬脚奖励 0.125 太低

**决策（做法 2）**: 奖励修复方案（躯干终止/姿态惩罚/接触×5/抬脚×4/降难度）整体**回滚挂账**，
所有环境保持 变量隔离——先验证"特权 obs 能否单独救趴窝"（对照实验），
再决定是否动激励。修复方案细节保留在下表，随时可重新应用：

**2026-09-01 重定向**：v1 对照实验已出结论（特权救活趴窝但 fall 上升，v1 NOTES），
反趴窝杠杆已按论文口径在 **v3** 落地（`versions/lizard/v3/PLAN.md` D1–D4：tilt 终止 +
防拖 r_fc 替换 feet_air_time + c_k 惩罚课程 + DR reset 化；接触终止按 D0-6 拍板明确
不做）。下表候选仅作 v3 失效时的备选升级路径（对应 v3 PLAN §9 风险表"belly-down
趴窝敞口"行：① 接触惩罚 -1→-5 即本表第 3 行）；挂账 #7 的"奖励修复重应用"以此为准。

| 项 | 候选修改（已回滚） |
|---|---|
| 躯干终止 | 新增 `torso_contact`（rear/tail/neck 接触即终局） |
| 姿态惩罚 | `flat_orientation_l2` 0 → -2.0（rough 爬坡冲突，若启用应挪 flat-only） |
| 接触惩罚 | -1.0 → -5.0 |
| 抬脚奖励 | 0.125 → 0.5 |
| 开局难度 | `max_init_terrain_level` 5→0，腿质量 DR ±30%→±15% |

## 4. Phase 2 · Student 蒸馏规格（后置，Phase 1 验收后细化）

- 网络: 移植 `RecurrentAttentionPolicy`（GRU belief encoder + 门控融合 + belief decoder 重建外感）
- 输入: 本体感受（瞬时）+ 加噪高度扫描（移植参考仓库 3 噪声模型: 逐点噪声/遮挡/漂移）
- 损失: `L_bc(动作) + L_re(扫描重建)`，噪声课程 c_sk 渐进
- 数据: teacher rollout 存干净扫描，离线加噪（同一批数据可随课程重新加噪）
- 部署: student 零特权、零干净扫描依赖

## 5. 挂账清单

| # | 事项 | 优先级 |
|---|---|---|
| 1 | ✅ teacher env 独立快照重写（去掉 lizard 中间层继承） | 完成 2026-08-28 |
| 2 | ✅ teacher_smoke 解包 bug（gym 5 元组）+ 冒烟通过 | 完成 2026-08-28 |
| 3 | ✅ teacher v1 训练 14000 iters + 验收：对照判出**特权救活趴窝**（零动作 success 0.254 → v1 0.635）；遗留 fall 随迭代上升（0.03→0.33）、gap_40cm 不跳 → `versions\lizard\v1\NOTES.md` | 完成 2026-09-01 |
| 4 | 摩擦/外力真值 obs term（event 缓存） | 🟡 Phase 2 前 |
| 5 | 三噪声模型 C++→Python 移植 | 🟡 Phase 2 |
| 6 | 延迟注入 DR（EP 技巧） | 🟡 UE 部署前 |
| 7 | 奖励修复重应用（若对照坐实逃生舱假设） | 🔄 已重定向：v1 对照已出结论，杠杆改走 v3 论文口径（tilt/r_fc/c_k/DR-reset，见 §3 重定向注）；本行余下仅剩"v3 失效时的备选升级路径"（§3 表 + v3 PLAN §9） |
| 8 | 资产换代时同步 teacher 快照文件（2026-08-31 起机器化报警：check_dr_parity ④robot 块比对/⑤usda 结构契约/⑥versions asset_lock 哈希锁；同步本身仍是人工，但漏同步会在离线闸门炸出 DRIFT） | 🟢 有闸门 |
| 9 | staged 课程 metric 接线 bug（Curriculum/*/metric 恒 0） | 🟢 低（v3 的 c_k 课程因此刻意不走 CurriculumTerm——纯函数推导 + 自定义 reward/event 读取，见 v3 PLAN D3；本 bug 修复仍挂账，只影响家族 staged 课程） |
| 10 | yaml obs_layout 更新（感知版 +扫描差异） | ✅ v3 装配时同步（v3 yaml obs_layout 注记三组；组级 SSOT = OBS.md） |
| 11 | DR 放宽策略 / resume 二阶段 | 🟢 走稳后 |
| 12 | ablation_harness 版本与待办 → `ablation_harness/HARNESS.md`（自有版本文档 SSOT，2026-09-01 拍板：仓不拆、只拆版本文档）。当前挂账：G3 剩余 `_ISAAC_ROOT` 参数化三处 → 删 `E:\IsaacLab\ablation_harness` junction | 🟡 G3 收尾 |
| 13 | v5 开训前 GUI 目视判读"碎石堆无粗糙度"，与 preflight difficulty=1.0 数字矛盾（random_rough relief p95 0.325 m @ 满档）。归因假设：PLAY 非课程模式难度 U(0,1) 随机采样，所视 tile 大概率低难度（难度 d 振幅 ≈ 0.10+0.25d m，d=0.2 时 ≈0.15 m，视觉为平缓土堆）；训练侧 curriculum=True 按行爬坡 + 出生 level 0，前期平缓是设计内。**v5.3 起由 SIR 地形课程直接回应**（用户拍板 2026-09-03）：训练流量按真实成败在固定网格上再分配（带 [0.5,0.9] 重采样），不再依赖目视——`Curriculum/terrain_levels` 判读语义反转：带内集中/爬升 = 课程在起作用（分布随能力上移是设计内），**长期贴地不动**才需复核碎石参数；二次目视用 `_tmp_terrain_previews\v5_*.png`（difficulty=1.0 渲染） | 🟡 v5 训练期观察 |
| 14 | 版本表达架构未定案：任务注册表与 teacher V 子类只增不减（现 14 注册 + V1..V5 常驻），退役条款曾写入 versioning 后撤回（commit d642ce9）。候选方向：a) 退役降级 git tag 复现 b) 组件库（地形/reward/obs spec 表化，参数级 diff 写 spec 行而非新子类）c) 维持现状。约束：teacher 零家族 import 是冻结纪律，组件化不得破坏"改组件≠改历史版本语义"。触发再议：连续两个纯参数级新版本，或第二家族立项 | 🟢 未定案（用户拍板挂账 2026-09-03） |
| 15 | SIR 课程判据 v6 候选（v5.4 弃案存档）：v5 冷启动若长期停滞——flat 集中后课程不动、rough 各行 p̂ 全带下、`Curriculum/terrain_levels` 长期钉低位（诊断信号）——则 v6 升测量判据。候选优先级：a) **逐步 Tr**（逐状态转移期望，贴论文原文，带信号从第一块就有）b) **v5.4 进度分制**（位移线性 × 存活占比 + 带下线性权重，代码保全 git `3ef2aa0`，含单测 10/10 + 冷启动梯度回归，可直接复活）。约束：v5 训练期不动判据（归因隔离，用户拍板 2026-09-03），诊断数据记入 v5 NOTES 结果回填 | 🟡 v5 训练后裁决 |
