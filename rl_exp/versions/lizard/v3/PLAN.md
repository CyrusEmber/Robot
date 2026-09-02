# Lizard-Rough-v3 实施计划（teacher Phase 1 论文对齐增强版）

> 状态：**代码已装配，训练待启动**（2026-09-01：D0-1/D0-2 用户拍板后 A–F 全部落地，
> 离线闸门 8/8 绿 + teacher_smoke_v3 + 4096 env 计时通过；实施偏差见 §10 v3.3 行）。
> 生成：2026-09-01。来源：全仓 code review + Miki et al. 2022（arXiv:2201.08117,
> Sci. Robotics）全文核实（正文 + 补充材料 S1–S9）。
> 修订：v3.6（2026-09-01）——回放诊断三修：速度课程接入（-1..2→5，`用户拍板`）、
> base_contact 终止删除（D0-6 执行落地）、碎石粗化（downsampled_scale 0.3m），明细见 §10 修订记录。
> 此前 v3.5（2026-09-01）：地形课程护城河 `max_init_terrain_level 5→0`。
> 关联：`../PLAN.md`（家族滚动计划/挂账）、`../FAMILY.md`（obs 布局 SSOT）。v3 定稿
> 训练后本文件并入 ../PLAN.md，FILEMAP 登记随 Phase F 补。

## 0. 背景与动机

v2 的"论文对齐"只完成了特权 obs 表（最容易的一块）。本次 review + 论文核实确认
teacher 与论文仍有结构性差异，按对 Phase 2 蒸馏的影响排序：

1. **teacher 单体 MLP**——论文 g_e/g_p/f_π 三组件是为蒸馏设计的（权重迁移 +
   belief 对齐），单体网络全部丢失；
2. **obs 归一化关闭**——381 维输入跨 3 个数量级（力 ~700 N / mass ~11 kg /
   摩擦 0–1.2 / cos 0–1），PPO 直接受害；
3. **body 网格扫描**——论文是每脚环形 52 点，g_e 结构、r_fc 奖励、噪声模型
   z∈R^{8×4} 三者的共同前提；
4. **奖励/终止面 = stock ANYmal 校准**，与论文 S7 语义不同源——**趴窝的论文防线
   在终止三件套 + c_k 惩罚课程，不在接触惩罚权重**（PLAN §2.3 回滚表调的是论文
   没调的杠杆，若重启应改方向）。v3 采 tilt 终止 + c_k 课程两项；接触终止因
   sprawled 低趴误杀风险**明确不做**（D0-6 声明偏差，敞口与升级路径见 §9）；
   v3.6 起代码落地执行（`terminations.base_contact = None`，肚皮接触只罚不终止，
   `用户拍板：2026-09-01`）。

## 1. D0 决策门（拍板后开工）

| # | 决策点 | 提案立场 |
|---|---|---|
| 1 | 高度采样形态 | **脚环方案 A**：4×RayCaster 挂 `.*_foot`，52 点/脚 |
| 2 | DR startup→reset 化 | 做（c_k 吃不到 startup 一次性采样） |
| 3 | torque-limit 终止 | **不做**，文档记录理由（implicit PD 无可靠 readback） |
| 4 | CPG 动作空间 | 继续挂账；v3 声明偏差，belief encoder 兜时序 |
| 5 | 改动范围 | **只动 teacher 快照，family 零改动**（对照实验纪律） |
| 6 | 终止覆盖面 | **不加接触终止**（2026-09-01 拍板：躯干链也排除——低趴构型正常过障即可触地，任何接触终止都有误杀风险）。趴窝防线 = tilt + 软惩罚权重消融；belly-down 敞口见 §6 D1 / §9 |
| 7 | 仓布局 | **Phase G 采纳**（2026-09-01）：git 仓为唯一代码家——`.pth` 直指 `E:\lizard_migration`、删 junction、`_ISAAC_ROOT` 参数化。不可消残留 = **1 行注册 shim**（`isaaclab_tasks/__init__.py` 只 `import_packages` 自家树，无第三方 entry-point 发现，已读 pinned 源码验证） |

## 2. 架构规格（摘要，论文精确数字见 §8）

```
teacher v3（Phase 1 训练）
  脚环×4 ──g_e {80,60} 共享──> l_e (24/脚, 拼 96) ─┐
  特权 83 ──g_p {64,32}──────> l_priv (24) ────────┼─> f_π {256,160,128} ─> action 26
  proprio 90 ──────────────────────────────────────┘        （三流各自 running mean/std）

student（Phase 2，本计划只锁接口）
  b'_t,h+ = GRU(o_p, l_e, h)   # 2 层 × 50
  α_t = σ(g_a(b'_t))           # {64,64} → 96
  b_t = g_b(b'_t) + l_e ⊙ α_t  # {64,64} → 120（zero-pad 对齐）
  a_t = f_π([o_p ‖ b_t])       # 输入 210 维与 teacher 恒等 → 权重零改动继承
  L = L_bc + 0.5·L_re          # L_re 目标 = 干净高度样本 + l_priv
```

