# harness 代码基线覆盖补齐：判分语义与整腿扩列（2026-10-10）

## 适用范围

- 对象：`ablation_harness/HARNESS.md`「代码基线」段的**覆盖声明**，即 v1.9.0 → v1.10.0 之间哪些改动被算进这次编号、各自凭什么依据。
- 被补的三处：判分侧的 banded / settled 种类与身份（`1fba2b8`、`6de88a0`）、整腿扩列对耦合报告的影响（`601f1d6`）、足端几何来源改为家族声明的 mesh 树（`88f6bd9`）；同一跨度里不计入编号的改动也逐笔写明理由。审核依据见 `acceptance/records/2026-10-10-harness-version-anchor-review.md`。
- 不改实现、不改协议文件、不改已推 tag（`harness-v1.9.0` / `harness-v1.10.0`），不改写任何已落盘的历史记录。
- 不覆盖：这两个判分器家族与步态报告项**是否好用**（数值质量、阈值合理性归各家族版本记录），以及 v1.10.0 之外的后续改动。

## 验收条件

1. 覆盖声明逐笔点名 v1.9.0 之后的测量语义变化，并给出可读的证据指向（记录或实现落点），不再用概括词带过。
2. `601f1d6` 的"报告计算是否变了"有可复读的对照，而不是靠提交正文自述。
3. 编号裁决写明：为什么这几笔落在 v1.10.0 的树里、因此不需要新版本号；已推 tag 不动。
4. 同一跨度里未计入编号的改动逐笔给出理由，不留"没提到"的空白（否则下一次审核会把空白再当漏项）。
5. 离线闸门全绿，证据记录与本项在同一笔变更里落地。

## 结果

### ① 判分侧与足端几何来源（原覆盖声明漏列）

原来只写"帧格式 2 与足端判据、定点场景驱动、身份拒表、帧格式 3 与四条报告项"，没有写判分器在这一跨度里换了身份与种类。实际变化：

| 提交 | 判分器身份 / 协议 | 新增或改变的测量语义 | 实现落点 |
|---|---|---|---|
| `1fba2b8` | `baseline-criteria-banded-1` / `lizard2_flat_v1.json` | `tracking_banded_v1`、`displacement_banded_v1`（带边界 `[lo,hi)`、未归带的帧判失败、位移先求和再除命令距离）；`non_foot_load_sum_v1`（先求和再驻留，`non_foot_carrier_v1` 的 `any` 会漏掉轮流承载）；`gait_swing_v1`（swing 需跑满最短时长且落地帧重新承载） | `ablation_harness/baseline_metrics.py:368`、`:427`、`:497`、`:512` |
| `1fba2b8` | 同上 | 声明了但 reader 从未判的 gate：由"隐形"改为 `invalid`（原 `passed = {}` + `all(...)` 会让漏判的判据不参与判决） | `ablation_harness/baseline_metrics.py:1279`、`:1411` |
| `6de88a0` | `baseline-criteria-banded-settled-1` / `lizard2_flat_v2.json` | `tracking_banded_settled_v1`、`displacement_banded_settled_v1`：命令切换后有 `settle_s` 窗口不计（由实测减速推出，不是由判词反推）；零命令带漂移改为**逐 env 取最差**（原按全 env 求和，读数随批量大小变） | `ablation_harness/baseline_metrics.py:344`、`:472` |
| `6de88a0` | 同上 | 修 `start_pos` 设备混用（meta 仍是 CUDA 张量、帧已是 CPU 拷贝）——该缺陷使位移判据在 GPU 上从未真正出过判词 | `ablation_harness/baseline_metrics.py:448` |
| `88f6bd9` | 同上（无新身份） | 足端几何的来源由默认 mesh 树改为**该 run 用的任务家族声明的树**：读数与 `foot_geometry` 摘要都取实际加载的那棵树（两家族几何不同时，旧写法会把别家的脚读进来） | `ablation_harness/baseline_eval.py:99`、`:180`、`:190`、`:340` |

`88f6bd9` 的其余部分（lizard2 的 rl 脚碰撞壳与家族资产）属资产工作，不归 harness 编号。

身份与种类是可查的冻结面：`judge_semantics.json` 的用例表、各协议文件的 `judge` 与 `criteria[].kind`（`lizard2_flat_v1.json:8`、`v2.json:8`）。协议 `v3/v4/v5` 是身份副本与报告项升级（判据数值不动），不构成新的测量语义，故不在这次覆盖声明里单列。

### ② 整腿扩列：同一输入下报告计算确实变了

`601f1d6` 的提交正文只声明"帧格式不冻结关节列表"，因此是采集变化；但它同时把 reader 的腿关节候选集从三个 token 扩到五个，`spine_leg_coupling` 取的是**躯干关节 × 腿关节的最差相关**，候选集一变，这个数就变。

同一帧输入（64 帧、1 env，`chest_yaw` 与 `haa` 同相、`hip` 正交），分别执行该提交与它的父提交的 `_gait_shape_readings`：

| reader 源码 | `spine_leg_coupling` |
|---|---|
| `601f1d6^` | `5.995425592306487e-18` |
| `601f1d6` | `1.0` |

