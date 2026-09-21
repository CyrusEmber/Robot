# 硬 B：差异声明从 baseline 到 main 12 条 + 谱系口径（2026-09-17 → 2026-09-18）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的以下旧节：

| 旧节 | 主题 |
|---|---|
| §B2/B4 | baseline 线接入构建器 + 硬 B 差异清单（首个新架构配方） |
| §B4 · 硬 B 加齿 | 路径归属元素 + agent 侧进清单 + baseline 锁入摘要看守 |
| §B4 · 硬 B 谱系口径 | v14 试点 + `author` 校验（口径由 `base.json` 决定） |
| §B4 · main 线 12 条配方的差异声明 | 台账 #24 收尾（322 条，`format: 4`） |
| §硬 B 追加（2026-09-18） | 家族三条配方的差异声明 + 生成方式与限制 + 边界 |

**本记录内部的前后作废关系（读结论以此为准，被作废的旧句保留作留痕）**：

- **`硬 B 只覆盖 env cfg`（§B2/B4 · 边界第一条）被判`自此失效`** —— 作废它的是 §B4 · 硬 B 加齿
  的开头一句："agent 侧已进清单"。这是本次 ACCEPTANCE 分流里两条已知作废之二（另一条是
  `硬 A 前置未满足`，见 `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`）。
- **`baseline` 线的锁当时不在 `[35]` 的 FROZEN 表里**（§B2/B4 · 边界第二条）—— 由 §B4 · 硬 B 加齿 ③
  收掉（加为第 4 项，冻结于 `ed4d35b`）。
- **差异清单的格式一路演进**，同一条规则在不同节读法不同，以最后一节为准：
  `format 1`（33 条具名路径）→ `format 2`（每条路径带 `element`）→ `format 3`（按母版/stock 分流）
  → **`format 4`（按作者集合分组）**。`EXPECTED_DIFFS` 的钉数与"未声明即打印"的纪律一路保留。
- **`author` 的两类（`components.X` / 元素名）在 main 12 条处扩为三类**（增加 `wiring`：共享接线读
  本配方自己的文档）；"两个作者"的说法只在 v14 试点那一节成立，以最后一节为准。

**与其它记录的关系**：

- 硬 A 的锚与比较对象：`acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`；
  构建器与 `[41]` 的三条纪律：`acceptance/records/2026-09-16-lizard-builder-hard-a.md`。
- 声明路径成为训练入口、版本类体删除、声明缺口台账清空：
  `acceptance/records/2026-09-17-lizard-entry-switch-and-declaration-gap.md`。
- obs 协议的宽度与「谁断言的」：`acceptance/records/2026-09-16-lizard-obs-protocol-gate.md`。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管 ⇒ 各节的成功行读数**只在当日 commit 上成立**；「已修」与「仍是缺口」并存时，
作废句一律从作废它的那节读。

## 验收条件

### 口径：基准由 `base.json` 决定，不是二选一

有母版 ⇒ 对母版（谱系）；`base: null`（line root）⇒ 只能对框架基类（stock）。baseline 之所以用 stock，
正因为它没有母版。**有母版却写 stock 块（或反之）＝对一个已有答案的问题给第二个答案 ⇒ 红。**

### 差异声明的三条硬要求（跨五节一致）

| 要求 | 内容 |
|---|---|
| 具名路径，不写子树前缀 | 写 `rewards` 这种前缀，"新加一个奖励项"会自动通过 —— 那就不叫"**只允许**一份显式差异清单"了 |
| 每条路径必须归属某作者 | `format 2` 起：`{路径: {element, why}}`；`format 4` 起按**作者集合**分组，组里路径的作者必须与之**恰好相等** |
| 声明必须被钉 | `diff.json` 存在而 `EXPECTED_DIFFS` 里没有它的条目 ⇒ 红（**未检查的声明读起来与已检查的一样**） |

