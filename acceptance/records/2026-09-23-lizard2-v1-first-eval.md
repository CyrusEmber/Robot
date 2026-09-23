# lizard2 v1 首次评测：判决、尺子的两处结构缺陷（2026-09-23）

## 适用范围

`ablation_harness/protocols/lizard2_flat_v2.json`（新协议）、`ablation_harness/baseline_metrics.py`
（`settle_s` + 新种类 + 零命令带按 env 读 + 设备归位）、`ablation_harness/judge_semantics.json`
（新 reader id 的冻结块）、`rl_exp/tools/verify/test_baseline_contract.py`（fixture 的 `settled`/`coast`
+ 行为单测 + 反例）、`ablation_harness/results/lizard2_flat_v1|v2/`（三份报告）。判决书只对
"这一颗检查点、这一套评测条件"负责，不构成"这条线整体可用"的结论。

## 验收条件

1. 协议与 reader 身份**都在报告里**：报告带 `judge.id`、协议全文与摘要，判决能指名尺子。
2. 带齐全且**不许有声明漏洞**：逐带判据、零命令带是声明出来的带，落在所有带外的帧算声明漏洞并判否。
3. 反例**双向有界**：不只证明"改后能过"，还要证明"改后仍然会否"（窗口外的刹车、持续 creep）。
4. 旧 reader 的语义**一字不动**：它必须仍把同一份 rollout 判为 fail，那份报告保留可读。
5. 两次判决的差别**可归因到尺子**：两份报告的帧数据逐位相同。

## 结果

### 判决

- 无 settle 的读者（`baseline-criteria-banded-1`，协议 v1）：**fail**，倒的是 `tracking` 与 `displacement`，
  且只倒在**零命令带**——`|v|` 2.622 m/s（限 0.15）、漂移 +3.216 m（限 0.3）。其余六条全过。
- 修正后的读者（`baseline-criteria-banded-settled-1`，协议 v2）：**pass**，八条全过。
  零命令带 `|v|` **0.0453**（限 0.15）、最差 env 漂移 **0.155 m**（限 0.3）；相对带误差
  0.036 / 0.011 / 0.0063（限 0.25）；位移比 0.988 / 1.006 / 0.997（限 0.8）；
  存活 1.0、姿态 12.5°、非足接触/单部位/总量全 0.0、步态摆动脚数最少 3（均值 3.84）。
- 条件（两份报告同一次 rollout）：`Lizard2-Flat-Play-v1`，检查点 `model_13999.pt`
  （sha256 `48e89b4afa24a3ed171626885e9234f5e0d61445ece03b44cd849c16d8c92f1f`），256 envs、seed 123、
  首回合 20 s、确定性策略、plane；训练 `lizard2_v1/2026-09-22_19-26-50` 跑满 14000/14000。
  两份报告的帧数据逐位相同（逐列 `torch.equal` 全为真）⇒ 差别只可能来自尺子。

### 缺陷 1：零命令带在**命令阶跃那一帧**取样

15 段零命令**全部起于第 499 帧**（框架 10 s 重采样边界），`|v|` 首帧 2.622，其后单调衰减：
0.5 s 时 0.213、1.0 s 时 0.104、2.0 s 时 0.037 m/s；0.5 s 后最差单帧位移 0.004 m、均值 0.0087 m/s。
命令是方波，**任何因果策略都不可能在命令落到 0 的那一帧就已经是 0 m/s** ⇒ 该带当时测的是命令本身。
修正：两种类声明 `settle_s`，只把"命令已持续 ≥ settle_s"的帧当证据；取值**由实测减速度反推**
（2.622→0.104 m/s 用 1.0 s ⇒ ≈2.5 m/s²；命令箱上界 3.0 m/s ⇒ 1.2 s，取 1.5 s）。报告同时给出裁剪前
的读数 `tracking_band_unsettled_max=2.622`，余量可见，不许被这个参数藏起来。

### 缺陷 2：零命令带的位移读数**随批量大小变化**（硬 bug）

原实现把漂移在**全部 env 与全部帧**上求和，再与一个"米"限值比：3.216 m 是 15 个 env 的和
（每 env 约 0.21 m），换 16 envs 会读成约 0.2 m——**读数跟着落在带里的 env 个数走，不跟着策略走**。
修正：先按 env 求和，读**最差 env**的漂移，单位仍是米。反例
`settled_zero_band_drift_is_metres_per_env_not_a_sum_over_the_band` 在改前读 1.0 m、改后读 0.5 m。

### 缺陷 3：判据在 GPU 上一次都没跑出来过

首次采集静默退出（`exit 0` 是 `app.close()` 的），栈在日志里：
`baseline_metrics.py:293 ... RuntimeError: Expected all tensors to be on the same device, but found at
least two devices, cuda:0 and cpu`。采集器把 `meta` 原样透传（`start_pos` 还是回合开始那块 CUDA 张量），
而 `frames` 已是 CPU 拷贝；旧 `displacement_v1` 与 `_score` 都在读处 `.to(device)`，新写的分带版漏了。
13 条反例全在 CPU fixture 上，谁也没撞到。修正为同一写法；反例
`banded_initial_state_need_not_be_a_tensor_on_the_frames_device`（fixture 的 `meta_plain` 把初态按普通数
递进去，同一假设同一坏法），**撤掉修正后确实红**：`TypeError: cos(): argument 'input' (position 1) must
be Tensor, not list`。

### 反例与套件

- 新 reader 的冻结块 11 例；`settle_s` 双向都有界：窗口内 1.0 s 刹车**过**、窗口外 2.5 s 刹车
  **判否**（`tracking` 与 `displacement` 同时）、持续 creep 0.4 m/s **判否**。
