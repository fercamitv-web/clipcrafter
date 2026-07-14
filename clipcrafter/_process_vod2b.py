"""Process VOD2 long clips with new ValorantStudio v2 system"""
import sys, os, subprocess, gc, time, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from video_processor import VideoProcessor
from valorant_studio import ValorantStudio

base = os.path.expanduser("~/clipcrafter_downloads/clipes2")
out_dir = os.path.join(base, "processados")
os.makedirs(out_dir, exist_ok=True)
vs = ValorantStudio()

clips = ["v2_09_clutch_long","v2_10_play_long","v2_11_momento_long",
         "v2_12_jogada_long","v2_13_highlight_long","v2_14_insano_long",
         "v2_15_final_long"]

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
        if not proc.load(src):
            print(f"  FAIL load")
            continue

        t0 = time.time()
        ok = proc.export_clip(0, proc.duration, dst,
            shorts_mode=True, viral_audio=True,
            add_subtitles=True, hook_text=None, loop_mode=True,
            add_watermark=True, watermark_text="@CanalPropra",
            gameplay_text="GAMEPLAY FERCAMI")
        elapsed = time.time() - t0

        if ok:
            # Get analysis from the stored attribute
            analysis = getattr(proc, "_analysis", None)
            if analysis and analysis.speech_text:
                # Re-analyze with fresh instance for better SEO
                a2 = vs.analyze_transcript(analysis.speech_text.split(" | "))
                title = vs.generate_seo_title(
                    kill_count=a2.kill_count,
                    event_type=a2.event_type,
                    agent=a2.agent, map_name=a2.map_name,
                    weapon=a2.weapon)
                hook = vs.generate_hook("auto")
                desc, tags = vs.get_description_tags()
            else:
                title = vs.generate_seo_title()
                hook = vs.generate_hook()
                desc, tags = vs.get_description_tags()

            print(f"  OK ({elapsed:.0f}s)")
            print(f"  Title: {title}")
            if hook:
                print(f"  Hook: {hook}")
            results.append({"file": short, "title": title, "hook": hook or "",
                           "desc": desc, "tags": tags})
        else:
            print(f"  FAIL export")
    finally:
        if proc:
            proc.cleanup()
        gc.collect()

meta_path = os.path.join(out_dir, "clips_metadata2.json")
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSalvo: {meta_path}")
print(f"Total: {len(results)}/{len(clips)} processados")