方向是 `covers(声明项, 路径)`：条目通常比它覆盖的路径浅（`scene.robot` 覆盖 12 个叶子、
`events.reset_base.params.pose_range` 覆盖 6 个 `__tuple__[n]`）。

## 结果

### B2/B4 · baseline 线接入构建器 + 硬 B 差异清单（2026-09-17）

**性质**：`ARCH_PLAN.md` §2.4 的 B2（首个新架构配方）与 B4（硬 B）。改动面 = `recipe.py`
（按线分表 + `build(…, line=)` + 10 个 baseline 元素 + `pins`）、`baseline_env_cfg.py`（拆出空的共享接线基类）、
`check_recipe_build.py`（按线迭代 + 硬 B）、新增 `versions/lizard/baseline/v1/diff.json`。
`ARCH_PLAN:251` 说"新架构承接新的实验线"——baseline 线就是那条新线。

**落地**

| 件 | 内容 |
|---|---|
| 首个新架构配方 | `Lizard-Baseline-Flat-v1`(+Play) 可由 `recipe.build("v1", line="lizard/baseline")` 产出：10 个元素（robot · actions · flat ground · proprio obs · timing · fixed command · rewards · base contact · no curriculum · no DR）。任务/配方键（`baseline-flat-v1@1`）早在 `ed4d35b` 注册；本批补的是"这版能被**声明式**表达" |
| 共享接线 | 新 `BaselineWiringCfg` = 框架 stock cfg + 身份（`params_line` 为 ClassVar、`params_version` 为字段），**零 delta**；`BaselineFlatEnvCfg` 改为继承它，body 留作类路径（golden 由它产出） |
| 线维度 | `recipe.LINES = {line: {base, recipes}}`；`build/base_cfg/declared/pending` 收 `line=`（默认 main，既有调用全不受影响） |
| 硬 B | `versions/lizard/baseline/v1/diff.json`：相对**框架基类 stock cfg** 的 33 条具名差异路径 + 每条理由；`[41]` 双向校验 |

**三条判断**

- **"基准是 stock cfg"这句话本身被机器校验**：`diff.json` 声明 `wiring_is_stock_except: ["params_version"]`，`[41]` 真的比对 `snapshot(stock)` 与 `snapshot(接线类)`，不等即红（实测该 diff 恰为 1 条）。理由：接线类若偷偷带 delta，后面所有比较都失去意义。
- **差异清单写"具名路径"，不写子树前缀**：初稿量出 63 个叶子，聚成 33 条具体路径（`rewards.ang_vel_xy_l2`、`events.push_robot`、`commands.base_velocity.ranges.lin_vel_x` …）。若写 `rewards` 这种前缀，"新加一个奖励项"会自动通过——那就不叫"**只允许**一份显式差异清单"了。
- **`baseline_timing` 是 pin，不是死声明**：它把 decimation/episode/dt/render_interval 写成与 stock **相同**的值（实测这四条不产生差异），于是 `attribution` 的"每步至少动一个字段"会判它红。**不能删**——删了声明路径就不读 yaml 的 `sim:` 段，yaml 改了类会动、声明不动；等版本子类退役后那段 yaml 就成了没人读的装饰。故给配方表加显式 `pins` 名单，且**双向**校验（pin 一旦开始动字段即要求摘掉）。

