"""Check other VOD"""
import subprocess, json, sys, os

yt = os.path.join(os.environ["TEMP"], "yt_env", "Scripts", "python.exe")
url = "https://youtube.com/watch?v=2ZEba7_AW7I"

for vid, name in [("2ZEba7_AW7I", "VOD3"), ("0jptBKFXf7I", "VOD4"), ("fxDqwSuNIKA", "VOD5")]:
    r = subprocess.run([yt, "-m", "yt_dlp", "-j", f"https://youtube.com/watch?v={vid}"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        d = json.loads(r.stdout)
        title = d["title"]
        if "ferca" in title.lower() or "fercami" in title.lower() or "gameplay" in title.lower():
            dur = d["duration"]
            print(f"{name} {vid}: {dur//60}:{dur%60:02d} - {title}")
    else:
        err = r.stderr.lower()
        if "video unavailable" not in err and "private" not in err:
            pass
