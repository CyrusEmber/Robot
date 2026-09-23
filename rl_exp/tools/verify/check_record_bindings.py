# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""One home for the record's binding primitives (work/active/record-variant-and-snapshot-specs.md ①, the gate that keeps it one).

``rl_exp/tools/runrecord/manifest.py`` and ``ablation_harness/record.py`` write two files that
describe one run, and before that item's ① gate each of them spelled the shared half itself: two file-hash
implementations (bare hex on one side, ``sha256:`` + hex on the other) and two commit
abbreviations (``[:12]`` here against ``git --short`` there), so one commit read as *two*
strings in the two records of one run and nothing could reconcile them. The primitives live in
``rl_exp/tools/runrecord/binding.py`` now and both records call them; this is the static half
of that, in the shape of ``check_terrain_split_source.py``: a **paste detector**, not a
semantics check, and its ceiling is stated below rather than implied.

Four signatures, read off the syntax tree -- so a comment or docstring may quote the old lines
without tripping it (this file does), while the same text as code cannot hide behind a
``# noqa``:

* **a file digest** -- one scope that hashes *file bytes*: a ``sha256`` call, a binary read
  (``open(..., "rb")`` / ``read_bytes()``) and a ``hexdigest()``. Hashing bytes that were
  *built* -- a canonical JSON, an observation order, a declaration -- is a different fact and
  stays out of reach by construction, which is what lets ``record.digest`` and the golden locks
  keep digesting their own payloads.
* **an abbreviated revision** -- a ``rev-parse`` whose result is truncated in the same
  expression, or a ``rev-parse`` asked for ``--short``.
* **a caller choosing a revision spelling** -- ``git_rev(..., short=<anything but False>)``:
  drift #2 exactly, one layer up from a second implementation.
* **a second spelling of the rsl_rl identity** -- an interpolated string whose literal starts
  ``source:`` or ``installed:``. ``provenance.rsl_rl_id`` spells that identity for the
  framework-combination key a baseline is selected by, and drift #3 was the eval record naming
  the same dependency another way (a distribution version) so the two records of one run could
  not be reconciled; a re-spelled identity is how that comes back.

**One behavioural half, not a signature.** ``binding.git_run`` and ``lifecycle_entry_run._run`` are
the two places where a record's evidence arrives from a child process, and both read it through a
decode. Left to the host locale, a byte the locale cannot decode kills the reader thread, ``stdout``
arrives as ``None``, and the caller still sees success -- measured twice on 2026-09-23
(``acceptance/records/2026-09-23-git-output-encoding.md`` and
``acceptance/records/2026-09-23-utf8-assumption-and-entry-run-decode.md``), and it only shows on a
host without UTF-8 mode (PEP 597). No static rule can decide that, so this gate starts one
interpreter with ``-X utf8=0`` and asserts both shapes -- and reproduces the *old* shape in the same
process as a control, so the assertion cannot pass by measuring nothing on a host that stopped
breaking on those bytes.

