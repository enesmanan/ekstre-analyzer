# Faz 4 — JWT Auth + Kullanıcı Ayarları + Admin

| Durum | Tarih | Süre tahmini | Bağımlılık |
|---|---|---|---|
| onaylı | 2026-09-16 | 1,5 hafta | Faz 3.5 bitti |

Önceki: [Faz 3.5](faz-3.5-ai-advice.md) · Sonraki: [Faz 5](faz-5-cloud-run.md) · İlgili: [security-kvkk.md](../security-kvkk.md)

## 1. Amaç

Çok kullanıcılı kapalı betaya hazırlık: kayıt/giriş, oturum yönetimi, kullanıcı ayarları (profil, ek maskeleme terimleri, maskelenmiş PDF saklama opsiyonu), veri indirme ve hesap silme, admin API'si ve ekranı, audit log, rate limit. Faz bitince dev user pasiftir ve her istek JWT ile kimliklenir.

## 2. Kapsam / Kapsam dışı

- Kapsam: `/auth/*`, argon2id, PyJWT access token, opak refresh token (rotasyon, aile bazlı yeniden kullanım tespiti, mutlak oturum süresi), `HttpOnly` cookie, `Sec-Fetch-Site` kontrolü, slowapi rate limit (IP ve e-posta/kullanıcı anahtarlı), admin onaylı kayıt, ayarlar, veri dışa aktarma, hesap silme, artifact saklama soyutlaması (lokal FS; Faz 5'te GCS), admin JSON API + React `/admin` ekranı, audit log, frontend giriş akışı.
- Kapsam dışı: E-posta doğrulama ve şifre sıfırlama (v1.1; kapalı betada admin elle), OAuth, 2FA, RS256 (v2), KVKK metinlerinin yazımı ([security-kvkk.md](../security-kvkk.md); `kvkk-aydinlatma.md` bu fazda F4-T12 ile yazılır).

## 3. Ön koşullar

- [ ] Faz 3.5 KK'ları geçti
- [ ] `JWT_SECRET` (≥ 32 byte rastgele) `.env` içinde; `.env.example` güncel
- [ ] `ARTIFACT_DIR` lokal yol (Faz 5'te `ARTIFACT_BUCKET`)

## 4. Teslimatlar

| Teslimat | Açıklama |
|---|---|
| `backend/app/auth/{passwords,tokens,deps,router}.py` | Şifre hash, JWT, refresh token, `get_current_user` (Faz 3'teki sabit dependency'nin yerine) |
| `backend/app/api/{settings,export,account,admin}.py` | Ayarlar, dışa aktarma, silme, admin JSON API |
| `backend/app/storage/{base,local,gcs}.py` | `ArtifactStorage` Protocol; Faz 4 `LocalStorage`, Faz 5 `GcsStorage` |
| `backend/app/ratelimit.py`, `app/audit.py` | slowapi kurulumu, özel 429 gövdesi; audit yardımcıları |
| `backend/app/db/alembic/versions/0003_auth.py` | `refresh_tokens`, `audit_log`, `users` yeni sütunlar, dev user pasif |
| `frontend/src/pages/{Login,Register,Admin}.tsx`, `src/auth/*` | Token bellekte, açılışta refresh, 401 yakalama, Web Locks ile tek uçuş |
| `docs/kvkk-aydinlatma.md` | Aydınlatma metni (kayıt ekranından link) |

## 5. Tasarım

### 5.1 Veri modeli (ek)

`users` tablosunda `is_active`, `is_admin`, `settings_json` Faz 2 migration'ında zaten var; `0003_auth` yalnızca yeni sütunlar ekler:

```
users           + approved_at, last_login_at, consent_kvkk_at, consent_gemini_at,
                  sessions_revoked_at, deleted_at
                  settings_json: {profile, extra_terms: [..], keep_masked_pdf: false}
refresh_tokens  id PK, user_id FK, token_hash (sha256), family_id, family_expires_at,
                created_at, expires_at, revoked_at, replaced_by_id
audit_log       id PK, user_id FK nullable, action, meta_json, ip, created_at
                action ∈ {register, login, login_failed, refresh_reuse, logout, upload,
                          delete_statement, export, delete_account, admin_approve,
                          admin_deactivate, admin_revoke_sessions, admin_maintenance}
```

`audit_log.ip` ve `meta_json` kişisel veridir: saklama 90 gün (günlük temizleyici), `meta_json`'a asla e-posta veya açıklama yazılmaz (yalnızca id'ler ve sayılar). Dev user (`id=1`) migration'da `is_active=0`; testler kendi kullanıcısını oluşturur.

### 5.2 Auth akışı

| Uç nokta | Davranış |
|---|---|
| `POST /auth/register` `{email, password, consent_kvkk: true, consent_gemini: true}` | Şifre 10–128 karakter; iki onay zorunlu (`consent_*_at`). `is_active=0`; yanıt "onay bekliyor". Rate limit `3/saat/IP`. |
| `POST /auth/login` `{email, password}` | Kullanıcı yoksa veya `password_hash` boşsa (silinmiş) açılışta üretilmiş sahte hash doğrulanır (sabit süre). Şifre yanlış → `401 invalid_credentials` + `login_failed` audit. Şifre doğru ama `is_active=0` → `403 pending_approval` (yalnızca doğru şifrede; onay bekleyen e-postalar sayılamasın). Doğru → `{access_token, expires_in}` + `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`. `check_needs_rehash` ile parametre yükseltme. Rate limit `5/dk/IP` **ve** `5/dk/e-posta`. |
| `POST /auth/refresh` (cookie) | Önce `Sec-Fetch-Site ∈ {same-origin, none}` (yoksa `Origin` eşleşmesi), değilse `403`. Token hash'i bul. `revoked_at` **ve** `replaced_by_id` doluysa **yeniden kullanım**: aynı `family_id`'deki tüm token'ları iptal et, `refresh_reuse` audit, `401`. `expires_at` veya `family_expires_at` geçmişse düz `401`. Geçerliyse yeni token: `expires_at = min(now + 30 gün, family_expires_at)`, eskisi `revoked_at` + `replaced_by_id`; yeni cookie + yeni access token. |
| `POST /auth/logout` | Aynı `Sec-Fetch-Site` kontrolü; cookie'deki token'ın ailesini iptal et; cookie sil. |

- Access token: PyJWT `HS256`, `sub=str(user.id)` (PyJWT ≥ 2.10 string zorunlu), `exp` 15 dk, `iat`, `jti`; decode `jwt.decode(t, key, algorithms=["HS256"], options={"require": ["exp", "iat", "sub", "jti"]}, leeway=10)`. Frontend bellekte tutar (localStorage yok).
- Refresh: 32 byte `secrets.token_urlsafe`, DB'de yalnızca sha256, 30 gün; **aile mutlak süresi** `family_expires_at = ilk token created_at + 30 gün` (kayan pencere ile sonsuz oturum yok; OWASP absolute timeout).
- Cookie `Path=/api/v1/auth` diğer isteklerde gönderilmez (güvenlik sınırı değil, gürültü azaltma); `SameSite=Strict` + aynı origin (ADR-0006, `run.app` Public Suffix List'te) CSRF'i keser; `Sec-Fetch-Site` ikinci katman. `Secure` her ortamda açık (tarayıcılar `localhost`'ta https şartını yok sayar).
- `get_current_user`: Bearer doğrula → `users` satırı; `is_active=0` veya `deleted_at` dolu → `401`; `iat < sessions_revoked_at` → `401` (admin "tüm oturumları kapat" access token'ı da düşürür). Admin uçları ek `is_admin`; admin olmayana `404`.

### 5.3 Rate limit

`slowapi` 0.1.10 (bellek içi; tek instance). `key_func(request)` yalnızca `request` alır; `get_current_user` `request.state.user_id` yazar, kullanıcı anahtarlı limitler bunu okur. Endpoint imzasında `request: Request` zorunlu; `@router.post` dekoratörü `@limiter.limit`'in üstünde. Varsayılan 429 gövdesi Faz 3 formatına çevrilir: `{"error": {"code": "rate_limited"}}`.

IP anahtarı: uvicorn `--proxy-headers --forwarded-allow-ips="*"` `X-Forwarded-For`'un **en soldaki** girdisini alır ve Cloud Run istemcinin gönderdiği XFF'e gerçek IP'yi **ekler**, silmez; soldaki değer sahte olabilir. Prod'da `key_func` XFF'in **son** girdisini kullanır (Cloud Run önünde başka LB yok); dev'de `request.client.host`. IP'den bağımsız e-posta/kullanıcı limitleri ikinci katmandır.

| Uç | Limit |
|---|---|
| `POST /auth/login` | 5/dk/IP + 5/dk/e-posta |
| `POST /auth/register` | 3/saat/IP |
| `POST /statements` | 10/saat/kullanıcı |
| `POST /advice` | 5/saat/kullanıcı |
| `POST /export` | 3/saat/kullanıcı |

### 5.4 Kullanıcı ayarları (`/api/v1/settings`)

- `profile`: banka profili adı veya `auto`.
- `extra_terms`: serbest metin listesi (ad, adres, işyeri adı); her biri 3–64 karakter, ≤ 20 adet; Faz 1 `mask(..., extra_terms=...)` parametresine gider ve orada `(?<!\w)re.escape(term)(?!\w)` büyük/küçük harf duyarsız kelime sınırıyla uygulanır. Ham regex opsiyonu **yok** (ReDoS).
- `keep_masked_pdf` (default **false**): açıksa iş bitince maskelenmiş PDF `ArtifactStorage.put(f"users/{uid}/statements/{sid}.pdf")`. Kapalıysa hiç yazılmaz. Kapatınca mevcut artifact'ler silinir.

### 5.5 Veri indirme ve hesap silme

- `POST /export` → zip: JSON (`statements`, `transactions`, `advice`, `settings`) + CSV (`transactions`); `export` audit. Senkron üretim (< 5 MB beklenir).
- `DELETE /account` `{password}` → şifre doğrula; `transactions`, `statements`, `advice`, `refresh_tokens` sil; artifact'leri sil; `users` satırı: `email = "deleted-<id>@invalid"` (kişisel veri içermez; yeniden kayıt engeli istenirse ayrıca `sha256(email)` saklanır), `password_hash = ""`, `is_active=0`, `deleted_at`. `audit_log` satırları 90 gün sonra temizlenir. Yanıt sonrası cookie silinir. KVKK metni: yedeklerden silinme 30 gün (Litestream retention + bucket versioning).

### 5.6 Admin (`/api/v1/admin/*` JSON + React `/admin`)

Karar: Jinja2 paneli yok. Admin ekranı SPA içinde `/admin` route'u; API `Bearer` + `is_admin`; admin olmayana `404`. Ek oturum, CSRF token ve CSP istisnası gerekmez.

- `GET /admin/users`: e-posta, durum, kayıt tarihi, ekstre sayısı, toplam token, toplam tahmini maliyet, son giriş, hata oranı.
- `POST /admin/users/{id}/approve` (`is_active=1`, `approved_at`), `/deactivate`, `/revoke-sessions` (`sessions_revoked_at = now` + refresh aileleri iptal).
- `GET /admin/system`: bakım bayrağı, aktif ve bekleyen iş sayısı, günlük Gemini maliyeti ve eşik. `POST /admin/system/maintenance {on: bool}` → `app.state.maintenance` (süreç içi; ADR-0005).
- Günlük bütçe: `GEMINI_DAILY_BUDGET_USD`; aşılınca `POST /statements` ve `POST /advice` `503 budget_exceeded`.

### 5.7 Frontend

- `Login`, `Register` sayfaları; `Register` iki onay kutusu ve [kvkk-aydinlatma.md](../kvkk-aydinlatma.md) linki.
- Access token bellekte (module scope). Açılışta `POST /auth/refresh` → token; `401` gelince tek kez refresh dene, olmazsa `/login`. Sekmeler arası yarış: `navigator.locks.request("refresh", ...)` (Web Locks) + tek uçuşluk promise; grace period yok.
- `Settings`: profil, terim listesi, `keep_masked_pdf`, "Verilerimi indir", "Hesabı sil" (şifre onaylı Dialog).
- `Admin`: kullanıcı tablosu ve aksiyon butonları, sistem kutusu.

### 5.8 Bilinen tuzaklar

- `SameSite=Strict` ile dış linkten gelen ilk istekte cookie gitmez; SPA açılışta refresh'i uygulama içinden çağırır, sorun değil.
- argon2 hash ~ 50-100 ms; login limitleri CPU'yu korur. Sahte hash açılışta aynı parametrelerle bir kez üretilir.
- Silinmiş hesabın boş `password_hash`'i `argon2` `InvalidHashError` fırlatır; sahte hash yoluna düşürülür.
- slowapi FastAPI 0.141 ile resmi uyumluluk notu yok; F4-T05 doğrular, sorun çıkarsa 30 satırlık bellek içi limiter aynı arayüzle.

## 6. Görevler

- [ ] F4-T01 Bağımlılıklar — `backend/pyproject.toml`
      Komut: `uv add pyjwt argon2-cffi slowapi && uv add --dev freezegun`
      Doğrula: `uv run python -c "import jwt, argon2, slowapi; print(jwt.__version__)"`
- [ ] F4-T02 Migration `0003_auth` (yalnızca yeni sütunlar; refresh_tokens, audit_log; dev user pasif) — `backend/app/db/alembic/versions/0003_auth.py`
      Doğrula: `uv run alembic -c app/db/alembic.ini -x db=/tmp/t.db upgrade head` (Faz 2 DB'si üzerinde `ADD COLUMN` çakışması yok)
- [ ] F4-T03 [P] Şifre ve token yardımcıları — `backend/app/auth/{passwords,tokens}.py`
      Doğrula: `uv run pytest tests/test_auth_tokens.py -q` (süresi geçmiş JWT reddediliyor; `sub` string; `require` claim'leri eksikse hata; refresh hash DB'de düz token yok)
- [ ] F4-T04 Auth router + `get_current_user` değişimi + audit — `backend/app/auth/{router,deps}.py`, `app/audit.py`
      Doğrula: `uv run pytest tests/test_auth_flow.py -q` (register → pending; admin onayı → login; yanlış şifre + pending → `invalid_credentials`; refresh rotasyonu; iptal edilmiş+değiştirilmiş refresh tekrar → tüm aile iptal + 401; süresi geçmiş refresh → düz 401; `family_expires_at` sonrası refresh reddi (freezegun); `Sec-Fetch-Site: cross-site` → 403; `sessions_revoked_at` sonrası eski access token 401; logout)
- [ ] F4-T05 [P] Rate limit — `backend/app/ratelimit.py`
      Doğrula: `uv run pytest tests/test_ratelimit.py -q` (6. login denemesi 429 ve gövde `rate_limited`; sahte `X-Forwarded-For: 1.2.3.4` ile limit aşılamıyor; aynı e-posta farklı IP'lerden 6. deneme 429)
- [ ] F4-T06 [P] Artifact storage soyutlaması (local) — `backend/app/storage/{base,local}.py`
      Doğrula: `uv run pytest tests/test_storage.py -q`
- [ ] F4-T07 Ayarlar + `extra_terms` + `keep_masked_pdf` — `app/api/settings.py`, `app/jobs.py`
      Doğrula: `uv run pytest tests/test_settings.py -q` (3 karakterden kısa terim 422; terim eklenince sentetik ekstrede o metin maskeleniyor, kısmi kelime maskelenmiyor; `keep_masked_pdf=false` iken storage boş; `true` iken dosya var; kapatınca siliniyor)
- [ ] F4-T08 [P] Dışa aktarma ve hesap silme — `app/api/{export,account}.py`
      Doğrula: `uv run pytest tests/test_account.py -q` (zip içinde JSON+CSV; silme sonrası tablolar ve storage boş; `email` iskelet; audit satırı var, `meta_json`'da e-posta yok)
- [ ] F4-T09 Admin API + günlük bütçe + bakım bayrağı — `app/api/admin.py`
      Doğrula: `uv run pytest tests/test_admin.py -q` (admin olmayan 404; onaylama; `revoke-sessions` sonrası access token 401; bütçe aşımında upload ve advice 503; bakım bayrağı toggle → upload, PATCH, advice, settings, export, account `503 maintenance`; auth ve admin uçları açık)
- [ ] F4-T10 Frontend auth akışı, ayarlar, admin ekranı — `frontend/src/auth/*`, `pages/{Login,Register,Settings,Admin}.tsx`
      Doğrula: `npm test -- auth` (401 → refresh → yeniden dene; refresh başarısız → /login; iki eşzamanlı 401'de tek refresh isteği)
- [ ] F4-T11 Güvenlik testi — `backend/tests/test_security.py`
      Doğrula: başka kullanıcının ekstresi 404; Bearer olmadan 401; CSP başlıkları var; `caplog`'da e-posta, şifre, PDF şifresi yok
- [ ] F4-T12 Aydınlatma metni, gizlilik/kullanım şartları sayfaları, `SECURITY.md`, onay akışı — `docs/kvkk-aydinlatma.md`, `frontend/src/pages/{Register,Privacy,Terms}.tsx`, `SECURITY.md`
      Doğrula: [security-kvkk.md](../security-kvkk.md) §2 ilk üç madde ve §4 `SECURITY.md` maddesi işaretlenebilir durumda; `/privacy` ve `/terms` route'ları render oluyor
- [ ] F4-T13 Bu dosyada Durum → bitti, changelog; `docs/README.md`

## 7. Kabul kriterleri

- KK-1: `tests/test_auth_flow.py` rotasyon, yeniden kullanım, mutlak süre ve oturum iptali senaryolarıyla geçer.
- KK-2: Düz refresh token yalnızca cookie'de; access token localStorage'a yazılmaz (`grep -rn localStorage frontend/src` boş).
- KK-3: Hesap silme sonrası kullanıcının `transactions`, `statements`, `advice`, `refresh_tokens` satırı ve artifact'i yok.
- KK-4: Rate limit'ler tabloya uygun; sahte XFF ile aşılamıyor.
- KK-5: Log'larda e-posta, şifre, PDF şifresi, işlem açıklaması yok (structlog processor + test).
- KK-6: `audit_log.meta_json` hiçbir satırda `@` içermez.

## 8. Riskler (bu faza özgü)

| Risk | Etki | Önlem |
|---|---|---|
| Refresh yeniden kullanım tespiti yanlış pozitif (sekme yarışı) | Kullanıcı düşer | Web Locks + tek uçuş; UI yeniden giriş mesajı |
| slowapi bakım temposu düşük | Güvenlik yaması gecikir | Aynı arayüzle bellek içi limiter fallback |
| XFF sahteciliği | Login limit aşımı | Son XFF girdisi + e-posta anahtarlı limit |
| `extra_terms` kötüye kullanımı | Ekstre okunmaz olur | Min 3 karakter, kelime sınırı |

## 9. Açık sorular

- Yok (admin paneli React + JSON API; grace period yerine Web Locks; e-posta iskeleti kişisel veri içermiyor).

## 10. Referanslar

- PyJWT (usage, `sub` string, `require`, `leeway`): https://pyjwt.readthedocs.io/en/stable/usage.html , changelog: https://pyjwt.readthedocs.io/en/stable/changelog.html
- argon2-cffi: https://argon2-cffi.readthedocs.io/en/stable/api.html
- slowapi: https://slowapi.readthedocs.io/
- OWASP CSRF, Session Management (absolute timeout), Authentication (timing): https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html , https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html , https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- Auth0 refresh token rotation: https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation
- MDN Set-Cookie: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie
- X-Forwarded-For güvenliği: https://adam-p.ca/blog/2022/03/x-forwarded-for/
- Web Locks API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API
- Doğrulama notu: [../reference/tech-verification-2026-09-16.md](../reference/tech-verification-2026-09-16.md)

## Changelog

- 2026-09-16 taslak oluşturuldu (monolit plandan bölündü; token ailesi ve yeniden kullanım tespiti, cookie Path, consent alanları, artifact storage soyutlaması, günlük bütçe, hesap silme detayı, regex opsiyonu kaldırıldı)
- 2026-09-16 doğrulama turu 1: `users` yalnızca yeni sütunlar, `sub` string + `require`/`leeway`, XFF son girdi + e-posta limiti, aile mutlak süresi, `sessions_revoked_at`, `Sec-Fetch-Site`, reuse tanımı, Web Locks, sahte hash ve `pending_approval` sırası, slowapi anahtar/gövde, admin React + JSON (Jinja2 kaldırıldı), audit 90 gün, bakım bayrağı süreç içi, `extra_terms` kelime sınırı, aydınlatma metni görevi
