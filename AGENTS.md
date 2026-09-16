# AGENTS.md — Development Loop

Bu repodaki **her coding agent** için bağlayıcıdır. İnsan developer da aynı loop'u izler.

**Ürün:** Ekstre Analyzer — TOM Bank ekstresini (PDF) sunucuda maskeleyip Gemini 3.8 Flash ile işlemlere ayıran, SQLite'ta saklayan ve sade bir dashboard'da gösteren kapalı beta uygulaması. Python 3.13 + FastAPI + PyMuPDF + SQLAlchemy/Alembic; Vite 8 + React 19 + TypeScript; SQLite + Litestream → GCS; Cloud Run tek instance.

> `docs/` altındaki planlama dokümanları **Türkçe** yazılır; kod, tanımlayıcılar, commit mesajları **İngilizce**dir. Terim eşlemesi için bkz. `docs/sozluk.md`.

**Tek hedef banka:** v1'in tamamı geliştiricinin kendi TOM Bank ekstresi üzerinden ilerler. Profil `backend/profiles/tom.yaml`, gerçek ekstre `backend/tests/private/tom.pdf` (gitignore). Başka banka profili yazılmaz; `generic.yaml` yalnızca fallback'tir.

---

## 0. Plan nerede yaşıyor

`docs/` klasörü git'te durur ve 24 dokümandan oluşur.

| Path | Amaç |
|---|---|
| `docs/README.md` | Harita, faz durum tablosu. **Her seferinde önce bunu oku.** |
| `docs/00-plan.md` | Ürün, faz listesi, doğrulanmış kararların özeti |
| `docs/01-architecture.md` | Bileşenler, veri akışı, repo ağacı, **§6 çapraz kesen ilkeler** |
| `docs/phases/faz-N-*.md` | 6 faz dokümanı (1, 2, 3, 3.5, 4, 5); her biri 10 bölüm + changelog |
| `docs/decisions/` | 7 kilitli ADR — **tartışmaya açık değil** |
| `docs/sozluk.md` | Doküman terimi ↔ kod adı eşlemesi |
| `docs/reference/tech-verification-2026-09-16.md` | Sürümler, API şekilleri, kaynak URL'leri; kod bununla çelişemez |
| `docs/security-kvkk.md` | Veri envanteri ve deploy öncesi kontrol listesi |
| `docs/risks-timeline.md` | Süre planı, riskler, kapsam kırpma sırası |

Faz dokümanı bölümleri: §3 Ön koşullar · §4 Teslimatlar · §5 Tasarım (5.1 modüller, 5.2 veri modeli, 5.3 API/CLI, "Bilinen tuzaklar" alt bölümü) · §6 Görevler · §7 Kabul kriterleri (DoD) · §8 Riskler · §9 Açık sorular · §10 Referanslar.

> **Uyarı:** Remote veya CI agent bu loop'u kullanacaksa ilgili faz dokümanını prompt'a yapıştır. Gerçek ekstre içeriğini (`tests/private/`) **hiçbir** prompt'a, log'a, commit'e veya sub-agent'a verme.

**Context budget:** Bir fazı implement ederken en fazla 5 doküman oku — `docs/README.md`, faz dokümanı, `01-architecture.md` §6, ilgili ADR'ler ve sözlük. `tech-verification` yalnızca bir API şekli tereddüdünde açılır.

---

## 1. Altın kurallar

Pazarlık konusu değildir. Tereddütte kaldığında dur ve sor.

1. **Plansız kod yok.** Her değişiklik bir faz görevine (`FN-TXX`) traceable olmalı.
2. **Validate edilmemiş plan implement edilmez.** Güncel dokümanlara *ve* clean-context bir reviewer'a karşı validate et.
3. **Test edilmemiş değişiklik ship edilmez.** Değişiklik türüne uygun bir testle kanıtla.
4. **Kanıtsız "done" yok.** Her kabul kriteri (§7) ve görev doğrulama satırı bir komut çıktısı ister.
5. **Her tamamlanan görev grubundan sonra commit at.** Tek cümle, İngilizce.
6. **ADR'ler kilitlidir.** Katılmıyor musun? Dur ve insana sor; gerekirse yeni ADR açılır, eskisi "yerini aldı" olur.
7. **Faz sırasını asla atlama.** §3 ön koşulları geçmeden hiçbir faz başlamaz.
8. **Orijinal PDF ve gerçek ekstre pahalı sınırdır.** Orijinal bytes asla diske yazılmaz (multipart/`UploadFile` yasak); gerçek TOM ekstresi yalnızca `tests/private/` altında ve yalnızca L4 testlerde kullanılır; sızıntı testi (`verify`) geçmeden Gemini çağrısı yapılmaz.
9. **Canlı Gemini çağrısı para harcar.** Testler `RecordedClient` ile çalışır; canlı çağrı yalnızca `--record` ile tek seferlik fixture üretiminde ve faz dokümanının açıkça istediği smoke testlerde.

