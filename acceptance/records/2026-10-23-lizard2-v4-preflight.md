# lizard2 v4 训练前预检

## 适用范围

按用户“预检”，核正式 `Lizard2-Flat-v4` 的真实平地、小场景目视与默认并行规模短程运行，不启动学习器或训练。本轮不改冻结配方、资产、PD、限制、奖励、终止或目标速度。版本输入为 `lizard2-main-v4` → `9465f9f60dee2eed9b0ab310e40d0ba853fedb09`，基础树为 `95d3fa5d8cdea78502d46360dfb6dd9c63e49db9`；正式采用与接口边界见[配置记录](2026-10-23-lizard2-v4-configuration.md)。

复用原生 `resolve_task_config`、`launch_simulation` 和 gym 注册任务。旧 `view_terrain.py` 会移除关节 reset 并加入接触探针，故不据其判断正式配置；旧 `terrain_preflight.py` 只读 v11 地形表，本轮不调用。新增薄入口 `rl_exp/tools/diagnose/palm_preflight.py` 保留真实 reset、传感器和物理配置，没有诊断 target override、额外外力、速度参考、步态或抬腿动作。GUI 仅覆盖环境数和观察相机，seed=42；默认规模不覆盖环境数。

## 验收条件

- 原生构造器加载正式掌部资产与真实 plane 地形，动作/观测及命名对应实际集合；GUI 无明显丢网格、错误方向或装载错位。
- backend 为自由根、TGS/false，全部环境的逐关节 Kp/Kd、effort/speed 与正式参数逐值一致。
- 预算内每个控制步的 q/dq、根位置、接触力与 policy 为有限值，backend 速度参考恒零；保留实际 reset 计数，不将平衡或动作表现作为门槛。
- 报告完成并持久化，失败和中间制品不覆盖；退出码或普通启动横幅不能代替报告。

## 结果

**有限环境预检通过，可接续已批准训练。** 默认规模的场景构造与短程推进成立；不外推 PPO 训练内存、吞吐、长时稳定性或策略表现。

| 采集 | 环境数 | 控制步 / 物理步 | 实际状态 |
|---|---:|---:|---|
| gui01 | — | 0 / 0 | Hydra 收到已消费 CLI 参数，在 Kit 前停止；失败报告保留 |
| gui02 | 4 | 100 / 400 | 已运行并实际目视；原生 Kit 关闭中断脚本末尾保存，无结构化报告，不作数值通过 |
| scale01 | 4096 | 10 / 40 | 到达运行完成横幅；同上保存缺陷，无报告，不作数值通过 |
| gui03 | 4 | 100 / 400 | completed/closed=true，最终结构化报告通过；2 s 仿真 |
| scale02 | 4096 | 10 / 40 | completed/closed=true，最终结构化报告通过；0.2 s 仿真 |

步数按每次向量环境调用计，不乘环境数；初始化内部步不计。先修 CLI 交接，再将报告写入原生上下文退出前，避免 Kit 关闭回调提前结束解释器。末两次使用同一最终入口，源 SHA256 `56f03a701fd49ee30ab6e8a2c8e2c108f3c008329820b2043356b9d45acd9e71`。提交版随后仅补齐仓库要求的标准版权头；与两份捕获源逐 AST 比较相同（不计行号），没有重跑物理。提交版 SHA256 `577b18593f75f1f966e618be97dec19b37da5f3564f7e5ea52037a89b9babcca`。修补只涉及诊断参数和保存，不变更正式配置。拒绝覆盖既有输出、拒绝零步数均在建场前返回 2，后者不创建目录。

两次正式任务均为 plane、30 动作、102 维 policy、30 joints /31 bodies；接触 dt=0.005 s、history=4、decimation=4、lazy=false。每个环境的四类驱动数组均与 YAML 相同；后端读回 TGS、force timing=false、fixed_base=false。每一步的有限值检查与零速度参考检查均通过，reset 计数均为 0；第一控制步分别全部环境已有非零接触。报告保留初始化、首步和末步摘要，未保留全部状态轨迹。

