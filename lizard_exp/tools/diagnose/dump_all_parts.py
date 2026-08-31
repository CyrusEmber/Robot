# -*- coding: utf-8 -*-
"""Dump all loose parts of lizard.blend with bbox + sphericity."""
import collections

import bpy
import bmesh
from mathutils import Vector

bpy.ops.wm.open_mainfile(filepath=r'E:\IsaacLab\model\lizard.blend')
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

mw = o.matrix_world
rows = []
for comp in parts:
	cos = [mw @ bm.verts[j].co for j in comp]
	mn = Vector((min(c.x for c in cos), min(c.y for c in cos), min(c.z for c in cos)))
	mx = Vector((max(c.x for c in cos), max(c.y for c in cos), max(c.z for c in cos)))
	size = mx - mn
	ctr = (mx + mn) / 2
	sph = min(size.x, size.y, size.z) / max(size.x, size.y, size.z) if max(size.x, size.y, size.z) > 0 else 0
	rows.append((len(comp), ctr, mn, mx, size, sph))

rows.sort(key=lambda r: (r[1].y, r[1].x))
for i, (nv, ctr, mn, mx, size, sph) in enumerate(rows):
	print('P %03d v=%4d c=(%6.3f,%6.3f,%6.3f) s=(%5.3f,%5.3f,%5.3f) sph=%4.2f' % (
		i, nv, ctr.x, ctr.y, ctr.z, size.x, size.y, size.z, sph))
print('TOTAL_PARTS', len(parts))
bm.free()
