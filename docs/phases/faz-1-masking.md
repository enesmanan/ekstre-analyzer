# Faz 1 — CLI: Ekstre Maskeleme

| Durum | Tarih | Süre tahmini | Bağımlılık |
|---|---|---|---|
| uygulanıyor | 2026-09-16 | 1,5 hafta | yok |

Önceki: — · Sonraki: [Faz 2](faz-2-extraction-sqlite.md) · İlgili ADR: [ADR-0003](../decisions/0003-pymupdf-redaction.md), [ADR-0002](../decisions/0002-pdf-native-input-no-png.md)

## 1. Amaç

Elindeki gerçek banka ekstresini komut satırından güvenli şekilde maskelemek ve maskelemenin başarılı olduğunu makine ile doğrulamak. Ürünün geri kalanının gizlilik iddiası bu fazın doğruluğuna dayanır. Faz bitince: `mask` komutu bir ekstreyi maskeler, `verify` komutu sızıntı yoksa 0 ile çıkar, CI sentetik ekstrelerle her iki komutu test eder.

## 2. Kapsam / Kapsam dışı

- Kapsam: Metin katmanı olan PDF'ler, şifreli PDF'ler (şifre kullanıcıdan alınır), banka profilleri (YAML), built-in desenler, sızıntı testi, sentetik test ekstresi üretici, görsel çıktı.
- Kapsam dışı: Taranmış/görüntü ekstreler (v2, OCR), LLM çağrısı ([Faz 2](faz-2-extraction-sqlite.md)), kullanıcı bazlı ayarlar ([Faz 4](faz-4-auth-admin.md)), tarayıcı içi maskeleme.

## 3. Ön koşullar

- [ ] Python 3.13 ve `uv` kurulu (`uv --version` ≥ 0.12)
- [ ] Geliştiricinin kendi TOM Bank ekstresi `backend/tests/private/tom.pdf` (klasör `.gitignore`'da). v1'in tek hedef bankası TOM'dur; tüm fazlar bu ekstre üzerinden doğrulanır.
- [ ] TOM ekstresi şifreliyse şifre biliniyor; şifre hiçbir dosyaya yazılmaz

## 4. Teslimatlar

| Teslimat | Açıklama |
|---|---|
| `uv run cli.py mask INPUT.pdf -o OUT.pdf [--profile tom] [--password ...] [--term "..."]` | Maskelenmiş PDF üretir. `--profile` verilmezse otomatik tespit; tespit başarısızsa `generic` profil + uyarı. `--term` birden fazla verilebilir (serbest metin maskeleme). `--password` verilmezse ve PDF şifreliyse stdin'den gizli okur. |
| `uv run cli.py inspect INPUT.pdf [--page N]` | Sayfa / blok / satır / span dökümü; profil yazarken kullanılır. |
| `uv run cli.py verify MASKED.pdf [--profile tom] [--expect-absent DOSYA]` | Sızıntı testi. Herhangi bir bulgu varsa exit code 1. `--expect-absent` satır satır "bu string'ler kesinlikle olmamalı" listesi (lokal, gitignore'da). |
| `uv run cli.py render MASKED.pdf -o DIR --dpi 100` | Sayfaları PNG'ye çevirir (elle görsel kontrol). |
| `backend/profiles/generic.yaml`, `tom.yaml` (tam) | Tek banka: TOM. Başka banka profili v1 kapsamı dışında; `generic` yalnızca fallback. `detect.any` değerleri `inspect` çıktısından alınır. |
| `backend/tests/fixtures/make_statement.py` | Sentetik ekstre üreten script (PyMuPDF `insert_text` ile); CI bunu kullanır. |
| `backend/tests/test_patterns.py`, `test_masker.py`, `test_verify.py` | Birim ve uçtan uca testler. |

## 5. Tasarım

### 5.1 Modüller

```
backend/app/anonymizer/
├── patterns.py     # built-in regex'ler + Luhn / TCKN checksum yardımcıları
├── profile.py      # YAML yükleme, Pydantic doğrulama, banka tespiti
├── layout.py       # PyMuPDF'ten satır modeli: Line(text, spans[(text, rect)])
├── masker.py       # mask(pdf_bytes, profile, password, extra_terms) -> MaskResult
├── verify.py       # leak_scan(pdf_bytes, profile) -> list[Finding]
└── sanitize.py     # scrub, metadata, JS / gömülü dosya tespiti
backend/cli.py      # typer: mask / inspect / verify / render
backend/profiles/*.yaml
```

`MaskResult`: `pdf_bytes`, `bank`, `page_count`, `redaction_count`, `warnings`, `masked_sha256`.

### 5.2 Profil formatı

```yaml
bank: tom
version: 1
detect:                       # ilk sayfa metni; hiçbiri eşleşmezse generic
  any: ["TOM Katılım", "tombank"]   # [NETLEŞTİRİLMELİ: gerçek değerler `inspect` ile ekstreden alınır]
mask:
  builtin: [iban, card_number, tckn, phone, email]
  regex:
    - name: customer_no
      pattern: 'Müşteri No\s*:?\s*(\d{6,})'
      group: 1
    - name: name_line
      pattern: '^(Sayın|Adı Soyadı)\s*:?\s*(.+)$'
      group: 2
    - name: address_block         # etiketle başlayan satırın tamamı
      pattern: '^(Adres|Adresi)\s*:?\s*(.+)$'
      group: 2
keep:                         # asla maskeleme (regex, satır metnine uygulanır)
  - 'İşlem Tarihi'
  - 'Toplam'
padding_pt: 1.0
```

`generic.yaml`: sadece `builtin` listesi + `name_line`/`address_block`; `detect` boş. Kullanıcı `--term` ile eklediği her metin (min 3 karakter, boşluk kırpılmış) `mask.regex` listesine `(?<!\w)` + `re.escape(term)` + `(?!\w)` olarak, büyük/küçük harf duyarsız eklenir; kısmi kelime eşleşmesi yapılmaz (Faz 4 `extra_terms` aynı kuralı kullanır).

Built-in desenler (`patterns.py`):

| Ad | Desen | Ek doğrulama |
|---|---|---|
| `iban` | `TR\d{2}\s?(\d{4}\s?){5}\d{2}` | mod-97 kontrolü isteğe bağlı; eşleşme yeterli |
| `card_number` | `(?<![\dX*])(?:\d{4}|\d[\dX*]{3}|[X*]{4})(?:[\s-]?[\dX*]{4}){2}[\s-]?\d{4}(?![\dX*])` | Bankalar kartı zaten kısmen maskeler; `4XXX XXXX XXXX 1234`, `1234 **** **** 5678` ve 16 hane tam rakam eşleşir. Tamamı rakamsa **Luhn şart** (aksi halde IBAN parçası ve 16 haneli referans no yakalanır) |
| `tckn` | `(?<!\d)[1-9]\d{10}(?!\d)` | TCKN checksum (10. ve 11. hane) geçmeli; geçmezse maskeleme, 11 haneli hesap numarası olabilir → `long_digits` yakalar |
| `phone` | `(?<!\d)(?:\+90|0)?\s?\(?5\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)` | Lookaround sınırları şart; sınırsız desen referans numaralarının ortasını siler |
| `email` | `[\w.+-]+@[\w-]+\.[\w.-]+` | |
| `long_digits` | `\b\d{8,}\b` | Yalnızca `verify` uyarısı (sızıntı adayı); `mask` içinde profil açıkça isterse |

### 5.3 Algoritma (`masker.mask`)

1. `doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")`. `doc.needs_pass` ve şifre verilmemişse `PasswordRequired`; `doc.authenticate(password)` `0` dönerse `WrongPassword`. Şifre değişkeni fonksiyon bitince silinir, log'a yazılmaz.
2. `doc.is_pdf` değilse reddet. `sanitize.check(doc)` şu durumlardan biri varsa `UnsafePdf`: `doc.embfile_count() > 0`; `cat = doc.pdf_catalog()` için `doc.xref_get_key(cat, "Names/JavaScript")[0] != "null"`; `doc.xref_get_key(cat, "OpenAction/S")[1] == "/JavaScript"`; herhangi bir xref'te `doc.xref_get_key(x, "S")[1] == "/JavaScript"` (sayfa `/AA`, annotasyon ve form JS'ini de yakalar); `doc.is_form_pdf`; herhangi bir sayfada `page.annots(types=[pymupdf.PDF_ANNOT_FILE_ATTACHMENT])` boş değil. Düz `OpenAction` (GoTo) meşrudur, reddetme.
3. Profil tespiti: ilk sayfa `get_text("text")` içinde `detect.any` listesinden biri geçiyorsa o profil; hiçbiri geçmiyorsa `generic` + `warnings.append("profile: generic")`. Metin katmanı boşsa (ilk 2 sayfada 20'den az kelime) `ScannedPdf` hatası.
4. `pymupdf.TOOLS.set_small_glyph_heights(True)` (`TOOLS` modül düzeyinde hazır örnek; `Tools()` diye sınıf çağrısı yok). Glif bbox'ı satır yüksekliği yerine karakter yüksekliği olur; ayar süreç-global, `layout.py` import anında bir kez çağrılır. Bu ayar kapalıyken 12 pt satır aralığında bir satırı redakte etmek üst ve alt satırı da siler (1.28.2'de doğrulandı).
5. Her sayfa için `layout.lines(page)`: `page.get_text("rawdict")` → blocks → lines → spans → `chars`; her karakter `{"c", "bbox", "origin"}`. Satır metni `"".join(c["c"])`, karakter indeksi → bbox eşlemesi doğrudan. (`"dict"` çıktısında `chars` yok; orantılı x-bölme kullanılmaz.)
6. Satır metni üzerinde önce `keep` regex'leri: eşleşen aralıklar korunur. Sonra profil `mask.regex` + `builtin` desenleri; eşleşen `group` aralığındaki karakter bbox'ları `Rect.include_rect` ile birleştirilir → `rect = rect + (pad, pad, -pad, -pad)`.
7. `page.add_redact_annot(rect, fill=(0, 0, 0))`. Sayfa başına tek `page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE, text=pymupdf.PDF_REDACT_TEXT_REMOVE)`.
8. `doc.scrub(metadata=True, xml_metadata=True, javascript=True, embedded_files=True, attached_files=True, hidden_text=True, remove_links=True, redactions=False)`. Not: `hidden_text=True` gizli metin bulursa kendi `apply_redactions`'ını varsayılan `graphics=REMOVE_IF_COVERED` ile çağırır; sentetik ve gerçek ekstrede çizgi kaybı görsel testte kontrol edilir.
9. `out = doc.tobytes(garbage=3, deflate=True)`; `masked_sha256 = sha256(out)`. Şifreli girdi çıktıda şifresizdir (`tobytes` varsayılan `encryption=PDF_ENCRYPT_NONE`).
10. `verify.leak_scan(out, profile)` çağrılır; bulgu varsa `MaskResult.warnings` yerine `LeakDetected` hatası (mask komutu exit 2).

### 5.4 Sızıntı testi (`verify.leak_scan`)

Maskeleme regex'leri ile aynı desenleri tekrar çalıştırmak totolojiktir; sadece kutu kaçırmalarını yakalar. Bu yüzden üç katman:

1. **Profil desenleri:** maskelenmiş PDF'ten `get_text("text")` alınır, `mask.regex` + `builtin` hiç eşleşmemeli.
2. **Bağımsız sezgisel kontroller:** Luhn geçen 13-19 haneli diziler; `long_digits` (8+ hane, tarih ve tutar değil); art arda 2-3 tamamı büyük harf kelime ve satırda tutar yok (ad soyad adayı); `@` içeren token. Bunlar `Finding(kind, page, snippet)` olarak döner; snippet ilk 4 karakter + `…` (log'a tam değer yazılmaz).
3. **Beklenen yokluk listesi:** `--expect-absent` dosyasındaki her satır maskelenmiş metinde geçmemeli (gerçek ekstre için elle hazırlanır, gitignore'da).

Ayrıca `render` ile PNG üretilip elle bakılır; kabul için zorunlu.

### 5.5 Bilinen tuzaklar

- PyMuPDF karakteri redaction dikdörtgeni ile **herhangi bir kesişimde** siler, tam kapsama şartı yok. `padding_pt` daraltması ve `TOOLS.set_small_glyph_heights(True)` birlikte kullanılır; yine de komşu karakter kaybı görsel testte kontrol edilir.
- `page.search_for` regex desteklemez; konum tespiti `get_text("rawdict")` karakter bbox'larından yapılır.
- Sentetik fixture'da `page.insert_text(fontname="helv")` Latin-1 kodlar; ş, ğ, ı, İ metin katmanına bozuk yazılır ve "Müşteri No", "Sayın", "İşlem Tarihi" regex'leri eşleşmez. Fixture `pymupdf.TextWriter` + `pymupdf.Font("helv")` veya `page.insert_htmlbox` ile yazılır; T02 doğrulaması `"Müşteri No" in page.get_text()` içerir.
- IBAN kelimeler arası boşlukla bölünmüş gelir; regex satır metnine uygulanır, kelime bazlı değil.
- Tutarlar (`1.234,56`) ve tarihler (`16/09/2026`) rakam desenlerine yakalanmamalı; `long_digits` `\b` sınırları ve nokta/virgül dışlaması ile ayrılır, `keep` listesi sütun başlıklarını korur.
- Şifreli PDF: `authenticate` sonrası `tobytes` şifresiz üretir. Şifre TCKN olabilir; asla loglanmaz, CLI'da `--password` yerine prompt önerilir.
- Gerçek ekstre CI'da yok: `make_statement.py` ile üretilen sentetik ekstre (IBAN, kart, TCKN, ad, adres, 30 işlem satırı, 3 sayfa) fixture'dır.
- PyMuPDF AGPL; ADR-0003'teki lisans notu.

## 6. Görevler

Format: `- [ ] F1-TXX [P] Açıklama — dosya`. Her görevin altında doğrulama komutu. Komutlar `backend/` içinden çalıştırılır.

### 6.1 Kurulum

- [ ] F1-T01 uv projesi, bağımlılıklar, `.gitignore` (`tests/private/`, `tests/out/`) — `backend/pyproject.toml`
      Doğrula: `uv sync && uv run python -c "import pymupdf, typer, yaml, pydantic; print(pymupdf.version)"`
      Komutlar: `uv init --python 3.13 && uv add pymupdf typer pyyaml pydantic && uv add --dev pytest`
- [ ] F1-T02 [P] Sentetik ekstre üretici (`TextWriter` + `Font("helv")`, Türkçe karakterler doğru; `--password` ile `save(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=...)`) — `backend/tests/fixtures/make_statement.py`
      Doğrula: `uv run python tests/fixtures/make_statement.py -o tests/fixtures/synthetic.pdf && uv run python -c "import pymupdf; d=pymupdf.open('tests/fixtures/synthetic.pdf'); print(d.page_count, 'Müşteri No' in d[0].get_text())"` → `3 True`. Üretici bilinen değerleri `tests/fixtures/synthetic_expected.json` içine yazar (IBAN, kart, TCKN, ad, telefon, e-posta, adres).

### 6.2 Çekirdek

- [ ] F1-T03 [P] Built-in desenler + TCKN checksum + Luhn — `backend/app/anonymizer/patterns.py`
      Doğrula: `uv run pytest tests/test_patterns.py -q` (pozitif/negatif örnekler: boşluklu IBAN, `4XXX XXXX XXXX 1234`, geçerli/geçersiz TCKN, tutar `1.234,56` eşleşmemeli)
- [ ] F1-T04 [P] Profil şeması ve yükleyici, banka tespiti — `backend/app/anonymizer/profile.py`, `backend/profiles/generic.yaml`
      Doğrula: `uv run pytest tests/test_profile.py -q`
- [ ] F1-T05 Satır modeli (`rawdict`, karakter bbox'ları, `TOOLS.set_small_glyph_heights(True)` import anında) — `backend/app/anonymizer/layout.py`
      Doğrula: `uv run pytest tests/test_layout.py -q` (sentetik PDF'te IBAN satırı tek `Line` olarak geliyor, karakter sayısı satır metni uzunluğuna eşit; 12 pt aralıklı komşu satır redaksiyonda korunuyor)
- [ ] F1-T06 Sanitizasyon kontrolleri ve scrub — `backend/app/anonymizer/sanitize.py`
      Doğrula: `uv run pytest tests/test_sanitize.py -q` (gömülü dosyalı ve JS'li fixture reddediliyor)
- [ ] F1-T07 Maskeleme — `backend/app/anonymizer/masker.py`
      Doğrula: `uv run pytest tests/test_masker.py -q` (sentetik ekstre: `synthetic_expected.json` içindeki hiçbir değer çıktı metninde yok; işlem satırlarındaki tutarlar ve tarihler duruyor; sayfa sayısı aynı)
- [ ] F1-T08 Sızıntı testi — `backend/app/anonymizer/verify.py`
      Doğrula: `uv run pytest tests/test_verify.py -q` (maskelenmemiş sentetik ekstrede ≥ 6 bulgu, maskelenmişte 0)
- [ ] F1-T09 CLI: mask / inspect / verify / render — `backend/cli.py`
      Doğrula (Git Bash): `uv run cli.py mask tests/fixtures/synthetic.pdf -o tests/out/masked.pdf && uv run cli.py verify tests/out/masked.pdf; echo $?` → 0. PowerShell'de `;` ile ayırıp `$LASTEXITCODE` oku.
- [ ] F1-T10 Şifreli PDF desteği (fixture: `make_statement.py --password 12345678901`) — `masker.py`, `cli.py`
      Doğrula: `uv run pytest tests/test_masker.py -q -k password`
- [ ] F1-T11 TOM profili: önce `uv run cli.py inspect tests/private/tom.pdf` ile başlık/etiket satırlarını çıkar, sonra `detect`, `mask.regex`, `keep` yaz — `backend/profiles/tom.yaml`
      Doğrula: `uv run cli.py mask tests/private/tom.pdf -o tests/out/tom-masked.pdf --profile tom && uv run cli.py verify tests/out/tom-masked.pdf --profile tom --expect-absent tests/private/absent.txt` → 0, ardından `render` ile göz kontrolü; `inspect` çıktısı ve `absent.txt` commit edilmez
- [ ] F1-T12 [P] Profil şeması testi — `backend/tests/test_profile.py`
      Doğrula: `uv run pytest tests/test_profile.py -q` (`tom.yaml` ve `generic.yaml` şema doğrulamasını geçiyor; `detect` boş profil yalnızca `generic`)

### 6.3 Kapanış

- [ ] F1-T13 Performans ölçümü — `tests/test_perf.py`
      Doğrula: 10 sayfalık sentetik ekstre `mask` < 2 sn (`uv run pytest tests/test_perf.py -q`)
- [ ] F1-T14 Bu dosyada Durum → bitti, changelog satırı; `docs/README.md` faz tablosunu güncelle

## 7. Kabul kriterleri

- KK-1: Sentetik ekstre maskelendiğinde `synthetic_expected.json` içindeki hiçbir değer çıktıda geçmez. Komut: `uv run pytest tests/test_masker.py -q`
- KK-2: TOM ekstresinde `verify --expect-absent` exit 0 döner ve PNG çıktısında işlem satırları, tarihler, tutarlar okunabilir.
- KK-3: 10 sayfalık ekstre için `mask` süresi < 2 sn.
- KK-4: `app/anonymizer/` içinde builtin `open(`, `doc.save(`, `write_bytes`, `write_text` çağrısı yok (`pymupdf.open` serbest); orijinal bytes hiçbir yere yazılmıyor. Komut: `grep -nE "(^|[^.\w])open\(|\.save\(|write_bytes|write_text" app/anonymizer/` → boş.
- KK-5: Şifreli sentetik ekstre `--password` ile maskeleniyor, çıktı şifresiz, şifre `tests/out/` altındaki hiçbir dosyada ve log'da yok.
- KK-6: JS veya gömülü dosya içeren PDF `UnsafePdf` ile reddediliyor.
- KK-7: Metin katmanı olmayan PDF `ScannedPdf` ile reddediliyor, mesaj "Taranmış ekstre desteklenmiyor" içeriyor.

## 8. Riskler (bu faza özgü)

| Risk | Etki | Önlem |
|---|---|---|
| Kesişim kuralı komşu karakterleri siler | Tutar/tarih bozulur, Faz 2 doğruluğu düşer | padding + small_glyph_heights, görsel test, `keep` listesi |
| Regex kişisel adı yakalamaz (havale açıklaması) | Ad LLM'e gider | `--term` ile kullanıcı terimleri, verify'da büyük harf ad sezgisi, KVKK metninde açık ifade |
| Banka formatı değişir | Profil kaçırır | `verify` her upload'da zorunlu; fail → işlem durur |
| Şifreli PDF | Açılamaz | `authenticate`, kullanıcıdan şifre |
| Taranmış ekstre | Maskelenemez | Reddet, v2 OCR |

## 9. Açık sorular

- Karar: tek banka TOM (2026-09-16); ek profil yok.
- [NETLEŞTİRİLMELİ: TOM ekstresi kart mı hesap ekstresi mi (katılım bankası; muhtemelen hesap); `inspect` çıktısına göre profil `statement_type` alanı ve "toplam" satırı regex'i belirlenir]
- [NETLEŞTİRİLMELİ: TOM ekstresi şifreli mi; şifre formatı]
- [NETLEŞTİRİLMELİ: `long_digits` mask'ta varsayılan açık mı? Açıksa hesap numaraları gider ama bazı referans numaraları da silinir]

## 10. Referanslar

- PyMuPDF Page (redaction, get_text, search_for): https://pymupdf.readthedocs.io/en/latest/page.html
- PyMuPDF Document (open, authenticate, scrub, tobytes): https://pymupdf.readthedocs.io/en/latest/document.html
- PyMuPDF TextPage (dict/words yapısı): https://pymupdf.readthedocs.io/en/latest/textpage.html
- PyMuPDF TOOLS.set_small_glyph_heights: https://pymupdf.readthedocs.io/en/latest/tools.html
- Komut notu: görev doğrulama komutları Git Bash sözdizimindedir (`&&`, `$?`); PowerShell 5.1'de `&&` yoktur.
- Doğrulama notu: [../reference/tech-verification-2026-09-16.md](../reference/tech-verification-2026-09-16.md)

## Changelog

- 2026-09-16 taslak oluşturuldu (monolit plandan bölündü; şifreli PDF, sentetik fixture, generic profil, bağımsız sızıntı sezgileri, scrub eklendi)
- 2026-09-16 kapsam kararı: tek hedef banka TOM; iki ek banka taslağı kaldırıldı, F1-T12 profil şema testi oldu
- 2026-09-16 doğrulama turu 1: kart/telefon/TCKN regex sınırları, `TOOLS` adı, `rawdict` karakter bbox'ları, JS tespit kuralı (düz OpenAction reddedilmez), fixture font notu, KK-4 grep düzeltildi
