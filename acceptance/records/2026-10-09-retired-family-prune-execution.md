# 退休线清理：执行记录（2026-10-09）

## 适用范围

`work/active/retired-family-code-prune.md` 的执行落盘记录：三条退休线（`lizard/main`、`lizard/parkour`、
`lizard/baseline`）的代码、任务注册、离线检查与在办事项移出主路径。清单与裁决见
`acceptance/records/2026-10-09-retired-family-prune-manifest.md`（本记录只写落盘事实与偏离，不复述判据）。

## 验收条件

- 删除面与清单 §7 的校正计数一致，且每处删除与"依赖它的注册/检查/声明"在同一变更内（`AGENTS.md` 迁移纪律）。
- 判据形状：`run_offline_checks.bat` 全绿 + lizard2 任务能注册与构造 + `check_cfg_lock` / `check_recipe_map` 无漂移。
- 偏离清单处必须逐条写明依据，不静默吸收。

## 结果

### 删除（38 个文件）

| 面 | 数量 | 内容 |
|---|---|---|
| `rl_exp/tasks/` | 13 | `baseline_env_cfg` / `baseline_mdp` / `baseline_recipe` / `components` / `curriculum_env_cfg` / `lizard_env_cfg` / `parkour_env_cfg` / `parkour_mdp` / `rough_env_cfg` / `staged_curriculum` / `student_networks` / `teacher_env_cfg` / `teacher_networks` |
| `rl_exp/tools/verify/` | 24 | `check_obs_layout` / `check_reward_v13` / `check_terminations_v14` / `teacher_smoke` + `teacher_smoke_runner` + `teacher_smoke_v{3,5,6,8,11}` / `parkour_smoke` / `pose_check` / `joint_check` / `position_check` / `smoke_test` / `test_baseline_mdp` / `test_baseline_isolation` / `test_component_ownership` / `test_staged_curriculum` / `test_student_networks` / `test_teacher_networks` / `test_v12_noise` / `test_v3_curriculum` / `test_v5_rewards` |
| 声明 | 1 | `rl_exp/versions/freeze_parity.json`（裁决 D①：机制与其唯一主体同进退） |

### 改造（规模与语义）

| 文件 | 前 → 后 | 说明 |
|---|---|---|
| `rl_exp/tasks/recipe.py` | 966 → 329 行 | 旧线 import/元素/`RECIPES`/`MAIN_LINE`/`BASELINE_*` 全删；只留 `LINES["lizard2/main"]` 路由与构建机制；10 个构造函数的 `line=` 默认值由 `MAIN_LINE` 改成 `LIZARD2_LINE`；`apply_into` 的元素来源改读 `lizard2_recipe.ELEMENTS` |
| `rl_exp/tasks/__init__.py` | 44 → 6 条注册 | 实测旧线注册 **38** 条（清单写 39，见下） |
| `rl_exp/tasks/recipe_tasks.py` | — | `_LINES_BUILT_ELSEWHERE = {"lizard2/main"}`，baseline 分支删除 |
| `rl_exp/tasks/agents/rsl_rl_ppo_cfg.py` | → 84 行 / 3 类 | `Lizard2PPORunnerCfg` 改继承 `RslRlOnPolicyRunnerCfg`，字段逐字段搬运；`to_dict()` 与改前快照逐字节一致（MRO 已变，配置值未变） |
| `rl_exp/versions/recipes.json` | 45 → 6 条 recipe 键 / 6 条 task 映射 | 只留 lizard2 |
| `rl_exp/tools/verify/offline_suite.py` | 48 → **37** 条 | 删 11 条、`MAX_CHECKS` 48→37、3 条 contract 重指（`[1]`→`rsl_rl_ppo_cfg` + `curriculum_state`，按 §8-F；`[2]`→`play_utils`+`dr_controller`；`[12]`→`param_grid_terrain`） |
| `check_dr_parity.py` | 6 检查 → 6 检查 | freeze-parity 两节与 `load_subjects` 删除并重编号（原 docstring 的 "Six checks" 名不副实，现与实际一致） |
| `terrain_preflight.py` | 地形来源替换 | 从 `teacher_env_cfg.TEACHER_TERRAINS_CFG*` 改为冻结 v11 `terrain_grid` 经 `param_grid_terrain`；`build_sub_terrain` 语义不动（`test_terrain_geometry` 依赖） |
| `framework_pin_check.py` | −5 needle | 依赖本次消失的针删净（`staged_curriculum` / `teacher_networks` / `student_networks` 展开为 5 条）；依赖 `teacher_mdp` 的针保留 |
| `hooks/pre-commit` | 换闸门 | 原调已删的 `check_obs_layout.py` ⇒ 改调 `check_obs_protocol.py`（声明半边恒跑，有 venv 时加 `--live`） |
| 文档 | — | `FILEMAP.md` / `README.md` / `OFFLINE_CHECKS.md` / `rl_exp/docs/pitfalls.md` P004 / `versions/lizard2/FAMILY.md` / `declare_family.py` 的 FAMILY 模板按现状改准 |

