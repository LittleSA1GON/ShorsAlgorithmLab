"""
scenes.py — procedural Blender scenes for the Shor's-algorithm explainer.

Works two ways:
  * pip-installed bpy:   python scenes.py <scene|all> <out_dir> [--frames 72] [--preview]
  * Blender itself:      blender -b -P scenes.py -- <scene|all> <out_dir>

Scenes (each renders a short PNG sequence that the web page scrubs with scroll):
  rsa            two primes fuse into a semiprime N, then a cloud of candidate factors searches it
  clock          a^x mod N on a 15-hour clock: 1 -> 2 -> 4 -> 8 -> 1, period r = 4
  superposition  Hadamards spread one state into 16; controlled-U tags each with a^x mod N
  interference   inverse QFT: a periodic comb interferes into a few sharp peaks
  measure        one peak survives; y/2^t = 1/4 -> r = 4 -> 15 = 3 x 5
  lattice        post-quantum: a skewed lattice and a noisy target point (learning with errors)
"""
from __future__ import annotations

import math
import os
import sys

import bpy
from mathutils import Vector

# --------------------------------------------------------------------------- palette (linear sRGB)
def srgb(h: str, a: float = 1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, a)

BG      = srgb("#0e1320")
FLOOR   = srgb("#141b2b")
SLATE   = srgb("#3b4660")
INK     = srgb("#dfe5f0")
QUANT   = srgb("#5cc8d6")   # quantum / cyan
CLASS   = srgb("#e2a65a")   # classical / amber
ROSE    = srgb("#d9738a")
VIOLET  = srgb("#9a8ae0")
GREEN   = srgb("#7cc79a")
RESIDUE = [QUANT, CLASS, VIOLET, GREEN]  # colors for a^x mod N values

FONT_PATHS = ["/usr/share/fonts/opentype/inter/Inter-Medium.otf",
              "C:/Windows/Fonts/segoeui.ttf", "/System/Library/Fonts/SFNS.ttf"]

FRAMES = 72


# --------------------------------------------------------------------------- helpers
def reset():
    global _font
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _font = None
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, FRAMES
    sc.render.fps = 24
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bgn = world.node_tree.nodes["Background"]
    bgn.inputs["Color"].default_value = BG
    bgn.inputs["Strength"].default_value = 1.0
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium Low Contrast"
    except Exception:
        pass
    return sc


