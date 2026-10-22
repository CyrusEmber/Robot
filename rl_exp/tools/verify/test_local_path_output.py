# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Check local-path producer ownership at the real registration/write boundary."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diagnose'))
import local_path_check as check
from artifact_paths import ArtifactPaths
from artifact_run import inspect_run


class LocalPathOutputTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.index = self.root / 'rl_exp/tools/diagnose/artifact_index.json'
        self.index.parent.mkdir(parents=True)
        self.index.write_text(json.dumps({'format': 1, 'packages': []}))
        self.input = self.root / 'source.json'
        self.input.write_text('{}')
        self.output = self.root / 'rl_exp/out/runs/local-path-check/test'
        self.paths = ArtifactPaths(self.index, self.root)
        bound = self.paths.describe(self.input)
        self.metadata = dict(topic='local-path-check', work_id='diagnostic-artifact-lifecycle',
                             owner='test-executor', retention_reason='real lifecycle boundary fixture',
                             command=['python', 'fixture'], inputs=[bound], code=[bound])

    def invoke(self, writer, **options):
        with patch.object(check, 'REPO', self.root), \
                patch.object(check.view, 'ArtifactPaths', return_value=self.paths), \
                patch.object(check.view, '_run_metadata', return_value=self.metadata), \
                patch.object(check, '_collect', side_effect=writer, create=True), redirect_stdout(io.StringIO()):
            check._run(self.input, self.output, **options)

    def writer(self, *args, **kwargs):
        self.assertEqual(json.loads((self.output / 'run.json').read_text())['state'], 'running')
        self.assertEqual(len(json.loads(self.index.read_text())['packages']), 1)
        (self.output / 'report.json').write_text('{"geometry":"retained"}')

    def test_four_modes_owned_before_collection_and_completed(self):
        for name, options in [('quarters', {}), ('mirror', {'mirror': True}),
                              ('combined', {'combined': True}),
                              ('support', {'combined': True, 'support_schedule': True})]:
            with self.subTest(mode=name):
                self.output = self.output.with_name(name)
                self.index.write_text(json.dumps({'format': 1, 'packages': []}))
                self.invoke(self.writer, **options)
                self.assertEqual(inspect_run(self.output, self.paths)['state'], 'completed')

    def test_partial_report_failure_retained_and_duplicate_never_collects(self):
        def failed(*args, **kwargs):
            self.writer()
            raise OSError('injected failure after actual report write')
        with self.assertRaisesRegex(OSError, 'actual report write'):
            self.invoke(failed)
        record = json.loads((self.output / 'run.json').read_text())
        self.assertEqual(record['state'], 'failed')
        self.assertTrue(record['owner'] and record['next'])
        files = {p: p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        index = self.index.read_bytes()
        with self.assertRaises(FileExistsError):
            self.invoke(lambda *a, **k: self.fail('duplicate collected'))
        self.assertEqual(files, {p: p.read_bytes() for p in self.output.rglob('*') if p.is_file()})
        self.assertEqual(index, self.index.read_bytes())

    def test_failed_registration_stops_collection(self):
        replace = os.replace
        def failed(source, destination):
            if Path(destination) == self.index:
                raise OSError('injected index failure')
            return replace(source, destination)
        with patch.object(os, 'replace', failed), self.assertRaisesRegex(OSError, 'index failure'):
            self.invoke(lambda *a, **k: self.fail('unregistered collection'))
        self.assertEqual(json.loads((self.output / 'run.json').read_text())['state'], 'failed')
        self.assertFalse((self.output / 'report.json').exists())

    def test_changed_input_cannot_complete(self):
        def changed(*args, **kwargs):
            self.writer()
            self.input.write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'binding changed'):
            self.invoke(changed)
        self.assertEqual(json.loads((self.output / 'run.json').read_text())['state'], 'failed')

    def test_complete_mapped_identity_preserves_every_code_digest(self):
        old = self.root / 'old'
        new = self.root / 'new'
        new.mkdir()
        for name in ('build.json', 'code.py'):
            (new / name).write_text('same bytes')
        self.index.write_text(json.dumps({'format': 1, 'packages': [{
            'logical_root': 'old', 'current_location': 'new', 'relocation': {
                'original_absolute_root': str(old), 'files': {
                    name: self.paths.describe(new / name)['sha256'] for name in ('build.json', 'code.py')}}}]}))
        self.paths = ArtifactPaths(self.index, self.root)
        original = {'build_report': str(old / 'build.json'), 'candidate': 'same',
                    'code_sha256': {str(old / 'code.py'): 'a' * 64}}
        current = {'build_report': str(new / 'build.json'), 'candidate': 'same',
                   'code_sha256': {str(new / 'code.py'): 'a' * 64}}
        with patch.object(check, 'REPO', self.root), patch.object(check.view, 'ArtifactPaths', return_value=self.paths):
            check._source_identity(original, current)
            for bad in ({**current, 'candidate': 'changed'},
                        {**current, 'build_report': str(self.root / 'foreign/build.json')},
                        {**current, 'code_sha256': {str(new / 'code.py'): 'b' * 64}},
                        {**current, 'code_sha256': {str(self.root / 'foreign/code.py'): 'a' * 64}}):
                with self.assertRaises(AssertionError):
                    check._source_identity(original, bad)

    def test_saved_physical_location_resolves_only_with_exact_explicit_alias(self):
        actual = self.root / 'current'
        actual.mkdir()
        (actual / 'source.json').write_text('exact retained bytes')
        old = self.root / 'previous'
        entry = {'logical_root': 'logical', 'current_location': 'current', 'relocation': {
            'original_absolute_root': str(self.root / 'logical'),
            'original_absolute_locations': [str(old)],
            'files': {'source.json': self.paths.describe(actual / 'source.json')['sha256']}}}
        self.index.write_text(json.dumps({'format': 1, 'packages': [entry]}))
        paths = ArtifactPaths(self.index, self.root)
        self.assertEqual(paths.resolve(old / 'source.json'), actual / 'source.json')
        self.assertTrue(paths.same_identity(old / 'source.json', self.root / 'logical/source.json'))
        with self.assertRaises(ValueError):
            paths.resolve(old / 'unlisted.json')
        entry['relocation']['original_absolute_locations'] = ['relative/alias']
        self.index.write_text(json.dumps({'format': 1, 'packages': [entry]}))
        with self.assertRaises(ValueError):
            ArtifactPaths(self.index, self.root)
        entry['relocation']['original_absolute_locations'] = [str(self.root)]
        self.index.write_text(json.dumps({'format': 1, 'packages': [entry]}))
        with self.assertRaises(ValueError):
            ArtifactPaths(self.index, self.root)


