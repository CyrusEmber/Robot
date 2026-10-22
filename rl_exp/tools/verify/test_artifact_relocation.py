# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Real local-path/runtime readers with original evidence roots inaccessible.

Requires the local checkpoint and contact report. Does not simulate or render.
Copies bound bytes into TemporaryDirectory, removes its staging copy, and denies
reads through old paths, including resolved aliases. CLI optimization protection
is covered by test_local_path_optimization.py. No production evidence is changed.
"""

import builtins
import argparse
import importlib.util
from contextlib import contextmanager, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'rl_exp/tools/diagnose'))
import artifact_paths as routes
import local_path_view as view
import palm_spatial_runtime as runtime
import test_diagnostic_git_boundary as git_boundary

CONTACT = REPO / 'rl_exp/out/lizard2_palm_local_path_contact_20261015'
CHECKPOINT = runtime.BUILD.parent

# The audit hook is process-local and installed BEFORE importing the restored code.
# It catches the CPython open event for builtins/io/FileIO/os.open, including hashes.
RECOVERY_CHILD = r'''
import builtins, io, json, os, sys
from pathlib import Path
root, old_repo, contact = map(Path, sys.argv[1:4])
sys.path[:] = [p for p in sys.path if p and not Path(p).resolve().is_relative_to(old_repo.resolve())]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'rl_exp/tools/diagnose'))
attempts = []
def isolation(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to(old_repo.resolve()):
            attempts.append(str(path))
            raise AssertionError('OLD_ROOT_OPEN: ' + str(path))
sys.addaudithook(isolation)
import local_path_view as view
import palm_spatial_runtime as runtime
import artifact_paths as routes
for module in (view, runtime, view.csc, routes, sys.modules['rl_exp'], sys.modules['binding']):
    if not Path(module.__file__).resolve().is_relative_to(root):
        raise AssertionError('original code imported: ' + module.__file__)
old_file = old_repo / 'rl_exp/tools/verify/check_self_collision.py'
probes = [lambda: builtins.open(old_file, 'rb'), lambda: io.open(old_file, 'rb'),
          lambda: io.FileIO(old_file, 'r'), lambda: os.open(old_file, os.O_RDONLY),
          lambda: routes.sha256_file(old_file),
          lambda: routes.sha256_file(old_file.parent / '..' / 'verify' / old_file.name)]
for operation in probes:
    try:
        operation()
    except AssertionError as error:
        if 'OLD_ROOT_OPEN' not in str(error):
            raise
    else:
        raise AssertionError('isolation destructive probe escaped')
probe_count = len(attempts)
attempts.clear()
view._load(contact / 'report.json')
runtime.check_build(runtime.BUILD)
if attempts:
    raise AssertionError('positive consumers attempted old-root reads')
for unauthorized in (root / 'forged/build.json', root / 'other/checkpoint_v3/build.json'):
    try:
        runtime.check_build(unauthorized)
    except ValueError as error:
        if 'authorized' not in str(error):
            raise
    else:
        raise AssertionError('foreign build authorized')
fk = Path(view.csc.__file__)
raw = fk.read_bytes()
try:
    fk.write_bytes(raw + b'\n# identity corruption\n')
    try:
        view._load(contact / 'report.json')
    except AssertionError as error:
        if 'FK changed since collection' not in str(error):
            raise
    else:
        raise AssertionError('changed FK bytes accepted')
finally:
    fk.write_bytes(raw)
foreign = root / 'foreign/check_self_collision.py'
foreign.parent.mkdir()
foreign.write_bytes(raw)
view.csc.__file__ = str(foreign)
try:
    view._load(contact / 'report.json')
except AssertionError as error:
    if 'FK changed since collection' not in str(error):
        raise
else:
    raise AssertionError('same basename at unauthorized code path accepted')
print('RECOVERY_CHILD_OK ' + json.dumps({'blocked_probes': probe_count, 'positive_old_reads': len(attempts),
      'code_root': str(root), 'fk_negative': True, 'authorization_negatives': True}))
'''


class RelocationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='diagnostic-relocation-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.index = self.root / 'artifact_index.json'
        self.doc = {'format': 1, 'packages': []}
        existing = routes.ArtifactPaths()
        for original, label in ((CONTACT, 'contact'), (CHECKPOINT, 'checkpoint')):
            physical = existing.resolve(original / ('report.json' if label == 'contact' else 'build.json')).parent
            destination = self.root / 'rl_exp/out/runs/relocation' / label
            shutil.copytree(physical, destination)
            files = {p.relative_to(destination).as_posix(): routes.sha256_file(p)
                     for p in destination.rglob('*') if p.is_file()}
            self.doc['packages'].append({
                'logical_root': original.relative_to(REPO).as_posix(),
                'current_location': destination.relative_to(self.root).as_posix(),
                'relocation': {'original_absolute_root': str(original), 'files': files}})
        self.save()
        self.paths = routes.ArtifactPaths(self.index, self.root)
        # This historical report predates the current FK implementation. Restore
        # its exact committed source in the fixture; never rewrite its binding.
        fk_name = 'rl_exp/tools/verify/check_self_collision.py'
        report = json.loads(self.paths.resolve(CONTACT / 'report.json').read_text(encoding='utf-8'))
        expected_fk = next(digest for name, digest in report['identity']['code_sha256'].items()
                           if existing.same_identity(Path(name), REPO / fk_name))
        fk_raw = git_boundary.git(REPO, 'show', 'd243b9e:' + fk_name).stdout
        self.assertEqual(runtime.binding.sha256_bytes(fk_raw), expected_fk)
        self.fk_path = self.root / fk_name
        self.fk_path.parent.mkdir(parents=True)
        self.fk_path.write_bytes(fk_raw)
        spec = importlib.util.spec_from_file_location('relocation_fixture_fk', self.fk_path)
        historical_fk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(historical_fk)
        historical_patch = patch.object(view, 'csc', historical_fk)
        historical_patch.start()
        self.addCleanup(historical_patch.stop)
        self.old_open = Path.open
        self.old_builtin_open = builtins.open
        self.old_io_open = io.open
        self.old_os_open = os.open
        self.blocked_roots = [CONTACT, CHECKPOINT]

    def save(self):
        self.index.write_text(json.dumps(self.doc), encoding='utf-8')

    def deny_old(self, path, *args, **kwargs):
        self.check_old(path)
        return self.old_open(path, *args, **kwargs)

    def check_old(self, path):
        if isinstance(path, int):
            return
        path = Path(os.fsdecode(path))
        if any(path.resolve().is_relative_to(p.resolve()) for p in self.blocked_roots):
            raise AssertionError(f'OLD_EVIDENCE_READ: {path}')

    @contextmanager
    def isolated(self):
        def guarded(operation):
            def invoke(path, *args, **kwargs):
                self.check_old(path)
                return operation(path, *args, **kwargs)
            return invoke
        with patch.object(Path, 'open', lambda p, *a, **kw: self.deny_old(p, *a, **kw)), \
                patch.object(builtins, 'open', guarded(self.old_builtin_open)), \
                patch.object(io, 'open', guarded(self.old_io_open)), \
                patch.object(os, 'open', guarded(self.old_os_open)):
            yield

    def test_isolation_blocks_real_hash_and_direct_open(self):
        path = CHECKPOINT / 'build.json'
        with self.isolated():
            for operation in (lambda: routes.sha256_file(path),
                              lambda: builtins.open(path, 'rb'),
                              lambda: io.open(path, 'rb'),
                              lambda: os.open(path, os.O_RDONLY)):
                with self.assertRaisesRegex(AssertionError, 'OLD_EVIDENCE_READ'):
                    operation()

    def test_actual_local_path_reader_without_original_roots(self):
        with patch.object(view, 'ArtifactPaths', lambda: self.paths, create=True), \
                self.isolated():
            report, _, meshes, _, tracks = view._load(CONTACT / 'report.json')
        self.assertEqual(report['mode'], 'budgeted_local_path')
        self.assertTrue(meshes)
        self.assertTrue(all(stats['completed_local_loop'] for stats, _ in tracks.values()))

    def test_runtime_authorization_and_bytes_at_new_location(self):
        with patch.object(runtime, 'ArtifactPaths', lambda: self.paths, create=True), \
                self.isolated():
            original = runtime.check_build(runtime.BUILD)
            relocated = runtime.check_build(self.paths.resolve(runtime.BUILD))
        self.assertEqual(original, relocated)
        self.assertEqual(original['candidate_sha256'], runtime.URDF_HASH)
        with patch.object(runtime, 'ArtifactPaths', lambda: self.paths, create=True):
            with self.assertRaisesRegex(ValueError, 'authorized'):
                runtime.check_build(self.root / 'forged/build.json')

    def test_runtime_authorization_after_code_root_changes(self):
        new_build = self.root / runtime.BUILD.relative_to(REPO)
        with patch.object(runtime, 'ArtifactPaths', lambda: self.paths), \
                patch.object(runtime, 'BUILD', new_build), self.isolated():
            self.assertEqual(runtime.check_build(new_build)['candidate_sha256'], runtime.URDF_HASH)

    def test_corrupt_or_missing_file_never_uses_old_copy(self):
        target = self.paths.resolve(CONTACT / 'report.json')
        target.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            self.paths.resolve(CONTACT / 'report.json')
        target.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.paths.resolve(CONTACT / 'report.json')

    def test_missing_mapping_and_wrong_expected_digest(self):
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            self.paths.resolve(CONTACT / 'report.json', '0' * 64)
        self.doc['packages'] = self.doc['packages'][1:]
        self.save()
        paths = routes.ArtifactPaths(self.index, self.root)
        with patch.object(view, 'ArtifactPaths', lambda: paths, create=True), \
                self.isolated():
            with self.assertRaises((OSError, AssertionError)):
                view._load(CONTACT / 'report.json')

    def test_path_escape_unbound_file_and_overlapping_routes(self):
        with self.assertRaisesRegex(ValueError, 'unbound'):
            self.paths.resolve(CONTACT / 'unlisted.json')
        self.doc['packages'][0]['current_location'] = '../escape'
        self.save()
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            routes.ArtifactPaths(self.index, self.root)
        self.doc['packages'][0]['current_location'] = 'rl_exp/out/runs/relocation/contact'
        self.doc['packages'].append(self.doc['packages'][0])
        self.save()
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            routes.ArtifactPaths(self.index, self.root)

    def test_recheckout_bytes_and_real_consumers(self):
        for autocrlf in ('true', 'false'):
            case = self.root / ('git-' + autocrlf)
            case.mkdir()
            source = git_boundary.DiagnosticGitBoundaryTest().new_repo(case, autocrlf)
            names = ['.gitattributes', 'artifact_index.json']
            (source / '.gitattributes').write_bytes((REPO / '.gitattributes').read_bytes())
            (source / 'artifact_index.json').write_bytes(self.index.read_bytes())
            # Include real code and its import dependencies, not parent-process modules.
            tracked = git_boundary.git(REPO, 'ls-files', '-z', '--', 'rl_exp').stdout.decode().split('\0')
            tracked = sorted(set(tracked) | {'rl_exp/tools/diagnose/artifact_run.py'})
            for name in tracked:
                if not name or (Path(name).suffix != '.py'
                                and not (name.startswith('rl_exp/versions/') and name.endswith('.json'))):
                    continue
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((REPO / name).read_bytes())
                names.append(name)
            (source / self.fk_path.relative_to(self.root)).write_bytes(self.fk_path.read_bytes())
            default_index = source / 'rl_exp/tools/diagnose/artifact_index.json'
            default_index.write_bytes(self.index.read_bytes())
            names.append(default_index.relative_to(source).as_posix())
            for entry in self.doc['packages']:
                for name in entry['relocation']['files']:
                    relative = Path(entry['current_location']) / name
                    target = source / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((self.root / relative).read_bytes())
                    names.append(relative.as_posix())
            git_boundary.git(source, 'add', '--', *names)
            git_boundary.git(source, 'commit', '-q', '-m', 'Relocated diagnostic byte fixture')
            clone = case / 'clone'
            git_boundary.git(case, '-c', 'core.autocrlf=' + autocrlf,
                             'clone', '-q', str(source), str(clone))
            for entry in self.doc['packages']:
                for name, digest in entry['relocation']['files'].items():
                    relative = Path(entry['current_location']) / name
                    blob = git_boundary.git(source, 'show', 'HEAD:' + relative.as_posix()).stdout
                    self.assertEqual(blob, (self.root / relative).read_bytes())
                    self.assertEqual((clone / relative).read_bytes(), blob)
                    self.assertEqual(routes.sha256_file(clone / relative), digest)
            self.assertTrue(source.resolve().is_relative_to(self.root.resolve()))
            self.assertNotEqual(source.resolve(), self.root.resolve())
            def remove_readonly(function, path, error):
                if not isinstance(error, PermissionError):
                    raise error
                self.assertTrue(Path(path).resolve().is_relative_to(source.resolve()))
                Path(path).chmod(stat.S_IWRITE)
                function(path)
            shutil.rmtree(source, onexc=remove_readonly)
            paths = routes.ArtifactPaths(clone / 'artifact_index.json', clone)
            with patch.object(view, 'ArtifactPaths', lambda: paths), \
                    patch.object(runtime, 'ArtifactPaths', lambda: paths), \
                    patch.object(view.csc, '__file__', str(clone / self.fk_path.relative_to(self.root))), \
                    self.isolated():
                self.assertTrue(view._load(CONTACT / 'report.json')[-1])
                self.assertEqual(runtime.check_build(runtime.BUILD)['candidate_sha256'], runtime.URDF_HASH)
            child = subprocess.run(
                [sys.executable, '-I', '-B', '-c', RECOVERY_CHILD, str(clone), str(REPO), str(CONTACT)],
                cwd=clone, capture_output=True, text=True, timeout=60)
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
            self.assertIn('RECOVERY_CHILD_OK', child.stdout)
            summary = json.loads(child.stdout.split('RECOVERY_CHILD_OK ', 1)[1])
            self.assertEqual(summary['blocked_probes'], 6)
            self.assertEqual(summary['positive_old_reads'], 0)
            print(f'RECOVERY_RECHECKOUT autocrlf={autocrlf}: ' + json.dumps(summary))

    def drive_fixture(self):
        analysis = json.loads((REPO / 'rl_exp/out/lizard2_palm_combined_view_20261016_drive/analysis.json').read_text())
        source_path = Path(analysis['source_report'])
        report = json.loads(source_path.read_text())
        drive_path = Path(analysis['drive_limit_prerequisites']['drive_report'])
        drive = json.loads(drive_path.read_text())
        manifest_path = Path(drive['input']['manifest'])
        manifest = json.loads(manifest_path.read_text())
        target = Path(manifest['target_binding']['target'])
        for original, label in ((source_path, 'support'), (drive_path, 'drive'),
                                (manifest_path, 'manifest'), (target, 'usd')):
            destination = self.root / 'rl_exp/out/runs/relocation' / label
            destination.mkdir()
            shutil.copyfile(original, destination / original.name)
            self.blocked_roots.append(original.parent)
            self.doc['packages'].append({
                'logical_root': original.parent.relative_to(REPO).as_posix(),
                'current_location': destination.relative_to(self.root).as_posix(),
                'relocation': {'original_absolute_root': str(original.parent),
                               'files': {original.name: routes.sha256_file(original)}}})
        self.save()
        self.paths = routes.ArtifactPaths(self.index, self.root)
        return analysis, report, source_path, drive_path

    def test_drive_digest_without_old_copy_and_with_conflicting_old_bytes(self):
        analysis, report, _, drive_path = self.drive_fixture()
        expected = routes.sha256_file(self.paths.resolve(drive_path))
        with patch.object(view, 'artifact_path', self.paths.resolve), self.isolated():
            actual = view._drive_prerequisites(report, drive_path, analysis['time_mapping_prerequisites'])
        self.assertEqual(actual['drive_report_sha256'], expected)
        self.assertEqual(actual['drive_report'], str(drive_path))
        self.assertEqual(actual['drive_report_location'], str(self.paths.resolve(drive_path)))
        # A different old copy must never supply the digest of the relocated JSON.
        raw_digest = view.digest
        def conflicting(path):
            return '0' * 64 if Path(path).resolve() == drive_path.resolve() else raw_digest(path)
        with patch.object(view, 'artifact_path', self.paths.resolve), \
                patch.object(view, 'digest', conflicting), self.isolated():
            actual = view._drive_prerequisites(report, drive_path, analysis['time_mapping_prerequisites'])
        self.assertEqual(actual['drive_report_sha256'], expected)

    def test_run_binds_migrated_drive_in_written_analysis(self):
        analysis, _, source_path, drive_path = self.drive_fixture()
        binding = self.root / 'rl_exp/tools/runrecord/binding.py'
        binding.parent.mkdir(parents=True)
        shutil.copyfile(REPO / 'rl_exp/tools/runrecord/binding.py', binding)
        output = self.root / 'rl_exp/out/analysis'
        raw_digest = view.digest
        def missing_old(path):
            return None if Path(path).resolve() == drive_path.resolve() else raw_digest(path)
        # Only plotting is stubbed. Parsing, rates, drive binding and JSON writer are real.
        def plots(output, leg, *args):
            (output / (leg + '_trajectory.png')).write_bytes(b'test plot')

        def render(output, leg, *args):
            for angle in ('side', 'top'):
                (output / (leg + '_' + angle + '.gif')).write_bytes(b'test render')

        with patch.object(view, 'REPO', self.root), \
                patch.object(view, 'ArtifactPaths', lambda: self.paths), \
                patch.object(view, 'artifact_path', self.paths.resolve), \
                patch.object(view, 'digest', missing_old), \
                patch.object(view, '_plot', plots), patch.object(view, '_render', render), \
                self.isolated(), redirect_stdout(io.StringIO()):
            view._run(source_path, output, drive_report=drive_path)
        result = json.loads((output / 'analysis.json').read_text())
        self.assertEqual(result['drive_limit_prerequisites']['drive_report_sha256'],
                         analysis['drive_limit_prerequisites']['drive_report_sha256'])


CONSOLIDATED_CHILD = r'''
import builtins, io, json, os, sys
from pathlib import Path
root, original = map(Path, sys.argv[1:3])
attempts = []
def isolation(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to(original):
            attempts.append(str(path))
            raise AssertionError('OLD_ROOT_OPEN: ' + str(path))
sys.addaudithook(isolation)
sys.path[:] = [p for p in sys.path if p and not Path(p).resolve().is_relative_to(original)]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'rl_exp/tools/diagnose'))
import artifact_paths as routes
import palm_spatial_probe as probe
import palm_spatial_runtime as runtime
from artifact_run import inspect_run
for module in (probe, runtime, probe.csc, routes):
    assert Path(module.__file__).resolve().is_relative_to(root), module.__file__
old_code = original / 'rl_exp/tools/verify/check_self_collision.py'
for operation in (lambda: builtins.open(old_code, 'rb'), lambda: io.open(old_code, 'rb'),
                  lambda: os.open(old_code, os.O_RDONLY), lambda: routes.sha256_file(old_code)):
    try: operation()
    except AssertionError as error: assert 'OLD_ROOT_OPEN' in str(error)
    else: raise AssertionError('isolation control escaped')
attempts.clear()
manifest = json.loads((root / 'recovery.json').read_text(encoding='utf-8'))
paths = routes.ArtifactPaths()
baseline = original / manifest['source_root']
positive = baseline / 'checkpoint_v3_probe/report.json'
negative = baseline / 'checkpoint_v3_locked/report.json'
def read(path):
    return json.loads(paths.resolve(path).read_text(encoding='utf-8'))
assert read(positive)['regression_pass'] is True
assert read(negative)['regression_pass'] is False and read(negative)['lock_twist'] is True
runtime.check_build(runtime.BUILD)
for foreign in (root / 'forged/build.json', root / 'foreign/checkpoint_v3/build.json'):
    try: runtime.check_build(foreign)
    except ValueError as error: assert 'authorized' in str(error)
    else: raise AssertionError('foreign build authorized')
physical = paths.resolve(positive); raw = physical.read_bytes()
physical.write_bytes(b'corrupt baseline')
try:
    try: paths.resolve(positive)
    except ValueError as error: assert 'digest mismatch' in str(error)
    else: raise AssertionError('corrupt relocated baseline accepted')
finally: physical.write_bytes(raw)
index = root / 'rl_exp/tools/diagnose/artifact_index.json'
raw_index = index.read_bytes(); doc = json.loads(raw_index)
doc['packages'] = [p for p in doc['packages'] if p['logical_root'] != positive.parent.relative_to(original).as_posix()]
index.write_text(json.dumps(doc), encoding='utf-8')
try:
    try: routes.ArtifactPaths().resolve(positive).read_bytes()
    except AssertionError as error: assert 'OLD_ROOT_OPEN' in str(error)
    else: raise AssertionError('missing mapping silently accepted')
finally: index.write_bytes(raw_index)
attempts.clear()
for label, locked in (('positive', False), ('negative', True)):
    output = root / 'rl_exp/out/runs/restored-comparison' / label
    sys.argv = [str(Path(probe.__file__)), '--build_report', str(original / manifest['replay']['build_report']),
                '--output_dir', str(output)] + (['--lock_twist'] if locked else [])
    try: probe.main()
    except SystemExit as error:
        assert locked and str(error).startswith('REGRESSION_REJECTED'), str(error)
    else: assert not locked, 'locked-axis counterexample no longer rejected'
    expected = read(original / manifest['replay'][label + '_report'])
    actual = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    expected.pop('probe_sha256'); actual.pop('probe_sha256')
    assert actual == expected, 'historical comparison changed: ' + label
    record = json.loads((output / 'run.json').read_text(encoding='utf-8'))
    assert record['state'] == ('failed' if locked else 'completed')
    if not locked: inspect_run(output, routes.ArtifactPaths())
assert not attempts, attempts
print('CONSOLIDATED_RECOVERY_OK ' + json.dumps({'old_reads': 0, 'baseline_reads': 2,
      'real_cli_replays': 2, 'authorization_negatives': True, 'missing_mapping_and_corruption_rejected': True}))
'''


def verify_consolidated_archive(archive: Path, proof: Path) -> None:
    """Restore a blob-manifest archive, clone exact bytes, and replay real spatial consumers."""
    require = runtime.require
    require(not proof.exists(), 'proof directory must be fresh')
    proof.mkdir(parents=True)
    with zipfile.ZipFile(archive) as package:
        manifest = json.loads(package.read('manifest.json'))
        require(manifest['format'] == 1 and manifest['topic'] == 'palm-spatial-history', 'unexpected archive')
        expected_members = {'manifest.json'} | {'blobs/' + row['sha256'] for row in manifest['files'].values()}
        require(len(package.namelist()) == len(expected_members) and set(package.namelist()) == expected_members,
                'unexpected or duplicate archive members')
        blobs = {}
        for name, row in manifest['files'].items():
            routes._relative(name)
            raw = package.read('blobs/' + row['sha256'])
            require(runtime.binding.sha256_bytes(raw) == row['sha256'] and len(raw) == row['size'], name)
            blobs[name] = raw
    old_repo = Path(manifest['original_repository']).resolve()
    source_root = Path(manifest['source_root'])
    current = routes.ArtifactPaths()
    index_doc = json.loads(current.index.read_text(encoding='utf-8'))
    baseline_rows = [p for p in index_doc['packages'] if p['logical_root'] in {
        (source_root / 'checkpoint_v3_probe').as_posix(), (source_root / 'checkpoint_v3_locked').as_posix()}]
    require(len(baseline_rows) == 2, 'tracked baseline routes missing')
    checkpoint = current.resolve(runtime.BUILD).parent
    runtime.check_build(runtime.BUILD)
    results = []
    with tempfile.TemporaryDirectory(prefix='consolidated-diagnostic-') as temporary:
        temporary_root = Path(temporary).resolve()
        for autocrlf in ('true', 'false'):
            case = temporary_root / autocrlf; case.mkdir()
            source = git_boundary.DiagnosticGitBoundaryTest().new_repo(case, autocrlf)
            names = []

            def put(name, raw):
                target = source / routes._relative(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                names.append(name)

            tracked = git_boundary.git(REPO, 'ls-files', '-z', '--', 'rl_exp').stdout.decode().split('\0')
            for name in tracked:
                if name and (name.endswith('.py') or (name.startswith('rl_exp/versions/') and name.endswith('.json'))):
                    put(name, (REPO / name).read_bytes())
            attributes = (REPO / '.gitattributes').read_bytes()
            attributes += b'\n# Exact executed code bytes in this recovery fixture.\n/rl_exp/**/*.py -text\n/rl_exp/versions/**/*.json -text\n'
            put('.gitattributes', attributes)
            put('recovery.json', json.dumps(manifest).encode())
            packages = []
            for logical in manifest['historical_roots'] + manifest['dependency_roots']:
                relative = routes._relative(logical)
                location = Path('rl_exp/out/runs/archive-recovery') / relative
                files = {}
                for name, raw in blobs.items():
                    path = Path(name)
                    if path.is_relative_to(relative):
                        suffix = path.relative_to(relative).as_posix()
                        files[suffix] = manifest['files'][name]['sha256']
                        put((location / suffix).as_posix(), raw)
                require(bool(files), 'empty restore route: ' + logical)
                packages.append({'logical_root': logical, 'current_location': location.as_posix(),
                                 'relocation': {'original_absolute_root': str(old_repo / relative), 'files': files}})
            location = Path('rl_exp/out/runs/archive-recovery/checkpoint')
            files = {}
            for path in sorted(checkpoint.rglob('*')):
                if path.is_file():
                    suffix = path.relative_to(checkpoint).as_posix()
                    files[suffix] = routes.sha256_file(path)
                    put((location / suffix).as_posix(), path.read_bytes())
            packages.append({'logical_root': runtime.BUILD.parent.relative_to(REPO).as_posix(),
                             'current_location': location.as_posix(),
                             'relocation': {'original_absolute_root': str(old_repo / runtime.BUILD.parent.relative_to(REPO)),
                                            'files': files}})
            for row in baseline_rows:
                packages.append(row)
                destination = Path(row['current_location'])
                attributes = REPO / destination.parent / '.gitattributes'
                put((destination.parent / '.gitattributes').as_posix(), attributes.read_bytes())
                for name, digest in row['relocation']['files'].items():
                    original = REPO / destination / name
                    require(routes.sha256_file(original) == digest, 'baseline changed')
                    put((destination / name).as_posix(), original.read_bytes())
            put('rl_exp/tools/diagnose/artifact_index.json', json.dumps({'format': 1, 'packages': packages}).encode())
            names = sorted(set(names))
            originals = {name: (source / name).read_bytes() for name in names}
            for start in range(0, len(names), 50):
                git_boundary.git(source, 'add', '--', *names[start:start + 50])
            git_boundary.git(source, 'commit', '-q', '-m', 'Restore consolidated diagnostic evidence')
            clone = case / 'clone'
            git_boundary.git(case, '-c', 'core.autocrlf=' + autocrlf, 'clone', '-q', str(source), str(clone))
            query = ''.join('HEAD:' + name + '\n' for name in names).encode()
            batch = subprocess.run(['git', '-C', str(source), 'cat-file', '--batch'], input=query,
                                   capture_output=True, check=True, timeout=60)
            objects = io.BytesIO(batch.stdout)
            for name, raw in originals.items():
                header = objects.readline().split()
                require(len(header) == 3 and header[1] == b'blob', 'missing Git blob: ' + name)
                require(objects.read(int(header[2])) == raw and objects.read(1) == b'\n', 'Git blob changed: ' + name)
                require((clone / name).read_bytes() == raw, 'checkout changed: ' + name)
            require(not objects.read(), 'unexpected Git batch output')
            require(source.resolve().is_relative_to(temporary_root) and source.resolve() != temporary_root,
                    'unsafe temporary source cleanup')
            def remove_readonly(operation, path, error):
                require(Path(path).resolve().is_relative_to(source.resolve()), 'cleanup escaped source')
                if not isinstance(error, PermissionError):
                    raise error
                Path(path).chmod(stat.S_IWRITE)
                operation(path)
            shutil.rmtree(source, onexc=remove_readonly)
            child = subprocess.run([sys.executable, '-I', '-B', '-c', CONSOLIDATED_CHILD,
                                    str(clone), str(old_repo)], cwd=clone, capture_output=True, text=True, timeout=180)
            (proof / ('child-' + autocrlf + '.log')).write_text(child.stdout + child.stderr, encoding='utf-8')
            require(child.returncode == 0, child.stdout + child.stderr)
            require('CONSOLIDATED_RECOVERY_OK ' in child.stdout, 'missing real consumer result')
            results.append({'autocrlf': autocrlf, 'files_raw_blob_checkout_equal': len(names),
                            'archive_members_restored': len(blobs), 'child_passed': True})
    result = {'archive_sha256': routes.sha256_file(archive), 'results': results}
    (proof / 'checks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('CONSOLIDATED_ARCHIVE_OK ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--proof_root', type=Path)
    options, remaining = parser.parse_known_args()
    if options.archive is not None:
        if options.proof_root is None or remaining:
            parser.error('--archive requires --proof_root and no unittest selectors')
        verify_consolidated_archive(options.archive.resolve(), options.proof_root.resolve())
    else:
        unittest.main(argv=[sys.argv[0], *remaining])
