"""Schedule ALL 18 clips across 6 days in one shot using YouTube publishAt."""
import json, os, sys, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

YT_PY = Path(os.environ["TEMP"]) / "yt_env" / "Scripts" / "python.exe"
BASE = Path.home() / ".clipcrafter" / "schedule_clips"
BRT = timezone(timedelta(hours=-3))  # Brazil time

DAYS = [
    "2026-07-15", "2026-07-16", "2026-07-17",
    "2026-07-18", "2026-07-19", "2026-07-20",
]

def schedule_clip(file_path, title, description, tags, publish_at_iso):
    """Schedule a clip for future publishing via YouTube API."""
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
vid = upload(creds, r"{file_path}", {json.dumps(title)}, {json.dumps(description)},
             {json.dumps(tags)}, "{publish_at_iso}")
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
    print(f"  Error: {out[:300]}")
    return None

def main():
    print("="*60)
    print("  SCHEDULING ALL 18 CLIPS FOR PUBLICATION")
    print("="*60)

    for date_str in DAYS:
        manifest_path = BASE / date_str / "_manifest.json"
        if not manifest_path.exists():
            print(f"\n  No manifest for {date_str}, skipping")
            continue

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        clips = manifest["clips"]
        times = manifest["times"]

        print(f"\n  {manifest['day']} ({date_str}) — {len(clips)} clips @ {', '.join(times)}")

        for i, clip in enumerate(clips):
            target_time = times[i] if i < len(times) else "12:00"
            hour, minute = target_time.split(":")
            dt = datetime.strptime(f"{date_str} {hour}:{minute}:00", "%Y-%m-%d %H:%M:%S")
            dt_brt = dt.replace(tzinfo=BRT)
            publish_iso = dt_brt.isoformat()

            file_path = clip["file"]
            if not os.path.exists(file_path):
                print(f"    [{i+1}] MISSING: {file_path}")
                continue

            print(f"    [{i+1}] Schedule for {target_time} BRT ({publish_iso} UTC)...", end=" ", flush=True)
            vid = schedule_clip(file_path, clip["title"], clip.get("desc", ""),
                               clip.get("tags", ["Valorant"]), publish_iso)
            if vid:
                print(f"OK -> https://youtube.com/shorts/{vid}")
            else:
                print("FAIL")
            sys.stdout.flush()

    print(f"\n{'='*60}")
    print("  DONE!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
