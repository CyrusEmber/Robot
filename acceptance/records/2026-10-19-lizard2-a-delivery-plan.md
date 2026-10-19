# A 几何阶段交付计划调整

## 适用范围

2026-10-19 用户要求更新计划，承接本轮“检查是否过多”的讨论。只调整隔离候选总项 A 与肩髋重构、限位 PD 专项的当前执行路由；计划正文仍归 `work/active/lizard2-body-drive-candidate.md` A4。本记录是计划调整依据，不是几何、动力学验收或关闭审核。

## 验收条件

- 三份活跃事项的下一步一致指向 A4，几何交付按回放、机身前移与滑动检查、候选交接推进。
- 复用已绑定证据和已有产物，只补变更或缺证；保留错轴、连接、限位、翻掌、穿地和自碰撞判据及仓库提交闸门。
- 承重 PD、有效限速、时间映射、运行时、躯尾协同、转向/恢复及最终比较仍有责任归属，阶段交付不自动关闭任何事项。

## 结果

支持相位记录已覆盖固定机身下的四肢组合与节点重参数化。旧总项与限位 PD 专项仍把接缝、两腿准备和相位方案列作当前动作，需按实际进展更新；这些历史动作不应成为每轮重复检查的前置链。

仓内已有 `local_path_view.py` 组合回放与根运动前提分析能力（提交 `e415911`）。本机 `rl_exp/out/lizard2_palm_combined_view_20261016_final/` 已有 `analysis.json`、`combined_side.gif`、`combined_top.gif`；分析声明源报告为支持相位报告。此次仅核对文件存在与声明，尚未复核其完整身份、动画内容或动作质量，所以计划要求先核对后复用交付，不称动画尚未生成，也不认定用户已经确认。

总项 A4 作为当前顺序唯一正文；两个专项引用它并保留各自技术责任。P4 明确由 B/C/D 接续，不再作为几何阶段交付完成条件；B/C 开始标定的输入、运行时、惯量和碰撞前提继续保留。几何阶段交付与事项关闭分开，所有状态保持 `in_progress`。

## 证据引用

- 总计划：`work/active/lizard2-body-drive-candidate.md` A4。
- 执行专项：`work/active/lizard2-palm-spatial-reconfiguration.md`、`work/active/lizard2-restored-limits-pd-validation.md` 5a/5b/6。
- 既有组合与支持相位：`acceptance/records/2026-10-16-lizard2-local-path-combined.md`、`acceptance/records/2026-10-16-lizard2-support-schedule.md`。
- 有限采样边界：`acceptance/records/2026-10-16-lizard2-local-path-quarters.md`“用户确认的验证范围”。
- 回放实现与本机产物：`rl_exp/tools/diagnose/local_path_view.py`，`rl_exp/out/lizard2_palm_combined_view_20261016_final/analysis.json`；本机产物引用不承诺入仓。

## 未覆盖边界

本轮不新增动作采样、不修改资产或控制代码，不选择物理周期或限速，不验证无滑移、承重或稳定性。新增根运动工程取值仍按专项集中提出；无变化检查可复用不等于可跳过真实缺陷。未完成动作、用户外观/动作确认及独立关闭审核继续保留，不以本记录存在视为审核通过。
