# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Isolated checkpoint wiring diagnostic; no PD, tracking or load-bearing verdict [rad, m]."""
from __future__ import annotations

import argparse
import ast
import copy
import json
import math
import os
from pathlib import Path
import shutil
import sys
import traceback

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "rl_exp/tasks"))
from rl_exp.tools.runrecord import binding
from rl_exp.tools.diagnose.artifact_paths import ArtifactPaths
import joint_names
import obs_protocol
import xml.etree.ElementTree as ET

BUILD = REPO / "rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json"
OUT = REPO / "rl_exp/out/lizard2_e_spatial_20261015"
URDF_HASH = "2c78117020458d5e7934219a2064bf7241430b81c2a736acd8cc0761c7a1461f"
BLEND_HASH = "beeac4c09726260bf392a6ecc81a04ebcf9b54a210416493bbb2689c4909cdea"
DIAGNOSTIC_TASK = "PalmSpatial-Wiring-Diagnostic"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_build(path):
    paths = ArtifactPaths()
    require(paths.same_identity(path, BUILD), "only checkpoint_v3/build.json is authorized")
    path = paths.resolve(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    require(doc["naming"] == "palm_spatial", "wrong naming")
    files = doc["candidate_files_sha256"]
    require(len(files) == 38, "checkpoint must bind 38 files")
    require(doc["candidate_sha256"] == files["palm_spatial.urdf"] == URDF_HASH, "URDF binding mismatch")
    require(doc["candidate_blend_sha256"] == files["palm_spatial.blend"] == BLEND_HASH, "blend binding mismatch")
    require(paths.same_identity(Path(doc["candidate_urdf"]), BUILD.parent / "palm_spatial.urdf"),
            "candidate path mismatch")
    for name, digest in files.items():
        source = (path.parent / name).resolve()
        require(source.is_relative_to(path.parent.resolve()), "checkpoint path escape")
        require(binding.sha256_file(source) == digest, "checkpoint hash mismatch: " + name)
    return doc


def check_export(path, approved_report, approved_urdf):
    """Bind explicit approval to every export file before copying or starting Kit."""
    path = path.resolve()
    require(path.is_relative_to((REPO / "rl_exp/out").resolve()), "export report must be isolated")
    require(approved_report and approved_urdf, "independent export and URDF approvals required")
    require(binding.sha256_file(path) == approved_report, "export report approval mismatch")
    doc = json.loads(path.read_text(encoding="utf-8"))
    require(doc["status"] == "KINEMATIC_CANDIDATE_NOT_ADOPTED"
            and doc["naming"] == "palm_spatial" and doc["robot"] == "lizard2_palm_spatial",
            "export identity mismatch")
    require(doc["mass_policy"] == "reference_full_link_inertial"
            and doc["links"] == 31 and doc["joints"] == 30, "export structure mismatch")
    paths = ArtifactPaths()
    approved_sources = {"build_report": (BUILD, "59473f8c345dce48e8ee379c0972c928184f768be85afca948ac812a666fa6f8"),
                        "source_blend": (BUILD.parent / "palm_spatial.blend", BLEND_HASH),
                        "reference_urdf": (BUILD.parent / "palm_spatial.urdf", URDF_HASH)}
    for field, (source, digest) in approved_sources.items():
        require(paths.same_identity(Path(doc[field]), source), "export source path mismatch: " + field)
        require(doc["input_sha256"].get(doc[field]) == digest
                and binding.sha256_file(paths.resolve(source)) == digest, "export source hash mismatch: " + field)
    check_build(BUILD)
    files = doc["files_sha256"]
    urdf_name = "lizard2_palm_spatial.urdf"
    require(files.get(urdf_name) == approved_urdf, "export URDF approval mismatch")
    sources = set()
    for name, digest in files.items():
        relative = Path(name)
        source = (path.parent / relative).resolve()
        require(not relative.is_absolute() and ".." not in relative.parts
                and source.is_relative_to(path.parent) and source not in sources,
                "export file path escape/alias")
        require(name == urdf_name or (relative.parts[0] == "meshes" and relative.suffix in (".obj", ".stl")),
                "unexpected export file")
        sources.add(source)
        require(binding.sha256_file(source) == digest, "export file hash mismatch: " + name)
    tree = ET.parse(path.parent / urdf_name).getroot()
    reference = ET.parse(paths.resolve(BUILD.parent / "palm_spatial.urdf")).getroot()
    def attributes(element):
        require(element is not None, "missing export/reference XML element")
        # Attribute order and whitespace text/tails are serialization, not URDF values.
        require(not (element.text or "").strip(), "unexpected URDF element text")
        return element.tag, dict(element.attrib), [attributes(child) for child in element]

    require([attributes(j) for j in tree.findall("joint")] ==
            [attributes(j) for j in reference.findall("joint")], "export joint definitions differ")
    links = tree.findall("link")
    require([l.get("name") for l in links] == [l.get("name") for l in reference.findall("link")],
            "export link order differs")
    for actual, expected in zip(links, reference.findall("link")):
        require(attributes(actual.find("inertial")) == attributes(expected.find("inertial")),
                "export full inertia differs: " + actual.get("name"))
    refs = set()
    for mesh in tree.findall(".//mesh"):
        name = mesh.get("filename")
        require(name in files and Path(name).parts[0] == "meshes", "unbound export mesh")
        refs.add(name)
    require(refs and len(files) == 73, "export file coverage mismatch")
    return doc


def fresh_export_out(out, source):
    out = out.resolve()
    root = (REPO / "rl_exp/out").resolve()
    require(out.is_relative_to(root) and out != root and not out.exists()
            and not source.resolve().is_relative_to(out), "fresh isolated export output required")
    require(out.parent.is_dir(), "output parent must already exist")
    return out


def export_self_check(args):
    """Exercise approved files and real corruptions offline; temporary copies are removed."""
    from tempfile import TemporaryDirectory
    from unittest.mock import patch

    path = args.export_report.resolve()
    approved = args.approved_export_sha256
    urdf_hash = args.approved_urdf_sha256
    doc = check_export(path, approved, urdf_hash)
    negatives = {}

    def rejected(label, operation, expected):
        try:
            operation()
        except (ValueError, FileNotFoundError) as error:
            require(expected in str(error), label + " unexpected rejection: " + str(error))
            negatives[label] = str(error)
        else:
            raise ValueError("export destructive test escaped: " + label)

    # Approval must fail before report/URDF parsing, not merely later validation.
    with patch.object(json, "loads", side_effect=AssertionError("parsed unapproved report")):
        rejected("wrong_report_approval", lambda: check_export(path, "0" * 64, urdf_hash),
                 "export report approval mismatch")
    with patch.object(ET, "parse", side_effect=AssertionError("parsed unapproved URDF")):
        rejected("wrong_urdf_approval", lambda: check_export(path, approved, "0" * 64),
                 "export URDF approval mismatch")
    with TemporaryDirectory(prefix="palm_export_check_", dir=REPO / "rl_exp/out") as temporary:
        root = Path(temporary)
        copied = root / "export.json"
        for name in doc["files_sha256"]:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path.parent / name, target)
        shutil.copyfile(path, copied)
        check_export(copied, approved, urdf_hash)
        mesh = next(name for name in doc["files_sha256"] if name.endswith(".obj"))
        (root / mesh).unlink()
        rejected("missing_artifact", lambda: check_export(copied, approved, urdf_hash), mesh)
        shutil.copyfile(path.parent / mesh, root / mesh)
        name = "lizard2_palm_spatial.urdf"
        # Reapprove each corrupted report/URDF: semantic checks, not hashes, must reject it.
        for element, key in (("inertia", "ixx"), ("inertia", "iyy"), ("inertia", "izz"),
                             ("inertia", "ixy"), ("inertia", "ixz"), ("inertia", "iyz"),
                             ("mass", "value"), ("origin", "xyz"), ("origin", "rpy")):
            tree = ET.parse(path.parent / name)
            spec = tree.getroot().find("link/inertial/" + element)
            require(spec is not None, "self-check missing inertial element")
            spec.set(key, "1 2 3" if element == "origin" else str(float(spec.get(key)) + 1.))
            tree.write(root / name, encoding="utf-8", xml_declaration=True)
            broken = copy.deepcopy(doc)
            digest = binding.sha256_file(root / name)
            broken["files_sha256"][name] = digest
            copied.write_text(json.dumps(broken), encoding="utf-8")
            rejected("full_inertial_" + key,
                     lambda: check_export(copied, binding.sha256_file(copied), digest),
                     "export full inertia differs")
        broken = copy.deepcopy(doc)
        broken["input_sha256"][broken["source_blend"]] = "0" * 64
        copied.write_text(json.dumps(broken), encoding="utf-8")
        rejected("old_source_binding", lambda: check_export(copied, binding.sha256_file(copied), urdf_hash),
                 "export source hash mismatch")
        require(fresh_export_out(root / "fresh", path.parent) == root / "fresh", "fresh output positive failed")
        for label, out, source in (("existing_output", root, path.parent),
                                   ("source_inside_output", root / "fresh", root / "fresh/source"),
                                   ("outside_output", REPO / "unauthorized", path.parent),
                                   ("missing_parent", root / "missing/fresh", path.parent)):
            rejected(label, lambda: fresh_export_out(out, source),
                     "output parent" if label == "missing_parent" else "fresh isolated")
    print(json.dumps({"export_self_check": "PASS", "files_verified": len(doc["files_sha256"]),
                      "approved_export_sha256": approved, "approved_urdf_sha256": urdf_hash,
                      "negatives": negatives, "scope": "real export validation; no USD conversion/runtime"}), flush=True)


def exact_channels(expected, names, ids, runtime):
    require(len(names) == len(set(names)) and set(names) == set(expected), "action coverage/duplicate mismatch")
    require(len(ids) == len(names), "action ids width mismatch")
    require(all(runtime[i] == name for name, i in zip(names, ids)), "action name/id mismatch")


def close_values(actual, expected, budget, label):
    require(len(actual) == len(expected), label + " width mismatch")
    require(all(math.isfinite(a) and math.isfinite(b) and abs(a - b) <= budget
                for a, b in zip(actual, expected)), label + " readback mismatch")


def pair_binding(sensor_paths, filter_paths, source, owners, shape):
    """Validate actual registered single-body rows and single-owner columns before naming forces."""
    def singleton(paths):
        require(isinstance(paths, (list, tuple)), "contact pair path container mismatch")
        return [p if isinstance(p, str) else p[0]
                if isinstance(p, (list, tuple)) and len(p) == 1 and isinstance(p[0], str)
                else None for p in paths]
    rows = singleton(sensor_paths)
    require(rows == [source], "contact pair source binding mismatch")
    require(isinstance(filter_paths, (list, tuple)), "contact pair filter container mismatch")
    # Actual backend layout: one sensor row containing its filter columns, not singleton columns.
    if (len(filter_paths) == 1 and isinstance(filter_paths[0], (list, tuple))
            and len(filter_paths[0]) == len(owners)
            and all(isinstance(p, str) for p in filter_paths[0])):
        columns = list(filter_paths[0])
    else:
        columns = singleton(filter_paths)
    require(len(columns) == len(owners) and len(set(columns)) == len(columns)
            and set(columns) == set(owners), "contact pair filter binding mismatch")
    require(tuple(shape) == (1, len(columns), 3), "contact pair matrix shape mismatch")
    return columns


