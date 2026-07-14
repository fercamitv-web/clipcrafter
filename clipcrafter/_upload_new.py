"""Upload new clips (14-19) to YouTube with SEO-optimized titles"""
import sys, os, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from valorant_studio import ValorantStudio
from speech_recognizer import transcribe
from youtube_uploader import upload_video

base = os.path.expanduser('~/clipcrafter_downloads/clipes')
out_dir = os.path.join(base, 'processados')
secret_file = os.path.expanduser('~/client_secret.json')
os.environ["OAUTH_PATH"] = secret_file
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
    path = os.path.join(out_dir, f"{raw}_shorts.mp4")
    raw_path = os.path.join(base, f"{raw}.mp4")

    if not os.path.exists(path):
        print(f"MISSING {path}")
        continue

    print(f"\n=== {raw} ===")

    # Extract audio from raw clip for transcription
    audio_path = raw_path.replace(".mp4", ".wav")
    if not os.path.exists(audio_path):
        subprocess.run(["ffmpeg", "-i", raw_path, "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", "-y", audio_path],
            capture_output=True, text=True)

    # Transcribe and analyze
    transcript = None
    if os.path.exists(audio_path):
        transcript = transcribe(audio_path)

    if transcript:
        full = " | ".join(transcript)
        print(f"  Fala: {full[:100]}")
        analysis = studio.analyze_transcript(full)
    else:
        print(f"  (no audio)")
        analysis = studio.analyze_transcript([])

    # Generate SEO metadata
    title = studio.generate_seo_title(event_type=analysis.event_type,
                                      agent=analysis.agent,
                                      map_name=analysis.map_name,
                                      weapon=analysis.weapon)
    hook = studio.generate_hook("auto")
    desc, tags = studio.get_description_tags()

    print(f"  Titulo: {title}")
    print(f"  Hook: {hook}" if hook else "")

    # Upload
    print(f"  Uploading...", end=" ", flush=True)
    try:
        vid = upload_video(path, title=title, description=desc,
                          tags=tags, privacy_status="public")
        if vid:
            print(f"OK! https://youtube.com/watch?v={vid}")
        else:
            print("FAILED")
    except Exception as e:
        print(f"ERROR: {e}")
