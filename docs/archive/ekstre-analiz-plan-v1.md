# Ekstre Analiz Uygulaması — Uçtan Uca Uygulama Planı

Tarih: 16 Eylül 2026
Durum: v1 (Faz 1'e başlamadan önce)

---

## 0. Doğrulanmış Teknik Kararlar

Aşağıdaki maddeler güncel resmi dokümanlara karşı kontrol edildi. Çelişki çıkan yerlerde birincil kaynak (Google / PyMuPDF / Litestream resmi dokümanları) esas alındı.

| Konu | Karar | Kaynak / Gerekçe |
|---|---|---|
| LLM modeli | **`gemini-3.8-flash`** (GA) | ai.google.dev/gemini-api/docs/models — 3.8 Flash şu an en yeni Flash; 1M giriş, 64k çıkış, `thinking_level: low/medium/high`. 3.5 Flash artık "previous-generation". |
| API yüzeyi | **Interactions API** (`client.interactions.create`) | Google `generateContent`'i "Legacy" olarak etiketledi; yeni projeler için Interactions öneriliyor. Python SDK: `google-genai`. |
| Yapılandırılmış çıktı | `response_format={"type":"text","mime_type":"application/json","schema": Model.model_json_schema()}` | Interactions API structured-output dokümanı. Pydantic doğrudan destekleniyor. |
| Gemini 3.x özel kurallar | `temperature/top_p/top_k` gönderme; `thinking_budget` yerine `thinking_level`; `candidate_count` yok | "What's new in Gemini 3.8 Flash" migrasyon rehberi. |
| PDF girişi | PDF'i **doğrudan** gönder, PNG'ye çevirme | Gemini PDF'i native alıyor; gömülü metin katmanı çıkarılıp modele veriliyor ve **bu tokenlar ücretsiz**. PNG hem daha pahalı hem metin katmanını kaybettirir. PNG sadece taranmış ekstreler için fallback. |
| Maskeleme | PyMuPDF redaction annotation | `page.add_redact_annot` + `page.apply_redactions(images=PDF_REDACT_IMAGE_NONE, graphics=PDF_REDACT_LINE_ART_NONE)`. Kaydedilince içerik geri alınamaz. |
| Veritabanı | SQLite (WAL) **konteyner yerel diskinde** + **Litestream → GCS** | Cloud Run GCS mount'u (GCS FUSE) dosya kilidi sağlamıyor, POSIX değil; SQLite'ı doğrudan bucket'a koymak veri kaybı riski taşıyor. Litestream, Cloud Run'da instance kimliğiyle GCS'e otomatik yetkilenir. |
| Cloud Run | `min-instances=1`, `max-instances=1`, CPU always allocated | Tek yazıcı garantisi SQLite için şart. |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2 | — |
| Frontend | Vite + React + TypeScript, Tailwind (sadece utility), hazır component kütüphanesi **yok** | Sade tasarım için kendi 6-7 primitifin. |
| Tek image | Frontend `vite build` çıktısı FastAPI `StaticFiles` ile aynı konteynerden servis edilir | Deploy sadeliği. |
| Lokal geliştirme | Docker yok; `uv` + `npm run dev` | Docker sadece Faz 5'te. |

---

## 1. Hedef ve Kapsam

**Ürün cümlesi:** Kullanıcı banka ekstresini (PDF) yükler; sistem ekstreyi LLM'e göndermeden önce cihaz/sunucu tarafında regex tabanlı maskeler; maskelenmiş PDF Gemini'ye gider; harcamalar yapılandırılmış olarak çıkarılır, kategorilenir, sade bir dashboard'da gösterilir ve AI kişisel tavsiye üretir.

**Farklılaştırıcı:** "Ham verin LLM'e hiç gitmez, orijinal ekstre bizde hiç durmaz." Türkiye'de bu konumlamayı yapan ürün yok; banka bağlantısı (BKM GEÇİT) lisans gerektirdiğinden ekstre yükleme tek gerçekçi giriş kanalı.

**Kapsam dışı (v1):** Mobil uygulama, açık bankacılık entegrasyonu, çoklu para birimi, bütçe/hedef modülü, paylaşımlı hesaplar.

---

## 2. Mimari Özeti

```
[Tarayıcı]
   │  PDF upload (HTTPS, JWT)
   ▼
[FastAPI — tek Cloud Run instance]
   ├─ 1. Anonymizer  : PyMuPDF + regex → maskelenmiş PDF (bellekte)
   ├─ 2. Extractor   : Gemini 3.8 Flash (Interactions API, JSON schema)
   ├─ 3. Store       : SQLite (WAL, /data/app.db)  ──Litestream──▶  GCS (replika)
   ├─ 4. Advisor     : Gemini 3.8 Flash (kategori toplamları → tavsiye)
   ├─ 5. Static      : /  → React build (dist/)
   └─ 6. Artifacts   : maskelenmiş PDF/PNG → GCS (opsiyonel, kullanıcı onayı ile)
```

Veri akışında **orijinal PDF asla diske yazılmaz**; `UploadFile` → `bytes` → PyMuPDF → maskelenmiş bytes. Orijinal referansı işlem bitince düşer.

### Repo yapısı

```
ekstre/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, static mount
│   │   ├── config.py          # pydantic-settings
│   │   ├── anonymizer/        # Faz 1
│   │   ├── extractor/         # Faz 2
│   │   ├── advisor/           # Faz 3.5
│   │   ├── auth/              # Faz 4
│   │   ├── db/                # models, session, alembic
│   │   └── api/               # routers
│   ├── cli.py                 # typer CLI (Faz 1-2)
│   ├── tests/
│   ├── profiles/              # banka regex profilleri (yaml)
│   └── pyproject.toml         # uv
├── frontend/                  # Vite + React + TS
├── infra/
│   ├── Dockerfile             # Faz 5
│   ├── litestream.yml
│   └── entrypoint.sh
├── docs/
│   ├── kvkk-aydinlatma.md
│   └── security.md
└── README.md
```

---

## Faz 1 — CLI: Ekstre Maskeleme

**Amaç:** Elindeki gerçek ekstreyi komut satırından güvenli şekilde maskelemek. Ürünün geri kalanının kalitesi bu fazın doğruluğuna bağlı.

### 1.1 Teslimatlar
- `python cli.py mask input.pdf -o masked.pdf --profile garanti`
- `python cli.py inspect input.pdf` → sayfa/blok/metin dökümü (profil yazmak için)
- `python cli.py verify masked.pdf --profile garanti` → sızıntı testi (exit code ≠ 0 ise fail)
- `profiles/*.yaml` — en az kendi bankan için tam profil, 2 banka için taslak

### 1.2 Profil formatı

```yaml
bank: garanti
version: 1
detect:                        # bu ekstre hangi bankaya ait? (ilk sayfa metni)
  any: ["Garanti BBVA", "garantibbva.com.tr"]
mask:
  builtin: [iban, card_number, tckn, phone, email]
  regex:
    - name: customer_no
      pattern: 'Müşteri No\s*:?\s*(\d{6,})'
      group: 1
    - name: name_line
      pattern: '^(Sayın|Adı Soyadı)\s*:?\s*(.+)$'
      group: 2
  user_terms: []               # kullanıcı ayarlarından gelen serbest metinler (Faz 4)
keep:                          # asla maskeleme (tarih, tutar sütunları vb.)
  - 'İşlem Tarihi'
padding_pt: 1.0
```

Built-in regex'ler `anonymizer/patterns.py` içinde: TR IBAN (`TR\d{2}\s?(\d{4}\s?){5}\d{2}`), 16 haneli kart (boşluklu/`*`'lı), TCKN (11 hane, ilk hane ≠ 0 + checksum), telefon, e-posta.

