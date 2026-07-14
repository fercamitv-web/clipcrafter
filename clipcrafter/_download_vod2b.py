"""Download longer VOD2 clips via yt-dlp python -m module"""
import subprocess, os, sys

out = os.path.expanduser("~/clipcrafter_downloads/clipes2")
os.makedirs(out, exist_ok=True)
url = "https://youtube.com/watch?v=0xHD5y_weH0"

# Find the temp venv python
venv_dir = os.path.join(os.environ.get("TEMP", "C:/Temp"), "yt_env")
python_exe = os.path.join(venv_dir, "Scripts", "python.exe")

segments = [
    (67*60+30, 68*60+5,  "v2_09_clutch_long"),
    (69*60+42, 70*60+15, "v2_10_play_long"),
    (71*60+5,  71*60+40, "v2_11_momento_long"),
    (80*60+18, 80*60+48, "v2_12_jogada_long"),
    (96*60+33, 97*60+0,  "v2_13_highlight_long"),
    (104*60+35,105*60+5, "v2_14_insano_long"),
    (111*60+45,112*60+20,"v2_15_final_long"),
]

for start, end, label in segments:
    path = os.path.join(out, f"{label}.mp4")
    if os.path.exists(path) and os.path.getsize(path) > 50000:
        print(f"SKIP {label}")
        continue
    dur = end - start
    print(f"Download {label} at {start//60}:{start%60:02d} ({dur}s)...", end=" ", flush=True)
    r = subprocess.run([
        python_exe, "-m", "yt_dlp",
        "-f", "18",
        "--download-sections", f"*{start}-{end}",
        "--force-keyframes-at-cuts",
        "-o", path, url
    ], capture_output=True, text=True, timeout=120)
    if os.path.exists(path) and os.path.getsize(path) > 50000:
        print(f"OK ({os.path.getsize(path)/1e6:.1f}MB)")
    else:
        err = (r.stderr or "")[-300:].strip()
        print(f"FAIL: {err or 'no output'}")
