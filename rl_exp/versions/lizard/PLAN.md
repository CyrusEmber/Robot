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
> 更新: 2026-09-16（**v15 起草（提案态）**——地形课程换 joint SIR：参数格 combo ×
> 速度桶替 v5 行 SIR，方案 SSOT = `v15\PLAN.md`；该版拟在**老框架**下训练、项目并行
> 迁新框架（`ARCH_PLAN.md` Step 2），前置门与代码件清单见挂账 #21）。
> 更早的更新行与体例演进不在此复述（`git log -p`）——本节按 `versioning.mdc:84` 只留
> 当前版本态，方案细节一律归各 `vN\PLAN.md`。

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
Phase 1  Teacher: 特权 actor PPO（当前 = v10 **已训完 15000 iter、判决半通过**——终止
         占比/success/tracking 达标，terrain_levels 未继续爬，见 v10\NOTES.md 结果表与
         DIAGNOSE.md；v13 = Miki 对称跟踪核单变量消融（闭超速/横向/停车三账本盲区，
         2026-09-14 用户拍板）已实施待训；v11 联合粒子地形课程已实施，开训门 = v10
         判决已出，待用户拍板开训）
Phase 2  Student: 蒸馏（belief encoder + 加噪扫描 + 重建损失）
Phase 3  部署: student → ONNX → UE
```

待训入口：`--task Lizard-Rough-v13`（回放 `Lizard-Rough-Play-v13`，用户拍板的速度
目标修正消融线）；`--task Lizard-Rough-v11`（联合粒子地形课程线）。验证链与摆位见
仓根 README。

**并行支线**：parkour 支线（Parkour in the Wild 范式：跑/爬/跳多专家 → DAgger
蒸馏 → RL 微调）已开 v1（2026-09-04，分支 `paper/parkour-in-the-wild`），路线与
决策见 [parkour/PLAN.md](parkour/PLAN.md) + [parkour/v1/PLAN.md](parkour/v1/PLAN.md)；
与主线 Phase 2（belief 蒸馏）互不阻塞，感知路线终裁挂 H1。

决策记录:

- **参数版本化**（2026-08-28，用户拍板）: `rl_exp/versions/lizard/main/vN/` 冻结参数副本 +
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
反趴窝杠杆已按论文口径在 **v3** 落地（`versions/lizard/main/v3/PLAN.md` D1–D4：tilt 终止 +
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
| 3 | ✅ teacher v1 训练 14000 iters + 验收：对照判出**特权救活趴窝**（零动作 success 0.254 → v1 0.635）；遗留 fall 随迭代上升（0.03→0.33）、gap_40cm 不跳 → `versions\lizard\main\v1\NOTES.md` | 完成 2026-09-01 |
| 4 | 摩擦/外力真值 obs term（event 缓存） | 🟡 Phase 2 前 |
| 5 | 三噪声模型 C++→Python 移植 | 🟡 Phase 2 |
| 6 | 延迟注入 DR（EP 技巧） | 🟡 UE 部署前 |
| 7 | 奖励修复重应用（若对照坐实逃生舱假设） | 🔄 已重定向：v1 对照已出结论，杠杆改走 v3 论文口径（tilt/r_fc/c_k/DR-reset，见 §3 重定向注）；本行余下仅剩"v3 失效时的备选升级路径"（§3 表 + v3 PLAN §9） |
| 8 | 资产换代时同步 teacher 快照文件（2026-08-31 起机器化报警：check_dr_parity ④robot 块比对/⑤usda 结构契约/⑥versions asset_lock 哈希锁；同步本身仍是人工，但漏同步会在离线闸门炸出 DRIFT） | 🟢 有闸门 |
| 9 | staged 课程 metric 接线 bug（Curriculum/*/metric 恒 0） | 🟢 低（v3 的 c_k 课程因此刻意不走 CurriculumTerm——纯函数推导 + 自定义 reward/event 读取，见 v3 PLAN D3；本 bug 修复仍挂账，只影响家族 staged 课程） |
| 10 | yaml obs_layout 更新（感知版 +扫描差异） | ✅ v3 装配时同步（v3 yaml obs_layout 注记三组；组级 SSOT = OBS.md） |
| 11 | DR 放宽策略 / resume 二阶段 | **机制与验收不在此复述**：续训状态层（注册表 + 命名 slot、载荷 v2、c_k 与 term 解耦、`--drop_curriculum_state` 正名、`REQUIRES_CURRICULUM_STATE` 硬失败）见 `FAMILY.md` / `FILEMAP.md`；验收见 `ACCEPTANCE.md` §1.4a/§1.4b。**本行只留未兑现的两项**：① DR 放宽策略；② 多 GPU 续训不在保证范围（状态只从 rank 0 写，非 0 rank 明确拒绝并记录） | ✅ 结案（余两项见事项列） |
| 12 | ablation_harness 版本与待办 → `ablation_harness/HARNESS.md`（自有版本文档 SSOT，2026-09-01 拍板：仓不拆、只拆版本文档）。当前挂账：G3 剩余 `_ISAAC_ROOT` 参数化三处 → 删 `E:\IsaacLab\ablation_harness` junction | 🟡 G3 收尾 |
| 13 | v5 开训前 GUI 目视判读"碎石堆无粗糙度"，与 preflight difficulty=1.0 数字矛盾（random_rough relief p95 0.325 m @ 满档）。归因假设：PLAY 非课程模式难度 U(0,1) 随机采样，所视 tile 大概率低难度（难度 d 振幅 ≈ 0.10+0.25d m，d=0.2 时 ≈0.15 m，视觉为平缓土堆）；训练侧 curriculum=True 按行爬坡 + 出生 level 0，前期平缓是设计内。**v5.3 起由 SIR 地形课程直接回应**（用户拍板 2026-09-03）：训练流量按真实成败在固定网格上再分配（带 [0.5,0.9] 重采样），不再依赖目视——`Curriculum/terrain_levels` 判读语义反转：带内集中/爬升 = 课程在起作用（分布随能力上移是设计内），**长期贴地不动**才需复核碎石参数；二次目视用 `_tmp_terrain_previews\v5_*.png`（difficulty=1.0 渲染） | 🟡 v5 训练期观察 |
| 14 | 版本表达架构未定案：任务注册表与 teacher V 子类只增不减，退役条款曾写入 versioning 后撤回（commit d642ce9）。候选方向：a) 退役降级 git tag 复现 b) 组件库（地形/reward/obs spec 表化，参数级 diff 写 spec 行而非新子类）c) 维持现状。约束：teacher 零家族 import 是冻结纪律，组件化不得破坏"改组件≠改历史版本语义"。触发再议：连续两个纯参数级新版本，或第二家族立项。**2026-09-15 起本项由仓根 `ARCH_PLAN.md` 承接**（候选方向 b 的具体化）；落地进度与验收归 `ACCEPTANCE.md`，本行只留决定（未定案）与触发条件 | 🟢 未定案（用户拍板挂账 2026-09-03） |
| 15 | SIR 课程判据 v6 候选（v5.4 弃案存档）：v5 冷启动若长期停滞——flat 集中后课程不动、rough 各行 p̂ 全带下、`Curriculum/terrain_levels` 长期钉低位（诊断信号）——则 v6 升测量判据。候选优先级：a) **逐步 Tr**（逐状态转移期望，贴论文原文，带信号从第一块就有）b) **v5.4 进度分制**（位移线性 × 存活占比 + 带下线性权重，代码保全 git `3ef2aa0`，含单测 10/10 + 冷启动梯度回归，可直接复活）。约束：v5 训练期不动判据（归因隔离，用户拍板 2026-09-03），诊断数据记入 v5 NOTES 结果回填。**✅ 候选 a 由 v11 落地（2026-09-10）**：联合粒子 SIR 逐步 Tr（Eq.2/3/7，口径反转记录见 `v11\PLAN.md` §3/§9）；v5 旧二值代理类冻结不改 | ✅ 结案 |
| 16 | v7 实施（ghost 断腿鲁棒性，方案 SSOT = `v7\PLAN.md`，用户拍板开 v7 2026-09-08）：V7 env cfg + 任务注册 `Lizard-Rough-v7` + broken_leg DR 事件（p=0.3，整腿 stiffness→0/damping→1.0/质量 ×0.001）+ `damage_flags` 4 维进 actor obs（90→94）+ 断腿 hfe/kfe 接触罚豁免（V7 子类，不改旧类）+ ablation_harness broken-leg eval suite + v8 ckpt 微调入口。前置依赖：v8 已训 | 🟡 提案 |
| 17 | v3 复现锚缺失（2026-09-11 血统闸 review 发现）：v3 已训（2026-09-01 首跑）但无 git tag，FAMILY 退休注记"v1/v3/v5 复现走 `git checkout <tag>`"对 v3 落空。补法二选一：考古训练起点 commit 补打 tag，或退休注记为 v3 改记 commit 锚（v5 先例：tag 当日撤，NOTES 记 git `e08636b`） | 🟢 低（原地复现已整体退役，需求弱；`check_version_docs.py` tag WARN 持续提示） |
| 18 | **归档位置：仓内 git 归档（2026-09-15 用户拍板，原判"先不归档"被演练触发）**：演练取材把不可由 rev 取回的内容（脏树 diff + 代码根内未跟踪文件）写入 `rl_exp/archive/<run_id>/` 并随仓提交——小文件进 Git 即"找回得来"，不另建 NAS / 对象存储 / 工单附件；无落点仍**硬拒采**（`rebuild.py` 硬门）。**仍未落地的两条声明（一律标未知、不得冒充通过）**：① 1.5 隔离重建的"已验证重建"评级；② 3.3 的"地形产物一致"（须归档并核验实际 mesh/heightfield）。**衍生改进项（⑧，单独排期）**：`code.<source>.untracked*` 只记名字/数量/标志、不记内容摘要 ⇒ 归档材料无法与历史那一份判"同一份"；改进 = 记未跟踪文件逐文件内容摘要（改动面 `provenance.py` + 记录格式版本）—— 但这只是评级升级的**必要**条件，必须**同时**接通归档 + `rebuild` 校验 + 旧格式降级；**旧记录缺摘要仍然未知，不得用当前文件补出历史真实性**。**2026-09-18 拆解（评审修正）**：② 分两半 —— **⑤a 离线预览生成器回归（已落 2026-09-18）**：`geometry_digest`（vertices + faces + **origin**，固定 dtype/字节序）+ `seed_rngs`（每个 sub-terrain 生成前播种 numpy **与 torch**）；自证：两次独立进程输出逐字节相同；`--self-test` 覆盖"同 seed 同结果（中间插另一次生成）/ 换 seed 必变 / origin 与 faces 都在摘要里"；反证：把播种去掉 ⇒ 三个 global-RNG 地形全红。**实测新发现（未修，需拍板）**：真跑路径**根本不播种全局 RNG** —— `TerrainGenerator` 只建自己的 local rng（`terrain_generator.py:148` 明说不碰全局），训练入口未调 `seed_everything`，而 `random_rough`/`stepping_stones` 抽 **numpy 全局流**、`boxes` 抽 **torch 全局流**（`mesh_terrains.py:348` 的 `h_noise[:, 2].uniform_`）⇒ **同一 cfg 的两次真跑几何不同**（实测：两个构建里三个地形不一致）。修法 = 在训练/harness 入口播种全局 RNG，属**训练随机性语义变更，不得顺手做**；这同时是 ⑤b 必须归档实际几何的理由。它覆盖不了完整网格的难度抖动/拼接/边界/缓存路径，`_CFG_BY_VERSION:48` 也只到 v5（v15 的 grid 归 #21）⇒ **不得据此关闭本项**。**⑤b 实际几何证据**：须在真实生成路径（`TerrainGenerator._get_terrain_mesh` 产物）采集，先定义数组类型/字节序/形状/摘要范围，归档 `rl_exp/archive/<run_id>/terrain/`，再由 `rebuild.py` 核验；**历史 run 未采到的证据保持 unknown，不得事后生成后补认**。两条声明在接通前继续标未知、不得冒充通过。**实测新发现 2（评测侧，未修，需拍板）**：`ablation_harness/suites.py` 的 `rough_a`/`rough_b` **其实不是粗糙地形** —— 单值 `noise_range=(0.05,0.05)` / `(0.15,0.15)` 使 `height_range` 只剩一个元素，`np.random.choice` 退化成常量 ⇒ 实测 p2p 恰等于 0.05 / 0.15（均匀抬升平板，无起伏）；且 `suites.py:18`「seed 钉住 RNG 流」机制上不成立（seed 进的是 `TerrainGenerator` 的 local rng，hf 函数抽**全局** numpy 流），套件的可重复性来自「范围塌缩」这条巧合。后果：**套件里没有真正的地形粗糙列**，rough 两列的 completion 测的是"走上抬升平板"。改它 = 地形几何变更 ⇒ 按协议纪律该开 `locomotion_eval_v3`（旧结果不得混表）。**进度与实测证据**（R1 拒采实例、首个演练 run 的归档清单）见 `ACCEPTANCE.md` §1.2b 追加说明 | 🟡 仓内 git 归档（首个 run 已入仓） |
| 19 | **fork 树里的 DR 改动会静默改实验**（2026-09-15 F1 汇总复核发现）：IsaacLab 树 `velocity_env_cfg.py` 的本地改动分两半——**值**半边（摩擦 `[0.4,1.2]/[0.3,1.0]`，参数实际在 `main/main_params.yaml:141-142`，三处 cfg 显式赋值实际在 `lizard_env_cfg.py:172-173`、`teacher_env_cfg.py:646-647`、`parkour_env_cfg.py:442-443` —— 原记的 `lizard_params.yaml` 路径与 159-160/614-615/424-425 均已漂移）被本仓覆盖，**模式与节拍**半边（`base_external_force_torque.mode=interval` 及 `interval_range_s`、`push_robot.interval_range_s`）**未被覆盖 ⇒ 继承进 lizard**，golden 里可见该形状。后果：任何新 run 的 DR 都由这份未提交的 fork 树内容决定，改它等于改实验。**2026-09-18 根因更正（评审）**：不是"只有 golden 差异能抓到"—— `framework_pin_check.check_fork_patches` 取全部 patch 的 `+++ b/` 目标并集（`:135`）并对每个目标做换行归一化**整文件**字节比对（`:175-182`），`velocity_env_cfg.py` 已在目标中 ⇒ **只改树单边，现有检查就会红**（**2026-09-18 实测**：走 `neither applied nor appliable` 分支 —— 整文件比对本就只在全部 patch 仍可应用时才跑），**不能用它证明新断言有效**；新断言的价值只在**树与 patch 同时改、两者仍一致**时显现。**两臂实测（2026-09-18）**：a) 只改树 ⇒ 现有检查红 + 语义钉红；b) 树与 patch 同改并重钉 ⇒ 现有检查**绿**、**语义钉红**（含"改名后冻结值仍在别的 event 里"的反例）。**方案**：AST 解析活树 `velocity_env_cfg.py`，**按赋值目标名**（`base_external_force_torque`/`push_robot`）取 keyword 值钉住 `mode="interval"`、`interval_range_s=(4.0,8.0)`/`(3.0,6.0)` —— 不用全文件 regex（注释或其他事件会误满足；`force_range`/`torque_range` 刻意不钉，被配方覆盖）。**已实施（2026-09-18）**：`framework_pin_check.check_fork_dr_semantics` + `--self-test`（5 fixtures，进程内自证）；hook 侧 —— `hooks/pre-commit` 触发过滤补 `\.patch$` 与 `^hooks/`，hook 内跑 `framework_pin_check --strict --self-test`（无树记录时 WARN 跳过，套件仍跑），离线套件条目改带 `--self-test`。（触发缺口原状：`hooks/pre-commit:15` 的过滤只认 `rl_exp|ablation_harness/` 下的 `.py/.yaml/.json/.urdf/.usda` —— `.patch` 自身与 `hooks/` 的改动都不触发。） | ✅ 结案（2026-09-18） |
| 20 | **`isaaclab.bat` 被清空 + 树根出现未跟踪 `python` 文件**（2026-09-15 发现；**2026-09-18 实查定性**）：`isaaclab.bat` 从 49 行被改成空文件 = `local_tree_extras.patch` 的**刻意目标**（空 blob `e69de29bb`；`git status` 报 `M` 即预期态）⇒ **不是故障、不修**，结论 = 弃用 bat 引导，仅在 patch 头部补一句注记（该注记本身会改 `.patch`，故须先完成 #19 的 hook 触发过滤）。树根 `python`：实测 **0 字节**、未被 `.gitignore` 忽略、不在任何 patch / 锁 / 归档内（`provenance.split_untracked` 按 code root 分流，它在 code root 外 ⇒ 只影响未来 `untracked_outside_code_root` 计数）⇒ **删**。**验收（相对口径，不是"只剩 M isaaclab.bat"）**：操作前后各跑一次 `git -C <树> status --porcelain`，差异**恰好**少一行 `?? python`；树内其余条目（实测 `M play.py` / `M train.py` / `M anymal_c_env.py` / `M velocity_env_cfg.py`，`?? IMG/ _tmp_pngcheck/ model/ rl_exp/ spider/`）**逐项保持不变** —— 不得为满足验收清理其他内容。**已执行（2026-09-18）**：`python` 已删 —— status 由 11 条（5 个 `M` + 6 个 `??` 含 `python`）变 10 条，其余逐项不变；patch 头部已加"刻意置空 + DR 语义钉在包外"注记，`git apply --check --reverse` 仍通过、闸门绿 | ✅ 结案（2026-09-18） |
| 21 | **v15 起草（提案态，2026-09-16 用户拍板）**：地形课程换 **joint SIR**（"用 SIR 课程，不要 v14 的地形课程"），base = v14，obs/动作/奖励/终止/DR/资产逐字段零差异。**v15.3（2026-09-16）重规划**：保留联合 SIR，改**评分与冷启动**——逐帧达标换 yaw 帧跟踪误差 `‖vel_yaw_xy − cmd_xy‖ ≤ track_tol_mps`（用实际含 jitter 的指令）、`Tr` 分母改固定观察窗口 `W`（提前失败记未达标）、冷启动改显式 `anchor_combo` + 全部最低桶、每块只做一次局部扩展；**取消**硬解锁 / `anchor_share` 85% 锚集 / 掌握判据；机制评审 5 条的修复已落共享实现（v11/v12 golden 随之重生成）。方案 SSOT = `v15\PLAN.md`（已起草：PLAN/NOTES/base.json/yaml 段 + 血统边），**代码件待实施**（V15 env cfg + PLAY、注册 `Lizard-Rough-v15`/`-Play-v15`、runner cfg、`SMOKE_SPEC["v15"]` + 薄壳、`check_dr_parity` 白名单、离线套件、冻结前 `cfg_lock --update` + tag）。**2026-09-18 实施坑与分段（评审修正）**：① `components.py:233 _PARAM_GRID_SECTION = "v11"` 是写死的单常量，而 v15 的 grid 在 `params["v15"]`（`main/v15/main_params.yaml:428-429`；v12 的 params 照抄 v11 段，`main/v12/main_params.yaml:335-336`）⇒ 必须换**显式映射** `v11→v11 / v12→v11 / v15→v15`，并跑全量 golden 证 v11/v12 逐字段不变；② 清单里的 `check_dr_parity` 白名单项在声明式重构后**疑为 no-op**（`wiring_lines()` 只扫 `self.(events|rewards|terminations)`，抓不到 `curriculum.joint_sir`）⇒ 实施前先判，删项或另写；③ **装配与机制分两阶段验收**：装配 = 7 文件 + 注册 + smoke + `diff.json` + 套件条目 + tag；v15.3 机制（yaw 帧标签 / 固定窗口 `W` / `anchor_combo` / `curriculum_state` v2→v3）**四项待拍板**，尤其"共享课程类是否改变历史版本语义"须先定，**不得夹在装配里顺手做**。**依赖/前置门三条**：① joint SIR 线**从未真训**（v11 仅 6-iter 冒烟、v12 无 run）⇒ 本版为该课程线首跑，v11/v12 不作基线；② 用户意图 = **本版在老框架训练的同时把项目迁到新框架**（`ARCH_PLAN.md` Step 2）⇒ 开训前**必须打 tag**、训练进程**不得重启/续训**、训练结束前**不得 `cfg_lock --update`**（违反任一条，本次 run 的"可重建"声明作废）；③ 迁移后必须保留旧任务 id 映射才能评 v15 ckpt（Step 2.1 不变量）。命令口径变化（离散步点 vs 连续 U(0,3)）⇒ v15 跟踪数字不得与 v5–v14 同表 | 🟡 起草中（实施待启动） |
| 22 | **版本类体删除 + `[41]` 保真比较退役**（2026-09-17 完成）：注册表自 `2f67f4c` 起已指 `recipe_tasks` 的生成类 ⇒ 版本子类运行期无人引用。**依赖面与执行顺序不在此复述**（① 冻结 golden 记类名 26 处；② 12 个闸门/测试按名构造；③ `direction_probe`/`play_fast_task`；④ 文档教"新建版本类"；⑤ `[41]` 按发现取被替换类，删净后必然红），四步与逐条证据见 `ACCEPTANCE.md` §「2.4 收尾」。**本行只留决定**：golden 的 `env_cfg_class` 列**定点搬一行**到 `recipe_tasks:<同名>`，不改记配方键 —— `manifest.recipe_ref` 按**类名后缀**匹配 golden，改键会把迁移面扩大一轮（用户拍板 2026-09-17）；摘要随之变更并记在 B0 追加②；`[41]` 的"表 == 类"比较**反向**成"重复路径复活"探针（一个配方两个表达式即红），原缺口台账随其生产者（版本类）退役。**残留**：`--vs-upstream` 的归因列在翻表当天就已退化（它读本次构造的 entry），逐路径作者的替代来源是各配方的 `diff.json`；生成类的名字清单唯一来源 = `versions\recipes.json`。**2026-09-18 追加**：`env_cfg_class` 列**此前无人比较**（全仓唯一读者 `manifest.recipe_ref` 按类名后缀匹配 golden）⇒ step 2a 的"语义不变"当时只由一次性脚本自证，故已在 `[41]` 加常驻断言（golden 列 == 身份映射为该任务声明的入口；等价于注册表，因 `[31]` 已把两者逐字绑死），反证见 `ACCEPTANCE.md` 该节追加 —— 同一份文件 `[41]` 红而 `[24]` 绿 | ✅ 结案 |
| 23 | **L03 真跑臂：缺课程状态 resume 必须硬拒**（C4 剩余入口侧，2026-09-17 起）：离线半边已有（`test_missing_state_hard_aborts_and_weights_only_opts_out`），缺真进程证据。**方案（自足）**：窗口内跑 v14 短训得到带状态 ckpt → 复制并剥掉 `infos[STATE_KEY]`（原件不动）→ `--resume` 指向它 ⇒ 期望**非零退出 + 硬拒**（而非 WARN 冷启动），T1 的 `resume.source` 指向该文件（生命周期证据里的 `source_checkpoint` 字段已随 2026-09-17 收缩删除，源由 T1 负责记录）、`declaration_problems` 记缺状态；同一 ckpt 加 `--drop_curriculum_state` ⇒ 放行 + 记"显式降级"。**落点**：`lifecycle_entry_run.py` 新增 `--track resume` 档（判据同 `trainer` 档：退出码 2 + T0 拒绝记录 + `--verify` 不判损坏）；离线不可替代。**反证**：换成带状态的 ckpt ⇒ 同一命令必须成功（证红来自"缺状态"而非命令写错）。**结案（2026-09-18）**：真跑两臂过——arm2（剥状态 ckpt）**exit 2 硬拒**且文案点名缺状态；arm3（同 ckpt + `--drop_curriculum_state`）**exit 0 放行**，T1 `resume.status="dropped"`。期间发现并修掉"参数网格主线真跑全灭"（P005，`docs/pitfalls.md`）+ 失败退出码被 sim teardown 改写成 0，新增闸门 `check_split_probe_wait.py`。证据见 `ACCEPTANCE.md` §「主线真跑收口 + L03 真跑臂」 | ✅ 结案（2026-09-18） |
| 24 | **硬 B 覆盖面：agent（PPO）侧 + main 线差异声明**（2026-09-17 起，**同日已结案**）：agent 侧进清单（`baseline\v1\diff.json` 的 `agent` 段 + `hard_b()` 检查；ACCEPTANCE 里"硬 B 只覆盖 env cfg"一句已由 B4 节作废注记更正）。**main 线差异声明已补齐**：口径取 **B 谱系**，且**不由声明选**——`base.json` 有母版 ⇒ 对 `build(母版)`，root ⇒ 对 stock（本行原写的"A/B 二选一"当场被这条规则取代）。现存 **12 份 `diff.json`**：`main\v2..v14` 共 11 份（format 4，按作者集合分组：元素集 / `components.X` / `wiring`）+ `baseline\v1` 1 份；`main\v1` **刻意无声明**（母版 `v0` 无配方声明 ⇒ 谱系读数不可得，`[41]` 打印 `no difference declaration (hard A only): ['v1']` 而不是静默跳过），`v0/v7/v9` 不在链上。`EXPECTED_DIFFS` 逐条钉数（76+6+59+6+46+4+2+2+75+40+3+3=**322**），`params_version` 按名过滤为身份字段而非差异。落地 commit **`bfee543`**（闸门 + 11 份声明 + 格式 4 重排；记录见 ACCEPTANCE §B4 "main 线 12 条配方的差异声明"）。**本次独立复核**：`[41]` 单跑 `RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 322 declared difference(s) against their own base)`；反证重打一次（v10 的 `terminations.tilt` 改成不存在的路径）⇒ 三个检测器同报「未声明改动 / 声明已不生效 / 组件不拥有该路径名字」，原样回滚复绿 ⇒ **"只有 v14（1/12）"与"main 线没有差异声明"两条旧读数均过时**。硬 A（与 golden 逐字段一致，证"没漂"）与硬 B（与母版差异恰好等于声明，证"被声明"）互不可替，各自有反证。**残留（ACCEPTANCE §B4 边界已写）**：组件归属是"名字级"的（一条路径里两个组件各拥有一个名字时点名任一个都过 ⇒ 最软处）；路径是派生的、生成器用完即删 ⇒ 派生错误会同时落在文件与闸门两侧，独立边界只剩硬 A | ✅ 结案（2026-09-17） |
| 25 | **两条策略反转（2026-09-17，用户拍板"都是有意的"）→ 文档口径待同步**：① **退休线放行开关撤销**：`--allow_retired_resume` 从契约与补丁中移除，`recipe_lifecycle.judge(operation, status)` 只看状态 ⇒ **退休线一律拒新训与续训**，无豁免（旧文字"必须同时指定 resume 并解析到有效源 checkpoint 才豁免"作废）；② **manifest 不可用即硬拒**：fork 补丁的 `ImportError` 分支从 WARN 改 `[FATAL] … refusing to launch unrecorded` + `os._exit(2)` ⇒ 1.2a 的"记录绝不阻断训练"约定被**有意反转**（无 `rl_exp` 的树不能开训）。**口径同步（2026-09-17 收账）**：`ARCH_PLAN.md` 的收缩事实（现值 `:281`/`:298`/`:303`/`:317`，即本行原先点名的 `:304`/`:364`）随 `e4bd08e` 改写落地；`:122`（1.2a"ImportError 仅告警"）与 `:160`（1.3 第 1 条）本轮补齐 manifest 硬拒那句 ⇒ **旧口径已无残留**。`ACCEPTANCE.md` 按"追加不改写"补两条：收缩说明（`3ebf929` 那批）与 L02 入口侧两档重跑（本轮，见该文件 2026-09-17 补记）。代码侧：`lifecycle.py` 瘦身、parkour 真退休线当入口侧 fixture、`lifecycle_entry_fixture.py` 删除已入 `ee5778d`。**`[1]` 重钉**：本机实跑 `PIN_CHECK_OK`（存档与 fork 树逐字节一致）；重钉后的存档已随批提交（`ef2158d`/`6b5e1ee`），此后每次改 fork 树都当场重钉并复跑本闸门 | ✅ 结案（2026-09-17；存档收账 2026-09-18） |
| 26 | **Step 3.4 蒸馏与导出校验 —— 本轮不执行（登记，非排期承诺）**：① 导出前协议校验（`teacher_networks.py:176-243` 的 flat/分段与 ONNX/JIT 路径）；② 蒸馏数据 manifest ＋分片哈希（Phase 2 建）。P05/P06/P07 标"未执行"，不得通过。**现存冲突记敞口**：冻结 yaml 的 `obs_layout` 与协议声明**不同形**（yaml 写 `joint_pos_rel`，代码 term 是 `joint_pos`），它是 UE 侧契约，本轮不动导出。另：**几何一致性**（"地形产物一致"）须归档并核验实际 mesh/heightfield，本轮不执行 ⇒ 记未知（与 #18 ② 同一条腿；原记 "#18 ③" 为笔误）。**2026-09-18 定性**：只有 ⑤b 在真实生成路径采到实际产物并归档后，本项才具备判定条件，⑤a 的离线预览摘要**不能**替代 ⇒ ⑤b 落地前本项保持"未执行／不得通过" | 🟠 待排期（未执行） |
| 27 | **记录体系的两条结构性敞口（2026-09-17 评审提出）**：① **两套记录词汇并存** —— 训练侧 `rl_exp/tools/runrecord/manifest.py` 与评测侧 `ablation_harness/record.py` 记同一批事实、各有一套命名（`obs_protocol_digest` vs `obs_layout_digest`；资产锁两侧各算一遍），漂移只是时间问题；收敛路径 = 抽出共享的"绑定面 + 三态读侧"最小公共层，两侧各自保留自己的入场/落点。**2026-09-18 摸清后收窄**：共享面**已半存在**（eval 直接调 `manifest.protocol_ref`/`manifest.asset_digest`，`eval.py:199/212`），真正重复的是**原语**：① `sha256_file`（`provenance.py` vs `record.file_sha256`，**前缀不同**：裸 hex vs `sha256:`）、② git 身份（`prov.rev` = `rev-parse HEAD`[:12] vs eval `_git_rev` = `--short`≈7 ⇒ **同一 commit 在两份记录里是两个字符串**）、③ rsl_rl 身份（editable 时训练记 source rev、eval 记发行版版本号 ⇒ 不可对账）、④ 资产绑定口径（eval 的 `declared_digest` 退化为 lock 文件哈希，训练侧绑 `manifest_sha256`）。**已做（2026-09-18）**：重复的原语收进 `rl_exp/tools/runrecord/binding.py`（stdlib-only 一处家：`sha256_bytes`/`sha256_file`/`git_run`/`git_rev` + `REV_LENGTH`；`provenance` 保旧名转发，`check_dr_parity`/`check_golden_frozen` 的两份内联实现一并收掉），rev 口径统一为 12 字符（实测同一 commit 两侧同串；键名与记录格式版本未动，除该项外无任何已记录值变化 —— `GOLDEN_FROZEN_OK`/`PARITY_OK` 复跑为证），单源闸门 `check_record_bindings.py`（套件末条，1.2s；反证：把三签名之一的副本放进目录再指过去 ⇒ 非零退出且点名行号）。**③④ 也已闭（2026-09-18）**：③ eval 的 `runtime` 增 `rsl_rl_id`，由 `provenance.rsl_rl_id()` 拼写（与训练侧 golden 组合键的 `rsl_rl=` 同一个函数 ⇒ 两份记录首次可对账）；`rsl_rl_version` 保留为它自己的事实。**刻意不进 `record.ALWAYS`**：设为必需会把已落盘的 eval 记录读作"不完整"，与 `metrics.derived` 同一个判据。④ eval 的 `assets.declared_digest` 去掉"退化为 lock 文件哈希"的兜底，只认 `manifest_sha256`，缺失即 `unknown` —— 那个兜底让"没有 manifest 摘要的锁"读成了"绑定了"，且用了另一个事实的名字。闸门 `check_record_bindings.py` 相应加第 4 条签名（`f"source:…"`/`f"installed:…"` 这类**第二处身份拼写**，`.format()` 形态同判；`provenance.py` 与 `binding.py` 同为豁免家），自检里加了正/反例（含一条"另一个前缀是另一个事实"）—— 顺带被自检抓到过我自己写错的 `.format()` 匹配（模板在 `func.value` 不在 `args`）。② **单源扫描闸守"副本"不守"新规则"**：`check_terrain_split_source.py` 只认 `terrain_map` 的 epsilon 签名，新写一个**不同**的切分规则不会被抓。**原拟补法不成立（2026-09-18 实测）**：`test_component_ownership.py` 的所有权表是"谁**写**某个 scene 名"（AST 只扫 `Assign`/`setattr` + `OWNERSHIP` 叶子名），表达不了"谁**解释**某个值"这类读者断言，新规则不写任何 scene 名 ⇒ 对它是全局隐形。**改为可判定形式（已闭）**：`terrain_map.check` 把声明的列映射**回代本规则**，不一致即拒 ⇒ "一份来自别的规则、但自身自洽"的记录**不能**被消费（反证：撤掉该分支后同一用例返回 `[]`，`test_terrain_map.py` 两条新例咬住）；静态扫描的门槛与天花板已在其 docstring 写实（查副本，不查语义）。另记两条小敞口：① `--variant` **命名靠人** —— 它是"换过输入（协议/ckpt/suite/故意无锁）时另起 run 身份"的自由文本标签，追在 `run_id` 后做后缀、并在记录里留 `variant` 字段；没有机械校验它是否描述得对，也没从"检测到的替换项"反推名字（可反推的至少有 suite 替换与 ckpt 迭代）。② `record.json` 体积：实测 **88.8 KB**（无锁那份 54.7 KB），其中 `env_cfg` 快照 ≈ 40 KB 紧凑 JSON（占内容 95%，缩进后再翻倍）—— 无机械消费者 ⇒ 长期跑分会胀，升级路径 = 内容寻址快照。**挂账（未验，2026-09-18）**：③ 的新键 `runtime.rsl_rl_id` 只在**下次真跑 eval** 时才写进 `record.json` —— `eval.py` 是模块级 argparse 的脚本，离线导入会去解析 argv，所以这条改动**离线断言不了**（形状与训练侧同函数、UNKNOWN 兜底已读代码确认，但不声称"已跑过"）。下次 eval 跑完请核对：`record.json.runtime.rsl_rl_id` 与同 run 训练记录的身份**同一拼写** —— `rsl_rl_id()` 返回 `source:<rev>` / `installed:<distribution_version>`（`provenance.py:163-170`），而 `code.rsl_rl.rev` 存的是**裸 revision** ⇒ **不能直接相等**，须按训练记录的 `mode` 重建同一身份再比；若落成 `unknown`，查 `rl_exp` 是否在 `sys.path`、`rsl_rl` 是否可导入。**③ 离线补测（2026-09-18 定）**：把 `_baseline_evidence` 连 `_run_dir`（`eval.py:611-635` / `:586-588`）一起搬进 `record.py`（`args_cli` 改显式参数，`eval.py` 只留薄壳），测试补**三条异常路径**（目录不存在 / 只有 `eval.json` 的 pre-format 邻居 / 坏 JSON）+ **一条成功路径**（同 protocol、同 group 的可读基线真被读到 —— 专抓"路径拼错导致永远 unknown"）；坏 JSON 例只钉业务文案前缀（`… is unreadable (`），不锁死解析器完整报错文本。**方案（2026-09-18 评审修正后定稿，A3 → B1；A1 暂缓、A2/B2 不建议）**：① 机械账（A3）：落盘时记"相对基线的**已证实**变化类别（两个 obs 字段并成一类）+ 未证实的 binding 路径及原因 + 基线引用与当时采用的 binding 值"。**基线口径**：只取同 `protocol` + 同 `group` + **拼 variant 之前的基础 run_id**（`eval.py:586/729`；基础 id 在拼接前保留，不靠拆字符串还原），**找不到可读证据即 `unknown` 并写出原因，不去搜相似目录猜基线**（实例：`…suite-roughb016`、`…ckpt1150` 的无后缀邻居只有 `eval.json`，机械上不可比 ⇒ `unknown` 不总等于"第一次跑"）。**`differences` 不能直接映射成 substitutions**（`record.py:243` 把 unknown→已知同时放进 `differences` 与 `unproven`；legacy/不完整直接返回 unknown + 空 differences ⇒ 直接取差异键会把"证据补齐"误判成替换、把"无法判断"误报成无替换）；`substitutions: []` **只能**表示"比过且无确定替换"，不代表比较成功。新信息不进 `ALWAYS`（同 ③ 的判据）。**A1（2026-09-18 定下语义，待实施）**：只定义为"**类别声明校验**"——不承诺校验标签内容真实（写了 `ckpt1150` 无法证明是 1150 迭代）。**定案**：语法 `--variant <token>[+<token>...][-<自由文本>]`，token 取 `record.SUBSTITUTION_CATEGORY` 五类（`checkpoint`/`suite`/`assets`/`protocol`/`obs_protocol`）；重复 token 拒、解析不出任何 token 拒、**自由文本拒路径分隔符**（它直入 run 目录名）；**语法检查做成 `record.py` 的纯函数**，`eval.py` 在 `parse_args()` 之后、`AppLauncher()` 之前调用（秒级死且离线可测）。一致性规则：**已证实变化类别必须包含在声明中；多写的类别允许存在，但不得被解释为已证实**（记录里显式区分 `claimed` 与 `confirmed`，禁止实现成集合相等）；`comparison != "compared"` 时不做一致性判定；`--overwrite` **语法与一致性都不绕过**；一致性检查在算完 evidence 之后、rollout 之前（`eval.py:834` 与 `:838` 之间 —— 原记"前置入口 `eval.py:611`"是该函数的定义处，不是门槛本身），错误须给出基线、变化字段、缺少的类别与可用标签示例。② 体积（B1，去重收益真实：六份记录里四份 env digest 相同；已核实 **eval.json 都不含快照**，快照只在 `record.json` 的 `env_cfg`/`agent_cfg`，仓内未发现生产读侧，但外部消费者无法用仓内搜索排除）：快照本体外置为按摘要命名的共享文件，记录留摘要 + ref。**2026-09-18 修正（评审）**：`agent_cfg.clip_actions` **在 `ALWAYS` 中**（`record.py:53`）⇒ `agent_cfg` 对象**不得**缩成 `{digest, ref}`，必须保留 `clip_actions`，否则新记录被读作"不完整"；已存在的快照文件**必须校验摘要**再复用（"文件存在即跳过"会把损坏文件持续固化并复用）；`ref` 相对 **results 根**，并测"整个结果包搬移后仍可读"；本轮**不新增 `--export`**，"导出单个 run 目录须带被引用快照"落成**未来导出契约**（记入 `HARNESS.md` 记录格式节）。约束：摘要必须用 `cfg_snapshot.digest()`（**保键序**，与 `record.digest()` 的排序哈希语义不同，`cfg_snapshot.py:228`）；**快照写成功后才发布引用它的记录**，共享写不得用固定 `.tmp` 名（并发写同一快照要能过）；读侧按需解析并区分"可用 / 缺失 / 损坏或摘要不符"，缺失可回 `unknown` 但**原因必须可见**；**快照缺失不得改变原 bindings 的比较结论**；旧内联记录继续可读；**导出单个 run 目录必须带上被引用的快照**（否则搬走一个目录证据就没了）；**不改 eval.json**。**一年后最该防的故障**：基线被 `--overwrite` 改写、旧 `substitutions` 仍指同一路径 ⇒ 只存 `["suite"]` 不足以审计，必须保存**当时**的比较依据，读取时不得拿"当前基线"重新解释历史。**验收要点**：部分 unknown / legacy 基线 / 基线被覆盖 / 多项替换标签 / 旧内联读取 / 外置快照缺失与损坏 / 并发写同一快照 / **整个结果包搬移后读取** / **已存在快照摘要不符 ⇒ 不复用**。**执行顺序（2026-09-18 定）**：①②③ 离线 → ④ B1 → ⑤a 离线回归 → **一次真实运行**（同时结 ③ 的身份/标签核对与 ⑤b 实际几何采证）→ ⑥ A1 → ⑦ v15 装配与机制分阶段；⑧ 单独排期（未完成前"已验证重建"评级保留限制）。**A3 已落（2026-09-18）**：`record.substitution_evidence(candidate, baseline, baseline_ref=...)` 纯函数（离线 18 例）产出

```json
"substitutions": {"comparison": "compared", "baseline": {"run_id": "...", "path": "results/.../record.json"},
                  "reason": "", "substitutions": ["suite", "obs_protocol"],
                  "unproven": [{"path": "assets.declared_digest", "reason": "the baseline value is unknown"}],
                  "bindings": {"suite.digest": {"candidate": "...", "baseline": "..."}, "...": {}}}
```

类别 token = `checkpoint`/`suite`/`assets`/`protocol`/`obs_protocol`（两个 obs 字段并成一类）；`eval.py` 只在给了 `--variant` 时、**拼后缀前**把基础 run_id 留成值，去同 protocol + 同 group 找可读记录，找不到即 `unknown` + 原因、**不搜相似目录猜**；无 `--variant` 的基础 run **不写该键**；新键不进 `ALWAYS`。**A1（标签类别校验）与 B1（快照外置）未动（语义已于 2026-09-18 定案，见上一行挂账）**。**挂账（未验，2026-09-18）**：写侧 `rec["substitutions"] = ...` 只在真跑 eval 时落盘（与 `rsl_rl_id` 同一性质，`eval.py` 是模块级 argparse 的脚本 ⇒ 离线导入即解析 argv）；下次真跑核对：变体 run 的 `comparison`/`substitutions` 取值，以及"无后缀邻居只有 `eval.json`"的变体（`…suite-roughb016`、`…ckpt1150`）是否落成 `unknown` + `pre-format run` 原因。另：`_baseline_evidence` 的三条 reason 文案离线不可达（无自动断言），只测了 `record.substitution_evidence` 侧 —— **已修（2026-09-18，harness v1.7.3）**：`record.run_dir` + `record.baseline_evidence` 接手布局规则与三条 reason，`test_eval_record.py` 22 例（三异常 + **一条成功路径**）；反证：去掉 `run_dir` 的 group ⇒ 成功例红并报 `nothing at <path>`。**余下只有真跑核对**（口径见上一行 ③：`rsl_rl_id` 须按训练记录 `mode` 重建身份再比）。 | ✅ 两条都已闭（① 原语与 ③④ 两条漂移均收口，② 换方式已闭）；余两条小敞口（`--variant` 命名靠人、`record.json` 体积）另记 |
