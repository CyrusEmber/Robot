---
id: stride-axis-range-vs-speed
title: 步幅轴行程 vs 最高速度档：±0.6 rad 在 2.8 m/s 被顶满
scope: rl_exp/versions/lizard2, rl_exp/blender, rl_exp/tasks, acceptance/records
status: open
landing: rl_exp/versions/lizard2/main/main_params.yaml, ablation_harness/protocols/lizard2_flat_v4.json, rl_exp/tools/diagnose/gait_probe.py
next: ① **先把它从"单 seed 单窗口"变成结论**：现有读数是 256 envs/seed 123 的 20 s 窗口（lf 的 hip 在 2.8 档有 26.6% 的帧贴在上限 +0.600、四腿的髋都碰到过限位），而同一批读数里**脚板离限位还有 0.32 rad**、hfe 从不靠近。做法：换 2 个以上 seed 或 checkpoint、按档分开读同一读数（`plot_joints.py --at_stop_rad` 的"贴限位帧占比"与最小余量已给逐关节值）。② 若系统性成立，三选一（代价各写）：**(i) 加宽 hip 行程** —— 属资产换代（同样的生成器真跑 + 快照同步 + 历史 run 作废，与 `pad-flat-requirement-and-ankle-axis` 共用前置）；**(ii) 收窄命令窗口**到行程够用的范围 —— 属配方变更，已训的 v2 因此只能开 v3，且所有历史判决的"命令箱"与它不可比；**(iii) 接受** —— 写成口径前提："高速档由折膝折踝而非大腿摆动维持，速度上限由步幅轴行程决定"，并说明它如何影响"像蜥蜴"的判读。③ 与 `pad-flat-requirement-and-ankle-axis` 的**共用前置**：任何资产换代都要先有生成器真跑（`asset-tree-per-family`）。
close_when: (a) "髋贴限位是否系统性"有读数（≥2 seed 或 ≥2 checkpoint，按档分开报）；(b) 三条出口里有一条被选为决策，且落点可查（新版本参数 / 新命令窗口 + 版本号 / 一条口径前提）；(c) 若选了 (i) 或 (ii)，它对已训 v2 与历史判决的可比性影响已写明。
evidence: acceptance/records/2026-09-29-lizard2-pad-leveling-unreachable, acceptance/records/2026-09-29-lizard2-v2-gait-five-claims
---

## 问题与本次范围

`plot_joints.py` 的贴限位读数（判据带宽 0.02 rad，256 envs / seed 123 / 20 s）：2.8 m/s 档 `lf_hip`
**26.6% 的帧**贴在 +0.600 上限（最小余量 0.0000），另外三条髋也都碰到过限位；同批读数里脚板余量
≥0.32 rad、hfe 余量 ≥0.35 rad。⇒ "关节不够用"这件事**只发生在步幅轴上**，而它是 lizard2 相对旧构型
新加的那条轴。

本项只收**这条读数怎么变成结论、以及结论选哪条路**；具体数值与口径归上面两条记录。

## 与邻近事项的边界

- `pad-flat-requirement-and-ankle-axis`：同为"资产几何要不要改"，但问的是踝（立边），本项问的是髋（步幅行程）；
  两者若都要动资产，**应当一起换代**（一次换代 = 一次锁/快照刷新），这一点在两边都写明。
- `lizard2-family-landing`：管 v2 配方的奖励/动作接口；本项里的 (ii) 会改配方参数 ⇒ 属那条线的版本决策，
  本项只把"窗口与行程的关系"这个读数与出口递过去。
- `dr-widening-policy`：DR 放宽是另一条轴（观测/动力学），与本项的行程预算无关。
