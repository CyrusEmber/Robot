# lizard2 v3 PLAY 窗关节速度对 URDF 自带上限：帧均口径 9/20 越限、最坏 1.53×（2026-10-10）

## 适用范围

`work/active/lizard2-family-landing.md` ④ 要的那份读数：**有效限速要不要启用**。本记录给两条输入——
策略在 PLAY 窗里实际用到的关节速度（现测），以及求解器当前持有的上限（引既有读数，不重测）。
不改配方 / 资产 / 协议 / 闸门；不训练；**不作出启用与否的决定**（那是 ④ 的出口）。

被读对象：`Lizard2-Flat-Play-v3` + `model_5999.pt`
（sha256 `954fb332bdd7c56d0ba6cb8bb7faec443006bb1a62cd9b619855cd664b7ae1aa`）。

> **勘误（2026-10-10，同日）**：本记录初版只给了一个口径——报告里的 `data.joint_vel`（帧末**瞬时**速度），
> 并据此称"11/20 越限、最坏 2.66×、整段越限"。复核时加了第二个口径（相邻导出帧位置差分 / dt，
> 即**帧均**速度），两者在远端两个关节类型上相差到 2.2× ⇒ 初版的计数与最大比值都偏高。
> 下表两口径并列，结论以帧均口径为准，初版读数保留在表里作为对照。原委：`data.joint_vel` 是帧末瞬时值，
> 子帧振铃会被它读成"关节速度"，而位置差分量的是这一帧里关节实际走了多快。

## 验收条件

1. 关节速度必须来自**真 rollout 的逐帧记录**，不是估计、也不由 effort 反推（v1 已撤回那条，
   `rl_exp/versions/lizard2/main/v1/PLAN.md:133`）。
2. 速度必须**写明口径**：瞬时（`joint_vel`）与帧均（位置差分）不是同一个量，越限计数随口径变。
3. 上限的"求解器持有值"与"资产声明值"分开报。
4. 单 ckpt / 单 seed / 每档 1 env ⇒ 不得据此声称分布或稳定性。

## 结果

### ① 覆盖、窗口与两个口径

`gait_probe.py --task Lizard2-Flat-Play-v3 --checkpoint <model_5999.pt> --speeds 0.5,1.5,2.8 --seconds 8`：
3 envs（一速度一 env）、每档 399–400 帧 × 0.02 s = 8 s、seed 123。报告逐帧导出 20 个腿关节
（hip / haa / hfe / kfe / foot × 4 腿）与 10 个脊柱关节的 `target` / `actual` / `vel`。

- **瞬时口径** = 报告里的 `..._vel`（`ArticulationData.joint_vel`，帧末值），p99 取每档排序第 396 个；
- **帧均口径** = 相邻导出帧 `actual` 之差 ÷ 0.02 s；
- 两口径对 30 个关节的比值：**22 个落在 0.85–1.12（同一件事）**，**8 个在 1.26–2.24**（`kfe` 刀片与 `foot`
  脚板这两类远端轻杆：子帧振铃被瞬时口径读到，位置差分读不到）。

### ② 求解器持有的上限（引 2026-10-09 读数，本记录不重测）

`acceptance/records/2026-10-09-lizard2-drive-readback-audit.md`：30/30 关节的 `joint_vel_limits` 都是
**5.939047009418473e+36**（PhysX"无上限"）；yaml 声明的 10/6/4 被本 fork 丢弃，URDF 自带的 8/6/4
**也没有**成为驱动上限。⇒ 当前运行里**没有任何有效速度限速**。

### ③ 资产声明值（`rl_exp/lizard2_candidate/lizard2_candidate.urdf`，30 关节全声明）

腿 8 rad/s、脚 6 rad/s、脊柱 4 rad/s。这三个值从未进过驱动，只代表"资产自己说能转多快"。

### ④ 帧均口径下越限的 9 个腿关节

| 关节 | 帧均 p99 | 瞬时 p99 | 峰值 | URDF 限 | 帧均 / 限 | 瞬时 / 限 |
|---|---|---|---|---|---|---|
| `rf_kfe_joint` | **12.20** | 21.26 | 24.54 | 8 | **1.53** | 2.66 |
| `rl_hfe_joint` | **12.23** | 12.43 | 12.84 | 8 | **1.53** | 1.55 |
| `rf_hip_joint` | **12.23** | 11.66 | 15.34 | 8 | **1.53** | 1.46 |
| `lf_hfe_joint` | 12.17 | 12.01 | 13.68 | 8 | 1.52 | 1.50 |
| `rr_haa_joint` | 11.44 | 11.42 | 12.05 | 8 | 1.43 | 1.43 |
| `rl_haa_joint` | 10.49 | 10.14 | 10.97 | 8 | 1.31 | 1.27 |
| `lf_haa_joint` | 8.81 | 8.78 | 11.77 | 8 | 1.10 | 1.10 |
| `rf_hfe_joint` | 8.65 | 9.68 | 15.39 | 8 | 1.08 | 1.21 |
| `rr_hfe_joint` | 8.29 | 7.43 | 12.85 | 8 | 1.04 | 0.93 |

