"""Upload VOD2 clips with SEO titles and FERCAMI GAMEPLAY overlay"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from youtube_uploader import upload_video

base = os.path.expanduser('~/clipcrafter_downloads/clipes2')
out_dir = os.path.join(base, 'processados')
secret_file = os.path.expanduser('~/client_secret.json')
os.environ["OAUTH_PATH"] = secret_file

# Load pre-computed metadata
meta_path = os.path.join(out_dir, "clips_metadata.json")
with open(meta_path) as f:
    metadata = json.load(f)

for item in metadata:
    fname = item["file"]
    path = os.path.join(out_dir, f"{fname}.mp4")
    if not os.path.exists(path):
        print(f"MISSING {fname}")
        continue

    title = item["title"]
    hook = item.get("hook", "")
    desc = item.get("desc", "Clip da live! #Valorant #ClipCrafter #CanalPropra")
    tags = item.get("tags", ["Valorant", "shorts", "ClipCrader"])

    print(f"\n  {fname}")
    print(f"  Title: {title}")
    if hook:
        print(f"  Hook: {hook}")

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
