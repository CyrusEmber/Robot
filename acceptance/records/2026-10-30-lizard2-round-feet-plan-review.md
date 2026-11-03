# lizard2 固定圆头足事项审核与范围纠正

## 适用范围

用户要求找到类似事项并审核，随后选择“球形或半球形圆头足”。用户进一步明确要求为生成文档，停止实施。本轮交付是圆足方案及事项交接，不是机体采用或训练批准。

## 验收条件

- 圆足方案有单独责任入口，明确固定足、视觉/碰撞、质量惯量及接口处理。
- 暂存双轴与其它替代研究，未完动作不消失；不把踮脚、脚板必要性研究追加为圆足前置。
- 审核指出的范围冲突、旧基线及测量接线问题有明确处理，未证能力不写通过。
- 如实记录助手误执行及停止状态，不将其参数、结果视为用户批准方案。

## 结果

### 事项审核

1. `lizard2-foot-design-tradeoffs` 的 F-round / F-convex 是最接近的入口，但原文要求保留双轴脚板，与替换目标冲突。F-round 动作同次迁入脚手架生成的 `lizard2-round-feet`，原处改为指针；双轴及 F-convex 未完研究保留、暂不实施。
2. “圆形”不足以定义候选。用户已选择固定球形或半球形圆头足，首版方案拟完整球体、原腕踝位置固定安装。具体尺寸与质量政策仍是设计输入，不把推荐参数当确认。
3. 替换必须同时处理视觉、碰撞与旋转自由度；仅取消动作不是去掉脚板。四足刚体名及固定关节合并会影响接触识别，动作、观测、默认角及驱动须同步并在实际加载后核对。
4. `lizard2-foot-plate-necessity` 仍指向退休 v2，对照基线过时；若恢复必要性研究，应重新绑定当前基线，不能把旧 v2 checkpoint 当新圆足的匹配对照。本轮圆足方案不以该研究完成为前置，也不据此改写旧研究结果。
5. 原脚板方案将主动踮脚设为硬验收，缺少明确用途依据；本轮收窄为可选专项。既有失败及测量缺口继续保留，不写成通过或证明脚板无价值。圆足同样没有优于脚板的性能结论。

### 助手越界实施与当前状态

助手将形状选择误解为立即实施，已在用户纠正前新增 `lizard2_round_feet.py`、`lizard2_round_feet_probe.py`、`test_lizard2_round_feet.py`，生成隔离 URDF/USD、预览并运行短时诊断。用户并未要求本轮实施；此为助手范围错误，不是用户批准的实现交付。三份代码文件未提交，本轮纠正后不再修改；输出与失败现场保留，不覆盖正式资产。

现场目录为 `rl_exp/out/lizard2_round_feet/candidate01/`。其中 `candidate.json` 保存源文件与候选摘要，`preview.png` 为零位几何示意，`conversion.log` 为转换日志；`probe01.json` 与 `probe01.log` 保存运行和终止帧。助手自定球半径0.08m、每足保留原质量1.0861kg，按实心球重算惯量，保留足端刚体名、改为固定连接；主动关节由30降为26，总质量72.0004kg。这些只记现场，不作为方案已核定参数。

已发生的有限诊断读取到26个动作、26个关节、90维策略观测和四个球形碰撞体；运行时场景自碰撞关闭。旧默认目标及PD下，1.46s触发终止，末根高约0.4547m，胸部净接触力非零；报告保留终止前帧。它不是站立通过，也不能证明圆足不能训练。后续动作与reset阶段未执行，拟议悬空补测在用户叫停后未启动。此前结构测试3项通过，不代替物理能力验证。

### 文档落点

- `work/active/lizard2-round-feet.md`：圆足方案、后续实施步骤与验收；状态为 open，本轮不启动实施。
- `work/active/lizard2-foot-design-tradeoffs.md`：圆足迁移指针、暂存研究及可选踮脚边界。
- `work/active/lizard2-two-axis-feet.md`：暂缓双轴实施，保留未完动作，不自动关闭。

### 后续用户决定：纳入已有文件并替代关闭旧方案

用户随后要求“误生成的文件也加入一下方案。然后关闭掉之前的脚板方案”。当前仅执行文件纳管与事项关闭，不改实现、不补运行、不训练。此前越界事实与失败读数不改写；已有文件转为方案内可复用起点，不等于参数核定或正式采用。

