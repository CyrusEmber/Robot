# lizard2 B/C 默认驱动与通道交付清单

## 适用范围

用户在确认 B/C 状态后要求继续。本轮将已有默认驱动/通道证据交 D 核验，复读既有原始数据并比较参数身份，不启动物理、调整 PD、重开对称复测或限速/限矩试验。范围决定取[取消决定与计划盘点](2026-10-23-lizard2-plan-inventory.md)。全部关节目标速度仍为零，TGS/false；协调、抬腿和步态性能交 RL/S6。

候选 URDF SHA256 `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`。当前参数以承地报告及其 manifest 为交付对象：report `5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6`，manifest `2f39ca4e6268d90cee08600510f05a3eae78c1272fdbeebb811ba911405569f2`。历史固定根 USD 与当前自由根 USD 保持各自身份，不能要求两者同哈希；受载/无重力、固定根/自由根及增益背景不合并为一次试验。

## 验收条件

- 当前 30 关节逐名 PD/cap、动作/观测列和默认目标可回溯；明确局部增益相同与全机增益背景相同的区别。
- 全轴历史单轴、旧六组合、当前左后膝及承地观测保留原判词；误差增量与直接目标误差、设置读回与行为能力分开。
- C 的十个胸颈尾关节逐一有具名通道与历史测量；不因“躯尾协调交 RL”取消其底层输入/驱动要求。
- 取消试验不作通过，不再以已取消/不追加项目阻塞；D 对有限证据审核，不宣称任意姿态精度、硬件额定或新训练配置已验。

## 结果

### 本轮实际复读

五个持久读取入口均退出 0；其中“读取通过”是原始数据与判词一致，不把原失败转为通过。

| 入口与输出 | 本次确认 | 输出 SHA256 |
|---|---|---|
| `self_weight_audit.py` → `calibrated.json` | 全 30 轴、双向、102000 个历史自重样本的目标/零速度、增量判词、独立 actor/FK 一致；原标定通过 | `afe8358322da43ec6c9a16a6df547df18d8535542b2a99a9c84b9e8294970f84` |
| `palm_joint_force_audit.py` → `knee.json` | 当前四膝肘参数下左后膝单轴及左后腿五轴两例；原跟踪通过，载荷来源投影核对保持 | `02682b4afe0bf6104ac93776a8f08fd884d6f751f9e1aebf2f5dfe681e805fe4` |
| `palm_standing_force_audit.py` → `standing.json` | 当前自由根承地原始载荷/安全停止检查可复算；**原静站姿态判据失败保留** | `619c825b212a9dabbe5d48380859b5a3b9c4e0cc869ea18c40d422081b04e340` |
| `palm_velocity_limit_audit.py` → `caps.json` | 逐名 cap 设置/后端读回一致，三项错配反例拒绝；不进行触限试验 | `d80389bc1bdf3cc7f5d6e7adfe1a7e4af7790e9602c4c739382159e93610926c` |
| `palm_policy_channel_audit.py` → `channels.json` | 候选 30 通道与冻结 22 通道分开，历史非零目标读回；当前配置 PD 匹配承地 | `34b8b031cb1ec05bfc42381024952f4c8467804494ed63bbb0d0191d6fbef7d9` |

另直接核四份 report/manifest/URDF 身份，逐名比较增益和 caps，并从六组合 20400 帧重算原增量/返回/其它轴、静置漂移及绝对误差判词。六组合四肢原失败、颈/尾原通过均与 summary 一致，backend 位置目标与 float32 目标一致、速度目标为零。该复核没有重复六组合 actor/FK 独立测量，相关原证据仍取[六组合记录](2026-10-21-lizard2-calibrated-combinations.md)。新覆盖表 `coverage.json` SHA256 `e52e5dca33853e6d0e05076b701e648b3c0a51c1147609df62e906c5810ac15c`。

### 参数身份与允许复用的范围