**结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A + 硬 B | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 33 declared difference(s) from the stock base)` —— main 24（v1–v14×2）+ baseline 2 |
| **反向验证（闸门真的会红）** | 三处临时破坏同时打：加一个未声明字段 / 清单里塞一条不产生差异的路径 / 摘掉 pin | **五个检测器各自打对**：未声明变化、声明了没生效、pin 变活、差异条数漂移（34≠33）、硬 A 字段漂移；banner 翻 `RECIPE_BUILD_FAILED`。随后三处**原样回滚**，复跑全绿 |
| 门 1 | `check_cfg_lock.py`（`[24]`） | 通过：`CFG_LOCK_OK (36 tasks, 3 line(s))` |
| 单写者 | `test_component_ownership.py`（`[37]`） | 通过：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s))` |
| golden 摘要 | `check_golden_frozen.py`（`[35]`） | 通过：`GOLDEN_FROZEN_OK`（3 份基线文件自 `020e6fb` 未动） |
| 旁证 | `check_obs_layout` `[8]` · `check_dr_parity` `[2]` · `check_obs_protocol` · `check_recipe_map` · `check_recipe_registry` · `check_configclass_fields`（39 类含 `BaselineWiringCfg`）· `test_params_isolation` `[34]` · `check_suite_shape` | **全绿**；新基类未影响 configclass 判定（"`params_version` 在全部类里都是 dataclass 字段"） |

**边界**

- **硬 B 只覆盖 env cfg**：agent（PPO）配置未纳入清单，`Lizard-Baseline-Flat-v1` 的 PPO 是否逐字段等于 framework 默认**未验**。→ **该条后由「B4 · 硬 B 加齿」判失效**（agent 侧已进清单），原文保留作留痕。
- **baseline 线的锁不在 `[35]` 的 FROZEN 表里**（表内是 3 份：`cfg_baselines.json` + main + parkour）。本批没跑 `--update`、没动锁，但"这条线的 golden 被移动"目前**没有摘要看守**——属 A 带遗留（B0 节已记 baseline 线"落点未跟踪"）。→ 后由「B4 · 硬 B 加齿」③ 收掉。
- 版本类体与元素表**仍并存**（`BaselineFlatEnvCfg.__post_init__` 与 10 个元素逐段重复），过渡税与 teacher 线同：等 C2/C3 入口走到声明路径才能删类体。
- `recipe.py` 仍不在 `[37]` 的 HOSTS 里；baseline 元素写 `commands.base_velocity.*`（`components` 拥有的名字），与 main 线元素情形相同。
- 硬 B **不证"配方正确"**：它只证"与 stock 基类的差异恰好是声明的那 33 条"。也不证真环境行为（那要真跑）。
- 本轮**仍不新增套件条目**：硬 B 落在既有 `[41]` 内（同一套 snapshot/diff，只换期望值），不付第二份 import 税，也不碰并行侧的 `offline_suite.py`。

### B4 · 硬 B 元素 + agent 侧进清单 + baseline 锁入摘要看守（2026-09-17）

**性质**：上一节 B2/B4 列的四条里，本节收**三条**；第 4 条（注册表翻表 / 删版本类体）由并行批次的
`apply_into` + `recipe_class` 开头，本节只记**我核实的那一步**（见末节）。改动面 = `[41]`（`covers()`
方向、`hard_b` 的两侧、agent 段）、`versions/lizard/baseline/v1/diff.json`（format 2）、
`[35]`（FROZEN 第 4 项 + `FROZEN_REVS` + 两表键一致性）。

**顺带作废旧边界**：上一节"硬 B 只覆盖 env cfg"一条**自此失效** —— agent 侧已进清单。

**三条**

| 条 | 落地 |
|---|---|
| ① 每条路径必须归属某元素 | `diff.json` 的 env 条目改为 `{路径: {element, why}}`。`[41]` 用与 `attribution` **同一套 trace 重放**算出"每个元素真正动了哪些字段"，逐条比对：**没写元素名**、**元素名不存在**、**该元素不产出这条路径**——三种都红。⇒ 改清单消红必须同时改元素表，否则红（这正是上一节点名"同型洞"的堵法：归属不是自由文本，是断言） |
| ② agent 进清单 | `diff.json.agent`：基准 = 框架 stock `RslRlOnPolicyRunnerCfg`，主体 = `recipes.json` 的 `agent_entry`（不在声明里抄第二份）。实测 stock 把 model/algorithm 整块留空 ⇒ **43 条差异**，**逐条列叶子**（写 `algorithm` 当一条前缀，等于让框架新增的 PPO 字段自动通过）。同一套双向校验：未声明 / 声明了没生效 |
| ③ baseline 锁进 `[35]` | FROZEN 表第 4 项：`baseline/cfg_lock.json` sha256 `61d32e8d…`（**冻结于 `ed4d35b`**，晚于其余三份的 `020e6fb`）。新增 `FROZEN_REVS`——`check()` 是纯函数、自测拿它当纯函数证伪，把"谁在何时冻结"混进去等于污染被证伪的核心，故单独一张表只喂 banner，并校验**两表键一致** |

