# 配方线生命周期与 A0 布局迁移 / 版本类体退役（2026-09-16 → 2026-09-18）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的以下旧节：

| 旧节 | 主题 |
|---|---|
| §2.1 | 配方线生命周期（离线半，2026-09-16） |
| §2.1b | 配方身份映射（离线，2026-09-16） |
| §2.4 | A0 布局迁移（`ARCH_PLAN` 2.1a；声明先于执行）+ 独立审核与修复 |
| §2.4 收尾 | 版本类体删除 + 硬 A 保真比较退役（`PLAN.md` #22，2026-09-17）+ 追加（2026-09-18）三节 |

**本记录内部的前后作废关系（读结论以此为准，被作废的旧句保留作留痕）**：

- §2.1 的 **L06 行与「时钟无关性」一条**在 2026-09-17 被判**作废**（弃用声明层删除 ⇒ 闸门无时钟，
  反证集由 23+1 例变为 16 例）；L01/L05 行的规则仍有效（`index:` 打印的字段少了 `revision`，该字段同轮删除）。
  作废它的**生命周期收缩**节正文归 `2026-09-17-lizard-entry-switch-and-declaration-gap.md`，本记录只留作废声明。
- §2.1 / §2.1b 的「L02/L03/L04 与 L05/L06 的入口侧未跑 ⇒ 未知」是**当日**口径；入口侧的后续读数
  （含 L02 通过、parkour 退休）归 `2026-09-17-lizard-entry-switch-and-declaration-gap.md`，以那一条为准。
- §2.4 的两段「回填」是同一动作的前后两稿：`### 回填（执行后）` 为空标题，`### 回填（执行后，2026-09-16）`
  是实稿；本记录只留实稿，不保留空标题。
- §2.4 收尾 的 step 2a（26 条 `env_cfg_class` 定点搬移）**逐字段证据在 B0 追加②**，该子节按主题归
  `2026-09-16-lizard-frozen-baseline-reanchors.md`；追加③ 的家族翻表重锚同上（B0 追加③）。
  两处引用在这里保留指针，不复制摘要。
- §2.4 收尾「边界」里的两条被后节补上：`[21]` 的 PLAY 规则与 v4 声明口径在「执行中发现」里已改并补反证；
  `env_cfg_class` 列**当时无闸门看守**，由「追加（2026-09-18）」补上。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管 ⇒ 各节的成功行读数**只在当日 commit 上成立**（本记录横跨 31 → 47 条条目）；
「已修」与「仍是缺口」并存时，作废句一律从作废它的那节读。

## 验收条件

### §2.1 前提

| 项 | 值 |
|---|---|
| 项目 rev | `2a3883c`；**工作树未冻结** —— 另有并行批次的未提交改动（`rl_exp/tasks/*.py`、`cfg_lock.json`、`FAMILY.md`、`PLAN.md`、`check_cfg_lock.py`、`check_dr_parity.py`、`check_version_docs.py`、`run_offline_checks.bat`，以及新增的 `recipe_lines.py`、`versions/cfg_baselines.json`、`versions/lizard/parkour/cfg_lock.json`、`versions/lizard/v15/`）。本批改动 = 新增 `versions/lines.json`、`check_recipe_registry.py`、`test_recipe_registry_gate.py`；改 `run_offline_checks.bat`（`[29][30]`）与 `ARCH_PLAN.md` |
| 任务 id | 不适用（离线闸门，不构造 env；线由 `recipe_lines.discover()` 发现） |
| 设备 / env 数 / seed | 不适用（无 sim、无 env、无随机源） |
| 框架组合 | 未绑定（本批为纯文本 gate，不读 isaaclab/rsl_rl 版本） |
| 预设容差 | 无（离散判定：每条规则红或绿） |

**§2.1 范围限定**：只覆盖 `ARCH_PLAN.md` §2.1/§2.2 的**离线部分**（L01 全部、L05/L06 的离线半边）。
L02/L03/L04 与 L05/L06 的入口侧**未跑，记未知**；旧入口尚未接线 ⇒ 只能声明"新入口限制有效"，
不得据本批宣称 Step 2 通过。

### §2.1b 前提

| 项 | 值 |
|---|---|
| 项目 rev | `a5a7fab` + 未提交改动（本批 = 新增 `versions/recipes.json`、`check_recipe_map.py`、`test_recipe_map_gate.py`；改 `run_offline_checks.bat`、`FILEMAP.md`、`ARCH_PLAN.md`）。工作树**仍未冻结**：并行批次 19 项未提交，锁 v3 迁移进行中 |
| 任务 id | 全部 34 个注册任务（v0 家族 8 + teacher v1–v14 共 24 + parkour 2） |
| 设备 / env 数 / seed | 不适用（无 sim、无 env、无随机源） |
| 框架组合 | 未绑定（纯 stdlib：`ast` 解析注册模块，不 import registry、不 import isaaclab） |
| 预设容差 | 无（离散判定） |
| 声明真值来源 | 各任务 `params_version` 取自**现行** `cfg_lock` 条目（主线 32 + parkour 2）：teacher = `vN`、parkour = `v1`、v0 家族 = `None` |

