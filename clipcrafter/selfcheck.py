#!/usr/bin/env python3
"""Selfcheck — daily diagnostics + safe auto-fixes for the clipcrafter pipeline.

Runs in CI (daily guard) and locally. Auto-fixes only issues that are safe to
fix non-destructively (queue hygiene, titles, descriptions, state bounds).
Exits 1 when it finds errors it cannot auto-fix, so the CI job turns red.

Invocation:  python clipcrafter/selfcheck.py
"""
import json
import os
import re
import sys
import types
import py_compile
from pathlib import Path

CI = Path(__file__).resolve().parent
REPO = CI.parent
CLIPS = CI / "scheduled_uploads" / "clips"
QUEUE = CI / "scheduled_uploads" / "clip_queue.json"
STATE = CI / "scheduled_uploads" / "upload_state.json"

VALID_GAMES = {"Valorant", "Valorant Duo", "League of Legends", "Roblox",
               "Minecraft", "FNAF", "Super Mario", "Horror Co-op",
               "Marvel Rivals", "Squid Game", "Coaching", "Gaming"}

ALL_CAPS_WORD = re.compile(r"\b[A-ZÀ-ÿ]{6,}\b")
CLICKBAIT_WORDS = re.compile(r"\bPRECISA VER\b|\bINACREDITAVEL\b|\bINSANO\b|\bMAIS LOUCO\b", re.I)
OLD_TITLE_FAMILIES = re.compile(
    r"- CanalPropra$|- Fercami Gameplay$|- Momento da Live$"
    r"|^MOMENTO QUE PAROU|^MOMENTOS QUE PAROU|^ESSE MOMENTO FOI|\bQUE VOCE PRECISA VER\b",
    re.I)

fixes = []
errors = []


def log_ok(msg):
    print(f"  [OK]    {msg}")


def log_fix(msg):
    print(f"  [FIX]   {msg}")
    fixes.append(msg)


def log_err(msg):
    print(f"  [ERR]   {msg}")
    errors.append(msg)


def save_queue(queue):
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def step_compile_all():
    print("== 1. Syntax (compile) ==")
    bad = 0
    for py in sorted(CI.glob("*.py")):
        try:
            py_compile.compile(str(py), doraise=True)
        except py_compile.PyCompileError as e:
            bad += 1
            log_err(f"{py.name}: {e}")
    if not bad:
        log_ok(f"{len(list(CI.glob('*.py')))} modules compile clean")


def step_import_and_unit_tests():
    print("== 2. Imports + unit tests (light) ==")
    sys.path.insert(0, str(CI))
    try:
        from content_detector import detect_game
    except Exception as e:
        log_err(f"cannot import content_detector: {e}")
        return
    try:
        from valorant_studio import ValorantStudio
    except Exception as e:
        log_err(f"cannot import valorant_studio: {e}")
        return
    log_ok("modules import clean")

    samples = {
        "Void cup #1 - Começamos com o pé esquerdo": "Valorant",
        "Fercami e a sua mira bamba !..": "Valorant",
        "Minecraft one block ep 2 - Propostas + Herobrine": "Minecraft",
        "SOBREVIVI 99 Noites na Floresta": "Minecraft",
        "Um arquivo que nunca ira ser descoberto o motivo": "Gaming",
        "O inicio de uma base ... (Lost Rooms) Pt 2": "Horror Co-op",
        "Até o sol renascer...(Frigid Dusk)": "Horror Co-op",
        "All star tower defense - o melhor defensor": "Roblox",
        "Five Nights at Freddys - o terror começa": "FNAF",
        "Somos a DUPLA do Quebra-Cabeças de Trabalho": "Valorant Duo",
    }
    for title, want in samples.items():
        got = detect_game(title)
        if got != want:
            log_err(f"detect_game({title[:40]!r}) -> {got!r}, expected {want!r}")
        else:
            log_ok(f"detect_game ok: {title[:35]!r} -> {want}")

    vs = ValorantStudio()
    vs.analysis = _dummy_analysis()
    vs.game = "Valorant"
    titles = [vs.generate_seo_title(vod_title=t) for t in list(samples)]
    for t in titles:
        problems = []
        caps = sum(1 for ch in t if ch.isupper())
        if len(t) > 100:
            problems.append("len>100")
        if re.search(r"#(?!\d)", t):
            problems.append("has hashtag in title")
        if caps / max(1, len(t)) > 0.55:
            problems.append("mostly caps")
        if CLICKBAIT_WORDS.search(t):
            problems.append("clickbait word")
        if OLD_TITLE_FAMILIES.search(t):
            problems.append("old title family")
        if problems:
            log_err(f"title rule violated {t!r}: {problems}")
        else:
            log_ok(f"title ok: {t[:55]!r}")


def _dummy_analysis():
    return types.SimpleNamespace(
        kill_count=0, event_type="highlight", agent="", map_name="", weapon="",
        is_ace=False, is_clutch=False, speech_text=None)


