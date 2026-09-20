#!/usr/bin/env python3
"""Vigia da muralha (fecha o ciclo): confere HOJE e AMANHÃ slot a slot
(12h/18h/22h BRT) no YouTube de verdade.
-_slot passado sem vídeo      -> precisa de fill DIRETO
- slot futuro sem agendamento -> precisa de fill agendado
Imprime MISSING=... e sai 1 se faltar algo (o workflow dispara o fill).
"""
import pickle
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))


def main():
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    p = Path.home() / ".clipcrafter" / "youtube_token.pickle"
    env_cs, env_tp = None, None
    try:
        import os as _os
        import base64 as _b64
        env_cs, env_tp = _os.environ.get("YT_CLIENT_SECRET"), _os.environ.get("YT_TOKEN_PICKLE")
        if env_cs and env_tp:
            d = Path.home() / ".clipcrafter"
            d.mkdir(parents=True, exist_ok=True)
            (d / "client_secret.json").write_bytes(_b64.b64decode(env_cs))
            (d / "youtube_token.pickle").write_bytes(_b64.b64decode(env_tp))
    except Exception as e:
        print(f"secrets skip: {str(e)[:80]}")
    if not p.exists():
        print("MISSING=sem-credencial")
        return 2
    creds = pickle.load(open(p, "rb"))
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            pickle.dump(creds, open(p, "wb"))
        except Exception as e:
            print(f"MISSING=token-morto ({str(e)[:80]})")
            return 2
    yt = build("youtube", "v3", credentials=creds)
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    upl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while len(ids) < 120:
        r = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                    maxResults=50, pageToken=page).execute()
        ids += [it["contentDetails"]["videoId"] for it in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            break
    have = set()  # (date_str, hour)
    now = datetime.now(BRT)
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,status", id=",".join(ids[i:i+50])).execute()["items"]:
            st, sn = v["status"], v["snippet"]
            if st.get("privacyStatus") == "public":
                pub = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00")).astimezone(BRT)
                have.add((str(pub.date()), pub.hour))
            elif st.get("publishAt"):
                pa = datetime.fromisoformat(st["publishAt"].replace("Z", "+00:00")).astimezone(BRT)
                have.add((str(pa.date()), pa.hour))
    missing = []
    for ahead in (0, 1):
        day = now + timedelta(days=ahead)
        ds = str(day.date())
        for h in (12, 18, 22):
            slot = day.replace(hour=h, minute=0, second=0, microsecond=0)
            if (ds, h) in have:
                continue
            if ahead == 0 and slot < now - timedelta(minutes=10):
                missing.append(f"{ds} {h:02d}h (passou: direto)")
            elif ahead == 0 and slot > now + timedelta(minutes=30):
                missing.append(f"{ds} {h:02d}h (agendado)")
            elif ahead == 1:
                missing.append(f"{ds} {h:02d}h (agendado)")
    if missing:
        print("MISSING=" + ";".join(missing))
        return 1
    print("MURALHA OK: hoje+amanhã completos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
