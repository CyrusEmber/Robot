# -*- coding: utf-8 -*-
"""Pre-training terrain preflight: offline roughness stats + rendered previews.

No Isaac Sim needed (plain venv python, numpy + torch + matplotlib). Builds every
sub-terrain of the selected recipe version's terrain generator cfg through
the SAME IsaacLab code path the env uses (generator-level scale/slope
injection included, terrain_generator.py:123-130) and prints a roughness
table benchmarked against the body calibration:

  sole 0.46 x 0.51 m flat plate | stand height 0.94 m | foot lift ~0.52 m

"foot-plate relief" = height difference within one 0.5 m cell ~= what one
sole spans at a stance -- the metric that caught the v3.6 flat-rubble bug
(0.3 m pitch < sole width, plate bridged the bumps).

Also writes one PNG heatmap per sub-terrain to _tmp_terrain_previews/ for
eyeballing (git-ignored), plus a sha256 of what actually decides the geometry
-- vertices, faces and the terrain origin -- so a preview run can be compared
against the next one instead of trusted.

**What this digest is not**: it is a regression baseline for THIS offline
preview, not evidence about the geometry a training run stood on. The real
generator builds a local rng and leaves the global ones alone, while these
functions draw from the global streams (numpy for the height-field terrains
and the random boxes, torch for ``boxes`` heights -- mesh_terrains.py:348),
so a real run's geometry also depends on the process history. Archiving the
actual run's geometry is a different item (PLAN.md #18 ⑤b).

Usage:
  python rl_exp\\tools\\verify\\terrain_preflight.py                     # v4 (default)
  python rl_exp\\tools\\verify\\terrain_preflight.py --version v3       # compare base
  python rl_exp\\tools\\verify\\terrain_preflight.py --self-test        # falsify the digest
"""
import argparse
import hashlib
import pathlib
import sys

import numpy as np
import torch
import trimesh

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from rl_exp.tasks.teacher_env_cfg import (  # noqa: E402
    TEACHER_TERRAINS_CFG,
    TEACHER_TERRAINS_CFG_V3,
    TEACHER_TERRAINS_CFG_V4,
    TEACHER_TERRAINS_CFG_V5,
)
from isaaclab.terrains.height_field import HfTerrainBaseCfg  # noqa: E402

_CFG_BY_VERSION = {
    "v1": TEACHER_TERRAINS_CFG,
    "v2": TEACHER_TERRAINS_CFG,
    "v3": TEACHER_TERRAINS_CFG_V3,
    "v4": TEACHER_TERRAINS_CFG_V4,
    # v5.3: v4 grid + flat bootstrap column (SIR terrain curriculum)
    "v5": TEACHER_TERRAINS_CFG_V5,
}
_FOOT_CELL = 0.5  # m, ~= sole width (0.46) -- relief under one foot plate

#: Sub-terrains whose geometry comes from a global RNG, and which therefore pin the seeding.
_RANDOM_SUB_TERRAINS = ("random_rough", "stepping_stones", "boxes")


def seed_rngs(seed):
    """Seed both global RNGs the terrain functions draw from.

    ``TerrainGenerator`` builds its own local rng on purpose (terrain_generator.py:148) and
    never touches the global ones, so without this a sub-terrain is a function of process
    history rather than of ``cfg.seed``: measured, two builds of the same cfg disagree
    (PLAN.md #18). Numpy covers the height-field terrains, torch covers ``boxes``.
    """
    np.random.seed(int(seed))
    torch.manual_seed(int(seed))


def geometry_digest(mesh, origin) -> str:
    """sha256 over the geometry: vertices, faces and the terrain origin.

    Arrays are cast to a fixed dtype and byte order before hashing, so the digest does not
    depend on the platform's float default or endianness; values are compared at that
    precision. The origin is carried in because the generators use it to place a patch rather
    than to shape it -- dropping it would let two different placements hash alike.
    """
    digest = hashlib.sha256()
    for name, array, cast in (("vertices", np.asarray(mesh.vertices), "<f8"),
                              ("faces", np.asarray(mesh.faces), "<i8"),
                              ("origin", np.asarray(origin), "<f8")):
        canonical = np.ascontiguousarray(array, dtype=cast)
        digest.update(f"{name} {canonical.dtype.str} {canonical.shape} ".encode())
        digest.update(canonical.tobytes())
    return "sha256:" + digest.hexdigest()


