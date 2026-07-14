import os
import whisper
from typing import List


_model = None


def _load_model():
    global _model
    if _model is None:
        _model = whisper.load_model("tiny.en")
    return _model


def transcribe(audio_path: str, language: str = "en") -> List[str]:
    if not os.path.exists(audio_path):
        return []

    model = _load_model()
    result = model.transcribe(audio_path, language=language, word_timestamps=True)

    segments = result.get("segments", [])
    if not segments:
        return []

    phrases = []
    for seg in segments:
        text = seg.get("text", "").strip()
        if text:
            phrases.append(text)

    return phrases


def transcribe_audio_segment(audio_path: str, start_sec: float, end_sec: float,
                             language: str = "en") -> List[str]:
    import subprocess, tempfile, math

    model = _load_model()
    sr = 16000

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    subprocess.run([
        "ffmpeg", "-y", "-i", audio_path,
        "-ss", str(start_sec), "-to", str(end_sec),
        "-ar", str(sr), "-ac", "1",
        tmp_path
    ], capture_output=True)

    result = model.transcribe(tmp_path, language=language, word_timestamps=True)
    os.unlink(tmp_path)

    segments = result.get("segments", [])
    return [s["text"].strip() for s in segments if s.get("text", "").strip()]