**判断**

- **方向**：`covers(声明项, 路径)`。条目通常比它覆盖的路径浅（`scene.robot` 覆盖 12 个叶子、`events.reset_base.params.pose_range` 覆盖 6 个 `__tuple__[n]`）。初版把方向写反，`[41]` **当场报 7 条假红** —— 假红本身是好事：说明这个比较真的在比，而不是恒空。
- **agent 侧不做元素归属**：agent 是**类**不是声明，没有元素可归。所以它只带理由、不带元素名；`hard_b` 对两侧各施加**各自能施加**的校验，而不是把 env 的规则套上去假装两侧同构。
- **baseline 锁的债是"最值钱"的那条**：这条线是接下来要真训的线，而在本条之前"它的 golden 被移动"**没有任何摘要看守**（B0 节原来只钉 3 份文件、且已记 baseline 线"落点未跟踪"）。现在合法重基线在这条线上也回到"两处编辑 + 理由 + 逐字段审查"。

**结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A + 硬 B | `[41]` | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 76 declared difference(s) from the stock base)`（33 env + 43 agent） |
| **反向验证**（五检测器 + 一张表） | 八处临时破坏 | **各自打对**：未声明 env 变化 / env 声明了没生效 / **归属元素不存在** / **归属元素不产出该路径** / agent 未声明（少一条叶子）/ agent 声明了没生效（多一条假叶子）/ 计数漂移（77≠76）/ `FROZEN_REVS` 与 `FROZEN` 键不一致（`GOLDEN_FROZEN_DRIFT`）。随后**原样回滚**，两闸复绿 |
| golden 摘要 | `[35]`（含 `--self-test`） | **通过**：`GOLDEN_FROZEN_OK (4 baseline file(s) unchanged, frozen at: 020e6fb x3, ed4d35b x1)`；自测 `GOLDEN_FROZEN_SELFTEST_OK` |
| 门 1 / 单写者 | `[24]` / `[37]` 复跑 | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` · `COMPONENT_OWNERSHIP_OK`（本批不改 cfg 内容） |

**第 4 条（版本类体并存的过渡税）：已核实可删，但本轮不动**

并行批次 `384468e` 已把机制备好（`apply_into` + `recipe_class`：声明做成"注册入口能指向的类"）。
本批**只读**核实 baseline 线：

| 比较 | 结果 |
|---|---|
| `recipe_class("v1", line="lizard/baseline", name="BaselineFlatEnvCfg")()` vs `build(…)` | **逐字段 0 差异** |
| 同上 vs 该配方冻结 golden | **逐字段 0 差异** |

⇒ 把注册项指到该合成类、同时删掉 `BaselineFlatEnvCfg.__post_init__` 的重复 body，**可以做到不看任何字段变化**。
本轮不动的理由：那个 API 当时还在并行侧的工作树里（未提交），我在其上写调用点会把依赖钉在未提交代码上；
且"翻表 + 删类体"是同一件事的三步（生成类 / 改两处字符串 / `name=` 对齐），归那一批做。

**提交归属（写清楚，免得历史对不上）**

本节的 `[41]` 改动**落在 `384468e`**（并行批次提交时，当时工作树里的 `[41]` 被一并 `git add` 进去）；
本批自己的提交是 **`9894f73`**（`diff.json` format 2 + `[35]`）。两处合起来才是本节的完整改动面。