def build_sub_terrain(gen_cfg, sub_cfg, difficulty, seed):
    """Materialize one sub-terrain the way TerrainGenerator would (injection
    included, but on a copy -- the module-level teacher cfgs stay frozen).

    The global RNGs are seeded per sub-terrain, which the real generator does not do: the
    preview trades the run's stream order for a digest that depends on (version, difficulty,
    seed, name) alone. Returns the mesh and the origin the generator places it at.
    """
    sub = sub_cfg.copy()
    sub.size = tuple(gen_cfg.size)
    if isinstance(sub, HfTerrainBaseCfg):
        sub.horizontal_scale = gen_cfg.horizontal_scale
        sub.vertical_scale = gen_cfg.vertical_scale
        sub.slope_threshold = gen_cfg.slope_threshold
    sub.difficulty = float(difficulty)
    sub.seed = int(seed)
    seed_rngs(seed)
    meshes, origin = sub.function(sub.difficulty, sub)
    return trimesh.util.concatenate(meshes), origin


def stats(mesh):
    v = np.asarray(mesh.vertices)
    z = v[:, 2]
    ix = np.floor(v[:, 0] / _FOOT_CELL).astype(int)
    iy = np.floor(v[:, 1] / _FOOT_CELL).astype(int)
    ix -= ix.min()  # shift to non-negative -- floor() on centered meshes goes
    iy -= iy.min()  # negative and would collide the packed key below
    key = ix.astype(np.int64) * (iy.max() + 1) + iy
    bins = np.unique(key)
    zmax = np.full(key.max() + 1, -np.inf)
    zmin = np.full(key.max() + 1, np.inf)
    np.maximum.at(zmax, key, z)
    np.minimum.at(zmin, key, z)
    relief = (zmax - zmin)[bins]  # height range inside one 0.5 m foot cell
    return {
        "std": z.std(),
        "p2p": z.max() - z.min(),
        "relief_mean": relief.mean(),
        "relief_p95": np.percentile(relief, 95),
        "relief_max": relief.max(),
    }


def render(mesh, name, out_dir, version, difficulty):
    v = np.asarray(mesh.vertices)
    res = 0.2  # heatmap lattice (m)
    nx = int(np.ceil(np.ptp(v[:, 0]) / res)) + 1
    ny = int(np.ceil(np.ptp(v[:, 1]) / res)) + 1
    grid = np.full((ny, nx), np.nan)
    ix = np.clip(((v[:, 0] - v[:, 0].min()) / res).astype(int), 0, nx - 1)
    iy = np.clip(((v[:, 1] - v[:, 1].min()) / res).astype(int), 0, ny - 1)
    grid[iy, ix] = v[:, 2]  # fine vertices -> last write wins, fine for preview
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(grid, origin="lower", cmap="terrain")
    fig.colorbar(im, ax=ax, label="height [m]")
    ax.set_title(f"{version} / {name}  (difficulty {difficulty:.2f})")
    ax.set_xlabel("x [cells of 0.2 m]")
    ax.set_ylabel("y [cells of 0.2 m]")
    out = out_dir / f"{version}_{name}.png"
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out