**§2.1b 范围限定**：补 §2.1 的另一半 —— `任务 ID → 配方 + 修订 → 配置入口` 的显式映射。
仍只覆盖离线部分；入口侧（L02/L03/L04）未跑，同 §2.1 记**未知**。

### §2.4 声明的允许变化清单（执行前）

A0 会触碰 16 个冻结物，所以先落"允许变化清单"**再执行** —— 否则 `--update-locks` 之后的"全绿"
可能只是把意外变化一并接受。本节分两段：声明（执行前落盘）与回填（执行后补）。

| 对象 | 允许的变化 | 不允许的变化 |
|---|---|---|
| 17 个参数文件（dev 1 + 冻结 16） | **文件名** `lizard_params.yaml` → `main_params.yaml`（`recipe_lines` 规则要求基名 = 线名） | 内容任何一个字节 |
| 16 个冻结 `vN/asset_lock.json` | **自身 yaml 的仓库相对路径键**（`versions/lizard/vN/lizard_params.yaml` → `versions/lizard/main/vN/main_params.yaml`） | 资产 sha256（`lizard.urdf` / `lizard.usda` / meshes）、键序、其余键、键的增删 |
| 线级 `cfg_lock.json` | **位置** `versions/lizard/` → `versions/lizard/main/`；内容**零变化** | 任何条目或摘要变化。若真出现，说明快照记录了路径 ⇒ 必须逐字段审查并在此单独声明后才接受 |
| 16 个 `vN/base.json` | **无变化**（规则是"线内裸 `vN` 先命中本线"，`main/v14` 写 `v13` 仍解析到 `main/v13`） | 任何变化 |
| `vN/` 内的 PLAN/NOTES/yaml 正文 | **无变化** | 任何变化 |

### §2.4 前置检查（执行前，已过）

| 项 | 结果 |
|---|---|
| A0 写入集 ∩ 脏集 | **空** —— 3 个脏文件与本迁移无关，脚本明确列为"ignored on purpose" |
| 被搬目录内未跟踪文件 | 无（v15 已于 2026-09-16 入索引，`baseline/` 已提交且不在移动集） |
| 计划移动 | **34 项**：16 个版本目录 + 线 `cfg_lock.json` + `lizard_params.yaml` + 16 处改名 |

### §2.4 收尾 前提

| 项 | 值 |
|---|---|
| 项目 rev | 起点 `8f6ed6f`（step 1 已提交）；本批在其上，工作树另有并行批次已提交的文档改动（无冲突面） |
| 命令 | `rl_exp\tools\verify\run_offline_checks.bat`；单跑 `check_recipe_build.py`、`_b3_remove_version_classes.py`、`check_golden_frozen.py` |
| 设备 / env 数 / seed | 不适用（离线；构造 cfg，不 `gym.make`、不起 sim） |
| 容差 | 无（字段逐叶比对；摘要与字节相等） |

## 结果

### §2.1 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| L01 显式身份 | `python rl_exp\tools\verify\check_recipe_registry.py` | **通过**：`recipe lines discovered: 2 ['lizard', 'lizard/parkour']`、`index: lines.json revision=1 entries=2`、`lifecycle consistent`。未登记线、悬空线、第三态 `status`、缺字段、夹带 run 字段均被拒绝 |
| L05 记录冻结（离线半边） | 同上 | **通过**：索引入口键白名单（夹带 run-scoped 字段即红）；生命周期不是 env/agent cfg 的输入 ⇒ 不进配方摘要。"启动后改目录，原 T1 不变"需 manifest 接线 ⇒ **未知** |
| L06 迁移生效（离线半边） | `python rl_exp\tools\verify\test_recipe_registry_gate.py` | **通过**：23 例反证 + 1 例时钟无关性全部着火。提示期（`active` + 声明 + 条件未满足）判绿、`retired` 且条件已满足判绿、提前退休判红、到期仍 `active` 判红、自由文本条件判红。"提示期放行结果与无声明 `active` 逐项相同"需入口侧 ⇒ **未知** |
| 反证先行 | 同上 | 每条拒绝都由合成树 + 合成索引驱动，未触碰真实索引；`retire_not_before` 为 revision 型时同一索引在两个不同日期判据一致（无时钟依赖） |

> **2026-09-17 收缩**：上表 L06 行与"时钟无关性"一条**作废**（弃用声明层删除 ⇒ 闸门无时钟，反证集由 23+1 例变为 16 例；作废它的「生命周期收缩」节正文归 `2026-09-17-lizard-entry-switch-and-declaration-gap.md`）。L01/L05 行的规则仍有效（`index:` 打印的字段少了 `revision`，规则未变 —— 该字段同轮删除）。

**§2.1 结论与边界**：

- **通过**：L01（身份解析与拒绝）；L05/L06 的离线半边。
- **未知**：L02（入口执行）、L03（历史续训）、L04（历史兼容）、L05/L06 的入口侧 —— 全部需 §2.2 接线，属阶段 C。
- **未做**：A3（`check_cfg_lock` 身份改消费显式映射）等锁格式 v3 结构冻结后重读；A0（布局改造 `main/` + `baseline`、参数文件按闸门改名、`is_main_line` 判据更换）等并行批次落地。
- **口径**：本批**未跑全量套件**（`run_offline_checks.bat` 端到端），只跑了新增两条 ⇒ `[2][12][24][28]` 与新增条目的共存**未在本批验证，记未知**。
- **证据**：gate 脚本 + 上表命令（未另存日志文件；`verify_logs/` 现存的是套件整跑日志）。

