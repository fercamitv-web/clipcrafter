"""Auto Clipper - Fully automated resumable pipeline for Valorant clips"""
import sys, os, json, time, gc, subprocess, shutil, tempfile, traceback
from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE_DIR = os.path.expanduser("~/.clipcrafter")
STATE_FILE = os.path.join(STATE_DIR, "auto_clipper_state.json")
os.makedirs(STATE_DIR, exist_ok=True)

YT_PY = os.path.join(os.environ.get("TEMP", "C:/Temp"), "yt_env", "Scripts", "python.exe")
if not os.path.exists(YT_PY):
    YT_PY = sys.executable  # fallback to current Python (works on Linux CI)
BASE_DIR = os.path.expanduser("~/clipcrafter_downloads")

# ============================================================
# FASTER VIRAL DETECTOR (optimized for speed)
# ============================================================

@dataclass
class ViralSegment:
    start_sec: float
    end_sec: float
    score: float
    reason: str
    speech_ratio: float = 0.0

def detect_viral_fast(audio_path: str, video_duration: float,
                      energy_weight: float = 1.0,
                      excitement_weight: float = 0.5,
                      min_clip: float = 3.0, max_clip: float = 60.0,
                      sensitivity: float = 0.35, top_n: int = 20,
                      speech_weight: float = 0.0) -> List[ViralSegment]:
    """
    Optimized viral detection using audio energy + excitement + optional speech analysis.
    speech_weight > 0 enables speech-band filtering to prefer segments with voice.
    """
    from pydub import AudioSegment
    import numpy as np

    audio = AudioSegment.from_file(audio_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    samples = np.array(audio.get_array_of_samples()).astype(np.float32)
    sr = 16000
    total_s = len(samples) / sr
    if total_s < 0.5:
        return []

    if video_duration <= 0 or video_duration > total_s + 10:
        video_duration = total_s

    seg_dur = 0.05
    seg_n = int(seg_dur * sr)
    num = int(max(1, total_s / seg_dur))

    # RMS energy per segment
    energy = np.zeros(num, dtype=np.float64)
    for i in range(num):
        start = int(i * seg_n)
        seg = samples[start:start + seg_n]
        energy[i] = np.sqrt(np.mean(seg.astype(np.float64) ** 2))
    max_e = energy.max()
    if max_e > 0:
        energy /= max_e

    ws = max(1, int(0.3 / seg_dur))
    kernel = np.ones(ws) / ws
    energy_smooth = np.convolve(energy, kernel, mode='same')

    # Excitement via FFT on 1s windows
    fft_win = int(1.0 / seg_dur)
    excitement = np.zeros(num)
    for i in range(0, num, fft_win):
        end = min(i + fft_win, num)
        start_s = int(i * seg_n)
        end_s = min(int(end * seg_n), len(samples))
        chunk = samples[start_s:end_s]
        if len(chunk) > 100:
            cf = np.abs(np.fft.rfft(chunk))
            freqs = np.fft.rfftfreq(len(chunk), 1 / sr)
            high = np.sum(cf[freqs > 2000]) if np.any(freqs > 2000) else 0
            total = np.sum(cf) + 1e-10
            excitement[i:end] = high / total

    # Speech ratio per window (energy in 300-3000Hz band vs total)
    speech_ratio = np.zeros(num) if speech_weight > 0 else None
    if speech_weight > 0:
        for i in range(0, num, fft_win):
            end = min(i + fft_win, num)
            start_s = int(i * seg_n)
            end_s = min(int(end * seg_n), len(samples))
            chunk = samples[start_s:end_s]
            if len(chunk) > 100:
                cf = np.abs(np.fft.rfft(chunk))
                freqs = np.fft.rfftfreq(len(chunk), 1 / sr)
                speech_mask = (freqs >= 300) & (freqs <= 3000)
                low_mask = freqs < 300
                speech_e = np.sum(cf[speech_mask]**2) if np.any(speech_mask) else 0
                low_e = np.sum(cf[low_mask]**2) if np.any(low_mask) else 0
                total_e = speech_e + low_e + (np.sum(cf[~low_mask & ~speech_mask]**2) if np.any(~low_mask & ~speech_mask) else 0)
                if total_e > 1e-10:
                    sr_val = speech_e / total_e
                    # Penalize when bass dominates (music, not speech)
                    low_dom = low_e / total_e
                    if low_dom > 0.5:
                        sr_val *= 0.3
                    speech_ratio[i:end] = min(sr_val * 1.5, 1.0)

    # Combined score
    combined = (
        energy_weight * energy_smooth +
        excitement_weight * excitement
    )
    if speech_weight > 0 and speech_ratio is not None:
        combined += speech_weight * speech_ratio

    cn = combined.max()
    if cn > 0:
        combined /= cn

    threshold = np.percentile(combined, 100 - max(10, min(90, 80 - (sensitivity - 1.0) * 30)))
    threshold = max(threshold, np.mean(combined) * 1.2)
    above = combined > threshold

    segs_raw = []
    in_seg = False
    seg_start = 0
    for i in range(len(above)):
        if above[i] and not in_seg:
            in_seg = True
            seg_start = i
        elif not above[i] and in_seg:
            in_seg = False
            dur = (i - seg_start) * seg_dur
            if dur >= min_clip:
                segs_raw.append((seg_start, i))
    if in_seg:
        dur = (len(above) - seg_start) * seg_dur
        if dur >= min_clip:
            segs_raw.append((seg_start, len(above)))

    if not segs_raw:
        return []

    merged = []
    for s, e in segs_raw:
        t1 = s * seg_dur
        t2 = e * seg_dur
        if t2 > video_duration:
            t2 = video_duration
        if t2 - t1 > max_clip:
            mid = (t1 + t2) / 2
            merged.append((max(0, mid - max_clip/2), min(video_duration, mid + max_clip/2)))
        else:
            merged.append((t1, t2))

    final = []
    for s, e in merged:
        if final and (s - final[-1][1]) < 1.5:
            prev = final.pop()
            final.append((prev[0], max(prev[1], e)))
        else:
            final.append((s, e))

    results = []
    for s, e in final:
        si = int(s / seg_dur)
        ei = min(int(e / seg_dur), num - 1)
        seg_c = combined[si:ei + 1]
        score = float(np.mean(seg_c)) if len(seg_c) > 0 else 0
        peak = float(np.max(energy_smooth[si:ei + 1])) if len(seg_c) > 0 else 0
        avg_x = float(np.mean(excitement[si:ei + 1])) if len(seg_c) > 0 else 0
        avg_s = float(np.mean(speech_ratio[si:ei + 1])) if speech_ratio is not None and len(seg_c) > 0 else 0
        if peak > 0.7 and avg_x > 0.3:
            reason = "Grito / explosao"
        elif avg_s > 0.5:
            reason = "Fala / reacao"
        elif peak > 0.5:
            reason = "Alta energia"
        elif avg_x > 0.3:
            reason = "Agitacao / musica intensa"
        else:
            reason = "Momento de destaque"
        results.append(ViralSegment(s, e, score, reason, avg_s))

    # Filter: prefer segments with speech when available
    if speech_weight > 0 and results:
        results.sort(key=lambda x: (x.speech_ratio * 0.6 + x.score * 0.4), reverse=True)
        # Remove segments with zero speech if we have enough with speech
        speech_segs = [r for r in results if r.speech_ratio > 0.3]
        if len(speech_segs) >= top_n // 2:
            results = speech_segs + [r for r in results if r.speech_ratio <= 0.3]
    else:
        results.sort(key=lambda x: x.score, reverse=True)
    return results[:top_n]


# ============================================================
# STATE MANAGEMENT
# ============================================================

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE, "r"))
    return {"vods": {}, "completed_vods": [], "total_clips_uploaded": 0, "created": time.time()}

