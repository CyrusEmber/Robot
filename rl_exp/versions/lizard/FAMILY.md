# Lizard 训练家族总文档

> 一个版本 = 一代训练配方（参数冻结副本 + 版本文档 + 训练记录）。代码共享继承，
> 参数严格按版本隔离：跑 v1 只读 `versions/lizard/v1/lizard_params.yaml`，v2 读 v2 的，
> 开发态 `lizard_params.yaml` 的修改永远不影响已冻结版本。
> 训练计划/挂账见 [PLAN.md](PLAN.md)；评测协议见 ablation_harness 与
> skill `isaaclab-eval-harness`。

## 当前状态

- 活跃冻结版本: **v2**（2026-08-31，特权 obs 论文对齐补全，266 → 308 维；
  yaml 与 v1 逐字相同，纯代码级变更。v0 未训练 = 全量 DR 对照存档；
  v1 已训练 14000 iters 并出评测分，2026-09-01 回填）
- **v3: 首跑完成，结果待回填**（2026-09-01 启动，2048 env × 4999 iter；
  `versions/lizard/v3/PLAN.md` v3.6.2：三编码器 + 脚环扫描（208 维 extero）+
  tilt/r_fc/c_k/DR-reset 趴窝修复包 + v3.6 回放诊断三修。首跑受 v3.6.2 gate bug
  影响全程等效 stage 0（速度档未上探），修复后下一跑生效；方案细节以版本 PLAN
  为 SSOT，本行只记状态）
- **v4: 提案（已批准开工，未训练未冻结）**（2026-09-02）：碎石地重定标——实测脚掌
  0.46×0.51 m（v3.6 误用 kfe→foot 骨长 0.131 定标），random_rough 间距
  0.3→0.5 m（≥掌宽）+ 噪声 (0.10,0.35)/step 0.02；v3.6.1 collision stack
  2**28 补丁删除回 stock。**启动前警示：先看地形**（三步见 v4/NOTES.md）。
  启动前可 v4.M 修订；**训练启动时冻结 + 打 tag `lizard-v4`**
- teacher 训练: 待启动（PLAN 挂账 #3，v2）
- 开发态 yaml: `lizard_params.yaml`（家族活实验用，改动不追溯）
- 布局（2026-09-01 迁移）: 包名 `rl_exp`（家族无关），冻结配方按家族分层
  `versions/lizard/vN/`；代码只在 git 仓，IsaacLab 根常驻 1 行注册 shim

## 任务注册表

| 任务 id | env cfg | 参数来源 | 说明 |
|---|---|---|---|
| Lizard-Velocity-Flat-v0 | `LizardFlatEnvCfg` | 开发态 | 家族平地基座（活实验） |
| Lizard-Velocity-Flat-Play-v0 | `LizardFlatEnvCfg_PLAY` | 开发态 | 同上，回放 |
| Lizard-Velocity-Curriculum-Flat-v0 | `LizardCurriculumFlatEnvCfg` | 开发态 | 三课程平地变体 |
| Lizard-Velocity-Curriculum-Flat-Play-v0 | `LizardCurriculumFlatEnvCfg_PLAY` | 开发态 | 同上，回放 |
| Lizard-Velocity-Rough-v0 | `LizardRoughEnvCfg` | 开发态 | 家族粗糙地形（活实验） |
| Lizard-Velocity-Rough-Play-v0 | `LizardRoughEnvCfg_PLAY` | 开发态 | 同上，回放 |
| Lizard-Velocity-Curriculum-Rough-v0 | `LizardCurriculumRoughEnvCfg` | 开发态 | 三课程粗糙变体 |
| Lizard-Velocity-Curriculum-Rough-Play-v0 | `LizardCurriculumRoughEnvCfg_PLAY` | 开发态 | 同上，回放 |
| **Lizard-Rough-v2** | `LizardRoughTeacherEnvCfg_V2` | **versions/lizard/v2（冻结）** | teacher Phase 1（特权 actor） |
| Lizard-Rough-Play-v2 | `LizardRoughTeacherEnvCfg_V2_PLAY` | **versions/lizard/v2（冻结）** | teacher 回放 |
| Lizard-Rough-v1 | `LizardRoughTeacherEnvCfg_V1` | versions/lizard/v1（冻结） | v1 配方复现入口（obs 266） |
| Lizard-Rough-Play-v1 | `LizardRoughTeacherEnvCfg_V1_PLAY` | versions/lizard/v1（冻结） | v1 配方回放 |
| **Lizard-Rough-v3** | `LizardRoughTeacherEnvCfg_V3` | **versions/lizard/v3（冻结）** | teacher 论文对齐版（obs 三组 90/208/83，装配完成待训练） |
| Lizard-Rough-Play-v3 | `LizardRoughTeacherEnvCfg_V3_PLAY` | **versions/lizard/v3（冻结）** | v3 回放 |
| **Lizard-Rough-v4** | `LizardRoughTeacherEnvCfg_V4` | versions/lizard/v4（**提案，未冻结**——训练启动时冻结） | 碎石地重定标（obs 同 v3 三组 90/208/83；纯地形+物理缓冲区变更，spec 不变） |
| Lizard-Rough-Play-v4 | `LizardRoughTeacherEnvCfg_V4_PLAY` | versions/lizard/v4（**提案，未冻结**——训练启动时冻结） | v4 回放 |
| **Lizard-Rough-v5** | `LizardRoughTeacherEnvCfg_V5` | versions/lizard/v5（**冻结**，asset_lock 齐） | 反趴窝奖励包（r_fc 符号 + r_slip + 肚皮受力罚 + EP 线性跟踪；命令 (0,3) 无速度课程；obs 同 v3 三组 90/208/83，spec 不变） |
| Lizard-Rough-Play-v5 | `LizardRoughTeacherEnvCfg_V5_PLAY` | versions/lizard/v5（**冻结**，asset_lock 齐） | v5 回放 |

