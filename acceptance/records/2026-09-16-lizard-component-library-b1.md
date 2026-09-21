# 组件库 B1 六个切片（height sensing / terminations / terrain / commands / obs / `_load_params`）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的 §B1 · 组件库切片 1–6（2026-09-16，阶段 B
`ARCH_PLAN` §2.4 的 B1）。六个切片按落地的先后各带自己的「落地 / 检查与结果 / 边界」，**逐片读**：
每片的边界只对该片成立，别把一片的绿读成整个 B1。

| 片 | 主题 | 门 2 计数 |
|---|---|---|
| 切片 1 | height sensing | 1 component / 5 owned name(s) |
| 切片 2 | terminations | 2 component / 8 owned name(s) |
| 切片 3 | terrain block | 3 component / 11 owned name(s) |
| 切片 4 | commands | 4 component / 12 owned name(s) |
| 切片 5 | obs 组（B1 最大一片） | 5 component / 16 owned name(s) |
| 切片 6 | `_load_params` 收敛（B1 末片） | 5 component / 16 owned name(s) |

**从本记录移出的两个子节（按主题归他处，正文完整保留在那儿）**：

- §B1 切片 1 里的 **`### B0 追加`①②③④**（合法重锚台账）→
  `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`。
- §B1 切片 2 里的 **`### B0 结论文更新：B3 前置已解锁`** → 同上（它作废的是 §B0 的结论，
  作废声明与作废对象放在一起）。

**本记录内部的前后作废关系**：

- **切片 1「边界与阻塞」的门 1 / 端到端两条是当日口径**：门 1 是 **A0 落地前**的实跑，切片 2 起
  各门的读数已在 A0 后的新线键下重跑（`CFG_LOCK_OK (36 tasks, 3 line(s))`）；「端到端未验证」
  在切片 2/3/4/5/6 一路仍写着，直到套件整跑才闭合。
- 切片 1 的「**硬 A（B3）仍不可做**」被切片 2 的「B0 结论文更新：B3 前置**已解锁**」判**自此失效**
  （原文保留作留痕）；该判定与后续实跑归上面那条记录。
- 切片 5 的「本片修正」与切片 4 的「发现并修正（门 1 抓到）」都是**夹具/断言写错**、不是实现错。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管 ⇒ 各片成功行的读数**只在当日 commit 上成立**。

## 验收条件

六个切片共用同一套判据（每片都按这两道门 + 旁证复跑，且**每片都声明"未跑全量套件"直到收尾**）：

