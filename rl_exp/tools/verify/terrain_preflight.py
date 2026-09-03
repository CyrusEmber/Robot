# -*- coding: utf-8 -*-
"""Pre-training terrain preflight: offline roughness stats + rendered previews.

No Isaac Sim needed (plain venv python, numpy + matplotlib). Builds every
sub-terrain of the selected recipe version's terrain generator cfg through
the SAME IsaacLab code path the env uses (generator-level scale/slope
injection included, terrain_generator.py:123-130) and prints a roughness
table benchmarked against the body calibration:

  sole 0.46 x 0.51 m flat plate | stand height 0.94 m | foot lift ~0.52 m

"foot-plate relief" = height difference within one 0.5 m cell ~= what one
sole spans at a stance -- the metric that caught the v3.6 flat-rubble bug
(0.3 m pitch < sole width, plate bridged the bumps).

Also writes one PNG heatmap per sub-terrain to _tmp_terrain_previews/ for
eyeballing (git-ignored). Judgment (good enough? harder than last version?)
stays with the human/LLM running the pretrain check, not this script.

Usage:
  python rl_exp\\tools\\verify\\terrain_preflight.py                     # v4 (default)
  python rl_exp\\tools\\verify\\terrain_preflight.py --version v3       # compare base
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


def build_sub_terrain(gen_cfg, sub_cfg, difficulty, seed):
    """Materialize one sub-terrain the way TerrainGenerator would (injection
    included, but on a copy -- the module-level teacher cfgs stay frozen)."""
    sub = sub_cfg.copy()
    sub.size = tuple(gen_cfg.size)
    if isinstance(sub, HfTerrainBaseCfg):
        sub.horizontal_scale = gen_cfg.horizontal_scale
        sub.vertical_scale = gen_cfg.vertical_scale
        sub.slope_threshold = gen_cfg.slope_threshold
    sub.difficulty = float(difficulty)
    sub.seed = int(seed)
    meshes, _origin = sub.function(sub.difficulty, sub)
    return trimesh.util.concatenate(meshes)


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version", default="v4", choices=sorted(_CFG_BY_VERSION))
    p.add_argument("--difficulty", type=float, default=1.0,
                   help="1.0 = hardest curriculum row (default), 0.0 = easiest.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="_tmp_terrain_previews",
                   help="PNG output dir (git-ignored default).")
    args = p.parse_args()

    out_dir = _REPO / args.out
    out_dir.mkdir(exist_ok=True)
    gen_cfg = _CFG_BY_VERSION[args.version]

    print(f"version {args.version}  difficulty {args.difficulty:.2f}  seed {args.seed}")
    print(f"body calibration: sole 0.46x0.51 m | stand 0.94 m | foot lift ~0.52 m")
    print(f"{'sub-terrain':<20} {'z std':>7} {'z p2p':>7} {'relief mean':>12} "
          f"{'relief p95':>11} {'relief max':>11}")
    for name, sub_cfg in gen_cfg.sub_terrains.items():
        mesh = build_sub_terrain(gen_cfg, sub_cfg, args.difficulty, args.seed)
        s = stats(mesh)
        print(f"{name:<20} {s['std']:>7.3f} {s['p2p']:>7.3f} {s['relief_mean']:>12.3f} "
              f"{s['relief_p95']:>11.3f} {s['relief_max']:>11.3f}")
        render(mesh, name, out_dir, args.version, args.difficulty)
    print(f"previews: {out_dir}\\{args.version}_*.png")
    print("TERRAIN_PREFLIGHT_DONE")


if __name__ == "__main__":
    raise SystemExit(main())
