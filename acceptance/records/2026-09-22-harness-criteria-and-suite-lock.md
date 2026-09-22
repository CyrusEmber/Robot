# 判据身份化与套件指纹锁 — 验收记录

## 适用范围

本次提交覆盖 `ablation_harness/` 的四件事：

1. **baseline 判据从"阈值键"改为"具名判据 kind + 判分器身份"**：`baseline_flat_v4.json` 用 `criteria`
   声明判据，`baseline_metrics.CRITERION_KINDS`/`CRITERIA` 是唯一判分入口，`judge_semantics.json`
   把判分器身份钉到用例与预期上。
2. **locomotion 套件的两步指纹锁**：`suite_lock.py`（纯逻辑）+ `locomotion_eval_v4.yaml`（冻结指纹）
   + `eval.py` 的两处核对（cfg 在 `gym.make` 前、geometry 在生成后 rollout 前）。
3. **汇总表的条件面闸门**：`record.CONDITIONS` / `conditions_conflict` / `table_conflicts` +
   `run_ablation.py --summarize` 的非零退出。
4. **locomotion 判据身份**：`loco_judge.py` 承载派生半（`derived_thresholds`）与身份（`JUDGE_ID`
   = `metrics.METRICS_ID` + `DERIVATION_ID`），记录里的 `judge` 块由此合成。
5. **locomotion 判据的冻结用例表**：`judge_semantics.json` 第三个 id 块，14 条用例覆盖派生与内核边界。

覆盖面分两层：**离线可判**的部分由套件逐条看守；**真跑**部分只有本记录第"结果"节列出的那几次
Kit 运行（v4 解锁前的拒跑与解锁后的冒烟各一次），其余真跑一律不主张。

## 验收条件

| 检查 | 命令 | 通过标准 |
|---|---|---|
| 离线套件全量 | `rl_exp\tools\verify\offline_suite.py` | 47/47 全绿，含 work-ledger 形状与版本文档漂移两项 |
| baseline 判据与边界 | `rl_exp\tools\verify\test_baseline_contract.py` | 既有全部回归不变；新增用例全绿 |
| 冻结用例表 | 同上（`test_judge_semantics_are_frozen_and_hold`） | 每个 id 的 `kinds_sha256` 与 `frozen_sha256` 与块内一致，且块内每条用例产出与预期一致 |
| 套件锁三态 | `rl_exp\tools\verify\test_eval_frame_v2.py` | match / mismatch / unknown 三分，且只有"该阶段已存在"的指纹能拒跑 |
| 记录条件面 | `rl_exp\tools\verify\test_eval_record.py` | 27 passed；checkpoint 差异**不**构成同表冲突，assets 差异需显式声明 |
| locomotion 用例表 | `test_baseline_contract.py::test_judge_semantics_are_frozen_and_hold` | 三个 id 的用例全绿；**负控制**：把 fixture 的 dwell 改成 `sustain-1`（冻结块不动）必须红且点名用例 |
| 摘要跨拼写 | `test_eval_frame_v2.py::test_a_digest_is_compared_without_its_algorithm_prefix` | 带/不带 `sha256:` 前缀四种组合都判 match；真差异仍 mismatch 且报告保留原文拼写 |
| 真跑：锁拒跑（cfg 阶段） | `eval.py --task Lizard-Rough-v14 --protocol locomotion_eval_v4 --print-suite-fingerprint --headless` | 声明与实算不一致时在 `gym.make` **之前**拒跑、非零退出、不落记录、进程正常关停 |
| 真跑：批注后解锁 | 同上但不带 `--print-suite-fingerprint` | 正常落 `record.json`（`state=complete`），`suite.lock.verdict == match`（cfg 与 geometry 均 match） |
| 逐项判据 | 各文件内断言 | 边界相等、持续时间、身体交替接触、白名单拒绝、摘要冻结 |

**逐项判据**（这些是本次新增的语义断言，不是"跑通即过"）：

