# Ablation Harness —— 评测台 SSOT

> 本文件 = 评测台（`ablation_harness/`）**当前事实与规则**的唯一真源：协议版本、记录格式契约、
> 升级触发、与 `rl_exp` 的契约。
> **待办不在这里**（→ `work/`，发现命令见 `AGENTS.md`）；**版本史与修订记录也不在这里**
> （→ `git log -p ablation_harness/HARNESS.md` 与各 commit message）。
> 评测台是共享测量仪器：服务所有机器人家族（换家族后仍在），**不进任何家族的配方版本管理**
> （versioning.mdc「范围边界」）。修订纪律沿用 versioning.mdc B 节（vN.M.K + 版本号开头的 commit
> message），**编号独立于家族配方版本**（冻结 tag：家族叫 `lizard-vN`，这里叫 `harness-vN`）。
> 家族侧对应项 = `work/active/isaac-root-parameterisation.md`（原 `versions/lizard/PLAN.md` 挂账 #12）。

## 当前状态

- **协议（locomotion）**：`locomotion_eval_v3` 当前（`eval.py` 的 `--protocol` 默认值即它；套件
  `lizard_suite_v2` 的 rough 两列是真起伏）。`locomotion_eval_v2` 与 `v1` 冻结封存，旧结果留
  `results/locomotion_eval_v{1,2}/` 原地。**四版任一不得混表**：v1→v2 帧右移一个 `step_dt`（20 ms）
  ⇒ 全指标有系统漂移；v2 的 rough 两列实为均匀抬升平板（已由 v3 换掉）；v4 的数值口径与 v3
  逐字相同，变的是**协议自己冻结地形**（下节"套件锁"）：指纹已真跑批注并解锁，`--protocol`
  默认值仍是 v3。
- **协议（baseline）**：`baseline_flat_v1..v4`。v1/v2/v3 冻结封存，判据由"阈值键"表达；`baseline_flat_v4`
  数值与 v3 逐字相同，判据改为显式 `criteria`（具名 kind + 封闭参数集）。判分器身份 = `JUDGE_ID`
  （v4 起）与 `LEGACY_JUDGE_ID`（v1–v3，按声明身份白名单进入），身份→语义用例的冻结表在
  `judge_semantics.json`，由 `test_baseline_contract.py` 看守；无 `criteria` 且身份不在白名单 ⇒ 拒判，
  不回落。**v4 与 v3 判同一份记录必须得出同一结论**（迁移证明，有回归）。
- **代码基线**：v1.9.0 —— 几何测量的唯一家 `rl_exp/tasks/terrain_geometry.py`；记录格式见下一节。
  **版本纪律**：往 `ablation_harness/` 加模块、或改测量语义 ⇒ minor bump，并打 `harness-vN.M.K` 锚点
  （复现 = `git checkout harness-vN.M.K -- ablation_harness/`；已推的 tag 不改指不改名，内容错了开新
  版本号，不去改旧的）。v1.9.0 = v1.8.0（判据身份化 + 套件锁 + 同表条件面）加 `video_matrix.py`（见下）。
  **敞口**：v1.9.0 还没有锚点 —— 加模块那笔提交没声明版本，这一格登记在
  `work/active/harness-version-anchor-missing.md`，由落下一笔的人补。同一敞口下另有一笔未编号的改动：
  2026-09-23 的汇总侧身份闸门（记录格式节 ④，`run_ablation._identity_report`）—— 它不是新模块、也不改
  测量语义，编号与锚点同上面那条一起定，别在这里凭空写一个版本号。
- **部署形态**：仓根独立目录，全部自定位。机器本地事实（IsaacLab 树 + venv 解释器）登记在仓根
  `paths.yaml`（模板 `paths.example.yaml`），唯一读者 `host_paths.py`；`E:\IsaacLab\ablation_harness`
  junction 已废，原机可 `rmdir` 摘链接。
