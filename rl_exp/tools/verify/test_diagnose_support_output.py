# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Run production main/writers in tempfile; replace simulation and collected data only."""

import ast
from contextlib import redirect_stdout
import datetime
import io
import json
import math
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock


_TOOL = Path(__file__).resolve().parents[1] / "diagnose/diagnose_support.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file


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
        self.args = NS(heights="0.05", phases="0,1", speeds="0.3", label="same_label",
                       task="offline-fixture", base_seed=1000, device=None,
                       target_config=None, naming=None, checkpoint="unused", reps=1,
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
        wrapper = NS(reset=lambda: None, step=lambda action: (None, None, None, None))
        cfg = NS(scene=NS(), curriculum=NS(), sim=NS(),
                 events=NS(reset_base=NS(params={"pose_range": {}})))
        agent = NS(device="cpu", to_dict=lambda: {})
        lc = {"sum_all_ratio": 1.0, "residual_n": 0.0, "a_z_equiv_mps2": 0.0,
              "dv_z_window_mps": 0.0, "momentum_can_explain": False, "non_foot_top": []}
        stats = dict.fromkeys(("max_tilt_deg", "min_clearance", "drift_m", "max_belly_fz_n",
                               "feet_down_mean", "feet_down_min", "lift_frac", "air_frac"), 0.0)
        stats.update(load_closure=lc, foot_z_min=[0.0] * 4, foot_load_frac=[0.25] * 4,
                     foot_names=["rr", "rl", "rf", "lf"], fell=False)
        binding = {"target": "offline-fixture", "urdf": "unused.urdf"}
        self.terrain = Mock(return_value=(None, ["flat"]))
        self.rollout = Mock(return_value={"sample": "collected fixture"})
        self.measure = Mock(side_effect=lambda *a, **k: {
            "load_closure": dict(lc), "mesh_min_z_m": {"base_link": 0.0},
            "tail_joint_pos_rad": [0.0], "target_binding": binding})
        self.namespace = {
            "_REPO_ROOT": self.repo, "args_cli": self.args, "pathlib": __import__("pathlib"),
            "datetime": datetime, "json": json, "math": math,
            "build_terrain": self.terrain,
            "gym": NS(spec=lambda task: NS(kwargs={"env_cfg_entry_point": "env",
                                                      "rsl_rl_cfg_entry_point": "agent"}),
                      make=lambda *a, **k: gym_env),
            "string_to_callable": lambda entry: lambda: cfg if entry == "env" else agent,
            "apply_eval_mode": lambda *a: None,
            "obs_protocol": NS(load_diagnostic_target=lambda *a, **k: binding),
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
            "series_to_json": lambda res, columns: {"flat": {"sample": [1.0, 2.0]}},
        }
        # Execute whole production main unchanged, including mkdir, open, json.dump and summary.
        # Top-level CLI/AppLauncher and simulation imports are never executed.
        tree = ast.parse(_TOOL.read_text(encoding="utf-8"), filename=str(_TOOL))
        nodes = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in {"Case", "main"}]
        self.assertEqual({node.name for node in nodes}, {"Case", "main"})
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(_TOOL), "exec"), self.namespace)

    def run_main(self):
        with redirect_stdout(io.StringIO()):
            self.namespace["main"]()

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
                                     "p1b_policy_still_10s.json", "summary.md"})
        self.assertEqual(count, 4)
        report = json.loads(files["p1a_zero_action_5s.json"])
        self.assertEqual(report["case"], "p1a_zero_action_5s")
        self.assertEqual(report["series_json"], {"flat": {"sample": [1.0, 2.0]}})
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
        self.assertEqual(set(self.snapshot()[0]), {"p0_measure_check.json"})
        self.assert_duplicate_preserved()

    def test_existing_empty_directory_rejected(self):
        self.out.mkdir(parents=True)
        self.assert_duplicate_preserved()


if __name__ == "__main__":
    unittest.main(verbosity=2)
