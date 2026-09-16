# Güvenlik ve KVKK Kontrol Listesi

Durum: taslak · Tarih: 2026-09-16 · Kapanış: [Faz 5](phases/faz-5-cloud-run.md) F5-T12 · Sorumlu: geliştirici

Her madde işaretlenirken yanına tarih ve kanıt (test adı, PR, ekran görüntüsü yolu) yazılır. Bu dosya kapalı beta öncesi tamamen kapanmadan deploy yapılmaz.

## 1. Veri envanteri

| Veri | Kaynak | Nerede | Süre | Hukuki sebep |
|---|---|---|---|---|
| E-posta, şifre hash'i (argon2id) | Kayıt | SQLite `users` + Litestream replikası | Hesap silinene kadar; yedekte +30 gün | Sözleşme (hizmet) |
| KVKK ve Gemini onay zaman damgaları | Kayıt | `users.consent_*_at` | Hesap ömrü + 30 gün | Yasal yükümlülük (ispat) |
| Orijinal ekstre PDF'i | Upload | **Yalnızca bellek**, işlem süresince | Saniyeler | İşlenmez, saklanmaz |
| Maskelenmiş PDF | Upload | Bellek (önizleme, 10 dk); kullanıcı açarsa GCS `ekstre-files-prod` | 10 dk / kullanıcı silene kadar (lifecycle 90 gün) | Açık rıza (opsiyon) |
| Maskelenmiş PDF (Gemini'ye giden) | Upload | Google Gemini API (ücretli tier; ürün geliştirmede kullanılmaz, kötüye kullanım tespiti için sınırlı süre log) | Google politikası | Açık rıza (yurt dışı aktarım) |
| İşlem satırları (tarih, açıklama, tutar, kategori, işyeri) | Gemini çıktısı | SQLite `transactions` | Hesap silinene kadar; yedekte +30 gün | Sözleşme + açık rıza |
| Agregat harcama özeti | Hesaplama | Gemini API'ye gönderilir (`description` yok) | Google politikası | Açık rıza |
| Tavsiye metni | Gemini çıktısı | SQLite `advice` | Hesap silinene kadar | Sözleşme |
| IP adresi, user-agent | İstek | `audit_log` (günlük temizleyici), Cloud Logging | 90 gün | Meşru menfaat (güvenlik) |
| Token kullanımı ve maliyet | Gemini yanıtı | `statements`, `advice` | Hesap ömrü | Meşru menfaat |

**Özel nitelikli veri notu:** İşlem satırları sağlık harcaması (eczane, hastane) içerebilir; KVKK md. 6 kapsamında özel nitelikli veri sayılır. Aydınlatma metni bunu açıkça belirtir; tavsiye promptu sağlık kategorisi hakkında yorum üretmez (Faz 3.5).

**Regex maskelemenin sınırı:** Havale/EFT açıklamalarındaki üçüncü kişi adları, işyeri adları ve adres benzeri metinler regex ile tam yakalanamaz. Kullanıcıya "kimlik, hesap, kart, iletişim bilgileri maskelenir; işlem açıklamaları maskelenmiş haliyle Gemini'ye gider" denir, "tam anonimlik" vaadi verilmez.

## 2. KVKK — hukuki

- [ ] **Aydınlatma metni** `docs/kvkk-aydinlatma.md` yazıldı; kayıt ekranında link + onay kutusu. İçerik: veri sorumlusu kimliği ve iletişim, işlenen veriler (§1 tablosu), amaç, hukuki sebep, **yurt dışına aktarım** (Google Cloud `europe-west1` + Gemini API; açık rıza), saklama süreleri (yedek dahil 30 gün), silme/düzeltme/itiraz hakları ve başvuru yolu (e-posta), özel nitelikli veri (sağlık harcaması) uyarısı.
- [ ] **Açık rıza** ayrı kutu: "Maskelenmiş ekstremin ve harcama özetimin Google Gemini API'ye (yurt dışı) gönderilmesini kabul ediyorum." Kayıtta `consent_gemini_at` zorunlu.
- [ ] **Gizlilik politikası** ve **kullanım şartları** sayfaları (`/privacy`, `/terms`, statik; Faz 4 F4-T12).
- [ ] **VERBİS** yükümlülüğü kontrol edildi (çalışan sayısı / bilanço eşiği; gerçek kişi geliştirici için muafiyet olasılığı; KVKK Kurulu güncel kararlarına bak). `[NETLEŞTİRİLMELİ: hukuki görüş]`
- [ ] Google Cloud **Data Processing Addendum** kabul edildi; Gemini API **ücretli tier** açık (AI Studio faturalama). Deploy öncesi https://ai.google.dev/gemini-api/terms tekrar okundu, tarih yazıldı.
- [ ] Yurt dışı aktarım için KVKK md. 9 kapsamındaki güncel mekanizma (standart sözleşme / açık rıza) değerlendirildi. `[NETLEŞTİRİLMELİ: hukuki görüş]`
- [ ] Veri ihlali bildirim planı (72 saat, KVKK Kurulu + kullanıcılar): kim, nasıl.

## 3. Veri minimizasyonu — teknik

- [ ] Orijinal PDF diske/bucket'a hiç yazılmıyor: upload ham gövde (multipart/`UploadFile` yok, Starlette geçici dosyaya yazar); Faz 1 KK-4 ve Faz 3 KK-4 grep testleri CI'da.
- [ ] `gcloud run deploy --source` ile Cloud Build'e giden dosyalar arasında `tests/private`, `.env`, `.venv` yok (`.gcloudignore`, Faz 5 KK-5).
- [ ] Maskelenmiş PDF saklama varsayılan **kapalı** (Faz 4 `keep_masked_pdf=false`).
- [ ] Sızıntı testi her upload'da zorunlu; başarısızsa Gemini çağrısı yok (Faz 1 §5.3 adım 10, Faz 3 iş akışı).
- [ ] Log'larda PDF içeriği, işlem açıklaması, e-posta, PDF şifresi yok: structlog redaction processor + `caplog` testi (Faz 4 KK-5).
- [ ] Gemini'ye giden payload'da kullanıcı kimliği, e-posta yok (Faz 2 KK-7, Faz 3.5 KK-1).
- [ ] Tavsiye agregatında `description` yok (Faz 3.5 KK-1).
- [ ] Hesap silme uçtan uca test edildi: DB satırları, GCS artifact, refresh token'lar (Faz 4 KK-3). Yedeklerden silinme: Litestream snapshot retention 72 sa + bucket noncurrent 30 gün → aydınlatma metninde "30 gün".
- [ ] Veri indirme (JSON/CSV) çalışıyor (Faz 4).
- [ ] Önizleme bytes'ı 10 dk sonra bellekten düşüyor (Faz 3).

## 4. Uygulama güvenliği

- [ ] HTTPS only (Cloud Run); `Strict-Transport-Security: max-age=31536000; includeSubDomains` (Faz 5).
- [ ] CSP `default-src 'self'; img-src 'self' data:; style-src 'self'`; üretim build'inde inline script/style yok; konsolda ihlal yok (Faz 3 KK-6).
- [ ] `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`.
- [ ] CORS yok (aynı origin); `CORSMiddleware` eklenmemiş.
- [ ] Upload: ≤ 15 MB, `%PDF-` magic byte, ≤ 60 sayfa, JavaScript / gömülü dosya / form reddi (Faz 1 sanitize, Faz 3 T03).
- [ ] Şifreli PDF şifresi yalnızca istek gövdesinde; loglanmaz, DB'ye yazılmaz.
- [ ] Rate limit: login 5/dk/IP + 5/dk/e-posta, register 3/saat/IP, upload 10/saat/kullanıcı, advice 5/saat/kullanıcı, export 3/saat/kullanıcı; IP anahtarı `X-Forwarded-For` son girdisi, sahte XFF ile aşılamıyor (Faz 4 KK-4).
- [ ] Şifre politikası 10–128 karakter; argon2id varsayılan parametreler; `check_needs_rehash`; kullanıcı yokken sahte hash (sabit süre); `pending_approval` yalnızca doğru şifrede.
- [ ] Access token 15 dk, bellekte, `sub` string; refresh token opak, hash'li, 30 gün, aile mutlak süresi 30 gün, `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`, rotasyon + aile bazlı yeniden kullanım tespiti, `Sec-Fetch-Site` kontrolü (Faz 4 KK-1).
- [ ] Admin "tüm oturumları kapat" access token'ları da düşürüyor (`sessions_revoked_at`).
- [ ] Yetkilendirme: her sorgu `user_id` filtreli; başka kullanıcının kaydı `404` (Faz 3 KK-5).
- [ ] Admin JSON API `is_admin`, admin olmayana 404; admin aksiyonları audit'te; `audit_log.meta_json` e-posta içermez (Faz 4 KK-6).
- [ ] Secret'lar yalnızca Secret Manager (sabit sürüm); repoda `.env.example`; `git log -p | grep -i "api_key"` temiz.
- [ ] Bağımlılık taraması CI'da: `pip-audit`, `npm audit --audit-level=high` (Faz 5 T08).
- [ ] `SECURITY.md` + sorumlu ifşa e-postası (Faz 4 F4-T12).
- [ ] Bakım bayrağı tüm yazma uçlarını kapatıyor (mimari §6 listesi; Faz 3 T03, Faz 3.5 T04, Faz 4 T09 testleri).
- [ ] Günlük Gemini bütçe eşiği (`GEMINI_DAILY_BUDGET_USD`) ve AI Studio kota sınırı.
- [ ] Bakım bayrağı ile deploy runbook'u uygulanıyor (Faz 5 §5.5).

## 5. Operasyon

- [ ] Litestream restore tatbikatı yapıldı, süre < 5 dk, `integrity_check` ok (Faz 5 KK-3); tarih: ____
- [ ] Cloud Monitoring alarmları: 5xx oranı, `/api/healthz`, bellek, container restart, `extract_failed`, Litestream hata sayaçları, günlük maliyet (Faz 5 T11).
- [ ] Litestream GCS smoke testi yapıldı (0.5.17 regresyon #1512); sürüm sabit.
- [ ] DB bucket versioning açık, noncurrent 30 gün; artifact bucket 90 gün lifecycle.
- [ ] Erişim: GCP projesinde yalnızca geliştirici hesabı + iki servis hesabı (runtime, deploy); 2FA açık.
- [ ] Olay müdahale notu: Gemini kesintisi, kota aşımı, DB bozulması için ilk adımlar `docs/runbooks/` altında.

## 6. Kapanış

- [ ] Tüm maddeler işaretli, kanıt linkli. Kapanış tarihi: ____ · Onaylayan: ____
