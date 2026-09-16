# ADR-0002: PDF doğrudan gönderilir, PNG dönüşümü yok

Durum: kabul edildi · Tarih: 2026-09-16 · İlgili faz: Faz 2

## Bağlam ve problem

Maskelenmiş ekstre Gemini'ye hangi formatta gitmeli? PNG'ye çevirmek "metin katmanında sızıntı kalmaz" hissi verir ama maliyet ve doğruluk etkisi var.

## Değerlendirilen seçenekler

- PDF'i olduğu gibi (inline base64) gönder
- Her sayfayı PNG'ye çevirip görsel olarak gönder
- Sadece metin çıkarıp (PyMuPDF `get_text`) düz metin gönder

## Karar

"PDF doğrudan", çünkü:

- Gemini PDF'i native alır: sayfa başına 258 görsel token + gömülü metin katmanı **ücretsiz**. PNG'de metin katmanı kaybolur, model OCR yapmak zorunda kalır, doğruluk düşer.
- Redaction PyMuPDF'te uygulandığında metin katmanından da silinir (ADR-0003); PNG'ye çevirmenin sızıntı açısından ek faydası yok.
- Düz metin seçeneği tablo yapısını kaybeder; sütun hizası kategori ve tutar doğruluğu için önemli.

Uygulama kuralları:

- Inline gönderim: `{"type":"document","data":b64,"mime_type":"application/pdf"}`.
- Sınırlar: toplam istek 100 MB (üstünde Files API), PDF 50 MB / 1000 sayfa. Uygulama zaten 15 MB / 60 sayfa ile sınırlıyor, Files API v1'de gerekmez.
- 15 sayfadan uzun ekstreler 10'ar sayfalık alt PDF'lere bölünür; ilk sayfa (başlık ve sütun bağlamı) her parçaya eklenir.
- PNG yalnızca frontend önizlemesi için üretilir (`get_pixmap(dpi=100)`), Gemini'ye gitmez.

## Sonuçlar

- İyi: En düşük token maliyeti, en yüksek tablo doğruluğu, tek kod yolu.
- Kötü: Taranmış (görüntü) ekstreler için metin katmanı yok; v1'de reddedilir. `media_resolution` ayarı ile görsel token maliyeti düşürülebilir ama okunabilirlik test edilmeli.
- Doğrulama tarihi ve kaynak: 2026-09-16, https://ai.google.dev/gemini-api/docs/document-processing , https://ai.google.dev/gemini-api/docs/files
