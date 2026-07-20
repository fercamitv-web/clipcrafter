import os, json, subprocess, tempfile, struct, math, random
from pathlib import Path
from typing import List, Optional
from clip_analyzer import extract_features as _extract_features
from valorant_studio import ValorantStudio


HOOK_PHRASES = [
    "1v5?", "O QUE ACONTECEU?", "COMO ELE FEZ ISSO?",
    "ISSO FOI LOCO?", "MIRA PERFEITA?", "INACREDITAVEL",
    "ELE NAO PERDEU?", "QUE JOGADA", "ABCD?",
    "MOMENTO DE GENIO", "REACAO IMPOSSIVEL", "OLHA ISSO"
]

_valorant_studio = ValorantStudio()

GAMING_PHRASES = [
    "Olha isso!", "QUE JOGADA!", "INACREDITAVEL!",
    "MIRA PERFEITA!", "ELE SIMPLESMENTE...", "ISSO FOI ABSURDO!",
    "MOMENTO DE GENIO!", "JOGADOR DE OUTRO NIVEL!",
    "COMO ISSO ACERTOU?", "REACAO IMPOSSIVEL!",
    "ELE LEU PERFEITAMENTE!", "QUE TIRO!",
    "MIRA DE OUTRO MUNDO!", "ISSO NAO E NORMAL!",
    "HABILIDADE PURA!", "ELE E HUMANO?",
    "SENSACIONAL!", "IMPRESSIONANTE!",
    "ELE DOMINOU!", "QUE JOGADOR!"
]


def _pick_hook(score: float = 0.5, transcript: List[str] = None) -> str:
    if transcript:
        try:
            vs = _valorant_studio
            vs.analyze_transcript(transcript)
            return vs.generate_hook(style="auto")
        except Exception:
            pass
    idx = min(len(HOOK_PHRASES) - 1, int(score * len(HOOK_PHRASES)))
    return HOOK_PHRASES[idx]


