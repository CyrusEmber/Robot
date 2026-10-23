# lizard2 COM 接触候选速度修正独立审核

## 适用范围

由未参与本轮执笔的上下文审核当前 `baseline_metrics.py`、`judge_semantics.json`、`test_baseline_contract.py` 与 `HARNESS.md` 的差异，直接对照[执行记录](2026-10-23-lizard2-contact-com-calibration.md)、合成原数组、修前/修后日志。先读 `AGENTS.md`、work-ledger，按 FILEMAP/家族入口定位，并读取版本及 Git 收尾纪律。

范围仅为新 COM 杠杆臂 reader 与合成 writer/reader 校准。只读执行离线测试和内存复算，没有物理、训练、正式接触协议/S5 实装、标签发布、提交或推送；只写本审核记录。

## 验收条件

- 根因由共享函数签名与真实调用确认；同一消费者回归修前失败、修后通过。
- 新旧 reader/kind 的入口隔离，旧冻结语义及协议未变；新报告与 gate 使用相同的正确速度定义。
- 偏转、滚动、滑动等已知输入的刚体运动自洽，实际运动列进入真实 writer；缺列、无载与阈值边界不空验。
- 合成数值校准不提升为真实接触对、传感器/机体物理标定或完整协议交付。
- 评测台 minor 候选与机器人训练配方分开；最终标签、闸门及远端锚点不能用本次代码审核代证。

## 结果

**接受当前有限 COM 口径修正与合成校准实现。** 没有发现阻止此代码切片交付的缺陷。审核发现的 writer 覆盖过述已由实际夹具修复并增加破坏回归；正式协议、S5 和发布仍在范围之外。

### 根因、新旧路由与读数

共享 `diag_metrics.contact_point_velocity` 明确按 `v_com + omega × (point - com)` 计算，后两项参数是 COM、point；旧 `foot_point_velocity` 的实际位置参数顺序相反。新 helper 使用具名关键字纠正引用点，不是改变物理、阻尼或 PD。

检查 dispatch 及实际消费者：`baseline-criteria-contact-com-1` 只接新 `foot_slip_com_v1`，旧 reader 请求新 kind 拒为 invalid；新 reader 不含旧 foot_slip_v1。旧 helper/旧 kind 保留既有符号错误读数，旧 reader 的报告分支仍使用它；新 reader 的 report 与 gate 都调用新 COM 速度。默认 reader 未改变，既有协议不会默默迁移。

报告的 foot_slip_mps 是接触帧的切向速度均值，gate 则在 alive、contact>0、fraction≥min_load 的帧上判超过速度阈值的比例；二者共用速度公式，但均值、载荷筛选和超限比例不是同一统计量，不能拿报告均值直接冒充 gate 判据。

直接比较 HEAD 中所有六个旧 judge_semantics 块与当前内容，旧块结构及摘要均相同；仅追加新 reader 的九用例。十三个已跟踪协议文件逐字节（忽略 Git 换行转换）保持原内容。实际运行全部旧/新冻结语义，均符合原期望；旧滚动夹具仍读出约 0.2 m/s，原历史没有被校正覆盖。新 kind 明确新增其实际消费的 foot_contact 依赖。

### 已知运动与边界

从最终 JSON 原数组另用显式叉积独立计算切向速度，结果如下；数值不是机器人性能阈值。

| 已知合成输入 | 新切向速度 | 候选点首末迁移 |
|---|---:|---:|
| 固定点偏转 | 0 | 0 |
| 无滑动滚动 | 0 | 约 0.038 m |
| 纯滑动 | 约 0.1 m/s | 约 0.038 m |
| 反向平动叠加转动 | 约 0.2 m/s | 约 0.038 m |
| 纯法向下降 | 0 | 约 0.19 m，法向 |

偏转的 COM 位置为 radius×sin/cos，线速度是其时间导数，角速度与固定材料点条件相容。滚动 COM 平移与旋转在瞬时底点相消，而候选点本身沿地面迁移；不能把候选点轨迹导数当成同一材料点速度。反向平动与旋转应相加，旧错误恰会抵消。下降的位置/速度相符，仅末帧声明接触；接触标记和载荷是合成输入，没有力传感器真值。

本审核实际运行新回归，核缺 contact 列为 invalid、无受载样本为 fail；另在内存检查 contact 全零不空验，min_load 恰 0.05 时载荷帧纳入、0.049 时无样本并失败。速度恰阈值 0.1 通过、阈值 0.099 失败；超限比例恰 1/20 对 0.05 通过、0.049 失败。共同世界平移不改变速度。以上边界是现有严格 `>` 速度与 `<=` 比例规则，没有放宽原物理或策略判据。

