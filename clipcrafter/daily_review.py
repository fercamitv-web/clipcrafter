import os, sys, json, subprocess
from pathlib import Path

# --- ajusta o venv ---
venv = Path(__file__).parent.parent / "venv"   # C:\Users\ferca\OneDrive\Documentos\1\clipe-pro\venv
if venv.is_dir():
    sys.executable = str(venv / "Scripts/python.exe")
    os.chdir(venv.parent)                      # garante que os módulos do clipcrafter sejam encontrados
os.environ["PYTHONIOENCODING"] = "utf-8"

# --- 1. self‑check leve (compile + import + detect_game) ---
try:
    result = subprocess.run(
        [sys.executable, "clipcrafter/selfcheck.py"],
        capture_output=True, text=True, timeout=60000
    )
    lines = result.stdout.splitlines()
    ok   = [l for l in lines if "[OK]" in l]
    err  = [l for l in lines if "[ERR]" in l]
    summary = f"self‑check: {len(ok)} OK, {len(err)} ERR"
except Exception as e:
    summary = f"self‑check: ERRO ao executar ({e})"

# --- 2. saúde do token YouTube (refresh rápido) ---
token_ok = "NAO"
try:
    import pickle
    from pathlib import Path
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    p = Path.home() / ".clipcrafter" / "youtube_token.pickle"
    if p.exists():
        creds = pickle.load(open(p, "rb"))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            yt = build("youtube", "v3", credentials=creds)
            _ = yt.channels().list(part="id", mine=True).execute()
        token_ok = "OK"
except Exception:
    pass

# --- 3. integridade da fila ---
queue_ok = "NAO"
try:
    qp = Path("clipcrafter/scheduled_uploads/clip_queue.json")
    sp = Path("clipcrafter/scheduled_uploads/upload_state.json")
    if qp.exists() and sp.exists():
        q = json.load(open(qp, encoding="utf-8"))
        s = json.load(open(sp, encoding="utf-8"))
        if s.get("cursor", 0) <= len(q):
            queue_ok = "OK"
        else:
            # auto‑correção simples: ajusta o cursor ao tamanho real
            s["cursor"] = min(s["cursor"], len(q))
            json.dump(s, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            queue_ok = "OK (ajustado)"
except Exception:
    pass

# --- 4. relatório final ---
border = "=" * 50
report = f"""{border}
🗂️  REVISÃO DIÁRIA – início de sessão
{border}

{summary}
🔐  Token YouTube: {token_ok}
📋  Fila/clique:      {queue_ok}

{border}
Se houver ERR ou NAO verifique o log da Actions (GitHub) ou
re‑autentique o token no portal da Meta/Google.
{border}"""
# garante saída UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
print(report)
# exit code 1 se algum item indicar problema (para o Task Scheduler sinalizar)
sys.exit(1 if ("ERR" in summary or token_ok == "NAO" or queue_ok.startswith("NAO")) else 0)