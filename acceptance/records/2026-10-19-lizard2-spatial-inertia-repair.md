# lizard2 三轴候选：惯量主轴修正与 PD 初值交接

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
