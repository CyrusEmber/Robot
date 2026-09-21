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
| 11 | **DR 放宽策略 / 续训二阶段** —— 机制与验收**不在本行复述**：续训状态层（注册表 + 命名 slot、载荷 v2、c_k 与 term 解耦、`--drop_curriculum_state` 正名、`REQUIRES_CURRICULUM_STATE` 硬失败）见 `FAMILY.md` 与 `FILEMAP.md`，验收见 `ACCEPTANCE.md` 续训节。**本行只留未兑现的两项**：① DR 放宽策略（未定案）；② 多 GPU 续训**不在保证范围**（状态只从 rank 0 写，非 0 rank 明确拒绝并记录） | 低（余两项） |
| 12 | ablation_harness 版本与待办 → `ablation_harness/HARNESS.md`（自有版本文档 SSOT，2026-09-01 拍板：仓不拆、只拆版本文档）。当前挂账：G3 剩余 `_ISAAC_ROOT` 参数化三处 → 删 `E:\IsaacLab\ablation_harness` junction | 🟡 G3 收尾 |
| 13 | v5 开训前 GUI 目视判「碎石堆无粗糙度」与 preflight `difficulty=1.0` 的数字矛盾 —— 归因：PLAY 非课程模式按 U(0,1) 采样难度，目视 tile 大概率落在低难度；训练侧按行爬坡 + 出生 level 0，前期平缓属设计内。**v5.3 起由 SIR 地形课程直接回应**（2026-09-03 拍板）：地形流量按真实成败在固定网格上再分配 ⇒ `Curriculum/terrain_levels` 判读语义反转（带内集中或爬升 = 课程在起作用）；**长期贴地不动**才需复核碎石参数 | 低（v5 训练期观察） |
| 14 | **版本表达架构未定案**（用户拍板挂账 2026-09-03）：退役条款曾写入 versioning 后撤回；候选 a) 退役降级 git tag 复现 b) 组件库（参数级 diff 写 spec 行而非新子类）c) 维持现状。约束：teacher 零家族 import 是冻结纪律，组件化不得破坏「改组件 ≠ 改历史版本语义」。**2026-09-15 起由仓根 `ARCH_PLAN.md` 承接**（候选 b 的具体化），落地进度与验收归 `ACCEPTANCE.md`；**本行只留未定案与重议触发**：连续两个纯参数级新版本，或第二家族立项 | 低（未定案） |
| 16 | v7 实施（ghost 断腿鲁棒性，方案 SSOT = `v7\PLAN.md`，用户拍板开 v7 2026-09-08）：V7 env cfg + 任务注册 `Lizard-Rough-v7` + broken_leg DR 事件（p=0.3，整腿 stiffness→0/damping→1.0/质量 ×0.001）+ `damage_flags` 4 维进 actor obs（90→94）+ 断腿 hfe/kfe 接触罚豁免（V7 子类，不改旧类）+ ablation_harness broken-leg eval suite + v8 ckpt 微调入口。前置依赖：v8 已训 | 🟡 提案 |
| 17 | v3 复现锚缺失（2026-09-11 血统闸 review 发现）：v3 已训（2026-09-01 首跑）但无 git tag，FAMILY 退休注记"v1/v3/v5 复现走 `git checkout <tag>`"对 v3 落空。补法二选一：考古训练起点 commit 补打 tag，或退休注记为 v3 改记 commit 锚（v5 先例：tag 当日撤，NOTES 记 git `e08636b`） | 🟢 低（原地复现已整体退役，需求弱；`check_version_docs.py` tag WARN 持续提示） |
| 18 | **归档位置：仓内 git 归档**（2026-09-15 用户拍板）——不可由 rev 取回的内容写 `rl_exp/archive/<run_id>/` 并随仓提交；无落点仍**硬拒采**（`rebuild.py` 硬门）。**仍未落地**：① 1.5 隔离重建的「已验证重建」评级（其必要条件的衍生改进 ⑧：`code.<source>.untracked*` 只记名字与数量、不记内容摘要 ⇒ 归档材料无法与历史那份判同源；须同时接通归档 + rebuild 校验 + 旧格式降级；**旧记录缺摘要一律 unknown，不得用当前文件补出历史真实性**）。② 「地形产物一致」**已于 2026-09-20 落地**（归档 + 再生核验）：机制与未覆盖边界见 `work/closed/2026/terrain-evidence-18b.md` 与 `work/closed/2026/terrain-suite-v2-rng.md`，两跑摘要与反证臂读数见 `ACCEPTANCE.md`（本行不复述数值）。**standing 口径**：历史 run 未采到的证据保持 unknown，不得事后生成后补认（读侧规则见 `HARNESS.md` 记录格式节） | 中（仓内 git 归档，首个 run 已入仓） |
| 21 | **v15 起草（提案态，2026-09-16 拍板）**：地形课程换 joint SIR，base = v14，obs/动作/奖励/终止/DR/资产逐字段零差异；v15.3 重规划（评分改 yaw 帧跟踪误差、`Tr` 分母改固定窗口、冷启动改显式 `anchor_combo`、每块只做一次局部扩展；**取消**硬解锁 / 85% 锚集 / 掌握判据）。**方案 SSOT = `v15/PLAN.md`**（本行不复述方案正文）；**代码件待实施**。**前置门三条**：① 该课程线从未真训（v11 仅 6-iter 冒烟、v12 无 run）⇒ v11/v12 不作基线；② 本版在老框架训练的同时项目迁新框架 ⇒ 开训前必须打 tag、训练进程不得重启或续训、训练结束前不得 `cfg_lock --update`；③ 迁移后必须保留旧任务 id 映射才能评 v15 ckpt。**待拍板 4 项**（不得夹在装配里顺手做）：yaw 帧标签 / 固定窗口 `W` / `anchor_combo` / `curriculum_state` v2 到 v3，尤其「共享课程类是否改变历史版本语义」。命令口径由离散步点改连续 U(0,3) ⇒ **v15 跟踪数字不得与 v5 到 v14 同表**。 | 中（起草中，实施待启动） |
| 26 | **Step 3.4 蒸馏与导出校验 —— 本轮不执行（登记，非排期承诺）**：① 导出前协议校验（`teacher_networks.py` 的 flat 与分段、ONNX/JIT 路径）；② 蒸馏数据 manifest 与分片哈希（Phase 2 建）。P05/P06/P07 标「未执行」，不得通过。**已知敞口**：冻结 yaml 的 `obs_layout` 与协议声明不同形（yaml 写 `joint_pos_rel`，代码 term 是 `joint_pos`），它是 UE 侧契约，本轮不动导出 | 中（待排期） |
| 27 | **记录体系的两条结构性敞口（2026-09-17 评审，2026-09-18 大部分已闭）**：① 两套记录词汇 —— 共享原语收进 `rl_exp/tools/runrecord/binding.py`（rev 统一 12 字符）、eval `runtime.rsl_rl_id` 与训练侧同函数拼写、`assets.declared_digest` 只认 `manifest_sha256`，单源闸 `check_record_bindings.py` 守副本；**读数与闭合过程见 `ACCEPTANCE.md`**。② 单源扫描闸只守「副本」不守「新规则」⇒ 改为 `terrain_map.check` 把声明列映射回代本规则（已由 `test_terrain_map.py` 咬住）。**仍未实施的两件（方案已定稿，实施前不得改口径）**：**A1 = `--variant` 语法与一致性校验** —— 语法 `--variant <token>[+<token>...][-<自由文本>]`，token 取五类 `record.SUBSTITUTION_CATEGORY`；重复 token 拒、解析不出 token 拒、自由文本拒路径分隔符；检查做成 `record.py` 纯函数，在 `parse_args()` 之后、`AppLauncher()` 之前调用；**已证实的变化类别必须包含在声明中，多写的允许存在但不得被解释为已证实**（记录里显式分 `claimed` 与 `confirmed`，禁止实现成集合相等）；`comparison != compared` 时不做一致性判定；`--overwrite` 语法与一致性都不绕过。**B1 = 快照外置** —— 按摘要命名的共享文件 + 记录留摘要与 ref（ref 相对 results 根）；`agent_cfg` 必须保留 `clip_actions`（它在 `ALWAYS` 里）；已存在的快照**必须校验摘要**再复用；读侧区分「可用 / 缺失 / 损坏或摘要不符」，缺失可回 `unknown` 但原因必须可见；**旧内联记录继续可读**；**不改 eval.json**；导出单个 run 目录必须带上被引用的快照（未来导出契约）。**一年后最该防的故障**：基线被 `--overwrite` 改写而旧 `substitutions` 仍指同一路径 ⇒ 必须保存**当时**的比较依据，读取时不得拿当前基线重新解释历史。**执行顺序**：①② 已闭 → ③ 真跑核对（已立 `work/active/record-format-live-checks.md`）→ ④ B1 → ⑤a 离线回归（已落）→ 一次真实运行 → ⑥ A1 → ⑦ v15 装配与机制分阶段 → ⑧ 单独排期。**两条小敞口**：`--variant` 命名靠人（无机械校验它描述得对，也未从检测到的替换项反推名字）；`record.json` 实测约 89 KB（`env_cfg` 快照占内容 95%）⇒ 升级路径 = 内容寻址快照。 | 中（A1/B1 待实施） |
| 28 | **parkour 线的 `_yaw_from_quat` = baseline eval 同款缺陷（2026-09-20 发现，未改）**：`rl_exp/tasks/parkour_mdp.py` 的 docstring 写 `(x, y, z, w)`，算的是 `(w, x, y, z)` 分支 ⇒ 对 xyzw 输入恒约等于 pi。`PositionCommand` 用 4 处（目标采样与 `heading_err` 都建在它上面），该线已退休但**有训练 run** ⇒ 其记录含义可能受影响，按「未重跑即不可比」处理。**是否重解释该线记录待拍板**。修法与 baseline 侧同一处方（`euler_xyz_from_quat(quat)[2]`，实测口径见 `baseline/v1/NOTES.md`）；该方法已由离线守卫的白名单显式登记为已知坏（不静默） | 中（待拍板） |
