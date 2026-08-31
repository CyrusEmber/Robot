# v2 —— teacher 特权 obs 补全（论文对齐版）

- 目的/假设: v1 特权信息不全。对照 Miki et al. 2022 论文特权表逐项补齐，
  让 teacher 上限更高、蒸馏目标更完整。**纯代码级结构变更，yaml 与 v1
  逐字相同**（DR 仍是 v1 的收窄值）
- 相对 v1 的变更（obs 266 → 308，任务 id `Lizard-Rough-v2`）:
  **版本差异机制**：`teacher_env_cfg.py` 的 `TEACHER_PRIVILEGED_SPEC`
  （v1 = 空集，v2 = 五个新 term）是版本差异唯一真源；基类 wire 全部 term
  后按 spec 剥离。v1 任务 id 常驻注册（`LizardRoughTeacherEnvCfg_V1`，
  obs 266）保证旧版本从工作树可复现。**纪律：term 实现只增不改**。
  新增 5 个特权 term（论文表项）：
  | term | 维度 | 实现 |
  |---|---|---|
  | `foot_contact_forces` | 12 | 接触传感器 net_forces_w 每脚 3 维力矢量（世界系） |
  | `foot_contact_normals` | 12 | `FootContactNormalsTerm`：每脚垂直射线 warp raycast 取地形法线（世界系，未命中=0；start_offset 0.5m / max_dist 2.0m，mesh 用 height_scanner 已注册的 /World/ground） |
  | `foot_friction` | 4 | 每脚静态摩擦系数（材质桶随机为 per-shape、startup 一次，首调读回缓存到 env 上） |
  | `thigh_shank_contacts` | 8 | `*_hfe`/`*_kfe` body 接触布尔（阈值 1N） |
  | `base_external_wrench` | 6 | `permanent_wrench_composer.out_force_b/out_torque_b`（base，body 系——即仿真真实施加的持续外力） |
  已有对齐项：contact states 4（`foot_contact_bools`）、airtime 4（`feet_air_time`）✓
- **存量偏差声明（决策 B：保留）**——两项 v1 已有、论文表没有的特权：
  真值速度 6（`base_lin_vel_true/base_ang_vel_true`；论文中 body velocity 在
  proprio 里）与逐 body 质量 27（`body_mass`；属 RMA/Lee 2020 系特权，非 Miki）。
  保留理由：超集特权只抬高 teacher 上限，student 蒸馏结构不变；跑出问题
  再回归论文血统。全表见 FAMILY.md「Teacher 特权 obs 布局」节
- 完整 obs 布局（尾部从后往前）: wrench 6 | thigh_shank 8 | friction 4 |
  normals 12 | forces 12 | mass 27 | air 4 | contact 4 | true_vel 6 |
  scan 135 | proprio 90（lin3+ang3+grav3+cmd3+jpos26+jvel26+act26）
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v2 --max_iterations 4000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher/
- 验收线: 沿用 v1（~1000 iters 内 feet_air_time>0；判死刑信号 reward 平+air≈0）
- 冒烟判读（teacher_smoke.py，PLAY 变体）: OBS_SHAPE (2, 308)；
  MASS_SUM≈72；FOOT_FORCES_Z 合计≈700N；FOOT_NORMAL_Z 平地≈+1；
  FOOT_FRICTION 4 值在 [0.5,1.5]（PLAY 无随机化=默认材质）；
  BASE_WRENCH=0（PLAY 关外力事件）
- eval 结果: （训练后回填）ablation_harness results/locomotion_eval_v1/，tag=v2
- 逐迭代曲线: （训练后导出）`python lizard_exp\dump_tb.py --log_dir <run目录> --out lizard_exp\versions\v2\tb_scalars.csv`
- 结论/下一步: （训练后回填）
