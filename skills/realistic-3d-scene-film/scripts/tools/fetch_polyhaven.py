#!/usr/bin/env python3
"""从 Poly Haven（CC0，可商用、无需署名）下载 HDRI / PBR 贴图 / 模型。只用 Python 标准库。

用法:
  python fetch_polyhaven.py search <关键词> [hdris|textures|models]     # 列出匹配的资产 id
  python fetch_polyhaven.py hdri    <id> [1k|2k|4k] <out_dir>           # 下 .hdr 或 .exr
  python fetch_polyhaven.py texture <id> [1k|2k|4k] <out_dir>           # 下 diff / rough / nor_gl / ao / disp
  python fetch_polyhaven.py model   <id> [1k|2k|4k] <out_dir>           # 下 .blend 及其贴图

例:
  python fetch_polyhaven.py search sunrise hdris
  python fetch_polyhaven.py hdri  kloofendal_misty_morning 4k assets/hdri
  python fetch_polyhaven.py texture concrete_wall_008 2k assets/tex
贴图下载后在 Blender 里用 detail_kit.mat_pbr_folder("名字", "assets/tex/<id>")。
API 文档: https://api.polyhaven.com ；请求带一个通用 User-Agent，不要带个人信息。
"""
import json, os, sys, urllib.request

API = "https://api.polyhaven.com"
UA = {"User-Agent": "blender-scene-pipeline/1.0"}
TEX_MAPS = ("diffuse", "diff", "rough", "nor_gl", "ao", "displacement", "disp", "arm")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def save(url, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, url.split("/")[-1].split("?")[0])
    if os.path.exists(path):
        print("exists", path); return path
    data = get(url)
    with open(path, "wb") as f:
        f.write(data)
    print(f"saved {path} ({len(data) / 1e6:.1f} MB)")
    return path


def pick(node, res, fmts):
    r = node.get(res) or node.get("2k") or next(iter(node.values()))
    for f in fmts:
        if f in r:
            return r[f]
    return next(iter(r.values()))


def main(a):
    if not a or a[0] not in ("search", "hdri", "texture", "model"):
        print(__doc__); return 1
    if a[0] == "search":
        kind = a[2] if len(a) > 2 else "all"
        assets = json.loads(get(f"{API}/assets?type={kind}"))
        q = a[1].lower()
        hits = [(k, v.get("name", "")) for k, v in assets.items()
                if q in k.lower() or q in v.get("name", "").lower()
                or any(q in t.lower() for t in v.get("tags", []) + v.get("categories", []))]
        for k, n in sorted(hits)[:60]:
            print(f"{k}\t{n}")
        print(f"{len(hits)} hits"); return 0
    kind, aid = a[0], a[1]
    res = a[2] if len(a) > 3 else "2k"
    out = os.path.join(a[-1], aid)
    files = json.loads(get(f"{API}/files/{aid}"))
    if kind == "hdri":
        save(pick(files["hdri"], res, ("hdr", "exr"))["url"], out)
    elif kind == "texture":
        for key, node in files.items():
            if key.lower() in TEX_MAPS:
                save(pick(node, res, ("jpg", "png"))["url"], out)
    else:
        blend = pick(files["blend"], res, ("blend",))
        save(blend["url"], out)
        for rel, inc in blend.get("include", {}).items():
            save(inc["url"], os.path.join(out, os.path.dirname(rel)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
