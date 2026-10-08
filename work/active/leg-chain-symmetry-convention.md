---
id: leg-chain-symmetry-convention
title: Blender：对称骨架、骨段长度与默认姿态候选
scope: rl_exp/blender, acceptance/records
status: open
landing: acceptance/records/2026-10-08-lizard2-blender-body-candidate.md#操作步骤
next: 本对话用户按 landing 在 Blender 另存并调整候选，完成后回填该记录的结果；Codex 核对交付物并把未完导出、镜像断言、限位与运行时验证交回 joint-limit-shape-and-range-pass
close_when: 用户检查候选文件与预览，Codex 核对结果和后续落点；接受且未完接入已交 joint-limit-shape-and-range-pass 则关闭，拒绝并说明原因亦关闭，仍需修改或镜像/接地未核验则继续在办
evidence: acceptance/records/2026-10-08-lizard2-blender-body-candidate, acceptance/records/2026-09-23-lizard2-leg-chains-not-mirrored, acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation
---

执行者为本对话用户，Codex 负责交付说明与后续核对。本项承接 `work/active/joint-limit-shape-and-range-pass.md` 的 Blender 几何候选；用户已选择修改对称性、长度和默认姿态，并自行操作，不再等待“是否应镜像”的答复。

唯一操作说明、姿态要求和回填表均在 landing。先交付可复查的候选，不以动物量测、增轴比较或训练完成为前置。

导出接入、数值镜像断言与运行时验证交回父事项；正式采用才核验 `work/active/asset-tree-per-family.md`，资产生命周期沿用 `.codemaker/rules/versioning.mdc` §A。
