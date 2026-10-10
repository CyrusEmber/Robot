# 套件列间耦合探针：动一格的碰撞几何，让另四列（网格逐字节相同）读数改变（2026-10-10）

## 适用范围

- **被验的问题**：`work/active/eval-column-coupling.md` —— 套件里改一列，别的列会不会跟着动？
  （起因见 `acceptance/records/2026-10-10-cross-protocol-suite-readings.md`：v2→v3 改了 rough 两列，
  而 `stairs_10cm` 等**网格逐字节相同**的列读数也变了。）
- **手段**：不改仪器代码。`ablation_harness/suites.py` 的 `lizard_suite_v2()` 自述"返回的 cfg 可由调用方修改"，
  故用一个 TEMP 里的包装脚本**在内存里**替换 rough 列的几何后调用 `eval.py`（正文见文末"复现"节 ——
  该脚本路径会消失，脚本本身以本记录为准）。**没有任何就地看守**（v3 未声明指纹，`suite_lock.FIRST_VERSION_REQUIRING_LOCK = 4`），就地改会静默换掉此后所有 v3 run 的地面。
- **三次 run 的条件**：同一 ckpt（`model_5999.pt`，sha256 `954fb332…b7ae1aa`）、`--task Lizard2-Flat-v3`、
  `--mode nominal`、`--seed 123`、72 env、`--group coupling-probe`：

  | run | 地面 | 与前一次的差别 |
  |---|---|---|
  | `v3 · probe-ctrl` | rough 两列都换回 v1 几何（单值 = 抬升平板） | 相对 v3：两列几何都变 |
  | `v3 · probe-rougha` | **只** rough_a 换回 v1 几何，rough_b 保留 v3 起伏 | 相对 v2：**只有 rough_b 一格的网格不同** |

  落点：`ablation_harness/results/locomotion_eval_v3/coupling-probe/`。
- **参照行**取自 `2026-10-10-cross-protocol-suite-readings.md` 的 v2 / v3 第一次 run（同 ckpt、同条件）。
- **不覆盖**：robust 模式；多 seed；其它 ckpt；求解器级取证。

## 验收条件

1. **注入忠实**：`probe-ctrl` 的场地摘要应与 v2 的相同，且其读数与 v2 逐字相同（只允许 `protocol` 标签、
   `timestamp`、`git_rev_*` 不同）。
2. **单列可控**：`probe-rougha` 的 `geometry.json` 里 rough_a `relief` 回到 0、rough_b 仍有起伏。
3. **判据**：能指出"改了这一列 ⇒ 哪几列变了"，据此排除或坐实机制。

## 结果

### ① 注入忠实（条件 1 成立）

- `probe-ctrl` 场地摘要 `sha256:9f38cddb912dfb39…` = **v2 那次** `geometry.json` 的 `geometry_digest` 逐字相同。
- 读数对照：`global` / `segments` / `terrains` 三块**全部字段相同**；顶层只有
  `protocol`（`Locomotion-Eval-v3` vs `-v2`）、`git_rev_lizard`、`timestamp` 三个标签性字段不同。
- ⇒ v2 与 v3 两个协议文件之间**除套件几何外没有任何语义在动**；差异全部由地面产生。

### ② 单列可控（条件 2 成立）

`probe-rougha` 场地摘要 `sha256:52b69c126146243f…`（既非 v2 也非 v3），逐格与 v2 那次比对：

| 列 | 网格摘要 vs v2 | v2 | v3 | probe-rougha |
|---|---|---|---|---|
| flat | 相同 | 0.9782/0.000 | 0.9782/0.000 | 0.9782/0.000 |
| slope_5deg | 相同 | 0.8804/0.250 | 0.8804/0.250 | 0.8804/0.250 |
| slope_10deg | 相同 | 0.8439/0.750 | 0.8515/0.750 | **0.8739/0.625** |
| stairs_10cm | 相同 | 0.7394/0.750 | 0.7781/0.625 | **0.8537/0.500** |
| stairs_20cm | 相同 | 0.9543/0.000 | 0.9700/0.000 | **0.9479/0.125** |
| rough_a | **相同**（`246588bf1274…`） | 0.9141/0.125 | 0.7376/0.500 | **0.8660/0.250** |
| rough_b | 不同（唯一改动） | 0.8984/0.250 | 0.9135/0.125 | 0.7689/0.375 |
| gap_20cm | 相同 | 0.9140/0.125 | 0.9140/0.125 | 0.9140/0.125 |
| gap_40cm | 相同 | 0.2466/0.000 | 0.2466/0.000 | 0.2466/0.000 |

