# Lizard 奖励用途总表（家族级 SSOT）

> **定位**：奖励的"为什么"——每个 term 买什么行为、收什么税、在哪些版本生效。
> 权重数值的真源是代码与 yaml（本表是镜像，冲突以代码为准）：
> stock 项 = 框架基类 `velocity_env_cfg.py::RewardsCfg`；teacher 覆盖 =
> `rl_exp/tasks/teacher_env_cfg.py`；数值 = `versions/lizard/vN/lizard_params.yaml`。
> 论文对应：Miki et al. 2022 S7（`papers/miki-perceptive-locomotion/detail.md`）、
> Cheng et al. 2023 Eq.2（`papers/extreme-parkour/detail.md`）。
> 姊妹契约：obs 布局见 [OBS.md](OBS.md)（同款约定——语义镜像，数值真源在代码）。

## 一、总表（v5 当前生效集）

| term | 公式（每步） | 权重 | ×c_k | 版本 | 一句话用途 |
|---|---|---|---|---|---|
| `track_lin_vel_xy_lin` | `1.5·min(⟨v̂_cmd,v_yaw⟩,\|v_cmd\|)/max(\|v_cmd\|,0.1)` | +1.5 | 否 | v5 | **主收入**：跟踪速度。站立=0、倒退<0、超速封顶（EP 核，断白嫖） |
| `track_ang_vel_z_exp` | `0.5·exp(−\|ω_z−ω_cmd\|²/0.25)` | +0.5 | 否 | 全部 | 转向跟踪（次收入） |
| `foot_clearance`(r_fc) | 负 hinge：swing 脚净空 < 0.2 m 时罚 | **−0.003**（v3/v4 曾 +0.003 挂反） | 否 | v3+ | **反拖脚**：摆动脚必须抬过脚下地形 0.2 m |
| `feet_slide`(r_slip) | `−Σ_{接触脚}\|v_f\|²` | −0.003 | **是** | v5 | **反划脚**：脚踩地就不许横移——逼"先抬再走" |
| `belly_contact_force` | `−0.5·‖F_base‖/706` | −0.5 | 否（恒权） | v5 | **防趴窝**：肚皮承力按体重比例连续罚（防御项） |
| `undesired_contacts`(r_co) | `−Σ` 接触计数（力>1N 的 body 数） | −1.0 | **是**（v5 起） | 全部（body 列表分版本） | 腿部碰撞税：v5 前罚 base+全腿+脊柱；v5 只罚大腿/小腿(hfe/kfe) |
| `lin_vel_z_l2` | `−2.0·v_z²` | −2.0 | 否 | 全部 | 禁蹦跳：垂直速度税（贴地行走） |
| `ang_vel_xy_l2` | `−0.05·(ω_x²+ω_y²)` | −0.05 | **是** | 全部（v3 起挂 c_k） | 禁翻滚/侧倾：横滚俯仰角速度税 |
| `dof_torques_l2` | `−1e-5·Στ²` | −1e-5 | **是** | 全部（v3 起挂 c_k） | 能耗税：大扭矩亏钱（也压关节饱和） |
| `dof_acc_l2` | `−2.5e-7·Σq̈²` | −2.5e-7 | **是** | 全部（v3 起挂 c_k） | 平滑税：猛甩关节亏钱（保护硬件+动作自然） |
| `action_rate_l2` | `−0.01·Σ(a_t−a_{t−1})²` | −0.01 | 否 | 全部 | 抖动税：相邻动作差分（输出平滑） |
| `feet_air_time` | `Σ(air_time−0.5)·first_contact` | +0.125 | 否 | v0-v2（v3 删） | 长步奖励（迈大步）：v3 被 r_fc 替换（D2） |
| `flat_orientation_l2` | `−2.5·(g_x²+g_y²)` | **0**（禁用） | — | — | 姿态税：stock 关闭，姿态约束由 tilt 终止承担 |
| `dof_pos_limits` | 关节贴限位罚 | **0**（禁用） | — | — | 限位税：stock 关闭（限位由物理硬约束） |

## 二、按行为动机分组

### 收入侧（干活的报酬）
- **跟踪双核**：`track_lin_vel_xy_lin`（线）+ `track_ang_vel_z_exp`（角）是唯二
  正收入。v5 的线跟踪从 exp 核换 EP 线性核是**反划脚核心**：exp 核在
  \|v_cmd\|<0.5 时站立白嫖残值（v3 实测白嫖出 success_rate 0.47），线性核
  站立一分不给——想挣钱只能真位移。
- `feet_air_time`（v0-v2）：为"迈大步"付钱。v3 删除（D2）：它与 r_fc 语义
  打架（一个奖空中时间、一个罚离地不足），且对"脚不离地划脚"无约束力。

