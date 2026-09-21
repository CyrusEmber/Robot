---
id: floor-contact-attribution
title: 地面接触归属：谁在滑（摩擦极限）+ 穿透容忍度
scope: rl_exp/tools/diagnose, rl_exp/assets
status: open
landing: rl_exp/tools/diagnose/diag_metrics.py, ablation_harness/baseline_eval.py, ablation_harness/protocols/baseline_flat_v2.json
next: ① 采集逐接触 body 的 `|F_tang| / F_normal` 与有效 µ（摩擦已有实测值，但没有任何工具回答"谁在滑"）；② 用同一批数据分"颈在滑"还是"脚在滑"（颈 82–90 N、四脚 70–90% 体重，都在摩擦预算内）；③ 把穿透容忍度交资产/物理拍板：实测穿插 5 mm、`contact_offset` 3.5–14.7 mm、`rest_offset` 0——接受现状，还是收紧后重测
close_when: (a) 报告给出每个接触 body 的切向/法向比，且结论与位移、逐脚 duty 自洽；(b) 穿透容忍度有一句明确决定（接受 5 mm 或改参数重测并记新值）。两项齐了才关；只有 (a) 而 (b) 未拍板 ⇒ 保持 open（缺的是决定，不是数据）
depends_on: baseline-eval-native-crash
evidence: acceptance/records/2026-09-20-baseline-flat-eval-protocol.md
---

## 问题与本次范围

用户看到"头在地上划、而且确实穿插了"，本项把两个追问变成可量、可判的事：

1. **为什么能滑**：摩擦存在且不小（每 shape 静/动 1.0、地面 1.0、`combine=multiply` ⇒ µ ≈ 1.0），所以
   "无摩擦滑行"不成立；颈承重 82–90 N ⇒ µN ≈ 82–90 N 切向抗力，更像**刮擦借摩擦牵引**的第五支撑。
   是颈在滑还是脚在滑，需要逐 body 的切向/法向比——**目前没有这个量**。
2. **为什么能穿**：碰撞体是 `convexHull`，`rest_offset = 0`、`contact_offset` 3.5–14.7 mm ⇒ 接触只在极近
   距离生成、求解器有限速度去穿透，持续下压停在**几毫米稳态穿插**（实测 5 mm）。这是软约束允许的量级；
   是否为此收紧接触偏移是**资产/物理决策**。

口径教训（已落地）：AABB 角点读入地深度**夸大 ~10 倍**（同帧 −0.052 vs −0.005 m），角点实现已删，统一走网格顶点。

## 未覆盖边界

不覆盖资产改造（改 URDF/USD 或接触参数属资产线，本项只把问题与证据递过去）；不覆盖脚板被动移动的影响
（见 `baseline-v2-recipe` 的资产不动假设）；µ 的组合方式由框架基座声明，本项不能改。
