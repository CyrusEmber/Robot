# 2026-09-20 三节：基线线独立化收尾 · 摘要对 EOL 敏感（已修）· 固定窗口评测入口

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的三节同日追加（2026-09-20）：

| 旧节 | 主题 |
|---|---|
| §追加（2026-09-20）基线线独立化收尾 · 闸门主体集合不再靠命名空间 | 把"本线不 import 其它线的 cfg 或 mdp"从一句话变成机器可查的契约 + 收掉四条 [P1] 敞口 |
| §追加（2026-09-20）摘要对 EOL 敏感 · 仓库缺 EOL 声明（已修） | 修一条**非本批**的既有缺陷（由上一节的 worktree 验证暴露） |
| §追加（2026-09-20）基线线收口 · 固定窗口评测入口 + 开训前工具真跑 | 清上一节的"遗留"两项 + 基线线开训前工具链在**真实 Kit** 上重跑 |

**本记录内部的前后作废关系（读结论以此为准，被作废的旧句保留作留痕）**：

- **第一节的「观察（非本批，留给资产锁的维护者）」是同一条缺陷的**当日观察**，第二节把它**修掉**
  （根因是"仓库没有 EOL 政策"，不是锁算错）**—— 第二节的读数（两 worktree 各 `46/46`）为准。
- **第一节的「遗留」两项被第三节清掉**：`--confirm-cost` 串行复核已跑（并把 `SERIAL_BUDGET_S` 口径里的
  "45 条"改为 46）；`FILEMAP.md` 两行随并发批次落地。
- **第三节的 `SERIAL_BUDGET_S` 读数与第二节的读数不同**（第二节 quiet **154s**、第三节 quiet **140s**）：
  同一常量两次读数差 10%，两节都记在案，**都不足以支撑收紧**；常量不动。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管（本记录横跨 **45 → 46** 条，`MAX_CHECKS` 45→46 见第一节）⇒ 各节的读数
**只在当日 commit 上成立**。

## 验收条件

### 第一节的前提

`versions/lizard/baseline/PLAN.md` §与其它线的边界 写着"本线不 import 其它线的 cfg 或 mdp"——
本节把它从一句话变成机器可查的契约，并收掉随之暴露的四条敞口（2026-09-20 评审提出）。

### 第二节：两个真实 worktree 的对照

含 EOL 政策与不含政策的两侧对照：默认（`core.autocrlf=true`）与 `core.autocrlf=false` 各 checkout 一次，
跑同一套套件、并逐条比关键文件字节。

### 第三节：固定窗口评分协议

协议 `baseline_flat_v1.json`（20 s、命令固定、`plane`）：
每 env 只计**首回合**、终止帧计入；首回合结束后**冻结位置**（重生位移不计）、剩余帧按速度 0 补账
（分母恒为完整 20 s）；位移投到**初始 yaw**；存活率只认纯 `time_out`；同时失败+超时判失败。

## 结果

### 基线线独立化收尾 · 闸门主体集合不再靠命名空间（2026-09-20）

| 件 | 作用 |
|---|---|
| `tasks\recipe_factory.py`（新） | 构类机制**一处家**：`__post_init__` 链 + ClassVar 注解 + `configclass`，主线与基线共用 |
| `tasks\baseline_recipe.py`（新） | 基线的 10 个元素 + `BASELINE_RECIPES` + **本线自己的** `recipe_class`，不 import 主线 |
| `tasks\recipe_tasks.py` | 解析改为**按名、按需**（模块 `__getattr__`），并按 `recipes.json` 的 `line` 分发到"本线自己的构造器" |
| `tasks\recipe.py` | 元素表改为 `**baseline_recipe.ELEMENTS` 合并（基线元素只存一份，不再第二份 name→函数表） |

**四条 [P1] 的落点与实测**

