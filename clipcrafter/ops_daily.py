#!/usr/bin/env python3
# ops_daily.py - Sistema diário de revisão operacional
# Roda: selfcheck + daily_review + checagens extras, com auto-correção segura
import os, sys, json, subprocess, shutil, time
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name=="clipcrafter" else Path(__file__).resolve().parent
CLIP = REPO / "clipcrafter"
QUEUE_FILE = CLIP / "scheduled_uploads" / "clip_queue.json"
STATE_FILE = CLIP / "scheduled_uploads" / "upload_state.json"
LOG_DIR = Path.home() / ".clipcrafter" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"ops_daily_{datetime.now().strftime('%Y-%m-%d')}.log"

def log(msg):
    print(msg, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg+"\n")
    except: pass

def run_selfcheck():
    log("== Selfcheck ==")
    # usa o selfcheck existente
    py = sys.executable
    r = subprocess.run([py, str(CLIP/"selfcheck.py")], capture_output=True, text=True)
    log(r.stdout)
    if r.stderr:
        log(r.stderr)
    return r.returncode == 0

def check_queue():
    log("== Queue health ==")
    try:
        q = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        s = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        cursor = s.get("cursor", 0)
        # auto-fix 1: cursor clamp
        if cursor > len(q):
            log(f"[FIX] cursor {cursor} > len {len(q)} -> clamp to {len(q)}")
            s["cursor"] = len(q)
            STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
        # auto-fix 2: missing keys
        fixed=0
        for e in q:
            if "game" not in e:
                e["game"]="Gaming"; fixed+=1
            if "uploaded_youtube" not in e:
                e["uploaded_youtube"]=False
            if "uploaded_tiktok" not in e:
                e["uploaded_tiktok"]=False
        if fixed:
            log(f"[FIX] {fixed} entries missing keys -> preenchido")
            QUEUE_FILE.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
        # report
        pending = len(q)-s["cursor"]
        log(f"[OK] queue {len(q)} total, cursor {s['cursor']}, pendentes {pending}")
        # dedup titles
        from collections import Counter
        titles=[(e.get("title") or "").strip().lower() for e in q]
        dup=[t for t,c in Counter(titles).items() if c>1 and t]
        if dup:
            log(f"[WARN] {len(dup)} títulos duplicados (auto-fix via selfcheck)")
        else:
            log("[OK] sem duplicatas")
        return True
    except Exception as e:
        log(f"[ERR] queue check: {e}")
        return False

def check_token():
    log("== Token YouTube ==")
    try:
        import pickle
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        p = Path.home()/".clipcrafter"/"youtube_token.pickle"
        if not p.exists():
            log("[WARN] token não encontrado (precisa reautenticar)")
            return False
        creds = pickle.load(open(p,"rb"))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            log("[OK] token refresh OK")
            # salva
            pickle.dump(creds, open(p,"wb"))
        else:
            log("[OK] token válido")
        # teste rápido API
        yt = build("youtube","v3", credentials=creds)
        yt.channels().list(part="id", mine=True).execute()
        log("[OK] API YouTube respondeu")
        return True
    except Exception as e:
        log(f"[ERR] token/API: {e}")
        log("  -> rode: python \"%TEMP%\\opencode\\reauth.py\" e atualize GH secret YT_TOKEN_PICKLE")
        return False

def check_tools():
    log("== Ferramentas ==")
    ok=True
    for cmd, name in [(["ffmpeg","-version"],"ffmpeg"), (["yt-dlp","--version"],"yt-dlp")]:
        try:
            r=subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            ver=(r.stdout or r.stderr).splitlines()[0][:80] if (r.stdout or r.stderr) else "?"
            log(f"[OK] {name}: {ver}")
        except Exception as e:
            log(f"[ERR] {name} não encontrado: {e}")
            ok=False
    return ok

def check_last_run():
    log("== Último upload (local state) ==")
    try:
        s=json.loads(STATE_FILE.read_text(encoding="utf-8"))
        upl=s.get("uploaded",[])
        log(f"[OK] {len(upl)} uploads registrados, cursor {s.get('cursor')}")
        return True
    except Exception as e:
        log(f"[ERR] state: {e}")
        return False

def main():
    log("="*60)
    log(f"OPS DAILY {datetime.now().isoformat()}")
    log("="*60)
    results=[]
    results.append(("selfcheck", run_selfcheck()))
    results.append(("queue", check_queue()))
    results.append(("token", check_token()))
    results.append(("tools", check_tools()))
    results.append(("last_run", check_last_run()))
    log("-"*60)
    fails=[k for k,v in results if not v]
    if not fails:
        log("RESULT: PASS - tudo OK, auto-correções aplicadas se necessário")
        log(f"Log salvo em: {LOG_FILE}")
        return 0
    else:
        log(f"RESULT: FAIL - falhas em: {', '.join(fails)}")
        log(f"Log salvo em: {LOG_FILE}")
        log("Ação: verifique o log, rode reauth se token, ou me chame para consertar")
        return 1

if __name__=="__main__":
    sys.exit(main())