### §2.1b 检查与结果

| 编号 | 命令 | 结果 |
|---|---|---|
| L01 身份映射 | `python rl_exp\tools\verify\check_recipe_map.py` | **通过**：`recipes declared: 34 | task mappings: 34`，与 `gym.register` 逐字一致（env/agent 入口、任务键集、line 引用） |
| 反证 | `python rl_exp\tools\verify\test_recipe_map_gate.py` | **通过**：16 例地图反证 + 6 例绑定反证全部着火，外加"从真实 `tasks\__init__.py` 读出 34 个任务" |
| L01 配置侧绑定（原计划归 A3） | `E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\check_recipe_map.py --bind-config` | **通过**：34 个声明的 `env_cfg_entry` 逐个导入并**构造**实例，其 `params_version` 与 `legacy_task_version` **34/34 一致**（teacher = `vN`、parkour = `v1`、v0 家族 = 双向 `null`）。类属性读不到（1.0 已证）故必须构造；构造失败记红、不记跳过 |

绑定不需要锁文件，因此**未等锁 v3 冻结即可执行** —— 早先"等 v3 结构冻结"的判断是错的，已纠正。
绑定落地后 `check_cfg_lock.py` 里按任务 id 推断版本的旧校验（`_TASK_VERSION`）成为冗余：
`id 分词 == declared`（本闸门）+ `declared == params_version`（本闸门）⇒ 传递出 `id 声明 == 实际版本`。
该文件属并行批次，删除留给 A3 收口。

**本批修正（两处，均由反证抓到）**：

- **双向校验写错**：首版判"任务 id 带 `-vN` ⇒ 声明必须等于 vN" ⇒ 8 个 v0 家族任务被误判。它们的 `params_version` 实测是 `None`，**id 后缀 `v0` 不是配方声明**。改为单向：声明了版本就必须是任务 id 的 dash 分词；并加 `v1` 不被 `Lizard-Rough-v14` 满足的陷阱反证。
- **解析器读空注册表**：首版 `registered()` 只读位置参数，而 `gym.register` 的 `id` 是关键字参数 ⇒ 注册表读成空、**闸门静默通过**。由"真模块读出 34 个任务"这一例钉死。

**§2.1b 结论与边界**：

- **通过**：L01（配方身份映射与拒绝 + 配置侧绑定 34/34）。
- **未知**：L02/L03/L04 与 L05/L06 的入口侧（同 §2.1）。
- **未做**：`check_cfg_lock.py` 里冗余的旧 `_TASK_VERSION` 校验删除（并行批次文件，留 A3 收口）；A0 未动。
- **口径**：本批同样**未跑全量套件** ⇒ `[31][32]`（含 `--bind-config`）与既有条目的端到端共存**未验证**。
- **证据**：gate 脚本 + 上表命令（未另存日志文件）。

### §2.4 回填（执行后，2026-09-16）

| 项 | 结果 |
|---|---|
| 实际移动 | **34 项**：16 个版本目录 + 线 `cfg_lock.json` + 线参数 + 16 处改名。**首版脚本漏了线根 dev yaml 的改名**，留下 `main/lizard_params.yaml`，被 `recipe_lines` 当场拒绝（"basename names its line"）⇒ 已补 `git mv` 并把该步写进脚本 |
| 纯改名 | 55 个文件为 `R`（内容零变化）：线 `cfg_lock.json`、16 组 PLAN/NOTES/base.json 与版本内其它工件 |
| 允许变化项 | 16 个 `asset_lock.json` 各 **1 行增删**，唯一变化 = 自身 yaml 路径键（`versions/lizard/vN/lizard_params.yaml` → `versions/lizard/main/vN/main_params.yaml`）；**sha256 两侧逐字节相同** ⇒ 改名没动内容；`baseline/v1` 与 `parkour/v1` unchanged；16 个 `base.json` 内容未变 |
| 线 golden 漂移 | **无** —— `[24] CFG_LOCK_OK (36 tasks, 3 line(s), isaaclab=28a37cecdd43\|rsl_rl=source:28a37cecdd43\|python=3.12.13)`。快照记值不记 yaml 路径，与预期一致（不是"重生成后全绿"，`--update` 全程未跑） |
| 冻结看守 | `[35] GOLDEN_FROZEN_OK (3 baseline file(s) unchanged since rev 020e6fb)` ⇒ 线 golden 的内容确实没动 |
| 闸门 | **`ALL_OFFLINE_CHECKS_PASSED (37/37 in 30.7s)`**；`[12] VERSION_DOCS_OK` |
| 计划外（必须记） | A0 暴露一个**既有缺陷**：`manifest.asset_digest()` 按版本名 glob 资产锁，而 `v1` 现在三条线命中（baseline/main/parkour）⇒ 旧代码取排序第一 = **取错锁**。已改为按声明的 `params_line` 解析；无声明时对多命中**拒绝而不猜**；`rebuild.py` 改为从**记录里的锁路径**反推线（比再查一遍更忠实于记录） |
| 跟随改动 | `lizard_env_cfg` / `teacher_env_cfg` 的 `params_line`（`lizard` → `lizard/main`）与 yaml 路径常量；6 个闸门/工具的写死路径；FAMILY 16 行键（`\| vN \|` → `\| main/vN \|`）；FILEMAP 16 行路径；活文档散文（FAMILY/PLAN/REWARDS/OBS/README） |
| 未改（有意） | 冻结记录 `vN/PLAN.md` 与 `NOTES.md` 里的旧路径、`ACCEPTANCE.md` 的历史小节 —— 记录写的是当时那棵树，改写成今天的布局就不再是证据 |
| 已知上限 | `recipe_lines` 的版本目录规则仍是 `v<N>`；放宽到任意标签只在某线首版不叫 v1 时才需要（baseline 用了 v1 ⇒ 今日不需要） |

