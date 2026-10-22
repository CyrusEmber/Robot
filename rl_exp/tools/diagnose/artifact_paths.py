# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Locate relocated diagnostic bytes without rewriting historical identities.

Uses artifact_index.json's existing package routes. Only entries with relocation
metadata participate: original_absolute_root records the old identity; files maps
relative names to SHA256. current_location is relative to storage_root. Mapped
files MUST exist at the new location and match their stored digest; an old copy
is never a fallback. Unmapped paths retain their existing meaning. This is a
trusted local routing file, not permission to accept new asset identities.
Repository identity comparisons recognize only the current storage root and old
repository roots derivable from exact logical-root suffixes in those routes.
They compare the complete relative path, never a basename or unbound suffix.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import stat
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'rl_exp/tools/runrecord'))
from binding import sha256_file  # noqa: E402


def _relative(value: str) -> Path:
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError(f'unsafe artifact relative path: {value!r}')
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f'absolute artifact destination: {value!r}')
    return path


def _unlinked(root: Path, relative: Path) -> Path:
    path = root
    for part in relative.parts:
        path = path / part
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError(f'artifact link/reparse point: {path}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'artifact path escape: {path}')
    return path


class ArtifactPaths:
    """Resolve one caller-selected storage root and its trusted relocation index."""

    def __init__(self, index: Path | None = None, storage_root: Path = REPO) -> None:
        self.root = storage_root.resolve()
        self.index = (index if index is not None else self.root / 'rl_exp/tools/diagnose/artifact_index.json').resolve()
        doc = json.loads(self.index.read_text(encoding='utf-8'))
        if doc.get('format') != 1 or not isinstance(doc.get('packages'), list):
            raise ValueError('expected diagnostic artifact index format 1')
        self.routes = []
        self.repository_roots = {self.root}
        for entry in doc['packages']:
            if 'relocation' not in entry:
                continue
            location = entry['relocation']
            logical = _relative(entry['logical_root'])
            original = Path(location['original_absolute_root'])
            if not original.is_absolute():
                raise ValueError('artifact original identity must be absolute')
            original = original.absolute()
            if Path(*original.parts[-len(logical.parts):]) == logical:
                self.repository_roots.add(original.parents[len(logical.parts) - 1].resolve())
            current = _unlinked(self.root, _relative(entry['current_location']))
            files = location['files']
            if not isinstance(files, dict) or not files:
                raise ValueError('relocation requires an exact file manifest')
            for name, digest in files.items():
                _relative(name)
                if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                    raise ValueError(f'invalid relocation digest: {name}')
            aliases = {original, self.root / logical, current}
            previous_locations = location.get('original_absolute_locations', [])
            if not isinstance(previous_locations, list):
                raise ValueError('artifact previous locations must be an explicit list')
            for previous in previous_locations:
                if not isinstance(previous, str) or not Path(previous).is_absolute():
                    raise ValueError('artifact previous location must be absolute')
                aliases.add(Path(previous).absolute())
            if any(a != b and a.is_relative_to(b) for a in aliases for b in aliases):
                raise ValueError('overlapping aliases within artifact relocation root')
            for previous, _, _ in self.routes:
                if any(a == b or a.is_relative_to(b) or b.is_relative_to(a)
                       for a in aliases for b in previous):
                    raise ValueError('overlapping artifact relocation roots')
            self.routes.append((aliases, current, (original, files)))

    def logical(self, path: Path) -> Path:
        """Recover the original identity for authorization checks, without reading."""
        path = path.absolute() if path.is_absolute() else self.root / path
        for aliases, _, (original, _) in self.routes:
            for alias in aliases:
                if path.is_relative_to(alias):
                    return original / path.relative_to(alias)
        return path

    def _identity_key(self, path: Path) -> tuple[str, Path]:
        path = self.logical(Path(path)).resolve()
        # A restored checkout may itself sit inside an old repository. Its exact
        # root is the more specific namespace; do not strip an arbitrary suffix.
        for root in sorted(self.repository_roots, key=lambda p: len(p.parts), reverse=True):
            if path.is_relative_to(root):
                return 'repository', path.relative_to(root)
        return 'absolute', path

    def same_identity(self, first: Path, second: Path) -> bool:
        """Compare full logical identities across explicitly known repository roots."""
        return self._identity_key(first) == self._identity_key(second)

    def describe(self, path: Path, expected: str | None = None) -> dict:
        """Bind identity and current storage separately, with a nonempty digest."""
        location = self.resolve(path, expected).resolve()
        digest = sha256_file(location)
        if not digest:
            raise ValueError(f'unreadable artifact: {location}')
        key_type, key = self._identity_key(Path(path))
        return {'identity': str(self.logical(Path(path))),
                'logical_path': key.as_posix() if key_type == 'repository' else None,
                'location': location.relative_to(self.root).as_posix()
                if location.is_relative_to(self.root) else str(location), 'sha256': digest}

    def resolve(self, path: Path, expected: str | None = None) -> Path:
        """Return a verified relocated file; missing/corrupt mappings fail closed."""
        path = Path(path)
        path = path.absolute() if path.is_absolute() else self.root / path
        for aliases, current, (_, files) in self.routes:
            for alias in aliases:
                if not path.is_relative_to(alias):
                    continue
                relative = path.relative_to(alias)
                recorded = files.get(relative.as_posix())
                if recorded is None or (expected is not None and recorded != expected):
                    raise ValueError(f'unbound artifact file or identity mismatch: {path}')
                target = _unlinked(self.root, current.relative_to(self.root) / relative)
                if not target.is_file() or sha256_file(target) != recorded:
                    raise ValueError(f'relocated artifact missing or digest mismatch: {target}')
                return target
        if expected is not None and sha256_file(path) != expected:
            raise ValueError(f'artifact digest mismatch: {path}')
        return path


def artifact_path(path: Path, expected: str | None = None) -> Path:
    """Resolve using the repository's current routes; no cached stale mapping."""
    return ArtifactPaths().resolve(path, expected)
