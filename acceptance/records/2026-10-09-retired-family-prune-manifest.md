# 退休线清理删除清单（2026-10-09）

## 适用范围

对象 = 三条已退休线（`lizard/main`、`lizard/parkour`、`lizard/baseline`，见 `rl_exp/versions/lines.json`）
在**代码、任务注册、离线套件条目、在办事项**四处的主路径残留。逐项标 `删 / 留 / 改` 与判据，
供用户审后执行（执行前打 tag `lizard-final`）。

本文件是**清单与裁决记录**：执行落盘后另出执行记录。调研只读文件与 import 关系，
未跑训练、未跑仿真、未改任何代码与配置。

不动的边界：`rl_exp/versions/lizard/**` 的文档 / yaml / 历史 lock、`acceptance/records/`、
`ablation_harness/results/` 下的历史数据、`versions/lines.json` 的退休条目本身。

## 验收条件

- 每个候选文件 / 每条离线检查 / 每个在办事项有且只有一个判定，且判据写"谁依赖它"，不按文件名整组删。
- 三处已知反向耦合必须先拆（§0），拆法逐条给出。
- 批准后的判据形状（不预先断言本次会通过）：`run_offline_checks.bat` 全绿、
  `Lizard2-Flat-v1/v2/v3` 能注册与构造、`check_cfg_lock` / `check_recipe_map` / `check_pxr_leak` 绿。

## 结果

### 0. 执行前必须先拆的三处耦合（复核结论）

| # | 耦合 | 事实（file:line） | 拆法 |
|---|---|---|---|
| 1 | `recipe.py` ↔ 旧线**双向** | `recipe.py:42-49` import `baseline_env_cfg` / `baseline_recipe` / `components` / `teacher_mdp` / `curriculum_env_cfg` / `lizard_env_cfg` / `rough_env_cfg` / `curriculum_state` / `teacher_env_cfg` / `staged_curriculum`；同时它是 `lizard2/main` 的装载器（`recipe.py:687-695`） | **不删 `recipe.py`**（`check_recipe_build.py:63`、`rl_exp/tools/pipeline/emit_diff_declaration.py:40` 以 `line="lizard2/main"` 调它）。删旧线 import、`RECIPES` 表、`MAIN_LINE` / `BASELINE_LINE` / `BASELINE_RECIPES`、v0 与 v3–v14 元素、`LINES` 的前两键；留 `LIZARD2_LINE` / `LIZARD2_RECIPES` / `LINES["lizard2/main"]` 与 `CLASSVAR_STATEMENTS` |
| 2 | `curriculum_state.py` → `teacher_mdp` | `curriculum_state.py:93-97` import `JointSIRTerrainCurriculum` / `SpawnWeightSIRTerrainCurriculum` / `ck_value`，用在 `:319` `:456` `:848` `:1203`；`work/active/dr-widening-policy.md` 已把续训状态层声明为 **lizard2 未来依赖** | **`teacher_mdp` 保留**（裁决 A①）。删旧线元素即可，该文件不动内容 |
| 3 | lizard2 runner → baseline runner | `agents/rsl_rl_ppo_cfg.py:355` `Lizard2PPORunnerCfg(LizardBaselinePPORunnerCfg)` | 改基类为 `RslRlOnPolicyRunnerCfg` 并搬字段。lizard2 用 MLP（不涉 `teacher_networks`），改动面小 |

### 1. `rl_exp/tasks/` 逐文件