def self_check():
    doc = check_build(BUILD)
    names = [j.get("name") for j in ET.parse(ArtifactPaths().resolve(
        BUILD.parent / "palm_spatial.urdf")).getroot().findall("joint")]
    runtime = list(reversed(names))
    ids = [runtime.index(n) for n in names]
    exact_channels(names, names, ids, runtime)
    close_values([.05, -.05], [.05, -.05], 1e-6, "state")
    broken = 0
    for bad_names, bad_ids in ((names[:-1], ids[:-1]), (names + names[:1], ids + ids[:1]),
                               (names, ids[1:] + ids[:1])):
        try:
            exact_channels(names, bad_names, bad_ids, runtime)
        except ValueError:
            broken += 1
    try:
        close_values([.05, .05], [.05, -.05], 1e-6, "state")
    except ValueError:
        broken += 1
    from unittest.mock import patch
    with patch.object(binding, "sha256_file", return_value="0" * 64):
        try:
            check_build(BUILD)
        except ValueError:
            broken += 1
    require(broken == 5, "destructive test escaped")
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace as NS
    v3_task = "Lizard2-Flat-Play-v3"
    require(DIAGNOSTIC_TASK != v3_task, "dedicated diagnostic must not claim v3 identity")
    original = obs_protocol.body_for_task(v3_task)
    cfg = NS(scene=NS(robot=NS(spawn=NS(usd_path=str(original["usd"])))))
    loader_negatives = {}
    with TemporaryDirectory(prefix="palm_spatial_self_check_") as temporary:
        manifest = Path(temporary) / "manifest.json"
        write_json(manifest, {"target_binding": {"task": DIAGNOSTIC_TASK}})
        for task, expected in ((DIAGNOSTIC_TASK, "no declared family"),
                               (v3_task, f"task {DIAGNOSTIC_TASK!r} != {v3_task!r}")):
            try:
                obs_protocol.load_diagnostic_target(manifest, cfg, task)
            except obs_protocol.ProtocolError as error:
                require(expected in str(error), "unexpected loader rejection: " + str(error))
                loader_negatives[task] = str(error)
            else:
                raise ValueError("loader accepted dedicated diagnostic as " + task)
    owners = ["/Robot/a", "/Robot/b"]
    columns = pair_binding([[owners[0]]], [[owners[1]], [owners[0]]], owners[0], owners, (1, 2, 3))
    encoded = {name: force for name, force in zip(columns, [202, 101])}
    require(encoded == {owners[0]: 101, owners[1]: 202}, "encoded contact column shift")
    pair_negatives = 0
    for rows, cols, shape in (([owners[1]], owners, (1, 2, 3)),
                              ([owners[0]], [owners[0], owners[0]], (1, 2, 3)),
                              ([owners[0]], owners, (2, 1, 3)),
                              ([owners[0]], [[owners[0], owners[1]], [owners[1]]], (1, 2, 3))):
        try:
            pair_binding(rows, cols, owners[0], owners, shape)
        except ValueError:
            pair_negatives += 1
    require(pair_negatives == 4, "contact binding destructive test escaped")
    # Frozen attempt05/contact_pair_raw_01.json: backend returns one sensor row, 18 body paths.
    actual_owners = ["/World/envs/env_0/Robot/Geometry/" + name for name in (
        "base_link", "chest_pitch", "tail1_pitch", "rl_hip_twist", "rr_hip_twist",
        "neck_pitch", "tail2_pitch", "rl_knee", "rr_knee", "lf_shoulder_twist",
        "rf_shoulder_twist", "rl_ankle", "rr_ankle", "lf_elbow", "rf_elbow",
        "tail3_pitch", "lf_wrist", "rf_wrist")]
    actual_columns = pair_binding([actual_owners[0]], [actual_owners], actual_owners[0],
                                  actual_owners, (1, 18, 3))
    require(actual_columns == actual_owners, "actual backend column order changed")
    actual_negatives = 0
    for cols in ([actual_owners] * 18, [[actual_owners]], [actual_owners[:-1]],
                 [actual_owners[:-1] + actual_owners[:1]]):
        try:
            pair_binding([actual_owners[0]], cols, actual_owners[0], actual_owners, (1, 18, 3))
        except ValueError:
            actual_negatives += 1
    require(actual_negatives == 4, "actual backend binding destructive test escaped")
    approved_filters = [["base_link", "tail1_pitch"], ["tail1_pitch", "tail2_pitch"]]
    check_filter_pairs(approved_filters, approved_filters)
    for bad in (approved_filters[:-1], approved_filters + [["lf_wrist", "rl_ankle"]],
                [approved_filters[0], approved_filters[0]]):
        try:
            check_filter_pairs(bad, approved_filters)
        except ValueError:
            pass
        else:
            raise ValueError("filter set negative escaped")
    import subprocess
    source = Path(__file__).read_text(encoding="utf-8")
    function = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == "reset_probe")
    actual_branch = next(n for n in function.body if isinstance(n, ast.Try))
    writer = next(n for n in ast.parse(source).body
                  if isinstance(n, ast.FunctionDef) and n.name == "write_json")
    exit_checks = {}
    with TemporaryDirectory(prefix="palm_spatial_exit_branch_") as temporary:
        for variant, expected_code in (("before", 0), ("after", 1), ("success", 0)):
            branch = copy.deepcopy(actual_branch)
            branch.body = ast.parse("pass" if variant == "success" else
                                    "raise ValueError('exit-branch-only')").body
            if variant == "before":
                handler = branch.handlers[0]
                persist = next(i for i, n in enumerate(handler.body)
                               if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                               and isinstance(n.value.func, ast.Name) and n.value.func.id == "write_json")
                handler.body = handler.body[:persist + 1] + [ast.Raise()]
            out = Path(temporary) / variant
            out.mkdir()
            program = ("import os, sys, json, traceback\nfrom pathlib import Path\n"
                       "from types import SimpleNamespace as NS\n"
                       f"out = Path({str(out)!r})\nargs = NS(contact_pairs=True)\n"
                       "result = {'completed': True, 'stage': 'exit_branch_only'}\n"
                       "env = NS(close=lambda: print('ENV_CLOSE', flush=True))\n"
                       "def close():\n    print('APP_CLOSE', flush=True)\n    os._exit(0)\n"
                       "app = NS(close=close)\n" + ast.unparse(writer) + "\n" + ast.unparse(branch))
            child = subprocess.run([sys.executable, "-B", "-c", program],
                                   capture_output=True, text=True, timeout=30)
            require(child.returncode == expected_code, variant + " exit branch wrong code")
            failure = out / "reset_probe_failure.json"
            if variant != "success":
                saved = json.loads(failure.read_text(encoding="utf-8"))
                require(not saved["completed"] and saved["contact_pairs"]["status"] == "unknown"
                        and "exit-branch-only" in saved["traceback"], "exit failure persistence mismatch")
            require(("APP_CLOSE" in child.stdout) == (variant != "after"), "close branch mismatch")
            require(("ENV_CLOSE" in child.stdout) == (variant != "after"), "env close branch mismatch")
            require(("RUNTIME_FAILED" in child.stdout) == (variant == "after"), "failure print mismatch")
            require(variant != "after" or "ValueError: exit-branch-only" in child.stderr,
                    "failure traceback missing")
            require(variant != "success" or not failure.exists(), "success wrote failure")
            exit_checks[variant] = child.returncode
    print(json.dumps({"self_check": "PASS", "files_verified": len(doc["candidate_files_sha256"]),
                      "negative_cases": broken, "loader_negatives": loader_negatives,
                      "pair_binding_negative_cases": pair_negatives,
                      "actual_backend_binding": {"sensor_count": 1, "filter_count": len(actual_columns),
                                                 "layout": "one_sensor_row", "negative_cases": actual_negatives},
                      "exit_branch_codes": exit_checks,
                      "exit_branch_scope": "actual AST handler/finally; stub close exits 0; not PhysX negative",
                      "pair_scope": "CPU column encoding only; not PhysX mapping proof"}), flush=True)


def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


REGISTERED_OUT = REPO / "rl_exp/out/lizard2_e_registered_20261015"
REGISTERED_TASK = "Lizard2-Flat-Play-v3"
REGISTERED_INPUT = OUT / "attempt06"
FIXED_USD_HASH = "40f37d124d17f69b201c06f49173681367370a66a38431bcbda3d5e1192f3f79"


def check_registered_manifest(path, *, measured_order=True):
    """Exercise the real registered loader offline, including drive/action coverage."""
    import rl_exp.tasks
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg

    cfg = copy.deepcopy(resolve_task_cfg(REGISTERED_TASK))
    target = obs_protocol.load_diagnostic_target(path, cfg, REGISTERED_TASK)
    names = target["joint_names"]
    carried = []
    tree = ET.parse(target["urdf"]).getroot()
    limits = {j.get("name"): j.find("limit") for j in tree.findall("joint")}
    for actuator in cfg.scene.robot.actuators.values():
        selected = actuator.joint_names_expr
        require(isinstance(selected, list) and set(selected) <= set(names), "actuator selection mismatch")
        carried.extend(selected)
        for field in ("stiffness", "damping", "armature"):
            require(getattr(actuator, field) == 0., "nonzero actuator " + field)
        for field, key in (("effort_limit", "effort"), ("velocity_limit", "velocity"),
                           ("effort_limit_sim", "effort"), ("velocity_limit_sim", "velocity")):
            require(getattr(actuator, field) == {n: float(limits[n].get(key)) for n in selected},
                    "actuator URDF limit mismatch: " + field)
    require(len(carried) == len(names) and set(carried) == set(names), "actuator overlap/coverage mismatch")
    actions = []
    for term in vars(cfg.actions).values():
        if term is None:
            continue
        require(term.scale == 1. and term.preserve_order and term.use_default_offset,
                "action scale/order/default offset mismatch")
        require(term.offset == 0. and term.clip is None, "action offset/clip mismatch")
        actions.extend(term.joint_names)
    require(len(actions) == len(names) and len(set(actions)) == len(names) and set(actions) == set(names),
            "action overlap/coverage mismatch")
    robot = cfg.scene.robot
    require(robot.init_state.pos == [0., 0., 2.], "spawn position mismatch")
    for field in ("joint_pos", "joint_vel"):
        require(getattr(robot.init_state, field) == {n: 0. for n in names}, "default " + field)
    require(robot.spawn.rigid_props.disable_gravity is True, "gravity enabled")
    require(robot.spawn.articulation_props.fix_root_link is None, "fixed root adapter override")
    require(robot.spawn.articulation_props.enabled_self_collisions is True, "self collision disabled")
    document = json.loads(path.read_text(encoding="utf-8"))
    repaired = document.get("format") == "palm-spatial-registered-diagnostic-v2"
    if repaired:
        from isaaclab.envs import mdp
        resets = {"reset_base", "reset_robot_joints"}
        require({name for name, term in vars(cfg.events).items() if term is not None} == resets,
                "unexpected reset/randomization event")
        root, joints = cfg.events.reset_base, cfg.events.reset_robot_joints
        require(root.func is mdp.reset_root_state_uniform and root.mode == "reset", "root reset writer mismatch")
        require(joints.func is mdp.reset_joints_by_scale and joints.mode == "reset", "joint reset writer mismatch")
        require(joints.params["position_range"] == [1., 1.]
                and joints.params["velocity_range"] == [0., 0.], "joint reset is not deterministic")
        for field in ("pose_range", "velocity_range"):
            require(root.params[field] == {axis: [0., 0.] for axis in
                    ("x", "y", "z", "roll", "pitch", "yaw")}, "root reset is not deterministic")
    else:
        require(all(term is None for term in vars(cfg.events).values()), "active reset/randomization event")
    require(target["end_links"] == dict(zip(joint_names.LEGS, joint_names.contact_body_names(joint_names.PALM_SPATIAL_NAMING))),
            "foreign end link")
    if measured_order:
        require(target["runtime_joint_order"] == json.loads(
            (REGISTERED_INPUT / "runtime_report.json").read_text())["mapping"]["runtime_joint_order"],
            "runtime order not measured input")
    else:
        require(target["runtime_joint_order"] is None, "fresh export must not inherit old runtime order")
    return {"status": "PASS", "task": REGISTERED_TASK, "joints": len(names),
            "actions": len(actions), "actuators": list(robot.actuators), "feet": target["end_links"]}