### 台账

- 关闭 9 项（`work/closed/2026/`）：7 项 `superseded`（`superseded_by: retired-family-code-prune`）+ 2 项 `cancelled`
  （`row-sir-commanded-measurement-defect`、`deployment-delay-injection-dr`）。
- 改 scope/landing 3 项：`asset-tree-per-family`、`verified-rebuild-rating`、`obs-three-tables-merge`。
- 活跃项 28 → 19。为让台账闸门绿，另修 7 个**已关闭**事项的悬空指针（5 处 landing + 2 处 `depends_on`）。
- 本项自身按 `close_when` 判 `done`。

### 判词（可复读）

```
rl_exp\tools\verify\run_offline_checks.bat
ALL_OFFLINE_CHECKS_PASSED (37/37 in 45.9s, wave 219s/informational, jobs=6)
```

余下各门的判词（同一轮输出内）：`PIN_CHECK_OK` / `PARITY_OK` / `WORK_DOCS_OK` / `VERSION_DOCS_OK` /
`CFG_LOCK_GATE_OK` / `RECIPE_BUILD_OK (6 task(s) field-identical to the frozen golden; 115 declared difference(s))` /
`check_pxr_leak: OK (... 6 tasks constructed)` / `LIFECYCLE_STARTUP_OK` / `test_resume_state: 28 passed` /
`CONFIGCLASS_FIELDS_OK` / `declaration matches the goldens`。

### 与清单的偏离（逐条）

| # | 清单 §7 | 实际 | 依据 |
|---|---|---|---|
| 1 | 旧线注册 39 条 | **38** 条 | 全表实测（8 Velocity + 12 版本 ×2 + 2 Parkour + 4 Baseline）；清单多算 1 |
| 2 | 删 13 个模块 | 同 | §7 已校正（清单正文曾有"17"笔误） |
| 3 | 未列 | 另删 `rl_exp/tools/diagnose/play_fast_task.py` | 它 subclass 已删的 `LizardRoughTeacherEnvCfg_V8_PLAY`，本体是旧线专有配方 ⇒ 已不可能运行 |
| 4 | 未列 | 另改 4 处"守卫主体" | 删除使它们的探针主体消失：`test_cfg_snapshot.py`、`test_run_manifest.py`、`test_recipe_map_gate.py` 的夹具、`test_lifecycle_gate.py` 的真实索引用例（改用活跃线上已退休的**版本** v1 作真实拒绝主体）、`check_configclass_fields.py` 及其 falsifier 的 `TARGET`/`PLAY_TARGET` |
| 5 | 未列 | `test_resume_state.py` 的 4 个 teacher env cfg 主体 | 改用本文件自建的 stand-in 类 + 已保留的 `test_joint_sir`/`test_v5_terrain_sir` 工厂；`28 passed`，覆盖点（roundtrip / c_k 指纹 / 缺证降级 / hard-abort / hook save）保住 |
| 6 | 未列 | `hooks/pre-commit` 换闸门 | 不换则**提交即红**；该 hook 是 `AGENTS.md` 的提交截止线 |
| 7 | 4 个提交（记录 / 代码 / `--live` / 台账） | **3 个** | 依赖闭包迫使代码+声明+台账同提交，否则 checkout 单提交即红；"每步独立可回滚"要求每个提交在 checkout 上是绿的 |