- **边界相等**：tracking 归一化误差恰等于阈值 ⇒ 失败（严格 `<`）；displacement 恰等于阈值 ⇒
  失败（严格 `>`）；contact 恰在载荷上限 ⇒ 通过（`>` + `eps`）；carrier 承重比恰等于阈值 ⇒
  失败（`>=` 含等号）；mesh 恰好触及声明的下限 ⇒ 失败（严格 `>`）。
- **持续时间**：tilt 恰持续 `sustain_s` ⇒ 失败，短一帧 ⇒ 通过；carrier 同理。
- **身体交替接触**：两个身体交替承重，各自最长连续一帧（远低于门限），跨身体合并 ≥ 门限 ⇒
  门禁失败。该断言显式读出"逐身体最长连续"与"跨身体合并"两个数，证明聚合顺序是判据而非实现细节。
- **判据声明不可读即拒**：未知 kind / 多余参数 / 缺参数 / 未知 gate / 空 block / 参数为 null ⇒
  `invalid` 且报错点名；v4 缺 `criteria` 不回落旧路径。
- **旧路径白名单**：无 `criteria` 且身份不在白名单 ⇒ `invalid` 并说明"会变成猜判据"；白名单内
  （`Baseline-Flat-v1/v2/v3`）照旧判分，`judge.id` 记为 legacy 身份。
- **旧路径不静默降级**：`gates` 里出现读者不认识的键 ⇒ 拒；同时给出绝对与归一化两种跟踪口径 ⇒
  拒；缺伴随键（如 `tilt_sustain_s`）⇒ 拒并点名该键。
- **摘要冻结**：改旧 id 的用例块或改 kind 表 ⇒ 红，且报错指向"发布新 id"。
- **套件锁阶段归属**：cfg 指纹在 `gym.make` 前核 只能在地形生成后核 —— 后者在 cfg 阶段
  **不得**拒跑（否则 `--print-suite-fingerprint` 永远到不了终点）。
- **环境差异不误报**：几何摘要不同且环境不同（PhysX 版本变化）⇒ `unknown`，不拒跑；环境相同而
  几何不同 ⇒ `mismatch` 拒跑。
- **v4 未指纹化前拒跑**，且 v1–v3 作为历史协议不被回溯要求。

## 结果

全部通过：离线套件 47/47；`test_baseline_contract.py` 与 `test_eval_record.py`（27 passed）、
`test_eval_frame_v2.py` 全绿。

过程中发现并修掉三处**实现**错误，都留下了回归或注释说明：

1. **legacy 桥复制了键而不是参数**（`params = dict(spelled)` 应为参数体）——被既有回归当场抓住，
   说明"改造必须让旧用例原样通过"这条纪律有效。
2. **我的阈值边界用例自己踩了浮点表示误差**：首版用 1000 步 × 0.02 s，`expected_m` 是逐帧求和，
   ulp 偏差让"恰等于阈值"落到阈值之上。改用 1024 步（步长 5/256 s，二进制精确），原因写在
   fixture docstring 里。这条值得记住：**边界用例的输入必须二进制精确，否则测的是浮点不是判据**。
3. **fixture 的 `kw` 语义含混**（"span 秒数"被当成"门限秒数"）导致交替接触的两个用例预期反了。
   改名 `span_s` 并把"逐身体 vs 跨身体"的读数做成显式断言，而不是只写在 JSON 预期里。

另外确认了一处**设计边界**：`_GATED` 表里原先的 `direction`/`sustain` 两列从未被消费（判分写在
`_score` 里），所以"把 `direction` 搬进协议"是空转 —— 真判据必须连同比较方向、严格性、单位换算与
聚合顺序一起收进 kind。这也说明判据声明化不能只搬参数。

### 真跑（两次 Kit 运行）

第一次（打印指纹）**拒跑**，抓到的是我声明里的真实缺陷：`cfg_snapshot.digest` 返回**裸 hex**，而
`record.digest` 与地形探针返回 `sha256:<hex>`，我按后者习惯在 YAML 里写了前缀 ⇒ `cfg` 阶段即
`mismatch`。修法是让比较**按摘要而非拼写**（`suite_lock._bare`，报告保留原文），并加回归。这次拒跑
同时证明了三件设计意图：拒跑发生在 `gym.make` **之前**（不花一次启动）、非零退出且**不落任何记录**、
进程正常关停。（关停这一条是**跑之前读代码**发现的、不是这次跑发现的：原写法用 `raise SystemExit`
会跳过 `simulation_app.close()`，已改为从 `main()` 返回、交给模块自身的关停路径 —— "退出即跳过关停"
正是本仓付过代价的那个坑。）