def _pick_phrases(duration: float, count: int = None,
                  audio_path: str = None,
                  start_sec: float = None,
                  end_sec: float = None) -> List[str]:
    if count is None:
        count = max(1, min(6, int(duration // 4)))
    if audio_path and start_sec is not None and end_sec is not None:
        try:
            from speech_recognizer import transcribe_audio_segment
            phrases = transcribe_audio_segment(audio_path, start_sec, end_sec)
            phrases = [p.upper() for p in phrases if p]
            if phrases:
                return phrases[:count]
        except Exception:
            pass
    return random.sample(GAMING_PHRASES, min(count, len(GAMING_PHRASES)))


def _seconds_to_ass(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}".replace(".", ",")


def _generate_wav_beat(filepath: str, duration_sec: float, bpm: int = 140, sr: int = 44100):
    nsamples = int(sr * duration_sec)
    samples = [0.0] * nsamples
    spb = 60.0 / bpm * sr
    nbeats = int(duration_sec * bpm / 60)

    def add_sample(pos, val):
        i = int(pos)
        if 0 <= i < nsamples:
            samples[i] += val

    for b in range(nbeats):
        off = b * spb
        if b % 4 in (0, 2):
            for i in range(int(sr * 0.12)):
                t = i / sr
                add_sample(off + i, math.sin(2 * math.pi * 50 * t) * math.exp(-t * 25) * 0.6)
        if b % 4 in (1, 3):
            for i in range(int(sr * 0.08)):
                t = i / sr
                noise = (random.random() * 2 - 1) * math.exp(-t * 18) * 0.35
                tone = math.sin(2 * math.pi * 180 * t) * math.exp(-t * 20) * 0.15
                add_sample(off + i, noise + tone)
        for sub in (0, 0.5):
            hoff = off + sub * spb
            for i in range(int(sr * 0.025)):
                t = i / sr
                add_sample(hoff + i, math.sin(2 * math.pi * 900 * t) * math.exp(-t * 60) * 0.08)

    peak = max(abs(s) for s in samples) or 1
    samples = [s / peak * 0.6 for s in samples]
    with open(filepath, "wb") as f:
        f.write(struct.pack("<4sI4s", b"RIFF", 36 + nsamples * 2, b"WAVE"))
        f.write(struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, sr, sr * 2, 2, 16))
        f.write(struct.pack("<4sI", b"data", nsamples * 2))
        for s in samples:
            f.write(struct.pack("<h", max(-32768, min(32767, int(s * 32767)))))


def _generate_wav_impact(filepath: str, sr: int = 44100):
    nsamples = int(sr * 0.5)
    samples = [0.0] * nsamples
    for i in range(nsamples):
        t = i / sr
        freq = 80 - t * 100
        tone = math.sin(2 * math.pi * freq * t) * math.exp(-t * 6) * 0.5
        noise = (random.random() * 2 - 1) * math.exp(-t * 5) * 0.2
        samples[i] = tone + noise
    peak = max(abs(s) for s in samples) or 1
    samples = [s / peak * 0.8 for s in samples]
    with open(filepath, "wb") as f:
        f.write(struct.pack("<4sI4s", b"RIFF", 36 + nsamples * 2, b"WAVE"))
        f.write(struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, sr, sr * 2, 2, 16))
        f.write(struct.pack("<4sI", b"data", nsamples * 2))
        for s in samples:
            f.write(struct.pack("<h", max(-32768, min(32767, int(s * 32767)))))


def _generate_wav_whooshes(filepath: str, duration: float, num_hits: int, sr: int = 44100):
    nsamples = int(sr * duration)
    samples = [0.0] * nsamples
    spacing = duration / max(1, num_hits + 1)
    for w in range(num_hits):
        t_offset = spacing * (w + 1)
        if t_offset < 0.2 or t_offset > duration - 0.2:
            continue
        offset_sample = int(t_offset * sr)
        whoosh_len = min(int(sr * 0.25), nsamples - offset_sample)
        for i in range(whoosh_len):
            t = i / sr
            freq = 200 + t * 6000
            tone = math.sin(2 * math.pi * freq * t) * math.exp(-t * 5) * 0.12
            noise = (random.random() * 2 - 1) * math.exp(-t * 4) * 0.08
            samples[offset_sample + i] += tone + noise
    peak = max(abs(s) for s in samples) or 1
    samples = [s / peak * 0.5 for s in samples]
    with open(filepath, "wb") as f:
        f.write(struct.pack("<4sI4s", b"RIFF", 36 + nsamples * 2, b"WAVE"))
        f.write(struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, sr, sr * 2, 2, 16))
        f.write(struct.pack("<4sI", b"data", nsamples * 2))
        for s in samples:
            f.write(struct.pack("<h", max(-32768, min(32767, int(s * 32767)))))