def save_state(state):
    state["updated"] = time.time()
    json.dump(state, open(STATE_FILE, "w"), indent=2)


# ============================================================
# VOD DISCOVERY
# ============================================================

def discover_vods(channel_url: str = "https://www.youtube.com/@CanalPropra/videos",
                  min_duration: int = 600) -> List[tuple]:
    """Discover regular uploaded videos from channel (not livestreams). Returns [(id, duration, title), ...]"""
    print(f"  Discovering VODs from {channel_url}...", flush=True)
    r = subprocess.run([YT_PY, "-m", "yt_dlp", "--flat-playlist", "--dump-single-json",
                        channel_url], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"  FAIL: {r.stderr[-200:]}")
        return []
    data = json.loads(r.stdout)
    entries = data.get("entries", [data])
    vods = []
    for e in entries:
        if not e: continue
        live = e.get("live_status")
        if live is not None:
            continue  # skip livestream VODs
        vid = e.get("id", "")
        dur = e.get("duration", 0)
        title = e.get("title", "")
        if dur >= min_duration:
            vods.append((vid, dur, title))
    print(f"  Found {len(vods)} VODs >= {min_duration//60}min (filtered livestreams)")
    return vods


# ============================================================
# AUDIO DOWNLOAD
# ============================================================

def _cookies_args() -> list:
    """Return yt-dlp args for cookies if YT_COOKIES env is set."""
    c = os.environ.get("YT_COOKIES", "")
    if c:
        p = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
        if not os.path.exists(p):
            import base64
            try:
                data = base64.b64decode(c).decode("utf-8")
                with open(p, "w") as f:
                    f.write(data)
            except Exception:
                return []
        return ["--cookies", p]
    return []

