"""Deeper diagnosis"""
import subprocess, json, os, sys
from datetime import datetime

yt_py = os.path.join(os.environ["TEMP"], "yt_env", "Scripts", "python.exe")

# List all shorts with their view counts, sorted by upload date
r = subprocess.run([yt_py, "-m", "yt_dlp", "--flat-playlist", "--dump-single-json",
                    "https://www.youtube.com/@CanalPropra/shorts"],
                   capture_output=True, text=True, timeout=120)
if r.returncode == 0:
    data = json.loads(r.stdout)
    entries = [e for e in data.get("entries", []) if e]
    
    # Sort by upload date (newest first)
    entries.sort(key=lambda x: x.get("upload_date", "0"), reverse=True)
    
    print(f"\n=== Recent 20 shorts (newest) ===")
    for e in entries[:20]:
        vc = e.get("view_count", 0)
        ud = e.get("upload_date", "?")
        dur = e.get("duration", 0)
        title = (e.get("title") or "?")[:60].encode("ascii","replace").decode()
        try:
            ud_dt = datetime.strptime(ud, "%Y%m%d")
            ud_str = ud_dt.strftime("%d/%m")
        except:
            ud_str = ud
        marker = "*** ZERO ***" if vc == 0 else f"{vc:>5}v"
        print(f"  {marker} {ud_str} ({dur}s) {title}")
    
    # Top 10 by views
    entries.sort(key=lambda x: x.get("view_count", 0), reverse=True)
    print(f"\n=== Top 10 shorts (most viewed) ===")
    for e in entries[:10]:
        vc = e.get("view_count", 0)
        ud = e.get("upload_date", "?")
        title = (e.get("title") or "?")[:60].encode("ascii", "replace").decode()
        dur = e.get("duration", 0)
        print(f"  {vc:>5}v ({dur}s) {title}")
    
    # Analyze by period
    print(f"\n=== Performance by period ===")
    old = [e for e in entries if e.get("upload_date", "0") < "20260601"]
    recent = [e for e in entries if e.get("upload_date", "0") >= "20260601"]
    
    def analyze(entries, label):
        if not entries: return
        total = len(entries)
        with_v = sum(1 for e in entries if e.get("view_count", 0) > 0)
        total_v = sum(e.get("view_count", 0) for e in entries)
        avg_v = total_v / total if total > 0 else 0
        print(f"  {label}: {total} shorts, {with_v} with views, avg {avg_v:.0f}v, total {total_v}v")
    
    analyze(old, "Before June 2026")
    analyze(recent, "June 2026+ (our clips)")
    
    # Posting frequency
    print(f"\n=== Posting frequency ===")
    dates = [e.get("upload_date", "0") for e in entries]
    unique_dates = sorted(set(dates))
    print(f"  Unique upload dates: {len(unique_dates)}")
    
    # When did we start posting (our first clip)?
    our_titles = [e for e in entries if "GAMEPLAY" in str(e.get("title","")).upper() or "fercami" in str(e.get("title","")).lower()]
    print(f"  Shorts with fercami/gameplay title: {len(our_titles)}")
    for e in our_titles[:3]:
        t = (e.get("title") or "?")[:50].encode("ascii","replace").decode()
        print(f"    {e.get('upload_date','?')} {e.get('view_count',0)}v {t}")
else:
    print(f"Shorts list error: {r.stderr[:200]}")
