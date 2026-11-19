#!/usr/bin/env python3
"""成片 QC：联系表、响度、近静止。只出数字和图，好坏由人判断。

用法：
  python3 qc.py 成片.mp4 输出目录 [--step 2] [--left 0.36] [--thr 0.6] [--hold 3]

--step  联系表每隔几秒抽一帧
--left  近静止只量画面右边这部分：左侧手机页打字时，主画面可能根本没动
        （0 表示量全画面）
--thr   相邻半秒的平均差低于多少算“没动”（0–255）。默认 0.6 是在带颗粒的母版上校准的；
        压缩很重的分享版数值会偏低，所以要量母版
--hold  连续多少秒没动才列进清单

需要 ffmpeg、numpy。声音好坏量不出来，这里只有响度数字。
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys

import numpy as np


def probe(path):
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'format=duration,size:stream=width,height,r_frame_rate', '-of', 'json', path],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def tc(sec):
    return f'{int(sec // 60)}:{sec % 60:05.2f}'


def contact_sheet(path, out, step, dur):
    n = max(1, math.ceil(dur / step))
    cols = 8
    rows = math.ceil(n / cols)
    dst = os.path.join(out, 'contact.jpg')
    subprocess.run(
        ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', path, '-vf',
         f"fps=1/{step},scale=320:-2,drawtext=text='%{{pts\\:hms}}':x=4:y=4:fontsize=16:"
         f"fontcolor=white:box=1:boxcolor=black@0.6,tile={cols}x{rows}",
         '-frames:v', '1', '-q:v', '3', dst], check=True)
    return dst


def loudness(path):
    """整片响度。真峰值要看编码后的文件，不能只看混音。"""
    err = subprocess.run(
        ['ffmpeg', '-nostdin', '-hide_banner', '-i', path, '-map', '0:a:0', '-af',
         'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    tail = err[err.rfind('Summary:'):]
    grab = lambda pat: float(re.search(pat, tail, re.S).group(1))
    # 每秒的短时响度，用来找全片最响和最静的位置
    series = re.findall(r't:\s*([\d.]+).*?S:\s*(-?[\d.]+|-inf)', err)
    pts = [(float(t), float(s)) for t, s in series if s != '-inf']
    return dict(
        I=grab(r'I:\s*(-?[\d.]+) LUFS'),
        LRA=grab(r'LRA:\s*(-?[\d.]+) LU'),
        TP=grab(r'Peak:\s*(-?[\d.]+) dBFS'),
        loudest=max(pts, key=lambda p: p[1]) if pts else None,
        quietest=min((p for p in pts if p[0] > 3), key=lambda p: p[1]) if pts else None,
    )


def motion(path, left):
    """帧差。先把每半秒的帧平均，再比相邻两块：胶片颗粒被平均掉，慢动作还留得住。"""
    w, h, fps, block = 160, 90, 12, 6
    p = subprocess.Popen(
        ['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf',
         f'fps={fps},scale={w}:{h}:flags=area,format=gray', '-f', 'rawvideo', '-'],
        stdout=subprocess.PIPE)
    x0 = int(w * left)
    frames, prev, diffs = [], None, []
    while True:
        buf = p.stdout.read(w * h)
        if len(buf) < w * h:
            break
        frames.append(np.frombuffer(buf, np.uint8).reshape(h, w)[:, x0:].astype(np.float32))
        if len(frames) == block:
            f = np.mean(frames, 0)
            frames = []
            if prev is not None:
                diffs.append(np.abs(f - prev).mean())
            prev = f
    p.wait()
    return np.array(diffs, float), fps / block


def static_runs(d, fps, thr, hold):
    runs, s = [], None
    for i, still in enumerate(np.append(d < thr, False)):
        if still and s is None:
            s = i
        if not still and s is not None:
            if (i - s) / fps >= hold:
                runs.append((s / fps, i / fps))
            s = None
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--step', type=float, default=2)
    ap.add_argument('--left', type=float, default=.36)
    ap.add_argument('--thr', type=float, default=.6)
    ap.add_argument('--hold', type=float, default=2.5)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    info = probe(a.video)
    dur = float(info['format']['duration'])
    st = info['streams'][0]
    print(f"文件  {st['width']}x{st['height']} {st['r_frame_rate']}  {dur:.2f}s  "
          f"{int(info['format']['size']) / 1e6:.1f} MB")

    print('联系表', contact_sheet(a.video, a.out, a.step, dur))

    lo = loudness(a.video)
    print(f"响度  {lo['I']} LUFS  LRA {lo['LRA']}  真峰值 {lo['TP']} dBFS")
    if lo['loudest']:
        print(f"      短时最响 {lo['loudest'][1]} @ {tc(lo['loudest'][0])}；"
              f"最静 {lo['quietest'][1]} @ {tc(lo['quietest'][0])}"
              '（高潮和静默是不是落在你想要的位置？）')

    d, fps = motion(a.video, a.left)
    q = np.percentile(d, [10, 50, 90]).round(2)
    print(f'半秒差 10/50/90 分位 {q[0]} / {q[1]} / {q[2]}（用来判断 --thr 合不合适）')
    print(f'近静止 {(d < a.thr).mean() * 100:.1f}%（量的是右侧 {100 - a.left * 100:.0f}% 画面，'
          f'阈值 {a.thr}）')
    runs = static_runs(d, fps, a.thr, a.hold)
    print(f'连续 ≥{a.hold}s 没动的段（逐条问：这里是戏需要，还是我没做动作？）：')
    for s, e in sorted(runs, key=lambda r: r[0] - r[1])[:15]:
        print(f'  {tc(s)} – {tc(e)}  {e - s:.1f}s')
    if not runs:
        print('  无')


if __name__ == '__main__':
    sys.exit(main())