| 文件 | 判定 | 依据（依赖方） |
|---|---|---|
| `__init__.py` | **改** | 删 39 条旧线注册（`:20-338` 33 条 `Lizard-*`、`:346-364` 2 条 Parkour、`:374-415` 4 条 Baseline），留 `Lizard2-*` 6 条（`:421-483`） |
| `agents/rsl_rl_ppo_cfg.py` | **改** | 删旧线 runner（`:12-351`）；`Lizard2PPORunnerCfg` 改基类（§0-3） |
| `agents/__init__.py` | 留 | 包标记 |
| `recipe_tasks.py` | **改** | `_LINES_BUILT_ELSEWHERE` 去 `lizard/baseline`（`:41`）、`_builder` 的 baseline 分支（`:117-122`）随之死 |
| `recipe.py` | **改** | 有 active 调用方（§0-1） |
| `lizard2_env_cfg.py` / `lizard2_recipe.py` | 留 | 活跃线本体；只依赖 `recipe_params` / `play_utils` / `recipe_factory` |
| `obs_protocol.py` | 留 | 纯 stdlib（`:22-28`），被 lizard2 与 `runrecord/manifest.py:173` 等共用 |
| `recipe_params.py` / `recipe_factory.py` / `play_utils.py` | 留 | lizard2 直接 import（`lizard2_env_cfg.py:56-57`、`lizard2_recipe.py:32-34`） |
| `terrain_map.py` / `terrain_geometry.py` | 留 | 地形拆分与几何共用层（`terrain_split_probe.py:37-38`、`test_terrain_map.py`、`check_split_probe_wait.py`） |
| `curriculum_state.py` | 留 | 被 `dr-widening-policy` 声明为 lizard2 续训依赖；A① 下其 `teacher_mdp` 依赖成立（§0-2） |
| `teacher_mdp.py` | **留（A①）** | 删除面上的最大耦合点：旧线奖励 / 终止 / SIR / c_k 实现集中在此，且被 `curriculum_state` 反引用。本次只让它的旧线调用方消失，文件本身不动；纯旧线的奖励与终止内核留在其中 = 已知代价，另立事项定去向 |
| `param_grid_terrain.py` | **留（A①）** | 它是 SIR 参数网格的构建器（`teacher_mdp.py:876` 注释所指），与保留的 SIR 段配对；其 Python 入口 `build_param_grid_terrain_cfg` 现仅由将删的 `components.py:37` 与两条 verify 脚本使用 ⇒ 保留期内是"只被停跑的检查与保留的 SIR 机制引用"的库模块 |
| `teacher_env_cfg.py` | **删** | 消费者全是旧线：`recipe.py:46`、`check_obs_layout.py:25`、`teacher_smoke.py:26`、`terrain_preflight.py:52`、`test_component_ownership.py:34`、`test_v3_curriculum.py:18`、`test_params_isolation.py:20` |
| `components.py` | **删** | 旧线结构组件的唯一写者（`recipe.py:42`、`teacher_env_cfg.py:49`、`test_component_ownership.py:33`）；lizard2 不 import 它 |
| `lizard_env_cfg.py` | **删** | 被 `recipe.py:44`、`curriculum_env_cfg.py:26`、`rough_env_cfg.py:25` 与 4 个 verify 脚本用，全旧线 |
| `rough_env_cfg.py` | **删** | 仅 `recipe.py:44`（`v0_rough_terrain`） |
| `curriculum_env_cfg.py` | **删** | 仅 `recipe.py:44/485` + 自身 import `lizard_env_cfg`（`:26`） |
| `staged_curriculum.py` | **删** | 消费者 `recipe.py:49`、`teacher_env_cfg.py:51`、`curriculum_env_cfg.py:30`、`test_staged_curriculum.py` 全旧线；lizard2 不接课程（`dr-widening-policy` 记 v1 `REQUIRES_CURRICULUM_STATE=False`） |
| `teacher_networks.py` | **删** | 仅 teacher runner（`:96/:122/:129`）、`student_networks.py:37` 与两个测试用；lizard2 runner 走 MLP |
| `student_networks.py` | **删** | 蒸馏线，仅 `test_student_networks.py:16` |
| `baseline_env_cfg.py` / `baseline_mdp.py` / `baseline_recipe.py` | **删** | `recipe.py` / `recipe_tasks.py` / 各自测试，全旧线 |
| `parkour_env_cfg.py` / `parkour_mdp.py` | **删** | 仅注册表（`__init__.py:351,361`）、`parkour_smoke.py:22`、`test_params_isolation.py:20` |

