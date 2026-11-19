# 西湖 · 晨雾  —— Blender 5.2 程序化场景
# 用法: blender -b --factory-startup -P build_westlake.py -- [out.png] [samples] [res%]
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix, noise

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if len(ARGS) > 0 else ""
SAMPLES = int(ARGS[1]) if len(ARGS) > 1 else 64
RESPCT = int(ARGS[2]) if len(ARGS) > 2 else 50
HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(7)

# ---------------------------------------------------------------- reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection

def link(obj):
    col.objects.link(obj)
    return obj

def mesh_obj(name, verts, faces, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    return link(ob)

def setin(node, name, val):
    if name in node.inputs:
        node.inputs[name].default_value = val

# ---------------------------------------------------------------- materials
def principled(name, color, rough=0.5, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    setin(p, "Base Color", (*color, 1))
    setin(p, "Roughness", rough)
    for k, v in kw.items():
        setin(p, k.replace("_", " "), v)
    return m, p

def add_noise_color(m, p, c1, c2, scale=0.3, detail=6):
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.7
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    return nz

def add_bump(m, p, scale, strength, dist=0.1):
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 8
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = dist
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])

def foliage(name, color, translucent=(0.55, 0.75, 0.15), mix=0.35, rough=0.55):
    m, p = principled(name, color, rough, Specular_IOR_Level=0.35)
    nt = m.node_tree
    out = nt.nodes["Material Output"]
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = (*translucent, 1)
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.inputs["Fac"].default_value = mix
    nt.links.new(p.outputs[0], mx.inputs[1])
    nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    # per-object colour variation
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Color"].default_value = (*color, 1)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.47
    mr.inputs["To Max"].default_value = 0.53
    nt.links.new(oi.outputs["Random"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], hsv.inputs["Hue"])
    nt.links.new(hsv.outputs["Color"], p.inputs["Base Color"])
    return m

def emissive(name, color, strength):
    m, p = principled(name, color, 0.5)
    setin(p, "Emission Color", (*color, 1))
    setin(p, "Emission Strength", strength)
    return m

M_WILLOW = foliage("willow", (0.20, 0.33, 0.06), (0.55, 0.72, 0.12), 0.4)
M_WILLOW_FAR = foliage("willow_far", (0.10, 0.17, 0.05), (0.35, 0.5, 0.1), 0.3)
M_TREE = foliage("tree", (0.05, 0.09, 0.035), (0.25, 0.35, 0.08), 0.25, 0.8)
M_TWIG, _ = principled("twig", (0.06, 0.05, 0.03), 0.8)
M_BARK, pb = principled("bark", (0.05, 0.04, 0.03), 0.9)
add_bump(M_BARK, pb, 6, 0.6)

M_STONE, ps = principled("stone", (0.45, 0.44, 0.41), 0.75)
add_noise_color(M_STONE, ps, (0.13, 0.135, 0.13), (0.36, 0.36, 0.34), 0.6)
add_bump(M_STONE, ps, 3, 0.35)

M_LAND, pl = principled("land", (0.05, 0.06, 0.03), 0.95)
add_noise_color(M_LAND, pl, (0.03, 0.04, 0.02), (0.09, 0.09, 0.05), 0.2)

M_HILL, ph = principled("hill", (0.035, 0.05, 0.03), 0.95)
add_noise_color(M_HILL, ph, (0.02, 0.035, 0.02), (0.07, 0.08, 0.045), 0.02)

M_LOTUS = foliage("lotus", (0.02, 0.06, 0.02), (0.35, 0.6, 0.08), 0.35, 0.62)
setin(M_LOTUS.node_tree.nodes["Principled BSDF"], "Specular IOR Level", 0.15)
M_LOTUS_OLD, _ = principled("lotus_old", (0.20, 0.13, 0.05), 0.6)
M_BUD, pbud = principled("lotus_bud", (0.85, 0.35, 0.45), 0.4, Subsurface_Weight=0.4)
M_STEM, _ = principled("stem", (0.10, 0.16, 0.05), 0.5)

M_PAG_BODY, ppb = principled("pagoda_body", (0.28, 0.08, 0.05), 0.7)
M_PAG_ROOF, _ = principled("pagoda_roof", (0.07, 0.06, 0.05), 0.45, Metallic=0.5)
M_WARM = emissive("warm_light", (1.0, 0.55, 0.22), 12)
M_WARM_DIM = emissive("warm_dim", (1.0, 0.5, 0.2), 1.2)
M_EMBER = emissive("ember", (1.0, 0.42, 0.15), 0.9)
M_LANTERN = emissive("red_lantern", (1.0, 0.12, 0.03), 6)

M_HULL, phull = principled("hull", (0.12, 0.07, 0.035), 0.6)
add_noise_color(M_HULL, phull, (0.07, 0.04, 0.02), (0.18, 0.10, 0.05), 3)
M_CANOPY, _ = principled("canopy", (0.025, 0.022, 0.018), 0.85)
M_HAT, _ = principled("hat", (0.30, 0.22, 0.11), 0.8)
M_BIRD, _ = principled("bird", (0.75, 0.74, 0.70), 0.7)

