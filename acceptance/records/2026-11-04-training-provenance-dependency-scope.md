# 训练来源依赖范围：实施中（2026-11-04）

## 适用范围

`work/closed/2026/training-provenance-dependency-scope.md`；覆盖训练来源的路径分类、记录及重建材料读取，并保留短训及训后证据。修改后独立复审通过训练来源范围；不是训练成功、依赖闭包或重建评级结论。

## 验收条件

按事项的临时 Git 仓、T0 快照、子进程反证、真实 run 运行期观察、旧记录回退和离线闸门判据逐项核对。完成实现和证据后，由不带执笔历史的新上下文审核。

## 结果

### 修复前复现

在临时 Git 仓分别只修改一个已跟踪文件，通过真实 `code_sources → git_state/_changed_paths → manifest.begin`，使用独立活动生命周期 fixture 排除退休拒绝。三个 eval 文件分别被脏树拒绝；仅改 `README.md` 启动放行，但 repository 的 `_code_item` 无归档拒绝，文档再改后 `_verify_code` 为未知。原记录 `2026-09-22-dirty-tree-refusal-scoped-to-code.md` 把 rebuild 已跟踪散文描述为原本就豁免的说法不成立；未改写原记录。正式回归保留在两份现有测试里，不依赖已删除的临时脚本。

### 初始文件声明及训练侧导入方检查

2026-11-04 对 `rl_exp/tasks`、`rl_exp/tools/runrecord`、`rl_exp/tools/launch_recipe.py`、`rl_exp/tools/verify/cfg_snapshot.py` 分别搜索 `ablation_harness|importlib|__import__|run_ablation|record\.py|eval\.py`，并阅读匹配到的动态加载与字符串。逐项结果：

- `ablation_harness/eval.py`：未发现上述训练侧作用域静态导入、动态导入或运行时字符串引用。
- `ablation_harness/record.py`：未发现上述训练侧作用域导入；`runrecord/binding.py` 仅有描述性文档引用，方向不是训练导入 eval record。
- `ablation_harness/run_ablation.py`：未发现上述训练侧作用域导入或运行时字符串引用。

`launch_recipe.py` 用配方注册项动态导入任务；`tasks/obs_protocol.py` 使用文件加载器加载任务辅助模块；这些动态路径须结合运行期反证，不能仅因本次文本搜索无命中就当成完整依赖证明。`provenance.isaac_root` 和 `cfg_snapshot.py` 均导入共享的 `ablation_harness.host_paths`，该文件不在声明内。`provenance.py` 自身及其他未声明代码、配置、资产仍受保护。上述搜索不覆盖宿主 fork 的全部代码、间接拼接字符串、原生扩展、pickle、被忽略配置或之后新增的路径；每次增删声明都须重新检查并记录。

### 已实现与测试

