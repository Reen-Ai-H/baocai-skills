# scripts/：通用工具 + 《西湖·晨》参考实现

**通用工具（任何项目直接用，不用复制）**：
- `blender/detail_kit.py`：细节函数（`facade_tower`、`rooftop_clutter`、`bevel_all`、`instance`、材质）+ `clay` / `mask` / `demo` 检查命令。在建场景脚本里 `sys.path.append(<此目录>)` 后 `from detail_kit import *`。冒烟测试：`"$BLENDER" -b --factory-startup -P detail_kit.py -- demo out.png`。
- `blender/probe.py`：环境和 API 名自检。
- `tools/qa_detail.py`：细节体检（`--mask` 必带）。`tools/fetch_polyhaven.py`：下载 CC0 素材。

下面是参考实现的用法。

这些脚本是从项目目录 `westlake-3d/` 复制来的，按用途分进了 `blender/ post/ threejs/` 三个子目录**只为了好读**。脚本之间用相对路径互相调用，**在这里原地跑不起来**，也会把 `.blend` 和渲染帧写进 skill 目录。用法：先平铺复制到一个新项目目录，再改副本。

## 1. 平铺到项目目录

项目目录放在仓库根下（和 `assets/`、`westlake-3d/` 同级），因为 `make_titles.py`、`mix_audio.py` 用 `../assets/` 找字体和声音库。

```
<仓库>/
├─ assets/fonts/  assets/sfx/          仓库共用素材（已存在）
└─ <新项目>/
   ├─ build_westlake.py  doc_shots.py  probe.py  render_all.sh  night.sh     ← blender/
   ├─ grade.py  mix_audio.py  make_titles.py  assemble.sh                   ← post/
   ├─ renders/doc/   sfx/   titles/                                         ← 自己建；sfx/ 放下载的 Freesound 录音
   └─ three/                                                                ← threejs/ 整个目录
      ├─ export_three.py  index.html  render.mjs  server.mjs  package.json  jobs_test.json
      ├─ make_video.sh  testgrid.sh  peek.py
      └─ src/main.js  src/glsl.js
```

```bash
P=<仓库>/<新项目>; S=<仓库>/skills/realistic-3d-scene-film/scripts
mkdir -p "$P/renders/doc" "$P/sfx" "$P/titles" && cp "$S"/blender/* "$S"/post/* "$P"/ && cp -r "$S/threejs" "$P/three"
cd "$P/three" && npm i
```

依赖：Blender 4.2+ / 5.x（`probe.py` 自检，路径放进 `BLENDER` 环境变量）、bash（Windows 用 Git Bash）、`ffmpeg`、Python 3 + `numpy` + `Pillow`；three.js 侧再要 Node 24 + 系统 Chrome。

## 2. 写死的东西（换机器 / 换项目必改）

