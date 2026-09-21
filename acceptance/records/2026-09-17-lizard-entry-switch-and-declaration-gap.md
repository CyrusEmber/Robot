# 声明路径成为训练入口：载体对账、入口切换、生命周期收缩、声明缺口清空（2026-09-17）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的以下旧节（按追加序）：

| 旧节 | 主题 |
|---|---|
| §声明载体与接线对账 | C2 切换入口前必须落的那批（声明来源 / 启动校验 / trainer 守卫 / T0-T1 记录四件一次做完） |
| §入口切换的机制与第一档真跑 | C2 机制（`apply_into` + `recipe_class`）+ C4 第一档（launcher）与其余四档 |
| §生命周期收缩（在该节内，2026-09-17 追加条目） | 删掉未接线的一半判定机件（同时**删减** A2/A4 交付物）+ 其后的 L02 补记 |
| §C2 收尾 · 翻注册表 | 26 个已声明任务的入口改指 `recipe_tasks` 的生成类 |
| §收掉最后一条声明缺口 | `PLAY_PINS_COMMAND_RANGE` 进配方表（台账清空） |

**本记录内部的前后作废关系（读结论以此为准，被作废的旧句保留作留痕）**：

- **入口切换一节的 `announce`/`moved`/`tuning` 三档 + fixture 生成器 + `RL_RECIPE_DIR` +
  `--allow_retired_resume` 全部被「生命周期收缩」判删除/作废**（`launcher`/`trainer` 两档改打
  **真实**退休线 `lizard/parkour`；`moved` 档的断言收回离线面）。该节的 `launcher` 行引用的拒绝文案已变。
- **同节的「L02 入口侧重跑」补记作废了"三档各自真跑"**：收缩前那一节结论行写的"L02…**通过**
  （三档各自真跑）"与收缩后实情对不上 —— **L02 通过 = `launcher` + `trainer` 两档**，
  "三档"含已删的 `tuning` 档，**作废**；`trainer` 档"真跑窗口执行"一并按补记为准。
- **声明缺口的"修没修"要按两条读**（本记录与
  `2026-09-16-lizard-builder-hard-a.md` 各持一半，两条都未在同一句里区分）：
  - 本记录「收掉最后一条声明缺口」写的是 `[41]` **输出里不再有任何 ClassVar 缺口行**、
    `EXPECTED_GAPS` 清空 —— 这是**台账打印**这件事。
  - 「ClassVar **真缺口**未修」指的是**读取侧**（`REQUIRES_CURRICULUM_STATE` 的四个读者走
    `getattr(type(cfg), …)`），它的修法在**行为面**。
  ⇒ 判据是：**台账空 ≠ 机制停用、也 ≠ 读取侧已修**。本记录的载体对账给的正是读取侧那一半
  （`declares` 进配方表 + 合成子类盖章 + 启动校验），但"声明 True ⇔ 接线非空"的启动校验落点是
  `verify_declaration`，不是把四个读者改成读声明。
- **`recipe_lifecycle` 的字段也在本批被删**：`revision`（无行为读者）、`--now`/`today`（无时钟）；
  保留 `format`、二值 `status`、退休证据（`retired_at` + `reason`）、`successor` 校验。

**与其它记录的关系**：硬 B 的差异声明与 `author` 口径见
`acceptance/records/2026-09-17-lizard-hard-b-difference-declarations.md`；构建器与 `[41]` 的三条纪律见
`acceptance/records/2026-09-16-lizard-builder-hard-a.md`；版本类体删除与硬 A 保真比较退役见
`acceptance/records/2026-09-16-lizard-layout-migration-lifecycle.md`。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管（本记录横跨 43 条条目）⇒ 各节的成功行读数**只在当日 commit 上成立**；
「已修」与「仍是缺口」并存时，作废句一律从作废它的那节读。

## 验收条件

### 声明载体与接线对账的四件一次做完（为什么不能拆）

这批是"声明来源 / 启动校验 / trainer 守卫 / T0-T1 记录"四件一次做完，因为**单改一处都不完整**：
只删 save 守卫的合取会把它变成"训练几小时后 save 时才炸"；只改 manifest 会让其余三个读点继续按类读取。

**改动面**：`recipe.py`（`declares` 进配方表 + `declaration()` + `build()`/`base_cfg()` 返回**携带声明的
合成子类**）、`curriculum_state.py`（`declares`/`wired_terms`/`expected_terms`/`verify_declaration` +
启动调用 + save 的载荷覆盖判据）、`check_recipe_build.py`（**过渡期保真闸门**：表 == 类）、
`manifest.py`（T0 记 expected/wired/declaration_problems，原有 `declares_curriculum_state` 保留）、
`test_resume_state.py`（新用例 + 反证）、`FILEMAP.md`。

