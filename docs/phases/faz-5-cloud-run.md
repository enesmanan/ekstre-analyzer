# Faz 5 — Google Cloud Run Deploy (tek instance, tek image)

| Durum | Tarih | Süre tahmini | Bağımlılık |
|---|---|---|---|
| onaylı | 2026-09-16 | 1 hafta | Faz 4 bitti; [security-kvkk.md](../security-kvkk.md) kontrol listesi kapanmış |

Önceki: [Faz 4](faz-4-auth-admin.md) · Sonraki: — · İlgili ADR: [ADR-0004](../decisions/0004-sqlite-litestream-gcs.md), [ADR-0005](../decisions/0005-cloud-run-single-instance.md), [ADR-0006](../decisions/0006-single-image-static-frontend.md)

## 1. Amaç

Uygulamayı tek Docker image olarak Cloud Run'a almak; SQLite'ı Litestream ile GCS'e replike etmek; keysiz CI/CD; izleme ve kurtarma tatbikatı. Faz bitince kapalı beta URL'si çalışır, deploy ve restore runbook'ları belgelenmiş ve denenmiştir.

## 2. Kapsam / Kapsam dışı

- Kapsam: Dockerfile (repo kökünde), `.dockerignore`, `.gcloudignore`, entrypoint, Litestream config, `GcsStorage`, Cloud Run servisi, IAM, bucket'lar, Secret Manager, GitHub Actions (WIF), `/api/healthz` genişletme, Cloud Monitoring alarmları, deploy runbook (bakım bayrağı + tag'li revizyon), restore ve `litestream reset` tatbikatı, HSTS ve proxy başlıkları, startup probe.
- Kapsam dışı: Özel domain ve Cloud Armor (beta sonrası), Vertex AI EU (v2), çoklu bölge, Cloud SQL.

## 3. Ön koşullar

- [ ] Faz 4 KK'ları geçti; `ArtifactStorage` Protocol sabit
- [ ] GCP projesi, faturalama, güncel `gcloud`, bölge `europe-west1`
- [ ] GitHub repo; WIF için proje sahibi yetkisi
- [ ] Docker Desktop lokal build için (yalnızca bu fazda)

## 4. Teslimatlar

| Teslimat | Açıklama |
|---|---|
| `Dockerfile` (repo kökü), `.dockerignore`, `.gcloudignore` | Image; `gcloud run deploy --source` Dockerfile'ı kökte arar, yol parametresi yok |
| `infra/entrypoint.sh`, `infra/litestream.yml`, `infra/setup.sh` | Başlatma, replikasyon, GCP kurulumu (idempotent) |
| `backend/app/storage/gcs.py` | `GcsStorage` (`google-cloud-storage`) |
| `.github/workflows/ci.yml`, `deploy.yml` | Test + build; main'e merge'de tag'li revizyon |
| `docs/runbooks/deploy.md`, `docs/runbooks/restore.md` | Bu fazda yazılır ve denenir |

## 5. Tasarım

### 5.1 Dockerfile (repo kökü, multi-stage)

```dockerfile
FROM node:24-alpine AS fe
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend .
RUN npm run build

FROM python:3.13-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/
COPY --from=litestream/litestream:0.5.17 /usr/local/bin/litestream /usr/local/bin/litestream
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY backend .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY --from=fe /fe/dist ./static
COPY infra/litestream.yml /etc/litestream.yml
COPY infra/entrypoint.sh /entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH" DB_PATH=/data/app.db
CMD ["/entrypoint.sh"]
```

`.dockerignore`: `backend/.venv`, `**/__pycache__`, `backend/tests/private`, `backend/tests/out`, `frontend/node_modules`, `frontend/dist`, `.git`, `docs`. Aksi halde `COPY backend .` lokal Windows `.venv`'i `/app/.venv` üzerine yazar ve image bozulur.

`.gcloudignore`: `#!include:.gitignore` + `backend/tests/private/` + `.git`. `gcloud run deploy --source .` tüm dizini zip'leyip Cloud Build staging bucket'ına yükler; gerçek ekstreler ve `.env` asla yüklenmemeli (KVKK).

Notlar: `python:3.13-slim` (Alpine değil). uv sürümü sabit. Litestream binary'si resmi imajda `/usr/local/bin/litestream` yolundadır (resmi Dockerfile hem debian hem scratch varyantında aynı; statik binary, glibc bağımsız). GitHub release asset adı `litestream-0.5.17-linux-x86_64.tar.gz` biçimindedir, `releases/latest/download/litestream-linux-amd64.tar.gz` yoktur.

### 5.2 entrypoint.sh

