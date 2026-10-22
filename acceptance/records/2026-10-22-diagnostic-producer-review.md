# 诊断生产试点及迁移修复独立复审

## 适用范围

本上下文未参与实现，按 `work/active/diagnostic-artifact-lifecycle.md` 阶段 1、迁移前置表及关闭条件，独立核对源码、现存回归、真实保留运行和本机证据。审查基线为 `8c986266facb5d84b7ed0575463b4f724bbc54ba`；运行测试时 `artifact_run.py`、`artifact_paths.py`、`local_path_view.py`、索引没有本轮未提交变更。审查期间父上下文收到反例后另补回归，不属于本记录的修复后验收。

范围为原三项迁移修复，以及 `local_path_view.py` 的写前归属和登记、独占、真实 drive/root_translation CLI、故障留存、只读检查、完整 Git 换根和图像再生成。没有修改主实现、原保留运行、索引或其它会话文件，没有提交。临时破坏仅针对自动清理的复制品。

## 验收条件

- 隔离须拦实际哈希读取，直接读取破坏探针先失败；drive 摘要取实际映射读点；代码和证据换根保留完整 FK 身份、摘要及 BUILD 授权。
- 写第一份图像前登记主题、事项、执行者、输入和代码身份、复跑命令；目录独占，正常收尾有完整输出和保留决定。
- 部分写入、登记、初始或终端记录失败、kill 后保留现场且检查拒绝；检查不得把缺失或损坏的绑定当成功。
- 真实 CLI 同带 drive 和根平移；同名重跑文件与索引不变。代码、输入、索引、属性经真实 add/commit/clone，两个 autocrlf 设置均核字节、阻断旧仓读取、生成全套图像并比较内容；自己的恢复目录清理。
- 原缺陷有修前失败证据及修后行为证明；阶段 1 通过不能代替入口推广、存量闭合和交接，不能关闭总事项。

## 结果

**阶段 1 本次独立复审不通过：发现一项 P2。原三项迁移修复在本次范围内通过。总事项继续保持未关闭。**

1. **P2：只读检查把空输入/代码绑定当作有效完成。** 基线 `rl_exp/tools/diagnose/artifact_run.py:180` 直接遍历 `record['inputs'] + record['code']`，没有恢复创建时要求非空的约束。复制真实完成运行到临时新根，仅将 `run.json` 的 `inputs`、`code` 清为 `[]`，保留原八份产物及唯一索引；临时根没有任何源码、版本声明或原始输入。实际 `inspect_run` 仍返回 `state=completed`、`output_count=8`。原清单有 45 项输入、13 项源码，因此这是可观察到的绑定丢失，不能用零次循环证明身份成立。应在检查入口显式验证输入和代码分别为非空列表、绑定行结构及必需身份字段，再执行摘要核对；补两者清空、仅输入清空、仅代码清空的破坏回归。清空绑定应拒绝，原有效运行应继续只读通过。复现不需要修改任何生产源码或原始证据；它不是对恶意编辑的签名防护要求，而是检查器对无绑定完成记录的基本拒绝能力。

其余已核验行为如下：

- 生命周期回归独立运行 **10/10 通过，36.829 s**。审阅实际 writer 接入和各注入点：第一份图像前检查 `run.json` 为 running 且索引已有登记；覆盖部分 GIF 后异常、登记 replace 失败、初始记录写失败、终端持续失败与单次失败、输入改变、输出损坏、登记丢失，以及真实子进程写部分文件后 kill。kill/终端不可写保留未完成状态和归属/下一步；初始记录完全不可写时只有空目录，未登记、未写图像，不宣称该空目录具有完整归属记录。现有回归没有覆盖上述空绑定反例。
- 原迁移回归独立运行 **10/10 通过，41.453 s**。两档新根子进程各六种直接读取/真实哈希探针均被拒绝，正向旧仓读取为零；完整逻辑路径和 FK 摘要仍校验，改坏 FK、相同 basename 的异位源码、伪造 BUILD 路径均拒绝。drive 旧根不可读和冲突副本测试通过，真实 `_run` 写出的摘要非空且取映射位置。优化模式回归 **3/3 通过，66.047 s**。
- 真实运行 `rl_exp/out/runs/local-path-view/support-drive-root-20261021-final/` 的初始只读检查通过。另对索引及运行内九个文件作前后摘要快照，再调用检查，**十个文件字节均未变化**。运行有四张轨迹 PNG、两份各 109 帧 GIF、根平移 PNG、分析及运行记录。亲自查看根平移和 lf 轨迹 PNG，以及自行抽取的两份 GIF 第 0/54/108 帧：网格、掌标记、相位与根位移有实际内容，根 x 从零推进约 0.05061 m，说明文字区分播放与物理时间。轨迹图图例较密，但不影响本次生命周期判定；未重审机器人或物理结论。
- 完整真实恢复独立运行成功：`core.autocrlf=true/false` 分别对 **60 文件**真实 add/commit/clone，原始/blob/检出字节一致，移除 source 后由 clone 中代码完整执行 CLI，同时带 drive 和根平移。每档三个旧仓读取探针被拒绝，正常旧仓读取为零；全部 PNG 和 GIF 的所有帧像素相等，根平移、根前置、时间前置和各腿分析相等。drive 摘要均为 `36344c8af1ccf56552c931d252008fb50a9b6951265e8fe083f2079bd340d115`。真实同名重跑拒绝且原文件及索引不变。日志确认恢复临时根已移除。
- 查阅原修前日志：生命周期四项在第一份图像前无归属记录处失败；隔离真实 hash 未被拦、drive 错摘要及 writer 空摘要有明确失败；补齐声明后新根 FK 拒绝、BUILD 授权错误也分别有失败日志。最初缺 `assets.json` 的 fixture 错误未算修前证明。原中间运行清理账仍在，所列两个替代目录实际均不存在；本次恢复再次证明保留运行可再生成。

