---
id: leg-chain-symmetry-convention
title: Blender：对称骨架、骨段长度与默认姿态候选
scope: rl_exp/blender, rl_exp/tools/verify, acceptance/records
status: done
landing: acceptance/records/2026-10-08-lizard2-blender-body-candidate.md#操作步骤
outcome: 用户已批准采用候选，交付与正式接入证据见 acceptance/records/2026-10-08-lizard2-blender-body-candidate.md、acceptance/records/2026-10-08-lizard2-v3-landing.md；按原关闭条件归档，后续限位、完整动作与镜像闸门交 work/active/joint-limit-shape-and-range-pass.md。关闭复核见 acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync.md
close_when: 用户检查候选文件与预览，Codex 核对结果和后续落点；接受且未完接入已交 joint-limit-shape-and-range-pass 则关闭，拒绝并说明原因亦关闭，仍需修改或镜像/接地未核验则继续在办
evidence: acceptance/records/2026-10-08-lizard2-blender-body-candidate, acceptance/records/2026-10-08-lizard2-v3-landing, acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync
---

执行者为 Codex（用户 2026-10-08 从"自行在 Blender 操作"改为要求 Codex 用脚本执行）。本项承接 `work/active/joint-limit-shape-and-range-pass.md` 的 Blender 几何候选；用户已选择修改对称性、长度和默认姿态，本轮保骨长不变，并追加"转轴随新零位一起定 + 隔离目录导出"。

唯一操作说明、姿态要求和回填表均在 landing；用户选择与正式采用引用 evidence。

后续数值镜像闸门、限位与完整运行验证交回 `work/active/joint-limit-shape-and-range-pass.md`；本项关闭不表示这些验证完成。资产生命周期沿用 `.codemaker/rules/versioning.mdc` §A。
