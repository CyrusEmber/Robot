# v13 NOTES —— 换回 Miki 对称跟踪核（一个核闭三个账本盲区）

- 修订历史：v13.0（2026-09-14，单变量：跟踪核换形）；v13.1（2026-09-14，**开训前验收
  口径修正**——代码/配方零变更，只改验收与表述，见「风险」「验收」两节）；v13.2
  （2026-09-14，**验收量测换帧 + 侧滑改 abs**：前向统一 `vel_yaw_x`（= 奖励核同帧）、
  侧滑闸改 `mean(|vel_yaw_y|)`、逐帧 MAE 报告，见「验收 1」）。

- 目的/假设: v10 判决（`v10\NOTES.md` + `DIAGNOSE.md`）暴露 EP 线性核
  `track_lin_vel_xy_lin`（v5，Cheng et al. 2023 Eq.2）的三个账本盲区：
  ① **超速饱和中性**——`clamp(proj, max=speed_c)`，快了不扣分（实测 cmd 0.3 跑
  0.445，+48…54%，账本 1.47/1.5）；② **横向不进分子**——`proj` 只取命令轴投影，
  横向速度不受约束（实测恒定 ~19–21° 蟹行、世界横移 2.4–6.2 m/10 s）；③ **零命令
  无停车梯度**——cmd=0 时 `proj≡0`，站与不站同分（实测零命令 10 s 漂 0.31 m 不停）。
  口径限定（DIAGNOSE 修订后，v13.1 再修正）：①的准确表述是**旧核放过了超速误差**，
  既不是超速的必要条件也不是充分条件——**有超速惩罚的策略同样可能超速**（罚项存在
  与净收益是两回事）；旧核做的事只是让该误差不进账本。本版闭合的是**账本盲区**
  （误差不再被 clamp 抹掉），策略是否收敛到「跟准」由验收量测判，不预设。
  v13 假设：换回 Miki et al. 2022 对称核 `r = exp(−‖v_cmd − v_yaw‖²/0.25)`
  （全 2D 误差、yaw 帧），一个核同时闭合三洞的账本侧；且 **cmd=0 站立拿满分** =
  停车目标首次进账本。
- 相对 v10 的变更（**单变量**，obs/DR/地形/终止/课程零变更）:
  - `versions/lizard/v13/lizard_params.yaml` = v10 全量拷贝 + `v13:` 段（v1–v10
    段保留作冻结记录；v5 段的 `track_goal_vel` 留作 EP 核冻结档案）
  - `LizardRoughTeacherEnvCfg_V13(V10)`: `params_version="v13"`，
    `__post_init__` 里 `rewards.track_lin_vel_xy_lin = None` 并挂
    `teacher_mdp.track_lin_vel_xy_miki`（weight/sigma_sq 读 v13 段）
  - 注册 `Lizard-Rough-v13` / `Lizard-Rough-Play-v13`（runner
    `lizard_rough_teacher_v13`）
  - 静态闸: `rl_exp/tools/verify/check_reward_v13.py`（无 sim：V13 miki 接线 +
    EP 核移除 + V5/V10 冻结不动 + yaml 记录 + v13.1 预注册静止值表）
- **偏差声明（F（belly −0.5 / r_slip −0.03 / torque 等）的相对权重逐字节同 v10，这是
  纯核形状单变量消融的前提；代价是不复刻论文超参比，判读时记住这点。

- 已知风险（预注册，判废线 = v10）: v3/v4 病历——旧 exp 核让站立白嫖残值，收敛到
  脚垫蹭行最优。**v13.1 修正：抗塌缩包的保留不足以推出「不会复发」**，理由两条：
  1. **静止仍拿残值，且各档增益不对称**（核形状推导，w=1.5、σ²=0.25，
     静止时 `r = 1.5·exp(−v_cmd²/0.25)`；闸 `check_reward_v13.py` 断言此表）：

     | 命令速度 | 静止时跟踪奖励 | 完美跟踪奖励 | 最大增益 |
     |---|---|---|---|
     | 0.3 m/s | 1.047 | 1.5 | 0.453 |
     | 0.5 m/s | 0.552 | 1.5 | 0.948 |
     | 1.0 m/s | 0.027 | 1.5 | 1.473 |

     0.3 档从静止到完美跟踪最多多拿 0.453；若运动带来的力矩、加速度、动作变化
     等代价吃掉这部分收益，停住或慢蹭仍是局部最优。
  2. **反塌缩罚项在「静止且腹部不触地」时都≈0**——belly −0.5 要接触力才扣、
     r_slip 要足部滑动才扣。它们封住的是「塌下去蹭」这条路径，**不产生走路激励**；
     保留权重 1.5 只保奖励上限，不保「实际收益 vs 罚项」的平衡。
  → 结论：复发与否只能由实测判（进度、速度误差、duty/接触形态）。
  **复发判据（v13.1 改组合，不再是单项判废）**：
  - **单项异常只记观察项**：`Episode_Reward/feet_slide` 劣于 v10 同期——从静止变成
    真正行走，滑动代价本来就可能上升；反过来彻底不动反而能让它变好。
  - **判废回滚 v10 需同时满足三条**：① 速度误差不达标（见「验收 1」的 abs 闸与
    MAE 报告）② 实际进度/位移低于 v10 同期 ③ 后脚 duty 塌向 0 **或**
    `belly_contact_force` 持续 >0（真趴窝的形态证据）。

