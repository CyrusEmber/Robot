# -*- coding: utf-8 -*-
"""Terrain-split probe: watch a real generator, snapshot at call time (ARCH_PLAN Step 3.3c).

The generator computes its column split in a local variable and drops it, so the honest way
to learn what it did is to watch it do it. This wraps **both** call points of
``TerrainGenerator`` -- no upstream edit -- and snapshots at call time, because the facts a
record needs are not all at one of them:

* the **actual difficulty** exists only inside ``_get_terrain_mesh``: the callers pass the raw
  sub-terrain cfg, and the curriculum generator adds its per-cell jitter internally. It also
  does ``cfg = cfg.copy()`` before writing ``cfg.difficulty``, so the object the caller holds
  never carries the value.
* the **(row, col)** of a cell exists only as arguments of ``_add_sub_terrain``.

Pairing is per generator instance and is verified, not assumed: every ``_add_sub_terrain``
must consume exactly one preceding ``_get_terrain_mesh`` for the **same cfg object**, and a
``get`` left without its ``add`` is an anomaly too. Anomalies go into the record and refuse
consumption -- the probe never re-derives a difficulty from the row index or the loop order
(re-deriving would also consume the same RNG stream).

Snapshots hold **no object references** (name, parameter digest, difficulty, indices only), so
installing the probe cannot keep a terrain or its cfgs alive. Dispatch is by the generator
cfg's identity, which is how the curriculum finds its record without touching the generator.
"""

from __future__ import annotations

import builtins
import hashlib
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tasks import terrain_map  # noqa: E402
from rl_exp.tasks.terrain_geometry import foot_relief, geometry_digest  # noqa: E402

#: cfg identity -> record. Keyed by the object the generator was built with, which is the
#: same object the curriculum can reach at ``env.scene.terrain.cfg.terrain_generator``.
_RECORDS: dict[int, dict] = {}
#: cfg identity -> gets that have not been paired with an add yet, as (cfg id, difficulty, digest)
_PENDING: dict[int, list[tuple[int, float, str]]] = {}
_INSTALLED = False
#: The module holding the class under watch. Importing it is *not* free: it pulls
#: ``isaaclab.terrains.utils`` -> ``from pxr import UsdGeom`` (pip usd-core), which must not
#: reach ``sys.modules`` before Kit starts (P001/P003) -- see :func:`_patch_when_imported`.
_GENERATOR_MODULE = "isaaclab.terrains.terrain_generator"
_PATCHED = False
#: Is the generator module being waited for (see :func:`_patch_when_imported`)?
_WATCHING = False
#: At most this many records are kept. A process builds one env (one cfg) at a time and the
#: consumer reads the record right after, so the cap only ever evicts a cfg that is long gone --
#: without it, a sweep that builds envs in one process grows this table without bound. Ceiling:
#: an env whose cfg is evicted before its curriculum reads it would be refused, not misled; raise
#: the cap if a future caller really does keep many live terrains at once.
_MAX_RECORDS = 8


def _watched(cfg) -> bool:
    """Is this generator cfg one whose split is a column mapping?

    Curriculum mode assigns one sub-terrain per column; the random mode samples per cell and
    has no column mapping to declare (ARCH_PLAN Step 3.3, "模式区分"), so watching it would
    only manufacture a claim it does not make.
    """
    return bool(getattr(cfg, "curriculum", False))


def _name_of(cfg, sub_cfg) -> str | None:
    """Name of the sub-terrain cfg inside the generator cfg, or None when it is not one of them."""
    for name, candidate in cfg.sub_terrains.items():
        if candidate is sub_cfg:
            return name
    return None


def _record_for_cfg(cfg) -> dict:
    key = id(cfg)
    record = _RECORDS.get(key)
    if record is None:
        record = terrain_map.new_record(cfg, key)
        _RECORDS[key] = record
        while len(_RECORDS) > _MAX_RECORDS:  # insertion order: the oldest cfg goes first
            _RECORDS.pop(next(iter(_RECORDS)))
    return record


def release(terrain) -> None:
    """Forget the record of one terrain (its generation is done and has been consumed).

    Optional: the table is capped anyway. Call it from a long-lived loop that keeps building
    envs so the *whole* record (not just its slot) goes away with the env.
    """
    cfg = getattr(getattr(terrain, "cfg", None), "terrain_generator", None)
    if cfg is not None:
        _RECORDS.pop(id(cfg), None)
        _PENDING.pop(id(cfg), None)