def prepare_registered(args):
    """Prepare an isolated replay manifest without starting AppLauncher or editing recipes."""
    build = ArtifactPaths().resolve(BUILD)
    out = args.out.resolve()
    require(out.parent == REGISTERED_OUT.resolve(), "only registered output attempt allowed")
    require(not out.exists(), "registered output already exists")
    report_path = REGISTERED_INPUT / "runtime_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    old = json.loads((REGISTERED_INPUT / "manifest.json").read_text(encoding="utf-8"))
    require(report["completed"] and report["input"]["build_sha256"] == binding.sha256_file(build),
            "completed checkpoint measurement required")
    usd, urdf = REGISTERED_INPUT / "palm_spatial.usda", REGISTERED_INPUT / "palm_spatial.urdf"
    require(binding.sha256_file(usd) == FIXED_USD_HASH and binding.sha256_file(urdf) == URDF_HASH,
            "registered input hash mismatch")
    require(old["target_binding"]["task"] == DIAGNOSTIC_TASK, "old diagnostic identity changed")
    names = old["joint_order"]
    joints = ET.parse(urdf).getroot().findall("joint")
    require(names == [j.get("name") for j in joints], "URDF order mismatch")
    runtime = report["mapping"]["runtime_joint_order"]
    require(len(runtime) == len(names) and set(runtime) == set(names), "measured runtime order mismatch")
    manifest = out / "registered_manifest.json"
    target = joint_names.binding_for_target(str(usd), str(manifest), joint_names.PALM_SPATIAL_NAMING,
                                           joint_names=names)
    target.update(task=REGISTERED_TASK, urdf=str(urdf), runtime_joint_order=runtime)
    config = registered_config(names, joints)
    document = {"format": "palm-spatial-registered-diagnostic-v2", "target_binding": target,
                "joint_order": names, "runtime_joint_order": runtime, "config": config,
                "sha256": {"target": FIXED_USD_HASH, "urdf": URDF_HASH},
                "scope": "registered mother routing only; isolated deepcopy; no recipe/PD/support/performance verdict",
                "input": {"runtime_report": str(report_path), "runtime_report_sha256": binding.sha256_file(report_path),
                          "old_manifest_sha256": binding.sha256_file(REGISTERED_INPUT / "manifest.json"),
                          "build": str(BUILD), "build_sha256": binding.sha256_file(build)}}
    out.mkdir(parents=True, exist_ok=False)
    write_json(manifest, document)
    verify_registered(manifest)


def registered_config(names, joints):
    """Reuse the deterministic zero-gain mother routing; no runtime order is inferred."""
    legs = [n for n in names if n.split("_", 1)[0] in joint_names.LEGS]
    ends = [joint_names.joint_name(leg, joint_names.roots_of(joint_names.PALM_SPATIAL_NAMING, leg)[-1])
            for leg in joint_names.LEGS]
    spine = [n for n in names if n not in legs]
    config = {
        "scene.num_envs": 1,
        "scene.robot.init_state.pos": [0., 0., 2.],
        "scene.robot.init_state.rot": [0., 0., 0., 1.],
        "scene.robot.init_state.lin_vel": [0., 0., 0.],
        "scene.robot.init_state.ang_vel": [0., 0., 0.],
        "scene.robot.init_state.joint_pos": {n: 0. for n in names},
        "scene.robot.init_state.joint_vel": {n: 0. for n in names},
        "scene.robot.spawn.rigid_props.disable_gravity": True,
        "scene.robot.spawn.articulation_props.fix_root_link": None,
        "scene.robot.spawn.articulation_props.enabled_self_collisions": True,
        "actions.joint_pos": None,
        "rewards.undesired_contacts.params.sensor_cfg.body_names": [
            joint_names.link_name(leg, root) for leg in joint_names.LEGS
            for root in joint_names.roots_of(joint_names.PALM_SPATIAL_NAMING, leg)[2:4]],
    }
    import rl_exp.tasks
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg
    mother = resolve_task_cfg(REGISTERED_TASK)
    require(set(mother.scene.robot.actuators) == {"legs", "feet", "spine"}, "mother actuator layout changed")
    require(set(vars(mother.actions)) == {"joint_pos", "joint_pos_legs", "joint_pos_spine"},
            "mother action layout changed")
    limits = {j.get("name"): j.find("limit") for j in joints}
    for group, selected in (("legs", [n for n in legs if n not in ends]), ("feet", ends), ("spine", spine)):
        prefix = "scene.robot.actuators." + group + "."
        config[prefix + "joint_names_expr"] = selected
        for field in ("stiffness", "damping", "armature", "friction", "dynamic_friction", "viscous_friction"):
            config[prefix + field] = 0.
        for field, key in (("effort_limit", "effort"), ("velocity_limit", "velocity"),
                           ("effort_limit_sim", "effort"), ("velocity_limit_sim", "velocity")):
            config[prefix + field] = {n: float(limits[n].get(key)) for n in selected}
    for term, selected in (("joint_pos_legs", legs), ("joint_pos_spine", spine)):
        prefix = "actions." + term + "."
        config.update({prefix + "joint_names": selected, prefix + "scale": 1., prefix + "offset": 0.,
                       prefix + "preserve_order": True, prefix + "use_default_offset": True,
                       prefix + "clip": None})
    config.update({"events." + name: None for name in vars(mother.events)
                   if name not in ("reset_base", "reset_robot_joints")})
    config.update({
        "events.reset_robot_joints.params.position_range": [1., 1.],
        "events.reset_robot_joints.params.velocity_range": [0., 0.],
        "events.reset_base.params.pose_range": {axis: [0., 0.] for axis in
                                               ("x", "y", "z", "roll", "pitch", "yaw")},
        "events.reset_base.params.velocity_range": {axis: [0., 0.] for axis in
                                                   ("x", "y", "z", "roll", "pitch", "yaw")},
    })
    return config


def verify_registered(manifest):
    """Re-read prepared manifest and persist real loader positive/negative results."""
    out = manifest.parent
    require(out.parent.resolve() == REGISTERED_OUT.resolve(), "unauthorized replay verification path")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    legs = document["config"]["actions.joint_pos_legs.joint_names"]
    positive = check_registered_manifest(manifest)
    negatives = {}
    defects = ["duplicate_joint", "missing_twist", "foreign_end", "mismatch_sha"]
    if document.get("format") == "palm-spatial-registered-diagnostic-v2":
        defects.append("missing_reset_writer")
    for defect in defects:
        broken = copy.deepcopy(document)
        path = out / ("negative_" + defect + ".json")
        broken["target_binding"]["source"] = str(path)
        if defect == "duplicate_joint":
            broken["config"]["actions.joint_pos_legs.joint_names"].append(legs[0])
        elif defect == "missing_twist":
            broken["target_binding"]["joint_names"].remove("lf_shoulder_twist_joint")
        elif defect == "foreign_end":
            broken["target_binding"]["end_links"]["lf"] = "lf_ankle"
        elif defect == "missing_reset_writer":
            for field in list(broken["config"]):
                if field.startswith("events.reset_robot_joints."):
                    del broken["config"][field]
            broken["config"]["events.reset_robot_joints"] = None
        else:
            broken["sha256"]["target"] = "0" * 64
        if path.exists():
            require(json.loads(path.read_text(encoding="utf-8")) == broken, "negative artifact changed")
        else:
            write_json(path, broken)
        try:
            check_registered_manifest(path)
        except (ValueError, obs_protocol.ProtocolError) as error:
            negatives[defect] = {"status": "REJECTED", "error": str(error)}
        else:
            raise ValueError("registered loader accepted " + defect)
    if not (out / "prepare_report.json").exists():
        shutil.copyfile(Path(__file__), out / "prepare_source.py")
        write_json(out / "prepare_report.json", {"positive": positive, "negatives": negatives,
            "manifest": str(manifest), "manifest_sha256": binding.sha256_file(manifest),
            "code_sha256": binding.sha256_file(Path(__file__)), "scope": document["scope"]})
    print("REGISTERED_PREPARED", json.dumps({"manifest": str(manifest), "positive": positive,
          "negatives": negatives, "current_code_sha256": binding.sha256_file(Path(__file__))}), flush=True)