### 生命周期收缩的判据（实测，不是判断）

触发是评审问"9 类操作 × 二值 status + 弃用声明层，要防的事其实只有一件：别对 retired 线开新训 ——
这是不是过度设计"。收缩后的判据形状：

- `recipe_lifecycle.judge(operation, status)`：**2 类接线操作 × 二值 status**；未知操作 / 未知 status /
  缺索引一律拒绝；**拒绝文案不承诺后继线**（`successor` 只做结构校验）。契约自带 7 判定 + 2 文案检查。
- `--drop_curriculum_state`（含弃用别名 `--weights_only`）的"无 resume 即拒"迁到
  `runrecord/lifecycle.curriculum_flag_problems()`，两种拼写一致，仍由 launcher 与 trainer 共用同一入口。
- C4 的档表：`launcher` / `trainer` 两档打**真实**退休线（`lifecycle_entry_run.py` 的 `TRACKS`）。

## 结果

### 声明载体与接线对账：关键设计（不改四个读点，而是让 `type(cfg)` 说真话）

resume 拒绝、save 守卫、`train.py` 的导入失败守卫、manifest 记录，四者都读 `type(cfg)` 上的
`REQUIRES_CURRICULUM_STATE`。所以修法不是教四个读者认新来源，而是让**声明路径返回的类也带这句声明**
（配方表为真源，`build()` 用 `type(...)` 合成子类盖上）；`launch_recipe.py`（C2 入口）与注册表仍走类路径，
两条路径因此**答案一致**。

> **一处实测教训（写下来免得重踩）**：盖章必须写成 `ClassVar[bool]` 标注，不能只 `setattr` 一个值。
> 只设值会让 `cfg_snapshot` 的 ClassVar 判定失效 ⇒ 它作为**字段**进入快照 ⇒ 一次跑出
> **24 条硬 A 红 + 9 条归属无主 + 1 条硬 B 未声明差异**。标注后三条全消失：声明是"关于配方的陈述"，
> 不是数据。

