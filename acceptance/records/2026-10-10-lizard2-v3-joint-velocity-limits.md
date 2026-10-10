# lizard2 v3 PLAY 窗关节速度对 URDF 自带上限：11/20 腿关节 p99 越限、最坏 2.66×（2026-10-10）

## 适用范围

`work/active/lizard2-family-landing.md` ④ 要的那份读数：**有效限速要不要启用**。本记录给两条输入——
策略在 PLAY 窗里实际用到的关节速度（现测），以及求解器当前持有的上限（引既有读数，不重测）。
不改配方 / 资产 / 协议 / 闸门；不训练；**不作出启用与否的决定**（那是 ④ 的出口）。

被读对象：`Lizard2-Flat-Play-v3` + `model_5999.pt`
（sha256 `954fb332bdd7c56d0ba6cb8bb7faec443006bb1a62cd9b619855cd664b7ae1aa`）。

## 验收条件

1. 关节速度必须来自**真 rollout 的逐帧记录**，不是估计、也不由 effort 反推（v1 已撤回那条，
   `rl_exp/versions/lizard2/main/v1/PLAN.md:133`）。
2. 上限的"求解器持有值"与"资产声明值"分开报：两者都不是策略读数的替代品。
3. 读数必须写明窗口（几个速度、几秒、几个 env），且只称它就是这个窗口的读数。
4. 单 ckpt / 单 seed / 每档 1 env ⇒ 不得据此声称分布或稳定性。

## 结果

### ① 覆盖与窗口

`gait_probe.py --task Lizard2-Flat-Play-v3 --checkpoint <model_5999.pt> --speeds 0.5,1.5,2.8 --seconds 8`：
3 envs（一速度一 env）、400 帧 × 0.02 s = 8 s、seed 123。报告逐帧导出 20 个腿关节
（hip / haa / hfe / kfe / foot × 4 腿）与 10 个脊柱关节的 `target` / `actual` / `vel`。
下表取三档中**最大**的 p99（每档 400 帧排序取第 396 个）与峰值。

### ② 求解器持有的上限（引 2026-10-09 读数，本记录不重测）

`acceptance/records/2026-10-09-lizard2-drive-readback-audit.md`：30/30 关节的 `joint_vel_limits` 都是
**5.939047009418473e+36**（PhysX"无上限"）；yaml 声明的 10/6/4 被本 fork 丢弃，URDF 自带的 8/6/4
**也没有**成为驱动上限。⇒ 当前运行里**没有任何有效速度限速**。

### ③ 资产声明值（`rl_exp/lizard2_candidate/lizard2_candidate.urdf`，30 关节全声明）

腿 8 rad/s、脚 6 rad/s、脊柱 4 rad/s。这三个值从未进过驱动，只代表"资产自己说能转多快"。

### ④ 实测：p99 越限的 11 个腿关节

| 关节 | p99 [rad/s] | 峰值 [rad/s] | URDF 限 | p99 / 限 |
|---|---|---|---|---|
| `rf_kfe_joint` | **21.26** | 24.54 | 8 | **2.66** |
| `lf_kfe_joint` | 12.62 | 17.53 | 8 | 1.58 |
| `rl_hfe_joint` | 12.43 | 12.84 | 8 | 1.55 |
| `lf_hfe_joint` | 12.01 | 13.68 | 8 | 1.50 |
| `rf_hip_joint` | 11.66 | 15.34 | 8 | 1.46 |
| `rr_haa_joint` | 11.42 | 12.05 | 8 | 1.43 |
| `lf_foot_joint` | 8.21 | 17.27 | 6 | 1.37 |
| `rl_haa_joint` | 10.14 | 10.97 | 8 | 1.27 |
| `rf_hfe_joint` | 9.68 | 15.39 | 8 | 1.21 |
| `lf_haa_joint` | 8.78 | 11.77 | 8 | 1.10 |
| `rf_foot_joint` | 6.17 | 11.17 | 6 | 1.03 |

`rf_kfe` 的越限在最高速档最重：p99 按档（0.5 / 1.5 / 2.8 m/s）为 3.14 / 11.73 / 21.26。

### ⑤ 实测：p99 未越限的 9 个腿关节

