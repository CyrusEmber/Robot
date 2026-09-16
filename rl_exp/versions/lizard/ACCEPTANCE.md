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



