# lizard2 当前 palm 整机候选限位：只读实际几何扫描（2026-10-13）

## 适用范围

用户选择“先确认全部限位”，随后批准“作为待验证工程候选”，不是批准正式机械限位或动物 ROM。保留当前低机身、四肢竖直下段、自然贴地尾的 Blender 模型；本轮不生成 URDF/USD、不改正式资产、配方、PD 或执行器限速，也不关闭相邻碰撞。执行者直接运行检查，未委托。

落点：`rl_exp/blender/scripts/lizard2_stance_candidate.py` 的独立 `palm_limit_probe()` / `--limit_probe`。旧生成模式不改。该入口只读取保存场景，在内存设置真实诊断姿态并恢复；仅将报告写入新隔离目录。

## 验收条件

- 从真实保存场景取得骨树、actual head/frame、evaluated 网格与实体归属；通过原 P1 消费者核对四角色 palm 链，不能猜固定五轴布局。
- 按用户批准的工程候选范围扫描，明确零位与轴符号；不同于旧资产或动物角度。轴也仅是待验证功能提案。
- 有符号肘膝折角不得跨过伸直侧；真实 Blender 反曲姿态作为负例。离线刚体运动必须对照真实 Blender 逐顶点运动。
- 实体碰撞包含排除关节球后的全部真实网格，连接区与远距碰撞按实际树距离分别登记，不假定运行时已过滤。
- 翻掌按实际向下掌底面导出的有向法线检查；地面按固定基座扫描登记，不将静态全盒采样当完整浮动基座动作周期证明。
- 出现反例留为候选不通过，不放宽判据、不把局部连接处穿插一律归类远距碰撞；完整范围确认前不导出。

## 结果

**候选范围尚未确认，整盒存在明确反例，停止隔离导出。** 工具退出 0 只说明诊断完成，不表示限位设计通过。

输入：`rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical_tail_ground/sample_neutral.blend`，SHA256 `c6566679f514581dd972e40dfbbb9d6f115a43e975f861ab4c57a53e3496ca47`。最终原始报告：`rl_exp/blender/lizard2_palm_limit_probe_20261013_verified/measurements.json`。首轮报告保留于 `rl_exp/blender/lizard2_palm_limit_probe_20261013/measurements.json`，其直接父子分类不能独自区分带无网格短轴的连接区；最终报告增加实际树距离和真实反曲姿态负例，不改写首轮报告。

### 范围与轴：工程提案，不是实施值

以当前保存姿态为 q=0，共 26 个活动关节。每条前肢 shoulder_swing/shoulder_abduct/elbow/wrist，后肢 hip_swing/hip_abduct/knee/ankle；胸/颈各 yaw/pitch，尾三组 yaw/pitch。

| 角色 | 候选下/上限 [rad] | 候选幅度 [deg] |
|---|---|---|
| 肩/髋 swing、abduct | −0.6 / +0.6 | ±34.377468 |
| 肘/膝 | −1.2 / +1.2 | ±68.754935 |
| 腕/踝 | −π/6 / +π/6 | ±30 |
| 胸/颈/尾 yaw | −0.6 / +0.6 | ±34.377468 |
| 胸/颈/尾 pitch | −0.5 / +0.5 | ±28.647890 |

左肩/髋 swing 世界 +Z，右侧按轴矢量镜像为 −Z；左肢铰链由上段 cross 下段导出，右侧 −R 镜像。胸/颈/尾 yaw 暂按世界 +Z，pitch 按当前实际骨 local +X。轴在父级转动时随父运动，原始完整向量在 JSON。没有以 bone roll 自动证明该功能轴正确，也没有把旧躯干世界轴悄悄当新尾 rest 轴；最终轴选择仍待核对。

### 肘膝边界及真实运动核对

| 关节 | 伸直 q [deg] | 完全折叠 q [deg] | 负向候选边距伸直 [deg] |
|---|---:|---:|---:|
| lf_elbow | −80.161598133 | 99.838401867 | 11.406662717 |
| rf_elbow | −80.161595935 | 99.838404065 | 11.406660519 |
| rl_knee | −80.160803720 | 99.839196280 | 11.405868305 |
| rr_knee | −80.160803905 | 99.839196095 | 11.405868489 |

四腿在所提肘膝范围内未跨伸直侧，几何余量约 11.41°；这不是跟踪误差/控制安全余量验证。与旧机体的 ±75° 伸直位不同，不能搬旧事实。

实际将四个肘膝旋至各自伸直位之外 0.01 rad，evaluated 有符号折角为 −0.572934998 至 −0.572979171°，均被反曲判据拒绝，再恢复。26 轴分别使用候选正端，所有下游实际 evaluated 顶点与独立刚体树变换互比，最大残差 `1.9120576403682606e−6 m`，小于由源坐标导出的 float32 算术界 `2.781680814223364e−5 m`。算术界不是批准净空或穿透容差。

### 反例与分类

169 个姿态：中立位 1、每轴四个单关节档共 104、四腿各 16 个区间盒角共 64。没有扫描全部 26 轴组合、连续域或真实动作轨迹。

