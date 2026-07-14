import json, os

with open(os.path.expanduser('~/.clipcrafter/vod2_segments.json')) as f:
    segs = json.load(f)

long = [s for s in segs if s['dur'] >= 5]
long.sort(key=lambda x: x['start'])

# Merge nearby segments (gap < 10s)
merged = []
current = None
for s in long:
    if current is None:
        current = dict(s)
    elif s['start'] - current['end'] < 10:
        current['end'] = max(current['end'], s['end'])
        current['dur'] = round(current['end'] - current['start'], 1)
        current['score'] = round(max(current['score'], s['score']), 4)
    else:
        merged.append(current)
        current = dict(s)
if current:
    merged.append(current)

merged.sort(key=lambda x: x['score'], reverse=True)

print(f"Merged segments: {len(merged)}")
print(f"\nTop merged segments:")
for i, s in enumerate(merged):
    m, sec = divmod(int(s['start']), 60)
    me, sece = divmod(int(s['end']), 60)
    print(f"  {i+1:2d}. {m:02d}:{sec:02d}-{me:02d}:{sece:02d} ({s['dur']}s) score={s['score']}")

# Filter to reasonable short durations (5-30s) and pick best dozen
good = [s for s in merged if 5 <= s['dur'] <= 45]
good.sort(key=lambda x: x['score'], reverse=True)
print(f"\n\nBest {len(good)} segments (5-45s):")
for i, s in enumerate(good[:12]):
    m, sec = divmod(int(s['start']), 60)
    me, sece = divmod(int(s['end']), 60)
    print(f"  {i+1:2d}. {m:02d}:{sec:02d}-{me:02d}:{sece:02d} ({s['dur']}s) score={s['score']}")