### 2. 其它文件

| 路径 | 判定 | 依据 |
|---|---|---|
| `rl_exp/versions/recipes.json` | **改** | 删 21 条旧线 recipe 键（`:4-231`）与 39 条 task 映射（`:270-307`）；留 lizard2 各 6 条（`:232-267`、`:308-313`） |
| `rl_exp/versions/obs_protocols.json` | **留（裁决 C②，替代 C①；见 §8）** | 保留 golden 的协议可读面；退休只退出注册与运行，不删除历史任务映射 |
| `rl_exp/versions/obs_protocol_anchors.json` | **留（C②）** | 与保留的协议声明配套；不接受本次清理导致历史 manifest 的协议复读降级 |
| `rl_exp/versions/freeze_parity.json` | **删文件（裁决 D①）** | 唯一 subject 是 `lizard/main`（`:4-33`），两份手抄 cfg 都删 ⇒ 机制无被试对象 |
| `rl_exp/versions/lines.json` | 留 | 退休记录本身是历史事实 |
| `rl_exp/versions/lizard/**`（含 `cfg_lock.json`） | 留 | 边界 |
| `rl_exp/versions/lizard2/main/cfg_lock.json` | 留 | 活跃线 golden；删除后须用 `check_cfg_lock.py --diff` 复核未漂移 |
| `rl_exp/fork_patches/config_lizard___init__.py` | 留 | 只 `import rl_exp.tasks`，lizard2 也经它注册；改名会牵动部署链，收益为零 |
| `FILEMAP.md` 相关条目 | **改** | `rl_exp/tasks/` 节提到的 parkour / baseline 支线、`teacher_smoke*`、`_LINES_BUILT_ELSEWHERE` 等行 |
| `rl_exp/tools/verify/` 脚本 **删** | **删**（24 个） | `teacher_smoke.py`、`teacher_smoke_v{3,5,6,8,11}.py`、`teacher_smoke_runner.py`（§7-2 由"留"翻"删"）、`parkour_smoke.py`、`check_reward_v13.py`、`check_terminations_v14.py`、`test_v3_curriculum.py`、`test_v5_rewards.py`、`test_v12_noise.py`、`test_student_networks.py`、`test_baseline_mdp.py`、`test_baseline_isolation.py`、`test_component_ownership.py`、`test_teacher_networks.py`、`test_staged_curriculum.py`、`check_obs_layout.py`（裁决 B2①）、`pose_check.py`、`joint_check.py`、`position_check.py`、`smoke_test.py` |
| 同上 **改** | **改** | `framework_pin_check.py`（按 §8-F 清旧消费者 needle、保留活跃 PPO 与续训依赖）；`check_recipe_build.py`（计数表 `:68-135` 删两条 lizard 行、留 `lizard2/main`，并按 §8-G 删除 component 专属归因）；`check_dr_parity.py`（删两节 freeze-parity 代码 + `load_subjects` 的 `SUBJECTS_PATH` 引用；留 asset contract 与 body swap 段）、`test_params_isolation.py`（`:20` 四处 import 全是被删模块）、`test_launcher.py`（`:39-41/:69/:186` 硬编码 `Lizard-Rough-v14` / `lizard/main`）、`terrain_preflight.py`（默认 `--version v4` 指 lizard，contract `teacher_env_cfg.py`） |
| 同上 **留**（含"随 A① 由删转留"的） | 留 | `test_joint_sir.py`、`test_v5_terrain_sir.py`、`cstate_observer.py`（SIR 段保留 ⇒ 其断言对象仍在）、`test_resume_state.py`、`check_c_layer.py`、`lifecycle_entry_run.py`、`check_version_docs.py`（`:79-87` 已内建 retired 版本判据——退休线目录留在盘上即仍被覆盖，**不需改**） |

