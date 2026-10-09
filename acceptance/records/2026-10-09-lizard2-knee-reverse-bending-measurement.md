# lizard2 膝反曲边界量测与限位候选（2026-10-09）

## 适用范围

承接 `2026-10-09-lizard2-limit-requirement-and-status-sync.md` 的用户决定（限位必须禁止反曲），执行
`work/active/joint-limit-shape-and-range-pass.md` 的下一份可审阅提案：**先让离线口径覆盖当前采用的机体，
再逐腿量测伸直边界、反曲余量与折叠端**。本轮不改 URDF/USD/网格/锁/配方，不训练，不实施限位；限位实施
仍按 `.codemaker/rules/versioning.mdc` §A 的版本与资产采用机制处理。

## 验收条件

- 现成口径能读**当前采用机体**（`rl_exp/lizard2_candidate/lizard2_candidate.urdf`），不再把上一代机体的
  轴向与膝事实当当前机体的事实。
- 量测以工具输出为准，不手抄资产；反曲余量的**符号**有意义（正 = 可达反曲）。
- "不能反曲"至少有一条会变的断言看守，且该断言被证明**不放宽限位就会红**。
- 不把限位候选写成已实施；余量取值不凭未验证角度倒填。

## 结果

### 口径覆盖当前机体（本轮前置）

`check_leg_reachability.py` 的轴向前提原是字面量（铰链 `-1 0 0`、掌轴 `0 1 0`），闭式
`fold_tilt_cos` 的注释也声明"仅对本资产轴向有效"。在候选上 `--self-check` 直接红：

```
AssertionError: ('lf', "the closed form is written for the asset's own hinge and blade directions")
```

实测候选的轴是那条旧轴向绕机体 z 偏航后的结果，且**同腿的铰链与掌轴用同一偏航**：

| 腿 | 腿平面偏航 ψ | 铰链/掌轴关系 |
|---|---|---|
| lf / rr | `+20.0000°` | 掌轴 = 铰链绕 z 转 90°（测得一致） |
| rf / rl | `-20.0000°` | 同上 |

前腿与后腿的偏航**异号**（lf `+20` vs rl `-20`）⇒ 前腿向外的腿平面与后腿向外的腿平面朝向相反，与
"前腿向前外、后腿向后外"的站姿一致；同对左右腿异号 ⇒ 左右互为镜像。最小改法：闭式与手算事实改用
URDF 轴自身推出的偏航（`leg_plane_yaw` / `yawed_normal`），旧机体 ψ = 0 时逐字退化为原式——该退化由
`--self-check` 的闭式-FK 逐点比对（σ×foot 网格，容差 1e-12）在本机体上继续看守。

一并修正：`--urdf` 传相对路径时 `urdf.parent in pad_mesh(...).parents` 误红（一边相对一边绝对），改为入口
统一 `resolve()`；`DEFAULT_URDF` 从上一代机体的 `versions/lizard2/lizard2.urdf` 改指**资产树声明消费的**
`rl_exp/lizard2_candidate/lizard2_candidate.urdf`（`versions/lizard2/assets.json`）。

### 反曲边界（当前采用的机体，URDF 自身读数）

限位逐关节（URDF 原文）：`hip ±0.60`、`haa ±0.60`、`hfe ±1.20`、`kfe ±1.60`、`foot ±0.50` rad。

| 腿 | 膝伸直位 `hfe` [deg] | 限位对伸直位的余量 [deg]<br>（正 = 可达反曲） | 折叠端 thigh–shank [deg] |
|---|---|---|---|
| lf | `-74.999965` | `-6.245030` | `143.754901` |
| rf | `+74.999965` | `-6.245030` | `143.754901` |
| rl | `-74.999968` | `-6.245033` | `143.754903` |
| rr | `+74.999968` | `-6.245033` | `143.754903` |

**结论（当前机体）**：膝的 `±1.2 rad` 区间**停在伸直位之前 6.245°** ⇒ **反曲不可达**；代价是膝也
**不能完全伸直**（差同一 6.245°）。上一代机体是相反的情形：伸直位在 `±55.1465…55.1497°`，而区间仍
`±1.2 rad` ⇒ 带 `+13.605…13.608°` 的反曲，这正是"反曲禁区"要修的那件事——**当前机体已经不欠这条**，
欠的是"余量是否够控制误差"。

### 限位候选（提案，未实施）

| 关节 | 现限位 [rad] | 反曲侧 | 候选 | 待定项 |
|---|---|---|---|---|
| `hfe`（膝） | `±1.20` | 伸直位 `±75.00°`，落在区间外 | 现状已满足"不能反曲"；**不改数值** | 6.245° 余量对跟踪误差/控制是否足够（R4：需扰动、跟踪误差与执行验证，本轮未做） |
| `kfe`（踝） | `±1.60` | 未定义 | 未给候选 | 踝/掌的"反曲"方向要从脚板几何与 R3/R4 定；本轮只报了它的数值，没有把它算成反曲项 |
| `hip` / `haa` | `±0.60` | 不属反曲类（yaw / 外展轴） | 不动 | 行程需求归 R4 的髋行程项 |
| `foot` | `±0.50` | 同上（板角） | 不动 | — |

