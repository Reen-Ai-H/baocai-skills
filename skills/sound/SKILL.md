---
name: sound
description: >-
  Use when finding or downloading video sound effects from Freesound (or similar
  real recordings), especially for Foley that should not be code-synthesized.
---
# sound（浙大猫学长 / vibe-motion）

从 Freesound 找真实录音做视频音效。Agent 听不到，靠下载量、评分人数、上传描述和许可证来选。

## 本账号政策

产出视频**不商用**。音效优先真实录音；CC0 直接用，CC-BY 尽量署名，BY-NC 可用。ElevenLabs 与现有素材可继续用；未授权的微信提示音发布前仍建议换掉，并留 `sfx/credits.md`。

## 命令

脚本装在 `/home/box/.claude/skills/sound/scripts/`（CC 项目内也有副本 `.claude/skills/sound/`）。

```bash
S=/home/box/.claude/skills/sound/scripts/sfx.py
python3 $S freesound "<English query>"
python3 $S freesound "<English query>" --license cc0
python3 $S get <dir> fs:<id>...
```

搜索加 `--urls` 可给用户试听预览链接。

## 怎么挑

1. 把画面动作翻成英文关键词（whoosh、paper slide、duct tape 等）。
2. 优先下载量高且贴合的；★评分人数比平均分更可信。
3. 读描述：写了 Zoom / Sound Devices 等设备的更靠谱；写手机麦、嘴拟音的慎用；来源和 cue 对不上的再热门也拒。
4. 用 ffmpeg 查时长、尾音、能量位置，避免「名字 thud、实际是 3 秒轰鸣」。
5. 许可证：CC0 直接用；BY 要署名（`get` 会打印）；商用才需避开 BY-NC（本账号不商用可用）。

超时：`python3 /home/box/.claude/skills/sound/scripts/clash_freesound.py --fix`；仍失败见同目录 `references/local-setup.md`。Freesound 约 80KB/s，一次 `get` 带齐所有 id。

## 和合成器的分工

Foley / 环境 / 道具声走真实录音。合成器只留给音乐性声音（riser、重击垫、极短 UI 反馈）。

来源：https://github.com/vibe-motion/sound
