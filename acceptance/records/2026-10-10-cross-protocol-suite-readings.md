# 套件入口的跨协议读数：v3 与 v2 各自逐字段可复现，但改套件会污染几何未变的列（2026-10-10）

## 适用范围

- **被验的动作**：`work/active/runtime-acceptance-v3.md` 的 ①（同一 ckpt 跨协议对照）与 ②（rough 两列 completion 分布），
  在 `ablation_harness/eval.py` + `locomotion_eval_v2` / `locomotion_eval_v3` 两个冻结协议下各跑一次，并**每臂再重跑一次**作可复现性对照。
- **被评对象**：`E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50\model_5999.pt`
  （sha256 `954fb332bdd7c56d0ba6cb8bb7faec443006bb1a62cd9b619855cd664b7ae1aa`，6000 步短窗末档）。
- **条件**：`--task Lizard2-Flat-v3`（train id）、`--mode nominal`、`--seed 123`、9 列 × 8 envs = 72 env、
  `--group runtime-acceptance`、`--viz none`；IsaacLab rev `28a37cecdd43`；仓 rev 见各 `eval.json`。
- **四个 run 目录**：
  - `ablation_harness/results/locomotion_eval_v3/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123`（v3 第一次）
  - `ablation_harness/results/locomotion_eval_v3/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999b_nominal_seed123`（v3 重跑）
  - `ablation_harness/results/locomotion_eval_v2/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123`（v2 第一次）
  - `ablation_harness/results/locomotion_eval_v2/runtime-acceptance/Lizard2-Flat-v3_v2ckpt5999b_nominal_seed123`（v2 重跑）
- **不覆盖**：robust 模式；多 seed；别的 ckpt；协议文件本身（冻结，只读）。

## 验收条件

1. **可复现性对照**：同一协议重跑一次，两次读数应逐字段相同（不同则先修可复现性，再谈跨协议）。
2. **① 判据**：两协议**几何相同**的列，读数应在 ±0.02 内；rough 两列（几何按协议设计不同）允许有差异。
3. **② 判据**：rough 两列有非零动作策略的 completion 分布，而不是零动作那种全列贴地。

## 结果

### ① 重跑对照：两臂各自逐字段完全相同

| 对照 | 结果 |
|---|---|
| v3 第一次 vs v3 重跑 | `a == b`（含 `global` / `segments` / `terrains` 全部字段，仅 `timestamp` 除外） |
| v2 第一次 vs v2 重跑 | 同上，`a == b` |

⇒ 单次 eval 在本机可复现；下面所有跨协议差异**不会**是"重跑就变"的噪声。

### ② 跨协议逐列读数（Δ = v3 − v2；同一次的数据取自第一次的两个 run）

| 列 | mesh digest v2/v3 | v2 comp | v3 comp | Δcomp | v2 fall | v3 fall | Δfall |
|---|---|---|---|---|---|---|---|
| flat | 相同 | 0.9782 | 0.9782 | 0.0000 | 0.000 | 0.000 | 0 |
| slope_5deg | 相同 | 0.8804 | 0.8804 | 0.0000 | 0.250 | 0.250 | 0 |
| slope_10deg | 相同 | 0.8439 | 0.8515 | +0.0075 | 0.750 | 0.750 | 0 |
| stairs_10cm | 相同 | 0.7394 | 0.7781 | **+0.0387** | 0.750 | 0.625 | **−0.125** |
| stairs_20cm | 相同 | 0.9543 | 0.9700 | +0.0157 | 0.000 | 0.000 | 0（success 0.7877 → 0.8789，**+0.091**） |
| rough_a | 不同（relief 0 → 0.030 m） | 0.9141 | 0.7376 | −0.1765 | 0.125 | 0.500 | +0.375 |
| rough_b | 不同（relief 0 → 0.060 m） | 0.8984 | 0.9135 | +0.0151 | 0.250 | 0.125 | −0.125 |
| gap_20cm | 相同 | 0.9140 | 0.9140 | 0.0000 | 0.125 | 0.125 | 0 |
| gap_40cm | 相同 | 0.2466 | 0.2466 | 0.0000 | 0.000 | 0.000 | 0 |

全局行：v2 `success=0.686 / fall=0.250 / lin_mae=12.557 / energy_per_m=7609.0`；
v3 `success=0.681 / fall=0.264 / lin_mae=13.198 / energy_per_m=8282.2`。

**几何证据**：两协议的唯一差异 = `suites.lizard_suite_v1` → `_v2`，即 rough 两列的 `noise_range` 由单值改区间；
`terrain/geometry.json` 实测 v3 的 rough_a/rough_b `relief_p95 = 0.030 / 0.060 m`，v2 两列同为 `0.0`。
上面 7 个"mesh digest 相同"的列，其逐格 geometry 摘要**逐字相同**。

### 判定

- **条件 2（①）不成立，且原因不是口径**：`stairs_10cm` 的 completion 差 +0.039、fall 差 −0.125（一整格 env），
  `stairs_20cm` 的 success 差 +0.091 —— 这些列的网格与 v2 **字节相同**，运行本身又可复现（条件 1 通过）。
  ⇒ 同一列的读数**不是该列几何的函数**：改动 rough 两列会改变别的列的读数。**跨列耦合**成立。
  机制未隔离，候选两条：(a) 合并 mesh 的三角形顺序改变 → PhysX 接触/求解顺序变（边缘接触多的 stairs 列动、
  flat/gap 逐字不动，与此相符）；(b) spawn 高度或 reset RNG 流耦合。**本记录不下结论。**
