# -*- coding: utf-8 -*-
"""Dump lizard.blend armature + object hierarchy (headless Blender)."""
import bpy

bpy.ops.wm.open_mainfile(filepath=r'E:\IsaacLab\model\lizard.blend')

print('===OBJECTS===')
for o in bpy.data.objects:
	extra = ''
	if o.type == 'MESH':
		extra = 'verts=%d' % len(o.data.vertices)
	print('%s | %s | parent=%s | %s' % (
		o.name, o.type, o.parent.name if o.parent else None, extra))

print('===ARMATURES===')
for a in bpy.data.objects:
	if a.type != 'ARMATURE':
		continue
	print('ARMATURE', a.name, 'bones=%d' % len(a.data.bones))
	for b in a.data.bones:
		print('BONE %s | parent=%s | head=(%.4f,%.4f,%.4f) | tail=(%.4f,%.4f,%.4f)' % (
			b.name, b.parent.name if b.parent else None,
			b.head_local.x, b.head_local.y, b.head_local.z,
			b.tail_local.x, b.tail_local.y, b.tail_local.z))
