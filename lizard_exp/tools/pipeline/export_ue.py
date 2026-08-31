"""Export SSOT (lizard.urdf + lizard_params.yaml) into UE artifacts.

Output: lizard_exp/ue/lizard_ue.json
  - links with world pose at default joint pose (forward kinematics)
  - joints with world frame, world axis, limits, default angle, PD gains
  - control params + obs layout for the UE inference loop

Plain python, no Isaac Sim needed:
    python lizard_exp/tools/pipeline/export_ue.py

UE is left-handed Z-up, URDF/Isaac is right-handed Z-up. This file keeps
right-handed values; ue/build_lizard_ue.py does the handedness conversion.
"""

import json
import pathlib
import re
import xml.etree.ElementTree as ET

import numpy as np
import yaml

# file lives at lizard_exp/tools/pipeline/ -> exp root is parents[2]
EXP_DIR = pathlib.Path(__file__).resolve().parents[2]
URDF_PATH = EXP_DIR / "lizard.urdf"
PARAMS_PATH = EXP_DIR / "lizard_params.yaml"
OUTPUT_DIR = EXP_DIR / "ue"


def rpy_to_matrix(rpy):
    # URDF convention: R = Rz(yaw) @ Ry(pitch) @ Rx(roll)
    roll, pitch, yaw = rpy
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    rot_x = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    rot_y = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rot_z = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rot_z @ rot_y @ rot_x


def axis_angle_matrix(axis, angle):
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    c, s = np.cos(angle), np.sin(angle)
    x, y, z = axis
    return np.array([
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ])


def matrix_to_rpy(rot):
    sy = np.sqrt(rot[0, 0] ** 2 + rot[1, 0] ** 2)
    singular = sy < 1e-6
    if not singular:
        roll = np.arctan2(rot[2, 1], rot[2, 2])
        pitch = np.arctan2(-rot[2, 0], sy)
        yaw = np.arctan2(rot[1, 0], rot[0, 0])
    else:
        roll = np.arctan2(-rot[1, 2], rot[1, 1])
        pitch = np.arctan2(-rot[2, 0], sy)
        yaw = 0.0
    return [float(roll), float(pitch), float(yaw)]


def parse_vec(text, size):
    return [float(v) for v in text.split()[:size]]


def parse_urdf(urdf_path):
    root = ET.parse(urdf_path).getroot()
    links = {}
    for link in root.findall("link"):
        name = link.get("name")
        entry = {"mass": 0.0, "inertia": None, "inertial_origin": [0.0, 0.0, 0.0], "shape": None, "shape_origin": [0.0, 0.0, 0.0]}
        inertial = link.find("inertial")
        if inertial is not None:
            entry["mass"] = float(inertial.find("mass").get("value"))
            inertia = inertial.find("inertia")
            entry["inertia"] = {k: float(inertia.get(k)) for k in ("ixx", "iyy", "izz", "ixy", "ixz", "iyz")}
            origin = inertial.find("origin")
            if origin is not None and origin.get("xyz"):
                entry["inertial_origin"] = parse_vec(origin.get("xyz"), 3)
        collision = link.find("collision")
        if collision is not None:
            geom = collision.find("geometry")
            cylinder = geom.find("cylinder")
            sphere = geom.find("sphere")
            box = geom.find("box")
            if cylinder is not None:
                entry["shape"] = {
                    "type": "cylinder",
                    "radius": float(cylinder.get("radius")),
                    "length": float(cylinder.get("length")),
                }
            elif sphere is not None:
                entry["shape"] = {"type": "sphere", "radius": float(sphere.get("radius"))}
            elif box is not None:
                entry["shape"] = {"type": "box", "size": parse_vec(box.get("size"), 3)}
            origin = collision.find("origin")
            if origin is not None and origin.get("xyz"):
                entry["shape_origin"] = parse_vec(origin.get("xyz"), 3)
        links[name] = entry

    joints = []
    for joint in root.findall("joint"):
        entry = {
            "name": joint.get("name"),
            "type": joint.get("type"),
            "parent_link": joint.find("parent").get("link"),
            "child_link": joint.find("child").get("link"),
            "origin_pos": [0.0, 0.0, 0.0],
            "axis": [0.0, 0.0, 1.0],
            "limits": None,
        }
        origin = joint.find("origin")
        if origin is not None:
            if origin.get("xyz"):
                entry["origin_pos"] = parse_vec(origin.get("xyz"), 3)
            if origin.get("rpy"):
                entry["origin_rpy"] = parse_vec(origin.get("rpy"), 3)
            else:
                entry["origin_rpy"] = [0.0, 0.0, 0.0]
        else:
            entry["origin_rpy"] = [0.0, 0.0, 0.0]
        axis = joint.find("axis")
        if axis is not None:
            entry["axis"] = parse_vec(axis.get("xyz"), 3)
        limit = joint.find("limit")
        if limit is not None:
            entry["limits"] = {
                "lower": float(limit.get("lower", 0.0)),
                "upper": float(limit.get("upper", 0.0)),
                "effort": float(limit.get("effort", 0.0)),
                "velocity": float(limit.get("velocity", 0.0)),
            }
        joints.append(entry)
    return links, joints


