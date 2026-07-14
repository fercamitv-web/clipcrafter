"""Analyze all VOD2 clips and show virality metrics"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clip_analyzer import analyze_clip
from valorant_studio import ValorantStudio

vs = ValorantStudio()
base = os.path.expanduser("~/clipcrafter_downloads/clipes2")
names = ["v2_01_early","v2_02_clutch","v2_03_play","v2_04_momento",
         "v2_05_jogada","v2_06_highlight","v2_07_insano","v2_08_final"]

print(f"{'Clip':<20} {'Dur':>5} {'Virality':>8} {'Excite':>7} {'Silence':>7} {'Peaks':>6} {'Cuts':>5}")
print("-"*60)
for c in names:
    p = os.path.join(base, f"{c}.mp4")
    f = analyze_clip(p)
    dr = vs.suggest_duration(f["excitement"]/100)
    print(f"{c:<20} {f['duration']:>5.0f}s {f['virality_score']:>7.0f}/100 {f['excitement']:>6.0f}/100 {f['silence_pct']:>6.0f}% {f['energy_peaks']:>5d} {f['scene_cuts']:>4d}")
    print(f"{'':>20} {'ideal':>5} {dr[0]:.0f}-{dr[1]:.0f}s")
