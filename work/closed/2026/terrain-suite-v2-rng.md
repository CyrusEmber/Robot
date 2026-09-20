---
id: terrain-suite-v2-rng
title: 地形随机源的两处缺口（套件"粗糙列"退化 + 训练侧未播种）（HARNESS 挂账 #3 ①②，已收）
scope: ablation_harness, rl_exp/tasks
status: done
landing: ablation_harness/suites.py, ablation_harness/protocols/locomotion_eval_v3.yaml, rl_exp/tasks/terrain_geometry.py, rl_exp/fork_patches/train_seed_rng.patch, rl_exp/tools/verify/test_terrain_geometry.py
outcome: 两处都改成了机制：(a) 套件升 `lizard_suite_v2`（rough 两列从单值 `noise_range` 退化成均匀抬升平板 → `(0.02,0.06)`/`(0.08,0.16)` + `noise_step` + `downsampled_scale`），配套新协议 `locomotion_eval_v3`（与 v2 只差 name/version/suite，由测试看守），`eval.py` 默认协议改 v3 且每次运行写 `suite.geometry_digest`；(b) 训练侧同 cfg 两次真跑几何不同（`stepping_stones`/`random_rough` 抽未播种的全局 numpy 流、`boxes` 抽全局 torch 流）→ 训练入口把播种提到 `gym.make` 之前，补丁存档并由 `framework_pin_check` 逐字节重建看守。两处都有"抽掉即红"的离线反证。
evidence: rl_exp/versions/lizard/ACCEPTANCE.md
---

## 问题与本次范围

"粗糙地形"列名与实际几何不符：单值 `noise_range` 让 `height_range` 只剩一个元素、`np.random.choice`
退化成常量 ⇒ rough 两列实为均匀抬升平板，`suites.py` 里"seed 钉住 RNG 流"的说法在机制上不成立。
同一类问题在训练侧表现为"同 cfg 同 seed 两跑几何不同"。

## 落点（这条为什么算已关闭）

规则不靠散文成立：套件参数由 `suites.py` 持有并被协议引用；几何测量与归档形态由
`terrain_geometry.py` 定义；"同 seed 必须同几何"由离线闸逐格比断言，播种由被 pin 看守的补丁保证。
改任一处，闸门会红。

## 未覆盖边界

顶点法与归档边界见 `work/closed/2026/terrain-evidence-18b.md`；协议 v1/v2 的历史结果留在原地不迁移，
且**三版不得混表**。重建评级 = `PLAN.md` #18 ① 仍单独排期。