纳入文件清单：

| 落点 | 内容与当前边界 |
|---|---|
| `rl_exp/tools/diagnose/lizard2_round_feet.py` | URDF 球足生成、结构校验、预览与身份记录；尺寸与质量政策仍需设计复核 |
| `rl_exp/tools/diagnose/lizard2_round_feet_probe.py` | 独立配置的加载与控制诊断；已发生的受载终止保留，动作/reset 未完成 |
| `rl_exp/tools/verify/test_lizard2_round_feet.py` | 结构正例与拒绝原脚板/坏连接/上游改动的检查；不是行为验收 |
| `rl_exp/out/lizard2_round_feet/candidate01/lizard2_round_feet.urdf`、`meshes/` | 已生成候选及实际网格依赖 |
| 同目录 `lizard2_round_feet/lizard2_round_feet.usda` 及其依赖 | 已转换 USD；不接正式资产路径 |
| 同目录 `candidate.json`、`config.yaml`、`.asset_hash`、`conversion.log` | 身份清单、导入配置/缓存及转换现场；缓存不替代内容核验 |
| 同目录 `preview.png`、`probe01.json`、`probe01.log` | 几何预览与失败原始记录，保留原字节 |

复读使用既有入口，不新增执行：候选生成 `lizard2_round_feet.py --out <新的隔离目录> --radius <复核后的半径>`；转换复用 `lizard2_two_axis_convert.py --candidate <新URDF> --viz none`；诊断用 `lizard2_round_feet_probe.py --candidate <candidate.json> --usd <候选USD> --out <新的报告> --viz none`；结构检查为 `test_lizard2_round_feet.py`。以上均通过仓库 IsaacLab Python 环境运行，窗口/参数应按后续执行协议复核；此次只保存复读入口，不运行命令。

关闭范围为 `lizard2-foot-design-tradeoffs` 与其双轴实施事项 `lizard2-two-axis-feet`，按 superseded 由 `lizard2-round-feet` 接替，不能写 done。两项先置 pending_review，独立上下文核验后再归档。双轴驱动/几何/接线、F-convex、P-locked/必要性、接触及策略动作的当前责任指针归圆足事项交接节；必要性、接触及抬身专项不在本次关闭范围。活跃抬身/必要性事项的结构采用交接改指圆足，旧结果仍归原记录。

独立审核记录为 `acceptance/records/2026-10-30-lizard2-foot-plan-closure-review.md`。通过后两项移入 `work/closed/2026/`，保留原 id、置 superseded、接替者为 lizard2-round-feet；圆足与归档事项同次挂独立审核指针，最终落点由原独立审核者复核。

### 后续审核与方案优化：阶段隔离、转换绑定及接触参数

用户要求审核圆足方案，随后选择“仅优化方案”：本次只修订本记录与 `work/active/lizard2-round-feet.md`，不修脚本、不生成或转换候选、不运行仿真或训练、不提交。旧事项替代关闭的历史审核仍限于交接，不为本次新增的实施判据背书。

只读核对现有生成器、探针、候选清单及首轮报告，确认三个缺口：

1. **阶段耦合**：探针先执行保持，之后才显式 reset 和下发动作；保持终止会跳过后两项。方案改为独立记录接口检查与自由受载保持，局部受载失败不取消其它独立检查；共用前提失败则明确依赖阶段未执行。显式 reset 要从非默认状态检查恢复，动作目标送达和实际响应分开，不要求先手工站稳或走路。
2. **转换绑定未闭合**：生成器在转换前生成 `candidate_files_sha256`，不含后生成的 USD；探针核同目录、球体半径和关节数量并记录 USD 摘要，不能单独证明输出继承了预期物理属性。方案补入转换输入、网格、入口、配置及输出引用依赖的绑定，并另核实际加载的固定连接、几何和质量惯量。哈希一致是身份检查，不是转换正确性或物理能力验收。
3. **接触参数缺少政策**：生成器的 `round_foot_rubber` 只有视觉颜色，不能证明物理橡胶。方案允许先继承现有物理接触材料，但要求交代摩擦、恢复系数、组合规则和接触/静止偏移的来源，并核实际加载值；区分场景读回、后端运行值和配置声明。不默认新增标定专项，不把未测滑移或下沉直接归因于腿部 PD。