**边界**

- 硬 B **不判"这条差异是否合理"**：它只判"与基准的差异是否恰好等于声明"，合理性是 PLAN/review 的事。也不判真环境行为。
- `FROZEN_REVS` 只喂 banner，**不是比较规则的一部分**（比较只看 `FROZEN` 摘要）。
- agent 的"基准 = 框架 stock"未做像 env 那样的"基准确实是空"的机器校验（env 侧有 `wiring_is_stock_except`）；agent 侧直接以 stock 为基准，无中间接线类可夹带。
- 本批**未跑全量套件端到端**（套件条目随并行批次变动）；所跑为 `[41]` `[35]`（含自测）`[24]` `[37]`。

### B4 · 硬 B 谱系口径：v14 试点 + `author` 校验（2026-09-17）

**性质**：`PLAN` 台账 #24 的起步（试点一条）。改动面 = `[41]`（`hard_b` 加母版分支 + `author` 校验 +
身份字段过滤 + "有声明就必须被钉"）、新增 `main\v14\diff.json`、`baseline\v1\diff.json` 迁到 format 3。

**v14 − v13 的实测：3 条，两个作者 + 一个身份字段**

| 路径 | author | 说明 |
|---|---|---|
| `rewards.head_load_penalty` | `v14_head_load` | v14.3 把头部承力终止改成逐帧罚 |
| `terminations.roll_over` | `components.terminations` | v14.4 的翻转跌落门，由**版本解析的组件**写入（没有元素写它） |
| `params_version` | ——（按名过滤） | `'v13' → 'v14'`：**身份**，不是差异；它是"这两条配方不同"的原因本身 |

⇒ main 线的 delta 有**两个作者**：配方的元素，与共享接线里按版本解析自身形态的**组件**。
两者都必须在声明里点名，否则"这条路径归谁"就没有答案。

**判断**

- **母版从 `base.json` 读，不重抄**：`diff.json` 只描述差异；基准由版本目录里那份约定文件决定。**有母版却写 stock 块**（或反之）＝对一个已有答案的问题给第二个答案 ⇒ 红。
- **`author` 二选一，两侧都机器校验**：`components.<名>` ⇒ 必须**没有元素**动过它（有则红，要求点名元素），且该组件在所有权表里**拥有这条路径里的某个名字**（表从 `[37]` 懒取，不抄第二份）；否则视作元素名 ⇒ 必须在 trace 重放里**真的产出**这条路径。
- **身份字段按名过滤，不写进 12 份声明**：`params_version` 是"这是哪条配方"，不是差异；写 12 遍只会多 12 处可抄错的地方。
- **声明必须被钉**：`diff.json` 存在而 `EXPECTED_DIFFS` 里没有它的条目 ⇒ 红（**未检查的声明读起来与已检查的一样**，这正是本仓反复出现的静默跳过形态）。

**结果**

