---
id: ledger-inbound-reference-scan
title: 台账入站引用扫描：区分现行指针与历史引用
scope: rl_exp/tools/verify/check_work_docs.py
status: open
landing: rl_exp/tools/verify/check_work_docs.py
next: 在 `--check` 里加两条**提示级**读数（不硬拒）：① 路径式——`**/*.md|py|rst` 里 `work/active/<id>.md`、`work/closed/<year>/<id>.md` 是否存在；② id 式——`depends_on`/`superseded_by` 的裸 id 能否唯一解析。先拿反例定误报：事项移入 closed 后的旧路径、重复 id、合法锚点（`#anchor`）、示例路径（如 `resolve_work_doc.py` 文档里的例子）、固定 commit 下的历史路径
close_when: 用上述五类反例各造一次，观察两类读数：正确断链报出、历史/示例/带锚点引用不报 ⇒ 成立；若历史引用无法与现行指针自动区分（只能靠改写历史才能过闸），把它们降为**列出不判定**并记下这个天花板，本项同样可关
---

## 当前状态

未开工。2026-09-21 实测两次全仓扫描**均为 0 命中**（路径式 0 断链、id 式 0 悬空），
故这是防御性闭环，不是修既有缺陷；读数与口径见 `acceptance/records/2026-09-21-version-docs-drift-audit.md`。

## 未覆盖边界

只判"存在 / 能否唯一解析"，**不**判语义正确性（链接指向了错的事项不在此列）。
不含冻结记录改写：历史引用若必须改写才合法，按 `version-doc-single-owner` 的边界豁免，不改写。
