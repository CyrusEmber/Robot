# 阶段 B 的冻结基线：锚、比较口径、四次合法重锚（2026-09-16 → 2026-09-18）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的：

| 来源 | 主题 |
|---|---|
| §B0 · 基线冻结（阶段 B 开工，2026-09-16） | 锚（阶段 B 的验收预期值）+ 比较口径 + 等价性验证 + B 期间冻结 + 边界 |
| §B1 · 组件库切片 1 的 `### B0 追加`①②③④ | 四次**合法重锚**的逐字段证据（该子节按主题归此） |
| §B1 · 组件库切片 2 的 `### B0 结论文更新：B3 前置已解锁` | 作废 §B0「硬 A 前置未满足」并给出解锁证据（该子节按主题归此） |

**本记录内部的前后作废关系（读结论以此为准，被作废的旧句保留作留痕）**：

- **`硬 A 前置未满足`（§B0 · 等价性验证的结论）被判`自此失效`** —— 作废它的是本记录末尾的
  「B0 结论文更新：B3 前置**已解锁**」小节（原文保留作留痕，以该小节为准）。这是本次 ACCEPTANCE
  分流里两条已知作废之一（另一条是 `硬 B 只覆盖 env cfg`，见
  `2026-09-17-lizard-hard-b-entry-switch.md`）。
- **四次重锚的性质不同，读的时候别混**：
  - **追加①** 是"搬家：内容零变化、摘要不变"（只改 `FROZEN` 表的**路径**）。
  - **追加②③** 是"改了一个列"（`env_cfg_class`）⇒ 摘要随之改变，但**配方内容一字未动**，**未跑 `--update`**。
  - **追加④** 是**配方内容真的变了**（`reset_robot_joints` 从 `None` 变成带参数的 term）⇒
    走唯一授权路径 `check_cfg_lock.py --update --line … --reason …`，**这才是 `--update` 的正当场景**。
- **§B0 只钉"预期值未被移动"**：它**不判 golden 是否正确**（那是硬 A 的活）。四次追加都不改变这条边界。

**与其它记录的关系**：

- `FROZEN` 表的第 4 项（baseline 线的锁）由
  `2026-09-17-lizard-hard-b-entry-switch.md` 的「B4 · 硬 B 加齿」③ 加入 —— 在那之前 baseline 锁
  **没有摘要看守**；本记录的 §B0 只钉 3 份文件。
- 重锚②③ 的触发动作（版本类体删除、家族四配方翻表）的证据在
  `2026-09-16-lizard-layout-migration-lifecycle.md`。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管 ⇒ 各节的成功行读数**只在当日 commit 上成立**。

## 验收条件

### §B0 锚（阶段 B 的验收预期值）

**性质**：`ARCH_PLAN.md` §2.4 阶段 B 的开工准备。**不改任何实现**：新增冻结闸门
`check_golden_frozen.py`（套件 `[35]`）+ 本节记录。开工第一件事是钉住"整改前 golden"——
它同时是硬 A 的比较对象与 B 期间被禁止移动的那份东西。

| 项 | 值 |
|---|---|
| 项目 rev | `020e6fb34034b2621f359e999cb441463b3127fc`（`020e6fb`） |
| 基线文件 | `versions/cfg_baselines.json` sha256 `b18a517c43ddef5f…`（764 B）；`versions/lizard/cfg_lock.json` sha256 `4326bd0bbf0b0b26…`（2,581,820 B）；`versions/lizard/parkour/cfg_lock.json` sha256 `6c60a92633235478…`（123,845 B） |
| 框架组合 | `isaaclab=28a37cecdd43\|rsl_rl=source:28a37cecdd43\|python=3.12.13` |
| 三文件状态 | `git status --porcelain` 对这三条为空 ⇒ 锚是**提交态字节**，不受并行批次未提交改动影响 |

### §B0 比较口径（硬 A 之前冻结，不由实现者事后选）

