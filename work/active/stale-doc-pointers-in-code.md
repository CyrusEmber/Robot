---
id: stale-doc-pointers-in-code
title: 代码注释与 docstring 里指向已迁走内容的旧指针（五处）
scope: rl_exp/tasks, rl_exp/tools/verify
status: open
landing: rl_exp/tasks/components.py, rl_exp/tasks/lizard_env_cfg.py, rl_exp/tools/verify/teacher_smoke.py, rl_exp/tools/verify/check_pxr_leak.py, rl_exp/tools/verify/check_split_probe_wait.py
next: 五处只改注释/文档字符串，不动行为：① `tasks/components.py`、`tasks/lizard_env_cfg.py`、`tools/verify/teacher_smoke.py` 里"FAMILY 的 obs 布局表"改指 `rl_exp/versions/lizard/OBS.md`（那张表已归 OBS.md）；② `tools/verify/check_pxr_leak.py`、`tools/verify/check_split_probe_wait.py` 的 docstring 里 `docs/pitfalls.md` 补成 `rl_exp/docs/pitfalls.md`
close_when: 执行者改完并在五处检索旧目标 —— 观测 = 这三处再也搜不到"FAMILY"充当 obs 布局出处、这两处搜不到裸 `docs/pitfalls.md`，且离线套件仍 47/47（纯注释改动不应改变任何闸门结果）
---

## 问题与本次范围

文档侧搬家把内容搬走了，但**代码里指向它的指针还留在原处**：读代码的人照着找会落空。
属代码文件，未混进文档批次。

## 未覆盖边界

不改任何行为、不重排导入、不动 `rl_exp/docs/pitfalls.md` 本身（那是 `historical-facts-homing` 的目标文件）。
如果某处指针指向的内容**确实已不存在**（而非搬家），保留原文并在本项记下，不自行判断该删该留。
