# Lizard2 P2 无指爪掌：隔离掌形迭代

## 适用范围

2026-10-12，仅 `lf` / `rl`，在 `rl_exp/blender/scripts/lizard2_stance_candidate.py` 现有 P2 流程追加显式 `--palm_shape claw`；默认 `halfpad` 不变。用户已认可当前前臂/小腿末端—掌根连接，本轮只改实体掌形，不再要求重新批准该连接方式；外观、最终尺寸、位置/网格容差仍未批准。状态 **PROVISIONAL_SAMPLE_NOT_ACCEPTED**，事项保持 `in_progress`。

输入源、上/下骨段、腕/踝 head/tail、所有骨架矩阵/轴、父子树、关节数及姿态均与上一 P2 neutral 相同。加载旧 neutral 的 armature datablock 只作逐骨精确相等断言，不把旧对象链接进当前场景。其它肢体与躯干保持原样。无指、趾、拇指残段、爪尖及其活动轴。

## 验收条件

本轮工程出口：新旧同尺度真实网格图、两肢 neutral blend、原始尺寸及真实 cap 顶点测量、封闭/一致外向网格、既有 P1/P2 正反例、-10/0/+10° 诊断及保护哈希。不是美术/几何接受或采用出口。

掌形由六个十二顶点横截面环、侧面及两端封口直接构造，无 bevel/subsurf、无新依赖/测试框架。根截面中心位于腕/踝，真实根 cap 顶点编号在 JSON `rest.*.claw_topology.physical_cap_vertex_ids`；测量沿用 depsgraph evaluated 顶点，不取关节球/显示标记替代封口。

试做依据：保留已有源半掌长度作为尺度起点，延长掌体，掌宽收敛到长度尺度、厚度减小；根窄、前向渐宽、宽远端收圆，中央跖侧近乎平面、背侧轻拱。因最后一环仍宽，远端是带圆角的宽封口，不是趾尖。精确默认配方仅在实现及 JSON `trial_recipe_NOT_approved`；**不是动物测量，不是批准尺寸，也不宣称保持旧尺寸**。保留旧 P2 腕/踝显示骨尾长度，即新网格可延伸超过骨尾，未增骨段。

## 结果

真实 Blender 5.2.2 LTS（d13f752e3b9c）生成退出 0，保存 neutral + JSON + 六 PNG。前侧/斜视、后斜视及前转动图已目视：相比旧圆鼓半垫，新掌明显扁平且前向延伸，根窄、远端宽；旧大关节球仍在，遮挡部分掌根。

12 档真实逐关节 pose / evaluated 顶点与独立世界刚体变换核对：最大运动残差 `3.5762786865234375e-7 m`，最大 cap/root 残差 `4.042583693936627e-7 m`。两掌 72 顶点 / 62 面；bmesh 所有边 manifold + contiguous、signed volume 正，封闭且一致外向。中立实际长/宽/厚、各环尺寸及体积**唯一原始数值家**为本地 `measurements.json` 的 `rest.*.raw_length_width_thickness_m`、`raw_section_x_width_thickness_m`、`claw_topology`；本记录不复制尺寸表。

既有逆修复负例保持含义：实际掌顶点回移半掌长，退出 1，`physical palm root mismatch`，根残差 `0.1399224999935214 m`，居中跨 pivot 被拒。带修复退出 0。错 parent、缺段、stale inverse、残留 toe、转动冻结世界矩阵负例继续检出；转动专属错误漂移 `0.03307483940527777 m`。没有新增宽松容差；现有 float32 算术预算不是用户几何容差。

默认旧 halfpad 正例退出 0、旧逆修复退出 1；P1 正例退出 0、逆修复退出 1，旧消费者 3 / palm 正例 1 / 负例 10。保护哈希 477 文件构建前后及渲染后相同，含两个源/采用 blend 与上轮 P2 全部输出；旧 P2 未覆盖。源 SHA256 `ede254ae904d5ffcb909b55ae134714441d1f0c721b85660531d4b675ebc9010`，采用候选 `0a503c7069d665779392f7f8997c3839e807def9787df97cd0d1b2eb4cf41deb`；旧 P2 neutral SHA256 见 JSON `protected_sha256_before`。其它骨架精确相同，右肢 evaluated 顶点残差 0。

