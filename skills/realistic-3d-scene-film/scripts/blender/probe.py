# 环境 / API 名自检：打印天空节点 sky_type 枚举、天空和 Principled / 体积节点的输入名、渲染引擎、可用 GPU
# 用法: blender -b --factory-startup -P probe.py      换机器或换 Blender 版本后先跑一次
import bpy
n=bpy.data.node_groups.new('t','ShaderNodeTree')
s=n.nodes.new('ShaderNodeTexSky')
print('SKY',[e.identifier for e in s.bl_rna.properties['sky_type'].enum_items])
print('SKYPROPS',[p.identifier for p in s.bl_rna.properties])
m=bpy.data.materials.new('m'); m.use_nodes=True
p=m.node_tree.nodes['Principled BSDF']
print('PB',[i.name for i in p.inputs])
v=n.nodes.new('ShaderNodeVolumePrincipled'); print('VOL',[i.name for i in v.inputs])
print('ENG',[e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items])
prefs=bpy.context.preferences.addons['cycles'].preferences
for t in ('OPTIX','CUDA'):
    try:
        prefs.compute_device_type=t; prefs.get_devices(); print('DEV',t,[(d.name,d.type) for d in prefs.devices]); break
    except Exception as e: print('ERR',t,e)
print('VT',[e.identifier for e in bpy.types.View3DShading.bl_rna.properties['type'].enum_items])
print('LOOK',[e.identifier for e in bpy.types.ColorManagedViewSettings.bl_rna.properties['view_transform'].enum_items])