落点：采集轴 `ablation_harness/baseline_eval.py:54`；候选集 `ablation_harness/baseline_metrics.py:866`（`_LEG_TOKENS`）；读数 `:916`。复读命令见下节（不生成脚本文件、不起仿真）。

结论写法：这仍是**同一版格式 3 的实现细化**，但它属于测量语义变化，覆盖声明必须点名，不能按"只加采集列"豁免。

### ③ 这一段里不计入本编号的改动

编号的准据是"加模块或改测量语义"。同一跨度里其余的 `ablation_harness/` 改动逐笔列出，附不计入的理由——不列出的空白下次还会被当成漏项：

| 提交 | 改了什么 | 为何不计入 |
|---|---|---|
| `4ef9fb4` | 评测启动的 `--headless` 换成显式 `--viz none` | 启动旗标，rollout 与指标计算不变；自身记录在 `acceptance/records/2026-10-10-ablation-harness-headless-flag-replacement.md` |
| `f1e6421` | lizard 家族源码退休后的路径改写 | 只换默认 task 与示例；显式任务下的测量公式未动，自身记录在 `work/closed/2026/retired-family-code-prune.md` |
| `862e39f` | `plot_eval.py` 兼容两种记录、加 gate 图 | 展示层，不重算测量 |
| `21ec102`、`d086fc4` | 协议锚点表与"从目录推导覆盖集合" | 声明一致闸门，不改 rollout 或判分公式 |

### ④ 编号裁决

计进本编号的四笔（`1fba2b8`、`6de88a0`、`601f1d6`、`88f6bd9`）都是声明提交 `925d997` 的祖先，即它们**已经在 v1.10.0 锚定的树里**。缺的是覆盖文本，不是锚点内容 —— 因此：

- 不新开 v1.11.0：那会让同一棵树挂两个号，且已推的 `harness-v1.10.0` 不改指向，重编号反而丢归因；
- 本次改动是覆盖声明的勘误（文档级），按 `versioning.mdc` B 节记 `v1.10.0.1`，只体现在 commit 主题上，`HARNESS.md` 不写修订行（该文件版本史归 git log，见其头部）；
- 代码基线的编号仍是 v1.10.0，`check_version_docs.py` 的基线↔tag 配对不变。

`acceptance/records/2026-09-29-gait-shape-in-the-eval-flow.md` 是 `601f1d6` 之前形态的记录，保持原样：它写的是当时的事实，不就地改成后续状态。

### ⑤ 闸门

`check_version_docs.py`、`check_work_docs.py`、`check_suite_banners.py`、`framework_pin_check.py --strict --self-test`、`check_dr_parity.py --strict`、`check_obs_protocol.py --live` 全绿（读数见 commit 的 pre-commit 输出）。

## 证据引用

### 身份与种类（声明一致）

```bat
git show 1fba2b8 -- ablation_harness/protocols/lizard2_flat_v1.json ablation_harness/judge_semantics.json
git show 6de88a0 -- ablation_harness/protocols/lizard2_flat_v2.json ablation_harness/judge_semantics.json
git show 601f1d6 -- ablation_harness/baseline_eval.py ablation_harness/baseline_metrics.py
```

### 耦合报告对照（行为，可复读）

用 `python ablation_harness\host_paths.py --python` 返回的解释器，以 `-B -c` 执行；依赖仓内 Git 历史与已安装的 torch，不起仿真。

```python
import ast
import subprocess
import torch

t = torch.arange(64, dtype=torch.float64) * 2 * torch.pi / 64
angles = torch.stack((t.sin(), t.cos(), t.sin()), dim=-1).unsqueeze(1)
frames = {"joint_pos": angles}
axes = {"joint_pos": ["chest_yaw_joint", "lf_hip_joint", "lf_haa_joint"]}
alive = torch.ones((64, 1), dtype=torch.bool)
for rev in ("601f1d6^", "601f1d6"):
    source = subprocess.check_output(
        ["git", "show", rev + ":ablation_harness/baseline_metrics.py"], text=True
    )
    tree = ast.parse(source)
    nodes = [
        node for node in tree.body
        if (isinstance(node, ast.FunctionDef)
            and node.name in ("_nan_correlation", "_gait_shape_readings"))
        or (isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name)
                    and target.id in ("_LEG_TOKENS", "MOVING_COMMAND_MPS")
                    for target in node.targets))
    ]
    namespace = {"torch": torch}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), rev, "exec"), namespace)
    print(rev, namespace["_gait_shape_readings"](frames, alive, axes, {})["spine_leg_coupling"])
```

### 落点

- 覆盖声明：`ablation_harness/HARNESS.md`「代码基线」段。
- 审核先例：`acceptance/records/2026-10-10-harness-version-anchor-review.md`。

## 未覆盖边界

- 只补声明与依据，不重评这些判据/报告项当前是否好用；家族侧的判据质量归各版本记录。
- 未跑 GPU rollout；耦合对照只证明"同一输入下报告计算改变"，不产任何策略性能结论。
- 不覆盖 v1.10.0 之后的新改动；下一次加模块或改测量语义仍按「版本纪律」升 minor 并打 tag。
- 本记录不替代审核：覆盖声明的修订是否够，仍由新上下文对照事项 `close_when` 判。
