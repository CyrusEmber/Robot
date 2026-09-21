# 声明式构建器与硬 A：机制、v5、v6–v14、`[41]` 的三条纪律（2026-09-16 → 2026-09-17）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的 §B3 四节：

| 旧节 | 主题 |
|---|---|
| §B3 · 硬 A：构建器机制 | 首个声明式子集（v1/v2 × train/play），机制三条 + 被证伪的假设 + 接手点 |
| §B3 · v5 元素化 | 奖励包 + 行 SIR 课程；首次暴露"声明路径带不走的 ClassVar" |
| §B3 · v6–v14 元素化 | 剩余九条配方，B3 收口（24/24 已声明） |
| §B3 收尾 · `[41]` 的三条纪律 | 覆盖钉数 / 缺口台账 / 逐步归属 —— 都是"闸门自己的牙" |

**本记录内部的前后作废关系**：

- 硬 A 首节里"未声明 ≠ 通过、v5 起尚未迁移"的**过渡状态**在后续两节逐版本收口；到 v6–v14 一节
  `pending()` 已空、输出里不再有 `not declared yet` 行 —— 以最后一节为准。
- 「硬 A 首节 · 边界」里"等 PLAY 元素化时补一条**类侧**断言（比两条路径的 ClassVar 取值）"
  在 v5 一节落地为**打印**形态（`[41]` 每次运行都打印，不判红），到收尾一节升级为**台账**
  （`EXPECTED_GAPS` 按 ClassVar 名给理由 + 到期）——以收尾一节为准。
- **ClassVar 缺口的两条读法不能混**（本记录与
  `2026-09-17-lizard-entry-switch-and-declaration-gap.md` 各有一半，两条都未在同一句里区分）：
  - 本记录 v6–v14 一节的边界写着「**ClassVar 真缺口未修**，且现在覆盖 v5–v14 全部 18 个任务」
    —— 那是**读取侧**（`REQUIRES_CURRICULUM_STATE` 的四个读者走 `getattr(type(cfg), …)`）。
  - `2026-09-17-lizard-entry-switch-and-declaration-gap.md` 的「收掉最后一条声明缺口」一节写着
    「**输出里不再有任何 ClassVar 缺口行**」—— 那说的是**台账打印**（`EXPECTED_GAPS` 清空），
    **不是**读取侧缺口被修。
  ⇒ 两句都对，指的不是同一件事；读"ClassVar 到底修没修"必须同时看这两条。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管（本记录横跨 41 → 43 条条目）⇒ 各节的成功行读数**只在当日 commit 上成立**；
「已修」与「仍是缺口」并存时，作废句一律从作废它的那节读。

**硬 A 的比较对象**（锚、比较口径、冻结看守与四次合法重锚）在
`acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`。

## 验收条件

### 机制（三条，缺一条就不是证明）

| 项 | 做法 |
|---|---|
| 期望值来源 | **冻结 lock** 从盘上读（写于构建器存在之前，不可能被它塑形）。构建器与自己比是恒等，这正是 §2.4 点名的第一号失败模式 |
| 被测对象 | `recipe.build(version)`，即**声明**，**不经版本类**（golden 闸门走类，本闸门走声明，两者互补） |
| 比较口径 | 复用 `check_cfg_lock` 的 `cfg_snapshot` + `walk_diff`：两套口径会让差异藏在缝里 |

### `[41]` 的三条纪律（收尾一节定的判据）

| 判据 | 之前 | 现在 |
|---|---|---|
| 覆盖钉数 | `compared` 只出现在结尾那句 OK 里，比较集缩小 = 更短的绿 | `EXPECTED_COMPARED = 24` + `EXPECTED_PENDING = ()` 双向钉住：声明被撤（比较集变小）或新配方未声明就进表（pending 变多）都红 |
| 缺口台账 | 缺口**每次打印**，永不见红；到期条件只写在散文里 | `EXPECTED_GAPS`：按 ClassVar 名给「理由 + 到期」；**台账外的新缺口即红**（一年后没人会逐条读打印），**台账里已消失的项也红**（陈旧项会盖住下一条） |
| 逐步归属 | 无：空转元素在字段比对上**完全隐形**（字段全等 ⇒ 零差异） | 回放 `trace`：每个声明元素**必须改到至少一个字段**；且该版与基线的**全部差异必须有人认领**（"没人改却变了" = 映射不是全部事实） |

