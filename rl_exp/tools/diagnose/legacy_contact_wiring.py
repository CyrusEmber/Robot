# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Observe the real ownership CLI on the three original shared/split assets.

The profile keeps the original PD, gravity and free base. At most 60 zero-action
control steps after initialization, one environment, and force timing False.
Every live collider gets an exact ground-filtered contact view [N]. No config,
state, force or producer verdict is changed by this observer. Output is a new
directory under rl_exp/out; this proves wiring, not sustained support or gait.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tools.diagnose.palm_entry_wiring import _ground_binding, _require  # noqa: E402
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402

ASSETS = {
    "da05432efd5d3c3dd9302682286825869b289d5f912cb5703bd0d32642e0c52b":
        "fceaf55be1f045572121c464cb32e1eb0ae7d5d0ba63dfbe9a0d943f84df3b6c",
    "9c57fbb7af1558c7da86d19650c5a6bd28fdaafcd27b1517f0ff31db09baf1c7":
        "cce0989b30fb642138aa8a20752a1d5042ed6499417ee70319135dc40c1fde6d",
    "d758c56f69f7eb3d65684db37ca49f249630777c2757448ec47f3ae385e7aecd":
        "dc41586cf31eb89a38f69e2157804b78c8b009a823de6a212e47e22db9ac95a6",
}


