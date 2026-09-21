---
id: ledger-inbound-reference-scan
title: 台账入站引用扫描：区分现行指针与历史引用
scope: rl_exp/tools/verify/check_work_docs.py
status: done
landing: rl_exp/tools/verify/check_work_docs.py
outcome: 折进既有闸门（**1 个文件、0 棘轮**，`hooks/pre-commit` 已调它）：`check_work_docs.py` 新增 `_inbound_hints()`，在 `--check` 里扫文档中的 `work/active/<id>.md` / `work/closed/<年>/<id>.md` 散文引用，分 **moved**（id 现在在另一侧，报出解析后的真实路径）与 **dangling**（盘上没有这个 id）两种判定，以 `HINT` 打印、**不改退出码**。三条边界是设计的一部分而非疏漏：① 只读 `*.md`——代码里路径是数据（迁移工具的替换规则）或夹具（闸门自检字面量），"这指针解析得到吗"在那里无意义，自检用一条 `.py` 反例钉住该范围；② `rl_exp/versions/**`（A0 冻结记录）不读，它们按原样保留当时那棵树；③ 不硬拒——现行指针该改、历史痕迹该留，文本判不出，闸门硬拒要么逼人改写历史、要么把真断链判成合法。实测：自检 +3 反例（moved / dangling / 代码不读）全绿；真仓 `--check` 0 误报；端到端探针（临时文档写 moved 与 dangling 各一条）两条都报对且退出码仍 0。id 式（`depends_on` / `superseded_by`）已由 front-matter 闸覆盖（含"依赖已关闭事项"判红），未重复实现。本项自身的 move（`version-doc-single-owner`、`run-record-reachability`、`ledger-inbound-reference-scan` 三处关闭）就是第一批用它复扫的用例：0 断链
evidence: acceptance/records/2026-09-21-version-doc-read-cost.md
---

## 当前状态

已收，工具在闸门里常驻。

## 未覆盖边界

- 只判"路径是否存在 / id 是否在盘上"，**不判**语义正确性（指向了错的事项不在此列）。
- 虚构 id 的**示例**写法会报 `dangling`：今天真仓 0 命中，将来若某文档要举例子，改写法或加白名单，
  这是已知天花板（先列出、不判定，已按提示级实现）。
- `acceptance/records/**` 不在冻结范围内 ⇒ 记录里的旧指针会报 HINT；现行做法是关闭事项时把记录的
  指针一并改指（今天三次都如此），闸门不替人决定该改还是该留。
