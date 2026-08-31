# Lizard 训练家族总文档

> 一个版本 = 一代训练配方（参数冻结副本 + 版本文档 + 训练记录）。代码共享继承，
> 参数严格按版本隔离：跑 v1 只读 `versions/v1/lizard_params.yaml`，v2 读 v2 的，
> 开发态 `lizard_params.yaml` 的修改永远不影响已冻结版本。
> 训练计划/挂账见 [PLAN.md](PLAN.md)；评测协议见 ablation_harness 与
> skill `isaaclab-eval-harness`。

## 当前状态

- 活跃冻结版本: **v1**（2026-08-31，teacher 首跑配方 = v0 全量 DR 收窄；
  v0 从未训练，作全量 DR 对照基准存档）
- teacher 训练: 待启动（PLAN 挂账 #3，v1 参数）
- 开发态 yaml: `lizard_params.yaml`（家族活实验用，改动不追溯）

## 任务注册表

| 任务 id | env cfg | 参数来源 | 说明 |
|---|---|---|---|
| Lizard-Velocity-Flat-v0 | `LizardFlatEnvCfg` | 开发态 | 家族平地基座（活实验） |
| Lizard-Velocity-Flat-Play-v0 | `LizardFlatEnvCfg_PLAY` | 开发态 | 同上，回放 |
| Lizard-Velocity-Curriculum-Flat-v0 | `LizardCurriculumFlatEnvCfg` | 开发态 | 三课程平地变体 |
| Lizard-Velocity-Rough-v0 | `LizardRoughEnvCfg` | 开发态 | 家族粗糙地形（活实验） |
| Lizard-Velocity-Curriculum-Rough-v0 | `LizardCurriculumRoughEnvCfg` | 开发态 | 三课程粗糙变体 |
| **Lizard-Rough-v1** | `LizardRoughTeacherEnvCfg` | **versions/v1（冻结）** | teacher Phase 1（特权 actor） |
| Lizard-Rough-Play-v1 | `LizardRoughTeacherEnvCfg_PLAY` | **versions/v1（冻结）** | teacher 回放 |

注：teacher 任务 id 与配方版本同步（`Lizard-Rough-v1` 读 versions/v1）；
`Lizard-Rough-v0` 已注销（v0 配方未训练即被取代，无 checkpoint 依赖）。
家族任务 id 的 `-v0` 是 gym API 版本后缀，与配方版本无关。

## 版本历史

| 版本 | 日期 | 摘要 | 文档 |
|---|---|---|---|
| v0 | 2026-08-28 | 首版冻结：72kg、DR 全套、基线奖励（回滚态）、teacher 特权 obs。未训练即被 v1 取代，存档作全量 DR 对照 | [versions/v0/NOTES.md](versions/v0/NOTES.md) |
| v1 | 2026-08-31 | teacher 首跑：v0 仅 DR 段全部收窄（无一归零），验证"特权+锁脊柱+轻扰动"能否出步态 | [versions/v1/NOTES.md](versions/v1/NOTES.md) |

## 代码地图（lizard_exp\tasks\，自有代码 100% 自包含）

```
lizard_exp\
├─ tasks\                            任务包（2026-08-28 从 fork 源码树收编）
│  ├─ __init__.py                    gym 注册表（全部 10 个任务 id）
│  ├─ lizard_env_cfg.py              家族平地基座（_load_params 支持版本参数）
│  │  ├─ rough_env_cfg.py            家族粗糙地形（LIZARD_ROUGH_TERRAINS_CFG）
│  │  │  └─ curriculum_rough_env_cfg.py  三课程粗糙变体
│  │  └─ curriculum_env_cfg.py       三课程平地变体 + LizardCurriculumActionsCfg
│  ├─ teacher_env_cfg.py             teacher 独立快照（TEACHER_PARAMS_VERSION="v1"，
│  │                                 只继承框架基类，零家族 import）
│  ├─ teacher_mdp.py                 特权 obs term（接触/air time/质量）
│  ├─ staged_curriculum.py           通用课程组件（原 velocity/mdp/ 收编）
│  └─ agents\rsl_rl_ppo_cfg.py       runner cfg（experiment_name 按任务族隔离）
├─ versions\vN\                      冻结参数副本 + NOTES.md + tb_scalars.csv
├─ blender\ / convert_urdf.py        资产管线
└─ 验证/工具脚本（teacher_smoke / position_check / dump_tb / ...）
```

**fork 源码树仅剩两处占用**：

| 位置 | 内容 |
|---|---|
| `config\lizard\__init__.py` | 10 行 shim：sys.path 插入 IsaacLab 根 + `import lizard_exp.tasks`（`import isaaclab_tasks` 时自动触发注册） |
| `scripts\...\rsl_rl\play.py` | 键盘遥控回退补丁（6 行） |

**import 可达性**：venv site-packages 有 `lizard_exp.pth`（指向 E:\IsaacLab）→ `import lizard_exp` 全局可达。新机器移植需重建此 .pth。

## 记录体系（四层）

| 层 | 内容 | 位置 |
|---|---|---|
| 每迭代 | success_rate / reward / curriculum 曲线 | log 目录 TB 事件文件 → `dump_tb.py` 导 csv |
| 每次 eval | 协议跑分（nominal/robust/逐地形） | `ablation_harness/results/locomotion_eval_v1/` |
| 每版本 | 目的/改动/命令/结果/结论 | `versions/vN/NOTES.md` |
| 家族层 | 版本历史 / 任务表 / 代码地图 | 本文档 |

## 开新版本流程（v0 → v1）

1. `copy versions\v0 versions\v1`（含 yaml），改 `versions/v1/lizard_params.yaml` 参数
2. 写 `versions/v1/NOTES.md`（目的/假设/相对 v0 的 diff）
3. 若有结构变更（reward/obs/actions 代码级）：cfg 子类只写差异
   （如 `LizardRoughTeacherEnvCfgV1(LizardRoughTeacherEnvCfg)`，改
   `TEACHER_PARAMS_VERSION` 引用或模块常量），`__init__.py` 注册 `Lizard-Rough-v1`；
   纯参数变更不需要新任务 id，直接 hydra override + 新版本目录
4. 训练 → `dump_tb.py` 导曲线 → `run_ablation.py` 跑 eval → 结果回填 NOTES.md
5. 版本历史表加一行

**纪律**：冻结目录只读（改 = 开新版本）；同配方换 seed 重跑不建新版本
（spec/NOTES 记 seed 即可）。
