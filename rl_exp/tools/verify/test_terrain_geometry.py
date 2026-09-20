# -*- coding: utf-8 -*-
"""Offline gate for terrain geometry: the digest, the seeding, and the suite it measures.

Three claims, each aimed at a failure that would otherwise show up as "two runs disagree":

1. A real generation can be hashed, and two generations of the same ground hash alike when the
   global streams are seeded first -- the property PLAN.md #18 ②/⑤b rests on. Unseeded they
   differ, which is what makes the seeding load-bearing rather than decorative.
2. The eval suite's rough columns are actually rough (PLAN.md #18 ①): v1's single-value
   ``noise_range`` collapsed the sampler to a constant plate, so a "rough" column measured
   nothing. v1 stays as it is -- results were taken on it -- and v2 is the fix.
3. The column layout is unchanged between v1 and v2, so the two are readable side by side.
4. The ground a real run archived is reproducible from what the archive names, and the relief of
   its rough columns is real -- the check that turns "the suite is rough" from a claim about code
   into a claim about the ground a run stood on (PLAN.md #18 ①/⑤b).
"""
import json
import pathlib
import sys

import yaml

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

import isaaclab.terrains as terrain_gen  # noqa: E402
from isaaclab.terrains import TerrainGeneratorCfg  # noqa: E402

from ablation_harness import suites  # noqa: E402
from rl_exp.tasks.terrain_geometry import foot_relief, seed_rngs  # noqa: E402
from rl_exp.tools.verify import terrain_preflight, terrain_split_probe  # noqa: E402

_SEED = 7

#: One real v3 run's archived ground: written by ``eval.py`` at the end of the rollout, committed
#: with the run's other records. Regenerating from it is what makes the archive checkable.
_V3_EVIDENCE = (_REPO / "ablation_harness" / "results" / "locomotion_eval_v3" / "smoke"
                / "Lizard-Rough-v14_zeroaction-evidence_nominal_seed123" / "terrain" / "geometry.json")


def _cfg() -> TerrainGeneratorCfg:
    """One flat column and one that draws from the global numpy stream."""
    return TerrainGeneratorCfg(
        size=(8.0, 8.0),  # the spline under downsampled_scale=0.5 needs ~10 samples per axis
        border_width=1.0,
        num_rows=1,
        num_cols=2,
        curriculum=True,
        difficulty_range=(1.0, 1.0),
        seed=123,
        use_cache=False,
        sub_terrains={
            "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=1.0),
            "rough": terrain_gen.HfRandomUniformTerrainCfg(
                proportion=1.0,
                noise_range=(0.02, 0.06),
                noise_step=0.01,
                downsampled_scale=0.5,
                border_width=1.0,
            ),
        },
    )


def _generate(seed: int | None) -> dict:
    if seed is not None:
        seed_rngs(seed)
    return terrain_split_probe.generate_record(_cfg())


def test_a_real_generation_hashes_every_cell() -> None:
    """The capture sees the mesh the generator built, cell by cell."""
    record = _generate(_SEED)
    assert record["anomalies"] == [], f"a sound generation must not raise anomalies: {record['anomalies']}"
    assert len(record["cells"]) == 2, f"one flat + one rough column: {record['cells']}"
    for cell in record["cells"]:
        assert (cell.get("geometry") or "").startswith("sha256:"), f"unhashed cell: {cell}"
    assert record["geometry_digest"].startswith("sha256:"), record


def test_the_seed_is_what_pins_the_ground() -> None:
    """Same seed, same ground -- and without the seed, the same cfg does not repeat.

    The second half is the falsifier: neuter :func:`seed_rngs` and this check goes red, which is
    the whole reason a real run's terrain is not reproducible today (PLAN.md #18 ②).
    """
    first, second = _generate(_SEED), _generate(_SEED)
    assert first["geometry_digest"] == second["geometry_digest"], \
        "two seeded generations of one cfg must stand on the same ground"
    assert _generate(_SEED)["cells"][1]["geometry"] == first["cells"][1]["geometry"], \
        "the moving column is the one that draws from a global stream"

    unseeded = {_generate(None)["geometry_digest"] for _ in range(3)}
    assert len(unseeded) > 1, (
        "without the seeding the same cfg must not repeat -- if this fails, the terrain "
        "functions have stopped drawing from the global streams and this check guards nothing"
    )