- T0 保存 `eval_exclusive_paths`、完整 `changed_paths_full` 和 `changed_blocking`；整仓 `dirty` 与 diff 摘要仍记录。旧记录缺分类字段不套用当前声明。重建材料保留上述字段。
- `after_env` 在 `sys.modules` 中按真实文件路径记录观察到的仓内模块，声明路径命中记违例；缺观察证据或已记录违例在复核中不能当作完整。此为反证，不是独立性放行依据。
- 路径使用无重命名折叠的 NUL 输出，未跟踪路径完整保留；受保护变动的 override 不免除归档。Git 状态读取失败不当作干净树。
- 修复前新增真实仓测试失败；修复后 `test_run_manifest.py`、`test_rebuild_gate.py` 的先前版本通过。对受保护 `configs/run.log.yaml`，在工作树暂时移除 repository 分类的保护合并后，真实临时 Git 仓运行 `test_rebuild_gate.py` 输出 `FAIL scope/untracked-filtered/not-lost`，退出 1；恢复修复后的全套中该检查输出 `REBUILD_GATE_TEST_OK`。该例经真实 T0/T1 与材料采集，不只比较过滤函数。
- `test_launcher.py` 八个独立样例覆盖真实 launcher CLI、`--launch` 子进程交接和 trainer 桩内真实 `manifest.begin`；三个声明文件分别注入 launcher、trainer 两侧均触发守卫。守卫由 `settrace` 改为 `setprofile` 后单项 22.414 秒、输出 `LAUNCHER_OK`；停用守卫的六个注入样例失败。trainer 仍是桩，不是实际 fork 训练器；守卫只覆盖进程主线程的 Python 文件执行，不覆盖原生、伪造文件名或之后的导入。
- 先前代码完整套件曾输出 `ALL_OFFLINE_CHECKS_PASSED`；混合脏树修复后两次完整套件均为 37/37 行为通过但成本闸门退出 1。第一次 rebuild 单独 27.0 s > 25 s；优化测试夹具中不可变 Git 对象与宿主路径的重复检查后，第二次 rebuild 单独 23.5 s，但 launcher 单独 25.1 s > 25 s。实际结果为 `OFFLINE_SUITE_COST_REGRESSION`，不是全套通过；默认运行未审计串行总成本。各真实 Git 工作树采样仍执行，不将夹具缓存当行为能力证据。
- 混合脏树回归：真实临时 Git 仓同时包含受保护的已跟踪变更、未跟踪 `.md` 和未跟踪声明文件。原实现因沿用 `untracked_in_code_root`，`test_rebuild_gate.py` 报 `FAIL scope/mixed/verify`、`FAIL scope/mixed/archive`；按 T0 `changed_blocking` 过滤后，同一测试 `REBUILD_GATE_TEST_OK`，`test_run_manifest.py` 为 `RUN_MANIFEST_TEST_OK`。测试另检查受保护未跟踪文件仍需归档，缺新字段的旧记录仍按旧口径处理。复读命令见下方。旧展示字段本身仍保留历史全量分类，不能把 `untracked_requires_archive` 单独当新口径结论。
- 独立审核后补二进制负例：真实 Git 仓的已跟踪二进制新增、修改、删除产生不可应用的 `Binary files … differ` 存根；修前材料采集误报 `captured`，历史材料检查亦未拦截。修后 `rebuild` 对存根采集拒绝、历史材料复核失败，三个真实场景及文本内容误报、未跟踪文件、排除路径和 T1 后漂移例通过；不更改历史摘要或补造 T0。同一完整 diff 同时含排除路径二进制和受保护变更时会保守拒绝。最新完整套件行为 37/37 通过，但 rebuild 单独 27.7 s > 25 s，退出 `OFFLINE_SUITE_COST_REGRESSION`，未通过成本闸门；另需新上下文复审本次修复。
- 已跟踪受保护文件同路径 T0→T1 内容变化、T1 后变化，以及 T1 声明收紧但按 T0 清单判断，已有真实仓用例。源采集只反映各采样时点，两个时点之间或 T1 之后的训练期变动不受完整监控；存在阻塞路径时整仓 diff 的非受保护变化也可能导致保守报告。
- 限定性反例：若记录已有非空 `scope_violations`，原复核只使用该列表而不追加从 `observed_dependencies` 重算的其他命中；人为构造遗漏 `eval.py` 的非空列表时，复核仍阻断，但问题详情只显示已有的 `record.py`。回归在修复前输出 `scope/after-env-incomplete-violations` 失败；现合并已记录违例和观察命中，修复后单项及完整离线套件通过。该反例针对明细完整性，不能误称修复前会放行违例。
- 先前仿真构造：`obs_protocol_live.py --tasks Lizard2-Flat-v7 --envs 1 --viz none` 输出 `OBS_PROTOCOL_LIVE_OK`；该诊断没有调用 `manifest.after_env`，不能替代真实训练。用户随后要求 v7 短训并明确允许本次脏树豁免；历史已训 run `2026-11-03_17-07-29` 的旧 manifest 不含新字段，不修改或补写历史记录。
- 真实 fork 反证：隔离诊断 `rl_exp/tools/diagnose/launcher_source_probe.py` 的历史输出 `rl_exp/tools/diagnose/out/launcher_source_probe/20261104-185247-8ff6d73d/summary.json` 记录 control 真实交接到 fork `train.py` 并从真实 `manifest.begin()` 返回后以 73 停止；三个声明文件分别在 launcher 和 trainer 路径注入，六例均被守卫以 86 拦截。诊断重定向 manifest 至隔离目录，在 `gym.make` 和学习之前退出；使用单独的诊断 override，不是训练，也不扩大用户短训授权。守卫不覆盖原生加载、其他线程和后续路径，不能证明完整依赖闭包；前几次诊断失败现场仍保留。之后脚本摘要读取改为共享原语，通过静态闸门；2026-11-05 用修改后的脚本重新执行，`rl_exp/tools/diagnose/out/launcher_source_probe/20261105-105405-98d8ff34/summary.json` 的 control 和六个注入例均通过，退出 0，仍在环境构建前停止。提交前将 fork 根目录改用机器路径统一解析后再次复读，输出 `rl_exp/tools/diagnose/out/launcher_source_probe/20261105-161938-c40984cb/summary.json`，control 和六例注入均通过，未开始训练。历史输出未改写。
- 2026-11-05 针对二进制存根的单独只读复核未发现已证实的存根拒绝缺陷；它不是对整个事项及后续变更的独立审核。另一次只读预审指出已提交的声明变更可更改豁免清单，但其例子将声明改空后把受保护文件提交，干净树放行并不证明本闸门误放行；声明变更仍须逐项人工审核训练依赖，运行观察也不证明完整闭包。真实 fork 注入仅证明探针守卫在所测主线程路径阻断，并非产品自带的全程导入拦截。重建回归新增缓存后真实 Git 工作树仍逐次采样；多次单项结果虽输出 `REBUILD_GATE_TEST_OK`，但耗时在预算附近波动。2026-11-05 完整套件行为 37/37 通过，重建项波内 35.3 s、安静重跑 29.0 s，超 25 s 预算，最终 `OFFLINE_SUITE_COST_REGRESSION`、退出 1；其他超线项安静重测达标。随后仅缓存真实 Git 夹具初始化后不再变化的 HEAD，状态、路径和 diff 仍逐次真实采集；单项两次 24.606 s、24.567 s，均通过，但余量不足。随后再次运行完整套件，行为 37/37 通过，重建项波内 40.5 s、安静重跑 29.4 s，仍以 `OFFLINE_SUITE_COST_REGRESSION` 退出 1。补充夹具开始和结束 HEAD 一致断言后单项 25.538 s、行为通过，仍未稳定达标。不降低覆盖或提高预算，不能凭单项称全套通过。
- 针对二进制配置的临时真实 Git 复核：当前 Git for Windows 2.56.0 中 `git -c diff.binary=true diff HEAD` 与默认 diff 一致，仍为无法应用的存根；显式 `git diff --binary HEAD` 在同一 HEAD 的干净工作树应用成功且字节一致。仅覆盖已跟踪二进制修改，不推及其他 Git 版本、驱动或脏基底；当前代码仍按原普通 diff 摘要口径判断，不修改历史摘要。

