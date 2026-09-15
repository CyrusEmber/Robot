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
- ~~`REQUIRES_CURRICULUM_STATE` 的声明目前只落在 `*_PLAY` 变体（`False`）上，基类的 `True` 声明缺失~~ **已修（1.3，2026-09-15）**：基类声明落在 `LizardRoughTeacherEnvCfg_V5`（`REQUIRES_CURRICULUM_STATE: ClassVar[bool] = True`，v6–v14 继承），8 个 `*_PLAY` 显式 `False`，V3/V4 不声明（其 staged 课程未覆盖，只 WARN）。仍按 `8ac2eb9` 的 `ClassVar` 形态（进 `[21]` 通过、`[24]` golden 34/34 不变）；读取一律用 `curriculum_state.REQUIRES_CURRICULUM_STATE` 常量 + `getattr(type(cfg), ...)`，不再有 `AttributeError`。
- 声明仍会出现在 `to_dict()` / `params/env.yaml`（上游 `class_to_dict` 按实例命名空间遍历，`configclass` 已把类成员拷到实例上）：该 dump 是**记录面**，不进 golden 也不进 run manifest 的 cfg 摘要，故不改声明语义；要连它一起干净需动上游 `utils/dict.py`（增补丁），本轮不做。
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
| 验证命令 | `rl_exp\tools\verify\run_offline_checks.bat`（cwd 本仓）→ `ALL_OFFLINE_CHECKS_PASSED`；`[15]` 23/23（**本批**；B 层补齐后为 26/26，见 §1.4a）、`[21]` `CONFIGCLASS_FIELDS_OK`、`[24]` `CFG_LOCK_OK (34 tasks)`、`[26]` `RUN_MANIFEST_TEST_OK` |
| 补丁一致性 | **已固化为常态检查**：`[1]` `framework_pin_check.py` 现重建校验——把 `fork_patches/*.patch` 按序应用到 `git show HEAD:` 的 pristine 副本上，与 fork 树逐字节比（行尾归一，`core.autocrlf` 属本机设置），并报告每份存档是否已应用／可反向。2026-09-15 复跑：两存档各自 `--check --reverse` 幂等、pristine + 两补丁 == 树；反证两例 **FIRED**（树内补丁区域外手加一行 ⇒ 只有逐字节比能抓；反向卸掉一补丁 ⇒ `NOT applied` 报出）。配套 `.gitattributes` 钉 `*.patch text eol=lf`（CRLF 签出会让 hunk 匹配不上 LF 树，setup.bat 会静默失败） |
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
| S09 声明与分布式 | `test_declaration_is_class_level_and_off_in_play`、`test_non_zero_rank_neither_restores_nor_saves`；闸门 `[21]`/`[24]` | **通过**：声明为类属性（V5 声明、v6–v14 继承、8 个 PLAY 显式 False、V4 无）；不进 cfg 快照（golden 34/34 不变、`to_dict()` 仍带该键属记录面）；非 0 rank 拒绝恢复且不装 hook |
| S10 实际恢复证据 | `test_run_manifest` 的 `s10/restored-complete`、`s10/restored-partial-v1`、`s10/dropped`、`s10/module-unavailable`、`record/distributed-flags` | **通过**：T1 的 `resume.curriculum_state` 直接引用 apply 返回结果（源版本/已恢复项/缺证据/丢弃/c_k 状态）；partial 只判未知、drop 记为不阻塞未知、声明任务模块缺失计失败 |
| B 层（1.4a） | `test_b_layer_update_equivalence`、`test_b_layer_row_sir_branch_equivalence`、`test_b_layer_joint_sir_branch_equivalence`、`test_b_layer_c_k_boundary_equivalence` | **通过**：行 SIR（正常权重更新 + 流量不足保留两分支）与 joint SIR，同统计 + 复位 RNG 下单次真实课程更新输出逐位一致；分支级用 spy 断到实际走的分支；c_k 迭代边界前后取自不同迭代 |

### 结论与边界

