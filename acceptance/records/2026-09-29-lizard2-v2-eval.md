# lizard2 v2 评测：判决倒在零命令带，脚板不再整段饱和、改由固定平放参考顶回（2026-09-29）

## 适用范围

- **判决**：`Lizard2-Flat-v2` 在协议 `ablation_harness/protocols/lizard2_flat_v3.json`
  （reader `baseline-criteria-banded-settled-1`）下的固定窗报告，落点
  `ablation_harness/results/lizard2_flat_v3/v2/Lizard2-Flat-v2_9999_deterministic_seed123/eval.json`
  （同目录的 `eval.frames.pt` 是帧数据，被 `.gitignore` 的 `*.pt` 挡在仓外 ⇒ **只在那台机器上**可离线重判）。
- **机制读数**：`rl_exp/tools/diagnose/gait_probe.py` 三档 0.5 / 1.5 / 2.8 m/s，8 s 与 20 s 两个窗口，
  报告 `rl_exp/tools/diagnose/out/gait_probe/gait_v2.json` 与 `gait_v2_20s.json`（`out/` 机器本地）。
- **曲线读数**：run 自己的 tfevents → `rl_exp/versions/lizard2/main/v2/tb_scalars.full.csv`（机器本地，250000 点）
  及其入库抽样 `tb_scalars.csv`（3775 点 = 25 tags × 151）。
- 被评对象：`logs/rsl_rl/lizard2_v2/2026-09-28_17-02-42` 的 `model_9999.pt`
  （sha256 `2c96057be4e428daf34cac6a9c3d3b93084e348cee0a1635ef9934c6805995d9`，4096 envs，seed 42）。
- **不覆盖**：两臂对照（对照臂不存在，见"未覆盖边界"）、部署接口、sensor 层之外的接触力真值。

## 验收条件

1. 判决必须**指名它的尺子**：报告里带 `judge.id`、协议全文与摘要。
2. 两臂各有一份协议文件时，"同一把尺"必须是**机器可查**的，不是承诺：`test_baseline_contract.py`
   逐块比对两份 lizard2 协议，身份键与 `why_*` 以外不许有差；该检查的破坏测试（改 `threshold_cos`
   0.766→0.866）实测转红并点名 `['criteria']`。
3. 机制读数必须**满足样本下限**（每档每脚 ≥30 稳态承重周期）才进结论；不足的格子标"样本不足"。
4. 收窄的预算必须写成**偏离**，不许留在 cfg 里假装一致。
5. 读数只能来自 run/探针自己的记录；机制性量（力矩）只给**上界**并说明口径。

## 结果

### ① 判决：fail，八条闸门里六条过，两条都只倒在零命令带

| 闸门 | 结果 | 读数（限） |
|---|---|---|
| tracking | **false** | 零命令带 **0.163 m/s**（限 0.15） |
| displacement | **false** | 零命令带漂移 **+0.764 m**（限 0.3） |
| survival | true | `first_episode_timeout_fraction` **1.0** |
| attitude | true | `tilt_max_deg` **14.5**（限 cos 0.766 ≈ 40°） |
| no_non_foot_contact / _carrier / _load_sum | true | 三个最大值全 **0.0** |
| gait | true | 最少摆动脚数 **3**（限 2），均值 3.90 |

三条相对带误差 **0.030 / 0.012 / 0.012**（限 0.25）、位移比 **0.979 / 0.986 / 0.989**（限 0.8）、
`command_mps_mean` 1.458、`tracking_unclaimed_frames` 0、`invalid_reasons` 空。
⇒ 被命令走的部分全干净，**唯一坏掉的是"被要求停下"**：零命令带 6370 帧上跑 0.163 m/s、漂 0.764 m。
该读数是"最差 env"的口径（settled reader 的 per-env 修正），`tracking_band_unsettled_max` 2.593 是
裁剪前的余量，两者并列写在报告里。

### ② 机制读数：脚板从"整段顶上限"变成"几乎不饱和，但被地面顶开后 PD 顶回"

20 s 窗口（样本下限达标：每脚每档稳态承重周期 **37–64**，全 ≥30）。8 s 窗口的同一批读数与之几乎重合
（脚板 p50 rr 2.7→2.5、lf 63.9→64.3、lf 饱和 0.13→0.15）⇒ 读数不是窗口人造物。

