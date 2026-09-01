"""UE editor script: assemble the lizard physics actor from ue/lizard_ue.json.

Run inside UE editor (Python plugin enabled):
    import runpy; runpy.run_path(r"<path>/ue/build_lizard_ue.py")
or: Python -> Execute Python Script.

What it does:
  1. Spawns one StaticMeshActor per link with a shape (BasicShapes
     cylinder/sphere/box), scaled/sized/massed from lizard_ue.json,
     simulate physics on.
  2. Spawns one PhysicsConstraintActor per joint at the joint world frame,
     constrains parent/child bodies, applies joint limits.
  3. Prints a joint table for manual verification (position drive gains).

Handedness: lizard_ue.json is right-handed Z-up (URDF). UE is left-handed
Z-up, so Y is mirrored on import. If the robot looks mirrored wrong, flip
the sign of MIRROR_Y below.

NOTE: constraint-drive API names vary across UE 5.x versions. The CONSTRAINT
section is best-effort; verify limits/drives in the details panel after run.
"""

import json
import math
import os

import unreal

MIRROR_Y = -1.0
BASIC_SHAPES = {
    "cylinder": "/Engine/BasicShapes/Cylinder.Cylinder",
    "sphere": "/Engine/BasicShapes/Sphere.Sphere",
    "box": "/Engine/BasicShapes/Cube.Cube",
}
# BasicShapes cylinder: radius 50 cm, height 100 cm. sphere: radius 50 cm. cube: 100 cm.
BASIC_SHAPE_RADIUS_CM = 50.0
BASIC_SHAPE_HEIGHT_CM = 100.0


def load_data():
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lizard_ue.json")
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def rpy_to_quat(rpy):
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return w, x, y, z


def quat_to_ue_rotator(w, x, y, z):
    # mirror Y for left-handed UE, then quaternion -> FRotator (degrees)
    y = -y
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return unreal.Rotator(math.degrees(pitch), math.degrees(yaw), math.degrees(roll))


def to_ue_location(pos_m):
    return unreal.Vector(pos_m[0] * 100.0, pos_m[1] * 100.0 * MIRROR_Y, pos_m[2] * 100.0)


def apply_shape(comp, shape):
    if shape["type"] == "cylinder":
        scale_xy = shape["radius"] * 100.0 / BASIC_SHAPE_RADIUS_CM
        scale_z = shape["length"] * 100.0 / BASIC_SHAPE_HEIGHT_CM
        comp.set_world_scale3d(unreal.Vector(scale_xy, scale_xy, scale_z))
    elif shape["type"] == "sphere":
        scale = shape["radius"] * 100.0 / BASIC_SHAPE_RADIUS_CM
        comp.set_world_scale3d(unreal.Vector(scale, scale, scale))
    elif shape["type"] == "box":
        size_x, size_y, size_z = shape["size"]
        comp.set_world_scale3d(unreal.Vector(size_x, size_y, size_z))


def spawn_link_bodies(data):
    link_actors = {}
    for name, link in data["links"].items():
        shape = link["shape"]
        if shape is None:
            unreal.log_warning(f"link {name} has no shape, skipped")
            continue
        mesh_path = BASIC_SHAPES[shape["type"]]
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.StaticMeshActor, to_ue_location(link["shape_pos"])
        )
        actor.set_actor_label(f"Lizard_{name}")
        comp = actor.static_mesh_component
        comp.set_static_mesh(unreal.load_asset(mesh_path))
        comp.set_world_rotation(quat_to_ue_rotator(*rpy_to_quat(link["shape_rpy"])))
        apply_shape(comp, shape)
        comp.set_simulate_physics(True)
        comp.set_mass(link["mass"])
        comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        link_actors[name] = actor
    return link_actors


def spawn_joint_constraints(data, link_actors):
    for joint in data["joints"]:
        if joint["type"] not in ("revolute", "fixed"):
            continue
        parent_actor = link_actors.get(joint["parent_link"])
        child_actor = link_actors.get(joint["child_link"])
        if parent_actor is None or child_actor is None:
            unreal.log_warning(f"joint {joint['name']}: missing body actor, skipped")
            continue
        constraint_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.PhysicsConstraintActor, to_ue_location(joint["frame_pos"])
        )
        constraint_actor.set_actor_label(f"LizardJoint_{joint['name']}")
        constraint_actor.set_actor_rotation(
            quat_to_ue_rotator(*rpy_to_quat(joint["frame_rpy"])), False
        )
        comp = constraint_actor.constraint_comp
        comp.set_constrained_components(
            parent_actor.static_mesh_component, unreal.Name(),
            child_actor.static_mesh_component, unreal.Name(),
        )
        # CONSTRAINT (version-sensitive): lock everything, then free the joint axis.
        # Verify in details panel: revolute = all locked except one angular DOF.
        if joint["type"] == "fixed":
            comp.set_linear_limit(unreal.Vector(0, 0, 0), 0.0)
        else:
            limits = joint.get("limits") or {}
            swing_deg = 0.0
            twist_lo = math.degrees(limits.get("lower", 0.0))
            twist_hi = math.degrees(limits.get("upper", 0.0))
            comp.set_angular_swing_limit(unreal.Vector(swing_deg, swing_deg, 0.0), 0.0)
            comp.set_angular_twist_limit(unreal.Vector(twist_lo, twist_hi, 0.0), 0.0)
            unreal.log(
                f"joint {joint['name']}: axis_world={joint['axis_world']} "
                f"limits=[{twist_lo:.1f}, {twist_hi:.1f}] deg, "
                f"kp={joint.get('stiffness')}, kd={joint.get('damping')}"
            )


def print_joint_table(data):
    unreal.log("=== lizard joint table (verify drives manually) ===")
    for joint in data["joints"]:
        if joint["type"] != "revolute":
            continue
        unreal.log(
            f"{joint['name']}: pos={joint['frame_pos']} axis={joint['axis_world']} "
            f"default={joint.get('default_angle', 0.0):.3f} rad"
        )
    control = data["control"]
    unreal.log(
        f"policy {control['policy_hz']} Hz, decimation {control['decimation']}, "
        f"action_scale {control['action_scale']}"
    )


def main():
    data = load_data()
    link_actors = spawn_link_bodies(data)
    spawn_joint_constraints(data, link_actors)
    print_joint_table(data)
    unreal.log(f"Spawned {len(link_actors)} bodies. Check constraints before playing.")


main()
