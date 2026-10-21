# 诊断产物整理计划与迁移证据独立审核

## 适用范围

用户请求审核 `work/active/diagnostic-artifact-lifecycle.md`。本上下文未参与此前实施，核对计划、最新验收记录、迁移读取器与回归；基线 HEAD 为 `5fb6153`。本次不是全事项关闭审核，不接管其它会话的工作树改动。

## 验收条件

以事项既有要求为准：旧证据根不可访问时真实消费者仍可用；身份与摘要不可丢失；重新检出恢复不能依靠原机器绝对路径。已声明未完成的生产者治理、其它消费者、外部备份等仍是未完工作，不重复作为新发现。

## 结果

保留 `in_progress`。继续迁移前需处理以下三项；没有修改实现或搬动原始证据。

1. **P1：旧根隔离测试漏拦实际哈希读取。** `test_artifact_relocation.py:deny_old` 只替换 `Path.open`；`runrecord/binding.py:sha256_file` 实际使用 `builtins.open`。因此旧根及其 alias 的哈希读取仍能访问原磁盘，现有测试不能支持“旧证据根均不可读”的完整结论。实测仅拦 `Path.open` 时，迁移后的 drive 分支仍读旧文件摘要并正常返回；补拦 `builtins.open` 后才观察到该旧路径读取。应覆盖真实读取通道或采用进程级文件隔离，并先注入一次直接读取旧证据的破坏对照，证明隔离本身能拦住，再复验各消费者。不是要求对不相关系统文件禁读。

2. **P2：drive 迁移后会静默丢失摘要绑定。** `local_path_view._drive_prerequisites` 第一次读报告调用 `artifact_path(path)`，但返回字段 `drive_report_sha256` 仍使用 `digest(path)`。旧路径不存在时 hash helper 返回 `None`，调用成功而产物带空摘要；若旧副本存在且内容不同，还可能给新读取数据绑定旧副本摘要。使用真实历史 drive/report/rates，复制 drive 至临时新根并登记真实映射，屏蔽旧路径后实测返回 `None`，预期原摘要为 `36344c8af1ccf56552c931d252008fb50a9b6951265e8fe083f2079bd340d115`。应分别保存逻辑身份与实际读点，摘要从已验证的新位置计算；补旧根缺失、旧副本冲突两种回归，并覆盖 `_run` 的该分支，不能只验证 `_load`。

3. **P2：重新检出测试没有验证代码换根后的恢复。** 当前 `test_recheckout_bytes_and_real_consumers` 只复制证据及索引到新仓，consumer/FK 仍来自原工作树。`local_path_view._load` 用当前 `csc.__file__` 的绝对路径索引历史 `code_sha256`；`palm_spatial_runtime.check_build` 将映射恢复的原绝对身份与当前代码根推导的 `BUILD` 比较。隔离对照中，复制 FK 后摘要完全相同，仅改变模块文件位置即报 `FK changed since collection`；只把 `BUILD` 改为新根下同一逻辑检查点即报 `only checkpoint_v3/build.json is authorized`。这是局部变量换根对照，不冒称已经完成全量跨机恢复。最新实施记录已诚实限定其恢复范围，但计划关闭条件还需要明确落实“代码和证据一起换根”的真实子进程验收，并保留原授权边界，不能简单去掉校验。若该能力暂缓，应作为未完成迁移前置保留。

本次独立运行：迁移回归 **6/6 通过**，全仓 **37/37 通过**（52.5 s）。闸门绿色没有覆盖以上反例。执行环境配置解释器启动在沙箱内被 uv trampoline 拒绝，使用获准的提升权限执行完成；不是测试逻辑失败。

## 证据引用

- 计划：`work/active/diagnostic-artifact-lifecycle.md` 的“迁移前必须补齐”和“迁移与恢复成立”。
- 原实施记录：`2026-10-21-diagnostic-artifact-decoupling-cleanup.md`，尤其“行为证明与检查”和“未覆盖边界”。
- 读取与验证：`rl_exp/tools/diagnose/local_path_view.py` 的 `_drive_prerequisites`、`_load`、`_run`；`rl_exp/tools/diagnose/palm_spatial_runtime.py:check_build`；`rl_exp/tools/runrecord/binding.py:sha256_file`；`rl_exp/tools/verify/test_artifact_relocation.py`。
- 真实 drive 复读参数取 `rl_exp/out/lizard2_palm_combined_view_20261016_drive/analysis.json` 的 `source_report`、`time_mapping_prerequisites`、`drive_limit_prerequisites.drive_report`。原文件只读，临时复制自动清理。

