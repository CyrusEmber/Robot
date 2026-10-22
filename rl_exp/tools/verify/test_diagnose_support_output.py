# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Run production main/writers in tempfile; replace simulation and collected data only."""

import ast
import builtins
from contextlib import redirect_stdout
from contextlib import redirect_stderr
from contextlib import ExitStack
from dataclasses import dataclass
import datetime
import getpass
import io
import json
import math
import os
from pathlib import Path
import tempfile
import sys
import traceback
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch


_TOOL = Path(__file__).resolve().parents[1] / "diagnose/diagnose_support.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file
sys.path.insert(0, str(_TOOL.parent))
sys.path.insert(0, str(_TOOL.parents[1] / "verify"))
from artifact_paths import ArtifactPaths, _relative, _unlinked
from artifact_run import ArtifactRun, inspect_run
import cfg_snapshot
import support_native_ab


@dataclass(init=False)
class Config(NS):
    """Fixture with the same snapshot traversal contract as framework configs."""


class SimValue:
    """Minimal stand-in for tensor readings used during simulation setup."""

    def __getitem__(self, key):
        return self

    def sum(self, *args, **kwargs):
        return self

    def mean(self, *args, **kwargs):
        return self

    def item(self):
        return 1.0

    def tolist(self):
        return [1.0] * 4

    def to(self, device):
        return self


class OutputTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.out = self.repo / "rl_exp/tools/diagnose/out/same_label"
        asset = self.repo / "rl_exp/assets/fixture"
        asset.mkdir(parents=True)
        for name in ("body.urdf", "body.usda", "mesh.obj", "params.yaml", "checkpoint.pt"):
            (asset / name).write_bytes(b"bound fixture bytes")
        self.index = self.repo / "rl_exp/tools/diagnose/artifact_index.json"
        self.index.parent.mkdir(parents=True, exist_ok=True)
        self.index.write_text(json.dumps({"format": 1, "packages": []}))
        for name in ("recipes.json", "obs_protocols.json", "obs_protocol_anchors.json", "joint_order_runtime.json",
                     "fixture/assets.json"):
            declaration = self.repo / "rl_exp/versions" / name
            declaration.parent.mkdir(parents=True, exist_ok=True)
            declaration.write_text("{}")
        self.args = NS(heights="0.05", phases="0,1", speeds="0.3", label="same_label",
                       task="offline-fixture", base_seed=1000, device=None,
                       target_config=None, naming=None, checkpoint=str(asset / "checkpoint.pt"), reps=1,
                       approach=0.3)
        tensor = SimValue()
        robot = NS(body_names=["base_link"],
                   find_bodies=lambda *a, **k: ([0], ["base_link"]),
                   find_joints=lambda *a, **k: ([0], ["tail_joint"]),
                   data=NS(body_quat_w=NS(torch=tensor), root_pos_w=NS(torch=tensor),
                           body_mass=NS(torch=tensor)))
        sensor = NS(body_names=["base_link"],
                    find_sensors=lambda *a, **k: ([0], ["base_link"]),
                    data=NS(net_forces_w=NS(torch=tensor)))

        class Scene(dict):
            sensors = {"contact_forces": sensor}

        env = NS(scene=Scene(robot=robot), device="cpu", step_dt=0.02, num_envs=1,
                 action_manager=NS(total_action_dim=1),
                 command_manager=NS(get_term=lambda name: None),
                 reward_manager=NS(_term_names=[]))
        gym_env = NS(unwrapped=env, close=Mock())
        self.gym_env = gym_env
        wrapper = NS(reset=lambda: None, step=lambda action: (None, None, None, None))
        cfg = Config(scene=Config(replicate_physics=True), curriculum=NS(), sim=NS(),
                 events=NS(reset_base=NS(params={"pose_range": {}})))
        agent = NS(device="cpu", to_dict=lambda: {})
        lc = {"sum_all_ratio": 1.0, "residual_n": 0.0, "a_z_equiv_mps2": 0.0,
              "dv_z_window_mps": 0.0, "momentum_can_explain": False, "non_foot_top": []}
        stats = dict.fromkeys(("max_tilt_deg", "min_clearance", "drift_m", "max_belly_fz_n",
                               "feet_down_mean", "feet_down_min", "lift_frac", "air_frac"), 0.0)
        stats.update(load_closure=lc, foot_z_min=[0.0] * 4, foot_load_frac=[0.25] * 4,
                     foot_names=["rr", "rl", "rf", "lf"], fell=False)
        binding = {"target": str(asset / "body.usda"), "urdf": str(asset / "body.urdf"),
                   "source": str(asset / "params.yaml")}
        self.terrain = Mock(return_value=(None, ["flat"]))
        self.rollout = Mock(return_value={"sample": "collected fixture"})
        self.measure = Mock(side_effect=lambda *a, **k: {
            "load_closure": dict(lc), "mesh_min_z_m": {"base_link": 0.0},
            "tail_joint_pos_rad": [0.0], "target_binding": binding})
        self.namespace = {
            "_REPO_ROOT": self.repo, "args_cli": self.args, "pathlib": __import__("pathlib"),
            "datetime": datetime, "json": json, "math": math,
            "__file__": str(_TOOL), "sys": sys, "getpass": getpass, "ExitStack": ExitStack,
            "traceback": traceback,
            "ArtifactPaths": ArtifactPaths, "ArtifactRun": ArtifactRun, "cfg_snapshot": cfg_snapshot,
            "_relative": _relative, "_unlinked": _unlinked,
            "build_terrain": self.terrain,
            "gym": NS(spec=lambda task: NS(kwargs={"env_cfg_entry_point": "env",
                                                      "rsl_rl_cfg_entry_point": "agent"}),
                      make=lambda *a, **k: gym_env),
            "string_to_callable": lambda entry: lambda: cfg if entry == "env" else agent,
            "apply_eval_mode": lambda *a: None,
            "obs_protocol": NS(load_diagnostic_target=lambda *a, **k: binding,
                               family_of=lambda task: "fixture",
                               resolve_body=lambda *a: {"refs": [asset / "mesh.obj"]}),
            "joint_names": NS(naming_from_binding=lambda binding: "fixture"),
            "collision_assets": lambda path: ({"base_link": path}, None),
            "RslRlVecEnvWrapper": lambda env: wrapper,
            "SPINE_BODIES": [], "MESH_POINT_BODIES": [], "TAIL_PITCH_JOINTS": [],
            "_select_contacts": lambda *a: ([0], ["rr", "rl", "rf", "lf"], [0], [0]),
            "importlib": NS(metadata=NS(version=lambda package: "unused")),
            "handle_deprecated_rsl_rl_cfg": lambda cfg, version: cfg,
            "OnPolicyRunner": lambda *a, **k: NS(load=lambda path: None,
                                                 get_inference_policy=lambda **k: None),
            "mesh_vertices": lambda *a: tensor, "_pad_clouds": lambda clouds: tensor,
            "torch": NS(zeros=lambda *a, **k: tensor), "GRAVITY": 9.81, "LEDGER_KEYS": (),
            "measure_check": self.measure, "run_case": self.rollout,
            "analyze_stand": lambda *a: dict(stats),
            "series_to_json": lambda res, columns: {
                "columns": columns, "series": {name: {"sample": [1.0, 2.0]} for name in columns}},
        }
        # Execute whole production main unchanged, including mkdir, open, json.dump and summary.
        # Top-level CLI/AppLauncher and simulation imports are never executed.
        tree = ast.parse(_TOOL.read_text(encoding="utf-8"), filename=str(_TOOL))
        nodes = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                 and node.name in {"Case", "_cases", "_support_metadata", "_run_session", "main", "_run_cli", "_wiring_request"}]
        self.assertTrue({"Case", "_cases", "_support_metadata", "_run_session", "main", "_run_cli"}
                        <= {node.name for node in nodes})
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(_TOOL), "exec"), self.namespace)

    def run_main(self):
        with redirect_stdout(io.StringIO()):
            self.namespace["main"]()

    def test_wiring_collects_once_without_policy_or_warmup(self):
        self.args.wiring_steps = 2
        self.args.phases, self.args.heights = "0", ""
        self.args.checkpoint = None
        self.args.target_config = str(self.repo / "rl_exp/assets/fixture/params.yaml")
        self.namespace["OnPolicyRunner"] = Mock(side_effect=AssertionError("policy must not load"))
        self.run_main()
        self.measure.assert_called_once()
        self.assertEqual(self.measure.call_args.kwargs, {"seconds": 0.04, "zero_action": True})
        report = json.loads((self.out / "p0_measure_check.json").read_text())
        self.assertEqual(report["wiring"]["env_steps"], 2)
        self.assertEqual(report["wiring"]["action"], "zero")
        self.assertNotIn("zero_action", report, "do not relabel one window as two independent samples")
        self.namespace["OnPolicyRunner"].assert_not_called()
        self.gym_env.close.assert_called_once()
        record = json.loads((self.out / "run.json").read_text())
        self.assertEqual(record["state"], "completed")
        self.assertEqual(record["config"]["wiring_steps"], 2)
        self.assertFalse(any(row["identity"].endswith("checkpoint.pt") for row in record["inputs"]))

    def test_wiring_rejects_unbounded_or_policy_requests(self):
        validate = self.namespace["_wiring_request"]
        self.assertIsNone(validate(self.args))
        self.args.wiring_steps = 2
        for changes in ({}, {"checkpoint": None}, {"checkpoint": None, "target_config": "manifest"},
                        {"checkpoint": None, "target_config": "manifest", "phases": "0"}):
            request = NS(**(vars(self.args) | changes))
            with self.assertRaises(ValueError):
                validate(request)
        valid = vars(self.args) | {"checkpoint": None, "target_config": "manifest", "phases": "0", "heights": ""}
        self.assertEqual(validate(NS(**valid)), 2)
        for budget in (0, -1, 3):
            with self.assertRaises(ValueError):
                validate(NS(**(valid | {"wiring_steps": budget})))
        with self.assertRaises(ValueError):
            validate(NS(checkpoint=None, wiring_steps=None))

    def snapshot(self):
        files = {path.relative_to(self.out).as_posix(): path.read_bytes()
                 for path in self.out.rglob("*") if path.is_file()}
        digests = {name: sha256_file(self.out / name) for name in files}
        return files, len(files), digests

    def assert_duplicate_preserved(self):
        before = self.snapshot()
        terrain_calls = self.terrain.call_count
        with self.assertRaises(FileExistsError) as raised:
            self.run_main()
        self.assertEqual(Path(raised.exception.filename), self.out)
        self.assertEqual(self.snapshot(), before, "old bytes, file count or SHA-256 changed")
        self.assertEqual(self.terrain.call_count, terrain_calls, "must reject before simulation setup")

    def test_first_write_then_same_label_rejected(self):
        self.run_main()
        files, count, _ = self.snapshot()
        self.assertEqual(set(files), {"p0_measure_check.json", "p1a_zero_action_5s.json",
                                     "p1b_policy_still_10s.json", "summary.md", "run.json"})
        self.assertEqual(count, 5)
        report = json.loads(files["p1a_zero_action_5s.json"])
        self.assertEqual(report["case"], "p1a_zero_action_5s")
        self.assertEqual(report["series_json"],
                         {"columns": ["flat"], "series": {"flat": {"sample": [1.0, 2.0]}}})
        self.assertEqual(report["stats"]["flat"]["foot_load_frac"], [0.25] * 4)
        measure = json.loads(files["p0_measure_check.json"])
        self.assertIn("zero_action", measure)
        self.assertIn("target_binding", measure)
        summary = files["summary.md"].decode("utf-8")
        self.assertIn("## Phase 1", summary)
        self.assertIn("| p1a_zero_action_5s |", summary)
        self.assertIn("| p1b_policy_still_10s |", summary)
        self.assertEqual(self.rollout.call_count, 2)
        self.assertEqual(self.measure.call_count, 2)
        self.assert_duplicate_preserved()

    def test_injected_old_case_and_summary_bytes_preserved(self):
        self.out.mkdir(parents=True)
        for name in ("p0_measure_check.json", "p1a_zero_action_5s.json", "summary.md"):
            (self.out / name).write_bytes(b"old evidence: " + name.encode() + b"\x00\xff\r\n")
        extra = self.out / "nested/unrelated.bin"
        extra.parent.mkdir()
        extra.write_bytes(bytes(range(256)))
        self.assert_duplicate_preserved()
        self.rollout.assert_not_called()
        self.measure.assert_not_called()

    def test_phase_zero_only_repeat_preserved(self):
        self.args.phases = "0"
        self.run_main()
        self.assertEqual(set(self.snapshot()[0]), {"p0_measure_check.json", "run.json"})
        self.assert_duplicate_preserved()

    def test_existing_empty_directory_rejected(self):
        self.out.mkdir(parents=True)
        self.assert_duplicate_preserved()

    def test_run_is_registered_before_measurement_and_finishes(self):
        original = self.measure.side_effect

        def measured(*args, **kwargs):
            path = self.out / "run.json"
            self.assertTrue(path.is_file(), "measurement reached before ownership record")
            self.assertEqual(json.loads(path.read_text())["state"], "running")
            index = self.repo / "rl_exp/tools/diagnose/artifact_index.json"
            entries = json.loads(index.read_text())["packages"]
            expected = "rl_exp/tools/diagnose/out/same_label/run.json"
            self.assertTrue(any(row.get("run_record") == expected for row in entries))
            return original(*args, **kwargs)

        self.measure.side_effect = measured
        self.run_main()
        record = json.loads((self.out / "run.json").read_text())
        self.assertEqual(record["state"], "completed")
        self.assertTrue(record["owner"])
        self.assertTrue(record["inputs"])
        self.assertTrue(record["code"])
        self.assertIn("summary.md", record["outputs"])
        self.assertEqual(inspect_run(self.out, ArtifactPaths(self.index, self.repo))["state"], "completed")

    def test_partial_report_failure_retains_owned_scene(self):
        self.rollout.side_effect = OSError("injected case collection failure")
        with self.assertRaisesRegex(OSError, "injected case collection failure"):
            self.run_main()
        self.assertTrue((self.out / "p0_measure_check.json").is_file())
        self.assertFalse((self.out / "summary.md").exists())
        record = json.loads((self.out / "run.json").read_text())
        self.assertEqual(record["state"], "failed")
        self.assertTrue(record["owner"])
        self.assertTrue(record["next"])

    def test_phase_zero_return_finishes_record(self):
        self.args.phases = "0"
        self.run_main()
        record = json.loads((self.out / "run.json").read_text())
        self.assertEqual(record["state"], "completed")
        self.assertIn("p0_measure_check.json", record["outputs"])
        self.assertNotIn("summary.md", record["required_outputs"])

    def test_registration_failure_prevents_case_writes(self):
        raw_replace = os.replace

        def failed(source, destination, *args, **kwargs):
            if Path(destination).name == "artifact_index.json":
                raise OSError("injected support registration failure")
            return raw_replace(source, destination, *args, **kwargs)

        with patch.object(os, "replace", failed):
            with self.assertRaisesRegex(OSError, "injected support registration failure"):
                self.run_main()
        self.assertFalse((self.out / "p0_measure_check.json").exists())
        self.assertFalse((self.out / "summary.md").exists())
        self.measure.assert_not_called()

    def test_summary_write_failure_keeps_case_reports_and_closes_environment(self):
        raw_open = builtins.open

        def failed(path, *args, **kwargs):
            if not isinstance(path, int) and Path(path) == self.out / "summary.md":
                raise OSError("injected summary writer failure")
            return raw_open(path, *args, **kwargs)

        with patch.object(builtins, "open", failed):
            with self.assertRaisesRegex(OSError, "injected summary writer failure"):
                self.run_main()
        for name in ("p0_measure_check.json", "p1a_zero_action_5s.json", "p1b_policy_still_10s.json"):
            self.assertTrue((self.out / name).is_file())
        record = json.loads((self.out / "run.json").read_text())
        self.assertEqual(record["state"], "failed")
        self.assertTrue(record["next"])
        self.gym_env.close.assert_called_once()

    def test_virtual_relative_module_filename_is_not_a_repository_source(self):
        with patch.dict(sys.modules, {"support_virtual_module": NS(__file__="_classes.py")}):
            self.run_main()
        record = json.loads((self.out / "run.json").read_text())
        self.assertEqual(record["state"], "completed")
        self.assertFalse(any(Path(row["location"]).name == "_classes.py" for row in record["code"]))

    def test_missing_absolute_repository_source_is_rejected(self):
        missing = _TOOL.parents[3] / "missing-runtime-source.py"
        with patch.dict(sys.modules, {"support_missing_module": NS(__file__=str(missing))}):
            with self.assertRaisesRegex(ValueError, "unreadable artifact"):
                self.run_main()
        self.assertFalse(self.out.exists())

    def test_native_shutdown_receives_failure_exit_code(self):
        def close(*, exit_code=0):
            raise SystemExit(exit_code)

        self.namespace["main"] = Mock(side_effect=ValueError("producer error before record"))
        self.namespace["simulation_app"] = NS(close=Mock(side_effect=close))
        errors = io.StringIO()
        with redirect_stderr(errors):
            with self.assertRaises(SystemExit) as raised:
                self.namespace["_run_cli"]()
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("producer error before record", errors.getvalue())

    def test_cli_prints_units_with_a_legacy_gbk_stdout(self):
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="gbk")
        self.namespace["main"] = lambda: print("m/s\u00b2")
        self.namespace["simulation_app"] = NS(close=Mock())
        with redirect_stdout(output):
            self.namespace["_run_cli"]()
        output.flush()
        self.assertEqual(raw.getvalue().decode("utf-8").splitlines(), ["m/s\u00b2"])
        self.namespace["simulation_app"].close.assert_called_once_with(exit_code=0)

    def test_explicit_empty_heights_selects_flat_only(self):
        self.args.heights = ""
        with patch.object(sys, "argv", [str(_TOOL), "--heights", ""]):
            self.run_main()
        self.terrain.assert_called_once_with([])

    def test_phase_three_requires_a_step_height(self):
        self.args.heights = ""
        self.args.phases = "3"
        with self.assertRaisesRegex(ValueError, "step height"):
            self.run_main()
        self.assertFalse(self.out.exists())

    def test_phase_three_finishes_step_summary_and_closes(self):
        self.args.phases = "3"
        self.args.heights = "0.05,0.10"
        columns = ["flat", "up_5", "down_5", "up_10", "down_10"]
        self.terrain.return_value = (None, columns)
        self.namespace["analyze_flat"] = lambda *a: {}
        self.namespace["analyze_step"] = lambda *a: {
            "progress_m": 4.5, "crossed": True, "belly_contact_s": 0.0,
            "fwd_speed_during_belly": None, "spine_bodies_touched": []}

        self.run_main()

        self.terrain.assert_called_once_with([0.05, 0.10])
        summary = (self.out / "summary.md").read_text(encoding="utf-8")
        for height in (5, 10):
            for direction in ("up", "down"):
                self.assertIn(f"| {height}cm | {direction} | 4.5 | 1/1 |", summary)
        case = json.loads((self.out / "p3_steps_r0.json").read_text())
        self.assertEqual(set(case["stats"]), set(columns))
        self.assertEqual(case["series_json"]["columns"], columns)
        self.assertEqual(set(case["series_json"]["series"]), set(columns))
        self.assertEqual(inspect_run(self.out, ArtifactPaths(self.index, self.repo))["state"], "completed")
        self.gym_env.close.assert_called_once()

    def test_multienvironment_uses_independent_physics_parsing(self):
        columns = ["flat", "up_5", "down_5"]
        self.terrain.return_value = (None, columns)
        original_make = self.namespace["gym"].make
        configurations = []

        def make(task, *, cfg):
            configurations.append(cfg)
            self.assertEqual(cfg.scene.num_envs, len(columns))
            self.assertFalse(cfg.scene.replicate_physics,
                             "support diagnostics must not enter the crashing native replicator")
            return original_make(task, cfg=cfg)

        self.namespace["gym"].make = make
        self.run_main()
        self.assertEqual(len(configurations), 1)
        case = json.loads((self.out / "p1a_zero_action_5s.json").read_text())
        self.assertEqual(set(case["stats"]), set(columns))
        self.assertEqual(case["series_json"]["columns"], columns)
        self.assertEqual(set(case["series_json"]["series"]), set(columns))
        record = json.loads((self.out / "run.json").read_text())
        self.assertIs(record["config"]["env"]["scene"]["replicate_physics"], False)
        self.assertEqual(record["state"], "completed")
        self.gym_env.close.assert_called_once()

    def test_phase_two_summary_columns_match_metric_meanings(self):
        self.args.phases = "2"
        metrics = {
            "fwd_yaw_mean": 1.1, "overshoot_frac": 2.2, "overshoot_abs_frac": 3.3,
            "fwd_mae_mps": 4.4, "fwd_speed_std": 5.5, "fwd_speed_mean": 6.6,
            "slip_y_mean": 7.7, "slip_y_abs_mean": 8.8, "yaw_drift_deg": 9.9,
            "turn_rate_deg_s": 10.1, "drift_x_m": 11.2, "drift_y_m": 12.3,
            "crab_deg_mean": 13.4, "v_world_mean": [14.5, 15.6, 16.7],
            "tilt_max_deg": 17.8, "feet_below2_frac": 18.9,
            "foot_duty": [0.1, 0.2, 0.3, 0.4], "foot_load_frac": [0.5, 0.6, 0.7, 0.8],
            "load_closure": {"sum_all_ratio": 19.1, "non_foot_top": []},
            "neck_support_frac": 20.2, "belly_gt10n_frac": 21.3, "ledger": {"term": 22.4}}
        self.namespace["analyze_flat"] = lambda *a: metrics
        self.run_main()

        lines = (self.out / "summary.md").read_text(encoding="utf-8").splitlines()
        header = next(line for line in lines if line.startswith("| case | cmd |"))
        row = next(line for line in lines if line.startswith("| p2_flat_v0.3_r0 |"))
        names = [cell.strip() for cell in header.split("|")[1:-1]]
        values = [cell.strip() for cell in row.split("|")[1:-1]]
        self.assertEqual(len(values), len(names))
        self.assertEqual(dict(zip(names, values)), {
            "case": "p2_flat_v0.3_r0", "cmd": "0.3", "fwd_yaw": "1.1", "overshoot": "2.2",
            "overshoot_abs": "3.3", "fwd_mae": "4.4", "fwd_std": "5.5", "fwd_b": "6.6",
            "slip_y": "7.7", "slip_abs": "8.8", "yaw_drift": "9.9", "turn_rate": "10.1",
            "drift_x": "11.2", "drift_y": "12.3", "crab": "13.4°", "v_world": "[14.5, 15.6, 16.7]",
            "tilt_max": "17.8", "feet<2": "18.9", "foot_duty": "[0.1, 0.2, 0.3, 0.4]",
            "foot_load_frac": "[0.5, 0.6, 0.7, 0.8]", "ΣF_body/mg": "19.1", "非足top3": "",
            "neck_frac": "20.2", "belly_frac": "21.3", "ledger": '{"term": 22.4}'})
        self.assertEqual(inspect_run(self.out, ArtifactPaths(self.index, self.repo))["state"], "completed")


