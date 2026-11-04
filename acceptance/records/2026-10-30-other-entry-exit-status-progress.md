# 跨入口退出状态修复：阶段证据

## 适用范围

本记录对应 `work/active/exit-status-swallowed-by-app-close.md` 的在办修改，不构成跨入口验收或独立审核。冻结评测协议未改。成功路径仍须正常关闭；失败路径先保留可写证据、输出异常，再直接非零退出，代价是跳过 Kit 正常清理。stderr 不可写时不能保证栈可见。

## 验收条件

本阶段仅核实已修改入口的退出状态；最终关闭仍按事项中的逐入口真实失败与成功、回归及形态决策验收。

## 结果

### 观测与 NaN 入口

`rl_exp/tools/diagnose/diagnose_nan.py` 和 `rl_exp/tools/verify/obs_protocol_live.py` 增加启动、启动后导入及主函数异常的非零出口。进程外回归 `rl_exp/tools/verify/test_obs_protocol_gate.py` 模拟 Kit 在解释器退出时返回 0；新增导入失败场景在本轮补丁前两入口均返回 0、回归失败，补丁后八个场景通过，包含失败不调用 close、成功调用 close。该模拟不代替实际 Kit。

本机实际运行记录为 `rl_exp/tools/diagnose/out/runs/exit_status_obs_20261030/`（不入库）：`exit_codes.json` 记录 NaN 不存在任务失败 1、默认任务成功 0；live 参数不合法失败 1，`--all-tasks` 当前返回 1。`exit_codes_additional.json` 记录 live 的 `Lizard2-Flat-v3` 实际建环境成功 0，不存在任务拒绝 1；后者为正常拒绝并非异常栈。可复跑 `E:\IsaacLab\env_isaaclab\Scripts\python.exe -c "from rl_exp.tools.verify.test_obs_protocol_gate import entry_exit_regression, PROBLEMS; entry_exit_regression(); assert not PROBLEMS, PROBLEMS"`。

### 两个掌部诊断

`rl_exp/tools/diagnose/palm_contact_sample.py` 和 `rl_exp/tools/diagnose/palm_training_interface.py` 失败时先尝试写报告并保留原异常，正常路径才关闭 Kit；若 `app.close()` 抛非零 `SystemExit`，不再静默吞掉。两个入口的 `--self_check` 通过；修补前自检中的非零 close 样例失败，修补后通过，同时覆盖原始异常、env.close 和写盘失败组合。该自检模拟 finally，不证明真实 Kit 的所有关闭故障。

前一轮掌部真跑在 `rl_exp/out/palm_exit_probe_20261030/current_exit_codes/`（不入库）：无效 GPU ordinal 的两条启动失败均退出 1，报告保存原异常；默认 GPU 的两条成功尝试被固定安装检查错误拒绝。根因是检查目标 URDF 时读取了重映射前的母任务配置。`rl_exp/tasks/obs_protocol.py` 现先完成草案配置映射与覆盖，再检查最终初始状态与固定/可动安装是否相符，选择器按正则匹配；验证通过前不会把草案写回调用者。新增自检在修复前因该检查失败，修复后通过，并覆盖固定和可动安装的匹配与不匹配、正则及重映射。独立只读审核未发现阻塞缺陷，未执行真实仿真。

修复后掌部两入口真实运行均退出 0，`report.json` 均记录 `completed` 和 `closed`；证据在 `rl_exp/out/palm_exit_probe_20261030/target_config_fix_20261103/`，`run_status.json` 记录修复时源码哈希及退出码。该修复的自检后来增加反例，源码哈希随之变化；生产路径未再改变。启动失败及成功分别有当前掌部入口的源码快照，不能外推其他失败方式。

### 耦合探针

2026-11-03 后续选择：用户决定保留默认严格拒绝，并允许通过显式 `--allow_unconfirmed` 只读复读无退出凭据的旧批次；此时逐臂警告且不得写报告。存在但无效的凭据仍拒绝。下述兼容性段保留当时记录，以本次选择为准；限定复核与命令见 `acceptance/records/2026-10-28-eval-column-coupling-repair.md`。

`rl_exp/tools/diagnose/column_coupling_probe.py` 的启动器异常直接输出栈并非零退出。收尾先落原始数据和 `failed` 元数据，`env.close()` 返回后才原子替换 `complete` 元数据；关闭失败时退出非零且保留失败标记，避免独立 `compare` 接收该臂。新增子进程自检模拟异常关闭与以 0 结束的 Kit：修复前关闭失败仍写 `complete`，修复后标为 `failed`；启动器回归用临时修前源码重放，修前退出 0，修后退出 1。

