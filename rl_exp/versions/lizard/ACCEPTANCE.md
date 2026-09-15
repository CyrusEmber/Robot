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
- **1.3a S01–S10**（载荷/指纹/损坏/边界/兼容）：**已执行（离线）**，见下节。
- **无归档的"可取回"项**：一律保持未知（`PLAN.md` #18），本批不因此判失败，也不提升为通过。

### 已知瑕疵（不阻塞本批，需另行处理）

- ~~fork 补丁仍以 `weights_only=args_cli.weights_only` 调用~~ **已修（1.3，2026-09-15）**：新补丁传 `drop_curriculum_state=args_cli.drop_curriculum_state or args_cli.weights_only`，旧 CLI 名保留为别名 + 一行弃用提示（仅在使用旧名时打印）；两条补丁插入点已解耦，`git apply --check --reverse` 各自幂等。
- IsaacLab 树内 `source/isaaclab_tasks/…/velocity/config/spider/` 未跟踪 ⇒ 该树所有 run 的 isaaclab 来源项都会记未知。需在树里提交或删除该目录，才能让这一项可判通过。
- ~~`REQUIRES_CURRICULUM_STATE` 的声明目前只落在 `*_PLAY` 变体（`False`）上，基类的 `True` 声明缺失~~ **已修（1.3，2026-09-15）**：基类声明落在 `LizardRoughTeacherEnvCfg_V5`（v6–v14 继承），8 个 `*_PLAY` 显式 `False`，V3/V4 不声明（其 staged 课程未覆盖，只 WARN）；属性名改为 dunder **`__requires_curriculum_state__`**（普通/`ClassVar` 命名都会经 `configclass` 的实例命名空间进快照，dunder 由两个序列化器一致跳过）。`curriculum_state.REQUIRES_CURRICULUM_STATE` 常量即该名字，改用 `getattr(type(cfg), ...)` 读取，不再有 `AttributeError`。
- 本批期间该声明与快照 ClassVar 排除曾在并发编辑中一度消失（快照排除已按原设计恢复）；`cfg_snapshot.py` 同一时间被两方写入，后续应避免同文件并发编辑。


---

## 1.3a · 载荷与接口离线验收（2026-09-15）

### 前提

| 项 | 值 |
|---|---|
| 任务 id | 不适用（离线；用测试桩 env/cfg，不注册 gym 任务） |
| 代码摘要 | Robot 工作树**未提交**（1.3a 改动：`rl_exp/tasks/curriculum_state.py`、`teacher_env_cfg.py`、`runrecord/manifest.py`、`verify/test_resume_state.py`、`verify/test_run_manifest.py`、`fork_patches/*.patch`、`README.md`/`FILEMAP.md`/`PLAN.md`/`ARCH_PLAN.md`）；提交后须按同表重跑 |
| 框架摘要 | IsaacLab 源码树 rev `28a37cecdd43`，工作树 11 项未提交差异（两个 fork 补丁 + 本地 shim 等）；Python 3.12.13 |
| 设备与规模 | 无仿真（纯 torch + 桩对象）；桩 env 数 6/8；不依赖 seed |
| 容差 | A 层位级相等（`torch.equal`）；B 层同 seed 下位级相等；无数值容差 |
| 验证命令 | `rl_exp\tools\verify\run_offline_checks.bat`（cwd 本仓）→ `ALL_OFFLINE_CHECKS_PASSED`；`[15]` 23/23、`[21]` `CONFIGCLASS_FIELDS_OK`、`[24]` `CFG_LOCK_OK (34 tasks)`、`[26]` `RUN_MANIFEST_TEST_OK` |
| 补丁一致性 | `git apply --check --reverse` 两补丁各自幂等；pristine + 两补丁按序应用后与 fork 树 `train.py` 逐字节一致（`%TEMP%\patch_check.py`） |
| 负对照（闸门反证） | 去掉行 SIR 地形摘要比较 ⇒ `test_row_sir_type_order_and_terrain_changes_rejected` 失败；不比较 c_k 调度参数 ⇒ `test_c_k_schedule_evidence_per_parameter` 失败；去掉有限性闸门 ⇒ `test_corrupt_row_sir_payload_rejected` 失败（`%TEMP%\falsify_guards.py`，跑完原模块复原） |

### 检查与结果（S01–S10 + B 层，全部**通过**）

