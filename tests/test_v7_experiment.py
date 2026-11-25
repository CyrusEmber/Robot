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
from rl_exp.locomotion.run import asset_fingerprints, interface_signature

ROOT = Path(__file__).resolve().parents[1]


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
    assert train.scene.robot.spawn.usd_path == str(lizard2_v7.ROBOT.USD_PATH)
    body = ElementTree.parse(lizard2_v7.ROBOT.URDF_PATH)
    movable = {joint.get("name") for joint in body.findall("joint") if joint.get("type") != "fixed"}
    leg_joints = train.actions.joint_pos_legs.joint_names
    spine_joints = train.actions.joint_pos_spine.joint_names
    assert len(movable) == 26
    assert set(leg_joints + spine_joints) == movable
    assert not train.observations.policy.enable_corruption
    assert not play.observations.policy.enable_corruption
    assert [train.observations.policy.joint_vel.noise.n_min, train.observations.policy.joint_vel.noise.n_max] == [-1.5, 1.5]
    assert list(train.rewards.to_dict()) == [
        "track_ang_vel_z_exp", "lin_vel_z_l2", "dof_torques_l2",
        "action_rate_l2", "track_lin_vel_xy_miki", "belly_contact_force",
    ]
    assert list(train.terminations.to_dict()) == ["time_out", "base_contact", "head_ground_contact"]
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


