# Mimari Karar Kayıtları (ADR)

Şablon: [../templates/adr-template.md](../templates/adr-template.md). Numaralar sıralı, silinmez; geçersiz olan karar "yerini aldı" durumuna çekilir ve yeni ADR açılır.

| No | Başlık | Durum | Faz |
|---|---|---|---|
| [0001](0001-gemini-flash-interactions-api.md) | Gemini 3.8 Flash + Interactions API | kabul edildi | 2, 3.5 |
| [0002](0002-pdf-native-input-no-png.md) | PDF doğrudan gönderilir, PNG dönüşümü yok | kabul edildi | 2 |
| [0003](0003-pymupdf-redaction.md) | Maskeleme için PyMuPDF redaction annotation | kabul edildi | 1 |
| [0004](0004-sqlite-litestream-gcs.md) | SQLite WAL + Litestream → GCS | kabul edildi | 2, 5 |
| [0005](0005-cloud-run-single-instance.md) | Cloud Run tek instance, CPU always on | kabul edildi | 5 |
| [0006](0006-single-image-static-frontend.md) | Tek image, frontend FastAPI'den servis | kabul edildi | 3, 5 |
| [0007](0007-frontend-stack-no-component-lib.md) | Vite + React + TS, component kütüphanesi yok | kabul edildi | 3 |
