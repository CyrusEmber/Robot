# lizard2 碰撞、余量与踝几何的一次性核验（2026-10-09）

## 适用范围

承接 `work/active/joint-limit-shape-and-range-pass.md` 的挂账，本轮把三项此前"未做/未定义"的读数补齐：
**网格级自碰撞（三机体对照）**、**自碰撞开关的物理对照**、**膝关节余量对控制滞后的关系**，并给踝（`kfe`）
的几何一个可判定的定位。除下面明写的一处口径修正外，不改 URDF/USD/网格/限位/锁/配方，不训练、不冻结。

## 验收条件

- 网格级自碰撞要有**控制组**：新机体的读数只有和旧机体、以及另一个家族放在一起才有归因意义。
- 物理侧对照必须**只换开关**（同一命令、同一任务、同一窗口），否则"整机不动"仍是无归因观察。
- 每条结论带它的天花板：凸包/三角口径、盒内极值组合的可达性、单 seed 短窗。
- 不把红读数加进离线清单；不把本轮读数写成限位或几何已修。

## 结果

### ① 网格级自碰撞：三机体对照（离线，不起仿真）

口径：逐关节取 URDF 自身限位内的姿态（`single` + `combined` 两组），碰撞网格取**凸包**做包含判定，
再对命中姿态做**网格级点-三角**确认（世界变换已烘进顶点）；直接相邻对按枢轴规则跳过（它们本来就共享枢轴）。
复读：`rl_exp\tools\verify\check_self_collision.py --family <f> [--urdf <body>.urdf]`。

| 机体 | URDF | 最小余量 | 穿透判定 | 网格级确认 | 判词 |
|---|---|---|---|---|---|
| **采用机体**（lizard2 main/v3） | `rl_exp/lizard2_candidate/lizard2_candidate.urdf` | **−222.86 mm** | 40 | **32** | `SELF_COLLISION_COUNTEREXAMPLE` |
| 旧机体（lizard2 main/v1-v2，已退休） | `rl_exp/versions/lizard2/lizard2.urdf` | −164.71 mm | 24 | 12 | `SELF_COLLISION_COUNTEREXAMPLE` |
| 对照家族（lizard） | `rl_exp/versions/lizard/lizard.urdf` | **+79.33 mm** | 0 | 0 | 无穿透 |

最深的确认对（采用机体）：`['base_link','rl_foot']` **−215.43 mm**，姿态
`rl_haa=+0.60, rl_hfe=+1.20, rl_kfe=+1.60`；以及 `['chest_pitch','lf_foot']` −138.85 mm。
即**限位盒里存在脚掌穿过躯干/底盘的姿态**，而训练默认 `enabled_self_collisions=False` ⇒ 没有任何奖励或终止惩罚它。

三条读法：

1. 这不是"新机体才有的"：旧机体同口径也穿（12 对确认，−161 mm）⇒ 属 **lizard2 家族继承**的一笔账。
2. 但它**不是普遍属性**：同工具的 lizard 家族最小余量是 **+79.33 mm（零穿透）** ⇒ "限位值必须与几何匹配"
   是可以做到的，lizard2 的 `±0.6/±1.2/±1.6` 两代都不匹配。
3. 换代让这笔账**变差**：确认对数 12 → 32、最深 −161 → −215 mm。

### ② 自碰撞开关的物理对照（只换开关）

命令（唯一差别是 `--self-collision`，以及对照组的 `--usd/--urdf` 指向旧机体）：

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\diagnose\stance_step_probe.py --headless ^
    --task Lizard2-Flat-Play-v3 --self-collision on --settle 200 --steps 60 --leg lf --joint haa
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\diagnose\stance_step_probe.py --headless ^
    --task Lizard2-Flat-Play-v3 --self-collision on --settle 200 --steps 60 --leg lf --joint haa ^
    --usd rl_exp\assets\lizard2\lizard2.usda --urdf rl_exp\versions\lizard2\lizard2.urdf
