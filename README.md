# baocai-skills

「包菜的AI宇宙」做图、做视频用的 **Claude Code skill（经验手册）**。

skill 是一份写给 AI 编程助手看的工作手册：遇到对应的活，助手会先读它，再按里面的流程、标准和检查方法去做。这里的每一份都是从真实作品里一轮轮返工总结出来的。

## 有哪些

| skill | 用来做什么 |
|---|---|
| [`realistic-3d-scene-film`](skills/realistic-3d-scene-film/SKILL.md) | 让代码模型写 Python 驱动 Blender，程序化搭写实 3D 场景（风景、城市天际线、地标），用 Cycles 渲成静帧或纪录片式短片；需要快时用 Three.js 出视频。自带细节体检脚本、白模 / 剪影检查方法。 |
| [`vibe`](skills/vibe/SKILL.md) | 无旁白、少文字的 vibe 知识视频（Remotion + Python）：审美标准、协作规矩、工作流程、审片评分表。 |
| [`game-look-micro-film`](skills/game-look-micro-film/SKILL.md) | 游戏感画面、有角色和对白的叙事微电影：选角、分镜、配音、混音、QC。 |
| [`music-explainer-video`](skills/music-explainer-video/SKILL.md) | 音乐知识科普视频（节奏、和弦、音阶、音色……）：结构、选歌、动效和 QC。 |
| [`sound`](skills/sound/SKILL.md) | 从 Freesound 找真实录音做音效，而不是用代码合成。 |

## 怎么装

把 `skills/` 里想要的文件夹复制（或链接）到你的 skill 目录：

- Claude Code：`~/.claude/skills/`
- 其他支持 skill 的助手：放到它读取 skill 的目录

装好后不用特意调用，正常说需求就行，比如「用 Blender 做一张上海外滩的蓝调夜景」。

## 搭配 DeepSeek 用

想让更便宜的 DeepSeek 来干主要的活、你的 AI 助手负责派活和验收，可以配合 [deepseek-bridge](https://github.com/Reen-Ai-H/deepseek-bridge) 使用。两边读同一份 skill，规则改一处，两边同时生效。

## 说明

- 这里只有手册和脚本，**不含**我私有仓库里的字体、音效和角色素材。脚本里提到 `assets/fonts/`、`assets/sfx/` 的地方，请换成你自己的素材。
- 示例里的城市楼块数据来自 OpenStreetMap（© OpenStreetMap contributors）。

## License

MIT