（读数为 `completion` / `fall_rate`；探针的 rough_a `relief = 0.0`、rough_b `= 0.065`。）

### ③ 判定

- **耦合成立，且不是局部的**：`probe-rougha` 相对 v2 **只差 rough_b 一格的碰撞几何**，却有 **4 列**（slope_10deg、
  stairs_10cm、stairs_20cm、**rough_a 自己**）读数改变 —— 其中三列在网格上离 rough_b 不近，而 rough_a 的地面
  与 v2 **逐字节相同**却给出不同读数（0.9141 → 0.8660，fall 0.125 → 0.250）。幅度（completion 最大 0.115、
  fall 最大 0.25）远大于此前 ① 用的 ±0.02。
- **但也不是"随便动一下就全漂"**：flat、slope_5deg、gap 两列在 v2 / v3 / 探针**三种不同地面**下逐字相同。
  受影响集合恰是接触最边缘的列（连续斜面、台阶、起伏）；未受影响的是平面与跨越地形。**"任何套件改动都让
  全表不可比"是不成立的过度概括**，但"只有改动那列不可比"同样被证伪。
- **一条独立的新通道（地形生成期）**：`probe-rougha` 的 rough_b **配置逐字未改**，实测 `relief` 却是 `0.065`，
  而 v3 run 里是 `0.060` —— height-field 列从**全局 numpy 流**取起伏（`suites.py` 自述），所以改前面一列的
  参数会改变后面一列的**实现几何**。⇒ 在 hf 列之间做"只改一列"的单变量探针，**几何上本来就不成立**。
- **机制余项**：剩下的候选是"碰撞几何变 ⇒ 接触/求解顺序变，边缘接触列翻转"，与受影响集合相符；
  但**未从求解器取证**，本记录不坐实。要排除 reset RNG / spawn 高度那两条，需要一个**不动任何几何**的探针
  （例如只换 env 排布），当前 `eval.py` 没有这种入口 —— 这也是本项剩下的真实缺口。

## 证据引用

```bat
:: 需要本机 E:\IsaacLab 的 venv 解释器；下面脚本正文写在本记录里（TEMP 那份会随机器清理消失）
E:\IsaacLab\env_isaaclab\Scripts\python.exe %TEMP%\probe_suite.py ctrl
E:\IsaacLab\env_isaaclab\Scripts\python.exe %TEMP%\probe_suite.py rougha

:: 三次对照（去 timestamp 后逐字段比）
python -c "import json;g=lambda p:json.load(open(p,encoding='utf-8'));A=g('<run>/eval.json');B=g('<ref>/eval.json');print([k for k in set(A)|set(B) if A.get(k)!=B.get(k)])"
```

`%TEMP%\probe_suite.py`（正文即权威副本）：

```python
import runpy
import sys

REPO = r"e:\Robot"
HARNESS = REPO + r"\ablation_harness"
sys.path.insert(0, HARNESS)   # suites.py lives here; eval.py gets it as its script dir
sys.path.insert(0, REPO)      # rl_exp lives here

import suites  # noqa: E402  (the same top-level module eval)

mode = sys.argv[1]
tag = {"ctrl": "probe-ctrl", "rougha": "probe-rougha"}[mode]

_V1 = suites._LIZARD_SUITE_V1_GENERATOR
_orig_factory = suites.lizard_suite_v2


def _factory():
    # mutates the module-level v2 generator singleton (the factory hands out the same object);
    # fine for a one-shot probe process, not a pattern to copy into the harness
    cfg = _orig_factory()
    sub = cfg.terrain_generator.sub_terrains
    sub["rough_a"] = _V1.sub_terrains["rough_a"].copy()
    if mode == "ctrl":
        sub["rough_b"] = _V1.sub_terrains["rough_b"].copy()
    return cfg


suites.lizard_suite_v2 = _factory

sys.argv = [
    "eval.py",
    "--task", "Lizard2-Flat-v3",
    "--checkpoint", r"E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50\model_5999.pt",
    "--protocol", "locomotion_eval_v3",
    "--mode", "nominal",
    "--seed", "123",
    "--tag", tag,
    "--group", "coupling-probe",
    "--viz", "none",
]
runpy.run_path(REPO + r"\ablation_harness\eval.py", run_name="__main__")
```

