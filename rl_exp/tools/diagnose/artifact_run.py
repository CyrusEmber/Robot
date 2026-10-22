# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Own one diagnostic run and register it in the existing artifact index.

run.json is written before producer artifacts. Only a registered, completed run
whose input/code/output hashes still match passes --inspect_run. A killed writer,
failed registration, or failed terminal write remains incomplete; inspection never
deletes or repairs evidence. Hashes detect file changes, not an immutable execution
snapshot. The index is a location pointer; run.json owns status and retention.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile

from artifact_paths import ArtifactPaths, _relative, _unlinked, sha256_file


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write(path, doc, scratch):
    descriptor, name = tempfile.mkstemp(prefix='.artifact-', suffix='.tmp', dir=scratch)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(doc, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _index_lock(root):
    # Persistent inode, OS-released lock: no stale-lock deletion or unlink race.
    lock = root / 'rl_exp/out/.artifact_index.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _check_bindings(rows, root):
    for row in rows:
        location = Path(row['location'])
        location = location if location.is_absolute() else _unlinked(root, _relative(row['location']))
        if not row['sha256'] or sha256_file(location) != row['sha256']:
            raise ValueError(f'run binding changed or unreadable: {location}')


def _validate_metadata(metadata, required):
    """Apply the same ownership and binding invariants at creation and inspection."""
    for key in ('topic', 'work_id', 'owner', 'retention_reason'):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f'missing run metadata: {key}')
    command = metadata.get('command')
    if (not isinstance(command, list) or not command or any(not isinstance(a, str) for a in command)
            or not command[0].strip()):
        raise ValueError('invalid run metadata: command')
    for key in ('inputs', 'code'):
        rows = metadata.get(key)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f'missing run metadata: {key}')
        for row in rows:
            if (not isinstance(row, dict)
                    or any(not isinstance(row.get(field), str) or not row[field].strip()
                           for field in ('identity', 'location', 'sha256'))
                    or re.fullmatch('[0-9a-f]{64}', row['sha256']) is None):
                raise ValueError(f'invalid run binding: {key}')
    if (not isinstance(required, list) or not required or any(not isinstance(n, str) for n in required)
            or len(set(required)) != len(required)):
        raise ValueError('invalid run required_outputs')
    for name in required:
        _relative(name)
        if name == 'run.json':
            raise ValueError('run.json cannot bind itself as an output')


def _inventory(output):
    inventory = {}
    for path in sorted(output.rglob('*')):
        _unlinked(output, path.relative_to(output))
        if path.is_file() and path != output / 'run.json':
            digest = sha256_file(path)
            if not digest:
                raise ValueError(f'unreadable run output: {path}')
            inventory[path.relative_to(output).as_posix()] = digest
    return inventory


class ArtifactRun:
    """Context for exclusive creation, registration, and terminal accounting."""

    def __init__(self, output: Path, paths: ArtifactPaths, metadata: dict, required: list[str]) -> None:
        self.output, self.paths = output, paths
        relative = output.relative_to(paths.root).as_posix()
        _unlinked(paths.root, _relative(relative))
        roots = (paths.root / 'rl_exp/out', paths.root / 'rl_exp/tools/diagnose/out')
        if not any(output != root and output.is_relative_to(root) for root in roots):
            raise ValueError('diagnostic run must be under a diagnostic output root')
        _validate_metadata(metadata, required)
        self.relative = relative
        self.record = {'format': 1, **metadata, 'state': 'registering', 'created_utc': _now(),
                       'required_outputs': required, 'outputs': {},
                       'retention': {'decision': 'retain_incomplete', 'reason': 'creation unfinished'},
                       'next': 'Owner must inspect the retained scene and rerun into a fresh directory.'}

    def _save(self):
        _write(self.output / 'run.json', self.record, self.output)

    def _inventory(self):
        return _inventory(self.output)

    def _fail(self, error):
        self.record.update(state='failed', ended_utc=_now(),
                           error={'type': type(error).__name__, 'message': str(error)}, outputs=self._inventory(),
                           next='Owner must inspect the retained scene and rerun into a fresh directory.')
        self.record['retention'] = {'decision': 'retain_failure', 'reason': 'incomplete producer; preserve scene'}
        self._save()

    def __enter__(self):
        _check_bindings(self.record['inputs'] + self.record['code'], self.paths.root)
        self.output.mkdir(parents=True, exist_ok=False)
        try:
            self._save()
            with _index_lock(self.paths.root):
                original = self.paths.index.read_bytes()
                doc = json.loads(original)
                if doc.get('format') != 1 or not isinstance(doc.get('packages'), list):
                    raise ValueError('invalid diagnostic index')
                if any(e.get('current_location') == self.relative or e.get('logical_root') == self.relative
                       for e in doc['packages']):
                    raise ValueError('run already registered; use a fresh run name')
                doc['packages'].append({'logical_root': self.relative, 'current_location': self.relative,
                                        'run_record': self.relative + '/run.json',
                                        'classification': 'producer_run', 'owner': self.record['work_id'],
                                        'writer_status': 'see_run_manifest', 'storage': 'local_single_copy_no_backup'})
                if self.paths.index.read_bytes() != original:
                    raise ValueError('index changed during registration')
                _write(self.paths.index, doc, self.output)
            self.record['state'] = 'running'
            self._save()
        except BaseException as error:
            self._fail(error)
            raise
        return self

    def __exit__(self, kind, error, traceback):
        if error is not None:
            self._fail(error)
            return False
        try:
            _check_bindings(self.record['inputs'] + self.record['code'], self.paths.root)
            outputs = self._inventory()
            if any(not outputs.get(name) for name in self.record['required_outputs']):
                raise ValueError('producer omitted required output')
            self.record.update(state='completed', ended_utc=_now(), outputs=outputs, next=None)
            self.record['retention'] = {'decision': 'retain', 'reason': self.record['retention_reason']}
            self._save()
        except BaseException as failure:
            self._fail(failure)
            raise
        return False


def inspect_run(output: Path, paths: ArtifactPaths) -> dict:
    """Check completion, registration, and all recorded bytes without mutations."""
    _unlinked(paths.root, output.relative_to(paths.root))
    record = json.loads((output / 'run.json').read_text(encoding='utf-8'))
    if record.get('format') != 1 or record.get('state') != 'completed':
        raise ValueError(f'incomplete run: {record.get("state", "missing state")}')
    _validate_metadata(record, record.get('required_outputs'))
    relative = output.relative_to(paths.root).as_posix()
    doc = json.loads(paths.index.read_text(encoding='utf-8'))
    matches = [e for e in doc['packages'] if e.get('current_location') == relative
               and e.get('run_record') == relative + '/run.json']
    if len(matches) != 1:
        raise ValueError('completed record has no unique index registration')
    _check_bindings(record['inputs'] + record['code'], paths.root)
    actual = _inventory(output)
    if actual != record['outputs'] or any(not actual.get(n) for n in record['required_outputs']):
        raise ValueError('run output inventory changed')
    return {'state': 'completed', 'owner': record['owner'], 'topic': record['topic'],
            'retention': record['retention'], 'output_count': len(actual)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect_run', type=Path, required=True)
    parser.add_argument('--storage_root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--index', type=Path)
    args = parser.parse_args()
    try:
        result = inspect_run(args.inspect_run.resolve(), ArtifactPaths(args.index, args.storage_root))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'INCOMPLETE_RUN: {error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