### §2.4 独立审核与修复（2026-09-16，审核方复签阶段 A）

审核方对 `9ee6773` 做了**逐字节**核验（迁移前后 Git 对象比对：17 个参数文件内容不变、16 组 base/PLAN/NOTES 不变、主线 golden 不变、16 个 asset_lock 的变化严格限于自身 YAML 路径键），结论 **A0 迁移通过**，同时指出三项并已修复：

| 编号 | 问题 | 修法与提交 |
|---|---|---|
| P1 | `9ee6773` 的 `teacher_env_cfg.py` 已导入 `components`，而该模块未跟踪 ⇒ **HEAD 自身不可导入**，37/37 只证明本机工作树 | 完整提交组件库 `1083952`；复核查明套件引用的 38 个文件全部已跟踪且存在，导入链闭合 |
| P1 | `check_recipe_map.bind()` 只比 `params_version`、未比 `params_line` ⇒ 把某配方指到**另一条已存在线**时两侧均返回"无问题"，而配置仍属原线 | `bind()` 增比 `params_line`，反证加"版本对但线错"与"配置不声明线"两例 `83f0a40`；真树 36/36 一致 |
| P2 | A3 未收口：`check_cfg_lock` 仍以任务名尾缀正则推导版本、且不消费 `recipes.json` ⇒ 身份规则两套并存 | 删除该推导，改消费显式映射（声明版本 == `params_version`；声明版本在该线须有冻结目录；映射线与 `params_line` 一致），golden 内容比较不动 `83f0a40` |

**复审证据**：修复后全套 **38/38**（含 `[12] [24] [25] [31] [32] [35] [36]`），审核方据此**签收阶段 A**。

**边界（不因签收而改变）**：L02–L04 与 L05/L06 的**入口侧**仍未接线 ⇒ 按原口径记**未知**，属阶段 C；
本次签收**不覆盖运行期验收**。

**教训（记一笔，防重犯）**：两次同类事故（`9ee6773` 的 components、更早的 v15）根因相同 ——
提交前未核"HEAD 能否独立成立"。此后提交前查两件事：① `git diff --cached`（索引里到底有什么）
② 新提交物引用的文件是否同样进入 HEAD。

### §2.4 收尾 落地

| 步 | 件 | 内容 |
|---|---|---|
| 1（`8f6ed6f`） | 11 个闸门/测试/探针 | 版本类的解析源改到 `recipe_tasks`（类名逐字相同）；`check_obs_layout` 拆两个句柄：版本类走 `_recipe_mod`，`TEACHER_TERRAINS_CFG*` payload 常量仍走 `_env_cfg_mod` |
| 3 | 新增 `tools\verify\_b3_remove_version_classes.py`（一次性，AST 按名定位，decorator 行一并算入） | 删 24 个 teacher 版本类（V1/V2/V3/V4/V5/V6/V8/V10/V11/V12/V13/V14 × train/play）+ baseline 的 `BaselineFlatEnvCfg`/`_PLAY`；**keeper 检查**：共享接线（`LizardRoughTeacherEnvCfg`/`_PLAY`、`BaselineWiringCfg`）与 `ring_pattern`/`RingPatternCfg`/payload 常量/`TEACHER_PRIVILEGED_SPEC` 缺一个即**拒跑**（它们夹在删除区之间）。净变化 `-970 / +19` 行 |
| 2a | 两份 `cfg_lock.json` | 26 条 `env_cfg_class`（main 24 + baseline 2）定点搬到 `rl_exp.tasks.recipe_tasks:<同名>`；**未跑 `--update`**、未重生成任何 `snapshot`（逐字段证据见 B0 追加②） |
| 4 | `check_recipe_build.py` | "表 == 类"保真比较反向为 `resurrected_class()` 探针：某配方的版本子类重新出现即具名报红；`classvar_gaps`/`EXPECTED_GAPS`/两处台账循环随其生产者（版本类）一并退役 |

### §2.4 收尾 检查与结果

