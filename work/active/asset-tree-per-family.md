---
id: asset-tree-per-family
title: 每家族一份网格树：生成器真跑与旧家族冻结分歧的处置
scope: rl_exp/versions, rl_exp/tools/verify, rl_exp/blender, ablation_harness
status: open
landing: rl_exp/versions/lizard2/assets.json, rl_exp/tools/verify/check_dr_parity.py, rl_exp/blender/generate_urdf.py
next: ① **生成器真跑一次**：本机无 Blender，目前只有"引用必须落在声明树内"这半边被闸门看守；真跑要确认重新生成落到声明树、URDF 引用可解析、usda 内联点与之一致（三份拷贝同几何）。② **处置旧家族 `lizard` 的冻结分歧**：它的 URDF 引用 `versions/lizard/meshes/**`，而它声明并消费共享树 `meshes/`；两条出路是"在那条线开新版本时一并换树"或"带理由的长期豁免并写明期限"，不能继续只是打印。③ 若将来要修旧家族的 `rl` 脚平板 hull，按同一流程再走一次换代（其历史 run 的可复现性随之作废）。
close_when: (a) 生成器在真机上跑过一次，产出落在声明树、三份拷贝互证、闸门全绿；(b) 旧家族的分歧有一条明确处置（换树，或写明理由与期限的豁免），且该处置引用一次真跑或一次闸门读数。
depends_on: teacher-snapshot-asset-sync
evidence: acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation
---

## 问题与本次范围

把"网格树"从共享一份改成**每家族按 `versions/<family>/assets.json` 声明**：共享树被两个家族的所有
锁钉住，于是修一个家族的脚掌几何等于改写另一个家族的冻结资产。已落地的部分（声明文件、
`diag_metrics.meshes_dir(family)` 与 `obs_protocol.family_of(task)`、五处调用点、
`check_dr_parity` 的资产隔离一节与 `_lock_files`、生成器改读声明并同时写 .obj、lizard2 的 `rl` 脚
hull 换代为 `rr` 的镜像）见记录，本项不复述。

本项只收**这次改造的尾**：生成器没有真跑过；旧家族的 URDF/消费树分歧被打印但不被处置；"两个家族
各改几何"的流程已写进记录，但从未演练第二次。

## 与邻近事项的边界

- `teacher-snapshot-asset-sync`：资产换代后 teacher 快照里派生的字面量仍人工同步。本项不接管那一步，
  只把它列为依赖——几何换代"完成"不等于快照侧"同步完成"。
- `lizard2-family-landing`：v2 的配方决策归它；本项只提供"接触几何已变、v1 属已训配方变更"这个前提。
- 资产隔离的**规则**归机制（声明文件 + 闸门），不归本项；本项只写当前状态与剩余动作。