**检查与结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A / 硬 B / 归属 | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 33 declared difference(s) from the stock base)` |
| 过渡期保真闸门 | 同上（每个 line/version/kind 比对表与类） | **通过**（26/26）；**反证 FIRED**：只把表里 v14 改成 `(False, False)` ⇒ `FAIL lizard/main/v14/train: the recipe states …=False while LizardRoughTeacherEnvCfg_V14 states True -- the two paths would answer differently` |
| 台账清理 | 同上 | **通过**：`REQUIRES_CURRICULUM_STATE` 不再是缺口 ⇒ 按"陈旧台账项也红"的规则删条目（`EXPECTED_GAPS` 现只剩 `PLAY_PINS_COMMAND_RANGE`） |
| 声明与接线对账 + save 覆盖 | `test_resume_state.py`（新用例 + 反证） | **通过**：28/28。三面：①声明 True 而配置不断言任何课程项 ⇒ `verify_declaration` 报"wires no curriculum at all"且 `hook_runner_save` 抛错；②已接的 stateful term 无 adapter ⇒ 报"no registered adapter"；③配置仍要该 term 而**接线被清空**（只有 c_k 时钟的载荷，`collect` 返回的不是 None）⇒ save 抛"un-resumable"。**反证 FIRED**：把 `declares` 读法摘掉后同一 save 顺利通过 ⇒ 上述红来自新判据，不是旧的"载荷为空"分支 |
| 旁证 | 全量套件 | **43/43**（wave 203 s / 400 s）；`[14]` 仍 `task cfg import chain is pxr-clean`（`recipe.py` 新增 `curriculum_state` import 未破坏链） |

**边界**

- **合取保留**（`requires_resume_state = 声明 ∧ 有接线`）：它不再承担"声明是否成立"的判断，那件事移到启动时 `verify_declaration`（训练前终止）；它在 resume 侧仍表达"这条任务确实要恢复点什么"。
- **对账用"配置字段"而非第二张 term 清单**：`expected_terms` 从 `cfg.curriculum.*` 派生（取不到时回落 manager 的 cfg，为的是不把 stub 读成"配置什么都没要"）。因此**不新增手抄映射**；代价是"声明与接线"的对账强度取决于 cfg 字段与 manager 是否同源（真实 env 上二者本就是同一对象）。
- **`train.py:324` 一字未动**：它的读法在声明路径变真后自动正确 —— 这正是"改载体、不改读者"的收益。
- **仍未做**：`launch_recipe.py` 改走 `recipe.build()`（即"声明路径成为训练入口"）与随之的版本类体删除；硬 B 仍只覆盖 env cfg（agent 配置未纳入；该边界随后由硬 B 加齿作废，见硬 B 记录）；真环境行为等价仍要 C 层真跑。
- **`declares` 的值是过渡期抄自版本类的**（train True/False、play 全 False），由保真闸门逐步看守；等类体删除后，配方表成为唯一来源。

### 入口切换的机制与第一档真跑（C2 机制 / C4 部分）

**性质**：C2 的"声明路径成为训练入口"拆成两件可分别验收的事：**机制**（本节）与**翻注册表**
（见「C2 收尾」）。C4 同理：五档真跑里只有一档不需要仿真，本节把它真跑掉。

**机制：`apply_into` + `recipe_class`**

- `build()` 的步骤体抽成 `apply_into(cfg, version, play=, line=, trace=)`，`build()` 变成"构造共享接线的实例 + `apply_into`"；`recipe_class(version, play=, line=, name=)` 生成一个 `@configclass` **子类**，其 `__post_init__` = `base.__post_init__(self)` + `apply_into(self, …)` —— 版本类体当年就在这个位置干这件事，所以注册表能指它。
- **两者共用同一份步骤** ⇒ 不可能漂移；`[41]` 逐条断言"可注册的类构造出来的 cfg == `build()` 的 cfg"（26 个 task/kind 全过）。
- `name=` 参数是给切换用的：**注册类叫什么名，生成的类就叫什么名**。因为 ckpt 载荷记 `type(cfg).__name__` 并参与 resume 身份核验，名字不一致会让"类路径起的 run"无法被"声明路径"续训。

**检查与结果**

| 项 | 结果 |
|---|---|
| 机制等价 | `[41]` **通过**（26/26）；**灵敏度**证明："拿 v13 的类去比 v14 的 build"出 3 条差异 ⇒ 这个比对不是恒空 |
| `[41]` 成本 | 单跑 **9.7 s**（预算 25 s；+26 次构造约 +1 s） |
| **C4 第一档真跑（launcher）** | **通过**：`lifecycle_entry_run.py --track launcher` ⇒ 退出码 2、stderr `[launcher] refused: retired line: refusing new_train; new work belongs to an active successor line`，且**没有新建 run 目录**（拒绝发生在 spawn 之前 ⇒ trainer 从未启动）。这一档不需要 sim app，所以它现在就是真证据，不是离线断言 |
| 其余四档 | **真跑通过**（`--track all`，一条命令五档）：`trainer` 拒绝且 T0 记 `allowed=False`；`tuning` 被同一子进程杀死（exit 1）；`announce` exit 0 且记录 `warn="the line's announced retirement is due and the directory has not been revised; recording the overdue directory, proceeding under status=active"`；`moved` 记录保住原目录摘要、`verify` 只报告"目录已改" |
| **由此发现并修掉的缺陷（真跑才看得见）** | 拒绝**没有被退出码观察到**：进程打印拒绝、T0 记 `allowed=false`，却 **exit 0**（Isaac 的 app 收尾在返回路径上把码归一）。按退出码判成功的调用方（CI、`&&` 链、扫参调度）会把它当成功 ⇒ fork 补丁在 T0 调用点加 try/except：打印 `[FATAL]` 后 `os._exit(2)`（`os._exit` 是必需的，降级 `raise`/`sys.exit` 依然被收尾吞掉）。实测 `RC=2`；`[1] PIN_CHECK_OK` 复验补丁链仍与 fork 树逐字节一致 |
| `moved` 的控制修正 | 首版两份 fixture 内容相同（只改 revision 数字、值一样）⇒ 摘要相同 ⇒ 控制没生效（假过）。加 `bump=` 让 A/B 修订真的不同后，`verify` 才报出"目录已改" |

> **2026-09-17 收缩（本节部分内容作废）**：上表 `announce`/`moved` 两档与 `tuning` 档、fixture 生成器
> （`lifecycle_entry_fixture.py`）、`RL_RECIPE_DIR`、`--allow_retired_resume` 均已删除；`launcher`/`trainer`
> 两档改打**真实**退休线 `lizard/parkour`（不再造 fixture）。上表 `launcher` 行引用的拒绝文案已变
> （旧文案承诺后继线，而该线没有 `successor`）。`moved` 档的断言（目录改版不改写记录）收回离线面：
> `test_run_manifest.py` 的 `verify/rev-moved-is-reachable` + `dirty/refusal-verify-is-not-drift`
> 覆盖同一族规则。

**边界（本节更新后的入口侧验收状态）**

- **注册表未翻**（当日）：`rl_exp\tasks\__init__.py` 的 `env_cfg_entry_point` 与 `recipes.json` 的 `env_cfg_entry` 仍指版本类 ⇒ 训练走的还是类路径。翻表是三步（生成类 + 改两处字符串 + `name=` 对齐），本轮只把机制与证明备好，**没动**——因为它同时意味着版本类体可以开始删，那是 B 侧迁移的收尾节奏。→ 由「C2 收尾」接上。
- `recipes.json` 里 baseline 的 demo/extra 条目与 `RECIPE_DEMO`/`EXTRA_TASKS` 无关（主线任务），所以翻表不影响它们。
- C4 的 `launch` 档只证"新入口在 `gym.make` 前拒绝"；`trainer` 档另外证"拒绝会被退出码观察到，且 T0 留下拒绝记录"；`tuning` 档证"调参入口不能绕过"（该档已被收缩删除）。
- **入口侧验收状态（本节更新）**：L02（退休线过三个入口）**通过**（三档各自真跑）；L03 的"缺状态 resume 硬拒"仍只有离线半边（真跑需一个缺课程状态的 ckpt 臂，属 C 层旧账）；L05 的"启动后改目录"**通过**（`moved` 档）。→ 其中"三档"与 `moved` 两条按收缩与补记为准。
- 本批不新增套件条目（机制断言落在 `[41]` 内；`lifecycle_entry_run.py` 要起 sim，按 `OFFLINE_CHECKS.md` 5 不进套件）。

### 生命周期收缩：删掉未接线的一半判定机件（2026-09-17）

**性质**：同时**删减** A2/A4 交付物。

**依据（实测，不是判断）**

| 项 | 实测 |
|---|---|
| 到达 `judge()` 的操作 | 只有 `new_train`/`resume`（全仓唯一调用点 `runrecord/lifecycle.py`，`operation = "resume" if is_resume else "new_train"`）⇒ 表中 `tune`/`new_recipe`/`load_ckpt`/`eval`/`export`/`rebuild`/`modify_recipe` 7 类从未被传入 |
| `deprecation` 使用方 | `lines.json` 三行全为 `null` ⇒ 时间条件、WARN 层、`--now`、`condition_satisfied`/`retirement_due` 全部零执行 |
| 续训豁免可达性 | 唯一退休线 `lizard/parkour` 因 v8 改名构不出 env ⇒ `--allow_retired_resume` 豁免的是"健康但已退休的线"，当前不可达 |
| 附带发现（先于本轮存在） | `--verify` 把"在 T0 被拒"当**失败训练**（`manifest.py` 的缺 stages 分支 + `_verify_lifecycle`）⇒ 想让审计变绿的唯一办法是删掉拒绝目录，正好删掉设计要的"拒绝留痕" |

**改为**

- `recipe_lifecycle.judge(operation, status)`：2 类接线操作 × 二值 status；未知操作/未知 status/缺索引一律拒绝；**拒绝文案不承诺后继线**（`successor` 只做结构校验）。契约自带 7 判定 + 2 文案检查。
- `--drop_curriculum_state`（含弃用别名 `--weights_only`）的"无 resume 即拒"迁到 `runrecord/lifecycle.curriculum_flag_problems()`，两种拼写一致，仍由 launcher 与 trainer 共用同一入口。
- `check_recipe_registry.py` 无时钟（`--now`/`today` 删除）；保留 `format`、二值 status、退休证据（`retired_at` + `reason`）、`successor` 校验。**同轮删掉 `revision`**：它的唯一行为读者（`registry_revision` 条件）随本收缩消失，剩下的只是人读标签 + 与内容摘要冗余的跨入口对照，而人工计数器会撒谎（改目录忘 bump、bump 而内容未动，两者都不触发任何红）。目录身份由 `lines.json`/`recipes.json` 的内容摘要给出（`evidence.directory_sha256`），`--verify` 的"目录未变"行不再打印修订号。
- `verify()` 认"T0 被拒"为**终态**：记录完整（`allowed=False` + 原因 + `failures`）、训练后才有的断言记不适用/未知且不阻塞、`--verify` 退出 2（未声称任何训练后结论）而非 1；反向仍红（拒绝与训练阶段并存、或拒绝缺 `failures`）。
- trainer 侧 ImportError（`rl_exp` 不可用）由"WARN 后继续"改为 `[FATAL]` + `os._exit(2)`：门禁不可用 ≠ 无门禁（记录器与门禁同体，记录不是"永不打断训练"那一类）。代价：该路径下拒绝**不留记录**（记录器本身缺失），只能看 stderr。

**检查与结果**

| 项 | 结果 |
|---|---|
| 离线套件 | **43/43 通过**（`ALL_OFFLINE_CHECKS_PASSED (43/43)`；另有一次并行跑里 `[34] test_params_isolation` 单例失败、单独跑与复跑均通过，判定为并行抖动、与本轮改动路径无关） |
| C4 launcher 档（真跑，不需 sim） | **通过**：`lifecycle_entry_run.py --track launcher --task Lizard-Parkour-Climb-v1` ⇒ 退出码 2、stderr `[launcher] refused: retired line: refusing new_train; retirement stops new work on this line`、**没有新建 run 目录**；记录里 `line=lizard/parkour`、`status=retired`、`allowed=false`，拒绝文案**不含** `successor` |
| C4 trainer 档 | 保留档位（真跑窗口执行）：断言退出码 2、T0 留下拒绝记录、且 `manifest --verify` 把该目录读成"启动被拒"而非损坏。→ **按下面的补记，该档已真跑，措辞以补记为准** |
| `moved` 档 | 收回离线面（`verify/rev-moved-is-reachable`、`dirty/refusal-verify-is-not-drift`、`test_lifecycle_gate.py` 的 verify 组） |
| fork 补丁一致性 | `git apply --check --reverse` 两个补丁均成功 ⇒ 删除 `--allow_retired_resume` 参数块与 ImportError 改 FATAL 后，补丁链与 fork 树仍逐字节一致 |

> **2026-09-17 补记（L02 入口侧重跑；追加，不改上文）**：上表 `trainer` 档标"保留档位（真跑窗口执行）"，
> 而本节结论行又写"L02…**通过**（三档各自真跑）" —— 两者对不上：前者是收缩**删掉 `tuning` 档、把
> ImportError 改 `[FATAL]`、并改掉拒绝文案之后**的实情，后者是从收缩前那一节抄来的旧口径。现按
> `ARCH_PLAN.md` §2.3 对 L02 的**原始两档定义**重跑，两档跑的都是收缩**之后**的代码：
>
> - `--track launcher --task Lizard-Parkour-Climb-v1` ⇒ 退出码 **2**、stderr `[launcher] refused: retired line: refusing new_train; retirement stops new work on this line`、**未新建 run 目录**（拒绝发生在 spawn 之前）；
> - `--track trainer`（同 task）⇒ 退出码 **2**、拒绝留在 `logs/rsl_rl/lizard_parkour_climb_v1/2026-09-17_17-02-16`：`stages` 只有 `pre_make`、`declaration.lifecycle.allowed=false`、`status=retired`、`failures=["refused to start: retired line: refusing new_train; retirement stops new work on this line"]`；`manifest --verify` **无 blocking**，逐行读作 "launch refused at T0, no training started"，训练后才有的断言一律记 not applicable；
> - 两档同跑 `LIFECYCLE_ENTRY_RUN_OK`（`lifecycle_entry_run.py` 的档表见 `TRACKS`；`--report` 落在 `%TEMP%`，本条目摘出实际值）。
>
> ⇒ **L02 通过 = 上述两档**，"三档"含已删的 `tuning` 档，**作废**；上文 `trainer` 档"真跑窗口执行"与
> 结论行的"三档"一并按本条为准。L03 的缺状态 resume 真跑臂**仍未跑**（工作树里 `--track resume`
> 已起草但未提交、未跑，按 `PLAN.md` #23 记在账上）。

**边界**

- **不再有"提示期 / 生效日"机制**：退休生效 = 目录显式修订；旧线不会被自动退休，也不存在运行期硬截止日。若要给某条线留迁移期，写进 `reason` 与人读的文档，不用机器判定条件表达。
- **`eval`/`export`/`rebuild`/`load_ckpt` 不经过这张表**：它们不受退休影响，但也**没有被这层覆盖**（原表把"允许"当成已接线，是误读）。将来若某入口要受管，届时连同它的调用点一起加。
- **身份解析仍是依赖**：`task id → recipes.json → 线 → lines.json` 任一文件不同步 ⇒ 拒绝启动（"未知即拒"的既有代价）。收缩时保留 `identity()` 的分类原因，不回退成一句笼统的"生命周期失败"。
- **L03 缺状态 resume 真跑臂仍未跑**（当日口径；后由
  `acceptance/records/2026-09-18-lizard-mainline-run-closeout-l03.md` 的两臂补上）。

### C2 收尾 · 翻注册表：声明路径成为训练入口（2026-09-17）

**性质**：上节备好的机制在本节**接上电**：26 个已声明任务的 `env_cfg_entry`（注册表）与
`env_cfg_entry_point`（身份映射）从版本类改指 `recipe_tasks` 的生成类。

**落地**

| 件 | 内容 |
|---|---|
| `tasks\recipe_tasks.py`（新） | 每条已声明配方 × train/play 生成一个类，**名字沿用被替换的版本类名**；名字从 `recipes.json` 读（身份映射），不另立清单；模块无需显式 import（注册表以字符串指向它） |
| 注册表 + 身份映射 | 各 26 条 entry 改指 `rl_exp.tasks.recipe_tasks:<同类名>`（脚本改字符串，逐条打印，未手抄） |
| `[41]` 过渡闸门 | 改为**按发现**取被替换的版本类（构造候选类读 `params_version` —— 它是字段，1.0 结论；版本令牌优先解决"最新类与 `_V<N>` 类同版"的歧义）。**不改就会静默失效**：翻表后身份映射指向生成类，闸门若仍经它取类，就是拿生成类与自己比 |
| `test_recipe_map_gate.py` | 反证用例改为断言"解析器读到了 env 入口"（类名后缀）而非"等于某个模块路径"，否则它会为一次它并不看守的改动变红 |

**检查与结果**

| 项 | 结果 |
|---|---|
| 真实入口路径 | **通过**：`gym.spec('Lizard-Rough-v14')` → `rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V14` → 构造得 `params_version=v14`、`REQUIRES_CURRICULUM_STATE=True`、`type(cfg).__name__` **与翻表前同名**（PLAY 同理） |
| 硬 A / 硬 B / 归属 / 生成类等价 | `[41]` **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 76 declared difference(s) from the stock base)`，单跑 9.8 s（预算 25） |
| 全套 | **43/43 通过**（wave 199 s / 400）—— 含 golden `[24]`（逐字段未动）、身份映射 `[31]` + 其反证 `[32]`、obs 契约、pxr `[14]`、生命周期 `[39][40]`、组件单写点 `[37]` |

