# 诊断待判定核定与第二批历史归档

## 适用范围

用户选择“核定待判定产物并推进下一批归档”，继续此前授权的不删除范围。对应 [诊断整理事项](../../work/active/diagnostic-artifact-lifecycle.md)。本轮核定十条 pending 路由，沿用已有 reader 归档另两包明确作废的历史台阶对照；不新增盘点/迁移框架，不搬活跃候选链。

## 验收条件

- 分类依据须来自实际报告、已绑定记录和真实消费者，不据 final、日期或无引用判无效。
- 失败试作及字节同一副本保留，不将完成采样、hash 相等或复读成功外推为专项通过。
- 下一批归档保持原字节与判词，旧根实际不存在；真实历史摘要消费者复读和独立 Git 恢复成功，身份/缺映射/错文件拒绝。
- 复用既有实现，新增 schema 保存旧实现拒绝与扩展后同一检查通过的对照；未判定和未接通传递依赖保持原位。

## 结果

### 十条 pending 的具体判定

| 包（路径保持原位） | 本轮类别 | 核定依据与保留理由 |
|---|---|---|
| `rl_exp/tools/diagnose/out/lizard2_e_shared_20261013` | 历史对照 | 与 shared_final 实算摘要相同，绑定同一目标/来源；原命名诊断输入保留，不删除未具名副本 |
| `rl_exp/tools/diagnose/out/lizard2_e_shared_final_20261013` | 历史对照 | 摘要与 `2026-10-13-lizard2-body-drive-plan-review.md:271` 相符；按 :254 的旧 checkpoint 具名测量解释，不作候选性能批准 |
| `rl_exp/tools/diagnose/out/lizard2_e_split_20261013` | 历史对照 | 与 split_final 实算摘要相同；保留 split 角色/来源及原路线，不猜新旧权威 |
| `rl_exp/tools/diagnose/out/lizard2_e_split_final_20261013` | 历史对照 | 摘要与同记录 :271 相符；补入原索引遗漏的该记录引用 |
| `rl_exp/out/lizard2_a_contact_corrected_20261019` | 历史对照 | 实际 `legs.combined.failure`、未完成 loop；真实 `_load` 能读已接受前缀，保留落掌/接触失败 |
| `rl_exp/out/lizard2_a_contact_heading_20261019` | 历史对照 | 首姿态即失败；真实 `_load` 拒绝 `no accepted combined poses`，只声明失败 JSON 可读，不称能回放 |
| `rl_exp/out/lizard2_a_contact_patch_20261019` | 历史对照 | 同样无接受姿态；失败列表似同但实算字节摘要不同，不称重复可删 |
| `rl_exp/out/lizard2_a_contact_delivery_view_20261019` | 历史对照 | 分段交接记录 :55 的实际摘要匹配；保留用户确认回放，不再当动作交付或监督轨迹 |
| `rl_exp/out/lizard2_a_geometry_delivery_20261019` | 当前依赖 | 摘要匹配几何回放记录，`contact-path-correction.md:54,65` 的真实 `--root_report` 路线；保持根轨迹与上游身份 |
| `rl_exp/tools/diagnose/out/baseline_v1_headcheck` | 历史对照 | `2026-09-20-baseline-flat-eval-protocol.md:69` 具名姿态/承重来源；实读五 case 的 stats/下采样 schema，无 target_binding，尚未钉历史渲染器，保留原位 |

E 的 shared 两份均为 SHA256 `e5ec338360d03b2efb6155b677b882167e611d1caae00db93ac690d8edc9e746`，split 两份均为 `8139af7cd49c893a73e107c4606d04dcb6546b8acc0a4da00fcd3bae25214d05`。这仅证明两组字节相同和与记录身份一致，不证明资产/驱动仍适用；报告内 `target_binding.source/target` 仍依赖原本机路径，未迁移任何一份。

