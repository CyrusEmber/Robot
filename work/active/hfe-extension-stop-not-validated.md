---
id: hfe-extension-stop-not-validated
title: 膝限位（hfe）越过伸直 13.61°：取值与是否重训待定
scope: rl_exp/versions/lizard2, rl_exp/blender, rl_exp/tools/diagnose, rl_exp/tools/verify, acceptance/records
status: blocked
landing: rl_exp/blender/generate_urdf.py, rl_exp/tools/diagnose/leg_axis_geometry.py, rl_exp/versions/lizard2/lizard2.urdf, rl_exp/assets/lizard2/lizard2.usda
next: ① **先定伸展端取值**（三档代价已量：0.9625 / 0.90 / 0.79 rad，见 evidence）——但**任一取值都会改已训 v2 的行为**（最小改动也压掉 lf@2.8 的 10.31% 帧），所以取值必须与"是否重训/是否只重评"一起定；② 若定值：生成器改成**逐腿镜像非对称**（现 `joint_spec` 按后缀查一条 spec、四腿共用，`:227-231`）+ 真跑 + `convert_urdf.py --headless --robot lizard2` + **同 commit `--update-locks`** + 历史 run 可复现性写明；③ 屈曲端与 `*_kfe`（±1.6 rad = 折叠 75.5° 过伸直）**网格上没有止挡证据、同批未判**——是"只堵反折"还是"两端都按设计收"，由 owner 定；④ 潜在护栏：把"膝限位不得越过共线"做成离线断言（`leg_axis_geometry.py` 已有 `straight_hfe`/`included_angle`，扩展即可），避免下次换轴再沿用旧数值。
close_when: (a) 伸展端（以及是否含屈曲端/kfe）的取值被选定且落点可查（生成器 + URDF/USD + 锁）；(b) 若动物理：历史 run 的可复现性影响与"重训 or 只重评"写明；(c) 未取值的那一端显式收口（判掉，或写成口径前提）。
evidence: acceptance/records/2026-09-29-lizard2-hfe-knee-limit, acceptance/records/2026-09-29-lizard2-pad-leveling-unreachable
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
