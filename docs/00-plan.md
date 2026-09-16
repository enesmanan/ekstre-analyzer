# Ekstre Analiz Uygulaması — Plan Özeti

Durum: v2 (faz dosyalarına bölünmüş, doğrulanmış) · Tarih: 2026-09-16 · Önceki sürüm: [archive/ekstre-analiz-plan-v1.md](archive/ekstre-analiz-plan-v1.md)

## 1. Ürün

Kullanıcı banka ekstresini (PDF) yükler. Sunucu, ekstreyi LLM'e göndermeden önce PyMuPDF ve regex profilleriyle maskeler; maskelenmiş PDF Gemini 3.8 Flash'a gider; harcamalar yapılandırılmış olarak çıkarılır, kategorilenir, sade bir dashboard'da gösterilir ve dönem bazlı AI tavsiyesi üretilir.

**Konumlama:** Orijinal ekstre diske hiç yazılmaz; LLM'e yalnızca maskelenmiş PDF gider. Türkiye'de açık bankacılık (BKM GEÇİT) lisans gerektirdiğinden ekstre yükleme tek gerçekçi giriş kanalı. Maskelemenin sınırları [security-kvkk.md](security-kvkk.md) §1'de açıkça yazılıdır; "tam anonimlik" vaadi verilmez.

**Kapsam dışı (v1):** Mobil, açık bankacılık, çoklu para birimi, bütçe/hedef, paylaşımlı hesap, taranmış ekstre (OCR), tarayıcı içi maskeleme, TOM dışında banka profili.

**Tek hedef banka:** v1 geliştiricinin kendi TOM Bank ekstresi üzerinden ilerler; her fazın L4 testi bu ekstreyle yapılır (`backend/tests/private/tom.pdf`, gitignore). Çalışma düzeni: [../AGENTS.md](../AGENTS.md).

Mimari ve teknoloji seçimleri: [01-architecture.md](01-architecture.md). Kararların gerekçeleri: [decisions/](decisions/README.md).

## 2. Fazlar

| Faz | Dosya | Amaç | Süre | Durum |
|---|---|---|---|---|
| 1 | [faz-1-masking.md](phases/faz-1-masking.md) | CLI maskeleme, profil, sızıntı testi, sentetik fixture | 1,5 hafta | bitti |
| 2 | [faz-2-extraction-sqlite.md](phases/faz-2-extraction-sqlite.md) | Gemini çıkarım, doğrulama katmanı, SQLite | 1,5 hafta | onaylı |
| 3 | [faz-3-dashboard.md](phases/faz-3-dashboard.md) | HTTP API + React dashboard | 3 hafta | onaylı |
| 3.5 | [faz-3.5-ai-advice.md](phases/faz-3.5-ai-advice.md) | Agregat tabanlı AI öneri | 4 gün | onaylı |
| 4 | [faz-4-auth-admin.md](phases/faz-4-auth-admin.md) | JWT auth, ayarlar, admin, audit | 1,5 hafta | onaylı |
| 5 | [faz-5-cloud-run.md](phases/faz-5-cloud-run.md) | Docker, Litestream, Cloud Run, CI | 1 hafta | onaylı |
| — | [security-kvkk.md](security-kvkk.md) | Kontrol listesi (Faz 4-5 ile paralel) | 3-4 gün | taslak |

Toplam ~10 hafta. Zaman planı, program riskleri ve kapsam kırpma sırası: [risks-timeline.md](risks-timeline.md).

## 3. Doğrulanmış teknik kararlar (özet)

Tam liste ve kaynaklar: [reference/tech-verification-2026-09-16.md](reference/tech-verification-2026-09-16.md).

| Konu | Karar | ADR |
|---|---|---|
| LLM | `gemini-3.8-flash` (GA), Interactions API, `google-genai >= 2.3.0`, `thinking_level` low/medium, structured output JSON şema | [0001](decisions/0001-gemini-flash-interactions-api.md) |
| PDF girişi | Doğrudan PDF (metin katmanı ücretsiz), 15 sayfa üstü parçalama, ilk sayfa bağlam | [0002](decisions/0002-pdf-native-input-no-png.md) |
| Maskeleme | PyMuPDF redaction, `rawdict` karakter bbox'ları, `TOOLS.set_small_glyph_heights(True)`, `scrub()` | [0003](decisions/0003-pymupdf-redaction.md) |
| Veritabanı | SQLite WAL + Litestream 0.5 → GCS; kuruş tamsayı tutarlar | [0004](decisions/0004-sqlite-litestream-gcs.md) |
| Çalışma ortamı | Cloud Run tek instance, CPU always on, bakım bayrağı ile deploy | [0005](decisions/0005-cloud-run-single-instance.md) |
| Dağıtım | Tek image; FastAPI `app.frontend()` ile SPA | [0006](decisions/0006-single-image-static-frontend.md) |
| Frontend | Vite 8 + React 19 + TS, react-router 8, TanStack Query 5, Tailwind 4, uPlot; component kütüphanesi yok | [0007](decisions/0007-frontend-stack-no-component-lib.md) |
| Diller / araçlar | Python 3.13, Node 24, uv, FastAPI 0.141+, SQLAlchemy 2, Alembic (batch), PyJWT, argon2-cffi, slowapi | — |

v1 planından değişenler: Python 3.12 → 3.13, Node 22 → 24, `react-router-dom` → `react-router`, `StaticFiles(html=True)` → `app.frontend(check_dir=False)`, multipart upload → ham gövde (Starlette `UploadFile` diske yazıyor), Litestream config ve binary kaynağı 0.5 sözdizimine, Dockerfile repo köküne, `gemini-3.5-flash` "previous-generation" ifadesi kaldırıldı, inline sınırı 20 MB → 100 MB, tutarlar float → kuruş, tek yazıcı "garantisi" → bakım bayrağı + tag'li revizyon runbook'u, admin Jinja2 → React + JSON API, refresh oturumuna mutlak süre, süre 7 → 10 hafta.

## 4. İlk komutlar (Faz 1 başlangıcı)

```bash
mkdir -p backend frontend infra
cd backend
uv init --python 3.13
uv add pymupdf typer pyyaml pydantic
uv add --dev pytest
mkdir -p app/anonymizer profiles tests/fixtures tests/private tests/out
printf "tests/private/\ntests/out/\n.env\n" >> .gitignore
```

Sonraki adım: [Faz 1 görev listesi](phases/faz-1-masking.md#6-görevler) F1-T01'den başla.