- 验收（预注册，全部用 diagnose_support 修正后口径——真实体重 706.3 N、xyzw lib
  旋转、全 50 Hz 接触；**v13.1 三处修正 + v13.2 换帧/abs 侧滑**）:
  1. 三洞量测闭合（ckpt 接管，Phase 1/2 重跑）: 前向速度一律用 **`vel_yaw_x`**
     （yaw 对齐重力帧 = **奖励核同帧**；体坐标 `fwd_b` 俯仰会把重力分量折进 x 轴，
     会误报欠速，只作诊断列）。0.3 m/s 档速度误差**双向**——
     `abs(mean(vel_yaw_x)/v_cmd − 1) < 0.15`（原签名量 `overshoot < 0.15` 把「完全
     不动」记成 −1 也放行，v13.1 修正）；同时**报告逐帧 MAE**
     `fwd_mae_mps = mean|vel_yaw_x − v_cmd|`（不设闸，防「快慢交替被均值抵消」——均值
     达标而每帧都不对的情况必须看得见）。侧滑闸 **`mean(|vel_yaw_y|) < 0.05 m/s`**
     （v13.2：签名均值会被左右摆动抵消，`slip_y_mean` 只留方向诊断）、零命令
     `|v| < 0.1 m/s`（零命令档同样报 MAE）。闸与奖励同帧由
     `test_acceptance_metrics.py` 断言（含变异：体坐标在 45° 俯仰下会假阴）。
  2. 不劣化 = **固定场景性能**，**不用** `Curriculum/terrain_levels`（课程状态不是
     能力；eval 侧本来就把 terrain_levels 置 None）。判据：`Locomotion-Eval-v1`
     nominal seed 123 固定套件 `lizard_suite_v1`（flat / slope_5·10° / stairs_10·20cm /
     rough_a·b / gap_20·40cm）上 v13 与 v10 ckpt 同期对比——`lin_mae_mps`（全局 +
     逐地形）、`terrain_completion_mean`、`success_rate`/`fall_rate`、
     `stop_overshoot_mps`；再加 diagnose Phase 2 速度误差/位移、Phase 3 单级台阶
     （5/10/15/20 cm 上/下）通过率。v10 锚点（已在库，`results/locomotion_eval_v1/v10/`）：
     success 0.5681 / fall 0.0 / lin_mae 0.4643 / completion 0.7008 / stop_overshoot 0.1212。
     **口径注（v13.2）**：harness 的 `lin_mae_mps` 仍取体坐标 `lin_vel_b`（本次未改，
     保 v1 基线可比）——与奖励 yaw 帧不同源，读数偏高不是策略更差；改 harness 需开
     `Locomotion-Eval-v2` 并重跑 v10 基线，记入待办。
  3. 趴窝判据（v13.1 改组合，见上「风险」节）: `feet_slide` 单项变差**不作判废线**；
     判废 = 速度误差不达标 **且** 进度/位移回退 **且**（后脚 duty 塌向 0 或
     belly 持续受力）。
  4. **第一轮唯一判读问题**：**侧向漂移与超速是否下降，同时没有退化成欠速或不动**。
     本轮**不**额外加入四脚着地或 belly 惩罚（保单变量；它们属下一轮候选，见观察项）。
  5. 观察项（非闸）: 载荷左右对称性（lf/rf 比）与静止期四脚着地是否改善——
     v10 的三脚站/左前 62% 是否随停车梯度消失。
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v13 --max_iterations 15000 --seed 42
  ```
- 固定场景评测命令（验收 2）:
  ```bat
  python ablation_harness\eval.py --task Lizard-Rough-v13 --checkpoint <model.pt> ^
      --protocol locomotion_eval_v1 --mode nominal --seed 123
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v13/
- 结果回填: （训练后补：三洞量测表（含 MAE）/ 固定套件指标与台阶通过率对 v10 /
  趴窝组合判据读数 / 结论）
- 结论: （一句话，训练后补）
