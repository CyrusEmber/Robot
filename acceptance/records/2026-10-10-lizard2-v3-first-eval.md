# lizard2 v3 首次评测：入口真跑可用、6000 迭代短窗八闸全过（2026-10-10）

## 适用范围

- **被验的入口**：`ablation_harness/baseline_eval.py` + 冻结协议
  `ablation_harness/protocols/lizard2_flat_v5.json`（协议 **v5** 判配方 **v3**，两个命名空间）。
  在此之前该入口只到"启动契约级"（`acceptance/records/2026-10-09-lizard2-v3-eval-entry-and-inert-velocity-field.md` ④）：
  四项检查过，**没有任何策略读数**。本记录补的就是那一跑。
- **报告落点**：`ablation_harness/results/lizard2_flat_v5/v3/Lizard2-Flat-v3_5999_deterministic_seed123/eval.json`
  （同目录 `eval.frames.pt` 被 `.gitignore:53` 的 `*.pt` 挡在仓外 ⇒ **只在那台机器上**可离线重判）。
- **被评对象**：`logs/rsl_rl/lizard2_v3/2026-10-10_10-14-50` 的 `model_5999.pt`
  （sha256 `954fb332bdd7c56d0ba6cb8bb7faec443006bb1a62cd9b619855cd664b7ae1aa`；训练预算 6000 跑满，见
  `rl_exp/versions/lizard2/main/v3/NOTES.md`）。
- **不覆盖**：判据内容是否恰当（归协议与 `v3/PLAN.md`）；不改配方 / 资产 / 协议 / 闸门；不训练；
  不做 v2→v3 归因（机体与动作接口同时变，两臂不是同一次测量）。

## 验收条件

1. "入口可用"必须是**真跑**得出的，不能拿启动契约级自检代替（旧记录已把那条边界写死）。
2. 报告必须能**指名尺子**：`judge.id`、协议路径与摘要写进报告本身。
3. 帧 hook 必须活：`terminal_frames_captured > 0`（为 0 即私有 API 失配，fall 会偏低）。
4. 判决只对"这一颗 ckpt + 这一套条件"负责，不构成"v3 可用 / 已收敛"的结论。

## 结果

### ① 条件（单点、单 seed、单回合）

| 项 | 值 |
|---|---|
| 任务 | `Lizard2-Flat-Play-v3`（非 `-Play` 的 train id 才给 harness 控 DR；本协议 terrain=plane） |
| 检查点 | `model_5999.pt`，sha256 `954fb332…b7ae1aa`，1826357 B |
| 协议 | `ablation_harness/protocols/lizard2_flat_v5.json`，摘要 `sha256:db5f92ba56586907837f49081ba640d0239ff92a2692277371b3ae8b79aa138a` |
| 规模 / seed / 策略 | 256 envs、seed 123、`deterministic`、首回合 20 s |
| 代码 | `<REPO>` rev `0f4b2bf5317a`（`dirty=false`，启动时工作树干净）；IsaacLab rev `28a37cecdd43`（树带未提交 fork 补丁，预期状态） |

### ② 入口可用（本次判据的主体）

- `judge.id = baseline-criteria-banded-settled-1`、协议路径与摘要、两仓 rev 全部写在报告里 ⇒ 判决指名了尺子。
- `invalid_reasons = []`；`tracking_band_reasons` / `displacement_band_reasons` 均空、`tracking_unclaimed_frames = 0`
  ⇒ 没有"落在所有带外"的声明漏洞。
- `terminal_frames_captured = 256` = env 数 ⇒ 终止帧 hook 存活。
- 报告格式 `report_format` 与既有 lizard2 记录同族，`gates` 八条齐 ⇒ 入口产出可被既有 reader 读。

### ③ 判决：pass，八条闸门全过

| 闸门 | 结果 |
|---|---|
| tracking / displacement / survival / attitude | true |
| no_non_foot_contact / _carrier / _load_sum | true（三项最大值全 **0.0 N**） |
| gait | true（最少摆动脚数 **3**，均值 **3.86**） |

按带读数（判据按带读，**不读全局均值**）：

| 带 | 帧数 | 跟踪误差 [m/s]（限 0.25） | 位移比（限 0.8） |
|---|---|---|---|
| 0–0.1 | 6370 | **0.063** | **0.084** |
| 0.1–1 | 69276 | 0.055 | 0.948 |
| 1–2 | 75648 | 0.015 | 0.957 |
| 2–3 | 66306 | 0.010 | 0.876 |

其余：`first_episode_timeout_fraction` 1.0、`tilt_max_deg` **27.09**（限 cos 0.766 ≈ 40°）、
`tracking_band_unsettled_max` 零带 2.58（裁剪前读数，见下）、
`forward_mae_mps` 0.051、`forward_displacement_m` 26.46 / 期望 29.16。

### ④ 读这些数时别读错

- 零命令带从前是 v2 的判否点（`0.163 m/s`、`+0.764 m` 漂移，见
  `acceptance/records/2026-09-29-lizard2-v2-eval.md`）；v3 在同一族尺子下该带为 `0.063` / `0.084`。
  **这不构成"v3 修好了 v2 的缺陷"**：机体与动作接口同时变，跨臂读数不是同一次测量，可比性由记录的条件面判。
