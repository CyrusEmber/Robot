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


### golden 基线来源补记（2026-09-15 晚，F2 收口）

**问题**：Step 2 硬 A 要"与整改前 golden 逐字段一致"，而落盘基线的戳是 `created_rev cc1b2e7083ec` + `created_dirty true`
（格式 2 重基线时树上有未提交改动）。`created_dirty` 本身不证明 golden 错——它说明 `created_rev` 单独**不足以**标识生成 golden 的完整代码状态。

**处置（不是把 `dirty` 改成 `false` 消警）**：

1. 先在带未提交改动的工作树上跑 `check_cfg_lock --update`（**不带** `--reason`）→ 工具自判 **`no content change (provenance or format only)`** 并**拒绝写入**。"内容与干净树再生一致"由此由工具给出，不靠人声明。
2. 在**确定的干净提交**上重新生成：`git clone E:\Robot E:\rl_golden_clean`（HEAD `cee0adb`，`git status --short` 为空）→ 克隆内跑 `--update --reason "clean-tree baseline: …"`。
3. 结果：与旧文件相比**只有 4 行元数据**变化（`created_at` / `reason` / `created_rev` → `cee0adb1f51f` / `created_dirty` → `false`）；**34 个任务、1 个组合块、2642 KiB 的配置内容一字未动**（`git diff --stat` = 4 insertions / 4 deletions）。
4. 等价性双证：第 1 步（工具的逐字段判定）+ 第 3 步（逐行 diff 只剩元数据）。

**旧基线（格式 1）保留方式（明确到可取回）**：

| 项 | 值 |
|---|---|
| commit | `7525268`（"records: stamp the golden baseline from a clean tree"） |
| 路径 | `rl_exp/versions/lizard/cfg_lock.json` |
| 文件摘要 | sha256 `176513b73a9e19f708bd449b48fd1db9b773817cacf2464dadfabc9d763cab40`，2,634,664 B |
| 取回 | `git show 7525268:rl_exp/versions/lizard/cfg_lock.json > <out>` 或 `git checkout 7525268 -- rl_exp/versions/lizard/cfg_lock.json` |
| 1→2 变化 | `ClassVar` 成员离开快照：34 个任务各 12 条路径（6 个 PLAY 各另 1 条 `REQUIRES_CURRICULUM_STATE`）；**无任何配置值改变**；lock 2674 → 2642 KiB |

**边界**：格式 1 的条目**只在 git 历史**里（同一组合块被就地重写，文件内不并存两份）——`ARCH_PLAN` 1.1c 的"旧 block 保留"按字面只适用于**框架组合变化**；格式变更路径以 git 历史为保留手段。格式 1 时期的配方项仍一律**未知**（不可比），不据旧摘要判失败或通过。

### golden 拆为路线级锁（格式 2 → 3，2026-09-16）

| 项 | 内容 |
|---|---|
| 变更 | `lock_format` **2 → 3**：`baselines` 移入全仓共享的 `rl_exp/versions/cfg_baselines.json`（组合是框架事实，不属于任何一条线；一份才不会互相矛盾）；`entries` 按**配方线**拆文件（主线 `versions/lizard/cfg_lock.json`，支线 `versions/lizard/parkour/cfg_lock.json`）。动机：`--update` 原为**全量写**（构造全部注册任务、整体替换该组合的 entries）⇒ 给一个新任务建 golden 会**静默吸收**其它任务的漂移并挂在同一条 `--reason` 下；且 entry schema 有意封闭（多一个字段即红），"这条 golden 属于哪条线"只能由文件路径承载 |
| 审查方式 | 迁移**不走 `--update`**（它会全量重写，正是要防的那件事），改按 cfg 类声明的 `params_line` 分组、逐条**原样搬运**并逐条比对 |
| 实际落子 | 34 条拆为 **32**（主线）+ **2**（parkour）；**34/34 条目规范化 JSON 逐条一致**（脚本内断言）；`CFG_LOCK_OK (34 tasks, 2 line(s))` |
| 复核命令 | `git diff --stat -- rl_exp/versions/lizard/cfg_lock.json rl_exp/versions/lizard/parkour/cfg_lock.json`；新增 `rl_exp/versions/cfg_baselines.json` |
| **与 1→2 的关键区别** | 1→2 **改了快照内容**（ClassVar 路径离开 ⇒ 旧配方项不可比）；2→3 **一个配置值都没动**，只动落点与元数据 ⇒ 格式 2 的配方项**仍然可比**，不降级为未知 |
| 后续一条真实改动（隔离性实证） | `--update --line lizard/parkour --reason "..."`：只写支线文件；主线锁 sha256 前后**完全一致**（本批实测）；parkour 两条各 1 条路径变化（`env.params_version: <absent> -> "v1"`），共用组合块未被改写 |
| 旧基线（格式 2）保留方式 | 本批提交前的 `rl_exp/versions/lizard/cfg_lock.json`（`lock_format` 2 / `task_count` 34 / 2,603,613 B）；取回 `git show <本批前的 rev>:rl_exp/versions/lizard/cfg_lock.json > <out>` |

### 本批未覆盖（不得据本批宣称通过）

- **1.5 隔离重建**：无重建记录，`已验证重建` 恒为**未知**（非必需项，不影响其它结论）。
  - **追加（2026-09-15 晚）**：已执行一轮按需演练（重建项目材料 + 复用声明环境），范围内通过，见 1.5a 节；本批结论不受影响。
- **1.4b C 层代表任务**（c_k-only `v3`、行 SIR `v14`、joint SIR `v12` 的真续训）：**未执行**。
  - **追加（2026-09-15 晚）**：**已执行**（3 代表任务 × resume/drop，15 臂；`afd1e54`），结论见 1.4b 节。
- **1.3a S01–S10**（载荷/指纹/损坏/边界/兼容）：**已执行（离线）**，见下节。
- **无归档的"可取回"项**：一律保持未知（`PLAN.md` #18），本批不因此判失败，也不提升为通过。
- **出口判定（2026-09-15 晚，F3 补记）**：本批**必需**验收 ①②③④ **通过**（R2 动态模型类进 T1、R3 恢复后生效 lr、R5/R6 失败无 T1、R7/R8 引用漂移与未声明来源判失败）；**R4 的两项未知属非必需项**（未跟踪代码可取得、格式 1 配方摘要可比性），**不阻塞本阶段出口**，原判定与边界一并保留。§1.2b 追加说明只补"材料在哪、摘要多少"，**不把当时的未知改判为通过**。

### 已知瑕疵（不阻塞本批，需另行处理）

- ~~fork 补丁仍以 `weights_only=args_cli.weights_only` 调用~~ **已修（1.3，2026-09-15）**：新补丁传 `drop_curriculum_state=args_cli.drop_curriculum_state or args_cli.weights_only`，旧 CLI 名保留为别名 + 一行弃用提示（仅在使用旧名时打印）；两条补丁插入点已解耦，`git apply --check --reverse` 各自幂等。
- IsaacLab 树内 `source/isaaclab_tasks/…/velocity/config/spider/` 未跟踪 ⇒ 该树所有 run 的 isaaclab 来源项都会记未知。需在树里提交或删除该目录，才能让这一项可判通过。
  - **追加说明（2026-09-15 晚，归档到位；原判"未知"保留）**：该目录内容与脏树 diff 已入仓——
    `rl_exp/archive/2026-09-15_19-08-50/untracked/isaaclab/source/…/config/spider/`，逐文件 sha256（前 16）：
    `__init__.py` `7f59990e30e3faf4`（933 B）、`agents/__init__.py` `3be19bd191a2d878`（192 B）、
    `agents/rsl_rl_ppo_cfg.py` `69db92b889acaa89`（1236 B）、`spider_env_cfg.py` `9bdc2896be9456b1`（4815 B）；
    同目录另存 `isaaclab.diff` / `rsl_rl.diff` = `13aee682fe1efb37`（17632 B）。
  - **归档绑定的是哪一次**：那份 diff 绑 **19-08-50 那次 run**（其 T1 记录 `13aee682`），**不是 R4/R1 的 `cc25f24b`**
    （R1 的 286 行 diff 内容从未落盘，且现树已漂移，按硬约束 6 不得补造）。故 R4 的"代码可取回"**仍为未知**。
  - **旁证（强度上限写清）**：① 状态清单摘要三点同值 `391d17f7db7b64ea`（R1 `15-30-08` / `19-08-50` / 现在的树）——
    只证**文件集合与状态一致**，不含内容；② 上面 4 个 `.py` 的 mtime 均为 `2026-08-24 17:26–17:48`，早于 R1 约三周且至今未变。
    两条合起来只支持"**很可能未被改动**"；mtime 可被 `copy2`/`robocopy` 保留，不构成同一份的证明。
  - **升级为"通过"的条件**：某 run 的 T1 里带**未跟踪文件的逐文件内容摘要**时，其归档材料才可与记录判"同一份"。
    现在 `code.<source>.untracked*` 只有名字 / 数量 / `untracked_requires_archive` 标志，**没有内容摘要**——这是
    R4 无法收口的根因，已作为 provenance 改进项登记（`PLAN.md` #18 衍生项）。
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

