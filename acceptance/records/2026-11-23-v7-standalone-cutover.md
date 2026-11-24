# Lizard2 v7 显式实验入口切换

把现有圆足 v7 切到显式机体和实验文件，验证同一策略换入口后的行为以及新 Run 的训推接线。

权重位于 Isaac Lab 根下 `logs/rsl_rl/lizard2_v7/2026-11-03_17-07-29/model_5999.pt`，旁边保留实测接口签名。退网后评测位于该 Run 下 `evaluation/2026-11-23_11-09-10_55396241/`。旧入口对照和首帧证据位于本仓 `rl_exp/out/v7_refactor_eval/36016876/` 与 `rl_exp/out/v7_play_review/d96a6b14/`。

PLAY 以 0.5 m/s、seed 123 对比，首帧 90 维观测和首步 26 维动作逐值相等。`locomotion_eval_v3` robust 对照中，新旧入口都启用了相同的观测噪声和离地测距，归档标签里的原旧入口仅按倾角计跌倒。统一工况下，72 个环境的全局、分地形、分窗口和恢复指标逐项相同。平地跟踪成功率 74.04%，跌倒率 25.00%。离地高度采到 43,186 个有效帧，另有 10,451 个有效控制帧缺少射线命中。九段各 500 帧，每段抽验五帧。0.5 和 1.5 m/s 下机身基本保持朝向，3 m/s 片段可见机身朝向变化。三档峰值前向位移分别约 4.90、14.68、27.29 m，与旧录像一致。抽帧覆盖姿态和画面完整性，瞬时接触仍需逐帧检查。

采纳显式入口，沿用原 v7 权重。一次 PPO 更新产生的 `model_0.pt` 仅用于接线验证。旧流程从 `archive/pre-refactor` 复读。

## 退网加固后的复核（2026-11-23 18:57）

源码锁定 `5b9bf541d27f`（`git_rev_lizard` 记为该值），`eval.cmd --ckpt .../2026-11-03_17-07-29/model_5999.pt --protocol locomotion_eval_v3 --exp rl_exp/lizard2_v7.py` 退出码 0，产物在该 Run 下 `evaluation/2026-11-23_18-57-14_edd6c7dc/`（`metrics/eval.json`、九段录像 `video/matrix.json`）。

与 `evaluation/2026-11-23_11-09-10_55396241/`（`git_rev_lizard` `89178065fdec`）逐项相等：全局 `success_rate` 0.7677162885665894、`fall_rate` 0.1805555522441864、`lin_mae_mps` 12.051260948181152、`ang_mae_radps` 0.4399124085903168、`energy_per_m_j` 1050.36181640625、`terrain_completion_mean` 0.9306706322564019；`segments`、`terrains`、`recovery`、`terrain_evidence` 亦全等。动作 scale/clip 由 `lizard2_round_feet.ACTION_SCALE`/`ACTION_CLIP` 提供后逐关节与重构前字面量相等（16 腿 + 10 脊，零差异）。

`conditions.interface_signature` 与 `model_5999.pt.interface.json` 完全相等，含 `joints` 顺序：该 sidecar 记的是 Isaac 关节序（`chest_yaw_joint`、`tail1_yaw_joint` 开头），既非 URDF 文档序也非 `ACTION_JOINTS` 序，因此旧白名单推导与新推导落到同一结果。

`conditions.experiment.config_check` 为 `{"status": "unavailable", "reason": "resolved_cfg.yaml not found"}`：该 Run 无 `provenance.json`/`resolved_cfg.yaml`，漂移比对按不可用记录而未阻断。

相对旧产物只有两处差异，均不影响指标：删除 `report_only` 三个恒为 `null` 的死字段（`body_tail_coordination`、`foot_support_and_swing`、`non_foot_support`），以及 `conditions.runtime` 不再写 `device_declared` / `num_envs_declared`。这两个声明字段随 `record.json` 一起退网——评测只写 `eval.json`，`ablation_harness/record.py` 的状态机已无生产者，仅 `checkpoint_digest` 仍被三个诊断探针使用。

录像只核到九段与一格 grid 文件齐全，逐帧姿态与瞬时接触未复核。