## 结果

### 硬 A：构建器机制（首个声明式子集，2026-09-16）

**性质**：B3（硬 A）的**机制先行**。新增 `rl_exp/tasks/recipe.py`（`RECIPES` / `ELEMENTS` /
`build()` / `declared()` / `pending()`）与闸门 `check_recipe_build.py`（套件 `[41]`）。

**一条被证伪的假设（省掉一步）**：先前计划里的 **S1「把基类 body 抽成模块级函数」不需要**：
`params_version` 实测是**字段**（1.0 已证），因此 `LizardRoughTeacherEnvCfg(params_version="v14")`
就已给出"共享接线 + 按该版本解析的结构组件"，无需版本类、也无需搬 250 行 body。
⇒ 实际只需 S2（元素）+ S3（构建器 + 闸门）。

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A（首个子集） | `check_recipe_build.py` | **通过**：`RECIPE_BUILD_OK (4 task(s) field-identical to the frozen golden)` —— `v1`/`v2` × train/play 四个任务，**声明构建**与冻结 golden 的 `snapshot.env` 逐字段一致；未声明的 10 个版本被**打印**（`not declared yet (not compared)`），不是静默跳过 |
| 门 1 | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))`（本批未改任何 cfg） |
| 套件形状 | `check_suite_shape.py` | **通过**：`SUITE_SHAPE_OK`（41 条，单列表、每检查一进程） |

**边界**

- **未声明 ≠ 通过**：v5–v14 的 delta 仍写在子类里，本闸门对它们**不比较也不宣称**。`RECIPE_BUILD_OK` 的准确含义是"已声明的那几条配方逐字段一致"（当前 v1–v4）。
- **PLAY 的 `ClassVar` 不进快照**（格式 2 已定）：`REQUIRES_CURRICULUM_STATE` 之类构建器造不出来也验不了 ⇒ 等 PLAY 元素化时补一条**类侧**断言（比类与构建器两条路径的 ClassVar 取值），本闸门现在看不见这一面。
- v5 起尚未迁移；两条路径（类 + 声明）在过渡期并存，漂移面由 `[24]` + `[41]` 双闸覆盖。
- **下一步（S2）**：v3 的 delta 元素化并逐条收口 —— 速度课程 / `r_fc`（`feet_air_time=None` + `foot_clearance`）/ `c_k`（`init_ck` 事件）/ reset DR 三件；随后 v4（一行 headroom）、v5（奖励包 + 行 SIR）、v12（鲁棒性包 + 环噪声事件）、v13（核替换）、v14（`head_load`），v11（joint SIR 接线、参数格地形与粒子命令已在组件侧）。

**进度（逐版本，2026-09-16 当日）**

| 版本 | 状态 | 元素 |
|---|---|---|
| v1 / v2 | **已声明** | 无 delta（`elements: ()`） |
| v3 | **已声明** | `v3_contact_headroom` · `v3_speed_curriculum` · `v3_anti_drag_reward` · `v3_ck_clock`；PLAY = `play_drops_speed_curriculum` · `play_pins_full_command_range` |
| v4 | **已声明** | v3 四项 + `v4_stock_contact_stack`；PLAY 同 v3 |
| v5 | **已声明** | v3 四项 + `v4_stock_contact_stack` + `v5_drops_speed_curriculum` · `v5_reward_package` · `v5_sir_terrain_curriculum`；PLAY = `play_drops_sir_terrain_curriculum`（见下节） |
| v6–v14 | **已声明** | v6 `v6_spine_unlock`；v8/v10 无 cfg 增量（同 v6 表）；v11 `v11_joint_sir_curriculum`；v12 `v12_reset_robustness`；v13 `v13_miki_kernel`（从 v10 分叉）；v14 `v14_head_load`（见下下节） |

实测：`RECIPE_BUILD_OK (8 task(s) field-identical to the frozen golden)`（提交 `3360642`）。
**每加一个元素跑 `[24]` + `[41]`**。

**接手点（下一个会话）**

1. 读 `rl_exp/tasks/recipe.py`（元素 + `RECIPES` 表 + `build`）；读目标版本在 `teacher_env_cfg.py` 的子类 body 作为**搬运源**（逐行搬，不改语义）。
2. 加元素函数（`_doc(cfg)` 取该配方的参数文档），在 `RECIPES["v<版本>"]` 填 `elements` / `play_elements` / `train` / `play` 任务 id。
3. `build()` 已支持 `play_elements`（共享 PLAY 接线**之后**施加）。
4. `[41]` 会打印未声明版本 —— **不许**用"半套元素 + 声明成已迁移"骗绿：未声明的必须留 `None`。
5. 全绿后按仓库惯例提交（pre-commit 三闸会自动跑）。
6. **未合口**：`components.observations` 仍带三张手抄表（`PROPRIO_TERMS`/`BASELINE_PRIV_TERMS`/`SPEC_TERMS`），而 `tasks/obs_protocol.py` + `versions/obs_protocols.json` 已声明同一身份（按 task 带 `version`/`line`/`groups`/`terms`/`dropped_terms`）。现由 `check_obs_protocol` 互钉；合口 = 组件只留构造、按 (line, version) 读声明，删掉三张表。**是否合、何时合由用户定**（声明面属并行批次）。

### v5 元素化（奖励包 + 行 SIR 课程，2026-09-16）

**性质**：B3 的第二个声明式子集。改动面 = `rl_exp/tasks/recipe.py`（4 个元素 + `RECIPES["v5"]`）、
`check_recipe_build.py`（新增"声明路径带不走的 ClassVar"打印）；`teacher_env_cfg.py` 的
V5/V5_PLAY 子类**不动**（过渡期两条路径并存，漂移面由 `[24]` + `[41]` 双闸覆盖）。

**落地**

| 元素 | 内容 |
|---|---|
| `v5_drops_speed_curriculum` | `curriculum.speed_curriculum = None` |
| `v5_reward_package` | EP 核 → `track_lin_vel_xy_lin`（yaml `v5.track_goal_vel`）；`feet_slide` = `feet_slide_ck`；`undesired_contacts.func` = `undesired_contacts_ck`；`belly_contact_force`（yaml `v5.r_slip` / `v5.belly_contact_force`） |
| `v5_sir_terrain_curriculum` | `curriculum.terrain_levels` = `SIRTerrainCurriculumCfg`，8 参数全读 yaml `v5.terrain_curriculum` |
| `play_drops_sir_terrain_curriculum` | PLAY 侧 `terrain_levels = None` |

三处**不是搬运、是判断**（写下来，省得下次重新推）：

- **r_fc 符号修正不需要元素**：`v3_anti_drag_reward` 走 `_doc(cfg)` 按**本配方**的 yaml 读 `v3.r_fc`，v5 的 yaml 副本里就是 `-0.003`。迁移前它靠"V3 在 `params_version='v5'` 时执行"生效，迁移后靠"元素读该版本的文档"生效 —— 同一件事，少一个元素。
- **`v5_drops_speed_curriculum` 必须留，且必须排在 v3 元素之后**：`v3_speed_curriculum` 也在这份元素表里。删掉"装"只留"缺"看着更省，但 `speed_curriculum` 是**靠赋值才存在**的属性：省掉它，快照里就是"缺席"，而冻结配方记的是 `null`（1.1 明写 missing ≠ None），`[41]` 会当场红。**逐行照搬类链，语义才等价**。
- **v3/v4 的 PLAY 元素不进 v5**：`play_drops_speed_curriculum` 会去删一个 v5 本就没有的课程（无害但说谎），`play_pins_full_command_range` 会把范围钉成 `(-1, 5)`，而冻结的 v5 PLAY 是 yaml 的 `(0, 3)`——两者都会让 `[41]` 红。这是"元素表按配方写、不按版本链继承"的直接好处。

**结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (10 task(s) field-identical to the frozen golden)` —— v5 train/play 加入后仍逐字段一致；未声明的 7 个版本继续被打印 |
| 门 1 | `check_cfg_lock.py`（套件 `[24]`） | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))`（本批未改任何 cfg） |
| 单写者 | `test_component_ownership.py`（套件 `[37]`） | **通过**：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s))` |
| golden 摘要 | `check_golden_frozen.py`（套件 `[35]`） | **通过**：`GOLDEN_FROZEN_OK`（3 份基线文件自 `020e6fb` 未动） |
| 旁证五闸 | `check_obs_layout` · `check_dr_parity` · `check_reward_v13` · `check_configclass_fields` · `check_suite_shape` | **全绿**（v5 obs 381 与冻结一致；v5/v10 的 EP 核冻结断言未动；`test_v5_rewards` 4 例 + `test_v5_terrain_sir` 9 例全过） |

