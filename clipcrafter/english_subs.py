"""Second subtitle line in English (burned-in) for Shorts.

Uses whisper multilingual with task=translate (PT speech -> EN text) and
burns a smaller EN line BELOW the PT karaoke via libass (real segment
timings, not evenly-split).
"""
import os
import re
import subprocess
import tempfile

import imageio_ffmpeg

EXE = imageio_ffmpeg.get_ffmpeg_exe()

_model = None


def _load_model():
    global _model
    if _model is None:
        import whisper
        _model = whisper.load_model("tiny")
    return _model


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def translate_segments(mp4_path: str):
    """Returns [(start, end, en_text)] via whisper translate. Empty if no speech."""
    wav = os.path.join(tempfile.gettempdir(), "en_sub.wav")
    subprocess.run([EXE, "-v", "error", "-y", "-i", mp4_path,
                    "-ar", "16000", "-ac", "1", wav], check=True)
    try:
        model = _load_model()
        res = model.transcribe(wav, task="translate", language="pt",
                               fp16=False, condition_on_previous_text=False)
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass
    out = []
    for seg in res.get("segments", []):
        txt = _ass_escape(seg.get("text", ""))
        if txt:
            out.append((float(seg["start"]), float(seg["end"]), txt))
    return out


def _build_ass(segs, duration: float) -> str:
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EN,Arial,34,&H0000E6FF,&H00000000,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,40,40,24,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [head]
    for s, e, t in segs:
        e = min(e, duration)
        if e - s < 0.2:
            continue
        lines.append(f"Dialogue: 0,{_ass_time(s)},{_ass_time(e)},EN,,0,0,0,,{t}\n")
    return "".join(lines)


def add_english_subs(src_mp4: str, dst_mp4: str = None, preset: str = "fast") -> bool:
    """Burn EN subtitle line. Returns True if subs added, False if no speech."""
    import re as _re
    probe = subprocess.run([EXE, "-i", src_mp4], capture_output=True, text=True)
    duration = 0.0
    m = _re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe.stderr or "")
    if m:
        duration = (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)))
    if duration <= 0:
        return False
    segs = translate_segments(src_mp4)
    if not segs:
        return False
    ass = os.path.join(tempfile.gettempdir(), "en_captions.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(_build_ass(segs, duration))
    out = dst_mp4 or src_mp4
    tmp = out + ".en.mp4"
    rel = os.path.relpath(ass).replace("\\", "/")
    r = subprocess.run(
        [EXE, "-v", "error", "-y", "-i", src_mp4,
         "-vf", f"ass={rel}:original_size=1080x1920",
         "-c:v", "libx264", "-preset", preset, "-crf", "18",
         "-c:a", "copy", tmp],
        capture_output=True, text=True)
    try:
        os.remove(ass)
    except OSError:
        pass
    if r.returncode != 0 or not os.path.exists(tmp):
        raise RuntimeError(f"ffmpeg EN burn failed: {(r.stderr or '')[-300:]}")
    os.replace(tmp, out)
    return True


if __name__ == "__main__":
    import sys
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    print("EN subs added:", add_english_subs(src, dst))