| 项 | 结果 |
|---|---|
| 硬 A / 硬 B | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 79 declared difference(s) against their own base)`（baseline 76 + v14 3） |
| **反证（5 条分支各自打红后原样回滚）** | ① 组件作者但元素真的动过它 ⇒ "name the element"；② 元素作者指到不产出该路径的元素 ⇒ "does not produce it"；③ 组件作者指到不拥有该路径任何名字的组件 ⇒ "owns no name in that path"；④ 有母版却写 stock 块 ⇒ "a second answer to a question that already has one"；⑤ 摘掉 `EXPECTED_DIFFS` 条目 ⇒ "an unchecked declaration reads as a checked one" |
| 旁证 | `[24]` `CFG_LOCK_OK (36 tasks)` · `[37]` `COMPONENT_OWNERSHIP_OK` |

**试点当场抓到一条我写错的声明**：我先把 v14 的 `agent.allowed` 写成空（以为"agent 无差异"），
闸门立刻报 `experiment_name` 与 v13 不同 —— 每个版本一个日志目录。空声明也要被双向检查，这正是它的价值。

**边界**

- **只试点 v14**：main 线其余 11 条未声明（硬 A 证明"没漂"，不证明"差异被声明"）。补法：量 `build(母版)` vs `build(本版)` → 每条路径点 `author` → 在 `EXPECTED_DIFFS` 钉数。
- **两侧的 agent 基准不同**：baseline 对框架 stock runner cfg（line root），main 线**对母版的 agent cfg**（同为版本类，`agent_entry` 从 recipe map 取）。
- 本批未跑全量套件端到端（并行批次仍在飞）；所跑为 `[41]` `[24]` `[37]`。

### B4 · main 线 12 条配方的差异声明（台账 #24 收尾，2026-09-17）

**性质**：口径在上一节已定（由 `base.json` 决定：有母版走谱系、root 走 stock），本批把**其余 11 条补齐**，
并把声明格式换成**按作者集合分组**（`format: 4`），baseline 一并重排到同一格式。改动面 = `[41]`
（分组 schema + 三类作者判定 + 组非空 + 未声明配方打印）、`main/v2..v14` 共 11 个 `diff.json`、
`baseline/v1/diff.json`。

**量出来的规模（322 条，全部逐条带作者与理由）**

| 配方 | 条数 | 配方 | 条数 |
|---|---|---|---|
| v2 | 6 | v10 | 2 |
| v3 | 59 | v11 | 75 |
| v4 | 6 | v12 | 40 |
| v5 | 46 | v13 | 3 |
| v6 | 4 | v14 | 3 |
| v8 | 2 | baseline v1 | 76 |

**三类作者（这是本批的实质发现）**

main 线的 delta 有**三个写者**，不是两个：**元素集合**（同一条路径可被多个元素先后动过，实测 4 处：
v3-v4 的碰撞栈、v5 的速度课程"装后删"、v11 替换 v5 的行 SIR、v13 替换 v5 的核）、
**`components.X`**（按版本解析自身形态的组件，绝大多数路径都是它）、
**`wiring`**（共享接线读本配方自己的文档——yaml 里的数值，既非元素也非组件，实测 v5/v6/v8/v12 各有 1–2 条）。

分组规则：**一个组 = 一个作者集合**，组里路径的作者必须与之**恰好相等**（路径放错组即红）。
组件归属取"拥有该路径里某个名字、位置最浅"者，平手按字母；所有权表从 `[37]` **懒取**，不抄第二份。

**判断**

- **按作者集合分组，而不是逐路径写**：243 条逐条抄理由会把"相同理由"与"复制粘贴"混在一起，且组内路径的归属本就是同一句话。分组后 `v3` 9 组、`v5` 7 组、`v11` 4 组、`v12` 3 组、`v14` 2 组、baseline 9 组。
- **`v1` 不假装**：它的母版 `v0` **没有配方声明**（不是注册任务）⇒ 谱系读数不可得。不判红、也不改用 stock 口径（那会把整条 main 线的遗产写成 v1 的 delta）。`[41]` 现在打印 `no difference declaration (hard A only): ['v1']`——"没有声明"与"声明且相符"在绿灯下读起来一样，所以必须打印。
- **身份字段仍按名过滤**（上一节定的）：`params_version` 是"这是哪条配方"，不写进 12 份声明。

**结果**

| 项 | 结果 |
|---|---|
| 硬 A / 硬 B | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 322 declared difference(s) against their own base)` |
| **反证（三条新分支各自打红后回滚）** | ① 路径放进别的作者组 ⇒ "while the elements that moved it are none"；② 空组 ⇒ "declares no path -- empty groups read as coverage"；③ `wiring` 认领组件拥有的路径 ⇒ "a component owns a name in that path -- name the component" |
| 旁证 | `[24]` `CFG_LOCK_OK (36 tasks)` · `[37]` `COMPONENT_OWNERSHIP_OK` · `[31]` `check_recipe_map` 通过 |

