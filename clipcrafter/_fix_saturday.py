"""Re-run just the Saturday Pc81CFT20Jo VOD (failed earlier)."""
import sys, os, json, gc, subprocess
sys.path.insert(0, r"C:\Users\ferca\OneDrive\Documentos\1\clipcrafter")
from pathlib import Path

YT_PY = os.environ["TEMP"] + "/yt_env/Scripts/python.exe"
VOD_ID = "Pc81CFT20Jo"
VOD_CACHE = Path.home() / ".clipcrafter" / "vod_cache" / f"{VOD_ID}.mp4"
DAY_DIR = Path.home() / ".clipcrafter" / "schedule_clips" / "2026-07-18"
DAY_DIR.mkdir(parents=True, exist_ok=True)
os.environ["PATH"] = f"{os.environ.get('TEMP', 'C:/Temp')}/yt_env/Scripts;{os.environ.get('PATH', '')}"

# Top 3 segments sorted by score
SEGMENTS = [
    (957.0, 965.0, "clip_1"),
    (1866.8, 1872.45, "clip_2"),
    (729.0, 739.0, "clip_3"),
]

def extract(start, end, output):
    dur = end - start
    r = subprocess.run([
        "ffmpeg", "-y", "-ss", str(start), "-i", str(VOD_CACHE),
        "-t", str(dur), "-c", "copy", "-avoid_negative_ts", "make_zero",
        str(output)
    ], capture_output=True, text=True, timeout=120)
    return output.exists() and output.stat().st_size > 50000

from video_processor import VideoProcessor
from valorant_studio import ValorantStudio

def process_clip(src, dst):
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
            print(f"FAIL export")
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

clips = []
for start, end, label in SEGMENTS:
    # Extend to 20s
    min_dur, max_dur = 20.0, 50.0
    dur = end - start
    extra = (min_dur - dur) / 2
    s = max(0.0, start - extra)
    e = end + extra
    if e - s < min_dur:
        if s == 0: e = s + min_dur
        else: s = e - min_dur
    if e - s > max_dur:
        m = (s + e) / 2
        s = max(0.0, m - max_dur/2)
        e = min(1876.0, m + max_dur/2)

    raw = DAY_DIR / f"raw_{label.split('_')[1]}.mp4"
    final = DAY_DIR / f"{label}.mp4"

    if not raw.exists():
        print(f"Extract {label} {int(s)//60}:{int(s)%60:02d}-{int(e)//60}:{int(e)%60:02d} ({e-s:.0f}s)...", end=" ")
        ok = extract(s, e, raw)
        print("OK" if ok else "FAIL")
        if not ok: continue

    print(f"Process {label}...", end=" ")
    meta = process_clip(raw, final)
    if meta:
        clips.append(meta)
        print(f"OK -> {meta['title'][:60]}")
    else:
        print("FAIL")

if clips:
    manifest = DAY_DIR / "_manifest.json"
    for i, mc in enumerate(clips):
        mf = DAY_DIR / f"meta_{i+1}.json"
        mf.write_text(json.dumps(mc, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest.write_text(json.dumps({
        "date": "2026-07-18", "day": "Sab 18/07", "vod_id": VOD_ID,
        "times": ["10:00", "15:00", "19:00"],
        "clips": clips
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(clips)} clips ready at {DAY_DIR}")
else:
    print("\nNo clips generated")
