# 套件列间耦合诊断修复及恢复验证（2026-10-28）

## 适用范围

修复 `acceptance/records/2026-10-28-eval-column-coupling-dynamics.md` 所述诊断工具的独立审核缺陷，验证真实新入口及历史原始数据的本机归档恢复。不改冻结协议、正式评测或历史证据。

## 验收条件

比较器识别无效状态、错误身份、错误干预、不一致重复及不可观察的 reset 前状态；采集不覆盖现有运行；比较结果和身份可追溯；原始证据解包核验并实际复读。不得将本机归档当作异地备份或完整仿真环境。

## 2026-11-03 历史批次显式复读补修

用户选择默认严格、显式复读旧批次。`compare` 默认仍拒绝缺少父进程退出凭据的数据；`--allow_unconfirmed` 或 Python `allow_unconfirmed=True` 可只读比较，并逐臂警告退出状态未知。存在但无效的凭据仍拒绝，未确认数据不能写 `comparison.json`，不补造凭据。旧命令本身依用户选择仍为严格模式；显式选项提供复读路径，不等于旧默认调用行为完全兼容。

自检先因缺少显式入口失败、修后通过；后续对非布尔参数及无凭据写报告的断言分别先红后绿。新上下文限定审核实际复读旧批次与新批次，并在临时副本验证坏凭据、悬空链接、部分缺失和 raw 损坏，结果通过；未运行仿真或整体关单复审。历史环境恢复仍未完成。

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\eval-column-coupling\probe-20261028-b --allow_unconfirmed
```

## 2026-11-03 最新整体独立审核

**不通过，退回执行。** 不带执笔历史的新上下文对照事项关闭条件、当前代码和原始数据审核：单标量对照及可观测候选机制排除满足现有条件；不要求解释所有未观测的 PhysX 内部状态。f/g 四臂初态、退出凭据、摘要、重置标志及分叉读数复核通过，g 的默认全局 RNG 在各采样点一致；不排除采样间状态变化、独立 RNG 或未记录状态，也不将生成器几何视为物理引擎烹饪结果。

当前 `compare` 对旧批次要求原本没有的退出凭据，未经此前版本弃用即改变既有调用行为；须恢复兼容并明确标记退出状态未知，不能补造凭据。历史运行环境依赖仍为 open，源码和资产归档不等于完整恢复。汇总规则在限定范围内通过，但地形长表新增 `source` 列、透视碰撞退出行为对外可见，外部消费者未核验。工作树与退出码等并行事项混属，提交须拆分，不得连同其他事项误提交。未增加维护接收门槛。

审核实际运行现有 `selftest`、f/g 四臂 `compare`、`test_eval_record.py`（59 项通过），并用历史批次原快照比较；当前入口比较历史批次报 `missing exit confirmation: ctrl1`。未运行仿真、policy、完整仓库闸门或历史环境恢复；摘要不证明真实性。本次审核不等于提交或关闭。

## 2026-11-03 工具交接要求勘误

先前把“工具去向可查”扩大为必须指定维护者并正式接收；用户指出没有的流程不要添加。该接收要求不是仓库通用规定，已从活跃事项移除；下文历史审核记录保留原样，不表示这项人为要求仍是待办。诊断工具入口和边界仍保留，历史环境恢复及机制验证未完成，不因此视为通过。

## 2026-11-03 退出确认与复读勘误

下文各段保留当时运行和复读记录。当前 `compare` CLI 已要求每臂有父进程写出的 `exit_status.json`；本记录引用的旧批次没有该文件，严格 CLI 会拒绝，旧命令不能直接复读。原始输出与采集快照保留，不能补造退出确认。固定初态 e 批次的后台运行通知曾报告四臂各退出 0、父进程退出 0，但该通知不在批次归档内。曾由当时支持 `allow_unconfirmed=True` 的当前比较器显式降级复读，现该参数已被并行工作区移除；改用 e 批次采集快照进行只读比较：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\out\runs\eval-column-coupling\probe-controlled-initial-20261103-e\capture_script.py compare rl_exp\out\runs\eval-column-coupling\probe-controlled-initial-20261103-e
```

