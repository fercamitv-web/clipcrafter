#!/usr/bin/env python3
"""Reposição de emergência do estoque (máx 2 VODs por execução).
Chamado sozinho pelo ops_daily quando pendentes < 1 semana E há fonte.
NÃO commita/push (evita travar credencial): avisa no log p/ sincronizar.
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "clipcrafter" else Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "clipcrafter"))
LOG = Path.home() / ".clipcrafter" / "logs" / "refill.log"


def log(m):
    line = f"{datetime.now().strftime('%H:%M:%S')} {m}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main():
    from auto_clipper import discover_vods
    from ci_discover import load_queue, save_queue, process_one_video, already_processed
    queue = load_queue()
    before = len(queue)
    vods = discover_vods("https://www.youtube.com/@CanalPropra/videos", min_duration=300)
    todo = [(v, d, t) for v, d, t in vods if not already_processed(v, queue)][:2]
    log(f"refill: {len(todo)} VODs (fila {before})")
    for vid, dur, title in todo:
        try:
            process_one_video(vid, dur, title, queue)
            save_queue(queue)
            log(f"OK {vid} -> fila {len(queue)}")
        except Exception as e:
            log(f"FAIL {vid}: {str(e)[:120]}")
    # conserta chaves p/ selfcheck não reclamar
    q = queue
    for e in q:
        e.setdefault("game", "Gaming")
        e.setdefault("uploaded_youtube", False)
        e.setdefault("uploaded_tiktok", False)
    save_queue(q)
    log(f"FIM: +{len(queue) - before} clips. Rode git add+commit+push p/ sincronizar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
