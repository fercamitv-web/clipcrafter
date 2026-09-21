#!/usr/bin/env python3
"""Reprocessa os clipes pendentes a partir do RAW com o processador atual.
Uso: campanha longa em segundo plano (trava de instância única).
  python clipcrafter/reprocess_queue.py [--all | --limit N]
Padrão: só arquivos ainda não processados nesta campanha (estado persistente).
Idempotente: reprocessar de novo gera o mesmo padrão (a partir do raw).
"""
import json
import os
import re
import shutil
import sys
import time
import gc
from pathlib import Path

REPO = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "clipcrafter" else Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "clipcrafter"))
QUEUE = REPO / "clipcrafter" / "scheduled_uploads" / "clip_queue.json"
STATE = REPO / "clipcrafter" / "scheduled_uploads" / "upload_state.json"
CLIPS = REPO / "clipcrafter" / "scheduled_uploads" / "clips"
WORK = Path.home() / ".clipcrafter" / "ci_work"
CFG = Path.home() / ".clipcrafter"
PROG = CFG / "reprocess_state.json"
LOG = CFG / "logs" / "reprocess.log"
LOCK = CFG / "reprocess.lock"

CFG.mkdir(parents=True, exist_ok=True)
(LOG.parent).mkdir(parents=True, exist_ok=True)


def log(m):
    line = f"{time.strftime('%H:%M:%S')} {m}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def raw_for(entry):
    cf = entry.get("clip_file", "")
    vid = entry.get("vod_id", "")
    m = re.match(r"final_(.+)_seg(\d+)\.mp4$", cf)
    if m and vid:
        return WORK / vid / "clips" / f"raw_seg{m.group(2)}.mp4"
    m = re.match(r"eI4H_qJgySU_clip(\d+)_shorts\.mp4$", cf)
    if m:
        return WORK / "eI4H_qJgySU" / "clips" / f"clip_{m.group(1)}.mp4"
    m = re.match(r"([A-Za-z0-9_-]{11})_clip(\d+)_shorts\.mp4$", cf)
    if m:
        return WORK / m.group(1) / "clips" / f"clip_{m.group(2)}.mp4"
    return None


def main():
    from auto_clipper import process_clip
    if LOCK.exists():
        try:
            _pid = int(LOCK.read_text().strip())
            os.kill(_pid, 0)
            print(f"Outra instancia ativa (pid {_pid}), saindo.")
            return 1
        except (OSError, ValueError):
            pass
    LOCK.write_text(str(os.getpid()))
    try:
        limit = None
        for a in sys.argv[1:]:
            if a.startswith("--limit"):
                limit = int(a.split("=")[1] if "=" in a else sys.argv[sys.argv.index(a) + 1])
        q = json.loads(QUEUE.read_text(encoding="utf-8"))
        s = json.loads(STATE.read_text(encoding="utf-8"))
        cursor = s["cursor"]
        done = set(json.loads(PROG.read_text(encoding="utf-8"))["done"]) if PROG.exists() else set()
        if "--all" in sys.argv:
            done = set()
        order, seen, idxs_of = [], set(), {}
        for i in range(cursor, len(q)):
            cf = q[i].get("clip_file", "")
            idxs_of.setdefault(cf, []).append(i)
            if cf not in seen:
                seen.add(cf)
                order.append(cf)
        todo = [cf for cf in order if cf not in done]
        if limit:
            todo = todo[:limit]
        log(f"START pending={len(q)-cursor} unique={len(order)} todo={len(todo)}")
        for n, cf in enumerate(todo, 1):
            idxs = idxs_of[cf]
            e0 = q[idxs[0]]
            raw = raw_for(e0)
            if not raw or not raw.exists():
                log(f"[{n}/{len(todo)}] SKIP no raw {cf}")
                done.add(cf)
                continue
            dst = CLIPS / (Path(cf).stem + "_repro.mp4")
            try:
                ok, title, hook, desc, tags = process_clip(
                    str(raw), str(dst), e0.get("game", "Gaming"),
                    vod_title=e0.get("title", ""), vod_id=e0.get("vod_id", ""))
                if ok and dst.exists() and dst.stat().st_size > 50000:
                    shutil.move(str(dst), str(CLIPS / cf))
                    for i in idxs:
                        q[i]["title"] = title
                        q[i]["desc"] = desc
                        q[i]["tags"] = tags
                    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
                    log(f"[{n}/{len(todo)}] OK {cf} -> {title[:50]}")
                else:
                    log(f"[{n}/{len(todo)}] FAIL {cf} ({title})")
                    if dst.exists():
                        dst.unlink()
            except Exception as ex:
                log(f"[{n}/{len(todo)}] ERROR {cf}: {ex}")
            done.add(cf)
            PROG.write_text(json.dumps({"done": sorted(done)}, ensure_ascii=False), encoding="utf-8")
            gc.collect()
        log("DONE all processed")
        return 0
    finally:
        try:
            LOCK.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