| 门 | 工具 | 判据 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py`（套件 `[24]`） | 把多处写入点并成一处后，36 个任务构造出的 cfg 与冻结 golden **逐字段不变** |
| 门 2（非快照） | `test_component_ownership.py`（套件 `[37]`） | 逐版本形态完整且唯一；`OWNERSHIP`/`HOSTS` 只声明**已迁范围**；反证 `--self-test` 三种"第二个写入者"都着火 |
| 基线冻结 | `check_golden_frozen.py`（套件 `[35]`） | 3 份基线文件自 `020e6fb` 未动 |
| 旁证（按片） | `check_obs_layout.py` `[8]`、`check_dr_parity.py` `[2]`、`check_pxr_leak.py` `[14]`、`test_params_isolation.py` `[34]` | 各自独立实现，不复述门 2 的结论 |

**单写者范围的共同前提（六片一致）**：只到 `teacher_env_cfg.py` —— `baseline_env_cfg.py` /
`lizard_env_cfg.py` / `rough_env_cfg.py` / `parkour_env_cfg.py` / `curriculum_*_env_cfg.py` 各有自己的
写入点，属不同配方线，**未迁**；`OWNERSHIP`+`HOSTS` 只声明已迁范围，不冒充全仓。

## 结果

### 切片 1 · height sensing（2026-09-16）

**性质**：阶段 B（`ARCH_PLAN` §2.4）的 B1 第一片。改动面 = 新增 `rl_exp/tasks/components.py`；
`rl_exp/tasks/teacher_env_cfg.py` 三处（import、基类单点写入、V3 删掉重复写入）；
新增闸门 `test_component_ownership.py`（套件 `[37]`）。

**落地**

| 项 | 内容 |
|---|---|
| 组件形态 | `components.height_sensing(version, ...) -> {name: sensor}`：v1/v2 = 单个地面 grid scanner；v3+ = `height_scanner=None` + 4 个 `{foot}_foot_ring`（几何仍读 yaml `v3.foot_ring`） |
| 写入点 | 由 3 处（基类建 scanner、V3 置 `None`、V3 再建 4 环）并为 **1 处**（基类一次循环 `setattr`） |
| 版本解析 | 按版本判定（`GRID_SCANNER` / `FOOT_RINGS` 两张表），未知版本**抛错**；不再靠 MRO 静默继承 |
| 刻意不动 | `RingPatternCfg` / `ring_pattern` 留在 `teacher_env_cfg`（其 `__callable__` 路径已写进 golden 76 处，搬移 = 无行为变化却重写全部 V3+ 条目）；pattern 改由调用方注入 |

**检查与结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过（A0 落地前那次）**：`36 tasks, 3 line(s)`、`CFG_LOCK_OK` —— 换成单点写入后 36 个任务的 cfg 树逐字段不变 |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (1 component(s), 5 owned name(s), 1 host file(s))`；12 个版本各自解析出**完整且唯一**的形态（grid 形态无环、ring 形态无 grid、四脚环几何一致）；`v99` 未声明版本抛 `ValueError` |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` —— 直接赋值 / 写被拥有实体的字段 / 字面量 `setattr` 三种"第二个写入者"都着火，"走组件循环"不着火 |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（见 B0 追加①） |

**边界与阻塞（不得据本片宣称通过）**

- **门 1 的时点限定**：上表门 1 是 **A0 落地前**的实跑（当时线键仍是 `lizard`）。A0 落地后 `[24]` 独立红于 `lizard: 32 task(s) declare this line … but no such line exists ['lizard/baseline','lizard/main','lizard/parkour']`（`params_line` 收尾在 A0 清单里）⇒ **切到新布局后必须重跑门 1**，本片不以 A0 前的绿替代。
- **端到端未验证**：全量套件在 `[2]` 即失败（A0 中场：16 个 `asset_lock.json` 键未按 `--update-locks` 重生成），fail-fast 让 `[24]`–`[37]` 全部跳过 ⇒ `[35]/[37]` 与既有条目的共存**本批未验证**。
- **硬 A（B3）仍不可做**：v11/v12 基线不可由任何 rev 取回（见 B0 节），须待那批内容提交后重跑 clone 等价性。（该条后由切片 2 判失效。）
- **后续切片**：`terminations` → `terrain block` → `commands` → `obs 组` → `_load_params` 收敛（最后一片等 A1 提交，避免与其缓存/隔离改动互踩）。

### 切片 2 · terminations（2026-09-16）

**性质**：改动面 = `components.py`（新增 `terminations` 组件与 5 张声明表）、`teacher_env_cfg.py`
（4 处写入点并为 1 处，另清掉因此变死的 `DoneTerm` import）、`test_component_ownership.py`
（`OWNERSHIP` 加该组件 + 逐版本形态校验）、`FILEMAP.md`。

**落地**

| 项 | 内容 |
|---|---|
| 组件形态 | `components.terminations(version, *, params, base_contact, base_body) -> {name: term 或 None}`：`base_contact` 由调用方传入继承来的框架 term（其 `func` 是框架的，只原地收窄 sensor），其余按配方声明构造 |
| 写入点 | 4 处 → **1 处**：基类 `:631` 收窄、V3 `:949` 置 `None`、V3 建 `tilt`、V10 `tilt = None`、V14 建 `roll_over` 全部并入基类一次循环写入 |
| 声明表 | `BASE_CONTACT_KEPT`（v1/v2 收窄）· `BASE_CONTACT_DROPPED`（v3+ 丢弃）· `TILT_ADDED`（v3+）· `TILT_FLAG`（v10+，由 yaml `v10.tilt_terminate is None` 决定是否留存）· `ROLL_OVER`（v14） |
| 刻意保留的语义 | ① v1/v2 **不写** `tilt` 键（写了 `None` 就等于给老配方长出一个没人选的键，快照看得出）；② v10+ 的取舍仍读同一面 yaml 标志（不把决定搬到代码）；③ `base_contact` 传引用收窄而非重建，`func` 仍指框架 |

**检查与结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))`（A0 后的新线键下）—— 4 处写入并为 1 处后逐字段不变 |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (2 component(s), 8 owned name(s), 1 host file(s))`；新增逐版本形态校验：键集恰为 `base_contact`(+`tilt`)(+`roll_over`)、v1/v2 保留的 term 就是继承来的那一个且 sensor 收窄到 base body、`TILT_FLAG` 版本按标志判、`v99` 抛 `ValueError` |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（未重锚、未改摘要） |

**边界**

- **单写者范围**只到 `teacher_env_cfg.py`：`baseline_env_cfg.py` / `lizard_env_cfg.py` / `parkour_env_cfg.py` 仍各自写 `base_contact` / `tilt`（属不同配方线，未迁；`OWNERSHIP`+`HOSTS` 只声明已迁范围，不冒充全仓）。
- PLAY 变体继承同一单点：已核 `play_utils.apply_play_wiring` 不写 terminations。
- **v15 待实现的手续**：基类对未声明版本**抛错**，v15 落地时须在 `GRID_SCANNER`/`FOOT_RINGS` 与 terminations 三组表里各声明一次，否则构造即失败（错误信息给出可声明位置）。
- 本轮只跑三闸，**未跑全量套件** ⇒ `[37]` 与既有条目的端到端共存仍未验证（A0 后套件已由 A 带补规则，可在收尾时整跑）。
- 后续切片：`terrain block` → `commands` → `obs 组` → `_load_params` 收敛。

### 切片 3 · terrain block（2026-09-16）

**性质**：改动面 = `components.py`（新增 `terrain` 组件 + `TERRAIN_BY_RECIPE` 单表）、
`teacher_env_cfg.py`（5 处写入点并为 1 处；清掉因此变死的 `build_param_grid_terrain_cfg` import）、
`test_component_ownership.py`（`OWNERSHIP` 加该组件 + 逐版本形态校验 + `HOSTS` 旁声明 PLAY 后处理器）、
`FILEMAP.md`。

**落地**

| 项 | 内容 |
|---|---|
| 组件形态 | `components.terrain(version, *, params, payloads) -> {terrain_type, terrain_generator, max_init_terrain_level}`；`TERRAIN_BY_RECIPE` 单表给出**每配方的 payload 与起始行**（v1/v2 冻结生成器/5；v3 换 Miki 地形/0；v4 碎石换 payload/继承 0；v5–v10、v13/v14 用 V5 payload/None 均匀；v11/v12 由自身 grid 段构建/None） |
| 写入点 | 5 处 → **1 处**：基类 3 行、V3 换生成器 + 起始行、V4 换生成器、V5 换生成器 + 起始行、V11 参数格 + 起始行全部并入基类一次循环写入 |
| 关键保留 | ① **payload 常量不搬**：`check_obs_layout.py` 与 `terrain_preflight.py` 从 `teacher_env_cfg` import 它们（`terrain_preflight` 还按版本建表），搬移会牵动两个闸门与多处历史文档；payload 改由调用方按名传入，选择表留在组件侧。② v11 的"先建后替换会丢 `curriculum=True`"这条坑消失——不再有第二次替换。③ 起始行语义（v3.5 最易行、v5+ SIR 均匀起始）写进声明表注释，不再散在子类里 |

**检查与结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` —— 地形三字段换单点写入后逐字段不变（含 v11/v12 的参数格地形） |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (3 component(s), 11 owned name(s), 1 host file(s))`；新增校验：块字段恰为三项、`terrain_type` 恒 `generator`、取到的就是**它声明的那份 payload**（对象身份）、起始行与声明相等、由 grid 段构建的只应是 v11/v12、`v99` 抛 `ValueError` |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（未重锚） |

**边界**

- **PLAY 是已知的、被声明的第二个写入者**：`play_utils.apply_play_wiring` 会给每个 PLAY 变体重写起始行与网格形状（确定性评估不漫游）。它是配方级决定、非"某版本悄悄覆盖兄弟"，故**不进扫描范围**，但记在 `test_component_ownership.py` 的 `HOSTS` 旁，且一旦退化成按版本覆盖就必须迁进组件。
- 单写者范围仍只到 `teacher_env_cfg.py`（`rough_env_cfg.py` / `parkour_env_cfg.py` / `baseline_env_cfg.py` 各有自己的地形块，属其他配方线）。
- 本轮只跑三闸，未跑全量套件。
- 后续切片：`commands` → `obs 组` → `_load_params` 收敛。

### 切片 4 · commands（2026-09-16）

**性质**：改动面 = `components.py`（新增 `commands` 组件 + `COMMAND_RANGE`/`PARTICLE_COMMAND`/`FULL_FORWARD_RANGE`）、
`teacher_env_cfg.py`（6 处写入点并为 1 处，另加基类 `PLAY_PINS_COMMAND_RANGE` 与两个 PLAY 类的同名 ClassVar）、
`test_component_ownership.py`（`OWNERSHIP` 加该组件 + 逐版本范围校验）、`FILEMAP.md`。

**落地**

| 项 | 内容 |
|---|---|
| 组件形态 | `components.commands(version, *, params, base_velocity, pins_full_range) -> {base_velocity: term}`。侧向/偏航范围（`(-0.5,0.5)`/`(-1,1)`）对所有配方是同一套论文收窄；**前向范围**按配方：v1/v2 `(-1,1)`、v3/v4 `(-1,2)`、v5–v10/v13/v14 取 yaml `v5.commands.lin_vel_x`、v11/v12 换 `ParticleVelocityCommandCfg`（逐字段从原 term 拷贝，含 ranges） |
| 写入点 | 6 处 → **1 处**：基类 3 行、V3 前向范围、V5 yaml 范围、V11 换 term 全部并入基类一次循环；`V3_PLAY`/`V4_PLAY` 的"钉满量程"改为**声明式**——类上 `PLAY_PINS_COMMAND_RANGE: ClassVar[bool] = True`，由组件统一施加 |
| ClassVar 选择理由 | PLAY 的钉范围是**配方级**决定（评估没有课程去中途放宽），不是"某版本偷偷覆盖兄弟"；ClassVar 不进快照（快照格式 2 已定），故**零 golden 影响**，且把这条规则从两处散写收进一张表 |
| 发现并修正（门 1 抓到） | 首版把 `v4` 的前向范围写成 `(-1,5)`——那是 `V4_PLAY` 的值，`v4` 训练配方沿用 v3 的 `(-1,2)`。逐字段差异实证：`env.commands.base_velocity.ranges.lin_vel_x.__tuple__[1]: 2.0 -> 5.0`（仅 `Lizard-Rough-v4` 一条，`-Play-v4` 相符）。按 golden 修正声明表后全绿 |

**检查与结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过（修正后）**：`CFG_LOCK_OK (36 tasks, 3 line(s))`；中途 1 条漂移已由 `--diff --tasks` 定位并修掉，见上 |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (4 component(s), 12 owned name(s), 1 host file(s))`；新增校验：12 个配方各自的前向范围、侧向/偏航恒为该收窄值、粒子配方的 term 类型与从文档读到的 `v_pr_threshold`/`command_jitter`、`resampling_time_range=(1e9,1e9)`、非粒子配方**不得替换**该 term（对象身份）、`pins_full_range=True` 时恒为满量程、`v99` 抛 `ValueError` |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（未重锚） |

