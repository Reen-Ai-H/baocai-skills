# 西湖·晨  纪录片分镜模块 —— 由 build_westlake.py 在 "doc" 模式下 exec 引入（共享其全局变量）
# 参数: -- <out_dir> <samples> <res%> doc <SHOT> [frame <n>|mid|first|last] [nobake]
import bpy, math, random
from mathutils import Vector, Matrix

FPS = 24
SHOTS = {   # name: (start, end)
    "S1": (1, 96),       # 微距：荷叶上的水珠
    "S2": (97, 240),     # 大全景：湖面推进，白鹭低飞
    "S3": (241, 360),    # 长焦：雷峰塔与山影，鹭群掠过
    "S4": (361, 480),    # 长焦：白鹭伫立逆光，鱼咬水面
    "S5": (481, 600),    # 微距：荷花 -> 红蜻蜓，变焦
    "S6": (601, 720),    # 长焦：野鸭划过日光水道
    "S7": (721, 816),    # 近景：柳丝逆光，变焦到远处
    "S8": (817, 960),    # 收尾大全景：后拉
}
scene.frame_start, scene.frame_end = 1, 960
scene.render.fps = FPS

# ============================================================ helpers
def loft_spine(name, pts, radii, mat, seg=14, wscale=1.0, hscale=1.0, caps=True, subsurf=1):
    pts = [Vector(p) for p in pts]
    verts, faces = [], []
    n = len(pts)
    for i, (c, r) in enumerate(zip(pts, radii)):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        side = t.cross(ref).normalized()
        up = side.cross(t).normalized()
        for k in range(seg):
            a = 2 * math.pi * k / seg
            verts.append(tuple(c + side * math.cos(a) * r * wscale + up * math.sin(a) * r * hscale))
    for i in range(n - 1):
        for k in range(seg):
            a, b = i * seg + k, i * seg + (k + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    if caps:
        verts.append(tuple(pts[0])); c0 = len(verts) - 1
        verts.append(tuple(pts[-1])); c1 = len(verts) - 1
        for k in range(seg):
            faces.append((c0, (k + 1) % seg, k))
            faces.append((c1, (n - 1) * seg + k, (n - 1) * seg + (k + 1) % seg))
    ob = mesh_obj(name, verts, faces, mat, smooth=True)
    if subsurf:
        ob.modifiers.new("ss", "SUBSURF").levels = subsurf
        ob.modifiers["ss"].render_levels = subsurf
    return ob

def parent_all(name, objs, loc=(0, 0, 0), rot=(0, 0, 0)):
    par = bpy.data.objects.new(name, None)
    link(par)
    for o in objs:
        o.parent = par
    par.location = loc
    par.rotation_euler = rot
    return par

def descendants(ob):
    out = []
    for c in ob.children:
        out.append(c)
        out += descendants(c)
    return out

def key_hide(o, f0, f1, visible_inside=True):
    """visible only inside [f0, f1] (or hidden only inside, if visible_inside=False)"""
    o.hide_render = visible_inside
    o.keyframe_insert("hide_render", frame=1)
    o.hide_render = not visible_inside
    o.keyframe_insert("hide_render", frame=f0)
    o.hide_render = visible_inside
    o.keyframe_insert("hide_render", frame=f1 + 1)

def visible_only(par, f0, f1):
    for o in [par] + descendants(par):
        if o.type != "EMPTY":
            key_hide(o, f0, f1, True)

def cone_between(name, a, b, r0, r1, mat, seg=10):
    return loft_spine(name, [a, Vector(a).lerp(Vector(b), 0.5), b], [r0, (r0 + r1) / 2, r1], mat, seg, caps=True,
                      subsurf=0)

def key_seq(ob, path, idx, keys):
    for f, v in keys:
        getattr(ob, path)[idx] = v
        ob.keyframe_insert(path, index=idx, frame=f)

def d3(a, b):
    return (Vector(a) - Vector(b)).length

# ============================================================ materials
M_FEATHER, pf = principled("feather", (0.92, 0.92, 0.89), 0.62, Subsurface_Weight=0.35, Sheen_Weight=0.6,
                           Sheen_Roughness=0.4)
setin(pf, "Subsurface Radius", (0.3, 0.3, 0.25))
setin(pf, "Subsurface Scale", 0.02)
M_PLUME = foliage("plume", (0.9, 0.9, 0.86), (0.95, 0.92, 0.85), 0.5, 0.5)
M_BILL, _ = principled("bill", (0.75, 0.55, 0.08), 0.35)
M_LEG, _ = principled("leg", (0.02, 0.02, 0.02), 0.45)
M_EYE, _ = principled("eye", (0.6, 0.45, 0.05), 0.05)
M_DROP, _ = principled("droplet", (1, 1, 1), 0.0, Transmission_Weight=1.0, IOR=1.333)

def hero_leaf_material():
    m = foliage("lotus_hero", (0.02, 0.16, 0.02), (0.25, 0.65, 0.05), 0.4, 0.5)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    setin(p, "Specular IOR Level", 0.12)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])

    def mnode(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath"); n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                nt.links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]
    ang = mnode("ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
    rad = nt.nodes.new("ShaderNodeVectorMath"); rad.operation = "LENGTH"
    nt.links.new(tc.outputs["Object"], rad.inputs[0])
    r = rad.outputs["Value"]
    vein = mnode("POWER", mnode("SUBTRACT", 1.0, mnode("ABSOLUTE", mnode("SINE", mnode("MULTIPLY", ang, 11.0)))), 14.0)
    vein2 = mnode("POWER", mnode("SUBTRACT", 1.0, mnode("ABSOLUTE", mnode("SINE", mnode("MULTIPLY", ang, 44.0)))), 30.0)
    vfade = mnode("MINIMUM", mnode("MULTIPLY", r, 12.0), 1.0)
    veins = mnode("MULTIPLY", mnode("ADD", vein, mnode("MULTIPLY", vein2, 0.35)), vfade)
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 260; nz.inputs["Detail"].default_value = 2
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    h = mnode("ADD", veins, mnode("MULTIPLY", nz.outputs["Fac"], 0.25))
    b = nt.nodes.new("ShaderNodeBump"); b.inputs["Strength"].default_value = 0.18; b.inputs["Distance"].default_value = 0.0008
    nt.links.new(h, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    hsv = [n for n in nt.nodes if n.bl_idname == "ShaderNodeHueSaturation"][0]
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    navel = mnode("SUBTRACT", 1.0, mnode("MINIMUM", mnode("MULTIPLY", r, 28.0), 1.0))
    tint = mnode("MAXIMUM", navel, mnode("MULTIPLY", veins, 0.35))
    nt.links.new(tint, mix.inputs["Factor"])
    nt.links.new(hsv.outputs["Color"], mix.inputs["A"])
    mix.inputs["B"].default_value = (0.2, 0.32, 0.1, 1)
    nt.links.new(mix.outputs["Result"], p.inputs["Base Color"])
    return m

M_LOTUS_HERO = hero_leaf_material()

def petal_material():
    m = foliage("petal", (0.9, 0.6, 0.7), (1.0, 0.55, 0.65), 0.55, 0.45)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    setin(p, "Subsurface Weight", 0.3)
    setin(p, "Sheen Weight", 0.3)
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.95, 0.93, 0.82, 1)
    els[1].position, els[1].color = 1.0, (0.78, 0.12, 0.32, 1)
    e = els.new(0.45); e.color = (0.97, 0.82, 0.84, 1)
    e = els.new(0.8); e.color = (0.92, 0.45, 0.58, 1)
    nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    tr = [n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfTranslucent"][0]
    nt.links.new(ramp.outputs["Color"], tr.inputs["Color"])
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = 18; wv.inputs["Distortion"].default_value = 1.5
    nt.links.new(uv.outputs["UV"], wv.inputs["Vector"])
    b = nt.nodes.new("ShaderNodeBump"); b.inputs["Strength"].default_value = 0.12
    nt.links.new(wv.outputs["Fac"], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m

M_PETAL = petal_material()
M_POD, _ = principled("seedpod", (0.55, 0.62, 0.15), 0.5, Subsurface_Weight=0.2)
M_STAMEN, _ = principled("stamen", (0.95, 0.72, 0.15), 0.5)

def wing_material():
    m = bpy.data.materials.new("dragonfly_wing")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    setin(p, "Base Color", (0.95, 0.95, 0.95, 1))
    setin(p, "Roughness", 0.04)
    setin(p, "Thin Film Thickness", 420.0)
    setin(p, "Thin Film IOR", 1.5)
    uv = nt.nodes.new("ShaderNodeUVMap")
    vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 22
    mp = nt.nodes.new("ShaderNodeMapping"); setin(mp, "Scale", (1.0, 3.5, 1.0))
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], vor.inputs["Vector"])
    vein = nt.nodes.new("ShaderNodeMapRange")
    vein.inputs["From Min"].default_value = 0.0; vein.inputs["From Max"].default_value = 0.06
    vein.inputs["To Min"].default_value = 1.0; vein.inputs["To Max"].default_value = 0.0
    nt.links.new(vor.outputs["Distance"], vein.inputs["Value"])
    veinbsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    setin(veinbsdf, "Base Color", (0.08, 0.05, 0.03, 1)); setin(veinbsdf, "Roughness", 0.4)
    tp = nt.nodes.new("ShaderNodeBsdfTransparent")
    glass = nt.nodes.new("ShaderNodeMixShader"); glass.inputs["Fac"].default_value = 0.22
    nt.links.new(tp.outputs[0], glass.inputs[1]); nt.links.new(p.outputs[0], glass.inputs[2])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(vein.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(glass.outputs[0], mix.inputs[1])
    nt.links.new(veinbsdf.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m

M_WING = wing_material()
M_DF_BODY, _ = principled("df_body", (0.55, 0.05, 0.02), 0.35, Coat_Weight=0.6)
M_DF_THORAX, _ = principled("df_thorax", (0.25, 0.08, 0.04), 0.4, Coat_Weight=0.5)
M_DF_EYE, _ = principled("df_eye", (0.35, 0.08, 0.05), 0.15, Coat_Weight=1.0)

def duck_material(name, male):
    m, p = principled(name, (0.4, 0.4, 0.4), 0.7, Sheen_Weight=0.15)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    if male:
        stops = [(0.0, (0.02, 0.02, 0.02)), (0.12, (0.85, 0.85, 0.82)), (0.2, (0.42, 0.42, 0.40)),
                 (0.6, (0.45, 0.44, 0.42)), (0.66, (0.22, 0.08, 0.04)), (0.78, (0.25, 0.09, 0.05)),
                 (0.8, (0.9, 0.9, 0.9)), (0.83, (0.02, 0.18, 0.06)), (1.0, (0.01, 0.12, 0.05))]
    else:
        stops = [(0.0, (0.15, 0.10, 0.06)), (0.5, (0.33, 0.22, 0.12)), (0.82, (0.30, 0.20, 0.11)),
                 (0.85, (0.20, 0.13, 0.07)), (1.0, (0.24, 0.16, 0.09))]
    el[0].position, el[0].color = stops[0][0], (*stops[0][1], 1)
    el[1].position, el[1].color = stops[-1][0], (*stops[-1][1], 1)
    for pos, c in stops[1:-1]:
        e = el.new(pos); e.color = (*c, 1)
    ramp.color_ramp.interpolation = "EASE"
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.28; mr.inputs["From Max"].default_value = 0.30
    nt.links.new(sep.outputs["X"], mr.inputs["Value"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 90
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath"); add.operation = "MULTIPLY_ADD"
    nt.links.new(nz.outputs["Fac"], add.inputs[0]); add.inputs[1].default_value = 0.03
    nt.links.new(mr.outputs["Result"], add.inputs[2])
    nt.links.new(add.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    return m

M_DUCK_M = duck_material("mallard_m", True)
for _m in ():
    pass
M_DUCK_F = duck_material("mallard_f", False)
M_DUCK_BILL, _ = principled("duck_bill", (0.75, 0.6, 0.1), 0.4)
M_DUCK_BILL_F, _ = principled("duck_bill_f", (0.55, 0.32, 0.08), 0.45)

# ============================================================ clear generic lotus where heroes stand
KEEP_OUT = [((3.2, 6.0), 0.75), ((5.0, 8.25), 0.55), ((4.55, 7.4), 0.55), ((3.05, 5.6), 0.45),
            ((8.6, 19.5), 0.9), ((7.7, 19.6), 0.6)]
for ob in list(scene.objects):
    if ob.type != "MESH" or not (ob.name.startswith("lotus_leaf") or ob.name.startswith("Cylinder")):
        continue
    if ob.parent is not None:
        continue
    p2 = Vector((ob.location.x, ob.location.y))
    if any((p2 - Vector(c)).length < r for c, r in KEEP_OUT):
        bpy.data.objects.remove(ob, do_unlink=True)

# ============================================================ hero lotus leaf with water beads (S1)
def hero_leaf(c, R=0.42):
    NR, NA = 30, 120
    rnd = random.Random(4)
    verts = [(0, 0, 0)]
    notch = 2.4
    for i in range(1, NR + 1):
        d = i / NR
        for j in range(NA):
            a = 2 * math.pi * j / NA
            da = (a - notch + math.pi) % (2 * math.pi) - math.pi
            rr = R * d * (1 - 0.12 * math.exp(-(da / 0.12) ** 2) * d)
            wav = 0.012 * R * math.sin(a * 9 + 1.3) * d ** 4 + 0.006 * R * math.sin(a * 23) * d ** 6
            verts.append((rr * math.cos(a), rr * math.sin(a),
                          0.07 * R * d ** 2 + wav - 0.01 * R * math.exp(-(d / 0.08) ** 2)))
    faces = [(0, 1 + j, 1 + (j + 1) % NA) for j in range(NA)]
    for i in range(NR - 1):
        for j in range(NA):
            a = 1 + i * NA + j
            b = 1 + i * NA + (j + 1) % NA
            faces.append((a, a + NA, b + NA, b))
    leaf = mesh_obj("hero_leaf", verts, faces, M_LOTUS_HERO, smooth=True)
    leaf.location = c
    leaf.rotation_euler.z = 0.7
    beads = [(0.0, 0.01, 0.011), (0.035, -0.02, 0.006), (-0.03, 0.04, 0.005)]
    for k in range(70):
        a = rnd.uniform(0, 2 * math.pi)
        d = R * (rnd.random() ** 0.6) * 0.9
        beads.append((d * math.cos(a), d * math.sin(a), rnd.choice((0.0018, 0.0025, 0.0032, 0.004, 0.0055))))
    for bx, by, br in beads:
        d = math.hypot(bx, by) / R
        z = 0.07 * R * d ** 2 + br * 0.72
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=br, location=(bx, by, z))
        o = bpy.context.active_object
        o.scale.z = 0.78
        o.data.shade_smooth()
        o.data.materials.append(M_DROP)
        o.parent = leaf
        o.location = (bx, by, z)
    leaf.driver_add("rotation_euler", 0).driver.expression = "0.012*sin(frame*0.09)"
    leaf.driver_add("rotation_euler", 1).driver.expression = "0.009*sin(frame*0.07+1.0)"
    return leaf

hero_leaf((3.2, 6.0, 0.012))

# ============================================================ lotus flower + bud (S5)
def petal_mesh(name, L, W, cup, curl, mat):
    NU, NV = 9, 14
    verts, faces, uvs = [], [], []
    for j in range(NV):
        v = j / (NV - 1)
        t = (v - 0.6) / (0.6 if v < 0.6 else 0.42)
        w = W * max(0.0, 1 - t * t) ** 0.5 * (1 - 0.15 * max(0, v - 0.9) / 0.1) + 0.004 * (1 - v)
        for i in range(NU):
            u = -1 + 2 * i / (NU - 1)
            x = u * w
            y = (-cup * W * (1 - u * u) * (0.4 + 0.6 * math.sin(math.pi * min(v * 1.1, 1)))
                 - curl * L * v * v + 0.004 * math.sin(u * 3 + v * 5))
            z = v * L
            verts.append((x, y, z))
            uvs.append(((u + 1) / 2, v))
    for j in range(NV - 1):
        for i in range(NU - 1):
            a = j * NU + i
            faces.append((a, a + 1, a + NU + 1, a + NU))
    ob = mesh_obj(name, verts, faces, mat, smooth=True)
    uvl = ob.data.uv_layers.new(name="UVMap")
    for poly in ob.data.polygons:
        for li in poly.loop_indices:
            uvl.data[li].uv = uvs[ob.data.loops[li].vertex_index]
    ob.modifiers.new("s", "SOLIDIFY").thickness = 0.0012
    return ob

def lotus_bloom(name, base, stem_h, rings, pod=True, seed=0):
    rnd = random.Random(seed)
    objs = []
    top = Vector(base) + Vector((0, 0, stem_h))
    st = loft_spine(name + "_stem", [Vector(base), Vector(base) + Vector((0.01, 0, stem_h * 0.5)), top],
                    [0.006, 0.0055, 0.005], M_STEM, 8, subsurf=0)
    for ri, (n, L, W, tilt, cup, curl) in enumerate(rings):
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * (ri % 2)) / n + rnd.uniform(-0.12, 0.12)
            pt = petal_mesh(f"{name}_p{ri}_{k}", L * rnd.uniform(0.92, 1.06), W, cup, curl, M_PETAL)
            pt.location = top
            pt.rotation_euler = (-(tilt + rnd.uniform(-0.12, 0.12)), rnd.uniform(-0.12, 0.12), a - math.pi / 2)
            objs.append(pt)
    if pod:
        bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.016, radius2=0.024, depth=0.022,
                                        location=top + Vector((0, 0, 0.018)))
        pd = bpy.context.active_object; pd.data.materials.append(M_POD); objs.append(pd)
        for k in range(9):
            a = 2 * math.pi * k / 9
            rr = 0.012 if k else 0
            bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.0028,
                                                 location=top + Vector((math.cos(a) * rr, math.sin(a) * rr, 0.0295)))
            s_ = bpy.context.active_object; s_.data.materials.append(M_POD); objs.append(s_)
        for k in range(46):
            a = 2 * math.pi * k / 46 + rnd.uniform(-0.05, 0.05)
            p0 = top + Vector((math.cos(a) * 0.02, math.sin(a) * 0.02, 0.006))
            p1 = p0 + Vector((math.cos(a) * 0.016, math.sin(a) * 0.016, 0.024 + rnd.uniform(-0.004, 0.004)))
            objs.append(cone_between(f"{name}_st{k}", p0, p1, 0.0007, 0.0012, M_STAMEN, 6))
    par = parent_all(name, objs + [st])
    for o in par.children:            # pivot at the stem base, not the world origin
        o.location = o.location - Vector(base)
    par.location = base
    return par

lotus_bloom("bloom", (5.0, 8.25, 0.0), 0.5, [
    (4, 0.08, 0.04, 0.3, 0.75, 0.10),
    (6, 0.1, 0.05, 0.75, 0.62, 0.05),
    (7, 0.11, 0.054, 1.2, 0.55, -0.03),
], seed=3)
BUD_TOP_H = 0.6
lotus_bloom("bud", (5.27, 8.42, 0.0), BUD_TOP_H - 0.08, [
    (5, 0.085, 0.034, -0.13, 0.55, 0.05),
    (5, 0.09, 0.036, -0.06, 0.55, 0.05),
], pod=False, seed=8)
BUD_TIP = Vector((5.27, 8.42, BUD_TOP_H - 0.08 + 0.085))
for nm, ph in (("bloom", 0.0), ("bud", 1.3)):
    o = scene.objects[nm]
    o.driver_add("rotation_euler", 0).driver.expression = f"0.010*sin(frame*0.06+{ph})"
    o.driver_add("rotation_euler", 1).driver.expression = f"0.008*sin(frame*0.045+{ph})"

# ============================================================ dragonfly (on the bud tip)
def dragonfly(name):
    objs = []
    objs.append(loft_spine(name + "_ab", [(-0.004 - 0.0033 * i, 0, -0.0004 * i) for i in range(10)],
                           [0.0016, 0.0019, 0.0017, 0.0015, 0.0015, 0.0016, 0.0016, 0.0015, 0.0013, 0.0008],
                           M_DF_BODY, 10, subsurf=1))
    objs.append(loft_spine(name + "_th", [(-0.005, 0, 0), (-0.001, 0, 0.0005), (0.003, 0, 0.0004), (0.005, 0, 0)],
                           [0.0018, 0.0033, 0.003, 0.002], M_DF_THORAX, 12, subsurf=1))
    for side in (-1, 1):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.0027,
                                             location=(0.0068, side * 0.0019, 0.0006))
        e = bpy.context.active_object; e.data.materials.append(M_DF_EYE); e.data.shade_smooth(); objs.append(e)
    wings = []
    for fore, x0, L, W, sweep in ((1, 0.0015, 0.031, 0.0068, -0.15), (0, -0.0028, 0.029, 0.0085, 0.08)):
        for side in (-1, 1):
            NU, NV = 6, 16
            verts, faces, uvs = [], [], []
            for j in range(NV):
                v = j / (NV - 1)
                w = W * math.sin(math.pi * (0.08 + 0.92 * v)) ** 0.6 * (1.0 - 0.2 * v)
                for i in range(NU):
                    u = i / (NU - 1)
                    verts.append(((u - 0.5) * w, side * v * L, -0.0012 * v * v))
                    uvs.append((u, v))
            for j in range(NV - 1):
                for i in range(NU - 1):
                    a = j * NU + i
                    faces.append((a, a + 1, a + NU + 1, a + NU))
            wo = mesh_obj(f"{name}_w{fore}{side}", verts, faces, M_WING, smooth=True)
            uvl = wo.data.uv_layers.new(name="UVMap")
            for poly in wo.data.polygons:
                for li in poly.loop_indices:
                    uvl.data[li].uv = uvs[wo.data.loops[li].vertex_index]
            wo.location = (x0, side * 0.0015, 0.0022)
            wo.rotation_euler.z = sweep * side
            wings.append((wo, side, fore))
            objs.append(wo)
    for k, (lx, ly) in enumerate(((0.003, 1), (0.003, -1), (0.0, 1), (0.0, -1), (-0.003, 1), (-0.003, -1))):
        objs.append(cone_between(f"{name}_leg{k}", (lx, ly * 0.001, -0.001), (lx + 0.002, ly * 0.0035, -0.0055),
                                 0.00035, 0.00025, M_LEG, 5))
    par = parent_all(name, objs)
    for wo, side, fore in wings:
        wo.driver_add("rotation_euler", 1).driver.expression = \
            f"{side}*(0.05*sin(frame*0.9+{fore}) + 0.35*max(0, sin(frame*0.04))**40)"
    return par

DF = dragonfly("dragonfly")
DF.location = BUD_TIP + Vector((0.0, 0.0, 0.004))
DF.rotation_euler = (0.0, -0.15, math.radians(144))
DF.scale = (1.5, 1.5, 1.5)

# ============================================================ standing egret (S4, and seen in S2 / S8)
def egret_standing(name):
    body = loft_spine(name + "_body",
                      [(-0.36, 0, 0.50), (-0.26, 0, 0.51), (-0.14, 0, 0.53), (-0.02, 0, 0.56), (0.07, 0, 0.60),
                       (0.12, 0, 0.65), (0.145, 0, 0.69)],
                      [0.008, 0.042, 0.07, 0.086, 0.08, 0.06, 0.045], M_FEATHER, 16, wscale=0.8, hscale=1.0)
    wings_f = []
    for side in (-1, 1):   # folded wing tips over the tail
        wings_f.append(loft_spine(f"{name}_wing{side}", [(0.04, side * 0.05, 0.6), (-0.12, side * 0.06, 0.56),
                                                         (-0.3, side * 0.035, 0.5), (-0.4, side * 0.015, 0.47)],
                                  [0.03, 0.035, 0.022, 0.006], M_FEATHER, 10, wscale=0.45, hscale=1.0))
    neck = loft_spine(name + "_neck",
                      [(0.0, 0, 0.0), (0.03, 0, 0.08), (0.0, 0, 0.17), (-0.04, 0, 0.25), (-0.02, 0, 0.33),
                       (0.03, 0, 0.38), (0.07, 0, 0.40), (0.11, 0, 0.405), (0.14, 0, 0.40)],
                      [0.04, 0.03, 0.024, 0.022, 0.022, 0.024, 0.027, 0.029, 0.02], M_FEATHER, 14)
    bill = cone_between(name + "_bill", (0.14, 0, 0.40), (0.27, 0, 0.385), 0.011, 0.0008, M_BILL, 10)
    bill.parent = neck
    for side in (-1, 1):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.0055, location=(0.12, side * 0.022, 0.41))
        e = bpy.context.active_object; e.data.materials.append(M_EYE); e.parent = neck
    neck_piv = bpy.data.objects.new(name + "_neckpivot", None); link(neck_piv)
    neck_piv.location = (0.14, 0, 0.68)
    neck.parent = neck_piv
    objs = [body, neck_piv] + wings_f
    for side in (-1, 1):
        objs.append(loft_spine(f"{name}_leg{side}", [(0.0, side * 0.035, 0.52), (0.0, side * 0.038, 0.42),
                                                     (-0.015, side * 0.04, 0.27), (0.0, side * 0.045, 0.05),
                                                     (0.01, side * 0.05, -0.08)],
                               [0.016, 0.009, 0.009, 0.007, 0.007], M_LEG, 8, subsurf=1))
    rnd = random.Random(9)
    pv, pfc = [], []
    for k in range(34):
        y0 = rnd.uniform(-0.05, 0.05)
        p0 = Vector((rnd.uniform(-0.14, -0.02), y0, 0.6))
        L = rnd.uniform(0.25, 0.42)
        pts = [p0 + Vector((-L * t, y0 * t * 0.8 + rnd.uniform(-0.01, 0.01), -0.32 * L * t * t)) for t in
               [i / 10 for i in range(11)]]
        for i in range(10):
            d = (pts[i + 1] - pts[i]).normalized()
            s = d.cross(Vector((0, 0, 1))).normalized() * 0.0035 * (1 - i / 11)
            n0 = len(pv)
            pv += [tuple(pts[i] - s), tuple(pts[i] + s), tuple(pts[i + 1] + s), tuple(pts[i + 1] - s)]
            pfc.append((n0, n0 + 1, n0 + 2, n0 + 3))
    objs.append(mesh_obj(name + "_plumes", pv, pfc, M_PLUME))
    return parent_all(name, objs), neck_piv

EGRET, NECK = egret_standing("egret")
EGRET.location = (8.6, 19.5, 0.0)
EGRET.rotation_euler.z = math.pi + 0.15
EGRET.scale = (1.05, 1.05, 1.05)
s0, s1 = SHOTS["S4"]
# idle, then notices the fish (ripple at s0+50) and turns / lowers toward it
key_seq(NECK, "rotation_euler", 2, [(s0, 0.0), (s0 + 52, 0.0), (s0 + 66, 0.28), (s1, 0.3)])
key_seq(NECK, "rotation_euler", 1, [(s0, -0.02), (s0 + 30, 0.03), (s0 + 56, 0.0), (s0 + 72, 0.22), (s0 + 100, 0.26),
                                    (s1, 0.24)])
EGRET.driver_add("location", 2).driver.expression = "0.003*sin(frame*0.05)"

# ============================================================ flying egrets
def egret_flying(name, k=1.0):
    body = loft_spine(name + "_b", [(-0.38 * k, 0, 0), (-0.25 * k, 0, 0.0), (-0.1 * k, 0, 0), (0.05 * k, 0, 0.01 * k),
                                    (0.12 * k, 0, 0.03 * k), (0.15 * k, 0, 0.075 * k), (0.2 * k, 0, 0.065 * k),
                                    (0.245 * k, 0, 0.062 * k)],
                      [0.006 * k, 0.045 * k, 0.07 * k, 0.06 * k, 0.04 * k, 0.03 * k, 0.032 * k, 0.018 * k], M_FEATHER, 10,
                      wscale=0.85)
    bill = cone_between(name + "_bill", (0.245 * k, 0, 0.062 * k), (0.37 * k, 0, 0.05 * k), 0.01 * k, 0.001 * k, M_BILL, 8)
    objs = [body, bill]
    for side in (-1, 1):
        objs.append(cone_between(f"{name}_leg{side}", (-0.15 * k, side * 0.02 * k, -0.02 * k),
                                 (-0.62 * k, side * 0.025 * k, -0.05 * k), 0.008 * k, 0.005 * k, M_LEG, 6))
    flaps = []
    for side in (-1, 1):
        def wing_part(nm, y0, y1, c0, c1, sweep):
            NU, NV = 5, 8
            verts, faces = [], []
            for j in range(NV):
                v = j / (NV - 1)
                y = y0 + (y1 - y0) * v
                c = c0 + (c1 - c0) * v ** 1.3
                for i in range(NU):
                    u = i / (NU - 1)
                    verts.append(((0.35 - u) * c - sweep * v, side * (y - y0), 0.02 * k * math.sin(math.pi * u)))
            for j in range(NV - 1):
                for i in range(NU - 1):
                    a = j * NU + i
                    faces.append((a, a + 1, a + NU + 1, a + NU))
            o = mesh_obj(nm, verts, faces, M_FEATHER, smooth=True)
            o.modifiers.new("s", "SOLIDIFY").thickness = 0.008 * k
            return o
        inner = wing_part(f"{name}_wi{side}", 0, 0.42 * k, 0.30 * k, 0.26 * k, 0.02 * k)
        outer = wing_part(f"{name}_wo{side}", 0, 0.46 * k, 0.26 * k, 0.07 * k, 0.12 * k)
        inner.location = (0.0, side * 0.04 * k, 0.015 * k)
        outer.parent = inner
        outer.location = (-0.02 * k, side * 0.42 * k, 0.0)
        objs.append(inner)
        flaps.append((inner, outer, side))
    return parent_all(name, objs), flaps

def flock(prefix, shot, n, p0, vel, spread, span, seed, flap_rate=0.42):
    rnd = random.Random(seed)
    f0, f1 = SHOTS[shot]
    for i in range(n):
        par, flaps = egret_flying(f"{prefix}{i}", span)
        off = Vector((i * spread[0] + rnd.uniform(-1, 1) * spread[0] * 0.4, rnd.uniform(-1, 1) * spread[1],
                      rnd.uniform(-1, 1) * spread[2]))
        st = Vector(p0) + off
        for ax in range(3):
            par.driver_add("location", ax).driver.expression = f"{st[ax]:.3f} + (frame-{f0})*{vel[ax]:.4f}" + (
                f" + 0.15*sin(frame*0.06+{i})" if ax == 2 else "")
        par.rotation_euler.z = math.atan2(vel[1], vel[0])
        ph = rnd.uniform(0, 6.28)
        rate = flap_rate * rnd.uniform(0.9, 1.1)
        for inner, outer, side in flaps:
            inner.driver_add("rotation_euler", 0).driver.expression = f"{side}*(0.12+0.62*sin(frame*{rate:.3f}+{ph:.2f}))"
            outer.driver_add("rotation_euler", 0).driver.expression = f"{side}*(0.05+0.45*sin(frame*{rate:.3f}+{ph - 0.9:.2f}))"
        visible_only(par, f0, f1)

flock("fl_s2_", "S2", 3, (36, 62, 3.4), (-0.30, 0.0, -0.004), (2.2, 2.0, 0.5), 1.0, 11)
flock("fl_s3_", "S3", 6, (128, 350, 44), (-0.46, -0.02, 0.0), (5.5, 10, 3.0), 1.0, 12)
flock("fl_s8_", "S8", 4, (-14, 180, 13), (0.28, 0.06, 0.012), (4.0, 6, 1.5), 1.0, 13)

# ============================================================ mallards (S6) — swim across the sun's glitter path
def mallard(name, male):
    mat = M_DUCK_M if male else M_DUCK_F
    body = loft_spine(name + "_b", [(-0.27, 0, 0.075), (-0.2, 0, 0.065), (-0.08, 0, 0.06), (0.06, 0, 0.065),
                                    (0.15, 0, 0.08), (0.19, 0, 0.13), (0.2, 0, 0.18), (0.235, 0, 0.215),
                                    (0.27, 0, 0.215), (0.295, 0, 0.205)],
                      [0.01, 0.07, 0.105, 0.105, 0.08, 0.045, 0.04, 0.046, 0.04, 0.02], mat, 16,
                      wscale=1.05, hscale=0.72)
    bill = loft_spine(name + "_bill", [(0.29, 0, 0.205), (0.33, 0, 0.198), (0.355, 0, 0.192)],
                      [0.018, 0.016, 0.011], M_DUCK_BILL if male else M_DUCK_BILL_F, 10, wscale=1.3, hscale=0.45)
    return parent_all(name, [body, bill])

DUCKS = []
s0, s1 = SHOTS["S6"]
for nm, male, start, lag in (("duck_m", True, (5.4, 28.1), 0), ("duck_f", False, (6.2, 28.6), 14)):
    d = mallard(nm, male)
    d.rotation_euler.z = math.pi + 0.06
    speed = 0.03  # m / frame
    x0, y0 = start
    d.driver_add("location", 0).driver.expression = f"{x0} - (frame-{s0 - lag})*{speed}"
    d.driver_add("location", 1).driver.expression = f"{y0} + (frame-{s0})*0.0012"
    d.driver_add("location", 2).driver.expression = f"-0.035 + 0.006*sin(frame*0.35+{lag})"
    d.driver_add("rotation_euler", 1).driver.expression = f"0.03*sin(frame*0.35+{lag}+0.8)"
    DUCKS.append(d)

# ============================================================ ripple canvases (dynamic paint waves)
def make_canvas(name, center, size, res, f0, f1):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=res, y_subdivisions=res, size=size,
                                    location=(center[0], center[1], 0.0015))
    cv = bpy.context.active_object
    cv.name = name
    cv.data.materials.append(M_WATER)
    cv.data.shade_smooth()
    bpy.context.view_layer.objects.active = cv
    md = cv.modifiers.new("dp", "DYNAMIC_PAINT")
    md.ui_type = "CANVAS"
    bpy.ops.dpaint.type_toggle(type="CANVAS")
    surf = md.canvas_settings.canvas_surfaces[0]
    surf.surface_type = "WAVE"
    surf.frame_start, surf.frame_end = f0, f1
    surf.wave_timescale = 1.0
    surf.wave_speed = 0.55
    surf.wave_damping = 0.035
    surf.wave_spring = 0.08
    surf.wave_smoothness = 1.0
    surf.use_wave_open_border = True
    ss = cv.modifiers.new("ss", "SUBSURF"); ss.levels = 1; ss.render_levels = 1
    return cv, surf

