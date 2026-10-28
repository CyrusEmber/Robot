# 左前腿首跑失败报告的透明压缩

## 适用范围

`work/active/diagnostic-artifact-lifecycle.md` 阶段 3。只处理 `rl_exp/out/lizard2_b_lf_lift_20261019_run01/` 的 `report.json` 和 `failure.json`；两份不完整 JSON 为不同写入失败现场，不合并逻辑身份，不改历史判词、证据索引或可恢复样本。

## 验收条件

- 两个路径、原字节与失败状态不变，两个文件保持独立；原证据索引逐项直接复读。
- 同卷先建立可校验备份，在隔离根分别恢复并与原件逐字节比较；停写与文件身份检查后仅压缩明确的两个文件。
- 压缩后从原路径复读全部绑定，核摘要和原 JSON 失败判词；说明存储方式、回退和备份边界。

## 结果

两个原件各 20,041,372 字节，SHA-256 均为 `7292618ba857ec56132e8fa5566bf853979259f575c5fd1e83475804924c10b3`；均未被 Git 跟踪，且是不同文件、各为单硬链接。处理前按 ZIP manifest 在系统临时根恢复两份，分别与原件逐字节相等。处理前检查文件非重解析点、唯一链接、原摘要和独占打开；相关进程命令行快照未发现写者，不保证未来无人写入。

E: 为 NTFS，分别对两个文件启用 Windows 原生透明压缩，目录本身未设置压缩。压缩后每份逻辑大小不变，`compact /Q` 显示两份各存储 9,703,424 字节；以压缩前逻辑大小估算减少 20,675,896 字节，再扣新增归档 4,051,264 字节，净节省估计约 15.85 MiB。压缩前实际占用未留可复核读数；此估算不是实测磁盘空闲空间变化。两份路径仍可直接读取，与归档字节逐项相等、摘要不变；`evidence_index.json` 自身摘要不变且 13 项均从原路径校验通过，两个不完整 JSON 仍在原位置解析失败。未触碰 `recovered_samples.json`、源码或训练进程。

## 证据引用

原故障、两份历史身份及真实复读入口见 `acceptance/records/2026-10-19-lizard2-single-leg-lift.md`。本机备份 `rl_exp/out/archive/diagnostic-development/single-leg-failure-20261019-relative.zip`，4,051,264 字节，SHA-256 `730c81e1b45bd51a83bc28a362a866eabc531d4d708c6b6a30022e0f9d25a5bb`；`manifest.json` 分别绑定两个原仓库相对路径，均指向同一个 SHA blob。该包与原文件同卷，不能当异地备份，检出 Git 亦不包含这些字节。

检查透明压缩可运行 `compact /Q rl_exp\out\lizard2_b_lf_lift_20261019_run01\report.json rl_exp\out\lizard2_b_lf_lift_20261019_run01\failure.json`。如需取消压缩，先核对停写、备份摘要和磁盘可用空间，分别对这两个具名路径运行 `compact /U` 并检查每次结果，之后逐个重算上述 SHA-256 与完整索引绑定；不得递归处理目录。

在仓根运行以下命令，在独立系统临时目录恢复两份；命令先校验整包摘要、清单和成员，再核各 blob 摘要，不会覆盖原件。使用后清理打印的临时目录。

```cmd
python -B -c "exec('import zipfile,json,tempfile,hashlib\nfrom pathlib import Path,PurePosixPath\na=Path(\'rl_exp/out/archive/diagnostic-development/single-leg-failure-20261019-relative.zip\'); want=\'730c81e1b45bd51a83bc28a362a866eabc531d4d708c6b6a30022e0f9d25a5bb\'; hashlib.sha256(a.read_bytes()).hexdigest()==want or (_ for _ in ()).throw(ValueError(\'archive digest\')); z=zipfile.ZipFile(a); m=json.loads(z.read(\'manifest.json\')); expected={\'rl_exp/out/lizard2_b_lf_lift_20261019_run01/report.json\',\'rl_exp/out/lizard2_b_lf_lift_20261019_run01/failure.json\'}; set(m[\'files\'])==expected and len(z.namelist())==len(set(z.namelist())) and set(z.namelist())=={\'manifest.json\',\'blobs/7292618ba857ec56132e8fa5566bf853979259f575c5fd1e83475804924c10b3\'} and z.testzip() is None or (_ for _ in ()).throw(ValueError(\'manifest\')); t=Path(tempfile.mkdtemp(prefix=\'robot-lift-restore-\')); print(\'RESTORE_DIR\',t,flush=True)\nfor k,v in m[\'files\'].items():\n rel=PurePosixPath(k); not rel.is_absolute() and all(p not in (\'\',\'.\',\'..\') and \':\' not in p for p in rel.parts) or (_ for _ in ()).throw(ValueError(k)); b=z.read(\'blobs/\'+v[\'sha256\']); len(b)==v[\'size_bytes\'] and hashlib.sha256(b).hexdigest()==v[\'sha256\'] or (_ for _ in ()).throw(ValueError(k)); p=t/Path(k); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b); print(\'RESTORED\',p)\n')"
```

可从仓根直接复读原索引的 13 项绑定：

```cmd
python -B -c "import json,hashlib; from pathlib import Path; r=Path.cwd(); p=r/'rl_exp/out/lizard2_b_lf_lift_legs12_20261019/evidence_index.json'; d=json.loads(p.read_bytes()); print([(k,hashlib.sha256((r/k).read_bytes()).hexdigest()==v) for k,v in d.items()]); print('INDEX_OK',hashlib.sha256(p.read_bytes()).hexdigest()=='33cb06ab5f1613cd93709f9aef42baa9350907ae1c82c66f9f9172fe1a921dc4')"
```

独立审核实际核两个压缩文件的不同文件身份、单硬链接、摘要及不完整判词，复读索引 13 项并在隔离根恢复两份字节；归档仅同卷。审核指出恢复命令缺失与净收益口径不清，已补上述命令并注明估算。新上下文随后原样运行恢复和索引命令，逐字节对照两份文件，13 项绑定通过；错误归档摘要在 `-O` 下明确拒绝。压缩前的实际占用无法事后重证，整个事项未审核关闭。

## 未覆盖边界

本批未删除文件、不改变路径或引入共享可写硬链接；未建立外部备份，未断言全系统无写者。压缩属性为本机 NTFS 特性，移动到非 NTFS 卷可能不保留压缩状态，但必须仍核对原字节。其它输出、写入者接入和历史清理仍由原事项承接。
