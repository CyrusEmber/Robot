---
id: family-filemap-identity-overlap
title: FAMILY 版本史行与 FILEMAP 版本目录行都带版本身份（重叠约 70%）
scope: rl_exp/versions/lizard, .
status: done
landing: rl_exp/versions/lizard/FAMILY.md, FILEMAP.md
outcome: 取候选 b —— 身份只归 FAMILY 版本史（摘要 + 教训 + 指向 NOTES），FILEMAP 的版本行统一缩成「路径 + 冻结配方/支线版本包 + 指向 FAMILY」，两处写明这个分工。闸门零改动（两条版本行都是硬要求，改的是行的内容不是行本身）；身份与教训并未丢失：同一份文字本来就在 FAMILY。
close_when: 三条候选之一被选定并落地：观测 = 同一版本的"它是什么"只在一处成文，另一处只剩指针或（候选 c）两处各写明用途；改后 `python rl_exp/tools/verify/check_version_docs.py` 仍 `VERSION_DOCS_OK`
---

## 问题与本次范围

批 1/批 2 都各压了这两份文档的正文，但**版本身份仍写了两遍**：`FILEMAP.md` 的版本目录行写身份，
`FAMILY.md` 的版本史行也写摘要。这是"事实不重复"唯一明确剩下的违例点。

## 未覆盖边界

本项只处理**版本身份**这一种重复；不重写版本史、不动家族线结构、不改闸门口径以外的代码。
若选定候选 a/b 需要动闸门，闸门改动必须同批完成并保留反证（`--self-test`）。