- `tracking_band_unsettled_max` 零带 2.58 是**命令阶跃那一帧**的裁剪前读数，v1 已定性
  （`acceptance/records/2026-09-23-lizard2-v1-first-eval.md` 缺陷 1：任何因果策略都不可能在该帧就是 0 m/s），
  它是余量可见性，不是缺陷。
- 全局 `forward_mae_mps` / `forward_displacement_m` 会把带间差异抹平，**不作判据引用**。
- `diagnostics` 里的 `foot_slip_mps`（承重脚 **0.76–1.40 m/s**）、`spine_leg_coupling` 0.91、
  `yaw_offset_abs_rad` 0.249、`foot_clearance_swing_m` 0.15–0.27 都是 `report_only` 量，
  **本协议不判它们**；滑移算不算缺陷归奖励 / 步态口径（`work/active/lizard2-family-landing.md` ③）
  与 `work/active/joint-limit-shape-and-range-pass.md`，此处只留读数指针，不在这里下结论。

## 证据引用

判决报告（唯一读数家）：`ablation_harness/results/lizard2_flat_v5/v3/Lizard2-Flat-v3_5999_deterministic_seed123/eval.json`

```bat
:: 本次真跑（cwd <REPO>，复跑须换 --output，脚本拒覆盖已存在的报告）
E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness\baseline_eval.py --viz none ^
  --task Lizard2-Flat-Play-v3 --protocol ablation_harness\protocols\lizard2_flat_v5.json ^
  --checkpoint E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50\model_5999.pt ^
  --num_envs 256 --seed 123 ^
  --output ablation_harness\results\lizard2_flat_v5\v3\Lizard2-Flat-v3_5999_deterministic_seed123\eval.json

:: 离线重判（不需要仿真；吃的是帧记录 .pt，不是 eval.json —— 帧数据只在那台机器上）
E:\IsaacLab\env_isaaclab\Scripts\python.exe -m ablation_harness.baseline_metrics ^
  ablation_harness\results\lizard2_flat_v5\v3\Lizard2-Flat-v3_5999_deterministic_seed123\eval.frames.pt ^
  --protocol ablation_harness\protocols\lizard2_flat_v5.json
```

离线重判实测（同一台机器，同一协议文件）：

```json
{"verdict": "pass", "judge": "baseline-criteria-banded-settled-1",
 "protocol_file": "ablation_harness\\protocols\\lizard2_flat_v5.json",
 "protocol_digest": "sha256:db5f92ba56586907837f49081ba640d0239ff92a2692277371b3ae8b79aa138a"}
```

即判决可从盘上记录**重导出**，不依赖本次仿真的进程状态。

`--headless` 已弃用，用 `--viz none`（等价，无弃用告警）。

## 未覆盖边界

- **单点**：1 seed × 1 ckpt × 1 回合（20 s）。趋势判断要 ≥5 点、结论性对照要 ≥3 seed（评测台纪律）；
  本记录只证明"入口能产出可读判决"。
- **短窗**：预算 6000 是用户声明的短窗，且该机体的限位 / 碰撞面仍在
  `work/active/joint-limit-shape-and-range-pass.md` 挂账 ⇒ 读数只能说"截至 6000 步"，不能称收敛或修复。
- **没跑 robust 模式**，也没走 `locomotion_eval_vN.yaml` 的地形套件路径（本协议声明 terrain plane、
  无 `suite_expected`）：地形完成度、跨协议对照归 `work/active/runtime-acceptance-v3.md`（† 同处交接的
  "基线重跑"已无归口，见文末勘误）；记录格式的真跑段归 `work/active/record-format-live-checks.md`。
- **不可异地重判**：`eval.frames.pt` 不入仓，另一台机器要复现只能重跑。
- 判决不评"这条线整体可用"：机身采用、奖励语义、部署接口各有归口事项。

## 勘误（2026-10-10）：交接给 `runtime-acceptance-v3` 的项里"基线重跑"已无归口

**原委**：这一项要的是旧家族基线 ckpt（v13 / v10）在 v3 协议下重跑。核过之后两条都不通：
`rl_exp/versions/lizard/main/v13/` 只有版本规格四件套、**没有 ckpt**；v10 的 ckpt 虽在仓
（`rl_exp/versions/lizard/main/v10/model_14999.pt`），但它依赖的 task id 已随
`work/closed/2026/retired-family-code-prune.md` 注销、家族在 `rl_exp/versions/lines.json` 里
`retired` ⇒ 那一行跑不出来，且旧机体的行本就不得与 lizard2 行同表。

**处置**：`work/active/runtime-acceptance-v3.md` 删掉这一条（原 ①③ 归并为 ① ②），
`ablation_harness/HARNESS.md` 挂账 #1 文案同步去掉"/ 基线重跑"。边界与理由写在那个事项的
"未覆盖边界"节（**单一真身**，不在本记录复述）。上面"未覆盖边界"第 3 条按本勘误只交接
"地形完成度、跨协议对照"两项；本记录其余读数不受影响。
