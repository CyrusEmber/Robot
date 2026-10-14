# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Validate isolated palm coordinates, inertia and collision prerequisites [m, rad, kg, N]."""

import argparse
import json
import math
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import traceback

try:
    from isaaclab.app import AppLauncher
except BaseException:
    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--urdf", type=Path, required=True)
parser.add_argument("--probe_report", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--convert", action="store_true")
parser.add_argument("--filter_connections", action="store_true")
parser.add_argument("--coordinates_only", action="store_true")
parser.add_argument("--inertia_only", action="store_true")
parser.add_argument("--collision_only", action="store_true")
parser.add_argument("--collision_negative", action="store_true")
parser.add_argument("--normalize_inertia", action="store_true")
parser.add_argument("--legacy_zero_check", action="store_true")
parser.add_argument("--inject_error", choices=("pivot", "axis", "state", "exception", "inertia", "filter", "import", "scan_extra"))
parser.add_argument("--inertia_pose", type=float, default=0.)
parser.add_argument("--require_inertia_match", action="store_true")
parser.add_argument("--write_normalized_usd", type=Path)
parser.add_argument("--usd", type=Path)
parser.add_argument("--blender_snapshot", type=Path)
parser.add_argument("--steps", type=int, default=600)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
try:
    app = AppLauncher(args).app

    if args.inject_error == "import":
        raise ImportError("INJECTED_PALM_PROBE_IMPORT_FAILURE")
    import numpy as np
    import torch

    import isaaclab.sim as sim_utils
    from isaaclab.actuators import ImplicitActuatorCfg
    from isaaclab.assets import Articulation, ArticulationCfg
    from isaaclab.sensors import ContactSensor, ContactSensorCfg
    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg
    from pxr import Gf, Usd, UsdGeom, UsdPhysics

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
    from flatten_usd import flatten_usd
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runrecord"))
    import binding
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "verify"))
    from check_leg_reachability import _matrix
except BaseException:
    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)


def pose_matrix(pose):
    x, y, z, w = pose[3:]
    matrix = np.array(Gf.Matrix4d().SetRotate(Gf.Quatd(float(w), Gf.Vec3d(float(x), float(y), float(z))))).T
    matrix[:3, 3] = pose[:3]
    return matrix


def coordinate_snapshot(robot, joints, label, initial_z, *, reject=True):
    actor = robot.data.body_link_pose_w.torch[0].cpu().numpy().copy()
    q = dict(zip(robot.joint_names, robot.data.joint_pos.torch[0].cpu().numpy().copy()))
    root = actor[robot.body_names.index("base_link")]
    frames = {"base_link": pose_matrix(root)}
    depths = {"base_link": 0}
    if args.inject_error == "state":
        q["lf_shoulder_abduct_joint"] += .1
    for joint in joints:
        parent, child = joint.find("parent").get("link"), joint.find("child").get("link")
        xyz = np.fromstring(joint.find("origin").get("xyz"), sep=" ")
        axis = np.fromstring(joint.find("axis").get("xyz"), sep=" ")
        rpy = np.fromstring(joint.find("origin").get("rpy", "0 0 0"), sep=" ")
        frames[child] = frames[parent] @ np.array(_matrix(xyz, axis, float(q[joint.get("name")]), rpy))
        depths[child] = depths[parent] + 1
    scale = max(1., float(np.abs(root[:3]).max()) + sum(
        np.linalg.norm(np.fromstring(joint.find("origin").get("xyz"), sep=" ")) for joint in joints))
    residuals = {}
    for name, actual_pose in zip(robot.body_names, actor):
        actual = pose_matrix(actual_pose)
        delta = actual[:3, 3] - frames[name][:3, 3]
        rotation_error = float(np.linalg.norm(actual[:3, :3] - frames[name][:3, :3], ord="fro"))
        depth = max(1, depths[name])
        position_budget = float(math.sqrt(3) * .5e-6 * depth + 64 * np.finfo(np.float32).eps * scale * depth)
        rotation_budget = float(64 * np.finfo(np.float32).eps * depth)
        residuals[name] = {"position_residual_m": delta.tolist(), "rotation_matrix_residual": rotation_error,
                           "position_budget_m": position_budget, "rotation_budget": rotation_budget}
    result = {"label": label, "joint_pos_rad": {n: float(v) for n, v in q.items()},
              "root_actor_pose_xyzw": root.tolist(), "body_actor_pose_xyzw": dict(zip(robot.body_names, actor.tolist())),
              "body_com_pose_xyzw": dict(zip(robot.body_names, robot.data.body_com_pose_w.torch[0].cpu().tolist())),
              "residuals": residuals,
              "budget_rule": "per-depth: xyz decimal roundoff sqrt(3)*0.5e-6 + 64*float32_eps*declared_world_scale; rotation 64*eps"}
    print("COORDINATE_SNAPSHOT", json.dumps(result), flush=True)
    if reject:
        failures = [n for n, r in residuals.items() if np.linalg.norm(r["position_residual_m"]) > r["position_budget_m"]
                    or r["rotation_matrix_residual"] > r["rotation_budget"]]
        assert not failures, "actor/FK mismatch: " + str(failures)
    return result


