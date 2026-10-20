# A 几何阶段交付计划调整

> 前段保留此前交付顺序的历史依据；手工步态前置按“用户定案：撤销手工步态交付前置”撤销。正式导出、写前拒错与独立导出切片审核的当前判定见末节；不代表整体 A/E、USD runtime 或正式采用完成。

## 适用范围

2026-10-19 用户要求更新计划，承接本轮“检查是否过多”的讨论。只调整隔离候选总项 A 与肩髋重构、限位 PD 专项的当前执行路由；计划正文仍归 `work/active/lizard2-body-drive-candidate.md` A4。本记录是计划调整依据，不是几何、动力学验收或关闭审核。

## 验收条件

- 三份活跃事项的下一步一致指向 A4，几何交付按回放、机身前移与滑动检查、候选交接推进。
- 复用已绑定证据和已有产物，只补变更或缺证；保留错轴、连接、限位、翻掌、穿地和自碰撞判据及仓库提交闸门。
- 承重 PD、有效限速、时间映射、运行时、躯尾协同、转向/恢复及最终比较仍有责任归属，阶段交付不自动关闭任何事项。

## 结果

支持相位记录已覆盖固定机身下的四肢组合与节点重参数化。旧总项与限位 PD 专项仍把接缝、两腿准备和相位方案列作当前动作，需按实际进展更新；这些历史动作不应成为每轮重复检查的前置链。

仓内已有 `local_path_view.py` 组合回放与根运动前提分析能力（提交 `e415911`）。本机 `rl_exp/out/lizard2_palm_combined_view_20261016_final/` 已有 `analysis.json`、`combined_side.gif`、`combined_top.gif`；分析声明源报告为支持相位报告。此次仅核对文件存在与声明，尚未复核其完整身份、动画内容或动作质量，所以计划要求先核对后复用交付，不称动画尚未生成，也不认定用户已经确认。

总项 A4 作为当前顺序唯一正文；两个专项引用它并保留各自技术责任。P4 明确由 B/C/D 接续，不再作为几何阶段交付完成条件；B/C 开始标定的输入、运行时、惯量和碰撞前提继续保留。几何阶段交付与事项关闭分开，所有状态保持 `in_progress`。

## 证据引用

- 总计划：`work/active/lizard2-body-drive-candidate.md` A4。
- 执行专项：`work/active/lizard2-palm-spatial-reconfiguration.md`、`work/active/lizard2-restored-limits-pd-validation.md` 5a/5b/6。
- 既有组合与支持相位：`acceptance/records/2026-10-16-lizard2-local-path-combined.md`、`acceptance/records/2026-10-16-lizard2-support-schedule.md`。
- 有限采样边界：`acceptance/records/2026-10-16-lizard2-local-path-quarters.md`“用户确认的验证范围”。
- 回放实现与本机产物：`rl_exp/tools/diagnose/local_path_view.py`，`rl_exp/out/lizard2_palm_combined_view_20261016_final/analysis.json`；本机产物引用不承诺入仓。

## 未覆盖边界

本轮不新增动作采样、不修改资产或控制代码，不选择物理周期或限速，不验证无滑移、承重或稳定性。新增根运动工程取值仍按专项集中提出；无变化检查可复用不等于可跳过真实缺陷。未完成动作、用户外观/动作确认及独立关闭审核继续保留，不以本记录存在视为审核通过。

## 用户定案：撤销手工步态交付前置

用户拍板：2026-10-19，明确已确认当前回放，同时指出仅脚板移动不能表达整机动作；授权撤销 A4 的手工步态回放、根前移和无滑移交付要求，只保留真实机构几何检查与具名候选交接。该确认只记录观看/确认回放，不推定独立候选外观批准、整体几何审核、动作有效性或正式采用。删除的是计划要求，不删除脚本、报告或历史失败/残差证据。

仅末端显示移动不能证明真实腿链正确，但真实关节轴、pivot、实体连接/随动、镜像、机械限位、翻掌/反曲/穿地和碰撞仍须有依据。现有几何样本可支持这些具名检查，不再要求手工开发步长、相位、周期、根运动或无滑移参考轨迹；它也不是 RL 需要复现的控制目标。整机协调与真实行走滑移仍由 `work/active/lizard2-family-landing.md` S6 的实际学习策略及接触协议验收，不因本次取消手工轨迹任务而被宣布完成。

### 原材料点残差的处置

