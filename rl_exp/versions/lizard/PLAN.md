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
| — | **已收走**（正文在关闭项，本表不复述）：#1/#2/#3 → `work/closed/2026/teacher-v1-first-run.md`；#10/#15 → `sir-criterion-and-obs-layout`；#19/#20 → `fork-tree-dr-semantics-and-hygiene`；#22/#24 → `recipe-registry-and-diff-declaration`；#23/#25 → `lifecycle-hard-refusal-and-policy-reversals`（后四条同在 `work/closed/2026/`） |

| # | 事项 | 优先级 |
|---|---|---|
| 4 | 摩擦/外力真值 obs term（event 缓存） | 🟡 Phase 2 前 |
| 5 | 三噪声模型 C++→Python 移植 | 🟡 Phase 2 |
| 6 | 延迟注入 DR（EP 技巧） | 🟡 UE 部署前 |
| 7 | 奖励修复重应用（若对照坐实逃生舱假设） | 🔄 已重定向：v1 对照已出结论，杠杆改走 v3 论文口径（tilt/r_fc/c_k/DR-reset，见 §3 重定向注）；本行余下仅剩"v3 失效时的备选升级路径"（§3 表 + v3 PLAN §9） |
| 8 | 资产换代时同步 teacher 快照文件（2026-08-31 起机器化报警：check_dr_parity ④robot 块比对/⑤usda 结构契约/⑥versions asset_lock 哈希锁；同步本身仍是人工，但漏同步会在离线闸门炸出 DRIFT） | 🟢 有闸门 |
| 9 | staged 课程 metric 接线 bug（Curriculum/*/metric 恒 0） | 🟢 低（v3 的 c_k 课程因此刻意不走 CurriculumTerm——纯函数推导 + 自定义 reward/event 读取，见 v3 PLAN D3；本 bug 修复仍挂账，只影响家族 staged 课程） |
| 11 | DR 放宽策略 / resume 二阶段 | **机制与验收不在此复述**：续训状态层（注册表 + 命名 slot、载荷 v2、c_k 与 term 解耦、`--drop_curriculum_state` 正名、`REQUIRES_CURRICULUM_STATE` 硬失败）见 `FAMILY.md` / `FILEMAP.md`；验收见 `ACCEPTANCE.md` §1.4a/§1.4b。**本行只留未兑现的两项**：① DR 放宽策略；② 多 GPU 续训不在保证范围（状态只从 rank 0 写，非 0 rank 明确拒绝并记录） | ✅ 结案（余两项见事项列） |
| 12 | ablation_harness 版本与待办 → `ablation_harness/HARNESS.md`（自有版本文档 SSOT，2026-09-01 拍板：仓不拆、只拆版本文档）。当前挂账：G3 剩余 `_ISAAC_ROOT` 参数化三处 → 删 `E:\IsaacLab\ablation_harness` junction | 🟡 G3 收尾 |
| 13 | v5 开训前 GUI 目视判读"碎石堆无粗糙度"，与 preflight difficulty=1.0 数字矛盾（random_rough relief p95 0.325 m @ 满档）。归因假设：PLAY 非课程模式难度 U(0,1) 随机采样，所视 tile 大概率低难度（难度 d 振幅 ≈ 0.10+0.25d m，d=0.2 时 ≈0.15 m，视觉为平缓土堆）；训练侧 curriculum=True 按行爬坡 + 出生 level 0，前期平缓是设计内。**v5.3 起由 SIR 地形课程直接回应**（用户拍板 2026-09-03）：训练流量按真实成败在固定网格上再分配（带 [0.5,0.9] 重采样），不再依赖目视——`Curriculum/terrain_levels` 判读语义反转：带内集中/爬升 = 课程在起作用（分布随能力上移是设计内），**长期贴地不动**才需复核碎石参数；二次目视用 `_tmp_terrain_previews\v5_*.png`（difficulty=1.0 渲染） | 🟡 v5 训练期观察 |
| 14 | 版本表达架构未定案：任务注册表与 teacher V 子类只增不减，退役条款曾写入 versioning 后撤回（commit d642ce9）。候选方向：a) 退役降级 git tag 复现 b) 组件库（地形/reward/obs spec 表化，参数级 diff 写 spec 行而非新子类）c) 维持现状。约束：teacher 零家族 import 是冻结纪律，组件化不得破坏"改组件≠改历史版本语义"。触发再议：连续两个纯参数级新版本，或第二家族立项。**2026-09-15 起本项由仓根 `ARCH_PLAN.md` 承接**（候选方向 b 的具体化）；落地进度与验收归 `ACCEPTANCE.md`，本行只留决定（未定案）与触发条件 | 🟢 未定案（用户拍板挂账 2026-09-03） |
| 16 | v7 实施（ghost 断腿鲁棒性，方案 SSOT = `v7\PLAN.md`，用户拍板开 v7 2026-09-08）：V7 env cfg + 任务注册 `Lizard-Rough-v7` + broken_leg DR 事件（p=0.3，整腿 stiffness→0/damping→1.0/质量 ×0.001）+ `damage_flags` 4 维进 actor obs（90→94）+ 断腿 hfe/kfe 接触罚豁免（V7 子类，不改旧类）+ ablation_harness broken-leg eval suite + v8 ckpt 微调入口。前置依赖：v8 已训 | 🟡 提案 |
| 17 | v3 复现锚缺失（2026-09-11 血统闸 review 发现）：v3 已训（2026-09-01 首跑）但无 git tag，FAMILY 退休注记"v1/v3/v5 复现走 `git checkout <tag>`"对 v3 落空。补法二选一：考古训练起点 commit 补打 tag，或退休注记为 v3 改记 commit 锚（v5 先例：tag 当日撤，NOTES 记 git `e08636b`） | 🟢 低（原地复现已整体退役，需求弱；`check_version_docs.py` tag WARN 持续提示） |
| 18 | **归档位置：仓内 git 归档（2026-09-15 用户拍板，原判"先不归档"被演练触发）**：演练取材把不可由 rev 取回的内容（脏树 diff + 代码根内未跟踪文件）写入 `rl_exp/archive/<run_id>/` 并随仓提交——小文件进 Git 即"找回得来"，不另建 NAS / 对象存储 / 工单附件；无落点仍**硬拒采**（`rebuild.py` 硬门）。**仍未落地的两条声明（一律标未知、不得冒充通过）**：① 1.5 隔离重建的"已验证重建"评级；② 3.3 的"地形产物一致"（须归档并核验实际 mesh/heightfield）——**② 已于 2026-09-20 落地（见下 ⑤b 收口：归档 + 再生核验）；历史 run 未有归档仍一律 unknown**。**衍生改进项（⑧，单独排期）**：`code.<source>.untracked*` 只记名字/数量/标志、不记内容摘要 ⇒ 归档材料无法与历史那一份判"同一份"；改进 = 记未跟踪文件逐文件内容摘要（改动面 `provenance.py` + 记录格式版本）—— 但这只是评级升级的**必要**条件，必须**同时**接通归档 + `rebuild` 校验 + 旧格式降级；**旧记录缺摘要仍然未知，不得用当前文件补出历史真实性**。**2026-09-18 拆解（评审修正）**：② 分两半 —— **⑤a 离线预览生成器回归（已落 2026-09-18）**：`geometry_digest`（vertices + faces + **origin**，固定 dtype/字节序）+ `seed_rngs`（每个 sub-terrain 生成前播种 numpy **与 torch**）；自证：两次独立进程输出逐字节相同；`--self-test` 覆盖"同 seed 同结果（中间插另一次生成）/ 换 seed 必变 / origin 与 faces 都在摘要里"；反证：把播种去掉 ⇒ 三个 global-RNG 地形全红。**实测新发现（2026-09-18 已修）**：真跑路径**曾**不播种全局 RNG —— `TerrainGenerator` 只建自己的 local rng（`terrain_generator.py:148` 明说不碰全局），训练入口未调 `seed_everything`，而 `random_rough`/`stepping_stones` 抽 **numpy 全局流**、`boxes` 抽 **torch 全局流**（`mesh_terrains.py:348` 的 `h_noise[:, 2].uniform_`）⇒ **同一 cfg 的两次真跑几何不同**（实测：两个构建里三个地形不一致）。**已修（2026-09-18，用户拍板）**：训练入口把 `configure_seed(env_cfg.seed)` 提到 `gym.make` **之前**（上游那次在 runner 之后 = 地形已建好），存档 `fork_patches/train_seed_rng.patch`（`framework_pin_check.py --strict --self-test` 逐字节重建证明树与全部存档一致）；评测入口 `eval.py` 在 `gym.make` 前 `seed_rngs(suites.SUITE_SEED)`。**这条改的正是训练随机性语义 ⇒ 离线只能证"种子生效"，验收要等一次真实运行**：用 ⑤b 采到的 `[TERRAIN_GEOMETRY]` 摘要做「同一 cfg 两次运行摘要相同」的对照（跑到之前该条保持 unknown）。**2026-09-20 真跑已证**：`Lizard-Rough-v14 --num_envs 32 --max_iterations 1 --seed 123` 两次 ⇒ `[TERRAIN_GEOMETRY] cells=200 hashed=200 anomalies=0 digest=sha256:b74cb2278a3396aad01ce493b53e8bf9` **逐位相同**；反证臂 `--seed 7` ⇒ `sha256:0b163edff4f2a75d4a39a6943c16531c` **不同**（排除"摘要对几何不敏感"这个廉价解释）。前两跑为干净树、反证臂走 `RL_ALLOW_DIRTY_TREE`（另一开发者正在改 `ACCEPTANCE.md`，理由已落其 T0）。eval 侧：v3 零动作 smoke 两次独立调用同为 `sha256:1fc13fa2…`（9 格）。它覆盖不了完整网格的难度抖动/拼接/边界/缓存路径，`_CFG_BY_VERSION:48` 也只到 v5（v15 的 grid 归 #21）⇒ **不得据此关闭本项**。**⑤b 实际几何证据（采集件已装 2026-09-18）**：须在真实生成路径（`TerrainGenerator._get_terrain_mesh` 产物）采集，先定义数组类型/字节序/形状/摘要范围，归档 `rl_exp/archive/<run_id>/terrain/`，再由 `rebuild.py` 核验；采集件：`terrain_split_probe._add_sub_terrain` 在生成器交出 mesh 的那一处逐格算 `geometry_digest(mesh, origin)`（数组类型/字节序/形状/摘要范围 = `rl_exp/tasks/terrain_geometry.geometry_digest` 的定义），每次生成打印一行 `[TERRAIN_GEOMETRY] cells=… anomalies=… digest=sha256:…`，`eval.py` 把它写进 `eval.json.suite.geometry_digest`；**（原状态）归档 `rl_exp/archive/<run_id>/terrain/` 与 `rebuild.py` 核验未接通**（当时只装采集点，未跑真实 run）。**2026-09-20 已接通**：采集件逐格加 `relief`（`foot_relief` = 0.5 m 脚板格内高差），`eval.py` 每次运行写 `<run_dir>/terrain/geometry.json`（**归档位置改在运行目录**：这块证据由 suite 名 + seed 即可再生、随记录入库即为"取回得来"，再往 `rl_exp/archive/` 抄一份是重复；该目录仍是"rev 取不回的内容"的落点，规矩不变）、`rebuild.py` 取材把它收进材料并逐文件核摘要，**"地形产物一致"由再生判定**（离线闸按归档自述的 suite+seed 重建、逐格比摘要；`rebuild.py` 负责材料完整性）——这是对 ⑤b 原文"由 `rebuild.py` 核验"的**替代**（与归档位置一起记在 `HARNESS.md` 挂账 #4，**待用户确认**），理由：再生判的是"地面本身对不对"，材料摘要只判"抄本没被改"，而重建评级 = 本项 ①，仍单独排期。**顶点法的天花板**：只对"最大面 ≤ 脚板格"的网格成立（hfield 面 0.14–0.28 m ✓；楼梯/gap/平面是 13–22 m 巨面 ⇒ 记 `null`，实测过 0.87 m 的假起伏），升级路径 = 射线采样，写在 `foot_relief` docstring。实测（v3 零动作 smoke 归档）：`rough_a 0.030 / rough_b 0.065`（v1 同位置常值 `0.0` 作参照），`flat`/楼梯/gap 全 `null`。**历史 run 未采到的证据保持 unknown，不得事后生成后补认**。两条声明在接通前继续标未知、不得冒充通过。**实测新发现 2（评测侧，2026-09-18 已修）**：`ablation_harness/suites.py` 的 `rough_a`/`rough_b` **其实不是粗糙地形** —— 单值 `noise_range=(0.05,0.05)` / `(0.15,0.15)` 使 `height_range` 只剩一个元素，`np.random.choice` 退化成常量 ⇒ 实测 p2p 恰等于 0.05 / 0.15（均匀抬升平板，无起伏）；且 `suites.py:18`「seed 钉住 RNG 流」机制上不成立（seed 进的是 `TerrainGenerator` 的 local rng，hf 函数抽**全局** numpy 流），套件的可重复性来自「范围塌缩」这条巧合。后果：**套件里没有真正的地形粗糙列**，rough 两列的 completion 测的是"走上抬升平板"。**已修**：套件升 `lizard_suite_v2`（rough_a `noise_range=(0.02,0.06)`/`noise_step=0.01`、rough_b `(0.08,0.16)`/`0.02`、`downsampled_scale=0.5` ⇒ 真起伏），协议新建 `ablation_harness/protocols/locomotion_eval_v3.yaml`（与 v2 只差 `name`/`version`/`suite` 三键，由测试断言看守），`eval.py` 默认协议改 v3 并把每次运行的几何摘要写进记录；v2 冻结封存，**v1/v2 结果不得与 v3 混表**（v2 的 rough 两列测的不是粗糙地形）。反证 `tools/verify/test_terrain_geometry.py`：`relief_p95` v2 > 0.02 / v1 == 0.0、同 seed 重复摘要一致而抽掉播种则三次三样。**进度与实测证据**（R1 拒采实例、首个演练 run 的归档清单）见 `ACCEPTANCE.md` §1.2b 追加说明 | 🟡 仓内 git 归档（首个 run 已入仓） |
| 21 | **v15 起草（提案态，2026-09-16 用户拍板）**：地形课程换 **joint SIR**（"用 SIR 课程，不要 v14 的地形课程"），base = v14，obs/动作/奖励/终止/DR/资产逐字段零差异。**v15.3（2026-09-16）重规划**：保留联合 SIR，改**评分与冷启动**——逐帧达标换 yaw 帧跟踪误差 `‖vel_yaw_xy − cmd_xy‖ ≤ track_tol_mps`（用实际含 jitter 的指令）、`Tr` 分母改固定观察窗口 `W`（提前失败记未达标）、冷启动改显式 `anchor_combo` + 全部最低桶、每块只做一次局部扩展；**取消**硬解锁 / `anchor_share` 85% 锚集 / 掌握判据；机制评审 5 条的修复已落共享实现（v11/v12 golden 随之重生成）。方案 SSOT = `v15\PLAN.md`（已起草：PLAN/NOTES/base.json/yaml 段 + 血统边），**代码件待实施**（V15 env cfg + PLAY、注册 `Lizard-Rough-v15`/`-Play-v15`、runner cfg、`SMOKE_SPEC["v15"]` + 薄壳、`check_dr_parity` 白名单、离线套件、冻结前 `cfg_lock --update` + tag）。**2026-09-18 实施坑与分段（评审修正）**：① `components.py:233 _PARAM_GRID_SECTION = "v11"` 是写死的单常量，而 v15 的 grid 在 `params["v15"]`（`main/v15/main_params.yaml:428-429`；v12 的 params 照抄 v11 段，`main/v12/main_params.yaml:335-336`）⇒ 必须换**显式映射** `v11→v11 / v12→v11 / v15→v15`，并跑全量 golden 证 v11/v12 逐字段不变；② 清单里的 `check_dr_parity` 白名单项在声明式重构后**疑为 no-op**（`wiring_lines()` 只扫 `self.(events|rewards|terminations)`，抓不到 `curriculum.joint_sir`）⇒ 实施前先判，删项或另写；③ **装配与机制分两阶段验收**：装配 = 7 文件 + 注册 + smoke + `diff.json` + 套件条目 + tag；v15.3 机制（yaw 帧标签 / 固定窗口 `W` / `anchor_combo` / `curriculum_state` v2→v3）**四项待拍板**，尤其"共享课程类是否改变历史版本语义"须先定，**不得夹在装配里顺手做**。**依赖/前置门三条**：① joint SIR 线**从未真训**（v11 仅 6-iter 冒烟、v12 无 run）⇒ 本版为该课程线首跑，v11/v12 不作基线；② 用户意图 = **本版在老框架训练的同时把项目迁到新框架**（`ARCH_PLAN.md` Step 2）⇒ 开训前**必须打 tag**、训练进程**不得重启/续训**、训练结束前**不得 `cfg_lock --update`**（违反任一条，本次 run 的"可重建"声明作废）；③ 迁移后必须保留旧任务 id 映射才能评 v15 ckpt（Step 2.1 不变量）。命令口径变化（离散步点 vs 连续 U(0,3)）⇒ v15 跟踪数字不得与 v5–v14 同表 | 🟡 起草中（实施待启动） |
| 26 | **Step 3.4 蒸馏与导出校验 —— 本轮不执行（登记，非排期承诺）**：① 导出前协议校验（`teacher_networks.py:176-243` 的 flat/分段与 ONNX/JIT 路径）；② 蒸馏数据 manifest ＋分片哈希（Phase 2 建）。P05/P06/P07 标"未执行"，不得通过。**现存冲突记敞口**：冻结 yaml 的 `obs_layout` 与协议声明**不同形**（yaml 写 `joint_pos_rel`，代码 term 是 `joint_pos`），它是 UE 侧契约，本轮不动导出。另：**几何一致性**（"地形产物一致"）须归档并核验实际 mesh/heightfield，本轮不执行 ⇒ 记未知（与 #18 ② 同一条腿；原记 "#18 ③" 为笔误）。**2026-09-18 定性**：只有 ⑤b 在真实生成路径采到实际产物并归档后，本项才具备判定条件，⑤a 的离线预览摘要**不能**替代 ⇒ ⑤b 落地前本项保持"未执行／不得通过" | 🟠 待排期（未执行） |
| 27 | **记录体系的两条结构性敞口（2026-09-17 评审提出）**：① **两套记录词汇并存** —— 训练侧 `rl_exp/tools/runrecord/manifest.py` 与评测侧 `ablation_harness/record.py` 记同一批事实、各有一套命名（`obs_protocol_digest` vs `obs_layout_digest`；资产锁两侧各算一遍），漂移只是时间问题；收敛路径 = 抽出共享的"绑定面 + 三态读侧"最小公共层，两侧各自保留自己的入场/落点。**2026-09-18 摸清后收窄**：共享面**已半存在**（eval 直接调 `manifest.protocol_ref`/`manifest.asset_digest`，`eval.py:199/212`），真正重复的是**原语**：① `sha256_file`（`provenance.py` vs `record.file_sha256`，**前缀不同**：裸 hex vs `sha256:`）、② git 身份（`prov.rev` = `rev-parse HEAD`[:12] vs eval `_git_rev` = `--short`≈7 ⇒ **同一 commit 在两份记录里是两个字符串**）、③ rsl_rl 身份（editable 时训练记 source rev、eval 记发行版版本号 ⇒ 不可对账）、④ 资产绑定口径（eval 的 `declared_digest` 退化为 lock 文件哈希，训练侧绑 `manifest_sha256`）。**已做（2026-09-18）**：重复的原语收进 `rl_exp/tools/runrecord/binding.py`（stdlib-only 一处家：`sha256_bytes`/`sha256_file`/`git_run`/`git_rev` + `REV_LENGTH`；`provenance` 保旧名转发，`check_dr_parity`/`check_golden_frozen` 的两份内联实现一并收掉），rev 口径统一为 12 字符（实测同一 commit 两侧同串；键名与记录格式版本未动，除该项外无任何已记录值变化 —— 两闸复跑为证，读数归 `ACCEPTANCE.md`），单源闸门 `check_record_bindings.py`（套件末条，1.2s；反证：把三签名之一的副本放进目录再指过去 ⇒ 非零退出且点名行号）。**③④ 也已闭（2026-09-18）**：③ eval 的 `runtime` 增 `rsl_rl_id`，由 `provenance.rsl_rl_id()` 拼写（与训练侧 golden 组合键的 `rsl_rl=` 同一个函数 ⇒ 两份记录首次可对账）；`rsl_rl_version` 保留为它自己的事实。**刻意不进 `record.ALWAYS`**：设为必需会把已落盘的 eval 记录读作"不完整"，与 `metrics.derived` 同一个判据。④ eval 的 `assets.declared_digest` 去掉"退化为 lock 文件哈希"的兜底，只认 `manifest_sha256`，缺失即 `unknown` —— 那个兜底让"没有 manifest 摘要的锁"读成了"绑定了"，且用了另一个事实的名字。闸门 `check_record_bindings.py` 相应加第 4 条签名（`f"source:…"`/`f"installed:…"` 这类**第二处身份拼写**，`.format()` 形态同判；`provenance.py` 与 `binding.py` 同为豁免家），自检里加了正/反例（含一条"另一个前缀是另一个事实"）—— 顺带被自检抓到过我自己写错的 `.format()` 匹配（模板在 `func.value` 不在 `args`）。② **单源扫描闸守"副本"不守"新规则"**：`check_terrain_split_source.py` 只认 `terrain_map` 的 epsilon 签名，新写一个**不同**的切分规则不会被抓。**原拟补法不成立（2026-09-18 实测）**：`test_component_ownership.py` 的所有权表是"谁**写**某个 scene 名"（AST 只扫 `Assign`/`setattr` + `OWNERSHIP` 叶子名），表达不了"谁**解释**某个值"这类读者断言，新规则不写任何 scene 名 ⇒ 对它是全局隐形。**改为可判定形式（已闭）**：`terrain_map.check` 把声明的列映射**回代本规则**，不一致即拒 ⇒ "一份来自别的规则、但自身自洽"的记录**不能**被消费（反证：撤掉该分支后同一用例返回 `[]`，`test_terrain_map.py` 两条新例咬住）；静态扫描的门槛与天花板已在其 docstring 写实（查副本，不查语义）。另记两条小敞口：① `--variant` **命名靠人** —— 它是"换过输入（协议/ckpt/suite/故意无锁）时另起 run 身份"的自由文本标签，追在 `run_id` 后做后缀、并在记录里留 `variant` 字段；没有机械校验它是否描述得对，也没从"检测到的替换项"反推名字（可反推的至少有 suite 替换与 ckpt 迭代）。② `record.json` 体积：实测 **88.8 KB**（无锁那份 54.7 KB），其中 `env_cfg` 快照 ≈ 40 KB 紧凑 JSON（占内容 95%，缩进后再翻倍）—— 无机械消费者 ⇒ 长期跑分会胀，升级路径 = 内容寻址快照。**挂账（未验，2026-09-18）**：③ 的新键 `runtime.rsl_rl_id` 只在**下次真跑 eval** 时才写进 `record.json` —— `eval.py` 是模块级 argparse 的脚本，离线导入会去解析 argv，所以这条改动**离线断言不了**（形状与训练侧同函数、UNKNOWN 兜底已读代码确认，但不声称"已跑过"）。下次 eval 跑完请核对：`record.json.runtime.rsl_rl_id` 与同 run 训练记录的身份**同一拼写** —— `rsl_rl_id()` 返回 `source:<rev>` / `installed:<distribution_version>`（`provenance.py:163-170`），而 `code.rsl_rl.rev` 存的是**裸 revision** ⇒ **不能直接相等**，须按训练记录的 `mode` 重建同一身份再比；若落成 `unknown`，查 `rl_exp` 是否在 `sys.path`、`rsl_rl` 是否可导入。**③ 离线补测（2026-09-18 定）**：把 `_baseline_evidence` 连 `_run_dir`（`eval.py:611-635` / `:586-588`）一起搬进 `record.py`（`args_cli` 改显式参数，`eval.py` 只留薄壳），测试补**三条异常路径**（目录不存在 / 只有 `eval.json` 的 pre-format 邻居 / 坏 JSON）+ **一条成功路径**（同 protocol、同 group 的可读基线真被读到 —— 专抓"路径拼错导致永远 unknown"）；坏 JSON 例只钉业务文案前缀（`… is unreadable (`），不锁死解析器完整报错文本。**方案（2026-09-18 评审修正后定稿，A3 → B1；A1 暂缓、A2/B2 不建议）**：① 机械账（A3）：落盘时记"相对基线的**已证实**变化类别（两个 obs 字段并成一类）+ 未证实的 binding 路径及原因 + 基线引用与当时采用的 binding 值"。**基线口径**：只取同 `protocol` + 同 `group` + **拼 variant 之前的基础 run_id**（`eval.py:586/729`；基础 id 在拼接前保留，不靠拆字符串还原），**找不到可读证据即 `unknown` 并写出原因，不去搜相似目录猜基线**（实例：`…suite-roughb016`、`…ckpt1150` 的无后缀邻居只有 `eval.json`，机械上不可比 ⇒ `unknown` 不总等于"第一次跑"）。**`differences` 不能直接映射成 substitutions**（`record.py:243` 把 unknown→已知同时放进 `differences` 与 `unproven`；legacy/不完整直接返回 unknown + 空 differences ⇒ 直接取差异键会把"证据补齐"误判成替换、把"无法判断"误报成无替换）；`substitutions: []` **只能**表示"比过且无确定替换"，不代表比较成功。新信息不进 `ALWAYS`（同 ③ 的判据）。**A1（2026-09-18 定下语义，待实施）**：只定义为"**类别声明校验**"——不承诺校验标签内容真实（写了 `ckpt1150` 无法证明是 1150 迭代）。**定案**：语法 `--variant <token>[+<token>...][-<自由文本>]`，token 取 `record.SUBSTITUTION_CATEGORY` 五类（`checkpoint`/`suite`/`assets`/`protocol`/`obs_protocol`）；重复 token 拒、解析不出任何 token 拒、**自由文本拒路径分隔符**（它直入 run 目录名）；**语法检查做成 `record.py` 的纯函数**，`eval.py` 在 `parse_args()` 之后、`AppLauncher()` 之前调用（秒级死且离线可测）。一致性规则：**已证实变化类别必须包含在声明中；多写的类别允许存在，但不得被解释为已证实**（记录里显式区分 `claimed` 与 `confirmed`，禁止实现成集合相等）；`comparison != "compared"` 时不做一致性判定；`--overwrite` **语法与一致性都不绕过**；一致性检查在算完 evidence 之后、rollout 之前（`eval.py:834` 与 `:838` 之间 —— 原记"前置入口 `eval.py:611`"是该函数的定义处，不是门槛本身），错误须给出基线、变化字段、缺少的类别与可用标签示例。② 体积（B1，去重收益真实：六份记录里四份 env digest 相同；已核实 **eval.json 都不含快照**，快照只在 `record.json` 的 `env_cfg`/`agent_cfg`，仓内未发现生产读侧，但外部消费者无法用仓内搜索排除）：快照本体外置为按摘要命名的共享文件，记录留摘要 + ref。**2026-09-18 修正（评审）**：`agent_cfg.clip_actions` **在 `ALWAYS` 中**（`record.py:53`）⇒ `agent_cfg` 对象**不得**缩成 `{digest, ref}`，必须保留 `clip_actions`，否则新记录被读作"不完整"；已存在的快照文件**必须校验摘要**再复用（"文件存在即跳过"会把损坏文件持续固化并复用）；`ref` 相对 **results 根**，并测"整个结果包搬移后仍可读"；本轮**不新增 `--export`**，"导出单个 run 目录须带被引用快照"落成**未来导出契约**（记入 `HARNESS.md` 记录格式节）。约束：摘要必须用 `cfg_snapshot.digest()`（**保键序**，与 `record.digest()` 的排序哈希语义不同，`cfg_snapshot.py:228`）；**快照写成功后才发布引用它的记录**，共享写不得用固定 `.tmp` 名（并发写同一快照要能过）；读侧按需解析并区分"可用 / 缺失 / 损坏或摘要不符"，缺失可回 `unknown` 但**原因必须可见**；**快照缺失不得改变原 bindings 的比较结论**；旧内联记录继续可读；**导出单个 run 目录必须带上被引用的快照**（否则搬走一个目录证据就没了）；**不改 eval.json**。**一年后最该防的故障**：基线被 `--overwrite` 改写、旧 `substitutions` 仍指同一路径 ⇒ 只存 `["suite"]` 不足以审计，必须保存**当时**的比较依据，读取时不得拿"当前基线"重新解释历史。**验收要点**：部分 unknown / legacy 基线 / 基线被覆盖 / 多项替换标签 / 旧内联读取 / 外置快照缺失与损坏 / 并发写同一快照 / **整个结果包搬移后读取** / **已存在快照摘要不符 ⇒ 不复用**。**执行顺序（2026-09-18 定）**：①②③ 离线 → ④ B1 → ⑤a 离线回归 → **一次真实运行**（同时结 ③ 的身份/标签核对与 ⑤b 实际几何采证）→ ⑥ A1 → ⑦ v15 装配与机制分阶段；⑧ 单独排期（未完成前"已验证重建"评级保留限制）。**A3 已落（2026-09-18）**：`record.substitution_evidence(candidate, baseline, baseline_ref=...)` 纯函数（离线 18 例）产出

```json
"substitutions": {"comparison": "compared", "baseline": {"run_id": "...", "path": "results/.../record.json"},
                  "reason": "", "substitutions": ["suite", "obs_protocol"],
                  "unproven": [{"path": "assets.declared_digest", "reason": "the baseline value is unknown"}],
                  "bindings": {"suite.digest": {"candidate": "...", "baseline": "..."}, "...": {}}}
```

类别 token = `checkpoint`/`suite`/`assets`/`protocol`/`obs_protocol`（两个 obs 字段并成一类）；`eval.py` 只在给了 `--variant` 时、**拼后缀前**把基础 run_id 留成值，去同 protocol + 同 group 找可读记录，找不到即 `unknown` + 原因、**不搜相似目录猜**；无 `--variant` 的基础 run **不写该键**；新键不进 `ALWAYS`。**A1（标签类别校验）与 B1（快照外置）未动（语义已于 2026-09-18 定案，见上一行挂账）**。**挂账（未验，2026-09-18）**：写侧 `rec["substitutions"] = ...` 只在真跑 eval 时落盘（与 `rsl_rl_id` 同一性质，`eval.py` 是模块级 argparse 的脚本 ⇒ 离线导入即解析 argv）；下次真跑核对：变体 run 的 `comparison`/`substitutions` 取值，以及"无后缀邻居只有 `eval.json`"的变体（`…suite-roughb016`、`…ckpt1150`）是否落成 `unknown` + `pre-format run` 原因。另：`_baseline_evidence` 的三条 reason 文案离线不可达（无自动断言），只测了 `record.substitution_evidence` 侧 —— **已修（2026-09-18，harness v1.7.3）**：`record.run_dir` + `record.baseline_evidence` 接手布局规则与三条 reason，`test_eval_record.py` 22 例（三异常 + **一条成功路径**）；反证：去掉 `run_dir` 的 group ⇒ 成功例红并报 `nothing at <path>`。**余下只有真跑核对**（口径见上一行 ③：`rsl_rl_id` 须按训练记录 `mode` 重建身份再比）。 | ✅ 两条都已闭（① 原语与 ③④ 两条漂移均收口，② 换方式已闭）；余两条小敞口（`--variant` 命名靠人、`record.json` 体积）另记 |
| 28 | **parkour 线的 `_yaw_from_quat` = baseline eval 同款缺陷（2026-09-20 同轮发现，**未改**）**：`rl_exp/tasks/parkour_mdp.py:28` 的 docstring 写 `(x, y, z, w)`，算的是 `(w, x, y, z)` 分支 ⇒ 对 xyzw 输入恒 ≈ π（实测真 yaw `[0, π/2, π]` → 返回 `[π, π, π]`，与转向无关）。`PositionCommand` 用 4 处（`command` / `_resample_command` / `_update_command` / `_update_metrics`）：目标采样 `abs_dir = base_yaw + rel_dir` 与 `heading_err` 都建在它上面 ⇒ 采到的目标方向与朝向误差都不是本意。该线已退休、**但有训练 run**（`logs/rsl_rl/lizard_parkour_climb_v1`）⇒ 其记录的含义可能受影响，按"未重跑即不可比"处理；**是否重解释该线记录待拍板**。修法与 baseline 侧同一处方（`euler_xyz_from_quat(quat)[2]`，实测口径与回归见 `baseline/v1/NOTES.md` §验收工具缺陷）；该方法已由离线守卫 `test_no_hand_rolled_quat_yaw` 的白名单**显式登记为已知坏**（不静默、可被 ponytail-debt 类扫描看见） | 🟡 待拍板（退休线，是否重解释其记录） |