**新增的可见缺口：声明路径带不走的 ClassVar**

`[41]` 现在**每次运行都打印**（不是判红）：

```
classvar the declaration cannot carry (no class to hold it): v3/play PLAY_PINS_COMMAND_RANGE: True != False
classvar the declaration cannot carry (no class to hold it): v4/play PLAY_PINS_COMMAND_RANGE: True != False
classvar the declaration cannot carry (no class to hold it): v5/train REQUIRES_CURRICULUM_STATE: True != 'not stated'
classvar the declaration cannot carry (no class to hold it): v5/play REQUIRES_CURRICULUM_STATE: False != 'not stated'
```

（以上是本条提交当时的原样输出。v6–v14 声明完后同样的行变成 18 行、措辞也改短，遂按**缺口类**聚合——下一节记的是新格式。）

这是 `[41]` 原有纪律（"未声明 ≠ 通过"要打印）扩到 ClassVar 面：`build()` 返回**共享基类**实例，
而 `ClassVar` 是"关于配方的声明"，快照格式 2 把它排除 ⇒ 声明路径**结构上**没有地方承载它。
两个名字的后果不同：

- `PLAY_PINS_COMMAND_RANGE` 是**构造期**读取（基类 `__post_init__` 用它选范围），声明路径复现的是**效果**而非声明（`play_pins_full_command_range` 事后写同一个范围），字段面已等价 —— 打印出来是留痕，不是缺口。
- `REQUIRES_CURRICULUM_STATE` 是**运行期**读取（`curriculum_state.requires_resume_state` 与 `runrecord.manifest` 都走 `getattr(type(cfg), ...)`），声明路径给不出 `True`，字段面也补不回来。**这是真缺口**。当前被 `need = requires_resume_state(env) or bool(covered)` 兜住（行 SIR 是注册 term，`covered` 非空 ⇒ 缺载荷 / 缺 slot 时**仍然硬失败**），退化的只有三处：声明语义本身、"声明了却没收集到状态"那条 save 守卫、以及 manifest 里那条记录。**修法在读取侧**（读实例，或按 `(line, version)` 读声明表），落在并行侧 C 的 lane。本次按用户拍板（2026-09-16）**先让它可见，不假装已修**；B3 原计划里"等 PLAY 元素化时补一条类侧断言（比两条路径的 ClassVar 取值）"由此落地为**打印**形态。

