# -*- coding: utf-8 -*-
"""Offline checks for ``ablation_harness/record.py`` helpers and ``eval.py`` exit status."""

import ast
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "ablation_harness"))

import record  # noqa: E402


def test_digest_canonical_deterministic() -> None:
    """Equivalent dicts with different key orders hash identically."""
    first = record.digest({"b": 2, "a": 1})
    second = record.digest({"a": 1, "b": 2})
    assert first.startswith("sha256:") and first == second
    assert first != record.digest({"a": 1, "b": 3})


def test_checkpoint_digest_follows_the_file() -> None:
    """The digest helper reads the real bytes: a rewritten file changes it, a missing one is None."""
    with tempfile.TemporaryDirectory() as scratch:
        path = pathlib.Path(scratch) / "model.pt"
        path.write_bytes(b"first")
        first = record.checkpoint_digest(path)
        assert first["sha256"] and first["size"] == 5, f"a readable file must hash: {first}"
        path.write_bytes(b"second")
        assert record.checkpoint_digest(path)["sha256"] != first["sha256"], \
            "different bytes must hash differently"
        assert record.checkpoint_digest(pathlib.Path(scratch) / "absent.pt")["sha256"] is None, \
            "an unreadable checkpoint is None, never a fabricated digest"


def test_record_module_cannot_consume_the_random_stream() -> None:
    """The record helper module imports no framework and no RNG."""
    source = (_REPO / "ablation_harness" / "record.py").read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    banned = {"torch", "numpy", "random"}
    assert not (imported & banned), f"record.py must not import {sorted(imported & banned)}"
    for name in sorted(banned):
        assert not hasattr(record, name), f"the record module exposes {name}"
    probe = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path[:0] = [{str(_REPO)!r}, {str(_REPO / 'ablation_harness')!r}]; "
         "import record; assert 'torch' not in sys.modules and 'numpy' not in sys.modules"],
        capture_output=True, text=True, errors="replace",
    )
    assert probe.returncode == 0, f"importing the record module pulled in torch/numpy: {probe.stderr}"
    for token in ("np.random", "torch.rand", "random."):
        assert token not in source, f"record.py must not reach for {token}"


def _eval_exit_probe(entry: pathlib.Path) -> None:
    """Run the real parser and post-launch import; simulate Kit and main in a child."""
    script = r'''
import atexit, builtins, importlib.util, io, os, pathlib, runpy, sys, types
mode, entry, marker, ckpt, exp = sys.argv[1:]
app_module = types.ModuleType('isaaclab.app')
class AppLauncher:
    @staticmethod
    def add_app_launcher_args(parser): pass
    def __init__(self, args):
        self.app = self
        self.device = 'cpu'
        atexit.register(lambda: os._exit(0))
    def close(self):
        if mode == 'close_error': raise RuntimeError('injected close failure')
        pathlib.Path(marker).touch()
        os._exit(0)
app_module.AppLauncher = AppLauncher
sys.modules['isaaclab'] = types.ModuleType('isaaclab')
sys.modules['isaaclab.app'] = app_module
original_find_spec = importlib.util.find_spec
importlib.util.find_spec = lambda name, package=None: object() if name == 'isaacsim' else original_find_spec(name, package)
original_import = builtins.__import__
def injected_import(name, *args, **kwargs):
    if name == 'torch': raise RuntimeError('injected import failure')
    return original_import(name, *args, **kwargs)
builtins.__import__ = injected_import
sys.argv = [entry] + (['--help'] if mode == 'help' else [] if mode == 'parser_error' else ['--ckpt', ckpt, '--exp', exp])
original_run_path = runpy.run_path
if mode not in ('import', 'help', 'parser_error'):
    def fake_runner(path, run_name):
        def main():
            if mode == 'error': raise RuntimeError('injected main failure')
            if mode == 'system_exit': raise SystemExit('injected main refusal')
            if mode == 'broken_stdout':
                class BrokenStdout(io.StringIO):
                    def flush(self): raise OSError('stdout flush failed')
                sys.stdout = BrokenStdout()
                raise RuntimeError('injected flush failure')
        return {'main': main, 'simulation_app': AppLauncher(None)}
    runpy.run_path = fake_runner
original_run_path(entry, run_name='__main__')
'''
    cases = (('import', 1, 'injected import failure'), ('parser_error', 1, '--checkpoint'),
             ('help', 0, 'usage:'), ('error', 1, 'injected main failure'),
             ('system_exit', 1, 'injected main refusal'), ('broken_stdout', 1, 'injected flush failure'),
             ('close_error', 1, 'injected close failure'), ('success', 0, ''))
    with tempfile.TemporaryDirectory() as scratch:
        ckpt = pathlib.Path(scratch) / 'model_0.pt'
        exp = pathlib.Path(scratch) / 'exp.py'
        ckpt.write_bytes(b'ckpt')
        exp.write_text('# stub\n', encoding='utf-8')
        for mode, expected, message in cases:
            marker = pathlib.Path(scratch) / mode
            result = subprocess.run([sys.executable, '-c', script, mode, str(entry), str(marker), str(ckpt), str(exp)],
                                    cwd=scratch, capture_output=True, text=True, encoding='utf-8', errors='replace')
            assert result.returncode == expected, (mode, result.returncode, result.stderr)
            assert message in (result.stdout if mode == 'help' else result.stderr), (mode, result.stderr)
            assert marker.exists() == (mode == 'success'), mode
            if expected == 1:
                assert 'Traceback' in result.stderr, (mode, result.stderr)


def test_eval_failure_exit_status() -> None:
    _eval_exit_probe(_REPO / 'ablation_harness' / 'eval.py')


def _main() -> None:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"[OK] {fn.__name__}")
    assert "torch" not in sys.modules and "numpy" not in sys.modules, \
        "the checks in this file must stay framework-free"
    print(f"test_eval_record: {len(tests)} passed")


if __name__ == "__main__":
    _main()
