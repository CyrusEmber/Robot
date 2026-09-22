---
id: video-matrix-gears
title: 录像矩阵：速度挡位 × 地形挡位，任意组合，跟随相机
scope: ablation_harness/video_matrix.py, rl_exp/tools/verify/test_terrain_geometry.py, ablation_harness/suites.py
status: done
depends_on: ablation_harness/eval.py
landing: ablation_harness/video_matrix.py, rl_exp/tools/verify/test_terrain_geometry.py
evidence: acceptance/records/2026-09-22-video-matrix-gears.md
outcome: 落地为 `ablation_harness/video_matrix.py`（一台相机，不是判官）：`--speeds` × `--terrains` 任意组合，默认最高速 × 平地；地形挡位直接复用套件命名列（`plane` 走配方自己的地，其余取单列板，不改冻结定义）；命令每步注入并先冻 term，否则框架会把它改回去。真跑过了默认格与 `rough_b` 格，并用逐帧色块证明相机真跟随（整段 86k–144k px 稳定，而不是固定机位那次 43k→2.8k 单调缩小）。两处真 bug 当场修掉并留证：位移在末步 auto-reset 之后读会得到 0.0（改为逐步取峰值 + 另记净位移/复位）；Kit 录像机只在第一帧摆一次相机、不自己跟随（改为每步推 `/OmniverseKit_Persp`，`--no-follow` 保留固定机位）。断言折进 `test_terrain_geometry.py`（已付过 `suites` 的 import）：独立 check 会把离线套件顶过棘轮 47，按 `OFFLINE_CHECKS.md` 折而不是抬上限。边界见记录：地形只上过 `rough_b`、速度只上过 3.0、只有 Kit 后端。
---

## 问题与本次范围

要看的不是一条判分，是**一段**：同一策略在不同速度、不同地面上各自走成什么样。冻结协议回答不了这个——
它判一条固定窗口、固定地面，而且判官明确拒绝与录像混表。

所以本项只加一台**相机**：不产 verdict、不写 `results/<协议>/`；命令可以落在配方命令区间之外
（那种格子记 `in_recipe_box: false` 以示不在分布内），而不是被当成证据。

## 当前状态

已关闭（done）。工具、闸门、默认值、跟随相机都在位并真跑留证，结论与边界见
`acceptance/records/2026-09-22-video-matrix-gears.md`；未覆盖的挡位组合（其余八列地形、低挡速度、
多 env、Newton 后端）在该记录的"未覆盖边界"里，需要时另立事项。

## 未覆盖边界

- 相机跟随只在 Kit 后端验过；`--no-follow` 的固定机位语义实现了但未单独留证。
- 套件板 16 m 的尺度保护不存在：长片后段可能已出受考区，选多长由 `--seconds` 的使用者负责。
- 录像里的位移/均速只作"这段片子是否靠谱"的自查，不得引用进验收表。