def resolve_default_angles(joints, default_patterns):
    defaults = {}
    for joint in joints:
        if joint["type"] != "revolute":
            continue
        for pattern, angle in default_patterns.items():
            if re.fullmatch(pattern, joint["name"]):
                defaults[joint["name"]] = float(angle)
                break
        else:
            raise ValueError(f"No default angle pattern matches joint: {joint['name']}")
    return defaults


def forward_kinematics(links, joints, default_angles):
    # frame = (pos, rot) of each link in the root frame at the default joint pose
    child_to_joint = {j["child_link"]: j for j in joints}
    root_links = set(links) - set(child_to_joint)
    if len(root_links) != 1:
        raise ValueError(f"Expected exactly one root link, got: {root_links}")
    root_link = next(iter(root_links))

    frames = {root_link: (np.zeros(3), np.eye(3))}
    pending = [root_link]
    children_by_parent = {}
    for joint in joints:
        children_by_parent.setdefault(joint["parent_link"], []).append(joint)

    while pending:
        parent_link = pending.pop(0)
        parent_pos, parent_rot = frames[parent_link]
        for joint in children_by_parent.get(parent_link, []):
            origin_rot = rpy_to_matrix(joint["origin_rpy"])
            joint_rot = np.eye(3)
            if joint["type"] == "revolute":
                angle = default_angles.get(joint["name"], 0.0)
                joint_rot = axis_angle_matrix(joint["axis"], angle)
            child_rot = parent_rot @ origin_rot @ joint_rot
            child_pos = parent_pos + parent_rot @ np.asarray(joint["origin_pos"])
            frames[joint["child_link"]] = (child_pos, child_rot)
            joint["frame_pos"] = (parent_pos + parent_rot @ np.asarray(joint["origin_pos"])).tolist()
            joint["frame_rpy"] = matrix_to_rpy(parent_rot @ origin_rot)
            joint["axis_world"] = (parent_rot @ origin_rot @ np.asarray(joint["axis"])).tolist()
            pending.append(joint["child_link"])

    if len(frames) != len(links):
        raise ValueError("Forward kinematics did not reach all links")

    for name, link in links.items():
        link_pos, link_rot = frames[name]
        com_pos = link_pos + link_rot @ np.asarray(link["inertial_origin"])
        link["com_pos"] = com_pos.tolist()
        link["com_rpy"] = matrix_to_rpy(link_rot)
        shape_pos = link_pos + link_rot @ np.asarray(link["shape_origin"])
        link["shape_pos"] = shape_pos.tolist()
        link["shape_rpy"] = matrix_to_rpy(link_rot)


def main():
    with open(PARAMS_PATH, encoding="utf-8") as f:
        params = yaml.safe_load(f)

    links, joints = parse_urdf(URDF_PATH)
    default_angles = resolve_default_angles(joints, params["default_joint_pos"])
    forward_kinematics(links, joints, default_angles)

    # cross-check SSOT joint order against URDF revolute joints
    urdf_joint_names = [j["name"] for j in joints if j["type"] == "revolute"]
    if urdf_joint_names != params["joint_order"]:
        raise ValueError(
            f"joint_order in lizard_params.yaml does not match URDF order.\n"
            f"  yaml: {params['joint_order']}\n  urdf: {urdf_joint_names}"
        )

    for joint in joints:
        if joint["type"] != "revolute":
            continue
        joint["default_angle"] = default_angles[joint["name"]]
        for group_params in params["actuators"].values():
            matched = any(re.fullmatch(p, joint["name"]) for p in group_params["joint_patterns"])
            if matched:
                joint["stiffness"] = group_params["stiffness"]
                joint["damping"] = group_params["damping"]
                break
        else:
            raise ValueError(f"No actuator group matches joint: {joint['name']}")

    export = {
        "meta": {
            "source": ["lizard.urdf", "lizard_params.yaml"],
            "units": "SI (meters, radians, kg). UE side converts to cm.",
            "handedness": "right-handed Z-up (URDF). UE is left-handed Z-up: mirror Y.",
            "default_base_height": params["robot"]["base_init_height"],
        },
        "links": links,
        "joints": joints,
        "joint_order": params["joint_order"],
        "control": {
            # legs carry the policy's main action scale; spine is locked in
            # the teacher and scaled separately in the family variants
            "action_scale": params["action"]["legs_scale"],
            "action_scale_spine": params["action"]["spine_scale"],
            "use_default_offset": params["action"]["use_default_offset"],
            "dt": params["sim"]["dt"],
            "decimation": params["sim"]["decimation"],
            "policy_hz": round(1.0 / (params["sim"]["dt"] * params["sim"]["decimation"]), 3),
        },
        "obs_layout": params["obs_layout"],
        "command_ranges": params["commands"],
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / "lizard_ue.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2)
    print(f"Written: {output_path}")
    print(f"Links: {len(links)}, joints: {len(joints)} ({len(urdf_joint_names)} actuated)")


if __name__ == "__main__":
    main()