### 真实 v7 短训来源读数

- 执行者 CodeMaker；2026-11-04 16:12:57 +08:00，新建 run `E:/IsaacLab/logs/rsl_rl/lizard2_v7/2026-11-04_16-12-57/`，`Lizard2-Flat-v7`，seed 42，16 环境，从头执行 1 次 PPO 更新；不恢复旧 run。实际命令：`set HEADLESS=1&& set PYTHONDONTWRITEBYTECODE=1&& set "RL_ALLOW_DIRTY_TREE=User explicitly authorized this one-iteration v7 provenance validation on the dirty tree; uncommitted changes require archival and are not proven reproducible."&& E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\launch_recipe.py --task Lizard2-Flat-v7 --num_envs 16 --max_iterations 1 --seed 42 --launch --python E:\IsaacLab\env_isaaclab\Scripts\python.exe`；实际交接 fork trainer，终端回报正常结束、退出码 0，checkpoint 落盘时间 16:13:11 +08:00。训练终端输出没有另存日志，结束时间仅知晚于末档写入，不能补造精确退出时刻。
- T0 `eval_exclusive_paths` 三项、`changed_paths_full` 和 `changed_blocking` 均存在；`env_constructed.observed_dependencies` 记录 26 个模块、24 个仓内路径，含共享 `ablation_harness/host_paths.py`，`scope_violations=[]`、`failures=[]`。16 环境、seed 42、policy 宽度 90 与声明相符。T0/T1 整仓 diff 摘要及变更路径相同；这是两个采样点，不是训练全程未变证明。
- checkpoint `model_0.pt` 的 SHA-256 在 CPU 安全加载前后均为 `94cd4fb180cfd1918e9f08e51920bfaa6aefffdba6a2a3312ff517febc16edde`，68 个张量无非有限值。修复前 `manifest --verify` 的 repository 未知行误将非阻塞未跟踪 `.md` 计入 code。按 T0 范围修复后再次复核仍为 `RUN_MANIFEST_PARTIAL`：repository 由于 T0 和当前完整 diff 不匹配而未知，IsaacLab 因未跟踪文件未知，安装态 rsl_rl 的来源也未知；退出 0 不等于可重建。
- 用 `rebuild --capture` 按原样尝试归档：`rebuild_capture/rebuild_material.json` 为 `refused`，原因包括 repository 当时完整 diff 摘要 `25a89360…` 与事后 `bc097289…` 不一致，以及 rsl_rl 为安装包、源码未固定。IsaacLab diff 与未跟踪文件已保存到 `rl_exp/archive/2026-11-04_16-12-57/`，但未跟踪内容没有 T0 摘要，不证明同源；训练后另一时点的 `repository-current-after-training.diff` 仅作诊断，不是 T0 归档。未核定差异，不恢复或改动其他会话文件。
- 训练探针只读到一次迭代：`Policy/mean_std=0.9992`、`Loss/value=0.0165`、没有探针告警；单点无法看趋势，训练 success 和零奖励不能作为能力结论。