- 可**宣告**："1.3 离线状态恢复验收通过"（S01–S10 + A/B 层）。
- **不可**据本表宣告：运行时续训连续（C 层 1.4b 未执行）、多卡续训已验证（明确不在保证范围）、drop 路径的 rsl_rl 加载行为（未真跑）、隔离重建（1.5）。
- 工作树未提交 ⇒ 本记录绑定**内容**而非 revision；提交后按同表重跑方可挂 revision。

---

## 1.5a · 恢复演练工具（2026-09-15，离线）

**本节不是"1.5 演练通过"。** 按 `ARCH_PLAN` v0.17，1.5 已从主交付出口改为**条件触发的独立恢复演练**
（触发：某实验值得长期保留 / 要对外声明可重建 / 归档迁移前留证据），不阻塞日常训练与 Step 2 迁移。
本节只交付**演练工具**（`rebuild.py` + 离线门 `[27]`）与一次真 run 上的取材证据；演练本身（另用一份
路径配置指向重建位置 + 声明复用环境 + 跑 `--check`/`--maintest`）**尚未执行**，故评级仍为未知。

### 前提

| 项 | 值 |
|---|---|
| 任务 id | 不适用（工具离线；实测取材用真 run `Lizard-Rough-v14`） |
| 代码摘要 | Robot rev `27a25fa` + 本文件所在提交（`rebuild.py`、`test_rebuild_gate.py`、`run_offline_checks.bat`） |
| 框架摘要 | 同 1.2b/1.3a：IsaacLab rev `28a37cecdd43`（跑 run 用原 tree），Python 3.12.13（原 venv） |
| 设备与规模 | 无仿真（纯文件/git + torch）；取材用 run 为单卡 64 env、seed 42、2 iter |
| 容差 | 摘要与内容哈希精确相等；无数值容差 |
| 验证命令 | `rl_exp\tools\verify\run_offline_checks.bat` → `[27] REBUILD_GATE_TEST_OK`（30 项）；单跑 `python rl_exp\tools\verify\test_rebuild_gate.py` |

### 检查与结果

