# 步态形态进评测流水线：新帧格式 + 四条报告项 + v4 协议（2026-09-29）

## 适用范围

- **契约面**：`ablation_harness/baseline_frames.py`（新格式 `baseline-frames-3`）、
  `ablation_harness/frame_semantics.json`（第三块摘要）、`ablation_harness/baseline_metrics.py`
  （四条报告项 + 两条拒绝）、`ablation_harness/baseline_eval.py`（采集该列）、
  `ablation_harness/protocols/lizard2_flat_v4.json`（新协议 + `protocol_anchors.json` 锚）、
  `rl_exp/tools/verify/test_baseline_contract.py`（三条新用例）。
- **诊断面**：`rl_exp/tools/diagnose/gait_probe.py` 导出 10 个躯干关节的逐帧序列
  （`spine_series`）；出图 `rl_exp/tools/diagnose/plot_joints.py`。
- **被评对象**：`logs/rsl_rl/lizard2_v2/2026-09-28_17-02-42/model_9999.pt`，256 envs、seed 123、20 s，
  报告 `ablation_harness/results/lizard2_flat_v4/v2/Lizard2-Flat-v2_9999_deterministic_seed123/eval.json`。
- **不覆盖**：什么算"像蜥蜴"（没有阈值、没有参照群体）、脊椎的**力/力矩**、以及跨家族的可比性。

## 验收条件

1. 新格式**不搬旧记录**：格式名 → 声明的映射按记录自带的 `format` 查；旧格式 1/2 各自冻结、照旧可读，
   且"同一份 rollout 在旧新两格式下判决必须相同"有回归。
2. **契约不许就地改**：新格式 = 新名字 + 新摘要块；两份摘要（列集合与冻结块自身）都由闸门看守。
3. **报告项自带依赖列**：读不到的列 ⇒ 该记录判 `invalid`（不是"少一个数"）；轴里没有可读的关节 ⇒ 同样 `invalid`。
4. **NaN 不许进报告**：未定义就不给这个数（NaN 不等于自身，会让整份报告失去可复现性）。
5. **不能用一个数藏掉结构**：逐关节的量报成逐关节的列表，步幅归属报成逐脚列表。
6. **两种口径当场修掉并写明理由**：被零命令段稀释的相关（只统计命令要求移动的帧）、以及"多对取最大"的
   多重比较上限。
7. 诊断面的同款读数（探针的躯干序列）真跑一次、能读出数。

## 结果

### ① 契约改动

- **`baseline-frames-3`** = 格式 2 的十六列 + `joint_pos`（新轴种类 `joints`，轴向 = 关节名，取值弧度）。
  采集侧只装**有读者的关节**：脊椎组（按实例化 cfg 的 `spine` 组表达式）+ 每腿 `hip/hfe/blade` 三个 token，
  共 22 轴（lizard2）。空轴**拒跑**，不落一列没有轴标的数。
- 旧格式 1/2 的声明与摘要**逐字节不变**（格式 2 的冻结块只改了 `constant` 指向名，`columns_sha256` 未动、
  `frozen_sha256` 属**有意重钉**，理由写在该块旁边）。
- **四条报告项**（report-only，无判据）：`spine_yaw_travel_deg`（逐 yaw 关节的 5–95% 行程，列表）、
  `spine_leg_coupling`（躯干关节 × 腿关节的最差 |相关|）、`stride_hip_corr` / `stride_knee_corr`
  （逐脚：前后位移与髋 / 与膝的相关）。
- **两条拒绝**：协议要的报告项，其依赖列在记录里缺失 ⇒ `invalid`；要读躯干侧摆而轴里没有 yaw 关节 ⇒ `invalid`。
- **协议 v4**：与 v3 判据逐块相同、recipe 相同，只多这四项；锚进 `protocol_anchors.json`。
  一条 v3 的报告在新 reader 下**判决未动**（仍 fail，两条零命令带）⇒ 尺子没被这次改动挪动。

### ② 读数（同一 checkpoint，256 envs、seed 123、20 s，命令 0–3 m/s 混档）

| 项 | 值 | 读法 |
|---|---|---|
| `spine_yaw_travel_deg` | chest_yaw **20.7**、tail1_yaw 10.4、neck_yaw 5.3、tail2_yaw 10.8、tail3_yaw 7.8 | 躯干**在动**，前段最大；量级仍远小于髋（髋的行程 ±0.6 rad = 69°，实测扫 40–50°） |
| `spine_leg_coupling` | 0.78 | 有耦合，但见 ③ 的上限：120 对取最大，本身会偏高 |
| `stride_hip_corr`（rr/rl/rf/lf） | 0.69 / −0.84 / 0.66 / −0.22 | 三条腿的步幅主要由**髋**（横扫黑）承担 |
| `stride_knee_corr`（同一顺序） | 0.21 / −0.05 / −0.71 / 0.24 | rf 的膝与髋同级（0.71 vs 0.66）⇒ 那条腿是混合的；**lf 两头都低**（0.22 / 0.24）|

**诊断面同款读数**（`gait_probe.py`，0.5 m/s、单 env、8 s，单关节），两列并列：
`chest_yaw` p2p 3.9° / 5–95% 3.0°、`neck_yaw` 33.9° / 3.5°、`tail1_yaw` 25.4° / 9.2°、
`tail2_yaw` 34.2° / 2.3°、`tail3_yaw` 28.1° / 10.2°、以及 `tail2_pitch` 42.4° / —。