```

| 跑 | base z | 四脚受力 | 被扫关节实际/目标 | 备注 |
|---|---|---|---|---|
| 采用机体 + 开自碰撞 | 恒 `1.1000`（= `base_init_height`，即**没落地**） | `0.0 N` ×4 全程 | `0.000 / −0.150`（关节不动） | 仿真不推进；重建力矩随目标线性走到 −120 Nm 而位移恒 0 |
| 旧机体 + 开自碰撞 | `0.905–0.910`（正常起伏） | `55–280 N`（正常承重） | 跟得上（−0.074 / −0.100） | 非足体接触 `0 N`，行为正常 |

**这条推翻了 `2026-10-08-lizard2-blender-body-candidate.md` 的假设**。该记录当时写"控制组尚未跑 ⇒ 这更像
'这一族资产本就不能开自碰撞'，不能据此说候选自碰撞有问题"；控制组现在跑了，结论相反：**旧机体开自碰撞
是正常的**，"开自碰撞整机不动"是**采用机体特有**，属于新机体碰撞体的一笔真账（至少在生成/默认姿态附近）。
`isaaclab-asset-pipeline` 里"接触抖振 → 关自碰撞"那条说的是旧机体的**抖振**，不是"不推进"。

### ③ 膝的 6.245° 余量与控制滞后

- 几何：限位停在伸直位之前 **6.245°**（= 0.1090 rad），反曲**物理不可达**（前一份记录）。
- 实测滞后（`2026-10-08` 记录，目标幅值 0.135 rad 的稳态窗）：`hip` 0.064、`hfe` 0.115、`haa` 0.129 rad。

⇒ R4 那个"控制余量够不够"的问题，在膝上**换了个形态**：它不再是"滞后会不会把关节顶过伸直"（硬限位挡住，
最多贴限位），而是"**滞后（0.115 rad）与余量（0.109 rad）同量级 ⇒ 被压向伸直侧时关节会长期贴限位**"。
这是"贴限位常态"的问题，不是反曲问题；判它需要同工况（膝被驱动到接近限位）的贴限位占比，而不是小幅度扫描的滞后。

### ④ 踝（`kfe`）的几何定位

按膝的同一读法扫 `kfe` 全行程（41 点、其余关节为零），量"胫段（`hfe`→`kfe`）与掌段（`kfe`→`foot`）的夹角"：

| 腿 | `kfe` 限位 | 该夹角 |
|---|---|---|
| lf / rf / rl / rr | `±91.67°` | **全程恒 `75.00°`** |

即 `kfe` **转不动这两个段之间的夹角**（掌垫偏移沿铰链轴）⇒ 它是**纯朝向关节**：它的作用是把掌垫绕铰链轴
转，而不是折叠腿链。因此"踝的反曲 = 越共线"这种定义**在这条链上没有几何意义**；踝侧唯一有向的判据是
**掌面朝向**（`faces_down` / `fold_tilt` 的有向那一半），而限位盒里确实存在**掌面朝上**的姿态——
`check_leg_reachability.py --self-check` 的翻掌反例就是被断言"在盒内"且被 `faces_down` 判红的那一个。

⇒ 踝侧的"禁区"应定义为**多关节耦合的朝向约束（运行姿态域）**，而不是某个轴的 URDF 限位——这与 ① 的
自穿是同一类问题（盒 ≠ 域），可以并到同一次范围/姿态域决策里，不需要各立一项。

### ⑤ 本轮的口径修正（P011：工具默认读退役机体）

换届后有三个地方"报告说在检当前机体、实际读的是上一代"（与 `check_leg_reachability` 的默认值同一种病）：

| 落点 | 旧默认 | 现在 |
|---|---|---|
| `check_self_collision.py` | 固定 `versions/<family>/<family>.urdf` ⇒ 对 lizard2 落在**退休**旧机体 | 按家族 `assets.json` 声明的网格树解析 `<body>/<body>.urdf`，回退老布局（`lizard` 的树是仓级的），`--urdf` 覆盖 |
| `check_leg_reachability.py` | 字面量指 `versions/lizard2/lizard2.urdf` | 同一解析函数 |
| `stance_step_probe.py` | `--urdf` 默认字面量指同一个退役文件（标定来源与 `--usd` 可能不是同一台机体） | 同一解析函数；非默认时打印 `--urdf override` |

解析规则现在**只有一个家**：`check_leg_reachability.family_urdf(rl_exp, family) -> (path, source)`，
另两个工具 import 它（`check_leg_reachability` 是 stdlib-only，所以探针可以在 `AppLauncher` 之前 import）。
三处都把来源打进首行：`sweeping <path> [body from: …]` / `CALIBRATION <path> [body from: …]`——
**让"扫了退役机体"不可能静默**是这条修正的一半，另一半才是把默认值改对。

顺带实测一处**没有**发生的错：本次对照里采用机体的那次跑没有传 `--urdf`，所以标定读的是旧机体 URDF。
实测两代机体在零位的掌垫法线拟合**同值**（都 `1.45°`，`--pose 0 0 0 0 0 --leg lf`）⇒ 那次读数没有被标定来源污染；
但这条不构成"以后也不会"——掌垫换代就会分叉，所以默认值照改。

**没有**把 `check_self_collision.py` 加进离线清单：它现在对 lizard2 是**红**的
（`SELF_COLLISION_COUNTEREXAMPLE`，exit 1），加红闸等于每天红一次。加它的前提是先做范围/姿态域决策，
让它在采用机体上变绿。

## 复读命令与结果

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_self_collision.py --family lizard2
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_self_collision.py --family lizard2 --urdf rl_exp\versions\lizard2\lizard2.urdf
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_self_collision.py --family lizard
rl_exp\tools\verify\run_offline_checks.bat --jobs 4
git diff --check
```

