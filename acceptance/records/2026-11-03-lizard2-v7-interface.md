# lizard2 v7 当前正式资产接口与 reset 实测

## 适用范围

2026-11-03，用户要求完成当前资产实测关节序、观测宽度及动作/reset 核验，并选择“接口＋首步核验”：TRAIN/PLAY 正式配方，有限物理步，不训练、不做承重专项、不提交。仅将正式配置的 `num_envs` 缩为2、seed设为123；不改PD、默认姿态、活动权限、终止规则或资产。

执行者完成两轮实测；不带执笔历史的独立上下文先审核run04，提出刺激盲区；补强后另一新上下文复审run05，支持仅本资产宽度/列序与已测reset首步的限定批准。不是家族整体关闭或训练性能验收。

## 验收条件

- 当前正式USD/URDF及配方、源脚本绑定一致；真正注册TRAIN/PLAY，不用隔离v6替代。
- URDF具名活动轴、实际articulation索引、action局部/全局索引及PhysX DOF一一闭合；每轴正负小目标核全部列，真实PhysX getter与目标一致。
- 观测组/项序、各项宽度及实际拼接列可复读；两env不同的非零输入、非平凡姿态，拒绝跨env/列广播、错列及未旋转反例。
- 全量显式、子集、timeout自动reset恢复选中环境root/q/dq/action/history/episode；未选中环境包括command/processed/目标及PhysX目标按字节不变。目标持久化如实记录，不假定reset清processed。
- 全量显式及自动reset后第一零动作控制步，在每次physics前write完成后读PhysX全部列，有限状态且无额外终止；单成功task最多3控制步。

## 结果

### 最终有效实测

| 项 | TRAIN | PLAY |
|---|---|---|
| task | `Lizard2-Flat-v7` | `Lizard2-Flat-Play-v7` |
| 最终报告 | `rl_exp/out/lizard2_v7_interface/run05/train/report.json` | `rl_exp/out/lizard2_v7_interface/run05/play/report.json` |
| 报告SHA256 | `0f27735ec6c27dd09a042ebed6ea04c39445933a84a4413e089e362d7a501f19` | `ac64a7d3e8bc30fed2122eb4b9103facea9072f2d891966d1bfbd00e7ec033cd` |
| JSON status / report退出码 / 子进程退出码 | completed / 0 / 0 | completed / 0 / 0 |
| runner墙钟 | 15.812s | 15.407s |
| 实际结构 | 26关节、31body | 26关节、31body |
| policy | `[2,90]` | `[2,90]` |
| 目标用例 / PhysX真读回 | 54 / 54 | 54 / 54 |
| 每task控制步 / 物理子步 | 3 / 12 | 3 / 12 |

54例为零动作、全26轴各正负0.01rad及reset后零动作；每例全部列均按affine动作、clip及具名索引检查。目标与PhysX最大误差0。正式脚本来源副本与当前源码SHA为 `9e4a4188db8c9b2ce6376bea4a1b9886f7ef2b17d5b5874b6c11cd6c954d49fd`；v7 yaml SHA为 `cec36187638859eb8109e760551cde1203b9a7bfdeb3b0462c72f71eb37b49dc`。USD/URDF保持接入记录的原字节。主上下文独立重算所有报告bindings并检查TRAIN/PLAY实际序与pin结果一致。

实际runtime序（此处记录测量；唯一机器消费点仍是 `rl_exp/versions/joint_order_runtime.json`）：

```text
chest_yaw, tail1_yaw, rl_hip_swing, rr_hip_swing,
chest_pitch, tail1_pitch, rl_hip_abduct, rr_hip_abduct,
neck_yaw, lf_shoulder_swing, rf_shoulder_swing, tail2_yaw,
rl_hip_twist, rr_hip_twist, neck_pitch,
lf_shoulder_abduct, rf_shoulder_abduct, tail2_pitch,
rl_knee, rr_knee, lf_shoulder_twist, rf_shoulder_twist,
tail3_yaw, lf_elbow, rf_elbow, tail3_pitch
```