def asset_chain_snapshot(stage, joints, links, snapshots, probe):
    from scipy.spatial import cKDTree

    source = json.loads(args.blender_snapshot.read_text(encoding="utf-8"))
    assert source["completed"] and source["source_sha256"] == probe["source_sha256"]
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1. and UsdGeom.GetStageUpAxis(stage) == "Z"
    assert set(source["parents"]) == set(links), "Blender/URDF body set mismatch"
    bodies = {p.GetName(): p for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)}
    cache = UsdGeom.XformCache()
    joint_prims = {p.GetName(): p for p in stage.Traverse() if p.IsA(UsdPhysics.RevoluteJoint)}
    axes_checked = {}
    for joint in joints:
        name = joint.get("name")
        parent, child = joint.find("parent").get("link"), joint.find("child").get("link")
        assert source["parents"][child] == parent
        authored = UsdPhysics.RevoluteJoint(joint_prims[name])
        assert authored.GetBody0Rel().GetTargets() == [bodies[parent].GetPath()]
        assert authored.GetBody1Rel().GetTargets() == [bodies[child].GetPath()]
        xyz = np.fromstring(joint.find("origin").get("xyz"), sep=" ")
        assert np.allclose(authored.GetLocalPos0Attr().Get(), xyz, rtol=0., atol=2e-6), "USD pivot mismatch"
        assert np.linalg.norm(authored.GetLocalPos1Attr().Get()) < 2e-6
        rotations = []
        for quat in (authored.GetLocalRot0Attr().Get(), authored.GetLocalRot1Attr().Get()):
            rotations.append(pose_matrix(np.r_[np.zeros(3), list(quat.GetImaginary()), quat.GetReal()])[:3, :3])
        axis = rotations[0][:, "XYZ".index(authored.GetAxisAttr().Get())]
        expected_axis = np.fromstring(joint.find("axis").get("xyz"), sep=" ")
        assert np.linalg.norm(axis - expected_axis) < 2e-6, "USD joint axis mismatch"
        assert np.linalg.norm(rotations[0] @ rotations[1].T - np.eye(3)) < 2e-6
        axes_checked[name] = float(np.linalg.norm(axis - expected_axis))
    results = []
    for sample in source["snapshots"]:
        angle = sample["q_rad"]
        label = "explicit_zero_no_physics_step" if angle == 0 else "written_nonzero_no_physics_step"
        actual = next(row for row in snapshots if row["label"] == label)
        root_world = np.array(source["rest_pivots_world_m"]["base_link"])
        runtime_root = pose_matrix(actual["root_actor_pose_xyzw"])
        frames = {"base_link": np.eye(4)}
        depth = {"base_link": 0}
        for joint in joints:
            parent, child = joint.find("parent").get("link"), joint.find("child").get("link")
            frames[child] = frames[parent] @ np.array(_matrix(
                np.fromstring(joint.find("origin").get("xyz"), sep=" "),
                np.fromstring(joint.find("axis").get("xyz"), sep=" "), angle,
                np.fromstring(joint.find("origin").get("rpy", "0 0 0"), sep=" ")))
            depth[child] = depth[parent] + 1
        rows = {}
        for name, link in links.items():
            body_world = cache.GetLocalToWorldTransform(bodies[name])
            runtime_frame = np.linalg.inv(runtime_root) @ pose_matrix(np.array(actual["body_actor_pose_xyzw"][name]))
            pivot = np.array(sample["pivots_world_m"][name]) - root_world
            scale = max(1., float(np.abs(pivot).max()))
            budget = float((math.sqrt(3) * .5e-6 + 64 * np.finfo(np.float32).eps * scale) * (depth[name] + 2))
            rows[name] = {"budget_m": budget,
                          "blender_pivot_vs_urdf_m": float(np.linalg.norm(pivot - frames[name][:3, 3])),
                          "blender_pivot_vs_runtime_m": float(np.linalg.norm(pivot - runtime_frame[:3, 3]))}
            assert max(rows[name][k] for k in ("blender_pivot_vs_urdf_m", "blender_pivot_vs_runtime_m")) < budget
            for kind in ("visual", "collision"):
                tag = link.find(kind + "/geometry/mesh")
                objects = [obj for obj in sample["meshes"] if obj["link"] == name and (kind == "visual" or obj["collision"])]
                assert (tag is not None) == bool(objects), "Mesh ownership mismatch: " + name + kind
                if tag is None:
                    continue
                point_key = "points_world_m" if kind == "visual" else "collision_points_world_m"
                blender_points = np.concatenate([np.array(obj[point_key]) for obj in objects]) - root_world
                obj_points = np.array([list(map(float, row.split()[1:4]))
                                       for row in (args.urdf.parent / tag.get("filename")).read_text().splitlines()
                                       if row.startswith("v ")])
                prim = bodies[name].GetChild(name + "_" + kind)
                assert prim.IsA(UsdGeom.Mesh), "Missing USD mesh"
                relative = cache.GetLocalToWorldTransform(prim) * body_world.GetInverse()
                usd_points = np.array([relative.Transform(Gf.Vec3d(*p)) for p in UsdGeom.Mesh(prim).GetPointsAttr().Get()])
                for origin, local, transform in (("urdf", obj_points, frames[name]),
                                                  ("usd", usd_points, frames[name]),
                                                  ("runtime", usd_points, runtime_frame)):
                    points = local @ transform[:3, :3].T + transform[:3, 3]
                    error = float(max(cKDTree(points).query(blender_points)[0].max(),
                                      cKDTree(blender_points).query(points)[0].max()))
                    rows[name][kind + "_blender_vs_" + origin + "_m"] = error
                    assert error < budget, "Asset mesh mismatch: " + name + " " + kind + " " + origin
        results.append({"q_rad": angle, "links": rows})
    return {"snapshots": results, "joint_axis_errors": axes_checked,
            "mesh_check": "symmetric vertex-set distance, not topology or cooked convex hull equivalence",
            "budget_rule": "(depth+2)*(sqrt(3)*0.5e-6 + 64*float32_eps*root_relative_scale)"}


