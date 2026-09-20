#!/usr/bin/env python3
"""Via LOCAL de upload (redundância da Actions).
Chamado pelo revisar_dia.bat após ops_daily PASSAR:
  1. git pull (traz o que a CI já fez)
  2. se a CI já subiu hoje -> encerra sem gastar quota
  3. senão roda o mesmo ci_upload.main() com credencial local (~/.clipcrafter)
  4. commit + push do progresso (se falhar, avisa LOUD — próximo run da CI
     completa sem duplicar, graças ao prevmap + cursor parcial)
Uso manual: python clipcrafter/local_upload.py [--force]
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BRT = timezone(timedelta(hours=-3))
REPO = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "clipcrafter" else Path(__file__).resolve().parent
STATE_FILE = REPO / "clipcrafter" / "scheduled_uploads" / "upload_state.json"


def sh(*args):
    r = subprocess.run(list(args), cwd=str(REPO), capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    force = "--force" in sys.argv
    print("== Local upload (via redundante) ==")
    rc, out = sh("git", "pull", "--rebase", "origin", "master")
    print(out.strip().splitlines()[-1] if out.strip() else "(pull vazio)")
    # checagem dupla: data remota (vale mesmo se o pull falhar por sujeira local)
    rc2, out2 = sh("git", "show", "origin/master:clipcrafter/scheduled_uploads/upload_state.json")
    remote_date = ""
    if rc2 == 0:
        try:
            remote_date = json.loads(out2).get("last_upload_date", "")
        except Exception:
            pass
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"state ilegível: {e} — abortando por segurança")
        return 1
    today = datetime.now(BRT).strftime("%Y-%m-%d")
    if not force and (state.get("last_upload_date") == today or remote_date == today):
        print(f"CI já subiu hoje ({today}). Nada a fazer, quota preservada.")
        return 0
    print(f"CI ainda não subiu hoje ({today}) — assumindo via local...")
    sys.path.insert(0, str(REPO / "clipcrafter"))
    os.environ.setdefault("DAILY_BATCH", "3")
    try:
        from ci_upload import main as ci_main
        ci_main()
    except SystemExit as e:
        print(f"ci_upload encerrou com code {e.code}")
    except Exception as e:
        print(f"ERRO no upload local: {e}")
        return 1
    rc, out = sh("git", "add", "clipcrafter/scheduled_uploads/")
    rc, out = sh("git", "diff", "--cached", "--quiet")
    if rc == 0:
        print("Sem mudanças p/ commitar.")
        return 0
    sh("git", "-c", "user.name=clipcrafter-bot", "-c", "user.email=bot@clipcrafter",
       "commit", "-m", "Auto-update queue cursor after upload (via local)")
    rc, out = sh("git", "push", "origin", "master")
    print(out.strip().splitlines()[-1] if out.strip() else "(push vazio)")
    if rc != 0:
        print("!!! PUSH FALHOU — uploads foram feitos, mas a CI pode repetir. "
              "Rode 'git push origin master' manual quando der.")
        return 2
    print("OK: progresso sincronizado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