**Phase 1 必须为 Phase 2 暴露的接口**：g_e/g_p/f_π 为命名子模块（ckpt 可逐个摘取）；
obs 按**三个组**交付 `[proprio 90 | extero 208 | priv 83]`（组名对齐 rsl_rl
`obs_groups`，网络按名取流，见 §4 B2）；脚环噪声模型按脚定义；
干净扫描副本与 l_priv 计算项（v2 已齐）留给 student env 读。

## 3. Phase A：修复阻塞项（独立先行，不等 v3）

| 任务 | 文件 | 说明 |
|---|---|---|
| A1 | `ablation_harness/eval.py:158-191` | **end_pos 改 step 前快照**（H1：现采到 auto-reset 重生坐标，completion/energy 对真 checkpoint 全废） |
| A2 | `tools/verify/check_dr_parity.py` | 清单 count assert；`--update-locks` 只更新受影响版本；锁扩面 `meshes/**` + `versions/lizard/vN/*.yaml` |
| A3 | `tools/verify/smoke_test.py:28` | 死闸门（`step_out[2]`=terminated 恒 False）改真断言：obs 维 + 有限性 |

✅ 验证：`run_offline_checks.bat` 全绿。

## 4. Phase B：网络模块（teacher 三编码器 + student belief encoder）

| 任务 | 文件 | 说明 |
|---|---|---|
| B1 | `tasks/teacher_networks.py`（新） | `ExteroEncoder`（g_e {80,60}→24/脚，4 脚共享）、`PrivEncoder`（g_p {64,32}→24）、`PolicyTrunk`（f_π {256,160,128}，LeakyReLU） |
| B2 | 同上 | `SplitEncoderModel`：env 侧定义 `proprio/extero/priv` 三个 **obs 组**，网络按**组名**取流（替掉魔法偏移切片；组内 term 顺序仍受 F1 看守），三组各自 running mean/std，命名子模块，critic 同构无循环。**待验证**：`RslRlVecEnvWrapper` 把 obs dict 透传到 model forward（实现日 30 分钟确认；不通则退回单向量+偏移切片，F1 升级为偏移强断言） |
| B3 | `agents/rsl_rl_ppo_cfg.py` | ~~fork 补丁~~ **删除**。rsl_rl 5.4.2 `resolve_callable`（utils.py:97）支持 `"module:Class"` 点路径，actor/critic 类名在 ppo.py:416-418 即按此解析 → cfg 里写 `class_name="rl_exp.tasks.teacher_networks:SplitEncoderModel"` 即可，**零 rsl_rl 改动** |
| B4 | `tasks/student_networks.py`（新） | belief encoder 全组：`BeliefEncoder`（GRU 2 层×50，输入 `[o_p 90 ‖ l_e 96]`，输出 b' 100 + h）、`AttentionGate` g_a {64,64}→96（σ 输出 α）、`BeliefMapper` g_b {64,64}→120（zero-pad 对齐）、合成 **b_t = g_b(b') + l_e ⊙ α**；`StudentPolicy`（f_π 输入 `[90‖120]=210`，与 teacher 恒等）；`BeliefDecoder`（b_t → 干净扫描 208 + l_priv 24，训练期专用，同款 gate）。**f_π 输入段序冻结 [proprio 90 | l_e 96 | l_priv 24]**：b_t 前 96 维 = l_e 位（zero-pad 落在 g_b 输出侧）、后 24 = priv 预测位——两侧段序恒等是权重迁移的语义前提（同维不同序 = 静默错位，shape 检查抓不到）。L_re 目标取 l_priv 24 为**有意偏差**（论文重建原始特权态 s_p 50 维；参考仓库同款做法），F3 声明 |
| B5 | 同上 | 权重迁移接口 `load_from_teacher(ckpt)`：校验并拷贝 f_π/g_e 逐层权重 **+ o_p 组 running mean/std 统计**（g_p、critic 不迁移——teacher-only）；附 f_π 输入段序恒等断言；Phase 2 蒸馏直接 import，不再动网络层 |

✅ 验证：离线单测——teacher：前向 shape / 梯度 / 命名子模块权重摘取；student：GRU 步进 shape、α∈[0,1]、b_t=120、L_re 输出维 (208+24)、`load_from_teacher` 后 f_π/g_e 逐层权重相等、o_p 归一化统计相等、f_π 输入段序恒等。

> B4/B5 只交付**模块与接口**；蒸馏 runner（监督 BC+re、Adam）、噪声模型 z^{8×4}
> 三条件 60/30/10、teacher rollout 采集 = **Phase 2 交付**，不阻塞 v3 训练。

## 5. Phase C：脚环扫描（方案 A）

| 任务 | 文件 | 说明 |
|---|---|---|
| C1 | `tasks/teacher_env_cfg.py` | 自定义环形 pattern：52 点 = counts {6,8,10,12,16} × radii {0.08,0.16,0.26,0.36,0.48} m（静态偏移张量） |
| C2 | 同上 | 4×RayCaster 挂 `/Robot/Geometry/{lf,rf,rl,rr}_foot`，`attach_yaw_only=True`（v3.1 修正：`ray_alignment` 非 RayCasterCfg 字段名；语义 = 环随 yaw 保持水平、不随 roll/pitch 翻转），update_period=策略率 |
| C3 | 同上 | extero obs 项按 lf/rf/rl/rr 拼 208 |

