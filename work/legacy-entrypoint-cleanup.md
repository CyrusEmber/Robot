---
id: legacy-entrypoint-cleanup
title: 清理旧配方退网后残留的代码、资产、本地产物与工单
scope: AGENTS.md, README.md, .gitignore, .codemaker, ablation_harness, rl_exp, work
status: in_progress
next: 按二审修订后的步骤执行：先解耦留存入口并开放系统临时目录校验；再逐文件生成字节级 manifest、校验可恢复性后执行本地归档与工作树清理；最后用 %TEMP% 完成全部离线、Blender 导出、USD 修复、列耦合复读、腿驱预检与 sim 验收，收口删除本单。
close_when: 仓内仅保留 v7 现役最小代码集、正式圆足资产、4 份锚定 YAML 协议、v7 产物与 10 份现役工单；rl_exp/out 仅保留在办目录、列耦合归档 ZIP 与 archive/pre-refactor，且明确禁止新增任何临时文件/临时目录；每一个被移除文件均经字节级 SHA-256 核验可从 git tag 或 local_archive 无损恢复；圆足 Blender 隔离导出、正式 USD 审计与 5 处惯量 --repair、协议全目录锚定扫描、列耦合四臂复读与 ZIP 恢复、腿驱实测关节序预检及 pytest -m sim 全部实跑通过；收尾后按 README 删除本单并同步 v7-workflow-hardening。
---

## 硬性目录纪律（新增）

- **`rl_exp/out/` 严禁新增任何临时文件或临时验证目录**：`rl_exp/out/` 只允许存放正式训练输出（`rl_exp/out/train/`）、按在办事项组织的正式留存诊断产物，以及 `rl_exp/out/archive/` 历史归档。
- **一次性操作、回归沙盒与隔离验证一律使用系统临时目录**（`%TEMP%` / `tempfile.TemporaryDirectory`），验证通过后立即清理自己的临时目录，不在仓根或 `rl_exp/out/` 留任何残余。

---

## 第一轮实现（`9318d5d` + `2d8ed76`）与方案审查结论

### 已生效项（保留）

- `rl_exp/tools/diagnose/lizard2_round_feet_probe.py` 已改从 `lizard2_v7.ROBOT` 读取 `URDF_PATH` 并将机体模块纳入 `bindings`。
- `ablation_harness/terrain_geometry.py` 的 `definition.module` 已改为 `__name__`，`test_terrain_geometry.py` 已补动态模块导入断言与协议 UTF-8 读取。
- 第一批 8 个脚本（`palm_preflight.py`、`head_ground_dwell_probe.py`、`convert_urdf.py`、`export_ue.py`、`migrate_joint_names_v8.py`、`_a0_paths.py`、`recipe_lines.py`、`test_recipe_lines.py`）已删除且可从 `archive/pre-refactor` 取回。

### 待解决的实现缺口与二审修正点

1. **大范围退网遗产与 `rl_exp/out/` 积压未清**：`rl_exp/tasks/`、`rl_exp/versions/`、`rl_exp/fork_patches/`、`rl_exp/archive/`、`rl_exp/ue/`、`rl_exp/docs/`、退役资产目录、`rl_exp/blender/` 旧目录、约 80 个旧 `diagnose/` 脚本、45 个旧 `verify/` 脚本、旧 `ablation_harness` 支线及 `rl_exp/out/` 下 479 个根级散落文件与约 140 个旧目录仍留在树上。
2. **圆足 Blender 导出的完整上游输入链（二审 P1）**：
   - `lizard2_round_feet_export.py` 校验 `SOURCE`（`lizard2_palm_spatial.urdf`，`FORMAL_SHA = e8896feb...`）及全部关联 OBJ 网格顶点，并通过 `skeleton02/build.json` → `lizard2_two_axis.json` 链式绑定 `lizard2_two_axis_20261029/candidate01/lizard2_two_axis.blend` 与 `lizard2_e_spatial_20261015/palm_spatial.blend`，同时锁定 `lizard2_round_feet_candidate.py` 的脚本哈希并从 `check_self_collision.py`、`generate_urdf.py` AST 抽取纯函数。不能把 `SOURCE` 换成圆足 URDF，也不能在未保留上游源件与哈希校验的前提下删源路径。