### 3. 离线套件 48 项：删 11 / 改 8 / 留 29（执行面复核后校正，依据见 §7）

**删（11）**：`[4]` test_staged_curriculum、`[5]` test_teacher_networks、`[6]` test_student_networks、
`[7]` test_v3_curriculum、`[8]` check_obs_layout（B2①）、`[9]` test_v5_rewards、`[16]` test_v12_noise、
`[20]` check_reward_v13、`[21]` check_terminations_v14、
`[34]` test_baseline_isolation、`[37]` test_component_ownership。
理由同 §1/§2：被断言对象在删除面上（contract 直指 `versions/lizard/**/main_params.yaml` 或被删模块）。

**改（8）**：`[1]` framework_pin_check（contract 指被删模块）、`[2]` check_dr_parity（D①）、
`[12]` terrain_preflight（地形来源重指）、`[22]` test_baseline_contract（**摘掉旧线尾段，条目保留**，见 §7-1）、
`[33]` test_params_isolation（import）、`[40]` test_launcher（硬编码任务）、`[41]` check_recipe_build（计数表）、
`[42]` check_obs_protocol（**条目参数加 `--live`**：`:526-530` 支持 `--self-test` 与 `--live` 并存，
`:547` 的 live 半边补上被删的 `[8]` 的覆盖）。

**留（29）**：其余条目。点名几条易误判的：`[10]` test_v5_terrain_sir、`[11]` test_joint_sir、
`[18]` test_resume_state（A① 下 SIR 实现与冻结参数文档都在，断言对象未消失）、
`[14]` check_version_docs（retired 判据已内建）、`[39]` test_lifecycle_gate（用 `lines.json` 的
`lizard/parkour` 退休条目当样例，条目保留）、`[17]` check_pxr_leak 与 `[24]` check_configclass_fields
（走注册表，注册一删自动只剩 lizard2）、`[48]` check_leg_reachability（lizard2 资产）、
`[26]`/`[35]` cfg_lock / golden（**经复核不需改**：`check_cfg_lock.py:650-701` 只遍历"有注册任务的行"，
退休线零注册后其 golden 永不被读）。

**连带修改**：
- `offline_suite.py:195` `MAX_CHECKS` 48 → **37**（棘轮常数必须同步收）。
- `offline_suite.py:196` `SERIAL_BUDGET_S = 175.0` 须 `--confirm-cost` **实测后**再钉，不按比例外推。
- **顺序约束（不可省）**：`MAX_CHECKS` 是硬上限，48 封顶 ⇒ 给 `[42]` 加 `--live`（新增一条检查）
  必须在 11 条删除**之后**的独立提交里做，否则套件瞬态 49 条、`_count_problem` 直接红（`offline_suite.py:314-326`）。

### 4. 在办事项（口径 = `check_work_docs.py --list` 的 28 项；其中 1 项是本项自身 ⇒ 27 项待判）

**判删（9）**：
`baseline-pre-make-record-check`（`next` 的触发条件"baseline 线下一次启动"永久不可达）、
`baseline-v2-recipe`（`in_progress`，线已退休、产物已判 pass）、
`staged-curriculum-metric-wiring`、`v7-ghost-leg-implementation`（`versions/lizard/main/v7`）、
`teacher-literal-parity-gate`、`teacher-snapshot-asset-sync`（teacher 快照的对照家族即退休线）、
`phase2-obs-fidelity`（teacher/student 蒸馏 Phase 2，两侧皆退休）
—— 这 7 项是**剥离性动作被本项接管**，写 `superseded` + `superseded_by: retired-family-code-prune`；
`row-sir-commanded-measurement-defect`（只划退役线历史读数边界，非被接管）、
`deployment-delay-injection-dr`（`blocked`；landing = `components.py` + `versions/lizard/OBS.md`，仓内零实现，
无 lizard2 落点）
—— 这 2 项写 `cancelled` + 理由，后者若日后要作 lizard2 的 DR 需求则另立。