| 档 | 脚 | duty | 脚板 p50 / 上限占比 / 饱和帧占比 [N·m] | 目标偏离平放位 / 实际被顶开 [rad] | 承重稳态接触点速度 p50 / p95 [m/s] |
|---|---|---|---|---|---|
| 0.5 | rr | 0.37 | 2.5 / 0.04 / 0.00 | 0.000 / 0.005 | 0.00 / 0.00 |
| 0.5 | rl | 0.74 | 5.3 / 0.08 / 0.00 | 0.000 / 0.016 | 0.00 / 0.43 |
| 0.5 | rf | 0.29 | 9.2 / 0.13 / 0.00 | 0.000 / 0.022 | 0.00 / 0.03 |
| 0.5 | lf | 0.52 | 29.9 / 0.43 / 0.00 | 0.000 / 0.132 | 0.00 / 0.66 |
| 1.5 | rr | 0.40 | 4.8 / 0.07 / 0.00 | 0.000 / 0.029 | 0.00 / 0.03 |
| 1.5 | rl | 0.47 | 14.3 / 0.20 / 0.00 | 0.000 / 0.083 | 0.05 / 2.20 |
| 1.5 | rf | 0.39 | 9.0 / 0.13 / 0.00 | 0.000 / 0.042 | 0.30 / 0.43 |
| 1.5 | lf | 0.37 | 48.9 / 0.70 / 0.00 | 0.000 / 0.203 | 0.00 / 0.00 |
| 2.8 | rr | 0.38 | 8.2 / 0.12 / 0.00 | 0.000 / 0.034 | 0.02 / 0.26 |
| 2.8 | rl | 0.39 | 12.9 / 0.18 / 0.00 | 0.000 / 0.088 | 0.56 / 2.51 |
| 2.8 | rf | 0.36 | 26.7 / 0.38 / 0.00 | 0.000 / 0.153 | 0.54 / 0.71 |
| 2.8 | lf | 0.35 | 64.3 / 0.92 / **0.15** | 0.000 / 0.249 | 0.00 / 0.01 |

**能读出来的：**

1. **三个假设里第 3 条成立**：脚板目标整个窗口恒为 **0.000 rad 偏离平放位**（策略没有通道，如设计），
   而它**实际**被地面顶开 0.005–0.249 rad ⇒ 无命令下 PD 确实把脚板钉在平放位附近。
2. **反向假设这次没有出现**：脚板**不再整段饱和**——12 格中 11 格饱和帧占比 0.00，只有 lf 2.8 档
   0.15（p50 0.92 倍上限）。"去掉权限等于拿掉一个饱和执行器所以步态变差"这条**没有**证据支持。
3. **代价换了个位置**：脚板被顶开到 0.249 rad 时 PD 出到 **64.3 N·m（0.92 上限）** ⇒ 定位到 PLAN
   预写的入口——"固定参考 PD 是否阻碍接触顺应"。这是下一问的读数，不是本轮结论。
4. **腿仍不吃紧**：hip p50 2.5–26.3（≤0.15 上限，饱和全 0.00）、hfe 12.8–76.8（最高 0.43 上限，
   2.8 档 lf 0.01）。⇒ "关节力太大"在腿上仍不成立。
5. **四只脚仍分两类**：rr / rf / rl 倾角 36–50°、贴地占自身 cap 0.003–0.129（踮着承重），
   lf 倾角 1.5°、占 cap 0.09–1.60（平放）。滑移最重的是 **lf**（2.8 档 p95 2.51 m/s）。
6. **存活**：三个档 `frames_alive` 999/1000，`done_frames` 1（末帧一次；该字段的含义未单独核，见边界）。

### ③ 曲线读数：任务级 3000 迭代定型，质量层到 10000 仍在收紧

分块 = 1000 迭代；“退出块” = 其后所有分块都留在尾块 ±band 内的最早分块。

| tag | 尾块均值 | 2% / 5% / 10% 退出块 | 首块 → 尾块 |
|---|---|---|---|
| `Train/mean_reward` | 30.05 | 8 / 6 / 5 | 0.27 → 30.05 |
| `Train/mean_episode_length` | 999.6 | 3 / 3 / 3 | 27.6 → 999.6 |
| `Metrics/success_rate` | 0.99998 | 3 / 3 / 3 | 0.456 → 1.000 |
| `Episode_Termination/time_out` | 0.9991 | 3 / 3 / 3 | 0.0006 → 0.999 |
| `Metrics/base_velocity/error_vel_xy` | 0.09729 | 9 / 8 / 7 | 0.782 → 0.0973 |
| `Loss/entropy` | −9.162 | 9 / 9 / 8 | −2.10 → −9.16 |
| `Policy/mean_std` | 0.2085 | 8 / 7 / 6 | 0.258 → 0.209 |
| `Episode_Termination/head_contact` | 8.87e−4 | 9 / 9 / 9 | **0.994 → 8.87e−4** |
| `Episode_Termination/base_contact` | 0 | 0 / 0 / 0 | 恒 0 |

1. **任务级在第 3 块（3000 迭代）定型**：episode 长度顶到 999.6、`time_out` 0.999、`success_rate` 1.0。
2. **质量层没有平台**：`error_vel_xy` 与熵的 2% 带都落在**最后一块**，`mean_std` 单调下降 ⇒ 到 10000
   迭代策略仍在收紧，"10000 已收敛"不成立。
3. **失败模式有明确首现点**：`head_contact` 第 0 块就占 **0.994**（几乎每一次终止都是砸头），
   第 3 块降到 0.016，尾块残余 8.9e−4；`base_contact` 全程恒 0。
