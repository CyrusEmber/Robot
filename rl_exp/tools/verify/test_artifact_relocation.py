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
from types import ModuleType, SimpleNamespace
import unittest
import zipfile
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'rl_exp/tools/diagnose'))
import artifact_paths as routes
import body_precheck as precheck
import local_path_view as view
import palm_spatial_runtime as runtime
import test_diagnostic_git_boundary as git_boundary

CONTACT = REPO / 'rl_exp/out/lizard2_palm_local_path_contact_20261015'
CHECKPOINT = runtime.BUILD.parent
EXPORT = REPO / 'rl_exp/out/lizard2_spatial_export_cli_verified_20261019'

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

    def test_export_reader_without_checkpoint_originals(self):
        export = self.export_fixture()
        with patch.object(runtime, 'ArtifactPaths', lambda: self.paths), \
                patch.object(runtime, 'REPO', self.root), self.isolated():
            document = runtime.check_export(export,
                '1f69bcd41330df40c9034c68973e687049f1294697924940cbef264bafe0e36a',
                'e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00')
        self.assertEqual(len(document['files_sha256']), 73)

    def export_fixture(self):
        source = routes.ArtifactPaths().resolve(EXPORT / 'export.json').parent
        target = self.root / 'rl_exp/out/runs/relocation/export'
        shutil.copytree(source, target)
        self.doc['packages'].append({'logical_root': EXPORT.relative_to(REPO).as_posix(),
            'current_location': target.relative_to(self.root).as_posix(),
            'relocation': {'original_absolute_root': str(EXPORT), 'files': {
                p.relative_to(target).as_posix(): routes.sha256_file(p) for p in target.rglob('*') if p.is_file()}}})
        self.save()
        self.paths = routes.ArtifactPaths(self.index, self.root)
        self.blocked_roots.append(EXPORT)
        return EXPORT / 'export.json'

    def test_runtime_copies_real_inputs_before_app_launch(self):
        # All preparation is real; stop at the first physical-app boundary.
        app = ModuleType('isaaclab.app')
        def stop_at_launch(args):
            raise RuntimeError('PREPARATION_REACHED_APP_BOUNDARY')
        app.AppLauncher = stop_at_launch
        export = self.export_fixture()
        output_root = self.root / 'rl_exp/out/runtime'; output_root.mkdir(parents=True)
        for label, report in (('checkpoint', None), ('export', export)):
            output = output_root / label
            args = SimpleNamespace(build=runtime.BUILD, out=output, export_report=report,
                approved_export_sha256='1f69bcd41330df40c9034c68973e687049f1294697924940cbef264bafe0e36a',
                approved_urdf_sha256='e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00')
            result = {}
            with patch.object(runtime, 'ArtifactPaths', lambda: self.paths), \
                    patch.object(runtime, 'REPO', self.root), patch.object(runtime, 'OUT', output_root), \
                    patch.dict(sys.modules, {'isaaclab.app': app}), self.isolated():
                with self.assertRaisesRegex(RuntimeError, 'PREPARATION_REACHED_APP_BOUNDARY'):
                    runtime.run(args, result)
            self.assertEqual(result['stage'], 'app_launch')
            self.assertEqual(routes.sha256_file(output / 'input_build.json'),
                             routes.sha256_file(self.paths.resolve(runtime.BUILD)))
            for name, digest in result['input']['candidate_files_sha256'].items():
                self.assertEqual(routes.sha256_file(output / name), digest)

    def test_fresh_reset_accepts_same_export_identity_at_new_location(self):
        app = ModuleType('isaaclab.app')
        def stop_at_launch(args):
            raise RuntimeError('RESET_VALIDATION_REACHED_APP_BOUNDARY')
        app.AppLauncher = stop_at_launch
        with tempfile.TemporaryDirectory(prefix='export-reset-relocation-', dir=REPO / 'rl_exp/out') as temporary:
            folder = Path(temporary)
            source = routes.ArtifactPaths().resolve(EXPORT / 'export.json').parent
            target = folder / 'export'
            shutil.copytree(source, target)
            doc = json.loads(routes.ArtifactPaths().index.read_text(encoding='utf-8'))
            doc['packages'] = [p for p in doc['packages'] if p['logical_root'] != EXPORT.relative_to(REPO).as_posix()]
            doc['packages'].append({'logical_root': EXPORT.relative_to(REPO).as_posix(),
                'current_location': target.relative_to(REPO).as_posix(),
                'relocation': {'original_absolute_root': str(EXPORT), 'files': {
                    p.relative_to(target).as_posix(): routes.sha256_file(p) for p in target.rglob('*') if p.is_file()}}})
            index = folder / 'index.json'; index.write_text(json.dumps(doc))
            paths = routes.ArtifactPaths(index, REPO)
            args = SimpleNamespace(reset_probe=REPO / 'rl_exp/out/lizard2_e_fresh_prepare_20261020/registered_manifest.json',
                export_manifest_sha256='b48f99efcb298860db4f8dfaf12b134c994c54df08bbe192bfbb8465d6efa6e1',
                export_report=target / 'export.json', out=folder / 'reset', repair_connections=False,
                approved_export_sha256='1f69bcd41330df40c9034c68973e687049f1294697924940cbef264bafe0e36a',
                approved_urdf_sha256='e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00')
            result = {}
            self.blocked_roots.append(EXPORT)
            with patch.object(runtime, 'ArtifactPaths', lambda: paths), \
                    patch.dict(sys.modules, {'isaaclab.app': app}), self.isolated():
                with self.assertRaisesRegex(RuntimeError, 'RESET_VALIDATION_REACHED_APP_BOUNDARY'):
                    runtime.reset_probe(args, result)
                foreign = folder / 'foreign'
                shutil.copytree(target, foreign)
                args.export_report = foreign / 'export.json'
                args.out = folder / 'foreign-reset'
                with self.assertRaisesRegex(ValueError, 'fresh export lineage mismatch'):
                    runtime.reset_probe(args, {})
                self.assertFalse(args.out.exists())
            self.assertEqual(result['stage'], 'app_launch')

    def test_whole_body_precheck_with_mapped_source_evidence(self):
        config_path = REPO / 'rl_exp/tools/diagnose/body_precheck_lizard2.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        expected = precheck.run(config, config_path.parent)
        self.assertEqual(expected['counters']['cases_evaluated'], 10)
        with patch.object(precheck, 'artifact_path', self.paths.resolve, create=True), self.isolated():
            actual = precheck.run(config, config_path.parent)
        current = routes.ArtifactPaths()
        def normalize(value):
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items() if key != 'code_sha256'}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, str) and Path(value).is_absolute():
                return str(self.paths.logical(current.logical(Path(value))))
            return value
        self.assertEqual(normalize(actual), normalize(expected))

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


