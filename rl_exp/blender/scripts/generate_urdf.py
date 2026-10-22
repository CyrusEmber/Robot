import bpy
import bmesh
import importlib.util
import json
import math
import os
import shutil
import struct
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
from mathutils import Vector

# Which robot to emit. Default keeps the lizard line's asset exactly as it is; `--robot lizard2`
# emits the new family's asset (co-located hip pivot + the stride axis moved to the hip). Blender
# passes script arguments after a bare `--`, so the call is
#   blender.exe --background --python generate_urdf.py -- --robot lizard2
ROBOT = "lizard"
_argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def cli(name):
    """Value of ``--<name>`` from the argument tail, or None."""
    for _i, _a in enumerate(_argv):
        if _a == "--%s" % name and _i + 1 < len(_argv):
            return _argv[_i + 1]
    return None


ROBOT = cli("robot") or ROBOT
BLEND_OVERRIDE = cli("blend")
OUT_OVERRIDE = cli("out_dir")
CONTRACT_CHECK = "--contract_check" in _argv
MEMORY_SCENE = "--memory_scene" in _argv

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_file_binding_spec = importlib.util.spec_from_file_location(
    "file_binding", os.path.join(_SCRIPT_DIR, "..", "..", "tools", "runrecord", "binding.py"))
file_binding = importlib.util.module_from_spec(_file_binding_spec)
_file_binding_spec.loader.exec_module(file_binding)
#: The ``.blend`` assets stay one level up: this folder holds scripts, not assets.
_ASSET_DIR = os.path.dirname(_SCRIPT_DIR)
TOTAL_MASS = 72.0
MICRO_MASS = 0.05
SHELL_FACTOR = 1.4

# world-frame functional axes, valid AFTER the v8 rename_flip (+180 deg Z on
# top of v5.6's -90, net +90 from the pre-v6 blend: sphere head -y -> +x,
# antenna tail -> -x): old axis -> R_z(180) @ old axis (X,Y negate, Z keeps)
#
# The effort/velocity numbers here are DOCUMENTATIONAL ONLY: the IsaacLab
# URDF importer keeps them as custom float attrs (urdf:limit:*), PhysX does
# not enforce them. Runtime limits come from lizard_params.yaml actuators
# (ImplicitActuator writes drive maxForce / maxJointVelocity at spawn) --
# known divergences: legs 120/150 here vs 180 there, foot 30 vs 70.
AXIS_MAP = {
    "yaw": ("0 0 1", -0.6, 0.6, 80, 4),
    "pitch": ("0 1 0", -0.5, 0.5, 80, 4),
    "haa": ("-1 0 0", -0.6, 0.6, 120, 8),
    "hfe": ("0 0 1", -1.2, 1.2, 150, 8),
    "kfe": ("-1 0 0", -1.6, 1.6, 150, 8),
    "foot": ("0 1 0", -0.5, 0.5, 30, 6),
}

# lizard2 (2026-09-22): the vertical axis belonged at the hip all along (a sprawled leg strides by
# sweeping the femur in the horizontal plane). Here it moves to a NEW co-located hip joint and the
# knee joint takes the fore-aft hinge; `haa` keeps the elevation axis. Measured consequence on the
# lizard geometry: the hip sweep is the only fore-aft DoF (0.148 m per 0.3 rad at the plate centre,
# vs 15 mm before), and the knee hinge lifts the foot instead of twisting it.
_HIP_AXIS = ("0 0 1", -0.6, 0.6, 120, 8)
AXIS_MAP_LIZARD2 = dict(AXIS_MAP, hip=_HIP_AXIS, hfe=("-1 0 0", -1.2, 1.2, 150, 8))

# `micro_budget`: meshless links that came out of the solid-mass budget in the reference asset.
# lizard2's hip pivots must NOT change any solid link's mass, so its budget is fixed to the
# reference arithmetic (72 - 5 * 0.05) and the four new micro links simply add 0.2 kg of total mass.
ROBOT_SPECS = {
    "lizard": {"axes": AXIS_MAP, "blend": "lizard_stance.blend", "hip_joint": False, "micro_budget": None},
    "lizard2": {"axes": AXIS_MAP_LIZARD2, "blend": "lizard_stance.blend", "hip_joint": True, "micro_budget": 5},
    # The 2026-10-08 stance candidate's twin of lizard2: same family, same links, but the blend's
    # default stance now carries a leg-plane yaw per leg, so its in-plane hinges must follow that
    # yaw (`leg_plane_axes`). Written where `--out_dir` says -- never into versions/<family>/meshes,
    # which the frozen v1/v2 asset locks pin, because it is a candidate and not an adopted asset.
    "lizard2_candidate": {"axes": AXIS_MAP_LIZARD2, "blend": "lizard2_stance_candidate.blend",
                          "hip_joint": True, "micro_budget": 5, "leg_plane_axes": True},
    # Read-only build contract only: no candidate geometry or axes approved yet.
    "lizard2_palm_contract": {"axes": None, "blend": "lizard_stance.blend",
                             "hip_joint": False, "micro_budget": None,
                             "source_naming": "palm", "target_naming": "palm"},
    "lizard2_palm_diagnostic": {"axes": None, "blend": None,
                               "hip_joint": False, "micro_budget": None,
                               "source_naming": "palm", "target_naming": "palm"},
}
ROBOT_SPECS["lizard2_palm_spatial"] = {
    "axes": None, "blend": None, "hip_joint": False, "micro_budget": None,
    "source_naming": "palm_spatial", "target_naming": "palm_spatial",
}
ROBOT_SPECS["lizard2_candidate_split"] = dict(
    ROBOT_SPECS["lizard2_candidate"], source_naming="shared", target_naming="split")