def step_queue_integrity():
    print("== 3. Queue integrity ==")
    if not QUEUE.exists():
        log_err("clip_queue.json missing")
        return
    try:
        queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    except Exception as e:
        log_err(f"clip_queue.json is not valid JSON: {e}")
        return
    if not isinstance(queue, list):
        log_err("clip_queue.json root is not a list")
        return

    required = ["file", "clip_file", "vod_id", "game", "title", "desc",
                "tags", "uploaded_youtube", "uploaded_tiktok"]
    for i, e in enumerate(queue):
        if not isinstance(e, dict):
            log_err(f"entry {i} is not an object")
            continue
        missing = [k for k in required if k not in e]
        if missing:
            log_err(f"entry {i} missing keys {missing}")
        if e.get("game") not in VALID_GAMES:
            log_err(f"entry {i} ({e.get('clip_file')}) unknown game {e.get('game')!r}")

    # missing files -> drop entry (non-destructive: file is gone anyway)
    alive = [e for e in queue if e.get("file") and (REPO / e["file"]).exists()]
    dropped = len(queue) - len(alive)
    if dropped:
        log_fix(f"dropped {dropped} queue entries whose files are missing")
        queue = alive

    cursor = load_cursor()
    if cursor >= len(queue):
        log_fix(f"cursor {cursor} >= queue {len(queue)}; clamped to {max(0, len(queue)-1)}")
        cursor = max(0, len(queue) - 1)
        set_cursor(cursor)
    elif cursor < 0:
        log_fix("cursor < 0; reset to 0")
        cursor = 0
        set_cursor(0)

    # title hygiene on pending entries
    seen = set(e["title"] for e in queue[:cursor])
    changed_title = 0
    for i in range(cursor, len(queue)):
        e = queue[i]
        t = e.get("title", "")
        new = t
        if "#clip" in new or new.endswith("#") or ' - CORTA' in new.upper():
            new = new.replace(" #clip", "").replace("#clip", "").rstrip("#").strip()
        if len(new) > 100:
            new = new[:97].rstrip() 
        if new and new != t:
            e["title"] = new
            changed_title += 1
        # ensure unique among pending + uploaded
        t2 = e["title"]
        if t2 in seen:
            n = 1
            base = re.sub(r"\s+pt\d+$", "", t2)
            while f"{base} pt{n}" in seen and n < 50:
                n += 1
            e["title"] = f"{base} pt{n}"
            seen.add(e["title"])
            changed_title += 1
        else:
            seen.add(t2)
    if changed_title:
        log_fix(f"normalized/deduped {changed_title} titles")
    else:
        log_ok(f"{len(queue)-cursor} pending, titles clean")

    # description hygiene on pending
    changed_desc = 0
    for i in range(cursor, len(queue)):
        e = queue[i]
        d = e.get("desc", "")
        if not isinstance(d, str) or not d.strip():
            d = "SE INSCREVA GRATIS e ative o sininho para nao perder NENHUM momento!\n\n#CanalPropra #Shorts\n"
            changed_desc += 1
        if "youtube.com/@CanalPropra" not in d:
            d = (d.rstrip() + "\n\nINSCREVA-SE no CanalPropra para mais momentos:\n"
                 "https://www.youtube.com/@CanalPropra\n").strip() + "\n"
            changed_desc += 1
        vid = e.get("vod_id", "")
        if vid and f"watch?v={vid}" not in d:
            d = d.rstrip() + f"\n\nQuer ver a partida completa? Assiste aqui:\nhttps://youtube.com/watch?v={vid}\n"
            changed_desc += 1
        if "#Shorts" not in d:
            d = d.rstrip() + "\n#Shorts\n"
            changed_desc += 1
        e["desc"] = d
        if not isinstance(e.get("tags"), list) or not e["tags"]:
            e["tags"] = ["ClipCrafter", "CanalPropra", "Shorts", "Gameplay"]
            changed_desc += 1
    if changed_desc:
        log_fix(f"repaired {changed_desc} descriptions/tags")

    clean_uploaded = None
    for i, u in enumerate(load_state().get("uploaded", [])):
        if u.get("idx", 0) >= len(queue):
            clean_uploaded = [x for x in load_state().get("uploaded", []) if x.get("idx", 0) < len(queue)]
            break
    if clean_uploaded is not None:
        st = load_state(); st["uploaded"] = clean_uploaded; save_state(st)
        log_fix(f"pruned uploaded history to {len(clean_uploaded)} entries")

    save_queue(queue)
    if not dropped and not changed_title and not changed_desc:
        log_ok("queue fully clean")


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def load_cursor():
    return int(load_state().get("cursor", 0))


def set_cursor(c):
    st = load_state()
    st["cursor"] = c
    save_state(st)


def step_pipeline_config():
    print("== 4. Pipeline config sanity ==")
    wf = REPO / ".github" / "workflows" / "upload_schedule.yml"
    if wf.exists() and "${{ secrets.YT_CLIENT_SECRET }}" not in wf.read_text(encoding="utf-8"):
        log_err("upload workflow no longer references YT_CLIENT_SECRET (check secrets wiring)")
    else:
        log_ok("upload workflow wired")


def main():
    print("=== clipcrafter selfcheck ===")
    step_compile_all()
    step_import_and_unit_tests()
    step_queue_integrity()
    step_pipeline_config()

    print("\n--- summary ---")
    print(f"  fixes applied:  {len(fixes)}")
    print(f"  unfixable errors: {len(errors)}")
    for e in errors:
        print(f"    - {e}")
    if errors:
        print("RESULT: FAIL (manual attention required)")
        sys.exit(1)
    print("RESULT: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()