### 训后固定评估

- 责任：CodeMaker 执行；独立审核已执行且未通过，未逐片复看九宫格。流程状态未完成，模型未判定；robust 评测和录像的实际命令、带时区启动结束时间及退出码分别保存在各自 `execution.json`，原始日志分别保存在 `eval.log` 和 `video.log`。九宫格已逐片抽帧验看，未完成动作见下表。
- checkpoint 是本 run 内末档 `model_0.pt`，读取前后摘要一致，CPU `weights_only=True` 可读；robust eval 与九段视频均实际加载并绑定相同摘要。无 resume，坏末档不适用。训练仅用于采集来源字段，不能把迭代 0 的训练奖励、成功率或探针零值当成模型能力。
- 评估协议 `ablation_harness/protocols/locomotion_eval_v3.yaml`，冻结 commit `29dee477f328246d49955804f4648af169138b2b`，时间 `2026-09-20T10:31:04+08:00`；文件 SHA-256 `00f8c067932eacdf680f8104c452e98f1ce61973af042cd0f95db2e9818ec47f` 与 `record.json.eval_protocol.digest` 一致，早于本次评估。PLAN 只要求分项报告且性能阈值未定，不凭此次结果增设通过线。
- robust 评测：`2026-11-04T16:14:28+08:00` 至 `16:16:32+08:00`，退出 0，TRAIN task、seed 123、72 环境，协议 30 s；记录中 corruption 开启，任务物理 DR 与 interval push 均为 None，reset 固定。协议另安排 12 s、4 m/s 的 recovery kick，不能把模式名当成任务 DR 已启用的证据。视频入口为 nominal、seed 0、单环境且不注入 kick，不能与 robust 逐项混比。
- 关键读数按有效样本解释：`eval.log` 报终止帧捕获 1419、首局提前终止 72/72；`eval.json` 仅 0–5 s 段有有限误差，线速度 MAE 0.2029 m/s、偏航 MAE 0.0212 rad/s，几何跌倒标记 0。5 s 起各段 MAE 为 NaN；首局在 12 s 扰动前已全终止，recovery `measured_envs=0`、恢复时间和未恢复比例未定义。输出中停车残速 0 和冲击后跌倒率 0 的实现使用空集合分母夹紧，**均无有效样本，不能当实测零或成功**。逐地形 completion 在 `eval.json`，仅覆盖各环境终止前有效窗口，不能当 30 s 完整地形能力。终止原因与首局终止时刻细分未落盘，不擅自归因。
- 平地逐足承载/摆动、落地再承载及非足支撑数值缺测：`acceptance/records/2026-11-04-lizard2-shank-tilt-reach.md` 的第 3 步只核定净力阈值作为候选接触指示，明确不代表真实落地或正式支撑分类；当前 eval 与录像也不输出核定逐足承载。不得把候选接触边沿当落地、把腹部净力当全部非足支撑，见下方缺口表。

#### 九段逐片抽帧验看

- `video_matrix.py` 运行 `2026-11-04T16:16:46+08:00` 至 `16:25:43+08:00`、退出 0；九段原片、带速度/视角标签的 `plane_overview.mp4` 和 `matrix.json` 均保留，均绑定本次 `model_0.pt` 摘要。九段和合成片均已完整解码（FFmpeg 退出 0）；完整解码不是人或 agent 连续看完。
- 视频是 PLAY、nominal、无恢复 kick、1 env、seed 0、平地、每段 10 s，速度 0.5/1.5/3 m/s 均位于配方 vx `[0,3]`；相机跟随。评测为 TRAIN、robust、seed 123、72 env、地形套件，不能直接当同条件对照。任务 reset 固定（root 位置/速度偏移均为 0、关节缩放 1 和速度 0）；视频关闭观测 corruption。`matrix.json` 记各段的重置计数，不是裁判或位置精度报告。
- CodeMaker 于 `2026-11-04T16:28:50+08:00` 前查看下表每个 `frames/*.png`；方式为 agent 抽帧，非连续播放：常规图每 1 s、标注 0–9 s，异常图每 0.25 s、标注 0.75–2.00 s，覆盖首次重置附近。抽帧采样间可漏瞬态/相位，画面被身体、阴影或视角遮挡；不可据此量化逐足接触/承载、判定确切碰撞部位、连续步态或躯尾协调。九张常规图与九张加密图同保留在视频目录 `frames/`。