| 编号 | 覆盖用例 | 实际结果 |
|---|---|---|
| S01 完整往返 | `test_roundtrip_bitwise_and_ck_continuity`（joint）、`test_row_sir_roundtrip_and_field_set`（行 SIR）、`test_c_k_only_roundtrip`（c_k-only） | **通过**：三线全字段位级一致 + counter 一致；`collect` 交出独立副本 |
| S02 行 SIR 指纹 | `test_row_sir_type_order_and_terrain_changes_rejected`、`test_row_sir_cfg_entries_each_rejected`、`test_static_fingerprint_catches_grid_edit`、`test_velocity_bucket_mismatch_rejected` | **通过**：网格/有序类型名/地形配置摘要/9 项 cfg 逐项变化均拒绝；**列分配逐位相同**的等占比类型换序也被拒 |
| S03 行 SIR 状态 | `test_row_sir_roundtrip_and_field_set` | **通过**：7 项运行时全恢复；无 joint 专有字段被虚构；`env_type` 参与恢复并检测重生差异 |
| S04 c_k 指纹 | `test_c_k_schedule_evidence_per_parameter`、`test_c_k_only_roundtrip` | **通过**：counter 不变改 c0/decay/steps_per_iteration 均拒；c_k 存在性双向不匹配均拒；`ck=None` = 明确无 c_k；空 `terms` 合法 |
| S05 身份与损坏 | `test_corrupt_row_sir_payload_rejected`、`test_corrupt_clock_and_weights_rejected`、`test_task_identity_mismatch_rejected` | **通过**：NaN/Inf、负值、未归一权重、计数反序、越界粒子/历史/env_type、浮点索引、错长度、未知版本、缺/多 slot、缺字段全部报错 |
| S06 原子回填 | `test_corrupt_row_sir_payload_rejected`（失败后逐项不变）、`test_hard_fail_boundaries`（同类型两实例） | **通过**：校验全过才写入；同 adapter 两实例明确拒绝（不覆盖、不任选） |
| S07 硬失败边界 | `test_missing_state_hard_aborts_and_weights_only_opts_out`、`test_hard_fail_boundaries`、`test_uncovered_stateful_term_tripwire`、`test_fork_patch_call_site_contract` | **通过**（离线面）：缺载荷/缺 slot/改名/未覆盖 term/已知类未实例化均明确处置；**调用侧**（含模块内部 ImportError）以补丁静态契约 + 树一致性校验覆盖，**未起真进程** |
| S08 兼容与 drop | `test_v1_payload_migrates_with_its_missing_evidence`、`test_drop_alias_and_conflict` | **通过**：v1 迁移为唯一 joint slot、缺证据列明且不以当前值补造；旧入口可用 + 弃用提示；新旧参数矛盾报错。**未复核**：drop 后 rsl_rl 仍加载 model/optimizer（属 rsl_rl 行为，需真跑） |
| S09 声明与分布式 | `test_declaration_is_class_level_and_off_in_play`、`test_non_zero_rank_neither_restores_nor_saves`；闸门 `[21]`/`[24]` | **通过**：声明为类属性（V5 声明、v6–v14 继承、8 个 PLAY 显式 False、V4 无）；不进 `to_dict()`；`[24]` golden 34/34 不变；非 0 rank 拒绝恢复且不装 hook |
| S10 实际恢复证据 | `test_run_manifest` 的 `s10/restored-complete`、`s10/restored-partial-v1`、`s10/dropped`、`s10/module-unavailable`、`record/distributed-flags` | **通过**：T1 的 `resume.curriculum_state` 直接引用 apply 返回结果（源版本/已恢复项/缺证据/丢弃/c_k 状态）；partial 只判未知、drop 记为不阻塞未知、声明任务模块缺失计失败 |
| B 层（1.4a） | `test_b_layer_update_equivalence` | **通过**：行 SIR（正常权重更新 + 流量不足保留两分支）与 joint SIR，同统计 + 复位 RNG 下单次真实课程更新输出逐位一致 |

### 结论与边界

- 可**宣告**："1.3 离线状态恢复验收通过"（S01–S10 + A/B 层）。
- **不可**据本表宣告：运行时续训连续（C 层 1.4b 未执行）、多卡续训已验证（明确不在保证范围）、drop 路径的 rsl_rl 加载行为（未真跑）、隔离重建（1.5）。
- 工作树未提交 ⇒ 本记录绑定**内容**而非 revision；提交后按同表重跑方可挂 revision。