action→runtime索引：legs全局0–15对应 `9,15,20,23,10,16,21,24,2,6,12,18,3,7,13,19`；spine全局16–25对应 `0,4,8,14,1,5,11,17,22,25`。关节观测按runtime序，actions观测按action term拼接序，不要求二者相同。

| policy项 | 起始列 | 宽度 |
|---|---:|---:|
| base_lin_vel | 0 | 3 |
| base_ang_vel | 3 | 3 |
| projected_gravity | 6 | 3 |
| velocity_commands | 9 | 3 |
| joint_pos | 12 | 26 |
| joint_vel | 38 | 26 |
| actions | 64 | 26 |

正式配置corruption=false，未覆盖。两env使用不同非零q/dq/action/root速度与roll/pitch/yaw。独立复审从world-state与四元数代数复算旋转，source最大误差5.64e-8；actual/reference最大误差：线速度8.94e-8、角速度1.79e-7、投影重力2.38e-7，其余项0，均在既定2e-5阈值内。七项均拒绝跨env和列广播；重力拒绝未旋转输入。参考读取运行cfg的选择、scale和clip，不是外部物理规范的全面认证。

### reset与首步

- 全量显式reset：root位置/xyzw/速度、全部关节位置/速度恢复默认；action/prev_action/episode清零。processed与目标持久化是记录项，未改框架。
- 子集reset：只重置env0；env1全部10类字段字节精确保持，含command、processed、command buffer和PhysX目标。子集reset后额外process/apply/write零动作，核全部26列，physics增量0；**不称子集reset后首物理步已验证**。
- timeout自动reset：人为将env0 episode计数设至timeout前一控制步，`terminated=[false,false]`、`truncated=[true,false]`，只重置env0；env1同样字节精确保持。不是通过实际跌倒强制重开。
- 三控制步分别为显式reset后首步、forced timeout、自动reset后首步。每步4次write后PhysX读回，physics计数分别 `[0,1,2,3]`、`[4,5,6,7]`、`[8,9,10,11]`，全部零动作affine目标误差0；非timeout两步无终止，root/q/dq/obs有限。
- body-frame速度缓存写world速度后不会立即失效。探针使用公开 `robot.update(1e-6)` 仅推进缓存时间戳、不推进physics，再与world状态独立变换参考比较；没有修框架。

### 失败现场、回归与批准

- run01：漏原生 `resolve_presets()`，传感器cfg类型加载失败，0控制步；run02：发现body-frame缓存旧值，0控制步；run03：组装报告 `KeyError('after')`，实际已1控制步/4物理子步，旧报告 `physics_steps_after_load=0` 错误，按 `physics_steps_at_failure=4` 保留。
- run04：TRAIN/PLAY完成，随后独立审核发现同env刺激、平凡姿态和子集首步声明盲区；不是删除旧报告后伪装首轮成功。run04绑定旧源码，不能当当前源hash匹配证据。
- run05：补两env差异、非平凡姿态、广播反例及未选extra字节核；独立复审支持上述限定批准。run01–05合计7次task尝试，4成功3失败；累计TRAIN7、PLAY6控制步，合计52已测物理子步。启动阶段physics未界定；pin加载另记，不混入上述控制步数。
- 新最小回归先在旧源码上失败，再修后通过；错mapping、错列/宽度、非零缺失、NaN、reset残留、跨env广播、未旋转输入、signed zero篡改均有拒绝检查。接口刺激部分11项通过；再补真正cfg构造的原生preset回归，未resolve的内存修前路径在两task类型断言实际失败，修后原有11项加新增1项共12项通过。
- 既有 `obs_protocol_live.py --pin` 的pin01同样暴露漏原生preset解析，双task失败退出1。仅在其真实cfg构造处加既有 `resolve_presets()`，不改term或检查语义。pin02真跑双task成功退出0，26关节与run05相同，policy90当时标unapproved；源码SHA `9c4b0562298d87faf094cda483bcf16d14b92f43e515f12f4f5fd08707095824`。这两次日志均保留。
- 实测与两轮新上下文审核后，仅为资产键 `lizard2_round_feet/lizard2_round_feet.usda` 批准 `a25a8c39001b` 的policy90，保留其他资产/task所有既有宽度。dims摘要用既有 `check_obs_protocol.dims_digest()` 计算，不自动刷新全协议；新摘要 `f76d71f765b955ece96816086f9f45d864d58dbbfcd2e1d832c6fe5b405fa3cb`，依据指向本记录。
- 收尾独立核：两正式task的 `runtime_joint_order` 各26、`recorded_dims` 均 `{'policy':90}`；报告所有输入bindings匹配，观测声明/golden/实际cfg比较通过，12项focused回归通过，work形状及 `git diff --check` 通过。
- 本轮完整离线套件：37项中25通过、1失败、11因fail-fast跳过，37.9s。仍为原 `GOLDEN_FROZEN_DRIFT`：新线golden `f82affdc627aa82b` 与冻结基线 `b1396611378c26e9` 不同；未更新该审核锚点制造全绿。观测协议项被全套fail-fast跳过，但已单独运行本轮两task检查并通过。

