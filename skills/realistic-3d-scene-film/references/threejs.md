# three.js 离线渲染器：结构、参数、坑

**定位：只做视频的辅助渲染器。** 任何静帧、封面、九宫格、小红书图都用 Cycles（SKILL.md 第 9 节默认审美 1），这里渲出的静帧只能当预演、调参参考。

## 为什么这样分工（用户问过"效果和效率差在哪、适用性是否更好"）

| | Cycles | three.js 管线 |
|---|---|---|
| 强项 | 全局光照、真体积雾和光柱、真实倒影、次表面散射 → 照片感 | 迭代快（秒级）、风格可控、批量 / 模板化、能做网页交互 |
| 弱项 | 慢，调一次看一次是分钟级 | 无二次反弹和 AO（物体略"浮"）、雾无体积阴影、倒影偏镜面、SSS 靠近似 |
| 本项目用途 | **所有图像**；时间够时视频也用它 | **只用于视频**：效果视频、多版本、赶时间、预演 |

用户看完两版九宫格的结论："效果上还是 Blender 更好，特别是静态图像，非常自然。"视频里画面在动、有运动模糊和剪辑节奏，差距不明显，速度优势（5–20 倍）才值得。逆光 + 浓雾 + 剪影最能藏住短板；室内、多反射、晴天无雾时差距大，先跟用户说清。

## 环境
three 0.181、puppeteer-core 24、系统 Chrome，Node 24。在 `three/` 目录 `npm i`（`package.json` 已列依赖；国内网络可能要几分钟）。包名别叫 `three`，否则 `npm i three` 报 ENOSELF，skill 里已改成 `scene-three-renderer`。
- `render.mjs` 读 `CHROME_PATH`，没设就找常见安装位置。
- 无头 Chrome 跑独显：`--use-angle=d3d11 --force_high_performance_gpu`，启动后看 `[page]` 日志里打印的 GPU 名，确认不是核显。
- 本地服务 `server.mjs` 只监听 127.0.0.1:5178，`POST /save` 只允许写 `../renders/` 下。

## 数据流
```
Blender ──export_three.py──▶ public/scene.glb + scene.json + anim.bin
                              │
index.html + src/main.js (WebGL2, 无头 Chrome 独显) ◀── render.mjs (puppeteer) ── jobs.json
                              │ POST /save  (server.mjs 只允许写 ../renders/)
                       renders/.../f_0001.u16  (8 字节头 w,h + 16-bit RGB，AgX 之后)
                              │ grade.py (同 Cycles 版)
                            PNG → ffmpeg
```
jobs.json：`[{shot, frames:[...], spp, w, h, shutter, out, params?}]`，`frames` 是**全局帧号**（和 Blender 单帧的镜头内偏移不同），`shutter` 是快门占帧比例（视频 0.5，静帧 0），`out` 相对 `three/`。示例见 `scripts/threejs/jobs_test.json`。`node render.mjs --still S2 109 64` 出单帧预演。

## 导出（export_three.py）
- exec 基础场景脚本（OUT 留空 → 不渲染）。注意被 exec 的脚本会覆盖同名全局变量（`HERE`），导出脚本自己的路径变量要另起名。
- 删掉 three 里另做的东西：体积雾立方体、涟漪画布、brush 代理、Empty；移除 Displace / Dynamic Paint 修改器（风摆在顶点着色器里做）。
- 坐标：Blender Z-up → glTF Y-up，`C = [[1,0,0],[0,0,1],[0,-1,0]]`。物体矩阵 `C·M·C⁻¹`，**相机矩阵 `C·M`**（保持相机自身朝 −Z、上 +Y）。
- 动画：只采样有 animation_data（或祖先有）的对象，丢掉全程不变的；960 帧 × 308 个对象 = 14 MB float32。可见性存成区间 `[[起,止]]`。
- 相机逐帧存 `[焦距 mm, 对焦距离, 光圈]`；three 的竖直 fov = `2·atan(tan(hfov/2)/aspect)`，hfov 由 36 mm 传感器算。
- three 加载后按 `PropertyBinding.sanitizeNodeName` 找节点（`Sphere.012` → `Sphere012`）；动画对象 `scene.attach` 到根、`matrixAutoUpdate=false`，直接写世界矩阵。

