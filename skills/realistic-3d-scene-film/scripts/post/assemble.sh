#!/usr/bin/env bash
# 调色 → 按全局帧号拼接 8 个镜头（硬切）→ 片头字幕 / 片尾片名 → 混音 → 母版 + 分享版
set -e
cd "$(dirname "$0")"
VER=${VER:-r2}
mkdir -p renders/doc_graded
for S in S1 S2 S3 S4 S5 S6 S7 S8; do
  python grade.py --dir "renders/doc/$S" renders/doc_graded
done
n=$(ls renders/doc_graded/f_*.png | wc -l)
echo "graded frames: $n"
python mix_audio.py
OUT="西湖晨_纪录短片_${VER}_母版.mp4"
ffmpeg -y -loglevel error -framerate 24 -start_number 1 -i renders/doc_graded/f_%04d.png \
  -loop 1 -framerate 24 -i titles/lower3.png -loop 1 -framerate 24 -i titles/endtitle.png -i sfx/mix.wav \
  -filter_complex "\
[1:v]format=rgba,trim=duration=40,fade=t=in:st=5.2:d=0.9:alpha=1,fade=t=out:st=8.7:d=0.8:alpha=1[l3];\
[2:v]format=rgba,trim=duration=40,fade=t=in:st=35.6:d=1.4:alpha=1,fade=t=out:st=38.9:d=1.0:alpha=1[et];\
[0:v][l3]overlay=0:0:format=auto[v1];[v1][et]overlay=0:0:format=auto,\
fade=t=in:st=0:d=1.0,fade=t=out:st=39.0:d=1.0,format=yuv420p[v]" \
  -map "[v]" -map 3:a -t 40 -c:v libx264 -preset slow -crf 15 -c:a aac -b:a 256k -movflags +faststart "$OUT"
ffmpeg -y -loglevel error -i "$OUT" -c:v libx264 -preset slow -crf 23 -c:a aac -b:a 160k -movflags +faststart \
  "西湖晨_纪录短片_${VER}_小体积.mp4"
ls -la 西湖晨_纪录短片_${VER}_*.mp4
