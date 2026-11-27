---
name: isaaclab-asset-pipeline
description: >
  处理 Isaac Lab 机器人训练资产：URDF→USD 转换、mesh/关节/碰撞排障。
  当用户提到"URDF 转 USD"、"转换资产"、"convert_urdf"、"重转/重新生成资产"、
  "改了 urdf/模型没更新"、"资产不生效"、"mesh 不见/丢几何/穿地坠落"、"关节对不上/关节名后缀"、
  "站姿不对/摆姿态/默认姿态"、"STL/OBJ 转换"、"接触抖振/自碰撞"、"换机器人/新机器人资产"、"资产换代"等需求时，
  务必使用此 skill。旧的 Blender 站姿管线（`build_rig`/`fix_bones`/`generate_urdf`）已随旧机体退网，
  只作存档指针。任务创建/课程/DR 用 isaaclab-task-creator，评测用 isaaclab-eval-harness。
---

# IsaacLab Asset Pipeline（资产管线）

资产链路为 Blender 站姿 → URDF → USD → 实验机体绑定。当前项目的机体、候选转换和验证入口见仓根 `README.md`。

## 核心规则

- **改了 URDF 后必须重跑 convert**，env 引用的 USD 才更新
  （`force_usd_conversion` 只管重转、不管触发）
- **在隔离候选目录转换**，为输出 USD 与导入产物使用新路径；资产验证后再采用。
- **换代或更新资产后同步更新机体模块 `robots/<body.py>`**（资产路径、默认 PD、动作关节与身体部位）
- `UrdfConverterCfg` 要点新机器人照抄，每条都有踩坑理由，别乱改

## 转换配置

`UrdfConverterCfg` 要点：

- PD 增益与动作映射在现役机体模块 `robots/<body.py>` 统一定义
- `merge_fixed_joints=False`：保留脚部独立 body，接触奖励依赖它们
- `fix_base=False`；`self_collision=True`
- `run_asset_transformer=False` / `run_multi_physics_conversion=False`：分层资产把物理放
  deferred payload，spawn 不加载 → articulation 塌成单刚体
- 转完自动 `flatten_usd()`：3.0 importer 把 link 嵌套进 base body，破坏接触传感器
  body 匹配，必须拍平回 2.x 布局
- 显式 `usd_file_name="<robot>/<robot>.usda"`：缺省时旧目录占坑会被静默改名
  `<robot>_1/`，导致引用路径错位

## 资产层 vs 环境层

PD 增益虽内嵌 USD，机体模块的 `make_robot_cfg()` actuator 配置会覆盖它 ⇒ **调 PD 直接改 `robots/<body.py>` 即生效，不用重转
USD**。PD 初值随质量量级重估，抄旧机器人数值必炸。

## 转换后验证链

| 步骤 | 方法 |
|---|---|
| 资产结构 | 核对活动关节、固定末端、USD 碰撞几何及可解析的依赖。 |
| 配置绑定 | 对照机体模块与实验实际配置的关节、动作组和默认姿态。 |
| 运行时接口 | 用正式探针实测 articulation、动作顺序、观测宽度、首步与 reset。 |
| 训评接线 | 用仿真冒烟验证 checkpoint 加载和训评接口。 |
| 物理复核 | 按资产变更选择接触受力、站姿对称或穿模工况，保留对应读数。 |

先检查候选资产和配置，再验证正式资产在仿真中的行为。历史受力和站姿流程按对应版本的源码及证据复跑。

## 核心坑（症状 → 根因）

| 症状 | 根因与修法 |
|---|---|
| 穿地坠落、usda 仅 ~60KB、`faceVertexIndices`=0 | **mesh 相对路径坑（静默丢几何）**：importer 按 URDF 所在目录解析相对路径，路径错不报错只丢几何 ⇒ URDF 里写 `meshes/...`（不是 `../meshes/...`） |
| 正则失配 `Not all regular expressions are matched!` | **3.0 importer 给关节名加 `_joint` 后缀**（body 名不加）⇒ 关节正则带后缀、body 正则不带 |
| 接触抖振（脚力 ±kN 交替） | 关自碰撞：`enabled_self_collisions=False` + `solver_position_iteration_count=8` |
| 资产改了没生效 | 检查是否重新转换、USD 是否另存到 `_1/`，以及机体模块实际绑定的 USD。 |
| 训练直接塌倒 | `run_asset_transformer` 被开了（单刚体），或 `merge_fixed_joints=True` |
| 站姿左右不对称 / 腿折向天上 | 手算镜像 rpy 必翻车 ⇒ 走 Blender 管线 |

## 改站姿

旧 Blender 站姿管线（`build_rig` / `fix_bones` / `generate_urdf`）随旧机体一起退网：脚本与
`rl_exp/lizard_urdf/` 只在 `archive/pre-refactor` tag 与 `rl_exp/out/archive/pre-refactor/` 里。
现役圆足的唯一导出入口是 `blender/scripts/lizard2_round_feet_export.py`（上游 .blend 与
`skeleton02/build.json` 逐个 SHA 绑定，缺件直接报错）。要换机体就照它改写，不手算姿态。