def make_brush(ob, factor, wtype="DEPTH"):
    bpy.context.view_layer.objects.active = ob
    md = ob.modifiers.new("dpb", "DYNAMIC_PAINT")
    md.ui_type = "BRUSH"
    bpy.ops.dpaint.type_toggle(type="BRUSH")
    md.brush_settings.wave_type = wtype
    md.brush_settings.wave_factor = factor
    md.brush_settings.wave_clamp = 0.0

CANVASES = [make_canvas("ripple_ducks", (3.0, 28.4), 9.0, 240, SHOTS["S6"][0] - 40, SHOTS["S6"][1]),
            make_canvas("ripple_egret", (8.2, 19.6), 3.6, 150, SHOTS["S4"][0] - 20, SHOTS["S4"][1])]

# dynamic paint ignores driven parents -> un-parented, keyframed proxies act as the wake brushes
_proxies = []
for d in DUCKS:
    body = [c for c in d.children if c.name.endswith("_b")][0]
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0, location=(0, 0, 0))
    px = bpy.context.active_object
    px.name = body.name + "_wakebrush"
    px.data.transform(Matrix.Diagonal((0.28, 0.12, 0.09, 1.0)) @ Matrix.Translation((0.0, 0.0, 0.0)))
    px.data.transform(Matrix.Translation((0.0, 0.0, 0.03)))
    px.hide_render = True
    _proxies.append((body, px))
