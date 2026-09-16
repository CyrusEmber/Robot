# v12 — Miki S8 复位/观测鲁棒性包（reset & observation robustness）

> 状态：提案（未冻结）。开训前必看地形（isaaclab-pretrain-check）+
> `teacher_smoke_v3.py` 式冒烟（obs 维度/有限性）补跑。

## 修订：

- v12 初稿（2026-09-10，用户拍板开 v12 + r_slip 回 −0.003）。

## 1. 目的

2026-09-10 对照 Miki et al. 2022 S8 的审计发现三处缺口（`papers/miki-perceptive-locomotion/detail.md`
L62-68 为对照底本）：

1. **关节初值/速度 reset 随机缺失**——stock `reset_robot_joints` 是 scale 型
   （0.5–1.5 倍默认姿态），本 rig 默认姿态全零 → 永远零，静默 no-op。
2. **足底摩擦偶发调低缺失**——摩擦只有 startup 桶化抽样 [0.7, 1.0]，
   无 per-episode 低摩擦尾部。
3. **高度采样噪声模型整体缺失**——teacher 线为特权设计（刻意干净环扫描）。
   用户拍板（2026-09-10）：**不做学生蒸馏，teacher 即最终策略**，
   噪声直接上 teacher actor 的 extero 组。

同批一项奖励回退：r_slip −0.03 → −0.003（v8.1 的 ×10 升级从未在干净
步态配方下探针过；用户拍板回原档，见 §6）。

另：审计修正——**机体姿态/速度 reset 随机其实一直存在**（stock 基类
`EventsCfg` 自带 pose x/y ±0.5 m、yaw ±3.14、六轴速度 ±0.5，teacher 线
继承至今）。本版只是把范围搬进 yaml 变成可调，无行为变化。

## 2. 设计

全部旋钮在 `versions/lizard/v12/lizard_params.yaml` 的 `v12` 段（SSOT）。

### 2.1 关节初始状态随机（`reset_randomization.joints` / `joint_velocity`）

三个 reset 事件（`reset_joints_legs/feet/spine`，func=
`isaaclab.envs.mdp.events.reset_joints_by_offset`，软限位自动 clamp）：

| 组 | position 偏置 [rad] | 共同速度偏置 [rad/s] |
|---|---|---|
| legs（haa/hfe/kfe） | ±0.2 | ±0.5 |
| feet（foot） | ±0.1 | ±0.5 |
| spine（chest/neck/tail） | ±0.1 | ±0.5 |

数值为估值（论文无数字）→ ablation knob。stock scale 型 term 置 None。

### 2.2 基座姿态/速度范围 yaml 化（`base_pose_range` / `base_velocity_range`）

默认值 = stock 继承值（见 §1 审计修正）。纯暴露，不改行为。

### 2.3 足底摩擦偶发调低（`friction_dip`）

`teacher_mdp.FootFrictionDipTerm`（reset 事件，类式）：每次 reset 以
`p_dip=0.1` 抽中 → 该 env 全部脚部 shape 的静摩擦重抽
`static=[0.05, 0.3]`，动摩擦 = ratio∈[0.7,1.0] × 静。同一调用直写
`foot_friction_truth` 特权 obs 缓存（同 body 解析序，特权真值不撒谎）。

`ponytail:` 天花板：CPU get/modify/set per dip step（stock PhysX material
路径同级成本；4096 env ~4 reset/步、p=0.1 时大多数步会触发一次）。
升级路径 = GPU 侧 material 写入（profiling 显示成本再动）。

### 2.4 高度环噪声（`height_noise`，Miki S8 噪声模型）

- **事件** `sample_ring_noise`（reset）：每 episode 抽工况
  nominal/offset/noisy = 60/30/10；每脚 per-episode 单位正态偏置 `w`
  （存未缩放值）；`mid_fired` 标志复位。
- **观测项** `NoisyFootRing` 替换 4 个环扫描 term 的 func（名字/顺序/
  维度 208 不变 → obs 契约、网络、UE 导出全不动）：
  - nominal：干净；
  - offset：+ `w`（位姿漂移/可变形地形语义）；
  - noisy：+ `w` + 每脚每步 ε_f + 每点每步 ε_p + 间歇离群值替换
    （outlier_prob，替换值 ∈ outlier_range）；
  - **中途重抽**：episode_length_buf 过半且未抽过 → 重抽工况与 w（论文
    "开头与中途各抽一次"）。
  - 幅度 = σ × `ck_value`（c_k，见 §4 偏差 3）。

