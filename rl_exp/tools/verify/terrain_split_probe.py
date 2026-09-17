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

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tasks import terrain_map  # noqa: E402

#: cfg identity -> record. Keyed by the object the generator was built with, which is the
#: same object the curriculum can reach at ``env.scene.terrain.cfg.terrain_generator``.
_RECORDS: dict[int, dict] = {}
#: cfg identity -> gets that have not been paired with an add yet, as (cfg id, difficulty, digest)
_PENDING: dict[int, list[tuple[int, float, str]]] = {}
_INSTALLED = False


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
    return record


def install() -> None:
    """Wrap the generator's two call points once per process (idempotent).

    Called where a param-grid terrain cfg is built, i.e. before any env constructs a
    generator from it -- the generation happens inside ``TerrainGenerator.__init__``, so
    wrapping an instance afterwards would be too late.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    from isaaclab.terrains import TerrainGenerator

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
        return original_curriculum(self)

    def generate_random(self):
        _start_generation(self.cfg)
        return original_random(self)

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
                record["cells"].append({
                    "row": int(row),
                    "col": int(col),
                    "sub_terrain": _name_of(self.cfg, sub_terrain_cfg),
                    "difficulty": difficulty,
                    "params": params,
                })
        return original_add(self, mesh, origin, row, col, sub_terrain_cfg)

    TerrainGenerator._get_terrain_mesh = get_terrain_mesh
    TerrainGenerator._add_sub_terrain = add_sub_terrain
    TerrainGenerator._generate_curriculum_terrains = generate_curriculum
    TerrainGenerator._generate_random_terrains = generate_random
    _INSTALLED = True

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
