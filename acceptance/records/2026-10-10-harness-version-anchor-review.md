# harness 版本锚点审核：远端锚点成立，覆盖声明待补证（2026-10-10）

## 适用范围

- 对象：`work/active/harness-version-anchor-missing.md` 的独立审核，按其 `close_when`、`next` 与落点核查，不以事项正文的完成摘要代替证据。
- 落点：`ablation_harness/HARNESS.md`「代码基线」段。
- 版本边界：`harness-v1.9.0..harness-v1.10.0` 的实际提交与补丁；另核实远端 tag，而非只读本地 ref。
- 本次只回填审核结果，不修改 harness 实现、基线覆盖声明、历史证据或已推 tag。

## 验收条件

1. `git ls-remote --tags origin` 同时列出两枚 tag，分别指向对应版本声明提交；提交主题以该版本号开头。
2. `HARNESS.md` 的代码基线与较新 tag 对应，不留敞口段，列出的四份记录均存在。
3. 按事项 `next` 的覆盖审查要求，核对旧基线之后的测量语义变化是否都被当前声明及引用证据解释；不能以“代码已进 tag”替代“覆盖已解释”。
4. 锚点检查与语义覆盖检查分开判。可就地补证的缺口退回 `in_progress`；补齐后由新上下文复审，不能本次直接关闭。

## 结果

**审核不通过，事项退回 `in_progress`。远端锚点部分通过；语义覆盖声明不完整。**

### ① 锚点、声明与记录路径

远端实际读数：

| tag | 远端指向 | 声明提交主题 |
|---|---|---|
| `harness-v1.9.0` | `0c3ec25ac92c0aaaf8bd8755ea26e43f0022eefb` | `harness-v1.9.0: declare the version, log the anchor it needs` |
| `harness-v1.10.0` | `925d99781a177d36b62db215f0ed949811f4f17a` | `harness-v1.10.0: declare the baseline, and anchor it together with v1.9.0` |

前者是后者祖先，`git merge-base --is-ancestor` 退出码为 0。当前 `HARNESS.md` 代码基线为 v1.10.0，无敞口段；其列出的四份验收记录均存在并已阅读。

这些形状检查符合事项 `close_when` 的明文条款。退回依据是事项 `next` 另要求的“是否漏掉测量语义变更”审查，不是 tag 缺失、指错或记录文件不存在。

### ② P2：分段判分器与 settled 语义漏列

- 声明落点：`ablation_harness/HARNESS.md:34`；待清理的重复覆盖摘要原在 `work/active/harness-version-anchor-missing.md:18`。
- 实际变化：`1fba2b8` 新增分段 tracking/displacement、非足总载荷与完整 swing 判据，并把声明但未执行的 gate 判为 `invalid`；`6de88a0` 增加 settled reader，排除命令切换后的窗口，将零速漂移由跨 env 求和改为最差 env，并修正 CPU 帧与 CUDA 起始状态混用。
- 实现定位：`ablation_harness/baseline_metrics.py:344`、`:427`、`:472`、`:497`、`:512`。
- 两笔均处于实际 tag 区间，不是只增加独立协议文件。当前覆盖摘要的“帧格式 2 与足端判据、定点场景、身份拒表、帧格式 3 与四报告项”未解释这些判分规则。
- 四份引用记录分别证明采集、定点命令、身份拒表与步态报告；第一份明确不覆盖判据内容，第二份明确不覆盖阈值与协议版本，不能借它们推导分段判分器与 settled 语义已被说明。

### ③ P2：整腿扩列同时改变耦合报告，不只是采集变化

- 提交：`601f1d6`，在实际 tag 区间内。
- `ablation_harness/baseline_eval.py:54` 增加 `haa/kfe` 采集轴；同笔也扩大 `ablation_harness/baseline_metrics.py:866` 的 `_LEG_TOKENS`，直接改变 `:894` 的腿关节集合和 `:916` 的耦合候选配对。
- 提交正文以“格式不冻结关节列表”解释无需新格式、协议或锚点。该理由只能解释列轴变化，不足以证明报告计算未变。
- 主审核上下文执行同一输入的父提交/该提交函数对照：64 帧、1 env，`chest_yaw` 与 `haa` 同相，`hip` 正交。

| reader 源码 | `spine_leg_coupling` |
|---|---|
| `601f1d6^` | `5.995425592306487e-18` |
| `601f1d6` | `1.0` |

该变化由 reader 的候选集合造成，不依赖仿真或策略变化。当前引用的 `acceptance/records/2026-09-29-gait-shape-in-the-eval-flow.md:33`、`:69` 仍描述首次落地时的旧轴集合；它是历史记录，不应就地改写为后续状态，应补后续变更证据。

### ④ 版本号判断

上述改动已进入 v1.10.0 的锚定树，不能说代码“未锚定”。本审核确认的是覆盖说明与证据漏项；现有规则不足以仅凭多笔语义变化就断言必须改成 v1.11.0。已推 tag 保持不动，本次不作新编号裁决。

## 证据引用

### 远端与提交边界复读

```bat
git ls-remote --tags origin "harness-v1.9.0" "harness-v1.10.0"
git show -s --format="%H %s" 0c3ec25 925d997
git merge-base --is-ancestor 0c3ec25 925d997
git log --format="%h %s" 0c3ec25..925d997 -- ablation_harness/baseline_metrics.py
git show 1fba2b8 6de88a0 -- ablation_harness/baseline_metrics.py ablation_harness/judge_semantics.json
git show 601f1d6 -- ablation_harness/baseline_eval.py ablation_harness/baseline_metrics.py
```

### 耦合报告对照复读

用 `ablation_harness/host_paths.py --python` 返回的现有 IsaacLab venv 解释器，以 `-B -c` 执行以下代码；依赖仓内 Git 历史与已安装的 torch，不生成脚本文件，不起仿真。

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

### 已阅读的覆盖记录

- `acceptance/records/2026-09-23-baseline-frames-format-2-foot-reading.md`
- `acceptance/records/2026-09-23-baseline-fixed-scenes.md`
- `acceptance/records/2026-09-23-diagnostic-row-identity-gate.md`
- `acceptance/records/2026-09-29-gait-shape-in-the-eval-flow.md`

## 未覆盖边界

- 不重新评价 `video_matrix.py` 的实现，不审核另项 `harness-baseline-tag-gate` 的破坏测试。
- 未跑 GPU rollout；耦合对照只证明同输入下报告计算改变，不给任何策略性能结论。
- 不承诺修复了两个缺口，也不改原有历史证据；后续补证与覆盖声明修订完成后需重新独立审核。
- 本记录不对 tag 区间之外的后续代码改动作完整性判断。