渲染 BEFORE 为同流程重建的上一 P2 **halfpad**，不是旧 source pad；仅诊断 collection 网格、不污染 neutral。JSON 同存重建 BEFORE bounds 及上次原始 baseline bounds；两者有 float32 重建/绑定舍入差，不声称逐顶点位级相同。前后骨线与 pivot 仍同坐标；朝相机移线仅显示，不进入测量。AFTER / BEFORE 完全相同相机尺度。

## 证据引用

本地目录 `rl_exp/blender/lizard2_palm_p2_sample_claw/`，`.git/info/exclude` 精确排除此目录；图片、blend、JSON、日志不进仓。

- `sample_neutral.blend`：仅两肢新掌，中立样本，渲染前保存，无诊断物。
- `measurements.json`：尺寸、实际 cap、原始坐标、保护哈希、机械负例、12 档转动、配方。
- `lf_side.png`、`lf_oblique.png`、`rl_side.png`、`rl_oblique.png`：左 BEFORE halfpad / 右 AFTER claw，骨线/pivot/角色标签。
- `lf_turns.png`、`rl_turns.png`：沿用真实 ±10° cap/掌端线；黄/粉肘膝，蓝/紫腕踝。
- `checks.json`、`claw_without_fix.log`、`claw_with_fix.log`、`halfpad_with_fix.log`、`halfpad_without_fix.log`、`p1_with_fix.log`、`p1_without_fix.log`：完整实际命令、退出码与 stdout/stderr。
- 前序记录只读指针：`acceptance/records/2026-10-12-lizard2-palm-p2-sample.md`、`acceptance/records/2026-10-12-lizard2-palm-chain-p1.md`，不改历史测量。

仓根 cmd 精确复读命令（生成仅限不存在的新目录；已有目录用 check_only）：

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --palm_shape claw --output_dir rl_exp\blender\lizard2_palm_p2_sample_claw --diagnostic_angles=-10,0,10
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --palm_shape claw --output_dir rl_exp\blender\lizard2_palm_p2_sample_claw --diagnostic_angles=-10,0,10 --check_only --regression_without_fix
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --palm_shape claw --output_dir rl_exp\blender\lizard2_palm_p2_sample_claw --diagnostic_angles=-10,0,10 --check_only
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --output_dir rl_exp\blender\lizard2_palm_p2_sample_claw --diagnostic_angles=-10,0,10 --check_only
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --output_dir rl_exp\blender\lizard2_palm_p2_sample_claw --diagnostic_angles=-10,0,10 --check_only --regression_without_fix
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --contract_self_check
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --contract_self_check --regression_without_fix
```

脚本 `compile(..., 'exec')` 成功；`"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_work_docs.py` 最终退出 0，`WORK_DOCS_OK (86 item file(s))`、活跃总量 `99832/100000` bytes。首次检查超预算后，仅缩短本项旧串联审核说明，未删除未完动作或容差要求；并发 E3 更新保留。`git diff --check` 退出 0，`git check-ignore rl_exp/blender/lizard2_palm_p2_sample_claw/measurements.json` 命中本地精确排除。脚本差异 96 行，形状构造约 36 行，复用原构建/测量/负例/转动/渲染。

## 未覆盖边界

最大隐藏风险：关节球大且掌根可与球/下段重叠，机械端面一致不证明无碰撞、接触可用或承重能力。六环低多边形圆角仍有可见棱面，不是最终美术表面；根截面为配方比例，不是从动物解剖或实体下段宽度拟合。`claw` 分支依赖本地上一 P2 `sample_neutral.blend` 与 `measurements.json` 作精确骨架对照；干净检出须先用默认 halfpad 命令重建该基线，当前隔离实现不承诺无基线运行。

用户仍需看爪掌外观并决定尺寸与位置/网格容差；诊断 -10/0/+10 不推断生物 ROM、性能或正式限位。主会话已复读对比图与实现，并复跑真实回归（逆修复退出 1、带修复退出 0）及提交闸门。未做四肢、URDF/USD、采用、物理、碰撞、完整动作周期或训练；本轮交付不完成 P2 接受或整项关闭，其他会话文件未触碰。
