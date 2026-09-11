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
- 结果回填（2026-09-11，ckpt `model_14999.pt`，iter 14999/15000 跑满；数据源
  `tb_scalars.csv` 151 点/tag + `probe_run.py` 读 tfevents，均无 sim）：

| # | 验收项 | 实测 | 判 |
|---|---|---|---|
| 1 | `Episode_Termination/` 只剩 time_out，占比 → 1.0 | 该目录下**只有** `time_out` 一个 tag（tilt 消失）；0.012（iter 0）→ **1.0000** | ✅ |
| 2a | success_rate 离开 0.019 地板 | 0.048 → **0.135**（峰值 0.299） | ✅（7× 地板，绝对值仍低） |
| 2b | terrain_levels 继续爬 | 首 4.54 → 末 **4.05**，峰 4.63（约 60% 处见峰，末段回落） | ❌ 未爬升 |
| 3 | belly ≈ 0（反仰面 hack） | 权重项 max **0.0** / min −0.045（偶发轻触）/ 末 −2.5e−6 | ✅ |
| 4 | track_lin_vel 回升（v8.1 基线 0.79） | 0.002 → **1.134**（峰 1.274，EP 线性核上限 1.5） | ✅（1.4× 基线） |
| 5 | 观察项：摔倒后自行起身 | `mean_episode_length` 满 **1000**（20 s 满长，无提前收局）→ 无「翻倒即终结」路径；但起身**未被直接观测** | ⬜ 未验证 |

- 口径警告：② 的 `terrain_levels` 在 SIR 里是**粒子加权后的难度均值**，不是「最高能爬
  档」；且它 iter 0 就 4.54（冷启动即非最低档），"爬升"判读要看趋势而非绝对值。
- 同族量级对照（**非单变量**——v5 与 v10 之间隔了 v6 判废、v7/v9 未启动、v8 资产换代，
  只作量级参考）：v5 跑满 15000 iter 末值 terrain_levels 4.11 / 峰 5.75、track_lin
  1.359 / 峰 1.400、success 0.033 / 峰 0.121。→ v10 的 success 是其 4 倍，tracking 略低
  （1.134 vs 1.359），地形难度峰值明显更低（4.63 vs 5.75）。
- 附带发现（`DIAGNOSE.md`，固定本 ckpt）：零命令 10 s 全程**非四脚着地**——`rl_foot`
  0 帧受力、稳态高出落地基线 15 cm，`lf_foot` 扛 52% 体重；tilt 与 eval 几何判据
  均看不见（eval 无脚接触项）。
- 结论: **半通过**——「删 tilt 终止 → 课程不再被饿死」的假设在终止占比与成功率上兑现
  （time_out 1.0、success 0.048→0.135/峰 0.30、tracking 0.002→1.13 高于 v8.1 的 0.79
  基线），belly 恒 0 无反 hack；但 **terrain_levels 未继续爬升**（4.54→4.05）、成功率
  绝对值仍低、且静止期支撑退化为 2–3 脚站。配方明确胜于判废的 v8.1，但不足以称问题
  解决：课程爬升瓶颈留 v11（联合粒子地形课程）验证，支撑退化留扰动恢复测试
  （本轮未覆盖）。
- 未覆盖（不判入验收）: robust 级扰动（4 m/s 踢 + DR）、更高速度、连续窄踏面（0.7 m
  金字塔楼梯）；摔后自行起身的显式测量。
