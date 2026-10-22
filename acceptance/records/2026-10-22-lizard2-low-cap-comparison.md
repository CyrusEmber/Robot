# 左后膝低上限对照：限速通过，限矩上沿判据未达

## 适用范围

用户在审阅[三组提案与预算](2026-10-22-lizard2-drive-gaps-and-cap-plan.md)后回复“继续吧”，批准执行 A 10 rad/s／180 N·m、B 2 rad/s／180 N·m、C 10 rad/s／5 N·m。仅当前 `palm_spatial` 左后膝 `rl_knee_joint`，不追加其它关节或试验，不改默认 PD、正式配方或资产，不训练。抬腿、平衡与支撑协调继续归 S6。

固定根 z=2 m，31 body 保留重力，无接触、砝码或其它夹具；Kp=220、Kd≈14.95，全部位置目标按 50 Hz 保持、速度目标全零，物理 dt=0.005 s，TGS/`enable_external_forces_every_iteration=False`。沿用同一具名参考和共同 URDF `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`；只在 t=5 s 后覆盖左后膝本组的一项 cap。

## 验收条件

执行前固定提案判词和停止线，未根据结果修改。名义峰值 4 rad/s 的 ±0.768 rad 正负往返，每组静置 5 s，四段 0.36 s 运动及四段 1 s 保持／恢复，共 10.44 s、2088 步；三组 31.32 s、6264 命令采集步，一次物理进程，墙钟上限 900 s，失败不自动重跑。原膝绝对角、其它关节角、速度、轴向载荷、接触、有限性、backend／缓存与预算停止线全部保留。

A 的速度和载荷需分别超过 2.1 rad/s、5.1 N·m，连续至少 0.04 s，才解释 B/C 对照。B 后向 0.02 s 位移速度需不超过 2.1 rad/s，并在 1.8–2.1 rad/s 连续至少 0.04 s。C 步平均轴向载荷需不超过 5.1 N·m、在 4.9–5.1 N·m 连续至少 0.02 s，且相对 A 的实际角响应差超过 1e-4 rad；还须排查位置限位、速度约束、显式 effort／摩擦／armature／tendon 和接触贡献。提案工程带宽不作为电机物理硬界。

每组正常 reset 前恢复原上限；原上限下静置末状态一致才施加覆盖。记录逐步实际 Kp/Kd、effort/speed cap、位置／速度目标、q/v、q 差分、原始六维 incoming wrench 和 DOF 投影。结束／异常恢复原上限并核 backend。离线从原始样本重算限制、目标、停止与判词；历史入口语义保留，原非零速度参考只可复读，不得用于本轮物理。

## 结果

### 准备与唯一执行

新增具名 `--prepare --cap_comparison`，在原升速工具中接入固定三组调度、既有 cap setter 和逐步读回。判词与恢复消费者归 `palm_cap_comparison.py`，不新增执行器或依赖；无任意 cap／PD 覆盖入口。旧目标、采样摘要、原始样本消费者等 11 个函数 AST 与修改前相同，原膝、肘与历史速度参考对照均实读复算通过。

第一次离线准备的几何已通过，但 `state_atol` 使用 NumPy float32，独占写入计划时 JSON 序列化失败；原不完整 plan 留存，未启动物理。改为 Python float，并在永久自检中序列化真实判据字典；在内存恢复旧标量会让该自检失败，修复后通过。最终计划为 attempt03：43 姿态、18 实体、5977 次配对，离散限位与碰撞预查通过；只保留原直接连接与六对具名过滤，不证明连续安全。

唯一物理进程一次采完三组，共 **6264 步／31.32 s**，无硬停止或软件异常，无续跑／重试。记录墙钟约 **69.953 s**。本机 `SimulationContext` 单调 step 计数在环境就绪时为 0、结束为 6264，reset 未增加该计数；不把 SDK 内部初始化解释成已独立计数的物理步。报告 `completed=true` 和 `full_window=true` 表示采集窗口完整，状态为 **`low_cap_comparison_criteria_unmet`，真实进程退出 1**，完整采集不等于判据通过。

### 三组观测与原判词

| 组别 | cap（rad/s／N·m） | q 单步差分峰值 rad/s | 后向 20 ms 速度峰值 rad/s | 最大绝对步平均轴向载荷 N·m | 判定 |
|---|---|---:|---:|---:|---|
| A 原上限 | 10／180 | 3.498143 | 3.448466 | 13.892570 | 基线激励充分 |
| B 仅降限速 | 2／180 | 2.000833 | 2.000831 | 12.805792 | 限速响应通过 |
| C 仅降限矩 | 10／5 | 3.543466 | 3.503244 | **5.118464** | 限矩上沿判据未达 |

A 与原膝 4 档全部 q 逐值相同，最大差为零；本轮 A 超过 2.1 rad/s 的最长连续时间 0.185 s、超过 5.1 N·m 为 0.100 s，均达到预定激励要求。三组初值、原 cap 静置段及动作目标按实际 q/v 与读回核同条件；匹配允许的 float32 运输误差带已在执行前代码固定，不作为跟踪精度。

B 的 1.8–2.1 rad/s 后向 20 ms 速度平台最长 0.290 s，峰值 2.000831 rad/s；backend 速度峰值 2.000865 rad/s。支持本膝、本自重轨迹中低速 cap 的实际约束响应。B 的轴向载荷可能含速度约束贡献，不将其称作电机力矩或用于限矩验收。

C 载荷明显受限，4.9–5.1 N·m 平台最长 0.290 s，相对 A 的最大实际膝角差 **0.087081 rad**。本膝位置限位最小余量约 0.451784 rad，最大 backend 速度约 3.575948 rad/s、q 差分约 3.543466 rad/s，低于提案的 8 rad/s 排查线；friction、armature、显式 effort 均为零，无 tendon，接触全程为零。这些排查支持解释低 effort cap 的响应，但不能把传递载荷与 solver 瞬时纯驱动力矩无条件画等号。

