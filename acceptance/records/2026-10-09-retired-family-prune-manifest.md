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
| `rl_exp/versions/obs_protocols.json` | **删条目（裁决 C①）** | 删 `line: lizard/*` 条目（`:825-1014`）；6 条 lizard2 条目共用协议 `a25a8c39001b`（`:1015-1044`）保留 |
| `rl_exp/versions/obs_protocol_anchors.json` | **删条目（C①）** | anchors 只留被 lizard2 引用的协议摘要；历史 run 的 manifest 复读退化为"protocol 未声明"（`runrecord/manifest.py:171-183` 已优雅降级） |
| `rl_exp/versions/freeze_parity.json` | **删文件（裁决 D①）** | 唯一 subject 是 `lizard/main`（`:4-33`），两份手抄 cfg 都删 ⇒ 机制无被试对象 |
| `rl_exp/versions/lines.json` | 留 | 退休记录本身是历史事实 |
| `rl_exp/versions/lizard/**`（含 `cfg_lock.json`） | 留 | 边界 |
| `rl_exp/versions/lizard2/main/cfg_lock.json` | 留 | 活跃线 golden；删除后须用 `check_cfg_lock.py --diff` 复核未漂移 |
| `rl_exp/fork_patches/config_lizard___init__.py` | 留 | 只 `import rl_exp.tasks`，lizard2 也经它注册；改名会牵动部署链，收益为零 |
| `FILEMAP.md` 相关条目 | **改** | `rl_exp/tasks/` 节提到的 parkour / baseline 支线、`teacher_smoke*`、`_LINES_BUILT_ELSEWHERE` 等行 |
| `rl_exp/tools/verify/` 脚本 **删** | **删** | `teacher_smoke.py`、`teacher_smoke_v{3,5,6,8,11}.py`、`parkour_smoke.py`、`check_reward_v13.py`、`check_terminations_v14.py`、`test_v3_curriculum.py`、`test_v5_rewards.py`、`test_v12_noise.py`、`test_student_networks.py`、`test_baseline_mdp.py`、`test_baseline_isolation.py`、`test_component_ownership.py`、`test_teacher_networks.py`、`test_staged_curriculum.py`、`check_obs_layout.py`（裁决 B2①）、`pose_check.py`、`joint_check.py`、`position_check.py`、`smoke_test.py` |
| 同上 **改** | **改** | `check_recipe_build.py`（计数表 `:68-135` 删两条 lizard 行、留 `lizard2/main`）、`check_dr_parity.py`（删两节 freeze-parity 代码 + `load_subjects` 的 `SUBJECTS_PATH` 引用；留 asset contract 与 body swap 段）、`test_params_isolation.py`（`:20` 四处 import 全是被删模块）、`test_launcher.py`（`:39-41/:69/:186` 硬编码 `Lizard-Rough-v14` / `lizard/main`）、`terrain_preflight.py`（默认 `--version v4` 指 lizard，contract `teacher_env_cfg.py`） |
| 同上 **留**（含"随 A① 由删转留"的） | 留 | `test_joint_sir.py`、`test_v5_terrain_sir.py`、`teacher_smoke_runner.py`、`cstate_observer.py`（SIR 段保留 ⇒ 其断言对象仍在）、`test_resume_state.py`、`check_c_layer.py`、`lifecycle_entry_run.py`、`check_version_docs.py`（`:79-87` 已内建 retired 版本判据——退休线目录留在盘上即仍被覆盖，**不需改**） |

### 3. 离线套件 48 项：删 12 / 改 6 / 留 30

**删（12）**：`[4]` test_staged_curriculum、`[5]` test_teacher_networks、`[6]` test_student_networks、
`[7]` test_v3_curriculum、`[8]` check_obs_layout（B2①）、`[9]` test_v5_rewards、`[16]` test_v12_noise、
`[20]` check_reward_v13、`[21]` check_terminations_v14、`[22]` test_baseline_contract、
`[34]` test_baseline_isolation、`[37]` test_component_ownership。
理由同 §1/§2：被断言对象在删除面上（contract 直指 `versions/lizard/**/main_params.yaml` 或被删模块）。

**改（6）**：`[2]` check_dr_parity（D①）、`[12]` terrain_preflight（默认版本与 contract）、
`[33]` test_params_isolation（import）、`[40]` test_launcher（硬编码任务）、`[41]` check_recipe_build（计数表）、
`[42]` check_obs_protocol（**条目参数加 `--live`**：`:526-530` 支持 `--self-test` 与 `--live` 并存，
`:547` 的 live 半边补上被删的 `[8]` 的覆盖；同时清锚点与声明里 lizard 条目）。