3. **协议锚表与 `protocols/` 全目录扫描（二审 P1）**：
   - `ablation_harness/protocol_anchors.json` 仍锚定拟删除的 6 份 `.json` 协议；若只删文件不同步迁出锚条目，`test_protocol_anchors_match_the_files_they_pin` 必败；且必须保留对 `protocols/` 全目录扫描以拦截未来未锚定的新协议。
4. **正式圆足 USD 审计与 `--repair` 契约差异（二审 P1）**：
   - `lizard2_round_feet_usd.py` 现有 CLI 面向含 `candidate.json`/`config.yaml`/`conversion.log` 且多一层子目录的转换候选目录，并绑定拟删除的 `palm_spatial_inertia.py`，不能直接传 `--export_dir rl_exp/lizard2_round_feet`。需提供正式资产只读 `audit(stage, tree)` 分支，并在 `%TEMP%` 候选沙盒中实测验证 5 处主轴惯量 `--repair`。
5. **在办列耦合事项的比较器与归档 ZIP（二审 P1）**：
   - `eval-column-coupling.md` 与 `eval-column-runtime-recovery.md` 仍依赖 `rl_exp/tools/diagnose/column_coupling_probe.py`（含 `archive/pre-refactor` 之后的退出状态与 `allow_unconfirmed` 修复）及 `rl_exp/out/archive/eval-column-coupling-*.zip` 两份原路径归档包。需保留该探针与两份 ZIP，并将探针的新采样 `capture()` 从已删 `gym.make('Lizard2-Flat-v3')` 切到 `lizard2_v7`。
6. **删除前字节级可恢复账本（二审 P1）**：
   - 部分拟移除的 Git 跟踪文件在 `archive/pre-refactor` 之后发生过路径移动或内容修改（如 `work/archive/2026/ARCH_PLAN.md`、扁平化后的退役 `work/*.md`、`rl_exp/ue/build_lizard_ue.py` 等），仅看 tag 文件名或迁移后看目录清空会漏掉增量字节。必须在删除前逐文件登记字节级 `sha256` 并反向核验恢复源后才允许删除。
7. **腿驱动基线的实测关节序来源与 `pytest` 0 收集盲区（二审 P2）**：
   - `lizard2_round_feet.py` 的 `ACTION_JOINTS` 是作者动作序，而 `lizard2_leg_drive_baseline.py` 需读取 PhysX 实测关节序（原存于 `versions/joint_order_runtime.json`）供推进与标定探针按列对齐；需迁入 `lizard2_round_feet.py` 并与正式 USD SHA-256 强绑定，验证 26 维同维重排必被拒绝。同时修复留存 `test_*.py` 无 `test_*` 函数导致 `pytest` 收集 0 条的假绿问题。

---

## 重定后的现役保留白名单

除下列白名单与根级基础文件（`README.md`、`AGENTS.md`、`train.cmd`、`eval.cmd`、`setup.bat`、`pytest.ini`、`paths.example.yaml`、`paths.yaml`、`hooks/pre-commit`、`.gitignore`、`.gitattributes`、`acceptance/records/`、`.codemaker/`）外，其余退网文件均经字节级可恢复核验后移出主树：

- **机体与实验核心**：
  - `rl_exp/__init__.py`、`rl_exp/lizard2_v7.py`
  - `rl_exp/robots/lizard2_round_feet.py`（含正式资产路径、动作序 `ACTION_JOINTS`、实测关节序 `MEASURED_JOINT_ORDER` 及绑定的 `MEASURED_USD_SHA256` / `MEASURED_URDF_SHA256`）
  - `rl_exp/lizard2_round_feet/`（`lizard2_round_feet.urdf`、`lizard2_round_feet.usda`、`meshes/`）
  - `rl_exp/locomotion/`（`find_python.cmd`、`rewards.py`、`terminations.py`、`train.py`、`train_record.py`、`tests/test_v7_experiment.py`）
