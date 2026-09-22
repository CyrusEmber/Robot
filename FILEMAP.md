# FILEMAP —— 目录导航（给下一个 AI / 新协作者）

> **本文件是目录导航，不是文件登记册。** 它回答"这块东西住哪、干什么、哪条路不能靠看树推出来"，
> 不逐个登记文件。由此三条边界：
>
> - 新增一个普通文件、一条事项或一批验收记录 **都不需要改本文件**；
> - 新增版本 **只需满足既有目录登记**（`versions\<family>\<line>\vN\` 四件套 + `base.json` + FAMILY 版本史行 + 本文件版本行）；
> - 只有"入口 / 闸门 / 契约 SSOT / 看树推不出来的坑"这四类才值得加行。
>
> 读图顺序：`README.md`（仓定位 + 新机器摆位）→ 本文件（目录职责与入口）→
> `rl_exp\versions\lizard\PLAN.md`（意图与挂账）→ `rl_exp\versions\lizard\FAMILY.md`（已成立事实）。
> 守则：`AGENTS.md`（本仓 + IsaacLab 上游）；方法论文档见 `.codemaker\skills\tool\`。

## 主要目录职责

| 目录 / 文件 | 职责 |
|---|---|
| `\`（仓根） | 入口脚本 + 主机路径模板 + 仓级文档；代码家是 git 仓，不是 IsaacLab 树 |
| `setup.bat` | 新机器摆位一键（幂等）：写 venv `.pth` / 建 `config\lizard\` 拷 fork shim / 逐份应用 `fork_patches\*.patch` / 按本机生成 `paths.yaml` / 设 `core.hooksPath`。纯 ASCII（`.bat` 按控制台代码页读，非 ASCII 带崩解析）；补丁打不上 `[FAIL]` 非零退出 |
| `paths.example.yaml` | 主机路径模板（`isaac_root` + `python`）；每台机器 copy 成 `paths.yaml`（不入库） |
| `README.md` / `AGENTS.md` | 仓定位与摆位步骤 / 工作与 IsaacLab 守则 |
| `ARCH_PLAN.md` | 架构改造的判据与实现形态（**只写当时证据，不写当前状态**）；加粗状态词与"覆盖文档里的闸门判词"由 `check_version_docs.py` 扫 |
| `work\` | 在办事项（`active\`，一项一文件）与关闭归档（`closed\<year>\`）；形状闸 `check_work_docs.py`，发现命令见 `AGENTS.md` |
| `FILEMAP.md` | 本文件 = 目录导航（见文首边界） |
| `rl_exp\` | 任务包（自包含核心）；`import rl_exp` 经 venv `.pth` 可达 |
| `rl_exp\tasks\` | gym 任务包 = 训练代码本体：家族线 + `parkour` / `baseline` 支线；注册表在 `__init__.py` |
| `rl_exp\versions\` | 声明与冻结层：`<family>\<line>\` 路线层 + `vN\` 版本目录 + 配方 diff 目录 + 全仓声明 JSON + 各线 `cfg_lock.json` |
| `rl_exp\blender\` | DCC 源件 + 一次性 Blender 脚本（几何 / 绑骨 / 重命名的唯一出处） |
| `rl_exp\assets\` / `rl_exp\meshes\` | 训练用 USD 资产 / URDF 网格（`versions\lizard\meshes\` 为版本侧网格，与仓根 `rl_exp\meshes\` 同构） |
| `rl_exp\tools\` | 工具按类分目录：`pipeline\` 资产与 UE 导出 / `verify\` 离线闸门与套件 / `trainlog\` 训练日志 / `runrecord\` 运行记录 / `diagnose\` 诊断 / `archive\` 考古 |
| `rl_exp\docs\pitfalls.md` | 踩坑登记（P00x 编号）—— 闸门"为什么存在"写在编号条目里 |
| `rl_exp\fork_patches\` | IsaacLab 树侧的 fork 补丁存档 + 注册 shim 副本 |
| `rl_exp\ue\` | UE 侧 JSON 与编辑器脚本 |
| `ablation_harness\` | 评测系统（`HARNESS.md` 是它的文档 SSOT）：协议 / 套件 / 指标 / 调度 / 组件 |
| `ablation_harness\results\` | 跑分落盘（记录即数据，随仓提交；每个 run 目录一份 `terrain\geometry.json`） |
| `acceptance\records\` | 验收记录（扁平一层，文件名即索引） |
| `hooks\pre-commit` | 提交钩子（`core.hooksPath` 由 `setup.bat` 设） |
| `papers\` | 论文存档 + `INDEX.md` |
| `.codemaker\skills\tool\` | 本项目方法论 skill（任务创建 / 资产管线 / 评测 / 训练巡检 / git 纪律） |

## 关键入口

### 启动与运行

| 入口 | 作用 |
|---|---|
| `ablation_harness\host_paths.py` | **机器本地路径的唯一读者**（`eval` / 调度 / `run_offline_checks.bat` / `hooks\pre-commit` / `framework_pin_check` 共用）；纯 stdlib、不 import `rl_exp`、**无 PATH 兜底**（宁缺不猜），`--check` 取不到即 exit 1 |
| `rl_exp\tools\verify\run_offline_checks.bat` | 离线全套一键；本体只剩主机 python 引导（`paths.yaml` → `host_paths.py`），额外参数原样透传（`--jobs` / `--verbose` / `--list` / `--self-test`） |
| `rl_exp\tools\verify\offline_suite.py` | **离线清单的唯一来源 + 并行调度器**（fail-fast、每项独立进程与 temp、全绿才打一行判词，字面见 runner 末行）。改 tasks 或 harness 后、commit 前必跑；规则见 `OFFLINE_CHECKS.md` |
| `ablation_harness\eval.py` | 统一评测 runner：task + checkpoint + 协议 + 模式 → `eval.json`（另写 `terrain\geometry.json`） |
| `ablation_harness\run_ablation.py` | 消融调度：spec yaml → 串行 train + eval → 汇总表，断点续跑；`--by-terrain` 出逐地形长表 |
| `ablation_harness\video_matrix.py` | 录像矩阵（**相机，不是判官**）：`--speeds` × `--terrains` 想怎么组合都行，默认最高速 × 配方平地 → 每格一段 mp4 + `matrix.json`（命令区间 / 是否在配方区间内 / 帧数 / 峰值与净位移 / 复位 / 相机）；地形挡位取套件命名列（单列板）；**不产 verdict、不写 `results/`**，产物落 `ablation_harness\videos\`（gitignore） |
| `rl_exp\tools\launch_recipe.py` | 新启动器：目录 → 身份 → 配置侧绑定 → golden 对比 → 生命周期判定 → 记录；默认只检查（不起 sim），`--launch` 交回 fork trainer |
| `ablation_harness\protocols\locomotion_eval_v*.yaml` | 评测协议契约（时间线 / 帧定义 / 阈值 / 套件 / DR）：v1/v2 冻结封存，v3 换真起伏套件 `lizard_suite_v2`；**改动 = 新建 v4，v1/v2/v3 不得混表**。套件定义在 `ablation_harness\suites.py` |
| `rl_exp\tools\runrecord\` | 运行记录层（**训练路径实际调用**，不是人手跑的入口）：`manifest.py` T0/T1 记录 + `--verify` 两维度 / `lifecycle.py` 启动生命周期判定（退休线拒新训与续训）/ `binding.py` 摘要与 rev 拼写的唯一家（stdlib 栈底）/ `provenance.py` 代码来源规则 / `rebuild.py` 恢复演练（按需） |
| `rl_exp\tools\trainlog\probe_run.py` | 训练中巡检（只读 tfevents，秒级，不起仿真）：进度 / ETA / 趋势 / 终止计数 / 课程值 / 告警 |
| `rl_exp\tools\trainlog\dump_tb.py` | TB 事件 → `vN\tb_scalars.csv`（按 tag 抽样、**保首尾**；`--csv_in` 重抽样不需 tensorboard） |
| `rl_exp\tools\verify\view_terrain.py` | GUI 看机器人站**指定版本的真实地形**（每 env 头向箭头 + 接触点探针 vs 碰撞栈预算） |
| `rl_exp\tools\verify\terrain_preflight.py` | 开训前地形预检：离线生成全部子地形 + 粗糙度 + PNG 预览 + 几何摘要。它是**离线预览的回归基线**，不是真跑所站地形的证据（真跑几何由 `terrain_split_probe` 采集归档） |
| `rl_exp\tools\pipeline\export_ue.py` | SSOT → UE 工件（盲部署前置）；**没有实测关节序就拒绝导出**（不写文件） |

### 闸门与反证（`rl_exp\tools\verify\`；`check_*` = 闸门本体，`test_*` = 它的反证）

| 闸门 | 看守什么 |
|---|---|
| `check_version_docs.py` | 版本文档完备 + 血统闸：每版本目录四件套（PLAN/NOTES/`<line>_params.yaml`/asset_lock）+ `base.json` 边合法 + FAMILY 版本史行 + 本文件版本行；另扫覆盖文档的闸门判词与 `ARCH_PLAN.md` 加粗状态词 |
| `check_cfg_lock.py` | 配方 golden 闸门（format 3 分两层：框架组合块 + 线自己的条目）；`--update` 必须带 `--line` + `--reason`；反证 `test_cfg_lock_gate.py` |
| `check_recipe_build.py` | 构建硬闸：冻结 golden 逐字段比 + 覆盖钉数 + 逐步归属 |
| `check_recipe_map.py` | 配方身份闸门：`ast` 读注册表（不 import），声明的 `env_cfg_entry`/`agent_entry` 与注册逐字一致；`--bind-config` 构造实例读 `params_version`；反证 `test_recipe_map_gate.py` |
| `check_recipe_registry.py` | 实验线生命周期闸门（`lines.json` 二值 `status`，闸门无时钟）；反证 `test_recipe_registry_gate.py` |
| `check_obs_protocol.py` / `obs_protocol_live.py` | 协议闸门（自洽 + 已审锚点 + golden 逐任务 + `--live` 实构比对 + 覆盖）；live 侧起 env 读真实 manager 的组序/项序/宽度/shape。反证 `test_obs_protocol_gate.py` |
| `check_obs_layout.py` | obs 布局静态门（读 `obs_protocols.json`，不自带副本） |
| `check_dr_parity.py` | 契约漂移闸门（`--strict` 即 CI）：DR 行静态对比 / 两份 DR 事件名清单同步 / 全部 `*_PLAY` 接线 / 资产结构契约 / 资产锁比对 |
| `check_configclass_fields.py` | 字段面闸门：`params_version` 一类的声明必须真的进 `to_dict`（类属性读不到即红）；反证 `test_configclass_fields_gate.py` |
| `check_pxr_leak.py` | 按注册入口**构造** cfg 并断言 `pxr` 不进 `sys.modules`（防 Kit 启动被毒化，见 `rl_exp\docs\pitfalls.md` P001/P003/P004）；反证 `test_pxr_leak_gate.py` |
| `check_split_probe_wait.py` | P005：构造期等框架 import 的载体不许是 `sys.meta_path` finder（导入在第一个给出 spec 的 finder 处停止） |
| `check_joint_layout.py` | 关节布局硬闸（球头必 +X / 天线必 −X / 腿序）+ 单关节注入驱动读数 |
| `check_reward_v13.py` / `check_terminations_v14.py` | 版本专项静态闸：跟踪核替换与冻结不动 / 翻覆判据 + dwell 累积语义 + 惩罚算术 + 接线 |
| `check_record_bindings.py` / `check_golden_frozen.py` / `check_terrain_split_source.py` | 记录绑定原语单源看守（四条签名 + 反证）/ 冻结点与拆地来源的来源检查 |
| `check_suite_shape.py` / `check_suite_banners.py` | 套件形状（清单唯一来源、不许未声明 spawn 解释器）与 `.bat` 横幅转义卫生（未转义 `<`/`>` 在 bat 里是重定向） |
| `framework_pin_check.py` | 框架 pin：IsaacLab 内部符号 + 已验证 commit + `fork_patches\*.patch` 存档校验（按序应用到 pristine 副本再逐字节比） |
| `recipe_lines.py` | **线 / 版本目录发现规则的唯一入口**（`discover()`）；上面四个版本相关闸门全走它，零份 / 多份 / 名字不符一律抛错不跳过 |
| `cfg_snapshot.py` | 配置快照序列化器（顺序敏感 / 浮点位级 / callable 点路径 / MISSING 按类型 / 路径相对化 / 不落对象地址）；反证 `test_cfg_snapshot.py` |
| `teacher_smoke_runner.py` + `teacher_smoke_v*.py` | 冒烟协议与 `SMOKE_SPEC` 版本表（代码级真源）+ 薄壳；**开新版本 = 加表行 + 薄壳，不复制整文件** |
| `baseline_runtime.py` / `tools\diagnose\diag_metrics.py` | 共用运行时读点（实际关节/材质/终止注入）与验收量测纯函数（与奖励同帧坐标系）——防"验收与奖励不同坐标系"复发 |
| `test_*.py`（约 45 份） | 各闸门的反证与契约单测，清单在 `offline_suite.py`；命名与被看守对象同名 |

## 不直观的布局关系（看树推不出来、最容易搞错的）

- **IsaacLab 源码树里只有 1 个文件属于本仓**：共享 shim `<ROOT>\config\lizard\__init__.py`（副本 `rl_exp\fork_patches\config_lizard___init__.py`），只负责 `import isaaclab_tasks` 时注册任务。`<ROOT>` = `paths.yaml` 的 `isaac_root`（持 `scripts/` 与 `logs/`）。
- **旧 junction 摆位已死**：`E:\IsaacLab\rl_exp` 已删、`E:\IsaacLab\ablation_harness` 已废（只准 `rmdir` 摘链接）。机器本地路径一律问 `host_paths.py`，不要在代码里把"调用路径的爹"当配置。
- **主线就是家族本身**：`rl_exp\versions\<family>\<line>\vN\`。主线 = `versions\lizard\main\vN\`，支线多一层（`versions\lizard\parkour\v1\`、`versions\lizard\baseline\v1\`）。家族级文档（`FAMILY.md` / `PLAN.md` / `OBS.md` / `REWARDS.md` / `ACCEPTANCE.md`）落在 `versions\lizard\`，**不在 `main\` 里**。
- **`versions\lizard\main\` 里不全是版本目录**：`rough-v0\`、`curriculum-flat-v0\`、`curriculum-rough-v0\` 是**配方 diff 目录**（`base.json` 指该配方的母本 + `diff.json` 声明相对母本的差异），既不是 `vN\` 也不受版本四件套闸门管辖；配方锁在 `main\cfg_lock.json`，开发态参数在 `main\main_params.yaml`。
- **开发态参数与冻结参数是两份**：开发态 `versions\<family>\<line>\<line>_params.yaml`，冻结副本 `vN\<line>_params.yaml`；跑冻结版**永远不读**开发态（`recipe_params.frozen_only`）。`vN\asset_lock.json` 补"冻结 yaml 只钉路径不钉内容"这个洞（资产原地换代 → 常驻任务 id 复现被破坏）。
- **机器件不是文档**：`versions\recipes.json`（配方身份映射，身份写出来不推出来）/ `obs_protocols.json`（obs 协议声明，key 就是自身内容摘要）/ `obs_protocol_anchors.json`（已审摘要与宽度，只读不写）/ `lines.json`（实验线生命周期，二值 `status`；资产契约只查 `active` 线）/ `cfg_baselines.json`（框架组合基线，全仓一份）/ `freeze_parity.json`（冻结期对拍对象：哪两个 cfg 文件互为手工副本 + 已审差异，闸门不认识任何家族名）/ `<线>\cfg_lock.json`（配方 golden，**一线一份**，`--update --line` 只能写自己那份）。这些是闸门读的契约；`cfg_lock.json` **不写进 `vN\`**。
- **`joint_order` 有两种，别混**：配方里的 `joint_order` = URDF 树序（`export_ue.py` 拿它断 URDF）；obs/action 真正按索引取值的是 `versions\joint_order_runtime.json` 的**实测序**（**按资产键**，`--pin --reason` 才写），只有 `obs_protocol.py` 读它。UE 工件同时输出两者并注明用途，读它只有一处。
- **记录与证据落点**：跑分 → `ablation_harness\results\<协议>\<group>\<run_id>\`（外加组内 `summary.csv` / `terrains.csv`）；真跑证据 → `rl_exp\versions\lizard\verify_logs\`；版本结果回填 → 各 `vN\NOTES.md`；验收记录 → `acceptance\records\`（通过数/通过率的唯一归属是 `rl_exp\versions\lizard\ACCEPTANCE.md`）；训练 log / ckpt 在 `<ROOT>\logs\`（不入库）。
- **线之间的隔离是硬约束**：`tasks\recipe_factory.py` 是跨线共用的类构造器但**不 import 任何具体线**，每条线由自己的模块调它（`recipe_tasks.py` 按名按需生成可注册类，`_LINES_BUILT_ELSEWHERE`）；baseline 线刻意复制自己的奖励核而不共享 `teacher_mdp.py`。看守：`test_baseline_isolation.py`。
- **生成的注册类名是 ckpt 载荷的一部分**：`recipe_tasks.py` 沿用被替换的版本类名（载荷记 `type(cfg).__name__` 并参与 resume 身份核验），改名会让跨路径续训被拒。
- **续训状态的硬失败边界**：任务可声明 `REQUIRES_CURRICULUM_STATE`，缺载荷 / 缺 slot / 未覆盖 stateful term / hook 未装**训练前终止**；`--drop_curriculum_state`（旧 `--weights_only` 为别名）是唯一显式降级；状态只从 rank 0 写，多 GPU 不在保证范围。
- **`fork_patches\*.patch` 有顺序与格式纪律**：按文件名序应用，`train_seed_rng.patch` 排最后（其 hunk 行号指"全部补丁打完后"）；一份存档里同一个文件只能有**一个** `diff --git` 段——追加第二段会让 `git apply` 报 `wrong type`，正确动作是**新起一份存档**。
- **`blender\` 的输入只有一个**：`generate_urdf.py` / `fix_bones.py` / `rotate_rig.py` / `rename_flip_v8.py` 一律以 `lizard_stance.blend` 为输入；`lizard.blend` 只在"从原始模型重做几何/绑骨/贴图"时才用得上，**管线不读它**（同目录 `lizard.glb` 未入库，是它的导出件）。
- **工具目录按类别分**：新脚本先决定属于 `verify\`（闸门 / 套件，进离线清单）还是 `diagnose\`（人看的读数）；一次性历史脚本进 `archive\`，不要留在主路径上。
- **`teacher_mdp.py` 一个模块承载 v3–v13 的增量段**（v3 包 / v5 行 SIR / v11 联合粒子 / v12 噪声 / v13 跟踪核），按版本段落读；"只增不改"是纪律。

## 版本目录（每目录一行；本表同时是 versioning.mdc A-5 的 FILEMAP 登记行）

> 行里只写"这个版本是什么"（身份 / 版本级机制差异），不写进度与判决——那些归 `FAMILY.md` 版本史、各 `vN\NOTES.md` 与 `ACCEPTANCE.md`。
> 新增版本 = 建 `versions\<family>\<line>\vN\`（四件套 + `base.json`）+ 补 FAMILY 版本史行 + 在本表加一行。

| 目录 | 身份 |
|---|---|
| `rl_exp\versions\lizard\main\v0\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v1\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v2\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v3\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v4\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v5\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v6\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v7\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v8\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v9\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v10\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v11\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v12\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v13\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v14\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\main\v15\` | 冻结配方（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\parkour\` | 支线版本包（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\parkour\v1\` | 支线版本包（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\baseline\` | 支线版本包（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\baseline\v1\` | 支线版本包（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard\baseline\v2\` | 支线版本包（身份与教训见 `versions\lizard\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard2\main\` | 版本线目录（身份与教训见 `versions\lizard2\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `rl_exp\versions\lizard2\main\v1\` | 冻结配方（身份与教训见 `versions\lizard2\FAMILY.md` 版本史；本表只给路径与冻结状态） |
| `<线>\vN\PLAN.md` | 版本级计划（目的 / 假设 / 决策点 / 验收线）；结果回填走 NOTES |
| `<线>\vN\NOTES.md` | 版本文档：目的 / 参数 diff / 训练命令 / 结果回填 |
| `<线>\vN\<line>_params.yaml` | 冻结参数副本：跑冻结版只读这份，资产内容由 `asset_lock.json` 钉 |
| `<线>\vN\tb_scalars.csv` | 抽样入库的训练曲线（全量留机器本地 `.full.csv`，不入库） |

## 历史包袱提示（仍然改变今天决策的那些）

- `tools\verify\smoke_test.py` / `pose_check.py` 2026-08-31 修过陈旧 bug（动作维度 / 旧命名）——跑挂先查命名是否又变。
- `blender\build_rig.py`、`tools\archive\patch_*.py`、`tools\pipeline\migrate_joint_names_v8.py` 是早期一次性脚本（仅考古 / 迁移出处，别照抄改主路径）。
- `ablation_harness\results\...\summary.csv` 里 2026-08-28 那两行的 `energy_per_m_j` **无效**（energy 修复前少乘 step_dt，虚高 ~50×）；其余列有效，energy 列重跑后才有意义。
- 套件口径：`lizard_suite_v1` 的 rough 两列实为均匀抬升平板（`noise_range` 单值使 `np.random.choice` 退化），拿它当起伏地形会误判；真起伏从 `lizard_suite_v2` + 协议 v3 起，v1/v2/v3 **不得混表**。
- 旧趴窝 checkpoint 在 `E:\IsaacLab\logs\rsl_rl\lizard_rough\2026-08-28_14-08-22`（家族 run，不在仓里）。
