import sys, os, json, gc, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from video_processor import VideoProcessor
from valorant_studio import ValorantStudio

base = os.path.expanduser('~/clipcrafter_downloads/clipes')
out_dir = os.path.join(base, 'processados')
os.makedirs(out_dir, exist_ok=True)
studio = ValorantStudio()

clips = [
    "clip_14_clutch3",
    "clip_15_highlight2",
    "clip_16_play3",
    "clip_17_momento3",
    "clip_18_jogada2",
    "clip_19_final3",
]

results = []

for raw in clips:
    short = f"{raw}_shorts"
    src = os.path.join(base, f"{raw}.mp4")
    dst = os.path.join(out_dir, f"{short}.mp4")

    if os.path.exists(dst) and os.path.getsize(dst) > 200000:
        print(f"SKIP {raw}")
        continue

    print(f"\n=== {raw} ===", flush=True)
    proc = None
    try:
        proc = VideoProcessor()
        ok = proc.load(src)
        if not ok:
            print(f"  FAIL load")
            continue
        t0 = time.time()
        ok = proc.export_clip(0, proc.duration, dst,
            shorts_mode=True, viral_audio=True,
            add_subtitles=True, hook_text=None, loop_mode=True,
            add_watermark=True, watermark_text='@CanalPropra')
        elapsed = time.time() - t0
        if ok:
            analysis = getattr(proc, '_analysis', None)
            meta = studio.generate_seo_title(analysis) if analysis else {}
            title = meta.get('title', 'HIGHLIGHT')
            hook = meta.get('hook', '')
            event = meta.get('event', 'highlight')
            print(f"  OK ({elapsed:.0f}s) | {event}: {title[:80]}")
            if hook:
                print(f"  Hook: {hook}")
            results.append({"file": short, "title": title, "hook": hook, "event": event})
        else:
            print(f"  FAIL export")
    finally:
        if proc:
            proc.cleanup()
        gc.collect()

meta_path = os.path.join(out_dir, "clips_metadata.json")
with open(meta_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSalvo: {meta_path}")
print(f"Total: {len(results)}/{len(clips)} clips processados")
