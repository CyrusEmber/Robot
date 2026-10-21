# 诊断运行的创建与收尾

当前入口：`rl_exp/tools/diagnose/local_path_view.py`。其它生产入口仍按
`work/active/diagnostic-artifact-lifecycle.md` 推广，不能由本入口推定全覆盖。

从仓根用配置解释器运行；输入取已有报告，不重新采集物理：

```text
<python> -B rl_exp/tools/diagnose/local_path_view.py --source_report <support_report.json> --drive_report <reset_probe_report.json> --root_translation --output_dir rl_exp/out/runs/local-path-view/<new_run> --topic local-path-view --work_id <active_work_id> --owner <executor> --retention_reason "<why retain this run>"
```

目录必须全新。旧 CLI 参数仍可用；新调用显式填写事项与执行者，省略事项时由
`diagnostic-artifact-lifecycle` 承接归属核对，不能据此冒称原实验已经交接。
无需手工补索引：入口在第一份图像写入前创建 `run.json` 并向现有
`artifact_index.json` 注册位置。索引只指向运行记录，状态和保留决定归运行记录。

运行记录保存输入、代码的逻辑身份、当前位置、摘要及复跑参数；新分析同时保存
`input_bindings`，历史绝对路径不再是唯一读点。`analysis.json` 的图像绑定不包含
随后仍需收尾的 `run.json`，运行记录最终绑定分析与所有图像。完整性检查复用
`binding.py` 的摘要实现。开始写产物前及收尾时检查绑定；它不是不可变执行快照。

```text
<python> -B rl_exp/tools/diagnose/artifact_run.py --inspect_run <run_directory>
```

只有 `completed`、唯一索引登记和全部输入/代码/输出摘要同时成立时返回成功。
此检查只读。源码或输入后来改变也会拒绝，先恢复对应字节再复读，不改旧摘要冒充通过。

| 磁盘状态 | 执行者动作 |
|---|---|
| `completed` 且检查通过 | 按记录中的保留理由复用，核对原证据适用范围 |
| `failed` | 按 `owner`、`error`、`next` 排查；保留现场，重新执行用新编号 |
| `registering` / `running` | 先确认原执行者是否仍在写；进程已停止也不能当成功或自动删除 |
| 缺记录、缺登记、损坏或缺文件 | 视为未完成；由原执行者与维护者核对，不凭报告文件存在补成功状态 |

索引写入用操作系统锁协调本入口的并发写者，失败即停止产物写入；人工修改索引仍须
协调。登记或收尾失败会返回失败并尽量写失败记录；连记录也写不了时，目录及原状态
留下供检查识别。强制结束进程不会执行 Python 清理，留下的 `running` 同样不合格。
该入口不自动删除任何失败现场，不自动继续向半写目录追加。

行为回归和完整换根复读：

```text
<python> -B rl_exp/tools/verify/test_artifact_run.py
<python> -B rl_exp/tools/verify/test_artifact_run.py --real_run <completed_run_directory>
```

后一入口要求本机仍具备记录绑定的全部源码与输入，用记录重建临时恢复包，给绑定源码
配置精确的 `-text` 属性以保住运行时原字节；这与一般源码检出的文本规范化用途不同。
它真实 add/commit/clone，两档检出均核字节，阻断旧仓 Python 文件读取，完整生成图像，
比较逐帧像素及关键分析，最后清理自己的恢复目录。失败时返回错误，不能以缺输入的
运行代替有效恢复验证。图像语义仍需人工查看；逐像素相等只证明同环境再生成一致。

输出默认本机保留且被 Git 忽略；索引、源码与验收记录入仓不等于运行字节有外部备份。
恢复证明的范围、结果及已知边界见事项的验收记录指针。
