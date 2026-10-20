# lizard2 三轴候选：惯量主轴修正与 PD 初值交接

> 前段为旧输入的历史测量与交接。新正式导出 USD 的当前惯量前提见末节“新正式导出输入的运行时惯量复验”；当前默认驱动/RL 分工取胸部静站记录的用户定案，不恢复前段历史手工抬落/试走路由。

## 适用范围

承接限位 PD 专项步骤 3，消费 E 已绑定的具名过滤隔离候选及接触边修正轨迹。用户在看到几何交付后要求“继续”，本轮据此推进惯量和驱动前提；不把继续施工记为最终外观认可、正式采用或承重批准。

每次只启动一个固定基座、无重力、零 stiffness/damping/armature 的环境，读中立姿态和既有轨迹 c=0.25。正常 reset 后只写状态、forward 和刷新缓存，没有命令物理步或施加 PD 激励。质量单位 kg、位置 m、惯量和关节质量矩阵 kg·m²。正式资产、配方及生成器不改。

## 验收条件

- 先核实际关节状态、全体 actor/FK 坐标及基座约束，再比较逐 link 质量、质心和完整惯量张量；不得直接把 USD 的三个主惯量当 link 坐标分量。
- 按同姿态、同固定基座和同关节顺序，用 COM 线速度/角速度 Jacobian 投影 URDF 惯量，保留平行轴项，比较运行时完整质量矩阵。张量数值条件为最大分量差不超过 `64*float32_eps*max(abs(actual),abs(expected))`，仅是本次浮点复读预算，不是物理性能容差，也不保证每个小分量的相对精度。
- 修正限定到当前绑定输入的五个 `physics:principalAxes`；还原这些属性后 USD 序列化须与原层完全相同。其它 manifest 设置和网格字节保持不变；输出到新隔离目录，不覆盖原件。
- 同一测量函数须能显示修复前差异和修复后一致；投影删除平行轴项时，自检必须失败。只有已解释并验证的惯量才能交给 PD 初值计算。

## 结果

### 实际缺陷及修正

原候选的 31 个 link 质量和质心均一致，两个姿态的 actor/FK 最大矩阵分量差均为 8.66699218837752e-7；但 `lf_elbow`、`rf_elbow`、`rl_knee`、`rr_knee`、`tail1_pitch` 的主轴四元数把惯量分量循环置换到了错误方向。运行时质量矩阵符合这份错误 USD，不能靠“改用运行时矩阵”消除来源差异。

肘/膝的 URDF link 坐标惯量对角为 `[0.042611,0.042611,0.017492]`，USD 主惯量为 `[0.017492,0.042611,0.042611]`；四元数 xyzw 为 `[0.5,0.5,0.5,0.5]` 时重建为 `[0.042611,0.017492,0.042611]`。尾部同类问题使 `[0.177366,0.237661,0.132145]` 变为 `[0.237661,0.132145,0.177366]`。将这五处主轴改为其共轭 `[-0.5,-0.5,-0.5,0.5]` 后，`R*diag(I)*Rᵀ` 恢复 URDF 张量；未重设计质量或惯量。

| 姿态 | 原运行时矩阵与 URDF 最大差 | 修正后最大差 | 修正后浮点预算 |
|---|---:|---:|---:|
| neutral | 0.10550082112610326 | 2.004629788743273e-5 | 2.2871349938213825e-4 |
| existing_c_0.25 | 0.10550082112610326 | 2.0275802199876125e-5 | 2.2724305745214224e-4 |

修正后所有 link 的质量、质心、USD 张量与 URDF 相符；原始运行时张量直接按 actor 坐标投影也与质量矩阵相符，再乘一次 COM 主轴旋转的假设反而不符。两姿态读回区分了这两个 frame 假设，没有把字段名当坐标依据。前后源码的测量函数未变，仅增加隔离修正及身份记录；两次完整采集均正常退出，原报告状态是 `captured_inertia_mismatch`，修正后为 `authored_inertia_and_mass_matrix_verified`，不能仅凭退出 0 判通过。

隔离层恢复检查通过；manifest 除新路径、对应哈希和修正来源字段外逐项相等，具名过滤及运行配置保留，所有网格文件字节相等，原文件哈希未变。此结论绑定本次候选，不是任意 USD 的通用共轭修复政策。上游转换在哪一步写反主轴尚未定位，正式导出接线仍须防止再次产生该错误。

