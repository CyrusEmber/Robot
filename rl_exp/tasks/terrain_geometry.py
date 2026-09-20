# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Terrain geometry primitives: one seeder, one digest, for every path that makes terrain.

The generator builds a *local* rng on purpose (``terrain_generator.py:148``) and leaves the
global streams alone, while the terrain functions draw from them: numpy in the height-field
family (``hf_terrains.py``) and in the random boxes, torch for the boxes' heights
(``mesh_terrains.py:348``). So "the cfg has a seed" pins the config, not the ground.

Anything that must reproduce its terrain -- a training run, an eval suite, the offline preview
-- seeds here first, and can say what it stood on with :func:`geometry_digest`. The measurements
live here too (:func:`stats`, :func:`foot_relief`, :func:`evidence`), so the preview table and a
real run's record cannot drift into two definitions that agree only today.
"""

import hashlib

import numpy as np

#: ~= the sole width (0.46 m): the cell one foot plate covers. Relief below this scale is what
#: the robot feels as bumpiness, so a "rough" terrain has to show it *inside* a cell, not just
#: across the map (PLAN.md #18 ①).
_FOOT_CELL = 0.5

#: A cell is measured only when no face of the mesh is bigger than the cell. Inside one
#: triangular face z is *linear*, so a face that fits in a cell is measured exactly by its
#: vertices; a bigger face can straddle the cell, and then the corners of that single face are
#: read as bumpiness -- measured on this suite's stairs (264 vertices over a 16 m patch, faces up
#: to 16 m) a 0.5 m cell holding four of them reported 0.87 m for a 0.10 m riser. The suite's
#: height fields sit at 0.14-0.28 m faces and pass; its stairs, gaps and its two-triangle plane
#: (22 m faces) do not.
_MAX_MEASURABLE_FACE = _FOOT_CELL


def seed_rngs(seed: int) -> None:
    """Seed both global streams the terrain functions draw from (numpy and torch).

    Deliberately not :func:`isaaclab.utils.seed.configure_seed`: that one also flips cuDNN
    determinism, PYTHONHASHSEED and warp's rng, which changes how a *run* behaves and is
    upstream's call to make at upstream's point in the process. This one only answers "which
    ground did the generator roll".

    Args:
        seed: the value both streams are reset to.
    """
    import torch  # local: keeps this module importable without the framework's stack

    np.random.seed(int(seed))
    torch.manual_seed(int(seed))


def geometry_digest(mesh, origin) -> str:
    """sha256 over the geometry: every mesh in order, then the terrain origin.

    ``mesh`` is a trimesh object or the list the terrain functions return (a list is hashed
    entry by entry in order, so a rebuild and a real generation are comparable). Arrays are cast
    to a fixed dtype and byte order, so the digest does not depend on the platform's float
    default or endianness. The origin is carried in because generators use it to place a patch
    rather than to shape it -- dropping it would let two placements hash alike.

    Args:
        mesh: a trimesh object, or a sequence of them, as returned by the terrain functions.
        origin: the terrain origin, shape ``[3]``.
    """
    digest = hashlib.sha256()
    meshes = [mesh] if hasattr(mesh, "vertices") else list(mesh)
    digest.update(f"meshes {len(meshes)} ".encode())
    for index, part in enumerate(meshes):
        for name, array, cast in ((f"{index}.vertices", np.asarray(part.vertices), "<f8"),
                                  (f"{index}.faces", np.asarray(part.faces), "<i8")):
            canonical = np.ascontiguousarray(array, dtype=cast)
            digest.update(f"{name} {canonical.dtype.str} {canonical.shape} ".encode())
            digest.update(canonical.tobytes())
    origin_array = np.ascontiguousarray(np.asarray(origin), dtype="<f8")
    digest.update(f"origin {origin_array.dtype.str} {origin_array.shape} ".encode())
    digest.update(origin_array.tobytes())
    return "sha256:" + digest.hexdigest()


def stats(mesh) -> dict[str, float]:
    """Height statistics of one mesh, including the relief inside one foot-sized cell.

    Moved here from the preview tool: what makes a terrain "rough" for this robot is the height
    range under a foot, so the number the preview prints and the number a run records have to be
    one measurement rather than two that happen to agree.

    Args:
        mesh: one trimesh object.

    Returns:
        ``std`` / ``p2p`` over the whole mesh [m], and ``relief_mean`` / ``relief_p95`` /
        ``relief_max`` over its :data:`_FOOT_CELL`-sized cells [m].
    """
    vertices = np.asarray(mesh.vertices)
    z = vertices[:, 2]
    ix = np.floor(vertices[:, 0] / _FOOT_CELL).astype(int)
    iy = np.floor(vertices[:, 1] / _FOOT_CELL).astype(int)
    ix -= ix.min()  # shift to non-negative -- floor() on centered meshes goes
    iy -= iy.min()  # negative and would collide the packed key below
    key = ix.astype(np.int64) * (iy.max() + 1) + iy
    cells = np.unique(key)
    zmax = np.full(key.max() + 1, -np.inf)
    zmin = np.full(key.max() + 1, np.inf)
    np.maximum.at(zmax, key, z)
    np.minimum.at(zmin, key, z)
    relief = (zmax - zmin)[cells]  # height range inside one foot-sized cell
    return {
        "std": float(z.std()),
        "p2p": float(z.max() - z.min()),
        "relief_mean": float(relief.mean()),
        "relief_p95": float(np.percentile(relief, 95)),
        "relief_max": float(relief.max()),
    }


def foot_relief(mesh) -> float | None:
    """The relief [m] of a generated cell, or ``None`` when the cell cannot be measured.

    A cell is either one mesh or the list the multi-part terrain functions return; for a list the
    widest relief among the parts is the cell's, because a foot landing anywhere in the cell has
    to cope with that part.

    The measure reads vertices, so a mesh whose **faces are larger than a cell** cannot be
    measured by it: the surface between two corners of one big face is invisible, and the spread
    of those corners reads as relief instead (see :data:`_MAX_MEASURABLE_FACE`). Such a cell is
    reported as unmeasurable rather than as a number, and a cell with any unmeasurable part is
    unmeasurable as a whole -- averaging a real number with a corner spread would be a third,
    wrong number. Ceiling: sampling the surface inside the cell (ray casting at a few cm) would
    measure coarse meshes too; it is not done here because a training grid is 200 cells and
    casting every one of them is not an offline cost (upgrade path: sample the surface).
    """
    parts = [mesh] if hasattr(mesh, "vertices") else list(mesh)
    values = []
    for part in parts:
        vertices, faces = np.asarray(part.vertices), np.asarray(part.faces)
        if len(faces) == 0:
            return None
        corners = vertices[faces]
        edges = np.linalg.norm(corners - np.roll(corners, 1, axis=1), axis=-1)
        if float(edges.max()) > _MAX_MEASURABLE_FACE:
            return None
        values.append(stats(part)["relief_p95"])
    return max(values)


def evidence(record: dict, *, identity: dict) -> dict:
    """The archived, JSON-able form of one generation: what was hashed, and how bumpy it was.

    The record itself holds the cells; this adds what a later reader needs to make sense of them
    without this file in front of them -- the digest's and the relief's definitions, and what the
    generator was (a suite name and a seed are enough to rebuild it, which is what the offline
    check does). Numbers stay numbers: the cells are not re-serialised away.

    Args:
        record: the probe's record for one generator cfg.
        identity: what was generating -- at least ``suite`` and ``seed``, plus anything the
            caller knows (``task``, ``protocol``).
    """
    return {
        "definition": {
            "digest": "sha256 over each mesh's vertices (<f8) and faces (<i8, both contiguous) plus the origin",
            "relief": f"height range inside one {_FOOT_CELL} m cell [m], reported as relief_p95;"
                      f" null when the mesh's faces are larger than the cell"
                      f" ({_MAX_MEASURABLE_FACE:g} m), see terrain_geometry.foot_relief",
            "module": "rl_exp.tasks.terrain_geometry",
        },
        "identity": dict(identity),
        "geometry_digest": record.get("geometry_digest"),
        "anomalies": list(record.get("anomalies", [])),
        "cells": [
            {key: cell.get(key) for key in ("row", "col", "sub_terrain", "difficulty", "geometry", "relief")}
            for cell in sorted(record["cells"], key=lambda cell: (cell["row"], cell["col"]))
        ],
    }
