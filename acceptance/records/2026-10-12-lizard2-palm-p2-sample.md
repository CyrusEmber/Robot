# Lizard2 无指/趾掌链 P2：两肢小样与原始测量

## 适用范围

2026-10-12，输入 `rl_exp/blender/lizard_stance.blend`；仅制作左前 lf 与左后 rl。用户批准肘/膝、腕/踝逐关节 **-10/0/+10° 诊断**，不批准限位、动作范围、物理验收或位置/网格容差。当前判定 **PROVISIONAL_SAMPLE_NOT_ACCEPTED**；施工和诊断交付完成，P2 外观/几何接受仍待用户，不进 P3。

未修改旧默认 `main()`、导出器、URDF/USD、网格导出树、配方或锁；未扩四肢、未训练、未提交/推送。P1 的内存拓扑样本不是本次真实几何通过依据。本次局部骨架混合新旧名，故不能作为四肢 palm 构建输入。

## 验收条件

本轮出口仅为两肢真实施工、原始测量、预览、修复前失败/修复后机械不变量通过、保护文件不变及路由。位置/网格/外观不作接受判定；用户确认前不扩四肢。以下施工与读数给用户比较，不倒推容差。

### 真实源数据与施工

同一源网格制作，不拿显示骨线代替实体：

- lf：`shoulder_swing → shoulder_abduct → elbow → wrist`；rl：`hip_swing → hip_abduct → knee → ankle`。摆轴/外展轴共根；末端腕/踝骨头位于下段末端，骨尾沿 body +X。旧 `foot` 骨删除；旧无实体圆柱的 `kfe→foot` 幽灵段删除；旧 kfe 关节球移至重摆后的下段末端，归腕/踝。
- 上下段原圆柱以真实两端 16 顶点 cap polygons 为依据拟合端点，保留原顶点/面和径向偏移，只作纵向拟合及中心线校正；不是新增圆柱，不取 object origin 或极值单顶点当端面中心。
- 掌实体来自原 pad **evaluated subdivision** 网格：在 body-X 顶点质心平面截断，保留向前半部并封口；封口顶点中心移到腕/踝，下游不留居中旧 pad。半掌比例只是源数据最小探测方案，未获外观批准；无整体缩放，但切割会改变边界，宽度并非严格不变。原 JSON 描述中的 midpoint 是用词错误，实际代码取顶点质心；当前脚本注记已纠正，旧读数未改写。
- 源含非零 pose basis，虽然网格世界位置对应 rest 读数；若沿用它，重建骨架与网格会错位。本入口只清零重建的 lf/rl basis，再更新依赖图、显式保世界变换绑定 rigid bone parent。右肢与躯干不清零。原 basis 保存在 JSON。

原始读数（m，方向/倾角 deg；不是通过判据）：

| 量 | lf | rl |
|---|---:|---:|
| 原上段骨长 | 0.501644329 | 0.501658609 |
| 原下段骨长 | 0.382121145 | 0.382120293 |
| 删除幽灵段长 | 0.130751970 | 0.130751916 |
| 原下段实体 distal cap 至 kfe 骨头间距 | 0.030823011 | 0.030822795 |
| 腕/踝相对原世界 kfe 的位移（含候选重摆） | 0.232235518 | 0.218810411 |
| 腕/踝相对重摆后的旧 kfe 位移 | 0 | 0 |
| 新上段 side tilt | -22.175991 | +22.175991 |
| 新下段 side tilt | +9.061594 | -9.061594 |
| 掌顶点 body-X 相对 pivot 最小值 | -0.000000775 | -0.000000358 |
| 掌顶点 body-X 相对 pivot 最大值 | 0.186562479 | 0.186562896 |
| neutral 真实掌根 cap 中心至骨头 | 0.000000273 | 0.000000267 |
| neutral 下段实体 distal cap 至腕/踝 | 0.000000246 | 0.000000169 |
| neutral 关节球 evaluated 顶点质心至腕/踝 | 0.000000260 | 0.000000169 |
| neutral 掌根 cap 平面残差 | 0.000001517 | 0.000004287 |

完整 old/new 世界坐标、掌界限、cap 法向/平面、各段真实端面、单关节各档读数见本地 `rl_exp/blender/lizard2_palm_p2_sample/measurements.json`。前后上段外展，上段前肢向后/后肢向前，下段相反；未变直立人腿。没有额外腕 pivot 人为偏移：其位置就是重摆后的旧 kfe，下段实体补齐到该处，掌根由旧 foot 端改到这里。

主会话复读 JSON 的真实边界差：lf/rl 的 X 长度分别减少 0.186564207/0.186564326 m，Y 宽度分别减少 0.000088364/0.000088394 m，Z 厚度差均为 0 m。切割不是严格保宽操作；这些只是读数，不是容差或外观通过。复读口径为每轴 `sample palm_world_bounds_m` 幅宽减 `native_pad_bounds_m` 幅宽；掌形比例与前向长度由用户另判。

## 结果

