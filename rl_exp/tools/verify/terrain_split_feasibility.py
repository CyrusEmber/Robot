# -*- coding: utf-8 -*-
"""Feasibility gate for the terrain-split probe (ARCH_PLAN Step 3.3a). **This is the gate.**

Steps 3.3b/3.3c (a single split rule + a probe that records what the generator really did)
only make sense if the real generator can be built headless and watched at **both** call
points, with the pairing verified rather than assumed. This script answers exactly that:

1. build the param-grid terrain cfg from the recipe's ``terrain_grid`` table (the SSOT) and
   construct a real ``TerrainGenerator`` with it -- no Isaac Sim app, plain venv python;
2. install the probe and check the captured record: one cell per grid position, no pairing
   anomaly, and every captured cell agrees with the **independently computed** column split
   (``terrain_map.column_split``) -- the two sides are different executants, which is what
   makes the agreement evidence instead of self-confirmation;
3. a negative control: corrupting the declared split in the record must make ``check`` fire,
   so a green run above cannot be a vacuous one.

A failure here means 3.3c cannot be an offline probe and the curriculum migration (3.3d/e)
has nothing to stand on.
"""

import argparse
import pathlib
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

import yaml  # noqa: E402

from rl_exp.tasks import terrain_map  # noqa: E402
from rl_exp.tasks.param_grid_terrain import build_param_grid_terrain_cfg  # noqa: E402
from rl_exp.tools.verify import terrain_split_probe as probe  # noqa: E402

_GRID_SECTION = "v11"
_DEFAULT_PARAMS = _REPO / "rl_exp" / "versions" / "lizard" / "main" / "v11" / "main_params.yaml"


def _grid(path: pathlib.Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return document[_GRID_SECTION]["terrain_grid"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--params", type=pathlib.Path, default=_DEFAULT_PARAMS,
                        help="params document holding the terrain_grid table")
    parser.add_argument("--device", default="cpu", help="device for the flat-patches tensor")
    args = parser.parse_args()

    from isaaclab.terrains import TerrainGenerator

    cfg = build_param_grid_terrain_cfg(_grid(args.params))
    print(f"grid: {len(cfg.sub_terrains)} sub-terrains, {cfg.num_rows}x{cfg.num_cols} cells, "
          f"curriculum={cfg.curriculum}, seed={cfg.seed}")

    probe.install()
    started = time.time()
    generator = TerrainGenerator(cfg=cfg, device=args.device)
    seconds = time.time() - started
    print(f"TerrainGenerator built headless in {seconds:.1f}s "
          f"(origins {tuple(generator.terrain_origins.shape)})")

    record = probe.record(cfg, verify=False)
    problems = terrain_map.check(record)
    expected = int(cfg.num_rows) * int(cfg.num_cols)
    print(f"captured {len(record['cells'])} cells of {expected}; anomalies {len(record['anomalies'])}")
    for anomaly in record["anomalies"][:5]:
        print(f"  anomaly: {anomaly}")
    for problem in problems[:5]:
        print(f"  problem: {problem}")

    failures = list(problems)
    if len(record["cells"]) != expected:
        failures.append(f"grid incomplete: {len(record['cells'])} captured, {expected} expected")
    if record["mode"] != terrain_map.MODE_CURRICULUM:
        failures.append(f"generation mode is {record['mode']!r}, expected curriculum")

    # negative control: the declared split must be load-bearing, not decoration
    corrupted = dict(record)
    corrupted["columns"] = [0] * len(record["columns"])
    if not any("declared split says" in problem for problem in terrain_map.check(corrupted)):
        failures.append("negative control: a corrupted column split was not caught")

    if failures:
        print(f"TERRAIN_SPLIT_FEASIBILITY_FAILED ({len(failures)} problem(s))")
        return 1
    print(f"captured difficulty range {min(c['difficulty'] for c in record['cells']):.3f}.."
          f"{max(c['difficulty'] for c in record['cells']):.3f}")
    print("TERRAIN_SPLIT_FEASIBILITY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