注：teacher 任务 id 与配方版本同步，且**全部常驻注册**——旧版本不会因代码
演进而失复现（机制见下节"版本差异结构"）。`Lizard-Rough-v0` 无任务 id
（未训练存档，复现走 git 历史）。家族任务 id 的 `-v0` 是 gym API 版本后缀，
与配方版本无关。

## Teacher 特权 obs 布局（v2，本文档为 SSOT）

teacher（`Lizard-Rough-v2`）policy obs 共 **308 维**，拼接顺序：

| 段 | 维度 | 来源 | 论文对应 |
|---|---|---|---|
| proprio（带噪） | 90 | lin_vel 3 + ang_vel 3 + gravity 3 + cmd 3 + jpos 26 + jvel 26 + last_action 26 | Proprioception（论文 133 维含历史/CPG，我们无历史——蒸馏时 student 侧补） |
| height_scan（干净） | 135 | height_scanner 15×9 网格 | Exteroception（论文为每脚环形 52 点；v2 沿用 stock 网格，v3 已对齐脚环） |
| **存量偏差 ①** 真值速度 | 6 | `base_lin_vel_true` / `base_ang_vel_true` | ⚠️ 结构性超集：论文 body velocity 本就是仿真真值、直接进 proprio——我们是"带噪 + 真值"双份；保留决策 B |
| contact states | 4 | `foot_contact_bools` | 论文 contact states ✓ |
| airtime | 4 | `feet_air_time` | 论文 airtime ✓ |
| **存量偏差 ②** 逐 body 质量 | 27 | `body_mass_truth` | ⚠️ 论文无（RMA/Lee 系特权）；保留决策 B |
| contact forces | 12 | `foot_contact_forces`（世界系力矢量） | 论文 contact forces ✓（v2 新增） |
| contact normals | 12 | `FootContactNormalsTerm`（每脚垂直射线取地形法线，世界系） | 论文 contact normals ✓（v2 新增） |
| friction coefficients | 4 | `foot_friction_truth`（每脚静态摩擦，材质桶 per-shape） | 论文 friction ✓（v2 新增） |
| thigh/shank contact | 8 | `thigh_shank_contacts`（`*_hfe`/`*_kfe` 布尔） | 论文 thigh and shank contact ✓（v2 新增） |
| external wrench | 6 | `base_external_wrench`（`permanent_wrench_composer`，body 系） | 论文 external forces and torques ✓（v2 新增） |

