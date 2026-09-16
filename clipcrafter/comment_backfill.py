#!/usr/bin/env python3
"""Comentarios em TODOS os videos (lote diario resumivel):
- posta CTA de palavra-chave onde falta comentario nosso
- responde 1 comentario de fa sem nossa resposta
- pula privados (tentam de novo outro dia); nunca falha o run
Quota: ~1 unidade/leitura + 50/acao; BUDGET padrao 15 acoes/dia.
Estado em clipcrafter/scheduled_uploads/comment_state.json (commitado pelo workflow).
"""
import os, sys, json, pickle, random, time
from pathlib import Path
from datetime import datetime, timezone

CI_DIR = Path(__file__).resolve().parent
REPO_DIR = CI_DIR.parent
STATE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "comment_state.json"
sys.path.insert(0, str(CI_DIR))
from ci_upload import COMMENT_HOOKS  # noqa: E402

BUDGET = int(os.environ.get("COMMENT_BUDGET", "15"))
PER_DAY = int(os.environ.get("COMMENT_PER_DAY", "60"))

REPLIES = [
    "Valeu por assistir! Qual parte foi a melhor? 🔥",
    "Tamo junto! Comenta CLUTCH se curtiu 👇",
    "Obrigado pelo comentário! Tem mais clipe todo dia 🎮",
]


def main():
    import base64
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
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
    me = yt.channels().list(part="id", mine=True).execute()["items"][0]["id"]
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    upl = ch["contentDetails"]["relatedPlaylists"]["uploads"]

    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {"done": []}
    done = set(state.get("done", []))

    ids, page = [], None
    while len(ids) < 700:
        r = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                    maxResults=50, pageToken=page).execute()
        ids += [it["contentDetails"]["videoId"] for it in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            break
    todo = [v for v in ids if v not in done]
    print(f"total={len(ids)} todo={len(todo)} budget={BUDGET}")
    actions, checked = 0, 0
    for vid in todo:
        if actions >= BUDGET or checked >= PER_DAY:
            break
        try:
            v = yt.videos().list(part="snippet,status", id=vid).execute()["items"][0]
        except Exception:
            continue
        if v["status"].get("privacyStatus") != "public":
            continue  # tenta outro dia (nao marca done)
        checked += 1
        try:
            threads = yt.commentThreads().list(
                part="snippet,replies", videoId=vid, maxResults=10).execute().get("items", [])
        except Exception as e:
            print(f"{vid}: sem acesso ({str(e)[:60]})")
            done.add(vid)
            continue
        mine = [t for t in threads
                if t["snippet"]["topLevelComment"]["snippet"].get("authorChannelId", {}).get("value") == me]
        acted = False
        if not mine:
            try:
                yt.commentThreads().insert(
                    part="snippet",
                    body={"snippet": {"videoId": vid, "topLevelComment": {
                        "snippet": {"textOriginal": random.choice(COMMENT_HOOKS)[:1000]}}}},
                ).execute()
                print(f"{vid}: comentado ({v['snippet']['title'][:40]})")
                acted = True
            except Exception as e:
                print(f"{vid}: falhou ({str(e)[:80]})")
        else:
            # responde 1 fã sem nossa resposta
            for t in threads:
                top = t["snippet"]["topLevelComment"]["snippet"]
                if top.get("authorChannelId", {}).get("value") == me:
                    continue
                reps = [c for c in t.get("replies", {}).get("comments", [])
                        if c["snippet"].get("authorChannelId", {}).get("value") == me]
                if not reps:
                    try:
                        yt.comments().insert(
                            part="snippet",
                            body={"snippet": {"parentId": t["snippet"]["topLevelComment"]["id"],
                                              "textOriginal": random.choice(REPLIES)[:1000]}},
                        ).execute()
                        print(f"{vid}: respondido")
                        acted = True
                    except Exception as e:
                        print(f"{vid}: reply falhou ({str(e)[:80]})")
                    break
        if acted:
            actions += 1
            time.sleep(1)
        done.add(vid)
    state["done"] = sorted(done)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    print(f"FIM: {actions} acoes, {checked} verificados, restantes={len(todo) - checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