新上下文及执行者均用 e 采集快照复读通过；这只复核 raw、metadata 和对照，不代替未归档的退出状态。更严格的新批次结果见下文。

## 结果

- 修复有效状态的 NaN/Inf、字段宽度和关节宽度校验，跨臂配置与关节顺序核对，实际干预及 cell 参数绑定，采集脚本快照和 raw 摘要绑定；同臂重复不一致直接拒绝。单边 reset 时显式区分首个可观察差异与可证明的首次差异；初态输出列出环境、地形和字段。
- 原比较器分别接受无效数值和维度、身份及配置变化、同臂差异，并可丢失重置前差异；修复前破坏自测各组报失败，修后自测通过。后续快照缺失/变化、未改变配置、cell 参数解绑、初态详情和新运行快照六类破坏在修前分别失败、修后通过；新增四臂摘要不符的拒绝测试。部分早期测试组在第一个失败处退出，不能声称每个子负例都独立红灯。
- `capture` 改为独占创建新目录；向已存在的临时目录真实调用时返回非零，原 raw 与 metadata 内容不变。新布局兼容历史批次的只读比较。
- 真实新运行四臂各 12 步、72 env，均退出 0；同臂逐位相同，未干预的 stairs_20cm 八个 env 第 10 步出现差异。四臂没有终止或 reset，因此真实 reset 前采集路径仍未被物理验证。
- 新上下文限定范围审核了代码、新批次和历史批次、快照/原始摘要及参数破坏反例，未发现阻断本批结果的缺陷；两个批次前 13 帧逐字段相等。此审核不等于事项关闭审核。
- 历史 100 步四臂 18 个原始文件与比较器依赖快照保存在本机 ZIP；按清单核验、解压到隔离临时目录、逐文件与原件比较并实际运行恢复后的比较器成功。归档不含完整 IsaacLab、资产或当时全部源码；仅是本机副本，未验证外部备份或仿真环境恢复。归档里的比较器快照早于本轮进一步修复，恢复复读时仍须区分其版本和当前源码。

## 证据引用

