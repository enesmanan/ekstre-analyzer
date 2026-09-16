# Dokümantasyon İndeksi

Bu klasör tek indeks buradadır; başka yerde liste tutulmaz. Dosya adları ASCII kebab-case İngilizce, içerik Türkçe.

## Nereden başlamalı

1. [00-plan.md](00-plan.md) — ürün, fazlar, doğrulanmış kararlar (5 dk)
2. [01-architecture.md](01-architecture.md) — bileşenler, veri akışı, repo yapısı, çapraz kesen ilkeler
3. Çalışılacak fazın dosyası (aşağıdaki tablo)

## Faz durumu

| Faz | Dosya | Durum | Son güncelleme |
|---|---|---|---|
| 1 | [phases/faz-1-masking.md](phases/faz-1-masking.md) | bitti | 2026-09-16 |
| 2 | [phases/faz-2-extraction-sqlite.md](phases/faz-2-extraction-sqlite.md) | onaylı | 2026-09-16 |
| 3 | [phases/faz-3-dashboard.md](phases/faz-3-dashboard.md) | onaylı | 2026-09-16 |
| 3.5 | [phases/faz-3.5-ai-advice.md](phases/faz-3.5-ai-advice.md) | onaylı | 2026-09-16 |
| 4 | [phases/faz-4-auth-admin.md](phases/faz-4-auth-admin.md) | onaylı | 2026-09-16 |
| 5 | [phases/faz-5-cloud-run.md](phases/faz-5-cloud-run.md) | onaylı | 2026-09-16 |

Durum değerleri: taslak → onaylı → uygulanıyor → bitti. Bir faza başlarken durumu `uygulanıyor` yapın; biterken `bitti` ve changelog satırı.

## Diğer dokümanlar

| Dosya | İçerik |
|---|---|
| [decisions/README.md](decisions/README.md) | ADR indeksi (7 karar) |
| [security-kvkk.md](security-kvkk.md) | Veri envanteri, KVKK ve güvenlik kontrol listesi (deploy öncesi kapanır) |
| [risks-timeline.md](risks-timeline.md) | Zaman planı, program riskleri, kapsam kırpma sırası |
| [reference/tech-verification-2026-09-16.md](reference/tech-verification-2026-09-16.md) | Teknoloji doğrulama notu: sürümler, API şekilleri, kaynak URL'leri |
| [sozluk.md](sozluk.md) | Doküman terimi ↔ kod adı eşlemesi (kodda yalnızca sağ sütun) |
| [../AGENTS.md](../AGENTS.md) | Development loop: pick → plan → validate → implement → test → commit → DoD; yasaklar; test seviyeleri |
| [templates/phase-template.md](templates/phase-template.md) | Faz dosyası şablonu |
| [templates/adr-template.md](templates/adr-template.md) | ADR şablonu |
| [kvkk-aydinlatma.md](kvkk-aydinlatma.md) | Aydınlatma metni iskeleti (taslak; Faz 4 F4-T12 ile tamamlanır) |
| `runbooks/deploy.md`, `runbooks/restore.md` | Faz 5'te yazılır; henüz yok |
| [archive/ekstre-analiz-plan-v1.md](archive/ekstre-analiz-plan-v1.md) | Monolit plan v1 (arşiv, güncellenmez) |

## Yazım kuralları

- Faz dosyaları şablonu izler; görev satırı `- [ ] FN-TXX [P] Açıklama — dosya/yolu` ve altında doğrulama komutu.
- Doğrulama komutları Git Bash sözdizimindedir (`&&`, `$?`); PowerShell 5.1'de `&&` yoktur.
- Kabul kriterleri ölçülebilir: exit code, süre, sayı.
- Belirsizlikler `[NETLEŞTİRİLMELİ: ...]` ile işaretlenir; ajan bunları tahmin etmez, sorar.
- Bir karar değişirse ADR'yi güncelleme; yeni ADR aç, eskisini "yerini aldı" yap.
- Bir teknik iddia değişirse önce ilgili resmi dokümana bak, sonra `reference/tech-verification-*.md` dosyasını tarihli güncelle.
