"""Upload runner for GitHub Actions CI. Reads from clip_queue.json and uploads clips/day (default 5) to YouTube + TikTok."""
import json, os, sys, base64, random
from pathlib import Path
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))
CI_DIR = Path(__file__).resolve().parent
REPO_DIR = CI_DIR.parent
QUEUE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "clip_queue.json"
STATE_FILE = REPO_DIR / "clipcrafter" / "scheduled_uploads" / "upload_state.json"

COMMENT_HOOKS = [
    "Comenta CLUTCH se foi clutch de verdade 🔥",
    "Comenta SETUP que mando meu setup 👇",
    "Comenta LOUD se torceu nesse momento 🎮",
    "Comenta REPLAY se assistiu de novo 😅",
]

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"cursor": 0, "uploaded": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def save_queue(queue):
    QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

def _write_yt_files(client_secret_b64, token_pickle_b64):
    clipcrafter_dir = Path.home() / ".clipcrafter"
    clipcrafter_dir.mkdir(parents=True, exist_ok=True)
    (clipcrafter_dir / "client_secret.json").write_bytes(base64.b64decode(client_secret_b64))
    (clipcrafter_dir / "youtube_token.pickle").write_bytes(base64.b64decode(token_pickle_b64))

def _yt_token_ok():
    # valida refresh sem gastar quota (endpoint OAuth, nao API)
    try:
        import pickle
        from google.auth.transport.requests import Request
        p = Path.home() / ".clipcrafter" / "youtube_token.pickle"
        creds = pickle.load(open(p, "rb"))
        creds.refresh(Request())
        return True
    except Exception as e:
        print(f"    (token inválido: {str(e)[:100]})")
        return False

def setup_youtube():
    client_secret_b64 = os.environ.get("YT_CLIENT_SECRET")
    token_pickle_b64 = os.environ.get("YT_TOKEN_PICKLE")
    if not client_secret_b64 or not token_pickle_b64:
        return None
    _write_yt_files(client_secret_b64, token_pickle_b64)
    if _yt_token_ok():
        print("  YouTube: token 1 OK")
    else:
        # Fallback: segunda conta gerente (credencial independente)
        cs2 = os.environ.get("YT_CLIENT_SECRET_2")
        tp2 = os.environ.get("YT_TOKEN_PICKLE_2")
        if cs2 and tp2:
            print("  YouTube: token 1 falhou, tentando token 2 (conta reserva)...")
            _write_yt_files(cs2, tp2)
            if _yt_token_ok():
                print("  YouTube: token 2 OK (modo reserva)")
            else:
                print("  YouTube: token 2 também falhou")
                return None
        else:
            return None
    from youtube_uploader import upload_video as yt_upload
    return yt_upload

def setup_tiktok():
    if not os.environ.get("TT_COOKIES"):
        return None
    from tiktok_uploader import upload_video as tt_upload
    return tt_upload

def setup_instagram():
    if not os.environ.get("IG_ACCESS_TOKEN") or not os.environ.get("IG_USER_ID"):
        return None
    from instagram_uploader import upload_video as ig_upload
    return ig_upload

def notify_discord(title, results):
    # Avisa num canal Discord p/ gerar as primeiras views legítimas
    # (compartilhamento real). Best-effort: nunca derruba o run.
    url = os.environ.get("DISCORD_WEBHOOK")
    if not url:
        return
    try:
        import urllib.request
        links = []
        for r in results:
            if r.startswith("yt:"):
                links.append(f"https://youtube.com/shorts/{r[3:]}")
            elif r.startswith("tt:"):
                links.append(f"https://tiktok.com/@{r[3:]}")
            elif r.startswith("ig:"):
                links.append(f"IG media {r[3:]}")
            elif r.startswith("fb:"):
                links.append(f"FB video {r[3:]}")
        msg = {"content": f"Novo clipe: **{title[:120]}**\n" + "\n".join(links)}
        req = urllib.request.Request(
            url, data=json.dumps(msg).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)
        print("    (discord avisado)")
    except Exception as e:
        print(f"    (discord skip: {str(e)[:80]})")


def setup_facebook():
    if not os.environ.get("FB_ACCESS_TOKEN") or not os.environ.get("FB_PAGE_ID"):
        return None
    from facebook_uploader import upload_video as fb_upload
    return fb_upload

