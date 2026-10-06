#!/usr/bin/env python3
"""Leva extra de clips: próximos VODs não processados (máx 4).
Padrão via process_one_video; se 0 segmentos, fatiamento forçado uniforme.
Uso manual (foreground). Salva a fila a cada VOD.
"""
import gc
import json
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "clipcrafter" else Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "clipcrafter"))
from auto_clipper import discover_vods, download_clip, process_clip
from ci_discover import load_queue, save_queue, process_one_video, already_processed
from content_detector import detect_game

MAX_VODS = 4
FORCE_N = 5
FORCE_LEN = 20


def forced(vid, dur, title, queue, game):
    from pathlib import Path as _P
    import tempfile
    tmp = _P(tempfile.gettempdir()) / f"force_{vid}"
    tmp.mkdir(parents=True, exist_ok=True)
    n = 0
    step = max(45, (dur - 60 - FORCE_LEN) // max(1, FORCE_N))
    for idx in range(FORCE_N):
        s = 30 + idx * step
        e = min(s + FORCE_LEN, dur - 10)
        if e - s < 12:
            break
        raw, proc = tmp / f"c{idx}.mp4", tmp / f"c{idx}_s.mp4"
        if not download_clip(vid, s, e, str(raw)) or not raw.exists():
            continue
        try:
            ok, ct, hook, desc, tags = process_clip(str(raw), str(proc), game, vod_title=title, vod_id=vid)
        except Exception as ex:
            print(f"  force ERROR {ex}", flush=True)
            continue
        if ok and proc.exists():
            dest = REPO / "clipcrafter" / "scheduled_uploads" / "clips" / f"{vid}_clip{idx+1:02d}_shorts.mp4"
            shutil.copy2(proc, dest)
            queue.append({"vod_id": vid, "title": ct, "hook": hook or "", "desc": desc or "",
                          "tags": tags or [], "clip_file": dest.name,
                          "file": f"clipcrafter/scheduled_uploads/clips/{dest.name}",
                          "game": game, "uploaded_youtube": False, "uploaded_tiktok": False})
            save_queue(queue)
            print(f"  force OK -> {ct[:50]}", flush=True)
            n += 1
        gc.collect()
    return n


def main():
    queue = load_queue()
    before = len(queue)
    vods = discover_vods("https://www.youtube.com/@CanalPropra/videos", min_duration=300)
    todo = [(v, d, t) for v, d, t in vods if not already_processed(v, queue)][:MAX_VODS]
    print(f"leva: {len(todo)} VODs (fila {before})", flush=True)
    for vid, dur, title in todo:
        game = detect_game(title)
        n0 = sum(1 for e in queue if e.get("vod_id") == vid)
        try:
            process_one_video(vid, dur, title, queue)
        except Exception as e:
            print(f"FAIL {vid}: {str(e)[:120]}", flush=True)
        n1 = sum(1 for e in queue if e.get("vod_id") == vid)
        if n1 <= n0:
            print(f"0 segmentos p/ {vid} -> forçado uniforme", flush=True)
            n1 += forced(vid, dur, title, queue, game)
        save_queue(queue)
        print(f"{vid}: +{n1 - n0} clips (fila {len(queue)})", flush=True)
        gc.collect()
    for e in queue:
        e.setdefault("game", "Gaming")
        e.setdefault("uploaded_youtube", False)
        e.setdefault("uploaded_tiktok", False)
    save_queue(queue)
    print(f"FIM: +{len(queue) - before} clips. Commit + push p/ sincronizar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
