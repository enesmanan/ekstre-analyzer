# Faz 3 — HTTP API + Dashboard

| Durum | Tarih | Süre tahmini | Bağımlılık |
|---|---|---|---|
| bitti | 2026-09-16 | 3 hafta | Faz 2 bitti |

Önceki: [Faz 2](faz-2-extraction-sqlite.md) · Sonraki: [Faz 3.5](faz-3.5-ai-advice.md) · İlgili ADR: [ADR-0006](../decisions/0006-single-image-static-frontend.md), [ADR-0007](../decisions/0007-frontend-stack-no-component-lib.md)

## 1. Amaç

Faz 1-2'deki CLI akışını HTTP API ve tarayıcı arayüzüne taşımak. Auth yok; tek "dev user" (id=1). Faz bitince: tarayıcıdan PDF yüklenir, ilerleme izlenir, maskelenmiş önizleme görülür, genel bakış ve işlem listesi çalışır, kategori düzeltilebilir.

## 2. Kapsam / Kapsam dışı

- Kapsam: FastAPI router'ları (`/api/v1`), arka plan işi (threadpool + semaphore), upload güvenlik kontrolleri ve gövde boyutu sınırı, önizleme PNG, özet uç noktası, React SPA (4 ekran, 8 primitif), Vite proxy, üretim build'inin FastAPI'den servisi, temel güvenlik başlıkları, bakım bayrağı.
- Kapsam dışı: Tavsiye kutusu ([Faz 3.5](faz-3.5-ai-advice.md)), kayıt/giriş/ayarlar/admin ([Faz 4](faz-4-auth-admin.md)), Docker ve deploy ([Faz 5](faz-5-cloud-run.md)), `merchant_rules` (v1.1), çoklu para birimi.

## 3. Ön koşullar

- [x] Faz 2 KK-1..KK-7 geçti; `extract_statement(statement, mask_result, db, client)` servis imzası sabit
- [x] Node 24 ve npm kurulu (`node --version` ≥ 22.22, react-router 8 şartı)
- [x] `GEMINI_API_KEY` `.env` içinde

## 4. Teslimatlar

| Teslimat | Açıklama |
|---|---|
| `backend/app/main.py` | FastAPI app, `/api/v1` router'ları, `/api/healthz`, güvenlik başlıkları middleware'i, `app.frontend(...)` ile SPA, `app.state.maintenance` |
| `backend/app/api/{statements,transactions,summary}.py` | Router'lar; `GET /categories` `transactions.py` içinde |
| `backend/app/jobs.py` | `process_statement(statement_id)` arka plan işi, bellek içi PDF deposu |
| `frontend/` | Vite 8 + React 19 + TS; `npm run dev`, `npm run build`, `npm test` (vitest) |
| `backend/tests/test_api_*.py`, `frontend/src/**/*.test.tsx` | API testleri `RecordedClient` ile; UI testleri vitest + Testing Library |

## 5. Tasarım

### 5.1 API (`/api/v1`)

