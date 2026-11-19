#!/usr/bin/env bash
# three.js 效果视频（10 s）：调色 → 按剪辑顺序拼帧 → 从 r2 混音里截对应片段 → 片尾标题 → mp4
set -e
cd "$(dirname "$0")/.."
OUT="西湖晨_threejs效果_10s.mp4"
SEQ=renders/three/video_seq
rm -rf "$SEQ"; mkdir -p "$SEQ"
# shot first last  (与 jobs_video.json 一致)
CUTS="S2 109 168
S1 25 72
S5 535 594
S4 402 437
S8 880 915"
n=1
while read -r S A B; do
  python grade.py --dir "renders/three/video/$S" "renders/three/video_g/$S" > /dev/null
  for f in $(seq "$A" "$B"); do
    cp "renders/three/video_g/$S/f_$(printf %04d "$f").png" "$SEQ/f_$(printf %04d $n).png"
    n=$((n + 1))
  done
done <<< "$CUTS"
echo "sequence frames: $((n - 1))"

# 声音：截取 r2 混音里与每个镜头同一时刻的片段（原帧号 → 秒），短交叉淡化后拼接
python - <<'EOF'
import subprocess
cuts = [("S2", 109, 168), ("S1", 25, 72), ("S5", 535, 594), ("S4", 402, 437), ("S8", 880, 915)]
ins, fl = [], []
X = 0.12
for i, (_, a, b) in enumerate(cuts):
    st = (a - 1) / 24; ln = (b - a + 1) / 24 + (X if i < len(cuts) - 1 else 0)
    ins += ["-ss", f"{st:.3f}", "-t", f"{ln:.3f}", "-i", "sfx/mix.wav"]
chain = "[0:a]"
for i in range(1, len(cuts)):
    chain_out = f"[x{i}]"
    fl.append(f"{chain}[{i}:a]acrossfade=d={X}:c1=tri:c2=tri{chain_out}")
    chain = chain_out
fl.append(f"{chain}atrim=0:10,afade=t=in:d=0.6,afade=t=out:st=8.8:d=1.2,loudnorm=I=-18:TP=-2[out]")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fl), "-map", "[out]",
                "-ar", "48000", "sfx/mix_10s.wav"], check=True)
print("audio ok")
EOF

ffmpeg -y -loglevel error -framerate 24 -i "$SEQ/f_%04d.png" -loop 1 -framerate 24 -i titles/endtitle.png -i sfx/mix_10s.wav \
  -filter_complex "[1:v]format=rgba,trim=duration=10,fade=t=in:st=8.4:d=0.9:alpha=1[et];\
[0:v][et]overlay=0:0:format=auto,fade=t=in:st=0:d=0.6,fade=t=out:st=9.4:d=0.6,format=yuv420p[v]" \
  -map "[v]" -map 2:a -t 10 -c:v libx264 -preset slow -crf 16 -c:a aac -b:a 192k -movflags +faststart "$OUT"
ls -la "$OUT"