✅ 验证：teacher_smoke 208 维 + 脚位跟随；**计时对比 135 点版**（性能风险项）。

## 6. Phase D：趴窝修复包（论文杠杆）

| 任务 | 内容 |
|---|---|
| D1 | 终止：**不加任何接触终止**（2026-09-01 拍板：sprawled 低趴，躯干链/腿正常过障时均可触地，硬终止误杀不可控）——接触仅保留 undesired_contacts -1.0 软惩罚。① tilt：`projected_gravity_b[2] > -0.6`（≈53°；**v3.1 符号修正**——repo 约定 upright 时 pg_z = -1，证据 `ablation_harness/eval.py:176` `tilt_cos = -pg_z`；原稿 `< 0.6` 在 upright 恒真 → 起步即全灭。论文未给数值，0.6 进 yaml 标估计）② torque-limit 不做+记录。**敞口声明：belly-down 趴卧时 base 仍水平，tilt 抓不到——PLAN §2.3 根因①（悬空不终止）维持敞口**，监控/升级路径见 §9 |
| D2 | **r_fc 替换 feet_air_time**（v3.1 语义修正）：论文 r_fc 罚 swing 脚**抬太高**（max(H_sample) < -0.2，H = 环采样高 − 脚高），对防拖脚无效，不可"照抄论文"。v3 取反向语义，**有意偏差**（F3 声明）：该脚无接触（swing 判定 = 接触态代理，用户拍板：不用 CPG）且脚高低于"脚下地形高 + 0.2 m"才罚。地形基准 = 每脚垂直射线（复用 FootContactNormalsTerm 基建）——环 pattern 无 r=0 中心射线，原稿"环心采样"取不到数。权重 0.003 进 yaml（估计值起步，调参走消融） |
| D3 | **c_k 课程**（v3.1 定案）：c_{k+1}=c_k^0.98、**c_0=0.2，进 yaml 当消融变量（0.05 / 0.2 / 0.5 三档）**——DR 侧小起点正确（v1 实证收窄有效），但惩罚侧起点过低压垮趴窝防线：论文小 c_0 靠 body 碰撞终止兜底，我们砍了（D0-6），且接触罚 -1.0 全量下都曾压不住（PLAN §2.3）。机制：env 全局步数计数推导 c_k = 0.2^(0.98^⌊global_step / (num_envs × num_steps_per_env)⌋) 存 env buffer，自定义 reward/event func 读同一 buffer——零 runner 改动、**不挂 CurriculumTerm**。**乘子只挂 4 个现存惩罚项：q̈、torque、feet_slide、ω_xy；接触惩罚（r_co）豁免 c_k 恒定 -1.0**（有意偏差：弱惩罚期保持接触罚在线，F3 声明）。论文 jvel / r_s（目标平滑）repo 无对应 term，不新增（F3 声明）。注：对数距离半衰期恒定 ≈34 iter——c_0 只控起点不控课程时长，c_0=0.2 时 ~140 iter 到 0.9，本质是热身段 |
| D4 | **DR reset 化**：mass/com/inertia/gains/friction/joint params 挪 reset 模式，range = base × c_k（论文方向：DR 从小到大）。**机制补（v3.1）**：event cfg 的 range 是静态属性、训练中不可变——自定义 event func 内读 c_k buffer 动态算 range，base range 存 yaml |

✅ 验证：冒烟看 c_k 曲线（不走 CurriculumTerm → TB 无自动曲线，c_k 写入 episode 指标/extras 由 `dump_tb` 导出）；harness `fall_rate` **只做 v3 内部基线**——v2 无 tilt 终止 + DR 语义不同，跨版本不可比（与 §9 风险表口径一致）。

## 6.5 v3 奖励定案总表（term 集冻结，v3.1 补——原稿只列增量、全集未定）

基底 = stock 奖励集（velocity tracking exp 形 + 现存惩罚项），只做下列增量与声明：

| 项 | v3 定案 | 论文口径 | 性质 |
|---|---|---|---|
| velocity tracking（r_lv/r_av） | 保持 stock exp 形 | r_command 饱和形 + r_lvo 正交项 | 偏差（F3 声明，v4 候选） |
| feet_air_time 奖励 | 删除，换 r_fc（D2） | 无 air-time 奖励 | 对齐 |
| r_fc | 防拖脚版（D2） | 罚"抬太高" | **有意反向偏差** |
| undesired_contacts | -1.0 恒定，豁免 c_k | -0.1·c_k | 有意偏差（D3） |
| q̈ / torque / feet_slide / ω_xy | 现权重 × c_k | 同类项乘 c_k | 形制对齐，数值保持 repo 口径 |
| jvel / r_s 目标平滑 / r_jc / r_b 的 v_z² 项 | 不新增 | 论文在线 | 偏差（F3 声明） |
| flat_orientation / dof_pos_limits | 维持禁用 | — | 偏差（F3 声明） |
| tilt 终止 | `pg_z > -0.6`（0.6 估计值进 yaml） | 未给数值 | 对齐 + 估计 |
| c_k | c_0=0.2 定值 + 4 项乘子（D3） | c_0 未给 | 机制对齐，参数自定 |