- **翻掌：16/169**。例如 lf 四轴同时取负端（swing/abduct −0.6、elbow −1.2、wrist −π/6 rad），实际掌底向上法线 Z 为 `−0.6836868524551392`。单轴范围各自看来可用，不代表组合不会翻掌。
- **树距离 >2 的远距表面交叉：12/169**。例如仅 `chest_yaw=−0.6 rad` 就出现 `rr_ankle ↔ rf_wrist`（距离 10，39 对表面三角交叉）和 `rr_knee ↔ rf_elbow`（距离 8，8 对）。这是不同腿实体，不是关节球，不得以相邻过滤解释掉。
- 中立位表面交叉全部为树距离 1 或 2 的连接区；带 meshless yaw/swing 的两步连接不能按“非直接父子”误称远距碰撞。最终报告逐对给出实际距离，**仍保留连接区原始交叉，不做过滤**。这些对是否在新 USD/PhysX 中被排除尚未验证。
- 全部姿态均出现至少一次 BVH 交叉，因为原有连接区持续相交；不把 169/169 误读为每个姿态都新增远距冲突。
- 固定基座地面项 169/169 含源后掌约 −35 μm 的既有不共面偏差，不能将其宣传成每档都有大穿地。另有明显工况反例：`tail1_pitch=−0.5 rad` 时远端尾网格最低点下降到固定地面以下 `0.5413403660058975 m`；tail2/tail3 负向 pitch 也使当前贴地尾向地下转。固定平面反例需要区分机械活动域和拖地/悬空阶段目标，不据此直接冻结为单侧限位。

当前输入网格和骨架均未改。Blender 树内所有被保护文件的 SHA256 前后相同；源中立 pose 在每个真实诊断后恢复。生成器、USD、运行时 collision filter、PD 均未修改或验证。

## 证据引用

仓根 Windows cmd，实际执行：

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp/blender/scripts/lizard2_stance_candidate.py -- --limit_probe --output_dir rl_exp/blender/lizard2_palm_limit_probe_20261013_verified
```

最终退出 0；四个真实反曲负例被拒，26 轴运动核对与 169 姿态扫描完成。输出已经存在，复读须选新的同级 `lizard2_palm_limit_probe_*` 空目录，禁止覆盖旧报告；新增本地报告路径应精确排除，不提交模型或诊断 JSON。

只读来源：`rl_exp/blender/scripts/generate_urdf.py` 的 `BALL_MESHES` 与真实 `lizard2_palm_contract` 消费；旧限位与已确认不反曲要求见 `acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md` R4、`acceptance/records/2026-10-09-lizard2-knee-reverse-bending-measurement.md`。用户本轮接受的是工程候选扫描，不是沿用这些旧记录的机体结论。

## 执行者独立反例复读与当前输入边界

另用 Blender `--python-expr` 实际打开原保存场景，不调用本次刚体树 `motion()`，直接设置 `chest_yaw=−0.6`，对两腿 evaluated 真实碰撞网格构造 BVH：`rr_ankle ↔ rf_wrist` 仍有 39 对表面交叉。恢复胸 yaw 并设置 lf 四轴负端，实际腕 frame 的向上参照法线 Z 为 `−0.6836868524551392`，确认翻掌反例不是自写 FK 错误。四肢反曲负例也已在生成器内实际运行，不只检验标量公式。

本轮末读取到当前事项已路由后肢长度与足掌比例修订、四掌共面，依据为 `acceptance/records/2026-10-13-lizard2-specimen-hindlimb.md`，该记录仍是施工中。这里的源路径、hash、80.16° 伸直边界及全部反例**仅属于 natural-ground-tail 源**，不冒称修订后候选读数。新后肢完成后必须重新绑定、复量边界、再扫描；本轮没有覆盖或暂存并行的事项修订、报告接线或新比例生成代码。

旧 P1 契约回归、编译与 `git diff --check` 实际退出 0；旧消费者三条、palm 正例及十条拒错负例保持通过。以下提交前闸门也实际全部退出 0，保留既有 fork dirty、历史 tag 与限速警告，不解读为新机体物理通过：

```cmd
python rl_exp/tools/verify/check_suite_banners.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/framework_pin_check.py --strict --self-test
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_dr_parity.py --strict
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_version_docs.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_work_docs.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_obs_protocol.py --live
```

## 未覆盖边界

BVH 仅测实际表面交叉，纯包含可能漏报；计数不是穿透深度或力。有限样本只能证存在反例，不能证完整盒安全。中立连接区不能推断运行时过滤，零导出也不能宣称新资产已被物理验证。

最大风险是把独立限位盒当动作允许域：已见翻掌和跨腿碰撞，单纯保住肘膝非反曲不足。下一步应先按反例复核轴、范围/组合及动作阶段，再向用户确认修订；不能事后扩大净空容差、关闭全身自碰撞或直接调整 PD 掩盖几何问题。新机体惯量、驱动匹配、URDF/USD 漂移、运行时硬限位及实际碰撞过滤仍未完成。整项保持 in_progress，不进正式采用或训练。