A 三份失败报告摘要与真实读取边界保存于 `a-failure-reading-20261021.log`。heading 与 patch 摘要分别为 `69ca4e06e5e354c2b662dd0fcf41db9399258d2fa3598e00c97ea35ef249c76e`、`424d806e3b52f56a64165df1ba1b93d033d17f3d873aacfce55d7d62745e8e87`。保留真实失败，不修 reader 以伪造空轨迹、不过度外推失败为构型不可行。试作确切变体 argv 尚未核齐，索引如实标记；分类为保留失败不要求它成为可复用成功证据。

A 已完成但未具名绑定的 converged、source_seed、edge、edge_heading、rocking 及 root_replay 仍 pending；不能把同 mode、loop 完成或名称暗示套成最终交付。baseline_v1_verts、gait_probe、joint_plots 及其它未处理条目仍保持原位。

### 第二批实际搬移

| 原逻辑根 | 新位置 | 判定依据 |
|---|---|---|
| `rl_exp/tools/diagnose/out/v10_run2` | `rl_exp/out/archive/lizard-v10-support/v10_run2` | `rl_exp/versions/lizard/main/v10/DIAGNOSE.md:106-107` 明确原口径作废、仅留档 |
| `rl_exp/tools/diagnose/out/v10_run3` | `rl_exp/out/archive/lizard-v10-support/v10_run3` | 同上，保留另一实际重复试验，非字节重复删除 |

搬前再次检查旧目录精确文件集、目标不存在、Git 未跟踪和每文件摘要；进程快照仅 MCP server python，没有观察到诊断/Kit/Blender writer。实际 rename 两包共 8 文件、2,842,278 bytes，搬后所有摘要相同，旧根不存在且无 junction/原副本。没有删除，空间释放 0。前轮两包亦保持不变；现在归档共四包，14 个原证据文件。

### 复读与恢复

扩展既有 `archived_support_read.py` 的限定 schema 和历史摘要 AST 选择，沿用 index format 1 与 `read_archive` API。两个新 schema 共用原固定生产源码 `d5ff5ce791262f7825fcb6836e2f6fe353b3a551` / SHA256 `a2c8e807b1c0741fae0ea3aefddca879937ec3edfd6bbd65b6d4a9a7b83c7009`，实际 source 快照沿用 metadata 的 smoke_p1c 源，不增加源码副本。

Phase3 从固定历史 main 只取 p3 摘要段，消费存储 stats，不执行整 main、imports、仿真或曲线再统计。三个文件的 `case` 必须对应 r0/r1/r2；按固定 rep 文件名顺序渲染，原摘要的每行三列与此顺序全文相符。高度顺序来自原绑定 summary 行序，并与每个 report 的 stats 档位集合相等；这是特定归档的复读契约，不是通用运行顺序/全量日志证明。缺/多档位均拒绝，未扩展兼容未批准 schema。固定源码 pin 是执行信任边界，有限 builtins 不是安全沙箱。