**① 类身份：缓存不被批量生成覆盖。** 原 `generate()` 为**所有**线建类再 `globals().update()`，于是
"先解析基线、再解析主线"会把基线类换成由 `recipe.recipe_class` 造的另一个对象。改法不是 `setdefault`
（那只防覆盖，不消灭第二条构造路径），而是把批量生成整个删掉：`class_for()` 只建**被请求的那一个**类，
且基线线由 `baseline_recipe.recipe_class` 建（`_LINES_BUILT_ELSEWHERE`）。`__getattr__` 只在名字缺席时
被调用 ⇒ 首建即定。实测（`test_baseline_isolation.py` 三阶段）：`blocked` 阶段两名字各解析一次、二次读
同一对象、注册表字符串与模块属性同一对象；`baseline→main` 阶段主线解析后基线两名字 `is` 不变；
`fresh module` **反序**阶段用看门器包住 `recipe.recipe_class`，断言它**一次都没接到基线线的活**
（`built == [("lizard/main", …)]`）。

**② `[23]` 主体集合不得静默缩水。** 该闸门原本只扫 `vars(module)`；惰性化后生成类不再落在命名空间里
⇒ 主体从 39 掉到 7、反证器 `KeyError`。改法：保留扫描，再**逐个 `getattr` 身份映射声明的入口**
（解不出记红、**落不进** `SKIP module`；解出但无 `params_version` 字段也记红），同名时注册表解析出的类
胜出；另加**双向核对**：`recipe_tasks.__all__` 与 `recipes.json` 筛出的本模块入口逐名比对（缺名、多名、
两名共占一个类名都红）。反证器改为：目标行缺失时打印"它仍是一个注册任务的类 ⇒ 主体集合缩了"并返回 1，
不再裸 `KeyError` 代替诊断。实测 **39 类**、`CONFIGCLASS_FIELDS_OK`、7 条反证全 FIRES。

**③ 隔离封锁器自证。** 手写 6 个禁名只能挡住想得到的 import。改为**默认拒绝** `rl_exp.tasks.*`、显式
放行 10 个模块并**逐条写允许理由**；白名单不从本次观测自动生成，而是与"实际加载集"**相等**断言（用了
不需要的权限即红）。自证走真实 `importlib.import_module("rl_exp.tasks.recipe")` 并匹配**封锁器专属异常
类** `Blocked`（不是任意 `ImportError` —— 依赖缺失也是 `ImportError`）。入口断言：`__all__` 34 名全可
解析、`import *` 成功、parkour 两名**不被本模块认领**而其注册入口照旧解析（`ParkourClimbEnvCfg v1`；
入口过滤用 `partition(":")` 精确比模块名）。**反证（评审点名的那条）**：临时给 `baseline_recipe.py` 加
`teacher_mdp` ⇒ **rc 1**、`Blocked: BASELINE_ISOLATION_BLOCKED: rl_exp.tasks.teacher_mdp is not part of
the baseline's closure`；字节复原后 rc 0 `BASELINE_ISOLATION_OK`。

**④ 条数棘轮。** 新增独立检查有理由：它断言"解析基线任务不导入主线"，在任何已 import 过主线的进程里
**不可测**（`rl_exp.tasks.recipe` 已在 `sys.modules`，封锁器无从失效）—— 进程边界即被测对象。净增 1
（并发批次把 `test_acceptance_metrics.py` 那条与基线三份断言合并进 `test_baseline_contract.py`）。
`MAX_CHECKS` 45→46、条目与 §6 看守行**随并发批次的 `offline_suite.py` / `OFFLINE_CHECKS.md` 提交**
（本批不持有这两个文件；工作树里已就位）。

**小去重两处**（评审补的隐患）：`baseline_recipe.ELEMENTS` 原本只收 `elements` ⇒ 将来加 PLAY 专属元素必
`KeyError`，现同时收 `play_elements`；`params_version` 改为读表 `entry.get("params_version", version)`
（保留显式 `None` 的语义）。

**独立验证**

