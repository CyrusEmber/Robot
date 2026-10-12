# Lizard2 P2 四肢同步、降低掌体：隔离实生成

## 适用范围

用户批准四肢同步，并把脚板降低至接近腕/踝球底；连接方式此前已认可，其它骨段比例、角度及掌形外轮廓已获视觉认可，不等于物理验收。当前仅 P2：`rl_exp/blender/scripts/lizard2_stance_candidate.py` 增加显式 `--all_legs --sole_at_ball_bottom`；降低要求 `--palm_shape claw`。默认 halfpad 与既有两肢 claw 语义保留。事项仍 `in_progress`，模型 **PROVISIONAL_SAMPLE_NOT_ACCEPTED**；数值位置/网格验收容差未获批准。

实施路线为就地参数化六截面、保留根 cap、从真实 evaluated 球底计算掌体 Z 位移，再用世界 Y 反射构建右肢；复用原构建、绑定、测量、逐关节诊断和负例，不新增框架、依赖或 helper 文件。仅首次截面中心留 pivot，后五截面降低；不是整个掌网格平移。前向仍 +X，掌骨 head/tail 水平不变，根部下降过渡是连续封闭实体；不宣称所有 cap 共用同一高度。

右前/右后分别来自实际构建左前/左后，`MIRROR_Y=0`，反射直接烘入 mesh 顶点并反转面绕序，保持对象正 determinant。保留原右侧对象和球名字；用源真实 roles 在改名前映射，不复制同名球。镜像轴按轴矢量反射，不把左 theta 原样用于右世界方向。全部重建腿的非零源 pose basis 清零，躯干不动。没有驱动、URDF/USD、转换器、正式采用或训练变更。

## 验收条件

本轮交付是新隔离四肢 neutral、最多六张真实图、24 档单关节 evaluated 原始测量、真实消费者及负例、旧基线保护。`-10/0/+10°` 仅获准用于肘/膝、腕/踝诊断，不是 ROM 或物理工况。

掌根真实 cap 顶点中心、骨头/骨尾与下段实体端环连接在共同世界坐标系核对；逐顶点运动另与独立刚体变换对拍。球底与掌体底的中立几何相等是用户要求的摆放选择；实现中的 float32 算术预算不是批准位置容差。保存后重新打开新 neutral，比较旧 claw 的所有左骨 head/tail/matrix 精确相等，非掌实体世界顶点及掌 XY 外轮廓仅有浮点算术误差；新右骨点/尾、实体顶点及 cap 按反射核对。

现有 P1 exporter 在真实四肢 Blender 骨架上以 `exec` 消费 `--robot lizard2_palm_contract --contract_check --memory_scene`，恢复 `sys.argv`，四个实际末端绑定通过，无导出；声明契约通过不证明几何/物理通过。

## 结果

真实 Blender 5.2.2 LTS（d13f752e3b9c）生成退出 0，重新打开 neutral 校验通过，六 PNG 已输出。已查看全身俯视、全身斜视、右腕近景：右侧明确同步，掌体降低，根过渡仍与球/下段重叠，不是分离 pad。

原始数值唯一载体为本地 `rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered/measurements.json`：`rest` 保存四肢位移、实际球底/掌底差、cap 中心、骨/实体端环、长宽及整体 Z 包络、各环长宽厚、右侧 native/mirror 骨长；`turns` 保存 24 档原始 pose 测量、全部实体逐顶点残差和 BVH 计数。整体 Z 包络因根仍在 pivot 而增大，不能误读成降低后掌体厚度增加。后五环本身厚度/背拱不改；根 Y 宽不改。中立底差的小量为存储/绑定舍入，负值明确代表微小下悬，不宣称数学精确到位级。

`checks.json` 记录八组完整 argv 命令与实际/预期退出：all/claw/halfpad/P1 带修复各 0，逆修复各 1。旧 `--regression_without_fix` 仍把真实掌移回半掌长，根错位被拒；没有改变旧反例语义。四肢新增 high sole、twoleg incomplete、unmirrored right 负例，错 parent、缺实体段、stale inverse、retained toe、turn-only stale matrix 继续检出并恢复后通过。真实旧 claw blend 另被 fourleg 与低掌底要求分别拒绝；新 neutral reopen 后通过，同批共十个记录负例。

构建、保存及渲染后保护 492 个文件哈希一致，覆盖源/采用 blend、两个既有 P2 artifact 目录及采用/冻结树。源 SHA256 为 `ede254ae904d5ffcb909b55ae134714441d1f0c721b85660531d4b675ebc9010`；每个旧 artifact 哈希取 JSON `protected_sha256_before/after`。旧证据未重写、旧资产未删除。