- 落点：`rl_exp/tools/diagnose/column_coupling_probe.py`；历史数据：`rl_exp/out/eval-column-coupling/probe-20261028-b/`；真实新运行：`rl_exp/out/runs/eval-column-coupling/probe-20261028-184018-12step-a/`。
- 本机归档：`rl_exp/out/archive/eval-column-coupling-probe-20261028-b-3e2f4ca9.zip`，SHA-256 `0071be878933201910ea3cb449e2798785f906c29da27667fd86bca0b6b755f7`。清单与数据同包，仅验证一致性，不能证明真实性。
- 自检与真实新运行只读复算：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py selftest
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\runs\eval-column-coupling\probe-20261028-184018-12step-a
```

- 归档恢复：在 `cmd.exe` 中选择不存在的目录，先校验归档及逐文件摘要，再以归档中的比较器复读。验证通过后只清理自己的临时恢复目录，原件与 ZIP 均保留。

```bat
set "RESTORE=%TEMP%\column-coupling-restore-choose-new"
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B -c "import hashlib,json,pathlib,zipfile,os; p=pathlib.Path(r'E:\Robot\rl_exp\out\archive\eval-column-coupling-probe-20261028-b-3e2f4ca9.zip'); d=pathlib.Path(os.environ['RESTORE']); h=lambda b:hashlib.sha256(b).hexdigest(); assert h(p.read_bytes())=='0071be878933201910ea3cb449e2798785f906c29da27667fd86bca0b6b755f7'; z=zipfile.ZipFile(p); assert z.testzip() is None; m=json.loads(z.read('manifest.json')); assert len(z.namelist())==len(m['files'])+1 and set(z.namelist())=={'manifest.json'}|{x['path'] for x in m['files']}; assert all(len(z.read(x['path']))==x['size'] and h(z.read(x['path']))==x['sha256'] for x in m['files']); d.mkdir(); z.extractall(d); assert all(len((d/x['path']).read_bytes())==x['size'] and h((d/x['path']).read_bytes())==x['sha256'] for x in m['files']); print('verified:', d)"
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B "%RESTORE%\compare_snapshot\rl_exp\tools\diagnose\column_coupling_probe.py" selftest
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B "%RESTORE%\compare_snapshot\rl_exp\tools\diagnose\column_coupling_probe.py" compare "%RESTORE%\data"
```

## 未覆盖边界

本机归档和原件共处一机；未验证外部备份、完整运行环境恢复、PhysX 内部机制或指标放大。关节名依赖 metadata 和日志，摘要不能防整体协调篡改；子进程使用工作区脚本，启动检查与加载间仍有时间窗口。正式独立审核须重新对照事项全部关闭条件，不因本记录或格式检查存在而视为通过。

## 2026-10-30 事项独立复审

**不通过，退回执行。** 新上下文独立运行 `selftest` 和单变量四臂 `compare` 均退出 0，并以 NumPy 对照各臂原始摘要、配置差、逐环境初态、全部 done/reset 和同臂轨迹，复核单臂超时样本与两次失败现场；核实规则条件面和逐地形表边界。它确认该批的受控变量与记录一致，但指出 rough_b 自身初态已变，其他环境、全局 RNG 和 PhysX 内部路径仍未区分：排除 stairs 自身已记录初态和 reset 并不等于排除全部 spawn/RNG 路径，也不坐实引擎内部机制。原关闭条件的机制判定仍未完成。完整历史环境恢复依赖仍开放，拆分不等于恢复。审核未重跑物理仿真或 policy，不将本记录或格式通过视为关闭。

## 2026-10-30 补证：单标量探针

- `rl_exp/tools/diagnose/column_coupling_probe.py` 的 `single_noise_min` 保留四臂零动作与旧批次复读：全部臂的 rough_a 统一采用 v1 配置，干预组相对对照组唯一变化为 rough_b `noise_range` 下限从 0.08 m 到 0.10 m；上限及其他配置均相同。生成器重建及实际采集都显示只有 rough_b 的 cell 记录和几何摘要改变，四臂无生成异常；这不是 PhysX 烹饪后几何的证据。
- 实际四臂 100 步、72 env、seed 123，运行目录 `rl_exp/out/runs/eval-column-coupling/probe-20261030-single-noise-min-c/`。比较器检查四臂脚本快照、输入身份、几何及重复性；独立遍历配置差异确认只有一个叶子不同，同臂轨迹逐位相同。非目标列的六字段初态逐位相同；干预组 rough_b 初态的 `pos` 已不同。两组对照的 stairs_20cm 八个环境在第 10 步出现首个逐位差异，四臂无 done 或 reset。该结果排除目标环境已记录初态差异或自身已记录 reset 造成该次分叉，但不排除未观测的引擎状态、全局随机流消费或其他环境影响；逐位差异本身不证明性能幅度。
- 新比较器对额外改变 `noise_step` 和保持目标几何摘要不变分别做破坏自测；两项在实现对应检查前分别失败，修后均通过。当前比较器只读复算该批次及历史批次，未覆盖已有报告。捕获脚本有来自并行事项的退出状态修复，采集快照和 metadata 记录当时脚本摘要；当前源码身份及完整依赖仍须独立审核。
- 首次批次 `rl_exp/out/runs/eval-column-coupling/probe-20261030-single-noise-min/` 四臂结束后因并行修改 `rl_exp/tools/verify/test_eval_record.py` 导致源码摘要跨臂不一致，比较器拒绝；第二批 `rl_exp/out/runs/eval-column-coupling/probe-20261030-single-noise-min-b/` 因本次脚本变动在第三臂启动前中止。两批原始目录保留，均不作有效四臂结论。
- 规则与工具去向：常驻诊断入口为 `rl_exp/tools/diagnose/column_coupling_probe.py`，不是正式评测或跨套件可比判官；整套件条件面及 `--by-terrain` 未经过该检查的边界见 `ablation_harness/HARNESS.md`。历史运行环境恢复单独保留在 `work/active/eval-column-runtime-recovery.md`；本补证不授权跨协议或单列可比。

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py selftest
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\runs\eval-column-coupling\probe-20261030-single-noise-min-c
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\eval-column-coupling\probe-20261028-b
```