## 6.6 地形（v3.4，Miki 对齐）

**动因**：v1 数据 A5——增益全在难地形、地形没给策略出难题；现训练地形对
3.6m 身长相对过易（台阶顶 0.35m ≈ 腿展 25%，ANYmal 演示值 30.5cm ≈ 膝高
75%），且训练从未见过镂空/踏空面。v3 定位为"Miki 实现"，地形是论文血统的
一环，漏掉名不副实。
**纪律依据**：v3 训练未启动 → §B 允许内容修订。**边界写死：仅限未训版本**——
已训版本改地形一律 vN+1（§A 触发），本行不为"改地形不升版"开先例。

| 子地形 | 比例 | 参数 | 依据 |
|---|---|---|---|
| pyramid_stairs / inv | .2 / .2 | step_height **(0.08, 0.55)**（原 0.35 顶） | 论文上限未给精确数，0.55 ≈ 腿展 40%，`review 定案`（估计值，可随曲线调） |
| stepping_stones | .1 | stone_width (0.5,0.9)、distance (0.3,0.7)、height_max 0.3、**holes_depth −1.0** | open/ledged 楼梯近似，`用户拍板：2026-09-01`（选项 b） |
| boxes | .1（原 .2） | 不变 | 比例让位 stones，`review 定案` |
| random_rough | .2 | **downsampled_scale 0.3m、noise (0.06, 0.2)**（v3.6） | stock 0.1m 采样间距 = 10cm 细碎石，0.13m 平脚掌整面踩平（v1 回放实证"啪就能站上去"）；0.3m ≈ 2.3×脚掌，逼包络贴合，`用户拍板：2026-09-01` |
| hf_pyramid_slope / inv | .1 / .1 | 不变 | — |

**实现**：`TEACHER_TERRAINS_CFG_V3`（teacher_env_cfg.py），`V3.__post_init__` 换
引用——v1/v2 冻结生成器与 family 地形零改动（D0-5 保持）。

**0.55m 运动学核算（v3.4.1 补）**：URDF 腿链 thigh 0.50 + shank 0.382 + foot 0.131m，
kfe ±1.6rad 满屈提脚上限 ≈0.52m（+hfe ±1.2rad 摆量后 0.6~0.9m）——**抬脚够，
躯干勉强**（站高 z≈0.94m，0.55 立面 = 腹下 59%，sprawled 低趴 + spine 锁定无弯腰
借势，顶排大概率不可爬）。不致命：curriculum rows easy→hard，爬不上只是
terrain_levels 停排。判据：训练曲线长期卡 row≈0.4m 对应档 → 降 0.45–0.5
（`review 定案`）。比例列非论文口径——Miki 无子地形比例表（粒子滤波自适应课程），
此表比例为 stock 惯例 + 本地设计。

**偏差声明（三条）**：
1. open/ledged 楼梯未按原形态实现（论文动机 = 治 RaiSim 高度场边缘不垂直的
   仿真空子，Isaac mesh 路径无此病）；stones+深洞近似"可踏空面"族，镂空阶梯
   序列缺失，影响未验证。
2. 粒子滤波自适应地形课程**不做**，以离散等价替代：`terrain_levels_vel`（逐机
   成功率升降排）+ **v3.5 硬前提 `max_init_terrain_level=5→0`**（从最易排起步，
   论文"难而可解"的第一条；v1/v2 快照保持 5 不动——已训版本冻结）。此前
   init=5 是历史遗留（v0 修复表候选项），叠加 v3.4 难度抬升 = 开局即中难地形，
   正是论文避免的收敛陷阱。与 c_k 联动：弱惩罚期（前 ~100 iter）策略只在
   最易排活动，风险进一步压缩。
3. **归因声明**：训练地形变难、eval 套件（测量仪器）不动 → v3 对 v1 的 nominal
   success 可能不升反降，属地形难度差非机制倒退；跨版本对账以逐地形
   completion 为准。

## 7. Phase E：v3 装配 + Phase F：verify/文档

- **E1** `teacher_env_cfg.py`：`TEACHER_PRIVILEGED_SPEC` 加 v3（obs **381** = 90+208+83）、
  `params_version="v3"`、注册 `Lizard-Rough-v3` / `-Play-v3`（v1/v2 常驻不动）
- **E2** `versions/lizard/v3/` 冻结 + `lizard_params.yaml` 新段：`foot_ring` / `r_fc` /
  `tilt_terminate` / c_k 乘子项 / v3 奖励权重（term 集定案见 §6.5）
