---
id: terrain-evidence-18b
title: 地形证据随运行归档 + 离线再生核验（HARNESS 挂账 #3 ⑤b / PLAN #18 ①）
scope: ablation_harness
status: done
landing: rl_exp/tasks/terrain_geometry.py, ablation_harness/protocols/locomotion_eval_v3.yaml, rl_exp/tools/verify/test_terrain_geometry.py
outcome: 起伏改在真实生成路径逐格测量并随运行归档；离线闸按归档自述的 suite+seed 重建后逐格比，含起伏断言。替代说明：原写"由 rebuild.py 核验"，现 rebuild.py 只核材料完整性，"地形产物一致"由再生判定。
evidence: rl_exp/versions/lizard/ACCEPTANCE.md, acceptance/records/2026-09-20-doc-read-cost-baseline.md
---

## 问题与本次范围

零动作跑里 9 列 completion 全 ≈0.004 ⇒ 分布在这条跑上没有信息量；而套件 v1 的 rough 两列实为均匀抬升
平板（`noise_range` 单值使 `np.random.choice` 退化），拿它当起伏地形会误判。本轮要的是**能随运行取回、
且能离线重建比对**的地形几何证据。

## 落点（这条为什么算已关闭）

规则不靠散文成立：`foot_relief` 的定义与天花板写在 `rl_exp/tasks/terrain_geometry.py` 的 docstring；
归档位置与身份（suite+seed+定义）由协议 v3 规定；逐格比与起伏断言由离线闸第 5 例执行。
三处任一被改，闸门会红。

## 未覆盖边界

顶点法只对"最大面 ≤ 脚板格 0.5 m"的网格成立（hfield 0.14–0.28 m ✓；楼梯/gap/平面的 13–22 m 巨面
记 `null`）；升级路径（射线采样）写在 docstring，未实施。重建评级 = 另一事项。