约 0.80 mm 是[原根平移回放](2026-10-19-lizard2-a-geometry-replay.md#根运动与材料点读数)的持续接地材料点相邻采样位移，不是获准滑动阈值的超标判定。后续[接触边修正](2026-10-19-lizard2-contact-path-correction.md#本轮几何与材料点读数)已在同一根偏移和口径下将最大位移由 0.0007961633893181728 m 降至 0.000004727436951070913 m，并复读整个接地带的材料点，而非只验锚点。此前把旧残差再列为 A 当前待处理项是陈旧路由，应撤回。

本次不再次优化这些采样位移、不新增滑动阈值，也不称无滑移物理步态通过。修正前后读数、有限采样和源轨迹边界保留原记录；手工无滑移交付要求由用户撤销，不以忽略读数、放宽容差或改写历史判词代替处置。

### 具名几何候选分段交接

本次只复读已有文件及身份绑定，未生成资产、轨迹或物理结果。交付对象明确为 `palm_spatial` 的既有隔离几何候选；以下产物在本机，不承诺入仓。接收者须按用途选择身份，不能把惯量修正前的 USD 当当前动力学输入。

| 对象/用途 | 实际落点与身份依据 | 接收方及边界 |
|---|---|---|
| 几何源候选 | `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json`，SHA256 `59473f8c345dce48e8ee379c0972c928184f768be85afca948ac812a666fa6f8`；同目录 `palm_spatial.blend`、`palm_spatial.urdf`、`meshes/` 由报告 `identity.candidate_files_sha256` 逐文件绑定 | E 接树/轴/网格/真实构建来源；真实几何与连接仍按原代表姿态证据解释 |
| 几何检查与配置 | `rl_exp/out/lizard2_a_contact_delivery_20261019/report.json`，SHA256 `1d5ae02e0f7c4724144f1eb956c25f95899a53367603a0662c5196ae4052dc3b`；`identity`、`source_config`、`checked_pairs/excluded_pairs`、完整五轴 `legs` 及根偏移绑定；`completed_combined_loop=true`、`failure=null` | E/B/C 复用具名几何检查及来源，不据有限样本声称全 ROM 或可走 |
| 已确认回放及历史轨迹 | `rl_exp/out/lizard2_a_contact_delivery_view_20261019/analysis.json`，SHA256 `aac769420725b0242e7011563ccc010f598211c1ad6e4a6a0477ab89be36fa6d`；绑定侧/俯视 GIF、来源及图像哈希 | 用户已确认当前回放；仅诊断参考，不再作为交付动作或策略监督轨迹 |
| 当前隔离运行资产/配置 | `rl_exp/out/lizard2_b_inertia_repaired_20261019/registered_manifest.json`，SHA256 `7cb49fbe9d4ad4796148c4b80e5041066217ad277638837cb6ada9447032e19f`；同目录 `palm_spatial.usda` SHA256 `5f259d9e42d163ae60fa81f40aa9ec82bf4ad260dd976dfd0472deaea03a0b25`；URDF SHA256 `2c78117020458d5e7934219a2064bf7241430b81c2a736acd8cc0761c7a1461f` 与几何源相同 | E/B/C 按[惯量修正记录](2026-10-19-lizard2-spatial-inertia-repair.md)消费配置与新身份；此原 manifest 是固定基座诊断输入，自由静站/各 PD 覆盖须取其各自 manifest，不混用 |

本次实际核对：几何报告、回放分析和构建报告哈希与记录相符；构建报告所处目录的全部候选文件哈希与 `identity` 一致；回放绑定正确几何报告；隔离运行 USD/URDF 符合 manifest，运行 URDF 与几何源身份相同。已有几何检查结果按[接触边修正记录](2026-10-19-lizard2-contact-path-correction.md)复用；本次身份核对不是新增几何扫描或独立物理验收。

### 阶段判定与保留缺口

**当前几何样本与候选身份已具备向 E/B/C 分段交接的落点，本次完成交接整理，并记录用户回放确认及手工轨迹要求撤销。不能据此把整个 A 或任一 work 事项记为完成。** A 仍承担与 E 共用的正式导出/写前拒错及真实几何问题回修；D 的独立集成审核尚未由本记录代做。

- 正式导出声明/接口、五角色载体与实体质量惯量政策和写前拒错仍按[接线核查](2026-10-15-lizard2-e-spatial-runtime-wiring.md)及 A/E 原分工完成；隔离候选已有不等于正式导出链完成。
- 当前回放确认不代填独立外观批准或总项审核；镜像/连接等已有证据复用，后续真实几何变更须按影响重验。机械限位/禁区与未解释范围仍由专项维护，样本包络不变成安全盒。
- 全部关节默认 PD/已知载荷保持跟踪、有效力矩/速度边界、真实动作/观测/接触消费由 B/C/E 接续，不再要求重复手工抬落或原轨迹时间映射。RL 的实际动作性能及滑移归 S6，采用/训练另获用户授权。
- 所有原事项保持在办；本轮仅修正文档路由及证据指针，不修改资产、PD、上限、冻结配方或仿真代码，不删除工具，不启动物理测试/训练。

本轮 `check_work_docs.py`、`check_version_docs.py` 与本次路径 `git diff --check` 通过。独立新上下文核对六份修改文档，认可手工步态前置撤销、真实几何安全判据保留及具名分段交接的范围；该审查只证明本轮计划一致性，不复核本机哈希或构成 A/D 关闭审核。文件绑定由执行者上述实际复读提供，未把记录存在或格式通过当作几何验收成功。

## 正式导出与写前拒错切片验收

### 适用范围

用户拍板：2026-10-19，补齐正式 Blender→URDF 入口、真实保存源导出、写前拒错及独立导出切片审核；产物只写新隔离目录，不替换采用资产、不调 PD、不训练、不扩展到完整 E/USD runtime。用户另明确授权将 `generate_urdf.py` 与 `lizard2_stance_candidate.py` 中既有相关接线改动一并验收提交，其它在办文件保持不动。此前“正式导出/写前拒错仍未完成”的挂账由本节局部解除，不改写前段历史状态。

### 验收条件

- 正式目标显式为 `lizard2_palm_spatial`，五角色源树完整；加载保存的源 blend，重新生成真实 OBJ/STL，不复制参考 mesh 冒充导出。
- 调用方提供独立批准的 build 报告 SHA256，解析报告前先核批准摘要；源身份、完整骨树、neutral basis/pivot、共中心轴、限位、网格归属/几何及完整有限惯量字段均在创建或删除输出目录之前核验。
- 保留参考 link 的完整 inertial XML（origin 与六项 tensor）和 joint XML，不隐式套旧面积质量政策；仅独占创建全新 `rl_exp/out/` 子目录。
- 正负例经过真实导出验证/写入路径；真实缺陷回归修复前红、修复后绿；独立新上下文直接复核代码、日志、产物与磁盘几何，不仅核执行者总结。

### 结果

`rl_exp/blender/scripts/generate_urdf.py` 正式目标与 `rl_exp/blender/scripts/lizard2_stance_candidate.py:526` 的 `spatial_export_self_check()` 已落地。真实 Blender 5.2.2 LTS CLI 返回 0，旧 `--contract_self_check` 返回 0；自检完成 2 正例、31 负例，各负例均在写入前拒绝且对应输出不存在。独立未捕获 missingaxis 子进程返回 1，未因 Blender 关闭而吞错。保护清单的 502 个文件复算不变。

第一轮独立审核发现三个阻塞：报告只凭自身声明不能证明来源授权；NaN 质量及非有限 COM/RPY/tensor 未拒绝；首轮 CLI 与终版源码摘要不一致。已增加必填外部批准摘要、完整 finite/向量宽度/正质量检查，并在最终源码固定后重跑真实 CLI、自检与旧契约，保留全部日志。

| 绑定对象 | SHA256 |
|---|---|
| 最终 `generate_urdf.py` | `e350b8952c74e96ad9bbbe0303fc68d34e4b174c9106b9cbfaad4734ae3d56d3` |
| 最终 `lizard2_stance_candidate.py` | `dc4052d09fac73dbba81c7d5214e758843e355ce806ee4a9b877ab284ba47e0e` |
| 批准 `checkpoint_v3/build.json` | `59473f8c345dce48e8ee379c0972c928184f768be85afca948ac812a666fa6f8` |
| 源 `palm_spatial.blend` | `beeac4c09726260bf392a6ecc81a04ebcf9b54a210416493bbb2689c4909cdea` |
| 参考 `palm_spatial.urdf` | `2c78117020458d5e7934219a2064bf7241430b81c2a736acd8cc0761c7a1461f` |
| 新导出 `lizard2_palm_spatial.urdf`（CLI 与自检相同） | `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00` |

独立审核直接复算两套输出各 73 个声明工件；31 links/30 joints，唯一根 `base_link`，无重复 child、无环且全连通。所有 joint 与完整 inertial 属性等于参考；八个 meshless swing/abduct carrier 各 0.025 kg，总质量 72.0004 kg。额外 sentinel 经真实 writer 保留 `ixy/ixz/iyz=0.000001`，仅预期 `base_link` 惯量变化。36 个相对 OBJ 引用均存在且在输出树内，面索引一致；全部 OBJ 字节与参考不同，符合重新导出而非复制。

几何口径分开：Blender 内存对参考 OBJ 最大残差 `1.0999802789449242e-6 m`；独立最终磁盘 OBJ 对参考最大残差 `1.732051e-6 m`；STL 对对应 OBJ 最大残差 `8.481797e-7 m`，均在既定 `5e-6 m` 预算内。这些是有限导出一致性，不是全 ROM、连续安全域或物理无滑移证明。

修复前真实破坏测试分别报 `AssertionError: prewrite accepted forgedreport` 与 `AssertionError: prewrite accepted nonfinite_mass`；终版相同缺陷被真实验证路径拒绝。两份红例日志未记录旧源码 SHA，只能作为红→绿行为证据，不能称旧源码身份已独立认证。

终版独立新上下文审核 `a8c26648-0edc-4c11-8a0e-e05b57315f99` 直接读取代码、最终日志及工件，用 Python 独立核摘要、树、完整惯量、OBJ/STL 与负例输出缺席；审核结束再次复算两源码无漂移。判定：**批准 A 的正式 Blender→URDF 入口、真实写前拒错和独立导出切片审计完成，无本范围阻塞。** 本记录及路由回填不改变该已审代码/工件身份。

另一次独立完整 diff 核对 `c7aea8e7-fec4-4cec-a146-e26e996ed94d` 确认两文件旧 WIP 属于 shared/split/palm 接线，所需 `joint_names.py`、`binding.py` 已入库，无其它 dirty 文件依赖；不把静态核对外推成 split 真导出或 palm ROM 通过。旧 limit probe 新 `--blend` 仅在 `rl_exp/blender/` 资产树内有保护清单，不宣称任意外部源路径支持。

### 证据引用

最终本机工件与日志不承诺入仓：

- 正例/拒错清单：`rl_exp/out/lizard2_spatial_export_verified_20261019/self_check.json`；日志 `rl_exp/out/lizard2_spatial_export_verified_20261019.log`；sentinel 目录 `rl_exp/out/lizard2_spatial_export_verified_20261019_tensor_sentinel/`。
- 正式 CLI：`rl_exp/out/lizard2_spatial_export_cli_verified_20261019/export.json`；日志 `rl_exp/out/lizard2_spatial_export_cli_verified_20261019.log` 首行保留实际 argv、源码摘要与返回码。
- 旧契约及独立拒错：`rl_exp/out/lizard2_spatial_export_oldcontract_verified_20261019.log`、`rl_exp/out/lizard2_spatial_export_missingaxis_verified_20261019.log`。
- 红例：`rl_exp/out/lizard2_spatial_export_red_forgedreport_20261019.log`、`rl_exp/out/lizard2_spatial_export_red_nonfinite_mass_20261019.log`。
- 原 A/E 接口缺口：`acceptance/records/2026-10-15-lizard2-e-spatial-runtime-wiring.md`“正式导出交接核查”。

正式 CLI 复读须换未存在输出路径；下例 `replay` 是复读路径，不是本轮已执行目录：

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --python-exit-code 1 --python rl_exp\blender\scripts\generate_urdf.py -- --robot lizard2_palm_spatial --blend rl_exp\out\lizard2_palm_spatial_20261014\checkpoint_v3\palm_spatial.blend --build_report rl_exp\out\lizard2_palm_spatial_20261014\checkpoint_v3\build.json --build_report_sha256 59473f8c345dce48e8ee379c0972c928184f768be85afca948ac812a666fa6f8 --out_dir rl_exp\out\lizard2_spatial_export_replay
```

已有自检函数复读（仍须新路径；不调用脚本默认几何生成入口）：

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --python-exit-code 1 --python-expr "import runpy; n=runpy.run_path('rl_exp/blender/scripts/lizard2_stance_candidate.py',run_name='probe'); n['spatial_export_self_check']('rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/palm_spatial.blend','rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json','rl_exp/out/lizard2_spatial_export_check_replay',build_report_sha256='59473f8c345dce48e8ee379c0972c928184f768be85afca948ac812a666fa6f8')"
```

完整 `rl_exp\tools\verify\run_offline_checks.bat` 返回 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 54.2s)`。这是仓库离线回归，不替代上述 Blender 真导出或物理能力验证。

回填独立审核 `a096005d-8793-4989-91cd-a58e737d7ee4` 指出验证顺序表述与日志指针两处错误；已修正。新上下文复审 `6976d8b6-ea50-400d-9ff6-98450d8b8544` 直接核正文、四文档当前 diff 和两真实日志，批准回填，无新增阻塞；只审回填一致性，不替代或扩展前述代码/工件审计。提交前再次编译两源码并复算审核摘要一致，本次路径 `git diff --check` 通过；限定暂存本轮六文件后 `git hook run pre-commit` 返回 0，静态提交闸门通过。

### 未覆盖边界

正式导出入口完成不等于正式采用。E 须显式接收新 URDF 与 mesh 身份，转换新隔离 USD 并复验受影响 runtime/消费者，接回既有惯量主轴处理；本轮未执行。`palm_spatial_runtime.py` 仍保护原检查点，不删除 pin 来接受新导出。全部关节默认 PD/已知载荷、有效速度和真实动作权限、机械范围/碰撞缺口、外观批准及 D 集成审核继续原项在办；不关闭整个 A/E 或 work 事项，不修改已训 v3、不训练。其它 dirty 文件和早期调试工件保留，不随本次提交收走或删除。
