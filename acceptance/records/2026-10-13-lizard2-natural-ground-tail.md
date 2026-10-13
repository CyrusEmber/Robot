# lizard2 自然远端贴地尾：静态候选已生成，待独立审核（2026-10-13）

## 适用范围

用户要求是“远端尾段自然贴地”，不是“远端两段最长支持边同时精确贴地”，也没有禁止小幅轴向 roll。现已完成实际三维支持面搜索、固定长度连链、尾部刚性 rest 烘焙、保存重开、四张预览和 JSON。**静态几何自检通过；外观与独立审核待确认。** 不批准 ROM、物理、URDF/USD、采用或完整自碰撞。

源是 `rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical/sample_neutral.blend`，没有再降体高。实现是 `rl_exp/blender/scripts/lizard2_stance_candidate.py` 的 `palm_body75_vertical()` 内 opt-in `--tail_ground`；旧模式入口保持不变。

## 验收条件

远端实际实体有轴向面/边支撑，不只尾尖；根固定、固定长度连接、逐段下落；全部尾实体不穿固定地面，保持网格拓扑形状和全部非尾 rest/pose/actual frames 与网格。保存重开验证，真实抬/降尾负例恢复后通过。没有两个最长支持边或任意最大支持比例要求。

## 结果

### 产物

目录：`rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical_tail_ground/`。

- `sample_neutral.blend`：先保存机器人，再添加仅用于渲染的相机/地面；文件内无新 floor overlay。
- `full_side_ground.png`：全侧面，地面可见。
- `tail_close_ground.png`：远端近景，实体与地面连续接触可见。
- `full_oblique_ground.png`：全身斜视。
- `full_top.png`：俯视。
- `measurements.json`：实际三维候选法向、选用旋转、源 actual head/tail/full matrix/basis、全尾实体接触、骨长、逐点刚性残差、非尾 frame 残差、抬/降尾负例、保护哈希及重开结果。

已实际打开侧面和尾部近景：尾根下降到尾二，尾三锥形下表面沿实体长度落地；没有借尾尖单点接触冒充面支持。审美批准仍归用户。

## 实际三维构造与读数

直接用 evaluated cylinder vertices 建 `bmesh` 三维 convex hull，枚举向下的真实支持面法向，小幅 roll 窗口 ±15°；每个候选旋转后用该段全部附属网格（包含 Roundcube）最小 Z 求高度。不用 sagittal 投影代替真实支撑，不猜半径、不削底、不加依赖。

三维搜索在该窗口内未找到两段真实面同时支撑的固定 5 mm bridge；改用用户允许的**尾三真实长下表面落地、尾二渐近地面**。这是实际生成路线，不是整体不可达结论。尾二在其末端截面局部接触，不宣称它具有沿轴向支撑跨度。

- 固定 floor Z = -0.9711321443319321 m；body75 actual root height = 0.6027991026639938 m，源与候选相同。
- 实际链 `base_link → tail1_yaw → tail1_pitch → tail2_yaw → tail2_pitch → tail3_yaw → tail3_pitch` 保持父子树。pitch 长度 0.539228081703186 / 0.4299001693725586 / 0.5784001350402832 m，yaw 长度各 0.004999876022338867 m 保持。
- 选用尾三真实面候选轴向倾角约 -6.989903°，法向径向 roll 诊断约 +11.368180°；尾二从约 -3.299245° 支持姿态小幅再下降，接上固定短桥；非尾 actual frame 完全不变。

保存重开后实测：

| 段 | 全附属实体最小净空 m | 接触顶点数 | 实际轴向接触跨度 m | 判定 |
|---|---:|---:|---:|---|
| tail1_pitch | 0.10691772401332855 | 0 | 0 | 根部下降，未贴地 |
| tail2_pitch | -0.0000001341104507446289 | 2 | 0.00000011715565051417798 | 截面局部接触/渐近，**非轴向支持** |
| tail3_pitch | 0.00000016391277313232422 | 14 | 0.5129618952996111 | 真实实体下表面长跨度支持 |

数值为 float32 evaluated 几何；尾二约 -0.134 μm 属坐标舍入，不是有意下穿或允许毫米穿透。验收使用既有 `64 float32 ulps × max(1, |坐标|)` 运算界，不新增“神奇支持比例”。六个 pitch 附属网格以及其余尾挂接实体逐个检查真实 min Z，不仅检查 cylinder。

## 保持不变与检查

- 源 tail1_pitch basis 非 identity，最大偏差 0.19801978766918182；从其 actual pose matrix 烘焙，不使用 rest 轴猜实际方向。源 cap/joint 偏置随刚性变换保留。
- 只修改六尾骨 rest frame，清零**仅尾** pose basis；源实际帧相对根父 actual/rest 的偏置正确转换。根锚点、pitch 长度、yaw 长度和父子连接逐一检查。
- 独立重开现有候选后，**所有非尾骨** rest matrix、pose basis、evaluated actual matrix 与 body75 baseline 残差严格为 0；**全部非尾 evaluated mesh vertices** 残差严格为 0。因此 body、四肢、neck 不是“近似没动”。
- 全部 mesh 本地顶点、edges、polygons 未改，binding 保持；尾部 evaluated 世界顶点与源刚性变换逐点比较通过，没有缩放、变形、过滤或换拓扑。
- 初次生成哈希保护 **527** 个源资产/工件/冻结文件 before=after；不扫描输出自身进保护集合、不读取整份锁文档。其它会话 dirty 文件不动。
- 真实 geometry mutation：抬全部尾实体 +20 mm → `distal tail lacks surface/edge ground support: tail3_pitch`；降低 -20 mm → `tail mesh penetrates floor: tail2_pitch`。每次恢复后完整不变式重新通过。`--regression_without_fix` 保留抬尾失败，进程 exit 1。
- 未重跑完整旧 preflight，仅目标构造与要求的旧变体回归。

