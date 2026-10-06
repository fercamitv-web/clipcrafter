#!/usr/bin/env python3
"""Auto-tune semanal: aprende com os clipes e reajusta o sistema sozinho.
Mede (90 dias): views por nicho, por hora de publicacao (BRT), por faixa
de tamanho de titulo e por dia da semana. Escreve:
  - niche_scores.json (ordem da fila por media real)
  - tuning.json (melhores horarios, teto de titulo, dia forte)
O pipeline consome os dois automaticamente. ~30 units de quota.
"""
import json
import pickle
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from statistics import median

REPO = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "clipcrafter" else Path(__file__).resolve().parent
NS_FILE = REPO / "clipcrafter" / "scheduled_uploads" / "niche_scores.json"
TUNE_FILE = REPO / "clipcrafter" / "scheduled_uploads" / "tuning.json"
BRT = timezone(timedelta(hours=-3))
GAMES = ["Minecraft", "Valorant", "Roblox", "Horror Co-op", "Gaming", "Squid Game", "FNAF"]
sys.path.insert(0, str(REPO / "clipcrafter"))


def main():
    import base64
    import os as _os
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from niche_guard import classify
    cs, tp = _os.environ.get("YT_CLIENT_SECRET"), _os.environ.get("YT_TOKEN_PICKLE")
    if cs and tp:
        d = Path.home() / ".clipcrafter"
        d.mkdir(parents=True, exist_ok=True)
        (d / "client_secret.json").write_bytes(base64.b64decode(cs))
        (d / "youtube_token.pickle").write_bytes(base64.b64decode(tp))
    p = Path.home() / ".clipcrafter" / "youtube_token.pickle"
    if not p.exists():
        print("sem credencial")
        return 0
    creds = pickle.load(open(p, "rb"))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        pickle.dump(creds, open(p, "wb"))
    yt = build("youtube", "v3", credentials=creds)
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    upl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page, cutoff = [], None, datetime.now(timezone.utc) - timedelta(days=90)
    while len(ids) < 400:
        r = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                    maxResults=50, pageToken=page).execute()
        for it in r["items"]:
            if it["contentDetails"].get("videoPublishedAt", "") < cutoff.strftime("%Y-%m-%d"):
                pass
            ids.append(it["contentDetails"]["videoId"])
        page = r.get("nextPageToken")
        if not page:
            break
    rows = []
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,statistics", id=",".join(ids[i:i+50])).execute()["items"]:
            sn = v["snippet"]
            pub = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00")).astimezone(BRT)
            if pub < cutoff:
                continue
            rows.append({"v": int(v.get("statistics", {}).get("viewCount", 0)),
                         "g": classify(sn.get("title", "")),
                         "h": pub.hour, "dow": pub.weekday(),
                         "tlen": len(sn.get("title", ""))})
    print(f"amostra: {len(rows)} videos (90d)")
    if len(rows) < 10:
        print("amostra pequena, mantendo tuning atual")
        return 0

    def avg(sel):
        return sum(sel) / len(sel) if sel else 0

    gmap = {}
    for g in GAMES:
        vs = [r["v"] for r in rows if r["g"] == g]
        gmap[g] = (avg(vs), len(vs))
    med = median([a for a, _ in gmap.values()] + [0])
    scored = {g: round(a if n >= 3 else med, 1) for g, (a, n) in gmap.items()}
    order = sorted(GAMES, key=lambda g: -scored[g])

    hmap = {}
    for h in range(24):
        vs = [r["v"] for r in rows if r["h"] == h]
        if len(vs) >= 2:
            hmap[str(h)] = round(avg(vs), 1)
    best_hours = sorted(hmap, key=lambda h: -hmap[h])[:6]

    short = [r["v"] for r in rows if r["tlen"] <= 45]
    long = [r["v"] for r in rows if r["tlen"] > 45]
    cap = 45 if avg(short) >= avg(long) and len(short) >= 5 else 60

    dow = {}
    for d in range(7):
        vs = [r["v"] for r in rows if r["dow"] == d]
        if vs:
            dow[str(d)] = round(avg(vs), 1)

    NS_FILE.write_text(json.dumps(
        {"order": order, "scores": {g: {"avg": scored[g], "n": gmap[g][1]} for g in GAMES},
         "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
        ensure_ascii=False, indent=2), encoding="utf-8")
    TUNE_FILE.write_text(json.dumps(
        {"best_hours": [int(h) for h in best_hours], "hour_avg": hmap,
         "title_cap": cap, "dow_avg": dow, "sample": len(rows),
         "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print("ordem:", order)
    print("melhores horas:", best_hours, "| teto titulo:", cap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