| 原片（相对视频目录） / 速度 / 视角 | 图像证据（`frames/`） | 实际抽帧观察及限制 |
|---|---|---|
| `side/0.5mps_plane.mp4` / 0.5 / side | `side_0.5.png`、`side_0.5_reset.png` | 0.75–1.00 s 头部逐渐接近地面，1.25 s 形态回到高位；中尾多次出现类似低姿。画面内跟随但无法凭图断言接触力与足相。 |
| `front/0.5mps_plane.mp4` / 0.5 / front | `front_0.5.png`、`front_0.5_reset.png` | 首次重置前后躯体在画面中央，1 s 左右头部低；头部遮挡躯干及足部，无法判接触顺序。 |
| `rear_oblique/0.5mps_plane.mp4` / 0.5 / rear | `rear_oblique_0.5.png`、`rear_oblique_0.5_reset.png` | 能看到背部与尾部，1 s 前后低姿及 1.25 s 抬回；远侧足遮挡，尾部出画，不能判完整协调。 |
| `side/1.5mps_plane.mp4` / 1.5 / side | `side_1.5.png`、`side_1.5_reset.png` | 1 s 附近头部下沉，1.25 s 恢复较高姿；约 3、8 s 常规图也见低姿，不能凭离散帧判步态连续性。 |
| `front/1.5mps_plane.mp4` / 1.5 / front | `front_1.5.png`、`front_1.5_reset.png` | 0.75–1.25 s 头部下沉后回高，前视角遮挡腹部/远侧足；不能判逐足载荷。 |
| `rear_oblique/1.5mps_plane.mp4` / 1.5 / rear | `rear_oblique_1.5.png`、`rear_oblique_1.5_reset.png` | 首次重置前后身形变化可见，尾部局部出画；1 s 采样不足以判断躯尾协同或瞬态擦地。 |
| `side/3mps_plane.mp4` / 3 / side | `side_3.0.png`、`side_3.0_reset.png` | 1 s 头部低，1.25 s 回高；9 s 再见低姿。摄像机跟随使相对画面位置不能代替行进速度。 |
| `front/3mps_plane.mp4` / 3 / front | `front_3.0.png`、`front_3.0_reset.png` | 多数帧机体居中，1 s 左右头部低；正面遮挡足和躯干，不能判非足支撑。 |
| `rear_oblique/3mps_plane.mp4` / 3 / rear | `rear_oblique_3.0.png`、`rear_oblique_3.0_reset.png` | 可看背部姿态变化，远端尾部出画；重置前后可见姿态跳变，但相位与接触不能由抽帧确认。 |

各段 `matrix.json` 报 10 s 内 8 次重置、首次约 1.20–1.24 s；这与抽帧所见低姿/回高相容，不以画面代替终止原因。

转向补片：`turn/videos/play/rl-video-step-0.mp4`，fork PLAY 入口、seed 0、单环境、配置固定 vx=1 m/s、vy=0、wz=+0.5 rad/s；关 heading、standing、heading-env，重采样间隔 1e9 s。`turn/execution.json` 记录命令、checkpoint 原件与副本同摘要、运行 `2026-11-04T16:35:55+08:00` 至 `16:37:48+08:00`、退出 0；`turn/video.log` 有 task、seed、环境数、活动 command term 和 checkpoint 加载记录，但未打印逐步命令读回，因此固定命令是传参证据，不冒充运行时逐帧核验。CodeMaker 于 `2026-11-04T16:39:59+08:00` 前验看 `turn/turn_sheet.png`（0–9 s、1 Hz）和 `turn/turn_reset_sheet.png`（0.75–2.00 s、4 Hz）；画面远、小机体、躯尾变化难分辨，1 s 左右头部较低，未能从抽帧可靠识别连续转向或接触；原片解码退出 0。该补片按 PLAY 配方，不是 robust 扰动，也不能判转向合格。

#### 新一次具名场景补录与验看

`scenario-diagnostic-20261104-a/` 下的 `turn.mp4`、`stop.mp4`、`push.mp4` 是另一次诊断，不是原转向片的读回。CodeMaker 用 `rl_exp/tools/diagnose/policy_scenario_video.py` 调用同一 checkpoint，PLAY、nominal、seed 0、平地、1 env、3 s/片，`execution.json` 记录实际子进程命令和 2026-11-04 17:18:44–17:20:04 +08:00、退出 0，加载前后摘要均为本次 checkpoint 的 `94cd4fb1…`。逐步文件 `*_steps.jsonl` 记录策略观测中的命令、管理器读回、运动及 reset；三个场景各 150 步的策略观测命令与所设值一致。stop 于 0.30 s 切零；push 于 0.30 s 以世界方向约 `(-0.9997, 0.0235)` 注入 4 m/s，与正式协议 12 s 的时间线不同，不能代替 robust 首局结果。turn、stop 首局分别在控制时间 1.22 s、1.24 s 终止；push 的 3 s 内未终止。push 记录中注入当步世界 x 速度从约 +0.207 变到 −3.772 m/s，是新诊断的实际响应，不能据此判恢复合格。首局 done 的画面与 `motion_after_step` 已经 reset；终止前状态另在 `terminal_pre_reset`，后续样本不得混入首局。

