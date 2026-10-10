# 待审核状态与关闭前独立审核：机制与试审（2026-10-10）

对象：`rl_exp/tools/verify/check_work_docs.py` 与 `AGENTS.md` 的关闭流程（活跃事项
`pending-review-before-close`，审查时状态 `pending_review`）。
审核者 = 新上下文 subagent（不带执笔会话历史），只给事项、改动对象与命令，不给执笔者总结。

## 适用范围

- 覆盖：工具侧的 `pending_review` 状态、closed 树反向闸门、`--list` 状态匹配、自测 fixture 与
  断言；`AGENTS.md` 的关闭流程文本；以及"审核者是否会拒绝缺证据的关闭候选"这一负向对照。
- 不覆盖：任何训练/仿真读数（本次改动不触及），`work/closed/2026/` 既有 55 项的历史关闭质量，
  以及"审核是否真的发生过"（见未覆盖边界）。

## 验收条件

1. 状态集合含 `pending_review`，且它在 active 树合法、在 closed 树报红。
2. `--list pending_review` 能列出待审项，且不会因状态匹配产生假阳性。
3. 上述两条检查在删掉各自逻辑时**自测必须报红**（否则该检查未被验证）。
4. `AGENTS.md` 的流程与工具实际行为一致，不出现"工具做不到却写成闸门"的句子。
5. 审核者对"证据缺失的关闭候选"必须给拒绝；放行即说明该审核是盖章。

## 结果

**判定：PASS-WITH-GAPS。** 逐条：

- 条件 1、2、3 成立。自测基线 `WORK_DOCS_SELF_TEST_OK (17 item + 3 record + 3 pointer fixtures)`；
  真实树 `--list pending_review` 打印 1 行待审项；`--list blocked` 4 项全为 `[blocked]`、
  `--list open` 14 项全为 `[open]`，四项 id/title/scope 均不含 "blocked"，无假阳性。
- 破坏测试（在仓外副本上做，副本的 `_REPO` 解析到临时根，真实树那半读空树属预期）：

  | 破坏 | 自测输出 |
  |---|---|
  | 去掉 `if item.closed and status == "pending_review":` 闸门 | `FALSIFIER: falsifier did not fire: "'pending_review' is unverified work sitting in the closed tree"` + `the unverified-close gate fired on [] instead of only closed-pending-review.md` ⇒ `WORK_DOCS_SELF_TEST_DRIFT (2)` |
  | 去掉 `_list_lines` 里的 `+ i.fields.get("status", "")` | `FALSIFIER: \`--list pending_review\` printed [] instead of the one item awaiting review` ⇒ `WORK_DOCS_SELF_TEST_DRIFT (1)` |

- 条件 4 成立（无矛盾），但审核者给出**一条未定价的后果**：`AGENTS.md` 只写"事项只留指针"，而工具的
  `evidence` 存在性闸门要求该路径此刻存在 ⇒ 若先写指针、后补记录，待审项在记录落地前恒为 DRIFT
  （当时真实树确为 `WORK_DOCS_DRIFT (1)`，退出码 1，而 `offline_suite.py` 把该命令的 rc≠0 记为 FAIL
  并触发 fail-fast）。**已按此修**：`AGENTS.md` 补一句"记录与本项在同一次变更里落地，不能先写指针
  后补记录"，本记录即与该句同批落地。
- 条件 5 成立：负向对照（`status: done` + `outcome` 断言离线用例全绿、无 `evidence` 指针、记录未具名）
  判 **REJECT**，理由为判据的两半都不可读、连"用户给过口径"这一前提都无法核实。

## 证据引用

- 工具与流程：`rl_exp/tools/verify/check_work_docs.py`（`_STATUS` / `_TERMINAL` / closed 树闸门 /
  `_list_lines` / `self_test`），`AGENTS.md` §Where the work lives。
- 复读命令：`python rl_exp/tools/verify/check_work_docs.py --self-test`；
  `python rl_exp/tools/verify/check_work_docs.py --list pending_review`；
  破坏测试须在仓外副本上做（`git diff -- rl_exp/tools/verify/check_work_docs.py` 给出被破坏的两处）。
- 审核者结论（原文摘）：`VERDICT: PASS-WITH-GAPS`；`Negative control: REJECT`；
  "Both checks bite; neither is a rubber stamp"。

## 未覆盖边界

- "审核真的发生过"不可由文件判定：工具自测只证明**形状**，记录存在不等于被读过。本条状态因此只做
  一步、不设机器闸门；判真伪靠 review。
- 没有任何闸门要求 `next` 里真的写了审核者——审核者是自由文本里的角色，不是可校验字段。
- 审核者只以**角色**（新上下文）具名，不绑到具体人或会话 ⇒ 滞留的待审项没有可追的责任人；
  本次未引入超时/催办机制（不新增调度器）。
- 本次改动的语义边界未变：`--list` 只多匹配一个字段，打印行不变，`LIST_BYTES`/`BUDGET_BYTES`
  读数不受影响；`work/closed/2026/` 既有条目一个未动。
