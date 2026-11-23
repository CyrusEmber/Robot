---
id: v7-workflow-hardening
title: v7 实验闭环止血、机体解耦与仓内清旧
scope: rl_exp, ablation_harness, work, acceptance, .codemaker, AGENTS.md, README.md
status: open
next: 执行 Batch 1（修复 verify 断链与训练/评测安全阀）。
close_when: 三批全部提交且验收全绿；改奖励只动 exp.py，改机体只动 robots/<body.py>；三目录 pytest 零收集错误；最终提交上的实跑评测写入验收记录。
---

## 目标与非目标

目标：
- **改奖励/超参** = 只改 1 份 `exp.py` → 跑 `train.cmd`。
- **改机体** = 只改 1 份 `robots/<body.py>`，零泄漏到 `exp.py` 和 `eval.py`。
- **仓内与 AI 视图干净** = 零失效 import、零冲突 Skill/文档、验收证据与最终代码提交一致。

非目标（防过度设计）：
- 不建 `RobotSpec` / `BaseExperiment` / `RobotRegistry` / YAML 继承 / 插件体系。
- 不加 `apply_nominal` 新钩子（当前 v7 无 DR 事件，等首个带 DR 的现役实验出现再按真实事件定义）。
- 不拆 `eval_cfg.yaml`、不重塑 `eval.json` 结构、不为字面搜索归零而改写现役局部变量名（如 `eval.py:656` 的 `cfg_lock`）。
- 不为测试单独维护第二份真实 USD 资产，也不重构历史诊断工具（只修复被退网误伤的导入）。

## Batch 1：止血与安全阀（先修真缺陷，不改核心结构）

### 1.1 分流 `verify/` 16 个收集错误
- **修仍在用的诊断链**：把 `rl_exp/tools/verify/check_leg_reachability.py:103` 依赖的 `_actuator_groups` / `_joint_owners` 就地内联，断开已删的 `check_dr_parity`，恢复 `check_self_collision.py`、`local_path_view.py`、`pose_target_solver.py` 及相关 10 个测试。
- **迁移现役测试再删死代码**：先把 `test_eval_record.py:1751` 的 `test_eval_failure_exit_status` 等现役行为测试迁入 `rl_exp/locomotion/tests/test_v7_experiment.py`；再删除绑死已退网 `recipe_tasks` / `check_cfg_lock` / `check_recipe_map` 的废弃文件（`rl_exp/tasks/` 旧配方模块、`rl_exp/tools/runrecord/{lifecycle,manifest,provenance,rebuild}.py`、`test_cfg_snapshot.py`、`test_resume_state.py`、`test_run_manifest.py`、`test_rebuild_gate.py`、`test_pxr_leak_gate.py`、`check_pxr_leak.py`、`test_eval_record.py` 等）。历史统一由 `archive/pre-refactor` tag 兜底。
- **断反向依赖**：把新主线唯一复用的 `sha256_file` / `sha256_bytes` / `git_run`（~30 行）迁入 `rl_exp/locomotion/train_record.py`，移除对 `rl_exp.tools.runrecord.binding` 的依赖。

### 1.2 修训练与评测安全阀
- **训练默认只训练，保留兼容别名**：`rl_exp/locomotion/train.py` 默认只训练，加 `--eval` 才串接 `eval.cmd`；保留 `--train-only` 作为已弃用 no-op 兼容别名并提示弃用。
- **修训练启动与 ckpt 定位**：
  - `run.mkdir(parents=True)` 移到 `AppLauncher(args)` 之前，避免目录冲突时白等 Kit 启动。
  - 保留子进程现有的最终 checkpoint 存在性检查（避免中间权重冒充最终结果）；父进程仅在 `--eval` 且训练子进程成功退出后，从本次独占的新 Run 目录按数字迭代号选最大的 `model_<整数>.pt`，无候选即失败（删 `model_{max_iterations - 1}.pt` 猜测）。
