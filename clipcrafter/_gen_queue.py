"""Generate ALL remaining clips from cached VODs for continuous daily posting."""
import json, os, gc, sys, subprocess
from pathlib import Path

sys.path.insert(0, str(Path("clipcrafter").resolve()))
CI_DIR = Path(__file__).resolve().parent
REPO_DIR = CI_DIR.parent

YT_PY = os.environ["TEMP"] + "/yt_env/Scripts/python.exe"
STATE_PATH = Path.home() / ".clipcrafter" / "auto_clipper_state.json"
CACHE_DIR = Path.home() / ".clipcrafter" / "vod_cache"
QUEUE_DIR = REPO_DIR / "clipcrafter" / "scheduled_uploads"
QUEUE_FILE = QUEUE_DIR / "clip_queue.json"
os.environ["PATH"] = f"{os.environ.get('TEMP', 'C:/Temp')}/yt_env/Scripts;{os.environ.get('PATH', '')}"

# Which VODs are cached locally + segments already used in schedule (clip_1..3)
USED_IN_SCHEDULE = {
    "pWOa6rfA8_Q": 3, "PqkyWFFZoZ0": 3, "JUXE-h9GQ4U": 3,
    "Pc81CFT20Jo": 3, "MF7-edYfZyg": 3, "BHcDPU_Srxs": 0,
}

from video_processor import VideoProcessor
from valorant_studio import ValorantStudio

def process_clip(src, dst):
    vs = ValorantStudio()
    proc = VideoProcessor()
    try:
        if not proc.load(str(src)):
            return None
        hook_overlay = vs.generate_hook_overlay()
        ok = proc.export_clip(0, proc.duration, str(dst),
            shorts_mode=True, viral_audio=True,
            add_subtitles=True, hook_text=hook_overlay, loop_mode=True,
            add_watermark=True, watermark_text="@CanalPropra",
            gameplay_text=None)
        if not ok:
            return None
        analysis = getattr(proc, "_analysis", None)
        title, hook, desc, tags = "MOMENTO ABSURDO - Valorant", "", "", []
        if analysis and analysis.speech_text:
            a2 = vs.analyze_transcript(analysis.speech_text.split(" | "))
            title = vs.generate_seo_title(kill_count=a2.kill_count, event_type=a2.event_type,
                agent=a2.agent, map_name=a2.map_name, weapon=a2.weapon)
            hook = vs.generate_hook("auto")
        else:
            title = vs.generate_seo_title()
            hook = vs.generate_hook()
        desc, tags = vs.get_description_tags()
        return {"title": title, "hook": hook, "desc": desc, "tags": tags, "file": str(dst)}
    finally:
        proc.cleanup()
        gc.collect()

def main():
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    vods = state.get("vods", {})
    queue = []

    for vod_id, used_count in USED_IN_SCHEDULE.items():
        vod_info = vods.get(vod_id, {})
        segments = vod_info.get("segments", [])
        vod_duration = vod_info.get("duration", 99999)
        cache_path = CACHE_DIR / f"{vod_id}.mp4"
        if not cache_path.exists() or not segments:
            print(f"Skip {vod_id}: no cache or segments")
            continue

        # Sort segments by score descending, skip already used
        sorted_segs = sorted(segments, key=lambda s: s["score"], reverse=True)
        available = sorted_segs[used_count:]  # skip already-used
        # Limit to top 10 per VOD for quality
        available = available[:10]

        print(f"\n{vod_id}: {len(available)} available segments (skipped {used_count} used)")

        for i, seg in enumerate(available):
            start, end = seg["start"], seg["end"]
            dur = end - start
            # Extend to 20s minimum
            min_dur, max_dur = 20.0, 50.0
            if dur < min_dur:
                extra = (min_dur - dur) / 2
                ns = max(0.0, start - extra)
                ne = min(vod_duration, end + extra)
                if ne - ns < min_dur:
                    if ns == 0: ne = ns + min_dur
                    else: ns = ne - min_dur
                if ne - ns > max_dur:
                    m = (ns + ne) / 2
                    ns = max(0.0, m - max_dur/2)
                    ne = min(vod_duration, m + max_dur/2)
                start, end = ns, ne
                dur = end - start

            label = f"{vod_id}_seg{i+1+used_count:02d}"
            raw = CACHE_DIR / f"raw_{label}.mp4"
            final = CACHE_DIR / f"final_{label}.mp4"

            if not raw.exists():
                print(f"  Extract {label} ({dur:.0f}s)...", end=" ", flush=True)
                r = subprocess.run(["ffmpeg", "-y", "-ss", str(start), "-i", str(cache_path),
                    "-t", str(dur), "-c", "copy", "-avoid_negative_ts", "make_zero", str(raw)],
                    capture_output=True, text=True, timeout=120)
                ok = raw.exists() and raw.stat().st_size > 50000
                print("OK" if ok else "FAIL")
                if not ok: continue
            else:
                print(f"  Raw {label} exists")

            if not final.exists():
                print(f"  Process {label}...", end=" ", flush=True)
                meta = process_clip(raw, final)
                if meta:
                    queue.append(meta)
                    # Save individual meta
                    meta_file = CACHE_DIR / f"meta_{label}.json"
                    meta_file.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
                    print(f"OK -> {meta['title'][:50]}")
                else:
                    print("FAIL")
            else:
                meta_file = CACHE_DIR / f"meta_{label}.json"
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    meta["file"] = str(final)
                    queue.append(meta)
                    print(f"  Final {label} exists (added to queue)")
                else:
                    print(f"  Final {label} exists but no meta (reprocess needed)")

    # Save queue
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    # Copy final and schedule clips to repo, ensure queue has correct paths
    CLIPS_DIR = QUEUE_DIR / "clips"
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Refresh queue entries with correct relative paths for final clips
    import shutil
    for entry in queue:
        if "file" in entry:
            path = Path(entry["file"])
            name = path.name
            dest = CLIPS_DIR / name
            if path.exists() and not dest.exists():
                shutil.copy2(path, dest)
            entry["file"] = str(Path("clipcrafter/scheduled_uploads/clips") / name)

    # 2. Add schedule clips (schedule_*.mp4) not already in queue
    existing_files = {Path(e["file"]).name for e in queue if "file" in e}
    sched_dir = Path.home() / ".clipcrafter" / "schedule_clips"
    for day_dir in sorted(sched_dir.iterdir()):
        if not day_dir.is_dir():
            continue
        for i in range(1, 4):
            meta_file = day_dir / f"meta_{i}.json"
            src = day_dir / f"clip_{i}.mp4"
            if not meta_file.exists() or not src.exists():
                continue
            dest_name = f"schedule_{day_dir.name}_clip{i}.mp4"
            if dest_name in existing_files:
                continue
            dest = CLIPS_DIR / dest_name
            if not dest.exists():
                shutil.copy2(src, dest)
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["file"] = str(Path("clipcrafter/scheduled_uploads/clips") / dest_name)
            queue.append(meta)

    new_queue = []
    seen = set()
    for entry in queue:
        key = entry.get("title", "") + entry.get("file", "")
        if key not in seen:
            seen.add(key)
            new_queue.append(entry)
    QUEUE_FILE.write_text(json.dumps(new_queue, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'='*50}")
    print(f"Total: {len(new_queue)} clips in queue")
    print(f"At 3/day = {len(new_queue)//3} days of content")
    print(f"Queue: {QUEUE_FILE}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
