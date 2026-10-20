# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Reject optimized local-path replay before identity assertions can disappear.

Uses two historical reports read-only; bad identity fixtures live in temporary dirs.
Runs production _load and CLI main in subprocesses, never renders or starts simulation.
This is a local-path import-chain regression, not coverage of all diagnostic probes.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
DIAGNOSE = REPO / 'rl_exp/tools/diagnose'
REPORTS = (
    REPO / 'rl_exp/out/lizard2_palm_local_path_20261015_v3/report.json',
    REPO / 'rl_exp/out/lizard2_a_contact_delivery_20261019/report.json',
)
MODES = ('normal', '-O', 'PYTHONOPTIMIZE=1', 'PYTHONOPTIMIZE=2')
ERROR = 'local_path_view does not support Python optimization (-O/-OO or PYTHONOPTIMIZE); identity validation requires assertions'

# Rendering must never be reached, including on the unfixed production code.
NO_RENDER = """
import builtins
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.split('.')[0] in ('matplotlib', 'PIL'):
        raise RuntimeError('RENDER_REACHED')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
"""


class LocalPathOptimizationTest(unittest.TestCase):
    def run_child(self, mode, code, *args):
        env = os.environ.copy()
        env.pop('PYTHONOPTIMIZE', None)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        flags = ['-O'] if mode == '-O' else []
        if mode.startswith('PYTHONOPTIMIZE='):
            env['PYTHONOPTIMIZE'] = mode.split('=', 1)[1]
        result = subprocess.run(
            [sys.executable, *flags, '-c', code, *map(str, args)],
            cwd=REPO, env=env, capture_output=True, text=True, timeout=90,
        )
        print(f'{mode}: {args}\nexit={result.returncode}\n{result.stdout}{result.stderr}', flush=True)
        return result

    def assert_rejected(self, result, mode):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('AssertionError: build changed' if mode == 'normal' else ERROR, result.stderr)
        self.assertNotIn('RENDER_REACHED', result.stderr)
        self.assertNotIn('ACCEPTED', result.stdout)

    def test_real_good_reports(self):
        code = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from local_path_view import _load
report, urdf, meshes, root, tracks = _load(Path(sys.argv[2]))
if not urdf or not meshes or not tracks:
    raise RuntimeError('empty real report')
print('ACCEPTED', report['mode'], len(tracks))
"""
        for report in REPORTS:
            for mode in MODES:
                with self.subTest(report=report, mode=mode):
                    result = self.run_child(mode, code, DIAGNOSE, report)
                    if mode == 'normal':
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('ACCEPTED', result.stdout)
                    else:
                        self.assert_rejected(result, mode)

    def test_bad_identity_load_and_cli(self):
        load_code = """
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from local_path_view import _load
with patch.object(Path, 'write_text', side_effect=RuntimeError('WRITE_REACHED')), \\
     patch.object(Path, 'write_bytes', side_effect=RuntimeError('WRITE_REACHED')), \\
     patch.object(Path, 'mkdir', side_effect=RuntimeError('WRITE_REACHED')):
    _load(Path(sys.argv[2]))
print('ACCEPTED bad build identity')
"""
        cli_code = NO_RENDER + """
import runpy
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
script = Path(sys.argv[1]) / (sys.argv[2] + '.py')
sys.argv = [str(script), '--source_report', sys.argv[3], '--output_dir', sys.argv[4]]
if script.stem == 'local_path_contact':
    sys.argv.extend(['--root_report', sys.argv[2]])
with patch.object(Path, 'mkdir', side_effect=RuntimeError('WRITE_REACHED')), \\
     patch.object(Path, 'write_text', side_effect=RuntimeError('WRITE_REACHED')), \\
     patch.object(Path, 'write_bytes', side_effect=RuntimeError('WRITE_REACHED')):
    runpy.run_path(str(script), run_name='__main__')
"""
        with tempfile.TemporaryDirectory(prefix='local_path_optimization_', dir=REPO / 'rl_exp/out') as temporary:
            for index, report in enumerate(REPORTS):
                fixture = Path(temporary) / f'bad-{index}.json'
                data = json.loads(report.read_text(encoding='utf-8'))
                data['identity']['build_report_sha256'] = '0' * 64
                fixture.write_text(json.dumps(data), encoding='utf-8')
                for mode in MODES:
                    with self.subTest(report=report, mode=mode, entry='_load'):
                        self.assert_rejected(self.run_child(mode, load_code, DIAGNOSE, fixture), mode)
                    for module in ('local_path_view', 'local_path_check', 'local_path_contact'):
                        with self.subTest(report=report, mode=mode, entry=module):
                            output = Path(temporary) / f'out-{index}-{mode}-{module}'
                            result = self.run_child(mode, cli_code, DIAGNOSE, module, fixture, output)
                            self.assert_rejected(result, mode)
                            self.assertFalse(output.exists(), f'CLI created output: {output}')

    def test_optimized_import_before_input_or_numpy(self):
        code = """
import builtins
import importlib
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
module = sys.argv[2]
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if module == 'local_path_view' and name.split('.')[0] == 'numpy':
        raise RuntimeError('NUMPY_REACHED')
    return original_import(name, *args, **kwargs)
with patch.object(Path, 'read_text', side_effect=RuntimeError('INPUT_REACHED')), \\
     patch.object(Path, 'read_bytes', side_effect=RuntimeError('INPUT_REACHED')), \\
     patch.object(Path, 'open', side_effect=RuntimeError('INPUT_REACHED')), \\
     patch.object(builtins, 'open', side_effect=RuntimeError('INPUT_REACHED')), \\
     patch.object(builtins, '__import__', guarded_import):
    view = importlib.import_module(module)
    if module == 'local_path_view':
        view._load(Path(sys.argv[3]))
"""
        for mode in MODES[1:]:
            for module in ('local_path_view', 'local_path_check', 'local_path_contact'):
                with self.subTest(mode=mode, module=module):
                    result = self.run_child(mode, code, DIAGNOSE, module, REPORTS[0])
                    self.assert_rejected(result, mode)
                    self.assertNotIn('INPUT_REACHED', result.stderr)
                    self.assertNotIn('NUMPY_REACHED', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
