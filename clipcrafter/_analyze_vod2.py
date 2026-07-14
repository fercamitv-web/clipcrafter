"""Regenerate metadata for already processed VOD2 clips"""
import sys, os, subprocess, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from valorant_studio import ValorantStudio
from speech_recognizer import transcribe

base = os.path.expanduser('~/clipcrafter_downloads/clipes2')
out_dir = os.path.join(base, 'processados')
studio = ValorantStudio()

clips = [
    "v2_01_early", "v2_02_clutch", "v2_03_play", "v2_04_momento",
    "v2_05_jogada", "v2_06_highlight", "v2_07_insano", "v2_08_final",
]

results = []

for raw in clips:
    src = os.path.join(base, f"{raw}.mp4")
    print(f"\n=== {raw} ===")

    audio_path = src.replace(".mp4", ".wav")
    if not os.path.exists(audio_path):
        subprocess.run(["ffmpeg", "-i", src, "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", "-y", audio_path],
            capture_output=True, text=True)

    transcript = None
    if os.path.exists(audio_path):
        transcript = transcribe(audio_path)

    if transcript:
        full = " | ".join(transcript)
        print(f"  Fala: {full[:100]}")
        analysis = studio.analyze_transcript(full)
        title = studio.generate_seo_title(event_type=analysis.event_type,
                                          agent=analysis.agent,
                                          map_name=analysis.map_name,
                                          weapon=analysis.weapon)
        hook = studio.generate_hook("auto")
        desc, tags = studio.get_description_tags()
        print(f"  Evento: {analysis.event_type}, Kills: {analysis.kill_count}")
    else:
        print(f"  (no transcript)")
        analysis = studio.analyze_transcript([])
        title = studio.generate_seo_title()
        hook = studio.generate_hook()
        desc, tags = studio.get_description_tags()
        print(f"  (sem fala)")

    print(f"  Titulo: {title}")
    print(f"  Hook: {hook}" if hook else "")
    results.append({"file": f"{raw}_shorts", "title": title, "hook": hook or "",
                    "desc": desc, "tags": tags})

meta_path = os.path.join(out_dir, "clips_metadata.json")
with open(meta_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSalvo: {meta_path}")
