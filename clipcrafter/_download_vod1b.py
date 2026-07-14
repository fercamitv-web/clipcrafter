"""Download new VOD1 segments"""
import subprocess, os

out = os.path.expanduser("~/clipcrafter_downloads/clipes")
os.makedirs(out, exist_ok=True)
url = "https://youtube.com/watch?v=sKyHcON-MHA"
yt_py = os.path.join(os.environ["TEMP"], "yt_env", "Scripts", "python.exe")

# 6 new non-overlapping segments from VOD1
segs = [
    (23*60+59, 24*60+4,   "clip_20_momento5"),
    (41*60+6,  41*60+11,  "clip_21_jogada4"),
    (66*60+8,  66*60+13,  "clip_22_play5"),
    (66*60+53, 67*60+2,   "clip_23_highlight4"),
    (67*60+9,  67*60+14,  "clip_24_insano3"),
    (67*60+19, 67*60+25,  "clip_25_final3"),
]

for st, en, label in segs:
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
