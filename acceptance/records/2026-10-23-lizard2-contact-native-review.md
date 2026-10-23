# lizard2 原生接触短时采样独立审核

## 适用范围

由未参与本轮采样工具执笔的上下文审核。已读取 `AGENTS.md`、work-ledger，沿 FILEMAP/家族入口定位，直接检查 `palm_contact_sample.py`、采集源码快照、原生 API 快照、固定草案、实际 OBJ 与原始数组；没有把报告自身的速度摘要当独立真值。并核[执行记录](2026-10-23-lizard2-contact-native.md)的引用、正力/末窗口和未覆盖边界与原数组一致。

仅审核一环境、零动作、100 控制步/400 物理步/2 s 的有限原生 body→ground 采样，以及后续纯 CPU 切片/清理修补。未自行启动 Kit、物理或训练；不修改 work，不提交/推送，只写本记录。

## 验收条件

- 固定实际资产/草案与全部关节 PD/caps，保持零位置/速度目标、自由根、重力和 TGS/false；采集不插入动作或外力。
- 按实际原生 API 的 count/start 切片，逐 body 精确绑定单一 ground，法向力逐点和与 pair 矩阵相符；net/all-contact 与 ground-only 分开。
- 对 COM 速度和相邻 actor 位姿另行复算同一材料点速度，不能跨帧把接触 patch 索引当材料身份；差分不冒充瞬时真值。
- 正间隙、零力 patch、瞬态/晚窗口及候选网格点的边界具名保留，不据此判滚动/滑动性能或 TGS 偏差原因。
- 未完成采集拒判；正常及采集/写盘/序列化/audit 错误清理路径可复核，修前缺陷有真实代码破坏/修复证明。

## 结果

**接受此次有限原生接触采样证据及最终离线工具。** 接触归属、原数组计算和有限状态一致；不等于真实偏转/滚动/滑动分类、完整接触协议、S5 或训练放行。

### 实际身份与原生 buffer

attempt01 在导入 `PhysxManager` 时失败，原报告 completed/closed 均 false、samples/steps 均空，不能视为接触测试通过。原件保留；最终读取器实际拒绝 `incomplete collection`。入口按已安装 `isaaclab_physx.physics` 修正后，只有 attempt02 产生本轮实际 100/400 步原数组，completed/closed 为 true，stop_reason 为 null；全部控制步无 terminated/truncated，不存在跨自动 reset 的相邻位姿拼接。

直接核 actual draft/URDF/USD/OBJ 哈希，逐名比较 30 轴 Kp/Kd/effort/speed 与 B/C 当前承地报告精确相同；全部原物理行的 raw action、backend position/velocity target 均零。读取 actual TGS/false、自由根、重力及原配置，源码没有改 PD、限速或施加外力。

18 个 view 的 sensor_paths 精确等于本 body 路径，filter_paths 精确等于 `/World/ground/terrain/GroundPlane/CollisionPlane`，没有用模糊地面名给力矩阵贴标签。每个 view 为单 body/单 ground pair；18 份持久顶点数组逐值等于哈希绑定的 OBJ。

原生 API 快照的 `RigidContactView.get_contact_data` 明确返回 force/point/normal/separation/count/start 六个 buffer；pair 数据位于 `[start, start+count)`。采集原源码按该区间切片，`dt=.005` 对应 impulse→force 转换。实际 count 最大 4、start 全为 0；本机真实样本没有覆盖非零 start。

最终抽出的 `contact_patch` 同时由真实 collector 与 CPU 自检调用。本审核另给该函数非零 start=7、垃圾前后缀，核只返回指定两点；越界、负 start、满 capacity 拒绝，count=0 返回空数组。非零 offset 是共享消费者的 CPU 证明，不包装成另一组物理覆盖。原件仅存已选 patch，不能从它恢复未选 buffer。

从全部原 patch 的 magnitude×normal 独立求和，与 ground pair force 的最大分量差约 `2.97724e-5 N`；net_force 另与原总接触 view 对表。API 说明 net 包括所有交互，pair matrix 只包括 filter；本次地面归属采用后者，不将 net 自动等同地面支持力。

### 正间隙、零力及有限载荷

全原数组含 9600 个 patch 点，其中 4589 个法向力≤1e-8 N。最高点 z 约 0.02206618 m，其 separation 约 0.02206635 m、force=0；全体 z−separation 约在 `[-7.12e-7, 2.30e-7] m`。这与求解器保留的正间隙/零力点相容；不能将 count>0、原生点存在或最高点高度称为已受载、穿透或精确地表材料点真值。没有在本轮独立读取/改变 contact offset 来建立其因果解释。

最后 100 个物理行（0.5 s）的独立法向 z 载荷均值为四足合计约 670.81745 N、尾约 35.51006 N、其它 0；总和/体重约 1.0000051。它们是该末窗口的载荷观测，不是持续平衡或支持策略通过。最高全窗口值保留瞬态含义，不称稳态。

最低 OBJ 顶点到最近 native patch 的最大距离约 0.09128 m；不同掌面边角和零力点可能影响该距离。本记录没有从该差值反推错误归属，也没有据此保证几何候选点代表实际受载接触。最终摘要以 positive_force>0 另报速度；这只是描述性筛选，不是已批准的支撑事件/策略阈值。

