# Lizard Teacher 特权 Obs 契约（家族级 SSOT）

> obs = **契约面**：定网络输入形状与 teacher↔student 蒸馏接口（L_re 重建目标），
> 被版本之外的系统依赖，故享家族级 SSOT（与 REWARDS.md 平级）。
> **数值真源仍是代码**：`teacher_env_cfg.py`（含 `TEACHER_PRIVILEGED_SPEC`）+
> `check_obs_layout.py` 静态断言 + `teacher_smoke_v3.py` 运行时核对——本文只做
> 语义镜像（约定同 REWARDS.md"数值真源仍是代码+各 vN yaml"）。
> 时态纪律：只收已成立事实；"待补/待改"住 PLAN.md 挂账（摩擦/外力真值 = 挂账 #4）。

## 演进总表

| 版本 | 形态 | 维度 | obs 变更要点 |
|---|---|---|---|
| v1 | 单向量 | 266 | 基线：proprio 90 + 干净网格扫描 135 + 特权段 41（布局见下） |
| v2 | 单向量 | 308 | 论文对齐补全 +42（forces/normals/friction/thigh-shank/wrench）；yaml 与 v1 逐字相同，纯代码级变更 |
| v3 | 三命名组 | 90+208+83 = 381 | 脚环 extero 208 替代网格扫描；三编码器输入契约（`teacher_networks.py` `OBS_GROUP_CONTRACT`） |
| v4 | 同 v3 | 同 v3 | spec 不变（纯地形 + 物理3 | 同 v3 | spec 不变（反划脚奖励包变更） |

## v1 布局（266，单向量，actor 全可见 critic 同源）

```
policy obs (266 维) =
    本体感受: lin/ang vel(带噪) + gravity + commands + joint pos/vel(26) + last_action(26)
  + 干净高度扫描 135 点（特权: 去 Unoise，保留 clip）
  + 真值线/角速度（特权: 无噪声对应项）
  + 腿接触状态 ×4（特权, contact 力值过阈 bool）
  + 摆动时长 ×4（特权, sensor current_air_time）
  + 全 body 质量真值 27（特权, body_mass 读回）
```

## v2 布局（308，单向量拼接）

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

## v3 布局（三组按名交付）

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

## 版本差异结构（复现机制）

`teacher_env_cfg.py` 的 `TEACHER_PRIVILEGED_SPEC`（版本 → 增量 term 集合）是
代码级版本差异的唯一真源；基类 wire 全部 term 后按 spec 剥离本版本不含的。
每版本一个一行子类（override `params_version`）+ 常驻任务 id，任意版本可从
工作树直接跑。v3 的组结构差异（三组拆分/脚环/奖励/DR）全部封装在
`LizardRoughTeacherEnvCfg_V3` 子类的 `__post_init__` 后处理里——v1/v2 路径零改动。
**纪律：已发布 term 的实现永不改语义，新版本只加 term**——违反即破坏所有
旧版本复现。git tag 仍是整树快照兜底。
