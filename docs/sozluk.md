# Sözlük — Doküman Terimi ↔ Kod Adı

Dokümanlar Türkçe, kod İngilizce. Kodda **yalnızca** sağ sütundaki adlar kullanılır.

| Doküman terimi | Kod adı | Not |
|---|---|---|
| Ekstre | `statement`, tablo `statements` | |
| İşlem / harcama satırı | `transaction`, tablo `transactions` | |
| Tutar (kuruş) | `amount_kurus: int` | Asla `amount`, asla `float` |
| Borç / alacak yönü | `direction: "debit" \| "credit"` | Harcama `debit`, iade/ödeme `credit` |
| İşyeri (normalize) | `merchant_norm` | Asla `merchant`; havale/EFT'de `HAVALE`/`EFT` |
| Kategori (model) | `category` | 18 sabit değer, `CATEGORIES` |
| Kategori (kullanıcı düzeltmesi) | `user_override_category` | |
| Etkin kategori | `effective_category` | `COALESCE(user_override_category, category)` |
| Güven | `confidence: float` (0..1) | |
| Taksit | `is_installment`, `installment_no`, `installment_total` | |
| Dönem | `period_start`, `period_end` (`date`); tavsiyede `period: "YYYY-MM"` | |
| Ekstredeki toplam harcama satırı | `stated_total_debit_kurus` | LLM + regex fallback |
| Banka (LLM'in okuduğu) | `statements.bank` | |
| Profil (maskeleme YAML'ı) | `statements.profile`, `MaskResult.bank` | `tom` veya `generic` |
| Maskeleme | `mask()`, modül `anonymizer`, `masker.py` | |
| Redaksiyon | `add_redact_annot` / `apply_redactions` | PyMuPDF terimi |
| Sızıntı testi | `verify` (CLI), `leak_scan()` (`verify.py`), `Finding` | |
| Maskeleme sonucu | `MaskResult(pdf_bytes, bank, page_count, redaction_count, warnings, masked_sha256)` | |
| Ek maskeleme terimleri | `extra_terms` (settings), `--term` (CLI) | Min 3 karakter, kelime sınırı |
| Şifreli PDF | `PasswordRequired`, `WrongPassword`; API `password_required`, `wrong_password` | |
| Taranmış ekstre | `ScannedPdf`; API `scanned_pdf` | v1'de reddedilir |
| Güvensiz PDF (JS, gömülü dosya, form) | `UnsafePdf`; API `unsafe_pdf` | `sanitize.py` |
| Sızıntı bulundu | `LeakDetected`; API `leak_detected` | |
| Tekrar yüklenen ekstre | `DuplicateStatement`; API `duplicate_statement` | `UNIQUE(user_id, masked_sha256)` |
| Çıkarım | `extract_statement()`, modül `extractor`, `Extraction`, `Txn` | |
| Parça (uzun ekstre) | `chunker.split()`, `chunk_index`, `ChunkTxn` | İlk sayfa bağlam olarak eklenir |
| Doğrulama katmanı | `validate.py`, `ValidationReport(status, issues)`, sütun `validation_issues_json` | |
| İnceleme gerekli | `status = "needs_review"` | Toplam sapması > %1 veya dönem dışı tarih |
| Durum | `status ∈ queued, masking, mask_failed, extracting, extract_failed, needs_review, done` | |
| LLM istemcisi | `LLMClient` (Protocol), `GeminiClient`, `RecordedClient` | `extract_chunk()`, `advise()` |
| Token kullanımı | `Usage(input_tokens, output_tokens, thought_tokens)`, sütunlar aynı adla + `cost_usd_micro` | |
| Tavsiye | `advice`, `Advice`, `Suggestion`, modül `advisor` | |
| Bayat tavsiye | `stale`, `source_txn_count` | |
| Kullanıcı | `users`, `current_user`, `get_current_user` | Dev user `id=1` (Faz 3), Faz 4'te pasif |
| Erişim belirteci | `access_token` (JWT, `sub=str(id)`) | Bellekte |
| Yenileme belirteci | `refresh_token` (cookie), tablo `refresh_tokens`, `family_id`, `family_expires_at` | Yeniden kullanım: `refresh_reuse` |
| Oturumları kapat | `sessions_revoked_at` | |
| Onay bekliyor | `is_active = 0`; API `pending_approval` | |
| Bakım bayrağı | `app.state.maintenance`; API `maintenance` (503); dependency `require_not_maintenance` | Süreç içi |
| Meşgul | API `busy` (503) | ≥ 4 bekleyen upload |
| Günlük bütçe | `GEMINI_DAILY_BUDGET_USD`; API `budget_exceeded` | |
| Hız sınırı | `ratelimit.py`, API `rate_limited` (429) | |
| Denetim kaydı | `audit_log`, `audit.py` | 90 gün |
| Artifact (maskelenmiş PDF saklama) | `ArtifactStorage`, `LocalStorage`, `GcsStorage`, ayar `keep_masked_pdf` | |
| Sağlık ucu | `/api/healthz` | |
| Hata gövdesi | `{"error": {"code", "message", "issues"}}` | Kodlar faz dokümanlarında |
| Sentetik ekstre | `tests/fixtures/make_statement.py`, `synthetic.pdf`, `synthetic_expected.json` | CI bunu kullanır |
| Gerçek ekstre | `tests/private/tom.pdf`, `tests/private/absent.txt`, `tests/private/eval.md` | gitignore; yalnızca L4 |
