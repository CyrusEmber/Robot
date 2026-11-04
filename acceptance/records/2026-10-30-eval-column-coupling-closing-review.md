# 套件列间耦合关闭审核（2026-10-30）

## 适用范围

不带执笔历史的新上下文对照 `work/active/eval-column-coupling.md` 的关闭条件、原始数据、比较器、诊断和评测落点审核。审核时工作树包含并行会话未提交改动；未启动仿真、修改数据或运行完整离线套件。

## 验收条件

核验单变量探针、受影响列及候选机制，原始数据和身份、复读入口、比较器破坏验证、规则与工具去向，以及历史环境恢复事项的迁移；明确无法成立的结论和缺口。

## 结果

**不通过，退回执行。** 后续单标量四臂数据支持该批次目标环境的状态分叉，尚不能证明具体引擎或 RNG 通道、策略指标放大；事项引用的旧初态记录仍以无条件语气归因，且未提示其复读入口失效。

- 独立遍历四臂配置，唯一叶子差异为 rough_b `noise_range` 下限 0.08 m → 0.10 m；只有该地形 cell 记录变化。配置单标量不等于物理状态只有一项变化。
- 独立对账原始数组：同臂六字段逐位一致；跨臂初态仅 rough_b 的 env 48–55 不同；stairs_20cm 的 env 32–39 在第 10 步首次出现可观察差异。四臂没有记录到 done 或 reset。零动作排除策略/观测闭环和指标聚合作为该批次分叉的必要条件；不能排除未记录的引擎状态、全局随机流或其他环境影响。生成器摘要不证明 PhysX 烹饪后碰撞形状相同。
- 四臂 raw 哈希与 metadata 匹配，采集脚本快照互相及与当前脚本一致；metadata 中 1026 个源码文件、82 个资产文件的摘要与本机一致。这只验证本机一致性，摘要和 metadata 可协调修改，关节名依赖 metadata，不能证明来源真实性或完整运行环境。
- 比较器对两批数据的只读复算及 `selftest` 通过；另在内存将 `bits_differ` 替换为始终无差异，测试拒绝，恢复后自检通过。旧补证已说明部分破坏测试组在首个失败处退出，不能称每个子负例均独立证明修前失败。
- `acceptance/records/2026-10-10-eval-column-coupling-initial-state.md` 原批次没有逐环境 reset 和首次分叉记录，不能排除单边 reset 制造差异；原始日志及临时脚本缺失，原命令不能原样对账，截断摘要也不证明原始张量逐位相等。该记录未标明结论已被否定，不能由新批次反向补证；详见 `acceptance/records/2026-10-28-eval-column-coupling-independent-review.md`。
- 常驻诊断工具已落地；`ablation_harness/record.py` 的汇总条件面包含整套件摘要，`--by-terrain` 不经过相同检查，该边界由 `ablation_harness/HARNESS.md` 明示。未变列不是跨套件可比白名单。
- `work/active/eval-column-runtime-recovery.md` 保留历史环境来源追索、隔离恢复、真实运行和独立审核，仍为 open。本机两个 ZIP 的外层摘要及 ZIP 完整性通过，但不是异地备份或完整仿真环境；迁移不等于恢复完成。

## 证据引用

- 关闭条件与工具：`work/active/eval-column-coupling.md`、`rl_exp/tools/diagnose/column_coupling_probe.py`、`ablation_harness/HARNESS.md`。
- 四臂数据与复读入口：`acceptance/records/2026-10-28-eval-column-coupling-repair.md` 的“2026-10-30 补证：单标量探针”；历史批次及超时 reset 的边界和入口亦见该记录。
- 本次执行：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\runs\eval-column-coupling\probe-20261030-single-noise-min-c
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py compare rl_exp\out\eval-column-coupling\probe-20261028-b
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\column_coupling_probe.py selftest
```

两批比较及自检通过；另按修复记录的超时 reset 命令复读，观察到 72 env 在第 1500 步 timeout，六字段前后不同。配置、数组、文件摘要与 ZIP 独立对账使用只读 Python；本记录不将其结果当作完整仿真环境恢复。

## 未覆盖边界

未复跑物理仿真或策略，未验证引擎内部路径、定量指标放大、其他种子或资产；timeout 证据不覆盖接触终止。整套件条件面不强制约束所有手工比较。旧记录须勘误并指向复核和新证据，修订后须由不带执笔历史的新上下文重审；历史环境恢复继续由依赖事项承接。