**The ceiling, honestly stated** (work/active/record-variant-and-snapshot-specs.md's own warning about paste detectors): this decides
*which side of* a home *a line sits on*, not whether the record it feeds is right. A duplicate
in a shape none of the four signatures reaches -- text decoded and then hashed,
``hashlib.file_digest`` composed from a helper, a revision fetched through another library or an
environment variable, an identity assembled by ``str.join`` or a lookup table -- is invisible
here. The other direction is held where it can be decided: the values are read back by
``test_eval_record.py`` and ``test_run_manifest.py``, so a second *rule* cannot be consumed even
when this scan cannot see it written.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import subprocess
import sys
import warnings

_REPO = pathlib.Path(__file__).resolve().parents[3]
HOME = _REPO / "rl_exp" / "tools" / "runrecord" / "binding.py"
#: The one home of the identity spelling, exempt alongside :data:`HOME`: it is where the recorded
#: spelling is chosen, so the scan can only be pointed at a second one elsewhere.
IDENTITY_HOME = _REPO / "rl_exp" / "tools" / "runrecord" / "provenance.py"
ROOTS = ("rl_exp", "ablation_harness")
#: Prefixes that mean "this is an rsl_rl identity" -- the spelling ``rsl_rl_id`` owns.
IDENTITY_PREFIXES = ("source:", "installed:")


def call_name(node: ast.AST) -> str:
    """Name a call goes by: ``f`` for ``f(...)`` and for ``x.f(...)``."""
    func = getattr(node, "func", None)
    return getattr(func, "id", None) or getattr(func, "attr", None) or ""


def strings(node: ast.AST) -> list[str]:
    """Every string literal anywhere under ``node``."""
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def is_sha256(node: ast.AST) -> bool:
    """A sha256 hashing call, however the stdlib spells it."""
    if not isinstance(node, ast.Call):
        return False
    name = call_name(node)
    if name == "sha256":
        return True
    return name in ("new", "file_digest") and "sha256" in strings(node)


def binary_read(node: ast.AST) -> str | None:
    """How a call reads file *bytes*, or None when it reads nothing / reads text."""
    if not isinstance(node, ast.Call):
        return None
    name = call_name(node)
    if name == "read_bytes":
        return "read_bytes()"
    if name == "open":
        mode = next(
            (a.value for a in node.args[1:] if isinstance(a, ast.Constant) and isinstance(a.value, str)), None
        )
        if isinstance(mode, str) and "b" in mode:
            return f'open(..., "{mode}")'
    return None


def hashes_a_file(scope: ast.AST) -> str | None:
    """The file-digest shape: a sha256 over bytes read from a file, in one scope.

    Scope-wise rather than file-wise on purpose: a payload digest in one function and a text
    read in another must not add up to an alarm, because that pair is not a duplicate of
    anything -- and a real one is always written where its read is.
    """
    reads = [read for node in ast.walk(scope) if (read := binary_read(node))]
    if not reads:
        return None
    sha = next((node for node in ast.walk(scope) if is_sha256(node)), None)
    if sha is None:
        return None
    if not any(isinstance(node, ast.Call) and call_name(node) == "hexdigest" for node in ast.walk(scope)):
        return None
    return f"line {sha.lineno}: a file is hashed to a digest here ({reads[0]})"


def spelling_choice(node: ast.Call) -> str | None:
    """A caller of ``git_rev`` that picks a spelling instead of taking the recorded one."""
    if call_name(node) != "git_rev":
        return None
    for keyword in node.keywords:
        chosen = isinstance(keyword.value, ast.Constant) and keyword.value.value is False
        if keyword.arg == "short" and not chosen:
            return f"git_rev(..., short={ast.unparse(keyword.value)}) asks for another spelling"
    if len(node.args) > 1:
        return "git_rev(<repo>, <length>) asks for another spelling"
    return None


def rev_findings(tree: ast.AST) -> list[str]:
    """Every place a revision gets a second spelling."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Call) and "rev-parse" in strings(node.value):
            found.append(f"line {node.lineno}: a rev-parse result truncated in the same expression")
        if not isinstance(node, ast.Call):
            continue
        if "rev-parse" in strings(node) and "--short" in strings(node):
            found.append(f"line {node.lineno}: rev-parse asked for --short (git's own abbreviation)")
        choice = spelling_choice(node)
        if choice:
            found.append(f"line {node.lineno}: {choice}")
    return found


def identity_spelling(tree: ast.AST) -> list[str]:
    """Every place an rsl_rl identity string is spelled again.

    An f-string is the shape a second spelling takes (``f"source:{rev}"``); a plain literal is
    prose or a docstring example and is left alone, the same split the other signatures make.
    """
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        for part in node.values:
            literal = part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else ""
            if literal.startswith(IDENTITY_PREFIXES):
                found.append(f"line {node.lineno}: an rsl_rl identity is spelled here ({literal!r}...)")
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and call_name(node) == "format"):
            continue
        receiver = getattr(getattr(node, "func", None), "value", None)
        literal = receiver.value if isinstance(receiver, ast.Constant) and isinstance(receiver.value, str) else ""
        if literal.startswith(IDENTITY_PREFIXES):
            found.append(f"line {node.lineno}: an rsl_rl identity is spelled here ({literal!r}...)")
    return found


def module_level(tree: ast.Module) -> ast.Module:
    """The statements that run at import time, as a scope of their own.

    A table of frozen digests is exactly the kind of thing that gets written at module level,
    and it would otherwise sit between two function scopes and be seen by neither.
    """
    body = [node for node in tree.body if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    return ast.Module(body=body, type_ignores=[])


def problems_in(source: str) -> list[str]:
    """Findings for one file's source; a syntax error is a finding, never a pass."""
    try:
        with warnings.catch_warnings():
            # a scanned file's own escape-sequence quirk (a Windows path in a docstring) is not
            # this gate's business, and its parser warning must not land in this gate's output
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except SyntaxError as err:
        return [f"line {err.lineno}: unparseable ({err.msg})"]
    scopes: list[ast.AST] = [module_level(tree)]
    scopes += [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    found = [hit for scope in scopes if (hit := hashes_a_file(scope))]
    return found + rev_findings(tree) + identity_spelling(tree)


#: Fabricated sources: each duplicate the detector exists for, and each neighbour it must leave
#: alone. They are *strings*, so scanning this file finds nothing in them -- the same trick the
#: terrain gate uses, and the reason a green run cannot mean "the matcher fired on my fixtures".
_FIXTURES: list[tuple[str, str, bool]] = [
    (
        "the streaming file digest (the primitive's own old shape, pasted)",
        "def sha256_file(path):\n"
        "    digest = hashlib.sha256()\n"
        "    with open(path, 'rb') as handle:\n"
        "        for block in iter(lambda: handle.read(1 << 20), b''):\n"
        "            digest.update(block)\n"
        "    return digest.hexdigest()\n",
        True,
    ),
    ("a one-shot file digest", "def f(p):\n    return hashlib.sha256(p.read_bytes()).hexdigest()\n", True),
    (
        "the stdlib's file_digest",
        "def f(p):\n    with open(p, 'rb') as fh:\n        return hashlib.file_digest(fh, 'sha256').hexdigest()\n",
        True,
    ),
    (
        "a payload digest is not a file digest",
        "def d(o):\n    return 'sha256:' + hashlib.sha256(json.dumps(o).encode()).hexdigest()\n",
        False,
    ),
    ("a truncated revision", "def rev(root):\n    return git(root, 'rev-parse', 'HEAD')[:12]\n", True),
    (
        "git asked for --short",
        "def f(repo):\n"
        "    return subprocess.run(['git', '-C', str(repo), 'rev-parse', '--short', 'HEAD']).stdout\n",
        True,
    ),
    ("a caller choosing the spelling", "def f(p):\n    return binding.git_rev(p, short=True)\n", True),
    (
        "a full revision that is compared, not abbreviated",
        "def f(root):\n"
        "    sha = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD']).stdout\n"
        "    return sha == PIN\n",
        False,
    ),
    ("locating a work tree is not naming a commit", "def f(root):\n    return git(root, 'rev-parse', '--show-toplevel')\n", False),
    (
        "testing that a revision exists is not naming it either",
        "def f(tree, spec):\n    return bool(git(tree, 'rev-parse', '--verify', spec))\n",
        False,
    ),
    ("a second spelling of the rsl_rl identity", "def f(state):\n    return f\"source:{state.rev}\"\n", True),
    (
        "the same identity, composed by a format call",
        "def f(state):\n    return 'installed:{0}'.format(state.version)\n",
        True,
    ),
    (
        "another prefix is another fact",
        "def f(state):\n    return f\"distribution:{state.version}\"\n",
        False,
    ),
    (
        "a docstring quoting the spelling is prose",
        "def f(state):\n    '''Records 'source:<rev>' as the identity.'''\n    return state.rev\n",
        False,
    ),
]


#: The probe one ``-X utf8=0`` interpreter runs (see the docstring). It is a string rather than a
#: second file so the gate stays one file, and it reports ASCII only: the child's stdout is a
#: locale-encoded pipe, which is the subject. The interpreter it starts is named through ``PY`` so
#: this gate's spawn count is the one spawn *this file* makes -- the probe's text is data, not a call.
_DECODE_PROBE = "\n".join([
    "import pathlib, subprocess, sys, tempfile",
    "sys.path.insert(0, sys.argv[1])",
    "PY = sys.executable",
    "from rl_exp.tools.runrecord import binding",
    "from rl_exp.tools.verify import lifecycle_entry_run",
    "SUBJECT = 'twin probes \\U0001F98E attach'",
    "control = subprocess.run([PY, '-X', 'utf8=1', '-c', 'print(%r)' % SUBJECT],",
    "                         capture_output=True, text=True)",
    "print('control_stdout_is_none', control.stdout is None)",
    "with tempfile.TemporaryDirectory() as tmp:",
    "    root = pathlib.Path(tmp)",
    "    try:",
    "        binding.git_run(root, 'init', '-q')",
    "        (root / 'a.txt').write_text('x', encoding='utf-8')",
    "        binding.git_run(root, 'add', 'a.txt')",
    "        binding.git_run(root, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', SUBJECT)",
    "        subject = binding.git_run(root, 'log', '-1', '--pretty=%s')",
    "    except Exception as err:  # the crash is the failure mode: stdout arrived as None",
    "        subject = 'raised %s' % type(err).__name__",
    "    print('git_run_recovered', subject == SUBJECT)",
    "said = \"[run-manifest] \\u8bad\\u7ec3\\u542f\\u52a8\\uff1a\\u4e2d\\u6587\\u65e5\\u5fd7\"",
    "run = lifecycle_entry_run._run([PY, '-X', 'utf8=1', '-c', 'print(%r)' % said],",
    "                               cwd=pathlib.Path.cwd(),",
    "                               environment=lifecycle_entry_run._environment())",
    "print('entry_stdout_is_none', run.stdout is None)",
    "print('entry_stdout_recovered', said in (run.stdout or ''))",
])


def decode_probe() -> list[str]:
    """Start one non-UTF-8-mode interpreter and read what it says about the two decode shapes.

    Empty means both call sites handed their child's text on, **and** the control confirms that this
    host can still exhibit the failure being guarded against.
    """
    proc = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", _DECODE_PROBE, str(_REPO)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    said = dict(line.split(maxsplit=1) for line in proc.stdout.splitlines() if " " in line)
    if proc.returncode != 0:
        # A probe that crashed and a reading that came back missing look the same from here, so say
        # which it was: the crash is the probe's bug, the missing reading is the decode's.
        return [
            f"the decode probe itself failed (rc={proc.returncode}): "
            f"{(proc.stdout.strip() or proc.stderr.strip())[-300:]!r}"
        ]
    if said.get("control_stdout_is_none") != "True":
        return [
            "the unpinned decode no longer breaks on this host: this assertion has stopped measuring"
            f" anything (rc={proc.returncode}, said={proc.stdout.strip()[-200:]!r})"
        ]
    problems = []
    if said.get("git_run_recovered") != "True":
        problems.append("binding.git_run lost the non-ASCII git output off UTF-8 mode")
    if said.get("entry_stdout_is_none") != "False" or said.get("entry_stdout_recovered") != "True":
        problems.append("lifecycle_entry_run._run lost the child's non-ASCII output off UTF-8 mode")
    return problems


def self_test() -> list[str]:
    """The detector must fire on each duplicate it exists for and stay quiet on its neighbours."""
    problems: list[str] = []
    for label, source, expected in _FIXTURES:
        found = problems_in(source)
        if bool(found) != expected:
            problems.append(f"{label}: expected {'a finding' if expected else 'no finding'}, got {found}")
    return problems


def scan(roots: list[pathlib.Path], homes: tuple[pathlib.Path, ...]) -> tuple[int, list[tuple[str, list[str]]]]:
    """Findings per file under ``roots``, plus how many files were read."""
    scanned = 0
    findings: list[tuple[str, list[str]]] = []
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in files:
            if path.suffix != ".py" or any(path.resolve() == home.resolve() for home in homes):
                continue
            scanned += 1
            hits = problems_in(path.read_text(encoding="utf-8", errors="replace"))
            if hits:
                try:
                    label = path.resolve().relative_to(_REPO).as_posix()
                except ValueError:  # a scratch tree outside the repo (the falsification run)
                    label = str(path)
                findings.append((label, hits))
    return scanned, findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        action="append",
        default=None,
        help="scan this path instead of the repo roots (repeatable; for the falsification run)",
    )
    parser.add_argument("--home", default=None, help="exempt this file instead of the repo's two homes")
    args = parser.parse_args(argv)

    roots = [pathlib.Path(root) for root in args.root] if args.root else [_REPO / root for root in ROOTS]
    homes = (pathlib.Path(args.home),) if args.home else (HOME, IDENTITY_HOME)

    self_test_problems = self_test()
    decode_problems = decode_probe()
    scanned, findings = scan(roots, homes)
    for problem in self_test_problems:
        print(f"  self-test: {problem}")
    for problem in decode_problems:
        print(f"  decode: {problem}")
    for path, hits in findings:
        for hit in hits:
            print(f"  {path}: {hit}")
    if self_test_problems or decode_problems or findings:
        print(
            f"RECORD_BINDING_SINGLE_SOURCE_VIOLATED ({len(self_test_problems)} self-test, "
            f"{len(decode_problems)} decode, "
            f"{len(findings)} file(s)): the file digest, the revision spelling, the rsl_rl "
            f"identity belong in {', '.join(str(home) for home in homes)}, and the child's output is "
            f"decoded rather than left to the host locale"
        )
        return 1
    print(f"record binding primitives: one home ({', '.join(str(home) for home in homes)}), {scanned} file(s) clean")
    print("record binding decode: one -X utf8=0 interpreter, both shapes recovered, control still red")
    print("RECORD_BINDING_SINGLE_SOURCE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
