import subprocess, os, sys

out_dir = os.path.expanduser('~/clipcrafter_downloads/clipes')
os.makedirs(out_dir, exist_ok=True)

url = "https://youtube.com/live/sKyHcON-MHA"

segments = [
    (47*60+20, 47*60+30, "clip_14_clutch3"),
    (52*60+47, 52*60+58, "clip_15_highlight2"),
    (55*60+5,  55*60+18, "clip_16_play3"),
    (61*60+0,  61*60+10, "clip_17_momento3"),
    (94*60+12, 94*60+22, "clip_18_jogada2"),
    (108*60+2, 108*60+22,"clip_19_final3"),
]

for start, end, label in segments:
    output = os.path.join(out_dir, f"{label}.mp4")
    if os.path.exists(output) and os.path.getsize(output) > 10000:
        print(f"SKIP {label}")
        continue
    to = end - start
    print(f"Downloading {label} at {start//60}:{start%60:02d} ({to}s)...")
    r = subprocess.run([
        "yt-dlp", "-q", "-f", "18", "--download-sections", f"*{start}-{end}",
        "--force-keyframes-at-cuts", "-o", output, url
    ], capture_output=True, text=True, timeout=120)
    if os.path.exists(output) and os.path.getsize(output) > 10000:
        print(f"  OK ({os.path.getsize(output)/1e6:.1f}MB)")
    else:
        err = (r.stderr or "")[-200:].strip()
        print(f"  FAIL: {err or 'no output'}")