结果：

- lizard2（采用机体）：`sweeping …/lizard2_candidate.urdf [body from: declared asset tree (assets.json: meshes)]`，
  最小余量 −222.86 mm、穿透判定 40、**网格级确认 32**、判词 `SELF_COLLISION_COUNTEREXAMPLE`（exit 1）。
- lizard2（旧机体，`--urdf` 指向）：最小余量 −164.71 mm、判定 24、确认 12，同判词。
- lizard：`+79.33 mm`、0 判定（exit 0）。
- 两次仿真读数的尾部判词见 ② 表（两次都 `non-foot contact force: max 0.00 N on base_link`，采用机体那份的
  零值是"仿真没推进"的产物，旧机体那份是"真的没有非足体接触"）。
- 三工具改后的启动自检（`--headless --task Lizard2-Flat-Play-v3 --self-collision off --settle 20 --steps 4`）：
  `CALIBRATION E:\Robot\rl_exp\lizard2_candidate\lizard2_candidate.urdf [body from: declared asset tree
  (assets.json: meshes)]`，并且**关**自碰撞时正常跑（base z 0.907、四脚 120–260 N、非足体接触 0 N）
  ⇒ ② 的单变量对照成立：唯一差别是那个开关。
- 离线全套：`ALL_OFFLINE_CHECKS_PASSED (48/48 in 66.4s, wave 243s/informational, jobs=4)`；`check_leg_reachability`
  的 `--break-test` 仍 `BREAK_TEST_OK (6 perturbation(s), every one caught)`；`git diff --check` 无空白错误。

## 证据引用

- 用户要求："挂账的修复"（2026-10-09）。
- 挂账来源与判据：`work/active/joint-limit-shape-and-range-pass.md`、
  `acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md`（R3/R4/R5）。
- 被推翻的假设：`acceptance/records/2026-10-08-lizard2-blender-body-candidate.md`（"控制组尚未跑"一段）。
- 滞后读数出处：同记录（`--settle 200 --steps 60`，幅值 0.135 rad 稳态窗）。
- 家族自碰撞约定：`.codemaker/skills/tool/isaaclab-asset-pipeline/SKILL.md`（抖振 → 关自碰撞）。
- 反曲不可达：`acceptance/records/2026-10-09-lizard2-knee-reverse-bending-measurement.md`。
- 落点代码：`rl_exp/tools/verify/check_self_collision.py`（`family_urdf` / `--urdf` / 首行来源打印）。

## 未覆盖边界

- **网格口径的天花板**（工具自己印）：凸包过近似凹形 link（报出的重叠可能是凸包假象）；包含判定漏掉纯边-面
  交叉（真重叠可能被漏）；盒内极值组合**不一定在载荷下可达**——所以 ① 是"盒里有这种姿态"，不是"运行时会发生"。
  直接相邻对按枢轴规则跳过，它们的重叠不在读数里。
- **仿真侧**：1 env、单 seed、headless、单短窗；"采用机体开自碰撞不推进"的**机制未查明**（求解器不收敛 /
  约束爆发 / 生成姿态就重叠，三者未区分）。② 只证明"同一命令下开关差异"，不证明是几何的哪一处造成。
- **没有修任何几何、限位或资产**：自穿与不推进都指向资产/范围决策，按 §A 走版本与采用机制，本轮不刷新锁。
- ③ 的滞后是**小幅度扫描**的读数，不是"被驱动到接近限位"工况的贴限位占比；后者未测。
- ④ 只给几何定位，没有新增朝向约束；"踝反曲"的最终定义与实现仍待用户拍板（它属姿态域，不属单轴限位）。
- 左右命令符号、下段倾角 α、后脚板形状、完整动作周期与 R5 发力验证仍各自未决，不因本轮自动关闭。
- `rl_exp/assets/config.yaml` 里的 `asset_path` 仍指退役机体的 URDF：它是 IsaacLab 转换器的**旁产**
  （仓内无消费者，grep 只命中它自己与 `convert_urdf.py` 的调用参数），本轮不动它，但**不要**把它当
  "当前机体"的声明——那个声明是 `versions/<family>/assets.json` + 版本 yaml 的 `usd_path`。