- **E3** `agents/rsl_rl_ppo_cfg.py`：v3 runner——归一化开、超参**贴 S1 全表**（v3.1
  补全）：lr 5e-4 + **decay 0.9999/iter**（rsl_rl 无原生指数衰减，`schedule` 仅
  adaptive〔KL〕/fixed——subclass runner 每 iter 衰减，走 B3 class_name 点路径零
  fork）、γ 0.996、epochs 2、GAE 0.95、clip 0.2、entropy 0.005、**batch 8300 是
  minibatch 尺寸** → 个数换算 ⌊num_envs × num_steps_per_env / 8300⌋（论文每 iter
  采 1000 env × 250 步 = 250k 样本，我们 env 数不同，按尺寸等价换算）
- **F1** 新 `tools/verify/check_obs_layout.py`：**组名 + 各组维数（90/208/83）+ 组内 term 顺序断言**，入 bat（若 B2 验证失败退回偏移切片，则升级为偏移强断言）
- **F2** `framework_pin_check.py` 补 pin：`resolve_callable`（utils.py:97）、`ppo.py:416-418` 三处 `class_name` 调用点、`distillation.py:238-240`——点路径注册已是全架构地基，升级 IsaacLab 必查
- **F3** `FAMILY.md`：v3 任务行 + obs SSOT 更新 + **偏差表修正**（论文 proprio 133
  非 131；extero 208 脚环非网格；"真值速度"定性 = 论文 body velocity 本就是仿真真值）
  + 剩余偏差声明（无历史 / 无 CPG / 无 torque 终止 / priv 83 超集〔决策 B：真值速度 6
  + body mass 27〕/ r_fc 反向防拖〔有意〕/ 接触罚豁免 c_k〔有意〕/ L_re 目标 l_priv
  非 s_p / velocity 形制 stock exp / jvel·r_s·r_jc·r_lvo 缺项 / tilt 0.6 与 c_0 0.2
  为估计定值）
- **F4** `PLAN.md` §2.3 修复表重定向为本计划 D1–D4；FILEMAP 登记（versions 家族分层 + v3 行，2026-09-01 已做）

## 7.5 Phase G：仓布局迁移（2026-09-01 大部分已执行）

| 任务 | 内容 | 状态 |
|---|---|---|
| G0 | 包名 `lizard_exp`→`rl_exp`（git mv + 82 py/44 md 机械替换 + 2 处 `_VERSION_FAMILY` 常量 + check_dr_parity `*/v*` 家族无关 glob）；versions 家族分层 `versions/lizard/vN`；本计划文件 → `versions/lizard/v3/PLAN.md` | ✅ 已执行（闸门 PARITY_OK） |
| G1 | venv 新增 `rl_exp.pth`（内容 = git 仓 `E:\lizard_migration`）；删旧 `lizard_exp.pth` | ✅ 已执行 |
| G2 | 删 `E:\IsaacLab\lizard_exp` junction（已悬空）；**`ablation_harness` junction 暂留**（等 G3） | ✅ 部分 |
| G3 | harness `_ISAAC_ROOT` 参数化：`eval.py:69-77`（"故意不 resolve"hack）、`run_ablation.py:36`、`_log_dir_for_tag` glob——改读 env var `RL_ISAAC_ROOT`（缺省向上探测 `source/isaaclab`+`logs`）；落地后即可删 `ablation_harness` junction | → 移 `ablation_harness/HARNESS.md` 挂账 #1（harness 侧工作不属 lizard 配方版本管理，2026-09-01；PLAN.md #12 留指针）；闸门侧 RL_ISAAC_ROOT 已落（v3.1.3） |
| G4 | README 部署节重写（git 仓唯一代码家、.pth 指 `<REPO>`、1 shim、junction 过渡说明）；shim 简化为 1 行 import（删 sys.path hack） | ✅ 已执行 |

✅ 已验证：`import rl_exp.tasks` → gym 注册 12 个 Lizard 任务；`check_dr_parity.py`
PARITY_OK（4 yaml、锁 4 版、接线 21/21）；`compileall` 全绿。
**不可消残留**：1 行注册 shim（D0-7 已声明）。

## 8. 论文精确口径备查（已核实，防再考）