- **单轨推理配置漂移校验（选 A）**：
  - 新 Run 复用已有 `resolved_cfg.yaml`，在 `PLAY`、地形和 `nominal/robust` 覆写之前，对比训练口径下的 `scene.robot`、`actions`、`observations`、`sim.dt`、`decimation`，以及实际传给评测 wrapper 的 `runner.clip_actions`。
  - 保留已有资产校验和权重接口签名；源码哈希沿用现有来源记录，不参与拒绝判定。
  - 任一受检推理项不一致时默认拒绝（造环境前失败，不强行前移到 `AppLauncher` 之前，避免预启动阶段引入 `pxr` 泄漏）；仅在显式传 `--allow-drift` 或显式 `--exp` 时放行，并在指标和录像中记录实际来源。
  - 历史 `model_5999.pt` 无 `resolved_cfg.yaml`，沿用显式 `--exp` 和已有 sidecar，并记录配置比对不可用。
- **修观测签名（兼容现役权重）**：
  - `rl_exp/locomotion/train_record.py:145` 去掉字面名白名单 `{"joint_pos", "joint_vel"}`，改为覆盖两类项：显式带 `asset_cfg.joint_ids`/`joint_names` 的项，以及省略 `asset_cfg` 的关节类观测函数（保留默认全关节 `slice(None)` 语义，兼容 `model_5999.pt.interface.json`）。
- **修 `find_python.cmd`**：优先级改为 `RL_PYTHON` > `paths.yaml` > `VIRTUAL_ENV`；稳健解析 `paths.yaml`（容忍冒号前空格、单双引号、行尾 `#` 注释）。

### 1.3 补测试与前测
- `rl_exp/locomotion/tests/test_v7_experiment.py` 补：
  1. `train.py` 异常退出真实子进程测试，以及 `--train-only` / 默认纯训练 / `--eval`（含最大 `model_<整数>.pt` 选择与无候选失败）路径测试；
  2. 原始 `model_5999.pt.interface.json` sidecar 兼容加载测试 + 非标准项名（如 `joint_pos_legs`）同宽重排拒载测试；
  3. 漂移校验三例：只改一项 PD 默认拒绝、只改 `runner.clip_actions` 默认拒绝、只改奖励权重或注释正常通过；传 `--allow-drift` 放行并在指标和录像记录来源。
- Batch 1 完成后可跑一次 `eval.cmd` 作前测，不提前改写最终验收记录。

### Batch 1 验收
- 显式收集并执行三个目录：`pytest --collect-only` 与 `pytest` 覆盖 `rl_exp/locomotion/tests`、`rl_exp/tools/verify`、`rl_exp/tools/diagnose`，均 **0 error** 且全部通过。
- 漂移校验三例与 `--allow-drift` 全部命中预期。

## Batch 2：机体模块解耦（实现“改机体 = 只改机体”）

### 2.1 机体模块直接暴露物理常量与构造入口
在 `rl_exp/robots/lizard2_round_feet.py` 保留纯模块接口（不建 `RobotSpec` 类）：
- 资产与部位：`USD_PATH`, `URDF_PATH`, `ROOT_BODY_PRIM`（`"Geometry/base_link"`）, `BELLY_BODY`（`"base_link"`）, `CHEST_BODY`（`"chest_pitch"`）, `HEAD_BODY`（`"neck_pitch"`）, `HEAD_BODY_PRIM`（`"{ENV_REGEX_NS}/Robot/Geometry/neck_pitch"`）, `NOMINAL_WEIGHT_N`（`706.0`）。
- 动作与驱动：`LEG_ACTION_JOINTS`, `SPINE_ACTION_JOINTS`, `ACTION_JOINTS`, `ACTION_SCALE`, `ACTION_CLIP`（直接按关节映射，删掉 `lizard2_v7.py:40-53` 的 `joint.rsplit("_", 2)[1]` 字符串解析）。
- `make_robot_cfg()`：把 `lizard2_v7.py:194-204` 原地覆写的 `rigid_props` 6 个字段和默认 `actuator.friction` 收回机体构造。

