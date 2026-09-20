---
id: archive-location-decision
title: 地形证据归档位置与 rebuild.py 角色（HARNESS 挂账 #4，待用户拍板）
scope: ablation_harness, rl_exp/versions/lizard
status: blocked
landing: rl_exp/versions/lizard/PLAN.md, rl_exp/versions/lizard/ACCEPTANCE.md
next: 两条请用户裁决，任一条都需要明确回答：① **归档位置** —— 地形证据落运行目录 `terrain/geometry.json`，还是按 `PLAN.md` #18 原文落 `rl_exp/archive/<run_id>/terrain/`？（现状：落运行目录；理由是该证据由 suite+seed 可再生、随记录入库即"取回得来"，再抄一份是重复；`rl_exp/archive/` 留给"rev 取不回的内容"）② **`rebuild.py` 的角色** —— 现由 `rebuild.py` 核材料完整性、"地形产物一致"由再生判定（离线可跑）；原文写"由 `rebuild.py` 核验"
close_when: 用户对两条各给出裁决（接受现状 / 改回原文 之一），执行者把裁决写进 `PLAN.md` #18 与 `ACCEPTANCE.md` 的边界节，并把两处措辞改成与裁决一致；观测 = 这两处不再出现"未获确认前不得当成照原文交付"这句话
---

## 为什么它是 blocked 而不是 open

两条都**已按现状实施并生效**，只是与原文措辞不一致：卡的不是实现，是"这算不算照原文交付"的认可。
在裁决之前，任何引用这两处的人都会踩到同一句免责话，所以它必须挡在"可关闭"之外。

## 未覆盖边界

本项不改 `terrain_geometry.py` 的行为，也不动 `rebuild.py` 的材料完整性口径；重建评级 = `PLAN.md` #18 ①
仍单独排期。
