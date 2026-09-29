---
id: pad-flat-requirement-and-ankle-axis
title: 脚板能否平放：需求判定，与踝轴/行程的取舍
scope: rl_exp/versions/lizard2, rl_exp/blender, rl_exp/tasks, ablation_harness, acceptance/records
status: blocked
landing: rl_exp/blender/generate_urdf.py, rl_exp/versions/lizard2/main/main_params.yaml, ablation_harness/protocols/lizard2_flat_v4.json
next: ① **定需求（卡在所有者）**：验收要求是"**板必须能平放**"还是"**接触可靠即可**"。这一问决定它是架构问题还是资产问题，本项不自行判。② 若"必须能平放" ⇒ 现有结构表达不了（踝只有一条绕 y 的轴，而实测的立边是绕 x 的倾角，两轴垂直 ⇒ 该关节整个 ±0.5 rad 行程只值 1–3°）⇒ **换轴或加一个自由度**，属新家族/新版本的资产换代，历史 checkpoint 不可复用；且记录里的反事实读数说**光换轴不够**：同样的 ±0.5 rad 花在 x 上只把中位从 33–53° 降到 12–22°、最优角多数帧压在上限 ⇒ "换轴 + 扩行程"两件一起。③ 若"接触可靠即可" ⇒ 改板几何（摇椅面/圆角掌）属资产层，不动关节拓扑；同时把"允许立边承重"写成口径前提并指明落点，**并撤掉任何要求板平放的想法**（奖励/验收侧都不许再隐含它）。④ 无论走哪条：动资产就要走生成器真跑与快照同步（见依赖），并把"历史 run 的接触几何不再可复现"写明。
close_when: (a) 需求有一个明确答复（谁答的、依据是什么）；(b) 答复兑现成一件可查产物 —— 新版本的轴/行程 + 重复读数，**或**一条写进口径文档的"允许立边承重"前提（含落点）；(c) 若动了资产，锁/快照侧同步完成或另立事项，且历史 run 的可复现性作废已写明。
depends_on: asset-tree-per-family
evidence: acceptance/records/2026-09-29-lizard2-pad-leveling-unreachable, acceptance/records/2026-09-23-lizard2-v1-gait-skate
---

## 问题与本次范围

实测（逐帧、三档、四只脚）：三只板的倾角 36–50°，而它们**绕的是 x 轴**，脚板关节**只能绕 y 转** ⇒
该关节对自己的立边**无能为力**（整个行程只值 1–3°）；第四只（lf）的倾斜绕 y，于是真的被摆平（1.46°，
且实际角贴在最优角上）—— 这是同一条机制的反证。读数、模型验证（±1.5° 框偏移）与三条候选路都在记录里，
本项不复述。

本项只收**决定与它落在哪**：需求判定、轴/行程的取舍、以及"若不动轴"时口径要怎么说清。

## 与邻近事项的边界

- `lizard2-family-landing`：管 v2 配方的奖励/动作接口决定；本项是**资产几何与需求**，不是配方。
- `asset-tree-per-family`：本项**依赖**它 —— 改轴/行程都要"生成器真跑 + 引用落在声明树内"这半边先成立。
- `teacher-snapshot-asset-sync`：资产换代后 teacher 快照里的派生字面量同步仍人工；本项不接管那一步。
- 脚板**增益/上限**是否合理不在本项（那一问已由 `work/closed/2026/feet-drive-candidate-probe.md` 否掉）。