- **旧 reader 的块一字未动**：它仍把同一份 rollout 判为 fail，那份报告留在 `results/lizard2_flat_v1/`，
  所以"无 settle 读者在阶跃上判否"这句话保留可读性。
- `BASELINE_CONTRACT_OK`、离线套件 `47/47`（`ALL_OFFLINE_CHECKS_PASSED`）。

### 不许被读过头的地方

- **尺子是在看到这份 rollout 之后改的**。支撑它不是"调参到过"的是：三处缺陷都有与结果无关的独立理由
  （阶跃的因果不可能；单位随批量变；设备假定在 CPU fixture 上不可见），反例双向有界，旧 id 的语义块未动。
  但"先冻结再看"这一条是按纪律走的，本次没有做到；把这份 `pass` 当验收通过还是只当诊断结论，
  **由所有者定**。
- 低速带与退役线"定点 0.5"**不可比**（命令分布不同）；`forward_mae 0.038` 与退役线 v2 的 0.090
  口径不同，只作量级参考，不构成"更优"的证据。
- 步态读数 `gait_swing_feet_least = 3`：`min_swing_feet=2` 下过线，但**4 只脚里有 1 只在 20 s 内
  一次完整摆动都没有**，这属产品判断，不属本判据。

## 证据引用

- 报告：`ablation_harness/results/lizard2_flat_v1/v1/Lizard2-Flat-v1_13999_deterministic_seed123/eval.json`
  （无 settle 读者，fail）、`ablation_harness/results/lizard2_flat_v2/v1/Lizard2-Flat-v1_13999_deterministic_seed123/eval.json`
  （正式，pass）、同目录 `..._settle0.5_superseded/eval.json`（settle 0.5 s + 按 env 求和那版的判决，
  0.213 m/s / +1.248 m，已被取代）。
- 帧记录：上述两份正式报告各自的 `eval.frames.pt`（`*.pt` 不入库，本地可离线复判；
  两份帧数据逐位相同这句话由 `baseline_frames.load` + 逐列 `torch.equal` 核过）。
- 训练读数：`E:\IsaacLab\logs\rsl_rl\lizard2_v1\2026-09-22_19-26-50`（tfevents + `checkpoints.json`），
  巡检输出 13999/14000、`mean_reward` 32.64、`success_rate` 1.0、无 NaN。
- 冻结语义：`ablation_harness/judge_semantics.json` 的
  `baseline-criteria-banded-1`（`kinds_sha256` b1e9046f…／`frozen_sha256` 63a051e2…）与
  `baseline-criteria-banded-settled-1`（`kinds_sha256` 77052228…／`frozen_sha256` 6f27b59b…）。
- 反例名：`banded_initial_state_need_not_be_a_tensor_on_the_frames_device`、
  `settled_ignores_a_brake_inside_the_declared_window`、`settled_still_fails_a_brake_longer_than_the_window`、
  `settled_still_fails_a_robot_that_creeps_through_the_band`、
  `settled_zero_band_drift_is_metres_per_env_not_a_sum_over_the_band`。
- 复现：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness\baseline_eval.py --headless ^
  --task Lizard2-Flat-Play-v1 --protocol ablation_harness\protocols\lizard2_flat_v2.json ^
  --checkpoint E:\IsaacLab\logs\rsl_rl\lizard2_v1\2026-09-22_19-26-50\model_13999.pt ^
  --num_envs 256 --seed 123 ^
  --output ablation_harness\results\lizard2_flat_v2\v1\Lizard2-Flat-v1_13999_deterministic_seed123\eval.json
```

## 未覆盖边界

1. `report_only` 声明 15 项，报告实际产出 8 项：`foot_duty`、`foot_load_fraction`、`feet_down_mean`、
   `foot_yaw_deg`、`foot_slip_mps`、`dof_torque_frac_of_limit` 无人计算（`non_foot_load_fraction`、
   `non_foot_contact_load_n` 名字还对不上）。这与本模块到处在拒的"声明了却没人读"是同一类：
   要么补计算、要么把清单收窄，**未修**。
2. 开训**启动闸门**不存在（`manifest.begin` 只拒 lifecycle 与脏树），形态归
   `work/active/eval-protocol-before-training.md`；因此"协议先于训练"这条纪律在本次是**靠人**执行的。
3. run 的 `run_manifest.json` T0 `declaration` 为空（7 条 failure，含 `num_envs declared None != actual
   4096`）；查旧线 `lizard_baseline_v2` 的 run 同样如此 ⇒ 本机所有 run 的既有状态，非本次启动特有。
4. 零命令带的覆盖率依赖环境的 10 s 重采样（本次 256 envs 里 15 个落进该带、6370 帧）；
   评测器按固定基命令序列下命令这件事没做。
5. **八条判据里没有一条能看见"步态质量"**：判决之后所有者目视录像指出"垫着走（承重脚在滑、摆动脚只抬
   2–8 cm）"，实测证实——而本协议的步态判据只读接触与承重，PLAN 验收要求的 `min_lift_m`（离地高度）
   未实现、`report_only` 的 `foot_slip_mps` 无人计算。⇒ 这份 `pass` 只证明"不倒、方向对、位移对"，
   **不证明会走路**。数值、本仓自己的对照标准与两处根因见
   `acceptance/records/2026-09-23-lizard2-v1-gait-skate.md`。
6. `min_swing_feet` 现填 2，最终值待所有者；`no_non_foot_carrier.fraction=0.05` 仍缺"持续部分承重"档样本。