for fr in range(SHOTS["S6"][0] - 40, SHOTS["S6"][1] + 1):
    scene.frame_set(fr)
    for body, px in _proxies:
        px.matrix_world = body.matrix_world.copy()
        px.keyframe_insert("location", frame=fr)
        px.keyframe_insert("rotation_euler", frame=fr)
scene.frame_set(1)
for body, px in _proxies:
    make_brush(px, 1.0)
for leg in [o for o in descendants(EGRET) if "_leg" in o.name]:
    make_brush(leg, 0.15)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, location=(7.75, 19.6, -0.2))
fish = bpy.context.active_object
fish.name = "fish_brush"
fish.hide_render = True
s0 = SHOTS["S4"][0]
key_seq(fish, "location", 2, [(s0 + 44, -0.25), (s0 + 50, 0.01), (s0 + 53, 0.0), (s0 + 58, -0.25),
                              (s0 + 86, -0.25), (s0 + 89, 0.005), (s0 + 93, -0.25)])
make_brush(fish, 1.0)

# ============================================================ willow sway (wind)
wind = link(bpy.data.objects.new("Wind", None))
wind.driver_add("location", 0).driver.expression = "frame*0.011"
wind.driver_add("location", 1).driver.expression = "frame*0.004"
wtex = bpy.data.textures.new("wind_tex", "CLOUDS")
wtex.noise_scale = 1.6
for ob in [o for o in scene.objects if o.name.endswith("_leaves") or o.name.endswith("_twigs")]:
    me = ob.data
    zs = [v.co.z for v in me.vertices]
    if not zs:
        continue
    ztop = max(zs)
    vg = ob.vertex_groups.new(name="sway")
    for v in me.vertices:
        vg.add([v.index], min(1.0, max(0.0, (ztop - v.co.z) / 3.5)) ** 1.3, "REPLACE")
    near = ob.name.startswith("willow_fg")
    for axis, st in (("X", 0.16 if near else 0.25), ("Y", 0.08 if near else 0.12)):
        md = ob.modifiers.new("sway" + axis, "DISPLACE")
        md.texture = wtex
        md.texture_coords = "OBJECT"
        md.texture_coords_object = wind
        md.direction = axis
        md.strength = st
        md.mid_level = 0.5
        md.vertex_group = "sway"