## 证据引用

Windows cmd，Blender 5.2.2 LTS。下面命令去掉 `--check_only` 是本次已执行的生成命令 exit **0**；输出存在时拒绝覆盖，不重复生成。

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --output_dir E:/Robot/rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical_tail_ground --diagnostic_angles=-10,0,10 --palm_shape claw --all_legs --sole_at_ball_bottom --body75_vertical --tail_ground --check_only
```

当前 `--check_only` exit **0**，从源重建目标、执行两类真实负例，再重开已保存候选逐点比较；stdout `TAIL_GROUND CHECK_ONLY PASS`。加 `--regression_without_fix` exit **1**，失败明确命中真实 distal lack-of-support。

旧模式：去掉 `--tail_ground`，output 改原 `..._body75_vertical`：exit **0**；再加 `--regression_without_fix`：exit **1**，真实 root mutation 命中 `body ground height not 75%`。原 halfpad / claw / fourlow 隔离目录与原参数 `--check_only`：exit **0/0/0**。

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -c "from pathlib import Path; p=Path('rl_exp/blender/scripts/lizard2_stance_candidate.py'); compile(p.read_text(encoding='utf-8'),str(p),'exec')"
git diff --check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_work_docs.py
```

本轮无 commit/push；精确输出目录既有 `.git/info/exclude` 规则未改；原资产及其它 dirty 修改保留。

## 同日旧窄路线失败（保留披露，不是当前阻断）

此前约 20% 的只读预检只选择固定 roll 的 sagittal 最长 lower hull 支持线，并误把“两段都精确长跨度支持”当用户硬约束。其 tail2/tail3 所需 bridge 下降 0.007186970436225404 m，而固定长度 0.004999876022338867 m，缺口 **0.0021870944138865367 m**。该路线确实失败，当时未改场景、未生成新候选、527 文件哈希保持。它不是用户约束，也不能推导所有刚性姿态不可行。

旧源 cap/joint 残差 tail1 = 0.03694161422674847 / 0.013132904238363786 m，tail2 = 0.018020378453042524 / 0.009231815617470038 m，tail3 = 0.012231497671184999 / 0.0017251307035232911 m。本次保留这些偏置，不把 cap 强制绑到猜测 pivot。当前成功的是三维支持面加渐近连接路线，未伪称旧两精确支持路线已成功。

## 执行者直接复读（停止委托后）

执行者亲自复跑上面的尾部 `--check_only`：退出 0；追加 `--regression_without_fix`：退出 1，明确命中 `distal tail lacks surface/edge ground support: tail3_pitch`。运行前后新目录六工件 SHA256 完全相同。

另以 Blender `--python-expr` 独立顺次打开 body75 基线与尾贴地保存文件，捕获骨 rest matrix、pose basis、actual frame/head/tail、长度、父子及全部 evaluated 世界顶点，直接互比，不调用生成器检查函数。结果：21 个非尾骨及全部非尾网格严格不变；四条下段实际方向仍竖直；实际 root 离地高度仍 0.6027991026639938 m。六尾骨长度与父子保持，实际子骨 head 与父骨 tail 连续；尾实体按源/目标实际帧推导的刚性变换逐点复核。独立探测使用 30 μm 数值差异告警界，只作复核，不批准位置或穿地容差；主自检仍按坐标导出的 float32 算术界判定。

独立实测六尾网格净空 [m]：`Roundcube.025` 0.45672135055065155、`Roundcube.019` 0.031046375632286072、`Roundcube.018` 0.05471424758434296、`Cylinder.013` 1.6391277313232422e−7、`Cylinder.012` −1.341104507446289e−7、`Cylinder.011` 0.10691772401332855。这核对的是每个真实网格，不把骨线触地当实体接触。已实读侧面、尾近景及全身斜视；视觉认可仍由用户决定。

旧模式直接实跑结果：body75 正例 0、原高度逆例 1、halfpad/claw/fourlow/P1 正例各 0。以下提交前命令全部退出 0；既有 fork dirty、旧 tag 和限速警告保留：

```cmd
python rl_exp/tools/verify/check_suite_banners.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/framework_pin_check.py --strict --self-test
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_dr_parity.py --strict
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_version_docs.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_work_docs.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_obs_protocol.py --live
git diff --check
```

## 未覆盖边界

最大未覆盖风险：静态 floor 支持不是运行时接触稳定，也不是全尾/全身自碰撞认证；小 roll 会改变 hinge 方向，需要后续独立外观和轴审核，不能直接导出采用。旧 lower-palm crossings 未修、未过滤、未声称物理通过。

新上下文在 D 集成后按原关闭条件审核；当前用户查看实际 saved blend 和四 PNG、确认外观。尾贴地不解除其它 P2 前提或碰撞缺口，整体事项保留 in_progress，不进入 P3。