# water ----------------------------------------------------------------
def water_material():
    m = bpy.data.materials.new("water")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    setin(p, "Base Color", (0.010, 0.016, 0.014, 1))
    setin(p, "Roughness", 0.02)
    setin(p, "IOR", 1.333)
    tc = nt.nodes.new("ShaderNodeNewGeometry")
    # large slow swells
    mp = nt.nodes.new("ShaderNodeMapping")
    setin(mp, "Scale", (1.0, 2.6, 1.0))
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.noise_dimensions = "4D"
    n1.inputs["Scale"].default_value = 0.35
    n1.inputs["Detail"].default_value = 4
    n1.name = "swell"
    # fine ripples
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.noise_dimensions = "4D"
    n2.inputs["Scale"].default_value = 3.0
    n2.inputs["Detail"].default_value = 3
    n2.name = "ripple"
    nt.links.new(tc.outputs["Position"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], n1.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], n2.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 0.18
    nt.links.new(n2.outputs["Fac"], add.inputs[0])
    nt.links.new(n1.outputs["Fac"], add.inputs[2])
    # bump weaker in distance (keeps far reflections mirror-like)
    cam_d = nt.nodes.new("ShaderNodeCameraData")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 5
    mr.inputs["From Max"].default_value = 260
    mr.inputs["To Min"].default_value = 0.6
    mr.inputs["To Max"].default_value = 0.025
    nt.links.new(cam_d.outputs["View Distance"], mr.inputs["Value"])
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Distance"].default_value = 0.05
    nt.links.new(mr.outputs["Result"], b.inputs["Strength"])
    nt.links.new(add.outputs[0], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    # drivers for animated ripples
    for nm, speed in (("swell", 0.010), ("ripple", 0.04)):
        d = nt.nodes[nm].inputs["W"].driver_add("default_value").driver
        d.expression = f"frame*{speed}"
    return m

M_WATER = water_material()

# ---------------------------------------------------------------- world / sky
SUN_ELEV = math.radians(5.6)
SUN_AZ = math.radians(22.0)          # degrees to the right of camera axis (+Y)
sun_vec = Vector((math.sin(SUN_AZ) * math.cos(SUN_ELEV),
                  math.cos(SUN_AZ) * math.cos(SUN_ELEV),
                  math.sin(SUN_ELEV)))

world = bpy.data.worlds.new("dawn")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
bg = wnt.nodes["Background"]
sky = wnt.nodes.new("ShaderNodeTexSky")
sky.sky_type = "MULTIPLE_SCATTERING"
sky.sun_disc = True
sky.sun_size = math.radians(1.3)
sky.sun_intensity = 0.12
sky.sun_elevation = SUN_ELEV
# Blender sky: rotation 0 => sun toward -Y; we want toward +Y, rotated right
sky.sun_rotation = SUN_AZ
sky.air_density = 1.2
sky.aerosol_density = 3.0
sky.altitude = 20
wnt.links.new(sky.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.16

sun_data = bpy.data.lights.new("sun", "SUN")
sun_data.energy = 6.0
sun_data.color = (1.0, 0.52, 0.24)
sun_data.angle = math.radians(0.6)
sun = link(bpy.data.objects.new("sun", sun_data))
sun.rotation_euler = sun_vec.to_track_quat("Z", "Y").to_euler()

# ---------------------------------------------------------------- water plane
mesh_obj("lake", [(-4000, -500, 0), (4000, -500, 0), (4000, 4000, 0), (-4000, 4000, 0)],
         [(0, 1, 2, 3)], M_WATER)

# ---------------------------------------------------------------- hills
def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

def hill_layer(name, yc, depth, H, x0, x1, seed, mask=None, bumps=(), nx=420, ny=16):
    verts, faces = [], []
    for j in range(ny):
        v = j / (ny - 1)
        y = yc - depth / 2 + v * depth
        for i in range(nx):
            u = i / (nx - 1)
            x = x0 + u * (x1 - x0)
            p = Vector((x * 0.0025 + seed, seed * 3.1, 0))
            h = H * (0.45 + 0.55 * (noise.fractal(p, 0.6, 2.0, 4) * 0.5 + 0.5))
            for bx, bw, bh in bumps:
                h += bh * math.exp(-((x - bx) / bw) ** 2)
            if mask:
                h *= mask(x)
            prof = math.sin(min(1.0, v * 1.6) * math.pi / 2) ** 1.5
            canopy = noise.noise(Vector((x * 0.12, y * 0.12, seed))) * 1.6 * (H / 40)
            z = max(-1.0, h * prof + canopy * prof) - 0.6
            verts.append((x, y, z))
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    return mesh_obj(name, verts, faces, M_HILL, smooth=True)

# north shore / Gushan (left), fades out to the right
hill_layer("hill_near_left", 520, 160, 38, -900, 120, 1.3,
           mask=lambda x: smoothstep(60, -160, x), bumps=((-380, 120, 25),))
# Xizhao hill with Leifeng (right-middle)
hill_layer("hill_leifeng", 980, 200, 22, -300, 1200, 4.7,
           mask=lambda x: smoothstep(-250, 0, x), bumps=((175, 120, 48), (420, 160, 20)))
hill_layer("hill_mid", 1650, 300, 120, -1800, 1800, 8.2, bumps=((-600, 300, 60),))
hill_layer("hill_far", 2600, 400, 260, -2600, 2600, 12.9, bumps=((300, 500, 120),))

# ---------------------------------------------------------------- pagodas
def oct_ring(r, z, n=32, lift=0.0, corner_sharp=4):
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n + math.pi / 8
        seg = (math.degrees(a - math.pi / 8) % 45) - 22.5
        rr = r * math.cos(math.radians(22.5)) / math.cos(math.radians(seg))
        c = abs(seg) / 22.5
        pts.append((rr * math.cos(a), rr * math.sin(a), z + lift * c ** corner_sharp))
    return pts

def loft(rings, close=True):
    verts, faces = [], []
    n = len(rings[0])
    for r in rings:
        verts += r
    for j in range(len(rings) - 1):
        for k in range(n):
            a, b = j * n + k, j * n + (k + 1) % n
            faces.append((a, b, b + n, a + n))
    return verts, faces

def leifeng(origin, scale=1.0):
    objs = []
    z = 0.0
    def add(name, rings, mat, cap_top=False):
        v, f = loft(rings)
        if cap_top:
            f.append(tuple(range(len(v) - len(rings[-1]), len(v))))
        ob = mesh_obj(name, v, f, mat, smooth=False)
        objs.append(ob)
        return ob
    # platform
    add("lf_base", [oct_ring(17, -2), oct_ring(17, 3), oct_ring(14, 3), oct_ring(14, 6)], M_STONE, True)
    z = 6
    for i in range(5):
        rb = 10.5 - i * 1.05
        hb = 7.5 - i * 0.4
        add(f"lf_body{i}", [oct_ring(rb, z), oct_ring(rb, z + hb)], M_PAG_BODY)
        # glowing windows (one per alternate face)
        for k in range(8):
            if (k + i) % 2:
                continue
            a = math.radians(45 * k + 22.5) + math.pi / 8 - math.radians(22.5)
            a = 2 * math.pi * k / 8 + math.pi / 8 + math.pi / 8
            cx, cy = (rb * 0.93 + 0.12) * math.cos(a), (rb * 0.93 + 0.12) * math.sin(a)
            t = Vector((-math.sin(a), math.cos(a), 0))
            w, h = 1.1, 2.4
            zc = z + hb * 0.45
            c = Vector((cx, cy, zc))
            vs = [c - t * w / 2 - Vector((0, 0, h / 2)), c + t * w / 2 - Vector((0, 0, h / 2)),
                  c + t * w / 2 + Vector((0, 0, h / 2)), c - t * w / 2 + Vector((0, 0, h / 2))]
            objs.append(mesh_obj(f"lf_win{i}_{k}", [tuple(v) for v in vs], [(0, 1, 2, 3)], M_WARM_DIM))
        z += hb
        re = rb + 4.2 - i * 0.2
        add(f"lf_roof{i}", [oct_ring(rb, z - 0.2), oct_ring(re, z - 0.9, lift=1.5),
                            oct_ring(re, z - 1.5, lift=1.5), oct_ring(rb * 0.97, z - 1.2),
                            ], M_PAG_ROOF)
        add(f"lf_roofTop{i}", [oct_ring(re * 0.98, z - 0.85, lift=1.45), oct_ring(rb * 0.75, z + 0.9)], M_PAG_ROOF)
        z += 0.9
    # top roof + spire
    add("lf_cap", [oct_ring(8.5, z - 0.4, lift=1.4), oct_ring(1.0, z + 5.5), oct_ring(0.3, z + 6)], M_PAG_ROOF)
    add("lf_spire", [oct_ring(0.5, z + 5, 8), oct_ring(0.25, z + 15, 8)], M_PAG_ROOF)
    for s, (zz, r) in enumerate(((z + 8, 1.0), (z + 10, 0.8), (z + 12, 0.6))):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(0, 0, zz), segments=16, ring_count=8)
        o = bpy.context.active_object
        o.data.materials.append(M_PAG_ROOF)
        objs.append(o)
    parent = bpy.data.objects.new("Leifeng", None)
    link(parent)
    for o in objs:
        o.parent = parent
    parent.location = origin
    parent.scale = (scale,) * 3
    parent.rotation_euler.z = math.radians(10)
    return parent

def ground_z(x, y):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    hit, loc, *_ = scene.ray_cast(dg, Vector((x, y, 2000)), Vector((0, 0, -1)))
    return loc.z if hit else 0.0

LF_X, LF_Y = 175, 935
leifeng((LF_X, LF_Y, ground_z(LF_X, LF_Y) - 2.0), 1.5)

def baochu(origin):
    rings = []
    for k in range(18):
        t = k / 17
        r = 3.2 * (1 - t) ** 1.2 + 0.25
        rings.append(oct_ring(r, t * 48, 8))
        if k % 2 == 1 and k < 16:
            rings.append(oct_ring(r * 1.35, t * 48 + 0.4, 8))
            rings.append(oct_ring(r, t * 48 + 0.8, 8))
    v, f = loft(rings)
    ob = mesh_obj("Baochu", v, f, M_PAG_ROOF)
    ob.location = origin
    return ob

baochu((-375, 540, ground_z(-375, 540) - 1.0))

# ---------------------------------------------------------------- foliage generators
def willow(name, base, height, crown_r, n_strands, strand_len, leaf_len, leaves_per_step,
           mat, tips=None, lean=(0.0, 0.0), seed=0, step=0.12):
    rnd = random.Random(seed)
    base = Vector(base)
    top = base + Vector((lean[0], lean[1], height))
    lv, lf = [], []
    def leaf(c, d, side):
        n = d.cross(side).normalized()
        L = leaf_len * rnd.uniform(0.75, 1.2)
        W = L * 0.16
        p0 = c
        p1 = c + d * L
        s = side * W / 2
        q = [p0, c + d * L * 0.38 + s, p1, c + d * L * 0.38 - s]
        i = len(lv)
        lv.extend([tuple(x) for x in q])
        lf.append((i, i + 1, i + 2, i + 3))
    tv, tf = [], []
    def twig(pts, w):
        # flat ribbon
        for k in range(len(pts) - 1):
            d = (pts[k + 1] - pts[k]).normalized()
            s = d.cross(Vector((0.3, 1, 0.1))).normalized() * w
            i = len(tv)
            tv.extend([tuple(pts[k] - s), tuple(pts[k] + s), tuple(pts[k + 1] + s), tuple(pts[k + 1] - s)])
            tf.append((i, i + 1, i + 2, i + 3))
    for s in range(n_strands):
        if tips:
            p = Vector(tips(rnd))
        else:
            a = rnd.uniform(0, 2 * math.pi)
            r = crown_r * math.sqrt(rnd.uniform(0.05, 1))
            p = top + Vector((math.cos(a) * r, math.sin(a) * r * 0.85,
                              rnd.uniform(-0.5, 0.35) * crown_r * 0.6 - (r / crown_r) ** 2 * crown_r * 0.35))
        out = Vector((p.x - top.x, p.y - top.y, 0))
        out = out.normalized() if out.length > 1e-3 else Vector((1, 0, 0))
        d = (out * rnd.uniform(0.4, 1.0) + Vector((0, 0, rnd.uniform(-0.2, 0.5)))).normalized()
        L = strand_len * (rnd.uniform(0.35, 1.0) + (rnd.random() < 0.12) * rnd.uniform(0.5, 0.9))
        n = max(3, int(L / step))
        pts = [p.copy()]
        sway = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.02
        for k in range(n):
            d = (d + Vector((0, 0, -0.32)) + sway).normalized()
            p = p + d * step
            if p.z < 0.08:
                break
            pts.append(p.copy())
        twig(pts, 0.004 * leaf_len / 0.12)
        for k, c in enumerate(pts[1:], 1):
            dd = (pts[k] - pts[k - 1]).normalized()
            for _ in range(leaves_per_step):
                if rnd.random() < 0.15:
                    continue
                side = dd.cross(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))).normalized()
                ld = (dd * rnd.uniform(0.6, 1.0) + side * rnd.uniform(0.3, 0.9)).normalized()
                leaf(c, ld, ld.cross(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 1))).normalized())
    lob = mesh_obj(name + "_leaves", lv, lf, mat)
    tob = mesh_obj(name + "_twigs", tv, tf, M_TWIG)
    # trunk
    trunk_pts = [base + (top - base) * t + Vector((math.sin(t * 3 + seed) * 0.3, 0, 0)) for t in
                 [i / 8 for i in range(9)]]
    rings = []
    for k, c in enumerate(trunk_pts):
        r = (0.035 * height) * (1 - k / 10)
        rings.append([tuple(c + Vector((math.cos(a) * r, math.sin(a) * r, 0)))
                      for a in [2 * math.pi * q / 10 for q in range(10)]])
    v, f = loft(rings)
    trunk = mesh_obj(name + "_trunk", v, f, M_BARK, smooth=True)
    # main limbs toward crown
    for b in range(6):
        a = rnd.uniform(0, 2 * math.pi)
        e = top + Vector((math.cos(a) * crown_r * 0.7, math.sin(a) * crown_r * 0.6, rnd.uniform(-0.3, 0.6)))
        st = base + (top - base) * rnd.uniform(0.55, 0.8)
        rings = []
        for k in range(7):
            t = k / 6
            c = st.lerp(e, t) + Vector((0, 0, math.sin(t * math.pi) * crown_r * 0.25))
            r = 0.02 * height * (1 - t * 0.85)
            rings.append([tuple(c + Vector((math.cos(q) * r, math.sin(q) * r, 0)))
                          for q in [2 * math.pi * z / 8 for z in range(8)]])
        v, f = loft(rings)
        mesh_obj(name + f"_limb{b}", v, f, M_BARK, smooth=True)
    return lob