**C 在 9.325 s 有一个 5 ms 样本超过 5.1 N·m**：步平均轴向载荷 +5.118464 N·m，q=−0.410652 rad、位置目标=−0.161185 rad，位于负向返回段；backend 速度 +3.535367 rad/s、q 差分 +3.399700 rad/s。它相对配置 5 N·m 高约 2.369%，超出预定 5.1 N·m 判据约 0.018464 N·m。手工 raw-wrench 活动轴投影为同一 +5.118464 N·m，全部轴投影与 DOF 读数最大差约 3.05e−5 N·m，不能通过改摘要消除该样本。

因此保留 `speed_response=passed`、`effort_response=criteria_unmet`、总 `passed=false`。本轮没有单变量区分该动态偏差的求解误差、载荷接口组成等因果来源，不将其归因于 PD 不足或宣称原 180 N·m cap 失效；不放宽 5.1 判据，不更换 TGS 时序，不追加物理诊断。

### 参数恢复与证据验证

所有采集帧的实际 Kp/Kd 和全部 caps 都按本组预期核对：前 1000 步原 cap；随后只有本膝 B 的速度 cap=2 或 C 的 effort cap=5，其它轴及增益保持原值。六次组前／组后恢复读回均为原上限，最终左膝回到 10 rad/s／180 N·m；正式资产和训练默认值未变。

永久 `--replay` 复算全部 6264 帧：50 Hz 目标、零速度目标、逐步 caps、原始投影、相同静置段、安全停止、原上限恢复、完整窗口和失败判词一致，退出 0／`SPEED_REPLAY_OK`。对真实样本作内存反例：旧限速未改变、额外关节 cap 改动、非零速度目标、错误 raw 轴、将失败伪装成功，均被实际读取器拒绝，原始数据字节不变。第一次 raw 负例误改了未被关节消费的基座列，读取器正确未据此拒绝；按真实 child/axis 绑定修正负例后，五项均拒绝，未修改消费者来迎合该夹具。

永久自检还调用真实 Runtime 的设置／恢复路径；后端忽略 cap 写入的合成夹具被拒绝；旧轨迹预算与非零速度物理拒错保留。完整仓库离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 62.0s)`；不新增默认闸门。上述均为执行者自检，不替代原事项关闭所需的新上下文审核。

## 证据引用

实际物理目录 `rl_exp/out/lizard2_b_cap_physics_20261022/attempt01/`，计划目录 `rl_exp/out/lizard2_b_cap_plan_20261022/attempt03/`，离线验证与日志目录 `rl_exp/out/lizard2_b_cap_comparison_20261022/`。原始 NPZ、源码、依赖、计划与每步读回均保存，不覆盖历史；本机工件不承诺随仓提供。

| 工件 | SHA256 |
|---|---|
| 物理 `report.json` | `1745e6eb56204a6b901c34371e6021192c123bdeecd9b24a6ba8ec5222f648f0` |
| 物理 `source.py`／最终 `palm_speed_probe.py` | `21ce4c6fd383738e39caf5a94e53b567e22cd63b24c695a3e675ce4aa73c90e3` |
| 物理 `dependency_palm_cap_comparison.py`／最终消费者 | `94da44d4e61ccf5d770d2a262655b0abc3241f6aa7e2b982952ad7219aca8772` |
| 最终 `plan.json` | `5ec5b120eec239ab963a95c68bd325dcb53367cefd0bd3dc708945cdcb99985d` |
| 最终 `geometry_report.json` | `6c2bc7a642b4d20510e382200db5fc5cfebb968af6b4ca3ce306ddc4efd7d639` |
| 最终 `geometry_config.json` | `864b8acd7b2a42188a88bad22ee30afa7f22dd4f2996039ab12281c6737cdd50` |
| 离线 `replay.json` | `79544cb1dbdb79d8ffd23da026b1de8e882b3af65e48f1f113b45119c237761d` |
| 离线 `actual_audit.json` | `02b01b307ba80ec1f740b398727216edf1ac818bc320bab246d61bfc85b50110` |

原始物理日志 `physics_attempt01.log`，其它实际前查、序列化红绿、自检、历史兼容、完整套件、复读／五反例日志位于上述离线目录；代码与文档按归属分组提交。两个采集源码与最终代码逐字节一致，依赖快照不代表其它会话在办修改获本轮提交。

永久复读命令（不起物理，输出须为新路径）：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_speed_probe.py --self_check --out rl_exp/out/unused_cap_selfcheck
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_speed_probe.py --replay rl_exp/out/lizard2_b_cap_physics_20261022/attempt01/report.json --approved_report_sha256 1745e6eb56204a6b901c34371e6021192c123bdeecd9b24a6ba8ec5222f648f0 --out rl_exp/out/lizard2_b_low_cap_replay.json
```

## 未覆盖边界

仅验证本膝在本轨迹下的低 cap 响应，限速正例不外推全部关节；限矩观测保留严格失败和来源未分离边界。未验证原 10 rad/s 附近触限、180 N·m 实际截断、同条件有／无限速、其它 4/6 rad/s 组、全速度—载荷包线、额外负载或全姿态精度，更不是硬件连续／峰值额定或热余量。A 保留 10 cap，不能称无限速。

当前一次物理预算已用完，后续先离线核该越界和原边界；新增物理需新的具名工况／预算，不自动重跑或加 PD。原关节覆盖证据、未测边界、E/D/S5 集成和 S6 学习策略协调继续在办；不关闭事项，不批准正式采用或训练。
