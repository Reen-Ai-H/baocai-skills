#!/usr/bin/env python3
"""细节体检：把一张渲染图切成格子，量每格的「细节能量」，找出大片空、平、被雾洗白的区域，
并裁出 1:1 原尺寸小图让人 / agent 逐块看。不依赖 Blender，只要 numpy + Pillow。

用法:
  python qa_detail.py <img> [<img> ...] [--out qa/] [--cols 16] [--rows 9] [--mask <mask.png>]

  --mask：detail_kit.py 渲的实体几何蒙版（白 = 有东西）。给了蒙版，就只在"实体占 ≥ 50% 的格子"里量，
          天空、雾、平静水面这种故意留白不会被误判；没给就用"顶部连续平行 = 天空"粗估，留白多的构图会误报。
          多张图共用一个蒙版时（同一机位）直接给一个；不同机位就一张一张跑。

每张图输出:
  <out>/<name>_heat.jpg    原图缩到 1600 宽 + 格子热力（红 = 平 / 空，绿 = 有细节）
  <out>/<name>_crop{1,2,3}.png  三块 1:1 原分辨率裁切：最平的非天空区、画面中心、细节最多的区
  stdout 一行汇总:  name  flat=0.58  veiled=0.31  detail_med=3.2  verdict=GREYBOX

判读（经验阈值，按 1920 宽归一化；不同风格可调）:
  flat    = 细节能量 < 1.5 的格子占比（天空格除外）。> 0.45 基本可判为"灰盒感"。
  veiled  = 平均亮度 > 0.62 且局部对比 < 0.05 的格子占比 = 被雾 / 光晕洗白。> 0.30 说明雾太重。
  detail_med = 非天空格细节能量中位数。实拍城市 / 风景一般 4~12；< 2.5 偏空。
这些数字只是提醒，最终以人眼看 1:1 裁切为准；但如果 verdict 不是 OK，不要交付，先补细节。
"""
import sys, os, argparse
import numpy as np
from PIL import Image, ImageDraw


def load(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im, dtype=np.float32) / 255.0
    if a.max() > 1.0:  # 16-bit PNG already handled by convert, keep guard
        a = a / a.max()
    return im, a


