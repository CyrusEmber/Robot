---
id: historical-facts-homing
title: 三段只在旧版本史里写过的历史事实没有家（批 1 遗留）
scope: rl_exp/versions/lizard/main/v1, rl_exp/docs
status: open
landing: rl_exp/versions/lizard/main/v1/NOTES.md, rl_exp/docs/pitfalls.md
next: 逐条定去处并搬（原文在 `acceptance/records/2026-09-20-harness-migration.md` 的"走查发现的缺口"一节）：① v1 训练总时 25.735 h 与 `it=11438` 单次停顿 7.2 h —— 做消融的时间预算依据 ⇒ 进 `v1/NOTES.md` 的时间/成本节；② "记录链的源头（tfevents）在机器本地会被清理 ⇒ 记录必须入库" —— v1.5.2 的理由 ⇒ 进 `rl_exp/docs/pitfalls.md` 新编号条目；③ "别把调用路径的父目录当配置" —— v1.5.1 的 provenance 串位教训 ⇒ 同上新条目
close_when: 三条各自落进上列现存文件并写成"事实 + 为什么"（可被 `grep` 到），观测 = 三处均命中且迁移记录对应段落改为指针；缺任一条则保持 open
---

## 问题与本次范围

批 1 删掉 `HARNESS.md` 的版本史时，这三条**只在那里写过**的事实失去了唯一副本；当时原样保存在
迁移记录里、没有替它们挑去处。本项就是那个"挑去处并搬"的动作。

## 未覆盖边界

不重写这三条的事实内容（迁移记录里保存的就是原文），也不借机扩写版本史；`HARNESS.md` 仍不收版本史。
