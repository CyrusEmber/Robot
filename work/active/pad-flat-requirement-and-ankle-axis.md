---
id: pad-flat-requirement-and-ankle-axis
title: 脚板能否平放：需求判定，与踝轴/行程的取舍
scope: rl_exp/versions/lizard2, rl_exp/blender, rl_exp/tasks, ablation_harness, acceptance/records
status: blocked
landing: rl_exp/blender/generate_urdf.py, rl_exp/versions/lizard2/main/main_params.yaml, ablation_harness/protocols/lizard2_flat_v4.json, rl_exp/tools/diagnose/pose_slider.py, rl_exp/tools/verify/check_leg_reachability.py
next: ① **先做分段可达性检查（本仓可做、离线 FK、不需训练）**（**仪器已落**：`rl_exp/tools/diagnose/pose_slider.py` 手摆看轴向与姿态、`rl_exp/tools/verify/check_leg_reachability.py` 供 `pad_state` / `joint_effect` 两个函数与 `--self-check`；读数见 `acceptance/records/2026-09-29-leg-pose-slider-and-pad-clearance`——**A/B/C 三段本身仍未做**），三段各自排除一类问题，**并按低速优先**（先 0.5 m/s 档，不要求一次证 0–3 m/s 全可行）：**(A) 静态四脚同时平放** —— 在合理机身高度范围与腿外展范围内，四只掌能否同时满足"掌面接近水平 + 四脚着地"，排除"连基本支撑姿态都不具备"；**(B) 支撑相内的平放轨迹** —— 足端从支撑相前端走到后端时能否**持续**近似平放，排除"能站平、不能带着步幅走"；所需位移 = 命令速度 × 支撑时长（= duty × 周期，均由三档实测给出：0.5 档约 0.08 m，2.8 档按 duty 0.38–0.50 约 0.47–0.62 m）；**(C) 连续性、限位余量、自碰撞** —— 该轨迹是否连续、是否留有关节限位余量、是否避开自碰撞，排除"数学上有解、实际执行不了"。**输出不设人为阈值**：报"最小可达残余倾角 vs 容差"与"可行步幅 vs 机身高度"的曲线，容差留到判定那一步由所有者给。**它证明不了什么必须写在结论里**：不能证明能承重、能平衡、能稳定行走；三项全不过 ⇒ 才有强理由优先改机械；三项全过 ⇒ 只说明"值得继续做动力学验证"，**不能宣布"只是奖励问题"**。② 需求（所有者）分两层：一层是**目标步态的具体化**（外展腿横扫 / 四腿相位 / 躯干侧摆配合 / 脚掌接触方式，各自给可测形式）—— 没有它"能不能走蜥蜴步态"无法判；另一层是**容差**（平放容差已可写成 `SIGMA` 的容差，见 evidence；另加相位容差、接触方式）。两层都齐了才谈第 ③ 步。③ 可达而策略没做 ⇒ 缺的是**奖励/需求**（那时才谈奖励设计，且要先按 ② 的可测形式写判据）；不可达 ⇒ 才在"接受 A/B 的代价"与"承认需求不可满足"之间选。④ 无论哪条：动资产就要走生成器真跑与快照同步（见依赖），并把作废范围写明。
close_when: (a) 三段检查各有读数（A/B/C 的最小残余倾角—容差曲线、可行步幅上限、限位余量分布、自碰撞结论），且**口径自检**做了：离线 FK 与仿真 FK 在若干姿态上逐位比对，偏差有数字；(b) 目标步态与容差两层需求都有明确答复（谁答的、依据是什么），且在 (a) 之后；(c) 结论按 (a)(b) 落到一条可查产物 —— 奖励/需求变更落点、**或**新版本的轴/行程 + 重复读数、**或**写进口径文档的"允许立边承重"前提、**或**"需求不可满足"的书面结论；(d) 若动了资产，锁/快照侧同步完成或另立事项，历史 run 的可复现性作废已写明；(e) 本项的结论里**不得**出现承重/平衡/稳定行走的判断（那是动力学验证的事，另立）。
depends_on: asset-tree-per-family
evidence: acceptance/records/2026-09-29-lizard2-pad-leveling-unreachable, acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-09-29-leg-pose-slider-and-pad-clearance, acceptance/records/2026-09-29-lizard2-pad-tilt-is-the-fold-sum
---

## 问题与本次范围

实测（逐帧、三档、四只脚）：三只板的倾角 36–50°，而它们**绕的是 x 轴**，脚板关节**只能绕 y 转** ⇒
**在这些承重姿态下**该关节对自己的立边无能为力（整个行程只值 1–3°）；第四只（lf）的倾斜绕 y，于是真的被摆平（1.46°，
且实际角贴在最优角上）—— 这是同一条机制的反证。**这份读数的范围必须说清**：它量的是"固定该帧小腿朝向、只动踝角"
的可达集，**不是**"整条腿换姿态后仍不可达"（后者是 ① 要做的 FK 可达性）。读数、模型验证（±1.5° 框偏移）与三条候选路都在记录里，
本项不复述。

本项只收**决定与它落在哪**：需求判定、轴/行程的取舍、以及"若不动轴"时口径要怎么说清。

**更正（2026-09-29，② 的可测形式）**：本项原先按"掌面能否贴地"问，而上游的倾角本身是一个**标量** ——
三个铰**平行共面**、角可加 ⇒ 机体水平时倾角只由折腿和 `SIGMA = haa + hfe + kfe` 与脚板角决定（髋不进、怎么分配也不进），
且现成策略已在其中一条腿上做到平放 ⇒ ② 的**容差层可以直接写成 `SIGMA` 的容差**（可从帧记录直接算、
零资产、零新关节），"掌面能否平放"是它的**推论**而不是前提。另一条：脚板关节对倾角只有 `cos(foot)` 一条通道，
在本资产的法线朝向下它的最优角就是自己的零位 ⇒ "给脚板换轴/加行程"不是平放的必要条件。
读数、口径边界（**机体/胸腔姿态那一项未关**）与它对本项三条候选路的含义见
`acceptance/records/2026-09-29-lizard2-pad-tilt-is-the-fold-sum.md`；按它改写后，① 的三段可达性问的是
"`SIGMA` 在承重姿态与步幅下能否保持 ≈0"（**A/B/C 三段本身仍未做**）。

## 与邻近事项的边界

- **结构表达限制**（远端链运动平面只能转方位角、不能相对机体倾斜；`haa`/`hfe`/`kfe` 平行共面且随 `hip` 绕机体 z 转）**不在本项**：那要动的是**自由度拓扑**，按 `versioning.mdc` 越级段属**同家族内的机体换代**（新机体走新路径、旧机体上的冻结版本同一次变更退休；2026-09-30 前写的"必换家族"已被该段取代，机制见 `work/closed/2026/body-swap-and-version-retire.md`）；本项只问踝轴/行程与需求判定。见 `acceptance/records/2026-09-30-lizard2-leg-to-anatomy-mapping.md`。
- `lizard2-family-landing`：管 v2 配方的奖励/动作接口决定；本项是**资产几何与需求**，不是配方。
- `asset-tree-per-family`：本项**依赖**它 —— 改轴/行程都要"生成器真跑 + 引用落在声明树内"这半边先成立。
- `teacher-snapshot-asset-sync`：资产换代后 teacher 快照里的派生字面量同步仍人工；本项不接管那一步。
- 脚板**增益/上限**是否合理不在本项（那一问已由 `work/closed/2026/feet-drive-candidate-probe.md` 否掉）。