## 证据引用

新模型/图/原始测量/日志全在本地目录 `rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered/`，`.git/info/exclude` 精确排除此目录。旧两个 P2 目录只读，不覆盖。具体产物：

- `sample_neutral.blend`：四肢中立模型，渲染前保存，无诊断 collection。
- `all_top.png`、`all_oblique.png`：全身；`lf_root.png`、`rf_root.png`、`rl_root.png`、`rr_root.png`：四个腕/踝近景，共六图。
- `measurements.json`：本次全部原始几何、诊断、保护哈希、负例与碰撞读数。
- `generation.log`：真实生成/保存/reopen/六张渲染及旧实模型负例。
- `checks.json`：八组实际完整命令、预期/实际退出码；对应 `all_with_fix.log`、`all_without_fix.log`、`claw_with_fix.log`、`claw_without_fix.log`、`halfpad_with_fix.log`、`halfpad_without_fix.log`、`p1_with_fix.log`、`p1_without_fix.log`。
- 旧基线与批准来源只读：`acceptance/records/2026-10-12-lizard2-claw-palm-shape.md`、`acceptance/records/2026-10-12-lizard2-palm-p2-sample.md`、`acceptance/records/2026-10-12-lizard2-palm-chain-p1.md`。

仓根 cmd 实际生成命令如下；首次 stdout 重定向到同父目录 `_generation.log`，成功后移动为上述 `generation.log`。输出现在已存在，复读须加 `--check_only`，生成命令再次运行将拒绝覆盖。

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --palm_shape claw --all_legs --sole_at_ball_bottom --diagnostic_angles=-10,0,10 --output_dir rl_exp\blender\lizard2_palm_p2_sample_claw_all_lowered > rl_exp\blender\lizard2_palm_p2_sample_claw_all_lowered_generation.log 2>&1
```

八组实际复读命令取 `checks.json`（不是尚未执行计划）；其基本入口同上，`--check_only`，all/claw/halfpad 分别带对应 opt-in；逆修复再加 `--regression_without_fix`。P1 基本入口末尾为 `--contract_self_check`，其逆修复再加同一 regression flag。检查运行全在内存、不写旧输出。最后一轮八组仍为预期 0/1，全四肢掌网格另通过 manifold/contiguous 与正 signed volume 断言。

最终实际闸门命令及结果：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -c "import pathlib; p=pathlib.Path('rl_exp/blender/scripts/lizard2_stance_candidate.py'); compile(p.read_text(encoding='utf-8'),str(p),'exec')"
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_work_docs.py
git diff --check
git check-ignore rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered/measurements.json
```

compile 无错误（实际最后批次同一 `compile` 与八组回归合并执行，输出 `COMPILE_OK`）；事项检查退出 0，`WORK_DOCS_OK (86 item file(s))`，active bytes `100626/120000`；diffcheck 退出 0；check-ignore 命中新目录精确排除。未压缩或删除其它阶段的未完动作。父会话负责完整 hooks/提交，本轮未运行完整套件。

## 未覆盖边界

明确碰撞读数：evaluated 下段 cylinder 对掌 surface 的 BVHTree overlap，neutral 与每档单关节均量，同 pose 恢复旧高掌体作前后对照。全部 24 档仍有表面相交，下降只减少计数，未消除掌根相交；完整原始 pair counts 取 `rest/turns`，不把计数多少解释成穿透深度、净空或碰撞接受。有限半径 cylinder 仍到 pivot，根 cap 也在 pivot，根表面相交是保留原连接设计的结果；本轮不偷改 shank trim、球半径、轴或 pivot。

BVH 表面交叉不捕获纯包含，且只检查下段—掌这一对，不是所有自碰撞、球碰撞过滤、接触面承重、完整动作周期或物理。球名字虽保留供既有转换器过滤使用，本轮没有新导出，不宣称该过滤已在新资产生效。右 native 长度与左镜像有微小差异，原始 native/mirror 长度已单列；镜像形体不等于已测质量/惯量或动力学对称。无密度/质量/驱动采用。

最大维护依赖：该隔离分支依赖已有 halfpad 和 claw neutral 作只读实基线，干净检出没有这些本地 artifacts 时不能直接复现 alllegs；禁止绕过或悄悄覆盖基线。新输出再生成需新空目录。新上下文仍须按 A2/P3/P4 对实际网格、导出误差、完整周期与承重独立审核；四肢批准不解除未验不进 P3的边界。其他会话 dirty 文件未触碰；主会话已复读模型及实跑正负例和提交闸门，提交不构成候选接受。

