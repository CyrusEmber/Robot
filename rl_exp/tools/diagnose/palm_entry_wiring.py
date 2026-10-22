# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Observe bounded real palm CLI entries [m, rad, N] without changing their data or verdicts.

Only the current fixed candidate URDF, zero gains, disabled gravity and force timing False.
Budgets count env.step calls after gym.make: layout 0, ownership/baseline/support 2, stance 12.
The output must be a new directory under rl_exp/out. Forward the producer's arguments
after --; include its --task and use only a tiny normalized action (<= 0.01).
This is wiring evidence, not support, tracking, collision clearance or protocol approval.
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
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402

ENTRIES = {
    "layout": REPO / "rl_exp/tools/verify/check_joint_layout.py",
    "ownership": REPO / "rl_exp/tools/verify/check_contact_ownership.py",
    "baseline": REPO / "rl_exp/tools/verify/baseline_probe.py",
    "stance": REPO / "rl_exp/tools/diagnose/stance_step_probe.py",
    "support": REPO / "rl_exp/tools/diagnose/diagnose_support.py",
}
BUDGETS = {"check_joint_layout.py": 0, "check_contact_ownership.py": 2,
           "baseline_probe.py": 2, "stance_step_probe.py": 12, "diagnose_support.py": 2}
URDF_SHA256 = "e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _ground_binding(view, source: str, ground: list[str]) -> None:
    """Check the native one-body, one-ground row and column before naming forces."""
    _require(len(ground) == 1, 'one ground column required')
    _require(view.sensor_paths in ([source], [[source]]), 'ground contact row mismatch')
    _require(view.filter_paths in (ground, [ground]), 'ground contact column mismatch')
    _require(view.sensor_count == view.filter_count == 1, 'ground contact shape mismatch')


