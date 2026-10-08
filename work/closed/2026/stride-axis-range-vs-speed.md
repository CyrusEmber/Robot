---
id: stride-axis-range-vs-speed
title: 步幅轴行程 vs 最高速度档：±0.6 rad 在 2.8 m/s 被顶满
scope: rl_exp/versions/lizard2, rl_exp/blender, rl_exp/tasks, acceptance/records
status: superseded
landing: rl_exp/versions/lizard2/main/main_params.yaml, ablation_harness/protocols/lizard2_flat_v4.json, rl_exp/tools/diagnose/gait_probe.py
outcome: 2026-10-08 并入 joint-limit-shape-and-range-pass：跨 seed/checkpoint 按档复核、髋行程与命令窗口三条决策出口及可比性说明移交；尚未作出行程决定。正文保留为合并前记录，贴限位的因果边界与换代流程以接收项及 acceptance/records/2026-10-08-lizard2-work-consolidation.md 为准。
superseded_by: joint-limit-shape-and-range-pass
close_when: (a) "髋贴限位是否系统性"有读数（≥2 seed 或 ≥2 checkpoint，按档分开报）；(b) 三条出口里有一条被选为决策，且落点可查（新版本参数 / 新命令窗口 + 版本号 / 一条口径前提）；(c) 若选了 (i) 或 (ii)，它对已训 v2 与历史判决的可比性影响已写明。
evidence: acceptance/records/2026-09-29-lizard2-pad-leveling-unreachable, acceptance/records/2026-09-29-lizard2-v2-gait-five-claims, acceptance/records/2026-09-29-lizard2-hfe-knee-limit, acceptance/records/2026-09-29-lizard2-pad-tilt-is-the-fold-sum
---

## 问题与本次范围

`plot_joints.py` 的贴限位读数（判据带宽 0.02 rad，256 envs / seed 123 / 20 s）：2.8 m/s 档 `lf_hip`
**26.6% 的帧**贴在 +0.600 上限（最小余量 0.0000），另外三条髋也都碰到过限位；同批读数里脚板余量
≥0.32 rad。⇒ **"关节被顶满行程"这件事只发生在步幅轴上**，而它是 lizard2 相对旧构型新加的那条轴。

本项只收**这条读数怎么变成结论、以及结论选哪条路**；具体数值与口径归上面两条记录。

**补充（2026-09-29，出口 (iii) 的前提有读数）**：(iii) 的前提"高速档由折膝折踝而非大腿摆动维持"现在有直接读数 ——
承重帧的折腿和 `SIGMA = haa + hfe + kfe` 按档给出，而脚板关节的行程被钳在零位附近（它对本资产的倾角只有
`cos(foot)` 一条通道，最优角就是零位）⇒ (iii) 若被选中，可以直接引这份读数而不是定性描述。
读数、口径与未关的一格（机体/胸腔姿态）见 `acceptance/records/2026-09-29-lizard2-pad-tilt-is-the-fold-sum.md`；
**这不改本项的口径**（髋仍是唯一贴满行程的轴）。

**更正（2026-09-29）**：本项原先引的"hfe 余量 ≥0.35 rad / hfe 从不靠近限位"不成立 —— 四腿三档的最小余量是
**0.1254 rad**（lf_hfe，2.8 档），且 lf 的实际膝角已越过伸直 6.4°。这条**不改本项的口径**（髋是唯一贴满行程的轴），
但它不是"离限位很远"而是"限位本身画错了"：读数与代价见
`acceptance/records/2026-09-29-lizard2-hfe-knee-limit.md`，处置归 `joint-limit-shape-and-range-pass`。

## 与邻近事项的边界

- `pad-flat-requirement-and-ankle-axis`：同为"资产几何要不要改"，但问的是踝（立边），本项问的是髋（步幅行程）；
  两者若都要动资产，**应当一起换代**（一次换代 = 一次锁/快照刷新），这一点在两边都写明。
- `lizard2-family-landing`：管 v2 配方的奖励/动作接口；本项里的 (ii) 会改配方参数 ⇒ 属那条线的版本决策，
  本项只把"窗口与行程的关系"这个读数与出口递过去。
- `dr-widening-policy`：DR 放宽是另一条轴（观测/动力学），与本项的行程预算无关。
