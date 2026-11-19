# 审稿：realistic-3d-scene-film（2026-11-17）

审稿人：独立窗口的 Claude，没看过《西湖·晨》那次对话。读了 `SKILL.md`、`references/*.md`，抽查了 `scripts/` 的参数入口、路径、关键函数（`build_westlake.py` 头尾、`doc_shots.py` 相机和渲染循环、`grade.py` 全文、全部 .sh / .mjs），对照了同仓库的 `game-look-micro-film`、`vibe` 和项目目录 `westlake-3d/` 的实际布局。

## 改前总分：66 / 100

| 分项 | 满分 | 得分 | 理由 |
|---|---|---|---|
| 触发描述 | 15 | 11 | 正向触发词写得具体，也给了到 game-look / vibe 的分流。但「用 three.js 渲染」「渲染太慢怎么提速」「做个 3D 场景」太宽：做网页交互 3D、游戏场景、产品渲染，或者 Remotion 渲染慢的时候都会被误选。漏了一些自然说法：Cycles、程序化建模、风景壁纸 / 海报、雪山 / 海边 / 古镇这类别的地点。 |
| 可执行性 | 25 | 14 | 流程、审美、数字都有，但**照着 scripts/ 跑不起来**：脚本是从扁平的项目目录拆进 `blender/ post/ threejs/` 三个子目录的，彼此之间的相对路径全断了（见问题 1）。"图像一律 Blender"却没有出单张静帧、高分辨率、3:4 竖图的做法，`grade.py` 还会把非 1920×1080 的图强制拉成 1080p（见问题 2）。没有环境自检步骤（Blender 路径、GPU、ffmpeg、Node/Chrome 都写死在脚本里）。 |
| 准确性和内部一致性 | 15 | 10 | 镜头表的焦段 / 光圈和 `doc_shots.py` 对得上，耗时数字前后一致。但：文件地图暗示这些脚本能直接用；`frame <n>` 其实是"镜头内偏移"而不是全局帧号，没写；`testgrid.sh` 默认读的 `jobs_test.json` 没复制进来；`package.json` 的包名叫 `three`，在新目录 `npm i three` 会被 npm 以 ENOSELF 拒绝；`night.sh` 里写死了等 "done S2"、按目录名 `westlake-3d` 过滤进程。 |
| 用户偏好和审美规则 | 15 | 13 | 第 0 节用原话 → 做法的表格，很好，冲突优先级也写了。扣分：最硬的"图像一律 Blender"放在表格最后一行；交付前自查清单里没有"AI 生成标注"和"图是不是 Cycles 出的"；"不用配乐"埋在一个单元格里。 |
| 结构和篇幅 | 15 | 11 | SKILL.md 12.5 KB，和仓库其他 skill 同量级，写法直白有数字。但 three.js 明明是辅助，第 5 节却占了约 30% 篇幅，对比表和管线细节应该下沉到 `threejs.md`。缺一个"换地点怎么做"的入口。 |
| 可复用性 | 15 | 7 | 开头说了"地名、镜头、文件名都是例子"，但没说**哪些是通用的、哪些要换**。`build_westlake.py` 里断桥、雷峰塔、三潭、太阳方位、物体坐标、`SHOTS` 帧表、`mix_audio.py` 的声音文件名、`make_titles.py` 的字幕文字、`assemble.sh` 的输出文件名和 40 秒时长都是西湖专用，没有标注，也没有换场景的步骤。 |

## 问题清单（按严重程度）

### 严重：不改的话，新窗口照着做会卡住或出错

1. **scripts/ 拆目录后彼此引用全断。** 位置：`scripts/` 全部。
   - `threejs/export_three.py` 用 `ROOT/build_westlake.py`（期望在 `three/` 的上一级），而它现在在 `scripts/blender/`。
   - `blender/night.sh` 调 `./assemble.sh`，它在 `post/`；`post/assemble.sh` 读 `renders/doc`、`titles/`、`sfx/`，这些都在项目根。
   - `threejs/make_video.sh` `cd ..` 后调 `grade.py`；`threejs/peek.py` 从上一级 `import grade`。
   - `post/make_titles.py`、`post/mix_audio.py` 用 `HERE/../assets/...`，指的是仓库根的 `assets/`；声音文件 `sfx/fs_*.mp3` 在 `westlake-3d/sfx/`，skill 里没有。
   - `build_westlake.py` 把 `.blend` 存到脚本所在目录，直接在 skill 目录里跑会把几百 MB 的文件写进 skill。
   - 改法：`scripts/README.md` 写清"先把脚本平铺复制到新项目目录（与 `westlake-3d/` 同结构）再跑"，给出目录树和复制命令，逐个列出写死的路径。SKILL.md 文件地图加一句同样的提醒。

