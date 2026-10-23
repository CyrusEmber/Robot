# lizard2 隔离训练草案：真实动作、接触采样与 reset 核验

## 适用范围

用户要求继续实际环境中的动作映射、接触采样与完整 reset。对象是[训练接口方案](2026-10-23-lizard2-training-interface-plan.md)已构建的隔离草案，不改已训 v3、正式资产、配方注册或训练目标。全部关节速度目标仍为零；自由根、重力、当前 PD/caps、自碰撞与 TGS/`enable_external_forces_every_iteration=False` 保持。

执行入口为 `rl_exp/tools/diagnose/palm_training_interface.py`，通过注册任务构造器加载具名 manifest，2 env、dt=0.005 s、decimation=4。草案 SHA256 为 `a120b8907601852e5ca7bf1190f675d75ea7a8ae0fa79e970d887628ed7e8b19`；绑定 URDF/USD 与当前 B/C 承地输入不变。两环境的全部 PD/effort/speed 后端读回按逐列与承地报告精确比较；不只核膝肘。

大幅输入只调用真实 action manager 的 process，未 apply、write 或推进物理。真实小动作按动作列给不同的 ±0.0005…±0.015 rad 位置目标；随后零动作。不做增益、速度、限矩、精度、抬腿或行走性能测试。

## 验收条件

- 30 个真实动作逐名唯一覆盖，逐轴 scale/offset/clip 的实际处理结果及 backend 目标可复算；物理阶段速度目标为零，参考幅度不超过 0.015 rad。
- 真实 policy 七项、102 维由非零状态/动作与实际变换复算；宽度、同名列和全零不能单独证明映射。
- 在框架原 scene.update 后只读接触内部缓存，逐子步对照 native contact view；不由观察器额外刷新传感器。保留首步、历史移位、时间戳和非零接触。
- 脏关节/根状态、raw/prev action、接触历史和 episode 状态经完整及子集 reset 恢复；未点名 env 的对应数组不变。处理后/后端目标是否即时清除，与下一物理步实际目标分开判定。
- 用原终止条件核真实接触终止、自动 reset、终止前快照及紧接的零动作步；未触发的普通零动作轨迹不能冒称覆盖自动终止。

## 结果

[独立审核](2026-10-23-lizard2-interface-runtime-review.md)已接受此次有限隔离接口运行证据；审核直接复算原数组并核读取器修补前后，不替代 D/E 整体、正式 S5 或开训放行。

### 实际采集与复读

| 采集 | 完成情况 | 控制/物理步 | 作用 |
|---|---|---:|---|
| attempt01 | completed/closed；最终读取器通过 | 104 / 416 | 原姿态 100 步零动作窗口，以及小动作、完整/子集 reset；未自然终止 |
| attempt02 | **completed=false**，保留失败 | 2 / 8 | 倒置放置前因 keyword-only API 被误用为位置参数停止，不作通过 |
| attempt03 | completed/closed；中间采集 | 6 / 24 | 修正调用后原接触终止触发；尚未专门采紧接的下一零动作步 |
| attempt04 | completed/closed；最终读取器通过 | 7 / 28 | 补齐接触终止、自动 reset 及紧接零动作步，另核完整/子集 reset |

总计 4 次实际环境构建，119 控制步、476 物理步（每次 2 env；均不含初始化内部步），没有训练。入口早期语法检查失败发生在 AppLauncher 前，不算物理运行。attempt02 曾以进程码 0 结束，但报告明确未完成，读取器实际拒绝；最终入口捕获 app.close 的 SystemExit，不能用 CLI 退出码替代报告/数组验收。所有工件保留，不覆盖旧输出。

### 动作与观测

实际 manager 为两组 20/10 动作；逐名顺序继承草案，与实际 backend 关节列分开。四组双环境非零输入的实际处理结果等于逐轴 affine 后的硬限位 clip，探针新增物理步为零。每个真实物理步前，backend 位置目标按动作名重排后与期望一致；速度目标全部为零，最大参考绝对值 0.015 rad。没有把大幅裁剪探针送进物理。

两组最终数据的实际 policy 均为 102 维，七项逐值与关节 q/dq、默认值、原始动作、根速度/重力及命令缓冲和实际 term scale/clip 一致。存在非零 q/dq/action，不是仅检查宽度或零值。此项验证消费者/映射，不消除已知 TGS/false 速度观测偏差，也不批准新 observation 协议锚点。

### 接触与 reset

接触实际 update_period=0.005 s、history_length=4、lazy_sensor_update=False。native 路径与每环境传感器 body 顺序一致；逐物理子步的缓存力和 history 最新槽等于同帧 native force，后三槽正确移位，时间戳同步且 outdated=False。观察器读取内部已更新缓存，不调用额外刷新；非零接触和首次零动作子步均已覆盖。读数为 net normal force，含自碰撞可能性，不据此称地面承重/剪切力协议已通过。

根状态、关节 q/dq、manager raw/prev、逐 term raw（最终夹具）、episode 与接触历史按 reset 恢复；后端 q/dq 与读回状态一致。脏根平移与速度、非零关节及动作均为明确写入的状态夹具，不是动力学响应证据。attempt04 的 reset 前 prev_action 最大绝对值 0.09，接触历史有非零样本；完整/子集检查不空验。子集 reset env 0，env 1 的根/关节、动作、处理后和后端目标、接触历史及 episode 对照完全不变。