- **同目录但不是测量仪器**：`video_matrix.py`（录像矩阵）与 `results/` 里的记录无关 —— 它按
  `--speeds` × `--terrains` 任意组合录 mp4 + `matrix.json`，用来**看**策略在不同速度/地面上怎么走，
  **不产 verdict、不写 `results/<协议>/`**。它的命令由评测侧注入，可以落在配方命令区间之外（那种格子
  记 `in_recipe_box: false`），其位移/均速只作"这段片子是否靠谱"的自查，**不得引用进任何验收表**；
  地形挡位取本仓套件的单列板（`plane` 走配方自己的地）。断言折在 `test_terrain_geometry.py` 里，
  因为那道闸门已经付过 `suites` 的 import —— 单立一项会顶过离线套件的数量棘轮。

## 记录格式（`record_format`，独立于 eval 协议版本）

一次 eval 的**条件**写在 `results/<协议>/[组/]<run_id>/record.json`。格式身份 = `record_format` 字段
（现行 `eval-record-1`）。**版本号独立**：协议语义变化（时间线/阈值/地形/DR/指标/采样帧）才开新
`locomotion_eval_vN`；纯溯源字段补充**不开新协议**，只升这里的版本号。

**四条读侧规则**（`record.read_state`，合规即通过，违规即红，不做兼容）：

1. 无 `record_format` = **legacy**：缺字段一律读作未知，不回写、不补齐、不推导；
2. 有 `record_format` 但缺该格式必需字段 = **记录不完整**：不得按 legacy 放行，也不算通过
   （未知值写 `"unknown"`，**空槽不算记录**）；
3. 可比／不可比／未知分别有测试，缺证据**不得**自动升级为可比；
4. 记录行为不得改变 rollout、随机数消费或指标计算 —— `record.py` 不 import torch/numpy/random，
   由静态闸看守（`test_eval_record.py` 末例）。

**可比性只看绑定面**（`record.BINDINGS`：checkpoint / suite / assets / eval 协议 / obs 协议身份+摘要）：
任一侧 legacy 或不完整、或某绑定读作 unknown ⇒ **未知**；`differences` 只收**真差异**，
`unproven` 另记"两侧同为 unknown"的绑定。其余元数据（run_id、时间戳、分组）不参与比较。

**同表条件面 ≠ 绑定面**（`record.CONDITIONS`，v1.8.0 起）：绑定面判"是不是同一次测量"，条件面判
"两行能不能放进同一张表"。两者**故意不重合** —— checkpoint 在绑定面内、在条件面外：评分表比较的
正是模型这一变量，要求它相等会把每一张跨模型表都拒掉。条件面逐字段列举（不用前缀通配，免得日后
新字段被静默纳入比较）：`eval_protocol.digest`、`suite.name/digest/geometry_digest/num_rows/
num_cols/envs_per_terrain/terrains`、`obs_protocol.identity` **与** `digest`（同名协议可被重批，
身份相等不蕴含布局相等）、`judge.id`。唯一例外 `CONDITIONS_WITH_DECLARATION`：`assets.declared_digest`
不同时该行必须在 `run.variant` 里点明这次替换（表里 `variant` 列即该声明），否则按冲突拒。两侧同为
unknown 不算冲突但记 `unproven` —— 建立在缺失值上的表就是建立在空处。

**写侧硬门**：绑定齐备处（`_make_policy` 之后）与 `_persist` 各判一次 —— ①记录不完整 ⇒ **拒绝落盘**；
②同一 `run_id` 已有**可比**记录 ⇒ 重跑自重写，其余一律拒（记录有真差异 / legacy / 不完整 /
目录有结果无记录 / 记录文件不可读）。放行只有 `--variant`（另起身份）或 `--overwrite`（显式替换）。
拒写发生在 rollout **之前**。③**汇总侧按条件面拒表**：`--summarize` 读每行 run 目录的 `record.json`，
条件冲突或记录读不到 ⇒ 列出冲突字段与方向并以非零码退出。④**汇总侧按身份拒表**（2026-09-23）：
`--group` 只决定一行落在哪张表，不决定它是什么 ⇒ 非 `smoke` 组的表里出现 `policy.kind != checkpoint`
的行（零动作 / 冒烟）即点名该行与它的 kind 并非零退出 —— 那类行是**诊断**，与真分数同行会被读成性能读数
（`locomotion_eval_v4` 根表里唯一那行就是 `zero_action`，其读数与 v3 smoke 同值、没有信息量）。写在
`policy.kind` 字段出现之前的记录记 `identity uncertified` 但**不拒**：把历史表全变成不可读不叫更安全。
`record.json` / `eval.json` /
`summary.csv` 一律 tmp + `os.replace` 原子落盘：截断的记录会让下一次 run 崩在解析上，而不是崩在一个决定上。