class ArchiveDamageTest(unittest.TestCase):
    def test_local_archive_retains_fk_images_and_every_historical_control(self):
        archive = REPO / 'rl_exp/out/archive/palm-local-path/history-20261015.zip'
        manifest, _ = _archive_bytes(archive, 'palm-local-path-history')
        with zipfile.ZipFile(archive) as source:
            members = {name: source.read(name) for name in source.namelist()}
        fk = 'blobs/' + manifest['files'][manifest['historical_fk_source']]['sha256']
        gif = 'blobs/' + next(row['sha256'] for name,row in manifest['files'].items() if name.endswith('.gif'))
        with tempfile.TemporaryDirectory(prefix='local-archive-damage-') as temporary:
            for defect in ('missing_fk', 'corrupt_gif', 'duplicate_blob', 'omit_control'):
                with self.subTest(defect=defect):
                    rows = dict(members)
                    if defect == 'missing_fk':
                        del rows[fk]
                    elif defect == 'corrupt_gif':
                        raw = rows[gif]; rows[gif] = bytes([raw[0] ^ 1]) + raw[1:]
                    elif defect == 'omit_control':
                        doc = json.loads(rows['manifest.json']); doc['local_controls'].pop()
                        rows['manifest.json'] = json.dumps(doc).encode()
                    damaged = Path(temporary) / (defect + '.zip')
                    with zipfile.ZipFile(damaged, 'w') as target:
                        for name,raw in rows.items(): target.writestr(name,raw)
                        if defect == 'duplicate_blob':
                            with self.assertWarns(UserWarning): target.writestr(fk,rows[fk])
                    with self.assertRaises(ValueError):
                        if defect == 'omit_control':
                            verify_consolidated_archive(
                                REPO / 'rl_exp/out/archive/palm-spatial/history-20261014.zip',
                                Path(temporary) / 'proof', local_archive=damaged)
                        else:
                            _archive_bytes(damaged, 'palm-local-path-history')

    def test_real_export_archive_rejects_lost_or_corrupt_controls(self):
        archive = REPO / 'rl_exp/out/archive/palm-spatial/exports-20261019.zip'
        manifest, _ = _archive_bytes(archive, 'palm-spatial-export-history')
        tensor = next(row for row in manifest['export_controls'] if row['expected'] != 'accepted')
        tensor_file = str(Path(tensor['report']).parent / 'lizard2_palm_spatial.urdf').replace('\\', '/')
        tensor_blob = 'blobs/' + manifest['files'][tensor_file]['sha256']
        log_blob = 'blobs/' + manifest['files'][manifest['standalone_files'][0]]['sha256']
        with zipfile.ZipFile(archive) as source:
            members = {name: source.read(name) for name in source.namelist()}
        with tempfile.TemporaryDirectory(prefix='export-archive-damage-') as temporary:
            for defect in ('drop_tensor', 'corrupt_log', 'duplicate_blob', 'escape_path', 'omit_control'):
                with self.subTest(defect=defect):
                    rows = dict(members)
                    if defect == 'drop_tensor':
                        del rows[tensor_blob]
                    elif defect == 'corrupt_log':
                        raw = rows[log_blob]
                        rows[log_blob] = bytes([raw[0] ^ 1]) + raw[1:]
                    elif defect in ('escape_path', 'omit_control'):
                        doc = json.loads(rows['manifest.json'])
                        if defect == 'escape_path':
                            doc['files']['../escape'] = doc['files'].pop(tensor_file)
                        else:
                            doc['export_controls'].remove(tensor)
                        rows['manifest.json'] = json.dumps(doc).encode()
                    damaged = Path(temporary) / (defect + '.zip')
                    with zipfile.ZipFile(damaged, 'w') as target:
                        for name, raw in rows.items():
                            target.writestr(name, raw)
                        if defect == 'duplicate_blob':
                            with self.assertWarns(UserWarning):
                                target.writestr(tensor_blob, rows[tensor_blob])
                    with self.assertRaises(ValueError):
                        if defect == 'omit_control':
                            verify_consolidated_archive(
                                REPO / 'rl_exp/out/archive/palm-spatial/history-20261014.zip',
                                Path(temporary) / 'proof',
                                REPO / 'rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-checkpoint-relocation/body-before.json',
                                export_archive=damaged)
                        else:
                            _archive_bytes(damaged, 'palm-spatial-export-history')


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
if manifest.get('checkpoint_consumers'):
    from types import ModuleType, SimpleNamespace
    import body_precheck as precheck
    assert Path(precheck.__file__).resolve().is_relative_to(root)
    config = root / 'rl_exp/tools/diagnose/body_precheck_lizard2.json'
    output = root / 'rl_exp/out/body-restored.json'
    sys.argv = [str(Path(precheck.__file__)), '--config', str(config), '--output', str(output)]
    body_exit = precheck.main()
    actual_body = json.loads(output.read_text())
    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items() if key != 'code_sha256'}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, str) and Path(value).is_absolute():
            path = paths.logical(Path(value))
            return str(original / path.relative_to(root) if path.is_relative_to(root) else path)
        return value
    assert normalize(actual_body) == normalize(manifest['body_reference']), 'whole body report changed'
    assert body_exit == (0 if actual_body['status'] == 'pass' else 1)
    export = root / 'rl_exp/out/lizard2_spatial_export_cli_verified_20261019/export.json'
    approvals = ['--export_report', str(export), '--approved_export_sha256',
        '1f69bcd41330df40c9034c68973e687049f1294697924940cbef264bafe0e36a',
        '--approved_urdf_sha256', 'e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00']
    sys.argv = [str(Path(runtime.__file__)), '--export_self_check', *approvals]
    runtime.main()
    runtime.REGISTERED_OUT.mkdir(parents=True)
    prepared = runtime.REGISTERED_OUT / 'restored-preparation'
    sys.argv = [str(Path(runtime.__file__)), '--prepare_registered', '--out', str(prepared)]
    runtime.main()
    sys.argv = [str(Path(runtime.__file__)), '--verify_registered', str(prepared / 'registered_manifest.json')]
    runtime.main()
    # Exercise the real legacy/export copy branches; stop before starting physics.
    app = ModuleType('isaaclab.app')
    def stop_at_launch(args):
        raise RuntimeError('PREPARATION_REACHED_APP_BOUNDARY')
    app.AppLauncher = stop_at_launch
    sys.modules['isaaclab.app'] = app
    runtime.OUT.mkdir(parents=True, exist_ok=True)
    for label, exported in (('checkpoint-prepared', False), ('export-prepared', True)):
        destination = runtime.OUT / label
        args = SimpleNamespace(build=runtime.BUILD, out=destination,
            export_report=export if exported else None,
            approved_export_sha256=approvals[3], approved_urdf_sha256=approvals[5])
        result = {}
        try: runtime.run(args, result)
        except RuntimeError as error: assert str(error) == 'PREPARATION_REACHED_APP_BOUNDARY'
        else: raise AssertionError('physical-app boundary not reached')
        assert result['stage'] == 'app_launch'
        assert routes.sha256_file(destination / 'input_build.json') == routes.sha256_file(paths.resolve(runtime.BUILD))
        for name, digest in result['input']['candidate_files_sha256'].items():
            assert routes.sha256_file(destination / name) == digest
    assert not attempts, attempts
    checkpoint = paths.resolve(runtime.BUILD)
    raw_index = index.read_bytes(); doc = json.loads(raw_index)
    logical = runtime.BUILD.parent.relative_to(root).as_posix()
    doc['packages'] = [p for p in doc['packages'] if p['logical_root'] != logical]
    index.write_text(json.dumps(doc))
    try:
        try: runtime.check_export(export, approvals[3], approvals[5])
        except AssertionError as error: assert 'OLD_ROOT_OPEN' in str(error)
        except ValueError as error: assert 'export source hash mismatch: build_report' in str(error)
        else: raise AssertionError('checkpoint mapping removal escaped')
    finally: index.write_bytes(raw_index)
    attempts.clear()
    raw = checkpoint.read_bytes(); checkpoint.write_bytes(b'corrupt checkpoint')
    try:
        try: runtime.check_export(export, approvals[3], approvals[5])
        except ValueError as error: assert 'digest mismatch' in str(error)
        else: raise AssertionError('corrupt checkpoint accepted')
    finally: checkpoint.write_bytes(raw)
    assert not attempts, attempts
    print('CHECKPOINT_CONSUMERS_OK ' + json.dumps({'body_cases': actual_body['counters'],
          'body_status_preserved': actual_body['status'], 'export_and_registered_cli': True,
          'legacy_and_export_copy_before_physics': True, 'missing_mapping_and_corruption_rejected': True}))
