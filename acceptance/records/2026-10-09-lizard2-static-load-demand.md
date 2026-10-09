# lizard2 静站承重基线：默认站姿下逐关节的 PD 估算占用（2026-10-09）

## 适用范围

`work/active/actuator-params-audit.md` 的 `next` ④：量"站住要花掉多少力预算"，作为**承重下限**。零动作
（策略不参与）、重力开、默认关节目标，逐关节对自己的求解器侧限幅取占用率。不改资产、配方、限位；不训练。

被读对象：`Lizard2-Flat-Play-v3`（30 关节，单环境，`num_envs=1`）。

## 验收条件

口径全部写在工具 `run_static` 的 docstring 里，此处只列判据：

- 估计量 = `Kp*(q* − q) − Kd*q̇`，`Kp`/`Kd` **从求解器读**（与层 1/2 及奖励重构同式，`parkour_mdp.py:271`）；
- 分母 = **该关节自己的**求解器侧限幅（`data.joint_effort_limits`），不是组 cfg——逐关节口径沿用
  `2026-09-23-lizard2-v1-gait-skate.md` ⑫（那里逐关节化正是因为一次组内单键覆盖把 hip 按脚板限幅算了）；
- 窗口 = 零动作落定 2.0 s 之后，到**首次 env 复位**或**机体高度跌破落定高度一半**为止；落定/掉地/复位帧不进统计；
- 计数名 = `pd_estimate_over_limit_frac`，**不叫"饱和"**：估算越限 ≠ 求解器夹断（`applied_torque` 对 implicit
  结构性为零，夹断在求解器内部）。
- 不据此声称任何速度带下的执行器能力（静站不是步态）。

## 结果

落定后机体高度 **0.9082 m**，窗口正常关闭（无复位、无掉地），**100 帧**（2.0 s @ 50 Hz 控制）。全部 30 个关节的
`pd_estimate_over_limit_frac` = **0.000** ⇒ 默认站姿下**没有任何关节的估算触碰限幅**。

按组给最坏的 `frac_of_limit_p50`（p50 占**自身**限幅）：

| 组 | 关节数 | 限幅 [N·m] | 最坏关节 | p50 [N·m] | frac_of_limit_p50 |
|---|---|---|---|---|---|
| spine | 10 | 80 | `tail1_pitch` | 43.66 | **0.546** |
| legs | 16 | 180 | `lf_hfe` | 35.70 | 0.198 |
| feet | 4 | 70 | `rf_foot` | 2.09 | 0.030 |

逐关节 p50 占用（× 组限幅），按组列出：

- **spine（限幅 80）**：`tail1_pitch` **0.546**、`tail2_pitch` 0.188、`neck_pitch` 0.111、`chest_pitch` 0.076、`tail3_pitch` 0.050、`chest_yaw` 0.003、`tail1_yaw` 0.000、`tail2_yaw` 0.000、`tail3_yaw` 0.000、`neck_yaw` 0.000
- **legs（限幅 180）**：`lf_hfe` 0.198、`rf_hfe` 0.197、`rl_hfe` 0.165、`rr_hfe` 0.163、`lf_haa` 0.136、
  `rf_haa` 0.135、`rl_kfe` 0.091、`rr_hip` 0.090、`rl_hip` 0.088、`rr_kfe` 0.087、`rf_kfe` 0.075、
  `lf_kfe` 0.069、`rr_haa` 0.067、`rl_haa` 0.067、`lf_hip` 0.011、`rf_hip` 0.009
- **feet（限幅 70）**：`rf_foot` 0.030、`lf_foot` 0.027、`rl_foot` 0.018、`rr_foot` 0.016

**可读出的结论（只此三条）**：

1. **静站不构成本钱问题**：最坏 0.546，且全部 30 关节的最大估算值（`tail1_pitch` 46.32 N·m）都远低于自身限幅
   ⇒ "180/70/80 不够用"这一假设在承重基线上得不到支持。
2. **最吃紧的是尾不是腿**：`tail1_pitch` 用掉自身 80 N·m 的一半以上（默认站姿里尾根在承重），而腿组最坏只有
   0.198、脚板只有 0.030。若要问"哪个上限最先挡路"，当前的答案是 spine 的 `tail1_pitch`，不是 legs。
3. **腿与脚板的余量很大**：脚板静态只用到自身限幅的 1.6%–3.0%（与 `2026-09-23-lizard2-v1-gait-skate.md` ⑫
   承重期脚板 p50 占到 0.38–1.50× 形成对照 ⇒ 脚板的负载来自**步态/承重工况**，不来自站立）。

## 复读命令与结果

解释器 `E:\IsaacLab\env_isaaclab\Scripts\python.exe`（本机 `paths.yaml`），从 `E:\Robot` 执行：

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_actuator_budget.py ^
  --static-only --task Lizard2-Flat-Play-v3 --json "%TEMP%\static_load_lizard2_v3.json"
```

本机该次报告落在 `C:\Users\yanke03\AppData\Local\Temp\static_load_lizard2_v3.json`（**机器本地，不进仓**）。
完成标记 `STATIC_LOAD_MEASURED`，退出码 0（测量，不是判决）。

## 证据引用

- 事项与判据：`work/active/actuator-params-audit.md`。
- 同轮驱动读回（声明值 vs 求解器持有值）：`acceptance/records/2026-10-09-lizard2-drive-readback-audit.md`。
- 逐关节占用口径的来处（含一次组内单键覆盖的真错）：`acceptance/records/2026-09-23-lizard2-v1-gait-skate.md`（⑫）。
- 生效限幅与单关节跟踪能力首测：`acceptance/records/2026-09-22-lizard2-actuator-capability.md`。
- 落点代码：`rl_exp/tools/verify/check_actuator_budget.py`（`run_static` / `--static-only`）。

## 未覆盖边界

- **零动作 = 默认站姿**（`use_default_offset`），不是训练策略维持的姿势，也不是步态；策略可能站得更好或更差。
- **不是能力验收**：它只回答"站住花多少"，不回答命令窗口（`lin_vel_x [0, 3.0]`）下需要多少——那要目标速度带（R4）。
- **单次、单环境、单 seed**：未做跨 seed/跨 checkpoint 复核，未做多环境。
- **估算不是力矩**：不含求解器隐式项，也不含接触冲量；`pd_est_over_limit_frac = 0` 只说明估算没越限。
- 默认站姿的尾根承重是否**设计意图**未判：`tail1_pitch` 的高占用可能来自默认角与几何，取值与是否改配置归
  `work/active/actuator-params-audit.md`（改数值 = 新版本，本轮只出读数）。
- 2.0 s 落定窗是否足够未做敏感性检查；窗口内的峰值（`max_nm`）与 p50 同量级，未见瞬态冲高。
