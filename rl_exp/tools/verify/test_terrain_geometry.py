# -*- coding: utf-8 -*-
"""Offline gate for terrain geometry: the digest, the seeding, and the suite it measures.

Three claims, each aimed at a failure that would otherwise show up as "two runs disagree":

1. A real generation can be hashed, and two generations of the same ground hash alike when the
   global streams are seeded first -- the property work/active/verified-rebuild-rating.md ②/⑤b rests on. Unseeded they
   differ, which is what makes the seeding load-bearing rather than decorative.
2. The eval suite's rough columns are actually rough (work/active/verified-rebuild-rating.md ①): v1's single-value
   ``noise_range`` collapsed the sampler to a constant plate, so a "rough" column measured
   nothing. v1 stays as it is -- results were taken on it -- and v2 is the fix.
3. The column layout is unchanged between v1 and v2, so the two are readable side by side.
4. The ground a real run archived is reproducible from what the archive names, and the relief of
   its rough columns is real -- the check that turns "the suite is rough" from a claim about code
   into a claim about the ground a run stood on (work/active/verified-rebuild-rating.md ①/⑤b).
"""
import json
import math
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
    the whole reason a real run's terrain is not reproducible today (work/active/verified-rebuild-rating.md ②).
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
    ``noise_range`` leaves ``np.random.choice`` one height to choose from (work/active/verified-rebuild-rating.md ①).
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
    cell, which is the claim ① of ``work/active/verified-rebuild-rating.md`` is about -- a column named "rough" has to show it.

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