2. **"图像一律 Blender"没有出图的具体做法。** 位置：SKILL.md 第 7 节、`references/blender.md`。
   - 出单帧要用 `doc <SHOT> frame <n>`，`n` 是镜头内偏移（S2 的 `frame 12` = 全局第 109 帧），也接受 `mid / first / last`；S4、S6 会从涟漪模拟起点顺序步进，单帧也要等。
   - 高分辨率靠 `res%` 超过 100（`134` ≈ 2570×1450；要整好 2560×1440 就直接改 `resolution_x/y`）；分辨率 1920×1080 写死在 `build_westlake.py`，3:4 竖图要改 `resolution_x/y` 并重新构图，不能只裁。
   - `grade.py` 遇到非 1920×1080 一律 Lanczos 缩放到 1920×1080：高清图会被缩小，竖图会被压扁。必须加 `GRADE_KEEP=1`。
   - Cycles 九宫格怎么拼也没写（`testgrid.sh` 里的拼图片段只给 three.js 用）。
   - 改法：SKILL.md 第 7 节加"出图命令"小节；`blender.md` 加"静帧"一节；README 给拼九宫格的命令。

### 重要

3. **没有"换个地点怎么做"。** 位置：SKILL.md 第 1、2 节，缺 reference。改法：新增 `references/adapt.md`，把 `build_westlake.py` / `doc_shots.py` 分成"通用工具（直接留）"和"西湖专用（要换）"两张表，给出换场景的步骤和先后顺序（定一刻 → 改太阳 → 换地标 → 英雄图 → 分镜表 → 声音表 → 字幕）。SKILL.md 第 1 节指过去。

4. **缺环境自检。** 位置：SKILL.md 第 2 节、`render_all.sh`（`/d/software_uesful/blender/blender.exe`）、`render.mjs`（Chrome 路径）。项目里的 `probe.py`（打印 Blender 5.x 天空 / Principled / 体积节点的枚举和输入名、可用 GPU）没复制进来，而 Blender 版本一变 API 名就变。改法：SKILL.md 加"开工前自检"一条；README 列出要改的写死路径；把 `probe.py` 复制进 `scripts/blender/`。

5. **触发描述过宽也有漏。** 位置：SKILL.md frontmatter。改法：重写 description，加入 Cycles、程序化建模、风景静帧 / 壁纸、其他地点举例；明确不用于网页交互 3D、游戏 / 产品 / 角色建模、Remotion 渲染提速；去掉多余空格。

6. **硬规则不够醒目，自查清单漏项。** 位置：SKILL.md 第 0、8 节。改法：第 0 节表格前放 4 条硬规则（Blender 出所有图、默认无人、动物小而远 / 自发光克制、AI 生成标注）；第 8 节加"所有图来自 Cycles""文案写明 AI 生成、发布勾选声明""无配乐"三项。

### 一般

7. **three.js 篇幅喧宾夺主。** 位置：SKILL.md 第 5 节。改法：SKILL.md 只留分工规则、什么时候用、流程五步的一行版和实测数字；对比表、"为什么这样分工"移到 `threejs.md` 开头。

8. **自查方法没写。** 白鹭像摆件、塔孔像眼睛都是"审片时自查"发现的，但没说怎么查。改法：第 8 节加"用 Read 看渲出的帧：先看九宫格整体，再 100% 裁切看动物、发光体、接地处"。

9. **`night.sh` 的项目专用细节没标注。** 等 `done S2`（当晚补渲的最后一镜，不是 `render_all.sh` 默认顺序的最后一镜 S6）、按 `westlake-3d` 过滤进程、`NEED` 帧数表、Git Bash 下要写 `shutdown //s`。改法：README 列出，换项目必改。

10. **`threejs/package.json` 包名是 `three`。** 新目录里 `npm i three` 会报 ENOSELF。改法：包名改成 `scene-three-renderer`（只改 name 字段，不动逻辑），`threejs.md` 安装说明同步。

11. **缺 jobs 示例。** `testgrid.sh` 默认读 `jobs_test.json`，skill 里没有。改法：从项目复制 `jobs_test.json` 当示例，README 写字段含义。

### 小问题

12. description 在中文句子中间换行，YAML 折叠后变成多余空格（加载后显示为"静帧、 纪录片式"）；第 9 节文件地图没写 `make_titles.py` 依赖仓库字体 `assets/fonts/`。

---

## 已做的修改（2026-11-17）

没有改任何脚本逻辑，也没有动 `westlake-3d/`。改动范围：`SKILL.md`、`references/blender.md`、`references/threejs.md`，新增 `references/adapt.md`、`scripts/README.md`；从项目复制了 `scripts/blender/probe.py`（加了两行用法注释）和 `scripts/threejs/jobs_test.json`；`scripts/threejs/package.json` 只改了 `name` 字段。

