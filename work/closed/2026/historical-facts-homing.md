---
id: historical-facts-homing
title: 三段只在旧版本史里写过的历史事实没有家（批 1 遗留）
scope: rl_exp/versions/lizard/main/v1, rl_exp/docs
status: done
landing: rl_exp/versions/lizard/main/v1/NOTES.md, rl_exp/docs/pitfalls.md
outcome: 三条各自落进现存文件并写成「事实 + 为什么」：① v1 训练总时 25.735 h / `it=11438` 单次停顿 7.2 h → `versions/lizard/main/v1/NOTES.md`「时间预算」节（含「按纯算力估会低估约 30%」的用法）；② 「记录链源头在机器本地会被清理 ⇒ 记录必须入库」→ `rl_exp/docs/pitfalls.md` P007；③ 「别把调用路径的父目录当配置」→ 同文件 P008（两条都按该文件的五节形状写）。迁移记录里的原文段落已改为指针，不再持有正文。
close_when: 三条各自落进上列现存文件并写成"事实 + 为什么"（可被 `grep` 到），观测 = 三处均命中且迁移记录对应段落改为指针；缺任一条则保持 open
---

## 问题与本次范围

批 1 删掉 `HARNESS.md` 的版本史时，这三条**只在那里写过**的事实失去了唯一副本；当时原样保存在
迁移记录里、没有替它们挑去处。本项就是那个"挑去处并搬"的动作。

## 未覆盖边界

不重写这三条的事实内容（迁移记录里保存的就是原文），也不借机扩写版本史；`HARNESS.md` 仍不收版本史。