def _announce(cfg) -> None:
    """Record and print one line per generation: the ground a real run actually stood on.

    The per-cell digests are captured where the generator hands the mesh over, so this is the
    geometry that was built, not a rebuild of it (work/active/verified-rebuild-rating.md ⑤b). One line goes to the run's
    log -- the digests are small, the meshes are not, so the log carries the identity and not
    the material.
    """
    record = _RECORDS.get(id(cfg))
    if record is None or not record["cells"]:
        return
    cells = sorted(record["cells"], key=lambda cell: (cell["row"], cell["col"]))
    lines = [f"{cell['row']},{cell['col']}:{cell.get('geometry') or 'none'}" for cell in cells]
    combined = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    record["geometry_digest"] = "sha256:" + combined
    bumpy = max((cell for cell in cells if cell.get("relief") is not None),
                key=lambda cell: cell["relief"], default=None)
    relief_max = f"{bumpy['relief']:.4f}@{bumpy['sub_terrain']}" if bumpy else "none"
    unmeasurable = sum(1 for cell in cells if cell.get("relief") is None)
    print(f"[TERRAIN_GEOMETRY] cells={len(cells)} hashed={sum(1 for c in cells if c.get('geometry'))} "
          f"anomalies={len(record['anomalies'])} "
          f"relief_max={relief_max} relief_unmeasurable={unmeasurable} digest=sha256:{combined[:32]}",
          flush=True)


def _patch() -> None:
    """Wrap the generator's four call points once (idempotent); the module must be imported.

    The class is taken from ``sys.modules`` rather than imported here, because every caller
    either already imported it or is running from inside that import (see
    :func:`_patch_when_imported`).
    """
    global _PATCHED
    if _PATCHED:
        return
    TerrainGenerator = sys.modules[_GENERATOR_MODULE].TerrainGenerator

    original_get = TerrainGenerator._get_terrain_mesh
    original_add = TerrainGenerator._add_sub_terrain
    original_curriculum = TerrainGenerator._generate_curriculum_terrains
    original_random = TerrainGenerator._generate_random_terrains

    def _start_generation(cfg) -> None:
        """A generation begins here: drop whatever the previous one left for this cfg."""
        _RECORDS.pop(id(cfg), None)
        _PENDING.pop(id(cfg), None)

    def generate_curriculum(self):
        _start_generation(self.cfg)
        result = original_curriculum(self)
        _announce(self.cfg)
        return result

    def generate_random(self):
        _start_generation(self.cfg)
        result = original_random(self)
        _announce(self.cfg)
        return result

    def get_terrain_mesh(self, difficulty, cfg):
        if _watched(self.cfg):
            record = _record_for_cfg(self.cfg)
            name = _name_of(self.cfg, cfg)
            if name is None:
                record["anomalies"].append(
                    f"_get_terrain_mesh on a sub-terrain cfg that is not part of the generator cfg: {cfg!r}"
                )
            else:
                _PENDING.setdefault(id(self.cfg), []).append(
                    (id(cfg), float(difficulty), terrain_map.digest(cfg.to_dict()))
                )
        return original_get(self, difficulty, cfg)

    def add_sub_terrain(self, mesh, origin, row, col, sub_terrain_cfg):
        if _watched(self.cfg):
            key = id(self.cfg)
            record = _record_for_cfg(self.cfg)
            pending = _PENDING.setdefault(key, [])
            index, reason = terrain_map.pair(pending, id(sub_terrain_cfg))
            if index is None:
                record["anomalies"].append(f"cell ({row}, {col}): {reason}")
            else:
                _, difficulty, params = pending.pop(index)
                try:
                    geometry = geometry_digest(mesh, origin)
                    relief = foot_relief(mesh)
                except AttributeError as err:  # a shape this digest does not know: say so, do not guess
                    geometry, relief = None, None
                    record["anomalies"].append(f"cell ({row}, {col}): geometry is not hashable ({err})")
                record["cells"].append({
                    "row": int(row),
                    "col": int(col),
                    "sub_terrain": _name_of(self.cfg, sub_terrain_cfg),
                    "difficulty": difficulty,
                    "params": params,
                    "geometry": geometry,
                    "relief": relief,
                })
        return original_add(self, mesh, origin, row, col, sub_terrain_cfg)

    TerrainGenerator._get_terrain_mesh = get_terrain_mesh
    TerrainGenerator._add_sub_terrain = add_sub_terrain
    TerrainGenerator._generate_curriculum_terrains = generate_curriculum
    TerrainGenerator._generate_random_terrains = generate_random
    _PATCHED = True