**偏差声明**（决策 B，2026-08-31）：真值速度与逐 body 质量为论文外超集特权，
仅抬高 teacher 上限、不改 student 蒸馏结构；若复现保真度出问题，回归论文
血统 = 删这两 term（obs 269）重开版本。尾部切片速查（从末尾数）：
wrench 6 | thigh_shank 8 | friction 4 | normals 12 | forces 12 | mass 27 | air 4 | contact 4。

## Teacher obs 布局（v3，三组按名交付）

v3 obs 不再是单向量拼接，而是三个**命名 obs 组**（`teacher_networks.py` 的
`OBS_GROUP_CONTRACT`，rsl_rl `obs_groups` 按名取流；组内 term 顺序由
`check_obs_layout.py` 静态看守 + `teacher_smoke_v3.py` 运行时核对维数）：

| 组 | 维度 | 内容 |
|---|---|---|
| `proprio` | 90 | 与 v2 proprio 段逐项相同（带噪） |
| `extero` | 208 | 4 脚 × 52 点环形扫描，term 顺序 lf/rf/rl/rr（网络按 `[N,4,52]` reshape 的契约）；`height_scan` 相对脚高、`scan_offset=0.0`（v2 的 −0.5 是为 base 高度居中设计，脚环不适用） |
| `priv` | 83 | 与 v2 特权段逐项相同（真值速度 6 + contact 4 + air 4 + mass 27 + forces 12 + normals 12 + friction 4 + thigh_shank 8 + wrench 6） |

**v3 有意偏差声明**（细节与依据见 `versions/lizard/v3/PLAN.md` §6.5/§10 v3.3）：
真值速度/逐 body 质量超集（同 v2 决策 B）；无历史/无 CPG（蒸馏侧补）；r_fc 取
防拖脚反向语义（论文罚"抬太高"）；undesired_contacts 豁免 c_k 恒定 -1.0；
DR 课程不含 friction（`foot_friction_truth` 读回缓存只在 startup 语义有效）；
c_k 乘子挂 q̈/torque/ω_xy 三项（计划所列 feet_slide 非本仓奖励项——计划笔误，
按"不新增缺失论文项"纪律不补）；velocity tracking 保持 stock exp 形；
L_re 目标 = 干净脚环 208 + l_priv 24（论文重建原始特权态 s_p）。

**版本差异结构（复现机制）**：`teacher_env_cfg.py` 的
`TEACHER_PRIVILEGED_SPEC`（版本 → 增量 term 集合）是代码级版本差异的唯一
真源；基类 wire 全部 term 后按 spec 剥离本版本不含的。每版本一个一行子类
（override `params_version`）+ 常驻任务 id，任意版本可从工作树直接跑。
v3 的组结构差异（三组拆分/脚环/奖励/DR）全部封装在 `LizardRoughTeacherEnvCfg_V3`
子类的 `__post_init__` 后处理里——v1/v2 路径零改动。
**纪律：已发布 term 的实现永不改语义，新版本只加 term**——违反即破坏所有
旧版本复现。git tag 仍是整树快照兜底。

## 版本历史

| 版本 | 日期 | 摘要 | 文档 |
|---|---|---|---|
| v0 | 2026-08-28 | 首版冻结：72kg、DR 全套、基线奖励（回滚态）、teacher 特权 obs。未训练即被 v1 取代，存档作全量 DR 对照 | [PLAN](v0/PLAN.md) · [NOTES](v0/NOTES.md) |
| v1 | 2026-08-31 | teacher 首跑：v0 仅 DR 段全部收窄（无一归零），验证"特权+锁脊柱+轻扰动"能否出步态。已训练 14000 iters 并出评测分（09-01 回填），任务 id 常驻可复现 | [PLAN](v1/PLAN.md) · [NOTES](v1/NOTES.md) |
| v2 | 2026-08-31 | 特权 obs 论文对齐补全（+forces/normals/friction/thigh-shank/wrench 共 42 维，266→308）；yaml 与 v1 相同 | [PLAN](v2/PLAN.md) · [NOTES](v2/NOTES.md) |
| v3 | 2026-09-01 | teacher 论文对齐版（obs 三组 90/208/83=381：脚环 extero + SplitEncoderModel 三编码器；tilt 终止 + 防拖 r_fc + c_k 课程 + DR reset 化）。**首跑完成（2048 env × 4999 iter，全程等效 stage 0），结果待回填** | [PLAN](v3/PLAN.md) · [NOTES](v3/NOTES.md) |
| v4 | 2026-09-02 | 碎石地重定标：脚掌实测 0.46×0.51 m（v3.6 误用骨长 0.131），random_rough 间距 0.5 m ≥ 掌宽 + 噪声 (0.10,0.35) step 0.02；v3.6.1 collision stack 补丁回 stock 2**26。**待训练（启动前先看地形）** | [PLAN](v4/PLAN.md) · [NOTES](v4/NOTES.md) |