# ============================================================ cameras
def shot_camera(name, keys, lens, fstop, focus_keys, sensor=36):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
    cd.clip_start = 0.005
    cd.clip_end = 8000
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = fstop
    cd.dof.aperture_blades = 7
    co = link(bpy.data.objects.new(name, cd))
    for f, loc, tgt in keys:
        co.location = loc
        co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        co.keyframe_insert("location", frame=f)
        co.keyframe_insert("rotation_euler", frame=f)
    for f, dist in focus_keys:
        cd.dof.focus_distance = dist
        cd.dof.keyframe_insert("focus_distance", frame=f)
    return co

CAMS = {}
a, b = SHOTS["S1"]
CAMS["S1"] = shot_camera("cam_S1", [(a, (3.0, 5.66, 0.15), (3.21, 6.02, 0.034)),
                                    (b, (3.045, 5.66, 0.142), (3.245, 6.01, 0.03))], 100, 3.2,
                         [(a, d3((3.0, 5.66, 0.15), (3.205, 6.0, 0.034))), (b, d3((3.045, 5.66, 0.142), (3.24, 6.0, 0.03)))])
a, b = SHOTS["S2"]
CAMS["S2"] = shot_camera("cam_S2", [(a, (0.55, -3.2, 1.22), (0.55 + 600 * math.sin(math.radians(3.6)), 600, 17)),
                                    (b, (0.4, 0.8, 1.40), (0.4 + 600 * math.sin(math.radians(5.0)), 600, 21))], 45, 4.0,
                         [(a, 44), (b, 44)])