---

## 2. Loop

```
1. PICK PHASE   docs/README.md durum tablosundan; fazın §3 ön koşul komutlarını çalıştır
2. PLAN         görev görev (FN-TXX)
3. VALIDATE     güncel dokümanlar + clean-context sub-agent   ← ikisi de zorunlu
4. IMPLEMENT    plan sırasıyla, her seferinde tek görev
5. TEST         değişiklik türünün gerektirdiği seviyede (§5 tablosu)
6. COMMIT       git add -A + tek cümle
7. CHECK DoD    faz §7 tamam mı? → 1'e dön
```

**Tüm 6 faz `bitti`** olana ve kapalı beta URL'sinde uçtan uca akış (kayıt → onay → TOM ekstresi yükle → dashboard → tavsiye) çalışana kadar kesintisiz sürer.

### 1 · Pick phase

Ön koşulları geçen en düşük numaralı faz. Faz §3 komutlarını **gerçekten çalıştır** — varsayma:

```bash
cd backend && uv sync && uv run pytest -q          # Faz 2'den itibaren
cd frontend && npm ci && npm test && npx tsc --noEmit   # Faz 3'ten itibaren
```

Kırmızı ön koşul, önceki fazın DoD'sinin eksik olduğu anlamına gelir. Geri dön; ilerleme.

Paralel yürütülebilen tek iş: KVKK metinleri ve `security-kvkk.md` kapanışı Faz 4-5 ile birlikte gider. Faz 3.5 Faz 3 bitmeden başlamaz. Aynı dosyada aynı bloğu iki agent düzenlemez.

### 2 · Plan

Faz dokümanının **§6 Görevler** listesi zaten bir plandır (`- [ ] FN-TXX [P] Açıklama — dosya` + doğrulama komutu). Onu executable hale getir:

- Görev başına: dokunulan dosyalar, yazılacak kod, **nasıl kanıtlanacağı** (doğrulama satırı)
- `[P]` olmayan görevler sıralıdır
- **§5.2 veri modeli ve §5.3 API/CLI** bölümlerindeki imzaları birebir kullan — asla API uydurma; Gemini/PyMuPDF/Litestream şekilleri `tech-verification`'dan
- Planlamadan önce fazın **"Bilinen tuzaklar"** bölümünü oku; her satır doğrulama turunda yakalanmış bir hatadır

Plan üç şeyi söylemeli: **ne** (hangi görevler, hangi sırayla), **nasıl kanıtlanır** (test seviyesi + komut), **ne bozulabilir** (dokunulan mevcut davranış).

### 3 · Validate — iki kontrol, ikisi de zorunlu

**3a. Güncel dokümanlara karşı.** Plan bir external dependency'ye yaslanıyorsa — Gemini Interactions API, PyMuPDF, Starlette, Litestream, Cloud Run — önce `docs/reference/tech-verification-2026-09-16.md`, oradaki bilgi yetmiyorsa resmi doküman. Hafızadan çalışma.

> Bu projede hafızanın kaçırdığı, doküman kontrolünün yakaladığı örnekler: `pymupdf.Tools()` diye sınıf yok (`TOOLS`); `get_text("dict")` karakter bbox'ı vermez (`rawdict`); `google-genai` varsayılanda retry yapmaz; Starlette `UploadFile` 1 MB üstünü diske yazar; PyJWT `sub` string ister; `gcloud run deploy --no-traffic` tag'siz revizyonu başlatmaz; Litestream `releases/latest/download/...-amd64` asset'i yok.

Kaynak bulunamadı mı? Assumption'ı faz dokümanının §9'una `[NETLEŞTİRİLMELİ: ...]` olarak yaz ve devam et. Asla sessizce tahmin etme.