```sh
#!/bin/sh
set -eu
mkdir -p /data
if [ "${LITESTREAM_DISABLED:-0}" = "1" ]; then       # lokal docker testi
  alembic -c app/db/alembic.ini -x db="$DB_PATH" upgrade head
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
fi
litestream restore -if-db-not-exists -if-replica-exists -o "$DB_PATH" "gs://${DB_BUCKET}/app.db"
alembic -c app/db/alembic.ini -x db="$DB_PATH" upgrade head
exec litestream replicate -config /etc/litestream.yml \
  -exec "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-graceful-shutdown 5 --proxy-headers --forwarded-allow-ips=*"
```

`exec` ile Litestream PID 1; Cloud Run SIGTERM'i Litestream'e iletir, o da `-exec` çocuğuna iletir, çıkışı bekler, son sync'i yapar. Bütçe: 10 sn SIGTERM penceresi = uvicorn ≤ 5 sn + Litestream `shutdown-sync-timeout` 4 sn.

### 5.3 litestream.yml (v0.5.x sözdizimi)

```yaml
addr: "127.0.0.1:9090"          # Prometheus /metrics, yalnızca konteyner içi
shutdown-sync-timeout: 4s
snapshot:
  interval: 24h
  retention: 72h
dbs:
  - path: /data/app.db
    replica:
      url: gs://${DB_BUCKET}/app.db
      sync-interval: 1s
```

`replica` tekil; `replicas:` listesi ve replica altında `retention:` v0.5'te geçersiz. `${DB_BUCKET}` genişletmesi desteklenir. Kimlik: Cloud Run metadata sunucusu.

**Sürüm uyarısı:** Litestream 0.5.16/0.5.17'de GCS replika yazımlarının süresiz asılı kalabildiği bir regresyon bildirildi (issue #1512; düzeltme PR'ı 14 Eylül itibarıyla açık). F5-T02'de canlı GCS smoke testi şart; asılırsa `0.5.15`'e pinlenir.

### 5.4 Cloud Run servisi

```bash
gcloud run deploy ekstre \
  --source . --region europe-west1 \
  --allow-unauthenticated --ingress all \
  --min-instances 1 --max-instances 1 \
  --cpu 1 --memory 1Gi --no-cpu-throttling \
  --concurrency 40 --timeout 300 \
  --add-volume name=data,type=in-memory,size-limit=512Mi \
  --add-volume-mount volume=data,mount-path=/data \
  --startup-probe httpGet.path=/api/healthz,initialDelaySeconds=5,periodSeconds=5,failureThreshold=48 \
  --set-secrets GEMINI_API_KEY=gemini-key:1,JWT_SECRET=jwt-secret:1 \
  --set-env-vars DB_BUCKET=ekstre-db-prod,ARTIFACT_BUCKET=ekstre-files-prod,ENV=prod \
  --service-account ekstre-run@PROJECT.iam.gserviceaccount.com \
  --build-service-account projects/PROJECT/serviceAccounts/ekstre-build@PROJECT.iam.gserviceaccount.com \
  --no-traffic --tag canary
```

- `--allow-unauthenticated` public erişim (uygulama kendi JWT'sini kullanır); `--no-allow-unauthenticated=false` diye bir sözdizimi yok.
- `--no-traffic --tag canary`: yeni revizyon trafik almaz ama **tag'li olduğu için başlar** (revizyon düzeyi `min-instances` yalnızca trafik veya tag'i olan revizyonlarda instance açar; salt `--no-traffic` revizyon hiç başlamaz ve restore/migration doğrulanamaz). Tag URL'si (`https://canary---ekstre-xxx.run.app`) üzerinden `/api/healthz` kontrol edilir.
- Startup probe: restore + migration bitmeden trafik gelmesin; 48 × 5 sn = 4 dk üst sınır.
- Secret sürümü sabit (`:1`), `latest` değil.
- In-memory volume `size-limit=512Mi`; varsayılan FS de bellek tabanlı, bu üst sınır koyar. 1 GiB bellek: DB ≤ 300 MB + Python + 2 eşzamanlı PDF.
- Runtime servis hesabı: iki bucket'a `roles/storage.objectAdmin` (bucket düzeyinde), iki secret'a `roles/secretmanager.secretAccessor`.
- Bucket'lar: uniform bucket-level access, public erişim engeli; `ekstre-db-prod` versioning + lifecycle `daysSinceNoncurrentTime: 30` silme; `ekstre-files-prod` 90 gün `age` silme.
- HSTS `max-age=31536000; includeSubDomains` middleware'de `ENV=prod` iken. Cloud Run istek gövdesi sınırı 32 MiB (HTTP/1); upload 15 MiB.