**摘要拼写按字段而异，别靠猜**（实测）：`env_cfg.digest` / `agent_cfg.digest` / `suite.digest` /
`assets.declared_digest` / `obs_protocol.digest` 是**裸 hex**；`eval_protocol.digest` /
`checkpoint.sha256` / `suite.geometry_digest` 带 `sha256:` 前缀。因此任何"声明值 vs 实算值"的比较
**必须先按摘要归一化**（先例 `suite_lock._bare`；报告仍保留读到的原文），否则正确的声明会被判成
mismatch —— 套件锁首次真跑就是这么红的，根因是这张拼写表此前没人写下来。字段**之间**的比较
（`record.compare` / `CONDITIONS`）不受影响：同名字段两侧同源，拼写必同。

**字段清单与采集点**：格式定义见 `record.py`，采集点在 `eval.py`。v1.8.0 新增：`judge` 块
（baseline 记判分器身份与来源；locomotion 记 `metrics.METRICS_ID` + `eval.DERIVATION_ID` 及其内核名单）、
`suite.lock` / `suite.geometry_env` / `suite.expected`（见"套件锁"节）、`summary.csv` 的 `variant` 列。
`metrics.derived`（`tilt_cos_min` / `clearance_min` / `sustain_steps`）是"指标实际用到的值"，v1.7.2
之前的记录没有它 ⇒ 读作未知，不算缺字段；其**身份**（把协议的度/比/秒换算成内核输入的那一套）是
`eval.DERIVATION_ID`，与 `metrics.METRICS_ID` 合成 locomotion 记录的 `judge.id`。

## 套件锁（协议自己冻结地形，v1.8.0 起）

只写 `suite: lizard_suite_v2` **不锁地形**：套件内容与种子住在 `suites.py`，网格由引擎生成，而协议
摘要（该 yaml 的 sha256）只覆盖 yaml 自己 ⇒ 两个自称同协议的 run 可以站在不同地面上，只能事后从
记录里的 `suite.digest` / `geometry_digest` 发现。故 v4 起在协议里写 `suite_expected`，运行前核对。
两步两因：

| 步 | 指纹 | 时机 | 为什么是这个时机 |
|---|---|---|---|
| 一 | `cfg_digest` | `gym.make` **之前** | 套件由本仓工厂构造，可离线算；错套件不该花一次启动 |
| 二 | `geometry_digest` | 生成之后、rollout **之前** | 网格由引擎产出，只有生成后才有；错地面不该被量完再丢 |

**三态而非二态**：几何摘要不同且**环境不同** ⇒ `unknown`，**不拒跑** —— 换机器不是改协议；只有环境
相同而几何不同才 `mismatch` 拒跑。`geometry_env` 记 sim / **PhysX** / numpy / warp / torch 版本、
GPU 与 compute capability、IsaacLab rev；`suite_lock.ENV_FIELDS` 是**封闭**列表，不在表内的新差异源
会读作 mismatch 而不是 unknown。

**两个套件摘要取的时刻不同，本就不等，别当成改动**：协议里的 `suite_expected.cfg_digest` 取在
`gym.make` **之前**（本仓工厂刚构造出的 importer cfg），而记录里的 `suite.digest` 取在**之后**
（IsaacLab 建 env 时已动过 terrain cfg）。跨 run 比较用记录里的那个（条件面用 `suite.digest`），
它实测跨协议版本逐字相同（v3 与 v4 记录一致）；只有把协议里的 `cfg_digest` 与记录里的 `suite.digest`
并排比才会看到"差异"——那是同一件东西在两个时刻的样子，不是谁被改了。

**摘要比较不计算法前缀**：`cfg_snapshot.digest` 返回**裸 hex**，而 `record.digest` 与地形探针返回
`sha256:<hex>`。比较按摘要而非拼写（报告仍保留读到的原文）—— 本锁首次真跑正是被这个拼写差误判为
`mismatch`，修的是比较而不是声明。