**3b. Clean pair of eyes.** Planı **sıfır ön context'li** bir sub-agent'a ver. Yalnızca şunları görür: faz dokümanı, `01-architecture.md` §6, planın ve değiştireceğin dosyaların mevcut hali. Gerçek ekstre içeriği asla.

```
1. Bu plan §6'daki her görevi kapsıyor mu? Eksik ya da fazla bir şey var mı?
2. Mevcut davranışı bozabilir mi? Hangi dosyalar, onları başka kim kullanıyor?
3. Her adım verifiable mı? Hangi adım test edilemez?
4. §6 çapraz kesen ilkelerden (orijinal PDF diske yazılmaz, kuruş int, Gemini yasak parametreleri, log redaction) birini ihlal ediyor mu?
```

Sub-agent **read-only**'dir — review eder, yazmaz. Finding varsa plan düzeltilir, sonra yeniden validate edilir. Finding yoksa implement et.

### 4 · Implement

Plan sırasıyla, görev görev. İmzalar §5'ten birebir. Terimler sözlükten (`amount_kurus`, asla `amount`; `merchant_norm`, asla `merchant`; `effective_category`). Tuzaklar tekrarlanmaz. Hiçbir görev yarım bırakılmaz; biten görevin checkbox'ı faz dokümanında işaretlenir.

Plan yolda değişmek zorunda kalırsa: **dur, planı güncelle, değişiklik material ise yeniden validate et.** Asla sessizce drift etme. Bir ADR'yi değiştirmek gerekiyorsa §5'e göre dur.

### 5 · Test

**Hangi testin uyduğunu araştır — tahmin etme.** Seviyeler bu tabloda tanımlıdır:

| Seviye | Değişiklik | Komut |
|---|---|---|
| **L1** | Migration, model, pragma, storage | `cd backend && uv run pytest tests/test_db.py tests/test_storage.py -q` + boş DB'ye `uv run alembic -c app/db/alembic.ini -x db=/tmp/t.db upgrade head` |
| **L2** | Pure function: regex desenleri, layout, validate, chunker, money, token/maliyet | `cd backend && uv run pytest tests/test_patterns.py tests/test_validate.py tests/test_chunker.py -q` |
| **L3** | API ucu, iş akışı, auth, rate limit (httpx + `RecordedClient`); React bileşen/sayfa (vitest) | `cd backend && uv run pytest tests/test_api_*.py tests/test_auth_*.py -q` · `cd frontend && npm test` |
| **L4** | Gerçek TOM ekstresi ile maskeleme ve görsel kontrol; canlı Gemini smoke (`--record`); tarayıcıda uçtan uca akış; Lighthouse; deploy ve restore runbook'ları | Faz dokümanındaki komut; sonuç oranlar/süreler olarak `tests/private/eval.md`'ye (kişisel veri yok) |
| — | Yalnızca style veya copy | Görsel kontrol |

Testi yazmadan önce üç soru:

- Bunun bozabileceği en sinsi şey ne? *(genellikle: boş ekstre, şifreli PDF, komşu satır silinmesi, parça sınırı tekrarı, `stated_total = 0`, sekme yarışı, sahte `X-Forwarded-For`)*
- Yalnızca happy path'i mi test ediyorum? **Bir rejection testi var mı?** (`UnsafePdf`, `LeakDetected`, `413`, `401`, `404`)
- Yetkilendirme katmanına dokundun mu? O zaman üçü birden: **allows** + **rejects** + **başka kullanıcının kaydı 404**.

> Yalnızca "allows" testini yazmak en pahalı test hatasıdır — her şeye izin veren bir dependency de o testi geçer. Sızıntı testinde de aynı kural: maskelenmemiş sentetik ekstrede `verify` **kırmızı** olmalı.

Kırmızı test = **commit yok**. Önce düzelt.

### 6 · Commit

Doğrudan **`main`** üzerinde çalış. Faz dokümanları *ne* build edileceğini belirler; git branch'lerine karşılık gelmez.

```bash
git add -A
git commit -m "add tckn checksum and luhn helpers to patterns"
git push origin main
```

Tek cümle, İngilizce, lowercase, imperative, sonda nokta yok, ≤72 karakter. *Neyi* söyler, *nedenini* değil.

