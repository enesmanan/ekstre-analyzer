# Faz 3.5 — AI Öneri Sistemi

| Durum | Tarih | Süre tahmini | Bağımlılık |
|---|---|---|---|
| onaylı | 2026-09-16 | 4 gün | Faz 3 bitti |

Önceki: [Faz 3](faz-3-dashboard.md) · Sonraki: [Faz 4](faz-4-auth-admin.md) · İlgili ADR: [ADR-0001](../decisions/0001-gemini-flash-interactions-api.md)

## 1. Amaç

Dönem bazlı kişisel harcama tavsiyesi üretmek. Gizlilik ilkesi: modele **ham işlem satırı değil, agregat** gönderilir. Faz bitince: genel bakış sayfasının sağ sütununda "Bu ay" kutusu, "Yeniden üret" butonu, sonuç veritabanında cache'li.

## 2. Kapsam / Kapsam dışı

- Kapsam: Agregat üretici, `Advice` şeması, Gemini çağrısı (`thinking_level: medium`), `advice` tablosu ve migration, iki uç nokta, UI kutusu, kayıtlı yanıtla test.
- Kapsam dışı: Chat arayüzü, bütçe/hedef önerisi, bildirim, çoklu dönem karşılaştırma raporu (v1.1), kullanıcı başı rate limit ([Faz 4](faz-4-auth-admin.md) slowapi; burada basit bellek içi kilit).

## 3. Ön koşullar

- [x] Faz 3 KK-1..KK-7 geçti
- [ ] Bir dönem için ≥ 20 işlem içeren veri mevcut (sentetik veya gerçek)

## 4. Teslimatlar

| Teslimat | Açıklama |
|---|---|
| `backend/app/advisor/{aggregate,schema,prompt,service}.py` | Agregat, şema, prompt, servis |
| `backend/app/db/alembic/versions/0002_advice.py` | `advice` tablosu |
| `POST /api/v1/advice?period=2026-08`, `GET /api/v1/advice?period=2026-08` | Üret / getir |
| `frontend/src/pages/Overview.tsx` sağ sütun `AdviceBox` | UI |
| `backend/tests/test_advisor.py`, `tests/fixtures/gemini/advice_*.json` | Ağ yok |

## 5. Tasarım

### 5.1 Veri modeli

```
advice   id PK, user_id FK, period (YYYY-MM), content_json, source_txn_count,
         model_used, input_tokens, output_tokens, thought_tokens, cost_usd_micro,
         created_at, updated_at
         UNIQUE(user_id, period)
```

`period`: v1'de yalnızca ay; regex `^\d{4}-(0[1-9]|1[0-2])$`, aksi `400 invalid_period`. Özel aralık v1.1 (UI'daki `DateRange` Overview'da kalır, tavsiye kutusu seçili aralığın başladığı ayı kullanır). Yeniden üretim satırı günceller: `sqlite.insert(...).on_conflict_do_update(index_elements=[user_id, period], set_={content_json, source_txn_count, model_used, token alanları, updated_at})`; `set_` içinde `updated_at` açıkça verilir (upsert Python tarafı `onupdate` çalıştırmaz). `source_txn_count` UI'da "veri değişti, yeniden üret" göstergesi için (mevcut işlem sayısı ile karşılaştırılır).

### 5.2 Agregat girdisi (`aggregate.py`)

```json
{
  "period": "2026-08",
  "days": 31,
  "total_debit_kurus": 4235000,
  "total_credit_kurus": 120000,
  "by_category": {"market": 910000, "restoran_kafe": 640000},
  "prev_period_by_category": {"market": 870000},
  "top_merchants": [{"merchant_norm": "MIGROS", "kurus": 320000, "count": 9}],
  "installments_active": 3,
  "recurring": [{"merchant_norm": "NETFLIX", "kurus": 22999, "months_seen": 3}],
  "weekday_vs_weekend_debit_kurus": {"weekday": 3000000, "weekend": 1235000},
  "txn_count": 84
}
```

Kurallar: `description` alanı **hiç** gönderilmez; `merchant_norm` zaten Faz 2 prompt'unda havale/EFT için `HAVALE`/`EFT` olarak normalize edilmiştir. `top_merchants` en fazla 10. Kategori toplamlarında `COALESCE(user_override_category, category)`.

`recurring` algoritması: seçili ay dahil son 6 ay; her ay için `merchant_norm` başına işlem sayısı tam 1 olan kayıtlar alınır; ardışık aylarda `|a - b| / max(a, b) <= 0.05` ise zincir uzar; zincir uzunluğu ≥ 2 olanlar `recurring`'e girer, `months_seen` zincir uzunluğu, `kurus` son ayın tutarı. En fazla 10, `kurus` desc.

### 5.3 Çıktı şeması (`schema.py`)

