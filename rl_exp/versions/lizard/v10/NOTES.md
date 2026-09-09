# v10 —— 删除 tilt 终止（摔倒交给奖励账本 + 学翻身）

- 修订历史：v10.0（2026-09-09，单变量：tilt 终止删除）。

- 目的/假设: v3 装机的 `tilt_terminate`（`projected_gravity_b.z > -0.6`，
  瞬时总倾角 >53°、无持续时间窗）把合法 pitch 当摔：地形坡上限 26° /
  random_rough 局部 27.5° 叠加动态俯仰瞬态（上箱沿、落体、脊柱反扭）即
  越线。实测 `Episode_Termination/tilt` **0.60（v8.1@7700）/ 0.76（v6@8950）**
  ——六到七成 episode 提前截断，SIR success_rate 被钉死在 **0.019**（success
  要求活到 timeout），地形课程与速度学习全被饿死；GUI 观察 run 无一例真翻面、
  无一例肚皮瘫（`belly_contact_force` 全程 0.0000），tilt 全是假阳。
  v10 假设：删除终止后，摔倒状态留在 rollout 数据里——躺着的净收益已经为负
  （tracking 归零 + belly 罚 −0.5/步 + lin_vel_z 罚），起身梯度天然存在；
  2 m 尾链（yaw+pitch，80 N·m）+ 外趴腿具备地面撑翻的形态学条件（蜥蜴
  秒级自翻正；gecko 尾惯性翻正 Jusufi et al. 2008）。脊柱无 roll 自由度，
  180° 空中翻正不指望，地面撑翻可行。
- 相对 v8.1 的变更（**单变量**，reward/obs/DR/地形/网络/动作布局零变更）:
  - `versions/lizard/v10/lizard_params.yaml` = v8.1 全量拷贝 + `v10.tilt_terminate:
    null`（v3 段保留作 v1-v8 冻结记录）
  - `LizardRoughTeacherEnvCfg_V10(V8)`: `params_version="v10"`，
    `__post_init__` 里 `terminations.tilt = None`（yaml 驱动，可经 yaml 复原）
  - 注册 `Lizard-Rough-v10` / `Lizard-Rough-Play-v10`（runner
    `lizard_rough_teacher_v10`）
  - 静态闸: `rl_exp/tools/verify/check_terminations_v10.py`（无 sim：
    V10 tilt=None 且 time_out 存活、V8 冻结不动）
- 已知上限（用户拍板）: 起身动作不再被终止截断，但也不保证必然涌现——
  若物理/探索不支撑，躺到 timeout 是允许结局。**预注册反 hack**：probe 若见
  `belly_contact_force` 持续 >0 且 tracking 高（仰面爬行净收益 1.5−0.5>0），
  升 `belly_contact_force` 权重（v5 yaml 段，非本版新增项）。roll 罚被否决：
  重复计费 + 专收翻身过路费（起身必穿高 roll 区，belly 罚此时不触发）。
- 版本纪律: v8.1 已训（7700/15000 iters 判废终止，2026-09-09 用户手动 kill，
  ckpt 7700 留档）→ 配方行为变更开新版本。**v9 空号保留给断腿协议**
  （重基 v8，提案态，见 `..\v9\PLAN.md`），故跳号 v10（versioning.mdc §A）。
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v10 --max_iterations 15000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v10/
- 验收:
  1. `Episode_Termination/` 只剩 `time_out`（tilt 词条消失），占比 → 1.0
  2. success_rate 离开 0.019 地板，terrain_levels 继续爬
  3. `belly_contact_force` 保持 ≈0（持续 >0 且 tracking 高 = 仰面爬行 hack，
     触发预注册反制）
  4. track_lin_vel 回升（v8.1 终值 ~0.79 为基线）
  5. 观察项（非闸）：GUI/eval 摔倒后数秒内自行起身行为是否涌现
- 结果回填: （训练后补：reward 曲线读数 / success_rate 走势 / eval 跑分表 / 结论）
- 结论: （一句话，训练后补）