## 着色
- 所有材质是 `MeshPhysicalMaterial` + `onBeforeCompile` 补丁（`patch()`），用 `customProgramCacheKey` 让同类共享程序。
- **雾**替换 `#include <fog_fragment>`：沿视线二次分布 20 步，密度 = 薄雾 `0.00038·e^(−y/160)` + 晨雾 `0.0042·e^(−y/4.5)·噪声形状`；内散射 = 太阳 × HG(g=0.7) × 太阳透过率(y) + 环境；用 |y| 让倒影（虚拟相机在水下）走镜像光路。参数和 Blender 体积雾同单位。
- **透光**：在 `lights_fragment_begin` 的平行光 `RE_Direct` 后加 `transCol·mix·E·max(0,−N·L)/π`。
- **补光无高光**（Cycles 里 visible_glossy=False）：从 `lights_physical_pars_fragment` 删掉 RectArea 的 directSpecular 一行，否则水珠上会出现方形反光。
- **水珠**：替换 `opaque_fragment`，以物体原点为球心解析计算两次折射（含全反射），出射方向朝下取叶片色、朝上采 PMREM 天空，出射方向对准太阳时加焦散亮点。比内置 transmission 好得多（内置的像空心肥皂泡）。
- 程序纹理用 pcg3d 整数哈希的梯度噪声，别用 `fract(sin())`（大坐标精度崩）。物体空间坐标 = `(x, −z, y)` 还原 Blender 坐标，色带/叶脉公式可直接照搬节点。
- 水面：`Reflector`（HalfFloat、multisample 0）+ 自定义 shader：Blender 同款两层噪声的有限差分法线、凹凸随距离衰减、Fresnel 0.02、GGX 闪光（a=0.026，比真实粗糙度大一点，模拟日轮张角，太小会是细长亮线）、涟漪 = 若干发射点 `(x,z,年龄,振幅)` 的衰减波列（鸭子每 2 帧发一圈，自然成 V 形尾迹）。倒影渲染时关掉天空日轮，避免和 GGX 闪光重复。
- 天空自写（地平线渐变 + 朝日暖光多尺度 exp 衰减 + 日轮），同一材质再渲一次 PMREM 当环境光（不含日轮）。

## 累积采样
- 每个子样本用 Halton(2,3) 子像素、(5,7) 光圈（同心圆盘映射）、(11,13) 太阳张角、17 雾抖动、19 快门时间。帧间用同一序列 → 无闪烁。
- 薄透镜：相机沿右/上偏移 (dx,dy)，投影矩阵 `P[8] = −P[0]·dx/focus − 2jx/W`，`P[9]` 同理；光圈半径 = 焦距/(2·f值)。
- 累积用两张 RGBA32F ping-pong `mix(prev,new,1/k)`；**k=1 时直接写 new**（`mix(NaN,x,1)` 仍是 NaN）。
- 输出 pass：曝光 × 每镜白平衡 → 饱和度 1.18 → three 内置 `AgXToneMapping`（ShaderMaterial 要自己给 `toneMappingExposure` uniform）→ sRGB → 对比度 1.08。**不要再 include `colorspace_pars_fragment`**，ShaderMaterial 前缀里已有。
- 对数深度缓冲（微距 near 0.004 + far 6000）；自写 ShaderMaterial 要带 logdepthbuf 片段。

## 参数（《西湖·晨》最终值）
曝光 2^−0.9；太阳 6 × (1, .52, .24) × 透过率 ≈ 0.5；环境光 0.55；天空增益 1.3；地平线 (.52,.40,.28)、天顶 (.085,.09,.105)、暖光 (1,.52,.20)。每镜覆盖：S1 环境 1.0、补光 2.6×、白平衡 (1.12,1,.78)、饱和 0.95；S5 补光 1.5×。阴影盒跟镜头：S1 1.2 m、S2 60 m、S3 160 m（塔在 900 m 外）。

## 采样量和耗时（RTX 4060 Laptop）
| 镜头 | 1080p 单帧 | 备注 |
|---|---|---|
| 大全景 S2/S8 | 64 spp ≈ 2–7 s | 1.7M 顶点 × (阴影 + 倒影 + 主画面) |
| 微距 S1 | 256 spp ≈ 12.5 s | 焦外闪光点会显出"点阵"光斑，静帧用 1024 |
| 拉焦 S5/S7 | 96 spp 有重影，192–768 才干净 | |

## 已知不足（要对用户说清）
没有二次反弹/AO、雾没有体积阴影（无光柱）、倒影偏镜面、日光闪烁路径比 Cycles 宽亮、SSS 是近似。下一步可加：GTAO、雾里采样阴影图做光柱、倒影按距离模糊。
