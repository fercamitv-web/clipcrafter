"""Upload VOD2 batch 3 clips"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from youtube_uploader import upload_video

out_dir = os.path.expanduser("~/clipcrafter_downloads/clipes2/processados")
os.environ["OAUTH_PATH"] = os.path.expanduser("~/client_secret.json")
meta = json.load(open(os.path.join(out_dir, "clips_metadata3.json")))

for item in meta:
    fname = item["file"]
    path = os.path.join(out_dir, f"{fname}.mp4")
    if not os.path.exists(path):
        print(f"MISSING {path}")
        continue
    title = item["title"]
    hook = item.get("hook", "")
    desc = item.get("desc", "Clip da live! #Valorant #ClipCrafter #CanalPropra")
    tags = item.get("tags", ["Valorant", "shorts"])
    print(f"\n{fname}")
    print(f"  {title}")
    if hook:
        print(f"  Hook: {hook}")
    print("  Uploading...", end=" ", flush=True)
    try:
        vid = upload_video(path, title=title, description=desc,
                          tags=tags, privacy_status="public")
        if vid:
            print(f"OK! https://youtube.com/watch?v={vid}")
        else:
            print("FAILED")
    except Exception as e:
        print(f"ERROR: {e}")