def collect(manifest: Path, out: Path, steps: int) -> None:
    """Save bounded actual ownership samples [N] and exact source/asset bindings."""
    import gymnasium as gym

    manifest, out = manifest.resolve(), out.resolve()
    _require((REPO / "rl_exp/out").resolve() in out.parents, "output must be under rl_exp/out")
    _require(1 <= steps <= 60, "step budget must be 1..60")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    binding = document["target_binding"]
    urdf_sha, usd_sha = (sha256_file(Path(binding[key])) for key in ("urdf", "target"))
    _require(ASSETS.get(urdf_sha) == usd_sha, "unexpected original asset pair")
    entry = REPO / "rl_exp/tools/verify/check_contact_ownership.py"
    out.mkdir(parents=True, exist_ok=False)
    (out / "source.py").write_bytes(entry.read_bytes())
    (out / "observer.py").write_bytes(Path(__file__).read_bytes())
    audit = {"manifest": str(manifest), "manifest_sha256": sha256_file(manifest),
             "urdf_sha256": urdf_sha, "usd_sha256": usd_sha,
             "source_sha256": sha256_file(entry), "observer_sha256": sha256_file(Path(__file__)),
             "budget": steps, "env_steps": 0, "physics_steps": [], "closed": False}
    (out / "invocation.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    original_make = gym.make

    def make(*args, **kwargs):
        import torch
        import warp as wp
        from pxr import UsdPhysics
        from isaaclab_physx.physics import PhysxManager

        env = original_make(*args, **kwargs)
        live, cfg = env.unwrapped, kwargs["cfg"]
        robot, sensor = live.scene["robot"], live.scene["contact_forces"]
        stage = live.sim.stage
        names = list(robot.joint_names)
        gains = {name: [float(robot.data.joint_stiffness.torch[0, i]),
                        float(robot.data.joint_damping.torch[0, i])]
                 for i, name in enumerate(names)}
        expected = {}
        for leg, roles in binding["roles"].items():
            for role, gain in (("hip", [800., 40.]), ("haa", [800., 40.]),
                               ("hfe", [800., 40.]), ("kfe", [800., 40.]), ("foot", [200., 12.])):
                expected[f"{leg}_{roles[role]}_joint"] = gain
        expected.update({name: [400., 20.] for name in names if name not in expected})
        bodies = [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)]
        _require(live.num_envs == 1 and len(names) == 30 and len(bodies) == 31, "unexpected robot counts")
        _require(gains == expected, "original live PD changed")
        _require(not robot.is_fixed_base and cfg.scene.robot.spawn.articulation_props.enabled_self_collisions is False,
                 "original free-base/self-collision profile changed")
        _require(all(p.GetAttribute("physxRigidBody:disableGravity").Get() is False for p in bodies),
                 "original live gravity changed")
        force_timing = stage.GetPrimAtPath(cfg.sim.physics_prim_path).GetAttribute(
            "physxScene:enableExternalForcesEveryIteration").Get()
        _require(force_timing is False, "force timing differs from training")
        native_paths = list(sensor.contact_view.sensor_paths)
        _require([p.rsplit("/", 1)[-1] for p in native_paths] == list(sensor.body_names),
                 "native contact body order mismatch")
        from rl_exp.tools.verify.check_self_collision import load_urdf
        model = load_urdf(Path(binding["urdf"]))
        audit.update(joint_names=names, body_names=list(robot.body_names),
                     sensor_body_names=list(sensor.body_names), native_sensor_paths=native_paths,
                     action_names=[name for term in live.action_manager.active_terms
                                   for name in live.action_manager.get_term(term)._joint_names],
                     live_gains=gains, force_timing=force_timing, gravity_enabled=True,
                     fixed_base=False, self_collisions=False, decimation=cfg.decimation,
                     initial_q=robot.data.joint_pos.torch.cpu().tolist(), ground_contact_mapping=[])
        _require(len(audit["action_names"]) == 22 and cfg.decimation == 4, "original action/step profile changed")
        ground = [str(p.GetPath()) for p in stage.Traverse()
                  if p.HasAPI(UsdPhysics.CollisionAPI) and str(p.GetPath()).startswith("/World/ground/")]
        sim_view = PhysxManager.get_physics_sim_view()
        views = []
        for name, spec in model["links"].items():
            if not spec.get("collision"):
                continue
            owners = [p for p in bodies if p.GetName() == name]
            _require(len(owners) == 1, "one live collider owner required")
            source = str(owners[0].GetPath())
            view = sim_view.create_rigid_contact_view(source, filter_patterns=ground,
                max_contact_data_count=sensor.cfg.max_contact_data_count_per_prim)
            _ground_binding(view, source, ground)
            audit["ground_contact_mapping"].append({"body": name, "source": source,
                "ground": ground, "sensor_paths": view.sensor_paths, "filter_paths": view.filter_paths})
            views.append((name, view))
        original_physics, original_step, original_close = live.sim.step, live.step, live.close

        def physics_step(*args, **kwargs):
            _require(len(audit["physics_steps"]) < steps * cfg.decimation, "physics budget exceeded")
            result = original_physics(*args, **kwargs)
            net = wp.to_torch(sensor.contact_view.get_net_contact_forces(dt=live.physics_dt)).clone()
            _require(bool(torch.isfinite(net).all()), "nonfinite native force")
            pairs = {}
            for name, view in views:
                matrix = wp.to_torch(view.get_contact_force_matrix(dt=live.physics_dt)).clone()
                _require(tuple(matrix.shape) == (1, 1, 3) and bool(torch.isfinite(matrix).all()),
                         "invalid ground matrix")
                pairs[name] = matrix.cpu().tolist()
            audit["physics_steps"].append({"net_forces_w_n": net.cpu().tolist(), "ground_forces_w_n": pairs})
            return result

        def step(action):
            _require(audit["env_steps"] < steps, "control budget exceeded")
            _require(bool(torch.isfinite(action).all()) and bool((action == 0).all()), "zero action required")
            audit["env_steps"] += 1
            return original_step(action)

        def close():
            if not audit["closed"]:
                audit["closed"] = True
                audit["final_q"] = robot.data.joint_pos.torch.cpu().tolist()
                (out / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
            return original_close()

        live.sim.step, live.step, live.close = physics_step, step, close
        return env

    arguments = [str(entry), "--task", "Lizard2-Flat-Play-v3", "--target_config", str(manifest),
                 "--num_envs", "1", "--steps", str(steps), "--json", str(out / "report.json"), "--headless"]
    with patch.object(sys, "argv", arguments), patch.object(gym, "make", make):
        runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target_config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=60)
    options = parser.parse_args()
    collect(options.target_config, options.out, options.steps)