## 2026-10-30 补证：真实超时重置与记录依赖

- 当前诊断器单臂零动作运行 1501 步，72 个环境均在第 1500 步截断重置，无 contact termination；逐环境对账 `reset == truncated | terminated == reset_pre_valid`。六个字段在全部重置环境中的重置前、后样本均有至少一个分量不同；这只能作为采样旁证。时序依赖源码对照：`rl_exp/tools/diagnose/column_coupling_probe.py:772` 在调用原始 `_reset_idx` 前采样，框架的 `manager_based_rl_env.py` 在计算 done 后调用该入口；不证明所有字段的物理真值，也不覆盖接触终止路径。输出及元数据：`rl_exp/out/runs/eval-column-coupling/probe-20261030-reset-1501-ctrl1/`。原始数据及脚本摘要分别为 `26f5d49ceceef705a6ba0406d02a562dd28ba1fe41461cc8dcd9d0acf56baf5d`、`75d4b995d111c3a20a4ade10c0435006c4bd89d21526721a48db98fd07b10d83`；本次单独采集不是四臂对照，后台控制台输出未另存文件。
- 复核历史批次 metadata：82 个资产文件摘要与本机一致；1019 个 Python 源文件中 1016 个与当前工作区一致，另两个与当时 Git HEAD 一致，`test_terrain_geometry.py` 将当时 HEAD 的 LF 转为 CRLF 后与记录的摘要一致。上述核验只覆盖 metadata 中列出的文件，不证明运行时其他依赖完整或来源可信。
- 将这 1101 个已记录源码及资产文件、历史采集脚本和 metadata 归档到本机 `rl_exp/out/archive/eval-column-coupling-20261028-recorded-dependencies-20261030.zip`，SHA-256 `68ff98088e87348c66531370e1bca8c9c8eb93a9fcf57d455661bfb5630c77d1`。归档内清单和 1103 个文件在系统临时目录解压后逐个校验；再从旧数据 ZIP 隔离解压四臂数据，使用恢复的历史采集脚本及恢复的 `host_paths.py` 比较，得到相同的 stairs_20cm 第 10 步分叉。同一环境当前比较器 `selftest` 与历史四臂 `compare` 也通过。
- 恢复验证只覆盖已记录源码、资产和历史比较器的离线复算，不含完整 IsaacLab/Isaac Sim、venv、PhysX、驱动及外部 USD 资产；未从恢复目录重启仿真，未验证异地备份。两个归档和原始数据均在同一台机器，摘要和内容同包只能检验一致性，不证明真实性。新超时采集期间有并行工作区修改，其 metadata 中 3 个源码的运行后摘要已不匹配；未固定完整运行环境。完整历史依赖恢复由 `work/active/eval-column-runtime-recovery.md` 承接；列耦合事项仍须独立复审。
- 新上下文对本补证做了限定范围静态审核：要求把代码调用顺序与前后样本差异分开表述，并指出无法从静态阅读独立执行 raw 复读及工具最终去向未核定。本执行上下文随后运行下列 raw 复读命令通过；该静态审核不是事项整体关闭审核。
- 历史 metadata 未记录当次 Isaac Sim、PhysX、numpy、warp 版本和完整环境包集合；两仓当时有未提交内容。已检索原批次日志、相关归档和安装记录；同日另一次评测的 `ablation_harness/results/locomotion_eval_v3/checkpoint-sweep-v4-20261028/Lizard2-Flat-v4_checkpoint_sweep_v4_20261028_it1_nominal_seed123/record.json` 记录引擎及包版本，IsaacLab HEAD、torch 和 GPU 与本批匹配，但不同进程及时间，不能证明本批运行时版本未变。现有归档可校验已记录文件及离线复算，不能由当今环境或旁证证明历史环境相同。完整恢复不取消、不缩成离线复算，已迁入独立在办事项。