| 文件 | 写死了什么 | 怎么改 |
|---|---|---|
| `render_all.sh` | Blender 路径读环境变量 `BLENDER`（默认 `blender`）；默认镜头顺序 `S2 S3 S7 S8 S1 S5 S4 S6`、`SPP=32`、`RES=75`（视频降档） | 改路径；镜头名跟 `SHOTS` 表走。日志写 `renders/doc/log_<镜>.txt`，目录要先建好 |
| `render.mjs` | Chrome 路径读 `CHROME_PATH`，没设就找常见安装位置；端口 5178 | 找不到就设 `CHROME_PATH` |
| `build_westlake.py` | 1920×1080、`SUN_ELEV/SUN_AZ`、所有西湖地标；`.blend` 存到脚本所在目录 | 见 `references/adapt.md` |
| `doc_shots.py` | `SHOTS` 帧表、相机、动物、有涟漪的镜头 `("S4","S6")` | 见 `references/adapt.md` |
| `night.sh` | 等日志里出现 `done S2`（那晚最后补渲的是 S2，不是默认顺序的末镜 S6）；按 `PROJECT_TAG`（默认 `westlake-3d`）过滤进程；关机要 `ALLOW_SHUTDOWN=1`；`NEED` 每镜帧数；调 `./assemble.sh` 并设 `VER=r2` | 改成新片的末镜、项目目录名、帧数表。Git Bash 里关机要写 `shutdown //s //t 600`（单斜杠会被当成路径）。**关机必须用户明确授权** |
| `assemble.sh` | 8 个镜头名、40 秒、字幕淡入淡出时间点、输出名 `西湖晨_纪录短片_*` | 按新片改 |
| `mix_audio.py` | `cues` 表里的西湖声音文件名（在 `westlake-3d/sfx/` 和仓库 `assets/sfx/`）、`DUR = 40` | 换新地点的录音 |
| `make_titles.py` | "杭州 · 西湖""清晨 五时五十二分""WEST LAKE · HANGZHOU"，字体 Noto Serif SC / Noto Sans SC / Archivo | 改文字 |
| `export_three.py` | 期望上一级目录有 `build_westlake.py`；构建参数 `doc S2`；`DROP_PREFIX` 物体名前缀 | 平铺后路径自然对上；前缀按新场景改 |
| `make_video.sh` | 5 段剪辑的镜头和帧号、`sfx/mix.wav`、输出名 | 按新片改 |
| `testgrid.sh` | 读 `jobs_test.json`，九宫格顺序是西湖的帧号 | 按新片改 |

## 3. 常用命令（在项目目录里，Git Bash）

```bash
# 英雄图（基础场景，不进分镜）
"$BLENDER" -b --factory-startup -P build_westlake.py -- "$(pwd -W)/renders/hero.png" 128 100
# 分镜单帧静帧：frame 是镜头内偏移（S2 从 97 开始，frame 12 = 第 109 帧），也可 mid/first/last
"$BLENDER" -b --factory-startup -P build_westlake.py -- "$(pwd -W)/renders/stills" 128 100 doc S2 frame 12
# 静帧调色：一定加 GRADE_KEEP=1，否则会被缩放成 1920x1080（竖图会被压扁）
GRADE_KEEP=1 python grade.py renders/stills/S2_0109.png renders/stills/S2_0109.jpg
# 整片视频帧（逐镜，断点续渲；默认 75% + 32 spp）
./render_all.sh            # 或 SHOTS="S4 S6" SPP=48 ./render_all.sh
# 调色 + 字幕 + 混音 + 出片
python make_titles.py && VER=r1 ./assemble.sh
```

输出路径给绝对路径（Windows Git Bash 用 `pwd -W`），Blender 对相对路径的解析和 shell 不一样。设备默认 CUDA；`WL_DEVICE=OPTIX` 可切（有的机器 OptiX 内核会编译报错，降噪器不受影响）。

**Cycles 九宫格**（每镜一帧，调色后拼 3×3 预览）：
```bash
python - <<'EOF'
from PIL import Image
import glob
fs = sorted(glob.glob('renders/stills/S*_*.jpg'))[:9]   # 每镜一张，按镜头顺序
g = Image.new('RGB', (1920, 1080))
for i, f in enumerate(fs):
    g.paste(Image.open(f).resize((640, 360), Image.LANCZOS), ((i % 3) * 640, (i // 3) * 360))
g.save('renders/stills/grid.jpg', quality=90)
EOF
```

## 4. three.js（只做视频）

```bash
"$BLENDER" -b --factory-startup -P three/export_three.py          # → three/public/scene.glb + scene.json + anim.bin
cd three && node render.mjs --still S2 109 64                   # 单帧预演（帧号是全局帧号）
./testgrid.sh                                                   # 九宫格预演
node render.mjs jobs_video.json && ./make_video.sh              # 效果视频；jobs 格式见 jobs_test.json
python peek.py ../renders/three/test/S2_109/f_0109.u16           # 快速看 .u16（原始 + 调色）
```