**边界**

- `RECIPES["v5"]` 的 train/play 任务 id 是**写出来的**，不从版本串推 —— 改名不能静默把这个闸门指向空。
- **`recipe.py` 仍不在 `[37]` 的 HOSTS 里**：元素会写 `commands.base_velocity`（`components` 拥有的名字），`play_pins_full_command_range` 就是这么写的。把它加进扫描表会立刻红 —— 元素是独立于 `teacher_env_cfg.py` 的第二类合法写者，要不要扩 `[37]` 的范围，得先定义"元素豁免"的形状，本轮不动。
- **`FILEMAP.md` 只补 `[41]` 新打印的那一句**：落笔时它正带着并行侧 obs_protocol 的在飞改动（连同 `runrecord/manifest.py`），整份 `git add` 会把别人的半成品写进我的提交；那批他们随后自行提交（`38d80a6` / `a7e2b27` / `9afc9b8`），补记随之落在一个小提交里。v5 的**元素清单是状态**（上面进度表），代码地图只描述机制，不抄第二份。
- **未合口（本轮定：不合；2026-09-17 追记：用户已定"要合"，条件已满足）**：`components.observations` 的三张手抄表 vs `versions/obs_protocols.json`。理由：`obs_protocol` 自称"只声明 identity、不构建 config"，而 `check_obs_protocol` 是拿声明去比**构造出来的** cfg；让 `components.observations` 反过来读它，闸门就变成声明比声明 —— B3 点名的第一号失败模式（与自己比恒等）。且声明侧仍在飞。**追记**：声明侧已落定（`38d80a6` 的 3.1d + `9afc9b8`），"等他们 3.1d 落定后再议"这一条件已满足；合口的身份问题与代价见 §3.1 第 11 条（**不需要新加身份参数**；代价是 `--live` 退化为转换一致性检查、3.1e 变承重）。落地须在 builder 改动静下来之后、一次落。
- 仍未声明：v6 · v8 · v10 · v11 joint SIR 接线 · v12 鲁棒性包 + 环噪声事件 · v13 核替换 · v14 `head_load`，各自还需 PLAY 元素。**每加一个元素跑 `[24]` + `[41]`**。

