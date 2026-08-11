"""Upload runner for GitHub Actions CI. Reads from clip_queue.json and uploads clips/day (default 5) to YouTube + TikTok."""
import json, os, sys, base64, random
from pathlib import Path
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))
CI_DIR = Path(__file__).resolve().parent
REPO_DIR = CI_DIR.parent
QUEUE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "clip_queue.json"
STATE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "upload_state.json"

COMMENT_HOOKS = [
    "Qual momento foi o melhor? Comenta aí! 🔥",
    "Você já tinha visto uma jogada assim? Deixa sua opinião! 👇",
    "O que você achou desse momento? Me conta nos comentários! 🎮",
    "Se esse momento fosse com você, o que faria? Comenta! 😅",
]

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

def setup_instagram():
    if not os.environ.get("IG_ACCESS_TOKEN") or not os.environ.get("IG_USER_ID"):
        return None
    from instagram_uploader import upload_video as ig_upload
    return ig_upload

def main():
    sys.path.insert(0, str(CI_DIR))
    yt_upload = setup_youtube()
    tt_upload = setup_tiktok()
    ig_upload = setup_instagram()

    if not yt_upload and not tt_upload and not ig_upload:
        print("No upload targets configured. Need YT_CLIENT_SECRET+YT_TOKEN_PICKLE and/or TT_* and/or IG_* secrets.")
        sys.exit(1)

    queue = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    state = load_state()

    if not queue:
        print("Queue is empty! No more clips to upload.")
        return

    # Remove dead entries (files that don't exist in the repo)
    before = len(queue)
    alive = [c for c in queue if (REPO_DIR / c.get("file", "clipcrafter/scheduled_uploads/clips/" + c.get("clip_file", ""))).exists()]
    if len(alive) < before:
        print(f"Cleaned {before - len(alive)} dead entries from queue")
    queue = alive

    if not queue:
        print("No clips with valid files in queue.")
        return

    cursor = state["cursor"]
    if cursor >= len(queue):
        print(f"All {len(queue)} clips have been uploaded. Queue exhausted.")
        return

    daily_batch = int(os.environ.get("DAILY_BATCH", "3"))
    batch = queue[cursor:cursor + daily_batch]
    remaining = len(queue) - cursor - len(batch)

    today = datetime.now(BRT)
    print(f"Today: {today.strftime('%A %d/%m/%Y')}")
    print(f"Queue: uploading {len(batch)} clips, {remaining} remaining after this batch")
    if yt_upload:
        print("  YouTube: enabled")
    if tt_upload:
        print("  TikTok: enabled")
    if ig_upload:
        print("  Instagram: enabled")

    base_time = today.replace(hour=12, minute=0, second=0, microsecond=0)
    upload_times = [
        base_time.replace(hour=18),
        base_time.replace(hour=20),
        base_time.replace(hour=22),
    ][:len(batch)]

    for i, clip in enumerate(batch):
        publish_dt = upload_times[i]
        publish_iso = publish_dt.replace(tzinfo=BRT).isoformat()
        file_path = REPO_DIR / clip.get("file", "clipcrafter/scheduled_uploads/clips/" + clip.get("clip_file", ""))

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
                try:
                    from youtube_uploader import post_comment
                    comment = random.choice(COMMENT_HOOKS)
                    post_comment(vid, comment.format(**{"title": title}))
                except Exception as e:
                    print(f"    (comment skipped: {e})")
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

        # Instagram Reels upload
        if ig_upload:
            print(f"    -> Instagram...", end=" ", flush=True)
            try:
                ig_id = ig_upload(
                    video_path=str(file_path),
                    title=title,
                    description=desc,
                    tags=tags,
                )
                if ig_id:
                    print(f"OK media_id={ig_id}")
                    results.append(f"ig:{ig_id}")
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
