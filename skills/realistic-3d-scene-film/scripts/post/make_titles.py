# 字幕/片名卡（透明 PNG）
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(HERE, "..", "assets", "fonts")
os.makedirs(os.path.join(HERE, "titles"), exist_ok=True)

def font(name, size, var=None):
    f = ImageFont.truetype(os.path.join(F, name), size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f

def spaced(draw, xy, text, fnt, fill, spacing):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + spacing
    return x

def width(draw, text, fnt, spacing):
    return sum(draw.textlength(c, font=fnt) for c in text) + spacing * (len(text) - 1)

def with_shadow(layer):
    a = layer.split()[3]
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.35)))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 2))
    out.alpha_composite(layer)
    return out

W, H = 1920, 1080
# lower third
im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
big = font("NotoSerifSC-VF.ttf", 50, "Medium"); small = font("NotoSansSC-VF.ttf", 22, "Light")
x0, y0 = 128, 868
d.line([(x0, y0 - 18), (x0 + 36, y0 - 18)], fill=(255, 244, 228, 220), width=2)
spaced(d, (x0, y0), "杭州 · 西湖", big, (255, 248, 238, 240), 10)
spaced(d, (x0 + 2, y0 + 76), "清晨  五时五十二分", small, (255, 244, 230, 200), 6)
with_shadow(im).save(os.path.join(HERE, "titles", "lower3.png"))
# end title
im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
big = font("NotoSerifSC-VF.ttf", 104, "Regular"); sub = font("Archivo-VF.ttf", 22, "Light")
t1, t2 = "西湖 · 晨", "WEST LAKE  ·  HANGZHOU"
w1 = width(d, t1, big, 34); w2 = width(d, t2, sub, 9)
spaced(d, ((W - w1) / 2, 430), t1, big, (255, 249, 240, 245), 34)
spaced(d, ((W - w2) / 2, 590), t2, sub, (255, 244, 230, 190), 9)
with_shadow(im).save(os.path.join(HERE, "titles", "endtitle.png"))
print("titles ok")
