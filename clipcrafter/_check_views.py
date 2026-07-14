"""Check video performance directly via YouTube API"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["OAUTH_PATH"] = os.path.expanduser("~/client_secret.json")

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

def get_authenticated_service():
    creds = None
    token_file = os.path.expanduser("~/.clipcrader_oauth_token.pickle")
    if os.path.exists(token_file):
        with open(token_file, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_file = os.environ.get("OAUTH_PATH", os.path.expanduser("~/client_secret.json"))
            flow = InstalledAppFlow.from_client_secrets_file(client_file, SCOPES)
            creds = flow.run_local_server(port=8080)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)

# Read video IDs from performance DB
perf_file = os.path.expanduser("~/.clipcrafter/clip_performance.json")
if os.path.exists(perf_file):
    db = json.load(open(perf_file))
else:
    db = {}

print(f"Total videos in DB: {len(db)}")

if not db:
    print("No videos to check")
    sys.exit(0)

# Check via API in batches of 50
youtube = get_authenticated_service()
ids = list(db.keys())

# Check first 20
batch = ids[:20]
request = youtube.videos().list(
    part="statistics,snippet,contentDetails",
    id=",".join(batch)
)
response = request.execute()

print(f"\n=== First {len(batch)} videos ===")
items = {i["id"]: i for i in response.get("items", [])}
for vid in batch:
    item = items.get(vid)
    if item:
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        title = snippet.get("title", "?")
        published = snippet.get("publishedAt", "?")[:10]
        duration = item.get("contentDetails", {}).get("duration", "?")
        print(f"  {vid}: {views}v {likes}l {comments}c | {published} | {title[:60]}")
    else:
        print(f"  {vid}: NOT FOUND (deleted/private)")

# Summary
all_stats = {}
for i in range(0, len(ids), 50):
    batch = ids[i:i+50]
    r = youtube.videos().list(part="statistics", id=",".join(batch)).execute()
    for item in r.get("items", []):
        all_stats[item["id"]] = item.get("statistics", {})

print(f"\n=== Summary ({len(all_stats)} videos found) ===")
total_views = sum(int(s.get("viewCount", 0)) for s in all_stats.values())
total_likes = sum(int(s.get("likeCount", 0)) for s in all_stats.values())
zero_views = sum(1 for s in all_stats.values() if int(s.get("viewCount", 0)) == 0)
print(f"Total views: {total_views}")
print(f"Total likes: {total_likes}")
print(f"Videos with 0 views: {zero_views}/{len(all_stats)}")
print(f"Average views: {total_views/len(all_stats):.1f}" if all_stats else "N/A")

# Check what videos have >0 views
print("\n=== Videos with views > 0 ===")
for vid, s in sorted(all_stats.items(), key=lambda x: int(x[1].get("viewCount", 0)), reverse=True):
    v = int(s.get("viewCount", 0))
    if v > 0:
        print(f"  {vid}: {v} views")