def _generate_ass_subtitle(filepath: str, duration: float, phrases: List[str],
                           video_w: int = 1080, video_h: int = 1920):
    if not phrases:
        return
    ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,52,&H00FFFFFF,&H00FFD700,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,20,20,80,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".format(w=video_w, h=video_h)

    phrase_dur = duration / len(phrases)
    for i, phrase in enumerate(phrases):
        start_t = i * phrase_dur
        end_t = (i + 1) * phrase_dur
        words = phrase.split()
        word_dur_cs = max(10, int((end_t - start_t) / len(words) * 100))
        karaoke = "".join(f"{{\\k{word_dur_cs}}}{w} " for w in words).strip()
        ass_content += (f"Dialogue: 0,{_seconds_to_ass(start_t)},"
                        f"{_seconds_to_ass(end_t)},Caption,,0,0,0,,{karaoke}\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(ass_content)


class VideoProcessor:
    def __init__(self):
        self.video_path = None
        self.duration = 0
        self.fps = 30
        self.width = 0
        self.height = 0
        self.audio_path = None
        self.temp_dir = None

    def load(self, video_path: str) -> bool:
        if not os.path.exists(video_path):
            return False
        try:
            from moviepy.video.io.VideoFileClip import VideoFileClip
            clip = VideoFileClip(video_path)
            self.duration = clip.duration
            self.fps = clip.fps
            self.width = clip.size[0]
            self.height = clip.size[1]
            clip.close()

            self.video_path = video_path
            self.temp_dir = tempfile.mkdtemp(prefix="clipcrafter_")

            self.audio_path = os.path.join(self.temp_dir, "audio.wav")
            cmd = [
                "ffmpeg", "-i", video_path,
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "22050", "-ac", "1",
                "-y", self.audio_path
            ]
            subprocess.run(cmd, capture_output=True, text=True)
            return os.path.exists(self.audio_path)
        except Exception as e:
            print(f"Error loading video: {e}")
            return False

    def export_clip(self, start_sec: float, end_sec: float,
                    output_path: str,
                    add_watermark: bool = True,
                    watermark_text: str = "@CanalPropra",
                    watermark_position: str = "bottom-left",
                    add_progress_bar: bool = False,
                    add_countdown: bool = False,
                    add_highlight: bool = False,
                    shorts_mode: bool = False,
                    viral_audio: bool = False,
                    add_subtitles: bool = False,
                     hook_text: str = None,
                     loop_mode: bool = False,
                     gameplay_text: str = None) -> bool:
        try:
            output_path = Path(output_path).with_suffix(".mp4")
            output = str(output_path)
            duration = end_sec - start_sec

            font_path = "C\\:/Windows/Fonts/arial.ttf"
            if not os.path.exists(font_path.replace("\\:", ":")):
                font_path = ""
            fp = f":fontfile='{font_path}'" if font_path else ""

            if shorts_mode:
                # Transcribe audio first for smarter hook and subtitle generation
                transcript_phrases = None
                if add_subtitles and self.audio_path and duration > 3:
                    transcript_phrases = _pick_phrases(
                        duration, audio_path=self.audio_path,
                        start_sec=start_sec, end_sec=end_sec)

                if hook_text is None:
                    hook_text = _pick_hook(0.7, transcript=transcript_phrases)
                # Always run analysis for title generation (even with custom hook)
                self._analysis = _valorant_studio.analysis if transcript_phrases else None
                target_w, target_h = 1080, 1920
                # Punch zoom: fast zoom-in at start that decelerates smoothly
                zoom_expr = "min(1 + 0.4/(1+t*3) + 0.0001*t, 1.15)"
                parts = [
                    f"[0:v]zoompan=z='{zoom_expr}':d=1:fps=30[z]",
                    f"[z]scale={target_w}:{target_h}:"
                    f"force_original_aspect_ratio=increase,"
                    f"crop={target_w}:{target_h},boxblur=20:5[bg]",
                    f"[z]scale={target_w}:{target_h}:"
                    f"force_original_aspect_ratio=decrease,setsar=1[fg]",
                    "[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
                ]

                # Hook de curiosidade nos primeiros 2.5s — larger, bolder, with animated scale feel
                if duration > 3:
                    # Main hook text — large, centered, with thick border
                    parts.append(
                        f"[base]drawtext=text='{hook_text}':"
                        f"fontcolor=#FF4500:fontsize=64:box=1:boxcolor=black@0.85:"
                        f"x=(w-text_w)/2:y=(h-text_h)/2-40{fp}:"
                        f"borderw=3:bordercolor=black@0.6:"
                        f"enable='lt(t,2.5)'[base]"
                    )
                    # Subtitle "CANALPROPA" below hook
                    parts.append(
                        f"[base]drawtext=text='@CanalPropra':"
                        f"fontcolor=white:fontsize=32:box=1:boxcolor=black@0.6:"
                        f"x=(w-text_w)/2:y=(h+text_h)/2+10{fp}:"
                        f"enable='lt(t,2.5)'[base]"
                    )

                # Word-by-word subtitles via ASS karaoke
                if add_subtitles and duration > 3:
                    ass_path = os.path.join(self.temp_dir, "captions.ass")
                    phrases = transcript_phrases or _pick_phrases(
                        duration, audio_path=self.audio_path,
                        start_sec=start_sec, end_sec=end_sec)
                    _generate_ass_subtitle(ass_path, duration, phrases,
                                           target_w, target_h)
                    rel_path = os.path.relpath(ass_path).replace("\\", "/")
                    parts.append(f"[base]ass={rel_path}:original_size={target_w}x{target_h}[base]")

                if add_watermark:
                    if watermark_position == "bottom-left":
                        x, y = "10", "h-th-10"
                    elif watermark_position == "bottom-right":
                        x, y = "w-tw-10", "h-th-10"
                    elif watermark_position == "top-left":
                        x, y = "10", "10"
                    elif watermark_position == "top-right":
                        x, y = "w-tw-10", "10"
                    else:
                        x, y = "(w-tw)/2", "(h-th)/2"
                    parts.append(
                        f"[base]drawtext=text='{watermark_text}':"
                        f"fontcolor=white:fontsize=32:box=1:boxcolor=black@0.55:"
                        f"x={x}:y={y}{fp}[base]"
                    )

                if add_progress_bar:
                    bar_h = 6
                    parts.append(
                        f"[base]drawbox=x=0:y=ih-{bar_h}:w=iw:h={bar_h}:"
                        f"c=red@0.7:t=fill[base]"
                    )
                    expr = f'iw*min(1\\,max(0\\,t/{duration}))'
                    parts.append(
                        f"[base]drawbox=x=0:y=ih-{bar_h}:"
                        f"w='{expr}':h={bar_h}:"
                        f"c=yellow@0.9:t=fill[base]"
                    )

                if add_countdown and duration > 1:
                    parts.append(
                        f"[base]drawtext=text='ACABANDO':"
                        f"fontcolor=yellow:fontsize=48:box=1:boxcolor=black@0.6:"
                        f"x=(w-text_w)/2:y=16{fp}:"
                        f"enable='gte(t,{max(0,duration-5)})*lte(t,{duration})'[base]"
                    )

                if gameplay_text and duration > 3:
                    parts.append(
                        f"[base]drawtext=text='{gameplay_text}':"
                        f"fontcolor=white:fontsize=52:box=1:boxcolor=black@0.6:"
                        f"x=(w-text_w)/2:y=(h-th)/2-60{fp}:"
                        f"enable='gte(t,{duration-3})*lt(t,{duration})'[base]"
                    )

                if duration > 4:
                    parts.append(
                        f"[base]drawtext=text='INSCREVA-SE\\n@CanalPropra':"
                        f"fontcolor=yellow:fontsize=48:box=1:boxcolor=black@0.75:"
                        f"x=(w-text_w)/2:y=h-200{fp}:"
                        f"enable='gte(t,{max(0,duration-4)})'[base]"
                    )

                if add_highlight and duration > 2:
                    parts.append(
                        f"[base]drawbox=x=0:y=0:w=iw:h=ih:"
                        f"color=white@0.08:t=fill:"
                        f"enable='lt(mod(t+0.5,1),0.12)'[base]"
                    )

                extra_inputs = []
                audio_label = "0:a"

                if viral_audio and self.temp_dir:
                    beat_path = os.path.join(self.temp_dir, "viral_beat.wav")
                    impact_path = os.path.join(self.temp_dir, "viral_impact.wav")
                    whoosh_path = os.path.join(self.temp_dir, "viral_whooshes.wav")
                    num_whooshes = max(1, int(duration // 3) - 1)
                    _generate_wav_beat(beat_path, duration)
                    _generate_wav_impact(impact_path)
                    _generate_wav_whooshes(whoosh_path, duration, num_whooshes)
                    extra_inputs = [beat_path, impact_path, whoosh_path]

                    parts.append("[0:a]asplit=2[orig][side]")
                    parts.append(
                        f"[1:a]adelay=0|0,aloop=loop=-1:size=1,"
                        f"atrim=duration={duration}[beat]"
                    )
                    parts.append(
                        "[beat][side]sidechaincompress="
                        "threshold=0.1:ratio=8:attack=5:release=200[beat_d]"
                    )
                    parts.append(
                        "[orig][beat_d]amix=inputs=2:duration=first:"
                        "weights=1 0.35[audio1]"
                    )
                    # Impact at frame 0 (adelay=0 instead of 800)
                    parts.append(
                        "[2:a]adelay=0|0,volume=0.6[impact]"
                    )
                    parts.append(
                        "[audio1][impact]amix=inputs=2:duration=first:"
                        "weights=1 0.7[audio2]"
                    )
                    # Whooshes mixed in
                    parts.append(
                        "[3:a]volume=0.5[whooshes]"
                    )
                    parts.append(
                        "[audio2][whooshes]amix=inputs=2:duration=first:"
                        "weights=1 0.5[audio3]"
                    )
                    parts.append(
                        "[audio3]aecho=0.6:0.4:40:0.3[a_out]"
                    )
                    audio_label = "[a_out]"

                filter_complex = ";".join(parts)
                cmd = [
                    "ffmpeg", "-ss", str(start_sec), "-i", self.video_path,
                ]
                for inp in extra_inputs:
                    cmd.extend(["-i", inp])
                cmd.extend([
                    "-t", str(duration),
                    "-filter_complex", filter_complex,
                    "-map", "[base]", "-map", audio_label,
                    "-c:v", "libx264", "-preset", "fast",
                    "-c:a", "aac", "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    "-y", output
                ])
            else:
                filter_parts = []

                if gameplay_text:
                    filter_parts.append(
                        f"drawtext=text='{gameplay_text}':"
                        f"fontcolor=white:fontsize=40:box=1:boxcolor=black@0.6:"
                        f"x=(w-text_w)/2:y=40{fp}:"
                        f"enable='lt(t,{min(4,duration/3)})'"
                    )
                    filter_parts.append(
                        f"drawtext=text='{gameplay_text}':"
                        f"fontcolor=white:fontsize=40:box=1:boxcolor=black@0.6:"
                        f"x=(w-text_w)/2:y=(h-th)/2-40{fp}:"
                        f"enable='gte(t,{duration-4})*lt(t,{duration})'"
                    )

                if add_watermark:
                    if watermark_position == "bottom-left":
                        x, y = "10", "h-th-10"
                    elif watermark_position == "bottom-right":
                        x, y = "w-tw-10", "h-th-10"
                    elif watermark_position == "top-left":
                        x, y = "10", "10"
                    elif watermark_position == "top-right":
                        x, y = "w-tw-10", "10"
                    else:
                        x, y = "(w-tw)/2", "(h-th)/2"
                    filter_parts.append(
                        f"drawtext=text='{watermark_text}':"
                        f"fontcolor=white:fontsize=20:box=1:boxcolor=black@0.5:"
                        f"x={x}:y={y}{fp}"
                    )

                if add_progress_bar:
                    bar_h = 4
                    filter_parts.append(
                        f"drawbox=x=0:y=ih-{bar_h}:w=iw:h={bar_h}:"
                        f"c=red@0.7:t=fill"
                    )
                    expr = f'iw*min(1\\,max(0\\,t/{duration}))'
                    filter_parts.append(
                        f"drawbox=x=0:y=ih-{bar_h}:"
                        f"w='{expr}':h={bar_h}:"
                        f"c=yellow@0.9:t=fill"
                    )

                if add_countdown and duration > 1:
                    filter_parts.append(
                        "drawtext=text='ACABANDO':"
                        "fontcolor=yellow:fontsize=36:box=1:boxcolor=black@0.6:"
                        f"x=(w-text_w)/2:y=8{fp}:"
                        f"enable='gte(t,{max(0,duration-5)})*lte(t,{duration})'"
                    )

                if add_highlight and duration > 2:
                    filter_parts.append(
                        f"drawbox=x=0:y=0:w=iw:h=ih:"
                        f"color=white@0.06:t=fill:"
                        f"enable='lt(mod(t+0.5,1),0.12)'"
                    )

                cmd = [
                    "ffmpeg", "-ss", str(start_sec), "-i", self.video_path,
                    "-t", str(duration),
                    "-c:v", "libx264", "-preset", "fast",
                    "-c:a", "aac", "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                ]

                if filter_parts:
                    cmd.extend(["-vf", ",".join(filter_parts)])

                cmd.extend(["-y", output])

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                err_lines = result.stderr.split('\n')
                for ln in err_lines:
                    if 'Error' in ln or 'error' in ln:
                        print("FF:", ln.strip())

            if os.path.exists(output) and loop_mode:
                loop_output = output_path.parent / f"{output_path.stem}_loop.mp4"
                ok = self._apply_seamless_loop(str(output), str(loop_output))
                if ok:
                    os.replace(str(loop_output), output)

            if os.path.exists(output) and self.audio_path:
                try:
                    feat = _extract_features(self.audio_path, duration)
                    feat_db = os.path.expanduser("~/.clipcrafter/clip_features.json")
                    all_feat = {}
                    if os.path.exists(feat_db):
                        try:
                            with open(feat_db) as _f:
                                all_feat = json.load(_f)
                        except:
                            all_feat = {}
                    all_feat[output_path.stem] = feat
                    os.makedirs(os.path.dirname(feat_db), exist_ok=True)
                    with open(feat_db, "w") as _f:
                        json.dump(all_feat, _f, indent=2)
                except Exception:
                    pass

            return os.path.exists(output)
        except Exception as e:
            print(f"Export error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _apply_seamless_loop(self, input_path: str, output_path: str,
                             fade_duration: float = 0.4) -> bool:
        import json
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_entries", "format=duration", input_path],
            capture_output=True, text=True
        )
        try:
            info = json.loads(probe.stdout)
            total_dur = float(info["format"]["duration"])
        except:
            return False

        f = fade_duration
        if total_dur <= f * 3:
            return False

        cmd = [
            "ffmpeg", "-i", input_path,
            "-filter_complex",
            f"[0:v]split=3[v1][v2][v3];"
            f"[v1]trim=0:{total_dur-f},setpts=PTS-STARTPTS[v_main];"
            f"[v2]trim={total_dur-f}:{total_dur},setpts=PTS-STARTPTS[v_end];"
            f"[v3]trim=0:{f},setpts=PTS-STARTPTS[v_start];"
            f"[v_end][v_start]xfade=transition=fade:duration={f}:offset=0[v_blend];"
            f"[v_main][v_blend]concat=n=2[v_out];"
            f"[0:a]asplit=3[a1][a2][a3];"
            f"[a1]atrim=0:{total_dur-f},asetpts=PTS-STARTPTS[a_main];"
            f"[a2]atrim={total_dur-f}:{total_dur},asetpts=PTS-STARTPTS[a_end];"
            f"[a3]atrim=0:{f},asetpts=PTS-STARTPTS[a_start];"
            f"[a_end][a_start]acrossfade=d={f}[a_blend];"
            f"[a_main][a_blend]concat=n=2:v=0:a=1[a_out]",
            "-map", "[v_out]", "-map", "[a_out]",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-y", output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return os.path.exists(output_path)

    def get_frame_at(self, time_sec: float, output_path: str) -> str:
        cmd = [
            "ffmpeg", "-ss", str(time_sec), "-i", self.video_path,
            "-vframes", "1", "-q:v", "2",
            "-y", output_path
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        return output_path if os.path.exists(output_path) else None

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