仓根复读既有回归与闸门：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_artifact_relocation.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/offline_suite.py --jobs 4
```

下面是本轮两个反例的可复读 Python 入口内容；可通过 PowerShell 单引号 here-string 管道传给配置解释器的 `-B -`，不需在仓根新建脚本。只创建自动清理的临时副本，保留所有原文件：

```python
import builtins, json, shutil, sys, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, 'rl_exp/tools/verify')
import test_artifact_relocation as t
case = t.RelocationTest()
case.setUp()
try:
    with patch.object(t.view, 'ArtifactPaths', lambda: case.paths):
        t.view._load(t.CONTACT / 'report.json')
        fk = case.root / 'rl_exp/tools/verify/check_self_collision.py'
        fk.parent.mkdir(parents=True)
        shutil.copyfile(t.view.csc.__file__, fk)
        assert t.routes.sha256_file(fk) == t.routes.sha256_file(Path(t.view.csc.__file__))
        with patch.object(t.view.csc, '__file__', str(fk)):
            try:
                t.view._load(t.CONTACT / 'report.json')
            except AssertionError as exc:
                print('NEW_CODE_ROOT_LOAD_REJECTED:', exc)
    with patch.object(t.runtime, 'ArtifactPaths', lambda: case.paths):
        t.runtime.check_build(t.runtime.BUILD)
        new_build = case.root / t.runtime.BUILD.relative_to(t.REPO)
        with patch.object(t.runtime, 'BUILD', new_build):
            try:
                t.runtime.check_build(new_build)
            except ValueError as exc:
                print('NEW_CODE_ROOT_BUILD_REJECTED:', exc)
finally:
    case.doCleanups()

a = json.loads((t.REPO / 'rl_exp/out/lizard2_palm_combined_view_20261016_drive/analysis.json').read_text())
r = json.loads(Path(a['source_report']).read_text())
p = Path(a['drive_limit_prerequisites']['drive_report'])
with tempfile.TemporaryDirectory(prefix='drive-review-') as tmp:
    root = Path(tmp)
    dest = root / 'new'
    dest.mkdir()
    shutil.copyfile(p, dest / p.name)
    idx = root / 'index.json'
    idx.write_text(json.dumps({'format': 1, 'packages': [{
        'logical_root': p.parent.relative_to(t.REPO).as_posix(),
        'current_location': 'new',
        'relocation': {'original_absolute_root': str(p.parent),
                       'files': {p.name: t.view.digest(p)}}}]}))
    routes = t.routes.ArtifactPaths(idx, root)
    raw_open, raw_path_open = builtins.open, Path.open
    attempts = []
    def blocked(path, *args, **kwargs):
        if Path(path).resolve() == p.resolve():
            attempts.append(str(path))
            raise FileNotFoundError(str(path))
        return raw_open(path, *args, **kwargs)
    def blocked_path(path, *args, **kwargs):
        if path.resolve() == p.resolve():
            raise FileNotFoundError(str(path))
        return raw_path_open(path, *args, **kwargs)
    with patch.object(t.view, 'artifact_path', routes.resolve), \
            patch.object(builtins, 'open', blocked), \
            patch.object(Path, 'open', blocked_path):
        result = t.view._drive_prerequisites(r, p, a['time_mapping_prerequisites'])
    print('OLD_DIGEST_READ_ATTEMPTS', len(attempts))
    print('RETURNED_DRIVE_SHA256', result['drive_report_sha256'])
```

当前输出：两个换根拒绝如上；`OLD_DIGEST_READ_ATTEMPTS 1`、`RETURNED_DRIVE_SHA256 None`。这是缺陷复现，命令退出零不表示迁移能力通过。

## 未覆盖边界

未全量核定所有存量、混合子树或 ZIP 恢复；未启动 Isaac/物理/训练；未验证完整跨机新检出。没有重新审核原机器人/驱动结论。当前其它会话的 dirty 文件不属于本轮。修复后须重跑失败对照与受影响消费者，再更新实施证据并复审；本记录不能充当未来修复后的通过证明。
