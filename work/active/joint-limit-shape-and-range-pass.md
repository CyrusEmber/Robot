---
id: joint-limit-shape-and-range-pass
title: 巨蜥关节设计决策：参考动作、姿态与范围
scope: acceptance/records, rl_exp/tools/verify, rl_exp/tools/diagnose, rl_exp/blender
status: in_progress
landing: acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md#结果
next: 最小核验已补（r1 记录 §13：判定改逐项合取 + minimax 收尾、加密路径核验固定为关节空间线性插值、B≤A 定义为最坏项并核验种子等价性、体高敏感性证明 0.60 非机械上限）。下一步按用户方向：① 用**候选巨蜥空间姿态**重建目标（当前 engineered 周期尚未证明"像巨蜥"，也不能反推骨段长度/限位）；② 推进**骨架对称性、骨段长度与默认姿态候选**；③ 分支连续性与机体自碰撞仍未查，需在重建时一并定口径；④ D1–D3 待答复
close_when: Codex 复核 landing 的最终判定与证据，本对话用户确认选择及工况；保留/修改方案经评审通过且未完实施已交具名活跃事项后关闭，全部拒绝亦关闭，任一待决或未判定继续在办；正式采用另过机制闸门
evidence: acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-08-lizard2-reference-motion-v0, acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts
---

## 当前动作与待决问题

当前执行者为 Codex；需求确认人与最终设计决策人为本对话用户。技术判据唯一入口是 landing 的“验收条件”，候选读数与决策进入该记录的结果指针。

| 决策线程 | Codex 下一份可审阅提案 | 确认人 |
|---|---|---|
| D1 接触要求 | 各阶段接触方式，是否要求平放或允许立边，及其动作代价 | 本对话用户 |
| D2 允许姿态域 | 巨蜥目标正例与拒绝反例、默认站姿、各量工程容差及依据 | 本对话用户 |
| D3 工况与取舍 | 目标速度带、髋行程/命令窗口候选与历史可比性 | 本对话用户 |

三项提案草案已提交、答复待给（答复栏见 `evidence` 的 r1 记录）；已表达的巨蜥动作目标沿用参考记录；不重复询问已获授权的资料整理。未答项只阻塞相应定案，不阻塞标注、量测与离线探索。

## 阶段入口与交接

按 landing 的 R1（参考/需求）→ R2（仪器/结构）→ R3（接触/连续性）→ R4（范围/速度）→ R5（发力/执行）推进。每阶段读取该处判据，不在本项维护第二套产物或通过条件。

正式采用阶段才以前置核验 `work/active/asset-tree-per-family.md`；配方、动作接口及评测协议交付 `work/active/lizard2-family-landing.md`。源资产镜像与文献补证继续由各自事项承接；缺少实施落点时先建立具名事项再交接。

换代与两种锁的处理只引用 `.codemaker/rules/versioning.mdc` §A；规则证据见 `acceptance/records/2026-09-30-body-swap-and-lock-freeze.md`。此处涉及的资产冻结锁为 `asset_lock.json`，配方锁为 `cfg_lock.json`。