| 场景 | 结果 |
|---|---|
| 干净 worktree（`03b4ee2` + 本批 7 个源文件，**无**并发批次任何文件） | **45/45**（`[23] CONFIGCLASS_FIELDS_OK`、`[39] RECIPE_BUILD_OK` 34 任务逐字段同 golden） |
| 主树（本批 + 并发批次） | **46/46、零跳过**；`[40]` 硬 A 本批**第一次真被验过**：34 任务逐字段同 golden、355 条差异声明 |

**边界（不得据本节宣称）**

- 本节只证"基线任务的解析不拉主线、且类身份与导入顺序无关"，**不证基线配方本身能训、能达标**。
- 白名单的理由是人工审查产物；`= 实际加载集` 只挡**死权限**，挡不住"新加的模块恰好也被放行"。
- 干净 worktree 那次是**内容级**验证（复制文件进树），**不是** `git checkout` 出来的独立克隆。

**观察（非本批，留给资产锁的维护者）**：干净 checkout 下 `[2] check_dr_parity --strict` 报 4 条
asset-lock 漂移（`baseline/v1`、`main/v9`、`main/v11`、`main/v12` 的 `*_params.yaml`）：这四个文件在主树干
是 **LF**、checkout 得 **CRLF**，而锁按主树字节记录；换 `core.autocrlf=false` checkout 则反过来 770 条漂移
（锁多数按 CRLF 记录）。即锁摘要**对 EOL 敏感**。本批未改这些文件，改用"按主机字节覆盖这四个文件"
对齐环境后复核。→ **该观察由下一节修掉**。

**遗留**

- `--confirm-cost` 串行复核（并把 `SERIAL_BUDGET_S` 口径里的"45 条"改为 46）**待树静**：并发写手在场时
  串行计时测的是 CPU 争用，不是成本。
- `FILEMAP.md` 两行（`recipe_factory.py` / `baseline_recipe.py`）与 `recipe_tasks.py` 旧行（"为每条已声明
  配方生成一个类" → 按需）随并发批次；`baseline_env_cfg.py` 指向 `rl_exp.tasks.baseline_recipe` 的一行
  docstring 已在并发批次的 diff 中。

→ 两项均由下下节（固定窗口评测入口）清掉。

### 摘要对 EOL 敏感 · 仓库缺 EOL 声明（已修，2026-09-20）

**性质**：修一条**非本批**的既有缺陷 —— 由上一节的 worktree 验证暴露出来的，**不是**那一节自己造成的。

**症状**：干净 checkout 下 `[2] check_dr_parity --strict` 报 4 条 asset-lock 漂移（`baseline/v1`、
`main/v9`、`main/v11`、`main/v12` 的 `*_params.yaml`）；把**同一个 commit** 以 `core.autocrlf=false`
checkout 则报 ~770 条（18 套锁 × 43 文件，几乎全漂）；`[35]` 的 4 条冻结摘要同理。

**根因（不是锁算错，是仓库没有 EOL 政策）**：`.gitattributes` 此前只钉 `*.patch text eol=lf`（同一课
的历史教训，注里写得清清楚楚）。实测 `git ls-files --eol`：**索引 527 个文本文件全是 LF**，工作树却是
`207 lf / 311 crlf / 9 mixed` —— 同一份 blob，每台机器 checkout 出不同字节。而所有摘要
（`binding.sha256_file`）都是对**工作树字节**取的，于是锁记录的是"这台机器的行尾"。文本类里
`.obj`（每套锁 40 条、共 720 条条目）全 CRLF，`.usda`/`.urdf`/14 个 `*_params.yaml` 全 CRLF；二进制的
`.stl` 有 54 个恰好含 `0D0A` —— 正是"文本按 LF、二进制按字节"这条政策的缺口。

**改法**（原生机制优先：不新增启发式、不改摘要函数）：

1. `.gitattributes` 增 `* text=auto eol=lf` + `*.bat`/`*.cmd text eol=crlf` + `*.stl`/`*.blend`/`*.pt -text`；
   工作树按政策重物化 —— `checkout-index` 不套属性转换，故用"删后 `git checkout --`"，覆盖被摘要的文本类
   233 个文件（0 残留、无空文件）。
