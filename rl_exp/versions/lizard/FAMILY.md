# Lizard 训练家族总文档

> 一个版本 = 一代训练配方（参数冻结副本 + 版本文档 + 训练记录）。代码共享继承，
> 参数严格按版本隔离：跑 v1 只读 `versions/lizard/v1/lizard_params.yaml`，v2 读 v2 的，
> 开发态 `lizard_params.yaml` 的修改永远不影响已冻结版本。
> **本文只收已成立的事实（现在时/过去时）**：任何"待/未/若"字头的内容住
> [PLAN.md](PLAN.md)（路线/挂账），此处最多留挂账号指针。
> 训练计划/挂账见 PLAN.md；**obs 契约 SSOT 见 [OBS.md](OBS.md)**（每版布局/
> 论文对应/偏差声明/版本差异机制）；**奖励用途总表见 [REWARDS.md](REWARDS.md)**
> （每 term 的行为动机/权重镜像/c_k 归属/版本差异）；评测协议见 ablation_harness 与
> skill `isaaclab-eval-harness`。

## 当前状态

- 版本态：v0 存档（全量 DR 对照，无任务 id）· v1 已训（14000 iters，出分）·
  v2 冻结未训 · v3 首跑完成 2026-09-01（2048 env × 4999 iter，结果回填状态见
  `v3\NOTES.md`）· v4 提案未训（启动前先看地形，见 `v4/NOTES.md`）·
  v5 已训首跑（2026-09-07 判废：**横行**——资产长轴 Y vs 任务 +X 前向错配，
  判废归因与证据见 `v6\NOTES.md`）· v6 已训判废（2026-09-08 停训 8950/15000：
  **倒走**——rig 骨命名与解剖学 180° 装反（"neck"链=天线尾、"tail"链=球头），
  v6 把命名头转到 +X 即解剖学尾；探针/归因见 `v6\NOTES.md`）· **v8 提案待训**
  （资产解剖学转正 +180° + 全关节重命名 chest/neck/tail1-3 + 腿名换正，
  reward/obs 逐字同 v6.2，方案见 `v8\PLAN.md`）· **v7 提案**（ghost 断腿
  鲁棒性：截肢近似 DR + damage flag obs + v8 ckpt 微调——前提已随 v8 修正，
  方案见 `v7\PLAN.md`）
- 开发态 yaml: `lizard_params.yaml`（家族活实验用，改动不追溯）
- 布局（2026-09-01 迁移）: 包名 `rl_exp`（家族无关），冻结配方按家族分层
  `versions/lizard/vN/`；代码只在 git 仓，IsaacLab 根常驻 1 行注册 shim
- 支线：**parkour v1 初稿已开**（2026-09-04，分支 `paper/parkour-in-the-wild`，
  训练未启动）——跑/爬/跳多专家蒸馏+RL 微调线，方案见 `parkour/v1/PLAN.md`，
  路线与决策记录见 `parkour/PLAN.md`；主线 v0–v5 为主创始线，编号互不影响

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
| **Lizard-Rough-v5** | `LizardRoughTeacherEnvCfg_V5` | versions/lizard/v5（**已训首跑判废**——资产轴错配横行，见 v6） | 反划脚奖励包（r_fc 符号 + r_slip + 肚皮受力罚 + EP 线性跟踪；命令 (0,3) 无速度课程；obs 同 v3 三组 90/208/83，spec 不变） |
| Lizard-Rough-Play-v5 | `LizardRoughTeacherEnvCfg_V5_PLAY` | versions/lizard/v5（已训判废） | v5 回放 |
| **Lizard-Rough-v6** | `LizardRoughTeacherEnvCfg_V6` | versions/lizard/v6（**提案待训**） | 资产前向轴转正（头 +Y→+X）；reward/obs/地形逐字同 v5，yaml 逐字相同——纯资产换代 |
| Lizard-Rough-Play-v6 | `LizardRoughTeacherEnvCfg_V6_PLAY` | versions/lizard/v6（**提案待训**） | v6 回放 |