### 2.2 实验调用期绑定与评测解耦
- `rl_exp/lizard2_v7.py` 写 `ROBOT = lizard2_round_feet`；`make_env_cfg()` 每次**调用时**从 `ROBOT` 读取资产、动作映射、身体部位和 `make_robot_cfg()`（取消 `_Scene.robot` / `_Actions` 导入期静态绑定），删掉模块级 `URDF_PATH` 转发。
- 触地终止策略留在 `exp.py`（如 `exp.py` 选择 `[ROBOT.BELLY_BODY, ROBOT.CHEST_BODY]`）：改“胸碰地是否终止”只动 `exp.py`，换胸部 link 名只动机体。
- `train.py` / `experiment_eval.py` 统一从 `exp.ROBOT.URDF_PATH` 取 URDF；`ablation_harness/eval.py:317` 从 `exp.ROBOT.ROOT_BODY_PRIM` 构造高度射线 prim 路径，删 `Geometry/base_link` 硬编码。
- `ablation_harness/components/dr_controller.py`：保留现有行为和已有模式测试，仅清掉指向旧 `play_utils.py` / `v12` 的失效注释。

### Batch 2 验收
- **离线换机体单测**：用假模块替换 `exp.ROBOT`（改关节名、腹/胸/头名称、根 prim 和动作映射），通过正式配置入口断言这些值全部传到 `scene.robot`、`actions`、传感器、奖励/终止和高度射线路径（验收结论为“换模块后配置绑定正确”；实际加载与运行由现有 v7 PPO 冒烟测试与最终评测覆盖）。
- `lizard2_v7` 的 `make_env_cfg()` 导出配置与重构前逐字段等价（零物理漂移）。

## Batch 3：清旧文档、对齐 AI 规则与最终验收

### 3.1 对齐 `.codemaker/` 技能与规则
- 重写或删改冲突技能：
  - `isaaclab-task-creator/SKILL.md` → 改为显式 `robots/<body.py>` + `rl_exp/<exp>.py` 指南（删 `gym.register`、`versions/<family>/vN/`、`<robot>_params.yaml`、`FAMILY.md`）。
  - `isaaclab-pretrain-check/SKILL.md`、`isaaclab-train-probe/SKILL.md` → 更新指向 `rl_exp/out/train/` 与现役入口，不再用则直接删除。
- 精简 `AGENTS.md` 与 `.codemaker/rules/isaaclab-development.mdc`：删不适用个人实验仓的上游公共库条款（如“破坏公开 API 须先弃用”、“`./isaaclab.sh -d`”）。

### 3.2 清理残余历史文档与死字段
- `rl_exp/versions/` 废元数据与旧 `FAMILY.md` 清理或标只读归档；`work/active/` 29 份旧工单按 `README.md` 收口（已结删、未完扁平化到 `work/<id>.md`）。
- 保留 `eval.json` 现有生效配置快照，仅删除 `ablation_harness/eval.py:573-575` 三个恒为 `None` 的死字段。

### 3.3 最终实跑与验收收尾（三批全部提交后执行）
- 锁定三批全部改动的最终源码提交，用同一 `model_5999.pt`、`locomotion_eval_v3` 和 `seed 123` 跑一次完整 `robust` 评测（该命令同时生成九段 nominal 平地录像）：
  1. 对照已有 robust 基线的指标、射线有效帧与九段录像，确认无行为回归；
  2. 更新 `acceptance/records/2026-11-23-v7-standalone-cutover.md` 指向最终验证的提交与输出目录。

### Batch 3 验收
- 现役入口不再导入已删除的配方模块；三目录 pytest 全绿（`rl_exp/locomotion/tests`、`rl_exp/tools/verify`、`rl_exp/tools/diagnose`）。
- `.codemaker/`、`README.md`、`AGENTS.md` 不再指引已退网配方流程（`recipes.json` / `lizard2_recipe` / `recipe_tasks` / `versions/<family>/vN`）。
- 验收记录中 `eval.json` 的 `git_rev_lizard` 与最终提交一致。
