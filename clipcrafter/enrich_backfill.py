#!/usr/bin/env python3
"""Enriquece TODOS os videos: entra na playlist do jogo + link do viral na desc.
Lote diario resumivel (20/dia). Estado commitado pelo workflow.
"""
import os, sys, json, pickle, time
from pathlib import Path

CI_DIR = Path(__file__).resolve().parent
REPO_DIR = CI_DIR.parent
STATE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "enrich_state.json"
PL_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "playlists.json"
sys.path.insert(0, str(CI_DIR))

BUDGET = int(os.environ.get("ENRICH_BUDGET", "20"))
VIRAL_LINE = "O MAIS VISTO do canal:"
VIRAL_URL = "https://youtube.com/shorts/z33q6waLbEM"
CTA_BLOCK = ("INSCREVA-SE no CanalPropra para mais momentos INSANOS:\n"
             "https://www.youtube.com/@CanalPropra\n\n"
             "Comenta qual dessas jogadas foi a melhor!")


def upgrade_desc(desc):
    """Completa descrição fraca (<300 chars ou sem CTA) preservando o original."""
    nd = desc
    if len(nd) < 300 or "INSCREVA-SE" not in nd.upper():
        nd = (nd.rstrip() + "\n\n" + CTA_BLOCK)[:4800]
    if VIRAL_LINE not in nd:
        nd = (nd.rstrip() + f"\n{VIRAL_LINE}\n{VIRAL_URL}\n")[:5000]
    return nd


def main():
    import base64
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from content_detector import detect_game
    cs = os.environ.get("YT_CLIENT_SECRET")
    tp = os.environ.get("YT_TOKEN_PICKLE")
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
        try:
            creds.refresh(Request())
            pickle.dump(creds, open(p, "wb"))
        except Exception as e:
            print(f"token falhou: {str(e)[:100]}")
            return 0
    yt = build("youtube", "v3", credentials=creds)
    pls = json.loads(PL_FILE.read_text(encoding="utf-8")).get("playlists", {})
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {"done": []}
    done = set(state.get("done", []))

    # membros atuais das playlists (1x por run)
    members = {}
    for game, pid in pls.items():
        have, page = set(), None
        try:
            while True:
                r = yt.playlistItems().list(part="contentDetails", playlistId=pid,
                                            maxResults=50, pageToken=page).execute()
                have.update(it["contentDetails"]["videoId"] for it in r["items"])
                page = r.get("nextPageToken")
                if not page or len(have) > 800:
                    break
        except Exception as e:
            print(f"playlist {game}: {str(e)[:80]}")
        members[game] = have

    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    upl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while len(ids) < 800:
        r = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                    maxResults=50, pageToken=page).execute()
        ids += [it["contentDetails"]["videoId"] for it in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            break
    todo = [v for v in ids if v not in done]
    print(f"total={len(ids)} todo={len(todo)} budget={BUDGET}")
    used = 0
    for i in range(0, len(todo), 50):
        if used >= BUDGET:
            break
        chunk = todo[i:i + 50]
        try:
            vids = yt.videos().list(part="snippet", id=",".join(chunk)).execute()["items"]
        except Exception as e:
            print(f"list falhou: {str(e)[:80]}")
            break
        for v in vids:
            if used >= BUDGET:
                break
            vid = v["id"]
            sn = v["snippet"]
            game = detect_game(sn.get("title", ""))
            pid = pls.get(game) or pls.get("Gaming")
            try:
                if pid and vid not in members.get(game, set()):
                    yt.playlistItems().insert(
                        part="snippet",
                        body={"snippet": {"playlistId": pid, "resourceId": {
                            "kind": "youtube#video", "videoId": vid}}}).execute()
                    members.setdefault(game, set()).add(vid)
                    used += 1
                    print(f"{vid}: playlist {game}")
                    time.sleep(1)
            except Exception as e:
                print(f"{vid}: playlist skip ({str(e)[:80]})")
            try:
                desc = sn.get("description", "")
                nd = upgrade_desc(desc)
                if nd != desc:
                    body = {"id": vid, "snippet": {"title": sn.get("title", "")[:100],
                            "description": nd, "categoryId": sn.get("categoryId", "20")}}
                    if sn.get("tags"):
                        body["snippet"]["tags"] = sn["tags"][:500]
                    yt.videos().update(part="snippet", body=body).execute()
                    used += 1
                    print(f"{vid}: desc link")
                    time.sleep(1)
            except Exception as e:
                print(f"{vid}: desc skip ({str(e)[:80]})")
            done.add(vid)
    state["done"] = sorted(done)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    print(f"FIM: {used} escritas, restantes={len(todo) - min(len(todo), used + 50)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
