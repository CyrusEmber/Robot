# baseline 帧格式 2：足端读数采得到、来源可核（2026-09-23）

## 适用范围

`ablation_harness/baseline_frames.py`（格式 2 的声明、`expected_shape` 单源）、
`ablation_harness/frame_semantics.json`（两份格式的冻结块）、`ablation_harness/baseline_eval.py`
（采集四列 + 两条 meta）、`rl_exp/tools/verify/test_baseline_contract.py`（形状/来源/兼容回归）。
只回答"足端量采得到、来源可核、轴对得上、旧记录不变"，不回答判据内容与产品阈值（归
`lizard2-family-landing`），也不含 256-env 正式读数。

## 验收条件

1. 新格式只增列、不改旧义：同一 rollout 在两份格式的记录上判出同一结论。
2. 足端几何来源可核：记录里的 obj、摘要、顶点数与资产文件一致，且与报告列出的脚一致。
3. 轴标对得上脚：四列 `vec3_feet` 的标签等于报告的 `foot_bodies`，形状为 `(T, N, F, 3)`。
4. 接触点速度可离线复算，不依赖冻结的投影。
5. 短接触采样能力有读数；不足处明确说出。

## 结果

- **格式与列**：`baseline-frames-2` = 格式 1 的 12 列 + `foot_lowest_point`、`foot_com_pos`、
  `foot_lin_vel`、`foot_ang_vel`（后三列是 `v_com + ω × (p − p_com)` 的原始料）；必需 meta 增
  `ground_source`、`foot_geometry`。`frame_semantics.json` 两份块各自冻结：格式 1 声明摘要
  `sha256:bd8e5f6a…`（自首次冻结未动），格式 2 为 `sha256:b1514634…`。
- **同一 rollout 结论不变**：v1 与 v2 记录判分的 `verdict`／`gates`／`metrics` 逐项相同（回归
  `test_a_new_format_does_not_move_an_old_records_verdict`）。
- **几何来源（真跑）**：四只脚的 obj、摘要、顶点数逐条对上磁盘文件（各 26 顶点），键集合等于报告的
  `foot_bodies` = `lf/rf/rl/rr_foot`。
- **轴对应**：`foot_contact`、`foot_fraction`、`foot_lowest_point`、`foot_com_pos`、`foot_lin_vel`、
  `foot_ang_vel` 六列标签均为那四只脚，形状 `(1000, 16, 4)` 与 `(1000, 16, 4, 3)`。
- **接触点速度非等于身体速度**：`rr_foot` 的 `|v_com|` 均值 1.881 m/s，而该脚最低网格顶点处
  `|v_point|` 均值 2.288 m/s、最大 8.104 m/s ⇒ 用 COM 速度当"脚的速度"平均低估约 22%。这就是记录
  要带 `foot_com_pos` 的理由，也是"纯转动时原点为零而接触点在滑"那条的实测形态。
- **足端离地（最低网格顶点 z，地面 z=0）**：逐脚最小 −0.0012 / −0.0013 / −0.0074 / −0.0068 m
  （穿地最深 7.4 mm），均值 12.9 mm，最大 187 mm（摆动）。
- **短接触采样**：控制步 20 ms，四只脚最短接触段都是 **1 帧**；一帧长的段数 67 / 36 / 17 / 9
  （中位段长 3–8 帧）⇒ 这些接触的时长与占空比被量化在 20 ms 上，**当前采样分辨不出来**。任何基于
  接触时长的判据必须声明该下限。
- **报告与记录绑定**：报告的 `frames_sha256` 与帧文件摘要一致。

## 证据引用

- 记录与报告：`%TEMP%\baseline_eval_p0_probe\v2fmt2\eval.frames.pt`（16 列、1000 帧 × 16 env）与同目录
  `eval.json`；`*.pt` 不入库，本地可复判。
- 读法与命令：`read_foot_reading.py`（列/接触段/离地）、`check_geometry_and_axes.py`（摘要对文件、轴对脚、
  接触点速度），均只用 `baseline_frames.load` + `diag_metrics.contact_point_velocity`，不起仿真。
- 真跑命令：`<isaaclab python> ablation_harness\baseline_eval.py --headless --task Lizard2-Flat-Play-v1
  --protocol ablation_harness\protocols\lizard2_flat_v2.json --checkpoint
  E:\IsaacLab\logs\rsl_rl\lizard2_v1\2026-09-22_19-26-50\model_13999.pt --num_envs 16 --seed 123
  --output <...>\v2fmt2\eval.json`
- 冻结摘要：`ablation_harness/frame_semantics.json`（`--print-frames-frozen` 可复算）。
- 离线闸门：`rl_exp\tools\verify\run_offline_checks.bat` 47/47。

## 未覆盖边界

1. 判定侧**还没有任何一条判据读这四列**（属 P2）：本记录只证明采得到、来源可核、轴对得上。
2. 本次 16 env、`fail` 倒在零命令带覆盖率，不是策略结论；256-env 正式读数另见首评记录。
3. 同一个 format 名在写出记录之后又被增列（上一版 15 列记录）。读侧**容忍子集**——缺列只在某条判据要读它
   时才拒——所以"改名纪律"由冻结表与规则施压，不靠硬拒。已知边界，本轮未改。
4. 未做子步采样对照：短接触"到底有多短"仍只有 20 ms 量化的读数。
