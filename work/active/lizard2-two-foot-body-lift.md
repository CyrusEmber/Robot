---
id: lizard2-two-foot-body-lift
title: lizard2 两脚承重与抬身能力验证
scope: rl_exp/tools/diagnose, ablation_harness, rl_exp/versions/lizard2
status: in_progress
landing: rl_exp/tools/diagnose, acceptance/records
next: 执行者定自由基座对照范围；脚板必要性已转 lizard2-foot-plate-necessity。
close_when: 新上下文按正文“关闭条件”核验落点与证据；有缺口不关闭。
evidence: acceptance/records/2026-10-29-lizard2-two-foot-body-lift-plan.md, acceptance/records/2026-10-29-lizard2-body-lift-geometry-start.md, acceptance/records/2026-10-29-lizard2-two-foot-geometry-precheck.md, acceptance/records/2026-10-29-lizard2-foot-collision-candidate.md, acceptance/records/2026-10-29-lizard2-lift-guide-calibration.md, acceptance/records/2026-10-29-lizard2-guided-lift-first-trial.md, acceptance/records/2026-10-29-lizard2-lift-initialization-analysis.md, acceptance/records/2026-10-29-lizard2-guided-lift-video.md, acceptance/records/2026-10-29-lizard2-clearance10-video.md, acceptance/records/2026-10-29-lizard2-sag-force-analysis.md, acceptance/records/2026-10-29-lizard2-preload-offset-control.md, acceptance/records/2026-10-29-lizard2-foot-plate-sweep.md
---

## 当前范围

回答当前 lizard2 腿部与脚掌在受载时能否主动抬高身体，重点检查两组对角双足支撑。通用目标求解与机体适配分离；首例及用户请求的独立录像复现均在立稳前早停，尚未进入抬身。双轴候选连接相交仍待处理，策略评测未完成；方案与阶段证据见 evidence，不作为承载能力通过证据。

机体结构、轴向、惯量与正式采用继续归既有 lizard2-two-axis-feet；自由机身的移重、平衡和实际步态继续归 lizard2-learned-gait。本项负责受控抬身诊断及两脚支撑证据交接，不把手工协调动作或导向测试增加为默认驱动交付、机体采用或开训的通用前置，不重复建立训练任务。

## 下一步

1. **输入与工况固定（执行者）**：按方案记录绑定正式机体对照和双轴隔离候选，核实本机未入仓候选与采集脚本的身份及可复读性；将参数落入隔离配置，补齐资源预算、停止条件与目标生成定义后再运行。复用通用 `pose_target_solver.py` 与独立机体适配，补齐四足及两组对角支撑路径的限位、全机碰撞和非支撑部位净空检查，不可达单独报告；不把端点求解冒称全路径可行。
2. **夹具与观测（执行者）**：按用户要求修正连接区相交，不用过滤掩盖；现有隔离碰撞形状仍在有限非零转角失败，继续结合脚底、下肢几何与组合运动设计，并核运行时过滤。实现仅释放竖直平移的导向诊断，校验约束没有竖直托举，并记录它提供的横向反力与稳定力矩。补齐物理子步地面滤波接触、实际掌底运动、机身与质心高度、关节目标/实际状态及可验证力矩；保存原始时序。复用已有可信通道，只补实际缺口，不用历史净力峰值或 PD 推算冒充负载和驱动余量。
3. **受控抬身（执行者）**：首例已用掉一次预算并在立稳阶段触发停止线；离线分析定位下沉、受载关节偏差与非支撑足触地的时间关系，因果与实际驱动能力仍未确认。补齐后端目标、地面接触绑定、实际足部姿态和力通道独立审计，设计受载初始化和反例对照，另定复测范围，不直接重试或放宽停止线。随后按方案矩阵执行静置、抬高、保持、回落和恢复，低幅先行；分别报告脚掌、膝、肘角度和可信载荷，不将整机耦合响应误称单轴独立能力。失败、跳过和未覆盖均保留；阶段内禁止重置或写状态伪造位移。
4. **足板单独抬身（执行者）**：预查已完成（见 evidence 的 foot-plate-sweep），v6 驱动下按静态估算力矩差约一个数量级，不跑物理。脚板关节是否必要归 `lizard2-foot-plate-necessity`；不为通过加大足板增益，也不与腿部协调抬身混报。腿部协调抬身已在 0.02 m、0.05 m 两档完成，不再加高。
5. **策略交接（执行者与学习步态事项）**：交付两组对角支撑的测量口径和受控边界；在匹配机体的实际 checkpoint 上复用同一观测核验自由机身支撑，不以旧策略直接评判新接口候选。无适配策略时保留明确未完动作；自由步态记录由学习步态事项负责，本项留指针，不能把受控抬身成功写成走路成功。
6. **证据与审核（执行者）**：结果另记验收记录并同次更新 evidence；提供配置、源码与资产身份、运行命令、原始时序、视频和离线复读入口。完成相关检查后置 pending_review，交不带执笔历史的新上下文按关闭条件审核；不因文档或格式检查完成而关闭测试事项。

## 关闭条件

- **审核者与输入**：新上下文对照方案、隔离配置、实际落点、输入绑定、原始观测和复读结果，检查判词与实际数据相符；新增证据改变结论时重审。
- **可观察验收**：计划工况有明确的通过、失败或有依据的未执行状态；真实抬身、指定双足独立承重、足部稳定及恢复可复读；足板单独抬身有预查结论，不跑物理，必要性交 `lizard2-foot-plate-necessity`。导向竖直帮助和重置不能制造通过，未知力矩不能转写成余量充足；失败不自动归因于电机不足，缺测不冒称通过。
- **交付与边界**：受控能力结论及缺口交机体事项，自由步态的结果或明确未完动作交学习步态事项并核实实际承接。只有受控诊断已收口且策略部分已有证据或明确在办承接时才可关闭；尚未完成的本项实现、测量与验证不得省略。结论不外推硬件持续能力、其他支撑组合、地形或冲击。
- **结果处理**：通过审核后关闭；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。