### 可复读命令

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py selftest
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\eval-column-coupling\probe-20261028-b
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B -c "import numpy as np,json,pathlib,hashlib; from rl_exp.tools.diagnose.column_coupling_probe import validate,FIELDS; p=pathlib.Path(r'rl_exp\out\runs\eval-column-coupling\probe-20261030-reset-1501-ctrl1'); m=json.loads((p/'metadata.json').read_text(encoding='utf-8')); assert hashlib.sha256((p/'raw.npz').read_bytes()).hexdigest()==m['raw_sha256']; d=np.load(p/'raw.npz',allow_pickle=False); validate(d); assert m['status']=='complete' and m['step_dt']==0.02 and d['reset'].sum()==72 and d['reset'][1500].all() and d['truncated'][1500].all() and not d['terminated'].any(); mask=d['reset']; assert all(np.any(d['reset_pre_'+f]!=d[f],axis=-1)[mask].all() for f in FIELDS); print('PASS: 72 timeout resets at step 1500, six pre/post fields differ')"
```

## 固定初态探针：实现与首次尝试

- `rl_exp/tools/diagnose/column_coupling_probe.py` 新增单标量干预下的固定初态模式：wrapper reset 后以首臂为参考，写入全部环境的根 link 世界位姿、根 COM 世界速度及关节状态；采集写入前、输入、后端即时回读与实际初始六字段。比较器检查四臂一致、种子重置后的 Python、NumPy、Torch CPU/CUDA 全局随机状态和原始数据身份。回读发生在仿真步之前，不证明 PhysX 内部状态一致或后续步不会修正状态；独立随机生成器、命令及其他未记录状态也未证明一致。
- 当前 `selftest` 通过；在内存中将 `assert_controlled_initial` 替换为无操作后，自测的 `regression_gaps` 与 `controlled_initial_regression` 均失败，未修改源码或历史数据。旧单标量批次及历史批次使用当前比较器均可复读。
- 首次采集 `rl_exp/out/runs/eval-column-coupling/probe-controlled-initial-20261030-d/` 的首臂跑到第 100 步后，源码身份复核报 `capture source identity changed during run`，状态为 failed，其余臂未启动；保留现场，不作四臂结论。

## 2026-11-03 补证：固定初态单标量对照

- `rl_exp/out/runs/eval-column-coupling/probe-controlled-initial-20261103-e/` 四臂独立进程各运行 100 步并退出 0。配置唯一差异为 rough_b `noise_range` 下限 0.08 → 0.10；9 个生成 cell 中只见 rough_b 几何摘要变化。同臂 101 帧六字段逐位一致。四臂采集前后核验的 1116 个源码与 82 个资产摘要一致；摘要及端点检查不证明依赖完整、真实性或中途无短暂改动。
- 新上下文复读 `selftest`、`compare` 并独立核对 raw：参考写入前，干预组 rough_b 的 8 个环境位置不同；写入后全部 72 个环境的参考、输入、后端即时回读及首帧六字段逐位相同，播种后的 Python、NumPy、Torch CPU/CUDA 全局随机状态一致。每臂所有环境的终止、截断和 reset 均为零。跨干预组 stairs_20cm 与 rough_b 各 8 个环境从第 10 步出现首个逐位差异，六字段都有差异。不同臂重置前 NumPy 状态不同，播种后相同不保证后续随机消费相同。
- 第 10 步两组跨臂最大绝对差：根位置 0.0004214644 m、四元数 0.0002972604、根线速度 0.15889156 m/s、根角速度 0.15438312 rad/s、关节位置 0.04021408、关节速度 8.04796028；关节单位依关节类型而定。逐位差异并非策略性能或指标放大的证据。
- 该结果排除本批已记录的 72 环境六字段初始差及已记录 reset 单独解释分叉；不证明 PhysX 内部状态一致，也不能排除独立 RNG、运行时命令、目标缓冲、接触结构或求解顺序等未测通道。即时后端回读发生在物理步之前，不证明求解器内部状态；零动作带默认关节位置偏置。无策略闭环、其他 seed 或外部环境恢复验证。独立审核只针对本批证据，不是事项关闭审核。
- 原 2026-10-28 批次同进程日志显示 venv 的 `site-packages/isaacsim` 路径与 PhysX TGS 告警，且 `enable_external_forces_every_iteration=False`；`Kit/IsaacLab/3.0` 是配置目录名，不是包或引擎版本。另查 `E:/IsaacLab/logs/rsl_rl/lizard2_v6/2026-10-28_15-02-00/run_manifest.json`，它记录另一训练进程的环境声明和仓库状态，不证明本批包版本。检查 `E:/IsaacLab` 根目录 `_diag*.log`、`_eval*.log`、`_probe.log` 未发现可绑定本批的包版本；未查异机备份，不能说来源不存在。完整历史环境仍由 `work/active/eval-column-runtime-recovery.md` 承接。
- 用户目录 `~/.nvidia-omniverse/logs/omni.processlifetime.log` 中 2026-10-28 10:06:32–10:07:01 UTC 的 python 会话与 ctrl1 控制台时间相近；同一 telemetry 会话的 `omni.kit.log` 记录 Kit `110.1.1+production.305458.6312fa25.gl` 和应用 `IsaacLab` 3.0.0。时间相近不等于进程身份绑定，日志未提供可核实的 PID 或命令行对应；应用版本也不是 Isaac Sim 包版本。用户 uv 缓存及当前 venv 均有 `isaacsim` 6.0.0.1 元数据，不能证明其为历史运行所载版本；历史驱动 617.14 则由原 metadata 中的 nvidia-smi 直接记录。仍缺历史引擎及完整依赖身份，不能据此冒称完成恢复。

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py selftest
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\runs\eval-column-coupling\probe-controlled-initial-20261103-e
```

