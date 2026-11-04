# 套件列间耦合：受控零动作动力学补证（2026-10-28）

## 适用范围

针对 `acceptance/records/2026-10-28-eval-column-coupling-independent-review.md` 中的初态、自动重置和复读缺口，使用 `rl_exp/tools/diagnose/column_coupling_probe.py` 诊断；不改变正式评测、冻结协议或原始结果。本记录汇总执行与独立审核，不代表修复后的最终独立审核。

## 验收条件

对照各自重复，逐环境、逐字段比较 wrapper reset 后起跑态及后续状态，核验分叉前的终止与重置；保存真实输入、日志、原始状态及身份，明确无法观察的环节。诊断自身缺陷须有修前红、修后绿的破坏测试。

## 结果

- 真实仿真在单机 RTX 3060 Ti、nominal、seed 123、72 env 下运行 ctrl 和 rougha 各两次，零动作 100 步。两次同臂重复的六字段全程逐位相同；两臂 64 个未干预列环境起跑态六字段逐位相同，rough_b 自身 8 个环境初态不同。
- 两组跨臂比较中，未改生成器几何摘要的 stairs_20cm 环境 32–39 到第 9 步相同，第 10 步六字段出现差异。四次运行所有 env 的 terminated、truncated、reset 均为零：排除本批分叉由记录到的自动重置直接引起，但不排除未记录的引擎内部状态差异。
- 配置干预是 rough_b 的 noise_range、noise_step、downsampled_scale 一组生成参数；生成器输出的 cell 记录仅 rough_b 变化。这不是单一标量干预，也不证明烹饪后碰撞形状或求解状态相同。本次未定位 PhysX 内部路径，未量化如何放大为策略指标差异；其他 seed 和资产未验证。
- 不带执笔历史的新上下文独立核验四份原始数据摘要、记录的源文件和资产摘要、101 帧状态形状及有限值、逐位对比与 IsaacLab reset 调用链；未重跑物理仿真。审核发现比较器忽略 reset 前状态、接受零宽字段和终止而无 reset；本批无 reset，不推翻本批对账，但工具不能因此视为已验收。
- 在同一 `selftest` 命令下，比较器修前对 reset 前差异、零宽字段、无 reset 的终止三个破坏样例失败；修后五组样例通过。修后只读重算本批仍得到相同分叉。单边 reset 没有另一臂的 reset 前采样，比较器将该时间标为不可比较，不能断言首次分叉时刻。
- 两臂归档和原始文件位于本机忽略目录，当前无已验证备份或恢复路径。运行时采集脚本快照与当时元数据绑定；当前脚本的比较器已修复，不能将当前脚本摘要误认为当次采集摘要。两个仓当时均有未提交变化，HEAD 不足以重建完整运行环境。

## 证据引用

- 采集数据与命令：`rl_exp/out/eval-column-coupling/probe-20261028-b/` 下四个运行目录的 `command.json`、`console.log`、`metadata.json`、`raw.npz`；当次采集脚本为该目录的 `capture_script.py`。比较报告为捕获时版本所生成；修复后用当前工具只读重算，不覆盖原报告。
- 复读现有数据及工具自检：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py selftest
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\eval-column-coupling\probe-20261028-b
```

- 新运行须在等效 IsaacLab 和资产环境下指定不存在的目录：`E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py run --output <新运行目录> --steps 100`。运行时脚本快照按自身路径推导仓库根，不能直接作为可搬迁入口。
- 前次审核和地形重建复读：`acceptance/records/2026-10-28-eval-column-coupling-independent-review.md`、`acceptance/records/2026-10-10-eval-column-coupling-review.md`。

## 未覆盖边界

数据仅本机保存；需确认证据保留、恢复和诊断工具常驻方案，修复后需由不带执笔历史的新上下文审核。历史 probe 因复读链不全，不以新结果补写其原始日志；本次结果不授权跨套件单列可比，也不改变正式协议。