4. **单 run**：n=1，不据此声称 seed 稳定性。

### ④ 偏离：实跑 10000 迭代，而 cfg 声明 14000

`Lizard2V2PPORunnerCfg.max_iterations = 14000`（`rl_exp/tasks/agents/rsl_rl_ppo_cfg.py:390`），
而 run 的 `params/agent.yaml` 与 manifest 记的是 **10000**（末档 `model_9999` = `max_iterations-1`）。
覆盖来源未记在 argv 里 ⇒ 记为**未书面化的 CLI 覆盖**，写进 `v2/NOTES.md` 的"实际执行与偏离"。
v2 与 PLAN 里那条"两臂同预算"因此不能靠 cfg 声明成立。

## 判定

1. **v2 在当前冻结协议下是 fail**，且失败面**收窄到零命令带**的两条读（速度与漂移）。相对带全过 ⇒
   它不是"走不好"，是"停不住"。
2. **"去掉脚板动作权限"没有触发它最担心的失败模式**：脚板不再整段饱和，反向假设（拿掉饱和执行器
   ⇒ 步态变差）在本读数里没有证据。同时**代价被定位**：固定平放参考的 PD 在脚板被顶开时出到 0.92
   倍上限 ⇒ 下一问是"固定参考是否阻碍接触顺应"，不是"策略乱命令"。
3. **腿的力不是问题**：hip/hfe 稳态 p50 最高 76.8 N·m（0.43 上限），饱和几乎全 0。
4. **预算被砍到 10000 时曲线仍在收紧** ⇒ 这次 run 的读数属于"未训满"的配方，与 cfg 声明的 14000
   不构成同一次实验。

## 证据引用

- 判决（入仓 = 报告本体）：`ablation_harness/results/lizard2_flat_v3/v2/Lizard2-Flat-v2_9999_deterministic_seed123/eval.json`；
  帧数据 `eval.frames.pt` 被 `.gitignore` 的 `*.pt` 挡在仓外（机器本地，可被清理）⇒ 离线重判给的是**路径 + 命令**，
  不承诺仓内可点。尺子：`ablation_harness/protocols/lizard2_flat_v3.json`（锚
  `ablation_harness/protocol_anchors.json`）；与 `lizard2_flat_v2.json` 的判据同一性由
  `rl_exp/tools/verify/test_baseline_contract.py::test_the_two_lizard2_arms_are_judged_by_one_ruler_spelled_twice` 看守。
- 复读（离线重判，不起仿真）：
  `python -m ablation_harness.baseline_metrics ablation_harness\results\lizard2_flat_v3\v2\Lizard2-Flat-v2_9999_deterministic_seed123\eval.frames.pt --protocol ablation_harness\protocols\lizard2_flat_v3.json`
- 机制读数（机器本地、可被清理）：`rl_exp/tools/diagnose/out/gait_probe/gait_v2_20s.json`（20 s）与
  `gait_v2.json`（8 s）；复读
  `python rl_exp\tools\diagnose\gait_probe.py --task Lizard2-Flat-Play-v2 --checkpoint <run>\model_9999.pt --seconds 20`
- 曲线（入仓抽样）：`rl_exp/versions/lizard2/main/v2/tb_scalars.csv`；全量机器本地
  `tb_scalars.full.csv`。生成：
  `python rl_exp\tools\trainlog\dump_tb.py --log_dir <run> --out rl_exp\versions\lizard2\main\v2\tb_scalars.full.csv`

## 未覆盖边界

1. **无对照臂**：本轮只有实验臂。对照臂（v1 配方在当前资产上的重训）不存在 ⇒ 上面的差异都不是
   归因，v2 的读数就是 v2 自己的读数。
2. **单 run / 单 seed / 单 checkpoint**：n=1，任何"好了多少"都无 run-to-run 散度可比。
3. **探针是 3 个 env**（每档一个），不是 256；`frames_alive` 999/1000 与 `done_frames` 1 的组合
   未逐帧核过（`done_frames` = 该 env 的 done 帧计数，末帧那一次是终止还是探针收尾未判）。
4. **力矩仍是重构值**：`tau = Kp(q*−q) − Kd·q̇`，隐式驱动的 `applied_torque` 结构性为零 ⇒ 饱和帧上的
   "交付力矩"按 `clamp` 推，是上界不是实测。
5. **判决只对这一颗检查点、这一套条件负责**；`sensor` 层之外的接触力真值、真滑移都不在这里。
6. **`steady_stance_count` 下限是 PLAN 定的 30**，本次全档达标靠把窗口从 8 s 拉到 20 s；换窗口要重新陈述，
   不能只换数字（两窗口读数互证已写在上文）。
7. **几何与预算两条混淆仍在**：脚碰撞 hull 换代发生在 v1 训练之后（影响所有跨版本引用）；
   run 实跑 10000 vs 声明 14000。