def test_video_matrix_gears_resolve_against_the_suite() -> None:
    """The video matrix picks its ground off this same suite, so its gears are pinned here.

    ``ablation_harness/video_matrix.py`` shoots a clip per speed x terrain cell. Its terrain gears
    are the suite's column names, and one gear must narrow the frozen generator to *that one*
    column without editing the frozen definition in place -- a mutation would silently leave the
    next gear with fewer columns, and every later clip would face the wrong ground.

    The rest is the part that decides *what* gets shot: which strings are gears and which are
    typos, out-of-box speeds being labelled rather than refused, the chase-camera offsets riding
    the robot's spawn frame, and the module importing no simulator at its top level (P003: a heavy
    import before ``AppLauncher`` poisons Kit's USD stack for the whole run -- importing this
    module through ``suites`` is what that rule is about).
    """
    from ablation_harness import video_matrix
    from unittest.mock import patch
    import tempfile

    # Exercise the recording scheduler, including the camera passed to each rollout.
    # A nine-cell declaration alone would miss recording the same view nine times.
    args = video_matrix.build_parser().parse_args(["--checkpoint", "policy.pt"])
    assert args.speeds == "0.5,1.5,3" and args.seconds == 10.0
    args.dry_run = False
    recorded = []

    def shoot(cell, shot_args):
        recorded.append((cell["speed"], tuple(shot_args.eye), str(shot_args.out_dir)))
        return {"speed_mps": cell["speed"], "terrain": cell["terrain"],
                "clip": str(shot_args.out_dir / f"{cell['speed']:g}mps_plane.mp4")}

    with tempfile.TemporaryDirectory() as directory, \
            patch.object(video_matrix, "record_cell", side_effect=shoot), \
            patch.object(video_matrix, "compose_grids", return_value=["overview.mp4"]) as compose:
        args.out_dir = pathlib.Path(directory)
        output = video_matrix.run(args)
        assert json.loads((args.out_dir / "matrix.json").read_text())["cells"] == output["cells"]
    assert len(recorded) == len(output["cells"]) == 9
    assert {eye for _, eye, _ in recorded} == {(0.0, -5.0, 1.4), (5.0, 0.0, 1.6), (-4.0, -3.0, 2.2)}
    assert len({path for _, _, path in recorded}) == 3
    assert output["grids"] == ["overview.mp4"] and compose.call_count == 1
    assert [shot["view"] for shot in output["cells"]] == ["side", "front", "rear_oblique"] * 3

    # Explicit legacy camera coordinates remain a single custom view, at the old clip paths.
    custom = video_matrix.build_parser().parse_args(["--eye", "1", "2", "3", "--speeds", "2"])
    custom.dry_run = True
    assert video_matrix.run(custom)["cells"] == [{"speed": 2.0, "terrain": "plane", "view": "custom"}]

    # a heavy module bound at module level is the regression; the import itself is the symptom
    for name, value in vars(video_matrix).items():
        root = getattr(value, "__name__", "").split(".")[0]
        assert root not in ("torch", "isaaclab", "gymnasium", "rsl_rl", "imageio"), \
            f"video_matrix imported {name} at module level, before Kit is up"

    assert video_matrix.parse_speeds("1.5,3") == [1.5, 3.0]
    assert video_matrix.parse_speeds("0.5") == [0.5], "a below-the-box gear is a diagnostic, not a typo"
    for bad, why in (("fast", "takes comma-separated numbers"), ("nan", "NaN"), (" , ", "empty")):
        try:
            video_matrix.parse_speeds(bad)
        except SystemExit as exc:
            assert why in str(exc), (bad, str(exc))
        else:
            raise AssertionError(f"parse_speeds({bad!r}) was accepted")

    assert video_matrix.parse_terrains("plane") == ["plane"]
    assert video_matrix.parse_terrains(",".join(["plane", *suites.LIZARD_SUITE_V2_NAMES]))[1:] == \
        suites.LIZARD_SUITE_V2_NAMES, "every frozen column must be reachable as a terrain gear"
    try:
        video_matrix.parse_terrains("plane,tilted")
    except SystemExit as exc:
        assert "tilted" in str(exc) and "slope_10deg" in str(exc), str(exc)
    else:
        raise AssertionError("an unknown terrain gear was accepted")

    frozen_before = dict(suites._LIZARD_SUITE_V2_GENERATOR.sub_terrains)
    board = video_matrix.gear_terrain("rough_b", None)
    assert list(board.terrain_generator.sub_terrains) == ["rough_b"], board.terrain_generator.sub_terrains
    assert (board.terrain_generator.num_rows, board.terrain_generator.num_cols) == (1, 1)
    assert board.terrain_generator.seed == suites.SUITE_SEED, "a gear must be the seeded board"
    assert dict(suites._LIZARD_SUITE_V2_GENERATOR.sub_terrains) == frozen_before, \
        "narrowing a gear edited the frozen suite in place: the next gear would get fewer columns"
    plane = object()
    assert video_matrix.gear_terrain("plane", plane) is plane, \
        "plane must be the recipe's own ground, not the suite's flat column"

    box = [1.0, 3.0]
    assert video_matrix.in_recipe_box(1.0, box) and video_matrix.in_recipe_box(3.0, box)
    assert not video_matrix.in_recipe_box(0.5, box), "an out-of-box gear must read as out of box"

    assert video_matrix.cells([1.5, 3.0], ["plane", "rough_b"]) == [
        {"speed": 1.5, "terrain": "plane"}, {"speed": 1.5, "terrain": "rough_b"},
        {"speed": 3.0, "terrain": "plane"}, {"speed": 3.0, "terrain": "rough_b"},
    ], "speeds outer, every combination once: the manifest order is the shooting order"

    eye, aim = video_matrix.follow_view((10.0, -2.0, 0.5), 0.0, (-4.0, -3.0, 2.2), (1.5, 0.0, 0.3))
    assert eye == (6.0, -5.0, 2.7) and aim == (11.5, -2.0, 0.8), (eye, aim)
    turned, aimed = video_matrix.follow_view((0.0, 0.0, 0.5), math.pi / 2, (-4.0, -3.0, 2.2), (1.5, 0.0, 0.3))
    assert abs(turned[0] - 3.0) < 1e-9 and abs(turned[1] + 4.0) < 1e-9, turned
    assert abs(aimed[0]) < 1e-9 and abs(aimed[1] - 1.5) < 1e-9, aimed
    assert turned[2] == 0.5 + 2.2 and aimed[2] == 0.5 + 0.3, "height must stay an offset"
    print("  ok video matrix: gears resolve off the suite, one column per gear, camera rides the root")