def main():
    sys.path.insert(0, str(CI_DIR))
    yt_upload = setup_youtube()
    tt_upload = setup_tiktok()
    ig_upload = setup_instagram()
    fb_upload = setup_facebook()

    if not yt_upload and not tt_upload and not ig_upload and not fb_upload:
        print("No upload targets configured. Need YT_* and/or TT_* and/or IG_* and/or FB_* secrets.")
        sys.exit(1)

    queue = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    state = load_state()

    if not queue:
        print("Queue is empty! No more clips to upload.")
        return

    # Remove dead entries (files that don't exist in the repo)
    before = len(queue)
    alive = [c for c in queue if (REPO_DIR / c.get("file", "clipcrafter/scheduled_uploads/clips/" + c.get("clip_file", ""))).exists()]
    if len(alive) < before:
        print(f"Cleaned {before - len(alive)} dead entries from queue")
    queue = alive

    if not queue:
        print("No clips with valid files in queue.")
        return

    cursor = state["cursor"]
    if cursor >= len(queue):
        print(f"All {len(queue)} clips have been uploaded. Queue exhausted.")
        return

    # Filtro por jogo (ex: GAME_FILTER=Minecraft): prioriza matches na frente
    # dos pendentes, sem apagar nada. Se acabar, usa o resto (nunca trava o dia).
    game_filter = os.environ.get("GAME_FILTER", "").strip().lower()
    if game_filter:
        pend = queue[cursor:]
        match = [c for c in pend if (c.get("game") or "").lower() == game_filter]
        rest = [c for c in pend if (c.get("game") or "").lower() != game_filter]
        if match:
            queue = queue[:cursor] + match + rest
            save_queue(queue)
            print(f"Filtro '{game_filter}': {len(match)} na frente")
        else:
            print(f"::warning::Filtro '{game_filter}' esgotado — usando demais jogos p/ manter o dia")

    daily_batch = int(os.environ.get("DAILY_BATCH", "3"))
    pending_total = len(queue) - cursor
    # Estoque baixo: reduz ritmo p/ nunca zerar (3/dia normal)
    if pending_total <= 10:
        daily_batch = min(daily_batch, 1)
        print(f"::warning::Estoque crítico: {pending_total} clipes — ritmo reduzido p/ 1/dia")
    elif pending_total <= 30:
        daily_batch = min(daily_batch, 2)
        print(f"::warning::Estoque baixo: {pending_total} clipes — ritmo reduzido p/ 2/dia")
    elif pending_total <= 60:
        print(f"::notice::Estoque: {pending_total} clipes (~{pending_total // 3} dias)")
    # MURALHA: mantem daily_batch agendados em cada um dos proximos WALL_DAYS dias.
    # Video agendado (private+publishAt) publica SOZINHO, mesmo com token morto,
    # PC desligado ou quota zerada depois. Teto MAX_UPLOADS/run = quota-safe
    # (6x1600=9600 + retitle; estouros degradam com retry, sem corromper).
    WALL_DAYS = int(os.environ.get("WALL_DAYS", "14"))
    MAX_UPLOADS = int(os.environ.get("MAX_UPLOADS", "6"))

    now = datetime.now(BRT)
    today_str = now.strftime('%Y-%m-%d')
    print(f"Today: {now.strftime('%A %d/%m/%Y')}")

    scheduled = state.get("scheduled", {})
    for d in [d for d in scheduled if d < today_str]:
        del scheduled[d]  # limpa dias passados

    def day_slots(day_str):
        y, m, d = map(int, day_str.split("-"))
        base = now.replace(year=y, month=m, day=d, hour=12, minute=0, second=0, microsecond=0)
        return [base.replace(hour=h) for h in (12, 18, 22)]

    # Experimento A/B (2026-09): 1 clipe/dia publica DIRETO (public imediato)
    # vs resto agendado (publishAt). DIRECT_EXTRA=1 no cron durante o teste.
    direct_extra = int(os.environ.get("DIRECT_EXTRA", "0"))

    jobs = []  # (clip, publish_dt|None=public imediato, day_str)
    off = 0
    for ahead in range(WALL_DAYS):
        if len(jobs) >= MAX_UPLOADS:
            break
        day = now + timedelta(days=ahead)
        day_str = day.strftime('%Y-%m-%d')
        have = scheduled.get(day_str, 0)
        need = max(0, daily_batch - have)
        if need <= 0:
            continue
        day_batch = queue[cursor + off:cursor + off + min(need, MAX_UPLOADS - len(jobs))]
        if not day_batch:
            break
        slots = day_slots(day_str)[have:have + len(day_batch)]
        for clip, slot in zip(day_batch, slots):
            jobs.append((clip, slot, day_str))
        off += len(day_batch)
    if direct_extra > 0 and len(jobs) < MAX_UPLOADS + direct_extra:
        # job extra: publica DIRETO (sem agendar) p/ comparar com agendados
        extra = queue[cursor + off:cursor + off + direct_extra]
        for clip in extra:
            jobs.append((clip, None, today_str + "+direct"))
        off += len(extra)
        if extra:
            print(f"  +{len(extra)} direto (experimento A/B)")
    if not jobs:
        print("Muralha completa e sem buracos. Nada a agendar.")
        return
    remaining = len(queue) - cursor - len(jobs)
    print(f"Queue: uploading {len(jobs)} clips ({', '.join(sorted(set(d for _, _, d in jobs)))}), {remaining} remaining")
    if yt_upload:
        print("  YouTube: enabled")
    if tt_upload:
        print("  TikTok: enabled")
    if ig_upload:
        print("  Instagram: enabled")
    if fb_upload:
        print("  Facebook: enabled")

    for i, (clip, publish_dt, job_day) in enumerate(jobs):
        direct = publish_dt is None
        publish_iso = "public" if direct else publish_dt.replace(tzinfo=BRT).isoformat()
        file_path = REPO_DIR / clip.get("file", "clipcrafter/scheduled_uploads/clips/" + clip.get("clip_file", ""))

        print(f"  [{i+1}] {clip['title'][:60]}...", flush=True)
        title = clip["title"]
        desc = clip.get("desc", "")
        tags = clip.get("tags", ["Valorant"])
        results = []

        # YouTube upload
        if yt_upload:
            print(f"    -> YouTube ({'DIRETO' if direct else str(publish_dt.hour) + ':00'})...", end=" ", flush=True)
            try:
                vid = yt_upload(
                    video_path=str(file_path),
                    title=title,
                    description=desc,
                    tags=tags,
                    privacy_status=publish_iso,
                )
            except Exception as e:
                if "invalid_grant" in str(e):
                    print("TOKEN EXPIRADO (invalid_grant) — rode reauth.py e atualize YT_TOKEN_PICKLE")
                    from collections import Counter
                    for d, n in Counter(d for _, p, d in jobs[:i] if p is not None).items():
                        scheduled[d] = scheduled.get(d, 0) + n
                    state["scheduled"] = scheduled
                    state["cursor"] = cursor + i
                    save_queue(queue)
                    save_state(state)
                    sys.exit(1)
                raise
            if vid:
                print(f"OK https://youtube.com/shorts/{vid}")
                results.append(f"yt:{vid}")
                # Só tenta comentar se publicou DIRETO (agendado/privado dá 403;
                # o comment_backfill diário cobre o resto sem gastar quota à toa)
                if publish_iso == "public":
                    try:
                        from youtube_uploader import post_comment
                        comment = random.choice(COMMENT_HOOKS)
                        post_comment(vid, comment.format(**{"title": title}))
                    except Exception as e:
                        print(f"    (comment skipped: {e})")
                else:
                    print("    (comentário via backfill 23:30)")
            else:
                print("FAIL (quota?)")
                # avanca cursor só até os que já subiram: evita repostar amanhã
                from collections import Counter
                for d, n in Counter(d for _, p, d in jobs[:i] if p is not None).items():
                    scheduled[d] = scheduled.get(d, 0) + n
                state["scheduled"] = scheduled
                state["cursor"] = cursor + i
                save_queue(queue)
                save_state(state)
                print(f"\nParcial! Next cursor at {state['cursor']}/{len(queue)} (continua amanhã)")
                sys.exit(0)

        # TikTok upload
        if tt_upload:
            print(f"    -> TikTok...", end=" ", flush=True)
            try:
                hashtags = [t.replace(" ", "") for t in tags[:5]]
                tt_id = tt_upload(
                    video_path=str(file_path),
                    title=title,
                    description=desc,
                    hashtags=hashtags,
                )
                if tt_id:
                    print(f"OK https://tiktok.com/@{tt_id}")
                    results.append(f"tt:{tt_id}")
                else:
                    print("FAIL")
            except Exception as e:
                print(f"FAIL ({e})")

        # Instagram Reels upload
        if ig_upload:
            print(f"    -> Instagram...", end=" ", flush=True)
            try:
                ig_id = ig_upload(
                    video_path=str(file_path),
                    title=title,
                    description=desc,
                    tags=tags,
                )
                if ig_id:
                    print(f"OK media_id={ig_id}")
                    results.append(f"ig:{ig_id}")
                else:
                    print("FAIL")
            except Exception as e:
                print(f"FAIL ({e})")

        # Facebook Page video upload
        if fb_upload:
            print(f"    -> Facebook...", end=" ", flush=True)
            try:
                fb_id = fb_upload(
                    video_path=str(file_path),
                    title=title,
                    description=desc,
                    tags=tags,
                )
                if fb_id:
                    print(f"OK id={fb_id}")
                    results.append(f"fb:{fb_id}")
                else:
                    print("FAIL")
            except Exception as e:
                print(f"FAIL ({e})")

        if results:
            state["uploaded"].append({"idx": cursor + i, "title": title, "platforms": results})
            notify_discord(title, results)
        sys.stdout.flush()

    from collections import Counter
    for d, n in Counter(d for _, p, d in jobs if p is not None).items():
        scheduled[d] = scheduled.get(d, 0) + n
    state["scheduled"] = scheduled
    state.pop("buffer_date", None)
    state["cursor"] = cursor + len(jobs)
    state["last_upload_date"] = today_str
    save_queue(queue)
    save_state(state)
    done_days = sorted(set(d for _, _, d in jobs))
    print(f"\nDone! Next cursor at {state['cursor']}/{len(queue)} (dias: {', '.join(done_days)})")

if __name__ == "__main__":
    main()
