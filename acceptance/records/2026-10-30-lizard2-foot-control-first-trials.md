# lizard2 双轴脚板有限 PD 与踮脚首轮执行

## 适用范围

承接 `work/active/lizard2-foot-design-tradeoffs.md` 与 `work/active/lizard2-two-axis-feet.md`。用户确认执行有限协议：新增轴固定 Kd=20 N·m·s/rad，Kp=50/100/200 N·m/rad 各保持8秒；稳定的较低档检查 ±0.05 rad、1秒斜坡响应；当前双轴模型离线核2cm踮脚路径再做有限物理诊断，总墙钟预算30分钟。未训练、未修改正式资产/配方、惯量、材料、机械限位或限矩，未增加夹具或脚趾。

## 验收条件

单次出现终止、非有限位置/速度、根高低于0.45m、倾斜超过30°、任一原腕踝或新增轴的机械限位余量小于0.02rad时，在自动reset之前保存失败行并停止本次；失败不取消其它独立档。这些是用户确认的停止线，不是性能通过阈值。保持末2秒分别报告均值误差及前后半窗均值差，不将零漂移误作零误差，也不在数据出来后反推合格阈值。

实际力矩与饱和读回缺失；接触记录为控制步内传感器历史窗口逐刚体净力模长峰值，非地面滤波、接触区域或材料点滑移测量。根高是根参考点，不是全身质心。没有可信前缘接触及滑移读点时不得判踮脚通过。

### 输入与实现

- 候选 URDF：`rl_exp/out/lizard2_two_axis_20261029/candidate01/lizard2_two_axis.urdf`，SHA256 `0a506f94e48087aae9d4af64716b170ba744981ae8392bdd3d91917911a552dd`。
- USD：同候选的 `lizard2_two_axis/lizard2_two_axis.usda`，SHA256 `a90de34b39f59dd65399d38d18f0b2f8b10cd434f2de063305cb41715e5ede05`。本机工件不承诺入仓；其余驱动及动作接口以v6诊断配置为基线，新四轴由脚本显式追加。
- 运行仓基线 `a4c85906a709`，IsaacLab `28a37cecdd43`；本轮脚本为dirty tree，原始报告带脚本摘要。报告不是冻结发布，跨源码阶段不冒充相同字节运行。
- 本机 fork 的 `ArticulationView` 没有 `get_enabled_self_collisions()`；首次准备运行因 AttributeError 退出，未形成保持数据。修复为读取**已加载USD场景**的 `PhysxArticulationAPI`，每环境均为false才继续；不是声称有后端物理getter。地面仍启用。
- 复用 `lizard2_two_axis_standing.py`，增加选择新增四轴的9环境响应、停止线、速度/限位/原始动作/最终目标记录、独占输出及踮脚目标重放；`lizard2_support_sweep_report.py` 增加保持末窗描述性统计。新 `lizard2_tiprise_geometry.py` 复用既有FK/IK，不另建求解器。

## 结果

### 三档保持

三档均采满8秒，未触已列停止线。原轴增益保持v6，新增四轴统一本档Kp与Kd=20；同外部条件不等于同足载。零尾目标保持包含尾部接触：50档末窗中tail2_pitch历史净力峰值约34.35N；因此不是严格仅四足支撑，也不能将尾部触地当成比例已知的支撑。

| 新增轴Kp | 末根高m | 末2秒最大倾斜deg | 新增轴平均实际-目标误差rad（lf/rf/rl/rr） | 8足轴最大末窗前后半均值差rad |
|---|---|---|---|---|
| 50 | 0.52045 | 3.294 | +0.43885 / −0.43869 / +0.25632 / −0.25871 | 1.30e−6 |
| 100 | 0.52733 | 3.221 | +0.22611 / −0.23041 / +0.12609 / −0.12949 | 1.48e−4 |
| 200 | 0.56555 | 1.756 | +0.08589 / −0.08721 / +0.03252 / −0.03335 | 9.19e−6 |

低档已近似定姿，但偏差很大；这不是“50已满足脚掌用途”。更大刚度组合减小当前工况的静态偏差，没有证明独立关节力矩、硬件余量或踮脚能力。

### 新增轴小幅往返

选择能完成保持且未触停止线的最低档50/20做响应诊断，不要求静态偏差先达标。9环境：零动作参考＋四新增轴各正负一例，4秒静置，1秒升到±0.05rad，保持1秒，1秒回零，再观察2秒，共9秒。全部完成，无停止事件，末目标回零。各正负分支并非同一环境连续换向，不当作迟滞回线验证。

5.1–5.9秒实际角相对同时零目标参考环境的平均差：

| 新增轴 | 负分支rad | 正分支rad |
|---|---|---|
| lf | −0.02639 | +0.01320 |
| rf | −0.01618 | +0.02462 |
| rl | −0.04271 | +0.04160 |
| rr | −0.04169 | +0.04273 |

前足受载响应明显小于命令，不能由此单独判电机弱。响应窗口不等于末窗；回零后的末窗不能代替正负目标响应。

### 踮脚几何与物理

离线以根前向+x在真实碰撞网格最低面选前缘，绕根+y倾转0→0.15rad、根高目标增加0.02m，11个离散节点通过。后缘目标抬高约34.29mm，四足相对小腿目标转角前足约0.1951rad、后足约0.1767rad，足轴限位余量至少0.3429rad。检查36个visual/collision网格，非足最小地面间隙约79.04mm。仅节点候选，不声称连续安全、实际接触或滑移验证。