a, b = SHOTS["S3"]
CAMS["S3"] = shot_camera("cam_S3", [(a, (2.0, 0.0, 1.6), (176, 935, 96)), (b, (2.9, 0.0, 1.62), (179, 935, 97))], 135, 5.6,
                         [(a, 900), (b, 900)])
a, b = SHOTS["S4"]
E_T = Vector((8.45, 19.5, 0.55))
S4A = E_T - Vector((math.sin(math.radians(20)), math.cos(math.radians(20)), 0)) * 30
S4A.z = 0.55
S4B = S4A + Vector((0.45, 0.1, 0.0))
CAMS["S4"] = shot_camera("cam_S4", [(a, S4A, E_T), (b, S4B, E_T + Vector((0, 0, -0.03)))], 200, 4.0,
                         [(a, d3(S4A, E_T)), (b, d3(S4B, E_T))])
a, b = SHOTS["S5"]
L0 = (4.6, 7.42, 0.86)
L1 = tuple(BUD_TIP + (Vector(L0) - BUD_TIP).normalized() * 0.85)
CAMS["S5"] = shot_camera("cam_S5", [(a, L0, (5.05, 8.3, 0.53)), (a + 40, L0, (5.06, 8.3, 0.535)), (b, L1, tuple(BUD_TIP))],
                         90, 2.8, [(a, d3(L0, (5.0, 8.25, 0.56))), (a + 42, d3(L0, (5.0, 8.25, 0.56))),
                                   (a + 70, 0.95), (b, 0.85)])
