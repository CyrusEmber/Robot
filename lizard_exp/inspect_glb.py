# -*- coding: utf-8 -*-
"""Dump lizard.glb loose-part bounding boxes (headless Blender)."""
import collections

import bpy
import bmesh
from mathutils import Vector

bpy.ops.import_scene.gltf(filepath=r'E:\IsaacLab\model\lizard.glb')
o = bpy.data.objects['node_0']
me = o.data
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()

edges = collections.defaultdict(list)
for e in bm.edges:
	a, b = e.verts[0].index, e.verts[1].index
	edges[a].append(b)
	edges[b].append(a)

seen = bytearray(len(bm.verts))
parts = []
for v in range(len(bm.verts)):
	if seen[v]:
		continue
	comp = []
	stack = [v]
	seen[v] = 1
	while stack:
		cur = stack.pop()
		comp.append(cur)
		for nb in edges[cur]:
			if not seen[nb]:
				seen[nb] = 1
				stack.append(nb)
	parts.append(comp)

print('VERTS', len(bm.verts), 'FACES', len(bm.faces), 'PARTS', len(parts))
mw = o.matrix_world
for i, comp in enumerate(sorted(parts, key=len, reverse=True)[:25]):
	cos = [mw @ bm.verts[j].co for j in comp]
	mn = Vector((min(c.x for c in cos), min(c.y for c in cos), min(c.z for c in cos)))
	mx = Vector((max(c.x for c in cos), max(c.y for c in cos), max(c.z for c in cos)))
	print('PART %d verts=%d min=(%.3f,%.3f,%.3f) max=(%.3f,%.3f,%.3f)' % (
		i, len(comp), mn.x, mn.y, mn.z, mx.x, mx.y, mx.z))
bm.free()
