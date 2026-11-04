---
id: lizard2-two-foot-body-lift
title: lizard2 两脚承重与抬身能力验证
scope: rl_exp/tools/diagnose, ablation_harness, rl_exp/versions/lizard2
status: in_progress
landing: rl_exp/tools/diagnose/lizard2_round_support_geometry.py, rl_exp/tools/diagnose/lift_guide_asset.py, rl_exp/tools/verify/test_lizard2_round_support_geometry.py, rl_exp/tools/diagnose/test_lift_guide_asset.py, acceptance/records
next: 执行者依据离线准备记录补运行态导向标定与子步采集适配，集中确认承重时长、阈值及预算后再运行。
close_when: 新上下文按正文“关闭条件”核验落点与证据；有缺口不关闭。
evidence: acceptance/records/2026-10-29-lizard2-two-foot-body-lift-plan.md, acceptance/records/2026-10-29-lizard2-body-lift-geometry-start.md, acceptance/records/2026-10-29-lizard2-two-foot-geometry-precheck.md, acceptance/records/2026-10-29-lizard2-foot-collision-candidate.md, acceptance/records/2026-10-29-lizard2-lift-guide-calibration.md, acceptance/records/2026-10-29-lizard2-guided-lift-first-trial.md, acceptance/records/2026-10-29-lizard2-lift-initialization-analysis.md, acceptance/records/2026-10-29-lizard2-guided-lift-video.md, acceptance/records/2026-10-29-lizard2-clearance10-video.md, acceptance/records/2026-10-29-lizard2-sag-force-analysis.md, acceptance/records/2026-10-29-lizard2-preload-offset-control.md, acceptance/records/2026-10-29-lizard2-foot-plate-sweep.md
---

## 当前范围

回答当前固定圆足 lizard2 的两组对角腿能否在导向辅助下承担机体重量；本轮先做受控静态承重，不抬身、不验证自由双足平衡。输入采用圆足事项所绑定的修正版 USD、URDF 及已核接口；旧脚板导向试验仅作为工具与工况参考，结果与未覆盖边界见 evidence，不能外推为圆足通过。用户后续已授权准备两组圆足姿态与导向装配；当前离线产物及复读入口见 evidence，未启动运行态标定或承重物理试验。

机体结构、惯量与正式采用归 `lizard2-round-feet`，自由机身移重、平衡和实际步态归 `lizard2-learned-gait`。本项继续承接受控承重与历史抬身动作，不将其增加为机体采用或开训的通用前置；圆足先承重的范围不取消历史抬身、另一组支撑及自由机身交接的未完动作。

## 下一步

1. **圆足输入与支撑姿态（执行者）**：从 `lizard2-round-feet` 最新记录绑定修正资产、URDF、惯量假设及接口，不混用原失败 USD、旧脚板或双轴候选；导向若增加一个竖直被动关节，单列夹具自由度，不算机器人活动轴或动作。只准备左前＋右后、右前＋左后两个静态承重工况；四足仅在需要时作为测量/初始化基线，不恢复旧双机体和升降矩阵。复用 `pose_target_solver.py` 与几何预查，依据球面接地重新求姿态及根高；静态准备固定四个肩/髋 twist 零目标，只解其余腿轴，实际机器人活动轴不减少。当前推荐姿态与预览按 evidence 中零扭转修订绑定，旧冗余解仅保留历史；核限位、指定足接地和其它两足/尾/胸腹/头净空，不照搬平掌法线、旧离地高度或预偏置。
2. **导向与测量复用（执行者）**：复用已有仅释放竖直平移的导向、校验及子步地面配对采样；对圆足导向装配补输入绑定、无竖直驱动/托举检查及反力通道审计，记录横向反力和稳定力矩，不重建无关夹具。沿用圆足关闭自碰撞的诊断工况，内部网格相交记录限制，不重开旧脚板碰撞修形前置；地面碰撞、真实净空和限位仍须核。读取同帧逐物理子步地面滤波足力及所有潜在非足承重点、机身/质心高度速度、实际足心/姿态、关节目标/实际/速度；不以历史净力峰值充当静载或只凭两足力和排除夹具托举。
3. **有限静态承重（后续确认后执行）**：运行前将初始姿态、目标、PD/限矩/限速、材料、沉降及保持窗、资源预算、停止线和判据写入隔离配置，集中确认；当前不沿用旧升降脚本默认参数直接启动。先核 reset 后真实初始状态并下发本工况目标，再推进物理；计量期间禁止根/关节写状态、自动重置或夹具高度驱动。两组独立记录，不因一组失败取消另一组；共用资产、测量或夹具前提失败时明确哪些试次依赖失败而未执行。先保留现有驱动作诊断，不现场加大增益/限矩；若需受载目标偏置，另列依据与后续对照，不照搬旧偏置或静默迭代挑结果。可信实际力矩缺失不阻塞承重判定，但饱和、余量及电机不足保持未知。
4. **历史动作保留（不在本轮执行）**：旧足板单独抬身预查和腿部协调升降记录保留原身份，必要性归 `lizard2-foot-plate-necessity`，旧双轴结构缺口由圆足事项交接。当前圆足不做足板驱动或踮脚；历史抬身完整矩阵尚未覆盖部分、圆足是否恢复升降及更大幅度均不自动执行或视为完成，需要时另定范围，不把旧机体成功换写为圆足成功。
5. **交接与审核（执行者）**：判定指定双足是否承担机体重量时同时核静态高度/速度、两足实际持续载荷、其它部位无承重及导向竖直帮助；缺测则逐项未判，失败不自动归因于驱动力不足。结果、原始时序、输入/源码身份及复读入口归记录，并交 `lizard2-round-feet`；自由平衡与策略性能继续交 `lizard2-learned-gait`。完成本项约定范围后置 pending_review，由无执笔历史的新上下文核实际落点与证据，未完成动作不得随关闭消失。

## 关闭条件

- **审核者与输入**：新上下文对照方案、隔离配置、实际落点、输入绑定、原始观测和复读结果，检查判词与实际数据相符；新增证据改变结论时重审。
- **可观察验收**：圆足两组对角受控静态承重分别有通过、失败或有依据的未执行记录；指定双足载荷、非支撑部位净空/地面力、机身/质心状态及导向帮助可复读。夹具竖直托举、自动重置或写状态不能制造通过，未知力矩不能转写成余量充足；不以导向辅助承重冒充自由双足平衡。旧足板预查及升降证据按原身份保留，不作为圆足抬身通过。
- **交付与边界**：当前受控承重结论及缺口交圆足事项；历史未覆盖支撑组合、抬身/恢复及自由基座/策略动作须完成或明确保留活跃承接，不能因本轮只做静载而消失。只有约定受控范围已收口且其它未完动作有真实在办承接时才可关闭；不外推硬件持续能力、其他支撑组合、地形或冲击。
- **结果处理**：通过审核后关闭；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。
