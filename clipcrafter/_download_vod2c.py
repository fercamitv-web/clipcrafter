"""Download remaining VOD2 clips"""
import subprocess, os

out = os.path.expanduser("~/clipcrafter_downloads/clipes2")
os.makedirs(out, exist_ok=True)
url = "https://youtube.com/watch?v=0xHD5y_weH0"
yt_py = os.path.join(os.environ["TEMP"], "yt_env", "Scripts", "python.exe")

segs = [
    (72*60+33, 73*60+15, "v2_16_clutch2"),
    (74*60+55, 75*60+10, "v2_17_momento4"),
    (82*60+15, 82*60+30, "v2_18_play4"),
    (91*60+7,  91*60+20, "v2_19_jogada3"),
    (98*60+28, 99*60+18, "v2_20_highlight3"),
    (103*60+25,103*60+40, "v2_21_insano2"),
    (109*60+14,109*60+28, "v2_22_final2"),
    (114*60+42,114*60+55, "v2_23_extra"),
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
