# -*- coding: utf-8 -*-
"""
UYAP Tahliye ve Denetim Kontrol Robotu - Modern Kullanıcı Arayüzü (GUI)
"""
import os
import time
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import ctypes
from ctypes import wintypes
import winsound

user32 = ctypes.windll.user32

from config import (
    CALIBRATION_STEPS, EXCEL_OUTPUT_PATH, BACKUP_DIR,
    STARTUP_COUNTDOWN, SAVED_CASES_FILE
)
from pdf_reader import PdfReader
from ocr_engine import OcrEngine
from tahliye_bot import TahliyeBot

class TahliyeApp(tk.Tk):
    COLOR_PRIMARY = "#1E88E5"
    COLOR_SUCCESS = "#2E7D32"
    COLOR_DANGER  = "#D32F2F"
    COLOR_WARNING = "#F57C00"
    COLOR_PURPLE  = "#6A1B9A"
    COLOR_BG      = "#ECEFF1"
    COLOR_CARD    = "#FFFFFF"

    def __init__(self):
        super().__init__()

        self.title("UYAP Tahliye Bekleyen Para Cezası ve Denetim Kontrol Robotu")
        self.geometry("1150x760")
        self.minsize(980, 640)
        self.configure(bg=self.COLOR_BG)

        # Temel Nesneler
        self.ocr_engine = OcrEngine()
        self.pdf_reader = PdfReader(ocr_engine=self.ocr_engine)
        self.bot = TahliyeBot(ocr_engine=self.ocr_engine)
        self.calibration = self.bot.calibration

        self.loaded_cases = []
        self.results_data = []
        self.worker_thread = None

        self._setup_style()
        self._create_widgets()
        self._load_persisted_case_list()
        self._update_calib_status_label()

        # Global ESC Kısayolu ve Mouse Failsafe
        self.bind("<Escape>", lambda e: self._handle_esc_press())
        self._start_hotkey_listener()

    def _setup_style(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure("TNotebook", background=self.COLOR_BG)
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[14, 6])
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self.style.configure("Treeview", font=("Segoe UI", 9), rowheight=24)

    def _create_widgets(self):
        header = tk.Frame(self, bg=self.COLOR_PRIMARY, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        lbl_title = tk.Label(
            header,
            text="⚖ UYAP Tahliye Bekleyen Para Cezası & Denetim Kontrol Robotu",
            font=("Segoe UI", 13, "bold"),
            fg="#FFFFFF",
            bg=self.COLOR_PRIMARY
        )
        lbl_title.pack(side=tk.LEFT, padx=16)

        # Üst Kontrol Kartı
        top_card = tk.Frame(self, bg=self.COLOR_CARD, bd=1, relief=tk.SOLID)
        top_card.pack(fill=tk.X, padx=14, pady=10)

        r1 = tk.Frame(top_card, bg=self.COLOR_CARD)
        r1.pack(fill=tk.X, padx=12, pady=6)

        self.btn_select_file = tk.Button(
            r1,
            text="📁 PDF / Liste Dosyası Seç",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLOR_PRIMARY,
            fg="#FFFFFF",
            activebackground="#1565C0",
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            command=self.select_pdf_file
        )
        self.btn_select_file.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_clear_list = tk.Button(
            r1,
            text="🗑 Listeyi Sıfırla",
            font=("Segoe UI", 9, "bold"),
            bg="#ECEFF1",
            fg="#546E7A",
            activebackground="#CFD8DC",
            relief=tk.FLAT,
            padx=8,
            pady=5,
            cursor="hand2",
            command=self.clear_saved_list
        )
        self.btn_clear_list.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_file_status = tk.Label(
            r1,
            text="Lütfen kontrol edilecek dosya listesini (PDF) seçin.",
            font=("Segoe UI", 9),
            bg=self.COLOR_CARD,
            fg="#546E7A"
        )
        self.lbl_file_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_calib = tk.Button(
            r1,
            text="🎯 Ekranda Yerleri Göster (Kalibrasyon Sihirbazı)",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLOR_PURPLE,
            fg="#FFFFFF",
            activebackground="#4A148C",
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            command=self.open_calibration_wizard
        )
        self.btn_calib.pack(side=tk.RIGHT)

        # İkinci Satır: Kalibrasyon Durumu ve Eylemler
        r2 = tk.Frame(top_card, bg=self.COLOR_CARD)
        r2.pack(fill=tk.X, padx=12, pady=(0, 6))

        self.lbl_calib_status = tk.Label(
            r2,
            text="Kalibrasyon Durumu: Kontrol ediliyor...",
            font=("Segoe UI", 9, "bold"),
            bg=self.COLOR_CARD,
            fg="#546E7A"
        )
        self.lbl_calib_status.pack(side=tk.LEFT)

        self.btn_start = tk.Button(
            r2,
            text="▶ Kontrolü Başlat (1'den)",
            font=("Segoe UI", 11, "bold"),
            bg=self.COLOR_SUCCESS,
            fg="#FFFFFF",
            activebackground="#1B5E20",
            relief=tk.FLAT,
            padx=16,
            pady=5,
            cursor="hand2",
            state=tk.DISABLED,
            command=lambda: self.start_automation(start_index=1)
        )
        self.btn_start.pack(side=tk.RIGHT, padx=(8, 0))

        self.btn_stop = tk.Button(
            r2,
            text="⏹ Durdur (ESC)",
            font=("Segoe UI", 11, "bold"),
            bg=self.COLOR_DANGER,
            fg="#FFFFFF",
            activebackground="#B71C1C",
            relief=tk.FLAT,
            padx=16,
            pady=5,
            cursor="hand2",
            state=tk.DISABLED,
            command=self.stop_automation
        )
        self.btn_stop.pack(side=tk.RIGHT)

        # Üçüncü Satır: Kaldığı Yerden Devam Et & Belirli Numaradan Başlat Paneli
        r3 = tk.Frame(top_card, bg="#F1F5F9", bd=1, relief=tk.GROOVE)
        r3.pack(fill=tk.X, padx=12, pady=(0, 6))

        lbl_start_label = tk.Label(
            r3,
            text="🎯 Başlangıç Noktası (Sıra veya Dosya No):",
            font=("Segoe UI", 9, "bold"),
            bg="#F1F5F9",
            fg="#1E293B"
        )
        lbl_start_label.pack(side=tk.LEFT, padx=(8, 4), pady=5)

        self.ent_start_from = ttk.Entry(r3, font=("Segoe UI", 9, "bold"), width=16)
        self.ent_start_from.insert(0, "1")
        self.ent_start_from.pack(side=tk.LEFT, padx=(0, 6), pady=5)

        self.lbl_resume_hint = tk.Label(
            r3,
            text="",
            font=("Segoe UI", 8, "italic"),
            bg="#F1F5F9",
            fg="#0369A1"
        )
        self.lbl_resume_hint.pack(side=tk.LEFT, padx=(4, 10), pady=5)

        self.btn_resume = tk.Button(
            r3,
            text="⏩ Kaldığı Yerden Devam Et",
            font=("Segoe UI", 9, "bold"),
            bg="#D97706",
            fg="#FFFFFF",
            activebackground="#B45309",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED,
            command=self.resume_automation
        )
        self.btn_resume.pack(side=tk.RIGHT, padx=(4, 8), pady=4)

        self.btn_start_from = tk.Button(
            r3,
            text="▶ Girilen Numaradan Başlat",
            font=("Segoe UI", 9, "bold"),
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED,
            command=self.start_from_custom_number
        )
        self.btn_start_from.pack(side=tk.RIGHT, padx=4, pady=4)

        # İlerleme Çubuğu ve Durum
        prog_frame = tk.Frame(self, bg=self.COLOR_BG)
        prog_frame.pack(fill=tk.X, padx=14, pady=(0, 6))

        self.lbl_progress = tk.Label(
            prog_frame,
            text="Hazır. Dosya seçildiğinde kontrol başlatılabilir.",
            font=("Segoe UI", 9, "bold"),
            bg=self.COLOR_BG,
            fg="#37474F"
        )
        self.lbl_progress.pack(anchor="w")

        self.progress_bar = ttk.Progressbar(prog_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(2, 0))

        # Sekmeli Alan (Notebook)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        # SEKME 1: CANLI SONUÇLAR
        self.tab_results = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_results, text=" ⚡ UYAP Canlı Kontrol Sonuçları ")

        res_cols = ("sira", "dosya_no", "genel_durum", "cezaevi", "denetim", "detay")
        self.tree_res = ttk.Treeview(self.tab_results, columns=res_cols, show="headings", selectmode="browse")
        self.tree_res.heading("sira", text="Sıra")
        self.tree_res.heading("dosya_no", text="Dosya No")
        self.tree_res.heading("genel_durum", text="Genel Durum (Sonuç)")
        self.tree_res.heading("cezaevi", text="Cezaevi Durumu")
        self.tree_res.heading("denetim", text="Denetim Durumu")
        self.tree_res.heading("detay", text="Açıklama / Detay")

        self.tree_res.column("sira", width=60, anchor="center")
        self.tree_res.column("dosya_no", width=140, anchor="center")
        self.tree_res.column("genel_durum", width=220, anchor="center")
        self.tree_res.column("cezaevi", width=130, anchor="center")
        self.tree_res.column("denetim", width=130, anchor="center")
        self.tree_res.column("detay", width=350, anchor="w")

        self.tree_res.tag_configure("cezaevi", background="#FFCDD2", foreground="#B71C1C")
        self.tree_res.tag_configure("denetim", background="#FFF9C4", foreground="#F57F17")
        self.tree_res.tag_configure("temiz", background="#C8E6C9", foreground="#1B5E20")
        self.tree_res.tag_configure("hata", background="#CFD8DC", foreground="#37474F")

        sb_res = ttk.Scrollbar(self.tab_results, orient=tk.VERTICAL, command=self.tree_res.yview)
        self.tree_res.configure(yscrollcommand=sb_res.set)
        self.tree_res.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_res.pack(side=tk.RIGHT, fill=tk.Y)

        # SEKME 2: YÜKLENEN LİSTE ÖNİZLEME
        self.tab_preview = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_preview, text=" 📋 Yüklenen Dosyalar Önizleme ")

        prev_cols = ("sira", "dosya_no")
        self.tree_prev = ttk.Treeview(self.tab_preview, columns=prev_cols, show="headings")
        self.tree_prev.heading("sira", text="Sıra No")
        self.tree_prev.heading("dosya_no", text="İlamat / Dosya No")
        self.tree_prev.column("sira", width=80, anchor="center")
        self.tree_prev.column("dosya_no", width=300, anchor="w")
        self.tree_prev.pack(fill=tk.BOTH, expand=True)

        def _on_prev_double_click(event):
            sel = self.tree_prev.selection()
            if sel:
                vals = self.tree_prev.item(sel[0], "values")
                if vals:
                    s_no, d_no = vals[0], vals[1]
                    self.ent_start_from.delete(0, tk.END)
                    self.ent_start_from.insert(0, str(s_no))
                    self.notebook.select(self.tab_results)
                    self.log(f"📍 Başlangıç noktası seçildi: Sıra #{s_no} ({d_no})")
        self.tree_prev.bind("<Double-1>", _on_prev_double_click)

        # SEKME 3: İŞLEM GÜNLÜĞÜ (LOG)
        self.tab_log = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_log, text=" 📝 Canlı İşlem Günlüğü ")
        self.txt_log = tk.Text(self.tab_log, bg="#263238", fg="#ECEFF1", font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    def log(self, msg):
        def _append():
            self.txt_log.insert(tk.END, msg + "\n")
            self.txt_log.see(tk.END)
        self.after(0, _append)

    def _update_calib_status_label(self):
        calibrated = self.calibration.is_calibrated()
        if calibrated:
            self.lbl_calib_status.config(text="✔ Kalibrasyon Tamam: Tüm 11 UYAP butonu kayıtlı.", fg=self.COLOR_SUCCESS)
            if self.loaded_cases:
                self.btn_start.config(state=tk.NORMAL)
                self.btn_start_from.config(state=tk.NORMAL)
                self.check_resume_status()
        else:
            missing = len(self.calibration.get_missing_steps())
            self.lbl_calib_status.config(text=f"⚠ Kalibrasyon Eksik: {missing} nokta tanıtılmalı.", fg=self.COLOR_WARNING)
            self.btn_start.config(state=tk.DISABLED)
            self.btn_resume.config(state=tk.DISABLED)
            self.btn_start_from.config(state=tk.DISABLED)

    def resolve_start_index(self, query_str):
        """Kullanıcının girdiği sıra numarası veya dosya numarasını 1-tabanlı dizine çevirir."""
        if not self.loaded_cases:
            return 1
        q = str(query_str).strip()
        if not q:
            return 1

        # 1. Doğrudan bir sıra numarası girildiyse (örn: 350)
        if q.isdigit():
            val = int(q)
            if 1 <= val <= len(self.loaded_cases):
                return val
            elif val > len(self.loaded_cases):
                return len(self.loaded_cases)
            return 1

        # 2. Dosya numarası girildiyse (örn: 2015/2-100 veya 2015/100)
        q_norm = q.replace(" ", "").lower()
        for idx, c in enumerate(self.loaded_cases, start=1):
            c_norm = c.replace(" ", "").lower()
            if q_norm == c_norm:
                return idx
            if "/" in q_norm and "/2-" not in q_norm:
                parts = q_norm.split("/", 1)
                alt = f"{parts[0]}/2-{parts[1]}"
                if alt == c_norm:
                    return idx
            if q_norm in c_norm:
                return idx

        return 1

    def get_resume_index(self):
        """Mevcut oturumdan veya masaüstündeki Excel'den en son işlenen dosyanın bir sonraki sırasını döndürür."""
        if not self.loaded_cases:
            return 1

        # 1. Önce aktif oturumdaki sonuçlara bak
        if self.results_data:
            last_done = self.results_data[-1].get("dosya_no")
            if last_done in self.loaded_cases:
                last_idx = self.loaded_cases.index(last_done) + 1
                if last_idx < len(self.loaded_cases):
                    return last_idx + 1
                return last_idx

        # 2. Masaüstündeki Excel dosyasını kontrol et
        if os.path.exists(EXCEL_OUTPUT_PATH):
            try:
                df = pd.read_excel(EXCEL_OUTPUT_PATH)
                if df is not None and len(df) > 0 and "Dosya No" in df.columns:
                    done_cases = df["Dosya No"].dropna().astype(str).tolist()
                    for c in reversed(done_cases):
                        c_clean = c.strip()
                        if c_clean in self.loaded_cases:
                            last_idx = self.loaded_cases.index(c_clean) + 1
                            if last_idx < len(self.loaded_cases):
                                return last_idx + 1
                            return last_idx
            except Exception:
                pass

        return 1

    def check_resume_status(self):
        """Kaldığı yer durumunu denetler ve butonları/bilgi etiketini günceller."""
        if not self.loaded_cases:
            self.lbl_resume_hint.config(text="")
            return

        resume_idx = self.get_resume_index()
        total = len(self.loaded_cases)

        if resume_idx > 1:
            next_case = self.loaded_cases[resume_idx - 1] if resume_idx <= total else "Tamamlandı"
            self.lbl_resume_hint.config(
                text=f"💡 Önceki çalışma tespit edildi! Kaldığı yer: Sıra #{resume_idx} ({next_case})"
            )
            if self.calibration.is_calibrated():
                self.btn_resume.config(state=tk.NORMAL)
        else:
            self.lbl_resume_hint.config(text="💡 Liste henüz taranmadı. 1. sıradan başlayacak.")
            self.btn_resume.config(state=tk.DISABLED)

    def _load_excel_to_treeview(self):
        """Excel'de önceden kayıtlı dosyaları canlı sonuç tablosuna doldurur."""
        if not os.path.exists(EXCEL_OUTPUT_PATH):
            return
        try:
            df = pd.read_excel(EXCEL_OUTPUT_PATH)
            if df is None or len(df) == 0 or "Dosya No" not in df.columns:
                return

            for idx, row in df.iterrows():
                d_no = str(row.get("Dosya No", "-"))
                g_durum = str(row.get("Genel Durum (Sonuç)", "-"))
                c_durum = str(row.get("Cezaevi Durumu", "-"))
                den_durum = str(row.get("Denetim Durumu", "-"))
                detay = str(row.get("Açıklama / Detay", "-"))

                sira = idx + 1
                if self.loaded_cases and d_no in self.loaded_cases:
                    sira = self.loaded_cases.index(d_no) + 1

                tag = "temiz"
                if "Cezaevinde" in g_durum:
                    tag = "cezaevi"
                elif "Denetim" in g_durum:
                    tag = "denetim"
                elif "Hata" in g_durum:
                    tag = "hata"

                self.tree_res.insert("", tk.END, values=(sira, d_no, g_durum, c_durum, den_durum, detay), tags=(tag,))
        except Exception:
            pass

    def resume_automation(self):
        """Kaldığı yerden doğrudan devam ettirir."""
        if not self.loaded_cases:
            messagebox.showwarning("Uyarı", "Lütfen önce bir liste (PDF) yükleyin.")
            return
        idx = self.get_resume_index()
        self.ent_start_from.delete(0, tk.END)
        self.ent_start_from.insert(0, str(idx))
        self.start_automation(start_index=idx)

    def start_from_custom_number(self):
        """Kullanıcının kutucuğa yazdığı sıra no veya dosya no'dan başlatır."""
        raw = self.ent_start_from.get()
        idx = self.resolve_start_index(raw)
        self.ent_start_from.delete(0, tk.END)
        self.ent_start_from.insert(0, str(idx))
        self.start_automation(start_index=idx)

    def _load_persisted_case_list(self):
        """Uygulama açıldığında daha önce diske kaydedilmiş dosya listesini otomatik yükler."""
        if not os.path.exists(SAVED_CASES_FILE):
            return
        try:
            with open(SAVED_CASES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cases = data.get("cases", [])
            fn = data.get("file_name", "Kayıtlı Liste")
            if cases:
                self.loaded_cases = cases
                self.lbl_file_status.config(text=f"✔ {fn} (Kayıtlı Liste: Toplam {len(cases)} dosya)")
                self.progress_bar["maximum"] = len(cases)
                self.progress_bar["value"] = 0

                for r in self.tree_prev.get_children():
                    self.tree_prev.delete(r)
                for i, c in enumerate(cases, 1):
                    self.tree_prev.insert("", tk.END, values=(i, c))

                self._update_calib_status_label()
                resume_idx = self.get_resume_index()
                self.ent_start_from.delete(0, tk.END)
                self.ent_start_from.insert(0, str(resume_idx))
                self.check_resume_status()
                self.log(f"💾 Kayıtlı liste otomatik yüklendi: {fn} ({len(cases)} dosya)")
        except Exception:
            pass

    def _save_persisted_case_list(self, cases, file_path):
        """Yüklenen listeyi kalıcı olarak diske kaydeder (kapatıp açıldığında kaybolmaz)."""
        try:
            data = {
                "file_name": os.path.basename(file_path),
                "file_path": file_path,
                "total": len(cases),
                "cases": cases,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(SAVED_CASES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log(f"💾 {len(cases)} adet dosya kalıcı olarak kaydedildi. Uygulama açılışlarında otomatik yüklenecektir.")
        except Exception:
            pass

    def clear_saved_list(self):
        """Kayıtlı listeyi kullanıcı isteğiyle temizler."""
        if not self.loaded_cases:
            messagebox.showinfo("Bilgi", "Zaten yüklü bir liste bulunmuyor.")
            return

        ans = messagebox.askyesno(
            "Listeyi Temizle",
            "Mevcut kayıtlı dosya listesini silmek istiyor musunuz?\n\n"
            "Bu işlem taranan sonuçları veya Excel yedeğini etkilemez; yalnızca yüklenmiş dosya listesini sıfırlar."
        )
        if not ans:
            return

        try:
            if os.path.exists(SAVED_CASES_FILE):
                os.remove(SAVED_CASES_FILE)
        except Exception:
            pass

        self.loaded_cases = []
        for r in self.tree_prev.get_children():
            self.tree_prev.delete(r)

        self.lbl_file_status.config(text="Lütfen kontrol edilecek dosya listesini (PDF) seçin.")
        self.progress_bar["maximum"] = 100
        self.progress_bar["value"] = 0
        self.ent_start_from.delete(0, tk.END)
        self.ent_start_from.insert(0, "1")
        self.lbl_resume_hint.config(text="")
        self._update_calib_status_label()
        self.log("🗑 Kayıtlı liste temizlendi.")

    def select_pdf_file(self):
        fp = filedialog.askopenfilename(
            title="Tahliye Bekleyen Para Cezası Listesini Seçin",
            filetypes=[("Desteklenen Dosyalar", "*.pdf;*.txt"), ("PDF Dosyaları", "*.pdf"), ("Metin Dosyaları", "*.txt")]
        )
        if not fp:
            return
        self.log(f"Dosya seçildi: {fp}")
        cases = self.pdf_reader.load_case_list(fp)
        if not cases:
            self.log(f"⚠ Uyarı: '{os.path.basename(fp)}' dosyasında TBP ilamat numarası tespit edilemedi.")
            messagebox.showwarning(
                "Uyarı",
                "Seçilen dosyada ilamat / dosya numarası tespit edilemedi.\n\n"
                "Lütfen dosyanın 'TBP - CEZA İNFAZ KURUMUNDAN TAHLİYE BEKLEYEN PARA CEZASI' tablosunu içerdiğinden emin olun."
            )
            return

        self.loaded_cases = cases
        self._save_persisted_case_list(cases, fp)
        self.lbl_file_status.config(text=f"✔ {os.path.basename(fp)} (Toplam {len(cases)} adet dosya yüklendi)")
        self.progress_bar["maximum"] = len(cases)
        self.progress_bar["value"] = 0

        # Önizleme tablosunu doldur
        for r in self.tree_prev.get_children():
            self.tree_prev.delete(r)
        for i, c in enumerate(cases, 1):
            self.tree_prev.insert("", tk.END, values=(i, c))

        self.log(f"Dosya yüklendi: {fp} (Toplam {len(cases)} kayıt)")
        self._update_calib_status_label()

        # Kaldığı yeri kontrol et ve başlangıç kutusuna yaz
        resume_idx = self.get_resume_index()
        self.ent_start_from.delete(0, tk.END)
        self.ent_start_from.insert(0, str(resume_idx))
        self.check_resume_status()

    def open_calibration_wizard(self):
        """Kullanıcının 11 adımı ekranda gösterip [Boşluk] ile kaydettiği sihirbaz."""
        wiz = tk.Toplevel(self)
        wiz.title("🎯 UYAP Kalibrasyon Sihirbazı")
        wiz.geometry("700x380")
        wiz.attributes("-topmost", True)
        wiz.configure(bg="#F9FAFB")

        current_step_idx = [0]
        collected = dict(self.calibration.coordinates)

        lbl_step_num = tk.Label(wiz, text="", font=("Segoe UI", 12, "bold"), fg=self.COLOR_PRIMARY, bg="#F9FAFB")
        lbl_step_num.pack(pady=(16, 4))

        lbl_title = tk.Label(wiz, text="", font=("Segoe UI", 13, "bold"), fg="#212121", bg="#F9FAFB")
        lbl_title.pack(pady=(0, 6))

        lbl_desc = tk.Label(wiz, text="", font=("Segoe UI", 10), fg="#546E7A", bg="#F9FAFB", wraplength=640, justify="center")
        lbl_desc.pack(pady=(0, 16))

        lbl_coord = tk.Label(wiz, text="Farenizi butonun üzerine getirin ve [Boşluk] veya [F2] tuşuna basın.", font=("Segoe UI", 10, "bold"), fg="#D32F2F", bg="#F9FAFB")
        lbl_coord.pack(pady=(0, 16))

        def update_step_ui():
            idx = current_step_idx[0]
            if idx < len(CALIBRATION_STEPS):
                step = CALIBRATION_STEPS[idx]
                lbl_step_num.config(text=f"Adım {idx + 1} / {len(CALIBRATION_STEPS)}")
                lbl_title.config(text=step["title"])
                lbl_desc.config(text=step["desc"])
            else:
                lbl_step_num.config(text="✔ Kalibrasyon Tamamlandı!", fg=self.COLOR_SUCCESS)
                lbl_title.config(text=f"Tüm {len(CALIBRATION_STEPS)} UYAP Noktası Kaydedildi")
                lbl_desc.config(text="Robot artık tüm pencereleri, butonları, uyarı [Tamam] kutularını ve sorguları sıfır gecikmeyle tanıyacaktır.")
                self.calibration.save(collected)
                self._update_calib_status_label()
                time.sleep(1.2)
                wiz.destroy()

        def on_key_press():
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            idx = current_step_idx[0]
            if idx < len(CALIBRATION_STEPS):
                step = CALIBRATION_STEPS[idx]
                collected[step["key"]] = [pt.x, pt.y]
                try:
                    winsound.MessageBeep(winsound.MB_OK)
                except Exception:
                    pass
                current_step_idx[0] += 1
                update_step_ui()

        def poll_keys():
            VK_SPACE = 0x20
            VK_F2    = 0x71
            while wiz.winfo_exists():
                try:
                    if (user32.GetAsyncKeyState(VK_SPACE) & 0x8000) or (user32.GetAsyncKeyState(VK_F2) & 0x8000):
                        while (user32.GetAsyncKeyState(VK_SPACE) & 0x8000) or (user32.GetAsyncKeyState(VK_F2) & 0x8000):
                            time.sleep(0.05)
                        wiz.after(0, on_key_press)
                except Exception:
                    pass
                time.sleep(0.06)

        t = threading.Thread(target=poll_keys, daemon=True)
        t.start()
        update_step_ui()

    def start_automation(self, start_index=None):
        if not self.loaded_cases:
            messagebox.showwarning("Uyarı", "Lütfen önce bir liste (PDF) yükleyin.")
            return
        if not self.calibration.is_calibrated():
            messagebox.showwarning("Uyarı", "Lütfen önce kalibrasyon sihirbazını tamamlayın.")
            return

        if start_index is None:
            start_index = self.resolve_start_index(self.ent_start_from.get())

        total = len(self.loaded_cases)
        start_index = max(1, min(start_index, total))

        if start_index == 1:
            if self.tree_res.get_children():
                ans = messagebox.askyesno(
                    "Sıfırdan Başlat",
                    "Listeyi 1. sıradan sıfırdan başlatmak üzeresiniz.\n\n"
                    "Ekrandaki mevcut kontrol tablosu temizlensin mi?\n"
                    "(Önceki Excel dosyanız güvendedir ve otomatik olarak yedeklenecektir)"
                )
                if ans:
                    self.results_data = []
                    for r in self.tree_res.get_children():
                        self.tree_res.delete(r)
        else:
            # Belirli bir sıradan veya kaldığı yerden başlanıyor:
            # Ekranda satır yoksa fakat Excel'de önceden tarananlar varsa ekrana yükle
            if not self.tree_res.get_children() and os.path.exists(EXCEL_OUTPUT_PATH):
                self._load_excel_to_treeview()

        self.btn_start.config(state=tk.DISABLED)
        self.btn_resume.config(state=tk.DISABLED)
        self.btn_start_from.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_select_file.config(state=tk.DISABLED)
        self.btn_calib.config(state=tk.DISABLED)
        self.ent_start_from.config(state=tk.DISABLED)
        self.notebook.select(self.tab_results)

        self.worker_thread = threading.Thread(target=lambda: self._run_worker(start_index), daemon=True)
        self.worker_thread.start()

    def _run_worker(self, start_index=1):
        target_case = self.loaded_cases[start_index - 1]
        self.bot.should_stop = False
        self.log(f"▶ Kontrol başlıyor! Başlangıç: Sıra #{start_index} / {len(self.loaded_cases)} (Dosya: {target_case})")

        for i in range(STARTUP_COUNTDOWN, 0, -1):
            if self.bot.should_stop:
                self.log("⏹ Robot başlatılmadan önce iptal edildi.")
                self.after(0, self.stop_automation)
                return
            self.log(f"UYAP ekranına geçin... Başlamaya {i} saniye!")
            self.after(0, lambda s=i: self.lbl_progress.config(
                text=f"⏳ Lütfen UYAP ekranını açın... Başlamaya {s} sn (Başlangıç: Sıra #{start_index} - {target_case})"
            ))
            time.sleep(1.0)

        if self.bot.should_stop:
            self.after(0, self.stop_automation)
            return

        # 1. Önce robot arayüzünü simge durumuna küçült
        self.after(0, self.iconify)
        time.sleep(0.3)
        # 2. Ardından UYAP penceresini öne getir (Antigravity'yi ASLA öne getirmez)
        self.bot.controller.bring_window_to_front()
        time.sleep(0.4)

        if self.bot.should_stop:
            self.after(0, self.stop_automation)
            return

        os.makedirs(BACKUP_DIR, exist_ok=True)

        # 1. OTOMATİK GÜVENLİK YEDEĞİ (ASLA ÜZERİNE YAZIP SİLMEZ)
        if os.path.exists(EXCEL_OUTPUT_PATH):
            try:
                if os.path.getsize(EXCEL_OUTPUT_PATH) > 500:
                    safety_bkp = os.path.join(BACKUP_DIR, f"guvenlik_yedegi_{time.strftime('%Y%m%d_%H%M%S')}.xlsx")
                    import shutil
                    shutil.copy2(EXCEL_OUTPUT_PATH, safety_bkp)
                    self.log(f"🛡 Güvenlik Yedeği Alındı: {os.path.basename(safety_bkp)}")
            except Exception:
                pass

        # 2. ÖNCEKİ KAYITLARI OKU VE KORU (Kaldığı Yerden Ekleyerek Devam Eder)
        existing_records = None
        if os.path.exists(EXCEL_OUTPUT_PATH):
            try:
                df_old = pd.read_excel(EXCEL_OUTPUT_PATH)
                if df_old is not None and len(df_old) > 0 and "Dosya No" in df_old.columns:
                    existing_records = df_old
                    self.log(f"ℹ Mevcut tablodan {len(df_old)} kayıt hafızaya alındı (yeni tarananlar altına eklenecek).")
            except Exception:
                pass

        def row_callback(result_dict, current_idx, total):
            # ARKA PLANDA HER DOSYADA ANINDA VE GÜVENLİ EXCEL GÜNCELLE
            try:
                self.results_data.append(result_dict)
                df_new = pd.DataFrame(self.results_data)
                rename_map = {
                    "dosya_no": "Dosya No",
                    "genel_durum": "Genel Durum (Sonuç)",
                    "cezaevi_durumu": "Cezaevi Durumu",
                    "denetim_durumu": "Denetim Durumu",
                    "detay": "Açıklama / Detay"
                }
                df_new = df_new.rename(columns=rename_map)
                df_new["İşlem Tarihi"] = time.strftime("%Y-%m-%d %H:%M:%S")

                if existing_records is not None and len(existing_records) > 0:
                    combined = pd.concat([existing_records, df_new], ignore_index=True)
                    combined = combined.drop_duplicates(subset=["Dosya No"], keep="last")
                else:
                    combined = df_new

                tmp_p = EXCEL_OUTPUT_PATH + ".tmp"
                combined.to_excel(tmp_p, index=False)
                if os.path.exists(tmp_p):
                    os.replace(tmp_p, EXCEL_OUTPUT_PATH)
            except Exception:
                pass

            def _update():
                tag = "temiz"
                gd = result_dict.get("genel_durum", "")
                if "Cezaevinde" in gd:
                    tag = "cezaevi"
                elif "Denetim" in gd:
                    tag = "denetim"
                elif "Hata" in gd:
                    tag = "hata"

                self.tree_res.insert("", tk.END, values=(
                    current_idx,
                    result_dict.get("dosya_no", "-"),
                    result_dict.get("genel_durum", "-"),
                    result_dict.get("cezaevi_durumu", "-"),
                    result_dict.get("denetim_durumu", "-"),
                    result_dict.get("detay", "-")
                ), tags=(tag,))

                self.progress_bar["value"] = current_idx
                self.lbl_progress.config(text=f"İşleniyor: {current_idx} / {total} (Son: {result_dict.get('dosya_no')})")

            self.after(0, _update)

        def finish_callback(results):
            def _finish():
                self.deiconify()
                self.lift()
                self.btn_start.config(state=tk.NORMAL)
                self.btn_start_from.config(state=tk.NORMAL)
                self.btn_stop.config(state=tk.DISABLED)
                self.btn_select_file.config(state=tk.NORMAL)
                self.btn_calib.config(state=tk.NORMAL)
                self.ent_start_from.config(state=tk.NORMAL)
                self.check_resume_status()
                self.lbl_progress.config(text=f"✔ Tarama Tamamlandı! Bu oturumda {len(results)} dosya işlendi.")
                messagebox.showinfo("Başarılı", f"Dosyalar başarıyla kontrol edildi ve masaüstüne kaydedildi:\n\n{EXCEL_OUTPUT_PATH}")
            self.after(0, _finish)

        self.bot.run_batch(
            self.loaded_cases,
            row_callback=row_callback,
            log_callback=self.log,
            finish_callback=finish_callback,
            start_index=start_index
        )

    def stop_automation(self):
        self.bot.stop()
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_start.config(state=tk.NORMAL)
        self.btn_start_from.config(state=tk.NORMAL)
        self.btn_select_file.config(state=tk.NORMAL)
        self.btn_calib.config(state=tk.NORMAL)
        self.ent_start_from.config(state=tk.NORMAL)
        self.check_resume_status()
        self.deiconify()
        self.lift()
        self.lbl_progress.config(text="⏸ Robot kullanıcı tarafından duraklatıldı.")
        self.log("⏸ Robot durduruldu.")

    def _start_hotkey_listener(self):
        """Win32 API ile arka planda ESC tuşunu ve Mouse Failsafe'i denetler."""
        def _listen():
            VK_ESCAPE = 0x1B
            while True:
                try:
                    esc_down = bool(user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
                    pt = wintypes.POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    mouse_failsafe = (pt.x <= 15 and pt.y <= 15)

                    if esc_down or mouse_failsafe:
                        if self.bot:
                            self.bot.stop()
                        self.after(0, self._handle_esc_press)
                        while bool(user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000):
                            time.sleep(0.04)
                except Exception:
                    pass
                time.sleep(0.05)

        t = threading.Thread(target=_listen, daemon=True)
        t.start()

    def _handle_esc_press(self):
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass
        self.deiconify()
        self.lift()
        self.stop_automation()

if __name__ == "__main__":
    app = TahliyeApp()
    app.mainloop()