## 机体几何备忘（生物比例对账，2026-09-01）

URDF 实测（估 SVL ≈2.0m，尾基在 base 后 1.26m；长轴 = Y）。sprawled 姿态几何本身
正确：髋侧向 0.32m、股骨近水平外伸 0.42m、胫骨近垂直——high-crouch 教科书构型。

| 段 | 实测 | 相对量 | 生物参照（巨蜥科） | 判定 |
|---|---|---|---|---|
| 股骨 | 0.50 m | 25% SVL | 20–25%（科莫多档上限） | ✅ 压着上限 |
| 胫骨 | 0.382 m | 股:胫 1.3:1 | ≈1:1 | ⚠️ 偏短 |
| 脚（掌板） | **0.51 m 长 × 0.46 m 宽**（碰撞网格 bbox；kfe→foot 骨长 0.131，勘误 2026-09-02，v3.6 曾误当掌宽定标） | 胫:脚 ≈0.75:1 | 脚 > 胫 | ✅ 达标（旧记 0.131 时的"严重短"判定作废） |
| 站高（base z） | 0.94 m | 47% SVL | 50–55% | ⚠️ 略矮（胫/脚短的连带） |
| 肢质量 | ≈5.5 kg/条 | 7.6% 体重/肢 | 5–8% | ✅ |

- **一句话**：科莫多的股骨 + 截短的下腿。后果①提脚包络满屈 ≈0.52m（v3.4 的
  0.55m 台阶靠 hfe 摆量补够，边缘值）；后果②步幅靠超长股骨补偿锁死的 spine
  侧弯与短下腿，收支勉强平。
- **纪律**：改骨长 = 机体换代 = **换家族**（§A 越级条款），不是任何 vN+1。
  二代机体方向（若立项）：胫骨 +0.1m 换回生物比例（脚掌实测已达标，旧"脚掌
  +0.1m"建议随 0.131 勘误作废）。正常运动蜥蜴肚皮不贴地（postural
  inflation，随速抬高），肚皮接触力 = 病态信号，v3.7 候选惩罚项的生物学依据
  在此。

## 代码地图

不在此维护：全仓逐文件说明见仓根 `FILEMAP.md`；部署 / import 可达性 /
离线闸门（`tools\verify\run_offline_checks.bat`，改 `tasks` 后 commit 前必跑）
见 `README.md`。

## 记录体系（四层）

| 层 | 内容 | 位置 |
|---|---|---|
| 每迭代 | success_rate / reward / curriculum 曲线 | log 目录 TB 事件文件 → `dump_tb.py` 导 csv |
| 每次 eval | 协议跑分（nominal/robust/逐地形） | `ablation_harness/results/locomotion_eval_v1/` |
| 每版本 | 目的/改动/命令/结果/结论 | `versions/lizard/vN/NOTES.md` |
| 家族层 | 版本历史 / 任务表 / 家族特有机制 | 本文档 |

## 开新版本流程

通用五步（copy 目录 → NOTES 骨架 → 结构变更注册 → 训练回填 → 历史行 + tag）
已提取至 `.codemaker/rules/versioning.mdc` §A，含 NOTES 必含骨架与红线；全新
算法（无上游）按 §A 分线条款开支线（`versions/lizard/<line>/v1/` 独立计数），
存量 v0–v4 = 创始主线，裸编号不迁移。
本家族特有机制 = 「Teacher 特权 obs 布局」节「版本差异结构」段的
`TEACHER_PRIVILEGED_SPEC` 剥离纪律（已发布 term 实现永不改语义）。
