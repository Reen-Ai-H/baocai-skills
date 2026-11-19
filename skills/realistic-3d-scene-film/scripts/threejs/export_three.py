# 把 Blender 里的西湖纪录片场景导出给 three.js
# 用法: blender -b --factory-startup -P three/export_three.py
#  -> three/public/scene.glb      几何（Y-up，修改器已应用，柳条风摆在 three.js 里做）
#     three/public/scene.json     材质参数 / 相机 / 灯光 / 镜头表 / 动画索引
#     three/public/anim.bin       动画对象逐帧世界矩阵 (float32, 3x4, Y-up)
import bpy, sys, os, json, math, struct
from mathutils import Matrix, Vector

T_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(T_DIR)
PUB = os.path.join(T_DIR, "public")
os.makedirs(PUB, exist_ok=True)

# 以纪录片模式构建场景（OUT 为空 => 不渲染）
sys.argv = [sys.argv[0], "--", "", "1", "100", "doc", "S2"]
__file__ = os.path.join(ROOT, "build_westlake.py")
exec(compile(open(__file__, encoding="utf-8").read(), __file__, "exec"))

scene = bpy.context.scene
C = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))   # Blender Z-up -> glTF Y-up
Ci = C.inverted()

# ---------------------------------------------------------------- 清理 three.js 里另做的东西
DROP_PREFIX = ("Atmosphere", "ripple_", "fish_brush", "Wind")
for ob in list(scene.objects):
    if ob.name.startswith(DROP_PREFIX) or ob.name.endswith("_wakebrush"):
        bpy.data.objects.remove(ob, do_unlink=True)
for ob in scene.objects:
    for md in list(ob.modifiers):
        if md.type in ("DISPLACE", "DYNAMIC_PAINT"):
            ob.modifiers.remove(md)

# ---------------------------------------------------------------- 动画：逐帧世界矩阵 + 可见性
def has_anim(o):
    while o is not None:
        ad = o.animation_data
        if ad and (ad.action or len(ad.drivers)):
            return True
        o = o.parent
    return False

def hidden(o):
    while o is not None:
        if o.hide_render:
            return True
        o = o.parent
    return False

F0, F1 = 1, 960
cands = [o for o in scene.objects if o.type in ("MESH", "EMPTY", "CAMERA", "LIGHT") and has_anim(o)]
print("anim candidates", len(cands))
mats = {o.name: [] for o in cands}
cam_track = {o.name: [] for o in scene.objects if o.type == "CAMERA"}
hide_track = {o.name: [] for o in scene.objects if o.type in ("MESH", "LIGHT")}
for fr in range(F0, F1 + 1):
    scene.frame_set(fr)
    for o in cands:
        M = (C @ o.matrix_world) if o.type == "CAMERA" else (C @ o.matrix_world @ Ci)
        mats[o.name].append([M[r][c] for r in range(3) for c in range(4)])
    for name in cam_track:
        cd = scene.objects[name].data
        cam_track[name].append([cd.lens, cd.dof.focus_distance, cd.dof.aperture_fstop])
    for name in hide_track:
        hide_track[name].append(1 if hidden(scene.objects[name]) else 0)
    if fr % 120 == 0:
        print("sampled", fr)

anim_names, blob = [], bytearray()
for name, rows in mats.items():
    if all(max(abs(a - b) for a, b in zip(r, rows[0])) < 1e-6 for r in rows):
        continue
    anim_names.append(name)
    for r in rows:
        blob += struct.pack("12f", *r)
open(os.path.join(PUB, "anim.bin"), "wb").write(bytes(blob))
vis = {}
for name, seq in hide_track.items():
    if min(seq) != max(seq):                     # 只记录会切换可见性的对象: [[起, 止], ...] 可见区间
        spans, start = [], None
        for i, h in enumerate(seq):
            if not h and start is None:
                start = i + F0
            if h and start is not None:
                spans.append([start, i + F0 - 1]); start = None
        if start is not None:
            spans.append([start, F1])
        vis[name] = spans
