"""Upload runner for GitHub Actions CI. Reads from clip_queue.json and uploads 3 clips/day to YouTube + TikTok."""
import json, os, sys, base64
from pathlib import Path
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))
CI_DIR = Path(__file__).resolve().parent
REPO_DIR = CI_DIR.parent
QUEUE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "clip_queue.json"
STATE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "upload_state.json"

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"cursor": 0, "uploaded": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def save_queue(queue):
    QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

def setup_youtube():
    client_secret_b64 = os.environ.get("YT_CLIENT_SECRET")
    token_pickle_b64 = os.environ.get("YT_TOKEN_PICKLE")
    if not client_secret_b64 or not token_pickle_b64:
        return None
    clipcrafter_dir = Path.home() / ".clipcrafter"
    clipcrafter_dir.mkdir(parents=True, exist_ok=True)
    (clipcrafter_dir / "client_secret.json").write_bytes(base64.b64decode(client_secret_b64))
    (clipcrafter_dir / "youtube_token.pickle").write_bytes(base64.b64decode(token_pickle_b64))
    from youtube_uploader import upload_video as yt_upload
    return yt_upload

def setup_tiktok():
    if not os.environ.get("TT_COOKIES"):
        return None
    from tiktok_uploader import upload_video as tt_upload
    return tt_upload

def main():
    sys.path.insert(0, str(CI_DIR))
    yt_upload = setup_youtube()
    tt_upload = setup_tiktok()

    if not yt_upload and not tt_upload:
        print("No upload targets configured. Need YT_CLIENT_SECRET+YT_TOKEN_PICKLE and/or TT_* secrets.")
        sys.exit(1)

    queue = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    state = load_state()

    if not queue:
        print("Queue is empty! No more clips to upload.")
        return

    # Remove dead entries (files that don't exist in the repo)
    before = len(queue)
    queue = [c for c in queue if (REPO_DIR / c["file"]).exists()]
    if len(queue) < before:
        print(f"Cleaned {before - len(queue)} dead entries from queue")
        save_queue(queue)

    if not queue:
        print("No clips with valid files in queue.")
        return

    cursor = state["cursor"]
    if cursor >= len(queue):
        print(f"All {len(queue)} clips have been uploaded. Queue exhausted.")
        return

    batch = queue[cursor:cursor+3]
    remaining = len(queue) - cursor - len(batch)

    today = datetime.now(BRT)
    print(f"Today: {today.strftime('%A %d/%m/%Y')}")
    print(f"Queue: uploading {len(batch)} clips, {remaining} remaining after this batch")
    if yt_upload:
        print("  YouTube: enabled")
    if tt_upload:
        print("  TikTok: enabled")

    base_time = today.replace(hour=12, minute=0, second=0, microsecond=0)
    upload_times = [
        base_time,
        base_time.replace(hour=15),
        base_time.replace(hour=19),
    ]

    for i, clip in enumerate(batch):
        publish_dt = upload_times[i]
        publish_iso = publish_dt.replace(tzinfo=BRT).isoformat()
        file_path = REPO_DIR / clip["file"]

        print(f"  [{i+1}] {clip['title'][:60]}...", flush=True)
        title = clip["title"]
        desc = clip.get("desc", "")
        tags = clip.get("tags", ["Valorant"])
        results = []

        # YouTube upload
        if yt_upload:
            print(f"    -> YouTube ({publish_dt.hour}:00)...", end=" ", flush=True)
            vid = yt_upload(
                video_path=str(file_path),
                title=title,
                description=desc,
                tags=tags,
                privacy_status=publish_iso,
            )
            if vid:
                print(f"OK https://youtube.com/shorts/{vid}")
                results.append(f"yt:{vid}")
            else:
                print("FAIL (quota?)")
                save_state(state)
                sys.exit(0)

        # TikTok upload
        if tt_upload:
            print(f"    -> TikTok...", end=" ", flush=True)
            try:
                hashtags = [t.replace(" ", "") for t in tags[:5]]
                tt_id = tt_upload(
                    video_path=str(file_path),
                    title=title,
                    description=desc,
                    hashtags=hashtags,
                )
                if tt_id:
                    print(f"OK https://tiktok.com/@{tt_id}")
                    results.append(f"tt:{tt_id}")
                else:
                    print("FAIL")
            except Exception as e:
                print(f"FAIL ({e})")

        if results:
            state["uploaded"].append({"idx": cursor + i, "title": title, "platforms": results})
        sys.stdout.flush()

    state["cursor"] = cursor + len(batch)
    save_queue(queue)
    save_state(state)
    print(f"\nDone! Next cursor at {state['cursor']}/{len(queue)}")

if __name__ == "__main__":
    main()