2. **写手也要钉 LF**（否则重录一次又是平台相关）：`check_cfg_lock.py` 的两处（line lock 与
   `cfg_baselines.json`）与 `check_dr_parity.py` 的 `--update-locks` 改为 `newline="\n"`。
3. 重录 18 套 asset-lock 与 `[35]` 的 4 条 FROZEN。

**关键性质**：**索引没变一个字节** —— `git status` 对那 233 个文件仍报 unchanged（EOL 是 checkout 形态，
不是内容），所以这次重录只是把"锁到的字节"对齐到"每台机器现在都会 checkout 出的那种"，不是改历史。

**验证**（同一 commit `7acc84f`，两个真实 worktree）：

| checkout | 结果 |
|---|---|
| 默认（`core.autocrlf=true`）| `46/46`，`[2] PARITY_OK`、`[34] GOLDEN_FROZEN_OK` |
| `core.autocrlf=false` | `46/46`，同上 |

且两个 worktree 的关键文件字节**逐条相同**（`main_params.yaml` / `.obj` / `main/cfg_lock.json` /
`asset_lock.json` 均 0 CRLF；`run_offline_checks.bat` 两侧都 29 CRLF）。原症状（4 条与 ~770 条）在两种
checkout 下都不再出现。写手修复的直接证据：删掉 parkour 锁再跑一次 `--update-locks`，新写的锁
**0 CRLF / 88 LF**。

**成本口径补测**：同日 `--confirm-cost`（46 条）quiet **154s**（wave 205s），落在 ratified `SERIAL_BUDGET_S
= 175s` 内且未越过收紧线 `0.8 × 175 = 140` ⇒ 常量不动。同一批的另一次读数是 140s：两次相差 10%，
说明"安静主机"在不同时刻不等价，单次读数不足以支撑收紧（口径与两次读数均记在 `OFFLINE_CHECKS.md`）。

**边界**：

- ① 非被摘要类（`.py`/`.md`/`.csv`/`.log` 等）在本机仍是旧行尾，随下次 checkout 归一，本次**只保证
  被摘要的类**（`.obj`/`.usda`/`.urdf`/`.yaml`/`.json`）与 `.bat` 的两侧一致；
- ② 政策让"工作树与索引一致"，**不改任何已存 blob**，跨平台一致性来自 checkout 而非重写历史；
- ③ 本条的绿只证"摘要可移植"，**不证资产本身未被改动** —— 资产是否被改动仍由锁的内容判断
  （本次 18 套锁里除行尾外无一字节变化）。

**提交归属**：`.gitattributes` · 18 套 `asset_lock.json` · `check_golden_frozen.py`（4 条 FROZEN + 原因）·
`check_cfg_lock.py` / `check_dr_parity.py`（写手钉 LF）· `OFFLINE_CHECKS.md` + `offline_suite.py`（成本读数）。

### 基线线收口 · 固定窗口评测入口 + 开训前工具真跑（2026-09-20）

**性质**：清上一节的"遗留"两项（`--confirm-cost` 串行复核、`FILEMAP` 的两行），并把基线线的开训前
工具链在**真实 Kit** 上重跑。改动面 = 新增 `ablation_harness/baseline_eval.py` + `baseline_metrics.py` +
`protocols/baseline_flat_v1.json`、`rl_exp/tools/verify/baseline_runtime.py` + `test_baseline_contract.py` +
`test_baseline_mdp.py`；改 `baseline_probe.py`、`baseline_mdp.py`/`rsl_rl_ppo_cfg.py`/`baseline_env_cfg.py`（口径）、
`offline_suite.py` + `OFFLINE_CHECKS.md`（45 → **46** 条）、`FILEMAP.md`、`baseline/*` 与 `v1/NOTES.md`。

**落地**

