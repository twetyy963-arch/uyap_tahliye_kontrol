# UYAP Tahliye Bekleyen Para Cezası & 105/A Denetim Kontrol Robotu

Bu program; UYAP ortamında tahliye bekleyen para cezası ilam dosyalarını otomatik olarak tarayan, hükümlünün **Cezaevinde mi** olduğunu, **105/A Denetiminde Dosyası mı** olduğunu veya **Her İkisinde de Kaydının Olup Olmadığını** tespit edip canlı bir Excel raporu haline getiren güvenli bir **RPA (Robotik Süreç Otomasyonu)** programıdır.

---

## 🔒 Güvenlik & Zırhlı Kayıt Özellikleri

1. **Asla Üzerine Yazmama Garantisi:**  
   Program durdurulup yeniden başlatılsa bile masaüstündeki mevcut `tahliye_denetim_kontrol_GUNCEL.xlsx` tablosundaki kayıtları korur ve yeni taranan dosyaları listenin altına ekler (`merge`).
2. **Otomatik Güvenlik Yedeği:**  
   Program her başladığında mevcut Excel tablosunun silinmez bir kopyasını `tahliye_yedekler/` klasörüne zaman damgalı olarak kaydeder.
3. **Anında Excel Güncelleme:**  
   Taranan her dosya anında (arka planda) masaüstündeki Excel dosyasına satır satır yazılır; program aniden kapansa dahi tek bir dosya bile kaybolmaz.
4. **Acil Durdurma (ESC & Mouse Failsafe):**  
   Klavyeden **ESC** tuşuna basarak veya farenizi **ekranın en sol-üst köşesine (0,0)** çekerek robotu o salisede duraklatabilirsiniz.

---

## 🚀 Nasıl Kullanılır?

1. **Başlatma:**  
   Klasördeki **`baslat.vbs`** (veya `baslat.bat`) dosyasına çift tıklayarak programı açın.

2. **Liste Yükleme:**  
   * **"📁 PDF / Liste Dosyası Seç"** butonuna basarak dosya listenizi içeren PDF belgesini seçin.
   * Dosyalar otomatik ayrıştırılacak ve önizleme sekmesinde listelenecektir.

3. **🎯 Kalibrasyon Sihirbazı (Sadece İlk Seferde):**  
   * UYAP ekranını açın.
   * Mor renkli **"🎯 Ekranda Yerleri Göster (Kalibrasyon Sihirbazı)"** butonuna basın.
   * Sırasıyla şu 11 noktayı farenizle gösterip **[Boşluk]** veya **[F2]** tuşuna basarak kaydedin:
     1. Evrak Hazırlama Butonu
     2. Evrak Hazırlama Dosya No Kutusu
     3. Evrak Hazırlama Sorgula Butonu
     4. Evrak Hazırlama Sonuç / Tamam Butonu
     5. Evrak Hazırlama Kapat Butonu
     6. 105/A Denetim Sorgusu Butonu / Menüsü
     7. Denetim Dosya No Kutusu
     8. Denetim Sorgula Butonu
     9. Denetim Sonuç / Tamam Butonu
     10. Denetim Tablo / Liste Bölgesi
     11. Denetim Kapat Butonu

4. **Kontrolü Başlatma:**  
   * Yeşil renkli **"▶ Kontrolü Başlat"** butonuna basın.
   * 8 saniyelik geri sayım boyunca UYAP ekranını öne getirin.
   * Robot her dosyayı sırayla inceleyecek, cezaevi uyarısı varsa tespit edip kapatacak, yoksa denetim ekranını sorgulayacak ve sonuçları masaüstündeki Excel tablosuna anında kaydedecektir.

