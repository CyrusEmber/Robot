# 十七轴受载样本透明压缩

## 适用范围

`work/active/diagnostic-artifact-lifecycle.md` 阶段 3；仅对 `rl_exp/out/lizard2_b_loaded_axes_20261021/` 的 17 个逐轴样本执行 NTFS 透明压缩。原路径、字节和原物理失败判词保持不变；未有意处理报告、进度、source、manifest、audit 和其他运行数据，当前这些文件及目录均未压缩；压缩前未保留其它文件完整属性基线，不据此证明其历史状态。未修改机器人或训练配置。

## 验收条件

- 用真实 report 的具名单轴集合及下游绑定逐文件限定范围，核身份、写者与原摘要，不用通配符覆盖目录。
- 原字节预先备份，在隔离目录真实恢复全部样本并逐项核摘要；压缩前后用原路径运行真实审计和恢复链自检。
- 不将审计一致当作物理性能通过，不将同卷副本当作外部备份；明确可复读和回退方式。

## 结果

`report.json` SHA-256 为 `7a9141ed06cf187718309c2db7e17f9a5657fcace542caa7827f76dc7ccc8570`，下游 gain20 报告 SHA-256 为 `4e3d140b619bc9236da4cead7322c15c9b0f887a1efe031b12087f6019ac3f7a`。以 report 中 17 个 `selected_cases` 与 cases 顺序、单轴命令一致限定目标，逐个匹配 gain20 `resume.files_sha256`；报告、进度文件等不属于目标。处理前核摘要、大小、Git 未跟踪及忽略状态、单硬链接、非重解析点和独占打开；相关进程快照未见写者，不能保证未来无写者。

先建立 manifest/blob 同卷副本，恢复 17 份至隔离系统临时目录，逐项大小与 SHA-256 均与原件和下游绑定一致。随后逐个启用 NTFS 文件压缩，逐项重验 SHA-256、大小与压缩属性。17 份逻辑大小共 342,369,700 字节，压缩后工具报告存储 149,827,584 字节；新增副本 34,407,380 字节。按压缩前逻辑大小估算净减少 158,134,736 字节，约 150.8 MiB；压缩前实际磁盘分配未留可复核读数，这不是实测空闲空间变化。

前后运行相同 `self_weight_audit.audit()`，结果均与原 `audit.json` 逐字段相等：57,800 步、10 个原判词通过、7 个保持精度未达；未把审计通过误称物理判词通过。压缩后实际运行 gain20 持久入口的 `--self_check`，输出 `SPATIAL_TRACKING_SELF_CHECK_OK`、`SPATIAL_TRACKING_FRESH_INPUT_CHECK_OK` 和 `SELF_WEIGHT_SUITE_CHECK_OK`；未启动 Kit 或重跑物理。上述自检不能单独证明全部跨机恢复或后续训练能力。独立新上下文复核了 17 项当前压缩属性和下游绑定、真实审计及自检、ZIP 恢复；其指出原恢复命令依赖原报告和其他文件缺压缩前属性基线，已将恢复入口改为只读固定摘要 ZIP，并收窄历史状态结论。修订后新上下文在仅含 ZIP 副本的新根执行原命令，恢复 17 项并对照预先固定的下游摘要；隔离钩子对旧 report 的 `builtins.open`、`io.open`、`os.open` 及生产 ZIP 的打开破坏对照均拒绝，恢复期间无额外旧根读取。钩子只覆盖 Python `open` 事件，不能外推全部原生 I/O；`-O` 错误摘要在前次复核中拒绝。仓库离线套件执行至 36/37 时，另一个在办改动 `rl_exp/tools/diagnose/column_coupling_probe.py` 触发摘要单源闸门，最后一项跳过；未宣称全套通过。

## 证据引用

