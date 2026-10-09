# -*- coding: utf-8 -*-
"""Pre-training terrain preflight: offline roughness stats + rendered previews.

No Isaac Sim needed (plain venv python, numpy + torch + matplotlib). Builds every
sub-terrain of the frozen ``lizard/main`` v11 ``terrain_grid`` table -- expanded by
the retained ``param_grid_terrain`` builder and read through the retained
``recipe_params`` loader -- through the SAME IsaacLab code path the env uses
(generator-level scale/slope injection included, terrain_generator.py:123-130) and
prints a roughness table benchmarked against the body calibration:

  sole 0.46 x 0.51 m flat plate | stand height 0.94 m | foot lift ~0.52 m

"foot-plate relief" = height difference within one 0.5 m cell ~= what one
sole spans at a stance -- the metric that caught the v3.6 flat-rubble bug
(0.3 m pitch < sole width, plate bridged the bumps).

Also writes one PNG heatmap per sub-terrain to the git-ignored products tree
(rl_exp/tools/diagnose/out/terrain_previews/) for eyeballing, plus a sha256 of
what actually decides the geometry
-- vertices, faces and the terrain origin -- so a preview run can be compared
against the next one instead of trusted.

**What this digest is not**: it is a regression baseline for THIS offline
preview, not evidence about the geometry a training run stood on. The real
generator builds a local rng and leaves the global ones alone, while these
functions draw from the global streams (numpy for the height-field terrains
and the random boxes, torch for ``boxes`` heights -- mesh_terrains.py:348),
so a real run's geometry also depends on the process history. Archiving the
actual run's geometry is a different item (work/active/verified-rebuild-rating.md ⑤b).

Usage:
  python rl_exp\\tools\\verify\\terrain_preflight.py                    # frozen v11 param grid
  python rl_exp\\tools\\verify\\terrain_preflight.py --self-test        # falsify the digest
"""
import argparse
import pathlib
import sys

import numpy as np
import trimesh

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from rl_exp.tasks import recipe_params  # noqa: E402
from rl_exp.tasks.param_grid_terrain import build_param_grid_terrain_cfg  # noqa: E402
from rl_exp.tasks.terrain_geometry import foot_relief, geometry_digest, seed_rngs, stats  # noqa: E402,F401
from isaaclab.terrains.height_field import HfTerrainBaseCfg  # noqa: E402

#: The frozen geometry source: ``versions/lizard/main/v11/main_params.yaml``, read through the
#: loader every line shares. The version names both the frozen document and the section inside it
#: (the ``terrain_grid`` table is a v11 recipe delta -- versions/lizard/v11/PLAN.md section 1).
_GRID_LINE = "lizard/main"
_GRID_VERSION = "v11"
#: Sub-terrain TYPES whose geometry comes from a global RNG *and* can differ between seeds at all.
#: Param-grid sub-terrains are named ``<type>|<levels>``, so the type is the part before the bar.
#: ``random_rough`` is deliberately absent: the frozen grid pins its ``noise_amp`` levels to
#: single-value ranges whose step is the amplitude itself, so a height field samples one value and
#: is the same constant plane under every seed -- a seed comparison on it fails by construction,
#: not by defect (measured on the v11 grid, 2026-10-09: seed 7 and seed 8 hash alike).
_RANDOM_SUB_TERRAINS = ("stepping_stones", "boxes")


def terrain_cfg(version: str):
    """The generator cfg to preview: the frozen version's ``terrain_grid`` table, expanded.

    One sub-terrain per parameter combination, with single-value ranges -- so the recipe's own
    difficulty levels are what the preview shows, rather than points on a difficulty diagonal.
    """
    document = recipe_params.load(_GRID_LINE, version)
    return build_param_grid_terrain_cfg(document[version]["terrain_grid"])


