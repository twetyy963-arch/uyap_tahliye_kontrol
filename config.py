# -*- coding: utf-8 -*-
"""
UYAP Tahliye Bekleyen Para Cezası ve Denetim Kontrol Robotu
Yapılandırma Dosyası
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = BASE_DIR

# Kullanıcı Masaüstü Yolu
USER_DESKTOP = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Administrator"), "Desktop")

# Referans Görsel Klasörü (Kullanıcının masaüstündeki ekran görüntüleri klasörü)
DEFAULT_IMAGE_DIR = os.path.join(USER_DESKTOP, "tahliye bekleyen para")

# Kalibrasyon ve Durum Dosyaları
CALIBRATION_FILE = os.path.join(BASE_DIR, "kalibrasyon.json")
STATE_FILE = os.path.join(BASE_DIR, "son_durum.json")
SAVED_CASES_FILE = os.path.join(BASE_DIR, "kayitli_dosya_listesi.json")

# Çıktı Excel Dosyası (Masaüstü)
EXCEL_OUTPUT_PATH = os.path.join(USER_DESKTOP, "tahliye_denetim_kontrol_GUNCEL.xlsx")
BACKUP_DIR = os.path.join(USER_DESKTOP, "tahliye_yedekler")

# Kalibrasyon Adımları Tanımı (Tam 13 Adım)
CALIBRATION_STEPS = [
    # ─── 1. BÖLÜM: EVRAK HAZIRLAMA (CEZAEVİ KONTROLÜ) ───
    {
        "key": "btn_evrak_hazirlama",
        "title": "1. 'Evrak Hazırlama' Butonu",
        "desc": "UYAP ana ekranında Evrak Hazırlama'yı açan butonu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "txt_dosya_no_1",
        "title": "2. Dosya No Giriş Kutusu (Evrak Hazırlama)",
        "desc": "Evrak Hazırlama ekranındaki 'Dosya No' / 'İlamat No' kutucuğunu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "btn_sorgula_1",
        "title": "3. 'Sorgula' Butonu (Evrak Hazırlama)",
        "desc": "Evrak Hazırlama ekranındaki 'Sorgula' / 'Bul' butonunu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "btn_sorgu_onay_1",
        "title": "4. Sorgudan Sonraki İlk 'Tamam' Butonu (Evrak Hazırlama)",
        "desc": "Sorgula butonuna bastıktan sonra sorguyu onaylayan 'Tamam' butonunu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "btn_cezaevi_uyari_tamam",
        "title": "5. Cezaevi Uyarısı 'Tamam' Butonu",
        "desc": "Ekrana 'Sanık Ceza İnfaz Kurumunda Bulunmaktadır' uyarı kutusu geldiğinde, kutunun içindeki [Tamam] butonunu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "btn_kapat_1",
        "title": "6. 'Kapat' Butonu (Evrak Hazırlama)",
        "desc": "Evrak Hazırlama ekranının sağ altındaki [Kapat] butonunu gösterip [Boşluk] tuşuna basın."
    },

    # ─── 2. BÖLÜM: 105/A DENETİM SORGUSU ───
    {
        "key": "btn_denetim_sorgu",
        "title": "7. '105/A Denetim Sorgusu' Butonu",
        "desc": "UYAP ekranında 105/A Denetim ekranını (KLN_CEZA_DS) açan butonu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "txt_dosya_no_2",
        "title": "8. Dosya No Giriş Kutusu (Denetim Sorgusu)",
        "desc": "Denetim ekranındaki 'Dosya No' / 'İlamat No' kutucuğunu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "btn_sorgula_2",
        "title": "9. 'Sorgula' Butonu (Denetim Sorgusu)",
        "desc": "Denetim ekranındaki 'Sorgula' butonunu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "btn_sorgu_onay_2",
        "title": "10. Sorgudan Sonraki İlk 'Tamam' Butonu (Denetim Sorgusu)",
        "desc": "Denetim sorgula butonuna bastıktan sonra sorguyu onaylayan 'Tamam' butonunu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "btn_denetim_uyari_tamam",
        "title": "11. Denetim Uyarısı 'Tamam' Butonu",
        "desc": "Ekrana 'Bu Kişiye Ait Başka Denetimli Serbestlik Dosyası Bulunamadı' uyarı kutusu geldiğinde, içindeki [Tamam] butonunu gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "area_denetim_tablo",
        "title": "12. Denetim Tablosu İlk Satır Alanı",
        "desc": "Uyarı çıkmadığında hükümlünün listelendiği denetim tablosunun ilk satırının ortasını gösterip [Boşluk] tuşuna basın."
    },
    {
        "key": "btn_kapat_2",
        "title": "13. 'Kapat' Butonu (Denetim Sorgusu)",
        "desc": "Denetim penceresinin sağ altındaki [Kapat] butonunu gösterip [Boşluk] tuşuna basın."
    }
]

# Bekleme Süreleri (UYAP Arayüzü ile Tam Uyumlu ve Kararlı)
DELAYS = {
    "yazma_sonrasi": 0.15,
    "sorgu_sonrasi": 0.35,
    "pencere_acilis": 0.55,
    "kapatma_sonrasi": 0.25,
}

# Başlangıç Geri Sayımı (Kullanıcının UYAP ekranına geçmesi için saniye)
STARTUP_COUNTDOWN = 3