@pytest.mark.sim
@pytest.mark.skipif(find_spec("isaacsim") is None, reason="This smoke test needs Isaac Sim")
def test_one_ppo_update_and_reload(tmp_path):
    run = tmp_path / "run"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    train = subprocess.run(
        [sys.executable, "-m", "rl_exp.locomotion.train", "--exp", "rl_exp/lizard2_v7.py",
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
    assert report["conditions"]["experiment"]["config_check"]["status"] == "matched"
    expected = json.loads((run / "interface_signature.json").read_text(encoding="utf-8"))
    assert report["conditions"]["interface_signature"] == expected


def test_signature_matches_legacy_v7_sidecar_and_rejects_renamed_joint_obs():
    cfg = lizard2_v7.make_env_cfg()
    # Exact PhysX runtime 26-joint order from the adopted model_5999.pt.interface.json sidecar.
    sidecar_joints = [
        "chest_yaw_joint", "tail1_yaw_joint", "rl_hip_swing_joint", "rr_hip_swing_joint",
        "chest_pitch_joint", "tail1_pitch_joint", "rl_hip_abduct_joint", "rr_hip_abduct_joint",
        "neck_yaw_joint", "lf_shoulder_swing_joint", "rf_shoulder_swing_joint", "tail2_yaw_joint",
        "rl_hip_twist_joint", "rr_hip_twist_joint", "neck_pitch_joint", "lf_shoulder_abduct_joint",
        "rf_shoulder_abduct_joint", "tail2_pitch_joint", "rl_knee_joint", "rr_knee_joint",
        "lf_shoulder_twist_joint", "rf_shoulder_twist_joint", "tail3_yaw_joint", "lf_elbow_joint",
        "rf_elbow_joint", "tail3_pitch_joint",
    ]
    term_names = ["base_lin_vel", "base_ang_vel", "projected_gravity", "velocity_commands",
                  "joint_pos", "joint_vel", "actions"]
    dims = [(3,), (3,), (3,), (3,), (26,), (26,), (26,)]
    obs = SimpleNamespace(cfg=cfg.observations, active_terms={"policy": term_names},
                          group_obs_term_dim={"policy": dims})
    leg = list(lizard2_v7.ROBOT.LEG_ACTION_JOINTS)
    spine = list(lizard2_v7.ROBOT.SPINE_ACTION_JOINTS)
    action_terms = {
        "joint_pos_legs": SimpleNamespace(action_dim=len(leg), IO_descriptor=SimpleNamespace(joint_names=leg)),
        "joint_pos_spine": SimpleNamespace(action_dim=len(spine), IO_descriptor=SimpleNamespace(joint_names=spine)),
    }
    actions = SimpleNamespace(active_terms=list(action_terms), get_term=action_terms.__getitem__, total_action_dim=26)
    env = SimpleNamespace(observation_manager=obs, action_manager=actions,
                          scene={"robot": SimpleNamespace(joint_names=sidecar_joints)})

    actual = interface_signature(env)
    # Match the exact key layout and PhysX joint order in model_5999.pt.interface.json.
    legacy_fixture = {
        "observations": [{
            "name": "policy",
            "terms": [
                {"name": "base_lin_vel", "width": 3},
                {"name": "base_ang_vel", "width": 3},
                {"name": "projected_gravity", "width": 3},
                {"name": "velocity_commands", "width": 3},
                {"name": "joint_pos", "width": 26, "joints": sidecar_joints},
                {"name": "joint_vel", "width": 26, "joints": sidecar_joints},
                {"name": "actions", "width": 26},
            ],
        }],
        "action_dim": 26,
        "actions": [
            {"name": "joint_pos_legs", "width": len(leg), "joints": leg},
            {"name": "joint_pos_spine", "width": len(spine), "joints": spine},
        ],
    }
    check_signature(legacy_fixture, actual)

    # Unresolved asset_cfg with joint_names and joint_ids=None must not fail with TypeError.
    unresolved_entity = SimpleNamespace(name="robot", joint_names=["left", "right"], joint_ids=None)
    unresolved_policy = SimpleNamespace(
        joint_pos_legs=SimpleNamespace(func=lambda env, asset_cfg=None: None, params={"asset_cfg": unresolved_entity})
    )
    unresolved_obs = SimpleNamespace(cfg=SimpleNamespace(policy=unresolved_policy),
                                     active_terms={"policy": ["joint_pos_legs"]},
                                     group_obs_term_dim={"policy": [(2,)]})
    unresolved_env = SimpleNamespace(observation_manager=unresolved_obs, action_manager=actions,
                                     scene={"robot": SimpleNamespace(joint_names=["left", "right"])})
    assert interface_signature(unresolved_env)["observations"][0]["terms"][0]["joints"] == ["left", "right"]

    # Non-standard term name with explicit joint subset must still record and check joint order.
    entity = SimpleNamespace(name="robot", joint_names=["left", "right"], joint_ids=[0, 1])
    renamed_policy = SimpleNamespace(
        joint_pos_legs=SimpleNamespace(func=lambda env, asset_cfg=None: None, params={"asset_cfg": entity})
    )
    renamed_obs = SimpleNamespace(cfg=SimpleNamespace(policy=renamed_policy),
                                  active_terms={"policy": ["joint_pos_legs"]},
                                  group_obs_term_dim={"policy": [(2,)]})
    renamed_env = SimpleNamespace(observation_manager=renamed_obs, action_manager=actions,
                                  scene={"robot": SimpleNamespace(joint_names=["left", "right"])})
    baseline = interface_signature(renamed_env)
    assert baseline["observations"][0]["terms"][0]["joints"] == ["left", "right"]
    entity.joint_ids.reverse()
    with pytest.raises(ValueError, match=r"observations\[0\]\.terms\[0\]\.joints\[0\]"):
        check_signature(baseline, interface_signature(renamed_env))


def test_inference_config_drift_check(tmp_path):
    from isaaclab.utils.io import dump_yaml

    checkpoint = tmp_path / "model_0.pt"
    checkpoint.touch()
    env_cfg = lizard2_v7.make_env_cfg()
    runner_cfg = lizard2_v7.make_runner_cfg()

    # Legacy checkpoint without provenance.json or resolved_cfg.yaml reports unavailable.
    assert experiment_eval.check_inference_config(checkpoint, env_cfg, runner_cfg)["status"] == "unavailable"

    # A new training Run (provenance with experiment) missing resolved_cfg.yaml is refused by default.
    run_prov = {"experiment": {"repo_path": "rl_exp/lizard2_v7.py"}}
    (tmp_path / "provenance.json").write_text(json.dumps(run_prov), encoding="utf-8")
    with pytest.raises(ValueError, match="missing resolved_cfg.yaml"):
        experiment_eval.check_inference_config(checkpoint, env_cfg, runner_cfg)
    missing_allowed = experiment_eval.check_inference_config(checkpoint, env_cfg, runner_cfg, allow_drift=True)
    assert missing_allowed["status"] == "missing" and missing_allowed["allow_drift"] is True

    dump_yaml(str(tmp_path / "resolved_cfg.yaml"), {"env": env_cfg.to_dict(), "runner": runner_cfg.to_dict()})

    # Changing only reward weight passes cleanly.
    reward_only = lizard2_v7.make_env_cfg()
    reward_only.rewards.track_lin_vel_xy_miki.weight = 9.9
    assert experiment_eval.check_inference_config(checkpoint, reward_only, runner_cfg)["status"] == "matched"

    # Changing one joint PD stiffness is refused by default, allowed with --allow-drift.
    pd_drifted = lizard2_v7.make_env_cfg()
    pd_drifted.scene.robot.actuators["legs"].stiffness["lf_elbow_joint"] += 1.0
    with pytest.raises(ValueError, match=r"Training inference config\.robot\.actuators\.legs\.stiffness"):
        experiment_eval.check_inference_config(checkpoint, pd_drifted, runner_cfg)
    allowed_pd = experiment_eval.check_inference_config(checkpoint, pd_drifted, runner_cfg, allow_drift=True)
    assert allowed_pd["status"] == "drifted" and allowed_pd["allow_drift"] is True

    # Changing runner.clip_actions is refused by default, allowed with --allow-drift.
    clip_drifted = lizard2_v7.make_runner_cfg()
    clip_drifted.clip_actions = 1.5
    with pytest.raises(ValueError, match=r"Training inference config\.clip_actions"):
        experiment_eval.check_inference_config(checkpoint, env_cfg, clip_drifted)
    allowed_clip = experiment_eval.check_inference_config(checkpoint, env_cfg, clip_drifted, allow_drift=True)
    assert allowed_clip["status"] == "drifted" and allowed_clip["allow_drift"] is True

    # Changing runner.actor.activation (same weight shapes, different inference outputs) is refused by default.
    act_drifted = lizard2_v7.make_runner_cfg()
    act_drifted.actor.activation = "relu"
    with pytest.raises(ValueError, match=r"Training inference config\.actor\.activation"):
        experiment_eval.check_inference_config(checkpoint, env_cfg, act_drifted)
    allowed_act = experiment_eval.check_inference_config(checkpoint, env_cfg, act_drifted, allow_drift=True)
    assert allowed_act["status"] == "drifted" and allowed_act["allow_drift"] is True


def test_train_failure_exit_and_existing_run_dir(tmp_path):
    # Real subprocess probe: training error returns nonzero and an existing --run-dir fails before AppLauncher.
    stub_exp = tmp_path / "stub_exp.py"
    stub_exp.write_text(
        "from types import SimpleNamespace\n"
        "def make_env_cfg():\n"
        "    return SimpleNamespace(scene=SimpleNamespace(num_envs=1), sim=SimpleNamespace(device='cpu'), "
        "seed=0, log_dir='', validate=lambda: None, to_dict=lambda: {})\n"
        "def make_runner_cfg():\n"
        "    return SimpleNamespace(max_iterations=1, seed=0, clip_actions=None, device='cpu', to_dict=lambda: {})\n",
        encoding="utf-8",
    )
    probe = r'''
import importlib.util, os, pathlib, sys, types
mode, exp_path, run_dir = sys.argv[1:4]
app_mod = types.ModuleType("isaaclab.app")
class AppLauncher:
    @staticmethod
    def add_app_launcher_args(parser): pass
    def __init__(self, args):
        if mode == "existing_dir":
            raise AssertionError("AppLauncher must not start when --run-dir already exists")
        self.device = "cpu"
        self.app = self
    def close(self, exit_code=0):
        os._exit(exit_code)
app_mod.AppLauncher = AppLauncher
io_mod = types.ModuleType("isaaclab.utils.io")
io_mod.dump_yaml = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected train failure"))
envs_mod = types.ModuleType("isaaclab.envs")
envs_mod.ManagerBasedRLEnv = object
rsl_mod = types.ModuleType("isaaclab_rl.rsl_rl")
rsl_mod.handle_deprecated_rsl_rl_cfg = lambda cfg, ver: cfg
rsl_mod.RslRlVecEnvWrapper = object
runners_mod = types.ModuleType("rsl_rl.runners")
runners_mod.OnPolicyRunner = object
sys.modules["isaaclab"] = types.ModuleType("isaaclab")
sys.modules["isaaclab.app"] = app_mod
sys.modules["isaaclab.envs"] = envs_mod
sys.modules["isaaclab.utils"] = types.ModuleType("isaaclab.utils")
sys.modules["isaaclab.utils.io"] = io_mod
sys.modules["isaaclab_rl"] = types.ModuleType("isaaclab_rl")
sys.modules["isaaclab_rl.rsl_rl"] = rsl_mod
sys.modules["rsl_rl"] = types.ModuleType("rsl_rl")
sys.modules["rsl_rl.runners"] = runners_mod
orig_find = importlib.util.find_spec
importlib.util.find_spec = lambda name, pkg=None: object() if name == "isaacsim" else orig_find(name, pkg)
import rl_exp.locomotion.train as train_mod
if mode == "failure":
    sys.argv = ["train", "--exp", exp_path, "--run-dir", run_dir]
elif mode == "existing_dir":
    sys.argv = ["train", "--exp", exp_path, "--run-dir", run_dir]
train_mod.main()
'''
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    fail_run = tmp_path / "fail_run"
    res = subprocess.run([sys.executable, "-c", probe, "failure", str(stub_exp), str(fail_run)],
                         cwd=ROOT, env=env, capture_output=True, text=True, errors="replace")
    assert res.returncode == 1 and "injected train failure" in res.stderr

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    res = subprocess.run([sys.executable, "-c", probe, "existing_dir", str(stub_exp), str(occupied)],
                         cwd=ROOT, env=env, capture_output=True, text=True, errors="replace")
    assert res.returncode != 0 and "FileExistsError" in res.stderr
    assert "AppLauncher must not start" not in res.stderr


@pytest.mark.skipif(os.name != "nt", reason="find_python.cmd is Windows-only")
def test_find_python_cmd_priority_and_yaml_parsing(tmp_path):
    script_dir = tmp_path / "rl_exp" / "locomotion"
    script_dir.mkdir(parents=True)
    script = script_dir / "find_python.cmd"
    script.write_text((ROOT / "rl_exp/locomotion/find_python.cmd").read_text(encoding="utf-8"), encoding="utf-8")

    yaml_py = tmp_path / "yaml_py" / "python.exe"
    rl_py = tmp_path / "rl_py" / "python.exe"
    venv_dir = tmp_path / "other_venv"
    venv_py = venv_dir / "Scripts" / "python.exe"
    for path in (yaml_py, rl_py, venv_py):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"stub")

    probe_cmd = tmp_path / "probe.cmd"
    probe_cmd.write_text(f'@echo off\r\ncall "{script}"\r\nif errorlevel 1 exit /b 1\r\necho %EXP_PYTHON%\r\n',
                         encoding="utf-8")

    def resolve(yaml_text: str, extra_env: dict[str, str]) -> str:
        (tmp_path / "paths.yaml").write_text(yaml_text, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k.upper() not in {"RL_PYTHON", "VIRTUAL_ENV", "EXP_PYTHON"}}
        env.update(extra_env)
        out = subprocess.run(
            ["cmd", "/c", str(probe_cmd)],
            cwd=tmp_path, env=env, capture_output=True, text=True, errors="replace",
        )
        assert out.returncode == 0, out.stdout + out.stderr
        return out.stdout.strip()

    # paths.yaml wins over an unrelated active VIRTUAL_ENV and tolerates spaces, quotes, and comments.
    for line in (
        f"python: {yaml_py.as_posix()}\n",
        f"python : {yaml_py.as_posix()}  # trailing comment\n",
        f"python: '{yaml_py.as_posix()}' # single-quoted\n",
        f'python: "{yaml_py.as_posix()}" # double-quoted\n',
    ):
        assert Path(resolve(f"# python: ignored\n{line}", {"VIRTUAL_ENV": str(venv_dir)})) == yaml_py

    # RL_PYTHON wins over paths.yaml.
    assert Path(resolve(f"python: {yaml_py.as_posix()}\n", {"RL_PYTHON": str(rl_py)})) == rl_py

    # VIRTUAL_ENV is used only when RL_PYTHON and paths.yaml are absent.
    (tmp_path / "paths.yaml").unlink()
    env = {k: v for k, v in os.environ.items() if k.upper() not in {"RL_PYTHON", "VIRTUAL_ENV", "EXP_PYTHON"}}
    env["VIRTUAL_ENV"] = str(venv_dir)
    out = subprocess.run(
        ["cmd", "/c", str(probe_cmd)],
        cwd=tmp_path, env=env, capture_output=True, text=True, errors="replace",
    )
    assert out.returncode == 0 and Path(out.stdout.strip()) == venv_py


def test_swapping_robot_module_rebinds_env_and_scanner(tmp_path, monkeypatch):
    """Replacing exp.ROBOT rebinds robot cfg, actions, sensors, rewards, terminations, and scanner prim."""
    from isaaclab import sim as sim_utils
    from isaaclab.assets import ArticulationCfg

    fake_usd = tmp_path / "alt_robot.usda"
    fake_urdf = tmp_path / "alt_robot.urdf"
    fake_legs = ("alt_leg_a", "alt_leg_b")
    fake_spine = ("alt_spine_a",)

    def fake_make_robot_cfg(prim_path: str = "{ENV_REGEX_NS}/Robot") -> ArticulationCfg:
        return ArticulationCfg(
            prim_path=prim_path,
            spawn=sim_utils.UsdFileCfg(usd_path=str(fake_usd)),
            actuators={},
        )

    fake_robot = SimpleNamespace(
        USD_PATH=fake_usd,
        URDF_PATH=fake_urdf,
        ROOT_BODY_PRIM="Links/alt_pelvis",
        BELLY_BODY="alt_belly",
        CHEST_BODY="alt_thorax",
        HEAD_BODY="alt_skull",
        HEAD_BODY_PRIM="{ENV_REGEX_NS}/Robot/Links/alt_skull",
        NOMINAL_WEIGHT_N=321.5,
        LEG_ACTION_JOINTS=fake_legs,
        SPINE_ACTION_JOINTS=fake_spine,
        ACTION_JOINTS=fake_legs + fake_spine,
        ACTION_SCALE={"alt_leg_a": 0.4, "alt_leg_b": 0.5, "alt_spine_a": 0.1},
        ACTION_CLIP={"alt_leg_a": 1.1, "alt_leg_b": 1.2, "alt_spine_a": 0.3},
        make_robot_cfg=fake_make_robot_cfg,
    )
    monkeypatch.setattr(lizard2_v7, "ROBOT", fake_robot)

    cfg = lizard2_v7.make_env_cfg()
    assert cfg.scene.robot.spawn.usd_path == str(fake_usd)
    assert cfg.scene.head_ground_contact.prim_path == "{ENV_REGEX_NS}/Robot/Links/alt_skull"
    assert cfg.actions.joint_pos_legs.joint_names == ["alt_leg_a", "alt_leg_b"]
    assert cfg.actions.joint_pos_legs.scale == {"alt_leg_a": 0.4, "alt_leg_b": 0.5}
    assert cfg.actions.joint_pos_legs.clip == {"alt_leg_a": (-1.1, 1.1), "alt_leg_b": (-1.2, 1.2)}
    assert cfg.actions.joint_pos_spine.joint_names == ["alt_spine_a"]
    assert cfg.rewards.belly_contact_force.params["sensor_cfg"].body_names == ["alt_belly"]
    assert cfg.rewards.belly_contact_force.params["force_scale"] == 321.5
    assert cfg.terminations.base_contact.params["sensor_cfg"].body_names == ["alt_belly", "alt_thorax"]
    assert cfg.terminations.head_ground_contact.params["head_body_name"] == "alt_skull"
    assert experiment_eval.experiment_urdf(lizard2_v7) == fake_urdf
    assert experiment_eval.height_scanner_prim_path(cfg, lizard2_v7) == "{ENV_REGEX_NS}/Robot/Links/alt_pelvis"