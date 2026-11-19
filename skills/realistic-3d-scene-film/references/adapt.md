# 换一个地点 / 场景：哪些留、哪些换、按什么顺序

参考实现是西湖专用的。换成雪山、海边、古镇、园林时，别从头写，也别原样跑：按下面的表把"通用工具"留下，把"西湖专用"换掉。先按 `scripts/README.md` 把脚本平铺复制到新项目目录，再改副本，不要改 skill 里的脚本，也不要改 `westlake-3d/`。

## 改的顺序（每步出一张图给用户看再往下走）

1. **定一刻**，写成一句：地点 + 时间 + 天气 + 太阳高度和方位（"黄山，日出后 10 分钟，太阳高 4°，在镜头左前方，山谷云海"）。不确定就用低太阳 + 雾 + 逆光。
2. **改光**：`build_westlake.py` 的 `SUN_ELEV`、`SUN_AZ`（相对相机 +Y 轴向右的角度）。先只渲天空 + 水 / 地 + 雾，确认是逆光再加东西。
3. **换地形和地标**：删掉西湖专用的生成函数调用，换成新地标。能复用的造型手法：八角环 loft（任何塔、亭柱）、拱 + 倒影成圆（任何拱桥）、噪声高度网格分层（任何远山）、`land_strip`（堤、岸、沙洲）。
4. **英雄图**：45 mm 左右全景，用户点头前不做动画。
5. **分镜表**：改 `doc_shots.py` 的 `SHOTS` 帧区间和每个 `shot_camera(...)`；动物、近景道具换成当地的（海鸥、鹿、松枝、苔藓……），规则不变：长焦、逆光、小而远。
6. **声音表**：`mix_audio.py` 的 `cues` 全部换成新地点的 Freesound 录音（用 `sound` skill 找），时长 `DUR` 跟着片长改。
7. **字幕和文件名**：`make_titles.py` 的地点、时间、英文片名；`assemble.sh` 的输出文件名、`-t 40`、片尾淡入时间点；`night.sh` 的 `NEED` 帧数表和进程过滤名。

## `build_westlake.py`

| 留（通用） | 换（西湖专用） |
|---|---|
| `link`、`mesh_obj`、`setin` | `leifeng()` 雷峰塔、`baochu()` 保俶塔 |
| 材质：`principled`、`add_noise_color`、`add_bump`、`foliage`（叶片透光）、`emissive`（强度 ≲ 1）、`water_material`（世界坐标噪声 + 凹凸随距离衰减） | `bridge()` 断桥、`land_strip` 的白堤坐标 |
| `smoothstep`、`hill_layer`（分层远山） | `stone_lantern()` 三潭印月 |
| `oct_ring`、`loft`（环形 loft） | `boat()` 乌篷船（原来还带摇橹人，已删） |
| `ground_z`（射线落地） | `willow()` / `fg_tips()` 柳树、`lotus_leaf()` 荷叶：换植物时可当"叶片串"和"极坐标叶片"的写法参考 |
| `fog_volume()`（高度薄雾 + 贴地晨雾，各向异性 0.7） | 所有物体坐标、`random.seed(7)`、`hill_layer` 的山形参数 |
| 天空 + 太阳灯 + 方向校验打印（`SKY sun_direction ... wanted`） | `SUN_ELEV = 5.6°`、`SUN_AZ = 22°` |
| 渲染设置段（Cycles、自适应采样、降噪、体积步进、AgX、16-bit PNG） | 相机位置、`anim` 模式里的船和鸟驱动 |
| `anim` 模式的风摆做法（Displace + 移动 Empty + 顶点组） | 按名字找柳条的 `_leaves` / `_twigs` 后缀 |

## `doc_shots.py`

| 留（通用） | 换（西湖专用） |
|---|---|
| `loft_spine`（任何细长有机体：茎、鸟身、鱼）、`parent_all`、`descendants`、`cone_between`、`key_seq`、`d3` | `SHOTS` 帧表（8 镜 960 帧） |
| `key_hide` / `visible_only`（按镜头开关物体） | `hero_leaf`（荷叶水珠）、`lotus_bloom`、`dragonfly`、`egret_standing`、`egret_flying` / `flock`、`mallard` |
| `make_canvas` / `make_brush`（Dynamic Paint 涟漪，任何水面事件） | `petal_material`、`wing_material`、`duck_material`、`hero_leaf_material` |
| `shot_camera`（焦段、光圈、逐帧对焦） | 每个 `CAMS["Sx"]` 的坐标和对焦表 |
| `fill_light`（微距镜头的反光板补光，只对单镜可见） | `fill_S1`、`fill_S5` 的位置和强度 |
| 底部 run 段（单帧 / 逐帧、涟漪顺序步进、已存在跳过） | `need_sim = SHOT in ("S4", "S6")`：改成新片里有涟漪的镜头 |

## three.js 侧（只在做视频时才要改）

`export_three.py` 的 `DROP_PREFIX`（要删的体积、涟漪、代理物体名前缀）要和新场景的命名对上；`src/main.js` 按**材质名**挑特殊着色（`water`、`droplet`、`petal`、`dragonfly_wing`、`feather`、`lotus_bud`、`seedpod`、`stone`、`bark`、`lotus_hero`）和按物体名做风摆（`willow_fg`），每镜覆盖参数在顶部的镜头表（`S1: {near, shadowAt, shadowHalf, env, fill, warm, sat}`）。换场景后没对上名字的材质会按 `scene.json` 里导出的颜色、粗糙度、透光、噪声色走通用 PBR，不会报错，但水珠折射、花瓣渐变这类特写效果会悄悄消失，所以要对着 Cycles 帧逐镜比一遍。

## 换场景时最容易犯的错

- 只改地标不改光：太阳方位没重算，整片变顺光，氛围全没了。
- 动物或人物"补生命感"：人物默认不放；动物摆得大、近、正面就像摆件。
- 新地点没有雾的理由（正午、干燥地区）：氛围的主力没了，要提前跟用户商量换时刻（清晨、黄昏、雨后），别硬上浓雾。
- 自发光（窗、灯笼、塔孔）排成两点一线：像脸，调暗或打散。
