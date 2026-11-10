# -*- coding: utf-8 -*-
"""
UYAP Tahliye ve Denetim Kontrol Robotu - Cekirdek Islem Motoru
Kullanici Kurali: 
- 1. Asama (Evrak Hazirlama): Cezaevi uyarisi cikarsa -> CEZAEVINDE! Denetime girilmez.
- 2. Asama (105/A Denetim): 11 haneli T.C. Kimlik No cikiyorsa -> DENETIMI VAR! Cikmiyorsa -> DENETIMI YOK!
"""
import time
import re
import ctypes
from PIL import Image
from config import DELAYS, DEFAULT_IMAGE_DIR
from calibration_manager import CalibrationManager
from screen_control import ScreenController
from ocr_engine import OcrEngine

user32 = ctypes.windll.user32

class TahliyeBot:
    def __init__(self, image_dir=DEFAULT_IMAGE_DIR, ocr_engine=None):
        self.image_dir = image_dir
        self.controller = ScreenController()
        self.calibration = CalibrationManager()
        self.ocr = ocr_engine or OcrEngine()
        self.is_running = False
        self.should_stop = False

    def log(self, msg, callback=None):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line)
        if callback:
            callback(line)

    def stop(self):
        """Robotu aninda durdurur."""
        self.should_stop = True

    def check_stop(self):
        """Robot durduruldu mu veya kullanici ESC tusuna basti mi kontrol eder."""
        if self.should_stop or self.controller.check_emergency_stop():
            self.should_stop = True
            return True
        return False

    def click_button_safely(self, coord, name="Buton", log_callback=None):
        """Belirtilen koordinata tiklar ve stabil bekleme uygular."""
        if self.check_stop():
            return
        if coord and len(coord) == 2:
            self.controller.click(coord[0], coord[1], delay=0.08)
            time.sleep(0.08)

    def is_dialog_visible_on_screen(self, screen_img=None):
        """Ekranda acik bir modal uyari kutusu (Dikkat!, Uyari vb.) olup olmadigini kontrol eder."""
        if screen_img is None:
            screen_img = self.controller.grab_screen()
        w, h = screen_img.size
        crop_box = (int(w * 0.25), int(h * 0.20), int(w * 0.75), int(h * 0.75))
        cropped = screen_img.crop(crop_box)
        ocr_res = self.ocr.recognize_pil_image(cropped, upscale=True)
        raw = ocr_res.get("text", "")
        norm = self.ocr.normalize_text(raw)
        dialog_signals = ["dikkat", "uyari", "uyam", "olkx", "bulunamadi", "bulunm", "kisiye ait", "deneli", "baska", "serbestlik", "kurumu"]
        has_dialog = any(k in norm for k in dialog_signals)
        return has_dialog, raw, norm

    def dismiss_warning_popup(self, uyari_tamam_coord=None, log_callback=None):
        """
        Ekranda acilan uyari kutusunun [Tamam] butonuna basar.
        Kullanicinin gosterdigi koordinata tiklar ve donanim kodlu Enter/Bosluk gonderir.
        Kutu kapanana kadar dogrulamali dener.
        """
        self.controller.bring_window_to_front()
        for attempt in range(3):
            try:
                if uyari_tamam_coord and len(uyari_tamam_coord) == 2:
                    if attempt == 0:
                        self.log(f"Uyarinin [Tamam] butonuna tiklaniyor: ({uyari_tamam_coord[0]}, {uyari_tamam_coord[1]})", log_callback)
                    self.controller.click(uyari_tamam_coord[0], uyari_tamam_coord[1], delay=0.08)
                    time.sleep(0.1)

                self.controller.press_enter()
                time.sleep(0.08)
                self.controller.press_space()
                time.sleep(0.15)

                has_dialog, _, _ = self.is_dialog_visible_on_screen()
                if not has_dialog:
                    break
            except Exception:
                pass

    def wait_for_cezaevi_screen_reaction(self, timeout=2.5, log_callback=None):
        """
        Evrak Hazirlama ekraninda gercek bir cezaevi uyarisi cikip cikmadigini kontrol eder.
        Ekranin basligindaki statik 'Ceza Infaz Kurumu' yazilarini ASLA dikkate almaz.
        Yalnizca ekranin ortasinda acilan modal uyari kutusunu ('... Kurumunda Bulunmaktadir') inceler.
        """
        start_t = time.time()
        last_raw = ""
        last_norm = ""

        # Kullanıcının Kuralı: "Şu An ... Bulunmaktadır" (Çocuk Eğitimevi, Açık/Kapalı Cezaevi vb. tüm kurumlar)
        incarceration_signals = ["bulunmaktadir", "barindirilmaktadir"]
        context_signals = ["su an", "sanik", "kurum", "kutum", "egitim", "egitimevi", "ceza", "infaz", "kapali", "acik", "tipi"]
        negative_signals = [
            "bulunmamaktadir", "bulunmamakta", "bulunamadi", "bulunamamaktadir",
            "kayit yok", "kaydi yok", "tespit edilemedi"
        ]

        while time.time() - start_t < timeout:
            if self.check_stop():
                break
            screen = self.controller.grab_screen()
            w, h = screen.size
            # YALNIZCA EKRANIN ORTASINDAKI MODAL DIYALOG BOLGESINI KIRP (Statik basliklari eler)
            center_crop = screen.crop((int(w * 0.20), int(h * 0.20), int(w * 0.80), int(h * 0.70)))
            ocr_res = self.ocr.recognize_pil_image(center_crop, upscale=True)
            last_raw = ocr_res.get("text", "")
            last_norm = self.ocr.normalize_text(last_raw)

            # "Şu An ... Bulunmaktadır / Barındırılmaktadır" kontrolü
            has_incarc = any(k in last_norm for k in incarceration_signals)
            has_context = any(k in last_norm for k in context_signals)
            has_neg = any(k in last_norm for k in negative_signals)

            is_cezaevi = (has_incarc and has_context and not has_neg)

            if is_cezaevi:
                # Gercek kurum / egitimevi uyarisi belirdi!
                return True, last_raw, last_norm

            if has_neg:
                # 'Bulunmamaktadir' veya baska negatif uyari ciktiysa kurumda degildir
                return False, last_raw, last_norm

            time.sleep(0.15)

        return False, last_raw, last_norm

    def wait_for_denetim_screen_reaction(self, timeout=3.0, log_callback=None):
        """
        Denetim ekraninda kullanici kuralini uygular:
        - 11 haneli T.C. Kimlik No cikiyorsa -> TABLE (Denetimi Var)
        - Uyari kutusu cikiyorsa -> POPUP (Denetimi Yok)
        """
        popup_keys = ["dikkat", "olkx", "baska", "bulunamadi", "bulunm", "bulunmamaktadir", "kisiye ait", "serheydik", "deneli"]

        start_t = time.time()
        last_raw = ""
        last_norm = ""
        last_screen = None

        while time.time() - start_t < timeout:
            if self.check_stop():
                break
            last_screen = self.controller.grab_screen()
            ocr_res = self.ocr.recognize_pil_image(last_screen, upscale=True)
            last_raw = ocr_res.get("text", "")
            last_norm = self.ocr.normalize_text(last_raw)

            # 1. KURAL: 11 Haneli TC Kimlik Numarasi cikti mi?
            tc_match = re.findall(r'\b\d{11}\b', last_raw)
            if tc_match:
                return "TABLE", last_raw, last_norm, tc_match

            # 2. KURAL: Uyari kutusu cikti mi?
            has_popup = any(k in last_norm for k in popup_keys)
            if not has_popup:
                w, h = last_screen.size
                center_crop = last_screen.crop((int(w * 0.25), int(h * 0.25), int(w * 0.75), int(h * 0.70)))
                crop_res = self.ocr.recognize_pil_image(center_crop, upscale=True)
                crop_norm = self.ocr.normalize_text(crop_res.get("text", ""))
                has_popup = any(k in crop_norm for k in popup_keys)

            if has_popup:
                return "POPUP", last_raw, last_norm, []

            time.sleep(0.15)

        tc_match = re.findall(r'\b\d{11}\b', last_raw)
        if tc_match:
            return "TABLE", last_raw, last_norm, tc_match
        return "EMPTY", last_raw, last_norm, []

    def process_single_case(self, case_no, log_callback=None):
        """Tek bir dosya icin iki asamali kontrolu gerceklestirir."""
        result = {
            "dosya_no": case_no,
            "genel_durum": "Kaydı Yok (Cezaevi ve Denetimde Yok)",
            "cezaevi_durumu": "Yok",
            "denetim_durumu": "-",
            "detay": ""
        }

        self.log(f"══════════ Dosya İşleniyor: {case_no} ══════════", log_callback)

        try:
            self.controller.bring_window_to_front()

            # =========================================================
            # 1. ASAMA: CEZAEVI KONTROLU (EVRAK HAZIRLAMA EKRANI)
            # =========================================================
            self.log(f"▶ [1. Aşama] {case_no} Cezaevi sorgusu için 'Evrak Hazırlama' açılıyor...", log_callback)

            # 1.1 Evrak Hazirlama Butonu
            if self.check_stop(): return result
            c_evrak = self.calibration.get("btn_evrak_hazirlama")
            self.click_button_safely(c_evrak, "Evrak Hazırlama", log_callback)
            time.sleep(DELAYS["pencere_acilis"])

            if self.check_stop(): return result

            # 1.2 Dosya No Kutusuna Yazma
            c_dosya1 = self.calibration.get("txt_dosya_no_1")
            self.log(f"Dosya No yazılıyor: '{case_no}'", log_callback)
            self.controller.clear_and_type(c_dosya1[0], c_dosya1[1], case_no)
            time.sleep(DELAYS["yazma_sonrasi"])

            if self.check_stop(): return result

            # 1.3 Sorgula Butonu
            c_sorgula1 = self.calibration.get("btn_sorgula_1")
            self.log("'Sorgula' butonuna basılıyor...", log_callback)
            self.click_button_safely(c_sorgula1, "Sorgula 1", log_callback)
            time.sleep(0.25)

            if self.check_stop(): return result

            # 1.4 Sorgudan Sonraki Ilk 'Tamam' Butonu (Onay)
            c_onay1 = self.calibration.get("btn_sorgu_onay_1")
            if c_onay1:
                self.log("Sorgudan sonraki ilk 'Tamam' (Onay) butonuna basılıyor...", log_callback)
                self.click_button_safely(c_onay1, "Sorgu Onay 1", log_callback)
                self.controller.press_enter()

            if self.check_stop(): return result

            # 1.5 Ekran Tepkisini Bekle
            is_cezaevi, raw_text1, norm1 = self.wait_for_cezaevi_screen_reaction(timeout=2.2, log_callback=log_callback)
            if self.check_stop(): return result

            # Cezaevi uyarisi varsa [Tamam]'a bas
            c_cezaevi_tamam = self.calibration.get("btn_cezaevi_uyari_tamam")
            if is_cezaevi:
                self.log("Cezaevi uyarısı algılandı, uyarının içindeki [Tamam] butonuna basılıyor...", log_callback)
                self.dismiss_warning_popup(uyari_tamam_coord=c_cezaevi_tamam, log_callback=log_callback)
            elif "uyari" in norm1 or "uyam" in norm1 or "dikkat" in norm1:
                # Cezaevi disinda genel bir bilgi/uyari kutusu ciktiysa da kapat
                self.dismiss_warning_popup(uyari_tamam_coord=c_cezaevi_tamam, log_callback=log_callback)

            # 1.6 Evrak Hazirlama Penceresini Kapat
            c_kapat1 = self.calibration.get("btn_kapat_1")
            self.click_button_safely(c_kapat1, "Evrak Hazırlama Kapat", log_callback)
            time.sleep(DELAYS["kapatma_sonrasi"])

            # EGER SANIK CEZAEVINDE / EGITIMEVI'NDE ISE:
            if is_cezaevi:
                result["genel_durum"] = "Cezaevinde"
                result["cezaevi_durumu"] = "Cezaevinde"
                result["denetim_durumu"] = "-"

                detay = "Şu An Kurumda / Eğitimevinde Bulunmaktadır"
                clean_detay = raw_text1.replace("\n", " ").strip()
                dosya_match = re.search(r'\b(19\d{2}|20\d{2})/\d+\b', clean_detay)
                su_an_match = re.search(r'(?:şu\s*an|sanık,?\s*şu\s*an)\s*(.+?)(?:bulunmaktadır|barındırılmaktadır)', clean_detay, re.IGNORECASE)

                if su_an_match:
                    extracted = su_an_match.group(1).strip(" .,:;-")
                    detay = f"Şu An {extracted} Bulunmaktadır"
                elif " ile " in clean_detay.lower():
                    idx_ile = clean_detay.lower().find(" ile ")
                    detay = clean_detay[idx_ile + 5:].strip()
                elif "sanık," in clean_detay.lower():
                    idx_s = clean_detay.lower().find("sanık,")
                    detay = clean_detay[idx_s + 6:].strip()

                if dosya_match and dosya_match.group(0) not in detay:
                    detay = f"{detay} ({dosya_match.group(0)})"

                result["detay"] = detay[:140]
                self.log(f"🚨 SONUÇ: {case_no} -> CEZAEVİNDE / EĞİTİMEVİNDE! ({result['detay']})", log_callback)
                # KESIN KURAL: CEZAEVINDE OLDUGU ICIN DENETIME ASLA GIRILMEZ!
                return result

            # Sanik cezaevinde DEGIL -> 2. ASAMA: 105/A DENETIM
            self.log(f"ℹ {case_no} Ceza infaz kurumunda bulunmamaktadır. 105/A Denetime geçiliyor...", log_callback)

            if self.should_stop: return result

            # =========================================================
            # 2. ASAMA: 105/A MADDESI DENETIM SORGUSU (KLN_CEZA_DS)
            # =========================================================
            self.log("▶ [2. Aşama] '105/A Maddesi Denetim Sorgusu' açılıyor...", log_callback)

            # 2.1 Denetim Menu / Buton
            if self.check_stop(): return result
            c_denetim = self.calibration.get("btn_denetim_sorgu")
            self.click_button_safely(c_denetim, "Denetim Menü", log_callback)
            time.sleep(DELAYS["pencere_acilis"])

            if self.check_stop(): return result

            # 2.2 Denetim Dosya No Kutusu
            c_dosya2 = self.calibration.get("txt_dosya_no_2")
            self.log(f"Denetim ekranına dosya no yazılıyor: '{case_no}'", log_callback)
            self.controller.clear_and_type(c_dosya2[0], c_dosya2[1], case_no)
            time.sleep(DELAYS["yazma_sonrasi"])

            if self.check_stop(): return result

            # 2.3 Denetim Sorgula Butonu
            c_sorgula2 = self.calibration.get("btn_sorgula_2")
            self.log("Denetim 'Sorgula' butonuna basılıyor...", log_callback)
            self.click_button_safely(c_sorgula2, "Sorgula 2", log_callback)
            time.sleep(0.25)

            if self.check_stop(): return result

            # 2.4 Denetim Sorgudan Sonraki Ilk 'Tamam' Butonu (Onay)
            c_onay2 = self.calibration.get("btn_sorgu_onay_2")
            if c_onay2:
                self.log("Denetim sorgusundan sonraki ilk 'Tamam' (Onay) butonuna basılıyor...", log_callback)
                self.click_button_safely(c_onay2, "Sorgu Onay 2", log_callback)
                self.controller.press_enter()

            if self.check_stop(): return result

            # 2.5 Ekran Tepkisini Bekle
            reaction, raw_text2, norm2, tc_list = self.wait_for_denetim_screen_reaction(timeout=2.8, log_callback=log_callback)
            if self.check_stop(): return result

            # KULLANICININ KESIN KURALI:
            # 11 haneli TC numarasi cikiyorsa -> DENETIMI VAR
            # Cikmiyorsa -> DENETIMI YOK
            if len(tc_list) > 0:
                has_denetim_record = True
                tc_info = f" (TC: {tc_list[0]})"
                ds_detay = f"Denetim Dosyası Mevcut{tc_info} (Tabloda Listeli)"
                self.log(f"✔ 11 haneli T.C. Kimlik No tespit edildi! -> DENETİMDE DOSYASI VAR!{tc_info}", log_callback)
            else:
                has_denetim_record = False
                ds_detay = "Temiz (Denetim Dosyası Bulunamadı)"
                self.log("✔ 11 haneli T.C. Kimlik No yok -> DENETİM DOSYASI YOK (TEMİZ)", log_callback)

                # Eger ekranda uyari kutusu acildiysa uyarinin [Tamam]'ina bas
                c_denetim_tamam = self.calibration.get("btn_denetim_uyari_tamam")
                self.dismiss_warning_popup(uyari_tamam_coord=c_denetim_tamam, log_callback=log_callback)

            # 2.6 Denetim Penceresini Kapat
            c_kapat2 = self.calibration.get("btn_kapat_2")
            self.click_button_safely(c_kapat2, "Denetim Kapat", log_callback)
            time.sleep(DELAYS["kapatma_sonrasi"])

            if has_denetim_record:
                result["genel_durum"] = "Denetimde Dosyası Var"
                result["denetim_durumu"] = "Denetimde Var"
                result["detay"] = ds_detay
                self.log(f"✔ SONUÇ: {case_no} -> DENETİMDE DOSYASI VAR! ({result['detay']})", log_callback)
            else:
                result["genel_durum"] = "Kaydı Yok (Cezaevi ve Denetimde Yok)"
                result["denetim_durumu"] = "Kayıt Yok"
                result["detay"] = "Temiz (Her İkisinde de Yok)"
                self.log(f"✔ SONUÇ: {case_no} -> HER İKİSİNDE DE KAYIT YOK (Temiz)", log_callback)

        except Exception as e:
            self.log(f"⚠ {case_no} dosyasında hata oluştu: {e}", log_callback)
            try:
                self.controller.press_esc()
                time.sleep(0.2)
                self.controller.press_esc()
            except Exception:
                pass
            result["genel_durum"] = "Hata / Kontrol Edilemedi"
            result["detay"] = str(e)[:40]

        return result

    def run_batch(self, case_list, row_callback=None, log_callback=None, finish_callback=None, start_index=1):
        """Tum dosya listesini sirayla isler."""
        self.is_running = True
        self.should_stop = False
        self.controller.prevent_sleep(True)
        all_results = []

        total = len(case_list)
        if total == 0:
            self.log("⚠ İşlenecek dosya listesi boş!", log_callback)
            self.is_running = False
            return []

        start_idx = max(1, min(start_index, total))
        sub_list = case_list[start_idx - 1:]

        self.log(f"İşlem başlatılıyor: Sıra #{start_idx} / {total} (Kalan {len(sub_list)} dosya kontrol edilecek)", log_callback)

        for idx, case_no in enumerate(sub_list, start=start_idx):
            if self.check_stop():
                self.log(f"⏹ Robot kullanıcı tarafından durduruldu! (Son işlenen sıra: #{idx}, Dosya: {case_no})", log_callback)
                break

            res = self.process_single_case(case_no, log_callback)
            all_results.append(res)

            if row_callback:
                row_callback(res, idx, total)

            time.sleep(0.15)

        self.is_running = False
        self.controller.prevent_sleep(False)
        self.log(f"İşlemler sonlandırıldı. (Bu turda toplam {len(all_results)} dosya işlendi)", log_callback)

        if finish_callback:
            finish_callback(all_results)

        return all_results
