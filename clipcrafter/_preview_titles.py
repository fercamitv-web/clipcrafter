"""Preview SEO metadata for new clips without uploading"""
import sys, os, subprocess, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from valorant_studio import ValorantStudio
from speech_recognizer import transcribe

base = os.path.expanduser('~/clipcrafter_downloads/clipes')
out_dir = os.path.join(base, 'processados')
studio = ValorantStudio()

clips = [
    "clip_14_clutch3",
    "clip_15_highlight2",
    "clip_16_play3",
    "clip_17_momento3",
    "clip_18_jogada2",
    "clip_19_final3",
]

for raw in clips:
    raw_path = os.path.join(base, f"{raw}.mp4")
    if not os.path.exists(raw_path):
        print(f"MISSING {raw}")
        continue

    print(f"\n=== {raw} ===")

    audio_path = raw_path.replace(".mp4", ".wav")
    if not os.path.exists(audio_path):
        subprocess.run(["ffmpeg", "-i", raw_path, "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", "-y", audio_path],
            capture_output=True, text=True)

    transcript = None
    if os.path.exists(audio_path):
        transcript = transcribe(audio_path)

    if transcript:
        full = " | ".join(transcript)
        print(f"  Fala: {full[:120]}")
        analysis = studio.analyze_transcript(full)
        title = studio.generate_seo_title(event_type=analysis.event_type,
                                          agent=analysis.agent,
                                          map_name=analysis.map_name,
                                          weapon=analysis.weapon)
        hook = studio.generate_hook("auto")
        desc, tags = studio.get_description_tags()
        print(f"  Evento: {analysis.event_type}, Kills: {analysis.kill_count}")
    else:
        # Fallback for no transcript
        a = studio.analyze_transcript([])
        title = studio.generate_seo_title()
        hook = studio.generate_hook()
        desc, tags = studio.get_description_tags()
        print(f"  (sem fala)")

    print(f"  Titulo: {title}")
    if hook:
        print(f"  Hook: {hook}")
    print(f"  Tags: {', '.join(tags[:4])}")