### v6–v14 元素化（剩余九条配方，B3 收口，2026-09-16）

**性质**：B3 收口。改动面 = `recipe.py`（5 个元素 + delta 常量链 + 一个 `mdp` import）、
`check_recipe_build.py`（ClassVar 缺口按类聚合）；`teacher_env_cfg.py` 一字未动。

**落地**

| 版本 | 新增元素 | cfg 增量是什么 |
|---|---|---|
| v6 | `v6_spine_unlock` | 1 行：`action.spine_scale`（本版本 yaml 0.25；v1–v5 仍 0.0，因为值来自各自文档） |
| v8 | — | **0 行**：+180° 翻转与 26 关节改名在资产面，yaml 的名字迁移由基类按**本版本**文档读 |
| v10 | — | **0 行**：tilt 删除是 yaml 标志（`v10.tilt_terminate: null`），`components.terminations` 早已是唯一写者 |
| v11 | `v11_joint_sir_curriculum` | 行 SIR → 联合粒子（`JOINT_SIR_TERM`）；参数格地形与粒子命令 term 在 `components.TERRAIN_BY_RECIPE` / `COMMAND_RANGE` |
| v12 | `v12_reset_robustness` | 三个 `reset_joints_by_offset` + base 复位范围 yaml 化 + 摩擦 dip + 环噪声事件（extero 四项的 func/参数归 `components.observations`） |
| v13 | `v13_miki_kernel` | 线性核 → Miki 对称核 |
| v14 | `v14_head_load` | 头承力罚（`roll_over` 终止归 `components.terminations`） |

PLAY：v5–v10 与 v13/v14 用 `play_drops_sir_terrain_curriculum`；v11/v12 换成 `play_drops_joint_sir_curriculum`。

**三个判断**

- **delta 写成链，v13 从 v10 分叉**：`_V3_DELTA → _V4 → _V5 → _V6`，v11/v12 接 `_V6`，**v13 也接 `_V6`**（V13 的基类是 V10，不是 V12）——元素表按**类链**写，不按版本号顺序。每个 delta 只写一次：v8/v10"与 v6 同"是一个对象的事实，不是三份副本要对齐。
- **v8/v10 的空增量用 v6 的表，不是 `None`**：声明的是"除了 v6 的 delta 没有别的"，不是"未声明"。`None` 留给真正没搬的版本——现在一个都没有。
- **PLAY 守卫必须跟课程换名**：v11/v12 的课程是联合项，照抄 v3 那对 PLAY 元素会去 null 一个不存在的 `terrain_levels`（无害），却**留下**联合项在跑（有害：评估会按 episode 重派起点与速度）。冻结的 v11/v12 PLAY 只 null 联合项、把粒子命令 term 留着让它自己回退到均匀范围 —— 元素照此。

