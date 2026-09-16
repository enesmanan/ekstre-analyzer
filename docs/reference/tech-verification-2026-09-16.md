# Teknoloji Doğrulama Notu — 16 Eylül 2026

Bu dosya, plandaki teknik iddiaların resmi dokümanlara karşı kontrol edildiği tarihteki bulguları tutar. Faz dosyaları ve ADR'ler bu bulgulara göre yazıldı. Bir bilgi bu dosya ile çelişiyorsa önce ilgili resmi dokümana bakın, sonra bu dosyayı güncelleyin.

## Gemini API (Developer API, `google-genai` Python SDK)

| Konu | Doğrulanmış bilgi | Kaynak |
|---|---|---|
| Model | `gemini-3.8-flash` GA (2 Eyl 2026). Giriş 1.048.576, çıkış 65.536 token. `thinking_level`: `low` / `medium` / `high`; `minimal` hata döner; varsayılan `medium`. | https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash |
| Fiyat | Tanıtım: $0,75 giriş / $3,75 çıkış per 1M token, 31 Aralık 2026'ya kadar. Sonrası $1,50 / $7,50. | https://ai.google.dev/gemini-api/docs/pricing |
| Diğer modeller | `gemini-3.5-flash` Stable (kapatma tarihi yok). GA Pro modeli yok; `gemini-3.1-pro-preview` Preview. | https://ai.google.dev/gemini-api/docs/models |
| API yüzeyi | Interactions API: `client.interactions.create(model=, input=, generation_config=, system_instruction=, response_format=, tools=, stream=, store=, previous_interaction_id=, background=)`. `generateContent` legacy ama destekleniyor. SDK ≥ 2.3.0. | https://ai.google.dev/gemini-api/docs/interactions |
| Yanıt | `interaction.output_text`. Ham yapı `interaction.steps[-1].content[0].text`. Mayıs 2026'da `outputs` → `steps` oldu; eski `outputs[-1].text` kalıbı geçersiz. | https://ai.google.dev/gemini-api/docs/interactions/get-started |
| Token sayımı | `interaction.usage.total_tokens`, `.total_input_tokens`, `.total_output_tokens`, `.total_thought_tokens`, `.total_cached_tokens`. | aynı |
| Yapılandırılmış çıktı | `response_format={"type":"text","mime_type":"application/json","schema": Model.model_json_schema()}`. Pydantic sınıfı doğrudan verilemez. Parse: `Model.model_validate_json(interaction.output_text)`. | https://ai.google.dev/gemini-api/docs/structured-output |
| Gemini 3.x kuralları | `temperature`, `top_p`, `top_k` gönderme (deprecated). `thinking_budget` yerine `thinking_level`. `candidate_count` desteklenmez. `max_output_tokens` destekleniyor. | https://ai.google.dev/gemini-api/docs/latest-model |
| PDF girişi | Native PDF. Sayfa başına 258 görsel token; gömülü metin katmanı token'ları ücretsiz. Sınır 50 MB / 1000 sayfa. `media_resolution` part başına `low`/`medium`/`high`. | https://ai.google.dev/gemini-api/docs/document-processing |
| Inline / Files API | Toplam istek > 100 MB ise Files API zorunlu. Files API ücretsiz, dosyalar 48 saat saklanır. Part şekli inline: `{"type":"document","data":b64,"mime_type":"application/pdf"}`; Files: `{"type":"document","uri":uploaded.uri,"mime_type":uploaded.mime_type}`. | https://ai.google.dev/gemini-api/docs/files |
| Async | `client.aio.interactions.create(...)` mevcut. | https://googleapis.github.io/python-genai/ |
| Rate limit | 429 `RESOURCE_EXHAUSTED`. RPM/TPM/RPD + Tier bazlı 10 dakikalık harcama limiti (Tier 1: $10). SDK **varsayılanda retry yapmaz**; `genai.Client(http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=N)))` ile 408/429/500/502/503/504 için 1–60 sn jitter'lı retry açılır. | https://ai.google.dev/gemini-api/docs/rate-limits , python-genai `_api_client.py` |
| Veri kullanımı | Ücretli tier: prompt/yanıt ürün geliştirmede kullanılmaz. Ücretsiz tier: kullanılır. | https://ai.google.dev/gemini-api/terms |
| EU yerleşimi | Developer API'de bölge seçimi yok. Vertex AI EU bölgesi + servis hesabı + açık `location` gerekli. | https://ai.google.dev/gemini-api/docs/available-regions |