真实捕获一次成功、一次无效设备启动失败，退出码分别为 0、1，失败日志有栈，见 `rl_exp/tools/diagnose/out/runs/column_exit_20261103/`；`exit_codes.json` 含运行前后源码哈希。`app_guard_success_exit.json` 记录加入应用关停保护后的真实成功读数 0。子进程自检注入 `app.close()` 异常并模拟退出时以 0 覆盖：原来返回 0，保护后返回 1；同时覆盖非零 `SystemExit`、正常 `SystemExit(0)`、原始数据写入失败和元数据替换失败。`SystemExit(0)` 起初被保护误判为 1，补丁后为 0。若 `app.close()` 抛异常，先输出栈，尽力原子替换 `failed` 元数据再退出 1；如替换本身也失败，旧 `complete` 元数据可能保留。

父进程现仅在采集子进程返回 0、元数据和原始数据身份核实后写 `exit_status.json`，绑定该元数据字节的摘要；CLI 独立 `compare` 必须验证每一臂退出凭据和摘要。双故障模拟中旧 `complete` 元数据仍存在但无凭据，修复前比较误接收，修复后 CLI 与严格模式拒绝；受控失败的子进程返回非零时父进程不会写凭据或启动下一臂。比较对元数据和原始 `.npz` 使用各自一次读取的字节进行哈希与解析，避免文件在校验后被替换而读到不同数据。数据写入失败可能留下半文件或缺元数据，均不具备退出凭据。

兼容性：按用户明确要求，CLI 和 Python `compare(root)` 均拒绝无父进程退出凭据的旧批次及直接 `capture` 输出，移除未发布的 `allow_unconfirmed` 绕过；保留旧报告或重跑，不为旧批次伪造凭据。自检中默认调用无凭据样本在修改前误接受、修改后拒绝；真实四臂凭据数据由 Python 默认调用正常读取。此验证依赖静态归档，无法防御协调篡改凭据及数据；不能从成功退出推断 Kit 内部未报告的故障。真实 Kit 的双故障未注入。

### Kit 原生关停状态

本机真实启动 Kit，分别调用 `app.close(exit_code=0/1/7)`，子进程实际返回 0/1/7；日志与退出码在 `rl_exp/tools/diagnose/out/runs/app_close_exit_20261103/`。这只证明本机 Kit、这些参数及正常关闭路径，不证明其写盘异常或其他版本的行为。

## 证据引用

- 观测与 NaN 真跑：`rl_exp/tools/diagnose/out/runs/exit_status_obs_20261030/`；退出码见 `exit_codes.json` 和 `exit_codes_additional.json`。
- 当前掌部真跑：`rl_exp/out/palm_exit_probe_20261030/current_exit_codes/`、`rl_exp/out/palm_exit_probe_20261030/target_config_fix_20261103/`。
- 耦合探针真跑：`rl_exp/tools/diagnose/out/runs/column_exit_20261103/`；回归：`E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\diagnose\column_coupling_probe.py selftest`。
- 四臂退出凭据真跑：`rl_exp/tools/diagnose/out/runs/column_exit_confirmation_retry_20261103/`，`status.json` 记录运行返回 0 和源码首尾哈希；前一尝试 `rl_exp/tools/diagnose/out/runs/column_exit_confirmation_20261103/` 因并行修改 `rl_exp/tools/verify/test_eval_record.py` 停在第二臂，保留现场。
- 原生关停退出码：`rl_exp/tools/diagnose/out/runs/app_close_exit_20261103/exit_codes.json` 与同目录日志；本机临时子进程分别传 `--headless` 调用 `app.close(exit_code=N)`。
- 草案加载回归：`E:\IsaacLab\env_isaaclab\Scripts\python.exe -c "from rl_exp.tasks.obs_protocol import diagnostic_target_self_check; diagnostic_target_self_check()"`。
- 两个掌部离线清理自检：分别运行 `E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\diagnose\palm_contact_sample.py --self_check` 和 `E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\diagnose\palm_training_interface.py --self_check`。

## 未覆盖边界

- `ablation_harness/eval.py`、`rl_exp/tools/verify/test_eval_record.py`、`rl_exp/tasks/obs_protocol.py` 和 `rl_exp/tools/diagnose/column_coupling_probe.py` 混有并行事项的修改，不能整文件归属本轮；逐 hunk 协调后才能提交。真实 Kit 的关停和写盘双故障尚未注入；凭据并非防篡改证明。
- 当前成功真跑依赖可能并发变化的任务配置和资产；逐入口重新核对代码快照、失败与成功退出码。尚未清点本事项范围内全部入口，尚未确定共享助手或逐处关停形态。
- 11 月 3 日重跑完整离线套件通过 37/37，`check_golden_frozen.py` 当前通过；lizard2 v7 冻结引用仍为未提交占位 `uncommitted-v7:f82affdc627aa82b`，且相关锁及闸门属于并行工作树，未将其纳入本事项。共享文件后续变化须重跑。阶段结果未整体独立审核，事项继续 `in_progress`。