def collect(entry: Path, out: Path, arguments: list[str]) -> None:
    """Save a bounded entry's actual states [SI units] and source identities in a new directory."""
    import gymnasium as gym

    entry, out = entry.resolve(), out.resolve()
    _require(entry in [path.resolve() for path in ENTRIES.values()], "unknown producer")
    _require((REPO / "rl_exp/out").resolve() in out.parents, "output must be under rl_exp/out")
    _require("--target_config" in arguments, "explicit --target_config required")
    out.mkdir(parents=True, exist_ok=False)
    (out / 'source.py').write_bytes(entry.read_bytes())
    (out / 'observer.py').write_bytes(Path(__file__).read_bytes())
    audit = {'entry': str(entry), 'source_sha256': sha256_file(entry), 'arguments': arguments,
             'budget': BUDGETS[entry.name], 'observer_sha256': sha256_file(Path(__file__)), 'env_steps': [], 'closed': False}
    (out / 'invocation.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    original_make = gym.make

    def make(*args, **kwargs):
        import torch
        import warp as wp
        from pxr import UsdGeom, UsdPhysics
        from isaaclab.utils.math import quat_apply
        from rl_exp.tools.verify import check_self_collision as collision

        env = original_make(*args, **kwargs)
        live, cfg = env.unwrapped, kwargs['cfg']
        robot, sensor = live.scene['robot'], live.scene['contact_forces']
        manifest = Path(arguments[arguments.index('--target_config') + 1]).resolve()
        document = json.loads(manifest.read_text(encoding='utf-8'))
        urdf = Path(document['target_binding']['urdf'])
        _require(sha256_file(urdf) == URDF_SHA256, 'unexpected candidate URDF')
        model = collision.load_urdf(urdf)
        names = list(robot.body_names)
        clouds = {name: torch.tensor(collision.read_obj(spec['collision']), device=live.device,
                                    dtype=torch.float32)
                  for name, spec in model['links'].items() if spec.get('collision')}
        audit.update(manifest=str(manifest), manifest_sha256=sha256_file(manifest),
                     target_binding=document['target_binding'], body_names=names,
                     sensor_body_names=list(sensor.body_names), joint_names=list(robot.joint_names),
                     action_names=[name for term in live.action_manager.active_terms
                                   for name in live.action_manager.get_term(term)._joint_names],
                     force_timing=live.sim.stage.GetPrimAtPath(cfg.sim.physics_prim_path).GetAttribute(
                         'physxScene:enableExternalForcesEveryIteration').Get(),
                     body_disable_gravity={str(p.GetPath()): p.GetAttribute('physxRigidBody:disableGravity').Get()
                                           for p in live.sim.stage.Traverse()
                                           if p.HasAPI(UsdPhysics.RigidBodyAPI)},
                     fixed_base=bool(robot.is_fixed_base),
                     max_joint_stiffness=float(robot.data.joint_stiffness.torch.abs().max()),
                     max_joint_damping=float(robot.data.joint_damping.torch.abs().max()))
        _require(audit['force_timing'] is False, 'force timing differs from training')
        _require(audit['fixed_base'], 'fixed base required for this wiring probe')
        _require(len(audit['body_disable_gravity']) == 31 * live.num_envs
                 and all(audit['body_disable_gravity'].values()), 'unexpected live gravity')
        _require(audit['max_joint_stiffness'] == audit['max_joint_damping'] == 0., 'nonzero live gains')
        audit['native_contact_sensor_paths'] = list(sensor.contact_view.sensor_paths)
        _require([path.rsplit('/', 1)[-1] for path in audit['native_contact_sensor_paths']]
                 == list(sensor.body_names) * live.num_envs, 'native contact body order mismatch')
        audit['decimation'] = cfg.decimation
        audit['physics_steps'] = []
        audit['collisions'] = []
        transforms = UsdGeom.XformCache()
        for prim in live.sim.stage.Traverse():
            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                continue
            points = prim.GetAttribute('points').Get() if prim.HasAttribute('points') else None
            matrix = transforms.GetLocalToWorldTransform(prim)
            audit['collisions'].append({
                'path': str(prim.GetPath()), 'type': prim.GetTypeName(),
                'enabled': UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get(),
                'approximation': prim.GetAttribute('physics:approximation').Get(),
                'rest_offset_m': prim.GetAttribute('physxCollision:restOffset').Get(),
                'contact_offset_m': prim.GetAttribute('physxCollision:contactOffset').Get(),
                'usd_authored_mesh_lowest_world_z_m':
                    min(float(matrix.Transform(p)[2]) for p in points) if points else None})

        ground = [row['path'] for row in audit['collisions'] if row['path'].startswith('/World/ground/')]
        audit['ground_contact_mapping'] = []
        ground_views = []
        if entry.name == 'check_contact_ownership.py':
            from isaaclab_physx.physics import PhysxManager
            _require(len(ground) == 1, 'one exact ground collider required')
            sim_view = PhysxManager.get_physics_sim_view()
            for name in document['target_binding']['end_links'].values():
                sources = [prim for prim in live.sim.stage.Traverse()
                           if prim.HasAPI(UsdPhysics.RigidBodyAPI) and prim.GetName() == name]
                _require(len(sources) == 1, 'one live foot owner required')
                source = str(sources[0].GetPath())
                view = sim_view.create_rigid_contact_view(
                    source, filter_patterns=ground,
                    max_contact_data_count=sensor.cfg.max_contact_data_count_per_prim)
                mapping = {'body': name, 'source': source, 'ground': ground,
                           'sensor_paths': view.sensor_paths, 'filter_paths': view.filter_paths}
                audit['ground_contact_mapping'].append(mapping)
                _ground_binding(view, source, ground)
                ground_views.append((name, view))

        original_physics_step = live.sim.step

        def physics_step(*args, **kwargs):
            _require(len(audit['physics_steps']) < audit['budget'] * audit['decimation'],
                     'physics step budget exceeded')
            result = original_physics_step(*args, **kwargs)
            force = wp.to_torch(sensor.contact_view.get_net_contact_forces(dt=live.physics_dt)).clone()
            _require(bool(torch.isfinite(force).all()), 'nonfinite native contact force')
            pairs = {}
            for name, view in ground_views:
                matrix = wp.to_torch(view.get_contact_force_matrix(dt=live.physics_dt)).clone()
                _require(tuple(matrix.shape) == (1, 1, 3) and bool(torch.isfinite(matrix).all()),
                         'invalid ground contact matrix')
                pairs[name] = matrix.cpu().tolist()
            audit['physics_steps'].append({'net_forces_w_n': force.cpu().tolist(),
                                           'foot_ground_forces_w_n': pairs})
            return result

        live.sim.step = physics_step

        def snapshot():
            raw = wp.to_torch(robot.root_physx_view.get_link_transforms()).clone()
            minima = {}
            for name, vertices in clouds.items():
                pose = raw[0, names.index(name)]
                world = quat_apply(pose[3:].expand(len(vertices), -1), vertices) + pose[:3]
                minima[name] = float(world[:, 2].min())
            return {'backend_link_poses': raw.cpu().tolist(),
                    'cached_root_pos_w_m': robot.data.root_pos_w.torch.cpu().tolist(),
                    'mesh_lowest_world_z_m': minima,
                    'net_forces_w_n': sensor.data.net_forces_w.torch.cpu().tolist(),
                    'backend_joint_pos_rad': wp.to_torch(robot.root_physx_view.get_dof_positions()).cpu().tolist(),
                    'backend_joint_target_rad': wp.to_torch(robot.root_physx_view.get_dof_position_targets()).cpu().tolist(),
                    'joint_pos_rad': robot.data.joint_pos.torch.cpu().tolist(),
                    'joint_target_rad': robot.data.joint_pos_target.torch.cpu().tolist()}

        audit['initial'] = snapshot()
        original_step, original_close = live.step, live.close

        def step(action):
            _require(len(audit['env_steps']) < audit['budget'], 'env.step budget exceeded')
            _require(bool(torch.isfinite(action).all()) and float(action.abs().max()) <= .01,
                     'nonfinite or excessive action')
            row = {'action': action.cpu().tolist()}
            audit['env_steps'].append(row)
            result = original_step(action)
            row['after'] = snapshot()
            return result

        def close():
            if not audit['closed']:
                audit['final'] = snapshot()
                audit['closed'] = True
                (out / 'audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
            return original_close()

        live.step, live.close = step, close
        return env

    with patch.object(sys, 'argv', [str(entry), *arguments]), patch.object(gym, 'make', make):
        runpy.run_path(str(entry), run_name='__main__')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", choices=sorted(ENTRIES), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target_config", type=Path, required=True)
    parser.add_argument("producer_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    forwarded = args.producer_args[1:] if args.producer_args[:1] == ["--"] else args.producer_args
    _require(not any(item == "--target_config" or item.startswith("--target_config=") for item in forwarded),
             "pass target_config only to the observer")
    collect(ENTRIES[args.entry], args.out, ["--target_config", str(args.target_config.resolve()), *forwarded])


if __name__ == "__main__":
    main()
