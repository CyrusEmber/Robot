# A 四肢几何回放与水平根运动候选

> 本记录保留原根运动和残差读数；原残差已有[后续修正](2026-10-19-lizard2-contact-path-correction.md)。用户回放确认及手工步态/根前移/无滑移交付撤销见[当前定案](2026-10-19-lizard2-a-delivery-plan.md#用户定案撤销手工步态交付前置)，以下历史未完路由不再作为当前动作前置。

## 适用范围

执行用户“继续执行”及总项 A4 的前两步，并整理可供 E/B/C 读取的几何候选。复用原支持相位报告的全部接受姿态，仅拟合并应用水平根平移；机身高度、朝向、全部关节角、原相位和采样位置保持不变。未运行仿真、求解新关节轨迹或改变资产。

## 验收条件

- 核对源报告、候选资产、FK 与已有回放的身份，提供侧视、俯视动画和可复读命令。
- 根位移在各原采样间隔累积，水平平移应用到全部实体及足掌标记；机身不借升降改变接地。
- 用相邻帧的同一材料顶点测水平位移，分别报告接触特征切换和该顶点是否在两帧均接地；不将换点或播放帧率冒称滑动速度。
- 保留残差与后续动作，复用因水平刚体平移而保持不变的地面高度及内部碰撞证据，不额外扫描 ROM 或扩大采样。

## 结果

### 回放与身份

原 `rl_exp/out/lizard2_palm_combined_view_20261016_final/` 的源报告和动画文件哈希匹配，侧/俯视 GIF 均为 109 帧；其记录的渲染源码哈希与当前提交不一致，因此未将其认作当前工具产物。已用本轮修改前的已提交工具，从原支持相位报告重出 `rl_exp/out/lizard2_a_fixed_replay_20261019/`，并在对话展示固定机身回放。

带根运动的交付目录为 `rl_exp/out/lizard2_a_geometry_delivery_20261019/`：

- `analysis.json`：候选及源身份、各腿具名完整关节轨迹、原姿态、根运动前提、实际应用的 `root_translation` 和全部图像哈希。
- `combined_side.gif`、`combined_top.gif`：原 109 个姿态的全机实体回放，包含接地/离地相位与实际根位移。
- `root_translation.png`：根位移与逐材料点间隔残差。残差用散点，避免跨越离地阶段连线。
- 各腿 `*_trajectory.png`：原身体坐标下的轨迹对照，世界偏移另取 `root_translation.offsets_m`，不得把该图当世界无滑移轨迹。

### 根运动与材料点读数

对每个相邻原采样间隔，在两帧均有几何接触的腿上，选后帧最低顶点的材料身份，读取同一顶点在前后帧的位移。根水平增量取各腿材料位移 XY 的负均值，逐段累积；Z 增量恒为零。保留每腿的原位移、施加根增量后的世界位移和前后高度。这个等权平移拟合只给可复读候选，不是关节求解、无滑移约束解或新步长批准。

原 109 帧对应 108 个间隔，根净平移为 `[0.05061389757115707, -3.872964449147531e-10, 0.0]` m，未出现后退间隔。共 240 个腿/间隔读数，其中 236 个所选材料点在前后两帧均处于原接地容差带，4 个不在，不能将后者当持续接地滑动；有 12 个最低顶点身份切换读数。

持续接地材料点的最大水平间隔残差为 `0.0007961633893181728` m，发生在 `c=0.046875` 的 lf、顶点 320；该例最低特征未切换，世界位移约 `[-0.000779740763404202, 0.00016087412587620364, -1.3229569907624583e-7]` m。原有限轨迹在多脚接地时需要的根平移不完全相同，等权水平平移不能同时消除这些残差。这里报告约 0.80 mm 的相邻采样位移，不把它冒称每秒速度、周期总滑动量或已经超出获准滑动阈值；尚无此阈值，原穿地容差也不作滑动阈值。

根 Z、朝向与关节姿态不变，因此原采样的各实体地面高度、四掌接地集合及内部相交关系保持不变，沿用支持相位记录的有限几何判词；本轮没有把它们重新计作扫描通过。世界轨迹每轮前进，GIF 重播时跳回起点是显示重置，不是闭合的世界运动。节点停速、根轨迹插值及加速度/力矩可行性仍未获物理验证。

### 相关验证

正常 `--self_check` 通过；对实际根运动函数分别破坏位移累积、固定高度和保留残差，三项均使同一自检失败。另用逐轴标量求和独立复算全部根增量/累计量，与输出一致，Z 偏移全部为零。最终交付的源/代码/图像哈希、各腿全部具名关节角、参数对齐及两份 GIF 的 109 帧均核对通过；人工查看了侧视与位移散点图。保留原源报告与产物，不覆盖历史输出。

### 交接

E/B/C 可从源报告读取同一候选、配置和原相位，从 `analysis.json` 的 `legs` 读取具名 `q_rad`，从 `root_translation.c/offsets_m` 读取对应世界根偏移；两者共享原采样参数。源资产、轴、网格及导出未改，不要求 E 为本次回放重建无变化资产。

这是一份带残差的几何候选，待用户动作确认及 A 对支撑段残差提出处理方案；未把它升格为无滑移合格周期。B 仍负责有效限速、时间映射和承重 PD，C 负责躯尾协同，E 负责实际消费链；各自标定前提保留。A/专项/总项继续 `in_progress`，本记录不替代独立关闭审核。

## 证据引用

- 计划：`work/active/lizard2-body-drive-candidate.md` A4；`acceptance/records/2026-10-19-lizard2-a-delivery-plan.md`。
- 原几何：`acceptance/records/2026-10-16-lizard2-support-schedule.md`；源报告 `rl_exp/out/lizard2_palm_support_schedule_20261016/report.json`，SHA256 `85ab07309f4eaca67fb2895b11f30616948d1d19d438640465910041926e0086`。
- 本轮实现：提交 `5ad7c30` 的 `rl_exp/tools/diagnose/local_path_view.py`，SHA256 `5b72235d71de6a8b50e3e580570f13ceeaa5da8c127184a57f7cf4a5bda7106f`；该提交的仓库闸门通过。
- 本机交付：`rl_exp/out/lizard2_a_geometry_delivery_20261019/analysis.json`，SHA256 `2f3cda357b22b5cebf950d4d744a5351710babdc0a962e699cdf6d609e55da9b`；报告绑定具体产物哈希，本机产物引用不承诺入仓。

从仓根运行，输出目录须不存在：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --self_check --break_test root_accumulate
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --self_check --break_test root_horizontal
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --self_check --break_test root_residual
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --root_translation --source_report rl_exp/out/lizard2_palm_support_schedule_20261016/report.json --output_dir rl_exp/out/lizard2_a_geometry_reproduce
```

负例预期退出 1；采集退出 0 仅表示回放/测量完成。当前入口仍支持不带 `--root_translation` 的固定机身回放。

## 未覆盖边界

没有新增采样、全区间证明、关节轨迹修正、世界滚动求解、滑动合格阈值或物理周期。约 0.80 mm 的残差仍需具名处置；不能靠忽略它、放宽穿地容差、升高机身或只移动画面标记宣告无滑移。未完成用户动作确认、实际驱动/承重、转向恢复或采用批准，B/C/E 和最终 D 的未完动作继续保留。
