# Lizard 训练家族总文档

> 一个版本 = 一代训练配方（参数冻结副本 + 版本文档 + 训练记录）。代码共享继承，
> 参数严格按版本隔离：跑 v1 只读 `versions/lizard/main/v1/main_params.yaml`，v2 读 v2 的，
> 开发态参数的修改永远不影响已冻结版本。
> **本文只收已成立的事实（现在时/过去时）**：任何"待/未/若"字头的内容住
> [PLAN.md](PLAN.md)（路线/挂账），此处最多留挂账号指针。
> **obs 契约 SSOT 见 [OBS.md](OBS.md)**（每版布局/论文对应/偏差声明/版本差异机制）；
> **奖励用途总表见 [REWARDS.md](REWARDS.md)**（每 term 的行为动机/权重镜像/c_k 归属/版本差异）；
> 评测协议见 `ablation_harness/` 与 skill `isaaclab-eval-harness`。
> 目录职责、闸门清单、版本目录登记行见仓根 `FILEMAP.md`（本文不重复）。

## 线：家族 / 主线 / 支线

- **`versions/lizard/main/` = 创始主线**（v0–v15）。主线**就是家族本身**：家族级文档
  （`FAMILY.md` / `PLAN.md` / `OBS.md` / `REWARDS.md` / `ACCEPTANCE.md`）落在
  `versions/lizard/`，**不在 `main/` 里**；`versions/lizard/main/` 里也不全是版本目录
  （`rough-v0/` 等是配方 diff 目录）。
- **`versions/lizard/parkour/` = 支线**：Parkour in the Wild（跑/爬/跳多专家蒸馏 + RL 微调），
  分支 `paper/parkour-in-the-wild`，`v1` 初稿（未冻结、未启动）；血统 = 支线根（与主线无配方血缘）。
- **`versions/lizard/baseline/` = 支线**：能力基线（平地 + 固定 `0.5,0,0` + 零课程 + 零 DR），
  只回答"这副机器人能否学会持续行走"，不预留第二臂；配方代码自包含，**不 import 任何其它线的
  cfg/mdp**（刻意复制奖励核）；`baseline_params.yaml` **没有** `domain_randomization` 段
  （缺席是设计，不是遗漏）。
- 支线与主线的 **vN 编号各自独立计数**，互不影响。线间隔离由 `test_baseline_isolation.py` 看守。
- **每版的"当前状态"（已训 / 判废 / 待训）不写在这里**：跑没跑、判没判归各 `vN/NOTES.md`，
  状态总览归 `PLAN.md`。

## 任务注册表

**真源是 `rl_exp/tasks/recipe.py` 的配方表 + `versions/recipes.json`**（本文只留人类速查）。
teacher 任务 id 与配方版本同步，且**全部常驻注册**——旧版本不会因代码演进而失复现
（机制见 [OBS.md](OBS.md)「版本差异结构」节）。家族任务 id 的 `-v0` 是 gym API 版本后缀，
与配方版本无关；`Lizard-Rough-v0` 无任务 id（未训练存档，复现走 git 历史）。

| 任务 id | 配方来源 |
|---|---|
| `Lizard-Velocity-{Flat,Rough,Curriculum-Flat,Curriculum-Rough}[-Play]-v0` | 开发态 yaml（活实验）；8 条键见 `versions/recipes.json` |
| `Lizard-Rough[-Play]-v{1,2,3,4,5,6,8,10,11,12,13,14}` | 对应 `versions/lizard/main/vN/` 冻结参数 |

（无 v7 / v9 任务 id：v7 未启动即迁 v9 重基 v8。逐行 cfg 类名与"提案/待训/判废"标注是
`recipe.py` 表与版本史行的复制品，已删；`Lizard-Rough-v1` = v1 配方 obs 266 这类复现入口
查 `versions/recipes.json` 的 `legacy_task_version`。）

## Obs 契约

v1–v5 全部 obs 布局、论文对应、偏差声明（决策 B / v3 有意偏差）与
`TEACHER_PRIVILEGED_SPEC` 版本差异机制 = **[OBS.md](OBS.md)**（家族级 SSOT，
数值真源为代码 + `check_obs_layout.py`）。演进速览：v1 266 单向量 →
v2 308（+42 论文对齐）→ v3 三组 90/208/83（脚环 extero + 三编码器）→
v4/v5 spec 不变。

## 版本历史