**判改（3）**：
`asset-tree-per-family`（`next` ② 是旧家族冻结分歧处置，收窄措辞，主体留）、
`verified-rebuild-rating`（`scope`/`landing` 含 `versions/lizard/ACCEPTANCE.md`，改指 lizard2 版本）、
`obs-three-tables-merge`（`landing` 含将被删的 `components.py`，改指 `versions/obs_protocols.json`）。

**判留（15）**：`dr-widening-policy`、`eval-protocol-before-training`、`exit-status-swallowed-by-app-close`、
`floor-contact-attribution`、`gate-admission-rule`、`harness-version-anchor-missing`、
`headless-flag-deprecation`、`isaac-root-parameterisation`、`joint-limit-shape-and-range-pass`、
`large-monitor-skeleton-muscle-literature`、`live-doc-ledger-numbers`、`lizard2-family-landing`、
`record-format-live-checks`、`record-variant-and-snapshot-specs`、`runtime-acceptance-v3`。

**关闭机制**（`check_work_docs.py` docstring 口径，不发明）：状态词表 = `open / in_progress / blocked /
done / cancelled / superseded`；后三词即关闭，关闭 = **移动不是改写**——文件移进 `work/closed/<year>/`、
保留 id、**去掉 `next`**、补 `outcome`；`cancelled` 须写理由、`superseded` 须补可解析的 `superseded_by`；
未做完的动作另立活跃事项。

### 5. 裁决记录（六项，用户拍板 2026-10-09）

| # | 题面 | 裁决 |
|---|---|---|
| A | `teacher_mdp.py` 的 SIR / c_k 段去向 | ①**保留 teacher_mdp**，只删旧线其余模块；死代码暂留，其去向另立事项 |
| B | 离线套件 12 条旧线检查 | ①**删脚本 + 删条目**（`MAX_CHECKS` 48→36） |
| B2 | `check_obs_layout.py` | ①**删**，并把 `check_obs_protocol --live` 补进套件 `[42]` |
| C | `obs_protocols.json` / anchors 的 lizard 条目 | 原裁决 ①删；发现 §7-3 的保留 golden 冲突后，用户拍板改为 **②保留**（2026-10-09，见 §8-C）；原裁决撤回，不加 retired 豁免 |
| D | `freeze_parity.json` 与 `check_dr_parity` 的 freeze-parity 段 | ①**删该机制**（与其唯一主体同进退），保留 asset contract / body swap 段 |
| E | 9 项判删事项的关闭词 | 按接管关系分开写：7 项 `superseded_by: retired-family-code-prune`；2 项（`row-sir-commanded-measurement-defect`、`deployment-delay-injection-dr`）`cancelled` |

### 6. 执行顺序（批准后照此走，每步都是独立可回滚的提交）

1. **打 tag `lizard-final`**（删除前的整树快照；此后旧 checkpoint 只能靠该 tag 取回）。
2. **同一提交内建新删旧**（`AGENTS.md` 迁移纪律）：拆 `recipe.py` 旧线 import 与元素、删 §1 的 13 个模块、
   删 §2 的 24 个 verify 脚本、清 `recipes.json` 与 `freeze_parity.json`（`obs_protocols.json` / anchors 按 §8-C 保留）、
   删 §3 的 11 条套件条目并把 `MAX_CHECKS` 收到 37、改 §2 的 7 个脚本。中间态不留红。
3. **独立提交**：给 `[42]` 加 `--live`，`SERIAL_BUDGET_S` 用 `--confirm-cost` 实测后钉。
4. **独立提交**：§4 的事项移动（9 移 `work/closed/2026/`、3 项改 scope）。
5. **验收**：按 §验收条件；其中 lizard2 三任务的构造须**对拍**（第 1 步之后、删除之前先存一次 cfg
   构造读数，删完复跑同一命令逐条比）—— 判据形状只在 §验收条件 一处写。