**边界**

- 课程在**运行期**改 `commands.base_velocity.ranges`（`StagedCurriculumTerm` 的 stage 0 播种 cfg、后续按 `success_rate` 放宽）——那是运行时行为，不是 cfg 写入点，本组件与 golden 都不覆盖它。
- 单写者范围仍只到 `teacher_env_cfg.py`。
- 本轮只跑三闸，未跑全量套件。
- 后续切片：`obs 组`（表驱动两份真相合一处）→ `_load_params` 收敛。

### 切片 5 · obs 组（2026-09-16）

**性质**：B1 的**最大一片**。改动面 = `components.py`（新增 `observations` 组件 + `_teacher_terms`/`_ring_terms`
两个构造器 + `SINGLE_GROUP_OBS`/`PROPRIO_TERMS`/`BASELINE_PRIV_TERMS`/`SPEC_TERMS`/`RING_NOISE` 声明）、
`teacher_env_cfg.py`（3 处写入点并为 1 处；清掉因此变死的 `ObservationGroupCfg`/`ObsTerm` import）、
`test_component_ownership.py`（`OWNERSHIP` 加该组件 + 逐版本组/序校验）、`FILEMAP.md`。

**为什么 term 定义也得搬**：被拥有的是**组容器**（`policy`/`proprio`/`extero`/`priv`），而
`self.observations.policy.height_scan = ObsTerm(...)` 这类**组内 term 写入**同样决定组的最终状态 ⇒
按本组件库已声明的规则（"写被拥有对象的字段也算第二个写入者"）它必须一并迁入，否则"单写点"是假的。
因此 11 个教师 term 的构造、spec 剥离、v3 分组、v12 加噪全部进组件。