def self_test() -> list[str]:
    """Falsify the digest: reproducible per seed, independent of call order, and sensitive.

    The order case is what the seeding earns. Unchecked, a second build of the same sub-terrain
    continues the global stream where the first left it and hashes differently -- which is
    exactly what a real run does today, since the generator seeds only its own local rng
    (PLAN.md #18). Drop :func:`seed_rngs` and this test goes red.

    Returns:
        One problem per case that behaved unlike the geometry says.
    """
    problems: list[str] = []
    gen = _CFG_BY_VERSION["v5"]
    names = [name for name in _RANDOM_SUB_TERRAINS if name in gen.sub_terrains]
    if not names:
        return ["no global-RNG sub-terrain in the v5 cfg: this self-test would guard nothing"]

    def digest_of(name: str, seed: int) -> str:
        mesh, origin = build_sub_terrain(gen, gen.sub_terrains[name], 1.0, seed)
        return geometry_digest(mesh, origin)

    for index, name in enumerate(names):
        first = digest_of(name, 7)
        digest_of(names[(index + 1) % len(names)], 11)  # another build in between
        again = digest_of(name, 7)
        if first != again:
            problems.append(
                f"{name}: the same (difficulty, seed) hashed differently after another build "
                f"({first[:14]} vs {again[:14]}) -- the global RNG is not re-seeded per sub-terrain"
            )
        if digest_of(name, 8) == first:
            problems.append(f"{name}: seed 8 hashed like seed 7 -- the digest does not follow the seed")

    class _Stub:  # geometry_digest reads only these two attributes
        def __init__(self, vertices, faces):
            self.vertices = vertices
            self.faces = faces

    stub = _Stub(np.zeros((3, 3)), np.array([[0, 1, 2]]))
    print_origin = np.zeros(3)
    base = geometry_digest(stub, print_origin)
    moved_vertex = _Stub(np.array([[1e-6, 0.0, 0.0], [0, 0, 0], [0, 0, 0]]), stub.faces)
    moved_face = _Stub(stub.vertices, np.array([[0, 2, 1]]))
    cases = [
        (moved_vertex, print_origin, "a moved vertex"),
        (stub, np.array([1e-6, 0.0, 0.0]), "a moved origin"),
        (moved_face, print_origin, "a rewired face"),
    ]
    for shape, origin, what in cases:
        if geometry_digest(shape, origin) == base:
            problems.append(f"{what} does not reach the digest")
    print("TERRAIN_DIGEST_SELF_TEST_OK" if not problems else "TERRAIN_DIGEST_SELF_TEST_FAILED")
    return problems


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version", default="v4", choices=sorted(_CFG_BY_VERSION))
    p.add_argument("--difficulty", type=float, default=1.0,
                   help="1.0 = hardest curriculum row (default), 0.0 = easiest.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="_tmp_terrain_previews",
                   help="PNG output dir (git-ignored default).")
    p.add_argument("--self-test", action="store_true", help="falsify the geometry digest instead")
    args = p.parse_args()

    if args.self_test:
        problems = self_test()
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1 if problems else 0

    out_dir = _REPO / args.out
    out_dir.mkdir(exist_ok=True)
    gen_cfg = _CFG_BY_VERSION[args.version]

    print(f"version {args.version}  difficulty {args.difficulty:.2f}  seed {args.seed}")
    print(f"body calibration: sole 0.46x0.51 m | stand 0.94 m | foot lift ~0.52 m")
    print(f"{'sub-terrain':<20} {'z std':>7} {'z p2p':>7} {'relief mean':>12} "
          f"{'relief p95':>11} {'relief max':>11}  geometry digest")
    for name, sub_cfg in gen_cfg.sub_terrains.items():
        mesh, origin = build_sub_terrain(gen_cfg, sub_cfg, args.difficulty, args.seed)
        s = stats(mesh)
        print(f"{name:<20} {s['std']:>7.3f} {s['p2p']:>7.3f} {s['relief_mean']:>12.3f} "
              f"{s['relief_p95']:>11.3f} {s['relief_max']:>11.3f}  {geometry_digest(mesh, origin)}")
        render(mesh, name, out_dir, args.version, args.difficulty)
    print(f"previews: {out_dir}\\{args.version}_*.png")
    print("digest covers vertices + faces + origin, and follows (version, difficulty, seed, name): "
          "a preview regression baseline, not the geometry a training run stood on")
    print("TERRAIN_PREFLIGHT_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
