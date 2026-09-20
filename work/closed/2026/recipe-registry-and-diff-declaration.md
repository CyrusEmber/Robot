---
id: recipe-registry-and-diff-declaration
title: 版本类体退役 + 差异声明 B 谱系（PLAN 挂账 #22/#24，已结案）
scope: rl_exp/tasks, rl_exp/versions/lizard
status: done
landing: rl_exp/tasks/recipe.py, rl_exp/tasks/recipe_tasks.py, rl_exp/versions/recipes.json
outcome: ① 注册表改指 `recipe_tasks` 生成类后，版本子类运行期无人引用 ⇒ 删除；golden 的 `env_cfg_class` 列**定点搬一行**到 `recipe_tasks:<同名>`（不改配方键，否则迁移面扩大一轮）；`[41]` 的"表 == 类"比较反向成"重复路径复活"探针。② 差异声明口径取 **B 谱系**且不由声明选：有母版 ⇒ 对 `build(母版)`，root ⇒ 对 stock；现存 12 份 `diff.json`，`main/v1` 刻意无声明（母版无配方声明 ⇒ 谱系读数不可得，闸门打印而不是静默跳过）；`EXPECTED_DIFFS` 逐条钉数；agent 侧（PPO）纳入硬 B。
evidence: rl_exp/versions/lizard/ACCEPTANCE.md
---

## 问题与本次范围

两条都是"声明式重构"的收尾：**一个配方只剩一个表达式**（版本类体与生成类并存的窗口关掉），
以及**声明与母版差异的比对口径**（硬 A 证"没漂"，硬 B 证"被声明"，互不可替）。

## 未覆盖边界

组件归属是**名字级**的（一条路径被两个组件各拥有一个名字时，点名任一个都过）——这是硬 B 最软处，
已写在 `ACCEPTANCE.md` 的边界节；`--vs-upstream` 的归因列在翻表当天已退化，替代来源是各配方的 `diff.json`。