- **比较对象**：新构建器**构造**出的 cfg 树 vs golden 条目内的 `snapshot`；身份沿用 `check_cfg_lock` 的 `env_cfg_class` / `agent_cfg_class` + `digest`。B 期间**禁改比较器与规范化规则**——只禁 `--update` 挡不住"把标准搬到实现那一侧"。
- **缺失 ≠ 默认值**：沿用快照格式 2 规则——缺失写缺失哨兵，默认值写默认值。
- **顺序有语义**：obs 组 / term 序 / joint 序 / 地形列→combo 序均有序并纳入摘要。
- **浮点**：`repr` 往返，**无容差**；非有限值走标签，不用容差掩盖差异。
- **允许变化的路径**：B1 期间**期望为空**；真出现就逐条列**字段路径** + 旧值 + 新值 + 转换规则 + 不影响运行语义的验证，禁整字段或整子树豁免。

### §B0 B 期间冻结（机械看守，不靠约定）

禁 `cfg_lock --update`、禁手改锁、禁替换 golden、禁改比较器与规范化规则；由 `check_golden_frozen.py`
按摘要看守——自测 `GOLDEN_FROZEN_SELFTEST_OK`（改字节 / 删文件 / 不变三种都判过），实跑
`GOLDEN_FROZEN_OK (3 baseline file(s) unchanged since rev 020e6fb)`。**合法重基线** = 同一次改动里
同时改该闸门的 `FROZEN` 表与本节（附理由 + 逐字段差异审查）；只改一侧即判红。

## 结果

### §B0 等价性验证（本次实测，只读）

| 步骤 | 命令 | 结果 |
|---|---|---|
| 干净树再生 | `git clone --local --depth 1 E:\Robot E:\rl_b0_020e6fb`；`set PYTHONPATH=E:\rl_b0_020e6fb` + `set RL_ISAAC_ROOT=E:/IsaacLab`；`check_cfg_lock.py` | **34 任务 / 2 线**；**v11/v12 各 3 条路径漂移**：`env.curriculum.joint_sir.min_episode_frac: 0.5 -> <absent>`、`env.curriculum.joint_sir.require_survive: true -> <absent>`、`env.curriculum.joint_sir.unmeasured_prior: 0.5 -> <absent>` |
| 工作树 | `check_cfg_lock.py`（本仓） | **36 任务 / 3 线**，`CFG_LOCK_OK`（`baseline` 线随并行批次新增，属 A 带范围） |
| 字段归属 | `git grep -n unmeasured_prior HEAD -- rl_exp/tasks/teacher_mdp.py` | **空** ⇒ HEAD 无该字段；现只在未提交的 `teacher_mdp.py`（定义处 `:1026-1037`） |

**结论（硬 A 前置未满足，写死）**：现 golden 的 **v11/v12 条目只由未提交的工作树内容生成** ——
`cfg_baselines.json` 的 `created_rev 2a3883c` + `created_dirty: true` 由此得到具体解释：不是"戳不好看"，
而是这批条目**不可由任何 rev 取得**。⇒ **B1 可以开工**（B1 不改 cfg 内容，改动面与 golden 无关），
**B3 必须等该内容被提交后重跑上表第 1 行**，全绿才可比。否则硬 A 比的是一个谁也重建不出来的期望值。

> 上面这条结论已在同阶段被判**失效**，见本记录末尾「B0 结论文更新」。原文保留作留痕。

### B0 追加①：A0 迁移触发的合法重锚

| 项 | 值 |
|---|---|
| 触发 | A0 把主线搬进 `versions/lizard/main/`（git staged rename 34 项）：`versions/lizard/cfg_lock.json` → `versions/lizard/main/cfg_lock.json` |
| 证据 | 迁移前后 sha256 **完全相同** `4326bd0b…a12b`（2,581,820 B）⇒ 内容零变化、纯搬家；另两份基线摘要亦未变 |
| 处置 | 按本闸门声明的合法路径：同一次改动里改 `FROZEN` 表路径 + 补本条记录，**未改任何摘要值** |
| 残留 | 锁文件内部 `note` 仍写 `line 'lizard'`（改名收尾属 A0 清单），不影响条目内容，也不影响硬 A 的比较对象 |

### B0 追加②：版本类体删除触发的合法重锚（2026-09-17）

