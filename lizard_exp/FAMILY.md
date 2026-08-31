# Lizard 训练家族总文档

> 一个版本 = 一代训练配方（参数冻结副本 + 版本文档 + 训练记录）。代码共享继承，
> 参数严格按版本隔离：跑 v1 只读 `versions/v1/lizard_params.yaml`，v2 读 v2 的，
> 开发态 `lizard_params.yaml` 的修改永远不影响已冻结版本。
> 训练计划/挂账见 [PLAN.md](PLAN.md)；评测协议见 ablation_harness 与
> skill `isaaclab-eval-harness`。

## 当前状态

- 活跃冻结版本: **v2**（2026-08-31，特权 obs 论文对齐补全，266 → 308 维；
  yaml 与 v1 逐字相同，纯代码级变更。v0/v1 均未训练，v0 = 全量 DR 对照存档）
- teacher 训练: 待启动（PLAN 挂账 #3，v2）
- 开发态 yaml: `lizard_params.yaml`（家族活实验用，改动不追溯）

## 任务注册表

| 任务 id | env cfg | 参数来源 | 说明 |
|---|---|---|---|
| Lizard-Velocity-Flat-v0 | `LizardFlatEnvCfg` | 开发态 | 家族平地基座（活实验） |
| Lizard-Velocity-Flat-Play-v0 | `LizardFlatEnvCfg_PLAY` | 开发态 | 同上，回放 |
| Lizard-Velocity-Curriculum-Flat-v0 | `LizardCurriculumFlatEnvCfg` | 开发态 | 三课程平地变体 |
| Lizard-Velocity-Rough-v0 | `LizardRoughEnvCfg` | 开发态 | 家族粗糙地形（活实验） |
| Lizard-Velocity-Curriculum-Rough-v0 | `LizardCurriculumRoughEnvCfg` | 开发态 | 三课程粗糙变体 |
| **Lizard-Rough-v2** | `LizardRoughTeacherEnvCfg` | **versions/v2（冻结）** | teacher Phase 1（特权 actor，最新） |
| Lizard-Rough-Play-v2 | `LizardRoughTeacherEnvCfg_PLAY` | **versions/v2（冻结）** | teacher 回放 |
| Lizard-Rough-v1 | `LizardRoughTeacherEnvCfg_V1` | versions/v1（冻结） | v1 配方复现入口（obs 266） |
| Lizard-Rough-Play-v1 | `LizardRoughTeacherEnvCfg_V1_PLAY` | versions/v1（冻结） | v1 配方回放 |

注：teacher 任务 id 与配方版本同步，且**全部常驻注册**——旧版本不会因代码
演进而失复现（机制见下节"版本差异结构"）。`Lizard-Rough-v0` 无任务 id
（未训练存档，复现走 git 历史）。家族任务 id 的 `-v0` 是 gym API 版本后缀，
与配方版本无关。

## Teacher 特权 obs 布局（v2，本文档为 SSOT）

teacher（`Lizard-Rough-v2`）policy obs 共 **308 维**，拼接顺序：

| 段 | 维度 | 来源 | 论文对应 |
|---|---|---|---|
| proprio（带噪） | 90 | lin_vel 3 + ang_vel 3 + gravity 3 + cmd 3 + jpos 26 + jvel 26 + last_action 26 | Proprioception（论文 131 维含历史/CPG，我们无历史——蒸馏时 student 侧补） |
| height_scan（干净） | 135 | height_scanner 15×9 网格 | Exteroception |
| **存量偏差 ①** 真值速度 | 6 | `base_lin_vel_true` / `base_ang_vel_true` | ⚠️ 论文无（body velocity 在 proprio 里）；保留决策 B |
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

**版本差异结构（复现机制）**：`teacher_env_cfg.py` 的
`TEACHER_PRIVILEGED_SPEC`（版本 → 增量 term 集合）是代码级版本差异的唯一
真源；基类 wire 全部 term 后按 spec 剥离本版本不含的。每版本一个一行子类
（override `params_version`）+ 常驻任务 id，任意版本可从工作树直接跑。
**纪律：已发布 term 的实现永不改语义，新版本只加 term**——违反即破坏所有
旧版本复现。git tag 仍是整树快照兜底。

## 版本历史

| 版本 | 日期 | 摘要 | 文档 |
|---|---|---|---|
| v0 | 2026-08-28 | 首版冻结：72kg、DR 全套、基线奖励（回滚态）、teacher 特权 obs。未训练即被 v1 取代，存档作全量 DR 对照 | [versions/v0/NOTES.md](versions/v0/NOTES.md) |
| v1 | 2026-08-31 | teacher 首跑：v0 仅 DR 段全部收窄（无一归零），验证"特权+锁脊柱+轻扰动"能否出步态。未训练即被 v2 取代，任务 id 常驻可复现 | [versions/v1/NOTES.md](versions/v1/NOTES.md) |
| v2 | 2026-08-31 | 特权 obs 论文对齐补全（+forces/normals/friction/thigh-shank/wrench 共 42 维，266→308）；yaml 与 v1 相同 | [versions/v2/NOTES.md](versions/v2/NOTES.md) |

