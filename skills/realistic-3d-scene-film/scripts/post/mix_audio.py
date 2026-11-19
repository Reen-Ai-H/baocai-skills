# 西湖·晨 纪录片声音：环境床 + 按画面落点的真实录音
# 用法: python mix_audio.py  -> sfx/mix.wav (40s, 48k stereo)
import subprocess, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "..", "assets", "sfx")
S = os.path.join(HERE, "sfx")
DUR = 40.0
FPS = 24
def t(frame):              # timeline frame (1-based) -> seconds
    return (frame - 1) / FPS

# (file, src_start, length, at_time, gain_db, extra_filter)
cues = [
    # beds
    (f"{S}/fs_568819_200906-Water-waves-lapping-lake-gentle-c.mp3", 12.0, 40.0, 0.0, -11, "lowpass=f=9000"),
    (f"{S}/fs_614299_Gentle-waves-on-a-lake.mp3", 30.0, 37.0, 3.0, -15, "highpass=f=60"),
    (f"{S}/fs_745273_Bird-ambience-Coniferous-forest-dawn-cho.mp3", 60.0, 38.0, 2.0, -17, "highpass=f=300"),
    (f"{A}/freesound-foley/fs_277023_Birds-in-the-morning-WAV.mp3", 5.0, 14.0, 24.0, -22, "highpass=f=400"),
    # S1 macro: a bead settles
    (f"{A}/asmr-library/T07_water_drops_a.flac", 0.72, 0.5, 2.1, -16, "lowpass=f=7000"),
    # S2 egrets pass overhead-ish: soft wingbeats
    (f"{S}/fs_388973_Lintu-lentoonlähtö-siivet-Bird-takeoff-w.mp3", 0.75, 1.4, 6.6, -24, "lowpass=f=2500"),
    # S3 cut to the pagoda: distant temple bell
    (f"{S}/fs_668647_temple_bell_002-wav.mp3", 0.0, 9.6, t(241) - 0.05, -15,
     "lowpass=f=2600,aecho=0.7:0.6:180|420:0.25|0.15"),
    # S4 fish touches the surface twice
    (f"{A}/asmr-library/T07_water_drops_a.flac", 1.10, 0.25, t(361 + 50), -18, "lowpass=f=5000"),
    (f"{A}/asmr-library/T07_water_drops_a.flac", 2.56, 0.3, t(361 + 89), -20, "lowpass=f=4500"),
    # S5 dragonfly wings flick
    (f"{S}/fs_447319_Dragonfly-wav.mp3", 0.36, 0.85, t(481 + 66), -27, "highpass=f=200"),
    # S6 mallard call + paddling (close lapping, brighter)
    (f"{S}/fs_188376_Duck_quack_1_Sweden-wav.mp3", 7.0, 1.6, t(601) + 1.4, -22, "lowpass=f=5000"),
    (f"{S}/fs_568819_200906-Water-waves-lapping-lake-gentle-c.mp3", 70.0, 5.0, t(601), -19, "highpass=f=500"),
    # S7 breeze in the willows
    (f"{A}/freesound-foley/fs_457318_Autumn-wind-and-dry-leaves-wav.mp3", 8.0, 9.0, t(721) - 0.3, -24,
     "lowpass=f=3500,highpass=f=150"),
]

inputs, chains = [], []
for i, (f, ss, ln, at, gain, extra) in enumerate(cues):
    inputs += ["-ss", f"{ss:.3f}", "-t", f"{ln:.3f}", "-i", f]
    fade = min(0.6, ln / 4)
    fl = (f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,{extra},volume={gain}dB,"
          f"afade=t=in:d={min(0.02 if ln < 2 else fade, ln / 3):.3f},afade=t=out:st={max(0, ln - fade):.3f}:d={fade:.3f},"
          f"adelay={int(at * 1000)}|{int(at * 1000)}[c{i}]")
    chains.append(fl)
mixin = "".join(f"[c{i}]" for i in range(len(cues)))
fc = ";".join(chains) + f";{mixin}amix=inputs={len(cues)}:normalize=0:duration=longest," \
     f"atrim=0:{DUR},afade=t=in:d=1.2,afade=t=out:st={DUR - 2.5}:d=2.5,loudnorm=I=-18:TP=-2:LRA=9[out]"
cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + ["-filter_complex", fc, "-map", "[out]", "-ar", "48000",
                                                          os.path.join(S, "mix.wav")]
subprocess.run(cmd, check=True)
print("mix ok")
