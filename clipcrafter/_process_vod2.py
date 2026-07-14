"""Process VOD2 clips with FERCAMI GAMEPLAY overlay"""
import sys, os, json, gc, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from video_processor import VideoProcessor
from valorant_studio import ValorantStudio

base = os.path.expanduser('~/clipcrafter_downloads/clipes2')
out_dir = os.path.join(base, 'processados')
os.makedirs(out_dir, exist_ok=True)
studio = ValorantStudio()

clips = [
    "v2_01_early",
    "v2_02_clutch",
    "v2_03_play",
    "v2_04_momento",
    "v2_05_jogada",
    "v2_06_highlight",
    "v2_07_insano",
    "v2_08_final",
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
            add_watermark=True, watermark_text='@CanalPropra',
            gameplay_text='GAMEPLAY FERCAMI')
        elapsed = time.time() - t0
        if ok:
            analysis = getattr(proc, '_analysis', None)
            if analysis:
                title = studio.generate_seo_title(
                    event_type=analysis.event_type,
                    agent=analysis.agent,
                    map_name=analysis.map_name,
                    weapon=analysis.weapon)
                hook = studio.generate_hook("auto")
            else:
                title = "HIGHLIGHT - Tentando Evoluir no Valorant #clip"
                hook = ""
            print(f"  OK ({elapsed:.0f}s) | {title[:80]}")
            if hook:
                print(f"  Hook: {hook}")
            results.append({"file": short, "title": title, "hook": hook if hook else ""})
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
print(f"Total: {len(results)}/{len(clips)} processados")