本轮配置 Python 首次在沙箱中启动被 uv trampoline 以 permission denied 拒绝，随后按正规 `require_escalated` 成功运行；不是测试逻辑失败。

## 证据引用

- 事项：`work/active/diagnostic-artifact-lifecycle.md` 阶段 1、迁移前必须补齐、关闭条件。
- 源码：`rl_exp/tools/diagnose/artifact_run.py:168`（`inspect_run`，缺口在基线第 180 行）、`artifact_paths.py`、`local_path_view.py`、`palm_spatial_runtime.py:check_build`。
- 本机独占日志目录：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-independent-review/`。`lifecycle.log`、`relocation.log`、`optimization.log`、`inspect.log`、`real-recovery.log` 保存本次独立复跑；`readonly-qa.log` 保存只读快照和替代目录核验；`combined_side.gif.qa.png`、`combined_top.gif.qa.png` 为本次实际抽帧。
- `empty-bindings-counterexample.log` 保存真实反例输出：`original bindings: 45 13`；清空后检查仍为 completed；临时根源码/版本目录均不存在。临时复制品已随 `TemporaryDirectory` 清理，原运行未改。
- 已核原始修前证据：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261021-review-fixes/` 的 `red.log`、`code-root-red.log`、`runtime-root-red.log`、`drive-run-red.log`；`20261021-producer-proof/lifecycle-red.log`、`interim-cleanup.json`。执行记录为 `acceptance/records/2026-10-21-diagnostic-artifact-review-fixes.md`、`2026-10-21-diagnostic-producer-lifecycle.md`。

独立反例可在仓根把以下 Python 经 PowerShell 单引号 here-string 管道送入配置解释器 `-B -`，不留下仓根临时脚本：

```python
import json, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, 'rl_exp/tools/diagnose')
from artifact_paths import ArtifactPaths
from artifact_run import inspect_run
source = Path('rl_exp/out/runs/local-path-view/support-drive-root-20261021-final')
with tempfile.TemporaryDirectory(prefix='independent-manifest-review-') as tmp:
    root = Path(tmp)
    output = root / 'rl_exp/out/run'
    shutil.copytree(source, output)
    record = json.loads((output / 'run.json').read_text())
    record['inputs'] = []
    record['code'] = []
    (output / 'run.json').write_text(json.dumps(record))
    index = root / 'artifact_index.json'
    index.write_text(json.dumps({'format': 1, 'packages': [{
        'logical_root': 'rl_exp/out/run', 'current_location': 'rl_exp/out/run',
        'run_record': 'rl_exp/out/run/run.json'}]}))
    print(inspect_run(output, ArtifactPaths(index, root)))
```

正向复读入口：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_artifact_run.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_artifact_relocation.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_local_path_optimization.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_artifact_run.py --real_run rl_exp/out/runs/local-path-view/support-drive-root-20261021-final
```

## 未覆盖边界

本记录保留发现时的不通过结论；后续修复改变实现或绑定后必须另行复核，不能以本记录当作修复后通过证明。没有为本次纯审查重跑全仓离线套件，未宣称其它会话工作树通过；现有执行记录中的全仓结果仍属其各自基线。

只审核阶段 1 及原三项修复；阶段 2 的其它继续使用入口、`diagnose_support.py` 另一输出根和真实同名写入、阶段 3 存量/混合子树/外部备份、阶段 4 交接均未完成独立关闭审核，不能关闭总事项。此次恢复限定当前 Windows/Python/绘图库环境，忽略产物仍为本机证据；临时 Git 恢复成功不等于已有异地备份。审计钩子不是 OS 权限沙箱，磁盘绑定不是不可变执行快照，也不提供对任意重写有效清单的签名保护。未重新采物理、启动 Isaac/训练或修改资产与判据。