| 项 | 结果 |
|---|---|
| 全量套件 | **通过**：`ALL_OFFLINE_CHECKS_PASSED (47/47)` |
| `[24]` 删类**后** | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` —— 与删类前**同一句**：36 个任务构造出的 cfg 与冻结 `snapshot` 逐字段一致 ⇒ "删的是类，不是行为"（用户点名的第 4 条验收） |
| `[41]` | **通过**：`RECIPE_BUILD_OK (26 task(s) field-identical to the frozen golden; 322 declared difference(s) against their own base)` |
| `[35]` | **通过**：`GOLDEN_FROZEN_OK (4 baseline file(s) unchanged, frozen at: 020e6fb x3, ed4d35b x1)` + `--self-test` `GOLDEN_FROZEN_SELFTEST_OK` |
| `[21]` | **通过**：`CONFIGCLASS_FIELDS_OK`（39 类；规则修正见发现①） |
| 旁证 | `[37]` `COMPONENT_OWNERSHIP_OK` · `[8]` `OBS_LAYOUT_OK` · `[2]` `PARITY_OK` · `[14]` pxr-clean · `[31]/[32]` 身份映射与其反证 —— 全绿 |

**反证**：

| 编号 | 输入 | 结果 |
|---|---|---|
| 删类当场（step 4 的触发器） | 三处类体删净后跑 `[41]` | **按预期红**：对每个配方/kind **逐条具名**报 `no class in rl_exp.tasks.teacher_env_cfg builds params_version='vN' … the class path this recipe replaces is gone -- retire this comparison deliberately if intended`（"找不到"是红，不是跳过） |
| 硬 A 仍有牙齿（用户点名） | 卸掉 `_V14_DELTA` 里的 `v14_head_load` | **FIRED**：rc=1 + 两条具名 FAIL（`1 declared env path(s) no longer differ from the base` / `… is attributed to 'v14_head_load' while the elements that moved it are none`）；**逐字节复原**（sha256 `fe49e3d2…` 相同）后 rc=0 · `RECIPE_BUILD_OK`。脚本 `%TEMP%\falsify_b3_element.py` |
| `[21]` 规则修正的反证 | 给 `_check_play_inheritance` 补一例（PLAY 行 `value` 改成 `v99`） | **FIRES**；反证集 6 → 7 例，双双打红（`CONFIGCLASS_FIELDS_GATE_FALSIFIABLE`） |
| 重锚自证 | 新旧锁 JSON **递归逐叶** diff + `git diff --numstat` | 26 个叶全部且只有 `env_cfg_class`；`24/24`、`2/2` 行 —— 无其它行被触碰 |

### §2.4 收尾 执行中发现（三条，都不是"删类造成的回归"，而是一条被删类揭出来的旧假设）

1. **`[21]` 的"PLAY 不得改线"规则依赖旧类形状**：它取 **MRO 里最近的祖先类**作对照，而声明
   路径的 PLAY 类父级是共享接线（默认 `v2`）⇒ 删掉版本类后 11 个 PLAY 变体假红。改为**按名配对**
   （`X_PLAY` 对 `X`，即同一配方的 train 类；MRO 父类降为回退，服务非声明路径的类），并补一条反证
   —— 改规则而不带反证，正是规则退化成装饰的方式。
2. **`v4` 的 `REQUIRES_CURRICULUM_STATE`：类体"未声明"、配方表写 `False`**，两者是**同一答案**：
   `[41]` 的保真比较按 `bool(getattr(cls, name, False))` 比，四个读者（resume 拒绝 / save 守卫 /
   trainer 导入失败守卫 / manifest）也全走 `getattr(..., False)`。`test_resume_state` 里钉
   `not hasattr(V4, …)` 的那条断言因此改为断言**语义**而不是某一侧的**形状**。**同一事实也是台账可以
   退役的理由**：共享接线上的 `ClassVar` 由生成类继承，配方级的只能经 `CLASSVAR_STATEMENTS` 加，
   "无家可归"在单一路径下不再可表达。
3. **我自己的一处失误（已修，记在案）**：重指脚本按 `read_text()` 的**字符串**算 sha256，而本机
   `core.autocrlf=true`（工作树 CRLF）⇒ 表里先填的是 LF 视图的哈希，`[35]` 当场红。文件本身没坏
   （读-写往返保住 CRLF，只有 26 行被替换），按**磁盘字节**重算后复查通过。

### §2.4 收尾 边界（不得据本段宣称）

- **`--vs-upstream` 的归因列不在本批修复范围**：它读的是**本次构造**的 entry，不是 golden 里那列 ⇒
  改 golden 修不了它；该归因在翻表（`2f67f4c`）当天就已退化（本轮由用户纠正过我一次）。逐路径作者的
  替代来源是各配方的 `diff.json`（`format: 4`，本轮 12 条齐）。
- **未做**：v15 未实施（`v15\PLAN.md` 的待实施件已按"加元素 + 表行"改写）；agent（PPO）侧不在本批；
  `[41]` 的复活探针只覆盖**已声明配方**（v0 家族 8 个与 parkour 2 个任务的类本来就在
  `lizard_env_cfg`/`rough_env_cfg`/`parkour_env_cfg`，本批未动）。
- 生成类的名字清单唯一来源 = `versions\recipes.json`；`recipe_tasks` 不写第二份。
- 本批**未**重生成任何 `snapshot`，也未跑 `--update` ⇒ 硬 A 的比较对象仍是整改前冻结的那份。

### §2.4 收尾 追加（2026-09-18）：golden 的 `env_cfg_class` 从"散文"变成被看守的事实

**触发**：复核时点出 —— 上表 step 2a 的 26 处搬移只被**一次性脚本**证明过，而**没有任何闸门
比较这一列**。实测（见下）该列可以在指向**已删除的类**时让全部闸门保持绿：`[24]` 的
`verify_entries` 只比 `digest`／`snapshot` 自洽／`version`／配方映射／条目键白名单，`env_cfg_class`
在 `_ENTRY_KEYS` 里只是"允许出现的键"；全仓唯一读它的是 `manifest.recipe_ref`，按**类名后缀**
匹配 golden。于是它自 `2f67f4c`（入口切到 `recipe_tasks`）起在版本类名字上停了 24 小时以上
无人报红 —— 这正是 step 2a 存在的理由，也正是它必须先被看守才谈得上"语义不变"。

| 项 | 内容 |
|---|---|
| 落点 | `[41]`（`check_recipe_build.py`）的逐任务循环内；**不是** `[24]` —— 本批执行时 `check_cfg_lock.py` 与它的反证正被另一批（`--self-test` 接线）占用工作树。等价性：断言拿的是 `recipes.json` 的 `env_cfg_entry`，而 `[31]` 已把身份映射与注册表**逐字**绑死，故"golden 列 == 身份映射"= "golden 列 == 注册表解析出的入口" |
| 断言 | 每个已声明配方/kind：`stored["env_cfg_class"]` 必须**等于**身份映射为该任务声明的入口，否则具名报红；映射没声明入口同样报红 |
| 反证（一次跑完，含"洞"本身的证据） | 把 `main` 里 v14 那行搬回 `rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V14`：`[41]` **rc=1** → `FAIL Lizard-Rough-v14: the golden names 'rl_exp.tasks.teacher_env_cfg:LizardRoughTeacherEnvCfg_V14' as this entry's class while the recipe map declares 'rl_exp.tasks.recipe_tasks:LizardRoughTeacherEnvCfg_V14'`，而**同一份文件 `[24]` rc=0 `CFG_LOCK_OK`** ⇒ 洞是真的、断言真的补上了它；逐字节复原（sha256 `8a004fab…` = 重锚后摘要）后两者皆绿。脚本 `%TEMP%\falsify_golden_class.py` |
| 覆盖边界 | 只覆盖**已声明配方**（26 个任务条目）。v0 家族 8 个与 parkour 2 个任务的条目不在 `recipe.LINES` 里，它们的类仍活在自己的模块（`lizard_env_cfg`/`rough_env_cfg`/`curriculum_*`/`parkour_env_cfg`），`[41]` 的循环到不了 —— 若哪天它们也走声明路径，自动进入本断言 |
| 旁证 | 全量套件 `ALL_OFFLINE_CHECKS_PASSED`（42/42，当日套件条目数；并行批次同期在重排 `--self-test` 接线） |

