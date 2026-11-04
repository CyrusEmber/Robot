# 套件列间耦合独立审核（2026-10-28）

## 适用范围

不带执笔历史的新上下文对照 `work/active/eval-column-coupling.md` 的关闭条件、现有证据、实际落点和归档工件审核；不修改冻结协议或实验数据。本次未运行物理引擎诊断，不宣称复现动力学分叉。

## 验收条件

至少完成一组受控干预，明确改变的变量与受影响列，并据此排除或坐实候选机制；核验 wrapper 重置后的起跑态、零动作诊断及未覆盖边界，决定可比性规则和诊断工具去向。

## 结果

**不通过，退回执行。** 已有工件支持一次 rough_b 生成配置干预关联到其他地形列的读数变化；不证明引擎内部路径，也不足以独立核验相同起跑态下的物理分叉。

- 独立离线对账及重建：ctrl 与 v2 的归档地形及 `global`、`segments`、`terrains` 相同；两臂仅 rough_b 的 cell 记录不同，重建的两份地形归档逐字段相等。干预是 rough_b 的 `noise_range`、`noise_step`、`downsampled_scale` 一组配置，而非一个标量。未变列中 `slope_10deg`、`stairs_10cm`、`stairs_20cm`、`rough_a` 的指标变化；详值见前次审核记录。这些摘要采集于生成器输出，不证明 PhysX 烹饪后碰撞形状和求解状态相同。
- 原记录称 wrapper reset 后未改列六字段相同，零动作第 10 步 stairs_20cm 分叉；源码流程与 wrapper reset 后采样一致，但当次原始日志及临时脚本均已消失，无法独立对账。12 位截断 SHA-256 相等是摘要相等，不是原始张量逐位对比；结果表九列但仅八个数据格，无法确认错位原因。
- 原探针未抑制 auto-reset，也未保存逐环境 done、reset 和分叉时间。单边先终止重置可能制造差异，原记录称 reset 只会掩盖而不会制造分叉，缺证据。应禁用自动 reset，或记录逐 env 的 done、reset 前状态及首次分叉时间，证明目标 env 在分叉前未重置；保留逐环境状态和两臂同条件重复对照。
- 原复读命令没有把运行输出保存为比较器所需的输入，比较器硬编码临时路径；记录虽包含脚本正文，命令不能原样完成对账。重新生成证据时须提供完整可执行入口、输入及代码身份，缺行应失败；保留原始证据和失败现场。
- 不将“任意改套件，所有未变列一定改变”写为事实；一次实验未变的列也不是可比白名单。现有 `record.py` 条件面按整套件的配置及几何摘要拒绝不一致行，现阶段不新增列级可比框架或修改冻结协议。诊断原型依赖临时脚本及未固定的内部接口，先修复复读和行为证据，再决定是否需要常驻工具；当前不能将该未决动作视为已完成。

## 证据引用

- 原始结果、归因审核和后续诊断：`acceptance/records/2026-10-10-eval-column-coupling-probes.md`、`acceptance/records/2026-10-10-eval-column-coupling-review.md`、`acceptance/records/2026-10-10-eval-column-coupling-initial-state.md`。
- `rl_exp/tools/verify/terrain_split_probe.py`、`rl_exp/tasks/terrain_geometry.py`、`ablation_harness/eval.py`、`ablation_harness/record.py` 的条件面；地形独立重建命令见前次审核记录的证据引用。
- 本次执行的归档对账命令：

```bat
python -B -c "import json,pathlib; r=pathlib.Path('ablation_harness/results'); c=r/'locomotion_eval_v3/coupling-probe/Lizard2-Flat-v3_probe-ctrl_nominal_seed123'; p=r/'locomotion_eval_v3/coupling-probe/Lizard2-Flat-v3_probe-rougha_nominal_seed123'; v=r/'locomotion_eval_v2/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123'; load=lambda x:json.loads(x.read_text(encoding='utf-8')); cg,pg,vg=[load(x/'terrain/geometry.json') for x in (c,p,v)]; ce,pe,ve=[load(x/'eval.json') for x in (c,p,v)]; print('ctrl_v2_cells_equal',cg['cells']==vg['cells']); print('changed_cells',[(a['sub_terrain'],a['geometry']==b['geometry']) for a,b in zip(cg['cells'],pg['cells']) if a!=b]); print('ctrl_v2_metrics_equal',all(ce[k]==ve[k] for k in ('global','segments','terrains'))); print('changed_terrains',[n for n in ve['terrains'] if ve['terrains'][n]!=pe['terrains'][n]])"
```

输出分别为 `True`、`[('rough_b', False)]`、`True`，以及 `slope_10deg`、`stairs_10cm`、`stairs_20cm`、`rough_a`、`rough_b`。上述命令和重建只验证归档与几何，不验证动力学。

## 未覆盖边界

未运行实时仿真或 policy，不证明内部机制、定量放大或其他 seed/资产适用性；自动 reset、未测的内部状态和实验代码身份仍须控制。整套件条件面不是任意手工跨结果比较的强制约束；诊断报告不是正式测量协议。补证后须由不带执笔历史的新上下文重新审核。