def download_audio(vod_id: str, out_dir: str) -> Optional[str]:
    """Download m4a audio with -k to keep file. Returns path or None."""
    m4a = os.path.join(out_dir, f"{vod_id}.m4a")
    if os.path.exists(m4a) and os.path.getsize(m4a) > 100000:
        return m4a
    print(f"    Downloading audio...", end=" ", flush=True)
    cmd = [YT_PY, "-m", "yt_dlp", "-f", "140", "-k"] + _cookies_args() + \
          ["-o", m4a, f"https://youtube.com/watch?v={vod_id}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if os.path.exists(m4a) and os.path.getsize(m4a) > 100000:
        print(f"OK ({os.path.getsize(m4a)//1024}KB)")
        return m4a
    print(f"FAIL (rc={r.returncode})")
    err = r.stderr.strip()[-500:] if r.stderr else ""
    out = r.stdout.strip()[-500:] if r.stdout else ""
    if err:
        print(f"    {err}")
    if out:
        print(f"    {out}")
    return None


# ============================================================
# CLIP DOWNLOAD
# ============================================================

def download_clip(vod_id: str, start: float, end: float, output_path: str) -> bool:
    """Download a single clip segment."""
    if os.path.exists(output_path) and os.path.getsize(output_path) > 50000:
        return True
    cmd = [YT_PY, "-m", "yt_dlp", "-f", "18", "--download-sections", f"*{start}-{end}",
           "--force-keyframes-at-cuts"] + _cookies_args() + \
          ["-o", output_path, f"https://youtube.com/watch?v={vod_id}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 50000


# ============================================================
# CLIP PROCESSING
# ============================================================

def process_clip(src: str, dst: str, game: str = "Valorant") -> tuple:
    """Process a clip: shorts mode + hook overlay. Returns (ok, title, hook, desc, tags)."""
    from video_processor import VideoProcessor
    from valorant_studio import ValorantStudio

    vs = ValorantStudio()
    vs.game = game
    proc = VideoProcessor()
    try:
        if not proc.load(src):
            return False, f"{game} - CanalPropra #clip", "", "", [game]
        hook_overlay = vs.generate_hook_overlay()
        ok = proc.export_clip(0, proc.duration, dst,
            shorts_mode=True, viral_audio=True,
            add_subtitles=True, hook_text=hook_overlay, loop_mode=True,
            add_watermark=True, watermark_text="@CanalPropra")
        if ok:
            analysis = getattr(proc, "_analysis", None)
            if analysis and analysis.speech_text:
                a2 = vs.analyze_transcript(analysis.speech_text.split(" | "))
                title = vs.generate_seo_title(kill_count=a2.kill_count, event_type=a2.event_type,
                    agent=a2.agent, map_name=a2.map_name, weapon=a2.weapon)
                hook = vs.generate_hook("auto")
            else:
                title = vs.generate_seo_title()
                hook = vs.generate_hook()
            desc, tags = vs.get_description_tags(game)
            return True, title, hook or "", desc, tags
        return False, f"{game} - CanalPropra #clip", "", "", [game]
    finally:
        proc.cleanup()
        gc.collect()


# ============================================================
# UPLOAD
# ============================================================

def upload_clip(path: str, title: str, desc: str, tags: list) -> Optional[str]:
    """Upload to YouTube. Returns video ID or None."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from youtube_uploader import upload_video
    os.environ["OAUTH_PATH"] = os.path.expanduser("~/client_secret.json")
    try:
        return upload_video(path, title=title, description=desc,
                           tags=tags, privacy_status="public")
    except Exception as e:
        print(f"  Upload error: {e}", flush=True)
        return None


# ============================================================
# PARALLEL CLIP PROCESSING
# ============================================================

def _process_one(pair):
    """Process a single clip (for parallel execution). Returns (idx, ok, title, hook, desc, tags)."""
    idx, clip_path, processed_path, game = pair
    try:
        ok, title, hook, desc, tags = process_clip(clip_path, processed_path, game)
        return idx, ok, title, hook, desc, tags
    except Exception as e:
        return idx, False, str(e), "", "", []

def process_batch(pairs, max_workers=2):
    """Process multiple clips in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_process_one, p): p[0] for p in pairs}
        for f in as_completed(futures):
            idx, ok, title, hook, desc, tags = f.result()
            results[idx] = (ok, title, hook, desc, tags)
    return results


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(vod_id: str, duration: int, vod_title: str,
                 state: dict, max_clips: int = 15, sensitivity: float = 0.35,
                 jobs: int = 1):
    """Run full pipeline for one VOD."""
    # Detect game type from VOD title
    from content_detector import detect_game
    game = detect_game(vod_title)
    
    vod_state = state["vods"].get(vod_id, {
        "title": vod_title, "duration": duration, "game": game,
        "audio_done": False, "segments": [],
        "clips_downloaded": [], "clips_processed": [], "clips_uploaded": [],
        "skip": False
    })
    state["vods"][vod_id] = vod_state
    vod_state["game"] = game  # Update game each run

    if vod_state.get("skip"):
        print(f"  SKIP (marked skip)")
        return

    vod_dir = os.path.join(BASE_DIR, vod_id)
    clips_dir = os.path.join(vod_dir, "clips")
    processed_dir = os.path.join(vod_dir, "processed")
    os.makedirs(clips_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Step 1: Download audio
    if not vod_state["audio_done"]:
        print(f"\n{'='*50}")
        print(f"VOD: {vod_id} ({duration//60}:{duration%60:02d}) - {vod_title}")
        print(f"{'='*50}")
        audio_path = download_audio(vod_id, vod_dir)
        if not audio_path:
            print(f"  FAILED to download audio, skipping VOD")
            vod_state["skip"] = True
            save_state(state)
            return
        vod_state["audio_done"] = True
        save_state(state)
    else:
        audio_path = os.path.join(vod_dir, f"{vod_id}.m4a")
        if not os.path.exists(audio_path):
            audio_path = os.path.join(vod_dir, f"{vod_id}.wav")
        print(f"\n  VOD: {vod_id} ({duration//60}:{duration%60:02d}) - {vod_title}")

    # Step 2: Detect viral moments
    if not vod_state["segments"]:
        print(f"  Detecting viral moments...", end=" ", flush=True)
        t0 = time.time()
        try:
            segs = detect_viral_fast(audio_path, duration,
                                     sensitivity=sensitivity, top_n=max_clips + 5,
                                     speech_weight=0.6)
            elapsed = time.time() - t0
            print(f"{len(segs)} segments ({elapsed:.0f}s)")
            for s in segs:
                m, sec = divmod(int(s.start_sec), 60)
                print(f"    {m:02d}:{sec:02d} ({s.end_sec-s.start_sec:.0f}s) sc={s.score:.3f}")
            vod_state["segments"] = [{"start": s.start_sec, "end": s.end_sec,
                                       "score": s.score, "reason": s.reason} for s in segs]
            save_state(state)
        except Exception as e:
            print(f"FAIL: {e}")
            vod_state["skip"] = True
            save_state(state)
            return

    if not vod_state["segments"]:
        print(f"  No segments found, skipping")
        vod_state["skip"] = True
        save_state(state)
        return

    segs = vod_state["segments"]
    downloaded = set(vod_state.get("clips_downloaded", []))
    processed = set(vod_state.get("clips_processed", []))
    uploaded = set(vod_state.get("clips_uploaded", []))
    clip_meta = vod_state.get("clip_metadata", {})

    print(f"  Already: {len(downloaded)}/{len(processed)}/{len(uploaded)} downloaded/processed/uploaded")

    def _extend_seg(start, end, min_dur=20, max_dur=50, video_dur=duration):
        """Extend segment to minimum duration by adding context before/after."""
        dur = end - start
        if dur >= min_dur:
            return start, end
        extra = (min_dur - dur) / 2
        new_start = max(0, start - extra)
        new_end = min(video_dur if video_dur > 0 else 99999, end + extra)
        # If still too short, add more
        if new_end - new_start < min_dur:
            if new_start == 0:
                new_end = min(video_dur, new_start + min_dur)
            else:
                new_start = max(0, new_end - min_dur)
        if new_end - new_start > max_dur:
            mid = (new_start + new_end) / 2
            new_start = max(0, mid - max_dur/2)
            new_end = min(video_dur, mid + max_dur/2)
        return new_start, new_end

    # Step 3: Download ALL clips first (extend to 20s minimum)
    need_dl = [i for i in range(min(len(segs), max_clips)) if i not in downloaded]
    for idx in need_dl:
        seg = segs[idx]
        ext_start, ext_end = _extend_seg(seg["start"], seg["end"])
        label = f"clip_{idx+1:02d}"
        path = os.path.join(clips_dir, f"{label}.mp4")
        print(f"  DL {idx+1}/{len(segs)} at {int(ext_start)//60}:{int(ext_start)%60:02d} "
              f"({ext_end-ext_start:.0f}s, original {seg['end']-seg['start']:.0f}s)...", end=" ", flush=True)
        ok = download_clip(vod_id, ext_start, ext_end, path)
        if ok:
            print(f"OK", flush=True)
            downloaded.add(idx)
            vod_state["clips_downloaded"] = sorted(list(downloaded))
            save_state(state)
        else:
            print(f"FAIL", flush=True)

    if not downloaded:
        print(f"  No clips downloaded, skipping")
        return

    # Step 4: Process clips (sequential or parallel)
    need_proc = [i for i in sorted(downloaded) if i not in processed]
    game_name = vod_state.get("game", "Valorant")
    if need_proc:
        if jobs > 1 and len(need_proc) > 1:
            pairs = [(i, os.path.join(clips_dir, f"clip_{i+1:02d}.mp4"),
                      os.path.join(processed_dir, f"clip_{i+1:02d}_shorts.mp4"),
                      game_name) for i in need_proc]
            print(f"  Processing {len(need_proc)} clips ({jobs} workers)...", flush=True)
            t0 = time.time()
            results = process_batch(pairs, max_workers=jobs)
            for idx in need_proc:
                ok, clip_title, hook, desc, tags = results.get(idx, (False, "", "", "", []))
                if ok:
                    processed.add(idx)
                    vod_state["clips_processed"] = sorted(list(processed))
                    clip_meta[str(idx)] = {"title": clip_title, "hook": hook, "desc": desc, "tags": tags}
                    vod_state["clip_metadata"] = clip_meta
                    save_state(state)
                    print(f"    clip_{idx+1:02d}: {clip_title} ({time.time()-t0:.0f}s elapsed)", flush=True)
                else:
                    print(f"    clip_{idx+1:02d}: FAIL {clip_title}", flush=True)
        else:
            for idx in need_proc:
                seg = segs[idx]
                label = f"clip_{idx+1:02d}"
                clip_path = os.path.join(clips_dir, f"{label}.mp4")
                processed_path = os.path.join(processed_dir, f"{label}_shorts.mp4")
                print(f"  {label} processing...", end=" ", flush=True)
                t0 = time.time()
                ok, clip_title, hook, desc, tags = False, "", "", "", []
                try:
                    ok, clip_title, hook, desc, tags = process_clip(clip_path, processed_path, game_name)
                except Exception as e:
                    print(f"ERROR: {e}", flush=True)
                if ok:
                    print(f"({time.time()-t0:.0f}s) {clip_title}", flush=True)
                    processed.add(idx)
                    vod_state["clips_processed"] = sorted(list(processed))
                    clip_meta[str(idx)] = {"title": clip_title, "hook": hook, "desc": desc, "tags": tags}
                    vod_state["clip_metadata"] = clip_meta
                    save_state(state)
                else:
                    print(f"FAIL ({time.time()-t0:.0f}s)", flush=True)

    # Step 5: Upload all processed clips
    need_ul = [i for i in sorted(processed) if i not in uploaded]
    for idx in need_ul:
        seg = segs[idx] if idx < len(segs) else None
        clip_label = f"clip_{idx+1:02d}"
        processed_path = os.path.join(processed_dir, f"{clip_label}_shorts.mp4")
        if not os.path.exists(processed_path):
            print(f"  {clip_label}: processed file not found, skipping")
            continue
        # Read metadata from saved state
        meta = clip_meta.get(str(idx), {})
        ul_title = meta.get("title", f"highlight - Valorant #clip")
        ul_desc = meta.get("desc", "Clip da live! #Valorant #ClipCrafter #CanalPropra")
        ul_tags = meta.get("tags", ["Valorant", "shorts"])
        print(f"  Upload {clip_label}...", end=" ", flush=True)
        vid = upload_clip(processed_path, ul_title, ul_desc, ul_tags)
        if vid:
            print(f"OK! https://youtube.com/watch?v={vid}", flush=True)
            uploaded.add(idx)
            vod_state["clips_uploaded"] = sorted(list(uploaded))
            state["total_clips_uploaded"] = state.get("total_clips_uploaded", 0) + 1
            save_state(state)
        else:
            print(f"FAIL", flush=True)
        gc.collect()

    state.setdefault("completed_vods", [])
    if vod_id not in state["completed_vods"]:
        state["completed_vods"].append(vod_id)
    save_state(state)
    print(f"  DONE: {len(uploaded)} clips uploaded from this VOD")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto Clipper - Valorant clip pipeline")
    parser.add_argument("--vods", nargs="*", help="Specific VOD IDs to process")
    parser.add_argument("--max-clips", type=int, default=15, help="Max clips per VOD")
    parser.add_argument("--sensitivity", type=float, default=0.35, help="Detection sensitivity")
    parser.add_argument("--channel", help="Channel URL to discover VODs")
    parser.add_argument("--min-duration", type=int, default=1800, help="Min VOD duration in seconds")
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--list-vods", action="store_true", help="Just list VODs and exit")
    parser.add_argument("--reset", action="store_true", help="Reset state for listed VODs")
    parser.add_argument("--once", action="store_true", help="Process one VOD then stop")
    parser.add_argument("--jobs", type=int, default=1, help="Parallel clip processing workers")
    args = parser.parse_args()

    state = load_state()
    os.environ["PATH"] = f"{os.environ.get('TEMP', 'C:/Temp')}/yt_env/Scripts;{os.environ.get('PATH', '')}"

    # Discover or use provided VODs
    if args.vods:
        vods = [(v, 99999, f"vod_{v}") for v in args.vods]  # duration auto-detected from audio
    elif args.channel:
        vods = discover_vods(args.channel, args.min_duration)
    else:
        # Default: already-known valorant VODs
        vods = [
            # Already processed manually: VOD1 (sKyHcON-MHA), VOD2 (0xHD5y_weH0), VOD3 (2ZEba7_AW7I)
            # Already processed by pipeline: 0jptBKFXf7I
            ("fxDqwSuNIKA", 5794, "tentando evoluir no valorant"),
            ("CHuKAPB7N8o", 6501, "tentando evoluir no valorant"),
            ("gwBxG09I-Fw", 13261, "tentando evoluir no valorant"),
            ("sUIc4YVqYIc", 2610, "tentando evoluir no valorant"),
            ("BHcDPU_Srxs", 2077, "tentando evoluir no valorant"),
            ("pWOa6rfA8_Q", 2881, "tentando evoluir no valorant"),
            ("PqkyWFFZoZ0", 1649, "tentando evoluir no valorant"),
            ("JUXE-h9GQ4U", 2835, "tentando evoluir no valorant"),
            ("nbX-UgrkT1c", 2001, "tentando evoluir no valorant"),
            ("Pc81CFT20Jo", 1876, "tentando evoluir no valorant"),
            ("MF7-edYfZyg", 9396, "tentando evoluir no valorant"),
            ("B4w7tZlRrYg", 2969, "tentando evoluir no valorant"),
            ("DUe1S2aRN-E", 3750, "tentando evoluir no valorant"),
            ("ovhdZgXLY_0", 5617, "tentando evoluir no valorant"),
            ("ma_w80gDwzQ", 2067, "tentando evoluir no valorant"),
        ]

    if args.list_vods:
        print(f"Found {len(vods)} VODs:")
        for vid, dur, t in vods:
            status = "DONE" if vid in state.get("completed_vods", []) else "PENDING"
            done = len(state.get("vods", {}).get(vid, {}).get("clips_uploaded", []))
            print(f"  [{status}] {vid}: {dur//60}:{dur%60:02d} - {t} ({done} clips)")
        return

    if args.reset:
        for vid, _, _ in vods:
            if vid in state.get("vods", {}):
                del state["vods"][vid]
            if vid in state.get("completed_vods", []):
                state["completed_vods"].remove(vid)
        save_state(state)
        print("Reset done")
        return

    # Process VODs
    t_start = time.time()
    total_vods = len(vods)
    processed_count = 0

    for i, (vod_id, duration, vod_title) in enumerate(vods):
        # Skip already completed
        if vod_id in state.get("completed_vods", []):
            print(f"\n[{i+1}/{total_vods}] SKIP {vod_id} (already completed)")
            processed_count += 1
            continue

        print(f"\n\n{'#'*60}")
        print(f"# VOD [{i+1}/{total_vods}]: {vod_id}")
        print(f"# {vod_title}")
        print(f"# {duration//60}:{duration%60:02d}")
        print(f"{'#'*60}")

        try:
            run_pipeline(vod_id, duration, vod_title, state,
                        max_clips=args.max_clips, sensitivity=args.sensitivity,
                        jobs=args.jobs)
        except Exception as e:
            print(f"  FATAL ERROR on {vod_id}: {e}", flush=True)
            traceback.print_exc()
            print(f"  Continuing to next VOD...", flush=True)

        processed_count += 1
        elapsed = time.time() - t_start
        per_vod = elapsed / processed_count
        remaining = total_vods - processed_count
        eta = per_vod * remaining
        print(f"\n  Progress: {processed_count}/{total_vods} VODs "
              f"({elapsed/60:.0f}min elapsed, ETA: {eta/60:.0f}min)")

        if args.once:
            print("  --once: stopping after first VOD")
            break

    total = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"ALL DONE! {processed_count} VODs processed in {total/60:.0f}min")
    print(f"Total clips uploaded: {state.get('total_clips_uploaded', 0)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
