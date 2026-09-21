---
id: family-filemap-identity-overlap
title: FAMILY 版本史行与 FILEMAP 版本目录行都带版本身份（重叠约 70%）
scope: rl_exp/versions/lizard, .
status: open
landing: rl_exp/versions/lizard/FAMILY.md, FILEMAP.md
next: 定一个收敛方向并落成机制：候选 a) 身份只在 `FILEMAP.md` 的版本目录行，`FAMILY.md` 的版本史只留日期 + 教训（删掉重复的"这版是什么"摘要）；候选 b) 反过来，身份只在 `FAMILY.md`，`FILEMAP` 的版本行缩成路径 + 一行指向；候选 c) 明确保留两处并写明各自用途。**注意**：`FILEMAP.md` 的版本目录行是 `check_version_docs.py` 的硬要求（`:242` 以版本目录为 key），`FAMILY.md` 的 `| vNN |` 版本史行也是（`:238`）—— 两条都删不掉，所以候选 a/b 都要先改闸门或改行的形态，不能只删文字
close_when: 三条候选之一被选定并落地：观测 = 同一版本的"它是什么"只在一处成文，另一处只剩指针或（候选 c）两处各写明用途；改后 `python rl_exp/tools/verify/check_version_docs.py` 仍 `VERSION_DOCS_OK`
---

## 问题与本次范围

批 1/批 2 都各压了这两份文档的正文，但**版本身份仍写了两遍**：`FILEMAP.md` 的版本目录行写身份，
`FAMILY.md` 的版本史行也写摘要。这是"事实不重复"唯一明确剩下的违例点。

## 未覆盖边界

本项只处理**版本身份**这一种重复；不重写版本史、不动家族线结构、不改闸门口径以外的代码。
若选定候选 a/b 需要动闸门，闸门改动必须同批完成并保留反证（`--self-test`）。
