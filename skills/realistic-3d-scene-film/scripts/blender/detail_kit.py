# detail_kit.py —— 给程序化场景"加细节"和"查细节"的通用工具（Blender 4.2+ / 5.x，Cycles）
#
# 两种用法：
#   1) 在你的建场景脚本里 import / exec 后调用函数：
#        import sys; sys.path.append(<本文件所在目录>); from detail_kit import *
#        t = facade_tower("tower_03", cx, cy, 0, 38, 30, 160, seed=3)   # 带真实竖梃、楼板、屋顶设备的楼
#        bevel_all()                                                     # 全场景硬边倒角
#   2) 对任何一个已存好的 .blend 跑检查（不改原文件）：
#        blender -b scene.blend -P detail_kit.py -- clay  out_clay.png  [samples] [res%]
#        blender -b scene.blend -P detail_kit.py -- mask  out_mask.png  [res%]
#        blender -b --factory-startup -P detail_kit.py -- demo out_demo.png   # 冒烟测试：灰盒楼 vs 细节楼
#      clay = 去掉雾 / 体积、所有材质换成浅灰漫反射，保留天空光。灰模看起来像积木，加雾也救不回来。
#      mask = 实体几何为白、天空 / 雾 / 水（按名字排除）为黑，喂给 qa_detail.py --mask，只在"有东西的地方"量细节。
#
# 设计原则：能用真几何就别用贴图假装；能复用（实例）就别复制网格；所有随机都带 seed。
import bpy, math, random, sys
from mathutils import Vector

# ----------------------------------------------------------------------------- 基础
def _link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


class MeshBuilder:
    """把很多盒子 / 柱子攒进一个网格（每个零件可指定材质槽），比几百个对象快得多。"""
    def __init__(self):
        self.v, self.f, self.mi = [], [], []

    def box(self, x0, x1, y0, y1, z0, z1, mat=0):
        b = len(self.v)
        self.v += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.f.append(tuple(b + i for i in q)); self.mi.append(mat)

    def cyl(self, cx, cy, z0, z1, r, n=12, mat=0, cap=True):
        b = len(self.v)
        for z in (z0, z1):
            for i in range(n):
                a = 2 * math.pi * i / n
                self.v.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
        for i in range(n):
            j = (i + 1) % n
            self.f.append((b + i, b + j, b + n + j, b + n + i)); self.mi.append(mat)
        if cap:
            self.f.append(tuple(b + n + i for i in range(n))); self.mi.append(mat)
            self.f.append(tuple(b + i for i in reversed(range(n)))); self.mi.append(mat)

    def build(self, name, mats, coll=None, smooth=False):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", self.mi)
        if smooth:
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        me.update()
        return _link(bpy.data.objects.new(name, me), coll)


# ----------------------------------------------------------------------------- 材质（够用的写实默认值）
def _principled(name, color, rough=0.5, metal=0.0, **kw):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True  # 6.0 起默认开启，这里只为兼容 4.x
    except Exception:
        pass
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    for k, v in kw.items():
        if k in p.inputs:
            p.inputs[k].default_value = v
    return m, p