a, b = SHOTS["S6"]
S6C = Vector((3.4, 28.3, 0.0)) - Vector((math.sin(math.radians(21)), math.cos(math.radians(21)), 0)) * 42
S6C.z = 0.45
CAMS["S6"] = shot_camera("cam_S6", [(a, S6C, (3.55, 28.3, 0.12)), (b, S6C + Vector((0.1, 0, 0)), (3.1, 28.4, 0.12))],
                         200, 4.0, [(a, 42.0), (b, 42.2)])
a, b = SHOTS["S7"]
CAMS["S7"] = shot_camera("cam_S7", [(a, (-3.05, 3.9, 2.2), (-1.75, 7.3, 2.45)), (b, (-2.95, 4.08, 2.24), (-1.6, 7.4, 2.5))],
                         85, 2.0, [(a, 2.6), (a + 34, 2.6), (a + 66, 70), (b, 70)])
a, b = SHOTS["S8"]
CAMS["S8"] = shot_camera("cam_S8", [(a, (2.6, -1.0, 1.8), (40, 600, 13)), (b, (3.2, -9.5, 3.2), (40, 600, 10))], 35, 8.0,
                         [(a, 60), (b, 60)])

# ============================================================ reflector fill for the macro shots
def fill_light(name, loc, tgt, energy, size, shot):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    ld.color = (1.0, 0.86, 0.72)
    lo = link(bpy.data.objects.new(name, ld))
    lo.location = loc
    lo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    lo.visible_camera = False
    lo.visible_glossy = False
    f0, f1 = SHOTS[shot]
    key_hide(lo, f0, f1, True)

