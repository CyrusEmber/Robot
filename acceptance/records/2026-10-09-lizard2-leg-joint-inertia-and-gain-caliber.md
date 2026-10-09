# lizard2 腿关节反射惯量与增益口径（2026-10-09）

## 适用范围

补 `work/active/actuator-params-audit.md` 的 `next` ⑤ 缺的第一样：**关节轴上的有效惯量口径**，以及频率侧
口径。给出读数与判据形状，**不设阈值、不改任何增益、不动资产**。

被读对象：采用机体 `rl_exp/lizard2_candidate/lizard2_candidate.urdf`（零位构型），增益取消费该机体的配方声明
（`rl_exp/versions/lizard2/main/main_params.yaml` 的 `actuators:` 组，逐关节归属由契约闸同一实现给出）。

## 验收条件（口径，写在这里因为惯量没有口径就不是读数）

- **模型**：关节空间惯量矩阵在**零位构型**上的**对角元**——关节轴下方每条连杆按 `m·|r_perp|² + uᵀ I_L u`
  求和（复合刚体、下游关节冻结在同一组角度）。对对角元是精确的，**不含非对角耦合**。
- **基座视为固定**：浮动基座下严格量是消去基座后的 `M_ii`。机体重量远大于单腿，但这个近似的差额**本记录没有量化**
  ——是具名的缺口，不是修正项。
- **不含**接触、地面、其余三腿、脊柱；**单构型**，换姿态读数会变。
- `w_n = √(Kp/I)` [rad/s]、`ζ = Kd/(2√(Kp·I))` 是**局部单自由度**的一对；ζ **不判整机稳定**（耦合、接触、脊柱都在外面）。
- 频率只给**比值**：对**物理步 200 Hz**与**控制周期 50 Hz**。执行器自身带宽**无数据表可查**，因此不出现数字
  （这一点是本口径对"不拿 Nyquist 当判据"的落实：比的是这两个时钟）。

## 结果

零位、基座固定、30 关节机体的四条腿（`lf`/`rf` 与 `rl`/`rr` 各成一对镜像）：

| 关节 | I [kg·m²] (lf/rf → rl/rr) | ω_n [Hz] | ω_n / 200 Hz | ω_n / 50 Hz | ζ |
|---|---|---|---|---|---|
| `hip`（yaw） | 0.4598 → 0.4596 | 6.6 | 0.033 | 0.13 | 1.043 |
| `haa`（外展） | 1.9821 → 1.9905 | 3.2 | 0.016 | 0.06 | 0.502 |
| `hfe`（膝） | 0.5421 → 0.5474 | 6.1 | 0.031 | 0.12 | 0.960 |
| `kfe`（踝） | 0.0483 → 0.0496 | **20.5** | 0.103 | **0.41** | **3.218** |
| `foot`（板角） | 0.0220 → 0.0219 | 15.2 | 0.076 | 0.30 | 2.861 |

（Kp/Kd 取自配方声明：hip/haa/hfe/kfe = 800/40，foot = 200/12。）

**可读出的结论（只此三条）**：

1. **没有关节的局部带宽接近任一时钟**：最大 ω_n 是 `kfe` 的 20.5 Hz = 物理率的 0.103×、控制率的 0.41×
   ⇒ 在这两个口径下，PD 的局部时间常数都远离采样率；"隐式积分在替真实动力学做功"这一担心在本构型的**局部**
   读数上得不到支持（整机耦合仍是另一回事）。
2. **同一套 Kd/Kp = 1/20 并不产生统一的 ζ**：`haa` 0.502 而 `kfe` 3.218，跨关节差 **6.4 倍**。因为
   `ζ ∝ Kd/√(Kp·I)`，轻惯量关节（`kfe`/`foot`）在家族比例下**过阻尼**、最重的 `haa` 近临界。
   ⇒ 若目标是统一阻尼，改的是**逐关节 Kd**；`Kp` 定的是 ω_n（带宽），两件事分开。
3. **髋的 I 最小不是笔误**：它绕机体 z 转（yaw），零位时整条腿几乎沿其轴线 ⇒ 力臂近零（0.46）；`haa` 是
   外展轴，要摆整条腿 ⇒ 最大（1.98）。惯量必须**逐关节按自己的轴线**算，这也正是"不是 link 的惯量分量"的含义。

## 复读命令与结果

解释器 `E:\IsaacLab\env_isaaclab\Scripts\python.exe`（本机 `paths.yaml`），从 `E:\Robot` 执行：

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_leg_reachability.py --self-check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_leg_reachability.py --break-test
```

- `--self-check`：exit 0，四腿各打印 `reflected inertia (base fixed, zero pose)` 一行，数值与上表逐位一致。
- `--break-test`：`BREAK_TEST_OK (8 perturbation(s), every one caught)`，新增两条 = "所有连杆的惯量张量被丢掉
  （点质量模型）" 与 "子树被截断成关节自己的子连杆"。
- 离线全套：`ALL_OFFLINE_CHECKS_PASSED (48/48 in 69.3s, jobs=4)`，`MAX_CHECKS` 未动（断言的落点是第 48 条已
  有的 `leg chain caliber`，折进而非新增）。

**本轮手算自检当场抓到两处我自己的错**（记下来，因为它们是这类口径最自然的两个坑）：① 关节轴原点取成
**父**连杆帧——URDF 的轴是陈述在**子连杆**帧（= 关节自身帧）里的；错法会让两关节报同一个数，是手算例
4.8/0.8 抓到的。② 我原先写下的"嵌套子树 ⇒ 读数单调"是**错的**：质量项带的是每个关节**自己的**力臂，
零位髋纵轴就是反例；该断言已删，改为"点质量读数必须严格小于完整读数"。

## 证据引用

- 事项与判据：`work/active/actuator-params-audit.md`。
- 同轮驱动读回与静站基线：`acceptance/records/2026-10-09-lizard2-drive-readback-audit.md`、
  `acceptance/records/2026-10-09-lizard2-static-load-demand.md`。
- 跟踪能力随频率的实测（本口径的另一半问题）：`acceptance/records/2026-09-22-lizard2-actuator-capability.md`。
- 落点代码：`rl_exp/tools/verify/check_leg_reachability.py`（`link_inertials` / `downstream_links` /
  `gain_table` / `reflected_inertia` / `--self-check` / `--break-test`）。

## 未覆盖边界

- **不设阈值**：判"增益是否过大"要力矩与带宽需求，那要目标速度带（R4）；本记录只给口径、读数与两个时钟的比值。
- **单构型（零位）**：口径支持换姿态重算，本轮没扫；承重/接触下的有效惯量会变（接触约束方向相关，本口径完全不含）。
- **基座固定近似未量化**：浮动基座的真实 `M_ii` 与这里的差没算。
- **ζ 是局部量**：不构成稳定性结论，也不含关节耦合与非对角项。
- 只手算/几何口径：不代表策略行为，也不代表任何 run 的跟踪质量（那归速度带下的实测）。
- 惯量来自 URDF 的 `<inertial>`；网格与惯量的不一致（若有）不在本口径内。
