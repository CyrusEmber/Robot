# 输出根一次性提交脚本归档

## 适用范围

对应 `work/active/diagnostic-artifact-lifecycle.md`。本批仅处置输出根中已执行的提交、文档修正和事项路由去重辅助脚本；不涉及诊断样本、活动复读入口或 Git 索引文件。

## 验收条件

- 固定文件、摘要和 Git 状态；核对真实用途、引用与正在执行的进程。
- 用既有 manifest/blob 格式归档，隔离目录逐文件恢复核对后再移除原副本。
- 索引登记本机归档和恢复入口；归档不冒称远端备份。

## 结果

候选是 6 个提交脚本、1 个训练条件文档修正脚本和 1 个事项证据路由去重脚本，均非诊断生产或复读入口。对应六个提交已在 Git 历史中；训练条件修正和证据路由去重后的文档已在现行记录中。8 个脚本共 13,924 字节，均被忽略、未被 Git 跟踪。进程命令行快照未发现实际执行候选脚本的进程；快照不是写入锁。

原文件以逐路径大小和 SHA-256 写入归档 manifest，8 个 blob 在独立临时根逐文件解包，与原文件字节相等；删除前重新核对归档摘要、全部原件、实际绝对位置和 Git 跟踪状态。已删除 8 个原副本，删后确认旧位置均不存在，并再次解包核验 8 个文件的大小和 SHA-256；两次临时恢复目录均已清理。归档是本机单副本，不能代表已建立外部备份。

## 证据引用

本机归档：`rl_exp/out/archive/diagnostic-development/commit-scratch-20261028.zip`，9,212 字节，SHA-256 `d5b7c1d45723f981482015477ef0063f7ebbb276c89a7779673a47ed26cab4f9`。`manifest.json` 的 `files` 按原仓库相对路径映射 `size_bytes`、`sha256`；字节位于 `blobs/<sha256>`。本批仅含：

- `rl_exp/out/commit_joint_force_code_20261021.py`、`rl_exp/out/commit_joint_force_docs_20261021.py`
- `rl_exp/out/commit_standing_force_code_20261022.py`、`rl_exp/out/commit_standing_force_docs_20261022.py`
- `rl_exp/out/commit_symmetric_pd_20261021.py`、`rl_exp/out/commit_training_consistency_20261022.py`
- `rl_exp/out/correct_training_consistency_20261022.py`、`rl_exp/out/dedup_left_knee_work_routes.py`

由标准库 `zipfile` 读 manifest，在隔离临时根恢复并重新计算摘要；不要在工作树恢复或执行这些改文档和提交脚本。现有同格式恢复说明见 `acceptance/records/2026-10-21-diagnostic-artifact-decoupling-cleanup.md`。

独立只读复核：新上下文重新计算整包 SHA-256，在内存逐项解压核对 8 个 blob 的大小及摘要，确认 manifest 与本记录路径一致、无重复或额外成员、8 个原路径均不存在，索引指向一致。复核不能反证删除前原件、进程状态和临时恢复过程，以上删前事实仍依执行者记录。

检查：事项格式通过；产物定位器成功加载索引；项目解释器运行离线闸门 37/37 通过。系统默认 Python 因缺少 `gymnasium` 无法运行完整离线套件，后改用项目环境。

## 未覆盖边界

本批不移动有消费者的代码快照、诊断样本、进度文件、其它散文件或可能仍有用途的 Git 暂存索引；不改变实验结果。输出目录存量与新增生产入口仍由原事项继续承接。
