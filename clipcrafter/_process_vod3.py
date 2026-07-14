"""Process all 15 VOD3 clips"""
import sys, os, time, gc, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from video_processor import VideoProcessor
from valorant_studio import ValorantStudio

base = os.path.expanduser("~/clipcrafter_downloads/clipes3")
out_dir = os.path.join(base, "processados")
os.makedirs(out_dir, exist_ok=True)
vs = ValorantStudio()

clips = [f"v3_{i:02d}_{name}" for i, name in enumerate(
    ["insano","highlight","clutch","one_tap","ace","momento","jogada",
     "multi","play","retake","eco","ability","clutch2","insano2","momento2"], 1)]

results = []
for name in clips:
    short = f"{name}_shorts"
    src = os.path.join(base, f"{name}.mp4")
    dst = os.path.join(out_dir, f"{short}.mp4")
    if os.path.exists(dst) and os.path.getsize(dst) > 200000:
        print(f"SKIP {name}")
        continue
    print(f"\n=== {name} ===", flush=True)
    proc = None
    try:
        proc = VideoProcessor()
        if not proc.load(src):
            print(f"  FAIL load"); results.append({"file": short, "title": name, "hook": "",
                          "desc": "Clip da live! #Valorant #ClipCrafter #CanalPropra", "tags": ["Valorant"]})
            continue
        t0 = time.time()
        ok = proc.export_clip(0, proc.duration, dst,
            shorts_mode=True, viral_audio=True,
            add_subtitles=True, hook_text=None, loop_mode=True,
            add_watermark=True, watermark_text="@CanalPropra",
            gameplay_text="GAMEPLAY FERCAMI")
        elapsed = time.time() - t0
        if ok:
            analysis = getattr(proc, "_analysis", None)
            if analysis and analysis.speech_text:
                a2 = vs.analyze_transcript(analysis.speech_text.split(" | "))
                title = vs.generate_seo_title(kill_count=a2.kill_count, event_type=a2.event_type,
                    agent=a2.agent, map_name=a2.map_name, weapon=a2.weapon)
                hook = vs.generate_hook("auto")
            else:
                title = vs.generate_seo_title(); hook = vs.generate_hook()
            desc, tags = vs.get_description_tags()
            print(f"  OK ({elapsed:.0f}s) | {title}")
            if hook: print(f"  Hook: {hook}")
            results.append({"file": short, "title": title, "hook": hook or "",
                          "desc": desc, "tags": tags})
        else:
            print(f"  FAIL export")
            results.append({"file": short, "title": name, "hook": "",
                          "desc": "Clip da live! #Valorant #ClipCrafter #CanalPropra", "tags": ["Valorant"]})
    finally:
        if proc: proc.cleanup(); gc.collect()

meta_path = os.path.join(out_dir, "clips_metadata_vod3.json")
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nTotal: {len(results)}/15 processados")