**边界**

- **版本类体已无人引用，但没删**：删除属 B 侧迁移收尾；`[41]` 的过渡闸门正靠发现它们而与配方表对账 —— 删干净时该闸门应当被**显式退役**（"找不到被替换的类"现在是红，不是跳过）。→ 由
  `acceptance/records/2026-09-16-lizard-layout-migration-lifecycle.md` 的「2.4 收尾」接上。
- **未改**：agent（PPO）配置仍由 `rsl_rl_ppo_cfg.py` 的类提供（本轮只翻 env cfg 入口）；hydra override 语义、日志目录名、`--task` 与 agent 入口的一切不变。
- 生成类与版本类**是不同的类对象**：全仓已查无按类身份判版本的代码（只有框架基类的 `isinstance`），故无静默错。
- 声明路径成为入口 **≠ 已被真跑覆盖**：`lifecycle_entry_run.py` 的五档验的是**生命周期判定**；"声明路径训练出的 run 与类路径等价"仍由 `[41]` 的字段等价 + 将来的真跑背书。

### 收掉最后一条声明缺口：`PLAY_PINS_COMMAND_RANGE` 进配方表（2026-09-17）

**性质**：本批对应"**不加验证框架、只处理已确认的声明丢失**"那一条判断：`[41]` 台账里只剩的最后一条缺口。
改动面 = `recipe.py`（配方表 `pins_full_range` + `pins_full_range()` / `_stated()` + `CLASSVAR_STATEMENTS`
+ 两处盖章）、`[41]`（保真判据按同一张清单循环 + `EXPECTED_GAPS` 清空 + docstring）。
**未扩展元素所有权系统**（理由见末节）。

