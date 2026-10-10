# pose_slider 的视角 / 缩放 / 键位（2026-10-10）

## 适用范围

`rl_exp/tools/diagnose/pose_slider.py` 的交互层：视角（`elev`/`azim`/`roll`）与缩放（三条数据轴 limits）
跨重绘是否保留、三个鼠标键位的分工、界面上那一行操作说明。不覆盖该工具的 FK 口径、滑块限位语义、
`reset`/`save`/`--load` 的数据格式。

键位分工（左键与中键旋转、取消平移、右键缩放）与"说明放界面上""坐标系要跟着转"来自用户 2026-10-10
的口头拍板，不是本次实现方的选择。

## 验收条件

- ① 复读命令 exit 0，且输出里同时有"重绘后视角与缩放未被抹掉"与"键位 = 左/中旋转、无平移、右缩放"两条读数；
  把恢复逻辑删掉、或把键位退回 mpl 默认，该断言必须失败。
- ② 真窗口目视三条：中键拖动 ⇒ 模型与轴框/刻度标签**整幅**转动而不是平移；随后动任一滑块 ⇒ 视角不弹回；
  右键拖动缩放后动滑块 ⇒ 缩放不弹回。
- ③ 界面上一行操作说明可见。

## 结果

成因（matplotlib 3.10.8 实测，非推断）：

- `Axes3D.clear()` 保住 `elev`/`azim`/`roll` 与三个键位列表，**只**把 data limits 打回 `(0, 1) + margin`。
  实测：`view_init(33, 7)` + `set_xlim(-0.45, 0.45)` ⇒ `clear()` 后角度原样、limits 变 `(-1.031, 1.031)`。
- 3D 的"平移"（中键默认 `pan_btn=2`）改的正是 data limits（`Axes3D.drag_pan` 末尾三句 `set_*lim3d`）⇒
  模型在固定轴框里滑动，而轴框与刻度就是这里的坐标系，所以看起来"坐标系不转"。
- 旧 `draw()` 每一帧写死 `view_init(18, -62)` 与三行常量 limits ⇒ 任何一次重绘（动滑块、`reset`、`save`）
  把这二者一并清掉。

改后读数——

复读命令：`<ROOT>\env_isaaclab\Scripts\python.exe rl_exp\tools\diagnose\pose_slider.py --self-check`

```
[SELF-CHECK] a redraw hands the view back: 33/7 deg, x in (-0.45, 0.45); buttons rotate=[1, 2] pan=[] zoom=[3]
```

破坏测试两条，均在本次变更里跑过（脚本是 `--self-check` 自己，非一次性脚本）：

- 注释掉 `draw()` 尾部的 `apply_view(ax, held)` ⇒
  `AssertionError: {'elev': 33.0, 'azim': 7.0, 'roll': 0, 'xlim': (np.float64(-1.03125), np.float64(1.03125)), ...}`
  —— 角度仍在 ⇒ 旧病出在自己写死的 `view_init`；limits 被打回 ⇒ 缩放确实靠恢复那一句。
- 把 `mouse_init(...)` 退回默认 ⇒ `AssertionError: ([1], [2], [3])`，即中键又是平移。

真窗口目视（验收条件②③）：**三条均记为通过**，读到 2026-10-10 —— 读数来自用户本人在真窗口里操作
后的一句"可以"，未逐条留独立记录，故本行是"用户确认"而不是"机器复读"。

真窗口启动一条（自动跑，读数有限）：`<ROOT>\env_isaaclab\Scripts\python.exe
rl_exp\tools\diagnose\pose_slider.py` 起图、窗口关闭后 **exit 0**；只证明 TkAgg 路径能建图、
`mouse_init` 与说明行不报错、`draw()` 在真后端上跑通，**不证明**视觉上整幅在转。

## 证据引用

- 工具：`rl_exp/tools/diagnose/pose_slider.py`（`VIEW` / `view_state` / `apply_view` / `build` 里的
  `mouse_init` 与说明行 / `view_self_check`）。