## 未覆盖边界

- **机制未从求解器取证**（见判定末条）；要排除 reset RNG / spawn 高度缺一个"不动几何"的探针入口。
- **探针行是诊断读数**：只存在于 `results/locomotion_eval_v3/coupling-probe/`（自带 group），不进 campaign 表，
  也不被任何成绩引用；其地面摘要不与任何冻结协议对齐，但 `suite_lock` 对 v3 记 `not_declared`，故不拒跑。
- **功效**：8 env/列 × 1 seed，单列 completion 量化步长 0.125；本记录只用"变没变"这一位信息，不评策略强弱。
- 单 ckpt、短窗（6000 步末档）、只有 nominal；`eval.frames.pt` 不存在（`eval.py` 不留帧档）⇒ 无法从轨迹层面
  定位分叉帧，只能从读数层面判定。

## 勘误（2026-10-10，审核返工）：改的是"这些读数能支撑什么"，不是读数

**原委**：独立审核见 `acceptance/records/2026-10-10-eval-column-coupling-review.md`（不通过、退回）。本记录是那次
审核的对象：下面逐条**收窄声明并纠错**，读数、几何归档与两次 run 的落点均未改动（不改写原句，作废的话记在这里）。
机制缺口由 `acceptance/records/2026-10-10-eval-column-coupling-initial-state.md` 的初态对照诊断继续。

1. **第 59–62 行（判定）**：可证部分保留 —— 改 rough_b 的幅值后，摘要未变的列读数改变。**收回**"只差 rough_b
   一格的碰撞几何"：cell 摘要取在生成器交出 mesh 时（`terrain_split_probe.py:175-200`），含局部 vertices/faces/
   origin（`terrain_geometry.py:55-80`），**不含** PhysX 烹饪后的碰撞形状、接触、求解器状态或每 env 实际出生状态。
   正确写法 = "生成器交出的几何 + origin 摘要只在 rough_b 改变"，以及"其余通道未控制"。
2. **第 63–65 行（"非局部但也不是全局"）**：**收回**它作为可比性依据的部分。本次未变的四列（flat / slope_5deg /
   gap 两列）只在**本次干预**下相等，不是长期白名单，也不解除"跨协议读数只作测量差异诊断"的约束。
3. **第 66–68 行（hf 列单变量本就不成立）**：**收窄**。被证伪的是"只改 rough_a 配置而保持 rough_b 实现不变"
   这一具体前提，不是"hf 列之间永远做不了单变量"。
4. **第 136 行（功效）**：**错**。与 `2026-10-10-cross-protocol-suite-readings.md` 的勘误同因：completion 是逐 env
   连续比值再取均值，**没有**量化步长；`1/8` 是 `fall_rate` 这类逐 env 二值指标的计数粒度。现行 `success_rate`
   是有效帧加权比例（`eval.py:611`、`metrics.py:175-181`），同样不是逐 env 二值，不适用该粒度。
5. **绑定与复读条件**：ctrl 的 Robot rev 为 `efa2ba75db29`、rougha 为 `751a3a446ae3`、v2 参照为 `e4d1ac7d0a04`；
   三者之间测量实现无差异，但归档没有 dirty/diff 载荷 ⇒ 不能宣称"完整执行代码逐字相同"。第 75–81 行的对账命令
   含 `<run>` 占位符，复读以审核记录给出的完整命令为准；本机 `%TEMP%` 脚本会消失，正文以本记录为准。
6. **入口**：审核不授权新增正式诊断入口或改测量语义；诊断读数只作耦合证据，正式协议变更仍走升版。

未改动：全部读数、几何归档、三次 run 路径，以及"单列干预确实改变其他列读数"这一结论。