投影自检通过；删除平行轴项后同一入口 AssertionError、退出 1。实际原资产不满足同一数值条件，隔离修正后两个姿态满足；没有新增仓库闸门或扩大 ROM/轨迹采样。

### PD 接续

`pd_coefficients.json` 保存两个姿态、全部 30 个关节的矩阵对角及 `Kp/f²=I*(2π)²`、`Kd/(ζf)=2I*(2π)`。例如前肢 swing 的两姿态/左右范围为 I=1.000934–1.007745，Kp/f²=39.515286–39.784179；腕部 I=0.00891156–0.00891159，Kp/f²=0.351814–0.351816。f 单位 Hz，Kp 单位 N·m/rad，Kd 单位 N·m·s/rad；armature 已读回为零。对角表示基座及其它关节锁定的近似，不是所有关节同时运动、自由基座或接触下的精确有效惯量。频率和阻尼选择字段留空，没有暗定物理周期或正式增益。

下一切片用该隔离修正目标准备一套固定机身的小幅平滑跟踪配置，比较前固定频率、阻尼、窗口、误差/超调与停止条件及试验预算；需要用户决策的数值集中提出。跟踪后再按专项执行自由基座静站、单腿抬落及低速试走。新 q(c) 的插值/时间映射、有效限速、载荷和承重仍未验，不重新启动 A 的几何探索。

## 证据引用

- 入口：提交 `8bda52f` 的 `rl_exp/tools/diagnose/palm_spatial_inertia.py`，SHA256 `51d7bd7429397854f411274f46fd69df81d5bad76adcc7f72cef9df85436414e`；原采集源码快照 SHA256 `43b41dee07c2a72ea64d6f65e16978fc5cda0fb491b3d82cac81315ca772d163`。该代码提交的仓库预提交闸门通过。
- 上游接线：`acceptance/records/2026-10-15-lizard2-e-spatial-runtime-wiring.md`；几何输入：`acceptance/records/2026-10-19-lizard2-contact-path-correction.md`。
- 原报告：`rl_exp/out/lizard2_b_inertia_20261019/report.json`，SHA256 `34b03f2b558bbc9ed1396b565df0b94d7d85d238c18096a5103f790552c68075`。
- 修正报告：`rl_exp/out/lizard2_b_inertia_repaired_20261019/report.json`，SHA256 `0c82f1202e8b040a893404a0ddc1cf9e75d0f2e17d9c76e75cb83828cf6ef6de`；同目录 `neutral.json`、`existing_c_0.25.json` 和 `source.py` 保留原始读回及当次源码。
- 原 manifest：`rl_exp/out/lizard2_e_registered_20261015/connections_verified_20261016/registered_manifest.json`，SHA256 `eb58101306a1f27f931a63c6e24f00267946d91596a1c8e55b07f4490bbd9b62`；原 USD `62f430ee78fbfa45bf65d43d34f3f8bd332316cf0e68919511a2a8fb6dbfcb19`。
- 修正 manifest：`rl_exp/out/lizard2_b_inertia_repaired_20261019/registered_manifest.json`，SHA256 `7cb49fbe9d4ad4796148c4b80e5041066217ad277638837cb6ada9447032e19f`；同目录 USD `5f259d9e42d163ae60fa81f40aa9ec82bf4ad260dd976dfd0472deaea03a0b25`，URDF 保持 `2c78117020458d5e7934219a2064bf7241430b81c2a736acd8cc0761c7a1461f`。
- 系数：同目录 `pd_coefficients.json`，SHA256 `7d37db3f68d21b21f5b0cb41c85bd7b2ce358142319794cb710f7f6437968715`。这些本机产物引用不承诺入仓。

从仓根执行，输出目录须不存在；去掉 `--repair_inertia` 可对同一原输入复读缺陷。自检破坏命令预期退出 1：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_inertia.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_inertia.py --self_check --break_projection
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_inertia.py --repair_inertia --reset_report rl_exp/out/lizard2_e_registered_20261015/connections_verified_20261016/reset_probe_report.json --pose_report rl_exp/out/lizard2_a_contact_delivery_20261019/report.json --out rl_exp/out/lizard2_inertia_reproduce --viz none --device cuda:0
```

系数可从报告离线复算，不起 Isaac；以下 Python 片段打印全部关节，f/ζ 仍待具体测试配置选定：

```python
import json, math
from pathlib import Path
r = json.loads(Path('rl_exp/out/lizard2_b_inertia_repaired_20261019/report.json').read_text())
assert r['completed'] and r['status'] == 'authored_inertia_and_mass_matrix_verified'
for s in r['snapshots']:
    assert s['runtime_fixed_base'] and s['mass_matrix_checks']['urdf']['within_roundoff_budget']
    for k, name in enumerate(s['joint_names']):
        inertia = s['mass_matrix'][k][k]
        print(s['label'], name, inertia, inertia*(2*math.pi)**2, 4*math.pi*inertia)
