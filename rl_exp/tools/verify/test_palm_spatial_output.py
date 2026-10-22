# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Exercise the spatial CLI's lifecycle with collection replaced, not record writes."""

from contextlib import redirect_stdout
import argparse
import builtins
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / 'diagnose'))
import palm_spatial_probe as probe
from artifact_paths import ArtifactPaths
from artifact_run import inspect_run
import artifact_paths as locator


class SpatialOutputTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.index = self.repo / 'rl_exp/tools/diagnose/artifact_index.json'
        self.index.parent.mkdir(parents=True)
        self.index.write_text(json.dumps({'format': 1, 'packages': []}))
        self.candidate = self.repo / 'candidate/body.urdf'
        self.candidate.parent.mkdir()
        assets = [self.candidate, self.candidate.with_suffix('.blend'), self.candidate.parent / 'mesh.obj']
        for path in assets:
            path.write_bytes(b'bound fixture asset')
        self.candidate.write_text('<robot name="fixture"><link name="base"><visual><geometry>'
                                  '<mesh filename="mesh.obj"/></geometry></visual></link></robot>')
        declaration = self.repo / 'rl_exp/versions/lizard2/assets.json'
        declaration.parent.mkdir(parents=True)
        declaration.write_text('{}')
        self.build = self.repo / 'candidate/build.json'
        self.build.write_text(json.dumps({
            'candidate_urdf': str(self.candidate), 'candidate_sha256': probe.digest(self.candidate),
            'candidate_blend_sha256': probe.digest(self.candidate.with_suffix('.blend')),
            'candidate_files_sha256': {p.name: probe.digest(p) for p in assets},
            'source_urdf': str(self.candidate), 'input_sha256': {}, 'naming': 'palm_spatial'}))
        self.source = self.repo / 'source.json'
        self.source.write_text('{}')
        self.out = self.repo / 'rl_exp/out/runs/spatial/fixture'

    def invoke(self, mode, writer):
        flags = {'static': ['--static_slices'], 'refine': ['--refine_slices', '--source_report', str(self.source),
                                                      '--angle_resolution', '0.01'],
                 'local': ['--local_path'], 'historical': []}[mode]
        function = {'static': '_static_slices', 'refine': '_refine_slices',
                    'local': '_local_path', 'historical': '_historical_probe'}[mode]
        argv = [str(Path(probe.__file__)), '--build_report', str(self.build), '--output_dir', str(self.out), *flags]
        with patch.object(probe, 'REPO', self.repo), patch.object(sys, 'argv', argv), \
                patch.object(probe, function, side_effect=writer, create=True), redirect_stdout(io.StringIO()):
            probe.main()

    def write_result(self, mode):
        record = json.loads((self.out / 'run.json').read_text())
        self.assertEqual(record['state'], 'running')
        registrations = json.loads(self.index.read_text())['packages']
        self.assertEqual(len(registrations), 1)
        self.assertEqual(registrations[0]['run_record'], self.out.relative_to(self.repo).as_posix() + '/run.json')
        (self.out / 'report.json').write_text(json.dumps({'geometry_result': 'unchanged'}))
        if mode in ('static', 'historical'):
            (self.out / ('static_slices.png' if mode == 'static' else 'comparison.png')).write_bytes(b'plot fixture')

    def test_all_modes_register_before_writing_and_finish(self):
        for mode in ('static', 'refine', 'local', 'historical'):
            with self.subTest(mode=mode):
                self.out = self.out.with_name(mode)
                self.index.write_text(json.dumps({'format': 1, 'packages': []}))
                self.invoke(mode, lambda *args: self.write_result(mode))
                self.assertEqual(inspect_run(self.out, ArtifactPaths(self.index, self.repo))['state'], 'completed')
                doc = json.loads((self.out / 'run.json').read_text())
                self.assertTrue(any(r['identity'] == str(self.build) for r in doc['inputs']))
                self.assertTrue(any(r['identity'] == str(self.candidate) for r in doc['inputs']))
                self.assertEqual((self.out / 'report.json').read_text(), json.dumps({'geometry_result': 'unchanged'}))

    def test_partial_write_failure_is_owned_and_duplicate_preserves_all_bytes(self):
        def failed(*args):
            self.write_result('static')
            raise OSError('injected plot failure after partial write')

        with self.assertRaisesRegex(OSError, 'injected plot failure'):
            self.invoke('static', failed)
        doc = json.loads((self.out / 'run.json').read_text())
        self.assertEqual(doc['state'], 'failed')
        self.assertTrue(doc['next'])
        files = {p: p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
        original_index = self.index.read_bytes()
        with self.assertRaises(FileExistsError):
            self.invoke('static', lambda *args: self.fail('duplicate reached collection'))
        self.assertEqual({p: p.read_bytes() for p in self.out.rglob('*') if p.is_file()}, files)
        self.assertEqual(self.index.read_bytes(), original_index)
        with self.assertRaises(ValueError):
            inspect_run(self.out, ArtifactPaths(self.index, self.repo))

    def test_registration_failure_stops_collection(self):
        replace = os.replace

        def failed(source, destination):
            if Path(destination) == self.index:
                raise OSError('injected index failure')
            return replace(source, destination)

        with patch.object(os, 'replace', failed), self.assertRaisesRegex(OSError, 'injected index failure'):
            self.invoke('local', lambda *args: self.fail('unregistered run reached collection'))
        self.assertFalse((self.out / 'report.json').exists())
        self.assertEqual(json.loads((self.out / 'run.json').read_text())['state'], 'failed')

    def test_input_change_at_collection_prevents_completion(self):
        def changed(*args):
            self.write_result('local')
            self.candidate.write_bytes(b'input changed during collection')

        with self.assertRaises(ValueError):
            self.invoke('local', changed)
        self.assertEqual(json.loads((self.out / 'run.json').read_text())['state'], 'failed')

    def test_modern_mode_does_not_reread_provenance_only_sources(self):
        build = json.loads(self.build.read_text())
        build['input_sha256'] = {str(self.repo / 'missing-original.blend'): '0' * 64}
        self.build.write_text(json.dumps(build))
        self.invoke('local', lambda *args: self.write_result('local'))
        self.assertEqual(inspect_run(self.out, ArtifactPaths(self.index, self.repo))['state'], 'completed')

    def test_inconsistent_candidate_binding_fails_before_creation(self):
        build = json.loads(self.build.read_text())
        build['candidate_sha256'] = '0' * 64
        self.build.write_text(json.dumps(build))
        with self.assertRaises(ValueError):
            self.invoke('local', lambda *args: self.fail('wrong input reached collection'))
        self.assertFalse(self.out.exists())

    def test_python_optimization_refuses_before_dependency_imports(self):
        for flag, value in (('-O', None), ('-OO', None), (None, '1'), (None, '2')):
            with self.subTest(flag=flag, environment=value):
                command = [sys.executable, *([flag] if flag else []), '-B', str(Path(probe.__file__)),
                           '--local_path', '--build_report', str(self.build), '--output_dir', str(self.out)]
                environment = dict(os.environ)
                environment.pop('PYTHONOPTIMIZE', None)
                if value:
                    environment['PYTHONOPTIMIZE'] = value
                result = subprocess.run(command, env=environment, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('palm_spatial_probe does not support Python optimization', result.stderr)
                self.assertFalse(self.out.exists())


def real_failures(build: Path, proof: Path) -> None:
    """Inject actual plot/report failures with a real candidate, preserving owned scenes."""
    if proof.exists():
        raise FileExistsError(proof)
    proof.mkdir(parents=True)
    results = []
    for mode in ('static', 'historical'):
        output = proof / mode
        argv = [str(Path(probe.__file__)), '--build_report', str(build), '--output_dir', str(output)]
        if mode == 'static':
            argv.append('--static_slices')
        original_write = Path.write_text

        def fail_report(path, *args, **kwargs):
            if path == output / 'report.json':
                raise OSError('injected actual report write failure')
            return original_write(path, *args, **kwargs)

        failure = (patch.object(Path, 'write_text', fail_report) if mode == 'static' else
                   patch.object(probe, 'plot', side_effect=OSError('injected plot failure after actual report')))
        with patch.object(sys, 'argv', argv), failure:
            try:
                probe.main()
            except OSError as error:
                assert 'injected' in str(error), error
            else:
                raise AssertionError('injected writer failure was hidden')
        record = json.loads((output / 'run.json').read_text(encoding='utf-8'))
        assert record['state'] == 'failed' and record['owner'] and record['next']
        expected = 'static_slices.png' if mode == 'static' else 'report.json'
        assert (output / expected).is_file() and len(record['outputs']) == 1
        original = {p: p.read_bytes() for p in output.rglob('*') if p.is_file()}
        index = probe.REPO / 'rl_exp/tools/diagnose/artifact_index.json'
        index_before = index.read_bytes()
        with patch.object(sys, 'argv', argv):
            try:
                probe.main()
            except FileExistsError:
                pass
            else:
                raise AssertionError('duplicate failed scene accepted')
        assert {p: p.read_bytes() for p in output.rglob('*') if p.is_file()} == original
        assert index.read_bytes() == index_before
        results.append({'mode': mode, 'state': record['state'], 'outputs': record['outputs'],
                        'duplicate_bytes_preserved': True})
    (proof / 'checks.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('REAL_SPATIAL_FAILURES_OK', json.dumps(results), flush=True)


def real_relocation(build: Path, source: Path, proof: Path) -> None:
    """Run refinement from mapped current locations while denying all old-root reads."""
    if proof.exists():
        raise FileExistsError(proof)
    proof.mkdir(parents=True)
    original_build = json.loads(build.read_text(encoding='utf-8'))
    original_source = json.loads(source.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='restore_', dir=proof) as temporary:
        scratch = Path(temporary)
        assert scratch.resolve().is_relative_to(proof.resolve()), 'temporary restore root escaped proof directory'
        routes = []
        for old, destination, files in (
                (build.parent, scratch / 'candidate', {build.name: probe.digest(build),
                                                     **original_build['candidate_files_sha256']}),
                (source.parent, scratch / 'source', {source.name: probe.digest(source)})):
            for name in files:
                target = destination / locator._relative(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(old / name, target)
            routes.append({'logical_root': old.relative_to(probe.REPO).as_posix(),
                           'current_location': destination.relative_to(probe.REPO).as_posix(),
                           'relocation': {'original_absolute_root': str(old), 'files': files}})
        index = scratch / 'index.json'
        index.write_text(json.dumps({'format': 1, 'packages': routes}), encoding='utf-8')
        paths = ArtifactPaths(index, probe.REPO)
        denied_roots = (build.parent, source.parent)
        original_open, original_path_open, original_os_open = builtins.open, Path.open, os.open

        def check(path):
            if isinstance(path, (str, bytes, os.PathLike)):
                actual = Path(os.fsdecode(path)).absolute()
                if any(actual.is_relative_to(root) for root in denied_roots):
                    raise PermissionError(f'old root read blocked: {actual}')

        def guarded_open(path, *args, **kwargs):
            check(path)
            return original_open(path, *args, **kwargs)

        def guarded_path_open(path, *args, **kwargs):
            check(path)
            return original_path_open(path, *args, **kwargs)

        def guarded_os_open(path, *args, **kwargs):
            check(path)
            return original_os_open(path, *args, **kwargs)

        output = scratch / 'result'
        current_build, current_source = scratch / 'candidate' / build.name, scratch / 'source' / source.name
        argv = [str(Path(probe.__file__)), '--refine_slices', '--build_report', str(current_build),
                '--source_report', str(current_source), '--angle_resolution', '0.01', '--output_dir', str(output)]
        with patch.object(probe, 'ArtifactPaths', return_value=paths), \
                patch.object(locator, 'ArtifactPaths', return_value=paths), \
                patch.object(builtins, 'open', guarded_open), patch.object(Path, 'open', guarded_path_open), \
                patch.object(os, 'open', guarded_os_open), patch.object(sys, 'argv', argv):
            for reader in (lambda: builtins.open(build, 'rb'), lambda: build.open('rb'),
                           lambda: os.open(build, os.O_RDONLY)):
                try:
                    reader()
                except PermissionError:
                    pass
                else:
                    raise AssertionError('old-root isolation was bypassed')
            probe.main()
            inspection = inspect_run(output, paths)
            report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
            record = json.loads((output / 'run.json').read_text(encoding='utf-8'))
            assert report['checked_pairs'] == original_source['checked_pairs'] and report['bracket_count'] > 0
            assert all(row['angle_width_rad'] <= 0.01 for row in report['brackets'])
            assert any(row['identity'] == str(build) and row['location'] == current_build.relative_to(probe.REPO).as_posix()
                       and row['sha256'] == probe.digest(current_build) for row in record['inputs'])
            result = {'inspection': inspection, 'old_roots_unreadable': True, 'three_read_guards_verified': True,
                      'current_locations_used': True, 'bracket_count': report['bracket_count'],
                      'report_sha256': probe.digest(output / 'report.json')}
            source_bytes = current_source.read_bytes()
            source_manifest = next(files for _, current, (_, files) in paths.routes if current == scratch / 'source')
            rejected = []
            for defect in ('build_identity', 'code_identity', 'code_digest'):
                changed = json.loads(source_bytes)
                if defect == 'build_identity':
                    changed['identity']['build_report'] = str(probe.REPO / 'different-family' / build.name)
                else:
                    codes = changed['identity']['code_sha256']
                    key = next(k for k in codes if Path(k).name == 'check_self_collision.py')
                    if defect == 'code_identity':
                        codes[str(probe.REPO / 'different-family' / Path(key).name)] = codes.pop(key)
                    else:
                        codes[key] = '0' * 64
                current_source.write_text(json.dumps(changed), encoding='utf-8')
                source_manifest[source.name] = probe.digest(current_source)
                index_doc = json.loads(index.read_text(encoding='utf-8'))
                index_doc['packages'][1]['relocation']['files'][source.name] = source_manifest[source.name]
                index.write_text(json.dumps(index_doc), encoding='utf-8')
                bad_output = scratch / ('reject-' + defect)
                bad_argv = argv.copy()
                bad_argv[bad_argv.index('--output_dir') + 1] = str(bad_output)
                with patch.object(sys, 'argv', bad_argv):
                    try:
                        probe.main()
                    except AssertionError as error:
                        assert 'identity' in str(error) or 'changed' in str(error), error
                    else:
                        raise AssertionError(f'{defect} was accepted')
                assert json.loads((bad_output / 'run.json').read_text(encoding='utf-8'))['state'] == 'failed'
                assert not (bad_output / 'report.json').exists()
                rejected.append(defect)
            current_source.write_bytes(source_bytes)
            source_manifest[source.name] = probe.digest(current_source)
            index_doc = json.loads(index.read_text(encoding='utf-8'))
            index_doc['packages'][1]['relocation']['files'][source.name] = source_manifest[source.name]
            index.write_text(json.dumps(index_doc), encoding='utf-8')
            inspect_run(output, paths)
            result['wrong_identity_and_digest_rejected'] = rejected
    (proof / 'checks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('REAL_SPATIAL_RELOCATION_OK', json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--real_build', type=Path)
    parser.add_argument('--proof_dir', type=Path)
    parser.add_argument('--relocation_source', type=Path)
    options, remaining = parser.parse_known_args()
    result = unittest.main(argv=[sys.argv[0], *remaining], verbosity=2, exit=False)
    if not result.result.wasSuccessful():
        raise SystemExit(1)
    if options.real_build or options.proof_dir or options.relocation_source:
        if options.real_build is None or options.proof_dir is None:
            parser.error('--real_build and --proof_dir must be supplied together')
        if options.relocation_source:
            real_relocation(options.real_build.resolve(), options.relocation_source.resolve(), options.proof_dir.resolve())
        else:
            real_failures(options.real_build.resolve(), options.proof_dir.resolve())
