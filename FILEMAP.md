# FILEMAP —— 全仓文件地图（给下一个 AI / 新协作者）

> 读图顺序：`README.md`（仓定位 + 新机器摆位）→ 本文件（每个文件干啥）→
> `rl_exp\versions\lizard\PLAN.md`（训练计划与挂账，当前进度）→
> `rl_exp\versions\lizard\FAMILY.md`（任务注册表/版本历史/obs 布局/记录体系）。
> AI 开发守则见 `AGENTS.md`（IsaacLab 上游）+ `.codemaker\skills\tool\`（本项目 5 份 skill）。

## 仓根

| 文件 | 作用 |
|---|---|
| `README.md` | 仓说明：内容物 + 自装 Isaac Lab 要求 + 原机 junction 布局说明 |
| `AGENTS.md` | agent 工作守则（对抗性审查四问 / 先计划后动手 / 沟通语气）+ IsaacLab 官方守则（API 命名/工具链/commit 规范）；与 `ponytail.mdc` 重复的条目刻意不写 |
| `FILEMAP.md` | 本文件 |

## rl_exp\ —— 任务包（自包含核心）

### 文档与参数 SSOT（2026-09-01 迁移：家族级文件入 `versions\lizard\`）

| 文件 | 作用 |
|---|---|
| `versions\lizard\lizard_params.yaml` | **参数 SSOT（开发态）**：执行器 PD/动作缩放/命令范围/DR 范围。冻结版在 `versions\lizard\vN\`，跑冻结版永远不读这份 |
| `versions\lizard\lizard.urdf` | 机器人几何 SSOT（Blender 生成）：26 关节、质量、限位 |
| `versions\lizard\PLAN.md` | **纯意图文档（路线/备选路径/挂账清单）**：跨版本路线 + 决策记录 + 反趴窝备选升级表；时态纪律见 versioning.mdc（已成立事实归 FAMILY，方案细节归各 vN\PLAN.md） |
| `versions\lizard\FAMILY.md` | 家族事实总文档（现在时）：任务注册表 / 版本历史（含教训列）/ 当前状态 / 机体几何 / 四层记录体系（代码地图归本文件，开新版本流程归 `.codemaker/rules/versioning.mdc` §A） |
| `versions\lizard\OBS.md` | **obs 契约 SSOT（家族级）**：v1–v5 布局演进、论文对应、偏差声明（决策 B/v3 有意偏差）、`TEACHER_PRIVILEGED_SPEC` 版本差异机制（数值真源仍是代码 + check_obs_layout.py） |
| `versions\lizard\REWARDS.md` | **奖励用途总表（家族级）**：每 term 买什么行为/收什么税、公式+权重镜像、c_k 课程归属、v3 划脚事故的奖励经济学读法、版本差异摘要（数值真源仍是代码+各 vN yaml） |

### tasks\ —— gym 任务包（训练代码本体）

| 文件 | 作用 |
|---|---|
| `__init__.py` | 全部 14 个 gym 注册（家族 8 + teacher v1/v2/v3 各 train/play） |
| `lizard_env_cfg.py` | 家族平地基座：机器人装配 + DR 接线 + `_load_params`（版本参数机制） |
| `rough_env_cfg.py` | 家族粗糙地形（蜥蜴尺度化地形 + 高度扫描 obs） |
| `curriculum_env_cfg.py` | 三课程平地变体（骨骼/速度/转向，spine 可被课程锁放） |
| `curriculum_rough_env_cfg.py` | 三课程粗糙变体 |
| `teacher_env_cfg.py` | **teacher 独立快照**（只继承框架基类，零家族 import；`params_version` 类属性 + `TEACHER_PRIVILEGED_SPEC` 版本差异表，v1/v2/v3 子类常驻可复现；v3 = 三组 obs + 4×脚环 RayCaster + D 包接线，`RingPatternCfg` 环形 pattern 在此；spine 10 关节 scale=0 锁定） |
| `teacher_networks.py` | **v3 teacher 网络**：`SplitEncoderModel`（MLPModel 子类：g_e 每脚共享 {80,60}→24 / g_p {64,32}→24 / f_π {256,160,128}，三流各自 EmpiricalNormalization，f_π 段序冻结 [proprio\|l_e\|l_priv]）+ `DecayingLrPPO`（lr 0.9999/iter）；经 `class_name` 点路径注册，零 rsl_rl 改动 |
| `student_networks.py` | **Phase 2 接口锁**：`BeliefEncoder` GRU 2×50（b'=100）、`AttentionGate`/`BeliefMapper` {64,64}、`StudentPolicy`（f_π 输入 210 与 teacher 恒等）、`BeliefDecoder`（208+24）、`load_from_teacher`（g_e/f_π 权重 + o_p 归一化统计迁移 + 段序恒等断言） |
| `teacher_mdp.py` | 特权 obs term：真值速度/接触布尔/**力矢量/接触法线（warp 射线）/每脚摩擦/大小腿接触/持续外力**/air time/逐 body 质量（只增不改纪律）；v3 段 = D 包（c_k 纯函数课程 + tilt 终止 + `FootClearanceReward` 防拖脚 + reset 化 c_k 锚点缩放 DR 包装） |
| `play_utils.py` | **PLAY 共享工具**：`DR_EVENT_NAMES` + `disable_dr_events()`——全部 PLAY 变体的 DR 置空单一真源（与 harness 的 dr_controller 同步清单互指）；corruption 关闭遍历全部现存 obs 组（v3 无 policy 组） |
| `staged_curriculum.py` | 通用阶段课程组件（度量阈值+持续时长+依赖门控） |
| `agents\rsl_rl_ppo_cfg.py` | PPO runner 配置（experiment_name 按任务族隔离；`LizardTeacherV3PPORunnerCfg` = S1 超参 + obs_groups 三组 + SplitEncoderModel + DecayingLrPPO） |

### versions\ —— 参数版本冻结（**家族分层：`versions\<family>\vN\`，当前家族 = `lizard`**）

| 目录 | 作用 |
|---|---|
| `lizard\v0\` | 全量 DR 原始配方。**未训练即被 v1 取代**，存档作对照基准（复现走 git 历史） |
| `lizard\v1\` | v0 仅 DR 段收窄。**已训练 14000 iters 并出评测分**（2026-09-01，NOTES 回填）；任务 id `Lizard-Rough-v1` 常驻注册可复现（obs 266） |
| `lizard\v2\` | v1 参数 + 特权 obs 论文对齐补全（266→308）。NOTES.md 含验收线与判死刑信号 |
| `lizard\v3\` | **首跑完成，结果待回填**（2026-09-01 启动，2048 env × 4999 iter）：三编码器 + 脚环 extero 208 + tilt/r_fc/c_k/DR-reset 趴窝修复包 + **Miki 地形 v3.4**（`TEACHER_TERRAINS_CFG_V3`：台阶顶 0.55m + stepping stones，仅 v3 换用）+ v3.6 回放诊断三修。`PLAN.md` v3.6.2 + `NOTES.md`（含训练命令与装配验证记录）+ yaml（v2 全量 + `v3:` 段）+ asset_lock 齐备 |
| `lizard\v4\` | **已批准开工，未训练**（2026-09-02）：碎石地重定标——实测脚掌 0.46×0.51 m（v3.6 误用 kfe→foot 骨长 0.131），`TEACHER_TERRAINS_CFG_V4` random_rough 间距 0.3→0.5 m + 噪声 (0.10,0.35)/step 0.02；v3.6.1 collision stack 补丁回 stock。**启动前警示（先看地形）见 v4\NOTES.md**。yaml 与 v3 逐字相同 |
| `lizard\v5\` | **解冻修改中**（2026-09-03 撤 tag）：反划脚奖励包——r_fc 符号修正（+0.003→-0.003，v3 首跑收敛到"只有脚动身不动"划脚最优的根因之一）、r_slip（`feet_slide_ck` 接触脚滑速 ×c_k）、肚皮受力罚（防御项，`belly_contact_force` 连续 ‖F‖/706 恒权）、EP 线性跟踪（`track_lin_vel_xy_lin` 站立 0 分/倒退负分）替换 exp 核、命令 (0,3) 纯前进无速度课程。地形/obs/网络与 v4 相同。PLAN.md 含根因证据链与 F3 偏差声明 |
| `vN\PLAN.md` | 版本级计划存档（目的/假设/决策点/验收线/结论一句话；v3 原生，v0–v2 为 2026-09-01 追溯补录；结果回填仍走 NOTES） |
| `vN\NOTES.md` | 版本文档：目的/参数 diff/训练命令/结果回填 |
| `vN\tb_scalars.csv` | 训练后经 dump_tb.py 导出的逐迭代曲线 |
| `vN\asset_lock.json` | 冻结时资产 sha256（`lizard.urdf` + `lizard.usda`）。冻结 yaml 只钉路径不钉内容，此锁补这个洞：资产原地换代 → 常驻任务 id 复现被破坏 → 闸门⑥报警。有意换代在同一 commit 里 `--update-locks` |

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
| `tools\verify\teacher_smoke.py` | teacher 冒烟（v2）：obs 308 维 + 全特权段判读（MASS_SUM≈72 / 力矢量 / 法线 / 摩擦 / wrench=0）；per-term 布局从 observation_manager 现场推导，无魔数切片 |
| `tools\verify\teacher_smoke_v3.py` | teacher 冒烟（v3）：三组 90/208/83 + extero 顺序 lf/rf/rl/rr + tilt/r_fc 活性 + 有限性 + extero std>ε（防死通道回归） |
| `tools\verify\teacher_smoke_v5.py` | teacher 冒烟（v5 双环境）：PLAY（三组 90/208/83 + v5 奖励集合活性 + 无速度课程 + 无 SIR）+ TRAIN 2env（SIR 在真 TerrainImporter 上实例化、origin 重指落格内、Curriculum/terrain_levels 有限） |
| `tools\verify\test_v5_rewards.py` | v5 奖励离线单测（mock env）：线性核 8 case（站立 0/倒退负/超速封顶/min_speed clamp）/ feet_slide ×c_k / 肚皮罚不随 c_k 退火 / undesired_contacts ×c_k |
| `tools\verify\test_v5_terrain_sir.py` | v5.3 SIR 地形课程离线单测（mock env）：TerrainGenerator 列→类型映射复刻 / 初始 reset 跳过 + origin 重指一致 / 成功三态（存活×位移×命令距离）/ 软边带 / 带内重采样 / 流量不足保权 / 游走 clamp / replay 全历史池 / 块评估节流（240 步量化推进） |
| `tools\verify\check_obs_layout.py` | **obs 布局静态门**（离线）：v1/v2/v3 组名 + 组内 term 顺序 + extero 脚序 + 环形总点数 + c_k steps_per_iteration 与 runner num_steps_per_env 一致性（静默错位在 env 加载前炸出） |
| `tools\verify\test_teacher_networks.py` | SplitEncoderModel 离线单测：前向 shape / 梯度 / 三组归一化更新 / 命名子模块摘取 / JIT-ONNX 导出 / 契约违约 |
| `tools\verify\test_student_networks.py` | student belief 栈离线单测：GRU 步进 / α∈[0,1] / 门控槽对齐 / 解码器维数 / load_from_teacher 等价 + 段序失配 raise |
| `tools\verify\test_v3_curriculum.py` | v3 课程/几何离线单测：c_k 方向与热身长度 / 无参退化 1.0 / DR 锚点缩放 / tilt 判据 / 环形 pattern 几何（52 点逐环） |
| `tools\verify\time_foot_rings.py` | C3 性能风险项：v3 脚环 vs v2 网格在目标 env 数下的 ms/step + 显存（实测 4096 env +15%，预算内） |
| `tools\verify\smoke_test.py` | 家族平地冒烟：建环境 + obs 维度 + 10 步 |
| `tools\verify\position_check.py` | 落地检查：base 高度轨迹 + 四脚接触力（≈700N=全重）+ NaN 扫描，`--rough` 切粗糙 |
| `tools\verify\pose_check.py` | 静态几何打印：各 body 相对 base 坐标（头/四脚/尾） |
| `tools\verify\view_terrain.py` | Isaac Sim GUI 看机器人站**指定版本真实地形**（改名重写自 view_lizard：--task 任意注册任务、零动作保持、--steps headless 冒烟）；挂 robot-vs-terrain 接触点探针，逐步打印接触点数 vs 碰撞栈预算（v4 stock 2**26 重验） |
| `tools\verify\terrain_preflight.py` | **开训前地形预检**（skill `isaaclab-pretrain-check`）：离线生成全部子地形 + 粗糙度统计（foot-plate relief 核心指标）+ PNG 渲染到 `_tmp_terrain_previews\` |
| `tools\verify\joint_check.py` | reset 后打印关节角（验证默认位姿加载） |
| `tools\verify\check_dr_parity.py` | **契约漂移闸门（--strict 即 CI）**：① teacher vs 家族 DR wiring 行静态对比；② `play_utils.DR_EVENT_NAMES` 与 `dr_controller._DR_EVENT_NAMES` 两份列表同步；③ 全部 `*_PLAY` 类必须调 `apply_play_wiring`；④ 两侧 `ArticulationCfg` 字面块行比对；⑤ 资产结构契约（usda 文本 vs 各 yaml：joint_order/Geometry scope/base_link/body 模式，资产换代改名即报警）；⑥ 资产锁比对（见 `asset_lock.json`）。`--update-locks` 仅在有意换代资产的同一 commit 里跑 |
| `tools\verify\framework_pin_check.py` | **框架 pin 检查**：grep IsaacLab 源码树里我们依赖的内部符号（cfg.func 替换 / RayCaster.meshes / live PD 增益 / warp kernel 等）+ 比对已验证 commit `28a37ce`（perf-2026-06-24）；升级 IsaacLab 后第一件事 |
| `tools\verify\test_recovery_parity.py` | recovery 向量化 vs 朴素参考实现等价性（纯 torch，随机+6 组边界） |
| `tools\verify\test_staged_curriculum.py` | 课程组件离线单测（mock managers，不起仿真） |
| `tools\verify\run_offline_checks.bat` | **离线全套一键**（8 项：pin/parity/recovery/curriculum/teacher 网络/student 网络/v3 课程/obs 布局，秒级不起仿真）；改 tasks 或 harness 后、commit 前必跑 |
| `tools\diagnose\debug_pose.py` | reset 后立即 dump 全部腿关节轴心世界坐标 |
| `tools\diagnose\diagnose_nan.py` | Flat 任务 NaN obs 诊断（历史问题排查用） |

### 训练工具与 UE 导出

| 文件 | 作用 |
|---|---|
| `tools\trainlog\dump_tb.py` | TB 事件文件 → CSV（版本记录用：`--log_dir <run目录> --out versions\lizard\vN\tb_scalars.csv`） |
| `tools\trainlog\probe_run.py` | **训练中巡检探针**（skill `isaaclab-train-probe`，取代 read_curriculum）：`--exp v4`/`--run <目录>`/默认最活跃 run，只读 tfevents 出健康快照——进度+ETA（max_iterations 读 params/agent.yaml）、各 tag last/窗口均值/Δ% 趋势、终止计数、课程值、NaN/骤降/事件停更/ckpt 落后告警；秒级不起仿真 |
| `tools\trainlog\plot_tb.py` | tb_scalars.csv → 训练曲线 PNG（reward/终止/局长/课程/墙上时间五张，`--mark` 标已评测 ckpt，默认 200 DPI）；墙上时间由 `Train/mean_reward/time` 的 step 轴（引擎自记秒数）派生，不靠累加估计；`figure`/`series_to_figs` 供 `ablation_harness\plot_eval.py` 的 HTML 报告共用。**产物不入库**（可再生） |
| `ue\build_lizard_ue.py` | UE 编辑器脚本：按 `ue\lizard_ue.json` 组装蜥蜴物理 Actor |
| `fork_patches\config_lizard___init__.py` | fork shim 现成副本（装到 IsaacLab 树注册任务用） |
| `__init__.py` | 包声明（`import rl_exp` 入口，经 venv .pth 可达） |

## ablation_harness\ —— 评测系统（Locomotion-Eval-v1）

| 文件 | 作用 |
|---|---|
| `eval.py` | 统一评测 runner：task + checkpoint + 协议 + 模式 → eval.json |
| `run_ablation.py` | 消融调度器：spec yaml → 串行 train+eval → 汇总表，断点续跑；`--by-terrain` 出逐地形长表+pivot |
| `plot_eval.py` | 评测可视化（读组目录 eval.json，不起仿真）：`--report <版本目录>` → 单文件 HTML 汇总报告（训练曲线+评测图+summary 表+rev 溯源，**默认选它**）；`--out_dir` → 散图 PNG（只需贴图进工单时用）。两者均不入库 |
| `metrics.py` | 指标库：tracking/success/energy（PD 反解 τ）/fall 几何判定/completion |
| `suites.py` | 固定地形套件（9 地形确定性三锁：curriculum+等比例+单值难度+seed） |
| `components\command_player.py` | 命令时间线播放器（协议 yaml 是唯一真源） |
| `components\dr_controller.py` | nominal/robust 模式的 DR 开关变换 |
| `components\recovery.py` | recovery push：冲击注入 + 恢复计时（只统计冲击时仍在第一局的 env） |
| `protocols\locomotion_eval_v1.yaml` | **评测协议契约（冻结）**：6 段命令时间线 / kick 规格 / 阈值。改动 = 新建 v2 |
| `specs\example_baseline.yaml` | 消融 spec 示例 |
| `results\locomotion_eval_v1\` | 跑分落盘（记录即数据，随仓提交）。campaign 分组：`--group v1` → `locomotion_eval_v1\v1\<run_id>\` + 组内专属 `summary.csv`（全局指标）+ `terrains.csv`（逐地形长表，`--by-terrain` 生成）；`--summarize [--group v1]` 看单组或汇总 |

## .codemaker\skills\tool\ —— AI 开发技能（方法论）

| 技能 | 作用 |
|---|---|
| `isaaclab-task-creator` | Isaac Lab 任务创建方法论 + 运行时事实（log 命名/五元组/configclass 单例/ProxyArray） |
| `isaaclab-asset-pipeline` | 资产管线方法论（URDF→USD 坑/验证链/症状表） |
| `isaaclab-eval-harness` | 评测协议要点 + 指标口径 + 调度用法 |
| `isaaclab-train-probe` | 训练中巡检方法论（probe_run 用法 + 对照版本 NOTES 判读 + 汇报纪律） |
| `git-auto-sync` | 迭代完成自动 commit+push 云端（本项目 git 纪律） |

## 历史包袱提示（下一个 AI 注意）

- `smoke_test.py` / `pose_check.py` 2026-08-31 刚修过陈旧 bug（动作维度/旧命名），跑挂先查命名是否又变了
- `blender\build_rig.py`、`patch_*.py` 是管线早期一次性脚本，仅考古价值
- **`ablation_harness\results\...\summary.csv` 里 2026-08-28 两行的 `energy_per_m_j` 数值无效**（energy 修复前少乘 step_dt，虚高 ~50×）；其余列有效，energy 列重跑后才有意义
- 旧趴窝 checkpoint：`E:\IsaacLab\logs\rsl_rl\lizard_rough\2026-08-28_14-08-22`（15000 iters，家族 run，不在仓里）