## 2026-11-03 严格退出确认批次

- 新批次 `rl_exp/out/runs/eval-column-coupling/probe-controlled-initial-20261103-f/` 的四个采集进程均由父进程确认退出 0，并保存 `exit_status.json` 与 metadata 摘要；严格比较通过。新上下文独立复核退出确认、脚本和 raw 摘要、单标量与 9 个生成 cell：仅 rough_b 下限由 0.08 改为 0.10，只有该 cell 几何记录变化。
- 四臂各 100 步、72 env；四臂已记录输入、后端即时回读和首帧六字段与参考逐位一致，同臂轨迹重复一致，所有 terminated、truncated、reset、reset_pre_valid 均为零。跨臂的 stairs_20cm 与 rough_b 各 8 env 第 10 步 post-step 出现首个可观察差异；其余 56 env 未观察到差异。四类全局 RNG 重设后的状态一致，但后续消费、独立 RNG、PhysX 内部及其他运行时状态未测；不能将该结果称为机制定位。
- 审核期间工作区诊断脚本发生并行改动，审核者一度遇到签名与 CLI 不一致；随后执行者复读时该不一致已消失，当前 CLI 严格比较 f 批次通过。审查结果只覆盖 f 的采集快照及原始证据，不证明期间任何工作区版本始终稳定。

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\out\runs\eval-column-coupling\probe-controlled-initial-20261103-f\capture_script.py compare rl_exp\out\runs\eval-column-coupling\probe-controlled-initial-20261103-f
```

## 2026-11-03 逐步全局随机状态补证

- 使用 `rl_exp/tools/diagnose/column_coupling_probe.py` 的 `--rng_trace`，对单标量、固定初态四臂逐步记录 Python、NumPy legacy、Torch CPU 和全部 CUDA 默认生成器状态的 SHA-256；运行目录 `rl_exp/out/runs/eval-column-coupling/probe-controlled-initial-rng-trace-g/`。四臂各 100 步、退出确认及严格比较通过；单标量几何与六字段初态检查通过，无记录终止或 reset。
- 新上下文独立复核 raw 及摘要：四臂 0–100 步每个采样点的四类默认 RNG 摘要相同，各臂相对初始状态未变；CUDA 设备数为 1。stairs_20cm 和 rough_b 各 8 个环境仍在第 10 步 post-step 首次出现轨迹差异。g 与未追踪 f 批次对应臂所有共同 raw 数组逐字节相同；不证明采样在其他运行中无时序影响。
- 该结果限制的是所测全局 RNG 在**采样点**的状态，不能证明采样间没有消费后恢复，也不能排除独立生成器、未记录动作/命令或 PhysX 内部状态；读取 CUDA 状态可能影响时序。结果不能用于断定具体引擎机制，也不能推断策略表现。
- 后续评估抬高 rough_b 机器人以隔离地面接触：预检中的地形是共享碰撞体，对 2 个足部建立的地面过滤接触视图可观察到非零力；但现有 USD 包围盒查询对 18 个碰撞 mesh 返回空界限，尚不能证明 8 台机器人的所有碰撞形状在整段试验均离地。故未运行该四臂实验，不凭根位置假称隔离成功；须先核实 shape 界限或完整接触观测的可靠性。

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\runs\eval-column-coupling\probe-controlled-initial-rng-trace-g
```