- **现役资产与诊断最小集**：
  - `rl_exp/blender/scripts/`：`lizard2_round_feet_candidate.py`（保持原字节不变以匹配 `skeleton02/build.json` 绑定摘要）、`lizard2_round_feet_export.py`
  - `rl_exp/tools/pipeline/`：`flatten_usd.py`
  - `rl_exp/tools/runrecord/`：`binding.py`
  - `rl_exp/tools/trainlog/`：`probe_run.py`
  - `rl_exp/tools/diagnose/`（10 个文件）：`lizard2_two_axis_convert.py`、`lizard2_round_feet.py`、`lizard2_round_feet_usd.py`、`lizard2_round_feet_probe.py`、`lizard2_shank_use_probe.py`、`lizard2_leg_drive_baseline.py`、`lizard2_leg_drive_protocol.py`、`test_lizard2_leg_drive_baseline.py`、`test_lizard2_leg_drive_protocol.py`、`column_coupling_probe.py`
  - `rl_exp/tools/verify/`（8 个文件）：`test_lizard2_round_feet.py`、`test_eval_record.py`、`test_eval_frame_v2.py`、`test_recovery_parity.py`、`test_terrain_map.py`、`test_terrain_geometry.py`、`check_terrain_split_source.py`、`check_split_probe_wait.py`
- **现役评测与 v7 产物**：
  - `ablation_harness/` 代码与锚表：`evaluate.py`、`experiment_eval.py`、`eval.py`、`video_matrix.py`、`cfg_snapshot.py`、`host_paths.py`、`loco_judge.py`、`judge_semantics.json`、`metrics.py`、`protocol_anchors.json`（仅保留 4 条 `locomotion_eval_v1..v4.yaml` 锚点）、`record.py`、`suite_lock.py`、`suites.py`、`terrain_geometry.py`、`terrain_map.py`、`terrain_split_probe.py`、`components/`（`__init__.py`、`command_player.py`、`dr_controller.py`、`recovery.py`）
  - 冻结协议：`ablation_harness/protocols/locomotion_eval_v1.yaml` 至 `v4.yaml`
  - v7 产物：`ablation_harness/results/locomotion_eval_v3/provenance-v7-20261104-161257/`、`ablation_harness/videos/lizard2_v7_model5999_20261104_101635/`、`ablation_harness/videos/training-provenance-dependency-scope/`
- **`rl_exp/out/` 本地保留白名单（严禁新增临时文件/目录）**：
  - 历史归档与训练根：`archive/pre-refactor/`（统一本地归档根）、`archive/eval-column-coupling-probe-20261028-b-3e2f4ca9.zip`、`archive/eval-column-coupling-20261028-recorded-dependencies-20261030.zip`、`train/`（首次训练自动创建）
  - 圆足资产与支撑源件：`lizard2_round_feet/`（含 `skeleton02/`、`candidate01/`、`export03/`）、`lizard2_round_support/`
  - v7 切流与重构验证：`lizard2_v7_interface/`、`v7_play_review/`、`v7_refactor_eval/`、`v7_refactor_legacy_review_db3a64f2/`、`v7_refactor_smoke/`、`v7_lean_checks/`、`train_review_fault/`、`legacy-entrypoint-cleanup/`
  - 现役在办事项现场：`lizard2_shank_tilt/`、`lizard2_swing_pd_20261106_01/`、`lizard2_two_foot_20261117_05`、`_06`、`_10`、`_11`、`_12`、`_14`、`_15`、`eval-column-coupling/`、`runs/eval-column-coupling/`
