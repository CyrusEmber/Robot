# 录像矩阵（速度挡位 × 地形挡位）落地与跟随相机

## 适用范围

覆盖 `ablation_harness/video_matrix.py` 这一个新工具：挡位解析、单列套件地形装配、命令注入、
Kit 录像与**跟随相机**。断言折进 `rl_exp/tools/verify/test_terrain_geometry.py` —— 它已经付过
`suites` 那笔 import，合同本就含 `ablation_harness/suites.py`。

**不含**：任何判分。本工具不产 verdict、不写 `results/<协议>/`，与 `baseline_flat_v3`（及其后继）
判官无关；姿态/接触/脚 duty 等口径仍归评测台。

## 验收条件

（与 `work/closed/2026/video-matrix-gears.md` 的 `close_when` 同一套）

1. 一次真跑：帧数 == `seconds / step_dt`，且位移落在"命令 × 时长"的合理区间 ⇒ 工具可用。
2. 地形挡位**必须上过真机**：离线断言只证明配置被改对，不证明单列板能装配起来。
3. 冻结套件定义不得被改写（取一挡是取副本，不是就地改冻结对象）。
4. 相机必须真跟随：机器人出画或一路缩小 ⇒ 不满足（这正是本项要解决的那条）。
5. 模块顶层不得引入重依赖（P003：AppLauncher 之前的重 import 会毒掉 Kit 的 USD 栈）。

## 结果

**离线**：录像矩阵的断言（速度/地形挡位解析与拒绝、九列套件列都能当选、单列不污染冻结套件、区间内外
判定、矩阵序、跟随位姿、模块顶层不得绑定重模块）折进 `test_terrain_geometry.py`，该闸门 **6 passed**。
过程留一笔：我先另立了独立 check，全量套件因此顶到 48 > 棘轮 47（`OFFLINE_SUITE_COST_REGRESSION`）——
按 `OFFLINE_CHECKS.md` 的规矩折进已经付过同一笔 import 的闸门，而不是抬高上限；子进程那条断言也改成
进程内检查（重模块一旦被顶层导入就会绑在该模块的命名空间里），故 `SPAWN_ALLOWED` 不需要申报。

**真跑 A（默认格 3.0 m/s × plane，6 s，`model_9999.pt`）**：300/300 帧；峰值前向 16.658 m
⇒ 2.776 m/s；`resets 1 @ 6.0 s`（片末超时）、净位移 0.0（复位后原点）。逐帧核：色块 86k–144k px
**全程稳定**、质心 x≈600–645 ⇒ 相机跟随成立。

**真跑 B（3.0 m/s × plane / rough_b，各 3 s）**：各 150 帧；plane 峰值 7.65 m（2.55 m/s，含起步加速），
rough_b 峰值 5.10 m（1.70 m/s，8–16 cm 粗地形降速），`terrain_size_m 16.0` 证明单列套件板真装配上机。

**对照（修跟随之前，固定机位）**：同一 checkpoint 的 6 s 片里色块 43k px **单调缩到 2.8k px**——
机器人从中间走到远端出画。这就是"看着不动/看不到它"的机制，也是本项改成追车镜头的理由。

**修掉的两个真 bug**：

1. 位移读数在最后一步之后读，而片长 == episode 长度 ⇒ 末步超时 auto-reset，manifest 写成
   `forward_displacement_m: 0.0`。改为逐步取峰值，另记 `net_forward_m` / `resets` / `first_reset_s`。
2. 首版机位沿行进方向固定，机器人只会在画面里缩小远走（见上）。改为 `--follow`：每步按"机器人根位姿
   + 偏移（在出生朝向系里旋转）"推 `/OmniverseKit_Persp`——框架的 Kit 录像机只在**第一帧**摆一次相机
   （`isaacsim_kit_perspective_video.py:34-44`），不自己跟随。

**结论**：五条验收条件全部满足 ⇒ 按 `close_when` 关闭 `video-matrix-gears`。

## 证据引用

| 证据 | 位置 |
|---|---|
| 默认格 manifest + 片 | `ablation_harness/videos/2026-09-22-v2-follow/matrix.json`、`3mps_plane.mp4` |
| 挡位两格 manifest + 片 | `ablation_harness/videos/2026-09-22-v2-gears/matrix.json`、`3mps_plane.mp4`、`3mps_rough_b.mp4` |
| 修跟随之前的对照片 | `ablation_harness/videos/2026-09-22-v2-default/3mps_plane.mp4` |
| 闸门 | `rl_exp/tools/verify/test_terrain_geometry.py` 的 `test_video_matrix_gears_resolve_against_the_suite`（6 passed）；登记见 `rl_exp/tools/verify/offline_suite.py` 的 terrain geometry 一行 |
| 策略 | `E:\IsaacLab\logs\rsl_rl\lizard_baseline_v2\2026-09-21_17-41-12\model_9999.pt`，sha256 `3aa910f7cd3d1ddfbfeef00a00e01842d052d4ef6388104c7121ad4ecdbbc7c7` |

`videos/` 不入库（`.gitignore`：与 `diagnose/out/` 同待遇），逐帧核对用的是临时脚本：以末 10% 帧的
中位数为背景，取 `max|Δ| > 25` 的色块像素数与质心。

## 未覆盖边界

- **地形挡位只上过 `rough_b` 一列**：其余八列（斜坡、台阶、缺口、`rough_a`）只有离线断言。
- **速度只有 3.0 m/s 上过真机**：低挡、多挡矩阵、`--num_envs > 1` 均未真跑。
- **相机跟随只在 Kit 后端验过**（headless + cameras）：Newton/rerun 后端未验；`--no-follow` 的固定机位
  语义已实现但未单独留证。
- **套件板只有 16 m**：3 m/s 下约两秒就穿过受考区，长片的后半段是平地（甚至出板），这个尺度由
  `--seconds` 决定，工具不加保护。
- 位移/均速是**自查数**，不得引用进任何验收表；录制不留任何判分。