| 项 | 论文数值 |
|---|---|
| proprio（133） | cmd 3 + orient 3 + body vel 6 + jpos 12 + jvel 12 + **jpos 历史×3=36** + **jvel 历史×2=24** + **target 历史×2=24** + **CPG 相位 13** |
| extero（208） | 每脚环 52 点：counts {6,8,10,12,16} × radii {0.08,0.16,0.26,0.36,0.48} m |
| privileged（50） | contact 4 + forces 12 + normals 12 + friction 4 + thigh/shank 8 + wrench 6 + airtime 4 |
| 网络 | g_e {80,60}→24/脚；g_p {64,32}→24；f_π {256,160,128} LeakyReLU；running mean/std |
| 奖励 | `r = 0.75(r_lv+r_av+r_lvo) + r_b + 0.003r_fc + 0.1r_co + 0.001r_j + 0.08r_jc + 0.003r_s + 1e-6r_τ + 0.003r_slip`；r_co/r_j/r_s/r_τ/r_slip 乘 c_k（c_{k+1}=c_k^0.98，c_0∈(0,1) 单调→1——**c_0 论文未给**；对数距离半衰期 ≈34 iter）；r_b = -1.25v_z²-0.4\|ωx\|-0.4\|ωy\|；r_fc 罚 swing 脚**过高**（max(H_sample) < -0.2，H = 环采样高 − 脚高）——v3 反向取用，见 D2 |
| 终止 | body 碰撞 + 大倾角 + 力矩超限 |
| PPO | lr 5e-4、decay 0.9999/iter、γ 0.996、epochs 2、clip 0.2、entropy 0.005、GAE 0.95、batch（minibatch 尺寸）8300 |
| student | GRU 2×50；g_a/g_b {64,64}；belief 120；L_bc+0.5L_re；噪声 z^{8×4} 三条件 60/30/10（局首+局中切换）+ c_sk 线性课程；S9：GRU>MLP、gate 小噪声增益最大 |
| repo 差异数量级 | undesired_contacts -1.0 恒定 vs 论文 -0.1·c_k；torque -1e-5 vs -1e-6·c_k；q̈ -2.5e-7 vs -1e-3·c_k；ω_xy -0.05(L2) vs -0.4(L1)；侧向速度惩罚缺项；flat_orientation/dof_pos_limits 均禁用 |
| rsl_rl 5.4.2 扩展点（本机验证） | `resolve_callable` 支持 `"module:Class"`（utils.py:97）；actor/critic/algorithm 点路径解析（ppo.py:416-418）；student/teacher/algorithm 同（distillation.py:238-240）；obs 组 `resolve_obs_groups`（utils.py:177） |
| 注册机制（pinned 树验证） | `isaaclab_tasks/__init__.py` 仅 `import_packages` 自家子包树 + builtins 防重入 guard，**无第三方 entry-point 发现** → shim 1 行为最小不可消耦合 |
| Phase 2 现成件 | rsl_rl 自带 `Distillation` 算法 + `DistillationRunner`/`StudentTeacher(Recurrent)` 配置（isaaclab_rl `rsl_rl/distillation_cfg.py:24,55,87,119`）；BC 现成；belief encoder 接 `student.class_name` 点路径、L_re 接 `algorithm.class_name`（subclass `Distillation`），零 fork |

## 9. 验收、风险、依赖

**验收**：v3 vs v2 同 eval seed 对照**仅 nominal 模式**（v3.1 修口径矛盾：robust /
fall_rate 因 DR reset 化 + tilt 终止语义差异跨版本不可比，只做 v3 内部基线，与风险表
一致）；**不设中途达标门**（v3.2 用户拍板：500 iters 级别站都玄乎，趴窝率 / c_k 达标
判据无判读意义）——起步 sanity（~100 iters 内：无 NaN、非零 reward、终止计数正常）
后直接 4000 iters，验收一律以训完 harness eval 为准；中途趋势观察仅诊断用，不作门。

| 风险 | 缓解 |
|---|---|
| rsl_rl class_name 注入点上游重构 | pin check 补符号；升级 IsaacLab 必跑 |
| 4×52 射线开销 > 135 | C3 冒烟计时；超预算降 40 点/脚并记录偏差 |
| DR reset 化 → v2/v3 不可直接比 | 版本隔离即目的；对照只在 v3 内部做 |
| tilt 0.6 是估计值 | 进 yaml 当消融变量；训练早期盯 harness fall_rate + 终止计数 |
| **belly-down 趴窝敞口**（无接触终止；tilt 抓不到水平趴卧，§2.3 根因①敞口保留） | 训练早期盯 undesired_contacts 惩罚能否压住趴窝；复现则按序升级：① 接触惩罚 -1→-5（§2.3 候选，纯奖励杠杆）② tilt 收紧 ③ 最后才重议躯干终止（挪 v4，可逆） |
| 脚环挂动脚，obs 非平稳性变化 | 训练早期观察 extero 分布；必要时改名义脚位固定偏移 |
| B2 obs dict 透传未端到端验证 | 实现日 30 分钟确认；不通即退回单向量+偏移切片（F1 升级为偏移强断言），B 其余项不受影响 |
| c_k 弱惩罚期（前 ~100 iter）趴窝复发 | 接触罚豁免 c_k 已兜一层；复发先抬 c_0（0.2→0.5）再谈终止（D3） |
| 单 seed 趴窝复发误判 | 复发结论需第二 seed 复现再动激励（换 seed 不升版本，NOTES 记 seed） |

**依赖链**：D0 → A ∥ G → B ∥ C → D → E → F → 起步 sanity → 训练。

