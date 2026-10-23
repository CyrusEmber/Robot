# lizard2 隔离训练接口运行证据独立审核

## 适用范围

本记录由未参与本轮接口工具/运行记录执笔的上下文独立审核。已读取 `AGENTS.md`、`.codemaker/rules/work-ledger.mdc`、台账格式入口，按 `FILEMAP.md` 定位，核家族身份与[接口运行记录](2026-10-23-lizard2-interface-runtime.md)、实际工具、固定草案、原始数组及源码快照。既有 B/C 审核不替代本次接口核验。

对象仅为同一隔离草案在 attempt01/04 的动作、观测、接触采样及 reset 运行证据，以及本次发现后收紧的离线读取器。没有物理重跑、训练、正式版本/资产采用或事项关闭；不扩展用户已取消的运动、限速、限矩及对称复测。

## 验收条件

- 实际两环境全部 30 轴 PD/caps 与当前 B/C 承地读回一致；保留自由根、重力、自碰撞、TGS/false 和零速度目标。
- 从真实 affine/clip 结果和逐物理子步 backend 目标核动作列；从非零数组及实际 term 变换复算 102 维 policy，不以宽度或全零代证。
- 原框架更新后，内部接触缓存与同子步 native force、history 移位和时间戳相符；观察器不能额外刷新缓存来掩盖漏采。
- root/q/dq、动作、history、episode 的 reset 有非空脏状态；子集 reset 不改变未点名环境；区分即时目标残留与下一物理步前目标覆盖。
- 倒置夹具走原 contact termination，保留终止前快照，紧接实际零动作控制步；未完成采集和缺少该步的中间证据不能算完整通过。

## 结果

**接受此次隔离接口的有限运行证据。** 原数组及实际消费顺序支持主记录的有限结论；本审核不放行正式 S5、D/E 整体、自然翻倒/恢复、timeout 或策略性能。

### 身份、动作和观测

直接复核四次 report、各自采集 source.py、报告中四个运行时类快照、草案和实际 URDF/USD 哈希。attempt01 为 104 控制步/416 物理步；attempt04 为 7/28。attempt02 的 keyword-only API 误用错误和 `completed=false` 保留，实际读取器拒绝；attempt03 仅为 6/24 的中间切片。

两环境 Kp/Kd/effort/speed 数组逐名精确等同 B/C 当前承地报告。真实 scale/clip 对应草案两组 20/10 动作，scale 范围约 0.1667–0.4，offset 为零，动作列与 backend 关节列分别映射。四组处理探针包括大幅裁剪，source 只 process，未 apply/write/step；逐物理步 backend 位置目标重排后等于实际 affine/clip，最大参考约 0.015 rad，速度目标全部零。没有将大幅探针送入物理。

七项 policy 经原数组/default/term scale/clip 复算相同；attempt01/04 的 q、dq、raw action、根线/角速度与命令均有非零值。动作索引使用 action_names，q/dq 使用 joint_names，不能因都是 30 列而互换。此项是消费者一致性，不消除 TGS/false 已知速度偏差。

### 接触采样与 reset

逐一检查 observer 与历史运行时 source：`physics` 仅在原 sim.step 后读取 native view，`update` 先调用原 scene.update，再直接读取 `sensor._data` 和内部时间戳；没有调用 sensor.data 或额外 update 修复缓存。实际 sampling 是 dt/period 0.005 s、decimation 4、history_length 4、lazy=False。全部子步缓存与同帧 native force 最大差为零，history 最新槽相同、旧槽移位正确，时间戳一致且无 outdated；两组最大原 force 分量分别约 255.4、1578.8 N，检查非空。

完整/子集 reset 前实际 q/dq、根平移与速度、raw action、history 和 episode 均非零。attempt04 的 `fixture_prepare_reset` 前 prev_action 最大约 0.09，故 prev reset 也有非空覆盖；不能将 full_dirty/subset_dirty 中原本为零的 prev 单独当充分反例。reset 后选中 env 的 root/q/dq/default、raw/prev/history/episode 恢复，backend q/dq 与关节读回相符。attempt04 逐 term raw 也恢复为零；对子集 env0 reset，env1 的 root/q/dq、raw/prev/term_raw、processed、后端位置/速度目标、history、episode 均逐值完全不变，含读取器原本未逐项强制的 term_raw。

即时 processed/backend position target 确有约 0.015 rad 残留，未将其写作清零。运行时快照的 `JointPositionAction.reset` 只清 raw；`ManagerBasedRLEnv.step` 先 process，再在每子步 apply/write 后推进 sim。原数组中 full/subset reset 后首零步的四个物理子步前，位置/速度目标均零；attempt04 自动 reset 后紧接首零步亦同。该证据支持所采 env.step 路径没有旧目标进入首物理步，不担保绕过 env.step 直接 sim.step。

root 是实际 articulation 的 link pose 与 COM velocity；本次核其脏值、恢复及子集不变，但原件没有独立 backend root transform。没有把关节 backend 交叉读回冒充根状态的独立后端证明。

### 原终止、快照与读取器缺陷修复

从实际 URDF/FK 和 21780 个碰撞网格顶点独立重建零关节倒置姿态，最小初始间隙约 `0.0050000022 m`，与报告约 0.005 m 一致，env1 夹具根状态仍为默认。该核验使用真实网格和根放置，不是额外动力学。

