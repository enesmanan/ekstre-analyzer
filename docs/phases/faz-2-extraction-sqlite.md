# Faz 2 — LLM Çıkarım + SQLite

| Durum | Tarih | Süre tahmini | Bağımlılık |
|---|---|---|---|
| onaylı | 2026-09-16 | 1,5 hafta | Faz 1 bitti |

Önceki: [Faz 1](faz-1-masking.md) · Sonraki: [Faz 3](faz-3-dashboard.md) · İlgili ADR: [ADR-0001](../decisions/0001-gemini-flash-interactions-api.md), [ADR-0002](../decisions/0002-pdf-native-input-no-png.md), [ADR-0004](../decisions/0004-sqlite-litestream-gcs.md)

## 1. Amaç

Maskelenmiş PDF'i Gemini 3.8 Flash'a gönderip yapılandırılmış işlem listesi almak, sonucu doğrulayıp SQLite'a yazmak. Hâlâ CLI; HTTP yok. Faz bitince: `extract` komutu bir maskelenmiş PDF'i veritabanına işler, `ls` komutu filtreli listeler, testler kayıtlı Gemini yanıtlarıyla ağ olmadan geçer.

## 2. Kapsam / Kapsam dışı

- Kapsam: Gemini istemcisi (Interactions API, JSON şema), uzun ekstre parçalama, LLM sonrası doğrulama katmanı, SQLAlchemy modelleri, Alembic ilk migration, SQLite pragmaları, token/maliyet kaydı, kategori seti, CLI `extract` / `ls`.
- Kapsam dışı: HTTP API ve arka plan işi ([Faz 3](faz-3-dashboard.md)), tavsiye üretimi ([Faz 3.5](faz-3.5-ai-advice.md)), kullanıcı ve auth ([Faz 4](faz-4-auth-admin.md)), Litestream ([Faz 5](faz-5-cloud-run.md)), işyeri kuralları (`merchant_rules`, v1.1).

## 3. Ön koşullar