- **条件 3（②）成立**：rough_a completion 0.7376 / rough_b 0.9135、fall 0.5 / 0.125，不是零动作那种全列贴地；
  但"越粗越摔得少"这个形状在 8 env/列、单 seed 下不可解释（量化步长即 0.125），只作 OOD 探针读数。
- **列角色（本次新增，与 `ablation_harness/HARNESS.md` 同批落地）**：对平地训练的家族（`rl_exp/tasks/lizard2_recipe.py:185-186`
  `terrain_type="plane"` / `terrain_generator=None`），9 列里只有 `flat` 是成绩面，其余 8 列是 OOD 探针、不判分；
  平地判决走 `baseline_eval.py` + `lizard2_flat_v5.json`（见 `acceptance/records/2026-10-10-lizard2-v3-first-eval.md`）。

## 证据引用

```bat
:: 复跑任一臂（cwd <REPO>；改 --tag 换新 run_id，脚本拒覆盖已存在报告）
E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness\eval.py --task Lizard2-Flat-v3 ^
  --checkpoint E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50\model_5999.pt ^
  --protocol locomotion_eval_v3 --mode nominal --seed 123 --tag <tag> --group runtime-acceptance --viz none

:: 逐字段对照（仅去 timestamp）
python -c "import json;a=json.load(open('<run1>/eval.json'));b=json.load(open('<run2>/eval.json'));a.pop('timestamp');b.pop('timestamp');print(a==b)"
```

读数家：四个目录各自的 `eval.json`；几何：各自 `terrain/geometry.json`；汇总行：各自组的 `summary.csv`。
本记录是这些读数的唯一存放处，事项只留指针。

## 未覆盖边界

- **耦合机制未隔离**（本记录的核心遗留）：要单变量探针才能定案，已另立 `work/active/eval-column-coupling.md`。
- **功效**：8 env/列 × 1 seed，单列 completion 量化步长 0.125；不能据此评策略强弱，也不构成收敛判断。
- **单 ckpt、单窗口**：6000 步短窗末档，读数只对这颗 ckpt 负责（同 `2026-10-10-lizard2-v3-first-eval.md` 的限定）。
- **未跑 robust**：本记录不含 recovery / push 相关口径。
- `eval.frames.pt` 不入仓 ⇒ 另一台机器只能重跑，不能离线重判这四条记录。

## 勘误（2026-10-10，事项收束时追记）：改的是"这些读数能支撑什么"，不是读数

**原委**：本记录的条件 2（①）写的是"几何相同的列读数应在 ±0.02 内"。同一次跑出的读数把它证伪，
而第 58–62 行给的替代说法（"只在 mesh digest 相同的列上比"）救不回来 —— 超差的 `stairs_10cm` /
`stairs_20cm` 正是 mesh 摘要字节相同的列。独立审核见 `acceptance/records/2026-10-10-runtime-acceptance-v3-review.md`；
所服务的 `work/active/runtime-acceptance-v3.md`（同日收束为 `work/closed/2026/runtime-acceptance-v3.md`）由用户拍板
把 ① 降级为口径诊断后关闭。逐项：

1. **第 21 行（判据）**：`±0.02` 不是误差棒 —— 两臂各自重跑逐字段完全相同（条件 1）⇒ 超差是**确定性**的，
   不是"多跑几次能压下去"的噪声带，而是"几何相同 ⇒ 读数相同"这个假设本身。该假设已证伪，故 `±0.02` 作废；
   有效替代 = **跨协议读数只作测量差异诊断，不得作跨协议策略排名，也不得作"旧行仍可比"的依据**。
   原判据行不改写，作废记在这里。
2. **第 58–62 行（判定）**：可证部分保留 —— 改 rough 两列会让摘要未变的列读数改变，即读数是一整个套件的函数；
   **收回**的是"原因不是口径"，以及候选机制 (a)(b) 的倾向性：每列实际 reset/spawn 与接触状态都没归档，
   隔离程度不足以排除指标依赖之外的路径。机制归 `work/active/eval-column-coupling.md`。
3. **第 64、87 行（completion 的量化口径，错）**：completion 是连续比值的 env 均值，**没有** 0.125 这个步长；
   `1/8 = 0.125` 是 8 env 下 `fall_rate` / `success_rate` 这类**逐 env 二值**指标的计数粒度。
   正确写法：completion 无量化步长，fall/success 的粒度是 0.125。
4. **第 52 行（几何证据，"唯一差异"不全）**：`noise_range` 单值→区间只是其一；`suites.py:125-138` 同时改了
   `noise_step` 与 `downsampled_scale`。三者都落在 rough 一族的参数里，但"唯一差异"这句话不成立。
5. **首跑 v3 臂的双 rev（本记录未披露）**：该 run 的 `record.json` 记 `0f4b2bf5317a`，`eval.json` 与
   `summary.csv` 记 `e4d1ac7d0a04`（`eval.py` 在记录与指标两处分别读 rev，中间发生提交即可形成此形状）。
   两 rev 之间只有 `work/active/lizard2-family-landing.md` 的散文变更，测量代码无差异 ⇒ 数字不受影响；
   但"去掉 `timestamp` 后两臂相等"**不等于**两臂的记录条件相同。原工件不无痕回写，缺口记在这里。

未改动：全部读数、条件 1 的结论、条件 3（②）的成立判定，以及四个 run 的归档。