以上仅成为后续未完动作和关闭判据，现有代码没有因此修复，动作/reset 或承载能力没有新增通过证据。尺寸、质量、材料数值与运行预算仍待后续设计及执行协议复核，不补填未经确认的参数。

本次审核阶段运行 `E:/IsaacLab/env_isaaclab/Scripts/python.exe -B -m unittest rl_exp.tools.verify.test_lizard2_round_feet -v`，现有结构测试 3/3 通过，仅支持固定连接、足形替换和上游结构契约，不覆盖上述三项缺口。

### 用户后续授权：先改双轴骨架与圆足外形

用户纠正实施顺序为“先换骨骼”，指出相对双轴候选应移除八个自由度，并选择“骨架与圆足外形一起改”。本阶段仅生成隔离 Blender 候选，临时球半径沿用 0.08 m 用于预览；不转换 USD、不仿真、不训练、不修改正式配方。此前“不提交”的限制本轮保留，未提交或推送。

**自由度口径纠正**：双轴候选为 34 个活动轴，每足原轴及 lateral 各一轴，圆足移除共八轴后为 26。旧 candidate01 由正式单轴 30 轴母本移除四轴得到同样的 26；数值终点相同，但不是从当前双轴骨架生成，不能冒称本次骨架落地。根刚体对应的一根 Blender 骨骼不计入活动轴，浮动基座的六个自由度也不计入该关节数。

新增持久入口 `rl_exp/blender/scripts/lizard2_round_feet_candidate.py`，输入逐字节核为双轴候选 `rl_exp/out/lizard2_two_axis_20261029/candidate01/lizard2_two_axis.blend`，SHA256 `4b204706e871220aaec4a6a404e96f99c18a2c6c984771c1c186d2b7ecea6f42`。执行命令：

```bat
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_round_feet_candidate.py -- --source rl_exp\out\lizard2_two_axis_20261029\candidate01\lizard2_two_axis.blend --out rl_exp\out\lizard2_round_feet\skeleton02 --radius 0.08
```

复读必须改用新的 out 目录，禁止覆盖现有现场。脚本删除四个原腕踝骨及四个 lateral carrier 骨，同时移除绑定旧足的八个网格对象；球心取原腕踝枢轴世界位置，新球体直接刚性绑定对应肘/膝骨，无独立足端活动骨骼。保留其它骨链、中立姿态及全部其余 evaluated 网格，不重新摆腿。

实际 Blender 5.2.3 LTS 执行并保存重开：

- 输出 `rl_exp/out/lizard2_round_feet/skeleton02/lizard2_round_feet.blend`，SHA256 `4e3073d1389db9875a0dd4db4e7ec4ef7a56b5231d7df6fc12edc4c57660cf07`；`build.json` 保存源/输出/脚本身份及原始检查读数。
- 骨骼总数 35→27，即根骨以外 34→26；八条目标骨骼均不存在，四球体分别绑定 lf/rf_elbow 与 rl/rr_knee。
- 全部保留网格的 evaluated 顶点在修改后及保存重开后最大位置差均为 0 m；其它骨骼父级和中立框架一致。
- 对四足逐一把父骨误设为 base_link，四个破坏例均被绑定检查拒绝；恢复后重新核验通过。对应肘/膝施加 ±0.1 rad，球体实际 evaluated 顶点与父骨刚体变换最大差约 `2.74e-7 m`，小于本检查 `1e-5 m` 数值容差；该检查不验证生物力学轴向或可达包络。
- 源 blend 摘要保持不变；旧 candidate01 与正式资产未改。另从保存候选渲染 `side.png`、`oblique.png` 预览，不改写 blend。

本阶段的活动骨架计数和刚性绑定不构成 URDF/USD 活动关节数、接触刚体或质量惯量验收。后续导出应从本次骨架适配，若另保留固定足端刚体用于接触采样，固定连接仍为零自由度；不得复用旧单轴导出器产物冒充同源输出。圆足尺寸、质量惯量、材料、转换绑定、动作/reset 与受载验证继续未完。

### 后续授权与实际导出：URDF、USD 与惯量主轴修正

用户要求继续下一步，并选择“保留质量作诊断”：球半径暂用 0.08 m，每足保留原足质量 1.0861 kg，质心移到球心，实心球惯量 `I=0.4*m*r²=0.002780416 kg·m²`；这是诊断假设，不代表材料或实物设计核定。本阶段授权导出及转换，不启动环境、物理步、训练或正式配方变更，延续不提交限制。