注：teacher 任务 id 与配方版本同步，且**全部常驻注册**——旧版本不会因代码
演进而失复现（机制见 [OBS.md](OBS.md)「版本差异结构」节）。`Lizard-Rough-v0` 无任务 id
（未训练存档，复现走 git 历史）。家族任务 id 的 `-v0` 是 gym API 版本后缀，
与配方版本无关。

## Obs 契约

v1–v5 全部 obs 布局、论文对应、偏差声明（决策 B / v3 有意偏差）与
`TEACHER_PRIVILEGED_SPEC` 版本差异机制 = **[OBS.md](OBS.md)**（家族级 SSOT，
数值真源为代码 + `check_obs_layout.py`）。演进速览：v1 266 单向量 →
v2 308（+42 论文对齐）→ v3 三组 90/208/83（脚环 extero + 三编码器）→
v4/v5 spec 不变。

## 版本历史

| 版本 | 日期 | 摘要 | 教训 |
|---|---|---|---|
| v0 | 2026-08-28 | 首版冻结：72kg、DR 全套、基线奖励（回滚态）、teacher 特权 obs。未训练即被 v1 取代，存档作全量 DR 对照 | 未训即被取代也要存档——v1 收窄后"有得比"全靠这份对照 |
| v1 | 2026-08-31 | teacher 首跑：v0 仅 DR 段全部收窄（无一归零）。已训练 14000 iters 并出评测分（0.635 = base+x 位移达标率——Y 轴资产上即**横行成绩**，见 v5\NOTES 问题所在）。**原地复现已退役**（v6 资产换代后跑 `Lizard-Rough-v1` = 新资产静默错配，复现走 git checkout tag；见本节末退休注记） | 一次只动一个变量：特权 obs 单独救活趴窝（0.254→0.635），激励逃生舱假设被对照否定 |
| v2 | 2026-08-31 | 特权 obs 论文对齐补全（+forces/normals/friction/thigh-shank/wrench 共 42 维，266→308）；yaml 与 v1 相同 | 纯代码级 obs 变更可不升 yaml——契约差异写在代码 spec 里足够 |
| v3 | 2026-09-01 | teacher 论文对齐版（obs 三组 90/208/83=381：脚环 extero + 三编码器；tilt 终止 + 防拖 r_fc + c_k 课程 + DR reset 化）。首跑完成 2026-09-01（2048 env × 4999 iter，全程等效 stage 0），结果回填见 NOTES。**原地复现已退役**（同 v1；划脚诊断本身 frame 无关，结论存活） | 结构重排先过装配 gate：gate bug 让首跑全程等效 stage 0，代价一整跑 |
| v4 | 2026-09-02 | 碎石地重定标：脚掌实测 0.46×0.51 m（v3.6 误用骨长 0.131），random_rough 间距 0.5 m ≥ 掌宽 + 噪声 (0.10,0.35) step 0.02；v3.6.1 collision stack 补丁回 stock 2**26。待训练（启动前先看地形） | 定标用实测碰撞 bbox 不用骨长（0.131 勘误）——数字必须可溯源到测量 |
| v5 | 2026-09-03 | 反划脚奖励包：r_fc 符号 + r_slip + 肚皮受力罚 + EP 线性跟踪；命令 (0,3) 无速度课程；obs 同 v3。首跑（~2000+ iters，2026-09-07）**横行判废**：资产长轴 Y vs 任务 +X 前向错配——奖励包本身教会了位移，方向沿身体右侧。**原地复现已退役**（同 v1） | **资产坐标系列进任务前先对表**：URDF 长轴方向必须在开训前对上命令系 +X（几何备忘写了"长轴 = Y"没人连到任务约定）；位移首次有收益的版本才会暴露轴错配 |
| v6 | 2026-09-07 | 资产前向轴转正（blend R_z(-90°) + AXIS_MAP 同步）+ v6.1 脊柱/尾动作解锁（scale 0→0.25，用户拍板）+ v6.2 脊柱 PD 400/20（测量依据见 NOTES）；其余逐字同 v5。**已训判废**（2026-09-08 停训 8950/15000：**倒走**——骨命名与解剖学 180° 装反，转正的"命名头"=解剖学尾；归因链见 `v6\NOTES.md`） | **"头"的判定必须锚定造型证据（球头/锥尾），禁止只信骨名**——装配验证全信骨名，名字错则全链绿灯 |
| v7 | 2026-09-08 | ghost 断腿鲁棒性（提案，代码未实施）：截肢近似 DR（p=0.3 整腿 stiffness→0 + 质量 ×0.001，契约维度不变）+ `damage_flags` 4 维进 actor obs（90→94，UE 断腿事件直填）+ v8 ckpt 微调（PITW 配方）。limp/分级/多腿/mid-episode 不做 | （训练后补） |
| v8 | 2026-09-08 | 资产解剖学转正 + 全关节重命名（v6 判废根因修复）：blend 再转 R_z(+180°)（球头→+X）+ 26 关节按解剖学改名 + 全版本 yaml 迁移 + 注册 `Lizard-Rough-v8`；reward/obs 逐字同 v6.2，v8.1 r_slip ×10（预注册升级，v6 数据触发）。布局硬闸入 `check_joints_v8.py` | （训练后补） |