**本节结论按覆盖范围限定。** 按 `ARCH_PLAN` v0.17，1.5 已从主交付出口改为**条件触发的独立恢复演练**
（触发：某实验值得长期保留 / 要对外声明可重建 / 归档迁移前留证据），不阻塞日常训练与 Step 2 迁移。
本节交付**演练工具**（`rebuild.py` + 离线门 `[27]`）与**一次完整演练**：选定实验 → 备材料 → 另用一份
路径配置指向重建位置与声明复用环境 → 检查与缺件负测试（P10–P13）。覆盖范围 = **重建项目材料、复用
已声明的现有环境**，故结论只到"本次演练范围内：配置与加载级重建通过"。

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
| P5 | 来源断言（**只断言声明为重建的材料**） | 单测 `check/fallback-to-original-fails`、`check/no-original-is-unknown`、`check/undeclared-import-location-fails`、`check/asset-lock-fallback-fails`、`check/readable-original-is-informational`、`check/reused-deps-are-not-asserted`、`check/rebuilt-module-is-asserted` | **通过**：声明重建的模块解析落回 `--original` 原树 = **失败**；资产锁同判；落在重建根与 `--dep` 之外 = 失败；未给 `--original` = 未知；**声明复用的依赖不判**（只记录，"config 指向对就对了"，不再自证）；`--rebuilt-module` 可把框架一并纳入断言（环境重装的覆盖范围用）；原目录"仍可读"只作信息行（v0.16：不做系统级访问切断） |
| P6 | 缺件负测试与退出码口径 | 单测 `maintest/removed-payload-fails`、`maintest/restored-payload-passes`、`check/edited-payload-fails`、`check/refused-material-not-claimed`、`check/failed-material-blocks` | **通过**：删一个必需载荷检查必失败、还原必通过（还原后仍不过 = **未知**，不冒充通过）；被改载荷由材料摘要行判失败；拒采材料 `--check` 退 2（不计通过）、失败材料退 1（阻塞） |
| P7 | 载荷绑定与配置 | 单测 `check/binding-row`、`check/exit-code` | **通过**：ckpt 可加载且 `infos` 回指本记录 run id + T1 摘要；配方按 golden 再推导一致 |
| P8 | "只换配置"不算材料恢复演练 | 单测 `check/path-config-only-is-not-a-drill`、`check/scope-declares-reuse` | **通过**：`--root` 落在原树内 ⇒ 记**未知**（不冒充材料恢复）；正常演练输出 scope 行，写明"材料重建在哪、依赖复用了哪些" |
| P9 | 演练①②步实测（选定实验 + 取材） | 真 run `Lizard-Rough-v14`（`logs\rsl_rl\lizard_rough_teacher_v14\2026-09-15_19-08-50`，T1 `aeba04549bc363f1`，2 iter）→ `rebuild --capture … --archive rl_exp\archive` | **通过（材料可取材）**：`REBUILD_CAPTURE_OK`；`repository`=`git-rev`（rev `27a25fa`）、`isaaclab`/`rsl_rl`=`stored-diff`（脏树 diff 已入仓 `rl_exp\archive\<run_id>\`，摘要逐项比对 == 记录值 `13aee682fe1e`）、`assets`=`in-repo-git`、`payload`=`copied`（`model_0/1.pt` + 记录，材料内 12 个载荷文件各有摘要）；材料落 `E:\rl_rebuild\material` |

| P10 | 演练③步：第二份机器路径配置 | 在重建位置写 `E:\rl_rebuild\proj\paths.yaml`（`isaac_root: E:/IsaacLab`、`python: E:/IsaacLab/env_isaaclab/Scripts/python.exe`，即**声明复用的同一环境**） | **通过**：重建位置自带一份路径配置；项目材料为 `git clone` 后 `remote remove origin` 的 `27a25fa`（该 run 的声明 rev，工作树干净） |
| P11 | 演练④步：**负对照**（材料仍在原地） | cwd `E:\Robot`（原项目），`--check E:\rl_rebuild\material --root E:\rl_rebuild\proj --original E:\Robot` | **通过（按预期失败，退 1）**：`sources: rebuilt material ['rl_exp'] resolved back into the original tree (E:\Robot\rl_exp\__init__.py)`、`assets: the lock resolves back into the original tree`——"只换配置、材料仍在原地"会被区分出来（覆盖范围表第三行） |
| P12 | 演练④步：**正式检查**（从重建位置跑） | cwd `E:\rl_rebuild\proj`，`RL_ISAAC_ROOT=E:\IsaacLab`，`--check … --root E:\rl_rebuild\proj --dep E:\IsaacLab\source --dep E:\IsaacLab\env_isaaclab\Lib\site-packages --original E:\Robot` | **通过（`REBUILD_CHECK_OK`，退 0）**：材料 12 文件摘要一致；`rl_exp` 解析在重建位置（非原树）；资产锁解析在重建位置；配方按 golden `3c6439cea8e2` 从**重建代码**再推导一致；`model_1.pt` 可加载且回指 T1 `aeba04549bc363f1` |
| P13 | 演练④步：缺件负测试 | 同 P12 + `--maintest` | **通过**：删 `run/model_0.pt` ⇒ 检查必失败（实测失败）；还原 ⇒ `REBUILD_CHECK_OK` |

### 结论与边界

- 可**宣告（仅限本次演练范围）**：**重建项目材料 + 复用声明的现有环境 ⇒ 配置与加载级重建通过**。
  - 重建项：项目代码（`rl_exp`，rev `27a25fa`）、资产（83 文件锁）、该 run 的 ckpt 与记录、脏树归档材料；
  - 复用项（**只记录、不断言**）：Python 解释器与预装框架（`E:\IsaacLab` 源码树 + venv `site-packages` 中的 isaacsim / torch / rsl_rl）；
  - 依据：P10–P13；工具侧"只断言声明为重建的材料"这条口径由 `[27]` 增补测试覆盖。
- **不可外推**：环境未重装 ⇒ 不证明环境安装过程可复现；未做系统级访问切断 ⇒ 不覆盖隐藏读取（包内部 / 缓存 / 环境变量旁路）；2 iter run ⇒ 不承诺推理或训练结果等价。
- 工具版本说明：演练②的取材材料落在 `27a25fa`，故 P12/P13 跑的是**重建出的那份工具**；P11 用工作树当前工具（多一条 scope 行、框架断言更严）——判据行一致，结论不受影响。
- 演练转按需：后续触发（值得长期保留的实验 / 要对外声明可重建 / 归档迁移前）再跑，不阻塞日常训练与 Step 2。
- **演练位置是一次性的，已按用户要求删除**（`E:\rl_rebuild`：`proj` 重建位置 + `material` 材料 + 第二份 `paths.yaml`）。证据仍在：材料与脏树归档在仓内 `rl_exp\archive\2026-09-15_19-08-50\`，run 在原 `logs\` 目录，复跑按 P10–P13 的命令重建即可（`git clone` 到任一新位置 + 写那份路径配置 → `--check` → `--maintest`）。**结论不依赖该目录存在**：它只是本次演练的现场。



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

---

## Step 1 汇总复核（2026-09-15 晚，F1）

**性质**：**追加**条目。历史各节的原摘要与原结论**不改**（硬约束 6）；此前 1.3a / 1.5a 前提里"提交后须按同表重跑"的要求由此闭合到 revision。

### 前提（本次复核绑定的对象）

| 项 | 值 |
|---|---|
| 项目 rev | `00d0b07c768fa8db0206007cd9ad74ed6d976f33`（`00d0b07`）；**跟踪文件零改动**（`git diff HEAD` = 0 行，空摘要 `e3b0c442…`）。当时树上另有 2 项**未跟踪**：`ablation_harness/results/locomotion_eval_v2/v14/`（并发 eval 产物，非本次改动）与本日志 |
| IsaacLab | rev `28a37cecdd43`，dirty，diff `13aee682fe1efb37…`，**344 行**；未跟踪 6 项（代码根内 1 项 `…/velocity/config/spider/`） |
| rsl_rl | 同树同 rev，`editable/source`（包目录 `env_isaaclab\Lib\site-packages\rsl_rl`） |
| Python | `E:\IsaacLab\env_isaaclab\Scripts\python.exe`，3.12.13 |
| 框架组合 | `isaaclab=28a37cecdd43\|rsl_rl=source:28a37cecdd43\|python=3.12.13`（与 `cfg_lock.json` 的 baseline 键一致） |
| 命令 | `rl_exp\tools\verify\run_offline_checks.bat`（cwd 本仓） |
| 结果 | `ALL_OFFLINE_CHECKS_PASSED`；`[1] PIN_CHECK_OK`、`[15]`（`test_joint_sir` 10 passed / `test_resume_state` 27 passed）、`[21] CONFIGCLASS_FIELDS_OK`、`[24] CFG_LOCK_OK (34 tasks)`、`[26] RUN_MANIFEST_TEST_OK`、`[27] REBUILD_GATE_TEST_OK` |
| 日志 | `rl_exp/versions/lizard/verify_logs/step1-offline-00d0b07-2026-09-15.log`（入库） |

### 框架漂移（286 → 344 行）影响审查

| 项 | 结论 |
|---|---|
| rev 与未跟踪清单 | 与 R1 相同（rev `28a37cecdd43`；未跟踪 6 项，代码根内仍是 `spider/`）⇒ 漂移只在**已跟踪文件的 diff 内容** |
| 逐文件归属 | **不可证**：R1 只记整体 diff 摘要（`cc25f24b`，286 行）+ 文件清单（同 5 个文件），未逐文件记摘要，内容也未落盘 ⇒ 按硬约束 6 记**未知**；不得反推"只差 train.py" |
| extras 实际影响面（当前内容由 `fork_patches/local_tree_extras.patch` 钉住，`git apply --check --reverse` 通过） | `isaaclab.bat` 置空、`anymal_c_env.py` 加 `set_command` ⇒ **不在 lizard 路径**（bat 不参与 `python scripts/…`；anymal 是另一条 direct 任务）。`velocity_env_cfg.py` 的 DR 改动分两半：**值**半边被本仓覆盖（`lizard_params.yaml:141-142` = `[0.4,1.2]/[0.3,1.0]`，由 `lizard_env_cfg.py:159-160`、`teacher_env_cfg.py:614-615`、`parkour_env_cfg.py:424-425` 显式赋值）；**模式与节拍**半边（`base_external_force_torque.mode=interval` 及 `interval_range_s`、`push_robot.interval_range_s`）**未覆盖 ⇒ 继承进 lizard**，golden 里已能看到该形状（`mode: interval`） |
| 是否补 C 层 | **不需要**：可归属的增量是 `train.py`/`play.py` 的 wrapper 与恢复门，已由 1.3a S01–S10 + 1.4b C 层覆盖；不可归属部分按未知处理，既不据此判失效，也不据此补跑 |
| **新登记风险** | fork 树里的 DR 放大**会静默改变新 run 的 DR**（值被本仓覆盖、模式与节拍走继承），目前只有 golden 差异能抓到。这同时是"golden 承重"的正面证据。建议后续把这三处 DR 改动显式收编进本仓参数（或至少在 `fork_patches` 里标明其语义），避免“改 fork 树 = 改实验且无痕” |

## 2.1 · 配方线生命周期（离线半，2026-09-16）

**性质**：**追加**条目。只覆盖 `ARCH_PLAN.md` §2.1/§2.2 的**离线部分**（L01 全部、L05/L06 的离线半边）。L02/L03/L04 与 L05/L06 的入口侧**未跑，记未知**；旧入口尚未接线 ⇒ 只能声明"新入口限制有效"，不得据本批宣称 Step 2 通过。

### 前提

| 项 | 值 |
|---|---|
| 项目 rev | `2a3883c`；**工作树未冻结** —— 另有并行批次的未提交改动（`rl_exp/tasks/*.py`、`cfg_lock.json`、`FAMILY.md`、`PLAN.md`、`check_cfg_lock.py`、`check_dr_parity.py`、`check_version_docs.py`、`run_offline_checks.bat`，以及新增的 `recipe_lines.py`、`versions/cfg_baselines.json`、`versions/lizard/parkour/cfg_lock.json`、`versions/lizard/v15/`）。本批改动 = 新增 `versions/lines.json`、`check_recipe_registry.py`、`test_recipe_registry_gate.py`；改 `run_offline_checks.bat`（`[29][30]`）与 `ARCH_PLAN.md` |
| 任务 id | 不适用（离线闸门，不构造 env；线由 `recipe_lines.discover()` 发现） |
| 设备 / env 数 / seed | 不适用（无 sim、无 env、无随机源） |
| 框架组合 | 未绑定（本批为纯文本 gate，不读 isaaclab/rsl_rl 版本） |
| 预设容差 | 无（离散判定：每条规则红或绿） |

### 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| L01 显式身份 | `python rl_exp\tools\verify\check_recipe_registry.py` | **通过**：`recipe lines discovered: 2 ['lizard', 'lizard/parkour']`、`index: lines.json revision=1 entries=2`、`lifecycle consistent`。未登记线、悬空线、第三态 `status`、缺字段、夹带 run 字段均被拒绝 |
| L05 记录冻结（离线半边） | 同上 | **通过**：索引入口键白名单（夹带 run-scoped 字段即红）；生命周期不是 env/agent cfg 的输入 ⇒ 不进配方摘要。"启动后改目录，原 T1 不变"需 manifest 接线 ⇒ **未知** |
| L06 迁移生效（离线半边） | `python rl_exp\tools\verify\test_recipe_registry_gate.py` | **通过**：23 例反证 + 1 例时钟无关性全部着火。提示期（`active` + 声明 + 条件未满足）判绿、`retired` 且条件已满足判绿、提前退休判红、到期仍 `active` 判红、自由文本条件判红。"提示期放行结果与无声明 `active` 逐项相同"需入口侧 ⇒ **未知** |
| 反证先行 | 同上 | 每条拒绝都由合成树 + 合成索引驱动，未触碰真实索引；`retire_not_before` 为 revision 型时同一索引在两个不同日期判据一致（无时钟依赖） |

### 结论与边界

- **通过**：L01（身份解析与拒绝）；L05/L06 的离线半边
- **未知**：L02（入口执行）、L03（历史续训）、L04（历史兼容）、L05/L06 的入口侧 —— 全部需 §2.2 接线，属阶段 C
- **未做**：A3（`check_cfg_lock` 身份改消费显式映射）等锁格式 v3 结构冻结后重读；A0（布局改造 `main/` + `baseline`、参数文件按闸门改名、`is_main_line` 判据更换）等并行批次落地
- **口径**：本批**未跑全量套件**（`run_offline_checks.bat` 端到端），只跑了新增两条 ⇒ `[2][12][24][28]` 与新增条目的共存**未在本批验证，记未知**
- **证据**：gate 脚本 + 上表命令（未另存日志文件；`verify_logs/` 现存的是套件整跑日志）

## 2.1b · 配方身份映射（离线，2026-09-16）

**性质**：**追加**条目，补 §2.1 的另一半 —— `任务 ID → 配方 + 修订 → 配置入口` 的显式映射。仍只覆盖离线部分；入口侧（L02/L03/L04）未跑，同 §2.1 记**未知**。

### 前提

| 项 | 值 |
|---|---|
| 项目 rev | `a5a7fab` + 未提交改动（本批 = 新增 `versions/recipes.json`、`check_recipe_map.py`、`test_recipe_map_gate.py`；改 `run_offline_checks.bat`、`FILEMAP.md`、`ARCH_PLAN.md`）。工作树**仍未冻结**：并行批次 19 项未提交，锁 v3 迁移进行中 |
| 任务 id | 全部 34 个注册任务（v0 家族 8 + teacher v1–v14 共 24 + parkour 2） |
| 设备 / env 数 / seed | 不适用（无 sim、无 env、无随机源） |
| 框架组合 | 未绑定（纯 stdlib：`ast` 解析注册模块，不 import registry、不 import isaaclab） |
| 预设容差 | 无（离散判定） |
| 声明真值来源 | 各任务 `params_version` 取自**现行** `cfg_lock` 条目（主线 32 + parkour 2）：teacher = `vN`、parkour = `v1`、v0 家族 = `None` |

### 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| L01 身份映射 | `python rl_exp\tools\verify\check_recipe_map.py` | **通过**：`recipes declared: 34 | task mappings: 34`，与 `gym.register` 逐字一致（env/agent 入口、任务键集、line 引用） |
| 反证 | `python rl_exp\tools\verify\test_recipe_map_gate.py` | **通过**：16 例地图反证 + 6 例绑定反证全部着火，外加"从真实 `tasks\__init__.py` 读出 34 个任务" |
| L01 配置侧绑定（原计划归 A3） | `E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\check_recipe_map.py --bind-config` | **通过**：34 个声明的 `env_cfg_entry` 逐个导入并**构造**实例，其 `params_version` 与 `legacy_task_version` **34/34 一致**（teacher = `vN`、parkour = `v1`、v0 家族 = 双向 `null`）。类属性读不到（1.0 已证）故必须构造；构造失败记红、不记跳过 |

绑定不需要锁文件，因此**未等锁 v3 冻结即可执行** —— 早先"等 v3 结构冻结"的判断是错的，已纠正。绑定落地后 `check_cfg_lock.py` 里按任务 id 推断版本的旧校验（`_TASK_VERSION`）成为冗余：`id 分词 == declared`（本闸门）+ `declared == params_version`（本闸门）⇒ 传递出 `id 声明 == 实际版本`。该文件属并行批次，删除留给 A3 收口。

### 本批修正（两处，均由反证抓到）

- **双向校验写错**：首版判"任务 id 带 `-vN` ⇒ 声明必须等于 vN" ⇒ 8 个 v0 家族任务被误判。它们的 `params_version` 实测是 `None`，**id 后缀 `v0` 不是配方声明**。改为单向：声明了版本就必须是任务 id 的 dash 分词；并加 `v1` 不被 `Lizard-Rough-v14` 满足的陷阱反证
- **解析器读空注册表**：首版 `registered()` 只读位置参数，而 `gym.register` 的 `id` 是关键字参数 ⇒ 注册表读成空、**闸门静默通过**。由"真模块读出 34 个任务"这一例钉死

### 结论与边界

- **通过**：L01（配方身份映射与拒绝 + 配置侧绑定 34/34）
- **未知**：L02/L03/L04 与 L05/L06 的入口侧（同 §2.1）
- **未做**：`check_cfg_lock.py` 里冗余的旧 `_TASK_VERSION` 校验删除（并行批次文件，留 A3 收口）；A0 未动
- **口径**：本批同样**未跑全量套件** ⇒ `[31][32]`（含 `--bind-config`）与既有条目的端到端共存**未验证**
- **证据**：gate 脚本 + 上表命令（未另存日志文件）

## B0 · 基线冻结（阶段 B 开工，2026-09-16）

**性质**：**追加**条目，`ARCH_PLAN.md` §2.4 阶段 B 的开工准备。**不改任何实现**：新增冻结闸门 `check_golden_frozen.py`（套件 `[35]`）+ 本节记录。开工第一件事是钉住"整改前 golden"——它同时是硬 A 的比较对象与 B 期间被禁止移动的那份东西。

### 锚（阶段 B 的验收预期值）

| 项 | 值 |
|---|---|
| 项目 rev | `020e6fb34034b2621f359e999cb441463b3127fc`（`020e6fb`） |
| 基线文件 | `versions/cfg_baselines.json` sha256 `b18a517c43ddef5f…`（764 B）；`versions/lizard/cfg_lock.json` sha256 `4326bd0bbf0b0b26…`（2,581,820 B）；`versions/lizard/parkour/cfg_lock.json` sha256 `6c60a92633235478…`（123,845 B） |
| 框架组合 | `isaaclab=28a37cecdd43\|rsl_rl=source:28a37cecdd43\|python=3.12.13` |
| 三文件状态 | `git status --porcelain` 对这三条为空 ⇒ 锚是**提交态字节**，不受并行批次未提交改动影响 |

### 比较口径（硬 A 之前冻结，不由实现者事后选）

- **比较对象**：新构建器**构造**出的 cfg 树 vs golden 条目内的 `snapshot`；身份沿用 `check_cfg_lock` 的 `env_cfg_class` / `agent_cfg_class` + `digest`。B 期间**禁改比较器与规范化规则**——只禁 `--update` 挡不住"把标准搬到实现那一侧"。
- **缺失 ≠ 默认值**：沿用快照格式 2 规则——缺失写缺失哨兵，默认值写默认值。
- **顺序有语义**：obs 组 / term 序 / joint 序 / 地形列→combo 序均有序并纳入摘要。
- **浮点**：`repr` 往返，**无容差**；非有限值走标签，不用容差掩盖差异。
- **允许变化的路径**：B1 期间**期望为空**；真出现就逐条列**字段路径** + 旧值 + 新值 + 转换规则 + 不影响运行语义的验证，禁整字段或整子树豁免。

### 等价性验证（本次实测，只读）

| 步骤 | 命令 | 结果 |
|---|---|---|
| 干净树再生 | `git clone --local --depth 1 E:\Robot E:\rl_b0_020e6fb`；`set PYTHONPATH=E:\rl_b0_020e6fb` + `set RL_ISAAC_ROOT=E:/IsaacLab`；`check_cfg_lock.py` | **34 任务 / 2 线**；**v11/v12 各 3 条路径漂移**：`env.curriculum.joint_sir.min_episode_frac: 0.5 -> <absent>`、`env.curriculum.joint_sir.require_survive: true -> <absent>`、`env.curriculum.joint_sir.unmeasured_prior: 0.5 -> <absent>` |
| 工作树 | `check_cfg_lock.py`（本仓） | **36 任务 / 3 线**，`CFG_LOCK_OK`（`baseline` 线随并行批次新增，属 A 带范围） |
| 字段归属 | `git grep -n unmeasured_prior HEAD -- rl_exp/tasks/teacher_mdp.py` | **空** ⇒ HEAD 无该字段；现只在未提交的 `teacher_mdp.py`（定义处 `:1026-1037`） |

**结论（硬 A 前置未满足，写死）**：现 golden 的 **v11/v12 条目只由未提交的工作树内容生成** —— `cfg_baselines.json` 的 `created_rev 2a3883c` + `created_dirty: true` 由此得到具体解释：不是"戳不好看"，而是这批条目**不可由任何 rev 取得**。⇒ **B1 可以开工**（B1 不改 cfg 内容，改动面与 golden 无关），**B3 必须等该内容被提交后重跑上表第 1 行**，全绿才可比。否则硬 A 比的是一个谁也重建不出来的期望值。

### B 期间冻结（机械看守，不靠约定）

禁 `cfg_lock --update`、禁手改锁、禁替换 golden、禁改比较器与规范化规则；由 `check_golden_frozen.py` 按摘要看守——自测 `GOLDEN_FROZEN_SELFTEST_OK`（改字节 / 删文件 / 不变三种都判过），实跑 `GOLDEN_FROZEN_OK (3 baseline file(s) unchanged since rev 020e6fb)`。**合法重基线** = 同一次改动里同时改该闸门的 `FROZEN` 表与本节（附理由 + 逐字段差异审查）；只改一侧即判红。

### 边界（不得据本节宣称）

- 本节只钉"**预期值未被移动**"：**不判 golden 是否正确**（B3 的活）、不判 `baseline` 线新增（2 任务、落点未跟踪）、36 vs 34 计数差异、参数加载读模块（`_load_params` 缓存/隔离）——均属 A 带。
- 干净 clone 需补机器路径配置（`paths.yaml` 是机器本地文件、不在仓内，`RL_ISAAC_ROOT` 由环境变量给）⇒ "可追溯"的准确含义是"**代码内容可由 rev 取得，主机路径由 `paths.yaml`/环境变量提供**"，不是"克隆即可跑"。
- 本次只验读模式；**未跑全量套件端到端** ⇒ "`[35]` 与既有条目共存"按 A 带同口径记**未验证**。

## 2.4 · A0 布局迁移（ARCH_PLAN 2.1a；声明先于执行）

**性质**：**追加**条目。A0 会触碰 16 个冻结物，所以先落"允许变化清单"**再执行** —— 否则 `--update-locks` 之后的"全绿"可能只是把意外变化一并接受。本节分两段：声明（执行前落盘）与回填（执行后补）。

### 声明的允许变化清单（执行前）

| 对象 | 允许的变化 | 不允许的变化 |
|---|---|---|
| 17 个参数文件（dev 1 + 冻结 16） | **文件名** `lizard_params.yaml` → `main_params.yaml`（`recipe_lines` 规则要求基名 = 线名） | 内容任何一个字节 |
| 16 个冻结 `vN/asset_lock.json` | **自身 yaml 的仓库相对路径键**（`versions/lizard/vN/lizard_params.yaml` → `versions/lizard/main/vN/main_params.yaml`） | 资产 sha256（`lizard.urdf` / `lizard.usda` / meshes）、键序、其余键、键的增删 |
| 线级 `cfg_lock.json` | **位置** `versions/lizard/` → `versions/lizard/main/`；内容**零变化** | 任何条目或摘要变化。若真出现，说明快照记录了路径 ⇒ 必须逐字段审查并在此单独声明后才接受 |
| 16 个 `vN/base.json` | **无变化**（规则是"线内裸 `vN` 先命中本线"，`main/v14` 写 `v13` 仍解析到 `main/v13`） | 任何变化 |
| `vN/` 内的 PLAN/NOTES/yaml 正文 | **无变化** | 任何变化 |

### 前置检查（执行前，已过）

| 项 | 结果 |
|---|---|
| A0 写入集 ∩ 脏集 | **空** —— 3 个脏文件与本迁移无关，脚本明确列为"ignored on purpose" |
| 被搬目录内未跟踪文件 | 无（v15 已于 2026-09-16 入索引，`baseline/` 已提交且不在移动集） |
| 计划移动 | **34 项**：16 个版本目录 + 线 `cfg_lock.json` + `lizard_params.yaml` + 16 处改名 |

### 回填（执行后）

### 回填（执行后，2026-09-16）

| 项 | 结果 |
|---|---|
| 实际移动 | **34 项**：16 个版本目录 + 线 `cfg_lock.json` + 线参数 + 16 处改名。**首版脚本漏了线根 dev yaml 的改名**，留下 `main/lizard_params.yaml`，被 `recipe_lines` 当场拒绝（"basename names its line"）⇒ 已补 `git mv` 并把该步写进脚本 |
| 纯改名 | 55 个文件为 `R`（内容零变化）：线 `cfg_lock.json`、16 组 PLAN/NOTES/base.json 与版本内其它工件 |
| 允许变化项 | 16 个 `asset_lock.json` 各 **1 行增删**，唯一变化 = 自身 yaml 路径键（`versions/lizard/vN/lizard_params.yaml` → `versions/lizard/main/vN/main_params.yaml`）；**sha256 两侧逐字节相同** ⇒ 改名没动内容；`baseline/v1` 与 `parkour/v1` unchanged；16 个 `base.json` 内容未变 |
| 线 golden 漂移 | **无** —— `[24] CFG_LOCK_OK (36 tasks, 3 line(s), isaaclab=28a37cecdd43\|rsl_rl=source:28a37cecdd43\|python=3.12.13)`。快照记值不记 yaml 路径，与预期一致（不是"重生成后全绿"，`--update` 全程未跑） |
| 冻结看守 | `[35] GOLDEN_FROZEN_OK (3 baseline file(s) unchanged since rev 020e6fb)` ⇒ 线 golden 的内容确实没动 |
| 闸门 | **`ALL_OFFLINE_CHECKS_PASSED (37/37 in 30.7s)`**；`[12] VERSION_DOCS_OK` |
| 计划外（必须记） | A0 暴露一个**既有缺陷**：`manifest.asset_digest()` 按版本名 glob 资产锁，而 `v1` 现在三条线命中（baseline/main/parkour）⇒ 旧代码取排序第一 = **取错锁**。已改为按声明的 `params_line` 解析；无声明时对多命中**拒绝而不猜**；`rebuild.py` 改为从**记录里的锁路径**反推线（比再查一遍更忠实于记录） |
| 跟随改动 | `lizard_env_cfg` / `teacher_env_cfg` 的 `params_line`（`lizard` → `lizard/main`）与 yaml 路径常量；6 个闸门/工具的写死路径；FAMILY 16 行键（`\| vN \|` → `\| main/vN \|`）；FILEMAP 16 行路径；活文档散文（FAMILY/PLAN/REWARDS/OBS/README） |
| 未改（有意） | 冻结记录 `vN/PLAN.md` 与 `NOTES.md` 里的旧路径、`ACCEPTANCE.md` 的历史小节 —— 记录写的是当时那棵树，改写成今天的布局就不再是证据 |
| 已知上限 | `recipe_lines` 的版本目录规则仍是 `v<N>`；放宽到任意标签只在某线首版不叫 v1 时才需要（baseline 用了 v1 ⇒ 今日不需要） |

### 独立审核与修复（2026-09-16，审核方复签阶段 A）

审核方对 `9ee6773` 做了**逐字节**核验（迁移前后 Git 对象比对：17 个参数文件内容不变、16 组 base/PLAN/NOTES 不变、主线 golden 不变、16 个 asset_lock 的变化严格限于自身 YAML 路径键），结论 **A0 迁移通过**，同时指出三项并已修复：

| 编号 | 问题 | 修法与提交 |
|---|---|---|
| P1 | `9ee6773` 的 `teacher_env_cfg.py` 已导入 `components`，而该模块未跟踪 ⇒ **HEAD 自身不可导入**，37/37 只证明本机工作树 | 完整提交组件库 `1083952`；复核查明套件引用的 38 个文件全部已跟踪且存在，导入链闭合 |
| P1 | `check_recipe_map.bind()` 只比 `params_version`、未比 `params_line` ⇒ 把某配方指到**另一条已存在线**时两侧均返回"无问题"，而配置仍属原线 | `bind()` 增比 `params_line`，反证加"版本对但线错"与"配置不声明线"两例 `83f0a40`；真树 36/36 一致 |
| P2 | A3 未收口：`check_cfg_lock` 仍以任务名尾缀正则推导版本、且不消费 `recipes.json` ⇒ 身份规则两套并存 | 删除该推导，改消费显式映射（声明版本 == `params_version`；声明版本在该线须有冻结目录；映射线与 `params_line` 一致），golden 内容比较不动 `83f0a40` |

**复审证据**：修复后全套 **38/38**（含 `[12] [24] [25] [31] [32] [35] [36]`），审核方据此**签收阶段 A**。

**边界（不因签收而改变）**：L02–L04 与 L05/L06 的**入口侧**仍未接线 ⇒ 按原口径记**未知**，属阶段 C；本次签收不覆盖运行期验收。
**教训（记一笔，防重犯）**：两次同类事故（`9ee6773` 的 components、更早的 v15）根因相同 —— 提交前未核"HEAD 能否独立成立"。此后提交前查两件事：① `git diff --cached`（索引里到底有什么）② 新提交物引用的文件是否同样进入 HEAD。

## B1 · 组件库切片 1（height sensing，2026-09-16）

**性质**：**追加**条目，阶段 B（`ARCH_PLAN` §2.4）的 B1 第一片。改动面 = 新增 `rl_exp/tasks/components.py`；`rl_exp/tasks/teacher_env_cfg.py` 三处（import、基类单点写入、V3 删掉重复写入）；新增闸门 `test_component_ownership.py`（套件 `[37]`）。

### 落地

| 项 | 内容 |
|---|---|
| 组件形态 | `components.height_sensing(version, ...) -> {name: sensor}`：v1/v2 = 单个地面 grid scanner；v3+ = `height_scanner=None` + 4 个 `{foot}_foot_ring`（几何仍读 yaml `v3.foot_ring`） |
| 写入点 | 由 3 处（基类建 scanner、V3 置 `None`、V3 再建 4 环）并为 **1 处**（基类一次循环 `setattr`） |
| 版本解析 | 按版本判定（`GRID_SCANNER` / `FOOT_RINGS` 两张表），未知版本**抛错**；不再靠 MRO 静默继承 |
| 刻意不动 | `RingPatternCfg` / `ring_pattern` 留在 `teacher_env_cfg`（其 `__callable__` 路径已写进 golden 76 处，搬移 = 无行为变化却重写全部 V3+ 条目）；pattern 改由调用方注入 |

### 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过（A0 落地前那次）**：`36 tasks, 3 line(s)`、`CFG_LOCK_OK` —— 换成单点写入后 36 个任务的 cfg 树逐字段不变 |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (1 component(s), 5 owned name(s), 1 host file(s))`；12 个版本各自解析出**完整且唯一**的形态（grid 形态无环、ring 形态无 grid、四脚环几何一致）；`v99` 未声明版本抛 `ValueError` |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` —— 直接赋值 / 写被拥有实体的字段 / 字面量 `setattr` 三种"第二个写入者"都着火，"走组件循环"不着火 |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（见下节重锚） |

### B0 追加：A0 迁移触发的合法重锚

| 项 | 值 |
|---|---|
| 触发 | A0 把主线搬进 `versions/lizard/main/`（git staged rename 34 项）：`versions/lizard/cfg_lock.json` → `versions/lizard/main/cfg_lock.json` |
| 证据 | 迁移前后 sha256 **完全相同** `4326bd0b…a12b`（2,581,820 B）⇒ 内容零变化、纯搬家；另两份基线摘要亦未变 |
| 处置 | 按本闸门声明的合法路径：同一次改动里改 `FROZEN` 表路径 + 补本条记录，**未改任何摘要值** |
| 残留 | 锁文件内部 `note` 仍写 `line 'lizard'`（改名收尾属 A0 清单），不影响条目内容，也不影响硬 A 的比较对象 |

### 边界与阻塞（不得据本片宣称通过）

- **门 1 的时点限定**：上表门 1 是 **A0 落地前**的实跑（当时线键仍是 `lizard`）。A0 落地后 `[24]` 独立红于 `lizard: 32 task(s) declare this line … but no such line exists ['lizard/baseline','lizard/main','lizard/parkour']`（`params_line` 收尾在 A0 清单里）⇒ **切到新布局后必须重跑门 1**，本片不以 A0 前的绿替代。
- **端到端未验证**：全量套件在 `[2]` 即失败（A0 中场：16 个 `asset_lock.json` 键未按 `--update-locks` 重生成），fail-fast 让 `[24]`–`[37]` 全部跳过 ⇒ `[35]/[37]` 与既有条目的共存**本批未验证**。
- **硬 A（B3）仍不可做**：v11/v12 基线不可由任何 rev 取回（见 B0 节），须待那批内容提交后重跑 clone 等价性。
- **后续切片**：`terminations` → `terrain block` → `commands` → `obs 组` → `_load_params` 收敛（最后一片等 A1 提交，避免与其缓存/隔离改动互踩）。

## B1 · 组件库切片 2（terminations，2026-09-16）

**性质**：**追加**条目。改动面 = `components.py`（新增 `terminations` 组件与 5 张声明表）、`teacher_env_cfg.py`（4 处写入点并为 1 处，另清掉因此变死的 `DoneTerm` import）、`test_component_ownership.py`（`OWNERSHIP` 加该组件 + 逐版本形态校验）、`FILEMAP.md`。

### 落地

| 项 | 内容 |
|---|---|
| 组件形态 | `components.terminations(version, *, params, base_contact, base_body) -> {name: term 或 None}`：`base_contact` 由调用方传入继承来的框架 term（其 `func` 是框架的，只原地收窄 sensor），其余按配方声明构造 |
| 写入点 | 4 处 → **1 处**：基类 `:631` 收窄、V3 `:949` 置 `None`、V3 建 `tilt`、V10 `tilt = None`、V14 建 `roll_over` 全部并入基类一次循环写入 |
| 声明表 | `BASE_CONTACT_KEPT`（v1/v2 收窄）· `BASE_CONTACT_DROPPED`（v3+ 丢弃）· `TILT_ADDED`（v3+）· `TILT_FLAG`（v10+，由 yaml `v10.tilt_terminate is None` 决定是否留存）· `ROLL_OVER`（v14） |
| 刻意保留的语义 | ① v1/v2 **不写** `tilt` 键（写了 `None` 就等于给老配方长出一个没人选的键，快照看得出）；② v10+ 的取舍仍读同一面 yaml 标志（不把决定搬到代码）；③ `base_contact` 传引用收窄而非重建，`func` 仍指框架 |

### 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))`（A0 后的新线键下）—— 4 处写入并为 1 处后逐字段不变 |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (2 component(s), 8 owned name(s), 1 host file(s))`；新增逐版本形态校验：键集恰为 `base_contact`(+`tilt`)(+`roll_over`)、v1/v2 保留的 term 就是继承来的那一个且 sensor 收窄到 base body、`TILT_FLAG` 版本按标志判、`v99` 抛 `ValueError` |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（未重锚、未改摘要） |

### B0 结论文更新：B3 前置**已解锁**

| 步骤 | 结果 |
|---|---|
| HEAD | `c33bbf6`（A0 + 身份收编 + 套件规则已提交；工作树除一个 eval 产物目录外干净） |
| 字段是否已提交 | `git grep -n unmeasured_prior HEAD -- rl_exp/tasks/teacher_mdp.py` **有命中**（`:1026/1037/1076/1172`）⇒ B0 当时"只在未提交工作树里"的状态已结束 |
| 干净树再生 | 新克隆 `E:\rl_b1_check`（`PYTHONPATH` 指向克隆、`RL_ISAAC_ROOT` 补机器路径）+ `check_cfg_lock.py` → **36 任务 / 3 线 / `CFG_LOCK_OK`** |

⇒ **"整改前 golden 可由 rev 取回"成立**，B0 §结论 里"硬 A 前置未满足"一条**自此失效**（原文保留作留痕，以本条为准）。硬 A（B3）**技术上已可做**：比较对象=冻结摘要那三份文件，再生路径=任一干净 clone。

### 边界

- **单写者范围**只到 `teacher_env_cfg.py`：`baseline_env_cfg.py` / `lizard_env_cfg.py` / `parkour_env_cfg.py` 仍各自写 `base_contact` / `tilt`（属不同配方线，未迁；`OWNERSHIP`+`HOSTS` 只声明已迁范围，不冒充全仓）。
- PLAY 变体继承同一单点：已核 `play_utils.apply_play_wiring` 不写 terminations。
- **v15 待实现的手续**：基类对未声明版本**抛错**，v15 落地时须在 `GRID_SCANNER`/`FOOT_RINGS` 与 terminations 三组表里各声明一次，否则构造即失败（错误信息给出可声明位置）。
- 本轮只跑三闸，**未跑全量套件** ⇒ `[37]` 与既有条目的端到端共存仍未验证（A0 后套件已由 A 带补规则，可在收尾时整跑）。
- 后续切片：`terrain block` → `commands` → `obs 组` → `_load_params` 收敛。

## B1 · 组件库切片 3（terrain block，2026-09-16）

**性质**：**追加**条目。改动面 = `components.py`（新增 `terrain` 组件 + `TERRAIN_BY_RECIPE` 单表）、`teacher_env_cfg.py`（5 处写入点并为 1 处；清掉因此变死的 `build_param_grid_terrain_cfg` import）、`test_component_ownership.py`（`OWNERSHIP` 加该组件 + 逐版本形态校验 + `HOSTS` 旁声明 PLAY 后处理器）、`FILEMAP.md`。

### 落地

| 项 | 内容 |
|---|---|
| 组件形态 | `components.terrain(version, *, params, payloads) -> {terrain_type, terrain_generator, max_init_terrain_level}`；`TERRAIN_BY_RECIPE` 单表给出**每配方的 payload 与起始行**（v1/v2 冻结生成器/5；v3 换 Miki 地形/0；v4 碎石换 payload/继承 0；v5–v10、v13/v14 用 V5 payload/None 均匀；v11/v12 由自身 grid 段构建/None） |
| 写入点 | 5 处 → **1 处**：基类 3 行、V3 换生成器 + 起始行、V4 换生成器、V5 换生成器 + 起始行、V11 参数格 + 起始行全部并入基类一次循环写入 |
| 关键保留 | ① **payload 常量不搬**：`check_obs_layout.py` 与 `terrain_preflight.py` 从 `teacher_env_cfg` import 它们（`terrain_preflight` 还按版本建表），搬移会牵动两个闸门与多处历史文档；payload 改由调用方按名传入，选择表留在组件侧。② v11 的"先建后替换会丢 `curriculum=True`"这条坑消失——不再有第二次替换。③ 起始行语义（v3.5 最易行、v5+ SIR 均匀起始）写进声明表注释，不再散在子类里 |

### 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` —— 地形三字段换单点写入后逐字段不变（含 v11/v12 的参数格地形） |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (3 component(s), 11 owned name(s), 1 host file(s))`；新增校验：块字段恰为三项、`terrain_type` 恒 `generator`、取到的就是**它声明的那份 payload**（对象身份）、起始行与声明相等、由 grid 段构建的只应是 v11/v12、`v99` 抛 `ValueError` |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（未重锚） |

### 边界

- **PLAY 是已知的、被声明的第二个写入者**：`play_utils.apply_play_wiring` 会给每个 PLAY 变体重写起始行与网格形状（确定性评估不漫游）。它是配方级决定、非"某版本悄悄覆盖兄弟"，故**不进扫描范围**，但记在 `test_component_ownership.py` 的 `HOSTS` 旁，且一旦退化成按版本覆盖就必须迁进组件。
- 单写者范围仍只到 `teacher_env_cfg.py`（`rough_env_cfg.py` / `parkour_env_cfg.py` / `baseline_env_cfg.py` 各有自己的地形块，属其他配方线）。
- 本轮只跑三闸，未跑全量套件。
- 后续切片：`commands` → `obs 组` → `_load_params` 收敛。

## B1 · 组件库切片 4（commands，2026-09-16）

**性质**：**追加**条目。改动面 = `components.py`（新增 `commands` 组件 + `COMMAND_RANGE`/`PARTICLE_COMMAND`/`FULL_FORWARD_RANGE`）、`teacher_env_cfg.py`（6 处写入点并为 1 处，另加基类 `PLAY_PINS_COMMAND_RANGE` 与两个 PLAY 类的同名 ClassVar）、`test_component_ownership.py`（`OWNERSHIP` 加该组件 + 逐版本范围校验）、`FILEMAP.md`。

### 落地

| 项 | 内容 |
|---|---|
| 组件形态 | `components.commands(version, *, params, base_velocity, pins_full_range) -> {base_velocity: term}`。侧向/偏航范围（`(-0.5,0.5)`/`(-1,1)`）对所有配方是同一套论文收窄；**前向范围**按配方：v1/v2 `(-1,1)`、v3/v4 `(-1,2)`、v5–v10/v13/v14 取 yaml `v5.commands.lin_vel_x`、v11/v12 换 `ParticleVelocityCommandCfg`（逐字段从原 term 拷贝，含 ranges） |
| 写入点 | 6 处 → **1 处**：基类 3 行、V3 前向范围、V5 yaml 范围、V11 换 term 全部并入基类一次循环；`V3_PLAY`/`V4_PLAY` 的"钉满量程"改为**声明式**——类上 `PLAY_PINS_COMMAND_RANGE: ClassVar[bool] = True`，由组件统一施加 |
| ClassVar 选择理由 | PLAY 的钉范围是**配方级**决定（评估没有课程去中途放宽），不是"某版本偷偷覆盖兄弟"；ClassVar 不进快照（快照格式 2 已定），故**零 golden 影响**，且把这条规则从两处散写收进一张表 |
| 发现并修正（门 1 抓到） | 首版把 `v4` 的前向范围写成 `(-1,5)`——那是 `V4_PLAY` 的值，`v4` 训练配方沿用 v3 的 `(-1,2)`。逐字段差异实证：`env.commands.base_velocity.ranges.lin_vel_x.__tuple__[1]: 2.0 -> 5.0`（仅 `Lizard-Rough-v4` 一条，`-Play-v4` 相符）。按 golden 修正声明表后全绿 |

### 检查与结果

| 门 1（字段面） | `check_cfg_lock.py` | **通过（修正后）**：`CFG_LOCK_OK (36 tasks, 3 line(s))`；中途 1 条漂移已由 `--diff --tasks` 定位并修掉，见上 |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (4 component(s), 12 owned name(s), 1 host file(s))`；新增校验：12 个配方各自的前向范围、侧向/偏航恒为该收窄值、粒子配方的 term 类型与从文档读到的 `v_pr_threshold`/`command_jitter`、`resampling_time_range=(1e9,1e9)`、非粒子配方**不得替换**该 term（对象身份）、`pins_full_range=True` 时恒为满量程、`v99` 抛 `ValueError` |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（未重锚） |

### 边界

- 课程在**运行期**改 `commands.base_velocity.ranges`（`StagedCurriculumTerm` 的 stage 0 播种 cfg、后续按 `success_rate` 放宽）——那是运行时行为，不是 cfg 写入点，本组件与 golden 都不覆盖它。
- 单写者范围仍只到 `teacher_env_cfg.py`。
- 本轮只跑三闸，未跑全量套件。
- 后续切片：`obs 组`（表驱动两份真相合一处）→ `_load_params` 收敛。

## B1 · 组件库切片 5（obs 组，2026-09-16）

**性质**：**追加**条目，B1 的**最大一片**。改动面 = `components.py`（新增 `observations` 组件 + `_teacher_terms`/`_ring_terms` 两个构造器 + `SINGLE_GROUP_OBS`/`PROPRIO_TERMS`/`BASELINE_PRIV_TERMS`/`SPEC_TERMS`/`RING_NOISE` 声明）、`teacher_env_cfg.py`（3 处写入点并为 1 处；清掉因此变死的 `ObservationGroupCfg`/`ObsTerm` import）、`test_component_ownership.py`（`OWNERSHIP` 加该组件 + 逐版本组/序校验）、`FILEMAP.md`。

### 为什么 term 定义也得搬

被拥有的是**组容器**（`policy`/`proprio`/`extero`/`priv`），而 `self.observations.policy.height_scan = ObsTerm(...)` 这类**组内 term 写入**同样决定组的最终状态 ⇒ 按本组件库已声明的规则（"写被拥有对象的字段也算第二个写入者"）它必须一并迁入，否则"单写点"是假的。因此 11 个教师 term 的构造、spec 剥离、v3 分组、v12 加噪全部进组件。

### 落地

| 项 | 内容 |
|---|---|
| 组件形态 | `components.observations(version, *, params, base_policy, spec) -> {组名: 组 或 None}` |
| 单组配方（v1/v2） | 在框架的 `policy` 组上原地追加 11 个 term，再把 spec 未包含的增量 term 置 `None`（`sorted(every - allowed)`，与旧实现同序） |
| 拆组配方（v3+） | `proprio`（7 个框架 term，按固定序）、`extero`（4 个脚环 term，lf/rf/rl/rr 序）、`priv`（5 个基线 + 按 spec 的增量 term）、`policy = None` |
| v12 加噪 | extero 的 `func` 与参数在构造时即按 `v12.height_noise` 给出（含 `foot_index`），不再"先建后改" |
| 两份真相合一处 | 旧的"V3 硬编码 7/10 个名字的清单"消失：分组的名字序列现在由 `PROPRIO_TERMS`/`BASELINE_PRIV_TERMS`/`SPEC_TERMS` 三张表统一给出，spec 表只回答"这个配方含哪些增量项" |

### 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` —— 整棵 obs 树（含 36 个任务的组名/term/序/clip/params）逐字段不变 |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s), 1 host file(s))`；新增校验：单组配方只产 `policy` 且 spec 未含的增量项为 `None`（在含的必须是 term）、拆组配方键集与 `policy is None`、三组的 **term 序逐项相等**、`proprio` 的 term **就是框架那一个**（对象身份）、v12 的 extero 是 `NoisyFootRing` 且带 `foot_index`、非 v12 的 extero 不带噪声、`v99` 抛 `ValueError` |
| obs 契约闸门 | `check_obs_layout.py`（套件 `[8]`，独立实现） | **通过**：`OBS_LAYOUT_OK`（v1/v2/v3/v4/v5/v11/v12 复检组名/term 序/c_k 一致性） |
| import 面 | `check_pxr_leak.py`（套件 `[14]`） | **通过**：`OK (task cfg import chain is pxr-clean)` —— 新模块进了 env cfg 的 import 链，仍是 pxr-clean |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（未重锚） |
| 接线 parity | `check_dr_parity.py`（套件 `[2]`） | **通过**：`PARITY_OK`（family 20 / teacher 20 行）。切片 2 把 teacher 的 `base_contact` 收窄行移进组件后，该行只存在于家族侧 ⇒ 按该闸门自带的扩展点把这条**已审查的单侧差异**列入 `ALLOWLIST`（附理由 + golden 佐证），未放宽任何其他比对项 |

### 本片修正（均由反证/断言抓到）

- **门 2 断言写错（非实现错）**：首版用 `vars(group)` 比 term 序，结果组自身的配置字段（`concatenate_terms`/`enable_corruption`/…）被算进去 ⇒ 全绿判红。改为先减去一个空 `ObservationGroupCfg` 的自有字段，再比 term 序列。

### 边界

- `TEACHER_PRIVILEGED_SPEC` **留在 `teacher_env_cfg.py`**（`check_obs_layout.py`、`OBS.md`、`FAMILY.md` 都从代码侧引用它），由调用方按 `spec=` 传入——与切片 3 的 payload 注入同一策略。
- 运行期的加噪事件 `events.sample_ring_noise` 仍在 v12 类里（那是 reset 事件，不是 cfg 写入点，且 PLAY 会把它置空 ⇒ 干净扫描）。
- 单写者范围仍只到 `teacher_env_cfg.py`。
- 本轮只跑五闸（门 1、门 2、obs 契约、pxr、冻结），未跑全量套件。
- 后续切片：只剩 `_load_params` 收敛（4 份定义 → 1，等 A1 的读模块稳定）。

## B1 · 组件库切片 6（`_load_params` 收敛，B1 末片，2026-09-16）

**性质**：**追加**条目，B1 的最后一片。改动面 = 新增 `rl_exp/tasks/recipe_params.py`；`lizard_env_cfg.py` / `teacher_env_cfg.py` / `parkour_env_cfg.py` / `baseline_env_cfg.py` 各换成一行 wrapper；`test_params_isolation.py` 补 baseline 探针；`FILEMAP.md`。

### 收敛前的四份（实测差异，不是"看起来一样"）

| 线 | 缓存 | 允许读 dev yaml | 路径推导 |
|---|---|---|---|
| `lizard/main` | `_params_document` lru_cache + deepcopy | 是（`version=None`） | `_LINE_DIR/<v>/main_params.yaml` |
| teacher（同线） | 同上 | **否**（version 必填） | 同上 |
| `lizard/parkour` | 同上 | 是 | `_LINE_DIR/<dir.name>_params.yaml` |
| `lizard/baseline` | **无**（每次 `yaml.safe_load`） | 是 | 同上 |

⇒ 四份已经漂了：一份不缓存，一份不许读 dev yaml。收敛后**缓存/深拷贝/路径约定只有一处**，每线只留"我是哪条线 + 我是否 frozen-only"。

### 落地

| 项 | 内容 |
|---|---|
| 新模块 | `recipe_params.py`：`document(path, stamp)`（lru_cache(maxsize=64)）、`path(line_key, version)`（目录名即 basename）、`load(line_key, version, *, frozen_only)`（每次 deepcopy；`frozen_only` 且 `version is None` **抛错**） |
| 各线 wrapper | `return recipe_params.load(_LINE_KEY, version)`；teacher 传 `frozen_only=True`（保住"冻结配方永不读 dev yaml"） |
| 顺带修掉 | baseline 从"每调用重解析"升级为共享缓存（原先每个 cfg 构建都要多解析一次该文件） |
| 清理 | 四文件里变死的 `copy`/`functools`/`yaml` import 与 `_LINE_DIR`/`_PARAMS_NAME` 常量；`teacher_env_cfg.py` 里重复的 `from typing import ClassVar` 一并去掉 |

### 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` —— 换加载器后 36 个任务的 cfg 树逐字段不变（含 17 份 yaml 全部版本副本） |
| 隔离契约 | `test_params_isolation.py`（套件 `[34]`） | **通过**：`PARAMS_ISOLATION_OK`，**5 例**（teacher v14 / family v14 / parkour v1 / **baseline v1（新增）** / family dev yaml）——两次 load 非同一对象、污染不跨调用存活 |
| 组件单写者 | `test_component_ownership.py`（套件 `[37]`） | **通过**：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s))` |
| obs 契约 | `check_obs_layout.py`（套件 `[8]`） | **通过**：`OBS_LAYOUT_OK` |
| 接线 parity | `check_dr_parity.py`（套件 `[2]`） | **通过**：`PARITY_OK` |
| import 面 | `check_pxr_leak.py`（套件 `[14]`） | **通过**：`OK (task cfg import chain is pxr-clean)` |

### 边界

- **不是"全仓只剩一份"**：`rl_exp/archive/**` 与 `rl_exp/fork_patches/isaaclab_untracked/**` 里的 spider env cfg 各有自己的 `_load_params`——那是归档/未跟踪材料，属**留痕**，不迁不改。
- baseline 探针是**新增覆盖**：该线原来没有缓存也就无从"泄漏"，现在进了共享缓存，隔离必须被钉住。
- 单写者范围仍只到 `teacher_env_cfg.py`；四条线的 cfg 只共享加载器，互不共享配方。
- 本轮只跑六闸（门 1、隔离、单写者、obs、parity、pxr），未跑全量套件。

## B3 · 硬 A：构建器机制（首个声明式子集，2026-09-16）

**性质**：**追加**条目，B3（硬 A）的**机制先行**。新增 `rl_exp/tasks/recipe.py`（`RECIPES` / `ELEMENTS` / `build()` / `declared()` / `pending()`）与闸门 `check_recipe_build.py`（套件 `[41]`）。

### 机制（三条，缺一条就不是证明）

| 项 | 做法 |
|---|---|
| 期望值来源 | **冻结 lock** 从盘上读（写于构建器存在之前，不可能被它塑形）。构建器与自己比是恒等，这正是 §2.4 点名的第一号失败模式 |
| 被测对象 | `recipe.build(version)`，即**声明**，**不经版本类**（golden 闸门走类，本闸门走声明，两者互补） |
| 比较口径 | 复用 `check_cfg_lock` 的 `cfg_snapshot` + `walk_diff`：两套口径会让差异藏在缝里 |

### 一条被证伪的假设（省掉一步）

先前计划里的 **S1「把基类 body 抽成模块级函数」不需要**：`params_version` 实测是**字段**（1.0 已证），因此 `LizardRoughTeacherEnvCfg(params_version="v14")` 就已给出"共享接线 + 按该版本解析的结构组件"，无需版本类、也无需搬 250 行 body。⇒ 实际只需 S2（元素）+ S3（构建器 + 闸门）。

### 结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A（首个子集） | `check_recipe_build.py` | **通过**：`RECIPE_BUILD_OK (4 task(s) field-identical to the frozen golden)` —— `v1`/`v2` × train/play 四个任务，**声明构建**与冻结 golden 的 `snapshot.env` 逐字段一致；未声明的 10 个版本被**打印**（`not declared yet (not compared)`），不是静默跳过 |
| 门 1 | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))`（本批未改任何 cfg） |
| 套件形状 | `check_suite_shape.py` | **通过**：`SUITE_SHAPE_OK`（41 条，单列表、每检查一进程） |

### 边界

- **未声明 ≠ 通过**：v5–v14 的 delta 仍写在子类里，本闸门对它们**不比较也不宣称**。`RECIPE_BUILD_OK` 的准确含义是"已声明的那几条配方逐字段一致"（当前 v1–v4）。
- **PLAY 的 `ClassVar` 不进快照**（格式 2 已定）：`REQUIRES_CURRICULUM_STATE` 之类构建器造不出来也验不了 ⇒ 等 PLAY 元素化时补一条**类侧**断言（比类与构建器两条路径的 ClassVar 取值），本闸门现在看不见这一面。
- v5 起尚未迁移；两条路径（类 + 声明）在过渡期并存，漂移面由 `[24]` + `[41]` 双闸覆盖。
- **下一步（S2）**：v3 的 delta 元素化并逐条收口 —— 速度课程 / `r_fc`（`feet_air_time=None` + `foot_clearance`）/ `c_k`（`init_ck` 事件）/ reset DR 三件；随后 v4（一行 headroom）、v5（奖励包 + 行 SIR）、v12（鲁棒性包 + 环噪声事件）、v13（核替换）、v14（`head_load`），v11（joint SIR 接线、参数格地形与粒子命令已在组件侧）。

### 进度（逐版本，2026-09-16 当日）

| 版本 | 状态 | 元素 |
|---|---|---|
| v1 / v2 | **已声明** | 无 delta（`elements: ()`） |
| v3 | **已声明** | `v3_contact_headroom` · `v3_speed_curriculum` · `v3_anti_drag_reward` · `v3_ck_clock`；PLAY = `play_drops_speed_curriculum` · `play_pins_full_command_range` |
| v4 | **已声明** | v3 四项 + `v4_stock_contact_stack`；PLAY 同 v3 |
| v5 | **已声明** | v3 四项 + `v4_stock_contact_stack` + `v5_drops_speed_curriculum` · `v5_reward_package` · `v5_sir_terrain_curriculum`；PLAY = `play_drops_sir_terrain_curriculum`（见下节） |
| v6–v14 | **已声明** | v6 `v6_spine_unlock`；v8/v10 无 cfg 增量（同 v6 表）；v11 `v11_joint_sir_curriculum`；v12 `v12_reset_robustness`；v13 `v13_miki_kernel`（从 v10 分叉）；v14 `v14_head_load`（见下下节） |

实测：`RECIPE_BUILD_OK (8 task(s) field-identical to the frozen golden)`（提交 `3360642`）。**每加一个元素跑 `[24]` + `[41]`**。

### 接手点（下一个会话）

1. 读 `rl_exp/tasks/recipe.py`（元素 + `RECIPES` 表 + `build`）；读目标版本在 `teacher_env_cfg.py` 的子类 body 作为**搬运源**（逐行搬，不改语义）。
2. 加元素函数（`_doc(cfg)` 取该配方的参数文档），在 `RECIPES["v<版本>"]` 填 `elements` / `play_elements` / `train` / `play` 任务 id。
3. `build()` 已支持 `play_elements`（共享 PLAY 接线**之后**施加）。
4. `[41]` 会打印未声明版本 —— **不许**用"半套元素 + 声明成已迁移"骗绿：未声明的必须留 `None`。
5. 全绿后按仓库惯例提交（pre-commit 三闸会自动跑）。
6. **未合口**：`components.observations` 仍带三张手抄表（`PROPRIO_TERMS`/`BASELINE_PRIV_TERMS`/`SPEC_TERMS`），而 `tasks/obs_protocol.py` + `versions/obs_protocols.json` 已声明同一身份（按 task 带 `version`/`line`/`groups`/`terms`/`dropped_terms`）。现由 `check_obs_protocol` 互钉；合口 = 组件只留构造、按 (line, version) 读声明，删掉三张表。**是否合、何时合由用户定**（声明面属并行批次）。

## B3 · v5 元素化（奖励包 + 行 SIR 课程，2026-09-16）

**性质**：**追加**条目，B3 的第二个声明式子集。改动面 = `rl_exp/tasks/recipe.py`（4 个元素 + `RECIPES["v5"]`）、`check_recipe_build.py`（新增"声明路径带不走的 ClassVar"打印）；`teacher_env_cfg.py` 的 V5/V5_PLAY 子类**不动**（过渡期两条路径并存，漂移面由 `[24]` + `[41]` 双闸覆盖）。

### 落地

| 元素 | 内容 |
|---|---|
| `v5_drops_speed_curriculum` | `curriculum.speed_curriculum = None` |
| `v5_reward_package` | EP 核 → `track_lin_vel_xy_lin`（yaml `v5.track_goal_vel`）；`feet_slide` = `feet_slide_ck`；`undesired_contacts.func` = `undesired_contacts_ck`；`belly_contact_force`（yaml `v5.r_slip` / `v5.belly_contact_force`） |
| `v5_sir_terrain_curriculum` | `curriculum.terrain_levels` = `SIRTerrainCurriculumCfg`，8 参数全读 yaml `v5.terrain_curriculum` |
| `play_drops_sir_terrain_curriculum` | PLAY 侧 `terrain_levels = None` |

三处**不是搬运、是判断**（写下来，省得下次重新推）：

- **r_fc 符号修正不需要元素**：`v3_anti_drag_reward` 走 `_doc(cfg)` 按**本配方**的 yaml 读 `v3.r_fc`，v5 的 yaml 副本里就是 `-0.003`。迁移前它靠"V3 在 `params_version='v5'` 时执行"生效，迁移后靠"元素读该版本的文档"生效 —— 同一件事，少一个元素。
- **`v5_drops_speed_curriculum` 必须留，且必须排在 v3 元素之后**：`v3_speed_curriculum` 也在这份元素表里。删掉"装"只留"缺"看着更省，但 `speed_curriculum` 是**靠赋值才存在**的属性：省掉它，快照里就是"缺席"，而冻结配方记的是 `null`（1.1 明写 missing ≠ None），`[41]` 会当场红。**逐行照搬类链，语义才等价**。
- **v3/v4 的 PLAY 元素不进 v5**：`play_drops_speed_curriculum` 会去删一个 v5 本就没有的课程（无害但说谎），`play_pins_full_command_range` 会把范围钉成 `(-1, 5)`，而冻结的 v5 PLAY 是 yaml 的 `(0, 3)`——两者都会让 `[41]` 红。这是"元素表按配方写、不按版本链继承"的直接好处。

### 结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (10 task(s) field-identical to the frozen golden)` —— v5 train/play 加入后仍逐字段一致；未声明的 7 个版本继续被打印 |
| 门 1 | `check_cfg_lock.py`（套件 `[24]`） | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))`（本批未改任何 cfg） |
| 单写者 | `test_component_ownership.py`（套件 `[37]`） | **通过**：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s))` |
| golden 摘要 | `check_golden_frozen.py`（套件 `[35]`） | **通过**：`GOLDEN_FROZEN_OK`（3 份基线文件自 `020e6fb` 未动） |
| 旁证五闸 | `check_obs_layout` · `check_dr_parity` · `check_reward_v13` · `check_configclass_fields` · `check_suite_shape` | **全绿**（v5 obs 381 与冻结一致；v5/v10 的 EP 核冻结断言未动；`test_v5_rewards` 4 例 + `test_v5_terrain_sir` 9 例全过） |

### 新增的可见缺口：声明路径带不走的 ClassVar

`[41]` 现在**每次运行都打印**（不是判红）：

```
classvar the declaration cannot carry (no class to hold it): v3/play PLAY_PINS_COMMAND_RANGE: True != False
classvar the declaration cannot carry (no class to hold it): v4/play PLAY_PINS_COMMAND_RANGE: True != False
classvar the declaration cannot carry (no class to hold it): v5/train REQUIRES_CURRICULUM_STATE: True != 'not stated'
classvar the declaration cannot carry (no class to hold it): v5/play REQUIRES_CURRICULUM_STATE: False != 'not stated'
```

（以上是本条提交当时的原样输出。v6–v14 声明完后同样的行变成 18 行、措辞也改短，遂按**缺口类**聚合——下一节记的是新格式。）

这是 `[41]` 原有纪律（"未声明 ≠ 通过"要打印）扩到 ClassVar 面：`build()` 返回**共享基类**实例，而 `ClassVar` 是"关于配方的声明"，快照格式 2 把它排除 ⇒ 声明路径**结构上**没有地方承载它。两个名字的后果不同：

- `PLAY_PINS_COMMAND_RANGE` 是**构造期**读取（基类 `__post_init__` 用它选范围），声明路径复现的是**效果**而非声明（`play_pins_full_command_range` 事后写同一个范围），字段面已等价 —— 打印出来是留痕，不是缺口。
- `REQUIRES_CURRICULUM_STATE` 是**运行期**读取（`curriculum_state.requires_resume_state` 与 `runrecord.manifest` 都走 `getattr(type(cfg), ...)`），声明路径给不出 `True`，字段面也补不回来。**这是真缺口**。当前被 `need = requires_resume_state(env) or bool(covered)` 兜住（行 SIR 是注册 term，`covered` 非空 ⇒ 缺载荷 / 缺 slot 时**仍然硬失败**），退化的只有三处：声明语义本身、"声明了却没收集到状态"那条 save 守卫、以及 manifest 里那条记录。**修法在读取侧**（读实例，或按 `(line, version)` 读声明表），落在并行侧 C 的 lane。本次按用户拍板（2026-09-16）**先让它可见，不假装已修**；B3 原计划里"等 PLAY 元素化时补一条类侧断言（比两条路径的 ClassVar 取值）"由此落地为**打印**形态。

### 边界

- `RECIPES["v5"]` 的 train/play 任务 id 是**写出来的**，不从版本串推 —— 改名不能静默把这个闸门指向空。
- **`recipe.py` 仍不在 `[37]` 的 HOSTS 里**：元素会写 `commands.base_velocity`（`components` 拥有的名字），`play_pins_full_command_range` 就是这么写的。把它加进扫描表会立刻红 —— 元素是独立于 `teacher_env_cfg.py` 的第二类合法写者，要不要扩 `[37]` 的范围，得先定义"元素豁免"的形状，本轮不动。
- **`FILEMAP.md` 只补 `[41]` 新打印的那一句**：落笔时它正带着并行侧 obs_protocol 的在飞改动（连同 `runrecord/manifest.py`），整份 `git add` 会把别人的半成品写进我的提交；那批他们随后自行提交（`38d80a6` / `a7e2b27` / `9afc9b8`），补记随之落在一个小提交里。v5 的**元素清单是状态**（上面进度表），代码地图只描述机制，不抄第二份。
- **未合口（本轮定：不合；2026-09-17 追记：用户已定"要合"，条件已满足）**：`components.observations` 的三张手抄表 vs `versions/obs_protocols.json`。理由：`obs_protocol` 自称"只声明 identity、不构建 config"，而 `check_obs_protocol` 是拿声明去比**构造出来的** cfg；让 `components.observations` 反过来读它，闸门就变成声明比声明 —— B3 点名的第一号失败模式（与自己比恒等）。且声明侧仍在飞。**追记**：声明侧已落定（`38d80a6` 的 3.1d + `9afc9b8`），"等他们 3.1d 落定后再议"这一条件已满足；合口的身份问题与代价见 §3.1 第 11 条（**不需要新加身份参数**；代价是 `--live` 退化为转换一致性检查、3.1e 变承重）。落地须在 builder 改动静下来之后、一次落。
- 仍未声明：v6 · v8 · v10 · v11 joint SIR 接线 · v12 鲁棒性包 + 环噪声事件 · v13 核替换 · v14 `head_load`，各自还需 PLAY 元素。**每加一个元素跑 `[24]` + `[41]`**。

---

## 3.1 · obs 协议声明与双源闸门（离线，2026-09-16）

### 前提与范围

依 `ARCH_PLAN.md` v0.21「Step 3 施工件表」。本片**只做离线段**：几何一致性、导出校验、蒸馏不在内（记未执行）。全程不碰并行批次的写点，提交按路径限定。

### 落地（件号 → 产物 → 提交）

| 件 | 产物 | 提交 |
|---|---|---|
| 3.1a | `versions/obs_protocols.json`：36 任务 → 11 协议身份，**key = 自身 `groups` 摘要前 12 位** | `6742a64` |
| 3.1a′ | `versions/lizard/obs_protocol_anchors.json`：已审 `digest`/`label`/`dims`/`purpose`，闸门只读不写 | `6742a64`、`5d4cb38` |
| 3.1a 读者 | `tasks/obs_protocol.py`（纯 stdlib；脚序由 extero 项名派生） | `6742a64` |
| 3.1b | `tools/verify/check_obs_protocol.py` + `test_obs_protocol_gate.py`（20 例反证） | `f20a568` |
| 3.1c | `check_obs_layout.py`／`test_cfg_snapshot.py`／`teacher_smoke_runner.py`／`teacher_smoke.py`／`parkour_smoke.py` 改读声明 | `6ccfe2f`、`5d4cb38` |
| 3.1d | `manifest.py::recipe_ref` 记协议身份 + 已审摘要 + 宽度（与实构 `obs_layout_digest` 分开命名） | `38d80a6` |
| 3.1f（离线半） | `test_teacher_networks.py` 脚序标记输入 | `be89bc5` |
| 3.1g | clip/scale/噪声**数值**入声明（非"有无"） | `6742a64` |
| 3.1h | `OBS.md` 补 v13/v14/v15 行与真源注记 | `53c0d42` |
| 套件挂载 | `[42]/[43]`（离线半区；`--live` 归真跑窗口） | `a7e2b27` |

### 检查与结果（本机实跑）

```
check_obs_protocol.py             11 protocols | 36 tasks | golden 36 | live 0   → 与 golden 一致
check_obs_protocol.py --live      golden 36 | live 36                          → 两来源一致
test_obs_protocol_gate.py         OBS_PROTOCOL_GATE_OK（20/20）
check_obs_layout.py               OBS_LAYOUT_OK（顺序/脚序来自声明）
test_cfg_snapshot.py              CFG_SNAPSHOT_OK（脚序来自声明）
pytest test_teacher_networks.py   8 passed
test_run_manifest.py              RUN_MANIFEST_TEST_OK
check_suite_shape.py              SUITE_SHAPE_OK（改套件后）
```

**关键反证（每条都真红）**：交换两个 term（报 `same members, different order`）／交换两个组（报组序）／翻转 `enable_corruption`／`dropped_terms` 加一项／未审锚点／key 与内容脱钩／golden↔声明双向覆盖缺失／`--only` 过滤不掩盖范围内问题。

**3.1f 的能力证明**：把 `teacher_networks` 的 reshape 临时改成 point-major，测试报
`AssertionError: marking foot 0 (lf) moved latent segments [0, 1, 2, 3]`（1 failed）；改回后 8 passed，且该文件 `git diff` 为空。这正是"维度全对、语义全错"的错法。

**已装事实**（声明不再是 stand-in）：v14 teacher cfg 实测 `obs_protocol=6cd53ec273dc`、`obs_protocol_dims={proprio:90, extero:208, priv:83}`，与本次会话实构的 `obs_layout_digest` 并列记录。

### 本片修正（均由反证或实测抓到）

1. **"有无"不是事实**：首版把噪声/clip 记成存在性，"改一个 sigma"仍为真 ⇒ 改为记**值**（11 个 key 全变，锚点重批）。
2. **重批必须先自证是表示变化**：重批锚点前对新旧声明做结构对比（`tasks 36/36，structural drift: none`），确认无 term/顺序/dropped/flag 变化，才写新摘要；理由写进锚点注记。
3. **未测宽度必须抛错**：`dims_for` 对未批协议直接 `ProtocolError`。写 parkour 时当场被拦（PLAY 身份单独成身份、未批宽度），而非给出 0 或默默跳过。
4. **无向声明补造入口**：v7/v9/v15 目录存在但无注册入口，闸门按"有历史目录、无注册入口"登记，缺号不补造。
5. **套件提交不卷走并行批次**：工作树含他人的在飞重写 ⇒ 只提交索引（`hash-object -w` + `update-index --cacheinfo`），实测 `1 file changed, 3 insertions(+)`，其重写保持未暂存。
6. **宽度原先没有任何完整性保护**（自查）：协议 `digest` 只覆盖 `groups`，而 `dims` 存在锚点里 ⇒ 原地改一个宽度既不红也无人断言（smoke 只在真跑时读它）。现宽度由 `dims_digest` 自钉，并加结构性规则（组名必须真实存在且 live、值为正整数、同一协议**要么全填要么全空**）；补 6 例反证：原地改宽度、缺 `dims_digest`、未知组名、`True` 当宽度、半填、以及"是否存在多组协议可供该规则测试"的存在性检查（否则规则会静默不被测）。
7. **假红地雷**（自查）：`check_obs_layout` 的 v3/v4/v5 段原共用一份从 **v12** 取的顺序常量 ⇒ 只改 v12 的布局会误红 v3/v4/v5，而该文件在 pre-commit 里。实测证据：`v12-only change: constant still == v3 terms → False`，而 `v3 own declaration unchanged → True`。现各段按自己的 task id 取（v3/v4/v5/v12 各一份），脚序也改为 `feet_for` 派生。

### 边界（**不得**据本节宣称）

- **真 env 未跑**：3.1e（实际 manager 的逐 term 维度、最终张量维度、实际 joint/body 名与索引序）与 3.1f 真跑半、以及 `--live` 入套件 —— 全部**未知**。
- **v0 家族（flat/rough/curriculum）宽度为空**：无真跑量过，无人断言。
- **声明不参与 cfg 构造**（与并行批次写点隔离的取舍）：装配事实仍在代码，`components.observations` 的三张表与声明是同一身份的两处，现由 `[8]` + `[42]` 互钉。**用户已定"要合"**，合口的身份与代价见第 11 条（不需要新加身份参数；合口后 `--live` 退化为"声明 → 配置"的转换一致性检查，3.1e 变承重）—— 落地须在 B 的 builder 改动静下来之后、且一次落。
- 几何一致性、导出前协议校验、蒸馏数据 manifest = **未执行**。
- `OBS.md` 的 v15 行只声明"有目录、无入口"，不声明其布局。
- 本节为**离线段**通过，**不得**称为"Step 3 全部通过"。

### 结构性风险处置（review 后，2026-09-16）

评审列出三条结构性风险，当场修两条、第三条记敞口：

8. **锚点路径写死家族名**（已修，`415a8bf`）：声明是**全仓**的（闸门 glob 所有线的 golden），锚点却放在 `versions/lizard/` 下 ⇒ 第二个机器人家族落地时要么改代码、要么把别家的协议塞进蜥蜴目录。现移到 `versions/obs_protocol_anchors.json`，与它钉的文件同层，也与 `recipes.json`/`lines.json`/`cfg_baselines.json` 一致（"钉与被钉同层"）。重生成声明只动了 note 一行，**key 与全部已审摘要不变**，两半区仍 36/36。
9. **退役：前版结论越界，现按端到端反证重写**（首版 `ef47d0c`；完整反证与读者修复随本节同批提交）：上一版只证明了"声明里没有该任务时聚合门不崩"，却写成"退役已验证"—— **证据越界**。真正的退役形状是：保留历史声明与锚点 + `lines.json` 标 retired + 撤掉注册 + live 配置不可用。
   **完整反证（跑真实聚合入口，非注入答案）**：`lines.json` 把 `lizard/main` 标 retired、注册表去掉 `Lizard-Rough-v3` 与 `-Play-v3`、从 `teacher_env_cfg` 删除 `LizardRoughTeacherEnvCfg_V3`，然后：
```
aggregate layout gate   exit 1   SEGMENTS_OBSOLETE: ['LizardRoughTeacherEnvCfg_V3']
                                 "a deleted recipe class means the segment covering it must be
                                  removed or re-pointed; no segment was run, so nothing here
                                  has been checked"
protocol gate（离线半）  exit 0   golden 36 | live 0
protocol gate（--live）  exit 0   golden 36 | live 34（退役的两个任务按历史留存、不再构造）
声明与锚点              退役任务仍在册；其协议仍有已审摘要
```
   为此聚合门改两处：类名导入改 `_resolve`（删类不再拖垮整个模块的导入），并加 `SEGMENTS_OBSOLETE` 前置 —— **具名拒绝**而非 traceback，且明说"什么都没检查"（不许把未跑的段当成通过）。
   **反证当场抓到的真缺陷**：`retired_lines()` 的 `path` 原是**默认参数**，导入时绑定 `LINES`，补丁对它无效 ⇒ `--live` 仍红。根因是单测**直接注入** `retired` 集合、从没走过读者。已改为调用时解析，并补两例直接喂临时 `lines.json` 的反证（读者读索引、读者驱动覆盖规则）。
   **仍未覆盖（不得据此宣称）**：退役后**要不要删掉该段的代码**是维护动作，闸门只能具名提醒、无法验证；本反证也无法模拟"段代码已删"的状态。单配方 smoke 与网络单测仍依赖其配方存在 —— 那对它们是依赖，不是缺陷。
10. **"生成 + 人工审批"仍是社会控制**（敞口，未修）：闸门能查的全是**自洽**（key=内容摘要、digest=锚点、dims=dims_digest），三件事同一条命令都算得出来 ⇒ 重新生成 + 重批可以不留"有人看过"的痕迹。既有先例是 golden 的 `--update --reason`。
   **判据更正（评审）**：`approved_rev` 只能提供**追溯**，不能证明审核发生。更稳的判据是**"审批绑定的内容摘要是否仍等于当前受审内容"**（相等即未被改写）；`rev` 用来定位来源，`purpose` 用来解释改动原因。仅凭"HEAD 已前进 + golden 有变动"发警告会混入无关变化，也可能漏掉审批范围之外的实际影响。故将来动作 = 锚点记 `approved_rev`（追溯）+ `purpose` 必填（原因），**硬红判据仍是摘要相等**。
11. **合口的身份问题：先查再断**（评审纠正上一版的越界结论）：上一版断言"必须新增身份参数"，依据是 TRAIN/PLAY 是两个身份、v0 家族 `version` 全为 `null`。查过后这两条都**不足以**推出该结论：
    - `components.observations` 只有**一个**调用点（`teacher_env_cfg.py:730`，传 `params_version`），**v0 家族根本不走它**（走 `lizard_env_cfg`/`rough_env_cfg`/`curriculum_*`）⇒ `version=null` 与组件寻址无关；
    - v1/v2 的 TRAIN/PLAY 差异（corruption/噪声）由**其后的 play 接线**施加（`play_utils`），不在组件里 ⇒ 组件按 `params_version` 寻址时两者形状相同，只有在**协议身份**层面才分家。
    ⇒ 合口**不需要**新造身份参数；需要的是把既有的"版本 → 该版本 TRAIN 侧布局"映射讲清（声明有 `tasks[t]["version"]`，`recipes.json` 有 `legacy_task_version`），并保证 **play 接线仍是唯一施加 PLAY 噪声/corruption 的地方**（否则"版本 → 布局"不再良定义）。
    措辞更正：合口后 `--live` 不是"自己比自己"，准确说是**退化为"声明 → 配置"的转换一致性检查**，不再提供独立正确性证据；届时唯一独立来源是冻结 golden，**3.1e 真 env 变为承重**。
### 3.1e 真跑：live obs 契约（2026-09-17，**部分完成**）

命令（本机实跑，headless）：
```
python rl_exp/tools/verify/obs_protocol_live.py --headless \
  --tasks Lizard-Rough-v14 Lizard-Rough-Play-v14 Lizard-Parkour-Climb-v1 Lizard-Velocity-Flat-v0
```
结果：`OBS_PROTOCOL_LIVE_FAILED (1 problem(s), 3 warning(s))`

**通过的部分**（读的是 live manager，不是构造物）：
```
v14 TRAIN / PLAY   proprio=90 extero=208 priv=83，组序与逐 term 序与声明一致，张量 (2, width) 一致，4 只脚的 <foot>_foot body 都在
Velocity-Flat-v0   policy=90（宽度**未批**，按未批标记，不冒充通过）
```
**发现 1（WARN，判据未定）**：live articulation 的关节**序列**与配方文档的 `joint_order` 不同（同一 26 个关节）：
```
live     chest_yaw, tail1_yaw, rr_haa, rl_haa, chest_pitch, tail1_pitch, rr_hfe, rl_hfe, …
declared chest_yaw, chest_pitch, neck_yaw, neck_pitch, rf_haa, rf_hfe, rf_kfe, rf_foot, lf_haa, …
```
训练侧 obs/action 走的是 **live articulation 序**；文档里的 `joint_order` 是 **URDF 树序**（`export_ue.py` 拿它比对 URDF，且它进 `ue/lizard_ue.json`）。既有闸门只把文档与 usda 关节的**集合**比对（`check_dr_parity.py:277` 用 `set(...)`），**没人比过顺序**。故：要么文档顺序只是部署侧约定（则须写明 UE 按名装配，且把 live 序钉成训练契约），要么两者本应相等（则是部署契约的真错）。**判据待用户定，本轮不判通过也不判失败**。

**发现 2（FAIL，非本批文件）**：`Lizard-Parkour-Climb-v1`（`lines.json` 里 `status: active`）**根本构造不出 env**：
```
ValueError: Not all regular expressions are matched!
  rear_.*: []   tail_.*: []        （.*_haa_joint / .*_foot_joint / neck.*_.* 均有匹配）
```
原因：`versions/lizard/parkour/v1/parkour_params.yaml` 的 `actuators.spine.joint_patterns`（:46-47）与 `default_joint_pos`（:21-22）仍用 **v8 之前的命名** `rear_.*` / `tail_.*`，而当前资产已改名 `tail1_yaw` 等 ⇒ 该 actuator 组没有任何关节，IsaacLab 直接抛错。**这与 Step 3 无关**，但它是真跑的产物：**离线闸门全绿，而一个 active 线的任务连 env 都建不起来**（`parkour_smoke.py` 能抓，但它不在套件里、需手跑）。

**边界（不得据本节宣称）**：
- 3.1e **未通过**：只跑了 4 个任务；parkour 因构造不出 env 已退役（见下）；joint 序判据已定为"live == 已钉实测序"（见下）；v0 家族宽度仍无人量过。
- 只跑了 4 个任务，**不代表其余 32 个**；一次真跑不覆盖其他协议。
- 本节证据只到"live manager 与声明一致 + 上述差异"，不含推理等价。

**发现 2 的处置（用户拍板 2026-09-17）**：**parkour 标记退役**（`versions/lines.json` → `revision: 3`）：`status: retired` + `retired_at: 2026-09-17` + 原因（v8 改名后 `joint_patterns`/`default_joint_pos` 失配，无法构造 env）+ `successor: null`。
复核（本机实跑，全绿）：`check_recipe_registry` `lifecycle consistent`（`revision=3 entries=3`）· `test_lifecycle_gate` `LIFECYCLE_STARTUP_OK`（退休线拒绝新训练：`refused to start: retired line: refusing new_train`）· `test_launcher` `LAUNCHER_OK` · `check_recipe_map --bind-config` 36/36 · `check_cfg_lock` `CFG_LOCK_OK (36 tasks, 3 line(s))` · `check_obs_protocol --live` 36/36 · `check_obs_layout` `OBS_LAYOUT_OK`。
**边界**：退役是**权限事实，不删内容** —— parkour 的任务仍在注册表、golden 与冻结目录保留（"已发布内容不改写"）。要连注册一起撤掉是另一次动作，本轮**未做**，也不影响上述通过项。
**发现 1 的处置（用户拍板 A，2026-09-17）**：**钉住运行序**，判据改成"不该断言 live == 配方文档"。
- **落点**：新文件 `versions/lizard/joint_order_runtime.json`，**按资产键**（`assets["assets/lizard/lizard.usda"]`），记实测关节序 + 测量任务 + 日期 + 理由。写它只能由 `obs_protocol_live.py --pin --reason '<why>'`（刻意行为，不是刷新）；读它只有 `rl_exp.tasks.obs_protocol` 一处（`runtime_joint_order` / `joint_order_digest`），避免检查与写入各读一份。
- **判据**：live 序 == **已钉实测序** ⇒ 硬红（不等就 FAIL 并列出两个序列）。**配方 `joint_order` 与它不等只出 WARN** —— 两者服务不同事（URDF/部署序 vs 训练 I/O 序），相等是巧合不是义务，断相等会逼人改坏部署契约。
- **覆盖**：`--all-tasks` 只读文件、不起 sim，实测 `OBS_PROTOCOL_LIVE_OK (36 declared task(s), all pinned)`（36 个声明任务全部落在同一资产上，故一处实测覆盖全部）。
- **run 记录**：`manifest.recipe_ref` 增 `runtime_joint_order_digest`（v14 实测 `416640b4d16af072…`）⇒ ckpt 可追到"它在哪个关节序下训练"。
- **反证（本机实跑）**：把钉住值里 `chest_yaw` 与 `tail1_yaw` 互换 ⇒
```
FAIL Lizard-Rough-v14: live joint order differs from the measured one for 'assets/lizard/lizard.usda'
OBS_PROTOCOL_LIVE_FAILED (1 problem(s), 1 warning(s))
```
　换回后 `OBS_PROTOCOL_LIVE_OK`。即：钉住值是承重的，不是装饰。
- **导出侧已闭合（2026-09-17）**：`lizard_ue.json` 现在同时带**两种序**并写明用途 —— `joint_order`（URDF 树序，保留 + `joint_order_note` 标注它不是装配序）与 `joint_order_runtime`（实测运行序）+ `joint_order_runtime_digest`，`meta.obs_assembly` 写明"装配必须按关节**名**，或用 `joint_order_runtime`"。**导出器没有实测序就拒绝导出**（不写任何文件）：实测 `exit code 1` + `ValueError: no measured runtime joint order for 'assets/lizard/lizard.usda'`，且导出产物逐字节未动。
  导出器**不 import** `rl_exp.tasks`（它在部署机上跑，不该拖进训练栈），因此它是直读数据文件的第二处读取 —— 这一处重复由闸门机器核对：`check_obs_protocol` 增 `check_export_agreement`，比对导出产物与实测序及其摘要（4 例反证：序过期、摘要过期、缺 `meta.asset`、干净）。

## B3 · v6–v14 元素化（剩余九条配方，B3 收口，2026-09-16）

**性质**：**追加**条目，B3 收口。改动面 = `recipe.py`（5 个元素 + delta 常量链 + 一个 `mdp` import）、`check_recipe_build.py`（ClassVar 缺口按类聚合）；`teacher_env_cfg.py` 一字未动。

### 落地

| 版本 | 新增元素 | cfg 增量是什么 |
|---|---|---|
| v6 | `v6_spine_unlock` | 1 行：`action.spine_scale`（本版本 yaml 0.25；v1–v5 仍 0.0，因为值来自各自文档） |
| v8 | — | **0 行**：+180° 翻转与 26 关节改名在资产面，yaml 的名字迁移由基类按**本版本**文档读 |
| v10 | — | **0 行**：tilt 删除是 yaml 标志（`v10.tilt_terminate: null`），`components.terminations` 早已是唯一写者 |
| v11 | `v11_joint_sir_curriculum` | 行 SIR → 联合粒子（`JOINT_SIR_TERM`）；参数格地形与粒子命令 term 在 `components.TERRAIN_BY_RECIPE` / `COMMAND_RANGE` |
| v12 | `v12_reset_robustness` | 三个 `reset_joints_by_offset` + base 复位范围 yaml 化 + 摩擦 dip + 环噪声事件（extero 四项的 func/参数归 `components.observations`） |
| v13 | `v13_miki_kernel` | 线性核 → Miki 对称核 |
| v14 | `v14_head_load` | 头承力罚（`roll_over` 终止归 `components.terminations`） |

PLAY：v5–v10 与 v13/v14 用 `play_drops_sir_terrain_curriculum`；v11/v12 换成 `play_drops_joint_sir_curriculum`。

### 三个判断

- **delta 写成链，v13 从 v10 分叉**：`_V3_DELTA → _V4 → _V5 → _V6`，v11/v12 接 `_V6`，**v13 也接 `_V6`**（V13 的基类是 V10，不是 V12）——元素表按**类链**写，不按版本号顺序。每个 delta 只写一次：v8/v10"与 v6 同"是一个对象的事实，不是三份副本要对齐。
- **v8/v10 的空增量用 v6 的表，不是 `None`**：声明的是"除了 v6 的 delta 没有别的"，不是"未声明"。`None` 留给真正没搬的版本——现在一个都没有。
- **PLAY 守卫必须跟课程换名**：v11/v12 的课程是联合项，照抄 v3 那对 PLAY 元素会去 null 一个不存在的 `terrain_levels`（无害），却**留下**联合项在跑（有害：评估会按 episode 重派起点与速度）。冻结的 v11/v12 PLAY 只 null 联合项、把粒子命令 term 留着让它自己回退到均匀范围 —— 元素照此。

### 结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A（全部配方） | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (24 task(s) field-identical to the frozen golden)` —— 12 条配方 × train/play 全部**声明构建**与冻结 golden 逐字段一致；`pending()` 已空，输出里不再有 `not declared yet` 行 |
| 门 1 | `check_cfg_lock.py`（套件 `[24]`） | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))`（本批未改任何 cfg） |
| 单写者 | `test_component_ownership.py`（套件 `[37]`） | **通过**：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s))` |
| golden 摘要 | `check_golden_frozen.py`（套件 `[35]`） | **通过**：`GOLDEN_FROZEN_OK`（3 份基线文件自 `020e6fb` 未动） |
| 旁证 | `check_obs_layout` `[8]` · `check_dr_parity` `[2]` · `check_pxr_leak` `[14]` · `check_reward_v13` · `check_terminations_v10` · `check_terminations_v14` · `check_suite_shape` · `test_joint_sir`（12 例）· `test_v12_noise` | **全绿**（v10/v13/v14 的冻结断言未动 —— 因为版本类一字未改） |

### ClassVar 缺口打印改为按类聚合

```
classvar the declaration cannot carry: PLAY_PINS_COMMAND_RANGE: True != False -- in v3/play, v4/play
classvar the declaration cannot carry: REQUIRES_CURRICULUM_STATE: True != 'not stated' -- in v5/train, v6/train, v8/train, ...
classvar the declaration cannot carry: REQUIRES_CURRICULUM_STATE: False != 'not stated' -- in v5/play, v6/play, v8/play, ...
```

缺口性质与修法不变（见上节）。改的只是可读性：每条配方一行会变成 18 行同文，而"每次跑都刷屏的同文"恰好会被当成噪音跳过，聚合后 3 行，仍然每次跑都出现。

### 边界

- **24/24 已声明，`[41]` 仍保留 `not declared yet` 那条打印**：下一条新配方（v15+）填进 `RECIPES` 而没写元素时，是被打印，不是静默通过。闸门不因"当前全绿"而收掉这条纪律。
- `recipe.py` 新增 `isaaclab_tasks...velocity.mdp` import（v12 的 `reset_joints_by_offset` 用）。`[14]` 复跑仍 pxr-clean：与 `teacher_env_cfg.py` 同一模块，没有新增链路。
- `recipe.py` 仍不在 `[37]` 的 HOSTS 里（理由见上节边界）。
- **ClassVar 真缺口未修，且现在覆盖 v5–v14 全部 18 个任务**：读取侧一改，18 个任务一起受益、也一起被验。**C2/C3 的 launcher 把 `build()` 变成默认训练路径之前必须落**，否则这批配方的续训声明对 manifest 与 save 守卫是隐形的（安全性仍由 `covered` 项兜住，见上节）。
- obs 三表合口本轮仍未动（上节已定）。
- 本节只证"声明与冻结 golden 逐字段一致"；**不证**元素在真环境下的行为等价（那是 C 层真跑的事），也不证 PLAY 的 `ClassVar` 面（见上节缺口）。

## B3 收尾 · `[41]` 的三条纪律（覆盖钉数 / 缺口台账 / 逐步归属，2026-09-17）

**性质**：**追加**条目。改动面 = `recipe.py`（新增 `base_cfg(version)`；`build()` 增可选 `trace=`，按序记下每一步 `(name, callable)`，让读者**回放**而不是复述顺序 —— 复述顺序就是下一个漂移面）、`check_recipe_build.py`（三条判据 + 缺口按 ClassVar **名**入账）、`FILEMAP.md`。**不动任何配方的字段内容**（24/24 仍逐字段一致）。

### 动了什么（都是"闸门自己的牙"，不改语义）

| 判据 | 之前 | 现在 |
|---|---|---|
| 覆盖钉数 | `compared` 只出现在结尾那句 OK 里，比较集缩小 = 更短的绿 | `EXPECTED_COMPARED = 24` + `EXPECTED_PENDING = ()` 双向钉住：声明被撤（比较集变小）或新配方未声明就进表（pending 变多）都红 |
| 缺口台账 | 缺口**每次打印**，永不见红；到期条件只写在散文里 | `EXPECTED_GAPS`：按 ClassVar 名给「理由 + 到期」；**台账外的新缺口即红**（一年后没人会逐条读打印），**台账里已消失的项也红**（陈旧项会盖住下一条） |
| 逐步归属 | 无：空转元素在字段比对上**完全隐形**（字段全等 ⇒ 零差异） | 回放 `trace`：每个声明元素**必须改到至少一个字段**；且该版与基线的**全部差异必须有人认领**（"没人改却变了" = 映射不是全部事实） |

### 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A（全部配方） | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (24 task(s) field-identical to the frozen golden)`，单跑 8.7 s（预算 25 s）；两条台账条目按名字打印，附「why / due」 |
| 逐步归属反证 ①（空元素） | 进程内塞 `ELEMENTS['_noop'] = lambda cfg: None` 并挂进 v14 元素表 | **FIRED**：`element '_noop' changes nothing` |
| 逐步归属反证 ②（无主字段） | 包一层 `build()`，在返回值上多写一个字段（`seed`） | **FIRED**：`1 field(s) changed with no declared element behind them: ['seed']` |
| 覆盖钉数反证 | 把任一版本 `elements=None`（或从 `RECIPES` 撤一条） | 由构造保证：`compared` 变 23 ≠ 24 **且** `pending` 非空 ⇒ 两条独立红 |
| 旁证 | 全量套件 `offline_suite.py` | **43/43 通过**（wave 188 s / 预算 400 s） |

### 边界（写清楚，别把绿读成更多）

- **归属 ≠ 行为等价**：它证的是"声明的每一步确实动了它该动的字段、且没有无主差异"，**不证**这些字段在真环境里产生同一行为（C 层真跑的事）。
- **`REQUIRES_CURRICULUM_STATE` 这条真缺口未修**：本轮只是给它上了台账与到期条件（"`build()` 变成默认训练路径之前"）。读取侧的修法（载体决定 + 拆 `declared()`/`needs_restore()` + 启动时校验"声明 True ⇔ 接线非空"）仍在他们那侧，属**行为面**；本节不主张已修。
- **save 守卫的合取今天不可达，所以没动**：只有一处类声明 True（`teacher_env_cfg.py:1083`），而所有清空课程项的元素都是 `play_drops_*`（PLAY 侧，且 PLAY 类显式声明 False）⇒ `(声明 True ∧ 接线空)` 现不存在。**注意**：删掉那个合取是**反向风险**（声明 True 却无 term 的配置会改成"训练几小时后 save 时才炸"），必须与"启动时校验"一起做，不能单删。
- 归属判据只覆盖 `train`/`play` 两条已声明路径；元素**执行顺序**由 `trace` 给出（不再由检查器复述），所以将来 `build()` 改序，判据跟着走而不是失效。
- 本轮不新增套件条目：三条判据都落在既有 `[41]` 内，不付第二份 import 税。

## B2/B4 · baseline 线接入构建器 + 硬 B 差异清单（2026-09-17）

**性质**：**追加**条目，`ARCH_PLAN.md` §2.4 的 B2（首个新架构配方）与 B4（硬 B）。改动面 = `recipe.py`（按线分表 + `build(…, line=)` + 10 个 baseline 元素 + `pins`）、`baseline_env_cfg.py`（拆出空的共享接线基类）、`check_recipe_build.py`（按线迭代 + 硬 B）、新增 `versions/lizard/baseline/v1/diff.json`。`ARCH_PLAN:251` 说"新架构承接新的实验线"——baseline 线就是那条新线。

### 落地

| 件 | 内容 |
|---|---|
| 首个新架构配方 | `Lizard-Baseline-Flat-v1`(+Play) 可由 `recipe.build("v1", line="lizard/baseline")` 产出：10 个元素（robot · actions · flat ground · proprio obs · timing · fixed command · rewards · base contact · no curriculum · no DR）。任务/配方键（`baseline-flat-v1@1`）早在 `ed4d35b` 注册；本批补的是"这版能被**声明式**表达" |
| 共享接线 | 新 `BaselineWiringCfg` = 框架 stock cfg + 身份（`params_line` 为 ClassVar、`params_version` 为字段），**零 delta**；`BaselineFlatEnvCfg` 改为继承它，body 留作类路径（golden 由它产出） |
| 线维度 | `recipe.LINES = {line: {base, recipes}}`；`build/base_cfg/declared/pending` 收 `line=`（默认 main，既有调用全不受影响） |
| 硬 B | `versions/lizard/baseline/v1/diff.json`：相对**框架基类 stock cfg** 的 33 条具名差异路径 + 每条理由；`[41]` 双向校验 |

### 三条判断

- **"基准是 stock cfg"这句话本身被机器校验**：`diff.json` 声明 `wiring_is_stock_except: ["params_version"]`，`[41]` 真的比对 `snapshot(stock)` 与 `snapshot(接线类)`，不等即红（实测该 diff 恰为 1 条）。理由：接线类若偷偷带 delta，后面所有比较都失去意义。
- **差异清单写"具名路径"，不写子树前缀**：初稿量出 63 个叶子，聚成 33 条具体路径（`rewards.ang_vel_xy_l2`、`events.push_robot`、`commands.base_velocity.ranges.lin_vel_x` …）。若写 `rewards` 这种前缀，"新加一个奖励项"会自动通过——那就不叫"**只允许**一份显式差异清单"了。
- **`baseline_timing` 是 pin，不是死声明**：它把 decimation/episode/dt/render_interval 写成与 stock **相同**的值（实测这四条不产生差异），于是 `attribution` 的"每步至少动一个字段"会判它红。**不能删**——删了声明路径就不读 yaml 的 `sim:` 段，yaml 改了类会动、声明不动；等版本子类退役后那段 yaml 就成了没人读的装饰。故给配方表加显式 `pins` 名单，且**双向**校验（pin 一旦开始动字段即要求摘掉）。

### 结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A + 硬 B | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 33 declared difference(s) from the stock base)` —— main 24（v1–v14×2）+ baseline 2 |
| **反向验证（闸门真的会红）** | 三处临时破坏同时打：加一个未声明字段 / 清单里塞一条不产生差异的路径 / 摘掉 pin | **五个检测器各自打对**：未声明变化、声明了没生效、pin 变活、差异条数漂移（34≠33）、硬 A 字段漂移；banner 翻 `RECIPE_BUILD_FAILED`。随后三处**原样回滚**，复跑全绿 |
| 门 1 | `check_cfg_lock.py`（`[24]`） | 通过：`CFG_LOCK_OK (36 tasks, 3 line(s))` |
| 单写者 | `test_component_ownership.py`（`[37]`） | 通过：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s))` |
| golden 摘要 | `check_golden_frozen.py`（`[35]`） | 通过：`GOLDEN_FROZEN_OK`（3 份基线文件自 `020e6fb` 未动） |
| 旁证 | `check_obs_layout` `[8]` · `check_dr_parity` `[2]` · `check_obs_protocol` · `check_recipe_map` · `check_recipe_registry` · `check_configclass_fields`（39 类含 `BaselineWiringCfg`）· `test_params_isolation` `[34]` · `check_suite_shape` | **全绿**；新基类未影响 configclass 判定（"`params_version` 在全部类里都是 dataclass 字段"） |

### 边界

- **硬 B 只覆盖 env cfg**：agent（PPO）配置未纳入清单，`Lizard-Baseline-Flat-v1` 的 PPO 是否逐字段等于 framework 默认**未验**。
- **baseline 线的锁不在 `[35]` 的 FROZEN 表里**（表内是 3 份：`cfg_baselines.json` + main + parkour）。本批没跑 `--update`、没动锁，但"这条线的 golden 被移动"目前**没有摘要看守**——属 A 带遗留（B0 节已记 baseline 线"落点未跟踪"）。
- 版本类体与元素表**仍并存**（`BaselineFlatEnvCfg.__post_init__` 与 10 个元素逐段重复），过渡税与 teacher 线同：等 C2/C3 入口走到声明路径才能删类体。
- `recipe.py` 仍不在 `[37]` 的 HOSTS 里；baseline 元素写 `commands.base_velocity.*`（`components` 拥有的名字），与 main 线元素情形相同。
- 硬 B **不证"配方正确"**：它只证"与 stock 基类的差异恰好是声明的那 33 条"。也不证真环境行为（那要真跑）。
- 本轮**仍不新增套件条目**：硬 B 落在既有 `[41]` 内（同一套 snapshot/diff，只换期望值），不付第二份 import 税，也不碰并行侧的 `offline_suite.py`。

## 声明载体与接线对账（C2 切换入口前必须落的那批，2026-09-17）

**性质**：**追加**条目。这批是"声明来源 / 启动校验 / trainer 守卫 / T0-T1 记录"四件一次做完，因为**单改一处都不完整**：只删 save 守卫的合取会把它变成"训练几小时后 save 时才炸"；只改 manifest 会让其余三个读点继续按类读取。

**改动面**：`recipe.py`（`declares` 进配方表 + `declaration()` + `build()`/`base_cfg()` 返回**携带声明的合成子类**）、`curriculum_state.py`（`declares`/`wired_terms`/`expected_terms`/`verify_declaration` + 启动调用 + save 的载荷覆盖判据）、`check_recipe_build.py`（**过渡期保真闸门**：表 == 类）、`manifest.py`（T0 记 expected/wired/declaration_problems，原有 `declares_curriculum_state` 保留）、`test_resume_state.py`（新用例 + 反证）、`FILEMAP.md`。

### 关键设计：不改四个读点，而是让 `type(cfg)` 说真话

resume 拒绝、save 守卫、`train.py` 的导入失败守卫、manifest 记录，四者都读 `type(cfg)` 上的 `REQUIRES_CURRICULUM_STATE`。所以修法不是教四个读者认新来源，而是让**声明路径返回的类也带这句声明**（配方表为真源，`build()` 用 `type(...)` 合成子类盖上）；`launch_recipe.py`（C2 入口）与注册表仍走类路径，两条路径因此**答案一致**。

> **一处实测教训（写下来免得重踩）**：盖章必须写成 `ClassVar[bool]` 标注，不能只 `setattr` 一个值。只设值会让 `cfg_snapshot` 的 ClassVar 判定失效 ⇒ 它作为**字段**进入快照 ⇒ 一次跑出 **24 条硬 A 红 + 9 条归属无主 + 1 条硬 B 未声明差异**。标注后三条全消失：声明是"关于配方的陈述"，不是数据。

### 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A / 硬 B / 归属 | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 33 declared difference(s) from the stock base)` |
| 过渡期保真闸门 | 同上（每个 line/version/kind 比对表与类） | **通过**（26/26）；**反证 FIRED**：只把表里 v14 改成 `(False, False)` ⇒ `FAIL lizard/main/v14/train: the recipe states …=False while LizardRoughTeacherEnvCfg_V14 states True -- the two paths would answer differently` |
| 台账清理 | 同上 | **通过**：`REQUIRES_CURRICULUM_STATE` 不再是缺口 ⇒ 按"陈旧台账项也红"的规则删条目（`EXPECTED_GAPS` 现只剩 `PLAY_PINS_COMMAND_RANGE`） |
| 声明与接线对账 + save 覆盖 | `test_resume_state.py`（新用例 + 反证） | **通过**：28/28。三面：①声明 True 而配置不断言任何课程项 ⇒ `verify_declaration` 报"wires no curriculum at all"且 `hook_runner_save` 抛错；②已接的 stateful term 无 adapter ⇒ 报"no registered adapter"；③配置仍要该 term 而**接线被清空**（只有 c_k 时钟的载荷，`collect` 返回的不是 None）⇒ save 抛"un-resumable"。**反证 FIRED**：把 `declares` 读法摘掉后同一 save 顺利通过 ⇒ 上述红来自新判据，不是旧的"载荷为空"分支 |
| 旁证 | 全量套件 | **43/43**（wave 203 s / 400 s）；`[14]` 仍 `task cfg import chain is pxr-clean`（`recipe.py` 新增 `curriculum_state` import 未破坏链） |

### 边界

- **合取保留**（`requires_resume_state = 声明 ∧ 有接线`）：它不再承担"声明是否成立"的判断，那件事移到启动时 `verify_declaration`（训练前终止）；它在 resume 侧仍表达"这条任务确实要恢复点什么"。
- **对账用"配置字段"而非第二张 term 清单**：`expected_terms` 从 `cfg.curriculum.*` 派生（取不到时回落 manager 的 cfg，为的是不把 stub 读成"配置什么都没要"）。因此**不新增手抄映射**；代价是"声明与接线"的对账强度取决于 cfg 字段与 manager 是否同源（真实 env 上二者本就是同一对象）。
- **`train.py:324` 一字未动**：它的读法在声明路径变真后自动正确 —— 这正是"改载体、不改读者"的收益。
- **仍未做**：`launch_recipe.py` 改走 `recipe.build()`（即"声明路径成为训练入口"）与随之的版本类体删除；硬 B 仍只覆盖 env cfg（agent 配置未纳入）；真环境行为等价仍要 C 层真跑。
- **`declares` 的值是过渡期抄自版本类的**（train True/False、play 全 False），由保真闸门逐步看守；等类体删除后，配方表成为唯一来源。

## 入口切换的机制与第一档真跑（C2 机制 / C4 部分，2026-09-17）

**性质**：**追加**条目。C2 的"声明路径成为训练入口"拆成两件可分别验收的事：**机制**（本节）与**翻注册表**（未做，见边界）。C4 同理：五档真跑里只有一档不需要仿真，本节把它真跑掉。

### 机制：`apply_into` + `recipe_class`
- `build()` 的步骤体抽成 `apply_into(cfg, version, play=, line=, trace=)`，`build()` 变成"构造共享接线的实例 + `apply_into`"；`recipe_class(version, play=, line=, name=)` 生成一个 `@configclass` **子类**，其 `__post_init__` = `base.__post_init__(self)` + `apply_into(self, …)` —— 版本类体当年就在这个位置干这件事，所以注册表能指它。
- **两者共用同一份步骤** ⇒ 不可能漂移；`[41]` 逐条断言"可注册的类构造出来的 cfg == `build()` 的 cfg"（26 个 task/kind 全过）。
- `name=` 参数是给切换用的：**注册类叫什么名，生成的类就叫什么名**。因为 ckpt 载荷记 `type(cfg).__name__` 并参与 resume 身份核验，名字不一致会让"类路径起的 run"无法被"声明路径"续训。

### 检查与结果

| 项 | 结果 |
|---|---|
| 机制等价 | `[41]` **通过**（26/26）；**灵敏度**证明："拿 v13 的类去比 v14 的 build"出 3 条差异 ⇒ 这个比对不是恒空 |
| `[41]` 成本 | 单跑 **9.7 s**（预算 25 s；+26 次构造约 +1 s） |
| **C4 第一档真跑（launcher）** | **通过**：`lifecycle_entry_run.py --track launcher` ⇒ 退出码 2、stderr `[launcher] refused: retired line: refusing new_train; new work belongs to an active successor line`，且**没有新建 run 目录**（拒绝发生在 spawn 之前 ⇒ trainer 从未启动）。这一档不需要 sim app，所以它现在就是真证据，不是离线断言 |
| 其余四档 | **真跑通过**（`--track all`，一条命令五档）：`trainer` 拒绝且 T0 记 `allowed=False`；`tuning` 被同一子进程杀死（exit 1）；`announce` exit 0 且记录 `warn="the line's announced retirement is due and the directory has not been revised; recording the overdue directory, proceeding under status=active"`；`moved` 记录保住原目录摘要、`verify` 只报告"目录已改" |
| **由此发现并修掉的缺陷（真跑才看得见）** | 拒绝**没有被退出码观察到**：进程打印拒绝、T0 记 `allowed=false`，却 **exit 0**（Isaac 的 app 收尾在返回路径上把码归一）。按退出码判成功的调用方（CI、`&&` 链、扫参调度）会把它当成功 ⇒ fork 补丁在 T0 调用点加 try/except：打印 `[FATAL]` 后 `os._exit(2)`（`os._exit` 是必需的，降级 `raise`/`sys.exit` 依然被收尾吞掉）。实测 `RC=2`；`[1] PIN_CHECK_OK` 复验补丁链仍与 fork 树逐字节一致 |
| `moved` 的控制修正 | 首版两份 fixture 内容相同（只改 revision 数字、值一样）⇒ 摘要相同 ⇒ 控制没生效（假过）。加 `bump=` 让 A/B 修订真的不同后，`verify` 才报出"目录已改" |

### 边界
- **注册表未翻**：`rl_exp\tasks\__init__.py` 的 `env_cfg_entry_point` 与 `recipes.json` 的 `env_cfg_entry` 仍指版本类 ⇒ 训练走的还是类路径。翻表是三步（生成类 + 改两处字符串 + `name=` 对齐），本轮只把机制与证明备好，**没动**——因为它同时意味着版本类体可以开始删，那是 B 侧迁移的收尾节奏。
- `recipes.json` 里 baseline 的 demo/extra 条目与 `RECIPE_DEMO`/`EXTRA_TASKS` 无关（主线任务），所以翻表不影响它们。
- C4 的 `launch` 档只证"新入口在 `gym.make` 前拒绝"；`trainer` 档另外证"拒绝会被退出码观察到，且 T0 留下拒绝记录"；`tuning` 档证"调参入口不能绕过"。
- **入口侧验收状态（本节更新）**：L02（退休线过三个入口）**通过**（三档各自真跑）；L03 的"缺状态 resume 硬拒"仍只有离线半边（真跑需一个缺课程状态的 ckpt 臂，属 C 层旧账）；L05 的"启动后改目录"**通过**（`moved` 档）。
- 本批不新增套件条目（机制断言落在 `[41]` 内；`lifecycle_entry_run.py` 要起 sim，按 `OFFLINE_CHECKS.md` 5 不进套件）。

## C2 收尾 · 翻注册表：声明路径成为训练入口（2026-09-17）

**性质**：**追加**条目。上节备好的机制在本节**接上电**：26 个已声明任务的 `env_cfg_entry`（注册表）与 `env_cfg_entry_point`（身份映射）从版本类改指 `recipe_tasks` 的生成类。

### 落地
| 件 | 内容 |
|---|---|
| `tasks\recipe_tasks.py`（新） | 每条已声明配方 × train/play 生成一个类，**名字沿用被替换的版本类名**；名字从 `recipes.json` 读（身份映射），不另立清单；模块无需显式 import（注册表以字符串指向它） |
| 注册表 + 身份映射 | 各 26 条 entry 改指 `rl_exp.tasks.recipe_tasks:<同类名>`（脚本改字符串，逐条打印，未手抄） |
| `[41]` 过渡闸门 | 改为**按发现**取被替换的版本类（构造候选类读 `params_version` —— 它是字段，1.0 结论；版本令牌优先解决"最新类与 `_V<N>` 类同版"的歧义）。**不改就会静默失效**：翻表后身份映射指向生成类，闸门若仍经它取类，就是拿生成类与自己比 |
| `test_recipe_map_gate.py` | 反证用例改为断言"解析器读到了 env 入口"（类名后缀）而非"等于某个模块路径"，否则它会为一次它并不看守的改动变红 |

### 检查与结果
| 项 | 结果 |
|---|---|
| 真实入口路径 | **通过**：`gym.spec('Lizard-Rough-v14')` → `rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V14` → 构造得 `params_version=v14`、`REQUIRES_CURRICULUM_STATE=True`、`type(cfg).__name__` **与翻表前同名**（PLAY 同理） |
| 硬 A / 硬 B / 归属 / 生成类等价 | `[41]` **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 76 declared difference(s) from the stock base)`，单跑 9.8 s（预算 25） |
| 全套 | **43/43 通过**（wave 199 s / 400）—— 含 golden `[24]`（逐字段未动）、身份映射 `[31]` + 其反证 `[32]`、obs 契约、pxr `[14]`、生命周期 `[39][40]`、组件单写点 `[37]` |

### 边界
- **版本类体已无人引用，但没删**：删除属 B 侧迁移收尾；`[41]` 的过渡闸门正靠发现它们而与配方表对账 —— 删干净时该闸门应当被**显式退役**（"找不到被替换的类"现在是红，不是跳过）。
- **未改**：agent（PPO）配置仍由 `rsl_rl_ppo_cfg.py` 的类提供（本轮只翻 env cfg 入口）；hydra override 语义、日志目录名、`--task` 与 agent 入口的一切不变。
- 生成类与版本类**是不同的类对象**：全仓已查无按类身份判版本的代码（只有框架基类的 `isinstance`），故无静默错。
- 声明路径成为入口 ≠ 已被真跑覆盖：`lifecycle_entry_run.py` 的五档验的是**生命周期判定**；"声明路径训练出的 run 与类路径等价"仍由 `[41]` 的字段等价 + 将来的真跑背书。

## B4 · 硬 B 加齿：路径归属元素 + agent 侧进清单 + baseline 锁入摘要看守（2026-09-17）

**性质**：**追加**条目。上一节 B2/B4 列的四条里，本节收**三条**；第 4 条（注册表翻表 / 删版本类体）由并行批次的 `apply_into` + `recipe_class` 开头，本节只记**我核实的那一步**（见末节）。改动面 = `[41]`（`covers()` 方向、`hard_b` 的两侧、agent 段）、`versions/lizard/baseline/v1/diff.json`（format 2）、`[35]`（FROZEN 第 4 项 + `FROZEN_REVS` + 两表键一致性）。

**顺带作废旧边界**：上一节"硬 B 只覆盖 env cfg"一条**自此失效** —— agent 侧已进清单。

### 三条

| 条 | 落地 |
|---|---|
| ① 每条路径必须归属某元素 | `diff.json` 的 env 条目改为 `{路径: {element, why}}`。`[41]` 用与 `attribution` **同一套 trace 重放**算出"每个元素真正动了哪些字段"，逐条比对：**没写元素名**、**元素名不存在**、**该元素不产出这条路径**——三种都红。⇒ 改清单消红必须同时改元素表，否则红（这正是上一节点名"同型洞"的堵法：归属不是自由文本，是断言） |
| ② agent 进清单 | `diff.json.agent`：基准 = 框架 stock `RslRlOnPolicyRunnerCfg`，主体 = `recipes.json` 的 `agent_entry`（不在声明里抄第二份）。实测 stock 把 model/algorithm 整块留空 ⇒ **43 条差异**，**逐条列叶子**（写 `algorithm` 当一条前缀，等于让框架新增的 PPO 字段自动通过）。同一套双向校验：未声明 / 声明了没生效 |
| ③ baseline 锁进 `[35]` | FROZEN 表第 4 项：`baseline/cfg_lock.json` sha256 `61d32e8d…`（**冻结于 `ed4d35b`**，晚于其余三份的 `020e6fb`）。新增 `FROZEN_REVS`——`check()` 是纯函数、自测拿它当纯函数证伪，把"谁在何时冻结"混进去等于污染被证伪的核心，故单独一张表只喂 banner，并校验**两表键一致** |

### 判断

- **方向**：`covers(声明项, 路径)`。条目通常比它覆盖的路径浅（`scene.robot` 覆盖 12 个叶子、`events.reset_base.params.pose_range` 覆盖 6 个 `__tuple__[n]`）。初版把方向写反，`[41]` **当场报 7 条假红** —— 假红本身是好事：说明这个比较真的在比，而不是恒空。
- **agent 侧不做元素归属**：agent 是**类**不是声明，没有元素可归。所以它只带理由、不带元素名；`hard_b` 对两侧各施加**各自能施加**的校验，而不是把 env 的规则套上去假装两侧同构。
- **baseline 锁的债是"最值钱"的那条**：这条线是接下来要真训的线，而在本条之前"它的 golden 被移动"**没有任何摘要看守**（B0 节原来只钉 3 份文件、且已记 baseline 线"落点未跟踪"）。现在合法重基线在这条线上也回到"两处编辑 + 理由 + 逐字段审查"。

### 结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A + 硬 B | `[41]` | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 76 declared difference(s) from the stock base)`（33 env + 43 agent） |
| **反向验证**（五检测器 + 一张表） | 八处临时破坏 | **各自打对**：未声明 env 变化 / env 声明了没生效 / **归属元素不存在** / **归属元素不产出该路径** / agent 未声明（少一条叶子）/ agent 声明了没生效（多一条假叶子）/ 计数漂移（77≠76）/ `FROZEN_REVS` 与 `FROZEN` 键不一致（`GOLDEN_FROZEN_DRIFT`）。随后**原样回滚**，两闸复绿 |
| golden 摘要 | `[35]`（含 `--self-test`） | **通过**：`GOLDEN_FROZEN_OK (4 baseline file(s) unchanged, frozen at: 020e6fb x3, ed4d35b x1)`；自测 `GOLDEN_FROZEN_SELFTEST_OK` |
| 门 1 / 单写者 | `[24]` / `[37]` 复跑 | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` · `COMPONENT_OWNERSHIP_OK`（本批不改 cfg 内容） |

### 第 4 条（版本类体并存的过渡税）：**已核实可删**，但本轮不动

并行批次 384468e 已把机制备好（`apply_into` + `recipe_class`：声明做成"注册入口能指向的类"）。本批**只读**核实 baseline 线：

| 比较 | 结果 |
|---|---|
| `recipe_class("v1", line="lizard/baseline", name="BaselineFlatEnvCfg")()` vs `build(…)` | **逐字段 0 差异** |
| 同上 vs 该配方冻结 golden | **逐字段 0 差异** |

⇒ 把注册项指到该合成类、同时删掉 `BaselineFlatEnvCfg.__post_init__` 的重复 body，**可以做到不看任何字段变化**。本轮不动的理由：那个 API 当时还在并行侧的工作树里（未提交），我在其上写调用点会把依赖钉在未提交代码上；且"翻表 + 删类体"是同一件事的三步（生成类 / 改两处字符串 / `name=` 对齐），归那一批做。

### 提交归属（**写清楚，免得历史对不上**）

本节的 `[41]` 改动**落在 384468e**（并行批次提交时，当时工作树里的 `[41]` 被一并 `git add` 进去）；本批自己的提交是 **`9894f73`**（`diff.json` format 2 + `[35]`）。两处合起来才是本节的完整改动面。

### 边界

- 硬 B **不判"这条差异是否合理"**：它只判"与基准的差异是否恰好等于声明"，合理性是 PLAN/review 的事。也不判真环境行为。
- `FROZEN_REVS` 只喂 banner，**不是比较规则的一部分**（比较只看 `FROZEN` 摘要）。
- agent 的"基准 = 框架 stock"未做像 env 那样的"基准确实是空"的机器校验（env 侧有 `wiring_is_stock_except`）；agent 侧直接以 stock 为基准，无中间接线类可夹带。
- 本批**未跑全量套件端到端**（套件条目随并行批次变动）；所跑为 `[41]` `[35]`（含自测）`[24]` `[37]`。

## 收掉最后一条声明缺口：`PLAY_PINS_COMMAND_RANGE` 进配方表（2026-09-17）

**性质**：**追加**条目。本批对应"**不加验证框架、只处理已确认的声明丢失**"那一条判断：`[41]` 台账里只剩的最后一条缺口。改动面 = `recipe.py`（配方表 `pins_full_range` + `pins_full_range()` / `_stated()` + `CLASSVAR_STATEMENTS` + 两处盖章）、`[41]`（保真判据按同一张清单循环 + `EXPECTED_GAPS` 清空 + docstring）。**未扩展元素所有权系统**（理由见末节）。

### 为什么这条必须在翻表前做

`PLAY_PINS_COMMAND_RANGE` 的读者是**共享接线的 `__post_init__`（构造期）**：v3/v4 的 PLAY 已无课程可以把范围拉宽，所以它要满量程而不是课程窗口。配方表沉默期间，声明路径读到的是基类的 `False`，**效果**由 `play_pins_full_command_range` 事后补上 —— 字段是对的，**声明没有了**。翻表之后（注册项指向合成类、版本类体开始删），那句话只剩在类体上，**会随类体一起消失**。所以它必须在翻表之前搬进表里。

### 落地

| 件 | 内容 |
|---|---|
| 配方表 | 每个配方加 `"pins_full_range": (train, play)`，v3/v4 = `(False, True)`、其余 `(False, False)`（与 `declares` **同形同位置**） |
| 读法 | `pins_full_range(version, play=, line=)`，与 `declaration()` 对称，共用 `_stated()` |
| 一处清单 | `recipe.CLASSVAR_STATEMENTS = ((REQUIRES_CURRICULUM_STATE, declaration), (PLAY_PINS_COMMAND_RANGE, pins_full_range))` —— "哪些声明要离开类体"只有一个答案；`_wired_class` 与 `recipe_class` 都照它盖章（按名标注 ClassVar，不是 `setattr`） |
| 闸门 | 保真判据改为对该清单循环（表 == 类，**两个 ClassVar × 两种 kind**）；`EXPECTED_GAPS` **清空**；docstring 里"构建器结构上带不走 ClassVar"那一段改写为过渡期规则（清单为真源、两条路径答案必须一致、无家可归者打印并须进台账） |

### 结果

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A / 硬 B | `[41]` | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 76 declared difference(s) from the stock base)`，**输出里不再有任何 ClassVar 缺口行**（台账空且无缺口 —— 上一节还有两类，现在为零） |
| **反向验证** | 三处临时破坏 | **各自打对**：① v3/play 表值翻成 `False` ⇒ `…PLAY_PINS_COMMAND_RANGE=False while LizardRoughTeacherEnvCfg_V3_PLAY states True -- the two paths would answer differently`；② 删掉 v4 的表键 ⇒ train/play **各自** `states no PLAY_PINS_COMMAND_RANGE … (the class path states …)`；③ 空台账下缺口再现 ⇒ `classvar the declaration cannot carry, and the ledger does not know it`。随后**原样回滚**复绿 |
| 旁证 | `[24]` · `[28]` · `[37]` · `[14]` | **全绿**：`CFG_LOCK_OK (36 tasks, 3 line(s))` · `test_resume_state: 28 passed` · `COMPONENT_OWNERSHIP_OK` · `task cfg import chain is pxr-clean` |

### 边界

- 基类**仍**声明 `PLAY_PINS_COMMAND_RANGE = False`，类路径照旧可读；本批做的是"让声明路径也说得出这句话"，**不是删旧载体** —— 删类体归翻表那批。
- **台账空 ≠ 机制停用**：`EXPECTED_GAPS` 仍在，新增一个"表里没家、类上有"的 ClassVar 会立刻红（本轮已验证"未知缺口"分支；"陈旧台账项也红"分支由并行批次的用例覆盖）。
- 本轮**未动翻表**（`rl_exp/tasks/__init__.py` 的 `env_cfg_entry_point` / `recipes.json` 的 `env_cfg_entry` 两处字符串）——那是并行批次的节奏；本批只把它前面最后一块砖补上。
- 未跑全量套件端到端。

### 明确不做：元素所有权系统（用户判断 2026-09-17）

上一节点名的"给每个元素声明允许写入的字段集"**不做**，理由被采纳：① 要抓"同值写入 / 先改再恢复"得上完整写入追踪，而目前**没有任何实际故障**证明值得；② YAML 在既有字段上的数值变化**本来就不是字段所有权检查的职责**，现有 golden 已能拦（`[24]` 对类路径、`[41]` 对声明路径）；③ "元素与清单可同时改"不是漏洞 —— 任何源码级检查都能连规则一起改，最终仍靠 review。

**本批把归属做成显式可校验的断言**（每条路径点名元素、闸门重放验证）即为该问题的收口。**后续若出现具体反例**（现有检查确实漏掉了非预期覆盖），再补**最小**检查；在此之前不扩机制。