越限集中在**髋/膝/踝的近端驱动关节**（hfe / haa / hip / kfe），最高速档最重
（`rf_kfe` 帧均 p99 按档 2.4 / 8.0 / 12.2）。

### ⑤ 两口径都未越限的 11 个腿关节（帧均 p99）

`rf_foot_haa` 7.63、`lf_foot_hip` 6.50、`lf_foot_kfe` 6.22、`rr_foot_hip` 5.62、`rf_foot_foot` 4.56、
`lf_foot_foot` 4.19、`rl_foot_kfe` 3.88、`rl_foot_hip` 3.70、`rl_foot_foot` 2.89、`rr_foot_foot` 2.86、
`rr_foot_kfe` 2.32。

**脚板四个关节（限 6）在帧均口径下全部未越限**（2.86–4.56）；它们在瞬时口径下有两个"越限"
（`lf_foot` 8.21、`rf_foot` 6.17）⇒ 那两条是振铃读数，不是脚板真的以 8 rad/s 在转。
`lf_kfe` 同理：瞬时 12.62 越限、帧均 6.22 不越（比值 2.03）。

### ⑥ 脊柱（限 4）：两口径一致，2/10 越限

`tail2_pitch` 帧均 **6.62**（瞬时 5.91）、`tail1_yaw` 帧均 **5.58**（瞬时 5.59）；其余 8 个帧均 ≤ 3.72
（`tail3_pitch` 3.72、`chest_pitch` 3.49、`tail2_yaw` 3.21、`tail3_yaw` 2.91、`neck_pitch` 2.55、
`chest_yaw` 1.90、`neck_yaw` 1.89）。脊柱无振铃（两口径比值 0.85–1.02）。

### ⑦ 汇总与这份读数说明什么

- **帧均口径**：腿 **9/20**、脊柱 **2/10** 越限，最大比值 **1.66×**（`tail2_pitch`）/ 腿内 **1.53×**。
- **瞬时口径**：腿 11/20、脊柱 2/10，最大 2.66× —— **不要把 2.66× 当成"关节真的转这么快"**：
  其中约一半来自 `kfe`/`foot` 的振铃（位置差分看不到）。
- **说明**：策略确实用到超过资产声明上限的关节速度，量级是 **1.0–1.5×**（不是 2.7×），
  且越限集中在近端驱动关节。若照 URDF 值启用有效限速，会裁掉中高速度档的一部分摆动。
- **不说明**：URDF 那三个数是对的。它们从未进驱动、从未被校准；要把"限到 8 会变差"变成结论，
  需要**限速臂的真跑对照**（同配方同 ckpt，限速开/关），本记录没有这个对照。
- **附带发现（未追）**：`rf_hfe` 的 `target − actual` 最大 0.94 rad（≈54°）、rms 0.23 rad，
  `rf_kfe` rms 0.12 rad ⇒ 近端大关节在追目标时有可观滞后。这是"跟踪误差"读数，
  与速度越限是两件事，本记录不判它是好是坏。

## 证据引用

```bat
:: 两口径都从这一份报告算（cwd <REPO>；报告落 out/，机器本地、gitignore 挡住）
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

1. **3 env / 8 s / 单 seed / 单 ckpt**：每档 1 个 env，故分位数的样本量是 ~400 帧；不是分布。
2. **帧均口径是"每帧走多远"**：它抹掉子帧信息；瞬时口径保留子帧但把振铃读成速度。两者都不是
   "关节承受了什么"——力矩/饱和是另一件事（`acceptance/records/2026-10-09-lizard2-leg-joint-inertia-and-gain-caliber.md`）。
3. **报告数列四舍五入到 5 位小数**，分位在舍入之后算；复算请从同一份报告取。
4. **无限速臂对照**：只说"会裁掉多少"，不说"裁掉之后策略会怎样"。
5. **三个上限值不同**（腿 8 / 脚 6 / 脊柱 4），已逐关节标出，别按组记。