| 项 | 值 |
|---|---|
| 触发 | `PLAN.md` #22 step 2a：`env_cfg_class` 列记的是**注册表解析出的入口**，而注册表自 `2f67f4c` 起已解析 `recipe_tasks` ⇒ 列值为 `rl_exp.tasks.teacher_env_cfg:<类名>` 的 26 条（main 24 + baseline 2）在 step 3 删类之后指向不存在的类。本次把它**定点搬一行**到 `rl_exp.tasks.recipe_tasks:<同名>` |
| 与重锚①的区别 | ① 是"搬家：内容零变化、摘要不变"；本条**改了一个列**，两份文件摘要随之改变（这是必须记在案的那种重锚） |
| 逐字段证据 | 对两份锁做**递归 diff**（新旧 JSON 逐叶比较）：main **24 条**、baseline **2 条**，**全部且只有** `env_cfg_class` 一个叶变了；`digest`/`snapshot`/`version`/`agent_cfg_class` 逐条相等；`git diff --numstat` = `24 24` / `2 2`（一行一条，无其它行被触碰）。新列值逐个验证是 `recipe_tasks` 里真实存在的生成类 |
| 摘要 | main `8a004fab…bf76`（2,581,748 B，= 重锚前 2,581,820 − 72：24×3 字符）；baseline `9523583b…c682`（88,704 B）；其余两份基线未动 |
| 处置 | 按本闸门声明的合法路径：同一次改动里改 `FROZEN` 两行摘要 + 本条记录 + 理由（`check_golden_frozen.py` 表头注释）。**未跑 `--update`**、未重生成任何 `snapshot` |
| 一处自陈失误 | 首版重指脚本按 `read_text()` 的字符串算 sha256，而机器 `core.autocrlf=true`（工作树 CRLF）⇒ 表里先填的摘要是 LF 视图的哈希，`[35]` 当场红（`GOLDEN_FROZEN_DRIFT`）。文件本身没坏：读-写往返保住 CRLF，只有 26 行被替换。已按**磁盘字节**重算并复查 |
| `FROZEN_REVS` | 与摘要分两次提交：先落新摘要（本批），再另一次提交把 rev 钉到本批的提交号 —— 该列只喂 banner，但"这份字节来自哪个 rev"必须是真话 |

### B0 追加③：家族 8 条开发态配方翻表触发的合法重锚（2026-09-18）

| 项 | 值 |
|---|---|
| 触发 | 片 4a 把这 8 个任务的注册表与身份映射入口从 `lizard_env_cfg` / `rough_env_cfg` / `curriculum_env_cfg` / `curriculum_rough_env_cfg` 改指 `recipe_tasks` 的同名生成类；golden 那列随即指向旧模块 ⇒ `[41]` 立刻在这一列上具名报红 8 条（**这正是 2026-09-18 那条断言的用途**：翻表不再能把锁留在旧形状上） |
| 与①②的区别 | ② 是"26 条教师条目搬一行"；③ 是同一动作在**家族 8 条**上（含 2 条来自已删文件的模块名） |
| 逐字段证据 | 递归逐叶 diff：`main/cfg_lock.json` **8 个叶**变了、**全部且只有** `env_cfg_class`；`digest`/`snapshot`/`version`/`agent_cfg_class` 逐条相等；`git diff --numstat` = `8 8`。**独立交叉核对**：新值长度差之和 = **42**，与该文件字节差（2,581,748 → 2,581,706）**相等** ⇒ 没有第二个字节被动过 |
| 摘要 | `8a004fab…bf76`（2,581,748 B）→ `1643a755…7dc8`（2,581,706 B） |
| 处置 | 同②：同一次改动里改 `FROZEN` 一行摘要 + 本条记录 + 理由；**未跑 `--update`**、未重生成任何 `snapshot` |

### B0 追加④：baseline v1.1 复原关节复位触发的合法重锚（2026-09-18）