6. **收尾**：commit / push 走 `git-auto-sync` skill；`FILEMAP.md` 同步改；本项 `close_when` 判词回填。

### 7. 执行面核查（2026-10-09 执行时发现；计数以本节为准，补裁决以 §8 为准）

逐条核对清单时六处不符，判据均为代码内 `file:line`：

| # | 清单写法 | 实情 | 依据 |
|---|---|---|---|
| 1 | 套件删 12 条 | 删 **11** 条：`[22]` test_baseline_contract 是**混合范围**，条目保留、摘尾段 | 其 `contract` 主体是评测对照臂（`ablation_harness` 的 `metrics.py` / `baseline_frames.py` / `baseline_metrics.py` / `frame_semantics.json`，全部保留），只有尾段 `:1804` 牵 `test_baseline_mdp`、`:980` 牵 `parkour_mdp` allowlist |
| 2 | `teacher_smoke_runner.py` 判"留" | 必须**删** | 它经 `recipe_tasks` 解析 `LizardRoughTeacherEnvCfg_{VER}`（`:283-286`），这些类随注册面一起消失 |
| 3 | 裁决 C①（删 `obs_protocols.json` / anchors 的 lizard 条目） | **不可行**（阻塞） | `check_obs_protocol.py:460-483` 要求声明面任务集 == 所有 golden 的任务集，而 `obs_protocol_inventory.goldens()` 扫全部 `versions/**/cfg_lock.json`（**含边界内保留的 `versions/lizard/**`**）⇒ 删声明即红 |
| 4 | D① 只删两节代码 + 一个文件 | 连带 **3 条 contract** 必须重指 | `[1]` / `[2]` / `[12]` 的 `contract=` 指 `teacher_env_cfg.py`（`[2]` 还指 `freeze_parity.json`），而 `check_suite_shape` 要求 contract 是**存在的文件** |
| 5 | （清单未提，属压掉的改动面） | `check_cfg_lock` / `check_version_docs` **不需改** | `check_cfg_lock.py:650-701` 只遍历"有注册任务的行"，退休线零注册后其 golden 永不被读；`check_version_docs.py:79-87` 已内建 retired 判据 |
| 6 | `terrain_preflight` 判"改" | 判定成立，但**新来源不是 lizard2** | 它被保留的门 `test_terrain_geometry.py:111` import（`build_sub_terrain`）且被 `isaaclab-pretrain-check` skill 调用；lizard2 是平地（`terrain_generator=None`）⇒ 地形来源改建自保留的 `param_grid_terrain` + 冻结 v11 yaml（经保留的 `recipe_params` 读） |

**校正后的执行面计数**：删 **13 个模块**（清单写 17）/ 删 **24 个验证脚本** / 套件删 11 条、`MAX_CHECKS` 48→**37** / 删 **1 个声明文件**（`freeze_parity.json`）/ 台账 **9 项**（7 superseded + 2 cancelled）/ 改 4 个 tasks 模块 + 7 个验证脚本 + `recipes.json`。

**已落盘 vs 未落盘**：四个并行编辑块在中断时被撤销 ⇒ **代码零改动**；本次唯一落盘的是本记录与在办事项 frontmatter/`next`。

**补裁决已落定**：当时阻塞执行的 C / framework needle / component 归因三项已由用户拍板，当前选择见 §8；本段保留发现顺序，不再作为待裁决入口。

### 8. 补裁决（用户拍板：2026-10-09；本轮只回填，不执行代码清理）

依据：用户选择“采用推荐，只回填裁决”。实际变化是旧线退出注册、活跃线继续使用 stock MLP；不是引入新组件框架。三项均为现有边界内的本地依赖清理，不授权扩大架构重构。

#### C. 改为 C②：协议声明与 anchors 保留