```python
class Suggestion(BaseModel):
    title: str
    detail: str
    est_saving_kurus: int | None = None
    category: Category | None = None

class Advice(BaseModel):
    summary: str                     # 2-3 cümle
    highlights: list[str] = Field(max_length=5)       # şemada maxItems
    suggestions: list[Suggestion] = Field(max_length=5)
    anomalies: list[str] = Field(max_length=5)

    @field_validator("suggestions")
    @classmethod
    def drop_health(cls, v):         # saglik kategorili öneri atılır (KVKK özel nitelikli veri)
        return [s for s in v if s.category != "saglik"]
```

Çağrı Faz 2 `GeminiClient` ile aynı desende (`interactions.create`, `response_format` JSON şema, `system_instruction`), farklar: `generation_config={"thinking_level": "medium", "max_output_tokens": 4096}`. Faz 2'deki Protocol `LLMClient` adıyla iki metot taşır: `extract_chunk(...)` ve `advise(payload: dict) -> tuple[Advice, Usage]`; `GeminiClient` ve `RecordedClient` ikisini de uygular. Faz 2 `Semaphore(3)` advice çağrılarını da kapsar. `Suggestion` nested olduğu için Pydantic `$defs`/`$ref` üretir; Faz 2 F2-T05 şema temizleme fonksiyonu burada da uygulanır ve F35-T03'te canlı smoke test yapılır.

### 5.4 Sistem promptu (Türkçe, özet)

- Rol: kişisel harcama asistanı; yargılamayan, somut, kısa. Rakamları TL olarak yaz (kuruş / 100, `1.234,56 ₺`).
- Yalnızca verilen agregatlara dayan; olmayan bilgi uydurma. Sağlık harcaması hakkında yorum yapma (hassas veri). Yatırım ürünü, kredi veya finansal araç önerme; bu bir finansal danışmanlık değildir (Google Generative AI Prohibited Use Policy finansı yüksek riskli alan sayar; çıktı bilgilendirme amaçlıdır).
- `prev_period_by_category` boşsa karşılaştırma yapma.
- `highlights`: önceki döneme göre en büyük 3-5 değişim. `suggestions`: uygulanabilir, tahmini tasarruf ile. `anomalies`: tek seferlik büyük harcama, yeni tekrarlayan ödeme.

### 5.5 Servis ve uç noktalar

Hata gövdesi Faz 3 formatında: `{"error": {"code": ..., "message": ...}}`. Bu fazın kodları: `invalid_period`, `no_advice`, `not_enough_data`, `in_progress`; Faz 4'ün `budget_exceeded` ve `maintenance` kodları bu uca da uygulanır.