| # | 问题 | 处理 |
|---|---|---|
| 1 | scripts/ 拆目录后引用全断 | **已改。** 新增 `scripts/README.md`：说明不能原地跑；给出平铺后的目录树（项目放在仓库根下，和 `assets/` 同级）和复制命令；一张表列出每个脚本写死的路径、名字、帧数和改法。SKILL.md 开头和第 9 节都提示先读它。 |
| 2 | 没有用 Blender 出静帧的做法 | **已改。** SKILL.md 第 7 节改为"静帧和小红书图文（全部用 Cycles）"，写了单帧命令、`frame <n>` 是镜头内偏移、静帧采样（128 / 256）、高分辨率和 3:4 竖图要改 `resolution_x/y` 并重新构图、调色必须 `GRADE_KEEP=1`。`blender.md` 加"静帧"一节；README 给了 Cycles 九宫格拼图命令。第 4 节注明"75% + 32 spp"只用于视频帧。 |
| 3 | 没有换地点的方法 | **已改。** 新增 `references/adapt.md`：7 步改造顺序（每步出图给用户看），`build_westlake.py` / `doc_shots.py` 的"留 / 换"对照表，three.js 侧按材质名挑着色、名字对不上会悄悄失效的提醒，以及换场景最容易犯的 4 个错。 |
| 4 | 缺环境自检 | **已改。** SKILL.md 第 1 节加第 0 步"环境自检"；复制 `probe.py` 并加用法注释；`blender.md` 说明 `setin()` 遇到对不上的输入名会静默跳过，所以换版本要先跑 probe；`threejs.md` 写明 Chrome 路径写死、看 `[page] GPU:` 日志确认独显。 |
| 5 | 触发描述过宽也有漏 | **已改。** 加了 Cycles、程序化建场景、风景图 / 壁纸、雪景，以及"雪山、海边、古镇、园林也一样"；"渲染太慢怎么提速"限定为"这个 3D 风景片"；明确排除网页交互 3D、游戏场景、产品或角色建模、Remotion 渲染提速；删掉多余空格。 |
| 6 | 硬规则不醒目、自查漏项 | **已改。** 第 0 节表格前放 4 条编号硬规则（Blender 出所有图、默认不放人、动物小而远和自发光克制、AI 生成标注），用户原话保留。第 8 节加了"所有图都是 Cycles 渲的""画面里没有人""没有配乐""文案写明 AI 生成、提醒勾选声明、CC BY 署名"。 |
| 7 | three.js 篇幅喧宾夺主 | **已改。** SKILL.md 第 5 节从约 3.4 KB 压到约 1.4 KB，只留分工、做法一段、实测数字和适用边界；对比表和"为什么这样分工"移到 `threejs.md` 开头，并在那里重申"这里渲出的静帧只能当预演"。 |
| 8 | 没写怎么自查 | **已改。** 第 8 节开头加"用 Read 看渲出来的图：先看九宫格整体，再看单帧原图里的动物、发光体、接地处"。 |
| 9 | `night.sh` 的专用细节 | **已改。** 写进 README 的写死项表（`done S2` 的来由、`westlake-3d` 进程过滤、`NEED` 表、Git Bash 下 `shutdown //s`、关机必须用户授权）；SKILL.md 第 4 节加一句"换项目必改"。 |
| 10 | `package.json` 包名 `three` | **已改。** 改成 `scene-three-renderer`；`threejs.md` 安装说明改成在 `three/` 里 `npm i`，并说明原因。 |
| 11 | 缺 jobs 示例 | **已改。** 复制 `jobs_test.json`（9 个镜头）；`threejs.md` 写明字段含义，特别是 `frames` 是全局帧号（和 Blender 单帧的镜头内偏移不同）。 |
| 12 | 小问题 | **已改。** description 合成一行，折叠空格消失；文件地图注明 `make_titles.py` 字体在仓库 `assets/fonts/`，并加上原项目 `westlake-3d/` 的位置。 |

**没做、留给以后的：**
- 没有在一个新目录里从头跑通整条管线（Blender 渲一镜要几十分钟到几小时，而且用户的 GPU 可能在跑别的任务）。README 里的命令是对着脚本源码核对的（参数解析、输出文件名、相对路径），没有实跑。下次真用到时，第一件事是按 README 平铺后先跑 `probe.py` 和英雄图，把踩到的坑补回 README。
- 脚本仍然是西湖写死的，没有参数化（按要求不重写脚本逻辑）。换场景靠 `adapt.md` 的对照表手改副本。
- 触发描述没有做 eval 实测，只是按措辞判断。

## 改后分数：87 / 100

| 分项 | 满分 | 改前 | 改后 | 说明 |
|---|---|---|---|---|
| 触发描述 | 15 | 11 | 13 | 正反例都齐了；没做触发 eval，留 2 分。 |
| 可执行性 | 25 | 14 | 21 | 有了平铺方法、单帧 / 静帧命令、环境自检、九宫格拼法；没在新目录实跑，留 4 分。 |
| 准确性和内部一致性 | 15 | 10 | 14 | 帧号语义、jobs 格式、包名、写死项都对齐了源码；README 命令未实跑，留 1 分。 |
| 用户偏好和审美规则 | 15 | 13 | 15 | 4 条硬规则置顶，自查清单逐条覆盖。 |
| 结构和篇幅 | 15 | 11 | 12 | three.js 细节下沉了，但加了硬规则、静帧命令和自查后，SKILL.md 从 12.5 KB 涨到约 13.9 KB；还可以再压。 |
| 可复用性 | 15 | 7 | 12 | 有留 / 换对照表和改造顺序；脚本本身仍写死，没有参数化。 |