### 1.3 Algoritma

1. `pymupdf.open(stream=bytes)`; her sayfa için `page.get_text("words")`.
2. Kelimeleri satır bazında birleştir (y-ekseni gruplama) → regex satır üzerinde çalışır (IBAN parçalı kelimelere bölünür, kelime bazlı eşleşme kaçırır).
3. Eşleşen span'in kelime rect'lerini birleştir → `rect = rect + (pad, pad, -pad, -pad)` ile **daralt** (komşu kelime silinmesini engeller).
4. `page.add_redact_annot(rect, fill=(0,0,0))`.
5. Sayfa başına **tek** `apply_redactions(images=PDF_REDACT_IMAGE_NONE, graphics=PDF_REDACT_LINE_ART_NONE)` (görsel/vektör dokunulmaz; sayfa başına tek çağrı performans için).
6. `doc.tobytes(garbage=3, deflate=True)` → maskelenmiş bytes.
7. Metadata temizle: `doc.set_metadata({})`, `doc.del_xml_metadata()`.

### 1.4 Sızıntı testi (`verify`)
- Maskelenmiş PDF'ten tekrar metin çıkar; tüm profil regex'leri **hiç** eşleşmemeli.
- Orijinalde bulunan hedef değerler (test fixture'ında bilinir) maskelenmişte string olarak aranır.
- Görsel kontrol: `page.get_pixmap(dpi=100)` → `tests/out/*.png` (elle bakmak için).

### 1.5 Bilinen tuzaklar
- Redaction kutusu bitişik kelimeye taşıyor → padding ile daralt, test et.
- Taranmış (görüntü) ekstreler: metin katmanı yok → Faz 1'de **desteklenmez**, `detect` başarısızsa "OCR gerekiyor" hatası ver. (v2: PyMuPDF OCR / Tesseract.)
- Alpine image'da PyMuPDF wheel sorunları → `python:3.12-slim` (Faz 5).

### 1.6 Kabul kriteri
- Kendi ekstrende `verify` geçiyor, layout bozulmamış, işlem satırları/tutarlar okunabilir.
- 10 sayfalık ekstre < 2 sn.

---

## Faz 2 — LLM Çıkarım + SQLite

**Amaç:** Maskelenmiş PDF'i Gemini 3.8 Flash'a gönderip yapılandırılmış işlem listesi almak ve SQLite'a yazmak. Hâlâ CLI.

### 2.1 Teslimatlar
- `python cli.py extract masked.pdf --db app.db`
- `python cli.py ls --db app.db --from 2026-08-01 --to 2026-08-31 --category market`
- Alembic ilk migration
- `tests/test_extractor.py` (kayıtlı Gemini yanıtı ile, ağ yok)

### 2.2 Veri modeli (SQLAlchemy)

```
users        (id, email, password_hash, created_at, settings_json)   # Faz 4'te dolar
statements   (id, user_id, bank, period_start, period_end, uploaded_at,
              page_count, masked_sha256, model_used, status, error)
transactions (id, statement_id, user_id, txn_date, description,
              amount, currency, direction[debit|credit],
              category, subcategory, merchant_norm,
              confidence, is_installment, installment_no, installment_total,
              user_override_category, created_at)
categories   (key, label_tr, parent_key, sort)
advice       (id, user_id, period, content_json, model_used, created_at)   # Faz 3.5
audit_log    (id, user_id, action, meta_json, created_at)                  # Faz 4
```

SQLite pragmaları (bağlantı başına): `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`.

### 2.3 Kategori seti (sabit, Türkçe)

`market, restoran_kafe, ulasim, yakit, fatura_abonelik, kira_konut, saglik, egitim, giyim, elektronik, eglence, seyahat, nakit_cekim, transfer, kredi_odeme, sigorta, vergi_harc, diger`. Model **bu listeden** seçmek zorunda (schema `enum`).

### 2.4 Gemini çağrısı

```python
from google import genai
from pydantic import BaseModel
from typing import Literal

class Txn(BaseModel):
    txn_date: str            # YYYY-MM-DD
    description: str
    amount: float
    direction: Literal["debit", "credit"]
    category: Literal["market", "restoran_kafe", ...]
    merchant_norm: str
    is_installment: bool
    installment_no: int | None
    installment_total: int | None
    confidence: float

class Extraction(BaseModel):
    bank: str
    period_start: str
    period_end: str
    transactions: list[Txn]

client = genai.Client()   # GEMINI_API_KEY env
interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input=[
        {"type": "text", "text": SYSTEM_PROMPT_TR},
        {"type": "document", "data": masked_b64, "mime_type": "application/pdf"},
    ],
    response_format={
        "type": "text",
        "mime_type": "application/json",
        "schema": Extraction.model_json_schema(),
    },
    generation_config={"thinking_level": "low"},   # çıkarım için low yeterli, ucuz
)
result = Extraction.model_validate_json(interaction.output_text)
```

Notlar:
- `temperature` vb. **gönderme** (3.x'te kaldırıldı).
- 20 MB inline sınırı; üstü için `client.files.upload`.
- Paralellik: sayfa sayısı > 15 ise PyMuPDF ile 10'ar sayfalık alt-PDF'ler üret, `asyncio.gather` ile paralel gönder, sonuçları tarih sırasına göre birleştir; dönem bilgisini ilk parçadan al.
- Retry: 429/5xx için exponential backoff (tenacity), 3 deneme.
- Maliyet günlüğü: `interaction.usage` → statements tablosuna token sayısı yaz.

### 2.5 Doğrulama katmanı (LLM sonrası)
- Tutar toplamı ≈ ekstredeki "Toplam Harcama" satırı (regex ile Faz 1'de yakala) → sapma > %1 ise `status=needs_review`.
- Tarihler dönem içinde mi?
- Duplicate: aynı `(user_id, txn_date, amount, merchant_norm)` → atla.

### 2.6 Kabul kriteri
- Kendi ekstrende ≥ %95 satır yakalama, ≥ %90 doğru kategori.
- Tek ekstre çıkarımı < 15 sn.

---

## Faz 3 — Dashboard + Frontend

**Amaç:** Çıkarılan veriyi sade bir arayüzde göstermek. Auth henüz yok; tek "dev user".

### 3.1 Frontend kararları
- **Vite + React 19 + TypeScript**, `react-router`, `@tanstack/react-query`.
- **Tailwind v4** sadece spacing/typography utility'si için. `shadcn`, `MUI`, gradient, emoji, kart-içinde-kart **yasak**.
- Grafik: `uPlot` (hafif, sade çizgi/bar) veya elle SVG. Recharts yok.
- Tipografi: tek aile (`Inter` veya sistem `-apple-system`), 3 boyut (13/15/22), gri skala + tek vurgu rengi. `prefers-color-scheme` desteği.
- Kendi primitifler: `Button, Input, Select, Table, Tabs, Dialog, Toast, DateRange`.

### 3.2 Ekranlar
1. **Yükle** — drag&drop, ilerleme (maskeleme → çıkarım → kayıt), maskelenmiş önizleme (ilk sayfa PNG, `page.get_pixmap`).
2. **Genel bakış** — dönem seçici (ay / özel aralık), toplam harcama, önceki dönem farkı, kategori dağılımı (yatay bar), günlük akış (çizgi), en büyük 10 işlem.
3. **İşlemler** — tablo; tarih/kategori/tutar/arama filtresi; satır içi kategori düzeltme (`user_override_category`); "bunu her zaman X yap" → `merchant_rules` (v1.1).
4. **Ayarlar** — (Faz 4'te büyür) şimdilik bank profili + maskeleme terimleri.

### 3.3 API (FastAPI, `/api/v1`)
```
POST /statements              multipart upload → 202 {statement_id}
GET  /statements/{id}         status, hata
GET  /statements              liste
GET  /transactions            ?from&to&category&q&page
PATCH /transactions/{id}      {category}
GET  /summary                 ?from&to → toplamlar, kategori dağılımı, günlük seri
GET  /categories
```
Uzun işlem: FastAPI `BackgroundTasks` (tek instance olduğu için yeterli). Frontend 2 sn polling.

### 3.4 Lokal geliştirme (Docker'sız)
```
backend:  uv run uvicorn app.main:app --reload --port 8000
frontend: npm run dev   (vite proxy → :8000/api)
```

### 3.5 Kabul kriteri
- Yükle → 20 sn içinde dashboard'da veri.
- Lighthouse performans ≥ 90, bundle < 250 KB gz.

---

## Faz 3.5 — AI Öneri Sistemi

**Amaç:** Dönem bazlı kişisel tavsiye. Gizlilik: modele **ham işlem değil, agregat** gönder.

### 3.5.1 Girdi
```json
{
  "period": "2026-08",
  "total_debit": 42350.0,
  "by_category": {"market": 9100, "restoran_kafe": 6400, ...},
  "prev_period_by_category": {...},
  "top_merchants": [{"merchant_norm": "MIGROS", "total": 3200, "count": 9}, ...],
  "installments_active": 3,
  "recurring": [{"merchant_norm": "NETFLIX", "amount": 229.99}]
}
```
Tüm `merchant_norm` değerleri maskeleme sonrası; kişisel veri içermez.

### 3.5.2 Çıktı şeması
```python
class Advice(BaseModel):
    summary: str                       # 2-3 cümle
    highlights: list[str]              # max 5
    suggestions: list[Suggestion]      # {title, detail, est_saving_try, category}
    anomalies: list[str]
```
`thinking_level: medium`, `response_format` JSON, Türkçe sistem prompt'u. Sonuç `advice` tablosuna cache'lenir; aynı dönem için tekrar üretim sadece kullanıcı isterse.

### 3.5.3 UI
Genel bakış sayfasının sağ sütunu: "Bu ay" kutusu — düz metin, madde işareti, tek buton "Yeniden üret". Chat arayüzü **yok** (v1).

---

## Faz 4 — JWT Auth + Kullanıcı Ayarları + Admin

### 4.1 Auth tasarımı
- `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`.
- Şifre: `argon2-cffi` (argon2id).
- **Access token**: JWT (HS256 → ileride RS256), 15 dk, `Authorization: Bearer`, bellekte tutulur.
- **Refresh token**: opak random (32 byte), DB'de hash'li, 30 gün, `HttpOnly; Secure; SameSite=Strict` cookie, rotasyonlu (her refresh'te yenisi, eskisi iptal).
- Kütüphane: `pyjwt` (python-jose değil; bakımsız).
- Rate limit: `slowapi` — login 5/dk/IP, upload 10/saat/kullanıcı.
- E-posta doğrulama v1'de yok; admin onaylı kayıt (`is_active=false` default) ile kapalı beta.

### 4.2 Kullanıcı ayarları
- Banka profili seçimi, ek maskeleme terimleri (isim, adres, işyeri adı vb. serbest metin + regex opsiyonu).
- "Maskelenmiş PDF'i sakla" (default **kapalı**). Açıksa GCS'e `users/{id}/statements/{sid}.pdf`.
- Veri indir (JSON/CSV) ve **hesabı sil** (tüm veriler + GCS objeleri, 24 saat içinde kesin silme).

### 4.3 Admin paneli
- `is_admin` flag; `/admin/*` router.
- Kullanıcı listesi, aktif/pasif, ekstre sayısı, token maliyeti (statements.usage toplamı), hata oranı.
- Basit HTML (Jinja2) yeterli — React'e admin taşımak gereksiz.

### 4.4 Audit log
`login, upload, delete_account, admin_action` → `audit_log`.

---

## Faz 5 — Google Cloud Run Deploy (tek instance, tek image)

### 5.1 Dockerfile (multi-stage)
```dockerfile
FROM node:22-alpine AS fe
WORKDIR /fe
COPY frontend/package*.json .
RUN npm ci
COPY frontend .
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
# Litestream binary
ADD https://github.com/benbjohnson/litestream/releases/latest/download/litestream-linux-amd64.tar.gz /tmp/ls.tgz
RUN tar -xzf /tmp/ls.tgz -C /usr/local/bin && rm /tmp/ls.tgz
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock .
RUN uv sync --frozen --no-dev
COPY backend .
COPY --from=fe /fe/dist ./static
COPY infra/litestream.yml /etc/litestream.yml
COPY infra/entrypoint.sh /entrypoint.sh
ENV DB_PATH=/data/app.db
CMD ["/entrypoint.sh"]
```

`entrypoint.sh`:
```sh
#!/bin/sh
set -e
mkdir -p /data
litestream restore -if-db-not-exists -if-replica-exists -o "$DB_PATH" "gs://$DB_BUCKET/app.db"
uv run alembic upgrade head
exec litestream replicate -exec "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"
```

`litestream.yml`:
```yaml
dbs:
  - path: /data/app.db
    replica:
      url: gs://${DB_BUCKET}/app.db
      sync-interval: 1s
      retention: 72h
```

### 5.2 Cloud Run ayarları
```
gcloud run deploy ekstre \
  --source . --region europe-west1 \
  --min-instances 1 --max-instances 1 \
  --cpu 1 --memory 1Gi --no-cpu-throttling \
  --concurrency 40 --timeout 300 \
  --set-secrets GEMINI_API_KEY=gemini-key:latest,JWT_SECRET=jwt-secret:latest \
  --set-env-vars DB_BUCKET=ekstre-db-prod,ARTIFACT_BUCKET=ekstre-files-prod \
  --service-account ekstre-run@PROJECT.iam.gserviceaccount.com
```
- Servis hesabı rolleri: `roles/storage.objectAdmin` (sadece iki bucket'a), `roles/secretmanager.secretAccessor`.
- `/data` için Cloud Run **in-memory emptyDir** yeterli (Litestream restore ile açılışta doldurulur). Bellek limitini DB boyutuna göre ayarla; 1 Gi'de ~500 MB DB rahat.
- Bucket'lar: uniform access, public erişim kapalı, versioning açık (DB bucket'ında), `ARTIFACT_BUCKET` için 90 gün lifecycle.
- Bölge: `europe-west1` (KVKK için yurt dışı aktarım yine de var; bkz. §6).
- Sağlık: `GET /healthz` → DB `SELECT 1` + Litestream son sync yaşı < 30 sn.

### 5.3 CI/CD
GitHub Actions: `pytest` + `npm test` + `vite build` → `gcloud run deploy --source`. Workload Identity Federation ile key'siz.

### 5.4 Tek instance sınırlamaları (bilinçli kabul)
- Deploy sırasında ~10-20 sn kesinti (yeni revizyon eski DB'yi restore eder; eski instance kapanırken Litestream son WAL'ı gönderir — `--no-cpu-throttling` bunun için).
- Ölçekleme gerektiğinde: Cloud SQL Postgres'e geç (SQLAlchemy sayesinde model değişmez).

---

## 6. Deploy Öncesi: KVKK ve Güvenlik Kontrol Listesi

### 6.1 KVKK — hukuki
- [ ] **Aydınlatma metni** (`docs/kvkk-aydinlatma.md`, kayıt ekranında link + onay kutusu). İçerik: veri sorumlusu kimliği, işlenen veriler (e-posta, şifre hash'i, maskelenmiş işlem verisi, IP/log), işleme amacı, hukuki sebep (açık rıza + sözleşme), **yurt dışına aktarım** (Google Cloud EU bölgesi + Gemini API — açık rıza şart), saklama süresi, silme hakkı, başvuru yolu.
- [ ] **Açık rıza** ayrı kutu: "Maskelenmiş ekstremin Google Gemini API'ye gönderilmesini kabul ediyorum."
- [ ] **Gizlilik politikası** ve **kullanım şartları** sayfaları.
- [ ] VERBİS yükümlülüğü kontrolü (çalışan sayısı/ciro eşiği; bireysel geliştirici muaf olabilir, kontrol et).
- [ ] Google Cloud **Data Processing Addendum** kabul edildi; Gemini API'de **ücretli tier** kullan (ücretsiz tier'da veriler eğitim için kullanılabilir — ücretli tier'da kullanılmaz; deploy öncesi güncel politikayı tekrar doğrula).
- [ ] Veri envanteri tablosu (`docs/security.md` içinde).

### 6.2 Veri minimizasyonu — teknik
- [ ] Orijinal PDF diske/bucket'a **hiç** yazılmıyor (kod incelemesi + test).
- [ ] Maskelenmiş PDF saklama default kapalı.
- [ ] Log'larda PDF içeriği, işlem açıklaması, e-posta yok (structlog + redaction filter).
- [ ] Gemini'ye giden payload'da kullanıcı kimliği yok.
- [ ] Hesap silme uçtan uca test edildi (DB + GCS + Litestream retention süresi sonunda replika).

### 6.3 Uygulama güvenliği
- [ ] HTTPS only (Cloud Run default), HSTS header.
- [ ] CSP: `default-src 'self'`; inline script yok.
- [ ] CORS sadece kendi origin.
- [ ] Upload: max 15 MB, MIME + magic byte kontrolü (`%PDF-`), sayfa sayısı ≤ 60, PDF'te JavaScript/embedded file varsa reddet (`doc.embfile_count()`, `page.get_annots`).
- [ ] Rate limit (login, upload, advice).
- [ ] Şifre politikası: min 10 karakter, HIBP kontrolü opsiyonel.
- [ ] Refresh token rotasyonu + reuse detection (eski token tekrar gelirse tüm oturumları kapat).
- [ ] Secret'lar sadece Secret Manager'da; repo'da `.env.example`.
- [ ] Bağımlılık taraması: `pip-audit`, `npm audit` CI'da.
- [ ] `SECURITY.md` + sorumlu ifşa e-postası.

### 6.4 Operasyon
- [ ] Litestream restore tatbikatı yapıldı (bucket'tan sıfır makineye kurtarma < 5 dk).
- [ ] Cloud Monitoring alarm: 5xx oranı, healthz fail, Gemini hata oranı, günlük token maliyeti eşiği.
- [ ] Günlük Gemini bütçe limiti (Google AI Studio'da quota + uygulama içi sayaç).
- [ ] Yedek: DB bucket versioning + 30 gün.

---

## 7. Zaman Planı (tek geliştirici, tahmini)

| Faz | Süre | Çıktı |
|---|---|---|
| 1 | 1 hafta | CLI maskeleme, profil, verify |
| 2 | 1 hafta | Gemini çıkarım, SQLite, CLI listeleme |
| 3 | 2 hafta | Dashboard + API |
| 3.5 | 3-4 gün | AI öneri |
| 4 | 1 hafta | Auth, ayarlar, admin, audit |
| 5 | 3-4 gün | Docker, Litestream, Cloud Run, CI |
| KVKK/güvenlik | 3-4 gün (Faz 4-5 ile paralel) | Metinler, checklist kapanışı |
| **Toplam** | **~7 hafta** | Kapalı beta |

---

## 8. Riskler ve Önlemler

| Risk | Etki | Önlem |
|---|---|---|
| Banka ekstre formatı değişir, regex kaçırır | Kişisel veri LLM'e sızar | `verify` her upload'da zorunlu; fail → işlem durur, kullanıcıya "profil güncellenmeli" |
| Taranmış ekstre | Maskeleme imkânsız | Reddet, v2'de OCR |
| Gemini model deprecation | Kırılma | Model adı config'te; changelog takibi; testler kayıtlı yanıtla çalışır |
| Tek instance çöker | Kısa kesinti | Litestream 1 sn sync; Cloud Run otomatik yeniden başlatır |
| Kategori doğruluğu düşük | Güven kaybı | Kullanıcı düzeltmeleri → merchant kuralları → prompt few-shot |
| Maliyet patlaması | Bütçe | `thinking_level: low`, PDF native metin (ücretsiz token), günlük limit |
| KVKK yurt dışı aktarım | Hukuki | Açık rıza + aydınlatma; ileride Vertex AI EU endpoint ile veri yerleşimi |

---

## 9. İlk Komutlar (Faz 1 başlangıcı)

```bash
mkdir ekstre && cd ekstre
mkdir backend frontend infra docs
cd backend
uv init --python 3.12
uv add pymupdf typer pyyaml pydantic
uv add --dev pytest
mkdir -p app/anonymizer profiles tests/fixtures
# elindeki ekstreyi tests/fixtures/ altına koyma; .gitignore'a ekle, lokalde tut
```

Bir sonraki adım: `app/anonymizer/patterns.py` + `profiles/<banka>.yaml` + `cli.py mask`.