def round_tree(name, loc, r, seed):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (1, 1, random.Random(seed).uniform(0.75, 1.0))
    tex = bpy.data.textures.new(name + "_tx", "CLOUDS")
    tex.noise_scale = r * 0.35
    md = o.modifiers.new("d", "DISPLACE")
    md.texture = tex
    md.strength = r * 0.45
    md.texture_coords = "GLOBAL"
    o.data.materials.append(M_TREE)
    o.data.shade_smooth()
    return o

# ---------------------------------------------------------------- foreground willow (frames top-left)
def fg_tips(rnd):
    x = -3.9 + 3.3 * rnd.random() ** 1.8
    return (x, rnd.uniform(5.5, 9.0), rnd.uniform(3.1, 3.9))

willow("willow_fg", (-6.5, 9.0, -0.2), 7.0, 4.5, 150, 2.6, 0.12, 2, M_WILLOW,
       tips=fg_tips, lean=(2.0, 0.3), seed=11, step=0.09)

# ---------------------------------------------------------------- causeway (Bai Di) + Broken Bridge
BR_Y = 78.0
BR_X0, BR_X1 = -27.0, -9.0          # bridge ends
def land_strip(name, x0, x1, y0, y1, h=0.7, seed=0):
    nx, ny = 120, 10
    verts, faces = [], []
    for j in range(ny):
        v = j / (ny - 1)
        for i in range(nx):
            u = i / (nx - 1)
            x = x0 + u * (x1 - x0)
            y = y0 + v * (y1 - y0)
            edge = math.sin(v * math.pi) ** 0.35
            endf = smoothstep(x1, x1 - 6, x) if x1 > x0 else 1
            z = (h + noise.noise(Vector((x * 0.3, y * 0.3, seed))) * 0.2) * edge * endf - 0.4 * (1 - edge)
            verts.append((x, y, z))
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    return mesh_obj(name, verts, faces, M_LAND, smooth=True)

