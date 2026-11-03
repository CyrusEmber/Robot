# lizard2 旧脚板方案替代关闭独立审核

## 适用范围

本审核由不带方案执笔历史的独立上下文执行，对照实际文件、既有原始报告及用户“误生成的文件也加入一下方案。然后关闭掉之前的脚板方案”的指令，审核 `lizard2-foot-design-tradeoffs` 与 `lizard2-two-axis-feet` 是否可以由 `lizard2-round-feet` 替代关闭。两项审核时均为 pending_review；本轮仅文档纳管，不实施资产或代码修改，不运行仿真或训练，不提交。

## 验收条件

- 旧事项未完动作有明确活跃承接，必要性、抬身、接触与学习策略研究不因关闭被取消。
- 三份圆足代码及 candidate01 现场实际存在、进入圆足方案，失败和未执行阶段仍可查；不能以文件存在或结构测试代替物理能力验收。
- 当前交接不得继续指向已关闭实施入口，不沿用退休基线作为新的匹配对照。
- 关闭类型为 superseded，保留原 id 与历史证据，superseded_by 为 lizard2-round-feet；归档时去掉 next、补 outcome，并同次挂本审核记录。最终移动落点另复核。

## 结果

**独立审核通过，允许两项按 superseded 移入 work/closed/2026。** 本结论只批准事项替代关闭，不是脚板、双轴、圆足或驱动能力通过，也不批准正式机体采用或训练。

1. 对照旧事项正文及 HEAD 中的双轴动作清单，圆足事项交接节保留了原腕反向偏差、受载保持与正负响应、踮脚路径失配、限位、实际力矩/饱和、接触观测、轴向/组合范围、自碰撞、几何、惯量、一致性与版本接线缺口；F-convex 作为未启动备选保留。旧方案详细条件继续留在归档，不要求圆足先完成这些研究。
2. 必要性与整腿可达性仍归活跃的 lizard2-foot-plate-necessity，受控抬身仍归 lizard2-two-foot-body-lift；接触测量和学习性能分别有活跃的 lizard2-contact-protocol、lizard2-learned-gait 承接。独立审核发现必要性下一步仍以退休 v2 为默认对照且混列锁死/移除；执笔者修正后重新读取，现已要求当前可复现基线，锁死与移除分别定义，历史 v2 不充当匹配对照。此缺口已消除。
3. 已实际读取三份圆足代码，检查 candidate01 文件树、candidate.json、probe01.json 与日志；候选 URDF、USD、网格、预览、转换配置和记录均存在。重新计算 candidate.json 列出的 30 个候选文件摘要，无不匹配；probe01 对候选清单、USD、当前探针脚本的摘要也匹配。这证明本次文档指向真实现场，不证明候选设计正确。
4. 原始 probe01 的状态为 stopped_before_reset，仅有 hold 阶段 73 帧，末帧 1.46 s、done=true、根高约 0.4547 m；explicit_reset_checked=false。记录中的 26 关节、26 动作、策略观测形状 [1,90]、四球体与自碰撞 false 均可从原始字段核对。探针源码在保持阶段后才执行显式 reset 和响应，因此保留“动作/reset 未完成”边界成立；初始化曾调用 reset 不等于独立 reset 验证通过。结构测试代码仅检查结构契约，本审核未运行测试或物理程序。
5. 复核活跃事项中的旧 id/路径引用，除了圆足的来源说明，没有其它事项继续把旧两项作为当前实施承接入口；必要性与抬身已转交圆足。双轴历史失败与未证能力没有被改写为通过。关闭依据为用户替代指令与动作迁移审核，不依据活跃目录预算。
6. **归档后最终复核**：重新读取两份 `work/closed/2026/` 实际文件，原 id 保留、status=superseded、superseded_by=lizard2-round-feet，已去掉 front matter 的 next，补有 outcome 与本记录 evidence；两个旧 active 路径均不存在。圆足仍为 open，已挂本审核记录并指向归档来源；必要性与抬身仍活跃，未完交接未丢失。最终落点复核通过。

## 证据引用

- `.codemaker/rules/work-ledger.mdc` 与 `rl_exp/tools/verify/check_work_docs.py` 模块文档：独立审核、替代关闭及记录格式依据。
- `FILEMAP.md` 对工作账本、诊断与验收记录的定位；`rl_exp/versions/lizard2/FAMILY.md` 的当前正式资产与 v2 退休事实。
- 审核时的 `work/active/lizard2-foot-design-tradeoffs.md`、`work/active/lizard2-two-axis-feet.md`；获准最终归档位置分别为 `work/closed/2026/lizard2-foot-design-tradeoffs.md`、`work/closed/2026/lizard2-two-axis-feet.md`。
- `work/active/lizard2-round-feet.md`、`lizard2-foot-plate-necessity.md`、`lizard2-two-foot-body-lift.md`、`lizard2-contact-protocol.md`、`lizard2-learned-gait.md`：当前承接与未完动作。
- `acceptance/records/2026-10-30-lizard2-round-feet-plan-review.md`、`acceptance/records/2026-10-30-lizard2-foot-control-first-trials.md`：范围纠正、文件纳管及双轴已知失败。
- `rl_exp/tools/diagnose/lizard2_round_feet.py`、`rl_exp/tools/diagnose/lizard2_round_feet_probe.py`、`rl_exp/tools/verify/test_lizard2_round_feet.py`：只读核对的现有入口。
- `rl_exp/out/lizard2_round_feet/candidate01/` 中的 candidate.json、probe01.json、probe01.log、候选 URDF/USD、网格及其它现场文件：只读检查及摘要核对来源，仍为本机工件，不承诺入仓。

## 未覆盖边界

未重跑生成、转换、结构测试、仿真、训练或策略评测，未验证实物驱动、足端尺寸、材料、真实惯量、全运动域安全或性能优劣；未独立重算双轴历史试验全部读数。后续恢复实施仍需核输入绑定、协议及执行范围。圆足事项保持活跃，动作/reset、受载问题、正式接线与采用继续未完；其它专项未被本次关闭。已完成归档后的字段、路径及审核指针复核，格式检查本身不替代本审核。