- **采纳**：`obs_protocols.json`、`obs_protocol_anchors.json` 不动。golden 留存，声明保留其可读面；`check_recorded` 继续核对历史声明，`check_live` 沿用现有退休线未注册豁免（`rl_exp/tools/verify/check_obs_protocol.py:356-398`）。不增加 recorded 半边豁免。
- **未选方案**：C①删历史条目并加 retired 豁免。它也可实现，但要接受历史 manifest 降级、收窄 golden 覆盖并补相应破坏测试；与本次“保留历史 golden”边界相比，多改机制而没有活跃路径收益。
- **验证要求**：清理后 recorded 核对仍覆盖保留声明；live 核对只构造仍注册的任务。声明留存不等于承诺退休环境还能运行。

#### F. framework needle 按真实消费者处理，不按模块名一刀切

**采纳**：删除仅看守待删功能的 needle；保留活跃 PPO、观测传递、评测和 A① 续训机制仍依赖的 needle。不改框架 pin、fork patch 检查或 DR 语义判据。

| `rl_exp/tools/verify/framework_pin_check.py` 中的条目（编辑前行号） | 裁决与依据 |
|---|---|
| `:38-40` manager 内 `term_cfg.func` 实例替换 | 删这条 staged 跨 term 引用专属针；不解释成 ManagerTermBase/SIR 机制被删除，A① 的 SIR 实现及其测试照留 |
| `:79-81` `resolve_callable` 的冒号点路径分支 | 删 custom teacher 类装载专属针；lizard2 的 stock `MLPModel` 不是自定义 `module:Class`（框架 `rl_cfg.py:25`） |
| `:91-96` distillation 的 student / teacher 注入 | 两条均删；蒸馏消费者整体退出，不只删文字里提 `student_networks` 的那条 |
| `:97-99` `get_latent` | 删自定义 SplitEncoderModel 基类覆写契约的针；不是删除框架 MLP 方法 |
| `:85-90` PPO 的 actor / critic `resolve_callable` | **留并改消费者说明**为 lizard2 stock MLP；框架 `rsl_rl/algorithms/ppo.py:417-418` 仍经这两处构造 actor/critic |
| `:63-65` wrapper 的 TensorDict 传递 | **留并改说明**为活跃观测组 → stock MLP；网络换成 MLP 不意味着 wrapper 传递契约消失 |
| `:68-73` curriculum reset/clock；`:101-106` checkpoint infos | 留；A① 保留 `curriculum_state` 与续训依赖，不因旧 runner 删除而连带摘针 |

**未选方案**：整组保留原针，在说明里写“legacy”。它省下本轮改动，但仍将无人消费的自定义网络/蒸馏契约作为开训前框架阻塞项；不符合本次退出主路径的目标。

`offline_suite` 中 framework 条目的 `contract` 重指保留的 `rl_exp/tasks/agents/rsl_rl_ppo_cfg.py` 与 `rl_exp/tasks/curriculum_state.py`；其余两处死亡 contract 的重指仍按 §7-4，不能只改 needle 忘记声明文件路径。

**验证要求**：剩余针逐项能指出保留消费者；framework 检查与 suite shape 通过，lizard2 runner 构造对拍不漂移。不得靠删 actor/critic 针让检查变绿。

#### G. 授权 check_recipe_build 就地删 component 专属判据，不做通用化

**采纳**：删除 `COMPONENT_AUTHOR`、`ownership()`、`component_owns()`，以及 hard-B 中 wiring 反查旧 component ownership 和 `components.*` 作者专属分支（`rl_exp/tools/verify/check_recipe_build.py:312-319,401-423,490-505`）。同步去掉对 `test_component_ownership` 的依赖。