land_strip("causeway_left", -520, BR_X0 + 1.0, BR_Y - 9, BR_Y + 9, seed=1)
land_strip("causeway_right", BR_X1 - 1.0, 4.0, BR_Y - 7, BR_Y + 7, h=0.6, seed=2)

def bridge():
    L0, L1 = BR_X0, BR_X1
    xc = (L0 + L1) / 2
    half = (L1 - L0) / 2
    a_span, a_rise = 4.6, 4.1
    W = 6.0
    def top(x):
        t = (x - xc) / half
        return 0.7 + 4.6 * (math.cos(t * math.pi / 2) ** 1.4)
    def bottom(x):
        dx = x - xc
        if abs(dx) < a_span:
            return a_rise * math.sqrt(max(0, 1 - (dx / a_span) ** 2)) - 0.6
        return -0.6
    N = 90
    xs = [L0 + (L1 - L0) * i / (N - 1) for i in range(N)]
    # snap sample to arch springing
    verts, faces = [], []
    for x in xs:
        for yy in (BR_Y - W / 2, BR_Y + W / 2):
            verts.append((x, yy, bottom(x)))
            verts.append((x, yy, top(x)))
    # index: i*4 + (0 front-bottom,1 front-top,2 back-bottom,3 back-top)
    for i in range(N - 1):
        a, b = i * 4, (i + 1) * 4
        faces.append((a, b, b + 1, a + 1))          # front
        faces.append((a + 2, a + 3, b + 3, b + 2))  # back
        faces.append((a + 1, b + 1, b + 3, a + 3))  # deck
        faces.append((a, a + 2, b + 2, b))          # underside
    faces.append((0, 1, 3, 2))
    e = (N - 1) * 4
    faces.append((e, e + 2, e + 3, e + 1))
    mesh_obj("DuanQiao", verts, faces, M_STONE)
    # parapets + posts
    for side in (-1, 1):
        yy = BR_Y + side * (W / 2 - 0.15)
        pv, pf = [], []
        for i, x in enumerate(xs):
            z = top(x)
            pv += [(x, yy - 0.14, z), (x, yy + 0.14, z), (x, yy + 0.14, z + 0.75), (x, yy - 0.14, z + 0.75)]
        for i in range(N - 1):
            a, b = i * 4, (i + 1) * 4
            for k in range(4):
                pf.append((a + k, b + k, b + (k + 1) % 4, a + (k + 1) % 4))
        mesh_obj(f"parapet{side}", pv, pf, M_STONE)
        for i in range(0, N, 9):
            x = xs[i]
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, yy, top(x) + 0.55))
            o = bpy.context.active_object
            o.scale = (0.32, 0.32, 1.1)
            o.data.materials.append(M_STONE)
    # arch ring stones (voussoir rim) - slightly proud band
    rv, rf = [], []
    M = 40
    for side in (-1, 1):
        yy = BR_Y + side * (W / 2 + 0.06)
        base = len(rv)
        for k in range(M + 1):
            t = math.pi * k / M
            for rr in (1.0, 1.12):
                rv.append((xc - math.cos(t) * a_span * rr, yy, math.sin(t) * (a_rise * rr) - 0.6))
        for k in range(M):
            a = base + k * 2
            rf.append((a, a + 2, a + 3, a + 1))
    mesh_obj("arch_rim", rv, rf, M_STONE)