| 件 | 内容 |
|---|---|
| 固定窗口评分 | 协议 `baseline_flat_v1.json`（20 s、命令固定、`plane`）+ `BaselineWindow`：每 env 只计**首回合**、终止帧计入；首回合结束后**冻结位置**（重生位移不计）、剩余帧按速度 0 补账（分母恒为完整 20 s）；位移投到**初始 yaw**；存活率只认纯 `time_out`；同时失败+超时判失败 |
| 分报告 | `deterministic` / `sampled` 分文件（`--output` 已存在即拒写），零动作标 `smoke_only`，不得当训练验收 |
| 探针加齿 | 三项**真实**检查取代声明侧检查：实际关节复位（读活值比默认）、live 逐 shape 摩擦（缺读取接口 = 失败而非静默通过）、终止注入（接触历史与回合时钟注进**活的管理器**再还原） |
| 接触注入目标 | 取 `sensor.body_names.index("base_link")`，**独立于被检查的 term**——`base_contact` 若错绑到脚，注 `base_link` 就不触发 ⇒ 报错而不是跟着一起错 |
| 套件 | `[21]` 换成 `test_baseline_contract.py`（一个进程跑四段：baseline mdp + 三组 baseline 断言 + acceptance metrics）+ 新增 `[33]` `test_baseline_isolation.py` ⇒ **46** |

**结果（真实 Kit + 离线套件）**

| 运行 | 结果 |
|---|---|
| 探针 `--headless` / `--random-actions` | rc 0 / rc 0，各 **26 项全 ok**；激励面 `mean\|a\| 0.4998`、`mean\|da\| 0.6679`、commanded dims **26/26** |
| `reset_check.py --task Lizard-Baseline-Flat-v1` | rc 0，A–D **八条全 ok**（激励 8/8、worst \|dq\| 0.3986 rad、suppressed respawns **0**、子集复位后未命名 env 逐位未变） |
| 评测三跑 | 零动作 `zero_action`/`smoke_only`、随机 `deterministic`/`fail`、随机 `sampled`/`fail` —— **没有一次被判成通过** |
| 全量套件 | **46/46**（`ALL_OFFLINE_CHECKS_PASSED`）；`--confirm-cost` quiet **140s** |

**边界（不得据本节宣称）**

- 以上全是**工具冒烟**：没有任何训练 checkpoint 进过这些路径，"这副机器人能否学会持续行走"仍
  **待**（`baseline/v1/NOTES.md` 结果表）。
- "首回合失败后不累计重生位移"**未被真实跑触发**——三跑首回合都活满 1000 步
  （`first_episode_frame_fraction 1.0`）；它只有离线反例证过（第 3 步失败后逐帧喂 1000 m 假位移，
  位移仍为 2 m）。
- 探针的终止注入验证**接线与阈值**，不替代物理跌倒试验；探针只排除所测故障。
- `[21]` 的可见横幅是末段 `test_acceptance_metrics: 5 passed`（`main()` 把它放在最后），`BASELINE_CONTRACT_OK`
  只在套件输出里露一次：**"某段被静默跳过"这件事没有钉子**（`main()` 按 `globals()` 前缀收集，改名即掉）。
  本轮按现状记录，未加钉。
- `SERIAL_BUDGET_S` **不动**：实测 140s 与 `0.8 × 175 = 140` 恰好相等 ⇒ 工具不报 tighten 提示，但富余
  25% 略宽于口径自称的 20%；只记测量，收紧另起一笔。
- 本节的评测报告与日志落在 `_tmp_*`（`.gitignore` 内），**不进仓**；引用的随机 checkpoint 已随本轮
  清理删除，故这些报告**不可复跑**——它们只是工具冒烟，不是可引用的验收记录。

