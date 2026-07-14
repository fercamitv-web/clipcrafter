"""Download top VOD3 clips"""
import subprocess, os

out = os.path.expanduser("~/clipcrafter_downloads/clipes3")
os.makedirs(out, exist_ok=True)
url = "https://youtube.com/watch?v=2ZEba7_AW7I"
yt_py = os.path.join(os.environ["TEMP"], "yt_env", "Scripts", "python.exe")

# Top segments (non-overlapping, selected by score/duration)
# Format: (start_sec, end_sec, label)
top = [
    (76*60+8,  76*60+16,  "v3_01_insano"),
    (76*60+23, 76*60+44,  "v3_02_highlight"),
    (76*60+47, 76*60+57,  "v3_03_clutch"),
    (77*60+28, 77*60+33,  "v3_04_one_tap"),
    (112*60+18,112*60+25, "v3_05_ace"),
    (109*60+49,109*60+56, "v3_06_momento"),
    (32*60+7,  32*60+12,  "v3_07_jogada"),
    (36*60+0,  36*60+13,  "v3_08_multi"),
    (36*60+14, 36*60+27,  "v3_09_play"),
    (74*60+51, 75*60+0,   "v3_10_retake"),
    (31*60+27, 31*60+32,  "v3_11_eco"),
    (14*60+35, 14*60+42,  "v3_12_ability"),
    (60*60+4,  60*60+10,  "v3_13_clutch2"),
    (73*60+43, 73*60+51,  "v3_14_insano2"),
    (47*60+15, 47*60+20,  "v3_15_momento2"),
]

for st, en, label in top:
    path = os.path.join(out, f"{label}.mp4")
    if os.path.exists(path) and os.path.getsize(path) > 50000:
        print(f"SKIP {label}")
        continue
    dur = en - st
    print(f"Download {label} at {st//60}:{st%60:02d} ({dur}s)...", end=" ", flush=True)
    r = subprocess.run([
        yt_py, "-m", "yt_dlp", "-f", "18",
        "--download-sections", f"*{st}-{en}",
        "--force-keyframes-at-cuts", "-o", path, url
    ], capture_output=True, text=True, timeout=120)
    ok = os.path.exists(path) and os.path.getsize(path) > 50000
    if ok:
        print(f"OK ({os.path.getsize(path)/1e6:.1f}MB)")
    else:
        err = (r.stderr or "")[-200:].replace("\n", " ").strip()
        print(f"FAIL: {err or 'no output'}")