bridge()

# causeway trees: alternating willows and camphor
rnd = random.Random(3)
x = BR_X0 - 4
k = 0
while x > -520:
    y = BR_Y + rnd.uniform(-6, 6)
    if k % 3 != 2:
        willow(f"cw_willow{k}", (x, y, 0.5), rnd.uniform(5.5, 7.0), rnd.uniform(5, 6.5), 380, 5.8, 0.55, 2,
               M_WILLOW_FAR, seed=100 + k, step=0.3)
    else:
        round_tree(f"cw_tree{k}", (x, y + rnd.uniform(2, 5), rnd.uniform(5, 7)), rnd.uniform(4, 6), k)
    x -= rnd.uniform(9, 16)
    k += 1
for j, xx in enumerate((BR_X1 + 3, BR_X1 + 9)):
    willow(f"cr_willow{j}", (xx, BR_Y + 1.5 * (-1) ** j, 0.4), rnd.uniform(5, 6.5), 5.0, 380, 5.4, 0.5, 2,
           M_WILLOW_FAR, seed=300 + j, step=0.28)

# far-shore tree band under Leifeng (silhouette fringe at the waterline)
for i in range(70):
    xx = rnd.uniform(-60, 700)
    yy = rnd.uniform(880, 900) + xx * 0.02
    round_tree(f"shore_tree{i}", (xx, yy, rnd.uniform(4, 9)), rnd.uniform(6, 11), 500 + i)

# ---------------------------------------------------------------- 三潭印月 stone lanterns
def stone_lantern(name, loc, s=1.0):
    objs = []
    def prim(fn, mat, **kw):
        fn(**kw)
        o = bpy.context.active_object
        o.data.materials.append(mat)
        objs.append(o)
        return o
    prim(bpy.ops.mesh.primitive_cylinder_add, M_STONE, vertices=24, radius=0.42, depth=1.4, location=(0, 0, 0.1))
    prim(bpy.ops.mesh.primitive_cylinder_add, M_STONE, vertices=24, radius=0.55, depth=0.12, location=(0, 0, 0.82))
    sph = prim(bpy.ops.mesh.primitive_uv_sphere_add, M_STONE, segments=32, ring_count=16, radius=0.62,
               location=(0, 0, 1.38))
    sph.scale.z = 0.82
    prim(bpy.ops.mesh.primitive_cylinder_add, M_STONE, vertices=24, radius=0.78, depth=0.1, location=(0, 0, 1.92))
    prim(bpy.ops.mesh.primitive_cone_add, M_STONE, vertices=24, radius1=0.7, radius2=0.12, depth=0.22,
         location=(0, 0, 2.08))
    prim(bpy.ops.mesh.primitive_uv_sphere_add, M_STONE, segments=16, ring_count=8, radius=0.2, location=(0, 0, 2.35))
    prim(bpy.ops.mesh.primitive_uv_sphere_add, M_STONE, segments=16, ring_count=8, radius=0.13, location=(0, 0, 2.62))
    prim(bpy.ops.mesh.primitive_cone_add, M_STONE, vertices=12, radius1=0.06, radius2=0.0, depth=0.3,
         location=(0, 0, 2.86))
    for k in range(5):
        a = 2 * math.pi * k / 5 - math.pi / 2
        o = prim(bpy.ops.mesh.primitive_cylinder_add, M_EMBER, vertices=16, radius=0.085, depth=0.1,
                 location=(math.cos(a) * 0.6, math.sin(a) * 0.6, 1.4))
        o.rotation_euler = (0, math.pi / 2, a)
    parent = bpy.data.objects.new(name, None)
    link(parent)
    for o in objs:
        o.parent = parent
    parent.location = loc
    parent.scale = (s, s, s)
    return parent