def mat(name, color, emit=0.0, rough=0.45, metal=0.0, emit_color=None, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Emission Color"].default_value = emit_color or color
    b.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m


def bsdf(m):
    return m.node_tree.nodes.get("Principled BSDF")


def key(obj_or_input, path, frame, value=None):
    if value is not None:
        setattr(obj_or_input, path, value) if not isinstance(value, (tuple, list)) or path != "default_value" \
            else setattr(obj_or_input, path, value)
    obj_or_input.keyframe_insert(path, frame=frame)


def kv(target, path, pairs):
    """Keyframe a property through [(frame, value), ...]."""
    for f, v in pairs:
        setattr(target, path, v)
        target.keyframe_insert(path, frame=f)


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def sphere(name, loc, r, m, seg=48):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=seg // 2)
    o = bpy.context.object
    o.name = name
    bpy.ops.object.shade_smooth()
    o.data.materials.append(m)
    return o


def box(name, loc, size, m, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    if bevel:
        mod = o.modifiers.new("bev", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.affect = "EDGES"
    o.data.materials.append(m)
    return o


_font = None
def font():
    global _font
    if _font is None:
        for p in FONT_PATHS:
            if os.path.exists(p):
                _font = bpy.data.fonts.load(p)
                break
    return _font


def text(name, body, loc, size, m, rot=(math.radians(90), 0, 0), align="CENTER"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    if font():
        cu.font = font()
    o = link(bpy.data.objects.new(name, cu))
    o.location = loc
    o.rotation_euler = rot
    o.data.materials.append(m)
    return o


def floor(z=0.0, size=400):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    o = bpy.context.object
    o.name = "floor"
    o.data.materials.append(mat("floor", FLOOR, rough=0.32))
    return o


def camera(loc, look_at, lens=40):
    cam = link(bpy.data.objects.new("cam", bpy.data.cameras.new("cam")))
    cam.data.lens = lens
    cam.location = loc
    target = link(bpy.data.objects.new("cam_target", None))
    target.location = look_at
    c = cam.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    bpy.context.scene.camera = cam
    cam.data.dof.use_dof = False
    return cam, target


def area_light(loc, energy, size=6, color=(1, 1, 1)):
    l = bpy.data.lights.new("key", "AREA")
    l.energy, l.size, l.color = energy, size, color
    o = link(bpy.data.objects.new("key", l))
    o.location = loc
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    o.visible_camera = False      # soft light only; never a bright card in frame
    o.visible_glossy = False
    return o


def lights():
    area_light((-5, -6, 8), 900, 8, (0.95, 0.97, 1.0))
    area_light((7, 3, 6), 350, 6, (0.85, 0.92, 1.0))
    area_light((0, 9, 3), 250, 10, (0.7, 0.85, 1.0))


def ease_all():
    """Ease every F-curve (smooth starts and stops)."""
    def curves_of(anim):
        act = anim.action if anim else None
        if not act:
            return []
        if hasattr(act, "fcurves"):
            try:
                return list(act.fcurves)
            except Exception:
                pass
        out = []
        for layer in getattr(act, "layers", []):
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    out += list(bag.fcurves)
        return out
    holders = list(bpy.data.objects) + list(bpy.data.materials) + list(bpy.data.curves)
    for h in holders:
        ad = getattr(h, "animation_data", None)
        if h.__class__.__name__ == "Material" and h.node_tree:
            ad2 = h.node_tree.animation_data
        else:
            ad2 = None
        for fc in curves_of(ad) + curves_of(ad2):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "AUTO"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------- scenes
def scene_rsa():
    sc = reset(); floor(-1.4); lights()
    cam, tgt = camera((0, -11, 3.2), (0, 0, 0.2), lens=42)
    kv(cam, "location", [(1, (0.6, -11.5, 3.0)), (FRAMES, (-0.6, -9.6, 3.6))])
    am = mat("amber", CLASS, emit=0.35, rough=0.3)
    p = sphere("p", (-3.0, 0, 0.3), 0.75, am)
    q = sphere("q", (3.0, 0, 0.3), 0.95, am)
    nm = mat("N", SLATE, emit=0.12, rough=0.25, metal=0.5, emit_color=QUANT)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0, location=(0, 0, 0.3))
    N = bpy.context.object; N.name = "N"; N.data.materials.append(nm)
    ink = mat("ink", INK, emit=1.2)
    tp = text("tp", "p", (-3.0, 0, 1.55), 0.55, ink)
    tq = text("tq", "q", (3.0, 0, 1.75), 0.55, ink)
    tN = text("tN", "N = p × q", (0, 0, 2.2), 0.5, ink)
    # p, q drift together and fuse
    kv(p, "location", [(1, (-3.0, 0, 0.3)), (8, (-3.0, 0, 0.3)), (30, (-0.2, 0, 0.3))])
    kv(q, "location", [(1, (3.0, 0, 0.3)), (8, (3.0, 0, 0.3)), (30, (0.2, 0, 0.3))])
    for o in (p, q):
        kv(o, "scale", [(1, (1, 1, 1)), (24, (1, 1, 1)), (32, (0.01, 0.01, 0.01))])
    for o in (tp, tq):
        kv(o, "scale", [(1, (1, 1, 1)), (16, (1, 1, 1)), (24, (0.001, 0.001, 0.001))])
    kv(N, "scale", [(1, (0.001,) * 3), (24, (0.001,) * 3), (36, (1.35,) * 3)])
    kv(N, "rotation_euler", [(24, (0, 0, 0)), (FRAMES, (0.3, 0.2, 1.4))])
    kv(tN, "scale", [(1, (0.001,) * 3), (32, (0.001,) * 3), (40, (1, 1, 1))])
    kv(tN, "location", [(32, (0, 0, 2.2)), (40, (0, 0, 2.4))])
    # candidate factors: a ring of small dim probes that sweep around N ("trial division")
    pm = mat("probe", SLATE, emit=0.0, rough=0.5)
    hit = bsdf(pm).inputs["Emission Strength"]
    kv(hit, "default_value", [(40, 0.0), (52, 0.6), (FRAMES, 0.25)])
    count = 36
    for i in range(count):
        ang = 2 * math.pi * i / count
        o = sphere(f"probe{i}", (0, 0, 0.3), 0.09, pm, seg=16)
        r0, r1 = 1.6, 2.6 + 0.25 * math.sin(i * 1.7)
        z = 0.3 + 0.6 * math.sin(i * 2.3)
        kv(o, "location", [(1, (0, 0, 0.3)), (40, (0, 0, 0.3)),
                           (54, (r1 * math.cos(ang), r1 * math.sin(ang), z)),
                           (FRAMES, (r0 * 1.4 * math.cos(ang + 0.9), r0 * 1.4 * math.sin(ang + 0.9), z * 0.8))])
        kv(o, "scale", [(1, (0.001,) * 3), (40, (0.001,) * 3), (48, (1, 1, 1))])
    return sc


def scene_clock():
    sc = reset(); floor(-0.3); lights()
    cam, tgt = camera((0, -9.5, 9.0), (0, 0.0, 0.3), lens=34)
    kv(cam, "location", [(1, (-0.8, -10.2, 9.6)), (FRAMES, (0.8, -9.0, 8.6))])
    N, seq = 15, [1, 2, 4, 8, 1]
    R = 3.1
    def pos(k, z=0.0):
        ang = math.pi / 2 - 2 * math.pi * k / N
        return Vector((R * math.cos(ang), R * math.sin(ang), z))
    ring = mat("ring", SLATE, rough=0.4)
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=0.025, location=(0, 0, 0))
    bpy.context.object.data.materials.append(ring)
    ink_dim = mat("inkdim", INK, emit=0.35)
    beads = []
    for k in range(N):
        m = mat(f"bead{k}", SLATE, emit=0.0, rough=0.35)
        b = sphere(f"bead{k}", pos(k), 0.2, m, seg=24)
        beads.append((b, m))
        lp = pos(k) * 1.2
        text(f"lab{k}", str(k), (lp.x, lp.y, 0.02), 0.32, ink_dim, rot=(0, 0, 0))
    traveler = sphere("trav", pos(1, 0.2), 0.16, mat("trav", QUANT, emit=4.0), seg=24)
    hop = 12
    start = 6
    tm = mat("trail", QUANT, emit=2.2)
    for i in range(4):
        a, b = seq[i], seq[i + 1]
        f0, f1 = start + i * hop, start + (i + 1) * hop
        # arc trail as a bezier curve
        cu = bpy.data.curves.new(f"arc{i}", "CURVE")
        cu.dimensions = "3D"; cu.bevel_depth = 0.03; cu.bevel_resolution = 4
        spl = cu.splines.new("BEZIER"); spl.bezier_points.add(1)
        pa, pb = pos(a, 0.2), pos(b, 0.2)
        mid = (pa + pb) / 2; lift = 0.6 + 0.5 * (pa - pb).length / (2 * R)
        for bp, pt in zip(spl.bezier_points, (pa, pb)):
            bp.co = pt
            bp.handle_left_type = bp.handle_right_type = "FREE"
        spl.bezier_points[0].handle_right = pa + (mid - pa) * 0.6 + Vector((0, 0, lift * 1.6))
        spl.bezier_points[0].handle_left = pa
        spl.bezier_points[1].handle_left = pb + (mid - pb) * 0.6 + Vector((0, 0, lift * 1.6))
        spl.bezier_points[1].handle_right = pb
        arc = link(bpy.data.objects.new(f"arc{i}", cu)); arc.data.materials.append(tm)
        kv(cu, "bevel_factor_end", [(f0, 0.0), (f1, 1.0)])
        # traveler follows the arc (sampled)
        for s in range(0, hop + 1, 2):
            u = smooth(s / hop)
            p0, p1, p2, p3 = pa, spl.bezier_points[0].handle_right, spl.bezier_points[1].handle_left, pb
            pt = (1 - u) ** 3 * p0 + 3 * (1 - u) ** 2 * u * p1 + 3 * (1 - u) * u ** 2 * p2 + u ** 3 * p3
            traveler.location = pt; traveler.keyframe_insert("location", frame=f0 + s)
        # light up the destination bead
        if b == seq[0]:
            continue                      # back at the start bead, already lit
        bm = beads[b][1]
        e = bsdf(bm).inputs["Emission Strength"]; c = bsdf(bm).inputs["Emission Color"]
        c.default_value = QUANT
        kv(e, "default_value", [(1, 0.0), (f1 - 2, 0.0), (f1 + 2, 2.4)])
        kv(bsdf(bm).inputs["Base Color"], "default_value", [(1, SLATE), (f1 - 2, SLATE), (f1 + 2, QUANT)])
    b1 = beads[1][1]
    bsdf(b1).inputs["Base Color"].default_value = QUANT
    kv(bsdf(b1).inputs["Emission Strength"], "default_value", [(1, 2.4)])
    tr = text("r", "r = 4", (0, 0, 0.05), 0.9, mat("inkr", INK, emit=1.4), rot=(0, 0, 0))
    kv(tr, "scale", [(1, (0.001,) * 3), (start + 4 * hop, (0.001,) * 3), (start + 4 * hop + 8, (1, 1, 1))])
    return sc


def scene_superposition():
    sc = reset(); floor(0.0); lights()
    cam, tgt = camera((0, -13, 4.4), (0, 0, 1.1), lens=34)
    kv(cam, "location", [(1, (0, -13.0, 4.3)), (FRAMES, (0, -12.2, 4.8))])   # steady: easy to follow
    M, a, N = 16, 2, 15
    vals = [pow(a, x, N) for x in range(M)]
    order = {v: i for i, v in enumerate(dict.fromkeys(vals))}   # 1,2,4,8 -> 0..3
    gap = 0.62
    H0, Hs = 3.2, 3.2 / 4   # amplitude 1 -> 1/sqrt(16)
    ink_dim = mat("inkdim", INK, emit=0.3)
    for x in range(M):
        X = (x - (M - 1) / 2) * gap
        m = mat(f"bar{x}", QUANT, emit=0.6, rough=0.35)
        bar = box(f"bar{x}", (X, 0, 0), (0.42, 0.42, 1.0), m)
        # origin at the bottom so scaling grows upward
        bar.data.transform(__import__("mathutils").Matrix.Translation((0, 0, 0.5)))
        h_start = H0 if x == 0 else 0.02
        kv(bar, "scale", [(1, (0.42, 0.42, h_start)), (10, (0.42, 0.42, h_start)),
                          (22 + x, (0.42, 0.42, Hs))])
        col = RESIDUE[order[vals[x]]]
        bc, ec = bsdf(m).inputs["Base Color"], bsdf(m).inputs["Emission Color"]
        f = 40 + 2 * x
        kv(bc, "default_value", [(1, QUANT), (f, QUANT), (f + 6, col)])
        kv(ec, "default_value", [(1, QUANT), (f, QUANT), (f + 6, col)])
        # work-register token floats above, carrying a^x mod N
        tok = sphere(f"tok{x}", (X, 0, Hs + 0.55), 0.17, mat(f"tok{x}", col, emit=1.6), seg=20)
        kv(tok, "scale", [(1, (0.001,) * 3), (f, (0.001,) * 3), (f + 6, (1, 1, 1))])
        tv = text(f"tv{x}", str(vals[x]), (X, -0.02, Hs + 1.05), 0.26, ink_dim)
        kv(tv, "scale", [(1, (0.001,) * 3), (f + 2, (0.001,) * 3), (f + 8, (1, 1, 1))])
        text(f"x{x}", str(x), (X, -0.6, 0.02), 0.24, ink_dim, rot=(0, 0, 0))
    return sc


def qft_probs(M=64, r=4, x0=0):
    import cmath
    xs = [x for x in range(M) if x % r == x0]
    out = []
    for y in range(M):
        s = sum(cmath.exp(-2j * math.pi * x * y / M) for x in xs) / M
        out.append(abs(s) ** 2 * M / len(xs) * len(xs) / M)  # P(y | value class)
    tot = sum(out)
    return [o / tot for o in out]


def scene_interference():
    sc = reset(); floor(0.0); lights()
    cam, tgt = camera((0, -13.5, 4.4), (0, 0, 1.0), lens=34)
    kv(cam, "location", [(1, (0, -13.6, 4.3)), (FRAMES, (0, -12.8, 4.8))])   # steady, row fills frame
    M, r = 64, 4
    final = qft_probs(M, r)
    comb = [1 / (M // r) if x % r == 0 else 0 for x in range(M)]
    scale = 9.0
    gap = 0.2
    import mathutils
    for x in range(M):
        X = (x - (M - 1) / 2) * gap
        is_peak = final[x] > 1e-6
        m = mat(f"b{x}", QUANT, emit=0.5, rough=0.35)
        bar = box(f"b{x}", (X, 0, 0), (0.14, 0.3, 1), m, bevel=0.01)
        bar.data.transform(mathutils.Matrix.Translation((0, 0, 0.5)))
        h0 = max(0.02, comb[x] * scale * 1.6)
        h1 = max(0.02, final[x] * scale)
        # the wave of interference sweeps left -> right
        f = 18 + int(30 * x / M)
        kv(bar, "scale", [(1, (0.14, 0.3, h0)), (f, (0.14, 0.3, h0)),
                          (f + 6, (0.14, 0.3, (h0 + h1) / 2 + (0.35 if is_peak else 0.0))),
                          (f + 12, (0.14, 0.3, h1))])
        if is_peak:
            ec = bsdf(m).inputs["Emission Strength"]
            kv(ec, "default_value", [(1, 0.5), (f + 6, 0.5), (f + 14, 2.4)])
    # sinusoid ribbon showing the hidden period
    cu = bpy.data.curves.new("wave", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.025
    spl = cu.splines.new("POLY"); n = 256; spl.points.add(n - 1)
    for i in range(n):
        x = i / (n - 1) * (M - 1)
        X = (x - (M - 1) / 2) * gap
        spl.points[i].co = (X, 0.6, 2.4 + 0.45 * math.cos(2 * math.pi * x / (M / r)), 1)
    w = link(bpy.data.objects.new("wave", cu)); w.data.materials.append(mat("wave", VIOLET, emit=1.6))
    kv(cu, "bevel_factor_end", [(1, 0.0), (14, 0.0), (52, 1.0)])
    kv(w, "location", [(50, (0, 0, 0)), (FRAMES, (0, 0, 0.6))])
    return sc


def scene_measure():
    sc = reset(); floor(0.0); lights()
    cam, tgt = camera((0, -15, 5.0), (0, 0, 1.2), lens=30)
    kv(cam, "location", [(1, (0, -15.5, 5.0)), (FRAMES, (0, -12.5, 4.4))])
    kv(tgt, "location", [(1, (0, 0, 1.2)), (40, (0, 0, 1.2)), (FRAMES, (-2.0, 0, 1.6))])
    M, r, chosen = 64, 4, 16
    final = qft_probs(M, r)
    gap, scale = 0.2, 9.0
    import mathutils
    for x in range(M):
        X = (x - (M - 1) / 2) * gap
        m = mat(f"b{x}", QUANT, emit=2.4 if final[x] > 1e-6 else 0.5, rough=0.35)
        bar = box(f"b{x}", (X, 0, 0), (0.14, 0.3, 1), m, bevel=0.01)
        bar.data.transform(mathutils.Matrix.Translation((0, 0, 0.5)))
        h = max(0.02, final[x] * scale)
        if x == chosen:
            kv(bar, "scale", [(1, (0.14, 0.3, h)), (14, (0.14, 0.3, h)), (24, (0.22, 0.4, 4.0))])
            bc = bsdf(m).inputs["Emission Color"]; bb = bsdf(m).inputs["Base Color"]
            kv(bc, "default_value", [(14, QUANT), (24, CLASS)]); kv(bb, "default_value", [(14, QUANT), (24, CLASS)])
        else:
            kv(bar, "scale", [(1, (0.14, 0.3, h)), (12, (0.14, 0.3, h)), (22, (0.14, 0.3, 0.02))])
    X = (chosen - (M - 1) / 2) * gap
    ink = mat("ink", INK, emit=1.3)
    t1 = text("t1", "y = 16", (X, 0, 4.6), 0.42, ink)
    t2 = text("t2", "16 / 64 = 1 / 4   →   r = 4", (2.4, 0, 3.0), 0.42, ink)
    t3 = text("t3", "gcd(2² − 1, 15) = 3     gcd(2² + 1, 15) = 5", (2.4, 0, 2.2), 0.3, mat("ink2", INK, emit=0.8))
    for o, f in ((t1, 24), (t2, 34), (t3, 44)):
        kv(o, "scale", [(1, (0.001,) * 3), (f, (0.001,) * 3), (f + 8, (1, 1, 1))])
    am = mat("amber", CLASS, emit=0.5, rough=0.3)
    s3 = sphere("f3", (1.0, 0, 1.0), 0.45, am); s5 = sphere("f5", (3.8, 0, 1.0), 0.58, am)
    ink3 = mat("ink3", INK, emit=1.3)
    l3 = text("l3", "3", (1.0, -0.65, 1.0), 0.5, ink3); l5 = text("l5", "5", (3.8, -0.75, 1.0), 0.5, ink3)
    for o in (s3, s5, l3, l5):
        kv(o, "scale", [(1, (0.001,) * 3), (54, (0.001,) * 3), (64, (1, 1, 1))])
    return sc


def scene_lattice():
    sc = reset(); lights()
    cam, tgt = camera((0, -12, 5), (0, 0, 0), lens=38)
    for i, f in enumerate(range(1, FRAMES + 1, 6)):
        ang = -math.pi / 2 + 0.9 * f / FRAMES
        cam.location = (12 * math.cos(ang), 12 * math.sin(ang), 5.2 - 1.2 * f / FRAMES)
        cam.keyframe_insert("location", frame=f)
    b1, b2, b3 = Vector((1.0, 0.25, 0.1)), Vector((0.45, 1.05, -0.15)), Vector((0.2, -0.3, 0.95))
    pm = mat("pt", SLATE, emit=0.45, rough=0.4, emit_color=srgb("#7f8db0"))
    for i in range(-4, 5):
        for j in range(-4, 5):
            for k in range(-1, 2):
                p = i * b1 + j * b2 + k * b3
                if p.length > 5.2:
                    continue
                o = sphere(f"p{i}{j}{k}", p, 0.07, pm, seg=12)
                d = int(p.length * 4)
                kv(o, "scale", [(1, (0.001,) * 3), (2 + d, (0.001,) * 3), (8 + d, (1, 1, 1))])
    # basis arrows
    for v, c, nm in ((b1, QUANT, "b1"), (b2, VIOLET, "b2"), (b3, GREEN, "b3")):
        cu = bpy.data.curves.new(nm, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.035
        spl = cu.splines.new("POLY"); spl.points.add(1)
        spl.points[0].co = (0, 0, 0, 1); spl.points[1].co = (*v, 1)
        o = link(bpy.data.objects.new(nm, cu)); o.data.materials.append(mat(nm, c, emit=2.0))
        kv(cu, "bevel_factor_end", [(1, 0.0), (20, 0.0), (32, 1.0)])
    # secret lattice point + small error = public target
    secret = 2 * b1 - 1 * b2 + 0 * b3
    target = secret + Vector((0.31, -0.22, 0.27))
    s = sphere("secret", secret, 0.12, mat("secret", QUANT, emit=2.5), seg=20)
    t = sphere("target", target, 0.13, mat("target", CLASS, emit=2.5), seg=20)
    halo = sphere("halo", target, 0.55, mat("halo", CLASS, emit=0.2, alpha=0.12, rough=0.1), seg=32)
    for o, f in ((t, 36), (halo, 40), (s, 56)):
        kv(o, "scale", [(1, (0.001,) * 3), (f, (0.001,) * 3), (f + 8, (1, 1, 1))])
    tgt.location = (0, 0, 0)
    kv(tgt, "location", [(1, (0, 0, 0)), (36, (0, 0, 0)), (FRAMES, tuple(target * 0.7))])
    return sc


SCENES = dict(rsa=scene_rsa, clock=scene_clock, superposition=scene_superposition,
              interference=scene_interference, measure=scene_measure, lattice=scene_lattice)


def configure_render(sc, out, preview=False):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 6 if preview else 12
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 3
    sc.cycles.transparent_max_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y = 854, 480
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = os.path.join(out, "f_####")
    sc.render.use_overwrite = False       # resume an interrupted render: skip finished frames
    sc.render.use_persistent_data = True


def main(argv):
    global FRAMES
    name, out = argv[0], argv[1]
    preview = "--preview" in argv
    if "--frames" in argv:
        FRAMES = int(argv[argv.index("--frames") + 1])
    names = list(SCENES) if name == "all" else name.split(",")
    for n in names:
        sc = SCENES[n]()
        ease_all()
        d = os.path.join(out, n)
        os.makedirs(d, exist_ok=True)
        configure_render(sc, d, preview)
        if preview:
            pf = [int(x) for x in argv[argv.index("--pf") + 1].split(",")] if "--pf" in argv else \
                 (1, FRAMES // 3, 2 * FRAMES // 3, FRAMES)
            for f in pf:
                sc.frame_set(f)
                sc.render.filepath = os.path.join(d, f"preview_{f:03d}.png")
                bpy.ops.render.render(write_still=True)
        else:
            bpy.ops.render.render(animation=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, f"{n}.blend"))
        print("DONE", n, flush=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(args)