本路径初始根高约0.602799m，尾首pitch=0.3rad；它与前述零尾目标保持场景不同，不能直接混表。路径期间仅发送完整关节目标，根不写轨迹、不托举；4秒静置、2秒踮起、1秒保持、2秒回落、1秒恢复。根高必须由动力学自然产生。

首个物理尝试误用上游wxyz初始化，在本机xyzw fork中形成翻转，第1步触倾斜停止；该失败原始记录保留，不作驱动结论。修正为xyzw identity后再跑，实际首行根四元数接近 `[0,0,0,1]`。原始50档成功运行记录把逐帧四元数字段误命名为 `root_quaternion_wxyz`，**值实际为xyzw**；未重写原记录，后续源码及100/200档字段已改正。初始化q0与已求解第0节点本次最大差为0，不存在本次目标跳变。

| 新增轴Kp / Kd20 | 4秒静置末根高m | 目标顶端附近实际根高m | 结果 |
|---|---|---|---|
| 50 | 0.50159 | 7秒0.47709 | 完成10秒，但下沉约24.5mm，不是踮起；回落段末恢复至0.50095m |
| 100 | 0.51289 | 7秒0.49950 | 完成10秒，但下沉约13.4mm，不是踮起；末0.51261m |
| 200 | 0.52480 | 6.98秒0.50423 | 触足关节限位余量停止线，未完成回落 |

200档触发的是**左前原腕轴**：实际+0.50390rad，目标−0.07371rad，上限余量0.01970rad；不能写成新增轴缺刚度，也不能靠继续提高新增轴刚度批准通过。三档均未证明主动踮脚，未补测400、未放宽停止线或改正式驱动。

## 证据引用

本机输出根 `rl_exp/out/lizard2_foot_control/`，JSON原始时序与同名日志保留，不随日期清理：

| 相对输出根文件 | SHA256 |
|---|---|
| `pd02/keep_kp50.json` | `dcb9e8367fa248db4dfbb4db9085532587a53ad94f9d8bb67ba7f619d45596cd` |
| `pd02/keep_kp100.json` | `0089a35069b69d2d03137caf99650ccf0bc03754130960dfb3853a01e7614420` |
| `pd02/keep_kp200.json` | `035ea2b2201d85f6476b7d30b9293e04ee8417572a4c2bdbbbad08e6b3d90f54` |
| `pd02/feet_kp50.json` | `5db4d1dc7714cfd24fbd9733972a1ead3cb1d2412c12185b0904a538cc1c741c` |
| `tiprise01/geometry.json` | `30fdf1c6fabd9f846149e51a30b182b250c06a66601317a54b3719703bbe6043` |
| `tiprise01/native_kp50_kd20_10s.json`（错误初始化） | `75cd4bc671f09ee86ba09e3aae07f94fa55c98f20b69e1d3eb278b0c58a77093` |
| `tiprise01/native_kp50_xyzw.json` | `2ab5611ef8923a461cd0a58edbe00a433c8f69943266c103d615a108fdc6461b` |
| `tiprise01/native_kp100_xyzw.json` | `718f2462ee038a65240fa97deb0cb065c11a8c5a3c3417c53341238c13fb32c7` |
| `tiprise01/native_kp200_xyzw.json` | `1afc9c22b487584dd58750d490a92e5f7af00fd17db769647b9207535b8987fa` |

解释器使用 `ablation_harness/host_paths.py --python` 本机返回值；从仓根复读，所有 `--out` 必须换全新路径，不覆盖现场：

```text
python -B rl_exp/tools/diagnose/lizard2_two_axis_standing.py --candidate_usd <上述USD> --lateral_kp <50或100或200> --lateral_kd 20 --duration 8 --safety_checks --headless --out <新保持JSON>
python -B rl_exp/tools/diagnose/lizard2_support_sweep_report.py <保持JSON> --hold --window_s 2
python -B rl_exp/tools/diagnose/lizard2_two_axis_standing.py --candidate_usd <上述USD> --lateral_kp 50 --lateral_kd 20 --feet_sweep --test_target .05 --settle_s 4 --ramp_s 1 --duration 9 --safety_checks --headless --out <新响应JSON>
python -B rl_exp/tools/diagnose/lizard2_tiprise_geometry.py --urdf <上述URDF> --out <新几何JSON>
python -B rl_exp/tools/diagnose/lizard2_two_axis_standing.py --candidate_usd <上述USD> --candidate_urdf <上述URDF> --tiprise_geometry <几何JSON> --lateral_kp <50或100或200> --lateral_kd 20 --duration 10 --headless --out <新踮脚JSON>
```

重放当前源码将使用正确字段与初始化，不会重现程序错误的首个试次；源码更改和原始摘要必须区分。保持/响应仅筛查新增轴，原轴用途验证仍不足；接触区域/滑移专项还未交付，踮脚不能判通过。

## 未覆盖边界

新增安全、保持判读、目标时序及踮脚几何测试，修改前缺接口导致失败，修后专项11项通过；四元数初始化回归约束本fork身份。完整离线套件在UTF8模式下37/37通过，后续最终提交钩子另核。另一新上下文已对记录与原始JSON核对主要读数，未发现阻塞性证据不一致；该核对未独立重算全部文件摘要，也不是能力通过或关闭审核。自检不替代新上下文能力审核。

下一步先定位踮脚时原腕轴目标与实际反向偏差、受载姿态及前缘接触，检查几何路径与实际下沉姿态失配；在不变更结构和限矩前提下提出原轴/新增轴分别调整的最小对照及预算。需要可信接触区域/滑移证据才能判踮脚通过。未核实际力矩、饱和、真实惯量、粗糙地形、扰动、重复性和行走能力；不核定正式PD、不关闭事项。
