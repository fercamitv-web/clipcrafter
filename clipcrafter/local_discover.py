"""Run this locally to discover new videos, process clips, and push to repo.
Usage: python clipcrafter/local_discover.py

Requires: yt-dlp, deno/node, ffmpeg, numpy, pydub, requests
"""
import json, os, sys, subprocess, time, gc, shutil
from pathlib import Path

CI_DIR = Path(__file__).resolve().parent
REPO_DIR = CI_DIR.parent
QUEUE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "clip_queue.json"
CLIPS_DIR = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "clips"
WORK_DIR = Path.home() / ".clipcrafter" / "ci_work"
WORK_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CI_DIR))

def log(msg, end="\n"):
    print(msg, end=end, flush=True)

def load_queue():
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    return []

def save_queue(queue):
    QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

def already_processed(vid, queue):
    return any(e.get("vod_id") == vid for e in queue)

def main():
    from auto_clipper import discover_vods, download_audio, download_clip, process_clip, detect_viral_fast
    from content_detector import detect_game

    print("=" * 60)
    print("LOCAL DISCOVER - Processing unprocessed videos")
    print("=" * 60)

    queue = load_queue()

    all_vods = discover_vods()
    if not all_vods:
        print("No videos found!")
        return

    print(f"Found {len(all_vods)} videos total")

    unprocessed = [(vid, dur, title) for vid, dur, title in all_vods if not already_processed(vid, queue)]
    print(f"Unprocessed: {len(unprocessed)} videos")

    if not unprocessed:
        print("All videos already processed!")
        return

    for i, (vid, dur, title) in enumerate(unprocessed[:5]):
        print(f"\n{'='*50}")
        print(f"Video {i+1}/{min(5, len(unprocessed))}: {vid} ({dur//60}:{dur%60:02d}) - {title[:70]}")
        print(f"{'='*50}")

        game = detect_game(title)
        print(f"Game: {game}")

        vod_dir = WORK_DIR / vid
        clips_dir_v = vod_dir / "clips"
        processed_dir = vod_dir / "processed"
        vod_dir.mkdir(parents=True, exist_ok=True)
        clips_dir_v.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)

        print("Downloading audio...", end=" ")
        audio_path = download_audio(vid, str(vod_dir))
        if not audio_path:
            print("FAIL")
            continue
        size_kb = os.path.getsize(audio_path) // 1024
        print(f"OK ({size_kb} KB)")

        print("Detecting viral moments...", end=" ")
        t0 = time.time()
        segs = detect_viral_fast(audio_path, dur, sensitivity=0.35, top_n=12, speech_weight=0.6)
        print(f"{len(segs)} segments ({time.time()-t0:.0f}s)")
        for s in segs[:3]:
            m, sec = divmod(int(s.start_sec), 60)
            print(f"  {m:02d}:{sec:02d} ({s.end_sec-s.start_sec:.0f}s) sc={s.score:.3f} | {s.reason}")

        if not segs:
            print("No segments found, skipping")
            continue

        clip_paths = []
        for si, seg in enumerate(segs[:10]):
            clip_file = clips_dir_v / f"raw_seg{si+1:02d}.mp4"
            out_path = str(clip_file)
            print(f"  Downloading clip {si+1} ({seg.start_sec:.0f}s-{seg.end_sec:.0f}s)...", end=" ")
            if download_clip(vid, seg.start_sec, seg.end_sec, out_path):
                print(f"OK ({os.path.getsize(out_path)//1024}KB)")
                clip_paths.append(out_path)
            else:
                print("FAIL")

        if not clip_paths:
            print("No clips downloaded, skipping")
            continue

        for cp in clip_paths:
            clip_name = f"final_{vid}_{Path(cp).name.replace('raw_', '')}"
            dst = CLIPS_DIR / clip_name
            result = process_clip(cp, str(dst), game, is_short=True, add_intro=True, add_outro=True)
            if result:
                queue.append({
                    "clip_file": clip_name,
                    "vod_id": vid,
                    "game": game,
                    "uploaded_youtube": False,
                    "uploaded_tiktok": False,
                })
                print(f"  Processed -> {clip_name}")
            else:
                print(f"  Failed to process {cp}")
                continue

        print(f"Queue now has {len(queue)} clips")

        gc.collect()

    save_queue(queue)
    print(f"\n{'='*60}")
    print(f"Done! Total queue: {len(queue)} clips")
    print(f"{'='*60}")

    # Git commit and push
    print("\nCommitting changes to repo...")
    subprocess.run(["git", "add", str(CLIPS_DIR), str(QUEUE_FILE)], cwd=REPO_DIR)
    r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_DIR)
    if r.returncode != 0:
        subprocess.run(["git", "commit", "-m", f"Local discover: add {len(queue)} clips to queue"], cwd=REPO_DIR)
        subprocess.run(["git", "push"], cwd=REPO_DIR)
        print("Pushed to GitHub!")
    else:
        print("No changes to commit")

if __name__ == "__main__":
    main()
