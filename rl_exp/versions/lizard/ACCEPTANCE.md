# 验收记录（运行时）

按 `ARCH_PLAN.md` v0.12「验收记录通则」保存：每次验收记检查编号、任务 id、命令、代码/框架与资产摘要、
设备与 env 数、seed、输入 checkpoint/样本摘要、预设容差、实际结果、证据路径与通过/失败/未知。

**该通则明确：验收标准是实施要求，不等于已通过。** 本文只记**实际跑过**的东西；未跑、前提不满足、证据缺失一律
记「未知」，不算通过。离线闸门（`run_offline_checks.bat`）的通过不能替代真跑或隔离重建。

---

## 1.2b · 运行记录运行时验收（2026-09-15）

### 共同前提（本批所有检查共用）

| 项 | 值 |
|---|---|
| 任务 id | `Lizard-Rough-v14`（注册表核验通过；`params_version=v14`） |
| 代码摘要 | Robot（本仓）rev `98faef89b626`（R1/R3）、`cc1b2e7083ec`（R5/R6）；工作树干净 |
| 框架摘要 | IsaacLab + rsl_rl 源码树同 rev `28a37cecdd43`，rsl_rl 为 editable；fork 补丁未提交差异 286 行（摘要已入记录，内容未存 → 见 #18 口径） |
| 资产摘要 | `versions/lizard/v14/asset_lock.json`，83 文件，manifest sha256 `0f831506e0616fc0`（allow-list，非依赖闭包） |
| 配方摘要 | golden `b5348330fb416786`（框架组合 `isaaclab=28a37cecdd43\|rsl_rl=source:28a37cecdd43\|python=3.12.13`）；会话覆盖 57 处（`--num_envs`/seed/device/log_dir 等） |
| 设备与规模 | 单卡 `cuda:0`，64 env，`sim_dt=0.005`，`control_dt=0.02` |
| seed | 42 |
| 容差 | 本批为结构/摘要/行为比对，**无数值容差**；涉及张量位级比较的 A/B 层属 1.4 |
| 验证命令 | `python -m rl_exp.tools.runrecord.manifest --verify <run_dir>`（cwd 本仓） |

训练命令统一形态（cwd `E:\IsaacLab`）：
`python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v14 --headless --num_envs 64 --max_iterations 2`

### 检查与结果

| 编号 | 检查 | 输入/操作 | 实际结果 | 证据路径 |
|---|---|---|---|---|
| R1 | 记录完整 + 声明=实际 | 干净树全新 run | **通过**：T0/T1 齐、T1 摘要可重算 `c71fd57d4d532202`、声明/实际 5 项一致（num_envs 64、sim_dt、control_dt、seed、params_version） | `logs/rsl_rl/lizard_rough_teacher_v14/2026-09-15_15-30-08` |
| R1′ | 快照格式 2 下的全新 run | golden 重基线后重跑同一命令 | **通过（配方项）**：`recipe: reviewed golden unchanged (3c6439cea8e2)`；记录已带 `golden_combination` / `golden_snapshot_format=2`。其余 2 项未知，原因见下表 | `…/2026-09-15_15-58-41` |
| R2 | ① 运行时动态加载的类进 T1 | R1 | **通过**：`resolved_algorithm=rl_exp.tasks.teacher_networks:DecayingLrPPO`，`resolved_models={alg.actor, alg.critic} = rl_exp.tasks.teacher_networks:SplitEncoderModel`（真·runner 构造期导入，非配置字符串） | R1 `run_manifest.json: stages.ready_to_learn` |
| R3 | ② 有意的 lr 配置差异 | 复制 R1 的 run 目录为 fixture，改写其 `model_1.pt` 的 optimizer lr 5e-4→1e-4（**原 run 未改**；fixture 内记录文件已删，避免被误当 run 记录），再 resume | **通过**：`learning_rate={declared_by_recipe: 5e-4, effective: 1e-4, agrees: false, source: "checkpoint optimizer state overrode the recipe (resume)"}`；`resume={resumed: true, source_sha256: c0c90518…, loaded_iteration: 1}` | fixture `…/2026-09-15_15-30-08_lr104`；恢复 run `…/2026-09-15_15-31-28` |
| R4 | 可重建（代码/资产/配方/载荷） | R1（格式 1 记录） | **通过 5 项 / 未知 2 项**：repository rev 与 diff 摘要一致；assets 83 文件一致；2 个 ckpt 文件哈希一致；**无法核验**：① IsaacLab 树内 `source/isaaclab_tasks/…/velocity/config/spider/` 未跟踪代码（#18）；② 该记录早于快照格式标签，配方摘要差值 `b5348330fb41 → 3c6439cea8e2` **无法归因**于配方变化还是口径变化——独立证据见下节：该差值只由 ClassVar 路径造成，没有任何配置值改变 | R1，`--verify` 输出 |
| R5 | ③a 构造失败 ⇒ 无最终 T1 | `--num_envs 0 --max_iterations 1`（不改任何输入） | **通过**：T0 已落盘、`env_constructed`/`ready_to_learn` 缺失、无 T1 摘要；`--verify` 退出 1（`RUN_MANIFEST_DRIFT`） | `…/2026-09-15_15-33-25` |
| R6 | ③b 恢复失败 ⇒ 无最终 T1 | `--resume --load_run 2026-09-15_never_exists_zzz` | **通过**：`get_checkpoint_path` 抛 `ValueError: No runs present …`，T0 只有启动声明，无 T1；`--verify` 退出 1 | `…/2026-09-15_15-33-58` |
| R7 | ③c 引用漂移必须失败 | **副本注入**：复制 R1 记录，改 `declaration.assets.manifest_sha256`，**并重算 T1 摘要**（连伪造摘要一起做） | **通过（按预期判失败）**：退出 1，`BLOCKING: assets: content differs from the recorded lock` | 副本 `%TEMP%\rm_inject_asset_drift`；脚本 `%TEMP%\rm_2b_inject.py` |
| R8 | ③d 未声明来源不得算通过 | **副本注入**：删除记录中的 `code.rsl_rl` 来源，重算 T1 摘要 | **通过（按预期不得算通过）**：退出 2，`NOT CLAIMED: rsl_rl: not recorded` | 副本 `%TEMP%\rm_inject_undeclared_source` |
| R9 | 负对照：原记录不受污染 | 以上全部操作后复核 R1 | **通过**：T1 摘要仍为 `c71fd57d4d532202`，退出码与 R1 相同（2，唯一必需未知仍是 spider/） | `…/2026-09-15_15-30-08` |
| R10 | 回归纪律：修前必失败、修后同记录通过 | 用**新**验证器复核修复前的真跑记录 | **通过**：同一条 run（修复前产物）旧实现判 `recipe: 失败`/退出 1，新实现判 `recipe: 通过`；`resolved_policy` 由 `None`（旧）变为 actor/critic 双模型（新） | `…/2026-09-15_15-24-34`（修复前记录） |