```

## 未覆盖边界

未证明 URDF 的近似质量模型符合真实材料分布，未对其它姿态或自由基座惯量给出精度结论。没有驱动激励、有效限速对照、接触负例重跑、承重或 PD 调参结果；原具名过滤行为证据只在其原边界复用。本次新身份须供后续 B/E 使用，不能继续拿旧 USD 做动力学，也不把本轮状态写读当五角色真实驱动验证。上游导出链、转向/恢复、C 协同及 D 审核保持在办；未关闭专项。

## 新正式导出输入的运行时惯量复验（2026-10-20）

### 范围与批准

用户要求继续下一步并确认：各单环境一次启动、固定基座/无重力/零增益，分别做新输入运行时质量矩阵及独立在线观测检查；复用 neutral 和已批准旧 `c=.25` 非零状态，不加命令物理步、不调 PD、不训练、不替换正式资产。新转换/reset/action-cache/contact 的来源取 `acceptance/records/2026-10-15-lizard2-e-spatial-runtime-wiring.md` 的 2026-10-20 追加段；本节只解除该新输入的固定基惯量测量缺证。

### 入口与写前拒错

`palm_spatial_inertia.py` 新增成对 `--approved_reset_sha256/--approved_pose_sha256`，解析报告、写输出或启动 Kit 前核外部批准。fresh 分支消费 reset 实际绑定的 **replay manifest**，其 runtime order 为 None；原 `check_registered_manifest(measured_order=False)` 强制此条件，不是删除顺序检查。不得换成已测顺序的 measured manifest 来混用两类来源。完整 export、USD/URDF、73 件 mesh/STL/OBJ 来源绑定复用现有验证器；禁止 fresh 调用旧 `--repair_inertia`，旧入口/原源 pin 不改。

同一实际 fresh 输入，旧 HEAD 入口在 `runtime order not measured input` 拒绝，新增入口通过。持久 fresh self-check 正例及十负例均通过：错 reset/pose 批准、部分批准、repair 混用、外部/已有输出、错姿态来源、错 manifest、新 URDF 失绑、继承旧 runtime order；日志 `rl_exp/out/lizard2_e_fresh_inertia_selfcheck_20261020.log` 保留拒词。旧自检和删除平行轴项破坏测试保持原语义；修复前正例输出由实现上下文记录，未保存带旧源码摘要的红工件，不声称独立旧身份认证。新增输入/CLI 未改 `_snapshot` 或 `_project`，新上下文对 HEAD AST 一致。

### 真实结果

真实命令退出 0，`completed=true`、`authored_inertia_and_mass_matrix_verified`。normal reset 后仅记录 neutral，再写既有 `c=.25` 状态、forward/刷新记录；无新增命令物理步。两姿态固定基、全部 stiffness/damping/armature 零。

| 读数 | neutral | existing_c=.25 |
|---|---:|---:|
| 完整 30×30 URDF 投影与 runtime M 最大误差 [kg·m²] | `2.004629788743273e-5` | `2.0275802199876125e-5` |
| 原浮点复读预算 [kg·m²] | `2.2871349938213825e-4` | `2.2724305745214224e-4` |
| 非对角最大误差 [kg·m²] | `1.237164e-6` | `1.241556e-6` |
| actor/FK 最大矩阵分量差 [m 或无量纲旋转分量] | `8.66699218837752e-7` | `8.66699218837752e-7` |
| joint position 与批准状态最大差 [rad] | `0` | `6.318272e-9` |
| runtime M 特征值范围 [kg·m²] | `[0.00805784,30.17230960]` | `[0.00806931,29.97037302]` |

全部 31 body mass/COM/full tensor 对 URDF/USD/raw 一致，总质量 72.0004 kg；live 对 URDF 最大差分别 `4.7302e-7 kg`、`2.5814e-8 m`、`2.9644e-7 kg·m²`。两矩阵有限、对称、正定，不仅对角通过。raw tensor 按已实测 actor-local 投影一致；再乘 principal rotation 的假设复现 `0.10687028870278947 kg·m²` 错差，属于重复坐标转换，不判新 USD 有未解释惯量错误。

独立新上下文 `692d19c1-5975-4640-9955-0649e8b6be40` 直接读实际 URDF/USD/replay/源码/快照，不调用采集器 `_project`，另用内存 FK/Jacobian 重建全 900 元素，包含非对角耦合。独立 FK 投影差 `3.992498e-5/4.040834e-5 kg·m²` 仍在原预算内；ΔM 对 actor 投影差 `2.963187e-7`、对独立 FK 投影差 `1.023087e-6`，均低于约 `1.63367e-6` 复读预算。两姿态最大 diagonal 变化 `0.214128494`、非对角变化 `0.098855427 kg·m²`（胸 yaw/pitch 耦合）；变化有完整投影解释，不能据 PD 标量初值说关节已解耦。审核批准本轮固定基惯量工件，无阻塞。

### 身份与复读

| 文件（仓根相对路径） | SHA256 |
|---|---|
| `rl_exp/tools/diagnose/palm_spatial_inertia.py` 及本次 `source.py` | `8e1de03091d5f8f356423c27861cc085317ac84486d35e3ea23c588410d9edc6` |
| `rl_exp/out/lizard2_e_fresh_inertia_20261020/report.json` | `f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd` |
| 同目录 `neutral.json` | `e9afc4f3a20592df52a61163c5679c56f2f6fd9d569cc66ed35f664aac51ab9c` |
| 同目录 `existing_c_0.25.json` | `7311a8313fc41b3521b08a5bfb887ea9a1d972690b451d0552ae1b5726680389` |
| `rl_exp/out/lizard2_e_fresh_reset_20261020/registered_manifest.json` | `d9d8cbc04d7295966c82735b03778fa7eacf990099b3b32d6c0f3e0ad37fa5f3` |
| 同目录 `palm_spatial.urdf` | `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00` |
| 同目录 `palm_spatial.usda` | `0c5ffd157b39faf9b65907877badbe069ae5af69585124a1097f94956df3fe76` |
| `rl_exp/out/lizard2_e_fresh_inertia_20261020.log` | `21193ac87f90a78c1d6188a650da16c178ea2c56a3345d59fa96c1f76c1975ec` |
| `rl_exp/out/lizard2_e_fresh_inertia_selfcheck_20261020.log` | `ce27f059018cd79478fb88e28701fac71d9f434685a97df9e616f889c11d7c2a` |

输入 reset 批准摘要 `22cd55fe9d38a4325b50eac774b86a7686728f4611fb29f5705d212524e0ba0b`；旧姿态报告批准摘要 `1d5ae02e0f7c4724144f1eb956c25f95899a53367603a0662c5196ae4052dc3b`。工件、候选文件与三个框架源摘要经独立复算匹配，结束再次复读无变化；本机产物不承诺入仓。

从仓根复读，用新输出路径；下列 `replay` 未当作本轮实际已运行目录。输入自检需去掉 `--headless --device cuda:0` 并追加 `--self_check`，只做输入/投影拒错、不创建目录；独立 `--self_check --break_projection` 预期失败：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_inertia.py --headless --device cuda:0 --reset_report rl_exp\out\lizard2_e_fresh_reset_20261020\reset_probe_report.json --approved_reset_sha256 22cd55fe9d38a4325b50eac774b86a7686728f4611fb29f5705d212524e0ba0b --pose_report rl_exp\out\lizard2_a_contact_delivery_20261019\report.json --approved_pose_sha256 1d5ae02e0f7c4724144f1eb956c25f95899a53367603a0662c5196ae4052dc3b --out rl_exp\out\lizard2_e_fresh_inertia_replay
```

### B 交接与未覆盖

B 可消费此实际 runtime 名序、完整 M（含非对角）与绑定资产作**固定基**默认 PD 初值依据；diagonal 是其它关节锁定近似，不把它当耦合消失或接触/自由基座有效惯量。资产、质量/COM/tensor、约束、armature 或状态变化须核对应 M。

快照未保存 joint velocity，只能确认源码写零速度，不能声称两姿态速度读回已独立实测。不证明真实材料分布、其它姿态、后端 drive target/实体运动、受载保持/跟踪、实际饱和或有效限速；这些继续 B/C/E。在线观测的独立复验另见接线记录对应追加段，未冻结新 obs 协议。无新 PD 工程取值或物理激励预算，未关闭整个 A/E/B/D。