def test_eval_suite_rough_columns_are_rough() -> None:
    """v2's rough columns vary inside a foot cell; v1's do not, and stay frozen that way.

    ``relief_p95`` is the surface's height range inside one 0.5 m cell -- the sole-sized metric
    the preflight uses. It is exactly zero on v1's rough columns, because a single-value
    ``noise_range`` leaves ``np.random.choice`` one height to choose from (PLAN.md #18 ①).
    """
    assert suites.LIZARD_SUITE_V2_NAMES == suites.LIZARD_SUITE_V1_NAMES, "the columns must line up"

    def relief(generator, name: str) -> float:
        _, _, mesh = terrain_preflight.build_sub_terrain(generator, generator.sub_terrains[name], 1.0, 123)
        measured = foot_relief(mesh)
        assert measured is not None, f"{name}: a height-field column is densely meshed and must measure"
        return measured

    for name in ("rough_a", "rough_b"):
        v2 = relief(suites._LIZARD_SUITE_V2_GENERATOR, name)
        v1 = relief(suites._LIZARD_SUITE_V1_GENERATOR, name)
        assert v2 > 0.02, f"{name}: v2 must vary inside a footprint (relief_p95={v2})"
        assert v1 == 0.0, f"{name}: v1's constant plate is frozen -- do not 'fix' v1 in place (relief_p95={v1})"
    assert relief(suites._LIZARD_SUITE_V2_GENERATOR, "rough_b") > relief(suites._LIZARD_SUITE_V2_GENERATOR, "rough_a"), \
        "rough_b must stay the harder of the two, as its amplitude says"


def test_the_archived_ground_of_a_real_run_regenerates() -> None:
    """A real run's archived terrain verifies offline, and its rough columns are rough.

    This is the ⑤b half that does not need a simulator: the file a run wrote says what generated
    it (suite + seed), so regenerating from that and comparing cell by cell is a real check on
    the archived ground rather than a read-back of it. It also carries the relief inside one foot
    cell, which is the claim #18 ① is about -- a column named "rough" has to show it.

    Ceiling: this verifies the *evidence*, not the bytes. If the framework's terrain code changes,
    the regenerated digest moves and the comparison below fails against the archived file -- the
    archive pins what the ground was, it does not resurrect it.
    """
    artifact = json.loads(_V3_EVIDENCE.read_text(encoding="utf-8"))
    identity = artifact["identity"]
    seed_rngs(identity["seed"])
    regenerated = terrain_split_probe.generate_record(getattr(suites, identity["suite"])().terrain_generator)
    assert regenerated["geometry_digest"] == artifact["geometry_digest"], (
        f"the archived ground ({identity}) must regenerate: {artifact['geometry_digest']} != "
        f"{regenerated['geometry_digest']}"
    )
    archived = {(cell["row"], cell["col"]): cell for cell in artifact["cells"]}
    assert len(archived) == len(artifact["cells"]) > 0, "the archive must carry unique cells"
    for cell in regenerated["cells"]:
        assert archived[(cell["row"], cell["col"])]["geometry"] == cell["geometry"], \
            f"cell ({cell['row']}, {cell['col']}) drifted from the archived one"

    relief = {cell["sub_terrain"]: cell["relief"] for cell in artifact["cells"]}
    assert relief["rough_a"] > 0.02, f"a rough column must vary inside a footprint: {relief}"
    assert relief["rough_b"] > relief["rough_a"], f"the harder rough column must be bumpier: {relief}"
    # the gate, not a missing value: a staircase and a plane are meshed with faces far bigger than
    # a foot cell, and a vertex measure there reads the corners of one face (see foot_relief)
    assert relief["stairs_20cm"] is None, f"a coarse column must not report a relief: {relief}"
    assert relief["flat"] is None, f"two 16 m triangles are not a measurement: {relief}"


def test_protocol_v3_differs_from_v2_only_where_it_says() -> None:
    """A new protocol file is a copy plus one documented change -- not a slow re-typing drift.

    v3's reason to exist is the suite, so name / version / suite are the only fields allowed to
    move. Anything else that moves is an undocumented semantic change hiding in a version bump.
    """
    root = _REPO / "ablation_harness" / "protocols"
    v2 = yaml.safe_load((root / "locomotion_eval_v2.yaml").read_text(encoding="utf-8"))
    v3 = yaml.safe_load((root / "locomotion_eval_v3.yaml").read_text(encoding="utf-8"))
    assert v3["version"] == v2["version"] + 1 and v3["name"] != v2["name"], "version discipline"
    assert v3["suite"] == "lizard_suite_v2", v3["suite"]
    moved = sorted(key for key in set(v2) | set(v3) if v2.get(key) != v3.get(key))
    assert moved == ["name", "suite", "version"], f"v3 must move only what it documents: {moved}"


def _main() -> None:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"[OK] {fn.__name__}")
    print(f"test_terrain_geometry: {len(tests)} passed")


if __name__ == "__main__":
    _main()