**为什么这条必须在翻表前做**

`PLAY_PINS_COMMAND_RANGE` 的读者是**共享接线的 `__post_init__`（构造期）**：v3/v4 的 PLAY 已无课程
可以把范围拉宽，所以它要满量程而不是课程窗口。配方表沉默期间，声明路径读到的是基类的 `False`，
**效果**由 `play_pins_full_command_range` 事后补上 —— 字段是对的，**声明没有了**。翻表之后
（注册项指向合成类、版本类体开始删），那句话只剩在类体上，**会随类体一起消失**。所以它必须在翻表之前搬进表里。

**落地**

| 件 | 内容 |
|---|---|
| 配方表 | 每个配方加 `"pins_full_range": (train, play)`，v3/v4 = `(False, True)`、其余 `(False, False)`（与 `declares` **同形同位置**） |
| 读法 | `pins_full_range(version, play=, line=)`，与 `declaration()` 对称，共用 `_stated()` |
| 一处清单 | `recipe.CLASSVAR_STATEMENTS = ((REQUIRES_CURRICULUM_STATE, declaration), (PLAY_PINS_COMMAND_RANGE, pins_full_range))` —— "哪些声明要离开类体"只有一个答案；`_wired_class` 与 `recipe_class` 都照它盖章（按名标注 ClassVar，不是 `setattr`） |
| 闸门 | 保真判据改为对该清单循环（表 == 类，**两个 ClassVar × 两种 kind**）；`EXPECTED_GAPS` **清空**；docstring 里"构建器结构上带不走 ClassVar"那一段改写为过渡期规则（清单为真源、两条路径答案必须一致、无家可归者打印并须进台账） |

