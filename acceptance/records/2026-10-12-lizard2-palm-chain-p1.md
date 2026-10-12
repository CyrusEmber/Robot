# lizard2 无指/趾掌链 P1（2026-10-12）

## 适用范围

仅 `work/active/lizard2-body-drive-candidate.md` A2/P1。批准目标为每腿摆轴、外展、肘/膝、腕/踝四个 revolute，腕/踝子 link 是掌/跖末端；不建 foot/finger/toe 活动轴。本次只验证四角色骨树契约，不验证 URDF 关节类型。真实源 `rl_exp/blender/lizard_stance.blend` 仍为 haa/hfe/kfe/foot，旧 lizard2 导出器合成 hip。新几何不存在。

解释器：Blender 5.2.2 LTS（d13f752e3b9c）、`E:\IsaacLab\env_isaaclab\Scripts\python.exe`。父会话旧基线已通过 self-check 与 9 项 break-test；默认 Python 因 gymnasium 导入失败，不安装依赖。

## 验收条件

旧 shared/split 保持原语义；真实 exporter 拒绝缺骨、乱序、跨腿及多余 distal 子骨；四角色掌链小样通过只读消费；回归移除修复失败、原代码通过；资产树前后不变。只验契约，不验几何。

### 修改与实际消费者

- `rl_exp/tasks/joint_names.py`：新增独立 `palm` / `PALM_NAMING`，由原 split 每腿去掉最后词根派生；原 shared/split 五角色、公开符号和 PLANNED_ACTIVE=False 不变。自检覆盖腕/踝末端与禁止词根。
- `rl_exp/blender/scripts/generate_urdf.py`：现有 ROBOT_SPECS 声明 source/target naming 与骨角色；新增只读 `lizard2_palm_contract`。`validate_build_contract` 检查真实 bpy 骨树、精确腿内集合、父子顺序、跨腿绑定及末端无子骨，在 mesh 删除/写入前调用。旧 hip 合成角色的 source_bone 明确为 None。`--contract_check` 在写网格前退出；无此参数的 palm 目标直接拒绝，轴/几何未批准。`--memory_scene` 仅限只读检查。
- `rl_exp/blender/scripts/lizard2_stance_candidate.py`：原几何主入口不改算法/参数；增加 `--contract_self_check` 分支，真实 load/leg_roles 读取旧 blend，执行真实 exporter 的同一代码与检查。正例为 bpy 内存新建、无网格、任意坐标的四腿四轴 armature；永不保存，明确 CONTRACT_ONLY / geometry_proven=False。

共享文件已有 `_ASSET_DIR` 路径修复原样保留；joint_names 的另一会话 `naming_id` 新增也保留。其余会话修改未整理、暂存或提交。

## 结果

### 命令与实际结果

从仓根执行：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tasks\joint_names.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_leg_reachability.py --self-check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_leg_reachability.py --break-test
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --contract_self_check --regression_without_fix
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --contract_self_check
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\generate_urdf.py -- --robot lizard2_palm_contract
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\generate_urdf.py -- --robot lizard2_palm_contract --contract_check
 git diff --check
```

实际结果：名表 self-check 通过；旧 FK self-check（含 shared/split 同几何孪生）通过；`BREAK_TEST_OK (9 perturbation(s), every one caught)`。diff --check 通过。记录五节格式调整及本项 P1 路由去重后，`check_work_docs.py` 返回 `WORK_DOCS_OK (86 item file(s))`，active 总量 99956/100000 B；预算紧，不扩其它事项。

回归 fail-before：`--regression_without_fix` 仅在内存把 exporter 的 `binding = validate_build_contract(bones, SPEC)` 改成空 binding，不改磁盘源码、不 reset。真实旧源被错误接受，回归报 `AssertionError: old long source accepted under palm; distal silently discarded`，退出码 1。修复原代码同一检查通过，退出码 0；使用 venv Python subprocess.run 明确读回并断言两退出码。

Blender 真消费结果：旧 lizard/lizard2/lizard2_candidate 三种目标在旧源内存场景通过；新四角色掌链正例通过。10 个负例拒绝：旧长源配 palm、顺序错误、跨腿根父骨、缺腕末端、保留 foot、finger、toe、无腿前缀的 distal 子骨、前后肢词根混绑、source/target naming 不符。检查并非只按名字列表推定树；负例均到实际 exporter 骨树入口。

独立 exporter CLI：不带 contract_check 的 palm 目标退出码 1，报 `palm contract has no approved geometry; export blocked until P2/P3`；带 contract_check 读取真实旧 blend 后退出码 1，列出缺失新骨及多余旧骨。

## 证据引用

- 需求与后续路由：`work/active/lizard2-body-drive-candidate.md` A2/P1。
- 可复读检查：`rl_exp/blender/scripts/lizard2_stance_candidate.py:contract_self_check` 调用 `rl_exp/blender/scripts/generate_urdf.py:validate_build_contract`。
- 旧基线：`rl_exp/tools/verify/check_leg_reachability.py` self-check / break-test；命令与实际终端读数见上节。

## 未覆盖边界

### 无写入证明与限制

正例/负例全程只改进程内 bpy 数据。成功检查对 `rl_exp/blender`、`rl_exp/assets`、`rl_exp/versions` 下 314 个文件作前后 SHA-256 与路径集合比较，完全相同；覆盖源、旧 candidate blend/PNG、mesh、USD、冻结声明。Python audit hook 禁止写入 open 及 mkdir/remove/rename/rmdir，禁写 pycache。没有 URDF/mesh/USD/candidate blend/PNG 输出，没有训练、模型/pivot 改动或正式采用。Blender 原生 I/O 不受 Python audit hook 保证，故同时使用实际文件哈希；哈希只覆盖具名树，不宣称整个机器零写入。

正例仅证明四角色命名与实际骨树契约可被真实 Blender/export consumer 表达，不证明掌根位置、骨长、实体掌面、网格归属、碰撞、质量/惯量、轴或转动连接。源到目标不允许从长旧链删 foot 偷渡为新掌几何。旧导出完整网格写出未跑（明确禁止写资产），验证止于写前消费路径；其它 FK pose、runtime、report consumer 的新 palm 贯通未做。

### 判定与剩余

P1 窄范围完成：显式四角色独立绑定、旧基线保持、真实 Blender 正反例、fail-before/pass-after 与无写资产证据。P1 完成度 100%；不把此比例应用到整个事项或 E。

停止于 P2 前。新候选几何、掌根 pivot/mesh 连接与转动、容差/角度批准仍待 P2；隔离导出/USD/FK/runtime、动力学及集成审核均未执行。没有 review/close 整项，没有 pending_review；提交由主会话处理。

主会话复读同一 Blender 回归：移除消费端验证退出 1，恢复验证退出 0。新上下文只审 P1 代码范围，未发现阻断缺陷；不等于整项验收。旧导出入口现在也在写前核对骨树，这是有意的拒绝行为变化：当前旧源已验证可读，但含额外 helper 骨的未声明腿链会被拒，未承诺任意骨架兼容。

并行归属：P1 名表修改已随另一会话的 `2a9fd90` 入库；本轮保留该提交，不重写历史。用户批准连同两个 Blender 脚本中 P1 必需的 `_ASSET_DIR` 路径修复提交；其余在途文件不提交。