| 编号 | 检查 | 输入/操作 | 实际结果 |
|---|---|---|---|
| P1 | 取材闸门对**已漂移脏树** | R1（`…/2026-09-15_15-30-08`）真 run 记录 → `rebuild --capture`，再对同一目标跑 `--check` | **通过（按预期拒采：capture 退出 2、check 退出 2）**：`isaaclab`/`rsl_rl` 记录 `cc25f24b` ≠ 现树 `13aee682`（286 行 diff 内容从未落盘，run 目录那份 `git/IsaacLab.diff` 字节哈希对不上）；`repository` = `git-rev`、`assets` = `in-repo-git`、`payload` = `copied` 三项本可取材。目标目录**只有** `rebuild_material.json`，**无 `material/`**（严格：拒采不写材料）；`--check` 报 `REBUILD_CHECK_PARTIAL` + `material was not captured (verdict=refused)`，不冒充通过。证据：`%TEMP%\rebuild_r1_dryrun\rebuild_material.json`（同命令可重跑复现） |
| P2 | 脏树 diff 无归档落点 | 单测 `capture/refuse-without-archive` | **通过**：拒采理由直指 `PLAN.md #18`（哈希 ≠ 可取回） |
| P3 | 带归档则一致 | 单测 `capture/accept-with-archive`、`stored-diff-hashes-as-recorded`、`payload-hash-matches`、`untracked-payload-stored` | **通过**：diff 与未跟踪代码内容落 `--archive` 与 `material/`，逐文件摘要与记录值相等（含 CRLF 往返不损哈希） |
| P4 | 未跟踪代码只有哈希没有内容 | 单测 `capture/refuse-vanished-untracked`、`capture/refuse-drifted-diff`、`capture/refuse-edited-record` | **通过**：`spider/` 类内容缺失、diff 漂移、冻结后被改记录（T1 摘要对不上）均拒采/判失败 |
| P5 | 来源断言（不落回原树） | 单测 `check/fallback-to-original-fails`、`check/no-original-is-unknown`、`check/undeclared-import-location-fails`、`check/asset-lock-fallback-fails`、`check/readable-original-is-informational` | **通过**：模块解析落回 `--original` 原树 = **失败**；资产锁解析落回原树 = **失败**；落在重建根与 `--dep` 之外 = 失败；未给 `--original` = 未知（不冒充）；原目录"仍可读"只作信息行（`required=False`），不判失败（**v0.16 收窄**：不做系统级访问切断） |
| P6 | 缺件负测试与退出码口径 | 单测 `maintest/removed-payload-fails`、`maintest/restored-payload-passes`、`check/edited-payload-fails`、`check/refused-material-not-claimed`、`check/failed-material-blocks` | **通过**：删一个必需载荷检查必失败、还原必通过（还原后仍不过 = **未知**，不冒充通过）；被改载荷由材料摘要行判失败；拒采材料 `--check` 退 2（不计通过）、失败材料退 1（阻塞） |
| P7 | 载荷绑定与配置 | 单测 `check/binding-row`、`check/exit-code` | **通过**：ckpt 可加载且 `infos` 回指本记录 run id + T1 摘要；配方按 golden 再推导一致 |
| P8 | "只换配置"不算材料恢复演练 | 单测 `check/path-config-only-is-not-a-drill`、`check/scope-declares-reuse` | **通过**：`--root` 落在原树内 ⇒ 记**未知**（不冒充材料恢复）；正常演练输出 scope 行，写明"材料重建在哪、依赖复用了哪些" |
| P9 | 演练①②步实测（选定实验 + 取材） | 真 run `Lizard-Rough-v14`（`logs\rsl_rl\lizard_rough_teacher_v14\2026-09-15_19-08-50`，T1 `aeba04549bc363f1`，2 iter）→ `rebuild --capture … --archive rl_exp\archive` | **通过（材料可取材）**：`REBUILD_CAPTURE_OK`；`repository`=`git-rev`（rev `27a25fa`）、`isaaclab`/`rsl_rl`=`stored-diff`（脏树 diff 已入仓 `rl_exp\archive\<run_id>\`，摘要逐项比对 == 记录值 `13aee682fe1e`）、`assets`=`in-repo-git`、`payload`=`copied`（`model_0/1.pt` + 记录，材料内 12 个载荷文件各有摘要）；材料落 `E:\rl_rebuild\material` |

### 结论与边界

- 可**宣告**：演练工具与取材闸门已落地并进离线套件（`[27]` 30/30）；**演练①②步（选实验 + 备材料）在真 run 上跑通**；
  R1 因脏树漂移被闸门拒采——判据非摆设的证据（与 1.2b R4 把该 run 的 isaaclab 来源判未知同一事实）。
- **口径**：v0.16 收窄验收强度（不做账号/ACL，判据 = 解析不落回原树；原目录可读只作信息行）；v0.17 把 1.5 从主出口
  移到**按需演练**，并引入**覆盖范围表**（重建材料+复用环境 / 连环境一并重装 / 只换配置不算演练）。
- **不可**据本节宣告 1.5 演练通过。剩余步骤（③ 另用一份路径配置指向重建位置与声明环境；④ `--check` + `--maintest`，
  记录覆盖范围）**尚未执行**：
  1. **重建位置未搭**：未把代码/配置/资产/ckpt 另置一处（按覆盖范围表选"只重建材料、复用声明环境"还是"连环境一并重装"），
     未写那份指向重建位置的路径配置；`--check`/`--maintest` 尚未在真重建位置跑过。
  2. **归档落盘状态**：`rl_exp\archive\<run_id>\` 已生成，须**入仓提交**才算"取回得"（小文件进 Git，#18 改判）。
  3. **边界**：不做系统级访问切断，不覆盖任意隐藏读取（包内部/缓存/环境变量旁路）；不承诺推理或训练结果等价。



---

## 1.4a · 恢复验收 B 层补全（2026-09-15）

1.3a 的 B 层只覆盖行 SIR 两条分支、每线一次更新。本节按 `ARCH_PLAN.md` 1.4a 补齐**分支级**与
**c_k 迭代边界**覆盖；A 层（S01–S10）沿用上节，不重复。

### 前提

| 项 | 值 |
|---|---|
| 任务 id | 不适用（离线；测试桩 env/cfg，不注册 gym 任务） |
| 代码摘要 | Robot rev `fe4e8f1` + 工作树未提交（本批：`verify/test_resume_state.py`；同批另有一路并行编辑把声明改为 `ClassVar[bool]`，本轮全套闸门在该改动落定后重跑） |
| 框架摘要 | IsaacLab 源码树 rev `28a37cecdd43`；Python 3.12.13 |
| 设备与规模 | 无仿真（纯 torch + 桩对象）；桩 env 数 6（joint SIR）/8（行 SIR） |
| 容差 | 位级相等（`torch.equal`）；c_k 与**按载荷保存参数独立重算**的 float64 值，绝对误差 ≤ 1e-12 |
| 验证命令 | `rl_exp\tools\verify\run_offline_checks.bat`（cwd 本仓）→ `ALL_OFFLINE_CHECKS_PASSED`；`[15]` **26 passed**（+3 新增）、`[24]` `CFG_LOCK_OK (34 tasks)`、`[26]` `RUN_MANIFEST_TEST_OK` |
| 负对照（7 例反证） | `%TEMP%\falsify_b_layer.py`（逐例改一处生产行为、跑目标用例、逐字节复原 `curriculum_state.py`/`teacher_mdp.py`）：no-op 回填 / 行 SIR 丢弃测量 / 行 SIR 丢弃全带外回退 / joint 游走退化为恒等 / joint 前沿回退退化为均匀 / joint 未结算也清零统计 / c_k 迭代序号 +1 —— **七例全部 FIRED**（每例都让目标用例失败，无虚过） |

### 检查与结果

| 编号 | 覆盖用例 | 实际结果 |
|---|---|---|
| B1 行 SIR 分支 | `test_b_layer_row_sir_branch_equivalence`（测量更新 / `n_traj_min` 以下 / 全带外回退 / 随机游走 / replay） | **通过**：每例先断言分支签名（测量替换先验、先验权重存活、全域重探均匀、粒子落 ±1 行、粒子来自受限回放池），再走生产入口 `term(env, ids)`（块边界，含节流 `next_eval_step` 与重生目标），原对象与恢复对象逐位一致；回填前先断言"冷对象 ≠ 载荷"（no-op 回填必失败） |
| B2 joint SIR 分支 | `test_b_layer_joint_sir_branch_equivalence`（同五例；回退走 `_fallback_weights` 有向前沿，游走用 `_walk` 计数探针） | **通过**：`maintain_mass` 份额、前沿非均匀（单 combo 类型按论文语义退均匀）、未结算 pair 保留统计跨块累积、结算 pair 清零统计均合生产语义；两线逐位一致 |
| B3 c_k 边界 | `test_b_layer_c_k_boundary_equivalence` | **通过**：counter 恢复为源值；边界前 / 边界 / 边界后 / 多块处 counter 一致、c_k 与按保存参数独立重算的 float64 值误差 ≤ 1e-12，且边界处确实变化（非平凡） |
| B4 旧字段回归 | `test_roundtrip_bitwise_and_ck_continuity`（增 joint 槽字段集断言） | **通过**：载荷少一个 joint 运行时字段即失败——"静默丢状态"不再能通过往返 |

### 本批修正（旧夹具虚标）

- 旧 B 层标为"正常权重更新"的一例用 `episodes=3.0`，而 `n_traj_min=6` ⇒ 实际走的是**保留旧权重**分支，与另一例同支：标注与夹具不符。已改为 `episodes=10.0 / successes=7.0` 的真测量更新（`p_hat=0.7` 落带内），并在 docstring 写明分支归属；两分支的精确签名断言改由 B1 承担。

### 结论与边界

- 可**宣告**：**1.4a A/B 层离线验收通过**（A 层 S01–S10 见 §1.3a）。
- **不可**据本节宣告：接线时序正确（apply 早于 wrapper 首次 reset）——只有 1.4b C 层真跑能证；冷热前 N 步逐位一致（RNG/出生/per-episode 瞬态刻意不存）；多卡续训（不在保证范围）。
- B 层证明的是"**状态 → 更新映射**一致"，不是"复现"。

---

## 1.4b · 恢复验收 C 层（真跑，2026-09-15）

C 层只认**真实 trainer 进程**里的观察点：另写一套"逐行对齐 train.py"的流程会与 trainer 分叉，只能当辅助。
做法是把观察器注入真进程，**只包装读取**：

* `rl_exp/tools/verify/cstate_observer.py`（逻辑，入仓）+ 3 行 `sitecustomize.py`（`%TEMP%\obs`，经 `PYTHONPATH` 注入，不入仓）。
* 包装点：`apply_resume_state`（P0/P1）、`OnPolicyRunner.load`（与 ckpt 逐项比 actor/critic/optimizer）、
  `OnPolicyRunner.learn`（单次调用跑满，**不循环 `learn(1)`**——rsl_rl 的 `learn` 按 `start_it + n` 计数，且每次收尾会保存并关掉
  logging writer，反复 `learn(1)` 会反复用同一个 iteration 编号）、`env.step`（逐 step Δcounter）、
  `alg.update`（optimizer 更新与步数）、两个 SIR 的 `_resample`/`_resample_all`（**真实课程更新事件**）。
* `rl_exp/tools/verify/check_c_layer.py` 读这些 JSON 判据（`--resave` 另开最终 ckpt 校验）。

### 前提

| 项 | 值 |
|---|---|
| 任务 id | `Lizard-Rough-v14`（行 SIR）/ `Lizard-Rough-v12`（joint SIR）/ `Lizard-Rough-v3`（c_k-only，无 term），注册表核验通过 |
| 代码摘要 | Robot rev `9fc06d6`（含本轮 `_check_eval_clock` 修复 + 新离线用例）+ 工作树未提交 `tools/verify/cstate_observer.py`、`check_c_layer.py`。**时序**：t_v12-resume 首次尝试在修复前（18:16，被闸门拒），其余有效运行在修复后；修复只**放宽**接受范围，不影响既有通过项 |
| 框架摘要 | IsaacLab 树 rev `28a37cecdd43` + 两个 fork 补丁（`git apply --check --reverse` 幂等）；rsl_rl 装于 venv `site-packages`；Python 3.12.13 |
| 设备与规模 | 单卡 RTX 3060 Ti 8 GB（开跑前桌面占用 ~1 GB）、64 env、seed 42、`--headless`、`sim.dt=0.005`/`decimation=4`/`episode_length_s=20` ⇒ H = 1000 步 |
| 运行长度 | **84 it = 2016 步** ≥ `max(2B, 2H)` = `max(480, 2000)` = 2000（每支一次 `learn()`） |
| 容差 | 张量按内容摘要位级相等；counter 精确整数；c_k 与独立 float64 重算 \|err\| ≤ 1e-12；Adam `step` 每次更新每参数 +1 |
| 命令形态（cwd `E:\IsaacLab`） | 源：`train.py --task <id> --headless --num_envs 64 --seed 42 --max_iterations 20`；短路径：`--resume --load_run <src> --checkpoint model_39.pt --max_iterations 1`；主证据：同上但 `--max_iterations 84`；drop 臂另加 `--drop_curriculum_state` |
| 实测速度 | 稳态 v14 ≈ 1.9–2.1 s/it、v12 ≈ 1.85 s/it、v3 ≈ 2.8 s/it（先前用 2-iteration run 估的 5.4 s/it 混入了第一迭代与环境创建，偏高）；单支 84 it ≈ 3–4.5 min |
| 验证命令 | `python rl_exp\tools\verify\check_c_layer.py --root %TEMP%\c4 --resave --source-checkpoint v14=<ckpt> …` → **`C_LAYER_OK (0 failing)`**（15 臂 × 全判据） |
| 证据路径 | 每臂 `%TEMP%\c4\<arm>\observe_<pid>.json` + `<arm>.log`；汇总 `%TEMP%\c4\c_layer_report.json`；run 目录见下表 |
| 负对照 | `%TEMP%\falsify_clock_rule.py`：把时钟规则改回 `next_eval <= counter` ⇒ 新用例失败；还原后通过（**FIRED**） |

### 臂与 run

| 臂 | run 目录（`logs\rsl_rl\<exp>\`，机器本地） | counter | it | 真实课程更新 |
|---|---|---|---|---|
| s_v14 | `lizard_rough_teacher_v14\2026-09-15_17-51-57` | 0 → 960 | 39 | 4 次 @247/487/722/960 |
| s_v12 | `lizard_rough_teacher_v12\2026-09-15_17-55-59` | 0 → 960 | 39 | 3 次 @250/485/734 |
| s_v3 | `lizard_rough_teacher_v3\2026-09-15_19-21-40` | 0 → 480 | 19 | 无 term（时钟即状态） |
| p_v14-resume / p_v14-drop | `…_v14\2026-09-15_18-02-30` / `18-04-33` | 960 → 984 / 0 → 24 | 39 | — |
| p_v12-resume / p_v12-drop | `…_v12\2026-09-15_18-05-28` / `18-06-00` | 960 → 984 / 0 → 24 | 39 | — |
| p_v3-resume / p_v3-drop | `…_v3\2026-09-15_18-06-00` / `18-06-23` | 480 → 504 / 0 → 24 | 19 | — |
| t_v14-resume / t_v14-drop | `…_v14\2026-09-15_18-09-30` / `18-12-40` | 960 → 2976 / 0 → 2016 | 122 | 8 / 8 |
| t_v12-resume / t_v12-drop | `…_v12\2026-09-15_18-21-05` / `19-05-29` | 960 → 2976 / 0 → 2016 | 122 | **9** / 8 |
| t_v3-resume / t_v3-drop | `…_v3\2026-09-15_19-29-07` / `19-35-43` | 480 → 2496 / 0 → 2016 | 102 | 无 term（c_k 另验） |

### 检查与结果（全部**通过**）

| 编号 | 检查 | 实际结果 |
|---|---|---|
| C1 回填与首次 reset | P1 的 counter == 源 counter（960/960/480）；P1→P2 **持久状态**（particles/weights/episodes/successes/history 等）逐位不变、counter 不变；**出生相关**状态（`env_type`/`env_pair`/`desired_vel`）允许按生产规则重采样（两案分开判，不无条件要求位级相等） | **通过**：行 SIR（v14）与 joint SIR（v12）都保持持久集，出生集只查合法；c_k-only 线无 schedule 可到期，另记 |
| C2 时钟推进 | 逐 `env.step` 前后 `counter_after − counter_before == 1`（**不**按 iteration 增量反推）：源 960/960/480 步、主证据 2016 步/臂，`deltas={'1': n}` 且 `bad=0`；终态算术 resume `2976−960=2016`、`2496−480=2016`，drop `2016−0=2016` | **通过**：三线六臂全对；2016 ≥ 2000 |
| C3 c_k 连续（不回热） | 真跑取值：v3-resume 入口 c_k `0.341477468432` == 源出口值（**连续、未回热**）、出口 `0.82129495338`；与按载荷参数独立重算的 float64 值 \|err\| ≤ 1e-12；drop 入口 `c0=0.2` 且 counter=0、出口 `0.744611194915`（回热对照） | **通过**（c_k 的实跑证据取自 c_k-only 线；v14/v12 的 c_k 由 §1.4a 的 1e-12 用例 + 载荷指纹覆盖） |
| C4 课程更新时点 | 记录**实际更新事件**（不凭 counter 猜）：每个事件 `clock ≥ next_eval_before`、`next_eval_after == next_eval_before + 240`、事件后状态合法（权重和/索引/`env_type`/`env_pair`/`desired_vel` 有限）。观察到的时点 247/250 = 块沿 240 之后**第一个带 reset 的 step**（term 由 `_reset_idx` 调用） | **通过**：v14 源 4 次、v12 源 3 次、主证据每臂 ≥2 次（含恢复后立刻补发的挂起块 ⇒ v12-resume 9 次）；`ok` 无 problems |
| C5 训练正常推进 | 84 次 optimizer 更新/臂、参数每次均变化、Adam `step` 每参数每次 +1（每次更新总量 +902）、全部 loss 有限；最终 ckpt 可加载且 `iter` == 最后完成迭代、载荷 counter == 观测终值、调度前进（`--resave`） | **通过**：六臂一致；`param_moved` 84/84 |
| C6 冷启动负对照 | 同 checkpoint、同 84 it、同 64 env/seed；drop 臂 P1 counter=0 且无 SIR 状态、入口 c_k=c0、终态 2016；同任务 resume 臂 2976/2496 | **通过**（两臂都推进，差异只在课程状态） |
| C7 S08 遗留：drop 后是否仍加载 model/optimizer | `runner.load()` 之后、首次 `update()` 之前与**同一 ckpt** 逐项比：actor 33/33、critic 32/32 键逐位相等；optimizer `param_groups` 相等 + `state` 41/41 张量相等（含 `step`/`exp_avg`/`exp_avg_sq`）；resume 与 drop **两臂都与该 ckpt 一致** | **通过**：不用"reward 相近"推断（该推断不成立），改为直接状态比较 |

### 本批修正：`_check_eval_clock` 曾把合法 ckpt 判为不可恢复

真跑抓到（A/B 层看不见）：

```
ValueError: curriculum state in the checkpoint does not fit this task: runtime.next_eval_step[joint_sir]
960 is not the first block edge above 960  [checkpoint …v12\2026-09-15_17-55-59\model_39.pt]
```

- **事实**：v12 源在 counter=960 保存，而块沿 960 的更新尚未触发（term 只在带 reset 的 step 被调用；v14 的同位置更新恰在 960 触发）⇒ 同配方、同迭代数，可恢复与否取决于 env 是否恰在边界步 reset。
- **旧规则**：`next_eval_step > counter` 严格成立，否则硬拒 ⇒ **挂起（pending）状态被误判为不一致**；counter 落在 `[edge, edge+6]` 窗口内保存的 ckpt 同样会被拒（v14 的更新落在 247，说明该窗口真实存在）。
- **新规则**：`next_eval_step % block == 0 and next_eval_step > counter − block`——接受"覆盖当前 counter 的块沿或下一个块沿"（挂起/已到期），仍拒绝**落后整块及以上**的调度（块大小被改 / 手改载荷的证据）。
- **覆盖**：`test_eval_clock_accepts_a_pending_edge_and_rejects_a_stale_one`（3 接受 + 3 拒绝）；`%TEMP%\falsify_clock_rule.py` 证明改回旧规则该用例必失败；离线 `[15]` **27 passed**、全套 `ALL_OFFLINE_CHECKS_PASSED`。
- **代价/边界**：放宽后不再保证"载荷调度与 counter 严格同步"，只保证"调度自洽且不落后整块"；C1 的"是否到期"改为分案判定，到期时要求**实际发生对应更新**（v12-resume 的 9 次事件即此案）。

### 结论与边界

- 可**宣告**："**1.4 C 层集成级恢复验收通过（三条代表线 × resume/drop）**"：回填早于首次 reset、逐 step 时钟 +1、课程按真实节流更新且合法、训练正常推进、drop 冷启动且两臂同 ckpt 加载。
- **不可**据本节宣告：① "复现"——冷热前 N 步不逐位一致（RNG/出生/per-episode 瞬态刻意不存），C 层只证**接线时序**；② 其它版本的 C 层（v5–v10、v13 共享同一适配器与注册表，但未逐版本真跑）；③ 多卡续训（非 0 rank 明确拒绝，不在保证范围）；④ 长期训练统计等价（84 it 只够覆盖 ≥2 个课程块与 2H）。
- **本批损耗（记录在案）**：批量链式启动被 shell 截断两次（t_v12-drop 41/84 it、S·v3 264 步），产物**不计证据**，均改单臂重跑；`s_v14`/`s_v12` 两臂的 `run_dir` 未记录（观察器后补该字段），其 ckpt 由 `--source-checkpoint` 显式给出。

