# ADR-0005: Cloud Run tek instance, CPU always on

Durum: kabul edildi · Tarih: 2026-09-16 · İlgili faz: Faz 5

## Bağlam ve problem

SQLite tek yazıcı ister. Cloud Run yatay ölçeklenen bir platform; ölçeklenmeyi bilinçli olarak kapatmak gerekiyor. Litestream'in arka planda sürekli çalışması için CPU throttling kapalı olmalı.

## Değerlendirilen seçenekler

- Cloud Run, `min-instances=1`, `max-instances=1`, `--no-cpu-throttling`
- Compute Engine e2-micro VM + systemd (tam kontrol, ama yama/izleme yükü)
- Fly.io (volume + tek makine; GCP dışı, KVKK envanteri karmaşıklaşır)

## Karar

"Cloud Run tek instance", çünkü deploy, secret, log ve HTTPS hazır geliyor; VM bakımı tek geliştirici için gereksiz yük.

Uygulama kuralları:

- `--min-instances 1 --max-instances 1 --no-cpu-throttling --concurrency 40 --timeout 300 --cpu 1 --memory 1Gi`.
- **Tek yazıcı garantisi yoktur:** `max-instances` revizyon başına uygulanır; deploy geçişinde eski ve yeni revizyon aynı anda çalışabilir. Önlem: deploy öncesi bakım bayrağı (süreç içi `app.state.maintenance`; başlangıç değeri `MAINTENANCE` env'den, admin API ile değiştirilir; DB'de tutulmaz ki restore edilen replika bayrağı taşımasın) ile upload ve yazma uçları kapatılır; yeni revizyon `--no-traffic --tag canary` ile başlatılır (salt `--no-traffic` revizyon instance açmaz), tag URL'sinde doğrulanır, sonra `update-traffic --to-latest`. İki Litestream sürecinin kesişmesi < 2 dk. Faz 5 runbook'unda adım adım.
- SIGTERM sonrası 10 sn: uvicorn `--timeout-graceful-shutdown 5` + Litestream `shutdown-sync-timeout: 4s`.
- Startup probe `/api/healthz` (restore + migration bitmeden trafik gelmesin).
- Public erişim `--allow-unauthenticated` (uygulama kendi JWT'sini kullanır).
- `/data` için in-memory volume `size-limit=512Mi` ile (varsayılan FS zaten in-memory, limit bellek patlamasını önler).
- Bellek bütçesi 1 GiB: DB (≤ 300 MB hedef) + Python + eşzamanlı 2 PDF işleme.

## Sonuçlar

- İyi: Sıfır sunucu yönetimi, otomatik HTTPS, Secret Manager, WIF ile keysiz CI.
- Kötü: Deploy sırasında birkaç dakikalık yazma kesintisi (bakım bayrağı). Ölçek gerektiğinde Cloud SQL'e geçiş şart. Cold start yok ama min-instance sürekli ücretli.
- Doğrulama tarihi ve kaynak: 2026-09-16, https://docs.cloud.google.com/run/docs/configuring/max-instances , https://docs.cloud.google.com/run/docs/container-contract , https://docs.cloud.google.com/run/docs/configuring/services/in-memory-volume-mounts
