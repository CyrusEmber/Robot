# 承重协调交给 RL：用户定案与动作接入核对

## 适用范围

2026-10-22 用户在[当前承地静站力矩观测](2026-10-22-lizard2-standing-joint-force.md)和原因讨论后确认“这个可以让 RL 学习”，随后要求记录并开始下一步。本记录延续[默认驱动与 RL 职责](2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)，不是正式机体采用或开训决定。

**用户定案**：受载目标角偏置、前后腿支持分配、躯干/尾巴姿态以及抬腿/步态协调交给 RL 学习。当前 PD 保留候选；不为使全部零目标静站通过旧诊断判据继续提高刚度，也不追加手工补偿控制器或手工步态前置。原静站失败与受载静差保留原判词，不改成通过、不将其等同关节不能驱动。RL 可以改变目标来建立支撑力矩，但不代表底层任意目标跟踪误差消失。

底层轴向、几何/碰撞、限位、effort/speed、可达动作和可信观测继续由 B/C/E/D 保证；RL 不承担掩盖接线或读数缺陷的职责。需协调的关节必须有实际可达动作；诊断全部可控不等于正式配方已经开放，逐角色权限/固定或门控仍在 S5 按实际接入落地。用户此前撤销手工动作交付前置的依据继续取[交付修订](2026-10-19-lizard2-a-delivery-plan.md#用户定案撤销手工步态交付前置)。

本轮下一步选择动作通道与候选配置接入核对：只构建注册配置、读取已采非零数据，不起物理、不训练、不改冻结 v3 或正式资产，不关闭原事项。

## 验收条件

- 固定已批准的全部关节小幅报告和当前承地报告字节身份，核绑定 manifest 与当前 URDF；历史小幅通路证据只复用其原无重力/固定根条件，不转移为当前增益受载精度通过。
- 用真实注册配置构造器分别构建冻结 v3 与当前隔离候选覆盖配置，按各自实际 URDF 解析 action 选择；不从动作维数相同推断语义一致。
- 当前候选逐关节绑定 action 所属、缩放、偏置、裁剪、默认目标和实际 PD；需要非零通道，不接受 scale=0 或重复/遗漏。正式 v3 保持原值，另报它的选择器作用到新关节集合时缺什么。
- 复读现有全部 30 个逐轴 case 的实际目标、backend 目标、零速度目标与同向实际 q；校验 case 判词和已有 actor/FK 残差。保持此前独立实体有符号角审核的原边界，不以本轮重读标量 q 替代新的实体方向审核。
- 缺失通道、零缩放和错误后端目标反例必须被实际消费者或核对工具拒绝。声明/配置一致与历史行为证据分开报告，不声称正式策略已接入或已会站立。

## 结果

新增持久复读入口 `rl_exp/tools/diagnose/palm_policy_channel_audit.py`；真实构建注册 `Lizard2-Flat-Play-v3`，分别使用原正式资产及当前隔离 manifest，不实例化环境。

| 对象 | 动作集合与已核边界 |
|---|---|
| 当前隔离候选 | 腿部 20 + 胸颈尾 10，共 30；逐关节唯一所属，scale=1、offset=0、clip=None、保序，默认目标全零；配置 Kp/Kd 逐项匹配最新承地读回 |
| 冻结 v3 | 原机体腿部 12 + 胸颈尾 10，共 22；腿部 scale=0.5，胸颈尾 scale=0.25，维持原配置 |
| 原 v3 选择器直接套当前新关节集合 | 全部 20 个腿部关节不匹配，只有胸颈尾 10 个匹配；仅替换资产路径无法完成接入 |

历史全部 30 个逐轴 case、每例 1200 帧，共 36000 帧非零动作通路复读通过；期望位置目标与实际 backend 最大差 `9.2743857038613e-10 rad`，速度目标均为零，目标峰值处实际关节角与命令同向。其实体方向独立审核仍引用[全部关节小幅记录](2026-10-19-lizard2-spatial-small-tracking.md#新导出输入全部关节小幅驱动复验2026-10-20)的原批准，不宣称本轮新做实体轴向或当前受载全关节精度验证。

缺失一个腿部动作、将腿部 scale 改为零、将真实样本的一个 backend 目标增加 0.01 rad，三种对消费者输入的内存破坏均被拒绝；原始证据文件未改写。物理启动数为零，正式动作权限与配方没有变更。 仓库离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 52.1s)`，事项格式检查及提交前闸门通过。

结论：当前候选具备诊断层全部关节可达通道与已有非零随动证据；旧正式 v3 不能直接用于当前候选学习。后续 E/S5 需按真实角色接动作/观测/接触语义和正式权限，B 保留速度通道异常及有效边界缺口，D 仍核集成与安全 reset，S6 才评价已训策略的承重协调。当前这一步完成不等于上述事项完成，也不授权绕过缺口开训。

## 证据引用

- 工具提交 `8604e6d`：`rl_exp/tools/diagnose/palm_policy_channel_audit.py`；固定输入：`rl_exp/out/lizard2_e_fresh_tracking_20261020/report.json` SHA256 `6ae21d6db17a46f2431917c5488ace92b8cf6a57f4c87302ab36c8ca8937bb11`，`rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json` SHA256 `5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6`。
- 输出 `rl_exp/out/lizard2_policy_channel_audit_20261022.json`（SHA256 `34b8b031cb1ec05bfc42381024952f4c8467804494ed63bbb0d0191d6fbef7d9`），含每个实际动作组、缺失关节、当前逐轴 PD、历史 case 哈希与作用范围；日志同名 `.log`。本机数据引用不承诺入仓。
- 反例输出 `rl_exp/out/lizard2_policy_channel_negative_20261022.json`，日志同名 `.log`。内存注入覆盖缺失动作、零 scale 和错误 backend 目标，不是另起物理的错轴负例。
- 实际注册构造器 `rl_exp/tools/verify/baseline_runtime.py:resolve_task_cfg`，诊断绑定消费者 `rl_exp/tasks/obs_protocol.py:load_diagnostic_target`，冻结动作构造 `rl_exp/tasks/lizard2_recipe.py:lizard2_actions`；未改变这些消费者。

从仓根复读，输出须不存在：

```cmd
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/palm_policy_channel_audit.py --tracking_report rl_exp/out/lizard2_e_fresh_tracking_20261020/report.json --approved_tracking_sha256 6ae21d6db17a46f2431917c5488ace92b8cf6a57f4c87302ab36c8ca8937bb11 --current_report rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json --approved_current_sha256 5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6 --out rl_exp/out/lizard2_policy_channel_audit_replay.json
```

## 未覆盖边界

不修改正式配方、策略权限、奖励或已训 v3，不批准新资产采用、冻结或开训。当前增益下其它关节的未测受载精度、速度读数异常、有效限速行为、非零 obs 语义、接触协议、gait/终止等真实消费者及集成审核仍按原事项承接。历史 actor/FK 和目标读回不保证新策略成功学习、任意姿态精度、最大负载或连续域安全；协调性能留 S6，未完成动作未取消。
