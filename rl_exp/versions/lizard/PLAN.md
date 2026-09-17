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
> 迁新框架（`ARCH_PLAN.md` Step 2），前置门与代码件清单见挂账 #21）。上一版 2026-09-10（v10 在训——tilt 删除单变量版，判决门 = `v10\NOTES.md` 验收
> 1–5；v11 联合粒子地形课程实施完成待开训——挂账 #15 候选 a 落地，v11.1 审查
> 四修见 `v11\PLAN.md` 修订记录；断腿线占位 v9 重基 v8）。上一版 2026-09-08（v6 已训判废——倒走，骨命名与解剖学 180° 装反；开 v8
> 资产解剖学转正+全关节重命名，v8.1 r_slip ×10，已冻结待训；v7 提案挂账 #16
> 前提改指 v8 ckpt，方案 SSOT = `v7\PLAN.md`）。上一版 2026-09-03（重构为纯意图文档：现状
> 快照/Phase 1 详情/命令速查移除
> ——事实归 FAMILY，obs 契约归 OBS.md（v1 266 布局迁入），方案细节归 vN\PLAN，
> 命令归 README；备选奖励修复表保留为 §3。再上一版 2026-09-02（v4 提案：碎石地
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
| 11 | DR 放宽策略 / resume 二阶段 | ✅ 2026-09-15（ARCH_PLAN 1.3a）三线真续训落地：课程状态层改为**注册表 + 命名 slot**（`rl_exp/tasks/curriculum_state.py`，载荷 v2：header + `clock`（counter + c_k 指纹 `c0/decay/steps_per_iteration`）+ `terms` 按实际 term 名索引，slot 内带 `adapter`/`adapter_version`/`term_type`）——joint SIR（v11/v12）与**行 SIR（v5–v10、v13/v14）**同构覆盖，**c_k 时钟与 term 解耦**（v3/v4 线只存 counter），恢复前逐项核验（任务/env 数/版本/slot 集合/指纹/张量有限性与索引合法性）后才原子回填。原 v1 载荷可读（迁移为唯一 joint slot，缺证据列为未知、不以当前值补造）。**开关正名**：`--drop_curriculum_state`（旧 `--weights_only` 保留为别名 + 弃用提示，Python 入口同）；声明 `REQUIRES_CURRICULUM_STATE`（`ClassVar[bool]`）的任务在缺载荷/缺 slot/模块导入失败/保存 hook 未装时**硬失败**（不静默冷启动），PLAY 显式声明 False。**余**：① DR 放宽策略；② 多 GPU 续训不在保证范围（状态只从 rank 0 写，非 0 rank 明确拒绝并记录）。离线门 `[15]` 27/27（S01–S10 + B 层分支级/迭代边界，见 `ACCEPTANCE.md` §1.4a） | 🟢 离线通过 + **C 层真跑通过（1.4b，2026-09-15）**：3 代表任务（v14 行 SIR / v12 joint SIR / v3 c_k-only）× resume/drop 共 15 臂，观察点注入真 trainer 进程（只读包装）；回填早于首次 reset、逐 step Δcounter==1、真实更新落在块沿后第一个带 reset 的 step（247/250）且 `next_eval` 精确 +240、84 次 optimizer 更新与重存 ckpt 前进、c_k 连续不回热、drop 冷启动且两臂对同一 ckpt 的 actor/critic/optimizer 逐项相等（关掉 1.2b 遗留的未知项）。**执行中发现并修复** `_check_eval_clock` 把"挂起块沿"误判为不一致（`next_eval_step=960` 在 counter=960 时硬拒恢复）——新规则接受挂起/已到期，拒绝落后整块。记录见 `ACCEPTANCE.md` §1.4b |
| 12 | ablation_harness 版本与待办 → `ablation_harness/HARNESS.md`（自有版本文档 SSOT，2026-09-01 拍板：仓不拆、只拆版本文档）。当前挂账：G3 剩余 `_ISAAC_ROOT` 参数化三处 → 删 `E:\IsaacLab\ablation_harness` junction | 🟡 G3 收尾 |
| 13 | v5 开训前 GUI 目视判读"碎石堆无粗糙度"，与 preflight difficulty=1.0 数字矛盾（random_rough relief p95 0.325 m @ 满档）。归因假设：PLAY 非课程模式难度 U(0,1) 随机采样，所视 tile 大概率低难度（难度 d 振幅 ≈ 0.10+0.25d m，d=0.2 时 ≈0.15 m，视觉为平缓土堆）；训练侧 curriculum=True 按行爬坡 + 出生 level 0，前期平缓是设计内。**v5.3 起由 SIR 地形课程直接回应**（用户拍板 2026-09-03）：训练流量按真实成败在固定网格上再分配（带 [0.5,0.9] 重采样），不再依赖目视——`Curriculum/terrain_levels` 判读语义反转：带内集中/爬升 = 课程在起作用（分布随能力上移是设计内），**长期贴地不动**才需复核碎石参数；二次目视用 `_tmp_terrain_previews\v5_*.png`（difficulty=1.0 渲染） | 🟡 v5 训练期观察 |
| 14 | 版本表达架构未定案：任务注册表与 teacher V 子类只增不减（现 14 注册 + V1..V5 常驻），退役条款曾写入 versioning 后撤回（commit d642ce9）。候选方向：a) 退役降级 git tag 复现 b) 组件库（地形/reward/obs spec 表化，参数级 diff 写 spec 行而非新子类）c) 维持现状。约束：teacher 零家族 import 是冻结纪律，组件化不得破坏"改组件≠改历史版本语义"。触发再议：连续两个纯参数级新版本，或第二家族立项。**2026-09-15 起本项由仓根 `ARCH_PLAN.md` 承接**（候选方向 b 的具体化）：1.0/1.1a/1.1b/1.2a 已落地，闸门入离线套件 `[21]`–`[27]`（`[27]` = 1.5a 恢复演练工具：取材严格拒采 + 来源断言 + 缺件负测试 + "只换配置不算演练"）；1.2b 运行时验收待真跑 | 🟢 未定案（用户拍板挂账 2026-09-03） |
| 15 | SIR 课程判据 v6 候选（v5.4 弃案存档）：v5 冷启动若长期停滞——flat 集中后课程不动、rough 各行 p̂ 全带下、`Curriculum/terrain_levels` 长期钉低位（诊断信号）——则 v6 升测量判据。候选优先级：a) **逐步 Tr**（逐状态转移期望，贴论文原文，带信号从第一块就有）b) **v5.4 进度分制**（位移线性 × 存活占比 + 带下线性权重，代码保全 git `3ef2aa0`，含单测 10/10 + 冷启动梯度回归，可直接复活）。约束：v5 训练期不动判据（归因隔离，用户拍板 2026-09-03），诊断数据记入 v5 NOTES 结果回填。**✅ 候选 a 由 v11 落地（2026-09-10）**：联合粒子 SIR 逐步 Tr（Eq.2/3/7，口径反转记录见 `v11\PLAN.md` §3/§9）；v5 旧二值代理类冻结不改 | ✅ 结案 |
| 16 | v7 实施（ghost 断腿鲁棒性，方案 SSOT = `v7\PLAN.md`，用户拍板开 v7 2026-09-08）：V7 env cfg + 任务注册 `Lizard-Rough-v7` + broken_leg DR 事件（p=0.3，整腿 stiffness→0/damping→1.0/质量 ×0.001）+ `damage_flags` 4 维进 actor obs（90→94）+ 断腿 hfe/kfe 接触罚豁免（V7 子类，不改旧类）+ ablation_harness broken-leg eval suite + v8 ckpt 微调入口。前置依赖：v8 已训 | 🟡 提案 |
| 17 | v3 复现锚缺失（2026-09-11 血统闸 review 发现）：v3 已训（2026-09-01 首跑）但无 git tag，FAMILY 退休注记"v1/v3/v5 复现走 `git checkout <tag>`"对 v3 落空。补法二选一：考古训练起点 commit 补打 tag，或退休注记为 v3 改记 commit 锚（v5 先例：tag 当日撤，NOTES 记 git `e08636b`） | 🟢 低（原地复现已整体退役，需求弱；`check_version_docs.py` tag WARN 持续提示） |
| 18 | **归档位置未定 → 用户拍板"先不归档"（2026-09-15，走 c）**：`ARCH_PLAN.md` §0.2 的两条腿（哈希证明"是不是同一份"／归档地址证明"能不能找回来"）目前只有前一条。因此下列声明**一律标未知，不得冒充通过**：① 1.5 隔离重建的"已验证重建"评级；② 未跟踪源码归档（`run_manifest.json` 已记 `untracked_requires_archive` + 文件名清单，内容无处可取）；③ 3.3 的"地形产物一致"（实际 mesh/heightfield 无归档即证据不足）。**触发落地**：第一次需要"已验证重建"评级、或第一次要声明地形产物一致时，必须先定归档位置（NAS / 对象存储 / 工单附件三选一）。**触发条件已到（2026-09-15）→ 当日改判为"仓内 git 归档"（用户拍板）**：演练取材把不可由 rev 取回的内容（脏树 diff + 代码根内未跟踪文件）写入 `rl_exp/archive/<run_id>/` 并随仓提交——小文件进 Git 即"找回得来"，不另建 NAS/对象存储/工单附件；无落点仍**硬拒采**（实测 R1 被拒：`cc25f24b` ≠ 现树 `13aee682`，`spider/` 无落点）。现状：首个演练 run（`2026-09-15_19-08-50`）的归档已生成并**入仓提交**（`rl_exp/archive/<run_id>/`：两份 diff + 未跟踪 `spider/` 4 个 `.py`，逐文件摘要见 `ACCEPTANCE.md` 1.2b 追加说明）；①③ 两条声明仍待各自演练/举证。**衍生改进项（R4 收口暴露）**：`code.<source>.untracked*` 只记名字/数量/标志、**不记内容摘要**，故归档材料永远无法与历史那一份判"同一份"（R1 的 R4 项因此只能保持未知）；改进 = 记未跟踪文件逐文件内容摘要（改动面 `provenance.py` + 记录格式版本），待排期 | 🟡 已改判：仓内 git 归档（2026-09-15），首个 run 归档已提交 |
| 19 | **fork 树里的 DR 改动会静默改实验**（2026-09-15 F1 汇总复核发现）：IsaacLab 树 `velocity_env_cfg.py` 的本地改动分两半——**值**半边（摩擦 `[0.4,1.2]/[0.3,1.0]`）被本仓覆盖（`lizard_params.yaml:141-142`，三处 cfg 显式赋值），**模式与节拍**半边（`base_external_force_torque.mode=interval` 及 `interval_range_s`、`push_robot.interval_range_s`）**未被覆盖 ⇒ 继承进 lizard**，golden 里可见该形状。后果：任何新 run 的 DR 都由这份未提交的 fork 树内容决定，改它等于改实验，目前**只有 golden 差异能抓到**（正面看：golden 承重；负面看：fork 树无痕改动无独立闸门）。建议二选一：把这三处 DR 语义**收编进本仓参数**（走配方升版），或在 `fork_patches\local_tree_extras.patch` 处标明"包含实验语义改动，改它须走 golden 复核" | 🔴 中 |
| 20 | **`isaaclab.bat` 被清空 + 树根出现未跟踪 `python` 文件**（2026-09-15 影响审查时发现）：`isaaclab.bat` 从 49 行被改成空文件（`local_tree_extras.patch` 已钉住该状态），树根另有未跟踪的 `python` 文件，疑为误覆盖；训练用 `python scripts\…` 直调，故不影响运行，但属"树状态异常"且会被记进每个 run 的框架来源。建议：确认 `python` 文件用途后删掉或提交，并把 `isaaclab.bat` 恢复或明确弃用 | 🟢 低 |
| 21 | **v15 起草（提案态，2026-09-16 用户拍板）**：地形课程换 **joint SIR**（"用 SIR 课程，不要 v14 的地形课程"），base = v14，obs/动作/奖励/终止/DR/资产逐字段零差异。**v15.3（2026-09-16）重规划**：保留联合 SIR，改**评分与冷启动**——逐帧达标换 yaw 帧跟踪误差 `‖vel_yaw_xy − cmd_xy‖ ≤ track_tol_mps`（用实际含 jitter 的指令）、`Tr` 分母改固定观察窗口 `W`（提前失败记未达标）、冷启动改显式 `anchor_combo` + 全部最低桶、每块只做一次局部扩展；**取消**硬解锁 / `anchor_share` 85% 锚集 / 掌握判据；机制评审 5 条的修复已落共享实现（v11/v12 golden 随之重生成）。方案 SSOT = `v15\PLAN.md`（已起草：PLAN/NOTES/base.json/yaml 段 + 血统边），**代码件待实施**（V15 env cfg + PLAY、注册 `Lizard-Rough-v15`/`-Play-v15`、runner cfg、`SMOKE_SPEC["v15"]` + 薄壳、`check_dr_parity` 白名单、离线套件、冻结前 `cfg_lock --update` + tag）。**依赖/前置门三条**：① joint SIR 线**从未真训**（v11 仅 6-iter 冒烟、v12 无 run）⇒ 本版为该课程线首跑，v11/v12 不作基线；② 用户意图 = **本版在老框架训练的同时把项目迁到新框架**（`ARCH_PLAN.md` Step 2）⇒ 开训前**必须打 tag**、训练进程**不得重启/续训**、训练结束前**不得 `cfg_lock --update`**（违反任一条，本次 run 的"可重建"声明作废）；③ 迁移后必须保留旧任务 id 映射才能评 v15 ckpt（Step 2.1 不变量）。命令口径变化（离散步点 vs 连续 U(0,3)）⇒ v15 跟踪数字不得与 v5–v14 同表 | 🟡 起草中（实施待启动） |
| 22 | **版本类体删除 + `[41]` 过渡闸门显式退役**（C2 翻表后的收尾，2026-09-17 起）：注册表已切到 `recipe_tasks` 的 26 个生成类 ⇒ 版本类**运行期已无人引用**。**依赖面（实测，不是"删 body"）**：① **冻结 golden 记类名**——`main\cfg_lock.json` 26 处 + `baseline\cfg_lock.json` 2 处 `env_cfg_class: rl_exp.tasks.teacher_env_cfg:<Class>` ⇒ 删类即令锁指向不存在的类，而锁**正是硬 A 的比较对象**；② 约 12 个闸门/测试**按名构造**版本类（`check_obs_layout` 10 个、`check_reward_v13` 5、`check_terminations_v14` 4、`check_joint_layout`、`teacher_smoke`、`baseline_probe`、`test_cfg_snapshot`、`test_configclass_fields_gate`、`test_resume_state`、`test_run_manifest`、`test_recipe_map_gate` 期望串）；③ `direction_probe`/`play_fast_task` **继承**版本类；④ 文档教"新建版本类"（`FAMILY.md` 26 行列、各版本 NOTES/PLAN、`v15\PLAN.md`）；⑤ `[41]` 过渡闸门按**发现**取被替换类，删净后必然红 ⇒ 必须显式退役（不是跳过）。**步骤（顺序不可换）**：(1) 先把上述闸门/测试的解析源改到 `recipe_tasks`（此步后套件仍全绿）；(2) 定 golden 的 `env_cfg_class` 字段命运——(a) 重锚锁 + `--reason`（动硬 A 比较对象，需单独验收）或 (b) 该字段改记「行/配方键」（更贴近它现在的角色，摘要变一次但要审）；(3) 删类体 + 同步文档口径（加版本 = 加元素 + 表行）；(4) `[41]` 过渡闸门显式退役 + 复跑全套。**验收/反证**：套件全绿含 golden；26 个任务构造出的 cfg 与重锚前逐字段一致（证"删的是类不是行为"）；反证：临时删一个元素 ⇒ 硬 A 必红。**风险**：唯一会动冻结工件的一项 ⇒ 不与任何批次混提交；与 B 侧节奏强耦合 | 🔴 中（动冻结工件） |
| 23 | **L03 真跑臂：缺课程状态 resume 必须硬拒**（C4 剩余入口侧，2026-09-17 起）：离线半边已有（`test_missing_state_hard_aborts_and_weights_only_opts_out`），缺真进程证据。**方案（自足）**：窗口内跑 v14 短训得到带状态 ckpt → 复制并剥掉 `infos[STATE_KEY]`（原件不动）→ `--resume` 指向它 ⇒ 期望**非零退出 + 硬拒**（而非 WARN 冷启动），T1 的 `resume.source` 指向该文件（生命周期证据里的 `source_checkpoint` 字段已随 2026-09-17 收缩删除，源由 T1 负责记录）、`declaration_problems` 记缺状态；同一 ckpt 加 `--drop_curriculum_state` ⇒ 放行 + 记"显式降级"。**落点**：`lifecycle_entry_run.py` 新增 `--track resume` 档（判据同 `trainer` 档：退出码 2 + T0 拒绝记录 + `--verify` 不判损坏）；离线不可替代。**反证**：换成带状态的 ckpt ⇒ 同一命令必须成功（证红来自"缺状态"而非命令写错） | 🟢 低（要真跑窗口） |
| 24 | **硬 B 覆盖面：agent（PPO）侧 + main 线差异声明**（2026-09-17 起，**同日已结案**）：agent 侧进清单（`baseline\v1\diff.json` 的 `agent` 段 + `hard_b()` 检查；ACCEPTANCE 里"硬 B 只覆盖 env cfg"一句已由 B4 节作废注记更正）。**main 线差异声明已补齐**：口径取 **B 谱系**，且**不由声明选**——`base.json` 有母版 ⇒ 对 `build(母版)`，root ⇒ 对 stock（本行原写的"A/B 二选一"当场被这条规则取代）。现存 **12 份 `diff.json`**：`main\v2..v14` 共 11 份（format 4，按作者集合分组：元素集 / `components.X` / `wiring`）+ `baseline\v1` 1 份；`main\v1` **刻意无声明**（母版 `v0` 无配方声明 ⇒ 谱系读数不可得，`[41]` 打印 `no difference declaration (hard A only): ['v1']` 而不是静默跳过），`v0/v7/v9` 不在链上。`EXPECTED_DIFFS` 逐条钉数（76+6+59+6+46+4+2+2+75+40+3+3=**322**），`params_version` 按名过滤为身份字段而非差异。落地 commit **`bfee543`**（闸门 + 11 份声明 + 格式 4 重排；记录见 ACCEPTANCE §B4 "main 线 12 条配方的差异声明"）。**本次独立复核**：`[41]` 单跑 `RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 322 declared difference(s) against their own base)`；反证重打一次（v10 的 `terminations.tilt` 改成不存在的路径）⇒ 三个检测器同报「未声明改动 / 声明已不生效 / 组件不拥有该路径名字」，原样回滚复绿 ⇒ **"只有 v14（1/12）"与"main 线没有差异声明"两条旧读数均过时**。硬 A（与 golden 逐字段一致，证"没漂"）与硬 B（与母版差异恰好等于声明，证"被声明"）互不可替，各自有反证。**残留（ACCEPTANCE §B4 边界已写）**：组件归属是"名字级"的（一条路径里两个组件各拥有一个名字时点名任一个都过 ⇒ 最软处）；路径是派生的、生成器用完即删 ⇒ 派生错误会同时落在文件与闸门两侧，独立边界只剩硬 A | ✅ 结案（2026-09-17） |
| 25 | **两条策略反转（2026-09-17，用户拍板"都是有意的"）→ 文档口径待同步**：① **退休线放行开关撤销**：`--allow_retired_resume` 从契约与补丁中移除，`recipe_lifecycle.judge(operation, status)` 只看状态 ⇒ **退休线一律拒新训与续训**，无豁免（旧文字"必须同时指定 resume 并解析到有效源 checkpoint 才豁免"作废）；② **manifest 不可用即硬拒**：fork 补丁的 `ImportError` 分支从 WARN 改 `[FATAL] … refusing to launch unrecorded` + `os._exit(2)` ⇒ 1.2a 的"记录绝不阻断训练"约定被**有意反转**（无 `rl_exp` 的树不能开训）。**待同步的旧口径**：`ARCH_PLAN.md:304`、`:364`（仍写放行开关为契约一部分）、`:160`（只写课程模块导入失败，未写 manifest 硬拒）；`ACCEPTANCE` 的 C1/C3 段落提到放行开关与公告时钟（**建议追加**说明而非改写历史）。代码侧已在工作区落地（含 `lifecycle.py` 瘦身、parkour 真退休线当入口侧 fixture、`lifecycle_entry_fixture.py` 删除）；**`[1]` 重钉前不得开训**（存档被改一半时 `setup.bat` 会静默漏打 hunk） | 🔴 中（文档口径未同步） |
| 26 | **Step 3.4 蒸馏与导出校验 —— 本轮不执行（登记，非排期承诺）**：① 导出前协议校验（`teacher_networks.py:176-243` 的 flat/分段与 ONNX/JIT 路径）；② 蒸馏数据 manifest ＋分片哈希（Phase 2 建）。P05/P06/P07 标"未执行"，不得通过。**现存冲突记敞口**：冻结 yaml 的 `obs_layout` 与协议声明**不同形**（yaml 写 `joint_pos_rel`，代码 term 是 `joint_pos`），它是 UE 侧契约，本轮不动导出。另：**几何一致性**（"地形产物一致"）须归档并核验实际 mesh/heightfield，本轮不执行 ⇒ 记未知（与 #18 ③ 同一条腿） | 🟠 待排期（未执行） |
