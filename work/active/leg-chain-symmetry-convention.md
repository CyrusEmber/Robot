---
id: leg-chain-symmetry-convention
title: 腿链镜像：源资产意图待定，生成器与闸门都没有数值级对称约束
scope: rl_exp/blender, rl_exp/versions/lizard2, rl_exp/tools/verify, acceptance/records
status: blocked
landing: rl_exp/blender/generate_urdf.py, rl_exp/blender/fix_bones.py, rl_exp/tools/verify/check_dr_parity.py
next: ① **定判据（卡在仓外输入）**：腿链关节点等于"网格摆在哪"（`fix_bones.py` 用网格对象的世界平移写 bone head），所以"该不该对称"问的是**源资产的意图**——由所有者 + 美术/CAD 回答"四腿是否应严格左右镜像"。② 应答后二选一：**(a) 应严格对称** ⇒ 在网格源头修（`lizard_stance.blend` 的摆件，需 Blender 机）→ 重新生成 → 走一次资产换代（lizard2 各版本 `asset_lock` 整体漂移；`lizard` 旧家族的 19 个冻结锁按 `assets.json` 声明不动），并在生成器加**数值级**镜像断言（容差按记录实测的量级取，不是 1e-6）。**(b) 不视为缺陷** ⇒ 把"左右腿不可互为对照"写成口径前提并指明它的家（读数口径文档 / 协议），同时清掉任何按左右腿做对照的做法。③ 断言上线前先解决旧家族必红：同一份链在 `lizard` 上同样不对称且被 19 个冻结锁压住 ⇒ 断言只能对新家族生效或带显式豁免，豁免写清路径与理由。
close_when: (a) "源资产是否应严格左右镜像"有一个明确答复（谁答的、依据是什么）；(b) 该答复兑现成一件可查产物——生成器里的数值级断言 + 一次资产换代，**或**一条写进口径文档的前提（含"左右不可对照"的落点）；(c) 若走断言路线，旧家族不会因此变红（豁免或按家族启用，有一条闸门读数作证）。
depends_on: asset-tree-per-family
evidence: acceptance/records/2026-09-23-lizard2-leg-chains-not-mirrored, acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation
---

## 问题与本次范围

腿链的关节原点（`*_hip` / `*_hfe` / `*_kfe` / `*_foot` 的 origin）逐腿比对后**不是镜像**：前腿对在
hip 上偏几毫米，后腿对偏到厘米量级以内（逐格读数归 `2026-09-23-lizard2-leg-chains-not-mirrored`，
本项不复述）。同时 `rl` 的**脚碰撞网格**已按 `rr` 镜像修好（归
`2026-09-28-lizard2-foot-hull-and-asset-isolation`）—— 网格与关节原点是两笔账不等于修后者。

本项只收**判据与约束的缺口**，不收几何本身：

- **上游没有镜像约束**：几何真源是 `.blend` 里 ARMATURE 的 bone head，腿骨 head 又由 `fix_bones.py`
  从**网格对象的世界平移**覆写 ⇒ 关节原点等于"网格摆在哪"。生成器（`generate_urdf.py`）只做父子 head
  相减的转录，不做校验。
- **管线里唯一的对称检查是符号级**：命名/朝向脚本断言的是"左腿在 +y、右腿在 −y"，不碰数值。所以
  mm–cm 级偏差在闸门眼里一直合法。
- **因此现状是"无人要求"，不是"决定不做"**：它没被证明与任何训练读数相关（记录只敢说"推翻左右腿
  互为对照"这个默认假设），也没进过任何版本的挂账。

## 与邻近事项的边界

- `asset-tree-per-family`：管网格树的归属与生成器**真跑**（本机无 Blender）。本项不接管真跑，只把它
  当依赖——"生成器能跑通"是"改网格后重新生成"的前置。
- 资产换代的前置是**依赖它的训练/评测已收尾**：v2 两臂的当前状态归 `lizard2-v2-foot-authority`，
  本项只声明"改链原点 = 换代 = 那批 run 的可复现性随之作废"。
- 断言若只按新家族启用，"家族声明"这一机制归 `assets.json` + `check_dr_parity`；本项不重写该机制，
  只要求它承载一条对称判据并留下读数。