| 关节 | p99 [rad/s] | 峰值 [rad/s] | URDF 限 | p99 / 限 |
|---|---|---|---|---|
| `rf_haa_joint` | 7.42 | 8.98 | 8 | 0.93 |
| `rr_hfe_joint` | 7.43 | 12.85 | 8 | 0.93 |
| `lf_hip_joint` | 6.08 | 8.00 | 8 | 0.76 |
| `rr_hip_joint` | 5.61 | 8.98 | 8 | 0.70 |
| `rl_foot_joint` | 4.18 | 17.60 | 6 | 0.70 |
| `rr_kfe_joint` | 5.20 | 7.59 | 8 | 0.65 |
| `rl_kfe_joint` | 4.90 | 8.86 | 8 | 0.61 |
| `rl_hip_joint` | 4.11 | 6.31 | 8 | 0.51 |
| `rr_foot_joint` | 2.49 | 10.53 | 6 | 0.41 |

注意 `rl_foot_joint` 的峰值 17.60 远超它的 6，但 p99 只有 4.18 ⇒ 它的越限是**冲击型**（少数帧），
与 `rf_kfe` 的持续性越限不是一回事——这正是"用 p99 不用峰值"的理由。

### ⑥ 脊柱（限 4）：2/10 越限

| 关节 | p99 | 峰值 | 关节 | p99 | 峰值 |
|---|---|---|---|---|---|
| `tail2_pitch_joint` | **5.91** | 8.07 | `tail1_pitch_joint` | 3.61 | 5.04 |
| `tail1_yaw_joint` | **5.59** | 5.78 | `chest_pitch_joint` | 3.46 | 3.91 |
| `tail3_pitch_joint` | 3.71 | 6.71 | `tail2_yaw_joint` | 3.13 | 5.53 |
| `tail3_yaw_joint` | 2.48 | 3.42 | `neck_pitch_joint` | 2.44 | 4.21 |
| `neck_yaw_joint` | 1.77 | 2.86 | `chest_yaw_joint` | 1.76 | 2.27 |

**汇总**：腿 **11/20**、脊柱 **2/10** 的 p99 超过 URDF 限值；最大比值 **2.66×**；峰值最大 24.54 rad/s。

### ⑦ 这份读数说明什么、不说明什么

- **说明**：策略的步态确实依赖"超过资产声明上限"的关节速度，而且不是个别冲击帧——
  中高速度档里整段都在越限。
- **不说明**：URDF 那三个数是对的。它们从未进驱动、也从未被任何实验校准；
  "8 rad/s" 可能只是导出占位值。要把"限到 8 会变差"变成结论，需要**限速臂的真跑对照**
  （同配方、同 ckpt，限速开/关两臂），本记录没有这个对照。
- **也不说明**：峰值可持续。峰值含落地冲击单帧，判决策料用 p99。

## 证据引用

```bat
:: 本次真跑（cwd <REPO>；报告落 out/，机器本地、gitignore 挡住）
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\diagnose\gait_probe.py --viz none ^
  --task Lizard2-Flat-Play-v3 ^
  --checkpoint E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50\model_5999.pt ^
  --speeds 0.5,1.5,2.8 --seconds 8 --out rl_exp\tools\diagnose\out\gait_probe\gait_v3.json

:: 求解器持有值（重测会起仿真；上一次读数见记录）
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\check_actuator_budget.py ^
  --drive-audit --task Lizard2-Flat-Play-v3 --json "%TEMP%\drive_audit_lizard2_v3.json"
```

- 上限口径的原始读数：`acceptance/records/2026-10-09-lizard2-drive-readback-audit.md`。
- "不得由 effort/velocity 反推速度上限"：`rl_exp/versions/lizard2/main/v1/PLAN.md:133-135`。
- 事项：`work/active/lizard2-family-landing.md` ④。

## 未覆盖边界

1. **3 env / 8 s / 单 seed / 单 ckpt**：这是"这一颗 ckpt 在这三档上"的读数，不是分布；
   每档只有 1 个 env，故分位数的样本量是 400 帧。
2. **报告里的数列四舍五入到 5 位小数**，本表的分位在此之后算——对本表的量级无影响，
   但复算请从同一份报告取。
3. **无限速臂对照**：没有"限到 URDF 值"的第二次真跑，故本记录只说"会裁掉多少"，
   不说"裁掉之后策略会怎样"。
4. **`foot`/`spine`/`leg` 三个上限值不同**（6 / 4 / 8），已逐关节标出，别按组记。
5. **不含 armature / 摩擦影响**的讨论：速度快慢与执行器能否跟上是两件事（后者见
   `acceptance/records/2026-10-09-lizard2-leg-joint-inertia-and-gain-caliber.md`）。