class NativeAbTest(unittest.TestCase):
    def test_archived_binding_survives_live_source_change_but_rejects_wrong_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            executable, snapshot = repo / "driver.py", repo / "archived.py"
            executable.write_bytes(b"exact executed bytes")
            snapshot.write_bytes(executable.read_bytes())
            rows = [{"identity": str(executable), "sha256": sha256_file(executable)}]
            with patch.object(support_native_ab, "REPO", repo):
                snapshot.write_bytes(b"wrong bytes")
                with self.assertRaisesRegex(ValueError, "differs from archived source"):
                    support_native_ab._archive_binding(rows, executable, snapshot)
                snapshot.write_bytes(executable.read_bytes())
                support_native_ab._archive_binding(rows, executable, snapshot)
                executable.write_bytes(b"later implementation")
                support_native_ab._check_bindings(rows, repo)
                self.assertEqual(rows[0]["identity"], str(executable))

    def test_inspect_reclassifies_verified_evidence_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            index = repo / "rl_exp/tools/diagnose/artifact_index.json"
            index.parent.mkdir(parents=True)
            index.write_text(json.dumps({"format": 1, "packages": []}))
            source = repo / "driver.py"
            source.write_bytes(b"bound driver")
            paths = ArtifactPaths(index, repo)
            binding = paths.describe(source)
            root = repo / "rl_exp/tools/diagnose/out/runs/ab"
            metadata = {"topic": "support-native-ab", "work_id": "fixture", "owner": "fixture",
                        "retention_reason": "actual native failure", "command": [sys.executable],
                        "inputs": [binding], "code": [binding]}
            with ArtifactRun(root, paths, metadata, ["report.json"]):
                log = root / "pair3-before.log"
                log.write_text('Windows fatal exception: code 0xc0000374\n'
                               'physx_replicate.py", line 102 in attach_end_fn\n')
                (root / "report.json").write_text(json.dumps({"versions": {"before": {}}, "results": [{
                    "pair": 3, "variant": "before", "outcome": "incomplete", "returncode": 3221226356,
                    "forced_stop": None, "log": log.name, "log_sha256": sha256_file(log),
                    "measurement_sha256": None}]}))
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with patch.object(support_native_ab, "REPO", repo):
                review = support_native_ab.inspect_results(root)
                row = review["results"][0]
                self.assertEqual((row["reported_outcome"], row["reviewed_outcome"], row["exit_hex"]),
                                 ("incomplete", "native_failure", "0xc0000374"))
                self.assertTrue(row["native_replication_frame"])
                self.assertEqual({p: p.read_bytes() for p in before}, before)
                log.write_text("changed log")
                with self.assertRaises(ValueError):
                    support_native_ab.inspect_results(root)

    def test_observed_heap_corruption_after_replication_is_a_native_failure(self):
        # Local reporter pair3-before: access violation followed by 0xc0000374.
        native_log = ('Windows fatal exception: access violation\n'
                      'physx_replicate.py", line 102 in attach_end_fn\n'
                      'Windows fatal exception: code 0xc0000374\n')
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(support_native_ab._classify(
                3221226356, native_log, Path(directory) / "missing.json", None), "native_failure")

    def test_local_reporter_requires_all_four_effective_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {"/crashreporter/enabled": True, "/crashreporter/url": "",
                      "/crashreporter/skipOldDumpUpload": True, "/app/uploadDumpsOnStartup": False}

            def launch(*args, **kwargs):
                (root / "reporter_check.json").write_text(json.dumps(values))
                return NS(poll=lambda: 0, returncode=0, wait=lambda **kwargs: 0)

            with patch.object(support_native_ab.subprocess, "Popen", side_effect=launch):
                self.assertEqual(support_native_ab._reporter_check(root, {}, ""), values)
                for setting, invalid in (("/crashreporter/enabled", False), ("/crashreporter/url", "upload"),
                                         ("/crashreporter/skipOldDumpUpload", False),
                                         ("/app/uploadDumpsOnStartup", True)):
                    with self.subTest(setting=setting):
                        original = values[setting]
                        values[setting] = invalid
                        with self.assertRaisesRegex(ValueError, "restrictions did not take effect"):
                            support_native_ab._reporter_check(root, {}, "")
                        values[setting] = original

    def test_masked_failure_native_exit_and_missing_measurement_are_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            measurement = Path(directory) / "p0.json"
            classify = support_native_ab._classify
            self.assertEqual(classify(0, "", measurement, None), "incomplete")
            measurement.write_text(json.dumps({"zero_action": {}, "target_binding": {}}))
            self.assertEqual(classify(0, "", measurement, None), "completed")
            self.assertEqual(classify(0, "Windows fatal exception: access violation", measurement, None),
                             "completed_with_native_exception_log")
            self.assertEqual(classify(0, "Traceback (most recent call last):", measurement, None), "python_failure")
            self.assertEqual(classify(-1073741819, "", measurement, None), "native_access_violation")
            self.assertEqual(classify(1, "Windows fatal exception: access violation", measurement,
                                      "deadline"), "native_exception_timeout")
            self.assertEqual(classify(1, "", measurement, "deadline"), "timeout")

    def test_environment_comparison_detects_changes_despite_agent_construction_order(self):
        before = b'''def main():
    out_dir = "old"
    terrain_cfg, columns = build_terrain(heights)
    env_cfg.scene.num_envs = len(columns)
    gym_env = gym.make(task, cfg=env_cfg)
    agent_cfg = AgentCfg()
'''
        after = before.replace(b'"old"', b'"new"').replace(
            b'    gym_env = gym.make(task, cfg=env_cfg)\n    agent_cfg = AgentCfg()',
            b'    agent_cfg = AgentCfg()\n    gym_env = gym.make(task, cfg=env_cfg)')
        compare = support_native_ab._environment_setup
        self.assertEqual(compare(before), compare(after))
        self.assertNotEqual(compare(before), compare(after.replace(b'len(columns)', b'1')))

    def test_trial_applies_no_upload_controls_and_preserves_actual_source_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            root = repo / "rl_exp/tools/diagnose/out/runs/ab"
            root.mkdir(parents=True)
            snapshot = root / "source.py"
            snapshot.write_bytes(b"historical source")
            executable = repo / "rl_exp/tools/diagnose/_tmp_fixture.py"
            executable.write_bytes(snapshot.read_bytes())
            captured = {}

            def launch(command, **kwargs):
                captured.update(command=command, environment=kwargs["env"])
                case = root / "cases/pair0-after"
                case.mkdir(parents=True)
                (case / "p0_measure_check.json").write_text(
                    json.dumps({"zero_action": {}, "target_binding": {}}))
                (case / "run.json").write_text(json.dumps({
                    "config": {"env": {"scene": {"replicate_physics": True}}},
                    "code": [{"identity": str(executable), "sha256": sha256_file(snapshot)}],
                    "command": ["python", "wrong-live-source"]}))
                return NS(poll=lambda: 0, returncode=0)

            with patch.object(support_native_ab, "REPO", repo), \
                    patch.object(support_native_ab, "venv_python", return_value="configured-python"), \
                    patch.object(support_native_ab.subprocess, "Popen", side_effect=launch), \
                    redirect_stdout(io.StringIO()):
                result = support_native_ab._trial(root, "after", 0, 7, snapshot, executable,
                                                 {"rows": [], "checkpoint": "checkpoint.pt"}, 30)
            self.assertEqual(result["outcome"], "completed")
            self.assertEqual(captured["environment"]["OMNI_CRASHREPORTER_ENABLED"], "0")
            self.assertEqual(captured["environment"]["OMNI_CRASHREPORTER_SKIPOLDDUMPUPLOAD"], "1")
            self.assertEqual(captured["environment"]["PYTHONHASHSEED"], "7")
            self.assertEqual(captured["command"][0], "configured-python")
            kit_args = captured["command"][captured["command"].index("--kit_args") + 1]
            self.assertIn("--/app/uploadDumpsOnStartup=false", kit_args)
            record = json.loads((root / "cases/pair0-after/run.json").read_text())
            self.assertEqual(record["command"], captured["command"])
            self.assertEqual(record["code"][0]["location"], snapshot.relative_to(repo).as_posix())
            self.assertEqual(record["comparison"]["restore_script_to"], str(executable))


if __name__ == "__main__":
    unittest.main(verbosity=2)
