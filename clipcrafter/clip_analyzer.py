"""Clip analyzer v2 — energy, pace, silence detection with viral scoring (no numpy)"""
import json, os, math, struct, tempfile, subprocess

def extract_features(audio_path: str, duration: float = None) -> dict:
    sr = 22050
    frame_ms = 50
    frame_samples = sr * frame_ms // 1000

    # Convert to raw PCM
    tmp = tempfile.mktemp(suffix=".raw")
    args = ["ffmpeg", "-y", "-i", audio_path, "-f", "s16le", "-ac", "1", "-ar", str(sr)]
    if duration:
        args.extend(["-t", str(duration)])
    args.append(tmp)
    subprocess.run(args, capture_output=True)

    with open(tmp, "rb") as f:
        raw = f.read()
    os.unlink(tmp)

    # Convert to samples
    n = len(raw) // 2
    samples = []
    for i in range(n):
        val = struct.unpack_from("<h", raw, i * 2)[0]
        samples.append(float(val))

    # Frame energy
    n_frames = max(1, n // frame_samples)
    energy = []
    for i in range(n_frames):
        frame = samples[i * frame_samples : (i + 1) * frame_samples]
        rms = math.sqrt(sum(s * s for s in frame) / max(1, len(frame)))
        energy.append(rms)
    max_e = max(energy) if energy else 1
    energy_norm = [e / max_e for e in energy]

    # Silence
    silence_count = sum(1 for e in energy_norm if e < 0.02)
    silence_pct = silence_count / n_frames * 100 if n_frames else 0

    # Energy peaks
    peaks = 0
    for i in range(1, len(energy_norm) - 1):
        if energy_norm[i] > 0.6 and energy_norm[i] > energy_norm[i-1] and energy_norm[i] > energy_norm[i+1]:
            peaks += 1
    peak_rate = peaks / max(1, n_frames) * 100

    # Scene cuts (sudden energy changes)
    scene_cuts = 0
    for i in range(1, len(energy_norm)):
        if abs(energy_norm[i] - energy_norm[i-1]) > 0.3:
            scene_cuts += 1
    cut_rate = scene_cuts / max(1, len(energy_norm)) * 100

    # Excitement (composite)
    silence_ok = max(0, 1 - silence_pct / 50)
    energy_boost = min(1, sum(energy_norm) / max(1, len(energy_norm)) * 2)
    peak_ok = min(1, peak_rate / 20)
    excitement = (silence_ok * 0.3 + energy_boost * 0.4 + peak_ok * 0.3) * 100

    # Virality (research-based: 30-60s ideal, scene cuts + energy peaks = 86% signals)
    dur_seconds = n / sr
    dur_opt = 1.0 if 25 <= dur_seconds <= 55 else max(0.5, 1 - abs(dur_seconds - 37) / 60)
    cut_score = min(1, scene_cuts / 8)
    energy_score_v = min(1, peak_rate / 10)
    virality = (dur_opt * 0.25 + cut_score * 0.30 + energy_score_v * 0.30 + excitement / 100 * 0.15) * 100

    mean_db = 20 * math.log10(max(energy_norm[0] if energy_norm else 1, 1e-10))
    peak_db = max(20 * math.log10(max(v, 1e-10)) for v in energy_norm) if energy_norm else 0

    return {
        "duration": round(dur_seconds, 1),
        "silence_pct": round(silence_pct, 1),
        "mean_energy_db": round(mean_db, 1),
        "peak_energy_db": round(peak_db, 1),
        "energy_peaks": peaks,
        "energy_peak_rate": round(peak_rate, 2),
        "scene_cuts": scene_cuts,
        "scene_cut_rate": round(cut_rate, 2),
        "excitement": round(excitement, 1),
        "virality_score": round(virality, 1),
    }

def analyze_clip(video_path: str) -> dict:
    tmp = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                    "-ar", "22050", "-ac", "1", "-y", tmp], capture_output=True)
    feat = extract_features(tmp)
    os.unlink(tmp)
    return feat