| Metot | Yol | Açıklama |
|---|---|---|
| POST | `/statements` | **Ham gövde** `Content-Type: application/pdf` (multipart değil, bkz. 5.5). Opsiyonel başlıklar: `X-Statement-Password`, `X-Statement-Profile`. Gövde sınırı `JsonBodyLimitMiddleware` 15 MiB (Starlette `max_body_size` `include_router` ile düşer). Handler `await request.body()` ile bytes alır; threadpool'da: ilk 5 bayt `%PDF-` değilse `400 unsafe_pdf`; `pymupdf.open`; `needs_pass` ve şifre yoksa `400 password_required`; `authenticate()==0` ise `400 wrong_password`; `page_count > 60` ise `400 too_many_pages`; `sanitize.check`. Geçerse `statements` satırı `status=queued`, `masked_sha256="pending:"+uuid4()` ile açılır, bytes bellek deposuna konur, `202 {id}`. `app.state.maintenance` açıksa `503 maintenance`; bekleyen (`queued`) iş sayısı ≥ 4 ise `503 busy`. |
| GET | `/statements/{id}` | `status`, `error`, `issues` (`validation_issues_json`), `mask_warnings`, `page_count`, `bank`, `profile`, `statement_type`, `period_*`, `redaction_count`, token ve maliyet alanları |
| GET | `/statements` | Kullanıcının ekstreleri, `uploaded_at` desc |
| GET | `/statements/{id}/preview.png` | Maskelenmiş PDF'in 1. sayfası, threadpool'da `get_pixmap(dpi=100)`; yalnızca maskeleme sonrası bellekte tutulan bytes'tan üretilir, 10 dk sonra `404 preview_expired` (maskelenmiş PDF diske yazılmaz; kalıcı saklama Faz 4 opsiyonu) |
| DELETE | `/statements/{id}` | Ekstre + işlemler (CASCADE); bellek deposundaki bytes da silinir |
| GET | `/transactions` | Filtreler: `from`, `to`, `category` (etkin kategori), `direction`, `q` (açıklama; SQLite'ta `ILIKE` yok, SQLAlchemy `.ilike()` `lower() LIKE` üretir ve Türkçe İ/ı katlamaz, kabul edilir), `statement_id`, `page`, `page_size` (≤ 200). Yanıt `{items, total}`; item: `id, statement_id, txn_date, description, amount_kurus, currency, direction, category, user_override_category, effective_category, merchant_norm, confidence, is_installment, installment_no, installment_total` |
| PATCH | `/transactions/{id}` | `{category}` → `user_override_category`; `null` temizler; yanıt güncel item |
| GET | `/summary` | `from`, `to` zorunlu (`to` dahil). Yanıt: `total_debit_kurus`, `total_credit_kurus`, `prev_total_debit_kurus` (aynı gün sayısı kadar önceki aralık), `by_category: [{key, label_tr, kurus, count}]`, `daily: [{date, debit_kurus}]` (boş günler 0), `top: [{id, txn_date, merchant_norm, amount_kurus, effective_category}]` (10) |
| GET | `/categories` | `categories` tablosu |
| GET | `/api/healthz` (kök `/api` altında, sürümsüz) | `SELECT 1` → `{"ok": true}`; Faz 5'te Litestream kontrolü eklenir |

Kategori hesaplarında `effective_category = COALESCE(user_override_category, category)`. Tüm uç noktalar `user_id = current_user.id` ile filtreler; Faz 3'te `get_current_user` dependency sabit `User(id=1)` döner, Faz 4 bunu JWT ile değiştirir. Kullanıcıya ait olmayan kayıt `404` (`403` değil; varlık sızdırmaz).

Hata gövdesi: `{"error": {"code": "...", "message": "...", "issues": [...]}}`. Bu fazın kodları: `password_required`, `wrong_password`, `unsafe_pdf`, `scanned_pdf`, `too_large` (413), `too_many_pages`, `leak_detected`, `duplicate_statement`, `mask_failed`, `extract_failed`, `preview_expired`, `maintenance`, `busy`, `not_found`, `validation_error`. Sonraki fazlar kendi kodlarını ekler (Faz 3.5: `invalid_period`, `no_advice`, `not_enough_data`, `in_progress`; Faz 4: `invalid_credentials`, `pending_approval`, `rate_limited`, `budget_exceeded`).

### 5.2 Arka plan işi (`jobs.py`)

- Bellek deposu: `dict[int, PdfEntry(original, password, profile_name, masked, expires_at)]`.
- `POST` → `BackgroundTasks.add_task(process_statement, app, id)`. İş kendi Session'ını açar (istek session'ı 202 sonrası kapanır).
- `process_statement`: `status=masking` → `run_in_threadpool(mask, ...)`; `original` ve şifre **hemen** `None`. Maske hatası (`LeakDetected`, `UnsafePdf`, `ScannedPdf`, şifre) → `mask_failed` + kod, **istemci yok**, durur. Maske OK → Gemini **öncesi** `UPDATE masked_sha256=sha256(orijinal)` + commit; `IntegrityError` → `mask_failed`+`duplicate_statement`, istemci yok. Claim OK → `status=extracting` → `await extract_statement(...)` → `done` / `needs_review`. `ExtractFailed` satırı servis yazar; iş üzerine `mask_failed` basmaz. Frontend 2 sn'de bir sorgular.
- Eşzamanlılık: `asyncio.Semaphore(2)`; fazlası `queued`'da bekler; bekleyen sayısı ≥ 4 ise `POST` `503 busy` (bekleyen bytes belleği şişirmesin).
- Maskelenmiş bytes önizleme için 10 dk TTL ile tutulur, süreli temizleyici görev düşürür.
- Süreç yeniden başlarsa açılışta `queued`/`masking` → `mask_failed` + `error=restart`, `extracting` → `extract_failed` + `error=restart` (bytes bellekteydi; kullanıcı yeniden yükler).
- `BackgroundTasks` tek instance için yeterli; kuyruk sistemi v1'de yok (iş başına < 30 sn).
- Bakım bayrağı: `app.state.maintenance: bool`, başlangıç `MAINTENANCE` env'den; Faz 4 admin API'si değiştirir. DB'de tutulmaz (ADR-0005). Açıkken **tüm yazma uçları** `503 maintenance` döner: bu fazda `POST /statements`, `DELETE /statements/{id}`, `PATCH /transactions/{id}`; sonraki fazların yazma uçları aynı dependency'yi (`require_not_maintenance`) kullanır. Okuma uçları ve `/api/healthz` açık kalır.