**落地**

| 项 | 内容 |
|---|---|
| 组件形态 | `components.observations(version, *, params, base_policy, spec) -> {组名: 组 或 None}` |
| 单组配方（v1/v2） | 在框架的 `policy` 组上原地追加 11 个 term，再把 spec 未包含的增量 term 置 `None`（`sorted(every - allowed)`，与旧实现同序） |
| 拆组配方（v3+） | `proprio`（7 个框架 term，按固定序）、`extero`（4 个脚环 term，lf/rf/rl/rr 序）、`priv`（5 个基线 + 按 spec 的增量 term）、`policy = None` |
| v12 加噪 | extero 的 `func` 与参数在构造时即按 `v12.height_noise` 给出（含 `foot_index`），不再"先建后改" |
| 两份真相合一处 | 旧的"V3 硬编码 7/10 个名字的清单"消失：分组的名字序列现在由 `PROPRIO_TERMS`/`BASELINE_PRIV_TERMS`/`SPEC_TERMS` 三张表统一给出，spec 表只回答"这个配方含哪些增量项" |

**检查与结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` —— 整棵 obs 树（含 36 个任务的组名/term/序/clip/params）逐字段不变 |
| 门 2（非快照） | `test_component_ownership.py` | **通过**：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s), 1 host file(s))`；新增校验：单组配方只产 `policy` 且 spec 未含的增量项为 `None`（在含的必须是 term）、拆组配方键集与 `policy is None`、三组的 **term 序逐项相等**、`proprio` 的 term **就是框架那一个**（对象身份）、v12 的 extero 是 `NoisyFootRing` 且带 `foot_index`、非 v12 的 extero 不带噪声、`v99` 抛 `ValueError` |
| obs 契约闸门 | `check_obs_layout.py`（套件 `[8]`，独立实现） | **通过**：`OBS_LAYOUT_OK`（v1/v2/v3/v4/v5/v11/v12 复检组名/term 序/c_k 一致性） |
| import 面 | `check_pxr_leak.py`（套件 `[14]`） | **通过**：`OK (task cfg import chain is pxr-clean)` —— 新模块进了 env cfg 的 import 链，仍是 pxr-clean |
| 门 2 反证 | 同上 `--self-test` | **通过**：`COMPONENT_OWNERSHIP_SELFTEST_OK` |
| 基线冻结 | `check_golden_frozen.py` | **通过**：`GOLDEN_FROZEN_OK`（未重锚） |
| 接线 parity | `check_dr_parity.py`（套件 `[2]`） | **通过**：`PARITY_OK`（family 20 / teacher 20 行）。切片 2 把 teacher 的 `base_contact` 收窄行移进组件后，该行只存在于家族侧 ⇒ 按该闸门自带的扩展点把这条**已审查的单侧差异**列入 `ALLOWLIST`（附理由 + golden 佐证），未放宽任何其他比对项 |