本机同卷回滚副本 `rl_exp/out/archive/diagnostic-development/loaded-axes-samples-20261028.zip`，34,407,380 字节，SHA-256 `77c46706f70d5fb738fc071af35e61195f67fa2a92907b2feaffcd25206e1903`。`manifest.json` 按原仓库相对路径记录每份文件大小与 SHA-256；字节位于 `blobs/<sha256>`。原实验和持久自检入口见 `acceptance/records/2026-10-21-lizard2-loaded-remaining-axes.md` 与 `acceptance/records/2026-10-21-lizard2-loaded-gain20.md`。该 ZIP 不能抵御 E: 卷故障，也不随 Git 检出。

从仓根执行以下命令，使用固定的 ZIP 整包摘要及清单在新的系统临时目录恢复 17 份，不依赖原 report；打印恢复目录后需人工核验并清理，不覆盖原件。报告和其它运行数据不在此包中。

```cmd
python -B -c "exec('import zipfile,json,hashlib,tempfile\nfrom pathlib import Path,PurePosixPath\na=Path(\'rl_exp/out/archive/diagnostic-development/loaded-axes-samples-20261028.zip\'); want=\'77c46706f70d5fb738fc071af35e61195f67fa2a92907b2feaffcd25206e1903\'; h=lambda p:hashlib.file_digest(p.open(\'rb\'),\'sha256\').hexdigest(); h(a)==want or (_ for _ in ()).throw(ValueError(\'archive digest\')); z=zipfile.ZipFile(a); m=json.loads(z.read(\'manifest.json\')); prefix=\'rl_exp/out/lizard2_b_loaded_axes_20261021/\'; keys=list(m[\'files\']); len(keys)==17 and len({x.casefold() for x in keys})==17 and len(z.namelist())==len(set(z.namelist())) and set(z.namelist())=={\'manifest.json\'}|{\'blobs/\'+v[\'sha256\'] for v in m[\'files\'].values()} or (_ for _ in ()).throw(ValueError(\'manifest\')); t=Path(tempfile.mkdtemp(prefix=\'robot-axes-restore-\')); print(\'RESTORE_DIR\',t,flush=True)\nfor rel,v in m[\'files\'].items():\n q=PurePosixPath(rel); len(q.parts)==4 and q.as_posix().startswith(prefix) and not q.is_absolute() and all(x not in (\'\',\'.\',\'..\') and \':\' not in x and \'\\\\\' not in x for x in q.parts) and q.name.endswith(\'.json\') or (_ for _ in ()).throw(ValueError(rel)); p=t/Path(rel); p.parent.mkdir(parents=True,exist_ok=True)\n with z.open(\'blobs/\'+v[\'sha256\']) as src,p.open(\'xb\') as dst:\n  for chunk in iter(lambda:src.read(1048576),b\'\'): dst.write(chunk)\n p.stat().st_size==v[\'size_bytes\'] and h(p)==v[\'sha256\'] or (_ for _ in ()).throw(ValueError(rel)); print(\'RESTORED\',rel,flush=True)\n')"
```

真实只读审计入口：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -c "import json,sys; from pathlib import Path; sys.path.insert(0,'rl_exp/tools/diagnose'); import self_weight_audit as a; r=Path('rl_exp/out/lizard2_b_loaded_axes_20261021'); x=a.audit((r/'report.json').resolve()); y=json.loads((r/'audit.json').read_bytes()); print('EQUAL',x==y,'STEPS',x['steps'],'CASE_PASSED',sum(c['passed'] for c in x['cases'])); sys.exit(0 if x==y else 1)"
```

取消 NTFS 压缩前须确认停写、备份可恢复及足够磁盘空间；仅从上述 ZIP manifest 的 17 个具名路径逐个执行 `compact /U`、逐项检查退出码和 SHA-256，完成后再次运行真实审计和自检。不能对整目录递归操作；任何失败停止并保留现场。

## 未覆盖边界

同卷回滚副本不是独立外部备份；快照和独占打开后释放不阻止未来写者。压缩不改变可见路径或逻辑文件体积，迁往非 NTFS 卷时可能恢复为未压缩状态，仍须核原字节。未验证所有外部动态消费者、PhysX 原生复制或其它诊断产物；未完成总事项审核。
