# ADR-0004: SQLite WAL + Litestream → GCS

Durum: kabul edildi · Tarih: 2026-09-16 · İlgili faz: Faz 2, Faz 5

## Bağlam ve problem

Kapalı beta ölçeğinde (onlarca kullanıcı) kalıcı veri deposu gerekiyor. Cloud Run'ın yerel diski geçici. Ek yönetilen servis maliyeti ve operasyon yükü minimum olmalı.

## Değerlendirilen seçenekler

- SQLite dosyası doğrudan GCS FUSE mount üzerinde
- SQLite yerel (in-memory) disk + Litestream ile GCS'e sürekli replikasyon
- Cloud SQL Postgres (en küçük instance)
- Turso / hosted SQLite

## Karar

"SQLite yerel disk + Litestream → GCS", çünkü:

- GCS FUSE POSIX uyumlu değil, file locking yok, "last write wins"; SQLite bozulma riski.
- Litestream Cloud Run'da metadata sunucusundan kimlik alır, ek secret gerekmez.
- Cloud SQL v1 için aylık sabit maliyet ve bağlantı yönetimi getirir; SQLAlchemy sayesinde ileride geçiş modeli değiştirmez.

Uygulama kuralları (Litestream v0.5.x):

- Config: `dbs: - path: /data/app.db` altında **tekil** `replica: {url: gs://..., sync-interval: 1s}`. `replicas:` listesi ve replica altında `retention:` geçersiz.
- Global: `snapshot: {interval: 24h, retention: 72h}`, `shutdown-sync-timeout: 4s` (Cloud Run 10 sn SIGTERM penceresi = uvicorn 5 sn + Litestream 4 sn), `addr: "127.0.0.1:9090"` (Prometheus metrikleri; "son sync yaşı" metriği yok, hata sayaçları izlenir).
- DB altında `restore-if-db-not-exists: true` veya entrypoint'te `litestream restore -o PATH -if-db-not-exists -if-replica-exists URL`.
- Binary: `litestream/litestream:0.5.17` imajından `COPY --from=... /usr/local/bin/litestream`. `releases/latest/download/litestream-linux-amd64.tar.gz` yolu mevcut değil.
- **Aynı replikaya eşzamanlı iki süreç desteklenmez** (Litestream tips: restore edilemez duruma yol açabilir). Deploy geçişinde kesişme < 2 dk ve yazma kapalı (ADR-0005); kurtarma `litestream reset`.
- 0.5.16/0.5.17'de GCS yazımlarının asılı kalabildiği regresyon (issue #1512) bildirildi; Faz 5'te smoke test, gerekirse `0.5.15`.
- SQLite pragmaları bağlantı başına: `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`.
- Alembic `render_as_batch=True` (SQLite ALTER kısıtı).

## Sonuçlar

- İyi: Sıfır ek servis, 1 sn RPO, ücretsiz, tek dosya yedek.
- Kötü: Tek yazıcı gerektirir; deploy geçişinde iki revizyon çakışabilir (ADR-0005). Silinen kullanıcı verisi snapshot retention süresi (72 sa) ve bucket versioning (30 gün) boyunca replikada kalır; KVKK metninde belirtilir. DB in-memory dosya sisteminde olduğu için konteyner belleğini tüketir.
- Doğrulama tarihi ve kaynak: 2026-09-16, https://litestream.io/reference/config/ , https://litestream.io/guides/gcs/ , https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts
