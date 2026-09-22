# 2026-09-22 lizard2 家族落成（新骨骼 + 自包含基线配方）

## 适用范围

- 新家族 `lizard2`（唯一线 `main`，版本 `v1`）：资产 `versions/lizard2/lizard2.urdf` + `assets/lizard2/lizard2.usda`、
  参数 `versions/lizard2/main/main_params.yaml`、行代码 `rl_exp/tasks/lizard2_env_cfg.py` / `lizard2_recipe.py`、
  注册（`recipe.py` 的 `LINES`/`ELEMENTS`、`recipe_tasks.py`、`versions/recipes.json`、`tasks/__init__.py`、
  `agents/rsl_rl_ppo_cfg.py:Lizard2PPORunnerCfg`、`versions/lines.json`）。
- 覆盖：**从旧资产到可建 env 的全链路落成**，以及支撑它的三项机器证据（资产差异、锁隔离、离线套件）。
- 不覆盖：训练结果、obs 协议声明、`diff.json` 的人论证；本记录不含任何性能结论。

## 验收条件

- 资产差异必须是**逐位可证**的：只多 4 个 hip link/joint，其余 link 的 `<mass>`/惯量与 lizard 相同，网格逐字节相同。
- 新家族的一切声明必须**从本家族自身推出**（不引用参照家族）：差异声明由 `emit_diff_declaration.py` 计算。
- 旧家族的锁必须**零漂移**：`check_dr_parity.py --update-locks` 在 lizard 的 19 个版本上全部 `unchanged`。
- 注册必须能被机器自检：`import rl_exp.tasks` 通过；配方键与任务映射计数相等。

## 结果

| 项 | 实测 |
|---|---|
| 生成器（`--robot lizard2`） | `links=31 joints=30 total_mass=72.20kg`（26+4 关节；72.0+0.2） |
| 资产差异（lizard2 vs lizard，URDF 逐行） | 仅三类改动各 4 处：新增 hip joint/ link、`haa` 改挂 hip、`hfe` 轴 `0 0 1` → `-1 0 0`；**27 个共有 link 的质量 0 个变化** |
| 网格 | `versions/lizard2/meshes/**` 40 个 OBJ，与 lizard 的 **missing=0 different=0**（1.8 MB） |
| 生成器重构对旧资产 | `lizard` 重出 vs 已提交 URDF：差异**只有管线自己的两步改写**（`../meshes/` 前缀、`.stl`→`.obj`），内容一致 |
| 注册 | `IMPORT_OK`；`recipes declared: 40 | task mappings: 40`；`recipe lines discovered: 4`（含 `lizard2/main`）；`families checked: 2` |
| 差异声明（计算，非克隆） | 9 个元素组、64 条 env 路径、43 条 agent 叶子；base = `LocomotionVelocityRoughEnvCfg` + `['params_version']` |
| 锁 | `lizard2/main/cfg_lock.json`（85 KiB，2 条目 = train+play）；`lizard2/main/v1/asset_lock.json`；**lizard 19 个版本全部 unchanged** |
| 离线套件 | **45/47 通过**（`PARITY_OK`，`[2/47] freeze contracts` 由红转绿）；剩 2 项见"未覆盖边界" |
| 版本记录 | `FILEMAP.md` 两行、`versions/lizard2/FAMILY.md`（含版本史行）已落 |

复现命令（按顺序）：`blender --background --python rl_exp/blender/generate_urdf.py -- --robot lizard2` →
`convert_stl_to_obj.py --robot lizard2` → 装配进 `versions/lizard2/` → `convert_urdf.py --headless --robot lizard2` →
`declare_family.py --family lizard2 --apply` → `emit_diff_declaration.py`（由前者调用）→
`check_cfg_lock.py --update --line lizard2/main` → `check_dr_parity.py --update-locks`。

## 证据引用

- 记录：本文件；上位记录 = `acceptance/records/2026-09-21-lizard-leg-axis-kinematics.md`（为什么换代的测量依据）。
- 工具：`rl_exp/blender/generate_urdf.py`、`rl_exp/tools/pipeline/{convert_stl_to_obj,convert_urdf,declare_family,emit_diff_declaration}.py`、
  `rl_exp/tools/verify/{check_dr_parity,check_cfg_lock,check_recipe_build}.py`。
- 事项：`work/active/lizard2-family-landing.md`（本记录服务的在办工作）。

## 未覆盖边界

- **离线套件剩 2 项红**，均为"契约待声明"：① `check_recipe_build` 的 `EXPECTED_DIFFS` 未给 `lizard2/main/v1` 钉计数；
  ② obs 协议声明缺 `Lizard2-Flat-v1` / `-Play-v1`（存在于 golden，未在声明中）。
- `diff.json` 的 64 条 env + 43 条 agent `why` 全是 TODO：hard B 只比路径，所以不红，但**论证未写**。
- `declare_family.py` 有三处欠账：`ref`/`diff_json`/`_rename_element` 成死代码；其"零漂移自检"按正斜杠解析而输出是反斜杠
  ⇒ 打印 `0 checked`，**该网在事实上是空的**（判定碰巧正确）。
- 本记录不含性能结论；`v1` 在 PLAN 的验收节与 diff 论证写完前不算"可开训"；无 git tag（开训前必须）。
- 未跑仿真：obs 宽度 102（12+30×3）来自行代码公式推算与文档一致性，**尚无 live 观测确认**。