def test_video_matrix_resolves_dynamic_sensor_presets() -> None:
    """V5's dynamically attached head sensor must reach gym as a concrete config."""
    import gymnasium as gym
    from unittest.mock import patch

    import rl_exp.tasks  # noqa: F401
    from ablation_harness import video_matrix

    class CheckedBeforeSimulation(Exception):
        pass

    for gear, suffix in (("plane", "/terrain/GroundPlane/CollisionPlane"), ("rough_b", "/terrain/mesh")):
        def check_config(task, *, cfg, **kwargs):
            assert task == "Lizard2-Flat-Play-v5"
            sensor = cfg.scene.head_ground_contact
            floor = cfg.scene.terrain.prim_path + suffix
            assert sensor.prim_path == "{ENV_REGEX_NS}/Robot/Geometry/neck_pitch"
            assert sensor.filter_prim_paths_expr == [floor]
            assert cfg.terminations.head_ground_contact.params["floor_prim_path"] == floor
            assert cfg.terminations.head_ground_contact.params["dwell_s"] == 0.5
            raise CheckedBeforeSimulation

        args = video_matrix.build_parser().parse_args(["--task", "Lizard2-Flat-Play-v5"])
        with patch.object(gym, "make", side_effect=check_config):
            try:
                video_matrix.record_cell({"speed": 1.5, "terrain": gear}, args)
            except CheckedBeforeSimulation:
                pass
            else:
                raise AssertionError("record_cell did not construct the requested task")


def test_eval_resolves_dynamic_sensor_presets() -> None:
    import argparse
    import ast
    import importlib.metadata
    from unittest.mock import patch

    import gymnasium as gym
    from isaaclab.sensors import SensorBaseCfg
    from isaaclab.utils.string import string_to_callable
    from isaaclab_rl.rsl_rl import handle_deprecated_rsl_rl_cfg
    from isaaclab_tasks.utils.hydra import resolve_presets
    import yaml

    import rl_exp.tasks  # noqa: F401
    from ablation_harness import suites
    from ablation_harness.components.dr_controller import apply_eval_mode

    source = (_REPO / "ablation_harness" / "eval.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_prepare_env")
    namespace = {
        "gym": gym, "args_cli": argparse.Namespace(task="Lizard2-Flat-v6", envs_per_terrain=None,
                                                  seed=123, device=None, mode="nominal"),
        "string_to_callable": string_to_callable, "resolve_presets": resolve_presets,
        "handle_deprecated_rsl_rl_cfg": handle_deprecated_rsl_rl_cfg,
        "importlib": importlib, "suites": suites,
        "_SUITE_REGISTRY": {"lizard_suite_v2": (None, suites.lizard_suite_v2)},
        "apply_eval_mode": apply_eval_mode,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "eval.py", "exec"), namespace)
    protocol = yaml.safe_load((_REPO / "ablation_harness" / "protocols" / "locomotion_eval_v3.yaml").read_text())
    with patch.object(importlib.metadata, "version", return_value="5.0.1"):
        env_cfg, _, _ = namespace["_prepare_env"](protocol)
    assert isinstance(env_cfg.scene.head_ground_contact, SensorBaseCfg)
    floor = env_cfg.scene.terrain.prim_path + "/terrain/mesh"
    assert env_cfg.scene.head_ground_contact.filter_prim_paths_expr == [floor]
    assert env_cfg.terminations.head_ground_contact.params["floor_prim_path"] == floor
    env_cfg.scene.terrain.prim_path = "/World/custom"
    suites.bind_head_ground_to_terrain(env_cfg)
    assert env_cfg.scene.head_ground_contact.filter_prim_paths_expr == ["/World/custom/terrain/mesh"]
    assert env_cfg.terminations.head_ground_contact.params["floor_prim_path"] == "/World/custom/terrain/mesh"
    env_cfg.scene.terrain.terrain_type = "usd"
    try:
        suites.bind_head_ground_to_terrain(env_cfg)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown terrain cannot be silently bound to a guessed collider")


def _main() -> None:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"[OK] {fn.__name__}")
    print(f"test_terrain_geometry: {len(tests)} passed")


if __name__ == "__main__":
    _main()