| 证据 | 与当前候选的参数关系 | D 可采用的结论 | 不可外推 |
|---|---|---|---|
| [全 30 轴标定](2026-10-21-lizard2-calibrated-loaded-pd.md) | 四个膝肘当时 Kp=65，当前为 220；其它 26 轴自身 Kp/Kd 精确相同 | 原固定根、自重、中立附近单轴增量保持/返回通过，30 轴方向和驱动通路已有证据 | 不能写成当前整套 PD 下全 30 轴精度已复验；即使某轴自身增益不变，四轴背景变化也不能抹掉 |
| [旧六组合](2026-10-21-lizard2-calibrated-combinations.md) | 全机参数与旧标定一致；与当前相差同四个膝肘 | 四肢原精度失败、颈/尾原通过；负载改变的局部解释仅属保持段 | 不是四膝肘 220 后四肢均通过，也不是当前新增益背景的颈尾组合新物理复验 |
| [当前左膝两例](2026-10-21-lizard2-left-knee-joint-force.md) | 全部 30 轴 Kp/Kd、effort/speed caps 与当前承地报告逐名完全相同 | 当前固定根自重下左膝单轴及左后腿五轴原工况，跟踪和载荷来源有证据 | 不是全部四肢当前精度、最大力矩、额外负载或动态额定 |
| [当前承地观测](2026-10-22-lizard2-standing-joint-force.md) | 当前全机 PD，重力/自由根/零目标 | 该窗口载荷、有限状态与原停止线可复算，未将姿态失败归为关节不能驱动 | 不是承重协调通过、长期稳定、自然步态或全动作余量 |
| [零速度/胸载荷](2026-10-22-lizard2-drive-input-and-chest-load.md) | 零速度目标定案；胸部悬空及承地各保留原工况 | PD 输入接口和自重载荷解释有具名证据 | 历史非零速度 B 组不得作为当前默认能力或训练设置；悬空高载荷不代表行走载荷 |

本轮比较的四个变化轴为 `rl_knee_joint/rr_knee_joint/lf_elbow_joint/rf_elbow_joint`。当前左膝报告与承地报告的全机参数/caps 一致，不只是膝自身一致。原始样本未改写。其它当前增益下未测范围依用户既定决定保留未知，不自动复测。

### C：胸颈尾十关节的具名交付

下表列号从零开始；q/dq 局部列 `r` 来自真实后端顺序，policy 实际切片分别为 `12+r/42+r`，raw action 的 policy 列为 `72+a`。默认位置/速度目标全零；实际关节速度可非零。当前自身增益均与旧全轴标定一致，但全机背景的四个膝肘已改变。

| 真实关节 | 语义 | 动作列 a | 后端关节列 r | 已有响应/载荷证据 |
|---|---|---:|---:|---|
| `chest_yaw_joint` | 胸部侧弯，不是根 heading | 20 | 0 | 原单轴受载及实际目标/实体随动 |
| `chest_pitch_joint` | 胸部俯仰 | 21 | 4 | 原单轴受载、自重/承地载荷；胸部水平不作门槛 |
| `neck_yaw_joint` | 颈 yaw | 22 | 8 | 原单轴受载、旧颈双轴组合 |
| `neck_pitch_joint` | 颈 pitch | 23 | 14 | 原单轴受载、旧颈双轴组合 |
| `tail1_yaw_joint` | 尾根 yaw | 24 | 1 | 原单轴受载、旧六尾轴组合 |
| `tail1_pitch_joint` | 尾根 pitch | 25 | 5 | 原单轴受载、旧六尾轴组合 |
| `tail2_yaw_joint` | 尾二段 yaw | 26 | 11 | 原单轴受载、旧六尾轴组合 |
| `tail2_pitch_joint` | 尾二段 pitch | 27 | 17 | 原单轴受载、旧六尾轴组合 |
| `tail3_yaw_joint` | 尾三段 yaw | 28 | 22 | 原单轴受载、旧六尾轴组合 |
| `tail3_pitch_joint` | 尾三段 pitch | 29 | 27 | 原单轴受载、旧六尾轴组合 |

胸部没有与颈尾一起完成一组联合激励，不能将“颈/尾两组通过”写作“胸颈尾整体组合通过”。诊断可达通道不是正式训练权限已开放；S5 的 scale/clip、实际部署映射、非零 obs 和 reset 继续按[接口方案](2026-10-23-lizard2-training-interface-plan.md)落地。拖尾、异常主承重及协调性能归协议/S6，不由 C 手工补偿证明。

### 给 D/S5 的判定与责任边界

