---
name: isaaclab-asset-pipeline
description: >
  在 E:\IsaacLab 中做机器人训练资产管线：URDF→USD 转换（convert_urdf.py）、
  Blender 站姿骨架管线（build_rig/fix_bones/generate_urdf）、mesh/关节/碰撞排障。
  当用户提到"URDF 转 USD"、"转换资产"、"convert_urdf"、"重转/重新生成资产"、
  "改了 urdf/模型没更新"、"资产不生效"、"mesh 不见/丢几何/穿地坠落"、"关节对不上/关节名后缀"、
  "站姿不对/摆姿态/默认姿态"、"Blender 骨架/骨骼/rig"、"fix_bones"、"generate_urdf"、
  "STL/OBJ 转换"、"接触抖振/自碰撞"、"换机器人/新机器人资产"、"资产换代"等需求时，
  务必使用此 skill。任务创建/课程/DR 用 isaaclab-task-creator，评测用 isaaclab-eval-harness。
---

# IsaacLab Asset Pipeline（资产管线）

机器人物理资产管线：Blender 站姿 SSOT → URDF（几何 SSOT）→ USD（训练用）。
方法论通用；**每机器人一个 `<robot>_exp\` 目录**（convert_urdf.py / blender\ /
meshes\ / 验证脚本都在里面，实例清单读该机器人的 FAMILY.md）。
本项目实例：lizard → `E:\IsaacLab\rl_exp\`。

**改了 URDF 或 PD 参数后必须重跑 convert**，env 引用的 USD 才更新（`force_usd_conversion`
只管重转不管触发）。**资产换代时同步冻结配方环境**（快照里抄了资产配置的）。

## convert_urdf 运行

```
<venv python> E:\IsaacLab\<robot>_exp\tools\pipeline\convert_urdf.py --headless
```

`UrdfConverterCfg` 要点（都有踩坑理由，新机器人照抄，别乱改）：

- PD 增益从 `<robot>_params.yaml` actuator 组读取——USD 内嵌 drive 与训练配置一致
- `merge_fixed_joints=False`：保留脚部独立 body，接触奖励依赖它们
- `fix_base=False`；`self_collision=True`
- `run_asset_transformer=False` / `run_multi_physics_conversion=False`：分层资产把物理放
  deferred payload，spawn 不加载 → articulation 塌成单刚体（训练直接趴倒）
- 转完自动 `flatten_usd()`：3.0 importer 把 link 嵌套进 base body（issue #5126），
  破坏接触传感器 body 匹配，必须拍平回 2.x 布局
- 显式 `usd_file_name="<robot>/<robot>.usda"`：缺省时旧目录占坑会被静默改名
  `<robot>_1/`，yaml 指向空。**转换前删旧 assets 目录 + `.asset_hash` + `config.yaml`**

## 转换后验证链（从 E:\IsaacLab 根目录，venv python）

| 步骤 | 方法 |
|---|---|
| 关节数 | `findstr /i "Revolute" assets\<robot>\<robot>.usda \| find /c /i "joint"` = yaml `joint_order` 长度（秒级） |
| 几何量 | usda 应为 MB 级、`faceVertexIndices`/`PhysicsCollisionAPI` 计数 > 0（丢几何见坑表） |
| 位置/受力 | exp 目录的 position_check 类脚本（z 轨迹 + 接触力 + NaN） |
| 关节对表 | exp 目录的 joint_check 类脚本（reset 后关节名/角度 vs joint_order） |
| 站姿对称 | exp 目录的 debug_pose 类脚本（每腿 pivot 世界坐标） |
| 肉眼终验 | GUI 观察脚本（lizard: `tools\verify\view_terrain.py --viz kit --task <任意 PLAY 任务>`）——开 Isaac Sim 窗口看站立/穿模/地形（改名自 view_lizard，已支持选地形） |

具体脚本名读该机器人 FAMILY.md。标准顺序：convert → 关节数 → position_check（数据）
→ view_terrain（肉眼）。

## 核心坑（症状 → 根因）

| 症状 | 根因与修法 |
|---|---|
| 机器人穿地坠落、usda 只有 ~60KB、`faceVertexIndices`=0 | **mesh 相对路径坑（静默丢几何）**：importer 按 URDF 所在目录解析相对路径，路径错不报错只丢几何。URDF 里写 `meshes/...`（不是 `../meshes/...`） |
| 关节正则失配 `Not all regular expressions are matched!` | **3.0 importer 给关节名加 `_joint` 后缀**（body 名不加）。所有关节正则带后缀、body 正则不带 |
| 接触抖振（脚力 ±kN 交替） | 关自碰撞：`enabled_self_collisions=False` + `solver_position_iteration_count=8`（lizard 实测 ±3kN → 数百 N） |
| 资产改了没生效 | 忘重跑 convert，或没删旧 assets 目录（被挤到 `_1/`） |
| 训练直接塌倒 | `run_asset_transformer` 被开了（单刚体），或 `merge_fixed_joints=True` |
| 站姿左右不对称/腿折向天上 | 手算镜像 rpy 必翻车——走 Blender 管线（见 references/blender_pipeline.md） |

## 资产层 vs 环境层

PD 增益虽内嵌 USD，但 env cfg actuator 配置会覆盖它——**调 PD 改 yaml 即生效，不用重转 USD**。
PD 初值跨体型要重估，随质量量级变（案例：14kg 机器人 50/3，72kg 用 600/30 起步），
抄旧机器人数值必炸。

## 改站姿

完整 Blender 流程（摆位 → fix_bones → generate_urdf → 转换 → 验证）是**实例参考**，
新机器人复制改造：见 `references/blender_pipeline.md`。