for i, (lx, ly) in enumerate(((20, 150), (34, 170), (47, 156))):
    stone_lantern(f"santan{i}", (lx, ly, 0), 1.5)

# ---------------------------------------------------------------- boat (乌篷船)
def boat(loc, rot):
    Lh = 2.7
    NS, NJ = 28, 12
    verts, faces = [], []
    for i in range(NS):
        x = -Lh + 2 * Lh * i / (NS - 1)
        t = x / Lh
        w = 0.68 * max(0.02, (1 - abs(t) ** 2.4)) ** 0.6
        sheer = 0.38 + 0.28 * t ** 2
        depth = 0.48 * (1 - t ** 2) + 0.06
        for j in range(NJ):
            a = -math.pi / 2 + math.pi * j / (NJ - 1)
            verts.append((x, w * math.sin(a), sheer - depth * math.cos(a) ** 0.8))
    for i in range(NS - 1):
        for j in range(NJ - 1):
            a = i * NJ + j
            faces.append((a, a + NJ, a + NJ + 1, a + 1))
    hull = mesh_obj("boat_hull", verts, faces, M_HULL, smooth=True)
    sm = hull.modifiers.new("s", "SOLIDIFY")
    sm.thickness = 0.04
    # canopy arc
    cv, cf = [], []
    NA = 14
    x0, x1 = -0.9, 0.85
    for i, x in enumerate((x0, x1)):
        for j in range(NA):
            a = math.pi * j / (NA - 1)
            cv.append((x, 0.66 * math.cos(a), 0.40 + 0.62 * math.sin(a)))
    for j in range(NA - 1):
        cf.append((j, j + 1, NA + j + 1, NA + j))
    can = mesh_obj("boat_canopy", cv, cf, M_CANOPY, smooth=True)
    can.modifiers.new("s", "SOLIDIFY").thickness = 0.04
    # small rear canopy
    cv2 = [(x - 1.85, y * 0.85, (z - 0.4) * 0.8 + 0.42) for (x, y, z) in cv[:NA]] + \
          [(x - 1.85 + 0.75, y * 0.85, (z - 0.4) * 0.8 + 0.42) for (x, y, z) in cv[:NA]]
    can2 = mesh_obj("boat_canopy2", cv2, cf, M_CANOPY, smooth=True)
    can2.modifiers.new("s", "SOLIDIFY").thickness = 0.04
    # lantern on a pole at stern
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.02, depth=1.6, location=(-2.2, 0, 1.2))
    pole = bpy.context.active_object
    pole.data.materials.append(M_TWIG)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.16, location=(-2.2, 0.0, 1.85))
    lan = bpy.context.active_object
    lan.scale.z = 1.25
    lan.data.materials.append(M_LANTERN)
    lt = bpy.data.lights.new("lantern_light", "POINT")
    lt.energy = 60
    lt.color = (1.0, 0.45, 0.2)
    lt.shadow_soft_size = 0.15
    lto = link(bpy.data.objects.new("lantern_light", lt))
    lto.location = (-2.2, 0, 1.85)
    # oar
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.025, depth=3.2, location=(-2.9, 0.25, 0.4))
    oar = bpy.context.active_object
    oar.rotation_euler = (0, math.radians(62), math.radians(8))
    oar.data.materials.append(M_TWIG)
    parts = [hull, can, can2, pole, lan, lto, oar]
    # boatman at the stern: robe, head, conical bamboo hat (斗笠)
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.26, radius2=0.15, depth=1.25, location=(-1.75, 0.05, 0.95))
    body = bpy.context.active_object; body.data.materials.append(M_CANOPY); parts.append(body)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.11, location=(-1.75, 0.05, 1.67))
    head = bpy.context.active_object; head.data.materials.append(M_CANOPY); parts.append(head)
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.36, radius2=0.0, depth=0.2, location=(-1.75, 0.05, 1.79))
    hat = bpy.context.active_object; hat.data.materials.append(M_HAT); parts.append(hat)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.05, depth=0.6, location=(-1.95, 0.22, 1.2))
    arm = bpy.context.active_object; arm.rotation_euler = (0.3, 0.9, 0); arm.data.materials.append(M_CANOPY); parts.append(arm)
    parent = bpy.data.objects.new("Boat", None)
    link(parent)
    for o in parts:
        o.parent = parent
    parent.location = loc
    parent.rotation_euler.z = rot
    return parent

DOC = "doc" in ARGS
if not DOC:
    BOAT = boat((7.5, 42, -0.05), math.radians(-18))