- **现役未结工单（`work/` 仅留 10 份活跃项，本单完成后删除）**：
  - `v7-workflow-hardening.md`、`v7-short-run-post-train-evidence.md`、`lizard2-round-feet.md`、`lizard2-leg-drive-calibration.md`、`eval-command-observation-timing.md`、`eval-column-coupling.md`、`eval-column-runtime-recovery.md`、`exit-status-swallowed-by-app-close.md`、`joint-limit-shape-and-range-pass.md`、`large-monitor-skeleton-muscle-literature.md`

---

## 执行步骤

### 1. 留存工具解耦与契约加固（删前完成）

1. **开放系统临时目录、封堵 `rl_exp/out` 临时写入**：
   - `lizard2_round_feet_export.py` 与 `lizard2_two_axis_convert.py` 的输出/候选路径校验改为：**拒绝写入 `ROOT` 内除 `rl_exp/out/<事项目录>` 外的任何工作仓路径（防覆盖正式资产），同时允许写入仓外系统临时目录（`%TEMP%`）下的全新目录**，使一次性验证全部在 `%TEMP%` 中完成并清理。
2. **圆足导出链解耦与上游摘要绑定（对应二审 #1）**：
   - 将 `check_self_collision.py` 的 `{load_urdf, read_obj, chain_up, fk}` 与 `generate_urdf.py` 的 `{BALL_MESHES, build_bmesh}` 内联至 `lizard2_round_feet_export.py`（或共用至 `lizard2_leg_drive_baseline.py`），移除对这两个拟删脚本的 AST/文件绑定；**`lizard2_round_feet_candidate.py` 保持零字节改动**。
   - `lizard2_round_feet.py` 与 `lizard2_round_feet_export.py` 支持显式参数传入上游源路径（`--source_urdf`、`--skeleton`、`--two_axis_blend`、`--original_blend`），缺省定位到归档后的 `rl_exp/out/archive/pre-refactor/` 对应相对路径（`rl_exp/lizard2_palm_spatial/lizard2_palm_spatial.urdf` 及 `meshes/`、`rl_exp/out/lizard2_two_axis_20261029/candidate01/lizard2_two_axis.{blend,json}`、`rl_exp/out/lizard2_e_spatial_20261015/palm_spatial.blend`），继续严格校验 `FORMAL_SHA`、`SKELETON_SHA`、`build.json` 与 `lizard2_two_axis.json` 中的全部 `*_sha256` 及网格顶点一致性。
   - `test_lizard2_round_feet.py` 同时覆盖合成最小四足 URDF 的 `build_tree`/`validate_tree` 正负例与正式 `rl_exp/lizard2_round_feet/lizard2_round_feet.urdf` 结构校验。
3. **正式圆足 USD 审计与候选 `--repair`（对应二审 #3）**：
   - `lizard2_round_feet_usd.py:26-39` 现从 `palm_spatial_inertia.py` 抽源码 exec `{_rotation, _comparison, _principal_repair, repair_fresh_stage}`，改为直接写成本文件函数，并同步移除 `:234` 文件绑定表里的该项与过期的 `DEFAULT = .../export03`。`audit(stage, tree)` 已在 `:76`，只需补 CLI 分支，不重写。
   - 新增 `--formal_dir <dir>` 只读核验分支（输出报告可写 `%TEMP%`）：直接打开 `<dir>/lizard2_round_feet.usda` 与 `<dir>/lizard2_round_feet.urdf`，校验 `ComputeAllDependencies` 无未解析引用并运行 `audit(stage, tree)`。保留候选目录审计与 `--repair` 分支（允许 `%TEMP%` 下的隔离候选副本）。
