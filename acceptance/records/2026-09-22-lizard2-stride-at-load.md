# 2026-09-22 新骨骼的承重行程与动作映射（lizard2 vs lizard 同口径）

## 适用范围

- 被验对象：`lizard2/main` v1（新骨骼，腿链 `hip → haa → hfe → kfe → foot`）与
  `lizard/main` baseline v1（旧骨骼，腿链 `haa → hfe → kfe → foot`）。
- 工具：`rl_exp/tools/verify/check_joint_layout.py`（本轮改为**按资产自身**推导腿部关节、逐腿量测、
  力臂与弦长断言；`--sweep-leg/--sweep-a/--sweep-b`、`--require-all-actions`）。
- 覆盖：腿部关节的轴向、驱动几何（力臂）、承重姿态下的前后/上下行程（四腿）、两关节组合行程、动作通道覆盖。
  回答"新髋到底做了什么、能不能被策略驱动"。
- 不覆盖：接触力、摩擦、PD 跟踪、多腿协调、训练效果；也不覆盖 obs 声明与 `EXPECTED_DIFFS`（既定待办）。

## 验收条件

- 两次运行必须**同口径**：同一工具、同一落定流程（零动作 100 步）、同一天；旧家族的读数必须与
  2026-09-21 记录**逐项一致**（否则工具改造动了旧读数）。
- 每个关节必须给出力臂与自由上界 `2·arm·sin(Δθ/2)`，且实测 `dx ≤ chord`（读法错误必须当场判红）。
- 新髋必须给出**四腿**的承重行程，不允许单腿特例；必须是本资产前后行程最大的关节。
- 动作侧：30 个关节全部且仅被一个动作项覆盖，动作维数与映射一致（`--require-all-actions`）。

## 结果

单关节（各自扫遍 URDF 行程，机体高度固定；`arm` = 轴线到该腿脚掌中心垂距）：

| 关节 | lizard2（base z 0.912 m） | lizard（base z 0.935 m） |
|---|---|---|
| **hip** | 轴 (0,0,1)，arm 0.490–0.494，±0.6 rad，**dx 0.546–0.558 m（四腿）** | 不存在 |
| haa | 轴 (−1,0,0)，arm ≈0.98，dx 0.016–0.041，dz 0.547–0.552 | 轴 (−1,0,0)，arm ≈0.99，dx 0.000–0.059，dz 0.538–0.560 |
| hfe | 轴 (−1,0,0)，arm 0.591，dx 0.015–0.045，dz ≈0.302 | 轴 **(0,0,1)**，arm 0.060–0.070，**dx 0.111–0.130（本资产最大）** |
| kfe | 轴 (−1,0,0)，arm 0.213，dx 0.009–0.017，dz ≈0.18 | 轴 (−1,0,0)，arm 0.213，dx 0.003–0.029，dz ≈0.18 |
| foot | 轴 (0,1,0)，arm 0.079，dx 0.072–0.076，dz 0.098 | 同 lizard2 |

组合（承重高度、参考腿 lf，5×5 网格）：lizard2 **hip×hfe 0.932 m**（10/25 格可达，全格 1.130 m）；
lizard **hfe×kfe 0.392 m**（10/25 格，全格 0.395 m，需要机体高度 0.901–1.099 m）——与
`2026-09-21-lizard-leg-axis-kinematics` 记录逐项一致。两族的中格自检都过：458 vs 457 mm、422 vs 423 mm。

动作侧（`Lizard2-Flat-Play-v1`）：`TOTAL_ACTION_DIM 30` = `joint_pos_legs (20)` + `joint_pos_spine (10)`；
`ACTION COVERAGE 30 of 30 joints channelled`，无未接通道、无重复；`ACTION_COVERAGE_GATE PASSED`；
env 构建表 `policy (102,)` = 3+3+3+3+30+30+30，7 项。

本轮在工具里补的三处读法（都会让数字失真，已写成机制）：参考姿态必须是**落定后**的关节状态；
测量点必须是**固定材料点**（脚掌 bbox 中心，不是"最低角"——后者量到脚掌自身 0.458 m 的尺寸）；
**每条腿量自己的脚掌**，且力臂与轴线必须在**同一姿态**下重新测（首版用零位姿态的轴量落定姿态，
lizard 的 `rr_hfe` 力臂偏小 8%，被 `dx ≤ chord` 断言当场抓住）。

## 证据引用

- 复读命令（同口径）：
  `check_joint_layout.py --task Lizard2-Flat-Play-v1 --viz none --require-all-actions --sweep-a hip --sweep-b hfe`；
  `check_joint_layout.py --task Lizard-Baseline-Flat-Play-v1 --viz none`。
- 旧读数对照：`acceptance/records/2026-09-21-lizard-leg-axis-kinematics.md`（0.392 m / 0.395 m / 0.901–1.099 m）。
- 结论用途：`work/active/lizard2-family-landing.md` 的 `next` ⑤（开训前检查已含此项证据，探针改造仍待做）。

## 未覆盖边界

- **纯运动学**：全程 `sim.forward()`，不含接触力、摩擦与 PD 跟踪；"0.93 m"是几何可达，不是"能推 0.93 m 地面"。
- **一次一条腿**：组合表只扫参考腿 lf 的两个关节；四腿同时使用时的自碰撞、机身反作用、足端滑移都不在内。
- **组合表只覆盖两关节**，5×5 网格不是可达集上界；haa 的抬降（0.55 m）与髋的耦合未扫。
- 承重高度按"零动作落定"取值，策略实际姿态不同则行程不同；落定失败（机体过低/过高）时脚本只 WARN，仍会出数。
- obs 102 是 env 构建时的活表，但尚未钉进 obs 协议声明；`--sweep-*` 改配对或换地形/任务都会改数，本记录只对上述两次运行有效。