**结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A / 硬 B | `[41]` | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 76 declared difference(s) from the stock base)`，**输出里不再有任何 ClassVar 缺口行**（台账空且无缺口 —— 上一节还有两类，现在为零） |
| **反向验证** | 三处临时破坏 | **各自打对**：① v3/play 表值翻成 `False` ⇒ `…PLAY_PINS_COMMAND_RANGE=False while LizardRoughTeacherEnvCfg_V3_PLAY states True -- the two paths would answer differently`；② 删掉 v4 的表键 ⇒ train/play **各自** `states no PLAY_PINS_COMMAND_RANGE … (the class path states …)`；③ 空台账下缺口再现 ⇒ `classvar the declaration cannot carry, and the ledger does not know it`。随后**原样回滚**复绿 |
| 旁证 | `[24]` · `[28]` · `[37]` · `[14]` | **全绿**：`CFG_LOCK_OK (36 tasks, 3 line(s))` · `test_resume_state: 28 passed` · `COMPONENT_OWNERSHIP_OK` · `task cfg import chain is pxr-clean` |

**边界**

- 基类**仍**声明 `PLAY_PINS_COMMAND_RANGE = False`，类路径照旧可读；本批做的是"让声明路径也说得出这句话"，**不是删旧载体** —— 删类体归翻表那批。
- **台账空 ≠ 机制停用**：`EXPECTED_GAPS` 仍在，新增一个"表里没家、类上有"的 ClassVar 会立刻红（本轮已验证"未知缺口"分支；"陈旧台账项也红"分支由并行批次的用例覆盖）。
- 本轮**未动翻表**（`rl_exp/tasks/__init__.py` 的 `env_cfg_entry_point` / `recipes.json` 的 `env_cfg_entry` 两处字符串）——那是并行批次的节奏；本批只把它前面最后一块砖补上。
- 未跑全量套件端到端。

**明确不做：元素所有权系统（用户判断 2026-09-17）**

上一节点名的"给每个元素声明允许写入的字段集"**不做**，理由被采纳：① 要抓"同值写入 / 先改再恢复"
得上完整写入追踪，而目前**没有任何实际故障**证明值得；② YAML 在既有字段上的数值变化**本来就不是
字段所有权检查的职责**，现有 golden 已能拦（`[24]` 对类路径、`[41]` 对声明路径）；③ "元素与清单可同时改"
不是漏洞 —— 任何源码级检查都能连规则一起改，最终仍靠 review。

**本批把归属做成显式可校验的断言**（每条路径点名元素、闸门重放验证）即为该问题的收口。
**后续若出现具体反例**（现有检查确实漏掉了非预期覆盖），再补**最小**检查；在此之前不扩机制。

## 证据引用

- 声明载体：`rl_exp/tasks/recipe.py`（`declares` / `declaration()` / `CLASSVAR_STATEMENTS` /
  `pins_full_range()` / `_stated()` / 合成子类盖章）、`rl_exp/tasks/curriculum_state.py`
  （`declares`/`wired_terms`/`expected_terms`/`verify_declaration`）、`rl_exp/tools/runrecord/manifest.py`、
  `rl_exp/tools/verify/test_resume_state.py`。
- 入口与生命周期：`rl_exp/tasks/recipe_tasks.py`、`rl_exp/tasks/__init__.py`、
  `rl_exp/versions/recipes.json`、`rl_exp/versions/lines.json`、
  `rl_exp/tools/verify/lifecycle_entry_run.py`（`TRACKS`）、`rl_exp/tools/runrecord/lifecycle.py`、
  `rl_exp/tools/verify/{check_recipe_registry.py,test_lifecycle_gate.py,test_launcher.py}`。
- 真跑读数：`--track launcher` / `--track trainer` 的退出码与 stderr；
  `logs/rsl_rl/lizard_parkour_climb_v1/2026-09-17_17-02-16` 的 T0 记录；
  `%TEMP%` 下的 `--report`（`LIFECYCLE_ENTRY_RUN_OK`）。
- fork 补丁：`rl_exp/fork_patches/`（T0 调用点的 `os._exit(2)`）、`[1]` `PIN_CHECK_OK`。
- 套件：`ALL_OFFLINE_CHECKS_PASSED (43/43)`；`[41]` 单跑 9.7–9.8 s（预算 25 s）。
- 相关记录：`2026-09-17-lizard-hard-b-difference-declarations.md`（硬 B 与 `author`）、
  `2026-09-16-lizard-builder-hard-a.md`（`[41]` 三条纪律与 ClassVar 真缺口）、
  `2026-09-16-lizard-layout-migration-lifecycle.md`（类体删除与保真比较退役）、
  `2026-09-18-lizard-mainline-run-closeout-l03.md`（L03 两臂）。

## 未覆盖边界

- **声明缺口的两条读法（本记录与 B3 记录各一半）**：本记录的"输出里不再有任何 ClassVar 缺口**行**"
  是**台账打印**；**`REQUIRES_CURRICULUM_STATE` 的读取侧真缺口同一日仍未修**（修法在行为面：
  载体决定 + 拆 `declared()`/`needs_restore()` + 启动时校验"声明 True ⇔ 接线非空"）。
  **台账空 ≠ 机制停用**（新增"表里没家、类上有"的 ClassVar 会立刻红，已由本轮的反向验证③证实）。
- **save 守卫的合取不可单删**：删它是反向风险（把错误推迟到训练几小时后 save 时才炸），必须与
  "启动时校验"一起做。
- **生命周期收缩删掉的能力是永久性的**：不再有"提示期 / 生效日"机制；`eval`/`export`/`rebuild`/`load_ckpt`
  **不经过这张表**，不受退休影响，也**没有被这层覆盖**；`revision` 字段已删（目录身份由内容摘要给出）。
- **真跑覆盖不到的地方**：
  - `moved` 档的断言**收回离线面**（不再有真跑证据）。
  - `tuning` 档已删（原"调参入口不能绕过"这条不再被证）。
  - trainer 侧 ImportError 改 `[FATAL]` 后，该路径下**拒绝不留记录**（记录器本身缺失），只能看 stderr。
  - 声明路径成为入口 **≠** 已被真跑覆盖：`lifecycle_entry_run.py` 验的是**生命周期判定**；
    "声明路径训练出的 run 与类路径等价"仍由 `[41]` 的字段等价 + 将来的真跑背书。
- **过渡期残留（当日的开项）**：
  - 版本类体**已无人引用但未删**；删净时 `[41]` 的过渡闸门应被**显式退役**（"找不到被替换的类"
    现在是红，不是跳过）。
  - `declares` 的值是**过渡期抄自版本类**的，由保真闸门逐步看守；等类体删除后配方表才是唯一来源。
  - agent（PPO）配置仍由 `rsl_rl_ppo_cfg.py` 的类提供；硬 B 当时仍只覆盖 env cfg
    （该边界随后由硬 B 加齿作废）。
  - 基类**仍**声明 `PLAY_PINS_COMMAND_RANGE = False`（旧载体未删）。
- **`[34] test_params_isolation` 一次单例失败**被判为**并行抖动**（单独跑与复跑均通过）——
  这是**判断**而非机制给出的结论，记在案。
- **口径边界**：历史 `[N]` 是当次运行编号而非闸门身份；`RECIPE_BUILD_OK` 的读数只在**当日 commit**
  上成立（本记录横跨 33 → 76 条差异声明）。
