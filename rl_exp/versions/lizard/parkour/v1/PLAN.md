# Parkour v1 — 切片：跑 / 爬 / 跳 三专家 → DAgger 蒸馏 → RL 微调

> 状态：**初稿（未冻结）**。本文件 = 本版本方案 SSOT；路线层与决策记录见
> [../PLAN.md](../PLAN.md)；论文可复现细节（reward 全表 / 噪声模型 / 网络结构）
> 见仓根 `papers/parkour-in-the-wild/detail.md`，本文只写实现决策不抄论文。
> 开新版本流程继承 `.codemaker/rules/versioning.mdc` §A；红线：已发布 term
> 实现永不改语义。
>
> 修订：v1 初稿 2026-09-04
> 修订：v1.1 2026-09-04（用户拍板：撤回预加 belly 罚（paper 字面无此项，
> teacher 无补丁先跑家训）；reward 表修正——Table 2 是微调期表，专家期
> gate="none"、M5 切回论文字面（挂账 H5/H6））

## 1. 目的与范围

复现论文核心范式（多专家蒸馏 + RL 微调 > 分层/单策略 RL）于 lizard：

- **3 专家**：跑（平地+坡）/ 爬（楼梯上+下）/ 跳（gap 跑跳，probe gate）
- **1 蒸馏**：DAgger 在线蒸馏 → 单深度感知学生
- **1 微调**：RL 微调（特权 critic + critic 预训练）恢复并超越专家
- 跳跃 probe 不过 → 双专家（跑+爬）继续，管线结论不受影响

不做（本版出界）：9 技能全量、扫描地形导入、分层/VAE 对比、UE 部署。

## 2. 位置任务基建（M1）

### Command term（新，`parkour_mdp.py`）

- 指令 (r\*, ψ\*, t\*)：目标位置（地形坐标系）、目标朝向、剩余时间预算。
- resample：到达判定成功 / t\* 耗尽 / termination 时重采；t\* 从距离+期望速度
  推出的范围采样（M1 定标，初值 [dist/1.5, dist/0.5] s 上下夹）。
- 到达判定 S_L = 1(‖r_xy−r\*_xy‖ < 0.25 m)·1(‖ψ−ψ\*‖ < 0.5 rad)（论文口径）。

### Reward（移植论文 Table 2，论文权重起步）

| 项 | 口径 | 权重 |
|---|---|---|
| Track position | 1_{t\*≥1→none}(1−0.5‖r_xy−r\*_xy‖) | 10 |
| Track heading | 同上门控 | 5 |
| Joint velocity / Torque / 越限 / Base acc / Feet acc / Action rate / Feet force / Collision | 论文值（见 papers detail.md Table） | 论文值 |
| Don't wait | 1(‖v_b‖<0.2) | −1 |
| Stand at target | S_L‖q−q_d‖ | −0.5 |
| Termination | 倾角>135° 等 | −2e3 |

- **Table 2 是微调期 reward 表**：goal-oriented 行为来自蒸馏继承，`1_{t*<1}`
  末秒门控在微调语境合理。专家从零训练无蒸馏来源 → 专家期必须 `gate="none"`
  （必要偏差，M5 微调切回论文字面）。用户拍板 2026-09-04（纠正预加 belly 罚）。
- **无 belly 罚项（paper 字面）**：四层自带防线（Don't wait 罚慢蠕 / t\* 逼时效 /
  0.25m 到达半径逼精度 / 0.55m 台阶物理过滤拖行）。belly_contact_force（v5 形态）
  挂账 H5 待命，仅凭 M2 证据启用——家训先例：teacher 基线先跑无补丁。
- 正则项数值以论文为初值；v5 反划脚包经验仅按需叠加，单独列 diff 不混入论文表。

### 地形（M1 定标 + 预检，"先看地形再开训"）

| 专家 | 地形 | 定标来源 |
|---|---|---|
| 跑 | random_rough + slope | rough = v4 定标（间距 0.5m，噪声 (0.10,0.35)）；slope 坡度范围 M1 新定标（初值 5–25°，sprawled 侧滑风险 → 地形预检 gate） |
| 爬 | pyramid_stairs + pyramid_stairs_inv | v3.4 定标（台阶顶 0.55m，提脚包络 0.52m 边缘值），课程从低台阶起步 |
| 跳 | box gap（跑跳） | 新定标：初值 0.2–0.8m（体长 2m 可"桥跨"小沟，难度轴真实起点待 probe 标定） |

## 3. 跳跃 probe gate（M1.5，先证后用）

