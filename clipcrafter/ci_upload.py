"""Upload runner for GitHub Actions CI. Uploads clips scheduled for today."""
import json, os, sys, base64
from pathlib import Path
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))
CI_DIR = Path(__file__).resolve().parent  # clipcrafter/
REPO_DIR = CI_DIR.parent
SCHEDULE_DIR = REPO_DIR / "clipcrafter" / "scheduled_uploads"

def clean_old_manifest(path):
    """Re-read manifest and produce new metadata from clip_*.mp4 + meta_*.json."""
    clips = []
    i = 1
    while True:
        meta_file = path / f"meta_{i}.json"
        clip_file = path / f"clip_{i}.mp4"
        if not meta_file.exists() or not clip_file.exists():
            break
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        meta["file"] = str(clip_file.resolve())
        clips.append(meta)
        i += 1
    return clips

def today_manifest():
    today = datetime.now(BRT).strftime("%Y-%m-%d")
    day_path = SCHEDULE_DIR / today
    manifest_path = day_path / "_manifest.json"
    if not manifest_path.exists():
        return None
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    m["clips"] = clean_old_manifest(day_path)
    return m

def main():
    # Setup auth from GitHub secrets
    client_secret_b64 = os.environ.get("YT_CLIENT_SECRET")
    token_pickle_b64 = os.environ.get("YT_TOKEN_PICKLE")
    if not client_secret_b64 or not token_pickle_b64:
        print("MISSING SECRETS: YT_CLIENT_SECRET and YT_TOKEN_PICKLE required")
        sys.exit(1)

    clipcrafter_dir = Path.home() / ".clipcrafter"
    clipcrafter_dir.mkdir(parents=True, exist_ok=True)

    cs_path = clipcrafter_dir / "client_secret.json"
    cs_path.write_bytes(base64.b64decode(client_secret_b64))

    tk_path = clipcrafter_dir / "youtube_token.pickle"
    tk_path.write_bytes(base64.b64decode(token_pickle_b64))

    sys.path.insert(0, str(CI_DIR))
    from youtube_uploader import upload_video

    manifest = today_manifest()
    if not manifest:
        print(f"No schedule for today ({datetime.now(BRT).strftime('%Y-%m-%d %A')})")
        return

    clips = manifest["clips"]
    times = manifest["times"]
    print(f"Today: {manifest['day']} — {len(clips)} clips @ {', '.join(times)}")

    for i, clip in enumerate(clips):
        target_time = times[i] if i < len(times) else "12:00"
        # Use publishAt for target time
        hour, minute = target_time.split(":")
        dt = datetime.strptime(f"{manifest['date']} {hour}:{minute}:00", "%Y-%m-%d %H:%M:%S")
        publish_iso = dt.replace(tzinfo=BRT).isoformat()

        file_path = clip["file"]
        if not os.path.exists(file_path):
            print(f"  [{i+1}] MISSING: {file_path}")
            continue

        print(f"  [{i+1}] Upload for {target_time}...", end=" ", flush=True)
        vid = upload_video(
            video_path=file_path,
            title=clip["title"],
            description=clip.get("desc", ""),
            tags=clip.get("tags", ["Valorant"]),
            privacy_status=publish_iso,
        )
        if vid:
            print(f"OK -> https://youtube.com/shorts/{vid}")
        else:
            print("FAIL")
        sys.stdout.flush()

    print("Done!")

if __name__ == "__main__":
    main()
