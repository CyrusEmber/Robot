# 固定机身回放整理前置阻塞

## 适用范围

事项：`work/active/diagnostic-artifact-lifecycle.md` 阶段 3。本批仅核查三个固定机身回放目录，未迁移、归档或删除；不涉及 `rl_exp/out/lizard2_palm_combined_view_20261016_drive/`。当前不能证明三份历史渲染源码和真实重跑满足要求，因此保留原件。本机原件被 Git 忽略，不构成外部备份。

## 验收条件

保留原字节和实际依赖，先确认历史源码与真实重跑，再执行隔离恢复、消费者复验和删除。

## 结果

三个目录各 7 文件，合计 25,325,142 字节；目录与直接文件的 Windows reparse 标志均未设置。三个分析 JSON 真实解析，其 `artifacts_sha256` 与各自六张图片的实际 SHA-256 一致。使用 `E:\IsaacLab\env_isaaclab\Scripts\python.exe` 的 Pillow 12.1.1 对所有图片逐帧 `load()`，六个 GIF 各 109 帧，12 张 PNG 均解码。六张图在三目录之间逐字节一致。

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `lizard2_a_fixed_replay_20261019/analysis.json` | 1,468,845 | `47359efce435ac5d2a57417dd9bbf3e9a10c0bea822d19a4759c79da847dd278` |
| `lizard2_palm_combined_view_20261016/analysis.json` | 1,465,129 | `40d95654080d17dc3667f0ba0040363c402a7c4bc484a31e8c9eeaec80c7d11b` |
| `lizard2_palm_combined_view_20261016_final/analysis.json` | 1,468,808 | `6c0d5eeb13a317d271169bdf6f152669a40c51d0f225e1608a71898c473e148c` |
| 每目录 `combined_side.gif` | 2,955,745 | `adfb24816f5bda54c4c58857e7c390f91614f2a1691d7585eabf3961e098642c` |
| 每目录 `combined_top.gif` | 2,936,266 | `e3f091409463b4eb3ef2b98e72325d76d21eda89bbbfd3d1bea2c66ab71c8fc2` |
| 每目录 `lf_trajectory.png` | 265,266 | `1fc7645adbc2d4e7369d7109fe51209b035034b33a0d43e463c147cd7a4d7ee0` |
| 每目录 `rf_trajectory.png` | 269,324 | `9d072652c23c031aa71c19087147044c3ffea85e578356b8da92272005e373d5` |
| 每目录 `rl_trajectory.png` | 273,466 | `6b299c463a426d672d2944a92d91f576ee5abfb42691e15207267d16053d09c9` |
| 每目录 `rr_trajectory.png` | 274,053 | `7bc8c9128553ab13ab39e8705d2ded99a356858e20db7e0fa0192b64c1d3e981` |

表中路径相对 `rl_exp/out/`。三目录未被 Git 跟踪，`.gitignore` 忽略 `rl_exp/out/`。`acceptance/records/2026-10-19-lizard2-a-geometry-replay.md:20` 和 `acceptance/records/2026-10-19-lizard2-a-delivery-plan.md:19` 引用历史回放；检索未发现这三条固定路径的代码消费者。相似但不属于本批的 drive 目录被 `rl_exp/tools/verify/test_artifact_relocation.py:432` 读取。进程命令行快照未见相关生产者，不能证明没有间接 writer 或后续写入。

共同源报告 `rl_exp/out/lizard2_palm_support_schedule_20261016/report.json` 实际 SHA-256 为 `85ab07309f4eaca67fb2895b11f30616948d1d19d438640465910041926e0086`。当前 `rl_exp/tools/diagnose/local_path_view.py` 的 `_load()` 实际读取该报告、build 和资产后，在 FK 身份校验处报 `AssertionError: FK changed since collection`；未跳过身份校验，也未声称完成真实重跑。历史 FK 复读线索见 `acceptance/records/2026-10-22-diagnostic-local-path-consolidation.md`，但本次尚未证明此三份回放的完整旧渲染器恢复和重跑。

三份分析绑定的 `local_path_view.py` SHA-256 分别为：

- fixed：`2b54a951af27dbaa9d297d1d44a7967339b07c74813fd2a117fe14027919bc0b`，在可达 Git 历史找到提交 `e4159118a5da38c194b4f0f8166a60c2130f7752`。
- combined：`9668bf0a179d415c0b32c2e829d611963d0c031831228a2dd7e7a6c5cbd5429c`，未在该文件可达 Git 历史、`rl_exp/out/archive/` 六个 ZIP、大小 1–300,000 字节的不可达 Git blob、输出树内至多 300,000 字节的 `.py`/`.txt` 文件及已登记 run 的 code 绑定中找到。
- final：`17e9fedc9afaaebed823a2a391aed72f7e5ebace88fb8f30e514179057189b47`，同样未在上述范围找到。

未穷举其他磁盘位置、外部备份、输出树的非 `.py`/`.txt` 文件或其他 Git 对象尺寸，不断言源码永久丢失。固定机身回放的六张相同图片不证明三份不同分析对应的渲染源码可替换。

## 证据引用

原件、引用和历史复读线索见上文；本次核查未生成归档或独立运行日志。

## 未覆盖边界

整理执行者继续查找两份精确源码，恢复匹配历史 FK、源报告与全部实际资产，在隔离根按原身份真实重跑并核对。满足阶段 3 的完整恢复、消费者、逐文件重校和 writer 要求后，再按现有 manifest/blob 归档并处置原件；缺任一项继续保留。尚未运行旧根失效的恢复测试，未更新位置映射或改写历史引用。