def run(args, result):
    result["stage"] = "input"
    build = ArtifactPaths().resolve(BUILD)
    exported = args.export_report is not None
    if exported:
        doc = check_export(args.export_report, args.approved_export_sha256, args.approved_urdf_sha256)
        source = args.export_report.resolve().parent
        files = doc["files_sha256"]
        out = fresh_export_out(args.out, source)
    else:
        doc = check_build(args.build)
        source, files = build.parent, doc["candidate_files_sha256"]
        out = args.out.resolve()
        require(out == OUT.resolve() or out.parent == OUT.resolve(), "only authorized output tree allowed")
    out.mkdir(exist_ok=False)
    result["output"] = str(out)
    result["input"] = {"build": str(BUILD), "build_sha256": binding.sha256_file(build),
                       "candidate_files_sha256": files}
    if exported:
        result["input"].update(export_report=str(args.export_report.resolve()),
            export_report_sha256=args.approved_export_sha256, urdf_sha256=args.approved_urdf_sha256)
    result["code"] = {"path": str(Path(__file__).resolve()), "sha256": binding.sha256_file(Path(__file__)),
                      "revision": binding.git_rev(REPO)}
    for name in files:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        require(binding.sha256_file(target) == files[name], "copy mismatch")
    if exported:
        shutil.copyfile(out / "lizard2_palm_spatial.urdf", out / "palm_spatial.urdf")
        shutil.copyfile(args.export_report, out / "input_export.json")
    shutil.copyfile(build, out / "input_build.json")
    shutil.copyfile(Path(__file__), out / "runtime_source.py")
    tree = ET.parse(out / "palm_spatial.urdf").getroot()
    joints = tree.findall("joint")
    names = [j.get("name") for j in joints]
    limits = {j.get("name"): [float(j.find("limit").get(k)) for k in ("lower", "upper")] for j in joints}
    for name, bounds in limits.items():
        require(bounds[0] <= -.05 <= .05 <= bounds[1], "injection outside URDF limits: " + name)
    result["injection_limits_rad"] = limits
    result["stage"] = "app_launch"
    from isaaclab.app import AppLauncher
    launcher = AppLauncher(args)
    app = launcher.app
    import numpy as np
    import torch
    import isaaclab.sim as sim_utils
    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg
    from isaaclab.actuators import ImplicitActuatorCfg
    from isaaclab.assets import ArticulationCfg
    from isaaclab.sensors import ContactSensorCfg
    from isaaclab.scene import InteractiveSceneCfg
    from isaaclab.envs import ManagerBasedEnv, ManagerBasedEnvCfg, mdp
    from isaaclab.managers import ObservationGroupCfg, ObservationTermCfg, SceneEntityCfg
    from isaaclab.utils import configclass
    from pxr import Gf
    sys.path.insert(0, str(REPO / "rl_exp/tools/pipeline"))
    from flatten_usd import flatten_usd

    result["stage"] = "conversion"
    converter = UrdfConverter(UrdfConverterCfg(
        asset_path=str(out / "palm_spatial.urdf"), usd_dir=str(out), usd_file_name="palm_spatial.usda",
        fix_base=False, merge_fixed_joints=False, force_usd_conversion=True, self_collision=True,
        run_asset_transformer=False, run_multi_physics_conversion=False,
        joint_drive=UrdfConverterCfg.JointDriveCfg(target_type="position",
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=0., damping=0.))))
    usd = Path(converter.usd_path).resolve()
    require(usd.is_relative_to(out) and usd.is_file(), "converter output escaped")
    from pxr import Usd
    flatten_usd(str(usd))
    if usd != out / "palm_spatial.usda":
        # Export composed layer, preserving meshes without rewriting geometry/inertia.
        Usd.Stage.Open(str(usd)).Flatten().Export(str(out / "palm_spatial.usda"))
        usd = out / "palm_spatial.usda"
    result["stage"] = "fixed_root_adapter"
    from pxr import UsdPhysics
    isolated = Usd.Stage.Open(str(usd))
    isolated.SetEditTarget(isolated.GetRootLayer())

    def root_paths(stage):
        return [str(p.GetPath()) for p in stage.Traverse() if p.HasAPI(UsdPhysics.ArticulationRootAPI)]

    before = root_paths(isolated)
    require(len(before) == 1 and before[0].endswith("/base_link"), "unexpected converted root")
    base = isolated.GetPrimAtPath(before[0])
    parent = base.GetParent()
    result["fixed_root_adapter"] = adapter = {
        "usd_sha256_before": binding.sha256_file(usd), "roots_before": before,
        "base_schemas_before": base.GetAppliedSchemas(),
        "scope": "isolated USD root metadata/world fixed joint only; no rigid scope, mesh or inertia edits",
        "schemas_source_sha256": binding.sha256_file(Path(sim_utils.modify_articulation_root_properties.__wrapped__.__code__.co_filename)),
    }
    # The framework finder uses current stage even when modifier receives an explicit stage.
    with sim_utils.use_stage(isolated):
        sim_utils.modify_articulation_root_properties(before[0],
            sim_utils.ArticulationRootPropertiesCfg(fix_root_link=True, enabled_self_collisions=True),
            stage=isolated)
    adapter["schema_inclusions"] = {}
    for schema in ("NewtonArticulationRootAPI", "PhysxArticulationAPI"):
        definition = Usd.SchemaRegistry().FindAppliedAPIPrimDefinition(schema)
        adapter["schema_inclusions"][schema] = list(definition.GetAppliedAPISchemas()) if definition else None
    adapter["roots_after_framework"] = root_paths(isolated)
    adapter["base_schemas_after_framework"] = base.GetAppliedSchemas()
    adapter["base_api_specs_after_framework"] = [
        {"layer": str(spec.layer.identifier), "apiSchemas": str(spec.GetInfo("apiSchemas"))}
        for spec in base.GetPrimStack()]
    # Snapshot after the real framework RemoveAPI, before our residual-schema fix.
    from pxr import Sdf
    snapshot_layer = Sdf.Layer.CreateAnonymous("without_residual_fix.usda")
    require(snapshot_layer.ImportFromString(isolated.GetRootLayer().ExportToString()), "schema snapshot failed")
    snapshot = Usd.Stage.Open(snapshot_layer)
    adapter["without_residual_fix"] = {"roots": root_paths(snapshot),
        "scope": "in-memory USD schema snapshot after real framework RemoveAPI; no extra simulation"}
    try:
        require(root_paths(snapshot) == [str(parent.GetPath())], "fixed USD must have exactly one parent root")
    except ValueError as error:
        adapter["without_residual_fix"].update(status="REJECTED", error=str(error))
    else:
        require(exported, "without-fix snapshot did not reproduce residual root defect")
        adapter["without_residual_fix"]["status"] = "ALREADY_CORRECT"
    adapter["removed_residual_schemas"] = []
    if base.HasAPI(UsdPhysics.ArticulationRootAPI):
        # Multi-physics importer metadata may re-include PhysicsArticulationRootAPI.
        adapter["remove_api_return"] = base.RemoveAPI(UsdPhysics.ArticulationRootAPI)
        adapter["roots_after_explicit_remove"] = root_paths(isolated)
        if base.HasAPI(UsdPhysics.ArticulationRootAPI):
            # Only this isolated root's authored schema list; keep body/mass/link schemas intact.
            spec = isolated.GetRootLayer().GetPrimAtPath(base.GetPath())
            authored = spec.GetInfo("apiSchemas").GetAppliedItems()
            remove = {"PhysicsArticulationRootAPI", "NewtonArticulationRootAPI", "PhysxArticulationAPI"}
            adapter["removed_residual_schemas"] = [s for s in authored if s in remove]
            from pxr import Sdf
            spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit([s for s in authored if s not in remove]))
    require(root_paths(isolated) == [str(parent.GetPath())], "fixed USD must have exactly one parent root")
    require(not parent.HasAPI(UsdPhysics.RigidBodyAPI), "scope must not become a rigid body")
    fixed = sim_utils.find_global_fixed_joint_prim(str(parent.GetPath()), check_enabled_only=True, stage=isolated)
    require(fixed is not None and fixed.GetPrim().IsA(UsdPhysics.FixedJoint), "enabled world fixed joint missing")
    targets = list(fixed.GetBody0Rel().GetTargets()) + list(fixed.GetBody1Rel().GetTargets())
    require(targets == [base.GetPath()], "world fixed joint targets differ from base_link")
    adapter.update(roots_final=root_paths(isolated), base_schemas_final=base.GetAppliedSchemas(),
                   fixed_joint=str(fixed.GetPath()), fixed_joint_targets=list(map(str, targets)),
                   fixed_joint_enabled=fixed.GetJointEnabledAttr().Get(), spawn_fix_root_link=None)
    isolated.GetRootLayer().Save()
    adapter["usd_sha256_after"] = binding.sha256_file(usd)
    write_json(out / "fixed_root_adapter.json", adapter)
    if exported:
        from palm_spatial_inertia import repair_fresh_stage
        result["inertia_repair"] = repair_fresh_stage(isolated, out / "palm_spatial.urdf")
        isolated.GetRootLayer().Save()
        require(len([p for p in isolated.Traverse() if p.IsA(UsdPhysics.RevoluteJoint)]) == 30,
                "fresh USD joint count mismatch")
        manifest = out / "registered_manifest.json"
        target = joint_names.binding_for_target(str(usd), str(manifest),
            joint_names.PALM_SPATIAL_NAMING, joint_names=names)
        target.update(task=REGISTERED_TASK, urdf=str(out / "palm_spatial.urdf"))
        document = {"format": "palm-spatial-registered-diagnostic-v2", "target_binding": target,
                    "joint_order": names, "config": registered_config(names, joints),
                    "sha256": {"target": binding.sha256_file(usd), "urdf": args.approved_urdf_sha256},
                    "input": result["input"], "inertia_repair": result["inertia_repair"],
                    "scope": "fresh export conversion; runtime order/reset/action/contact/collectors NOT yet measured"}
        write_json(manifest, document)
        result["offline_contract"] = check_registered_manifest(manifest, measured_order=False)
        result.update(completed=True, stage="prepared", manifest=str(manifest),
                      manifest_sha256=binding.sha256_file(manifest),
                      status="fresh_export_prepared_runtime_unverified")
        check_export(args.export_report, args.approved_export_sha256, args.approved_urdf_sha256)
        result["artifacts"] = {str(p.relative_to(out)): binding.sha256_file(p)
                               for p in sorted(out.rglob("*")) if p.is_file()}
        write_json(out / "prepare_report.json", result)
        print("EXPORT_PREPARED", str(manifest), result["manifest_sha256"], flush=True)
        app.close()
        return
    target = joint_names.binding_for_target(str(usd), str(out / "manifest.json"),
                                          joint_names.PALM_SPATIAL_NAMING, joint_names=names)
    target.update(task=DIAGNOSTIC_TASK, urdf=str(out / "palm_spatial.urdf"))
    legs = [n for n in names if n.split("_", 1)[0] in joint_names.LEGS]
    spine = [n for n in names if n not in legs]
    config = {
        "scene.robot.init_state.joint_pos": {n: 0. for n in names},
        "scene.robot.init_state.joint_vel": {n: 0. for n in names},
        "scene.robot.spawn.rigid_props.disable_gravity": True,
        "scene.robot.spawn.articulation_props.fix_root_link": None,
        "scene.robot.spawn.articulation_props.enabled_self_collisions": True,
        "actions.joint_pos_legs.joint_names": legs,
        "actions.joint_pos_spine.joint_names": spine,
    }

    @configclass
    class SceneCfg(InteractiveSceneCfg):
        robot = ArticulationCfg(
            prim_path="{ENV_REGEX_NS}/Robot",
            spawn=sim_utils.UsdFileCfg(usd_path=str(usd), activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(disable_gravity=True),
                articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                    fix_root_link=None, enabled_self_collisions=True)),
            init_state=ArticulationCfg.InitialStateCfg(pos=(0., 0., 2.),
                joint_pos={n: 0. for n in names}, joint_vel={n: 0. for n in names}),
            actuators={"all": ImplicitActuatorCfg(joint_names_expr=names,
                stiffness=0., damping=0., armature=0.)})
        contact_forces = ContactSensorCfg(prim_path="{ENV_REGEX_NS}/Robot/.*", history_length=1)

    @configclass
    class ActionsCfg:
        joint_pos_legs = mdp.JointPositionActionCfg(asset_name="robot", joint_names=legs,
                                                  scale=1., use_default_offset=True, preserve_order=True)
        joint_pos_spine = mdp.JointPositionActionCfg(asset_name="robot", joint_names=spine,
                                                   scale=1., use_default_offset=True, preserve_order=True)

    @configclass
    class PolicyCfg(ObservationGroupCfg):
        base_lin_vel = ObservationTermCfg(func=mdp.base_lin_vel)
        base_ang_vel = ObservationTermCfg(func=mdp.base_ang_vel)
        projected_gravity = ObservationTermCfg(func=mdp.projected_gravity)
        joint_pos = ObservationTermCfg(func=mdp.joint_pos_rel, params={"asset_cfg": SceneEntityCfg("robot")})
        joint_vel = ObservationTermCfg(func=mdp.joint_vel_rel, params={"asset_cfg": SceneEntityCfg("robot")})
        actions = ObservationTermCfg(func=mdp.last_action)

    @configclass
    class ObservationsCfg:
        policy = PolicyCfg(enable_corruption=False, concatenate_terms=True)

    result["stage"] = "load"
    cfg = ManagerBasedEnvCfg(scene=SceneCfg(num_envs=1, env_spacing=5.), actions=ActionsCfg(),
                            observations=ObservationsCfg(), events={}, decimation=1,
                            sim=sim_utils.SimulationCfg(dt=.005, device=args.device))
    env = ManagerBasedEnv(cfg)
    env.reset()
    robot, sensor, manager = env.scene["robot"], env.scene["contact_forces"], env.action_manager
    runtime = list(robot.joint_names)
    target["runtime_joint_order"] = runtime
    obs_protocol.validate_diagnostic_runtime(target, cfg, robot, sensor, manager)
    result["stage"] = "mapping"
    require(robot.is_fixed_base, "base is not fixed")
    live_roots = [str(p.GetPath()) for p in Usd.PrimRange(env.sim.stage.GetPrimAtPath("/World/envs/env_0/Robot"))
                  if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
    require(len(live_roots) == 1, "spawned articulation must have exactly one root")
    live_bodies = [p for p in Usd.PrimRange(env.sim.stage.GetPrimAtPath("/World/envs/env_0/Robot"))
                   if p.HasAPI(UsdPhysics.RigidBodyAPI)]
    gravity = {str(p.GetPath()): p.GetAttribute("physxRigidBody:disableGravity").Get() for p in live_bodies}
    require(len(live_bodies) == len(robot.body_names) and all(v is True for v in gravity.values()),
            "disable_gravity live USD readback mismatch")
    result["readbacks"] = {"is_fixed_base": bool(robot.is_fixed_base), "root_paths": live_roots,
                           "disable_gravity_usd": gravity, "zero_fields": {}}
    for field in ("joint_stiffness", "joint_damping", "joint_armature", "default_joint_pos", "default_joint_vel"):
        values = getattr(robot.data, field).torch
        require(bool((values == 0).all()), field + " is nonzero")
        result["readbacks"]["zero_fields"][field] = values.cpu().tolist()
    require(len(robot.actuators) == 1 and robot.actuators["all"].num_joints == len(names), "drive coverage mismatch")
    live_limits = robot.data.joint_pos_limits.torch[0].cpu().tolist()
    for name, bounds in zip(runtime, live_limits):
        close_values(bounds, limits[name], 2e-6, "limits " + name)
    action_names, action_ids, terms = [], [], []
    for term_name in manager.active_terms:
        term = manager.get_term(term_name)
        ids = list(range(len(runtime)))[term._joint_ids] if isinstance(term._joint_ids, slice) else list(term._joint_ids)
        ids = [int(i) for i in ids]
        terms.append({"term": term_name, "names": list(term._joint_names), "ids": ids,
                      "scale": torch.as_tensor(term._scale).cpu().tolist(),
                      "offset": torch.as_tensor(term._offset).cpu().tolist()})
        action_names.extend(term._joint_names)
        action_ids.extend(ids)
    exact_channels(names, action_names, action_ids, runtime)
    sensor_map = [{"body": n, "sensor_id": i, "robot_id": robot.body_names.index(n)}
                  for i, n in enumerate(sensor.body_names)]
    result["mapping"] = {"runtime_joint_order": runtime, "action_terms": terms,
                         "sensor": sensor_map, "robot_bodies": list(robot.body_names)}
    obs = env.observation_manager
    slices, offset = {}, 0
    for name, shape in zip(obs.active_terms["policy"], obs.group_obs_term_dim["policy"]):
        width = math.prod(shape)
        slices[name] = [offset, offset + width]
        offset += width
    result["mapping"]["observations"] = {"terms": slices, "width": offset,
        "joint_pos_order": runtime, "joint_vel_order": runtime, "action_order": action_names}
    manifest = {"format": "palm-spatial-wiring-measurement-v1", "target_binding": target,
                "joint_order": names, "runtime_joint_order": runtime,
                "config": config, "sha256": {"target": binding.sha256_file(usd), "urdf": URDF_HASH},
                "scope": "dedicated unregistered ManagerBasedEnv config, NOT a registered task or v3 recipe; "
                         "config is partial measurement metadata, NOT a replay config; "
                         "load_diagnostic_target rejects diagnostic identity (no family) and v3 (task mismatch)"}
    write_json(out / "manifest.json", manifest)
    # Load only the deployed FK functions, avoiding its module-level adopted-asset lookup.
    fk_path = REPO / "rl_exp/tools/verify/check_leg_reachability.py"
    syntax = ast.parse(fk_path.read_text(encoding="utf-8"))
    selected = [n for n in syntax.body if isinstance(n, ast.FunctionDef) and n.name in ("_matrix", "_rpy_matrix")]
    scope = {"math": math}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(fk_path), "exec"), scope)
    result["code"]["fk_sha256"] = binding.sha256_file(fk_path)

    def pose_matrix(pose):
        x, y, z, w = pose[3:]
        matrix = np.array(Gf.Matrix4d().SetRotate(Gf.Quatd(float(w), Gf.Vec3d(float(x), float(y), float(z))))).T
        matrix[:3, 3] = pose[:3]
        return matrix

    result["stage"] = "injection"
    samples = []
    zero = torch.zeros((1, len(runtime)), device=env.device)
    for joint_id in range(len(runtime)):
        for angle in (-.05, .05):
            q = zero.clone()
            q[0, joint_id] = angle
            robot.write_joint_state_to_sim(q, zero)
            action = zero.clone()
            action[0, action_names.index(runtime[joint_id])] = angle
            manager.process_action(action)
            manager.apply_action()
            env.scene.write_data_to_sim()
            close_values(robot.data.joint_pos_target.torch[0].cpu().tolist(), q[0].cpu().tolist(), 1e-6, "action target")
            # No tracking test: step only materializes actor poses and contact sensor data.
            env.sim.step(render=False)
            env.scene.update(env.physics_dt)
            actual = robot.data.joint_pos.torch[0].cpu().tolist()
            velocity = robot.data.joint_vel.torch[0].cpu().tolist()
            observation = obs.compute_group("policy")[0].cpu().tolist()
            for key, expected in (("joint_pos", actual), ("joint_vel", velocity), ("actions", action[0].cpu().tolist())):
                start, stop = slices[key]
                close_values(observation[start:stop], expected, 1e-6, "observation " + key)
            actor = robot.data.body_link_pose_w.torch[0].cpu().numpy().copy()
            frames = {"base_link": pose_matrix(actor[robot.body_names.index("base_link")])}
            depth = {"base_link": 0}
            q_actual = dict(zip(runtime, actual))
            for j in joints:
                parent, child = j.find("parent").get("link"), j.find("child").get("link")
                origin = j.find("origin")
                frames[child] = frames[parent] @ np.array(scope["_matrix"](
                    list(map(float, origin.get("xyz").split())), list(map(float, j.find("axis").get("xyz").split())),
                    q_actual[j.get("name")], list(map(float, origin.get("rpy", "0 0 0").split()))))
                depth[child] = depth[parent] + 1
            residuals = {}
            for name, pose in zip(robot.body_names, actor):
                actual_frame = pose_matrix(pose)
                pos = float(np.linalg.norm(actual_frame[:3, 3] - frames[name][:3, 3]))
                rot = float(np.linalg.norm(actual_frame[:3, :3] - frames[name][:3, :3]))
                budget = max(1, depth[name]) * 64 * np.finfo(np.float32).eps * 4
                residuals[name] = {"position_m": pos, "rotation_fro": rot, "budget": float(budget)}
                require(pos <= budget and rot <= budget, "actor/FK mismatch: " + name)
            forces = sensor.data.net_forces_w.torch[0].cpu().tolist()
            samples.append({"joint": runtime[joint_id], "injected_rad": angle,
                "injected_state_rad": q[0].cpu().tolist(), "actual_rad": actual, "velocity_rad_s": velocity,
                "target_rad": robot.data.joint_pos_target.torch[0].cpu().tolist(),
                "observation": observation, "actor_pose_xyzw": actor.tolist(),
                "sensor_force_n": forces, "fk_residuals": residuals})
            result["samples_completed"] = len(samples)
    result["samples"] = samples
    result["measurement_summary"] = {
        "scope": "measured after one physics step per injection; NOT pass/fail criteria, PD tracking or support",
        "state_drift_max_abs_rad": max(abs(a - b) for s in samples
            for a, b in zip(s["actual_rad"], s["injected_state_rad"])),
        "state_velocity_max_abs_rad_s": max(abs(v) for s in samples for v in s["velocity_rad_s"]),
        "sensor_force_max_norm_n": max(math.sqrt(sum(v * v for v in force))
            for s in samples for force in s["sensor_force_n"]),
        "sensor_force_max_abs_component_n": max(abs(v) for s in samples
            for force in s["sensor_force_n"] for v in force),
    }
    result["stage"] = "reader"
    from rl_exp.tools.diagnose.plot_joints import report_naming, report_tokens, draw_band
    naming = joint_names.PALM_SPATIAL_NAMING
    feet = [joint_names.end_link(leg, naming) for leg in joint_names.LEGS]
    entry = {"speed": 0., "feet": [], "joint_series": {}, "spine_series": {}, "series": {"force": []}}
    for leg, foot in zip(joint_names.LEGS, feet):
        summary = {"body": foot}
        for token in report_tokens(naming, leg):
            summary[token + "_limits_rad"] = limits[joint_names.joint_name(leg, token)]
        entry["feet"].append(summary)
        entry["series"]["force"].append([s["sensor_force_n"][sensor.body_names.index(foot)][2] for s in samples])
        for root in joint_names.roots_of(naming, leg):
            i = runtime.index(joint_names.joint_name(leg, root))
            for kind, key in (("actual", "actual_rad"), ("target", "target_rad"), ("vel", "velocity_rad_s")):
                entry["joint_series"][f"{foot}_{root}_{kind}"] = [s[key][i] for s in samples]
    for name in spine:
        for kind, key in (("actual", "actual_rad"), ("target", "target_rad"), ("vel", "velocity_rad_s")):
            entry["spine_series"][f"{name}_{kind}"] = [s[key][runtime.index(name)] for s in samples]
    reader_report = {"target_binding": target, "target_binding_required": True, "foot_bodies": feet,
        "envs": [entry], "contact_n": 1., "scope": "state injection; dedicated writer, NOT gait rollout/performance"}
    report_naming(reader_report)
    result["reader_negatives"] = {}
    for defect in ("missing_twist", "mixed_naming", "missing_source"):
        broken = copy.deepcopy(reader_report)
        if defect == "missing_twist":
            del broken["envs"][0]["joint_series"]["lf_wrist_shoulder_twist_actual"]
        elif defect == "mixed_naming":
            columns = broken["envs"][0]["joint_series"]
            columns["lf_wrist_hip_actual"] = columns.pop("lf_wrist_shoulder_swing_actual")
        else:
            del broken["target_binding"]["source"]
        try:
            report_naming(broken)
        except ValueError as error:
            result["reader_negatives"][defect] = {"status": "REJECTED", "error": str(error)}
        else:
            raise ValueError("reader accepted " + defect)
    write_json(out / "reader_report.json", reader_report)
    result["reader"] = draw_band(entry, 1., .02, out, "injection_not_gait", naming)
    check_build(BUILD)
    result["artifacts"] = {str(p.relative_to(out)): binding.sha256_file(p)
                           for p in sorted(out.rglob("*")) if p.is_file()}
    result["completed"] = True
    result["stage"] = "completed"
    write_json(out / "runtime_report.json", result)
    print("RUNTIME_COMPLETED", json.dumps({"samples": len(samples), "joints": len(runtime),
        "report_sha256": binding.sha256_file(out / "runtime_report.json")}), flush=True)
    env.close()
    app.close()