执行者认为 B/C 已具备**按上述有限工况接收的证据包**，可交 D 独立核验；不是 B/C 无条件全域验收，也不是 D 整体放行或正式配置已接入。审核者须直接核原报告、manifest、样本及工具，不能只凭本清单接受。

- 已取消：剩余限速边界和限矩验证；不追加对称复测。保留原低 cap 越界样本和各未知范围，不修改判词。
- 已知风险：训练一致 TGS/false 下后端速度偏差进入 joint_vel；不能用 true 或 PD shadow 的“力矩”掩盖。该风险不因通道存在或取消限速试验消失。
- 转 D/S5：同一正式候选的动作/观测/接触采样、根与缓存/后端目标 reset；实际配置尚需落地和运行核验。不由此要求手工抬腿、步行、移重或躯尾协调通过。
- 保持在办：A 的几何/机械禁区、协议、新配置与整体审核/采用。B/C 局部交付不关闭总项、限位 PD 专项、D/E 或 S5/S6。

独立审核已[接受此有限 B/C 输入](2026-10-23-lizard2-bc-independent-review.md)，原失败和未知边界保留；不代表 D 整体、S5 或训练放行。

## 证据引用

本机输出目录 `rl_exp/out/lizard2_bc_handoff_20261023/` 包含上表 JSON 及同名 log；原始物理输入未覆盖，制品不承诺随仓分发。固定输入：

| report | SHA256 |
|---|---|
| `lizard2_b_calibrated_20261021/report.json` | `c5500ee862043111f68b65d5e0c2a03a8a9d4154f143a8b38775fd3281def9dc` |
| `lizard2_b_combinations_20261021/report.json` | `903ec4dcf17ba4c6bd7c7f2e4e4e1a68ed0794cf0c17f18356554574b386de82` |
| `lizard2_b_joint_force_probe_20261021/report.json` | `13929c53eccdb51d454ade60cf071c3eaa614bf5c90684dd2e06f4017d2485ef` |
| `lizard2_b_standing_force_20261022_run02/report.json` | `5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6` |

路径均在 `rl_exp/out/` 下。永久离线入口如下，输出目录须预先存在且目标文件不存在：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/self_weight_audit.py --report rl_exp/out/lizard2_b_calibrated_20261021/report.json --output rl_exp/out/lizard2_bc_handoff_replay/calibrated.json
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_joint_force_audit.py --report rl_exp/out/lizard2_b_joint_force_probe_20261021/report.json --out rl_exp/out/lizard2_bc_handoff_replay/knee.json
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_standing_force_audit.py --report rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json --out rl_exp/out/lizard2_bc_handoff_replay/standing.json
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_velocity_limit_audit.py --out rl_exp/out/lizard2_bc_handoff_replay/caps.json
```

动作入口与批准参数按[通道记录](2026-10-22-lizard2-rl-coordination-handoff.md)的持久命令运行，替换为新输出路径。六组合独立 scalar 判词/参数比较不依赖临时脚本即可复核：先核上表四 report 和各 manifest 的记录哈希；将 readbacks 按各自 joint_names 映射后精确比较 Kp/Kd/caps；六组合各取 `q[999]` 为原平衡基准，在 `(5,11]`、`(11,17]` 两方向分别按原末 0.2 s 保持/返回窗口及原阈值计算，与 summary 完整相等才接受。actor/FK 不由这一步代证。当前逐名参数仍唯一取具名 manifest，不手抄成正式训练参数。

独立审核过程与复核依据见[独立记录](2026-10-23-lizard2-bc-independent-review.md)。提交前 `check_work_docs.py` 通过：30 active/61 closed、179855/180000 bytes、226 records；`git diff --check` 无报错。七个归属文件暂存后，`git hook run pre-commit` 的静态闸门全部通过，日志为本输出目录的 `precommit.log`。本轮仅改文档，沿用同日接口方案提交前完整离线套件 37/37 的结果，不把文档闸门或读取器通过称作新增物理证据。

## 未覆盖边界

没有新增物理行为证据、正式采用、训练或 checkpoint。历史单轴和旧颈尾组合不等于当前全机增益背景重验，步平均载荷不等于子步峰值或硬件额定；没有证明全姿态 0.002 rad、整机平衡/步态或速度观测偏差无影响。未做不写通过，已取消不重新排期；总项仍按原范围维护，独立审核只可在其实际核验的范围内判定。
