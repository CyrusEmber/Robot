---
id: archive-location-decision
title: 地形证据归档位置与 rebuild.py 角色（规格裁决，HARNESS 挂账 #4）
scope: ablation_harness, rl_exp/versions/lizard
status: done
landing: rl_exp/tools/runrecord/rebuild.py, rl_exp/tools/verify/test_terrain_geometry.py, acceptance/records/2026-09-22-terrain-evidence-archive-and-verification.md
outcome: 两条规格均已裁决（2026-09-22）：① 地形证据只住运行目录 `terrain/geometry.json`，不再复制进 `rl_exp/archive/`；② `rebuild.py` 只判材料完整性，地形几何一致由离线再生闸判，"已验证重建"评级另归 `verified-rebuild-rating`。裁决依据有二：位置不是措辞而是接线（`rebuild.py` 已按此取材），且 archive 的定义是"rev 取不回的内容"；原状理由里"可再生 ⇒ 取回得来"被用户改正为不成立 —— 代码与版本会变，原始几何记录及其版本身份必须保留，缺证据的历史 run 继续判 `unknown`。缺件静默作为已声明边界接受，未新立动作。原关闭条件的观测句作废：它从未以该措辞存在，且指向的两处正文已迁走。
evidence: acceptance/records/2026-09-22-terrain-evidence-archive-and-verification
---

## 问题与本次范围

地形证据放哪（原文 `rl_exp/archive/<run_id>/terrain/` vs 现状运行目录）与谁核什么（原文 `rebuild.py`
核"地形产物一致" vs 现状材料完整性）—— 两处**规格偏离**，实现早已按现状生效，卡的是"这算不算照原文
交付"的认可。用户 2026-09-22 对两条各给出裁决，并改正了原状理由里的一条脆弱处。

## 落点（这条为什么算已关闭）

- 裁决、依据与理由改正：`acceptance/records/2026-09-22-terrain-evidence-archive-and-verification.md`
  （本项不复述）。
- 裁决的载体是现行实现，不是散文：`rl_exp/tools/runrecord/rebuild.py` 按运行目录取材；
  `rl_exp/tools/verify/test_terrain_geometry.py` 的再生例按归档自述重建后逐格比。
- 入站指针已更新：`ablation_harness/HARNESS.md` 挂账表、harness 迁移记录的去处表、
  `work/active/verified-rebuild-rating.md`、地形产物记录的两条边界。

## 未覆盖边界

缺件静默（运行目录无地形件时不拒采也不报问题）按裁决保留，属**已声明边界**：要改成可见的 `unknown`
须另立事项，归 `verified-rebuild-rating`。"这份地面今天还跑得动"不在本项 —— 几何摘要一致 ≠ 行为一致。