def main():
    if args.inject_error == "exception":
        raise RuntimeError("INJECTED_PALM_PROBE_FAILURE")
    if sum((args.coordinates_only, args.inertia_only, args.collision_only)) != 1:
        raise ValueError("Choose one validation stage; PD is blocked until all prerequisites pass")
    urdf = args.urdf.resolve()
    scratch = Path(__file__).resolve().parents[2] / "out"
    assert scratch in urdf.parents and args.output.resolve().parent == urdf.parent
    assert not args.output.exists(), "Refuse overwriting a calibration record"
    probe = json.loads(args.probe_report.read_text(encoding="utf-8"))
    assert probe["naming"] == "palm", "This entry validates only the restored palm contract"
    assert binding.sha256_file(Path(probe["source"])) == probe["source_sha256"]
    usd = (args.usd or urdf.with_suffix(".usda")).resolve()
    assert usd.parent == urdf.parent, "USD must remain in the isolated input directory"
    input_files = {"source": Path(probe["source"]), "probe_report": args.probe_report.resolve(),
                   "urdf": urdf, "usd": usd}
    if args.blender_snapshot:
        input_files["blender_snapshot"] = args.blender_snapshot.resolve()
    for mesh in ET.parse(urdf).getroot().iter("mesh"):
        path = (urdf.parent / mesh.get("filename")).resolve()
        input_files[str(path.relative_to(urdf.parent))] = path
    repo = Path(__file__).resolve().parents[3]
    source_files = sorted({Path(__file__).resolve(),
                           Path(__file__).with_name("palm_asset_probe.py"),
                           repo / "rl_exp/blender/scripts/generate_urdf.py",
                           repo / "rl_exp/versions/lizard2/assets.json"} | {
        Path(module.__file__).resolve() for module in sys.modules.values()
        if getattr(module, "__file__", None) and Path(module.__file__).resolve().is_relative_to(repo)
        and Path(module.__file__).suffix == ".py" and Path(module.__file__).resolve().is_file()})
    assert all(path.is_file() for key, path in input_files.items() if key != "usd" or not args.convert), "Missing bound input"
    code_snapshot = args.output.with_suffix(".code.zip")
    import zipfile

    with zipfile.ZipFile(code_snapshot, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files:
            archive.write(path, path.relative_to(Path(__file__).resolve().parents[3]).as_posix())
    identity = {"inputs": {key: {"path": str(path), "sha256": binding.sha256_file(path)} for key, path in input_files.items()},
                "code": {str(path): binding.sha256_file(path) for path in source_files},
                "code_snapshot": {"path": str(code_snapshot), "sha256": binding.sha256_file(code_snapshot)},
                "revision": binding.git_rev(Path(__file__).resolve().parents[3]),
                "cli": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
                "completed": False}
    identity["repository_status"] = binding.git_run(Path(__file__).resolve().parents[3], "status", "--porcelain")
    import isaaclab

    framework = Path(isaaclab.__file__).resolve().parents[3]
    identity["framework"] = {"root": str(framework), "revision": binding.git_rev(framework),
                             "status": binding.git_run(framework, "status", "--porcelain")}
    print("VALIDATION_IDENTITY", json.dumps(identity), flush=True)
    tree = ET.parse(urdf).getroot()
    joints = tree.findall("joint")
    links = {link.get("name"): link for link in tree.findall("link")}
    positions = {"base_link": np.zeros(3)}
    parents, axes, limits, velocity, effort = {}, {}, {}, {}, {}
    for joint in joints:
        name = joint.get("name").removesuffix("_joint")
        parent = joint.find("parent").get("link")
        child = joint.find("child").get("link")
        assert name == child and parent in positions
        positions[child] = positions[parent] + np.fromstring(joint.find("origin").get("xyz"), sep=" ")
        parents[child] = parent
        axes[child] = np.fromstring(joint.find("axis").get("xyz"), sep=" ")
        limits[child] = [float(joint.find("limit").get(k)) for k in ("lower", "upper")]
        velocity[joint.get("name")] = float(joint.find("limit").get("velocity"))
        effort[joint.get("name")] = float(joint.find("limit").get("effort"))
        assert np.allclose(axes[child], probe["candidate_axes_world"][child], atol=1e-8)
        assert np.allclose(limits[child], probe["candidate_limits_rad"][child], atol=1e-8)
    masses = {n: float(link.find("inertial/mass").get("value")) for n, link in links.items()}
    com = {n: positions[n] + np.fromstring(link.find("inertial/origin").get("xyz"), sep=" ")
           for n, link in links.items()}
    inertia = {n: np.diag([float(link.find("inertial/inertia").get(k)) for k in ("ixx", "iyy", "izz")])
               for n, link in links.items()}
    paths = {}
    for n in links:
        path = [n]
        while path[-1] in parents:
            path.append(parents[path[-1]])
        paths[n] = path
    mass = sum(masses.values())
    seed, moment = {}, {}
    for n in axes:
        axis, pivot = axes[n], positions[n]
        descendants = [child for child in links if n in paths[child]]
        effective = sum(float(axis @ inertia[child] @ axis)
                        + masses[child] * float(np.linalg.norm(np.cross(com[child] - pivot, axis)) ** 2)
                        for child in descendants)
        gravity = sum(float(axis @ np.cross(com[child] - pivot, [0, 0, -9.80665 * masses[child]]))
                      for child in descendants)
        support = 0.0
        if n[:2] in ("lf", "rf", "rl", "rr"):
            end = n[:2] + ("_wrist" if n[1] == "f" else "_ankle")
            support = float(axis @ np.cross(com[end] - pivot, [0, 0, mass * 9.80665 / 4]))
        kp = max(effective * 100, abs(gravity + support) / .05, 20)
        kd = 2 * .9 * math.sqrt(kp * effective)
        seed[n + "_joint"] = [kp, kd]
        moment[n] = {"locked_descendant_inertia_kg_m2": effective,
                     "neutral_subtree_gravity_nm": gravity, "equal_foot_support_nm": support}
    if args.convert:
        assert not usd.exists(), "Conversion requires a fresh isolated asset"
        converter = UrdfConverter(UrdfConverterCfg(
            asset_path=str(urdf), usd_dir=str(urdf.parent), usd_file_name=usd.name,
            fix_base=False, merge_fixed_joints=False, force_usd_conversion=True,
            self_collision=True, run_asset_transformer=False, run_multi_physics_conversion=False,
            joint_drive=UrdfConverterCfg.JointDriveCfg(
                gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(
                    stiffness={n: v[0] for n, v in seed.items()},
                    damping={n: v[1] for n, v in seed.items()}), target_type="position")))
        converted = Path(converter.usd_path)
        flatten_usd(str(converted))
        assert converted.is_relative_to(urdf.parent), "Converter escaped isolated tree"
        if converted != usd:
            converted.replace(usd)
    stage = Usd.Stage.Open(str(usd))
    bodies = [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)]
    actual_joints = [p for p in stage.Traverse() if p.IsA(UsdPhysics.RevoluteJoint)]
    assert len(bodies) == len(links) and len(actual_joints) == len(joints)
    assert {p.GetName() for p in actual_joints} == set(seed)
    if args.write_normalized_usd:
        target = args.write_normalized_usd.resolve()
        assert target.parent == urdf.parent and target.suffix == ".usda" and not target.exists()
        original = {str(attr.GetPath()): str(attr.Get()) for prim in stage.Traverse()
                    for attr in prim.GetAttributes()}
        for prim in bodies:
            mass_api = UsdPhysics.MassAPI(prim)
            mass_api.GetDiagonalInertiaAttr().Set(Gf.Vec3f(*np.diag(inertia[prim.GetName()])))
            mass_api.GetPrincipalAxesAttr().Set(Gf.Quatf(1., Gf.Vec3f(0.)))
        with target.open("x", encoding="utf-8") as handle:
            handle.write(stage.GetRootLayer().ExportToString())
        reopened = Usd.Stage.Open(str(target))
        for prim in reopened.Traverse():
            for attr in prim.GetAttributes():
                if attr.GetName() not in ("physics:diagonalInertia", "physics:principalAxes"):
                    assert str(attr.Get()) == original[str(attr.GetPath())], "Non-inertia asset value changed"
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                mass_api = UsdPhysics.MassAPI(prim)
                assert np.allclose(mass_api.GetDiagonalInertiaAttr().Get(), np.diag(inertia[prim.GetName()]),
                                   rtol=2e-7, atol=1e-10)
                assert mass_api.GetPrincipalAxesAttr().Get() == Gf.Quatf(1., Gf.Vec3f(0.))
        usd = target
        stage = reopened
        identity["normalized_asset"] = {"path": str(target), "sha256": binding.sha256_file(target)}
        args.require_inertia_match = True
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=.005, device=args.device))
    sim_utils.GroundPlaneCfg().func("/World/Ground", sim_utils.GroundPlaneCfg())
    sim_utils.DomeLightCfg(intensity=2000).func("/World/Light", sim_utils.DomeLightCfg(intensity=2000))
    sim.set_camera_view([4, -5, 3], [0, 0, .6])
    floor_by_link = {}
    for n, link in links.items():
        mesh = link.find("collision/geometry/mesh")
        if mesh is not None:
            points = np.array([list(map(float, line.split()[1:4]))
                               for line in (urdf.parent / mesh.get("filename")).read_text().splitlines()
                               if line.startswith("v ")])
            floor_by_link[n] = float(points[:, 2].min() + positions[n][2])
    initial_z = -min(floor_by_link.values()) + .003
    robots, sensors = [], []
    factors = (.5, 1., 2.)
    for index, factor in enumerate(factors):
        prim = f"/World/Case{index}/Robot"
        cfg = ArticulationCfg(
            prim_path=prim,
            spawn=sim_utils.UsdFileCfg(
                usd_path=str(usd), activate_contact_sensors=True,
                articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                    enabled_self_collisions=True, solver_position_iteration_count=8,
                    solver_velocity_iteration_count=2)),
            init_state=ArticulationCfg.InitialStateCfg(pos=(0, index * 5., initial_z),
                                                     joint_pos={".*": 0.}, joint_vel={".*": 0.}),
            actuators={"all": ImplicitActuatorCfg(
                joint_names_expr=list(seed), stiffness={n: v[0] * factor for n, v in seed.items()},
                damping={n: v[1] * math.sqrt(factor) for n, v in seed.items()},
                effort_limit_sim=effort, velocity_limit_sim=velocity)})
        robots.append(Articulation(cfg))
        sensors.append(ContactSensor(ContactSensorCfg(prim_path=prim + "/.*", update_period=0., history_length=1)))
    filtered = []
    if args.filter_connections:
        approved = {frozenset(pair) for pair in (
            ("tail2_pitch", "tail1_pitch"), ("tail1_pitch", "base_link"),
            ("base_link", "rr_hip_abduct"), ("base_link", "rl_hip_abduct"),
            ("rf_shoulder_abduct", "chest_pitch"), ("lf_shoulder_abduct", "chest_pitch"))}
        for hit in probe["samples"][0]["mesh_surface_crossings"]:
            a, b = hit["links"]
            common = next(n for n in paths[a] if n in paths[b])
            intermediates = paths[a][1:paths[a].index(common)] + paths[b][1:paths[b].index(common)]
            if (hit["tree_distance_joints"] == 2
                    and all(links[n].find("collision") is None for n in intermediates)
                    and (common == a or common == b)):
                filtered.append((a, b))
        if args.inject_error == "scan_extra":
            filtered.append(("lf_wrist", "rl_ankle"))
        scanned = {frozenset(pair) for pair in filtered}
        assert len(scanned) == len(filtered) and scanned == approved, \
            f"Scanned connections differ from approved set: {sorted(map(sorted, scanned ^ approved))}"
        live_stage = sim_utils.get_current_stage()
        for index in range(len(robots)):
            body_prims = {p.GetName(): p for p in live_stage.Traverse()
                          if str(p.GetPath()).startswith(f"/World/Case{index}/Robot/")
                          and p.HasAPI(UsdPhysics.RigidBodyAPI)}
            for a, b in filtered:
                relationship = UsdPhysics.FilteredPairsAPI.Apply(body_prims[a]).CreateFilteredPairsRel()
                relationship.AddTarget(body_prims[b].GetPath())
                assert body_prims[b].GetPath() in relationship.GetTargets()
        print("DIAGNOSTIC_FILTERED_CONNECTIONS", filtered, flush=True)
    live_stage = sim_utils.get_current_stage()
    if args.inject_error == "filter":
        for index in range(len(robots)):
            body_prims = {p.GetName(): p for p in live_stage.Traverse()
                          if str(p.GetPath()).startswith(f"/World/Case{index}/Robot/")
                          and p.HasAPI(UsdPhysics.RigidBodyAPI)}
            UsdPhysics.FilteredPairsAPI.Apply(body_prims["lf_wrist"]).CreateFilteredPairsRel().AddTarget(
                body_prims["rl_ankle"].GetPath())
    filter_readback = []
    expected_pairs = {frozenset(pair) for pair in filtered}
    for index in range(len(robots)):
        actual_pairs = []
        for prim in live_stage.Traverse():
            if str(prim.GetPath()).startswith(f"/World/Case{index}/Robot/") and prim.HasAPI(UsdPhysics.FilteredPairsAPI):
                actual_pairs.extend([prim.GetName(), target.name]
                                    for target in UsdPhysics.FilteredPairsAPI(prim).GetFilteredPairsRel().GetTargets())
        assert {frozenset(pair) for pair in actual_pairs} == expected_pairs, "Unexpected collision filter pair"
        filter_readback.append({"case": index, "pairs": actual_pairs})
    pair_sensors = []
    if args.collision_only:
        live_stage = sim_utils.get_current_stage()
        for index in range(len(robots)):
            body_prims = {p.GetName(): str(p.GetPath()) for p in live_stage.Traverse()
                          if str(p.GetPath()).startswith(f"/World/Case{index}/Robot/")
                          and p.HasAPI(UsdPhysics.RigidBodyAPI)}
            pairs = [hit["links"] for hit in probe["samples"][0]["mesh_surface_crossings"]]
            pairs.extend((["lf_elbow", "rl_knee"], ["lf_wrist", "rl_ankle"]))
            for a, b in pairs:
                pair_sensors.append((index, a, b, ContactSensor(ContactSensorCfg(
                    prim_path=body_prims[a], filter_prim_paths_expr=[body_prims[b]], update_period=0.,
                    track_contact_points=True, max_contact_data_count_per_prim=128))))
    if args.normalize_inertia:
        live_stage = sim_utils.get_current_stage()
        for index in range(len(robots)):
            for prim in live_stage.Traverse():
                if str(prim.GetPath()).startswith(f"/World/Case{index}/Robot/") and prim.HasAPI(UsdPhysics.RigidBodyAPI):
                    mass_api = UsdPhysics.MassAPI(prim)
                    mass_api.GetDiagonalInertiaAttr().Set(Gf.Vec3f(*np.diag(inertia[prim.GetName()])))
                    mass_api.GetPrincipalAxesAttr().Set(Gf.Quatf(1., Gf.Vec3f(0.)))
    if args.inject_error == "inertia":
        live_stage = sim_utils.get_current_stage()
        for prim in live_stage.Traverse():
            if prim.GetName() == "lf_elbow" and prim.HasAPI(UsdPhysics.RigidBodyAPI):
                mass_api = UsdPhysics.MassAPI(prim)
                diagonal = mass_api.GetDiagonalInertiaAttr().Get()
                mass_api.GetDiagonalInertiaAttr().Set(Gf.Vec3f(diagonal[0] * 1.25, diagonal[1], diagonal[2]))
    if args.inject_error in ("pivot", "axis"):
        live_stage = sim_utils.get_current_stage()
        live_stage.SetEditTarget(live_stage.GetSessionLayer())
        for index in range(len(robots)):
            joint_prim = next(p for p in live_stage.Traverse()
                              if str(p.GetPath()).startswith(f"/World/Case{index}/Robot/")
                              and p.GetName() == "lf_shoulder_abduct_joint")
            joint_api = UsdPhysics.RevoluteJoint(joint_prim)
            if args.inject_error == "pivot":
                pos = joint_api.GetLocalPos0Attr().Get()
                joint_api.GetLocalPos0Attr().Set(Gf.Vec3f(pos[0] + .01, pos[1], pos[2]))
            else:
                joint_api.GetAxisAttr().Set("Z" if joint_api.GetAxisAttr().Get() != "Z" else "X")
    sim.reset()
    snapshots = []
    for index, robot in enumerate(robots):
        robot.update(.005)
        snapshots.append(coordinate_snapshot(robot, joints, "after_sim_reset_before_state_write", initial_z, reject=False))
        if args.legacy_zero_check:
            actual = robot.data.body_pos_w.torch[0] - robot.data.body_pos_w.torch[0, robot.body_names.index("base_link")]
            expected = torch.as_tensor(np.array([positions[n] for n in robot.body_names]), dtype=torch.float32, device=sim.device)
            assert torch.allclose(actual, expected, atol=1e-5), "LEGACY_MOVED_STATE_COMPARED_WITH_ZERO"
        root_pose = torch.tensor([[0., index * 5., initial_z, 0., 0., 0., 1.]], device=sim.device)
        zero = torch.zeros_like(robot.data.joint_pos.torch)
        robot.write_root_pose_to_sim_index(root_pose=root_pose)
        robot.write_root_velocity_to_sim_index(root_velocity=torch.zeros((1, 6), device=sim.device))
        robot.write_joint_state_to_sim_index(position=zero, velocity=zero)
        robot.reset()
        robot.update(0.)
        snapshots.append(coordinate_snapshot(robot, joints, "explicit_zero_no_physics_step", initial_z))
        assert robot.data.joint_pos.torch.abs().max() < 1e-7
    if args.coordinates_only:
        for robot in robots:
            target = torch.full_like(robot.data.joint_pos.torch, .03)
            robot.write_joint_state_to_sim_index(position=target, velocity=torch.zeros_like(target))
            robot.update(0.)
            snapshots.append(coordinate_snapshot(robot, joints, "written_nonzero_no_physics_step", initial_z))
            robot.set_joint_position_target_index(target=target)
            robot.write_data_to_sim()
        sim.step()
        for robot in robots:
            robot.update(.005)
            snapshots.append(coordinate_snapshot(robot, joints, "after_one_physics_step_actual_q", initial_z))
        asset_chain = asset_chain_snapshot(stage, joints, links, snapshots, probe) if args.blender_snapshot else None
        identity["completed"] = True
        report = {"status": "COORDINATES_VALIDATED_NOT_PD", "identity": identity, "snapshots": snapshots,
                  "asset_chain": asset_chain,
                  "source_sha256": probe["source_sha256"], "urdf_sha256": binding.sha256_file(urdf),
                  "usd_sha256": binding.sha256_file(usd), "code_sha256": binding.sha256_file(Path(__file__)),
                  "code_revision": binding.git_rev(Path(__file__).resolve().parents[3]),
                  "inject_error": args.inject_error, "self_collision": True, "filtered_connections": filtered}
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print("COORDINATES_COMPLETE", args.output, flush=True)
        return
    if args.collision_only:
        if args.collision_negative:
            for robot in robots:
                zero = torch.zeros_like(robot.data.joint_pos.torch)
                zero[0, robot.joint_names.index("chest_yaw_joint")] = .6
                robot.write_joint_state_to_sim_index(position=zero, velocity=torch.zeros_like(zero))
                robot.set_joint_position_target_index(target=zero)
        else:
            for robot in robots:
                robot.set_joint_position_target_index(target=torch.zeros_like(robot.data.joint_pos.torch))
        for robot in robots:
            robot.write_data_to_sim()
        sim.step()
        for robot in robots:
            robot.update(.005)
        pairs = []
        for index, a, b, sensor in pair_sensors:
            sensor.update(.005, force_recompute=True)
            force = sensor.data.force_matrix_w.torch[0, 0, 0]
            pairs.append({"case": index, "links": [a, b], "force_n": force.tolist(),
                          "contact_pos_m": sensor.data.contact_pos_w.torch[0, 0, 0].tolist(),
                          "filtered": (a, b) in filtered or (b, a) in filtered})
        if args.collision_negative:
            for index in range(len(robots)):
                observed = [p for p in pairs if p["case"] == index and p["links"] == ["lf_wrist", "rl_ankle"]]
                assert observed and max(np.linalg.norm(p["force_n"]) for p in observed) > 1., "Required cross-leg collision missing"
        elif args.filter_connections:
            assert all(np.linalg.norm(p["force_n"]) < 1e-3 for p in pairs), "Neutral collision remains"
        identity["completed"] = True
        result = {"status": "COLLISION_ATTRIBUTION_DIAGNOSTIC", "identity": identity, "pairs": pairs,
                  "negative": args.collision_negative, "filtered_connections": filtered,
                  "filter_readback": filter_readback,
                  "self_collision": True, "steps": 1}
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
        print("COLLISION_DIAGNOSTIC_COMPLETE", args.output, flush=True)
        return
    if args.inertia_only:
        robot = robots[0]
        if args.inertia_pose:
            target = torch.full_like(robot.data.joint_pos.torch, args.inertia_pose)
            robot.write_joint_state_to_sim_index(position=target, velocity=torch.zeros_like(target))
            robot.update(0.)
            snapshots.append(coordinate_snapshot(robot, joints, "inertia_pose_no_physics_step", initial_z))
        actor = robot.data.body_link_pose_w.torch[0].cpu().numpy()
        mass_live = robot.data.body_mass.torch[0].cpu().numpy()
        tensors = robot.data.body_inertia.torch[0].cpu().numpy().reshape(-1, 3, 3)
        com_local = robot.data.body_com_pos_b.torch[0].cpu().numpy()
        principal_quat = robot.data.body_com_quat_b.torch[0].cpu().numpy()
        link_results = {}
        authored = {p.GetName(): p for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)}
        for i, name in enumerate(robot.body_names):
            expected_com = com[name] - positions[name]
            mass_api = UsdPhysics.MassAPI(authored[name])
            usd_diagonal = np.diag(list(mass_api.GetDiagonalInertiaAttr().Get()))
            usd_quat = mass_api.GetPrincipalAxesAttr().Get()
            usd_rot = pose_matrix(np.r_[np.zeros(3), list(usd_quat.GetImaginary()), usd_quat.GetReal()])[:3, :3]
            link_results[name] = {
                "mass_kg": float(mass_live[i]), "mass_delta_kg": float(mass_live[i] - masses[name]),
                "com_local_m": com_local[i].tolist(), "com_delta_m": (com_local[i] - expected_com).tolist(),
                "raw_tensor": tensors[i].tolist(), "principal_quat_xyzw": principal_quat[i].tolist(),
                "raw_vs_urdf_max": float(np.abs(tensors[i] - inertia[name]).max()),
                "usd_tensor_forward_vs_live": float(np.abs(usd_rot @ usd_diagonal @ usd_rot.T - tensors[i]).max()),
                "usd_tensor_inverse_vs_urdf": float(np.abs(usd_rot.T @ usd_diagonal @ usd_rot - inertia[name]).max()),
            }
            assert np.isclose(mass_live[i], masses[name], rtol=2e-6, atol=1e-7), "Link mass mismatch: " + name
            assert np.allclose(com_local[i], expected_com, rtol=0., atol=2e-6), "Link COM mismatch: " + name
        projected = np.zeros((robot.num_joints, robot.num_joints))
        projected_urdf = np.zeros_like(projected)
        for i, name in enumerate(robot.body_names):
            rotation = pose_matrix(actor[i])[:3, :3]
            center = rotation @ com_local[i] + actor[i, :3]
            linear = np.zeros((3, robot.num_joints))
            angular = np.zeros_like(linear)
            for j, joint_name in enumerate(robot.joint_names):
                child = joint_name.removesuffix("_joint")
                if child in paths[name]:
                    frame = pose_matrix(actor[robot.body_names.index(child)])
                    axis = frame[:3, :3] @ axes[child]
                    angular[:, j] = axis
                    linear[:, j] = np.cross(axis, center - frame[:3, 3])
            shift = mass_live[i] * linear.T @ linear
            projected += angular.T @ rotation @ tensors[i] @ rotation.T @ angular + shift
            projected_urdf += angular.T @ rotation @ inertia[name] @ rotation.T @ angular + shift
        matrix = robot.data.mass_matrix.torch[0].cpu().numpy()
        joint_block = matrix[-robot.num_joints:, -robot.num_joints:]
        assert np.allclose(joint_block, projected, rtol=1e-4, atol=3e-5), "Runtime tensor mass matrix mismatch"
        if args.normalize_inertia or args.require_inertia_match:
            assert max(v["raw_vs_urdf_max"] for v in link_results.values()) < 1e-5, "Normalized link inertia mismatch"
            assert np.allclose(joint_block, projected_urdf, rtol=1e-4, atol=3e-5), "URDF tensor mass matrix mismatch"
        elif not args.normalize_inertia:
            assert max(v["usd_tensor_forward_vs_live"] for v in link_results.values()) < 1e-5
        assert max(v["usd_tensor_inverse_vs_urdf"] for v in link_results.values()) < 1e-5
        identity["completed"] = True
        result = {
            "status": "ISOLATED_ASSET_INERTIA_VALIDATED" if args.require_inertia_match else
                      "INERTIA_NORMALIZED_CONTROL_VALIDATED" if args.normalize_inertia else
                      "IMPORTER_INERTIA_BASIS_MISMATCH_VERIFIED",
            "identity": identity, "normalize_inertia": args.normalize_inertia,
            "inertia_pose_rad": args.inertia_pose, "links": link_results, "snapshots": snapshots,
            "joint_order": robot.joint_names, "mass_matrix_shape": list(matrix.shape),
            "joint_block": joint_block.tolist(), "projected_runtime_tensor": projected.tolist(),
            "projected_urdf_tensor": projected_urdf.tolist(),
            "matrix_budget": {"rtol": 1e-4, "atol_kg_m2": 3e-5},
            "source_sha256": probe["source_sha256"], "code_sha256": binding.sha256_file(Path(__file__)),
        }
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
        print("INERTIA_DIAGNOSTIC_COMPLETE", args.output, flush=True)
        return


try:
    main()
except BaseException:
    import traceback

    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)
finally:
    app.close()
