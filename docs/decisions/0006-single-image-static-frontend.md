# ADR-0006: Tek image, frontend FastAPI'den servis

Durum: kabul edildi · Tarih: 2026-09-16 · İlgili faz: Faz 3, Faz 5

## Bağlam ve problem

Frontend (Vite build) ve backend (FastAPI) ayrı mı dağıtılmalı? Ayrı dağıtım CORS, iki deploy, iki domain, cookie SameSite karmaşıklığı getirir.

## Değerlendirilen seçenekler

- Tek Docker image: Vite `dist/` FastAPI tarafından servis edilir
- Frontend Cloud Storage + CDN, backend Cloud Run (ayrı origin)
- Frontend Firebase Hosting, backend Cloud Run

## Karar

"Tek image", çünkü aynı origin: CORS gerekmez, refresh token cookie `SameSite=Strict` çalışır, CSP `default-src 'self'` yeterli, tek deploy.

Uygulama kuralları:

- FastAPI ≥ 0.141: `app.frontend("/", directory="static", fallback="index.html", check_dir=False)`. Bu API route'larını her zaman önce eşler ve yalnızca `Accept: text/html` isteklerinde `index.html` döner; `StaticFiles(html=True)` + sıralama hilesi kullanılmaz. `check_dir=False` şart: varsayılan `"auto"` yalnızca `FASTAPI_ENV=development` iken eksik dizini tolere eder.
- Vite build çıktısı repo kökündeki Dockerfile'da `COPY --from=fe /fe/dist ./static`; `build.assetsInlineLimit = 0` (CSP için `data:` URI yok).
- Lokal geliştirmede Vite dev server `server.proxy` ile `/api` → `http://localhost:8000`.
- Vite üretim çıktısı inline script içermez; CSP `script-src 'self'` ile uyumlu.

## Sonuçlar

- İyi: Tek deploy, tek domain, basit güvenlik başlıkları.
- Kötü: Frontend değişikliği için backend imajı yeniden build edilir (CI'da 2-3 dk). CDN yok; Cloud Run static dosyaları servis eder (kapalı beta için sorun değil).
- Doğrulama tarihi ve kaynak: 2026-09-16, https://fastapi.tiangolo.com/tutorial/frontend/ , https://vite.dev/config/server-options
