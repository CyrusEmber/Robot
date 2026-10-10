---
id: pose-slider-view-wiped-by-redraw
title: pose_slider 的视角与缩放被重绘抹掉，中键是平移不是旋转
scope: rl_exp/tools/diagnose/pose_slider.py
status: done
landing: rl_exp/tools/diagnose/pose_slider.py
outcome: 关闭于 2026-10-10。修法、读数、两条破坏测试、复核（新上下文）读数与它留下的三条残留上限都归证据记录（含该记录的"独立审核"节）；复核判定可关闭。
close_when: ① env python 跑 `pose_slider.py --self-check` exit 0，且它断言"重绘后视角与缩放未被抹掉 + 键位 = 左/中旋转、无平移、右缩放"——把恢复逻辑删掉或把键位退回默认，该断言必须失败（两条破坏测试已跑，读数在证据记录里）；② 真窗口目视三条：中键拖动 ⇒ 模型与轴框/刻度标签整幅转动而不是平移；之后动任一滑块 ⇒ 视角不弹回；右键拖动缩放后动滑块 ⇒ 缩放不弹回；③ 界面上一行操作说明可见。①不成立，或②③任一目视不成立 ⇒ 退回 `in_progress`；三条都成立 ⇒ 关闭，复核由新上下文对照本项判据、落点与证据记录进行，不看执笔者的总结。
evidence: acceptance/records/2026-10-10-pose-slider-view-and-zoom.md
---

## 来源与范围

用户报的现象：`pose_slider` 转不动视角、坐标系不跟着转。成因是两处叠加，均在
`rl_exp/tools/diagnose/pose_slider.py`：`draw()` 每次重绘写死视角与三个 limits；mpl 3D 的中键默认是
平移，而 3D 平移改的是**数据轴范围**，于是模型在固定轴框内滑动。本项只改这一个文件，不碰
`rl_exp/tools/verify/check_leg_reachability.py` 的 FK 口径与读数。

## 当前状态

已关闭（2026-10-10，状态 `done`）。修法与读数归证据记录：`draw()` 不再写死视角与 limits，键位改左/中旋转、
去平移、右缩放，界面加一行说明，`--self-check` 增两组断言与 `view_margin=0` 硬化。复核判可关闭，
它留下的三条残留上限（工具栏平移仍可达、这组断言不在离线套件且无 mpl 时静默 exit 0、说明行宽度）
只记在证据记录的"未覆盖边界"与"独立审核"两节，本项不复述。

## 未覆盖边界

- 不把视角/缩放写进 pose JSON（未要求）。
- 不在原点另画 xyz 三轴：轴框与刻度即坐标系，随视角转动；要显式三轴另立事项。
- 不改 FK、滑块限位、`reset`/`save`/`--load` 的语义。