### 本批期间的 golden 重基线（已审查差异，非消警）

| 项 | 内容 |
|---|---|
| 变更 | 快照格式 **1 → 2**：`ClassVar` 成员不再进入快照（IsaacLab 的 `_usd_*` USD API 提示；本仓 `REQUIRES_CURRICULUM_STATE`）。理由：`ClassVar` 是"关于配方的声明"，不是配方数据；`configclass` 会把它拷到实例上，导致**改声明看起来像改配置** |
| 审查方式 | `--update --reason "<上述理由>"`，工具先逐字段打印差异 |
| 实际落子 | 34 个任务各 **12 条** ClassVar 路径离开（6 个 PLAY 任务另有 1 条 `REQUIRES_CURRICULUM_STATE`）；lock 由 2674 KiB 降到 2642 KiB；**没有任何配置值改变** |
| 复核命令 | `git diff -- rl_exp/versions/lizard/cfg_lock.json`（可逐条核对只有 ClassVar 路径被删） |
| 影响 | 格式 1 记录的配方项一律降级为**未知**（不可比），不得据旧摘要判失败或通过；格式 2 之后的 run（R1′）配方项判通过 |


### 本批未覆盖（不得据本批宣称通过）

- **1.5 隔离重建**：无重建记录，`已验证重建` 恒为**未知**（非必需项，不影响其它结论）。
- **1.4b C 层代表任务**（c_k-only `v3`、行 SIR `v14`、joint SIR `v12` 的真续训）：**未执行**。
- **1.3a S01–S10**（载荷/指纹/损坏/边界/兼容）：属 1.3 那轮，**未执行**；本批只用到"声明不进配置数据"（S09 的一部分，见下节）。
- **S10 的接口缝**：`apply_resume_state` 的 outcome dict 目前**未进 T1**（fork 补丁丢弃了返回值）→ 待补，之后 manifest 才能直接引用恢复的实际结果。
- **无归档的"可取回"项**：一律保持未知（`PLAN.md` #18），本批不因此判失败，也不提升为通过。

### 已知瑕疵（不阻塞本批，需另行处理）

- fork 补丁仍以 `weights_only=args_cli.weights_only` 调用，即使未使用该开关也会打印一行 `DEPRECATED: weights_only= is now drop_curriculum_state=`。应在新补丁里改传 `drop_curriculum_state`，旧 CLI 名保留为别名。
- IsaacLab 树内 `source/isaaclab_tasks/…/velocity/config/spider/` 未跟踪 ⇒ 该树所有 run 的 isaaclab 来源项都会记未知。需在树里提交或删除该目录，才能让这一项可判通过。
- `REQUIRES_CURRICULUM_STATE` 的声明目前只落在 `*_PLAY` 变体（`False`）上，**基类的 `True` 声明缺失**，因此 `V14.REQUIRES_CURRICULUM_STATE` 取不到值（`AttributeError`）。属 1.3 那轮未完的部分；本批未依赖它（`requires_resume_state` 走的是 wire 了注册 term 的路径）。
- 本批期间该声明与快照 ClassVar 排除曾在并发编辑中一度消失（快照排除已按原设计恢复）；`cfg_snapshot.py` 同一时间被两方写入，后续应避免同文件并发编辑。