| 项 | 值 |
|---|---|
| 触发 | baseline 线 v1.1（`baseline/v1/PLAN.md` §修订）：`reset_robot_joints` 不再与其余五项随机化一起置 None，改为保留并钉 `position_range=(1.0,1.0)`/`velocity_range=(0.0,0.0)`。原因：本框架**资产级 reset 不写关节状态**（`InteractiveScene.reset` → `Articulation.reset` 只清执行器状态与两个 wrench composer，`isaaclab_physx/assets/articulation/articulation.py:222-246`），`reset_joints_by_scale` 是关节位置的**唯一**写入者（`envs/mdp/events.py:1924-2003`）⇒ 置 None 等于取消关节复位，终止/超时后的回合带上上一回合的关节位置与速度。机制、检测与通用规则见 `rl_exp/docs/pitfalls.md` P006 |
| 与①②③的区别 | ①②③ 是**入口列/模块名的搬家与翻表**：配方内容一字未动，动的只是 golden 记的入口。本条是**配方内容真的变了**（一个事件从 `None` 变成带参数的 term）⇒ 这是"配方修订 ⇒ golden 必须重锚"的正例，而不是搬家 |
| 逐字段证据 | 走唯一授权路径 `check_cfg_lock.py --update --line lizard/baseline --reason …`（锁头部 `reason`/`reason_at`/`reason_rev` 三行随之更新）。`git diff --numstat` = `51 7`：51 = 2 × 23（两条 entry 各一个 23 行的 `reset_robot_joints` 对象）+ 2（两条 `digest`，快照的派生值）+ 3（头部三行）；7 = 2 × 1（`reset_robot_joints: null`）+ 2 + 3。除这 7 处**无第三类叶**：`version`/`env_cfg_class`/`agent_cfg_class` 逐条未动，`snapshot` 内只有 `reset_robot_joints` 一个路径变化 |
| 独立交叉核对 | 文件 85,645 → 86,567 B（LF 视图：`git cat-file -s HEAD:` 与去 CRLF 后的 `len`），差 **+922 B = 44 行**（= 51 − 7）× ~21 B/行；磁盘字节 88,704 → 89,670（3,103 行 CRLF）⇒ 没有第二个字节被动过 |
| 摘要 | baseline `9523583b…c682` → `34e9acb1…9c94`；其余三份基线未动（`--update` 前跑 `check_cfg_lock.py --diff` 只报这两个 baseline 任务；`--diff` 命名空间里 `lizard/main`、`lizard/parkour` 无输出 ⇒ 嵌套 term 的原地修改未跨线泄漏） |
| 处置 | 按本闸门声明的合法路径：同一次改动里改 `FROZEN` 一行摘要 + 本条记录 + 理由（`check_golden_frozen.py` 表头注释第三段）。**本次跑 `--update` 是正当的**——配方内容变更本来就是它的场景（与①②③"未跑 `--update`"相反，那三条改的只是入口列）。`FROZEN_REVS` 该行随后一次提交钉 rev（同②：未提交前不留旧 SHA，填 `v1.1 (pending commit)`） |
| 端到端验证 | `reset_check.py --task Lizard-Baseline-Flat-v1`：修复前 C/D 红（reset 前后偏差**同为** 0.4089 rad、残余速度 9.3779 rad/s），修复后 `RESET_CHECK_OK`（8/8 项）；同一探针在 `Lizard-Rough-v14` 全绿 ⇒ 不误报。`baseline_probe.py` 改后 `BASELINE_PROBE_OK`（DR 名单去掉该项，改为断言存在 + func + 钉死，并补 `reset_base` 逐轴归零检查） |

### B0 结论文更新：B3 前置**已解锁**

| 步骤 | 结果 |
|---|---|
| HEAD | `c33bbf6`（A0 + 身份收编 + 套件规则已提交；工作树除一个 eval 产物目录外干净） |
| 字段是否已提交 | `git grep -n unmeasured_prior HEAD -- rl_exp/tasks/teacher_mdp.py` **有命中**（`:1026/1037/1076/1172`）⇒ B0 当时"只在未提交工作树里"的状态已结束 |
| 干净树再生 | 新克隆 `E:\rl_b1_check`（`PYTHONPATH` 指向克隆、`RL_ISAAC_ROOT` 补机器路径）+ `check_cfg_lock.py` → **36 任务 / 3 线 / `CFG_LOCK_OK`** |

⇒ **"整改前 golden 可由 rev 取回"成立**，§B0 结论里"硬 A 前置未满足"一条**自此失效**（原文保留作留痕，
以本条为准）。硬 A（B3）**技术上已可做**：比较对象 = 冻结摘要那三份文件，再生路径 = 任一干净 clone。

### §B0 机械看守实跑读数

