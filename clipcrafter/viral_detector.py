import numpy as np
from pydub import AudioSegment
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class ViralSegment:
    start_sec: float
    end_sec: float
    score: float
    reason: str

def detect_viral_moments(audio_path: str, video_duration: float,
                          energy_weight: float = 1.0,
                          excitement_weight: float = 0.5,
                          min_clip_duration: float = 3.0,
                          max_clip_duration: float = 60.0,
                          sensitivity: float = 1.0) -> Tuple[List[ViralSegment], np.ndarray, np.ndarray]:
    audio = AudioSegment.from_file(audio_path)
    audio = audio.set_channels(1).set_frame_rate(22050)
    samples = np.array(audio.get_array_of_samples()).astype(np.float32)
    sample_rate = 22050
    total_samples = len(samples)
    duration = total_samples / sample_rate

    if duration < 0.5:
        return [], np.array([]), np.array([])

    # Segment audio into small windows
    segment_duration = 0.05
    segment_samples = int(segment_duration * sample_rate)
    num_segments = max(1, total_samples // segment_samples)

    # Compute RMS energy per segment
    energy = np.zeros(num_segments)
    for i in range(num_segments):
        seg = samples[i*segment_samples:(i+1)*segment_samples]
        energy[i] = np.sqrt(np.mean(seg.astype(np.float64)**2))

    max_energy = np.max(energy)
    if max_energy > 0:
        energy_norm = energy / max_energy
    else:
        energy_norm = np.zeros_like(energy)

    # Smooth energy envelope
    window_size = max(1, int(0.3 / segment_duration))
    kernel = np.ones(window_size) / window_size
    energy_smooth = np.convolve(energy_norm, kernel, mode='same')

    # Compute spectral excitement (ratio of high-frequency energy)
    fft_result = np.abs(np.fft.rfft(samples))
    freqs = np.fft.rfftfreq(len(samples), 1/sample_rate)
    high_freq_mask = freqs > 2000
    mid_freq_mask = (freqs > 500) & (freqs <= 2000)

    high_energy = np.sum(fft_result[high_freq_mask]) if np.any(high_freq_mask) else 0
    mid_energy = np.sum(fft_result[mid_freq_mask]) if np.any(mid_freq_mask) else 0
    total_fft = np.sum(fft_result) + 1e-10

    # Compute per-segment excitement using FFT windows
    fft_window = int(1.0 / segment_duration)
    excitement = np.zeros(num_segments)
    for i in range(0, num_segments, fft_window):
        end = min(i + fft_window, num_segments)
        seg_start_sample = i * segment_samples
        seg_end_sample = min(end * segment_samples, total_samples)
        chunk = samples[seg_start_sample:seg_end_sample]
        if len(chunk) > 100:
            chunk_fft = np.abs(np.fft.rfft(chunk))
            chunk_freqs = np.fft.rfftfreq(len(chunk), 1/sample_rate)
            chunk_high = np.sum(chunk_fft[chunk_freqs > 2000]) if np.any(chunk_freqs > 2000) else 0
            chunk_total = np.sum(chunk_fft) + 1e-10
            excitement[i:end] = chunk_high / chunk_total

    # Combined viral score
    combined_score = (
        energy_weight * energy_smooth +
        excitement_weight * excitement
    )
    combined_score = combined_score / (np.max(combined_score) + 1e-10)

    # Adaptive threshold based on percentile
    # sensitivity: lower = more sensitive (lower threshold)
    percentile_base = max(10, min(90, 80 - (sensitivity - 1.0) * 30))
    threshold = np.percentile(combined_score, 100 - percentile_base)

    # Ensure minimum threshold for very quiet videos
    threshold = max(threshold, np.mean(combined_score) * 1.2)

    above_threshold = combined_score > threshold

    # Find continuous segments
    segments_raw = []
    in_segment = False
    seg_start = 0
    for i in range(len(above_threshold)):
        if above_threshold[i] and not in_segment:
            in_segment = True
            seg_start = i
        elif not above_threshold[i] and in_segment:
            in_segment = False
            seg_end = i
            dur = (seg_end - seg_start) * segment_duration
            if dur >= min_clip_duration:
                segments_raw.append((seg_start, seg_end))
    if in_segment:
        seg_end = len(above_threshold)
        dur = (seg_end - seg_start) * segment_duration
        if dur >= min_clip_duration:
            segments_raw.append((seg_start, seg_end))

    if not segments_raw:
        return [], combined_score, np.arange(len(combined_score)) * segment_duration

    # Convert to times and cap max duration
    merged = []
    for s, e in segments_raw:
        start_t = s * segment_duration
        end_t = e * segment_duration
        if end_t > video_duration:
            end_t = video_duration
        if end_t - start_t > max_clip_duration:
            mid = (start_t + end_t) / 2
            merged.append((max(0, mid - max_clip_duration/2),
                          min(video_duration, mid + max_clip_duration/2)))
        else:
            merged.append((start_t, end_t))

    # Merge nearby segments
    final_segments = []
    for s, e in merged:
        if final_segments and (s - final_segments[-1][1]) < 1.5:
            prev = final_segments.pop()
            final_segments.append((prev[0], max(prev[1], e)))
        else:
            final_segments.append((s, e))

    # Build results with scores and reasons
    results = []
    for s, e in final_segments:
        s_idx = int(s / segment_duration)
        e_idx = min(int(e / segment_duration), num_segments - 1)
        seg_scores = combined_score[s_idx:e_idx+1]
        score = float(np.mean(seg_scores)) if len(seg_scores) > 0 else 0.0

        peak = float(np.max(energy_smooth[s_idx:e_idx+1])) if len(seg_scores) > 0 else 0.0
        avg_excite = float(np.mean(excitement[s_idx:e_idx+1])) if len(seg_scores) > 0 else 0.0

        if peak > 0.7 and avg_excite > 0.3:
            reason = "Grito / explosao"
        elif peak > 0.5:
            reason = "Alta energia"
        elif avg_excite > 0.3:
            reason = "Agitacao / musica intensa"
        else:
            reason = "Momento de destaque"
        results.append(ViralSegment(start_sec=s, end_sec=e, score=score, reason=reason))

    results.sort(key=lambda x: x.score, reverse=True)
    time_axis = np.arange(len(combined_score)) * segment_duration

    return results, combined_score, time_axis


def detect_scene_changes(video_path: str, threshold: float = 30.0) -> List[float]:
    import subprocess
    cmd = [
        "ffmpeg", "-i", video_path,
        "-filter:v", f"select='gt(scene,{threshold/100})',showinfo",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    timestamps = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            for part in line.split():
                if part.startswith("pts_time:"):
                    try:
                        ts = float(part.split(":")[1])
                        timestamps.append(ts)
                    except:
                        pass
    return timestamps
