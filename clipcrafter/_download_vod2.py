import subprocess, os

out_dir = os.path.expanduser('~/clipcrafter_downloads/clipes2')
os.makedirs(out_dir, exist_ok=True)
url = "https://youtube.com/watch?v=0xHD5y_weH0"

# Well-spaced best moments from VOD2
segments = [
    (30*60+24, 30*60+34, "v2_01_early"),
    (67*60+50, 68*60+0,  "v2_02_clutch"),
    (68*60+15, 68*60+30, "v2_03_play"),
    (71*60+5,  71*60+35, "v2_04_momento"),
    (80*60+20, 80*60+38, "v2_05_jogada"),
    (96*60+38, 96*60+55, "v2_06_highlight"),
    (104*60+38,104*60+58,"v2_07_insano"),
    (111*60+48,112*60+22,"v2_08_final"),
]

for start, end, label in segments:
    output = os.path.join(out_dir, f"{label}.mp4")
    if os.path.exists(output) and os.path.getsize(output) > 10000:
        print(f"SKIP {label}")
        continue
    dur = end - start
    print(f"Downloading {label} at {start//60}:{start%60:02d} ({dur}s)...", end=" ", flush=True)
    r = subprocess.run([
        "yt-dlp", "-q", "-f", "92", "--download-sections", f"*{start}-{end}",
        "--force-keyframes-at-cuts", "-o", output, url
    ], capture_output=True, text=True, timeout=120)
    if os.path.exists(output) and os.path.getsize(output) > 10000:
        print(f"OK ({os.path.getsize(output)/1e6:.1f}MB)")
    else:
        err = (r.stderr or "")[-200:].strip()
        print(f"FAIL: {err or 'no output'}")