**指纹由人批注，闸门不自动写**：`eval.py --print-suite-fingerprint` 打印待粘块后即返回、不落任何记录
（走模块自身的关停路径，避免 Kit 关停吞掉退出）；把块粘进协议的 `suite_expected` 是人的动作 ——
自动重算等于把刚产生的值当成标准，那就没有"冻结"。v1–v3 无此声明，按历史协议放行（规则不回溯）；
**v4 起未声明即拒跑**。`locomotion_eval_v4` 已于 2026-09-22 真跑批注并解锁，且其 `geometry_digest`
与既有 v3 记录逐字相同 —— 同套件同种子在不同协议版本下是同一块地面，这是锁量对了的旁证。

## 升级触发（防"永远不升"）

harness 代码高频变更 / 多机器人共用 / 再开新协议时 → 目录化 `versions/harness/vN/`（协议 yaml + NOTES
进版本目录，与家族配方同款冻结纪律）。

**跨协议规则（现行约束，不是将来时）**：老跑分留在各自 `results/<协议>/` 原地不迁移；
**禁止跨协议直接对比**（任何表格/图表不得混 v1 / v2 / v3 / v4 行）；新协议新起 campaign 目录，
`--report` / `--summarize` 按协议目录天然隔离。v1.8.0 起这条**部分由机器执行**：`--summarize` 按
条件面（见记录格式节）逐对比较，冲突即非零退出。**闸门只覆盖它看见的字段** —— `policy.kind`
（零动作冒烟行混进真分数表）自 2026-09-23 起由 `--summarize` 单独拒绝（记录格式节 ④），
图表/HTML 不经过 `--summarize`，那部分仍是纪律。

## 与 rl_exp 的契约（单向消费，改动必跑闸门）

- 任务 id：suites 引用 rl_exp 注册的 gym 任务（`import isaaclab_tasks` 触发注册链）
- DR 事件名：`components/dr_controller.py` ↔ rl_exp `play_utils.py` 9 事件清单，`check_dr_parity` 双向看守
- 机器人块：ArticulationCfg parity（family vs teacher）
- 套件几何指纹：`suite_lock` 的 `geometry_digest` 来自 `rl_exp/tasks/terrain_geometry.py`（`seed_rngs` +
  `evidence`）与 `rl_exp/tools/verify/terrain_split_probe.py`；`geometry_env`（含 PhysX 版本）决定该指纹
  是 `mismatch` 还是 `unknown`。这条依赖是**单向**的：harness 读 terrain_geometry 的产物，它不知道
  评测台存在；terrain_geometry 改口径即等于换地面，v4 会拒跑而不是静默换量

→ 任何 harness 代码变更后必跑 `rl_exp\tools\verify\run_offline_checks.bat`（闸门红 = 不提交）。

## 挂账（正文已迁 `work/`，本表只留 id 与指针）

**新增待办直接开到 `work/active/`，不要往本表加行**；本表随批次收干。

| # | 事项 | 指针 | 优先级 |
|---|---|---|---|
| 1 | 运行时验收未跑完（跨协议对照 / 基线重跑 / rough 两列分布） | → `work/active/runtime-acceptance-v3.md` | 高 |
| 2 | 记录格式的剩余真跑段（rsl_rl 身份 / num_envs 格子 / 资产 fail 路径待授权） | → `work/active/record-format-live-checks.md` | 中 |
| 3 | 地形随机源两处缺口 + 几何证据归档（已收） | → `work/closed/2026/terrain-suite-v2-rng.md`、`work/closed/2026/terrain-evidence-18b.md` | — |
| 4 | 地形证据归档位置与 `rebuild.py` 角色（已裁决：运行目录 + 材料完整性） | → `work/closed/2026/archive-location-decision.md`；裁决见 `acceptance/records/2026-09-22-terrain-evidence-archive-and-verification.md` | — |
| 5 | 诊断 run 与 campaign 表之间没有闸门（已收：汇总侧按身份拒表） | → `work/closed/2026/diagnostic-run-gate.md`；读数见 `acceptance/records/2026-09-23-diagnostic-row-identity-gate.md` | — |
| 6 | `--headless` 已弃用而本仓仍在用 | → `work/active/headless-flag-deprecation.md` | 低 |