# ---------------------------------------------------------------- lotus (foreground right)
def lotus_leaf(c, r, cup, tilt, mat, seed):
    rnd = random.Random(seed)
    NR, NA = 6, 28
    notch = rnd.uniform(0, 2 * math.pi)
    verts = [(0, 0, 0)]
    for i in range(1, NR + 1):
        d = i / NR
        for j in range(NA):
            a = 2 * math.pi * j / NA
            # small V notch
            da = (a - notch + math.pi) % (2 * math.pi) - math.pi
            rr = r * d * (1 - 0.18 * math.exp(-(da / 0.18) ** 2) * d)
            wav = (0.035 + 0.06 * (cup > 0.1)) * r * math.sin(a * 7 + seed * 1.7) * d ** 3
            droop = 0.0
            verts.append((rr * math.cos(a), rr * math.sin(a), cup * r * d ** 2 - droop * d ** 5 + wav))
    faces = [(0, 1 + j, 1 + (j + 1) % NA) for j in range(NA)]
    for i in range(NR - 1):
        for j in range(NA):
            a = 1 + i * NA + j
            b = 1 + i * NA + (j + 1) % NA
            faces.append((a, a + NA, b + NA, b))
    ob = mesh_obj("lotus_leaf", verts, faces, mat, smooth=True)
    ob.location = c
    ob.rotation_euler = (tilt[0], tilt[1], rnd.uniform(0, 6.28))
    return ob

rl = random.Random(21)
placed = []
for i in range(150):
    for _ in range(30):
        x = rl.uniform(1.2, 12.0)
        y = rl.uniform(3.0, 30)
        # keep a clear channel toward the boat / lanterns
        if x < 1.9 + (y - 3.0) * 0.2:
            continue
        r = rl.uniform(0.16, 0.34) * (1 + y / 25)
        if all((Vector((x, y)) - Vector(p[:2])).length > (r + p[2]) * 0.85 for p in placed):
            break
    placed.append((x, y, r))
    raised = rl.random() < 0.09
    z = rl.uniform(0.12, 0.42) if raised else 0.01
    cup = rl.uniform(0.18, 0.32) if raised else rl.uniform(0.0, 0.05)
    tilt = (rl.uniform(-0.35, 0.35), rl.uniform(-0.35, 0.35)) if raised else (0, 0)
    mat = M_LOTUS_OLD if rl.random() < 0.08 else M_LOTUS
    lotus_leaf((x, y, z), r, cup, tilt, mat, 1000 + i)
    if raised:
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.012, depth=z, location=(x, y, z / 2))
        bpy.context.active_object.data.materials.append(M_STEM)
# a few buds
for (x, y, h) in (() if DOC else ((4.6, 7.5, 0.55), (7.4, 13.0, 0.7))):
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.008, depth=h, location=(x, y, h / 2))
    bpy.context.active_object.data.materials.append(M_STEM)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=0.05, location=(x, y, h + 0.05))
    b = bpy.context.active_object
    b.scale.z = 1.7
    sk = b.modifiers.new("t", "SIMPLE_DEFORM")
    sk.deform_method = "TAPER"
    sk.factor = -0.9
    sk.deform_axis = "Z"
    b.data.materials.append(M_BUD)

