---
id: stale-doc-pointers-in-code
title: 代码与配置里的旧目标指针：硬错 5 处 + 旧编号引用约 90 处
scope: rl_exp/tasks, rl_exp/tools/verify, ablation_harness, hooks
status: open
landing: rl_exp/tasks/components.py, rl_exp/tasks/lizard_env_cfg.py, rl_exp/tools/verify/teacher_smoke.py, rl_exp/tools/verify/check_pxr_leak.py, rl_exp/tools/verify/check_split_probe_wait.py, ablation_harness/eval.py, ablation_harness/record.py, rl_exp/tools/runrecord/rebuild.py, ablation_harness/protocols/locomotion_eval_v3.yaml, hooks/pre-commit
next: 分两批，只改注释/文档字符串，不动行为。**批 A（硬错，先做）**：① `tasks/components.py`、`tasks/lizard_env_cfg.py`、`tools/verify/teacher_smoke.py` 里"FAMILY 的 obs 布局表"改指 `rl_exp/versions/lizard/OBS.md`（那张表已归 OBS.md）；② `check_pxr_leak.py`、`check_split_probe_wait.py` 的 docstring 里裸 `docs/pitfalls.md` 补成 `rl_exp/docs/pitfalls.md`。**批 B（旧编号，可解析但多一跳）**：全仓 `PLAN.md #N` / `挂账 #N` 引用约 90 处在代码注释、`protocols/*.yaml`、`hooks/pre-commit`、`fork_patches/*.patch` 里；目标编号在新 `PLAN.md` 里已不是主表（表已清空）⇒ 改成直接指事项或机制（如 `#18` → `work/active/verified-rebuild-rating.md`）。**版本目录里的历史记录（`main/vN/PLAN.md`、`NOTES.md`）不改写**（证据），它们靠 PLAN 留下的"原行 → 新事项"映射解析
close_when: 批 A = 五处检索不到旧目标（"FAMILY"不再充当 obs 布局出处、无裸 `docs/pitfalls.md`）；批 B = 按 `grep -rn "PLAN\.md #"` 计数归零（版本目录历史记录除外，计数时排除 `rl_exp/versions/lizard/main/v*/`、`.../NOTES.md`）。两批各自完成即关；批 B 未完而 A 完，保持 open 并在正文写明剩余计数
---

## 问题与本次范围

文档搬家把内容搬走了，**指向它的指针留在代码与配置里**。分两类，代价不同：
批 A 是**硬错**（照着找会落空）；批 B 是**多一跳**（编号仍能通过 `PLAN.md` 的"原行 → 新事项"
映射表解析，但读者要跳两次，且新 PLAN 的表已不是主表，编号不再有本地含义）。

## 计数方法（可复跑）

```
grep -rn "PLAN\.md #" --include=*.py --include=*.yaml --include=*.md .
grep -rn "挂账 #[0-9]" .
```
2026-09-21 实测：125 处命中里约 90 处在代码/配置注释，其余在文档与版本目录历史记录。

## 未覆盖边界

不改任何行为、不重排导入、不动 `rl_exp/docs/pitfalls.md` 本身（那是 `historical-facts-homing` 的目标文件）。
若某处指针指向的内容**确实已不存在**（而非搬家），保留原文并在本项记下，不自行判断该删该留。
批 B 若发现在代码里逐处改会牵动闸门或 golden，就地停下、把该文件记入本项由人决定，不为凑计数而改。