另只读构造原注册任务并加载固定草案，核原 time_out、base_contact、head_contact 没有替换/缩短；实际 base 为 base_link、head 为 chest_pitch/neck_pitch，接触阈值均 1 N。按原 illegal_contact 公式，从每控制步末子步 raw history 对 attempt01/04 全部 terminated 重算，逐步一致。attempt04 第 4 控制步为 **head_contact=[True,False]，base_contact=[False,False]**，truncated=[False,False]；实际自动 `_reset_idx` 仅 env0。终止前 history 等于该步末物理子步 history，terminal_policy 为 102 维且 q/dq/raw 切片对应 reset 前数组；随后第 5 控制步确为 first_zero_auto，其四子步目标覆盖、采样及返回 policy 均复算一致。

审核发现初版读取器虽报告 `first_zero_after_automatic_reset=false`，仍会将真实缺首零步的 attempt03 标为 arrays_verified。已具名通知执行者，执行者只收紧 reader，没有新增物理或修改采集原件：加入原接触谓词复算、子步/控制步 phase 对应、fixture 唯一 env0 终止及下一控制步必须 first_zero_auto。审核再次比较差异，并以 AST 确认 collect 与 attempt04 历史快照完全相同。

本审核亲自见到修前 attempt03 被接受，修后对同一原件明确拒绝 `missing immediate first zero step after automatic reset`；最终 reader 再审 attempt01/04 均通过，分别实际拒绝 6/7 种原数组内存破坏，包括新增的 terminated 污染和首零步 phase 污染。结果与 `audit01_final.json` / `audit04_final.json` 相同。这是以真实中间缺口作反例的 reader 修复，未将 attempt03 事后改成完整物理通过。

普通姿态 attempt01 的 100 个零动作控制步没有自然终止；原 20 s timeout 未到期。两者仍未覆盖。接触为 net normal force，可能含自碰撞，不据此批准地面承重/剪切/滑动协议。

## 证据引用

- 主入口：[运行记录](2026-10-23-lizard2-interface-runtime.md)、[训练接口方案](2026-10-23-lizard2-training-interface-plan.md)、[B/C 有限审核](2026-10-23-lizard2-bc-independent-review.md)。主体工具 `rl_exp/tools/diagnose/palm_training_interface.py` 最终 reader SHA256 `c98c347e8cc3ae7fa66c00523191aae1ddfa85a0744fc4f032d72a63bf2945b2`；其 collect 与历史 attempt04/source.py AST 相同。
- 草案 `rl_exp/out/lizard2_bc_handoff_20261023/training_interface_draft.json` SHA256 `a120b8907601852e5ca7bf1190f675d75ea7a8ae0fa79e970d887628ed7e8b19`；实际 USD `721e8a4053c2a6114b5c4607e57ed34f287fe317f8f9abb47a5e857b845e9c0e`，URDF `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`；当前 PD/caps 对照 `lizard2_b_standing_force_20261022_run02/report.json`，SHA256 `5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6`。
- 以下均位于 `rl_exp/out/lizard2_interface_live_20261023/`，本审核直接计算哈希，原件未修改：

| 工件 | SHA256 |
|---|---|
| attempt01/report.json | `159719d4624078b9dbe9173409214b9186542f221d576f002d45fcd42fc15511` |
| attempt02/report.json | `aae7061563490a5e347239e8e0da0d3b56c49ebe1bf331fe81a290fc725786f1` |
| attempt03/report.json | `77017974494010ab8dd70b9fd6fd7492e12a86f6ab9612f4571d92aa024c7c8a` |
| attempt04/report.json | `6dd0667982efb3b3105cc53783a362a913d2a01d934828fcae46bf1ddedcf1de` |
| attempt01/source.py | `0e854c673c8906a23b4eb7e27c63cad162577f927fe537dae04941ddcbc21ee1` |
| attempt04/source.py | `e67a6b78be3d6e91c13b7451fcf1d7e37ca0ca3d8ce5ea952492e596e35c0c16` |
| audit01_final.json | `61cafa6061faed7e7f99cb9188a9721547b025996c2fcd55099b5aa886673b7c` |
| audit04_final.json | `fed874af825ae49ee4fab83173a1d165b5eb93688cfa87b1c3e206f41f49510f` |

- `audit03_before.json` / `audit03_after.log` 保留实际缺首零步反例的前后判词；本审核又直接调用最终 reader 确认拒绝。同目录 offline_suite.log SHA256 `ad7da624563b033dc3fe5724b32eb867c5d43f41a0071dc60c1729e37e1198d9` 为执行者套件记录，本审核不借其 37/37 代替上述数组复算。
- 持久只读复核命令为项目 Python 加 `-B rl_exp/tools/diagnose/palm_training_interface.py --audit <上述 attempt01 或 attempt04/report.json>`，不启 Kit、不写新工件。本审核的额外检查全部在内存进行，只写此审核记录，没有新增脚本、日志或复读输出。
- 记录写入后 `check_work_docs.py` 返回 `WORK_DOCS_OK (91 item file(s))`，本记录路径的 `git diff --check` 无报错；这些格式检查不代替实际审核。

## 未覆盖边界

接受的是固定草案与有限原数组及其真实消费路径。没有证明正式 S5 配方已落地、新 observation/contact 协议锚点通过、D/E 全部通过、正式采用或训练获批。没有补测普通自然终止、timeout 到期、所有 root/reset 状态、持续平衡/恢复、全姿态跟踪、硬件或被用户取消的试验。

接触/动作 observer 源码和原数组的一致不等于独立物理传感器标定；根状态没有独立 backend transform；速度偏差仍具名存在。即时目标残留只在已采实际 env.step 首零步覆盖下判为未见有害影响。读取器绑定固定草案及当前原接触谓词，配置、阈值、物理输入或采集证据改变须针对变化复审，不能沿用本记录无条件通过。