if manifest.get('export_controls'):
    outcomes = []
    for control in manifest['export_controls']:
        report = paths.resolve(original / control['report'])
        assert routes.sha256_file(report) == control['report_sha256']
        try:
            runtime.check_export(report, control['report_sha256'], control['urdf_sha256'])
        except ValueError as error:
            assert str(error) == control['expected'] and control['expected'] != 'accepted'
        else: assert control['expected'] == 'accepted'
        outcomes.append(control['expected'])
    logical_export = root / 'rl_exp/out/lizard2_spatial_export_cli_verified_20261019/export.json'
    canonical_export = paths.resolve(logical_export)
    assert canonical_export != logical_export and not logical_export.exists()
    logical_export.parent.mkdir(parents=True)
    logical_export.write_bytes(b'conflicting old export bytes')
    try: runtime.check_export(logical_export, approvals[3], approvals[5])
    finally: logical_export.unlink(); logical_export.parent.rmdir()
    raw = canonical_export.read_bytes(); canonical_export.write_bytes(b'corrupt canonical export')
    try:
        try: runtime.check_export(logical_export, approvals[3], approvals[5])
        except ValueError as error: assert 'digest mismatch' in str(error)
        else: raise AssertionError('corrupt canonical export accepted')
    finally: canonical_export.write_bytes(raw)
    raw_index = index.read_bytes(); doc = json.loads(raw_index)
    logical = logical_export.parent.relative_to(root).as_posix()
    doc['packages'] = [p for p in doc['packages'] if p['logical_root'] != logical]
    index.write_text(json.dumps(doc))
    try:
        try: runtime.check_export(logical_export, approvals[3], approvals[5])
        except ValueError as error: assert 'export report approval mismatch' in str(error)
        else: raise AssertionError('export route removal escaped')
    finally: index.write_bytes(raw_index)
    assert not attempts, attempts
    print('EXPORT_ARCHIVE_RECOVERY_OK ' + json.dumps({'controls':outcomes,
        'conflicting_old_copy_ignored':True, 'corrupt_and_missing_route_rejected':True, 'old_reads':0}))