### 硬 B 追加（2026-09-18）：家族三条配方的差异声明

**性质**：补上"家族 4 条配方无 `diff.json`"这一项（4 条里 3 条可声明，1 条按先例不声明）。

| 项 | 内容 |
|---|---|
| 母版怎么定 | 按本仓既有决定（B4 段："`v1` 不假装"）：**根配方没有可用母版就不写声明**。`flat-v0` 的 base 就是家族接线本身 ⇒ 与 `v1` 同类，保持硬 A-only（闸门打印），**不写 stock 相对声明**（那会把整条线的遗产写成它一条的 delta）。其余三条的母版 = `flat-v0`（家族接线根，也是它们的 base） |
| 落子 | `versions/lizard/main/{rough-v0,curriculum-flat-v0,curriculum-rough-v0}/base.json`（`{"base": "flat-v0", …}`）+ `diff.json`（`format: 4`，按**作者集合**分组）：路径数 **6 / 11 / 16**（各含 1 条 agent `experiment_name`）。`EXPECTED_DIFFS` 钉三条 |
| 作者面（本批的实质） | 每个 env 路径**恰好一个 `_V0_*` 元素**认领；`wiring`、`components.X` 一次都没用上 ⇒ 家族这条线的 delta 完全由元素表达，正是"配方 = 声明"想要的样子 |
| 目录合法性 | `recipe_lines.discover()` 只把 `v\d+` 当版本、**其它子目录忽略**（不是报错）；`declared_diff()` 按 `line.root / <handle> / diff.json` 拼路径 ⇒ 新目录既不被当版本、也不被当线（`check_version_docs` 仍绿） |
| 证据 | `RECIPE_BUILD_OK (34 task(s) field-identical to the frozen golden; **355** declared difference(s))` = 322 + 6 + 11 + 16；`flat-v0`（且只有它，家族侧）仍在 hard A-only 行里；全量套件 `ALL_OFFLINE_CHECKS_PASSED (45/45)` |
| 反证（4 条，各自逐字节复原） | ① 把一条声明路径挪进别的作者组 ⇒ `empty groups read as coverage` + `… is attributed to 'v0_rough_terrain' while the elements that moved it are ['v0_rough_terrain_curriculum'] -- the list and the element list have drifted apart`；② 声明一条**不产出差异**的路径 ⇒ `1 declared env path(s) no longer differ from the base` + `… while the elements that moved it are none`；③ 删一条声明行 ⇒ `1 env field(s) differ from mother flat-v0 without being declared` + `declared 15 difference path(s), expected 16`；④ 删 `EXPECTED_DIFFS` 钉 ⇒ `has a difference declaration that no EXPECTED_DIFFS entry pins -- an unchecked declaration reads as a checked one` |

**边界**：`flat-v0` 仍 hard A-only（与 `v1` 同类，**不是缺口**）；三条声明写的是**路径集合**，它们读
dev yaml ⇒ 改某个值不动声明，改**形状**（新键/新差异）才动——若某条声明路径因此**不再有差异**，它按
`no longer differ` 红，那正是想要的。

### 生成方式，与它带来的**限制**

路径是**派生**的（量母版 → 重放元素 → 残差按所有权表分类），**理由是手写的**；生成器用完即删，不留在仓里。
这带来一个必须写下来的限制：**派生错误会同时出现在文件与闸门两侧**——两边互相印证不等于正确。
独立边界只剩硬 A（冻结 golden 钉住字段面）。已做的抽查：分组数与条数与独立量测一致；每组理由都能追到
该版 `PLAN.md`；人眼过了 v14（2 组）、v3/v5/v11/v12（分组与计数）、baseline（9 组）。

### 本节（追加）的边界

