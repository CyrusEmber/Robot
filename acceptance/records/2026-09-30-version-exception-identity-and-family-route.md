# 版本例外的身份合成、退休版齐件豁免、家族走路由（bcd 三条旁链）

- 日期：2026-09-30
- 范围：`work/active/body-swap-and-version-retire.md` ⑧ 的三条旁链 —— B 身份、C 齐件、D 路由
- 关联：`acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation.md`（家族级声明与 `family_of` 的先例）

## 适用范围

本次只处理该事项 ⑧ 里点名可并行的三条旁链：

1. **B 身份**：`versions/lines.json` 的版本例外（`versions` 子映射）+ `check_recipe_registry.effective_status` 作为"线状态 + 版本例外"的唯一读者 + `lifecycle.identity()` 在启动侧合成状态。
2. **C 齐件**：`check_version_docs.py` 的齐件要求按版本状态取值（退休版免 `asset_lock.json`）。
3. **D 路由**：`check_contact_ownership.py` 的家族改从任务的声明路由取。

不覆盖：主链（`check_dr_parity.py` 的锁构造 ④、检查 ⑤、换代检查 ①）；`lines.json` 里**实际**退休 `lizard2/main/v1`（⑥ 退役动作 + ⑦ 缺口记录归该事项收尾）；`versioning.mdc` ② 的规则正文；`check_contact_ownership.py` 在 sim 里的实跑。

## 验收条件

1. 退休版本拒绝新训与续训，且状态只在**一处**合成（`recipe_lifecycle.judge` 与它的用例表不变）。
2. **线 retired 优先**：一份没有先过 `validate` 的索引（例外写 `active`）不得把退役线读回 active。
3. 退休版不要求也**不读** `asset_lock.json`，PLAN/NOTES/yaml 仍要求；非退休版缺件、缺锁、锁不认自己 yaml 仍红。
4. 家族取自任务的声明路由，不再从 spawn 路径反推；路由为空 ⇒ 拒绝而非猜。
5. 每条新判据都有反证，且**还原修复前行为后必然着火**；离线套件条目数不变。

## 结果

**合成点（B）**：`effective_status(registry, line, version)` 是唯一读者 —— `line` 的状态先判（`retired` 直接返回，例外不能把退役线的某个版本读回 active），`active` 线上才看该版本的例外；例外存在但不可解析（未知 status）返回 `None` 而非回落到线状态。启动侧 `lifecycle.identity()` 的版本取 `recipes.json` 的 `legacy_task_version`（身份映射已把它绑到 cfg 的 `params_version`，**不**从任务 id 反解析），T0 的 `evidence` 增加 `version` 一项。

**齐件条件（C）**：`required_pieces(retired)`；退休版的锁既不要求也不读，非退休版仍按摘要语义读。索引不可用时报告一条并以"无状态 ⇒ 不免除"处理。

**路由（D）**：`obs_protocol.family_of(task)`，空 ⇒ `SystemExit`。今天两条路径**同答**（所有冻结版本的 `usd_path` 都是 `assets/<family>/<family>.usda`，`parent.name` 恰等于家族名），本次去掉的是这个巧合而不是修一个当场错的值。

**反证（还原修复前行为，逐条返回 1 = 咬住）**：

| 还原成 | 着火的判词 |
|---|---|
| 例外先于线状态 | `an exception cannot put a retired line's version back in service: effective_status -> 'active', expected 'retired'` |
| 齐件无状态条件 | `a retired version keeps the record and drops the lock: expected ('PLAN.md', 'NOTES.md'), got ('PLAN.md', 'NOTES.md', 'asset_lock.json')` |
| 启动只读线状态 | `new training on a retired version must be refused`（resume 同）+ `the refusal must name the version and the composed status` |

**读数**：`run_offline_checks.bat` → `ALL_OFFLINE_CHECKS_PASSED (47/47 in 55.5s)`，其中 `[14]` 齐件闸打印 `VERSION_DOCS_OK`、`[30]` 生命周期闸 `lifecycle consistent`（含新增的版本例外反证与 8 例状态读法）、`[39]` 启动闸 `LIFECYCLE_STARTUP_OK`。`check_version_docs` 在真实树上打印 `retired versions (19, asset_lock.json not required)` —— lizard 全族按线状态继承，lizard2 目前无例外。

## 证据引用

- 命令：`rl_exp\tools\verify\run_offline_checks.bat`；单跑 `check_recipe_registry.py --self-test`、`check_version_docs.py --self-test`、`test_lifecycle_gate.py`
- 落点：`rl_exp/tools/verify/check_recipe_registry.py`（`_check_versions` / `effective_status`）、`rl_exp/tools/verify/test_recipe_registry_gate.py`（版本例外 8 例 + 状态读法 8 例）、`rl_exp/tools/runrecord/lifecycle.py`（`identity`）、`rl_exp/tools/verify/test_lifecycle_gate.py`（`_version_cases`）、`rl_exp/tools/verify/check_version_docs.py`（`required_pieces`）、`rl_exp/tools/verify/check_contact_ownership.py`、`rl_exp/versions/lines.json`（四条线补 `"versions": null`）
- 路由旁证：同环境的导入与解析实测 `family_of('Lizard2-Flat-v1')='lizard2'`、`family_of('Lizard-Baseline-Flat-v2')='lizard'`、未声明任务 `None`

## 未覆盖边界

- 真实 `lines.json` 里**还没有任何版本例外**，"退休版免锁"这条路径目前只在合成树的用例里被验证过；它第一次真正生效要等 ⑥ 退休 `lizard2/main/v1`。
- **没有闸门要求退休版的锁被删掉**：C 只是"不要求"，孤儿锁的守卫（主链 ⑤）口径是"锁没有主人"，不是"主人已退休却还留着锁" —— 所以 ⑥ 忘了删锁不会有任何红。代价有限（锁仍是"只冻结一次"的字节记录，不参与任何判定），但这是本次设计里唯一没人看守的位移。
- D 未在 sim 里实跑（成本=起 Isaac Sim）；本次只证明导入链可用、路由答案正确，探针本体未执行。
- `legacy_task_version` 为 `null` 的配方（v0 一批）只继承线状态，版本级退休对它们不适用 —— 这是声明侧的缺口（任务 id 的版本只在 vN 命名里出现），不在本次能补的范围内。
- 主链未做，故"换代检查 + 资产验收"共用 `_lock_files` / 当前机体解析器这件事仍只是计划。
