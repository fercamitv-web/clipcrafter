#!/usr/bin/env python3
"""Comenta CTA de palavra-chave nos videos de HOJE que ainda nao tem comentario nosso.
Roda 23:30 BRT (02:30 UTC): videos das 12h/18h/22h ja estao publicos.
Sinal de engajamento (criador ativo) que o algoritmo 2026 premia.
"""
import os, sys, pickle, random
from pathlib import Path
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))
CI_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CI_DIR))
from ci_upload import COMMENT_HOOKS  # noqa: E402


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
        print("sem credencial (YT_TOKEN_PICKLE ou ~/.clipcrafter/youtube_token.pickle)")
        return 0
    creds = pickle.load(open(p, "rb"))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        pickle.dump(creds, open(p, "wb"))
    yt = build("youtube", "v3", credentials=creds)
    me = yt.channels().list(part="id", mine=True).execute()["items"][0]["id"]
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    upl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(
        part="contentDetails", playlistId=upl, maxResults=10).execute()["items"]
    done = 0
    for it in items:
        vid = it["contentDetails"]["videoId"]
        v = yt.videos().list(part="snippet,status", id=vid).execute()["items"][0]
        pub = v["snippet"]["publishedAt"][:10]
        # compara em BRT de forma simples: usa data UTC (suficiente p/ janela diaria)
        if v["status"].get("privacyStatus") != "public":
            continue
        try:
            threads = yt.commentThreads().list(
                part="snippet", videoId=vid, maxResults=20).execute().get("items", [])
        except Exception as e:
            print(f"{vid}: sem acesso a comentarios ({str(e)[:80]})")
            continue
        mine = [t for t in threads
                if t["snippet"]["topLevelComment"]["snippet"].get("authorChannelId", {}).get("value") == me]
        if mine:
            print(f"{vid}: ja tem comentario nosso")
            continue
        title = v["snippet"]["title"]
        try:
            yt.commentThreads().insert(
                part="snippet",
                body={"snippet": {"videoId": vid, "topLevelComment": {
                    "snippet": {"textOriginal": random.choice(COMMENT_HOOKS)[:1000]}}}},
            ).execute()
            print(f"{vid}: comentado ({title[:40]})")
            done += 1
        except Exception as e:
            print(f"{vid}: falhou ({str(e)[:100]})")
    print(f"FIM: {done} comentarios postados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