- **组件归属是"名字级"的**：一条路径里若两个组件各拥有一个名字（如 `observations.extero.lf_foot_ring`：`observations` 拥有 `extero`、`height_sensing` 拥有 `lf_foot_ring`），**点名任一个都过**；实际选谁由"最浅"启发式与手写理由承担。闸门只保证点名者确实拥有该路径里某个名字。这是本批最软的一处，已写在这里。
- `v1` 无声明（理由如上）；`v0/v7/v9` 无配方声明故不在链上。
- **未动**台账 #22（版本类体删除）：它卡在"锁的 `env_cfg_class` 字段命运"这个决定上，且会移动冻结工件，按那一条的要求**不与其他批次混提交**。
- 未跑全量套件端到端（并行批次仍在飞）。

## 证据引用

- 声明文件：`rl_exp/versions/lizard/main/vN/diff.json`（v2..v14）、
  `rl_exp/versions/lizard/main/{rough-v0,curriculum-flat-v0,curriculum-rough-v0}/diff.json` +
  `base.json`、`rl_exp/versions/lizard/baseline/v1/diff.json`。
- 闸门：`rl_exp/tools/verify/check_recipe_build.py`（`[41]`：`hard_b` / `covers` / `attribution` /
  `trace` / `EXPECTED_DIFFS` / `EXPECTED_COMPARED`）、`check_golden_frozen.py`（`[35]`：
  `FROZEN` 第 4 项 + `FROZEN_REVS` / `GOLDEN_FROZEN_SELFTEST_OK`）。
- 所有权表（组件归属的懒取来源）：`rl_exp/tools/verify/test_component_ownership.py`（`[37]`）。
- 反向验证：八处 / 五条 / 四条 / 三条破坏的读数均记在各节的**反证**行；逐字节回滚后复绿。
- 提交：`ed4d35b`（baseline 任务注册）、`384468e`（并行批次，本批）。
- 相关记录：硬 A 与锚 `2026-09-16-lizard-frozen-baseline-reanchors.md`；构建器与 `[41]` 纪律
  `2026-09-16-lizard-builder-hard-a.md`；入口切换与声明缺口清空
  `2026-09-17-lizard-entry-switch-and-declaration-gap.md`。

## 未覆盖边界

- **硬 B 不判"差异是否合理"**：只判"与基准的差异是否恰好等于声明"。也不判真环境行为（那要真跑）。
- **agent 侧的基准校验弱于 env 侧**：env 有 `wiring_is_stock_except` 的"基准确实是空"机器校验；
  agent 直接以框架 stock 为基准，**无此校验**（也没有中间接线类可夹带）。
- **`FROZEN_REVS` 不参与比较**：只喂 banner；比较只看 `FROZEN` 摘要。追加的四次合法重锚
  （逐字段证据）在 `2026-09-16-lizard-frozen-baseline-reanchors.md`。
- **派生带来的结构限制（最软的一处）**：路径由生成器派生、理由手写 ⇒ **派生错误会同时出现在文件与
  闸门两侧**，两边互相印证不等于正确；独立边界只剩硬 A。组件归属是"名字级"的（一条路径里两个组件
  各持一名时点名任一个都过）。
- **未闭合项**：
  - **`v1` 与 `flat-v0` 无差异声明**（按先例 hard A-only，**不是缺口**）；`v0/v7/v9` 无配方声明不在链上。
  - **版本类体与元素表仍并存**（过渡税）：等入口走到声明路径才能删类体；台账 #22 本轮未动。
  - `recipe.py` 不在 `[37]` 的 HOSTS 里；元素是第二类合法写者，"元素豁免"的形状未定义。
  - 各节多写着"**未跑全量套件端到端**"（并行批次仍在飞）；所跑为 `[41]` `[24]` `[35]` `[37]` `[31]`。
- **口径边界**：历史 `[N]` 是当次运行编号而非闸门身份；`RECIPE_BUILD_OK (… ; N declared
  difference(s))` 的 N 只在**当日 commit** 上成立（本记录横跨 33 → 76 → 79 → 322 → **355**）。