fill_light("fill_S5", (4.45, 7.55, 0.75), (5.05, 8.3, 0.58), 6.0, 0.8, "S5")
fill_light("fill_S1", (2.9, 5.7, 0.3), (3.2, 6.0, 0.02), 2.0, 0.6, "S1")

# hide the foreground willow for the closing pull-back (its bare trunk would show)
for o in [o for o in scene.objects if o.name.startswith("willow_fg")]:
    key_hide(o, SHOTS["S8"][0], SHOTS["S8"][1], visible_inside=False)

# ============================================================ run
di = ARGS.index("doc")
SHOT = ARGS[di + 1]
f0, f1 = SHOTS[SHOT]
scene.camera = CAMS[SHOT]
scene.render.use_persistent_data = True
if SHOT == "S1":
    scene.cycles.max_bounces = 10
    scene.cycles.transmission_bounces = 10

need_sim = SHOT in ("S4", "S6") and "nobake" not in ARGS
single = None
if "frame" in ARGS:
    v = ARGS[ARGS.index("frame") + 1]
    single = {"mid": (f0 + f1) // 2, "first": f0, "last": f1}.get(v, None) or f0 + int(v)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "westlake_doc.blend"))
if OUT:
    if single:
        if need_sim:
            surf_start = min(s.frame_start for _, s in CANVASES)
            for fr in range(surf_start, single + 1):
                scene.frame_set(fr)
            dg = bpy.context.evaluated_depsgraph_get()
            for cv, surf in CANVASES:
                zs = [v.co.z for v in cv.evaluated_get(dg).data.vertices]
                print("CANVAS", cv.name, "zmin %.4f zmax %.4f" % (min(zs), max(zs)))
        else:
            scene.frame_set(single)
        scene.render.filepath = os.path.join(OUT, f"{SHOT}_{single:04d}.png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", scene.render.filepath)
    else:
        # render frame by frame so the ripple sim advances sequentially
        os.makedirs(os.path.join(OUT, SHOT), exist_ok=True)
        start_sim = min(s.frame_start for _, s in CANVASES) if need_sim else f0
        for fr in range(start_sim, f1 + 1):
            scene.frame_set(fr)
            if fr < f0:
                continue
            path = os.path.join(OUT, SHOT, f"f_{fr:04d}.png")
            if os.path.exists(path) and not need_sim:
                continue
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
        print("RENDERED_SHOT", SHOT)
DOC_DONE = True
