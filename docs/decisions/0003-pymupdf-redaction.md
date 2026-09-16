# ADR-0003: Maskeleme için PyMuPDF redaction annotation

Durum: kabul edildi · Tarih: 2026-09-16 · İlgili faz: Faz 1

## Bağlam ve problem

Kişisel veriler PDF'ten geri alınamaz şekilde silinmeli; siyah kutu çizmek yetmez, metin katmanından da kalkmalı. Layout ve tablo yapısı korunmalı.

## Değerlendirilen seçenekler

- PyMuPDF redaction annotation (`add_redact_annot` + `apply_redactions`)
- pdfplumber / pypdf ile metin bul, üstüne dikdörtgen çiz (metin katmanı kalır, sızıntı)
- PDF'i yeniden oluştur (metin çıkar, maskele, reportlab ile yeni PDF üret; layout kaybı)

## Karar

"PyMuPDF redaction", çünkü `apply_redactions` metni içerik akışından fiziksel olarak kaldırır, kaydedildikten sonra geri alınamaz, görsel ve vektör çizimler korunabilir.

Uygulama kuralları:

- Açma: `pymupdf.open(stream=bytes, filetype="pdf")`; `doc.needs_pass` ise `doc.authenticate(pwd)`.
- Konum tespiti `get_text("rawdict")` karakter bbox'larından; regex satır metni üzerinde çalışır, eşleşen karakter aralığının bbox'ları birleştirilir. `search_for` regex desteklemediği için kullanılmaz.
- Silme kuralı: karakter bbox'ı redaction dikdörtgeni ile **herhangi bir kesişim** yaparsa silinir. Bu yüzden dikdörtgen `padding_pt` kadar daraltılır ve `pymupdf.TOOLS.set_small_glyph_heights(True)` açılır (kapalıyken 12 pt satır aralığında komşu satırlar da silinir; 1.28.2'de doğrulandı).
- Sayfa başına tek `apply_redactions(images=PDF_REDACT_IMAGE_NONE, graphics=PDF_REDACT_LINE_ART_NONE, text=PDF_REDACT_TEXT_REMOVE)`.
- Temizlik: `doc.scrub(metadata=True, xml_metadata=True, javascript=True, embedded_files=True, attached_files=True, hidden_text=True, redactions=False)`; redaction'lar zaten uygulanmış olduğu için `redactions=False`.
- Çıktı: `doc.tobytes(garbage=3, deflate=True)`.

## Sonuçlar

- İyi: Geri alınamaz silme, layout korunur, tek kütüphane, abi3 wheel (Python 3.10–3.14), musl x86_64 wheel mevcut.
- Kötü: Kesişim kuralı komşu karakterleri silebilir; sızıntı testi ve görsel test zorunlu. Taranmış PDF'lerde metin katmanı olmadığı için işe yaramaz (v1'de reddedilir). PyMuPDF AGPL lisanslı; ticari kullanımda lisans değerlendirmesi gerekir [NETLEŞTİRİLMELİ: kapalı beta sonrası ticari lisans ihtiyacı].
- Doğrulama tarihi ve kaynak: 2026-09-16, https://pymupdf.readthedocs.io/en/latest/page.html , https://pymupdf.readthedocs.io/en/latest/document.html