## 补充：独立运动镜像与非根掌底自检（仅内存）

本次只改当前 P2 自检与本记录。未改构建轴、bone roll/matrix、骨点、网格、默认路径或既有 regression flag；没有重新生成 blend/PNG/JSON。上文生成时源 SHA256 保留；本次自检脚本 SHA256 为 `a261f9f5603bbd54a80b30a48b228a36e6e6897d52d862dd0e7ae0659b9b6a56`。以下读数来自实际 Blender stdout，不回写旧 `measurements.json`。

审核纠正：世界 Y 反射的线性部分 R 是 improper transform，det(R)=-1；旋转轴是轴矢量，变换为 det(R)R·axis=-R·axis，不是极矢量 R·axis。当前 `axis=-(reflection.to_3x3() @ source["axis"])` 正确，负号保留。现有 pose bases 清零遍历全部 rebuilt samples，包含右侧；原整体掌底断言也已经用 abs 比较真实 evaluated 球底，不是单向高度断言。新自检是独立回归增强，不是当前模型缺陷修复。

独立 oracle 直接取左侧 `turn_geometry` 的真实 evaluated 世界顶点，再反射后逐顶点对照右侧同角度 evaluated 顶点，不用右侧 axis 重建期望。前肘/腕、后膝/踝各 -10/0/+10°，共 12 对；原 24 档逐关节诊断继续全部通过。最大镜像残差 `6.474721724510321e-07 m`，只按既有 float32 坐标尺度算术界检查，不新增或批准数值验收容差。真实 P1 四肢动态平面/末端消费者仍通过。

八个独立运动负例实际把右侧 pose 的旋转轴反号，保持左侧同角度 oracle、骨矩阵和网格不变；全部由 `same-angle mirrored motion mismatch` 拒绝。-10/+10° 最大逐顶点偏差 [m] 分别为：rf_elbow `0.1880985005016574 / 0.18809840085773827`，rf_wrist `0.06955861076250311 / 0.06955886818711753`，rr_knee `0.16258668790944428 / 0.16258688051871276`，rr_ankle `0.06956127031765601 / 0.0695618444527508`。每例 finally 恢复实际 pose basis，恢复后 mechanical_check 通过；不是假向量测试，也没有新增用户 flag。

新增原始字段 `palm_body_min_z_minus_ball_min_z_m` 排除 `cap_ids`，只量非根掌体相对真实 evaluated 球底。neutral lf/rf/rl/rr 分别 `-1.1920928955078125e-07 / -5.960464477539063e-08 / 0 / 0 m`；abs 断言只使用既有算术界。既有 `sole_restore(True)` 负例仅升高非根掌体、根 cap 固定，四肢该字段分别 `0.04825311899185181 / 0.04825317859649658 / 0.04827791452407837 / 0.04827791452407837 m`，实际由 `high distal body sole: not aligned to actual ball bottom` 拒绝，随后恢复通过。整体网格 min 若由低 cap 提供，不能单独证明掌体贴底；当前设计 cap 高于降低后的掌体，没有发现这一缺陷，不另造 cap-only 负例。

实际复读命令（仓根 cmd；无重定向、无新 artifacts）：

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --palm_shape claw --all_legs --sole_at_ball_bottom --diagnostic_angles=-10,0,10 --output_dir rl_exp\blender\lizard2_palm_p2_sample_claw_all_lowered --check_only
```

最终脚本实跑正例退出 0，四肢/24 档/16 个内存负例通过；同一命令追加 `--regression_without_fix` 退出 1，仍因原真实半掌长逆修复导致 `unmirrored right mesh` 拒绝。另实跑两肢 claw、默认 halfpad 与 P1：前两者从上述命令去掉 `--all_legs --sole_at_ball_bottom`，halfpad 再去掉 `--palm_shape claw`；P1 将 `--` 后参数改为 `--contract_self_check`。三组正例退出 0，各追加原 `--regression_without_fix` 退出 1（claw/halfpad 根错位，P1 旧长段被错误接受）。这六组在只增加负例原始读数打印前执行，相关模式不进入该新增低掌分支；最终低掌正负例随后再次实跑。

编译与 `git diff --check` 通过。四肢正例保护 492 个源/旧资产文件哈希不变；最终正负例运行前后另对现有 all4 输出目录全部 18 个文件 SHA256 核对不变。模型/图/pose 输出未改，新增读数仅 stdout。本轮依然 **24/24 档下段—掌表面相交**，不修碰撞、不宣称接受。没有修改 active 事项、其它 dirty 文件；没有 stage、commit 或 push。
