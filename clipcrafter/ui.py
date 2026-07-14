import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np

from viral_detector import detect_viral_moments, ViralSegment
from video_processor import VideoProcessor, _pick_hook, HOOK_PHRASES
from downloader import VideoDownloader, DownloadListener
from youtube_uploader import upload_video, has_credentials, set_credentials_from_path, generate_credentials_guide

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CANVAS_H = 160
TIMELINE_PAD = 60


class ClipCrafterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ClipCrafter - Cortador de Clipes Virais")
        self.geometry("1100x800")
        self.minsize(900, 700)

        self.processor = VideoProcessor()
        self.downloader = VideoDownloader()
        self.viral_segments: list[ViralSegment] = []
        self.score_data = None
        self.time_axis = None
        self.video_duration = 0
        self.file_loaded = False
        self.analyzing = False
        self.downloading = False

        self.selected_start = 0.0
        self.selected_end = 0.0

        self.dragging = None
        self.thumbnails = []

        self.sensitivity_var = ctk.DoubleVar(value=1.0)
        self.min_clip_var = ctk.DoubleVar(value=5.0)
        self.max_clip_var = ctk.DoubleVar(value=60.0)
        self.watermark_var = ctk.BooleanVar(value=True)
        self.watermark_pos_var = ctk.StringVar(value="bottom-left")
        self.progress_bar_var = ctk.BooleanVar(value=True)
        self.countdown_var = ctk.BooleanVar(value=True)
        self.highlight_var = ctk.BooleanVar(value=True)
        self.last_exported_path = None
        self.game_name_var = ctk.StringVar(value="Valorant")
        self.subtitles_var = ctk.BooleanVar(value=True)
        self.loop_var = ctk.BooleanVar(value=True)

        self._build_ui()
        self.downloader.set_listener(self._make_download_listener())

    def _make_download_listener(self):
        class Listener(DownloadListener):
            def __init__(self, app):
                self.app = app
            def on_progress(self, percent, speed=""):
                self.app.after(0, lambda: self.app._on_dl_progress(percent))
            def on_complete(self, path):
                self.app.after(0, lambda: self.app._on_dl_complete(path))
            def on_error(self, msg):
                self.app.after(0, lambda: self.app._on_dl_error(msg))
            def on_status(self, msg):
                self.app.after(0, lambda: self.app.set_status(msg))
        return Listener(self)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="ClipCrafter",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text="Corte os melhores momentos das suas lives com deteccao viral automatica",
                     font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w")

        # Main
        main = ctk.CTkFrame(self)
        main.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(5, weight=1)

        # URL input row
        url_frame = ctk.CTkFrame(main, fg_color="transparent")
        url_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        url_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(url_frame, text="Link do video:",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, padx=(0, 5))
        self.url_entry = ctk.CTkEntry(url_frame, placeholder_text="https://youtube.com/... ou https://twitch.tv/...",
                                       font=ctk.CTkFont(size=13))
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))

        self.btn_download = ctk.CTkButton(url_frame, text="Baixar Video",
                                           command=self.download_video, width=120, height=35,
                                           font=ctk.CTkFont(size=13, weight="bold"))
        self.btn_download.grid(row=0, column=2, padx=(0, 5))

        self.dl_progress = ctk.CTkProgressBar(url_frame, width=120)
        self.dl_progress.grid(row=0, column=3)
        self.dl_progress.set(0)
        self.dl_progress.grid_remove()

        # File row
        file_frame = ctk.CTkFrame(main, fg_color="transparent")
        file_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        file_frame.grid_columnconfigure(1, weight=1)

        self.btn_open = ctk.CTkButton(file_frame, text="Abrir Video Local", command=self.open_video,
                                       width=140, height=38, font=ctk.CTkFont(size=14, weight="bold"))
        self.btn_open.grid(row=0, column=0, padx=(0, 10))

        self.btn_yt_config = ctk.CTkButton(file_frame, text="YT Config", command=self.setup_youtube_credentials,
                                            width=80, height=30, font=ctk.CTkFont(size=11))
        self.btn_yt_config.grid(row=0, column=1, padx=(0, 5))

        self.file_label = ctk.CTkLabel(file_frame, text="Nenhum video carregado", anchor="w",
                                        font=ctk.CTkFont(size=13))
        self.file_label.grid(row=0, column=2, sticky="ew")

        # Fix the column configure
        file_frame.grid_columnconfigure(2, weight=1)

        self.btn_analyze = ctk.CTkButton(file_frame, text="Analisar Momentos Virais",
                                          command=self.analyze_video,
                                          width=200, height=38, state="disabled",
                                          font=ctk.CTkFont(size=14, weight="bold"))
        self.btn_analyze.grid(row=0, column=2, padx=10)

        self.analyze_progress = ctk.CTkProgressBar(file_frame, width=150, mode="indeterminate")
        self.analyze_progress.grid(row=0, column=3, padx=(0, 10))
        self.analyze_progress.grid_remove()

        # Timeline
        self.timeline_frame = ctk.CTkFrame(main, height=CANVAS_H + 40)
        self.timeline_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.timeline_frame.grid_columnconfigure(0, weight=1)
        self.timeline_frame.grid_propagate(False)

        self.canvas = tk.Canvas(self.timeline_frame, height=CANVAS_H + 10, bg="#1a1a2e",
                                highlightthickness=0)
        self.canvas.pack(fill="x", padx=10, pady=(10, 0))
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # Info bar
        info_frame = ctk.CTkFrame(main, fg_color="transparent")
        info_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        info_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.lbl_duration = ctk.CTkLabel(info_frame, text="Duracao: --", font=ctk.CTkFont(size=12))
        self.lbl_duration.grid(row=0, column=0, sticky="w")
        self.lbl_segments = ctk.CTkLabel(info_frame, text="Clipes virais: --", font=ctk.CTkFont(size=12))
        self.lbl_segments.grid(row=0, column=1, sticky="w")
        self.lbl_selection = ctk.CTkLabel(info_frame, text="Selecao: --", font=ctk.CTkFont(size=12))
        self.lbl_selection.grid(row=0, column=2, sticky="w")
        self.lbl_status = ctk.CTkLabel(info_frame, text="Pronto", font=ctk.CTkFont(size=12))
        self.lbl_status.grid(row=0, column=3, sticky="e")

        # Controls
        controls = ctk.CTkFrame(main, fg_color="transparent")
        controls.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        controls.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(controls, text="Sensibilidade:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=5)
        ctk.CTkSlider(controls, from_=0.3, to=2.0, variable=self.sensitivity_var,
                       width=120).grid(row=0, column=1, padx=5)
        self.lbl_sens = ctk.CTkLabel(controls, text="1.0x", font=ctk.CTkFont(size=12))
        self.lbl_sens.grid(row=0, column=2, padx=5, sticky="w")

        self.btn_select_first = ctk.CTkButton(controls, text="Selecionar Top", width=130,
                                                command=self.select_top_segment, state="disabled")
        self.btn_select_first.grid(row=0, column=3, padx=5)
        self.btn_export = ctk.CTkButton(controls, text="Exportar Clipe", width=130,
                                         command=self.export_clip, state="disabled",
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         fg_color="#2d7a3e", hover_color="#1f5c2e")
        self.btn_export.grid(row=0, column=4, padx=5)

        self.btn_upload = ctk.CTkButton(controls, text="Postar no YouTube", width=150,
                                         command=self.upload_to_youtube, state="disabled",
                                         font=ctk.CTkFont(size=13, weight="bold"),
                                         fg_color="#cc0000", hover_color="#990000")
        self.btn_upload.grid(row=0, column=5, padx=5)

        self.upload_progress = ctk.CTkProgressBar(controls, width=100)
        self.upload_progress.grid(row=0, column=6)
        self.upload_progress.grid_remove()

        # Bottom panels
        opts_frame = ctk.CTkFrame(main)
        opts_frame.grid(row=5, column=0, sticky="nsew")
        opts_frame.grid_columnconfigure(1, weight=1)

        self.seg_list_frame = ctk.CTkScrollableFrame(opts_frame, width=350)
        self.seg_list_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        ctk.CTkLabel(self.seg_list_frame, text="Clipes Virais Detectados",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(5, 10))
        self.seg_list_inner = ctk.CTkFrame(self.seg_list_frame, fg_color="transparent")
        self.seg_list_inner.pack(fill="x", padx=5)

        right_panel = ctk.CTkFrame(opts_frame, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)

        clip_opts = ctk.CTkFrame(right_panel)
        clip_opts.pack(fill="x", pady=(0, 10))
        clip_opts.grid_columnconfigure(1, weight=1)

        ro = 0
        ctk.CTkLabel(clip_opts, text="Duracao min (s):", font=ctk.CTkFont(size=12)).grid(row=ro, column=0, sticky="w", padx=5)
        ctk.CTkEntry(clip_opts, textvariable=self.min_clip_var, width=60).grid(row=ro, column=1, sticky="w", padx=5)
        ro += 1
        ctk.CTkLabel(clip_opts, text="Duracao max (s):", font=ctk.CTkFont(size=12)).grid(row=ro, column=0, sticky="w", padx=5)
        ctk.CTkEntry(clip_opts, textvariable=self.max_clip_var, width=60).grid(row=ro, column=1, sticky="w", padx=5)
        ro += 1

        ctk.CTkCheckBox(clip_opts, text="Marca dagua (@CanalPropra)",
                         variable=self.watermark_var).grid(row=ro, column=0, columnspan=2, sticky="w", padx=5, pady=1)
        ro += 1
        pos_frame = ctk.CTkFrame(clip_opts, fg_color="transparent")
        pos_frame.grid(row=ro, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 3))
        ctk.CTkLabel(pos_frame, text="Pos:", font=ctk.CTkFont(size=11)).pack(side="left")
        for p, lbl in [("bottom-left", "Inf.Esq"), ("bottom-right", "Inf.Dir"),
                        ("top-left", "Sup.Esq"), ("center", "Centro")]:
            ctk.CTkRadioButton(pos_frame, text=lbl, variable=self.watermark_pos_var,
                               value=p, font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
        ro += 1
        ctk.CTkCheckBox(clip_opts, text="Barra de progresso",
                         variable=self.progress_bar_var).grid(row=ro, column=0, columnspan=2, sticky="w", padx=5, pady=1)
        ro += 1
        ctk.CTkCheckBox(clip_opts, text="Contagem regressiva (ultimos 5s)",
                         variable=self.countdown_var).grid(row=ro, column=0, columnspan=2, sticky="w", padx=5, pady=1)
        ro += 1
        ctk.CTkCheckBox(clip_opts, text="Destaque pulsante",
                         variable=self.highlight_var).grid(row=ro, column=0, columnspan=2, sticky="w", padx=5, pady=1)
        ro += 1
        ctk.CTkCheckBox(clip_opts, text="Legendas word-by-word (karaoke)",
                         variable=self.subtitles_var,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#00BFFF").grid(row=ro, column=0, columnspan=2, sticky="w", padx=5, pady=1)
        ro += 1
        ctk.CTkCheckBox(clip_opts, text="Loop seamless (fim->inicio)",
                         variable=self.loop_var,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#32CD32").grid(row=ro, column=0, columnspan=2, sticky="w", padx=5, pady=1)
        ro += 1
        ctk.CTkLabel(clip_opts, text="Jogo:", font=ctk.CTkFont(size=12)).grid(row=ro, column=0, sticky="w", padx=5)
        ctk.CTkEntry(clip_opts, textvariable=self.game_name_var, width=120).grid(row=ro, column=1, sticky="w", padx=5)
        ro += 1
        self.shorts_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(clip_opts, text="Modo Shorts (9:16 vertical)",
                         variable=self.shorts_var,
                         font=ctk.CTkFont(size=12, weight="bold")).grid(row=ro, column=0, columnspan=2, sticky="w", padx=5, pady=1)
        ro += 1
        self.viral_audio_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(clip_opts, text="Audio viral (beat + ducking + reverb)",
                         variable=self.viral_audio_var,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#FF6B35").grid(row=ro, column=0, columnspan=2, sticky="w", padx=5, pady=1)

        preview_frame = ctk.CTkFrame(right_panel)
        preview_frame.pack(fill="both", expand=True)
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(preview_frame, text="Preview do Clipe",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.preview_label = ctk.CTkLabel(preview_frame, text="Selecione um clipe para preview\nou clique no timeline",
                                           font=ctk.CTkFont(size=13))
        self.preview_label.grid(row=1, column=0, sticky="nsew", pady=10)

    # ---- download ----
    def download_video(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Atencao", "Cole um link do YouTube ou Twitch primeiro.")
            return
        if self.downloading:
            return

        self.downloading = True
        self.btn_download.configure(state="disabled", text="Baixando...")
        self.dl_progress.grid()
        self.dl_progress.set(0)
        self.set_status("Iniciando download...")

        def task():
            path = self.downloader.download(url)
            if not path:
                self.after(0, lambda: self._on_dl_error("Falha no download"))
        threading.Thread(target=task, daemon=True).start()

    def _on_dl_progress(self, percent):
        self.dl_progress.set(percent / 100)

    def _on_dl_complete(self, path):
        self.downloading = False
        self.btn_download.configure(state="normal", text="Baixar Video")
        self.dl_progress.grid_remove()
        self.set_status(f"Video baixado: {os.path.basename(path)}")
        self._load_video_path(path)

    def _on_dl_error(self, msg):
        self.downloading = False
        self.btn_download.configure(state="normal", text="Baixar Video")
        self.dl_progress.grid_remove()
        messagebox.showerror("Erro", msg)
        self.set_status("Erro no download.")

    # ---- open local ----
    def open_video(self):
        path = filedialog.askopenfilename(
            title="Selecione um video",
            filetypes=[("Videos", "*.mp4 *.mov *.avi *.mkv *.webm"), ("Todos", "*.*")]
        )
        if path:
            self._load_video_path(path)

    def _load_video_path(self, path):
        self.set_status("Carregando video...")
        self.update()
        if self.processor.load(path):
            self.file_loaded = True
            self.video_duration = self.processor.duration
            self.file_label.configure(text=f"{os.path.basename(path)} ({self._fmt_time(self.video_duration)})")
            self.lbl_duration.configure(text=f"Duracao: {self._fmt_time(self.video_duration)}")
            self.btn_analyze.configure(state="normal")
            self.viral_segments = []
            self.score_data = None
            self.time_axis = None
            self.selected_start = 0
            self.selected_end = 0
            self.btn_export.configure(state="disabled")
            self.btn_select_first.configure(state="disabled")
            self.lbl_segments.configure(text="Clipes virais: --")
            self.lbl_selection.configure(text="Selecao: --")
            self.canvas.delete("all")
            self._clear_seg_list()
            self.set_status("Video carregado. Clique em 'Analisar' para detectar momentos virais.")
        else:
            messagebox.showerror("Erro", "Nao foi possivel carregar o video.")

    # ---- analyze ----
    def analyze_video(self):
        if not self.file_loaded or self.analyzing:
            return
        self.analyzing = True
        self.btn_analyze.configure(state="disabled", text="Analisando...")
        self.analyze_progress.grid()
        self.analyze_progress.start()
        self.set_status("Analisando audio para detectar momentos virais...")

        def task():
            try:
                segs, scores, tax = detect_viral_moments(
                    self.processor.audio_path, self.video_duration,
                    sensitivity=self.sensitivity_var.get(),
                    min_clip_duration=self.min_clip_var.get(),
                    max_clip_duration=self.max_clip_var.get()
                )
                self.after(0, lambda: self._on_analysis_done(segs, scores, tax))
            except Exception as e:
                self.after(0, lambda: self._on_analysis_error(str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _on_analysis_done(self, segs, scores, tax):
        self.analyzing = False
        self.analyze_progress.stop()
        self.analyze_progress.grid_remove()
        self.btn_analyze.configure(state="normal", text="Analisar Novamente")
        self.viral_segments = segs
        self.score_data = scores
        self.time_axis = tax
        self.lbl_segments.configure(text=f"Clipes virais: {len(segs)}")
        self._draw_timeline()
        self._populate_seg_list()
        if segs:
            self.select_top_segment()
            self.btn_export.configure(state="normal")
            self.btn_select_first.configure(state="normal")
            self.set_status(f"{len(segs)} momentos virais encontrados!")
        else:
            self.set_status("Nenhum momento viral encontrado. Tente diminuir a sensibilidade.")

    def _on_analysis_error(self, error):
        self.analyzing = False
        self.analyze_progress.stop()
        self.analyze_progress.grid_remove()
        self.btn_analyze.configure(state="normal", text="Analisar Momentos Virais")
        messagebox.showerror("Erro", f"Falha ao analisar:\n{error}")
        self.set_status("Erro na analise.")

    # ---- timeline ----
    def _draw_timeline(self):
        self.canvas.delete("all")
        cw = self.canvas.winfo_width() - TIMELINE_PAD * 2
        if cw < 100:
            cw = 800
        h = CANVAS_H

        self.canvas.create_rectangle(TIMELINE_PAD, 10, TIMELINE_PAD + cw, h + 10,
                                      fill="#16213e", outline="#0f3460", width=1)

        if self.score_data is None or self.time_axis is None:
            self.canvas.create_text(TIMELINE_PAD + cw // 2, h // 2 + 10,
                                    text="Analise o video para ver o grafico de momentos virais",
                                    fill="#555", font=("Arial", 13))
            return

        step = max(1, len(self.score_data) // cw)
        scored = self.score_data[::step][:cw]
        max_s = np.max(scored) if np.max(scored) > 0 else 1
        norm = scored / max_s

        threshold = np.percentile(self.score_data,
                                   max(10, min(90, 80 - (self.sensitivity_var.get() - 1) * 30)))

        for i in range(min(len(norm), cw)):
            x = TIMELINE_PAD + i
            bar_h = max(2, norm[i] * (h - 20))
            y0 = h + 10 - bar_h
            idx = i * step
            is_viral = idx < len(self.score_data) and self.score_data[idx] > threshold
            if is_viral:
                intensity = min(1, self.score_data[idx] / (threshold * 2)) if threshold > 0 else 0.5
                r = int(233 - intensity * 80)
                g = int(69 + intensity * 50)
                b = int(96 - intensity * 40)
                color = f"#{r:02x}{g:02x}{b:02x}"
            else:
                color = "#1a1a4e"
            self.canvas.create_line(x, h + 10, x, y0, fill=color, width=1)

        if self.selected_end > self.selected_start:
            sx = TIMELINE_PAD + int((self.selected_start / self.video_duration) * cw)
            ex = TIMELINE_PAD + int((self.selected_end / self.video_duration) * cw)
            self.canvas.create_rectangle(sx, 10, ex, h + 10,
                                          fill="#e9456040", outline="#e94560", width=2)
            self.canvas.create_text((sx + ex) // 2, h + 25,
                                    text=f"{self.selected_end - self.selected_start:.1f}s",
                                    fill="white", font=("Arial", 9, "bold"))

        for t in range(0, int(self.video_duration) + 1,
                       max(1, int(self.video_duration // 10))):
            x = TIMELINE_PAD + int((t / self.video_duration) * cw)
            self.canvas.create_line(x, h + 10, x, h + 18, fill="#555", width=1)
            self.canvas.create_text(x, h + 28, text=self._fmt_time(t), fill="#888",
                                    font=("Arial", 8))

    def _populate_seg_list(self):
        for w in self.seg_list_inner.winfo_children():
            w.destroy()
        if not self.viral_segments:
            ctk.CTkLabel(self.seg_list_inner, text="Nenhum segmento encontrado",
                         text_color="gray").pack(pady=20)
            return

        for i, seg in enumerate(self.viral_segments):
            frame = ctk.CTkFrame(self.seg_list_inner, fg_color="#1a1a2e", corner_radius=8,
                                 border_width=1, border_color="#0f3460")
            frame.pack(fill="x", pady=3, padx=2)

            r1 = ctk.CTkFrame(frame, fg_color="transparent")
            r1.pack(fill="x", padx=8, pady=(6, 2))
            ctk.CTkLabel(r1, text=f"#{i+1}",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color="#e94560").pack(side="left", padx=(0, 8))
            ctk.CTkLabel(r1, text=seg.reason,
                         font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(r1, text=f"{seg.score:.2f}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#ffd700").pack(side="right")

            r2 = ctk.CTkFrame(frame, fg_color="transparent")
            r2.pack(fill="x", padx=8, pady=(0, 6))
            ctk.CTkLabel(r2, text=f"{self._fmt_time(seg.start_sec)} -> {self._fmt_time(seg.end_sec)}",
                         font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left")
            ctk.CTkLabel(r2, text=f"({seg.end_sec - seg.start_sec:.1f}s)",
                         font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left", padx=5)
            ctk.CTkButton(r2, text="Selecionar", width=80, height=25,
                           command=lambda s=seg: self.select_segment(s)).pack(side="right")

    def select_top_segment(self):
        if self.viral_segments:
            self.select_segment(self.viral_segments[0])

    def select_segment(self, seg: ViralSegment):
        self.selected_start = seg.start_sec
        self.selected_end = seg.end_sec
        self.lbl_selection.configure(
            text=f"Selecao: {self._fmt_time(seg.start_sec)} -> {self._fmt_time(seg.end_sec)} ({seg.end_sec - seg.start_sec:.1f}s)")
        self.btn_export.configure(state="normal")
        self._draw_timeline()
        self._show_preview()

    def _show_preview(self):
        mid = (self.selected_start + self.selected_end) / 2
        thumb_path = os.path.join(self.processor.temp_dir or os.path.expanduser("~"), "_preview.jpg")
        try:
            self.processor.get_frame_at(mid, thumb_path)
            img = Image.open(thumb_path)
            max_w = 400
            ratio = max_w / img.width
            new_h = int(img.height * ratio)
            img = img.resize((max_w, new_h), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=tk_img, text="")
            self.preview_label.image = tk_img
        except:
            self.preview_label.configure(
                text=f"Preview\n{self._fmt_time(self.selected_start)} -> {self._fmt_time(self.selected_end)}\n({self.selected_end - self.selected_start:.1f}s)")
            if hasattr(self.preview_label, 'image'):
                del self.preview_label.image

    # ---- export ----
    def export_clip(self):
        if not self.file_loaded or self.selected_end <= self.selected_start:
            return
        output_dir = filedialog.askdirectory(title="Salvar clipe em...")
        if not output_dir:
            return
        name = os.path.splitext(os.path.basename(self.processor.video_path))[0]
        ts = self._fmt_time(self.selected_start).replace(":", "-")
        output = os.path.join(output_dir, f"{name}_clip_{ts}.mp4")

        # Generate hook text based on current segment score
        hook = _pick_hook(0.7)
        if self.viral_segments:
            top_score = self.viral_segments[0].score
            hook = _pick_hook(min(1.0, top_score))

        self.set_status("Exportando clipe...")
        self.btn_export.configure(state="disabled", text="Exportando...")
        self.update()

        def task():
            pos = self.watermark_pos_var.get()
            ok = self.processor.export_clip(
                self.selected_start, self.selected_end, output,
                add_watermark=self.watermark_var.get(),
                watermark_text="@CanalPropra",
                watermark_position=pos,
                add_progress_bar=self.progress_bar_var.get(),
                add_countdown=self.countdown_var.get(),
                add_highlight=self.highlight_var.get(),
                shorts_mode=self.shorts_var.get(),
                viral_audio=self.viral_audio_var.get(),
                add_subtitles=self.subtitles_var.get(),
                hook_text=hook,
                loop_mode=self.loop_var.get()
            )
            self.after(0, lambda: self._on_export_done(ok, output))
        threading.Thread(target=task, daemon=True).start()

    def _on_export_done(self, ok, path):
        self.btn_export.configure(state="normal", text="Exportar Clipe")
        if ok:
            self.last_exported_path = path
            self.set_status(f"Clipe exportado em {path}")
            self.btn_upload.configure(state="normal")
            messagebox.showinfo("Exportado!", f"Clipe salvo em:\n{path}")
        else:
            messagebox.showerror("Erro", "Falha ao exportar clipe.")
            self.set_status("Erro ao exportar.")

    # ---- youtube upload ----
    def setup_youtube_credentials(self):
        if not has_credentials():
            msg = generate_credentials_guide()
            answer = messagebox.askyesno("Credenciais do YouTube",
                                          msg + "\n\nVoce ja baixou o arquivo client_secret.json?")
            if answer:
                path = filedialog.askopenfilename(
                    title="Selecione o arquivo client_secret.json",
                    filetypes=[("JSON", "*.json")]
                )
                if path:
                    set_credentials_from_path(path)
                    messagebox.showinfo("OK", "Credenciais salvas! Clique em 'Postar no YouTube'.")
                    return True
            return False
        return True

    def upload_to_youtube(self):
        if not self.last_exported_path or not os.path.exists(self.last_exported_path):
            messagebox.showwarning("Atencao", "Exporte um clipe primeiro.")
            return

        if not has_credentials():
            self.setup_youtube_credentials()
            if not has_credentials():
                return

        self.btn_upload.configure(state="disabled", text="Enviando...")
        self.upload_progress.grid()
        self.upload_progress.set(0)
        self.set_status("Enviando para o YouTube...")

        def on_progress(pct):
            self.after(0, lambda: self.upload_progress.set(pct / 100))

        def task():
            try:
                hook = _pick_hook(0.7)
                if self.viral_segments:
                    top_score = self.viral_segments[0].score
                    hook = _pick_hook(min(1.0, top_score))
                game = self.game_name_var.get().strip() or "Valorant"
                title = f"{hook} | {game} | ClipCrafter"
                desc = (f"{hook} Momentos que acontecem no {game}!\n\n"
                        f"#ClipCrafter #CanalPropra #{game.replace(' ', '')}\n"
                        f"https://www.youtube.com/@CanalPropra")
                vid = upload_video(
                    self.last_exported_path,
                    title=title,
                    description=desc,
                    tags=["ClipCrafter", "CanalPropra", "clipe", "games", game.replace(" ", "")],
                    privacy_status="public",
                    on_progress=on_progress
                )
                self.after(0, lambda: self._on_upload_done(vid))
            except Exception as e:
                self.after(0, lambda: self._on_upload_error(str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _on_upload_done(self, video_id):
        self.btn_upload.configure(state="normal", text="Postar no YouTube")
        self.upload_progress.grid_remove()
        if video_id:
            url = f"https://youtu.be/{video_id}"
            self.set_status(f"Publicado! {url}")
            messagebox.showinfo("Publicado!",
                                f"Video publicado com sucesso!\n{url}")
        else:
            messagebox.showerror("Erro", "Falha ao publicar. Verifique suas credenciais.")
            self.set_status("Erro ao publicar.")

    def _on_upload_error(self, error):
        self.btn_upload.configure(state="normal", text="Postar no YouTube")
        self.upload_progress.grid_remove()
        messagebox.showerror("Erro", f"Falha ao enviar:\n{error}")
        self.set_status("Erro no upload.")

    # ---- canvas events ----
    def on_canvas_click(self, event):
        if not self.file_loaded or self.video_duration == 0:
            return
        cw = self.canvas.winfo_width() - TIMELINE_PAD * 2
        if cw <= 0:
            return
        x = event.x - TIMELINE_PAD
        if x < 0 or x > cw:
            return
        t = (x / cw) * self.video_duration

        if self.selected_end > self.selected_start:
            sx = TIMELINE_PAD + int((self.selected_start / self.video_duration) * cw)
            ex = TIMELINE_PAD + int((self.selected_end / self.video_duration) * cw)
            if abs(event.x - sx) < 8:
                self.dragging = "start"
                return
            if abs(event.x - ex) < 8:
                self.dragging = "end"
                return

        nearest = None
        near_dist = float("inf")
        for seg in self.viral_segments:
            if seg.start_sec <= t <= seg.end_sec:
                self.select_segment(seg)
                return
            d = min(abs(t - seg.start_sec), abs(t - seg.end_sec))
            if d < near_dist:
                near_dist = d
                nearest = seg
        if nearest and near_dist < self.video_duration * 0.05:
            self.select_segment(nearest)

    def on_canvas_drag(self, event):
        if not self.dragging:
            return
        cw = self.canvas.winfo_width() - TIMELINE_PAD * 2
        if cw <= 0:
            return
        x = max(0, min(cw, event.x - TIMELINE_PAD))
        t = (x / cw) * self.video_duration
        t = max(0, min(t, self.video_duration))
        if self.dragging == "start" and t < self.selected_end - 1.0:
            self.selected_start = t
        elif self.dragging == "end" and t > self.selected_start + 1.0:
            self.selected_end = t
        self.lbl_selection.configure(
            text=f"Selecao: {self._fmt_time(self.selected_start)} -> {self._fmt_time(self.selected_end)} ({self.selected_end - self.selected_start:.1f}s)")
        self._draw_timeline()

    def on_canvas_release(self, event):
        if self.dragging:
            self.dragging = None
            self._show_preview()

    # ---- helpers ----
    def set_status(self, text):
        self.lbl_status.configure(text=text)

    def _clear_seg_list(self):
        for w in self.seg_list_inner.winfo_children():
            w.destroy()

    def _fmt_time(self, seconds):
        seconds = max(0, seconds)
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"

    def on_closing(self):
        self.downloader.cancel()
        self.processor.cleanup()
        self.destroy()