| İyi | Kötü |
|---|---|
| `add raw-body statement upload with 15 MiB limit` | `upload changes` |
| `fix neighbour line deletion with small glyph heights` | `bug fix` |
| `wire advice box to overview page` | `phase 3.5 progress` |

`git add -A` öncesi `git status` ile `tests/private/`, `tests/out/`, `.env` görünmediğini doğrula. Body yalnızca gerçekten gerekiyorsa.

**Commit imzası yok.** Mesaja `Co-Authored-By`, `Made-with: Cursor`, `Signed-off-by` (agent için) veya Cursor/Claude/Copilot trailer'ı ekleme. Author git config'deki insan developer'dır.

### 7 · Check Definition of Done

Faz **§7 Kabul kriterleri** bölümündeki her maddeyi tek tek işaretle. Her madde bir komut çıktısı ya da ölçüm ister — "çalışıyor" kanıt değildir. İşaretsiz madde = faz bitmemiş.

Tamamlanınca: faz dokümanının başındaki Durum tablosunu `bitti` yap, changelog satırı ekle, `docs/README.md` durum tablosunu güncelle. Sonra 1. adıma dön.

---

## 3. Ne zaman agent spawn edilir

Üç ayrı kullanım. Karıştırma.

**Paralel agent'lar — end-to-end research.** Birden fazla bilinmeyeni olan bir görevi planlarken. Her agent'a **farklı bir input dilimi** ver — iki agent'a asla aynı soruyu sorma.

```
Faz 2 (Gemini çıkarım) planlaması, 3 paralel agent:
  1 → Interactions API: response_format şekli, usage alanları, retry seçenekleri
  2 → PyMuPDF insert_pdf ile parçalama ve tobytes davranışı
  3 → mevcut kod: anonymizer MaskResult ve cli.py bugün ne yapıyor
```

**Sub-agent — clean-eyes review.** Implement etmeden önce zorunlu (adım 3b). Büyük bir değişiklikten sonra "bir şey bozdum mu?" için ve kendi kodunu review etmek için de — o noktada context'in kirlidir. Read-only; çıktı bir findings listesidir. Gerçek ekstre içeriği verilmez.

**Solo — geri kalan her şey.** Küçük, iyi anlaşılmış değişiklikler. Agent spawn etmenin de bir maliyeti vardır.

---

## 4. Orchestrator

Bir agent loop'u döndürür. İşi kod yazmak değil — cycle'ı işletmektir.

```
1. docs/README.md içindeki faz durum tablosunu oku
2. Ön koşulları geçen en düşük numaralı fazı seç
3. O fazın §3 ön koşul komutlarını ÇALIŞTIR — kırmızıysa geri dön
4. 2–7. adımları sür
5. Tamamlanınca faz Durum tablosunu ve README'yi güncelle
6. Sonraki turn
```

**Tam olarak üç nedenle durur:**

| Neden | Eylem |
|---|---|
| **Done** | 6 faz `bitti` **ve** kapalı beta URL'sinde uçtan uca akış TOM ekstresiyle çalışıyor |
| **Blocked** | Bir ADR tartışmalı, bir `[NETLEŞTİRİLMELİ]` maddesi görevi engelliyor ya da karar insana ait (§5) |
| **External clock** | Yalnızca Faz 5'te: GCP IAM/WIF yayılımı, Cloud Build süresi, Litestream regresyon düzeltmesi (#1512) beklenirken |

Başka hiçbir şey durdurmaz. Kırmızı test → fix. İnce plan → tamamla. Finding → işle.

**External clock çalışırken idle kalma:**

| Beklenen | Yapılabilecek iş |
|---|---|
| GCP kurulumu / build | `security-kvkk.md` maddeleri, `kvkk-aydinlatma.md` metni, runbook taslakları |
| Litestream düzeltmesi | `0.5.15` ile devam; alarm ve healthz işleri |

**Progress report** her fazdan sonra:

```
Faz N — bitti
  Görevler:    N/N
  Testler:     L1 x/x · L2 x/x · L3 x/x · L4 x/x
  DoD:         N/N madde, kanıtlı
  Commit'ler:  N
  Sonraki:     Faz M (ön koşullar geçiyor)
```

---

## 5. Dur ve sor