## 证据引用

- 可复跑探针：`rl_exp/tools/diagnose/lizard2_round_feet_probe.py --task <TRAIN或PLAY> --out <新的独占目录> --viz none`；实际执行解释器 `E:\IsaacLab\env_isaaclab\Scripts\python.exe`。外层 `subprocess.run(..., timeout=180)` 顺序单进程跑两task，stdout/stderr归相应train.log/play.log，runner对照真实子进程退出码与报告status/exit_code，不能只信shell0。每task控制步上限在探针实现内。
- 最终报告/source/log/runner：`rl_exp/out/lizard2_v7_interface/run05/`；首次成功及失败现场 `run01/`–`run04/`。本机产物不承诺入库；source副本与哈希保留，复读实现在仓内。
- pin实际命令：`python -B rl_exp/tools/verify/obs_protocol_live.py --tasks Lizard2-Flat-v7 Lizard2-Flat-Play-v7 --envs 2 --pin --reason "Measure exact v7 fixed round-foot order after run05 nonzero interface and reset checks" --viz none`；日志 `run05/pin02.log`，原失败 `run04/pin01.log`。
- 回归入口：`python -B rl_exp/tools/verify/test_lizard2_round_feet.py`；cfg/锚点核对：`python -B rl_exp/tools/verify/check_obs_protocol.py --live --only Lizard2-Flat-v7 Lizard2-Flat-Play-v7`。
- 机器落点：`rl_exp/versions/joint_order_runtime.json`、`rl_exp/versions/obs_protocol_anchors.json`；正式配方及资产来源取 `acceptance/records/2026-11-03-lizard2-v7-round-feet.md`。
- 独立审核上下文：第一次task `26a3f289-0283-4f64-81de-b000a8b8b75d`，补强后复审task `8dff9d8f-6111-44e8-90a3-e9ff6278d337`；二者研究只读，不带本轮执笔历史。具体实测数值与批准限制已落本记录，不用“记录存在”代替实际审核。

## 未覆盖边界

- 子集reset后首物理步未单独验；只核子集reset和首零命令真实写入。显式全量/timeout自动reset后的零动作首步已核，不外推任意非零首步或所有终止组合。
- 不证明站稳、两足承重、接触材料、长期物理稳定、训练效果或步态；原事项不关闭、不取消。
- 本轮接口测量及限定锚点批准不等于已获训练启动授权；无训练run/checkpoint、无提交、推送或冻结标签。golden基线审核与共享脏树仍按原流程处理，不绕过开训限制。