def _generator_class():
    """The watched class, or ``None`` while the module is still being imported.

    A module sits in ``sys.modules`` before its body finishes, so presence is not readiness --
    patching a half-executed module raises ``AttributeError``.
    """
    return getattr(sys.modules.get(_GENERATOR_MODULE), "TerrainGenerator", None)


def _patch_when_imported() -> None:
    """Apply :func:`_patch` the first time the generator module lands in ``sys.modules``.

    ``install()`` is called from an env cfg's ``__post_init__`` -- during hydra compose, **before**
    Kit has finished starting -- and importing ``TerrainGenerator`` there pulls
    ``isaaclab.terrains.utils`` -> ``from pxr import UsdGeom`` (pip usd-core) into ``sys.modules``,
    which is what kills Kit at boot (P001/P003). The framework imports that module when it builds
    the terrain, after Kit is up, and the patch only has to be in place by then, so the import is
    waited for here instead of forced early.

    The wait is spent on ``builtins.__import__``, which every python-level import goes through. A
    ``sys.meta_path`` finder cannot be used for it: the machinery stops at the first finder that
    answers, Kit keeps one of its own ahead of anything we insert, and the module then arrives
    without our hook ever being asked -- measured 2026-09-18, the patch never landed and every
    param-grid trainer run refused with "the probe was not installed".
    """
    global _WATCHING
    if _generator_class() is not None:
        _patch()
        return
    if _WATCHING:  # one watcher is enough, however many callers install
        return
    _WATCHING = True
    real_import = builtins.__import__

    def watching_import(name, globals=None, locals=None, fromlist=(), level=0):
        module = real_import(name, globals, locals, fromlist, level)
        if _generator_class() is not None:
            builtins.__import__ = real_import  # one shot: nothing left to wait for
            _patch()
        return module

    builtins.__import__ = watching_import


def install() -> None:
    """Wrap the generator's four call points once per process (idempotent).

    Called where a param-grid terrain cfg is built, i.e. before any env constructs a
    generator from it -- the generation happens inside ``TerrainGenerator.__init__``, so
    wrapping an instance afterwards would be too late. The wrapping itself is deferred past the
    pre-kit window (P001/P003) by :func:`_patch_when_imported`; the invariant is unchanged,
    because that module cannot be reached before it is imported, and importing it is what
    applies the patch.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    if _generator_class() is not None:  # already imported: a caller paid it
        _patch()
    else:
        _patch_when_imported()


def _drain_leftovers(cfg) -> dict:
    """Record gets that never got their add, then forget them (they are per-generation)."""
    record = _record_for_cfg(cfg)
    for _cfg_id, difficulty, params in _PENDING.pop(id(cfg), []):
        record["anomalies"].append(
            f"a _get_terrain_mesh (difficulty {difficulty:.4f}, {params[:19]}) has no matching _add_sub_terrain"
        )
    return record


def record(cfg, *, verify: bool = True) -> dict:
    """The record captured for this generator cfg, optionally refused when it is not sound."""
    record = _drain_leftovers(cfg)
    if verify:
        problems = terrain_map.check(record)
        if problems:
            raise terrain_map.SplitRecordError(
                f"terrain split record for cfg {id(cfg)} cannot be consumed: " + "; ".join(problems[:5])
            )
    return record


def generate_record(cfg, *, device: str = "cpu") -> dict:
    """Install the probe, run a real generator with ``cfg``, and return its record.

    The offline path for handing a consumer a record a **real generation** produced: the
    generator owns the split, so a test or an offline check must not write the mapping itself.
    """
    install()
    from isaaclab.terrains import TerrainGenerator

    TerrainGenerator(cfg=cfg, device=device)
    return record(cfg)


def record_for(terrain, *, verify: bool = True) -> dict:
    """The record for a live ``TerrainImporter``: keyed by the cfg it generated from."""
    cfg = getattr(getattr(terrain, "cfg", None), "terrain_generator", None)
    if cfg is None:
        raise terrain_map.SplitRecordError("terrain has no generator cfg: nothing to read a split record from")
    if id(cfg) not in _RECORDS:
        raise terrain_map.SplitRecordError(
            "no split record for this terrain: the probe was not installed before the generator ran"
        )
    return record(cfg, verify=verify)
