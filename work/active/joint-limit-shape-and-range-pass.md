---
id: joint-limit-shape-and-range-pass
title: lizard2 陆地骨骼、足部驱动与完整步态修复统筹
scope: acceptance/records, rl_exp/blender, rl_exp/tools/verify, rl_exp/tools/diagnose, rl_exp/tasks, rl_exp/versions/lizard2
status: in_progress
landing: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md#阶段顺序与责任, acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md#验收条件
next: 执行者按整体记录 S0–S3 先完成需求正反例、仪器口径核对、隔离骨骼与足部驱动候选及完整周期验证，再按 S4 验躯干侧弯和拖尾。数值容差由执行者提出、用户确认；具体 kfe/foot 映射和实现由执行者设计，不再等用户指定骨骼。S5–S6 交付由 lizard2-family-landing 承接。当前只落整体 work，未开始机体或驱动实施；游泳留后续。读数和判定只写 acceptance/records。
close_when: 执行者完成整体记录 S0–S4 的候选、R1–R5 证据与具名判定后置 pending_review；新上下文审核落点、原始证据及各需求正反例，用户确认机体与动作。未通过退回 in_progress 或 blocked；未完配方、资产采用、训练和评测交付须由具名活跃事项承接，不能以最小自检或旧 v3 速度通过关闭。
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-08-lizard2-reference-motion-v0, acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts, acceptance/records/2026-10-08-lizard2-v3-landing, acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync, acceptance/records/2026-10-09-lizard2-knee-reverse-bending-measurement, acceptance/records/2026-10-09-lizard2-collision-margin-and-ankle-pass, acceptance/records/2026-10-09-lizard2-v3-init-dist-limit-occupancy
---

## 整体入口与责任

本项统筹陆地机体、足部驱动、完整迈步、躯干和尾部协同的设计与验证。用户本轮授权、候选映射、阶段顺序、未定参数和游泳暂缓范围唯一归 `acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md`；技术验收继承原合同 R1–R5，不在本项复制判据或结论。

执行者为接手本项的 AI；用户确认视觉目标、工程容差与最终采用。先交隔离候选，不覆盖现机体；正式采用和版本处理消费 `.codemaker/rules/versioning.mdc` §A。现有 v3 入口为 `rl_exp/versions/lizard2/PLAN.md`，本项不是 v3 解冻或新版本已建立的声明。

## 落点与交接

- 骨骼候选复用 `rl_exp/blender/lizard2_stance_candidate.py` 与 `rl_exp/blender/generate_urdf.py`；是否需要新增脚本或自由度由结构缺口决定，不默认新建。
- 仪器与连续周期复用 `rl_exp/tools/verify/check_leg_reachability.py`、`rl_exp/tools/diagnose/stance_step_probe.py`、`rl_exp/tools/diagnose/gait_probe.py`；既有踝部分析的勘误入口见整体记录，不继续消费过时判断。
- `work/active/lizard2-family-landing.md` 承接获准设计的动作接口、奖励、有效限速、新接触协议、下一版本和训练评测接入；`work/active/asset-tree-per-family.md` 仅在正式采用时核验资产管线。
- `work/active/large-monitor-skeleton-muscle-literature.md` 提供生物资料与证据边界，不阻止明确标注的工程候选探索，也不替代动态验证。

原有范围/姿态域、髋行程、反曲、碰撞、增益预算与部署边界均继续由上述阶段消费；证据只引用 frontmatter 的落点，不另留历史状态或读数摘要。
