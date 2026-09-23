# golden 冻结集合改为从树上读（第 2 步第一类，2026-09-22）

## 适用范围

- 落点：`rl_exp/tools/verify/check_golden_frozen.py`（新增 `subjects()` / `uncovered()`、主体对账、自测两条用例、
  `FROZEN` 第 5 条与对应 `FROZEN_REVS` 条目）、`rl_exp/tools/verify/offline_suite.py`（该检查的标签补一句）。
- 属 `work/active/freeze-maintenance-simplification` 第 2 步第一类：把"新线的锁没人登记"这个静默缺口折进**已有**闸门，
  不新增套件入口、不动 `MAX_CHECKS`。
- **不覆盖**：第 2 步其余三类（asset lock 集合完整性、开训前协议绑定、`binding.git_run` 编码）；也不覆盖
  `rl_exp/versions/**` 里三个枚举外目录（`rough-v0` 等）的**目录形态**（属第 4 步判定）。

## 验收条件

1. **先证明旧实现漏**：不改代码就能观测到"新增一条线的锁但未登记摘要 ⇒ 闸门仍绿"。
2. 修后同一情形必须**红并点名该文件**（反证：临时移除该条 ⇒ 判红；恢复 ⇒ 判绿）。
3. 合法重钉路径照旧：`--self-test` 判过、五条摘要判过。
4. 套件入口数与 `MAX_CHECKS` 不增。

## 结果

**漏检事实（未改任何文件即可观测）**：`FROZEN` 原为 4 条（`cfg_baselines.json` + `lizard/{main,parkour,baseline}/cfg_lock.json`），
而盘上有 **4 份线锁**，第 4 份是今天落地的 `rl_exp/versions/lizard2/main/cfg_lock.json`。旧实现据此判
`GOLDEN_FROZEN_OK (4 baseline file(s) unchanged, ...)` —— 新线的 golden **没有任何字节级看守**。

同一缺口是**第二次**发生：`baseline` 线的锁直到 2026-09-17 也在表外，
见 `acceptance/records/2026-09-17-lizard-hard-b-difference-declarations.md`（B0/B4 节，当时列为 A 带遗留）。两次都靠"人工想起来补一条"，
这正是不再把主体集合写成声明式的理由。

**修法**：`subjects(root)` 从树上读应有主体（`rl_exp/versions/cfg_baselines.json` 与 `rl_exp/versions/*/*/cfg_lock.json`），
`uncovered(root, frozen)` 做差集；`main()` 对差集逐条报
`{rel}: present but not frozen -- add its digest and a FROZEN_REVS entry, or state why this one is exempt in the record`。
**新锁落地即被覆盖**，要豁免得显式写下来，而不是靠没人看见的沉默。

**同变更内补钉**（否则修好即红）：`rl_exp/versions/lizard2/main/cfg_lock.json`
sha256 `0d67afd05d66061b2557aca047393140fd855f3b315bff737cdc2965360c05ce`，`FROZEN_REVS` 记 `dfdc2ae`
（该文件最后一次改动所在提交；改动前后 `git status --short` 对该路径无输出，即工作区字节 = 该 rev 的字节）。
理由写在表内注释：lizard2 线落地时无人被要求登记，v1 未训练、无 tag，故冻结它落地时的字节。

**反证**：临时把该条注释掉 ⇒

```
  DRIFT: rl_exp/versions/lizard2/main/cfg_lock.json: present but not frozen -- add its digest and a FROZEN_REVS entry, ...
  DRIFT: rl_exp/versions/lizard2/main/cfg_lock.json: frozen and FROZEN_REVS disagree about which files are covered
GOLDEN_FROZEN_DRIFT
```

恢复后 ⇒ `GOLDEN_FROZEN_OK (5 baseline file(s) unchanged, frozen at: 020e6fb x2, 27ca424 x1, 817d64e x1, dfdc2ae x1)`。

**自测**加两条：临时树里多出一份未登记的锁 ⇒ 必须判为 uncovered；表覆盖全部主体 ⇒ 必须判为无 uncovered。
`GOLDEN_FROZEN_SELFTEST_OK`。套件入口数未增（折进既有检查），`MAX_CHECKS` 未动。

## 证据引用

```
$ git ls-files rl_exp/versions | findstr /i cfg_lock
rl_exp/versions/lizard/baseline/cfg_lock.json
rl_exp/versions/lizard/main/cfg_lock.json
rl_exp/versions/lizard/parkour/cfg_lock.json
rl_exp/versions/lizard2/main/cfg_lock.json

$ python rl_exp\tools\verify\check_golden_frozen.py            # 旧实现
GOLDEN_FROZEN_OK (4 baseline file(s) unchanged, frozen at: 020e6fb x2, 27ca424 x1, 817d64e x1)

$ python -c "...sha256(read_bytes())..."                        # 补钉用的摘要
0d67afd05d66061b2557aca047393140fd855f3b315bff737cdc2965360c05ce

$ git status --short rl_exp/versions/lizard2/main/cfg_lock.json
（无输出 = 工作区与该 rev 一致）

$ git log --oneline -1 -- rl_exp/versions/lizard2/main/cfg_lock.json
dfdc2ae Point the head guard at the links that have colliders, and name the live termination set

$ python rl_exp\tools\verify\check_golden_frozen.py --self-test
GOLDEN_FROZEN_SELFTEST_OK

$ python rl_exp\tools\verify\check_golden_frozen.py            # 修后
GOLDEN_FROZEN_OK (5 baseline file(s) unchanged, frozen at: 020e6fb x2, 27ca424 x1, 817d64e x1, dfdc2ae x1)

（反证判词见"结果"节；全量套件见下）

```
$ rl_exp\tools\verify\run_offline_checks.bat
[35/47] stage B acceptance baseline is still the frozen one (golden locks pinned by digest; every lock on disk covered) ... ok (0.2s) -> GOLDEN_FROZEN_OK (5 baseline file(s) unchanged, frozen at: 020e6fb x2, 27ca424 x1, 817d64e x1, dfdc2ae x1)
ALL_OFFLINE_CHECKS_PASSED (47/47 in 43.9s, wave 220s/informational, jobs=6)
```
```

## 未覆盖边界

- 第 2 步其余三类缺口未做（asset lock 集合完整性、开训前协议绑定、`binding.git_run` 编码）。
- 闸门判红时打印的建议文本仍写"改本表 + `rl_exp/versions/lizard/ACCEPTANCE.md` 的 B0 节"——那是 **lizard 线**的基线冻结节；
  lizard2 没有 B0，其 provenance 落在本记录与表内注释。print 文案未改（动它会波及既有记录的引用），属遗留的措辞缺口。
- `FROZEN` / `FROZEN_REVS` 的**摘要值**仍需手写；本类只保证"集合不漏"，不保证"值自动可信"。
- 未在其他 checkout（CRLF/LF 差异）上验证；三个枚举外目录的目录形态仍无看守（第 4 步判）。