**结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A（全部配方） | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (24 task(s) field-identical to the frozen golden)` —— 12 条配方 × train/play 全部**声明构建**与冻结 golden 逐字段一致；`pending()` 已空，输出里不再有 `not declared yet` 行 |
| 门 1 | `check_cfg_lock.py`（套件 `[24]`） | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))`（本批未改任何 cfg） |
| 单写者 | `test_component_ownership.py`（套件 `[37]`） | **通过**：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s))` |
| golden 摘要 | `check_golden_frozen.py`（套件 `[35]`） | **通过**：`GOLDEN_FROZEN_OK`（3 份基线文件自 `020e6fb` 未动） |
| 旁证 | `check_obs_layout` `[8]` · `check_dr_parity` `[2]` · `check_pxr_leak` `[14]` · `check_reward_v13` · `check_terminations_v10` · `check_terminations_v14` · `check_suite_shape` · `test_joint_sir`（12 例）· `test_v12_noise` | **全绿**（v10/v13/v14 的冻结断言未动 —— 因为版本类一字未改） |

**ClassVar 缺口打印改为按类聚合**

```
classvar the declaration cannot carry: PLAY_PINS_COMMAND_RANGE: True != False -- in v3/play, v4/play
classvar the declaration cannot carry: REQUIRES_CURRICULUM_STATE: True != 'not stated' -- in v5/train, v6/train, v8/train, ...
classvar the declaration cannot carry: REQUIRES_CURRICULUM_STATE: False != 'not stated' -- in v5/play, v6/play, v8/play, ...
```

缺口性质与修法不变（见上节）。改的只是可读性：每条配方一行会变成 18 行同文，而"每次跑都刷屏的同文"
恰好会被当成噪音跳过，聚合后 3 行，仍然每次跑都出现。

**边界**

- **24/24 已声明，`[41]` 仍保留 `not declared yet` 那条打印**：下一条新配方（v15+）填进 `RECIPES` 而没写元素时，是被打印，不是静默通过。闸门不因"当前全绿"而收掉这条纪律。
- `recipe.py` 新增 `isaaclab_tasks...velocity.mdp` import（v12 的 `reset_joints_by_offset` 用）。`[14]` 复跑仍 pxr-clean：与 `teacher_env_cfg.py` 同一模块，没有新增链路。
- `recipe.py` 仍不在 `[37]` 的 HOSTS 里（理由见上节边界）。
- **ClassVar 真缺口未修，且现在覆盖 v5–v14 全部 18 个任务**：读取侧一改，18 个任务一起受益、也一起被验。**C2/C3 的 launcher 把 `build()` 变成默认训练路径之前必须落**，否则这批配方的续训声明对 manifest 与 save 守卫是隐形的（安全性仍由 `covered` 项兜住，见上节）。
- obs 三表合口本轮仍未动（上节已定）。
- 本节只证"声明与冻结 golden 逐字段一致"；**不证**元素在真环境下的行为等价（那是 C 层真跑的事），也不证 PLAY 的 `ClassVar` 面（见上节缺口）。

### `[41]` 的三条纪律（覆盖钉数 / 缺口台账 / 逐步归属，2026-09-17）

**性质**：改动面 = `recipe.py`（新增 `base_cfg(version)`；`build()` 增可选 `trace=`，按序记下每一步
`(name, callable)`，让读者**回放**而不是复述顺序 —— 复述顺序就是下一个漂移面）、`check_recipe_build.py`
（三条判据 + 缺口按 ClassVar **名**入账）、`FILEMAP.md`。**不动任何配方的字段内容**（24/24 仍逐字段一致）。

**检查与结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 硬 A（全部配方） | `check_recipe_build.py`（套件 `[41]`） | **通过**：`RECIPE_BUILD_OK (24 task(s) field-identical to the frozen golden)`，单跑 8.7 s（预算 25 s）；两条台账条目按名字打印，附「why / due」 |
| 逐步归属反证 ①（空元素） | 进程内塞 `ELEMENTS['_noop'] = lambda cfg: None` 并挂进 v14 元素表 | **FIRED**：`element '_noop' changes nothing` |
| 逐步归属反证 ②（无主字段） | 包一层 `build()`，在返回值上多写一个字段（`seed`） | **FIRED**：`1 field(s) changed with no declared element behind them: ['seed']` |
| 覆盖钉数反证 | 把任一版本 `elements=None`（或从 `RECIPES` 撤一条） | 由构造保证：`compared` 变 23 ≠ 24 **且** `pending` 非空 ⇒ 两条独立红 |
| 旁证 | 全量套件 `offline_suite.py` | **43/43 通过**（wave 188 s / 预算 400 s） |

**边界（写清楚，别把绿读成更多）**

- **归属 ≠ 行为等价**：它证的是"声明的每一步确实动了它该动的字段、且没有无主差异"，**不证**这些字段在真环境里产生同一行为（C 层真跑的事）。
- **`REQUIRES_CURRICULUM_STATE` 这条真缺口未修**：本轮只是给它上了台账与到期条件（"`build()` 变成默认训练路径之前"）。读取侧的修法（载体决定 + 拆 `declared()`/`needs_restore()` + 启动时校验"声明 True ⇔ 接线非空"）仍在他们那侧，属**行为面**；本节不主张已修。
- **save 守卫的合取今天不可达，所以没动**：只有一处类声明 True（`teacher_env_cfg.py:1083`），而所有清空课程项的元素都是 `play_drops_*`（PLAY 侧，且 PLAY 类显式声明 False）⇒ `(声明 True ∧ 接线空)` 现不存在。**注意**：删掉那个合取是**反向风险**（声明 True 却无 term 的配置会改成"训练几小时后 save 时才炸"），必须与"启动时校验"一起做，不能单删。
- 归属判据只覆盖 `train`/`play` 两条已声明路径；元素**执行顺序**由 `trace` 给出（不再由检查器复述），所以将来 `build()` 改序，判据跟着走而不是失效。
- 本轮不新增套件条目：三条判据都落在既有 `[41]` 内，不付第二份 import 税。

## 证据引用

- 构建器与判据：`rl_exp/tasks/recipe.py`（`RECIPES` / `ELEMENTS` / `build()` / `base_cfg()` /
  `declared()` / `pending()` / `trace`）、`rl_exp/tools/verify/check_recipe_build.py`（套件 `[41]`）。
- 硬 A 的锚、比较口径、冻结看守与每次重锚：
  `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`。
- 组件库（元素写到的组件拥有的名字）：`acceptance/records/2026-09-16-lizard-component-library-b1.md`。
- obs 三表 vs `obs_protocols.json` 的合口条件：见
  `acceptance/records/2026-09-16-lizard-obs-protocol-gate.md`（§3.1 第 11 条）。
- 逐元素归属的替代来源（翻表后）：各配方的 `rl_exp/versions/lizard/main/vN/diff.json`，
  见 `acceptance/records/2026-09-17-lizard-entry-switch-and-declaration-gap.md`。
- 提交：`3360642`（v5 起的元素化批次）；套件整跑 `offline_suite.py` → `43/43`。

## 未覆盖边界

- **未声明 ≠ 通过**（三节一致）：`RECIPE_BUILD_OK` 只对**已声明**的配方成立；`[41]` 永远保留
  `not declared yet` 的打印，闸门不因"当前全绿"收掉这条纪律。
- **PLAY 的 `ClassVar` 面看不见**：`build()` 返回共享基类实例，声明路径结构上没有地方承载
  `ClassVar`；`PLAY_PINS_COMMAND_RANGE` 是构造期读取（字段面已等价，打印只是留痕），
  `REQUIRES_CURRICULUM_STATE` 是运行期读取（**真缺口**，修法在读取侧，属行为面）。
- **ClassVar 真缺口当日未修**，覆盖 v5–v14 全部 18 个任务；**必须在 C2/C3 把 `build()` 变成默认
  训练路径之前落**。台账（`EXPECTED_GAPS`）只把它变成"可见 + 有到期条件"，**不是**已修；
  后续记录里"不再有任何 ClassVar 缺口**行**"说的是台账打印，别读成读取侧已修。
- **归属 ≠ 行为等价**：本记录只证"与冻结 golden 逐字段一致 + 声明与字段归属自洽"；
  不证元素在真环境下的行为等价。
- **`recipe.py` 不在 `[37]` 的 HOSTS 里**：元素是第二类合法写者，"元素豁免"的形状未定义 ⇒ 开项留到最后。
- **obs 三表合口未做**：条件已满足（用户已定"要合"），但落地须在 builder 改动静下来之后、一次落，
  且合口后 `--live` 退化为转换一致性检查（3.1e 转为承重）。
- **save 守卫的合取不可单删**：删它是反向风险（把错误推迟到训练几小时后 save 时），必须与"启动时校验"一起做。
- **口径边界**：历史 `[N]` 是当次运行编号而非闸门身份；`RECIPE_BUILD_OK (N task(s) …)` 的 N
  只在**当日 commit** 上成立（本记录横跨 4 → 8 → 10 → 24 条任务）。