for _spec in ROBOT_SPECS.values():
    _spec.setdefault("source_naming", "shared")
    _spec.setdefault("target_naming", "shared")
SPEC = ROBOT_SPECS[ROBOT]
if ROBOT == "lizard2_palm_contract" and not CONTRACT_CHECK:
    raise ValueError("palm contract has no approved geometry; export blocked until P2/P3")
if MEMORY_SCENE and not CONTRACT_CHECK:
    raise ValueError("memory_scene is read-only and requires contract_check")
AXIS_MAP = SPEC["axes"]
DIAGNOSTIC_REPORT = None
SPATIAL_REPORT = None
REFERENCE_ROOT = None
BUILD_REPORT_PATH = cli("build_report")
BUILD_REPORT_SHA256 = cli("build_report_sha256")


def valid_sha256(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


if (BUILD_REPORT_PATH or BUILD_REPORT_SHA256) and ROBOT != "lizard2_palm_spatial":
    raise ValueError("build_report requires lizard2_palm_spatial target")
if ROBOT == "lizard2_palm_spatial":
    if not BLEND_OVERRIDE or not OUT_OVERRIDE or not BUILD_REPORT_PATH:
        raise ValueError("palm spatial requires --blend, --build_report and fresh --out_dir")
    if not valid_sha256(BUILD_REPORT_SHA256):
        raise ValueError("palm spatial requires valid --build_report_sha256")
    scratch = Path(_SCRIPT_DIR).parents[1] / "out"
    requested = Path(OUT_OVERRIDE).resolve()
    if scratch.resolve() not in requested.parents or os.path.lexists(requested):
        raise ValueError("palm spatial output must be fresh and isolated under rl_exp/out")
    sys.path.insert(0, str(Path(_SCRIPT_DIR).parents[1] / "tools/diagnose"))
    from artifact_paths import ArtifactPaths
    artifact_paths = ArtifactPaths()
    report_path = artifact_paths.resolve(Path(BUILD_REPORT_PATH).resolve())
    if file_binding.sha256_file(report_path) != BUILD_REPORT_SHA256:
        raise ValueError("palm spatial approved build_report SHA256 mismatch")
    SPATIAL_REPORT = json.loads(report_path.read_text(encoding="utf-8"))
    reference_path = artifact_paths.resolve(Path(SPATIAL_REPORT["candidate_urdf"]).resolve())
    source_path = artifact_paths.resolve(Path(BLEND_OVERRIDE).resolve())
    BLEND_OVERRIDE = str(source_path)
    declared = SPATIAL_REPORT.get("candidate_files_sha256")
    if (not isinstance(declared, dict)
            or not valid_sha256(SPATIAL_REPORT.get("candidate_blend_sha256"))
            or not valid_sha256(SPATIAL_REPORT.get("candidate_sha256"))
            or not all(valid_sha256(declared.get(name)) for name in
                       ("palm_spatial.blend", "palm_spatial.urdf"))):
        raise ValueError("palm spatial requires explicit candidate blend/urdf SHA256 declarations")
    if (SPATIAL_REPORT["naming"] != "palm_spatial"
            or source_path != report_path.parent / "palm_spatial.blend"
            or reference_path != report_path.parent / "palm_spatial.urdf"
            or declared.get("palm_spatial.blend") != SPATIAL_REPORT["candidate_blend_sha256"]
            or declared.get("palm_spatial.urdf") != SPATIAL_REPORT["candidate_sha256"]):
        raise ValueError("palm spatial source/build_report binding mismatch")
    for relative, expected_hash in declared.items():
        if not isinstance(relative, str) or not relative or not valid_sha256(expected_hash):
            raise ValueError("palm spatial malformed candidate file SHA256 declaration")
        path = (report_path.parent / relative).resolve()
        actual_hash = file_binding.sha256_file(path)
        if (report_path.parent not in path.parents or not valid_sha256(actual_hash)
                or actual_hash != expected_hash):
            raise ValueError("palm spatial candidate file binding mismatch: " + relative)
    SPATIAL_INPUT_HASHES = {str(path): file_binding.sha256_file(path)
                            for path in (source_path, reference_path, report_path)}
    REFERENCE_ROOT = ET.parse(reference_path).getroot()
    REFERENCE_LINKS = {node.get("name"): node for node in REFERENCE_ROOT.findall("link")}
    REFERENCE_JOINTS = {node.find("child").get("link"): node
                        for node in REFERENCE_ROOT.findall("joint")}
if ROBOT == "lizard2_palm_diagnostic":
    from pathlib import Path

    report_path = cli("probe_report")
    if not BLEND_OVERRIDE or not OUT_OVERRIDE or not report_path:
        raise ValueError("palm diagnostic requires --blend, --probe_report and fresh --out_dir")
    scratch = Path(_SCRIPT_DIR).parents[1] / "out"
    requested = Path(OUT_OVERRIDE).resolve()
    if scratch.resolve() not in requested.parents or requested.exists():
        raise ValueError("palm diagnostic output must be fresh and isolated under rl_exp/out")
    DIAGNOSTIC_REPORT = json.loads(Path(report_path).read_text(encoding="utf-8"))
    if (Path(DIAGNOSTIC_REPORT["source"]).resolve() != Path(BLEND_OVERRIDE).resolve()
            or file_binding.sha256_file(Path(BLEND_OVERRIDE)) != DIAGNOSTIC_REPORT["source_sha256"]
            or DIAGNOSTIC_REPORT["naming"] != "palm"):
        raise ValueError("palm diagnostic source/report binding mismatch")
_BLEND_IN = BLEND_OVERRIDE or os.path.join(_ASSET_DIR, SPEC["blend"])
# The family's own directory, read off the declaration rather than guessed: this generator writes the
# meshes the URDF references and the asset lock pins, and since 2026-09-28 that tree is per-family
# (`versions/<family>/assets.json`). It used to write into a scratch `<robot>_urdf/` directory while
# referencing `../meshes/` (the shared tree), so a regeneration landed where nothing read it.
# `--out_dir` overrides it for a candidate family that has no declaration on purpose.
_EXP_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
if not CONTRACT_CHECK and SPEC["source_naming"] != SPEC["target_naming"]:
    scratch = os.path.realpath(os.path.join(_EXP_DIR, "out"))
    requested = os.path.realpath(OUT_OVERRIDE) if OUT_OVERRIDE else scratch
    if (not OUT_OVERRIDE or os.path.commonpath((scratch, requested)) != scratch
            or requested == scratch or os.path.lexists(requested)):
        raise ValueError("renamed export requires a fresh isolated --out_dir under rl_exp/out")
if CONTRACT_CHECK:
    OUT_DIR = None
elif OUT_OVERRIDE:
    OUT_DIR = os.path.abspath(OUT_OVERRIDE)
else:
    _DECLARATION = os.path.join(_EXP_DIR, "versions", ROBOT, "assets.json")
    with open(_DECLARATION) as _fh:
        _DECLARED = json.load(_fh)["meshes_dir"]
    OUT_DIR = os.path.join(_EXP_DIR, _DECLARED)

BALL_MESHES = {
    "Roundcube.001", "Roundcube.017", "Roundcube.025", "Roundcube.018", "Roundcube.019",
    "Roundcube.014", "Roundcube.007", "Roundcube.010", "Roundcube.002",
    "Roundcube.013", "Roundcube.006", "Roundcube.005", "Roundcube",
    "Roundcube.015", "Roundcube.008", "Roundcube.011", "Roundcube.003",
}

# Blender imports the stdlib-only table without executing tasks/__init__.py.
sys.path.insert(0, os.path.join(_EXP_DIR, "tasks"))
import joint_names as leg_names

# Bone roles are independent of target joint roles: the old lizard2 exporter synthesizes hip,
# while the palm source must already carry all four revolutes. No old distal role can be dropped.
for _spec in ROBOT_SPECS.values():
    _spec["source_roles"] = (("swing", "abduct", "twist", "bend", "end")
                             if _spec["source_naming"] == "palm_spatial" else
                             leg_names.CHAIN_ROOTS[:-1] if _spec["source_naming"] == "palm"
                             else leg_names.CHAIN_ROOTS[1:])
    _spec["target_roles"] = (leg_names.CHAIN_ROOTS if _spec["hip_joint"]
                             else _spec["source_roles"])


def validate_build_contract(bones, spec):
    """Bind source bones to target roles and check actual parents before any mesh write.

    Palm samples prove topology only, not pivot positions, mesh ownership or approved geometry.
    Legacy source lacks the synthesized hip; only the legacy exporter may insert that role.
    """
    source = leg_names.naming_for(spec["source_naming"])
    target = leg_names.naming_for(spec["target_naming"])
    binding = {}
    for leg in leg_names.LEGS:
        source_roots = leg_names.roots_of(source, leg)
        target_roots = leg_names.roots_of(target, leg)
        def role_keys(naming):
            return (("swing", "abduct", "twist", "bend", "end") if naming == "palm_spatial"
                    else leg_names.CHAIN_ROOTS[:-1] if naming == "palm" else leg_names.CHAIN_ROOTS)
        source_keys = role_keys(spec["source_naming"])
        target_keys = role_keys(spec["target_naming"])
        if source_keys != target_keys:
            raise ValueError(f"{leg}: source/target roles differ; dropping distal bones is forbidden")
        source_by_role = dict(zip(source_keys, source_roots))
        target_by_role = dict(zip(target_keys, target_roots))
        source_roles, target_roles = spec["source_roles"], spec["target_roles"]
        synthetic = set(target_roles) - set(source_roles)
        legacy_hip = (spec["hip_joint"] and spec["source_naming"] == "shared"
                      and source_roles == leg_names.CHAIN_ROOTS[1:])
        if (set(source_roles) - set(target_roles)
                or synthetic != ({"hip"} if legacy_hip else set())
                or not set(target_roles) <= set(target_keys)):
            raise ValueError(f"{leg}: invalid source/target role binding")
        roles = tuple((role, source_by_role[role]) for role in source_roles)
        names = tuple(leg_names.link_name(leg, root) for _, root in roles)
        actual = {name for name in bones if name.startswith(leg + "_")}
        if actual != set(names):
            raise ValueError(f"{leg}: source bones missing={sorted(set(names) - actual)} "
                             f"extra={sorted(actual - set(names))}")
        for index, name in enumerate(names):
            parent = bones[name]["parent"]
            if index:
                if parent != names[index - 1]:
                    raise ValueError(f"{name}: parent {parent!r}, expected {names[index - 1]!r}")
            elif parent not in bones or any(parent.startswith(p + "_") for p in leg_names.LEGS):
                raise ValueError(f"{name}: missing or cross-leg root parent {parent!r}")
            children = {child for child, data in bones.items() if data["parent"] == name}
            expected = {names[index + 1]} if index + 1 < len(names) else set()
            if children != expected:
                raise ValueError(f"{name}: children {sorted(children)}, expected {sorted(expected)}")
        binding[leg] = {
            "roles": {role: {"source_bone": (leg_names.link_name(leg, source_by_role[role])
                                              if role in source_roles else None),
                             "target_link": leg_names.link_name(leg, target_by_role[role]),
                             "target_joint": leg_names.joint_name(leg, target_by_role[role])}
                      for role in target_roles},
            "end_link": leg_names.end_link(leg, target),
            "end_joint": leg_names.joint_name(leg, target_roots[-1]),
        }
    return binding


if not MEMORY_SCENE:
    bpy.ops.wm.open_mainfile(filepath=_BLEND_IN)
depsgraph = bpy.context.evaluated_depsgraph_get()
scene = bpy.context.scene

arm = next(o for o in scene.objects if o.type == "ARMATURE")
# head in WORLD space (armature may carry the v5.6 rotation as object
# transform; meshes are already read via matrix_world -- keep one frame)
bones = {b.name: {"head": (arm.matrix_world @ b.head_local).copy(), "parent": b.parent.name if b.parent else None} for b in arm.data.bones}

binding = validate_build_contract(bones, SPEC)
if DIAGNOSTIC_REPORT is not None:
    expected = set(bones) - {"base_link"}
    if (set(DIAGNOSTIC_REPORT["candidate_axes_world"]) != expected
            or set(DIAGNOSTIC_REPORT["candidate_limits_rad"]) != expected):
        raise ValueError("palm diagnostic report must cover every actual joint")
    if any(max(abs(pb.matrix_basis[i][j] - (i == j)) for i in range(4) for j in range(4)) != 0
           for pb in arm.pose.bones):
        raise ValueError("palm diagnostic requires baked neutral rest frames")
    for obj in scene.objects:
        if obj.type == "MESH" and (obj.parent != arm or obj.parent_type != "BONE" or obj.parent_bone not in bones):
            raise ValueError("palm diagnostic contains unbound mesh: " + obj.name)
    for name, axis in DIAGNOSTIC_REPORT["candidate_axes_world"].items():
        if abs(Vector(axis).length - 1) > 1e-5:
            raise ValueError("palm diagnostic axis is not normalized: " + name)
if CONTRACT_CHECK:
    print("CONTRACT_ONLY robot=%s source=%s target=%s geometry_proven=False" %
          (ROBOT, SPEC["source_naming"], SPEC["target_naming"]))
    print(json.dumps({leg: {"roles": tuple(data["roles"]), "end_link": data["end_link"],
                           "end_joint": data["end_joint"]} for leg, data in binding.items()}, sort_keys=True))
    raise SystemExit(0)

# Keep geometry and axes in source vocabulary; only output ownership changes.
output_links = {}
source_roles = {}
source_legs = {}
for leg, data in binding.items():
    for role, bound in data["roles"].items():
        source_link = bound["source_bone"] or leg_names.link_name(leg, role)
        output_links[source_link] = bound["target_link"]
        source_roles[source_link] = role
        source_legs[source_link] = leg


def output_link(link):
    return output_links.get(link, link)


link_meshes = {}
for obj in scene.objects:
    if obj.type == "MESH" and obj.parent_type == "BONE":
        link_meshes.setdefault(obj.parent_bone, []).append(obj)

missing = [b for b in bones if b not in link_meshes]
print("links_without_mesh=%s" % missing)

def build_bmesh(mesh_objects, offset, evaluated):
    bm = bmesh.new()
    for obj in mesh_objects:
        source = obj.evaluated_get(depsgraph) if evaluated else obj
        me = source.to_mesh()
        mat = obj.matrix_world.copy()
        mat.translation -= offset
        me.transform(mat)
        bm.from_mesh(me)
        source.to_mesh_clear()
    return bm


def export_stl(bm, path):
    tris = []
    for face in bm.faces:
        vs = face.verts
        if len(vs) == 3:
            tris.append((vs[0].co, vs[1].co, vs[2].co))
        else:
            for i in range(1, len(vs) - 1):
                tris.append((vs[0].co, vs[i].co, vs[i + 1].co))
    with open(path, "wb") as fh:
        fh.write(b"lizard urdf export".ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(tris)))
        for va, vb, vc in tris:
            normal = (vb - va).cross(vc - va)
            length = normal.length
            normal = normal / length if length > 0 else Vector((0.0, 0.0, 0.0))
            fh.write(struct.pack("<12fH", normal.x, normal.y, normal.z,
                                 va.x, va.y, va.z, vb.x, vb.y, vb.z, vc.x, vc.y, vc.z, 0))
    # This used to free the bmesh, which made the OBJ export that follows it raise
    # `ReferenceError: BMesh data ... has been removed` under Blender 5.x: the caller exports both
    # formats from one bmesh and owns it, so it frees it.


