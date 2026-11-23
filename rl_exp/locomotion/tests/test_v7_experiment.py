# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Checks for the explicit v7 experiment and checkpoint interface."""

from importlib.util import find_spec
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest

from ablation_harness.components.dr_controller import apply_eval_mode
from ablation_harness import experiment_eval
from ablation_harness.experiment_eval import check_signature, resolved_config
from rl_exp import lizard2_v7
from rl_exp.locomotion.train_record import asset_fingerprints, interface_signature

ROOT = Path(__file__).resolve().parents[3]


def test_eval_uses_workspace_experiment_and_checks_run_assets(tmp_path, monkeypatch):
    checkpoint = tmp_path / "model_0.pt"
    checkpoint.touch()
    experiment = ROOT / "rl_exp/lizard2_v7.py"
    copy = tmp_path / "v7_at_training.py"
    copy.write_text("# experiment at training time\n", encoding="utf-8")
    provenance = {"experiment": {"repo_path": "rl_exp/lizard2_v7.py", "copy": copy.name},
                  "assets": {"usd": {"sha256": "recorded"}}}
    (tmp_path / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")

    files = experiment_eval.experiment_files(checkpoint, None)
    assert files[0] == experiment.resolve()
    source = experiment_eval.experiment_source(checkpoint, files)
    assert source["path"] == str(experiment.resolve())
    assert source["matches_run_copy"] is False

    monkeypatch.setattr(experiment_eval, "asset_fingerprints", lambda *_: {"usd": {"sha256": "changed"}})
    for explicit in (None, experiment):
        with pytest.raises(ValueError, match="USD sha256 differs from the training Run"):
            experiment_eval.configurations(experiment_eval.experiment_files(checkpoint, explicit))


def test_v7_modes():
    train = lizard2_v7.make_env_cfg()
    play = lizard2_v7.make_env_cfg(play=True)
    assert train.scene.num_envs == 4096
    assert play.scene.num_envs == 50
    assert train.scene.robot.spawn.usd_path == str(lizard2_v7.lizard2_round_feet.USD_PATH)
    body = ElementTree.parse(lizard2_v7.URDF_PATH)
    movable = {joint.get("name") for joint in body.findall("joint") if joint.get("type") != "fixed"}
    leg_joints = train.actions.joint_pos_legs.joint_names
    spine_joints = train.actions.joint_pos_spine.joint_names
    assert len(movable) == 26
    assert set(leg_joints + spine_joints) == movable
    assert not train.observations.policy.enable_corruption
    assert not play.observations.policy.enable_corruption
    assert [train.observations.policy.joint_vel.noise.n_min, train.observations.policy.joint_vel.noise.n_max] == [-1.5, 1.5]
    apply_eval_mode(train, "robust")
    assert train.observations.policy.enable_corruption
    apply_eval_mode(train, "nominal")
    assert not train.observations.policy.enable_corruption


def test_signature_rejects_same_width_reorder():
    entity = SimpleNamespace(name="robot", joint_ids=[0, 1])
    policy = SimpleNamespace(joint_pos=SimpleNamespace(params={"asset_cfg": entity}))
    obs = SimpleNamespace(cfg=SimpleNamespace(policy=policy), active_terms={"policy": ["joint_pos"]},
                          group_obs_term_dim={"policy": [(2,)]})
    joints = SimpleNamespace(joint_names=["left", "right"])
    terms = {"joints": SimpleNamespace(action_dim=2, IO_descriptor=joints), "other": SimpleNamespace(action_dim=1)}
    actions = SimpleNamespace(active_terms=list(terms), get_term=terms.__getitem__, total_action_dim=3)
    env = SimpleNamespace(observation_manager=obs, action_manager=actions,
                          scene={"robot": SimpleNamespace(joint_names=["left", "right"])})
    original = interface_signature(env)
    check_signature(original, interface_signature(env))
    entity.joint_ids.reverse()
    with pytest.raises(ValueError, match=r"observations\[0\]\.terms\[0\]\.joints\[0\]"):
        check_signature(original, interface_signature(env))
    entity.joint_ids.reverse()
    joints.joint_names.reverse()
    with pytest.raises(ValueError, match=r"actions\[0\]\.joints\[0\]"):
        check_signature(original, interface_signature(env))
    joints.joint_names.pop()
    original["actions"][0]["joints"].reverse()
    with pytest.raises(ValueError, match=r"actions\[0\]\.joints\[1\].*length"):
        check_signature(original, interface_signature(env))


def test_asset_fingerprints_follow_meshes(tmp_path, monkeypatch):
    usd = tmp_path / "robot.usda"
    layer = tmp_path / "geometry.usda"
    urdf = tmp_path / "robot.urdf"
    mesh = tmp_path / "foot.obj"
    usd.write_text("#usda 1.0\n", encoding="utf-8")
    layer.write_text("#usda 1.0\n", encoding="utf-8")
    urdf.write_text('<robot><mesh filename="foot.obj"/></robot>', encoding="utf-8")
    mesh.write_text("v 0 0 0\n", encoding="utf-8")
    usd_utils = SimpleNamespace(ComputeAllDependencies=lambda _: ([SimpleNamespace(realPath=str(layer))], [], []))
    monkeypatch.setitem(sys.modules, "pxr", SimpleNamespace(UsdUtils=usd_utils))

    actual = asset_fingerprints(str(usd), urdf)
    assert set(actual["usd"]["dependencies"]) == {"geometry.usda"}
    assert set(actual["urdf"]["dependencies"]) == {"foot.obj"}
    mesh.write_text("v 0 0 1\n", encoding="utf-8")
    assert asset_fingerprints(str(usd), urdf)["urdf"]["dependencies"] != actual["urdf"]["dependencies"]
    mesh.unlink()
    with pytest.raises(FileNotFoundError, match="foot.obj"):
        asset_fingerprints(str(usd), urdf)


@pytest.mark.skipif(find_spec("isaacsim") is None, reason="This smoke test needs Isaac Sim")
def test_one_ppo_update_and_reload(tmp_path):
    run = tmp_path / "run"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    train = subprocess.run(
        [sys.executable, "-m", "rl_exp.locomotion.train", "--exp", "rl_exp/lizard2_v7.py", "--train-only",
         "--num-envs", "4", "--max-iterations", "1", "--seed", "123", "--viz", "none", "--run-dir", str(run)],
        cwd=ROOT, env=env, capture_output=True, text=True, errors="replace", timeout=180,
    )
    assert train.returncode == 0, train.stdout + train.stderr
    cfg = resolved_config(run / "resolved_cfg.yaml")
    assert (cfg["env"]["seed"], cfg["env"]["scene"]["num_envs"], cfg["runner"]["max_iterations"]) == (123, 4, 1)
    assert list(run.glob("events.out.tfevents.*"))
    assert (run / "git.diff").is_file()

    metrics = tmp_path / "metrics"
    rollout = subprocess.run(
        [sys.executable, "ablation_harness/eval.py", "--ckpt", str(run / "model_0.pt"), "--mode", "robust",
         "--envs_per_terrain", "1", "--viz", "none", "--output-dir", str(metrics)],
        cwd=ROOT, env=env, capture_output=True, text=True, errors="replace", timeout=300,
    )
    assert rollout.returncode == 0, rollout.stdout + rollout.stderr
    report = json.loads((metrics / "eval.json").read_text(encoding="utf-8"))
    assert report["num_envs"] == 9
    assert report["report_only"]["fall_clearance"]["valid_steps"] > 0
    assert all(math.isfinite(value) for value in report["global"].values())
    assert report["conditions"]["experiment"]["matches_run_copy"] is True
    expected = json.loads((run / "interface_signature.json").read_text(encoding="utf-8"))
    assert report["conditions"]["interface_signature"] == expected