### §2.4 收尾 追加②（2026-09-18）：家族开发态配方上声明路径（片 0–3 / 共 5 片）

上一条把**已声明**的 26 条吃进 `[41]`；本条处理剩下的 10 条里的家族 8 条
（`Lizard-Velocity-{Flat,Rough,Curriculum-Flat,Curriculum-Rough}-v0` + 各自 PLAY）。parkour 2 条不动
（退役线，且它是拒绝路径的唯一活体夹具）。本片只落**声明**：注册表仍指类路径，类体未删（翻表与删体是片 4）。

**机制的两处扩展**（`recipe.py`，皆默认值 = 旧行为，故 26 条不受影响）：

| 扩展 | 为什么必须 |
|---|---|
| 配方条目可**显式声明 `params_version`**（默认 = 表键） | 这 4 条**没有冻结版本**：映射写 `legacy_task_version: null`、类上 `params_version = None`、参数读**开发态 yaml**。表键原来直接当字段值用 ⇒ 只能硬造一个假版本号（golden 与映射随即互相矛盾）。改后键降为**句柄**、版本成为声明的**事实**。参数侧免费：`_doc(cfg)` = `recipe_params.load(cfg.params_line, cfg.params_version)`（`recipe.py:55`），`None` 即 dev yaml |
| **base 按配方解析**（默认 = 线 base） | 这 4 条与 teacher 共用线 `lizard/main`（它们的 `params_line` 就是它、读同一份 dev yaml），但**根接线不同**：family 用 `LizardFlatEnvCfg`。按线给 base 就只能另起一条线，而另起线需要自己的 `<line>_params.yaml` ⇒ **同一套机器参数两份 SSOT** |

**落子**：新增 10 个元素（6 train + 4 play）与 3 个 delta 元组；`flat-v0` 元素为空（它**就是**那个根，
同 teacher 线 v1 的形状）。**tuning 值仍留在原模块**，只搬装配：`rough_env_cfg.LIZARD_ROUGH_TERRAINS_CFG`、
`curriculum_env_cfg.LizardCurriculumActionsCfg` / `_make_stages(spine_scale)`；元素里不重述任何阈值。