def connection_geometry(urdf=None):
    """Scan actual neutral meshes before allowing exactly the six connected pairs [m]."""
    import itertools
    import numpy as np
    from rl_exp.tools.diagnose import palm_motion_boundaries as motion

    doc = check_build(BUILD)
    csc = motion.gait.csc
    model = csc.load_urdf(urdf if urdf is not None else ArtifactPaths().resolve(
        BUILD.parent / "palm_spatial.urdf"))
    collision = motion.Collision(model, 1e-9)
    remap = {d["abduct"]: d["twist"] for d in doc["definitions"].values()}
    expected = {frozenset(remap.get(n, n) for n in pair) for pair in motion.gait.APPROVED}
    parents = {s["child"]: s["parent"] for s in model["joints"].values()}
    frames = {n: csc.fk(model["joints"], n, {}) for n in model["links"]}
    world = {n: v @ frames[n][:3, :3].T + frames[n][:3, 3]
             for n, (v, _) in collision.local.items()}
    rows, scanned = [], set()
    for a, b in itertools.combinations(sorted(world), 2):
        va, vb = world[a], world[b]
        if np.any(va.min(0) > vb.max(0)) or np.any(vb.min(0) > va.max(0)):
            continue
        fa, fb = collision.local[a][1], collision.local[b][1]
        crossing = motion.surface_crosses(va, fa, vb, fb) or motion.surface_crosses(vb, fb, va, fa)
        contained = any(motion.inside(va[i], vb, fb) for i in collision.representatives[a]) or any(
            motion.inside(vb[i], va, fa) for i in collision.representatives[b])
        if not crossing and not contained:
            continue
        if csc.jointed_pair(model["joints"], a, b):
            continue
        endpoint, ancestor = (a, b) if b in csc.depths(model["joints"], a) else (b, a)
        chain = [endpoint]
        while chain[-1] != ancestor and chain[-1] in parents:
            chain.append(parents[chain[-1]])
        intermediates = chain[1:-1]
        connected = chain[-1] == ancestor and bool(intermediates) and all(
            model["links"][n]["collision"] is None for n in intermediates)
        pivots = [frames[n][:3, 3] for n in chain[:-1]]
        span = max(float(np.linalg.norm(x - y)) for x in pivots for y in pivots) if pivots else 0.
        pair = frozenset((a, b))
        if connected:
            scanned.add(pair)
        rows.append({"pair": [a, b], "surface_crossing": bool(crossing), "containment": bool(contained),
                     "child_to_ancestor": chain, "collider_free_intermediates": intermediates,
                     "connected": connected, "joint_pivots_m": [p.tolist() for p in pivots],
                     "pivot_span_m": span, "approved": pair in expected})
    require(len(expected) == 6 and scanned == expected, "neutral connected scan differs from six approved pairs")
    require(all(row["approved"] for row in rows), "unapproved nonadjacent neutral interference")
    twist_links = {d["twist"] for d in doc["definitions"].values()}
    require(all(row["pivot_span_m"] < (1e-6 if set(row["pair"]) & twist_links else .006)
                for row in rows), "connection pivots differ from bound mechanism")
    pose = {"chest_yaw_joint": .6}
    a, b = "lf_wrist", "rl_ankle"
    negative_world = {}
    for n in (a, b):
        frame = csc.fk(model["joints"], n, pose)
        negative_world[n] = collision.local[n][0] @ frame[:3, :3].T + frame[:3, 3]
    negative_crossing = motion.surface_crosses(negative_world[a], collision.local[a][1],
                                              negative_world[b], collision.local[b][1]) or motion.surface_crosses(
        negative_world[b], collision.local[b][1], negative_world[a], collision.local[a][1])
    require(negative_crossing and frozenset((a, b)) not in expected, "cross-leg negative geometry absent")
    return {"pairs": rows, "negative": {"pose_rad": pose, "pair": [a, b], "surface_crossing": True},
            "scope": "neutral real-mesh intersections, collider-free mechanism and pivots; not full ROM approval",
            "sources": {str(Path(m.__file__)): binding.sha256_file(Path(m.__file__))
                        for m in (motion, motion.gait, csc)}}


