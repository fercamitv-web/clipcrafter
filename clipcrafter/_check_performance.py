"""Check YouTube performance data"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["OAUTH_PATH"] = os.path.expanduser("~/client_secret.json")
from performance_tracker import YouTubePerformanceTracker

f = os.path.expanduser("~/.clipcrafter/clip_performance.json")
if os.path.exists(f):
    d = json.load(open(f))
    print(f"Videos in DB: {len(d)}")
    for i, vid in enumerate(list(d.keys())[:5]):
        print(f"  {vid}: {d[vid]}")

tracker = YouTubePerformanceTracker()
stats = tracker.fetch_all_stats()
print(f"\nFetched stats: {len(stats)} videos")

# Sort by views
sorted_vids = sorted(stats.items(), key=lambda x: x[1].get("views", 0), reverse=True)
print("\n=== Top 10 by views ===")
for vid, data in sorted_vids[:10]:
    v = data.get("views", 0)
    l = data.get("likes", 0)
    c = data.get("comments", 0)
    print(f"  {vid}: {v} views, {l} likes, {c} comments")

print("\n=== Bottom 10 (zero view) ===")
zero_count = 0
for vid, data in sorted_vids:
    if data.get("views", 0) == 0:
        zero_count += 1
        if zero_count <= 10:
            print(f"  {vid}: {data}")
print(f"\nTotal with 0 views: {zero_count}/{len(stats)}")

# Check a sample video directly via web
print("\n=== Checking video metadata on web ===")
import urllib.request
sample = sorted_vids[0][0] if sorted_vids else ""
if sample:
    url = f"https://www.youtube.com/shorts/{sample}"
    print(f"Sample URL: {url}")
