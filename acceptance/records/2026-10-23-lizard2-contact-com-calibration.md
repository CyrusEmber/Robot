# lizard2 接触口径前置：COM 杠杆臂修正与合成运动校准

## 适用范围

用户批准新候选从头训练的预算后要求继续正式接入。本轮从接触协议的测量前置开始，发现并复现评测消费者的真实符号错误；不改变当前 PD、位置/零速度目标、限速决定或已训 v3，不增加物理运行或训练。预算仍取[接口方案](2026-10-23-lizard2-training-interface-plan.md)中的用户决定。

本轮交付是具名新测量 reader 及已知刚体运动的合成 writer/reader 校准，**不是**新机体正式接触协议、传感器物理标定或 S5 全部完成。评测台代码基线按自身规则升 minor；与机器人配方版本分开。

## 验收条件

- 修改前通过实际消费者复现错误，修正后的新入口通过同一回归；不能仅用修后通过代替覆盖证明。
- 材料点世界速度为 `v_com + omega × (point - com)`，以显式关键字传参；地面切向分量与法向下降分开。
- 通过真实 BaselineFrames 和 judge 对照固定点偏转、无滑动滚动、纯滑动，以及旧公式抵消掉的滑动反例；报告读取与 gate 使用同一新算式。
- 旧 reader、旧 kind、旧协议文件及旧冻结语义不变；新行为只能由新身份访问，缺列、无受载样本和边界条件均核。
- 合成已知输入、几何候选点和原生接触对真值分开，不将本次结果升级为当前机体真实滚动/滑动能力或已批准策略性能阈值。

## 结果

### 根因与责任层

共享函数 `diag_metrics.contact_point_velocity` 的后两项参数为 `com_pos_w, point_pos_w`。旧 `baseline_metrics.foot_point_velocity` 却按 `foot_lowest_point, foot_com_pos` 调用，实际使旋转项符号反向。修改前只读复现：质心向 +x 走 0.1 m/s、绕 +y 转 1 rad/s、候选点在质心下 0.1 m，理论接触点静止；共享函数返回 0，评测返回 +0.2 m/s。

这不是缺少阻尼、真实摩擦变化或候选 PD 不足。调用检索显示问题在离线 baseline 测量路径，本轮未改训练奖励或共享正确函数。旧测试覆盖了纯平移或纯转动的速度范数；旋转项单独反号不改变范数，因而漏掉平移与旋转相消/相加的错误。

### 新旧身份

新增 `foot_point_velocity_com_v1`、`foot_slip_speed_com_v1`，用显式关键字向共享正确函数传 COM 与候选点。新增 kind `foot_slip_com_v1` 和 reader `baseline-criteria-contact-com-1`，报告和 gate 都使用新速度；新 kind 还声明了自身实际消费的 `foot_contact` 列。旧 `foot_slip_v1` 及所有旧 reader 仍走原路径，旧 `judge_semantics.json` 各块的内容/摘要不变，仅追加新身份与九个具名用例。

旧 reader 请求新 kind 会被拒绝，不能借一个新 kind 名字默默改变旧判分器。相同 `foot_slip_mps` 字段必须结合 judge 身份解读；既有含非零平动与转动的旧值不能作为已校正结果，后续重评必须保留新的协议/reader 归属，不覆盖旧判词。未改任何已锚定协议、protocol_anchors 或机器人配方。

### 合成校准与回归

所有夹具都是手工可推导的理想刚体输入，不是仿真 rollout。两只具名 toy feet、20 帧、0.02 s；真实 BaselineFrames 写出完整契约数组，再由实际 judge 消费。候选点位置、COM 位置、线/角速度、接触标记和载荷分数均可复读。下降夹具位置与速度一致，仅末帧声明接触；这些接触/载荷是合成输入，不代表实际力测量。

| 已知输入 | 新切向速度 | 区分依据 |
|---|---:|---|
| 固定材料点偏转 | 约 0 m/s | 候选点世界位置固定，COM 绕它运动 |
| 理想无滑动滚动 | 约 0 m/s | 候选点沿地面迁移约 0.038 m，瞬时材料点速度仍为零 |
| 纯滑动 | 约 0.1 m/s | 平动无角速度，材料点沿地面移动 |
| 反向平动与转动叠加 | 约 0.2 m/s | 旧错误算式可相消成零，新算式检出滑动 |
| 纯法向下降 | 约 0 m/s | 只计切向分量，末帧接触不被记作切向滑动 |

这组已知轨迹区分了原点/候选点迁移与瞬时材料速度，不是任意复杂接触下的通用滚动分类器，更不承诺整个接触面无微滑。最低网格候选点仍存在几何离散和接触配对不确定性。