### 步态时序税（v5 反划脚包）
- **`feet_slide` = 步态时序的执法者**：正常走路脚要么钉在地上（支撑相，
  不动）、要么抬起来飞（摆动相，随便快）——两态都不缴税。唯一被罚的
  形态是"踩着地蹭"= 划脚/打滑。这条是 v3 首跑"只有脚动身不动"的
  **直接对症药**（v3 缺失，划脚零成本）。
- **`foot_clearance`(r_fc)**：摆动脚离地不足 0.2 m 罚——与 feet_slide 成对：
  slide 罚"贴地蹭"，r_fc 罚"抬太低地飘"。两税夹出"干脆利落的抬脚-落步"。
- **`belly_contact_force`**：恒权防御项（v3 症状不含趴窝，但奖励经济学改版
  后新局部最优可能出现肚皮承重）——按受力连续罚，平躺=满税，正常步态=0。
  恒权不随 c_k 退火：趴窝在任何训练阶段都不能变免费。

### 姿态与能耗税（stock 继承）
- `lin_vel_z_l2`（跳的税）+ `ang_vel_xy_l2`（翻滚的税）：压出贴地稳定行走。
- `dof_torques_l2` + `dof_acc_l2` + `action_rate_l2`：三连平滑税，防
  高频抖动与蛮力解。挂 c_k（v3 起）= 训练后期逐渐收紧（先学动、再学雅）。

### 接触税
- `undesired_contacts`：罚"不该碰地的地方碰地"。**body 列表是版本差异点**：
  v0-v4 罚 base+haa+hfe+kfe+全脊柱（宽税基，但 base 在 v3.6 删终止后只吃
  这条轻税）；v5 缩到 hfe/kfe（论文 r_co 原文只罚大腿/小腿），base 移交
  belly 专项、脊柱/haa 豁免（脖子尾巴拖地暂不罚，观察首跑再定）。

## 三、c_k 惩罚课程（v3+，`curriculum_ck`）

`c_k = 0.2^(0.98^iter)`，从 0.2 单调爬向 1（~140 iters 过 0.9）。
挂在上面的税：`dof_acc_l2` / `dof_torques_l2` / `ang_vel_xy_l2`（v3 起）
+ `feet_slide` / `undesired_contacts`（v5 起）。

**设计意图**：起步阶段税打 2 折——先允许毛糙动作把"能动"学出来；
步态成形后税率升到全价，逼出省力平滑的成熟步态。
**反例教训**：v3 把 `undesired_contacts` 留在恒权（没挂 c_k），论文里它
是挂的——恒权重税 + 早期探索期 = 趴着别动最省税。v5 对齐论文。

**不挂 c_k 的项**（设计上区分）：跟踪收入（收入不随课程打折）、
`belly_contact_force`（防御项永不打折）、`action_rate_l2`（输出平滑从第一步
就要）、`foot_clearance`（r_fc 门槛低、无需退火）。

## 四、奖励经济学速查（v3 首跑实测，每步量级）

| 项 | v3 实测均值 | 备注 |
|---|---|---|
| track_lin_vel_xy_exp | +0.50 | 站桩白嫖基线（一半命令低速） |
| track_ang_vel_z_exp | +0.36 | 转向白嫖（不转也不大亏） |
| dof_torques_l2 | −0.39 | 最大单项税 |
| action_rate_l2 | −0.33 | 平滑税可观（26 关节） |
| dof_acc_l2 | −0.13 | |
| undesired_contacts | −0.02 | 宽税基但几乎不触发（趴着稳） |
| foot_clearance | ~0 | 符号挂反 + 脚没离地，双死 |

**读法**：v3 的经济结构里"完全不动"净收入 ≈ +0.4/步且零风险；v5 改版后
"不动"收入 = 0（线性核）+ 趴地税 + 划脚税——正收益路径只剩真走路。

## 五、版本差异摘要

| 版本 | 奖励集差异 |
|---|---|
| v0-v2 | stock 全套 + `feet_air_time`；无 tilt/c_k/r_fc |
| v3/v4 | 删 `feet_air_time`，加 `foot_clearance`（**符号挂反 +0.003**）、tilt 终止、c_k 三税；base_contact 终止删除（v3.6） |
| v5 | 上述 + r_slip（平方式）、belly 受力罚、EP 线性核替换 exp 核、r_co 缩腿挂 c_k、r_fc 负号修正、命令 (0,3) 无速度课程 |

冻结配方的实际数值以各自 `versions/lizard/vN/lizard_params.yaml` 为准；
本表描述 v5 当前形态。改奖励 = 走 versioning 规则（已冻结开 vN+1，
提案态 vN.M 修订）。
