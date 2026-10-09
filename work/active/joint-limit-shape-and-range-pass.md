---
id: joint-limit-shape-and-range-pass
title: 巨蜥关节设计决策：参考动作、姿态与范围
scope: acceptance/records, rl_exp/tools/verify, rl_exp/tools/diagnose, rl_exp/blender
status: in_progress
landing: acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md#结果
next: 反曲边界已按当前机体重测并进离线闸门；网格级自碰撞与自碰撞开关对照已补齐（见 acceptance/records/2026-10-09-lizard2-collision-margin-and-ankle-pass.md：限位盒内 32 对网格级确认自穿、采用机体开自碰撞仿真不推进、旧机体同命令正常跑 ⇒ "这一族不能开自碰撞"的旧假设被推翻）。待决落在两件上：**范围/姿态域**（限位盒自穿 + 盒内翻掌姿态 + 踝是纯朝向关节 ⇒ 盒 ≠ 运行域；收窄限位、加朝向约束或明确接受，属同一个决策）与**限位实施的版本/资产路径**（§A）；控制余量改按同工况贴限位占比判，不再用小幅度扫描的滞后。**下一读数**：把同一把 `check_self_collision.py` 的用例集合限到**运行可达域**（可命令关节取自身限位内、`kfe`/`foot` 钉在 PD 目标），看盒内那批反例还剩几对——"盒 ≠ 运行域"到这才可判；裁剪/夹紧的前置是该域达标，不是先裁后验。读数按绑定位形状留（code rev、cfg、资产 sha、seed、环境数、窗口）。继续核验完整动作周期（R3）与发力/执行（R5）；下段倾角、左右命令符号、后脚板形状仍分别决策，不因正式采用自动关闭。**下游动作（2026-10-09 接手）**：目标速度带（R4）定下后，回填 `actuator-params-audit` 留下的"增益是否过大"**阈值依据**——用 R4 的速度带换出各关节的力矩/带宽需求，再与 `acceptance/records/2026-10-09-lizard2-leg-joint-inertia-and-gain-caliber.md` 的 ω_n/ζ 读数比；该事项已关闭（`work/closed/2026/actuator-params-audit.md`），其读数归上述记录。**髋侧贴限位已有读数（2026-10-09）**：初始分布下的命令侧占比、物理侧占比及其对动作相关时间的敏感性见 `acceptance/records/2026-10-09-lizard2-v3-init-dist-limit-occupancy.md` —— 它把 D3 的出口（改 `legs_scale` / 改髋量程 / 写成口径前提）从"没有读数"推到"读数在手待选"，本项不在事项里选出口。
close_when: Codex 复核 landing 的最终判定与证据，本对话用户确认选择及工况；保留/修改方案经评审通过且未完实施已交具名活跃事项后关闭，全部拒绝亦关闭，任一待决或未判定继续在办；正式采用另过机制闸门
evidence: acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-08-lizard2-reference-motion-v0, acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts, acceptance/records/2026-10-08-lizard2-v3-landing, acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync, acceptance/records/2026-10-09-lizard2-knee-reverse-bending-measurement, acceptance/records/2026-10-09-lizard2-collision-margin-and-ankle-pass, acceptance/records/2026-10-09-lizard2-v3-init-dist-limit-occupancy
---

## 当前动作与待决问题

总体核对与接入执行者为 Codex；Blender 交付事项已归档至 `work/closed/2026/leg-chain-symmetry-convention.md`，后续设计与验证由本项承接。需求确认人与最终设计决策人为本对话用户。技术判据唯一入口是 landing 的“验收条件”，候选读数与决策进入该记录的结果指针。

| 决策线程 | Codex 下一份可审阅提案 | 确认人 |
|---|---|---|
| D1 接触要求 | 各阶段接触方式，是否要求平放或允许立边，及其动作代价 | 本对话用户 |
| D2 允许姿态域 | 巨蜥目标正例与拒绝反例、默认站姿、各量工程容差及依据 | 本对话用户 |
| D3 工况与取舍 | 目标速度带、髋行程/命令窗口候选与历史可比性 | 本对话用户 |

三项提案草案已提交，剩余答复见 `evidence` 的 r1 记录；D2 已有用户补充决定，引用状态同步记录与 landing 的 R4，不再整项记为未答。未答项只阻塞相应定案，不阻塞标注、量测与离线探索。

## 阶段入口与交接

当前 v3 设计入口为 `rl_exp/versions/lizard2/PLAN.md`；本项承接其中的机体、动作与限位决策，推进状态留在本项，实测与判定仍归 evidence。

按 landing 的 R1（参考/需求）→ R2（仪器/结构）→ R3（接触/连续性）→ R4（范围/速度）→ R5（发力/执行）推进。每阶段读取该处判据，不在本项维护第二套产物或通过条件。

后续资产采用仍以前置核验 `work/active/asset-tree-per-family.md`；配方、动作接口及评测协议交付 `work/active/lizard2-family-landing.md`。Blender 几何交付归已关闭事项；后续镜像闸门、候选限位与验证由本项承接，文献补证继续由各自事项承接。

换代与两种锁的处理只引用 `.codemaker/rules/versioning.mdc` §A；规则证据见 `acceptance/records/2026-09-30-body-swap-and-lock-freeze.md`。此处涉及的资产冻结锁为 `asset_lock.json`，配方锁为 `cfg_lock.json`。
