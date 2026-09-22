#!/usr/bin/env python3
"""Guarda anti-queda: mede views medias por nicho (60 videos) e escreve a ordem
de prioridade da fila. Nicho provado na frente; frio no meio; fraco no fim.
Roda 1x/semana (CI) + on demand. ~5 units de quota.
"""
import json
import pickle
import sys
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "clipcrafter" else Path(__file__).resolve().parent
OUT = REPO / "clipcrafter" / "scheduled_uploads" / "niche_scores.json"
GAMES = ["Minecraft", "Valorant", "Roblox", "Horror Co-op", "Gaming", "Squid Game", "FNAF"]


def classify(title):
    t = (title or "").lower()
    if any(k in t for k in ["valorant", "platina", "vct", "loud", "yordle", "celesty"]):
        return "Valorant"
    if "minecraft" in t or "one block" in t:
        return "Minecraft"
    if "roblox" in t:
        return "Roblox"
    if any(k in t for k in ["terror", "demonology", "lost rooms", "frigid", "susto", "fantasma"]):
        return "Horror Co-op"
    if "squid" in t or "round" in t:
        return "Squid Game"
    if "fnaf" in t or "freddy" in t or "five nights" in t:
        return "FNAF"
    return "Gaming"


def main():
    import base64
    import os as _os
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
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
    ids, page = [], None
    while len(ids) < 60:
        r = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                    maxResults=50, pageToken=page).execute()
        ids += [it["contentDetails"]["videoId"] for it in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            break
    agg = {}
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,statistics", id=",".join(ids[i:i+50])).execute()["items"]:
            g = classify(v["snippet"].get("title", ""))
            agg.setdefault(g, []).append(int(v.get("statistics", {}).get("viewCount", 0)))
    avgs = {g: sum(v) / len(v) for g, v in agg.items()}
    med = median(avgs.values()) if avgs else 0
    scored = {}
    for g in GAMES:
        n = len(agg.get(g, []))
        scored[g] = round(avgs[g], 1) if n >= 3 else round(med, 1)
    order = sorted(GAMES, key=lambda g: -scored[g])
    from datetime import datetime, timezone
    OUT.write_text(json.dumps(
        {"order": order, "scores": {g: {"avg": scored[g], "n": len(agg.get(g, []))} for g in GAMES},
         "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
        ensure_ascii=False, indent=2), encoding="utf-8")
    for g in order:
        print(f"{g}: avg={scored[g]} n={len(agg.get(g, []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