4. **腿驱动基线实测关节序与纯函数内联（对应二审 #6）**：
   - 在 `rl_exp/robots/lizard2_round_feet.py` 写入 2026-11-03 实测的 26 维运行时关节序 `MEASURED_JOINT_ORDER` 以及正式资产摘要 `MEASURED_USD_SHA256`、`MEASURED_URDF_SHA256`。
   - 将 `_project`、`_rotation`、`_gravity_design`、`load_urdf`、`chain_up`、`fk` 内联至 `lizard2_leg_drive_baseline.py`（同步改掉 `:186`、`:621` 两处代码身份表里的 `palm_spatial_inertia.py` / `palm_spatial_tracking.py` 路径；`test_lizard2_leg_drive_baseline.py:16` 的 `_rotation` 改从本文件导入），将 `support_contact_window`、`tilt_cos` 内联至 `lizard2_shank_use_probe.py`，并把 `leg_drive_contact_views`（`:214`）对 `palm_spatial_runtime.pair_binding` 的调用按原样就地内联，断开 `palm_spatial_*`、`check_self_collision.py`、`diag_metrics.py` 与 `rl_exp/versions/`。
   - `lizard2_leg_drive_baseline.inputs()` 每次重算正式 USD/URDF 的 SHA-256 并与 `MEASURED_*_SHA256` 强校验，返回 `MEASURED_JOINT_ORDER`；补齐同维度（26 维）关节重排被拒绝的破坏测试。
5. **协议锚表同步与全目录扫描保留（对应二审 #2）**：
   - 从 `ablation_harness/protocol_anchors.json` 移出拟删的 6 条 `.json` 历史协议锚点，保留 `locomotion_eval_v1..v4.yaml` 4 条。
   - `test_eval_frame_v2.py` 移除 `baseline_metrics` 豁免后，完整保留 `test_protocol_anchors_match_the_files_they_pin` 与 `protocols/` 全目录扫描（任何未锚定的 `.json`/`.yaml` 落入 `protocols/` 立即判败），并新增临时未锚定协议触发失败的破坏断言。
   - `test_terrain_geometry.py` 内联 `build_sub_terrain`，`_V3_EVIDENCE` 改指保留的 v7 `Lizard2-Flat-v7_short_robust_seed123/terrain/geometry.json`。归档 `geometry.json` 里的 `definition.module` 只是历史字符串，没有任何代码按它 import（`:82` 校验的是内存中新生记录的模块名），删除 `rl_exp/tasks` 后无需映射表或垫片。
6. **列耦合探针保留与新采样解耦（对应二审 #4）**：
   - 保留 `rl_exp/tools/diagnose/column_coupling_probe.py`，其 `compare` 与 `selftest` 逻辑原封不动以保障历史批次与归档 ZIP 复读（`compare` 只认目录内 `capture_script.py` 快照，ZIP 的 `data/` 下已有该文件）；仅将 `capture()` 新运行采样从 `gym.make('Lizard2-Flat-v3')` 与 `rl_exp/tasks` 源码哈希切到 `rl_exp.lizard2_v7.make_env_cfg()` + `ManagerBasedRLEnv` 及现役源码目录哈希，并让 `source_hashes()` 的每个根目录先断言存在——目录不存在时 `rglob` 静默返回空集，会把覆盖缩水当通过。
7. **消除 `pytest` 0 收集假绿**：为 `test_recovery_parity.py`、`test_lizard2_leg_drive_baseline.py`、`test_lizard2_leg_drive_protocol.py` 补齐包路径导入与标准 `test_*` 函数入口。

### 2. 删除前逐文件字节级可恢复登记与迁移（对应二审 #5）

在系统临时目录 `%TEMP%` 运行一次性迁移器（先跑冲突拒绝与中断续跑两项夹具自测，通过后再操作真实目录，不在仓内留临时脚本）：

1. **全量枚举与字节摘要登记**：扫描白名单外所有拟移除文件（含 Git 跟踪文件、被 `.gitignore` 忽略文件及未跟踪文件，如 `rl_exp/out/` 旧目录与 479 个根散落文件、`rl_exp/tools/diagnose/out/`、非 v7 `ablation_harness/videos/`、`rl_exp/versions/**`、`work/archive/2026/ARCH_PLAN.md`、退役 `work/*.md`、`./ucode.elf` 等），逐文件记录 `rel_path`、`size`、`sha256`：
   - 仅当 `archive/pre-refactor:<rel_path>` 在 Git tag 中存在 **且 blob 的 SHA-256 与当前磁盘文件逐字节相等** 时，标为 `recovery_source = "git_tag:archive/pre-refactor"` 并记录 `blob_oid`；
   - 其余所有文件（包括未入 Git 的本地产物、tag 中路径不同的迁移文件如 `work/archive/2026/ARCH_PLAN.md`、以及 `archive/pre-refactor..HEAD` 期间发生过修改的文件）一律标为 `recovery_source = "local_archive"`，目标为 `rl_exp/out/archive/pre-refactor/<rel_path>`。
