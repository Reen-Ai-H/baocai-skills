# Blender 5.x 后台脚本：坑和做法

适用 Blender 4.2+ / 5.x。参考机器的配置和耗时见 `examples/westlake.md`。

换机器或换 Blender 版本先跑 `"$BLENDER" -b --factory-startup -P probe.py`：它打印天空节点的 `sky_type` 枚举、Principled BSDF 和体积节点的输入名、可用的 OPTIX/CUDA 设备。脚本里的 `setin(node, name, val)` 按输入名设值，名字对不上会静默跳过，所以版本一变要先对一遍。

## 运行
- `blender -b --factory-startup -P script.py -- args`，脚本里用 `sys.argv[sys.argv.index("--")+1:]` 取参数。
- 设备用环境变量切（参考脚本里是 `WL_DEVICE=CUDA|OPTIX`；AMD 用 HIP，Mac 用 METAL）。OptiX 内核编译报错时切 CUDA，OptiX **降噪器**通常仍可用。不要去删系统级缓存。
- 长任务放后台，日志写文件；`render_all.sh` 逐镜头跑，每镜结束打印 `done S2 ...` 供外部脚本判断。

## 方向和坐标
- 太阳灯：`sun_vec.to_track_quat("Z","Y")`（灯沿 −Z 发光，所以对准太阳方向向量本身）。天空：`sun_rotation = SUN_AZ`。两者都要和"太阳在镜头右前方"一致，渲一张检查顺光/逆光。
- 物体摆在地形上用射线 `ground_z(x,y)` 求高度，塔第一次就埋进了山里。

## 材质
- 水面法线噪声用 `ShaderNodeNewGeometry` 的 Position（世界坐标），多块水面才能无缝。
- 凹凸强度随视距衰减（近 0.6 → 远 0.025），远处倒影才像镜子。
- 叶片 = Principled + Translucent 混合 + ObjectInfo.Random 做 ±3% 色相变化。
- 自发光（窗、孔洞）强度 ≲ 1，不然像眼睛。

## 动画
- 驱动表达式用 `frame`；镜头切换用 `hide_render` 关键帧；风摆用 Displace + 移动 Empty。
- 支点：花茎摆动的父物体要放在茎底，放世界原点会让上面的蜻蜓飘离花苞约 10 m。
- **Dynamic Paint 涟漪**：画布 WAVE；brush 不能挂在被驱动的父物体下（会被忽略），要做不带父级的代理物体逐帧 keyframe；loft 网格当 volume brush 失败，用缩放的 UV 球代理成功（±2.4 cm 波）；渲染必须从模拟起点顺序 `frame_set`。枚举里没有 "OBSTACLE"，用 DEPTH/CHANGE。

## 渲染设置
- 采样 32–64 + 自适应 0.02 + 降噪；体积步进 rate 4、max steps 256；`use_persistent_data=True`。
- AgX + Medium High Contrast，曝光 −0.9，16-bit PNG。
- 降分辨率渲染（75%）+ `grade.py` 里 Lanczos 放大到 1080p，比提采样划算。

## 静帧（所有图像都走这里）
- 单帧：`-- <out_dir> <samples> <res%> doc <SHOT> frame <n>`，`n` 是镜头内偏移（`f0 + n`），也可 `mid/first/last`；输出 `<out_dir>/<SHOT>_<全局帧号>.png`。S4、S6 带涟漪模拟，单帧也会从模拟起点步进到目标帧，比别的镜头慢。
- 采样：宽景 128，微距 / 拉焦 256；视频那套"75% + 32 spp"不要用在静帧上。
- 尺寸：`build_westlake.py` 写死 1920×1080 × `res%`。高清改 `res%`（134 ≈ 2570×1450）或直接改 `resolution_x/y`；3:4 竖图（1440×1920）必须改 `resolution_x/y` 并重摆相机（竖幅视角变窄，焦段往短调一档），不要从横图裁。
- 调色必须 `GRADE_KEEP=1 python grade.py in.png out.jpg`，否则 `grade.py` 会把图缩放成 1920×1080（竖图会被压扁）。

## 相机方向（最常见的第一个坑）
- `rotation_euler.x`：90° 是水平看，**小于 90° 是低头**，大于 90° 是抬头。更稳的做法：`(target - cam.location).to_track_quat("-Z", "Y").to_euler()`，直接对准一个目标点。

## 脚本工程
- Windows 上 heredoc 打补丁容易被 CRLF 和引号坑：补丁写成独立 .py 文件，用 `assert old in s` 再替换。
- 会话崩溃曾把 `doc_shots.py` 写成全 NUL：重要脚本定期备份到 `backup/`。
- 杀进程只杀本项目的：按命令行里的项目路径过滤（Windows：`Get-CimInstance Win32_Process -Filter "name='blender.exe'"` 再看 CommandLine；Linux / macOS：`pgrep -af blender`）。
- 补丁别堆成几十个 `patch_*.py` / `fix_*.py`：直接改主脚本、用 git 管版本。上海那次项目目录里有 70 多个一次性补丁脚本，谁也说不清最终场景由哪些补丁组成。
