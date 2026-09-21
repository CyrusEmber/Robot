---
id: record-format-live-checks
title: 记录格式的剩余真跑段（HARNESS 挂账 #2 的未做半）
scope: ablation_harness
status: open
landing: ablation_harness/record.py, ablation_harness/eval.py
next: 三件真跑核对：① 写侧 `substitutions` 与 `runtime.rsl_rl_id` —— 按训练记录的 `mode` 重建同一身份再比（`rsl_rl_id` 是 `source:<rev>`/`installed:<ver>`，训练侧存的是裸 rev ⇒ 不能直接相等），顺带核变体 run 的取值与 `unknown` + pre-format reason；② `num_envs` 声明值与实际值不同的格子；③ 资产 **fail** 路径真跑 —— **待决**：造 fail 要改冻结资产（越界），授权方式定了才做
close_when: 执行者跑 ①② 并观察记录内容：① 同一 run 身份重建后两处取值一致 ⇒ 记"已核到行为"，不一致则记差异并指出是哪一侧的字段口径；② 声明与实际分列且不相等时两列都出现 ⇒ 成立，若某侧缺失则报记录不完整；③ 授权确定后同法核对。三件都写出观测结果即关；③ 若授权仍无结论，把它拆出去单列，本项只关 ①②
---

## 当前状态

已完成（真跑 + 逐位对照）：同 seed 无记录重复的 A/A 臂、一次真实 run 落全六类、P04 四项替换与
拒绝路径各一次；证据在 `rl_exp/versions/lizard/ACCEPTANCE.md` §3.2。**未做**见 `next`。

## 待决项（不自行决定）

资产 fail 路径需要一条"能 fail 的资产"：动冻结资产越界。**授权方式**（临时副本 / 冻结资产的一次性例外 /
改用合成摘要）由人定；在定之前本项的 ③ 不做，也不许把 ①② 的通过读成"记录格式已全部真跑"。

## 未覆盖边界

本项不含协议版本切换的对照（见 `runtime-acceptance-v3`），也不改 `record.py` 的规则
（记录格式的读侧/写侧语义归 `record.py` 与 `test_eval_record.py`）。
