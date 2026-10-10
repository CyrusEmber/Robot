---
id: harness-baseline-tag-gate
title: "代码基线 ↔ tag"的配对没有闸门：等 §4 冻结解除后再建
scope: ablation_harness
status: blocked
landing: rl_exp/tools/verify/check_version_docs.py
next: 等两件事齐了再动：(1) `OFFLINE_CHECKS.md` §4 的暂缓解除（lizard2 出第一条能走的策略）；(2) 用户拍板口径 —— 单给 harness 提成 red，还是与家庭侧同口径只报 WARN。齐了之后按 §4 默认动作走：断言进已有的 `check_version_docs.py`（0 新进程、0 秒预算），不新建 `check_harness_baseline.py`。落地前先读 `OFFLINE_CHECKS.md` §4 的准入两条。
close_when: 要么闸建成且 §4 的准入两条都写进了 commit message（来源缺陷 = 本项所指的 `0c3ec25`，破坏测试 = 还原比对后 `--self-test` 变绿）；要么用户拍板"本项与 lizard2 走通前不建"并把它取消（取消是用户决策，不是默认动作）。两种之外不关闭。
---

## 情况

`ablation_harness/HARNESS.md` 的「代码基线」是散文行，改了它没有任何机器判据要求同笔打 tag。2026-09-22
的实例是 `0c3ec25`：它把基线从 v1.8.0 写到 v1.9.0、并写下"加模块或改语义要 bump + 打锚点"，但只 push 了
提交，v1.9.0 从此无锚点可 checkout —— 缺口由 `work/active/harness-version-anchor-missing.md` 补上，
**但补的是数据，不是机制**。

**为什么不现在建闸**（三条，都在仓内可查）：

1. `OFFLINE_CHECKS.md` §4 把新检查分**声明一致**（文档 / 声明 / 锁之间互查）与**行为成立**两类，本闸属
   前者；同一节写明"lizard2 出第一条能走的策略之前，**暂缓新增声明一致类**"。实测未解除：
   `rl_exp/versions/lizard2/main/v1/NOTES.md` 判据 pass 而步态不合格、明说"按能力基线记账，不按会走路
   记账"；`v2/NOTES.md` 判决 fail；v3 于 2026-10-10 才冻结开训。
2. **离线套件不能联网** ⇒ 闸只能读本地 ref，能抓"没打 tag"、抓不到"打了没推"。而锚点的用途恰恰是
   别人能 checkout（本项的判据落在 `git ls-remote`）⇒ 任何能建的闸都**弱于**它的判据，别把它当等价物。
3. **口径会打架**：家庭侧就同一问题已有检查 —— `rl_exp/tools/verify/check_version_docs.py` 比对
   `git tag --list`，**缺失只报 WARN**，理由写在 versioning.mdc（"tag 缺失仅 WARN，历史前缀可不统一"）。
   单给 harness 提成 red，会让同一仓对同一问题有两套答案而无理由；要改口径就先改规则，再改闸。

## 已落的那一半

`ablation_harness/HARNESS.md` 的版本纪律段添了一句：只写版本号不打 tag = 视同未声明，号成为锚点是在远端
能 checkout 的那一刻。这是**散文纪律、无闸门**——它降低复发概率，不阻止复发。

## 未覆盖边界

- 不碰 `harness-v1.8.0` / `harness-v1.9.0` / `harness-v1.10.0` 三个已推的 tag。
- 不走 pre-commit 钩子：那一刻 tag 只能标正在生成的提交（鸡生蛋）；post-commit 钩子是仓内无先例的新机制
  类别，为这点杠杆不开。
- 不重新评价 `video_matrix.py`（归 `work/closed/2026/video-matrix-gears.md`）。