### 5.3 Frontend

Paketler: `vite@8`, `react@19`, `react-dom@19`, `react-router@8` (Data mode: `createBrowserRouter` `react-router`'dan, `RouterProvider` `react-router/dom`'dan; `react-router-dom` yok), `@tanstack/react-query@5`, `tailwindcss@4` + `@tailwindcss/vite`, `uplot@1.6`, `typescript@6` (7 `tsc -b` ile kırıldı), dev: `vitest`, `@testing-library/react`, `jsdom`.

```
frontend/src/
├── main.tsx, router.tsx, api/client.ts (fetch sarmalayıcı, hata gövdesi parse)
├── ui/            # Button, Input, Select, Table, Tabs, Dialog, Toast, DateRange
├── pages/
│   ├── Upload.tsx      # drag&drop, şifre alanı, ilerleme (queued→masking→extracting→done), önizleme
│   ├── Overview.tsx    # dönem seçici, toplam + önceki dönem farkı, kategori bar, günlük çizgi (uPlot lazy), en büyük 10
│   ├── Transactions.tsx # tablo, filtreler, satır içi kategori Select → PATCH
│   └── Settings.tsx    # Faz 3'te yalnızca "profil" bilgisi; Faz 4'te büyür
└── lib/money.ts   # kuruş → "1.234,56 ₺" (Intl.NumberFormat tr-TR)
```

Upload isteği: `fetch("/api/v1/statements", {method: "POST", body: file, headers: {"Content-Type": "application/pdf", "X-Statement-Password": pwd}})`. `FormData` kullanılmaz.

Tasarım kuralları (ADR-0007): sistem font yığını (`ui-sans-serif, system-ui, sans-serif`; Google Fonts / Inter yok — `font-src 'self'`), 3 boyut (13/15/22 px), gri skala + tek vurgu rengi, `prefers-color-scheme`, gradient/emoji/kart-içinde-kart yok, hazır component kütüphanesi yok.