def mat_curtain_glass(name="kit_glass", tint=(0.05, 0.07, 0.08), cell=(1.6, 3.8)):
    """幕墙玻璃：低粗糙金属感 + 每块玻璃随机明暗 / 粗糙度（世界坐标格子），远看才不是一整块镜子。"""
    m, p = _principled(name, tint, rough=0.06, metal=0.6)
    nt = m.node_tree; N = nt.nodes; L = nt.links
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Position"], sep.inputs[0])
    # 横向坐标取 x+y（轴对齐楼的两组立面都能用），竖向取 z
    add = N.new("ShaderNodeMath"); add.operation = "ADD"
    L.new(sep.outputs[0], add.inputs[0]); L.new(sep.outputs[1], add.inputs[1])
    cmb = N.new("ShaderNodeCombineXYZ")
    dx = N.new("ShaderNodeMath"); dx.operation = "DIVIDE"; dx.inputs[1].default_value = cell[0]
    dz = N.new("ShaderNodeMath"); dz.operation = "DIVIDE"; dz.inputs[1].default_value = cell[1]
    L.new(add.outputs[0], dx.inputs[0]); L.new(sep.outputs[2], dz.inputs[0])
    fx = N.new("ShaderNodeMath"); fx.operation = "FLOOR"; L.new(dx.outputs[0], fx.inputs[0])
    fz = N.new("ShaderNodeMath"); fz.operation = "FLOOR"; L.new(dz.outputs[0], fz.inputs[0])
    L.new(fx.outputs[0], cmb.inputs[0]); L.new(fz.outputs[0], cmb.inputs[1])
    wn = N.new("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "3D"; L.new(cmb.outputs[0], wn.inputs["Vector"])
    ramp = N.new("ShaderNodeMapRange"); ramp.inputs["To Min"].default_value = 0.03; ramp.inputs["To Max"].default_value = 0.22
    L.new(wn.outputs["Value"], ramp.inputs["Value"]); L.new(ramp.outputs[0], p.inputs["Roughness"])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs[6].default_value = (*tint, 1); mix.inputs[7].default_value = (tint[0] * 2.2, tint[1] * 2.2, tint[2] * 2.0, 1)
    L.new(wn.outputs["Value"], mix.inputs[0]); L.new(mix.outputs[2], p.inputs["Base Color"])
    return m


def mat_weathered(name="kit_concrete", color=(0.42, 0.40, 0.37), dirt=(0.16, 0.15, 0.14), rough=0.8):
    """风化外墙：噪声色差 + 凹处 / 底部积灰（AO）+ 微凹凸。任何石材、混凝土、涂料墙都能当起点。"""
    m, p = _principled(name, color, rough=rough)
    nt = m.node_tree; N = nt.nodes; L = nt.links
    noi = N.new("ShaderNodeTexNoise"); noi.inputs["Scale"].default_value = 0.35; noi.inputs["Detail"].default_value = 8
    ao = N.new("ShaderNodeAmbientOcclusion"); ao.inputs["Distance"].default_value = 1.5; ao.samples = 8
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    L.new(noi.outputs["Fac"], mul.inputs[0]); L.new(ao.outputs["AO"], mul.inputs[1])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs[6].default_value = (*dirt, 1); mix.inputs[7].default_value = (*color, 1)
    L.new(mul.outputs[0], mix.inputs[0]); L.new(mix.outputs[2], p.inputs["Base Color"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25; bump.inputs["Distance"].default_value = 0.02
    n2 = N.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 40; n2.inputs["Detail"].default_value = 6
    L.new(n2.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def mat_pbr_folder(name, folder, scale=1.0):
    """读一个 PBR 贴图文件夹（Poly Haven / ambientCG 下载的 *_diff_*, *_rough_*, *_nor_gl_* 或 *Color*, *Roughness*, *NormalGL*），
    世界坐标 Box 投影，不需要 UV。贴图用 scripts/tools/fetch_polyhaven.py 下载。"""
    import os, glob
    m, p = _principled(name, (0.5, 0.5, 0.5))
    nt = m.node_tree; N = nt.nodes; L = nt.links
    tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])

    def find(*keys):
        for f in sorted(glob.glob(os.path.join(folder, "*"))):
            low = os.path.basename(f).lower()
            if any(k in low for k in keys):
                return f

    def tex(path, noncolor):
        t = N.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(path, check_existing=True)
        t.projection = "BOX"; t.projection_blend = 0.25
        if noncolor:
            t.image.colorspace_settings.name = "Non-Color"
        L.new(mp.outputs[0], t.inputs["Vector"])
        return t

    f = find("diff", "color", "albedo", "basecolor")
    if f: L.new(tex(f, False).outputs["Color"], p.inputs["Base Color"])
    f = find("rough")
    if f: L.new(tex(f, True).outputs["Color"], p.inputs["Roughness"])
    f = find("nor_gl", "normalgl", "_nor_", "normal")
    if f:
        nm = N.new("ShaderNodeNormalMap"); L.new(tex(f, True).outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], p.inputs["Normal"])
    return m


# ----------------------------------------------------------------------------- 几何：楼、屋顶、倒角、实例
def facade_tower(name, cx, cy, z0, sx, sy, h, floor_h=3.8, bay=1.6, fin_depth=0.35, fin_w=0.16,
                 band_h=0.85, setbacks=1, crown=True, clutter=True, seed=0, mats=None, coll=None):
    """一栋带真实立面结构的塔楼：内凹玻璃芯 + 竖向铝竖梃 + 每层楼板带 + 退台 + 顶冠 + 屋顶设备。
    sx, sy 是平面尺寸（米），h 是总高。默认参数接近常见写字楼（层高 3.8 m，分格 1.6 m）。
    mats = (玻璃, 竖梃 / 楼板, 屋顶设备)；不给就用 kit 默认材质。返回对象。
    远景楼（屏幕上 < 80 px 高）用不着这个，见 SKILL.md 的细节预算。"""
    rnd = random.Random(seed)
    if mats is None:
        mats = (mat_curtain_glass(), _principled("kit_frame", (0.55, 0.56, 0.57), rough=0.35, metal=0.8)[0],
                mat_weathered("kit_roof", (0.35, 0.35, 0.34)))
    mb = MeshBuilder()
    segs = []  # (z_start, z_end, half_x, half_y)
    tiers = setbacks + 1
    z = z0
    for t in range(tiers):
        frac = 1.0 - 0.13 * t
        hz = h * (0.62 if tiers > 1 and t == 0 else (1.0 / tiers if tiers > 1 else 1.0))
        if t == tiers - 1:
            hz = z0 + h - z
        segs.append((z, z + hz, sx / 2 * frac, sy / 2 * frac))
        z += hz
    for (za, zb, hx, hy) in segs:
        r = fin_depth
        # 玻璃芯（内凹 fin_depth）
        mb.box(cx - hx + r, cx + hx - r, cy - hy + r, cy + hy - r, za, zb, 0)
        # 楼板带：每层一圈，外凸到立面
        nf = max(1, int((zb - za) / floor_h))
        for k in range(nf + 1):
            zz = za + k * (zb - za) / nf
            mb.box(cx - hx, cx + hx, cy - hy, cy + hy, zz - band_h / 2 if k else zz, zz + band_h / 2, 1)
        # 竖梃：四个面
        for side in range(4):
            if side < 2:
                L = 2 * hx; n = max(2, int(L / bay))
                yy0, yy1 = (cy - hy, cy - hy + r) if side == 0 else (cy + hy - r, cy + hy)
                for i in range(n + 1):
                    xx = cx - hx + i * L / n
                    mb.box(xx - fin_w / 2, xx + fin_w / 2, yy0, yy1, za, zb, 1)
            else:
                L = 2 * hy; n = max(2, int(L / bay))
                xx0, xx1 = (cx - hx, cx - hx + r) if side == 2 else (cx + hx - r, cx + hx)
                for i in range(n + 1):
                    yy = cy - hy + i * L / n
                    mb.box(xx0, xx1, yy - fin_w / 2, yy + fin_w / 2, za, zb, 1)
    za, zb, hx, hy = segs[-1]
    top = zb
    if crown:
        ch = rnd.uniform(3, 7)
        mb.box(cx - hx, cx + hx, cy - hy, cy + hy, top, top + 0.4, 1)        # 屋面板
        for (x0, x1, y0, y1) in ((cx - hx, cx + hx, cy - hy, cy - hy + 0.3), (cx - hx, cx + hx, cy + hy - 0.3, cy + hy),
                                 (cx - hx, cx - hx + 0.3, cy - hy, cy + hy), (cx + hx - 0.3, cx + hx, cy - hy, cy + hy)):
            mb.box(x0, x1, y0, y1, top, top + 1.2, 1)                          # 女儿墙
        # 设备层幕墙框（顶冠）
        cw = 0.55
        mb.box(cx - hx * cw, cx + hx * cw, cy - hy * cw, cy + hy * cw, top, top + ch, 0)
        top_cl = top + 0.4
    else:
        top_cl = top
    if clutter:
        rooftop_clutter(mb, cx - hx + 1.5, cx + hx - 1.5, cy - hy + 1.5, cy + hy - 1.5, top_cl,
                        n=int(hx * hy / 25) + 4, seed=seed, mat=2)
    return mb.build(name, list(mats), coll)


def rooftop_clutter(mb, x0, x1, y0, y1, z, n=10, seed=0, mat=2):
    """屋顶杂物：空调外机、冷却塔、水箱、管道、天线。远看是"有人用的楼顶"，是城市照片感的大头。"""
    rnd = random.Random(seed * 7 + 1)
    for _ in range(n):
        k = rnd.random(); x = rnd.uniform(x0, x1); y = rnd.uniform(y0, y1)
        if k < 0.45:      # 空调 / 机组
            w, d, hh = rnd.uniform(1.2, 4), rnd.uniform(1, 3), rnd.uniform(0.8, 2.2)
            mb.box(x - w / 2, x + w / 2, y - d / 2, y + d / 2, z, z + hh, mat)
        elif k < 0.70:    # 冷却塔 / 水箱
            r = rnd.uniform(0.8, 2.2); mb.cyl(x, y, z, z + rnd.uniform(1.5, 4), r, 14, mat)
        elif k < 0.85:    # 管道（贴地横管）
            L = rnd.uniform(3, 9)
            if rnd.random() < 0.5:
                mb.box(x - L / 2, x + L / 2, y - 0.15, y + 0.15, z + 0.3, z + 0.6, mat)
            else:
                mb.box(x - 0.15, x + 0.15, y - L / 2, y + L / 2, z + 0.3, z + 0.6, mat)
        else:             # 天线 / 避雷针
            mb.cyl(x, y, z, z + rnd.uniform(3, 12), 0.06, 6, mat)


def bevel(obj, width=0.03, segments=2, angle_deg=35):
    """硬边是 CG 感第一来源：真实世界没有零宽的棱。逆光时倒角会接到一条亮边。"""
    if obj.type != "MESH" or any(m.type == "BEVEL" for m in obj.modifiers):
        return
    m = obj.modifiers.new("kit_bevel", "BEVEL")
    m.width = width; m.segments = segments
    m.limit_method = "ANGLE"; m.angle_limit = math.radians(angle_deg)
    try:
        m.harden_normals = True
    except Exception:
        pass


def bevel_all(width=0.03, segments=2, skip=("water", "fog", "sky", "ground", "terrain", "leaf", "volume")):
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and not _name_hit(o.name, skip):
            bevel(o, width, segments)


def instance(src, placements, coll=None, prefix=None):
    """链接复制（共享网格数据）：几千棵树 / 几百栋楼也不爆内存。placements = [(loc, rot_z, scale), ...]"""
    out = []
    for i, (loc, rz, s) in enumerate(placements):
        o = src.copy()  # 不 copy data → 共享网格
        o.name = f"{prefix or src.name}_i{i:04d}"
        o.location = loc; o.rotation_euler = (0, 0, rz); o.scale = (s, s, s)
        _link(o, coll); out.append(o)
    return out


# ----------------------------------------------------------------------------- 检查：clay / mask
VOLUME_HINTS = ("fog", "mist", "haze", "volume", "atmo", "cloud")


def _tokens(name):
    import re
    return set(t for t in re.split(r"[^a-z]+", name.lower()) if t)


def _name_hit(name, words):
    """按单词匹配（skyline_03 不会被 "sky" 命中）。"""
    return bool(_tokens(name) & set(words))


def _is_volume_obj(o):
    if _name_hit(o.name, VOLUME_HINTS):
        return True
    for slot in getattr(o, "material_slots", []):
        m = slot.material
        if m and m.node_tree:
            out = next((n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL"), None)
            if out and out.inputs["Volume"].is_linked and not out.inputs["Surface"].is_linked:
                return True
    return False


def _kill_world_volume(scene):
    w = scene.world
    if w and w.node_tree:
        for n in w.node_tree.nodes:
            if n.type == "OUTPUT_WORLD" and n.inputs["Volume"].is_linked:
                for l in list(n.inputs["Volume"].links):
                    w.node_tree.links.remove(l)


def setup_clay(scene=None, grey=0.55):
    scene = scene or bpy.context.scene
    for o in scene.objects:
        if _is_volume_obj(o):
            o.hide_render = True
    _kill_world_volume(scene)
    m, p = _principled("kit_clay", (grey, grey, grey), rough=0.65)
    bpy.context.view_layer.material_override = m


def setup_mask(scene=None, exclude=("water", "river", "lake", "sea", "ocean", "sky", "sun_disc", "sundisc")):
    """白 = 实体几何，黑 = 天空 / 雾 / 水 / 名字命中 exclude 的东西。"""
    scene = scene or bpy.context.scene
    for o in scene.objects:
        if _is_volume_obj(o) or _name_hit(o.name, exclude):
            o.hide_render = True
    w = bpy.data.worlds.new("kit_black"); w.color = (0, 0, 0)
    try:
        w.use_nodes = True
    except Exception:
        pass
    if w.node_tree:
        bg = w.node_tree.nodes.get("Background")
        if bg:
            bg.inputs["Color"].default_value = (0, 0, 0, 1); bg.inputs["Strength"].default_value = 0.0
    scene.world = w
    m = bpy.data.materials.new("kit_white")
    try:
        m.use_nodes = True
    except Exception:
        pass
    N = m.node_tree.nodes; L = m.node_tree.links
    for n in list(N):
        if n.type == "BSDF_PRINCIPLED":
            N.remove(n)
    e = N.new("ShaderNodeEmission"); e.inputs["Strength"].default_value = 1.0
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    L.new(e.outputs[0], out.inputs["Surface"])
    bpy.context.view_layer.material_override = m
    scene.cycles.samples = 4
    scene.cycles.use_denoising = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0


def _render(path, samples=None, res=None):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    if samples:
        sc.cycles.samples = int(samples)
    if res:
        sc.render.resolution_percentage = int(res)
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("KIT_RENDERED", path)


def _demo(path):
    """冒烟测试：左边灰盒楼（现状），右边 facade_tower（同尺寸），斜阳 + 天空。"""
    sc = bpy.context.scene
    for o in list(sc.objects):
        bpy.data.objects.remove(o)
    w = bpy.data.worlds.new("w"); sc.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1); bg.inputs["Strength"].default_value = 0.6
    ground = MeshBuilder(); ground.box(-200, 200, -200, 200, -1, 0)
    ground.build("ground", [mat_weathered("kit_ground", (0.3, 0.3, 0.3))])
    plain = MeshBuilder(); plain.box(-55, -17, -15, 15, 0, 160)
    plain.build("greybox", [_principled("plain", (0.45, 0.45, 0.45), rough=0.5)[0]])
    t = facade_tower("detailed", 36, 0, 0, 38, 30, 160, setbacks=1, seed=3)
    bevel_all(0.04)
    sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 4; sun.angle = math.radians(1.0)
    so = _link(bpy.data.objects.new("sun", sun)); so.rotation_euler = (math.radians(62), 0, math.radians(-35))
    cam = bpy.data.cameras.new("cam"); cam.lens = 50
    co = _link(bpy.data.objects.new("cam", cam)); sc.camera = co
    co.location = (-10, -430, 95)
    d = Vector((-5, 0, 80)) - co.location; co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.view_settings.view_transform = "AgX"
    _render(path, 48, 100)


if __name__ == "__main__" and "--" in sys.argv:
    a = sys.argv[sys.argv.index("--") + 1:]
    if a:
        cmd, out = a[0], a[1]
        if cmd == "clay":
            setup_clay(); _render(out, a[2] if len(a) > 2 else 32, a[3] if len(a) > 3 else 50)
        elif cmd == "mask":
            setup_mask(); _render(out, None, a[2] if len(a) > 2 else 50)
        elif cmd == "demo":
            _demo(out)
        else:
            print("usage: -- clay|mask|demo <out.png> ...")
