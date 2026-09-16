# Riskler ve Zaman Planı

Durum: onaylı · Tarih: 2026-09-16

## 1. Zaman planı (tek geliştirici, tahmini)

Monolit plandaki 7 haftalık tahmin, doğrulama turunda ortaya çıkan ek işler (şifreli PDF, sentetik fixture, bağımsız sızıntı testi, parça dedupe, 8 UI primitifi, deploy runbook'u) nedeniyle 10 haftaya çıkarıldı.

| Faz | Süre | Kümülatif | Çıktı |
|---|---|---|---|
| [Faz 1](phases/faz-1-masking.md) | 1,5 hafta | 1,5 | CLI maskeleme, profil, verify, sentetik fixture |
| [Faz 2](phases/faz-2-extraction-sqlite.md) | 1,5 hafta | 3 | Gemini çıkarım, SQLite, CLI listeleme, kayıtlı yanıt testleri |
| [Faz 3](phases/faz-3-dashboard.md) | 3 hafta | 6 | HTTP API + dashboard |
| [Faz 3.5](phases/faz-3.5-ai-advice.md) | 4 gün | 6,8 | AI öneri kutusu |
| [Faz 4](phases/faz-4-auth-admin.md) | 1,5 hafta | 8,3 | Auth, ayarlar, admin, audit, rate limit |
| [Faz 5](phases/faz-5-cloud-run.md) | 1 hafta | 9,3 | Docker, Litestream, Cloud Run, CI, runbook'lar |
| [KVKK / güvenlik](security-kvkk.md) | 3-4 gün (Faz 4-5 ile paralel) | 10 | Metinler, kontrol listesi kapanışı |
| **Toplam** | **~10 hafta** | | Kapalı beta |

Kritik yol: Faz 1 → 2 → 3 → 4 → 5. Faz 3.5 ve KVKK metinleri paralel yapılabilir. Faz 3 en riskli süre tahmini (UI primitifleri); 3 haftayı aşarsa `DateRange` ve `Dialog` basitleştirilir, Toast kaldırılır.

## 2. Program düzeyi riskler

| Risk | Olasılık | Etki | Önlem | Sahip faz |
|---|---|---|---|---|
| Regex maskeleme kişisel adı kaçırır (havale açıklaması) | Yüksek | Kişisel veri Gemini'ye gider | `verify` bağımsız sezgiler, kullanıcı terimleri, aydınlatma metninde açık ifade, "tam anonimlik" vaadi yok | 1, 4, KVKK |
| Banka ekstre formatı değişir | Orta | Profil kaçırır, upload durur | `verify` her upload'da zorunlu; fail → kullanıcıya "profil güncellenmeli"; generic profil fallback | 1 |
| Şifreli / taranmış ekstre | Yüksek / Orta | Açılamaz / maskelenemez | Şifre alanı; taranmış reddedilir, v2 OCR | 1, 3 |
| Gemini Interactions API şema değişikliği veya model deprecation | Orta | Çıkarım kırılır | SDK pin, model adı config'te, changelog takibi, kayıtlı yanıt testleri | 2 |
| Kategori doğruluğu düşük | Orta | Güven kaybı | `confidence`, `needs_review`, kullanıcı düzeltmesi, v1.1 merchant kuralları ve few-shot | 2, 3 |
| Deploy geçişinde iki Litestream süreci aynı replikayı hedefler (resmen desteklenmiyor) | Orta | Restore edilemez replika, veri kaybı | Bakım bayrağı, `--no-traffic --tag canary`, kesişme < 2 dk, `litestream reset` runbook'u, bucket versioning | 5 |
| Litestream 0.5.16/17 GCS asılma regresyonu (#1512) | Orta | Replikasyon sessizce durur | Smoke test, `0.5.15` fallback, hata sayacı alarmı | 5 |
| Orijinal PDF'in yanlışlıkla diske inmesi (multipart geçici dosya, `--source` yüklemesi) | Orta | Gizlilik iddiası çöker | Ham gövde upload, grep testleri, `.gcloudignore`, `.dockerignore` | 3, 5 |
| Bellek aşımı (DB + PDF + Python, 1 GiB) | Orta | OOM restart, yarım işler | Semaphore(2), in-memory volume limiti, bellek alarmı, DB boyut izleme | 3, 5 |
| Tek instance çöker | Düşük | Kısa kesinti, bellekteki işler kaybolur | Litestream 1 sn sync; Cloud Run yeniden başlatır; yarım işler açılışta `mask_failed`/`extract_failed` + `restart`, kullanıcı yeniden yükler | 3, 5 |
| Maliyet patlaması | Düşük | Bütçe | `thinking_level: low`, native PDF metni ücretsiz, günlük bütçe eşiği, rate limit; fiyat 1 Ocak 2027'de 2x | 2, 4 |
| KVKK yurt dışı aktarım / özel nitelikli veri | Orta | Hukuki | Açık rıza + aydınlatma; sağlık kategorisi tavsiyede yasak; v2 Vertex AI EU | KVKK |
| Silinen veri yedekte 30 gün kalır | Kesin | KVKK silme süresi | Aydınlatma metninde 30 gün; retention sabit | 4, 5, KVKK |
| PyMuPDF AGPL lisansı | Düşük (kapalı beta) | Ticari kullanımda lisans | Kapalı beta sonrası ticari lisans değerlendirmesi | ADR-0003 |
| Zaman aşımı (tek geliştirici) | Yüksek | Beta gecikir | Faz 3 kapsam kırpma planı; Faz 3.5 ertelenebilir | Tümü |

## 3. Kapsam kırpma sırası (gerekirse)

1. Faz 3.5 AI öneri → v1.1'e ertele.
2. Faz 3 `DateRange` → iki `<input type="date">`; `Toast` → satır içi mesaj.
3. Faz 4 admin paneli → yalnızca CLI komutları (`cli.py user approve EMAIL`).
4. Faz 4 veri indirme → JSON yalnız, CSV yok.

Kırpılamaz: Faz 1 sızıntı testi, Faz 4 hesap silme, KVKK metinleri, Faz 5 restore tatbikatı.
