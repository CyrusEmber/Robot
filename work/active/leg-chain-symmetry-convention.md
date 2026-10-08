---
id: leg-chain-symmetry-convention
title: Blender：对称骨架、骨段长度与默认姿态候选
scope: rl_exp/blender, rl_exp/tools/verify, acceptance/records
status: open
landing: acceptance/records/2026-10-08-lizard2-blender-body-candidate.md#操作步骤
next: 候选已由 Codex 脚本交付（blend + 四张截图 + 隔离目录导出与随姿态偏转的转轴），镜像、接地与四段方向在记录里回填 —— 等本对话用户看候选给接受/修改/拒绝。接受则把限位、运行时初始角度与镜像闸门留在 joint-limit-shape-and-range-pass 后关闭本项；要改则只改摆姿参数重出候选
close_when: 用户检查候选文件与预览，Codex 核对结果和后续落点；接受且未完接入已交 joint-limit-shape-and-range-pass 则关闭，拒绝并说明原因亦关闭，仍需修改或镜像/接地未核验则继续在办
evidence: acceptance/records/2026-10-08-lizard2-blender-body-candidate, acceptance/records/2026-09-23-lizard2-leg-chains-not-mirrored, acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation
---

执行者为 Codex（用户 2026-10-08 从"自行在 Blender 操作"改为要求 Codex 用脚本执行）。本项承接 `work/active/joint-limit-shape-and-range-pass.md` 的 Blender 几何候选；用户已选择修改对称性、长度和默认姿态，本轮保骨长不变，并追加"转轴随新零位一起定 + 隔离目录导出"。

唯一操作说明、姿态要求和回填表均在 landing。先交付可复查的候选，不以动物量测、增轴比较或训练完成为前置。

导出接入、数值镜像断言与运行时验证交回父事项（导出与轴向本轮已做，镜像断言进闸门与限位、初始角度仍在父事项）；正式采用才核验 `work/active/asset-tree-per-family.md`，资产生命周期沿用 `.codemaker/rules/versioning.mdc` §A。