gui03 末步 env0 根高约 0.56882 m、最大绝对 q 约 0.12215 rad；scale02 末步约 0.56979 m、最大绝对 q 约 0.11914 rad。这是自由根零动作受重力落定读数，**不据此判 0.002 rad 精度通过**，也不改变既有小幅诊断判决。记录的 dq 为当前后端观测，不消除已知 TGS/false 速度偏差。

GUI 由 Computer Use 实际查看：四个机体位于网格平面上，头、躯干、四肢与掌部可见，未见明显丢网格、方向翻转或装载飞散。截图来自 gui02 的末段暂停观察，保存在该目录 `visual.jpg`；gui02/gui03 的构造配置快照同 SHA256 `234b7eb86ac51a923fe9ba2006c9448c8a3e6586597a4aff635ddc3c908a57a8`。截图仅支持目视陈述，不能替代 gui03 的数值报告或证明无碰撞/无穿透。

本次最终日志未见 OOM、碰撞栈溢出或容量超限报错。已知 disabled world FixedJoint 的 disjoint-transform 提示、heading 未启用提示及 GUI 命令箭头的 Fabric 提示保留；未通过改 solver/外力时序压掉警告。主机为 RTX 3060 Ti /8 GiB；Torch peak 不是 PhysX/Kit/整卡峰值，未用它宣称训练显存余量。

## 证据引用

本机输出位于 `rl_exp/out/lizard2_v4_preflight_<采集名>/`，各日志同前缀加 `.log`。不承诺这些本机工件全部入仓。最终报告与源快照应一起复读：

| 工件 | SHA256 |
|---|---|
| gui03/report.json | `756c6f618742371fd6f92140c7628e563b59b4a0e780081ba7556cd8bfbb0b06` |
| scale02/report.json | `b0c022a74330538dea6aee49f3e150918d8897226da7bcd14b889557991b9663` |
| gui02/visual.jpg | `6f139dbc846c9e15b184db72266e26b96b8527248b5b0570102ee556215aa42d` |

读已有报告不启动 Kit：用项目 Python 读 JSON，核 `completed`、`closed`、无 `error`、`source_sha256` 与同目录 source.py 一致、上述报告摘要及实际步数；首末摘要只按其存储范围解释。可重复运行入口为：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_preflight.py --out rl_exp/out/lizard2_v4_preflight_gui_replay --num_envs 4 --steps 100 --hold_seconds 20 --viz kit
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_preflight.py --out rl_exp/out/lizard2_v4_preflight_scale_replay --steps 10 --viz none
```

输出必须是不存在的新目录，不覆盖本次证据。正式启动仍使用 `rl_exp/tools/launch_recipe.py`，预算、seed 和从头初始化决定取 v4 PLAN 与已批接口方案；此工具不调用训练入口，不成为新增串行阶段或通用训练闸门。

完整离线套件 `37/37`、53.7 s 通过（`rl_exp/out/lizard2_v4_preflight_offline_suite.log`）。最终两报告的摘要、源快照、步数/维度、有限首末摘要与 GUI 配置身份离线复读通过（`lizard2_v4_preflight_replay.log`）；版权头补齐后补核 AST 等价，不把注释字节差当物理变更。提交前及正常提交钩子均通过（`lizard2_v4_preflight_precommit.log`、`lizard2_v4_preflight_commit_code.log`）。工具/FILEMAP 提交为 `565e7dca926a54856cf2de16f305defac7efbd28`；预检记录与事项指针另作同次文档提交。正式 v4 tag 不移动。

## 未覆盖边界

没有运行 PPO learner、rollout buffer、反向传播或 optimizer，未测训练峰值显存/速度，也没有新 run/checkpoint。GUI 不证明物理无穿透或接触分类正确，短程运行不证明持续平衡、0.002 rad 全域精度、速度/载荷包线、自然终止和所有 reset 组合。原动作/非零观测、接触子步和有限 reset 证据按配置记录范围复用，没有重做动态滑移/滚动标定、触边/限矩、对称复测、手工抬腿或行走。