### 5.5 Deploy runbook (`docs/runbooks/deploy.md`)

`max-instances=1` revizyon başına uygulanır; geçişte iki revizyon birlikte çalışabilir. Litestream dokümanı: aynı bucket/yola eşzamanlı iki replikasyon **desteklenmez** ve restore edilemez duruma yol açabilir. Bu yüzden kesişme süresi minimuma indirilir ve yazma kapalı tutulur:

1. Admin API'den bakım bayrağını aç (`POST /admin/system/maintenance {on: true}`): upload, PATCH, advice, ayarlar `503 maintenance`. `GET /admin/system` aktif ve bekleyen iş 0 olana kadar bekle.
2. `gcloud run deploy ... --no-traffic --tag canary` (§5.4). Yeni instance açılır, restore + migration çalışır. Tag URL'sinde `/api/healthz` 200 ve `GET /api/v1/categories` doğru. Bu andan itibaren iki Litestream süreci aynı replikayı hedefler; yazma kapalı olduğu için yeni LTX üretilmez ama her iki süreç compaction/retention çalıştırabilir; bu adım 2 dakikayı geçmemeli.
3. `gcloud run services update-traffic ekstre --to-latest`. Eski revizyon kalan istekleri bitirir, SIGTERM alır, Litestream kapanış sync'i yapar.
4. Yeni revizyonda bakım bayrağı varsayılan kapalı (süreç içi). Ana URL'de `/api/healthz`, bir okuma isteği ve `transactions` sayısının deploy öncesiyle eşit olduğu doğrulanır.
5. Sorun varsa: `gcloud run services update-traffic ekstre --to-revisions=ÖNCEKİ=100`. Migration'lar geriye uyumlu yazılır (yeni sütun nullable; silme bir sonraki sürümde).