| 项 | 结果 |
|---|---|
| 硬 A（`[41]`） | **通过**：`RECIPE_BUILD_OK (34 task(s) field-identical to the frozen golden; 322 declared difference(s))` —— 26 → 34，**多出来的 8 条逐字段一致**（这就是"搬运未改语义"的证明） |
| `[24]` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))`（类路径一侧仍未变，两条路径同对一份 golden ⇒ 漂移双向可抓） |
| 全量套件 | **通过**：`ALL_OFFLINE_CHECKS_PASSED (43/43)` |
| 钉数 | `EXPECTED_COMPARED["lizard/main"]` 24 → 32（+8 = 4 配方 × 2 kind） |
| 独立复核 | 对 8 个任务比 `recipe.build()` vs 仍注册的类路径快照：8/8 逐字段相同 |

**发现（1 条，值得单记）**：`configclass` 在构造时给每个成员**deepcopy 自己那一份**，而元素跑在构造**之后**
⇒ 元素里直接赋**模块级 cfg 单例**，会让后续 `apply_play_wiring` 的**就地**改写污染同进程所有 cfg（实测症状：
rough 的训练 cfg 读到 PLAY 的 5×5 网格，`10 → 5` 硬 A 的字段比对当场抓到）。修法 = 元素内 `deepcopy`。
危害面已量化收口：`apply_play_wiring` 唯一的共享对象就地写就是 `terrain_generator.num_rows/num_cols`
（`play_utils.py:63-64`），`_make_stages` 每次返回新对象 ⇒ **片 4 删掉类路径那份独立副本后，这仍是唯一一处**。

**边界（本片不得宣称）**：注册表与 `recipes.json` 仍指类路径（训练入口未切）；4 个类体未删；这 4 条**无
`diff.json`**（`[41]` 按预期打印 `no difference declaration (hard A only)`）；家族 obs 宽度仍未实测（旧账）。

### §2.4 收尾 追加③（2026-09-18）：家族四配方翻表 + 类体退役（片 4 / 共 5 片）

**落地**（4 处）：

| 件 | 内容 |
|---|---|
| 两处字符串 | `tasks/__init__.py` 8 条 + `recipes.json` 8 条 `env_cfg_entry` → `recipe_tasks:<同名>`；脚本逐条断言"该生成类确实存在"后再写（8 条映射条目改后仍 `line`/`agent_entry`/`legacy_task_version` 不变，且只有这 8 个叶变） |
| 6 个类体 | `LizardRoughEnvCfg(_PLAY)`、`LizardCurriculumFlatEnvCfg(_PLAY)`、`LizardCurriculumRoughEnvCfg(_PLAY)` 删除；`curriculum_rough_env_cfg.py` **整个文件删除**（删后只剩 docstring + import）。`LizardFlatEnvCfg(_PLAY)` **保留** —— 它是四个配方声明的 `base`（家族接线） |
| 引用面 | `position_check.py` 的 import 改指 `recipe_tasks`；`test_recipe_map_gate.py` 的两处 fixture 串同步；`check_dr_parity.py` 的注释（"family line stays inline until its own recipe line is migrated"）改为"已声明，且本模块的接线就是它们声明的 base" |
| 冻结件 | `main/cfg_lock.json` 8 条 `env_cfg_class` 定点搬一行 + `[35]` 重锚（见 B0 追加③） |

**检查与结果**

| 项 | 结果 |
|---|---|
| `[24]` 翻表**后** | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` —— 生成类重建出的 cfg 与 golden **digest 相同** ⇒ "换的是入口，不是内容" |
| `[41]` | **通过**：`RECIPE_BUILD_OK (34 task(s) field-identical to the frozen golden; 322 declared difference(s))` |
| `[35]` | **通过**：`GOLDEN_FROZEN_OK`（见 B0 追加③） |
| 全量套件 | **通过**：`ALL_OFFLINE_CHECKS_PASSED (43/43)` |
| 翻表现场 | `[41]` 在那 8 条上**具名报红**（`the golden names …lizard_env_cfg:LizardFlatEnvCfg… while the recipe map declares …recipe_tasks:…`）⇒ 昨天加的断言正是这一步的守卫，金标准不会停在旧形状上 |

**反证**（比片 0–3 时更强：那时类路径还在、golden 可由任一表达式满足；现在声明是**唯一**表达式）

| 输入 | 结果 |
|---|---|
| 从 `_V0_ROUGH_DELTA` 拿掉 `v0_rough_terrain` | `[41]` **rc=1**，且**恰好 4 条**（`Rough` 与 `Curriculum-Rough` 各 train/play）具名报两处字段差：`scene.terrain.terrain_type` `"generator" → "plane"`、`scene.terrain.terrain_generator` `{TerrainGenerator} → null` —— 用该元素的两条配方、两种 kind 一个不多一个不少 |
| 逐字节复原（sha256 相同） | rc=0 · `RECIPE_BUILD_OK (34 task(s) …)` |

**边界**：parkour 2 条仍走类路径（退役线，且它是拒绝路径的**唯一活体夹具**，见
`2026-09-17-lizard-entry-switch-and-declaration-gap.md` 的 L02 记录）；这 4 条仍**无 `diff.json`**；
家族 obs 宽度仍未实测（旧账，属 Step 3.1 那一支，后由
`2026-09-16-lizard-obs-protocol-gate.md` 的 §3.1e 补账关掉）。