### 速度独立核验

独立使用 SciPy 的 xyzw 四元数旋转矩阵，从当前世界点变换回当前 body 局部坐标，再以此前 body pose 映射同一材料点，重建 0.005 s 后向位移速度。没有对相邻 patch 的第 k 个点直接差分。另从原 COM position/linear/angular velocity 用显式叉积计算材料点速度，与最终工具逐项一致到浮点舍入量级。

最后 100 帧中正力点的四足最大切向速度：原 COM 速度重建约 `0.00383091 m/s`，独立同材料点后向差分约 `0.00020165 m/s`。另在可用相邻三帧上重建中心差分作时间离散对照；其末窗口足端最大量级约 1.1e-4 m/s。后向/中心估计的时间窗口不同，均不是独立物理速度传感器，不能据其较小就判定“无滑动”。

原生 COM 通道与位姿差分的差异保留。TGS/false 的既有 warning 及前序速度异常是相关背景，本轮未切换求解器或外力时序，不足以排除时间离散、采样/求解器对齐和数值误差，也不证明差异的唯一根因。全窗口速度差最大值与晚窗口、切向量与全三维量分别解读。

### 读取与清理的实际验证

最终 audit 对同一 attempt02 原件复算结果与 `audit02_verified.json` 精确相同，并实际拒绝 force、point shape、mapping、velocity target、gravity 五种原数据内存破坏。`--self_check` 的材料点旋转/平移、切片边界和清理夹具已实际运行通过。

审核指出采集快照中 report 序列化/写盘位于 app.close 的 finally 保护外。执行者未重采，而将 env.close、report 写出及 audit 纳入外层 finally，并增加持久 cleanup_self_check。本审核抽取修前和最终 collect 的实际 try/finally AST，以无 Kit 的假 env/app/文件对象运行：修前写盘 OSError 与 NaN 序列化 ValueError 均跳过 app.close；修后两者均调用 app.close，错误仍传播。正常、采集错误、env.close 错误、audit 错误亦独立检查；持久自检另外覆盖 app.close 抛 SystemExit。没有用 CLI 退出码替代 completed/closed 和数组审核。

## 证据引用

本机原件位于 `rl_exp/out/lizard2_contact_native_20261023/`，不承诺随仓分发。本审核直接核验的 SHA256：

| 对象 | SHA256 |
|---|---|
| 最终 `rl_exp/tools/diagnose/palm_contact_sample.py` | `9dd3b451b9f4cd803bf28c5cf9dd474974c22b293f5d3fa04957a3c3a331e586` |
| attempt01/report.json，失败原件 | `99020491eca03d449c3f0846f130729fb9f1a4a4bc48e4e0bd7210052ff8702d` |
| attempt02/report.json | `7d8169117ccea67592d4b27a6c128087929cf91193e71965a0d76f25093106e9` |
| attempt02/source.py，真实采集源码 | `2b33881768d83c0ebd0074ff414f43c546fb904a353375b82a15b508aaf5d9b2` |
| attempt02/native_contact_api.py | `be558e31693e0d48a7003134a777c306bc3b080ce5e7ce6ebabc418fb680f9ca` |
| audit02_verified.json，最终复读 | `dfb09e451bda32a5639429fe4f4f7dbff4c539f874a14d1e5683e1d39d7e01c6` |

- 草案 SHA256 `a120b8907601852e5ca7bf1190f675d75ea7a8ae0fa79e970d887628ed7e8b19`；实际 URDF `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`、USD `721e8a4053c2a6114b5c4607e57ed34f287fe317f8f9abb47a5e857b845e9c0e`。原 report 内还保留各 OBJ 摘要及完整数组。
- 本审核直接比较真实采集 source 与最终 source：差异为共享切片抽取/CPU负控、额外末窗口与正力/候选点统计、未完成早拒及清理保护；历史采集字节未用最终源码冒充。相关前置边界见[接口运行审核](2026-10-23-lizard2-interface-runtime-review.md)、[COM 口径审核](2026-10-23-lizard2-contact-com-review.md)。
- 持久复读为项目 Python 的 `-B rl_exp/tools/diagnose/palm_contact_sample.py --audit <attempt02/report.json>`；CPU 入口为同工具 `--self_check`。独立速度/载荷/点语义及 AST/mock 复核在内存完成，没有新增物理、诊断脚本或持久复读工件。
- 写入本记录后，`check_work_docs.py` 为 `WORK_DOCS_OK (91 item file(s))`，本记录路径的 `git diff --check` 无报错；格式结果不替代实际审核。

## 未覆盖边界

未验证真实偏转/滚动/滑动分类器、摩擦剪切力、接触面微滑、地面材料点真值、长期支持分配、策略性能、全域安全、S5 完整接触协议或训练放行。18 个精确 filter view 不代替所有几何/地形/状态覆盖；真实非零 start、容量饱和、异常运动/自动 reset 的此工具路径亦未采。

接触 API、COM 速度和位姿均来自同一仿真后端，差分是不同计算通道而非外部真值；根姿态来源也没有另添独立 root transform 传感器。positive force 统计未固定有效接触阈值。原取消的试验不恢复，事项不关闭；源、实际输入或证据发生变化后须针对变化重审。