新增 `rl_exp/blender/scripts/lizard2_round_feet_export.py`。它不是仅复制旧 URDF 后声称来自新骨架：核骨架/build/双轴来源链，逐项比对原正式 blend 的全部骨骼父级与框架、上游 evaluated 网格顶点与拓扑，再将原 blend 的 visual/collision 网格与正式 OBJ 对应，验证新骨架保留部分一致后复用已核上游字节和功能轴。四球绑定、中心与半径另核；26 轴逐一激励 0.07 rad，与共享 FK 的全部骨枢轴及网格顶点比较。错误绑定和偏移球心的八个破坏例均拒绝。

实际导出 `rl_exp/out/lizard2_round_feet/export03/`：31 links、26 revolute、4 fixed mounts、28 个上游 OBJ；总质量 72.0004 kg。原 blend/正式网格最大误差 `9.49419e-7 m`，新骨架保留网格误差 0 m，逐轴 FK/几何最大误差 `1.18066e-6 m`，均在本检查 `1e-5 m` 容差内。四个固定足刚体保留采样身份，不增加活动轴；相对双轴候选仍为 34→26。

转换复用 `lizard2_two_axis_convert.py`；成功路径实际为 `export03/lizard2_round_feet/lizard2_round_feet.usda`，不是 export03 根下同名文件。转换配置保留固定关节、不固定基座、拍平 31 个刚体。转换时 self_collision=true，后续环境是否关闭必须另读运行设置；未启动环境，不能将导入设置当受载验证。

新增 `rl_exp/tools/diagnose/lizard2_round_feet_usd.py` 只读核 USD 层属性并保存依赖绑定。原始转换产物的 26 活动轴、四固定连接、局部框架/轴/限位、全部质量与质心、四球 visual/collision 半径和归属通过，但 **lf/rf_elbow、rl/rr_knee、tail1_pitch 五个完整惯量张量失败**：前四个最大误差约 0.025119 kg·m²，尾部约 0.105516 kg·m²，远超 float32 舍入预算。该问题为已有导入器主轴四元数方向问题，不是球足质量重新估计。

显式复用 `palm_spatial_inertia.py` 的 `_principal_repair` / `repair_fresh_stage`，只在共轭能恢复 URDF 完整张量且其它质量/质心一致时另存修正副本。五处均 `xyzw [0.5,0.5,0.5,0.5] → [-0.5,-0.5,-0.5,0.5]`；撤回五处后完整 layer 与原始相同。首个修正输出被保存后完整字符串检查发现 Windows 文本换行改变了 USD doc 字段，失败现场保留；改为不转换换行后另出 repaired02，未覆盖原始或失败副本。

**当前有效 USD 仅为 `rl_exp/out/lizard2_round_feet/export03/lizard2_round_feet/lizard2_round_feet_repaired02.usda`**。修后全部 31 个刚体质量、质心、完整惯量、连接和几何检查通过；质量、固定连接与惯量三种匿名覆盖破坏例均拒绝，清理覆盖后恢复一致。依赖无 unresolved，文件绑定在检查前后不变。初始 authored body 世界位置不代表求解后的关节姿态；本阶段没有 backend 读回、加载后 FK、接触材料或承载判定。

| 工件（相对 export03/） | SHA256 |
|---|---|
| `lizard2_round_feet.urdf` | `88ba19fe7b9e50b59264e4490f1c86f00a1a85593edaebc1496d1bb218c2b398` |
| `candidate.json` | `e460c153dcf1cc0fc5bc45fe3d198bc79b5ec392a9b8e588fd781929b1b5f5ca` |
| `lizard2_round_feet/lizard2_round_feet.usda`（原失败输入） | `1bea5e7442d64235fff5d1d507ddf49669de25c7467a1942134d6cdc5b3677b7` |
| `usd_audit_original03.json`（最终源码修前回归） | `6c5a65979bbd4270dd06cd2bfe813d9ea42608a3816087d85eb65337177a8d36` |
| `lizard2_round_feet/lizard2_round_feet_repaired02.usda` | `0e6b86c58e083987718315f5a3f385466c5248fe1544cbb1a5f729a96600a971` |
| `lizard2_round_feet_repaired02.repair.json` | `c10985e797c6ba4101567d4d8a9649c13599a9ed6d9dd4e95ca8574d3abe07ad` |
| `usd_repair_check02.json` | `ef51dc7559132fb8c095363bae880b8d460db0227814910d44d44fe14490f833` |
| `usd_audit_repaired02.json` | `bd7974c1c34d86ff117a066702caa96f3c217cbc697e59ea5a0c2adc9963a0a7` |