## 2026-11-03 独立复审

**不通过，事项继续执行。** 新上下文独立核对固定初态四臂的快照、原始数据和单标量几何；以显式 `allow_unconfirmed=True` 复读新、旧批次，并用采集快照比较固定初态批次，重置样本复读通过。已记录的六字段初态差异和 reset 不能单独解释本次分叉，但重播后的随机消费、独立 RNG、其他未记录状态和 PhysX 内部仍未隔离；不能称机制已定位。严格 CLI 缺退出确认时拒绝旧批次，见本记录开头勘误。

复审还确认 `table_conflicts` 对重名 run 的辅助报告可覆盖，主汇总不走该函数；该未完动作仍在主事项。完整历史环境恢复、维护者实际接收、汇总最终复审及整体关单审核均未完成。复审未起仿真、未跑完整仓库闸门或归档解压；本次未将这份限定复读当作整体通过。

新归档的完整性和解压后摘要可用以下命令在系统临时目录验证；清理临时目录不影响本机原件：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B -c "import pathlib,hashlib,json,zipfile,tempfile; p=pathlib.Path(r'rl_exp\out\archive\eval-column-coupling-20261028-recorded-dependencies-20261030.zip'); h=lambda b:hashlib.sha256(b).hexdigest(); assert h(p.read_bytes())=='68ff98088e87348c66531370e1bca8c9c8eb93a9fcf57d455661bfb5630c77d1'; z=zipfile.ZipFile(p); m=json.loads(z.read('manifest.json')); assert z.testzip() is None and set(z.namelist())==set(m['files'])|{'manifest.json'}; t=tempfile.TemporaryDirectory(prefix='column-deps-restore-'); z.extractall(t.name); root=pathlib.Path(t.name); assert all(h((root/k).read_bytes())==v for k,v in m['files'].items()); print('verified',len(m['files'])); t.cleanup()"
```