- 同一新增 Phase3 回归在本轮修改前 HEAD reader 上失败：`unknown logical root: .../v10_run2`；当前扩展后通过，不回退共用工作树源码。
- 扩展与搬后回归均 7/7；四包摘要实际全文比对通过，旧根访问含宿主绝对路径均禁用，缺映射、错摘要、源码 pin/路径逃逸/错 case/缺额外文件均拒绝。
- 真实消费者破坏对照：series 任意变化且刷新测试摘要不影响渲染；stats 改动且刷新摘要会在原摘要全文比对失败。高度行重排测试只声明按绑定原摘要顺序复读，不称重新证明历史采样顺序。
- 独立临时 Git 实际 add/commit/clone，两档 `core.autocrlf=true/false` 检出后消费 14 原证据＋2 源码＋索引，临时原 bundle 已移除，旧根及宿主原路径不可读。
- 搬后 normal、`-O`、`PYTHONOPTIMIZE=1/2` 下四包 CLI 均重现原摘要；显式身份拒绝不依赖 assert。
- 全仓既有闸门 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 53.4s, jobs=4)`；新增 Phase3 回归沿用按需入口，没有添加默认闸门条目。

### 索引与独立审查

`artifact_index.json` 仍 170 条；本轮十条 pending 改为九历史对照和一当前依赖，pending 从 142 降为 132，历史对照 25、当前依赖 11、容器 2。四包归档映射与全局位置同步，其余未因预算/日期被取消或移出。此计数仅对既有索引，不保证会话期间全部新增文件已登记或容器内部归属闭合。

新上下文有界静态审核 Phase3 与本批索引，未发现阻断归档的问题。审核建议已去测试重复维护 PINS，并补 baseline 实读元信息。审核关于 E 摘要/记录缺失、归档目录不存在的说法经本体复核不成立：索引明确含 :254,271 的 basis 与四份 SHA256，实际目录和 CLI 已验证。其余关于顺序只按绑定摘要解释、非通用 renderer、单副本及传递链未齐的边界保留，审核不是全事项关闭审核。

## 证据引用

- 路由：`rl_exp/tools/diagnose/artifact_index.json`，本轮落盘 SHA256 `c9410882e01f56da3a69e03aca12688961b122e4d1803c8c5b1f1fc3177ec439`。
- 四包映射：`rl_exp/tools/diagnose/support_archive_index.json`，SHA256 `fa76f024ba74d2f0116bf32403af8ec5b1f2ab3c13f6f3deb7e236dd19a68b48`。
- 实现/回归：`rl_exp/tools/diagnose/archived_support_read.py`、`rl_exp/tools/verify/test_archived_support_read.py`。
- 本机日志均在 `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261020-preflight/`：
  - `phase3-recovery-red-20261021.log`，SHA256 `7f471b2ce6fe927cb0398c8f1cf4a0cc7c0bf2c0c5bcceed65a50bd9983de181`。
  - `phase3-recovery-green-20261021.log`，SHA256 `7fa27258092a01ccc26cc4ee4225f7d527c4094c6d6db298de0ffdc5d9bc63ff`。
  - `phase3-recovery-after-move-20261021.log`，SHA256 `abd75d0be8d6559d7de06bde7554e992e8b5b7c98190955d0bbe7b29fb616b0c`。
  - `a-failure-reading-20261021.log`，SHA256 `d6c7cfb318e6760c2fce776d61c0498fea4325746c6c972bd513003e8d99d839`。

仓根复读：

```text
python -B rl_exp/tools/diagnose/archived_support_read.py --index rl_exp/tools/diagnose/support_archive_index.json --package rl_exp/tools/diagnose/out/v10_run2
python -B rl_exp/tools/diagnose/archived_support_read.py --index rl_exp/tools/diagnose/support_archive_index.json --package rl_exp/tools/diagnose/out/v10_run3
<配置解释器> -B rl_exp/tools/verify/test_archived_support_read.py
```

恢复与回退沿前轮记录：完整归档布局及两份源码在新存储根，传 `--storage_root` 运行实际 reader；旧根不可用。若回退，先核原目录不存在、目标精确文件集/摘要及没有 writer，再原样 rename 回原根，并同轮更新映射/路由和重验，任何冲突不覆盖。

## 未覆盖边界

- 归档四包仍本机单副本且 Git 忽略；索引、实现与记录入仓不等于材料从云端可恢复，外部备份尚未建立，不删除唯一证据。
- 132 个 pending 及新增输出、其它输出根、容器内部分类、生产入口登记与日常收尾尚未完成，不将本轮十条核定当全部清单闭合。
- A 试作、E 命名诊断的上游资产/manifest 仍含原绝对路径；未接活跃 local_path/runtime 的迁移定位，不搬这些包，不改历史身份来绕授权。
- 本轮真实回归需要本机证据及 Git 历史，不是材料缺失也能通过的跨机小样本；Git 恢复验证的是隔离携带材料后消费者可用，不是既有远端具备材料。
- 未起仿真、未改构型/PD/阈值、未恢复作废数值有效性，未代替原专项或整个整理事项独立关闭审核；事项仍 in_progress。