复读入口（须为尚不存在的输出名）：

```bat
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_round_feet_export.py -- --out rl_exp\out\lizard2_round_feet\export04
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\lizard2_two_axis_convert.py --candidate rl_exp\out\lizard2_round_feet\export04\lizard2_round_feet.urdf --viz none
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\lizard2_round_feet_usd.py --output rl_exp\out\lizard2_round_feet\export03\usd_audit_original04.json
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\lizard2_round_feet_usd.py --usd rl_exp\out\lizard2_round_feet\export03\lizard2_round_feet\lizard2_round_feet_repaired02.usda --output rl_exp\out\lizard2_round_feet\export03\usd_audit_repaired03.json
```

前两条另建导出/转换，后两条只复核本次工件；原始审计预期退出 1，修后审计预期退出 0。显式重做修复另传 `--repair <原USD同目录下新usda路径>`，复用已保存失败审计作历史绑定。当前审计默认绑定本次历史 `usd_audit.json`，不是全新目录的一键构建入口；跨目录复用须先明确其历史绑定及输出政策，不用已有文件冒充新审计。

本阶段结构单元测试 3/3 通过；UTF8 模式全仓离线检查 37/37 通过。导出器内嵌八个几何破坏例及 USD 审计三类覆盖破坏例均实际运行。闸门通过不等于独立关闭审核或运行能力通过；圆足 work 保持 in_progress，阶段分离的动作/reset、接触参数读回、加载后姿态及受载检查尚未执行。

### 后续用户授权：加载后核对活动轴、动作与显式 reset

用户明确要求“核对一下26轴、动作与 reset”，本阶段不执行接触测试、站立保持或训练。扩展已有 `lizard2_round_feet_probe.py` 的 `--interface_only --usd_audit` 模式；保留旧 CLI，运行前核 candidate 及通过的修正 USD 审计的全部 89 项依赖摘要，不混用未修正 USD。旧模式保持阶段早停仍会跳过后续阶段，本次绕开该路径，不声称已修复旧模式受载流程。

实际运行两次无物理步的原生接口检查，证据分别为 `rl_exp/out/lizard2_round_feet/interface04/` 与 `interface05/`。首轮 optional PhysX getter 返回 Warp array，错误使用 tensor 转换，已在原始报告保留错误，不将其认作后端目标成功；第二轮使用已有 `wp.to_torch` 方式，并将后端目标全向量比较纳入每个工况，最终结果如下：

- 从 candidate URDF 提取的 26 个 revolute 名称与实际加载的全部活动关节、动作映射集合一致，无重复、无遗漏。实际 legs term 16 维、spine term 10 维；报告保存 global/local/joint index、scale、offset、clip，不假定动作顺序等于关节顺序。
- 零动作、全部 26 轴各 ±0.01 rad、reset 后零动作共 54 例。每例完整保存 raw、processed、command target、PhysX target。映射/缩放/偏移/裁剪及所有其它目标列一致，实际后端 DOF 名称顺序另核；54/54 后端最大误差为 0 rad。本项验证指令通道，不宣称关节实际运动或受载响应。
- 在 reset 前真正写入非默认根位移 `[0.02,0.01,0.05] m`、根速度各分量 `0.03`、全部关节交替 ±0.01 rad 偏移及 `0.02 rad/s` 速度；动作 current/previous 均为非零，episode_length=7。写后读回验证，原始 altered 快照保留。显式 `env.reset()` 一次后，根位置（含 env origins）、xyzw 姿态及速度、全部关节默认位置和速度、current/previous action 与 episode_length 恢复检查通过。
- **reset 不是清除全部驱动目标**：本 fork reset 后 processed 和 command/backend target 仍有旧值，其中 tail3_pitch target 为 `0.009999999776482582 rad`。报告保留此快照，不把它写成全部控制状态清空；随后明确处理并下发零动作，完整 buffer/backend 均恢复零动作目标，残差 0 rad。此阶段没有修改框架 reset 语义。调用者若 reset 后不处理新动作就直接推进物理，旧目标风险仍存在；本次没有验证或修改训练自动 reset 时序。
- `env.step=0`，加载时物理计数 0，加载后物理步增加 0；共两次 forward（扰动后与 reset 内部），不属于动力学演化。没有要求或测试接触、支撑、自由受载保持、策略或训练。

