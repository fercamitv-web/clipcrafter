#!/usr/bin/env python3
"""Retitula/descricao de TODOS os videos do canal em lotes diários (quota-safe).
- newest-first, resumable via state, budget de updates/dia (videos.update = 50 units)
- protege vencedores: nao mexe no titulo se views>=2000 e sem spam
- uso: python retitle_all.py [--budget 80] [--dry]
"""
import json, re, sys, time
from pathlib import Path

BUDGET = 80
STATE = Path(r"C:\Users\ferca\AppData\Local\Temp\retitle_all_state.json")
LOG = Path(r"C:\Users\ferca\AppData\Local\Temp\retitle_all.log")

GAMEWORDS = ["valorant", "minecraft", "roblox", "tft", "teamfight tactics",
             "fnaf", "five nights", "horror", "squid game", "mario",
             "fortnite", "free fire", "league of legends", "counter-strike",
             "gta", "genshin", "overwatch", "apex"]
BRAND = ["fercami gameplay", "canalpropra", "canal propra", "fercami"]
MAINMAP = {"Valorant": "valorant", "Minecraft": "minecraft", "Roblox": "roblox",
           "Horror Co-op": "horror", "FNAF": "fnaf", "Valorant Duo": "valorant"}

def log(m):
    print(m, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(m + "\n")

def spam_markers(t):
    tl = t.lower()
    marks = []
    if "#" in t:
        marks.append("hashtag")
    caps = sum(1 for c in t if c.isupper())
    if caps / max(1, len(t)) > 0.4:
        marks.append("caps")
    games = {g for g in GAMEWORDS if re.search(r"\b" + re.escape(g) + r"\b", tl)}
    if len(games) > 1:
        marks.append("stuffing")
    if len(t) > 95:
        marks.append("long")
    return marks

def clean_title(t, main_word):
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"#\w+", "", t)
    for b in BRAND:
        t = re.sub(re.escape(b), "", t, flags=re.I)
    for g in GAMEWORDS:
        if g != (main_word or ""):
            t = re.sub(r"\b" + re.escape(g) + r"\b", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -–—|")
    t = re.sub(r"\b[A-ZÀ-Þ]{5,}\b", lambda m: m.group(0).capitalize(), t)
    if t:
        t = t[0].upper() + t[1:]
    if len(t) > 95:
        t = t[:95].rsplit(" ", 1)[0]
    return t

def main():
    budget = BUDGET
    dry = False
    for a in sys.argv[1:]:
        if a == "--dry":
            dry = True
        elif a.startswith("--budget"):
            budget = int(a.split("=")[1] if "=" in a else sys.argv[sys.argv.index(a) + 1])
    sys.path.insert(0, r"C:\Users\ferca\OneDrive\Documentos\1\clipcrafter")
    import pickle
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from content_detector import detect_game

    p = Path.home() / ".clipcrafter" / "youtube_token.pickle"
    creds = pickle.load(open(p, "rb"))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        pickle.dump(creds, open(p, "wb"))
    yt = build("youtube", "v3", credentials=creds)

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"done": []}
    done = set(state["done"])

    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    upl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    # coleta IDs newest-first
    ids, page = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                    maxResults=50, pageToken=page).execute()
        ids += [it["contentDetails"]["videoId"] for it in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            break
    todo = [v for v in ids if v not in done]
    log(f"total={len(ids)} todo={len(todo)} budget={budget} dry={dry}")

    used, updated, skipped = 0, 0, 0
    for vid in todo:
        if used >= budget:
            break
        v = yt.videos().list(part="snippet,statistics", id=vid).execute()["items"]
        if not v:
            done.add(vid)
            continue
        v = v[0]
        sn, st = v["snippet"], v.get("statistics", {})
        views = int(st.get("viewCount", 0))
        old_t = sn.get("title", "")
        desc = sn.get("description", "")
        marks = spam_markers(old_t)
        main_word = MAINMAP.get(detect_game(old_t), "")
        new_t = clean_title(old_t, main_word)
        need_title = (new_t != old_t) and (marks or views < 2000)
        need_desc = "#shorts" not in desc.lower()
        if not need_title and not need_desc:
            done.add(vid)
            skipped += 1
            continue
        if dry:
            log(f"DRY {vid} views={views} marks={marks} | {old_t[:50]} -> {new_t[:50]}")
            done.add(vid)
            continue
        body = {"id": vid, "snippet": {
            "title": new_t if need_title else old_t,
            "description": (desc.rstrip() + "\n\n#Shorts") if need_desc else desc,
            "categoryId": sn.get("categoryId", "20"),
        }}
        if sn.get("tags"):
            body["snippet"]["tags"] = sn["tags"][:500]
        try:
            yt.videos().update(part="snippet", body=body).execute()
            used += 1
            updated += 1
            done.add(vid)
            log(f"OK {vid} views={views} title={need_title} desc={need_desc}")
            time.sleep(1)
        except Exception as e:
            log(f"FAIL {vid}: {str(e)[:150]}")
            break
    state["done"] = sorted(done)
    STATE.write_text(json.dumps(state), encoding="utf-8")
    log(f"FIM used={used} updated={updated} skipped-ok={skipped} restantes={len(todo)-used}")

if __name__ == "__main__":
    main()
