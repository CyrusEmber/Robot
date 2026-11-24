# Blender 站姿管线（改站姿时读这里）

> 脚本、路径和关节映射来自旧 Lizard。完整复跑使用 `archive/pre-refactor`。当前机器人按仓根 README 的资产与接口检查执行。

站姿 SSOT = Blender 文件（lizard: `<robot>_exp\blender\lizard_stance.blend`，WYSIWYG；
脚本内输入输出路径全部相对脚本自身，可移植）。
**不要手算关节 rpy/镜像符号**——左右手性推导极易翻车（实测：手算版两条腿折向天上）。
零位 = 站姿（joint rpy 全 0，姿态烘进几何），env 默认姿态就是自然站立。

## 管线脚本（`<REPO>\rl_exp\blender\`）

Steam Blender 运行：
`E:\SteamLibrary\steamapps\common\Blender\blender.exe --background --python <脚本>`

| 脚本 | 作用 |
|---|---|
| `build_rig.py` | 从素模建 26 关节骨架 + mesh 归属（一次性，历史存档） |
| `fix_bones.py` | **改站姿后必跑**：骨骼 head/tail 对齐新球心 mesh 位置（mesh 保 world 不动）。用户只摆 mesh 不动骨骼时 pivot 与 mesh 脱节，关节绕错点转 |
| `generate_urdf.py` | 读 `lizard_stance.blend` → URDF + STL（零位=站姿；AXIS_MAP 世界功能轴：haa=Y / hfe=Z / kfe=Y(±1.6) / foot=X；关节球剔除 collision） |

## 改站姿完整流程（7 步）

1. Blender 打开 `blender\lizard_stance.blend`，object/pose 模式摆腿位（大腿外展、小腿垂直、blade 平放）
2. `fix_bones.py` 对齐骨骼 → 另存（原位覆盖 lizard_stance.blend）
3. `generate_urdf.py` 重出 URDF+STL 到 `rl_exp\lizard_urdf\`
4. 从 `lizard_urdf\` 拷 `lizard.urdf` + `meshes\` 到 `rl_exp\`，跑
   `tools\pipeline\convert_stl_to_obj.py`（STL→OBJ 双保险 + URDF 引用改写 .obj）
5. 路径修正：URDF 里 `../meshes/` → `meshes/`（**必须**，mesh 路径坑见 SKILL.md）
6. 在独立候选目录转换 USD，核对 mesh 和碰撞体的加载结果。
7. 测量四腿 pivot 对称、站姿受力和基座高度，再在仿真中复核穿模与站姿。

## 旧 Lizard 站姿判定标准

- 四脚 force_z 合计 ≈ 总质量 × 9.8，单脚偏差 < 30%
- base z 轨迹收敛无震荡
- 四条腿同段 pivot 的 rel_z 一致（容差 mm 级）

## 历史坑备忘

- Blender 5.2 无 `bmesh.ops.append` → 用 `mesh.transform` + `bm.from_mesh` 追加
- STL 导出 operator 未启用 → 手写二进制 STL（struct.pack）
- 烘焙旋转只需改 rpy，origin xyz 桥接不变（fix_bones 的发现）