def export_obj(bm, path):
    """The same triangles as ``export_stl``, as an OBJ, because that is what the URDFs reference.

    Written beside the STL rather than instead of it: the URDFs in ``versions/<family>/`` name
    ``meshes/collision/<link>_collision.obj``, and a regeneration that only produced STL would leave
    every one of those references dangling.
    """
    verts, faces = [], []
    for face in bm.faces:
        vs = face.verts
        for i in range(1, len(vs) - 1):
            indices = []
            for vertex in (vs[0], vs[i], vs[i + 1]):
                verts.append(vertex.co)
                indices.append(len(verts))
            faces.append(indices)
    with open(path, "w") as fh:
        fh.write("# lizard mesh\n")
        for co in verts:
            fh.write("v %.6f %.6f %.6f\n" % (co.x, co.y, co.z))
        for tri in faces:
            fh.write("f %d %d %d\n" % tuple(tri))


def validate_spatial_scene():
    """Check the loaded saved-source tree, neutral geometry [m] and reference binding prewrite."""
    if len([o for o in scene.objects if o.type == "ARMATURE"]) != 1:
        raise ValueError("palm spatial requires exactly one armature")
    if (len(REFERENCE_LINKS) != 31 or len(REFERENCE_JOINTS) != 30
            or len(REFERENCE_ROOT.findall("link")) != 31
            or len(REFERENCE_ROOT.findall("joint")) != 30
            or set(bones) != set(REFERENCE_LINKS)
            or set(REFERENCE_JOINTS) != set(bones) - {"base_link"}
            or set(SPATIAL_REPORT["axes_neutral"]) != set(REFERENCE_JOINTS)):
        raise ValueError("palm spatial requires full 31-link/30-joint reference and axes")
    if any(max(abs(pb.matrix_basis[i][j] - (i == j)) for i in range(4) for j in range(4)) > 1e-7
           for pb in arm.pose.bones):
        raise ValueError("palm spatial requires neutral bone rest basis")
    neutral = [row for row in SPATIAL_REPORT["snapshots"] if row["case"] == "neutral"]
    if len(neutral) != 1 or neutral[0]["q_rad"]:
        raise ValueError("palm spatial requires unique neutral snapshot")
    neutral = neutral[0]
    if set(neutral["pivots"]) != set(bones) or bones["base_link"]["parent"] is not None:
        raise ValueError("palm spatial neutral pivot/root mismatch")
    for name, bone in bones.items():
        if (bone["head"] - Vector(neutral["pivots"][name])).length > 5e-6:
            raise ValueError("palm spatial neutral pivot mismatch: " + name)
        if name == "base_link":
            continue
        joint = REFERENCE_JOINTS[name]
        parent = joint.find("parent").get("link")
        origin = joint.find("origin")
        axis = Vector(SPATIAL_REPORT["axes_neutral"][name])
        limit = joint.find("limit")
        if (joint.get("name") != name + "_joint" or joint.get("type") != "revolute"
                or parent != bone["parent"]
                or Vector(tuple(float(v) for v in origin.get("rpy").split())).length > 1e-12
                or (bone["head"] - bones[parent]["head"]
                    - Vector(tuple(float(v) for v in origin.get("xyz").split()))).length > 5e-6
                or not all(math.isfinite(v) for v in axis) or abs(axis.length - 1) > 1e-5
                or (axis - Vector(tuple(float(v) for v in joint.find("axis").get("xyz").split()))).length > 2e-6
                or set(limit.attrib) != {"lower", "upper", "effort", "velocity"}
                or not all(math.isfinite(float(v)) for v in limit.attrib.values())
                or float(limit.get("lower")) >= float(limit.get("upper"))
                or float(limit.get("effort")) <= 0 or float(limit.get("velocity")) <= 0):
            raise ValueError("palm spatial reference parent/pivot/axis/limit mismatch: " + name)
    if set(SPATIAL_REPORT["definitions"]) != set(leg_names.LEGS):
        raise ValueError("palm spatial definitions must cover all legs")
    for leg, data in binding.items():
        roles = data["roles"]
        definition = SPATIAL_REPORT["definitions"][leg]
        for role in ("abduct", "twist", "bend", "end"):
            if definition[role] != roles[role]["source_bone"]:
                raise ValueError("palm spatial definition mismatch: " + leg)
        pivot = bones[roles["swing"]["source_bone"]]["head"]
        if any((bones[roles[r]["source_bone"]]["head"] - pivot).length > 5e-6
               for r in ("abduct", "twist")):
            raise ValueError("palm spatial three axes must share pivot: " + leg)
        direction = (bones[definition["bend"]]["head"] - pivot).normalized()
        if ((direction - Vector(definition["axis_neutral"])).length > 2e-6
                or (direction - Vector(SPATIAL_REPORT["axes_neutral"][definition["twist"]])).length > 2e-6):
            raise ValueError("palm spatial twist axis must follow upper limb: " + leg)
    objects = {o.name: o for o in scene.objects if o.type == "MESH"}
    if set(objects) != set(neutral["meshes"]):
        raise ValueError("palm spatial neutral mesh inventory mismatch")
    for name, obj in objects.items():
        row = neutral["meshes"][name]
        if (obj.parent != arm or obj.parent_type != "BONE" or obj.parent_bone != row["link"]
                or obj.parent_bone not in bones):
            raise ValueError("palm spatial mesh ownership mismatch: " + name)
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            indices = sorted({i * (len(mesh.vertices) - 1) // 31 for i in range(32)})
            if (len(mesh.vertices) != row["vertex_count"] or indices != row["indices"]
                    or len(row["points"]) != len(indices)
                    or any((evaluated.matrix_world @ mesh.vertices[i].co - Vector(point)).length > 5e-6
                           for i, point in zip(indices, row["points"]))):
                raise ValueError("palm spatial neutral saved mesh mismatch: " + name)
        finally:
            evaluated.to_mesh_clear()
    residual = 0.0
    for name, node in REFERENCE_LINKS.items():
        inertial = node.find("inertial")
        try:
            if inertial is None or [child.tag for child in inertial].count("origin") != 1:
                raise ValueError("missing/duplicate inertial origin")
            origin, tensor, mass = (inertial.find(tag) for tag in ("origin", "inertia", "mass"))
            if (tensor is None or mass is None
                    or len(inertial.findall("inertia")) != 1 or len(inertial.findall("mass")) != 1
                    or set(origin.attrib) != {"xyz", "rpy"}
                    or set(tensor.attrib) != {"ixx", "ixy", "ixz", "iyy", "iyz", "izz"}
                    or set(mass.attrib) != {"value"}):
                raise ValueError("missing/malformed inertial fields")
            xyz, rpy = (tuple(float(v) for v in origin.get(key).split()) for key in ("xyz", "rpy"))
            mass_value = float(mass.get("value"))
            values = (mass_value, *xyz, *rpy, *(float(v) for v in tensor.attrib.values()))
            if len(xyz) != 3 or len(rpy) != 3 or not all(math.isfinite(v) for v in values) or mass_value <= 0:
                raise ValueError("nonfinite/invalid inertial values")
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("palm spatial requires finite full inertial: " + name) from exc
        for kind in ("visual", "collision"):
            nodes = node.findall(kind)
            objs = link_meshes.get(name, [])
            if kind == "collision":
                objs = [o for o in objs if o.name not in BALL_MESHES]
            if len(nodes) != bool(objs):
                raise ValueError("palm spatial reference mesh coverage mismatch: " + name)
            if not nodes:
                continue
            origin = nodes[0].find("origin")
            if any(float(v) != 0 for key in ("xyz", "rpy") for v in origin.get(key).split()):
                raise ValueError("palm spatial reference mesh origin unsupported: " + name)
            relative = nodes[0].find("geometry/mesh").get("filename")
            if relative not in SPATIAL_REPORT["candidate_files_sha256"]:
                raise ValueError("palm spatial reference mesh hash missing: " + relative)
            reference, faces = [], []
            with open(reference_path.parent / relative, encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("v "):
                        reference.append(Vector(tuple(float(v) for v in line.split()[1:4])))
                    elif line.startswith("f "):
                        faces.append(tuple(int(v) for v in line.split()[1:]))
            if faces != [(i + 1, i + 2, i + 3) for i in range(0, len(reference), 3)]:
                raise ValueError("palm spatial reference OBJ triangle topology unsupported: " + name)
            bm = build_bmesh(objs, bones[name]["head"], kind == "visual")
            try:
                actual = [vertex.co.copy() for face in bm.faces for i in range(1, len(face.verts) - 1)
                          for vertex in (face.verts[0], face.verts[i], face.verts[i + 1])]
                if not actual or len(actual) != len(reference):
                    raise ValueError("palm spatial reference OBJ vertex coverage mismatch: " + name)
                gap = max((a - b).length for a, b in zip(actual, reference))
                residual = max(residual, gap)
                if gap > 5e-6:
                    raise ValueError("palm spatial actual mesh/reference OBJ mismatch: %s %s %.9g m" % (name, kind, gap))
            finally:
                bm.free()
    return residual


if SPATIAL_REPORT is not None:
    SPATIAL_GEOMETRY_RESIDUAL = validate_spatial_scene()
if SPEC["source_naming"] != SPEC["target_naming"] or DIAGNOSTIC_REPORT is not None or SPATIAL_REPORT is not None:
    # Exclusive creation closes the check/write race; isolated samples never clean another tree.
    os.makedirs(OUT_DIR, exist_ok=False)
else:
    for sub in ("visual", "collision"):
        sub_path = os.path.join(OUT_DIR, "meshes", sub)
        if os.path.exists(sub_path):
            shutil.rmtree(sub_path)
os.makedirs(os.path.join(OUT_DIR, "meshes", "visual"), exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "meshes", "collision"), exist_ok=True)


link_data = {}
for link, bone in bones.items():
    offset = bone["head"]
    entry = {"parent": bone["parent"], "origin": offset}
    if link in link_meshes:
        objs = link_meshes[link]
        vis_bm = build_bmesh(objs, offset, True)
        area = sum(f.calc_area() for f in vis_bm.faces)
        coords = [v.co.copy() for v in vis_bm.verts]
        export_stl(vis_bm, os.path.join(OUT_DIR, "meshes", "visual", "%s_visual.stl" % output_link(link)))
        export_obj(vis_bm, os.path.join(OUT_DIR, "meshes", "visual", "%s_visual.obj" % output_link(link)))
        col_objs = [o for o in objs if o.name not in BALL_MESHES]
        if col_objs:
            col_bm = build_bmesh(col_objs, offset, False)
            export_stl(col_bm, os.path.join(OUT_DIR, "meshes", "collision", "%s_collision.stl" % output_link(link)))
            export_obj(col_bm, os.path.join(OUT_DIR, "meshes", "collision", "%s_collision.obj" % output_link(link)))
            col_bm.free()
        vis_bm.free()
        entry["has_collision"] = bool(col_objs)
        entry["area"] = area
        entry["aabb_min"] = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
        entry["aabb_max"] = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    else:
        entry["has_collision"] = False
        entry["area"] = 0.0
        entry["aabb_min"] = Vector((-0.005, -0.005, -0.005))
        entry["aabb_max"] = Vector((0.005, 0.005, 0.005))
    link_data[link] = entry

if SPEC["hip_joint"]:
    # Co-located hip pivot: same origin as the leg's haa, meshless, inserted as haa's parent, so the
    # URDF carries a revolute whose origin is 0 relative to its parent -- the second hip DoF the leg
    # was missing. The .blend stays untouched: this pivot is a rigging decision the generator owns.
    hip_sources = {data["roles"]["haa"]["source_bone"]: leg_names.link_name(leg, "hip")
                   for leg, data in binding.items() if data["roles"]["hip"]["source_bone"] is None}
    rebuilt = {}
    for link, entry in link_data.items():
        if link in hip_sources:
            hip = hip_sources[link]
            rebuilt[hip] = {"parent": entry["parent"], "origin": entry["origin"].copy(),
                            "has_collision": False, "area": 0.0,
                            "aabb_min": Vector((-0.005, -0.005, -0.005)),
                            "aabb_max": Vector((0.005, 0.005, 0.005))}
            entry = dict(entry)
            entry["parent"] = hip
        rebuilt[link] = entry
    link_data = rebuilt

micro_count = sum(1 for e in link_data.values() if e["area"] == 0.0)
# lizard: micro links come out of the solid budget (arithmetic unchanged). lizard2: the budget is
# frozen to the REFERENCE micro count so every pre-existing link keeps its exact mass, and the new
# hip pivots only add their own MICRO_MASS to the total (72.0 -> 72.2 kg).
_budget_micros = micro_count if SPEC["micro_budget"] is None else SPEC["micro_budget"]
solid_budget = TOTAL_MASS - _budget_micros * MICRO_MASS
total_area = sum(e["area"] for e in link_data.values())
for link, entry in link_data.items():
    entry["mass"] = (float(REFERENCE_LINKS[link].find("inertial/mass").get("value"))
                     if SPATIAL_REPORT is not None else
                     MICRO_MASS if entry["area"] == 0.0 else solid_budget * entry["area"] / total_area)


def inertia_box(mass, aabb_min, aabb_max):
    x = max(aabb_max.x - aabb_min.x, 1e-4)
    y = max(aabb_max.y - aabb_min.y, 1e-4)
    z = max(aabb_max.z - aabb_min.z, 1e-4)
    ixx = mass / 12.0 * (y * y + z * z)
    iyy = mass / 12.0 * (x * x + z * z)
    izz = mass / 12.0 * (x * x + y * y)
    return ixx, iyy, izz


def joint_spec(link):
    if DIAGNOSTIC_REPORT is not None:
        axis = DIAGNOSTIC_REPORT["candidate_axes_world"][link]
        lo, hi = DIAGNOSTIC_REPORT["candidate_limits_rad"][link]
        leg = link.partition("_")[0]
        effort, velocity = ((70, 6) if link.endswith(("_wrist", "_ankle")) else (180, 10)) if leg in leg_names.LEGS else (80, 4)
        return " ".join("%.9f" % value for value in axis), lo, hi, effort, velocity
    if link in source_roles:
        return AXIS_MAP[source_roles[link]]
    # Non-leg body joints retain the existing yaw/pitch export convention.
    for suffix, spec in AXIS_MAP.items():
        if link.endswith("_" + suffix):
            return spec
    return None


# Per-leg baked flexion-plane yaw [deg]: once the default stance carries a leg yaw, a leg's flexion
# plane is no longer the body's own x = const plane, and an in-plane hinge has to stay perpendicular
# to it. Read off the pose itself -- the two proximal segment directions -- rather than restating the
# stance constants here, so the two cannot drift apart. The branch keeps the frozen asset's sign
# convention: every leg's in-plane hinge keeps a negative x component.
LEG_YAW = {}
for _leg in ("lf", "rf", "rl", "rr"):
    if "%s_kfe" % _leg in bones:
        _d1 = bones["%s_hfe" % _leg]["head"] - bones["%s_haa" % _leg]["head"]
        _d2 = bones["%s_kfe" % _leg]["head"] - bones["%s_hfe" % _leg]["head"]
        _normal = _d1.cross(_d2).normalized()
        _yaw = math.degrees(math.atan2(_normal.y, _normal.x))
        LEG_YAW[_leg] = _yaw - math.copysign(180.0, _yaw) if abs(_yaw) > 90.0 else _yaw


def axis_for(link, axis_str):
    """``axis_str`` rotated by the link's own leg-plane yaw, when the spec asks for it.

    A baked leg yaw turns the leg's flexion plane while every exported joint frame keeps ``rpy = 0``,
    so yesterday's world-X hinge would point out of the plane. ``R_z(yaw) @ base_axis`` is the same
    hinge in the new plane: the vertical hip yaw is untouched, the in-plane hinges
    (``haa``/``hfe``/``kfe``, base -X) and the sagittal ``foot`` (base +Y) follow their leg.
    """
    if not SPEC.get("leg_plane_axes"):
        return axis_str
    yaw = LEG_YAW.get(source_legs.get(link))
    if yaw is None or source_roles.get(link) not in ("haa", "hfe", "kfe", "foot"):
        return axis_str
    v = [float(value) for value in axis_str.split()]
    theta = math.radians(yaw)
    return "%.6f %.6f %.6f" % (v[0] * math.cos(theta) - v[1] * math.sin(theta),
                               v[0] * math.sin(theta) + v[1] * math.cos(theta), v[2])


xml = ['<?xml version="1.0"?>', '<robot name="lizard_robot">']
for link, entry in link_data.items():
    mass = entry["mass"]
    com = (entry["aabb_min"] + entry["aabb_max"]) / 2.0
    ixx, iyy, izz = inertia_box(mass, entry["aabb_min"], entry["aabb_max"])
    xml.append('  <link name="%s">' % output_link(link))
    if SPATIAL_REPORT is not None:
        xml.append(ET.tostring(REFERENCE_LINKS[link].find("inertial"), encoding="unicode"))
    else:
        xml.append('    <inertial>')
        xml.append('      <origin xyz="%.6f %.6f %.6f" rpy="0 0 0"/>' % (com.x, com.y, com.z))
        xml.append('      <mass value="%.4f"/>' % mass)
        xml.append('      <inertia ixx="%.6f" ixy="0" ixz="0" iyy="%.6f" iyz="0" izz="%.6f"/>' % (ixx, iyy, izz))
        xml.append('    </inertial>')
    if entry["area"] > 0.0:
        xml.append('    <visual>')
        xml.append('      <origin xyz="0 0 0" rpy="0 0 0"/>')
        xml.append('      <geometry><mesh filename="meshes/visual/%s_visual.obj"/></geometry>' % output_link(link))
        xml.append('    </visual>')
        if entry["has_collision"]:
            xml.append('    <collision>')
            xml.append('      <origin xyz="0 0 0" rpy="0 0 0"/>')
            xml.append('      <geometry><mesh filename="meshes/collision/%s_collision.obj"/></geometry>' % output_link(link))
            xml.append('    </collision>')
    xml.append('  </link>')

for link, entry in link_data.items():
    parent = entry["parent"]
    if parent is None:
        continue
    if SPATIAL_REPORT is not None:
        # Explicit reference preserves normalized axes, original limits and documentary drive values.
        xml.append(ET.tostring(REFERENCE_JOINTS[link], encoding="unicode"))
        continue
    rel = entry["origin"] - link_data[parent]["origin"]
    spec = joint_spec(link)
    axis, lo, hi, effort, vel = spec
    xml.append('  <joint name="%s_joint" type="revolute">' % output_link(link))
    xml.append('    <parent link="%s"/>' % output_link(parent))
    xml.append('    <child link="%s"/>' % output_link(link))
    xml.append('    <origin xyz="%.6f %.6f %.6f" rpy="0 0 0"/>' % (rel.x, rel.y, rel.z))
    xml.append('    <axis xyz="%s"/>' % axis_for(link, axis))
    if DIAGNOSTIC_REPORT is not None:
        xml.append('    <limit lower="%.9f" upper="%.9f" effort="%d" velocity="%d"/>' % (lo, hi, effort, vel))
    else:
        xml.append('    <limit lower="%.2f" upper="%.2f" effort="%d" velocity="%d"/>' % (lo, hi, effort, vel))
    xml.append('  </joint>')

xml.append('</robot>')
urdf_path = os.path.join(OUT_DIR, "%s.urdf" % ROBOT)
with open(urdf_path, "w") as f:
    f.write("\n".join(xml) + "\n")

mass_sum = sum(e["mass"] for e in link_data.values())
print("=== URDF ===")
print("robot=%s blend=%s out_dir=%s" % (ROBOT, _BLEND_IN, OUT_DIR))
print("links=%d joints=%d total_mass=%.2fkg" % (len(link_data), len(link_data) - 1, mass_sum))
print("saved=%s" % urdf_path)
if SPEC.get("leg_plane_axes"):
    print("=== LEG PLANE AXES (R_z(yaw) @ base) ===")
    for leg in ("lf", "rf", "rl", "rr"):
        print("  %s yaw=%+7.3f deg | haa/hfe/kfe %s | foot %s"
              % (leg, LEG_YAW[leg], axis_for("%s_haa" % leg, AXIS_MAP["haa"][0]),
                 axis_for("%s_foot" % leg, AXIS_MAP["foot"][0])))
if SPATIAL_REPORT is not None:
    if any(file_binding.sha256_file(Path(path)) != value for path, value in SPATIAL_INPUT_HASHES.items()):
        raise ValueError("palm spatial source changed during export")
    export_report = {
        "status": "KINEMATIC_CANDIDATE_NOT_ADOPTED", "robot": ROBOT, "naming": "palm_spatial",
        "source_blend": str(source_path), "build_report": str(report_path),
        "reference_urdf": str(reference_path), "input_sha256": SPATIAL_INPUT_HASHES,
        "exporter_sha256": file_binding.sha256_file(Path(__file__)),
        "mass_policy": "reference_full_link_inertial", "links": len(link_data),
        "joints": len(REFERENCE_JOINTS), "total_mass_kg": mass_sum,
        "actual_mesh_reference_obj_residual_m": SPATIAL_GEOMETRY_RESIDUAL,
        "files_sha256": {p.relative_to(OUT_DIR).as_posix(): file_binding.sha256_file(p)
                         for p in sorted(Path(OUT_DIR).rglob("*")) if p.is_file()},
    }
    (Path(OUT_DIR) / "export.json").write_text(json.dumps(export_report, indent=2), encoding="utf-8")
print("=== DONE ===")