- [ ] Faz 1 KK-1..KK-7 geçti; `MaskResult` arayüzü sabit
- [ ] `GEMINI_API_KEY` (ücretli tier, Google AI Studio'da faturalama açık) `.env` içinde; `.env.example` repoda
- [ ] `backend/tests/out/masked.pdf` (sentetik) ve lokalde gerçek maskelenmiş ekstre mevcut

## 4. Teslimatlar

| Teslimat | Açıklama |
|---|---|
| `uv run cli.py extract MASKED.pdf --db app.db [--profile tom] [--record tests/fixtures/gemini/NAME.json]` | Çıkarım + doğrulama + kayıt. `--record` ham Gemini yanıtını test fixture'ı olarak kaydeder. Exit 0 = `done`, 3 = `needs_review`, 1 = hata. |
| `uv run cli.py ls --db app.db [--from 2026-08-01] [--to 2026-08-31] [--category market] [--statement ID]` | Tablo çıktısı: tarih, açıklama, tutar, kategori, güven. |
| `uv run cli.py db upgrade --db app.db` | Alembic `upgrade head` sarmalayıcısı. |
| `backend/app/db/alembic/versions/0001_initial.py` | users, statements, transactions, categories tabloları. |
| `backend/tests/test_db.py`, `test_schema.py`, `test_prompt.py`, `test_chunker.py`, `test_extractor.py`, `test_validate.py`, `test_service.py` | Ağ yok; kayıtlı yanıtlar `tests/fixtures/gemini/*.json`. |

## 5. Tasarım

### 5.1 Modüller

```
backend/app/extractor/
├── schema.py       # Pydantic: Txn, Extraction; CATEGORIES sabiti
├── prompt.py       # SYSTEM_PROMPT_TR, chunk yönergesi
├── client.py       # GeminiClient (async), RecordedClient (testler)
├── chunker.py      # split(pdf_bytes, single_request_max=15, chunk_pages=10, context_first_page=True)
├── validate.py     # totals, dates → ValidationReport
└── service.py      # extract_statement(statement, mask_result, db, client) -> Statement; parça birleştirme + dedupe burada
                    # `statement` önceden açılmış satır (CLI: status=extracting; Faz 3: status=queued ile 202 anında)
backend/app/db/
├── models.py       # SQLAlchemy 2 declarative
├── session.py      # engine, pragmalar, SessionLocal
└── alembic/        # env.py (render_as_batch=True), versions/
```

### 5.2 Veri modeli

Tutarlar **kuruş cinsinden tamsayı** (`amount_kurus`); float yok. Tarihler `date`, zaman damgaları UTC `datetime`.

```
users         id PK, email UNIQUE, password_hash, is_active (default 0), is_admin (default 0),
              settings_json (TEXT), created_at
statements    id PK, user_id FK, bank (LLM Extraction.bank), profile (MaskResult.bank: tom/generic),
              statement_type [card|account|unknown],
              period_start, period_end, uploaded_at, page_count, redaction_count,
              mask_warnings_json (MaskResult.warnings), validation_issues_json (ValidationReport.issues),
              masked_sha256, model_used, status, error,
              input_tokens, output_tokens, thought_tokens, cost_usd_micro,
              stated_total_debit_kurus (ekstredeki toplam, nullable),
              extracted_total_debit_kurus,
              UNIQUE(user_id, masked_sha256)
transactions  id PK, statement_id FK (ON DELETE CASCADE), user_id FK,
              txn_date, description, amount_kurus, currency (default 'TRY'),
              direction [debit|credit], category, merchant_norm, confidence (0..1),
              is_installment, installment_no, installment_total,
              user_override_category (nullable), created_at
              INDEX (user_id, txn_date), INDEX (statement_id)
categories    key PK, label_tr, sort
```

`status` değerleri: `queued`, `masking`, `mask_failed`, `extracting`, `extract_failed`, `needs_review`, `done`. Faz 2'de CLI `extracting` → `done` / `needs_review` / `extract_failed` geçişlerini kullanır; `queued`/`masking` Faz 3'te.

Faz 2 tek "dev user" ile çalışır: migration `users` tablosuna `id=1, email=dev@local, is_active=1` satırı ekler; Faz 4 gerçek kayıt getirir. `advice` ve `audit_log` tabloları kendi fazlarında ayrı migration ile gelir.

SQLite pragmaları (`session.py`, `event.listens_for(engine, "connect")`): `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`. Python 3.12+ için `create_engine(url, connect_args={"autocommit": False})`; PRAGMA'ları çalıştırmadan önce `dbapi_connection.autocommit = True`, sonra `False`'a dön (SQLAlchemy SQLite dokümanındaki reçete). Engine senkron (`create_engine`), aiosqlite kullanılmaz; Faz 3'te çağrılar threadpool'da.

Alembic `env.py`: `context.configure(..., render_as_batch=True)`; SQLite `ALTER TABLE` kısıtları için zorunlu. DB yolu `alembic.ini`'den değil `-x db=PATH` argümanından (`context.get_x_argument(as_dictionary=True)`) veya `DATABASE_URL` env'den okunur; `cli.py db upgrade --db` aynı mekanizmayı kullanır.

### 5.3 Kategori seti (sabit, `schema.py`)

`market, restoran_kafe, ulasim, yakit, fatura_abonelik, kira_konut, saglik, egitim, giyim, elektronik, eglence, seyahat, nakit_cekim, transfer, kredi_odeme, sigorta, vergi_harc, diger`

Şemada `Literal[...]` ile zorlanır; `categories` tablosu aynı listeden seed edilir (`label_tr` Türkçe etiket, `sort` görüntüleme sırası).

### 5.4 Gemini çağrısı (`client.py`)

```python
from datetime import date
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal

Category = Literal["market", "restoran_kafe", ...]  # 5.3 listesi

class Txn(BaseModel):
    txn_date: date                    # şemada {"type":"string","format":"date"}; parse hatası Pydantic'te
    description: str                  # ekstredeki ham açıklama
    amount_kurus: int                 # 1.234,56 TL -> 123456
    direction: Literal["debit", "credit"]
    category: Category
    merchant_norm: str                # "MIGROS 1234 KADIKOY" -> "MIGROS"
    is_installment: bool
    installment_no: int | None = None
    installment_total: int | None = None
    confidence: float = Field(ge=0, le=1)

class Extraction(BaseModel):
    bank: str
    statement_type: Literal["card", "account", "unknown"]
    period_start: date
    period_end: date
    stated_total_debit_kurus: int | None   # ekstredeki "Toplam Harcama/Borç" satırı
    transactions: list[Txn]

class Usage(NamedTuple):
    input_tokens: int
    output_tokens: int
    thought_tokens: int

class GeminiClient:                       # LLMClient Protocol'ünü uygular
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = genai.Client(      # tembel: import anında değil, örnek oluşturulunca
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=4)   # 408/429/5xx, 1–60 sn jitter
            )
        )

    async def extract_chunk(self, pdf_b64: str, chunk_index: int) -> tuple[Extraction, Usage]:
        interaction = await self._client.aio.interactions.create(
            model=self._settings.gemini_model,        # "gemini-3.8-flash", config'te
            system_instruction=SYSTEM_PROMPT_TR,
            input=[
                {"type": "text", "text": chunk_instruction(chunk_index)},
                {"type": "document", "data": pdf_b64, "mime_type": "application/pdf"},
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": Extraction.model_json_schema(),
            },
            generation_config={"thinking_level": "low"},
        )
        result = Extraction.model_validate_json(interaction.output_text)
        u = interaction.usage
        return result, Usage(u.total_input_tokens, u.total_output_tokens, u.total_thought_tokens)
```

Kurallar:

- `temperature`, `top_p`, `top_k`, `candidate_count` **gönderilmez** (Gemini 3.x'te kaldırıldı/desteklenmiyor).
- `thinking_level="low"` çıkarım için yeterli; `minimal` 3.8 Flash'ta hata döner.
- Eşzamanlılık: `asyncio.Semaphore(3)` (Tier 1 RPM sınırı için); parçalar `asyncio.gather` ile.
- Retry **tek katman:** SDK varsayılanda retry yapmaz (`retry_options` verilmezse tek deneme). `HttpRetryOptions(attempts=4)` ile 408/429/500/502/503/504 için SDK retry açılır; tenacity kullanılmaz (iki katman 12 denemeye çıkar). `400` (şema/istek hatası) retry edilmez.
- `genai.Client` modül düzeyinde oluşturulmaz; `GEMINI_API_KEY` yokken import kırılır ve `RecordedClient` testleri de düşer.
- `RecordedClient`: aynı arayüz, `tests/fixtures/gemini/*.json` dosyasından `output_text` ve `usage` döner. `GeminiClient` ve `RecordedClient` `LLMClient` Protocol'ünü uygular (Faz 2'de `extract_chunk`, Faz 3.5'te `advise` eklenir); `service.py` bunu enjekte alır.
- Şema: Gemini `anyOf`, `enum`, `format: date`, `minimum/maximum` destekler; Pydantic'in ürettiği `$defs`, `title`, `default` anahtarları için resmi örnek yok ve "deeply nested schemas may be rejected" uyarısı var. F2-T05'te tek canlı smoke test; reddedilirse şema `title`/`default` anahtarlarından arındırılır (`model_json_schema` sonrası temizleme fonksiyonu).
- Boyut: uygulama üst sınırı 15 MB / 60 sayfa (Faz 3 upload sınırı). Gemini inline sınırı 100 MB toplam istek olduğu için Files API v1'de gerekmez.
- Maliyet (tahmini üst sınır): `cost_usd_micro = in_tokens * price_in + (out_tokens + thought_tokens) * price_out`; fiyatlar config'te (`GEMINI_PRICE_IN_PER_M=0.75`, `GEMINI_PRICE_OUT_PER_M=3.75`; 1 Ocak 2027'de güncellenecek). PDF gömülü metin token'ları `usage`'da görünür ama faturalanmaz; gerçek maliyet bu değerin altındadır.

### 5.5 Sistem promptu (`prompt.py`, Türkçe, özet)

- Rol: Türk bankası ekstresi okuyan muhasebe asistanı. Yalnızca ekstredeki işlemleri listele, uydurma.
- Tutar: kuruş tamsayı; `1.234,56` → `123456`. Taksit satırları: `3/12` → `installment_no=3, installment_total=12`.
- `direction`: harcama/borç `debit`, iade/ödeme/gelen `credit`.
- `merchant_norm`: şube kodu, şehir, `*`, rakam ekleri atılmış büyük harf marka adı. Havale/EFT'de karşı taraf adı yerine `HAVALE` / `EFT` yaz (kişisel veri minimizasyonu).
- Kategori listeden; emin değilsen `diger` ve `confidence` düşük.
- `stated_total_debit_kurus`: ekstrede "Toplam Harcama", "Dönem Borcu", "Toplam Borç" satırı varsa; yoksa `null`.
- Parça yönergesi (`chunk_index > 0`): "İlk sayfa yalnızca bağlam içindir, oradaki işlemleri listeleme; dönem ve banka bilgisini ilk sayfadan al."

### 5.6 Parçalama (`chunker.py`)

`page_count <= 15` ise tek istek. Aksi halde 10'ar sayfalık parçalar; her parçaya ilk sayfa eklenir:

```python
part = pymupdf.open()
if chunk_index > 0:
    part.insert_pdf(doc, from_page=0, to_page=0)
part.insert_pdf(doc, from_page=start, to_page=end)
data = part.tobytes(garbage=3, deflate=True)
```

Birleştirme (`service.py`): `bank`, `statement_type`, `period_*`, `stated_total_debit_kurus` ilk parçadan; `transactions` `list[ChunkTxn(chunk_index, txn)]` olarak toplanır. Parça dedupe kuralı:

- Parça `k > 0`'daki bir `(txn_date, amount_kurus, description)` üçlüsü parça 0'da da varsa at (bağlam olarak eklenen 1. sayfanın işlemleri prompt'a rağmen listelenmiş demektir).
- Parça `k`'nın son satırı parça `k+1`'in ilk satırıyla aynı üçlüyse birini at (sayfa sonu satır tekrarı).
- Aynı parça içindeki tekrarlar meşrudur (aynı gün aynı kahve), korunur.
- Atılan sayı `ValidationReport.issues`'a `chunk_dup:<n>` olarak yazılır.

Parça `Usage`'ları toplanır.

### 5.7 Doğrulama katmanı (`validate.py`)

`ValidationReport(status, issues: list[str])`:

1. **Toplam kontrolü:** `stated_total_debit_kurus > 0` ise `|sum(debit) - stated| / stated > 0.01` → `needs_review`, issue `total_mismatch`. `stated` LLM'den gelmezse maskelenmiş PDF metninde regex fallback: `(Toplam Harcama|Dönem Borcu|Toplam Borç)\s*:?\s*(\d{1,3}(\.\d{3})*,\d{2})`. İkisi de yoksa veya sıfırsa kontrol atlanır, issue `no_stated_total` (bilgi amaçlı, status değişmez).
2. **Tarih kontrolü:** her `txn_date` `[period_start - 5 gün, period_end + 5 gün]` içinde olmalı; dışındaki satır `needs_review`, issue `date_out_of_period:<n>`. Parse edilemeyen tarih Pydantic'te (`format: date`) yakalanır → `extract_failed`.
3. **Parça dedupe:** 5.6'daki kural `service.py`'de uygulanır; `validate.py` yalnızca sonucu raporlar.
4. **Ekstre dedupe:** `UNIQUE(user_id, masked_sha256)`; `service.py` satırı güncellemeden önce aynı hash'li başka `done`/`needs_review` satır varsa `DuplicateStatement` fırlatır; CLI "bu ekstre zaten yüklü (statement N)" der, exit 1; Faz 3 satırı `mask_failed` + `error=duplicate_statement` yapar.
5. **Şema dışı değerler:** Pydantic zaten reddeder; `model_validate_json` hatası `extract_failed`, ham yanıt `error` alanına ilk 500 karakteriyle yazılır (kişisel veri içermez, maskelenmiş PDF'ten gelir).

### 5.8 Bilinen tuzaklar

- Interactions API yanıt yapısı Mayıs 2026'da `outputs` → `steps` oldu; `output_text` kullanılır, `outputs[-1].text` kalıbı geçersiz. SDK `google-genai >= 2.3.0` pinlenir.
- Kredi kartı ekstresinde "önceki dönem ödemesi" `credit` olarak gelir; toplam kontrolü yalnızca `debit` toplamı ile yapılır.
- Aynı işlem provizyon ve kesinleşme olarak iki kez görünebilir; v1'de dokunulmaz, `[NETLEŞTİRİLMELİ]`.
- LLM `merchant_norm`'u tutarsız üretebilir (`MİGROS` / `MIGROS`); `service.py` post-normalize eder: NFKD → ASCII, büyük harf, rakam ve tekil harf ekleri kırp.
- Fiyat tanıtım dönemi 31 Aralık 2026'da bitiyor; `cost_usd_micro` hesabı config'ten fiyat okur.

## 6. Görevler

Format: `- [ ] F2-TXX [P] Açıklama — dosya`. Komutlar `backend/` içinden, Git Bash.

### 6.1 Kurulum

- [ ] F2-T01 Bağımlılıklar — `backend/pyproject.toml`
      Komut: `uv add "google-genai>=2.3.0" sqlalchemy alembic pydantic-settings tenacity && uv add --dev pytest-asyncio`
      Doğrula: `uv run python -c "from google import genai; import sqlalchemy, alembic; print(sqlalchemy.__version__)"`
- [ ] F2-T02 [P] Ayarlar — `backend/app/config.py`, `backend/.env.example`
      Doğrula: `uv run python -c "from app.config import settings; print(settings.gemini_model)"` → `gemini-3.8-flash`

### 6.2 Veritabanı

- [ ] F2-T03 Modeller ve session (pragmalar, autocommit notu) — `backend/app/db/models.py`, `session.py`
      Doğrula: `uv run pytest tests/test_db.py -q` (WAL modu aktif: `PRAGMA journal_mode` → `wal`; FK ihlali `IntegrityError`)
- [ ] F2-T04 Alembic kurulumu (`render_as_batch=True`, `-x db=` ile yol), ilk migration, kategori ve dev user seed — `backend/app/db/alembic/`, `cli.py db upgrade`
      Doğrula: `uv run cli.py db upgrade --db /tmp/t.db && uv run alembic -c app/db/alembic.ini -x db=/tmp/t.db current` → `0001 (head)`

### 6.3 Çıkarım

- [ ] F2-T05 [P] Şema ve kategori sabiti — `backend/app/extractor/schema.py`
      Doğrula: `uv run pytest tests/test_schema.py -q` (`Extraction.model_json_schema()` üretiliyor; kategori dışı değer ve `2026-13-40` tarihi `ValidationError`). Ek: bir kez canlı smoke test, şema Gemini tarafından kabul ediliyor (`uv run cli.py extract tests/out/masked.pdf --db /tmp/t.db --record tests/fixtures/gemini/synthetic.json`); 400 dönerse `title`/`default` temizleme fonksiyonu eklenir.
- [ ] F2-T06 [P] Sistem promptu — `backend/app/extractor/prompt.py`
      Doğrula: `uv run pytest tests/test_prompt.py -q` (chunk 0 ve chunk 1 yönergeleri farklı)
- [ ] F2-T07 [P] Parçalayıcı — `backend/app/extractor/chunker.py`
      Doğrula: `uv run pytest tests/test_chunker.py -q` (25 sayfalık sentetik PDF → 3 parça: 10, 11, 6 sayfa; ilk parça hariç her parçanın 1. sayfası orijinal 1. sayfa)
- [ ] F2-T08 İstemci: `LLMClient` Protocol, `GeminiClient` (tembel `genai.Client`, `HttpRetryOptions(attempts=4)`), `RecordedClient` — `backend/app/extractor/client.py`
      Doğrula: `uv run pytest tests/test_extractor.py -q` (`GEMINI_API_KEY` tanımsızken `RecordedClient` testleri geçiyor; `GeminiClient` `retry_options.attempts == 4` ile kuruluyor)
- [ ] F2-T09 Doğrulama katmanı — `backend/app/extractor/validate.py`
      Doğrula: `uv run pytest tests/test_validate.py -q` (toplam sapması %1,5 → `needs_review`; `stated=0` sıfıra bölme yok; dönem dışı tarih işaretleniyor)
- [ ] F2-T10 Servis: önceden açılmış `statement` + `MaskResult` → parça birleştirme + parça dedupe → transactions, `validation_issues_json` — `backend/app/extractor/service.py`
      Doğrula: `uv run pytest tests/test_service.py -q` (kayıtlı yanıtla uçtan uca; `statements.input_tokens` dolu; parça 1'de tekrarlanan 1. sayfa işlemleri atılıyor, aynı parça içi eşit iki satır korunuyor; aynı `masked_sha256` ikinci kez → `DuplicateStatement`)
- [ ] F2-T11 CLI `extract` / `ls` — `backend/cli.py`
      Doğrula: `uv run cli.py extract tests/out/masked.pdf --db /tmp/t.db && uv run cli.py ls --db /tmp/t.db --category market` (sentetik ekstre için canlı Gemini gerekir; ilk çalıştırmada `--record tests/fixtures/gemini/synthetic.json` ile kaydet)
- [ ] F2-T12 TOM ekstresi ile kalite ölçümü (`tests/out/tom-masked.pdf` üzerinden; prompt TOM'un satır yapısına göre ayarlanır, ham yanıt `tests/private/` altına kaydedilir, commit edilmez) — `tests/private/eval.md` (gitignore)
      Doğrula: satır yakalama ≥ %95, kategori doğruluğu ≥ %90 (elle sayım, sonuç bu dosyanın changelog'una yazılır; kişisel veri yok, sadece oranlar)

### 6.4 Kapanış

- [ ] F2-T13 Süre ölçümü — `tests/private/eval.md`
      Doğrula: gerçek ekstre `extract` < 15 sn (`time uv run cli.py extract ...`)
- [ ] F2-T14 Bu dosyada Durum → bitti, changelog; `docs/README.md` faz tablosu

## 7. Kabul kriterleri

- KK-1: `uv run pytest -q` ağ bağlantısı olmadan geçer (`RecordedClient`).
- KK-2: TOM ekstresinde satır yakalama ≥ %95, kategori doğruluğu ≥ %90 (F2-T12).
- KK-3: Tek ekstre `extract` süresi < 15 sn; 25 sayfalık sentetik ekstre 3 parça ile < 30 sn.
- KK-4: Toplam sapması %1'i geçen ekstre `needs_review` ile kaydedilir, exit 3.
- KK-5: `statements` satırında `input_tokens`, `output_tokens`, `thought_tokens`, `cost_usd_micro` dolu.
- KK-6: Kod tabanında `temperature`, `top_p`, `top_k`, `candidate_count`, `thinking_budget` geçmez. Komut: `grep -rnE "temperature|top_p|top_k|candidate_count|thinking_budget" app/` → boş.
- KK-7: Gemini'ye giden payload'da kullanıcı kimliği, e-posta veya ekstre şifresi yok (test: `RecordedClient` çağrı argümanlarını yakalar).

## 8. Riskler (bu faza özgü)

| Risk | Etki | Önlem |
|---|---|---|
| Interactions API şema değişikliği | Parse kırılır | SDK pin, `output_text` kullanımı, changelog takibi, kayıtlı yanıt testleri |
| Model kategori doğruluğu düşük | Güven kaybı | `confidence` alanı, `needs_review`, Faz 3'te kullanıcı düzeltmesi, ileride few-shot |
| Toplam satırı ekstrede yok | Doğrulama zayıflar | Regex fallback, `no_stated_total` bilgi issue'su |
| 429 / kota (RPM ve Tier 1'de 10 dakikalık $10 harcama limiti) | İş durur | Semaphore(3), SDK retry, uygulama içi harcama sayacı ve eşik (Faz 4 admin), Tier yükseltme |
| Fiyat artışı Ocak 2027 | Maliyet 2x | Fiyat config'te, admin panelde günlük maliyet |

## 9. Açık sorular

- [NETLEŞTİRİLMELİ: Provizyon + kesinleşme çift satırları v1'de nasıl ele alınacak]
- [NETLEŞTİRİLMELİ: Yabancı para işlemler (USD/EUR) `currency` ile saklanacak ama toplamlara dahil edilmeyecek mi; TL karşılığı satırı var mı]
- [NETLEŞTİRİLMELİ: `media_resolution: low` ile doğruluk düşmeden maliyet düşüyor mu; gerçek ekstrede A/B]

## 10. Referanslar

- Interactions API: https://ai.google.dev/gemini-api/docs/interactions , https://ai.google.dev/gemini-api/docs/interactions/get-started
- Structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Document processing: https://ai.google.dev/gemini-api/docs/document-processing
- Gemini 3 migration: https://ai.google.dev/gemini-api/docs/latest-model
- Rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- SQLAlchemy SQLite dialect (pragma, autocommit): https://docs.sqlalchemy.org/en/20/dialects/sqlite.html
- Alembic batch mode: https://alembic.sqlalchemy.org/en/latest/batch.html
- PyMuPDF `insert_pdf`: https://pymupdf.readthedocs.io/en/latest/document.html
- Doğrulama notu: [../reference/tech-verification-2026-09-16.md](../reference/tech-verification-2026-09-16.md)

## Changelog

- 2026-09-16 taslak oluşturuldu (monolit plandan bölündü; kuruş tamsayı, token/maliyet sütunları, ekstre dedupe, parça sınırı dedupe, ilk sayfa bağlamı, `system_instruction`, `client.aio`, `RecordedClient`, Alembic batch modu eklendi)
- 2026-09-16 doğrulama turu 1: SDK retry varsayılanı düzeltildi (tek katman `HttpRetryOptions`), tembel client, parça dedupe kuralı `service.py`'e taşındı ve netleştirildi, `date` tipi, `bank`/`profile` ayrımı, Alembic `-x db=`, şema smoke test, harcama limiti riski