CodeMaker 于 2026-11-04 17:22:15 +08:00 前抽帧验看，原片和命名 PNG 均在该目录，FFmpeg 全片解码退出 0，非连续播放：

| 补片 | 实际看过的视频时间 / 帧图 | 观察与限制 |
|---|---|---|
| `turn.mp4` | 0、0.8、1.0、1.2、2.98 s；`turn_t*.png` | 0 s 黑屏；其余可见机体，低姿与回高片段难靠离散画面确定连续转向。1.2 s 按逐步记录已 reset，2.98 s 非首局。 |
| `stop.mp4` | 0.3、1.0、1.2、1.5、2.98 s；`stop_t*.png` | 机体有画面、相机跟随；1.2 s 附近画面较低，1.5、2.98 s 已是 reset 后，不能据此判断首局停止效果。 |
| `push.mp4` | 0、0.3、0.6、1.5、2.98 s；`push_t*.png` | 0 s 黑屏；其余可见机体，抽帧姿态变化有限；跟随机位与遮挡使位移、接触及连续恢复不能从画面核定。 |

`video.log` 含 RTX 动态对象变换同步及物理速度噪声警告；现有数据未证明它是否影响画面。首帧黑屏与 fork 采集器 warmup 空帧行为相符，不能称 150 帧都是有效画面；无独立像素与物理同步校验。图片命名来自 FFmpeg 请求的时间，未逐帧核对容器 PTS。抽帧及远侧遮挡不能核定逐足、非足接触或躯尾连续协调。原 robust 评估的停车及 12 s 扰动首局窗口仍是零样本、指标未定义；固定评估保持未完成。

#### 未完成项与责任

| 缺项 | 分类 / 影响 | 责任人与下一步 |
|---|---|---|
| 转向连续运动及画面同步 | 新诊断已读回策略命令，但首局 1.22 s 终止，原补片无命令读回；RTX 有变换同步警告，画面能否代表每步真实姿态未核定。v7 PLAN 的转向目标不能判通过 | CodeMaker：保留两次独立现场；补固定机位或像素/物理对照，或交人连续验看并说明局限。 |
| 停车及恢复扰动视频 | 新诊断提前安排停车与扰动并保留原片，但并非协议时序；robust 首局在协议窗口前已全终止，停车及恢复无有效样本 | CodeMaker：保留零参与证据、区分诊断工况并核对画面同步，不将 reset 后帧或新诊断当原评估结果。 |
| 足端承载、摆动、落地再承载与非足支撑数值 | 资产/探测证据见 `acceptance/records/2026-11-04-lizard2-shank-tilt-reach.md` 第 3 步：仅候选净力指标，尚无核定逐接触支撑口径；属于当前能力缺口，v7 的支撑/摆动目标不能判通过 | `work/active/lizard2-contact-protocol.md` 承接接触口径，`work/active/lizard2-thigh-drive-shank-landing.md` 承接落地阶段应用；CodeMaker 不把候选当正式数值。 |
| 来源材料归档 | 执行失败：T0 整仓 diff 已不匹配、rsl_rl 安装态无源码；真实 run 的依赖可重建性未知 | CodeMaker：保留拒绝与现存材料，核对并交 `work/active/verified-rebuild-rating.md`；不可用当前内容倒填 T0。 |
| 复核 | 已由新上下文审核，未通过；审核后代码已变化 | CodeMaker 修复缺陷、补证并重跑闸门，随后交新上下文重审；本次审核未逐片复看九宫格。 |

### 独立审核（2026-11-04）

新上下文独立读取实现、测试、真实 run 与评估证据，并复读三个相关单项；结论 **未通过，退回实施**。未独立逐片复看九宫格。审核发现：