## PyMuPDF (1.28.2)

| Konu | Doğrulanmış bilgi | Kaynak |
|---|---|---|
| Açma | `pymupdf.open(stream=bytes, filetype="pdf")`; `filetype` içerik tespiti başarısız olursa kullanılır. Şifreli PDF: `doc.needs_pass` → `doc.authenticate(pwd)`. | https://pymupdf.readthedocs.io/en/latest/document.html |
| Metin | `get_text("words")` → `(x0,y0,x1,y1,word,block_no,line_no,word_no)`. `get_text("dict")` → blocks → lines → spans (span'de `chars` yok). `get_text("rawdict")` → span'lerde `chars: [{"c","bbox","origin","synthetic"}]`, karakter bazlı bbox buradan. | https://pymupdf.readthedocs.io/en/latest/textpage.html |
| `search_for` | Düz string arar, regex desteklemez. | https://pymupdf.readthedocs.io/en/latest/page.html |
| Redaction | `add_redact_annot(quad, fill=(1,1,1), ...)`. `apply_redactions(images=PDF_REDACT_IMAGE_PIXELS, graphics=PDF_REDACT_LINE_ART_REMOVE_IF_COVERED, text=PDF_REDACT_TEXT_REMOVE)`. Sabitler modül düzeyinde: `pymupdf.PDF_REDACT_IMAGE_NONE`, `PDF_REDACT_LINE_ART_NONE`, `PDF_REDACT_TEXT_REMOVE`, `PDF_REDACT_TEXT_NONE`. | aynı |
| Silme kuralı | Karakter bbox'ı redaction dikdörtgeni ile **boş olmayan herhangi bir kesişim** yaparsa silinir. `pymupdf.TOOLS.set_small_glyph_heights(True)` (modül düzeyinde hazır `TOOLS` örneği; `Tools()` çağrısı yok) glif bbox'ını karakter yüksekliğine indirir; kapalıyken 12 pt aralıklı komşu satırlar da silinir (1.28.2, ampirik). | https://pymupdf.readthedocs.io/en/latest/tools.html |
| JS tespiti | `cat = doc.pdf_catalog()`; `doc.xref_get_key(cat, "Names/JavaScript")` (yoksa `("null","null")`), `doc.xref_get_key(cat, "OpenAction/S")[1] == "/JavaScript"`, tüm xref'lerde `xref_get_key(x, "S") == "/JavaScript"`. Düz `OpenAction` (GoTo) meşru. Form: `doc.is_form_pdf`, `page.widgets()`. Ek: `page.annots(types=[PDF_ANNOT_FILE_ATTACHMENT])`. | https://pymupdf.readthedocs.io/en/latest/document.html |
| Fixture yazımı | `page.insert_text(fontname="helv")` Latin-1 kodlar, Türkçe karakterler bozulur. `TextWriter` + `pymupdf.Font("helv")` veya `insert_htmlbox` kullan. Şifreli fixture: `doc.save(path, encryption=PDF_ENCRYPT_AES_256, user_pw=...)`. `authenticate` yanlış şifrede `0` döner. | https://pymupdf.readthedocs.io/en/latest/page.html |
| Rect cebiri | `rect + (pad, pad, -pad, -pad)` bileşen bazlı geçerli. | https://pymupdf.readthedocs.io/en/latest/algebra.html |
| Temizlik | `doc.scrub(attached_files, clean_pages, embedded_files, hidden_text, javascript, metadata, redactions, redact_images, remove_links, reset_fields, reset_responses, thumbnails, xml_metadata)` tek çağrı. `set_metadata({})`, `del_xml_metadata()`, `embfile_count()`, `xref_get_key()` ayrıca mevcut. | https://pymupdf.readthedocs.io/en/latest/document.html |
| Kaydetme | `doc.tobytes(garbage=3, deflate=True)`. | aynı |
| Görsel | `page.get_pixmap(dpi=100)`. | page.html |
| Wheel | `cp310-abi3` (3.10–3.14). `musllinux_1_2_x86_64` var, aarch64 musl yok. | https://pypi.org/project/PyMuPDF/#files |
| OCR | `get_textpage_ocr()` Tesseract gerektirir. v1 kapsam dışı. | https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html |

## Litestream (v0.5.17)

| Konu | Doğrulanmış bilgi | Kaynak |
|---|---|---|
| GCS | `gs://bucket/path`; Cloud Run'da kimlik metadata sunucusundan otomatik. | https://litestream.io/guides/gcs/ |
| Config | `dbs: - path: ... replica: url: ... sync-interval: 1s` (tekil `replica`). `replicas:` listesi geçersiz. `retention:` replica altında yok. Global: `snapshot: {interval: 24h, retention: 24h}` (doküman varsayılanları; proje 72h kullanır, ADR-0004), `l0-retention`, `exec:`, `shutdown-sync-timeout` (varsayılan 30s), `shutdown-sync-interval`. `${ENV}` genişletme var. DB altında `restore-if-db-not-exists: true`. | https://litestream.io/reference/config/ |
| Komutlar | `litestream restore -o PATH -if-db-not-exists -if-replica-exists URL`; `litestream replicate -exec "cmd"`. | https://litestream.io/reference/restore/ |
| İndirme | Asset: `litestream-0.5.17-linux-x86_64.tar.gz` (`v` öneki yok, `x86_64`). `releases/latest/download/litestream-linux-amd64.tar.gz` **yok**. Docker: `litestream/litestream:0.5.17`. | https://github.com/benbjohnson/litestream/releases |
| Cloud Run | Resmi Cloud Run rehberi yok (sadece GCS ve Docker rehberleri). | https://litestream.io/guides/ |
| Kapanış | `-exec` ile SIGTERM çocuk sürece iletilir, çıkış beklenir, `shutdown-sync-timeout` içinde son sync yapılır. | kaynak kod `cmd/litestream/main.go` |
| Docker imajı | `litestream/litestream:0.5.17` ve `0.5.17-scratch`; binary `/usr/local/bin/litestream`, statik. | https://github.com/benbjohnson/litestream/blob/main/Dockerfile |
| Metrikler | `addr:` ile Prometheus `/metrics`: `litestream_txid`, `litestream_sync_count`, `litestream_sync_error_count`, `litestream_wal_size`, `litestream_replica_operation_*`. "Son sync yaşı" gauge'u yok. `heartbeat-url` / `heartbeat-interval` global anahtarları var. | https://litestream.io/reference/metrics/ |
| Çoklu süreç | Aynı bucket/yola eşzamanlı iki replikasyon desteklenmez; restore edilemez duruma yol açabilir. Kurtarma `litestream reset`. | https://litestream.io/tips/ |
| Regresyon | 0.5.16/0.5.17 GCS yazımları asılı kalabiliyor (issue #1512, PR #1520 14 Eyl'de açık). | https://github.com/benbjohnson/litestream/issues/1512 |

## Google Cloud Run

| Konu | Doğrulanmış bilgi | Kaynak |
|---|---|---|
| Flag'ler | `--min-instances`, `--max-instances` (revizyon düzeyi), `--no-cpu-throttling`, `--concurrency`, `--timeout`, `--set-secrets`, `--set-env-vars`, `--service-account`, `--source`, `--cpu`, `--memory` geçerli. | https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy |
| Tek instance | max-instances revizyon başına uygulanır; deploy geçişinde eski ve yeni revizyon birlikte istek alabilir. "Tek yazıcı" garantisi yok. | https://docs.cloud.google.com/run/docs/configuring/max-instances |
| Dosya sistemi | Varsayılan yazılabilir FS in-memory ve konteyner belleğini tüketir. In-memory volume: `--add-volume name=V,type=in-memory,size-limit=512Mi` + `--add-volume-mount volume=V,mount-path=/data`. | https://docs.cloud.google.com/run/docs/configuring/services/in-memory-volume-mounts |
| GCS FUSE | POSIX uyumlu değil, file locking yok, "last write wins". SQLite için uygun değil. | https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts |
| Kapanış | SIGTERM sonrası 10 sn, ardından SIGKILL. | https://docs.cloud.google.com/run/docs/container-contract |
| Secret | `--set-secrets ENV=SECRET:VERSION`; `latest` yerine sabit sürüm önerilir. | https://docs.cloud.google.com/run/docs/configuring/services/secrets |
| Public erişim | `--allow-unauthenticated` / `--no-allow-unauthenticated` (boolean; `=false` sözdizimi yok). | https://docs.cloud.google.com/run/docs/authenticating/public |
| `--source` | Dockerfile kaynak dizininin kökünde olmalı; yol parametresi yok. Tüm dizin Cloud Build staging'e yüklenir → `.gcloudignore` (`#!include:.gitignore`). | https://docs.cloud.google.com/run/docs/deploying-source-code , https://docs.cloud.google.com/sdk/gcloud/reference/topic/gcloudignore |
| `--no-traffic` | Revizyon düzeyi `min-instances` yalnızca trafik veya tag'i olan revizyonda instance açar; `--no-traffic --tag NAME` ile başlatılıp tag URL'sinde doğrulanır. | https://docs.cloud.google.com/run/docs/configuring/min-instances |
| Startup probe | `--startup-probe httpGet.path=...,initialDelaySeconds=,periodSeconds=,failureThreshold=`. | https://docs.cloud.google.com/run/docs/configuring/healthchecks |
| İstek boyutu | 32 MiB, yalnızca HTTP/1; HTTP/2'de sınır yok. | https://docs.cloud.google.com/run/quotas |
| Deploy izinleri | `roles/run.sourceDeveloper` + `roles/serviceusage.serviceUsageConsumer` (proje), `roles/iam.serviceAccountUser` (runtime SA), build SA `roles/run.builder`, `--build-service-account`. | https://docs.cloud.google.com/run/docs/deploying-source-code#permissions |
| CI | `google-github-actions/auth@v3`, Direct Workload Identity Federation; `permissions: id-token: write`; `gcloud` için `service_account` verilir. | https://github.com/google-github-actions/auth |
| uvicorn | `--timeout-graceful-shutdown`, `--proxy-headers`, `--forwarded-allow-ips` mevcut. `--forwarded-allow-ips="*"` XFF'in **en soldaki** girdisini istemci sayar; Cloud Run gerçek IP'yi sona **ekler**, silmez → rate limit anahtarı son girdiyi almalı. | https://uvicorn.dev/settings/ , https://adam-p.ca/blog/2022/03/x-forwarded-for/ |

## Backend kütüphaneleri

| Paket | Sürüm (16 Eyl 2026) | Not |
|---|---|---|
| Python | 3.13 önerilir | 3.12 security-only (EOL Eki 2028). 3.13 bugfix (EOL Eki 2029). |
| fastapi | 0.141.1 | `app.frontend(path, *, directory, fallback="auto"\|"index.html"\|"404.html"\|None, check_dir)` resmi SPA desteği; `check_dir="auto"` yalnızca `FASTAPI_ENV=development` iken eksik dizini tolere eder → `check_dir=False`. `BackgroundTasks` `async def` görev kabul eder; ağır işleri threadpool'a al. |
| starlette | 1.6.0 (8 Ağu 2026) | `max_body_size` (app/route) ve `RequestBodyLimitMiddleware` (413; `Content-Length` yoksa bayt sayar). **Multipart `UploadFile` dosya parçalarını `SpooledTemporaryFile(max_size=1 MB)` ile diske yazar** → orijinal PDF için ham gövde `await request.body()`. FastAPI 0.141.1 `starlette>=0.46` pinler; 1.6 açıkça istenir. |
| sqlalchemy | 2.0.54 | PRAGMA'lar `event.listens_for(engine, "connect")` ile. Py3.12+ sqlite3'te PRAGMA için `autocommit` geçici `True`. Sync engine + threadpool yeterli; aiosqlite gerçek async değil. |
| alembic | 1.20.0 | SQLite için `render_as_batch=True` zorunlu. |
| pyjwt | 2.14.0 | ≥ 2.10 `sub` claim'i **string** olmalı (`InvalidSubjectError`); `jwt.decode(..., algorithms=["HS256"], options={"require": [...]}, leeway=10)`. python-jose 3.5.0 (May 2025); CVE-2024-33663/33664 3.4.0'da düzeltildi ama sürüm temposu düşük. PyJWT tercih. |
| argon2-cffi | 25.1.0 | Varsayılan argon2id, t=3, m=64 MiB, p=4. |
| slowapi | 0.1.10 (Haz 2026) | `key_func(request)` yalnızca `request` alır (kullanıcı anahtarı için `request.state`); endpoint imzasında `request: Request` zorunlu; varsayılan 429 gövdesi `{"error": "..."}` string → özel handler. Yavaş bakım ama kullanılabilir. fastapi-limiter Redis ister. |
| pydantic-settings | 2.15.0 | |
| tenacity | 9.1.4 | |
| structlog | 26.1.0 | |
| typer | 0.27.2 | |
| pyyaml | 6.0.3 | |
| pytest | 9.1.1 | |
| uv | 0.12.15 | `uv init --python`, `uv add`, `uv add --dev`, `uv sync --frozen --no-dev`, `uv run` geçerli. Docker: `COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/`, `--no-install-project` katman deseni, `--mount=type=cache,target=/root/.cache/uv`, `UV_COMPILE_BYTECODE=1`. |

## Frontend kütüphaneleri

| Paket | Sürüm (16 Eyl 2026) | Not |
|---|---|---|
| Node | 24 önerilir | 22 Maintenance LTS (EOL 30 Nis 2027). 24 Active LTS. |
| vite | 8.3.0 | Rolldown tabanlı. Node `^20.19 \|\| >=22.12`. |
| react / react-dom | 19.3.0 | |
| react-router | 8.4.0 | `react-router-dom` paketi kaldırıldı; `RouterProvider` → `react-router/dom`. React ≥ 19.2.7, Node ≥ 22.22, ESM-only. Declarative veya Data mode. |
| @tanstack/react-query | 5.103.0 | |
| tailwindcss + @tailwindcss/vite | 4.3.3 | `@import "tailwindcss"`. |
| uplot | 1.6.32 | ~22 KB gz. Lazy-load önerilir. |
| typescript | 7.0.2 (Go) | Sorun çıkarsa 6.x pinle. |
| Bundle | react+dom ~69 KB, react-router ~60 KB, react-query ~14 KB, uplot ~22 KB gz | 250 KB gz hedefi gerçekçi. |
| CSP | Vite üretim çıktısı inline script içermez (modulepreload polyfill giriş chunk'ında); küçük asset'ler `data:` URI olarak inline edilir → `build.assetsInlineLimit = 0` veya `font-src 'self' data:`. Tailwind v4 CSS dosyası üretir, inline style yok. | https://vite.dev/guide/features#content-security-policy-csp |
| pydantic | 2.x | `Field(max_length=N)` listeler için geçerli (v2'de `max_items` yok), şemada `maxItems`. Gemini structured output `maxItems`, `anyOf`, `enum`, `format: date`, nested object destekler; `$defs`/`title`/`default` için resmi örnek yok → şema temizleme + smoke test. | https://docs.pydantic.dev/latest/api/fields/ , https://ai.google.dev/gemini-api/docs/structured-output |