# ---------------------------------------------------------------- atmosphere volume
def fog_volume():
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 1600, 220))
    v = bpy.context.active_object
    v.name = "Atmosphere"
    v.scale = (7000, 3600, 440)
    m = bpy.data.materials.new("mist")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    out = nt.nodes["Material Output"]
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.80, 0.88, 1.0, 1)
    vol.inputs["Anisotropy"].default_value = 0.7
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    def math_node(op, a=None, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if a is not None and not isinstance(a, bpy.types.NodeSocket):
            n.inputs[0].default_value = a
        elif a is not None:
            nt.links.new(a, n.inputs[0])
        if b is not None and not isinstance(b, bpy.types.NodeSocket):
            n.inputs[1].default_value = b
        elif b is not None:
            nt.links.new(b, n.inputs[1])
        return n.outputs[0]
    z = sep.outputs["Z"]
    # thin haze, falls off slowly with altitude
    haze = math_node("MULTIPLY", math_node("EXPONENT", math_node("MULTIPLY", z, -1 / 160)), 0.00038)
    # ground mist hugging the water, broken up by noise
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 0.018
    nz.inputs["Detail"].default_value = 3
    nz.inputs["Roughness"].default_value = 0.55
    nz.name = "mistnoise"
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    nz.inputs["W"].driver_add("default_value").driver.expression = "frame*0.004"
    shape = nt.nodes.new("ShaderNodeMapRange")
    shape.inputs["From Min"].default_value = 0.42
    shape.inputs["From Max"].default_value = 0.68
    shape.inputs["To Min"].default_value = 0.15
    shape.inputs["To Max"].default_value = 1.6
    nt.links.new(nz.outputs["Fac"], shape.inputs["Value"])
    ground = math_node("MULTIPLY", math_node("EXPONENT", math_node("MULTIPLY", z, -1 / 3.5)), 0.0024)
    ground = math_node("MULTIPLY", ground, shape.outputs["Result"])
    dens = math_node("ADD", haze, ground)
    nt.links.new(dens, vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    v.data.materials.append(m)
    v.visible_shadow = True
    return v

# ---------------------------------------------------------------- egrets
BIRDS = []
def bird(name, loc, span, phase):
    wings = []
    for side in (-1, 1):
        v = [(0, 0, 0), (0.18 * span, side * 0.5 * span, 0.02), (-0.12 * span, side * 0.45 * span, 0), (-0.15 * span, 0, 0)]
        w = mesh_obj(f"{name}_w{side}", v, [(0, 1, 2, 3)], M_BIRD)
        wings.append((w, side))
    bv = [(0.35 * span, 0, 0.0), (0, 0.04 * span, 0), (-0.4 * span, 0, 0), (0, -0.04 * span, 0), (0, 0, 0.05 * span)]
    body = mesh_obj(name + "_b", bv, [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 3, 2, 1)], M_BIRD)
    par = bpy.data.objects.new(name, None); link(par)
    for w, side in wings:
        w.parent = par
    body.parent = par
    par.location = loc
    BIRDS.append((par, wings, phase))
    return par

rb = random.Random(5)
for i in range(0 if DOC else 5):
    bird(f"egret{i}", (38 + i * 5.5 + rb.uniform(-2, 2), 150 + rb.uniform(-12, 12), 12.5 + rb.uniform(-2.5, 3)), 1.6, rb.uniform(0, 6.28))
for par, wings, ph in BIRDS:
    for w, side in wings:
        w.rotation_euler.x = side * 0.35 * math.sin(ph)

ATM = fog_volume()
if "nofog" in ARGS:
    ATM.hide_render = True

# ---------------------------------------------------------------- camera
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 45
cam_d.sensor_width = 36
cam_d.dof.use_dof = True
cam_d.dof.focus_distance = 44
cam_d.dof.aperture_fstop = 4.0
cam_d.clip_end = 6000
cam = link(bpy.data.objects.new("Camera", cam_d))
cam.location = (0.4, 0.0, 1.35)
cam.rotation_euler = (math.radians(91.6), 0, math.radians(-4.5))
scene.camera = cam

# ---------------------------------------------------------------- render settings
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
DEVTYPE = os.environ.get("WL_DEVICE", "CUDA")
prefs.compute_device_type = DEVTYPE
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == DEVTYPE
scene.cycles.device = "GPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.02
scene.cycles.use_denoising = True
try:
    scene.cycles.denoiser = "OPTIX"
except Exception:
    pass
scene.cycles.max_bounces = 6
scene.cycles.volume_bounces = 1
scene.cycles.transparent_max_bounces = 8
for attr, val in (("volume_step_rate", 4.0), ("volume_max_steps", 256)):
    try:
        setattr(scene.cycles, attr, val)
    except Exception:
        pass
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = RESPCT
scene.view_settings.view_transform = "AgX"
print("LOOKS", [e.identifier for e in scene.view_settings.bl_rna.properties["look"].enum_items])
for look in ("AgX - Medium High Contrast", "Medium High Contrast", "AgX - Base Contrast"):
    try:
        scene.view_settings.look = look
        break
    except Exception:
        continue
scene.view_settings.exposure = -0.9
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "16"
scene.render.film_transparent = False
scene.frame_start, scene.frame_end = 1, 1

if "anim" in ARGS:

    # ---------------------------------------------------------------- animation
    FRAMES = 192
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1, FRAMES
    # wind field for willows
    wind = link(bpy.data.objects.new("Wind", None))
    wind.location = (0, 0, 0)
    wind.keyframe_insert("location", frame=1)
    wind.location = (2.2, 0.8, 0.4)
    wind.keyframe_insert("location", frame=FRAMES)
    for fc in (wind.animation_data.action.fcurves if hasattr(wind.animation_data.action, "fcurves") else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
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
    # boat drift along its heading
    bt = scene.objects["Boat"]
    h = bt.rotation_euler.z
    for ax, comp in ((0, math.cos(h)), (1, math.sin(h))):
        d = bt.driver_add("location", ax).driver
        d.expression = f"{bt.location[ax]:.4f} + frame*{0.013 * comp:.5f}"
    dz = bt.driver_add("rotation_euler", 1).driver
    dz.expression = "0.012*sin(frame*0.11)"
    # egrets: glide left, flap
    for par, wings, ph in BIRDS:
        x0, z0 = par.location.x, par.location.z
        par.driver_add("location", 0).driver.expression = f"{x0:.3f} - frame*0.20"
        par.driver_add("location", 2).driver.expression = f"{z0:.3f} + 0.35*sin(frame*0.05+{ph:.2f})"
        par.rotation_euler.z = math.pi
        for w, side in wings:
            w.driver_add("rotation_euler", 0).driver.expression = f"{side}*0.55*sin(frame*0.62+{ph:.2f})"
    # camera: slow push-in with a gentle rise
    cam.location = (0.55, -3.2, 1.22)
    cam.rotation_euler = (math.radians(91.2), 0, math.radians(-3.6))
    cam.keyframe_insert("location", frame=1)
    cam.keyframe_insert("rotation_euler", frame=1)
    cam.location = (0.35, 1.2, 1.42)
    cam.rotation_euler = (math.radians(91.9), 0, math.radians(-5.0))
    cam.keyframe_insert("location", frame=FRAMES)
    cam.keyframe_insert("rotation_euler", frame=FRAMES)
    scene.render.use_persistent_data = True
DOC_DONE = False
if DOC:
    exec(open(os.path.join(HERE, "doc_shots.py"), encoding="utf-8").read())
print("SKY sun_direction", tuple(sky.sun_direction) if hasattr(sky, "sun_direction") else None,
      "wanted", tuple(sun_vec))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "westlake.blend"))
if DOC_DONE:
    pass
elif OUT and "anim" in ARGS and "frame" not in ARGS:
    scene.render.filepath = OUT
    if len(ARGS) > 5 and ARGS[4].isdigit():
        scene.frame_start, scene.frame_end = int(ARGS[4]), int(ARGS[5])
    bpy.ops.render.render(animation=True)
elif OUT:
    if "frame" in ARGS:
        scene.frame_set(int(ARGS[ARGS.index("frame") + 1]))
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
    print("RENDERED", OUT)