- **双口径**：站跳（reward=腾空高度）+ 跑跳（reward=腾空前向净空），各 ~2000
  iters 短跑，平地+沟条地形，无位置任务结构。
- **gate 判据（初值，可调）**：跑跳 eval 净空 ≥0.4m 或腾空 ≥0.2s（站跳仅参考
  不卡 gate）。
- 过 → 跳专家进 M3；不过 → 记录证据，双专家管线继续（用户拍板）。

## 4. 专家训练（M2–M3）

- 每专家 = 单地形 env cfg（继承家族基座，`params_version` 机制挂 parkour 线参数）
  + 位置任务 + 上表 reward + StagedCurriculumTerm（metric_name 换到达率口径）。
- 专家感知 = 特权：height_scanner（映射论文 elevation map 精细档）+ 特权段复用
  `teacher_mdp`（只增不改红线）。
- 网络 = `SplitEncoderModel` 现成（obs 三组机制不变）。
- 任务 id：`Lizard-Parkour-Run-v1` / `-Climb-v1` / `-Jump-v1`（+Play 对），
  runner `experiment_name = lizard_parkour_<expert>_v1`（一任务族一日录）。
- 训练顺序：Climb（M2，范式验证）→ Run → Jump（probe 过才开）。
- 验收线：各专家自有地形到达率 ≥95%（论文专家档 84.8–99.9）。

## 5. 蒸馏（M4）

- 学生感知：**Q2 终裁在 M3 末**（倾向 4× RayCasterCamera 48×32 深度，2 前 2 后，
  俯角 M1 冒烟实测——趴行构型必须看得见脚下近场）。
- 学生网络 `ParkourStudentModel`：每图 CNN(3conv+pool→2FC→64) → 拼 proprio →
  2×LSTM → 拼 proprio+指令 → 3FC ELU → 26 维动作；`class_name` 点路径注册。
- DAgger trainer（新，rsl_rl 外自研训练循环）：混合 obs 组 env（专家组+学生组
  同环境）→ 学生动作加零均值高斯噪声执行 → 专家同状态打标 → MSE。
  渐进降级：在线 DAgger 跑不通 → 离线 BC（存专家轨迹）先行验证学生网络。
- 噪声模型：论文 5 步（clip/边缘/Perlin 空洞/盲区列/模糊）做成 obs corruption。
- 验收线：蒸馏 vs 专家掉点表成型（论文对标 −10.4%；精度地形掉最狠属预期）。

## 6. RL 微调（M5）

- env：actor obs = proprio+depth；critic obs = +特权（obs_groups 非对称现成）。
- 稳定三件套：蒸馏 action noise 遗产 + 低初始 log_std + **critic 预训练**
  （冻结 policy 先训 critic，runner 扩展）。
- 微调地形 = 全专家地形混合 + 未见保留地形（random_rough 高难度）。
- 验收线：微调恢复到专家 ±5%（论文 +3.1%）；未见地形非零到达率。

## 7. 风险（本版增量；路线级风险见 ../PLAN.md §5）

| # | 风险 | 缓解 |
|---|---|---|
| P1 | 跳跃物理未知（扭矩/体重 ANYmal 档但 sprawled 构型反跳跃，大型 varanid 无跳跃先例） | M1.5 probe gate（先证后用，不过不进蒸馏） |
| P2 | 位置任务新作弊面（到点趴着刷分） | 三件套成对进；M2 观察 reward 分解曲线 |
| P3 | DAgger 自研循环工程量 | 渐进降级路线（在线→离线 BC） |
| P4 | RayCasterCamera 俯角/近场覆盖设计错 | M1 冒烟含近场覆盖验证（沟在脚前 0.3m 必须可见） |
| P5 | slope 侧滑（sprawled + 短胫） | M1 地形预检 gate，坡度课程从 5° 起步 |

## 8. 挂账

- H1：Q2 学生感知终裁（M3 末，RayCaster 深度 vs belief 复用）
- H2：UE 深度部署方案（SceneCapture vs LineTrace，部署阶段，见路线 PLAN §6-2）
- H3：下楼梯独立专家分支决策（M3，下行学崩才开）
- H4：gap 难度轴真实起点（probe 标定"桥跨"上限）
- H5：belly_contact_force 补丁待命（−1.0，v5 形态）——仅凭 M2 Run 专家
  快速滑行最优解证据启用，不预防性上（用户拍板 2026-09-04）
- H6：Track gate 两段式——专家期 "none"（必要偏差）/ M5 微调期切论文字面
  "t_star_lt_1"（Table 2 是微调表，行为来自蒸馏）
