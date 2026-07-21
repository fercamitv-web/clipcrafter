"""CI script: discover ALL videos, process clips from unprocessed ones, add to queue."""
import json, os, sys, subprocess, time, gc, base64, shutil
from pathlib import Path

CI_DIR = Path(__file__).resolve().parent
REPO_DIR = CI_DIR.parent
QUEUE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "clip_queue.json"
CLIPS_DIR = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "clips"
WORK_DIR = Path.home() / ".clipcrafter" / "ci_work"
WORK_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CI_DIR))

def log(msg):
    print(msg, flush=True)

def load_queue():
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    return []

def save_queue(queue):
    QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

def already_processed(vid, queue):
    for entry in queue:
        if entry.get("vod_id") == vid:
            return True
    return False

def process_one_video(vid, dur, title, queue):
    """Process a single video: download audio, detect, download clips, process, add to queue."""
    from auto_clipper import download_audio, download_clip, process_clip, detect_viral_fast
    from content_detector import detect_game

    game = detect_game(title)
    log(f"\n{'='*50}")
    log(f"Video: {vid} ({dur//60}:{dur%60:02d}) - {title[:70]}")
    log(f"Game: {game}")
    log(f"{'='*50}")

    vod_dir = WORK_DIR / vid
    clips_dir_v = vod_dir / "clips"
    processed_dir = vod_dir / "processed"
    vod_dir.mkdir(parents=True, exist_ok=True)
    clips_dir_v.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Download audio
    log("Downloading audio...", end=" ")
    audio_path = download_audio(vid, str(vod_dir))
    if not audio_path:
        log("FAIL")
        return
    log(f"OK ({os.path.getsize(audio_path)//1024} KB)")

    # Detect viral moments
    log("Detecting viral moments...", end=" ")
    t0 = time.time()
    segs = detect_viral_fast(audio_path, dur, sensitivity=0.35, top_n=12, speech_weight=0.6)
    log(f"{len(segs)} segments ({time.time()-t0:.0f}s)")
    for s in segs[:3]:
        m, sec = divmod(int(s.start_sec), 60)
        log(f"  {m:02d}:{sec:02d} ({s.end_sec-s.start_sec:.0f}s) sc={s.score:.3f} | {s.reason}")

    if not segs:
        log("No segments found, skipping")
        return

    # Download clips
    log("Downloading clips...")
    downloaded = []
    for idx, seg in enumerate(segs[:10]):
        start, end = seg.start_sec, seg.end_sec
        d = end - start
        min_dur, max_dur = 20.0, 50.0
        if d < min_dur:
            extra = (min_dur - d) / 2
            ns = max(0.0, start - extra)
            ne = min(dur, end + extra)
            if ne - ns < min_dur:
                if ns == 0: ne = ns + min_dur
                else: ns = ne - min_dur
            if ne - ns > max_dur:
                m = (ns + ne) / 2
                ns = max(0.0, m - max_dur/2)
                ne = min(dur, m + max_dur/2)
            start, end = ns, ne

        label = f"clip_{idx+1:02d}"
        path = clips_dir_v / f"{label}.mp4"
        log(f"  {label} at {int(start)//60}:{int(start)%60:02d} ({end-start:.0f}s)...", end=" ")
        ok = download_clip(vid, start, end, str(path))
        log("OK" if ok else "FAIL")
        if ok:
            downloaded.append(idx)

    if not downloaded:
        log("No clips downloaded, skipping")
        return

    # Process clips
    log("Processing clips...")
    for idx in downloaded:
        label = f"clip_{idx+1:02d}"
        raw = clips_dir_v / f"{label}.mp4"
        processed = processed_dir / f"{label}_shorts.mp4"
        log(f"  {label}...", end=" ")
        t0 = time.time()
        try:
            ok, clip_title, hook, desc, tags = process_clip(str(raw), str(processed), game)
            if ok:
                dest = CLIPS_DIR / f"{vid}_{label}_shorts.mp4"
                shutil.copy2(processed, dest)
                queue.append({
                    "vod_id": vid,
                    "title": clip_title,
                    "hook": hook or "",
                    "desc": desc or "",
                    "tags": tags or [],
                    "file": f"clipcrafter/scheduled_uploads/clips/{dest.name}",
                })
                log(f"OK ({time.time()-t0:.0f}s) -> {clip_title[:50]}")
            else:
                log(f"FAIL: {clip_title}")
        except Exception as e:
            log(f"ERROR: {e}")
        finally:
            gc.collect()

def main():
    log("=" * 60)
    log("CI DISCOVER - Processing ALL unprocessed videos")
    log("=" * 60)

    from auto_clipper import discover_vods
    queue = load_queue()

    # Discover ALL videos (not livestreams)
    all_vods = discover_vods(
        "https://www.youtube.com/@CanalPropra/videos",
        min_duration=300  # 5 min minimum
    )
    log(f"\nFound {len(all_vods)} videos total")

    if not all_vods:
        log("No videos found")
        return

    # Process unprocessed videos, max 5 per run to avoid CI timeout
    MAX_VIDEOS_PER_RUN = 5
    to_process = []
    for vid, dur, title in all_vods:
        if already_processed(vid, queue):
            continue
        to_process.append((vid, dur, title))
        if len(to_process) >= MAX_VIDEOS_PER_RUN:
            break

    log(f"Unprocessed: {len(to_process)} videos (processing up to {MAX_VIDEOS_PER_RUN} this run)")

    if not to_process:
        log("All videos already processed!")
        return

    # Process each unprocessed video
    processed_count = 0
    for vid, dur, title in to_process:

        try:
            process_one_video(vid, dur, title, queue)
            processed_count += 1

            # Save queue after each video to avoid losing progress
            save_queue(queue)
            log(f"\nQueue now has {len(queue)} clips\n")

        except Exception as e:
            log(f"ERROR processing {vid}: {e}")
            import traceback
            traceback.print_exc()
            continue

    log(f"\n{'='*60}")
    log(f"Done! Processed {processed_count} new videos")
    log(f"Total queue: {len(queue)} clips")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()
