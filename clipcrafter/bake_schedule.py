"""Generate 18 clips (3/day × 6 days) from different VODs at optimal times."""
import json, os, gc, sys, subprocess
from pathlib import Path

YT_PY = str(Path(os.environ["TEMP"]) / "yt_env" / "Scripts" / "python.exe")
STATE_PATH = Path.home() / ".clipcrafter" / "auto_clipper_state.json"
CACHE_DIR = Path.home() / ".clipcrafter" / "vod_cache"
OUT_DIR = Path.home() / ".clipcrafter" / "schedule_clips"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

os.environ["PATH"] = f"{os.environ.get('TEMP', 'C:/Temp')}/yt_env/Scripts;{os.environ.get('PATH', '')}"

SCHEDULE = [
    ("Qua 15/07", "2026-07-15", "pWOa6rfA8_Q", ["12:00", "15:00", "19:00"]),
    ("Qui 16/07", "2026-07-16", "PqkyWFFZoZ0", ["12:00", "19:00", "21:00"]),
    ("Sex 17/07", "2026-07-17", "JUXE-h9GQ4U", ["11:00", "16:00", "19:00"]),
    ("Sab 18/07", "2026-07-18", "Pc81CFT20Jo", ["10:00", "15:00", "19:00"]),
    ("Dom 19/07", "2026-07-19", "MF7-edYfZyg", ["10:00", "16:00", "21:00"]),
    ("Seg 20/07", "2026-07-20", "BHcDPU_Srxs", ["12:00", "18:00", "20:00"]),
]

def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"vods": {}, "completed_vods": []}

def ensure_vod_cached(vod_id):
    """Download full VOD once to cache if not present."""
    cache_path = CACHE_DIR / f"{vod_id}.mp4"
    if cache_path.exists() and cache_path.stat().st_size > 500000:
        return cache_path
    print(f"  Caching full VOD {vod_id}...", end=" ", flush=True)
    r = subprocess.run([
        YT_PY, "-m", "yt_dlp", "--quiet", "--no-warnings",
        "-f", "worstvideo[height>=720]+worstaudio/best[height>=720]",
        "-o", str(cache_path),
        f"https://youtube.com/watch?v={vod_id}"
    ], capture_output=True, text=True, timeout=1200)
    ok = cache_path.exists() and cache_path.stat().st_size > 500000
    print("OK" if ok else "FAIL")
    return cache_path if ok else None

def extract_section(vod_path, start, end, output_path):
    """Extract a section from cached VOD locally using ffmpeg."""
    dur = end - start
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-i", str(vod_path),
        "-t", str(dur), "-c", "copy", "-avoid_negative_ts", "make_zero",
        str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return output_path.exists() and output_path.stat().st_size > 50000

def process_clip(src, dst):
    from video_processor import VideoProcessor
    from valorant_studio import ValorantStudio

    vs = ValorantStudio()
    proc = VideoProcessor()
    try:
        if not proc.load(str(src)):
            print(f"FAIL load {src.name}")
            return None
        hook_overlay = vs.generate_hook_overlay()
        ok = proc.export_clip(0, proc.duration, str(dst),
            shorts_mode=True, viral_audio=True,
            add_subtitles=True, hook_text=hook_overlay, loop_mode=True,
            add_watermark=True, watermark_text="@CanalPropra",
            gameplay_text="GAMEPLAY FERCAMI")
        if not ok:
            print(f"FAIL export {src.name}")
            return None
        analysis = getattr(proc, "_analysis", None)
        title = "MOMENTO ABSURDO - Valorant"
        hook = ""
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

def extend_segment(start, end, vod_duration, min_dur=20.0, max_dur=50.0):
    dur = end - start
    if dur >= min_dur:
        return start, end
    extra = (min_dur - dur) / 2
    new_start = max(0.0, start - extra)
    new_end = min(vod_duration, end + extra)
    if new_end - new_start < min_dur:
        if new_start == 0:
            new_end = new_start + min_dur
        else:
            new_start = new_end - min_dur
    if new_end - new_start > max_dur:
        mid = (new_start + new_end) / 2
        new_start = max(0.0, mid - max_dur/2)
        new_end = min(vod_duration, mid + max_dur/2)
    return new_start, new_end

def main():
    state = load_state()
    summary = []

    for day_label, date_str, vod_id, times in SCHEDULE:
        print(f"\n{'='*60}")
        print(f"  {day_label} ({date_str}) — {vod_id}")
        print(f"  Upload at: {', '.join(times)}")
        print(f"{'='*60}")

        vod_info = state.get("vods", {}).get(vod_id, {})
        segments = vod_info.get("segments", [])
        vod_duration = vod_info.get("duration", 99999)
        if not segments:
            print(f"  NO SEGMENTS for {vod_id}, skipping")
            continue

        # Cache VOD locally first
        vod_path = ensure_vod_cached(vod_id)
        if not vod_path:
            print(f"  FAILED to cache {vod_id}, skipping")
            continue

        sorted_segs = sorted(segments, key=lambda s: s["score"], reverse=True)[:3]
        day_dir = OUT_DIR / date_str
        day_dir.mkdir(parents=True, exist_ok=True)

        day_clips = []
        for i, seg in enumerate(sorted_segs):
            start, end = extend_segment(seg["start"], seg["end"], vod_duration)
            dur = end - start

            raw_path = day_dir / f"raw_{i+1}.mp4"
            final_path = day_dir / f"clip_{i+1}.mp4"

            if not raw_path.exists():
                print(f"  Extract {i+1}/3: {int(start)//60}:{int(start)%60:02d}-{int(end)//60}:{int(end)%60:02d} ({dur:.0f}s)...", end=" ", flush=True)
                ok = extract_section(vod_path, start, end, raw_path)
                if not ok:
                    print("FAIL")
                    continue
                print("OK")
            else:
                print(f"  Raw {i+1}/3 exists")

            if not final_path.exists():
                print(f"  Process {i+1}/3...", end=" ", flush=True)
                meta = process_clip(raw_path, final_path)
                if meta:
                    day_clips.append(meta)
                    print(f"OK -> {meta['title'][:60]}")
                else:
                    print("FAIL")
            else:
                print(f"  Clip {i+1}/3 already processed")
                meta_path = day_dir / f"meta_{i+1}.json"
                if meta_path.exists():
                    day_clips.append(json.loads(meta_path.read_text(encoding="utf-8")))

        if day_clips:
            meta_list = []
            for i, mc in enumerate(day_clips):
                meta_path = day_dir / f"meta_{i+1}.json"
                meta_path.write_text(json.dumps(mc, ensure_ascii=False, indent=2), encoding="utf-8")
                meta_list.append(mc)
            manifest = day_dir / "_manifest.json"
            manifest.write_text(json.dumps({
                "date": date_str, "day": day_label, "vod_id": vod_id,
                "times": times, "clips": meta_list
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            summary.append({"day": day_label, "date": date_str, "vod": vod_id, "times": times, "clips": len(day_clips)})

    print(f"\n\n{'='*60}\nSCHEDULE SUMMARY\n{'='*60}")
    for s in summary:
        print(f"  {s['day']} ({s['date']}): {s['vod']} — {s['clips']} clips @ {', '.join(s['times'])}")
    print(f"\nAll clips in: {OUT_DIR}")

if __name__ == "__main__":
    main()
