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
-- seeds here first, and can say what it stood on with :func:`geometry_digest`.
"""

import hashlib

import numpy as np


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
