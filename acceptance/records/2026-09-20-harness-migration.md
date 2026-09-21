# HARNESS 迁移（批次 1）：搬运 + 四项走查

## 适用范围

`ablation_harness/HARNESS.md` 的分流：待办迁成事项、版本史与修订记录移出、规则点名执行者。
时点 2026-09-20。对象是**这一份文档**，不外推到 `PLAN.md` / `ACCEPTANCE.md`（批 2 / 批 3），
也不改任何 `ablation_harness/` 代码行为。

## 验收条件

主判据 = **可定位 / 可执行 / 可关闭 / 无约束遗漏**，对每个迁移产物人工走查，并**真的沿
"下一步 → 观测 → 分支结论"走一遍**；"确认后可关"式措辞即使过格式检查也判该产物不通过。
形状侧由 `check_work_docs.py` 看守（字段、状态词表、落点与证据存在、id 唯一、活跃预算）；
文档侧由 `check_version_docs.py` 看守（四件套 / 版本行 / 无判词泄漏）。

## 结果

**搬了什么**（HARNESS 26315 → **6017** 字节）：

| 原内容 | 去处 |
|---|---|
| 挂账 #1 的未做半（跨协议对照 / 基线重跑 / rough 两列分布） | `work/active/runtime-acceptance-v3.md` |
| 挂账 #2 的未做半（rsl_rl 身份 / `num_envs` 格子 / 资产 fail 路径） | `work/active/record-format-live-checks.md` |
| 挂账 #3 ①②（套件粗糙列退化 + 训练侧未播种，已收） | `work/closed/2026/terrain-suite-v2-rng.md` |
| 挂账 #4（两处规格偏离待拍板） | `work/active/archive-location-decision.md`（`blocked`） |
| 挂账 #5 / #6 | 已经是指针，未动 |
| 版本历史 + 修订记录（**同一批版本的两份日志**） | 删除；正文归 `git log -p ablation_harness/HARNESS.md` 与 commit message |
| 记录格式一节 | 压缩：四条读侧规则 / 可比性 / 写侧硬门逐条**点名执行者**（`record.read_state`、`record.BINDINGS`、`_persist`、`test_eval_record.py`） |
| 升级触发里的"协议 v2 出现时/落地时" | 改为**现行规则**（跨协议禁止混表），依据 = `eval.py` 的 `--protocol` 默认值已是 v3 |

**四项走查**（逐产物）：

| 产物 | 可定位 | 可执行 | 可关闭 | 无约束遗漏 |
|---|---|---|---|---|
| `runtime-acceptance-v3` | ✅ | ✅ 三条各有动作与口径 | ✅ 各条观测 + 不达标时的分支 | ✅ 已做半写在项内；"v2 行不得混表"在项内，不靠读者去别处拼 |
| `record-format-live-checks` | ✅ | ✅ | ✅（③ 依赖授权 —— 已写成"授权无结论则拆出单列，本项只关 ①②"） | ✅ |
| `archive-location-decision` | ✅ | ✅ 两条待答问题写全 | ✅ 观测 = 两处不再出现"未获确认前不得当成照原文交付" | ✅ 用 `blocked` 区分"实现已生效、认可未给" |
| `terrain-suite-v2-rng`（关闭） | ✅ | — | ✅ `landing` 五处均指向现存机制，无 `next` | ✅ 未覆盖边界指向另两个关闭项 |

**走查发现的缺口（本批唯一一处）**：删掉版本史时，有三条**只在旧版本史里写过**的事实没有家 ——
① v1 训练总时 25.735 h，其中 `it=11438` 单次停顿 7.2 h（做消融的时间预算依据）；
② "记录链的源头（tfevents）在机器本地且会被清理 ⇒ 记录必须入库"（v1.5.2 的理由）；
③ "别把调用路径的父目录当配置"（v1.5.1 的 provenance 串位教训）。
**已归位（2026-09-21）**：① → `rl_exp/versions/lizard/main/v1/NOTES.md`「时间预算」节；② → `rl_exp/docs/pitfalls.md` P007；③ → 同文件 P008。**本记录不再持有正文，也不再有"去处待决"这一状态**（归位动作由 `work/closed/2026/historical-facts-homing.md` 收口，上面 ①②③ 三行只作摘要留痕）。

**预算**：搬完 `work/active/` 为 19265 / 24000 字节（80%）。注意其中约 5 KB 是**另一位开发者**
同期开的两个事项与一条记录（`baseline-eval-protocol-gap`、`eval-protocol-before-training`、
`2026-09-20-baseline-flat-eval-protocol`），它们未改一行文档就被本闸门接受通过。

## 证据引用

- 闸门：`check_work_docs.py` → `WORK_DOCS_OK (10 item file(s))`；`check_version_docs.py` → `VERSION_DOCS_OK`。
- 体积：`Get-Item ablation_harness/HARNESS.md | Select Length`（字节，非字符）。
- 版本史正文：`git log -p ablation_harness/HARNESS.md`（本批删除前的内容在删除提交的父版本里）。
- 逐条挪动：`git show --stat` 与上面"搬了什么"表一一对应。

## 未覆盖边界

- 只做 `HARNESS.md` 一份；`PLAN.md`（批 2）、`ACCEPTANCE.md`（批 3）与仓根文档未动 记录格式**只做压缩与点名执行者**，没有把散文规则变成新断言：若某条其实无执行者，本批不会发现。
- 三条历史事实的家未定（见"走查发现的缺口"）。
- 代码注释里指向已迁走内容的指针（`tasks/*.py`、`teacher_smoke.py`）与两处陈旧 docstring 路径仍在，
  属代码文件，另行安排。
- 本批未做读取成本对照：批级只验四项，成本对照只在试点做过一次。