### 实际复核与修前失败证明

读取真实 before 日志的消费者失败，核其哈希。又在内存令新速度 helper 暂时走原错误 helper，实际 `judge` 回归在 deflection 失败；恢复正确 helper 后同一回归通过。此操作未改写源文件。原完整 baseline 契约与 acceptance metrics 在本审核运行中通过；最终只改 fixture/writer 回归后，本审核再次实际运行全部五项新回归及所有旧/新冻结语义。

初版夹具先通过 build 建骨架，再直接覆盖 artifact 运动数组，不能证明这些运动值经过 writer。本审核指出后，执行者改为先生成运动列，以 series 逐帧传入 build，再由真实 BaselineFrames.add 写入；缺列用例仍明确在读侧删除列。

本审核用独立 spy 检查全部五种运动共 100 帧，六个运动/接触/载荷列进入 add 的值与回读数组逐帧精确相同。又核新增持久 writer 回归，在内存重建原“先写默认值后覆盖”的实际模式，断言在 foot_lowest_point 比较失败，最终夹具通过。不是仅阅读执行者日志；最终 `contact_com_calibration()` 的内存输出也精确等于 `calibration_writer_verified.json`。

## 证据引用

- [执行记录](2026-10-23-lizard2-contact-com-calibration.md)；永久入口 `rl_exp/tools/verify/test_baseline_contract.py`。本次核验的源/元数据 SHA256：

| 文件 | SHA256 |
|---|---|
| ablation_harness/baseline_metrics.py | `d797ff7d009fba64c79ff1631411e7791b19e9fac6344d2c7e310d9a355976be` |
| ablation_harness/judge_semantics.json | `de7721e6563e00401f20ba134f059ce7cdb7592480f82396665a2fbcd8f78f87` |
| ablation_harness/HARNESS.md | `c4a9a452176e41a089f539e703013c2076fad1123005249df484078a1e669dbb` |
| rl_exp/tools/verify/test_baseline_contract.py | `25c42d2e222b8051cd1029217f28fcf1686ac4b4b85956dc75d7005f90cfad63` |

- 最终原数组 `rl_exp/out/lizard2_contact_com_20261023/calibration_writer_verified.json` SHA256 `7a34f6391a43c0eac89027d56ee60fa70caba7f39d56c3a4d496ae1f069aff66`；较早 calibration.json/calibration_final.json 仅作中间过程，不作 writer 覆盖出口。
- 原失败日志 `rl_exp/out/lizard2_contact_com_before_20261023.log` SHA256 `9731d0d8bfe57b783bb88bd10fa10c87fb848091ac47c04cec8e5584a4dc2c41`；最终 writer 破坏/修复日志 `rl_exp/out/lizard2_contact_com_writer_contract_final_20261023.log` `2edb2eebb946a6f2f948d50a3886222dfefd758bb52fcf063da4e6a0846af144`，含 `DEFERRED_POST_WRITE_PATTERN_REJECTED`。日志只辅助，本审核实际复现了同类失败与通过。
- 本审核只读运行项目 Python 的 `-B rl_exp/tools/verify/test_baseline_contract.py`；最终五项 `test_contact_com_*`、`test_judge_semantics_are_frozen_and_hold` 和内存校准复算均已实际执行。未生成额外脚本、物理数据或校准输出。
- 写入本记录后 `check_work_docs.py` 为 `WORK_DOCS_OK (91 item file(s))`，本记录路径的 `git diff --check` 无报错；格式检查不代替实际审核。

## 未覆盖边界

新 reader 不是滚动分类器，也未验证真实最低碰撞顶点就是原生地面接触对。真实机体的偏转/滚动/滑动样本、地面接触位置/法向力、拖尾与异常主承重分组、阈值标定、新协议/锚点、正式 S5、D/E 整体和训练产物未由此交付。未重开已取消的试验。

HARNESS v1.11.0 是本轮待完成发布锚点的 minor 候选；本审核不声称标签已发布。候选树准备、本地标签、仓库闸门、以期望旧 SHA 快进 main 及推送原标签须由执行者完成并留真实结果；已审四文件以最终受检树为准，不能因本审核存在跳过闸门或改写已推历史。若实现、冻结块或证据再变，须针对变化复审。
