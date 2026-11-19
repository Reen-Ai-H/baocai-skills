# 调色：bloom + S 曲线 + 冷暖分离 + 暗角 + 胶片颗粒
# 用法: python grade.py in.png out.(png|jpg) [seed]   或   python grade.py --dir in_dir out_dir
import sys, os
import numpy as np
from PIL import Image


def blur(ch, factor):
    h, w = ch.shape
    im = Image.fromarray(ch.astype(np.float32), "F")
    small = im.resize((max(1, w // factor), max(1, h // factor)), Image.BOX)
    small = small.resize((max(1, w // (factor * 2)), max(1, h // (factor * 2))), Image.BOX)
    return np.asarray(small.resize((w, h), Image.BICUBIC), dtype=np.float32)


def load(src):
    if src.endswith(".u16"):                     # three.js 渲染器输出：8 字节头 (w, h) + 16-bit RGB
        raw = np.fromfile(src, dtype=np.uint16)
        w, h = np.frombuffer(raw[:4].tobytes(), dtype=np.uint32)
        return raw[4:4 + w * h * 3].reshape(h, w, 3).astype(np.float32) / 65535.0
    a = np.asarray(Image.open(src)).astype(np.float32)
    return (a / (65535.0 if a.max() > 255 else 255.0))[..., :3]


def grade(src, dst, seed=0):
    a = load(src)
    if (a.shape[1] != 1920 or a.shape[0] != 1080) and not os.environ.get("GRADE_KEEP"):   # 低分辨率渲染 → Lanczos 放大到 1080p
        a = np.stack([np.asarray(Image.fromarray(a[..., c].astype(np.float32), "F").resize((1920, 1080), Image.LANCZOS))
                      for c in range(3)], -1).astype(np.float32)
        a = np.clip(a, 0, None)
    h, w, _ = a.shape
    s = w / 1920.0
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)

    # --- bloom (warm, multi-scale)
    thr = np.clip((lum - 0.80) / 0.20, 0, 1) ** 2
    src_b = a * thr[..., None]
    bloom = np.zeros_like(a)
    for f, wgt in ((max(2, int(6 * s)), 0.35), (max(4, int(18 * s)), 0.35), (max(8, int(48 * s)), 0.30)):
        for c in range(3):
            bloom[..., c] += blur(src_b[..., c], f) * wgt
    bloom *= np.array([1.0, 0.78, 0.55], np.float32)
    a = a + bloom * 0.30
    # --- gentle atmospheric glow lift (halation)
    a = 1 - (1 - a) * (1 - bloom * 0.10)

    # --- tone: black floor + S curve
    a = np.clip((a - 0.035) / 0.965, 0, None)
    sm = a * a * (3 - 2 * np.clip(a, 0, 1))
    a = a * 0.62 + sm * 0.38

    # --- split toning
    lum = np.clip(a @ np.array([0.2126, 0.7152, 0.0722], np.float32), 0, 1)
    sh = (1 - lum) ** 2.2
    hi = lum ** 2.0
    a += sh[..., None] * np.array([-0.018, 0.004, 0.030], np.float32)
    a += hi[..., None] * np.array([0.030, 0.010, -0.028], np.float32)

    # --- saturation
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    a = lum[..., None] + (a - lum[..., None]) * 1.14

    # --- vignette
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 * 0.85 + ((yy - h / 2) / (h / 2)) ** 2)
    vig = 1 - 0.28 * np.clip((r - 0.45) / 0.9, 0, 1) ** 1.6
    a *= vig[..., None]

    # --- film grain (luma-weighted, stronger in mids)
    rng = np.random.default_rng(seed)
    g = rng.normal(0, 1, (h, w)).astype(np.float32)
    g = (g + np.roll(g, 1, 0) * 0.5 + np.roll(g, 1, 1) * 0.5) / 1.5
    lum = np.clip(a @ np.array([0.2126, 0.7152, 0.0722], np.float32), 0, 1)
    a += (g * 0.011 * (0.4 + 2.4 * lum * (1 - lum)))[..., None]

    out = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    img = Image.fromarray(out, "RGB")
    if dst.lower().endswith(".jpg"):
        img.save(dst, quality=95, subsampling=0)
    else:
        img.save(dst)


if __name__ == "__main__":
    if sys.argv[1] == "--dir":
        ind, outd = sys.argv[2], sys.argv[3]
        os.makedirs(outd, exist_ok=True)
        files = sorted(f for f in os.listdir(ind) if f.endswith((".png", ".u16")))
        for i, f in enumerate(files):
            o = os.path.join(outd, f.replace(".u16", ".png"))
            if not os.path.exists(o):
                grade(os.path.join(ind, f), o, seed=i)
        print("graded", len(files))
    else:
        grade(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0)
        print("ok", sys.argv[2])