2. **无覆盖幂等复制/归档与写盘清单**：
   - 对 `local_archive` 项：若目标不存在则写入/移动；若目标已存在且 `size` + `sha256` 与源完全一致则视为前次中断已完成（幂等续跑）；若目标已存在但字节不同则立即中止报错，严禁覆盖。
   - 将完整条目原子写入 `rl_exp/out/archive/pre-refactor/manifest.json`（已存在旧清单时校验合并或分批后缀命名，禁止覆盖不同内容），并写明：同一 `rel_path` 在 tag 与本归档中字节可能不同时，本归档是 tag 之后的权威版本，恢复按条目的 `blob_oid`（tag 项）或 `local_path`（local_archive 项）执行，不按路径推断来源。
3. **删前反向核验（Verify-Before-Delete）**：
   - 重新读取 `manifest.json`，逐条核验：`git_tag` 项重算 `git cat-file blob archive/pre-refactor:<rel_path>` 的 SHA-256 必须等于原文件 `sha256`；`local_archive` 项重算目标磁盘文件 `size` 与 `sha256` 必须等于原文件。
   - **只有全部条目 100% 核验通过后**，才删除原位置文件与空目录（涵盖 `rl_exp/{tasks,versions,fork_patches,archive,ue,docs}`、6 个旧资产目录、`rl_exp/blender` 旧件、`rl_exp/tools/{archive,diagnose,verify,pipeline,trainlog}` 非白名单项、`ablation_harness` 非白名单代码/JSON 协议/非 v7 结果视频、`rl_exp/tools/diagnose/out`、`rl_exp/out` 非白名单项、`work/{closed,archive,active}` 及 15 份退役工单、`./ucode.elf`）。

### 3. 规则、配置、技能与留存工单同步

- **`AGENTS.md` 与 `README.md`**：
  - 在 `AGENTS.md` 明确写入“`rl_exp/out/` 禁止新增任何临时文件或临时验证目录，一次性操作与隔离验证一律使用系统临时目录并在用后清理”。
  - 在 `README.md` 更新 `lizard2_round_feet_usd.py --formal_dir` 正式资产核验命令与归档说明（Git 历史从 `archive/pre-refactor` tag 检出，未入库与增量归档位于 `rl_exp/out/archive/pre-refactor/`）。
  - 清掉与本次删除冲突的两句：`AGENTS.md:7` 的「历史工具进 `rl_exp/tools/archive/`」（该目录删除）、`README.md:39` 的「现有 UE 构建器和导出 JSON 保留旧资产口径」（`rl_exp/ue/build_lizard_ue.py` 删除）。
- **`.gitignore`**：移除已退网的 `rl_exp/versions/**`、`rl_exp/tools/diagnose/out/`、`rl_exp/lizard_urdf/`、`rl_exp/assets/lizard2_candidate/`、`lizard2_stance_candidate_*.png` 规则及过期注释。
- **`.codemaker/skills/`**：同步 `isaaclab-asset-pipeline/SKILL.md`、`references/blender_pipeline.md` 与 `isaaclab-pretrain-check/SKILL.md` 的路径、触发词和归档复跑说明。
- **留存的 10 份 `work/*.md`**：修正指向 `rl_exp/versions/*`、`work/active`、`work/closed/*` 及已退役工单/脚本的引用；`eval-column-coupling.md` 与 `eval-column-runtime-recovery.md` 保留对 `column_coupling_probe.py` 与 `rl_exp/out/archive/eval-column-coupling-*.zip` 的有效引用。

