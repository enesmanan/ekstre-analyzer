# Ekstre Analyzer

Türk banka ekstresi (PDF) analiz uygulaması: PyMuPDF ile maskele → Gemini 3.8 Flash ile işlemleri çıkar → SQLite → React dashboard → Cloud Run. Tek geliştirici, kapalı beta hedefi.

@docs/README.md
@AGENTS.md

**Tek hedef banka:** v1 tamamen geliştiricinin kendi TOM Bank ekstresi üzerinden ilerler (`backend/profiles/tom.yaml`, gerçek ekstre `backend/tests/private/tom.pdf`, gitignore). Başka banka profili yazılmaz.

## Çalışma düzeni

- Önce `docs/README.md`, sonra `docs/00-plan.md` ve çalışılacak fazın dosyasını oku (`docs/phases/faz-N-*.md`). Tek seferde tek faz; kapsam dışına çıkma.
- Faz dosyasındaki görev listesini sırayla uygula. Her görevin altındaki doğrulama komutunu çalıştır, çıktısını göster; geçmeden sonrakine geçme.
- Görev bitince checkbox'ı işaretle; faz bitince Durum → `bitti`, changelog satırı ekle, `docs/README.md` faz tablosunu güncelle.
- `[NETLEŞTİRİLMELİ: ...]` gördüğünde tahmin etme, kullanıcıya sor.
- Bir teknik iddia dokümanla çelişiyorsa resmi dokümana bak, `docs/reference/tech-verification-*.md` dosyasını tarihli güncelle, sonra kodu yaz.
- Mimari karar değişikliği gerekirse yeni ADR aç (`docs/decisions/`), mevcut ADR'yi "yerini aldı" yap.

## Kırmızı çizgiler

- Orijinal PDF bytes'ı **asla** diske/bucket'a yazılmaz; yalnızca bellekte işlenir. Upload ham gövde ile alınır (`await request.body()`); `UploadFile`/multipart kullanılmaz (Starlette geçici dosyaya yazar).
- Sızıntı testi (`verify`) başarısızsa Gemini çağrısı yapılmaz.
- Gemini çağrılarında `temperature`, `top_p`, `top_k`, `candidate_count`, `thinking_budget` gönderilmez; `thinking_level` kullanılır. Model adı config'ten okunur.
- Tutarlar kuruş cinsinden `int`; `float` yok.
- Log'lara PDF içeriği, işlem açıklaması, e-posta, PDF şifresi, token yazılmaz.
- Gemini'ye giden payload'da kullanıcı kimliği, e-posta veya ham `description` yok (tavsiye agregatı).
- Gerçek ekstreler `backend/tests/private/` altında, gitignore'da; CI sentetik fixture kullanır.

## Komutlar

Backend (`backend/` içinde, Python 3.13, uv):

```bash
uv sync
uv run pytest -q
uv run cli.py mask INPUT.pdf -o OUT.pdf
uv run cli.py verify OUT.pdf
uv run uvicorn app.main:app --reload --port 8000
uv run alembic -c app/db/alembic.ini -x db=app.db upgrade head
```

Frontend (`frontend/` içinde, Node 24):

```bash
npm ci
npm run dev
npm test
npm run build
```

Doğrulama komutları Git Bash sözdizimindedir. Bu makinede varsayılan kabuk PowerShell 5.1; `&&` yerine `;` kullan veya Git Bash'e geç.

## Yol kapsamlı kurallar

- `frontend/**`: `.claude/rules/frontend.md` (ADR-0007 tasarım kuralları, `react-router` import yolları, CSP uyumu, ham gövde upload).
- `backend/app/anonymizer/**`: PyMuPDF `rawdict`, `TOOLS.set_small_glyph_heights(True)`, `apply_redactions(images=PDF_REDACT_IMAGE_NONE, graphics=PDF_REDACT_LINE_ART_NONE)`; `search_for` regex için kullanılmaz.
- `backend/app/auth/**`: PyJWT `sub=str(id)`, `require` claim'leri; rate limit IP anahtarı `X-Forwarded-For` **son** girdisi.
- `Dockerfile`, `infra/**`: Litestream 0.5 sözdizimi (tekil `replica`, global `snapshot`), `shutdown-sync-timeout: 4s`; deploy `--no-traffic --tag canary` + bakım bayrağı runbook'u.