血统 SSOT = 各版本目录 `base.json`（唯一母本边；决策引用留在 PLAN 散文）。
vN 编号只是句柄，不是顺序契约——重基（v7→v9 迁 v8、v10 承 v8.1）由闸门锁死，
`check_version_docs.py --tree` 可出全树。

**行内只留"这版是什么 + 教训"**；判决读数、观测数据、验收明细归各 `vN/NOTES.md` 与
`ACCEPTANCE.md`（本文不复制数值）。

| 版本 | 日期 | 摘要 | 教训 |
|---|---|---|---|
| main/v0 | 2026-08-28 | 首版冻结：72kg、DR 全套、基线奖励（回滚态）、teacher 特权 obs。未训练即被 v1 取代，存档作全量 DR 对照 | 未训即被取代也要存档——v1 收窄后"有得比"全靠这份对照 |
| main/v1 | 2026-08-31 | teacher 首跑：v0 仅 DR 段全部收窄（无一归零），14000 iters 出分。**原地复现已退役**（见下退休注记） | 一次只动一个变量：特权 obs 单独救活趴窝（0.254→0.635），激励逃生舱假设被对照否定 |
| main/v2 | 2026-08-31 | 特权 obs 论文对齐补全（+forces/normals/friction/thigh-shank/wrench 共 42 维，266→308）；yaml 与 v1 相同 | 纯代码级 obs 变更可不升 yaml——契约差异写在代码 spec 里足够 |
| main/v3 | 2026-09-01 | teacher 论文对齐版（obs 三组 90/208/83=381：脚环 extero + 三编码器；tilt 终止 + 防拖 r_fc + c_k 课程 + DR reset 化）。首跑完成，**原地复现已退役**（见下） | 结构重排先过装配 gate：gate bug 让首跑全程等效 stage 0，代价一整跑 |
| main/v4 | 2026-09-02 | 碎石地重定标：脚掌实测 0.46×0.51 m（v3.6 误用骨长 0.131），random_rough 间距 0.5 m ≥ 掌宽 + 噪声 (0.10,0.35) step 0.02；v3.6.1 collision stack 补丁回 stock | 定标用实测碰撞 bbox 不用骨长（0.131 勘误）——数字必须可溯源到测量 |
| main/v5 | 2026-09-03 | 反划脚奖励包：r_fc 符号 + r_slip + 肚皮受力罚 + EP 线性跟踪；命令 (0,3) 无速度课程；obs 同 v3。**首跑判废：横行**（资产长轴 Y vs 任务 +X 错配）；**原地复现已退役**（见下） | **资产坐标系列进任务前先对表**：URDF 长轴方向必须在开训前对上命令系 +X（几何备忘写了"长轴 = Y"没人连到任务约定）；位移首次有收益的版本才会暴露轴错配 |
| main/v6 | 2026-09-07 | 资产前向轴转正（blend R_z(-90°) + AXIS_MAP 同步）+ v6.1 脊柱/尾动作解锁（scale 0→0.25）+ v6.2 脊柱 PD 400/20；其余逐字同 v5。**已训判废：倒走**（骨命名与解剖学 180° 装反，转正的"命名头"= 解剖学尾） | **"头"的判定必须锚定造型证据（球头/锥尾），禁止只信骨名**——装配验证全信骨名，名字错则全链绿灯 |
| main/v7 | 2026-09-08 | ghost 断腿鲁棒性（提案，代码未实施）：截肢近似 DR（p=0.3 整腿 stiffness→0 + 质量 ×0.001，契约维度不变）+ `damage_flags` 4 维进 actor obs（90→94）+ v8 ckpt 微调（PITW 配方）。**v7.1 同日归档**：未启动即迁 v9 重基 v8 | 提案未启动前提失效（v6 判废）→ 编号顺序 < 语义正确：占位号让位，血缘号接管 |
| main/v8 | 2026-09-08 | 资产解剖学转正 + 全关节重命名（v6 判废根因修复）：blend 再转 R_z(+180°)（球头→+X）+ 26 关节按解剖学改名 + 全版本 yaml 迁移 + 注册 `Lizard-Rough-v8`；reward/obs 逐字同 v6.2，v8.1 r_slip ×10（预注册升级，v6 数据触发）。布局硬闸入 `check_joint_layout.py` | （训练后补） |
| main/v9 | 2026-09-08 | ghost 断腿鲁棒性（提案，代码未实施，自 v7 迁入重基 v8）：内容同 v7 行，另加 weight surgery 90→94。limp/分级/多腿/mid-episode 不做 | （训练后补） |
| main/v10 | 2026-09-09 | 单变量删除 tilt 终止（v8.1 之上唯一差异，`tilt_terminate: null`）：翻倒数据留在 rollout 自供翻身梯度，只有 time_out 收局；4096 env。训完 15000 iter，判决门 = `v10/NOTES.md` 验收 1–5 | **半通过**（读数见 NOTES + `DIAGNOSE.md`）：time_out 与 success 达标、terrain_levels **未爬**；附带发现零命令下 2–3 脚站、恒定蟹行、低速超速——**账本满分 ≠ 行为正确** |
| main/v11 | 2026-09-10 | 联合粒子地形课程（Lee 2020 Alg S1 + 联合扩展）：粒子 = (参数格 combo, 速度桶)，`param_grid_terrain.py` 参数组合网格（治对角线问题）+ 逐步 Tr 测量 + `ParticleVelocityCommand` 桶命令 + 空方向分流兜底。实施完成（smoke TRAIN 段留开训前补跑） | （训练后补） |
| main/v12 | 2026-09-10 | Miki S8 鲁棒性包（提案，代码实施同日）：关节初值/速度 reset 随机（offset 型三组，替换 stock 对全零默认 no-op 的 scale 型）+ 基座姿态/速度范围 yaml 化 + 足底摩擦偶发调低（p_dip 0.1 → [0.05,0.3]，特权 obs 缓存同调用更新）+ teacher 侧高度环噪声（工况 60/30/10，幅度 × c_k，中途重抽；无学生蒸馏）+ r_slip 回 −0.003。obs 契约不变 | （训练后补） |
| main/v13 | 2026-09-14 | 换回 Miki 对称跟踪核（单变量，base = v10）：`track_lin_vel_xy_miki` = `exp(−‖v_cmd−v_yaw‖²/0.25)`（全 2D 误差、yaw 帧、无 min_speed → cmd=0 站立拿满分），替掉 EP 线性核（超速饱和中性/横向投影不可见/零命令无梯度三盲区，v10 判决实证）。weight 保 1.5 不随 paper 0.75（= 纯核形状消融）。闸 `check_reward_v13.py`；v13.1/v13.2 验收口径三修与换帧见 `v13/NOTES.md` | 风险预注册：v3/v4 exp 核趴窝病历，判废线 = v10 |
| main/v14 | 2026-09-14（v14.3/v14.4 09-15） | 加回摔倒闸，三次改形后 = v14.4：终止项 = `roll_over_trigger`（基座四元数 ZYX roll，`\|roll\| > 70°`，单调覆盖整圈含肚朝上；`\|pitch\| > 80°` 护栏；per-env dwell 0.5 s）+ 头承重改**惩罚** `head_load_penalty`（头链 contact_forces 世界系 +z 力 relu 求和 / 706 N，权重 -1.0，无阈值/无姿态门控/不做 c_k 缩放）。前栽不收局，趴地接触不管。闸 `check_terminations_v14.py` | **"留肚朝上供起身梯度"不成立** —— Miki 配方没有起身目标，倒了就是翻车（用户拍板）；`\|sin\|` 形判据在 110° 后回落会放过一整族，已废 |
| main/v15 | 2026-09-16 | 地形课程换 **joint SIR**（base = v14，提案态未实施）：v5 行 SIR（只调难度行、类型维度不可调）→ v11 机制的**联合粒子 SIR**，粒子 = (类型**内部**参数档 combo, 速度桶)，**类型份额固定、不跨类型**（env→type 初始化锁定 `teacher_mdp.py:1150`）；`build_param_grid_terrain_cfg` 参数格（默认 57 combo + flat = 58 类型 / 4×120）+ `ParticleVelocityCommand`（buckets 0.5…3.0 + jitter）+ `Curriculum/joint_sir/{tr_mean, particle_entropy}`（判读量；`frontier_max_v` 冷启动即满值 3.0，**不作能力进度**）；obs/动作/奖励/终止/DR/资产逐字段同 v14。v15.3 重规划（评分换 yaw 帧跟踪误差、Tr 分母改固定窗口、冷启动改显式 `anchor_combo`、每块一次局部扩展；**取消**硬解锁 / 85% 锚集 / 掌握判据）见 `v15/PLAN.md` | **首跑该课程线**（v11 仅 6-iter 冒烟、v12 无 run ⇒ 均不作基线）；本版拟在**老框架**下训练而项目并行迁新框架 ⇒ 前置门：开训前打 tag、进程不得重启、训练结束前不得 `cfg_lock --update`；机制评审 5 条已核证，修复落共享实现后**共用 term 的 v11/v12 golden 已随之重生成**（需偏差声明或 v15 专用变体，待拍板） |
| parkour/v1 | 2026-09-04 | 支线初稿（未冻结未训练）：跑/爬/跳多专家蒸馏 + RL 微调（PITW 配方）；血统 = 支线根（`base.json` null，与主线 vN 无配方血缘）；参数冻结副本 `parkour/v1/parkour_params.yaml` | （训练后补） |
| baseline/v1 | 2026-09-16 | 支线初稿（未冻结未训练）：**平地 + 固定 `0.5,0,0` + 零课程 + 零 DR** 的能力基线；血统 = 支线根（`base.json` null）；配方代码自包含（只依赖框架基类与框架 mdp + 本线 `baseline_mdp.py` 的两个核副本），不 import 任何其它线的 cfg/mdp；观测 90 维单组 proprio + 普通 MLP；参数冻结副本 `baseline/v1/baseline_params.yaml` | （训练后补） |

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
以 `check_joint_layout.py` 实测（注入 ±0.3 看 dy/dz）为准，禁止手算镜像。