always_hidden = [n for n, s in hide_track.items() if min(s) == 1]
print("animated", len(anim_names), "vis-switching", len(vis), "always hidden", len(always_hidden))

# ---------------------------------------------------------------- 材质参数
def inp(p, name, default=None):
    try:
        v = p.inputs[name].default_value
        return list(v) if hasattr(v, "__len__") else float(v)
    except Exception:
        return default

materials = {}
for m in bpy.data.materials:
    if not m.use_nodes:
        continue
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    d = {}
    if p is not None:
        d.update(color=inp(p, "Base Color")[:3], rough=inp(p, "Roughness"), metal=inp(p, "Metallic"),
                 emit=inp(p, "Emission Color")[:3], emitStrength=inp(p, "Emission Strength"),
                 trans=inp(p, "Transmission Weight"), sss=inp(p, "Subsurface Weight"),
                 sheen=inp(p, "Sheen Weight"), coat=inp(p, "Coat Weight"), spec=inp(p, "Specular IOR Level"))
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeBsdfTranslucent":
            d["translucent"] = list(n.inputs["Color"].default_value)[:3]
        if n.bl_idname == "ShaderNodeMixShader" and "translucent" in d and "mix" not in d:
            d["mix"] = n.inputs["Fac"].default_value
        if n.bl_idname == "ShaderNodeHueSaturation":
            d["color"] = list(n.inputs["Color"].default_value)[:3]
        if n.bl_idname == "ShaderNodeValToRGB" and m.name in ("stone", "land", "hill", "hull"):
            el = n.color_ramp.elements
            d["noise"] = [list(el[0].color)[:3], list(el[1].color)[:3]]
        if n.bl_idname == "ShaderNodeTexNoise" and m.name in ("stone", "land", "hill", "hull"):
            d["noiseScale"] = n.inputs["Scale"].default_value
    materials[m.name] = d

# ---------------------------------------------------------------- 灯光 / 天空 / 相机
lights = []
for o in scene.objects:
    if o.type != "LIGHT":
        continue
    ld = o.data
    M = C @ o.matrix_world
    fwd = (M.to_3x3() @ Vector((0, 0, -1))).normalized()
    lights.append(dict(name=o.name, type=ld.type, color=list(ld.color), energy=ld.energy,
                       pos=list(M.translation), dir=list(fwd),
                       size=getattr(ld, "size", 0.0), angle=getattr(ld, "angle", 0.0)))
cams = {}
for o in scene.objects:
    if o.type == "CAMERA":
        cams[o.name] = dict(sensor=o.data.sensor_width, track=cam_track[o.name],
                            anim=o.name in anim_names, static=[(C @ o.matrix_world)[r][c] for r in range(3) for c in range(4)])
info = dict(
    frames=[F0, F1], fps=24, shots=SHOTS, cams={k: "cam_" + k for k in SHOTS},
    sun=dict(elev=SUN_ELEV, az=SUN_AZ, dir=list(C @ sun_vec)), materials=materials, lights=lights, cameras=cams,
    anim=anim_names, vis=vis, alwaysHidden=always_hidden,
    exposure=scene.view_settings.exposure,
)
json.dump(info, open(os.path.join(PUB, "scene.json"), "w", encoding="utf-8"))

# ---------------------------------------------------------------- 几何
scene.frame_set(SHOTS["S2"][0])
bpy.ops.object.select_all(action="DESELECT")
for o in scene.objects:
    if o.type in ("MESH", "EMPTY"):
        o.hide_render = False
        o.hide_set(False)
        o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(PUB, "scene.glb"), export_format="GLB", use_selection=True,
                          export_apply=True, export_yup=True, export_cameras=False, export_lights=False,
                          export_animations=False, export_materials="EXPORT", export_normals=True,
                          export_texcoords=True, export_extras=False)
nv = sum(len(o.data.vertices) for o in scene.objects if o.type == "MESH")
print("EXPORT_OK meshes", sum(1 for o in scene.objects if o.type == "MESH"), "verts", nv)