Blender 5.2.2 LTS（d13f752e3b9c）；以下均仓根 cmd 命令。生成必须新目录，已有目录拒绝覆盖；复读可用新 `lizard2_palm_p2_sample_<label>` 目录。

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --output_dir rl_exp\blender\lizard2_palm_p2_sample --diagnostic_angles=-10,0,10
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --output_dir rl_exp\blender\lizard2_palm_p2_sample --diagnostic_angles=-10,0,10 --check_only --regression_without_fix
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --output_dir rl_exp\blender\lizard2_palm_p2_sample --diagnostic_angles=-10,0,10 --check_only
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --contract_self_check
```

实际命令经 `E:\IsaacLab\env_isaaclab\Scripts\python.exe -B -c` 的标准库 subprocess 包装捕获 stdout/stderr 和退出码，日志留本地目录。生成退出 **0**，6 PNG + neutral blend + JSON；without-fix **1**，with-fix **0**，P1 **0**。去修复在真实小样内存中撤销掌根非居中放置，得到根残差 **0.093281090 m**、前后居中范围约 ±0.093281 m，检查真实封口失败；工作树不回滚。

12 档（2 腿 × 2 关节 × 3 角度）使用真实 pose、depsgraph evaluated 顶点，对比独立 mathutils 世界刚体绕点变换；最大顶点运动残差 **3.674277069e-7 m**，最大掌根中心残差 **4.842304232e-7 m**，最大下段 distal cap 残差 **2.682209015e-7 m**。下段端面至掌根平面距离也逐档报告。机械自检只断言结构、封口构造与 float32 绑定算术；`64×2^-23×坐标幅值` 是数值舍入检查预算，**不是用户几何容差**，旧 `TOL` 不被用作 P2 接受判据。

额外真实小样负例全部拒绝：错 mesh parent、缺下段实体、stale parent inverse、retained rl_toe；另一个转动专属负例冻结掌世界矩阵，在 +10° 下产生 **0.036204489 m** 顶点运动偏差，独立运动检查检出。P1 保持旧消费者 3 / 正例 1 / 负例 10，只读哈希 334 文件。

P2 保存/渲染前后保护 **465 文件**，JSON 存完整 SHA256 对照；右肢 evaluated 顶点变化 **0 m**，其它骨头/head/tail/rest matrix 相同。

- source SHA256：`ede254ae904d5ffcb909b55ae134714441d1f0c721b85660531d4b675ebc9010`
- adopted candidate SHA256：`0a503c7069d665779392f7f8997c3839e807def9787df97cd0d1b2eb4cf41deb`

脚本 `compile(..., 'exec')` 真编译成功，实际 Blender 执行成功。没有新依赖、新机器闸门或 P3 导出改动。

## 证据引用

共同目录 `rl_exp/blender/lizard2_palm_p2_sample/`（仅本地，`.git/info/exclude` 加精确路径，不改仓库 `.gitignore`）：

- `sample_neutral.blend`：源场景、仅 lf/rl 改造，rf/rr 旧链保留；场景/armature 元数据明确两肢小样、未接受、不能整机 palm 导出。
- `measurements.json`：全原始测量、源 pose basis、负例、保护哈希。
- `lf_side.png`、`lf_oblique.png`、`rl_side.png`、`rl_oblique.png`：左 source / 右 P2，同尺度真实网格比较，含旧幽灵段、新骨线与真实 pivot 标签。
- `lf_turns.png`、`rl_turns.png`：neutral 实体 + 独立单关节 ±10° evaluated 掌根环/掌尖叠加；黄/粉 = 肘膝 -/+，蓝/紫 = 腕踝 -/+。
- `run.log`、`p2_without_fix.log`、`p2_with_fix.log`、`p1_with_fix.log`：真运行输出。成功结果不等于外观/位置/物理验收。

已目视读 lf side、rl oblique、lf turns：真实旧 pad 在骨根中央下方，与新半掌掌根/朝前骨线区别可见，标签可读。为了透过不透明网格显示，诊断线/标签向相机平移；该偏移是显示层，绝不是测量坐标。所有测量无显示偏移。诊断几何独立 `P2_DIAGNOSTICS_NOT_EXPORT_OR_COLLISION` collection，neutral blend 在渲染前保存，不混入骨架/实体。

## 未覆盖边界

最大限制：新几何未提供，当前是**原 pad 向前半部封口**的小样，不是最终美术掌形；圆柱完整端面与关节球存在实体重叠，未做布尔合并，中心/端面残差小不证明无表面穿透、关节间隙或承重可用。源 pad 宽大且根截面朝 +X，前后原厚度不完全一致；用户需看 preview 决定长度/宽度/根截面是否可用。不得拿这次极小刚体残差宣布几何接受。

未验：用户外观接受、位置/网格容差批准、全周期/限位/碰撞、动力学/承重、镜像四肢、URDF/USD/FK 消费者。主会话已复读 JSON、前后肢比较图及只读回归（去修复退出 1、带修复退出 0），新上下文代码复核未见阻断缺陷；已纠正“严格保宽”的未实测说法，机械算术预算不作为位置验收。P2 **未接受**，整项不置 pending_review/关闭；等用户外观意见及容差批准，调整小样后再考虑四肢，禁止直接进 P3。
