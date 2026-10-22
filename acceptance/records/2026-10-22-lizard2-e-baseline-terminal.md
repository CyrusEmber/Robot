# E baseline 终止前快照实际消费验证

## 适用范围

用户要求在[在线值与 gait 切片](2026-10-22-lizard2-e-live-values-gait.md)后继续执行。本轮承接 `lizard2-candidate-wiring` 的 baseline terminal hook 缺证；新增持久入口 `rl_exp/tools/diagnose/palm_baseline_terminal.py`，复用实际 `baseline_eval.run()`、原 `capture_reset()`、wrapper、termination manager、`BaselineFrames.save()` 与 `baseline_metrics.judge()`。生产 evaluator、冻结协议、正式资产/v3、PD、求解器和训练均未修改，没有新增依赖或默认套件条目。

仅一个固定根、禁重力、零 Kp/Kd 环境，三个控制步，共 0.06 s 的采集窗；第 2 步完成物理后、调用原 termination manager 前，注入有界关节/命令 marker 并把 episode clock 置到原 deadline，从原 timeout term 触发一次 reset。它是显式 synthetic 采集诊断，不是自然超时、跌倒或跟踪。初始化/reset 不计入所述三个控制步，不用该窗口冒充原协议 20 s。

输入仍为已批准 fresh measured manifest：`rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json`，SHA256 `d876713b1a4aa6a4fef51f39bed284f4a15a01d562815eefefcf74eebfb77137`。入口在启动前核独立 manifest 批准及 USD/URDF 摘要；真实环境再核固定根、31 body 禁重力与 `enable_external_forces_every_iteration=False`，不采用 true 对照设置。

## 验收条件

- 真实 collector 只捕获一次终止，timeout 位于第 2 帧，terminated 均为 false；reset 调用的实际 env id 和 control step 留存。
- 30 个实际 runtime 关节按列注入不同值，独立从 backend 在原 reset 前/后读 q，保存帧按自己的 joint axis 对齐，必须等于 reset 前 marker、区别于 reset 后零值；命令 marker 也须跨 reset 可区分。
- 工件与报告都显式标注 synthetic 条件，完整 17 列 finite；保存后再读盘核摘要、首局掩码及 reader 原判词，不修改协议或把 smoke 改成绩效通过。
- 对真实磁盘工件的内存副本做 post-reset 替换、错列、漏 timeout、错命令破坏并拒绝；离线真实 hook 顺序和 selective merge 的破坏也必须失败，便携测试不依赖本机证据。

## 结果

### 真实采集与读回

一次物理启动正常退出 0，`BASELINE_TERMINAL_PROBE_OK`，未物理重试。实际 writer 保存 `report.frames.pt`，报告 `terminal_frames_captured=1`、`smoke_only`；唯一 reset 为 env `[0]`、control step 2。三个 timeout 为 `[False, True, False]`，三个 terminated 均 false。

marker 是按实际 runtime 顺序的 `q[i]=(i+1)*0.001 rad`，最大 0.03 rad；在真实位置限位内，注入时速度为零。原 `capture_reset()` 先取快照，再调用诊断观察器包裹的原 `_reset_idx()`；观察器独立读取 backend q。保存终止帧全部 30 列（含四个 twist）与 pre-reset backend/输入逐值相等，最大误差零；post-reset backend 全零，不能误用它替代 marker。这里证明的是状态写入到 terminal 记录的数值/索引，不是 marker 的物理随动或当前驱动力。

命令 pre-reset 为 float32 的 `[0.17, 0, 0]`，post-reset 为 `[1.3509786128997803, 0, 0]`，保存终止帧保留前者。该变化来自既有 reset 命令采样；未改命令范围或协议。命令 marker 是消费测量，不证明策略响应。

完整 17 列 shape 的前两轴为 `(3,1)` 且 finite。独立显式调用 `_alive/_data_reasons` 得首局掩码 `[True, True, False]`、data reasons 空，包含终止帧并排除 reset 后第三帧；没有依赖短窗 judge 的前退来声称数据有效。原 reader 仍为 `invalid`，唯一原因 `the window is 3 steps x 0.02 s = 0.06 s, but the protocol declares 20 s`；八个 gate 均 null。读盘 `judge()` 与原 `reader_validation` 完整相等。

### 破坏测试与本轮工具缺陷

`test_baseline_contract.py` 新测试 AST 加载生产 `capture_reset()` 与实际 pending merge，核先取快照、再 reset、只替换对应 env；把原 reset 调到快照前，或将 selective merge 改成整批替换，两种真实代码破坏均使测试失败。它是便携离线夹具，不冒充多环境物理采集；生产 hook 本轮未发现需修的错误。

真实 `.pt` 的四种内存破坏均经同一 `audit()` 拒绝：把 terminal joint_pos 换为零/reset 后值、反转关节列、清除 timeout、将 terminal command 换零。报告批准摘要不符的便携负例也被拒绝。原始工件未改写。

初次磁盘回放失败 `frames digest mismatch`：新增工具错误地用裸 hex 比较 collector 报告的 `sha256:` 字段。便携 fixture 使用真实 `baseline_frames.save()` 和 `record.file_sha256()`，修复前测试同样失败；回放改用已有 `record.file_sha256()` 后测试及原磁盘工件均通过。没有改 collector 的摘要格式、原采集文件或断言阈值，没有因此重跑物理。