完整链回归先让新入口沿用旧算法，固定点偏转实际失败（约 0.1943 m/s）；修正关键字传参后通过。另核共同世界平移不改变速度、速度恰在阈值与略超阈值、缺 contact 列拒判、无受载样本不空验，以及旧 reader 的 0.2 m/s 历史读数仍保留。九个新语义用例覆盖相应成功/失败/invalid 分支；用例里的数值仅为测量回归阈值，不是新机器人的性能验收线。

原完整 baseline 契约运行通过，包含原所有冻结 reader 及既有 acceptance metrics；最终夹具更新后五项新回归和所有新旧冻结语义再次通过。新增 writer 回归实际拒绝“先写默认值再覆盖数组”的旧夹具模式。本轮没有新增默认离线套件条目。

### 发布检查

最终代码提交 `07e5d2f3cf4e5de302b4c28b57f6c9e27cc6e23d`，本地标签 `harness-v1.11.0` 精确指向同一提交；先以明确四文件索引树准备内容寻址提交对象和标签，再用相同元数据正常提交，原 pre-commit 钩子完整执行，未绕过检查、移动标签或改写历史。

首次离线套件在标签建立前因缺少版本锚点停止，其日志保留为 `rl_exp/out/lizard2_contact_com_20261023/offline_suite_before_tag.log`。准确标签建立后，完整套件 `37/37` 通过，日志 `offline_suite.log`；提交前及正常提交时原仓库钩子均通过，日志 `precommit_code.log`、`commit_code.log`。此为仓库一致性与离线行为验证，不代替物理或策略验收。远端发布以实际 Git 远端状态为准。

## 证据引用

永久入口为 `rl_exp/tools/verify/test_baseline_contract.py`，新增合成校准导出模式；原始数组与新旧消费者结果位于本机 `rl_exp/out/lizard2_contact_com_20261023/`，不承诺随仓分发。首次导出 `calibration.json` 及 `calibration_final.json` 是中间版本；独立复核指出旧夹具先建 writer 骨架、再直接覆盖运动数组，不能据此声称运动值经过 writer。已改为以 series 逐帧传入真实 BaselineFrames.add，最终使用 `calibration_writer_verified.json`，SHA256 `7a34f6391a43c0eac89027d56ee60fa70caba7f39d56c3a4d496ae1f069aff66`，与前轮最终运动值/判词完全相同。旧文件未覆盖，既有数值回归不冒充 writer 覆盖证明。

- 修改前失败：`rl_exp/out/lizard2_contact_com_before_20261023.log`，SHA256 `9731d0d8bfe57b783bb88bd10fa10c87fb848091ac47c04cec8e5584a4dc2c41`。
- 修正后初次通过：`rl_exp/out/lizard2_contact_com_after_20261023.log`；四项回归和冻结用例：`rl_exp/out/lizard2_contact_com_after_final_20261023.log`；真实 writer 修补后复跑：`rl_exp/out/lizard2_contact_com_writer_verified_20261023.log`。
- 原完整契约：`rl_exp/out/lizard2_contact_com_contract_20261023.log`，SHA256 `bb870bfaae75b4c9078d20140892b365ef9a7d2532d7d909b7f24a9614942d02`。
- 最终 writer 破坏/修复与五项回归：`rl_exp/out/lizard2_contact_com_writer_contract_final_20261023.log`，SHA256 `2edb2eebb946a6f2f948d50a3886222dfefd758bb52fcf063da4e6a0846af144`。
- [独立审核](2026-10-23-lizard2-contact-com-review.md)接受这次有限修正；审核实际复跑消费者、全部新旧冻结语义及 writer 破坏对照，不代表真实物理标定或正式协议交付。

从仓根使用项目 Python；导出目标必须不存在。复读不启动 Kit：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_baseline_contract.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_baseline_contract.py --contact-calibration rl_exp/out/contact_com_replay/calibration.json
```

## 未覆盖边界

原生地面接触对的位置/法向力、当前掌跖几何下偏转/滚动/滑动的真实物理样本、拖尾与异常主承重的分组和幅值标定、具名新协议及固定策略性能判据仍未完成；不因新 reader 存在而关闭接触协议事项。已有隔离接口运行核验按[运行记录](2026-10-23-lizard2-interface-runtime.md)和其独立复核复用。

正式配方/新版本/资产采用、D/E 整体及 S5 接入和训练产物仍没有由本记录交付；不会用旧 v3 或旧脚本替代新候选训练。6000 迭代预算已获用户批准，不再次询问。原取消限速/限矩/对称复测和手工动作性能前置的决定保持。