1. `ablation_harness/eval.py` 在注入本步命令前取得观测，注入后仍用旧观测推理；首步及切换步的策略输入可能与用于指标的命令错位。需用首步、切换、reset 反例核验并处理；冻结协议不得就地改写，现有评估保留此限制。
2. 普通 `git diff HEAD` 对已跟踪二进制仅给出 `Binary files … differ`，不含目标字节。审核者用真实临时 Git 仓修改 `robot.usd`，`rebuild._code_item` 仍给 `stored-diff`，但归档文件 `git apply --check` 退出 128。受保护不等于材料可重建；后续已按上文补真实仓红绿和存根拒绝，尚须独立重审，不伪造历史 T0。
3. `test_launcher.py` 使用 trainer 桩；该桩的注入反证和真实短训的 `after_env` 分别成立，但不等于在真实 fork trainer 上执行独立进程导入反证，需对照事项关闭条件补证。
4. robust 首局提前终止 72/72，停车与恢复窗口零参与；新 PLAY nominal 提前扰动视频不是同一工况。画面同步、v7 核心支撑/摆动与转向能力仍未核定；流程不能宣称完成。
5. 最近完整套件两次行为 37/37，但成本闸门退出 1，见上文；须重新验证，不把单项通过冒充全套通过。

上述发现有不同责任范围；评测命令时序已转入 `work/active/eval-command-observation-timing.md`。本项曾加入未冻结的 v5 草案，用户确认最小范围后已撤除；旧评估时序缺陷仍未修复，历史结果不改写。来源归档同源及评级由 `work/active/verified-rebuild-rating.md` 承接；短训画面同步、停车恢复零样本及支撑/摆动缺口由 `work/active/v7-short-run-post-train-evidence.md` 承接。后续实现或证据变更后须再次交不带执笔历史的新上下文审核。

### 最小回归调整（2026-11-05）

按用户要求保留必要测试：真实 Git 二进制新增、修改、删除仍分别验证存根不可应用及采集拒绝；既有归档和历史材料复核各保留二进制修改的真实反例，不重复三遍同一读取路径。混合脏树旧格式仍覆盖字段分别缺失的采集拒绝，复核及未跟踪归档检查保留双字段缺失反例；声明查找改为直接引用实际声明。新增真实未跟踪受保护文件在 T0 后出现的 T1 反例，并核实 T1 当前声明改变时仍按 T0 声明处理。现行 `test_rebuild_gate.py` 单项两次通过，32.357 s、35.847 s；仍超过既定 25 s 成本上限，修改后完整套件及最终独立复审尚未通过。

### 恢复目录来源假通过修复（2026-11-05）

用户指出：测试把当前仓库作为依赖、指定不存在的恢复目录和无关原路径仍获通过，`check_sources` 把依赖目录当作重建来源，资产锁亦有同类问题；相邻目录的字符串前缀也会被误认成包含关系。补充三条反例后，修复前 `test_rebuild_gate.py` 以 `REBUILD_GATE_TEST_DRIFT` 退出 1，三条分别失败；修复后仅允许声明的重建模块与资产锁位于实际恢复根内，路径按组件判断，并拒绝不存在的恢复根。`maintest` 删除和恢复使用同一 `rebuilt` 范围。独立解释器分别从临时恢复根及原仓加载，核对真实包来源和资产锁，前者通过、后者失败；其他进程内材料/checkpoint 测试使用模拟来源，不作为实际导入证据。后续将独立解释器资产锁改为使用记录中的 `<REPO_ROOT>` 形式，单项 `REBUILD_GATE_TEST_OK`、43.567 s。此项修改前的最近完整套件行为 37/37，恢复测试安静重跑 43.3 s 超 25 s，成本闸门失败；最后修改后完整套件未重跑。检查只覆盖声明包的导入来源和资产锁位置，不证明所有子模块、动态加载或训练等价；T0 未跟踪内容同源仍未解决，详见 `work/active/verified-rebuild-rating.md`。

### 重建回归运行时机调整（2026-11-05）

按用户决定，`test_rebuild_gate.py` 移出默认离线套件，保留单独运行入口；训练配方打 tag 前执行，默认套件和 Git tag 不自动运行它。默认套件不再以该单项的 25 s 耗时判失败；单项回归本身仍须通过，不以移出套件替代实际恢复证据或独立审核。调整后的首次默认套件行为 36/36 通过，但 `check_obs_protocol.py` 安静复跑 26.9 s，成本闸门以 `OFFLINE_SUITE_COST_REGRESSION` 退出 1。提交前重跑默认套件 `ALL_OFFLINE_CHECKS_PASSED`（36/36）；两项波内超预算后安静复跑，manifest 23.2 s、观测检查 20.9 s。上述重建单项不在该次默认套件中。

### 独立复审（2026-11-05）

审核者：不带本事项执笔历史的新上下文，审查提交 `bd6fb1d`、事项关闭条件、实现、回归及本机原始证据；结论 **通过训练来源范围验收**。审核者亲自复跑 `test_run_manifest.py`、`test_rebuild_gate.py`、`test_launcher.py` 均通过；默认套件 `ALL_OFFLINE_CHECKS_PASSED`（36/36，47.2 s），manifest 单项安静复测 18.6 s。另以临时 Git 夹具补核已跟踪 `record.py` 启动、T0 分类与材料往返，输出 `AUDIT_TRACKED_RECORD PASS`。