## 记录体系

| 层 | 位置 |
|---|---|
| 每迭代 | `<ROOT>\logs\` 的 TB 事件文件 → `dump_tb.py` → `vN/tb_scalars.csv`（抽样入库，全量留机器本地） |
| 每次 eval | `ablation_harness\results\<协议>\<group>\<run_id>\eval.json`（含 `terrain\geometry.json`） |
| 每版本 | `vN/NOTES.md`（目的 / 参数 diff / 训练命令 / 结果回填） |
| 家族层 | 本文档（版本史）+ 各线 `PLAN.md`（计划/挂账）+ 线级 `ACCEPTANCE.md`（通过数与通过率的唯一归属） |

## 开新版本流程

通用五步（copy 目录 → NOTES 骨架 → 结构变更注册 → 训练回填 → 历史行 + tag）
已提取至 `.codemaker/rules/versioning.mdc` §A，含 NOTES 必含骨架与红线；全新
算法（无上游）按 §A 分线条款开支线（`versions/lizard/<line>/v1/` 独立计数），
存量 v0–v4 = 创始主线，裸编号不迁移。

**本家族的结构变更机制（2026-09-17 起：注册表已切到声明路径）**：加一个版本 =
在 `rl_exp/tasks/recipe.py` 加元素函数并填**配方表一行**（`elements`/`play_elements`/
`declares`/`pins_full_range`/`train`/`play`）+ 在 `versions/recipes.json` 登记配方键与两个
入口 + `tasks/__init__.py` 注册任务 id（`env_cfg_entry_point` 指 `recipe_tasks:<类名>`）。
**不再新建版本类，也不再改 `teacher_env_cfg.py`**：可注册的类由 `tasks/recipe_tasks.py`
按声明生成，并且**沿用被替换类的名字**（ckpt 载荷记 `type(cfg).__name__` 并参与 resume
身份核验，名字不一致会让跨路径续训被拒）。配方表是唯一真源 ——"这个版本是什么"= 有序元素
表 + 逐条差异声明，而不是某个 `__post_init__` 的残留；版本子类一旦重新出现，
`[41]` 立即具名报红（一个配方两个表达式 = 总有一个没人跑）。

**开发态配方走同一张表（2026-09-18）**：`flat-v0` / `rough-v0` / `curriculum-flat-v0` /
`curriculum-rough-v0` 四条声明在 `lizard/main` 的**同一张配方表**上（表键 = 身份映射的配方键去掉
`@1`），`params_version: None`（⇒ 读**开发态** yaml）；base 是**家族接线** `LizardFlatEnvCfg`
（不是 teacher 接线）。它们服务的注册任务就是任务注册表里那 8 个 `Lizard-Velocity-*-v0`
⇒ **调试态的 env 与冻结配方走同一条机制**；`rough_env_cfg.py` / `curriculum_env_cfg.py`
的类体与 `curriculum_rough_env_cfg.py` 整个文件随之退役（只留调参常量与辅助类）。

## 代码地图

不在此维护：全仓目录职责与闸门清单见仓根 `FILEMAP.md`；部署 / import 可达性 /
离线闸门（`tools\verify\run_offline_checks.bat`，改 `tasks` 后 commit 前必跑）
见 `README.md`。

**本家族特有机制** = [OBS.md](OBS.md) 的 `TEACHER_PRIVILEGED_SPEC` 剥离纪律
（已发布 term 实现永不改语义）。