- 工具自带断言：同上文件的 `view_self_check`，经 `--self-check` 调用，`main` 里 `--self-check` 分支进入。
- 事项：`work/closed/2026/pose-slider-view-wiped-by-redraw.md`（关闭之日移入，本记录与它同一次变更落地）。

## 未覆盖边界

- 验收条件②③的真窗口读数只有用户本人口头确认一句，未逐条留独立读数；"视觉上整幅在转"不来自机器判据。
- 滚轮缩放、触控板手势未测（mpl 默认不绑滚轮）。
- 视角/缩放不进 pose JSON（未要求）；不在原点另画 xyz 三轴（轴框本身即坐标系）。
- `--load` 载入后的首帧等于这里的首次 `draw()`（首帧用 `VIEW` 缺省），未另测。

复核（见下节）留下的三条上限，都不是未完成动作而是已知边界：

1. **工具栏的平移仍在**：`mouse_init(pan_btn=[])` 只让鼠标键不动到平移分支；导航工具栏的平移模式直接调
   `ax.drag_pan`（`backend_bases.py` 的 `press_pan`），绕过 `_pan_btn` ⇒ 从工具栏点一下平移，模型仍能在
   固定轴框里滑。本记录只宣称"鼠标左/中/右键分工"，不宣称"该工具不可能平移"。
2. **这组断言不在离线套件里**：`rl_exp/tools/verify/offline_suite.py` 只跑 `check_leg_reachability.py
   --self-check`，本工具的断言只有人手动跑 `--self-check` 才发现回归；且无 matplotlib 时该检查打印"未跑"
   并以 **exit 0** 结束 ⇒ 只看退出码的 CI 会把"跳过"读成"通过"。
3. **说明行的宽度**：`fig.text` 那行实测宽约 1188 px，只在画布宽 ≥ 约 16 in（默认 `figsize=(16, 10)` @100 dpi）
   时不溢出；窗口更窄时右段会被裁掉。

## 独立审核

2026-10-10，由**新上下文**（无执笔会话历史的子 agent，非执笔人）按 `close_when`、落点与本记录复核，
自跑读数如下：

- 复读 `--self-check`：exit 0（它先用链式 `%ERRORLEVEL%` 读到 0、判定该读法在解析期展开会撒谎，改用
  `cmd /v:on` 重取），输出同时含 `33/7 deg, x in (-0.45, 0.45)` 与 `buttons rotate=[1, 2] pan=[] zoom=[3]`；
  无 matplotlib 路径也跑了一条（自造 import 失败的 shim）⇒ exit 0 + "未跑"。
- 自做两条破坏测试（副本存 `%TEMP%`，改完按副本还原）：`mouse_init()` 退回默认 ⇒ exit 1、
  `AssertionError: ([1], [2], [3])`；`apply_view(ax, held)` 换成 `pass` ⇒ exit 1、`xlim (-1.03125, 1.03125)`。
  它记下一条比本文更细的读数：**该破坏下角度仍是 33/7** ⇒ 组一的角度半条只挡"重新写死 `view_init`"，
  真正咬住恢复逻辑的是 limits 半条。
- 键位派发另用无界面事件注入补同向读数：键 2 改角度不改 limits（不是平移）、键 3 只改 limits，
  随后重绘并经真实 Agg 绘制，二者均不变。（该注入脚本是复核方的一次性脚本，未入仓，按"一次性脚本不留仓根"
  处理 ⇒ **不可由仓内复读**。）
- 说明行与 25 个 axes 的渲染包围盒相交面积 0.0（1600×1000 画布）。
- 判定 **可关闭**；最大弱点是"这组断言钉的是坐标轴**状态**，不是派发路径，也不是视觉声明，且它自己不在
  离线套件里"。据其复核新增一条硬化与一条断言：`apply_view` 传 `view_margin=0`（`axes3d.automargin=True`
  时每次 set 会加 1/48 边距，实测三次重绘 xlim `0.48828 → 0.50863 → 0.52982`，每次外扩 4.17 %；当前该
  rcParam 为 False，故该关键字今天零代价），`view_self_check` 里加一条把该 rcParam 打开后重绘再断言的读数。

本节的读数由复核方取得，执笔人只做转录；其中"真窗口三条"仍只有用户一句确认。
