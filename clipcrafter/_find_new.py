import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viral_detector import detect_viral_moments

wav_path = os.path.expanduser('~/clipcrafter_downloads/vod_audio.wav')
video_duration = 6510

segs, scores, times = detect_viral_moments(
    wav_path, video_duration,
    min_clip_duration=3.0, max_clip_duration=60.0,
    sensitivity=0.5
)

# All clips we already downloaded (start times)
already = [16*60+28, 22*60+50, 25*60+30, 38*60+25, 40*60+0, 52*60+25,
           65*60+20, 68*60+0, 66*60+20, 93*60+40, 105*60+20, 108*60+0, 19*60+50]

def is_new(start_sec, margin=8):
    for a in already:
        if abs(start_sec - a) < margin:
            return False
    return True

# Filter: new, >= 5s, good score
new_segs = [s for s in segs if (s.end_sec-s.start_sec) >= 5 and is_new(s.start_sec)]
new_segs.sort(key=lambda x: x.score, reverse=True)

print(f"Novos segmentos >= 5s disponiveis: {len(new_segs)}")
print()
for i, s in enumerate(new_segs):
    dur = s.end_sec - s.start_sec
    ms = int(s.start_sec//60); ss = int(s.start_sec%60)
    print(f"  {i+1}. {ms:02d}:{ss:02d} ({dur:.0f}s) score={s.score:.4f}")

# Also show by region (clusters)
print("\n--- Agrupados por regiao ---")
new_segs.sort(key=lambda x: x.start_sec)
for s in new_segs:
    dur = s.end_sec - s.start_sec
    ms = int(s.start_sec//60); ss = int(s.start_sec%60)
    print(f"  {ms:02d}:{ss:02d} ({dur:.0f}s) score={s.score:.4f}")
