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
            for name in tracked:
                if not name or (Path(name).suffix != '.py'
                                and not (name.startswith('rl_exp/versions/') and name.endswith('.json'))):
                    continue
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((REPO / name).read_bytes())
                names.append(name)
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
        with patch.object(view, 'REPO', self.root), \
                patch.object(view, 'ArtifactPaths', lambda: self.paths), \
                patch.object(view, 'artifact_path', self.paths.resolve), \
                patch.object(view, 'digest', missing_old), \
                patch.object(view, '_plot'), patch.object(view, '_render'), \
                self.isolated(), redirect_stdout(io.StringIO()):
            view._run(source_path, output, drive_report=drive_path)
        result = json.loads((output / 'analysis.json').read_text())
        self.assertEqual(result['drive_limit_prerequisites']['drive_report_sha256'],
                         analysis['drive_limit_prerequisites']['drive_report_sha256'])


if __name__ == '__main__':
    unittest.main()