---

## 验收判据（全部临时输出入 `%TEMP%` 并在跑后清理）

1. **迁移可恢复性与异常续跑证明**：
   - `%TEMP%` 夹具实测证明“目标存在异字节文件时非零中止且零覆盖”与“中途停止后重跑可幂等续跑补齐”。
   - 复核 `rl_exp/out/archive/pre-refactor/manifest.json` 全条目字节摘要 100% 可从 `archive/pre-refactor` tag 或 `local_archive` 读回；`rl_exp/out/` 根下散落文件为 0、顶层仅剩白名单目录，`rl_exp/tools/diagnose/out/` 已不存在。
2. **圆足 Blender 隔离导出实跑**：
   - 在原位 `rl_exp/lizard2_palm_spatial`、`rl_exp/out/lizard2_two_axis_20261029`、`rl_exp/out/lizard2_e_spatial_20261015` 均不存在的状态下，以归档源件向 `%TEMP%\round-feet-export-*` 实跑 Blender `lizard2_round_feet_export.py` 退出 0，核验 URDF/网格与全部 SHA-256 绑定通过后清理 `%TEMP%` 目录。解耦后报告的绑定集不再含 `check_self_collision.py`、`generate_urdf.py`，与 `export03` 不同构：`export03` 只作历史证据留存，不复读其摘要。
3. **圆足 USD 正式只读审计与候选 `--repair` 实跑**：
   - 运行 `lizard2_round_feet_usd.py --formal_dir rl_exp/lizard2_round_feet --output %TEMP%\...` 通过（`pass=true`、`unresolved=[]`），正式资产目录零新增文件、摘要不变。
   - 在 `%TEMP%` 候选沙盒中实跑 `--repair`，确认精确修复 `REPAIR_LINKS` 五处惯量、修后 `audit` 通过且源 USD 字节摘要不变，随后清理沙盒。
4. **协议锚表与全目录扫描破坏测试**：
   - `test_eval_frame_v2.py` 全绿；验证向协议扫描注入未锚定协议文件时断言失败、移除后恢复通过。
5. **列耦合比较器与归档 ZIP 复读**：
   - 运行 `column_coupling_probe.py selftest` 通过；运行四臂 `compare rl_exp/out/runs/eval-column-coupling/probe-20261030-single-noise-min-c` 通过并复现 `stairs_20cm` 第 10 步分叉；按验收记录命令将 `rl_exp/out/archive/eval-column-coupling-probe-20261028-b-3e2f4ca9.zip` 解压至 `%TEMP%` 校验逐文件摘要并跑通快照 `selftest` + `compare`，随后清理 `%TEMP%`。
6. **腿驱动基线、默认与专项测试、圆足探针与 `sim` 冒烟**：
   - 离线运行 `lizard2_leg_drive_baseline.py` 退出 0；破坏测试验证 26 维同维关节重排与 USD 摘要漂移均被拒绝；以 `%TEMP%` 输出实跑 `lizard2_shank_use_probe.py --leg_drive_preflight` 验证运行时 PhysX 关节序与 `MEASURED_JOINT_ORDER` 逐位一致。
   - 默认 `pytest` 全绿；显式 `pytest rl_exp/tools/verify rl_exp/tools/diagnose` 逐文件执行条数均 `>= 1` 且全绿；`check_terrain_split_source.py` 与 `check_split_probe_wait.py` 退出 0；`pytest -m sim` 全绿。
7. **静态扫描与收尾闭环**：全仓现役代码/配置/文档/留存工单零断链与零已删模块引用（`acceptance/records/` 为历史记录，只读不改写，不计入本判据）；扫描须同时覆盖静态 import 与从记录中读出的模块名（如 `geometry.json` 的 `definition.module`），只跑静态 import 不算证据。`rl_exp/out/` 无任何新增临时文件，`git diff --check` 通过；完成后更新 `work/v7-workflow-hardening.md` 与验收记录，并按 `README.md` 删除本工单。
