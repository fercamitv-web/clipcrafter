"""Diagnose why clips get 0 views"""
import subprocess, json, os, sys
from datetime import datetime, timedelta

yt_py = os.path.join(os.environ["TEMP"], "yt_env", "Scripts", "python.exe")

# Sample a few random clips from our channel
test_ids = [
    "ig3tHeDi_1Y", "F_qwFZygjOI", "VSQSXwPBgf8",  # last uploaded batch
    "GRrsYdJgnXk", "xrTX5wXWLzw", "vJCvlf783N8",  # VOD3 batch
    "7fysWhICP-0", "sApChJttX-4",                  # VOD1 batch
    "b-fHxw9lEb4", "cMJksh4eBI4",                  # VOD2 batch
]

print("=== DIAGNOSE: Why shorts have 0 views ===\n")

# 1. Check video status via yt-dlp
for vid in test_ids:
    url = f"https://youtube.com/watch?v={vid}"
    r = subprocess.run([yt_py, "-m", "yt_dlp", "-j", url],
                       capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        d = json.loads(r.stdout)
        vc = d.get("view_count", 0)
        title = d.get("title", "?")
        upload = d.get("upload_date", "?")
        dur = d.get("duration", 0)
        # Parse upload date
        try:
            up_dt = datetime.strptime(upload, "%Y%m%d")
            age_days = (datetime.now() - up_dt).days
        except:
            age_days = -1
        status = d.get("availability", "public")
        # Count live comments/ratings
        like_count = d.get("like_count", 0)
        comment_count = d.get("comment_count", 0)
        print(f"  {vid}: {vc}v | {like_count}l | {comment_count}c | {age_days}d ago | {status}")
        if vc == 0:
            print(f"    Title: {title[:80]}")
            print(f"    Duration: {dur}s")
    else:
        print(f"  {vid}: ERROR - {r.stderr[:100]}")

# 2. Check channel info
print("\n=== Channel Info ===")
r = subprocess.run([yt_py, "-m", "yt_dlp", "--flat-playlist", "--dump-single-json",
                    "https://www.youtube.com/@CanalPropra/shorts"],
                   capture_output=True, text=True, timeout=60)
if r.returncode == 0:
    data = json.loads(r.stdout)
    entries = data.get("entries", [])
    print(f"Shorts on channel: {len(entries)}")
    # Check recent shorts
    for e in entries[:5]:
        if e:
            print(f"  {e.get('id','?')}: {e.get('view_count',0)}v - {e.get('title','?')[:60]}")
    # How many have >0 views?
    with_views = sum(1 for e in entries if e and e.get("view_count", 0) > 0)
    zero_views = sum(1 for e in entries if e and e.get("view_count", 0) == 0)
    total_views = sum(e.get("view_count", 0) for e in entries if e)
    print(f"  With views: {with_views}, Zero views: {zero_views}, Total: {total_views}")

# 3. Analysis
print("\n=== DIAGNOSIS ===")
print("""
Most likely causes for 0 views on Valorant Shorts:

1. HOOK (most common): 
   - No strong visual/text hook in first 1-2 seconds
   - Valorant gameplay starts slow (no immediate action)
   - "GAMEPLAY FERCAMI" overlay at start wastes critical seconds

2. AUDIENCE SIGNAL:
   - New channel (<30 days?) with no subscriber base
   - Algorithm hasn't found the right seed audience
   - Topics too broad ("Valorant", "gaming")

3. TECHNICAL:
   - Check if videos are truly Public (not Unlisted/Private)
   - Check for age restrictions from voice/audio
   - Processing delay (24h+ for HD)

4. SEO/METADATA:
   - Titles need searchable keywords
   - Descriptions need more context
   - Needs relevant hashtags (#Valorant #Shorts #Gameplay)

5. RETENTION:
   - No pattern interrupts (visual changes every 3-5s)
   - Audio may have dead air
   - Ending doesn't encourage rewatch
""")

# Check for age restriction or content flags
print("\n=== Quick Technical Check ===")
for vid in test_ids[:3]:
    url = f"https://www.youtube.com/shorts/{vid}"
    r = subprocess.run([yt_py, "-m", "yt_dlp", "--print", "%(age_limit)s %(is_live)s",
                        url], capture_output=True, text=True, timeout=15)
    print(f"  {vid}: {r.stdout.strip()}")