**本片修正（均由反证/断言抓到）**

- **门 2 断言写错（非实现错）**：首版用 `vars(group)` 比 term 序，结果组自身的配置字段（`concatenate_terms`/`enable_corruption`/…）被算进去 ⇒ 全绿判红。改为先减去一个空 `ObservationGroupCfg` 的自有字段，再比 term 序列。

**边界**

- `TEACHER_PRIVILEGED_SPEC` **留在 `teacher_env_cfg.py`**（`check_obs_layout.py`、`OBS.md`、`FAMILY.md` 都从代码侧引用它），由调用方按 `spec=` 传入——与切片 3 的 payload 注入同一策略。
- 运行期的加噪事件 `events.sample_ring_noise` 仍在 v12 类里（那是 reset 事件，不是 cfg 写入点，且 PLAY 会把它置空 ⇒ 干净扫描）。
- 单写者范围仍只到 `teacher_env_cfg.py`。
- 本轮只跑五闸（门 1、门 2、obs 契约、pxr、冻结），未跑全量套件。
- 后续切片：只剩 `_load_params` 收敛（4 份定义 → 1，等 A1 的读模块稳定）。

### 切片 6 · `_load_params` 收敛（B1 末片，2026-09-16）

**性质**：B1 的最后一片。改动面 = 新增 `rl_exp/tasks/recipe_params.py`；
`lizard_env_cfg.py` / `teacher_env_cfg.py` / `parkour_env_cfg.py` / `baseline_env_cfg.py` 各换成一行 wrapper；
`test_params_isolation.py` 补 baseline 探针；`FILEMAP.md`。