审核者核对三个豁免文件、受保护路径、完整列表与旧口径、二进制存根真实反例，逐例读取 `20261105-161938-c40984cb` 探针命令及 stdout，确认真实 fork 的 control 和六个注入结果；核对真实短训 manifest 与 checkpoint、归档拒绝现场。真实 run 复核仍为 `RUN_MANIFEST_PARTIAL`，repository、IsaacLab 和安装态 `rsl_rl` 三项必需来源为未知；输出的退出码不代表可重建。审核没有启动仿真或训练，也未重跑真实 fork、短训、训后评估或逐片复看视频。探针和 `sys.modules` 不证明完整依赖闭包、训练期无后续变化或原生加载；本次通过不代表短训模型合格、历史材料同源或已验证重建评级完成。评测时序、短训证据与重建评级分别由现存活跃事项承接。

## 证据引用

- `rl_exp/tools/verify/test_run_manifest.py`、`rl_exp/tools/verify/test_rebuild_gate.py`：真实仓回归及历史材料断言。
- `rl_exp/tools/verify/test_launcher.py`、`rl_exp/tools/verify/check_suite_shape.py`：独立进程与注入反证。
- 真实 fork 无训练复读：`E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\launcher_source_probe.py`；本次输出 `rl_exp/tools/diagnose/out/launcher_source_probe/20261105-105405-98d8ff34/`。探针输出及视频位于本机忽略目录，不随仓提交；复核需要本机保留证据或重新运行，脚本不能事后补造原始训练证据。
- 复读：`E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\test_run_manifest.py`；将文件名替换为 `test_rebuild_gate.py`、`test_launcher.py` 分别复读。
- 新补片复读：`E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\policy_scenario_video.py --out <新诊断目录>`；具体环境、首局逐步数据、子进程命令、日志与原帧位于 `ablation_harness/videos/training-provenance-dependency-scope/2026-11-04_16-12-57/model_0/scenario-diagnostic-20261104-a/`。
- 全套：`rl_exp\tools\verify\run_offline_checks.bat`。
- 真实环境但非真训练：`E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\obs_protocol_live.py --tasks Lizard2-Flat-v7 --envs 1 --viz none`。
- 新 run 与复核：`E:/IsaacLab/logs/rsl_rl/lizard2_v7/2026-11-04_16-12-57/run_manifest.json`、`checkpoints.json`、`rebuild_capture/rebuild_material.json`；`E:\IsaacLab\env_isaaclab\Scripts\python.exe -B -m rl_exp.tools.runrecord.manifest --verify E:\IsaacLab\logs\rsl_rl\lizard2_v7\2026-11-04_16-12-57`。
- 短训 checkpoint 的 robust 评测：`ablation_harness/results/locomotion_eval_v3/provenance-v7-20261104-161257/Lizard2-Flat-v7_short_robust_seed123/`。
- 短训 checkpoint 的录像和逐片观察：`ablation_harness/videos/training-provenance-dependency-scope/2026-11-04_16-12-57/model_0/`。

## 未覆盖边界

真实训练的 `after_env` 读数已取得，九宫格和新旧补片已抽帧；新诊断已核策略命令，原补片当时命令无法追补。独立审核已做但未通过，后续修改尚待重审；画面同步、核心支撑/摆动目标及来源归档仍有缺口，不能把训后流程写成完成。本次短训是用户明确批准的一次性脏树偏差，不改变版本方案对其他训练的约束；不得将零训练仿真构造或 trainer 桩称为训练 run。`after_env` 后延迟导入、不进入 `sys.modules` 的动态加载、被 `.gitignore` 忽略但实际读取的配置、搜索范围外的加载均未覆盖。T0 与 T1 之间受保护已跟踪路径和内容变化、声明收紧已有真实仓反证；不能将 T0 分类当整次训练的完整依赖结论。真实仓反例显示，同名未跟踪内容无摘要、T0 至 T1 或 T1 之后改变后，当前 `capture` 仍可采到后来内容并返回 captured；该判词只说明材料采集，不证明内容同源。来源摘要与评级属于 `work/active/verified-rebuild-rating.md`，不得在本项补造历史摘要；该风险在独立审核及交接前必须显式核对。未跟踪路径 `split_untracked` 原按日志/缓存子串排除，而新分类对非声明非 `.md` 路径阻塞；repository 分类已补保护合并，修复后真实仓回归已通过。
