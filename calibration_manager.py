# -*- coding: utf-8 -*-
"""
UYAP Tahliye Kontrol Robotu - Kalibrasyon Yöneticisi
Kullanıcının ekranda bir kez gösterdiği koordinatları kalibrasyon.json dosyasına kaydeder.
Eski ve yeni koordinat anahtarları arasında tam geriye dönük uyumluluk sağlar.
"""
import os
import json
from config import CALIBRATION_FILE, CALIBRATION_STEPS

# Eski ve yeni kalibrasyon anahtarları eşleştirme tablosu (Geriye dönük uyumluluk)
FALLBACK_MAP = {
    "btn_sorgu_onay_1": "btn_tamam_1",
    "btn_cezaevi_uyari_tamam": "btn_tamam_1",
    "btn_sorgu_onay_2": "btn_tamam_2",
    "btn_denetim_uyari_tamam": "btn_tamam_2",
}

class CalibrationManager:
    def __init__(self, filepath=CALIBRATION_FILE):
        self.filepath = filepath
        self.coordinates = {}
        self.load()

    def load(self):
        """Kayıtlı koordinatları dosyadan yükler."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.coordinates = json.load(f)
            except Exception:
                self.coordinates = {}
        return self.coordinates

    def get(self, key, default=None):
        """Koordinatı döner; bulunamazsa geriye dönük uyumlu anahtara bakar."""
        if key in self.coordinates:
            return self.coordinates[key]
        fallback_key = FALLBACK_MAP.get(key)
        if fallback_key and fallback_key in self.coordinates:
            return self.coordinates[fallback_key]
        return default

    def save(self, coords=None):
        """Koordinatları JSON dosyasına kaydeder."""
        if coords is not None:
            self.coordinates = coords
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.coordinates, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def is_calibrated(self):
        """Tüm gerekli koordinatların kaydedilip kaydedilmediğini denetler."""
        if not self.coordinates:
            return False
        # 13 adımın hepsi veya eski 11 adım kayıtlıysa geçerli say
        all_13 = all(step["key"] in self.coordinates for step in CALIBRATION_STEPS)
        if all_13:
            return True
        legacy_keys = [
            "btn_evrak_hazirlama", "txt_dosya_no_1", "btn_sorgula_1", "btn_tamam_1", "btn_kapat_1",
            "btn_denetim_sorgu", "txt_dosya_no_2", "btn_sorgula_2", "btn_tamam_2",
            "area_denetim_tablo", "btn_kapat_2"
        ]
        return all(k in self.coordinates for k in legacy_keys)

    def get_missing_steps(self):
        """Eksik kalan kalibrasyon adımlarını listeler."""
        missing = []
        for step in CALIBRATION_STEPS:
            k = step["key"]
            if k not in self.coordinates and FALLBACK_MAP.get(k) not in self.coordinates:
                missing.append(step)
        return missing