**收敛前的四份（实测差异，不是"看起来一样"）**

| 线 | 缓存 | 允许读 dev yaml | 路径推导 |
|---|---|---|---|
| `lizard/main` | `_params_document` lru_cache + deepcopy | 是（`version=None`） | `_LINE_DIR/<v>/main_params.yaml` |
| teacher（同线） | 同上 | **否**（version 必填） | 同上 |
| `lizard/parkour` | 同上 | 是 | `_LINE_DIR/<dir.name>_params.yaml` |
| `lizard/baseline` | **无**（每次 `yaml.safe_load`） | 是 | 同上 |

⇒ 四份已经漂了：一份不缓存，一份不许读 dev yaml。收敛后**缓存/深拷贝/路径约定只有一处**，
每线只留"我是哪条线 + 我是否 frozen-only"。

**落地**

| 项 | 内容 |
|---|---|
| 新模块 | `recipe_params.py`：`document(path, stamp)`（lru_cache(maxsize=64)）、`path(line_key, version)`（目录名即 basename）、`load(line_key, version, *, frozen_only)`（每次 deepcopy；`frozen_only` 且 `version is None` **抛错**） |
| 各线 wrapper | `return recipe_params.load(_LINE_KEY, version)`；teacher 传 `frozen_only=True`（保住"冻结配方永不读 dev yaml"） |
| 顺带修掉 | baseline 从"每调用重解析"升级为共享缓存（原先每个 cfg 构建都要多解析一次该文件） |
| 清理 | 四文件里变死的 `copy`/`functools`/`yaml` import 与 `_LINE_DIR`/`_PARAMS_NAME` 常量；`teacher_env_cfg.py` 里重复的 `from typing import ClassVar` 一并去掉 |

**检查与结果**

| 编号 | 命令 | 结果 |
|---|---|---|
| 门 1（字段面） | `check_cfg_lock.py` | **通过**：`CFG_LOCK_OK (36 tasks, 3 line(s))` —— 换加载器后 36 个任务的 cfg 树逐字段不变（含 17 份 yaml 全部版本副本） |
| 隔离契约 | `test_params_isolation.py`（套件 `[34]`） | **通过**：`PARAMS_ISOLATION_OK`，**5 例**（teacher v14 / family v14 / parkour v1 / **baseline v1（新增）** / family dev yaml）——两次 load 非同一对象、污染不跨调用存活 |
| 组件单写者 | `test_component_ownership.py`（套件 `[37]`） | **通过**：`COMPONENT_OWNERSHIP_OK (5 component(s), 16 owned name(s))` |
| obs 契约 | `check_obs_layout.py`（套件 `[8]`） | **通过**：`OBS_LAYOUT_OK` |
| 接线 parity | `check_dr_parity.py`（套件 `[2]`） | **通过**：`PARITY_OK` |
| import 面 | `check_pxr_leak.py`（套件 `[14]`） | **通过**：`OK (task cfg import chain is pxr-clean)` |