def real_production(source, proof):
    """Run every real sampling mode, duplicate CLI and post-write failure."""
    proof.mkdir(parents=True, exist_ok=False)
    repo = Path(check.__file__).resolve().parents[3]
    paths = ArtifactPaths(storage_root=repo)
    snapshots = proof / 'executed-sources'
    snapshots.mkdir()
    def freeze(output):
        record = json.loads((output / 'run.json').read_text())
        for row in record['code']:
            original = repo / row['location']
            destination = snapshots / (row['sha256'] + '.py')
            raw = original.read_bytes()
            if check.view.digest(original) != row['sha256']:
                raise AssertionError('executed source changed before evidence capture')
            destination.write_bytes(raw)
            row['location'] = destination.relative_to(repo).as_posix()
        (output / 'run.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    for mode, flags in [('quarters', []), ('mirror', ['--mirror']), ('combined', ['--combined']),
                        ('support', ['--combined', '--support_schedule'])]:
        output = proof / mode
        command = [sys.executable, '-B', str(Path(check.__file__).resolve()),
                   '--source_report', str(source), '--output_dir', str(output), *flags]
        result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
        (proof / (mode + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        freeze(output)
        inspect_run(output, paths)
        files = {p.name: p.read_bytes() for p in output.iterdir()}
        index = paths.index.read_bytes()
        duplicate = subprocess.run(command, cwd=repo, capture_output=True, text=True)
        if not duplicate.returncode or 'FileExistsError' not in duplicate.stderr:
            raise AssertionError('duplicate CLI accepted')
        if files != {p.name: p.read_bytes() for p in output.iterdir()} or index != paths.index.read_bytes():
            raise AssertionError('duplicate modified existing bytes')
    write = Path.write_text
    def failed(path, text, *args, **kwargs):
        result = write(path, text, *args, **kwargs)
        if path == proof / 'failed' / 'report.json':
            raise OSError('injected failure after real serialized geometry report')
        return result
    with patch.object(Path, 'write_text', failed):
        try:
            check._run(source, proof / 'failed')
        except OSError as error:
            if 'real serialized' not in str(error):
                raise
        else:
            raise AssertionError('failure injection did not reach real writer')
    record = json.loads((proof / 'failed/run.json').read_text())
    if record['state'] != 'failed' or not (proof / 'failed/report.json').exists():
        raise AssertionError('actual partial report not retained as failed')
    freeze(proof / 'failed')
    (proof / 'checks.json').write_text(json.dumps({'four_real_modes': True, 'duplicate_cli_unchanged': True,
                                                  'partial_real_report_failed': True}), encoding='utf-8')
    print('LOCAL_PATH_PRODUCTION_OK', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--real_source' and sys.argv[3] == '--proof_dir':
        real_production(Path(sys.argv[2]).resolve(), Path(sys.argv[4]).resolve())
    else:
        unittest.main()
