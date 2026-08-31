# -*- coding: utf-8 -*-
"""Convert the pipeline's binary STL meshes to OBJ and rewrite lizard.urdf.

The Isaac Lab 3.0 URDF importer silently drops binary STL meshes (empty
geometry xforms, robot falls through the floor). The old pipeline used OBJ
successfully, so we convert. Usage: python convert_stl_to_obj.py
"""

import pathlib
import re
import struct
import sys

EXP_DIR = pathlib.Path(__file__).resolve().parent
MESH_DIR = EXP_DIR / "meshes"
URDF_PATH = EXP_DIR / "lizard.urdf"


def parse_stl(path):
    tris = []
    with open(path, "rb") as fh:
        fh.read(80)
        (count,) = struct.unpack("<I", fh.read(4))
        for _ in range(count):
            data = struct.unpack("<12fH", fh.read(50))
            tris.append((data[3:6], data[6:9], data[9:12]))
    return tris


def write_obj(tris, path):
    verts = []
    lookup = {}
    faces = []
    for tri in tris:
        face = []
        for vert in tri:
            key = (round(vert[0], 6), round(vert[1], 6), round(vert[2], 6))
            if key not in lookup:
                lookup[key] = len(verts) + 1
                verts.append(key)
            face.append(lookup[key])
        faces.append(face)
    with open(path, "w") as fh:
        fh.write("# lizard mesh\n")
        for vx, vy, vz in verts:
            fh.write("v %.6f %.6f %.6f\n" % (vx, vy, vz))
        for face in faces:
            fh.write("f %d %d %d\n" % tuple(face))


def main():
    stl_files = sorted(MESH_DIR.rglob("*.stl"))
    for stl_path in stl_files:
        obj_path = stl_path.with_suffix(".obj")
        write_obj(parse_stl(stl_path), obj_path)
        print("CONVERTED %s -> %s" % (stl_path.name, obj_path.name))

    src = URDF_PATH.read_text(encoding="utf-8")
    fixed = re.sub(r"\.stl", ".obj", src)
    if fixed != src:
        URDF_PATH.write_text(fixed, encoding="utf-8")
        print("URDF_REWRITTEN %s" % URDF_PATH)
    else:
        print("URDF_UNCHANGED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