- Bir **ADR tartışmalı** (ör. "maskeleme tarayıcıda yapılmalı", "Postgres'e geçelim")
- Bir faz dokümanının **§9 Açık sorular** bölümündeki `[NETLEŞTİRİLMELİ]` maddesi eldeki görevi etkiliyor
- TOM ekstresinin gerçek yapısı faz dokümanındaki varsayımla çelişiyor (ör. kredi kartı değil hesap ekstresi; toplam satırı yok; şifre formatı)
- Bir **external kural (KVKK, Google kullanım politikası, Cloud Run limiti) planı imkânsız kılıyor**
- **Para söz konusu** (canlı Gemini çağrısı fixture dışı, GCP kaynağı, domain, Tier yükseltme)
- Eylem **irreversible** (production DB'ye migration, bucket silme, `litestream reset`, hesap silme testi gerçek veride)
- **Aynı test aynı nedenle üçüncü kez** kırmızı — yaklaşım büyük olasılıkla yanlış

Sorarken: bir paragraf context, sonuçlarıyla birlikte seçenekler ve **bir öneri**.

---

## 6. Yasaklar

| Asla | Neden |
|---|---|
| Testi geçsin diye zayıflatma | Kanıt değerini yok eder |
| Kanıtsız DoD maddesi işaretleme | Faz anlamsızlaşır |
| `docs/` klasörünü sessizce değiştirme | Single source of truth; changelog satırı ve duyuru şart |
| `faz-*` git branch'i açma | `main` üzerinde commit; fazlar yalnızca planlamadır |
| Kırmızı testle commit atma | — |
| Orijinal PDF bytes'ını diske/bucket'a yazma; multipart/`UploadFile` kullanma | ADR-0003, `01-architecture.md` §6 |
| `verify` geçmeden Gemini'ye PDF gönderme | ADR-0002, Faz 1 §5.3 |
| Gemini çağrısında `temperature`, `top_p`, `top_k`, `candidate_count`, `thinking_budget` | ADR-0001 |
| Tutarları `float` saklama veya `amount` diye adlandırma | `01-architecture.md` §6, sözlük |
| Gerçek ekstre içeriğini, e-postayı, PDF şifresini, işlem açıklamasını log'a, prompt'a, commit'e, fixture'a yazma | `security-kvkk.md` §3 |
| `tests/private/` dışında gerçek ekstre tutma; başka banka profili yazma | Bu dosya §0 |
| `RecordedClient` yerine testte canlı Gemini | Kural 9 |
| Aynı GCS replikasına iki Litestream sürecini bilerek çalıştırma; bakım bayrağı kapalıyken deploy | ADR-0004, ADR-0005 |
| Bir ADR'yi yerinde düzenleme | Yeni ADR açılır, eskisi "yerini aldı" |
| Commit'e Cursor/Claude/Copilot `Co-Authored-By` veya benzeri AI trailer ekleme | Author yalnızca insan developer; imza yok |

---

## 7. Quick reference

```bash
# Preconditions
cd backend && uv sync && uv run pytest -q
cd frontend && npm ci && npm test && npx tsc --noEmit

# Develop
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev                      # /api → :8000 proxy

# CLI (Faz 1-2)
cd backend && uv run cli.py mask tests/private/tom.pdf -o tests/out/tom-masked.pdf --profile tom
cd backend && uv run cli.py verify tests/out/tom-masked.pdf --profile tom --expect-absent tests/private/absent.txt
cd backend && uv run cli.py render tests/out/tom-masked.pdf -o tests/out/png
cd backend && uv run cli.py extract tests/out/tom-masked.pdf --db tests/out/app.db

# Test
cd backend && uv run pytest -q                  # L1 + L2 + L3 (ağ yok)
cd frontend && npm test                         # L3 UI
cd frontend && npx tsc --noEmit

# Schema
cd backend && uv run alembic -c app/db/alembic.ini -x db=app.db upgrade head
cd backend && uv run alembic -c app/db/alembic.ini -x db=app.db revision --autogenerate -m "..."

# Commit (main üzerinde)
git status && git add -A && git commit -m "tek cümle" && git push origin main
```

Kabuk notu: komutlar Git Bash sözdizimindedir. Bu makinede varsayılan kabuk PowerShell 5.1'dir; `&&` yerine `;` kullan veya Git Bash'e geç.

**Faz sırası:** `1 → 2 → 3 → 3.5 → 4 → 5` · KVKK metinleri ∥ 4-5

**Critical path:** `1 → 2 → 3 → 4 → 5`