第二类：修后重跑打印到指纹块并人工批注，随后一次**不带** `--print-suite-fingerprint` 的 v4 真跑正常
落盘（`record.json`，`state=complete`），`suite.lock.verdict == match`（cfg 与 geometry 均 match）。

两条旁证（都是精确比对，不是推断）：

- 该次真跑的 `geometry_digest` 与既有 `results/locomotion_eval_v3/smoke/...` 记录里的**逐字相同**
  ⇒ 同套件同种子在不同协议版本下是同一块地面，锁量的是对的东西。
- 记录里的 `suite.digest` 在 v3 与 v4 两次记录里也**逐字相同** ⇒ `gym.make` 之后的那次快照是确定性的，
  条件面拿它做跨 run 比较成立。注意它与协议里的 `cfg_digest` **本就不等**（取的时刻不同，前者在
  `gym.make` 之后），已写进 `HARNESS.md`，免得后来者把它当改动。

`physx_version` 真取到 `6.0.0.1`（`_physx_version()` 走 `isaacsim-extscache-physics` 命中），
"取不到即 unknown"因此不再是唯一被验证的分支。

## 证据引用

- 代码：`ablation_harness/baseline_metrics.py`、`baseline_eval.py`、`record.py`、`metrics.py`、
  `loco_judge.py`、`eval.py`、`run_ablation.py`、`suite_lock.py`
- 声明：`ablation_harness/judge_semantics.json`（三个 id 块）、`ablation_harness/protocols/baseline_flat_v4.json`、
  `ablation_harness/protocols/locomotion_eval_v4.yaml`（已批注指纹）
- 用例：`rl_exp/tools/verify/test_baseline_contract.py`、`test_eval_record.py`、
  `test_eval_frame_v2.py`（契约登记在 `offline_suite.py` 的同一 Check 内，未新增条目）
- 真跑证据：`ablation_harness/results/locomotion_eval_v4/Lizard-Rough-v14_v4unlock_nominal_seed123/record.json`
  （`suite.lock` 三项均为 match）；拒跑那次的输出留在会话记录，未落文件（设计上不落）
- 命令：`rl_exp\tools\verify\offline_suite.py`；`test_baseline_contract.py --print-frozen` 用于人工
  发布新 id 的摘要；`eval.py --print-suite-fingerprint` 用于人工批注指纹

## 未覆盖边界

- **`geometry_env` 是本机的**：真跑只在 RTX 3060 Ti / Isaac Sim 6.0.0.1 / PhysX 6.0.0.1 上做过；
  换机器时锁给 `unknown`（不拒跑）—— 也就是说**换机器这件事本身不被拦住**，只有"换机器且地面不同"
  才可见。跨机器一致性没有证据。
- **只有冒烟档位真跑过**：解锁后的那次是零动作冒烟（`checkpoint=none`），**没有**用真策略跑过 v4；
  `produced by a policy` 这条路径在 v4 下未验证。
- **`suite_lock.ENV_FIELDS` 是封闭列表**：不在表内的新环境差异源会读成 `mismatch` 而非 `unknown`。
- **用例表只覆盖写下来的用例**：kind 内部未被用例触达的行为仍可在不触发任何红的情况下改变；
  派生浮点四舍五入到 9 位，1e-9 以下的变化看不见。
- **`_physx_version()` 的三个拼法只命中过一个**：本机走的是发行包分支，运行期 accessor 那条分支
  未被执行过。
- 不覆盖真机多 GPU、不覆盖跨协议历史记录的重判（本次未重判任何既有记录）；`diagnostic-run-gate`
  （`policy.kind` 不属同表条件面）仍在 `work/` 里开着，不在本记录范围。