Kurtarma: restore başarısızsa `litestream restore` alternatif `-timestamp` ile; o da olmazsa `litestream reset` sonrası `PRAGMA integrity_check` ve yeniden replikasyon (runbook'ta adım adım).

### 5.6 Sağlık ve izleme

- `/api/healthz`: `SELECT 1` + Litestream `127.0.0.1:9090/metrics` okuması: `litestream_sync_error_count` ve `litestream_replica_operation_errors_total` son 60 sn'de artıyorsa `503 {"ok": false, "litestream": "errors"}`. Litestream "son sync yaşı" metriği sunmaz; hata sayaçları kullanılır. Ek: config'de `heartbeat-url` ile dead-man's switch (`[NETLEŞTİRİLMELİ: Cloud Monitoring uptime check yeterli mi, harici heartbeat servisi gerekli mi]`).
- Cloud Monitoring alarmları: 5xx oranı > %2 (5 dk), startup/liveness başarısız, container restart, bellek > %85, log tabanlı `extract_failed` sayısı, günlük Gemini maliyeti (`GEMINI_DAILY_BUDGET_USD`'nin %80'i).
- Loglar: structlog JSON → Cloud Logging; redaction processor (e-posta, şifre, açıklama alanları).

### 5.7 CI/CD

- `ci.yml` (PR ve main): `uv sync --frozen`, `uv run pytest -q`, `uv run pip-audit`, `npm ci`, `npm test`, `npm audit --audit-level=high`, `npm run build`, `docker build` (push yok).
- `deploy.yml` (main'e merge, `environment: prod` manuel onay): `permissions: id-token: write, contents: read`; `google-github-actions/auth@v3` Direct WIF (`workload_identity_provider`, `service_account`; `gcloud` access token gerektirdiği için SA verilir); `gcloud run deploy --source . --no-traffic --tag canary`; trafik geçişi runbook 1-3 adımlarıyla **manuel**.
- Deploy servis hesabı rolleri (resmi liste): `roles/run.sourceDeveloper` ve `roles/serviceusage.serviceUsageConsumer` (proje), `roles/iam.serviceAccountUser` (runtime SA üzerinde). Build servis hesabı `ekstre-build`: `roles/run.builder`. `storage.admin` verilmez.

### 5.8 Restore tatbikatı (`docs/runbooks/restore.md`)

1. Boş dizinde `litestream restore -o /tmp/r.db gs://ekstre-db-prod/app.db`.
2. `sqlite3 /tmp/r.db "PRAGMA integrity_check; SELECT count(*) FROM transactions;"` → `ok` ve beklenen sayı.
3. Zamana dönüş: `litestream restore -timestamp 2026-09-16T10:00:00Z ...`.
4. Bozuk replika senaryosu: `litestream reset` + yeniden replikasyon; adımlar ve süre kaydedilir.
5. Hedef < 5 dk; sonuç bu dosyanın changelog'una yazılır.

### 5.9 Bilinen tuzaklar

- `--no-cpu-throttling` şart: Litestream arka planda CPU ister.
- In-memory `/data` → her cold start'ta restore; `min-instances=1` ile nadir ama her deploy'da olur (300 MB DB için ~10-30 sn; startup probe bunu bekler).
- `uv sync --no-install-project` iki aşamalı katman: bağımlılıklar cache'lenir.
- `--set-secrets` env değişkeni her deploy'da sürüm numarası ile sabittir.
- Lokal `docker run` testi GCS'e erişemez; `LITESTREAM_DISABLED=1` dalı entrypoint'te.

## 6. Görevler

- [ ] F5-T01 `GcsStorage` — `backend/app/storage/gcs.py`
      Komut: `uv add google-cloud-storage`
      Doğrula: `uv run pytest tests/test_storage.py -q -k gcs` (sahte GCS istemcisi ile put/get/delete/list)
- [ ] F5-T02 [P] Dockerfile, `.dockerignore`, `.gcloudignore`, entrypoint, litestream.yml — kök ve `infra/*`
      Doğrula: `docker build -t ekstre:dev . && docker run --rm -e LITESTREAM_DISABLED=1 -e DB_PATH=/tmp/app.db -p 8080:8080 ekstre:dev` → `curl localhost:8080/api/healthz` 200; `docker run --rm --entrypoint sh ekstre:dev -c "ls /app/.venv/bin/python && litestream version"`; `gcloud meta list-files-for-upload | grep -c private` → 0
- [ ] F5-T03 [P] GCP kurulumu — `infra/setup.sh`
      Doğrula: `gcloud storage buckets describe gs://ekstre-db-prod` (versioning açık, lifecycle 30 gün); `gcloud secrets versions list gemini-key`; IAM bucket ve secret düzeyinde
- [ ] F5-T04 Litestream GCS smoke testi — geçici Cloud Run servisi veya lokal ADC ile
      Doğrula: 5 dk yazma sonrası `gcloud storage ls gs://ekstre-db-prod/app.db/` altında LTX dosyaları güncel; asılma varsa `0.5.15`'e pinle ve changelog'a yaz
- [ ] F5-T05 İlk deploy — komut §5.4 + `update-traffic --to-latest`
      Doğrula: `curl https://<url>/api/healthz` 200; kayıt → admin onayı → upload → dashboard
- [ ] F5-T06 [P] HSTS, structlog JSON + redaction — `backend/app/main.py`, `app/logging.py`
      Doğrula: `curl -I https://<url>/` `strict-transport-security` var; Cloud Logging'de e-posta yok (test kaydı)
- [ ] F5-T07 `/api/healthz` genişletme (Litestream hata sayaçları) — `backend/app/main.py`
      Doğrula: DB kapalıysa 503; metrics endpoint erişilemezse `litestream: "unknown"` ile 200 (sert bağımlılık değil)
- [ ] F5-T08 CI/CD — `.github/workflows/{ci,deploy}.yml`
      Doğrula: PR'da ci yeşil; main'de deploy tag'li revizyon oluşturuyor, canary URL'de healthz 200
- [ ] F5-T09 Deploy runbook'u ile gerçek deploy — `docs/runbooks/deploy.md`
      Doğrula: bakım bayrağı açıkken deploy; adım 2 süresi < 2 dk; deploy sonrası `transactions` sayısı eşit; yazma kesintisi ölçülüp changelog'a yazılır
- [ ] F5-T10 Restore ve reset tatbikatı — `docs/runbooks/restore.md`
      Doğrula: < 5 dk, `integrity_check` ok
- [ ] F5-T11 Monitoring alarmları — `infra/setup.sh` veya konsol; ekran görüntüsü runbook'a
      Doğrula: `/api/healthz`'i kasıtlı bozup alarm e-postası alınıyor
- [ ] F5-T12 [security-kvkk.md](../security-kvkk.md) kontrol listesi kapanışı
      Doğrula: tüm kutular işaretli, tarih ve kanıt linki ile
- [ ] F5-T13 Bu dosyada Durum → bitti, changelog; `docs/README.md`

## 7. Kabul kriterleri

- KK-1: Kapalı beta URL'sinde uçtan uca akış (kayıt → onay → yükle → dashboard → tavsiye) çalışır.
- KK-2: Deploy runbook'u ile deploy sonrası veri kaybı yok (işlem sayısı eşit); iki Litestream sürecinin kesişme süresi < 2 dk; yazma kesintisi < 5 dk.
- KK-3: Restore tatbikatı < 5 dk, `integrity_check` ok; `reset` senaryosu denenmiş.
- KK-4: CI keysiz (repo ve Actions secrets'ta GCP JSON key yok).
- KK-5: Cloud Build staging'e yüklenen dosyalar arasında `tests/private`, `.env`, `.venv` yok (`gcloud meta list-files-for-upload`).
- KK-6: Healthz 30 sn üst üste başarısızsa alarm.
- KK-7: [security-kvkk.md](../security-kvkk.md) tüm maddeler kapalı.

## 8. Riskler (bu faza özgü)

| Risk | Etki | Önlem |
|---|---|---|
| Deploy geçişinde iki Litestream süreci aynı replikada | Restore edilemez replika | Bakım bayrağı, tag'li revizyon, < 2 dk kesişme, `reset` runbook'u, DB bucket versioning |
| Litestream 0.5.16/17 GCS asılma regresyonu | Replikasyon sessizce durur | F5-T04 smoke test, `0.5.15` fallback, hata sayacı alarmı |
| `--source` ile gizli dosyaların yüklenmesi | KVKK ihlali | `.gcloudignore`, KK-5 |
| Bellek aşımı (DB + PDF) | OOM restart | 512Mi volume limiti, semaphore(2), alarm |
| Secret `latest` kullanımı | Beklenmedik rotasyon | Sabit sürüm |
| KVKK yurt dışı aktarım | Hukuki | Açık rıza; v2'de Vertex AI EU |

## 9. Açık sorular

- [NETLEŞTİRİLMELİ: `heartbeat-url` için harici servis mi, Cloud Monitoring uptime check yeterli mi (§5.6)]

## 10. Referanslar

- Litestream: config https://litestream.io/reference/config/ , restore https://litestream.io/reference/restore/ , replicate https://litestream.io/reference/replicate/ , metrics https://litestream.io/reference/metrics/ , tips (çoklu replikasyon uyarısı) https://litestream.io/tips/ , GCS https://litestream.io/guides/gcs/ , Docker https://litestream.io/guides/docker/ , Dockerfile https://github.com/benbjohnson/litestream/blob/main/Dockerfile , issue #1512 https://github.com/benbjohnson/litestream/issues/1512
- Cloud Run: deploy https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy , source deploy ve izinler https://docs.cloud.google.com/run/docs/deploying-source-code , public erişim https://docs.cloud.google.com/run/docs/authenticating/public , min instances (tag/trafik şartı) https://docs.cloud.google.com/run/docs/configuring/min-instances , max instances https://docs.cloud.google.com/run/docs/configuring/max-instances , in-memory volume https://docs.cloud.google.com/run/docs/configuring/services/in-memory-volume-mounts , health checks https://docs.cloud.google.com/run/docs/configuring/healthchecks , container contract https://docs.cloud.google.com/run/docs/container-contract , secrets https://docs.cloud.google.com/run/docs/configuring/services/secrets , traffic https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration , quotas https://docs.cloud.google.com/run/quotas , gcloudignore https://docs.cloud.google.com/sdk/gcloud/reference/topic/gcloudignore
- uv Docker: https://docs.astral.sh/uv/guides/integration/docker/
- uvicorn settings: https://uvicorn.dev/settings/
- google-github-actions/auth: https://github.com/google-github-actions/auth
- Doğrulama notu: [../reference/tech-verification-2026-09-16.md](../reference/tech-verification-2026-09-16.md)

## Changelog

- 2026-09-16 taslak oluşturuldu (monolit plandan bölündü; Node 24 / Python 3.13, uv katmanlama, Litestream 0.5 config ve binary kaynağı, in-memory volume limiti, sabit secret sürümü, bakım bayrağı runbook'u, `--no-traffic` deploy, restore tatbikatı, bucket düzeyi IAM eklendi)
- 2026-09-16 doğrulama turu 1: dört açık soru kapatıldı (binary yolu doğru; Dockerfile repo köküne; sync yaşı metriği yok → hata sayaçları; iki süreç aynı replika desteklenmiyor → kesişme < 2 dk + reset runbook'u); `--allow-unauthenticated`; `.gcloudignore` ve `.dockerignore`; `--tag canary` (salt `--no-traffic` revizyon başlamıyor); resmi deploy SA rolleri ve build SA; `shutdown-sync-timeout` 4s; Litestream #1512 regresyon uyarısı ve smoke test; startup probe; 32 MiB HTTP/1; `LITESTREAM_DISABLED` lokal dalı