`GOLDEN_FROZEN_SELFTEST_OK`（改字节 / 删文件 / 不变三种都判过）；
`GOLDEN_FROZEN_OK (3 baseline file(s) unchanged since rev 020e6fb)`；
四次重锚后由 `[35]` 复验（追加② 那次曾红一次，原因见其"一处自陈失误"行）。

## 证据引用

- 锚与看守：`rl_exp/versions/cfg_baselines.json`、`rl_exp/versions/lizard/main/cfg_lock.json`、
  `rl_exp/versions/lizard/parkour/cfg_lock.json`；闸门 `rl_exp/tools/verify/check_golden_frozen.py`
  （`FROZEN` / `FROZEN_REVS` 两表 + 键一致性校验 + `--self-test`）。
- 干净 clone 再生：`E:\rl_b0_020e6fb`（`git clone --local --depth 1`）、`E:\rl_b1_check`；
  命令 `check_cfg_lock.py`（`PYTHONPATH` 指向克隆、`RL_ISAAC_ROOT=E:/IsaacLab`）。
- 四次重锚的提交与逐字段证据：`git diff --numstat` / 递归逐叶 JSON diff 的读数见各追加行；
  触发动作的提交（A0 `9ee6773`、版本类体退役 `8f6ed6f`、家族翻表）见
  `acceptance/records/2026-09-16-lizard-layout-migration-lifecycle.md`。
- 追加④ 的机制与检测：`rl_exp/docs/pitfalls.md` P006、`rl_exp/tools/verify/reset_check.py`、
  `baseline_probe.py`。
- 解锁证据：`E:\rl_b1_check` 的 `check_cfg_lock.py` 输出；套件
  `rl_exp\tools\verify\run_offline_checks.bat` → `GOLDEN_FROZEN_OK`。

## 未覆盖边界

- **§B0 的边界（不得据本节宣称）**：
  - 本节只钉"**预期值未被移动**"：**不判 golden 是否正确**（硬 A 的活）、不判 `baseline` 线新增
    （2 任务、落点未跟踪）、36 vs 34 计数差异、参数加载读模块（`_load_params` 缓存/隔离）——均属 A 带。
  - 干净 clone 需补机器路径配置（`paths.yaml` 是机器本地文件、不在仓内，`RL_ISAAC_ROOT` 由环境变量给）
    ⇒ "可追溯"的准确含义是"**代码内容可由 rev 取得，主机路径由 `paths.yaml`/环境变量提供**"，
    不是"克隆即可跑"。
  - 本节只验读模式；**未跑全量套件端到端** ⇒ "`[35]` 与既有条目共存"按 A 带同口径记**未验证**。
- **每次重锚自带的残留/限制（逐条保留）**：
  - 追加①：锁文件内部 `note` 仍写 `line 'lizard'`（改名收尾属 A0 清单）。
  - 追加②：重指脚本按字符串算 sha256 的失误已修（`[35]` 曾当场红）；`FROZEN_REVS` 与摘要**分两次提交**
    （该列只喂 banner，不是比较规则的一部分）。
  - 追加③：与②同形；独立交叉核对只到"字节差 == 长度差之和"，未复核每个叶的内容语义。
  - 追加④：`--update` 会重写锁头部三行（`reason`/`reason_at`/`reason_rev`），那是记录面；
    `FROZEN_REVS` 该行在提交前填 `v1.1 (pending commit)`。
- **未闭合项（仍开着）**：
  - `baseline` 线的锁在本记录成文时**不在 `[35]` 的 FROZEN 表里** ⇒ "这条线的 golden 被移动"当时
    **没有摘要看守**；由 `acceptance/records/2026-09-17-lizard-hard-b-entry-switch.md` 的
    「B4 · 硬 B 加齿」③ 补上（该记录同时记着这是"最值钱"的一条债）。
  - A 带遗留项（`baseline` 线落点未跟踪、36 vs 34 计数差异、参数加载读模块）在本记录内**未收口**。
- **口径边界**：历史 `[N]` 是当次运行编号而非闸门身份；`GOLDEN_FROZEN_OK` 一类横幅的
  "3 baseline file(s)" / "4 baseline file(s)" 只在**当日 commit 的 FROZEN 表**上成立
  （第 4 项由后续记录加入）。
