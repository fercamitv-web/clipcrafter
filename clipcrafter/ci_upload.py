"""Upload runner for GitHub Actions CI. Reads from clip_queue.json and uploads 3 clips/day."""
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

def main():
    # Setup auth from GitHub secrets
    client_secret_b64 = os.environ.get("YT_CLIENT_SECRET")
    token_pickle_b64 = os.environ.get("YT_TOKEN_PICKLE")
    if not client_secret_b64 or not token_pickle_b64:
        print("MISSING SECRETS: YT_CLIENT_SECRET and YT_TOKEN_PICKLE required")
        sys.exit(1)

    clipcrafter_dir = Path.home() / ".clipcrafter"
    clipcrafter_dir.mkdir(parents=True, exist_ok=True)
    (clipcrafter_dir / "client_secret.json").write_bytes(base64.b64decode(client_secret_b64))
    (clipcrafter_dir / "youtube_token.pickle").write_bytes(base64.b64decode(token_pickle_b64))

    sys.path.insert(0, str(CI_DIR))
    from youtube_uploader import upload_video

    queue = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    state = load_state()

    if not queue:
        print("Queue is empty! No more clips to upload.")
        return

    cursor = state["cursor"]
    if cursor >= len(queue):
        print(f"All {len(queue)} clips have been uploaded. Queue exhausted.")
        return

    # Take next 3 clips (or remaining if fewer)
    batch = queue[cursor:cursor+3]
    remaining = len(queue) - cursor - len(batch)

    today = datetime.now(BRT)
    print(f"Today: {today.strftime('%A %d/%m/%Y')}")
    print(f"Queue: position {cursor+1}/{len(queue)}, uploading {len(batch)} clips, {remaining} remaining")

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
        if not file_path.exists():
            print(f"  [{i+1}] MISSING: {file_path}")
            continue

        print(f"  [{i+1}] Upload for {publish_dt.hour}:00...", end=" ", flush=True)
        vid = upload_video(
            video_path=str(file_path),
            title=clip["title"],
            description=clip.get("desc", ""),
            tags=clip.get("tags", ["Valorant"]),
            privacy_status=publish_iso,
        )
        if vid:
            print(f"OK -> https://youtube.com/shorts/{vid}")
            state["uploaded"].append({"idx": cursor+i, "vid": vid, "title": clip["title"]})
        else:
            print("FAIL (may hit quota, will retry tomorrow)")
            # Don't advance cursor on failure
            save_state(state)
            sys.exit(0)
        sys.stdout.flush()

    state["cursor"] = cursor + len(batch)
    save_state(state)
    print(f"\nDone! Next cursor at {state['cursor']}/{len(queue)}")

if __name__ == "__main__":
    main()