> **两列差 4–6 倍，这个差本身就是结论**：p2p 大而 5–95% 小 ⇒ 那些是**偶发尖峰，不是持续摆动**。
> 报告项选 5–95% 是刻意的（静得只剩两帧的关节必须读成"静"）；代价是看不见尖峰，见 ④ 边界。
> 这也是一条口径自证：第一版该项写成"逐关节取平均"，结果 `chest_yaw`（3°）把 `tail3_yaw`（10°）抹平，
> 得出"躯干几乎不动"的错读 —— 与 record 里那条"两个 p50 不能配对"同源。改成列表后不再可能。

### ③ 本轮的两次口径修正与一处上限（都在落地前修掉）

1. **稀释**：`stride_*_corr` 原先统计全部存活帧，而窗口里混着"命令为零"的站立段 —— 那些帧上脚的前后位移是
   地面在动，会把两条相关都推向 0（读成"没有关节承担步幅"，真值是"没被要求走"）。改为只统计
   前向命令 > **0.5 m/s** 的帧（= 判据自己的 `floor_mps`，"移动"在本模块只有一个意思）。三条腿的髋相关
   因此上移（0.63→0.69、0.73→0.84、0.54→0.66）。
2. **一个数藏结构**：`spine_yaw_travel_deg` 由"逐关节取平均"改为**逐关节列表**（理由见 ②）。
3. **上限（已按仓规标注）**：`spine_leg_coupling` 是**若干对里的最大**，无多重比较校正；10 个躯干关节 ×
   12 条腿关节下，噪声的最大值本身就有几成 ⇒ 它答的是"存在某一对同相"，不是"躯干耦合有多强"。
   升级路径写在代码注释里（报出胜出那一对，或改成按关节的滞后耦合）。
4. **NaN 不许进报告**：未定义就跳过该项。这条守卫是被一条既有的等值测试逼出来的
   （`judged_or_recoverable(...) == judge(...)`，而 NaN 不等于自身）。

## 证据引用

- 契约与闸门：`python rl_exp\tools\verify\test_baseline_contract.py`（`BASELINE_CONTRACT_OK`）与
  `rl_exp\tools\verify\run_offline_checks.bat`（47/47）；格式摘要复算
  `python rl_exp\tools\verify\test_baseline_contract.py --print-frames-frozen`。
- 判决报告（入仓）：`ablation_harness/results/lizard2_flat_v4/v2/Lizard2-Flat-v2_9999_deterministic_seed123/eval.json`
  （帧数据 `eval.frames.pt` 被 `.gitignore` 的 `*.pt` 挡在仓外，机器本地可离线重判）。
- 探针（机器本地）：`rl_exp/tools/diagnose/out/gait_probe/gait_v2_spine.json`；复读
  `python rl_exp\tools\diagnose\gait_probe.py --task Lizard2-Flat-Play-v2 --checkpoint <run>\model_9999.pt --seconds 8`
- 出图：`python rl_exp\tools\diagnose\plot_joints.py --report <上面的报告>`（`out/joint_plots/*.png`）。
- 规则落点：`ablation_harness/HARNESS.md` 新增"加一条报告项也算升版"一条；
  `work/active/harness-version-anchor-missing.md` 记明锚点编号必须 ≥ `harness-v1.10.0`。

## 判定

1. **此项成立**：帧里现在有"姿态随时间"这一面，四条读数由**评测流水线自己**产出（不再依赖另一个 rollout），
   旧格式/旧记录逐字未动、旧判决在新 reader 下不变。
2. **读数成立但只说形状**：躯干在动（前段 21°）但远小于髋；三条腿的步幅由髋承担，rf 混合，lf 两头都低。
   **本轮不给它们任何判据**：没有健康/失败分布可用来定阈值。
3. **两条口径缺陷是当场修掉的、不是记录的**：稀释与"一个数藏结构"都在落地前改，并各留了一条能挂掉的用例。
4. **诊断面与流水线现在读同一件事**：探针出逐帧躯干序列、流水线出四项汇总；两列的差（p2p vs 5–95%）
   是"尖峰 vs 摆动"的读数，不要混用。

## 未覆盖边界

1. **单 checkpoint、单 seed、单窗口**：四条读数都是"这一次"的，不是分布；`stride_*` 还是混合命令下的
   总体相关（按档分开读会不同，命令只给了一条时间线）。
2. **没有参照群体**：这些数**不是判据**。什么值算"像蜥蜴"需要先有健康/失败的分布，本轮没有 ⇒ 没有阈值。
3. **没有阈值也就没有方向**：`stride_knee_corr` 高**不等于**"像狗"是坏事 —— 蜥蜴高速时也用对角步/跳跃。
   本轮只把"步幅从哪来"变成可读，不判好坏。
4. **躯干只测了位置**：脊椎的力矩、受力方向不在本轮（那些要探针的力矩读数）。
5. **p2p 与 5–95% 的差只在诊断面被读到**：报告项固定用 5–95%，尖峰要靠探针报告看。
6. **`spine_leg_coupling` 的上限**见 ③3；**`stride_*` 只在被要求移动的帧上取**，所以"站着不走"的窗口
   拿不到这两个数（不给数，不是给 0）；躯干行程的列表条目顺序 = 关节轴顺序（报告里的 `axes.joint_pos`）。
7. **只对 lizard2 验证过**：另一家族（`lizard`）没有 hip 关节，采集侧会少 4 轴，其协议也没要这四项；
   新格式对它是"能写但没人读"，未真跑。
8. **重判旧记录的前提**：格式 1 的记录 + 要那四项的协议会判 `invalid`（依赖列不存在），这是刻意的；
   但"同一份 rollout 在旧新格式下判决相同"只对**该协议没要那四项**的情况回归过。
