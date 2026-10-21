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

import json
from pathlib import Path
import shutil
import stat
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

    def save(self):
        self.index.write_text(json.dumps(self.doc), encoding='utf-8')

    def deny_old(self, path, *args, **kwargs):
        if any(path.resolve().is_relative_to(p.resolve()) for p in (CONTACT, CHECKPOINT)):
            raise AssertionError(f'OLD_EVIDENCE_READ: {path}')
        return self.old_open(path, *args, **kwargs)

    def test_actual_local_path_reader_without_original_roots(self):
        with patch.object(view, 'ArtifactPaths', lambda: self.paths, create=True), \
                patch.object(Path, 'open', lambda p, *a, **kw: self.deny_old(p, *a, **kw)):
            report, _, meshes, _, tracks = view._load(CONTACT / 'report.json')
        self.assertEqual(report['mode'], 'budgeted_local_path')
        self.assertTrue(meshes)
        self.assertTrue(all(stats['completed_local_loop'] for stats, _ in tracks.values()))

    def test_runtime_authorization_and_bytes_at_new_location(self):
        with patch.object(runtime, 'ArtifactPaths', lambda: self.paths, create=True), \
                patch.object(Path, 'open', lambda p, *a, **kw: self.deny_old(p, *a, **kw)):
            original = runtime.check_build(runtime.BUILD)
            relocated = runtime.check_build(self.paths.resolve(runtime.BUILD))
        self.assertEqual(original, relocated)
        self.assertEqual(original['candidate_sha256'], runtime.URDF_HASH)
        with patch.object(runtime, 'ArtifactPaths', lambda: self.paths, create=True):
            with self.assertRaisesRegex(ValueError, 'authorized'):
                runtime.check_build(self.root / 'forged/build.json')

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
                patch.object(Path, 'open', lambda p, *a, **kw: self.deny_old(p, *a, **kw)):
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
                    patch.object(Path, 'open', lambda p, *a, **kw: self.deny_old(p, *a, **kw)):
                self.assertTrue(view._load(CONTACT / 'report.json')[-1])
                self.assertEqual(runtime.check_build(runtime.BUILD)['candidate_sha256'], runtime.URDF_HASH)


if __name__ == '__main__':
    unittest.main()
