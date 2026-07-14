"""Download remaining VOD2 segments (gap fills + new moments)"""
import subprocess, os

out = os.path.expanduser("~/clipcrafter_downloads/clipes2")
os.makedirs(out, exist_ok=True)
url = "https://youtube.com/watch?v=0xHD5y_weH0"
yt_py = os.path.join(os.environ["TEMP"], "yt_env", "Scripts", "python.exe")

segs = [
    (68*60+1,  68*60+17,  "v2_24_gap_fill"),      # 16s - gap between v2_03 and v2_09
    (71*60+10, 71*60+20,  "v2_25_momento5"),       # 10s - before v2_11
    (71*60+27, 71*60+38,  "v2_26_jogada5"),        # 11s - before v2_11
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