def check_filter_pairs(actual, approved):
    require(len(actual) == len(approved)
            and {frozenset(pair) for pair in actual} == {frozenset(pair) for pair in approved},
            "unexpected collision filter pair")


def reset_probe(args, result):
    """Trace registered reset and one physical step on an explicitly bound isolated replay."""
    import inspect
    from unittest.mock import patch

    manifest = args.reset_probe.resolve()
    exported = args.export_manifest_sha256 is not None
    if exported:
        require(args.export_report is not None, "fresh reset requires explicit export report")
        check_export(args.export_report, args.approved_export_sha256, args.approved_urdf_sha256)
        require(binding.sha256_file(manifest) == args.export_manifest_sha256, "fresh manifest approval mismatch")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    repaired = document.get("format") == "palm-spatial-registered-diagnostic-v2"
    if exported:
        prepared = json.loads((manifest.parent / "prepare_report.json").read_text(encoding="utf-8"))
        require(prepared["completed"] and prepared["status"] == "fresh_export_prepared_runtime_unverified"
                and prepared["manifest_sha256"] == args.export_manifest_sha256, "fresh preparation binding mismatch")
        require(document["input"]["export_report"] == str(args.export_report.resolve())
                and document["input"]["export_report_sha256"] == args.approved_export_sha256
                and document["sha256"]["urdf"] == args.approved_urdf_sha256, "fresh export lineage mismatch")
        usd = Path(document["target_binding"]["target"]).resolve()
        urdf = Path(document["target_binding"]["urdf"]).resolve()
        require(usd == manifest.parent / "palm_spatial.usda" and urdf == manifest.parent / "palm_spatial.urdf"
                and manifest.is_relative_to((REPO / "rl_exp/out").resolve()), "fresh replay path mismatch")
        require(binding.sha256_file(usd) == document["sha256"]["target"]
                and binding.sha256_file(urdf) == args.approved_urdf_sha256, "fresh replay file mismatch")
        for name, digest in prepared["artifacts"].items():
            source = (manifest.parent / name).resolve()
            require(source.is_relative_to(manifest.parent) and binding.sha256_file(source) == digest,
                    "fresh prepared artifact mismatch: " + name)
        check_registered_manifest(manifest, measured_order=False)
    elif not repaired:
        require(binding.sha256_file(manifest) ==
                "30209cfc6237f8d0a6b1a3cbce6d5911c5c5a5e66113cb7473b204f561dab68f",
                "reset probe manifest changed")
    else:
        prepared = json.loads((manifest.parent / "prepare_report.json").read_text(encoding="utf-8"))
        require(prepared["manifest_sha256"] == binding.sha256_file(manifest), "prepared reset manifest changed")
        require(Path(document["target_binding"]["target"]).resolve() == REGISTERED_INPUT / "palm_spatial.usda"
                and document["sha256"]["target"] == FIXED_USD_HASH, "reset repair must start with fixed source USD")
    require(not args.repair_connections or repaired, "connection repair requires deterministic reset manifest")
    check_build(BUILD)
    out = args.out.resolve()
    if exported:
        out = fresh_export_out(out, manifest.parent)
    else:
        require(out.parent == REGISTERED_OUT.resolve() and not out.exists(), "fresh registered attempt required")
    out.mkdir(exist_ok=False)
    result.update(output=str(out), stage="app_launch", scope=
                  "registered reset attribution only; explicit-default counterfactual is NOT baseline acceptance")
    shutil.copyfile(Path(__file__), out / "reset_probe_source.py")
    result["input"] = {"manifest": str(manifest), "manifest_sha256": binding.sha256_file(manifest),
                       "usd_sha256": document["sha256"]["target"] if exported else FIXED_USD_HASH,
                       "urdf_sha256": args.approved_urdf_sha256 if exported else URDF_HASH}
    result["code_sha256"] = binding.sha256_file(Path(__file__))
    from isaaclab.app import AppLauncher
    app = AppLauncher(args).app
    import gymnasium as gym
    import torch
    import warp as wp
    import rl_exp.tasks
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
    from isaaclab.envs import ManagerBasedRLEnv
    from isaaclab.assets import AssetBaseCfg
    from pxr import Usd, UsdPhysics, UsdGeom
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg, joint_reset_errors

    geometry = None
    if args.repair_connections:
        source_dir = manifest.parent if exported else REGISTERED_INPUT
        geometry = connection_geometry(source_dir / "palm_spatial.urdf" if exported else None)
        write_json(out / "connection_geometry.json", geometry)
        for name in ("palm_spatial.urdf", "palm_spatial.usda"):
            shutil.copyfile(source_dir / name, out / name)
        shutil.copytree(source_dir / "meshes", out / "meshes")
        isolated = Usd.Stage.Open(str(out / "palm_spatial.usda"))
        bodies = {p.GetName(): p for p in isolated.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)}
        approved = [row["pair"] for row in geometry["pairs"]]
        original_schema_ops = {a: isolated.GetRootLayer().GetPrimAtPath(bodies[a].GetPath()).GetInfo("apiSchemas")
                               for a, _ in approved}
        require(not any(p.HasAPI(UsdPhysics.FilteredPairsAPI) for p in isolated.Traverse()),
                "source already has authored filters")
        for a, b in approved:
            UsdPhysics.FilteredPairsAPI.Apply(bodies[a]).CreateFilteredPairsRel().AddTarget(bodies[b].GetPath())
        isolated.GetRootLayer().Save()
        delta_layer = isolated.GetRootLayer().ExportToString()
        for a in original_schema_ops:
            prim = bodies[a]
            prim.RemoveProperty("physics:filteredPairs")
            isolated.GetRootLayer().GetPrimAtPath(prim.GetPath()).SetInfo("apiSchemas", original_schema_ops[a])
        source_stage = Usd.Stage.Open(str(source_dir / "palm_spatial.usda"))
        require(isolated.GetRootLayer().ExportToString() == source_stage.GetRootLayer().ExportToString(),
                "repaired USD changed fields other than six named filters")
        require(isolated.GetRootLayer().ImportFromString(delta_layer), "cannot restore isolated filters")
        result["only_named_filter_delta_verified"] = True
        repaired_document = copy.deepcopy(document)
        repaired_manifest = out / "registered_manifest.json"
        repaired_document["target_binding"].update(target=str(out / "palm_spatial.usda"),
            urdf=str(out / "palm_spatial.urdf"), source=str(repaired_manifest))
        repaired_document["sha256"]["target"] = binding.sha256_file(out / "palm_spatial.usda")
        repaired_document["connection_filter"] = {"pairs": approved, "geometry": str(out / "connection_geometry.json"),
            "geometry_sha256": binding.sha256_file(out / "connection_geometry.json"),
            "source_usd_sha256": result["input"]["usd_sha256"],
            "scope": "six named connections only; neutral reset/first-step diagnostic, no ROM or PD verdict"}
        write_json(repaired_manifest, repaired_document)
        manifest = repaired_manifest
    cfg = copy.deepcopy(resolve_task_cfg(REGISTERED_TASK))
    target = obs_protocol.load_diagnostic_target(manifest, cfg, REGISTERED_TASK)
    cfg.sim.device = args.device
    result["replay_manifest"] = str(manifest)
    result["replay_manifest_sha256"] = binding.sha256_file(manifest)
    result["offline_contract"] = check_registered_manifest(manifest, measured_order=not exported)
    result["quaternion_convention"] = {"order": "xyzw", "source": inspect.getfile(AssetBaseCfg),
                                        "default": list(AssetBaseCfg.InitialStateCfg().rot)}
    result["stages"] = []
    result["hook_calls"] = []
    live = None
    phase = "gym_make"
    pair_views = {}
    owner_colliders = {}
    ancestry = {}

    def tensor(value):
        if hasattr(value, "torch"):
            return value.torch
        return value if isinstance(value, torch.Tensor) else wp.to_torch(value)

    def sample(label, robot=None):
        robot = robot if robot is not None else live.scene["robot"]
        q = tensor(robot.root_view.get_dof_positions()).clone()
        qd = tensor(robot.root_view.get_dof_velocities()).clone()
        cq, cv = robot.data.joint_pos.torch.clone(), robot.data.joint_vel.torch.clone()
        row = {"label": label, "phase": phase, "cache_time_s": float(robot.data._sim_timestamp),
               "env_physics_steps": getattr(live, "_sim_step_counter", None),
               "backend_q_rad": q.cpu().tolist(), "backend_qd_rad_s": qd.cpu().tolist(),
               "cache_q_rad": cq.cpu().tolist(), "cache_qd_rad_s": cv.cpu().tolist(),
               "default_q_rad": robot.data.default_joint_pos.torch.cpu().tolist(),
               "default_qd_rad_s": robot.data.default_joint_vel.torch.cpu().tolist(),
               "q_error_max_rad": float((q - robot.data.default_joint_pos.torch).abs().max()),
               "qd_error_max_rad_s": float((qd - robot.data.default_joint_vel.torch).abs().max()),
               "cache_backend_q_error": float((cq - q).abs().max()),
               "cache_backend_qd_error": float((cv - qd).abs().max()),
               "root_pose_xyzw": robot.data.root_link_pose_w.torch.cpu().tolist(),
               "backend_root_pose_xyzw": tensor(robot.root_view.get_root_transforms()).cpu().tolist(),
               "body_pose_xyzw": robot.data.body_link_pose_w.torch.cpu().tolist(),
               "strict_reset_errors": joint_reset_errors(robot)}
        if args.contact_pairs:
            row["contact_pairs"] = {"status": "not_current", "reason":
                "no force read outside the two post-physics-step stages"}
            if label in ("post_1_physics_step", "explicit_default_post_1_physics_step", "cross_leg_post_1_physics_step"):
                result["stage"] = "contact_pair_sample_" + label
                matrices, nets, nonzero, checks = {}, {}, [], []
                main_forces = live.scene["contact_forces"].data.net_forces_w.torch[0].clone()
                for source, view in pair_views.items():
                    matrix = tensor(view.get_contact_force_matrix(dt=live.physics_dt)).clone()
                    net = tensor(view.get_net_contact_forces(dt=live.physics_dt)).clone()
                    columns = pair_binding(view.sensor_paths, view.filter_paths, source,
                                           owner_colliders, matrix.shape)
                    require(tuple(net.shape) == (1, 3), "contact net force shape mismatch")
                    require(bool(torch.isfinite(matrix).all() and torch.isfinite(net).all()),
                            "nonfinite contact forces")
                    matrices[source] = {path: force for path, force in zip(columns, matrix[0])}
                    nets[source] = net[0]
                    name = source.rsplit("/", 1)[-1]
                    sensor_net = main_forces[live.scene["contact_forces"].body_names.index(name)]
                    summed = matrix[0].sum(dim=0)
                    budget = 64 * torch.finfo(torch.float32).eps * max(
                        1., float(matrix.abs().sum()), float(net.abs().sum()), float(sensor_net.abs().sum()))
                    checks.append({"source": name, "source_path": source, "columns_actual": columns,
                        "matrix_shape": list(matrix.shape), "source_net_force_n": net[0].cpu().tolist(),
                        "filtered_sum_n": summed.cpu().tolist(),
                        "sum_minus_net_n": (summed - net[0]).cpu().tolist(),
                        "sum_residual_norm_n": float((summed - net[0]).norm()),
                        "main_sensor_same_step_n": sensor_net.cpu().tolist(),
                        "main_sensor_residual_norm_n": float((sensor_net - net[0]).norm()),
                        "float32_comparison_budget_n": budget})
                    for partner, force in matrices[source].items():
                        if bool((force != 0).any()):
                            other = partner.rsplit("/", 1)[-1]
                            a, b = ancestry[name], ancestry[other]
                            common = next(n for n in a if n in b)
                            nonzero.append({"source": name, "target": other,
                                "source_owner_path": source, "target_owner_path": partner,
                                "source_collision_path": owner_colliders[source],
                                "target_collision_path": owner_colliders[partner],
                                "force_world_n": force.cpu().tolist(), "norm_n": float(force.norm()),
                                "source_net_force_n": net[0].cpu().tolist(),
                                "parent_related": name in b or other in a,
                                "urdf_graph_distance": a.index(common) + b.index(common)})
                reciprocity = []
                paths = list(pair_views)
                for i, source in enumerate(paths):
                    for partner in paths[i + 1:]:
                        f, r = matrices[source][partner], matrices[partner][source]
                        if bool((f != 0).any() or (r != 0).any()):
                            reciprocity.append({"bodies": [source.rsplit("/", 1)[-1], partner.rsplit("/", 1)[-1]],
                                "fij_plus_fji_n": (f + r).cpu().tolist(), "residual_norm_n": float((f + r).norm())})
                row["contact_pairs"] = {"status": "observed" if nonzero else "unknown",
                    "dt_s": live.physics_dt, "coverage": [p.rsplit("/", 1)[-1] for p in paths],
                    "owner_count": len(paths), "directed_slots": len(paths) ** 2,
                    "nonzero": nonzero, "source_checks": checks, "unordered_reciprocity": reciprocity,
                    "scope": "normal-force aggregates at body-owner level; one collider per owner; "
                             "no contact points/friction; zero does not prove no self-contact; "
                             "sum excludes non-owner contacts; ancestry is not filter approval"}
                write_json(out / (label + "_contact_pairs.json"), row["contact_pairs"])
                result["contact_pairs"]["sample_labels"].append(label)
        result["stages"].append(row)
        write_json(out / f"stage_{len(result['stages']):02d}.json", row)
        print("RESET_STAGE", json.dumps({k: row[k] for k in
              ("label", "q_error_max_rad", "qd_error_max_rad_s", "cache_backend_q_error",
               "cache_backend_qd_error", "cache_time_s", "strict_reset_errors")}), flush=True)

    def traced_reset(env, *a, **kw):
        original_reset(env, *a, **kw)
        sample("after_reset_idx", env.scene["robot"])

    original_reset = ManagerBasedRLEnv._reset_idx
    env = None
    try:
        result["stage"] = "gym_make"
        with patch.object(ManagerBasedRLEnv, "_reset_idx", traced_reset):
            env = gym.make(REGISTERED_TASK, cfg=cfg)
            live = env.unwrapped
            robot = live.scene["robot"]
            sample("post_gym_make")
            result["joint_names"] = list(robot.joint_names)
            result["body_names"] = list(robot.body_names)
            result["dt_s"] = live.physics_dt
            result["decimation"] = cfg.decimation
            robot_type = type(robot)
            result["framework_sources"] = {}
            for obj in (robot_type, type(robot.data), type(live), type(live.sim.physics_manager),
                        RslRlVecEnvWrapper):
                path = Path(inspect.getfile(obj))
                result["framework_sources"][str(path)] = binding.sha256_file(path)
            result["live_readbacks"] = {"fixed_base": bool(robot.is_fixed_base),
                "events": list(live.event_manager.available_modes),
                "fields": {name: getattr(robot.data, name).torch.cpu().tolist() for name in
                    ("joint_stiffness", "joint_damping", "joint_armature", "joint_effort_target",
                     "joint_pos_target", "joint_vel_target", "joint_effort_limits", "joint_vel_limits")},
                "wrench_active": {name: bool(getattr(robot, name).active) for name in
                    ("_instantaneous_wrench_composer", "_permanent_wrench_composer")}}
            for name in ("joint_stiffness", "joint_damping", "joint_armature", "joint_effort_target"):
                require(bool((getattr(robot.data, name).torch == 0).all()), "nonzero live " + name)

            owner_path = REPO / "rl_exp/tools/verify/check_contact_ownership.py"
            nodes = [n for n in ast.parse(owner_path.read_text(encoding="utf-8")).body
                     if isinstance(n, ast.FunctionDef) and n.name in ("usd_collisions", "penalised_bodies")]
            scope = {"Usd": Usd, "UsdPhysics": UsdPhysics}
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(owner_path), "exec"), scope)
            root = live.sim.stage.GetPrimAtPath("/World/envs/env_0/Robot")
            actual_filters = [[p.GetName(), target.name] for p in Usd.PrimRange(root)
                              if p.HasAPI(UsdPhysics.FilteredPairsAPI)
                              for target in UsdPhysics.FilteredPairsAPI(p).GetFilteredPairsRel().GetTargets()]
            approved_filters = document.get("connection_filter", {}).get("pairs", [])
            if geometry is not None:
                approved_filters = [row["pair"] for row in geometry["pairs"]]
            check_filter_pairs(actual_filters, approved_filters)
            result["physics_filter_readback"] = actual_filters
            owners = scope["usd_collisions"](root)
            collisions, unclaimed, fixed = [], [], []
            for prim in Usd.PrimRange(root):
                if prim.IsA(UsdPhysics.FixedJoint):
                    joint = UsdPhysics.FixedJoint(prim)
                    fixed.append({"prim": str(prim.GetPath()), "body0": list(map(str, joint.GetBody0Rel().GetTargets())),
                        "body1": list(map(str, joint.GetBody1Rel().GetTargets())),
                        "local_pos0": list(joint.GetLocalPos0Attr().Get()),
                        "local_pos1": list(joint.GetLocalPos1Attr().Get()),
                        "local_rot0": str(joint.GetLocalRot0Attr().Get()),
                        "local_rot1": str(joint.GetLocalRot1Attr().Get()),
                        "enabled": joint.GetJointEnabledAttr().Get()})
                if not prim.HasAPI(UsdPhysics.CollisionAPI):
                    continue
                body = prim
                while body and not body.HasAPI(UsdPhysics.RigidBodyAPI):
                    body = body.GetParent()
                row = {"prim": str(prim.GetPath()), "nearest_body": str(body.GetPath()) if body else None,
                       "enabled": UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get(),
                       "mesh_local_extent": str(prim.GetAttribute("extent").Get()),
                       "local_to_world": str(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))}
                collisions.append(row)
                if not body:
                    unclaimed.append(row)
            terms = scope["penalised_bodies"](live)
            sensor = live.scene["contact_forces"]
            links = ET.parse(target["urdf"]).getroot().findall("link")
            urdf_meshes = {link.get("name"): [
                {"path": str((Path(target["urdf"]).parent / mesh.get("filename")).resolve()),
                 "sha256": binding.sha256_file((Path(target["urdf"]).parent / mesh.get("filename")).resolve()),
                 "scale": mesh.get("scale", "1 1 1"),
                 "origin_xyz": c.find("origin").get("xyz") if c.find("origin") is not None else "0 0 0",
                 "origin_rpy": c.find("origin").get("rpy", "0 0 0") if c.find("origin") is not None else "0 0 0"}
                for c in link.findall("collision") for mesh in c.findall("geometry/mesh")]
                for link in links}
            result["collision_ownership"] = {"source_sha256": binding.sha256_file(owner_path),
                "by_body": owners, "collisions": collisions, "unclaimed": unclaimed,
                "urdf_meshes": urdf_meshes, "reward_selected": terms,
                "dead_reward_bodies": sorted({n for ns in terms.values() for n in ns if not owners.get(n)}),
                "sensor_bodies": list(sensor.body_names),
                "feet": {n: {"colliders": owners.get(n, []), "sensor_id": sensor.body_names.index(n)}
                         for n in target["end_links"].values()},
                "bbox_scope": "mesh-local extents only; no cross-frame size equality claim",
                "contact_pair": "unknown: no filters changed; net force is not a contact pair"}
            result["fixed_joints"] = fixed
            result["live_readbacks"]["gravity_disabled"] = {
                str(p.GetPath()): p.GetAttribute("physxRigidBody:disableGravity").Get()
                for p in Usd.PrimRange(root) if p.HasAPI(UsdPhysics.RigidBodyAPI)}
            require(all(result["live_readbacks"]["gravity_disabled"].values()), "live gravity enabled")
            require(robot.is_fixed_base, "root is not fixed")
            write_json(out / "collision_ownership.json", result["collision_ownership"])
            if args.contact_pairs:
                from isaaclab_physx.physics import PhysxManager as SimulationManager
                result["stage"] = "contact_pair_initialization"
                result["contact_pairs"] = {"status": "unknown", "sample_labels": [],
                    "mapping": [], "physics_filters_changed": bool(approved_filters)}
                require(not unclaimed and len(collisions) == 18, "expected 18 claimed collision prims")
                for collision in collisions:
                    path = collision["nearest_body"]
                    require(path not in owner_colliders and collision["enabled"],
                            "expected one enabled collider per owner")
                    owner_colliders[path] = collision["prim"]
                require(len(robot.body_names) == 31, "expected 31 runtime bodies")
                parents = {j.find("child").get("link"): j.find("parent").get("link")
                           for j in ET.parse(target["urdf"]).getroot().findall("joint")}
                for name in robot.body_names:
                    chain = [name]
                    while chain[-1] in parents:
                        require(parents[chain[-1]] not in chain, "URDF ancestry cycle")
                        chain.append(parents[chain[-1]])
                    ancestry[name] = chain
                budget = sensor.cfg.max_contact_data_count_per_prim
                require(isinstance(budget, int) and budget > 0, "invalid existing per-body contact capacity")
                result["contact_pairs"]["capacity_per_owner"] = budget
                sim_view = SimulationManager.get_physics_sim_view()
                for source in owner_colliders:
                    require(source.rsplit("/", 1)[-1] in robot.body_names, "foreign collider owner")
                    view = sim_view.create_rigid_contact_view(source,
                        filter_patterns=list(owner_colliders), max_contact_data_count=budget)
                    pair_views[source] = view
                    api_path = Path(inspect.getfile(type(view)))
                    mapping = {"source_exact_pattern": source,
                        "filter_exact_patterns": list(owner_colliders),
                        "sensor_paths_actual": view.sensor_paths, "filter_paths_actual": view.filter_paths,
                        "sensor_count": view.sensor_count, "filter_count": view.filter_count,
                        "max_contact_data_count": view.max_contact_data_count,
                        "api_source": str(api_path), "api_sha256": binding.sha256_file(api_path),
                        "binding_status": "unverified"}
                    result["contact_pairs"]["mapping"].append(mapping)
                    write_json(out / f"contact_pair_raw_{len(pair_views):02d}.json", mapping)
                    mapping["columns_actual"] = pair_binding(view.sensor_paths, view.filter_paths, source,
                        owner_colliders, (view.sensor_count, view.filter_count, 3))
                    mapping["binding_status"] = "verified"
                require(live.physics_dt == .005, "unexpected physics dt")
                result["contact_pairs"]["status"] = "registered_paths_verified"
                result["collision_ownership"]["contact_pair"] = "see per-stage body-owner force observations"
                write_json(out / "contact_pair_mapping.json", result["contact_pairs"])

            def traced_method(name, original):
                def call(obj, *a, **kw):
                    result["hook_calls"].append({"phase": phase, "method": name})
                    answer = original(obj, *a, **kw)
                    if name.startswith("write_joint"):
                        sample("after_" + name, obj)
                    return answer
                return call

            with patch.object(robot_type, "write_joint_position_to_sim_index", traced_method(
                    "write_joint_position_to_sim_index", robot_type.write_joint_position_to_sim_index)), \
                 patch.object(robot_type, "write_joint_velocity_to_sim_index", traced_method(
                    "write_joint_velocity_to_sim_index", robot_type.write_joint_velocity_to_sim_index)):
                phase = "wrapper_reset"
                wrapper = RslRlVecEnvWrapper(env, clip_actions=None)
                sample("post_wrapper_reset")
                phase = "original_first_physics_step"
                live.scene.write_data_to_sim()
                sample("pre_physical_step")
                live.sim.step(render=False)
                live.scene.update(live.physics_dt)
                sample("post_1_physics_step")
                result["original_first_step_net_force_n"] = sensor.data.net_forces_w.torch.cpu().tolist()
                # Counterfactual writes exactly the bound defaults, not a new pose, gain or asset.
                phase = "explicit_bound_default_write_not_baseline"
                robot.write_joint_position_to_sim_index(position=robot.data.default_joint_pos.torch.clone())
                robot.write_joint_velocity_to_sim_index(velocity=robot.data.default_joint_vel.torch.clone())
                live.scene.write_data_to_sim()
                live.sim.forward()
                sample("explicit_default_after_forward")
                phase = "explicit_default_first_physics_step_not_baseline"
                live.sim.step(render=False)
                live.scene.update(live.physics_dt)
                sample("explicit_default_post_1_physics_step")
                result["default_first_step_net_force_n"] = sensor.data.net_forces_w.torch.cpu().tolist()
            first = next(row for row in result["stages"] if row["label"] == "post_1_physics_step")
            reset = next(row for row in result["stages"] if row["label"] == "post_wrapper_reset")
            if repaired:
                require(not reset["strict_reset_errors"], "deterministic wrapper reset failed")
                require(any(call["phase"] == "wrapper_reset" and call["method"].startswith("write_joint")
                            for call in result["hook_calls"]), "reset did not invoke joint writer")
            if geometry is not None:
                require(not first["strict_reset_errors"], "filtered neutral first physics step still moves")
                require(not result["stages"][-1]["strict_reset_errors"], "filtered explicit first step still moves")
                require(args.contact_pairs, "filter repair requires actual pair observation")
                phase = "cross_leg_negative"
                live.reset()
                q = robot.data.default_joint_pos.torch.clone()
                q[0, robot.joint_names.index("chest_yaw_joint")] = .6
                robot.write_joint_state_to_sim(q, robot.data.default_joint_vel.torch.clone())
                live.scene.write_data_to_sim()
                live.sim.forward()
                live.sim.step(render=False)
                live.scene.update(live.physics_dt)
                sample("cross_leg_post_1_physics_step")
                contact = result["stages"][-1]["contact_pairs"]
                kept = [row for row in contact["nonzero"] if {row["source"], row["target"]} == {"lf_wrist", "rl_ankle"}]
                require(kept and max(row["norm_n"] for row in kept) > 1., "required real cross-leg contact missing")
                result["preserved_contact_negative"] = kept
                phase = "reset_after_negative"
                live.reset()
                sample("reset_after_cross_leg_negative")
                require(not result["stages"][-1]["strict_reset_errors"], "reset after excitation failed")
            result["status"] = "reset_and_neutral_first_step_verified" if geometry is not None else (
                "blocked" if first["strict_reset_errors"] else "requires_reset_wiring_review")
            if exported:
                # Existing ±0.05 rad wiring budget, zero gain; no added physics steps.
                phase = "fresh_action_wiring_no_physics_steps"
                manager = live.action_manager
                obs_protocol.validate_diagnostic_runtime(target, cfg, robot, sensor, manager)
                runtime = list(robot.joint_names)
                channels, ids = [], []
                for name in manager.active_terms:
                    term = manager.get_term(name)
                    selected = list(range(len(runtime)))[term._joint_ids] if isinstance(term._joint_ids, slice) else list(term._joint_ids)
                    channels.extend(term._joint_names)
                    ids.extend(int(i) for i in selected)
                exact_channels(target["joint_names"], channels, ids, runtime)
                action_samples = []
                bounds = {j.get("name"): [float(j.find("limit").get(k)) for k in ("lower", "upper")]
                          for j in ET.parse(target["urdf"]).getroot().findall("joint")}
                for name in channels:
                    require(bounds[name][0] <= -.05 <= .05 <= bounds[name][1], "action injection outside limits")
                    for angle in (-.05, .05):
                        action = torch.zeros((1, len(channels)), device=live.device)
                        action[0, channels.index(name)] = angle
                        manager.process_action(action)
                        manager.apply_action()
                        live.scene.write_data_to_sim()
                        expected = [angle if n == name else 0. for n in runtime]
                        actual = robot.data.joint_pos_target.torch[0].cpu().tolist()
                        close_values(actual, expected, 1e-6, "fresh action target")
                        action_samples.append({"joint": name, "angle_rad": angle, "target_rad": actual})
                live.reset()
                require(not joint_reset_errors(robot), "reset after action wiring failed")
                result["action_wiring"] = {"runtime_joint_order": runtime, "channels": channels,
                    "samples": action_samples, "scope": "real process/apply/cache targets; no tracking or added physics steps"}
                replay = copy.deepcopy(json.loads(manifest.read_text(encoding="utf-8")))
                measured = out / "measured_manifest.json"
                replay["target_binding"].update(source=str(measured), runtime_joint_order=runtime)
                replay["runtime_joint_order"] = runtime
                replay["scope"] = "fresh export measured reset/action/contact routing; no PD/support/collector verdict"
                write_json(measured, replay)
                result["measured_manifest"] = str(measured)
                result["measured_manifest_sha256"] = binding.sha256_file(measured)
            result["baseline_10step"] = "separate real baseline consumer required"
        check_build(BUILD)
        require(binding.sha256_file(args.reset_probe.resolve()) == result["input"]["manifest_sha256"], "input manifest modified")
        original_usd = Path(document["target_binding"]["target"]) if exported else REGISTERED_INPUT / "palm_spatial.usda"
        require(binding.sha256_file(original_usd) == result["input"]["usd_sha256"], "source USD modified")
        require(binding.sha256_file(manifest) == result["replay_manifest_sha256"], "replay manifest modified")
        result.update(completed=True, stage="completed")
        write_json(out / "reset_probe_report.json", result)
        print("RESET_PROBE_COMPLETED", result["status"], binding.sha256_file(out / "reset_probe_report.json"), flush=True)
    except BaseException as error:
        result.update(completed=False, error=repr(error), traceback=traceback.format_exc())
        if args.contact_pairs:
            result.setdefault("contact_pairs", {})["status"] = "unknown"
        # Report and exit before close(): Kit shutdown can otherwise swallow failure with code 0.
        write_json(out / "reset_probe_failure.json", result)
        print("RUNTIME_FAILED", json.dumps({key: result.get(key) for key in
              ("stage", "error", "output", "samples_completed")}), flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    finally:
        if env is not None:
            env.close()
        app.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=BUILD)
    parser.add_argument("--out", type=Path, default=OUT,
                        help="fresh directory only; after first attempt use a new child of output root")
    parser.add_argument("--prepare_registered", action="store_true",
                        help="offline registered replay preparation; requires fresh --out attempt")
    parser.add_argument("--verify_registered", type=Path,
                        help="offline re-read of a prepared registered manifest")
    parser.add_argument("--self_check", action="store_true")
    parser.add_argument("--connection_geometry", action="store_true", help="offline exact six-pair geometry and negative")
    parser.add_argument("--repair_connections", action="store_true", help="isolated six-pair repair with preserved-contact negative")
    parser.add_argument("--reset_probe", type=Path, help="registered manifest reset/first-step attribution")
    parser.add_argument("--contact_pairs", action="store_true",
                        help="observe exact collider-owner body pairs during --reset_probe only")
    parser.add_argument("--export_report", type=Path, help="independently approved isolated export report")
    parser.add_argument("--approved_export_sha256", help="independent approval of export report bytes")
    parser.add_argument("--approved_urdf_sha256", help="independent approval of exported URDF bytes")
    parser.add_argument("--export_manifest_sha256", help="independent approval of fresh prepared reset manifest")
    parser.add_argument("--export_self_check", action="store_true", help="offline real export positive/negative checks")
    offline = any(flag in sys.argv for flag in ("--verify_registered", "--prepare_registered", "--self_check",
                                               "--connection_geometry", "--export_self_check"))
    # Validate new options before importing AppLauncher, including invalid runtime invocations.
    preliminary, _ = parser.parse_known_args()
    export_options = (preliminary.export_report, preliminary.approved_export_sha256,
                      preliminary.approved_urdf_sha256)
    if any(value is not None for value in export_options) and not all(export_options):
        parser.error("--export_report requires nonempty --approved_export_sha256 and --approved_urdf_sha256")
    for field in ("approved_export_sha256", "approved_urdf_sha256", "export_manifest_sha256"):
        value = getattr(preliminary, field)
        if value is not None and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value)):
            parser.error("--" + field + " must be a nonempty lowercase SHA256")
    if preliminary.export_manifest_sha256 is not None and not (preliminary.reset_probe and all(export_options)):
        parser.error("--export_manifest_sha256 requires --reset_probe and approved export parameters")
    if preliminary.export_report and preliminary.reset_probe and preliminary.export_manifest_sha256 is None:
        parser.error("fresh export --reset_probe requires --export_manifest_sha256")
    if preliminary.export_self_check and (not all(export_options) or preliminary.reset_probe):
        parser.error("--export_self_check requires approved export parameters without --reset_probe")
    if preliminary.export_report and offline and not preliminary.export_self_check:
        parser.error("export parameters are only valid for fresh conversion/reset or --export_self_check")
    if not offline:
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if args.export_self_check:
        export_self_check(args)
        return
    if args.verify_registered:
        verify_registered(args.verify_registered)
        return
    if args.prepare_registered:
        prepare_registered(args)
        return
    if args.self_check:
        self_check()
        return
    if args.connection_geometry:
        print(json.dumps(connection_geometry(), indent=2), flush=True)
        return
    if args.contact_pairs and args.reset_probe is None:
        parser.error("--contact_pairs requires --reset_probe")
    if args.repair_connections and (args.reset_probe is None or not args.contact_pairs):
        parser.error("--repair_connections requires --reset_probe and --contact_pairs")
    scope = ("registered mother configuration with isolated diagnostic override, NOT the frozen v3 recipe; "
             if args.export_report else
             "dedicated unregistered config, NOT registered task/v3 and NOT load_diagnostic_target replay; ")
    result = {"completed": False, "stage": "startup",
              "scope": scope + "fixed base, gravity disabled, zero gains/armature; no PD, tracking or support verdict"}
    try:
        if args.reset_probe is not None:
            reset_probe(args, result)
        else:
            run(args, result)
    except BaseException as error:
        result["completed"] = False
        result["error"] = repr(error)
        result["traceback"] = traceback.format_exc()
        print("RUNTIME_FAILED", json.dumps({key: result.get(key) for key in
              ("stage", "error", "output", "samples_completed")}), flush=True)
        if "output" in result:
            write_json(Path(result["output"]) / "failure.json", result)
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)


if __name__ == "__main__":
    main()
