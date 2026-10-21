# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Exercise lifecycle at the actual replay writer; real historical inputs, no physics.

Plots are tiny test payloads here; the production CLI and image content are exercised
separately. Each test owns all writes in a TemporaryDirectory.
"""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import stat
import tempfile
import time
from unittest.mock import patch
import unittest

import test_artifact_relocation as relocation

view = relocation.view
from artifact_run import ArtifactRun, inspect_run


REAL_CHILD = r'''
import builtins, io, json, os, runpy, sys
from pathlib import Path
root, old = map(Path, sys.argv[1:3])
command = json.loads(sys.argv[3])
attempts = []
def audit(event, args):
    if event != 'open' or isinstance(args[0], int):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    if path.is_relative_to(old):
        attempts.append(str(path))
        raise RuntimeError('OLD_ROOT_READ: ' + str(path))
sys.path[:] = [p for p in sys.path if p and not Path(p).resolve().is_relative_to(old)]
sys.path[:0] = [str(root / 'rl_exp/tools/diagnose'), str(root)]
sys.addaudithook(audit)
probe = old / 'rl_exp/tools/diagnose/local_path_view.py'
for read in (lambda: builtins.open(probe, 'rb'), lambda: io.FileIO(probe),
             lambda: os.open(probe, os.O_RDONLY)):
    try:
        read()
    except RuntimeError as error:
        if 'OLD_ROOT_READ:' not in str(error):
            raise
    else:
        raise AssertionError('old-root isolation failed')
blocked_probes = len(attempts)
attempts.clear()
script = root / command[2]
sys.argv = [str(script), *command[3:]]
runpy.run_path(str(script), run_name='__main__')
from artifact_paths import ArtifactPaths
from artifact_run import inspect_run
output = Path(command[command.index('--output_dir') + 1])
result = inspect_run(output, ArtifactPaths())
analysis = json.loads((output / 'analysis.json').read_text())
assert analysis['root_translation']['root_applied']
assert analysis['drive_limit_prerequisites']['drive_report_sha256']
assert all(r['sha256'] for r in analysis['input_bindings'])
assert not attempts, attempts
print('REAL_RECOVERY_OK ' + json.dumps(dict(result, blocked_probes=blocked_probes,
      positive_old_reads=len(attempts), drive_sha256=analysis['drive_limit_prerequisites']['drive_report_sha256'])))
'''


def verify_real_recovery(run):
    """Replay a real finished run, including Git checkout and denied legacy reads."""
    repo = relocation.REPO
    record = json.loads((run / 'run.json').read_text())
    inspect_run(run, relocation.routes.ArtifactPaths())
    before = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
    index = repo / 'rl_exp/tools/diagnose/artifact_index.json'
    index_before = index.read_bytes()
    repeated = subprocess.run([sys.executable, *record['command'][1:]], cwd=repo,
                              capture_output=True, text=True, timeout=60)
    if repeated.returncode == 0 or 'fresh isolated output required' not in repeated.stderr:
        raise AssertionError(repeated.stdout + repeated.stderr)
    if before != {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()} or index.read_bytes() != index_before:
        raise AssertionError('same-name rerun changed run or index')
    results = []
    with tempfile.TemporaryDirectory(prefix='diagnostic-real-recovery-') as temporary:
        owned = Path(temporary).resolve()
        for autocrlf in ('true', 'false'):
            case = owned / autocrlf
            case.mkdir()
            source = relocation.git_boundary.DiagnosticGitBoundaryTest().new_repo(case, autocrlf)
            files = {}
            for row in record['inputs'] + record['code']:
                location = Path(row['location'])
                if location.is_absolute() or not row['logical_path']:
                    raise ValueError('recovery requires repository-relative bound locations')
                files[location.as_posix()] = (repo / location).read_bytes()
            # A bound execution snapshot is evidence, including a dirty CRLF
            # checkout such as binding.py. Do not silently canonicalize its code.
            attributes = (repo / '.gitattributes').read_bytes()
            attributes += b'\n# Preserve exact source bytes bound by the restored run.\n'
            attributes += ''.join('/' + row['location'] + ' -text\n' for row in record['code']).encode()
            files['.gitattributes'] = attributes
            # Derive disjoint parent routes solely from the complete input closure.
            parents = {Path(row['identity']).parent for row in record['inputs']}
            parents = {p for p in parents if not any(p != q and p.is_relative_to(q) for q in parents)}
            packages = []
            for parent in sorted(parents):
                rows = [r for r in record['inputs'] if Path(r['identity']).is_relative_to(parent)]
                manifest, destinations = {}, set()
                for row in rows:
                    suffix = Path(row['identity']).relative_to(parent)
                    target = Path(row['location'])
                    destination = target.parents[len(suffix.parts) - 1]
                    destinations.add(destination)
                    manifest[suffix.as_posix()] = row['sha256']
                if len(destinations) != 1:
                    raise ValueError('inconsistent recovery route')
                packages.append({'logical_root': parent.relative_to(repo).as_posix(),
                                 'current_location': destinations.pop().as_posix(),
                                 'relocation': {'original_absolute_root': str(parent), 'files': manifest}})
            files['rl_exp/tools/diagnose/artifact_index.json'] = json.dumps(
                {'format': 1, 'packages': packages}, indent=2).encode()
            for name, raw in files.items():
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            git = relocation.git_boundary.git
            git(source, 'add', '--', *files)
            git(source, 'commit', '-q', '-m', 'Bound producer recovery fixture')
            clone = case / 'clone'
            git(case, '-c', 'core.autocrlf=' + autocrlf, 'clone', '-q', str(source), str(clone))
            for name, raw in files.items():
                if git(source, 'show', 'HEAD:' + name).stdout != raw or (clone / name).read_bytes() != raw:
                    raise AssertionError('recovery Git bytes changed: ' + name)
            if not source.resolve().is_relative_to(owned) or source.resolve() == owned:
                raise AssertionError('unsafe temporary source cleanup')
            def writable(function, name, error):
                if not isinstance(error, PermissionError) or not Path(name).resolve().is_relative_to(source.resolve()):
                    raise error
                Path(name).chmod(stat.S_IWRITE)
                function(name)
            shutil.rmtree(source, onexc=writable)
            command = list(record['command'])
            output = clone / 'rl_exp/out/runs/local-path-view/restored'
            command[command.index('--output_dir') + 1] = str(output)
            child = subprocess.run([sys.executable, '-I', '-B', '-c', REAL_CHILD,
                                    str(clone), str(repo), json.dumps(command)],
                                   cwd=clone, capture_output=True, text=True, timeout=300)
            if child.returncode or 'REAL_RECOVERY_OK ' not in child.stdout:
                raise AssertionError(child.stdout + child.stderr)
            result = json.loads(child.stdout.split('REAL_RECOVERY_OK ', 1)[1])
            # Compare actual produced pixels and numerical reports, not merely filenames.
            from PIL import Image, ImageChops
            for name in record['outputs']:
                if Path(name).suffix not in ('.png', '.gif'):
                    continue
                with Image.open(run / name) as first, Image.open(output / name) as second:
                    if first.size != second.size or first.n_frames != second.n_frames:
                        raise AssertionError('restored image shape/frame count changed: ' + name)
                    for frame in range(first.n_frames):
                        first.seek(frame)
                        second.seek(frame)
                        if ImageChops.difference(first.convert('RGB'), second.convert('RGB')).getbbox():
                            raise AssertionError('restored image pixels changed: ' + name)
            original_analysis = json.loads((run / 'analysis.json').read_text())
            restored_analysis = json.loads((output / 'analysis.json').read_text())
            for field in ('root_translation', 'root_motion_prerequisites', 'time_mapping_prerequisites', 'legs'):
                if original_analysis[field] != restored_analysis[field]:
                    raise AssertionError('restored analysis changed: ' + field)
            result.update(autocrlf=autocrlf, git_files=len(files), all_image_pixels_equal=True,
                          same_name_rejected_unchanged=True)
            results.append(result)
            print('RECOVERY_PROOF ' + json.dumps(result), flush=True)
    print('RECOVERY_CLEANED ' + json.dumps({'temporary_root_removed': not owned.exists()}), flush=True)
    return results


class ArtifactRunTest(unittest.TestCase):
    def setUp(self):
        self.fixture = relocation.RelocationTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        _, _, self.source, self.drive = self.fixture.drive_fixture()
        self.output = self.fixture.root / 'rl_exp/out/replay'
        binding = self.fixture.root / 'rl_exp/tools/runrecord/binding.py'
        binding.parent.mkdir(parents=True)
        shutil.copyfile(relocation.REPO / 'rl_exp/tools/runrecord/binding.py', binding)

    def call_writer(self, render=None):
        def plot(output, leg, stats, plt):
            # Metadata and route must precede the first real artifact write.
            record = output / 'run.json'
            self.assertTrue(record.is_file(), 'no ownership record before producer write')
            self.assertEqual(json.loads(record.read_text())['state'], 'running')
            index = json.loads(self.fixture.index.read_text())
            self.assertTrue(any(e.get('run_record') == 'rl_exp/out/replay/run.json'
                                for e in index['packages']), 'producer wrote before registration')
            (output / (leg + '_trajectory.png')).write_bytes(b'plot-payload')

        def default_render(output, *args):
            (output / 'combined_side.gif').write_bytes(b'side-payload')
            (output / 'combined_top.gif').write_bytes(b'top-payload')

        with patch.object(view, 'REPO', self.fixture.root), \
                patch.object(view, 'ArtifactPaths', lambda: self.fixture.paths), \
                patch.object(view, 'artifact_path', self.fixture.paths.resolve), \
                patch.object(view, '_plot', plot), patch.object(view, '_render', render or default_render), \
                self.fixture.isolated(), redirect_stdout(io.StringIO()):
            view._run(self.source, self.output, drive_report=self.drive, apply_root_translation=True)

    def test_real_writer_registers_and_finishes_then_rejects_same_name(self):
        self.call_writer()
        record = json.loads((self.output / 'run.json').read_text())
        self.assertEqual(record['state'], 'completed')
        self.assertEqual(record['retention']['decision'], 'retain')
        self.assertTrue(record['inputs'])
        self.assertTrue(record['code'])
        self.assertIn('analysis.json', record['outputs'])
        self.assertEqual(inspect_run(self.output, self.fixture.paths)['state'], 'completed')
        original = {p.name: p.read_bytes() for p in self.output.iterdir() if p.is_file()}
        with self.assertRaises((AssertionError, FileExistsError)):
            self.call_writer()
        self.assertEqual({p.name: p.read_bytes() for p in self.output.iterdir() if p.is_file()}, original)

    def test_output_corruption_and_missing_registration_are_rejected(self):
        self.call_writer()
        path = self.output / 'analysis.json'
        raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            inspect_run(self.output, self.fixture.paths)
        path.write_bytes(raw)
        # Restore the original index to model a lost registration, not a lost report.
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, 'registration'):
            inspect_run(self.output, self.fixture.paths)

    def test_missing_initial_record_is_incomplete_and_retained(self):
        self.output.mkdir()
        with self.assertRaises(FileNotFoundError):
            inspect_run(self.output, self.fixture.paths)
        self.assertTrue(self.output.is_dir())

    def test_initial_record_write_failure_prevents_registration(self):
        with patch.object(ArtifactRun, '_save', side_effect=OSError('initial record unavailable')):
            with self.assertRaisesRegex(OSError, 'initial record unavailable'):
                self.call_writer()
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertFalse(any(e.get('run_record') for e in json.loads(self.fixture.index.read_text())['packages']))

    def test_partial_write_failure_retains_owned_failed_run(self):
        def broken(output, *args):
            (output / 'partial.gif').write_bytes(b'partial')
            raise OSError('injected rendering failure')
        with self.assertRaisesRegex(OSError, 'injected rendering failure'):
            self.call_writer(broken)
        record = json.loads((self.output / 'run.json').read_text())
        self.assertEqual(record['state'], 'failed')
        self.assertEqual(record['retention']['decision'], 'retain_failure')
        self.assertTrue(record['owner'])
        self.assertTrue(record['next'])
        self.assertEqual((self.output / 'partial.gif').read_bytes(), b'partial')

    def test_registration_failure_prevents_artifact_writes(self):
        raw_replace = os.replace
        def failed(source, destination, *args, **kwargs):
            if Path(destination).resolve() == self.fixture.index.resolve():
                raise OSError('injected registration failure')
            return raw_replace(source, destination, *args, **kwargs)
        with patch.object(os, 'replace', failed):
            with self.assertRaisesRegex(OSError, 'injected registration failure'):
                self.call_writer()
        self.assertFalse(list(self.output.glob('*.png')))
        self.assertFalse((self.output / 'analysis.json').exists())
        record = json.loads((self.output / 'run.json').read_text())
        self.assertEqual(record['state'], 'failed')

    def test_finish_write_failure_never_reports_completed(self):
        raw_replace = os.replace
        def failed(source, destination, *args, **kwargs):
            if Path(destination) == self.output / 'run.json':
                state = json.loads(Path(source).read_text())['state']
                if state in ('completed', 'failed'):
                    raise OSError('injected terminal record failure')
            return raw_replace(source, destination, *args, **kwargs)
        with patch.object(os, 'replace', failed):
            with self.assertRaisesRegex(OSError, 'injected terminal record failure'):
                self.call_writer()
        self.assertEqual(json.loads((self.output / 'run.json').read_text())['state'], 'running')
        self.assertTrue((self.output / 'analysis.json').exists())
        with self.assertRaisesRegex(ValueError, 'incomplete run: running'):
            inspect_run(self.output, self.fixture.paths)

    def test_single_terminal_write_failure_retains_next_action(self):
        raw_replace = os.replace
        def failed(source, destination, *args, **kwargs):
            if Path(destination) == self.output / 'run.json':
                if json.loads(Path(source).read_text())['state'] == 'completed':
                    raise OSError('terminal write failed once')
            return raw_replace(source, destination, *args, **kwargs)
        with patch.object(os, 'replace', failed):
            with self.assertRaisesRegex(OSError, 'terminal write failed once'):
                self.call_writer()
        record = json.loads((self.output / 'run.json').read_text())
        self.assertEqual(record['state'], 'failed')
        self.assertTrue(record['next'])

    def test_input_changes_during_render_prevent_success(self):
        def changed(output, *args):
            (output / 'combined_side.gif').write_bytes(b'side')
            (output / 'combined_top.gif').write_bytes(b'top')
            location = self.fixture.paths.resolve(self.source)
            location.write_bytes(location.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'binding changed'):
            self.call_writer(changed)
        record = json.loads((self.output / 'run.json').read_text())
        self.assertEqual(record['state'], 'failed')
        self.assertTrue(record['next'])

    def test_killed_process_leaves_owned_incomplete_run(self):
        child = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from artifact_paths import ArtifactPaths
from artifact_run import ArtifactRun
root, index, output = map(Path, sys.argv[2:])
paths = ArtifactPaths(index, root)
bound = paths.describe(index)
metadata = dict(topic='kill-test', work_id='diagnostic-artifact-lifecycle', owner='test-executor',
                command=['test-child'], inputs=[bound], code=[bound], retention_reason='interrupted test')
# The index is a mutable output, so use a separate immutable input/code fixture.
fixture = root / 'fixture.txt'
fixture.write_text('bound bytes')
metadata['inputs'] = metadata['code'] = [paths.describe(fixture)]
with ArtifactRun(output, paths, metadata, ['analysis.json']):
    (output / 'partial.gif').write_bytes(b'interrupted payload')
    print('WRITING', flush=True)
    time.sleep(120)
'''
        process = subprocess.Popen([sys.executable, '-I', '-B', '-c', child,
                                    str(relocation.REPO / 'rl_exp/tools/diagnose'), str(self.fixture.root),
                                    str(self.fixture.index), str(self.output)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 15
            while not (self.output / 'partial.gif').exists() and process.poll() is None:
                if time.monotonic() > deadline:
                    self.fail('child never reached producer write')
                time.sleep(.05)
            self.assertIsNone(process.poll())
        finally:
            process.kill()
            process.communicate(timeout=10)
        record = json.loads((self.output / 'run.json').read_text())
        self.assertEqual(record['state'], 'running')
        self.assertEqual(record['owner'], 'test-executor')
        self.assertTrue(record['next'])
        with self.assertRaisesRegex(ValueError, 'incomplete run: running'):
            inspect_run(self.output, self.fixture.paths)
        self.assertEqual((self.output / 'partial.gif').read_bytes(), b'interrupted payload')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--real_run':
        verify_real_recovery(Path(sys.argv[2]).resolve())
    else:
        unittest.main()