**留（30）**：其余条目。点名几条易误判的：`[10]` test_v5_terrain_sir、`[11]` test_joint_sir、
`[18]` test_resume_state（A① 下 SIR 实现与冻结参数文档都在，断言对象未消失）、
`[14]` check_version_docs（retired 判据已内建）、`[39]` test_lifecycle_gate（用 `lines.json` 的
`lizard/parkour` 退休条目当样例，条目保留）、`[17]` check_pxr_leak 与 `[24]` check_configclass_fields
（走注册表，注册一删自动只剩 lizard2）、`[48]` check_leg_reachability（lizard2 资产）、
`[26]`/`[35]` cfg_lock / golden（按线遍历，退休线 lock 保留仍被盖）。

**连带修改**：
- `offline_suite.py:195` `MAX_CHECKS` 48 → **36**（棘轮常数必须同步收）。
- `offline_suite.py:196` `SERIAL_BUDGET_S = 175.0` 须 `--confirm-cost` **实测后**再钉，不按比例外推。
- **顺序约束（不可省）**：`MAX_CHECKS` 是硬上限，48 封顶 ⇒ 给 `[42]` 加 `--live`（新增一条检查）
  必须在 12 条删除**之后**的独立提交里做，否则套件瞬态 49 条、`_count_problem` 直接红（`offline_suite.py:314-326`）。

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
| C | `obs_protocols.json` / anchors 的 lizard 条目 | ①**删**（接受历史 manifest 复读降级） |
| D | `freeze_parity.json` 与 `check_dr_parity` 的 freeze-parity 段 | ①**删该机制**（与其唯一主体同进退），保留 asset contract / body swap 段 |
| E | 9 项判删事项的关闭词 | 按接管关系分开写：7 项 `superseded_by: retired-family-code-prune`；2 项（`row-sir-commanded-measurement-defect`、`deployment-delay-injection-dr`）`cancelled` |

### 6. 执行顺序（批准后照此走，每步都是独立可回滚的提交）

1. **打 tag `lizard-final`**（删除前的整树快照；此后旧 checkpoint 只能靠该 tag 取回）。
2. **同一提交内建新删旧**（`AGENTS.md` 迁移纪律）：拆 `recipe.py` 旧线 import 与元素、删 §1 的 17 个模块、
   删 §2 的 verify 脚本、清 `recipes.json` / `obs_protocols.json` / anchors / `freeze_parity.json`、
   删 §3 的 12 条套件条目并把 `MAX_CHECKS` 收到 36、改 §2 的 6 个脚本。中间态不留红。
3. **独立提交**：给 `[42]` 加 `--live`，`SERIAL_BUDGET_S` 用 `--confirm-cost` 实测后钉。
4. **独立提交**：§4 的事项移动（9 移 `work/closed/2026/`、3 项改 scope）。
5. **验收**：`run_offline_checks.bat` 全绿 + `Lizard2-Flat-v1/v2/v3` 注册与构造抽检 + `check_cfg_lock.py --diff` 无漂移。
6. **收尾**：commit / push 走 `git-auto-sync` skill；`FILEMAP.md` 同步改；本项 `close_when` 判词回填。

## 证据引用

- 评审：`acceptance/records/2026-10-09-repo-architecture-review.md`。
- 退休事实：`rl_exp/versions/lines.json`、`acceptance/records/2026-09-22-lizard-family-retirement.md`、
  `acceptance/records/2026-10-08-lizard2-v3-landing.md`。
- 依赖关系：§0–§2 的 `file:line` 逐条来自仓内 import 与消费者检索；
  套件条目 = `rl_exp/tools/verify/offline_suite.py:58-165`；事项 = `python rl_exp/tools/verify/check_work_docs.py --list`
  （本次读数：已迁移 28 项，其中本项自身不在待判之列 ⇒ 27 项待判）。

## 未覆盖边界

- 逐项判据是**静态依赖**（import / 注册 / contract 路径），未验证"删除后 lizard2 训练能否跑起来"——
  真跑归执行后的验收，不归本清单。
- 删除面**之外**但会被牵动的引用不在本项 scope，执行前须再扫一遍并另立或顺手处理：
  `ablation_harness` 里对旧线任务 id 的默认值（如 `baseline_eval.py` 的默认 task）与 `rl_exp/ue/*.json` 的导出引用。
- A① 的代价**未被任何设备度量**：保留 `teacher_mdp.py` 意味着旧线奖励 / 终止内核仍在主路径，
  每次 pre-commit 仍为它们付 import 与维护成本；"保留"省下的是本次的风险，不是长期成本。
  其去向须另立活跃事项（抽出 / 删除），否则这条会变成永久挂账。
- 未评估 `teacher_mdp.py` 内部可切分到什么粒度（选"抽出"时才需要，届时应另出拆分清单）。
- 未复核 `versions/lizard/**/cfg_lock.json` 与 golden 的逐条内容（那是闸门产物，只走 `check_cfg_lock.py` 的输出）。
