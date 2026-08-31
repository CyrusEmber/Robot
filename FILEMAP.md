# FILEMAP —— 全仓文件地图（给下一个 AI / 新协作者）

> 读图顺序：`README.md`（仓定位 + 新机器摆位）→ 本文件（每个文件干啥）→
> `lizard_exp\PLAN.md`（训练计划与挂账，当前进度）→
> `lizard_exp\FAMILY.md`（任务注册表/版本历史/obs 布局/记录体系）。
> AI 开发守则见 `AGENTS.md`（IsaacLab 上游）+ `.codemaker\skills\tool\`（本项目 4 份 skill）。

## 仓根

| 文件 | 作用 |
|---|---|
| `README.md` | 仓说明：内容物 + 自装 Isaac Lab 要求 + 原机 junction 布局说明 |
| `AGENTS.md` | IsaacLab 官方 AI agent 开发守则（API 命名/工具链/commit 规范） |
| `FILEMAP.md` | 本文件 |

## lizard_exp\ —— 任务包（自包含核心）

### 文档与参数 SSOT

| 文件 | 作用 |
|---|---|
| `lizard_params.yaml` | **参数 SSOT（开发态）**：执行器 PD/动作缩放/命令范围/DR 范围。冻结版在 `versions\vN\`，跑冻结版永远不读这份 |
| `lizard.urdf` | 机器人几何 SSOT（Blender 生成）：26 关节、质量、限位 |
| `PLAN.md` | 训练计划 + 挂账清单（#3 teacher 训练是当前关键路径） |
| `FAMILY.md` | 家族总文档：任务注册表 / 版本历史 / teacher obs 布局 SSOT / 代码地图 / 四层记录体系 |

### tasks\ —— gym 任务包（训练代码本体）

| 文件 | 作用 |
|---|---|
| `__init__.py` | 全部 10 个 gym 注册（含 teacher `Lizard-Rough-v1`） |
| `lizard_env_cfg.py` | 家族平地基座：机器人装配 + DR 接线 + `_load_params`（版本参数机制） |
| `rough_env_cfg.py` | 家族粗糙地形（蜥蜴尺度化地形 + 高度扫描 obs） |
| `curriculum_env_cfg.py` | 三课程平地变体（骨骼/速度/转向，spine 可被课程锁放） |
| `curriculum_rough_env_cfg.py` | 三课程粗糙变体 |
| `teacher_env_cfg.py` | **teacher 独立快照**（只继承框架基类，零家族 import；`params_version` 类属性 + `TEACHER_PRIVILEGED_SPEC` 版本差异表，v1/v2 子类常驻可复现；spine 10 关节 scale=0 锁定） |
| `teacher_mdp.py` | 特权 obs term：真值速度/接触布尔/**力矢量/接触法线（warp 射线）/每脚摩擦/大小腿接触/持续外力**/air time/逐 body 质量（只增不改纪律） |
| `play_utils.py` | **PLAY 共享工具**：`DR_EVENT_NAMES` + `disable_dr_events()`——全部 6 个 PLAY 变体的 DR 置空单一真源（与 harness 的 dr_controller 同步清单互指） |
| `staged_curriculum.py` | 通用阶段课程组件（度量阈值+持续时长+依赖门控） |
| `agents\rsl_rl_ppo_cfg.py` | PPO runner 配置（experiment_name 按任务族隔离：`lizard_rough_teacher` 等） |

### versions\ —— 参数版本冻结

| 目录 | 作用 |
|---|---|
| `v0\` | 全量 DR 原始配方。**未训练即被 v1 取代**，存档作对照基准（复现走 git 历史） |
| `v1\` | v0 仅 DR 段收窄。未训练即被 v2 取代，但任务 id `Lizard-Rough-v1` 常驻注册可复现（obs 266） |
| `v2\` | **当前活跃**：v1 参数 + 特权 obs 论文对齐补全（266→308）。NOTES.md 含验收线与判死刑信号 |
| `vN\NOTES.md` | 版本文档：目的/参数 diff/训练命令/结果回填 |
| `vN\tb_scalars.csv` | 训练后经 dump_tb.py 导出的逐迭代曲线 |

### 资产与管线（Blender → URDF → USD，工具在 `tools\` 下按类分目录）

| 文件 | 作用 |
|---|---|
| `blender\lizard_stance.blend` | **站姿 SSOT**（232KB）：自然站姿摆好、骨位已 fix |
| `blender\fix_bones.py` | Blender：把骨骼 head/tail 对齐到关节球网格 |
| `blender\generate_urdf.py` | Blender：从站姿 blend 导出 URDF + STL（限位/力矩在 AXIS_MAP 硬编码） |
| `blender\build_rig.py` | 历史一次性绑骨实验（硬编码桌面输出路径），已被上面两脚本取代 |
| `tools\pipeline\convert_urdf.py` | URDF → USD（Isaac Lab 训练用资产，输出 `assets\lizard\lizard.usda`） |
| `tools\pipeline\flatten_usd.py` | 压平 URDF-importer-3.0 层级（IsaacLab issue #5126 workaround） |
| `tools\pipeline\convert_stl_to_obj.py` | STL → OBJ 转换并重写 URDF 引用 |
| `tools\pipeline\export_ue.py` | SSOT → UE 工件（关节映射/参数打包，盲部署前置） |
| `tools\archive\patch_kfe_axis.py` | URDF 手术：kfe 轴 Z→Y + 对称限位（旧版一次性脚本，仅考古） |
| `tools\archive\patch_stance.py` | URDF 手术：把自然站姿烘进零位（旧版一次性脚本，仅考古） |
| `tools\diagnose\inspect_blend.py` / `inspect_glb.py` | 无头 Blender：dump blend 骨架层级 / glb 零件包围盒 |
| `tools\diagnose\dump_all_parts.py` | dump blend 全部散件 bbox + 球形度（关节球定位用） |
| `assets\lizard\lizard.usda` | 训练用 USD 资产（cfg 引用） |
| `meshes\` | URDF 用的 visual/collision 网格 |

### 环境验证与诊断（跑环境不训练）

| 文件 | 作用 |
|---|---|
| `tools\verify\teacher_smoke.py` | teacher 冒烟：obs 308 维 + 全特权段判读（MASS_SUM≈72 / 力矢量 / 法线 / 摩擦 / wrench=0）；per-term 布局从 observation_manager 现场推导，无魔数切片 |
| `tools\verify\smoke_test.py` | 家族平地冒烟：建环境 + obs 维度 + 10 步 |
| `tools\verify\position_check.py` | 落地检查：base 高度轨迹 + 四脚接触力（≈700N=全重）+ NaN 扫描，`--rough` 切粗糙 |
| `tools\verify\pose_check.py` | 静态几何打印：各 body 相对 base 坐标（头/四脚/尾） |
| `tools\verify\view_lizard.py` | Isaac Sim GUI 里看机器人（零动作持默认位姿） |
| `tools\verify\joint_check.py` | reset 后打印关节角（验证默认位姿加载） |
| `tools\verify\check_dr_parity.py` | **快照漂移检查**：teacher 与家族 cfg 的 DR wiring 行静态对比（快照复制纪律的防漂移闸门，改动任一 cfg 后跑） |
| `tools\verify\test_staged_curriculum.py` | 课程组件离线单测（mock managers，不起仿真） |
| `tools\diagnose\debug_pose.py` | reset 后立即 dump 全部腿关节轴心世界坐标 |
| `tools\diagnose\diagnose_nan.py` | Flat 任务 NaN obs 诊断（历史问题排查用） |

### 训练工具与 UE 导出

| 文件 | 作用 |
|---|---|
| `tools\trainlog\dump_tb.py` | TB 事件文件 → CSV（版本记录用：`--log_dir <run目录> --out versions\vN\tb_scalars.csv`） |
| `tools\trainlog\read_curriculum.py` | 从 tfevents 读课程终值（terrain level 等） |
| `ue\build_lizard_ue.py` | UE 编辑器脚本：按 `ue\lizard_ue.json` 组装蜥蜴物理 Actor |
| `fork_patches\config_lizard___init__.py` | fork shim 现成副本（装到 IsaacLab 树注册任务用） |
| `__init__.py` | 包声明（`import lizard_exp` 入口，经 venv .pth 可达） |

## ablation_harness\ —— 评测系统（Locomotion-Eval-v1）

| 文件 | 作用 |
|---|---|
| `eval.py` | 统一评测 runner：task + checkpoint + 协议 + 模式 → eval.json |
| `run_ablation.py` | 消融调度器：spec yaml → 串行 train+eval → 汇总表，断点续跑 |
| `metrics.py` | 指标库：tracking/success/energy（PD 反解 τ）/fall 几何判定/completion |
| `suites.py` | 固定地形套件（9 地形确定性三锁：curriculum+等比例+单值难度+seed） |
| `components\command_player.py` | 命令时间线播放器（协议 yaml 是唯一真源） |
| `components\dr_controller.py` | nominal/robust 模式的 DR 开关变换 |
| `components\recovery.py` | recovery push：冲击注入 + 恢复计时（只统计冲击时仍在第一局的 env） |
| `protocols\locomotion_eval_v1.yaml` | **评测协议契约（冻结）**：6 段命令时间线 / kick 规格 / 阈值。改动 = 新建 v2 |
| `specs\example_baseline.yaml` | 消融 spec 示例 |
| `results\locomotion_eval_v1\` | 跑分落盘（记录即数据，随仓提交） |

## .codemaker\skills\tool\ —— AI 开发技能（方法论）

| 技能 | 作用 |
|---|---|
| `isaaclab-task-creator` | Isaac Lab 任务创建方法论 + 运行时事实（log 命名/五元组/configclass 单例/ProxyArray） |
| `isaaclab-asset-pipeline` | 资产管线方法论（URDF→USD 坑/验证链/症状表） |
| `isaaclab-eval-harness` | 评测协议要点 + 指标口径 + 调度用法 |
| `git-auto-sync` | 迭代完成自动 commit+push 云端（本项目 git 纪律） |

## 历史包袱提示（下一个 AI 注意）

- `smoke_test.py` / `pose_check.py` 2026-08-31 刚修过陈旧 bug（动作维度/旧命名），跑挂先查命名是否又变了
- `blender\build_rig.py`、`patch_*.py` 是管线早期一次性脚本，仅考古价值
- **`ablation_harness\results\...\summary.csv` 里 2026-08-28 两行的 `energy_per_m_j` 数值无效**（energy 修复前少乘 step_dt，虚高 ~50×）；其余列有效，energy 列重跑后才有意义
- 旧趴窝 checkpoint：`E:\IsaacLab\logs\rsl_rl\lizard_rough\2026-08-28_14-08-22`（15000 iters，家族 run，不在仓里）