| 参数 | 默认 | 依据 |
|---|---|---|
| ratios | [0.6, 0.3, 0.1] | 论文 S8 逐项 |
| sigma_w | 0.15 m | 估值（论文 z 向量未印全）→ ablation knob |
| sigma_f | 0.05 m | 同上 |
| sigma_p | 0.02 m | 同上 |
| outlier_prob | 0.02 | 同上 |
| outlier_range | [-1, 1] m | = 环扫描 clip 窗 |

### 2.5 r_slip 回退（v5 段副本）

`v5.r_slip.weight`：−0.03 → **−0.003**（用户拍板 2026-09-10）。
v8/v10/v11 冻结副本保持 −0.03 不动。

## 3. 偏差声明（相对 Miki，有意为之）

1. **噪声上 teacher 而非 student**——无蒸馏管线（用户拍板）。priv 组
   （真速度/接触/法线/摩擦/外力）保持干净——actor 同时看带噪 extero 与
   干净 priv，鲁棒性目标限"高度感知"通道。
2. **论文的采样点横向偏移 (x_p, y_p) 不建模**——静态 ray pattern，
   改动需 per-point ray 起点运行时重写，成本不成比例。
3. **c_k 代替 c_sk**——论文噪声幅度由 student 课程的线性 c_sk 放大；
   本仓复用既有 c_k 指数退火（同向：小→全）。已知副作用：robust eval
   前 ~百步内噪声/DR 幅度仍处退火早期（与既有 _ck DR wrapper 同语义）。
4. **单一 σ 集合服务全部四脚**——论文 z ∈ R^{8×4} 每腿独立。
5. **关节/基座/dip 随机不挂 c_k**——初始化抖动与偶发事件量级温和；
   需要时是 yaml+wrapper 的小改。

## 4. 机器闸门同步（必须同 commit）

- `play_utils.DR_EVENT_NAMES` + `ablation_harness/components/dr_controller._DR_EVENT_NAMES`
  同步加 `foot_friction_dip`、`sample_ring_noise`（check_dr_parity 强制同步；
  PLAY / nominal eval → 环干净、无 dip；robust eval → 全包 + 钉种子）。
- `check_dr_parity.py` ALLOWLIST +5 条 teacher-only wiring（v12 注释组）。
- `check_obs_layout.py` v12 段：组/序/维度不变断言 + 全部新事件/obs 参数
  ↔ yaml 一致 + r_slip=−0.003 + ck 步数一致性。
- `test_v12_noise.py`（run_offline_checks [13/13]）：工况比率/三层噪声/
  outlier/foot_index 列选/中途重抽/c_k 缩放/无事件干净回退。
- 注册 `Lizard-Rough-v12`(+Play)，runner `experiment_name =
  lizard_rough_teacher_v12`（一版本一日志目录）。

## 5. 验收

1. 离线闸门 13/13 绿（含 check_version_docs 四件套）。
2. venv `py_compile` 全部改动文件。
3. 开训前：`isaaclab-pretrain-check` 看地形；smoke（TRAIN 段，参照
   teacher_smoke_v11.py 待办同款）确认 obs 381 维、有限、环值非全零。
4. 训练后（回填 NOTES）：`Curriculum/joint_sir/*` 正常爬升不被噪声压死；
   extero 编码器输入分布随 c_k 增宽；nominal/robust eval 分差 = 噪声
   鲁棒性溢价的读数。

## 6. 决策记录

| 日期 | 决策 | 来源 |
|---|---|---|
| 2026-09-10 | 开 v12（不并入 v11，保 v11 单变量纯净） | 用户拍板 |
| 2026-09-10 | r_slip 回 −0.003 | 用户拍板 |
| 2026-09-10 | 不做学生蒸馏，噪声直接上 teacher actor extero | 用户拍板 |
| 2026-09-10 | 噪声幅度挂既有 c_k（不另开 c_sk 线性 ramp） | review 定案 |

## 7. 训练命令

```bash
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v12
```