限位住在 URDF 内 ⇒ 任何数值改动都是**资产内容**变更，按 §A 走新版本与资产采用（现有 `v3/asset_lock.json`
不刷新）。本轮因此**只出候选，不落数值**。

### 会变的断言（"不能反曲"的看守）

`check_leg_reachability.py --self-check` 现在逐腿断言 `over_run <= 0`（`KNEE_FACTS` 同时重钉为当前机体
的伸直位、带符号余量与折叠端），并进了离线清单（`offline_suite.py`，`MAX_CHECKS` 47 → 48）。红绿：

| 步骤 | 命令 | 结果 |
|---|---|---|
| 修前 | `--self-check --urdf <候选>` | 红：闭式轴向前提断言失败（见上） |
| 修后 | `--self-check`（默认 = 采用机体） | exit 0；每腿打印 `straight … margin -6.2450 deg (>0 = reverse bending reachable), folded end 143.75 deg` |
| 破坏测试 | `--break-test` | `BREAK_TEST_OK (6 perturbation(s), every one caught)`，新增第 6 条 = "把膝区间放宽到伸直以外"，必须且确实被抓 |
| 离线全套 | `run_offline_checks.bat --jobs 4` | 见"复读与结果" |

## 复读命令与结果

解释器 `E:\IsaacLab\env_isaaclab\Scripts\python.exe`（本机 `paths.yaml`），从 `E:\Robot` 执行：

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_leg_reachability.py --self-check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_leg_reachability.py --break-test
rl_exp\tools\verify\run_offline_checks.bat --jobs 4
git diff --check
```

结果：

- `--self-check` exit 0；四腿的膝读数与上表逐位一致（伸直位 ±74.999965/±74.999968，余量 -6.245030/-6.245033，
  折叠端 143.754901/143.754903）；闭式-FK 一致性、翻掌反例被拒、三铰链与机体 z 恒 90° 等既有断言全绿。
- `--break-test`：6 条扰动全被抓（含新增的反曲扰动与"URDF 离开自己的网格树"）。
- 离线全套：`ALL_OFFLINE_CHECKS_PASSED (48/48 in 69.3s, wave 255s/informational, jobs=4)`；新增的第 48 条
  `leg chain caliber` 单独 0.9 s。
- 零位读数（顺带，仍是默认姿态的事实）：足垫原点 lf `(+0.428075,+0.516894,-0.843163)`、rf `(+0.428075,-0.516894,…)`、
  rl `(-0.545557,+0.493258,…)`、rr `(-0.545557,-0.493259,…)`；足底法线偏离 link `-z` 1.45°（前腿）/ 0.24°（后腿），
  有向 `facing +1.000`。

## 证据引用

- 用户决定与状态同步：`acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync.md`。
- 采用机体的来源与限制：`acceptance/records/2026-10-08-lizard2-blender-body-candidate.md`、
  `acceptance/records/2026-10-08-lizard2-v3-landing.md`。
- 评审判据（R3/R4 消费面）：`acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md`。
- 旧机体的膝越直证据：`acceptance/records/2026-09-29-lizard2-hfe-knee-limit.md`、`work/closed/2026/hfe-extension-stop-not-validated.md`。
- 落点代码：`rl_exp/tools/verify/check_leg_reachability.py`（`leg_plane_yaw` / `yawed_normal` / `KNEE_FACTS` /
  `straight_hfe` / `--self-check` / `--break-test`）、`rl_exp/tools/verify/offline_suite.py`（新增 Check 与 `MAX_CHECKS`）。

## 未覆盖边界

- **没有改任何限位数值，也没有实施候选**：URDF 内容变更按 §A 另走，本轮不刷新资产锁。
- **6.245° 余量够不够未定**：需要 R4 的跟踪误差、扰动与执行验证，本轮只有几何读数；余量不足时该改的是
  几何或区间（资产侧），不是本记录。
- **踝/掌的反曲方向未定义**：`kfe`/`foot` 的数值已报，但"什么算踝的反曲"要脚板几何 + R3/R4 才能判，
  本轮不算成反曲项。
- **仍是几何口径**：`--self-check` 证明的是 FK 与限位区间的几何关系，不是碰撞安全、完整动作周期、承重、
  滑移或策略行为；`--break-test` 只证明这些断言会响，不证明设计达标。
- 上一代机体的数值仍在 `versions/lizard2/lizard2.urdf` 与历史记录里可读（`--urdf` 仍可读任意机体；
  但 `KNEE_FACTS` 钉的是采用机体，把 `--self-check` 指向别的 URDF 应当红，这是本轮的口径，不是缺陷）。
- 左右命令符号、下段倾角 α、后脚板形状、真实网格碰撞与旧机体开自碰撞控制组仍按各自证据/事项决定。