## 10. 修订记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-09-01 | v3 初稿 | 全仓 code review + 论文全文核实产出 |
| 2026-09-01 | G0 迁移 | 包名 lizard_exp→rl_exp、versions 家族分层、本文件移至 versions/lizard/v3/PLAN.md（详见 §7.5 状态表） |
| 2026-09-01 | v3.1 | 二轮 review 修复（论文 S1–S9 复核 + 代码验证 + 用户拍板）：① D1 tilt 符号修正 `projected_gravity_b[2] > -0.6`（原稿 `< 0.6` upright 恒真 → 起步全灭；证据 eval.py:176）② D2 r_fc 语义修正：论文罚"抬太高"（max(H_sample)<-0.2），原稿方向反了且不可"照抄论文"；改标有意偏差（防拖脚）+ 补 swing 判定（接触态代理）与地形基准（每脚垂直射线，环无中心射线）③ D3 c_k 定案：c_0=0.2（yaml 消融变量 0.05/0.2/0.5）、env 步数计数推导机制（零 runner 改动、不挂 CurriculumTerm）、接触罚豁免 c_k（论文靠 body 碰撞终止兜底、我们砍了）、乘子收敛为 4 现存项 ④ D4 DR range 动态缩放机制补（自定义 event func 读 c_k buffer）⑤ 新增 §6.5 v3 奖励定案总表（原稿 term 集未定）⑥ E3 超参补全 S1 全 8 项 + lr decay 0.9999（subclass runner 衰减）+ batch 8300 尺寸→个数换算 ⑦ B4/B5 补 f_π 输入段序恒等（[proprio 90 \| l_e 96 \| l_priv 24]）+ normalizer 迁移 + L_re 目标偏差注记 ⑧ C2 字段名修正 attach_yaw_only ⑨ 验收口径矛盾修正（v2/v3 仅 nominal 可比）+ §6 验证行 fall_rate 口径同步 ⑩ F3 偏差声明清单扩充 ⑪ 风险表补 c_k 弱惩罚期与单 seed 两行 ⑫ §8 奖励/PPO 行数值补正 |
| 2026-09-01 | v3.1.1 | v3.1 修复合入 G0 迁移后的本文件（路径/G 状态保留迁移版）；旧路径副本 lizard_exp/PLAN_V3.md 删除 |
| 2026-09-01 | v3.1.2 | 用户勘误："不用cfg"实为"不用CPG"（笔误）。D2 swing 判定保持接触态代理并补"用户拍板"标记（文档本就未用 CPG）；撤回 v3.1 的"不设消融档"（系对该笔误的误读），c_0 恢复 yaml 消融变量（0.05/0.2/0.5） |
| 2026-09-01 | v3.1.3 | 闸门自定位修复（G3 部分）：junction 布局随 G2 删除后 framework_pin_check 自动探测失效——run_offline_checks.bat 自解析 `RL_ISAAC_ROOT`（缺省 E:\IsaacLab）+ venv python（缺省 `<root>\env_isaaclab\Scripts\python.exe`，回退 PATH python）；framework_pin_check 环境变量 ISAACLAB_ROOT→RL_ISAAC_ROOT 与 G3 命名统一。全新 shell 零环境变量闸门 4/4 绿 |
| 2026-09-01 | v3.1.4 | G3 剩余（harness 侧 _ISAAC_ROOT 参数化）移仓根 PLAN.md 挂账 #12——harness 是共享测量仪器（换家族后仍在），其工作不属 lizard 配方版本管理；升级触发（高频变更/多机器人/协议 v2 → versions/harness/vN）写入挂账行。versioning.mdc 分层原则补范围边界 |
| 2026-09-01 | v3.2 | 用户拍板砍中途达标门：500 iters 策略未成形（站都玄乎），趴窝率 / c_k 达标判据无判读意义——改起步 sanity（~100 iters 内无 NaN / 非零 reward / 终止计数正常）+ 直训 4000 iters，验收一律以训完 harness eval 为准，中途趋势观察仅诊断用；§9 风险表与依赖链"冒烟"措辞同步（C3 实现冒烟不动） |
| 2026-09-01 | v3.2.1 | G3 剩余与 harness 版本记录移 `ablation_harness/HARNESS.md`（自有版本文档，编号独立于家族配方版本；用户拍板：仓库不拆、只拆版本文档）——PLAN.md #12 留指针、G3 行改指。versioning.mdc 范围边界同步 |
| 2026-09-01 | v3.3 | A–F 全量实施落地（D0-1 方案 A / D0-2 reset 化用户拍板后），实施偏差四项记录：① C2 字段名实况——pinned 树（28a37ce）`RayCasterCfg` 用 `ray_alignment="yaw"`（v3.1 注记的 `attach_yaw_only` 在此版本不存在，语义一致：起点随 yaw 旋转、方向世界系固定），已按实况实现 ② D3 乘子实挂 3 项（q̈/torque/ω_xy）——计划的 feet_slide 非本仓 stock 奖励项（计划笔误），按"不新增缺失论文项"纪律不补 ③ D4 friction 保持 startup 模式（F3 偏差：foot_friction_truth 特权 obs 的材质读回缓存只在 startup 语义下有效，reset 化会让特权 obs 陈旧；DR 课程覆盖 mass/com/inertia/gains/joint 五项）④ D3 c_k 机制落地为纯函数推导（`ck_value(env)` 直读 `common_step_counter` + `init_ck` startup 事件存参数）——无 reward/event 更新时序依赖（rewards 先于 interval events 计算），PLAY/eval 不接 init_ck 时退化恒 1.0。另：B2 dict 透传经源码级确认（vecenv_wrapper.py 原生 TensorDict 包装，无需 fallback）；C3 计时实测 4096 env v3 121.8 vs v2 105.8 ms/step（+15%，预算内，无需 40 点降配）；E3 num_mini_batches=11 静态值（4096×24/8300 换算，换 env 数需同步改） |
| 2026-09-01 | v3.3.1 | 家族之家 consolidation：FAMILY.md / PLAN.md / lizard.urdf / 开发态 lizard_params.yaml 移入 versions/lizard/（rl_exp 根只剩代码；对齐规则路径约定，lizard 历史例外解除）；9 个代码消费点改路径（family cfg dev-yaml / pipeline ×3 / parity dev-yaml 契约 / archive ×2）；asset_lock 四版重生成（v3 首次上锁）；闸门 8/8 绿 |
| 2026-09-01 | v3.4 | 地形 Miki 对齐（新增 §6.6）：`TEACHER_TERRAINS_CFG_V3`——台阶顶 0.35→0.55m（review 定案，估计值）、+stepping_stones .1（open/ledged 近似，`用户拍板：选项 b 2026-09-01`，holes_depth −1.0）、boxes .2→.1；V3.__post_init__ 换引用，v1/v2 冻结生成器与 family 零改动（D0-5 保持）；粒子滤波课程不做；归因声明：训练地形变难、eval 套件不动，v3 对 v1 nominal success 可能不升反降，跨版本对账以逐地形 completion 为准。纪律边界：本修订合法仅因 v3 未训练——已训版本改地形一律 vN+1 |
| 2026-09-01 | v3.4.1 | §6.6 补记（不改方案实质）：0.55m 运动学核算（提脚够/躯干勉强/顶排或不可爬 + 降档判据）；澄清子地形比例为本地设计非论文口径（论文无比例表） |
| 2026-09-01 | v3.5 | 用户 review 指出收敛风险成立：v3.4 抄了论文难度、没抄课程护城河。修正 = V3 快照 `max_init_terrain_level 5→0`（从最易排起步，stock 行课程为粒子滤波的离散等价，init=0 是等价成立前提），偏差声明②同步；v1/v2 冻结快照不动。教训入 §6.6：地形难度与课程起点必须成对评审，只抬难度不改起点 = 反论文 |
| 2026-09-01 | v3.6 | 回放诊断三修（v1 checkpoint 蠕动根因 = 指令上限 1 m/s 下蠕动即最优，`用户拍板：2026-09-01`）：① 速度课程接入——V3 挂 `speed_curriculum`（StagedCurriculumTerm 复用，档位 (-1,2)→(-1,3)→(-1,4)→(-1,5)，门 = success_rate≥0.8 持续 120s，够不着的档永不到达；初始指令范围同步 (-1,2)；V3_PLAY 掐课程定固定 (-1,5)）；② base_contact 终止删除——执行 D0-6 拍板（肚皮接触只罚不终止，undesired_contacts -0.2 奖励仍在；实况：已训机体不翻倒，sprawled 低趴误杀敞口大于收益）；③ 碎石粗化——random_rough downsampled_scale 0.3m + noise (0.06,0.2)，§6.6 表同步。边界：v1/v2 冻结快照零改动；旧 v1 checkpoint 回放行为不变（蠕动是训练产物，非 env 可救） |
| 2026-09-01 | v3.6.1 | 训练启动实证（勘误，不改方案实质）：4096 env 下 PhysX `collisionStackSize` 溢出（默认 2**26 需 ≥67,137,584 字节，接触被静默丢弃 = 非确定性物理）。根因 = v3.6②的必然后果：趴地机器人不再被终局清场（趴平无倾角，tilt 也不触发），肚皮接触常驻 + 踏脚石接触对。修复：V3 `gpu_collision_stack_size = 2**28`（4× 余量）；v1/v2 冻结 cfg 保持 stock 值 |
| 2026-09-02 | v3.6.2 | 勘误（机制 bug 修复，不改配方实质）：TB 实证 v3.6①速度课程 gate 恒读 0（`Curriculum/speed_curriculum/metric=0`、stage 恒 0，而 `Metrics/success_rate` 已达 0.36）——`_reset_idx` 里 `curriculum_manager.compute()` 先于 `command_manager.reset()`，且 `CommandTerm.reset` 记完即清零 buffer，gate 读 `command.metrics[...].mean()` 永远为 0，档位 3/4/5 永不可达。首跑（2048 env，5000 iter）实际全程等效 stage 0 (-1,2)。修复：`StagedCurriculumTerm._gate_metric` 改读 `env.extras["log"]["Metrics/…"]`（上次 reset 批次的标量）+ EMA（`metric_ema_alpha` 默认 0.05）；单测改走真实通道，闸门 8/8 绿。文档：pitfalls P002。纪律：配方档位/阈值不动，仅机制修复；下一训练版本从修复后代码起跑即 v3.6 名义配方 |