**边界**

- **不是"全仓只剩一份"**：`rl_exp/archive/**` 与 `rl_exp/fork_patches/isaaclab_untracked/**` 里的 spider env cfg 各有自己的 `_load_params`——那是归档/未跟踪材料，属**留痕**，不迁不改。
- baseline 探针是**新增覆盖**：该线原来没有缓存也就无从"泄漏"，现在进了共享缓存，隔离必须被钉住。
- 单写者范围仍只到 `teacher_env_cfg.py`；四条线的 cfg 只共享加载器，互不共享配方。
- 本轮只跑六闸（门 1、隔离、单写者、obs、parity、pxr），未跑全量套件。

## 证据引用

- 组件与宿主：`rl_exp/tasks/components.py`、`rl_exp/tasks/teacher_env_cfg.py`、
  `rl_exp/tasks/recipe_params.py`；四条线的 `*_env_cfg.py` wrapper。
- 闸门：`rl_exp/tools/verify/test_component_ownership.py`（`COMPONENT_OWNERSHIP_OK` /
  `--self-test` → `COMPONENT_OWNERSHIP_SELFTEST_OK`）、`check_cfg_lock.py`、
  `check_golden_frozen.py`、`check_obs_layout.py`、`check_dr_parity.py`、`check_pxr_leak.py`、
  `test_params_isolation.py`；整跑 `rl_exp\tools\verify\run_offline_checks.bat`。
- 重锚（切片 1 的「基线冻结」行与切片 3/4/5/6 的「未重锚」对照）：
  `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`。
- 被替换的版本类后续退役与 `[41]` 保真比较：
  `acceptance/records/2026-09-16-lizard-layout-migration-lifecycle.md`。

## 未覆盖边界

- **单写者范围不冒充全仓**（六片一致）：只到 `teacher_env_cfg.py`；`baseline_*` / `lizard_*` /
  `rough_*` / `parkour_*` / `curriculum_*` 各写自己的 `base_contact` / `tilt` / 地形块 / 命令范围。
- **PLAY 是已知的第二个写入者**：`play_utils.apply_play_wiring` 会就地重写 terrain 起始行与网格形状
  （配方级决定，非按版本覆盖）；一旦退化成按版本覆盖就必须迁进组件。
- **运行期行为不在覆盖内**：课程在运行期改 `commands.base_velocity.ranges`；
  `events.sample_ring_noise` 仍在 v12 类里 —— 都不是 cfg 写入点。
- **各片都写着「未跑全量套件」**：切片 1 的失败点是 `[2]`（A0 中场未重生成 `asset_lock.json` 键），
  其余各片只跑各自的三至六闸 ⇒ `[35]/[37]` 与既有条目的**端到端共存**直到套件整跑才闭合。
- **切片 1 的门 1 时点限定**：那是 A0 落地前的读数，A0 后必须以新线键重跑（切片 2 起已重跑）。
- **v15 落地的手续是硬性的**：基类对未声明版本抛错，v15 须在三组声明表里各声明一次，否则构造即失败。
- **不是"全仓只剩一份"**：`rl_exp/archive/**` 与 `rl_exp/fork_patches/isaaclab_untracked/**` 里的
  spider env cfg 仍有自己的 `_load_params`（归档/未跟踪材料，不迁不改）。
- **未闭合项**：`recipe.py` 元素写 `commands.base_velocity.*`，但它**不在 `[37]` 的 HOSTS 里**
  （"元素豁免"的形状未定义，本轮不动）—— 该开项一路带到 B3 与翻表各批。