## 证据引用

- 清单与裁决：`acceptance/records/2026-10-09-retired-family-prune-manifest.md`（§5 裁决、§7 执行面核查）。
- 结构评审：`acceptance/records/2026-10-09-repo-architecture-review.md`。
- 退休事实：`rl_exp/versions/lines.json`、`acceptance/records/2026-09-22-lizard-family-retirement.md`、
  `acceptance/records/2026-10-08-lizard2-v3-landing.md`。
- 判词：上节复读命令（`run_offline_checks.bat`）。

## 未覆盖边界

- **未真跑训练/仿真**：本次只证明"能注册、能构造、能过 gate"（`check_pxr_leak` 构造 6 个任务、
  `LAUNCHER_OK`、`RECIPE_BUILD_OK`）。lizard2 v3 起训是另一件事，其读数不归本记录。
- **A① 的挂账未消化**：`teacher_mdp.py` 保留 ⇒ 旧线奖励/终止内核仍在主路径，每次 pre-commit 仍为它们付
  import 成本。"抽取或删除"须另立活跃事项，否则本条变成永久挂账。
- 以下**未处理**、逐条都需要一次独立决定（不在本项 scope 或未获授权）：
  > 已由 `work/closed/2026/stale-entrypoints-after-prune.md` 接管并于 2026-10-10 处置（默认值改写、
  > 两个死工具删除、`_b3`/`_a0` 归档、skill 入口改准），落盘事实见
  > `acceptance/records/2026-10-10-stale-entrypoints-after-prune.md`。下列各条保留的是 2026-10-09 那天的读数。
  - `rl_exp/tools/verify/_b3_remove_version_classes.py`：一次性脚本，仍指向已删模块（按仓规本应提交前删）。
  - `rl_exp/tools/diagnose/play_keyboard_task.py`：docstring 与 `_self_check` 默认仍指 `Lizard-Rough-Play-v8`，
    `KEY_SENSITIVITY` 按 v8 的 yaml 取值（lizard2 窗口 0–3 m/s，需重定才能改指）。
  - 若干 diagnose / verify 工具的 CLI 默认仍指旧任务 id（`diagnose_nan` / `diagnose_support` /
    `direction_probe` / `obs_protocol_live` / `baseline_probe` / `check_contact_ownership` /
    `check_joint_layout` / `reset_check` / `view_terrain` / `time_foot_rings` / `terrain_split_env_run` /
    `test_eval_record` / `test_rebuild_gate` 等）——不 import 已删模块，故不红，但默认值已不可运行。
  - `.codemaker/skills/` 下的 `isaaclab-task-creator`（把 `staged_curriculum.py`、`teacher_smoke.py`、
    `smoke_test.py` 当现成入口）与 `isaaclab-asset-pipeline`（`position_check` / `joint_check`）已失真。
  - `versions/lizard/**` 的历史文档按边界不动，其中"真源是 `recipe.py` 的配方表"一类句子与活跃家族口径
    已不一致（退休家族自己的记录，故意留）。
- `obs_protocols.json` / `obs_protocol_anchors.json` 按裁决 C② 未动：`check_obs_protocol.check_recorded`
  要求声明面的任务集覆盖**全部** golden，而 golden 按边界保留 ⇒ 声明面不能单方面清空。
- `SERIAL_BUDGET_S`：**本次随条数棘轮一起移动**（175 → **160**），依据是移动后重新 `--confirm-cost` 实测的
  quiet **146s**/37 条；口径与读数写进 `rl_exp/tools/verify/OFFLINE_CHECKS.md` §3.2，`offline_suite.py:175` 的注释同步。
