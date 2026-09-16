# ADR-0001: Gemini 3.8 Flash + Interactions API

Durum: kabul edildi · Tarih: 2026-09-16 · İlgili faz: Faz 2, Faz 3.5

## Bağlam ve problem

Maskelenmiş PDF'ten yapılandırılmış işlem listesi çıkaracak ve agregat verilerden tavsiye üretecek bir LLM gerekiyor. Maliyet, Türkçe kalitesi, native PDF desteği ve şema zorlama (structured output) belirleyici.

## Değerlendirilen seçenekler

- Gemini 3.8 Flash, Interactions API (`client.interactions.create`)
- Gemini 3.8 Flash, `generateContent` (legacy)
- Gemini 3.5 Flash (Stable, daha eski)
- Claude / OpenAI (native PDF var ama metin katmanı ücretsiz değil, TR fiyat avantajı yok)

## Karar

"Gemini 3.8 Flash + Interactions API", çünkü:

- 3.8 Flash GA (2 Eylül 2026), 1M giriş / 64k çıkış, `thinking_level` ile maliyet kontrolü.
- Google `generateContent`'i legacy ilan etti; yeni projede Interactions ile başlamak ileride migrasyon gerektirmez.
- PDF'in gömülü metin katmanı ücretsiz token olarak işleniyor (bkz. ADR-0002).
- Ücretli tier'da veriler ürün geliştirmede kullanılmıyor (KVKK için şart).

Uygulama kuralları:

- SDK: `google-genai >= 2.3.0` (Mayıs 2026 `outputs` → `steps` şema değişikliği sonrası).
- Yanıt: `interaction.output_text`. Token sayımı: `interaction.usage.total_input_tokens` / `total_output_tokens` / `total_thought_tokens`.
- Structured output: `response_format={"type":"text","mime_type":"application/json","schema": Model.model_json_schema()}`. Pydantic sınıfı doğrudan verilmez.
- `thinking_level`: çıkarım için `low`, tavsiye için `medium`. `minimal` 3.8 Flash'ta hata döner.
- `temperature`, `top_p`, `top_k`, `candidate_count` gönderilmez.
- Async: `client.aio.interactions.create`.
- Model adı config'te (`GEMINI_MODEL`), kodda sabit değil.

## Sonuçlar

- İyi: Düşük maliyet (tanıtım fiyatı $0,75 / $3,75 per 1M token), tek SDK, şema garantisi.
- Kötü: Tanıtım fiyatı 31 Aralık 2026'da bitiyor, sonrası iki katı ($1,50 / $7,50). Interactions API görece yeni; şema değişiklikleri olabilir (changelog takibi gerekli). Developer API'de EU veri yerleşimi yok; gerekirse Vertex AI EU + servis hesabı.
- Doğrulama tarihi ve kaynak: 2026-09-16, https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash , https://ai.google.dev/gemini-api/docs/interactions , https://ai.google.dev/gemini-api/docs/structured-output , https://ai.google.dev/gemini-api/docs/pricing
