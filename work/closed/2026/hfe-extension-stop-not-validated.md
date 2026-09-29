---
id: hfe-extension-stop-not-validated
title: 膝限位（hfe）越过伸直 13.61°：取值与是否重训待定
scope: rl_exp/versions/lizard2, rl_exp/blender, rl_exp/tools/diagnose, rl_exp/tools/verify, acceptance/records
status: superseded
landing: rl_exp/blender/generate_urdf.py, rl_exp/versions/lizard2/lizard2.urdf, rl_exp/assets/lizard2/lizard2.usda
close_when: (a) 伸展端（以及是否含屈曲端/kfe）的取值被选定且落点可查（生成器 + URDF/USD + 锁）；(b) 若动物理：历史 run 的可复现性影响与"重训 or 只重评"写明；(c) 未取值的那一端显式收口（判掉，或写成口径前提）。
outcome: 并入 `joint-limit-shape-and-range-pass`（2026-09-29）：范围从"膝伸展端一处"扩到全关节，理由是**同源无推导 + 约束形状不对**（髋之后 `haa`/`hfe`/`kfe` 同轴 ⇒ 平面链，逐关节盒表达不了物理止挡）。三档代价、取值与重训取舍随内容移交，本项未作独立决策。
superseded_by: joint-limit-shape-and-range-pass
evidence: acceptance/records/2026-09-29-lizard2-hfe-knee-limit, acceptance/records/2026-09-29-lizard2-pad-leveling-unreachable, acceptance/records/2026-09-29-lizard2-pad-tilt-is-the-fold-sum
depends_on: asset-tree-per-family
---

## 问题与本次范围

`*_hfe` 的限位 ±1.20 rad **没有任何膝的几何依据**：量得的共线角是 ±55.15°（右腿正、左腿负），
±1.20 rad = ±68.75° ⇒ **每腿的行程里 13.61° 是反折**。来源是 `generate_urdf.py` 的 `AXIS_MAP` 里
`hfe` 从 `("0 0 1", -1.2, 1.2, …)` 换成 `("-1 0 0", -1.2, 1.2, …)`（`:50`）——**轴换了、角沿用**，
而 1.2 是旧 Z 轴时代的默认（同一字典里小关节 0.6、kfe 1.6）。USD 侧同样是 ±68.75494（PhysX 硬限位）。

本项只收**取值怎么定、以及定值后资产换代怎么走**；几何与行为读数归上面两条记录，不复述数字。

## 与邻近事项的边界

- `stride-axis-range-vs-speed`：问髋（±0.6 被顶满，属"行程不够"），本项问膝（越过伸直，属"限位画错"）。
  两者都是资产换代 ⇒ **若同期定值应当一起换代**（一次换代 = 一次锁/快照刷新）。
- `pad-flat-requirement-and-ankle-axis`：问踝（立边）与整腿可达性。**本项的读数更正了它 ⑤ 里的 hfe 行**
  （它的判定未受影响），踝自己的限位问题仍归它。
- `leg-chain-symmetry-convention`：逐腿镜像的生成器约束；本项要"逐腿非对称"正好落在它管的地界上，
  定值时不要各写一套（生成器只应当有一处腿侧判据）。
