# 2026-09-23 汇总侧身份闸门：诊断行不许坐进真分数表

## 适用范围

- 对象：`ablation_harness/run_ablation.py --summarize` 的**行身份**判定（`policy.kind`），
  即 `_identity_report` 及其接线；落点 `work/active/diagnostic-run-gate.md`（HARNESS 挂账 #5）
- 覆盖：非 `smoke` 表里出现 `policy.kind != checkpoint` 的行时是否拒绝、退出码、以及三类行的反证
- 不覆盖：诊断 run **本身**的数值是否正确；`--by-terrain` / `plot_eval.py` / HTML 报表；历史数据是否要搬迁

## 验收条件

1. **非 smoke 组出现零动作行 ⇒ `--summarize` 报错并以非零码退出**（本项的 close_when）；
2. `smoke` 组仍放行（那张表按约定就是诊断表）；
3. 记录写在 `policy.kind` 字段出现之前 ⇒ 记 `identity uncertified`，**不拒**（否则历史表全变不可读）；
4. 反证要能**在没有零动作混行时**证明闸门不是恒红。

## 结果

落法选 (b)（汇总侧拒绝），不动记录格式面：`kind` 从每行自己的 `record.json` 读，与既有的条件面检查同一处。

**真树观测**（`python ablation_harness\run_ablation.py --summarize --protocol <P>`）：

| 协议 | 表 | 观测 | 退出码 |
|---|---|---|---|
| `locomotion_eval_v4` | 根表（非 smoke） | 点名 `Lizard-Rough-v14_v4unlock_nominal_seed123`，`policy.kind='zero_action'` | **1** |
| `locomotion_eval_v2` | `dev` 组（非 smoke） | 点名 `..._devnolock_...`，`policy.kind='zero_action'`；另有 3 条既有的条件冲突/无记录 | **3** |
| `locomotion_eval_v3` | `smoke` 组 | 无身份拒绝 | 0 |

**顺带读出的事实**：`locomotion_eval_v4` **目前没有任何真分数行**——它根表里唯一那行是零动作诊断行，
读数（`success_rate 0.285` / `lin_mae 0.8329` / `energy_per_m_j 3980.2253`）与 v3 smoke 表逐项同值，
即"v4 上的性能"这句话现在没有数据支撑。本记录不改那行：闸门只拒绝它被当成分数表读。

**反证**（`rl_exp/tools/verify/test_eval_record.py::test_a_diagnostic_row_cannot_sit_in_a_scores_table`）：
临时目录四例——非 smoke 表的 `zero_action` 行被拒且带 kind；同一条行放进 `smoke` 组放行；
`checkpoint` 行放行；无 `policy.kind` 的行报 `uncertified` 而非拒绝。该文件 `28 passed`。
配套：`HARNESS.md` 记录格式节新增 ④、跨协议规则那节的"不在条件面内"改成事实、版本节的敞口补记这笔未编号改动。

**旧表路径**：`locomotion_eval_v1` 的表仍是红，但红在**既有的** `no_record`（那些行没有 `record.json`），
不是被本闸门拒的——两件事在输出里分开写。

## 证据引用

- 代码：`ablation_harness/run_ablation.py`（`_identity_report`、`_SMOKE_GROUP`、`_summarize`）
- 反证：`rl_exp/tools/verify/test_eval_record.py`（`test_a_diagnostic_row_cannot_sit_in_a_scores_table`）
- 规则：`ablation_harness/HARNESS.md` 记录格式节 ④、跨协议规则节、版本节
- 复读命令：`python ablation_harness\run_ablation.py --summarize --protocol locomotion_eval_v4`
  （退出码用 `cmd /v:on /c "... & echo !errorlevel!"` 读；`cmd /c` 的 `%errorlevel%` 是**运行前**展开的，
  会报出恒 0 的假读数——本次踩过）

## 未覆盖边界

- 规则只对**非 smoke 组**生效：`smoke` 组里若混进 `checkpoint` 行**不拒**（反方向没有闸门），
  该方向仍靠纪律。
- 图表/HTML 不经过 `--summarize`：`plot_eval.py` 与报告仍可把两类行画在一起。
- 不搬迁历史数据：`v4` 根表那行留在原地，闸门只改变它能否被当成分数表读。
- 缺 `policy.kind` 的行只是 `uncertified`：它们仍可进表，语义上等同"未认证"，不等于"已核"。
- 本轮语料里没有"有 record 但缺 kind"的真样本（v1 那些行是根本没有 record）⇒ 该分支只有合成反证。