if manifest.get('local_controls'):
    import importlib.util
    import local_path_view as view
    fk = Path(view.csc.__file__)
    current_fk = fk.read_bytes()
    original_module = view.csc
    historical_fk = paths.resolve(original / manifest['historical_fk_source']).read_bytes()
    assert routes.sha256_file(paths.resolve(original / manifest['historical_fk_source'])) == '3425518c66192b60fad9edc44a586adf8b7b2dedcf9f73d27d792e9b6d8d7bf6'
    outcomes = []
    try:
        # Only the owned clone changes: execute the exact archived FK at its logical code path.
        fk.write_bytes(historical_fk)
        spec = importlib.util.spec_from_file_location('restored_historical_fk', fk)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        view.csc = module
        for control in manifest['local_controls']:
            source = paths.resolve(original / control['report'])
            assert routes.sha256_file(source) == control['sha256']
            document, urdf, meshes, transform, tracks = view._load(source)
            actual = {leg:{key:stats[key] for key in ('accepted_points', 'completed_local_loop', 'failure_phase')}
                      for leg,(stats,frames) in tracks.items()}
            assert actual == control['legs'], (actual, control['legs'])
            assert meshes and urdf
            raw = source.read_bytes()
            bad = json.loads(raw); bad['identity']['build_report_sha256'] = '0' * 64
            source.write_text(json.dumps(bad))
            try:
                try: view._load(source)
                except (AssertionError, ValueError): pass
                else: raise AssertionError('bad local report accepted')
            finally: source.write_bytes(raw)
            outcomes.append(actual)
    finally:
        view.csc = original_module
        fk.write_bytes(current_fk)
    from PIL import Image
    image_count = frame_count = 0
    for name in manifest['files']:
        if name.endswith(('.gif', '.png')) and any(Path(name).is_relative_to(Path(r)) for r in manifest['local_roots']):
            with Image.open(paths.resolve(original / name)) as picture:
                for frame in range(getattr(picture, 'n_frames', 1)):
                    picture.seek(frame); picture.convert('RGB').load(); frame_count += 1
            image_count += 1
    assert not attempts, attempts
    print('LOCAL_ARCHIVE_RECOVERY_OK ' + json.dumps({'verdicts':outcomes, 'old_reads':0,
          'historical_fk_executed':True, 'bad_digest_rejected':True,
          'images_decoded':image_count, 'frames_decoded':frame_count}))