def luma(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def box(L, k):
    pad = np.pad(L, k, mode="edge")
    c = np.cumsum(np.cumsum(pad, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    n = 2 * k + 1
    b = (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / (n * n)
    return b[: L.shape[0], : L.shape[1]]


def detail_energy(L):
    """结构细节：先用 2px 盒滤波压掉胶片颗粒 / 渲染噪点，再找"清楚的边"。
    返回每像素 0/1 的边缘图 ×100（格子均值 = 边缘像素百分比）。颗粒、雾里的渐变都不算细节。"""
    S = box(L, 2)
    gx = np.zeros_like(S); gy = np.zeros_like(S)
    gx[:, 1:-1] = S[:, 2:] - S[:, :-2]
    gy[1:-1, :] = S[2:, :] - S[:-2, :]
    g = np.hypot(gx, gy)
    return (g > 0.025).astype(np.float32) * 100.0


def analyze(path, out, cols, rows, mask=None):
    im, a = load(path)
    H, W = a.shape[:2]
    scale = 1920.0 / W
    if abs(scale - 1) > 0.01:  # 统一到 1920 宽再量，阈值才可比
        im_n = im.resize((1920, int(round(H * scale))), Image.LANCZOS)
        a_n = np.asarray(im_n, dtype=np.float32) / 255.0
    else:
        a_n = a
    L = luma(a_n)
    E = detail_energy(L)
    h, w = L.shape
    th, tw = h // rows, w // cols
    en = np.zeros((rows, cols)); mu = np.zeros((rows, cols)); sd = np.zeros((rows, cols))
    for r in range(rows):
        for c in range(cols):
            sl = (slice(r * th, (r + 1) * th), slice(c * tw, (c + 1) * tw))
            en[r, c] = E[sl].mean(); mu[r, c] = L[sl].mean(); sd[r, c] = L[sl].std()
    # 天空：从上往下连续的"平 + 无结构"行（每行 ≥ 80% 格子能量 < 1.2）
    sky = np.zeros_like(en, dtype=bool)
    for r in range(rows):
        if (en[r] < 0.5).mean() >= 0.8:
            sky[r] = en[r] < 0.5
        else:
            break
    if mask:
        mk = Image.open(mask).convert("L").resize((w, h), Image.NEAREST)
        mk = np.asarray(mk, dtype=np.float32) / 255.0
        cov = np.array([[mk[r * th:(r + 1) * th, c * tw:(c + 1) * tw].mean() for c in range(cols)] for r in range(rows)])
        sky = cov < 0.5
    land = ~sky
    flat_t = en < 1.5
    veil_t = (mu > 0.62) & (sd < 0.05)
    n_land = max(1, land.sum())
    flat = (flat_t & land).sum() / n_land
    veiled = (veil_t & land).sum() / n_land
    dmed = float(np.median(en[land])) if land.any() else 0.0
    if flat > 0.45 or dmed < 2.5:
        verdict = "GREYBOX"
    elif veiled > 0.30:
        verdict = "FOG-WASHED"
    elif flat > 0.30:
        verdict = "THIN"
    else:
        verdict = "OK"

    name = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(out, exist_ok=True)
    # 热力图
    pv = im.resize((1600, int(1600 * H / W)), Image.LANCZOS).convert("RGBA")
    ov = Image.new("RGBA", pv.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    sx, sy = pv.size[0] / cols, pv.size[1] / rows
    for r in range(rows):
        for c in range(cols):
            if sky[r, c]:
                continue
            t = min(1.0, en[r, c] / 6.0)
            col = (int(255 * (1 - t)), int(200 * t), 40, 90)
            d.rectangle([c * sx, r * sy, (c + 1) * sx - 1, (r + 1) * sy - 1], fill=col)
            d.text((c * sx + 3, r * sy + 2), f"{en[r, c]:.1f}", fill=(255, 255, 255, 230))
    Image.alpha_composite(pv, ov).convert("RGB").save(os.path.join(out, f"{name}_heat.jpg"), quality=88)
    # 三块 1:1 裁切（原分辨率坐标）
    cw, chh = min(768, W), min(432, H)
    def crop_at(r, c, tag):
        cx = int((c + 0.5) * W / cols); cy = int((r + 0.5) * H / rows)
        x0 = int(np.clip(cx - cw // 2, 0, W - cw)); y0 = int(np.clip(cy - chh // 2, 0, H - chh))
        im.crop((x0, y0, x0 + cw, y0 + chh)).save(os.path.join(out, f"{name}_{tag}.png"))
    masked = np.where(land, en, np.inf)
    r1, c1 = np.unravel_index(np.argmin(masked), en.shape)
    masked2 = np.where(land, en, -np.inf)
    r3, c3 = np.unravel_index(np.argmax(masked2), en.shape)
    crop_at(r1, c1, "crop1_flattest"); crop_at(rows // 2, cols // 2, "crop2_center"); crop_at(r3, c3, "crop3_richest")
    # 蒙版只量实体：主体很小、其余又大片平的时候，OK 只代表那一小块。打个提醒，交付时要说明是不是有意留白。
    note = ""
    frame_flat = float(flat_t.mean())
    if land.mean() < 0.20 and frame_flat > 0.60:
        note = f"\tnote=SPARSE(solid {land.mean():.0%}, frame_flat {frame_flat:.0%}: 确认留白是有意的构图)"
    print(f"{name}\tflat={flat:.2f}\tveiled={veiled:.2f}\tdetail_med={dmed:.1f}\tsolid={land.mean():.2f}\tverdict={verdict}{note}")
    return verdict


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 GBK，中文提示会乱码
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("imgs", nargs="+")
    ap.add_argument("--out", default="qa")
    ap.add_argument("--cols", type=int, default=16)
    ap.add_argument("--rows", type=int, default=9)
    ap.add_argument("--mask", default=None)
    a = ap.parse_args()
    bad = 0
    for p in a.imgs:
        bad += analyze(p, a.out, a.cols, a.rows, a.mask) != "OK"
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
