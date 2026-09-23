# 阈值试点：验收以什么为据，检查执行却为空（第 3 步，2026-09-23）

## 适用范围

- 实测对象：`ablation_harness/protocols/baseline_flat_v4.json` 的一次**纯阈值改动**（受控变更：就地替换首个
  `"threshold": 0.2` → `0.25`，即 `criteria.tracking.params.threshold`，字节差 1；`try/finally` 还原并逐字节校验）。
- "检查执行"面 = **全量离线套件**（47 条）＋单独加载该协议的两条检查（`test_baseline_contract.py`、`test_eval_frame_v2.py`）。
- **不覆盖**：协议数值锚的**实现**（未建，见末节）；`lizard2_flat_v1` 未测（它带 `suite_expected` 与四个新 kind）；
  只测了 tracking 一个轴；第四步去重候选。

## 验收条件

1. 一次纯阈值调整**不必换 kind**。
2. 不必在多处抄同一组数值。
3. 旧协议与旧记录**仍可读**。
4. 本次新增的一条：**"检查执行"阶段必须给实测**（会不会红），不许只推断——正是这条把自己证伪了。

## 结果

**一、检查执行阶段今天为空（实测，非推断）**

```
$ python "%TEMP%\probe_threshold_suite.py"          # 阈值改成 0.25 的状态下跑全量套件
runner rc = 0
ALL_OFFLINE_CHECKS_PASSED (47/47 in 45.3s, wave 227s/informational, jobs=6)
not-ok lines: none
restored byte-exact: True
```

单跑那两条加载它的检查同样 rc=0（`test_acceptance_metrics: 5 passed`／`ALL_EVAL_FRAME_V2_TESTS_PASSED`）。
⇒ 就地改掉一个已冻结协议的阈值：**没有任何闸门或测试发现**。旧记录里那个 `eval_protocol.digest` 会对不上磁盘文件，
而没有任何东西去核（第 1 步已核：摘要仓内无第二副本，校验等于重算）。

**为什么抓不到**：`test_v4_reproduces_v3_on_one_record`（`test_baseline_contract.py:1112-1120`）的 docstring 写着
"v4 renames the criteria and changes no number"，但它断言的是**同一记录下 v3 与 v4 的 verdict／gates／metrics 一致**
——那是"地板一致"，不是"数值相同"；只要这条记录在 0.2 与 0.25 下都过，改动就溜过去。
`judge_semantics` 的 `kinds_sha256`／`frozen_sha256` 只覆盖 kind 表与用例；`suite_lock` 只冻地形指纹。

**二、验收三条：成立，且手改面被数清**

| 判据 | 实测 |
|---|---|
| 不必换 kind | 成立。`CRITERION_KINDS` 只钉参数**名**（`baseline_metrics.py:88-108`），数值在协议正文里 |
| 不必多处抄 | 手改面 = **1 个数字** + **2 处散文复述**：`baseline_flat_v4.json:21` 的 `why_v4`（写"数值与 v3 逐字相同"）、`HARNESS.md:20-21`。这 2 处**没有任何提示**要你跟着改 |
| 旧协议与旧记录可读 | 成立。协议文件不被本次改动触碰；旧记录保留其摘要，指向当时的字节（前提是没人就地改——见第一条） |

**三、四阶段流程的实测（试点就是走一遍它）**

| 阶段 | 本次实际 |
|---|---|
| 候选 | 1 字节替换（`0.2` → `0.25`） |
| 差异摘要 | 单叶子路径：`criteria.tracking.params.threshold`（一份现成的 JSON 差异即可表达） |
| 审查批准 | 人定（本次为受控变更，批准=还原） |
| 检查执行 | **空**——见第一条 |

**四、因此本次不新建"候选生成器"**：改动面是 1 个数字，给它造生成器是多余机器；`grep <旧值>` 已经是找那 2 处散文的工具。
真缺的是**批准锚**（让"就地改数值"从静默变成必须显式批准），它属第 2 步式的补缺口，不是第 3 步的流程收敛。

## 证据引用

```
$ python "%TEMP%\probe_threshold_change.py"                 # 单跑加载它的两条检查
mutated bytes: 1 | changed: True
--- rl_exp/tools/verify/test_baseline_contract.py: rc=0
    test_acceptance_metrics: 5 passed
--- rl_exp/tools/verify/test_eval_frame_v2.py: rc=0
    ALL_EVAL_FRAME_V2_TESTS_PASSED
restored byte-exact: True

$ python "%TEMP%\probe_threshold_suite.py"                  # 全量套件（上面"结果"节原文）

$ python -c "..."        # 第 1 步的计数器复算：该文件里的 threshold 命中
ablation_harness/protocols/baseline_flat_v4.json 30  "params": {"threshold": 0.2, "normalized": true}
```

（探针脚本在 `%TEMP%`，两条都跑完即删；它们改的是工作树文件，`finally` 还原并逐字节校验。）

## 未覆盖边界

- **协议数值锚未建**：就地改阈值仍然静默。它是**新候选**，按第 4 步三问要先答"原抓什么错／预期或批准依据来自哪里／
  删或加之后由谁接替"，且落点有两条不相上下的路：① 在既有 `judge_semantics` 的 id 块里加 `protocol_sha256`
  （但会改到已发布块的 `frozen_sha256`，需要一次显式重钉 + 记录）；② 新建一张小批准表（协议文件 → 摘要 + 理由），
  核验折进既有入口 `test_eval_frame_v2.py`（其标签已含"v4 suite lock"），形态照抄 `suite_lock.fingerprint_block`
  的"打印 → 粘贴 → 比对"（`suite_lock.py:142`）。两条都由 owner 定，本次不预设。
- `lizard2_flat_v1` 未测：它已带 `suite_expected`，但"它自己的锁是否也拦不住阈值改动"未实测。
- 只测了 tracking 一个轴；displacement／attitude／contact 轴未逐轴测（同一机制，但未证）。
- 第 3 步的"候选可写入独立文件"这一形态未验（本次候选只存在于探针里，未落盘）。