- `GET /advice?period=` → varsa `advice` satırı + `stale: bool` (`source_txn_count != mevcut sayı`), yoksa `404 no_advice`.
- `POST /advice?period=` → agregat üret, işlem sayısı < 10 ise `400 not_enough_data`; Gemini çağır; upsert; sonucu döndür. Eşzamanlılık: süreç içi `in_progress: set[int]` (user_id); sette varsa `409 in_progress` (bekletmez; `asyncio.Lock` bekletir, o yüzden kullanılmaz). Test: `asyncio.Event` ile bekletilen sahte istemci.
- Otomatik üretim yok: kullanıcı butona basar (maliyet kontrolü). Faz 4'te slowapi `5/saat/kullanıcı`.
- `POST /advice` bakım bayrağı açıkken `503 maintenance` (Faz 3 `app.state.maintenance`; test F35-T04'te).
- Token ve maliyet `advice` satırına yazılır; admin toplamına girer (Faz 4).

### 5.6 UI

Overview sağ sütunu: başlık "Bu ay", `summary` düz metin, `highlights` madde listesi, `suggestions` başlık + detay + tasarruf, `anomalies` ayrı küçük liste. Tek buton "Yeniden üret" (yükleniyor durumu, hata toast'ı). `stale` ise küçük not "Veri değişti". Veri yoksa "Henüz öneri üretilmedi" + "Üret" butonu. Altta sabit küçük metin: "Bilgilendirme amaçlıdır, finansal danışmanlık değildir." Chat yok.

### 5.7 Bilinen tuzaklar

- `thinking_level: medium` yanıt süresini uzatır (tahmin 5-15 sn; resmi gecikme rehberi yok); UI'da açık yükleniyor durumu.
- Kategori toplamları override'ları içermeli; aksi halde kullanıcı düzeltmesi tavsiyeye yansımaz.
- Tek dönemlik veri ile `prev_period_by_category` boş; prompt karşılaştırma yapmaz.
- Yeni ekstre veya kategori düzeltmesi sonrası cache bayatlar; `stale` göstergesi ile kullanıcı yeniden üretir, otomatik üretim yok.

## 6. Görevler

- [ ] F35-T01 Migration `advice` — `backend/app/db/alembic/versions/0002_advice.py`
      Doğrula: `uv run cli.py db upgrade --db /tmp/t.db && uv run alembic -c app/db/alembic.ini -x db=/tmp/t.db current` → `0002 (head)`
- [ ] F35-T02 [P] Agregat — `backend/app/advisor/aggregate.py`
      Doğrula: `uv run pytest tests/test_advisor.py -q -k aggregate` (çıktıda `description` anahtarı yok; override kategori doğru kovada; recurring tespiti 3 aylık fixture'da NETFLIX'i buluyor)
- [ ] F35-T03 [P] Şema ve prompt — `backend/app/advisor/{schema,prompt}.py`
      Doğrula: `uv run pytest tests/test_advisor.py -q -k schema` (`maxItems: 5` şemada; `saglik` kategorili öneri atılıyor). Ek: bir kez canlı smoke test (`--record tests/fixtures/gemini/advice_synthetic.json`), temizlenmiş şema Gemini tarafından kabul ediliyor.
- [ ] F35-T04 Servis, `advise` metodu, uç noktalar — `backend/app/advisor/service.py`, `app/extractor/client.py`, `app/api/advice.py`
      Doğrula: `uv run pytest tests/test_advisor.py -q` (kayıtlı yanıtla `POST` → 200, ikinci `GET` cache'ten ve `stale: false`; yeni işlem eklenince `stale: true`; `not_enough_data`; `invalid_period`; `asyncio.Event` ile bekletilen sahte istemcide eşzamanlı ikinci `POST` → 409; upsert sonrası `updated_at` değişiyor)
- [ ] F35-T05 UI kutusu — `frontend/src/pages/Overview.tsx`, `frontend/src/ui/AdviceBox.tsx`
      Doğrula: `npm test -- AdviceBox`
- [ ] F35-T06 Canlı kalite kontrolü — `tests/private/eval.md`
      Doğrula: gerçek verinizle 3 dönem için üretim; öneriler somut ve uydurma rakam yok (elle)
- [ ] F35-T07 Bu dosyada Durum → bitti, changelog; `docs/README.md`

## 7. Kabul kriterleri

- KK-1: Gemini'ye giden payload'da `description`, e-posta, kullanıcı id yok (test `RecordedClient` argümanlarını yakalar).
- KK-2: Aynı dönem için ikinci `GET` Gemini çağırmaz.
- KK-3: Bir tavsiye üretimi < 20 sn; `output_tokens` ≤ 4.096 (`max_output_tokens`), `thought_tokens` ayrı sayılır ve raporlanır.
- KK-4: `uv run pytest -q` ağ olmadan geçer.
- KK-5: `saglik` kategorili öneri hiçbir yanıtta yer almaz (validator testi).

## 8. Riskler (bu faza özgü)

| Risk | Etki | Önlem |
|---|---|---|
| Genel, boş tavsiyeler | Değer algısı düşer | Prompt'ta somutluk kuralı, `est_saving_kurus`, canlı kalite kontrolü |
| Maliyet (kullanıcı tekrar tekrar üretir) | Bütçe | Cache, buton, Faz 4 rate limit |
| Sağlık/hassas kategori yorumu | KVKK hassasiyeti | Prompt kuralı; `saglik` kategorisi `suggestions`'ta yasak |

## 9. Açık sorular

- Yok (özel aralık v1.1'e ertelendi, karar verildi).

## 10. Referanslar

- Interactions API, structured output, thinking: https://ai.google.dev/gemini-api/docs/interactions , https://ai.google.dev/gemini-api/docs/structured-output , https://ai.google.dev/gemini-api/docs/thinking
- Google Generative AI Prohibited Use Policy: https://policies.google.com/terms/generative-ai/use-policy
- SQLAlchemy SQLite upsert: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#insert-on-conflict-upsert
- Pydantic `Field(max_length)` (iterable): https://docs.pydantic.dev/latest/api/fields/
- Doğrulama notu: [../reference/tech-verification-2026-09-16.md](../reference/tech-verification-2026-09-16.md)

## Changelog

- 2026-09-16 taslak oluşturuldu (monolit plandan bölündü; kuruş alanları, `UNIQUE(user_id, period)`, `not_enough_data`, eşzamanlılık kilidi, sağlık kategorisi kuralı, token kaydı eklendi)
- 2026-09-16 doğrulama turu 1: `period` yalnızca ay + regex, `recurring` algoritması, `LLMClient` Protocol adı, şema temizleme + smoke test, `in_progress` set (Lock yerine), hata gövdesi formatı, `saglik` validator, `max_output_tokens`, `stale`/`source_txn_count`, finansal danışmanlık uyarısı, upsert `updated_at`
- 2026-09-16 §3: Faz 3 KK-1..KK-7 işaretlendi (dashboard `bitti`)