## 证据引用

本机工件不承诺入仓。目录 `rl_exp/out/lizard2_e_terminal_20261022/attempt01/`：

| 文件 | SHA256（裸 hex） |
|---|---|
| `report.json` | `cb2567ea9508786cd99ff774a807c808b649ee820e2a384bc792047128f72d6b` |
| `report.frames.pt` | `adcbcbd1310ea3cd1510305d436ea8581b97c17edd64fe115c24dcf7e287bb1a` |
| 实际采集入口快照 `source.py` | `e4290cbb46b9eb1bd5d7bd5d80796a16c4afa8eef068c5b75f0a3b2dccbceead` |
| 实际 collector 快照 `baseline_eval.py` | `6b4ea3f3868b37fd39e7782b0ca7e3c9f2afa79331199f88b1c383b019fdb3aa` |

最终诊断入口 SHA256 `0d18b1217484143b2086665628c014bb1e3852128ffc9d0c1c4002e775f935b4`；与采集快照相比只修 `replay()` 的 frames 摘要语义。已 AST 对照 `audit/collect/main` 三函数逐节点相同；不以最终源码冒充此前物理启动源码。collector 本轮无工作树差异。

日志相对 `rl_exp/out/`：`lizard2_e_terminal_20261022_attempt01.log` 为唯一实际采集；`lizard2_e_terminal_replay_20261022.log` 为修复前回放失败；`lizard2_e_terminal_replay_final_20261022.log` 为修复后真实回放与四反例；`lizard2_e_terminal_replay_test_before_20261022.log` / `lizard2_e_terminal_replay_test_after_20261022.log` 为便携红/绿；`lizard2_e_terminal_hook_test_20261022.log` 为实际 hook/merge 测试；`lizard2_e_terminal_data_audit_20261022.log` 为首局/数据及 AST 对照。回放最终退出 0，`BASELINE_TERMINAL_REPLAY_OK`。

本轮完整默认套件退出 0，`ALL_OFFLINE_CHECKS_PASSED (37/37 in 53.8s, jobs=6)`，日志 `rl_exp/out/lizard2_e_terminal_offline_20261022.log`；包含新增真实 hook/merge 破坏与回放摘要便携回归，原条数不变。本轮路径 `git diff --check` 通过，提交前钩子按仓库规则另行执行。

代码提交 `b672d2c` 只含新诊断入口与 `test_baseline_contract.py`；显式提交前钩子和正常 commit 内钩子均退出 0，日志 `rl_exp/out/lizard2_e_terminal_precommit_code_20261022.log`、`lizard2_e_terminal_commit_code_20261022.log`。验收记录与事项指针另笔同次提交；没有纳入并行事项的暂存文件。

无物理复读，从仓根执行：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_baseline_terminal.py --replay rl_exp/out/lizard2_e_terminal_20261022/attempt01/report.json --approved_report_sha256 cb2567ea9508786cd99ff774a807c808b649ee820e2a384bc792047128f72d6b
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_baseline_contract.py
```

显式重采集须换不存在的 out，仅限同一三步条件，不追加自动物理重试：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_baseline_terminal.py --manifest rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json --approved_manifest_sha256 d876713b1a4aa6a4fef51f39bed284f4a15a01d562815eefefcf74eebfb77137 --out rl_exp/out/lizard2_e_terminal_replay/new01 --headless --device cuda:0
```

首局/数据与采集函数差异可直接复算，无需删除后无法复读的临时脚本：

```powershell
@'
import ast
from pathlib import Path
from ablation_harness import baseline_frames, baseline_metrics
base = Path('rl_exp/out/lizard2_e_terminal_20261022/attempt01')
a = baseline_frames.load(base/'report.frames.pt')
alive = baseline_metrics._alive(a['frames']['terminated'], a['frames']['timeout'])
assert alive[:,0].tolist() == [True, True, False]
assert not baseline_metrics._data_reasons(a, alive)
def functions(path):
    return {n.name: ast.dump(n) for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef)}
old, new = functions(base/'source.py'), functions(Path('rl_exp/tools/diagnose/palm_baseline_terminal.py'))
assert all(old[name] == new[name] for name in ('audit','collect','main'))
print('TERMINAL_DATA_AND_COLLECTION_SOURCE_OK')
'@ | & E:/IsaacLab/env_isaaclab/Scripts/python.exe -B -
```

## 未覆盖边界

本轮解除当前 fresh 输入的 synthetic timeout → pre-reset hook → 非零 joint/command → 保存/reader 连通缺证，不能升级成自然 20 s 超时或碰撞跌倒的实际触发行为。没有独立核 17 列中每个根/接触量的非零 terminal 语义，只核其完整性/finite 与本切片两个可区分字段；没有新跑受载、步态、组合驱动或训练。物理环境只有一个，多环境 selective merge 证据来自便携真实代码测试。

非零 gait 报告记录映射、完整 E3 出口与受影响旧基线清点、旧资产 ownership 回交以及 B/D/S5/S6 原边界继续在办。事项仍为 `in_progress`；本记录为执行者自检，不是关闭所需的新上下文审核。
