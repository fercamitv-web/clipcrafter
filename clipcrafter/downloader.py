import os
import re
import subprocess
import threading
from pathlib import Path
from queue import Queue

YOUTUBE_PATTERN = re.compile(
    r'(https?://)?(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com)/'
    r'(watch\?v=|embed/|v/|shorts/|live/|@[\w-]+/)?([\w-]{11})?'
)
TWITCH_PATTERN = re.compile(
    r'(https?://)?(www\.)?(twitch\.tv|clips\.twitch\.tv)/'
    r'([\w-]+)(/clip/[\w-]+|/video/[\d]+)?'
)
TWITCH_CLIP_PATTERN = re.compile(
    r'(https?://)?clips\.twitch\.tv/[\w-]+'
)

class DownloadListener:
    def on_progress(self, percent: float, speed: str = ""): pass
    def on_complete(self, path: str): pass
    def on_error(self, msg: str): pass
    def on_status(self, msg: str): pass

class VideoDownloader:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(os.path.expanduser("~"), "clipcrafter_downloads")
        os.makedirs(self.output_dir, exist_ok=True)
        self.cancelled = False
        self.listener = None

    def set_listener(self, listener: DownloadListener):
        self.listener = listener

    def cancel(self):
        self.cancelled = True

    def detect_platform(self, url: str) -> str:
        if YOUTUBE_PATTERN.match(url):
            return "youtube"
        if TWITCH_PATTERN.match(url) or TWITCH_CLIP_PATTERN.match(url):
            return "twitch"
        return "unknown"

    def download(self, url: str, quality: str = "best") -> str:
        self.cancelled = False

        platform = self.detect_platform(url)
        if platform == "unknown":
            if self.listener:
                self.listener.on_error("URL nao reconhecida. Use YouTube ou Twitch.")
            return None

        if self.listener:
            self.listener.on_status(f"Baixando video do {platform}...")

        output_template = os.path.join(self.output_dir, "%(title)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "-f", "best[height<=1080]",
            "-o", output_template,
            "--no-playlist",
            "--no-warnings",
            "--print", "after_move:filepath",
            "--progress-template", "%(progress._percent_str)s",
            url
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            output_path = None
            for line in process.stdout:
                line = line.strip()
                if self.cancelled:
                    process.terminate()
                    return None
                if os.path.exists(line):
                    output_path = line
                elif "%" in line:
                    try:
                        pct = float(line.strip("%").strip())
                        if self.listener:
                            self.listener.on_progress(pct)
                    except:
                        pass

            process.wait()

            if self.cancelled:
                return None

            if output_path and os.path.exists(output_path):
                if self.listener:
                    self.listener.on_complete(output_path)
                return output_path

            # Fallback: find the newest video file
            files = [f for f in os.listdir(self.output_dir)
                     if f.endswith(('.mp4', '.mkv', '.webm'))
                     and not f.startswith('._')]
            if files:
                newest = max(
                    [os.path.join(self.output_dir, f) for f in files],
                    key=os.path.getmtime
                )
                if self.listener:
                    self.listener.on_complete(newest)
                return newest

            if self.listener:
                self.listener.on_error("Nao foi possivel baixar o video")
            return None

        except Exception as e:
            if self.listener:
                self.listener.on_error(f"Erro no download: {str(e)}")
            return None

    def format_filename(self, path: str) -> str:
        return os.path.basename(path)