print('CONSOLIDATED_RECOVERY_OK ' + json.dumps({'old_reads': 0, 'baseline_reads': 2,
      'real_cli_replays': 2, 'authorization_negatives': True, 'missing_mapping_and_corruption_rejected': True}))
'''


BLENDER_RECOVERY_CHILD = r'''
import json, os, sys, types
from pathlib import Path
import bpy
root, original = map(Path, sys.argv[sys.argv.index('--') + 1:])
attempts = []
def isolation(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to(original):
            attempts.append(str(path))
            raise AssertionError('OLD_ROOT_OPEN: ' + str(path))
sys.path[:] = [p for p in sys.path if p and not Path(p).resolve().is_relative_to(original)]
sys.addaudithook(isolation)
sys.path.insert(0, str(root / 'rl_exp/tools/diagnose'))
from artifact_paths import ArtifactPaths
paths = ArtifactPaths()
logical = original / 'rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3'
exporter = root / 'rl_exp/blender/scripts/generate_urdf.py'
stance = root / 'rl_exp/blender/scripts/lizard2_stance_candidate.py'
target = root / 'rl_exp/out/restored-blender-export'
digest = '59473f8c345dce48e8ee379c0972c928184f768be85afca948ac812a666fa6f8'
sys.argv = [str(exporter), '--', '--robot', 'lizard2_palm_spatial',
    '--blend', str(logical / 'palm_spatial.blend'), '--build_report', str(logical / 'build.json'),
    '--build_report_sha256', digest, '--out_dir', str(target)]
try:
    exec(compile((root / 'rl_exp/out/generate-before.py').read_bytes(), str(exporter), 'exec'),
         {'__file__': str(exporter), '__name__': '__main__'})
except AssertionError as error: assert 'OLD_ROOT_OPEN' in str(error)
else: raise AssertionError('old exporter unexpectedly read relocated inputs')
assert not target.exists()
old = types.ModuleType('old_stance'); old.__file__ = str(stance)
exec(compile((root / 'rl_exp/out/stance-before.py').read_bytes(), str(stance), 'exec'), old.__dict__)
try: old.spatial_export_self_check(logical / 'palm_spatial.blend', logical / 'build.json', target,
                                   build_report_sha256=digest)
except AssertionError as error: assert 'OLD_ROOT_OPEN' in str(error)
else: raise AssertionError('old exporter self-check unexpectedly read relocated inputs')
assert not target.exists(); attempts.clear()
current = types.ModuleType('restored_stance'); current.__file__ = str(stance)
exec(compile(stance.read_bytes(), str(stance), 'exec'), current.__dict__)
current.spatial_export_self_check(logical / 'palm_spatial.blend', logical / 'build.json', target,
                                 build_report_sha256=digest)
report = json.loads((target / 'self_check.json').read_text())
assert report['status'] == 'PASS' and report['negative_outputs_absent'] is True
actual = json.loads((target / 'export.json').read_text())
expected = json.loads(paths.resolve(root / 'rl_exp/out/lizard2_spatial_export_cli_verified_20261019/export.json').read_text())
assert actual['files_sha256'] == expected['files_sha256'], 'Blender export bytes changed'
assert Path(bpy.data.filepath).resolve() == paths.resolve(logical / 'palm_spatial.blend')
assert not attempts, attempts
print('BLENDER_RECOVERY_OK ' + json.dumps({'positive':report['positive'], 'negatives':report['negatives'],
      'export_files_byte_equal':len(actual['files_sha256']), 'old_reads':0, 'native_blend_from_new_root':True}))
'''


def _archive_bytes(archive: Path, topic: str) -> tuple[dict, dict[str, bytes]]:
    """Validate every member before restoring an existing blob-manifest archive."""
    require = runtime.require
    with zipfile.ZipFile(archive) as package:
        manifest = json.loads(package.read('manifest.json'))
        require(manifest['format'] == 1 and manifest['topic'] == topic, 'unexpected archive')
        expected_members = {'manifest.json'} | {'blobs/' + row['sha256'] for row in manifest['files'].values()}
        require(len(package.namelist()) == len(expected_members) and set(package.namelist()) == expected_members,
                'unexpected or duplicate archive members')
        blobs = {}
        for name, row in manifest['files'].items():
            routes._relative(name)
            raw = package.read('blobs/' + row['sha256'])
            require(runtime.binding.sha256_bytes(raw) == row['sha256'] and len(raw) == row['size'], name)
            blobs[name] = raw
    return manifest, blobs


def verify_consolidated_archive(archive: Path, proof: Path, body_reference: Path | None = None,
                                blender: Path | None = None, export_archive: Path | None = None,
                                local_archive: Path | None = None) -> None:
    """Restore existing archives, clone exact bytes, and replay real spatial consumers."""
    require = runtime.require
    require(not proof.exists(), 'proof directory must be fresh')
    proof.mkdir(parents=True)
    manifest, blobs = _archive_bytes(archive, 'palm-spatial-history')
    old_repo = Path(manifest['original_repository']).resolve()
    source_root = Path(manifest['source_root'])
    current = routes.ArtifactPaths()
    index_doc = json.loads(current.index.read_text(encoding='utf-8'))
    baseline_rows = [p for p in index_doc['packages'] if p['logical_root'] in {
        (source_root / 'checkpoint_v3_probe').as_posix(), (source_root / 'checkpoint_v3_locked').as_posix()}]
    require(len(baseline_rows) == 2, 'tracked baseline routes missing')
    checkpoint = current.resolve(runtime.BUILD).parent
    runtime.check_build(runtime.BUILD)
    export_members = 0
    if export_archive is not None:
        exported_manifest, exported_bytes = _archive_bytes(export_archive, 'palm-spatial-export-history')
        require(exported_manifest['original_repository'] == manifest['original_repository'], 'archive roots differ')
        dependency = routes._relative(exported_manifest['checkpoint_root'])
        actual_checkpoint = {p.relative_to(checkpoint).as_posix(): p.read_bytes()
                             for p in checkpoint.rglob('*') if p.is_file()}
        archived_checkpoint = {Path(name).relative_to(dependency).as_posix(): raw
                               for name, raw in exported_bytes.items() if Path(name).is_relative_to(dependency)}
        require(actual_checkpoint == archived_checkpoint, 'archived checkpoint closure differs')
        for name, raw in exported_bytes.items():
            if Path(name).is_relative_to(dependency):
                continue
            require(name not in blobs, 'archive paths overlap')
            blobs[name] = raw
            manifest['files'][name] = exported_manifest['files'][name]
        manifest['historical_roots'] += exported_manifest['historical_roots']
        manifest['standalone_files'] = exported_manifest['standalone_files']
        manifest['export_controls'] = exported_manifest['export_controls']
        controls = exported_manifest['export_controls']
        expected_reports = {name + '/export.json' for name in exported_manifest['historical_roots']}
        require(len(controls) == len(expected_reports) and {row['report'] for row in controls} == expected_reports,
                'export control coverage incomplete')
        require(all(row['report_sha256'] == exported_manifest['files'][row['report']]['sha256']
                    for row in controls), 'export control identity differs')
        export_members = len(exported_bytes)
    local_members = 0
    if local_archive is not None:
        local_manifest, local_bytes = _archive_bytes(local_archive, 'palm-local-path-history')
        require(local_manifest['original_repository'] == manifest['original_repository'], 'local archive roots differ')
        dependency = routes._relative(local_manifest['checkpoint_root'])
        archived_checkpoint = {Path(name).relative_to(dependency).as_posix(): raw
                               for name, raw in local_bytes.items() if Path(name).is_relative_to(dependency)}
        require(archived_checkpoint == {p.relative_to(checkpoint).as_posix():p.read_bytes()
                for p in checkpoint.rglob('*') if p.is_file()}, 'local checkpoint closure differs')
        for name, raw in local_bytes.items():
            if Path(name).is_relative_to(dependency):
                continue
            require(name not in blobs, 'local archive paths overlap')
            blobs[name] = raw
            manifest['files'][name] = local_manifest['files'][name]
        manifest['historical_roots'] += local_manifest['historical_roots']
        manifest['local_roots'] = local_manifest['historical_roots']
        manifest['dependency_roots'] += local_manifest['dependency_roots']
        for key in ('historical_fk_source', 'local_controls'):
            manifest[key] = local_manifest[key]
        controls = local_manifest['local_controls']
        expected = {root + '/report.json' for root in local_manifest['historical_roots']
                    if root + '/report.json' in local_manifest['files']}
        require(len(controls) == len(expected) == 4 and {r['report'] for r in controls} == expected,
                'local control coverage incomplete')
        require(all(r['sha256'] == local_manifest['files'][r['report']]['sha256'] for r in controls),
                'local control identity differs')
        local_members = len(local_bytes)
    if body_reference is not None:
        manifest['checkpoint_consumers'] = True
        manifest['body_reference'] = json.loads(body_reference.read_text(encoding='utf-8'))
    groups = [routes._relative(name) for name in manifest['historical_roots'] + manifest['dependency_roots']]
    singles = set(manifest.get('standalone_files', []))
    require(all(sum(Path(name).is_relative_to(group) for group in groups) + (name in singles) == 1
                for name in blobs), 'archive member not restored exactly once')
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
                if name and (name.endswith('.py') or (name.startswith('rl_exp/versions/')
                             and name.endswith(('.json', '.yaml', '.yml')))):
                    put(name, (REPO / name).read_bytes())
            attributes = (REPO / '.gitattributes').read_bytes()
            attributes += (b'\n# Exact executed code/config bytes in this recovery fixture.\n/rl_exp/**/*.py -text\n'
                           b'/rl_exp/versions/**/*.json -text\n/rl_exp/versions/**/*.yaml -text\n/rl_exp/versions/**/*.yml -text\n')
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
            for name in manifest.get('standalone_files', []):
                put((Path('rl_exp/out/runs/archive-recovery') / name).as_posix(), blobs[name])
            location = checkpoint.relative_to(REPO) if body_reference is not None else Path('rl_exp/out/runs/archive-recovery/checkpoint')
            files = {}
            for path in sorted(checkpoint.rglob('*')):
                if path.is_file():
                    suffix = path.relative_to(checkpoint).as_posix()
                    raw = archived_checkpoint[suffix] if export_archive is not None or local_archive is not None else path.read_bytes()
                    files[suffix] = runtime.binding.sha256_bytes(raw)
                    put((location / suffix).as_posix(), raw)
            packages.append({'logical_root': runtime.BUILD.parent.relative_to(REPO).as_posix(),
                             'current_location': location.as_posix(),
                             'relocation': {'original_absolute_root': str(old_repo / runtime.BUILD.parent.relative_to(REPO)),
                                            'files': files}})
            if body_reference is not None:
                config = 'rl_exp/tools/diagnose/body_precheck_lizard2.json'
                put(config, (REPO / config).read_bytes())
                export = current.resolve(EXPORT / 'export.json')
                exported = json.loads(export.read_text())
                export_location = export.parent.relative_to(REPO)
                for name in ['export.json', *exported['files_sha256']]:
                    path = export.parent / name
                    put(path.relative_to(REPO).as_posix(), path.read_bytes())
                packages.append({'logical_root': EXPORT.relative_to(REPO).as_posix(),
                    'current_location': export_location.as_posix(), 'relocation': {
                    'original_absolute_root': str(old_repo / EXPORT.relative_to(REPO)),
                    'files': {name: routes.sha256_file(export.parent / name)
                              for name in ['export.json', *exported['files_sha256']]}}})
                for name in ('runtime_report.json', 'manifest.json', 'palm_spatial.urdf', 'palm_spatial.usda'):
                    path = runtime.REGISTERED_INPUT / name
                    put(path.relative_to(REPO).as_posix(), path.read_bytes())
                for path in runtime.obs_protocol.urdf_refs(runtime.REGISTERED_INPUT / 'palm_spatial.urdf'):
                    put(path.relative_to(REPO).as_posix(), path.read_bytes())
                mother = runtime.obs_protocol.body_for_task(runtime.REGISTERED_TASK)
                mother_names = []
                for path in {mother['usd'], mother['urdf'], *mother['refs']}:
                    name = path.relative_to(REPO).as_posix()
                    put(name, path.read_bytes())
                    mother_names.append(name)
                attributes = (source / '.gitattributes').read_bytes()
                attributes += b'\n# Exact declared mother-body inputs used by registered preparation.\n'
                attributes += ''.join('/' + name + ' -text\n' for name in sorted(mother_names)).encode()
                put('.gitattributes', attributes)
                if blender is not None:
                    for original_name, saved_name in (('generate_urdf.py', 'generate-before.py'),
                                                       ('lizard2_stance_candidate.py', 'stance-before.py')):
                        name = 'rl_exp/blender/scripts/' + original_name
                        put('rl_exp/out/' + saved_name, git_boundary.git(REPO, 'show', '21a9260:' + name).stdout)
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
            if body_reference is not None:
                require('CHECKPOINT_CONSUMERS_OK ' in child.stdout, 'checkpoint consumers not exercised')
            if export_archive is not None:
                require('EXPORT_ARCHIVE_RECOVERY_OK ' in child.stdout, 'export history consumers not exercised')
            if local_archive is not None:
                require('LOCAL_ARCHIVE_RECOVERY_OK ' in child.stdout, 'local history consumers not exercised')
            if blender is not None:
                native = subprocess.run([str(blender), '--background', '--factory-startup', '--python-exit-code', '1',
                                         '--python-expr', BLENDER_RECOVERY_CHILD, '--', str(clone), str(old_repo)],
                                        cwd=clone, capture_output=True, text=True, encoding='utf-8',
                                        errors='replace', timeout=240)
                (proof / ('blender-' + autocrlf + '.log')).write_text(native.stdout + native.stderr, encoding='utf-8')
                require(native.returncode == 0 and 'BLENDER_RECOVERY_OK ' in native.stdout,
                        native.stdout + native.stderr)
            results.append({'autocrlf': autocrlf, 'files_raw_blob_checkout_equal': len(names),
                            'archive_members_restored': len(blobs), 'child_passed': True,
                            'blender_passed': blender is not None, 'export_archive_members_restored': export_members,
                            'local_archive_members_restored': local_members})
    result = {'archive_sha256': routes.sha256_file(archive), 'results': results}
    if body_reference is not None:
        result['body_reference_sha256'] = routes.sha256_file(body_reference)
    if export_archive is not None:
        result['export_archive_sha256'] = routes.sha256_file(export_archive)
    if local_archive is not None:
        result['local_archive_sha256'] = routes.sha256_file(local_archive)
    (proof / 'checks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('CONSOLIDATED_ARCHIVE_OK ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--proof_root', type=Path)
    parser.add_argument('--body_reference', type=Path)
    parser.add_argument('--blender', type=Path)
    parser.add_argument('--export_archive', type=Path)
    parser.add_argument('--local_archive', type=Path)
    options, remaining = parser.parse_known_args()
    if options.archive is not None:
        if options.proof_root is None or remaining:
            parser.error('--archive requires --proof_root and no unittest selectors')
        if (options.blender is not None or options.export_archive is not None) and options.body_reference is None:
            parser.error('--blender and --export_archive require --body_reference')
        verify_consolidated_archive(options.archive.resolve(), options.proof_root.resolve(),
                                    options.body_reference, options.blender, options.export_archive, options.local_archive)
    else:
        if any(option is not None for option in (options.body_reference, options.proof_root,
                                               options.blender, options.export_archive, options.local_archive)):
            parser.error('recovery options require --archive')
        unittest.main(argv=[sys.argv[0], *remaining])