**提交窗口的实情（记录在案）**：本片收口时（上表 43/43 那次）树是干净的；随后另有一批**他人的未提交
改动**落在 baseline 线（`recipe.py` 的 `baseline_no_dr` 发现 `reset_robot_joints` 不能删、改为钉住，
并新增 `tools\verify\reset_check.py`）。那批使 `[24]`/`[41]` 在**恰好 2 条 baseline 条目**上红，字段就是
它动的那一处（`events.reset_robot_joints`：`null → reset_joints_by_scale`），**与本片的家族面无关**；
它需要自己的 baseline 重锚（`--update --reason` + `[35]`）。本片提交按路径限定，未扫入该批任何文件。

## 证据引用

- 生命周期与身份映射：`rl_exp/versions/lines.json`、`rl_exp/versions/recipes.json`、
  `rl_exp/tools/verify/check_recipe_registry.py`、`test_recipe_registry_gate.py`、
  `check_recipe_map.py`（含 `--bind-config`）、`test_recipe_map_gate.py`。
- A0 迁移：移动集与脚本、`rl_exp/versions/lizard/main/`（线 `cfg_lock.json` + `main_params.yaml`）、
  16 个 `main/vN/asset_lock.json`；复核命令
  `git diff --stat -- rl_exp/versions/lizard/main/cfg_lock.json`；套件
  `rl_exp\tools\verify\run_offline_checks.bat` → `ALL_OFFLINE_CHECKS_PASSED (37/37)`（审核后 38/38）。
- 版本类体退役：`rl_exp/tools/verify/_b3_remove_version_classes.py`（一次性）、
  `rl_exp/tools/verify/check_recipe_build.py`（`resurrected_class()` 探针）、
  `%TEMP%\falsify_b3_element.py`、`%TEMP%\falsify_golden_class.py`；
  两份锁 `rl_exp/versions/lizard/main/cfg_lock.json`（`8a004fab…bf76` → `1643a755…dc8`）、
  `versions/lizard/baseline/cfg_lock.json`。
- 家族片 0–3 / 片 4：`rl_exp/tasks/recipe.py`（显式 `params_version`、按配方 base）、
  `rl_exp/tasks/recipes.json` + `rl_exp/tasks/__init__.py` 的各 8 条 entry。
- 重锚证据：见 `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`
  （B0 追加②：26 条 `env_cfg_class` 逐叶 diff；B0 追加③：家族 8 条）。
- 提交：`9ee6773`（A0）、`1083952`（组件库，闭合 HEAD 可导入）、`83f0a40`（`bind()` 与 A3 收口）、
  `8f6ed6f`（收尾 step 1）、`2f67f4c`（翻注册表，属并行批次）。

## 未覆盖边界

- **§2.1 / §2.1b 的未知项（当时口径，入口侧由后续记录承接）**：L02（入口执行）、L03（历史续训）、
  L04（历史兼容）、L05/L06 的入口侧全部需 §2.2 接线，属阶段 C；两批**均未跑全量套件端到端** ⇒
  新增条目与既有条目的共存**未验证**（`[2][12][24][28]` / `[31][32]`）。
- **§2.4 独立审核边界**：签收**不覆盖运行期验收**（L02–L04 与 L05/L06 入口侧仍未接线）。
- **§2.4 A0 已知上限**：`recipe_lines` 的版本目录规则仍是 `v<N>`（放宽只在某线首版不叫 v1 时才需要）。
  A0 暴露的 `manifest.asset_digest()` 取错锁是**既有缺陷**，已改为按 `params_line` 解析 + 多命中拒绝而不猜。
- **§2.4 收尾 未做/不覆盖**：`--vs-upstream` 的归因列**不在修复范围**（改 golden 修不了它；替代来源是各配方
  `diff.json`）；v15 未实施；agent（PPO）侧不在本批；复活探针只覆盖已声明配方，v0 家族与 parkour 任务
  不在 `[41]` 循环里（后由追加②/③把家族 8 条纳入，**parkour 2 条仍在外**）。
- **家族面未闭合项（仍开着）**：
  - 家族 4 条（`rough-v0` / `curriculum-flat-v0` / `curriculum-rough-v0` / `flat-v0`）在翻表时仍**无 `diff.json`**；
    其中三条后由 `2026-09-17-lizard-entry-switch-and-declaration-gap.md` 的「硬 B 追加（2026-09-18）」补上，
    `flat-v0` 按先例保持 hard A-only。
  - **家族 obs 宽度未实测**（旧账），后由 `2026-09-16-lizard-obs-protocol-gate.md` 的 §3.1e 补账关掉；
    在本次读数当日仍为开项。
- **提交窗口风险（记录在案，未修）**：并行批次在同一工作树上改动会让 `[24]`/`[41]` 在 baseline 条上红；
  本片只能按路径限定提交，未扫入他批文件。
- **口径边界**：历史 `[N]` 是当次运行编号而非闸门身份，各节成功行读数只在**当日 commit** 上成立
  （本记录横跨 31 → 47 条套件条目）。