def build_sub_terrain(gen_cfg, sub_cfg, difficulty, seed):
    """Materialize one sub-terrain the way TerrainGenerator would (injection
    included, but on a copy -- the caller's generator cfg stays as built).

    The global RNGs are seeded per sub-terrain, which the real generator does not do: the
    preview trades the run's stream order for a digest that depends on (version, difficulty,
    seed, name) alone. Returns the raw mesh list, the origin and the joined mesh (for stats).
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
    return meshes, origin, trimesh.util.concatenate(meshes)


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
    # param-grid names separate the type from its levels with a bar, which no filesystem accepts
    out = out_dir / f"{version}_{name.replace('|', '_')}.png"
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out


def self_test() -> list[str]:
    """Falsify the digest: reproducible per seed, independent of call order, and sensitive.

    The order case is what the seeding earns. Unchecked, a second build of the same sub-terrain
    continues the global stream where the first left it and hashes differently -- which is
    exactly what a real run does today, since the generator seeds only its own local rng
    (work/active/verified-rebuild-rating.md). Drop :func:`seed_rngs` and this test goes red.

    Returns:
        One problem per case that behaved unlike the geometry says.
    """
    problems: list[str] = []
    gen = terrain_cfg(_GRID_VERSION)
    names = [name for name in gen.sub_terrains if name.split("|")[0] in _RANDOM_SUB_TERRAINS]
    if not names:
        return ["no seed-sensitive global-RNG sub-terrain in the frozen v11 grid: this self-test"
                " would guard nothing"]

    def digest_of(name: str, seed: int) -> str:
        meshes, origin, _ = build_sub_terrain(gen, gen.sub_terrains[name], 1.0, seed)
        return geometry_digest(meshes, origin)

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
    p.add_argument("--version", default=_GRID_VERSION, choices=(_GRID_VERSION,),
                   help="frozen params version whose terrain_grid is previewed (the only one that "
                        "still carries the table)")
    p.add_argument("--difficulty", type=float, default=1.0,
                   help="row difficulty handed to the sub-terrain function; every param-grid combo "
                        "pins its ranges to a single value, so this no longer moves the geometry "
                        "(0.0..1.0, default = hardest)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="rl_exp/tools/diagnose/out/terrain_previews",
                   help="PNG output dir, relative to the repo root (git-ignored default).")
    p.add_argument("--self-test", action="store_true", help="falsify the geometry digest instead")
    args = p.parse_args()

    if args.self_test:
        problems = self_test()
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1 if problems else 0

    out_dir = _REPO / args.out
    out_dir.mkdir(exist_ok=True)
    gen_cfg = terrain_cfg(args.version)

    print(f"version {args.version}  difficulty {args.difficulty:.2f}  seed {args.seed}")
    print(f"body calibration: sole 0.46x0.51 m | stand 0.94 m | foot lift ~0.52 m")
    print(f"{'sub-terrain':<20} {'z std':>7} {'z p2p':>7} {'relief mean':>12} "
          f"{'relief p95':>11} {'relief max':>11}  geometry digest")
    for name, sub_cfg in gen_cfg.sub_terrains.items():
        meshes, origin, mesh = build_sub_terrain(gen_cfg, sub_cfg, args.difficulty, args.seed)
        s = stats(mesh)
        # relief is a vertex measure: a column meshed coarsely (a staircase, a gap) hides the
        # surface between its corners, and printing that spread as bumpiness would be a number
        # nobody should act on -- so the column says so instead
        if foot_relief(mesh) is None:
            relief_cols = f"{'n/a':>12} {'n/a':>11} {'n/a':>11}"
        else:
            relief_cols = f"{s['relief_mean']:>12.3f} {s['relief_p95']:>11.3f} {s['relief_max']:>11.3f}"
        print(f"{name:<20} {s['std']:>7.3f} {s['p2p']:>7.3f} {relief_cols}  "
              f"{geometry_digest(meshes, origin)}")
        render(mesh, name, out_dir, args.version, args.difficulty)
    print(f"previews: {out_dir}\\{args.version}_*.png")
    print("digest covers vertices + faces + origin, and follows (version, difficulty, seed, name): "
          "a preview regression baseline, not the geometry a training run stood on")
    print("TERRAIN_PREFLIGHT_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