## 代码地图（lizard_exp\tasks\，自有代码 100% 自包含）

```
lizard_exp\
├─ tasks\                            任务包（2026-08-28 从 fork 源码树收编）
│  ├─ __init__.py                    gym 注册表（全部 10 个任务 id）
│  ├─ lizard_env_cfg.py              家族平地基座（_load_params 支持版本参数）
│  │  ├─ rough_env_cfg.py            家族粗糙地形（LIZARD_ROUGH_TERRAINS_CFG）
│  │  │  └─ curriculum_rough_env_cfg.py  三课程粗糙变体
│  │  └─ curriculum_env_cfg.py       三课程平地变体 + LizardCurriculumActionsCfg
│  ├─ teacher_env_cfg.py             teacher 独立快照（params_version 类属性 +
│  │                                 TEACHER_PRIVILEGED_SPEC 版本差异表 + V1 子类，
│  │                                 零家族 import；obs 布局见上节）
│  ├─ teacher_mdp.py                 特权 obs term（接触/力/法线/摩擦/外力/air time/质量）
│  ├─ staged_curriculum.py           通用课程组件（原 velocity/mdp/ 收编）
│  └─ agents\rsl_rl_ppo_cfg.py       runner cfg（experiment_name 按任务族隔离）
├─ versions\vN\                      冻结参数副本 + NOTES.md + tb_scalars.csv
├─ tools\                            工具脚本（2026-08-31 分类归档）
│  ├─ pipeline\                      convert_urdf / convert_stl_to_obj / flatten_usd / export_ue
│  ├─ verify\                        teacher_smoke / smoke_test / position_check / pose_check
│  │                                 / joint_check / view_lizard / test_staged_curriculum
│  ├─ diagnose\                      debug_pose / diagnose_nan / inspect_blend / inspect_glb / dump_all_parts
│  ├─ trainlog\                      dump_tb / read_curriculum
│  └─ archive\                       patch_kfe_axis / patch_stance（仅考古）
├─ blender\                          站姿 SSOT + 骨骼修复 + URDF 生成
└─ ue\ / fork_patches\               UE Actor 组装 + 任务注册 shim
```

**fork 源码树仅剩两处占用**：

| 位置 | 内容 |
|---|---|
| `config\lizard\__init__.py` | 10 行 shim：sys.path 插入 IsaacLab 根 + `import lizard_exp.tasks`（`import isaaclab_tasks` 时自动触发注册） |
| `scripts\...\rsl_rl\play.py` | 键盘遥控回退补丁（6 行） |

**import 可达性**：venv site-packages 有 `lizard_exp.pth`（指向 E:\IsaacLab）→ `import lizard_exp` 全局可达。新机器摆位步骤见仓根 `README.md`。

## 记录体系（四层）

| 层 | 内容 | 位置 |
|---|---|---|
| 每迭代 | success_rate / reward / curriculum 曲线 | log 目录 TB 事件文件 → `dump_tb.py` 导 csv |
| 每次 eval | 协议跑分（nominal/robust/逐地形） | `ablation_harness/results/locomotion_eval_v1/` |
| 每版本 | 目的/改动/命令/结果/结论 | `versions/vN/NOTES.md` |
| 家族层 | 版本历史 / 任务表 / 代码地图 | 本文档 |

## 开新版本流程（vN → vN+1）

1. `copy versions\vN versions\vN+1`（含 yaml），改 `versions/vN+1/lizard_params.yaml` 参数
2. 写 `versions/vN+1/NOTES.md`（目的/假设/相对上版 diff）
3. 代码级结构变更（新 obs/reward/action term）走 **spec 结构**：
   - 基类 wire 新 term，`TEACHER_PRIVILEGED_SPEC` 加 `"vN+1": {...vN 集合, "新term名"}`；
     **禁止修改任何已发布 term 的实现**（会破坏旧版本复现）
   - `params_version` 类属性指到 vN+1，2 行子类 + `__init__.py` 注册 `Lizard-Rough-vN+1`/`-Play-vN+1`
   - 纯参数变更（yaml-only）不需要新任务 id：spec 里 vN+1 集合 = vN 集合即可
4. 训练 → `dump_tb.py` 导曲线 → `run_ablation.py` 跑 eval → 结果回填 NOTES.md
5. 版本历史表加一行；git 侧 commit + `tag vN+1` + push（tag = 整树快照兜底）

**纪律**：冻结目录只读（改 = 开新版本）；同配方换 seed 重跑不建新版本
（NOTES 记 seed 即可）；已发布 term 实现永不改语义。