Vite: `server.proxy = { "/api": { target: "http://localhost:8000", changeOrigin: true } }` (`/api/healthz` da bu altında). `build.assetsInlineLimit = 0` (küçük asset'ler `data:` URI olarak inline edilmesin; CSP). Build çıktısı `frontend/dist`; Faz 5 Dockerfile bunu `backend/static`'e kopyalar. Lokal üretim denemesi: `npm run build`; PowerShell `Copy-Item -Recurse dist ..\backend\static` (`cp -r` yok).

FastAPI tarafı (FastAPI ≥ 0.141): `app.frontend("/", directory=STATIC_DIR, fallback="index.html", check_dir=False)`; API route'ları her zaman önce eşleşir, `index.html` yalnızca `Accept: text/html` GET/HEAD isteklerinde döner. `check_dir=False` şart: varsayılan `"auto"` yalnızca `FASTAPI_ENV=development` iken eksik dizini tolere eder, `uvicorn app.main:app` bunu set etmez ve import kırılır.

### 5.4 Güvenlik başlıkları (Faz 3'te temel, Faz 4-5'te tamamlanır)

Middleware (`ENV=prod`): `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`. CSP **yalnızca prod**; Vite HMR inline kullandığı için `ENV=dev` header yok. Vite üretim çıktısı inline script içermez (modulepreload polyfill giriş chunk'ında); Tailwind v4 CSS dosyası üretir; React ve uPlot CSSOM ile stil verir. HSTS Faz 5'te.

### 5.5 Bilinen tuzaklar

- **`UploadFile` orijinal PDF'i diske yazar.** Starlette multipart ayrıştırıcısı dosya parçalarını `SpooledTemporaryFile(max_size=1 MB)` ile tutar; 15 MB PDF geçici dosya olarak diske iner ve "orijinal PDF diske yazılmaz" ilkesi ihlal edilir. Bu yüzden upload **ham gövde** ile alınır, `python-multipart` bağımlılığı yoktur. KK-4 grep'i `UploadFile|SpooledTemporaryFile|File\(` içerir.
- Gövde boyutu: FastAPI `include_router` route `max_body_size` sarmalamasını düşürür; app-level `JsonBodyLimitMiddleware` (`Content-Length` varsa önden, yoksa bayt sayarak `413 too_large` zarfı). Yalnızca `Content-Length` kontrolü chunked gövdeyi kaçırır.
- Maskeleme `tobytes` deterministik değil; UNIQUE claim Gemini öncesi `sha256(orijinal)` (kolon adı `masked_sha256`). POST yer tutucu `pending:{uuid}` — `sha256(orijinal)` POST'ta yazılırsa paralel ikinci INSERT UNIQUE ile ölür veya iki Gemini çağrısı kaçabilir.
- TestClient `BackgroundTasks`'i POST bitmeden çalıştırır; busy testi `add_task` no-op ister.
- `PATCH /transactions/{id}` sonrası `summary` ve `transactions` query'leri `queryClient.invalidateQueries({queryKey})` ile yenilenir.
- Büyük tablo: `page_size` 50 varsayılan, sayfalama sunucuda; sanal liste v1'de yok.
- uPlot `React.lazy` + `Suspense` ile yalnızca Overview'da (`dist/assets/uplot-*.js`); bundle ölçümü giriş chunk'ları ile sınırlı, uPlot chunk'ı hariç.
- TypeScript 7 (Go) ile `tsc -b` kırıldı → Faz 3 `typescript@6`; Vite tip kontrolü yapmaz.

## 6. Görevler

### 6.1 Backend

- [x] F3-T01 Bağımlılıklar — `backend/pyproject.toml`
      Komut: `uv add "fastapi>=0.141" "starlette>=1.6.0" "uvicorn[standard]" && uv add --dev httpx`
      Doğrula: `uv run python -c "import fastapi, starlette; print(fastapi.__version__, starlette.__version__)"`
- [x] F3-T02 App iskeleti, `get_current_user` (dev user), hata gövdesi, güvenlik başlıkları, `/api/healthz`, `app.state.maintenance`, `app.frontend(check_dir=False)` — `backend/app/main.py`, `app/api/deps.py`, `app/api/errors.py`
      Doğrula: `uv run pytest tests/test_api_health.py -q` (`static/` yokken import başarılı)
- [x] F3-T03 Ham gövde upload + iş + durum + önizleme + silme — `app/api/statements.py`, `app/jobs.py`
      Doğrula: `uv run pytest tests/test_api_statements.py -q` (16 MiB gövde `413 too_large`; `%PDF-` olmayan `400 unsafe_pdf`; şifreli fixture şifresiz `400 password_required`, yanlış şifre `400 wrong_password`; 61 sayfa `400 too_many_pages`; sentetik ekstre `202` → polling ile `done`; aynı ekstre ikinci kez → `mask_failed` + `duplicate_statement`; `preview.png` 200 `image/png`, 10 dk sonra `404 preview_expired`; bakım bayrağı açıkken `POST /statements`, `DELETE /statements/{id}`, `PATCH /transactions/{id}` → `503 maintenance`, `GET` uçları 200; 5. bekleyen upload `503 busy`)
- [x] F3-T04 [P] İşlemler ve kategori düzeltme — `app/api/transactions.py`, `app/api/categories.py`
      Doğrula: `uv run pytest tests/test_api_transactions.py -q` (filtreler dahil `direction`, sayfalama, PATCH sonrası `effective_category`, başka kullanıcının kaydı `404`)
- [x] F3-T05 [P] Özet — `app/api/summary.py`
      Doğrula: `uv run pytest tests/test_api_summary.py -q` (override'lı kategori doğru kovada; `prev_total` önceki aralık; `daily` boş günler 0; `top` `effective_category`)
- [x] F3-T06 Event loop testi — `tests/test_api_concurrency.py`
      Doğrula: 2 paralel upload işlenirken `/api/healthz` < 200 ms

### 6.2 Frontend

- [x] F3-T07 Proje kurulumu — `frontend/`
      Komut: `npm create vite@latest frontend -- --template react-ts && cd frontend && npm i react-router @tanstack/react-query uplot && npm i -D tailwindcss @tailwindcss/vite vitest @testing-library/react jsdom`
      Doğrula: `npm run dev` açılıyor, `/api/healthz` proxy ile 200
- [x] F3-T08 [P] UI primitifleri — `frontend/src/ui/*`
      Doğrula: `npm test -- ui` (Dialog: Escape kapatır, focus içeride kalır; Toast: 4 sn sonra kaybolur; DateRange: geçersiz aralıkta hata)
- [x] F3-T09 [P] API istemcisi ve query hook'ları — `frontend/src/api/*`
      Doğrula: `npm test -- api` (hata gövdesi `error.code` ile parse ediliyor; upload ham gövde ile gidiyor)
- [x] F3-T10 Yükle ekranı — `frontend/src/pages/Upload.tsx`
      Doğrula: `npm test -- Upload` (PDF olmayan dosya istemci tarafı hata; durum geçişleri; `password_required` gelince şifre alanı vurgulanıyor)
- [x] F3-T11 Genel bakış — `frontend/src/pages/Overview.tsx`
      Doğrula: `npm test -- Overview`; uPlot chunk'ı ayrı dosyada (`dist/assets/uplot-*.js`)
- [x] F3-T12 İşlemler — `frontend/src/pages/Transactions.tsx`
      Doğrula: `npm test -- Transactions` (kategori değişince summary ve transactions invalidate)
- [x] F3-T13 Üretim build'i FastAPI'den — `backend/app/main.py`
      Doğrula: `cd frontend && npm run build && cp -r dist ../backend/static && cd ../backend && uv run uvicorn app.main:app --port 8000` → `curl -H "Accept: text/html" localhost:8000/transactions` index.html döner, `curl localhost:8000/api/v1/categories` JSON döner

### 6.3 Kapanış

- [x] F3-T14 Performans — Lighthouse ve bundle ölçümü
      Doğrula: `npm run build` sonrası giriş chunk'ları (`index-*.js` + `index-*.css`, uPlot hariç) gz toplamı < 256000 bayt; Chrome Lighthouse performans ≥ 90 (üretim build, uvicorn üzerinden)
- [x] F3-T15 [P] Yol kapsamlı ajan kuralları — `.claude/rules/frontend.md` (`paths: frontend/**`; ADR-0007 tasarım kuralları, `react-router` import yolları, CSP uyumu, ham gövde upload)
      Doğrula: dosya var, `CLAUDE.md`'deki referansla eşleşiyor
- [x] F3-T16 Bu dosyada Durum → bitti, changelog; `docs/README.md`

## 7. Kabul kriterleri

- KK-1: Sentetik ekstre tarayıcıdan yüklendiğinde 20 sn içinde genel bakışta veri görünür.
- KK-2: `uv run pytest -q` ve `npm test` ağ olmadan geçer.
- KK-3: Giriş chunk'ları < 250 KB gz; Lighthouse performans ≥ 90.
- KK-4: Orijinal PDF bytes'ı yalnızca `jobs.py` bellek deposunda yaşar. Komut: `grep -rnE "UploadFile|SpooledTemporaryFile|File\(|\.save\(|write_bytes|write_text|NamedTemporaryFile" app/api app/jobs.py` → boş.
- KK-5: Başka `user_id`'ye ait ekstre/işlem `404`.
- KK-6: Üretim build'inde CSP ile konsolda ihlal yok.
- KK-7: 2 paralel upload sırasında `/api/healthz` < 200 ms.

## 8. Riskler (bu faza özgü)

| Risk | Etki | Önlem |
|---|---|---|
| Event loop blokajı (PyMuPDF sync) | Tüm API donar | `run_in_threadpool`, KK-7 |
| Süreç yeniden başlarsa bellekteki PDF'ler kaybolur | Kullanıcı yeniden yükler | Açılışta yarım işler `*_failed` + `restart`, UI mesajı |
| Bekleyen upload'lar belleği şişirir | OOM | `busy` eşiği 4, Semaphore(2) |
| 8 primitif zaman alır | Faz uzar | Dialog/Toast/DateRange minimal; kırpma planı `risks-timeline.md` |
| TS 7 / Vite 8 uyumsuzluğu | Build kırılır | `typescript@6` fallback |

## 9. Açık sorular

- [x] Önizleme: 10 dk bellek TTL + `GET .../preview.png` (upload yanıtında base64 yok)
- [x] Dönem seçici varsayılanı: son ekstre `period_start`/`period_end`; yoksa içinde bulunulan ay

## 10. Referanslar

- FastAPI frontend/SPA: https://fastapi.tiangolo.com/tutorial/frontend/ , referans (`check_dir`): https://fastapi.tiangolo.com/reference/fastapi/
- FastAPI BackgroundTasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Starlette requests (`body()`), form parser (`SpooledTemporaryFile`), `max_body_size` / `RequestBodyLimitMiddleware`: https://starlette.dev/requests/ , https://starlette.dev/middleware/ , https://starlette.dev/release-notes/
- Vite server.proxy, CSP: https://vite.dev/config/server-options , https://vite.dev/guide/features#content-security-policy-csp
- react-router 8 modes ve changelog: https://reactrouter.com/start/modes , https://reactrouter.com/changelog
- Tailwind v4 + Vite: https://tailwindcss.com/docs/installation/using-vite
- TanStack Query v5: https://tanstack.com/query/latest
- uPlot: https://github.com/leeoniya/uPlot
- Doğrulama notu: [../reference/tech-verification-2026-09-16.md](../reference/tech-verification-2026-09-16.md)

## Changelog

- 2026-09-16 taslak oluşturuldu (monolit plandan bölündü; `app.frontend`, threadpool + semaphore, bakım bayrağı, 404 politikası, hata gövdesi, react-router 8, önizleme TTL eklendi; süre 2 → 3 hafta)
- 2026-09-16 doğrulama turu 1: multipart → ham gövde (SpooledTemporaryFile diske yazıyordu), Starlette 1.6 `max_body_size`, `extract_statement` imzası ve `duplicate_statement` akışı, `validation_issues_json`, şifreli PDF kontrolü POST'ta, `leak_detected` kodu, `check_dir=False`, `/api/healthz`, CSP eklemeleri ve `assetsInlineLimit`, item şeması + `direction` filtresi, `busy` eşiği, bundle ölçümü giriş chunk'ları
- 2026-09-16 uygulandı: HTTP API + Vite dashboard; UNIQUE claim `sha256(orijinal)` (maske hash'i deterministik değil); KK-1 tarayıcı sentetik → Overview ₺37,00; KK-2 pytest 70 + vitest 8; KK-3 giriş js gzip 110120 B, Lighthouse performans 90; KK-4 grep boş; KK-5 yabancı 404; KK-6 CSP ihlali yok; KK-7 healthz eşzamanlı upload
- 2026-09-16 as-built: §5.1–5.5 kodla hizalandı (`pending:{uuid}` claim, `JsonBodyLimitMiddleware`, CSP yalnızca prod, sistem fontu, `typescript@6`, kategoriler `transactions.py`)