**即时目标缓存不清零。** 脏输入完整/子集 reset 返回时，processed 与 backend position target 仍可保留最大约 0.015 rad；raw/prev 已零。这是当前框架的实际语义，不能写作“全部缓存清零”。实际 env.step 先 process 新动作、apply/write，再推进物理；已采集的完整/子集 reset 后首个零动作步中，四个物理子步前的 backend 位置和速度目标均为零。未发现旧目标影响这些首步，因此本轮不改平台 reset 或增加清零补丁。若消费方在 reset 后绕过 env.step 直接推进 sim，此证据不为该调用方式担保。

普通姿态 2 s 零动作未触发终止，保留未覆盖。倒置夹具只改变 env 0 初态，以真实碰撞网格算得全部顶点初始最小离地约 0.005 m，env 1 保持原态；不施加外力、不替换/关闭/缩短终止。attempt04 第 4 个控制步，原接触终止返回 terminated=[True,False]、truncated=[False,False]，实际 `_reset_idx` 仅处理 env 0，保留终止前状态/history/policy 快照；随后紧接的零动作步直接走实际 env.step，目标覆盖、接触刷新和返回观测均复算一致。它证明原接触终止→自动 reset 链路，不称普通站姿自然翻倒、恢复或策略表现通过；原 timeout 到期链未另跑满。

独立复核指出早期读取器只验证数组、未强制自动 reset 后首零步时序。用真实 attempt03 复现：修补前返回数组 verified 但首零步覆盖为 False，修补后明确拒绝 `missing immediate first zero step after automatic reset`；原始数据不变。最终读取器还从每控制步末子步 history 按原 base/head 的 1 N 接触谓词重算全部 terminated，校验子步/控制步 phase 一致及夹具终止后紧接首零步。未追加物理或改变终止条件。

最终 attempt01 拒绝 6 项、attempt04 拒绝 7 项真实数据破坏：处理后列错序、非零速度目标、接触历史污染、reset raw 残留、policy 值污染、终止标记污染，以及夹具首零步 phase 污染。没有新增默认闸门、协议锚点或放宽物理判据。

## 证据引用

输出根为本机 `rl_exp/out/lizard2_interface_live_20261023/`，不承诺随仓分发。各报告含 source 和四个实际运行时类的源码快照/摘要，历史采集源码不以最终入口冒充。

| 工件 | SHA256 |
|---|---|
| attempt01/report.json | `159719d4624078b9dbe9173409214b9186542f221d576f002d45fcd42fc15511` |
| attempt02/report.json | `aae7061563490a5e347239e8e0da0d3b56c49ebe1bf331fe81a290fc725786f1` |
| attempt03/report.json | `77017974494010ab8dd70b9fd6fd7492e12a86f6ab9612f4571d92aa024c7c8a` |
| attempt04/report.json | `6dd0667982efb3b3105cc53783a362a913d2a01d934828fcae46bf1ddedcf1de` |
| attempt04/source.py | `e67a6b78be3d6e91c13b7451fcf1d7e37ca0ca3d8ce5ea952492e596e35c0c16` |
| audit01_final.json | `61cafa6061faed7e7f99cb9188a9721547b025996c2fcd55099b5aa886673b7c` |
| audit04_final.json | `fed874af825ae49ee4fab83173a1d165b5eb93688cfa87b1c3e206f41f49510f` |
| audit03_before.json | `ecf5593337432e0365af998c4552bf3578b340eaaaf28536d78f4212ddcd061f` |
| audit03_after.log | `6cbdf2554119d775c4a19768fc35b60794cda94c4dbb81973851823d1b968f99` |

最终离线读取器 SHA256 为 `c98c347e8cc3ae7fa66c00523191aae1ddfa85a0744fc4f032d72a63bf2945b2`，与采集快照的区别只在离线读取/破坏检查，原 collector 与物理记录未改；早期 audit01/audit04 JSON 留作过程，不作为最终出口。

同级采集日志在 `rl_exp/out/lizard2_interface_live_20261023_attempt01.log` 至 `attempt04.log`。从仓根的项目 Python 运行；采集必须用不存在的新目录，复读不启 Kit：

仓库完整离线套件通过：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 49.6s, jobs=6)`，日志为输出根的 `offline_suite.log`；之后仅收紧离线读取器，并完成上述真实缺帧回归及两个最终报告/破坏检查。源码提交 `b1c499c`，只含诊断工具与 FILEMAP；最终显式 pre-commit 及正常 commit 钩子均通过，日志为 `precommit_code_final.log` / `commit_code.log`。`check_work_docs.py` 与 `git diff --check` 通过，未关闭或迁移事项；这些静态检查不代替本记录的实际数组证据。

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_training_interface.py --audit rl_exp/out/lizard2_interface_live_20261023/attempt01/report.json
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_training_interface.py --audit rl_exp/out/lizard2_interface_live_20261023/attempt04/report.json
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_training_interface.py --headless --device cuda:0 --termination_fixture --out rl_exp/out/lizard2_interface_live_replay
```

## 未覆盖边界

这是同一隔离草案的运行时证据，未改正式配方、版本或资产，未开训；不替代 S5 完整交付、D/E 整体审核、新接触协议、正式采用、训练预算与策略评测。根状态取实际 articulation 数据，独立后端交叉读回覆盖关节状态及驱动目标，未另存独立后端根变换通道。普通姿态的自然终止、原 timeout 到期、所有状态/地形/reset组合、硬件能力、持续平衡、全域精度均未证明。限速/限矩与对称复测的用户取消决定不变，不恢复排期。
