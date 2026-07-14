"""Upload schedule: run daily to post today's 3 clips at optimal times."""
import json, os, sys, time, subprocess
from pathlib import Path
from datetime import date

YT_PY = Path(os.environ["TEMP"]) / "yt_env" / "Scripts" / "python.exe"
BASE = Path.home() / ".clipcrafter" / "schedule_clips"

# Map today's date to schedule day
DATE_MAP = {
    "2026-07-15": ("Qua 15/07", ["12:00", "15:00", "19:00"]),
    "2026-07-16": ("Qui 16/07", ["12:00", "19:00", "21:00"]),
    "2026-07-17": ("Sex 17/07", ["11:00", "16:00", "19:00"]),
    "2026-07-18": ("Sab 18/07", ["10:00", "15:00", "19:00"]),
    "2026-07-19": ("Dom 19/07", ["10:00", "16:00", "21:00"]),
    "2026-07-20": ("Seg 20/07", ["12:00", "18:00", "20:00"]),
}

def upload_clip(file_path, title, description, tags):
    """Upload single clip via YouTube API."""
    cmd = [
        str(YT_PY), "-c",
        f"""
import sys, json
sys.path.insert(0, r"C:\\Users\\ferca\\OneDrive\\Documentos\\1\\clipcrafter")
from youtube_uploader import upload, authenticate
creds = authenticate()
if not creds:
    print("AUTH_FAIL")
    sys.exit(1)
vid = upload(creds, r"{file_path}", "{title}", "{description}", {json.dumps(tags)}, "public")
if vid:
    print(f"OK:{{vid}}")
else:
    print("UPLOAD_FAIL")
"""
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = r.stdout.strip()
    if out.startswith("OK:"):
        return out[3:]
    print(f"  Upload error: {out[:200]}")
    return None

def main():
    today = str(date.today())
    if today not in DATE_MAP:
        print(f"No schedule for today ({today}). Available: {', '.join(DATE_MAP.keys())}")
        return

    day_label, times = DATE_MAP[today]
    manifest_path = BASE / today / "_manifest.json"
    if not manifest_path.exists():
        print(f"No manifest for {today} at {manifest_path}")
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    clips = manifest["clips"]

    print(f"\n{'='*50}")
    print(f"  {day_label} ({today})")
    print(f"  VOD: {manifest['vod_id']}")
    print(f"  Upload schedule: {', '.join(times)}")
    print(f"{'='*50}")
    print()

    for i, clip in enumerate(clips):
        target_time = times[i] if i < len(times) else "?h"
        file_path = clip["file"]

        if not os.path.exists(file_path):
            print(f"  [{i+1}/{len(clips)}] {target_time} — File not found: {file_path}")
            continue

        title = clip["title"]
        desc = clip.get("desc", "")
        tags = clip.get("tags", ["Valorant"])

        print(f"  [{i+1}/{len(clips)}] Uploading for {target_time}...")
        print(f"    Title: {title}")

        vid = upload_clip(file_path, title, desc, tags)
        if vid:
            print(f"    OK -> https://youtube.com/shorts/{vid}")
        else:
            print(f"    FAIL")
        print()

    print("Done for today!")

if __name__ == "__main__":
    main()