最终证据 `rl_exp/out/lizard2_round_feet/interface05/probe.json` SHA256：`c47d9af79eda049f5dfbf46ca6a842195afc25e358663ea96bbd84f88630e419`；同目录 `native.log` 保留原生启动与检查日志。首轮 interface04 保留，未覆盖。复读须换新 out，命令：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\diagnose\lizard2_round_feet_probe.py --candidate rl_exp\out\lizard2_round_feet\export03\candidate.json --usd rl_exp\out\lizard2_round_feet\export03\lizard2_round_feet\lizard2_round_feet_repaired02.usda --usd_audit rl_exp\out\lizard2_round_feet\export03\usd_audit_repaired02.json --interface_only --viz none --out rl_exp\out\lizard2_round_feet\interface06\probe.json
```

接口离线测试覆盖完整/缺失/重复映射、错路由、非有限目标、裁剪及错误后端向量；checker 失效的内存破坏例实际使测试失败，恢复后四项测试通过。此记录不是总体圆足关闭审核；接触和正式训练接入均未因本次完成。

本次完整离线套件未全绿：`check_suite_shape` 报 `test_eval_record.py` 新增解释器子进程未在 SPAWN_ALLOWED 声明，1 项失败、10 项跳过；其余已执行项通过。该文件不在本次圆足修改范围，未为通过检查而修改它或放宽闸门。本轮接口四项专项及实际原生核对通过，与全仓阻塞分开记录。

## 证据引用

- 本轮用户的圆头足选择，以及“先别改了，我的要求是生成文档”的范围纠正。
- `work/active/lizard2-foot-plate-necessity.md`、`work/closed/2026/lizard2-v2-foot-authority.md`：旧必要性口径及取消动作与移除结构的区别。
- `rl_exp/versions/lizard2/FAMILY.md`、`rl_exp/versions/lizard2/main/v6/main_params.yaml`：当前正式资产及足端接线。
- `acceptance/records/2026-10-30-lizard2-foot-control-first-trials.md`：双轴已执行样本及未通过边界。
- 用户本次“优化”及“仅优化方案”选择：只补实施安排与验收边界，不扩大为代码修改或物理执行。
- `rl_exp/tools/diagnose/lizard2_round_feet.py` 的视觉材料与转换前清单生成、`rl_exp/tools/diagnose/lizard2_round_feet_probe.py` 的输入核对和保持/reset/响应次序：本次缺口的源码依据。
- `rl_exp/tools/verify/test_lizard2_round_feet.py`：本次运行的结构正例与破坏检查，非接触或控制行为证据。
- `rl_exp/blender/scripts/lizard2_round_feet_export.py`、`rl_exp/tools/diagnose/lizard2_round_feet_usd.py`、`rl_exp/tools/diagnose/palm_spatial_inertia.py`：本次导出、USD 审计及复用的受限主轴修复入口。
- `rl_exp/out/lizard2_round_feet/export03/` 的 candidate、conversion、原始/修正 USD 及审计/修复 JSON：本次实际导出和缺陷回归现场，仅为本机工件。
- `rl_exp/blender/scripts/lizard2_round_feet_candidate.py`、`rl_exp/out/lizard2_round_feet/skeleton02/build.json`、同目录 blend 与两张预览：本次骨架实现与实际执行结果，仍为隔离候选；本机工件不承诺入仓。
- `rl_exp/out/lizard2_round_feet/candidate01/candidate.json`、`probe01.json`、`probe01.log`：误执行现场；本机工件不承诺入仓，不作为正式方案验收。

## 未覆盖边界

本记录是执笔记录，不是独立关闭审核；关闭状态以单独的独立审核记录及事项落点为准。没有训练或步态评测，没有核定实物驱动、球足尺寸、材料、姿态或性能优劣。已有代码与候选已按用户要求纳入圆足方案；后续已执行授权的 Blender 骨架、隔离 URDF/USD 导出及主轴修复核验，未启动环境物理步，本轮不提交或推送。