> **退休注记（2026-09-07，资产换代后果）**：v1/v3/v5 的**原地复现已退役**——
> v6 资产换代后，工作树跑旧任务 id（`Lizard-Rough-v1/v3/v5`）加载的是**新资产**
> （yaml 只钉 usd 路径不钉内容），旧 checkpoint 的 obs 语义错配 90°，闸门不报警
> （锁已同 commit 刷新为现资产 hash）。旧数据复现**必须** `git checkout <tag>`
> 整树（资产 + 配方 + 锁自洽）；历史数据本身有效（度量从不引用视觉朝向），
> 旧 checkpoint 只在旧资产上有意义。
>
> **v8 换代追加（2026-09-08）**：v8 起资产再转正 180° 且关节**整体重命名**
> （rear/tail/neck1-3 → chest/neck/tail1-3，腿名换正）——全部版本 yaml 的
> joint_order 与脊柱正则已随换代 commit 机械迁移（数值配方不动，命名接口同步），
> 旧任务 id 仍可构造（加载新资产 + 旧数值），但旧 checkpoint 的 obs 槽位语义
> 与关节名双重错配，**任何 v8 前的 ckpt 均不可回放**。

## 机体几何备忘（生物比例对账，2026-09-01）

URDF 实测（估 SVL ≈2.0m；长轴 = **X**，球状头在 base +X、天线尾在 −X、
关节名 = 解剖学——v8 起如此）。sprawled 姿态几何本身
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

### 左右镜像符号约定（v6 起在案，v8 轴值更新，写对称先验/对称 loss 前必读）

四条腿**同号同轴**（AXIS_MAP 按关节类型统一，不分左右），几何左右镜像
（镜像面 = x-z 平面，y→−y）。镜像下旋转是否反号取决于轴与镜像面的关系。
v8 转正 180° 后轴值翻转（X/Y 分量取反），且**腿名自 v8 起等于解剖学左右**：

| 关节 | 轴（v8 转正后） | 轴与镜像面 | 镜像动作符号 |
|---|---|---|---|
| haa | −X | 面内 | **要取反** |
| hfe | +Z | 面内 | **要取反** |
| kfe | −X | 面内 | **要取反** |
| foot | +Y | 垂直面 | **不取反**（四脚正角齐翘脚尖；轴翻转×手性翻转两负相消） |

对称限位（±0.6/±1.2/±1.6/±0.5）下符号约定不改可达集，不伤训练——只影响
策略学到的每腿符号。**对称先验/镜像数据增广只许对 haa/hfe/kfe 反号，foot
不反**，一刀切全反会把脚掌 roll 项弄反。**v8 注意**：轴符号翻转 + 腿名换位
后，上表 v6 时代记录的"左 haa+ 抬腿"类逐腿极性断言全部作废——写对称先验前
以 `check_joints_v8.py` 实测（注入 ±0.3 看 dy/dz）为准，禁止手算镜像。

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
本家族特有机制 = [OBS.md](OBS.md) 的 `TEACHER_PRIVILEGED_SPEC` 剥离纪律
（已发布 term 实现永不改语义）。