**提交归属**：本批 commit：`baseline_eval.py` · `baseline_metrics.py` · `protocols/baseline_flat_v1.json` ·
`baseline_runtime.py` · `test_baseline_contract.py` · `test_baseline_mdp.py` · `baseline_probe.py` ·
`offline_suite.py` + `OFFLINE_CHECKS.md` · `FILEMAP.md` · `baseline/*` + `v1/NOTES.md` ·
`baseline_mdp.py`/`baseline_env_cfg.py`/`rsl_rl_ppo_cfg.py` 口径 · 本节。

## 证据引用

- 基线线独立化：`rl_exp/tasks/recipe_factory.py`、`baseline_recipe.py`、`recipe_tasks.py`、`recipe.py`；
  闸门 `check_configclass_fields.py` + `test_configclass_fields_gate.py`（套件 `[23]`）、
  `test_baseline_isolation.py`、`test_baseline_contract.py`；`FILEMAP.md`。
- EOL：`.gitattributes`、18 套 `rl_exp/versions/**/asset_lock.json`、
  `rl_exp/tools/verify/check_golden_frozen.py`（4 条 FROZEN）、`check_cfg_lock.py`、`check_dr_parity.py`、
  `OFFLINE_CHECKS.md` + `offline_suite.py`；commit `7acc84f`；
  实测 `git ls-files --eol` / `git status`（233 个文件 unchanged）。
- 固定窗口评测：`ablation_harness/baseline_eval.py`、`baseline_metrics.py`、
  `protocols/baseline_flat_v1.json`、`rl_exp/tools/verify/baseline_runtime.py`、
  `baseline_probe.py`、`reset_check.py`；套件 `46/46`。
- 相关记录：`acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`（`[35]` 的 FROZEN 表
  与每次合法重锚）、`acceptance/records/2026-09-17-lizard-hard-b-difference-declarations.md`
  （baseline 线的差异声明与 agent 段）。

## 未覆盖边界

- **基线线独立化的边界**：只证"基线任务的解析不拉主线、且类身份与导入顺序无关"，
  **不证基线配方本身能训、能达标**；白名单理由是人工审查产物，`= 实际加载集` **只挡死权限**，
  挡不住"新加的模块恰好也被放行"；干净 worktree 那次是**内容级**验证（复制文件进树），
  **不是** `git checkout` 出来的独立克隆。
- **EOL 的三条边界**：① 非被摘要类（`.py`/`.md`/`.csv`/`.log` 等）在本机仍是旧行尾，随下次 checkout
  归一，本次**只保证被摘要的类**与 `.bat` 的两侧一致；② 政策让"工作树与索引一致"、**不改任何已存 blob**，
  跨平台一致性来自 checkout 而非重写历史；③ 本条的绿只证"**摘要可移植**"，**不证资产本身未被改动**。
- **固定窗口评测的边界（全部归为工具冒烟）**：
  - 没有任何训练 checkpoint 进过这些路径 ⇒ 不谈"能否学会走路"；
  - "首回合失败后不累计重生位移"**未被真实跑触发**（三跑首回合都活满 1000 步），只有离线反例证过；
  - 探针的终止注入验证**接线与阈值**，不替代物理跌倒试验，只排除所测故障；
  - **`[21]` 的"某段被静默跳过"没有钉子**（`main()` 按 `globals()` 前缀收集，改名即掉）——本轮未加钉；
  - 报告与日志落 `_tmp_*`（不进仓）、引用的随机 checkpoint 已删 ⇒ 这些报告**不可复跑**，
    **不是可引用的验收记录**；
  - `SERIAL_BUDGET_S` 不动（140s 与收紧线恰好相等，富余 25% 略宽于自称的 20%），**收紧另起一笔**。
- **成本读数的口径边界**：同一常量两次读数（154s / 140s）差 10% ⇒ **单次读数不足以支撑收紧**；
  串行计时在并发写手在场时测的是 CPU 争用，不是成本（第一节的"遗留"就是这么来的）。
- **口径边界**：`MAX_CHECKS` 45→46、`46/46`、`39 类`、`7 条反证`这些读数只在**当日 commit** 上成立；
  历史 `[N]` 是当次运行编号，不是闸门身份。