- 保留实际差异双向覆盖：未声明变化要红，无效声明也要红；保留 base 血统与 stock 核对、agent 差异核对。
- 保留逐 element 重放归因：每个声明作者集合必须与实际改变该路径的 writers 相等且非空。`components.*` 不能变成被默许的旧前缀，须落入作者不匹配失败。
- 保留 `wiring` 残余归因：只有无 element 写入时才允许归 wiring；不复制旧 ownership 表，不新增空表或插件式作者注册。
- lizard2 现有 v1/v2/v3 的 `diff.json` 作者均为 element，没有 `components.*` 作者，不需要重写冻结声明或刷新 golden。历史 lizard 的 component 声明原样保留，不再尝试构造已退出的旧线。
- 连带修 `attribution(..., line=recipe.MAIN_LINE)` 的默认值（`:191`）：删除 `MAIN_LINE` 后不能留下导入时即失败的引用；已有调用显式传 line 时去掉该旧默认即可。

**未选方案**：将旧 ownership 表搬到保留模块、只改 import。它能保持旧判据，但为不存在的组件复制 SSOT、继续用旧线 scene 名管 lizard2；不是本次清理所需的能力。

**验证要求**：执行时沿用最小 runnable check，逐例破坏 lizard2 的未声明路径、无效声明、错误作者（含伪造 `components.*`）以及把 element 路径错归 wiring，均须失败，恢复后通过；只看构造对拍或 golden 一致不足以证明归因判据仍成立。

#### 本轮落盘边界

只更新本清单与 `work/active/retired-family-code-prune.md` 的当前状态/下一步；上述代码、JSON、套件参数、tag 均未执行修改。三项决策阻塞解除，不代表清理实施或行为验收完成。

本轮文档提交前复核：`check_suite_banners.py`、`framework_pin_check.py --strict --self-test`、`check_dr_parity.py --strict`、`check_version_docs.py`、`check_work_docs.py`、`check_obs_layout.py` 与 `git diff --check` 通过。既有 fork 工作树改动警告、历史 tag 缺失警告与旧事项路径提示仍在，未修改；这些检查验证的是回填后的当前树，不是尚未实施的清理方案。

## 证据引用

- 评审：`acceptance/records/2026-10-09-repo-architecture-review.md`。
- 退休事实：`rl_exp/versions/lines.json`、`acceptance/records/2026-09-22-lizard-family-retirement.md`、
  `acceptance/records/2026-10-08-lizard2-v3-landing.md`。
- 依赖关系：§0–§2 的 `file:line` 逐条来自仓内 import 与消费者检索；
  套件条目 = `rl_exp/tools/verify/offline_suite.py:58-165`；事项 = `python rl_exp/tools/verify/check_work_docs.py --list`
  （本次读数：已迁移 28 项，其中本项自身不在待判之列 ⇒ 27 项待判）。

## 未覆盖边界

- 逐项判据是**静态依赖**（import / 注册 / contract 路径），未验证"删除后 lizard2 训练能否跑起来"——
  §6-5 的构造对拍只钉"配置面没被拆坏"，真跑归执行后的验收，不归本清单。
  删除**不是不可逆**：`lizard-final` tag 是取回路径；真正不可逆的是"没打 tag 就删"。
- 删除面**之外**但会被牵动的引用不在本项 scope，执行前须再扫一遍并另立或顺手处理：
  `ablation_harness` 里对旧线任务 id 的默认值（如 `baseline_eval.py` 的默认 task）与 `rl_exp/ue/*.json` 的导出引用。
- A① 的代价**未被任何设备度量**：保留 `teacher_mdp.py` 意味着旧线奖励 / 终止内核仍在主路径，
  每次 pre-commit 仍为它们付 import 与维护成本；"保留"省下的是本次的风险，不是长期成本。
  其去向须另立活跃事项（抽出 / 删除），否则这条会变成永久挂账。
- 未评估 `teacher_mdp.py` 内部可切分到什么粒度（选"抽出"时才需要，届时应另出拆分清单）。
- 未复核 `versions/lizard/**/cfg_lock.json` 与 golden 的逐条内容（那是闸门产物，只走 `check_cfg_lock.py` 的输出）。
